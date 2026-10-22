"""K — Knowledge: does the model know the calculator's formula?

Two modes:
- "general" (default): the model sees the question, the fixed categorical characteristics (sex, drugs...) and
  the variables with their units, but NOT the patient's values. It writes the general formula, one case per
  branch: {"cases": [{"condition": "<condition, or always>", "formula": "<expression>"}]}
- "patient": the model also sees the patient's values and writes the formula that applies to THIS patient,
  as an expression of the variables: {"formula": "<expression>"}. Only the relevant branch is needed, so the
  probe measures recall of the formula rather than the writing of a complete piecewise function.

Scoring: the model's formula is evaluated (safe parser, never eval) at the patient's point and at up to
`n_points` other patients — real patients of the same calculator when a pool is given at build time
(restricted to the patient's branch in "patient" mode), otherwise perturbations of the patient — and compared
with the registry. It is correct only if it is right at every point. Symbolic comparison is avoided on purpose:
branches, rounded constants and equivalent rewritings make it fragile.

In "general" mode the prompt depends on the patient only through categorical fields, so many examples share
the same prompt: count each distinct prompt once in statistics (generation.prompt_key, evaluate.to_units).

Error types: format_invalid, unparsable_formula, unknown_variable (a name not in the listed variables),
wrong_at_patient_point, wrong_elsewhere (right for this patient only: wrong branch or wrong constant).

    >>> item = build(mk.data.demo()[2])                         # anion gap, variables na, cl, hco3
    >>> score(item, '{"cases": [{"condition": "always", "formula": "na - cl - hco3"}]}')["correct"]
    True
    >>> score(item, '{"cases": [{"condition": "always", "formula": "na + 4 - cl - hco3"}]}')["error_type"]
    'wrong_at_patient_point'
"""
from __future__ import annotations

import json
import math
import random
import zlib
from typing import Any

from medcalc_kit import expr
from medcalc_kit.calculators import derive
from medcalc_kit.data import PLAUSIBLE_RANGES, Example, as_example
from medcalc_kit.parsing import extract_json
from medcalc_kit.probes.base import Probe
from medcalc_kit.probes.common import (
    DEFAULT_DIGITS,
    DEFAULT_SYSTEM_PROMPT,
    Item,
    categorical_context,
    fmt,
    inline,
    make_item,
    rel_close,
    render,
    symbol_doc,
    task_question,
)

DEFAULT_MAX_NEW_TOKENS = 1024
DEFAULT_N_POINTS = 50
DEFAULT_REL_TOL = 0.01
# Per-calculator absolute tolerance replacing the relative one (MELD Na: integer score with nested rounding).
DEFAULT_ABS_TOL = {"23": 1.0}
DEFAULT_PERTURBATION_FACTOR = 3.0
# Drug-specific structure: test points are perturbations of the patient itself, never other patients.
PERTURB_ONLY = {"24", "49"}
# A branch with one of these formulas excludes a domain (e.g. height <= 0).
UNDEFINED_FORMULAS = {"undefined", "not defined", "nan", "n/a", "none", "null"}
CASE_SEMANTICS = ("all_agree", "first_match")

_ALLOWED = ("Use only numbers, the variables, + - * / ^, parentheses and the functions sqrt, ln, log10, exp, min, "
            "max, abs, round.")
# Placeholders: {question}, {context} (categorical characteristics), {variables} (name: meaning (unit)).
DEFAULT_TEMPLATE = (
    "Task: {question}\n\n"
    "You are NOT given the patient's measurements. Write the general formula needed to answer this task, "
    "using only the variables listed below. Their units are fixed as stated; include any unit conversion "
    "inside your formula.\n\n"
    "Known patient characteristics:\n{context}\n\n"
    "Variables:\n{variables}\n\n"
    "If the formula depends on thresholds or categories, give one case per branch, each with a condition "
    "written with these variables (for example \"x <= 0.9\"), and use \"otherwise\" for the remaining case. "
    + _ALLOWED + "\n\n"
    "You may think briefly, then end your answer with a JSON object of the form\n"
    '{"cases": [{"condition": "<condition, or always>", "formula": "<expression>"}]}'
)
# Placeholders: {question}, {context}, {variables}, {values} (name = value, in the variables' units).
DEFAULT_PATIENT_TEMPLATE = (
    "Task: {question}\n\n"
    "Known patient characteristics:\n{context}\n\n"
    "Patient values:\n{values}\n\n"
    "Write the formula that applies to THIS patient, as an expression of the variables listed below (their "
    "units are fixed as stated; include any unit conversion inside your formula). Do NOT compute the result: "
    "use the variable names, not the patient's numbers.\n\n"
    "Variables:\n{variables}\n\n"
    + _ALLOWED + "\n\n"
    "You may think briefly, then end your answer with a JSON object of the form\n"
    '{"formula": "<expression>"}'
)


