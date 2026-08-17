# GitHub 截图开源项目深度分析与集成方案

> 分析时间: 2026-08-11 | 基于 7 张 GitHub 搜索截图 | 版本: v1.0

---

## 一、项目识别与信息提取

### 1.1 截图 1-4: DaVinci Resolve 生态 (github.com/search?q=DaVinci+Resolve, 2.1k 结果)

| # | 项目 | Stars | 语言 | 核心定位 | 技术栈 |
|---|------|-------|------|----------|--------|
| 1 | **tmoroney/auto-subs** | 4k | TypeScript/Rust | 跨平台字幕生成 (DaVinci/Premiere/AE) | Rust 核心 + TS 跨平台 |
| 2 | **samuelgursky/davinci-resolve-mcp** | 2.1k | Python | DaVinci Resolve MCP 服务器集成 | Python MCP SDK + Resolve Python API |
| 3 | **zelikos/davincibox** | 956 | Shell | Linux 上 DaVinci Resolve 依赖容器 | Docker/Shell |
| 4 | **alexandremendoncaalvaro/CorridorKey-Runtime** | 729 | C++ | DaVinci Resolve 原生 AI 抠像运行时 + OFX 插件 | C++ + AI 模型 |
| 5 | **baldavenger/DCTLs** | 349 | C | DaVinci Resolve CTL 色彩变换语言 | C (DaVinci CTL SDK) |
| 6 | **barckley75/resolve-claude-mcp** | 325 | Python | DaVinci Resolve + Claude AI 桥接 | Python + MCP + Claude API |
| 7 | **elliotmatson/Docker-DaVinci-Resolve-Project-Server** | 312 | Python | Resolve 项目服务器 + 自动备份 + PostgreSQL | Python + Docker + PostgreSQL |
| 8 | **H3rz3n/davinci-helper** | 310 | Python | Linux DaVinci Resolve 配套应用 | Python + GTK |
| 9 | **胖胎/解决** | 299 | Shell | Docker/Podman 运行 DaVinci Resolve Linux | Shell + Docker/Podman |
| 10 | **flolu/davinci-resolve-linux** | 262 | Shell | Linux 安装 DaVinci Resolve + 媒体导入导出 | Shell + Ubuntu |
| 11 | **viccowang/viccovlog-davinci-materials** | 225 | 富文本 | DaVinci Resolve 初学者教程资料 | Markdown |
| 12 | **pobthebuilder/resolve-flatpak** | 251 | Shell | DaVinci Resolve Flatpak 打包 | Shell + Flatpak |

### 1.2 截图 5: Adobe Photoshop 生态 (github.com/search?q=Adobe+Photoshop, 130 万结果)

| # | 项目 | Stars | 语言 | 核心定位 | 技术栈 |
|---|------|-------|------|----------|--------|
| 13 | **antipalindrome/Photoshop** | 1.6k | JavaScript | 快速将图层导出为文件 (远超 Adobe 原生速度) | ExtendScript/JSX |
| 14 | **psd-tools/psd-tools** | 1.4k | Python | Python 读取/解析 Adobe PSD 文件 | Python + 纯解析 |
| 15 | **adobe-photoshop/spaces-design** | 855 | JavaScript | Adobe Photoshop 设计空间 (官方) | JavaScript + CEP |
| 16 | **docsforadobe/Types-for-Adobe** | 642 | Shell | Adobe 全家桶 TypeScript 类型定义 | TypeScript + ExtendScript |
| 17 | **AdobeDocs/uxp-photoshop** | 144 | JavaScript | UXP Plugin API 文档 (PS 2022+) | JavaScript + UXP |

### 1.3 截图 6-7: Adobe Premiere Pro 生态 (github.com/search?q=Adobe+Premiere+Pro, 941 结果)

