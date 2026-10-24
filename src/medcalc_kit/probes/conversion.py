"""U — Unit conversion: can the model convert a patient value to the unit the formula uses?

Prompt: one of the patient's values (e.g. serum creatinine), expressed in another plausible unit (e.g. µmol/L), and
the unit the registry's formula uses (mg/dL). The model converts it. The prompt names the substance but never gives
the molar mass or the valence: knowing them is part of the competence.
Answer: {"value": <number>}. Scoring: relative error <= rel_tol (default 1 %).
Error types: format_invalid, unconverted (the starting number copied back), inverse_factor (the factor applied the
wrong way: multiplied instead of divided, or the reverse), wrong_value.

The source unit is drawn at random among UNIT_TABLE's alternatives, reproducibly from `seed` and the item id. For a
monovalent ion (sodium, chloride, bicarbonate), mmol/L and mEq/L are the same number: the probe then checks that the
model knows it.

    >>> item = build(mk.data.demo()[0], field="creatinine")      # 0.76 mg/dL, given in µmol/L
    >>> item["reference"]["source_value"], item["reference"]["source_unit"], item["reference"]["target_unit"]
    (67.19, 'µmol/L', 'mg/dL')
    >>> score(item, '{"value": 0.76}')["correct"], score(item, '{"value": 67.19}')["error_type"]
    (True, 'unconverted')
"""
from __future__ import annotations

import json
import math
import random
from typing import Any

from medcalc_kit.data import Example, as_example
from medcalc_kit.probes.base import Probe
from medcalc_kit.probes.common import (
    DEFAULT_SYSTEM_PROMPT,
    Item,
    fmt,
    make_item,
    numeric_answer,
    rel_close,
    render,
    resolve_template,
)
from medcalc_kit.probes.extraction import CANONICAL
from medcalc_kit.units import convert

DEFAULT_MAX_NEW_TOKENS = 768
DEFAULT_REL_TOL = 0.01
# Significant digits of the value shown, as on a lab report; the reference is computed from the value shown.
DEFAULT_DIGITS = 4

# Annotation field -> (substance as shown to the model, analyte for molar conversions or None, canonical unit of the
# registry's formula, other plausible units the value can be given in).
UNIT_TABLE: dict[str, tuple[str, str | None, str, tuple[str, ...]]] = {
    "creatinine": ("serum creatinine", "creatinine", "mg/dL", ("µmol/L",)),
    "Urine creatinine": ("urine creatinine", "creatinine", "mg/dL", ("µmol/L", "mmol/L")),
    "Sodium": ("serum sodium", "sodium", "mEq/L", ("mmol/L",)),
    "Urine sodium": ("urine sodium", "sodium", "mEq/L", ("mmol/L",)),
    "Chloride": ("serum chloride", "chloride", "mEq/L", ("mmol/L",)),
    "Bicarbonate": ("serum bicarbonate", "bicarbonate", "mEq/L", ("mmol/L",)),
    "Glucose": ("serum glucose", "glucose", "mg/dL", ("mmol/L",)),
    "Calcium": ("serum calcium", "calcium", "mg/dL", ("mmol/L", "mEq/L")),
    "Blood Urea Nitrogen (BUN)": ("blood urea nitrogen", "bun", "mg/dL", ("mmol/L",)),
    "Albumin": ("serum albumin", "albumin", "g/dL", ("g/L",)),
    "Total cholesterol": ("total cholesterol", "cholesterol", "mg/dL", ("mmol/L",)),
    "high-density lipoprotein cholesterol": ("HDL cholesterol", "cholesterol", "mg/dL", ("mmol/L",)),
    "Triglycerides": ("triglycerides", "triglycerides", "mg/dL", ("mmol/L",)),
    "weight": ("body weight", None, "kg", ("lbs",)),
    "height": ("height", None, "cm", ("m", "in")),
}

# Registry variable -> UNIT_TABLE field, for the values substitution.build(value_units=...) can give in another unit.
VARIABLE_FIELDS = {
    "scr": "creatinine", "scr_raw": "creatinine", "ucr": "Urine creatinine", "na": "Sodium", "na_raw": "Sodium",
    "sna": "Sodium", "una": "Urine sodium", "cl": "Chloride", "hco3": "Bicarbonate", "glucose": "Glucose",
    "ca": "Calcium", "bun": "Blood Urea Nitrogen (BUN)", "albumin": "Albumin", "tc": "Total cholesterol",
    "hdl": "high-density lipoprotein cholesterol", "tg": "Triglycerides", "weight": "weight", "height": "height",
}

# Placeholders: {quantity} (the substance), {value}, {unit} (the value's unit), {target_unit}.
DEFAULT_TEMPLATE = (
    "A patient's {quantity} is {value} {unit}.\n\n"
    "Convert this value to {target_unit}. Work carefully without any tool, then end your answer with a JSON object "
    'of the form {"value": <number in {target_unit} with at least 4 significant digits>}'
)
# Paraphrases of the default template: the same information, conventions and answer format, worded differently, to
# measure how much a result depends on the wording (see evaluate_model(prompt_variants=...)). "v1" is the default.
TEMPLATES = {
    "v1": DEFAULT_TEMPLATE,
    "v2": ("Measured {quantity}: {value} {unit}.\n\n"
           "Express this measurement in {target_unit}, without using any tool. Show your work if you wish, then give "
           'the result as a JSON object {"value": <number in {target_unit} with at least 4 significant digits>}'),
    "v3": ("{quantity} = {value} {unit}. What is it in {target_unit}? Compute it yourself, then end with "
           '{"value": <number in {target_unit} with at least 4 significant digits>}'),
}


