"""Unit normalisation for MedCalc-Bench entity annotations.

Annotations come as [value, unit] (or [v1, u1, v2, u2] for composite heights/ages).
Constants (molar masses, valences, conversion factors) follow the reference MedCalc-Bench
implementation (ncbi-nlp/MedCalc-Bench, calculator_implementations/) so that our registry
reproduces the benchmark's conventions; deviations are documented in medcalc_kit.calculators.

    >>> from medcalc_kit import units
    >>> round(units.concentration(88.4, "µmol/L", "creatinine", "mg/dL"), 3)
    1.0
    >>> units.height_cm([5, "ft", 10, "in"])
    177.8
"""
from __future__ import annotations

import re
from typing import Any

# g/mol, as in the reference implementation.
MOLAR_MASS = {
    "creatinine": 113.12,
    "sodium": 22.99,
    "chloride": 35.45,
    "bicarbonate": 61.02,
    "glucose": 180.16,
    "bun": 28.02,
    "calcium": 40.08,
    "cholesterol": 386.654,
    "triglycerides": 861.338,
    "albumin": 66500.0,
}
VALENCE = {"sodium": 1, "chloride": 1, "bicarbonate": 1, "calcium": 2}

_GRAM = {"kg": 1e3, "g": 1.0, "mg": 1e-3, "µg": 1e-6, "ng": 1e-9}
_MOL = {"mol": 1.0, "mmol": 1e-3, "µmol": 1e-6, "nmol": 1e-9, "pmol": 1e-12}
_EQ = {"Eq": 1.0, "mEq": 1e-3}
_VOLUME = {"L": 1.0, "dL": 1e-1, "mL": 1e-3, "µL": 1e-6, "mm^3": 1e-6, "cm^3": 1e-3}


class UnitError(ValueError):
    """Raised for an unknown or unconvertible unit."""


# Spelling variants seen in model outputs (pilot A1), per '/'-separated component, matched case-insensitively.
_COMPONENT_ALIASES = {
    "dl": "dL", "l": "L", "ml": "mL", "µl": "µL", "ul": "µL", "mcl": "µL", "mm3": "mm^3", "mm^3": "mm^3",
    "meq": "mEq", "eq": "Eq", "mmol": "mmol", "µmol": "µmol", "umol": "µmol", "nmol": "nmol", "pmol": "pmol",
    "mg": "mg", "g": "g", "gm": "g", "gms": "g", "kg": "kg", "kgs": "kg", "ng": "ng", "µg": "µg", "mcg": "µg",
    "lb": "lbs", "lbs": "lbs", "pound": "lbs", "pounds": "lbs",
    "cm": "cm", "cms": "cm", "in": "in", "inch": "in", "inches": "in", "ft": "ft", "feet": "ft", "foot": "ft",
}


def clean_unit(unit: str) -> str:
    """Normalise unit spelling: micro sign variants, broken escapes, spacing, case of mm Hg, and
    case / plural variants of known components ('mg/dl' -> 'mg/dL', 'meq/l' -> 'mEq/L', 'inches' -> 'in').

    >>> clean_unit("mg/dl"), clean_unit("meq/l"), clean_unit("mm hg"), clean_unit("inches")
    ('mg/dL', 'mEq/L', 'mm Hg', 'in')
    """
    # Broken escapes of the micro sign must be repaired before strip(): '\x0b' is whitespace.
    u = unit.replace("μ", "µ").replace("\x0b5", "µ").replace("\x00b5", "µ").strip()
    u = re.sub(r"\s+", " ", u)
    if u.lower().replace(" ", "") in {"mmhg", "smmhg"}:  # 's mm hg' is an annotation typo
        return "mm Hg"
    parts = [p.strip() for p in u.split("/")]
    if all(p.lower() in _COMPONENT_ALIASES or p == "" for p in parts):
        return "/".join(_COMPONENT_ALIASES.get(p.lower(), p) for p in parts)
    return u


def _split_mass_unit(mass: str) -> tuple[str, float]:
    for table, kind in ((_GRAM, "g"), (_MOL, "mol"), (_EQ, "Eq")):
        if mass in table:
            return kind, table[mass]
    raise UnitError(f"unknown mass unit {mass!r}")


