"""积分固定床反应器的速率计算。"""

from __future__ import annotations

import math

from deactivation import activity_factor

R_GAS = 8.314462618
REFERENCE_TEMPERATURE_K = 623.15
REFERENCE_CONCENTRATION = 100.0


def reaction_rate(conversion: float, run: dict, parameters: list[float], model: str) -> float:
    reference_rate = math.exp(parameters[0])
    activation_energy = parameters[1]
    order = parameters[2]
    deactivation_constant = math.exp(parameters[3])

    inlet = run["inlet_methanol_concentration_mol_m3"]
    expansion = run["volumetric_expansion_factor"]
    concentration = inlet * (1.0 - conversion) / (1.0 + expansion * conversion)
    arrhenius = math.exp(
        -activation_energy * 1000.0
        / R_GAS
        * (1.0 / run["temperature_k"] - 1.0 / REFERENCE_TEMPERATURE_K)
    )
    decay = activity_factor(run["time_on_stream_h"], deactivation_constant, model)
    return (
        reference_rate
        * arrhenius
        * decay
        * (max(concentration, 1e-18) / REFERENCE_CONCENTRATION) ** order
    )


def reactor_modulus(conversion: float, run: dict, parameters: list[float], model: str) -> float:
    """按活塞流设计方程计算 W/F_A0。"""
    if conversion <= 0.0:
        return 0.0
    intervals = 24
    step = conversion / intervals
    total = 0.0
    for index in range(intervals + 1):
        x = index * step
        weight = 1.0 if index in (0, intervals) else (4.0 if index % 2 else 2.0)
        rate = reaction_rate(x, run, parameters, model)
        total += weight / max(rate, 1e-30)
    return total * step / 3.0
