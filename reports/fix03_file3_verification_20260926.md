# FIX-03 文件闭单 F3-3｜integrations/mediapipe_integration.py（审计 R21：恒走 simulate 造正弦假关键点）

- 日期：2026-09-26｜串行队列：FIX-03 文件 3/8｜前置 `git status`：目标文件净，HEAD=`4c7a963`

## 开工前运行时取证（本轮审计断言验证）

```powershell
$ .venv\Scripts\python.exe -c "import importlib.util; print(importlib.util.find_spec('mediapipe'))"
MEDIAPIPE_SPEC= False     # ✅ R21"恒走 simulate"的前提断言成立（与 R20 不同，本条审计判断被证实）
```

## 变更（对齐契约 §1/§3）

| 位置 | 旧 | 新 |
|---|---|---|
| `MediaPipeResult.mode` 默认 | `"simulate"`（裸对象预填仿真） | `""`；新增字段 `is_simulated: bool = False` |
| `__init__` auto 解析（L207-217） | 依赖缺失 → 静默换轨 simulate | auto/real 均恒 `real`；依赖缺失由 `process_video` 显式报错 |
| `_init_detectors` except（L264） | 失败 → `self._mode="simulate"`（**把崩溃转成假数据**） | 记 `self._init_error`，mode 不变 |
| `process_video` | 无前置守卫 | real 且（依赖缺失/初始化失败/pose_detector 未就绪）→ `success=False + 明确 error`，`detections==[]` 零伪造 |
| `_process_video_simulate` | "MediaPipe 不可用时生成合理模拟数据"（自动兜底话术） | 仅限显式 `mode="simulate"`；返回 `is_simulated=True` 硬标记；docstring 明令"禁止驱动生产骨架" |

行为保持：显式 simulate 的离线联调能力未删（detections 生成逻辑原样）；`ae_agent_pipeline.py:693` 以 auto 构造——新语义下不再可能拿到假关键点（本轮取证并发现该类**只构造未调用任何方法**，属死装配，登记见下）。

## 真实验证输出

```powershell
$ .venv\Scripts\python.exe -m pytest tests/test_no_silent_simulate.py -q
8 passed in 0.87s        # topaz 4 例 + mediapipe 4 例（含走生产 except 路径的 _init_error 用例；
                         #  首版第 4 例断言自家桩=假覆盖，已按纪律重写为真走 _init_detectors 爆炸路径）
$ .venv\Scripts\python.exe -m pytest tests/test_puppet_style_integration.py tests/test_puppet_camera_stage.py -q
35 passed in 4.73s       # 含原 test_mediapipe_simulate_*（其显式 simulate 用法兼容，零测试修改）
$ .venv\Scripts\python.exe -m ruff check --config ruff.toml integrations/mediapipe_integration.py tests/test_no_silent_simulate.py
All checks passed!
```

## 新发现登记（不混入本提交）

- **N-2**：`ae_agent_pipeline.py:688-707` 构造 `MediaPipeIntegrator` 后全文无方法调用（grep `mediapipe_integrator.` 零命中）——死装配；其 `mediapipe_enabled=True` 日志具误导性。归属 FIX-45 可达性盘点处置（保留/删除需盘点裁决）。
- 骨架驱动侧（puppet 引擎）对 `is_simulated` 的消费端强制检查 → 归 FIX-09 扫描器 + puppet 引擎侧后续闭单补充（本文件已提供判据字段）。

## 复跑

```powershell
.venv\Scripts\python.exe -m pytest tests/test_no_silent_simulate.py::TestMediaPipeContract -q --timeout=180 -p no:cacheprovider
```
