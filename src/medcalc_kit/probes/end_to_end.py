"""E2E — End to end: the original MedCalc-Bench task (note + question -> answer), for all 55 calculators.

Three kinds of answers, detected from the ground truth (`answer_type`):
- "number" (52 calculators): must fall within the benchmark's [Lower Limit, Upper Limit] interval, or, if
  `rel_tol` is given, within rel_tol of the ground truth;
- "date" (estimated due date, date of conception): the same calendar date (MM/DD/YYYY, YYYY-MM-DD or
  "September 11, 2014" are all read);
- "weeks_days" (estimated gestational age): the same number of weeks and days.

Error types: format_invalid (no readable {"answer": ...}), out_of_bounds (number), wrong_date, wrong_duration.

    >>> item = build(mk.data.demo()[2])                         # anion gap, ground truth 12
    >>> score(item, '{"answer": 12.4}')["correct"], score(item, '{"answer": 13}')["error_type"]
    (True, 'out_of_bounds')
"""
from __future__ import annotations

import json
import math
import re
from datetime import date, datetime
from typing import Any

from medcalc_kit import expr
from medcalc_kit.data import Example, as_example
from medcalc_kit.parsing import extract_json, to_number
from medcalc_kit.probes.base import Probe
from medcalc_kit.probes.common import (
    DEFAULT_DIGITS,
    DEFAULT_SYSTEM_PROMPT,
    Item,
    branch_formula,
    fmt,
    make_item,
    render,
    resolve_template,
    symbol_doc,
)

DEFAULT_MAX_NEW_TOKENS = 2048
# Placeholders: {note}, {question}, {answer_format} (depends on the answer type, see ANSWER_FORMATS).
DEFAULT_TEMPLATE = (
    "Patient note:\n{note}\n\n"
    "Question: {question}\n\n"
    'Think step by step, then end your answer with a JSON object of the form {"answer": {answer_format}}'
)
# Paraphrases of the default template: the same information, conventions and answer format, worded differently, to
# measure how much a result depends on the wording (see evaluate_model(prompt_variants=...)). "v1" is the default.
TEMPLATES = {
    "v1": DEFAULT_TEMPLATE,
    "v2": ("Here is a patient note.\n\n{note}\n\n"
           "Answer this question about the patient: {question}\n\n"
           'Reason step by step and finish with a JSON object {"answer": {answer_format}}'),
    "v3": ("{note}\n\n{question}\n\n"
           'Work it out, then end with {"answer": {answer_format}}'),
}
# Interventions (build(provide=...)): information from the registry added after the question, and the label suffix.
PROVIDE = {"values": "V", "formula": "F"}
PROVIDED_VALUES_HEADER = "Correct values of the variables, in the units of the formula:"
PROVIDED_FORMULA_HEADER = "Formula that applies to this patient:"
ANSWER_FORMATS = {
    "number": "<number>",
    "date": '"<MM/DD/YYYY>"',
    "weeks_days": '{"weeks": <integer>, "days": <integer>}',
}
_DATE_FORMATS = ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y", "%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%d %b %Y", "%m/%d/%y")
_DATE_RE = re.compile(r"\d{1,2}/\d{1,2}/\d{2,4}|\d{4}-\d{2}-\d{2}")


def answer_type(ground_truth: float | str) -> str:
    """"number", "date" or "weeks_days", from a ground truth.

    >>> answer_type(12.0), answer_type("09/11/2014"), answer_type("('16 weeks', '1 days')")
    ('number', 'date', 'weeks_days')
    """
    if not isinstance(ground_truth, str):
        return "number"
    return "weeks_days" if "week" in ground_truth else "date"


def parse_date(value: Any) -> date | None:
    """A calendar date from a model answer, or None.

    >>> parse_date("09/11/2014"), parse_date("2014-09-11"), parse_date("September 11, 2014")
    (datetime.date(2014, 9, 11), datetime.date(2014, 9, 11), datetime.date(2014, 9, 11))
    >>> parse_date("The due date is 9/11/2014.")
    datetime.date(2014, 9, 11)
    """
    if not isinstance(value, str):
        return None
    text = value.strip().rstrip(".")
    candidates = [text] + _DATE_RE.findall(text)
    for cand in candidates:
        for date_format in _DATE_FORMATS:
            try:
                return datetime.strptime(cand.strip(), date_format).date()
            except ValueError:
                continue
    return None


