# API reference

medcalc-kit 0.4.0. Generated from the docstrings by `docs/build_docs.py`; every example is run by the test suite (`tests/test_docs.py`). Examples marked as needing the dataset download it from the Hugging Face Hub; the others use `mk.data.demo()`, four hand-written examples.

See also the [user guide](guide.md) and the [calculator list](calculators.md).

- [`medcalc_kit` shortcuts](#medcalc_kit-shortcuts)
- [`medcalc_kit.benchmark`](#medcalc_kitbenchmark): [`evaluate_model`](#benchmarkevaluate_model), [`EvaluationReport`](#benchmarkevaluationreport)
- [`medcalc_kit.data`](#medcalc_kitdata): [`load`](#dataload), [`demo`](#datademo), [`MedCalcDataset`](#datamedcalcdataset), [`concat`](#dataconcat), [`from_records`](#datafrom_records), [`Example`](#dataexample), [`as_example`](#dataas_example), [`load_dataframe`](#dataload_dataframe), [`equation_subset`](#dataequation_subset), [`parse_entities`](#dataparse_entities), [`dataset_revision`](#datadataset_revision), [`DEFAULT_REVISION`](#datadefault_revision), [`EQUATION_CATEGORIES`](#dataequation_categories)
- [`medcalc_kit.data.quality`](#medcalc_kitdataquality): [`usable_train_pool`](#dataqualityusable_train_pool), [`flag_train_rows`](#dataqualityflag_train_rows), [`leak_flags`](#dataqualityleak_flags), [`leaking_rows`](#dataqualityleaking_rows), [`registry_agrees`](#dataqualityregistry_agrees), [`implausible_inputs`](#dataqualityimplausible_inputs), [`note_hash`](#dataqualitynote_hash), [`PLAUSIBLE_RANGES`](#dataqualityplausible_ranges)
- [`medcalc_kit.calculators`](#medcalc_kitcalculators): [`derive`](#calculatorsderive), [`table`](#calculatorstable), [`get`](#calculatorsget), [`list_calculators`](#calculatorslist_calculators), [`verify_registry`](#calculatorsverify_registry), [`Derivation`](#calculatorsderivation), [`Step`](#calculatorsstep), [`Calculator`](#calculatorscalculator), [`KNOWN_REFERENCE_DEVIATIONS`](#calculatorsknown_reference_deviations)
- [`medcalc_kit.calculators.registry`](#medcalc_kitcalculatorsregistry): [`calculator`](#calculatorsregistrycalculator), [`new_derivation`](#calculatorsregistrynew_derivation), [`is_male`](#calculatorsregistryis_male)
- [`medcalc_kit.calculators.verify`](#medcalc_kitcalculatorsverify): [`verify`](#calculatorsverifyverify), [`check_row`](#calculatorsverifycheck_row), [`main`](#calculatorsverifymain)
- [`medcalc_kit.probes`](#medcalc_kitprobes): [`ProbeSuite`](#probesprobesuite), [`score`](#probesscore), [`reference_answer`](#probesreference_answer), [`prompt`](#probesprompt), [`get`](#probesget), [`PROBES`](#probesprobes), [`ALL_PROBES`](#probesall_probes), [`STEP_PROBES`](#probesstep_probes), [`Probe`](#probesprobe), [`read_items`](#probesread_items), [`write_items`](#probeswrite_items), [`items_frame`](#probesitems_frame), [`as_items`](#probesas_items), [`as_item`](#probesas_item)
- [`medcalc_kit.probes.extraction`](#medcalc_kitprobesextraction): [`build`](#probesextractionbuild), [`score`](#probesextractionscore), [`score_answer`](#probesextractionscore_answer), [`score_field`](#probesextractionscore_field), [`reference_answer`](#probesextractionreference_answer), [`calculator_fields`](#probesextractioncalculator_fields), [`field_kind`](#probesextractionfield_kind), [`default_field_hint`](#probesextractiondefault_field_hint), [`TEMPLATES`](#probesextractiontemplates), [`DEFAULT_TEMPLATE`](#probesextractiondefault_template), [`KIND_HINT`](#probesextractionkind_hint)
- [`medcalc_kit.probes.knowledge`](#medcalc_kitprobesknowledge): [`build`](#probesknowledgebuild), [`score`](#probesknowledgescore), [`score_answer`](#probesknowledgescore_answer), [`reference_answer`](#probesknowledgereference_answer), [`test_points`](#probesknowledgetest_points), [`eval_cases`](#probesknowledgeeval_cases), [`perturb_entities`](#probesknowledgeperturb_entities), [`with_categorical`](#probesknowledgewith_categorical), [`TEMPLATES`](#probesknowledgetemplates), [`PATIENT_TEMPLATES`](#probesknowledgepatient_templates), [`DEFAULT_TEMPLATE`](#probesknowledgedefault_template), [`DEFAULT_PATIENT_TEMPLATE`](#probesknowledgedefault_patient_template)
- [`medcalc_kit.probes.substitution`](#medcalc_kitprobessubstitution): [`build`](#probessubstitutionbuild), [`score`](#probessubstitutionscore), [`score_answer`](#probessubstitutionscore_answer), [`reference_answer`](#probessubstitutionreference_answer), [`TEMPLATES`](#probessubstitutiontemplates), [`DEFAULT_TEMPLATE`](#probessubstitutiondefault_template)
- [`medcalc_kit.probes.arithmetic`](#medcalc_kitprobesarithmetic): [`build`](#probesarithmeticbuild), [`score`](#probesarithmeticscore), [`score_answer`](#probesarithmeticscore_answer), [`reference_answer`](#probesarithmeticreference_answer), [`TEMPLATES`](#probesarithmetictemplates), [`DEFAULT_TEMPLATE`](#probesarithmeticdefault_template)
- [`medcalc_kit.probes.end_to_end`](#medcalc_kitprobesend_to_end): [`build`](#probesend_to_endbuild), [`score`](#probesend_to_endscore), [`score_answer`](#probesend_to_endscore_answer), [`reference_answer`](#probesend_to_endreference_answer), [`answer_type`](#probesend_to_endanswer_type), [`parse_date`](#probesend_to_endparse_date), [`parse_weeks_days`](#probesend_to_endparse_weeks_days), [`TEMPLATES`](#probesend_to_endtemplates), [`DEFAULT_TEMPLATE`](#probesend_to_enddefault_template), [`ANSWER_FORMATS`](#probesend_to_endanswer_formats)
- [`medcalc_kit.probes.common`](#medcalc_kitprobescommon): [`render`](#probescommonrender), [`resolve_template`](#probescommonresolve_template), [`template_hash`](#probescommontemplate_hash), [`fmt`](#probescommonfmt), [`presented`](#probescommonpresented), [`symbol_doc`](#probescommonsymbol_doc), [`SYMBOL_DOCS`](#probescommonsymbol_docs), [`task_question`](#probescommontask_question), [`categorical_context`](#probescommoncategorical_context), [`mme_drugs`](#probescommonmme_drugs), [`inline`](#probescommoninline), [`branch_formula`](#probescommonbranch_formula), [`make_item`](#probescommonmake_item), [`numeric_answer`](#probescommonnumeric_answer), [`rel_close`](#probescommonrel_close), [`DEFAULT_SYSTEM_PROMPT`](#probescommondefault_system_prompt), [`DEFAULT_DIGITS`](#probescommondefault_digits)
- [`medcalc_kit.generation`](#medcalc_kitgeneration): [`run_items`](#generationrun_items), [`read_records`](#generationread_records), [`done_item_ids`](#generationdone_item_ids), [`prompt_key`](#generationprompt_key), [`model_name`](#generationmodel_name), [`classify_generation`](#generationclassify_generation), [`is_degenerate`](#generationis_degenerate), [`CATEGORIES`](#generationcategories)
- [`medcalc_kit.generation.artifacts`](#medcalc_kitgenerationartifacts): [`repeated_ngram_share`](#generationartifactsrepeated_ngram_share), [`max_line_repeats`](#generationartifactsmax_line_repeats)
- [`medcalc_kit.generation.hf`](#medcalc_kitgenerationhf): [`HFBackend`](#generationhfhfbackend)
- [`medcalc_kit.evaluate`](#medcalc_kitevaluate): [`score_records`](#evaluatescore_records), [`summary`](#evaluatesummary), [`to_units`](#evaluateto_units), [`read_jsonl`](#evaluateread_jsonl)
- [`medcalc_kit.expr`](#medcalc_kitexpr): [`evaluate`](#exprevaluate), [`parse`](#exprparse), [`variables`](#exprvariables), [`substitute`](#exprsubstitute), [`replace_vars`](#exprreplace_vars), [`to_str`](#exprto_str), [`canonical`](#exprcanonical), [`evaluate_condition`](#exprevaluate_condition), [`literals`](#exprliterals), [`map_literals`](#exprmap_literals), [`ExprError`](#exprexprerror), [`FUNCTIONS`](#exprfunctions)
- [`medcalc_kit.units`](#medcalc_kitunits): [`concentration`](#unitsconcentration), [`clean_unit`](#unitsclean_unit), [`weight_kg`](#unitsweight_kg), [`height_cm`](#unitsheight_cm), [`age_years`](#unitsage_years), [`platelets_1e9_per_L`](#unitsplatelets_1e9_per_l), [`insulin_uIU_per_mL`](#unitsinsulin_uiu_per_ml), [`UnitError`](#unitsuniterror), [`MOLAR_MASS`](#unitsmolar_mass)
- [`medcalc_kit.parsing`](#medcalc_kitparsing): [`extract_json`](#parsingextract_json), [`to_number`](#parsingto_number)

---

## `medcalc_kit` shortcuts

The shortcuts below cover a whole evaluation; every module (`data`, `calculators`, `probes`, `generation`,
`evaluate`, `expr`, `units`, `parsing`) has more.

```python
>>> import medcalc_kit as mk
>>> ds = mk.load(equation_only=True)                # MedCalc-Bench-Verified
>>> ds = mk.data.demo()                             # or 4 offline examples
>>> round(mk.derive("6", ds[1].entities).answer, 2) # reference computation
22.86
>>> items = mk.ProbeSuite().build(ds)               # every probe for every example: one row per item
>>> items.groupby("probe", sort=False).size().to_dict()
{'E': 4, 'K': 4, 'S': 4, 'A': 4, 'E2E': 4}
>>> mk.score(items.iloc[0], '{"sex": "Female"}')["error_type"]   # score one answer
'missing'
```

| shortcut | documented as |
|---|---|
| `mk.evaluate_model` | [`benchmark.evaluate_model`](#benchmarkevaluate_model) |
| `mk.EvaluationReport` | [`benchmark.EvaluationReport`](#benchmarkevaluationreport) |
| `mk.load` | [`data.load`](#dataload) |
| `mk.derive` | [`calculators.derive`](#calculatorsderive) |
| `mk.ProbeSuite` | [`probes.ProbeSuite`](#probesprobesuite) |
| `mk.score` | [`probes.score`](#probesscore) |
| `mk.reference_answer` | [`probes.reference_answer`](#probesreference_answer) |
| `mk.run_items` | [`generation.run_items`](#generationrun_items) |
| `mk.read_records` | [`generation.read_records`](#generationread_records) |
| `mk.score_records` | [`evaluate.score_records`](#evaluatescore_records) |
| `mk.summary` | [`evaluate.summary`](#evaluatesummary) |

---

## `medcalc_kit.benchmark`

Evaluate a model on MedCalc-Bench in one call: the general score and the step-by-step diagnosis.

- **General**: the original task (E2E) on every example of the benchmark (55 calculators, 1,100 test examples),
  by category.
- **Step by step**: on the 33 equation-based calculators, each step of the calculation measured on its own:
  E (finding the values in the note), K (knowing the formula), S (substituting the values), A (computing), next
  to E2E on the same examples, and per example the first step that fails.
- **Robustness**: with `prompt_variants=3`, every prompt is also asked in two paraphrases (same information and
  answer format, different wording), and `prompt_sensitivity` shows how much each score depends on the wording.

```python
>>> report = mk.evaluate_model(model)
>>> report
>>> report.general, report.steps, report.by_calculator
```

Generations are saved as they come (`<output_dir>/generations.jsonl`): run the same call again after an
interruption to resume, or with `model=None` to rescore what was generated.

### `benchmark.evaluate_model`

```python
def evaluate_model(model: Any, output_dir: str | Path | None = None, *, dataset: MedCalcDataset | None = None, split: str | Iterable[str] = 'test', per_calculator: int | None = None, seed: int = 0, steps: Iterable[str] = ('E', 'K', 'S', 'A'), k_mode: str = 'patient', k_pool: Any = 'auto', probe_options: Mapping[str, Mapping[str, Any]] | None = None, prompt_variants: int | Iterable[str] = 1, batch_size: int = 8, model_id: str | None = None, scoring: dict[str, dict[str, Any]] | None = None) -> EvaluationReport
```

Evaluate a model on MedCalc-Bench: the general score (end to end, all calculators) and the score of each step
(E, K, S, A on the equation-based calculators). Returns an EvaluationReport.

model:          what `run_items` accepts: an object with `generate_batch` or `generate` (e.g. HFBackend), or a
                function `generate(messages, max_new_tokens)`. None: only score generations already saved.
output_dir:     where items, generations and the report go (default: medcalc_eval/<model id>). Generations are
                appended as they come: the same call resumes an interrupted run.
dataset:        default: MedCalc-Bench-Verified at the pinned revision (`mk.load()`), all 55 calculators.
split:          the split(s) evaluated ("test", or your own, e.g. "dev" made with ds.split_off); per_calculator:
                evaluate only that many examples per calculator (random, `seed`), to try a model quickly.
steps:          the step probes to run (default all four; () for the general score only).
k_mode:         "patient" (the model sees the values, writes the formula of its branch) or "general".
k_pool:         patients used as K test points; "auto": the "train" examples that do not leak into the
                evaluated split(s) (`usable_train_pool`), if any; None: perturbations.
probe_options:  build options per probe, e.g. {"E2E": {"max_new_tokens": 4096}} (see ProbeSuite).
prompt_variants: how many wordings of each prompt to use (1 to 3: "v1" is the default, "v2" and "v3" are
                paraphrases with the same information and format), or their names. The views use the first one;
                `report.prompt_sensitivity` compares them. Each variant multiplies the number of generations.
batch_size, model_id: passed to run_items; scoring: passed to score_records.

```python
>>> def always_12(messages, max_new_tokens):
...     return '{"answer": 12, "result": 12}'
>>> import tempfile
>>> report = evaluate_model(always_12, tempfile.mkdtemp(), dataset=mk.data.demo(), split="demo", steps=())
>>> float(report.general.loc["all", "accuracy"])           # right for the anion gap only
0.25
```

### `benchmark.EvaluationReport`

```python
class EvaluationReport(model: str, items: pd.DataFrame, scores: pd.DataFrame, output_dir: Path | None = None) -> None
```

Result of `evaluate_model`. Every view is a DataFrame; `scores` has one row per answer (score_records columns,
with the answer `text`, the `verdict`, `calculator_name` and `calculator_category`) and `items` one row per
prompt, for any further analysis.

general:        end-to-end accuracy per category of calculator, and overall ("all")
steps:          per step (E, K, S, A, and E2E on the same examples): well-formed answers, competence, accuracy
by_calculator:  accuracy per calculator and step: where the chain breaks
examples:       one row per example: correctness at each step and the first step that fails
first_failures: for the equation-based examples, how often each step is the first to fail, and the E2E accuracy
                in each case
consistency:    E2E accuracy when every step succeeds and when a step fails: how faithfully the steps represent
                the task
prompt_sensitivity: accuracy of each step with each prompt variant, their mean, standard deviation and range

The views use the default prompts ("v1"); paraphrases (prompt_variants > 1) only enter prompt_sensitivity.

```python
>>> def oracle(messages, max_new_tokens):                   # a perfect "model", to show the report
...     return mk.reference_answer(by_prompt[mk.generation.prompt_key(messages, max_new_tokens)])
>>> ds = mk.data.demo()
>>> items = mk.ProbeSuite({"E": {}, "K": {"mode": "patient"}, "S": {}, "A": {}, "E2E": {}}).build(ds)
>>> by_prompt = {mk.generation.prompt_key(it["messages"], it["max_new_tokens"]): it
...              for it in mk.probes.as_items(items)}
>>> import tempfile
>>> report = mk.evaluate_model(oracle, tempfile.mkdtemp(), dataset=ds, split="demo")
>>> report
MedCalc-Bench evaluation of oracle
  general (end to end): 100.0% of 4 examples (4 calculators)
  step by step (4 examples of equation-based calculators):
    E    extraction         100.0%
    K    formula knowledge  100.0%
    S    substitution       100.0%
    A    arithmetic         100.0%
    E2E  end to end         100.0%
>>> report.general
          n  well_formed  accuracy
category
all       4          1.0       1.0
lab test  2          1.0       1.0
physical  2          1.0       1.0
```

#### `.save(self, directory: str | Path | None = None) -> Path`

Write every view as CSV (and the scores) to `directory` (default: the evaluation's output_dir).


---

## `medcalc_kit.data`

MedCalc-Bench-Verified data: loading, examples, leakage and quality control.

### `data.load`

```python
def load(revision: str = DEFAULT_REVISION, splits: tuple[str, ...] = ('train', 'test'), equation_only: bool = False, dataset_id: str = 'nsk7153/MedCalc-Bench-Verified') -> MedCalcDataset
```

Load MedCalc-Bench-Verified from the Hugging Face Hub (downloaded once, then cached; never redistributed).

revision: dataset commit SHA (default DEFAULT_REVISION, the version the registry was verified against).
equation_only=True keeps the 33 closed-form calculators, the ones the probes support.

```python
>>> ds = data.load(equation_only=True)
>>> ds
MedCalcDataset(...)
>>> test = ds.filter(split="test")
```

### `data.demo`

```python
def demo(n_per_calculator: int = 1, split: str = 'demo') -> MedCalcDataset
```

Hand-written examples (Cockcroft-Gault, BMI, anion gap, mean arterial pressure) with the dataset's columns,
to try every function offline: `n_per_calculator` patients per calculator (the first one is always the same).
Ground truths come from the registry; tolerance interval ±5 %.

```python
>>> ds = data.demo()
>>> ds.df[["example_id", "Calculator Name", "Ground Truth Answer"]]
  example_id                                  Calculator Name  Ground Truth Answer
0   demo:2:1  Creatinine Clearance (Cockcroft-Gault Equation)            79.883911
1   demo:6:1                            Body Mass Index (BMI)            22.857143
2  demo:39:1                                        Anion Gap            12.000000
3   demo:5:1                     Mean Arterial Pressure (MAP)           110.000000
>>> data.demo(5)
MedCalcDataset(20 examples, 4 calculators; demo: 20)
```

### `data.MedCalcDataset`

```python
class MedCalcDataset(df: pd.DataFrame)
```

A collection of examples backed by a DataFrame (`.df`, original column names, plus `entities`, `split` and
`example_id`). Every method returns a new dataset; the original is never modified.

Iterating yields `Example`s; `ds[i]` is the i-th example, `ds["test:2:9"]` the example with that id. The `split`
column is free: besides the benchmark's "train" and "test", create any split with `split_off`, `folds`,
`assign_split` or `with_splits`. An `example_id` never changes, so its prefix keeps the original split.

```python
>>> ds = data.demo()
>>> ds
MedCalcDataset(4 examples, 4 calculators; demo: 4)
>>> len(ds), ds.example_ids[:2]
(4, ['demo:2:1', 'demo:6:1'])
>>> [ex.calculator_id for ex in ds]
['2', '6', '39', '5']
```

#### `.filter(self, calculator: str | int | Iterable[str | int] | None = None, category: str | Iterable[str] | None = None, split: str | Iterable[str] | None = None, note_type: str | Iterable[str] | None = None, where: Callable[[pd.DataFrame], Any] | None = None) -> MedCalcDataset`

Examples matching every given criterion. Each criterion takes one value or a list: calculator id(s),
category ("lab test", "physical", "dosage", "risk", "severity", "diagnosis", "date"), split, note type
("Extracted", "Synthetic"...). `where` is any condition on the DataFrame: a function df -> boolean mask.

```python
>>> ds = data.demo(3)
>>> ds.filter(calculator=[2, "6"]).calculators()[["Calculator ID", "demo"]]
  Calculator ID  demo
0             2     3
1             6     3
>>> len(ds.filter(category=["lab test", "physical"]))
12
>>> ds.filter(where=lambda df: df["Ground Truth Answer"] > 100).example_ids
['demo:5:1', 'demo:5:2', 'demo:5:3']
```

#### `.select(self, example_ids: Iterable[str]) -> MedCalcDataset`

The given examples, in the given order.

```python
>>> data.demo().select(["demo:39:1", "demo:2:1"]).example_ids
['demo:39:1', 'demo:2:1']
```

#### `.sample(self, n: int, seed: int = 0, per_calculator: bool = False) -> MedCalcDataset`

`n` random examples (reproducible with `seed`); per_calculator=True takes up to `n` per calculator.
Handy to try a model on a small subset first.

```python
>>> len(data.demo().sample(2))
2
>>> data.demo().sample(1, per_calculator=True).example_ids
['demo:2:1', 'demo:6:1', 'demo:39:1', 'demo:5:1']
```

#### `.equation_only(self) -> MedCalcDataset`

Only the closed-form (equation-based) calculators (see EQUATION_CATEGORIES).

```python
>>> len(data.demo().equation_only())
4
```

**`.example_ids`** (property): The example ids, in order.

#### `.splits(self) -> pd.DataFrame`

Number of examples and of calculators per split.

```python
>>> data.demo(5).split_off("dev", fraction=0.4, from_split="demo").splits()
       examples  calculators
split
demo         12            4
dev           8            4
```

#### `.assign_split(self, example_ids: Iterable[str], split: str) -> MedCalcDataset`

Move the given examples to `split` (a new or existing split name).

```python
>>> ds = data.demo().assign_split(["demo:2:1", "demo:6:1"], "hard")
>>> ds.splits().examples.to_dict()
{'demo': 2, 'hard': 2}
```

#### `.split_off(self, name: str, fraction: float | None = None, n: int | None = None, *, from_split: str = 'train', per_calculator: bool = True, seed: int = 0, exclude_leaks: bool = False, leak_against: str | Iterable[str] = 'test') -> MedCalcDataset`

Move part of `from_split` to a new split `name`, at random (reproducible with `seed`), e.g. a dev set
taken from the training set. Give `fraction` (of each calculator's examples, at least one) or `n` (per
calculator; in total if per_calculator=False).

exclude_leaks=True never moves an example that leaks into `leak_against` (same note text, or an extracted
note of the same patient, see data.quality), so the new split is clean with respect to the test set.

```python
>>> ds = data.demo(5)
>>> dev = ds.split_off("dev", fraction=0.2, from_split="demo")
>>> dev.splits().examples.to_dict()
{'demo': 16, 'dev': 4}
>>> dev.filter(split="dev").calculators()["dev"].tolist()       # stratified: one per calculator
[1, 1, 1, 1]
>>> ds.split_off("dev", n=3, per_calculator=False, from_split="demo").splits().examples.to_dict()
{'demo': 17, 'dev': 3}
```

#### `.folds(self, k: int, *, from_split: str = 'train', name: str = 'dev', per_calculator: bool = True, seed: int = 0) -> list[MedCalcDataset]`

k-fold cross-validation over `from_split`: k datasets, the i-th with fold i moved to split `name` and the
other folds left in `from_split`. Folds are stratified by calculator and disjoint.

```python
>>> folds = data.demo(5).folds(5, from_split="demo")
>>> [f.splits().examples.to_dict() for f in folds[:2]]
[{'demo': 16, 'dev': 4}, {'demo': 16, 'dev': 4}]
>>> len(set().union(*(f.filter(split="dev").example_ids for f in folds)))       # every example once
20
```

#### `.with_splits(self, assignment: str | Path | pd.DataFrame | pd.Series | Mapping[str, str], *, drop_unassigned: bool = False) -> MedCalcDataset`

Apply a split assignment {example_id: split}: a CSV file written by `save_splits`, a DataFrame with
`example_id` and `split` columns, a Series or a dict. Examples absent from it keep their split, or are
dropped with drop_unassigned=True.

```python
>>> ds = data.demo().with_splits({"demo:2:1": "train", "demo:6:1": "train", "demo:39:1": "test"})
>>> ds.splits().examples.to_dict()
{'demo': 1, 'test': 1, 'train': 2}
>>> len(data.demo().with_splits({"demo:2:1": "train"}, drop_unassigned=True))
1
```

#### `.save_splits(self, path: str | Path) -> Path`

Save the split of every example (CSV: example_id, split), to reproduce a split later with
`with_splits` on a freshly loaded dataset.

```python
>>> import tempfile, pathlib
>>> path = pathlib.Path(tempfile.mkdtemp()) / "splits.csv"
>>> ds = data.demo(5).split_off("dev", fraction=0.2, from_split="demo")
>>> _ = ds.save_splits(path)
>>> data.demo(5).with_splits(path).splits().equals(ds.splits())
True
```

#### `.calculators(self) -> pd.DataFrame`

One row per calculator: id, name, category and number of examples per split.

```python
>>> data.demo().calculators()[["Calculator ID", "Category", "demo"]]
  Calculator ID  Category  demo
0             2  lab test     1
1             5  physical     1
2             6  physical     1
3            39  lab test     1
```

### `data.concat`

```python
def concat(*datasets: MedCalcDataset) -> MedCalcDataset
```

One dataset with the examples of all the given ones (also `ds1 + ds2`). Example ids must be unique.

```python
>>> mine = data.from_records([{"Calculator ID": "6", "entities": {"weight": [80, "kg"], "height": [180, "cm"]},
...                            "Ground Truth Answer": 24.69}], split="mine")
>>> data.demo() + mine
MedCalcDataset(5 examples, 4 calculators; demo: 4, mine: 1)
```

### `data.from_records`

```python
def from_records(records: Iterable[Mapping[str, Any]] | pd.DataFrame, split: str = 'custom') -> MedCalcDataset
```

A dataset from your own examples, with the benchmark's column names. Each record needs "Calculator ID" and
"entities" (or "Relevant Entities", parsed); "Patient Note", "Question", "Ground Truth Answer", "Lower Limit",
"Upper Limit" are needed by the probes that use them (limits default to the ground truth ±5 %). Missing
`example_id`s become "<split>:<calculator id>:<n>"; missing names and categories come from the registry.

```python
>>> ds = data.from_records([{"Calculator ID": 6, "entities": {"weight": [80, "kg"], "height": [180, "cm"]},
...                          "Ground Truth Answer": 24.69}])
>>> ds[0]
Example('custom:6:1', calculator 6 'Body Mass Index (BMI)', ground truth 24.69)
```

### `data.Example`

```python
class Example(example_id: str, split: str, calculator_id: str, calculator_name: str, category: str, note: str, question: str, entities: dict[str, Any], ground_truth: float | str, lower: float | str, upper: float | str, note_id: str = '', note_type: str = '', explanation: str = '') -> None
```

One benchmark example: a patient note, a question and the annotated input values (`entities`).

`entities` maps each input to its annotation, e.g. {"age": [51, "years"], "sex": "Female"}; quantities are
[value, unit]. `ground_truth` must fall in [lower, upper] for an answer to count as correct. For the date
calculators, `ground_truth` is a string (a date "MM/DD/YYYY", or "('16 weeks', '1 days')") and lower = upper.

```python
>>> ex = data.demo()[0]
>>> ex
Example('demo:2:1', calculator 2 'Creatinine Clearance (Cockcroft-Gault Equation)', ground truth 79.88)
>>> ex.entities["weight"]
[68.6, 'kg']
```

#### `.from_row(cls, row: dict[str, Any] | pd.Series) -> Example`

From a dataset row (original column names). Only example_id, Calculator ID and entities are required:
the other columns may be absent in hand-made examples (probes that need them will then be empty).

```python
>>> ex = Example.from_row({"example_id": "my:6:1", "Calculator ID": "6",
...                        "entities": {"weight": [70, "kg"], "height": [175, "cm"]}})
>>> round(ex.derive().answer, 2)
22.86
```

#### `.derive(self)`

Reference computation by the calculator registry (see `medcalc_kit.calculators.derive`).

```python
>>> d = data.demo()[0].derive()
>>> d.branches, round(d.answer, 2)
(['ibw:female', 'bmi>24.9:abw'], 79.88)
```

### `data.as_example`

```python
def as_example(x: Example | dict[str, Any] | pd.Series) -> Example
```

An Example from an Example (returned as is), a dataset row (Series) or a dict with the dataset's columns.

```python
>>> as_example(data.demo().df.iloc[1]).calculator_id
'6'
```

### `data.load_dataframe`

```python
def load_dataframe(revision: str = DEFAULT_REVISION, splits: tuple[str, ...] = ('train', 'test'), dataset_id: str = 'nsk7153/MedCalc-Bench-Verified') -> pd.DataFrame
```

The raw table, one row per example (original column names), plus parsed `entities`, a `split` column and
a stable `example_id` ("<split>:<calculator id>:<row number>"). Most users want `load` instead.

```python
>>> df = data.load_dataframe(splits=("test",))
>>> df[["example_id", "Calculator Name", "Ground Truth Answer"]].head(2)
```

### `data.equation_subset`

```python
def equation_subset(df: pd.DataFrame, categories: Iterable[str] = ('lab test', 'physical', 'dosage')) -> pd.DataFrame
```

Rows of the closed-form (equation-based) calculators, or of the given `categories`.

```python
>>> len(equation_subset(data.demo().df))
4
>>> len(equation_subset(data.demo().df, categories=["lab test"]))
2
```

### `data.parse_entities`

```python
def parse_entities(raw: str) -> dict[str, Any]
```

Parse a "Relevant Entities" annotation: JSON or a Python-literal dict (literal_eval never executes code).

```python
>>> parse_entities('{"weight": [70, "kg"]}')
{'weight': [70, 'kg']}
>>> parse_entities("{'sex': 'Male', 'smoker': True}")
{'sex': 'Male', 'smoker': True}
```

### `data.dataset_revision`

```python
def dataset_revision(dataset_id: str = 'nsk7153/MedCalc-Bench-Verified') -> str
```

Current commit SHA of the dataset on the Hugging Face Hub (needs network access).

Pin the result for reproducibility: `load(revision=...)` then always reads the same data.

```python
>>> data.dataset_revision()
'58fc3de568bfc53a68f32327e58f60dc6eaa17f8'
```

### `data.DEFAULT_REVISION`

```python
DEFAULT_REVISION = '58fc3de568bfc53a68f32327e58f60dc6eaa17f8'
```

### `data.EQUATION_CATEGORIES`

```python
EQUATION_CATEGORIES = ('lab test', 'physical', 'dosage')
```


---

## `medcalc_kit.data.quality`

Data quality and leakage control for building clean evaluation pools from the training split.

- leakage: a train note identical to a test note (normalised text hash), or an 'Extracted' (PMC) note of a
  patient present in test;
- registry agreement: the registry reproduces the row's ground truth (disagreement = annotation or
  reference-implementation error);
- plausibility: canonical inputs within wide physiological ranges (catches annotation errors such as
  platelets annotated per litre, not rare extreme-but-real values).

```python
>>> from medcalc_kit import data
>>> ds = data.load(equation_only=True)
>>> pool = data.usable_train_pool(ds)
>>> suite = mk.ProbeSuite(schema=ds, k_pool=pool)
```

### `data.quality.usable_train_pool`

```python
def usable_train_pool(data, train: str = 'train', test: str | Iterable[str] = 'test') -> pd.DataFrame
```

Rows of split `train` that are leakage-free with respect to `test`, reproduced by the registry and
plausible: a clean pool of other patients, e.g. for K test points (ProbeSuite(k_pool=...)). With custom splits,
pass every split you evaluate as `test`, e.g. test=["dev", "test"].

```python
>>> pool = usable_train_pool(data.load(equation_only=True))
```

### `data.quality.flag_train_rows`

```python
def flag_train_rows(data, train: str = 'train', test: str | Iterable[str] = 'test') -> pd.DataFrame
```

Rows of split `train` (DataFrame) with columns leak_text, leak_patient (with respect to the split(s) `test`),
registry_ok, plausible. `data`: a MedCalcDataset or a DataFrame containing both splits.

```python
>>> flags = flag_train_rows(data.load(equation_only=True))
>>> flags[["leak_text", "leak_patient", "registry_ok", "plausible"]].mean()
```

### `data.quality.leak_flags`

```python
def leak_flags(data, split: str = 'train', against: str | Iterable[str] = 'test') -> pd.DataFrame
```

For the rows of `split`: `leak_text` (the same note, up to case and spacing, appears in `against`) and
`leak_patient` (an "Extracted" note of a patient whose extracted note is in `against`). Indexed like the rows.

```python
>>> ds = mk.data.demo(2).assign_split(["demo:2:1"], "test")
>>> leak_flags(ds, split="demo").sum().to_dict()           # demo notes are all different
{'leak_text': 0, 'leak_patient': 0}
```

### `data.quality.leaking_rows`

```python
def leaking_rows(data, split: str = 'train', against: str | Iterable[str] = 'test') -> pd.Series
```

Boolean Series over the rows of `split`: True if the row leaks into `against` (see leak_flags).

### `data.quality.registry_agrees`

```python
def registry_agrees(row) -> bool
```

True if the registry's answer falls within the row's [Lower Limit, Upper Limit].

```python
>>> registry_agrees(mk.data.demo().df.iloc[0])
True
```

### `data.quality.implausible_inputs`

```python
def implausible_inputs(calculator_id: str, entities: dict[str, Any]) -> list[str]
```

Names of canonical inputs outside PLAUSIBLE_RANGES (empty list = plausible).

```python
>>> implausible_inputs("6", {"weight": [70, "kg"], "height": [175, "cm"]})
[]
>>> implausible_inputs("6", {"weight": [70, "kg"], "height": [175, "mm"]})
Traceback (most recent call last):
...
medcalc_kit.units.UnitError: unknown height unit 'mm'
>>> implausible_inputs("6", {"weight": [70, "g"], "height": [175, "cm"]})
['weight']
```

### `data.quality.note_hash`

```python
def note_hash(text: str) -> str
```

Hash of the note text, insensitive to case and whitespace.

```python
>>> note_hash("A 51-year-old  woman.") == note_hash("a 51-year-old woman.")
True
```

### `data.quality.PLAUSIBLE_RANGES`

```python
PLAUSIBLE_RANGES = {'age': (0, 120), 'weight': (0.3, 350), 'height': (30, 250), 'target_bmi': (10, 60), 'scr': (0.1, 25), 'scr_raw': (0.1, 25), 'ucr': (1, 1000), 'na': (100, 200), 'na_raw': (100, 200), 'sna': (100, 200), 'una': (1, 400), 'cl': (60, 150), 'hco3': (1, 60), 'albumin': (0.5, 7), 'ca': (3, 25), 'glucose': (10, 3000), 'bun': (1, 300), 'tc': (50, 1000), 'hdl': (3, 200), 'tg': (10, 10000), 'insulin': (0.1,  ...
```


---

## `medcalc_kit.calculators`

Executable registry of the 33 equation-based MedCalc-Bench calculators.

```python
>>> from medcalc_kit.calculators import derive, table
>>> d = derive("6", {"weight": [70, "kg"], "height": [175, "cm"]})
>>> round(d.answer, 2), [s.expr for s in d.steps]
(22.86, ['weight / (height / 100)^2'])
>>> d.to_frame()            # inputs, coefficients and steps as a DataFrame
     kind    name  ...
>>> len(table())            # one row per calculator
33
```

### `calculators.derive`

```python
def derive(calculator_id: str | int, entities: dict[str, Any]) -> Derivation
```

Reference computation for one patient: canonical inputs, steps, branches and answer.

calculator_id: MedCalc-Bench id (see `table()`); entities: the annotation, {name: value or [value, unit]}.

```python
>>> d = derive(2, {"sex": "Female", "age": [51, "years"], "weight": [68.6, "kg"],
...                "height": [158, "cm"], "creatinine": [0.76, "mg/dL"]})
>>> d.branches, round(d.answer, 1)          # BMI 27.5: overweight, adjusted body weight
(['ibw:female', 'bmi>24.9:abw'], 79.9)
>>> derive(6, {"weight": [70, "kg"]})
Traceback (most recent call last):
...
KeyError: "calculator 6 (Body Mass Index (BMI)) needs the entity 'height'; got ['weight']"
```

### `calculators.table`

```python
def table() -> pd.DataFrame
```

One row per registered calculator: id, name, and the documented deviation from the benchmark's reference
code ("" if none).

```python
>>> table().head(3)
  calculator_id                                             name reference_deviation
0             2  Creatinine Clearance (Cockcroft-Gault Equation)
1             3                 CKD-EPI Equations for Glomerular Filtration Rate
2             5                     Mean Arterial Pressure (MAP)
```

### `calculators.get`

```python
def get(calculator_id: str | int) -> Calculator
```

The registered calculator with this id.

```python
>>> get(6).name
'Body Mass Index (BMI)'
>>> get(1)
Traceback (most recent call last):
...
KeyError: "unknown calculator '1': the registry covers the 33 equation-based calculators, see calculators.table()"
```

### `calculators.list_calculators`

```python
def list_calculators() -> list[Calculator]
```

Every registered calculator, sorted by id.

```python
>>> [c.calculator_id for c in list_calculators()][:5]
['2', '3', '5', '6', '7']
```

### `calculators.verify_registry`

```python
def verify_registry(data)
```

Check the registry against the ground truth of a MedCalcDataset or DataFrame: (per-example table,
per-calculator x split summary). Same as `python -m medcalc_kit.calculators.verify` on the whole dataset.

```python
>>> per_example, summary = verify_registry(mk.data.demo())
>>> bool(per_example.within_bounds.all())
True
```

### `calculators.Derivation`

```python
class Derivation(calculator_id: str, inputs: dict[str, float] = <factory>, coefficients: dict[str, float] = <factory>, steps: list[Step] = <factory>, branches: list[str] = <factory>) -> None
```

The reference computation for one patient, as returned by `derive`.

inputs:        patient values in canonical units (e.g. weight in kg, creatinine in mg/dL),
coefficients:  constants chosen by clinical rules (sex coefficient, ...),
steps:         ordered computation steps; the last one is the answer,
branches:      the piecewise rules that applied to this patient (empty if none).

```python
>>> d = derive("6", {"weight": [154, "lbs"], "height": [175, "cm"]})
>>> d.inputs
{'weight': 69.853168, 'height': 175.0}
>>> [(s.name, s.expr) for s in d.steps]
[('bmi', 'weight / (height / 100)^2')]
>>> round(d.answer, 2)
22.81
```

**`.env`** (property): Every named value: inputs, coefficients and step results.

#### `.step(self, name: str, expression: str) -> float`

Evaluate `expression` over the values so far, record it as a step and return its value.

**`.answer`** (property): The value of the last step.

#### `.to_frame(self) -> pd.DataFrame`

One row per quantity, in computation order: inputs, coefficients, then steps (the last is the answer).

```python
>>> derive("6", {"weight": [70, "kg"], "height": [175, "cm"]}).to_frame()
    kind    name                       expr       value
0  input  weight                               70.000000
1  input  height                              175.000000
2   step     bmi  weight / (height / 100)^2   22.857143
```

### `calculators.Step`

```python
class Step(name: str, expr: str, value: float) -> None
```

One computation step: `name = expr`, and its value.

### `calculators.Calculator`

```python
class Calculator(calculator_id: str, name: str, derive: Callable[[dict[str, Any]], Derivation]) -> None
```

A registered calculator: its MedCalc-Bench id, its name and its derivation function.

### `calculators.KNOWN_REFERENCE_DEVIATIONS`

```python
KNOWN_REFERENCE_DEVIATIONS = {'31': 'HOMA-IR: reference converts insulin pmol/L -> µIU/mL by *6; correct is /6.', '23': 'MELD Na: reference clamps creatinine to >=1.0 before applying the dialysis rule (dialysis patients with creatinine < 1 get 1.0 instead of 4.0).'}
```


---

## `medcalc_kit.calculators.registry`

Core of the executable calculator registry.

Each calculator maps the benchmark's "Relevant Entities" annotation to a Derivation:
  - inputs:        patient values converted to canonical units,
  - coefficients:  values fixed by clinical rules (sex coefficient, CKD-EPI a/b, TBW fraction...),
  - steps:         ordered (name, expression) pairs in the safe grammar of medcalc_kit.expr; the last
                   step is the answer. Branches (piecewise rules) are resolved in Python and the
                   chosen branch is recorded in `branches`.

Conventions follow the reference implementation (ncbi-nlp/MedCalc-Bench) when the benchmark question
states them; known reference bugs are NOT reproduced and are listed in KNOWN_REFERENCE_DEVIATIONS.

### `calculators.registry.calculator`

```python
def calculator(cid: str, name: str)
```

Decorator registering a derivation function under a MedCalc-Bench calculator id (to add a calculator).

```python
>>> @calculator("999", "Pulse pressure")
... def pulse_pressure(e):
...     d = new_derivation("999")
...     d.inputs.update(sbp=e["sbp"][0], dbp=e["dbp"][0])
...     d.step("pp", "sbp - dbp")
...     return d
>>> derive("999", {"sbp": [120, "mm Hg"], "dbp": [80, "mm Hg"]}).answer
40.0
>>> del CALCULATORS["999"]
```

### `calculators.registry.new_derivation`

```python
def new_derivation(cid: str) -> Derivation
```

An empty Derivation for calculator `cid` (helper for derivation functions).

### `calculators.registry.is_male`

```python
def is_male(e: dict[str, Any]) -> bool
```

True if the annotation's sex is "Male" (helper for derivation functions).


---

## `medcalc_kit.calculators.verify`

Verify the calculator registry against MedCalc-Bench-Verified ground truth.

For every equation-based example the registry recomputes the answer from the annotated entities and
compares it with the ground truth interval. Disagreements point to a registry bug, an undocumented
benchmark convention, or an annotation / ground-truth error.

Usage:
    python -m medcalc_kit.calculators.verify [--revision SHA] [--out registry_verification]

### `calculators.verify.verify`

```python
def verify(data) -> tuple[pd.DataFrame, pd.DataFrame]
```

(per-example table, per-calculator x split summary) for a MedCalcDataset or DataFrame.

```python
>>> per_example, summary = verify(mk.data.demo())
>>> summary[["calculator_id", "n", "within_bounds"]]
  calculator_id  n  within_bounds
0             2  1            1.0
1            39  1            1.0
2             5  1            1.0
3             6  1            1.0
```

### `calculators.verify.check_row`

```python
def check_row(row) -> dict[str, Any]
```

Registry value, branches and agreement with the ground truth for one dataset row.

```python
>>> r = check_row(mk.data.demo().df.iloc[2])
>>> r["registry_value"], r["within_bounds"], r["error"]
(12.0, True, None)
```

### `calculators.verify.main`

```python
def main() -> None
```

Command line: `python -m medcalc_kit.calculators.verify [--revision SHA] [--out DIR]`.


---

## `medcalc_kit.probes`

Diagnostic probes: one module per competence, each with its prompt (`build`) and its scoring (`score`).

| probe | module        | measures                                                     |
|-------|---------------|--------------------------------------------------------------|
| E     | extraction    | finding the input values (with units) in the patient note    |
| K     | knowledge     | writing the general formula without the patient's values     |
| S     | substitution  | plugging the values into a given formula, without computing  |
| A     | arithmetic    | computing a fully written numerical expression               |
| E2E   | end_to_end    | the original benchmark task                                  |

An item is a dict (or a DataFrame row): the chat to send (`messages`) and what the scorer needs (`reference`).

```python
>>> from medcalc_kit import probes
>>> ex = mk.data.demo()[1]                                  # BMI, 70 kg, 175 cm
>>> item = probes.substitution.build(ex)                    # prompt + reference
>>> print(probes.prompt(item).splitlines()[2])              # what the model is asked
[user] Formula for Body Mass Index (BMI):
>>> probes.score(item, '{"expression": "70 / (175 / 100)^2"}')["correct"]
True
>>> probes.score(item, '{"expression": "22.857143"}')["error_type"]   # computed instead of substituted
'premature_computation'
```

### `probes.ProbeSuite`

```python
class ProbeSuite(probes: Iterable[str] | Mapping[str, Mapping[str, Any]] = ('E', 'K', 'S', 'A', 'E2E'), *, schema=None, k_pool=None, seed: int = 0)
```

Builds the items of several probes at once, giving each probe the context it needs.

E2E items are built for every example of the benchmark. The step probes (E, K, S, A) need the reference
computation, so they are built only for the 33 equation-based calculators of the registry; other examples
(rule-based scores, dates) get E2E only.

probes:  probe names ("E", "K", "S", "A", "E2E"), or {label: options} where options are keyword arguments of
         that probe's build() plus an optional "task" (the probe to use; default: the label). Labels let you
         build several variants of a probe, e.g.
             {"K": {"mode": "patient", "max_new_tokens": 1536}, "Kg": {"task": "K", "mode": "general"}}
schema:  examples used to infer the E field list per calculator (use the whole dataset, train + test,
         so that optional fields are asked consistently). Default: the examples being built.
k_pool:  patients used as K test points (MedCalcDataset or DataFrame, e.g. a leakage-free train pool),
         shuffled per calculator with `seed`. Default: perturbations of the patient at scoring time.

```python
>>> ProbeSuite().probes                                   # every probe, default options
['E', 'K', 'S', 'A', 'E2E']
>>> suite = ProbeSuite({"K": {"mode": "patient"}, "Kg": {"task": "K"}, "A": {"max_new_tokens": 512}})
>>> items = suite.build(mk.data.demo())
>>> items.groupby("probe", sort=False).max_new_tokens.first().to_dict()
{'K': 1024, 'Kg': 1024, 'A': 512}
>>> ProbeSuite(["X"])
Traceback (most recent call last):
...
ValueError: unknown probe 'X' for label 'X' (available: E, K, S, A, E2E)
```

#### `.build(self, examples: MedCalcDataset | pd.DataFrame | Iterable[Example | dict[str, Any]], check: bool = True, as_frame: bool = True) -> pd.DataFrame | dict[str, list[Item]]`

One row per item (see probes.items_frame), label by label, each in the order of `examples`
(as_frame=False: {label: [item, ...]}). check=True asserts that the resolved branch formula used by S and A
reproduces the registry answer.

examples: a MedCalcDataset, a DataFrame of dataset rows, or Examples / row dicts.

```python
>>> items = ProbeSuite("E2E").build(mk.data.demo())
>>> list(items.columns)
['item_id', 'probe', 'example_id', 'calculator_id', 'calculator_name', 'template', 'template_hash',
 'max_new_tokens', 'messages', 'reference']
>>> {k: round(v, 2) for k, v in items.loc[0, "reference"].items() if k != "answer_type"}
{'ground_truth': 79.88, 'lower': 75.89, 'upper': 83.88}
>>> list(ProbeSuite("E2E").build(mk.data.demo(), as_frame=False))
['E2E']
```

### `probes.score`

```python
def score(item: Item | pd.Series, text: str, **options: Any) -> dict[str, Any]
```

Score a model answer for any item (a dict or a DataFrame row). Dispatches on the item's task; `options` are
passed to that probe's score() (tolerances, case semantics...).

The verdict always has `format_valid`, `correct` and `error_type` (None when correct), plus probe-specific
details (e.g. `fields` for E, `point_pass_rate` for K, `rel_error` for A).

```python
>>> item = arithmetic.build(mk.data.demo()[2])              # anion gap: 140 - (104 + 24)
>>> score(item, 'So the result is {"result": 12}')
{'format_valid': True, 'correct': True, 'correct_strict': True, 'error_type': None, 'rel_error': 0.0}
>>> score(item, '{"result": 14}')["error_type"]
'arithmetic_error'
>>> score(item, 'twelve')["error_type"]
'format_invalid'
>>> score(item, '{"result": 12.1}', rel_tol=0.001)["correct"]
False
```

### `probes.reference_answer`

```python
def reference_answer(item: Item | pd.Series) -> str
```

A model answer that the item's probe scores as correct, in the format the prompt asks for. Useful to see
the expected format and to test a pipeline end to end without a model. For K in "general" mode, it is only
correct for calculators without branches (see knowledge.reference_answer).

```python
>>> ex = mk.data.demo()[2]
>>> reference_answer(arithmetic.build(ex))
'{"result": 12.0}'
>>> reference_answer(extraction.build(ex))
'{"Sodium": {"value": 140.0, "unit": "mEq/L"}, "Chloride": {"value": 104.0, "unit": "mEq/L"},
  "Bicarbonate": {"value": 24.0, "unit": "mEq/L"}}'
>>> item = knowledge.build(ex)
>>> reference_answer(item)
'{"cases": [{"condition": "always", "formula": "na - (cl + hco3)"}]}'
>>> score(item, reference_answer(item))["correct"]
True
```

### `probes.prompt`

```python
def prompt(item: Item | pd.Series) -> str
```

The chat of an item as readable text ("[role] content" blocks), to see what the model is asked.

```python
>>> item = mk.probes.arithmetic.build(mk.data.demo()[1])
>>> print(prompt(item))
[system] You are a careful clinical calculation assistant.
<BLANKLINE>
[user] Compute the value of the following expression ...
<BLANKLINE>
70 / (175 / 100)^2
<BLANKLINE>
Work carefully without any tool. ...
```

### `probes.get`

```python
def get(name: str) -> Probe
```

The probe with this name ("E", "K", "S", "A" or "E2E").

```python
>>> [(p.name, p.title) for p in map(get, ALL_PROBES)]
[('E', 'Extraction'), ('K', 'Knowledge'), ('S', 'Substitution'), ('A', 'Arithmetic'), ('E2E', 'End to end')]
```

### `probes.PROBES`

```python
PROBES = {'E': Probe(name='E', title='Extraction', measures='finding the input values (with units) in the patient note', build=<function build>, score=<function score>, reference_answer=<function reference_answer>), 'K': Probe(name='K', title='Knowledge', measures='writing the formula (general, or for this patient) without computing', build=<function build>, score=<function score>, reference_answer=<functi ...
```

### `probes.ALL_PROBES`

```python
ALL_PROBES = ('E', 'K', 'S', 'A', 'E2E')
```

### `probes.STEP_PROBES`

```python
STEP_PROBES = ('E', 'K', 'S', 'A')
```

### `probes.Probe`

```python
class Probe(name: str, title: str, measures: str, build: Callable[..., Item], score: Callable[[Item, str], dict[str, Any]], reference_answer: Callable[[Item], str]) -> None
```

A probe = how to build its prompt for an example + how to score a model answer.

build(example, **context) -> item     (context depends on the probe, see each module)
score(item, text) -> verdict dict      at least: format_valid, correct, error_type
reference_answer(item) -> text         a model answer that this probe scores as correct

```python
>>> p = mk.probes.get("A")
>>> p.name, p.title, p.measures
('A', 'Arithmetic', 'computing a fully written numerical expression')
```

### `probes.read_items`

```python
def read_items(directory: str | Path, probes: Iterable[str] | None = None, as_frame: bool = True) -> pd.DataFrame | list[Item]
```

Load items saved by `write_items`: the given probe labels (default: every <label>.jsonl in the directory),
one row per item (as_frame=False: a list of dicts).

```python
>>> import tempfile
>>> folder = tempfile.mkdtemp()
>>> _ = write_items(ProbeSuite(["S", "A"]).build(mk.data.demo()), folder)
>>> read_items(folder).groupby("probe").size().to_dict()
{'A': 4, 'S': 4}
>>> len(read_items(folder, probes=["S"]))
4
```

### `probes.write_items`

```python
def write_items(items: pd.DataFrame | list[Item] | dict[str, list[Item]], directory: str | Path) -> dict[str, int]
```

Save items as one JSONL file per probe label (<directory>/<label>.jsonl). Returns the counts per label.

```python
>>> import tempfile
>>> folder = tempfile.mkdtemp()
>>> write_items(ProbeSuite(["S", "A"]).build(mk.data.demo()), folder)
{'S': 4, 'A': 4}
```

### `probes.items_frame`

```python
def items_frame(items: pd.DataFrame | Iterable[Item] | Mapping[str, Iterable[Item]]) -> pd.DataFrame
```

One row per item; `messages` and `reference` stay nested (object columns).

```python
>>> items = items_frame([mk.probes.arithmetic.build(ex) for ex in mk.data.demo()])
>>> items[["item_id", "probe", "max_new_tokens"]].head(2)
      item_id probe  max_new_tokens
0  demo:2:1:A     A            1024
1  demo:6:1:A     A            1024
```

### `probes.as_items`

```python
def as_items(items: pd.DataFrame | Iterable[Item] | Mapping[str, Iterable[Item]]) -> list[Item]
```

Items (or generation records) as a list of dicts, from a DataFrame, a list or {label: [item, ...]}.
Missing cells of a DataFrame (NaN, e.g. `task` for items whose label is their task) are dropped.

```python
>>> items = mk.ProbeSuite({"K": {}, "Kg": {"task": "K"}}).build(mk.data.demo())
>>> dicts = as_items(items)
>>> "task" in dicts[0], dicts[-1]["task"]                   # NaN cells are not carried over
(False, 'K')
```

### `probes.as_item`

```python
def as_item(item: Item | pd.Series) -> Item
```

One item as a dict, from a dict (returned as is) or a DataFrame row (missing cells dropped).

```python
>>> items = mk.ProbeSuite(["A"]).build(mk.data.demo())
>>> as_item(items.iloc[0])["item_id"]
'demo:2:1:A'
```


---

## `medcalc_kit.probes.extraction`

E — Extraction: can the model find the calculator's input values in the patient note?

Prompt: the note + the list of fields of this calculator. Values are asked WITH their unit as written in the
note (no conversion), so that extraction is not confounded with unit conversion.
Scoring: field by field; quantities are converted to canonical units on both sides before comparison
(relative tolerance `rel_tol`). The item is correct if every field is correct.

Field results: correct, missing, wrong_value, unit_error (right number, unit changing its meaning),
unparsable, unit_unparsable, hallucinated (a value for a field absent from the note), gold_unconvertible.
The item's error_type is format_invalid or the most frequent field error.

```python
>>> item = build(mk.data.demo()[2])                         # anion gap: sodium, chloride, bicarbonate
>>> v = score(item, '{"Sodium": {"value": 140, "unit": "mmol/L"}, "Chloride": {"value": 104, "unit": "mEq/L"},'
...                 ' "Bicarbonate": {"value": 42, "unit": "mEq/L"}}')
>>> v["correct"], v["field_accuracy"], v["fields"]
(False, 0.666..., {'Sodium': 'correct', 'Chloride': 'correct', 'Bicarbonate': 'wrong_value'})
```

### `probes.extraction.build`

```python
def build(example: Example | dict[str, Any], fields: dict[str, str] | None = None, *, template: str = DEFAULT_TEMPLATE, max_new_tokens: int = 768, system_prompt: str | None = DEFAULT_SYSTEM_PROMPT, kind_hints: dict[str, str] | None = None, field_hints: dict[str, str] | None = None, label: str = 'E') -> Item
```

fields: field name -> kind for this calculator (see calculator_fields); default: this example's fields.
For MME (calculator 49) the drug fields are always taken from the example itself.

kind_hints: answer format per field kind (overrides KIND_HINT); field_hints: answer format for specific
field names (overrides the kind's format). template: prompt text with placeholders {note} and {fields}, or the
name of a variant of TEMPLATES ("v1", "v2", "v3");
max_new_tokens: token budget; system_prompt: None for none; label: the item's probe label (default "E").

```python
>>> item = build(mk.data.demo()[1], field_hints={"height": "height in cm, a number"})
>>> print(item["messages"][-1]["content"].split("Fields:")[1].split("You may")[0].strip())
- "weight": {"value": <number>, "unit": <unit as written>}
- "height": height in cm, a number
>>> item["reference"]["gold"]
{'weight': [70.0, 'kg'], 'height': [175.0, 'cm']}
```

### `probes.extraction.score`

```python
def score(item: Item, text: str, *, rel_tol: float = 0.01, accept_unit_as_written: bool = True) -> dict[str, Any]
```

Score a model answer for an E item. Options: rel_tol (default 1 %), accept_unit_as_written (accept a
value copied with the unit written in the prompt's note, default True).

```python
>>> score(build(mk.data.demo()[1]), '{"weight": {"value": 70, "unit": "kg"}}')["fields"]
{'weight': 'correct', 'height': 'missing'}
```

### `probes.extraction.score_answer`

```python
def score_answer(reference: dict[str, Any], text: str, note: str | None = None, rel_tol: float = 0.01) -> dict[str, Any]
```

Score a model answer against an E reference ({"fields", "gold"}).

```python
>>> ref = build(mk.data.demo()[1])["reference"]
>>> score_answer(ref, '{"weight": "70 kg", "height": "1.75 m"}')
{'format_valid': True, 'correct': True, 'field_accuracy': 1.0, 'error_type': None,
 'fields': {'weight': 'correct', 'height': 'correct'}}
```

### `probes.extraction.score_field`

```python
def score_field(name: str, kind: str, gold: Any, pred: Any, present: bool, note: str | None = None, rel_tol: float = 0.01) -> str
```

Return 'correct' or an error category for one field. `present`: the field is a key of the model's JSON.
`note`: the text the values were extracted from; when given, a value copied with the unit written in the note
is accepted even if the annotation uses another unit.

```python
>>> score_field("weight", "quantity", [70, "kg"], {"value": 154.3, "unit": "lbs"}, True)   # converted
'correct'
>>> score_field("creatinine", "quantity", [0.76, "mg/dL"], "0.76 µmol/L", True)
'unit_error'
>>> score_field("weight", "quantity", [70, "kg"], None, False)
'missing'
```

### `probes.extraction.reference_answer`

```python
def reference_answer(item: Item) -> str
```

A correct answer: every annotated field in the expected JSON format (composite heights and ages are
given in cm / years).

```python
>>> reference_answer(build(mk.data.demo()[1]))
'{"weight": {"value": 70.0, "unit": "kg"}, "height": {"value": 175.0, "unit": "cm"}}'
```

### `probes.extraction.calculator_fields`

```python
def calculator_fields(examples: Iterable[Example | dict[str, Any]]) -> dict[str, dict[str, str]]
```

Union of annotated fields per calculator, with their kind. Use the whole dataset (train + test) so that
optional fields (e.g. 'Race', boolean history items) are asked for every example of a calculator.

```python
>>> calculator_fields(mk.data.demo())["6"]
{'weight': 'quantity', 'height': 'quantity'}
```

### `probes.extraction.field_kind`

```python
def field_kind(name: str, value: Any) -> str
```

Answer type of an annotated field: sex, race, steroid, bool, number or quantity.

```python
>>> field_kind("weight", [70, "kg"]), field_kind("smoker", True), field_kind("sex", "Male")
('quantity', 'bool', 'sex')
```

### `probes.extraction.default_field_hint`

```python
def default_field_hint(name: str, kind: str, kind_hints: dict[str, str]) -> str
```

Answer format shown for a field. MME fields get explicit wording: '<drug> Dose Per Day' is the number of
administrations per day (not a daily dose), '<drug> Dose' the dose of one administration.

```python
>>> default_field_hint("weight", "quantity", KIND_HINT)
'{"value": <number>, "unit": <unit as written>}'
>>> default_field_hint("Morphine Dose Per Day", "quantity", KIND_HINT)
'{"value": <number of administrations per day>, "unit": "per day"}'
```

### `probes.extraction.TEMPLATES`

```python
TEMPLATES = {'v1': "Patient note:\n{note}\n\nTask: extract the following information about the patient from the note. Use the values at the patient's first admission, before any treatment. Report each numeric value exactly as written in the note together with its unit (do not convert units). Use null if a value is not mentioned.\n\nFields:\n{fields}\n\nYou may think briefly, then end your answer with a single ...
```

### `probes.extraction.DEFAULT_TEMPLATE`

```python
DEFAULT_TEMPLATE = "Patient note:\n{note}\n\nTask: extract the following information about the patient from the note. Use the values at the patient's first admission, before any treatment. Report each numeric value exactly as written in the note together with its unit (do not convert units). Use null if a value is not mentioned.\n\nFields:\n{fields}\n\nYou may think briefly, then end your answer with a single JSON o ...
```

### `probes.extraction.KIND_HINT`

```python
KIND_HINT = {'sex': '"Male" or "Female"', 'race': "the patient's race as written in the note, or null", 'steroid': '{"drug": <name>, "value": <dose>, "unit": <unit>}', 'bool': 'true or false (false if not mentioned)', 'number': 'a number', 'quantity': '{"value": <number>, "unit": <unit as written>}'}
```


---

## `medcalc_kit.probes.knowledge`

K — Knowledge: does the model know the calculator's formula?

Two modes:
- "general" (default): the model sees the question, the fixed categorical characteristics (sex, drugs...) and
  the variables with their units, but NOT the patient's values. It writes the general formula, one case per
  branch: {"cases": [{"condition": "<condition, or always>", "formula": "<expression>"}]}
- "patient": the model also sees the patient's values and writes the formula that applies to THIS patient,
  as an expression of the variables: {"formula": "<expression>"}. Only the relevant branch is needed, so the
  probe measures recall of the formula rather than the writing of a complete piecewise function.

Scoring: the model's formula is evaluated (safe parser, never eval) at the patient's point and at up to
`n_points` other patients — real patients of the same calculator when a pool is given at build time
(restricted to the patient's branch in "patient" mode), otherwise perturbations of the patient — and compared
with the registry. It is correct if it is right at the patient's point and at a share of all points of at least
`min_pass_rate` (default 1.0: every point). Symbolic comparison is avoided on purpose:
branches, rounded constants and equivalent rewritings make it fragile.

In "general" mode the prompt depends on the patient only through categorical fields, so many examples share
the same prompt: count each distinct prompt once in statistics (generation.prompt_key, evaluate.to_units).

Error types: format_invalid, unparsable_formula, unknown_variable (a name not in the listed variables),
wrong_at_patient_point, wrong_elsewhere (right for this patient only: wrong branch or wrong constant).

```python
>>> item = build(mk.data.demo()[2])                         # anion gap, variables na, cl, hco3
>>> score(item, '{"cases": [{"condition": "always", "formula": "na - cl - hco3"}]}')["correct"]
True
>>> score(item, '{"cases": [{"condition": "always", "formula": "na + 4 - cl - hco3"}]}')["error_type"]
'wrong_at_patient_point'
```

### `probes.knowledge.build`

```python
def build(example: Example | dict[str, Any], point_pool: list[dict[str, Any]] | None = None, *, mode: str = 'general', template: str | None = None, max_new_tokens: int = 1024, system_prompt: str | None = DEFAULT_SYSTEM_PROMPT, n_points: int = 50, symbol_docs: dict[str, str] | None = None, digits: int = 6, label: str = 'K') -> Item
```

point_pool: entity dicts of other (leakage-free) patients of the same calculator, used as test points
so that thresholds are explored realistically (in "patient" mode, only those in the patient's branch are
kept; pass a large pool). Without a pool, perturbations of the patient are used at scoring time.
mode: "general" (no values shown, one case per branch) or "patient" (values shown, this patient's formula).
template: prompt text, or the name of a variant ("v1", "v2", "v3") of TEMPLATES ("general" mode) or
PATIENT_TEMPLATES ("patient" mode); default "v1" (DEFAULT_TEMPLATE / DEFAULT_PATIENT_TEMPLATE).
n_points: test points kept from the pool; symbol_docs: {variable: description} overriding
common.SYMBOL_DOCS; digits: significant digits of the values shown in "patient" mode.

```python
>>> item = build(mk.data.demo()[1], mode="patient")
>>> print(item["messages"][-1]["content"].split("Variables:")[1].split("Use only")[0].strip())
- weight: body weight (kg)
- height: height (cm)
>>> item["reference"]["symbols"], item["reference"]["branches"]
(['weight', 'height'], [])
```

### `probes.knowledge.score`

```python
def score(item: Item, text: str, **options: Any) -> dict[str, Any]
```

Score a model answer for a K item. Options: see score_answer (rel_tol, abs_tol, n_points, case_semantics,
perturbation_factor, plausible_ranges, min_pass_rate, details). The perturbation seed is derived from the item
id, so scores are reproducible.

```python
>>> item = build(mk.data.demo()[1])
>>> score(item, '{"cases": [{"condition": "always", "formula": "weight / (height / 100)^2"}]}')["n_points"]
51
>>> score(item, '{"cases": [{"condition": "always", "formula": "w / h^2"}]}')["unknown_variables"]
['h', 'w']
```

A formula right at the patient's point but not everywhere can be accepted with a lower threshold:

```python
>>> almost = '{"cases": [{"condition": "height > 220", "formula": "0"}, ' \
...          '{"condition": "otherwise", "formula": "weight / (height / 100)^2"}]}'
>>> v = score(item, almost)
>>> v["correct"], v["error_type"], round(v["point_pass_rate"], 2)
(False, 'wrong_elsewhere', 0.94)
>>> score(item, almost, min_pass_rate=0.9)["correct"]
True
```

### `probes.knowledge.score_answer`

```python
def score_answer(reference: dict[str, Any], text: str, calculator_id: str, seed: int = 0, *, rel_tol: float = 0.01, abs_tol: dict[str, float] | None = None, n_points: int = 50, case_semantics: str = 'all_agree', perturbation_factor: float = 3.0, plausible_ranges: dict[str, tuple[float, float]] | None = {'age': (0, 120), 'weight': (0.3, 350), 'height': (30, 250), 'target_bmi': (10, 60), 'scr': (0.1, 25), 'scr_raw': (0.1, 25), 'ucr': (1, 1000), 'na': (100, 200), 'na_raw': (100, 200), 'sna': (100, 200), 'una': (1, 400), 'cl': (60, 150), 'hco3': (1, 60), 'albumin': (0.5, 7), 'ca': (3, 25), 'glucose': (10, 3000), 'bun': (1, 300), 'tc': (50, 1000), 'hdl': (3, 200), 'tg': (10, 10000), 'insulin': (0.1, 1000), 'ast': (1, 20000), 'alt': (1, 20000), 'platelets': (1, 2000), 'bili_raw': (0.05, 80), 'inr_raw': (0.5, 20), 'sbp': (40, 300), 'dbp': (10, 200), 'hr': (20, 300), 'qt': (150, 800), 'dose': (0.01, 5000)}, min_pass_rate: float = 1.0, details: bool = False) -> dict[str, Any]
```

Score a model answer against a K reference.

rel_tol: relative tolerance at each point; abs_tol: per-calculator absolute tolerance replacing rel_tol
(default DEFAULT_ABS_TOL; {} to disable); n_points: test points besides the patient's; case_semantics:
"all_agree" or "first_match" (see eval_cases); perturbation_factor, plausible_ranges: see test_points.
min_pass_rate: share of the test points the formula must be right at (default 1.0, all of them); a formula
wrong at the patient's point is never correct, whatever the threshold.
details=True adds `points`: one row per test point (inputs, registry value, model value, ok).

```python
>>> ref = build(mk.data.demo()[1])["reference"]
>>> v = score_answer(ref, '{"formula": "weight / height^2"}', "6", details=True)   # forgot cm -> m
>>> v["error_type"], v["point_pass_rate"]
('wrong_at_patient_point', 0.0)
>>> pd.DataFrame(v["points"]).head(2).round(4)
    weight    height  registry   model     ok
0  70.0000  175.0000   22.8571  0.0023  False
1  58.7901  103.0353   55.3773  0.0055  False
```

### `probes.knowledge.reference_answer`

```python
def reference_answer(item: Item) -> str
```

The registry's formula for this patient's branch, in the expected JSON format. Always correct in "patient"
mode; in "general" mode it is correct only for calculators without branches, since the registry resolves
branch conditions in code and does not store them as formulas.

```python
>>> reference_answer(build(mk.data.demo()[1], mode="patient"))
'{"formula": "weight / (height / 100)^2"}'
```

### `probes.knowledge.test_points`

```python
def test_points(reference: dict[str, Any], calculator_id: str, seed: int, n_points: int = 50, perturbation_factor: float = 3.0, plausible_ranges: dict[str, tuple[float, float]] | None = {'age': (0, 120), 'weight': (0.3, 350), 'height': (30, 250), 'target_bmi': (10, 60), 'scr': (0.1, 25), 'scr_raw': (0.1, 25), 'ucr': (1, 1000), 'na': (100, 200), 'na_raw': (100, 200), 'sna': (100, 200), 'una': (1, 400), 'cl': (60, 150), 'hco3': (1, 60), 'albumin': (0.5, 7), 'ca': (3, 25), 'glucose': (10, 3000), 'bun': (1, 300), 'tc': (50, 1000), 'hdl': (3, 200), 'tg': (10, 10000), 'insulin': (0.1, 1000), 'ast': (1, 20000), 'alt': (1, 20000), 'platelets': (1, 2000), 'bili_raw': (0.05, 80), 'inr_raw': (0.5, 20), 'sbp': (40, 300), 'dbp': (10, 200), 'hr': (20, 300), 'qt': (150, 800), 'dose': (0.01, 5000)}) -> list[tuple[dict[str, float], float]]
```

(canonical inputs, registry value) at the patient point + up to n_points other points: the reference's
pool points, or perturbations of the patient as a fallback. Perturbed points must lie in the patient's
branch ("patient" mode) and within `plausible_ranges` (default data.PLAUSIBLE_RANGES; None = no bound).

```python
>>> pts = test_points(build(mk.data.demo()[1])["reference"], "6", seed=0, n_points=3)
>>> len(pts), pts[0]
(4, ({'weight': 70.0, 'height': 175.0}, 22.857142857142858))
```

### `probes.knowledge.eval_cases`

```python
def eval_cases(cases: list[tuple[str | None, expr.Node | None]], env: dict[str, float], semantics: str = 'all_agree') -> float
```

Value of a piecewise answer at one point. Raises ExprError if no case (or an undefined one) applies.

semantics: "all_agree" — every case whose condition holds must give the same value;
           "first_match" — the first case (in the written order) whose condition holds is used.
"otherwise" applies when no other condition holds.

```python
>>> cases = [("x < 10", expr.parse("2 * x")), ("otherwise", expr.parse("x"))]
>>> eval_cases(cases, {"x": 3}), eval_cases(cases, {"x": 30})
(6.0, 30.0)
```

### `probes.knowledge.perturb_entities`

```python
def perturb_entities(entities: dict[str, Any], rng: random.Random, factor: float = 3.0) -> dict[str, Any]
```

Multiply every continuous value by a log-uniform factor in [1/factor, factor]; keep categorical fields;
daily administration counts become random integers in 1..6.

```python
>>> p = perturb_entities({"sex": "Male", "weight": [70.0, "kg"]}, random.Random(0))
>>> p["sex"], p["weight"][1], 70 / 3 <= p["weight"][0] <= 70 * 3
('Male', 'kg', True)
```

### `probes.knowledge.with_categorical`

```python
def with_categorical(point: dict[str, Any], entities: dict[str, Any]) -> dict[str, Any]
```

Continuous values from `point`, categorical (str/bool) fields from `entities`.

```python
>>> with_categorical({"sex": "Male", "age": [40, "years"]}, {"sex": "Female", "age": [51, "years"]})
{'age': [40, 'years'], 'sex': 'Female'}
```

### `probes.knowledge.TEMPLATES`

```python
TEMPLATES = {'v1': 'Task: {question}\n\nYou are NOT given the patient\'s measurements. Write the general formula needed to answer this task, using only the variables listed below. Their units are fixed as stated; include any unit conversion inside your formula.\n\nKnown patient characteristics:\n{context}\n\nVariables:\n{variables}\n\nIf the formula depends on thresholds or categories, give one case per branc ...
```

### `probes.knowledge.PATIENT_TEMPLATES`

```python
PATIENT_TEMPLATES = {'v1': 'Task: {question}\n\nKnown patient characteristics:\n{context}\n\nPatient values:\n{values}\n\nWrite the formula that applies to THIS patient, as an expression of the variables listed below (their units are fixed as stated; include any unit conversion inside your formula). Do NOT compute the result: use the variable names, not the patient\'s numbers.\n\nVariables:\n{variables}\n\nUse only n ...
```

### `probes.knowledge.DEFAULT_TEMPLATE`

```python
DEFAULT_TEMPLATE = 'Task: {question}\n\nYou are NOT given the patient\'s measurements. Write the general formula needed to answer this task, using only the variables listed below. Their units are fixed as stated; include any unit conversion inside your formula.\n\nKnown patient characteristics:\n{context}\n\nVariables:\n{variables}\n\nIf the formula depends on thresholds or categories, give one case per branch, each ...
```

### `probes.knowledge.DEFAULT_PATIENT_TEMPLATE`

```python
DEFAULT_PATIENT_TEMPLATE = 'Task: {question}\n\nKnown patient characteristics:\n{context}\n\nPatient values:\n{values}\n\nWrite the formula that applies to THIS patient, as an expression of the variables listed below (their units are fixed as stated; include any unit conversion inside your formula). Do NOT compute the result: use the variable names, not the patient\'s numbers.\n\nVariables:\n{variables}\n\nUse only numbers, ...
```


---

## `medcalc_kit.probes.substitution`

S — Substitution: can the model plug the values into a GIVEN formula?

Prompt: the formula of this patient's branch (resolved by the registry) and the value of each variable.
The model must copy the formula, replacing each variable by its value, without computing anything.
Scoring: (1) structural identity with the expected substituted expression (canonical form, so reordering is
accepted); otherwise (2) literals are mapped back to variables and the result is tested for numerical
equivalence with the formula. Checking the value alone is not enough: a partly computed answer has the right
value without being a substitution, and two swapped variables can give the right value by accident.

Error types: format_invalid, unparsable_expression, unsubstituted_variable (a variable name left in),
premature_computation (part of it computed: right value, missing literals), missing_or_wrong_value,
accidental_value_match (right value, wrong structure), structure_or_assignment_error, too_ambiguous.

```python
>>> item = build(mk.data.demo()[2])                         # anion gap
>>> item["reference"]["formula"], item["reference"]["gold_expression"]
('na - (cl + hco3)', '140 - (104 + 24)')
>>> score(item, '{"expression": "140 - (24 + 104)"}')["match"]     # reordering is accepted
'canonical'
>>> score(item, '{"expression": "140 - 128"}')["error_type"]
'premature_computation'
```

### `probes.substitution.build`

```python
def build(example: Example | dict[str, Any], *, template: str = DEFAULT_TEMPLATE, max_new_tokens: int = 768, system_prompt: str | None = DEFAULT_SYSTEM_PROMPT, digits: int = 6, symbol_docs: dict[str, str] | None = None, label: str = 'S') -> Item
```

The item for one example: the formula of this patient's branch and the values, to be substituted.

template: prompt text with placeholders {calculator_name}, {target}, {formula}, {values}, or the name of a
variant of TEMPLATES ("v1", "v2", "v3"); max_new_tokens: token
budget; system_prompt: None for none; digits: significant digits of the values shown (the expected
expression uses the same values); symbol_docs: {variable: description} overriding common.SYMBOL_DOCS;
label: the item's probe name.

```python
>>> item = build(mk.data.demo()[1], system_prompt=None)
>>> print(item["messages"][0]["content"])
Formula for Body Mass Index (BMI):
bmi = weight / (height / 100)^2
<BLANKLINE>
Variable values:
- weight = 70   (body weight (kg))
- height = 175   (height (cm))
...
```

### `probes.substitution.score`

```python
def score(item: Item, text: str, **options: Any) -> dict[str, Any]
```

Score a model answer for an S item. Options: equiv_rel_tol, value_rel_tol (see score_answer).

```python
>>> score(build(mk.data.demo()[2]), '{"expression": "na - (104 + 24)"}')["error_type"]
'unsubstituted_variable'
```

### `probes.substitution.score_answer`

```python
def score_answer(reference: dict[str, Any], text: str, *, equiv_rel_tol: float = 1e-06, value_rel_tol: float = 0.0001) -> dict[str, Any]
```

Score a model answer against an S reference ({"formula", "values", "gold_expression", "gold_value"}).

equiv_rel_tol: tolerance of the numerical equivalence test; value_rel_tol: tolerance of `value_matches`.

```python
>>> ref = build(mk.data.demo()[2])["reference"]
>>> score_answer(ref, '{"expression": "140 - (104 + 24)"}')
{'format_valid': True, 'correct': True, 'error_type': None, 'value_matches': True, 'missing_variables': [],
 'match': 'canonical'}
>>> score_answer(ref, '{"expression": "140 - 104 + 24"}')["error_type"]      # wrong structure
'structure_or_assignment_error'
```

### `probes.substitution.reference_answer`

```python
def reference_answer(item: Item) -> str
```

A correct answer: the expected substituted expression in the expected JSON format.

```python
>>> reference_answer(build(mk.data.demo()[2]))
'{"expression": "140 - (104 + 24)"}'
```

### `probes.substitution.TEMPLATES`

```python
TEMPLATES = {'v1': 'Formula for {calculator_name}:\n{target} = {formula}\n\nVariable values:\n{values}\n\nSubstitute the values into the formula. Do NOT compute or simplify anything: copy the formula exactly, replacing each variable by its value.\n\nEnd your answer with a JSON object of the form {"expression": "<formula with the values substituted>"}', 'v2': 'Here is the formula used for {calculator_name}:\n\ ...
```

### `probes.substitution.DEFAULT_TEMPLATE`

```python
DEFAULT_TEMPLATE = 'Formula for {calculator_name}:\n{target} = {formula}\n\nVariable values:\n{values}\n\nSubstitute the values into the formula. Do NOT compute or simplify anything: copy the formula exactly, replacing each variable by its value.\n\nEnd your answer with a JSON object of the form {"expression": "<formula with the values substituted>"}'
```


---

## `medcalc_kit.probes.arithmetic`

A — Arithmetic: can the model compute a fully written numerical expression?

Prompt: the expected answer of S (formula with the patient's values substituted). The model may work it out
step by step, then gives {"result": <number>}.
Scoring: relative error <= rel_tol (primary) and <= strict_rel_tol (reported as `correct_strict`).
Error types: format_invalid (no {"result": ...}), arithmetic_error.

```python
>>> item = build(mk.data.demo()[1])                         # BMI
>>> item["reference"]["expression"]
'70 / (175 / 100)^2'
>>> score(item, 'Step by step... {"result": 22.86}')["correct"]
True
```

### `probes.arithmetic.build`

```python
def build(example: Example | dict[str, Any], *, template: str = DEFAULT_TEMPLATE, max_new_tokens: int = 1024, system_prompt: str | None = DEFAULT_SYSTEM_PROMPT, digits: int = 6, label: str = 'A') -> Item
```

The item for one example: compute this patient's formula with the values already substituted.

template: prompt text with placeholder {expression}, or the name of a variant of TEMPLATES ("v1", "v2", "v3");
max_new_tokens: token budget; system_prompt: None for none;
digits: significant digits of the patient values inside the expression; label: the item's probe name.

```python
>>> item = build(mk.data.demo()[2], template='Compute {expression}. Reply {"result": <number>}.',
...              system_prompt=None)
>>> item["messages"]
[{'role': 'user', 'content': 'Compute 140 - (104 + 24). Reply {"result": <number>}.'}]
>>> item["reference"]
{'expression': '140 - (104 + 24)', 'gold_value': 12.0}
```

### `probes.arithmetic.score`

```python
def score(item: Item, text: str, **options: Any) -> dict[str, Any]
```

Score a model answer for an A item. Options: rel_tol (default 1 %), strict_rel_tol (default 0.1 %).

```python
>>> item = build(mk.data.demo()[2])
>>> score(item, '{"result": 12.1}')["correct"], score(item, '{"result": 12.1}', rel_tol=0.001)["correct"]
(True, False)
```

### `probes.arithmetic.score_answer`

```python
def score_answer(reference: dict[str, Any], text: str, *, rel_tol: float = 0.01, strict_rel_tol: float = 0.001) -> dict[str, Any]
```

Score a model answer against an A reference ({"expression", "gold_value"}).

```python
>>> score_answer({"expression": "1/3", "gold_value": 1 / 3}, '{"result": 0.333}')
{'format_valid': True, 'correct': True, 'correct_strict': True, 'error_type': None, 'rel_error': 0.000999...}
>>> score_answer({"expression": "1/3", "gold_value": 1 / 3}, '{"result": 0.33}')["correct_strict"]
False
```

### `probes.arithmetic.reference_answer`

```python
def reference_answer(item: Item) -> str
```

A correct answer: the gold value in the expected JSON format.

```python
>>> reference_answer(build(mk.data.demo()[2]))
'{"result": 12.0}'
```

### `probes.arithmetic.TEMPLATES`

```python
TEMPLATES = {'v1': 'Compute the value of the following expression (ln is the natural logarithm, log10 the base-10 logarithm, round(x, n) rounds x to n decimals, ^ is exponentiation):\n\n{expression}\n\nWork carefully without any tool. End your answer with a JSON object of the form {"result": <number with at least 4 significant digits>}', 'v2': 'Calculate the following expression without using any tool:\n\n{ex ...
```

### `probes.arithmetic.DEFAULT_TEMPLATE`

```python
DEFAULT_TEMPLATE = 'Compute the value of the following expression (ln is the natural logarithm, log10 the base-10 logarithm, round(x, n) rounds x to n decimals, ^ is exponentiation):\n\n{expression}\n\nWork carefully without any tool. End your answer with a JSON object of the form {"result": <number with at least 4 significant digits>}'
```


---

## `medcalc_kit.probes.end_to_end`

E2E — End to end: the original MedCalc-Bench task (note + question -> answer), for all 55 calculators.

Three kinds of answers, detected from the ground truth (`answer_type`):
- "number" (52 calculators): must fall within the benchmark's [Lower Limit, Upper Limit] interval, or, if
  `rel_tol` is given, within rel_tol of the ground truth;
- "date" (estimated due date, date of conception): the same calendar date (MM/DD/YYYY, YYYY-MM-DD or
  "September 11, 2014" are all read);
- "weeks_days" (estimated gestational age): the same number of weeks and days.

Error types: format_invalid (no readable {"answer": ...}), out_of_bounds (number), wrong_date, wrong_duration.

```python
>>> item = build(mk.data.demo()[2])                         # anion gap, ground truth 12
>>> score(item, '{"answer": 12.4}')["correct"], score(item, '{"answer": 13}')["error_type"]
(True, 'out_of_bounds')
```

### `probes.end_to_end.build`

```python
def build(example: Example | dict[str, Any], *, template: str = DEFAULT_TEMPLATE, max_new_tokens: int = 2048, system_prompt: str | None = DEFAULT_SYSTEM_PROMPT, label: str = 'E2E') -> Item
```

The item for one example: the patient note and the benchmark question. Works for every calculator of the
benchmark, including the rule-based scores and the date calculators.

template: prompt text with placeholders {note}, {question} and {answer_format}, or the name of a variant of
TEMPLATES ("v1", "v2", "v3"); max_new_tokens: token budget;
system_prompt: None for none; label: the item's probe name.

```python
>>> item = build(mk.data.demo()[2], max_new_tokens=512)
>>> item["max_new_tokens"], item["reference"]["ground_truth"], item["reference"]["answer_type"]
(512, 12.0, 'number')
>>> print(item["messages"][-1]["content"].splitlines()[-1])
Think step by step, then end your answer with a JSON object of the form {"answer": <number>}
```

### `probes.end_to_end.score`

```python
def score(item: Item, text: str, **options: Any) -> dict[str, Any]
```

Score a model answer for an E2E item. Options: rel_tol (replaces the benchmark interval, numbers only).

```python
>>> score(build(mk.data.demo()[2]), "The anion gap is 12 mEq/L.")["error_type"]   # JSON required
'format_invalid'
```

### `probes.end_to_end.score_answer`

```python
def score_answer(reference: dict[str, Any], text: str, *, rel_tol: float | None = None) -> dict[str, Any]
```

Score a model answer against an E2E reference ({"ground_truth", "lower", "upper", "answer_type"}).
`rel_error` is set for numbers, `error_days` (signed) for dates and durations.

```python
>>> ref = {"ground_truth": 100.0, "lower": 95.0, "upper": 105.0}
>>> score_answer(ref, '{"answer": "104 mL/min"}')
{'format_valid': True, 'correct': True, 'error_type': None, 'rel_error': 0.04}
>>> score_answer(ref, '{"answer": 104}', rel_tol=0.01)["correct"]
False
>>> ref = {"ground_truth": "06/16/2012", "lower": "06/16/2012", "upper": "06/16/2012", "answer_type": "date"}
>>> score_answer(ref, '{"answer": "06/23/2012"}')
{'format_valid': True, 'correct': False, 'error_type': 'wrong_date', 'error_days': 7}
```

### `probes.end_to_end.reference_answer`

```python
def reference_answer(item: Item) -> str
```

A correct answer: the ground truth in the expected JSON format.

```python
>>> reference_answer(build(mk.data.demo()[2]))
'{"answer": 12.0}'
```

### `probes.end_to_end.answer_type`

```python
def answer_type(ground_truth: float | str) -> str
```

"number", "date" or "weeks_days", from a ground truth.

```python
>>> answer_type(12.0), answer_type("09/11/2014"), answer_type("('16 weeks', '1 days')")
('number', 'date', 'weeks_days')
```

### `probes.end_to_end.parse_date`

```python
def parse_date(value: Any) -> date | None
```

A calendar date from a model answer, or None.

```python
>>> parse_date("09/11/2014"), parse_date("2014-09-11"), parse_date("September 11, 2014")
(datetime.date(2014, 9, 11), datetime.date(2014, 9, 11), datetime.date(2014, 9, 11))
>>> parse_date("The due date is 9/11/2014.")
datetime.date(2014, 9, 11)
```

### `probes.end_to_end.parse_weeks_days`

```python
def parse_weeks_days(value: Any) -> tuple[int, int] | None
```

(weeks, days) from a model answer: {"weeks": 16, "days": 1}, [16, 1], "(16 weeks, 1 day)"... or None.
Days beyond 6 are carried into weeks.

```python
>>> parse_weeks_days({"weeks": 16, "days": 1}), parse_weeks_days("('16 weeks', '1 days')")
((16, 1), (16, 1))
>>> parse_weeks_days([15, 8]), parse_weeks_days("3 weeks"), parse_weeks_days("soon")
((16, 1), (3, 0), None)
```

### `probes.end_to_end.TEMPLATES`

```python
TEMPLATES = {'v1': 'Patient note:\n{note}\n\nQuestion: {question}\n\nThink step by step, then end your answer with a JSON object of the form {"answer": {answer_format}}', 'v2': 'Here is a patient note.\n\n{note}\n\nAnswer this question about the patient: {question}\n\nReason step by step and finish with a JSON object {"answer": {answer_format}}', 'v3': '{note}\n\n{question}\n\nWork it out, then end with {"ans ...
```

### `probes.end_to_end.DEFAULT_TEMPLATE`

```python
DEFAULT_TEMPLATE = 'Patient note:\n{note}\n\nQuestion: {question}\n\nThink step by step, then end your answer with a JSON object of the form {"answer": {answer_format}}'
```

### `probes.end_to_end.ANSWER_FORMATS`

```python
ANSWER_FORMATS = {'number': '<number>', 'date': '"<MM/DD/YYYY>"', 'weeks_days': '{"weeks": <integer>, "days": <integer>}'}
```


---

## `medcalc_kit.probes.common`

Pieces shared by the probes: items, number presentation, variable documentation, resolved formulas.

An item is a JSON-serialisable dict (collections of items are DataFrames, one row per item, see items_frame):
    {"item_id", "example_id", "calculator_id", "calculator_name", "probe", "messages": [...],
     "max_new_tokens", "reference": {...}}           (+ "task" when the probe label differs from its task)
`messages` is the chat sent to the model; `reference` is everything the scorer needs. References are
derived from the executable calculator registry, never from an LLM.

Prompt texts are templates: `{name}` placeholders are replaced by `render`; any other text, including JSON
braces, is kept as is. Each probe documents its placeholders next to its DEFAULT_TEMPLATE.

### `probes.common.render`

```python
def render(template: str, **fields: Any) -> str
```

Replace the `{name}` placeholders whose name is given; leave every other brace untouched.

```python
>>> render('Compute {expression}, reply {"result": <number>} {unknown}', expression="1 + 1")
'Compute 1 + 1, reply {"result": <number>} {unknown}'
```

### `probes.common.resolve_template`

```python
def resolve_template(template: str | None, templates: dict[str, str]) -> tuple[str, str]
```

(name, text) of a template given by variant name ("v2"), by text, or None (the first variant). A text that
is not one of the variants is named "custom".

```python
>>> resolve_template("v2", {"v1": "A {x}", "v2": "B {x}"}), resolve_template("C {x}", {"v1": "A {x}"})
(('v2', 'B {x}'), ('custom', 'C {x}'))
```

### `probes.common.template_hash`

```python
def template_hash(template: str) -> str
```

Short hash of a template text, recorded in each item so that the exact prompt can be cited.

```python
>>> template_hash("Compute {expression}.")
'6366847ca0'
```

### `probes.common.fmt`

```python
def fmt(v: float, digits: int = 6) -> str
```

Presentation format for numbers shown to the model (`digits` significant digits).

```python
>>> fmt(70.0), fmt(1 / 3), fmt(1 / 3, digits=3), fmt(1.5e-7)
('70', '0.333333', '0.333', '1.5e-07')
```

### `probes.common.presented`

```python
def presented(v: float, digits: int = 6) -> float
```

The value as the model sees it (after fmt).

```python
>>> presented(1 / 3, digits=3)
0.333
```

### `probes.common.symbol_doc`

```python
def symbol_doc(name: str, entities: dict[str, Any], docs: dict[str, str] | None = None) -> str
```

Meaning and unit of a registry variable, as shown to the model. `docs` overrides SYMBOL_DOCS entries.

```python
>>> symbol_doc("scr", {})
'serum creatinine (mg/dL)'
>>> symbol_doc("scr", {}, docs={"scr": "creatinine in mg/dL"})
'creatinine in mg/dL'
```

### `probes.common.SYMBOL_DOCS`

```python
SYMBOL_DOCS = {'age': 'patient age (years)', 'weight': 'body weight (kg)', 'height': 'height (cm)', 'scr': 'serum creatinine (mg/dL)', 'scr_raw': 'serum creatinine (mg/dL)', 'ucr': 'urine creatinine (mg/dL)', 'na': 'serum sodium (mEq/L)', 'na_raw': 'serum sodium (mEq/L)', 'sna': 'serum sodium (mEq/L)', 'una': 'urine sodium (mEq/L)', 'cl': 'serum chloride (mEq/L)', 'hco3': 'serum bicarbonate (mEq/L)', 'albumin': ...
```

### `probes.common.task_question`

```python
def task_question(question: str) -> str
```

The benchmark question without the 'values at first admission' sentence.

```python
>>> task_question("What is the BMI? You should use the patient's medical values and health status when they "
...               "were first admitted to the hospital prior to any treatment.")
'What is the BMI?'
```

### `probes.common.categorical_context`

```python
def categorical_context(entities: dict[str, Any]) -> list[str]
```

Fixed categorical characteristics (sex, race, drugs...) as '- key: value' lines.

```python
>>> categorical_context({"sex": "Female", "age": [51, "years"], "smoker": True})
['- sex: Female', '- smoker: True']
```

### `probes.common.mme_drugs`

```python
def mme_drugs(entities: dict[str, Any]) -> dict[str, str]
```

tag -> drug name, consistent with the MME calculator's variable names (dose_<tag>, perday_<tag>).

```python
>>> mme_drugs({"OxyCODONE Dose": [10, "mg"], "OxyCODONE Dose Per Day": [2, "per day"]})
{'oxycodone': 'OxyCODONE'}
```

### `probes.common.inline`

```python
def inline(d: Derivation) -> expr.Node
```

Single expression of the resolved branch over the patient inputs (coefficients as constants).

```python
>>> expr.to_str(inline(derive("6", {"weight": [70, "kg"], "height": [175, "cm"]})))
'weight / (height / 100)^2'
```

### `probes.common.branch_formula`

```python
def branch_formula(example: Example, digits: int = 6) -> tuple[expr.Node, dict[str, float], Derivation]
```

(formula of this patient's branch, presented values of the variables it uses, derivation).

```python
>>> formula, values, d = branch_formula(mk.data.demo()[2])
>>> expr.to_str(formula), values
('na - (cl + hco3)', {'na': 140.0, 'cl': 104.0, 'hco3': 24.0})
```

### `probes.common.make_item`

```python
def make_item(example: Example, probe: str, user: str, reference: dict[str, Any], max_new_tokens: int, system_prompt: str | None = DEFAULT_SYSTEM_PROMPT, task: str | None = None, template: tuple[str, str] | None = None) -> Item
```

Assemble an item (used by every probe's build). task: the probe that scores this item when `probe` is a
custom label (e.g. two K variants "K", "Kg"). template: (name, text) of the template used, recorded as
`template` (its name) and `template_hash`.

```python
>>> item = make_item(mk.data.demo()[1], "A", "Compute 1 + 1", {"gold_value": 2.0}, 64, system_prompt=None)
>>> item["item_id"], item["messages"]
('demo:6:1:A', [{'role': 'user', 'content': 'Compute 1 + 1'}])
```

### `probes.common.numeric_answer`

```python
def numeric_answer(text: str, key: str) -> float | None
```

The number under `key` in the last JSON object of the text.

```python
>>> numeric_answer('Thinking... {"result": "12.5 mEq/L"}', "result")
12.5
```

### `probes.common.rel_close`

```python
def rel_close(a: float, b: float, tol: float) -> bool
```

|a - b| <= tol * |b| (b is the reference).

```python
>>> rel_close(101, 100, 0.01), rel_close(102, 100, 0.01)
(True, False)
```

### `probes.common.DEFAULT_SYSTEM_PROMPT`

```python
DEFAULT_SYSTEM_PROMPT = 'You are a careful clinical calculation assistant.'
```

### `probes.common.DEFAULT_DIGITS`

```python
DEFAULT_DIGITS = 6
```


---

## `medcalc_kit.generation`

Running models on probe items: backend-agnostic runner, generation-artifact classification, HF backend.

The Hugging Face backend needs the optional dependencies (pip install medcalc-kit[hf]):
```python
>>> from medcalc_kit.generation.hf import HFBackend
```

### `generation.run_items`

```python
def run_items(items: pd.DataFrame | Iterable[dict[str, Any]], out_path: str | Path, model: Any = None, model_id: str | None = None, meta: dict[str, Any] | None = None, on_record: Callable[[dict[str, Any]], None] | None = None, generate_batch: GenerateBatchFn | None = None, batch_size: int = 1) -> int
```

Generate an answer for every item not yet in `out_path` and append one JSON record per item (resumable:
run it again after an interruption). Returns the number of records written.

model:          an object with `generate_batch(list_of_messages, max_new_tokens)` (e.g. HFBackend) or
                `generate(messages, max_new_tokens)`, or such a function. `generate` returns the text or
                (text, n_prompt_tokens, n_new_tokens); without token counts, truncation cannot be detected.
model_id:       recorded in each record (default: the backend's `model_id`, else the function's name).
meta:           extra information stored in every record (decoding settings, seed...).
on_record:      called with each record as it is written (progress bars, logging).
generate_batch: a batch function, instead of `model`.
batch_size:     prompts generated together (same token budget, similar lengths).

```python
>>> import tempfile, pathlib
>>> out = pathlib.Path(tempfile.mkdtemp()) / "outputs.jsonl"
>>> items = mk.ProbeSuite(["A"]).build(mk.data.demo())
>>> def always_12(messages, max_new_tokens):
...     return '{"result": 12}'
>>> run_items(items, out, always_12)
4
>>> run_items(items, out, always_12)                        # already done: nothing to generate
0
>>> records = read_records(out)                             # one row per item (in generation order)
>>> len(records), records.loc[0, "model_id"], records.loc[0, "text"]
(4, 'always_12', '{"result": 12}')
```

### `generation.read_records`

```python
def read_records(path: str | Path) -> pd.DataFrame
```

The generation records of an output file, one row per record; `meta` is flattened into `meta.<key>`
columns. A line truncated by an interruption is skipped. Empty DataFrame if the file does not exist.

Columns: item_id, example_id, calculator_id, probe, model_id, prompt_key, shared_generation, text,
n_prompt_tokens, n_new_tokens, truncated, seconds, batch_size, error, timestamp, meta.<key>...

```python
>>> df = read_records("outputs.jsonl")
>>> df[["item_id", "text", "n_new_tokens"]]
```

### `generation.done_item_ids`

```python
def done_item_ids(out_path: str | Path) -> set[str]
```

item_ids already present in an output file (successful generations only): what `run_items` skips.

```python
>>> done_item_ids("does-not-exist.jsonl")
set()
```

### `generation.prompt_key`

```python
def prompt_key(messages: Messages, max_new_tokens: int) -> str
```

Short hash identifying a prompt (messages + token budget): items with the same key get the same answer.

```python
>>> prompt_key([{"role": "user", "content": "2 + 2 = ?"}], 64)
'14ce2533d1765515'
```

### `generation.model_name`

```python
def model_name(model: Any) -> str
```

The id recorded for a model: its `model_id` attribute, else its (function) name.

```python
>>> def my_model(messages, max_new_tokens): ...
>>> model_name(my_model)
'my_model'
```

### `generation.classify_generation`

```python
def classify_generation(text: str, n_new_tokens: int, max_new_tokens: int, format_valid: bool, **degenerate_options) -> str
```

Category of a generation, in this order: empty, truncated (the token budget is used up), degenerate (see
is_degenerate), format_invalid (the probe found no answer in the expected format), well_formed.
degenerate_options: ngram, repeat_share, line_repeats, min_words (see is_degenerate).

```python
>>> classify_generation("The result is 12.", 6, 512, format_valid=False)
'format_invalid'
```

### `generation.is_degenerate`

```python
def is_degenerate(text: str, ngram: int = 4, repeat_share: float = 0.5, line_repeats: int = 3, min_words: int = 40) -> bool
```

True if the text loops: a line repeated `line_repeats` times, or (for texts of at least `min_words` words)
more than `repeat_share` of its word `ngram`s are repeats.

```python
>>> is_degenerate("the value is " * 30), is_degenerate("The anion gap is 140 - (104 + 24) = 12.")
(True, False)
```

### `generation.CATEGORIES`

```python
CATEGORIES = ('empty', 'truncated', 'degenerate', 'format_invalid', 'well_formed')
```


---

## `medcalc_kit.generation.artifacts`

Classify each generation as a generation artifact or a well-formed answer.

Categories are exclusive and checked in this order:
    empty -> truncated -> degenerate -> format_invalid -> well_formed
A competence is best measured on well-formed answers only; the others are reported as artifact rates
(compressed or small models often produce empty, cut-off or looping text). Thresholds are arguments.

```python
>>> classify_generation("", 0, 512, format_valid=False)
'empty'
>>> classify_generation("I think " * 200, 512, 512, format_valid=False)
'truncated'
>>> classify_generation('{"result": 12}', 8, 512, format_valid=True)
'well_formed'
```

### `generation.artifacts.repeated_ngram_share`

```python
def repeated_ngram_share(text: str, n: int = 4) -> float
```

Share of word n-grams that are repeats of an earlier n-gram (0 = no repetition).

```python
>>> repeated_ngram_share("a b c d e f"), repeated_ngram_share("a b a b a b a b", n=2)
(0.0, 0.7142857142857143)
```

### `generation.artifacts.max_line_repeats`

```python
def max_line_repeats(text: str) -> int
```

How many times the most repeated line (of at least 8 characters) occurs.

```python
>>> max_line_repeats("Step 1: compute\nStep 1: compute\nStep 1: compute\ndone")
3
```


---

## `medcalc_kit.generation.hf`

Hugging Face transformers backend (optional dependency: pip install medcalc-kit[hf]).

### `generation.hf.HFBackend`

```python
class HFBackend(model_id: str, device: str = 'cuda:0', dtype: str = 'bfloat16', chat_template_kwargs: dict[str, Any] | None = None)
```

Loads a causal LM on one device and generates greedily with its chat template (left padding for
batches). chat_template_kwargs: e.g. {"enable_thinking": False} for Qwen3. Needs `pip install medcalc-kit[hf]`.

```python
>>> from medcalc_kit.generation.hf import HFBackend
>>> model = HFBackend("Qwen/Qwen2.5-3B-Instruct", device="cuda:0")
>>> model.generate([{"role": "user", "content": "2 + 2 = ?"}], max_new_tokens=16)
('2 + 2 = 4', 32, 8)
>>> mk.run_items(items, "outputs.jsonl", model, batch_size=16)
```

#### `.generate_batch(self, batch: list[Messages], max_new_tokens: int) -> list[tuple[str, int, int]]`

Greedy answers for several chats: [(text, n_prompt_tokens, n_new_tokens), ...].

#### `.generate(self, messages: Messages, max_new_tokens: int) -> tuple[str, int, int]`

Greedy answer for one chat: (text, n_prompt_tokens, n_new_tokens).

#### `.run_items(self, items, out_path, meta=None, on_record=None, batch_size: int = 1) -> int`

`generation.run_items` with this model; decoding settings are added to each record's meta.


---

## `medcalc_kit.evaluate`

Score model answers and summarise them per probe.

```python
>>> from medcalc_kit import evaluate, probes
>>> items = mk.ProbeSuite(["A", "E2E"]).build(mk.data.demo())
>>> answers = pd.DataFrame({"item_id": items.item_id,                  # any answers you collected
...                         "text": [probes.reference_answer(it) for _, it in items.iterrows()]})
>>> answers.loc[0, "text"] = '{"result": 1}'                           # one wrong answer
>>> df = evaluate.score_records(answers, items)                       # one row per answer
>>> df[["item_id", "category", "correct"]].head(3)
       item_id     category  correct
0   demo:2:1:A  well_formed    False
1   demo:6:1:A  well_formed     True
2  demo:39:1:A  well_formed     True
>>> df.loc[0, "error_type"]
'arithmetic_error'
>>> evaluate.summary(df)
       n_units  well_formed  competence  overall
probe
A          4.0          1.0        0.75     0.75
E2E        4.0          1.0        1.00     1.00
```

### `evaluate.score_records`

```python
def score_records(records: pd.DataFrame | Iterable[dict[str, Any]] | str | Path, items: pd.DataFrame | Iterable[dict[str, Any]] | dict[str, Any], condition: dict[str, Any] | None = None, scoring: dict[str, dict[str, Any]] | None = None, artifacts: dict[str, Any] | None = None, details: bool = False) -> pd.DataFrame
```

Score model answers: one row per answer, with its artifact category, correctness (only well-formed answers
can be correct) and error type (for an empty, truncated or looping answer: that category).

records:    the answers: the output file of `run_items` (path), its DataFrame (`read_records`), or any
            DataFrame / list of dicts with at least `item_id` and `text`. `n_new_tokens` (to detect truncated
            answers) and `error` are used when present; records with an error are skipped. A record's own
            `max_new_tokens` (set by truncate_records) replaces the item's budget.
items:      the items answered (DataFrame, list or {item_id: item}).
condition:  constant columns to add, e.g. {"model": "qwen2.5-7b"} to compare models later.
scoring:    score() options per probe label or task, e.g. {"K": {"case_semantics": "first_match"}}.
artifacts:  options of generation.is_degenerate (ngram, repeat_share, line_repeats, min_words).
details:    also return the answer `text` and the full `verdict` dict (e.g. per-field results for E).

```python
>>> items = mk.ProbeSuite(["A"]).build(mk.data.demo())
>>> recs = [{"item_id": "demo:6:1:A", "text": '{"result": 22.857}', "n_new_tokens": 12},
...         {"item_id": "demo:2:1:A", "text": "", "n_new_tokens": 0}]
>>> score_records(recs, items, condition={"model": "m1"})[["model", "item_id", "category", "correct"]]
  model     item_id     category  correct
0    m1  demo:6:1:A  well_formed     True
1    m1  demo:2:1:A        empty    False
>>> score_records(recs, items, details=True).loc[0, "verdict"]["rel_error"] < 1e-4
True
```

### `evaluate.summary`

```python
def summary(df: pd.DataFrame, by: Iterable[str] = ('probe',), collapse: Iterable[str] = ('K',)) -> pd.DataFrame
```

Per group (default: per probe): number of units, share of well-formed answers, accuracy among well-formed
answers ('competence') and overall accuracy. Tasks in `collapse` are counted once per distinct prompt
(see to_units). Group by condition columns to compare, e.g. by=("model", "probe").

```python
>>> df = pd.DataFrame({"model": ["m1", "m1", "m2", "m2"], "probe": "A", "example_id": ["a", "b", "a", "b"],
...                    "calculator_id": "6", "prompt_key": ["p", "q", "p", "q"],
...                    "correct": [True, False, True, True], "well_formed": [True, False, True, True],
...                    "category": "well_formed"})
>>> summary(df, by=("model", "probe"))
             n_units  well_formed  competence  overall
model probe
m1    A          2.0          0.5         1.0      0.5
m2    A          2.0          1.0         1.0      1.0
```

### `evaluate.to_units`

```python
def to_units(df: pd.DataFrame, keys: Iterable[str] = ('model', 'method', 'sparsity', 'seed'), collapse: Iterable[str] = ('K',)) -> pd.DataFrame
```

One row per analysis unit. Items of the `collapse` tasks that share a prompt collapse to that prompt (mean
correctness): identical prompts get identical greedy answers, so they are one observation (K in "general"
mode repeats its prompt across the examples of a calculator). Every other item is one unit.
keys: condition columns kept (those present), so that conditions are never mixed.

```python
>>> df = pd.DataFrame({"probe": ["K", "K", "A"], "calculator_id": "6", "example_id": ["a", "b", "a"],
...                    "prompt_key": ["p", "p", "q"], "correct": [True, True, False],
...                    "well_formed": True, "category": "well_formed"})
>>> to_units(df)[["probe", "unit", "correct"]]
  probe unit  correct
0     A    a      0.0
1     K    p      1.0
```

### `evaluate.read_jsonl`

```python
def read_jsonl(path: str | Path) -> list[dict[str, Any]]
```

Records as a list of dicts (generation.read_records gives a DataFrame).


---

## `medcalc_kit.expr`

Safe arithmetic expression parser and evaluator.

LLM outputs are never passed to eval()/sympy.parse_expr (which uses eval). This module
implements a small recursive-descent parser over a whitelisted grammar:

    expr   := term (('+' | '-') term)*
    term   := unary (('*' | '/') unary)*
    unary  := ('+' | '-') unary | power
    power  := atom (('^' | '**') unary)?          # right-associative, binds tighter than unary minus on its left
    atom   := NUMBER | NAME | NAME '(' expr (',' expr)* ')' | '(' expr ')'

Only the functions in FUNCTIONS are callable. Names are variables resolved from an environment.

```python
>>> from medcalc_kit import expr
>>> expr.evaluate("weight / (height / 100)^2", {"weight": 70, "height": 175})
22.857142857142858
>>> expr.evaluate("__import__('os').system('ls')")      # never executed: not in the grammar
Traceback (most recent call last):
...
medcalc_kit.expr.ExprError: unexpected character "'" at position 11
```

### `expr.evaluate`

```python
def evaluate(node: Node | str, env: Mapping[str, float] | None = None) -> float
```

Evaluate an AST (or expression string) with variables from env. Raises ExprError.

```python
>>> evaluate("sqrt(x) + max(1, 2, 3)", {"x": 16})
7.0
>>> evaluate("1 / x", {"x": 0})
Traceback (most recent call last):
...
medcalc_kit.expr.ExprError: evaluation error: float division by zero
```

### `expr.parse`

```python
def parse(text: str) -> Node
```

Parse an expression string into an AST. Raises ExprError. `^` and `**` are powers; `×`, `÷`, `−` accepted.

```python
>>> parse("2 * x + 1")
BinOp(op='+', left=BinOp(op='*', left=Num(value=2.0), right=Var(name='x')), right=Num(value=1.0))
```

### `expr.variables`

```python
def variables(node: Node | str) -> set[str]
```

Free variable names of an expression.

```python
>>> sorted(variables("(140 - age) * weight / (72 * scr)"))
['age', 'scr', 'weight']
```

### `expr.substitute`

```python
def substitute(node: Node | str, env: Mapping[str, float]) -> Node
```

Replace variables present in env by numeric literals (other variables are kept).

```python
>>> to_str(substitute("a * x + b", {"a": 2, "b": 3}))
'2 * x + 3'
```

### `expr.replace_vars`

```python
def replace_vars(node: Node | str, mapping: Mapping[str, Node]) -> Node
```

Replace variables by sub-expressions (used to inline multi-step derivations).

```python
>>> to_str(replace_vars("bmi * 2", {"bmi": parse("w / h^2")}))
'w / h^2 * 2'
```

### `expr.to_str`

```python
def to_str(node: Node) -> str
```

Render an AST back to a canonical string with minimal parentheses.

```python
>>> to_str(parse("((a + b)) * (c)"))
'(a + b) * c'
```

### `expr.canonical`

```python
def canonical(node: Node | str, sig: int = 10) -> tuple
```

Order-insensitive structural key: flattens +/- and * / chains, sorts commutative operands,
folds unary minus on literals. Two expressions with equal keys are identical up to
commutativity/associativity of + and *, and a - (b + c) == a - b - c style regrouping.

```python
>>> canonical("a - (b + c)") == canonical("a - c - b")
True
>>> canonical("a / b") == canonical("b / a")
False
```

### `expr.evaluate_condition`

```python
def evaluate_condition(text: str | None, env: Mapping[str, float]) -> bool
```

Evaluate 'a <= x < b and y > 3 or ...' (chained comparisons, and/or; no parentheses).

Empty / 'always' conditions are true. 'otherwise' must be handled by the caller.

```python
>>> evaluate_condition("18.5 <= bmi < 25", {"bmi": 22})
True
>>> evaluate_condition("age > 65 or scr >= 1.5", {"age": 40, "scr": 1.2})
False
```

### `expr.literals`

```python
def literals(node: Node) -> list[float]
```

Numeric literals in left-to-right order.

```python
>>> literals(parse("140 - (104 + 24)"))
[140.0, 104.0, 24.0]
```

### `expr.map_literals`

```python
def map_literals(node: Node, fn: Callable[[int, float], Node]) -> Node
```

Rebuild the tree replacing the i-th literal (left-to-right) by fn(i, value).

```python
>>> to_str(map_literals(parse("140 - (104 + 24)"), lambda i, v: Var(["na", "cl", "hco3"][i])))
'na - (cl + hco3)'
```

### `expr.ExprError`

```python
class ExprError
```

Raised for any syntax or evaluation error.

### `expr.FUNCTIONS`

```python
FUNCTIONS = {'sqrt': (<built-in function sqrt>, 1), 'ln': (<built-in function log>, 1), 'log': (<built-in function log>, 1), 'log10': (<built-in function log10>, 1), 'exp': (<built-in function exp>, 1), 'abs': (<built-in function abs>, 1), 'min': (<built-in function min>, None), 'max': (<built-in function max>, None), 'round': (<function <lambda>>, None)}
```


---

## `medcalc_kit.units`

Unit normalisation for MedCalc-Bench entity annotations.

Annotations come as [value, unit] (or [v1, u1, v2, u2] for composite heights/ages).
Constants (molar masses, valences, conversion factors) follow the reference MedCalc-Bench
implementation (ncbi-nlp/MedCalc-Bench, calculator_implementations/) so that our registry
reproduces the benchmark's conventions; deviations are documented in medcalc_kit.calculators.

```python
>>> from medcalc_kit import units
>>> round(units.concentration(88.4, "µmol/L", "creatinine", "mg/dL"), 3)
1.0
>>> units.height_cm([5, "ft", 10, "in"])
177.8
```

### `units.concentration`

```python
def concentration(value: float, unit: str, analyte: str, target: str) -> float
```

Convert a concentration between {g, mol, Eq}-per-volume units.

g <-> mol uses MOLAR_MASS[analyte]; mol <-> Eq uses VALENCE[analyte].

```python
>>> concentration(2.5, "mmol/L", "calcium", "mg/dL")
10.02
>>> concentration(140, "mmol/L", "sodium", "mEq/L")
140.0
```

### `units.clean_unit`

```python
def clean_unit(unit: str) -> str
```

Normalise unit spelling: micro sign variants, broken escapes, spacing, case of mm Hg, and
case / plural variants of known components ('mg/dl' -> 'mg/dL', 'meq/l' -> 'mEq/L', 'inches' -> 'in').

```python
>>> clean_unit("mg/dl"), clean_unit("meq/l"), clean_unit("mm hg"), clean_unit("inches")
('mg/dL', 'mEq/L', 'mm Hg', 'in')
```

### `units.weight_kg`

```python
def weight_kg(entity: list[Any]) -> float
```

Weight annotation [value, unit] in kg (kg, lbs, g).

```python
>>> weight_kg([154, "lbs"])
69.853168
```

### `units.height_cm`

```python
def height_cm(entity: list[Any]) -> float
```

Height annotation in cm: [value, unit] (cm, m, in, ft) or [feet, 'ft', inches, 'in'].

```python
>>> height_cm([1.75, "m"]), height_cm([69, "inches"])
(175.0, 175.26)
```

### `units.age_years`

```python
def age_years(entity: list[Any]) -> float
```

Benchmark convention: integer years; months//12, weeks//52, days -> 0.

For composite ages ([2, 'years', 11, 'months']) the first year component is used.

```python
>>> age_years([51, "years"]), age_years([30, "months"]), age_years([2, "years", 11, "months"])
(51.0, 2.0, 2.0)
```

### `units.platelets_1e9_per_L`

```python
def platelets_1e9_per_L(entity: list[Any]) -> float
```

Platelet count expressed in 10^9/L (count per volume unit -> per litre).

Accepts 'µL', '/µL', 'cells/µL', '10^3/µL', 'x10^9/L', 'K/µL'.

```python
>>> platelets_1e9_per_L([250, "10^3/µL"]), platelets_1e9_per_L([250000, "/µL"])
(250.0, 250.0)
```

### `units.insulin_uIU_per_mL`

```python
def insulin_uIU_per_mL(entity: list[Any]) -> float
```

Insulin in µIU/mL. Clinically correct conversion: 1 µIU/mL = 6 pmol/L (the reference implementation
multiplies by 6, see calculators.KNOWN_REFERENCE_DEVIATIONS).

```python
>>> insulin_uIU_per_mL([60, "pmol/L"])
10.0
```

### `units.UnitError`

```python
class UnitError
```

Raised for an unknown or unconvertible unit.

### `units.MOLAR_MASS`

```python
MOLAR_MASS = {'creatinine': 113.12, 'sodium': 22.99, 'chloride': 35.45, 'bicarbonate': 61.02, 'glucose': 180.16, 'bun': 28.02, 'calcium': 40.08, 'cholesterol': 386.654, 'triglycerides': 861.338, 'albumin': 66500.0}
```


---

## `medcalc_kit.parsing`

Deterministic extraction of structured answers from raw model text.

```python
>>> from medcalc_kit import parsing
>>> parsing.extract_json('Let me think... the answer is {"answer": "79.9 mL/min"}.')
{'answer': '79.9 mL/min'}
>>> parsing.to_number("79.9 mL/min")
79.9
```

### `parsing.extract_json`

```python
def extract_json(text: str) -> Any | None
```

Return the LAST valid JSON object/array in the text (fenced blocks preferred), else None.

```python
>>> extract_json('First {"a": 1}, then {"a": 2}')
{'a': 2}
>>> extract_json("no JSON here") is None
True
```

### `parsing.to_number`

```python
def to_number(value: Any) -> float | None
```

Coerce a JSON value to float: numbers, or strings like '79.9 mL/min', '1,234.5'. Else None.

```python
>>> to_number(12), to_number("1,234.5"), to_number("about -3e2 units"), to_number(True)
(12.0, 1234.5, -300.0, None)
```
