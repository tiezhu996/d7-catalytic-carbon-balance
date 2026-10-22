"""催化动力学参数反演的验收测试。

计分用例分成三组：高转化率下的床层积分修正、稀释条件下的反应级数、
以及长周期记录中的失活模型与初始 TOF。期望参数由本文件中的独立正演生成器设定，
不调用参考实现拟合。
"""

import json
import math
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
R_GAS = 8.314462618
T_REF = 623.15
C_REF = 100.0
N2_FLOW = 1.0e-5
N2_AREA = 25000.0
CALIBRATIONS = {
    "methanol": [0.02, 1.10, 0.015],
    "CO2": [0.01, 0.98, 0.006],
    "CO": [0.008, 1.05, 0.004],
    "CH4": [0.005, 1.10, 0.002],
    "DME": [0.012, 0.72, 0.010],
}
PRODUCT_CARBON = {"CO2": 0.85, "CO": 0.10, "CH4": 0.05, "DME": 0.0}
CARBON_NUMBER = {"CO2": 1, "CO": 1, "CH4": 1, "DME": 2}


def run_candidate(*args, timeout=CALL_TIMEOUT_SEC):
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


def activity(time_h, constant, model):
    if model == "first_order":
        return math.exp(-constant * time_h)
    return 1.0 / (1.0 + constant * time_h)


def forward_rate(conversion, spec, params, model):
    ea, order, kd, reference_rate = params
    inlet = spec["inlet_methanol_concentration_mol_m3"]
    expansion = spec["volumetric_expansion_factor"]
    concentration = inlet * (1.0 - conversion) / (1.0 + expansion * conversion)
    arrhenius = math.exp(-ea * 1000.0 / R_GAS * (1.0 / spec["temperature_k"] - 1.0 / T_REF))
    return (
        reference_rate
        * arrhenius
        * activity(spec["time_on_stream_h"], kd, model)
        * (concentration / C_REF) ** order
    )


def modulus(conversion, spec, params, model):
    intervals = 32
    step = conversion / intervals
    total = 0.0
    for index in range(intervals + 1):
        x = index * step
        weight = 1.0 if index in (0, intervals) else (4.0 if index % 2 else 2.0)
        total += weight / forward_rate(x, spec, params, model)
    return total * step / 3.0


def forward_conversion(spec, params, model):
    target = spec["catalyst_mass_g"] / spec["feed_methanol_mol_per_s"]
    low, high = 0.0, 0.999
    for _ in range(50):
        middle = (low + high) / 2.0
        if modulus(middle, spec, params, model) < target:
            low = middle
        else:
            high = middle
    return (low + high) / 2.0


def peak_area(amount, coefficients):
    ratio = amount / N2_FLOW
    area_ratio = coefficients[0] + coefficients[1] * ratio + coefficients[2] * ratio * ratio
    return area_ratio * N2_AREA


