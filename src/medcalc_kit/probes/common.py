"""Pieces shared by the probes: items, number presentation, variable documentation, resolved formulas.

An item is a JSON-serialisable dict (collections of items are DataFrames, one row per item, see items_frame):
    {"item_id", "example_id", "calculator_id", "calculator_name", "probe", "messages": [...],
     "max_new_tokens", "reference": {...}}           (+ "task" when the probe label differs from its task)
`messages` is the chat sent to the model; `reference` is everything the scorer needs. References are
derived from the executable calculator registry, never from an LLM.

Prompt texts are templates: `{name}` placeholders are replaced by `render`; any other text, including JSON
braces, is kept as is. Each probe documents its placeholders next to its DEFAULT_TEMPLATE.
"""
from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Iterable, Mapping
from typing import Any

import pandas as pd

from medcalc_kit import expr
from medcalc_kit.calculators import Derivation, derive
from medcalc_kit.data import Example
from medcalc_kit.parsing import extract_json, to_number

Item = dict[str, Any]

DEFAULT_SYSTEM_PROMPT = "You are a careful clinical calculation assistant."
DEFAULT_DIGITS = 6           # significant digits of the numbers shown to the model

ADMISSION_SENTENCE = re.compile(
    r"\s*You should use the patient's medical values and health status when they were first admitted "
    r"to the hospital prior to any treatment\.?", re.IGNORECASE)

# Meaning and canonical unit of every registry input, as shown to the model.
SYMBOL_DOCS = {
    "age": "patient age (years)", "weight": "body weight (kg)", "height": "height (cm)",
    "scr": "serum creatinine (mg/dL)", "scr_raw": "serum creatinine (mg/dL)", "ucr": "urine creatinine (mg/dL)",
    "na": "serum sodium (mEq/L)", "na_raw": "serum sodium (mEq/L)", "sna": "serum sodium (mEq/L)",
    "una": "urine sodium (mEq/L)", "cl": "serum chloride (mEq/L)", "hco3": "serum bicarbonate (mEq/L)",
    "albumin": "serum albumin (g/dL)", "ca": "serum calcium (mg/dL)", "glucose": "serum glucose (mg/dL)",
    "bun": "blood urea nitrogen (mg/dL)", "tc": "total cholesterol (mg/dL)", "hdl": "HDL cholesterol (mg/dL)",
    "tg": "triglycerides (mg/dL)", "insulin": "fasting insulin (µIU/mL)", "ast": "aspartate aminotransferase (U/L)",
    "alt": "alanine aminotransferase (U/L)", "platelets": "platelet count (10^9/L)",
    "bili_raw": "total bilirubin (mg/dL)", "inr_raw": "international normalized ratio (INR)",
    "sbp": "systolic blood pressure (mm Hg)", "dbp": "diastolic blood pressure (mm Hg)",
    "smoker": "1 if the patient smokes, else 0", "bp_treated": "1 if blood pressure is treated with medication, else 0",
    "hr": "heart rate (beats per minute)", "qt": "QT interval (msec)", "target_bmi": "target body mass index (kg/m^2)",
    "dose": "dose of the input steroid (mg)",
}


def render(template: str, **fields: Any) -> str:
    """Replace the `{name}` placeholders whose name is given; leave every other brace untouched.

    >>> render('Compute {expression}, reply {"result": <number>} {unknown}', expression="1 + 1")
    'Compute 1 + 1, reply {"result": <number>} {unknown}'
    """
    return re.sub(r"\{(\w+)\}", lambda m: str(fields[m.group(1)]) if m.group(1) in fields else m.group(0), template)


def template_hash(template: str) -> str:
    """Short hash of a template text, recorded in each item so that the exact prompt can be cited.

    >>> template_hash("Compute {expression}.")
    '6366847ca0'
    """
    return hashlib.sha1(template.encode()).hexdigest()[:10]


def resolve_template(template: str | None, templates: dict[str, str]) -> tuple[str, str]:
    """(name, text) of a template given by variant name ("v2"), by text, or None (the first variant). A text that
    is not one of the variants is named "custom".

    >>> resolve_template("v2", {"v1": "A {x}", "v2": "B {x}"}), resolve_template("C {x}", {"v1": "A {x}"})
    (('v2', 'B {x}'), ('custom', 'C {x}'))
    """
    if template is None:
        name = next(iter(templates))
        return name, templates[name]
    if template in templates:
        return template, templates[template]
    name = next((k for k, v in templates.items() if v == template), "custom")
    return name, template


