"""反应级数的输出口径。"""

from __future__ import annotations

import math


def reported_order(summaries: list[dict], fitted_order: float, basis: str) -> float:
    if basis == "axial":
        return fitted_order
    covariate = [math.log(max(run["feed_methanol_mol_per_s"], 1e-30)) for run in summaries]
    response = [
        math.log(
            max(
                run["feed_methanol_mol_per_s"]
                * run["conversion"]
                / run["catalyst_mass_g"],
                1e-30,
            )
        )
        for run in summaries
    ]
    mean_x = sum(covariate) / len(covariate)
    mean_y = sum(response) / len(response)
    denominator = sum((value - mean_x) ** 2 for value in covariate)
    if denominator < 1e-20:
        return 0.0
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(covariate, response)) / denominator
    return max(0.0, min(4.0, slope))


def output_order(summaries: list[dict], fitted_order: float) -> float:
    return reported_order(summaries, fitted_order, "axial")
