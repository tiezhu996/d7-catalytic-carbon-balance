"""气相色谱峰面积与摩尔比的换算。"""

from __future__ import annotations

import math


def amount_ratio_from_area(area_ratio: float, coefficients: list[float]) -> float:
    """反算二次校准曲线中与峰面积比对应的非负摩尔比。

    校准关系为：面积比 = c0 + c1*x + c2*x^2。x 取非负实根。
    """
    intercept = float(coefficients[0])
    slope = float(coefficients[1])
    curvature = float(coefficients[2])
    if area_ratio <= intercept:
        return 0.0
    if slope < 0.0 or curvature < 0.0:
        raise ValueError("calibration coefficients must be non-negative")

    target = area_ratio - intercept
    if curvature == 0.0:
        if slope == 0.0:
            raise ValueError("calibration slope must be positive")
        return max(0.0, target / slope)

    discriminant = slope * slope + 4.0 * curvature * target
    if discriminant < 0.0:
        raise ValueError("calibration has no real positive root")
    root = (-slope + math.sqrt(discriminant)) / (2.0 * curvature)
    if root < -1e-12:
        raise ValueError("calibration has no non-negative root")
    return max(0.0, root)