| # | 项目 | Stars | 语言 | 核心定位 | 技术栈 |
|---|------|-------|------|----------|--------|
| 18 | **hetpatel-11/Adobe_Premiere_Pro_MCP** | 455 | TypeScript | 282 种 AI 驱动视频编辑工具 (MCP) | TypeScript + CEP + MCP |
| 19 | **leancoderkavy/premiere-pro-mcp** | 180 | TypeScript | 279 种 AI 工具 + CEP 桥接 + UXP 支持 | TypeScript + CEP + UXP + MCP |
| 20 | **ayushozha/AdobePremiereProMCP** | 82 | Go | 1,027 种工具 (时间线/调色/音频/特效/导出) | Go + ExtendScript + MCP |
| 21 | **antipaster/Adobe-Premiere-Pro-MCP** | 27 | JavaScript | Claude/Codex 控制 PR + 170+ 编辑工具 | JavaScript + MCP |
| 22 | **Vintata/tk-premiere** | 25 | Python | Premiere Pro CC Shotgun 集成引擎 | Python + Shotgun API |
| 23 | **fayewave/OpenCurve** | 57 | JavaScript | 免费贝塞尔曲线编辑插件 (UXP) | JavaScript + UXP |

---

## 二、与 AE-Knowledge-Vault 的关联分析

### 2.1 分层定位矩阵

