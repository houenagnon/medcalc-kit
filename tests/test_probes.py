"""Scorers on hand-crafted model outputs (no GPU, no dataset)."""
import json

import pytest

from medcalc_kit.parsing import extract_json, to_number
from medcalc_kit.probes.arithmetic import build as build_A
from medcalc_kit.probes.arithmetic import score_answer as score_A
from medcalc_kit.probes.end_to_end import score_answer as score_E2E
from medcalc_kit.probes.extraction import build as build_E
from medcalc_kit.probes.extraction import score_answer as score_E
from medcalc_kit.probes.knowledge import build as build_K
from medcalc_kit.probes.knowledge import score_answer as score_K
from medcalc_kit.probes.substitution import build as build_S
from medcalc_kit.probes.substitution import score_answer as score_S

CG_ROW = {
    "example_id": "x:2:1", "Calculator ID": "2", "Calculator Name": "Creatinine Clearance (Cockcroft-Gault Equation)",
    "Patient Note": "A 51-year-old woman, 68.6 kg, 158 cm, creatinine 0.76 mg/dL.",
    "Question": "What is the patient's Creatinine Clearance using the Cockroft-Gault Equation in terms of mL/min? "
                "You should use the patient's adjusted body weight in kg instead of the patient's actual body weight "
                "if the patient is overweight or obese based on their BMI. If the patient's BMI's normal, set their "
                "adjusted body weight to the minimum of the ideal body and actual weight. If the patient is "
                "underweight, please set their adjusted body weight to their actual body weight.",
    "entities": {"sex": "Female", "age": [51, "years"], "weight": [68.6, "kg"], "height": [158.0, "cm"],
                 "creatinine": [0.76, "mg/dL"]},
}
CG_FIELDS = {"sex": "sex", "age": "quantity", "weight": "quantity", "height": "quantity", "creatinine": "quantity"}
CKD_ROW = {
    "example_id": "x:3:1", "Calculator ID": "3", "Calculator Name": "CKD-EPI Equations for Glomerular Filtration Rate",
    "Patient Note": "...", "Question": "Using the 2021 CKD-EPI Creatinine equation, what is the patient's GFR?",
    "entities": {"age": [35, "years"], "creatinine": [5.0, "mg/dL"], "sex": "Male"},
}


def wrap(obj) -> str:
    return "Some reasoning first.\n```json\n" + json.dumps(obj) + "\n```"


# ---------------------------------------------------------------- parsing

def test_extract_last_json_and_numbers():
    assert extract_json('a {"x": 1} b {"x": 2}') == {"x": 2}
    assert extract_json('{"s": "brace } inside"}') == {"s": "brace } inside"}
    assert extract_json("no json") is None
    assert to_number("79.9 mL/min") == pytest.approx(79.9)
    assert to_number("1,234.5") == pytest.approx(1234.5)
    assert to_number(True) is None


# ---------------------------------------------------------------- E

def test_E_correct_with_equivalent_unit():
    item = build_E(CG_ROW, CG_FIELDS)
    pred = {"sex": "female", "age": {"value": 51, "unit": "years"}, "weight": {"value": 151.24, "unit": "lbs"},
            "height": {"value": 1.58, "unit": "m"}, "creatinine": {"value": 67.2, "unit": "µmol/L"}}
    r = score_E(item["reference"], wrap(pred))
    assert r["format_valid"] and r["correct"], r


def test_E_unit_error_and_missing():
    item = build_E(CG_ROW, CG_FIELDS)
    pred = {"sex": "Female", "age": {"value": 51, "unit": "years"}, "weight": {"value": 68.6, "unit": "kg"},
            "height": {"value": 158, "unit": "cm"}, "creatinine": {"value": 0.76, "unit": "mmol/L"}}
    r = score_E(item["reference"], wrap(pred))
    assert r["fields"]["creatinine"] == "unit_error" and not r["correct"]
    del pred["weight"]
    r = score_E(item["reference"], wrap(pred))
    assert r["fields"]["weight"] == "missing"
    assert r["field_accuracy"] == pytest.approx(3 / 5)


def test_E_optional_bool_absent_means_false():
    row = {**CG_ROW, "Calculator ID": "46", "entities": {"sex": "Male"}}
    item = build_E(row, {"sex": "sex", "Smoker": "bool"})
    assert score_E(item["reference"], wrap({"sex": "Male", "Smoker": False}))["correct"]
    assert score_E(item["reference"], wrap({"sex": "Male"}))["correct"]          # not mentioned -> False
    assert not score_E(item["reference"], wrap({"sex": "Male", "Smoker": True}))["correct"]


def test_E_format_invalid():
    item = build_E(CG_ROW, CG_FIELDS)
    assert score_E(item["reference"], "I cannot answer")["format_valid"] is False


# ---------------------------------------------------------------- K

