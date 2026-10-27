"""K — Knowledge: does the model know the calculator's formula?

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

Definitions: an answer may define intermediate quantities from the listed variables, {"definitions": {"rr": "60 / hr"},
"formula": "qt / sqrt(rr)"}; each definition may use the variables and the definitions before it, and the formula
(and conditions) the variables and every definition. The templates "d1" ask for this form: the model writes the
formula as it is usually written and links its quantities to the variables given, instead of composing a single
expression of variables that are not the formula's own; "d2" also asks to think step by step (state the formula, then
link its quantities), and "d2-v2", "d2-v3" are its paraphrases. Definitions the answer does not use, and identities
such as "glucose": "glucose", are ignored.
An answer without definitions is scored as before.

Units: the variables are given in the registry's units by default. `build(formula_units=FORMULA_UNITS)` gives
some of them in the units of the formula's original publication instead (Devine's ideal body weight is defined per
inch of height), so that K measures the formula without a unit conversion to write (probe U measures conversions).

In "general" mode the prompt depends on the patient only through categorical fields, so many examples share
the same prompt: count each distinct prompt once in statistics (generation.prompt_key, evaluate.to_units).

Error types: format_invalid (no JSON formula), unparsable_formula (a case without a formula string),
undefined_function (a function outside the grammar, e.g. ideal_body_weight(height)), invalid_syntax (not an expression
of the grammar, e.g. Python's "x if c else y"), unknown_variable (a name not in the listed variables),
invalid_definition (definitions that are not {name: expression}, or a used definition that is not a name and an
expression, or that redefines a listed variable, e.g. "hr": "90"),
wrong_at_patient_point, wrong_elsewhere (right for this patient only: wrong branch or wrong constant). The answers of
the undefined_function and invalid_syntax kinds have the requested format: they count as well formed and wrong.

    >>> item = build(mk.data.demo()[2])                         # anion gap, variables na, cl, hco3
    >>> score(item, '{"cases": [{"condition": "always", "formula": "na - cl - hco3"}]}')["correct"]
    True
    >>> score(item, '{"cases": [{"condition": "always", "formula": "na + 4 - cl - hco3"}]}')["error_type"]
    'wrong_at_patient_point'
"""
from __future__ import annotations

import json
import math
import random
import re
import zlib
from typing import Any

from medcalc_kit import expr
from medcalc_kit.calculators import derive
from medcalc_kit.data import PLAUSIBLE_RANGES, Example, as_example
from medcalc_kit.parsing import extract_json
from medcalc_kit.probes.base import Probe
from medcalc_kit.probes.common import (
    DEFAULT_DIGITS,
    DEFAULT_SYSTEM_PROMPT,
    Item,
    categorical_context,
    fmt,
    inline,
    make_item,
    rel_close,
    render,
    resolve_template,
    symbol_doc,
    task_question,
)
from medcalc_kit.probes.conversion import UNIT_TABLE, VARIABLE_FIELDS
from medcalc_kit.units import convert

DEFAULT_MAX_NEW_TOKENS = 1024
DEFAULT_N_POINTS = 50
# Share of test points (the patient's included) the formula must be right at; the patient's point is always required.
DEFAULT_MIN_PASS_RATE = 1.0
DEFAULT_REL_TOL = 0.01
# Per-calculator absolute tolerance replacing the relative one (MELD Na: integer score with nested rounding).
DEFAULT_ABS_TOL = {"23": 1.0}
DEFAULT_PERTURBATION_FACTOR = 3.0
# Drug-specific structure: test points are perturbations of the patient itself, never other patients.
PERTURB_ONLY = {"24", "49"}
# A branch with one of these formulas excludes a domain (e.g. height <= 0).
UNDEFINED_FORMULAS = {"undefined", "not defined", "nan", "n/a", "none", "null"}
CASE_SEMANTICS = ("all_agree", "first_match")
# {calculator_id: {variable: unit}}: units of the formula's original publication where they differ from the registry's
# (build(formula_units=...)). The Devine ideal body weight (also inside Cockcroft-Gault and adjusted body weight) is
# 50 or 45.5 kg + 2.3 kg per inch of height over 60 inches.
FORMULA_UNITS: dict[str, dict[str, str]] = {"2": {"height": "in"}, "10": {"height": "in"}, "62": {"height": "in"}}

