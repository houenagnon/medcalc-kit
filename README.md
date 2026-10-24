# medcalc-kit

An evaluator for [MedCalc-Bench](https://huggingface.co/datasets/nsk7153/MedCalc-Bench-Verified), overall and step
by step.

MedCalc-Bench asks a model to read a patient note and compute a clinical score (creatinine clearance, anion gap,
QTc, CHA2DS2-VASc, due date…). `medcalc-kit` evaluates a model at two levels:

- **general**: the original task on the whole benchmark (55 calculators, 1,100 test examples);
- **step by step**: a wrong final answer can come from several distinct failures, so on the 33 equation-based
  calculators the task is split into independent probes, each measuring one competence:

| probe | name          | the model is given…                         | it must…                                  |
|-------|---------------|---------------------------------------------|-------------------------------------------|
| `E`   | extraction    | the note and the list of fields             | report each value with its unit as written |
| `U`   | conversion    | one value in another unit, the formula's unit | convert it                              |
| `K`   | knowledge     | the question and the variables (no values)  | write the general formula, one case per branch |
| `S`   | substitution  | the formula and the values                  | plug the values in, without computing     |
| `A`   | arithmetic    | the fully substituted expression            | compute it                                |
| `E2E` | end to end    | the note and the question                   | answer the original benchmark question    |

All references come from an **executable registry of the 33 equation-based calculators**, which reproduces the
660 answers of the MedCalc-Bench-Verified test set. Scoring is deterministic and never executes model output
(expressions go through a small whitelisted parser, not `eval`). Results are pandas DataFrames.

## Install

```bash
pip install medcalc-kit            # data, calculators, probes, scoring (no torch)
pip install "medcalc-kit[hf]"      # + Hugging Face transformers backend for generation
```

From source: `pip install -e ".[dev]"` then `pytest`. To run the notebooks: `conda env create -f environment.yml`
(see [examples/README.md](https://github.com/houenagnon/medcalc-kit/blob/main/examples/README.md)).

## Documentation

- **[Evaluation notebook](https://github.com/houenagnon/medcalc-kit/blob/main/examples/evaluate_model.ipynb)**: `evaluate_model` on MedCalc-Bench with
  Qwen2.5-3B-Instruct, general and step-by-step results, executed.
- **[Tutorial notebook](https://github.com/houenagnon/medcalc-kit/blob/main/examples/tutorial.ipynb)**: the whole library on the benchmark, with a real model
  (Qwen2.5-3B-Instruct), executed.
- **[User guide](https://github.com/houenagnon/medcalc-kit/blob/main/docs/guide.md)**: concepts, the objects you handle, the probes and their error types, using your own
  model, comparing conditions, customising, good practices, troubleshooting.
- **[API reference](https://github.com/houenagnon/medcalc-kit/blob/main/docs/api.md)**: every public function, with runnable examples.
- **[Calculators](https://github.com/houenagnon/medcalc-kit/blob/main/docs/calculators.md)**: the 33 calculators, the inputs each one expects, a worked example each.

## Quick start

```python
import medcalc_kit as mk
from medcalc_kit.generation.hf import HFBackend          # needs medcalc-kit[hf]

model = HFBackend("Qwen/Qwen2.5-7B-Instruct", device="cuda:0")
report = mk.evaluate_model(model, batch_size=16)          # downloads the benchmark, generates, scores (resumable)
report                                                    # general score + score of each step
```

```text
MedCalc-Bench evaluation of Qwen/Qwen2.5-7B-Instruct
  general (end to end): …% of 1100 examples (55 calculators)
  step by step (660 examples of equation-based calculators):
    E    extraction         …%
    K    formula knowledge  …%
    S    substitution       …%
    A    arithmetic         …%
    E2E  end to end         …%
```

`report.general` (per category), `report.steps`, `report.by_calculator` (where the chain breaks),
`report.examples` (first failing step of each example), `report.consistency` and `report.scores` (every answer) are
DataFrames, also saved as CSV in `medcalc_eval/<model>/`. With `prompt_variants=3`, every prompt is also asked in two
paraphrases and `report.prompt_sensitivity` shows how much each score depends on the wording; the prompts are designed
to guide the answer format, never the competence measured
([guide]({B}/docs/guide.md#10-prompt-design-and-robustness)). `per_calculator=5` evaluates a quick subset first. See the
[evaluation notebook](https://github.com/houenagnon/medcalc-kit/blob/main/examples/evaluate_model.ipynb) for a full run.

`model` is a Hugging Face model, any object with `generate_batch` or `generate`, or a plain function:

```python
from medcalc_kit.generation.hf import HFBackend          # needs medcalc-kit[hf]
model = HFBackend("Qwen/Qwen2.5-7B-Instruct", device="cuda:0")

def model(messages, max_new_tokens):                     # e.g. an API client
    return client.chat(messages, max_tokens=max_new_tokens)
```

Answers collected another way only need an `item_id` and a `text` column:
`mk.score_records(pd.DataFrame({"item_id": ..., "text": ...}), items)`.

## The benchmark and your own splits

```python
ds = mk.load()                                       # MedCalcDataset(11638 examples, 55 calculators; train: 10538, test: 1100)
ds.filter(split="test", category=["lab test", "physical"], where=lambda df: df["Note Type"] == "Extracted")
ds = ds.split_off("dev", fraction=0.1, exclude_leaks=True)   # dev from train, stratified, never leaking into test
folds = ds.folds(5)                                  # k-fold over train
ds = ds.assign_split(my_ids, "hard")                 # any split from example ids
ds.save_splits("splits.csv")                         # ...and mk.load().with_splits("splits.csv") restores it
ds = ds + mk.data.from_records(my_rows)              # add your own examples
report = mk.evaluate_model(model, dataset=ds, split="dev")
```

See the [user guide](https://github.com/houenagnon/medcalc-kit/blob/main/docs/guide.md#3-working-with-the-benchmark-and-splits).

## Building blocks

`evaluate_model` chains `load`, `ProbeSuite.build`, `run_items`, `score_records` and `summary`, which can be used on
their own:

```python
ds = mk.load()                                                     # 55 calculators (equation_only=True: 33)
items = mk.ProbeSuite(schema=ds).build(ds.filter(split="test"))   # one row per (example, probe)
mk.run_items(items, "outputs.jsonl", model, batch_size=16)        # any model, resumable
scores = mk.score_records("outputs.jsonl", items, condition={"model": "my-model"})
mk.summary(scores)                        # per probe: well-formed answers, competence, overall accuracy
```

## Look inside

```python
ex = ds.filter(calculator=2, split="test")[0]   # an Example: note, question, entities, ground truth…
mk.derive(ex.calculator_id, ex.entities).to_frame()   # the reference computation, step by step

item = mk.probes.knowledge.build(ex)            # one probe for one example
print(mk.probes.prompt(item))                   # what the model is asked
mk.reference_answer(item)                       # an answer the scorer accepts (the expected format)
mk.score(item, model_text)                      # {'format_valid', 'correct', 'error_type', ...}
```

## Further analyses

- `mk.evaluate.truncate_records(records, items, {"E2E": 512}, tokenizer)`: what a smaller token budget would give,
  without generating again.
- `end_to_end.build(ex, provide=("values", "formula"))`: interventions that give the model the correct values and/or
  formula (labels `E2E+V`, `E2E+F`, `E2E+VF`), to measure what each step costs end to end.
- `mk.evaluate_model(model, judge=judge_model)`: an LLM evaluation next to the automatic one. A blind, deterministic
  LLM judge grades every answer against the registry's reference (for E2E, the final answer against the ground
  truth); `report.llm_vs_auto` gives, per probe, both accuracies, their agreement and the judge's errors.
- `HFBackend.from_model(model, tokenizer)`: evaluate a model modified in memory (pruned, quantized) without reloading.

Each answer is first classified as `empty`, `truncated`, `degenerate` (looping), `format_invalid` or
`well_formed`; only well-formed answers can be correct. `competence` is the accuracy among well-formed answers, so
format failures and reasoning failures are reported separately. How each probe scores, its error types and all
options are in the [user guide](https://github.com/houenagnon/medcalc-kit/blob/main/docs/guide.md#5-the-probes).

## Everything is a parameter

Nothing is fixed globally: prompt templates, token budgets, system prompt, number formatting, tolerances, K mode
(`general` / `patient`), test points, artifact thresholds are arguments with documented defaults.

```python
suite = mk.ProbeSuite({"E": {}, "K": {"mode": "patient", "max_new_tokens": 1536},
                       "K_general": {"task": "K"}, "A": {"template": "Compute {expression}. Reply {\"result\": <x>}."}},
                      schema=ds, k_pool=mk.data.usable_train_pool(ds))
mk.score_records(records, items, scoring={"K_general": {"case_semantics": "first_match"}, "A": {"rel_tol": 0.001}})
```

## Modules

| module | content |
|---|---|
| `medcalc_kit.benchmark` | `evaluate_model`, `EvaluationReport` |
| `medcalc_kit.data` | `load`, `demo`, `MedCalcDataset`, `Example`; leakage and quality control (`usable_train_pool`, `flag_train_rows`) |
| `medcalc_kit.calculators` | `derive` (`.to_frame()`), `table`, `get`, `verify_registry`; `python -m medcalc_kit.calculators.verify` |
| `medcalc_kit.probes` | `extraction`, `conversion`, `knowledge`, `substitution`, `arithmetic`, `end_to_end` (each: `build`, `score`, `reference_answer`), `ProbeSuite`, `score`, `prompt`, `read_items` / `write_items` |
| `medcalc_kit.generation` | `run_items`, `read_records`, `classify_generation`; `generation.hf.HFBackend` |
| `medcalc_kit.evaluate` | `score_records`, `truncate_records`, `summary`, `to_units` |
| `medcalc_kit.judge` | `annotate`, `compare`, `agreement`, `build`, `parse` (LLM evaluation, next to the automatic one) |
| `medcalc_kit.expr`, `units`, `parsing` | safe expression parser/evaluator, unit conversions, JSON / number extraction |

## Conventions and known deviations

The registry follows the conventions stated in the benchmark questions (e.g. Cockcroft-Gault with a BMI-dependent
dosing weight). Where the benchmark's reference implementation is clinically wrong, the correct rule is implemented
and listed in `calculators.KNOWN_REFERENCE_DEVIATIONS` (HOMA-IR insulin conversion; MELD Na dialysis rule).

## Data

`medcalc-kit` does not ship any benchmark data: it downloads MedCalc-Bench-Verified from the Hugging Face Hub.
`mk.data.demo()` provides four hand-written examples to try the library offline. Please cite the original
MedCalc-Bench work and respect the dataset's license when you use it.

## License

MIT (code only).