def with_categorical(point: dict[str, Any], entities: dict[str, Any]) -> dict[str, Any]:
    """Continuous values from `point`, categorical (str/bool) fields from `entities`.

    >>> with_categorical({"sex": "Male", "age": [40, "years"]}, {"sex": "Female", "age": [51, "years"]})
    {'age': [40, 'years'], 'sex': 'Female'}
    """
    out = {k: v for k, v in point.items() if not isinstance(v, (str, bool))}
    out.update({k: v for k, v in entities.items() if isinstance(v, (str, bool))})
    return out


def _same_branch_points(pool: list[dict[str, Any]], entities: dict[str, Any], calculator_id: str,
                        branches: list[str], n_points: int) -> list[dict[str, Any]]:
    out = []
    for p in pool:
        q = with_categorical(p, entities)
        try:
            if derive(calculator_id, q).branches == branches:
                out.append(q)
        except Exception:  # noqa: BLE001 - underivable pool rows are skipped
            continue
        if len(out) == n_points:
            break
    return out


# ---------------------------------------------------------------- build

def build(example: Example | dict[str, Any], point_pool: list[dict[str, Any]] | None = None, *,
          mode: str = "general", template: str | None = None, max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS,
          system_prompt: str | None = DEFAULT_SYSTEM_PROMPT, n_points: int = DEFAULT_N_POINTS,
          symbol_docs: dict[str, str] | None = None, digits: int = DEFAULT_DIGITS, label: str = "K") -> Item:
    """point_pool: entity dicts of other (leakage-free) patients of the same calculator, used as test points
    so that thresholds are explored realistically (in "patient" mode, only those in the patient's branch are
    kept; pass a large pool). Without a pool, perturbations of the patient are used at scoring time.
    mode: "general" (no values shown, one case per branch) or "patient" (values shown, this patient's formula).
    template: defaults to DEFAULT_TEMPLATE ("general") or DEFAULT_PATIENT_TEMPLATE ("patient").
    n_points: test points kept from the pool; symbol_docs: {variable: description} overriding
    common.SYMBOL_DOCS; digits: significant digits of the values shown in "patient" mode.

    >>> item = build(mk.data.demo()[1], mode="patient")
    >>> print(item["messages"][-1]["content"].split("Variables:")[1].split("Use only")[0].strip())
    - weight: body weight (kg)
    - height: height (cm)
    >>> item["reference"]["symbols"], item["reference"]["branches"]
    (['weight', 'height'], [])
    """
    if mode not in ("general", "patient"):
        raise ValueError(f"unknown mode {mode!r}")
    ex = as_example(example)
    entities = ex.entities
    d = derive(ex.calculator_id, entities)
    symbols = list(d.inputs)
    fields = {
        "question": task_question(ex.question),
        "context": "\n".join(categorical_context(entities)) or "- (none)",
        "variables": "\n".join(f"- {s}: {symbol_doc(s, entities, symbol_docs)}" for s in symbols),
        "values": "\n".join(f"- {s} = {fmt(v, digits)}" for s, v in d.inputs.items()),
    }
    if template is None:
        template = DEFAULT_TEMPLATE if mode == "general" else DEFAULT_PATIENT_TEMPLATE
    user = render(template, **fields)
    reference: dict[str, Any] = {"entities": entities, "symbols": symbols, "answer": d.answer}
    points = None
    if point_pool and ex.calculator_id not in PERTURB_ONLY:
        if mode == "general":
            points = [with_categorical(p, entities) for p in point_pool[:n_points]]
        else:
            points = _same_branch_points(point_pool, entities, ex.calculator_id, d.branches, n_points)
    reference["point_entities"] = points
    if mode == "patient":
        reference.update(mode="patient", branches=d.branches)
    return make_item(ex, label, user, reference, max_new_tokens, system_prompt, task="K")


# ---------------------------------------------------------------- score

def perturb_entities(entities: dict[str, Any], rng: random.Random,
                     factor: float = DEFAULT_PERTURBATION_FACTOR) -> dict[str, Any]:
    """Multiply every continuous value by a log-uniform factor in [1/factor, factor]; keep categorical fields;
    daily administration counts become random integers in 1..6.

    >>> p = perturb_entities({"sex": "Male", "weight": [70.0, "kg"]}, random.Random(0))
    >>> p["sex"], p["weight"][1], 70 / 3 <= p["weight"][0] <= 70 * 3
    ('Male', 'kg', True)
    """
    def f(x: float) -> float:
        return x * math.exp(rng.uniform(-math.log(factor), math.log(factor)))

    out: dict[str, Any] = {}
    for k, v in entities.items():
        if isinstance(v, bool) or isinstance(v, str):
            out[k] = v
        elif isinstance(v, (int, float)):
            out[k] = f(v)
        elif isinstance(v, list) and len(v) == 2 and v[1] == "per day":
            out[k] = [rng.randint(1, 6), v[1]]           # administrations per day: a positive integer count
        elif isinstance(v, list):
            out[k] = [f(x) if isinstance(x, (int, float)) and not isinstance(x, bool) else x for x in v]
        else:
            out[k] = v
    return out


