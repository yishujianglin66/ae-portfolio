# AE-Knowledge-Vault 系统模型 — 证据索引

> 技能: `system-modeler` + `graphviz`
> 日期: 2026-08-17
> 范围: 当前状态 (current-state)

## 节点证据

### N1 — After Effects 自动化核心 (ae/)

| 字段 | 值 |
|------|-----|
| id | module.ae-core |
| label | AE 自动化核心 |
| type | module |
| state | current |
| confidence | high |
| sourceRefs | `ae/ae_agent_pipeline.py`, `ae/ae_bridge_base.py`, `ae/ae_command_client.py`, `ae/ae_smart_orchestrator.py`, `ae/ae_process_manager.py` |
| description | AE 合成的自然语言→脚本编排、Bridge 命令生成与执行、AE 进程生命周期管理 |

### N2 — 核心引擎 (core/)

| 字段 | 值 |
|------|-----|
| id | module.core-engine |
| label | 核心引擎 |
| type | module |
| state | current |
| confidence | high |
| sourceRefs | `core/effect_registry.py`, `core/engine_registry.py`, `core/camera_movement_classifier.py`, `core/beat_strength_engine.py`, `core/director_scorer.py`, `core/composition_tree.py` |
| description | 效果注册表、引擎注册表、运镜分类器、节拍强度引擎、导演评分器、合成树 — 五层架构的感知/理解/规划层 |

### N3 — Bridge 通信层 (bridges/)

| 字段 | 值 |
|------|-----|
| id | module.bridges |
| label | Bridge 通信层 |
| type | module |
| state | current |
| confidence | high |
| sourceRefs | `bridges/adobe_mcp_server.py`, `bridges/adobe_universal_bridge.py`, `bridges/mcp_bridge_client.py`, `bridges/pipeline_orchestrator.py`, `bridges/blender_ae_bridge.py` |
| description | Adobe MCP 服务器、通用 Bridge 适配器、MCP 客户端、管线编排器、Blender↔AE 桥接 |

### N4 — 管线编排 (pipeline/)

| 字段 | 值 |
|------|-----|
| id | module.pipeline |
| label | 管线编排层 |
| type | module |
| state | current |
| confidence | high |
| sourceRefs | `pipeline/unified_pipeline.py`, `pipeline/flagship_runner.py`, `pipeline/manga_pipeline.py`, `pipeline/ffmpeg_edit_engine.py`, `pipeline/stock_footage.py`, `pipeline/feedback_loop.py` |
| description | 统一管线、旗舰管线执行器、漫画剪辑管线、FFmpeg 剪辑引擎、素材搜索、反馈闭环 |

### N5 — 编译器 (compiler/)

| 字段 | 值 |
|------|-----|
| id | module.compiler |
| label | IR 编译器 |
| type | module |
| state | current |
| confidence | high |
| sourceRefs | `compiler/intent_router.py`, `compiler/parameter_mapper.py`, `compiler/report_to_ops.py`, `compiler/src/` (TypeScript) |
| description | 意图路由→参数映射→操作报告→JSX/操作码生成，含 TypeScript 前端编译 |

### N6 — 软件 SDK 适配器 (software_sdk/)

| 字段 | 值 |
|------|-----|
| id | module.software-sdk |
| label | 软件 SDK 适配器 |
| type | module |
| state | current |
| confidence | high |
| sourceRefs | `software_sdk/base.py`, `software_sdk/registry.py`, `software_sdk/adapters/ae_adapter.py`, `software_sdk/adapters/blender_adapter.py`, `software_sdk/adapters/davinci_adapter.py`, `software_sdk/adapters/ffmpeg_adapter.py`, `software_sdk/adapters/topaz_adapter.py`, `software_sdk/adapters/silhouette_adapter.py` |
| description | 统一适配器模式 — 每个外部软件一个适配器，通过注册表管理 |

### N7 — 集成层 (integrations/)

