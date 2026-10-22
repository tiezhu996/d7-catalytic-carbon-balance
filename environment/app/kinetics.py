"""反应数据处理工具。"""

from __future__ import annotations

import math

from deactivation import choose_model
from order import output_order
from reactor import differential_rate

R_GAS = 8.314462618
REFERENCE_TEMPERATURE_K = 623.15


def _solve(matrix: list[list[float]], vector: list[float]) -> list[float] | None:
    size = len(vector)
    rows = [list(matrix[i]) + [vector[i]] for i in range(size)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(rows[row][column]))
        if abs(rows[pivot][column]) < 1e-14:
            return None
        rows[column], rows[pivot] = rows[pivot], rows[column]
        divisor = rows[column][column]
        for j in range(column, size + 1):
            rows[column][j] /= divisor
        for row in range(size):
            if row == column:
                continue
            factor = rows[row][column]
            if factor:
                for j in range(column, size + 1):
                    rows[row][j] -= factor * rows[column][j]
    return [rows[i][size] for i in range(size)]


def estimate(summaries: list[dict], catalyst: dict) -> dict:
    """由转化率和操作条件给出一个快速参数估计。"""
    design = []
    response = []
    for run in summaries:
        feed = run["feed_methanol_mol_per_s"]
        rate = differential_rate(feed, run["conversion"], run["catalyst_mass_g"])
        response.append(math.log(max(rate, 1e-30)))
        design.append([
            1.0,
            math.log(max(feed, 1e-30)),
            1.0 / REFERENCE_TEMPERATURE_K - 1.0 / run["temperature_k"],
            -run["time_on_stream_h"],
        ])
    normal = [[0.0] * 4 for _ in range(4)]
    rhs = [0.0] * 4
    for row, target in zip(design, response):
        for i in range(4):
            rhs[i] += row[i] * target
            for j in range(4):
                normal[i][j] += row[i] * row[j]
    for i in range(4):
        normal[i][i] += 1e-8
    coefficients = _solve(normal, rhs) or [math.log(2e-4), 0.0, 90.0, 0.05]
    rref = math.exp(max(-20.0, min(2.0, coefficients[0])))
    ea = max(1.0, min(300.0, coefficients[2] * R_GAS / 1000.0))
    order = output_order(summaries, max(0.0, min(4.0, coefficients[1])))
    kd = max(0.0, min(10.0, coefficients[3]))
    sites = float(catalyst["active_sites_mmol_per_g"]) / 1000.0
    average_rate = sum(
        run["feed_methanol_mol_per_s"] * run["conversion"] / run["catalyst_mass_g"]
        for run in summaries
    ) / len(summaries)
    return {
        "activation_energy_kj_mol": ea,
        "reaction_order": order,
        "deactivation_model": choose_model(summaries),
        "deactivation_constant_per_h": kd,
        "rate_constant_at_reference_mol_g_s": rref,
        "initial_tof_s_inverse": average_rate / sites,
    }
