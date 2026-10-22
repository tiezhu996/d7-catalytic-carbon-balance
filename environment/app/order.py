"""反应级数的快速估算。"""

from __future__ import annotations

import math


def output_order(summaries: list[dict], fitted_order: float) -> float:
    x_values = [math.log(max(run["feed_methanol_mol_per_s"], 1e-30)) for run in summaries]
    y_values = [
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
    mean_x = sum(x_values) / len(x_values)
    mean_y = sum(y_values) / len(y_values)
    denominator = sum((x - mean_x) ** 2 for x in x_values)
    if denominator < 1e-20:
        return 0.0
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(x_values, y_values)) / denominator
    return max(0.0, min(4.0, slope))