def make_payload(group, variant):
    if group == "integral":
        presets = {
            0: (dict(ea=92.0, order=1.0, kd=1.0e-12, rate=4.0e-4),
                [590.0, 600.0, 610.0, 620.0, 630.0, 640.0, 650.0], 20.0, 0.8, 6.0e-5, 0.5),
            1: (dict(ea=118.0, order=0.9, kd=1.0e-12, rate=8.0e-4),
                [600.0, 610.0, 620.0, 630.0, 640.0, 650.0], 14.0, 0.5, 5.0e-5, 0.6),
            2: (dict(ea=74.0, order=1.1, kd=1.0e-12, rate=2.5e-4),
                [585.0, 595.0, 605.0, 615.0, 625.0, 635.0], 28.0, 1.0, 7.0e-5, 0.45),
        }
        true, temperatures, concentration, expansion, flow, mass = presets[variant]
        specs = [
            dict(
                temperature_k=value,
                time_on_stream_h=0.0,
                inlet_methanol_concentration_mol_m3=concentration,
                volumetric_expansion_factor=expansion,
                feed_methanol_mol_per_s=flow,
                catalyst_mass_g=mass,
            )
            for value in temperatures
        ]
        model = "first_order"
    elif group == "order":
        presets = {
            0: (dict(ea=88.0, order=1.4, kd=1.0e-12, rate=2.0e-4), [2.0, 3.0, 5.0, 8.0, 12.0, 18.0, 25.0], 0.015, 0.4),
            1: (dict(ea=96.0, order=0.65, kd=1.0e-12, rate=3.0e-4), [1.5, 2.5, 4.0, 7.0, 11.0, 17.0, 24.0], 0.010, 0.2),
            2: (dict(ea=81.0, order=1.8, kd=1.0e-12, rate=1.2e-4), [3.0, 5.0, 8.0, 12.0, 16.0, 22.0, 30.0], 0.030, 0.6),
        }
        true, concentrations, mass, expansion = presets[variant]
        specs = [
            dict(
                temperature_k=T_REF,
                time_on_stream_h=0.0,
                inlet_methanol_concentration_mol_m3=value,
                volumetric_expansion_factor=expansion,
                feed_methanol_mol_per_s=1.0e-5,
                catalyst_mass_g=mass,
            )
            for value in concentrations
        ]
        model = "first_order"
    else:
        presets = {
            0: (dict(ea=90.0, order=0.0, kd=0.18, rate=2.5e-4), [0.0, 2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 16.0, 20.0], 0.02),
            1: (dict(ea=102.0, order=0.0, kd=0.45, rate=5.0e-4), [0.0, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0], 0.012),
            2: (dict(ea=77.0, order=0.0, kd=0.06, rate=2.2e-4), [0.0, 5.0, 10.0, 20.0, 30.0, 40.0, 50.0, 60.0], 0.025),
        }
        true, times, mass = presets[variant]
        temperatures = [610.0, 620.0, 630.0]
        concentrations = [5.0, 10.0, 15.0]
        specs = [
            dict(
                temperature_k=temperatures[index % len(temperatures)],
                time_on_stream_h=value,
                inlet_methanol_concentration_mol_m3=8.0e-6,
                volumetric_expansion_factor=0.0,
                feed_methanol_mol_per_s=8.0e-6,
                catalyst_mass_g=mass,
            )
            for index, value in enumerate(times)
        ]
        model = "second_order"

    params = (true["ea"], true["order"], true["kd"], true["rate"])
    noise = [1.0001, 0.99985, 1.00005, 0.9999, 1.00015, 0.9998, 1.0000, 0.99995, 1.00005]
    runs = []
    for index, spec in enumerate(specs):
        conversion = forward_conversion(spec, params, model)
        measured_methanol = spec["feed_methanol_mol_per_s"] * (1.0 - conversion) * noise[index % len(noise)]
        if group == "integral" and variant == 1 and index == 2:
            measured_methanol *= 0.82
        measured_conversion = (spec["feed_methanol_mol_per_s"] - measured_methanol) / spec["feed_methanol_mol_per_s"]
        converted_carbon = spec["feed_methanol_mol_per_s"] * measured_conversion
        amounts = {"methanol": measured_methanol, "N2": N2_FLOW}
        for species, fraction in PRODUCT_CARBON.items():
            amounts[species] = converted_carbon * fraction / CARBON_NUMBER[species]
        peaks = {
            species: peak_area(amounts[species], coefficients)
            for species, coefficients in CALIBRATIONS.items()
        }
        peaks["N2"] = N2_AREA
        runs.append(
            {
                "run_id": f"{group}-{variant}-{index + 1}",
                "temperature_k": spec["temperature_k"],
                "time_on_stream_h": spec["time_on_stream_h"],
                "inlet_methanol_concentration_mol_m3": spec["inlet_methanol_concentration_mol_m3"],
                "volumetric_expansion_factor": spec["volumetric_expansion_factor"],
                "feed_methanol_mol_per_s": spec["feed_methanol_mol_per_s"],
                "catalyst_mass_g": spec["catalyst_mass_g"],
                "internal_standard_mol_per_s": N2_FLOW,
                "outlet_peak_areas": peaks,
            }
        )
    return {
        "run_id": f"kinetics-{group}-{variant}",
        "reference_temperature_k": T_REF,
        "reference_concentration_mol_m3": C_REF,
        "catalyst": {"active_sites_mmol_per_g": 0.18},
        "gc_calibrations": CALIBRATIONS,
        "runs": runs,
    }


