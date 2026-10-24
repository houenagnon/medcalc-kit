"""Deterministic extraction of structured answers from raw model text.

    >>> from medcalc_kit import parsing
    >>> parsing.extract_json('Let me think... the answer is {"answer": "79.9 mL/min"}.')
    {'answer': '79.9 mL/min'}
    >>> parsing.to_number("79.9 mL/min")
    79.9
"""
from __future__ import annotations

import json
import re
from typing import Any

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)
_INVALID_ESCAPE_RE = re.compile(r'\\(?!["\\/bfnrtu])')    # a backslash that does not start a JSON escape
_NUMBER_RE = re.compile(r"[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)?\.?\d+(?:[eE][-+]?\d+)?")


def _balanced_candidates(text: str) -> list[str]:
    """All top-level {...} / [...] substrings, in order of appearance (string-aware)."""
    out, stack, start, in_str, esc = [], [], None, False, False
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"' and stack:
            in_str = True
        elif ch in "{[":
            if not stack:
                start = i
            stack.append("}" if ch == "{" else "]")
        elif ch in "}]" and stack:
            if ch != stack[-1]:
                stack, start = [], None
                continue
            stack.pop()
            if not stack and start is not None:
                out.append(text[start : i + 1])
                start = None
    return out


def extract_json(text: str, lenient: bool = False) -> Any | None:
    """Return the LAST valid JSON object/array in the text (fenced blocks preferred), else None.
    lenient=True also reads objects whose strings hold backslashes that are not JSON escapes (LaTeX such as
    "\\times" quoted by a model); the probes use the strict default.

    >>> extract_json('First {"a": 1}, then {"a": 2}')
    {'a': 2}
    >>> extract_json("no JSON here") is None
    True
    >>> extract_json(r'{"quote": "\\[ x \\]"}') is None                  # \\[ is not a JSON escape
    True
    >>> print(extract_json(r'{"quote": "\\[ x \\]"}', lenient=True)["quote"])
    \\[ x \\]
    """
    if not text:
        return None
    for source in (_FENCE_RE.findall(text), _balanced_candidates(text)):
        for cand in reversed(source):
            try:
                return json.loads(cand.strip())
            except (json.JSONDecodeError, ValueError):
                if lenient:
                    try:
                        return json.loads(_INVALID_ESCAPE_RE.sub(r"\\\\", cand.strip()))
                    except (json.JSONDecodeError, ValueError):
                        pass
                continue
    return None


def to_number(value: Any) -> float | None:
    """Coerce a JSON value to float: numbers, or strings like '79.9 mL/min', '1,234.5'. Else None.

    >>> to_number(12), to_number("1,234.5"), to_number("about -3e2 units"), to_number(True)
    (12.0, 1234.5, -300.0, None)
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        m = _NUMBER_RE.search(value.strip())
        if m:
            return float(m.group(0).replace(",", ""))
    return None
