"""Example / MedCalcDataset / ProbeSuite on a small hand-made table (no download)."""
import json

import pandas as pd
import pytest

import medcalc_kit as mk
from medcalc_kit.data import Example, MedCalcDataset, flag_train_rows
from medcalc_kit.probes import ProbeSuite, read_items, write_items

QUESTION_CG = ("What is the patient's Creatinine Clearance using the Cockroft-Gault Equation in terms of mL/min? "
               "You should use the patient's medical values and health status when they were first admitted to "
               "the hospital prior to any treatment.")


def row(i, cid="2", split="train", note=None, **entities):
    ents = entities or {"sex": "Female", "age": [50 + i, "years"], "weight": [60.0 + i, "kg"],
                        "height": [160.0, "cm"], "creatinine": [0.9, "mg/dL"]}
    return {"Row Number": i, "Calculator ID": cid, "Calculator Name": "Creatinine Clearance (Cockcroft-Gault Equation)",
            "Category": "lab test", "Output Type": "decimal", "Note ID": str(i), "Note Type": "Synthetic",
            "Patient Note": note or f"Patient {i}: woman of {50 + i} years, {60 + i} kg, 160 cm, creatinine 0.9 mg/dL.",
            "Question": QUESTION_CG, "Relevant Entities": "", "entities": ents,
            "Ground Truth Answer": 1.0, "Lower Limit": 0.0, "Upper Limit": 1e6, "Ground Truth Explanation": "",
            "split": split, "example_id": f"{split}:{cid}:{i}"}


@pytest.fixture
def ds():
    return MedCalcDataset(pd.DataFrame([row(i) for i in range(6)] + [row(9, split="test")]))


def test_example_and_dataset_navigation(ds):
    assert len(ds) == 7 and isinstance(ds[0], Example)
    ex = ds["test:2:9"]
    assert ex.split == "test" and ex.calculator_id == "2" and ex.entities["age"] == [59, "years"]
    assert ex.derive().answer == pytest.approx(mk.calculators.derive("2", ex.entities).answer)
    assert len(ds.filter(split="train")) == 6 and len(ds.filter(calculator=2)) == 7
    assert ds.select(["train:2:3", "train:2:1"]).example_ids == ["train:2:3", "train:2:1"]
    cal = ds.calculators()
    assert cal.loc[0, "train"] == 6 and cal.loc[0, "test"] == 1


def test_example_from_hand_made_row_without_answer():
    r = row(1)
    for k in ("Ground Truth Answer", "Lower Limit", "Upper Limit"):
        del r[k]
    ex = Example.from_row(r)
    assert ex.note.startswith("Patient 1") and ex.ground_truth != ex.ground_truth  # NaN


def test_minimal_hand_made_example_for_substitution():
    ex = Example.from_row({"example_id": "demo:39:1", "Calculator ID": "39",
                           "entities": {"Sodium": [140, "mEq/L"], "Chloride": [100, "mEq/L"],
                                        "Bicarbonate": [24, "mEq/L"]}})
    item = mk.probes.substitution.build(ex)
    assert item["reference"]["gold_value"] == pytest.approx(16)


def test_leakage_flags_duplicate_note(ds):
    dup = MedCalcDataset(pd.concat([ds.df, pd.DataFrame([row(20, note=ds["test:2:9"].note)])]))
    flags = flag_train_rows(dup).set_index("example_id")
    assert flags.loc["train:2:20", "leak_text"] and not flags.loc["train:2:1", "leak_text"]


def test_suite_builds_every_probe_in_order(ds, tmp_path):
    examples = ds.filter(split="train")
    suite = ProbeSuite(k_pool=ds.filter(split="test"), schema=ds)
    built = suite.build(examples)
    assert built.probe.unique().tolist() == ["E", "U", "K", "S", "A", "E2E"]
    for _, items in built.groupby("probe", sort=False):
        assert items.example_id.tolist() == examples.example_ids
        assert items.messages.map(lambda m: m[0]["role"] == "system").all()
    # K test points come from the pool (other patients), not from perturbations
    k = built[built.probe == "K"].iloc[0]
    assert k.reference["point_entities"][0]["age"] == [59, "years"]
    assert suite.build(examples, as_frame=False)["K"][0]["item_id"] == k.item_id
    counts = write_items(built, tmp_path)
    assert counts["S"] == 6
    back = read_items(tmp_path)
    assert len(back) == 36 and set(back.item_id) == set(built.item_id)
    assert len(read_items(tmp_path, as_frame=False)) == 36


def test_gold_answers_score_correct(ds):
    built = ProbeSuite(probes=["S", "A", "E2E"]).build(ds.filter(split="train"), as_frame=False)
    s, a, e2e = built["S"][0], built["A"][0], built["E2E"][0]
    assert mk.probes.score(s, json.dumps({"expression": s["reference"]["gold_expression"]}))["correct"]
    assert mk.probes.score(a, json.dumps({"result": a["reference"]["gold_value"]}))["correct"]
    assert mk.probes.score(e2e, '{"answer": 10}')["correct"]


def test_unknown_probe_rejected():
    with pytest.raises(ValueError):
        ProbeSuite(probes=["E", "X"])
