# 甲醇重整动力学数据反演

甲醇重整中试装置会连续保存多组反应记录。每组记录包含温度、进料流量、入口甲醇浓度、体积膨胀因子、催化剂质量、运行时间和一张出口色谱图。操作员需要把这些记录合并，估出可交给反应工程组继续使用的本征动力学参数。

## 现状

`/app/main.py` 目前沿用早期的快速估算，把每次记录看到的转化率直接折算成反应速率再做线性回归。近期的记录里，温度越高转化率越高，得到的活化能会随转化率水平明显漂移；同一温度下改变甲醇稀释比后，反应级数也对不上。运行时间拉长到十几小时后，模型总是报一级失活，零时刻转换频率也比新鲜催化剂的标定值低。

## 输入

运行方式是 `python3 /app/main.py <输入文件>`。输入文件是 UTF-8 JSON：

```json
{
  "run_id": "批次编号",
  "reference_temperature_k": 623.15,
  "reference_concentration_mol_m3": 100.0,
  "catalyst": {"active_sites_mmol_per_g": 0.18},
  "gc_calibrations": {
    "methanol": [0.02, 1.1, 0.015],
    "CO2": [0.01, 0.98, 0.006],
    "CO": [0.008, 1.05, 0.004],
    "CH4": [0.005, 1.1, 0.002],
    "DME": [0.012, 0.72, 0.01]
  },
  "runs": [
    {
      "run_id": "r1",
      "temperature_k": 620.0,
      "time_on_stream_h": 2.0,
      "inlet_methanol_concentration_mol_m3": 20.0,
      "volumetric_expansion_factor": 0.8,
      "feed_methanol_mol_per_s": 0.00006,
      "catalyst_mass_g": 0.5,
      "internal_standard_mol_per_s": 0.00001,
      "outlet_peak_areas": {
        "N2": 25000.0,
        "methanol": 120000.0,
        "CO2": 50000.0,
        "CO": 5000.0,
        "CH4": 500.0,
        "DME": 300.0
      }
    }
  ]
}
```

每张出口色谱图使用同一组相对校准系数。系数依次是常数项、一次项和二次项，峰面积比与摩尔比的关系为二次多项式；出口氮气摩尔流量等于该次记录的 `internal_standard_mol_per_s`。多组记录的转化率由进料甲醇摩尔流量与出口甲醇摩尔流量之差除以进料甲醇摩尔流量得到，出口流量用氮气内标和对应物种的响应曲线反算。

每次记录来自积分固定床反应器，入口甲醇浓度、体积膨胀因子、进料摩尔流量和催化剂质量都在记录中给出。反应器入口到出口的甲醇浓度随转化率和体积膨胀变化。失活模型只允许填 first_order 或 second_order；两种模型分别按常见的一级和二级失活速率方程解释。

## 要交付的内容

修改 `/app/main.py` 及其同目录模块，用全部记录共同反演参考温度下的反应速率常数、活化能、反应级数和失活常数。参考温度为 623.15 K，参考浓度为 100 mol m-3。

程序向标准输出写一个 JSON 对象。对象只含以下字段：

- `run_id`：与输入相同。
- `activation_energy_kj_mol`：活化能，单位 kJ mol-1，保留 3 位小数。
- `reaction_order`：以入口甲醇浓度为基准的反应级数，保留 4 位小数。
- `deactivation_model`：`first_order` 或 `second_order`。
- `deactivation_constant_per_h`：失活常数，单位 h-1，保留 4 位小数。
- `rate_constant_at_reference_mol_g_s`：参考温度、参考浓度和零时刻下的反应速率，单位 mol g-1 s-1，保留 9 位小数。
- `initial_tof_s_inverse`：参考温度、参考浓度和零时刻下的转换频率，单位为 s-1，保留 6 位小数。
- `mean_carbon_balance_percent`：各次记录碳平衡百分数的算术平均值，保留 4 位小数。

所有数值按四舍五入处理。程序参数个数不对时退出码为 2，标准输出为空。同一份输入重复运行应得到相同结果。

## 约束

- 只使用 `/app` 内已有文件和 Python 标准库，不访问网络。
- `/app/sample_run.json` 是一份脱敏设备记录，可用于自检。
- 输入至少包含三条记录；温度、流量、浓度和催化剂质量均为正数，体积膨胀因子非负。
