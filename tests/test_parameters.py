"""Every setting is a function argument: templates, budgets, modes, tolerances, case semantics, labels."""
import json

import pytest

import medcalc_kit as mk
from medcalc_kit.data import Example
from medcalc_kit.evaluate import score_records
from medcalc_kit.generation import classify_generation
from medcalc_kit.probes import ProbeSuite, arithmetic, end_to_end, extraction, knowledge, substitution
from medcalc_kit.probes.common import render

CG = Example.from_row({
    "example_id": "x:2:1", "Calculator ID": "2", "Calculator Name": "Creatinine Clearance (Cockcroft-Gault Equation)",
    "Patient Note": "A 51-year-old woman, 68.6 kg, 158 cm, creatinine 0.76 mg/dL.",
    "Question": "What is the patient's Creatinine Clearance using the Cockroft-Gault Equation in terms of mL/min?",
    "entities": {"sex": "Female", "age": [51, "years"], "weight": [68.6, "kg"], "height": [158.0, "cm"],
                 "creatinine": [0.76, "mg/dL"]},
    "Ground Truth Answer": 70.0, "Lower Limit": 66.5, "Upper Limit": 73.5})


def cg_pool(n=40):
    """Women of various sizes: some underweight, normal and overweight (three Cockcroft-Gault branches)."""
    return [{"sex": "Female", "age": [30 + i, "years"], "weight": [40.0 + 2 * i, "kg"], "height": [160.0, "cm"],
             "creatinine": [0.8, "mg/dL"]} for i in range(n)]


def test_render_only_replaces_known_placeholders():
    assert render('{a} and {"json": 1} and {b}', a="x") == 'x and {"json": 1} and {b}'


def test_templates_budgets_and_system_prompt():
    item = arithmetic.build(CG, template="Compute {expression} now.", max_new_tokens=1536, system_prompt=None)
    assert item["messages"] == [{"role": "user", "content": f"Compute {item['reference']['expression']} now."}]
    assert item["max_new_tokens"] == 1536
    e = extraction.build(CG, template="NOTE {note} FIELDS {fields}", field_hints={"age": "an integer"})
    assert e["messages"][-1]["content"].startswith("NOTE A 51-year-old") and '- "age": an integer' in \
        e["messages"][-1]["content"]


def test_digits_change_values_and_gold_consistently():
    s = substitution.build(CG, digits=2)
    assert "- weight = 69" in s["messages"][-1]["content"] and "69" in s["reference"]["gold_expression"]


def test_mme_fields_are_described_explicitly():
    ex = Example.from_row({"example_id": "x:49:1", "Calculator ID": "49", "Calculator Name": "MME",
                           "Patient Note": "...", "Question": "MME?",
                           "entities": {"Morphine Dose": [10, "mg"], "Morphine Dose Per Day": [3, "per day"]}})
    text = extraction.build(ex)["messages"][-1]["content"]
    assert '"Morphine Dose Per Day": {"value": <number of administrations per day>' in text
    assert '"Morphine Dose": {"value": <dose of one administration>' in text


def test_knowledge_patient_mode_uses_values_and_same_branch_points():
    item = knowledge.build(CG, cg_pool(), mode="patient", n_points=10)
    prompt = item["messages"][-1]["content"]
    assert "- weight = 68.6" in prompt and '{"formula": "<expression>"}' in prompt
    ref = item["reference"]
    assert ref["mode"] == "patient" and ref["branches"] == CG.derive().branches
    assert len(ref["point_entities"]) == 10
    assert all(mk.calculators.derive("2", p).branches == ref["branches"] for p in ref["point_entities"])
    # this woman is overweight: the adjusted-weight formula is right on every same-branch point
    ibw = "45.5 + 2.3 * (height / 2.54 - 60)"
    good = {"formula": f"(140 - age) * ({ibw} + 0.4 * (weight - ({ibw}))) * 0.85 / (72 * scr)"}
    assert knowledge.score(item, json.dumps(good))["correct"]
    assert not knowledge.score(item, json.dumps({"formula": "(140 - age) * weight * 0.85 / (72 * scr)"}))["correct"]
    assert not knowledge.score(item, json.dumps({"formula": "57.1"}))["correct"]   # a number is not a formula


def test_knowledge_case_semantics():
    bmi = Example.from_row({"example_id": "x:6:1", "Calculator ID": "6", "Calculator Name": "BMI",
                            "Question": "BMI?", "entities": {"weight": [70, "kg"], "height": [175, "cm"]}})
    item = knowledge.build(bmi)
    if_elif = {"cases": [{"condition": "weight < 1000", "formula": "weight / (height / 100)^2"},
                         {"condition": "weight < 2000", "formula": "0"}]}      # 2nd case never reached in order
    assert not knowledge.score(item, json.dumps(if_elif))["correct"]            # overlapping cases disagree
    assert knowledge.score(item, json.dumps(if_elif), case_semantics="first_match")["correct"]
    with pytest.raises(ValueError):
        knowledge.score(item, json.dumps(if_elif), case_semantics="whatever")


