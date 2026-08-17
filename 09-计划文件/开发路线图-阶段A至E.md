# AE Knowledge Vault — 开发路线图 (阶段 A → E)

> 创建: 2026-07-23 | 状态: Phase B 进行中
> 最后整合: 2026-07-23 | 整合文档: [[2026-07-23_项目整体进度整合]]

## 总览

| 阶段 | 名称 | 状态 | 核心模块 |
|------|------|------|---------|
| A | 素材感知 | ✅ Stable | `scene_detector`, `beat_detector`, `whisper_subtitle` |
| B | 智能编排 | 🔧 In Progress | `ai_creative_planner`, `timeline_composer`, `transition_selector`, `subtitle_product` |
| C | IR 标准化 | 🔧 In Progress | `timeline_ir`, `preset_system` |
| D | 落轨执行 | 🔧 In Progress | `e2e_pipeline`, `pr_mcp_client`, `ae_mcp_client` |
| E | 审核优化 | 📋 Planned | `ir_validation`, `distributed_renderer` |

```
A: 感知 ──→ B: 编排 ──→ C: IR ──→ D: 落轨 ──→ E: 审核
 Stable     In Progress  In Prog   In Prog    Planned
```

---

## Phase A: 素材感知 — ✅ Stable

**目标**: 原始素材 → 结构化感知数据

| # | 能力 | 模块 | 状态 | 输出 |
|---|------|------|------|------|
| A1 | 场景检测 | `ae.scene_detector` | ✅ | 镜头切点 / 平均时长 |
| A2 | AI 镜头分割 | `ae.ai_scene_detector` | ✅ | Shot 列表 / 转场类型 |
| A3 | 节拍检测 | `ae.beat_detector` | ✅ | BPM / 节拍列表 / 段落 |
| A4 | 语音字幕 | `ae.whisper_subtitle` | ✅ | 带时间戳字幕段 |

**待办**: TransNetV2 模型缓存、多轨节拍对齐

---

## Phase B: 智能编排 — 🔧 In Progress

**目标**: 感知数据 + 创意 → 编排决策

| # | 能力 | 模块 | 状态 |
|---|------|------|------|
| B1 | AI 创意规划 | `ae.ai_creative_planner` | ✅ Stable |
| B2 | 时间线编排 | `ae.timeline_composer` | ✅ Stable |
| B3 | 转场智能选择 | `ae.transition_selector` | ✅ Stable |
| B4 | 字幕产品化 | `ae.subtitle_product` | ✅ Stable |
| B5 | 创意模式库 | `ae.creative_patterns` | ✅ Stable |

### B3 转场规则引擎 ✅

7 种风格 × 6 种内容关系 = 42 条规则。支持规则定制、PR 映射、时长推荐。36 项测试全部通过。

### B4 字幕预设 ✅

6 种风格预设：抖音风/B站风/电影风/极简风/游戏风/新闻风。含 SRT 解析、重叠修复、自动合并/拆分。36 项测试全部通过。

**待办**: LLM 增强转场选择、双语字幕、字幕动画 AE 导出

---

## Phase C: IR 标准化 — 🔧 In Progress

**目标**: 定义统一时间线中间表示 + 校验 + 导出

| # | 能力 | 模块 | 状态 |
|---|------|------|------|
| C1 | Timeline IR | `ae.timeline_ir` | 🔧 In Progress |
| C2 | 预设系统 | `ae.preset_system` | ✅ Stable |

### C1 IR Schema

| 数据结构 | 用途 |
|---------|------|
| `IRSequence` | 完整合成 (分辨率/帧率/轨道) |
| `IRTrack` | 单轨 (视频/音频/字幕/叠加) |
| `IRClip` | 素材片断 (时间/变换/特效/转场) |
| `IREffect` | 特效 (分类/参数/关键帧) |
| `IRTransition` | 转场 (类型/时长/缓动) |

**导出**: → PR MCP JSON (`export_to_pr_json`) → AE JSX (`export_to_ae_jsx`) → JSON (`export_to_json`)

**校验**: `validate_ir()` — 40+ 规则覆盖 (时间合法性/索引冲突/参数范围)

**待办**: AAF/FCPXML 导出、关键帧动画 IR 结构

---

## Phase D: 落轨执行 — 🔧 In Progress

**目标**: IR → 实际推轨到 PR/AE

