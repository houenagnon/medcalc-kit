"""Verify the calculator registry against MedCalc-Bench-Verified ground truth.

For every equation-based example the registry recomputes the answer from the annotated entities and
compares it with the ground truth interval. Disagreements point to a registry bug, an undocumented
benchmark convention, or an annotation / ground-truth error.

Usage:
    python -m medcalc_kit.calculators.verify [--revision SHA] [--out registry_verification]
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

from medcalc_kit.calculators.registry import CALCULATORS, KNOWN_REFERENCE_DEVIATIONS, derive
from medcalc_kit.data.dataset import DATASET_ID


def check_row(row) -> dict[str, Any]:
    """Registry value, branches and agreement with the ground truth for one dataset row.

    >>> r = check_row(mk.data.demo().df.iloc[2])
    >>> r["registry_value"], r["within_bounds"], r["error"]
    (12.0, True, None)
    """
    out = {
        "example_id": row["example_id"],
        "split": row["split"],
        "calculator_id": row["Calculator ID"],
        "calculator_name": row["Calculator Name"],
        "note_id": row["Note ID"],
        "note_type": row["Note Type"],
        "ground_truth": float(row["Ground Truth Answer"]),
        "lower": float(row["Lower Limit"]),
        "upper": float(row["Upper Limit"]),
    }
    try:
        d = derive(row["Calculator ID"], row["entities"])
        value = d.answer
        out.update(registry_value=value, branches="|".join(d.branches), inputs=json.dumps(d.inputs), error=None)
    except Exception as exc:  # noqa: BLE001 - every failure is reported, none is silent
        out.update(registry_value=math.nan, branches="", inputs="", error=f"{type(exc).__name__}: {exc}")
        return {**out, "within_bounds": False, "rel_error": math.nan}
    lo, hi = sorted((out["lower"], out["upper"]))
    gt = out["ground_truth"]
    out["within_bounds"] = bool(lo - 1e-9 <= value <= hi + 1e-9)
    out["rel_error"] = abs(value - gt) / abs(gt) if gt != 0 else abs(value)
    return out


def verify(data) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(per-example table, per-calculator x split summary) for a MedCalcDataset or DataFrame.

    >>> per_example, summary = verify(mk.data.demo())
    >>> summary[["calculator_id", "n", "within_bounds"]]
      calculator_id  n  within_bounds
    0             2  1            1.0
    1            39  1            1.0
    2             5  1            1.0
    3             6  1            1.0
    """
    df = data.df if hasattr(data, "df") else data
    missing = sorted(set(df["Calculator ID"]) - set(CALCULATORS))
    if missing:
        raise ValueError(f"calculators without registry entry: {missing}")
    res = pd.DataFrame([check_row(r) for _, r in df.iterrows()])
    summary = (
        res.groupby(["calculator_id", "calculator_name", "split"])
        .agg(n=("example_id", "size"),
             within_bounds=("within_bounds", "mean"),
             n_fail=("within_bounds", lambda s: int((~s).sum())),
             n_exceptions=("error", lambda s: int(s.notna().sum())),
             median_rel_error=("rel_error", "median"),
             max_rel_error=("rel_error", "max"))
        .reset_index()
        .sort_values(["split", "within_bounds", "calculator_id"])
    )
    return res, summary


def main() -> None:
    """Command line: `python -m medcalc_kit.calculators.verify [--revision SHA] [--out DIR]`."""
    from medcalc_kit.data import dataset_revision, load

    ap = argparse.ArgumentParser()
    ap.add_argument("--revision", default=None, help="dataset commit SHA (default: current main)")
    ap.add_argument("--out", default="registry_verification")
    args = ap.parse_args()

    revision = args.revision or dataset_revision()
    res, summary = verify(load(revision, equation_only=True))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    res.to_csv(out / "per_example.csv", index=False)
    summary.to_csv(out / "summary.csv", index=False)
    res[~res["within_bounds"]].to_csv(out / "mismatches.csv", index=False)
    (out / "metadata.json").write_text(json.dumps({
        "dataset": DATASET_ID, "revision": revision, "n_examples": len(res),
        "known_reference_deviations": KNOWN_REFERENCE_DEVIATIONS,
    }, indent=2))

    pd.set_option("display.width", 200, "display.max_rows", 200)
    print(f"dataset revision: {revision}")
    for split in ("test", "train"):
        s = res[res["split"] == split]
        print(f"\n[{split}] {len(s)} examples, within bounds: {s['within_bounds'].mean():.4f}, "
              f"exceptions: {s['error'].notna().sum()}")
    print("\nPer-calculator (test split):")
    print(summary[summary["split"] == "test"].drop(columns="split").to_string(index=False))
    print("\nCalculators with any train mismatch:")
    tr = summary[(summary["split"] == "train") & (summary["n_fail"] > 0)]
    print(tr.drop(columns="split").to_string(index=False))


if __name__ == "__main__":
    main()
