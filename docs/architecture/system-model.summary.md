# AE-Knowledge-Vault 系统模型 — 架构理解

> 技能: `system-modeler` + `graphviz`
> 日期: 2026-08-17
> 范围: 当前状态 (current-state)
> 受众: 项目开发者、架构评审

---

## 系统定位

AE-Knowledge-Vault 是一个 **AI 驱动的视频后期制作自动化平台**，以 Adobe After Effects 为核心合成引擎，围绕"感知→理解→规划→执行→反馈"五层架构，集成 11 款专业软件引擎，提供从素材分析到最终交付的全链路自动化能力。

**核心价值主张**：将视频后期制作的领域知识（剪辑风格、运镜语言、节拍感知、特效参数）编码为可复用的知识库，通过 AI 管线实现"自然语言→专业级视频合成"的智能编排。

---

## 系统边界

### 内部模块 (11 个核心容器)

| 模块 | 目录 | 职责 | 置信度 |
|------|------|------|--------|
| AE 自动化核心 | `ae/` | 合成编排、Bridge 命令生成、AE 进程管理 | high |
| 核心引擎 | `core/` | 效果注册表、运镜分类器、节拍引擎、导演评分 | high |
| Bridge 通信层 | `bridges/` | Adobe MCP 服务器、通用 Bridge、多软件桥接 | high |
| 管线编排层 | `pipeline/` | 统一管线、旗舰执行器、漫画管线、反馈闭环 | high |
| IR 编译器 | `compiler/` | 意图→参数→操作码→JSX 生成 | high |
| 软件 SDK 适配器 | `software_sdk/` | 统一适配器模式 — 8 个引擎适配器 | high |
| 外部集成层 | `integrations/` | DaVinci/Blender/ComfyUI 深度集成 | high |
| Web Dashboard | `ae-dashboard/` | React SPA 前端 | high |
| FastAPI 后端 | `web/` + `run.py` | REST API + WebSocket + JWT 认证 | high |
| 知识库系统 | `knowledge_base/` | MD 扫描、风格匹配、LLM 提取 | high |
| ML 模型训练 | `models/` | 运镜分类、节拍模型、训练评估 | medium |

### 外部系统 (10 个)

| 系统 | 通信方式 | 用途 |
|------|----------|------|
| Adobe After Effects 2025/2026 | ExtendScript / aerender CLI / MCP | 核心合成引擎 |
| Adobe Premiere Pro 2026 | CEP / ExtendScript / MCP | 时间线剪辑 |
| Adobe PS / AI / ME | MCP Bridge | 图像处理 / 矢量 / 编码 |
| DaVinci Resolve | Scripting API / Lua | 调色 / 交付 |
| Blender 5.1.0 | Python API | 3D 渲染 |
| FFmpeg 8.1.1 | CLI / ffmpeg-python | 转码 / 滤镜 |
| Topaz Video AI Pro | CLI | AI 超分 / 降噪 |
| Silhouette 2026 | Scripting API | Roto 抠像 |
| AI 平台 API | HTTP / MCP | ModelScope / DashScope / OpenAI |
| 素材源 | API / 下载 | Pexels / Pixabay / yt-dlp |

---

## 五层架构数据流

```
感知层          理解层            规划层           执行层          反馈层
─────────      ──────────       ──────────      ──────────      ──────────
音频处理  ──→  节拍引擎   ──→  导演评分器  ──→  旗舰执行器  ──→  反馈闭环
视频处理  ──→  运镜分类   ──→  合成树      ──→  漫画管线    ──→  中间评审
场景检测  ──→  视听关联   ──→  贝叶斯优化  ──→  FFmpeg剪辑  ──→  自适应回退
分析引擎  ──→  内容指标   ──→  AI创意规划  ──→  AE智能编排
```

**关键设计模式**：
- **适配器模式**：`software_sdk/` 为每个外部软件提供统一接口
- **MCP 协议**：所有 AI 交互通过 Model Context Protocol 标准化
- **知识库驱动**：258+ 篇 Markdown 文档编码领域知识，为管线决策提供依据
- **反馈闭环**：执行结果回流至规划层，支持中间步评审和自适应回退

---

## 部署拓扑

| 组件 | 运行方式 | 端口 |
|------|----------|------|
| FastAPI 后端 | Docker 容器 / 本地 Python | :8000 |
| Web Dashboard | Nginx 静态服务 | :80 |
| Redis | Docker 容器 (redis:7-alpine) | :6379 |
| Prometheus | Docker 容器 | :9090 |
| Grafana | Docker 容器 | :3000 |
| MCP 服务器 | 本地进程 (Node.js / Python) | 文件轮询 |
| 桌面软件引擎 | 本地安装 (Windows) | ExtendScript / CLI |

---

## 置信度与验证缺口

### 高置信度 (直接代码证据)
- 五层架构模块划分 — `pyproject.toml` packages 列表 + 目录结构
- MCP 服务器注册 — `.mcp.json` 13 个服务器条目
- 适配器模式 — `software_sdk/adapters/` 8 个适配器文件
- Docker 部署 — `docker-compose.yml` 完整服务定义

### 中等置信度 (部分信号)
- ML 模型训练管线的生产就绪程度 — `models/training/` 存在但未见生产调用链
- 反馈闭环的完整实现 — `pipeline/feedback_loop.py` 存在，但与规划层的回写路径需验证

### 待验证 (validation tasks)
- [ ] `compiler/` TypeScript 部分与 Python 部分的运行时交互方式
- [ ] `core/evolution/` 和 `core/fx/` 子目录的完整能力
- [ ] `integrations/` 中 ComfyUI MCP 的实际生产使用频率
- [ ] 知识库质量门控的当前执行状态

---

## 关键架构决策

| 决策 | 选择 | 理由 |
|------|------|------|
| AE 自动化基线 | 开源 after-effects-mcp | 禁止修改原版 bridge，附加式增强 |
| 多软件集成 | 统一适配器模式 | 每个引擎一个适配器，通过注册表管理 |
| API 通信 | MCP + REST 双通道 | AI 助手用 MCP，Web 用 REST |
| 知识存储 | Markdown 文档 + JSON 索引 | 人类可读 + 机器可解析 |
| 部署 | Docker Compose (Windows) | 单机部署，含可观测性栈 |

---

## 产出物索引

| 文件 | 回答的问题 | 路径 |
|------|-----------|------|
| 系统上下文图 | 系统与外部世界的边界 | `docs/architecture/system-context.dot` |
| 容器/模块视图 | 内部模块如何组织与交互 | `docs/architecture/container-view.dot` |
| 证据索引 | 每个节点/边的证据来源 | `docs/architecture/system-model.evidence.md` |
| 架构理解 (本文) | 系统整体理解 + 验证缺口 | `docs/architecture/system-model.summary.md` |

---

## 下一步

1. **查看 DOT 图**：在 Qoder Canvas 中打开 `.dot` 文件预览渲染效果
2. **深入某个模块**：使用 `flow-visualizer` 追踪"自然语言→AE 合成"的完整数据流
3. **依赖影响分析**：使用 `dependency-impact-analyzer` 评估修改某个适配器的爆炸半径
4. **架构健康检查**：使用 `architecture-health` 验证本文档与代码的同步性