def analyze(payload):
    folder = Path(tempfile.mkdtemp(prefix="kinetics-"))
    folder.chmod(0o755)
    case = folder / "runs.json"
    case.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    case.chmod(0o644)
    proc = run_candidate(case)
    assert proc.returncode == 0, f"exit={proc.returncode} stderr={proc.stderr[-500:]}"
    return json.loads(proc.stdout)


def result_for(group, variant):
    return analyze(make_payload(group, variant))


# ---------- gate：入口与结构契约，不计分 ----------

def test_outputs_json_contract():
    """「程序向标准输出写一个 JSON 对象。对象只含以下字段：」"""
    got = result_for("order", 0)
    assert set(got) == {
        "run_id",
        "activation_energy_kj_mol",
        "reaction_order",
        "deactivation_model",
        "deactivation_constant_per_h",
        "rate_constant_at_reference_mol_g_s",
        "initial_tof_s_inverse",
        "mean_carbon_balance_percent",
    }
    assert isinstance(got["run_id"], str)
    assert got["deactivation_model"] in {"first_order", "second_order"}
    for field in (
        "activation_energy_kj_mol",
        "reaction_order",
        "deactivation_constant_per_h",
        "rate_constant_at_reference_mol_g_s",
        "initial_tof_s_inverse",
        "mean_carbon_balance_percent",
    ):
        assert isinstance(got[field], (int, float)) and not isinstance(got[field], bool)


def test_wrong_argument_count_exits_2():
    """「程序参数个数不对时退出码为 2，标准输出为空。」"""
    proc = run_candidate()
    assert proc.returncode == 2
    assert proc.stdout.strip() == ""


# ---------- 难点 1：高转化率下的床层积分修正 ----------

def test_activation_energy_integral_case_a():
    """「用全部记录共同反演参考温度下的反应速率常数、活化能、反应级数和失活常数。」"""
    got = result_for("integral", 0)
    assert abs(got["activation_energy_kj_mol"] - 92.0) < 0.6


def test_activation_energy_integral_case_b():
    """「用全部记录共同反演参考温度下的反应速率常数、活化能、反应级数和失活常数。」"""
    got = result_for("integral", 1)
    assert abs(got["activation_energy_kj_mol"] - 118.0) < 1.2


def test_activation_energy_integral_case_c():
    """「用全部记录共同反演参考温度下的反应速率常数、活化能、反应级数和失活常数。」"""
    got = result_for("integral", 2)
    assert abs(got["activation_energy_kj_mol"] - 74.0) < 0.9


# ---------- 难点 2：稀释条件下的反应级数 ----------

def test_reaction_order_dilution_case_a():
    """「参考温度为 623.15 K，参考浓度为 100 mol m-3。」"""
    got = result_for("order", 0)
    assert abs(got["reaction_order"] - 1.4) < 0.025


def test_reaction_order_dilution_case_b():
    """「参考温度为 623.15 K，参考浓度为 100 mol m-3。」"""
    got = result_for("order", 1)
    assert abs(got["reaction_order"] - 0.65) < 0.015


def test_reaction_order_dilution_case_c():
    """「参考温度为 623.15 K，参考浓度为 100 mol m-3。」"""
    got = result_for("order", 2)
    assert abs(got["reaction_order"] - 1.8) < 0.05


# ---------- 难点 3：失活模型与初始活性 ----------

def test_second_order_deactivation_model_case_a():
    """「失活模型只允许填 first_order 或 second_order」"""
    got = result_for("deactivation", 0)
    assert got["deactivation_model"] == "second_order"
    assert abs(got["deactivation_constant_per_h"] - 0.18) < 0.004


def test_initial_tof_case_b():
    """「参考温度、参考浓度和零时刻下的转换频率，单位为 s-1」"""
    got = result_for("deactivation", 1)
    expected = got["rate_constant_at_reference_mol_g_s"] / 0.00018
    assert got["deactivation_model"] == "second_order"
    assert abs(got["initial_tof_s_inverse"] - expected) / expected < 0.000002


def test_second_order_deactivation_model_case_c():
    """「失活模型只允许填 first_order 或 second_order」"""
    got = result_for("deactivation", 2)
    assert got["deactivation_model"] == "second_order"
    assert abs(got["deactivation_constant_per_h"] - 0.06) < 0.002