| # | 能力 | 模块 | 状态 |
|---|------|------|------|
| D1 | E2E 管道 | `ae.e2e_pipeline` | 🔧 In Progress |
| D2 | PR MCP 集成 | `ae.pr_mcp_client` | ✅ Stable |
| D3 | AE MCP 集成 | `ae.ae_mcp_client` | ✅ Stable |

### D1 E2E Pipeline

```
Input ─→ Perception ─→ Orchestration ─→ IR Gen ─→ Placement ─→ Output
         (A:感知)       (B:编排)         (C:IR)     (D:落轨)      (E:审核)
```

**特性**: 检查点恢复、分段独立执行、PipelineContext 数据传递

**待办**: MCP 直接推轨 (跳过 JSON 导出)、实时管道监控 UI

---

## Phase E: 审核优化 — 📋 Planned

**目标**: 输出审核 + 质量保证 + 渲染优化

| # | 能力 | 模块 | 状态 |
|---|------|------|------|
| E1 | IR 校验 | `ae.timeline_ir.validate_ir` | 🔧 In Progress |
| E2 | 分布式渲染 | `ae.distributed_renderer` | 📋 Planned |

**待办**: 自动修复建议、人工审核 GUI、渲染农场对接

---

## 关键里程碑

| 里程碑 | 目标阶段 | 标志 |
|--------|---------|------|
| M1: 感知就绪 | Phase A ✅ | 场景/节拍/字幕可独立运行 |
| M2: 编排骨架 | Phase B ✅ | 规则引擎 + 样式预设可用 |
| M3: IR 标准化 | Phase C ✅ | Schema + 校验 + 导出就绪 |
| M4: 首条全流程 | Phase D | 端到端调通一条完整管道 |
| M5: 生产就绪 | Phase E | 人工审核 + 渲染稳定 |

---

## 整合优先级（2026-07-25 更新）

### ✅ 已完成
- **AE文字特效交接文档编写**（2026-07-25）：产出 `00-每日记录/2026-07-25_AE-文字特效-新会话交接文档.md`，约 300 行，完整覆盖 9 个章节（项目总览/任务进度/技术链路/核心文件/参数手册/陷阱警醒/渲染验收/新会话启动指南/附录），V3→V3.1→V4 全迭代经验已整合

### P0 - 本周
1. **TextFX Showcase 效果增强**：验证 AE 2025 效果清单 → 测试 V2 JSX → 封装特效组合生成器
2. **Phase B3/B4 完善**：转场规则引擎 42 条规则落地、字幕产品化 6 种预设

### P1 - 本月
3. **Phase C IR 标准化**：Timeline IR Schema 完善 + AAF/FCPXML 导出
4. **Phase D E2E 首条全流程**：M4 里程碑，端到端调通一条完整管道
5. **TextFX Showcase 产品化**：一键命令 + 自定义参数 + 批量生成

### P2 - 下月
6. **Phase E 审核优化**：IR 校验增强 + 分布式渲染
7. **execute-atom-script 缺口修复**：向开源项目提 PR

---

## 技术债与风险

| # | 项目 | 风险 | 优先级 |
|---|------|------|--------|
| 1 | 无统一测试框架 | 回归风险 | High |
| 2 | LLM 依赖外部 API | 离线不可用 | Medium |
| 3 | MCP 桥接稳定性（AE 2025 兼容性） | 版本兼容 | Medium |
| 4 | 完整版 JSX（491 行）AE 2025 兼容性问题 | 高级效果受阻 | Medium |
| 5 | 两套管线并存（UnifiedVideoPipeline vs E2E Pipeline） | 维护成本 | Medium |

### 管线收敛决策 (G5)

经代码审查盘点（详见 [[代码审查标准与流程]]），当前实际存在**三套**执行入口：`ae/ae_agent_pipeline.py`（5885 行单体，历史主干）、`puppet-automation/`（MOC 已定为"当前主线"，19 个引擎）与 `UnifiedPipeline v2`（quality-gate 引用）。为遏制 G5 类技术债扩散，明确：

- **唯一主干 = `puppet-automation/`**。新功能只在此扩展，不在旧单体上追加。
- **旧单体 `ae/ae_agent_pipeline.py` 标记 deprecation**：保留运行但不作为新开发目标；其拆分的优先任务是降到 <800 行/文件（状态机/LLM/事件/编排分离），拆分出的模块转入 `puppet-automation/` 或 `core/`。
- **`UnifiedPipeline v2` 与 E2E Pipeline 二选一并明确归属**，避免"两套并存"长期悬而未决；审查时对照本决策判定代码管线归属。

---

> 返回 → [[📝-计划文件-MOC]]
