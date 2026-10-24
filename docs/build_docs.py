"""Generate docs/api.md (from the docstrings) and docs/calculators.md (from the registry and the dataset).

    python docs/build_docs.py                # both (calculators.md downloads the dataset once)
    python docs/build_docs.py --api-only

The docstring examples are tested by tests/test_docs.py, so the generated reference stays correct.
"""
from __future__ import annotations

import argparse
import importlib
import inspect
import re
from pathlib import Path

import medcalc_kit as mk

DOCS = Path(__file__).parent

# Public API, in reading order: (module, members). Members are documented in this order.
API = [
    ("medcalc_kit.benchmark", ["evaluate_model", "EvaluationReport"]),
    ("medcalc_kit.data", ["load", "demo", "MedCalcDataset", "concat", "from_records", "Example", "as_example",
                          "load_dataframe",
                          "equation_subset", "parse_entities", "dataset_revision", "DEFAULT_REVISION",
                          "EQUATION_CATEGORIES"]),
    ("medcalc_kit.data.quality", ["usable_train_pool", "flag_train_rows", "leak_flags", "leaking_rows",
                                  "registry_agrees", "implausible_inputs",
                                  "note_hash", "PLAUSIBLE_RANGES"]),
    ("medcalc_kit.calculators", ["derive", "table", "get", "list_calculators", "verify_registry", "Derivation", "Step",
                                 "Calculator", "KNOWN_REFERENCE_DEVIATIONS"]),
    ("medcalc_kit.calculators.registry", ["calculator", "new_derivation", "is_male"]),
    ("medcalc_kit.calculators.verify", ["verify", "check_row", "main"]),
    ("medcalc_kit.probes", ["ProbeSuite", "score", "reference_answer", "prompt", "get", "PROBES", "ALL_PROBES",
                            "STEP_PROBES",
                            "Probe", "read_items", "write_items", "items_frame", "as_items", "as_item"]),
    ("medcalc_kit.probes.extraction", ["build", "score", "score_answer", "score_field", "reference_answer",
                                       "calculator_fields", "field_kind", "default_field_hint", "TEMPLATES",
                                       "DEFAULT_TEMPLATE",
                                       "KIND_HINT"]),
    ("medcalc_kit.probes.conversion", ["build", "score", "score_answer", "reference_answer", "convertible_fields",
                                       "UNIT_TABLE", "VARIABLE_FIELDS", "TEMPLATES", "DEFAULT_TEMPLATE"]),
    ("medcalc_kit.probes.knowledge", ["build", "score", "score_answer", "reference_answer", "test_points",
                                      "eval_cases", "perturb_entities", "with_categorical", "TEMPLATES",
                                      "PATIENT_TEMPLATES", "DEFAULT_TEMPLATE", "DEFAULT_PATIENT_TEMPLATE"]),
    ("medcalc_kit.probes.substitution", ["build", "score", "score_answer", "reference_answer", "TEMPLATES",
                                         "DEFAULT_TEMPLATE", "CONVERSION_NOTE"]),
    ("medcalc_kit.probes.arithmetic", ["build", "score", "score_answer", "reference_answer", "TEMPLATES",
                                       "DEFAULT_TEMPLATE"]),
    ("medcalc_kit.probes.end_to_end", ["build", "score", "score_answer", "reference_answer", "answer_type",
                                       "parse_date", "parse_weeks_days", "TEMPLATES", "DEFAULT_TEMPLATE",
                                       "ANSWER_FORMATS"]),
    ("medcalc_kit.probes.common", ["render", "resolve_template", "template_hash", "fmt", "presented", "symbol_doc",
                                   "SYMBOL_DOCS", "task_question",
                                   "categorical_context", "mme_drugs", "inline", "branch_formula", "make_item",
                                   "numeric_answer", "rel_close", "DEFAULT_SYSTEM_PROMPT", "DEFAULT_DIGITS"]),
    ("medcalc_kit.generation", ["run_items", "read_records", "done_item_ids", "prompt_key", "model_name",
                                "classify_generation",
                                "is_degenerate", "CATEGORIES"]),
    ("medcalc_kit.generation.artifacts", ["repeated_ngram_share", "max_line_repeats"]),
    ("medcalc_kit.generation.hf", ["HFBackend"]),
    ("medcalc_kit.evaluate", ["score_records", "summary", "to_units", "read_jsonl"]),
    ("medcalc_kit.expr", ["evaluate", "parse", "variables", "substitute", "replace_vars", "to_str", "canonical",
                          "evaluate_condition", "literals", "map_literals", "ExprError", "FUNCTIONS"]),
    ("medcalc_kit.units", ["convert", "concentration", "clean_unit", "weight_kg", "height_cm", "age_years",
                           "platelets_1e9_per_L", "insulin_uIU_per_mL", "UnitError", "MOLAR_MASS"]),
    ("medcalc_kit.parsing", ["extract_json", "to_number"]),
]


