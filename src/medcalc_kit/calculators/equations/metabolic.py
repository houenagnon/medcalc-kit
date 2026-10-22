"""Lipids, glucose metabolism and liver: LDL, HOMA-IR, FIB-4, MELD Na."""
from __future__ import annotations

from medcalc_kit.calculators.registry import calculator, new_derivation
from medcalc_kit.units import age_years, concentration, insulin_uIU_per_mL, platelets_1e9_per_L


@calculator("44", "LDL Calculated")
def ldl(e):
    d = new_derivation("44")
    d.inputs.update(
        tc=concentration(*e["Total cholesterol"], "cholesterol", "mg/dL"),
        hdl=concentration(*e["high-density lipoprotein cholesterol"], "cholesterol", "mg/dL"),
        tg=concentration(*e["Triglycerides"], "triglycerides", "mg/dL"),
    )
    d.step("ldl", "tc - hdl - tg / 5")  # Friedewald
    return d


@calculator("31", "HOMA-IR (Homeostatic Model Assessment for Insulin Resistance)")
def homa_ir(e):
    d = new_derivation("31")
    d.inputs.update(
        insulin=insulin_uIU_per_mL(e["Insulin"]),
        glucose=concentration(*e["Glucose"], "glucose", "mg/dL"),
    )
    d.step("homa_ir", "insulin * glucose / 405")
    return d


@calculator("19", "Fibrosis-4 (FIB-4) Index for Liver Fibrosis")
def fib4(e):
    d = new_derivation("19")
    d.inputs.update(
        age=age_years(e["age"]),
        ast=float(e["Aspartate aminotransferase"][0]),
        alt=float(e["Alanine aminotransferase"][0]),
        platelets=platelets_1e9_per_L(e["Platelet count"]),
    )
    d.step("fib4", "(age * ast) / (platelets * sqrt(alt))")
    return d


@calculator("23", "MELD Na (UNOS/OPTN)")
def meld_na(e):
    d = new_derivation("23")
    dialysis = bool(e.get("Dialysis at least twice in the past week")) or bool(
        e.get("Continuous veno-venous hemodialysis for ≥24 hours in the past week"))
    d.inputs.update(
        scr_raw=concentration(*e["creatinine"], "creatinine", "mg/dL"),
        bili_raw=concentration(*e["Bilirubin"], "bilirubin", "mg/dL"),
        inr_raw=float(e["international normalized ratio"]),
        na_raw=concentration(*e["Sodium"], "sodium", "mEq/L"),
    )
    if dialysis:
        d.branches.append("dialysis:scr=4")
        d.step("scr", "4")
    else:
        d.step("scr", "min(max(scr_raw, 1), 4)")
    d.step("bili", "max(bili_raw, 1)")
    d.step("inr", "max(inr_raw, 1)")
    d.step("na", "min(max(na_raw, 125), 137)")
    d.step("meld_i", "0.957 * ln(scr) + 0.378 * ln(bili) + 1.120 * ln(inr) + 0.643")
    d.step("meld", "round(round(meld_i, 1) * 10)")
    if d.env["meld"] > 11:
        d.branches.append("meld>11:na_adjusted")
        d.step("meld_na", "min(round(meld + 1.32 * (137 - na) - 0.033 * meld * (137 - na)), 40)")
    else:
        d.branches.append("meld<=11:no_na_adjustment")
        d.step("meld_na", "meld")
    return d