def eval_cases(cases: list[tuple[str | None, expr.Node | None]], env: dict[str, float],
               semantics: str = "all_agree") -> float:
    """Value of a piecewise answer at one point. Raises ExprError if no case (or an undefined one) applies.

    semantics: "all_agree" — every case whose condition holds must give the same value;
               "first_match" — the first case (in the written order) whose condition holds is used.
    "otherwise" applies when no other condition holds.

    >>> cases = [("x < 10", expr.parse("2 * x")), ("otherwise", expr.parse("x"))]
    >>> eval_cases(cases, {"x": 3}), eval_cases(cases, {"x": 30})
    (6.0, 30.0)
    """
    if semantics not in CASE_SEMANTICS:
        raise ValueError(f"unknown case semantics {semantics!r}")
    matched, fallback = [], None
    for cond, node in cases:
        if cond is not None and cond.strip().lower() in expr.OTHERWISE:
            fallback = node
            continue
        if expr.evaluate_condition(cond, env):
            matched.append(node)
            if semantics == "first_match":
                break
    if not matched and fallback is not None:
        matched = [fallback]
    if not matched:
        raise expr.ExprError("no case applies")
    if any(n is None for n in matched):
        raise expr.ExprError("an 'undefined' branch applies at a valid point")
    values = [expr.evaluate(n, env) for n in matched]
    if any(not math.isclose(v, values[0], rel_tol=1e-9, abs_tol=1e-12) for v in values):
        raise expr.ExprError("overlapping cases disagree")
    return values[0]


def _in_ranges(inputs: dict[str, float], ranges: dict[str, tuple[float, float]] | None) -> bool:
    return ranges is None or all(ranges[k][0] <= v <= ranges[k][1] for k, v in inputs.items() if k in ranges)


def test_points(reference: dict[str, Any], calculator_id: str, seed: int, n_points: int = DEFAULT_N_POINTS,
                perturbation_factor: float = DEFAULT_PERTURBATION_FACTOR,
                plausible_ranges: dict[str, tuple[float, float]] | None = PLAUSIBLE_RANGES
                ) -> list[tuple[dict[str, float], float]]:
    """(canonical inputs, registry value) at the patient point + up to n_points other points: the reference's
    pool points, or perturbations of the patient as a fallback. Perturbed points must lie in the patient's
    branch ("patient" mode) and within `plausible_ranges` (default data.PLAUSIBLE_RANGES; None = no bound).

    >>> pts = test_points(build(mk.data.demo()[1])["reference"], "6", seed=0, n_points=3)
    >>> len(pts), pts[0]
    (4, ({'weight': 70.0, 'height': 175.0}, 22.857142857142858))
    """
    rng = random.Random(seed)
    pool = reference.get("point_entities")
    others = pool or [perturb_entities(reference["entities"], rng, perturbation_factor)
                      for _ in range(3 * n_points)]
    branches = reference.get("branches")
    pts = []
    for i, ent in enumerate([reference["entities"]] + list(others)):
        try:
            d = derive(calculator_id, ent)
            if not math.isfinite(d.answer):
                continue
            if i > 0 and not pool:
                if branches is not None and d.branches != branches:
                    continue
                if not _in_ranges(d.inputs, plausible_ranges):
                    continue
            pts.append((dict(d.inputs), d.answer))
        except Exception:  # noqa: BLE001 - domain errors of the reference at extreme points are skipped
            continue
        if len(pts) == n_points + 1:
            break
    return pts


test_points.__test__ = False  # not a pytest test despite its name


def _parse_cases(text: str) -> list[dict[str, Any]] | None:
    obj = extract_json(text)
    raw_cases = obj.get("cases") if isinstance(obj, dict) else None
    if isinstance(obj, dict) and raw_cases is None and "formula" in obj:
        raw_cases = [{"condition": "always", "formula": obj["formula"]}]
    return raw_cases if isinstance(raw_cases, list) and raw_cases else None


