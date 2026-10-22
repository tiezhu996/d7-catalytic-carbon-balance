"""甲醇重整色谱汇总的验收测试。

每个 `test_` 的 docstring 用「」引用题面原句。计分测试分别覆盖非线性校准、
含碳产物衡算和活性金属位点三个独立难点；期望值来自 `research/verify_gc.py`
的独立复算，不调用参考实现生成。
"""

import json
import os
import signal
import subprocess
import tempfile
from pathlib import Path

ENTRY = "/app/main.py"
PYTHON = "/usr/local/bin/python3"
CANDIDATE_USER = "runner"
CANDIDATE_ENV = {
    "PATH": "/usr/local/bin:/usr/bin:/bin",
    "HOME": "/home/runner",
    "LANG": "C.UTF-8",
    "TZ": "UTC",
}
CALL_TIMEOUT_SEC = 30

QUADRATIC = {
    "methanol": [0.02, 1.12, 0.018],
    "CO2": [0.01, 0.98, 0.006],
    "CO": [0.008, 1.05, 0.004],
    "CH4": [0.005, 1.10, 0.002],
    "DME": [0.012, 0.72, 0.010],
}
LINEAR = {
    "methanol": [0.02, 1.15, 0.0],
    "CO2": [0.01, 1.00, 0.0],
    "CO": [0.008, 1.05, 0.0],
    "CH4": [0.005, 1.10, 0.0],
    "DME": [0.015, 0.68, 0.0],
}
BASE_CATALYST = {
    "active_metal_molar_mass_g_per_mol": 63.546,
    "catalyst_mass_g": 0.75,
    "diluent_mass_g": 0.25,
    "metal_loading_wt_percent": 12.0,
    "metal_dispersion_fraction": 0.18,
}


def run_candidate(*args, timeout=CALL_TIMEOUT_SEC):
    """以 runner 身份运行候选入口；超时结束整个进程组并抛出 TimeoutError。"""
    as_root = os.getuid() == 0
    proc = subprocess.Popen(
        [PYTHON, ENTRY, *[str(a) for a in args]],
        cwd="/app",
        env=CANDIDATE_ENV,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
        user=CANDIDATE_USER if as_root else None,
        group=CANDIDATE_USER if as_root else None,
        extra_groups=[] if as_root else None,
    )
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.communicate()
        raise TimeoutError(f"{ENTRY} 超过 {timeout}s")
    return subprocess.CompletedProcess(proc.args, proc.returncode, out, err)


def make_payload(
    run_id,
    feed_methanol,
    outlet_amounts,
    calibrations,
    catalyst=None,
    n2_flow=0.1,
    n2_area=25000.0,
    sensitivity=1.0,
):
    """按已知出口摩尔流量构造与校准曲线一致的峰面积。"""
    peaks = {"N2": n2_area * sensitivity}
    for species, coefficients in calibrations.items():
        molar_ratio = outlet_amounts.get(species, 0.0) / n2_flow
        area_ratio = (
            coefficients[0]
            + coefficients[1] * molar_ratio
            + coefficients[2] * molar_ratio * molar_ratio
        )
        peaks[species] = area_ratio * n2_area * sensitivity
    return {
        "run_id": run_id,
        "feed": {
            "methanol_mol_per_h": feed_methanol,
            "internal_standard_mol_per_h": n2_flow,
        },
        "catalyst": dict(BASE_CATALYST if catalyst is None else catalyst),
        "gc": {
            "calibrations": calibrations,
            "outlet_peak_areas": peaks,
        },
    }


def analyze(payload):
    folder = Path(tempfile.mkdtemp(prefix="msr-"))
    folder.chmod(0o755)
    case = folder / "run.json"
    case.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    case.chmod(0o644)
    proc = run_candidate(case)
    assert proc.returncode == 0, f"exit={proc.returncode} stderr={proc.stderr[-500:]}"
    return json.loads(proc.stdout)


def case_with(calibrations, feed=1.0, outlet=None, catalyst=None, n2_area=25000.0, sensitivity=1.0):
    amounts = {
        "methanol": 0.5,
        "CO2": 0.10,
        "CO": 0.05,
        "CH4": 0.05,
        "DME": 0.10,
    }
    if outlet is not None:
        amounts = dict(outlet)
    return analyze(
        make_payload(
            "hidden-case",
            feed,
            amounts,
            calibrations,
            catalyst=catalyst,
            n2_area=n2_area,
            sensitivity=sensitivity,
        )
    )


# ---------- gate：入口与结构契约，不计分 ----------

def test_outputs_json_contract():
    """「程序向标准输出写一个 JSON 对象。对象只含以下字段：」"""
    got = case_with(LINEAR)
    assert set(got) == {
        "run_id",
        "conversion_percent",
        "carbon_balance_percent",
        "selectivity_percent",
        "methanol_converted_mmol_per_h",
        "tof_s_inverse",
    }
    assert set(got["selectivity_percent"]) == {"CO2", "CO", "CH4", "DME"}
    assert isinstance(got["run_id"], str)
    for field in ("conversion_percent", "carbon_balance_percent", "methanol_converted_mmol_per_h", "tof_s_inverse"):
        assert isinstance(got[field], (int, float)) and not isinstance(got[field], bool)
    for value in got["selectivity_percent"].values():
        assert isinstance(value, (int, float)) and not isinstance(value, bool)