# Top-level shortcuts: name -> module where it is documented.
SHORTCUTS = {"evaluate_model": "benchmark", "EvaluationReport": "benchmark", "load": "data", "derive": "calculators",
             "ProbeSuite": "probes", "score": "probes",
             "reference_answer": "probes", "run_items": "generation", "read_records": "generation",
             "score_records": "evaluate", "summary": "evaluate"}


def anchor(text: str) -> str:
    """GitHub's heading slug."""
    return re.sub(r"[^\w\- ]", "", text.lower()).replace(" ", "-")


def qualified(module_name: str, name: str) -> str:
    return f"{module_name.removeprefix('medcalc_kit.')}.{name}"


def doc_block(doc: str) -> str:
    """Docstring as Markdown: prose as is, `>>>` examples in python code blocks."""
    out, code = [], []
    lines = inspect.cleandoc(doc).splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip().startswith(">>>"):
            indent = len(line) - len(line.lstrip())
            while i < len(lines) and lines[i].strip() and len(lines[i]) - len(lines[i].lstrip()) >= indent:
                code.append(lines[i][indent:].replace("# doctest: +SKIP", "").rstrip())
                i += 1
            out += ["```python", *code, "```"]
            code = []
            continue
        out.append(line)
        i += 1
    return "\n".join(out).strip()


def signature(name: str, obj) -> str:
    try:
        sig = inspect.signature(obj)
    except (TypeError, ValueError):
        return name
    # long string defaults are shown by the name of the module constant holding them (e.g. DEFAULT_TEMPLATE)
    module = inspect.getmodule(obj)
    constants = {v: k for k, v in vars(module).items() if k.isupper() and isinstance(v, str)} if module else {}
    params = []
    for p in sig.parameters.values():
        if isinstance(p.default, str) and p.default in constants and len(p.default) > 30:
            p = p.replace(default=_Named(constants[p.default]))
        params.append(p)
    sig = str(sig.replace(parameters=params))
    # annotations are strings (from __future__ import annotations): drop their quotes, keep those of defaults
    sig = re.sub(r"(: |-> )'([^']*)'", r"\1\2", sig)
    return f"{name}{sig}"


class _Named:
    def __init__(self, name: str):
        self.name = name

    def __repr__(self) -> str:
        return self.name


def constant(title: str, name: str, value) -> str:
    text = re.sub(r" at 0x[0-9a-f]+>", ">", repr(value))     # memory addresses change between runs
    if len(text) > 400:
        text = text[:400] + " ..."
    return f"### `{title}`\n\n```python\n{name} = {text}\n```"


def member(module, name: str) -> str:
    obj = getattr(module, name)
    title = qualified(module.__name__, name)
    if not (inspect.isclass(obj) or inspect.isroutine(obj)):
        return constant(title, name, obj)
    kind = "class" if inspect.isclass(obj) else "def"
    parts = [f"### `{title}`", "", "```python", f"{kind} {signature(name, obj)}", "```", ""]
    if inspect.getdoc(obj):
        parts.append(doc_block(inspect.getdoc(obj)))
    if inspect.isclass(obj):
        for meth_name, meth in vars(obj).items():
            if meth_name.startswith("_") and meth_name != "__init__":
                continue
            if isinstance(meth, (classmethod, staticmethod)):
                meth = meth.__func__
            if isinstance(meth, property):
                if meth.__doc__:
                    parts += ["", f"**`.{meth_name}`** (property): {inspect.getdoc(meth)}"]
                continue
            if not inspect.isfunction(meth) or meth_name == "__init__" or not meth.__doc__:
                continue
            parts += ["", f"#### `.{signature(meth_name, meth)}`", "", doc_block(inspect.getdoc(meth))]
    return "\n".join(parts)