def test_K_cockcroft_gault_with_cases_is_correct():
    item = build_K(CG_ROW)
    ibw = "(45.5 + 2.3 * (height / 2.54 - 60))"
    bmi = "(weight / (height / 100)^2)"
    cases = [
        {"condition": f"{bmi} < 18.5", "formula": "(140 - age) * weight * 0.85 / (72 * scr)"},
        {"condition": f"18.5 <= {bmi} <= 24.9", "formula": f"(140 - age) * min({ibw}, weight) * 0.85 / (72 * scr)"},
        {"condition": "otherwise", "formula": f"(140 - age) * ({ibw} + 0.4 * (weight - {ibw})) * 0.85 / (72 * scr)"},
    ]
    r = score_K(item["reference"], wrap({"cases": cases}), "2")
    assert r["correct"], r


def test_K_wrong_sex_coefficient_is_detected():
    item = build_K(CG_ROW)
    # always uses adjusted weight and the MDRD female coefficient 0.742
    ibw = "(45.5 + 2.3 * (height / 2.54 - 60))"
    r = score_K(item["reference"], wrap({"cases": [{"condition": "always",
                "formula": f"(140 - age) * ({ibw} + 0.4 * (weight - {ibw})) * 0.742 / (72 * scr)"}]}), "2")
    assert r["format_valid"] and not r["correct"]


CKD_POOL = [{"age": [a, "years"], "creatinine": [c, "mg/dL"], "sex": "Female"}
            for a, c in [(30, 0.6), (45, 0.8), (60, 0.95), (70, 1.4), (25, 0.5), (80, 3.2), (50, 0.85), (40, 2.0)]]


def test_K_ckd_epi_piecewise_and_single_branch():
    item = build_K(CKD_ROW, CKD_POOL)   # pool points get this patient's sex (Male)
    full = {"cases": [
        {"condition": "scr <= 0.9", "formula": "142 * (scr / 0.9)^(-0.302) * 0.9938^age"},
        {"condition": "scr > 0.9", "formula": "142 * (scr / 0.9)^(-1.2) * 0.9938^age"}]}
    assert score_K(item["reference"], wrap(full), "3")["correct"]
    minmax = {"cases": [{"condition": "always",
              "formula": "142 * min(scr / 0.9, 1)^(-0.302) * max(scr / 0.9, 1)^(-1.2) * 0.9938^age"}]}
    assert score_K(item["reference"], wrap(minmax), "3")["correct"]
    # only the branch matching this patient: right at the patient point, wrong elsewhere
    single = {"cases": [{"condition": "always", "formula": "142 * (scr / 0.9)^(-1.2) * 0.9938^age"}]}
    r = score_K(item["reference"], wrap(single), "3")
    assert not r["correct"] and r["original_point_correct"] and r["error_type"] == "wrong_elsewhere"


def test_K_rejects_unknown_variables_and_bad_format():
    item = build_K(CKD_ROW)
    r = score_K(item["reference"], wrap({"cases": [{"condition": "always", "formula": "kappa * scr"}]}), "3")
    assert r["error_type"] == "unknown_variable"
    assert score_K(item["reference"], "the formula is eGFR = 142 ...", "3")["format_valid"] is False
    r = score_K(item["reference"], wrap({"cases": [{"condition": "always", "formula": "__import__('os')"}]}), "3")
    assert r["format_valid"] is False


# ---------------------------------------------------------------- S

def test_S_gold_expression_is_correct():
    item = build_S(CG_ROW)
    r = score_S(item["reference"], wrap({"expression": item["reference"]["gold_expression"]}))
    assert r["correct"], r


def test_S_swapped_variables_detected_even_if_value_matches():
    row = {**CG_ROW, "Calculator ID": "5", "Calculator Name": "Mean Arterial Pressure (MAP)",
           "entities": {"Systolic Blood Pressure": [120, "mm hg"], "Diastolic Blood Pressure": [120, "mm hg"]}}
    item = build_S(row)  # sbp == dbp == 120: any assignment is acceptable
    assert score_S(item["reference"], wrap({"expression": "120 / 3 + 2 * 120 / 3"}))["correct"]
    row["entities"]["Diastolic Blood Pressure"] = [60, "mm hg"]
    item = build_S(row)
    r = score_S(item["reference"], wrap({"expression": "60 / 3 + 2 * 120 / 3"}))   # swapped
    assert not r["correct"] and r["error_type"] == "structure_or_assignment_error"


def test_S_accidental_value_match():
    # anion gap: na - (cl + hco3); writing na - cl - hco3 is equivalent (correct),
    # writing (na - cl) * hco3 / 60 gives the right value (16) with a wrong structure
    row = {**CG_ROW, "Calculator ID": "39", "Calculator Name": "Anion Gap",
           "entities": {"Sodium": [140, "mEq/L"], "Chloride": [100, "mEq/L"], "Bicarbonate": [24, "mEq/L"]}}
    item = build_S(row)
    assert score_S(item["reference"], wrap({"expression": "140 - 100 - 24"}))["correct"]
    r = score_S(item["reference"], wrap({"expression": "(140 - 100) * 24 / 60"}))
    assert not r["correct"] and r["error_type"] == "accidental_value_match"


