"""Probe U: unit conversion of one patient value to the unit the registry's formula uses."""
import pytest

import medcalc_kit as mk
from medcalc_kit.data import from_records
from medcalc_kit.probes import conversion

# Clinical factors (canonical unit -> other unit), computed independently of the kit: 1 / molar mass, x valence.
FACTORS = {
    ("creatinine", "µmol/L"): 1e4 / 113.12, ("Urine creatinine", "µmol/L"): 1e4 / 113.12,
    ("Urine creatinine", "mmol/L"): 10 / 113.12, ("Sodium", "mmol/L"): 1.0, ("Urine sodium", "mmol/L"): 1.0,
    ("Chloride", "mmol/L"): 1.0, ("Bicarbonate", "mmol/L"): 1.0, ("Glucose", "mmol/L"): 10 / 180.16,
    ("Calcium", "mmol/L"): 10 / 40.08, ("Calcium", "mEq/L"): 20 / 40.08,
    ("Blood Urea Nitrogen (BUN)", "mmol/L"): 10 / 28.02, ("Albumin", "g/L"): 10.0,
    ("Total cholesterol", "mmol/L"): 10 / 386.654, ("high-density lipoprotein cholesterol", "mmol/L"): 10 / 386.654,
    ("Triglycerides", "mmol/L"): 10 / 861.338, ("weight", "lbs"): 1 / 0.453592, ("height", "m"): 0.01,
    ("height", "in"): 1 / 2.54,
}
VALUES = {"creatinine": 1.2, "Urine creatinine": 95.0, "Sodium": 138.0, "Urine sodium": 40.0, "Chloride": 101.0,
          "Bicarbonate": 23.0, "Glucose": 250.0, "Calcium": 8.4, "Blood Urea Nitrogen (BUN)": 30.0, "Albumin": 3.1,
          "Total cholesterol": 210.0, "high-density lipoprotein cholesterol": 48.0, "Triglycerides": 150.0,
          "weight": 82.0, "height": 168.0}


def example(field):
    _, _, unit, _ = conversion.UNIT_TABLE[field]
    return from_records([{"Calculator ID": "2", "entities": {field: [VALUES[field], unit]}}])[0]


def test_every_pair_of_the_table_is_covered_and_correct():
    pairs = {(f, u) for f, (_, _, _, alts) in conversion.UNIT_TABLE.items() for u in alts}
    assert pairs == set(FACTORS)
    for (field, unit), factor in FACTORS.items():
        item = conversion.build(example(field), field, unit)
        ref = item["reference"]
        assert ref["source_unit"] == unit and ref["target_unit"] == conversion.UNIT_TABLE[field][2]
        assert ref["source_value"] == pytest.approx(VALUES[field] * factor, rel=1e-3)        # 4 significant digits
        assert ref["gold_value"] == pytest.approx(ref["source_value"] / factor, rel=1e-9)    # from the value shown
        assert mk.score(item, mk.reference_answer(item))["correct"]
        text = item["messages"][-1]["content"]
        assert unit in text and ref["target_unit"] in text and "molar" not in text.lower()
        assert "valence" not in text.lower() and "113" not in text


def test_error_types():
    item = conversion.build(example("Glucose"), "Glucose", "mmol/L")       # 13.88 mmol/L -> 250 mg/dL
    ref = item["reference"]
    answers = {ref["gold_value"]: None, ref["source_value"]: "unconverted",
               ref["source_value"] ** 2 / ref["gold_value"]: "inverse_factor", 999.0: "wrong_value"}
    for value, error in answers.items():
        assert mk.score(item, f'{{"value": {value}}}')["error_type"] == error
    assert mk.score(item, "250 mg/dL")["error_type"] == "format_invalid"
    sodium = conversion.build(example("Sodium"), "Sodium", "mmol/L")       # identity: copying it is right
    assert mk.score(sodium, '{"value": 138}')["correct"]


def test_unit_draw_is_reproducible():
    ex = example("height")
    units = [conversion.build(ex, "height", seed=s)["reference"]["source_unit"] for s in range(20)]
    assert units == [conversion.build(ex, "height", seed=s)["reference"]["source_unit"] for s in range(20)]
    assert set(units) == {"m", "in"}
    a = conversion.build(ex, "height", seed=3)
    assert a["messages"] == conversion.build(ex, "height", seed=3)["messages"]


def test_default_field_and_examples_without_convertible_value():
    ds = mk.data.demo()
    assert conversion.build(ds[0])["reference"]["field"] == "weight"
    with pytest.raises(ValueError, match="no value"):
        conversion.build(ds[3])                                             # mean arterial pressure
    items = mk.ProbeSuite(["U"]).build(ds)
    assert items.example_id.tolist() == ["demo:2:1", "demo:6:1", "demo:39:1"]


@pytest.mark.parametrize("variant", ["v1", "v2", "v3"])
def test_variants(variant):
    item = conversion.build(example("creatinine"), "creatinine", "µmol/L", template=variant)
    assert item["template"] == variant and mk.score(item, mk.reference_answer(item))["correct"]


def test_substitution_with_values_in_another_unit():
    from medcalc_kit.probes import substitution

    ex = mk.data.demo()[0]                                            # Cockcroft-Gault, creatinine 0.76 mg/dL
    plain = substitution.build(ex)
    assert set(plain["reference"]) == {"formula", "values", "gold_expression", "gold_value"} and plain["probe"] == "S"
    item = substitution.build(ex, value_units={"scr": "µmol/L", "weight": "lbs"})
    ref = item["reference"]
    assert item["probe"] == "S+U" and item["task"] == "S" and ref["shown_values"] == {"scr": 67.19, "weight": 151.2}
    assert ref["formula"] == plain["reference"]["formula"]                       # the formula's units do not change
    assert ref["gold_value"] == pytest.approx(plain["reference"]["gold_value"], rel=1e-3)
    text = item["messages"][-1]["content"]
    assert "67.19 µmol/L" in text and "151.2 lbs" in text and substitution.CONVERSION_NOTE in text
    gold = ref["gold_expression"]
    assert mk.score(item, mk.reference_answer(item))["correct"]
    rounded = gold.replace(f"{ref['values']['scr']:g}", "0.76").replace(f"{ref['values']['weight']:g}", "68.6")
    assert mk.score(item, f'{{"expression": "{rounded}"}}')["correct"]               # 1 % on converted values
    raw = gold.replace(f"{ref['values']['scr']:g}", "67.19")
    assert mk.score(item, f'{{"expression": "{raw}"}}')["error_type"] == "unconverted_value"
    with pytest.raises(ValueError, match="convertible variables"):
        substitution.build(ex, value_units={"age": "months"})
