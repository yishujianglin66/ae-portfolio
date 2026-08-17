# Plan B 稳定性子系统收口

> 日期：2026-08-17 ｜ 角色：EmbeddedFirmwareEngineer ｜ 范围：`core/engine_watchdog.py` + `pipeline/flagship_runner.py` + 网关 `/metrics`

把**嵌入式固件稳定性纪律**映射到视频旗舰管线：看门狗、非易失状态镜像、故障转移/背压、崩溃恢复。
目标——管线在 Adobe 引擎（AE/PR/Resolve）掉线、假死、崩溃时**自愈且不静默降级**，并让健康状态**常态化可观测**。

---

## 一、五大支柱（固件纪律 → 软件映射）

| 阶段 | 固件原语 | 软件实现 | 状态 |
|---|---|---|---|
| P0-1 | 子进程孤儿树回收 | `kill_process_tree` / `kill_process_tree_by_name`（双检 `tasklist`+`taskkill`，含编码修复） | ✅ |
| P0-2 | 引擎看门狗 + 假死自愈 | `ensure_ready` 杀树重启闭环 + `_watchdog_loop` 常驻巡检（`AEKV_WATCHDOG=1`） | ✅ |
| P1 | 故障转移一致性 | 降级改为 **opt-in**（`AEKV_ENGINE_FALLBACK=1`）；八类错误 postmortem（`core/pipeline_fault_policy.py`） | ✅ |
| P2 | 非易失状态 + 崩溃恢复 | `manifest` checkpoint / 断点续跑（`run_flagship_pipeline(resume_from=, run_id=)`） | ✅ |
| P3 | 资源配额 + 健康注册表 + 桥自愈 | `EngineHealthRegistry` / `ResourceQuota` / `restart_bridge`；观测进 `/metrics` | ✅ |

---

## 二、关键模块与函数

**`core/engine_watchdog.py`**
- `EngineHealthRegistry`（`ENGINE_HEALTH`）— 看门狗/编排器共享健康单一事实源（状态机 `unknown|launching|healthy|dead` + `last_seen_healthy_ts` + `launch_in_progress` + `snapshot()`）。
- `ResourceQuota`（`ENGINE_QUOTA`）— 每引擎 `RLock` 互斥 + 全局 `Semaphore`(默认 2) 背压，防并发双拉起 / 多引擎抢 GPU。
- `ensure_ready(engine, is_available, timeout)` — 拿配额 → 双检锁拉起 → 全程写注册表 → `finally` 释放配额。
- `restart_bridge(engine)` — 按 `.mcp.json` 唯一脚本子串精确定杀旧桥进程并重新拉起（**默认关闭**）。
- `engine_health_metrics_prometheus()` — 导出 `engine_health_*` / `engine_quota_*` 指标文本。
- 观测 getter：`get_engine_health` / `all_engine_health` / `quota_status` / `bridge_restart_enabled`。

**`pipeline/flagship_runner.py`**
- `_ensure_ae_bridge_ready` / `_ensure_pr_bridge_ready` / `_ensure_resolve_ready` 入口均调用 `start_ae_watchdog()`（三引擎路径全覆盖，幂等）。
- run 收尾把 `manifest["engine_health"]` + `manifest["resource_quota"]` 落盘（fail-safe）。
- CLI：`--resume` / `--run-id` / `--from` 断点续跑。
- P1 接线：`engine_fallback_enabled()`、`classify_failure()`、`write_postmortem()`（`postmortem.md` 按规格 §0.4）。

**网关 `puppet-automation/src/api/main.py`**
- `_build_prometheus_metrics()` 经 guarded 局部 import 复用 `engine_health_metrics_prometheus()`，使 `/metrics` 暴露引擎健康与配额。

---

## 三、环境变量开关

