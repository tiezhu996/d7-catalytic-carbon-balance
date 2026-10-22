"""催化剂失活模型。"""

from __future__ import annotations

import math


def activity_factor(time_h: float, constant_per_h: float, model: str) -> float:
    return math.exp(-constant_per_h * time_h)


def choose_model(summaries: list[dict], fit_model=None):
    return "first_order"
