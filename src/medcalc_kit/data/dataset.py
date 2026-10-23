"""Loading MedCalc-Bench-Verified at a pinned revision, as a filterable collection of examples.

    >>> from medcalc_kit import data
    >>> ds = data.load(equation_only=True)              # doctest: +SKIP
    >>> ds = data.demo()                                # 4 hand-written examples, no download
    >>> ds
    MedCalcDataset(4 examples, 4 calculators; demo: 4)
    >>> ds[0].calculator_name
    'Creatinine Clearance (Cockcroft-Gault Equation)'
"""
from __future__ import annotations

import ast
import json
import math
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

DATASET_ID = "nsk7153/MedCalc-Bench-Verified"
# Revision used by default (the one the registry was verified against); pass another SHA to change it.
DEFAULT_REVISION = "58fc3de568bfc53a68f32327e58f60dc6eaa17f8"
# Categories whose calculators are closed-form equations (excludes 'date' and rule-based scores).
EQUATION_CATEGORIES = ("lab test", "physical", "dosage")


def dataset_revision(dataset_id: str = DATASET_ID) -> str:
    """Current commit SHA of the dataset on the Hugging Face Hub (needs network access).

    Pin the result for reproducibility: `load(revision=...)` then always reads the same data.

    >>> data.dataset_revision()                         # doctest: +SKIP
    '58fc3de568bfc53a68f32327e58f60dc6eaa17f8'
    """
    from huggingface_hub import HfApi

    return HfApi().dataset_info(dataset_id).sha


def parse_entities(raw: str) -> dict[str, Any]:
    """Parse a "Relevant Entities" annotation: JSON or a Python-literal dict (literal_eval never executes code).

    >>> parse_entities('{"weight": [70, "kg"]}')
    {'weight': [70, 'kg']}
    >>> parse_entities("{'sex': 'Male', 'smoker': True}")
    {'sex': 'Male', 'smoker': True}
    """
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return ast.literal_eval(raw)


def load_dataframe(revision: str = DEFAULT_REVISION, splits: tuple[str, ...] = ("train", "test"),
                   dataset_id: str = DATASET_ID) -> pd.DataFrame:
    """The raw table, one row per example (original column names), plus parsed `entities`, a `split` column and
    a stable `example_id` ("<split>:<calculator id>:<row number>"). Most users want `load` instead.

    >>> df = data.load_dataframe(splits=("test",))      # doctest: +SKIP
    >>> df[["example_id", "Calculator Name", "Ground Truth Answer"]].head(2)   # doctest: +SKIP
    """
    from datasets import load_dataset

    ds = load_dataset(dataset_id, revision=revision)
    frames = [ds[s].to_pandas().assign(split=s) for s in splits]
    df = pd.concat(frames, ignore_index=True)
    df["Calculator ID"] = df["Calculator ID"].astype(str)
    df["Note ID"] = df["Note ID"].astype(str)
    df["entities"] = df["Relevant Entities"].map(parse_entities)
    # Stable example identifier used everywhere for paired comparisons.
    df["example_id"] = df["split"] + ":" + df["Calculator ID"] + ":" + df["Row Number"].astype(str)
    return df


def equation_subset(df: pd.DataFrame, categories: Iterable[str] = EQUATION_CATEGORIES) -> pd.DataFrame:
    """Rows of the closed-form (equation-based) calculators, or of the given `categories`.

    >>> len(equation_subset(data.demo().df))
    4
    >>> len(equation_subset(data.demo().df, categories=["lab test"]))
    2
    """
    return df[df["Category"].isin(list(categories))].copy()


