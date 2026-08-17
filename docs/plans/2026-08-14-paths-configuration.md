# 路径配置化迁移清单与路线图

> 日期：2026-08-14 · 状态：**第一阶段已完成（基础设施 + 5 个示范文件），待分批推进**

## 一、问题

项目历史上把本机绝对路径（`D:/AE-Work`、`C:/ffmpeg`、`C:/Users/Administrator/Documents/ae-mcp-bridge` 等）
散落硬编码在 **100+ 个 Python 模块**里（grep `[A-Za-z]:[\\/]` 命中 588 处，排除 URL/注释后仍有大量真实路径）。
换机器、换盘符、换用户名即失效，是代码长期维护的最大坎。

## 二、方案：统一路径层 `core/paths.py`

新增 `core/paths.py` 作为**单一权威源**：

| 原则 | 说明 |
|---|---|
| 一个主变量 | `AE_WORK_DIR` 决定工作根目录，绝大多数路径从它推导，换机器设一个变量即整体迁移 |
| 细粒度覆盖 | 每个具体路径可用 `AEK_*` 环境变量覆盖，优先级高于 `AE_WORK_DIR` 推导 |
| 向后兼容 | 默认值与历史硬编码完全一致，未设环境变量时行为 100% 不变（零迁移风险） |
| 零依赖 | 纯标准库、函数式惰性求值、不 import 项目模块（无循环依赖、无 import 时序陷阱） |

已提供的 API：`work_root()` / `ffmpeg_bin()` / `ffprobe_bin()` / `ae_exe()` / `aerender_exe()` /
`resources_root()` / `video_library()` / `audio_library()` / `bgm_library()` / `output_dir()` /
`work_output_dir()` / `cookies_dir()` / `models_dir()` / `installed_fonts_file()` / `ae_bridge_dir()`

`.env.example` 已补全对应环境变量段。

## 三、已完成（第一阶段）

| 文件 | 迁移内容 |
|---|---|
| `core/paths.py` | **新增**，统一路径层（基础设施） |
| `.env.example` | 补全 `AE_WORK_DIR` 主变量 + 16 个 `AEK_*` 覆盖项 |
| `ai/ae_render_channel.py` | AERENDER/AE_EXE/FFMPEG/FFPROBE |
| `video/video_generator.py` | MUSIC_DIR/CLIP_DIR/OUTPUT_DIR/COMMAND_FILE/RESULT_FILE |
| `core/font_manager.py` | _INSTALLED_FONTS_LIST |
| `core/style_spec_extractor.py` | FFMPEG/FFPROBE |
| `core/post_enhancer.py` | DEFAULT_CONFIG["ffmpeg"] |

## 四、剩余迁移（按优先级分批）

### P0 — 核心引擎（渲染/编排/素材，影响成片质量）

- `ai/ae_render_channel.py` ✅ 已完成
- `ai/material_intelligence.py` L944 ✅ 已完成
- `pipeline/unified_pipeline.py` ✅ 已完成（6 处）
- `pipeline/ffmpeg_edit_engine.py` ✅ 已完成
- `pipeline/stages/__init__.py` ✅ 已完成（resolve_ffmpeg/ffprobe env 优先）
- `pipeline/material_scanner.py` ✅ 已完成
- `pipeline/video_quality_assessor.py` ✅ 已完成
- `ai/production_director.py` L290-291 ✅ 已完成（并行任务已落地，默认参数改为 None + core.paths 兜底）
- `core/camera_movement_classifier.py`、`core/temporal_analyzer.py`：无硬编码路径（用相对 cache/）

### P1 — AE/Bridge/Adobe 全家桶

- `ae/ae_mcp_client.py` ✅ 已完成（2 处 bridge_dir）
- `ae/au_mcp_client.py` ✅ 已完成
- `ae/ps_mcp_client.py` ✅ 已完成
- `ae/pr_mcp_client.py` ✅ 已完成
- `ae/environment_validator.py` ✅ 已完成
- `workflow/creative_orchestrator.py` ✅ 已完成
- `workflow/creative_loop_dag.py` ✅ 已完成
- `ae/ae_process_manager.py` L123-125/695：AfterFX 候选列表（探测语义，保留）
- `ae/ps_process_manager.py`、`ae/au_process_manager.py`：同类（探测语义，保留）
- `bridges/adobe_suite_integration.py`：PS/PR/ME/ffmpeg 候选列表（探测语义，保留）
- `bridges/adobe_universal_bridge.py`、`bridges/adobe_open_source_integration.py`：同类（探测语义，保留）
- `ae/tests/test_ps_bridge.py`、`test_au_bridge.py`、`test_mcp_tools_validation.py`：测试硬编码（P3 批次）

### P2 — 素材获取/下载子系统

- `13-素材获取与搜索/01-下载器/*.py`（4 个）✅ 已完成：`_get_env_or_default` 支持 `AE_WORK_DIR` 前缀替换
- `13-素材获取与搜索/03-AI语义搜索/frame_extractor.py` ✅ 已完成：TEMP_FRAME_DIR
- `bilibili_creator_analyzer.py` ✅ 已完成：output_base_dir / cookies 候选

### P3 — 一次性脚本 / 示例 / 测试（低优先级，多为命令行入口或 demo）

> 状态：**暂缓**。理由：① 一次性验证脚本（`_run_v23_v24.py` 等）本机专用、无迁移价值；
> ② 测试文件里的 bridge 硬编码（`ae/tests/test_*_bridge.py`）是测试夹具语义，迁移需同步改断言，
> 收益低风险高；③ 示例文件（`ae/examples_*.py`）本身就该展示可读路径。
> 若要迁移，手法与 P0/P1 一致（`from core.paths import ...` + try/except 兜底）。

