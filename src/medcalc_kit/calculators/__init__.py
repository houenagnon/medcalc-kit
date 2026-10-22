"""Executable registry of the 33 equation-based MedCalc-Bench calculators.

    >>> from medcalc_kit.calculators import derive, table
    >>> d = derive("6", {"weight": [70, "kg"], "height": [175, "cm"]})
    >>> round(d.answer, 2), [s.expr for s in d.steps]
    (22.86, ['weight / (height / 100)^2'])
    >>> d.to_frame()            # inputs, coefficients and steps as a DataFrame
         kind    name  ...
    >>> len(table())            # one row per calculator
    33
"""
from medcalc_kit.calculators import equations  # noqa: F401 - registers every calculator
from medcalc_kit.calculators.registry import (
    CALCULATORS,
    KNOWN_REFERENCE_DEVIATIONS,
    Calculator,
    Derivation,
    Step,
    derive,
    get,
    list_calculators,
    table,
)


def verify_registry(data):
    """Check the registry against the ground truth of a MedCalcDataset or DataFrame: (per-example table,
    per-calculator x split summary). Same as `python -m medcalc_kit.calculators.verify` on the whole dataset.

    >>> per_example, summary = verify_registry(mk.data.demo())
    >>> bool(per_example.within_bounds.all())
    True
    """
    from medcalc_kit.calculators.verify import verify

    return verify(data)

__all__ = ["CALCULATORS", "KNOWN_REFERENCE_DEVIATIONS", "Calculator", "Derivation", "Step", "derive", "get",
           "list_calculators", "table",
           "verify_registry"]
