"""The common interface of all probes."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from medcalc_kit.probes.common import Item


@dataclass(frozen=True)
class Probe:
    """A probe = how to build its prompt for an example + how to score a model answer.

    build(example, **context) -> item     (context depends on the probe, see each module)
    score(item, text) -> verdict dict      at least: format_valid, correct, error_type
    reference_answer(item) -> text         a model answer that this probe scores as correct

    >>> p = mk.probes.get("A")
    >>> p.name, p.title, p.measures
    ('A', 'Arithmetic', 'computing a fully written numerical expression')
    """
    name: str
    title: str
    measures: str
    build: Callable[..., Item]
    score: Callable[[Item, str], dict[str, Any]]
    reference_answer: Callable[[Item], str]
