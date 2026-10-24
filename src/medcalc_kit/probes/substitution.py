"""S — Substitution: can the model plug the values into a GIVEN formula?

Prompt: the formula of this patient's branch (resolved by the registry) and the value of each variable.
The model must copy the formula, replacing each variable by its value, without computing anything.
Scoring: (1) structural identity with the expected substituted expression (canonical form, so reordering is
accepted); otherwise (2) literals are mapped back to variables and the result is tested for numerical
equivalence with the formula. Checking the value alone is not enough: a partly computed answer has the right
value without being a substitution, and two swapped variables can give the right value by accident.

Error types: format_invalid, unparsable_expression, unsubstituted_variable (a variable name left in),
premature_computation (part of it computed: right value, missing literals), missing_or_wrong_value,
accidental_value_match (right value, wrong structure), structure_or_assignment_error, too_ambiguous, and with
`value_units` unconverted_value (a value copied in the unit it was given in).

Variant "S+U": `build(example, value_units={"scr": "µmol/L"})` gives some values in another unit than the formula's;
the model converts them while substituting. The reference stays the expression in the formula's units, and the
numbers of the answer are matched to the variables within DEFAULT_CONVERTED_REL_TOL (rounding of the conversion).

    >>> item = build(mk.data.demo()[2])                         # anion gap
    >>> item["reference"]["formula"], item["reference"]["gold_expression"]
    ('na - (cl + hco3)', '140 - (104 + 24)')
    >>> score(item, '{"expression": "140 - (24 + 104)"}')["match"]     # reordering is accepted
    'canonical'
    >>> score(item, '{"expression": "140 - 128"}')["error_type"]
    'premature_computation'
"""
from __future__ import annotations

import itertools
import json
import math
import random
from typing import Any

from medcalc_kit import expr
from medcalc_kit.data import Example, as_example
from medcalc_kit.parsing import extract_json
from medcalc_kit.probes.base import Probe
from medcalc_kit.probes.common import (
    DEFAULT_DIGITS,
    DEFAULT_SYSTEM_PROMPT,
    Item,
    branch_formula,
    fmt,
    make_item,
    presented,
    rel_close,
    render,
    resolve_template,
    symbol_doc,
)
from medcalc_kit.units import convert

_MAX_ASSIGNMENTS = 4096
DEFAULT_MAX_NEW_TOKENS = 768
DEFAULT_EQUIV_REL_TOL = 1e-6     # numerical equivalence of the symbolic forms
DEFAULT_VALUE_REL_TOL = 1e-4     # `value_matches` diagnostic only
DEFAULT_LITERAL_REL_TOL = 1e-9   # matching a number of the answer to a value shown
DEFAULT_CONVERTED_REL_TOL = 0.01  # the same, for values the model had to convert ("S+U")
# Added after the values when some are given in another unit (value_units).
CONVERSION_NOTE = ("Some values are given in a different unit from the one in parentheses: convert them to the unit "
                   "in parentheses before substituting them.")
# Placeholders: {calculator_name}, {target} (name of the result), {formula}, {values} (one line per variable).
DEFAULT_TEMPLATE = (
    "Formula for {calculator_name}:\n{target} = {formula}\n\n"
    "Variable values:\n{values}\n\n"
    "Substitute the values into the formula. Do NOT compute or simplify anything: copy the formula exactly, "
    "replacing each variable by its value.\n\n"
    'End your answer with a JSON object of the form {"expression": "<formula with the values substituted>"}'
)

# Paraphrases of the default template: the same information, conventions and answer format, worded differently, to
# measure how much a result depends on the wording (see evaluate_model(prompt_variants=...)). "v1" is the default.
TEMPLATES = {
    "v1": DEFAULT_TEMPLATE,
    "v2": ("Here is the formula used for {calculator_name}:\n\n{target} = {formula}\n\n"
           "and the values of its variables:\n{values}\n\n"
           "Rewrite the formula with each variable replaced by its value. Keep every operation, constant and "
           "parenthesis as it is: do not calculate, round or simplify anything.\n\n"
           'Finish with a JSON object {"expression": "<formula with the values substituted>"}'),
    "v3": ("{calculator_name}\nFormula: {target} = {formula}\nValues:\n{values}\n\n"
           "Plug the values into the formula without evaluating it (no arithmetic, no simplification). "
           'End with {"expression": "<formula with the values substituted>"}'),
}


