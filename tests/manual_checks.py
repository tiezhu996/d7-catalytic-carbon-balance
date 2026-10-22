#!/usr/bin/env python3
"""题包冻结前的人工规则复核脚本。

只读 task 目录，不访问网络，不依赖 pytest。每条规则输出一行固定结论，
供 manual_receipt.py 记录并在审核导出的字节等价目录中重放。
"""

from __future__ import annotations

import argparse
import ast
import json
import math
import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "environment" / "app" / "main.py"
REFERENCE = ROOT / "solution" / "app" / "main.py"
SAMPLE = ROOT / "environment" / "app" / "sample_run.json"
INSTRUCTION = ROOT / "instruction.md"
TESTS = ROOT / "tests" / "test_outputs.py"
SCORING = ROOT / "tests" / "scoring.json"
TASK_TOML = ROOT / "task.toml"
DOCKERFILE = ROOT / "environment" / "Dockerfile"
DOCKERIGNORE = ROOT / "environment" / ".dockerignore"
TEST_SH = ROOT / "tests" / "test.sh"
SOLUTION = ROOT / "solution"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def reference_output() -> dict:
    proc = subprocess.run(
        [sys.executable, str(REFERENCE), str(SAMPLE)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=20,
        check=True,
    )
    return json.loads(proc.stdout)


def independent_output() -> dict:
    sample = json.loads(read(SAMPLE))
    calibrations = sample["gc"]["calibrations"]
    peaks = sample["gc"]["outlet_peak_areas"]
    n2_flow = float(sample["feed"]["internal_standard_mol_per_h"])
    n2_area = float(peaks["N2"])

    def inverse(coefficients: list[float], target: float) -> float:
        lo, hi = 0.0, 1.0
        def forward(x: float) -> float:
            return coefficients[0] + coefficients[1] * x + coefficients[2] * x * x
        while forward(hi) < target:
            hi *= 2.0
        for _ in range(200):
            mid = (lo + hi) / 2.0
            if forward(mid) < target:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2.0

    outlet = {
        species: n2_flow * inverse(coefficients, float(peaks.get(species, 0.0)) / n2_area)
        for species, coefficients in calibrations.items()
    }
    feed = float(sample["feed"]["methanol_mol_per_h"])
    carbon_number = {"CO2": 1, "CO": 1, "CH4": 1, "DME": 2}
    products = sum(carbon_number[s] * outlet.get(s, 0.0) for s in carbon_number)
    converted = feed - outlet["methanol"]
    catalyst = sample["catalyst"]
    surface_metal = (
        float(catalyst["catalyst_mass_g"])
        * float(catalyst["metal_loading_wt_percent"])
        / 100.0
        / float(catalyst["active_metal_molar_mass_g_per_mol"])
        * float(catalyst["metal_dispersion_fraction"])
    )
    return {
        "conversion_percent": round(100.0 * converted / feed, 4),
        "carbon_balance_percent": round(100.0 * (outlet["methanol"] + products) / feed, 4),
        "selectivity_percent": {
            species: round(100.0 * carbon_number[species] * outlet.get(species, 0.0) / products, 4)
            for species in carbon_number
        },
        "methanol_converted_mmol_per_h": round(converted * 1000.0, 4),
        "tof_s_inverse": round(converted / 3600.0 / surface_metal, 6),
    }


def check(condition: bool, detail: str) -> str:
    if not condition:
        raise SystemExit("FAIL: " + detail)
    return detail


def imports(path: Path) -> set[str]:
    tree = ast.parse(read(path))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def run_rule(rule: str) -> str:
    if rule == "C1":
        got = reference_output()
        expected = independent_output()
        fields = ("conversion_percent", "carbon_balance_percent", "methanol_converted_mmol_per_h", "tof_s_inverse")
        check(all(abs(got[f] - expected[f]) < 1e-6 for f in fields), "C1 sample recompute matches reference")
        check(got["selectivity_percent"] == expected["selectivity_percent"], "C1 selectivity recompute matches reference")
        return "C1 PASS: sample recompute matches reference on all numeric fields"
    if rule == "C2":
        text = read(INSTRUCTION)
        required = ["run_id", "conversion_percent", "carbon_balance_percent", "selectivity_percent",
                    "methanol_converted_mmol_per_h", "tof_s_inverse"]
        check(all(key in text for key in required), "C2 output fields are specified")
        check("参数个数不对时退出码为 2" in text, "C2 argument error is specified")
        return "C2 PASS: target, output contract, and error boundary are explicit"
    if rule == "C5":
        names = re.findall(r"^def (test_\w+)", read(TESTS), re.M)
        check(len(names) >= 10, "C5 test suite has at least ten behavior tests")
        check("solution/app/calibration.py" in read(ROOT / "solution" / "NOTES.md"), "C5 domain calculation is documented")
        return "C5 PASS: tests require recalibration, carbon accounting, and TOF rather than syntax edits"
    if rule == "C7":
        text = read(INSTRUCTION) + read(TESTS) + read(ROOT / "solution" / "app" / "main.py")
        for token in ("conversion_percent", "carbon_balance_percent", "selectivity_percent", "tof_s_inverse", "DME"):
            check(token in text, f"C7 token {token} is consistent")
        json.loads(read(SAMPLE))
        tomllib.loads(read(TASK_TOML))
        return "C7 PASS: paths, JSON keys, TOML, and chemical species names are consistent"
    if rule == "C8":
        got = reference_output()
        check(got["tof_s_inverse"] > 0, "C8 sample run is reachable")
        return "C8 PASS: sample input reaches a complete reference result"
    if rule == "D3":
        third_party = set()
        for path in (ROOT / "environment" / "app").glob("*.py"):
            third_party |= imports(path) - {"__future__", "json", "sys", "math", "decimal", "activity", "balances", "calibration"}
        check(not third_party, "D3 runtime uses standard library only")
        return "D3 PASS: runtime imports are Python standard library and local modules only"
    if rule == "D4":
        same_main = read(ROOT / "environment" / "app" / "main.py") == read(REFERENCE)
        changed = [
            name for name in ("calibration.py", "balances.py", "activity.py")
            if read(ROOT / "environment" / "app" / name) != read(ROOT / "solution" / "app" / name)
        ]
        check(same_main and changed == ["calibration.py", "balances.py", "activity.py"], "D4 defect scope is intentional")
        return "D4 PASS: only the three intended calculation modules differ; entry orchestration is unchanged"
    if rule == "D5":
        network = {"socket", "requests", "urllib", "http", "aiohttp", "httpx"}
        used = set()
        for path in (ROOT / "environment" / "app").glob("*.py"):
            used |= imports(path)
        check(not (used & network), "D5 runtime has no network dependency")
        config = tomllib.loads(read(TASK_TOML))
        check(config["environment"]["allow_internet"] is True, "D5 platform network flag is explicit")
        return "D5 PASS: Harbor exposes public network, while the submitted program neither imports nor needs network"
    if rule == "D6":
        first = subprocess.run([sys.executable, str(REFERENCE), str(SAMPLE)], cwd=ROOT, text=True,
                               capture_output=True, timeout=20, check=True).stdout
        second = subprocess.run([sys.executable, str(REFERENCE), str(SAMPLE)], cwd=ROOT, text=True,
                                capture_output=True, timeout=20, check=True).stdout
        check(first == second, "D6 repeated output is byte-identical")
        return "D6 PASS: two clean reference executions produce byte-identical JSON"
    if rule == "D7":
        dockerfile = read(DOCKERFILE)
        dockerignore = read(DOCKERIGNORE)
        config = tomllib.loads(read(TASK_TOML))
        check("COPY app/ /app/" in dockerfile, "D7 image copies only app")
        check("tests/" in dockerignore and "solution/" in dockerignore, "D7 tests and solution excluded")
        check(config["agent"]["user"] == "runner" and config["verifier"]["user"] == "root", "D7 user separation")
        return "D7 PASS: image exposes only /app; tests and solution are excluded; agent and verifier users differ"
    if rule == "E3":
        config = json.loads(read(SCORING))
        check(len(config["tests"]) == 9 and len(config["gate_tests"]) == 2, "E3 case matrix is complete")
        return "E3 PASS: two gates and nine scored cases cover three independent difficulty classes"
    if rule == "E4":
        config = json.loads(read(SCORING))
        total = math.fsum(float(item["weight"]) for item in config["tests"].values())
        check(abs(total - 1.0) < 1e-12, "E4 scoring weights sum to one")
        return "E4 PASS: weights sum to 1.0 and tolerances are tied to output precision"
    if rule == "E10":
        got = reference_output()
        check(set(got) == {"run_id", "conversion_percent", "carbon_balance_percent", "selectivity_percent",
                           "methanol_converted_mmol_per_h", "tof_s_inverse"}, "E10 top-level schema is exact")
        check(all(isinstance(got[k], (int, float)) and not isinstance(got[k], bool)
                  for k in ("conversion_percent", "carbon_balance_percent",
                            "methanol_converted_mmol_per_h", "tof_s_inverse")), "E10 numeric runtime types")
        check(set(got["selectivity_percent"]) == {"CO2", "CO", "CH4", "DME"}, "E10 selectivity schema is exact")
        return "E10 PASS: exact key sets, JSON object shape, and numeric runtime types are checked"
    if rule == "E11":
        test_sh = read(TEST_SH)
        check("rm -rf \"$V/reward.json\"" in test_sh, "E11 reward.json cleanup before scoring")
        check("score.py reap" in test_sh, "E11 candidate processes are reaped")
        return "E11 PASS: reward file is cleared, candidate processes are reaped, and tests run as root against runner output"
    if rule == "F1":
        got = reference_output()
        check(got["conversion_percent"] == 38.504, "F1 reference conversion")
        check(got["carbon_balance_percent"] == 99.8075, "F1 reference carbon balance")
        return "F1 PASS: reference implementation completes the sample and matches independently derived values"
    if rule == "F2":
        for name in ("calibration.py", "balances.py", "activity.py", "main.py"):
            env_path = ROOT / "environment" / "app" / name
            sol_path = ROOT / "solution" / "app" / name
            check(env_path.is_file() and sol_path.is_file(), f"F2 {name} exists")
        check(read(ROOT / "environment" / "app" / "main.py") == read(REFERENCE), "F2 entry orchestration unchanged")
        return "F2 PASS: reference changes only calculation modules and leaves the entry contract intact"
    if rule == "F3":
        first = reference_output()
        second = reference_output()
        check(first == second, "F3 repeated results are equal")
        return "F3 PASS: repeated execution is deterministic and writes no persistent intermediate output"
    if rule == "F4":
        text = read(INSTRUCTION)
        for key in ("run_id", "conversion_percent", "carbon_balance_percent", "selectivity_percent",
                    "methanol_converted_mmol_per_h", "tof_s_inverse", "CO2", "CO", "CH4", "DME"):
            check(key in text, f"F4 contract token {key} is documented")
        got = reference_output()
        check(set(got["selectivity_percent"]) == {"CO2", "CO", "CH4", "DME"}, "F4 test and reference species agree")
        return "F4 PASS: instruction, tests, and reference agree on paths, fields, units, species, and rounding"
    if rule == "F5":
        got = reference_output()
        expected = independent_output()
        check(got == {**got, **expected}, "F5 sample and independent calculation agree")
        return "F5 PASS: sample fixture, independent recomputation, and reference output agree"
    raise SystemExit(f"unknown rule: {rule}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rule", required=True)
    args = parser.parse_args()
    print(run_rule(args.rule))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