def parse_weeks_days(value: Any) -> tuple[int, int] | None:
    """(weeks, days) from a model answer: {"weeks": 16, "days": 1}, [16, 1], "(16 weeks, 1 day)"... or None.
    Days beyond 6 are carried into weeks.

    >>> parse_weeks_days({"weeks": 16, "days": 1}), parse_weeks_days("('16 weeks', '1 days')")
    ((16, 1), (16, 1))
    >>> parse_weeks_days([15, 8]), parse_weeks_days("3 weeks"), parse_weeks_days("soon")
    ((16, 1), (3, 0), None)
    """
    weeks = days = None
    if isinstance(value, dict):
        weeks, days = to_number(value.get("weeks")), to_number(value.get("days", 0))
    elif isinstance(value, (list, tuple)) and len(value) == 2:
        weeks, days = to_number(value[0]), to_number(value[1])
    elif isinstance(value, str):
        w = re.search(r"(\d+)\s*weeks?", value)
        d = re.search(r"(\d+)\s*days?", value)
        if w or d:
            weeks, days = float(w.group(1)) if w else 0.0, float(d.group(1)) if d else 0.0
    if weeks is None or days is None:
        return None
    total = int(round(weeks * 7 + days))
    return total // 7, total % 7


def build(example: Example | dict[str, Any], *, template: str = DEFAULT_TEMPLATE,
          max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS, system_prompt: str | None = DEFAULT_SYSTEM_PROMPT,
          label: str | None = None, provide: tuple[str, ...] = (), digits: int = DEFAULT_DIGITS) -> Item:
    """The item for one example: the patient note and the benchmark question. Works for every calculator of the
    benchmark, including the rule-based scores and the date calculators.

    template: prompt text with placeholders {note}, {question} and {answer_format}, or the name of a variant of
    TEMPLATES ("v1", "v2", "v3"); max_new_tokens: token budget;
    system_prompt: None for none; label: the item's probe name (default "E2E", or "E2E+V", "E2E+F", "E2E+VF" with
    `provide`).
    provide: an intervention for equation-based calculators: "values" adds the correct values of the variables (in
    the formula's units), "formula" the formula of the patient's branch, both taken from the registry and added
    after the question. Scoring is unchanged; digits: significant digits of the values given.

    >>> item = build(mk.data.demo()[2], max_new_tokens=512)
    >>> item["max_new_tokens"], item["reference"]["ground_truth"], item["reference"]["answer_type"]
    (512, 12.0, 'number')
    >>> print(item["messages"][-1]["content"].splitlines()[-1])
    Think step by step, then end your answer with a JSON object of the form {"answer": <number>}

    With the formula given (does the model fail for lack of the formula?):

    >>> item = build(mk.data.demo()[1], provide=("formula",))
    >>> item["probe"], [ln for ln in item["messages"][-1]["content"].splitlines() if ln.startswith("bmi =")]
    ('E2E+F', ['bmi = weight / (height / 100)^2'])
    """
    ex = as_example(example)
    kind = answer_type(ex.ground_truth)
    provide = tuple(provide)
    unknown = set(provide) - set(PROVIDE)
    if unknown:
        raise ValueError(f"provide: {sorted(unknown)} not among {list(PROVIDE)}")
    question = ex.question
    if provide:
        from medcalc_kit.calculators import CALCULATORS

        if ex.calculator_id not in CALCULATORS:
            raise ValueError(f"provide needs the registry: calculator {ex.calculator_id} is not equation-based")
        formula, _, d = branch_formula(ex, digits)
        blocks = []
        if "values" in provide:
            blocks.append(PROVIDED_VALUES_HEADER + "\n" + "\n".join(
                f"- {k} = {fmt(v, digits)} ({symbol_doc(k, ex.entities)})" for k, v in d.inputs.items()))
        if "formula" in provide:
            blocks.append(f"{PROVIDED_FORMULA_HEADER}\n{d.steps[-1].name} = {expr.to_str(formula)}")
        question = question + "\n\n" + "\n\n".join(blocks)
    name, text = resolve_template(template, TEMPLATES)
    user = render(text, note=ex.note, question=question, answer_format=ANSWER_FORMATS[kind])
    reference = {"ground_truth": ex.ground_truth, "lower": ex.lower, "upper": ex.upper, "answer_type": kind}
    if provide:
        reference["provided"] = [p for p in PROVIDE if p in provide]
    if label is None:
        label = "E2E" + ("+" + "".join(PROVIDE[p] for p in PROVIDE if p in provide) if provide else "")
    return make_item(ex, label, user, reference, max_new_tokens, system_prompt, task="E2E", template=(name, text))