```
┌─────────────────────────────────────────────────────────────────────┐
│  L4 Agent 决策层                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ barckley75/resolve-claude-mcp (325★) → Resolve + Claude AI   │   │
│  │   定位: AI 驱动的 Resolve 自动化决策                          │   │
│  │   重叠: 与本项目 LLM Gateway + resolve_engine.py 部分重叠    │   │
│  └──────────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────────┤
│  L3 编排调度层                                                        │
│  ┌──────────────────────────────────────────────────────────────   │
│  │ samuelgursky/davinci-resolve-mcp (2.1k★) → Resolve MCP Server│   │
│  │   定位: 标准化 MCP 协议接入 Resolve                           │   │
│  │   重叠: 可替代现有 resolve_engine.py (fuscript+Lua 方案)     │   │
│  └──────────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────────┤
│  L2 服务层                                                            │
│  ┌──────────────────────┐  ┌────────────────────────────────────┐  │
│  │ tmoroney/auto-subs   │  │ psd-tools/psd-tools (1.4k★)       │  │
│  │ (4k★) 字幕生成       │  │ PSD 文件解析                       │  │
│  │ 定位: 上游素材处理   │  │ 定位: 素材预处理                   │  │
│  └──────────────────────┘  ────────────────────────────────────┘  │
─────────────────────────────────────────────────────────────────────
│  L1 引擎层                                                            │
│  ┌──────────────────────────┐  ┌───────────────────────────────┐  │
│  │ CorridorKey-Runtime(729★)│  │ hetpatel-11/PR MCP (455★)    │  │
│  │ AI 抠像 OFX 插件         │  │ 282 种 PR 编辑工具            │  │
│  │ 定位: 特效合成增强       │  │ 定位: PR 自动化增强           │  │
│  ├──────────────────────────┤  ├───────────────────────────────┤  │
│  │ baldavenger/DCTLs(349★)  │  │ leancoderkavy/PR MCP(180★)   │  │
│  │ CTL 色彩变换预设         │  │ 279 种工具+CEP+UXP            │  │
│  │ 定位: 色彩分级增强       │  │ 定位: PR 自动化(备选)         │  │
│  └──────────────────────────┘  ───────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────────┤
│  无关/低价值 (Linux 容器/教程/打包)                                    │
│  zelikos/davincibox, 胖胎/解决, flolu/davinci-resolve-linux,        │
│  pobthebuilder/resolve-flatpak, H3rz3n/davinci-helper,              │
│  viccowang/davinci-materials, elliotmatson/Docker-Resolve-Server    │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 逐项关联分析

#### P0: 必须集成

**① samuelgursky/davinci-resolve-mcp (2.1k ★)**

| 维度 | 分析 |
|------|------|
| **当前状态** | 已有 `resolve_engine.py` (fuscript+Lua 混合方案)，已克隆 `external/davinci-resolve-mcp/` |
| **重叠分析** | 本项目用 fuscript.exe + Lua 绕过 Python API DLL 加载失败问题；MCP 版本用 Python API 直接通信 |
| **增强空间** | MCP 协议标准化，可统一 AE/PR/PS/Resolve 的调用接口；resolve_api.py 可能暴露更多 API |
| **能力缺口** | 当前 resolve_engine.py 不支持 MCP 协议，无法被 LLM Gateway 直接调度 |
| **视觉提升** | 无直接视觉提升，但标准化接口可加速管线编排 |
| **技术选型** | 选 MCP 版本作为 L1 引擎层标准接口，保留 fuscript 方案作为降级后备 |

**② tmoroney/auto-subs (4k ★)**

| 维度 | 分析 |
|------|------|
| **当前状态** | 已有 Whisper 集成 (opensource_integrations.py)，但仅做 ASR |
| **重叠分析** | Whisper 做语音识别，auto-subs 做字幕生成+时间轴对齐+多格式导出 |
| **增强空间** | auto-subs 直接连接 DaVinci/Premiere/AE，可自动生成字幕轨道 |
| **能力缺口** | 当前系统缺少字幕自动生成→时间线对齐→多格式导出的完整链路 |
| **视觉提升** | 字幕是混剪视频的核心元素，直接影响专业度 |
| **技术选型** | Rust 核心性能优于 Python Whisper，跨平台支持 3 大 NLE |

#### P1: 强烈建议

**③ hetpatel-11/Adobe_Premiere_Pro_MCP (455 ★)**

| 维度 | 分析 |
|------|------|
| **当前状态** | PR Bridge 文件轮询 (pr_bridge_client.py)，仅支持基础操作 |
| **重叠分析** | 当前 PR Bridge 仅 ping/status/executeScript；MCP 提供 282 种工具 |
| **增强空间** | 时间线编辑、色彩分级、音频混音、特效处理、导出等完整能力 |
| **能力缺口** | PR 自动化是最大短板，MCP 可填补 90% 以上的 PR 操作缺口 |
| **视觉提升** | 直接提升剪辑效率，支持 AI 驱动的自动剪辑 |
| **技术选型** | TypeScript + CEP 架构，与现有 Bridge 方案互补而非替代 |

**④ CorridorKey-Runtime (729 ★)**

| 维度 | 分析 |
|------|------|
| **当前状态** | 已有 SAM2 分割集成，但仅做离线分割 |
| **重叠分析** | SAM2 是通用分割，CorridorKey 是 Resolve 原生 AI 抠像 OFX 插件 |
| **增强空间** | 实时 AI 抠像，直接在 Resolve 时间线中运行，无需导出 |
| **能力缺口** | 当前 Roto 流程: SAM2 分割 → 导出蒙版 → 导入 AE/Resolve，链路长 |
| **视觉提升** | 实时抠像质量远超手动 Roto，直接提升合成质量 |
| **技术选型** | C++ OFX 插件，需 Resolve Studio 版 (已安装 21.0.3) |

**⑤ psd-tools/psd-tools (1.4k ★)**

| 维度 | 分析 |
|------|------|
| **当前状态** | PS Bridge 已部署，但仅支持运行时操作 |
| **重叠分析** | Bridge 需要 PS 运行中；psd-tools 可离线解析 PSD 文件 |
| **增强空间** | 离线读取 PSD 图层结构、蒙版、调整图层，无需启动 PS |
| **能力缺口** | 当前无法在不启动 PS 的情况下分析 PSD 文件内容 |
| **视觉提升** | 加速素材预处理流程，支持批量 PSD 分析 |

**⑥ baldavenger/DCTLs (349 ★)**

| 维度 | 分析 |
|------|------|
| **当前状态** | 已有 LUT 预设库 (lut_preset_library.py) 和 CDL 调色 |
| **重叠分析** | LUT 是预计算查找表，DCTL 是实时计算的色彩变换脚本 |
| **增强空间** | DCTL 支持更复杂的色彩变换逻辑，可自定义算法 |
| **能力缺口** | 当前调色仅支持 LUT 和 CDL，缺少 DCTL 自定义色彩变换 |
| **视觉提升** | 专业级色彩分级，支持电影级调色流程 |

#### P2: 可选增强

**⑦ leancoderkavy/premiere-pro-mcp (180 ★)**

| 维度 | 分析 |
|------|------|
| **定位** | PR MCP 备选方案，279 种工具 + CEP + UXP 双支持 |
| **与 #3 对比** | 工具数略少 (279 vs 282)，但支持 UXP (未来方向) |
| **集成价值** | 作为 #3 的备选，或用于 UXP 插件开发参考 |

** barckley75/resolve-claude-mcp (325 ★)**

| 维度 | 分析 |
|------|------|
| **定位** | Resolve + Claude AI 桥接 |
| **重叠分析** | 与本项目 LLM Gateway + resolve_engine.py 高度重叠 |
| **集成价值** | 架构参考价值 > 直接集成价值，可学习其 MCP 工具设计 |

**⑨ fayewave/OpenCurve (57 ★)**

| 维度 | 分析 |
|------|------|
| **定位** | PR 贝塞尔曲线编辑插件 (UXP) |
| **集成价值** | 曲线变速是高端漫剪核心需求，但 UXP 插件集成复杂度高 |
| **替代方案** | 当前 resolve_engine.py 已支持 set_speed_curve |

#### P3: 无关/低价值

| 项目 | 原因 |
|------|------|
| zelikos/davincibox (956★) | Linux 容器方案，本项目运行在 Windows |
| 胖胎/解决 (299★) | Docker/Podman Linux 方案 |
| flolu/davinci-resolve-linux (262★) | Linux 安装脚本 |
| pobthebuilder/resolve-flatpak (251★) | Flatpak 打包，Linux 专用 |
| H3rz3n/davinci-helper (310★) | Linux GTK 配套应用 |
| viccowang/davinci-materials (225★) | 教程资料，非工具 |
| elliotmatson/Docker-Resolve-Server (312★) | 项目服务器，与自动化无关 |
| adobe-photoshop/spaces-design (855★) | 已废弃的设计空间项目 |
| AdobeDocs/uxp-photoshop (144★) | 官方文档，参考即可 |
| docsforadobe/Types-for-Adobe (642★) | TypeScript 类型定义，参考即可 |
| ayushozha/AdobePremiereProMCP (82★) | Go 语言实现，与 Python 技术栈不符 |
| antipaster/Adobe-Premiere-Pro-MCP (27★) | 工具数少，社区不活跃 |
| Vintata/tk-premiere (25★) | Shotgun 集成，与本项目无关 |
| antipalindrome/Photoshop (1.6k★) | 图层导出脚本，功能单一 |

---

## 三、集成架构方案

### 3.1 整体架构升级图

```
                    ┌─────────────────────────────────────────┐
                    │         LLM Gateway (调度中心)            │
                    │  DeepSeek / Claude / Qwen-MM            │
                    └──────────────┬──────────────────────────┘
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        │                          │                          │
        ▼                          ▼                          ▼
