"""The registry reproduces every MedCalc-Bench-Verified test answer (downloads the dataset)."""
import pandas as pd
import pytest

REVISION = "58fc3de568bfc53a68f32327e58f60dc6eaa17f8"


@pytest.mark.network
def test_registry_reproduces_all_test_answers():
    from medcalc_kit.calculators.verify import verify
    from medcalc_kit.data import load

    res, _ = verify(load(REVISION, splits=("test",), equation_only=True))
    assert len(res) == 660
    assert res.within_bounds.all(), res[~res.within_bounds][["example_id", "registry_value", "ground_truth"]]


@pytest.mark.network
def test_reference_answers_score_correct_on_every_test_example():
    import medcalc_kit as mk

    ds = mk.load(REVISION, equation_only=True)
    items = mk.ProbeSuite({"E": {}, "K": {"mode": "patient"}, "S": {}, "A": {}, "E2E": {}},
                          schema=ds).build(ds.filter(split="test"))
    answers = [mk.reference_answer(it) for _, it in items.iterrows()]
    df = mk.score_records(pd.DataFrame({"item_id": items.item_id, "text": answers}), items, details=True)
    wrong = df[~df.correct]
    assert wrong.empty, wrong[["item_id", "category", "error_type"]].head(20).to_string()


@pytest.mark.network
def test_full_benchmark_end_to_end_reference_answers():
    import medcalc_kit as mk

    test = mk.load(REVISION).filter(split="test")
    assert len(test) == 1100 and test.df["Calculator ID"].nunique() == 55
    items = mk.ProbeSuite().build(test)
    assert (items.probe == "E2E").sum() == 1100 and len(items) == 1100 + 4 * 660
    e2e = items[items.probe == "E2E"]
    answers = pd.DataFrame({"item_id": e2e.item_id, "text": [mk.reference_answer(it) for _, it in e2e.iterrows()]})
    scores = mk.score_records(answers, e2e)
    assert scores.correct.all(), scores[~scores.correct].head()


@pytest.mark.network
def test_dev_split_from_train_never_leaks_into_test():
    import medcalc_kit as mk

    ds = mk.load(REVISION).split_off("dev", fraction=0.1, exclude_leaks=True)
    counts = ds.splits().examples.to_dict()
    assert counts["test"] == 1100 and counts["dev"] > 0
    assert not mk.data.leaking_rows(ds, "dev", "test").any()


@pytest.mark.network
@pytest.mark.parametrize("variant", ["v2", "v3"])
def test_reference_answers_correct_for_paraphrased_prompts(variant):
    import medcalc_kit as mk

    ds = mk.load(REVISION)
    specs = {"E": {}, "K": {"mode": "patient"}, "S": {}, "A": {}, "E2E": {}}
    items = mk.ProbeSuite({k: {**o, "template": variant} for k, o in specs.items()}, schema=ds.equation_only()) \
        .build(ds.filter(split="test"))
    answers = pd.DataFrame({"item_id": items.item_id, "text": [mk.reference_answer(it) for _, it in items.iterrows()]})
    scores = mk.score_records(answers, items)
    assert len(scores) == 1100 + 4 * 660 and scores.correct.all(), scores[~scores.correct].head()
