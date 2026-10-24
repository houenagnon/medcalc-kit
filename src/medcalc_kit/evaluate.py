"""Score model answers and summarise them per probe.

    >>> from medcalc_kit import evaluate, probes
    >>> items = mk.ProbeSuite(["A", "E2E"]).build(mk.data.demo())
    >>> answers = pd.DataFrame({"item_id": items.item_id,                  # any answers you collected
    ...                         "text": [probes.reference_answer(it) for _, it in items.iterrows()]})
    >>> answers.loc[0, "text"] = '{"result": 1}'                           # one wrong answer
    >>> df = evaluate.score_records(answers, items)                       # one row per answer
    >>> df[["item_id", "category", "correct"]].head(3)
           item_id     category  correct
    0   demo:2:1:A  well_formed    False
    1   demo:6:1:A  well_formed     True
    2  demo:39:1:A  well_formed     True
    >>> df.loc[0, "error_type"]
    'arithmetic_error'
    >>> evaluate.summary(df)
           n_units  well_formed  competence  overall
    probe
    A          4.0          1.0        0.75     0.75
    E2E        4.0          1.0        1.00     1.00
"""
from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pandas as pd

from medcalc_kit.generation.artifacts import classify_generation
from medcalc_kit.generation.runner import prompt_key, read_records
from medcalc_kit.probes import as_items, score

# Condition columns kept by default when collapsing items into analysis units.
DEFAULT_KEYS = ("model", "method", "sparsity", "seed")


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    """Records as a list of dicts (generation.read_records gives a DataFrame)."""
    return [json.loads(line) for line in open(path)]


def score_records(records: pd.DataFrame | Iterable[dict[str, Any]] | str | Path,
                  items: pd.DataFrame | Iterable[dict[str, Any]] | dict[str, Any],
                  condition: dict[str, Any] | None = None, scoring: dict[str, dict[str, Any]] | None = None,
                  artifacts: dict[str, Any] | None = None, details: bool = False) -> pd.DataFrame:
    """Score model answers: one row per answer, with its artifact category, correctness (only well-formed answers
    can be correct) and error type (for an empty, truncated or looping answer: that category).

    records:    the answers: the output file of `run_items` (path), its DataFrame (`read_records`), or any
                DataFrame / list of dicts with at least `item_id` and `text`. `n_new_tokens` (to detect truncated
                answers) and `error` are used when present; records with an error are skipped. A record's own
                `max_new_tokens` (set by truncate_records) replaces the item's budget.
    items:      the items answered (DataFrame, list or {item_id: item}).
    condition:  constant columns to add, e.g. {"model": "qwen2.5-7b"} to compare models later.
    scoring:    score() options per probe label or task, e.g. {"K": {"case_semantics": "first_match"}}.
    artifacts:  options of generation.is_degenerate (ngram, repeat_share, line_repeats, min_words).
    details:    also return the answer `text` and the full `verdict` dict (e.g. per-field results for E).

    >>> items = mk.ProbeSuite(["A"]).build(mk.data.demo())
    >>> recs = [{"item_id": "demo:6:1:A", "text": '{"result": 22.857}', "n_new_tokens": 12},
    ...         {"item_id": "demo:2:1:A", "text": "", "n_new_tokens": 0}]
    >>> score_records(recs, items, condition={"model": "m1"})[["model", "item_id", "category", "correct"]]
      model     item_id     category  correct
    0    m1  demo:6:1:A  well_formed     True
    1    m1  demo:2:1:A        empty    False
    >>> score_records(recs, items, details=True).loc[0, "verdict"]["rel_error"] < 1e-4
    True
    """
    if isinstance(records, (str, Path)):
        records = read_records(records)
    records = as_items(records)
    by_id = items if isinstance(items, dict) else {it["item_id"]: it for it in as_items(items)}
    rows = []
    for rec in records:
        item = by_id.get(rec["item_id"])
        if item is None or rec.get("error"):
            continue
        task = item.get("task", item["probe"])
        opts = (scoring or {}).get(item["probe"], (scoring or {}).get(task, {}))
        text = rec.get("text") or ""
        s = score(item, text, **opts)
        n_new = rec.get("n_new_tokens", 0)
        budget = rec.get("max_new_tokens") or item["max_new_tokens"]
        cat = classify_generation(text, n_new, budget, s["format_valid"], **(artifacts or {}))
        row = {**(condition or {}), "item_id": rec["item_id"], "example_id": item["example_id"],
               "calculator_id": item["calculator_id"], "probe": item["probe"], "task": task,
               "template": item.get("template"),
               "prompt_key": rec.get("prompt_key") or prompt_key(item["messages"], item["max_new_tokens"]),
               "category": cat, "well_formed": cat == "well_formed",
               "correct": bool(s["correct"]) and cat == "well_formed",
               # an unusable answer (empty, truncated, looping) is reported as such, whatever the probe found in it
               "error_type": cat if cat in ("empty", "truncated", "degenerate") else s.get("error_type"),
               "n_new_tokens": n_new, "seconds": rec.get("seconds", 0.0)}
        if details:
            row.update(text=text, verdict=s)
        rows.append(row)
    return pd.DataFrame(rows)


def _call(fn, *args, **kwargs):
    """fn(*args, **kwargs), or fn(*args) for tokenizers that take no such keyword."""
    try:
        return fn(*args, **kwargs)
    except TypeError:
        return fn(*args)