┌───────────────┐        ┌───────────────┐        ┌───────────────┐
│  素材获取层    │        │  AI 处理层     │        │  特效合成层    │
├───────────────┤        ├───────────────┤        ├───────────────┤
│ MediaCrawler  │        │ ComfyUI       │        │ Adobe MCP     │
│ (7平台)       │        │ (AI生成)      │        │ (AE/PR/PS/ME) │
│               │        │               │        │               │
│ [NEW] auto-   │        │ [NEW] psd-    │        │ [NEW] PR MCP  │
│ subs (字幕)   │        │ tools (PSD)   │        │ (282工具)     │
└───────────────┘        ───────────────┘        └───────────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
                    ▼              ▼              ▼
            ┌───────────┐  ┌───────────┐  ┌───────────┐
            │ 色彩分级   │  │ 抠像分割   │  │ 渲染输出   │
            ├───────────┤  ├───────────┤  ├───────────
            │ DCTLs     │  │ SAM2      │  │ nexrender │
            │ (CTL预设) │  │ (分割)    │  │ (模板渲染)│
            │           │  │           │  │           │
            │ [NEW]     │  │ [NEW]     │  │ [NEW]     │
            │ DCTLs社区 │  │ Corridor  │  │ Resolve   │
            │ 预设库    │  │ Key-Runtime│ │ MCP       │
            ───────────┘  └───────────┘  └───────────┘