def build(example: Example | dict[str, Any], *, template: str = DEFAULT_TEMPLATE,
          max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS, system_prompt: str | None = DEFAULT_SYSTEM_PROMPT,
          digits: int = DEFAULT_DIGITS, symbol_docs: dict[str, str] | None = None, label: str | None = None,
          value_units: dict[str, str] | None = None) -> Item:
    """The item for one example: the formula of this patient's branch and the values, to be substituted.

    template: prompt text with placeholders {calculator_name}, {target}, {formula}, {values}, or the name of a
    variant of TEMPLATES ("v1", "v2", "v3"); max_new_tokens: token
    budget; system_prompt: None for none; digits: significant digits of the values shown (the expected
    expression uses the same values); symbol_docs: {variable: description} overriding common.SYMBOL_DOCS;
    label: the item's probe name (default "S", or "S+U" with value_units); value_units: {variable: unit} gives
    those values in another unit (see conversion.VARIABLE_FIELDS and UNIT_TABLE for the supported ones).

    >>> item = build(mk.data.demo()[1], system_prompt=None)
    >>> print(item["messages"][0]["content"])
    Formula for Body Mass Index (BMI):
    bmi = weight / (height / 100)^2
    <BLANKLINE>
    Variable values:
    - weight = 70   (body weight (kg))
    - height = 175   (height (cm))
    ...

    With a value in another unit ("S+U"):

    >>> item = build(mk.data.demo()[0], value_units={"scr": "µmol/L"})        # creatinine 0.76 mg/dL
    >>> item["probe"], [ln for ln in item["messages"][-1]["content"].splitlines() if ln.startswith("- scr")]
    ('S+U', ['- scr = 67.19 µmol/L   (serum creatinine (mg/dL))'])
    >>> score(item, mk.reference_answer(item))["correct"], score(item, '{"expression": "%s"}' %
    ...       item["reference"]["gold_expression"].replace("0.760053", "0.76"))["correct"]
    (True, True)
    """
    from medcalc_kit.probes.conversion import DEFAULT_DIGITS as UNIT_DIGITS
    from medcalc_kit.probes.conversion import UNIT_TABLE, VARIABLE_FIELDS

    ex = as_example(example)
    formula, values, d = branch_formula(ex, digits)
    formula_str = expr.to_str(formula)
    shown = {k: fmt(v, digits) for k, v in values.items()}
    converted: dict[str, float] = {}
    for var, unit in (value_units or {}).items():
        if var not in values or var not in VARIABLE_FIELDS:
            raise ValueError(f"cannot give {var!r} in another unit: convertible variables of this formula are "
                             f"{[v for v in values if v in VARIABLE_FIELDS]}")
        _, analyte, canonical, _ = UNIT_TABLE[VARIABLE_FIELDS[var]]
        converted[var] = float(fmt(convert(values[var], canonical, unit, analyte), UNIT_DIGITS))  # as on a lab report
        values[var] = presented(convert(converted[var], unit, canonical, analyte), digits)
        shown[var] = f"{fmt(converted[var], UNIT_DIGITS)} {unit}"
    val_lines = "\n".join(f"- {k} = {shown[k]}   ({symbol_doc(k, ex.entities, symbol_docs)})" for k in values)
    if converted:
        val_lines += "\n\n" + CONVERSION_NOTE
    name, text = resolve_template(template, TEMPLATES)
    user = render(text, calculator_name=ex.calculator_name, target=d.steps[-1].name, formula=formula_str,
                  values=val_lines)
    gold_expr = expr.to_str(expr.substitute(formula, values))
    reference = {"formula": formula_str, "values": values, "gold_expression": gold_expr,
                 "gold_value": expr.evaluate(gold_expr)}
    if converted:
        reference.update(value_units=dict(value_units), shown_values=converted,
                         literal_rel_tol=DEFAULT_CONVERTED_REL_TOL)
    label = label or ("S+U" if converted else "S")
    return make_item(ex, label, user, reference, max_new_tokens, system_prompt, task="S", template=(name, text))


def _equivalent(a: expr.Node, b: expr.Node, symbols: dict[str, float], seed: int = 0,
                rel_tol: float = DEFAULT_EQUIV_REL_TOL) -> bool:
    """Numerical equivalence on small perturbations of the presented values (keeps branches and avoids
    overflow in exp/ln-heavy formulas). Points where both sides fail are skipped."""
    rng = random.Random(seed)
    n_valid = 0
    for _ in range(12):
        env = {k: (v if v != 0 else 1.0) * rng.uniform(0.9, 1.1) for k, v in symbols.items()}
        try:
            va = expr.evaluate(a, env)
        except expr.ExprError:
            va = None
        try:
            vb = expr.evaluate(b, env)
        except expr.ExprError:
            vb = None
        if va is None and vb is None:
            continue
        if va is None or vb is None or not math.isclose(va, vb, rel_tol=rel_tol, abs_tol=1e-12):
            return False
        n_valid += 1
    return n_valid >= 3


