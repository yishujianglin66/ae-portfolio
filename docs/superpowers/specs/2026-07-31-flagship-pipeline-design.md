# Flagship E2E Pipeline v1 · 科研级规格说明书

> 版本：v1.1（审阅修订）  
> 日期：2026-07-31  
> 验收等级：科研级 · 零 mock · 真实产物可检测  
> 链路代号：`ae_to_premiere_final_delivery`

---

## 0. 本设计的核心理念（不可修改原则）

1. **零 mock 原则**：AE / Premiere / DaVinci Resolve / Media Encoder 四个核心外部软件必须以 **真实 Bridge（_bridge_available=true）** 完成调用；若引擎回退到 JSX 文件模式或返回模拟 EngineResult，则本链路判失败。
2. **可检测原则**：通过的结论不可来自日志/日志截图，必须来自：
   - 可播放的 `final.mp4` 文件（ffprobe 技术参数合规）
   - 可在 AE/PR/DR 原生软件中打开的 `.aep` / `.prproj` / `.drp` 工程文件
   - 关键帧截图 + 节拍点时间线截图（肉眼可复核）
3. **全链路可失败原则**：若 S0 健康检查不通过，直接中止，不跳过任何阶段也不降级使用替代引擎（科研级不做"差不多能用"）。
4. **失败必有根因文档**：任何阶段失败后，自动生成 `postmortem.md`，错误分类为 `BRIDGE_DOWN / LICENSE_MISSING / OUTPUT_CORRUPT / SCRIPT_SYNTAX / TIMEOUT / USER_CANCELLED / DISK_FULL / LICENCE_POPUP_BLOCKING` 八类之一，并附修复建议。

---

## 1. 验收范围（8 阶段）与成功准则 5 条

### 1.1 阶段定义

| 阶段号 | 名称 | 真实引擎 | 真实输入 | 真实产物（必须落盘） |
|---|---|---|---|---|
| S0 | 环境健康门 | `core/health_checker.py`（新） | 无 | `S0_health.json`：`passed=true`，所有必需引擎 `available=true` |
| S1 | 素材规范化 | FFmpeg | 用户提供 3 条 mp4 + 1 条 wav | 3 条 1920×1080 H.264 统一编码片段 + 1 wav，MD5 落盘 |
| S2 | 节拍分析 | Whisper + Librosa | S1 音频 | `beats.json`（BPM + drop 数组 ≥4）+ `waveform.png` |
| S3 | AE 木偶风格化合成（3 段并行） | After Effects 真实 Bridge | S1 视频 + ae_presets/ 中的真实 preset | `FlagshipAE.aep` + 3 段 `.mov` 成品（每段 ≥3s） |
| S4 | PR 自动粗剪 & 卡点 | Premiere Pro 真实 Bridge | S3 3 段 mov + S2 beats + S1 wav | `FlagshipPR.prproj` + `timeline.xml` + 时间线截图（drop 标记点可见） |
| S5 | DaVinci Resolve 调色 | DaVinci Resolve Scripting API (Python/Lua) | S4 timeline.xml + `color_lut.cube` | `FlagshipDR.drp` + `graded.mov` + 调色前后对比图 |
| S6 | 成片导出 | Media Encoder 真实队列（不走回退） | S4 或 S5 主序列 | `final.mp4`：H.264 1920×1080 24fps，时长 15±2s |
| S7 | 质量门 QG 独立检测 | `core/quality_gate.py`（增强） | 全部阶段产物 | `quality_gate_report.json` + `thumbnail_grid.jpg` |

前端 Dashboard 单独作为 **S8** 演示层（不计入流水线 passed，但属于交付物 4）：admin JWT 登录 → 旗舰卡片 → Execute → 进度实时更新 → 预览弹出。

### 1.2 成功准则（5 条，全部满足才算科研级 PASS）

