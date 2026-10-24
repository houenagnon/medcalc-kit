"""Full-benchmark E2E (numbers, dates, durations) and the one-call evaluator."""
import json

import pandas as pd

import medcalc_kit as mk
from medcalc_kit.data import Example, MedCalcDataset
from medcalc_kit.probes import end_to_end

DUE = Example.from_row({"example_id": "test:13:1", "Calculator ID": "13", "Calculator Name": "Estimated Due Date",
                        "Category": "date", "Patient Note": "LMP 09/17/2011, cycle 21 days.",
                        "Question": "What is the estimated due date?", "entities": {"cycle length": 21},
                        "Ground Truth Answer": "06/16/2012", "Lower Limit": "06/16/2012",
                        "Upper Limit": "06/16/2012"})
AGE = Example.from_row({"example_id": "test:69:1", "Calculator ID": "69",
                        "Calculator Name": "Estimated Gestational Age", "Category": "date",
                        "Patient Note": "LMP 01/06/2022. Today 04/29/2022.",
                        "Question": "Gestational age?", "entities": {},
                        "Ground Truth Answer": "('16 weeks', '1 days')", "Lower Limit": "('16 weeks', '1 days')",
                        "Upper Limit": "('16 weeks', '1 days')"})


def test_date_and_duration_answers():
    assert DUE.ground_truth == "06/16/2012" and "06/16/2012" in repr(DUE)
    due = end_to_end.build(DUE)
    assert '"<MM/DD/YYYY>"' in due["messages"][-1]["content"]
    assert mk.score(due, '{"answer": "6/16/2012"}')["correct"]
    assert mk.score(due, '{"answer": "June 16, 2012"}')["correct"]
    assert mk.score(due, '{"answer": "06/23/2012"}')["error_days"] == 7
    assert mk.score(due, "06/16/2012")["error_type"] == "format_invalid"
    age = end_to_end.build(AGE)
    assert mk.score(age, '{"answer": {"weeks": 16, "days": 1}}')["correct"]
    assert mk.score(age, '{"answer": "(16 weeks, 1 day)"}')["correct"]
    assert mk.score(age, '{"answer": [16, 2]}')["error_type"] == "wrong_duration"
    for item in (due, age):
        assert mk.score(item, mk.reference_answer(item))["correct"]


def test_step_probes_only_for_registry_calculators():
    ds = MedCalcDataset(pd.concat([mk.data.demo().df.iloc[:1], pd.DataFrame([{
        "example_id": "test:13:1", "Calculator ID": "13", "Calculator Name": "Estimated Due Date", "Category": "date",
        "Patient Note": "LMP 09/17/2011.", "Question": "Due date?", "entities": {"cycle length": 21},
        "Ground Truth Answer": "06/16/2012", "Lower Limit": "06/16/2012", "Upper Limit": "06/16/2012",
        "split": "demo"}])], ignore_index=True))
    items = mk.ProbeSuite().build(ds)
    assert items[items.example_id == "test:13:1"].probe.tolist() == ["E2E"]
    assert len(items[items.example_id == "demo:2:1"]) == 6


def test_evaluate_model_resumes_and_rescores(tmp_path):
    ds = mk.data.demo()
    calls = []

    def model(messages, max_new_tokens):
        calls.append(1)
        return '{"answer": 12, "result": 12}'

    report = mk.evaluate_model(model, tmp_path, dataset=ds, split="demo", k_pool=None)
    n = len(calls)
    assert n == len(report.items) and (tmp_path / "generations.jsonl").exists()
    assert set(report.steps.index) == {"E", "U", "K", "S", "A", "E2E"}
    assert report.examples.set_index("example_id").loc["demo:39:1", "E2E"]
    assert set(report.first_failures.index) <= {"E", "K", "S", "A", "none"}
    assert (tmp_path / "general.csv").exists() and (tmp_path / "by_calculator.csv").exists()
    again = mk.evaluate_model(model, tmp_path, dataset=ds, split="demo", k_pool=None)       # nothing left to generate
    assert len(calls) == n and again.scores.correct.sum() == report.scores.correct.sum()
    rescored = mk.evaluate_model(None, tmp_path, dataset=ds, split="demo", model_id="model", k_pool=None)
    assert len(rescored.scores) == len(report.scores)
    assert "general (end to end)" in repr(report)


def test_general_only(tmp_path):
    report = mk.evaluate_model(lambda m, n: json.dumps({"answer": 1}), tmp_path, dataset=mk.data.demo(),
                               split="demo", steps=())
    assert set(report.items.probe) == {"E2E"} and report.general.loc["all", "n"] == 4


def test_report_keeps_artifact_categories(tmp_path):
    report = mk.evaluate_model(lambda m, n: "", tmp_path, dataset=mk.data.demo(), split="demo", steps=())
    assert set(report.scores.category) == {"empty"}
    assert set(report.scores.calculator_category) == {"lab test", "physical"}
    assert list(report.general.index) == ["all", "lab test", "physical"]