- `_run_v23_v24.py`、`_verify_v24.py`、`_measure_alignment.py`：V23 路径（验证脚本，本机专用）
- `analysis/*.py`（analyze_clip/visual_analysis/audio_analyzer_enhanced 等）
- `audio/*.py`（beat_sync_generator/audio_edit_engine 等）
- `ae/emotion_curve_generator.py`、`ae/text_animation_engine.py`、`ae/ai_scene_detector.py`
- `ae/examples_*.py`、`ae/tests/test_*.py`、`puppet-automation/*.py`、`ai/t3x_*.py`、`ai/t39_*.py`

### 不迁移（保留硬编码）

- **软件候选路径探测列表**（`ae_process_manager.py`、`adobe_suite_integration.py` 里的
  `C:\Program Files\Adobe\... 2023/2024/2025/2026` 多版本候选）—— 这是"探测"语义，不是"配置"，
  应保留多路径探测，仅将**命中结果**优先交给 env 覆盖。
- **docstring / 帮助文本里的示例路径**（`D:/output/matte_[####].exr` 等）。

## 五、注意事项

1. **并行任务占用文件**：`ai/camera_decision.py`、`ai/production_director.py`、`core/llm_gateway.py`、
   `ai/ai_agent.py`、`frontier_system.py` 正被另一个任务（camera_vocabulary + 审计）改动，
   **迁移这些文件前需等该任务落地**，避免冲突。（该任务已于 4a5619a 落地，production_director 已补完）
2. **`AE_WORK_DIR` 已有历史约定**：`integrations/topaz_integration.py`、`silhouette/silhouette_executor.py`、
   `integrations/blender_3d_integration.py`、`integrations/davinci_resolve_integration.py`、
   `ai/ai_video_generator.py` 已用 `os.environ.get("AE_WORK_DIR", r"D:\AE-Work")`，与本方案一致，无需改。
3. **迁移手法统一**：业务代码用 `from core.paths import xxx` 替换硬编码；对可能被独立运行的脚本，
   用 `try/except ImportError` 兜底保留旧默认值（参考 `video_generator.py` 的写法）。

## 七、配置机制收敛（坎 2/3，2026-08-14 追加）

**坎 3 — 四份重复 `_get_env_or_default` 收敛**：`core.paths.env_or_default()` 成为唯一实现
（.env 幂等加载 + `AE_WORK_DIR` 前缀替换 + `skip_keys` 代理跳过），四个下载器改为薄包装调用。

**坎 2 — ConfigManager 默认值接 `core.paths`**：`core/config.py` 的 `ae.install_path`、
`ffmpeg.bin_path`、`media_library` 八个目录默认值改由 `core.paths` 推导（未设 env 时字节级一致，
`AE_WORK_DIR` 可整体迁移）。`media_library.*` 保留正斜杠输出避免下游序列化差异。

**坎 4 — 自进化数据分流（2026-08-14 追加）**：
- 数据物理迁移 `data/self_evolution/` → `<AE_WORK_DIR>/self_evolution`（`AEK_SELF_EVOLUTION_DIR` 可覆盖）
- 5 个读写方收口：`core/self_evolution_engine.py`（DEFAULT_DATA_DIR + 启动自动搬迁）、
  `core/evolution/knowledge_sink.py`、`core/auto_evolution.py`、`core/experience_harvester.py`、
  `puppet-automation/src/api/evolution_routes.py`、`scripts/verify_learning_real_signals.py`
- git 停止跟踪 + `.gitignore` 规则；旧位置数据在引擎启动时自动搬迁（幂等、保留原件）
- 实测：引擎从新位置加载 100 条评审历史 ✓

**待办（后续批次，同类运行时目录）**：`data/digital_twin`、`data/pipeline_feedback`、
`data/observability`、`data/cost_log.jsonl`、`data/fallback_history.json` 等仍被跟踪，
可照此模式逐一迁移。

**已知差异（有意不合并）**：`media_library.video_dir`（`D:/AE-Work/resources/video`）与
`core.paths.video_library()`（`D:/AE-Work/视频素材库`）是历史上并存的两套目录约定，
合并需人工确认实际数据位置，暂不动。

## 六、验收标准

- [x] `core/paths.py` 存在且无项目内 import（零循环依赖）
- [x] `py -3.12` 下 AST 通过、函数 import 正常
- [x] 环境变量覆盖实测生效（`AE_WORK_DIR=E:/MyWork` → 所有 work 路径切换）
- [x] P0 核心引擎文件迁移（除 `ai/production_director.py` 待并行任务落地）
- [x] P1 AE/Bridge 迁移完成（四 MCP 客户端 + validator + workflow）
- [x] P2 下载子系统迁移完成（四下载器 AE_WORK_DIR 前缀替换 + frame_extractor + creator_analyzer）
- [ ] P3 一次性脚本/测试（暂缓，低价值）
- [x] `ai/production_director.py` L290-291（并行任务落地后补完）
- [x] 坎 3：四份 `_get_env_or_default` 收敛到 `core.paths.env_or_default()`
- [x] 坎 2：ConfigManager 默认值接 `core.paths`（ae/ffmpeg/media_library）
- [ ] 全仓库 `grep -n "D:/AE-Work\|D:\\\\AE-Work"` 仅剩 docstring/一次性脚本/探测列表
