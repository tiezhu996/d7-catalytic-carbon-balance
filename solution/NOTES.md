# 参考解说明

## 三个难点

| 编号 | 错误认知 | 正确知识 | 对应测试（`tests/scoring.json`） |
|---|---|---|---|
| difficulty_1 | 每次记录的转化率可以直接乘进料流量再除以催化剂质量，当作反应速率 | 高转化率下必须按积分固定床设计方程求 `W/F_A0`，沿床层积分，不能把出口转化率当作全程速率 | `test_activation_energy_integral_case_a/b/c` |
| difficulty_2 | 反应级数可以用进料摩尔流量的对数为自变量回归 | 反应级数以入口甲醇浓度为基准；进料流量和浓度不是同一个量，稀释实验必须用浓度 | `test_reaction_order_dilution_case_a/b/c` |
| difficulty_3 | 所有失活曲线都按一级指数衰减处理，初始活性取全程平均值 | 需要比较一级和二级失活模型，并用拟合的零时刻参考速率计算 TOF | `test_second_order_deactivation_model_case_a/c`、`test_initial_tof_case_b` |

## 参考解文件

- `solution/app/main.py`：入口、字段和四舍五入。
- `solution/app/calibration.py`：出口峰面积反算摩尔流量。
- `solution/app/gcdata.py`：转化率和碳平衡。
- `solution/app/reactor.py`：积分床层方程和速率计算。
- `solution/app/order.py`：反应级数输出口径。
- `solution/app/deactivation.py`：一级/二级失活模型选择。
- `solution/app/kinetics.py`：Levenberg-Marquardt 参数反演和汇总。
- `solution/solve.sh`：安装参考解，并通过 `HTB_SKIP` 用精确片段退回三个难点。

## 关键步骤

1. 用氮气内标和二次响应曲线反算每一步的出口甲醇流量。
2. 按 `r(x) = r_ref exp[-Ea/R(1/T-1/Tref)] a(t) [C(x)/Cref]^n` 建立反应速率。
3. 用活塞流设计方程 `W/F_A0 = ∫_0^X dx/r(x)` 计算每个记录的床层模数。
4. 以 `ln((W/F)_pred/(W/F)_obs)` 为残差，用多起点 LM 反演 `r_ref`、`Ea`、`n`、`k_d`。
5. 时间跨度足够时同时拟合一级和二级失活，二级模型残差明显更小时选择二级。
6. 用 `r_ref / active_sites` 得到零时刻 TOF。

## 容差依据

- 正演生成器给出口甲醇流量加入约 `1e-4` 的相对扰动；参考解输出的参数容差按独立复算误差和错误模型的偏差设定。
- Ea 容差约 0.6–1.2 kJ mol-1，反应级数容差 0.025–0.05，失活常数容差 0.002–0.004 h-1。
- 典型错误：差速近似会在高转化率下把 Ea 偏 30–50 kJ mol-1；用进料流量代替浓度会把级数算成接近 0；一级失活模型会漏掉二级衰减的长尾。

## 权重依据

- gate 不计分：入口结构、参数错误退出码。
- difficulty_1 合计 0.34：三条温度序列分别覆盖不同 Ea 和转化率。
- difficulty_2 合计 0.33：三条稀释序列覆盖低、中、高反应级数。
- difficulty_3 合计 0.33：两条失活曲线加一条初始 TOF 一致性。

## 数据来源

- 业务背景和样例色譜语义参考 Zenodo 记录 16569478 的公开甲醇蒸汽重整数据。
- 隐藏测试的入口组成和动力学参数由 `tests/test_outputs.py` 内的独立正演生成器生成；不代表原始实验的某一个具体样品。
- 独立复算与参数恢复过程记录在 `research/derivations.md`、`research/verify_kinetics.py`。

## 答案隔离

- [x] 镜像只复制 `environment/app/`，不复制 `tests/`、`solution/` 或 `.git/`。
- [x] 环境代码只保留粗略估算器，不包含测试参数和参考拟合结果。
- [x] Dockerfile 没有先复制正确版本再改坏。
