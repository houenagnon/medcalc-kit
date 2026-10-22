"""Diagnostic probes: one module per competence, each with its prompt (`build`) and its scoring (`score`).

| probe | module        | measures                                                     |
|-------|---------------|--------------------------------------------------------------|
| E     | extraction    | finding the input values (with units) in the patient note    |
| K     | knowledge     | writing the general formula without the patient's values     |
| S     | substitution  | plugging the values into a given formula, without computing  |
| A     | arithmetic    | computing a fully written numerical expression               |
| E2E   | end_to_end    | the original benchmark task                                  |

An item is a dict (or a DataFrame row): the chat to send (`messages`) and what the scorer needs (`reference`).

    >>> from medcalc_kit import probes
    >>> ex = mk.data.demo()[1]                                  # BMI, 70 kg, 175 cm
    >>> item = probes.substitution.build(ex)                    # prompt + reference
    >>> print(probes.prompt(item).splitlines()[2])              # what the model is asked
    [user] Formula for Body Mass Index (BMI):
    >>> probes.score(item, '{"expression": "70 / (175 / 100)^2"}')["correct"]
    True
    >>> probes.score(item, '{"expression": "22.857143"}')["error_type"]   # computed instead of substituted
    'premature_computation'
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from medcalc_kit.probes import arithmetic, end_to_end, extraction, knowledge, substitution
from medcalc_kit.probes.base import Probe
from medcalc_kit.probes.common import Item, as_item, as_items, items_frame, prompt
from medcalc_kit.probes.suite import ALL_PROBES, ProbeSuite, read_items, write_items

PROBES: dict[str, Probe] = {m.PROBE.name: m.PROBE for m in (extraction, knowledge, substitution, arithmetic,
                                                            end_to_end)}


def get(name: str) -> Probe:
    """The probe with this name ("E", "K", "S", "A" or "E2E").

    >>> [(p.name, p.title) for p in map(get, ALL_PROBES)]
    [('E', 'Extraction'), ('K', 'Knowledge'), ('S', 'Substitution'), ('A', 'Arithmetic'), ('E2E', 'End to end')]
    """
    if name not in PROBES:
        raise KeyError(f"unknown probe {name!r}; available: {', '.join(PROBES)}")
    return PROBES[name]


def _task(item: Item) -> str:
    return item.get("task", item["probe"])


def score(item: Item | pd.Series, text: str, **options: Any) -> dict[str, Any]:
    """Score a model answer for any item (a dict or a DataFrame row). Dispatches on the item's task; `options` are
    passed to that probe's score() (tolerances, case semantics...).

    The verdict always has `format_valid`, `correct` and `error_type` (None when correct), plus probe-specific
    details (e.g. `fields` for E, `point_pass_rate` for K, `rel_error` for A).

    >>> item = arithmetic.build(mk.data.demo()[2])              # anion gap: 140 - (104 + 24)
    >>> score(item, 'So the result is {"result": 12}')
    {'format_valid': True, 'correct': True, 'correct_strict': True, 'error_type': None, 'rel_error': 0.0}
    >>> score(item, '{"result": 14}')["error_type"]
    'arithmetic_error'
    >>> score(item, 'twelve')["error_type"]
    'format_invalid'
    >>> score(item, '{"result": 12.1}', rel_tol=0.001)["correct"]
    False
    """
    item = as_item(item)
    return get(_task(item)).score(item, text, **options)


def reference_answer(item: Item | pd.Series) -> str:
    """A model answer that the item's probe scores as correct, in the format the prompt asks for. Useful to see
    the expected format and to test a pipeline end to end without a model. For K in "general" mode, it is only
    correct for calculators without branches (see knowledge.reference_answer).

    >>> ex = mk.data.demo()[2]
    >>> reference_answer(arithmetic.build(ex))
    '{"result": 12.0}'
    >>> reference_answer(extraction.build(ex))
    '{"Sodium": {"value": 140.0, "unit": "mEq/L"}, "Chloride": {"value": 104.0, "unit": "mEq/L"},
      "Bicarbonate": {"value": 24.0, "unit": "mEq/L"}}'
    >>> item = knowledge.build(ex)
    >>> reference_answer(item)
    '{"cases": [{"condition": "always", "formula": "na - (cl + hco3)"}]}'
    >>> score(item, reference_answer(item))["correct"]
    True
    """
    item = as_item(item)
    return get(_task(item)).reference_answer(item)


__all__ = ["ALL_PROBES", "PROBES", "Item", "Probe", "ProbeSuite", "arithmetic", "as_item", "as_items", "end_to_end",
           "extraction", "get", "items_frame", "knowledge", "prompt", "read_items", "reference_answer", "score",
           "substitution", "write_items"]
