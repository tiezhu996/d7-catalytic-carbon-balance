"""催化剂活性指标。"""

from __future__ import annotations


def turnover_frequency(converted_mol_per_h: float, catalyst: dict) -> float:
    """按活性金属摩尔数计算转换频率。"""
    bed_mass_g = float(catalyst["catalyst_mass_g"]) + float(catalyst["diluent_mass_g"])
    loading = float(catalyst["metal_loading_wt_percent"]) / 100.0
    metal_mol = bed_mass_g * loading / 63.546
    if metal_mol <= 0.0:
        raise ValueError("active metal amount must be positive")
    return converted_mol_per_h / 3600.0 / metal_mol