def test_perturbed_points_are_plausible_by_default():
    ref = knowledge.build(CG)["reference"]          # no pool: perturbations
    pts = knowledge.test_points(ref, "2", seed=1, perturbation_factor=10)
    assert all(0 <= p["age"] <= 120 and 30 <= p["height"] <= 250 for p, _ in pts)
    wild = knowledge.test_points(ref, "2", seed=1, perturbation_factor=10, plausible_ranges=None)
    assert any(p["age"] > 120 or p["height"] > 250 for p, _ in wild)


def test_tolerances_are_arguments():
    a = arithmetic.build(CG)
    text = json.dumps({"result": a["reference"]["gold_value"] * 1.005})
    assert arithmetic.score(a, text)["correct"] and not arithmetic.score(a, text, rel_tol=0.001)["correct"]
    e2e = end_to_end.build(CG)
    assert end_to_end.score(e2e, '{"answer": 73}')["correct"]
    assert not end_to_end.score(e2e, '{"answer": 73}', rel_tol=0.01)["correct"]


def test_suite_variants_and_scoring_options(tmp_path):
    suite = ProbeSuite({"K": {"mode": "patient", "max_new_tokens": 1536}, "Kg": {"task": "K"},
                        "A": {"template": "{expression} = ?"}}, k_pool=None)
    built = suite.build([CG], as_frame=False)
    k, kg = built["K"][0], built["Kg"][0]
    assert k["max_new_tokens"] == 1536 and k["reference"]["mode"] == "patient" and "task" not in k
    assert kg["item_id"] == "x:2:1:Kg" and kg["task"] == "K" and "mode" not in kg["reference"]
    assert built["A"][0]["messages"][-1]["content"].endswith("= ?")
    with pytest.raises(ValueError):
        ProbeSuite({"Z": {"task": "nope"}})

    a = built["A"][0]
    rec = {"item_id": a["item_id"], "example_id": "x:2:1", "calculator_id": "2", "probe": "A", "error": None,
           "text": json.dumps({"result": a["reference"]["gold_value"] * 1.005}), "n_new_tokens": 5}
    assert score_records([rec], [a]).correct.all()
    assert not score_records([rec], [a], scoring={"A": {"rel_tol": 0.001}}).correct.any()


def test_artifact_thresholds_are_arguments():
    looping = "\n".join(["the same line again"] * 3)
    assert classify_generation(looping, 10, 100, True) == "degenerate"
    assert classify_generation(looping, 10, 100, True, line_repeats=5) == "well_formed"


def test_items_frame_round_trip_with_partial_task(tmp_path):
    built = ProbeSuite({"K": {}, "Kg": {"task": "K"}, "A": {}}).build([CG])
    assert built.columns[:3].tolist() == ["item_id", "probe", "task"] and built.task.isna().sum() == 2
    items = mk.probes.as_items(built)
    assert "task" not in items[0] and items[1]["task"] == "K"
    assert items == mk.probes.as_items(ProbeSuite({"K": {}, "Kg": {"task": "K"}, "A": {}}).build([CG], as_frame=False))
    a = built[built.probe == "A"].iloc[0]
    rec = {"item_id": a.item_id, "example_id": "x:2:1", "calculator_id": "2", "probe": "A", "error": None,
           "text": json.dumps({"result": a.reference["gold_value"]}), "n_new_tokens": 5}
    import pandas as pd
    assert score_records(pd.DataFrame([rec]), built).correct.all()


def test_usability_shortcuts(tmp_path):
    items = mk.ProbeSuite("A").build(mk.data.demo())
    row = items.iloc[0]
    assert mk.score(row, mk.reference_answer(row))["correct"]          # a DataFrame row works as an item
    assert mk.probes.prompt(row).startswith("[system]")
    out = tmp_path / "out.jsonl"
    assert mk.run_items(items, out, lambda messages, n: '{"result": 12}', model_id="twelve") == 4
    records = mk.read_records(out)
    assert (records.model_id == "twelve").all() and (records.n_new_tokens == 0).all()
    df = mk.score_records(records[["item_id", "text"]], items)          # only item_id and text needed
    assert df.correct.sum() == 1 and set(df.category) == {"well_formed"}
    assert mk.data.demo().sample(2, seed=1).example_ids == mk.data.demo().sample(2, seed=1).example_ids
    with pytest.raises(KeyError, match="needs the entity 'height'"):
        mk.derive("6", {"weight": [70, "kg"]})


def test_e_fields_option_applies_to_every_example():
    fields = {"weight": "quantity"}
    items = ProbeSuite({"E": {"fields": fields}}).build(mk.data.demo().filter(calculator=[6, 2]))
    assert all(set(ref["fields"]) == {"weight"} for ref in items.reference)
