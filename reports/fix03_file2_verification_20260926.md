# FIX-03 文件闭单 F3-2｜integrations/topaz_integration.py（审计 F3 + A 类假产物 + auto 静默降级）

- 日期：2026-09-26｜串行队列：FIX-03 文件 2/8｜前置 `git status`：目标文件净，HEAD=`34affbd`
- 用时说明：本文件含消费面 14 个测试文件全量回归（2:07），非"改完即提交"

## 开工前的运行时取证（修正审计 R20 的"无法证实"）

```powershell
$ Test-Path "D:\top\Topaz Video AI Pro"                     # True —— Topaz 确已安装
$ Test-Path "D:\top\Topaz Video AI Pro\topazcli.exe"        # False —— 无独立 CLI
$ python -c "... TopazEnhancer().is_available(); _find_cli()"
IS_AVAILABLE= True
CLI= D:\top\Topaz Video AI Pro\Topaz Video AI BETA.exe      # 代码候选表命中的是 GUI exe（--cli 变体）
```

→ **R20 修正**："topazcli.exe 无法证实"应表述为"CLI 入口为 `Topaz Video AI BETA.exe --cli` 变体，
exe 在盘、`--cli` 参数契约仍未经一次真实增强验证"（真实增强验证挂账至 FIX-03 批末真跑，避免本轮占用 GPU 跑长任务）。

## 变更（对齐契约 §1/§2.1/§3）

| 位置 | 旧 | 新 |
|---|---|---|
| `TopazResult.mode` 默认 | `"simulate"`（裸对象谎称已仿真执行） | `""`（未设置=未执行） |
| `enhance_video` auto 解析（L708-710） | auto→real 否则 simulate（静默换轨） | auto→恒 real；CLI 不可用时 `_run_real_mode` 自返显式失败 |
| real 失败降级（L731-739） | auto 下 real 失败**自动转 simulate 假成功** | **整块删除**——真实失败即失败；仿真预览须显式 `mode="simulate"` |
| `_run_simulate_mode` 产物（L876-891） | `TOPAZ_SIMULATED_OUTPUT` seek 撑大**写在期望路径**（骗过 exists()，审计 A 类） | 落 `<out>/simulated/<name>` + `.meta.json{execution_path:"simulated"}`；`result.output_path` 如实指向仿真位置 |

设计取舍（如实）：`TopazConfig.mode` 默认本就是 `"auto"`（非 simulate，审计所指 L220 实为 `TopazResult` 默认值——**又一处"引用行号与语义错位"，按实际落点修**）；显式 simulate 能力保留（演示价值）但三重隔离：期望路径不占用 + meta 标记 + mode 字段可判。

## 真实验证输出

```powershell
$ .venv\Scripts\python.exe -m pytest tests/test_no_silent_simulate.py -q --timeout=180
4 passed in 0.46s          # 新闸门文件首案：裸结果不谎称/auto失败禁转simulate/显式仿真落simulated+meta/配置默认值合规
$ .venv\Scripts\python.exe -m pytest <grep "topaz" 的全部 14 个消费面测试文件> -q --timeout=300
285 passed, 3 skipped in 127.31s (0:02:07)   # 含 test_topaz_engine.py、test_all_engines.py、p2 管线自检等
$ .venv\Scripts\python.exe -m ruff check --config ruff.toml integrations/topaz_integration.py tests/test_no_silent_simulate.py
All checks passed!
```

## 挂账（不掩）

- `--cli` 真实增强一帧验证 → FIX-03 批末统一真跑（需 GPU 时间，登记于此）。
- `ae_agent_pipeline.py:81 topaz_mode="auto"` 语义变化告知：auto 现在**失败即败**，不再有静默仿真产物——生产链行为更严，若某工作流依赖旧仿真兜底，会在其测试/运行中显式暴露（属预期）。

## 复跑

```powershell
.venv\Scripts\python.exe -m pytest tests/test_no_silent_simulate.py -q --timeout=180 -p no:cacheprovider
```
