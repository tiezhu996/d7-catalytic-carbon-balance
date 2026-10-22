"""催化剂失活模型与模型选择。"""

from __future__ import annotations

import math


def activity_factor(time_h: float, constant_per_h: float, model: str) -> float:
    if model == "first_order":
        return math.exp(-constant_per_h * time_h)
    return 1.0 / (1.0 + constant_per_h * time_h)


def choose_model(summaries: list[dict], fit_model) -> tuple[dict, str]:
    chosen, _ = fit_model(summaries, "first_order")
    return chosen, "first_order"
