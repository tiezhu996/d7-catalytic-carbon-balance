"""固定床速率的快速估算。"""

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
    concentration = run["feed_methanol_mol_per_s"]
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
    if conversion <= 0.0:
        return 0.0
    rate = reaction_rate(0.0, run, parameters, model)
    return conversion / max(rate, 1e-30)


def differential_rate(feed_methanol_mol_per_s: float, conversion: float, catalyst_mass_g: float) -> float:
    return feed_methanol_mol_per_s * conversion / catalyst_mass_g
