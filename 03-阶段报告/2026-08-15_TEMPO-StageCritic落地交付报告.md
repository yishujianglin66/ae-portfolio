# 2026-08-15 TEMPO StageCritic 落地 — 交付报告

> 对应方案：`09-计划文件/2026-08-15_TEMPO与dots3-note知识提取与落地方案.md` 第六章 4 条验收标准。
> 本报告全部结论均来自真实运行产物，可复验。

## 一、验收标准实跑结果（4/4 PASS）

| # | 验收标准 | 结果 | 实跑证据 |
|---|---------|------|---------|
| ① | 黑帧注入在 S3→S4 边界被 critic 拦截 | ✅ PASS | `output/flagship_1786731687/`（`--inject-blackframe`）：critic S3 先 retry 再 abort，`critic_abort_report.json` value=0.325，S4-S6 未执行；`events.jsonl` 含 fault_injected/stage_retry/critic_verdict 完整链 |
| ② | 失败 run manifest 含完整 critic_reports 且可被 ExperienceHarvester 解析 | ✅ PASS | `scripts/verify_flagship_injection.py` 实跑：8 个 manifest 全部解析，13 条 critic_reports → 13 条 critic 中途观测入库；harvest 106 records / 442 阶段经验 / 117 错误模式 |
| ③ | QG 报告原子项级且失败项可回溯引入阶段 | ✅ PASS | `output/flagship_1786743738/S7_qg/quality_gate_report.json`：`atomic_checks` 9 项（gate/check/passed/value/threshold/introduced_by），`atomic_summary={total:9, passed:9, failed_items:[]}` |
| ④ | 数字孪生校正样本数 ≥ 原方案 3 倍 | ✅ PASS | 中途观测密度 4.2 观测/run（基线 1.0），4.2 倍；digital_twin 注入 442 观测，6 阶段时长参数全部更新 |

## 二、全链路真跑证据（线程E）

成功 run：`flagship_1786743738`（`logs/flagship_fullrun4_20260815.log`，总耗时 1067.8s）

- S0 健康检查 5/7（davinci/PR 冷启离线，非致命）→ S1 规范化 3 clips + music.wav → S2 BPM=129.2/beats=30/drops=12
- critic 三门全 continue（S2/S3/S5 各 value=0.850，原子项全过）
- S3 comp 创建 5.0/7.0/5.0s（AE Bridge native），渲染走 FFmpeg 降级（见遗留风险 R1）
- S4 PR 冷启后 bridge 就绪，`createNewSequence failed` 正确降级 FCP XML（timeline.xml 4586B / 12 markers）
- S5/S6：graded.mov 27.5MB → final.mp4（ffprobe 实证：h264 1920×1080 24fps + aac，15.0s，29.9MB）
- S7 质量门 5/5 门、原子项 9/9 通过；`manifest.json` status=completed / termination=success
- 经验回灌：harvest 105 records / 116 error patterns

中间故障验收 run（critic 真实拦截缺陷的证据）：
- `flagship_1786739355`：critic 拦下 comp 时长 4.0s < 5.0s 下限（retry→abort），见 `critic_abort_report.json`
- `flagship_1786740990`：critic 拦下 S5 时长不一致（调色 17s vs 粗剪基准 7s，根因为 critic 自身 max/sum 计算缺陷，已修复）

## 三、已修复问题清单（本轮 10 项）

