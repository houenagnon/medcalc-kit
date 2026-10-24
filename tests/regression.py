"""Frozen behaviour of the default probes on mk.data.demo(), used by tests/test_regression.py.

    python tests/regression.py      # rewrites tests/data/regression_v040.json (only to deliberately accept a change)
"""
import json
import math
from pathlib import Path

import medcalc_kit as mk

SNAPSHOT = Path(__file__).parent / "data" / "regression_v040.json"
SUITE = {"E": {}, "K": {}, "Kp": {"task": "K", "mode": "patient"}, "S": {}, "A": {}, "E2E": {}}
# Answers scored for every item: the reference answer plus wrong, partial and malformed ones.
TEXTS = ["", "no answer here", '{"answer": 1}', '{"result": 1}', '{"result": 12}', '{"expression": "1 + 1"}',
         '{"formula": "weight / height^2"}', '{"cases": [{"condition": "always", "formula": "na - cl - hco3"}]}',
         '{"weight": {"value": 70, "unit": "kg"}, "height": "175 cm", "sex": "Female"}']


def _clean(value):
    if isinstance(value, float) and math.isnan(value):
        return "nan"
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_clean(v) for v in value]
    return value


def snapshot() -> dict:
    items = mk.ProbeSuite(SUITE).build(mk.data.demo(3))
    out = {}
    for it in mk.probes.as_items(items):
        texts = [mk.reference_answer(it)] + TEXTS if it.get("task", it["probe"]) != "K" or it["reference"].get(
            "mode") == "patient" else TEXTS
        out[it["item_id"]] = {"messages": it["messages"], "reference": _clean(it["reference"]),
                              "max_new_tokens": it["max_new_tokens"],
                              "verdicts": [_clean(mk.score(it, t)) for t in texts]}
    return out


if __name__ == "__main__":
    SNAPSHOT.write_text(json.dumps(snapshot(), indent=1, sort_keys=True, ensure_ascii=False))
    print("wrote", SNAPSHOT)
