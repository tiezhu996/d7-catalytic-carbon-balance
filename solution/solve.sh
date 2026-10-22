#!/usr/bin/env bash
# 参考解：安装 solution/app/ 下的完整实现。
# HTB_SKIP 用精确片段把指定难点退回原始估算写法，供留一法和变异矩阵使用。
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
for source in "$HERE"/app/*.py; do
    install -m 0644 "$source" "/app/$(basename "$source")"
done

SKIP="${HTB_SKIP:-}" /usr/local/bin/python3 - /app/kinetics.py <<'PY'
import os
import sys
from pathlib import Path

REVERT = {
    "difficulty_1": [
        ('''    if conversion <= 0.0:
        return 0.0
    intervals = 24
    step = conversion / intervals
    total = 0.0
    for index in range(intervals + 1):
        x = index * step
        weight = 1.0 if index in (0, intervals) else (4.0 if index % 2 else 2.0)
        rate = reaction_rate(x, run, parameters, model, concentration_basis)
        total += weight / max(rate, 1e-30)
    return total * step / 3.0''',
         '''    if conversion <= 0.0:
        return 0.0
    rate = reaction_rate(0.0, run, parameters, model, concentration_basis)
    return conversion / max(rate, 1e-30)'''),
    ],
    "difficulty_2": [
        ('    order = reported_order(summaries, chosen[2], "axial")',
         '    order = reported_order(summaries, chosen[2], "feed_flow")'),
    ],
    "difficulty_3": [
        ('''    first_parameters, first_error = fit_model(summaries, "first_order")
    model = "first_order"
    chosen = first_parameters
    times = [run["time_on_stream_h"] for run in summaries]
    if max(times) - min(times) > 1.0:
        second_parameters, second_error = fit_model(summaries, "second_order")
        if second_error < 0.8 * first_error:
            model = "second_order"
            chosen = second_parameters''',
         '''    chosen, _ = fit_model(summaries, "first_order")
    model = "first_order"'''),
    ],
}

skip = [item for item in os.environ.get("SKIP", "").split(",") if item]
unknown = sorted(set(skip) - set(REVERT))
if unknown:
    sys.exit(f"HTB_SKIP 里有未知难点：{unknown}")

path = Path("/app/kinetics.py")
for key in skip:
    for fixed, original in REVERT[key]:
        text = path.read_text(encoding="utf-8")
        count = text.count(fixed)
        if count != 1:
            sys.exit(f"{key} 的修复片段出现 {count} 次，应为 1")
        path.write_text(text.replace(fixed, original), encoding="utf-8")
        print(f"留一法：{key} 退回原始写法", file=sys.stderr)
PY

chown runner:runner /app/*.py 2>/dev/null || true