1. **S0-S7 全部阶段 `status=passed`（含 S7 QG 报告 passed=true）**
2. **S6 `final.mp4` ffprobe 满足**：`codec=h264 && 1910<=width<=1930 && 1070<=height<=1090 && 23<=fps<=25 && 13<=duration<=17`
3. **无回退**：S1/S3/S4/S5/S6 日志中不出现 `mode=fallback` / `mock=true` / `simulated=true`（S1 FFmpeg 规范化阶段同样禁止 fallback，ffprobe 不可用时直接 fail 而非短路）
4. **QG 5 条具体规则**（见第 3 章 QG-1 至 QG-5）全部 passed
5. **前端可演示**：Dashboard 有旗舰流水线卡片，能展示某次 run 的 8 阶段进度、产物下载按钮、final.mp4 在线播放（截图/录屏留证）

---

## 2. 架构与模块划分（单一职责 & 清晰边界）

```
M1 健康检查 ──▶ 若 fail 整条中止
     │
     ▼
M3 Orchestrator (DAG 编排)
  S1(素材) → S2(节拍) → S3_0 / S3_1 / S3_2 (AE并行) → 合并→S4(PR) → S5(DR) → S6(AME) → M4 QG
                  │              │                │             │          │          │
                  ▼              ▼                ▼             ▼          ▼          ▼
              M2 assets     M0 AE引擎(真)     M0 AE引擎    M0 PR引擎  M0 DR引擎  M0 AME引擎
```

| 模块 | 路径 | 职责 | 对外接口 |
|---|---|---|---|
| M0 引擎 | `puppet-automation/src/engines/<name>/engine.py` 共 21 引擎 | 真实调用外部软件，返回 EngineResult | `async execute(action, **params) -> EngineResult` |
| M1 健康检查 | `core/health_checker.py` **新增** | 检查全部必需引擎+Bridge+磁盘空间+许可弹窗 | `check_pipeline_requirements(list[engine_name]) -> HealthReport` |
| M2 素材节拍 | `pipeline/stages/analysis.py` / `pipeline/stages/planning.py` | S1 规范化 + S2 节拍 | `run_stage_1_assets()` / `run_stage_2_beat(audio)` |
| M3 编排器 | `core/workflow_orchestrator.py` 增强 | DAG、重试(≤1)、失败resume、幂等 manifest | `Orchestrator.run(stage_graph, input_config)` |
| M4 质量门 | `core/quality_gate.py` 增强 | 独立读盘检测（非依赖引擎自报） | `inspect_outputs(run_id) -> QGReport` |
| M5 根因 | `core/failure_postmortem.py` 增强 | 八类错误自动归档 + 修复建议 | `run_postmortem(stage, error, logs) -> Path` |
| M6 前后端 | 后端 `src/api/dashboard_routes.py` + 前端 `ae-dashboard/src/FlagshipPipeline.tsx` **新增** | 旗舰流水线触发/进度/预览/下载 | 4 端点 + 1 React 卡片 |
| M7 CI | `.github/workflows/ci.yml` 修复 | 修复不存在引用 + Docker smoke | push/PR 自动 |
| M8 Docker | `Dockerfile` / `docker-compose.yml` / `nginx/nginx.conf` 修复 | 容器化部署 | `docker compose up -d` 可访问 |

**边界约束**：
- M0 引擎之间**不互相调用**，只收 Orchestrator 的 `execute`；
- M3 Orchestrator 不读取引擎内部状态，只判断 `EngineResult.success`；
- M4 QG 只读产物文件，不调用任何引擎；
- M6 前端对后端的通信：首选 WebSocket `/ws/flagship/{run_id}`，降级 5s 轮询 `/status`。

---

## 3. API 契约、目录、QG 规则

### 3.1 后端端点（`/api/v1/pipelines/flagship/*`，双认证）

