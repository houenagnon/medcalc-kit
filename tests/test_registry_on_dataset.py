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
