"""LLM judge: reading answers, blindness to the condition, resumable annotation, agreement with humans."""
import json

import pandas as pd
import pytest

import medcalc_kit as mk
from medcalc_kit import judge
from medcalc_kit.data import from_records

DS = mk.data.demo(2)
ITEMS = mk.ProbeSuite(["E2E", "A"]).build(DS)
E2E = ITEMS[ITEMS.probe == "E2E"]
SECRET = {"model_id": "secret-model-xyz", "meta.sparsity": 0.5, "meta.method": "wanda-prune", "seconds": 1.5}


def records(text='Reasoning... {"answer": 1}'):
    return [{"item_id": i, "text": text, "n_new_tokens": 9, "error": None, **SECRET} for i in ITEMS.item_id]


def test_parse():
    item = judge.build(E2E.iloc[0], records()[0], example=DS[0])
    assert judge.parse('{"first_error": "Conversion", "evidence": "used kg"}', item) == \
        {"format_valid": True, "first_error": "conversion", "evidence": "used kg"}
    assert judge.parse('{"first_error": "none"}', item) == {"format_valid": True, "first_error": "none",
                                                            "evidence": None}
    for bad in ("", "the formula is wrong", '{"first_error": "units"}', '{"first_error": 3}', '{"error": "formula"}'):
        assert judge.parse(bad, item) == {"format_valid": False, "first_error": None, "evidence": None}
    only = judge.build(E2E.iloc[0], records()[0], example=DS[0], steps=("formula", "arithmetic"))
    assert judge.parse('{"first_error": "conversion"}', only)["first_error"] is None


def test_the_judge_is_blind_to_the_condition():
    item = judge.build(E2E.iloc[0], records()[0], example=DS[0])
    prompt = json.dumps(item["messages"])
    for leak in ("secret-model-xyz", "wanda", "sparsity", "0.5", "model_id", "method"):
        assert leak not in prompt, leak
    text = item["messages"][-1]["content"]
    ref = judge.reference_text(DS[0])
    assert DS[0].note in text and DS[0].question in text and ref in text and "Reasoning... " in text
    for part in ("Values in the note", "units of the formula", "Formula (branch", "Substituted expression", "Result"):
        assert part in ref


def test_annotate_resumes_and_skips(tmp_path):
    calls = []
    replies = iter(['{"first_error": "formula", "evidence": "x"}', "no idea", '{"first_error": "none"}'] * 10)

    def toy_judge(messages, max_new_tokens):
        calls.append(1)
        return next(replies)

    date = from_records([{"Calculator ID": "13", "Patient Note": "LMP 09/17/2011.", "Question": "Due date?",
                          "entities": {"cycle length": 21}, "Ground Truth Answer": "06/16/2012"}], split="demo")
    ds = DS + date
    items = mk.ProbeSuite(["E2E", "A"]).build(ds)
    recs = [{"item_id": i, "text": '{"answer": 1}', "model_id": "m", "error": None} for i in items.item_id]
    out = tmp_path / "judge.jsonl"
    notes = judge.annotate(items, recs, toy_judge, dataset=ds, out_path=out, model_id="toy")
    assert len(notes) == 8 == len(calls)                       # E2E of the 8 registry examples; no A, no date item
    assert set(notes.judged_item_id) == set(E2E.item_id)
    assert notes.format_valid.tolist().count(False) >= 2 and notes.first_error.isna().sum() >= 2
    assert (notes.judge_model_id == "toy").all() and set(notes.template) == {"v1"}
    assert notes.template_hash.nunique() == 1
    again = judge.annotate(items, recs, toy_judge, dataset=ds, out_path=out, model_id="toy")
    assert len(calls) == 8 and again.first_error.equals(notes.first_error)      # resumed: nothing generated
    other = [{**r, "model_id": "m2"} for r in recs]                              # another model: judged anew
    notes_m2 = judge.annotate(items, other, toy_judge, dataset=ds, out_path=out, model_id="toy")
    assert len(calls) == 16 and set(notes_m2.model_id) == {"m2"}
    assert set(notes_m2.judge_item_id).isdisjoint(notes.judge_item_id)


def test_agreement_known_kappa():
    r = judge.agreement(["a", "a", "b", "b"], ["a", "b", "b", "b"])
    assert r["n"] == 4 and r["agreement"] == 0.75 and r["kappa"] == pytest.approx(0.5)
    assert r["confusion"].loc["b", "a"] == 1 and r["confusion"].loc["b", "b"] == 2
    perfect = judge.agreement(["x", "y"], ["x", "y"])
    assert perfect["kappa"] == 1.0
    notes = pd.DataFrame({"judge_item_id": ["i1", "i2", "i3"], "first_error": ["formula", None, "none"]})
    r = judge.agreement(notes, {"i1": "formula", "i2": "formula", "i3": "arithmetic"})
    assert r["n"] == 2 and r["n_unreadable"] == 1 and r["agreement"] == 0.5
    with pytest.raises(ValueError):
        judge.agreement(["a"], ["a", "b"])


def test_build_refuses_other_probes_and_mismatched_records():
    a_item = ITEMS[ITEMS.probe == "A"].iloc[0]
    with pytest.raises(ValueError, match="end-to-end"):
        judge.build(a_item, records()[0], example=DS[0])
    with pytest.raises(ValueError, match="does not answer"):
        judge.build(E2E.iloc[0], {"item_id": "demo:6:1:E2E", "text": "x"}, example=DS[0])


def test_judge_reads_latex_quotes_and_states_the_rules():
    item = judge.build(E2E.iloc[0], records()[0], example=DS[0])
    answer = 'Wrong formula. {"first_error": "formula", "evidence": "\\\\[ QTc = QT + 0.03 \\\\times (HR - 60) \\\\]"}'
    assert judge.parse(answer, item)["first_error"] == "formula"
    for variant in ("v1", "v2", "v3"):
        text = judge.build(E2E.iloc[0], records()[0], example=DS[0], template=variant)["messages"][-1]["content"]
        assert judge.JUDGING_RULES in text and "metres instead of centimetres" in text