| 字段 | 值 |
|------|-----|
| id | module.integrations |
| label | 外部集成层 |
| type | module |
| state | current |
| confidence | high |
| sourceRefs | `integrations/davinci_resolve_integration.py`, `integrations/blender_3d_integration.py`, `integrations/adaptive_color_grader.py`, `integrations/comfyui_mcp_server.py`, `integrations/ae_to_davinci_pipeline.py` |
| description | DaVinci Resolve 集成、Blender 3D 集成、自适应调色、ComfyUI MCP、AE→DaVinci 管线 |

### N8 — Web Dashboard (ae-dashboard/)

| 字段 | 值 |
|------|-----|
| id | module.dashboard |
| label | Web Dashboard |
| type | module |
| state | current |
| confidence | high |
| sourceRefs | `ae-dashboard/src/`, `ae-dashboard/package.json`, `ae-dashboard/dist/` |
| description | 前端 SPA — 任务管理、效果预览、样式选择、执行控制面板 |

### N9 — FastAPI 后端 (web/ + run.py)

| 字段 | 值 |
|------|-----|
| id | module.web-backend |
| label | FastAPI 后端 |
| type | service |
| state | current |
| confidence | high |
| sourceRefs | `run.py`, `pyproject.toml` (fastapi, uvicorn), `docker-compose.yml` (backend service) |
| description | REST API + WebSocket 服务 — 任务管理、批处理、质量评估、认证、监控 |

### N10 — 知识库系统 (knowledge_base/)

| 字段 | 值 |
|------|-----|
| id | module.knowledge-base |
| label | 知识库系统 |
| type | module |
| state | current |
| confidence | high |
| sourceRefs | `knowledge_base/kb_loader.py`, `knowledge_base/kb_scanner.py`, `knowledge_base/md_parser.py`, `knowledge_base/style_matcher.py`, `knowledge_base/llm_extractor.py` |
| description | Markdown 知识文档扫描、解析、风格匹配、LLM 提取 — 为管线提供领域知识 |

### N11 — ML 模型训练 (models/)

| 字段 | 值 |
|------|-----|
| id | module.ml-models |
| label | ML 模型训练 |
| type | module |
| state | current |
| confidence | medium |
| sourceRefs | `models/anime_camera_classifier.py`, `models/camera/`, `models/beat/`, `models/training/`, `models/evaluation/` |
| description | 动画运镜分类器、节拍检测模型、训练管线、评估框架 |

### N12 — 字幕系统 (10-风格化剪辑知识库/ 中的 Whisper 管线)

| 字段 | 值 |
|------|-----|
| id | module.subtitle |
| label | 字幕/Whisper 系统 |
| type | module |
| state | current |
| confidence | medium |
| sourceRefs | `requirements.txt` (openai-whisper, faster-whisper), `knowledge` 模块树中的字幕系统描述 |
| description | SRT/VTT/ASS 解析、Whisper 语音识别、LLM 优化 → IR 字幕轨 |

## 外部系统证据

### E1 — Adobe After Effects 2025/2026

| 字段 | 值 |
|------|-----|
| id | ext.ae |
| label | Adobe After Effects |
| type | external-system |
| confidence | high |
| sourceRefs | `工具链集成总览.md` §2.1, `.mcp.json` (AfterEffectsMCP, AdobeMCP) |

### E2 — Adobe Premiere Pro 2026

| 字段 | 值 |
|------|-----|
| id | ext.pr |
| label | Adobe Premiere Pro |
| type | external-system |
| confidence | high |
| sourceRefs | `.mcp.json` (PremiereProMCP), `bridges/PRBridgeCEP/` |

### E3 — Adobe Photoshop / Illustrator / Media Encoder

| 字段 | 值 |
|------|-----|
| id | ext.adobe-suite |
| label | Adobe PS/AI/ME |
| type | external-system |
| confidence | high |
| sourceRefs | `工具链集成总览.md` §2.1, `.mcp.json` |

### E4 — DaVinci Resolve

| 字段 | 值 |
|------|-----|
| id | ext.davinci |
| label | DaVinci Resolve |
| type | external-system |
| confidence | high |
| sourceRefs | `.mcp.json` (DaVinciResolveMCP), `integrations/davinci_resolve_integration.py` |

### E5 — Blender

