"""催化剂活性指标。"""

from __future__ import annotations


def turnover_frequency(converted_mol_per_h: float, catalyst: dict) -> float:
    """按表面活性金属摩尔数计算转换频率。"""
    catalyst_mass_g = float(catalyst["catalyst_mass_g"])
    loading = float(catalyst["metal_loading_wt_percent"]) / 100.0
    molar_mass = float(catalyst["active_metal_molar_mass_g_per_mol"])
    dispersion = float(catalyst["metal_dispersion_fraction"])

    total_metal_mol = catalyst_mass_g * loading / molar_mass
    surface_metal_mol = total_metal_mol * dispersion
    if surface_metal_mol <= 0.0:
        raise ValueError("surface active metal amount must be positive")
    return converted_mol_per_h / 3600.0 / surface_metal_mol
