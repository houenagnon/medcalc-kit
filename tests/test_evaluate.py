"""Scoring of generation records, K de-duplication into units, per-probe summary."""
import pandas as pd
import pytest

from medcalc_kit import evaluate
from medcalc_kit.evaluate import score_records, summary, to_units


def a_item(i, gold=10.0):
    return {"item_id": f"x:{i}:A", "example_id": f"x:{i}", "calculator_id": "2", "probe": "A",
            "messages": [{"role": "user", "content": "1+1"}], "max_new_tokens": 100,
            "reference": {"expression": "5 + 5", "gold_value": gold}}


def record(item, text, n_new_tokens=10):
    return {"item_id": item["item_id"], "example_id": item["example_id"], "calculator_id": item["calculator_id"],
            "probe": item["probe"], "text": text, "n_new_tokens": n_new_tokens, "error": None}


def test_score_records_artifacts_and_correctness():
    items = [a_item(i) for i in range(4)]
    recs = [record(items[0], '{"result": 10}'), record(items[1], '{"result": 12}'),
            record(items[2], "", 0), record(items[3], "1 2 3", 100)]
    df = score_records(recs, items, condition={"model": "m"})
    assert df.category.tolist() == ["well_formed", "well_formed", "empty", "truncated"]
    assert df.correct.tolist() == [True, False, False, False]
    assert (df.model == "m").all()
    s = summary(df)
    assert s.loc["A", "n_units"] == 4 and s.loc["A", "competence"] == pytest.approx(0.5)
    assert s.loc["A", "overall"] == pytest.approx(0.25) and s.loc["A", "well_formed"] == pytest.approx(0.5)


def test_score_records_reads_jsonl(tmp_path):
    import json
    item = a_item(0)
    path = tmp_path / "out.jsonl"
    path.write_text(json.dumps(record(item, '{"result": 10}')) + "\n")
    assert evaluate.score_records(path, {item["item_id"]: item}).correct.all()


def test_k_units_collapse_by_prompt():
    df = pd.DataFrame([
        {"model": "m", "method": "dense", "sparsity": 0.0, "seed": 0, "probe": "K", "calculator_id": "2",
         "prompt_key": "p1", "example_id": f"e{i}", "correct": True, "well_formed": True, "category": "well_formed"}
        for i in range(5)] + [
        {"model": "m", "method": "dense", "sparsity": 0.0, "seed": 0, "probe": "A", "calculator_id": "2",
         "prompt_key": f"a{i}", "example_id": f"e{i}", "correct": True, "well_formed": True, "category": "well_formed"}
        for i in range(5)])
    u = to_units(df)
    assert (u.probe == "K").sum() == 1 and (u.probe == "A").sum() == 5


def test_collapse_uses_task_so_labelled_variants_collapse_too():
    df = pd.DataFrame([
        {"probe": "Kg", "task": "K", "calculator_id": "2", "prompt_key": "p", "example_id": f"e{i}",
         "correct": True, "well_formed": True, "category": "well_formed"} for i in range(3)])
    assert len(to_units(df)) == 1
    assert len(to_units(df, collapse=())) == 3


def test_unusable_answers_report_their_category_as_error():
    item = a_item(0)
    df = score_records([record(item, '{"result": 10}', n_new_tokens=100)], [item])     # correct but cut off
    assert df.category[0] == "truncated" and not df.correct[0] and df.error_type[0] == "truncated"