_ALLOWED = ("Use only numbers, the variables, + - * / ^, parentheses and the functions sqrt, ln, log10, exp, min, "
            "max, abs, round.")
# Placeholders: {question}, {context} (categorical characteristics), {variables} (name: meaning (unit)).
DEFAULT_TEMPLATE = (
    "Task: {question}\n\n"
    "You are NOT given the patient's measurements. Write the general formula needed to answer this task, "
    "using only the variables listed below. Their units are fixed as stated; include any unit conversion "
    "inside your formula.\n\n"
    "Known patient characteristics:\n{context}\n\n"
    "Variables:\n{variables}\n\n"
    "If the formula depends on thresholds or categories, give one case per branch, each with a condition "
    "written with these variables (for example \"x <= 0.9\"), and use \"otherwise\" for the remaining case. "
    + _ALLOWED + "\n\n"
    "You may think briefly, then end your answer with a JSON object of the form\n"
    '{"cases": [{"condition": "<condition, or always>", "formula": "<expression>"}]}'
)
# Placeholders: {question}, {context}, {variables}, {values} (name = value, in the variables' units).
DEFAULT_PATIENT_TEMPLATE = (
    "Task: {question}\n\n"
    "Known patient characteristics:\n{context}\n\n"
    "Patient values:\n{values}\n\n"
    "Write the formula that applies to THIS patient, as an expression of the variables listed below (their "
    "units are fixed as stated; include any unit conversion inside your formula). Do NOT compute the result: "
    "use the variable names, not the patient's numbers.\n\n"
    "Variables:\n{variables}\n\n"
    + _ALLOWED + "\n\n"
    "You may think briefly, then end your answer with a JSON object of the form\n"
    '{"formula": "<expression>"}'
)
_ALLOWED_DEFS = ("Use only numbers, the variables, the quantities you define, + - * / ^, parentheses and the functions "
                 "sqrt, ln, log10, exp, min, max, abs, round.")
_DEFINE = ("If the formula uses a quantity that is not one of the variables (for example an interval derived from "
           "another measurement, or a value in another unit), define it from the variables in \"definitions\".")
# "d1" templates: the formula as usually written, with definitions linking its quantities to the variables given.
DEFINITIONS_TEMPLATE = (
    "Task: {question}\n\n"
    "You are NOT given the patient's measurements. Write the general formula needed to answer this task. You may "
    "first state it as it is usually written.\n\n"
    "Known patient characteristics:\n{context}\n\n"
    "Variables (units fixed as stated):\n{variables}\n\n"
    + _DEFINE + " If the formula depends on thresholds or categories, give one case per branch, each with a "
    "condition (for example \"x <= 0.9\"), and use \"otherwise\" for the remaining case. " + _ALLOWED_DEFS + "\n\n"
    "End your answer with a JSON object of the form\n"
    '{"definitions": {"<name>": "<expression>"}, "cases": [{"condition": "<condition, or always>", '
    '"formula": "<expression>"}]}\n("definitions" may be empty)'
)
DEFINITIONS_PATIENT_TEMPLATE = (
    "Task: {question}\n\n"
    "Known patient characteristics:\n{context}\n\n"
    "Patient values:\n{values}\n\n"
    "Variables (units fixed as stated):\n{variables}\n\n"
    "Write the formula that applies to THIS patient. You may first state it as it is usually written. "
    + _DEFINE + " Do NOT compute the result: use the variable names, not the patient's numbers. "
    + _ALLOWED_DEFS + "\n\n"
    "End your answer with a JSON object of the form\n"
    '{"definitions": {"<name>": "<expression>"}, "formula": "<expression>"}\n("definitions" may be empty)'
)