def build_api() -> str:
    toc = ["# API reference", "",
           f"medcalc-kit {mk.__version__}. Generated from the docstrings by `docs/build_docs.py`; every example is "
           "run by the test suite (`tests/test_docs.py`). Examples marked as needing the dataset download it from "
           "the Hugging Face Hub; the others use `mk.data.demo()`, four hand-written examples.", "",
           "See also the [user guide](guide.md) and the [calculator list](calculators.md).", ""]
    top = inspect.getdoc(mk).split("\n\n", 1)
    body = ["", "---", "", "## `medcalc_kit` shortcuts", "", top[1].split("\n\n")[0], "", doc_block(top[1].split(
        "\n\n", 1)[1]), "", "| shortcut | documented as |", "|---|---|"]
    body += [f"| `mk.{n}` | [`{qualified('medcalc_kit.' + m, n)}`](#{anchor(qualified('medcalc_kit.' + m, n))}) |"
             for n, m in SHORTCUTS.items()]
    toc.append(f"- [`medcalc_kit` shortcuts](#{anchor('medcalc_kit shortcuts')})")
    for module_name, names in API:
        module = importlib.import_module(module_name)
        toc.append(f"- [`{module_name}`](#{anchor(module_name)}): " + ", ".join(
            f"[`{n}`](#{anchor(qualified(module_name, n))})" for n in names))
        doc = inspect.getdoc(module) or ""
        first, _, rest = doc.partition("\n\n")
        body += ["", "---", "", f"## `{module_name}`", "", first, ""]
        if rest:
            body += [doc_block(rest), ""]
        for name in names:
            body += [member(module, name), ""]
    return "\n".join(toc + body).rstrip() + "\n"


def build_calculators() -> str:
    from medcalc_kit.probes.common import SYMBOL_DOCS
    from medcalc_kit.probes.extraction import calculator_fields

    ds = mk.load(equation_only=True)
    fields = calculator_fields(ds)
    counts = ds.calculators().set_index("Calculator ID")
    lines = ["# Calculators", "",
             "The 33 equation-based calculators of the registry. For each: the entities `derive()` expects "
             "(names and kinds, as annotated in MedCalc-Bench-Verified), the canonical variables the probes use, and "
             "one worked example from the test split. Generated by `docs/build_docs.py`.", "",
             "| id | name | category | train | test |", "|---|---|---|---|---|"]
    for c in mk.calculators.list_calculators():
        row = counts.loc[c.calculator_id]
        link = anchor(f"{c.calculator_id} - {c.name}")
        counts_cells = f"{row['Category']} | {row['train']} | {row['test']}"
        lines.append(f"| [{c.calculator_id}](#{link}) | {c.name} | {counts_cells} |")
    for c in mk.calculators.list_calculators():
        ex = ds.filter(calculator=c.calculator_id, split="test")[0]
        d = ex.derive()
        lines += ["", f"## {c.calculator_id} - {c.name}", ""]
        deviation = mk.calculators.KNOWN_REFERENCE_DEVIATIONS.get(c.calculator_id)
        if deviation:
            lines += [f"> Deviation from the reference code: {deviation}", ""]
        lines += ["Entities (annotation name: kind): " + ", ".join(f"`{k}`: {v}" for k, v in
                                                               fields[c.calculator_id].items()), ""]
        variables = []
        for v in d.inputs:
            variables.append(f"`{v}` ({SYMBOL_DOCS[v]})" if v in SYMBOL_DOCS else f"`{v}`")
        lines += ["Variables: " + ", ".join(variables), "", f"Example `{ex.example_id}`:", "", "```python",
                  f"mk.derive({c.calculator_id!r}, {ex.entities!r})", "```", "",
                  "| step | expression | value |", "|---|---|---|"]
        lines += [f"| `{s.name}` | `{s.expr}` | {s.value:.6g} |" for s in d.steps]
        if d.branches:
            lines += ["", "Branches applied: " + ", ".join(f"`{b}`" for b in d.branches)]
        lines += ["", f"Ground truth {ex.ground_truth:.6g} (interval {ex.lower:.6g} to {ex.upper:.6g})."]
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api-only", action="store_true", help="skip calculators.md (no dataset download)")
    args = ap.parse_args()
    (DOCS / "api.md").write_text(build_api())
    print("wrote", DOCS / "api.md")
    if not args.api_only:
        (DOCS / "calculators.md").write_text(build_calculators())
        print("wrote", DOCS / "calculators.md")


if __name__ == "__main__":
    main()