@dataclass(frozen=True, repr=False)
class Example:
    """One benchmark example: a patient note, a question and the annotated input values (`entities`).

    `entities` maps each input to its annotation, e.g. {"age": [51, "years"], "sex": "Female"}; quantities are
    [value, unit]. `ground_truth` must fall in [lower, upper] for an answer to count as correct. For the date
    calculators, `ground_truth` is a string (a date "MM/DD/YYYY", or "('16 weeks', '1 days')") and lower = upper.

    >>> ex = data.demo()[0]
    >>> ex
    Example('demo:2:1', calculator 2 'Creatinine Clearance (Cockcroft-Gault Equation)', ground truth 79.88)
    >>> ex.entities["weight"]
    [68.6, 'kg']
    """
    example_id: str
    split: str
    calculator_id: str
    calculator_name: str
    category: str
    note: str
    question: str
    entities: dict[str, Any]
    ground_truth: float | str
    lower: float | str
    upper: float | str
    note_id: str = ""
    note_type: str = ""
    explanation: str = ""

    def __repr__(self) -> str:
        return (f"Example({self.example_id!r}, calculator {self.calculator_id} {self.calculator_name!r}, "
                f"ground truth {_show(self.ground_truth)})")

    @classmethod
    def from_row(cls, row: dict[str, Any] | pd.Series) -> Example:
        """From a dataset row (original column names). Only example_id, Calculator ID and entities are required:
        the other columns may be absent in hand-made examples (probes that need them will then be empty).

        >>> ex = Example.from_row({"example_id": "my:6:1", "Calculator ID": "6",
        ...                        "entities": {"weight": [70, "kg"], "height": [175, "cm"]}})
        >>> round(ex.derive().answer, 2)
        22.86
        """
        def get(key: str, default: Any = "") -> Any:
            value = row.get(key, default)
            return default if isinstance(value, float) and math.isnan(value) and default == "" else value

        lo, hi = _answer(row.get("Lower Limit", math.nan)), _answer(row.get("Upper Limit", math.nan))
        if isinstance(lo, float) and isinstance(hi, float):
            lo, hi = sorted((lo, hi))
        return cls(
            example_id=row["example_id"], split=get("split"),
            calculator_id=str(row["Calculator ID"]), calculator_name=get("Calculator Name"),
            category=get("Category"), note=get("Patient Note"), question=get("Question"),
            entities=row["entities"], ground_truth=_answer(row.get("Ground Truth Answer", math.nan)),
            lower=lo, upper=hi,
            note_id=str(get("Note ID")), note_type=get("Note Type"),
            explanation=get("Ground Truth Explanation"),
        )

    def derive(self):
        """Reference computation by the calculator registry (see `medcalc_kit.calculators.derive`).

        >>> d = data.demo()[0].derive()
        >>> d.branches, round(d.answer, 2)
        (['ibw:female', 'bmi>24.9:abw'], 79.88)
        """
        from medcalc_kit.calculators import derive

        return derive(self.calculator_id, self.entities)


