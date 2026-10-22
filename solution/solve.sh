#!/usr/bin/env bash
# 参考解：安装 solution/app/ 下的完整实现。
# HTB_SKIP 用精确片段把指定难点退回原始写法，供留一法和变异矩阵使用。
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
for source in "$HERE"/app/*.py; do
    install -m 0644 "$source" "/app/$(basename "$source")"
done

SKIP="${HTB_SKIP:-}" /usr/local/bin/python3 - /app/calibration.py /app/balances.py /app/activity.py <<'PY'
import os
import sys
from pathlib import Path

REVERT = {
    "difficulty_1": [
        ("/app/calibration.py", '''    intercept = float(coefficients[0])
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
    return max(0.0, root)''', '''    intercept = coefficients[0] if len(coefficients) > 0 else 0.0
    slope = coefficients[1] if len(coefficients) > 1 else 0.0
    if area_ratio <= intercept or slope <= 0.0:
        return 0.0
    ratio = (area_ratio - intercept) / slope
    return max(0.0, ratio)'''),
    ],
    "difficulty_2": [
        ("/app/balances.py", '''    carbon_products = sum(
        CARBON_NUMBER[species] * amount for species, amount in products.items()
    )''', "    carbon_products = sum(products.values())"),
        ("/app/balances.py", '''            species: 100.0 * CARBON_NUMBER[species] * amount / carbon_products''',
         '''            species: 100.0 * amount / carbon_products'''),
    ],
    "difficulty_3": [
        ("/app/activity.py", '''    catalyst_mass_g = float(catalyst["catalyst_mass_g"])
    loading = float(catalyst["metal_loading_wt_percent"]) / 100.0
    molar_mass = float(catalyst["active_metal_molar_mass_g_per_mol"])
    dispersion = float(catalyst["metal_dispersion_fraction"])

    total_metal_mol = catalyst_mass_g * loading / molar_mass
    surface_metal_mol = total_metal_mol * dispersion
    if surface_metal_mol <= 0.0:
        raise ValueError("surface active metal amount must be positive")
    return converted_mol_per_h / 3600.0 / surface_metal_mol''', '''    bed_mass_g = float(catalyst["catalyst_mass_g"]) + float(catalyst["diluent_mass_g"])
    loading = float(catalyst["metal_loading_wt_percent"]) / 100.0
    metal_mol = bed_mass_g * loading / 63.546
    if metal_mol <= 0.0:
        raise ValueError("active metal amount must be positive")
    return converted_mol_per_h / 3600.0 / metal_mol'''),
    ],
}

skip = [item for item in os.environ.get("SKIP", "").split(",") if item]
unknown = sorted(set(skip) - set(REVERT))
if unknown:
    sys.exit(f"HTB_SKIP 里有未知难点：{unknown}")

for key in skip:
    for filename, fixed, original in REVERT[key]:
        path = Path(filename)
        text = path.read_text(encoding="utf-8")
        count = text.count(fixed)
        if count != 1:
            sys.exit(f"{key} 在 {filename} 的修复片段出现 {count} 次，应为 1")
        path.write_text(text.replace(fixed, original), encoding="utf-8")
        print(f"留一法：{key} 修改 {filename}", file=sys.stderr)
PY

chown runner:runner /app/*.py 2>/dev/null || true