# Paraphrases of the default template: the same information, conventions and answer format, worded differently, to
# measure how much a result depends on the wording (see evaluate_model(prompt_variants=...)). "v1" is the default.
TEMPLATES = {
    "v1": DEFAULT_TEMPLATE,
    "v2": ("Question to answer: {question}\n\n"
           "The patient's measurements are not provided. Using only the variables below (in the units given; put "
           "any unit conversion inside the formula), write the general formula that answers this question.\n\n"
           "Patient characteristics already known:\n{context}\n\n"
           "Variables:\n{variables}\n\n"
           "If the formula changes with thresholds or categories, write one case per branch with a condition on these "
           "variables (for example \"x <= 0.9\") and use \"otherwise\" for the remaining case. " + _ALLOWED + "\n\n"
           "After any reasoning, end with a JSON object of the form\n"
           '{"cases": [{"condition": "<condition, or always>", "formula": "<expression>"}]}'),
    "v3": ("{question}\n\n"
           "Known about the patient:\n{context}\n\n"
           "Available variables (units fixed as stated):\n{variables}\n\n"
           "Without the patient's values, give the formula for this calculation in terms of these variables, unit "
           "conversions included. For a piecewise formula, give each branch with its condition (like \"x <= 0.9\"), "
           "the last one being \"otherwise\". " + _ALLOWED + "\n\n"
           'End with {"cases": [{"condition": "<condition, or always>", "formula": "<expression>"}]}'),
}
PATIENT_TEMPLATES = {
    "v1": DEFAULT_PATIENT_TEMPLATE,
    "v2": ("Question to answer: {question}\n\n"
           "Patient characteristics:\n{context}\n\n"
           "Patient values:\n{values}\n\n"
           "Give the formula that applies to THIS patient, written with the variable names below rather than the "
           "patient's numbers: do NOT compute the result. Units are fixed as stated; include any unit conversion in "
           "the formula.\n\n"
           "Variables:\n{variables}\n\n" + _ALLOWED + "\n\n"
           "After any reasoning, end with a JSON object of the form\n"
           '{"formula": "<expression>"}'),
    "v3": ("{question}\n\n"
           "Patient characteristics:\n{context}\nPatient values:\n{values}\n\n"
           "Write the formula used for this patient as an expression of these variables (units fixed as stated, "
           "conversions inside the formula), not as a computed number:\n{variables}\n\n" + _ALLOWED + "\n\n"
           'End with {"formula": "<expression>"}'),
}
_STEPS = ("Think step by step: first write the formula as it is usually written, with its own quantities; then express "
          "each of these quantities with the variables above.")
# Templates of another answer form (with definitions), not paraphrases of v1: build(template="d1" or "d2").
# "d2-v2" and "d2-v3" are paraphrases of "d2" (same information, steps and answer format, other wording).
_ALLOWED_DEFS_V2 = ("Allowed: numbers, the listed variables, the quantities you define, + - * / ^, parentheses and "
                    "sqrt, ln, log10, exp, min, max, abs, round.")
_JSON_DEFS_CASES = ('{"definitions": {"<name>": "<expression>"}, "cases": [{"condition": "<condition, or always>", '
                    '"formula": "<expression>"}]}')
_JSON_DEFS_FORMULA = '{"definitions": {"<name>": "<expression>"}, "formula": "<expression>"}'
DEFINITION_TEMPLATES = {
    "d1": DEFINITIONS_TEMPLATE,
    "d2": DEFINITIONS_TEMPLATE.replace("You may first state it as it is usually written.", _STEPS),
    "d2-v2": ("Question to answer: {question}\n\n"
              "The patient's measurements are not provided. Reason step by step: start from the general formula in its "
              "usual written form, then rewrite each of its quantities in terms of the variables listed.\n\n"
              "Patient characteristics already known:\n{context}\n\n"
              "Variables you may use (units as given):\n{variables}\n\n"
              "Any quantity of the formula that is not a listed variable must be defined from them under "
              "\"definitions\". If the formula changes with thresholds or categories, write one case per branch with "
              "a condition (for example \"x <= 0.9\") and use \"otherwise\" for the remaining case. "
              + _ALLOWED_DEFS_V2 + "\n\n"
              "After your reasoning, end with a JSON object of the form\n" + _JSON_DEFS_CASES
              + "\n(\"definitions\" may be empty)"),
    "d2-v3": ("{question}\n\n"
              "Known about the patient:\n{context}\n\n"
              "Available variables (fixed units):\n{variables}\n\n"
              "Think step by step. Without the patient's values, first state the standard formula for this "
              "calculation as it is usually written; then link each of its quantities to the variables above, defining "
              "under \"definitions\" those that are not variables. For a piecewise formula, give each branch with its "
              "condition (like \"x <= 0.9\"), the last one being \"otherwise\". " + _ALLOWED_DEFS + "\n\n"
              "End your answer with a JSON object of the form " + _JSON_DEFS_CASES + " (\"definitions\" may be empty)"),
}
DEFINITION_PATIENT_TEMPLATES = {
    "d1": DEFINITIONS_PATIENT_TEMPLATE,
    "d2": DEFINITIONS_PATIENT_TEMPLATE.replace("You may first state it as it is usually written.", _STEPS),
    "d2-v2": ("Question to answer: {question}\n\n"
              "Patient characteristics:\n{context}\n\n"
              "Patient values:\n{values}\n\n"
              "Variables you may use (units as given):\n{variables}\n\n"
              "Give the formula used for THIS patient. Reason step by step: start from the formula in its usual "
              "written "
              "form, then rewrite each of its quantities in terms of the variables listed. Any quantity of the "
              "formula that is not a listed variable must be defined from them under \"definitions\". Do not "
              "calculate anything: write variable names, not the patient's numbers. " + _ALLOWED_DEFS_V2 + "\n\n"
              "After your reasoning, end with a JSON object of the form\n" + _JSON_DEFS_FORMULA
              + "\n(\"definitions\" may be empty)"),
    "d2-v3": ("{question}\n\n"
              "Patient characteristics:\n{context}\nPatient values:\n{values}\n\n"
              "Available variables (fixed units):\n{variables}\n\n"
              "Think step by step. First state the standard formula for this calculation as it is usually written; "
              "then link each of its quantities to the variables above, defining under \"definitions\" those that are "
              "not variables. The answer is a formula in variable names, not a computed number. " + _ALLOWED_DEFS
              + "\n\nEnd your answer with a JSON object of the form " + _JSON_DEFS_FORMULA
              + " (\"definitions\" may be empty)"),
}


