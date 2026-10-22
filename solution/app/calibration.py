"""气相色谱峰面积与摩尔比的换算。"""

from __future__ import annotations

import math


def amount_ratio_from_area(area_ratio: float, coefficients: list[float]) -> float:
    """按相对响应曲线计算摩尔比。"""
    c0, c1, c2 = (float(x) for x in coefficients)
    target = max(0.0, area_ratio - c0)
    if c2 == 0.0:
        return max(0.0, target / c1)
    disc = c1 * c1 + 4.0 * c2 * target
    return max(0.0, (-c1 + math.sqrt(max(0.0, disc))) / (2.0 * c2))
