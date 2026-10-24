"""K: adjustable share of test points the formula must be right at; the patient's point is always required."""
import medcalc_kit as mk
from medcalc_kit.probes import knowledge

BMI = mk.data.demo()[1]                                    # 70 kg, 175 cm
BMI_FORMULA = "weight / (height / 100)^2"


def item_with_49_other_points():
    """The patient plus 49 pool patients (heights 150..198 cm, one of them 180 cm): 50 test points."""
    pool = [{"weight": [60.0 + i / 2, "kg"], "height": [150.0 + i, "cm"]} for i in range(49)]
    return knowledge.build(BMI, pool, n_points=49)


def cases(*pairs):
    return '{"cases": [' + ", ".join(f'{{"condition": "{c}", "formula": "{f}"}}' for c, f in pairs) + "]}"


def test_49_of_50_points():
    item = item_with_49_other_points()
    wrong_once = cases(("height == 180", "0"), ("otherwise", BMI_FORMULA))
    strict = mk.score(item, wrong_once, case_semantics="first_match")
    assert strict["n_points"] == 50 and strict["point_pass_rate"] == 0.98
    assert not strict["correct"] and strict["error_type"] == "wrong_elsewhere"
    lenient = mk.score(item, wrong_once, case_semantics="first_match", min_pass_rate=0.95)
    assert lenient["correct"] and lenient["error_type"] is None and lenient["point_pass_rate"] == 0.98


def test_wrong_at_the_patient_is_never_correct():
    item = item_with_49_other_points()
    wrong_for_patient = cases(("height == 175", "0"), ("otherwise", BMI_FORMULA))
    v = mk.score(item, wrong_for_patient, case_semantics="first_match", min_pass_rate=0.0)
    # the pool also holds a 175 cm patient: 2 of 50 points fail, yet the patient alone makes it wrong
    assert not v["correct"] and v["error_type"] == "wrong_at_patient_point" and v["point_pass_rate"] == 0.96


def test_default_threshold_is_every_point():
    assert knowledge.DEFAULT_MIN_PASS_RATE == 1.0
    item = item_with_49_other_points()
    assert mk.score(item, cases(("always", BMI_FORMULA)))["correct"]