def _answer(value: Any) -> float | str:
    """Numeric answers as float; dates and durations stay strings."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return str(value).strip()


def _show(value: float | str) -> str:
    return f"{value:.4g}" if isinstance(value, float) else repr(value)


def as_example(x: Example | dict[str, Any] | pd.Series) -> Example:
    """An Example from an Example (returned as is), a dataset row (Series) or a dict with the dataset's columns.

    >>> as_example(data.demo().df.iloc[1]).calculator_id
    '6'
    """
    return x if isinstance(x, Example) else Example.from_row(x)


def _as_list(value: Any) -> list | None:
    if value is None:
        return None
    return [value] if isinstance(value, (str, int)) else list(value)


class MedCalcDataset:
    """A collection of examples backed by a DataFrame (`.df`, original column names, plus `entities`, `split` and
    `example_id`). Every method returns a new dataset; the original is never modified.

    Iterating yields `Example`s; `ds[i]` is the i-th example, `ds["test:2:9"]` the example with that id. The `split`
    column is free: besides the benchmark's "train" and "test", create any split with `split_off`, `folds`,
    `assign_split` or `with_splits`. An `example_id` never changes, so its prefix keeps the original split.

    >>> ds = data.demo()
    >>> ds
    MedCalcDataset(4 examples, 4 calculators; demo: 4)
    >>> len(ds), ds.example_ids[:2]
    (4, ['demo:2:1', 'demo:6:1'])
    >>> [ex.calculator_id for ex in ds]
    ['2', '6', '39', '5']
    """

    def __init__(self, df: pd.DataFrame):
        self.df = df.reset_index(drop=True)

    def __len__(self) -> int:
        return len(self.df)

    def __iter__(self) -> Iterator[Example]:
        for _, row in self.df.iterrows():
            yield Example.from_row(row)

    def __getitem__(self, key: int | str) -> Example:
        """Position (int) or example_id (str)."""
        if isinstance(key, str):
            rows = self.df[self.df["example_id"] == key]
            if rows.empty:
                raise KeyError(key)
            return Example.from_row(rows.iloc[0])
        return Example.from_row(self.df.iloc[key])

    def __add__(self, other: MedCalcDataset) -> MedCalcDataset:
        return concat(self, other)

    def __repr__(self) -> str:
        counts = self.df["split"].value_counts(sort=False) if len(self) else {}
        splits = ", ".join(f"{k}: {v}" for k, v in dict(counts).items())
        return f"MedCalcDataset({len(self)} examples, {self.df['Calculator ID'].nunique()} calculators; {splits})"

    # ------------------------------------------------------------------ selecting

    def filter(self, calculator: str | int | Iterable[str | int] | None = None,
               category: str | Iterable[str] | None = None, split: str | Iterable[str] | None = None,
               note_type: str | Iterable[str] | None = None,
               where: Callable[[pd.DataFrame], Any] | None = None) -> MedCalcDataset:
        """Examples matching every given criterion. Each criterion takes one value or a list: calculator id(s),
        category ("lab test", "physical", "dosage", "risk", "severity", "diagnosis", "date"), split, note type
        ("Extracted", "Synthetic"...). `where` is any condition on the DataFrame: a function df -> boolean mask.

        >>> ds = data.demo(3)
        >>> ds.filter(calculator=[2, "6"]).calculators()[["Calculator ID", "demo"]]
          Calculator ID  demo
        0             2     3
        1             6     3
        >>> len(ds.filter(category=["lab test", "physical"]))
        12
        >>> ds.filter(where=lambda df: df["Ground Truth Answer"] > 100).example_ids
        ['demo:5:1', 'demo:5:2', 'demo:5:3']
        """
        df = self.df
        for column, value in (("Calculator ID", calculator), ("Category", category), ("split", split),
                              ("Note Type", note_type)):
            values = _as_list(value)
            if values is not None:
                df = df[df[column].isin([str(v) for v in values])]
        if where is not None:
            df = df[where(df)]
        return MedCalcDataset(df)

    def select(self, example_ids: Iterable[str]) -> MedCalcDataset:
        """The given examples, in the given order.

        >>> data.demo().select(["demo:39:1", "demo:2:1"]).example_ids
        ['demo:39:1', 'demo:2:1']
        """
        return MedCalcDataset(self.df.set_index("example_id").loc[list(example_ids)].reset_index())

    def sample(self, n: int, seed: int = 0, per_calculator: bool = False) -> MedCalcDataset:
        """`n` random examples (reproducible with `seed`); per_calculator=True takes up to `n` per calculator.
        Handy to try a model on a small subset first.

        >>> len(data.demo().sample(2))
        2
        >>> data.demo().sample(1, per_calculator=True).example_ids
        ['demo:2:1', 'demo:6:1', 'demo:39:1', 'demo:5:1']
        """
        if per_calculator:
            df = pd.concat([g.sample(min(n, len(g)), random_state=seed)
                            for _, g in self.df.groupby("Calculator ID", sort=False)])
        else:
            df = self.df.sample(min(n, len(self.df)), random_state=seed)
        return MedCalcDataset(df)

    def equation_only(self) -> MedCalcDataset:
        """Only the closed-form (equation-based) calculators (see EQUATION_CATEGORIES).

        >>> len(data.demo().equation_only())
        4
        """
        return MedCalcDataset(equation_subset(self.df))

    @property
    def example_ids(self) -> list[str]:
        """The example ids, in order."""
        return self.df["example_id"].tolist()

    # ------------------------------------------------------------------ splits

    def splits(self) -> pd.DataFrame:
        """Number of examples and of calculators per split.

        >>> data.demo(5).split_off("dev", fraction=0.4, from_split="demo").splits()
               examples  calculators
        split
        demo         12            4
        dev           8            4
        """
        out = self.df.groupby("split").agg(examples=("example_id", "size"), calculators=("Calculator ID", "nunique"))
        return out

    def assign_split(self, example_ids: Iterable[str], split: str) -> MedCalcDataset:
        """Move the given examples to `split` (a new or existing split name).

        >>> ds = data.demo().assign_split(["demo:2:1", "demo:6:1"], "hard")
        >>> ds.splits().examples.to_dict()
        {'demo': 2, 'hard': 2}
        """
        ids = set(example_ids)
        unknown = ids - set(self.df["example_id"])
        if unknown:
            raise KeyError(f"unknown example ids: {sorted(unknown)[:5]}")
        df = self.df.copy()
        df.loc[df["example_id"].isin(ids), "split"] = split
        return MedCalcDataset(df)

    def split_off(self, name: str, fraction: float | None = None, n: int | None = None, *, from_split: str = "train",
                  per_calculator: bool = True, seed: int = 0, exclude_leaks: bool = False,
                  leak_against: str | Iterable[str] = "test") -> MedCalcDataset:
        """Move part of `from_split` to a new split `name`, at random (reproducible with `seed`), e.g. a dev set
        taken from the training set. Give `fraction` (of each calculator's examples, at least one) or `n` (per
        calculator; in total if per_calculator=False).

        exclude_leaks=True never moves an example that leaks into `leak_against` (same note text, or an extracted
        note of the same patient, see data.quality), so the new split is clean with respect to the test set.

        >>> ds = data.demo(5)
        >>> dev = ds.split_off("dev", fraction=0.2, from_split="demo")
        >>> dev.splits().examples.to_dict()
        {'demo': 16, 'dev': 4}
        >>> dev.filter(split="dev").calculators()["dev"].tolist()       # stratified: one per calculator
        [1, 1, 1, 1]
        >>> ds.split_off("dev", n=3, per_calculator=False, from_split="demo").splits().examples.to_dict()
        {'demo': 17, 'dev': 3}
        """
        if (fraction is None) == (n is None):
            raise ValueError("give exactly one of fraction and n")
        pool = self.df[self.df["split"] == from_split]
        if pool.empty:
            raise ValueError(f"no example in split {from_split!r}")
        if exclude_leaks:
            from medcalc_kit.data.quality import leaking_rows

            pool = pool[~leaking_rows(self.df, from_split, leak_against).reindex(pool.index, fill_value=False)]

        def take(g: pd.DataFrame, k: int) -> pd.DataFrame:
            return g.sample(min(k, len(g)), random_state=seed)

        if per_calculator:
            chosen = pd.concat([take(g, n if n is not None else max(1, round(fraction * len(g))))
                                for _, g in pool.groupby("Calculator ID", sort=False)])
        else:
            chosen = take(pool, n if n is not None else round(fraction * len(pool)))
        return self.assign_split(chosen["example_id"], name)

    def folds(self, k: int, *, from_split: str = "train", name: str = "dev", per_calculator: bool = True,
              seed: int = 0) -> list[MedCalcDataset]:
        """k-fold cross-validation over `from_split`: k datasets, the i-th with fold i moved to split `name` and the
        other folds left in `from_split`. Folds are stratified by calculator and disjoint.

        >>> folds = data.demo(5).folds(5, from_split="demo")
        >>> [f.splits().examples.to_dict() for f in folds[:2]]
        [{'demo': 16, 'dev': 4}, {'demo': 16, 'dev': 4}]
        >>> len(set().union(*(f.filter(split="dev").example_ids for f in folds)))       # every example once
        20
        """
        pool = self.df[self.df["split"] == from_split]
        groups = [g for _, g in pool.groupby("Calculator ID", sort=False)] if per_calculator else [pool]
        fold_of: dict[str, int] = {}
        for g in groups:
            for i, example_id in enumerate(g.sample(frac=1, random_state=seed)["example_id"]):
                fold_of[example_id] = i % k
        return [self.assign_split([e for e, f in fold_of.items() if f == i], name) for i in range(k)]

    def with_splits(self, assignment: str | Path | pd.DataFrame | pd.Series | Mapping[str, str], *,
                    drop_unassigned: bool = False) -> MedCalcDataset:
        """Apply a split assignment {example_id: split}: a CSV file written by `save_splits`, a DataFrame with
        `example_id` and `split` columns, a Series or a dict. Examples absent from it keep their split, or are
        dropped with drop_unassigned=True.

        >>> ds = data.demo().with_splits({"demo:2:1": "train", "demo:6:1": "train", "demo:39:1": "test"})
        >>> ds.splits().examples.to_dict()
        {'demo': 1, 'test': 1, 'train': 2}
        >>> len(data.demo().with_splits({"demo:2:1": "train"}, drop_unassigned=True))
        1
        """
        if isinstance(assignment, (str, Path)):
            assignment = pd.read_csv(assignment, dtype=str)
        if isinstance(assignment, pd.DataFrame):
            assignment = assignment.set_index("example_id")["split"]
        mapping = dict(assignment)
        df = self.df.copy()
        assigned = df["example_id"].map(mapping)
        if drop_unassigned:
            df, assigned = df[assigned.notna()], assigned[assigned.notna()]
        df["split"] = assigned.fillna(df["split"])
        return MedCalcDataset(df)

    def save_splits(self, path: str | Path) -> Path:
        """Save the split of every example (CSV: example_id, split), to reproduce a split later with
        `with_splits` on a freshly loaded dataset.

        >>> import tempfile, pathlib
        >>> path = pathlib.Path(tempfile.mkdtemp()) / "splits.csv"
        >>> ds = data.demo(5).split_off("dev", fraction=0.2, from_split="demo")
        >>> _ = ds.save_splits(path)
        >>> data.demo(5).with_splits(path).splits().equals(ds.splits())
        True
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.df[["example_id", "split"]].to_csv(path, index=False)
        return path

    def calculators(self) -> pd.DataFrame:
        """One row per calculator: id, name, category and number of examples per split.

        >>> data.demo().calculators()[["Calculator ID", "Category", "demo"]]
          Calculator ID  Category  demo
        0             2  lab test     1
        1             5  physical     1
        2             6  physical     1
        3            39  lab test     1
        """
        counts = self.df.pivot_table(index=["Calculator ID", "Calculator Name", "Category"], columns="split",
                                     values="example_id", aggfunc="count", fill_value=0).reset_index()
        counts.columns.name = None
        return counts.sort_values("Calculator ID", key=lambda s: s.astype(int)).reset_index(drop=True)