| # | 缺陷 | 根因 | 修复 |
|---|------|------|------|
| 1 | `engine_task_dispatcher` 报 `name 'os' is not defined` | 缺 `import os/sys` | 补导入 |
| 2 | .mov 误用 h264 候选表，每 comp 浪费 ~8min | `suffix.lstrip('.')` 与带点 fmt_map 键永不匹配 | 去 lstrip |
| 3 | zip 截断丢失末尾 None 兜底，中文 AE 实例无法降级默认输出模块 | `zip(om, rs)` 按短列表截断 | `itertools.zip_longest` |
| 4 | .mov 输出首传 h264 模板，多一次无效探测 | 调用处模板误配 | 改传 `Lossless` |
| 5 | 正常产物被 critic abort | S3 comp 时长硬编码 4.0s < critic 5.0s 下限 | 模块级 `COMP_DURATIONS=(5.0,7.0,5.0)`，统一 3 处（comp_defs/FCP XML/total_duration×2） |
| 6 | S5 critic 误判时长不一致 | 粗剪基准用 `max`（单段 7s）而非 `sum`（总长 17s） | 改 `sum` |
| 7 | S4 `createNewSequence failed` 仍报 native_bridge 成功（clips_added=0） | 未检查 jsx 返回 `data["error"]` | 检查并降级 FCP XML |
| 8 | FlagshipManifestParser 将 critic abort run 误标成功、critic_reports 未解析 | 解析器未升级 | last_verdict 修正 + 中途裁决转 StageExperience（engine_used="critic"） |
| 9 | aerender 无 OM 模板时忽略 `-output`（写到默认 .avi），渲染成功被误判失败 | 判定只看期望路径 | dispatcher 增加同 stem 兄弟文件探测与归位 |
| 10 | 帧质量检测算法 4 处实证校准 | select 表达式无效 / H.264 黑帧 YAVG≈16 / 帧均值方差不可靠 | rawvideo 像素差分管道、yavg_min=20、min_frame_diff=1.0 |

## 四、遗留风险（暂无法在本环境闭环，已铺垫）

- **R1 AE OM 模板全不可用**：当前 AE 2025 实例所有命名输出模块模板（Lossless/ProRes/中文名）均报 "No output module template was found"；无模板时 aerender 实际可渲染但忽略 `-output`（证据：`flagship_1786743738/S3_ae/renders/Comp_Intro.avi`）。归位修复已就位，下轮 run 预计 AE 原生渲染打通；建议后续排查该实例的输出模块模板配置（或重建模板）。
- **R2 PR `createNewSequence` 返回 null**：PR 冷启后空项目状态下创建序列失败（诊断确认 has_project=True/created=False；`app.newProject` 会触发模态阻塞，勿在 bridge 脚本中调用）。已降级 FCP XML 路径保证产物完整；建议后续研究 `app.project.saveAs` 先行或预置工程。
- **R3 DaVinci Resolve 未安装**（D:\DaVinci Resolve\Resolve.exe 不存在）：S5 走 FFmpeg 调色等效路径。
- **R4 `AE_VAULT_SECRET_KEY` 未配置**：每次运行告警，Session/Token 重启失效（仅影响本地开发）。
- **R5 素材 Provider api_key 为空**：minimax_h3 等不可用，资产获取走本地真实素材缓存。
- **R6 SearchReplace 工具偶发 "save failed, reason: unknown"**：实际多数已生效，本轮全部改动均已用 Read/Grep/Select-String 逐项验证落盘。

## 五、清理结果

- 删除：`tmp/critic_test/`（3 个测试视频 fixture）、`tmp/diag_pr_sequence*.py`、`logs/critic_smoke_test.log`、3 份中途中断 run 的日志（fullrun/2/3，对应 manifest 与 critic 报告保留为证据）
- 保留证据：`logs/flagship_fullrun4_20260815.log`、`logs/flagship_blackframe_test.log`、4 个 critic run 目录（2 abort + 1 success + 1 故障注入）

## 六、回归测试

- `tests/test_midstep_critic.py + test_quality_gate_flagship.py + test_flagship_stages.py + test_flagship_e2e.py + test_harvester_state_path_unified.py`：**49 passed, 11 deselected**（最终一轮，含全部修复后复测）
- 全部改动模块 import 冒烟通过

## 七、下一步建议（P1）

1. **AE 原生渲染闭环**：修复 R1 后重跑，预期 S3 `execution_mode=native_cli` + 归位日志出现，并补充对应回归测试
2. **PR 序列创建**：按 R2 方案验证 `saveAs` 先行路径，打通 S4 native_bridge 真实上轨
3. **P1 候选比较自评**（TEMPO 方案）：critic 从单点裁决升级为多候选 value 比较
4. **vibe_search_bench 评测集** 与 **dots3-note 正式版接入**（等开源后重评估）
5. 为 `--inject-blackframe` 增加静帧/短时长两类故障注入开关，扩展故障演练矩阵
