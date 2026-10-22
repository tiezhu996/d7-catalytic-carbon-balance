# 参考解说明

## 三个难点

| 编号 | 错误认知 | 正确知识 | 对应测试（`tests/scoring.json`） |
|---|---|---|---|
| difficulty_1 | 面积比可以按线性斜率直接换算成摩尔比，二次项可以忽略 | 相对峰面积与摩尔比是二次关系，需要解非负实根；内标比值抵消整体灵敏度缩放 | `test_quadratic_calibration_conversion_moderate`、`test_quadratic_calibration_conversion_low`、`test_internal_standard_cancels_global_sensitivity` |
| difficulty_2 | 选择性按产物总摩尔流量归一，碳平衡只把各峰流量相加 | 各产物先乘碳原子数；DME 有两个碳；碳平衡还要包含未反应甲醇 | `test_selectivity_dme_has_two_carbons`、`test_carbon_balance_includes_unreacted_methanol_and_dme_carbon`、`test_second_dme_case_uses_formula_carbon_number` |
| difficulty_3 | TOF 用装填床总质量或总金属量归一 | TOF 分母是表面活性金属摩尔数，只使用催化剂质量、金属负载量、活性金属摩尔质量和分散度 | `test_tof_excludes_inert_diluent_from_catalyst_mass`、`test_tof_scales_with_metal_dispersion`、`test_tof_uses_active_metal_molar_mass` |

## 参考解文件

- `solution/app/main.py`：入口、输出字段和四舍五入。
- `solution/app/calibration.py`：二次校准曲线反算。
- `solution/app/balances.py`：转化率、碳基选择性和碳平衡。
- `solution/app/activity.py`：表面活性金属位点和 TOF。
- `solution/solve.sh`：安装参考解，并根据 `HTB_SKIP` 用精确片段退回难点。

## 核心公式

```text
x = (-c1 + sqrt(c1^2 + 4*c2*(area_ratio-c0))) / (2*c2)
n_i = n_N2 * x_i
conversion = 100 * (n_MeOH_in - n_MeOH_out) / n_MeOH_in
selectivity_i = 100 * C_i*n_i / sum(C_j*n_j)
carbon_balance = 100 * (n_MeOH_out + sum(C_j*n_j)) / n_MeOH_in
TOF = (n_MeOH_converted/3600) / (m_cat*loading/M_metal*dispersion)
```

推导和独立复核见 `research/derivations.md`、`research/verify_gc.py` 与 `research/verify_gc.out.json`。

## 容差依据

- 输出保留 4 位小数百分比或 6 位小数 TOF。
- 测试容差为百分数 `2e-4`、TOF `2e-6`，大于浮点运算抖动，小于任一错误口径的偏差。
- 代表性二次曲线错误会把 45% 算成约 32%，DME 碳数错误会把 50% 选择性算成 33.3%，TOF 漏掉分散度会造成数倍偏差。

## 权重依据

- gate：入口可用、参数错误退出码，不计分。
- difficulty_1 合计 0.34：三个输入覆盖中等转化率、低转化率和检测器灵敏度漂移。
- difficulty_2 合计 0.33：三个输入覆盖 DME 碳数、碳平衡和另一组物料组成。
- difficulty_3 合计 0.33：三个输入分别改变稀释剂、分散度和金属摩尔质量。

## 数据来源

- 真实组成：Zenodo 记录 16569478，`Results.csv` 的 330 °C、MeOH:H2O=1:1、1.0 mL/min 行。
- 重编码规则：见 `research/data-notes.md`。
- 隐藏输入：测试内按已知出口摩尔流量和校准曲线构造，独立复核见 `research/verify_gc.py`。

## 答案隔离

- [x] 镜像只复制 `environment/app/`，不复制 `tests/`、`solution/` 或 `.git/`。
- [x] 注释和文件名没有说明缺陷位置或正确算法。
- [x] Dockerfile 直接复制原始版本，不使用先复制正确版本再改坏的做法。