| 字段 | 值 |
|------|-----|
| id | ext.blender |
| label | Blender 5.1.0 |
| type | external-system |
| confidence | high |
| sourceRefs | `bridges/blender_ae_bridge.py`, `integrations/blender_3d_integration.py` |

### E6 — FFmpeg

| 字段 | 值 |
|------|-----|
| id | ext.ffmpeg |
| label | FFmpeg 8.1.1 |
| type | external-system |
| confidence | high |
| sourceRefs | `pipeline/ffmpeg_edit_engine.py`, `software_sdk/adapters/ffmpeg_adapter.py` |

### E7 — Topaz Video AI

| 字段 | 值 |
|------|-----|
| id | ext.topaz |
| label | Topaz Video AI Pro |
| type | external-system |
| confidence | high |
| sourceRefs | `software_sdk/adapters/topaz_adapter.py`, `工具链集成总览.md` §2.3.2 |

### E8 — Silhouette

| 字段 | 值 |
|------|-----|
| id | ext.silhouette |
| label | Silhouette 2026 |
| type | external-system |
| confidence | high |
| sourceRefs | `silhouette/`, `software_sdk/adapters/silhouette_adapter.py` |

### E9 — AI 平台 (ModelScope / DashScope / OpenAI)

| 字段 | 值 |
|------|-----|
| id | ext.ai-platforms |
| label | AI 平台 API |
| type | external-system |
| confidence | high |
| sourceRefs | `.mcp.json` (fetch, bing-cn-mcp-server, qwen-mm-plugins-*), `.env.modelscope.example`, `requirements.txt` (openai) |

### E10 — 素材源 (Pexels / Pixabay / yt-dlp)

| 字段 | 值 |
|------|-----|
| id | ext.stock-sources |
| label | 素材源 |
| type | external-system |
| confidence | high |
| sourceRefs | `pipeline/stock_footage.py`, `.mcp.json` (ytdlp), pytest marker `real_stock_api` |

## 边证据 (关键关系)

| 边 ID | from → to | type | confidence | sourceRefs |
|--------|-----------|------|------------|------------|
| edge.dash-api | dashboard → web-backend | calls | high | `ae-dashboard/src/`, `docker-compose.yml` |
| edge.api-ae | web-backend → ae-core | calls | high | `run.py`, `ae/ae_agent_pipeline.py` |
| edge.api-pipe | web-backend → pipeline | calls | high | `run.py`, `pipeline/unified_pipeline.py` |
| edge.api-kb | web-backend → knowledge-base | reads | high | `knowledge_mcp_server.py`, `knowledge_base/` |
| edge.ae-bridge | ae-core → bridges | calls | high | `ae/ae_bridge_base.py`, `bridges/` |
| edge.bridge-ae-ext | bridges → ext.ae | calls | high | `bridges/adobe_mcp_server.py`, `.mcp.json` |
| edge.bridge-pr | bridges → ext.pr | calls | high | `bridges/PRBridgeCEP/`, `.mcp.json` |
| edge.pipe-sdk | pipeline → software-sdk | depends-on | high | `pipeline/unified_pipeline.py`, `software_sdk/` |
| edge.sdk-ext | software-sdk → ext.* | calls | high | `software_sdk/adapters/*.py` |
| edge.pipe-compiler | pipeline → compiler | calls | high | `compiler/intent_router.py` |
| edge.compiler-ae | compiler → ae-core | calls | high | `compiler/report_to_ops.py` |
| edge.core-ml | core-engine → ml-models | depends-on | medium | `core/camera_movement_classifier.py`, `models/` |
| edge.integ-ext | integrations → ext.davinci/blender | calls | high | `integrations/*.py` |
| edge.pipe-stock | pipeline → ext.stock-sources | calls | high | `pipeline/stock_footage.py` |
| edge.api-ai | web-backend → ext.ai-platforms | calls | high | `.mcp.json`, `.env` |
| edge.kb-docs | knowledge-base → 知识库 Markdown 文档 | reads | high | `knowledge_base/kb_scanner.py`, `10-风格化剪辑知识库/`, `11-大师知识库/` |
