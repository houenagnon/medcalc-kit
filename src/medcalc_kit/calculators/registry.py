"""Core of the executable calculator registry.

Each calculator maps the benchmark's "Relevant Entities" annotation to a Derivation:
  - inputs:        patient values converted to canonical units,
  - coefficients:  values fixed by clinical rules (sex coefficient, CKD-EPI a/b, TBW fraction...),
  - steps:         ordered (name, expression) pairs in the safe grammar of medcalc_kit.expr; the last
                   step is the answer. Branches (piecewise rules) are resolved in Python and the
                   chosen branch is recorded in `branches`.

Conventions follow the reference implementation (ncbi-nlp/MedCalc-Bench) when the benchmark question
states them; known reference bugs are NOT reproduced and are listed in KNOWN_REFERENCE_DEVIATIONS.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from medcalc_kit import expr


@dataclass
class Step:
    """One computation step: `name = expr`, and its value."""
    name: str
    expr: str
    value: float


@dataclass
class Derivation:
    """The reference computation for one patient, as returned by `derive`.

    inputs:        patient values in canonical units (e.g. weight in kg, creatinine in mg/dL),
    coefficients:  constants chosen by clinical rules (sex coefficient, ...),
    steps:         ordered computation steps; the last one is the answer,
    branches:      the piecewise rules that applied to this patient (empty if none).

    >>> d = derive("6", {"weight": [154, "lbs"], "height": [175, "cm"]})
    >>> d.inputs
    {'weight': 69.853168, 'height': 175.0}
    >>> [(s.name, s.expr) for s in d.steps]
    [('bmi', 'weight / (height / 100)^2')]
    >>> round(d.answer, 2)
    22.81
    """
    calculator_id: str
    inputs: dict[str, float] = field(default_factory=dict)
    coefficients: dict[str, float] = field(default_factory=dict)
    steps: list[Step] = field(default_factory=list)
    branches: list[str] = field(default_factory=list)

    @property
    def env(self) -> dict[str, float]:
        """Every named value: inputs, coefficients and step results."""
        return {**self.inputs, **self.coefficients, **{s.name: s.value for s in self.steps}}

    def step(self, name: str, expression: str) -> float:
        """Evaluate `expression` over the values so far, record it as a step and return its value."""
        value = expr.evaluate(expression, self.env)
        self.steps.append(Step(name, expression, value))
        return value

    @property
    def answer(self) -> float:
        """The value of the last step."""
        return self.steps[-1].value

    def to_frame(self) -> pd.DataFrame:
        """One row per quantity, in computation order: inputs, coefficients, then steps (the last is the answer).

        >>> derive("6", {"weight": [70, "kg"], "height": [175, "cm"]}).to_frame()
            kind    name                       expr       value
        0  input  weight                               70.000000
        1  input  height                              175.000000
        2   step     bmi  weight / (height / 100)^2   22.857143
        """
        rows = ([{"kind": "input", "name": k, "expr": "", "value": v} for k, v in self.inputs.items()]
                + [{"kind": "coefficient", "name": k, "expr": "", "value": v} for k, v in self.coefficients.items()]
                + [{"kind": "step", "name": s.name, "expr": s.expr, "value": s.value} for s in self.steps])
        return pd.DataFrame(rows, columns=["kind", "name", "expr", "value"])


@dataclass(frozen=True)
class Calculator:
    """A registered calculator: its MedCalc-Bench id, its name and its derivation function."""
    calculator_id: str
    name: str
    derive: Callable[[dict[str, Any]], Derivation]


CALCULATORS: dict[str, Calculator] = {}

# Places where the reference implementation is clinically wrong; we implement the correct rule.
KNOWN_REFERENCE_DEVIATIONS = {
    "31": "HOMA-IR: reference converts insulin pmol/L -> µIU/mL by *6; correct is /6.",
    "23": "MELD Na: reference clamps creatinine to >=1.0 before applying the dialysis rule "
          "(dialysis patients with creatinine < 1 get 1.0 instead of 4.0).",
}


def calculator(cid: str, name: str):
    """Decorator registering a derivation function under a MedCalc-Bench calculator id (to add a calculator).

    >>> @calculator("999", "Pulse pressure")
    ... def pulse_pressure(e):
    ...     d = new_derivation("999")
    ...     d.inputs.update(sbp=e["sbp"][0], dbp=e["dbp"][0])
    ...     d.step("pp", "sbp - dbp")
    ...     return d
    >>> derive("999", {"sbp": [120, "mm Hg"], "dbp": [80, "mm Hg"]}).answer
    40.0
    >>> del CALCULATORS["999"]
    """
    def register(fn: Callable[[dict[str, Any]], Derivation]):
        CALCULATORS[cid] = Calculator(cid, name, fn)
        return fn
    return register


def derive(calculator_id: str | int, entities: dict[str, Any]) -> Derivation:
    """Reference computation for one patient: canonical inputs, steps, branches and answer.

    calculator_id: MedCalc-Bench id (see `table()`); entities: the annotation, {name: value or [value, unit]}.

    >>> d = derive(2, {"sex": "Female", "age": [51, "years"], "weight": [68.6, "kg"],
    ...                "height": [158, "cm"], "creatinine": [0.76, "mg/dL"]})
    >>> d.branches, round(d.answer, 1)          # BMI 27.5: overweight, adjusted body weight
    (['ibw:female', 'bmi>24.9:abw'], 79.9)
    >>> derive(6, {"weight": [70, "kg"]})
    Traceback (most recent call last):
    ...
    KeyError: "calculator 6 (Body Mass Index (BMI)) needs the entity 'height'; got ['weight']"
    """
    calc = get(calculator_id)
    try:
        return calc.derive(entities)
    except KeyError as exc:
        name = exc.args[0] if exc.args else exc
        if name in entities:
            raise
        raise KeyError(f"calculator {calc.calculator_id} ({calc.name}) needs the entity {name!r}; "
                       f"got {sorted(entities)}") from None


def get(calculator_id: str | int) -> Calculator:
    """The registered calculator with this id.

    >>> get(6).name
    'Body Mass Index (BMI)'
    >>> get(1)
    Traceback (most recent call last):
    ...
    KeyError: "unknown calculator '1': the registry covers the 33 equation-based calculators, see calculators.table()"
    """
    try:
        return CALCULATORS[str(calculator_id)]
    except KeyError:
        raise KeyError(f"unknown calculator {str(calculator_id)!r}: the registry covers the "
                       f"{len(CALCULATORS)} equation-based calculators, see calculators.table()") from None


def list_calculators() -> list[Calculator]:
    """Every registered calculator, sorted by id.

    >>> [c.calculator_id for c in list_calculators()][:5]
    ['2', '3', '5', '6', '7']
    """
    return sorted(CALCULATORS.values(), key=lambda c: int(c.calculator_id))


def table() -> pd.DataFrame:
    """One row per registered calculator: id, name, and the documented deviation from the benchmark's reference
    code ("" if none).

    >>> table().head(3)
      calculator_id                                             name reference_deviation
    0             2  Creatinine Clearance (Cockcroft-Gault Equation)
    1             3                 CKD-EPI Equations for Glomerular Filtration Rate
    2             5                     Mean Arterial Pressure (MAP)
    """
    return pd.DataFrame([{"calculator_id": c.calculator_id, "name": c.name,
                          "reference_deviation": KNOWN_REFERENCE_DEVIATIONS.get(c.calculator_id, "")}
                         for c in list_calculators()])


def is_male(e: dict[str, Any]) -> bool:
    """True if the annotation's sex is "Male" (helper for derivation functions)."""
    return e["sex"] == "Male"


def new_derivation(cid: str) -> Derivation:
    """An empty Derivation for calculator `cid` (helper for derivation functions)."""
    return Derivation(calculator_id=cid)