def score_answer(reference: dict[str, Any], text: str, *, rel_tol: float | None = None) -> dict[str, Any]:
    """Score a model answer against an E2E reference ({"ground_truth", "lower", "upper", "answer_type"}).
    `rel_error` is set for numbers, `error_days` (signed) for dates and durations.

    >>> ref = {"ground_truth": 100.0, "lower": 95.0, "upper": 105.0}
    >>> score_answer(ref, '{"answer": "104 mL/min"}')
    {'format_valid': True, 'correct': True, 'error_type': None, 'rel_error': 0.04}
    >>> score_answer(ref, '{"answer": 104}', rel_tol=0.01)["correct"]
    False
    >>> ref = {"ground_truth": "06/16/2012", "lower": "06/16/2012", "upper": "06/16/2012", "answer_type": "date"}
    >>> score_answer(ref, '{"answer": "06/23/2012"}')
    {'format_valid': True, 'correct': False, 'error_type': 'wrong_date', 'error_days': 7}
    """
    kind = reference.get("answer_type", "number")
    obj = extract_json(text)
    value = obj.get("answer") if isinstance(obj, dict) else None
    invalid = {"format_valid": False, "correct": False, "error_type": "format_invalid"}
    if kind == "number":
        v = to_number(value)
        if v is None:
            return {**invalid, "rel_error": math.nan}
        gt = reference["ground_truth"]
        if rel_tol is None:
            ok = reference["lower"] - 1e-9 <= v <= reference["upper"] + 1e-9
        else:
            ok = abs(v - gt) <= rel_tol * abs(gt)
        return {"format_valid": True, "correct": ok, "error_type": None if ok else "out_of_bounds",
                "rel_error": abs(v - gt) / max(abs(gt), 1e-12)}
    if kind == "date":
        got, gold = parse_date(value), parse_date(reference["ground_truth"])
        if got is None:
            return {**invalid, "error_days": None}
        diff = (got - gold).days
        return {"format_valid": True, "correct": diff == 0, "error_type": None if diff == 0 else "wrong_date",
                "error_days": diff}
    got, gold = parse_weeks_days(value), parse_weeks_days(reference["ground_truth"])
    if got is None:
        return {**invalid, "error_days": None}
    diff = (got[0] * 7 + got[1]) - (gold[0] * 7 + gold[1])
    return {"format_valid": True, "correct": diff == 0, "error_type": None if diff == 0 else "wrong_duration",
            "error_days": diff}


def score(item: Item, text: str, **options: Any) -> dict[str, Any]:
    """Score a model answer for an E2E item. Options: rel_tol (replaces the benchmark interval, numbers only).

    >>> score(build(mk.data.demo()[2]), "The anion gap is 12 mEq/L.")["error_type"]   # JSON required
    'format_invalid'
    """
    return score_answer(item["reference"], text, **options)


def reference_answer(item: Item) -> str:
    """A correct answer: the ground truth in the expected JSON format.

    >>> reference_answer(build(mk.data.demo()[2]))
    '{"answer": 12.0}'
    """
    ref = item["reference"]
    kind = ref.get("answer_type", "number")
    if kind == "date":
        return json.dumps({"answer": parse_date(ref["ground_truth"]).strftime("%m/%d/%Y")})
    if kind == "weeks_days":
        weeks, days = parse_weeks_days(ref["ground_truth"])
        return json.dumps({"answer": {"weeks": weeks, "days": days}})
    return json.dumps({"answer": ref["ground_truth"]})


PROBE = Probe("E2E", "End to end", "the original benchmark task", build, score, reference_answer)