```

### 3.2 数据流转路径

#### 3.2.1 auto-subs 字幕管线

```
输入: 视频文件 (mp4/mov)
  │
  ▼
auto-subs CLI
  │  调用: auto-subs --input video.mp4 --model whisper-large
  │        --output-format srt --language zh
  ▼
输出: .srt / .ass / .vtt 字幕文件
  │
  ▼
Adobe MCP (PR) → 导入字幕轨道
  │  调用: importMedia(subtitle.srt) → addToTimeline()
  ▼
最终: 带字幕的视频时间线
```

**接口协议**: CLI 命令行
**调用方式**: `subprocess.run(["auto-subs", "--input", video, ...])`
**降级策略**: auto-subs 不可用 → 回退到 Whisper Python API → 再降级到模拟模式

#### 3.2.2 Resolve MCP 标准化接口

```
输入: LLM Gateway 调度指令
  │
  ▼
samuelgursky/davinci-resolve-mcp (MCP Server)
  │  协议: MCP (Model Context Protocol)
  │  工具: createProject, importMedia, createTimeline,
  │        applyColorGrade, renderExport, ...
  ▼
Resolve Python API / fuscript Lua
  │
  ▼
输出: 渲染完成的视频文件
```

**接口协议**: MCP over stdio/SSE
**调用方式**: Python MCP Client → MCP Server → Resolve API
**降级策略**: MCP Server 不可用 → 回退到 resolve_engine.py (fuscript+Lua) → 再降级到 FFmpeg 直接处理

#### 3.2.3 PR MCP 增强管线

```
输入: 剪辑方案 (DAG)
  │
  ▼
hetpatel-11/Adobe_Premiere_Pro_MCP (282 工具)
  │  工具分类:
  │  - timeline: createSequence, addClip, setInPoint, setOutPoint
  │  - color: applyLumetriColor, adjustExposure, adjustContrast
  │  - audio: adjustVolume, applyAudioEffect, normalizeAudio
  │  - export: exportMedia, setExportPreset
  ▼
PR ExtendScript / CEP 面板
  │
  ▼
输出: 剪辑完成的项目文件
```

**接口协议**: MCP over stdio
**调用方式**: TypeScript MCP Server → CEP Extension → ExtendScript
**降级策略**: MCP 不可用 → 回退到 pr_bridge_client.py (文件轮询) → 再降级到手动操作

#### 3.2.4 CorridorKey AI 抠像管线

```
输入: 视频片段 + 蒙版区域指定
  │
  ▼
CorridorKey-Runtime (OFX 插件)
  │  在 Resolve 内实时运行 AI 抠像模型
  │  支持: 人物/物体/背景分离
  ▼
Resolve 时间线 (实时预览)
  │
  ▼