def concentration(value: float, unit: str, analyte: str, target: str) -> float:
    """Convert a concentration between {g, mol, Eq}-per-volume units.

    g <-> mol uses MOLAR_MASS[analyte]; mol <-> Eq uses VALENCE[analyte].

    >>> concentration(2.5, "mmol/L", "calcium", "mg/dL")
    10.02
    >>> concentration(140, "mmol/L", "sodium", "mEq/L")
    140.0
    """
    unit, target = clean_unit(unit), clean_unit(target)
    if unit == target:
        return float(value)
    try:
        src_mass, src_vol = unit.split("/")
        tgt_mass, tgt_vol = target.split("/")
    except ValueError as exc:
        raise UnitError(f"not a concentration unit: {unit!r} -> {target!r}") from exc
    src_kind, src_factor = _split_mass_unit(src_mass)
    tgt_kind, tgt_factor = _split_mass_unit(tgt_mass)
    if src_vol not in _VOLUME or tgt_vol not in _VOLUME:
        raise UnitError(f"unknown volume unit in {unit!r} or {target!r}")

    # amount per litre in base units (g, mol or Eq)
    amount = value * src_factor / _VOLUME[src_vol]
    if src_kind != tgt_kind:
        # route through mol
        if src_kind == "g":
            amount /= MOLAR_MASS[analyte]
        elif src_kind == "Eq":
            amount /= VALENCE[analyte]
        if tgt_kind == "g":
            amount *= MOLAR_MASS[analyte]
        elif tgt_kind == "Eq":
            amount *= VALENCE[analyte]
    return amount / tgt_factor * _VOLUME[tgt_vol]


def weight_kg(entity: list[Any]) -> float:
    """Weight annotation [value, unit] in kg (kg, lbs, g).

    >>> weight_kg([154, "lbs"])
    69.853168
    """
    value, unit = entity[0], clean_unit(entity[1])
    if unit == "kg":
        return float(value)
    if unit == "lbs":
        return value * 0.453592
    if unit == "g":
        return value / 1000
    raise UnitError(f"unknown weight unit {unit!r}")


def height_cm(entity: list[Any]) -> float:
    """Height annotation in cm: [value, unit] (cm, m, in, ft) or [feet, 'ft', inches, 'in'].

    >>> height_cm([1.75, "m"]), height_cm([69, "inches"])
    (175.0, 175.26)
    """
    if len(entity) == 4:  # [feet, 'ft', inches, 'in']
        return (entity[0] * 12 + entity[2]) * 2.54
    value, unit = entity[0], clean_unit(entity[1])
    factors = {"cm": 1.0, "m": 100.0, "in": 2.54, "ft": 30.48}
    if unit not in factors:
        raise UnitError(f"unknown height unit {unit!r}")
    return value * factors[unit]


def age_years(entity: list[Any]) -> float:
    """Benchmark convention: integer years; months//12, weeks//52, days -> 0.

    For composite ages ([2, 'years', 11, 'months']) the first year component is used.

    >>> age_years([51, "years"]), age_years([30, "months"]), age_years([2, "years", 11, "months"])
    (51.0, 2.0, 2.0)
    """
    for i in range(0, len(entity) - 1, 2):
        value, unit = entity[i], str(entity[i + 1])
        if "year" in unit:
            return float(value)
        if "month" in unit:
            return float(value // 12)
        if "week" in unit:
            return float(value // 52)
        if "day" in unit:
            return 0.0
    raise UnitError(f"cannot parse age {entity!r}")


def platelets_1e9_per_L(entity: list[Any]) -> float:
    """Platelet count expressed in 10^9/L (count per volume unit -> per litre).

    Accepts 'µL', '/µL', 'cells/µL', '10^3/µL', 'x10^9/L', 'K/µL'.

    >>> platelets_1e9_per_L([250, "10^3/µL"]), platelets_1e9_per_L([250000, "/µL"])
    (250.0, 250.0)
    """
    value, unit = entity[0], str(entity[1])
    unit = re.sub(r"^\s*(cells|platelets)?\s*/", "", unit, flags=re.IGNORECASE)
    mult = 1.0
    m = re.match(r"^\s*(?:[x×*]\s*)?10\s*\^\s*(\d+)\s*/\s*(.+)$", unit) or re.match(r"^\s*(K)\s*/\s*(.+)$", unit)
    if m:
        mult = 1e3 if m.group(1) == "K" else 10.0 ** int(m.group(1))
        unit = m.group(2)
    unit = clean_unit(unit)
    if unit not in _VOLUME:
        raise UnitError(f"unknown platelet unit {unit!r}")
    return value * mult / _VOLUME[unit] / 1e9


def insulin_uIU_per_mL(entity: list[Any]) -> float:
    """Insulin in µIU/mL. Clinically correct conversion: 1 µIU/mL = 6 pmol/L (the reference implementation
    multiplies by 6, see calculators.KNOWN_REFERENCE_DEVIATIONS).

    >>> insulin_uIU_per_mL([60, "pmol/L"])
    10.0
    """
    value, unit = entity[0], clean_unit(entity[1])
    if unit == "µIU/mL":
        return float(value)
    if unit == "pmol/L":
        return value / 6
    if unit == "ng/mL":
        return value * 24.8
    raise UnitError(f"unknown insulin unit {unit!r}")