def with_categorical(point: dict[str, Any], entities: dict[str, Any]) -> dict[str, Any]:
    """Continuous values from `point`, categorical (str/bool) fields from `entities`.

    >>> with_categorical({"sex": "Male", "age": [40, "years"]}, {"sex": "Female", "age": [51, "years"]})
    {'age': [40, 'years'], 'sex': 'Female'}
    """
    out = {k: v for k, v in point.items() if not isinstance(v, (str, bool))}
    out.update({k: v for k, v in entities.items() if isinstance(v, (str, bool))})
    return out


def _same_branch_points(pool: list[dict[str, Any]], entities: dict[str, Any], calculator_id: str,
                        branches: list[str], n_points: int) -> list[dict[str, Any]]:
    out = []
    for p in pool:
        q = with_categorical(p, entities)
        try:
            if derive(calculator_id, q).branches == branches:
                out.append(q)
        except Exception:  # noqa: BLE001 - underivable pool rows are skipped
            continue
        if len(out) == n_points:
            break
    return out


# ---------------------------------------------------------------- build

def build(example: Example | dict[str, Any], point_pool: list[dict[str, Any]] | None = None, *,
          mode: str = "general", template: str | None = None, max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS,
          system_prompt: str | None = DEFAULT_SYSTEM_PROMPT, n_points: int = DEFAULT_N_POINTS,
          symbol_docs: dict[str, str] | None = None, digits: int = DEFAULT_DIGITS, label: str = "K",
          formula_units: dict[str, dict[str, str]] | None = None) -> Item:
    """point_pool: entity dicts of other (leakage-free) patients of the same calculator, used as test points
    so that thresholds are explored realistically (in "patient" mode, only those in the patient's branch are
    kept; pass a large pool). Without a pool, perturbations of the patient are used at scoring time.
    mode: "general" (no values shown, one case per branch) or "patient" (values shown, this patient's formula).
    template: prompt text, or the name of a variant ("v1", "v2", "v3") of TEMPLATES ("general" mode) or
    PATIENT_TEMPLATES ("patient" mode), or "d1" (answer with definitions, DEFINITION_TEMPLATES /
    DEFINITION_PATIENT_TEMPLATES); default "v1" (DEFAULT_TEMPLATE / DEFAULT_PATIENT_TEMPLATE).
    n_points: test points kept from the pool; symbol_docs: {variable: description} overriding
    common.SYMBOL_DOCS; digits: significant digits of the values shown in "patient" mode.
    formula_units: {calculator_id: {variable: unit}} gives those variables (descriptions, values shown, test points)
    in another unit than the registry's, e.g. FORMULA_UNITS; the reference stores the factors (`variable_scale`).

    >>> item = build(mk.data.demo()[1], mode="patient")
    >>> print(item["messages"][-1]["content"].split("Variables:")[1].split("Use only")[0].strip())
    - weight: body weight (kg)
    - height: height (cm)
    >>> item["reference"]["symbols"], item["reference"]["branches"]
    (['weight', 'height'], [])
    """
    if mode not in ("general", "patient"):
        raise ValueError(f"unknown mode {mode!r}")
    ex = as_example(example)
    entities = ex.entities
    d = derive(ex.calculator_id, entities)
    symbols = list(d.inputs)
    units = (formula_units or {}).get(ex.calculator_id, {})
    scale = _unit_scales(units, symbols)
    docs = {s: symbol_doc(s, entities, symbol_docs) for s in symbols}
    for s, unit in units.items():
        if not (symbol_docs and s in symbol_docs):
            docs[s] = docs[s].replace(f"({UNIT_TABLE[VARIABLE_FIELDS[s]][2]})", f"({unit})")
    fields = {
        "question": task_question(ex.question),
        "context": "\n".join(categorical_context(entities)) or "- (none)",
        "variables": "\n".join(f"- {s}: {docs[s]}" for s in symbols),
        "values": "\n".join(f"- {s} = {fmt(v * scale.get(s, 1.0), digits)}" for s, v in d.inputs.items()),
    }
    templates = ({**TEMPLATES, **DEFINITION_TEMPLATES} if mode == "general"
                 else {**PATIENT_TEMPLATES, **DEFINITION_PATIENT_TEMPLATES})
    name, text = resolve_template(template, templates)
    user = render(text, **fields)
    reference: dict[str, Any] = {"entities": entities, "symbols": symbols, "answer": d.answer}
    points = None
    if point_pool and ex.calculator_id not in PERTURB_ONLY:
        if mode == "general":
            points = [with_categorical(p, entities) for p in point_pool[:n_points]]
        else:
            points = _same_branch_points(point_pool, entities, ex.calculator_id, d.branches, n_points)
    reference["point_entities"] = points
    if scale:
        reference.update(variable_units=units, variable_scale=scale)
    if mode == "patient":
        reference.update(mode="patient", branches=d.branches)
    return make_item(ex, label, user, reference, max_new_tokens, system_prompt, task="K", template=(name, text))