def concat(*datasets: MedCalcDataset) -> MedCalcDataset:
    """One dataset with the examples of all the given ones (also `ds1 + ds2`). Example ids must be unique.

    >>> mine = data.from_records([{"Calculator ID": "6", "entities": {"weight": [80, "kg"], "height": [180, "cm"]},
    ...                            "Ground Truth Answer": 24.69}], split="mine")
    >>> data.demo() + mine
    MedCalcDataset(5 examples, 4 calculators; demo: 4, mine: 1)
    """
    df = pd.concat([d.df for d in datasets], ignore_index=True)
    duplicated = df["example_id"][df["example_id"].duplicated()]
    if len(duplicated):
        raise ValueError(f"duplicate example ids: {duplicated.head().tolist()}")
    return MedCalcDataset(df)


def from_records(records: Iterable[Mapping[str, Any]] | pd.DataFrame, split: str = "custom") -> MedCalcDataset:
    """A dataset from your own examples, with the benchmark's column names. Each record needs "Calculator ID" and
    "entities" (or "Relevant Entities", parsed); "Patient Note", "Question", "Ground Truth Answer", "Lower Limit",
    "Upper Limit" are needed by the probes that use them (limits default to the ground truth ±5 %). Missing
    `example_id`s become "<split>:<calculator id>:<n>"; missing names and categories come from the registry.

    >>> ds = data.from_records([{"Calculator ID": 6, "entities": {"weight": [80, "kg"], "height": [180, "cm"]},
    ...                          "Ground Truth Answer": 24.69}])
    >>> ds[0]
    Example('custom:6:1', calculator 6 'Body Mass Index (BMI)', ground truth 24.69)
    """
    from medcalc_kit.calculators import CALCULATORS

    df = pd.DataFrame(records).copy() if not isinstance(records, pd.DataFrame) else records.copy()
    df["Calculator ID"] = df["Calculator ID"].astype(str)
    if "Relevant Entities" in df:                               # parse the raw annotations where entities are missing
        parsed = df["Relevant Entities"].map(lambda r: parse_entities(r) if isinstance(r, str) else None)
        df["entities"] = df["entities"].where(df["entities"].notna(), parsed) if "entities" in df else parsed
    if "split" not in df:
        df["split"] = split
    names = {cid: c.name for cid, c in CALCULATORS.items()}
    if "Calculator Name" not in df:
        df["Calculator Name"] = df["Calculator ID"].map(names).fillna("")
    if "Category" not in df:
        df["Category"] = ""
    if "Ground Truth Answer" in df:
        gt = pd.to_numeric(df["Ground Truth Answer"], errors="coerce")
        for column, factor in (("Lower Limit", 0.95), ("Upper Limit", 1.05)):
            if column not in df:
                df[column] = (gt * factor).where(gt.notna(), df["Ground Truth Answer"])
    if "example_id" not in df:
        rank = df.groupby("Calculator ID").cumcount() + 1
        df["example_id"] = df["split"] + ":" + df["Calculator ID"] + ":" + rank.astype(str)
    return MedCalcDataset(df)


