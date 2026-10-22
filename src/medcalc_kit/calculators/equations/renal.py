"""Kidney function: Cockcroft-Gault, CKD-EPI 2021, MDRD, FENa."""
from __future__ import annotations

from medcalc_kit.calculators.equations.anthropometry import ibw_steps
from medcalc_kit.calculators.registry import calculator, is_male, new_derivation
from medcalc_kit.units import age_years, concentration, height_cm, weight_kg


@calculator("2", "Creatinine Clearance (Cockcroft-Gault Equation)")
def cockcroft_gault(e):
    d = new_derivation("2")
    male = is_male(e)
    d.inputs.update(
        age=age_years(e["age"]),
        weight=weight_kg(e["weight"]),
        height=height_cm(e["height"]),
        scr=concentration(e["creatinine"][0], e["creatinine"][1], "creatinine", "mg/dL"),
    )
    d.coefficients["k_sex"] = 1.0 if male else 0.85
    d.step("bmi", "weight / (height / 100)^2")
    ibw_steps(d, male)
    # Benchmark convention stated in the question: underweight -> actual weight;
    # normal BMI -> min(IBW, actual); overweight/obese -> adjusted body weight.
    b = d.env["bmi"]
    if b < 18.5:
        d.branches.append("bmi<18.5:actual")
        d.step("dosing_weight", "weight")
    elif b <= 24.9:
        d.branches.append("18.5<=bmi<=24.9:min(ibw,actual)")
        d.step("dosing_weight", "min(ibw, weight)")
    else:
        d.branches.append("bmi>24.9:abw")
        d.step("dosing_weight", "ibw + 0.4 * (weight - ibw)")
    d.step("crcl", "((140 - age) * dosing_weight * k_sex) / (72 * scr)")
    return d


@calculator("3", "CKD-EPI Equations for Glomerular Filtration Rate")
def ckd_epi_2021(e):
    d = new_derivation("3")
    male = is_male(e)
    scr = concentration(e["creatinine"][0], e["creatinine"][1], "creatinine", "mg/dL")
    d.inputs.update(age=age_years(e["age"]), scr=scr)
    if male:
        kappa, alpha = (0.9, -0.302) if scr <= 0.9 else (0.9, -1.2)
    else:
        kappa, alpha = (0.7, -0.241) if scr <= 0.7 else (0.7, -1.2)
    d.branches.append(f"{'male' if male else 'female'}:scr{'<=' if alpha != -1.2 else '>'}kappa")
    d.coefficients.update(kappa=kappa, alpha=alpha, k_sex=1.0 if male else 1.012)
    d.step("egfr", "142 * (scr / kappa)^alpha * 0.9938^age * k_sex")
    return d


@calculator("9", "MDRD GFR Equation")
def mdrd(e):
    d = new_derivation("9")
    d.inputs.update(
        age=age_years(e["age"]),
        scr=concentration(e["creatinine"][0], e["creatinine"][1], "creatinine", "mg/dL"),
    )
    d.coefficients.update(
        k_sex=1.0 if is_male(e) else 0.742,
        k_race=1.212 if e.get("Race") == "Black" else 1.0,
    )
    d.step("egfr", "175 * scr^(-1.154) * age^(-0.203) * k_sex * k_race")
    return d


@calculator("40", "Fractional Excretion of Sodium (FENa)")
def fena(e):
    d = new_derivation("40")
    d.inputs.update(
        scr=concentration(*e["creatinine"], "creatinine", "mg/dL"),
        ucr=concentration(*e["Urine creatinine"], "creatinine", "mg/dL"),
        sna=concentration(*e["Sodium"], "sodium", "mEq/L"),
        una=concentration(*e["Urine sodium"], "sodium", "mEq/L"),
    )
    d.step("fena", "(scr * una) / (sna * ucr) * 100")
    return d