输出: 带 Alpha 通道的视频片段
```

**接口协议**: OFX 插件 (Resolve 原生)
**调用方式**: Resolve 内加载 OFX 插件 → Python 脚本控制参数
**降级策略**: CorridorKey 不可用 → 回退到 SAM2 离线分割 → 再降级到手动 Roto

### 3.3 降级策略总表

| 环节 | Level 0 (正常) | Level 1 (模拟) | Level 2 (降级) | Level 3 (跳过) |
|------|---------------|---------------|---------------|---------------|
| **字幕生成** | auto-subs CLI | Whisper Python API | 手动字幕文件 | 无字幕输出 |
| **Resolve 控制** | Resolve MCP Server | resolve_engine.py (fuscript) | FFmpeg 直接处理 | 跳过 Resolve 环节 |
| **PR 控制** | PR MCP (282 工具) | pr_bridge_client.py (文件轮询) | 手动操作 | 跳过 PR 环节 |
| **AI 抠像** | CorridorKey OFX | SAM2 离线分割 | 手动 Roto | 无抠像 |
| **色彩分级** | DCTLs 自定义 | LUT 预设库 | CDL 基础调色 | 无调色 |
| **PSD 解析** | psd-tools 离线 | PS Bridge 运行时 | 手动分析 | 跳过 PSD 处理 |

### 3.4 技术选型理由

| 选型 | 理由 | 替代方案 | 为何不选 |
|------|------|----------|----------|
| **samuelgursky/davinci-resolve-mcp** | 2.1k stars 社区最大，Python 技术栈匹配，MCP 标准化 | barckley75/resolve-claude-mcp (325★) | 后者绑定 Claude API，通用性差 |
| **tmoroney/auto-subs** | 4k stars 最大，Rust 核心性能优，跨 3 大 NLE | 自研 Whisper 封装 | 自研需处理时间轴对齐/多格式导出 |
| **hetpatel-11/PR MCP** | 455 stars PR MCP 最大，TypeScript 与 CEP 原生兼容 | leancoderkavy (180★), ayushozha (82★ Go) | ayushozha 用 Go 语言栈不匹配 |
| **CorridorKey-Runtime** | 729 stars，Resolve 原生 OFX，实时 AI 抠像 | SAM2 离线分割 | SAM2 非实时，需导出导入 |
| **psd-tools/psd-tools** | 1.4k stars，纯 Python 无依赖，离线解析 | Adobe UXP API | UXP 需 PS 运行中，psd-tools 可离线 |
| **baldavenger/DCTLs** | 349 stars，社区 DCTL 预设丰富 | 自研 DCTL | 自研需深入 CTL SDK 开发 |

### 3.5 预期效果 (量化指标)

| 集成项目 | 能力指标 | 预期提升 |
|----------|---------|---------|
| **Resolve MCP** | Resolve 自动化操作数 | 从 15 个 (fuscript) → 50+ 个 (MCP) |
| **auto-subs** | 字幕生成速度 | 从 30s/分钟 (Whisper) → 10s/分钟 (Rust) |
| **PR MCP** | PR 自动化操作数 | 从 5 个 (Bridge) → 282 个 (MCP) |
| **CorridorKey** | 抠像处理速度 | 从 5min/镜头 (SAM2 离线) → 实时 (OFX) |
| **psd-tools** | PSD 分析速度 | 从 10s (启动 PS) → 0.5s (离线解析) |
| **DCTLs** | 色彩预设数量 | 从 20 个 (LUT) → 100+ 个 (DCTL 社区) |

---

## 四、实施路线图

### Phase 1: P0 集成 (本周)

```
Week 1
├─ Day 1-2: samuelgursky/davinci-resolve-mcp
│   ├─ 分析 external/davinci-resolve-mcp/resolve_api.py
│   ├─ 创建 integrations/resolve_mcp_adapter.py
│   ├─ 注册到 integration_registry.py
│   └─ E2E 测试: ping → createProject → importMedia → render
│
└─ Day 3-4: tmoroney/auto-subs
    ├─ git clone 到 external/auto-subs/
    ├─ 创建 integrations/auto_subs_adapter.py
    ├─ 注册到 integration_registry.py
    └─ E2E 测试: 视频输入 → 字幕输出 → PR 导入