def fmt(v: float, digits: int = DEFAULT_DIGITS) -> str:
    """Presentation format for numbers shown to the model (`digits` significant digits).

    >>> fmt(70.0), fmt(1 / 3), fmt(1 / 3, digits=3), fmt(1.5e-7)
    ('70', '0.333333', '0.333', '1.5e-07')
    """
    s = f"{v:.{digits}g}"
    return s if "e" not in s else repr(float(s))


def presented(v: float, digits: int = DEFAULT_DIGITS) -> float:
    """The value as the model sees it (after fmt).

    >>> presented(1 / 3, digits=3)
    0.333
    """
    return float(fmt(v, digits))


def task_question(question: str) -> str:
    """The benchmark question without the 'values at first admission' sentence.

    >>> task_question("What is the BMI? You should use the patient's medical values and health status when they "
    ...               "were first admitted to the hospital prior to any treatment.")
    'What is the BMI?'
    """
    return ADMISSION_SENTENCE.sub("", question).strip()


def mme_drugs(entities: dict[str, Any]) -> dict[str, str]:
    """tag -> drug name, consistent with the MME calculator's variable names (dose_<tag>, perday_<tag>).

    >>> mme_drugs({"OxyCODONE Dose": [10, "mg"], "OxyCODONE Dose Per Day": [2, "per day"]})
    {'oxycodone': 'OxyCODONE'}
    """
    out = {}
    for key in entities:
        if key.endswith(" Dose"):
            drug = key[: -len(" Dose")]
            out["".join(ch for ch in drug.lower() if ch.isalnum())] = drug
    return out


def symbol_doc(name: str, entities: dict[str, Any], docs: dict[str, str] | None = None) -> str:
    """Meaning and unit of a registry variable, as shown to the model. `docs` overrides SYMBOL_DOCS entries.

    >>> symbol_doc("scr", {})
    'serum creatinine (mg/dL)'
    >>> symbol_doc("scr", {}, docs={"scr": "creatinine in mg/dL"})
    'creatinine in mg/dL'
    """
    if docs and name in docs:
        return docs[name]
    if name in SYMBOL_DOCS:
        return SYMBOL_DOCS[name]
    kind, _, tag = name.partition("_")
    drug = mme_drugs(entities).get(tag, tag)
    if kind == "dose":
        unit = "µg" if drug.lower().startswith("fentanyl") else "mg"
        return f"dose of {drug} per administration ({unit})"
    if kind == "perday":
        return f"number of administrations of {drug} per day"
    raise KeyError(name)


def inline(d: Derivation) -> expr.Node:
    """Single expression of the resolved branch over the patient inputs (coefficients as constants).

    >>> expr.to_str(inline(derive("6", {"weight": [70, "kg"], "height": [175, "cm"]})))
    'weight / (height / 100)^2'
    """
    nodes: dict[str, expr.Node] = {}
    coeffs = {k: expr.Num(float(v)) for k, v in d.coefficients.items()}
    for s in d.steps:
        nodes[s.name] = expr.replace_vars(s.expr, {**coeffs, **nodes})
    return nodes[d.steps[-1].name]


def branch_formula(example: Example, digits: int = DEFAULT_DIGITS) -> tuple[expr.Node, dict[str, float], Derivation]:
    """(formula of this patient's branch, presented values of the variables it uses, derivation).

    >>> formula, values, d = branch_formula(mk.data.demo()[2])
    >>> expr.to_str(formula), values
    ('na - (cl + hco3)', {'na': 140.0, 'cl': 104.0, 'hco3': 24.0})
    """
    d = derive(example.calculator_id, example.entities)
    formula = inline(d)
    used = expr.variables(formula)
    values = {k: presented(v, digits) for k, v in d.inputs.items() if k in used}
    return formula, values, d


def categorical_context(entities: dict[str, Any]) -> list[str]:
    """Fixed categorical characteristics (sex, race, drugs...) as '- key: value' lines.

    >>> categorical_context({"sex": "Female", "age": [51, "years"], "smoker": True})
    ['- sex: Female', '- smoker: True']
    """
    lines = []
    for k, v in entities.items():
        if isinstance(v, (str, bool)):
            lines.append(f"- {k}: {v}")
    if "input steroid" in entities:
        lines.append(f"- input steroid: {entities['input steroid'][0]}")
    drugs = mme_drugs(entities)
    if drugs:
        lines.append(f"- opioids taken: {', '.join(drugs.values())}")
    return lines


