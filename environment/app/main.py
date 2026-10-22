"""催化反应动力学数据汇总入口。

用法：python3 /app/main.py <runs.json>
"""

from __future__ import annotations

import json
import sys
from decimal import Decimal, ROUND_HALF_UP

from gcdata import summarize_payload
from kinetics import estimate


def rounded(value: float, places: int) -> float:
    quant = Decimal(1).scaleb(-places)
    return float(Decimal(str(value)).quantize(quant, rounding=ROUND_HALF_UP))


def analyze(payload: dict) -> dict:
    summaries = summarize_payload(payload)
    result = estimate(summaries, payload["catalyst"])
    return {
        "run_id": str(payload["run_id"]),
        "activation_energy_kj_mol": rounded(result["activation_energy_kj_mol"], 3),
        "reaction_order": rounded(result["reaction_order"], 4),
        "deactivation_model": result["deactivation_model"],
        "deactivation_constant_per_h": rounded(result["deactivation_constant_per_h"], 4),
        "rate_constant_at_reference_mol_g_s": rounded(result["rate_constant_at_reference_mol_g_s"], 9),
        "initial_tof_s_inverse": rounded(result["initial_tof_s_inverse"], 6),
        "mean_carbon_balance_percent": rounded(
            sum(run["carbon_balance_percent"] for run in summaries) / len(summaries), 4
        ),
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python3 /app/main.py <runs.json>", file=sys.stderr)
        return 2
    with open(argv[1], "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    print(json.dumps(analyze(payload), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