| 变量 | 默认 | 作用 |
|---|---|---|
| `AEKV_WATCHDOG` | `0`（关） | `=1` 启动常驻巡检线程，监控 AE/PR/Resolve/ME 四引擎并把健康写注册表 |
| `AEKV_ENGINE_FALLBACK` | `0`（严格） | `=1` 允许 S3–S6 降级到 FFmpeg 真实处理；否则按规格 §0.3 中止并写 postmortem |
| `AEKV_BRIDGE_RESTART` | `0`（关） | `=1` 自愈时**一并重启 Bridge 桥进程**（有风险，需显式授权） |

> 三开关默认全关——系统零副作用运行；自愈/降级/桥重启均为显式 opt-in，符合"绝不悄悄改变行为"。

---

## 四、运行证据与观测

- **manifest**：每次 run 在 `output/<run_id>/manifest.json`，并镜像到 `reports/flagship_runs/`；含 `stages`（checkpoint）、`engine_health`、`resource_quota`、`resumed_from`。
- **postmortem**：失败时在 run 目录生成 `postmortem.md`，含八类错误分类（`BRIDGE_DOWN`/`LICENSE_MISSING`/`OUTPUT_CORRUPT`/`SCRIPT_SYNTAX`/`TIMEOUT`/`USER_CANCELLED`/`DISK_FULL`/`LICENCE_POPUP_BLOCKING`）+ 修复建议 + 已完成阶段。
- **/metrics**：`GET /metrics` 暴露 `engine_health_up{engine}`、`engine_health_last_seen_healthy_ts{engine}`、`engine_quota_max_concurrent|active|available`。

---

## 五、测试矩阵（44 用例全绿）

| 套件 | 用例 | 覆盖 |
|---|---|---|
| test_pipeline_fault_policy (P1) | 7 | 降级 opt-in + 八类 postmortem |
| test_flagship_resume (P2) | 4 | manifest 断点续跑 |
| test_engine_health_quota (P3) | 12 | 注册表 + 配额（含真并发互斥） |
| test_engine_watchdog (P0) | 3 | 看门狗基础 |
| test_watchdog_coverage | 3 | PR/Resolve 看门狗覆盖 |
| test_stability_integration | 3 | 真实就绪路径 + manifest 证据链 |
| test_bridge_selfheal | 8 | 桥规格/精确 PID/先杀后拉起/门控 |
| test_metrics_exposition | 4 | Prometheus 文本生成 |

运行：`py -3.11 -m pytest tests/test_pipeline_fault_policy.py tests/test_flagship_resume.py tests/test_engine_health_quota.py tests/test_engine_watchdog.py tests/test_watchdog_coverage.py tests/test_stability_integration.py tests/test_bridge_selfheal.py tests/test_metrics_exposition.py`

---

## 六、真实验证结论

- **真实杀树+重拉 AE**：PID 从 `24780→46996`，`AE running=True`，配额正确释放。✅
- **真实桥自愈**（授权 `AEKV_BRIDGE_RESTART=1`）：AE `26100→18404`、Bridge `15004→33992`，桥进程按唯一子串精确定杀、未误伤其它 python 进程；本轮无编码异常。✅
- **顺带修复**：`kill_process_tree` 的 `taskkill` 调用补 `encoding="utf-8", errors="replace"`，消除 Windows GBK 字节 `0xb3` 触发的 `UnicodeDecodeError`（与 P0-2 给 `is_process_running` 修过的同类坑）。✅

---

## 七、已知局限与后续

1. **桥 `is_available` 时序**：桥进程已被拉起，但 `is_available` 常因 AE 刚重启（约需 30s 完全就绪）或桥重连未完成而暂报 False。属时序/架构问题，非自愈逻辑缺陷；自愈把"整个子系统"拉回的目标已达成。建议桥侧加重连重试。
2. **/metrics 为进程内指标**：多副本一致性依赖网关既有 Redis（Step 3）；本仓库单实例足够。
3. **红线恪守**：全程未改动 `after-effects-mcp/src/index.ts`、`mcp-bridge-auto.jsx`。