| 方法 | 路径 | 入参 | 响应 |
|---|---|---|---|
| POST | `/execute` | `{ run_label, inputs{source_videos[3], source_audio, ae_preset, ae_comps[3], color_lut, export_preset, require_real_bridge=true, mock_if_unavailable=false}, options{...} }` | `{ run_id, status: "started" }` |
| GET | `/{run_id}/status` | 路径 | `{ run_id, overall, stage_summary{...}, total_elapsed_s }` |
| POST | `/{run_id}/resume` | 路径 + `{from_stage?}` | `{ resumed: true }` |
| GET | `/{run_id}/download/{stage}` | 路径 + `?part=manifest|final|report` | 文件下载（Content-Disposition） |
| WS | `/ws/flagship/{run_id}` | 握手 | 每 10s 推送 status 增量 |

入参约束：`source_videos.length==3`、`require_real_bridge===true`、`mock_if_unavailable===false` 否则 400。

### 3.2 Run 目录（固定结构）

```
output/flagship_{run_id}/
├── manifest.json  report.json
├── S0_health.json
├── S1_assets/{clip1..3}.mp4  bgm.wav  md5sums.txt
├── S2_beat/beats.json  waveform.png
├── S3_ae/FlagshipAE.aep  renders/{Comp_Intro,Comp_Main,Comp_Outro}.mov
├── S4_premiere/FlagshipPR.prproj  timeline.xml  screenshots/timeline_01.png
├── S5_davinci/FlagshipDR.drp  graded.mov  before_after_compare.jpg
├── S6_export/final.mp4  ame_queue_log.txt  ffprobe.json
├── S7_qg/quality_gate_report.json  thumbnail_grid.jpg
└── postmortem.md  (若失败)
```

### 3.3 QG 规则（不可动摇阈值）

| 编号 | 检测 | 独立方法 | 通过阈值 |
|---|---|---|---|
| QG-1 | 成片非黑/白 | 20 帧均匀抽样，平均亮度 + 帧方差 | 平均亮度 ∈ [0.05, 0.95]，帧方差 ≥ 0.02 |
| QG-2 | 时长 ±2s | ffprobe duration | 13 ≤ dur ≤ 17 秒 |
| QG-3 | 技术规格 | ffprobe 视频流 | h264 && 1920±10 && 1080±10 && 24±1 fps |
| QG-4 | 节拍对齐误差 | S2 drop vs S4 XML 标记点 | 每个 drop 点偏移 **< 80ms**（v1 首版阈值；v2 收紧至 <40ms） |
| QG-5 | 调色节点 ≥3 | 解析 drp 元数据 / 节点截图识别 | 实际节点数 ≥ 3 且至少 1 个 LUT 类节点 |

---

## 4. 测试策略（T0-T4 五层）

| 类型 | 范围 | 允许 mock | 运行 | 命令 |
|---|---|---|---|---|
| T0 单元 | M0 内部分支 / M1-M5 逻辑 | 是（标注 `production_eligible=False`） | 每次提交 | `puppet-automation/> pytest tests/ -m 'not real_*'` |
| T1 引擎 Smoke 实跑 | 每个关键引擎各跑 1 个最小真实动作 | **否** | 旗舰跑之前 + 每周 | `pytest tests/test_*_engine.py -m real_ae` 等 |
| T2 旗舰 E2E 真跑 | S0→S7 全链路 | **否** | 交付前 + CI 手动（workflow_dispatch） | `pytest tests/test_flagship_e2e.py` |
| T3 人眼复核面板 | 最终 mp4 播放、关键图对比 | 否 | 每次 T2 后 | Dashboard 「复核」按钮 → report 中增加 `human_signed_off=true` |
| T4 可部署性 | docker compose 起 + 停 | 允许内部 mock 外部软件 | 每次提交 Dockerfile | `docker compose up --build -d` + `curl /health` 60 次 |

---