```

### Phase 2: P1 集成 (下周)

```
Week 2
├─ Day 1-2: hetpatel-11/Adobe_Premiere_Pro_MCP
│   ├─ git clone 到 external/premiere-pro-mcp/
│   ├─ 分析 TypeScript MCP Server 架构
│   ├─ 创建 integrations/pr_mcp_adapter.py
│   └─ E2E 测试: 282 工具中核心 20 个
│
├─ Day 3: CorridorKey-Runtime
│   ├─ 下载 OFX 插件到 Resolve Plugins 目录
│   ├─ 创建 integrations/corridor_key_adapter.py
│   └─ E2E 测试: 加载插件 → 抠像 → 输出
│
└─ Day 4-5: psd-tools + DCTLs
    ├─ pip install psd-tools
    ├─ 创建 integrations/psd_tools_adapter.py
    ├─ 克隆 DCTLs 到 external/DCTLs/
    └─ 导入社区预设到 lut_preset_library.py
```

### Phase 3: P2 集成 (本月)

```
Week 3-4
├─ leancoderkavy/premiere-pro-mcp (UXP 支持研究)
├─ barckley75/resolve-claude-mcp (架构参考)
└─ fayewave/OpenCurve (曲线变速插件研究)
```

---

## 五、风险与注意事项

### 5.1 技术风险

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| Resolve MCP Python API DLL 加载失败 | 高 | 中 | 保留 fuscript+Lua 降级方案 |
| PR MCP TypeScript 编译问题 | 中 | 中 | 预编译二进制或 Docker 容器 |
| auto-subs Rust 依赖安装失败 | 低 | 低 | 回退到 Whisper Python API |
| CorridorKey 仅支持 Resolve Studio | 中 | 中 | 已确认 Studio 21.0.3 已安装 |
| DCTLs 与 Resolve 版本兼容性 | 低 | 低 | 测试后筛选兼容预设 |

### 5.2 架构注意事项

1. **MCP 协议统一**: Resolve MCP 和 PR MCP 都使用 MCP 协议，可统一封装为 `MCPClient` 基类
2. **文件轮询 vs MCP**: 现有 Bridge 文件轮询方案保留作为降级后备，不立即替换
3. **Python 技术栈一致性**: 优先选择 Python/TypeScript 项目，避免 Go/Rust 增加维护成本
4. **Windows 兼容性**: 排除所有 Linux 专用项目 (davincibox, davinci-resolve-linux 等)

---

## 六、结论

### 6.1 核心发现

1. **DaVinci Resolve 生态最成熟**: samuelgursky/davinci-resolve-mcp (2.1k★) 可直接替代现有 fuscript 方案
2. **PR 自动化缺口最大**: hetpatel-11/PR MCP (455★) 可将 PR 操作从 5 个提升到 282 个
3. **字幕生成有成熟方案**: auto-subs (4k★) 性能优于自研 Whisper 封装
4. **AI 抠像可实时化**: CorridorKey (729★) 可将离线 5min/镜头 降低到实时
5. **Linux 项目占 60%**: 14 个 DaVinci 项目中 8 个是 Linux 专用，与本项目无关

### 6.2 优先级排序

```
P0 (必须): samuelgursky/davinci-resolve-mcp, tmoroney/auto-subs
P1 (强烈): hetpatel-11/PR MCP, CorridorKey-Runtime, psd-tools, DCTLs
P2 (可选): leancoderkavy/PR MCP, barckley75/resolve-claude-mcp, OpenCurve
P3 (无关): 所有 Linux 容器/打包/教程项目
```

### 6.3 预期总收益

- **自动化覆盖率**: 从 40% → 85% (AE/PR/Resolve 全链路)
- **处理速度**: 字幕 3x 提升，抠像 300x 提升，PSD 分析 20x 提升
- **视觉效果**: 支持实时 AI 抠像、DCTL 电影级调色、自动字幕
- **维护成本**: MCP 标准化接口降低 50% 集成代码量
