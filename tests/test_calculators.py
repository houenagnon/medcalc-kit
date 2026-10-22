"""Hand-computed checks of the registry (independent of the dataset)."""
import pytest

from medcalc_kit import expr as mathexpr
from medcalc_kit.calculators import CALCULATORS, derive


def test_registry_covers_33_calculators():
    assert len(CALCULATORS) == 33


def test_bmi():
    d = derive("6", {"weight": [70, "kg"], "height": [175, "cm"]})
    assert d.answer == pytest.approx(70 / 1.75**2)


def test_map():
    assert derive("5", {"Systolic Blood Pressure": [120, "mm hg"],
                        "Diastolic Blood Pressure": [80, "mm hg"]}).answer == pytest.approx(93.3333, rel=1e-5)


def test_cockcroft_gault_benchmark_example():
    # MedCalc-Bench-Verified test example (ground truth 25.2381): BMI 18.07 -> underweight -> actual weight
    e = {"sex": "Male", "age": [87, "years"], "weight": [48.0, "kg"], "height": [163.0, "cm"],
         "creatinine": [1.4, "mg/dL"]}
    d = derive("2", e)
    assert d.branches[-1].startswith("bmi<18.5")
    assert d.answer == pytest.approx(25.2381, rel=1e-4)


def test_cockcroft_gault_obese_uses_abw():
    e = {"sex": "Female", "age": [60, "years"], "weight": [100, "kg"], "height": [160, "cm"],
         "creatinine": [1.0, "mg/dL"]}
    d = derive("2", e)
    ibw = 45.5 + 2.3 * (160 / 2.54 - 60)
    abw = ibw + 0.4 * (100 - ibw)
    assert d.answer == pytest.approx((80 * abw * 0.85) / 72)


def test_ckd_epi_2021():
    # Male, 50 y, Scr 1.2 mg/dL -> 142 * (1.2/0.9)^-1.2 * 0.9938^50
    d = derive("3", {"sex": "Male", "age": [50, "years"], "creatinine": [1.2, "mg/dL"]})
    assert d.answer == pytest.approx(142 * (1.2 / 0.9) ** -1.2 * 0.9938**50)


def test_maintenance_fluids_branches():
    assert derive("22", {"weight": [8, "kg"]}).answer == 32
    assert derive("22", {"weight": [15, "kg"]}).answer == 50
    assert derive("22", {"weight": [70, "kg"]}).answer == 110


def test_meld_na_dialysis_forces_creatinine_4():
    e = {"creatinine": [0.8, "mg/dL"], "Bilirubin": [1.0, "mg/dL"], "international normalized ratio": 1.0,
         "Sodium": [137, "mEq/L"], "Dialysis at least twice in the past week": True}
    d = derive("23", e)
    assert d.env["scr"] == 4


def test_mme_sum():
    e = {"HYDROmorphone Dose": [10, "mg"], "HYDROmorphone Dose Per Day": [1, "per day"],
         "TraMADol Dose": [30, "mg"], "TraMADol Dose Per Day": [2, "per day"]}
    assert derive("49", e).answer == pytest.approx(62)


def test_every_step_expression_is_parsable_and_reproducible():
    """Each step's expression re-evaluated from inputs+coefficients reproduces the stored value."""
    e = {"sex": "Male", "age": [87, "years"], "weight": [48.0, "kg"], "height": [163.0, "cm"],
         "creatinine": [1.4, "mg/dL"]}
    d = derive("2", e)
    env = {**d.inputs, **d.coefficients}
    for s in d.steps:
        v = mathexpr.evaluate(s.expr, env)
        assert v == pytest.approx(s.value)
        env[s.name] = v


def test_derivation_and_registry_as_frames():
    from medcalc_kit.calculators import table

    df = derive("6", {"weight": [70, "kg"], "height": [175, "cm"]}).to_frame()
    assert df.kind.tolist() == ["input", "input", "step"]
    assert df.iloc[-1]["value"] == pytest.approx(70 / 1.75**2)
    t = table()
    assert len(t) == 33 and t.set_index("calculator_id").loc["31", "reference_deviation"].startswith("HOMA-IR")
