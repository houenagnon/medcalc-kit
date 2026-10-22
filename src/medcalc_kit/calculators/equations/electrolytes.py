"""Electrolytes and acid-base: anion gap family, calcium and sodium corrections, osmolality, free water deficit."""
from __future__ import annotations

from medcalc_kit.calculators.registry import Derivation, calculator, is_male, new_derivation
from medcalc_kit.units import age_years, concentration, weight_kg


def _anion_gap_inputs(d: Derivation, e) -> None:
    d.inputs.update(
        na=concentration(*e["Sodium"], "sodium", "mEq/L"),
        cl=concentration(*e["Chloride"], "chloride", "mEq/L"),
        hco3=concentration(*e["Bicarbonate"], "bicarbonate", "mEq/L"),
    )


def _albumin(e) -> float:
    return concentration(*e["Albumin"], "albumin", "g/dL")


@calculator("39", "Anion Gap")
def anion_gap(e):
    d = new_derivation("39")
    _anion_gap_inputs(d, e)
    d.step("ag", "na - (cl + hco3)")
    return d


@calculator("63", "Delta Gap")
def delta_gap(e):
    d = new_derivation("63")
    _anion_gap_inputs(d, e)
    d.step("ag", "na - (cl + hco3)")
    d.step("delta_gap", "ag - 12")
    return d


@calculator("64", "Delta Ratio")
def delta_ratio(e):
    d = new_derivation("64")
    _anion_gap_inputs(d, e)
    d.step("ag", "na - (cl + hco3)")
    d.step("delta_ratio", "(ag - 12) / (24 - hco3)")
    return d


@calculator("65", "Albumin Corrected Anion Gap")
def albumin_corrected_ag(e):
    d = new_derivation("65")
    _anion_gap_inputs(d, e)
    d.inputs["albumin"] = _albumin(e)
    d.step("ag", "na - (cl + hco3)")
    d.step("ag_corr", "ag + 2.5 * (4 - albumin)")
    return d


@calculator("66", "Albumin Corrected Delta Gap")
def albumin_corrected_delta_gap(e):
    d = new_derivation("66")
    _anion_gap_inputs(d, e)
    d.inputs["albumin"] = _albumin(e)
    d.step("ag", "na - (cl + hco3)")
    d.step("ag_corr", "ag + 2.5 * (4 - albumin)")
    d.step("delta_gap_corr", "ag_corr - 12")
    return d


@calculator("67", "Albumin Corrected Delta Ratio")
def albumin_corrected_delta_ratio(e):
    d = new_derivation("67")
    _anion_gap_inputs(d, e)
    d.inputs["albumin"] = _albumin(e)
    d.step("ag", "na - (cl + hco3)")
    d.step("ag_corr", "ag + 2.5 * (4 - albumin)")
    d.step("delta_ratio_corr", "(ag_corr - 12) / (24 - hco3)")
    return d


@calculator("7", "Calcium Correction for Hypoalbuminemia")
def calcium_correction(e):
    d = new_derivation("7")
    d.inputs.update(ca=concentration(*e["Calcium"], "calcium", "mg/dL"), albumin=_albumin(e))
    d.coefficients["albumin_normal"] = 4.0  # stated in the benchmark question
    d.step("ca_corr", "ca + 0.8 * (albumin_normal - albumin)")
    return d


@calculator("26", "Sodium Correction for Hyperglycemia")
def sodium_correction(e):
    d = new_derivation("26")
    d.inputs.update(
        na=concentration(*e["Sodium"], "sodium", "mEq/L"),
        glucose=concentration(*e["Glucose"], "glucose", "mg/dL"),
    )
    d.step("na_corr", "na + 0.024 * (glucose - 100)")  # Hillier
    return d


@calculator("30", "Serum Osmolality")
def serum_osmolality(e):
    d = new_derivation("30")
    d.inputs.update(
        na=concentration(*e["Sodium"], "sodium", "mmol/L"),
        bun=concentration(*e["Blood Urea Nitrogen (BUN)"], "bun", "mg/dL"),
        glucose=concentration(*e["Glucose"], "glucose", "mg/dL"),
    )
    d.step("osm", "2 * na + bun / 2.8 + glucose / 18")
    return d


@calculator("38", "Free Water Deficit")
def free_water_deficit(e):
    d = new_derivation("38")
    age = age_years(e["age"])
    male = is_male(e)
    d.inputs.update(
        age=age,
        weight=weight_kg(e["weight"]),
        na=concentration(*e["Sodium"], "sodium", "mmol/L"),
    )
    if age < 18:
        tbw, branch = 0.6, "child"
    elif age < 65:
        tbw, branch = (0.6, "adult_male") if male else (0.5, "adult_female")
    else:
        tbw, branch = (0.5, "elderly_male") if male else (0.45, "elderly_female")
    d.branches.append(branch)
    d.coefficients["tbw_fraction"] = tbw
    d.step("fwd", "tbw_fraction * weight * (na / 140 - 1)")
    return d