## 5. 风险对策（内置缓解机制）

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| Bridge 中途掉线 | 中 | 阶段 fail | 每阶段前强制 ping + 自动 retry 1 次；仍失败归类 `BRIDGE_DOWN` |
| AME 队列死锁 | 中 | S6 超时 | 启动 AME 前清空旧队列 + 超时阈值 1800s + 超时分类 `TIMEOUT_AME` |
| DR 中文路径编码问题 | 高 | S5 导入 fail | 所有 run_id 目录及文件名强制 ASCII（`^[A-Za-z0-9_-]+$`），并在 M1 预检 |
| AE 许可证弹窗阻塞 | 高 | S3 一直挂 | M1 阶段加「屏幕截图 + 弹窗模板匹配」；命中则 `close_dialog.ps1` 自动关，失败归类 `LICENCE_POPUP_BLOCKING` |
| WebSocket 断连 | 低 | UI 进度中断 | 前端 5s 轮询 `/status` 备用通道；重连后自动补齐缺失阶段 |
| 磁盘空间不足 | 中 | 写入 fail | M1 预检查 < 50GB 直接 fail；S6 前二次检查 < 10GB fail；错误归类 `DISK_FULL` |
| PR Bridge JSX 执行超时 | 中 | S4 阶段 fail | 单条 JSX 超时 120s + S4 总超时 600s；超时归类 `TIMEOUT`；重试 1 次后仍失败则中止 |

---

## 6. 交付物清单（科研级验收物）

1. **代码交付**：
   - 新文件：`core/health_checker.py`、`ae-dashboard/src/FlagshipPipeline.tsx`、`tests/test_flagship_e2e.py`、`tests/test_health_checker.py`、`tests/test_quality_gate_flagship.py`
   - 增强：`core/workflow_orchestrator.py`、`core/quality_gate.py`、`core/failure_postmortem.py`、`puppet-automation/src/api/dashboard_routes.py`、`puppet-automation/src/engines/{ae,premiere,davinci,media_encoder,ffmpeg,whisper}/engine.py`（各补 Bridge smoke 探测）、`Dockerfile`、`docker-compose.yml`、`.github/workflows/ci.yml`
2. **真实运行产物包**（至少 1 次完整 run）：`output/flagship_*/` 整目录，含 final.mp4、三个原生工程、三张关键检测图
3. **Dashboard 演示证据**：登录 → Execute → 进度满格 → 预览弹出，录屏或 ≥6 张连续截图
4. **可部署性证据**：`docker compose up -d` 后 60s `/health` 全部 200 的日志；本地 `act` 跑 CI.yml 两份 job 全绿的截图
5. **本规格说明书（本 md）**，与 `docs/superpowers/plans/` 下一步执行计划一一对应
6. 若过程中发生过失败并修复，**每次失败必须附 `postmortem.md`**（即使后来又成功了，也要留存以证明科研级严谨）
7. **`core/health_checker.py` 单元测试覆盖率 ≥ 90%**（健康门是整条链路的守门员，必须最高覆盖；`pytest --cov=core.health_checker --cov-fail-under=90`）

---

## 7. 规格自检（Spec Self-Review）

- ✅ 无 TBD / TODO / 含糊阈值（所有“约”、“左右”全部替换成 ± 数值）
- ✅ 各章节之间无矛盾：阶段与 QG 对应、QG 阈值与 ffprobe 字段一致、模块与路径对应
- ✅ 范围聚焦：本规格只定义「旗舰 E2E v1」一整条链路，不分散到横向扩展引擎
- ✅ 歧义消除：`require_real_bridge=true` / `mock_if_unavailable=false` 明确禁止回退；S5 引擎明确为 DaVinci Resolve Scripting API
- ✅ 科研级留痕：所有结论可追溯到落盘文件/截图/原生工程，不接受“日志里显示成功”这种证据
- ✅ v1.1 审阅修订：QG-4 首版放宽至 80ms（Librosa beat_track 固有 ±50ms 抖动）；无回退原则扩展至 S1；新增 PR JSX 超时风险对策；新增交付物 7（health_checker 覆盖率 ≥90%）

---

**下一步**：用户审阅本规格 → 调用 writing-plans 技能生成阶段化执行计划 → 按计划逐项实现并实跑验证。
