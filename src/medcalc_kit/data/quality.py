"""Data quality and leakage control for building clean evaluation pools from the training split.

- leakage: a train note identical to a test note (normalised text hash), or an 'Extracted' (PMC) note of a
  patient present in test;
- registry agreement: the registry reproduces the row's ground truth (disagreement = annotation or
  reference-implementation error);
- plausibility: canonical inputs within wide physiological ranges (catches annotation errors such as
  platelets annotated per litre, not rare extreme-but-real values).

    >>> from medcalc_kit import data
    >>> ds = data.load(equation_only=True)                      # doctest: +SKIP
    >>> pool = data.usable_train_pool(ds)                       # doctest: +SKIP
    >>> suite = mk.ProbeSuite(schema=ds, k_pool=pool)           # doctest: +SKIP
"""
from __future__ import annotations

import hashlib
import math
import re
from typing import Any

import pandas as pd

from medcalc_kit.calculators import derive

# Wide physiological ranges on the registry's canonical inputs (units as in medcalc_kit.calculators).
PLAUSIBLE_RANGES: dict[str, tuple[float, float]] = {
    "age": (0, 120), "weight": (0.3, 350), "height": (30, 250), "target_bmi": (10, 60),
    "scr": (0.1, 25), "scr_raw": (0.1, 25), "ucr": (1, 1000),
    "na": (100, 200), "na_raw": (100, 200), "sna": (100, 200), "una": (1, 400),
    "cl": (60, 150), "hco3": (1, 60), "albumin": (0.5, 7), "ca": (3, 25),
    "glucose": (10, 3000), "bun": (1, 300), "tc": (50, 1000), "hdl": (3, 200), "tg": (10, 10000),
    "insulin": (0.1, 1000), "ast": (1, 20000), "alt": (1, 20000), "platelets": (1, 2000),
    "bili_raw": (0.05, 80), "inr_raw": (0.5, 20), "sbp": (40, 300), "dbp": (10, 200),
    "hr": (20, 300), "qt": (150, 800), "dose": (0.01, 5000),
}


def note_hash(text: str) -> str:
    """Hash of the note text, insensitive to case and whitespace.

    >>> note_hash("A 51-year-old  woman.") == note_hash("a 51-year-old woman.")
    True
    """
    return hashlib.sha1(re.sub(r"\s+", " ", text.strip().lower()).encode()).hexdigest()


def implausible_inputs(calculator_id: str, entities: dict[str, Any]) -> list[str]:
    """Names of canonical inputs outside PLAUSIBLE_RANGES (empty list = plausible).

    >>> implausible_inputs("6", {"weight": [70, "kg"], "height": [175, "cm"]})
    []
    >>> implausible_inputs("6", {"weight": [70, "kg"], "height": [175, "mm"]})
    Traceback (most recent call last):
    ...
    medcalc_kit.units.UnitError: unknown height unit 'mm'
    >>> implausible_inputs("6", {"weight": [70, "g"], "height": [175, "cm"]})
    ['weight']
    """
    d = derive(calculator_id, entities)
    bad = [k for k, v in d.inputs.items()
           if k in PLAUSIBLE_RANGES and not (PLAUSIBLE_RANGES[k][0] <= v <= PLAUSIBLE_RANGES[k][1])]
    if not math.isfinite(d.answer):
        bad.append("answer")
    return bad


def _plausible(row) -> bool:
    try:
        return not implausible_inputs(row["Calculator ID"], row["entities"])
    except Exception:  # noqa: BLE001 - underivable rows are already excluded by registry_ok
        return False


def registry_agrees(row) -> bool:
    """True if the registry's answer falls within the row's [Lower Limit, Upper Limit].

    >>> registry_agrees(mk.data.demo().df.iloc[0])
    True
    """
    try:
        v = derive(row["Calculator ID"], row["entities"]).answer
    except Exception:  # noqa: BLE001
        return False
    lo, hi = sorted((float(row["Lower Limit"]), float(row["Upper Limit"])))
    return lo - 1e-9 <= v <= hi + 1e-9


def _frame(data) -> pd.DataFrame:
    return data.df if hasattr(data, "df") else data


def flag_train_rows(data) -> pd.DataFrame:
    """Train rows (DataFrame) with columns leak_text, leak_patient, registry_ok, plausible.
    `data`: a MedCalcDataset or a DataFrame containing both the train and test splits.

    >>> flags = flag_train_rows(data.load(equation_only=True))    # doctest: +SKIP
    >>> flags[["leak_text", "leak_patient", "registry_ok", "plausible"]].mean()   # doctest: +SKIP
    """
    df = _frame(data).copy()
    df["note_hash"] = df["Patient Note"].map(note_hash)
    test = df[df["split"] == "test"]
    train = df[df["split"] == "train"].copy()
    test_pmc_ids = set(test.loc[test["Note Type"] == "Extracted", "Note ID"])
    train["leak_text"] = train["note_hash"].isin(set(test["note_hash"]))
    train["leak_patient"] = (train["Note Type"] == "Extracted") & train["Note ID"].isin(test_pmc_ids)
    train["registry_ok"] = train.apply(registry_agrees, axis=1)
    train["plausible"] = train.apply(_plausible, axis=1)
    return train


def usable_train_pool(data) -> pd.DataFrame:
    """Train rows that are leakage-free, reproduced by the registry and plausible: a clean pool of other patients,
    e.g. for K test points (ProbeSuite(k_pool=...)).

    >>> pool = usable_train_pool(data.load(equation_only=True))   # doctest: +SKIP
    """
    t = flag_train_rows(data)
    return t[~t["leak_text"] & ~t["leak_patient"] & t["registry_ok"] & t["plausible"]]