def score_answer(reference: dict[str, Any], text: str, calculator_id: str, seed: int = 0, *,
                 rel_tol: float = DEFAULT_REL_TOL, abs_tol: dict[str, float] | None = None,
                 n_points: int = DEFAULT_N_POINTS, case_semantics: str = "all_agree",
                 perturbation_factor: float = DEFAULT_PERTURBATION_FACTOR,
                 plausible_ranges: dict[str, tuple[float, float]] | None = PLAUSIBLE_RANGES,
                 details: bool = False) -> dict[str, Any]:
    """Score a model answer against a K reference.

    rel_tol: relative tolerance at each point; abs_tol: per-calculator absolute tolerance replacing rel_tol
    (default DEFAULT_ABS_TOL; {} to disable); n_points: test points besides the patient's; case_semantics:
    "all_agree" or "first_match" (see eval_cases); perturbation_factor, plausible_ranges: see test_points.
    details=True adds `points`: one row per test point (inputs, registry value, model value, ok).

    >>> ref = build(mk.data.demo()[1])["reference"]
    >>> v = score_answer(ref, '{"formula": "weight / height^2"}', "6", details=True)   # forgot cm -> m
    >>> v["error_type"], v["point_pass_rate"]
    ('wrong_at_patient_point', 0.0)
    >>> pd.DataFrame(v["points"]).head(2).round(4)
        weight    height  registry   model     ok
    0  70.0000  175.0000   22.8571  0.0023  False
    1  58.7901  103.0353   55.3773  0.0055  False
    """
    raw_cases = _parse_cases(text)
    if raw_cases is None:
        return {"format_valid": False, "correct": False, "error_type": "format_invalid", "point_pass_rate": 0.0}
    cases = []
    try:
        for c in raw_cases:
            # an 'undefined' branch excludes a domain (e.g. height <= 0); it fails only if it applies at a test point
            undefined = str(c["formula"]).strip().lower() in UNDEFINED_FORMULAS
            node = None if undefined else expr.parse(str(c["formula"]))
            cond = c.get("condition")
            cases.append((None if cond is None else str(cond), node))
    except (expr.ExprError, KeyError, TypeError):
        return {"format_valid": False, "correct": False, "error_type": "unparsable_formula", "point_pass_rate": 0.0}

    allowed = set(reference["symbols"])
    used = set().union(*(expr.variables(n) for _, n in cases if n is not None))
    if used - allowed:
        return {"format_valid": True, "correct": False, "error_type": "unknown_variable",
                "point_pass_rate": 0.0, "unknown_variables": sorted(used - allowed)}

    tol_abs = (DEFAULT_ABS_TOL if abs_tol is None else abs_tol).get(calculator_id)
    points = test_points(reference, calculator_id, seed, n_points, perturbation_factor, plausible_ranges)
    passes, rows = [], []
    for env, gold in points:
        try:
            v = eval_cases(cases, env, case_semantics)
            ok = abs(v - gold) <= tol_abs if tol_abs is not None else rel_close(v, gold, rel_tol)
        except expr.ExprError:
            v, ok = math.nan, False
        passes.append(ok)
        rows.append({**env, "registry": gold, "model": v, "ok": ok})
    rate = sum(passes) / len(passes)
    correct = all(passes)
    out = {
        "format_valid": True,
        "correct": correct,
        "error_type": None if correct else ("wrong_at_patient_point" if not passes[0] else "wrong_elsewhere"),
        "point_pass_rate": rate,
        "original_point_correct": passes[0],
        "n_points": len(passes),
    }
    return {**out, "points": rows} if details else out


def score(item: Item, text: str, **options: Any) -> dict[str, Any]:
    """Score a model answer for a K item. Options: see score_answer (rel_tol, abs_tol, n_points, case_semantics,
    perturbation_factor, plausible_ranges, details). The perturbation seed is derived from the item id, so
    scores are reproducible.

    >>> item = build(mk.data.demo()[1])
    >>> score(item, '{"cases": [{"condition": "always", "formula": "weight / (height / 100)^2"}]}')["n_points"]
    51
    >>> score(item, '{"cases": [{"condition": "always", "formula": "w / h^2"}]}')["unknown_variables"]
    ['h', 'w']
    """
    return score_answer(item["reference"], text, item["calculator_id"],
                        seed=zlib.crc32(item["item_id"].encode()), **options)


def reference_answer(item: Item) -> str:
    """The registry's formula for this patient's branch, in the expected JSON format. Always correct in "patient"
    mode; in "general" mode it is correct only for calculators without branches, since the registry resolves
    branch conditions in code and does not store them as formulas.

    >>> reference_answer(build(mk.data.demo()[1], mode="patient"))
    '{"formula": "weight / (height / 100)^2"}'
    """
    ref = item["reference"]
    formula = expr.to_str(inline(derive(item["calculator_id"], ref["entities"])))
    if ref.get("mode") == "patient":
        return json.dumps({"formula": formula})
    return json.dumps({"cases": [{"condition": "always", "formula": formula}]})


PROBE = Probe("K", "Knowledge", "writing the formula (general, or for this patient) without computing", build,
              score, reference_answer)
