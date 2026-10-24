"""Evaluate a model on MedCalc-Bench in one call: the general score and the step-by-step diagnosis.

- **General**: the original task (E2E) on every example of the benchmark (55 calculators, 1,100 test examples),
  by category.
- **Step by step**: on the 33 equation-based calculators, each step of the calculation measured on its own:
  E (finding the values in the note), K (knowing the formula), S (substituting the values), A (computing), next
  to E2E on the same examples, and per example the first step that fails.
- **Robustness**: with `prompt_variants=3`, every prompt is also asked in two paraphrases (same information and
  answer format, different wording), and `prompt_sensitivity` shows how much each score depends on the wording.

    >>> report = mk.evaluate_model(model)                       # doctest: +SKIP
    >>> report                                                  # doctest: +SKIP
    >>> report.general, report.steps, report.by_calculator      # doctest: +SKIP

Generations are saved as they come (`<output_dir>/generations.jsonl`): run the same call again after an
interruption to resume, or with `model=None` to rescore what was generated.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from medcalc_kit.calculators import CALCULATORS
from medcalc_kit.data import MedCalcDataset, load, usable_train_pool
from medcalc_kit.evaluate import score_records, summary
from medcalc_kit.generation.runner import model_name, run_items
from medcalc_kit.probes.common import items_frame
from medcalc_kit.probes.suite import STEP_PROBES, ProbeSuite, write_items

VARIANT_SEP = "@"           # label of a paraphrased item: "<probe>@<variant>", e.g. "K@v2"
STEP_NAMES = {"E": "extraction", "U": "unit conversion", "K": "formula knowledge", "S": "substitution",
              "A": "arithmetic", "E2E": "end to end"}


@dataclass
class EvaluationReport:
    """Result of `evaluate_model`. Every view is a DataFrame; `scores` has one row per answer (score_records columns,
    with the answer `text`, the `verdict`, `calculator_name` and `calculator_category`) and `items` one row per
    prompt, for any further analysis.

    general:        end-to-end accuracy per category of calculator, and overall ("all")
    steps:          per step (E, K, S, A, and E2E on the same examples): well-formed answers, competence, accuracy
    by_calculator:  accuracy per calculator and step: where the chain breaks
    examples:       one row per example: correctness at each step and the first step that fails
    first_failures: for the equation-based examples, how often each step is the first to fail, and the E2E accuracy
                    in each case
    consistency:    E2E accuracy when every step succeeds and when a step fails: how faithfully the steps represent
                    the task
    prompt_sensitivity: accuracy of each step with each prompt variant, their mean, standard deviation and range
    by_label:       accuracy per item label, e.g. custom variants such as "Kg" next to "K"

    The views use the default prompts ("v1"); paraphrases (prompt_variants > 1) only enter prompt_sensitivity.

    >>> def oracle(messages, max_new_tokens):                   # a perfect "model", to show the report
    ...     return mk.reference_answer(by_prompt[mk.generation.prompt_key(messages, max_new_tokens)])
    >>> ds = mk.data.demo()
    >>> items = mk.ProbeSuite({"E": {}, "K": {"mode": "patient"}, "S": {}, "A": {}, "E2E": {}}).build(ds)
    >>> by_prompt = {mk.generation.prompt_key(it["messages"], it["max_new_tokens"]): it
    ...              for it in mk.probes.as_items(items)}
    >>> import tempfile
    >>> report = mk.evaluate_model(oracle, tempfile.mkdtemp(), dataset=ds, split="demo")
    >>> report
    MedCalc-Bench evaluation of oracle
      general (end to end): 100.0% of 4 examples (4 calculators)
      step by step (4 examples of equation-based calculators):
        E    extraction         100.0%
        K    formula knowledge  100.0%
        S    substitution       100.0%
        A    arithmetic         100.0%
        E2E  end to end         100.0%
    >>> report.general
              n  well_formed  accuracy
    category
    all       4          1.0       1.0
    lab test  2          1.0       1.0
    physical  2          1.0       1.0
    """
    model: str
    items: pd.DataFrame
    scores: pd.DataFrame
    output_dir: Path | None = None

    @property
    def _primary(self) -> pd.DataFrame:
        """One label per task: the label named after the task (e.g. "K"), else, when a task only has custom labels,
        those that are not paraphrases. Paraphrases ("K@v2") and other custom labels ("Kg") are in by_label."""
        s = self.scores
        own = s.probe == s.task
        tasks_with_own = set(s.task[own])
        return s[own | (~s.task.isin(tasks_with_own) & ~s.probe.str.contains(VARIANT_SEP, regex=False))]

    def __repr__(self) -> str:
        e2e = self._primary[self._primary.task == "E2E"]
        sens = self.prompt_sensitivity
        variants = [c for c in sens.columns if c not in ("mean", "sd", "range")]

        def spread(task: str) -> str:
            if len(variants) < 2 or task not in sens.index:
                return ""
            row = sens.loc[task, variants]
            return f"  (prompt variants: {row.min():.1%} to {row.max():.1%})"

        lines = [f"MedCalc-Bench evaluation of {self.model}",
                 f"  general (end to end): {e2e.correct.mean():.1%} of {len(e2e)} examples "
                 f"({e2e.calculator_id.nunique()} calculators){spread('E2E')}"]
        steps = self.steps
        if len(steps) > 1:
            n = int(steps.loc["E2E", "n"]) if "E2E" in steps.index else 0
            lines.append(f"  step by step ({n} examples of equation-based calculators):")
            lines += [f"    {p:4} {STEP_NAMES.get(p, p):18} {row.accuracy:6.1%}{spread(p) if p != 'E2E' else ''}"
                      for p, row in steps.iterrows()]
            c = self.consistency
            if "all steps correct" in c.index and "a step failed" in c.index:
                lines.append(f"  consistency: E2E correct for {c.loc['all steps correct', 'e2e_accuracy']:.0%} of the "
                             f"examples whose steps all succeed, {c.loc['a step failed', 'e2e_accuracy']:.0%} when "
                             "a step fails")
        return "\n".join(lines)

    @property
    def general(self) -> pd.DataFrame:
        e2e = self._primary[self._primary.task == "E2E"]
        rows = {"all": e2e, **{c: g for c, g in e2e.groupby("calculator_category")}}
        out = pd.DataFrame([{"category": c, "n": len(g), "well_formed": g.well_formed.mean(),
                             "accuracy": g.correct.mean()} for c, g in rows.items()])
        return out.set_index("category")

    @property
    def steps(self) -> pd.DataFrame:
        s = self._primary[self._primary.calculator_id.isin(list(CALCULATORS))]
        if s.empty:
            return pd.DataFrame(columns=["n", "well_formed", "competence", "accuracy"])
        out = summary(s, by=("task",), collapse=())
        order = [p for p in (*STEP_PROBES, "E2E") if p in out.index]
        out = out.loc[order].rename(columns={"n_units": "n", "overall": "accuracy"})
        out.index.name = "step"
        return out.astype({"n": int})

    @property
    def by_calculator(self) -> pd.DataFrame:
        table = self._primary.pivot_table(index=["calculator_id", "calculator_name", "calculator_category"],
                                        columns="task", values="correct", aggfunc="mean")
        table = table[[p for p in (*STEP_PROBES, "E2E") if p in table.columns]]
        table.columns.name = None
        table = table.reset_index().rename(columns={"calculator_category": "category"})
        return table.sort_values("calculator_id", key=lambda c: c.astype(int)).reset_index(drop=True)

    @property
    def examples(self) -> pd.DataFrame:
        table = self._primary.pivot_table(index=["example_id", "calculator_id", "calculator_category"],
                                          columns="task", values="correct", aggfunc="first")
        steps = [p for p in STEP_PROBES if p in table.columns]
        table = table[steps + [p for p in ("E2E",) if p in table.columns]].reset_index()
        table = table.rename(columns={"calculator_category": "category"})
        table.columns.name = None

        def first_failure(row) -> str | None:
            if row["calculator_id"] not in CALCULATORS:
                return None
            for p in steps:
                if row[p] is not None and row[p] == row[p] and not row[p]:      # skip missing (NaN) steps
                    return p
            return "none"

        table["first_failure"] = table.apply(first_failure, axis=1)
        return table

    @property
    def first_failures(self) -> pd.DataFrame:
        ex = self.examples.dropna(subset=["first_failure"])
        order = [p for p in (*STEP_PROBES, "none") if p in set(ex.first_failure)]
        ex = ex.assign(E2E=ex["E2E"].astype(float))
        out = ex.groupby("first_failure").agg(examples=("example_id", "size"), e2e_accuracy=("E2E", "mean"))
        out["share"] = out.examples / out.examples.sum()
        return out.loc[order, ["examples", "share", "e2e_accuracy"]]

    @property
    def consistency(self) -> pd.DataFrame:
        ex = self.examples.dropna(subset=["first_failure"])
        if ex.empty or "E2E" not in ex:
            return pd.DataFrame(columns=["examples", "e2e_accuracy"])
        ok = ex.first_failure == "none"
        rows = {"all steps correct": ex[ok], "a step failed": ex[~ok]}
        return pd.DataFrame([{"case": k, "examples": len(g), "e2e_accuracy": g["E2E"].astype(float).mean()}
                             for k, g in rows.items() if len(g)]).set_index("case")

    @property
    def by_label(self) -> pd.DataFrame:
        """Per item label (custom variants such as "Kg", paraphrases such as "K@v2"): n, well-formed, competence,
        accuracy."""
        out = summary(self.scores, by=("probe",), collapse=()).rename(columns={"n_units": "n", "overall": "accuracy"})
        out.index.name = "label"
        return out.astype({"n": int})

    @property
    def prompt_sensitivity(self) -> pd.DataFrame:
        s = self.scores
        paraphrase = [p.startswith(t + VARIANT_SEP) for p, t in zip(s.probe, s.task)]
        s = s[(s.probe == s.task) | pd.Series(paraphrase, index=s.index)]               # task and its paraphrases
        s = s.assign(template=s["template"].fillna("custom"))
        table = s.pivot_table(index="task", columns="template", values="correct", aggfunc="mean")
        table = table.loc[[p for p in (*STEP_PROBES, "E2E") if p in table.index]]
        variants = list(table.columns)
        table.columns.name = None
        table["mean"] = table[variants].mean(axis=1)
        table["sd"] = table[variants].std(axis=1) if len(variants) > 1 else float("nan")
        table["range"] = table[variants].max(axis=1) - table[variants].min(axis=1)
        return table

    def save(self, directory: str | Path | None = None) -> Path:
        """Write every view as CSV (and the scores) to `directory` (default: the evaluation's output_dir)."""
        out = Path(directory or self.output_dir or ".")
        out.mkdir(parents=True, exist_ok=True)
        self.general.to_csv(out / "general.csv")
        self.steps.to_csv(out / "steps.csv")
        self.by_calculator.to_csv(out / "by_calculator.csv", index=False)
        self.examples.to_csv(out / "examples.csv", index=False)
        self.consistency.to_csv(out / "consistency.csv")
        self.prompt_sensitivity.to_csv(out / "prompt_sensitivity.csv")
        self.by_label.to_csv(out / "by_label.csv")
        self.scores.drop(columns=["verdict"], errors="ignore").to_csv(out / "scores.csv", index=False)
        return out


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("_") or "model"


def evaluate_model(model: Any, output_dir: str | Path | None = None, *, dataset: MedCalcDataset | None = None,
                   split: str | Iterable[str] = "test", per_calculator: int | None = None, seed: int = 0,
                   steps: Iterable[str] = STEP_PROBES, k_mode: str = "patient", k_pool: Any = "auto",
                   probe_options: Mapping[str, Mapping[str, Any]] | None = None,
                   prompt_variants: int | Iterable[str] = 1, batch_size: int = 8,
                   model_id: str | None = None, scoring: dict[str, dict[str, Any]] | None = None,
                   items: pd.DataFrame | None = None) -> EvaluationReport:
    """Evaluate a model on MedCalc-Bench: the general score (end to end, all calculators) and the score of each step
    (E, K, S, A on the equation-based calculators). Returns an EvaluationReport.

    model:          what `run_items` accepts: an object with `generate_batch` or `generate` (e.g. HFBackend), or a
                    function `generate(messages, max_new_tokens)`. None: only score generations already saved.
    output_dir:     where items, generations and the report go (default: medcalc_eval/<model id>). Generations are
                    appended as they come: the same call resumes an interrupted run.
    dataset:        default: MedCalc-Bench-Verified at the pinned revision (`mk.load()`), all 55 calculators.
    split:          the split(s) evaluated ("test", or your own, e.g. "dev" made with ds.split_off); per_calculator:
                    evaluate only that many examples per calculator (random, `seed`), to try a model quickly.
    steps:          the step probes to run (default all four; () for the general score only).
    k_mode:         "patient" (the model sees the values, writes the formula of its branch) or "general".
    k_pool:         patients used as K test points; "auto": the "train" examples that do not leak into the
                    evaluated split(s) (`usable_train_pool`), if any; None: perturbations.
    probe_options:  build options per probe, e.g. {"E2E": {"max_new_tokens": 4096}} (see ProbeSuite).
    prompt_variants: how many wordings of each prompt to use (1 to 3: "v1" is the default, "v2" and "v3" are
                    paraphrases with the same information and format), or their names. The views use the first one;
                    `report.prompt_sensitivity` compares them. Each variant multiplies the number of generations.
    batch_size, model_id: passed to run_items; scoring: passed to score_records.
    items:          items already built (e.g. ProbeSuite variants labelled "Kg", or read_items): evaluated as they
                    are, without building any; split, per_calculator, steps, k_mode, k_pool, probe_options and
                    prompt_variants then do not apply. Calculator categories come from `dataset` when given.

    >>> def always_12(messages, max_new_tokens):
    ...     return '{"answer": 12, "result": 12}'
    >>> import tempfile
    >>> report = evaluate_model(always_12, tempfile.mkdtemp(), dataset=mk.data.demo(), split="demo", steps=())
    >>> float(report.general.loc["all", "accuracy"])           # right for the anion gap only
    0.25
    """
    if items is not None:
        return _evaluate_items(model, items, output_dir, dataset, batch_size, model_id, scoring)
    ds = dataset if dataset is not None else load()
    examples = ds.filter(split=split)
    if not len(examples):
        raise ValueError(f"no example in split {split!r}")
    if per_calculator:
        examples = examples.sample(per_calculator, seed=seed, per_calculator=True)
    steps = tuple(steps)
    specs: dict[str, dict[str, Any]] = {p: {} for p in steps}
    if "K" in specs:
        specs["K"] = {"mode": k_mode}
    specs["E2E"] = {}
    for label, opts in (probe_options or {}).items():
        specs[label] = {**specs.get(label, {}), **opts}
    variants = [f"v{i + 1}" for i in range(prompt_variants)] if isinstance(prompt_variants, int) \
        else list(prompt_variants)
    unknown = set(variants) - {"v1", "v2", "v3"}
    if not variants or unknown:
        raise ValueError(f"prompt_variants: 1 to 3, or names among v1, v2, v3 (got {sorted(unknown) or variants})")
    if len(variants) > 1 or variants[0] != "v1":
        for label in list(specs):
            if "template" in specs[label]:
                raise ValueError(f"probe {label!r} has its own template: it cannot also use prompt variants")
            base = specs[label]
            specs[label] = {**base, "template": variants[0]}
            for name in variants[1:]:
                specs[f"{label}{VARIANT_SEP}{name}"] = {**base, "task": base.get("task", label), "template": name}
    pool = None
    evaluated = [split] if isinstance(split, str) else list(split)
    if steps and isinstance(k_pool, str) and k_pool == "auto":
        if "train" in set(ds.df["split"]) and "train" not in evaluated:
            pool = usable_train_pool(ds, test=evaluated)
    elif k_pool is not None and not isinstance(k_pool, str):
        pool = k_pool
    equation = ds.equation_only()
    suite = ProbeSuite(specs, schema=equation if len(equation) else None, k_pool=pool, seed=seed)
    items = suite.build(examples)

    return _evaluate_items(model, items, output_dir, examples, batch_size, model_id, scoring)


def _evaluate_items(model: Any, items: pd.DataFrame, output_dir: str | Path | None,
                    examples: MedCalcDataset | None, batch_size: int, model_id: str | None,
                    scoring: dict[str, dict[str, Any]] | None) -> EvaluationReport:
    items = items_frame(items)
    model_id = model_id or (model_name(model) if model is not None else "model")
    out = Path(output_dir) if output_dir is not None else Path("medcalc_eval") / _slug(model_id)
    write_items(items, out / "items")
    generations = out / "generations.jsonl"
    if model is not None:
        run_items(items, generations, model, model_id=model_id, batch_size=batch_size)
    scores = score_records(generations, items, condition={"model": model_id}, scoring=scoring, details=True)
    if scores.empty:
        raise ValueError(f"no generation to score in {generations}")
    names = dict(zip(items["example_id"], items["calculator_name"])) if "calculator_name" in items else {}
    category: dict[str, str] = {}
    if examples is not None:
        meta = examples.df.set_index("example_id")
        category = meta["Category"].to_dict()
        names = {**names, **meta["Calculator Name"].to_dict()}
    scores["calculator_category"] = scores.example_id.map(category).fillna("") if category else ""
    scores["calculator_name"] = scores.example_id.map(names)
    report = EvaluationReport(model_id, items, scores, out)
    report.save(out)
    return report
