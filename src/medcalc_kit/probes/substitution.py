"""S — Substitution: can the model plug the values into a GIVEN formula?

Prompt: the formula of this patient's branch (resolved by the registry) and the value of each variable.
The model must copy the formula, replacing each variable by its value, without computing anything.
Scoring: (1) structural identity with the expected substituted expression (canonical form, so reordering is
accepted); otherwise (2) literals are mapped back to variables and the result is tested for numerical
equivalence with the formula. Checking the value alone is not enough: a partly computed answer has the right
value without being a substitution, and two swapped variables can give the right value by accident.

Error types: format_invalid, unparsable_expression, unsubstituted_variable (a variable name left in),
premature_computation (part of it computed: right value, missing literals), missing_or_wrong_value,
accidental_value_match (right value, wrong structure), structure_or_assignment_error, too_ambiguous.

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
    rel_close,
    render,
    symbol_doc,
)

_MAX_ASSIGNMENTS = 4096
DEFAULT_MAX_NEW_TOKENS = 768
DEFAULT_EQUIV_REL_TOL = 1e-6     # numerical equivalence of the symbolic forms
DEFAULT_VALUE_REL_TOL = 1e-4     # `value_matches` diagnostic only
# Placeholders: {calculator_name}, {target} (name of the result), {formula}, {values} (one line per variable).
DEFAULT_TEMPLATE = (
    "Formula for {calculator_name}:\n{target} = {formula}\n\n"
    "Variable values:\n{values}\n\n"
    "Substitute the values into the formula. Do NOT compute or simplify anything: copy the formula exactly, "
    "replacing each variable by its value.\n\n"
    'End your answer with a JSON object of the form {"expression": "<formula with the values substituted>"}'
)


def build(example: Example | dict[str, Any], *, template: str = DEFAULT_TEMPLATE,
          max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS, system_prompt: str | None = DEFAULT_SYSTEM_PROMPT,
          digits: int = DEFAULT_DIGITS, symbol_docs: dict[str, str] | None = None, label: str = "S") -> Item:
    """The item for one example: the formula of this patient's branch and the values, to be substituted.

    template: prompt text, placeholders {calculator_name}, {target}, {formula}, {values}; max_new_tokens: token
    budget; system_prompt: None for none; digits: significant digits of the values shown (the expected
    expression uses the same values); symbol_docs: {variable: description} overriding common.SYMBOL_DOCS;
    label: the item's probe name.

    >>> item = build(mk.data.demo()[1], system_prompt=None)
    >>> print(item["messages"][0]["content"])
    Formula for Body Mass Index (BMI):
    bmi = weight / (height / 100)^2
    <BLANKLINE>
    Variable values:
    - weight = 70   (body weight (kg))
    - height = 175   (height (cm))
    ...
    """
    ex = as_example(example)
    formula, values, d = branch_formula(ex, digits)
    formula_str = expr.to_str(formula)
    val_lines = "\n".join(f"- {k} = {fmt(v, digits)}   ({symbol_doc(k, ex.entities, symbol_docs)})"
                          for k, v in values.items())
    user = render(template, calculator_name=ex.calculator_name, target=d.steps[-1].name, formula=formula_str,
                  values=val_lines)
    gold_expr = expr.to_str(expr.substitute(formula, values))
    return make_item(ex, label, user, {
        "formula": formula_str, "values": values, "gold_expression": gold_expr,
        "gold_value": expr.evaluate(gold_expr),
    }, max_new_tokens, system_prompt, task="S")


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
    options = []
    for lit in lits:
        cands = [k for k, v in values.items() if rel_close(lit, v, 1e-9) or (lit == 0 and v == 0)]
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
