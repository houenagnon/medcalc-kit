"""Dosage conversions: steroid equivalents and morphine milligram equivalents."""
from __future__ import annotations

from medcalc_kit.calculators.registry import calculator, new_derivation

# Relative potency multipliers used by the benchmark (Dexamethasone = 1).
STEROID_MULTIPLIER = {
    "Betamethasone IV": 1, "Cortisone PO": 33.33, "Dexamethasone IV": 1, "Dexamethasone PO": 1,
    "Hydrocortisone IV": 26.67, "Hydrocortisone PO": 26.67, "MethylPrednisoLONE IV": 5.33,
    "MethylPrednisoLONE PO": 5.33, "PrednisoLONE PO": 6.67, "PredniSONE PO": 6.67,
    "Triamcinolone IV": 5.33,
}

MME_FACTOR = {
    "Codeine": 0.15, "FentaNYL buccal": 0.13, "FentANYL patch": 2.4, "HYDROcodone": 1,
    "HYDROmorphone": 5, "Methadone": 4.7, "Morphine": 1, "OxyCODONE": 1.5, "OxyMORphone": 3,
    "Tapentadol": 0.4, "TraMADol": 0.2, "Buprenorphine": 10,
}


@calculator("24", "Steroid Conversion Calculator")
def steroid_conversion(e):
    d = new_derivation("24")
    src_name, dose, unit = e["input steroid"]
    if unit != "mg":
        raise ValueError(f"unsupported steroid unit {unit!r}")
    tgt_name = e["target steroid"]
    d.inputs["dose"] = float(dose)
    d.coefficients.update(m_src=STEROID_MULTIPLIER[src_name], m_tgt=STEROID_MULTIPLIER[tgt_name])
    d.branches.append(f"{src_name}->{tgt_name}")
    d.step("target_dose", "dose * m_tgt / m_src")
    return d


@calculator("49", "Morphine Milligram Equivalents (MME) Calculator")
def mme(e):
    d = new_derivation("49")
    terms = []
    for key in e:
        if not key.endswith(" Dose"):
            continue
        drug = key[: -len(" Dose")]
        tag = "".join(ch for ch in drug.lower() if ch.isalnum())
        dose, unit = e[key]
        expected_unit = "µg" if drug.startswith("FentaNYL") or drug.startswith("FentANYL") else "mg"
        if unit != expected_unit:
            raise ValueError(f"unsupported unit {unit!r} for {drug}")
        d.inputs[f"dose_{tag}"] = float(dose)
        d.inputs[f"perday_{tag}"] = float(e[f"{drug} Dose Per Day"][0])
        d.coefficients[f"f_{tag}"] = MME_FACTOR[drug]
        terms.append(f"dose_{tag} * perday_{tag} * f_{tag}")
    d.step("mme", " + ".join(terms))
    return d
