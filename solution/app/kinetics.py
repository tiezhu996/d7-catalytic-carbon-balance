"""积分固定床动力学参数反演。"""

from __future__ import annotations

import math

from deactivation import choose_model
from order import output_order
from reactor import reactor_modulus


def residuals(summaries: list[dict], parameters: list[float], model: str) -> list[float]:
    values = []
    for run in summaries:
        observed = run["catalyst_mass_g"] / run["feed_methanol_mol_per_s"]
        predicted = reactor_modulus(run["conversion"], run, parameters, model)
        values.append(math.log(max(predicted, 1e-30) / observed))
    return values


def objective(summaries: list[dict], parameters: list[float], model: str) -> float:
    return sum(value * value for value in residuals(summaries, parameters, model))


def solve_linear(matrix: list[list[float]], vector: list[float]) -> list[float] | None:
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


def refine(summaries: list[dict], start: list[float], model: str) -> tuple[list[float], float]:
    parameters = list(start)
    damping = 1e-2
    best = objective(summaries, parameters, model)
    for _ in range(100):
        base = residuals(summaries, parameters, model)
        jacobian = []
        epsilon = 1e-5
        for column in range(4):
            shifted = list(parameters)
            shifted[column] += epsilon
            trial = residuals(summaries, shifted, model)
            jacobian.append([(trial[row] - base[row]) / epsilon for row in range(len(base))])
        normal = [
            [sum(jacobian[i][k] * jacobian[j][k] for k in range(len(base))) for j in range(4)]
            for i in range(4)
        ]
        gradient = [sum(jacobian[i][k] * base[k] for k in range(len(base))) for i in range(4)]
        for i in range(4):
            normal[i][i] += damping * (normal[i][i] + 1e-9)
        delta = solve_linear(normal, [-value for value in gradient])
        if delta is None:
            break
        candidate = list(parameters)
        for index in range(4):
            candidate[index] += max(-2.0, min(2.0, delta[index]))
        candidate[0] = max(-20.0, min(2.0, candidate[0]))
        candidate[1] = max(1.0, min(300.0, candidate[1]))
        candidate[2] = max(0.0, min(4.0, candidate[2]))
        candidate[3] = max(-18.0, min(3.0, candidate[3]))
        value = objective(summaries, candidate, model)
        if value < best:
            parameters, best = candidate, value
            damping = max(1e-8, damping / 3.0)
        else:
            damping = min(1e8, damping * 5.0)
        if max(abs(x) for x in delta) < 1e-7:
            break
    return parameters, best


def initial_starts(summaries: list[dict]) -> list[list[float]]:
    rates = [
        run["feed_methanol_mol_per_s"] * run["conversion"] / run["catalyst_mass_g"]
        for run in summaries
    ]
    median_log_rate = sorted(math.log(max(rate, 1e-30)) for rate in rates)[len(rates) // 2]
    starts = []
    for shift in (0.0, -0.7):
        for activation in (60.0, 90.0, 120.0):
            starts.append([median_log_rate + shift, activation, 1.0, math.log(0.1)])
    return starts


def fit_model(summaries: list[dict], model: str) -> tuple[list[float], float]:
    best_parameters = None
    best_value = float("inf")
    for start in initial_starts(summaries):
        parameters, value = refine(summaries, start, model)
        if value < best_value:
            best_parameters, best_value = parameters, value
    if best_parameters is None:
        raise ValueError("kinetic fit did not converge")
    return best_parameters, best_value


def fit_robust(summaries: list[dict], model: str) -> tuple[list[float], float]:
    parameters, value = fit_model(summaries, model)
    values = [abs(item) for item in residuals(summaries, parameters, model)]
    ordered = sorted(values)
    median = ordered[len(ordered) // 2]
    limit = max(0.005, 3.0 * median)
    kept = [
        run
        for run, residual in zip(summaries, residuals(summaries, parameters, model))
        if abs(residual) <= limit
    ]
    if len(kept) >= 3 and len(kept) < len(summaries):
        return fit_model(kept, model)
    return parameters, value


def estimate(summaries: list[dict], catalyst: dict) -> dict:
    chosen, model = choose_model(summaries, fit_robust)
    reference_rate = math.exp(chosen[0])
    sites_mol_per_g = float(catalyst["active_sites_mmol_per_g"]) / 1000.0
    order = output_order(summaries, chosen[2])
    return {
        "activation_energy_kj_mol": chosen[1],
        "reaction_order": order,
        "deactivation_model": model,
        "deactivation_constant_per_h": math.exp(chosen[3]),
        "rate_constant_at_reference_mol_g_s": reference_rate,
        "initial_tof_s_inverse": reference_rate / sites_mol_per_g,
    }
