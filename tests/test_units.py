import pytest

from medcalc_kit.units import (
    UnitError,
    age_years,
    clean_unit,
    concentration,
    height_cm,
    insulin_uIU_per_mL,
    platelets_1e9_per_L,
    weight_kg,
)


def test_creatinine_umol_to_mgdl():
    # 88.4 µmol/L ~ 1 mg/dL (molar mass 113.12)
    assert concentration(88.4, "µmol/L", "creatinine", "mg/dL") == pytest.approx(1.0, rel=1e-3)


def test_glucose_mmol_to_mgdl():
    assert concentration(5.55, "mmol/L", "glucose", "mg/dL") == pytest.approx(100, rel=1e-3)


def test_monovalent_meq_equals_mmol():
    assert concentration(140, "mmol/L", "sodium", "mEq/L") == pytest.approx(140)


def test_calcium_divalent():
    # 2.5 mmol/L calcium = 5 mEq/L = 10.02 mg/dL
    assert concentration(2.5, "mmol/L", "calcium", "mEq/L") == pytest.approx(5)
    assert concentration(2.5, "mmol/L", "calcium", "mg/dL") == pytest.approx(10.02)


def test_albumin_mass_units():
    assert concentration(35, "g/L", "albumin", "g/dL") == pytest.approx(3.5)
    assert concentration(3500, "mg/dL", "albumin", "g/dL") == pytest.approx(3.5)


def test_unknown_unit_raises():
    with pytest.raises(UnitError):
        concentration(1, "furlong/L", "sodium", "mEq/L")


def test_clean_unit_variants():
    assert clean_unit("μmol/L") == "µmol/L"
    assert clean_unit("\x0b5IU/mL") == "µIU/mL"
    assert clean_unit("s mm hg") == "mm Hg"


def test_anthropometry():
    assert weight_kg([100, "lbs"]) == pytest.approx(45.3592)
    assert weight_kg([3500, "g"]) == pytest.approx(3.5)
    assert height_cm([5, "ft", 10, "in"]) == pytest.approx(177.8)
    assert height_cm([1.75, "m"]) == pytest.approx(175)
    assert height_cm([70, "in"]) == pytest.approx(177.8)


def test_age_convention():
    assert age_years([45, "years"]) == 45
    assert age_years([2, "years", 11, "months"]) == 2
    assert age_years([30, "months"]) == 2
    assert age_years([6, "weeks"]) == 0
    assert age_years([10, "days"]) == 0


def test_platelets_and_insulin():
    assert platelets_1e9_per_L([250000, "µL"]) == pytest.approx(250)
    assert insulin_uIU_per_mL([60, "pmol/L"]) == pytest.approx(10)


def test_clean_unit_spelling_variants_from_model_outputs():
    assert clean_unit("mg/dl") == "mg/dL"
    assert clean_unit("meq/L") == "mEq/L"
    assert clean_unit("mmol/l") == "mmol/L"
    assert clean_unit("gm/dl") == "g/dL"
    assert clean_unit("inches") == "in" and clean_unit("kgs") == "kg" and clean_unit("cms") == "cm"
    assert clean_unit("IU/L") == "IU/L"                       # unknown components are left untouched
    assert concentration(2.8, "g/dl", "albumin", "g/dL") == pytest.approx(2.8)
    assert height_cm([69, "inches"]) == pytest.approx(175.26)


def test_platelet_unit_variants():
    for unit, value in [("µL", 191000), ("/µL", 191000), ("cells/mcL", 191000), ("10^3/µL", 191),
                        ("x10^9/L", 191), ("K/µL", 191)]:
        assert platelets_1e9_per_L([value, unit]) == pytest.approx(191), unit