def truncate_records(records: pd.DataFrame | Iterable[dict[str, Any]] | str | Path,
                     items: pd.DataFrame | Iterable[dict[str, Any]] | dict[str, Any],
                     budgets: dict[str, int], tokenizer: Any) -> pd.DataFrame:
    """Simulate a smaller token budget without generating again: every answer of a probe in `budgets` (label, or
    task) is cut to that many tokens; `text` and `n_new_tokens` are updated and the record gets the new
    `max_new_tokens`, so that score_records classifies a cut answer as truncated. Shorter answers are unchanged.
    Valid for greedy decoding, where the first tokens of an answer do not depend on the budget.

    tokenizer: a Hugging Face tokenizer, or any object with encode(text) -> ids and decode(ids) -> text.

    >>> class Words:                                            # a toy tokenizer: one token per word
    ...     def encode(self, text): return text.split()
    ...     def decode(self, ids): return " ".join(ids)
    >>> items = mk.ProbeSuite(["A"]).build(mk.data.demo())
    >>> recs = [{"item_id": "demo:39:1:A", "text": "step " * 300 + '{"result": 12}', "n_new_tokens": 302},
    ...         {"item_id": "demo:6:1:A", "text": '{"result": 22.857}', "n_new_tokens": 2}]
    >>> cut = truncate_records(recs, items, {"A": 150}, Words())
    >>> cut[["item_id", "n_new_tokens", "max_new_tokens"]]
           item_id  n_new_tokens  max_new_tokens
    0  demo:39:1:A           150             150
    1   demo:6:1:A             2             150
    >>> score_records(cut, items)[["item_id", "category", "correct"]]
           item_id     category  correct
    0  demo:39:1:A    truncated    False
    1   demo:6:1:A  well_formed     True
    """
    if isinstance(records, (str, Path)):
        records = read_records(records)
    by_id = items if isinstance(items, dict) else {it["item_id"]: it for it in as_items(items)}
    rows = []
    for rec in as_items(records):
        rec = dict(rec)
        item = by_id.get(rec["item_id"])
        if item is not None:
            budget = budgets.get(item["probe"], budgets.get(item.get("task", item["probe"])))
            if budget is not None:
                if budget > item["max_new_tokens"]:
                    raise ValueError(f"budget {budget} for {item['probe']} exceeds the generation budget "
                                     f"{item['max_new_tokens']}: a larger budget cannot be simulated")
                text = rec.get("text") or ""
                ids = list(_call(tokenizer.encode, text, add_special_tokens=False))
                n = rec.get("n_new_tokens") or len(ids)
                if n > budget:
                    rec["text"] = _call(tokenizer.decode, ids[:budget], skip_special_tokens=True)
                    rec["n_new_tokens"] = budget
                    rec["truncated"] = True
                rec["max_new_tokens"] = budget
        rows.append(rec)
    return pd.DataFrame(rows)


def to_units(df: pd.DataFrame, keys: Iterable[str] = DEFAULT_KEYS, collapse: Iterable[str] = ("K",)) -> pd.DataFrame:
    """One row per analysis unit. Items of the `collapse` tasks that share a prompt collapse to that prompt (mean
    correctness): identical prompts get identical greedy answers, so they are one observation (K in "general"
    mode repeats its prompt across the examples of a calculator). Every other item is one unit.
    keys: condition columns kept (those present), so that conditions are never mixed.

    >>> df = pd.DataFrame({"probe": ["K", "K", "A"], "calculator_id": "6", "example_id": ["a", "b", "a"],
    ...                    "prompt_key": ["p", "p", "q"], "correct": [True, True, False],
    ...                    "well_formed": True, "category": "well_formed"})
    >>> to_units(df)[["probe", "unit", "correct"]]
      probe unit  correct
    0     A    a      0.0
    1     K    p      1.0
    """
    keys = [c for c in keys if c in df.columns]
    task = df["task"] if "task" in df.columns else df["probe"]
    is_k = task.isin(list(collapse))
    k = df[is_k]
    other = df[~is_k].assign(unit=lambda d: d.example_id)
    if len(k):
        k = (k.groupby(keys + ["probe", "calculator_id", "prompt_key"], as_index=False)
             .agg(correct=("correct", "mean"), well_formed=("well_formed", "mean"), category=("category", "first"))
             .assign(unit=lambda d: d.prompt_key))
    out = pd.concat([other, k], ignore_index=True)
    return out.astype({"correct": float, "well_formed": float})


def summary(df: pd.DataFrame, by: Iterable[str] = ("probe",), collapse: Iterable[str] = ("K",)) -> pd.DataFrame:
    """Per group (default: per probe): number of units, share of well-formed answers, accuracy among well-formed
    answers ('competence') and overall accuracy. Tasks in `collapse` are counted once per distinct prompt
    (see to_units). Group by condition columns to compare, e.g. by=("model", "probe").

    >>> df = pd.DataFrame({"model": ["m1", "m1", "m2", "m2"], "probe": "A", "example_id": ["a", "b", "a", "b"],
    ...                    "calculator_id": "6", "prompt_key": ["p", "q", "p", "q"],
    ...                    "correct": [True, False, True, True], "well_formed": [True, False, True, True],
    ...                    "category": "well_formed"})
    >>> summary(df, by=("model", "probe"))
                 n_units  well_formed  competence  overall
    model probe
    m1    A          2.0          0.5         1.0      0.5
    m2    A          2.0          1.0         1.0      1.0
    """
    by = list(by)
    units = to_units(df, keys=list(dict.fromkeys([*DEFAULT_KEYS, *by])), collapse=collapse)
    return (units.groupby(by)
            .apply(lambda g: pd.Series({
                "n_units": len(g),
                "well_formed": g.well_formed.mean(),
                "competence": g[g.well_formed > 0].correct.mean(),
                "overall": g.correct.mean()}), include_groups=False))
