"""气相色谱峰面积与摩尔比的换算。"""

from __future__ import annotations


def amount_ratio_from_area(area_ratio: float, coefficients: list[float]) -> float:
    """把物种与内标的峰面积比换算成摩尔比。"""
    intercept = coefficients[0] if len(coefficients) > 0 else 0.0
    slope = coefficients[1] if len(coefficients) > 1 else 0.0
    if area_ratio <= intercept or slope <= 0.0:
        return 0.0
    ratio = (area_ratio - intercept) / slope
    return max(0.0, ratio)
