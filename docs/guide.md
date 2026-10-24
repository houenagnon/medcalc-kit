# User guide

This guide explains how medcalc-kit works and how to use it. Function signatures and examples are in the
[API reference](api.md), the expected inputs of each calculator are in the [calculator list](calculators.md).
[`examples/evaluate_model.ipynb`](../examples/evaluate_model.ipynb) evaluates a model in one call, and
[`examples/tutorial.ipynb`](../examples/tutorial.ipynb) walks through every building block.

- [1. The idea](#1-the-idea)
- [2. Evaluating a model](#2-evaluating-a-model)
- [3. Working with the benchmark and splits](#3-working-with-the-benchmark-and-splits)
- [4. The objects you handle](#4-the-objects-you-handle)
- [5. The probes](#5-the-probes)
- [6. Generation artifacts](#6-generation-artifacts)
- [7. Using your own model](#7-using-your-own-model)
- [8. Comparing models and conditions](#8-comparing-models-and-conditions)
- [9. Customising prompts and scoring](#9-customising-prompts-and-scoring)
- [10. Prompt design and robustness](#10-prompt-design-and-robustness)
- [11. Further analyses](#11-further-analyses)
- [12. Good practices](#12-good-practices)
- [13. Troubleshooting](#13-troubleshooting)

## 1. The idea

MedCalc-Bench asks a model to read a patient note and compute a clinical value (creatinine clearance, anion gap,
QTc…). A wrong answer can come from five different failures, and the end-to-end score cannot tell them apart:

| competence | probe | the model is given… | it must… |
|---|---|---|---|
| finding the values | **E** extraction | the note and the list of fields | report each value with its unit as written |
| converting units | **U** conversion | one value in another unit, and the formula's unit | convert it |
| knowing the formula | **K** knowledge | the question and the variables (no values) | write the formula, one case per branch |
| plugging values in | **S** substitution | the formula and the values | substitute, without computing |
| computing | **A** arithmetic | the fully substituted expression | compute it |
| all of the above | **E2E** end to end | the note and the question | answer the benchmark question |

Each probe isolates one competence: the model receives everything the other steps would have produced, computed
by the **calculator registry**, an executable implementation of the 33 equation-based calculators that reproduces
all 660 test answers of MedCalc-Bench-Verified. Scoring is deterministic and never runs model output as code.

So the kit evaluates a model at two levels:

- **general**: the original task (E2E) on the whole benchmark, 55 calculators and 1,100 test examples (equations,
  rule-based scores such as CHA2DS2-VASc, and dates), comparable with published MedCalc-Bench results;
- **step by step**: E, U, K, S and A on the 33 equation-based calculators (660 test examples), the only ones whose
  calculation can be split into steps, with E2E on the same examples to see where the chain breaks.

## 2. Evaluating a model

### In one call

```python
import medcalc_kit as mk
from medcalc_kit.generation.hf import HFBackend                    # pip install "medcalc-kit[hf]"

model = HFBackend("Qwen/Qwen2.5-7B-Instruct", device="cuda:0")      # or any function messages -> text
report = mk.evaluate_model(model, batch_size=16)
report
```

```text
MedCalc-Bench evaluation of Qwen/Qwen2.5-7B-Instruct
  general (end to end): 41.2% of 1100 examples (55 calculators)
  step by step (660 examples of equation-based calculators):
    E    extraction         85.0%
    U    unit conversion    80.3%
    K    formula knowledge  20.1%
    ...
```

(Illustrative numbers.) The report's views are DataFrames:

| view | content |
|---|---|
| `report.general` | E2E accuracy per category (lab test, physical, dosage, risk, severity, diagnosis, date) and `all` |
| `report.steps` | per step (E, U, K, S, A, E2E on the same examples): `n`, `well_formed`, `competence`, `accuracy` |
| `report.by_calculator` | accuracy per calculator and step |
| `report.examples` | one row per example: correct at each step, and `first_failure`, the first step that fails |
| `report.first_failures` | how often each step is the first to fail, and the E2E accuracy in each case |
| `report.consistency` | E2E accuracy when every step succeeds and when a step fails |
| `report.prompt_sensitivity` | with `prompt_variants=3`: accuracy per step and wording, mean, sd, range ([section 10](#10-prompt-design-and-robustness)) |
| `report.by_label` | accuracy per item label: custom variants (`Kg`) and paraphrases (`K@v2`) |
| `report.llm_vs_auto` | with `judge=`: the LLM evaluation next to the automatic one, per probe ([section 11](#11-further-analyses)) |
| `report.scores`, `report.items` | every answer (text, verdict) and every prompt, for your own analyses |

Everything is saved in `output_dir` (default `medcalc_eval/<model id>/`): the items, `generations.jsonl` (written
as the model answers) and the views as CSV. Running the same call again resumes an interrupted run;
`mk.evaluate_model(None, output_dir, model_id=...)` rescores saved generations without a model.

Useful options: `prompt_variants=3` to measure the sensitivity to the wording, `per_calculator=5` to try a model
quickly on 5 examples per calculator, `steps=()` for the general
score only, `k_mode="general"` for K without the patient's values, `probe_options={"E2E": {"max_new_tokens": 4096}}`
for a reasoning model, `dataset=` and `split=` to evaluate other examples.

To compare models, evaluate each and concatenate their scores: see [section 8](#8-comparing-models-and-conditions).

### Step by step, with the building blocks

`evaluate_model` chains five functions that can be used on their own, e.g. to change the examples, the probes or
the prompts:

```python
import medcalc_kit as mk

# 1. Data: MedCalc-Bench-Verified at a pinned revision (downloaded once, then cached)
ds = mk.load()                                   # all 55 calculators (or mk.data.demo() offline)
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

`model` can be a Hugging Face model (`mk.generation.hf.HFBackend`), any object with a `generate_batch` or
`generate` method, or a plain function; see [section 7](#7-using-your-own-model). `ProbeSuite` builds E2E for every
example and the step probes only for the 33 equation-based calculators.

## 3. Working with the benchmark and splits

`mk.load()` returns a `MedCalcDataset`: the benchmark as a DataFrame (`ds.df`, original columns plus `entities`,
`split` and `example_id`) with methods that each return a new dataset. Nothing is modified in place.

```python
ds = mk.load()                                   # 55 calculators, splits "train" and "test"
ds                                               # MedCalcDataset(11638 examples, 55 calculators; train: 10538, test: 1100)
ds.splits()                                      # examples and calculators per split
ds.calculators()                                 # examples per calculator and split
```

**Selecting.** Every criterion of `filter` takes one value or a list; `where` takes any condition on the DataFrame.

```python
ds.filter(split="test", category=["lab test", "physical"])
ds.filter(calculator=[2, 3, 9], note_type="Extracted")
ds.filter(where=lambda df: df["Patient Note"].str.len() < 2000)
ds.select(["test:2:1", "test:2:2"])              # given examples, in this order
ds.sample(5, per_calculator=True, seed=0)        # a quick, stratified subset
ds.equation_only()                               # the 33 equation-based calculators
```

**Making splits.** The `split` column is free: create any split, at any time.

```python
# a dev set: 10 % of each calculator's training examples, never leaking into the test set
ds = ds.split_off("dev", fraction=0.1, exclude_leaks=True)          # or n=20 per calculator
# k-fold cross-validation over train: 5 datasets, the i-th with fold i in "dev"
for fold in ds.folds(5):
    ...
# your own split from example ids (e.g. hard cases you selected)
ds = ds.assign_split(hard_ids, "hard")
```

`split_off` and `folds` are stratified by calculator and reproducible (`seed`). With `exclude_leaks=True`, an
example whose note also appears in the test set (or an extracted note of a test patient) is never moved.

**Saving and restoring a split.** A split is a mapping `example_id -> split`; save it to reuse it later or share it:

```python
ds.save_splits("splits/dev10.csv")
ds = mk.load().with_splits("splits/dev10.csv")   # the same split, on a fresh copy of the benchmark
ds.with_splits({"test:2:1": "hard"})             # or a dict / DataFrame / Series; drop_unassigned=True keeps only those
```

**Adding your own examples.** Build a dataset from records with the benchmark's column names, and concatenate:

```python
mine = mk.data.from_records([{"Calculator ID": 6, "Patient Note": "...", "Question": "...",
                              "entities": {"weight": [80, "kg"], "height": [180, "cm"]},
                              "Ground Truth Answer": 24.69}], split="mine")
ds = ds + mine                                   # or mk.data.concat(ds, mine, ...)
```

**Evaluating on any split.** `evaluate_model(model, dataset=ds, split="dev")` (or `split=["dev", "test"]`). The K test
points are taken from "train" examples that do not leak into the evaluated splits; for other uses,
`mk.data.usable_train_pool(ds, test=["dev", "test"])` gives the same pool.

## 4. The objects you handle

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
[section 6](#6-generation-artifacts)), `well_formed`, `correct`, `error_type`, `n_new_tokens`, `seconds`; with
`details=True`, also the answer `text` and the full `verdict`.

`mk.summary(scores)` returns per group: `n_units`, `well_formed` (share of well-formed answers), `competence`
(accuracy among well-formed answers) and `overall` (accuracy over all answers). Only well-formed answers can be
correct, so `overall = well_formed × competence`.

## 5. The probes

| probe | the model ends with | reference | verdict details | error types |
|---|---|---|---|---|
| E | `{"<field>": {"value": …, "unit": …}, …}` | `fields`, `gold` | `fields` (result per field), `field_accuracy` | `format_invalid`, or the most frequent field error: `missing`, `wrong_value`, `unit_error`, `unparsable`, `unit_unparsable`, `hallucinated`, `gold_unconvertible` |
| U | `{"value": …}` | `field`, `source_value`, `source_unit`, `target_unit`, `gold_value` | `rel_error` | `format_invalid`, `unconverted`, `inverse_factor`, `wrong_value` |
| K | `{"cases": [{"condition": …, "formula": …}]}` (patient mode: `{"formula": …}`) | `entities`, `symbols`, `answer`, `point_entities` | `point_pass_rate`, `original_point_correct`, `n_points`, `points` (with `details=True`) | `format_invalid`, `unparsable_formula`, `unknown_variable`, `wrong_at_patient_point`, `wrong_elsewhere` |
| S | `{"expression": …}` | `formula`, `values`, `gold_expression`, `gold_value` | `value_matches`, `missing_variables`, `match` | `format_invalid`, `unparsable_expression`, `unsubstituted_variable`, `premature_computation`, `missing_or_wrong_value`, `accidental_value_match`, `structure_or_assignment_error`, `too_ambiguous`, `unconverted_value` (S+U) |
| A | `{"result": …}` | `expression`, `gold_value` | `rel_error`, `correct_strict` | `format_invalid`, `arithmetic_error` |
| E2E | `{"answer": …}`: a number, `"MM/DD/YYYY"` or `{"weeks": …, "days": …}` | `ground_truth`, `lower`, `upper`, `answer_type` | `rel_error` (numbers), `error_days` (dates) | `format_invalid`, `out_of_bounds`, `wrong_date`, `wrong_duration` |

How each probe decides:

- **E**: field by field. Quantities are converted to canonical units on both sides (unit spellings such as
  `mg/dl`, `meq/L`, `inches`, `/µL` are normalised), relative tolerance 1 %. A value copied with the unit written in
  the note is accepted even if the annotation used another unit. Correct if every field is correct.
- **U**: one of the patient's values (creatinine, sodium, glucose, calcium, BUN, albumin, lipids, weight, height) is
  given in another plausible unit, drawn reproducibly from `conversion.UNIT_TABLE` (e.g. creatinine in µmol/L), and
  must be converted to the unit of the registry's formula (mg/dL). The prompt names the substance, never its molar
  mass or valence. Relative tolerance 1 %; copying the number back is `unconverted`, applying the factor the wrong
  way is `inverse_factor`. Built only for examples with such a value (24 of the 33 equation-based calculators).
- **K**: the formula is evaluated at the patient's point and at up to 50 other points (real patients of the same
  calculator from `k_pool`, or perturbations of the patient), and compared with the registry (1 %). Correct only if
  right at every point; `min_pass_rate=0.95` accepts a formula right at 95 % of the points (never one that is wrong
  at the patient's point). In the default `general` mode the prompt depends on the patient only through categorical
  fields (sex, drugs…), so many examples share a prompt: `summary` counts each distinct prompt once. In `patient`
  mode the model sees the values and writes the formula of the patient's branch.
- **S**: structural identity with the expected expression (reordering accepted), otherwise numerical equivalence
  after mapping the numbers back to variables. A partly computed answer is *not* a substitution, even if its value
  is right (`premature_computation`). Variant **S+U**: `substitution.build(ex, value_units={"scr": "µmol/L"})` gives
  some values in another unit; the model converts them while substituting (numbers matched within 1 %).
- **A**: relative error ≤ 1 % (`correct`) and ≤ 0.1 % (`correct_strict`).
- **E2E**: a number must fall within the benchmark's interval (the exact value for rule-based scores); a date or a
  gestational age (weeks and days) must be exactly right. Dates are read in the usual formats (`06/16/2012`,
  `2012-06-16`, `June 16, 2012`).

Every probe reads the **last** JSON object of the answer, so the model may reason before it.

## 6. Generation artifacts

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

## 7. Using your own model

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

## 8. Comparing models and conditions

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

## 9. Customising prompts and scoring

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
| U | `field`, `source_unit`, `template`, `max_new_tokens`, `system_prompt`, `digits`, `seed` | `rel_tol` |
| K | `mode` (`general`/`patient`), `template`, `max_new_tokens`, `system_prompt`, `n_points`, `symbol_docs`, `digits` | `rel_tol`, `abs_tol`, `n_points`, `case_semantics`, `perturbation_factor`, `plausible_ranges`, `min_pass_rate`, `details` |
| S | `template`, `max_new_tokens`, `system_prompt`, `digits`, `symbol_docs`, `value_units` | `equiv_rel_tol`, `value_rel_tol` |
| A | `template`, `max_new_tokens`, `system_prompt`, `digits` | `rel_tol`, `strict_rel_tol` |
| E2E | `template`, `max_new_tokens`, `system_prompt`, `provide` | `rel_tol` (instead of the benchmark interval) |

All builders also take `label`. The placeholders of each template are listed next to its `DEFAULT_TEMPLATE`.
`template` is either a text or the name of one of the module's wordings (`"v1"`, `"v2"`, `"v3"`, see
[section 10](#10-prompt-design-and-robustness)): `ProbeSuite({"A": {}, "A@v2": {"task": "A", "template": "v2"}})`.

## 10. Prompt design and robustness

A step probe is only valid if its prompt neither gives away the competence it measures (too much guidance) nor
makes the model guess conventions or formats that have nothing to do with it (too little). The prompts of the kit
follow these rules; keep them if you write your own.

**Guide the interface, never the competence.** Each prompt gives what is needed to answer and to be scored
automatically, and nothing of the competence measured:

| probe | given (interface) | never given (the competence) |
|---|---|---|
| E | the list of fields, the JSON format, "the unit as written" | the values, unit conversions |
| U | the value, its unit, the substance, the target unit | the molar mass, the valence, the factor |
| K | the variables and their units, the conventions stated in the benchmark question | the formula, the thresholds of the branches, the coefficients |
| S | the exact formula of the patient's branch, the values | the result, intermediate computations |
| A | the fully substituted expression | the result; no tool |
| E2E | the note and the question, as in the benchmark | nothing more |

K gives the list of variables, which automatic scoring needs; it helps a little (the model knows which quantities
enter the formula) and should be stated as a limitation.

**Oracle inputs.** Each step receives the reference output of the steps before it (S gets the reference formula, A
the reference expression), so an error upstream never propagates: each competence is measured on its own.

**Same protocol for every probe and every model.** Free reasoning, then a final JSON object; greedy decoding, the
model's chat template, fixed token budgets. Format failures are counted apart (`well_formed` vs `competence`), so
they are not mistaken for reasoning errors.

**Fix the prompts before looking at the results**, and report them verbatim. Each item records the name of its
template (`template`) and a hash of its text (`template_hash`), so a paper can cite exactly what was asked. To
iterate on prompts, use a dev split (`ds.split_off("dev", fraction=0.1, exclude_leaks=True)`), never the test set.

**Measure the sensitivity to the wording.** Every probe has three wordings (`TEMPLATES` in each probe module, and
`knowledge.PATIENT_TEMPLATES`): "v1" (the default) and two paraphrases with the same information, conventions and
answer format. A test checks that the three use the same placeholders and that reference answers are scored correct
with each of them, on the whole benchmark.

```python
report = mk.evaluate_model(model, prompt_variants=3)      # 3 wordings of every prompt (3x the generations)
report.prompt_sensitivity                                  # accuracy per step and wording, mean, sd, range
```

The views (`general`, `steps`...) use "v1"; `prompt_sensitivity` compares the wordings. Report the range next to
each score: a difference between two models that is smaller than the range is not robust. To compare models,
check that their ranking is the same with each wording.

**Treat the amount of guidance as a variable** rather than an arbitrary choice: K in `patient` mode (the model sees
the values and writes the formula of the patient's branch) versus `general` mode (no values, every branch) is such a
contrast, and the difference is a result in itself.

**Validate the probes.**

- Positive control: `mk.reference_answer(item)` must be scored correct for every item (tested on the 1,100 test
  examples, for every wording).
- Negative controls: known wrong answers must be rejected (tested per error type in `tests/`).
- Human audit: read a sample of failures per probe (`report.scores` has the text and the verdict) to check that each
  failure is real, not a parsing problem.
- Consistency of the decomposition: `report.consistency` gives the end-to-end accuracy when every step succeeds and
  when a step fails. If the first is low, the steps do not represent the task faithfully; if the second is high,
  the model reaches the answer by another route (or by chance).

## 11. Further analyses

**A smaller token budget, without generating again.** With greedy decoding, the first tokens of an answer do not
depend on the budget, so a run with a large budget also tells what a smaller one would give:

```python
records = mk.read_records("medcalc_eval/my-model/generations.jsonl")
cut = mk.evaluate.truncate_records(records, items, {"E2E": 512, "K": 256}, tokenizer)   # any encode/decode
mk.score_records(cut, items)            # cut answers are classified as truncated
```

**Interventions on the end-to-end task.** Giving the model what one step would have produced shows how much that
step costs end to end:

```python
suite = mk.ProbeSuite({"E2E": {}, "E2E+V": {"task": "E2E", "provide": ("values",)},
                       "E2E+F": {"task": "E2E", "provide": ("formula",)},
                       "E2E+VF": {"task": "E2E", "provide": ("values", "formula")}})
report = mk.evaluate_model(model, items=suite.build(ds.filter(split="test").equation_only()), dataset=ds)
report.by_label                         # accuracy with no help, with the values, the formula, or both
```

`provide` adds the correct values (in the formula's units) and/or the formula of the patient's branch, from the
registry, after the question; the scoring does not change.

**LLM evaluation, next to the automatic one.** An LLM judge can grade every answer too, for every probe: it reads
the task as the model received it, the reference answer from the registry and the probe's grading rule
(`judge.CRITERIA`, the same rules as the automatic scoring; for E2E, only the final answer against the ground truth),
and answers correct or incorrect with a short reason.

```python
from medcalc_kit.generation.hf import HFBackend

judge = HFBackend("Qwen/Qwen3-8B", deterministic=True, chat_template_kwargs={"enable_thinking": False})
report = mk.evaluate_model(model, judge=judge)
report.llm_vs_auto              # per probe: automatic vs LLM accuracy, agreement, kappa, false acceptances/rejections
report.scores.judge_correct     # the judge's verdict on each answer
```

The automatic evaluation stays the reference, so the comparison measures the judge's reliability without human
labels. The judge is blind (nothing about the model evaluated is in its prompt) and deterministic: greedy decoding,
one prompt at a time, deterministic torch kernels (`deterministic=True`), and its model revision and template hash are
recorded with every verdict. `mk.judge.annotate(items, records, judge)` and `mk.judge.compare(llm, scores)` do the
same on answers collected elsewhere.

**Models modified in memory.** `HFBackend.from_model(model, tokenizer)` wraps a model already loaded, for example
pruned or quantized in the same session, without loading it again.

## 12. Good practices

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

## 13. Troubleshooting

| symptom | cause and fix |
|---|---|
| `KeyError: "calculator 6 (...) needs the entity 'height'"` | the entities miss an input; [calculators.md](calculators.md) lists the expected names |
| `KeyError: "unknown calculator '1'"` | the registry (`derive`, step probes) covers the 33 equation-based calculators; E2E covers all 55 |
| every answer is `truncated` | `max_new_tokens` too small for a reasoning model: raise it in the suite options |
| every answer is `format_invalid` | the model does not end with the JSON object; look at `score_records(..., details=True).text` and adapt the template |
| K is `wrong_elsewhere` | right formula for this patient but wrong branch or constant elsewhere; `mk.score(item, text, details=True)["points"]` shows each test point |
| `error_type` is `NaN` in a DataFrame | the answer is correct (`None` becomes `NaN` in pandas) |
| `run_items` returns 0 | every item is already in the output file; delete it or use another path to regenerate |
| the dataset does not load | `mk.load` needs network access the first time, then reads the Hugging Face cache |
