"""催化反应色谱数据汇总入口。

用法：python3 /app/main.py <run.json>
"""

from __future__ import annotations

import json
import sys
from decimal import Decimal, ROUND_HALF_UP

from activity import turnover_frequency
from balances import outlet_molar_flows, summarize_balance


def rounded(value: float, places: int) -> float:
    quant = Decimal(1).scaleb(-places)
    return float(Decimal(str(value)).quantize(quant, rounding=ROUND_HALF_UP))


def analyze(payload: dict) -> dict:
    outlet = outlet_molar_flows(payload)
    summary = summarize_balance(payload, outlet)
    tof = turnover_frequency(summary["methanol_converted_mol_per_h"], payload["catalyst"])
    selectivity = {
        species: rounded(value, 4)
        for species, value in summary["selectivity_percent"].items()
    }
    return {
        "run_id": str(payload["run_id"]),
        "conversion_percent": rounded(summary["conversion_percent"], 4),
        "carbon_balance_percent": rounded(summary["carbon_balance_percent"], 4),
        "selectivity_percent": selectivity,
        "methanol_converted_mmol_per_h": rounded(
            summary["methanol_converted_mol_per_h"] * 1000.0, 4
        ),
        "tof_s_inverse": rounded(tof, 6),
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python3 /app/main.py <run.json>", file=sys.stderr)
        return 2
    with open(argv[1], "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    print(json.dumps(analyze(payload), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
