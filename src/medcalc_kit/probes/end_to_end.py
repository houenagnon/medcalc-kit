"""E2E — End to end: the original MedCalc-Bench task (note + question -> number).

Scoring: the answer must fall within the benchmark's [Lower Limit, Upper Limit] interval, or, if `rel_tol` is
given, within rel_tol of the ground truth. Error types: format_invalid (no {"answer": ...}), out_of_bounds.

    >>> item = build(mk.data.demo()[2])                         # anion gap, ground truth 12
    >>> score(item, '{"answer": 12.4}')["correct"], score(item, '{"answer": 13}')["error_type"]
    (True, 'out_of_bounds')
"""
from __future__ import annotations

import json
import math
from typing import Any

from medcalc_kit.data import Example, as_example
from medcalc_kit.probes.base import Probe
from medcalc_kit.probes.common import DEFAULT_SYSTEM_PROMPT, Item, make_item, numeric_answer, render

DEFAULT_MAX_NEW_TOKENS = 2048
# Placeholders: {note}, {question}.
DEFAULT_TEMPLATE = (
    "Patient note:\n{note}\n\n"
    "Question: {question}\n\n"
    "Think step by step, then end your answer with a JSON object of the form {\"answer\": <number>}"
)


def build(example: Example | dict[str, Any], *, template: str = DEFAULT_TEMPLATE,
          max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS, system_prompt: str | None = DEFAULT_SYSTEM_PROMPT,
          label: str = "E2E") -> Item:
    """The item for one example: the patient note and the benchmark question.

    template: prompt text, placeholders {note} and {question}; max_new_tokens: token budget;
    system_prompt: None for none; label: the item's probe name.

    >>> item = build(mk.data.demo()[2], max_new_tokens=512)
    >>> item["max_new_tokens"], item["reference"]["ground_truth"]
    (512, 12.0)
    """
    ex = as_example(example)
    user = render(template, note=ex.note, question=ex.question)
    return make_item(ex, label, user, {"ground_truth": ex.ground_truth, "lower": ex.lower, "upper": ex.upper},
                     max_new_tokens, system_prompt, task="E2E")


def score_answer(reference: dict[str, Any], text: str, *, rel_tol: float | None = None) -> dict[str, Any]:
    """Score a model answer against an E2E reference ({"ground_truth", "lower", "upper"}).

    >>> ref = {"ground_truth": 100.0, "lower": 95.0, "upper": 105.0}
    >>> score_answer(ref, '{"answer": "104 mL/min"}')
    {'format_valid': True, 'correct': True, 'error_type': None, 'rel_error': 0.04}
    >>> score_answer(ref, '{"answer": 104}', rel_tol=0.01)["correct"]
    False
    """
    v = numeric_answer(text, "answer")
    if v is None:
        return {"format_valid": False, "correct": False, "error_type": "format_invalid", "rel_error": math.nan}
    gt = reference["ground_truth"]
    if rel_tol is None:
        ok = reference["lower"] - 1e-9 <= v <= reference["upper"] + 1e-9
    else:
        ok = abs(v - gt) <= rel_tol * abs(gt)
    return {"format_valid": True, "correct": ok, "error_type": None if ok else "out_of_bounds",
            "rel_error": abs(v - gt) / max(abs(gt), 1e-12)}


def score(item: Item, text: str, **options: Any) -> dict[str, Any]:
    """Score a model answer for an E2E item. Options: rel_tol (replaces the benchmark interval).

    >>> score(build(mk.data.demo()[2]), "The anion gap is 12 mEq/L.")["error_type"]   # JSON required
    'format_invalid'
    """
    return score_answer(item["reference"], text, **options)


def reference_answer(item: Item) -> str:
    """A correct answer: the ground truth in the expected JSON format.

    >>> reference_answer(build(mk.data.demo()[2]))
    '{"answer": 12.0}'
    """
    return json.dumps({"answer": item["reference"]["ground_truth"]})


PROBE = Probe("E2E", "End to end", "the original benchmark task", build, score, reference_answer)