def _unit_scales(units: dict[str, str], symbols: list[str]) -> dict[str, float]:
    """{variable: factor} from the registry's unit to `units[variable]` (values in the new unit = factor * value)."""
    scale = {}
    for s, unit in units.items():
        if s not in symbols or s not in VARIABLE_FIELDS:
            raise ValueError(f"cannot give {s!r} in another unit: convertible variables of this formula are "
                             f"{[v for v in symbols if v in VARIABLE_FIELDS]}")
        _, analyte, canonical, _ = UNIT_TABLE[VARIABLE_FIELDS[s]]
        scale[s] = convert(1.0, canonical, unit, analyte)
    return scale


# ---------------------------------------------------------------- score

def perturb_entities(entities: dict[str, Any], rng: random.Random,
                     factor: float = DEFAULT_PERTURBATION_FACTOR) -> dict[str, Any]:
    """Multiply every continuous value by a log-uniform factor in [1/factor, factor]; keep categorical fields;
    daily administration counts become random integers in 1..6.

    >>> p = perturb_entities({"sex": "Male", "weight": [70.0, "kg"]}, random.Random(0))
    >>> p["sex"], p["weight"][1], 70 / 3 <= p["weight"][0] <= 70 * 3
    ('Male', 'kg', True)
    """
    def f(x: float) -> float:
        return x * math.exp(rng.uniform(-math.log(factor), math.log(factor)))

    out: dict[str, Any] = {}
    for k, v in entities.items():
        if isinstance(v, bool) or isinstance(v, str):
            out[k] = v
        elif isinstance(v, (int, float)):
            out[k] = f(v)
        elif isinstance(v, list) and len(v) == 2 and v[1] == "per day":
            out[k] = [rng.randint(1, 6), v[1]]           # administrations per day: a positive integer count
        elif isinstance(v, list):
            out[k] = [f(x) if isinstance(x, (int, float)) and not isinstance(x, bool) else x for x in v]
        else:
            out[k] = v
    return out


