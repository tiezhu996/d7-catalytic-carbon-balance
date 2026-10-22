"""反应进出口的摩尔流与选择性汇总。"""

from __future__ import annotations

from calibration import amount_ratio_from_area

INTERNAL_STANDARD = "N2"
PRODUCT_SPECIES = ("CO2", "CO", "CH4", "DME")
CARBON_NUMBER = {"methanol": 1, "CO2": 1, "CO": 1, "CH4": 1, "DME": 2}


def outlet_molar_flows(payload: dict) -> dict[str, float]:
    """根据出口峰面积和相对校准曲线计算各物种摩尔流量。"""
    n2_flow = float(payload["feed"]["internal_standard_mol_per_h"])
    peaks = payload["gc"]["outlet_peak_areas"]
    n2_area = float(peaks[INTERNAL_STANDARD])
    if n2_area <= 0.0:
        raise ValueError("internal standard peak area must be positive")

    calibration = payload["gc"]["calibrations"]
    amounts: dict[str, float] = {}
    for species, coefficients in calibration.items():
        area = float(peaks.get(species, 0.0))
        area_ratio = area / n2_area
        amount_ratio = amount_ratio_from_area(area_ratio, coefficients)
        amounts[species] = n2_flow * amount_ratio
    return amounts


def summarize_balance(payload: dict, outlet: dict[str, float]) -> dict:
    """计算转化率、碳平衡和各含碳产物的选择性。"""
    methanol_in = float(payload["feed"]["methanol_mol_per_h"])
    methanol_out = outlet.get("methanol", 0.0)
    products = {species: outlet.get(species, 0.0) for species in PRODUCT_SPECIES}
    carbon_products = sum(
        CARBON_NUMBER[species] * amount for species, amount in products.items()
    )
    carbon_out = CARBON_NUMBER["methanol"] * methanol_out + carbon_products
    converted = max(0.0, methanol_in - methanol_out)

    if carbon_products > 0.0:
        selectivity = {
            species: 100.0 * CARBON_NUMBER[species] * amount / carbon_products
            for species, amount in products.items()
        }
    else:
        selectivity = {species: 0.0 for species in PRODUCT_SPECIES}

    return {
        "conversion_percent": 100.0 * converted / methanol_in if methanol_in > 0.0 else 0.0,
        "carbon_balance_percent": 100.0 * carbon_out / methanol_in if methanol_in > 0.0 else 0.0,
        "selectivity_percent": selectivity,
        "methanol_converted_mol_per_h": converted,
    }
