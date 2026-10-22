"""把多次色谱记录整理成反应转化率与碳平衡。"""

from __future__ import annotations

from calibration import amount_ratio_from_area

CARBON_NUMBER = {"CO2": 1, "CO": 1, "CH4": 1, "DME": 2}


def run_summary(payload: dict, run: dict) -> dict:
    n2_flow = float(run["internal_standard_mol_per_s"])
    peaks = run["outlet_peak_areas"]
    n2_area = float(peaks["N2"])
    amounts = {}
    for species, coefficients in payload["gc_calibrations"].items():
        ratio = float(peaks.get(species, 0.0)) / n2_area
        amounts[species] = n2_flow * amount_ratio_from_area(ratio, coefficients)

    feed = float(run["feed_methanol_mol_per_s"])
    out_methanol = amounts.get("methanol", 0.0)
    conversion = max(0.0, min(0.999999, (feed - out_methanol) / feed))
    product_carbon = sum(
        CARBON_NUMBER[species] * amounts.get(species, 0.0) for species in CARBON_NUMBER
    )
    carbon_in = feed
    carbon_out = out_methanol + product_carbon
    return {
        "run_id": str(run["run_id"]),
        "temperature_k": float(run["temperature_k"]),
        "time_on_stream_h": float(run["time_on_stream_h"]),
        "inlet_methanol_concentration_mol_m3": float(run["inlet_methanol_concentration_mol_m3"]),
        "volumetric_expansion_factor": float(run["volumetric_expansion_factor"]),
        "feed_methanol_mol_per_s": feed,
        "catalyst_mass_g": float(run["catalyst_mass_g"]),
        "conversion": conversion,
        "carbon_balance_percent": 100.0 * carbon_out / carbon_in,
    }


def summarize_payload(payload: dict) -> list[dict]:
    return [run_summary(payload, run) for run in payload["runs"]]