def eval_cases(cases: list[tuple[str | None, expr.Node | None]], env: dict[str, float],
               semantics: str = "all_agree") -> float:
    """Value of a piecewise answer at one point. Raises ExprError if no case (or an undefined one) applies.

    semantics: "all_agree" — every case whose condition holds must give the same value;
               "first_match" — the first case (in the written order) whose condition holds is used.
    "otherwise" applies when no other condition holds.

    >>> cases = [("x < 10", expr.parse("2 * x")), ("otherwise", expr.parse("x"))]
    >>> eval_cases(cases, {"x": 3}), eval_cases(cases, {"x": 30})
    (6.0, 30.0)
    """
    if semantics not in CASE_SEMANTICS:
        raise ValueError(f"unknown case semantics {semantics!r}")
    matched, fallback = [], None
    for cond, node in cases:
        if cond is not None and cond.strip().lower() in expr.OTHERWISE:
            fallback = node
            continue
        if expr.evaluate_condition(cond, env):
            matched.append(node)
            if semantics == "first_match":
                break
    if not matched and fallback is not None:
        matched = [fallback]
    if not matched:
        raise expr.ExprError("no case applies")
    if any(n is None for n in matched):
        raise expr.ExprError("an 'undefined' branch applies at a valid point")
    values = [expr.evaluate(n, env) for n in matched]
    if any(not math.isclose(v, values[0], rel_tol=1e-9, abs_tol=1e-12) for v in values):
        raise expr.ExprError("overlapping cases disagree")
    return values[0]


def _in_ranges(inputs: dict[str, float], ranges: dict[str, tuple[float, float]] | None) -> bool:
    return ranges is None or all(ranges[k][0] <= v <= ranges[k][1] for k, v in inputs.items() if k in ranges)


def test_points(reference: dict[str, Any], calculator_id: str, seed: int, n_points: int = DEFAULT_N_POINTS,
                perturbation_factor: float = DEFAULT_PERTURBATION_FACTOR,
                plausible_ranges: dict[str, tuple[float, float]] | None = PLAUSIBLE_RANGES
                ) -> list[tuple[dict[str, float], float]]:
    """(canonical inputs, registry value) at the patient point + up to n_points other points: the reference's
    pool points, or perturbations of the patient as a fallback. Perturbed points must lie in the patient's
    branch ("patient" mode) and within `plausible_ranges` (default data.PLAUSIBLE_RANGES; None = no bound).

    >>> pts = test_points(build(mk.data.demo()[1])["reference"], "6", seed=0, n_points=3)
    >>> len(pts), pts[0]
    (4, ({'weight': 70.0, 'height': 175.0}, 22.857142857142858))
    """
    rng = random.Random(seed)
    pool = reference.get("point_entities")
    others = pool or [perturb_entities(reference["entities"], rng, perturbation_factor)
                      for _ in range(3 * n_points)]
    branches = reference.get("branches")
    pts = []
    for i, ent in enumerate([reference["entities"]] + list(others)):
        try:
            d = derive(calculator_id, ent)
            if not math.isfinite(d.answer):
                continue
            if i > 0 and not pool:
                if branches is not None and d.branches != branches:
                    continue
                if not _in_ranges(d.inputs, plausible_ranges):
                    continue
            pts.append((dict(d.inputs), d.answer))
        except Exception:  # noqa: BLE001 - domain errors of the reference at extreme points are skipped
            continue
        if len(pts) == n_points + 1:
            break
    return pts


test_points.__test__ = False  # not a pytest test despite its name


def _parse_cases(text: str) -> tuple[list[dict[str, Any]] | None, Any]:
    """(cases, raw definitions) of an answer; cases is None without a JSON formula."""
    obj = extract_json(text)
    raw_cases = obj.get("cases") if isinstance(obj, dict) else None
    if isinstance(obj, dict) and raw_cases is None and "formula" in obj:
        raw_cases = [{"condition": "always", "formula": obj["formula"]}]
    definitions = obj.get("definitions") if isinstance(obj, dict) else None
    return (raw_cases if isinstance(raw_cases, list) and raw_cases else None), definitions


def _definition_items(raw: Any) -> list[tuple[Any, Any]] | None:
    """[(name, expression)] from {name: expression} or [{"name", "expression"}]; None if neither."""
    if raw is None:
        return []
    if isinstance(raw, dict):
        return list(raw.items())
    if isinstance(raw, list) and all(isinstance(d, dict) for d in raw):
        return [(d.get("name"), d.get("expression", d.get("formula"))) for d in raw]
    return None