def make_item(example: Example, probe: str, user: str, reference: dict[str, Any], max_new_tokens: int,
              system_prompt: str | None = DEFAULT_SYSTEM_PROMPT, task: str | None = None,
              template: tuple[str, str] | None = None) -> Item:
    """Assemble an item (used by every probe's build). task: the probe that scores this item when `probe` is a
    custom label (e.g. two K variants "K", "Kg"). template: (name, text) of the template used, recorded as
    `template` (its name) and `template_hash`.

    >>> item = make_item(mk.data.demo()[1], "A", "Compute 1 + 1", {"gold_value": 2.0}, 64, system_prompt=None)
    >>> item["item_id"], item["messages"]
    ('demo:6:1:A', [{'role': 'user', 'content': 'Compute 1 + 1'}])
    """
    messages = [{"role": "system", "content": system_prompt}] if system_prompt else []
    item = {
        "item_id": f"{example.example_id}:{probe}",
        "example_id": example.example_id,
        "calculator_id": example.calculator_id,
        "calculator_name": example.calculator_name,
        "probe": probe,
        "messages": messages + [{"role": "user", "content": user}],
        "max_new_tokens": max_new_tokens,
        "reference": reference,
    }
    if template is not None:
        item["template"], item["template_hash"] = template[0], template_hash(template[1])
    if task and task != probe:
        item["task"] = task
    return item


ITEM_COLUMNS = ("item_id", "probe", "task", "example_id", "calculator_id", "calculator_name", "template",
                "template_hash", "max_new_tokens", "messages", "reference")


def _drop_missing(row: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in row.items() if not (isinstance(v, float) and math.isnan(v))}


def as_item(item: Item | pd.Series) -> Item:
    """One item as a dict, from a dict (returned as is) or a DataFrame row (missing cells dropped).

    >>> items = mk.ProbeSuite(["A"]).build(mk.data.demo())
    >>> as_item(items.iloc[0])["item_id"]
    'demo:2:1:A'
    """
    return _drop_missing(item.to_dict()) if isinstance(item, pd.Series) else item


def prompt(item: Item | pd.Series) -> str:
    """The chat of an item as readable text ("[role] content" blocks), to see what the model is asked.

    >>> item = mk.probes.arithmetic.build(mk.data.demo()[1])
    >>> print(prompt(item))
    [system] You are a careful clinical calculation assistant.
    <BLANKLINE>
    [user] Compute the value of the following expression ...
    <BLANKLINE>
    70 / (175 / 100)^2
    <BLANKLINE>
    Work carefully without any tool. ...
    """
    return "\n\n".join(f"[{m['role']}] {m['content']}" for m in as_item(item)["messages"])


def as_items(items: pd.DataFrame | Iterable[Item] | Mapping[str, Iterable[Item]]) -> list[Item]:
    """Items (or generation records) as a list of dicts, from a DataFrame, a list or {label: [item, ...]}.
    Missing cells of a DataFrame (NaN, e.g. `task` for items whose label is their task) are dropped.

    >>> items = mk.ProbeSuite({"K": {}, "Kg": {"task": "K"}}).build(mk.data.demo())
    >>> dicts = as_items(items)
    >>> "task" in dicts[0], dicts[-1]["task"]                   # NaN cells are not carried over
    (False, 'K')
    """
    if isinstance(items, pd.DataFrame):
        return [_drop_missing(row) for row in items.to_dict("records")]
    if isinstance(items, Mapping):
        return [it for group in items.values() for it in group]
    return list(items)


def items_frame(items: pd.DataFrame | Iterable[Item] | Mapping[str, Iterable[Item]]) -> pd.DataFrame:
    """One row per item; `messages` and `reference` stay nested (object columns).

    >>> items = items_frame([mk.probes.arithmetic.build(ex) for ex in mk.data.demo()])
    >>> items[["item_id", "probe", "max_new_tokens"]].head(2)
          item_id probe  max_new_tokens
    0  demo:2:1:A     A            1024
    1  demo:6:1:A     A            1024
    """
    if isinstance(items, pd.DataFrame):
        return items
    df = pd.DataFrame(as_items(items))
    first = [c for c in ITEM_COLUMNS if c in df.columns]
    return df[first + [c for c in df.columns if c not in first]]


def rel_close(a: float, b: float, tol: float) -> bool:
    """|a - b| <= tol * |b| (b is the reference).

    >>> rel_close(101, 100, 0.01), rel_close(102, 100, 0.01)
    (True, False)
    """
    return abs(a - b) <= tol * max(abs(b), 1e-12)


def numeric_answer(text: str, key: str) -> float | None:
    """The number under `key` in the last JSON object of the text.

    >>> numeric_answer('Thinking... {"result": "12.5 mEq/L"}', "result")
    12.5
    """
    obj = extract_json(text)
    if isinstance(obj, dict) and key in obj:
        return to_number(obj[key])
    return None
