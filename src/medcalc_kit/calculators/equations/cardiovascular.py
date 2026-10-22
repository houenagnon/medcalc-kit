"""Cardiovascular: Framingham risk score and QTc corrections (RR in seconds)."""
from __future__ import annotations

from medcalc_kit.calculators.registry import Derivation, calculator, is_male, new_derivation
from medcalc_kit.units import age_years, concentration


@calculator("46", "Framingham Risk Score for Hard Coronary Heart Disease")
def framingham(e):
    d = new_derivation("46")
    male = is_male(e)
    age = age_years(e["age"])
    d.inputs.update(
        age=age,
        tc=concentration(*e["Total cholesterol"], "cholesterol", "mg/dL"),
        hdl=concentration(*e["high-density lipoprotein cholesterol"], "cholesterol", "mg/dL"),
        sbp=float(e["Systolic Blood Pressure"][0]),
        smoker=1.0 if e.get("Smoker") else 0.0,
        bp_treated=1.0 if e.get("Blood pressure being treated with medicines") else 0.0,
    )
    if male:
        d.branches.append("male")
        d.coefficients.update(age_smoke_cap=70, s0=0.9402)
        d.step("age_smoke", "min(age, age_smoke_cap)")
        d.step("lp", "52.00961 * ln(age) + 20.014077 * ln(tc) - 0.905964 * ln(hdl) + 1.305784 * ln(sbp)"
                     " + 0.241549 * bp_treated + 12.096316 * smoker - 4.605038 * ln(age) * ln(tc)"
                     " - 2.84367 * ln(age_smoke) * smoker - 2.93323 * ln(age) * ln(age) - 172.300168")
    else:
        d.branches.append("female")
        d.coefficients.update(age_smoke_cap=78, s0=0.98767)
        d.step("age_smoke", "min(age, age_smoke_cap)")
        d.step("lp", "31.764001 * ln(age) + 22.465206 * ln(tc) - 1.187731 * ln(hdl) + 2.552905 * ln(sbp)"
                     " + 0.420251 * bp_treated + 13.07543 * smoker - 5.060998 * ln(age) * ln(tc)"
                     " - 2.996945 * ln(age_smoke) * smoker - 146.5933061")
    d.step("risk_pct", "(1 - s0^exp(lp)) * 100")
    return d


# ---------------------------------------------------------------- QTc (RR in seconds)

def _qt_inputs(d: Derivation, e) -> None:
    d.inputs.update(hr=float(e["Heart Rate or Pulse"][0]), qt=float(e["QT Interval"][0]))
    d.step("rr", "60 / hr")


@calculator("11", "QTc Bazett Calculator")
def qtc_bazett(e):
    d = new_derivation("11"); _qt_inputs(d, e)
    d.step("qtc", "qt / sqrt(rr)")
    return d


@calculator("56", "QTc Fridericia Calculator")
def qtc_fridericia(e):
    d = new_derivation("56"); _qt_inputs(d, e)
    d.step("qtc", "qt / rr^(1/3)")
    return d


@calculator("57", "QTc Framingham Calculator")
def qtc_framingham(e):
    d = new_derivation("57"); _qt_inputs(d, e)
    d.step("qtc", "qt + 154 * (1 - rr)")
    return d


@calculator("58", "QTc Hodges Calculator")
def qtc_hodges(e):
    d = new_derivation("58"); _qt_inputs(d, e)
    d.step("qtc", "qt + 1.75 * (hr - 60)")
    return d


@calculator("59", "QTc Rautaharju Calculator")
def qtc_rautaharju(e):
    d = new_derivation("59")
    d.inputs.update(hr=float(e["Heart Rate or Pulse"][0]), qt=float(e["QT Interval"][0]))
    d.step("qtc", "qt * (120 + hr) / 180")
    return d
