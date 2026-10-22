"""Body size, fluids and blood pressure: BMI, BSA, ideal/adjusted/target weight, maintenance fluids, MAP."""
from __future__ import annotations

from medcalc_kit.calculators.registry import Derivation, calculator, is_male, new_derivation
from medcalc_kit.units import height_cm, weight_kg


@calculator("6", "Body Mass Index (BMI)")
def bmi(e):
    d = new_derivation("6")
    d.inputs.update(weight=weight_kg(e["weight"]), height=height_cm(e["height"]))
    d.step("bmi", "weight / (height / 100)^2")
    return d


@calculator("60", "Body Surface Area Calculator")
def bsa(e):
    d = new_derivation("60")
    d.inputs.update(weight=weight_kg(e["weight"]), height=height_cm(e["height"]))
    d.step("bsa", "sqrt(weight * height / 3600)")  # Mosteller, height in cm
    return d


def ibw_steps(d: Derivation, male: bool) -> None:
    d.step("height_in", "height / 2.54")
    d.step("ibw", "50 + 2.3 * (height_in - 60)" if male else "45.5 + 2.3 * (height_in - 60)")
    d.branches.append("ibw:male" if male else "ibw:female")


@calculator("10", "Ideal Body Weight")
def ideal_body_weight(e):
    d = new_derivation("10")
    d.inputs.update(height=height_cm(e["height"]))
    ibw_steps(d, is_male(e))
    return d


@calculator("62", "Adjusted Body Weight")
def adjusted_body_weight(e):
    d = new_derivation("62")
    d.inputs.update(weight=weight_kg(e["weight"]), height=height_cm(e["height"]))
    ibw_steps(d, is_male(e))
    d.step("abw", "ibw + 0.4 * (weight - ibw)")
    return d


@calculator("61", "Target weight")
def target_weight(e):
    d = new_derivation("61")
    d.inputs.update(target_bmi=float(e["Body Mass Index (BMI)"][0]), height=height_cm(e["height"]))
    d.step("target_weight", "target_bmi * (height / 100)^2")
    return d


@calculator("22", "Maintenance Fluids Calculations")
def maintenance_fluids(e):
    d = new_derivation("22")
    d.inputs.update(weight=weight_kg(e["weight"]))
    w = d.inputs["weight"]
    if w < 10:
        d.branches.append("weight<10")
        d.step("rate", "4 * weight")
    elif w <= 20:
        d.branches.append("10<=weight<=20")
        d.step("rate", "40 + 2 * (weight - 10)")
    else:
        d.branches.append("weight>20")
        d.step("rate", "60 + (weight - 20)")
    return d


@calculator("5", "Mean Arterial Pressure (MAP)")
def mean_arterial_pressure(e):
    d = new_derivation("5")
    d.inputs.update(sbp=float(e["Systolic Blood Pressure"][0]), dbp=float(e["Diastolic Blood Pressure"][0]))
    d.step("map", "sbp / 3 + 2 * dbp / 3")
    return d
