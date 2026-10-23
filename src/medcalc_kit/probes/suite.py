"""Build the items of several probes for a set of examples, with the context each probe needs.

    >>> suite = ProbeSuite(["S", "A"])
    >>> items = suite.build(mk.data.demo())
    >>> items[["item_id", "probe", "example_id"]].head(3)
          item_id probe example_id
    0  demo:2:1:S     S   demo:2:1
    1  demo:6:1:S     S   demo:6:1
    2 demo:39:1:S     S  demo:39:1
"""
from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import pandas as pd

from medcalc_kit.calculators import CALCULATORS, derive
from medcalc_kit.data import Example, MedCalcDataset, as_example
from medcalc_kit.probes import arithmetic, end_to_end, extraction, knowledge, substitution
from medcalc_kit.probes.common import Item, as_items, items_frame

ALL_PROBES = ("E", "K", "S", "A", "E2E")
# Probes of the steps of a calculation: they need the registry, so they cover the 33 equation-based calculators.
STEP_PROBES = ("E", "K", "S", "A")
_MODULES = {"E": extraction, "K": knowledge, "S": substitution, "A": arithmetic, "E2E": end_to_end}


def _frame(data) -> pd.DataFrame | None:
    if data is None:
        return None
    return data.df if isinstance(data, MedCalcDataset) else data


class ProbeSuite:
    """Builds the items of several probes at once, giving each probe the context it needs.

    E2E items are built for every example of the benchmark. The step probes (E, K, S, A) need the reference
    computation, so they are built only for the 33 equation-based calculators of the registry; other examples
    (rule-based scores, dates) get E2E only.

    probes:  probe names ("E", "K", "S", "A", "E2E"), or {label: options} where options are keyword arguments of
             that probe's build() plus an optional "task" (the probe to use; default: the label). Labels let you
             build several variants of a probe, e.g.
                 {"K": {"mode": "patient", "max_new_tokens": 1536}, "Kg": {"task": "K", "mode": "general"}}
    schema:  examples used to infer the E field list per calculator (use the whole dataset, train + test,
             so that optional fields are asked consistently). Default: the examples being built.
    k_pool:  patients used as K test points (MedCalcDataset or DataFrame, e.g. a leakage-free train pool),
             shuffled per calculator with `seed`. Default: perturbations of the patient at scoring time.

    >>> ProbeSuite().probes                                   # every probe, default options
    ['E', 'K', 'S', 'A', 'E2E']
    >>> suite = ProbeSuite({"K": {"mode": "patient"}, "Kg": {"task": "K"}, "A": {"max_new_tokens": 512}})
    >>> items = suite.build(mk.data.demo())
    >>> items.groupby("probe", sort=False).max_new_tokens.first().to_dict()
    {'K': 1024, 'Kg': 1024, 'A': 512}
    >>> ProbeSuite(["X"])
    Traceback (most recent call last):
    ...
    ValueError: unknown probe 'X' for label 'X' (available: E, K, S, A, E2E)
    """

    def __init__(self, probes: Iterable[str] | Mapping[str, Mapping[str, Any]] = ALL_PROBES, *, schema=None,
                 k_pool=None, seed: int = 0):
        if isinstance(probes, str):
            probes = [probes]
        specs = dict(probes) if isinstance(probes, Mapping) else {p: {} for p in probes}
        self.specs: dict[str, dict[str, Any]] = {}
        for label, opts in specs.items():
            opts = dict(opts)
            task = opts.pop("task", label)
            if task not in _MODULES:
                raise ValueError(f"unknown probe {task!r} for label {label!r} (available: {', '.join(_MODULES)})")
            self.specs[label] = {"task": task, **opts}
        self.probes = list(self.specs)
        self._schema = schema
        self.k_points: dict[str, list[dict[str, Any]]] = {}
        pool = _frame(k_pool)
        if pool is not None:  # a full permutation per calculator; probes take what they need from its head
            self.k_points = {cid: g.sample(frac=1, random_state=seed)["entities"].tolist()
                             for cid, g in pool.groupby("Calculator ID")}

    def build(self, examples: MedCalcDataset | pd.DataFrame | Iterable[Example | dict[str, Any]], check: bool = True,
              as_frame: bool = True) -> pd.DataFrame | dict[str, list[Item]]:
        """One row per item (see probes.items_frame), label by label, each in the order of `examples`
        (as_frame=False: {label: [item, ...]}). check=True asserts that the resolved branch formula used by S and A
        reproduces the registry answer.

        examples: a MedCalcDataset, a DataFrame of dataset rows, or Examples / row dicts.

        >>> items = ProbeSuite("E2E").build(mk.data.demo())
        >>> list(items.columns)
        ['item_id', 'probe', 'example_id', 'calculator_id', 'calculator_name', 'template', 'template_hash',
         'max_new_tokens', 'messages', 'reference']
        >>> {k: round(v, 2) for k, v in items.loc[0, "reference"].items() if k != "answer_type"}
        {'ground_truth': 79.88, 'lower': 75.89, 'upper': 83.88}
        >>> list(ProbeSuite("E2E").build(mk.data.demo(), as_frame=False))
        ['E2E']
        """
        if isinstance(examples, pd.DataFrame):
            examples = (row for _, row in examples.iterrows())
        exs = [as_example(e) for e in examples]
        fields = extraction.calculator_fields(self._schema if self._schema is not None else exs)
        out: dict[str, list[Item]] = {}
        for label, spec in self.specs.items():
            opts = {k: v for k, v in spec.items() if k != "task"}
            task = spec["task"]
            build = _MODULES[task].build
            items = []
            for ex in exs:
                if task != "E2E" and ex.calculator_id not in CALCULATORS:
                    continue                                  # step probes need the registry
                if task == "E":
                    e_opts = {k: v for k, v in opts.items() if k != "fields"}
                    item = build(ex, opts.get("fields") or fields.get(ex.calculator_id), label=label, **e_opts)
                elif task == "K":
                    item = build(ex, self.k_points.get(ex.calculator_id), label=label, **opts)
                else:
                    item = build(ex, label=label, **opts)
                if check and task in ("S", "A"):
                    ans = derive(ex.calculator_id, ex.entities).answer
                    gv = item["reference"]["gold_value"]
                    assert abs(gv - ans) <= 1e-4 * max(abs(ans), 1), (item["item_id"], gv, ans)
                items.append(item)
            out[label] = items
        return items_frame(out) if as_frame else out


