"""E2E interventions: the correct values and/or formula given in the prompt."""
import pytest

import medcalc_kit as mk
from medcalc_kit.probes import end_to_end

CG = mk.data.demo()[0]


def test_no_intervention_is_unchanged():
    assert end_to_end.build(CG, provide=()) == end_to_end.build(CG)
    assert end_to_end.build(CG)["probe"] == "E2E" and "provided" not in end_to_end.build(CG)["reference"]


@pytest.mark.parametrize("provide,label", [(("values",), "E2E+V"), (("formula",), "E2E+F"),
                                           (("values", "formula"), "E2E+VF"), (("formula", "values"), "E2E+VF")])
def test_information_is_in_the_prompt(provide, label):
    item = end_to_end.build(CG, provide=provide)
    text = item["messages"][-1]["content"]
    assert item["probe"] == label and item["task"] == "E2E" and item["item_id"] == f"demo:2:1:{label}"
    assert CG.question in text and CG.note in text
    assert (end_to_end.PROVIDED_VALUES_HEADER in text) == ("values" in provide)
    assert (end_to_end.PROVIDED_FORMULA_HEADER in text) == ("formula" in provide)
    if "values" in provide:
        assert "- scr = 0.76 (serum creatinine (mg/dL))" in text and "- weight = 68.6 (body weight (kg))" in text
    if "formula" in provide:
        assert "crcl = (140 - age) * (45.5 + 2.3 * (height / 2.54 - 60)" in text
    plain = end_to_end.build(CG)
    assert item["reference"] == {**plain["reference"], "provided": [p for p in ("values", "formula") if p in provide]}
    assert mk.score(item, mk.reference_answer(item)) == mk.score(plain, mk.reference_answer(plain))


def test_suite_variants_and_errors():
    items = mk.ProbeSuite({"E2E": {}, "E2E+VF": {"task": "E2E", "provide": ("values", "formula")}}).build(
        mk.data.demo())
    assert items.groupby("probe", sort=False).size().to_dict() == {"E2E": 4, "E2E+VF": 4}
    with pytest.raises(ValueError, match="provide"):
        end_to_end.build(CG, provide=("answer",))
    date = mk.data.from_records([{"Calculator ID": "13", "entities": {}, "Ground Truth Answer": "06/16/2012"}])[0]
    with pytest.raises(ValueError, match="registry"):
        end_to_end.build(date, provide=("formula",))
