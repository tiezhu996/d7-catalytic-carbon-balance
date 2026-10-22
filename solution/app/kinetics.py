"""积分固定床动力学参数反演。"""

from __future__ import annotations

import math

R_GAS = 8.314462618
REFERENCE_TEMPERATURE_K = 623.15
REFERENCE_CONCENTRATION = 100.0


def activity_factor(time_h: float, constant_per_h: float, model: str) -> float:
    if model == "first_order":
        return math.exp(-constant_per_h * time_h)
    return 1.0 / (1.0 + constant_per_h * time_h)


def reaction_rate(
    conversion: float,
    run: dict,
    parameters: list[float],
    model: str,
    concentration_basis: str = "axial",
) -> float:
    reference_rate = math.exp(parameters[0])
    activation_energy = parameters[1]
    order = parameters[2]
    deactivation_constant = math.exp(parameters[3])

    if concentration_basis == "feed_flow":
        concentration = run["feed_methanol_mol_per_s"]
    else:
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


def reactor_modulus(
    conversion: float,
    run: dict,
    parameters: list[float],
    model: str,
    concentration_basis: str = "axial",
) -> float:
    """按活塞流设计方程计算 W/F_A0。"""
    if conversion <= 0.0:
        return 0.0
    intervals = 24
    step = conversion / intervals
    total = 0.0
    for index in range(intervals + 1):
        x = index * step
        weight = 1.0 if index in (0, intervals) else (4.0 if index % 2 else 2.0)
        rate = reaction_rate(x, run, parameters, model, concentration_basis)
        total += weight / max(rate, 1e-30)
    return total * step / 3.0


def residuals(
    summaries: list[dict],
    parameters: list[float],
    model: str,
    concentration_basis: str = "axial",
) -> list[float]:
    values = []
    for run in summaries:
        observed = run["catalyst_mass_g"] / run["feed_methanol_mol_per_s"]
        predicted = reactor_modulus(
            run["conversion"], run, parameters, model, concentration_basis
        )
        values.append(math.log(max(predicted, 1e-30) / observed))
    return values


def objective(
    summaries: list[dict],
    parameters: list[float],
    model: str,
    concentration_basis: str = "axial",
) -> float:
    return sum(
        value * value
        for value in residuals(summaries, parameters, model, concentration_basis)
    )


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


def refine(
    summaries: list[dict],
    start: list[float],
    model: str,
    concentration_basis: str = "axial",
) -> tuple[list[float], float]:
    parameters = list(start)
    damping = 1e-2
    best = objective(summaries, parameters, model, concentration_basis)
    for _ in range(100):
        base = residuals(summaries, parameters, model, concentration_basis)
        jacobian = []
        epsilon = 1e-5
        for column in range(4):
            shifted = list(parameters)
            shifted[column] += epsilon
            trial = residuals(summaries, shifted, model, concentration_basis)
            jacobian.append(
                [(trial[row] - base[row]) / epsilon for row in range(len(base))]
            )
        normal = [
            [
                sum(jacobian[i][k] * jacobian[j][k] for k in range(len(base)))
                for j in range(4)
            ]
            for i in range(4)
        ]
        gradient = [
            sum(jacobian[i][k] * base[k] for k in range(len(base))) for i in range(4)
        ]
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
        value = objective(summaries, candidate, model, concentration_basis)
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
        run["feed_methanol_mol_per_s"]
        * run["conversion"]
        / run["catalyst_mass_g"]
        for run in summaries
    ]
    median_log_rate = sorted(math.log(max(rate, 1e-30)) for rate in rates)[len(rates) // 2]
    starts = []
    for shift in (0.0, -0.7):
        for activation in (60.0, 90.0, 120.0):
            starts.append(
                [
                    median_log_rate + shift,
                    activation,
                    1.0,
                    math.log(0.1),
                ]
            )
    return starts


def fit_model(
    summaries: list[dict],
    model: str,
    concentration_basis: str = "axial",
) -> tuple[list[float], float]:
    best_parameters = None
    best_value = float("inf")
    for start in initial_starts(summaries):
        parameters, value = refine(summaries, start, model, concentration_basis)
        if value < best_value:
            best_parameters, best_value = parameters, value
    if best_parameters is None:
        raise ValueError("kinetic fit did not converge")
    return best_parameters, best_value


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


def estimate(summaries: list[dict], catalyst: dict) -> dict:
    first_parameters, first_error = fit_model(summaries, "first_order")
    model = "first_order"
    chosen = first_parameters
    times = [run["time_on_stream_h"] for run in summaries]
    if max(times) - min(times) > 1.0:
        second_parameters, second_error = fit_model(summaries, "second_order")
        if second_error < 0.8 * first_error:
            model = "second_order"
            chosen = second_parameters

    reference_rate = math.exp(chosen[0])
    sites_mol_per_g = float(catalyst["active_sites_mmol_per_g"]) / 1000.0
    order = reported_order(summaries, chosen[2], "axial")
    return {
        "activation_energy_kj_mol": chosen[1],
        "reaction_order": order,
        "deactivation_model": model,
        "deactivation_constant_per_h": math.exp(chosen[3]),
        "rate_constant_at_reference_mol_g_s": reference_rate,
        "initial_tof_s_inverse": reference_rate / sites_mol_per_g,
    }