def write_items(items: pd.DataFrame | list[Item] | dict[str, list[Item]], directory: str | Path) -> dict[str, int]:
    """Save items as one JSONL file per probe label (<directory>/<label>.jsonl). Returns the counts per label.

    >>> import tempfile
    >>> folder = tempfile.mkdtemp()
    >>> write_items(ProbeSuite(["S", "A"]).build(mk.data.demo()), folder)
    {'S': 4, 'A': 4}
    """
    out = Path(directory)
    out.mkdir(parents=True, exist_ok=True)
    items_by_probe: dict[str, list[Item]] = {}
    for it in as_items(items):
        items_by_probe.setdefault(it["probe"], []).append(it)
    for probe, items in items_by_probe.items():
        with open(out / f"{probe}.jsonl", "w") as f:
            for it in items:
                f.write(json.dumps(it, ensure_ascii=False) + "\n")
    return {p: len(v) for p, v in items_by_probe.items()}


def read_items(directory: str | Path, probes: Iterable[str] | None = None,
               as_frame: bool = True) -> pd.DataFrame | list[Item]:
    """Load items saved by `write_items`: the given probe labels (default: every <label>.jsonl in the directory),
    one row per item (as_frame=False: a list of dicts).

    >>> import tempfile
    >>> folder = tempfile.mkdtemp()
    >>> _ = write_items(ProbeSuite(["S", "A"]).build(mk.data.demo()), folder)
    >>> read_items(folder).groupby("probe").size().to_dict()
    {'A': 4, 'S': 4}
    >>> len(read_items(folder, probes=["S"]))
    4
    """
    d = Path(directory)
    paths = [d / f"{p}.jsonl" for p in probes] if probes is not None else sorted(d.glob("*.jsonl"))
    items = []
    for path in paths:
        if path.exists():
            items += [json.loads(line) for line in open(path)]
    return items_frame(items) if as_frame else items