def test_S_premature_computation_and_symbols():
    item = build_S(CG_ROW)
    r = score_S(item["reference"], wrap({"expression": str(item["reference"]["gold_value"])}))
    assert r["error_type"] == "premature_computation"
    r = score_S(item["reference"], wrap({"expression": item["reference"]["formula"]}))
    assert r["error_type"] == "unsubstituted_variable"


# ---------------------------------------------------------------- A / E2E

def test_A_tolerances():
    item = build_A(CG_ROW)
    g = item["reference"]["gold_value"]
    assert score_A(item["reference"], wrap({"result": g * 1.005}))["correct"]
    assert not score_A(item["reference"], wrap({"result": g * 1.005}))["correct_strict"]
    assert not score_A(item["reference"], wrap({"result": g * 1.02}))["correct"]
    assert score_A(item["reference"], wrap({"result": f"{g:.4f} mL/min"}))["correct"]
    assert not score_A(item["reference"], "about 80")["format_valid"]


def test_E2E_bounds():
    ref = {"ground_truth": 79.88, "lower": 75.89, "upper": 83.88}
    assert score_E2E(ref, wrap({"answer": 80}))["correct"]
    assert not score_E2E(ref, wrap({"answer": 90}))["correct"]


def test_S_reordered_copy_is_canonical_match():
    row = {**CG_ROW, "Calculator ID": "39", "Calculator Name": "Anion Gap",
           "entities": {"Sodium": [140, "mEq/L"], "Chloride": [100, "mEq/L"], "Bicarbonate": [24, "mEq/L"]}}
    item = build_S(row)
    r = score_S(item["reference"], wrap({"expression": "140 - (24 + 100)"}))
    assert r["correct"] and r["match"] == "canonical"


def test_K_pool_points_inherit_patient_categories():
    item = build_K(CKD_ROW, CKD_POOL)
    assert all(p["sex"] == "Male" for p in item["reference"]["point_entities"])


def test_E_unit_spelling_and_unit_as_written_in_note():
    from medcalc_kit.probes.extraction import score_field
    assert score_field("Glucose", "quantity", [273.0, "mg/dL"], {"value": 273, "unit": "mg/dl"}, True) == "correct"
    assert score_field("age", "quantity", [59, "years"], {"value": 59, "unit": "yr"}, True) == "correct"
    # the note itself says mg/dL for chloride (typo): copying it as written is not an extraction error
    note = "Labs: sodium 140 mEq/L, chloride 103 mg/dL (98-110 mg/dL), potassium 4.1."
    pred = {"value": 103, "unit": "mg/dL"}
    assert score_field("Chloride", "quantity", [103.0, "mEq/L"], pred, True, note) == "correct"
    assert score_field("Chloride", "quantity", [103.0, "mEq/L"], pred, True) == "unit_error"
    assert score_field("Chloride", "quantity", [103.0, "mEq/L"], {"value": 103, "unit": "mmol/dL"}, True,
                       note) == "unit_error"


def test_K_perturbed_points_keep_integer_daily_counts():
    # MME items have no pool points: perturbed 'per day' counts must stay positive integers,
    # otherwise a correct piecewise answer ('perday == 1' / 'perday > 1') has no applicable case.
    ref = {"symbols": ["dose_morphine", "perday_morphine"],
           "entities": {"Morphine Dose": [10, "mg"], "Morphine Dose Per Day": [3, "per day"]}}
    ans = {"cases": [{"condition": "perday_morphine == 1", "formula": "dose_morphine"},
                     {"condition": "perday_morphine > 1", "formula": "dose_morphine * perday_morphine"}]}
    r = score_K(ref, wrap(ans), "49", seed=3)
    assert r["correct"], r


def test_E_steroid_name_without_route():
    from medcalc_kit.probes.extraction import score_field
    gold = ["Cortisone PO", 49.333, "mg"]
    for drug in ["Cortisone PO", "Cortisone", "cortisone po"]:
        assert score_field("input steroid", "steroid", gold, {"drug": drug, "value": 49.333}, True) == "correct"
    assert score_field("input steroid", "steroid", gold, {"drug": "Prednisone", "value": 49.333}, True) == "wrong_value"


def test_E_null_value_dict_means_not_mentioned():
    from medcalc_kit.probes.extraction import score_field
    null = {"value": None, "unit": None}
    assert score_field("Body Mass Index (BMI)", "quantity", None, null, True) == "correct"
    assert score_field("Bicarbonate", "quantity", [24.0, "mEq/L"], null, True) == "missing"


def test_K_undefined_branch_is_a_domain_exclusion():
    ref = {"symbols": ["weight", "height"], "entities": {"weight": [70, "kg"], "height": [175, "cm"]}}
    ok = {"cases": [{"condition": "height <= 0", "formula": "undefined"},
                    {"condition": "height > 0", "formula": "weight * (100 / height)²"}]}
    assert score_K(ref, wrap(ok), "6", seed=1)["correct"]
    bad = {"cases": [{"condition": "height <= 170", "formula": "undefined"},
                     {"condition": "height > 170", "formula": "weight / (height / 100)^2"}]}
    assert not score_K(ref, wrap(bad), "6", seed=1)["correct"]
