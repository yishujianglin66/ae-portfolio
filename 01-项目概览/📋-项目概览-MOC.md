---
tags: [MOC, 项目概览]
---

# 项目概览

> AE-Knowledge-Vault 是一套多软件集成的风格化视频剪辑知识体系与自动化管线，覆盖 AE、DaVinci Resolve、Silhouette 2026、Topaz Video AI、Blender、FFmpeg、RunwayML/Pika、Adobe 全家桶（PR/PS/AME）等十余款软件。

---

## 当前项目主线：ae_agent_pipeline.py v2.0

> 五层架构（感知 → 理解 → 规划 → 执行 → 反馈）+ 核心基础设施层，已集成全部新软件。

### 已集成软件模块
| 模块 | 类名 | 功能 |
|------|------|------|
| Topaz Video AI | TopazEnhancer | 视频增强/超分/补帧/降噪 |
| DaVinci Resolve | DavinciColorist | 调色 + 12 个预设（含木偶风格） |
| RunwayML / Pika | AIVideoGenerator | AI 视频生成（Text-to-Video） |
| Blender | Blender3DIntegrator | 3D 建模/渲染/Python 自动化 |
| Adobe 全家桶 | AdobeSuiteIntegrator | PS/PR/AME 集成 + 木偶材质预设 |
| MediaPipe | MediaPipeIntegrator | 手势/姿态/面部跟踪 |
| Silhouette 2026 | SilhouetteExecutor | 遮罩抠像/修复 |
| FFmpeg | MediaPreprocessor | 素材预处理/转码 |
| Librosa | LibrosaAudioAnalyzer | BPM/节拍/情绪检测 |
| 木偶流水线 | PuppetWorkflowOrchestrator | 木偶风格化全流程编排 |

### 核心基础设施（core/）
- `config.py` — 配置管理（9 个软件配置段 + 依赖检查）
- `state_machine.py` — 层次化状态机（7 个子状态机：AE/Silhouette/Topaz/Runway/Pika/Blender/FFmpeg）
- `workflow_orchestrator.py` — 依赖拓扑排序 + 并行执行（含新软件 TaskType）
- `event_bus.py` — 事件总线（含新软件 EventCategory）
- `llm_gateway.py` / `memory_store.py` / `observability.py` — 通用基础设施

---

## 历史项目渊源

本知识库由两个早期项目演化而来，相关文档已归档至 `archive/ae-vocal-remover/`：

### after-effects-mcp（AE MCP 服务端，仍有参考价值）
> Node.js MCP 服务器，让 AI 助手通过标准协议操控 After Effects。

- [[after-effects-mcp-README]] — 项目主页（13 个 MCP 工具）
- [[after-effects-mcp-CLAUDE]] — 创意知识库（12 动画原则、5000 预设、特效配方）

### ae-vocal-remover（已归档）
> AE CEP 扩展插件，AI 驱动的人声分离工具集。已被多软件集成架构取代。

- 📦 已归档至 `archive/ae-vocal-remover/`：
  - ae-vocal-remover-README — 旧 CEP 扩展安装指南
  - ae-vocal-remover-CLAUDE — 旧项目开发知识库
  - AUDIT_REPORT — 旧项目审计报告（2026-06-03）

> 💡 after-effects-mcp 的表达式库和创意知识仍可补充当前多软件集成架构。

---

## 快速入口

- 新手入门 → [[用户手册]] → [[开发手册]]
- 架构理解 → [[PHASE3_ARCHITECTURE]] → [[ae_agent_pipeline]]
- 部署安装 → [[setup_guide]] → [[model-server-README]]
- 代码质量 → [[anti-patterns]] → [[design-patterns]]
- 阶段历程 → [[📊-阶段报告-MOC]]（Phase 1 ~ Phase 8）
- 知识体系 → [[🎬-风格化剪辑知识库-MOC]]

---

> 返回 → [[🏠-AE知识中心]]