def score_answer(reference: dict[str, Any], text: str, *, equiv_rel_tol: float = DEFAULT_EQUIV_REL_TOL,
                 value_rel_tol: float = DEFAULT_VALUE_REL_TOL) -> dict[str, Any]:
    """Score a model answer against an S reference ({"formula", "values", "gold_expression", "gold_value"}).

    equiv_rel_tol: tolerance of the numerical equivalence test; value_rel_tol: tolerance of `value_matches`.

    >>> ref = build(mk.data.demo()[2])["reference"]
    >>> score_answer(ref, '{"expression": "140 - (104 + 24)"}')
    {'format_valid': True, 'correct': True, 'error_type': None, 'value_matches': True, 'missing_variables': [],
     'match': 'canonical'}
    >>> score_answer(ref, '{"expression": "140 - 104 + 24"}')["error_type"]      # wrong structure
    'structure_or_assignment_error'
    """
    obj = extract_json(text)
    expression = obj.get("expression") if isinstance(obj, dict) else None
    if not isinstance(expression, str):
        return {"format_valid": False, "correct": False, "error_type": "format_invalid", "value_matches": False}
    try:
        node = expr.parse(expression.split("=")[-1])  # tolerate "crcl = ..."
    except expr.ExprError:
        return {"format_valid": False, "correct": False, "error_type": "unparsable_expression", "value_matches": False}

    values: dict[str, float] = reference["values"]
    gold_formula = expr.parse(reference["formula"])
    if expr.variables(node):
        return {"format_valid": True, "correct": False, "error_type": "unsubstituted_variable", "value_matches": False}

    try:
        value_matches = rel_close(expr.evaluate(node), reference["gold_value"], value_rel_tol)
    except expr.ExprError:
        value_matches = False

    # 1) faithful copy, possibly reordered: structural identity with the gold substituted expression
    if expr.canonical(node) == expr.canonical(reference["gold_expression"]):
        return {"format_valid": True, "correct": True, "error_type": None,
                "value_matches": value_matches, "missing_variables": [], "match": "canonical"}

    # 2) otherwise map literals back to variables and test symbolic equivalence
    lits = expr.literals(node)
    lit_tol = reference.get("literal_rel_tol", DEFAULT_LITERAL_REL_TOL)
    options = []
    for lit in lits:
        cands = [k for k, v in values.items() if rel_close(lit, v, lit_tol) or (lit == 0 and v == 0)]
        options.append([None] + cands)  # None = keep as constant
    present = {k for opts in options for k in opts if k}
    missing = sorted(set(values) - present)

    correct = False
    n_combos = math.prod(len(o) for o in options)
    if not missing and n_combos <= _MAX_ASSIGNMENTS:
        for combo in itertools.product(*options):
            if set(values) - {c for c in combo if c}:
                continue
            sym = expr.map_literals(
                node, lambda i, v: expr.Var(combo[i]) if combo[i] else expr.Num(v))  # noqa: B023 - used at once
            if _equivalent(sym, gold_formula, values, rel_tol=equiv_rel_tol):
                correct = True
                break
    if correct:
        err = None
    elif n_combos > _MAX_ASSIGNMENTS:
        err = "too_ambiguous"
    elif missing and any(rel_close(lit, reference.get("shown_values", {}).get(k, math.nan), lit_tol)
                         for k in missing for lit in lits):
        err = "unconverted_value"
    elif missing:
        err = "premature_computation" if value_matches else "missing_or_wrong_value"
    else:
        err = "accidental_value_match" if value_matches else "structure_or_assignment_error"
    return {"format_valid": True, "correct": correct, "error_type": err,
            "value_matches": value_matches, "missing_variables": missing,
            "match": "equivalence" if correct else None}


def score(item: Item, text: str, **options: Any) -> dict[str, Any]:
    """Score a model answer for an S item. Options: equiv_rel_tol, value_rel_tol (see score_answer).

    >>> score(build(mk.data.demo()[2]), '{"expression": "na - (104 + 24)"}')["error_type"]
    'unsubstituted_variable'
    """
    return score_answer(item["reference"], text, **options)


def reference_answer(item: Item) -> str:
    """A correct answer: the expected substituted expression in the expected JSON format.

    >>> reference_answer(build(mk.data.demo()[2]))
    '{"expression": "140 - (104 + 24)"}'
    """
    return json.dumps({"expression": item["reference"]["gold_expression"]})


PROBE = Probe("S", "Substitution", "plugging the values into a given formula, without computing", build, score,
              reference_answer)
