"""Prompt variants: same information and answer format in every paraphrase; traceability; sensitivity report."""
import re

import pandas as pd
import pytest

import medcalc_kit as mk
from medcalc_kit.probes import arithmetic, conversion, end_to_end, extraction, knowledge, substitution
from medcalc_kit.probes.common import template_hash

PLACEHOLDER = re.compile(r"\{(\w+)\}")
MODULE_TEMPLATES = {"E": extraction.TEMPLATES, "U": conversion.TEMPLATES, "K": knowledge.TEMPLATES,
                    "K_patient": knowledge.PATIENT_TEMPLATES,
                    "S": substitution.TEMPLATES, "A": arithmetic.TEMPLATES, "E2E": end_to_end.TEMPLATES}
JSON_KEY = {"E": None, "U": '"value"', "K": '"cases"', "K_patient": '"formula"', "S": '"expression"', "A": '"result"',
            "E2E": '"answer"'}


@pytest.mark.parametrize("probe", list(MODULE_TEMPLATES))
def test_variants_share_placeholders_and_answer_format(probe):
    templates = MODULE_TEMPLATES[probe]
    assert list(templates) == ["v1", "v2", "v3"] and len(set(templates.values())) == 3
    names = [set(PLACEHOLDER.findall(t)) for t in templates.values()]
    assert all(n == names[0] for n in names), names                    # every variant gets the same information
    if JSON_KEY[probe]:
        assert all(JSON_KEY[probe] in t for t in templates.values())


@pytest.mark.parametrize("variant", ["v1", "v2", "v3"])
def test_reference_answers_are_correct_for_every_variant(variant):
    # K in "general" mode is left out: its reference answer is only right for calculators without branches
    suite = mk.ProbeSuite({p: {"template": variant} for p in ("E", "U", "S", "A", "E2E")}
                          | {"Kp": {"task": "K", "mode": "patient", "template": variant}})
    items = suite.build(mk.data.demo(3))
    assert (items.template == variant).all()
    assert not items.messages.map(lambda m: bool(PLACEHOLDER.search(m[-1]["content"].replace('{"', '')))).any()
    texts = [mk.reference_answer(it) for _, it in items.iterrows()]
    scores = mk.score_records(pd.DataFrame({"item_id": items.item_id, "text": texts}), items)
    assert scores.correct.all() and (scores.template == variant).all()


def test_templates_are_traceable():
    item = arithmetic.build(mk.data.demo()[2], template="v2")
    assert item["template"] == "v2" and item["template_hash"] == template_hash(arithmetic.TEMPLATES["v2"])
    assert arithmetic.build(mk.data.demo()[2])["template"] == "v1"
    custom = arithmetic.build(mk.data.demo()[2], template="Compute {expression}.")
    assert custom["template"] == "custom" and custom["messages"][-1]["content"] == "Compute 140 - (104 + 24)."


def test_evaluate_model_with_prompt_variants(tmp_path):
    ds = mk.data.demo(2)
    oracle_by_prompt = {}

    def model(messages, max_new_tokens):
        return oracle_by_prompt[mk.generation.prompt_key(messages, max_new_tokens)]

    specs = {"E": {}, "U": {}, "K": {"mode": "patient"}, "S": {}, "A": {}, "E2E": {}}
    for v in ("v1", "v2", "v3"):
        items = mk.ProbeSuite({k: {**o, "template": v} for k, o in specs.items()}).build(ds)
        for _, it in items.iterrows():
            text = mk.reference_answer(it)
            if v == "v3" and it["probe"] == "A":
                text = '{"result": 0}'                                   # v3 of A always wrong
            oracle_by_prompt[mk.generation.prompt_key(it["messages"], it["max_new_tokens"])] = text
    report = mk.evaluate_model(model, tmp_path, dataset=ds, split="demo", prompt_variants=3)
    assert set(report.items.probe) == {f"{p}{s}" for p in specs for s in ("", "@v2", "@v3")}
    assert report.steps.loc["A", "accuracy"] == 1.0                     # the views use v1
    sens = report.prompt_sensitivity
    assert sens.loc["A", ["v1", "v2", "v3"]].tolist() == [1.0, 1.0, 0.0] and sens.loc["A", "range"] == 1.0
    assert sens.loc["E", "range"] == 0.0
    assert report.consistency.loc["all steps correct", "e2e_accuracy"] == 1.0
    assert "prompt variants: 0.0% to 100.0%" in repr(report)
    assert (tmp_path / "prompt_sensitivity.csv").exists()
    with pytest.raises(ValueError):
        mk.evaluate_model(model, tmp_path, dataset=ds, split="demo", prompt_variants=4)
    with pytest.raises(ValueError, match="own template"):
        mk.evaluate_model(model, tmp_path, dataset=ds, split="demo", prompt_variants=2,
                          probe_options={"A": {"template": "Compute {expression}."}})