def convertible_fields(example: Example | dict[str, Any]) -> list[str]:
    """The example's annotated fields that the probe can convert (those of UNIT_TABLE), in annotation order.

    >>> convertible_fields(mk.data.demo()[0]), convertible_fields(mk.data.demo()[3])
    (['weight', 'height', 'creatinine'], [])
    """
    return [k for k in as_example(example).entities if k in UNIT_TABLE]


def build(example: Example | dict[str, Any], field: str | None = None, source_unit: str | None = None, *,
          template: str = DEFAULT_TEMPLATE, max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS,
          system_prompt: str | None = DEFAULT_SYSTEM_PROMPT, digits: int = DEFAULT_DIGITS, label: str = "U",
          seed: int = 0) -> Item:
    """The item for one example: one of the patient's values in another unit, to convert to the formula's unit.

    field: the annotated field to convert (default: the first one of convertible_fields); source_unit: the unit it
    is given in (default: drawn among UNIT_TABLE's alternatives from `seed` and the item id); template: prompt text
    with placeholders {quantity}, {value}, {unit}, {target_unit}, or the name of a variant of TEMPLATES ("v1", "v2",
    "v3"); digits: significant digits of the value shown; max_new_tokens: token budget; system_prompt: None for
    none; label: the item's probe name.

    >>> item = build(mk.data.demo()[1])                          # BMI patient: weight 70 kg
    >>> print(item["messages"][-1]["content"].splitlines()[0])
    A patient's body weight is 154.3 lbs.
    >>> item["reference"]["gold_value"]
    69.98...
    >>> build(mk.data.demo()[1], "height", "m")["reference"]["source_value"]
    1.75
    """
    ex = as_example(example)
    fields = convertible_fields(ex)
    if not fields:
        raise ValueError(f"example {ex.example_id} has no value the probe can convert (see UNIT_TABLE)")
    field = field if field is not None else fields[0]
    if field not in UNIT_TABLE or field not in ex.entities:
        raise ValueError(f"{field!r} is not a convertible value of example {ex.example_id}: {fields}")
    quantity, analyte, target, alternatives = UNIT_TABLE[field]
    if source_unit is None:
        source_unit = random.Random(f"{seed}:{ex.example_id}:{label}").choice(alternatives)
    patient_value = CANONICAL[field](ex.entities[field])                  # in the canonical unit
    shown = float(fmt(convert(patient_value, target, source_unit, analyte), digits))
    gold = convert(shown, source_unit, target, analyte)
    name, text = resolve_template(template, TEMPLATES)
    user = render(text, quantity=quantity, value=fmt(shown, digits), unit=source_unit, target_unit=target)
    reference = {"field": field, "quantity": quantity, "analyte": analyte, "source_value": shown,
                 "source_unit": source_unit, "target_unit": target, "gold_value": gold}
    return make_item(ex, label, user, reference, max_new_tokens, system_prompt, task="U", template=(name, text))


def score_answer(reference: dict[str, Any], text: str, *, rel_tol: float = DEFAULT_REL_TOL) -> dict[str, Any]:
    """Score a model answer against a U reference ({"source_value", "gold_value", ...}).

    >>> ref = build(mk.data.demo()[0], "creatinine")["reference"]       # 67.19 µmol/L -> 0.76 mg/dL
    >>> [score_answer(ref, f'{{"value": {v}}}')["error_type"] for v in (0.76, 67.19, 5940, 1.2)]
    [None, 'unconverted', 'inverse_factor', 'wrong_value']
    """
    v = numeric_answer(text, "value")
    if v is None:
        return {"format_valid": False, "correct": False, "error_type": "format_invalid", "rel_error": math.nan}
    gold, source = reference["gold_value"], reference["source_value"]
    rel = abs(v - gold) / max(abs(gold), 1e-12)
    if rel <= rel_tol:
        error = None
    elif rel_close(v, source, rel_tol):
        error = "unconverted"
    elif source != 0 and gold != 0 and rel_close(v, source * source / gold, rel_tol):
        error = "inverse_factor"                                     # factor gold/source applied the other way
    else:
        error = "wrong_value"
    return {"format_valid": True, "correct": error is None, "error_type": error, "rel_error": rel}


def score(item: Item, text: str, **options: Any) -> dict[str, Any]:
    """Score a model answer for a U item. Options: rel_tol (default 1 %).

    >>> item = build(mk.data.demo()[1], "weight", "lbs")
    >>> score(item, '{"value": 70.5}')["correct"], score(item, '{"value": 70.5}', rel_tol=0.001)["correct"]
    (True, False)
    """
    return score_answer(item["reference"], text, **options)


def reference_answer(item: Item) -> str:
    """A correct answer: the converted value in the expected JSON format.

    >>> reference_answer(build(mk.data.demo()[1], "height", "m"))
    '{"value": 175.0}'
    """
    return json.dumps({"value": item["reference"]["gold_value"]})


PROBE = Probe("U", "Unit conversion", "converting a patient value to the unit the formula uses", build, score,
              reference_answer)
