#!/usr/bin/env bash
# 参考解：安装 solution/app/ 下的完整实现。
# HTB_SKIP 用精确片段把指定难点退回原始估算写法，供留一法和变异矩阵使用。
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
for source in "$HERE"/app/*.py; do
    install -m 0644 "$source" "/app/$(basename "$source")"
done

SKIP="${HTB_SKIP:-}" /usr/local/bin/python3 - <<'PY'
import os
import sys
from pathlib import Path

REVERT = {
    "difficulty_1": [
        ("/app/reactor.py", '''    if conversion <= 0.0:
        return 0.0
    intervals = 32
    step = conversion / intervals
    total = 0.0
    for index in range(intervals + 1):
        x = index * step
        weight = 1.0 if index in (0, intervals) else (4.0 if index % 2 else 2.0)
        rate = reaction_rate(x, run, parameters, model)
        total += weight / max(rate, 1e-30)
    return total * step / 3.0''', '''    if conversion <= 0.0:
        return 0.0
    rate = reaction_rate(0.0, run, parameters, model)
    return conversion / max(rate, 1e-30)'''),
    ],
    "difficulty_2": [
        ("/app/order.py", '''def output_order(summaries: list[dict], fitted_order: float) -> float:
    return reported_order(summaries, fitted_order, "axial")''',
         '''def output_order(summaries: list[dict], fitted_order: float) -> float:
    covariate = [math.log(max(run["feed_methanol_mol_per_s"], 1e-30)) for run in summaries]
    response = [
        math.log(max(run["feed_methanol_mol_per_s"] * run["conversion"] / run["catalyst_mass_g"], 1e-30))
        for run in summaries
    ]
    mean_x = sum(covariate) / len(covariate)
    mean_y = sum(response) / len(response)
    denominator = sum((value - mean_x) ** 2 for value in covariate)
    if denominator < 1e-20:
        return 0.0
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(covariate, response)) / denominator
    return max(0.0, min(4.0, slope))'''),
    ],
    "difficulty_3": [
        ("/app/deactivation.py", '''    first_parameters, first_error = fit_model(summaries, "first_order")
    chosen = first_parameters
    model = "first_order"
    times = [run["time_on_stream_h"] for run in summaries]
    if max(times) - min(times) > 1.0:
        second_parameters, second_error = fit_model(summaries, "second_order")
        if second_error < 0.8 * first_error:
            chosen = second_parameters
            model = "second_order"
    return chosen, model''', '''    chosen, _ = fit_model(summaries, "first_order")
    return chosen, "first_order"'''),
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
