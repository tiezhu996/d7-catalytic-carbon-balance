"""催化剂失活模型与模型选择。"""

from __future__ import annotations

import math


def activity_factor(time_h: float, constant_per_h: float, model: str) -> float:
    if model == "first_order":
        return math.exp(-constant_per_h * time_h)
    return 1.0 / (1.0 + constant_per_h * time_h)


def choose_model(summaries: list[dict], fit_model) -> tuple[dict, str]:
    """同时比较一级与二级失活，返回参数最优的模型。"""
    first_parameters, first_error = fit_model(summaries, "first_order")
    chosen = first_parameters
    model = "first_order"
    times = [run["time_on_stream_h"] for run in summaries]
    if max(times) - min(times) > 1.0:
        second_parameters, second_error = fit_model(summaries, "second_order")
        if second_error < 0.8 * first_error:
            chosen = second_parameters
            model = "second_order"
    return chosen, model