def load(revision: str = DEFAULT_REVISION, splits: tuple[str, ...] = ("train", "test"), equation_only: bool = False,
         dataset_id: str = DATASET_ID) -> MedCalcDataset:
    """Load MedCalc-Bench-Verified from the Hugging Face Hub (downloaded once, then cached; never redistributed).

    revision: dataset commit SHA (default DEFAULT_REVISION, the version the registry was verified against).
    equation_only=True keeps the 33 closed-form calculators, the ones the probes support.

    >>> ds = data.load(equation_only=True)              # doctest: +SKIP
    >>> ds                                              # doctest: +SKIP
    MedCalcDataset(...)
    >>> test = ds.filter(split="test")                  # doctest: +SKIP
    """
    df = load_dataframe(revision, splits, dataset_id)
    return MedCalcDataset(equation_subset(df) if equation_only else df)


# Hand-written examples (not from the benchmark) to try the library without downloading anything. Placeholders
# {e[name][0]:g} take the entities' values, so variants of a patient stay consistent with their note.
_DEMO = [
    ("2", "Creatinine Clearance (Cockcroft-Gault Equation)", "lab test",
     "A {e[age][0]:g}-year-old woman is seen for a medication review. She weighs {e[weight][0]:g} kg and is "
     "{e[height][0]:g} cm tall. Serum creatinine is {e[creatinine][0]:g} mg/dL.",
     "What is the patient's Creatinine Clearance using the Cockroft-Gault Equation in terms of mL/min? You should "
     "use the patient's adjusted body weight in kg instead of the patient's actual body weight if the patient is "
     "overweight or obese based on their BMI. If the patient's BMI's normal, set their adjusted body weight to the "
     "minimum of the ideal body and actual weight. If the patient is underweight, please set their adjusted body "
     "weight to their actual body weight.",
     {"sex": "Female", "age": [51, "years"], "weight": [68.6, "kg"], "height": [158.0, "cm"],
      "creatinine": [0.76, "mg/dL"]}),
    ("6", "Body Mass Index (BMI)", "physical",
     "A 34-year-old man comes for a routine check-up. Height {e[height][0]:g} cm, weight {e[weight][0]:g} kg. "
     "Blood pressure 118/76 mm Hg.",
     "What is the patient's body mass index (BMI)? Your answer should be in terms of kg/m².",
     {"weight": [70.0, "kg"], "height": [175.0, "cm"]}),
    ("39", "Anion Gap", "lab test",
     "A 45-year-old man presents with vomiting. Labs: sodium {e[Sodium][0]:g} mEq/L, potassium 3.9 mEq/L, chloride "
     "{e[Chloride][0]:g} mEq/L, bicarbonate {e[Bicarbonate][0]:g} mEq/L, glucose 98 mg/dL.",
     "What is the patient's anion gap in terms of mEq/L?",
     {"Sodium": [140.0, "mEq/L"], "Chloride": [104.0, "mEq/L"], "Bicarbonate": [24.0, "mEq/L"]}),
    ("5", "Mean Arterial Pressure (MAP)", "physical",
     "A 62-year-old woman with hypertension. Blood pressure {e[Systolic Blood Pressure][0]:g}/"
     "{e[Diastolic Blood Pressure][0]:g} mm Hg, heart rate 72 beats per minute.",
     "What is patient's mean arterial pressure in mm Hg?",
     {"Systolic Blood Pressure": [150.0, "mm Hg"], "Diastolic Blood Pressure": [90.0, "mm Hg"]}),
]


