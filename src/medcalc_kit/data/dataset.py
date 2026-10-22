"""Loading MedCalc-Bench-Verified at a pinned revision, as a filterable collection of examples.

    >>> from medcalc_kit import data
    >>> ds = data.load(equation_only=True)              # doctest: +SKIP
    >>> ds = data.demo()                                # 4 hand-written examples, no download
    >>> ds
    MedCalcDataset(4 examples, 4 calculators)
    >>> ds[0].calculator_name
    'Creatinine Clearance (Cockcroft-Gault Equation)'
"""
from __future__ import annotations

import ast
import json
import math
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
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
    [value, unit]. `ground_truth` must fall in [lower, upper] for an answer to count as correct.

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
    ground_truth: float
    lower: float
    upper: float
    note_id: str = ""
    note_type: str = ""
    explanation: str = ""

    def __repr__(self) -> str:
        return (f"Example({self.example_id!r}, calculator {self.calculator_id} {self.calculator_name!r}, "
                f"ground truth {self.ground_truth:.4g})")

    @classmethod
    def from_row(cls, row: dict[str, Any] | pd.Series) -> Example:
        """From a dataset row (original column names). Only example_id, Calculator ID and entities are required:
        the other columns may be absent in hand-made examples (probes that need them will then be empty).

        >>> ex = Example.from_row({"example_id": "my:6:1", "Calculator ID": "6",
        ...                        "entities": {"weight": [70, "kg"], "height": [175, "cm"]}})
        >>> round(ex.derive().answer, 2)
        22.86
        """
        lo, hi = sorted((float(row.get("Lower Limit", math.nan)), float(row.get("Upper Limit", math.nan))))
        return cls(
            example_id=row["example_id"], split=row.get("split", ""),
            calculator_id=str(row["Calculator ID"]), calculator_name=row.get("Calculator Name", ""),
            category=row.get("Category", ""), note=row.get("Patient Note", ""), question=row.get("Question", ""),
            entities=row["entities"], ground_truth=float(row.get("Ground Truth Answer", math.nan)), lower=lo, upper=hi,
            note_id=str(row.get("Note ID", "")), note_type=row.get("Note Type", ""),
            explanation=row.get("Ground Truth Explanation", ""),
        )

    def derive(self):
        """Reference computation by the calculator registry (see `medcalc_kit.calculators.derive`).

        >>> d = data.demo()[0].derive()
        >>> d.branches, round(d.answer, 2)
        (['ibw:female', 'bmi>24.9:abw'], 79.88)
        """
        from medcalc_kit.calculators import derive

        return derive(self.calculator_id, self.entities)


def as_example(x: Example | dict[str, Any] | pd.Series) -> Example:
    """An Example from an Example (returned as is), a dataset row (Series) or a dict with the dataset's columns.

    >>> as_example(data.demo().df.iloc[1]).calculator_id
    '6'
    """
    return x if isinstance(x, Example) else Example.from_row(x)