def test_wrong_argument_count_exits_2():
    """「程序参数个数不对时退出码为 2，标准输出为空。」"""
    proc = run_candidate()
    assert proc.returncode == 2
    assert proc.stdout.strip() == ""


# ---------- 难点 1：二次校准曲线反算 ----------

def test_quadratic_calibration_conversion_moderate():
    """「每个数组的三个数依次是常数项、一次项和二次项。」"""
    outlet = {"methanol": 0.44, "CO2": 0.20, "CO": 0.02, "CH4": 0.01, "DME": 0.05}
    got = case_with(QUADRATIC, feed=0.8, outlet=outlet)
    assert abs(got["conversion_percent"] - 45.0) < 0.0002


def test_quadratic_calibration_conversion_low():
    """「每个数组的三个数依次是常数项、一次项和二次项。」"""
    outlet = {"methanol": 1.05, "CO2": 0.06, "CO": 0.02, "CH4": 0.005, "DME": 0.01}
    got = case_with(QUADRATIC, feed=1.2, outlet=outlet)
    assert abs(got["conversion_percent"] - 12.5) < 0.0002


def test_internal_standard_cancels_global_sensitivity():
    """「每个数组的三个数依次是常数项、一次项和二次项。」"""
    outlet = {"methanol": 0.44, "CO2": 0.20, "CO": 0.02, "CH4": 0.01, "DME": 0.05}
    low = case_with(QUADRATIC, feed=0.8, outlet=outlet, n2_area=12000.0, sensitivity=0.65)
    high = case_with(QUADRATIC, feed=0.8, outlet=outlet, n2_area=180000.0, sensitivity=1.8)
    assert abs(low["conversion_percent"] - 45.0) < 0.0002
    assert abs(high["conversion_percent"] - 45.0) < 0.0002


# ---------- 难点 2：含碳产物衡算 ----------

def test_selectivity_dme_has_two_carbons():
    """「各值是相应产物碳摩尔流量占全部含碳产物碳摩尔流量之和的百分数，保留 4 位小数。」"""
    got = case_with(LINEAR)
    assert abs(got["selectivity_percent"]["CO2"] - 25.0) < 0.0002
    assert abs(got["selectivity_percent"]["DME"] - 50.0) < 0.0002


def test_carbon_balance_includes_unreacted_methanol_and_dme_carbon():
    """「出口甲醇与全部含碳产物的碳摩尔流量之和，除以进料甲醇碳摩尔流量后乘 100，保留 4 位小数。」"""
    got = case_with(LINEAR)
    assert abs(got["carbon_balance_percent"] - 90.0) < 0.0002


def test_second_dme_case_uses_formula_carbon_number():
    """「二甲醚按 DME（C2H6O）计。」"""
    outlet = {"methanol": 0.45, "CO2": 0.12, "CO": 0.03, "CH4": 0.02, "DME": 0.08}
    got = case_with(LINEAR, feed=0.9, outlet=outlet)
    assert abs(got["selectivity_percent"]["DME"] - 48.4848) < 0.0002
    assert abs(got["carbon_balance_percent"] - 86.6667) < 0.0002


# ---------- 难点 3：表面活性金属位点归一化 ----------

def test_tof_excludes_inert_diluent_from_catalyst_mass():
    """「惰性稀释剂不计入活性金属量」"""
    outlet = {"methanol": 0.5, "CO2": 0.10, "CO": 0.05, "CH4": 0.05, "DME": 0.10}
    light = dict(BASE_CATALYST)
    heavy = dict(BASE_CATALYST)
    heavy["diluent_mass_g"] = 1.25
    a = case_with(LINEAR, outlet=outlet, catalyst=light)
    b = case_with(LINEAR, outlet=outlet, catalyst=heavy)
    assert abs(a["tof_s_inverse"] - 0.544805) < 0.000002
    assert abs(b["tof_s_inverse"] - 0.544805) < 0.000002


def test_tof_scales_with_metal_dispersion():
    """「表面活性金属占总活性金属的摩尔分数」"""
    outlet = {"methanol": 0.5, "CO2": 0.10, "CO": 0.05, "CH4": 0.05, "DME": 0.10}
    half = dict(BASE_CATALYST)
    half["metal_dispersion_fraction"] = 0.09
    full = dict(BASE_CATALYST)
    full["metal_dispersion_fraction"] = 0.18
    a = case_with(LINEAR, outlet=outlet, catalyst=half)
    b = case_with(LINEAR, outlet=outlet, catalyst=full)
    assert abs(a["tof_s_inverse"] - 1.089609) < 0.000002
    assert abs(b["tof_s_inverse"] - 0.544805) < 0.000002


def test_tof_uses_active_metal_molar_mass():
    """「计算时用已转化甲醇的摩尔数除以催化剂表面活性金属摩尔数和反应时间」"""
    outlet = {"methanol": 0.5, "CO2": 0.10, "CO": 0.05, "CH4": 0.05, "DME": 0.10}
    copper = dict(BASE_CATALYST)
    palladium = dict(BASE_CATALYST)
    palladium["active_metal_molar_mass_g_per_mol"] = 106.42
    a = case_with(LINEAR, outlet=outlet, catalyst=copper)
    b = case_with(LINEAR, outlet=outlet, catalyst=palladium)
    assert abs(a["tof_s_inverse"] - 0.544805) < 0.000002
    assert abs(b["tof_s_inverse"] - 0.912380) < 0.000002
