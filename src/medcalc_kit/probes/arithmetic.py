"""A — Arithmetic: can the model compute a fully written numerical expression?

Prompt: the expected answer of S (formula with the patient's values substituted). The model may work it out
step by step, then gives {"result": <number>}.
Scoring: relative error <= rel_tol (primary) and <= strict_rel_tol (reported as `correct_strict`).
Error types: format_invalid (no {"result": ...}), arithmetic_error.

    >>> item = build(mk.data.demo()[1])                         # BMI
    >>> item["reference"]["expression"]
    '70 / (175 / 100)^2'
    >>> score(item, 'Step by step... {"result": 22.86}')["correct"]
    True
"""
from __future__ import annotations

import json
import math
from typing import Any

from medcalc_kit import expr
from medcalc_kit.data import Example, as_example
from medcalc_kit.probes.base import Probe
from medcalc_kit.probes.common import (
    DEFAULT_DIGITS,
    DEFAULT_SYSTEM_PROMPT,
    Item,
    branch_formula,
    make_item,
    numeric_answer,
    render,
    resolve_template,
)

DEFAULT_MAX_NEW_TOKENS = 1024
DEFAULT_REL_TOL = 0.01
DEFAULT_STRICT_REL_TOL = 0.001
# Placeholder: {expression}.
DEFAULT_TEMPLATE = (
    "Compute the value of the following expression (ln is the natural logarithm, log10 the base-10 "
    "logarithm, round(x, n) rounds x to n decimals, ^ is exponentiation):\n\n"
    "{expression}\n\n"
    "Work carefully without any tool. End your answer with a JSON object of the form "
    '{"result": <number with at least 4 significant digits>}'
)
# Paraphrases of the default template: the same information, conventions and answer format, worded differently, to
# measure how much a result depends on the wording (see evaluate_model(prompt_variants=...)). "v1" is the default.
TEMPLATES = {
    "v1": DEFAULT_TEMPLATE,
    "v2": ("Calculate the following expression without using any tool:\n\n"
           "{expression}\n\n"
           "Notation: ^ is exponentiation, ln the natural logarithm, log10 the base-10 logarithm, and round(x, n) "
           "rounds x to n decimal places.\n\n"
           'Show your work if you wish, then give the result as a JSON object {"result": <number with at least 4 '
           'significant digits>}'),
    "v3": ("Expression: {expression}\n"
           "(^ = power, ln = natural log, log10 = base-10 log, round(x, n) = x rounded to n decimals)\n\n"
           "What is its value? Compute it yourself, then end with "
           '{"result": <number with at least 4 significant digits>}'),
}


def build(example: Example | dict[str, Any], *, template: str = DEFAULT_TEMPLATE,
          max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS, system_prompt: str | None = DEFAULT_SYSTEM_PROMPT,
          digits: int = DEFAULT_DIGITS, label: str = "A") -> Item:
    """The item for one example: compute this patient's formula with the values already substituted.

    template: prompt text with placeholder {expression}, or the name of a variant of TEMPLATES ("v1", "v2", "v3");
    max_new_tokens: token budget; system_prompt: None for none;
    digits: significant digits of the patient values inside the expression; label: the item's probe name.

    >>> item = build(mk.data.demo()[2], template='Compute {expression}. Reply {"result": <number>}.',
    ...              system_prompt=None)
    >>> item["messages"]
    [{'role': 'user', 'content': 'Compute 140 - (104 + 24). Reply {"result": <number>}.'}]
    >>> item["reference"]
    {'expression': '140 - (104 + 24)', 'gold_value': 12.0}
    """
    ex = as_example(example)
    formula, values, _ = branch_formula(ex, digits)
    expression = expr.to_str(expr.substitute(formula, values))
    name, text = resolve_template(template, TEMPLATES)
    user = render(text, expression=expression)
    return make_item(ex, label, user, {"expression": expression, "gold_value": expr.evaluate(expression)},
                     max_new_tokens, system_prompt, task="A", template=(name, text))


def score_answer(reference: dict[str, Any], text: str, *, rel_tol: float = DEFAULT_REL_TOL,
                 strict_rel_tol: float = DEFAULT_STRICT_REL_TOL) -> dict[str, Any]:
    """Score a model answer against an A reference ({"expression", "gold_value"}).

    >>> score_answer({"expression": "1/3", "gold_value": 1 / 3}, '{"result": 0.333}')
    {'format_valid': True, 'correct': True, 'correct_strict': True, 'error_type': None, 'rel_error': 0.000999...}
    >>> score_answer({"expression": "1/3", "gold_value": 1 / 3}, '{"result": 0.33}')["correct_strict"]
    False
    """
    v = numeric_answer(text, "result")
    if v is None:
        return {"format_valid": False, "correct": False, "correct_strict": False,
                "error_type": "format_invalid", "rel_error": math.nan}
    gold = reference["gold_value"]
    rel = abs(v - gold) / max(abs(gold), 1e-12)
    return {"format_valid": True, "correct": rel <= rel_tol, "correct_strict": rel <= strict_rel_tol,
            "error_type": None if rel <= rel_tol else "arithmetic_error", "rel_error": rel}


def score(item: Item, text: str, **options: Any) -> dict[str, Any]:
    """Score a model answer for an A item. Options: rel_tol (default 1 %), strict_rel_tol (default 0.1 %).

    >>> item = build(mk.data.demo()[2])
    >>> score(item, '{"result": 12.1}')["correct"], score(item, '{"result": 12.1}', rel_tol=0.001)["correct"]
    (True, False)
    """
    return score_answer(item["reference"], text, **options)


def reference_answer(item: Item) -> str:
    """A correct answer: the gold value in the expected JSON format.

    >>> reference_answer(build(mk.data.demo()[2]))
    '{"result": 12.0}'
    """
    return json.dumps({"result": item["reference"]["gold_value"]})


PROBE = Probe("A", "Arithmetic", "computing a fully written numerical expression", build, score, reference_answer)