class MedCalcDataset:
    """A filterable collection of examples backed by a DataFrame (`.df`, original column names).

    Iterating yields `Example`s; `ds[i]` is the i-th example, `ds["test:2:9"]` the example with that id.

    >>> ds = data.demo()
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

    def __repr__(self) -> str:
        return f"MedCalcDataset({len(self)} examples, {self.df['Calculator ID'].nunique()} calculators)"

    def filter(self, calculator: str | int | Iterable[str | int] | None = None, category: str | None = None,
               split: str | None = None) -> MedCalcDataset:
        """Examples matching every given criterion: calculator id(s), category ("lab test", "physical",
        "dosage"...) and split ("train" / "test").

        >>> ds = data.demo()
        >>> ds.filter(calculator=[2, "6"]).example_ids
        ['demo:2:1', 'demo:6:1']
        >>> len(ds.filter(category="lab test"))
        2
        """
        df = self.df
        if calculator is not None:
            ids = [calculator] if isinstance(calculator, (str, int)) else list(calculator)
            df = df[df["Calculator ID"].isin([str(c) for c in ids])]
        if category is not None:
            df = df[df["Category"] == category]
        if split is not None:
            df = df[df["split"] == split]
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


# Hand-written examples (not from the benchmark) to try the library without downloading anything.
_DEMO = [
    ("2", "Creatinine Clearance (Cockcroft-Gault Equation)", "lab test",
     "A 51-year-old woman is seen for a medication review. She weighs 68.6 kg and is 158 cm tall. "
     "Serum creatinine is 0.76 mg/dL.",
     "What is the patient's Creatinine Clearance using the Cockroft-Gault Equation in terms of mL/min? You should "
     "use the patient's adjusted body weight in kg instead of the patient's actual body weight if the patient is "
     "overweight or obese based on their BMI. If the patient's BMI's normal, set their adjusted body weight to the "
     "minimum of the ideal body and actual weight. If the patient is underweight, please set their adjusted body "
     "weight to their actual body weight.",
     {"sex": "Female", "age": [51, "years"], "weight": [68.6, "kg"], "height": [158.0, "cm"],
      "creatinine": [0.76, "mg/dL"]}),
    ("6", "Body Mass Index (BMI)", "physical",
     "A 34-year-old man comes for a routine check-up. Height 175 cm, weight 70 kg. Blood pressure 118/76 mm Hg.",
     "What is the patient's body mass index (BMI)? Your answer should be in terms of kg/m².",
     {"weight": [70.0, "kg"], "height": [175.0, "cm"]}),
    ("39", "Anion Gap", "lab test",
     "A 45-year-old man presents with vomiting. Labs: sodium 140 mEq/L, potassium 3.9 mEq/L, chloride 104 mEq/L, "
     "bicarbonate 24 mEq/L, glucose 98 mg/dL.",
     "What is the patient's anion gap in terms of mEq/L?",
     {"Sodium": [140.0, "mEq/L"], "Chloride": [104.0, "mEq/L"], "Bicarbonate": [24.0, "mEq/L"]}),
    ("5", "Mean Arterial Pressure (MAP)", "physical",
     "A 62-year-old woman with hypertension. Blood pressure 150/90 mm Hg, heart rate 72 beats per minute.",
     "What is patient's mean arterial pressure in mm Hg?",
     {"Systolic Blood Pressure": [150.0, "mm Hg"], "Diastolic Blood Pressure": [90.0, "mm Hg"]}),
]


def demo() -> MedCalcDataset:
    """Four hand-written examples (Cockcroft-Gault, BMI, anion gap, mean arterial pressure) with the dataset's
    columns, to try every function offline. Ground truths come from the registry; tolerance interval ±5 %.

    >>> ds = data.demo()
    >>> ds.df[["example_id", "Calculator Name", "Ground Truth Answer"]]
      example_id                                  Calculator Name  Ground Truth Answer
    0   demo:2:1  Creatinine Clearance (Cockcroft-Gault Equation)            79.883911
    1   demo:6:1                            Body Mass Index (BMI)            22.857143
    2  demo:39:1                                        Anion Gap            12.000000
    3   demo:5:1                     Mean Arterial Pressure (MAP)           110.000000
    """
    from medcalc_kit.calculators import derive

    rows = []
    for cid, name, category, note, question, entities in _DEMO:
        gt = derive(cid, entities).answer
        rows.append({"Row Number": 1, "Calculator ID": cid, "Calculator Name": name, "Category": category,
                     "Note ID": f"demo-{cid}", "Note Type": "Synthetic", "Patient Note": note, "Question": question,
                     "Relevant Entities": json.dumps(entities), "Ground Truth Answer": gt,
                     "Lower Limit": gt * 0.95, "Upper Limit": gt * 1.05, "Ground Truth Explanation": "",
                     "split": "demo", "entities": entities, "example_id": f"demo:{cid}:1"})
    return MedCalcDataset(pd.DataFrame(rows))
