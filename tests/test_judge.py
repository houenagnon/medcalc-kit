"""LLM evaluation: the judge grades answers to every probe, next to the automatic evaluation."""
import json

import pandas as pd
import pytest

import medcalc_kit as mk
from medcalc_kit import judge

DS = mk.data.demo(2)
ITEMS = mk.ProbeSuite({"E": {}, "U": {}, "K": {"mode": "patient"}, "S": {}, "A": {}, "E2E": {}}).build(DS)
SECRET = {"model_id": "secret-model-xyz", "meta.sparsity": 0.5, "meta.method": "wanda-prune", "seconds": 1.5}


def record(item, text):
    return {"item_id": item["item_id"], "text": text, "n_new_tokens": 9, "error": None, **SECRET}


def test_every_probe_has_a_reference_and_a_rule():
    for _, item in ITEMS.groupby("probe").head(1).iterrows():
        j = judge.build(item, record(item, "x"))
        text = j["messages"][-1]["content"]
        assert judge.CRITERIA[item.get("task", item.probe)] in text
        assert judge.reference_text(item) in text and item.messages[-1]["content"] in text
        assert j["reference"]["graded_item_id"] == item.item_id


def test_the_judge_is_blind_and_grades_only_the_final_answer_for_e2e():
    e2e = ITEMS[ITEMS.probe == "E2E"].iloc[0]
    text = json.dumps(judge.build(e2e, record(e2e, '{"answer": 80}'))["messages"])
    for leak in ("secret-model-xyz", "wanda", "sparsity", "0.5", "model_id", "method"):
        assert leak not in text, leak
    assert "Only the final answer is graded" in text and "accepted interval" in text


def test_parse():
    assert judge.parse('ok {"verdict": "correct", "reason": "within 1 %"}') == \
        {"format_valid": True, "judge_correct": True, "reason": "within 1 %"}
    assert judge.parse('{"verdict": "INCORRECT"}')["judge_correct"] is False
    assert judge.parse('{"verdict": "Incorrect", "reason": "uses \\\\times wrongly"}')["format_valid"]    # LaTeX
    for bad in ("", "it is right", '{"verdict": "maybe"}', '{"correct": true}'):
        assert judge.parse(bad) == {"format_valid": False, "judge_correct": None, "reason": None}


def test_annotate_resumes_and_compare(tmp_path):
    calls = []

    def toy_judge(messages, max_new_tokens):                   # says "correct" iff the reference is in the answer
        calls.append(1)
        text = messages[-1]["content"]
        reference = text.split("Reference answer: ")[1].split("\n")[0].split(" ")[0]
        answer = text.split("Assistant's answer:\n<<<\n")[1]
        return json.dumps({"verdict": "correct" if reference in answer else "incorrect", "reason": "toy"})

    recs = [record(it, mk.reference_answer(it) if k % 2 == 0 else "no idea") for k, (_, it) in
            enumerate(ITEMS.iterrows())]
    out = tmp_path / "judge.jsonl"
    llm = judge.annotate(ITEMS, recs, toy_judge, out_path=out, model_id="toy")
    assert len(llm) == len(ITEMS) == len(calls) and (llm.judge_model_id == "toy").all()
    assert set(llm.template) == {"v1"} and llm.template_hash.nunique() == 1
    again = judge.annotate(ITEMS, recs, toy_judge, out_path=out, model_id="toy")
    assert len(calls) == len(ITEMS) and again.judge_correct.equals(llm.judge_correct)           # resumed
    scores = mk.score_records(recs, ITEMS)
    table = judge.compare(llm, scores)
    assert list(table.index)[-1] == "all" and table.loc["all", "n"] == len(ITEMS)
    assert table.loc["A", "agreement"] == 1.0 and table.loc["A", "kappa"] == 1.0
    assert table.loc["A", "auto_accuracy"] == table.loc["A", "llm_accuracy"] == 0.5


def test_compare_counts_the_judge_errors():
    scores = pd.DataFrame({"item_id": list("abcdef"), "task": "S", "correct": [True, True, True, False, False, False]})
    llm = pd.DataFrame({"item_id": list("abcdef"), "judge_correct": [True, True, False, True, False, None]})
    row = judge.compare(llm, scores).loc["S"]
    assert row.n == 6 and row.unreadable == 1
    assert row.false_rejection == pytest.approx(1 / 3) and row.false_acceptance == pytest.approx(1 / 2)
    assert row.agreement == pytest.approx(3 / 5)


def test_agreement_known_kappa():
    r = judge.agreement(["a", "a", "b", "b"], ["a", "b", "b", "b"])
    assert r["n"] == 4 and r["agreement"] == 0.75 and r["kappa"] == pytest.approx(0.5)
    assert judge.agreement(["x", None], ["x", "y"])["n_missing"] == 1
    with pytest.raises(ValueError):
        judge.agreement(["a"], ["a", "b"])


def test_evaluate_model_with_a_judge(tmp_path):
    def model(messages, max_new_tokens):
        return '{"answer": 12, "result": 12, "value": 12}'

    def always_correct(messages, max_new_tokens):
        return '{"verdict": "correct", "reason": "looks fine"}'

    report = mk.evaluate_model(model, tmp_path, dataset=DS, split="demo", k_pool=None, judge=always_correct)
    assert report.llm is not None and len(report.llm) == len(report.items)
    vs = report.llm_vs_auto
    assert vs.loc["all", "llm_accuracy"] == 1.0 and vs.loc["all", "false_acceptance"] == 1.0
    assert "LLM evaluation (always_correct)" in repr(report) and (tmp_path / "llm_vs_auto.csv").exists()
    assert report.scores.judge_correct.all()
    plain = mk.evaluate_model(None, tmp_path, dataset=DS, split="demo", k_pool=None, model_id="model")
    assert plain.llm is None and "LLM evaluation" not in repr(plain)
    with pytest.raises(ValueError, match="no LLM evaluation"):
        _ = plain.llm_vs_auto


def test_a_new_prompt_is_graded_again():
    item = ITEMS.iloc[0]
    a, b = (judge.build(item, record(item, "x"), template=t) for t in ("v1", "v2"))
    assert a["item_id"] != b["item_id"] and a["item_id"].endswith(a["template_hash"][:6])


@pytest.mark.gpu
def test_a_deterministic_judge_repeats_itself_exactly(tmp_path):
    torch = pytest.importorskip("torch")
    pytest.importorskip("transformers")
    if not torch.cuda.is_available():
        pytest.skip("no GPU")
    from medcalc_kit.generation.hf import HFBackend

    free = [torch.cuda.mem_get_info(i)[0] for i in range(torch.cuda.device_count())]
    device = f"cuda:{max(range(len(free)), key=free.__getitem__)}"
    backend = HFBackend("Qwen/Qwen2.5-3B-Instruct", device=device, deterministic=True)
    items = ITEMS[ITEMS.probe.isin(["A", "E2E"])]
    recs = [record(it, mk.reference_answer(it)) for _, it in items.iterrows()]
    first = judge.annotate(items, recs, backend, out_path=tmp_path / "a.jsonl", max_new_tokens=64)
    second = judge.annotate(items, recs, backend, out_path=tmp_path / "b.jsonl", max_new_tokens=64)
    assert first.judge_text.tolist() == second.judge_text.tolist()
    assert backend.revision is not None and first.judge_revision.iloc[0] == backend.revision
