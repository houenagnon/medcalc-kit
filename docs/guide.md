# User guide

This guide explains how medcalc-kit works and how to use it. Function signatures and examples are in the
[API reference](api.md), the expected inputs of each calculator are in the [calculator list](calculators.md), and
[`examples/tutorial.ipynb`](../examples/tutorial.ipynb) runs everything end to end.

- [1. The idea](#1-the-idea)
- [2. A whole evaluation in five steps](#2-a-whole-evaluation-in-five-steps)
- [3. The objects you handle](#3-the-objects-you-handle)
- [4. The five probes](#4-the-five-probes)
- [5. Generation artifacts](#5-generation-artifacts)
- [6. Using your own model](#6-using-your-own-model)
- [7. Comparing models and conditions](#7-comparing-models-and-conditions)
- [8. Customising prompts and scoring](#8-customising-prompts-and-scoring)
- [9. Good practices](#9-good-practices)
- [10. Troubleshooting](#10-troubleshooting)

## 1. The idea

MedCalc-Bench asks a model to read a patient note and compute a clinical value (creatinine clearance, anion gap,
QTc…). A wrong answer can come from four different failures, and the end-to-end score cannot tell them apart:

| competence | probe | the model is given… | it must… |
|---|---|---|---|
| finding the values | **E** extraction | the note and the list of fields | report each value with its unit as written |
| knowing the formula | **K** knowledge | the question and the variables (no values) | write the formula, one case per branch |
| plugging values in | **S** substitution | the formula and the values | substitute, without computing |
| computing | **A** arithmetic | the fully substituted expression | compute it |
| all of the above | **E2E** end to end | the note and the question | answer the benchmark question |

Each probe isolates one competence: the model receives everything the other steps would have produced, computed
by the **calculator registry**, an executable implementation of the 33 equation-based calculators that reproduces
all 660 test answers of MedCalc-Bench-Verified. Scoring is deterministic and never runs model output as code.

## 2. A whole evaluation in five steps

```python
import medcalc_kit as mk

# 1. Data: MedCalc-Bench-Verified at a pinned revision (downloaded once, then cached)
ds = mk.load(equation_only=True)                 # or mk.data.demo() to try things offline
test = ds.filter(split="test")

# 2. Items: one prompt per (example, probe), with everything needed to score the answer
suite = mk.ProbeSuite(schema=ds, k_pool=mk.data.usable_train_pool(ds))
items = suite.build(test)                        # DataFrame, one row per item

# 3. Generation: any model; answers are appended to a JSONL file (resumable)
mk.run_items(items, "outputs/qwen.jsonl", model, batch_size=16)

# 4. Scoring: one row per answer
scores = mk.score_records("outputs/qwen.jsonl", items, condition={"model": "qwen2.5-7b"})

# 5. Summary: per probe, share of well-formed answers, competence and overall accuracy
mk.summary(scores)
```

`model` can be a Hugging Face model (`mk.generation.hf.HFBackend`), any object with a `generate_batch` method, or a
plain function; see [section 6](#6-using-your-own-model).

## 3. The objects you handle

### Example

One benchmark row: `example_id` (`"<split>:<calculator id>:<row>"`), `calculator_id`, `calculator_name`, `note`,
`question`, `entities` (the annotated inputs, e.g. `{"age": [51, "years"], "sex": "Female"}`), `ground_truth`,
`lower` and `upper` (the tolerance interval). `ds[0]`, `ds["test:2:9"]` and `for ex in ds` give Examples;
`ds.df` is the underlying DataFrame with the dataset's original columns.

### Derivation

`mk.derive(calculator_id, entities)` returns the reference computation: `inputs` (canonical units), `coefficients`,
`steps` (each `name = expr`, with its value; the last is the answer), `branches` (the piecewise rules applied) and
`answer`. `d.to_frame()` shows it as a table.

### Item

A dict, or a row of the DataFrame returned by `ProbeSuite.build`:

| field | content |
|---|---|
| `item_id` | `"<example_id>:<probe label>"` |
| `probe` | the probe label (`"E"`, `"K"`… or your own label for a variant) |
| `task` | the probe that scores it, when the label differs (e.g. label `"Kg"`, task `"K"`) |
| `example_id`, `calculator_id`, `calculator_name` | where it comes from |
| `messages` | the chat to send: `[{"role": "system", ...}, {"role": "user", ...}]` |
| `max_new_tokens` | the token budget |
| `reference` | what the scorer needs (gold values, formula, test points…), never shown to the model |

`mk.probes.prompt(item)` prints the chat; `mk.reference_answer(item)` gives an answer the scorer accepts, which
shows the expected format.

### Record

What `run_items` writes, one JSON line per item, and `mk.read_records(path)` reads back as a DataFrame:
`item_id`, `example_id`, `calculator_id`, `probe`, `model_id`, `prompt_key`, `shared_generation`, `text` (the raw
answer), `n_prompt_tokens`, `n_new_tokens`, `truncated`, `seconds`, `batch_size`, `error`, `timestamp`, `meta.*`.
Answers collected another way only need `item_id` and `text`.

### Verdict

`mk.score(item, text)` returns a dict with at least `format_valid`, `correct` and `error_type` (`None` when
correct), plus details that depend on the probe (see below).

### Scores and summary

`mk.score_records(records, items)` returns one row per answer: the `condition` columns you passed, `item_id`,
`example_id`, `calculator_id`, `probe`, `task`, `prompt_key`, `category` (see
[section 5](#5-generation-artifacts)), `well_formed`, `correct`, `error_type`, `n_new_tokens`, `seconds`; with
`details=True`, also the answer `text` and the full `verdict`.

`mk.summary(scores)` returns per group: `n_units`, `well_formed` (share of well-formed answers), `competence`
(accuracy among well-formed answers) and `overall` (accuracy over all answers). Only well-formed answers can be
correct, so `overall = well_formed × competence`.

## 4. The five probes

| probe | the model ends with | reference | verdict details | error types |
|---|---|---|---|---|
| E | `{"<field>": {"value": …, "unit": …}, …}` | `fields`, `gold` | `fields` (result per field), `field_accuracy` | `format_invalid`, or the most frequent field error: `missing`, `wrong_value`, `unit_error`, `unparsable`, `unit_unparsable`, `hallucinated`, `gold_unconvertible` |
| K | `{"cases": [{"condition": …, "formula": …}]}` (patient mode: `{"formula": …}`) | `entities`, `symbols`, `answer`, `point_entities` | `point_pass_rate`, `original_point_correct`, `n_points`, `points` (with `details=True`) | `format_invalid`, `unparsable_formula`, `unknown_variable`, `wrong_at_patient_point`, `wrong_elsewhere` |
| S | `{"expression": …}` | `formula`, `values`, `gold_expression`, `gold_value` | `value_matches`, `missing_variables`, `match` | `format_invalid`, `unparsable_expression`, `unsubstituted_variable`, `premature_computation`, `missing_or_wrong_value`, `accidental_value_match`, `structure_or_assignment_error`, `too_ambiguous` |
| A | `{"result": …}` | `expression`, `gold_value` | `rel_error`, `correct_strict` | `format_invalid`, `arithmetic_error` |
| E2E | `{"answer": …}` | `ground_truth`, `lower`, `upper` | `rel_error` | `format_invalid`, `out_of_bounds` |

How each probe decides:

- **E**: field by field. Quantities are converted to canonical units on both sides (unit spellings such as
  `mg/dl`, `meq/L`, `inches`, `/µL` are normalised), relative tolerance 1 %. A value copied with the unit written in
  the note is accepted even if the annotation used another unit. Correct if every field is correct.
- **K**: the formula is evaluated at the patient's point and at up to 50 other points (real patients of the same
  calculator from `k_pool`, or perturbations of the patient), and compared with the registry (1 %). Correct only if
  right at every point. In the default `general` mode the prompt depends on the patient only through categorical
  fields (sex, drugs…), so many examples share a prompt: `summary` counts each distinct prompt once. In `patient`
  mode the model sees the values and writes the formula of the patient's branch.
- **S**: structural identity with the expected expression (reordering accepted), otherwise numerical equivalence
  after mapping the numbers back to variables. A partly computed answer is *not* a substitution, even if its value
  is right (`premature_computation`).
- **A**: relative error ≤ 1 % (`correct`) and ≤ 0.1 % (`correct_strict`).
- **E2E**: the answer must fall within the benchmark's interval.

Every probe reads the **last** JSON object of the answer, so the model may reason before it.

## 5. Generation artifacts

Before scoring, each answer is classified, in this order:

| category | meaning |
|---|---|
| `empty` | no text |
| `truncated` | the token budget was used up (needs `n_new_tokens`) |
| `degenerate` | the text loops (repeated lines or n-grams) |
| `format_invalid` | the probe found no answer in the expected format |
| `well_formed` | a usable answer: only these can be correct |

Small or compressed models often fail by producing artifacts rather than wrong answers; `well_formed` and
`competence` separate the two. Thresholds are options of `score_records(artifacts=...)`.

## 6. Using your own model

`run_items(items, out_path, model)` accepts:

```python
# a plain function: messages -> text (token counts unknown, so truncation is not detected)
def my_model(messages, max_new_tokens):
    return client.chat(messages, max_tokens=max_new_tokens)          # any API or local model

# or returning (text, n_prompt_tokens, n_new_tokens)
def my_model(messages, max_new_tokens):
    r = client.chat(messages, max_tokens=max_new_tokens)
    return r.text, r.prompt_tokens, r.completion_tokens

mk.run_items(items, "outputs/my_model.jsonl", my_model, model_id="my-model")

# an object with generate_batch(list_of_messages, max_new_tokens) -> [(text, n_in, n_out), ...] and model_id
from medcalc_kit.generation.hf import HFBackend                       # pip install "medcalc-kit[hf]"
model = HFBackend("Qwen/Qwen2.5-7B-Instruct", device="cuda:0")
mk.run_items(items, "outputs/qwen.jsonl", model, batch_size=16)
```

The runner generates each distinct prompt once (greedy decoding gives identical answers to identical prompts),
batches prompts of the same budget, writes one line per item as soon as it is generated, and skips items already in
the file: after an interruption, run the same command again. An exception on one prompt is recorded in `error` and
the run continues; those items are retried on the next run.

You can also skip `run_items` entirely and score answers collected elsewhere:

```python
answers = pd.DataFrame({"item_id": items.item_id, "text": my_texts})
mk.score_records(answers, items)
```

## 7. Comparing models and conditions

Add constant columns with `condition` and group by them:

```python
scores = pd.concat([
    mk.score_records("outputs/qwen-3b.jsonl", items, condition={"model": "qwen-3b"}),
    mk.score_records("outputs/qwen-7b.jsonl", items, condition={"model": "qwen-7b"}),
])
mk.summary(scores, by=("model", "probe"))
mk.summary(scores, by=("model", "calculator_id"))
```

Examples are identified by `example_id` in every table, so paired comparisons (same example, two conditions) are a
pivot away: `scores.pivot_table(index="item_id", columns="model", values="correct")`.

## 8. Customising prompts and scoring

Every setting is an argument with a documented default (`DEFAULT_*` constants in each probe module).

```python
from medcalc_kit.probes import arithmetic, knowledge

# prompts are templates with {placeholders}; other braces (JSON) are kept as written
item = arithmetic.build(ex, template='Compute {expression}. Answer as {"result": <number>}.',
                        max_new_tokens=1536, system_prompt=None, digits=4)

# several variants of a probe in one suite: labels become the probe names
suite = mk.ProbeSuite({"K": {"mode": "patient"}, "K_general": {"task": "K"}, "A": {"max_new_tokens": 1536}})

# scoring options per probe label or task
mk.score_records(records, items, scoring={"K_general": {"case_semantics": "first_match"}, "A": {"rel_tol": 0.001}})
```

| probe | build options | score options |
|---|---|---|
| E | `template`, `max_new_tokens`, `system_prompt`, `kind_hints`, `field_hints`, `fields` | `rel_tol`, `accept_unit_as_written` |
| K | `mode` (`general`/`patient`), `template`, `max_new_tokens`, `system_prompt`, `n_points`, `symbol_docs`, `digits` | `rel_tol`, `abs_tol`, `n_points`, `case_semantics`, `perturbation_factor`, `plausible_ranges`, `details` |
| S | `template`, `max_new_tokens`, `system_prompt`, `digits`, `symbol_docs` | `equiv_rel_tol`, `value_rel_tol` |
| A | `template`, `max_new_tokens`, `system_prompt`, `digits` | `rel_tol`, `strict_rel_tol` |
| E2E | `template`, `max_new_tokens`, `system_prompt` | `rel_tol` (instead of the benchmark interval) |

All builders also take `label`. The placeholders of each template are listed next to its `DEFAULT_TEMPLATE`.

## 9. Good practices

- **Pin the dataset revision.** `mk.load()` uses `data.DEFAULT_REVISION`, the version the registry was verified
  against. Pass `revision=` explicitly in papers and record it.
- **Use the whole dataset as `schema`** (`ProbeSuite(schema=ds)`), so that E asks the same fields for every example
  of a calculator, including optional ones.
- **Give K real test points.** `k_pool=mk.data.usable_train_pool(ds)` uses train patients that do not leak test
  notes, are reproduced by the registry and are plausible. Without a pool, perturbations of the patient are used.
- **Count K prompts once.** In `general` mode, examples of a calculator share prompts; `summary` and `to_units`
  collapse them so that a single answer is not counted twenty times.
- **Report artifacts.** Read `well_formed` before `competence`: a model that never answers in the right format has
  an undefined competence, not a low one.
- **Check your pipeline without a model**: score `mk.reference_answer(item)` for every item; everything should be
  correct (this is part of the test suite on the full test split).

## 10. Troubleshooting

| symptom | cause and fix |
|---|---|
| `KeyError: "calculator 6 (...) needs the entity 'height'"` | the entities miss an input; [calculators.md](calculators.md) lists the expected names |
| `KeyError: "unknown calculator '1'"` | only the 33 equation-based calculators are implemented: load with `equation_only=True` |
| every answer is `truncated` | `max_new_tokens` too small for a reasoning model: raise it in the suite options |
| every answer is `format_invalid` | the model does not end with the JSON object; look at `score_records(..., details=True).text` and adapt the template |
| K is `wrong_elsewhere` | right formula for this patient but wrong branch or constant elsewhere; `mk.score(item, text, details=True)["points"]` shows each test point |
| `error_type` is `NaN` in a DataFrame | the answer is correct (`None` becomes `NaN` in pandas) |
| `run_items` returns 0 | every item is already in the output file; delete it or use another path to regenerate |
| the dataset does not load | `mk.load` needs network access the first time, then reads the Hugging Face cache |