def _variant(entities: dict[str, Any], i: int) -> dict[str, Any]:
    """The i-th demo patient: numeric values moved by up to ±9 % (ages by whole years); i = 0 is the original."""
    step = (i * 5 + 3) % 7 - 3                                  # 0 for i = 0, then a fixed walk in -3..3
    out = {}
    for key, value in entities.items():
        if isinstance(value, list):
            v = value[0] + 3 * step if key == "age" else round(value[0] * (1 + 0.03 * step), 2)
            out[key] = [v, *value[1:]]
        else:
            out[key] = value
    return out


def demo(n_per_calculator: int = 1, split: str = "demo") -> MedCalcDataset:
    """Hand-written examples (Cockcroft-Gault, BMI, anion gap, mean arterial pressure) with the dataset's columns,
    to try every function offline: `n_per_calculator` patients per calculator (the first one is always the same).
    Ground truths come from the registry; tolerance interval ±5 %.

    >>> ds = data.demo()
    >>> ds.df[["example_id", "Calculator Name", "Ground Truth Answer"]]
      example_id                                  Calculator Name  Ground Truth Answer
    0   demo:2:1  Creatinine Clearance (Cockcroft-Gault Equation)            79.883911
    1   demo:6:1                            Body Mass Index (BMI)            22.857143
    2  demo:39:1                                        Anion Gap            12.000000
    3   demo:5:1                     Mean Arterial Pressure (MAP)           110.000000
    >>> data.demo(5)
    MedCalcDataset(20 examples, 4 calculators; demo: 20)
    """
    from medcalc_kit.calculators import derive

    rows = []
    for cid, name, category, note, question, base in _DEMO:
        for i in range(n_per_calculator):
            entities = _variant(base, i)
            gt = derive(cid, entities).answer
            rows.append({"Row Number": i + 1, "Calculator ID": cid, "Calculator Name": name, "Category": category,
                         "Note ID": f"demo-{cid}-{i + 1}", "Note Type": "Synthetic",
                         "Patient Note": note.format(e=entities), "Question": question,
                         "Relevant Entities": json.dumps(entities), "Ground Truth Answer": gt,
                         "Lower Limit": gt * 0.95, "Upper Limit": gt * 1.05, "Ground Truth Explanation": "",
                         "split": split, "entities": entities, "example_id": f"{split}:{cid}:{i + 1}"})
    return MedCalcDataset(pd.DataFrame(rows))
