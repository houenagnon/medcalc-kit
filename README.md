# medcalc-kit

Data, executable calculators and **diagnostic probes** for [MedCalc-Bench](https://huggingface.co/datasets/nsk7153/MedCalc-Bench-Verified).

MedCalc-Bench asks a model to read a patient note and compute a clinical score (creatinine clearance, anion gap,
QTc, MELD Na…). A wrong final answer can come from several distinct failures. `medcalc-kit` splits the task into
independent probes so that each competence can be measured on its own:

| probe | name          | the model is given…                         | it must…                                  |
|-------|---------------|---------------------------------------------|-------------------------------------------|
| `E`   | extraction    | the note and the list of fields             | report each value with its unit as written |
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

From source: `pip install -e ".[dev]"` then `pytest`.

## Documentation

- **[Tutorial notebook](https://github.com/houenagnon/medcalc-kit/blob/main/examples/tutorial.ipynb)**: the whole library on the benchmark, with a real model
  (Qwen2.5-3B-Instruct), executed.
- **[User guide](https://github.com/houenagnon/medcalc-kit/blob/main/docs/guide.md)**: concepts, the objects you handle, the probes and their error types, using your own
  model, comparing conditions, customising, good practices, troubleshooting.
- **[API reference](https://github.com/houenagnon/medcalc-kit/blob/main/docs/api.md)**: every public function, with runnable examples.
- **[Calculators](https://github.com/houenagnon/medcalc-kit/blob/main/docs/calculators.md)**: the 33 calculators, the inputs each one expects, a worked example each.

## Quick start

```python
import medcalc_kit as mk

ds = mk.load(equation_only=True)          # MedCalc-Bench-Verified at a pinned revision (or mk.data.demo() offline)
items = mk.ProbeSuite(schema=ds).build(ds.filter(split="test"))   # one row per (example, probe)

mk.run_items(items, "outputs.jsonl", model, batch_size=16)        # any model, resumable
scores = mk.score_records("outputs.jsonl", items, condition={"model": "my-model"})
mk.summary(scores)                        # per probe: well-formed answers, competence, overall accuracy
```

`model` is a Hugging Face model, any object with `generate_batch` or `generate`, or a plain function:

```python
from medcalc_kit.generation.hf import HFBackend          # needs medcalc-kit[hf]
model = HFBackend("Qwen/Qwen2.5-7B-Instruct", device="cuda:0")

def model(messages, max_new_tokens):                     # e.g. an API client
    return client.chat(messages, max_tokens=max_new_tokens)
```

Answers collected another way only need an `item_id` and a `text` column:
`mk.score_records(pd.DataFrame({"item_id": ..., "text": ...}), items)`.

## Look inside

```python
ex = ds.filter(calculator=2, split="test")[0]   # an Example: note, question, entities, ground truth…
mk.derive(ex.calculator_id, ex.entities).to_frame()   # the reference computation, step by step

item = mk.probes.knowledge.build(ex)            # one probe for one example
print(mk.probes.prompt(item))                   # what the model is asked
mk.reference_answer(item)                       # an answer the scorer accepts (the expected format)
mk.score(item, model_text)                      # {'format_valid', 'correct', 'error_type', ...}
```

Each answer is first classified as `empty`, `truncated`, `degenerate` (looping), `format_invalid` or
`well_formed`; only well-formed answers can be correct. `competence` is the accuracy among well-formed answers, so
format failures and reasoning failures are reported separately. How each probe scores, its error types and all
options are in the [user guide](https://github.com/houenagnon/medcalc-kit/blob/main/docs/guide.md#4-the-five-probes).

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
| `medcalc_kit.data` | `load`, `demo`, `MedCalcDataset`, `Example`; leakage and quality control (`usable_train_pool`, `flag_train_rows`) |
| `medcalc_kit.calculators` | `derive` (`.to_frame()`), `table`, `get`, `verify_registry`; `python -m medcalc_kit.calculators.verify` |
| `medcalc_kit.probes` | `extraction`, `knowledge`, `substitution`, `arithmetic`, `end_to_end` (each: `build`, `score`, `reference_answer`), `ProbeSuite`, `score`, `prompt`, `read_items` / `write_items` |
| `medcalc_kit.generation` | `run_items`, `read_records`, `classify_generation`; `generation.hf.HFBackend` |
| `medcalc_kit.evaluate` | `score_records`, `summary`, `to_units` |
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