def with_definitions(definitions: list[tuple[str, expr.Node]], env: dict[str, float]) -> dict[str, float]:
    """The point's variables plus the defined quantities, evaluated in order.

    >>> with_definitions([("rr", expr.parse("60 / hr"))], {"hr": 120.0, "qt": 400.0})
    {'hr': 120.0, 'qt': 400.0, 'rr': 0.5}
    """
    env = dict(env)
    for name, node in definitions:
        env[name] = expr.evaluate(node, env)
    return env


def score_answer(reference: dict[str, Any], text: str, calculator_id: str, seed: int = 0, *,
                 rel_tol: float = DEFAULT_REL_TOL, abs_tol: dict[str, float] | None = None,
                 n_points: int = DEFAULT_N_POINTS, case_semantics: str = "all_agree",
                 perturbation_factor: float = DEFAULT_PERTURBATION_FACTOR,
                 plausible_ranges: dict[str, tuple[float, float]] | None = PLAUSIBLE_RANGES,
                 min_pass_rate: float = DEFAULT_MIN_PASS_RATE, details: bool = False) -> dict[str, Any]:
    """Score a model answer against a K reference.

    rel_tol: relative tolerance at each point; abs_tol: per-calculator absolute tolerance replacing rel_tol
    (default DEFAULT_ABS_TOL; {} to disable); n_points: test points besides the patient's; case_semantics:
    "all_agree" or "first_match" (see eval_cases); perturbation_factor, plausible_ranges: see test_points.
    min_pass_rate: share of the test points the formula must be right at (default 1.0, all of them); a formula
    wrong at the patient's point is never correct, whatever the threshold.
    details=True adds `points`: one row per test point (inputs, registry value, model value, ok).

    >>> ref = build(mk.data.demo()[1])["reference"]
    >>> v = score_answer(ref, '{"formula": "weight / height^2"}', "6", details=True)   # forgot cm -> m
    >>> v["error_type"], v["point_pass_rate"]
    ('wrong_at_patient_point', 0.0)
    >>> pd.DataFrame(v["points"]).head(2).round(4)
        weight    height  registry   model     ok
    0  70.0000  175.0000   22.8571  0.0023  False
    1  58.7901  103.0353   55.3773  0.0055  False
    """
    raw_cases, raw_definitions = _parse_cases(text)
    if raw_cases is None:
        return {"format_valid": False, "correct": False, "error_type": "format_invalid", "point_pass_rate": 0.0}
    definition_items = _definition_items(raw_definitions)
    if definition_items is None:
        return {"format_valid": True, "correct": False, "error_type": "invalid_definition", "point_pass_rate": 0.0}
    allowed = set(reference["symbols"])
    cases, definitions = [], []
    try:
        for c in raw_cases:
            formula = c["formula"]
            if not isinstance(formula, str) or not formula.strip():
                raise TypeError("no formula")
            # an 'undefined' branch excludes a domain (e.g. height <= 0); it fails only if it applies at a test point
            undefined = formula.strip().lower() in UNDEFINED_FORMULAS
            node = None if undefined else expr.parse(formula)
            cond = c.get("condition")
            cases.append((None if cond is None else str(cond), node))
        # keep the definitions the formula uses (directly or through a later definition), latest first
        needed = set().union(*(expr.variables(n) for _, n in cases if n is not None),
                             *(set(re.findall(r"[A-Za-z_]\w*", cond)) for cond, _ in cases if cond))
        for name, text_def in reversed(definition_items):
            if name not in needed or (name in allowed and isinstance(text_def, str) and text_def.strip() == name):
                continue
            if not (isinstance(name, str) and name.isidentifier() and name not in allowed
                    and isinstance(text_def, str) and text_def.strip()):
                return {"format_valid": True, "correct": False, "error_type": "invalid_definition",
                        "point_pass_rate": 0.0}
            node = expr.parse(text_def)
            definitions.insert(0, (name, node))
            needed |= expr.variables(node)
    except (KeyError, TypeError):
        return {"format_valid": False, "correct": False, "error_type": "unparsable_formula", "point_pass_rate": 0.0}
    except expr.ExprError as exc:
        # The answer has the requested format (a JSON formula) but not a formula of the grammar: a knowledge error
        # (e.g. an undefined helper such as ideal_body_weight(height), or Python syntax), not a generation artifact.
        kind = "undefined_function" if str(exc).startswith("unknown function") else "invalid_syntax"
        return {"format_valid": True, "correct": False, "error_type": kind, "point_pass_rate": 0.0,
                "error_detail": str(exc)}

    unknown, known = set(), set(allowed)
    for name, node in definitions:              # a definition uses the variables and the definitions before it
        unknown |= expr.variables(node) - known
        known.add(name)
    unknown |= set().union(*(expr.variables(n) for _, n in cases if n is not None)) - known
    if unknown:
        return {"format_valid": True, "correct": False, "error_type": "unknown_variable",
                "point_pass_rate": 0.0, "unknown_variables": sorted(unknown)}

    tol_abs = (DEFAULT_ABS_TOL if abs_tol is None else abs_tol).get(calculator_id)
    points = test_points(reference, calculator_id, seed, n_points, perturbation_factor, plausible_ranges)
    scale = reference.get("variable_scale") or {}
    points = [({k: v * scale.get(k, 1.0) for k, v in env.items()}, gold) for env, gold in points]
    passes, rows = [], []
    for env, gold in points:
        try:
            v = eval_cases(cases, with_definitions(definitions, env) if definitions else env, case_semantics)
            ok = abs(v - gold) <= tol_abs if tol_abs is not None else rel_close(v, gold, rel_tol)
        except expr.ExprError:
            v, ok = math.nan, False
        passes.append(ok)
        rows.append({**env, "registry": gold, "model": v, "ok": ok})
    rate = sum(passes) / len(passes)
    correct = passes[0] and rate >= min_pass_rate
    out = {
        "format_valid": True,
        "correct": correct,
        "error_type": None if correct else ("wrong_at_patient_point" if not passes[0] else "wrong_elsewhere"),
        "point_pass_rate": rate,
        "original_point_correct": passes[0],
        "n_points": len(passes),
    }
    return {**out, "points": rows} if details else out


