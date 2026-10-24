"""Optional LLM judge: a SECONDARY analysis of the free reasoning of end-to-end (E2E) answers.

The judge reads the patient note, the question, the full reference computation of the registry (values extracted,
values in the formula's units, formula of the patient's branch, substituted expression, result) and the reasoning of
the model evaluated, and names the first step that went wrong. It never replaces the deterministic scoring of the
final answer (`probes.score`): use it to locate errors, and check it against human labels (`agreement`) first.

The judge is blind: its prompt holds nothing about the condition evaluated (model name, sparsity, method, metadata).

    >>> ex = mk.data.demo()[2]                                  # anion gap
    >>> e2e = mk.probes.end_to_end.build(ex)
    >>> record = {"item_id": e2e["item_id"], "model_id": "model-A", "text": "140 - 104 - 24 = 14. {\\"answer\\": 14}"}
    >>> item = build(e2e, record, example=ex)
    >>> "model-A" in item["messages"][-1]["content"]
    False
    >>> parse('Checking each step... {"first_error": "arithmetic", "evidence": "= 14"}', item)
    {'format_valid': True, 'first_error': 'arithmetic', 'evidence': '= 14'}
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import pandas as pd

from medcalc_kit import expr
from medcalc_kit.calculators import CALCULATORS
from medcalc_kit.data import Example, MedCalcDataset, as_example
from medcalc_kit.generation.runner import model_name, read_records, run_items
from medcalc_kit.parsing import extract_json
from medcalc_kit.probes.common import (
    DEFAULT_DIGITS,
    Item,
    as_item,
    as_items,
    branch_formula,
    fmt,
    make_item,
    render,
    resolve_template,
    symbol_doc,
)

DEFAULT_MAX_NEW_TOKENS = 1024
DEFAULT_SYSTEM_PROMPT = "You are a meticulous reviewer of clinical calculations."
# The steps of a calculation, in order; the judge names the first one that went wrong.
DEFAULT_STEPS = ("extraction", "conversion", "formula", "substitution", "arithmetic")
STEP_DESCRIPTIONS = {
    "extraction": "reading the patient's values in the note",
    "conversion": "converting the values to the units of the formula",
    "formula": "choosing and writing the right formula (and branch)",
    "substitution": "putting the values into the formula",
    "arithmetic": "computing the result",
}

# How to judge, in every template ({rules}): a step done differently but correctly is not an error.
JUDGING_RULES = (
    "A step done differently from the reference but correctly is NOT an error: other units (for example metres "
    "instead of centimetres), an equivalent form of the formula, or rounding that changes the result by less than "
    "1 %. Name a step only if it gives a wrong value. If every step is right, answer \"none\". In the evidence, "
    "quote plain text (no backslashes or LaTeX)."
)
# Placeholders: {note}, {question}, {reference} (the registry's computation), {reasoning}, {rules} (JUDGING_RULES),
# {categories} (one line per allowed answer), {choices} (the allowed values of first_error).
DEFAULT_TEMPLATE = (
    "You check the reasoning of an assistant who answered a clinical calculation question.\n\n"
    "Patient note:\n{note}\n\n"
    "Question: {question}\n\n"
    "Reference computation (correct):\n{reference}\n\n"
    "Reasoning to check:\n<<<\n{reasoning}\n>>>\n\n"
    "Compare the reasoning with the reference, step by step, and name the FIRST step where it goes wrong:\n"
    "{categories}\n\n{rules}\n\n"
    "Quote a short passage of the reasoning that shows it. End your answer with a JSON object of the form\n"
    '{"first_error": "<one of {choices}>", "evidence": "<short quote from the reasoning>"}'
)
# Paraphrases of the default template: the same information, conventions and answer format, worded differently.
TEMPLATES = {
    "v1": DEFAULT_TEMPLATE,
    "v2": ("Below are a clinical calculation question, the correct reference computation, and the reasoning of an "
           "assistant. Find the first step at which the reasoning departs from a correct computation.\n\n"
           "Patient note:\n{note}\n\n"
           "Question: {question}\n\n"
           "Correct reference computation:\n{reference}\n\n"
           "Assistant's reasoning:\n<<<\n{reasoning}\n>>>\n\n"
           "Possible answers:\n{categories}\n\n{rules}\n\n"
           "Support your choice with a short quote from the reasoning, then finish with a JSON object "
           '{"first_error": "<one of {choices}>", "evidence": "<short quote from the reasoning>"}'),
    "v3": ("Note:\n{note}\n\nQuestion: {question}\n\nReference (correct):\n{reference}\n\n"
           "Reasoning:\n<<<\n{reasoning}\n>>>\n\n"
           "Which step of the reasoning is the first one that is wrong?\n{categories}\n\n{rules}\n\n"
           'End with {"first_error": "<one of {choices}>", "evidence": "<short quote from the reasoning>"}'),
}


def _choices(steps: Iterable[str]) -> list[str]:
    return ["none", *steps, "other"]


def reference_text(example: Example | dict[str, Any], steps: Iterable[str] = DEFAULT_STEPS,
                   digits: int = DEFAULT_DIGITS) -> str:
    """The registry's computation for an example, one block per step, as shown to the judge.

    >>> print(reference_text(mk.data.demo()[1]))
    Values in the note:
    - weight: 70 kg
    - height: 175 cm
    Values in the units of the formula:
    - weight = 70 (body weight (kg))
    - height = 175 (height (cm))
    Formula (branch for this patient): bmi = weight / (height / 100)^2
    Substituted expression: 70 / (175 / 100)^2
    Result: 22.86
    """
    ex = as_example(example)
    if ex.calculator_id not in CALCULATORS:
        raise ValueError(f"calculator {ex.calculator_id} is not in the registry: no reference computation")
    steps = set(steps)
    formula, values, d = branch_formula(ex, digits)
    lines = []
    if "extraction" in steps:
        lines.append("Values in the note:")
        for k, v in ex.entities.items():
            shown = " ".join(fmt(x, digits) if isinstance(x, (int, float)) and not isinstance(x, bool) else str(x)
                             for x in v) if isinstance(v, list) else str(v)
            lines.append(f"- {k}: {shown}")
    if "conversion" in steps:
        lines.append("Values in the units of the formula:")
        lines += [f"- {k} = {fmt(v, digits)} ({symbol_doc(k, ex.entities)})" for k, v in d.inputs.items()]
    if "formula" in steps:
        branch = f" [{', '.join(d.branches)}]" if d.branches else ""
        lines.append(f"Formula (branch for this patient{branch}): {d.steps[-1].name} = {expr.to_str(formula)}")
    if "substitution" in steps:
        lines.append(f"Substituted expression: {expr.to_str(expr.substitute(formula, values))}")
    if "arithmetic" in steps:
        lines.append(f"Result: {fmt(d.answer, 4)}")
    return "\n".join(lines)


def _record_key(record: Mapping[str, Any]) -> str:
    """Identifies the judged answer (item, model, text, metadata) without showing any of it to the judge."""
    payload = json.dumps([record.get("item_id"), record.get("model_id"), record.get("text"),
                          {k: v for k, v in record.items() if k.startswith("meta")}], sort_keys=True, default=str)
    return hashlib.sha1(payload.encode()).hexdigest()[:10]


def build(item_e2e: Item | pd.Series, record: Mapping[str, Any] | pd.Series, *, example: Example | dict[str, Any],
          template: str = "v1", steps: Iterable[str] = DEFAULT_STEPS, max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS,
          system_prompt: str | None = DEFAULT_SYSTEM_PROMPT, digits: int = DEFAULT_DIGITS) -> Item:
    """The judge item for one answer (`record`, with its `text`) to an E2E item.

    example: the Example of the item (E2E items do not carry the patient's annotated values, which the reference
    needs); template: prompt text with placeholders {note}, {question}, {reference}, {reasoning}, {categories},
    {choices}, or the name of a variant of TEMPLATES; steps: the steps the judge can name (the answer is one of
    "none", these steps, or "other"). The prompt holds no field of the record but its text: the judge is blind to
    the condition. The item records template and template_hash, and keeps which answer it judges in its reference.

    >>> ex = mk.data.demo()[1]
    >>> item = build(mk.probes.end_to_end.build(ex), {"item_id": "demo:6:1:E2E", "text": "BMI = 70/1.75 = 40"},
    ...              example=ex)
    >>> item["probe"], item["reference"]["choices"]
    ('judge', ['none', 'extraction', 'conversion', 'formula', 'substitution', 'arithmetic', 'other'])
    """
    item_e2e = as_item(item_e2e)
    record = dict(record)
    if item_e2e.get("task", item_e2e["probe"]) != "E2E":
        raise ValueError(f"the judge reads end-to-end answers, not {item_e2e['probe']} items")
    if record.get("item_id", item_e2e["item_id"]) != item_e2e["item_id"]:
        raise ValueError(f"record of {record.get('item_id')} does not answer {item_e2e['item_id']}")
    ex = as_example(example)
    steps = tuple(steps)
    choices = _choices(steps)
    categories = "\n".join(['- "none": every step is correct'] +
                           [f'- "{s}": {STEP_DESCRIPTIONS.get(s, s)}' for s in steps] +
                           ['- "other": an error that fits none of these steps'])
    name, text = resolve_template(template, TEMPLATES)
    user = render(text, note=ex.note, question=ex.question, reference=reference_text(ex, steps, digits),
                  reasoning=record.get("text") or "", categories=categories, rules=JUDGING_RULES,
                  choices=", ".join(f'"{c}"' for c in choices))
    key = _record_key(record)
    item = make_item(ex, "judge", user, {"judged_item_id": item_e2e["item_id"], "judged_record": key,
                                         "choices": choices}, max_new_tokens, system_prompt, task="judge",
                     template=(name, text))
    item["item_id"] = f"{item_e2e['item_id']}:judge:{key}"
    return item


def parse(text: str, item: Item | None = None, steps: Iterable[str] = DEFAULT_STEPS) -> dict[str, Any]:
    """Read a judge's answer: {"format_valid", "first_error", "evidence"}. An unreadable answer, or a first_error
    outside the allowed choices (those of `item`, else "none", `steps`, "other"), gives first_error None.

    >>> parse('{"first_error": "formula", "evidence": "uses actual weight"}')["first_error"]
    'formula'
    >>> parse('{"first_error": "spelling"}'), parse("I think the formula is wrong.")["format_valid"]
    ({'format_valid': False, 'first_error': None, 'evidence': None}, False)
    """
    choices = item["reference"]["choices"] if item is not None else _choices(steps)
    obj = extract_json(text, lenient=True)                  # judges quote reasoning, often with LaTeX backslashes
    value = obj.get("first_error") if isinstance(obj, dict) else None
    value = value.strip().lower() if isinstance(value, str) else None
    if value not in choices:
        return {"format_valid": False, "first_error": None, "evidence": None}
    evidence = obj.get("evidence")
    return {"format_valid": True, "first_error": value, "evidence": evidence if isinstance(evidence, str) else None}


def annotate(items: pd.DataFrame | Iterable[Item], records: pd.DataFrame | Iterable[Mapping[str, Any]] | str | Path,
             judge_model: Any, *, dataset: MedCalcDataset | Iterable[Example], out_path: str | Path,
             template: str = "v1", steps: Iterable[str] = DEFAULT_STEPS, batch_size: int = 1,
             model_id: str | None = None, max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS) -> pd.DataFrame:
    """Have a judge annotate the E2E answers of `records`: one row per judged answer, with first_error and
    evidence. Answers to items of calculators outside the registry, to other probes, or with an error are skipped.

    judge_model: whatever run_items accepts (HFBackend, a function messages -> text, an API client wrapper);
    dataset: the examples of the items; out_path: the judge's generations (resumable, like run_items);
    max_new_tokens: the judge's token budget (raise it for a judge that reasons at length, e.g. Qwen3's thinking).
    Each row records judge_model_id, template and template_hash, the judged item and the evaluated model_id.

    >>> import tempfile, pathlib
    >>> ds = mk.data.demo()
    >>> items = mk.ProbeSuite(["E2E"]).build(ds)
    >>> records = [{"item_id": i, "model_id": "m", "text": '{"answer": 1}'} for i in items.item_id]
    >>> def toy_judge(messages, max_new_tokens):
    ...     return '{"first_error": "formula", "evidence": "answer 1"}'
    >>> out = pathlib.Path(tempfile.mkdtemp()) / "judge.jsonl"
    >>> notes = annotate(items, records, toy_judge, dataset=ds, out_path=out)
    >>> notes[["judged_item_id", "model_id", "first_error", "judge_model_id"]].head(2)
      judged_item_id model_id first_error judge_model_id
    0   demo:2:1:E2E        m     formula      toy_judge
    1   demo:6:1:E2E        m     formula      toy_judge
    """
    by_id = {it["item_id"]: it for it in as_items(items)}
    examples = {ex.example_id: ex for ex in (dataset if not isinstance(dataset, pd.DataFrame) else
                                             MedCalcDataset(dataset))}
    if isinstance(records, (str, Path)):
        records = read_records(records)
    judge_items, judged = [], {}
    for rec in as_items(records):
        item = by_id.get(rec.get("item_id"))
        if item is None or rec.get("error") or item.get("task", item["probe"]) != "E2E" \
                or item["calculator_id"] not in CALCULATORS:
            continue
        jitem = build(item, rec, example=examples[item["example_id"]], template=template, steps=steps,
                      max_new_tokens=max_new_tokens)
        if jitem["item_id"] not in judged:
            judge_items.append(jitem)
            judged[jitem["item_id"]] = rec
    judge_id = model_id or model_name(judge_model)
    run_items(judge_items, out_path, judge_model, model_id=judge_id, batch_size=batch_size)
    answers = {r["item_id"]: r for r in as_items(read_records(out_path)) if not r.get("error")}
    rows = []
    for jitem in judge_items:
        answer = answers.get(jitem["item_id"])
        if answer is None:
            continue
        rec = judged[jitem["item_id"]]
        rows.append({"judge_item_id": jitem["item_id"], "judged_item_id": jitem["reference"]["judged_item_id"],
                     "example_id": jitem["example_id"], "calculator_id": jitem["calculator_id"],
                     "model_id": rec.get("model_id"), **parse(answer.get("text") or "", jitem),
                     "judge_model_id": answer.get("model_id"), "template": jitem["template"],
                     "template_hash": jitem["template_hash"], "judge_text": answer.get("text")})
    return pd.DataFrame(rows)


def agreement(annotations: pd.DataFrame | Iterable[str | None], human_labels: Mapping[str, str] | pd.Series |
              pd.DataFrame | Iterable[str], *, key: str = "judge_item_id") -> dict[str, Any]:
    """Agreement between the judge and human labels of first_error: raw agreement, Cohen's kappa, and the confusion
    matrix (rows: human, columns: judge). Pairs where the judge's answer was unreadable are counted apart
    (`n_unreadable`) and left out.

    annotations: the DataFrame of annotate (matched to human_labels on `key`: a dict / Series indexed by it, or a
    DataFrame with `key` and `first_error` columns), or a plain sequence of labels aligned with human_labels.

    >>> judge_labels = ["formula", "formula", "arithmetic", "arithmetic"]
    >>> r = agreement(judge_labels, ["formula", "arithmetic", "arithmetic", "arithmetic"])
    >>> r["n"], r["agreement"], r["kappa"]
    (4, 0.75, 0.5)
    >>> r["confusion"]
    judge       arithmetic  formula
    human
    arithmetic           2        1
    formula              0        1
    """
    if isinstance(annotations, pd.DataFrame):
        if isinstance(human_labels, pd.DataFrame):
            human_labels = human_labels.set_index(key)["first_error"]
        human = dict(human_labels)
        pairs = [(human[k], j) for k, j in zip(annotations[key], annotations["first_error"]) if k in human]
    else:
        judge, human = list(annotations), list(human_labels)
        if len(judge) != len(human):
            raise ValueError("annotations and human_labels must have the same length")
        pairs = list(zip(human, judge))
    n_unreadable = sum(j is None or j != j for _, j in pairs)
    pairs = [(h, j) for h, j in pairs if j is not None and j == j]
    if not pairs:
        raise ValueError("no pair of labels to compare")
    df = pd.DataFrame(pairs, columns=["human", "judge"])
    po = float((df.human == df.judge).mean())
    ph, pj = df.human.value_counts(normalize=True), df.judge.value_counts(normalize=True)
    pe = float(sum(ph.get(c, 0.0) * pj.get(c, 0.0) for c in set(ph.index) | set(pj.index)))
    kappa = 1.0 if pe == 1 else (po - pe) / (1 - pe)
    confusion = pd.crosstab(df.human, df.judge)
    return {"n": len(df), "n_unreadable": n_unreadable, "agreement": po, "kappa": round(kappa, 12),
            "confusion": confusion}
