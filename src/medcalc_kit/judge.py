"""LLM evaluation: an LLM judge grades the answers, next to the automatic (deterministic) evaluation.

For every answer, to any probe (E, U, K, S, A, E2E), the judge reads the task as the model received it, the
reference answer from the registry, and the probe's grading rule, and says whether the answer is correct. For E2E it
checks the final answer against the ground truth (within the benchmark's interval), like the automatic scoring.

The automatic evaluation stays the reference: `compare` measures, per probe, how often the judge agrees with it
(agreement, Cohen's kappa, false acceptances and rejections), which tells how far the judge can be trusted, without
human labels. The judge is blind (its prompt holds nothing about the model evaluated) and deterministic with greedy
decoding, one prompt at a time (`batch_size=1`) and HFBackend(..., deterministic=True).

    >>> items = mk.ProbeSuite(["A"]).build(mk.data.demo())
    >>> item = mk.probes.as_item(items.iloc[2])                 # anion gap: 140 - (104 + 24)
    >>> judge_item = build(item, {"item_id": item["item_id"], "model_id": "model-A", "text": '{"result": 12}'})
    >>> "model-A" in judge_item["messages"][-1]["content"]
    False
    >>> parse('The value matches. {"verdict": "correct", "reason": "12 equals the reference"}')
    {'format_valid': True, 'judge_correct': True, 'reason': '12 equals the reference'}
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import pandas as pd

from medcalc_kit.generation.runner import model_name, prompt_key, read_records, run_items
from medcalc_kit.parsing import extract_json
from medcalc_kit.probes import reference_answer
from medcalc_kit.probes.common import Item, as_item, as_items, render, resolve_template, template_hash

DEFAULT_MAX_NEW_TOKENS = 512
DEFAULT_SYSTEM_PROMPT = "You are a meticulous grader of clinical calculations."

# The grading rule of each probe, as the judge reads it (the same rules as the automatic scoring).
# Every rule grades the content of the final answer: answer format is measured apart (well_formed), so a small slip
# (a misplaced quote or brace) must not decide the verdict.
FORMAT_NOTE = (" Grade the content of the final answer; a small format slip (a misplaced quote or brace) does not "
               "matter.")
CRITERIA = {
    "E": ("Correct only if every field has the reference value: numbers may be given in another unit that converts to "
          "the reference value (1 % tolerance), and may be written as text (\"7.25\" or \"7.25 mg\"); a drug may be "
          "named without its route (IV, PO); a field absent from the reference must be reported as not mentioned "
          "(null or false)."),
    "U": "Correct if the converted value is within the accepted range of the reference, in the requested unit.",
    "K": ("Correct if the formula, written with the variable names, gives the reference formula's value for this "
          "patient and is mathematically equivalent to it (rearranged terms, other notation, or unit conversions "
          "written inside the formula are fine). A number instead of a formula is incorrect."),
    "S": ("Correct if the answer is the given formula with each variable replaced by its value and nothing computed or "
          "simplified; the order of terms may differ. A partly computed expression is incorrect."),
    "A": "Correct if the result is within the accepted range of the reference.",
    "E2E": ("Correct if the final answer is within the reference interval (for a date or a duration: exactly the "
            "reference). Only the final answer is graded, not the reasoning."),
}

# Placeholders: {task} (the task as the model received it), {reference}, {criterion}, {answer}.
DEFAULT_TEMPLATE = (
    "You grade the answer of an assistant to a clinical calculation task, against the reference answer.\n\n"
    "Task given to the assistant:\n<<<\n{task}\n>>>\n\n"
    "Reference answer: {reference}\n\n"
    "Grading rule: {criterion}\n\n"
    "Assistant's answer:\n<<<\n{answer}\n>>>\n\n"
    "Decide whether the assistant's final answer is correct according to the grading rule. End your answer with a "
    'JSON object of the form {"verdict": "correct" or "incorrect", "reason": "<one short sentence, plain text>"}'
)
# Paraphrases of the default template: the same information, conventions and answer format, worded differently.
TEMPLATES = {
    "v1": DEFAULT_TEMPLATE,
    "v2": ("Below are a clinical calculation task, its reference answer, a grading rule and an assistant's answer. "
           "Grade the assistant's final answer.\n\n"
           "Task:\n<<<\n{task}\n>>>\n\n"
           "Reference answer: {reference}\n\n"
           "Rule: {criterion}\n\n"
           "Answer to grade:\n<<<\n{answer}\n>>>\n\n"
           'Finish with a JSON object {"verdict": "correct" or "incorrect", "reason": "<one short sentence, plain '
           'text>"}'),
    "v3": ("Task:\n<<<\n{task}\n>>>\nReference: {reference}\nRule: {criterion}\nAnswer:\n<<<\n{answer}\n>>>\n\n"
           'Is the final answer correct? End with {"verdict": "correct" or "incorrect", "reason": "<one short '
           'sentence, plain text>"}'),
}


def reference_text(item: Item | pd.Series) -> str:
    """The reference answer of an item, as the judge reads it.

    >>> ds = mk.data.demo()
    >>> reference_text(mk.probes.arithmetic.build(ds[2])), reference_text(mk.probes.end_to_end.build(ds[2]))
    ('12 (accepted range: 11.88 to 12.12)', '12 (accepted interval: 11.4 to 12.6)')
    >>> reference_text(mk.probes.knowledge.build(ds[1], mode="patient"))
    'bmi = weight / (height / 100)^2'
    """
    item = as_item(item)
    task, ref = item.get("task", item["probe"]), item["reference"]
    if task == "E2E":
        if ref.get("answer_type", "number") != "number":
            return str(ref["ground_truth"])
        return f"{ref['ground_truth']:.6g} (accepted interval: {ref['lower']:.6g} to {ref['upper']:.6g})"
    if task in ("A", "U"):
        # the accepted range is given, so the judge compares numbers instead of computing a percentage
        from medcalc_kit.probes import arithmetic, conversion

        tol = arithmetic.DEFAULT_REL_TOL if task == "A" else conversion.DEFAULT_REL_TOL
        gold = ref["gold_value"]
        lo, hi = sorted((gold * (1 - tol), gold * (1 + tol)))
        unit = f" {ref['target_unit']}" if task == "U" else ""
        return f"{gold:.6g}{unit} (accepted range: {lo:.6g} to {hi:.6g})"
    if task == "S":
        return ref["gold_expression"]
    if task == "K":
        answer = json.loads(reference_answer(item))
        formula = answer.get("formula") or answer["cases"][0]["formula"]
        note = "" if ref.get("mode") == "patient" else " (the formula of this patient's case; other cases may follow)"
        return f"{_target(item)}{formula}{note}"
    return reference_answer(item)                                   # E: every field in the expected format


def _target(item: Item) -> str:
    from medcalc_kit.calculators import derive

    d = derive(item["calculator_id"], item["reference"]["entities"])
    return f"{d.steps[-1].name} = "


def _record_key(record: Mapping[str, Any]) -> str:
    """Identifies the graded answer (item, model, text, metadata) without showing any of it to the judge."""
    payload = json.dumps([record.get("item_id"), record.get("model_id"), record.get("text"),
                          {k: v for k, v in record.items() if k.startswith("meta")}], sort_keys=True, default=str)
    return hashlib.sha1(payload.encode()).hexdigest()[:10]


def build(item: Item | pd.Series, record: Mapping[str, Any] | pd.Series, *, template: str = "v1",
          max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS, system_prompt: str | None = DEFAULT_SYSTEM_PROMPT) -> Item:
    """The judge item for one answer (`record`, with its `text`) to an item of any probe.

    template: prompt text with placeholders {task}, {reference}, {criterion}, {answer}, or the name of a variant of
    TEMPLATES. The prompt holds the task, the reference, the grading rule of the probe (CRITERIA) and the answer:
    nothing about the model or the condition evaluated. The id ends with the key of the full prompt (template, rules,
    reference, answer and budget), so that a resumed run never reuses a verdict given to a different prompt.

    >>> item = mk.probes.end_to_end.build(mk.data.demo()[1])
    >>> j = build(item, {"item_id": item["item_id"], "text": '{"answer": 22.9}'})
    >>> j["probe"], j["reference"]["graded_item_id"], j["item_id"].startswith("demo:6:1:E2E:judge:")
    ('judge', 'demo:6:1:E2E', True)
    """
    item, record = as_item(item), dict(record)
    if record.get("item_id", item["item_id"]) != item["item_id"]:
        raise ValueError(f"record of {record.get('item_id')} does not answer {item['item_id']}")
    task = item.get("task", item["probe"])
    if task not in CRITERIA:
        raise ValueError(f"no grading rule for probe {task!r}")
    name, text = resolve_template(template, TEMPLATES)
    user = render(text, task=item["messages"][-1]["content"], reference=reference_text(item),
                  criterion=CRITERIA[task] + FORMAT_NOTE, answer=record.get("text") or "")
    messages = ([{"role": "system", "content": system_prompt}] if system_prompt else []) + \
        [{"role": "user", "content": user}]
    key = template_hash(text)
    full = prompt_key(messages, max_new_tokens)                 # changes with anything the judge reads
    return {"item_id": f"{item['item_id']}:judge:{_record_key(record)}:{full}", "example_id": item["example_id"],
            "calculator_id": item["calculator_id"], "calculator_name": item.get("calculator_name", ""),
            "probe": "judge", "task": "judge", "template": name, "template_hash": key, "messages": messages,
            "max_new_tokens": max_new_tokens,
            "reference": {"graded_item_id": item["item_id"], "graded_probe": item["probe"], "graded_task": task}}


def parse(text: str) -> dict[str, Any]:
    """Read a judge's answer: {"format_valid", "judge_correct", "reason"}; an unreadable answer gives
    judge_correct None.

    >>> parse('{"verdict": "Incorrect", "reason": "13 is outside the interval"}')["judge_correct"]
    False
    >>> parse("The answer looks right.")
    {'format_valid': False, 'judge_correct': None, 'reason': None}
    """
    obj = extract_json(text, lenient=True)                  # judges quote answers, often with LaTeX backslashes
    verdict = obj.get("verdict") if isinstance(obj, dict) else None
    verdict = verdict.strip().lower() if isinstance(verdict, str) else None
    if verdict not in ("correct", "incorrect"):
        return {"format_valid": False, "judge_correct": None, "reason": None}
    reason = obj.get("reason")
    return {"format_valid": True, "judge_correct": verdict == "correct",
            "reason": reason if isinstance(reason, str) else None}


def annotate(items: pd.DataFrame | Iterable[Item], records: pd.DataFrame | Iterable[Mapping[str, Any]] | str | Path,
             judge_model: Any, *, out_path: str | Path, template: str = "v1", batch_size: int = 1,
             max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS, model_id: str | None = None) -> pd.DataFrame:
    """LLM evaluation of `records` (answers to `items`): one row per answer with the judge's verdict.

    judge_model: whatever run_items accepts (HFBackend, a function messages -> text, an API client wrapper);
    out_path: the judge's generations (resumable, like run_items); batch_size: 1 by default, so that a verdict never
    depends on the other prompts of its batch (use HFBackend(..., deterministic=True) for a fully deterministic
    judge). Each row records judge_model_id, judge_revision (the model's commit when known), template and
    template_hash. Answers with an error, or to unknown items, are skipped.

    >>> import tempfile, pathlib
    >>> items = mk.ProbeSuite(["A", "E2E"]).build(mk.data.demo())
    >>> records = [{"item_id": i, "model_id": "m", "text": '{"answer": 12, "result": 12}'} for i in items.item_id]
    >>> def toy_judge(messages, max_new_tokens):
    ...     return '{"verdict": "correct", "reason": "matches"}'
    >>> out = pathlib.Path(tempfile.mkdtemp()) / "judge.jsonl"
    >>> llm = annotate(items, records, toy_judge, out_path=out)
    >>> llm[["item_id", "probe", "judge_correct", "judge_model_id"]].head(2)
          item_id probe  judge_correct judge_model_id
    0  demo:2:1:A     A           True      toy_judge
    1  demo:6:1:A     A           True      toy_judge
    """
    by_id = {it["item_id"]: it for it in as_items(items)}
    if isinstance(records, (str, Path)):
        records = read_records(records)
    judge_items, graded = [], {}
    for rec in as_items(records):
        item = by_id.get(rec.get("item_id"))
        if item is None or rec.get("error") or item.get("task", item["probe"]) not in CRITERIA:
            continue
        jitem = build(item, rec, template=template, max_new_tokens=max_new_tokens)
        if jitem["item_id"] not in graded:
            judge_items.append(jitem)
            graded[jitem["item_id"]] = (item, rec)
    judge_id = model_id or model_name(judge_model)
    run_items(judge_items, out_path, judge_model, model_id=judge_id, batch_size=batch_size)
    answers = {r["item_id"]: r for r in as_items(read_records(out_path)) if not r.get("error")}
    rows = []
    for jitem in judge_items:
        answer = answers.get(jitem["item_id"])
        if answer is None:
            continue
        item, rec = graded[jitem["item_id"]]
        rows.append({"item_id": item["item_id"], "probe": item["probe"], "task": item.get("task", item["probe"]),
                     "example_id": item["example_id"], "calculator_id": item["calculator_id"],
                     "model_id": rec.get("model_id"), **parse(answer.get("text") or ""),
                     "judge_model_id": answer.get("model_id"), "judge_revision": getattr(judge_model, "revision", None),
                     "template": jitem["template"], "template_hash": jitem["template_hash"],
                     "judge_item_id": jitem["item_id"], "judge_text": answer.get("text")})
    return pd.DataFrame(rows)


def agreement(labels_a: Iterable[Any], labels_b: Iterable[Any]) -> dict[str, Any]:
    """Agreement between two aligned sequences of labels: n, raw agreement, Cohen's kappa, confusion matrix (rows: a,
    columns: b). Pairs with a missing label are left out (`n_missing`).

    >>> r = agreement(["x", "x", "y", "y"], ["x", "y", "y", "y"])
    >>> r["n"], r["agreement"], r["kappa"]
    (4, 0.75, 0.5)
    """
    a, b = list(labels_a), list(labels_b)
    if len(a) != len(b):
        raise ValueError("the two sequences of labels must have the same length")
    pairs = [(x, y) for x, y in zip(a, b) if x is not None and y is not None and x == x and y == y]
    if not pairs:
        raise ValueError("no pair of labels to compare")
    df = pd.DataFrame(pairs, columns=["a", "b"])
    po = float((df.a == df.b).mean())
    pa, pb = df.a.value_counts(normalize=True), df.b.value_counts(normalize=True)
    pe = float(sum(pa.get(c, 0.0) * pb.get(c, 0.0) for c in set(pa.index) | set(pb.index)))
    kappa = 1.0 if pe == 1 else (po - pe) / (1 - pe)
    return {"n": len(df), "n_missing": len(a) - len(df), "agreement": po, "kappa": round(kappa, 12),
            "confusion": pd.crosstab(df.a, df.b)}


def compare(llm: pd.DataFrame, scores: pd.DataFrame, by: str = "task") -> pd.DataFrame:
    """LLM evaluation against the automatic one, per probe (`by`: "task" or "probe") and overall: n, accuracy given
    by each, agreement, Cohen's kappa, and the judge's errors: accepted while wrong (false acceptance rate, among the
    answers the automatic scoring rejects) and rejected while right (false rejection rate, among those it accepts).
    With a `well_formed` column in scores, agreement_well_formed and kappa_well_formed compare the two on the
    answers in the expected format only: the content, apart from format failures (which only the automatic
    evaluation counts).

    llm: the output of annotate; scores: score_records on the same answers (same item_id).

    >>> scores = pd.DataFrame({"item_id": ["a", "b", "c", "d"], "task": "A", "correct": [True, True, False, False]})
    >>> llm = pd.DataFrame({"item_id": ["a", "b", "c", "d"], "judge_correct": [True, False, False, False]})
    >>> row = compare(llm, scores).loc["A"]
    >>> row[["auto_accuracy", "llm_accuracy", "agreement", "kappa", "false_rejection"]].tolist()
    [0.5, 0.25, 0.75, 0.5, 0.5]
    """
    cols = ["item_id", "correct", by] + (["well_formed"] if "well_formed" in scores else [])
    merged = llm[["item_id", "judge_correct"]].merge(scores[cols], on="item_id")
    rows = {}
    groups = [(g, d) for g, d in merged.groupby(by, sort=False)] + [("all", merged)]
    for name, d in groups:
        read = d.dropna(subset=["judge_correct"])
        auto, judge = read.correct.astype(bool), read.judge_correct.astype(bool)
        r = agreement(list(auto), list(judge)) if len(read) else {"agreement": float("nan"), "kappa": float("nan")}
        rows[name] = {"n": len(d), "unreadable": len(d) - len(read), "auto_accuracy": float(d.correct.mean()),
                      "llm_accuracy": float(judge.mean()) if len(read) else float("nan"),
                      "agreement": r["agreement"], "kappa": r["kappa"],
                      "false_acceptance": float(judge[~auto].mean()) if (~auto).any() else float("nan"),
                      "false_rejection": float((~judge[auto]).mean()) if auto.any() else float("nan")}
        if "well_formed" in read:
            wf = read[read.well_formed.astype(bool)]
            r = agreement(list(wf.correct.astype(bool)), list(wf.judge_correct.astype(bool))) if len(wf) else \
                {"agreement": float("nan"), "kappa": float("nan")}
            rows[name].update(n_well_formed=len(wf), agreement_well_formed=r["agreement"],
                              kappa_well_formed=r["kappa"])
    out = pd.DataFrame.from_dict(rows, orient="index")
    out.index.name = by
    return out.astype({"n": int, "unreadable": int})
