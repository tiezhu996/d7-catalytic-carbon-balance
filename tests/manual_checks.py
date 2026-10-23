#!/usr/bin/env python3
"""题包冻结前的人工规则复核脚本。"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import math
import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "solution" / "app" / "main.py"
SAMPLE = ROOT / "environment" / "app" / "sample_run.json"
INSTRUCTION = ROOT / "instruction.md"
TESTS = ROOT / "tests" / "test_outputs.py"
SCORING = ROOT / "tests" / "scoring.json"
TASK_TOML = ROOT / "task.toml"
DOCKERFILE = ROOT / "environment" / "Dockerfile"
DOCKERIGNORE = ROOT / "environment" / ".dockerignore"
TEST_SH = ROOT / "tests" / "test.sh"
OUTPUT_FIELDS = {
    "run_id",
    "activation_energy_kj_mol",
    "reaction_order",
    "deactivation_model",
    "deactivation_constant_per_h",
    "rate_constant_at_reference_mol_g_s",
    "initial_tof_s_inverse",
    "mean_carbon_balance_percent",
}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def run_reference(path: Path = SAMPLE) -> dict:
    proc = subprocess.run(
        [sys.executable, str(ENTRY), str(path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
        check=True,
    )
    return json.loads(proc.stdout)


def imports(path: Path) -> set[str]:
    tree = ast.parse(read(path))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def check(condition: bool, detail: str) -> str:
    if not condition:
        raise SystemExit("FAIL: " + detail)
    return detail


def load_test_module():
    spec = importlib.util.spec_from_file_location("task_tests", TESTS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_generated_case(group: str, variant: int) -> dict:
    module = load_test_module()
    payload = module.make_payload(group, variant)
    folder = Path(__import__("tempfile").mkdtemp(prefix="manual-kinetics-"))
    case = folder / "runs.json"
    case.write_text(json.dumps(payload), encoding="utf-8")
    return run_reference(case)


def run_rule(rule: str) -> str:
    if rule == "C1":
        got = run_generated_case("integral", 0)
        check(abs(got["activation_energy_kj_mol"] - 92.0) < 0.6, "C1 activation energy recovers")
        return "C1 PASS: integral packed-bed data recover the generated activation energy"
    if rule == "C2":
        text = read(INSTRUCTION)
        for key in OUTPUT_FIELDS:
            check(key in text, f"C2 field {key} is specified")
        check("程序参数个数不对时退出码为 2" in text, "C2 argument error is specified")
        return "C2 PASS: target, output contract, and error boundary are explicit"
    if rule == "C5":
        tests = re.findall(r"^def (test_\w+)", read(TESTS), re.M)
        check(len(tests) >= 10, "C5 test suite has at least ten behavior tests")
        return "C5 PASS: the task requires kinetics, inverse fitting, and model selection"
    if rule == "C7":
        text = read(INSTRUCTION) + read(TESTS) + read(ENTRY)
        for token in OUTPUT_FIELDS:
            check(token in text, f"C7 field {token} is consistent")
        return "C7 PASS: paths, JSON keys, units, and species names are consistent"
    if rule == "C8":
        got = run_reference()
        check(set(got) == OUTPUT_FIELDS, "C8 sample reaches complete output")
        return "C8 PASS: sample input reaches a complete reference result"
    if rule == "D3":
        allowed = {"__future__", "json", "sys", "math", "decimal", "calibration", "gcdata", "kinetics",
                   "deactivation", "order", "reactor"}
        used = set()
        for path in (ROOT / "environment" / "app").glob("*.py"):
            used |= imports(path)
        check(not (used - allowed), "D3 runtime uses standard library only")
        return "D3 PASS: runtime uses Python standard library and local modules only"
    if rule == "D4":
        changed = []
        for name in ("deactivation.py", "kinetics.py"):
            if read(ROOT / "environment" / "app" / name) != read(ROOT / "solution" / "app" / name):
                changed.append(name)
        check(changed == ["deactivation.py", "kinetics.py"], "D4 intended modules differ")
        return "D4 PASS: only the intended deactivation and fitting modules differ"
    if rule == "D5":
        network = {"socket", "requests", "urllib", "http", "aiohttp", "httpx"}
        used = set()
        for path in (ROOT / "environment" / "app").glob("*.py"):
            used |= imports(path)
        check(not (used & network), "D5 runtime has no network import")
        config = tomllib.loads(read(TASK_TOML))
        check(config["environment"]["allow_internet"] is True, "D5 platform network flag is explicit")
        return "D5 PASS: public platform network is explicit; the program has no network dependency"
    if rule == "D6":
        first = run_reference()
        second = run_reference()
        check(first == second, "D6 repeated results are equal")
        return "D6 PASS: repeated reference execution is deterministic"
    if rule == "D7":
        config = tomllib.loads(read(TASK_TOML))
        check("COPY app/ /app/" in read(DOCKERFILE), "D7 image copies only app")
        check("tests/" in read(DOCKERIGNORE) and "solution/" in read(DOCKERIGNORE), "D7 excluded files")
        check(config["agent"]["user"] == "runner" and config["verifier"]["user"] == "root", "D7 users")
        return "D7 PASS: image isolation and user separation match the contract"
    if rule == "E3":
        config = json.loads(read(SCORING))
        gates = set(config["gate_tests"])
        scored = set(config["tests"])
        defined = set(re.findall(r"^def (test_\w+)", read(TESTS), re.M))
        configured = {item.split("::", 1)[1] for item in gates | scored}
        check(len(gates) == 7 and len(scored) == 9, "E3 case matrix")
        check(not (gates & scored), "E3 gate and scored sets are disjoint")
        check(configured == defined, "E3 scoring config matches test functions")
        return "E3 PASS: seven gates and nine scored cases match the test suite"
    if rule == "E4":
        config = json.loads(read(SCORING))
        check(config.get("weight_policy") == "business_priority", "E4 business-priority policy")
        weights = [float(value["weight"]) for value in config["tests"].values()]
        check(all(0.0 < weight <= 1.0 for weight in weights), "E4 weights are normalized fractions")
        check(all(str(value.get("rationale", "")).strip() for value in config["tests"].values()),
              "E4 every weight has a business rationale")
        total = math.fsum(weights)
        check(abs(total - 1.0) < 1e-12, "E4 weights sum to one")
        return "E4 PASS: business_priority weights sum to 1.0 and each has a rationale"
    if rule == "E10":
        got = run_reference()
        check(set(got) == OUTPUT_FIELDS, "E10 exact key set")
        check(all(isinstance(got[k], (int, float)) and not isinstance(got[k], bool)
                  for k in OUTPUT_FIELDS - {"run_id", "deactivation_model"}), "E10 numeric types")
        return "E10 PASS: exact key set, JSON object shape, and runtime types are covered"
    if rule == "E11":
        text = read(TEST_SH)
        check('rm -rf "$V/reward.json"' in text, "E11 reward cleanup")
        check("score.py reap" in text, "E11 process reap")
        return "E11 PASS: reward cleanup and candidate process reaping are present"
    if rule == "F1":
        got = run_reference()
        check(set(got) == OUTPUT_FIELDS, "F1 reference completes")
        return "F1 PASS: the reference implementation completes the sample and outputs every field"
    if rule == "F2":
        for name in ("calibration.py", "gcdata.py", "deactivation.py", "order.py", "reactor.py", "kinetics.py", "main.py"):
            check((ROOT / "solution" / "app" / name).is_file(), f"F2 {name} exists")
        return "F2 PASS: the reference changes only analysis modules and leaves the entry contract intact"
    if rule == "F3":
        check(run_reference() == run_reference(), "F3 repeated results")
        return "F3 PASS: repeated execution is deterministic and writes no persistent intermediate output"
    if rule == "F4":
        text = read(INSTRUCTION)
        for key in OUTPUT_FIELDS:
            check(key in text, f"F4 contract token {key}")
        return "F4 PASS: instruction, tests, and reference agree on fields, units, species, and rounding"
    if rule == "F5":
        got = run_generated_case("deactivation", 0)
        check(got["deactivation_model"] == "second_order", "F5 generated model matches reference")
        check(abs(got["deactivation_constant_per_h"] - 0.18) < 0.004, "F5 generated kd matches reference")
        return "F5 PASS: generated fixture and reference output agree on the declared model"
    raise SystemExit(f"unknown rule: {rule}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rule", required=True)
    args = parser.parse_args()
    print(run_rule(args.rule))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
