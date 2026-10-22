"""E — Extraction: can the model find the calculator's input values in the patient note?

Prompt: the note + the list of fields of this calculator. Values are asked WITH their unit as written in the
note (no conversion), so that extraction is not confounded with unit conversion.
Scoring: field by field; quantities are converted to canonical units on both sides before comparison
(relative tolerance `rel_tol`). The item is correct if every field is correct.

Field results: correct, missing, wrong_value, unit_error (right number, unit changing its meaning),
unparsable, unit_unparsable, hallucinated (a value for a field absent from the note), gold_unconvertible.
The item's error_type is format_invalid or the most frequent field error.

    >>> item = build(mk.data.demo()[2])                         # anion gap: sodium, chloride, bicarbonate
    >>> v = score(item, '{"Sodium": {"value": 140, "unit": "mmol/L"}, "Chloride": {"value": 104, "unit": "mEq/L"},'
    ...                 ' "Bicarbonate": {"value": 42, "unit": "mEq/L"}}')
    >>> v["correct"], v["field_accuracy"], v["fields"]
    (False, 0.666..., {'Sodium': 'correct', 'Chloride': 'correct', 'Bicarbonate': 'wrong_value'})
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from collections.abc import Callable, Iterable
from typing import Any

from medcalc_kit.data import Example, as_example
from medcalc_kit.parsing import extract_json, to_number
from medcalc_kit.probes.base import Probe
from medcalc_kit.probes.common import DEFAULT_SYSTEM_PROMPT, Item, make_item, rel_close, render
from medcalc_kit.units import (
    UnitError,
    clean_unit,
    concentration,
    height_cm,
    insulin_uIU_per_mL,
    platelets_1e9_per_L,
    weight_kg,
)

DEFAULT_MAX_NEW_TOKENS = 768
DEFAULT_REL_TOL = 0.01
# Placeholders: {note} the patient note, {fields} one line per field with its expected answer format.
DEFAULT_TEMPLATE = (
    "Patient note:\n{note}\n\n"
    "Task: extract the following information about the patient from the note. Use the values at the "
    "patient's first admission, before any treatment. Report each numeric value exactly as written in the "
    "note together with its unit (do not convert units). Use null if a value is not mentioned.\n\n"
    "Fields:\n{fields}\n\n"
    "You may think briefly, then end your answer with a single JSON object containing exactly these fields."
)

# Entity fields whose information is given by the question, not by the patient note.
NOT_IN_NOTE = {"target steroid"}

KIND_HINT = {
    "sex": '"Male" or "Female"',
    "race": "the patient's race as written in the note, or null",
    "steroid": '{"drug": <name>, "value": <dose>, "unit": <unit>}',
    "bool": "true or false (false if not mentioned)",
    "number": "a number",
    "quantity": '{"value": <number>, "unit": <unit as written>}',
}


def default_field_hint(name: str, kind: str, kind_hints: dict[str, str]) -> str:
    """Answer format shown for a field. MME fields get explicit wording: '<drug> Dose Per Day' is the number of
    administrations per day (not a daily dose), '<drug> Dose' the dose of one administration.

    >>> default_field_hint("weight", "quantity", KIND_HINT)
    '{"value": <number>, "unit": <unit as written>}'
    >>> default_field_hint("Morphine Dose Per Day", "quantity", KIND_HINT)
    '{"value": <number of administrations per day>, "unit": "per day"}'
    """
    if kind == "quantity" and name.endswith(" Dose Per Day"):
        return '{"value": <number of administrations per day>, "unit": "per day"}'
    if kind == "quantity" and name.endswith(" Dose"):
        return '{"value": <dose of one administration>, "unit": <unit as written>}'
    return kind_hints[kind]


def field_kind(name: str, value: Any) -> str:
    """Answer type of an annotated field: sex, race, steroid, bool, number or quantity.

    >>> field_kind("weight", [70, "kg"]), field_kind("smoker", True), field_kind("sex", "Male")
    ('quantity', 'bool', 'sex')
    """
    if name == "sex":
        return "sex"
    if name == "Race":
        return "race"
    if name == "input steroid":
        return "steroid"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float)):
        return "number"
    return "quantity"


def calculator_fields(examples: Iterable[Example | dict[str, Any]]) -> dict[str, dict[str, str]]:
    """Union of annotated fields per calculator, with their kind. Use the whole dataset (train + test) so that
    optional fields (e.g. 'Race', boolean history items) are asked for every example of a calculator.

    >>> calculator_fields(mk.data.demo())["6"]
    {'weight': 'quantity', 'height': 'quantity'}
    """
    out: dict[str, dict[str, str]] = defaultdict(dict)
    for ex in examples:
        ex = as_example(ex)
        for k, v in ex.entities.items():
            out[ex.calculator_id].setdefault(k, field_kind(k, v))
    return dict(out)


# ---------------------------------------------------------------- build

def build(example: Example | dict[str, Any], fields: dict[str, str] | None = None, *,
          template: str = DEFAULT_TEMPLATE, max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS,
          system_prompt: str | None = DEFAULT_SYSTEM_PROMPT, kind_hints: dict[str, str] | None = None,
          field_hints: dict[str, str] | None = None, label: str = "E") -> Item:
    """fields: field name -> kind for this calculator (see calculator_fields); default: this example's fields.
    For MME (calculator 49) the drug fields are always taken from the example itself.

    kind_hints: answer format per field kind (overrides KIND_HINT); field_hints: answer format for specific
    field names (overrides the kind's format). template: prompt text, placeholders {note} and {fields};
    max_new_tokens: token budget; system_prompt: None for none; label: the item's probe label (default "E").

    >>> item = build(mk.data.demo()[1], field_hints={"height": "height in cm, a number"})
    >>> print(item["messages"][-1]["content"].split("Fields:")[1].split("You may")[0].strip())
    - "weight": {"value": <number>, "unit": <unit as written>}
    - "height": height in cm, a number
    >>> item["reference"]["gold"]
    {'weight': [70.0, 'kg'], 'height': [175.0, 'cm']}
    """
    ex = as_example(example)
    entities = ex.entities
    if fields is None or ex.calculator_id == "49":
        fields = {k: field_kind(k, v) for k, v in entities.items()}
        if ex.calculator_id == "49":
            fields = {k: "quantity" for k in entities}
    fields = {k: kind for k, kind in fields.items() if k not in NOT_IN_NOTE}
    gold = {}
    for k, kind in fields.items():
        if k in entities:
            gold[k] = entities[k]
        else:  # optional field absent from annotation: reference implementation treats it as False / non-Black
            gold[k] = False if kind == "bool" else None
    hints = {**KIND_HINT, **(kind_hints or {})}
    lines = "\n".join(f'- "{k}": {(field_hints or {}).get(k) or default_field_hint(k, kind, hints)}'
                      for k, kind in fields.items())
    user = render(template, note=ex.note, fields=lines)
    return make_item(ex, label, user, {"fields": fields, "gold": gold}, max_new_tokens, system_prompt, task="E")


# ---------------------------------------------------------------- score

_AGE_ABBREVIATIONS = {"y": "year", "yr": "year", "yrs": "year", "yo": "year", "y/o": "year", "mo": "month",
                      "mos": "month", "wk": "week", "wks": "week", "d": "day"}


def _age_years_float(entity: list[Any]) -> float:
    total = 0.0
    factors = {"year": 1.0, "month": 1 / 12, "week": 1 / 52, "day": 1 / 365}
    for i in range(0, len(entity) - 1, 2):
        unit = str(entity[i + 1]).lower().strip().rstrip(".")
        unit = _AGE_ABBREVIATIONS.get(unit, unit)
        f = next((v for k, v in factors.items() if k in unit), None)
        if f is None:
            raise UnitError(f"unknown age unit {unit!r}")
        total += float(entity[i]) * f
    return total


def _conc(analyte: str, target: str) -> Callable[[list[Any]], float]:
    return lambda e: concentration(float(e[0]), str(e[1]), analyte, target)


# Field -> conversion to a canonical value (fields absent here have a fixed unit: compare the value only).
CANONICAL: dict[str, Callable[[list[Any]], float]] = {
    "weight": weight_kg, "height": height_cm, "age": _age_years_float,
    "creatinine": _conc("creatinine", "mg/dL"), "Urine creatinine": _conc("creatinine", "mg/dL"),
    "Sodium": _conc("sodium", "mEq/L"), "Urine sodium": _conc("sodium", "mEq/L"),
    "Chloride": _conc("chloride", "mEq/L"), "Bicarbonate": _conc("bicarbonate", "mEq/L"),
    "Glucose": _conc("glucose", "mg/dL"), "Blood Urea Nitrogen (BUN)": _conc("bun", "mg/dL"),
    "Calcium": _conc("calcium", "mg/dL"), "Albumin": _conc("albumin", "g/dL"),
    "Total cholesterol": _conc("cholesterol", "mg/dL"),
    "high-density lipoprotein cholesterol": _conc("cholesterol", "mg/dL"),
    "Triglycerides": _conc("triglycerides", "mg/dL"), "Bilirubin": _conc("bilirubin", "mg/dL"),
    "Platelet count": platelets_1e9_per_L, "Insulin": insulin_uIU_per_mL,
}


def _parse_bool(v: Any) -> bool | None:
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    if isinstance(v, str):
        s = v.strip().lower()
        if s in {"true", "yes", "y", "1", "present"}:
            return True
        if s in {"false", "no", "n", "0", "absent", "none", "not mentioned", "null"}:
            return False
    return None


def _norm_text(s: Any) -> str:
    return "".join(ch for ch in str(s).lower() if ch.isalnum())


def _model_quantity(v: Any) -> list[Any] | None:
    """Model answer -> [value, unit] (unit may be '')."""
    if isinstance(v, dict):
        num = to_number(v.get("value"))
        if num is None:
            return None
        return [num, str(v.get("unit") or "")]
    num = to_number(v)
    if num is None:
        return None
    unit = v.split(maxsplit=1)[1] if isinstance(v, str) and len(v.split(maxsplit=1)) == 2 else ""
    return [num, unit]


def _written_in_note(q: list[Any], note: str) -> bool:
    """True if the note contains this value immediately followed by this unit (spelling-normalised)."""
    unit = q[1].strip()
    if not unit:
        return False
    for m in re.finditer(r"(?<![\d.])(\d+(?:\.\d+)?)\s*([^\s,;()]+)", note):
        if rel_close(float(m.group(1)), float(q[0]), 1e-9) and clean_unit(m.group(2).rstrip(".")) == clean_unit(unit):
            return True
    return False


def score_field(name: str, kind: str, gold: Any, pred: Any, present: bool, note: str | None = None,
                rel_tol: float = DEFAULT_REL_TOL) -> str:
    """Return 'correct' or an error category for one field. `present`: the field is a key of the model's JSON.
    `note`: the text the values were extracted from; when given, a value copied with the unit written in the note
    is accepted even if the annotation uses another unit.

    >>> score_field("weight", "quantity", [70, "kg"], {"value": 154.3, "unit": "lbs"}, True)   # converted
    'correct'
    >>> score_field("creatinine", "quantity", [0.76, "mg/dL"], "0.76 µmol/L", True)
    'unit_error'
    >>> score_field("weight", "quantity", [70, "kg"], None, False)
    'missing'
    """
    if kind == "bool":
        b = _parse_bool(pred) if present else False
        return "correct" if b == bool(gold) else ("unparsable" if b is None else "wrong_value")
    if kind == "sex":
        if not present or pred is None:
            return "missing"
        p = _norm_text(pred)
        p = {"m": "male", "man": "male", "f": "female", "woman": "female"}.get(p, p)
        return "correct" if p == _norm_text(gold) else "wrong_value"
    if kind == "race":
        gold_black = _norm_text(gold) in {"black", "africanamerican"} if gold else False
        pred_black = "black" in _norm_text(pred) or "african" in _norm_text(pred) if pred else False
        return "correct" if gold_black == pred_black else "wrong_value"
    if isinstance(pred, dict) and pred.get("value") is None and kind in ("number", "quantity"):
        pred = None                                   # {"value": null, "unit": null} means "not mentioned"
    if gold is None:
        return "correct" if pred is None else "hallucinated"
    if not present or pred is None:
        return "missing"
    if kind == "number":
        num = to_number(pred.get("value") if isinstance(pred, dict) else pred)
        if num is None:
            return "unparsable"
        return "correct" if rel_close(num, float(gold), rel_tol) else "wrong_value"
    if kind == "steroid":
        if not isinstance(pred, dict):
            return "unparsable"
        num = to_number(pred.get("value"))
        # the route (PO / IV) does not change the benchmark's potency multiplier: the drug name suffices
        if _norm_text(pred.get("drug")) not in {_norm_text(gold[0]), _norm_text(gold[0].rsplit(" ", 1)[0])}:
            return "wrong_value"
        if num is None:
            return "unparsable"
        return "correct" if rel_close(num, float(gold[1]), rel_tol) else "wrong_value"

    # quantity
    q = _model_quantity(pred)
    if q is None:
        return "unparsable"
    canon = CANONICAL.get(name)
    if canon is None:  # unit fixed by the field (blood pressure, heart rate, doses...): compare value only
        return "correct" if rel_close(q[0], float(gold[0]), rel_tol) else "wrong_value"
    try:
        g = canon(gold)
    except (UnitError, KeyError, ValueError):
        return "gold_unconvertible"
    try:
        p = canon(q)
    except (UnitError, KeyError, ValueError, IndexError):
        p = None
    if p is not None and rel_close(p, g, rel_tol):
        return "correct"
    # same number as in the note but a unit that changes its meaning
    if rel_close(q[0], float(gold[0]), rel_tol):
        # the prompt asks for the unit as written: a note typo (e.g. 'chloride 103 mg/dL') is not the model's error
        return "correct" if note and _written_in_note(q, note) else "unit_error"
    return "wrong_value" if p is not None else "unit_unparsable"


def score_answer(reference: dict[str, Any], text: str, note: str | None = None,
                 rel_tol: float = DEFAULT_REL_TOL) -> dict[str, Any]:
    """Score a model answer against an E reference ({"fields", "gold"}).

    >>> ref = build(mk.data.demo()[1])["reference"]
    >>> score_answer(ref, '{"weight": "70 kg", "height": "1.75 m"}')
    {'format_valid': True, 'correct': True, 'field_accuracy': 1.0, 'error_type': None,
     'fields': {'weight': 'correct', 'height': 'correct'}}
    """
    obj = extract_json(text)
    if not isinstance(obj, dict):
        return {"format_valid": False, "correct": False, "error_type": "format_invalid",
                "field_accuracy": 0.0, "fields": {}}
    results = {}
    for name, kind in reference["fields"].items():
        results[name] = score_field(name, kind, reference["gold"][name], obj.get(name), name in obj, note, rel_tol)
    n_ok = sum(r == "correct" for r in results.values())
    errors = [r for r in results.values() if r != "correct"]
    return {
        "format_valid": True,
        "correct": not errors,                      # exact match over all fields
        "field_accuracy": n_ok / len(results),
        "error_type": None if not errors else max(set(errors), key=errors.count),
        "fields": results,
    }


def score(item: Item, text: str, *, rel_tol: float = DEFAULT_REL_TOL, accept_unit_as_written: bool = True
          ) -> dict[str, Any]:
    """Score a model answer for an E item. Options: rel_tol (default 1 %), accept_unit_as_written (accept a
    value copied with the unit written in the prompt's note, default True).

    >>> score(build(mk.data.demo()[1]), '{"weight": {"value": 70, "unit": "kg"}}')["fields"]
    {'weight': 'correct', 'height': 'missing'}
    """
    note = item["messages"][-1]["content"] if accept_unit_as_written else None
    return score_answer(item["reference"], text, note=note, rel_tol=rel_tol)


def _gold_value(name: str, kind: str, gold: Any) -> Any:
    if gold is None or kind in ("bool", "number", "sex", "race"):
        return gold
    if kind == "steroid":
        return {"drug": gold[0], "value": gold[1], "unit": gold[2] if len(gold) > 2 else "mg"}
    if len(gold) == 2:
        return {"value": gold[0], "unit": gold[1]}
    if name == "height":                              # composite [feet, 'ft', inches, 'in']
        return {"value": height_cm(gold), "unit": "cm"}
    return {"value": _age_years_float(gold), "unit": "years"}


def reference_answer(item: Item) -> str:
    """A correct answer: every annotated field in the expected JSON format (composite heights and ages are
    given in cm / years).

    >>> reference_answer(build(mk.data.demo()[1]))
    '{"weight": {"value": 70.0, "unit": "kg"}, "height": {"value": 175.0, "unit": "cm"}}'
    """
    ref = item["reference"]
    return json.dumps({k: _gold_value(k, kind, ref["gold"][k]) for k, kind in ref["fields"].items()},
                      ensure_ascii=False)


PROBE = Probe("E", "Extraction", "finding the input values (with units) in the patient note", build, score,
              reference_answer)