def score(item: Item, text: str, **options: Any) -> dict[str, Any]:
    """Score a model answer for a K item. Options: see score_answer (rel_tol, abs_tol, n_points, case_semantics,
    perturbation_factor, plausible_ranges, min_pass_rate, details). The perturbation seed is derived from the item
    id, so scores are reproducible.

    >>> item = build(mk.data.demo()[1])
    >>> score(item, '{"cases": [{"condition": "always", "formula": "weight / (height / 100)^2"}]}')["n_points"]
    51
    >>> score(item, '{"cases": [{"condition": "always", "formula": "w / h^2"}]}')["unknown_variables"]
    ['h', 'w']

    A formula right at the patient's point but not everywhere can be accepted with a lower threshold:

    >>> almost = '{"cases": [{"condition": "height > 220", "formula": "0"}, ' \\
    ...          '{"condition": "otherwise", "formula": "weight / (height / 100)^2"}]}'
    >>> v = score(item, almost)
    >>> v["correct"], v["error_type"], round(v["point_pass_rate"], 2)
    (False, 'wrong_elsewhere', 0.94)
    >>> score(item, almost, min_pass_rate=0.9)["correct"]
    True
    """
    return score_answer(item["reference"], text, item["calculator_id"],
                        seed=zlib.crc32(item["item_id"].encode()), **options)


def reference_answer(item: Item) -> str:
    """The registry's formula for this patient's branch, in the expected JSON format. Always correct in "patient"
    mode; in "general" mode it is correct only for calculators without branches, since the registry resolves
    branch conditions in code and does not store them as formulas.

    >>> reference_answer(build(mk.data.demo()[1], mode="patient"))
    '{"formula": "weight / (height / 100)^2"}'
    """
    ref = item["reference"]
    node = inline(derive(item["calculator_id"], ref["entities"]))
    # variables given in another unit: the registry's variable is the given one divided by its factor
    scale = ref.get("variable_scale") or {}
    node = expr.replace_vars(node, {s: expr.parse(f"{s} / {f!r}") for s, f in scale.items()})
    formula = expr.to_str(node)
    if ref.get("mode") == "patient":
        return json.dumps({"formula": formula})
    return json.dumps({"cases": [{"condition": "always", "formula": formula}]})


PROBE = Probe("K", "Knowledge", "writing the formula (general, or for this patient) without computing", build,
              score, reference_answer)
