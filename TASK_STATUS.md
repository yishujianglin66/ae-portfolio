# TASK_STATUS — AE-Knowledge-Vault 项目级任务看板

> 更新时间：2026-08-27 · 维护规范：任何会话结束前更新本表；单任务详细进度写 `00-每日记录/` 或 `09-计划文件/`
> 历史：原梁祝模型任务进度已归档至 `03-阶段报告/2026-07-28_梁祝模型修正任务进度归档.md`

## 总览

| 主线 | 状态 | 关键指标 | 负责人/会话 |
|------|------|---------|------------|
| 运镜分类器 | ✅ 本地端到端验证通过 | 2-class CNN bal_acc=0.67，CPU 0.02-0.31s，GPU 一致；分层架构 CNN+VLM 优雅降级已验证；**VLM 专家已本地部署（4bit 5.82GB 显存）并批量验收：28 条真实 AMV 跑通，弱真值子集 3/4=0.75（高于预期 0.55-0.65）；解析器已补强（正则化+伪静止词剔除+优先级调整），原 4 处 static 误判全修正；**08-27 增：光流物理标注器 v7.1（AMV 转场域感知，7 轮迭代）三角验证 VLM 一致率 43%——真实可靠性 40-60%，标签歧义源自转场 vs 相机运动定义；L0.5 分层 CNN+VLM 已接入 SourceCameraInventory 生产路径并 E2E 验证（orbit conf 0.79 + 静态纠偏），生产必须用 .venv python（4bit 仅此环境）** | 本地 RTX 4060 |
| 抠像链路 | ⚠️ 产物核查已闭环：权重在盘，MOV 丢失可重跑 | BiRefNet 动漫域 IoU 0.9756；MOV 365MB 已丢（report 留存） | 修复会话 |
| 木偶动画 | 🔄 进行中主线 | look_at 相机正立已突破；待固化进引擎 | — |
| 后端架构重构 | 🔄 Phase 0 完成，Phase 1 待启动 | 4 套 API 面→单一 Gateway | — |
| 项目治理（本方案） | 🔄 P0 全部执行完毕，收敛动作 1 项待批准 | P0-A/B/C/D 全闭环 | 当前会话 |
| MG动画/手书动画集成 | ✅ P0+P1 全部落地完成（含 P1-4/P1-6） | 64/64 测试通过；演示产物 + 两个新适配器 | 当前会话 |
| AEP 逆向工程补强 | ✅ 完成 (08-26) | 流水线全链路打通 + 性能优化（18.7MB: 78.5s→5.9s）；批量扫描 9 套 AE 新手工程 38.9s 全完成；matchName 噪声过滤器（19条规则）；5 种风格配方；知识库增量已写入 | 当前会话 |
| 系统稳定性增强 | ✅ 阶段完成 (08-27，含二次会话复验) | **测试套件全面修复完成：5119 passed/78F/40E → 5305 passed/0F/0E**；收集健康 5338/0 错误；修复 9 个 sys.exit 崩溃 + 84 个导入失败 + 78 个运行期失败 + 40 个收集错误；根目录治理 159→11 文件；引擎契约 21 类对齐；**08-27 复验修正：`pipeline/batch_queue.py` 两处竞态缺陷补修（终态锁外发布 / 回调挂晚，旧实现 196/200 批次回调丢失→0/200），`aiohttp 导入阻断`结论被诊断否证并已撤防（恢复 H3 请求超时）；竞态契约固化为常驻闸门 `TestCallbackRaceContract`（3 用例，反向验证对修复前实现 3/3 + 2/3 检出），导入污染取证固化为 `scripts/diag_import_guard.py`；复验全量 0 failed / 0 errors**；详见§测试套件全面修复 | 当前会话 |

## 治理行动项（来源：`09-计划文件/2026-08-20_全项目扫描分析与提升方案.md` §八）

### P0（本周）

| # | 行动项 | 状态 | 验收标准 | 证据/产物 |
|---|--------|------|---------|----------|
| P0-A | 补录每日记录 + 重建 TASK_STATUS 看板 | ✅ 完成 | 当日记录存在；看板含三主线状态 | `00-每日记录/2026-08-20_断更补录-08-08至08-20关键工作.md`、本文件 |
| P0-B | 产物一致性核查与修复 | ✅ 完成（2026-08-21） | 关键产物路径 100% 可 Test-Path 通过；文档同步 | 见「P0-B 核查台账」 |
| P0-C | 双协议诊断结论落地 | 🔄 只读确认完成（08-21），剩余 1 项收敛动作待批准 | 无双写竞争；单例哨兵 | `09-计划文件/2026-08-17_P0-2_AE桥接双协议只读诊断.md`、本表「P0-C 只读确认」 |
| P0-D | 产物清单（SHA-256+备份路径）登记 | ✅ 完成（2026-08-21） | 清单含 SHA-256 与备份路径 | `data/artifact_manifest.json`（7 产物，6 在盘 + 1 丢失可重跑） |

### P1（两周内）：P1-A 统一 API 网关 · P1-B CI 覆盖率采集 · P1-D 因果引擎质量接入 · P1-E 测试套件归并（含 08-27 复验发现的 `sys.path` 膨胀 ~300 条目收敛）— 全部待启动
**P1-C 根目录治理+LoRA 清理** ✅ **完成 (08-26)**: 根目录.py文件从159个减少到11个（↓93%），建立25+功能域包，创建135条import重定向规则

### P2（四周内）：P2-A FAISS 知识服务 · P2-B golden set 验收 · P2-C 数据层统一 · P2-D 调研转化 · P2-E 木偶 MP4 — 全部待启动

## P0-B 核查台账（2026-08-21 闭环）

| 产物 | 文档声称路径 | 磁盘实况（08-21 实测） | 处理 |
|------|-------------|------------------|------|
| BiRefNet 混合权重 | `external/birefnet/finetuned_anime.pth`（08-16 交接文档） | ✅ 实为 `finetuned_anime_mixed.pth`（844MB）+ `finetuned_anime_fp16.pth`（421MB）+ 基座 `model.safetensors`，均在盘 | ✅ 交接文档 2 处已改为实际文件名 |
| FATE alpha MOV (v17, 365MB) | `output/one_pipeline/DL_DL_FATE_r978_..._v17/..._alpha.mov` | ❌ 仓内与 `D:\AE-Work\渲染档案\one_pipeline\..._v17\` 均只剩 pipeline_report JSON（QC_PASS、finished_at 08-16 01:41 为证）；输入源 mp4 在盘 | ✅ 交接文档已标注「可重跑 v17 复现（约 31s）」，重跑归入 FATE 交付前必办 |
| 开源适配器（nexrender/MediaCrawler/firecrawl 等 52 文件） | `integrations/*.py`（08-11 集成方案） | ⚠️ 目录此前被清空；已从 `feat/phase1.1-gateway-consolidation`（4b8aa81 / adobe 3490aa2）恢复 | ✅ 恢复后 69/72 测试通过；剩余 3 失败=llm_gateway 缺 TASK_TIER_MAP/开源 TaskType（分支版 3362 行 vs 工作区 1380 行，差异大，随 P1-A 网关合并处理） |

## P0-C 只读确认（2026-08-21 实测）

| 检查项 | 实测结果 |
|--------|---------|
| Protocol A 加载入口 | ✅ 唯一活跃：Startup\`z_mcp_bridge_startup.jsx`（v4 延迟 5s）→ eval `PROJ_ROOT/ae_mcp_auto_listener.jsx` → `__startMcpPolling()`；`.ae-mcp-bridge/startup.log` 最近 4 次均 `Polling started OK`（最新 08-17 22:27） |
| Protocol B1 面板 | ✅ 已禁用：Panels 目录中为 `mcp-bridge-auto.jsx.disabled`（改名后缀关闭）；`Documents/ae-mcp-bridge` 仅残留目录（可清理，低优先） |
| Protocol B2 面板 | ✅ 非活动：`mcp_bridge_panel.jsx` 为项目内手动面板，不在 Startup/Panels 加载链 |
| 干扰进程 | ⚠️ **node PID 17320 = `c:\Users\Administrator\Desktop\after-effects-mcp-main\build\index.js` 存活**（诊断报告 §2.8 点名干扰源；注意路径是 Desktop 而非红线 external/）；其余 node=编辑器工具(npx chrome/modelcontextprotocol)，python 3 个均非 ae_tools_mcp_server.py，无干扰 |
| 结论 | 收敛动作仅剩 1 项：**Stop-Process 17320（及同类复活）**。B1/B2 已处于禁用态，无需再动；会话初清理建议固化进启动脚本 |

## MG动画/手书动画集成（2026-08-24 落地）

来源方案：`09-计划文件/2026-08-21_MG动画与手书动画集成设计方案.md`

### P0 适配器（代码 + 测试 + 注册表 全完成）

| 模块 | 文件 | 测试 | 状态 |
|------|------|------|------|
| SCAIL-2 角色动画 | `integrations/scail2_adapter.py` | ✅ 7/7 | ✅ 组件验证完成 (08-25): VAE/CLIP GPU 加载+前向，DiT 权重缺失已记录显存边界 |
| MuseTalk 唇同步 | `integrations/musetalk_adapter.py` | ✅ 6/6 | ✅ 源码已克隆 (external/musetalk) + 远程全链路推理完成 (08-25) |
| MatAnyone2 抠图 | `integrations/matanyone2_adapter.py` | ✅ 5/5 | ✅ 源码已克隆 (external/matanyone2) |
| Remotion Agent | `integrations/remotion_agent_adapter.py` | ✅ 5/5 | 适配器就绪，Remotion 项目待初始化 |
| AnimatedDrawings | `integrations/animated_drawings_adapter.py` | ✅ 3/3 | 适配器就绪 |

### P1 核心模块（代码 + 测试 + 演示产物 全完成）

| 模块 | 文件 | 测试 | 演示产物 |
|------|------|------|----------|
| MG 模板引擎 | `core/mg_template_engine.py` | ✅ 4/4 | `mg_data_chart_demo.mp4` (18KB) |
| MG 编排器 | `pipeline/mg_orchestrator.py` | ✅ 3/3 | `mg_orchestrated_demo.mp4` (31KB) |
| 手绘风格化 | `core/handdrawn_styler.py` | ✅ 4/4 | 4 种风格 PNG (pencil/ink/comic/watercolor) |
| 手书动画管线 | `pipeline/handdrawn_pipeline.py` | — | 通过 stylize 测试覆盖 |
| Lottie 导出 | `core/lottie_exporter.py` | ✅ 3/3 | `mg_lottie_demo.json` (7.6KB, valid=True) |

### P1-4 / P1-6 后续落地（2026-08-24 第二轮）

| 模块 | 文件 | 测试 | 状态 |
|------|------|------|------|
| ComfyUI 手绘风格化 | `integrations/comfyui_handdrawn_adapter.py` + `data/comfyui_workflows/handdrawn_style_transfer.json` | ✅ 7/7 | 服务端离线时自动 dry-run（生成可提交工作流 JSON）；产物 `handdrawn_comfyui_pencil_demo.workflow.json` |
| Motion Canvas | `integrations/motion_canvas_adapter.py` | ✅ 6/6 | 项目脚手架已真实初始化 (external/motion_canvas) + q4_chart/title_card 场景真实生成；渲染待 `npm install` |
| 注册表 | `integrations/integration_registry.py` | ✅ | 新增 `comfyui_handdrawn`/`motion_canvas`，总注册数 29 |
| 测试总计 | `tests/test_mg_handdrawn_integration.py` | ✅ 64/64 | 30.4s 全量通过 |

### 待完成项（全部下载完成，仅余 1 项环境搁置）

| # | 项 | 优先级 | 状态 |
|---|------|------|------|
| 1 | SCAIL-2 源码克隆 | P0 | ✅ 完成 (08-24): codeload ZIP 线路 (分支 wan-scail2)，已解压+验证 |
| 2 | 模型权重下载 | P0 | ✅ 全部完成 (08-24): SCAIL-2 15.5GB + MuseTalk 6.3GB (ModelScope) + MatAnyone2 141MB (GitHub Release) |
| 3 | Motion Canvas 真实渲染 | P2 | ✅ 完成 (08-24): npm 依赖安装 + tsc/vite 构建成功，适配器 render 真实执行 |
| 4 | AnimatedDrawings 源码 | P1 | ✅ 完成 (08-24): codeload ZIP 下载解压，核心包可导入 |
| 5 | Python 依赖 (torch 等) | P1 | ✅ 完成 (08-25): torch 2.13.0+cu126 (CUDA) / torchvision / diffusers / transformers / easydict / ftfy 等 |
| 6 | ComfyUI 真实推理 | P2 | ⏸ 需 ComfyUI 服务端启动 + GPU + checkpoint |
| 7 | GPU 真实推理验证 | P0 | ✅ 全部完成 (08-25): MatAnyone2 1278MiB / AnimatedDrawings 151KB / MuseTalk 核心链 5655MiB+8.30FPS / SCAIL-2 组件+边界；见 `00-每日记录/2026-08-25_01` |
| 8 | 远程 MuseTalk 官方推理 | P0 | ✅ 完成 (08-25): 32GB vGPU 全链路 inference.py，1024×1536 60s 1500帧 4.9MB mp4，峰值 4743MiB |

## 运镜分类器本地验证（2026-08-26）

### 验证结果

| 测试项 | 结果 | 详情 |
|---------|------|------|
| 合成视频 6 类 | ✅ 6/6 正确 | static→static(0.79), pan/zoom→motion(0.65-0.66) |
| 真实动漫 8 条 | ✅ 全部 motion | 置信度 0.69-0.88 |
| CPU vs GPU 一致性 | ✅ 完全一致 | CPU 0.20-0.31s，GPU 0.22-0.70s |
| 阈值 fallback | ✅ 正确 | static→static(0.65), zoom→motion(0.99) |
| 分层架构降级 | ✅ 优雅降级 | VLM 不可用时自动回退 2-class |

### 修复项
- VLM 加载增加本地缓存检测（无缓存时秒级失败而非卡死 2 分钟）
- 分层架构 VLM 加载失败时优雅降级（try/except 包裹）

### 待办
- ~~云端开机后下载 v6.4 产物 + 评测数据 + 标签集~~（已完成）
- ~~VLM 模型下载（15GB，需稳定网络或云端 GPU 环境）~~（✅ 已完成 08-27：云端补全→SFTP 拉回 13.8min/19MB/s，落 `D:\hf_cache`）

## AEP 逆向工程补强（2026-08-26）

### 新增/修复文件

| 文件 | 动作 | 内容 |
|------|------|------|
| `aep_analyzer/preset_generator.py` | 新增 | 效果链→JSX预设自动生成，含 11 个效果参数知识库 + 5 种风格配方 |
| `aep_analyzer/knowledge_extractor.py` | 修复 | 关键帧贝塞尔曲线详细提取 + 属性时间线 + None name 防御 |
| `reverse_engineer_pipeline.py` | 新增 | 统一流水线 CLI：扫描→提取→匹配→预设→报告，含 19 条 matchName 噪声过滤规则 |
| `config/style_reverse_presets.json` | 新增 | 5 种风格预设 JSON（赛博朋克/动漫混剪/复古胶片/清新文艺/音频响应） |

### 实测结果（Untitled Project.aep, 2.9MB）

- 27 合成 / 375 图层 / 247 matchName（过滤后保留真实效果 ~30 种）
- 风格匹配：动漫混剪 (0.5) + 赛博朋克 (0.4)
- 自定义链提取：Simple Choker→Tint, Brightness→Color Balance
- 输出：5 文件（scan/knowledge/style_matches/presets/report.md）

### 批量扫描 9 套 AE 新手工程（38.9s 全完成）

| 工程 | 大小 | 合成 | 图层 | matchName | 风格匹配 |
|------|------|------|------|-----------|----------|
| 8.15 | 18.7MB | 45 | 696 | 281 | 赛博朋克(0.4) |
| 9.23(do you mean) | 10.3MB | 9 | 140 | 120 | — |
| 五条悟 | 5.6MB | 19 | 262 | 234 | 赛博朋克(0.6)+动漫混剪(0.5)+复古胶片(0.5) |
| 初音 | 2.1MB | 1 | 35 | 97 | — |
| 李诗雅 | 9.9MB | 8 | 113 | 86 | — |
| 独自升级 | 3.2MB | 30 | 423 | 161 | — |
| 猫猫 | 16.1MB | 58 | 1366 | 330 | 赛博朋克(0.4) |
| 美人鱼 | 6.1MB | 31 | 472 | 369 | 赛博朋克(0.6) |
| 蓝色监狱 | 8.3MB | 53 | 720 | 208 | 动漫混剪(0.5)+复古胶片(0.5) |

### 解析器性能优化

| 优化项 | 效果 |
|---------|------|
| `_extract_paths_from_text` 盘符预过滤 | PATH_RE 正则跳过 99%+ 垃圾文本 |
| `_global_supplement_scan` 大文件跳过(>5MB) | 避免重复扫描 |
| 18.7MB 文件 | 78.5s+ → 5.9s |
| 9 套批量 | 超时未完成 → 38.9s |

## 根目录治理完成（2026-08-26）

### 治理成果

| 指标 | 治理前 | 治理后 | 改善 |
|------|--------|--------|------|
| 根目录.py文件数 | **159** | **11** | ↓ 93% |
| 功能域包数量 | ~15 | **25+** | ↑ 67% |
| import重定向规则 | 0 | **135** | 新建 |

### 最终根目录结构（11个核心文件）

```
根目录/
├── _import_redirect.py        # Import兼容层（135条规则）
├── ae_agent_pipeline.py       # AE管线入口
├── api_server.py              # API服务入口
├── bootstrap.py               # 启动引导
├── config_schema.py           # 配置模式
├── database.py                # 数据库
├── exceptions.py              # 异常定义
├── frontier_system.py         # 主系统入口
├── logger.py                  # 日志配置
├── system_memory.py           # 系统内存
└── ultimate_video_factory.py  # 视频工厂入口
```

### 三批次迁移统计

| 批次 | 迁移文件数 | 删除重复 | 保留不同 | 错误 |
|------|-----------|---------|---------|------|
| 第一批 | 30 | 0 | 0 | 0 |
| 第二批 | 63 | 0 | 26 | 0 |
| 第三批 | 24 | 3 | 25 | 1 |
| **总计** | **117** | **3** | **51** | **1** |

### 关键产出

- ✅ 根目录.py文件从159个减少到11个（↓93%）
- ✅ 建立25+个功能域包，结构清晰
- ✅ 创建135条import重定向规则，向后兼容
- ✅ 安全处理版本冲突，无数据丢失
- ✅ 详细报告：`ROOT_CLEANUP_COMPLETE.md`

## 阻塞问题

| # | 问题 | 依赖 |
|---|------|------|
| B1 | ✅ 已闭环：FATE MOV 确认丢失，report 留存，可重跑复现 | — |
| B2 | ✅ 已闭环：适配器已从 feat 分支恢复并验证 | — |
| B3 | ⏸ 收敛动作最后 1 项：杀干扰 node 17320（after-effects-mcp-main） | 用户批准（杀进程触及活跃环境，按约定需确认） |

## 红线提醒

- 禁改 `external/after-effects-mcp/src/index.ts` 与 `external/after-effects-mcp/src/scripts/mcp-bridge-auto.jsx`（基线 94609 字节）
- 证据闸门铁律（commit `f4f738c`）：「已完成」结论必须实测验证后才可登记 ✅

## pytest全量收集超时专项排查完成（2026-08-26）

### 结果：无限挂起 → 10.2秒收集 4599 测试，0 错误

### 根本原因（三层叠加）

1. **collect_ignore 路径前缀错误（主因）**：`tests/conftest.py` 中条目写成 `os.path.join("tests", f)`，而 collect_ignore 是相对于 conftest 所在目录解析的，导致 **75 条忽略规则从未生效**，破损/阻塞文件全部被真实导入
2. **伪测试脚本模块级阻塞**：6 个 `test_*` 文件实为交互式脚本（模块级 sleep/启动 DaVinci/触发真实渲染/连 AE 客户端），收集时执行导致数十秒到数分钟阻塞（串行测量见 `temp/collection_timing.json`）
3. **模块级状态污染**：`test_roto_service.py` 注入 `__path__=[]` 的空 mock `src.engines`，阻断后续 `src.engines.*` 解析；`_import_redirect.py` 误将 4 个 `test_*` 模块名加入重定向表，劫持 pytest 同名收集；`test_layer_render_service.py` 裸名 `from config.settings import` 与项目根 config 包冲突

### 修复清单

| 文件 | 修复 |
|------|------|
| `tests/conftest.py` | 去掉 `tests/` 前缀使忽略生效；新增 25 个问题文件（6 伪测试 + 19 导入错误）并附原因注释 |
| `_import_redirect.py` | 移除 4 个 `test_*` 重定向条目（禁止重定向测试模块名） |
| `tests/test_layer_render_service.py` | 裸名导入改为 `spec_from_file_location` 显式路径加载 |
| `tests/test_roto_service.py` | mock 包 `__path__` 指向真实 engines 目录，不再阻断子模块解析 |
| `tests/test_topaz_engine.py` | ~~连带修复（roto 污染解除后自动恢复）~~ 已证伪：运行期 4 errors 实为引擎自身契约缺陷，见下节专项修复 |
| `tests/test_camera_classifier.py` | 连带修复（重定向劫持解除后自动恢复） |

### 诊断工具链（沉淀于 tmp/）

- `tmp/_measure_collection.py`：逐文件隔离进程导入计时（单文件 10s 超时）
- `tmp/_scan_blocking.py`：AST 扫描模块级阻塞调用（input/sleep/urlopen/while）
- `tmp/_collect_watchdog.py`：faulthandler 90s 栈转储
- py-spy dump 挂起进程栈：直接定位挂死文件（本次关键突破）
- 二分法组合复现：定位跨文件状态污染（layer+roto→topaz）

## topaz 运行期错误修复完成（2026-08-26）

### 结果：`test_topaz_engine.py` 1 passed + 4 errors → **5 passed**；全量收集健康保持（4599 测试 / 0 错误）

### 根本原因（引擎与新基类契约脱节，两处）

1. **抽象方法未实现（4 errors 直接原因）**：`BaseEngine` 已升级为模板方法模式——`execute()` 是 final 模板（负责 available 短路/异常包裹/时长统计），子类必须实现抽象方法 `_execute_impl()`。而 `TopazEngine` 仍直接覆盖 `execute()`、从未实现 `_execute_impl` → `TypeError: Can't instantiate abstract class`，fixture 实例化失败。
2. **`_run_subprocess` 返回值契约变更未跟进**：基类该方法已改返回 4 元组 `(code, stdout, stderr, error_code)`，但 topaz `enhance()` 内仍按 3 元组解包 → 即使能实例化，真实执行也会 `ValueError: too many values to unpack`。

### 修复（仅改 `puppet-automation/src/engines/topaz/engine.py`）

| 改动 | 说明 |
|------|------|
| `execute()` → `_execute_impl()` | 保留 action 调度语义；短路/异常/时长统计交还基类模板；对外 `execute()` 公共接口由基类保留，调用方零改动 |
| 3 元组解包 → 4 元组 | `code, _stdout, stderr, _err_code`，匹配新 `_run_subprocess` 契约 |

### 验证
- `test_topaz_engine.py` 5 passed
- 组合冒烟 `test_topaz_engine + test_roto_service + test_layer_render_service` = 104 passed（确认与 roto 的 `src.engines` mock 同跑无类身份冲突）
- 调用方核查：`beat_video_service.py` 直接调 `enhance()`，仅内部解包变化，对外签名零改动；`registry.py` / `api/main.py` 经 `execute()` 公共接口不受影响

## 引擎契约批量对齐完成（2026-08-26）

### 结果：继承 `BaseEngine` 的全部引擎子类实现对齐，21 个引擎类 `__abstractmethods__` 清零、可实例化、`execute()` 路径均返回 `EngineResult`

### 范围与处置（含一次误改回滚）
- **改名 `execute()`→`_execute_impl()`（12 个，均确认继承 `BaseEngine`）**：audition / davinci / media_encoder / moviepy / openmontage / photoshop / premiere / rife / sam2 / silhouette / whisper；`pr` 为 `PremiereEngine` 别名随继承生效。
- **`_run_subprocess` 3→4 元组解包（同批 9 处）**：davinci / media_encoder / moviepy / openmontage×2 / rife / sam2 / silhouette×5。
- **⚠️ 误改回滚（2 个）**：`comfyui`、`flux3` 是**独立类**（不继承 `BaseEngine`），本就不受抽象方法约束；首轮按"覆盖 execute()"粗扫描误改名导致 `no attribute 'execute'`，已回滚保留自有 `execute()`。

### 关键教训
批量修复前**必须逐个确认 `class XxxEngine(BaseEngine)`**——仅凭"覆盖了 execute()"扫描会把独立引擎（如 comfyui/flux3）误纳入，改名反而删掉其对外接口。

### 验证
- 21 引擎类 `__abstractmethods__` 全空、实例化成功、未知 action 经基类模板返回 `EngineResult`（`tmp/_verify_engines_contract.py`）
- `test_all_engines.py` 8 passed；`test_topaz_engine.py` 5 passed；`test_sam2_engine_integration + test_matting_engine` 24 passed（1 个环境性既有失败：sam2 模块在环境中可导入与"未安装"预期不符，与本改动无关）
- 全量收集健康保持（4599 测试 / 0 错误）
- 遗留（既有、与本改动无关）：`test_import_paths_regression` 4 个失败（引用已移除的 `bridges/*` 模块）、`test_engine_registry` 缺 `core.engine_registry` 模块

## 测试套件全面修复完成（2026-08-27）

### 最终结果

| 指标 | 修复前 | 修复后 | 改善 |
|------|--------|--------|------|
| passed | 5119 | **5305** | +186 |
| failed | 78 | **0** | -78 |
| errors | 40 | **0** | -40 |
| 收集数 | ~4600 | **5338** | +738 |
| 收集错误 | 多 | **0** | 清零 |

### 修复阶段与关键动作

| 阶段 | 内容 | 解锁/修复用例数 |
|------|------|---------------|
| Phase 1 | bridges 子系统恢复（从 git 历史）+ 35 模块回归 | 33 passed |
| Phase 2 | 路径修复 + 重定向 + toolchain 迁移 + ai_agent 对齐 | 52 passed |
| Phase 3 | 8 个丢失 core 模块恢复 + JSON 资源 + DAGOrchestrator 移植 + style_transfer 拆分 | 72+ passed |
| 串扰修复 | test_roto_service sys.modules 快照-恢复密闭化 | 4 errors→0 |
| 串扰修复 | test_layer_render_service 合成 src.engines.* 清理 | 15F→0 |
| 串扰修复 | test_p1_stock_e2e skipif 改环境变量 | 1E→0 |
| 契约修复 | style_copy 4 文件 + toolchain_manager 恢复 | 36 passed |
| 契约修复 | llm_gateway 30 Gap 契约（熔断器+路由兜底+密闭化） | 135 passed |
| 契约修复 | core_config 黄金版替换 + 契约修复 | 202 passed |
| 契约修复 | puppet 脚本迁移 + func=None 防御 + method 修正 | 121 passed |
| ~~防御修复~~ | ~~_h3_request aiohttp import 防御~~ **已证伪并于 08-27 复验时撤除**（见下方§复验与根因修正） | 2F→0 的说法不成立 |

### 关键经验

1. **sys.modules 快照-恢复模式**：测试文件在模块级注入 mock 包后必须恢复，否则全量运行时污染后续文件
2. **合成包陷阱**：`type(sys)("pkg.sub")` 创建的空壳包无 __init__.py 执行，后续真实导入命中缓存导致 ImportError
3. **builtins.\_\_import\_\_ 泄漏假说已被否证**（08-27 复验）：哨兵全量零告警、`PathFinder` 对 aiohttp 及其依赖零次未命中，延迟 import 并未被阻断；当时那 2 个失败的成因另在别处（见下方§复验与根因修正）。**不要**为"预防"这类不存在的阻断给生产代码加 try/except
4. **collect_ignore 路径解析**：条目相对 conftest.py 所在目录解析，子集运行绕过 conftest 导致收集错误
5. **"跑一次全量绿"不等于零失败**：时序竞态用例的特征是单跑挂、连跑过、全量看负载，必须用重复运行/压测守住
6. **回归闸门必须反向验证**：写完守门用例后，用 `git show HEAD:<旧路径>` 取回修复前实现跑同一用例，确认它**确实失败**——本会话第一版闸门对修复前实现全绿（缺陷窗口微秒级 vs `wait_for_task` 100ms 轮询），属于永远绿灯的无效闸门。另注意生产代码 `except Exception: pass` 包住回调，会把测试自身的错误伪装成"契约全面违规"

### 复验与根因修正（2026-08-27 二次会话）

上一会话收尾的"5305 passed / 0 failed"经复验**不成立**：实测 `1 failed, 5304 passed`，红点为 `test_batch_queue.py::TestBatchQueue::test_on_complete_callback`，且隔离运行同样失败（非串扰）。深挖出两个真实并发缺陷并修复：

| # | 位置 | 缺陷 | 修复 | 证据 |
|---|------|------|------|------|
| 1 | `pipeline/batch_queue.py::_execute_task` | 终态 `status=COMPLETED` 在**锁外**赋值，`on_complete` 在**锁内** `finally` 才触发 → `wait_for_task` 可返回"已终态但回调未跑"的任务（实测相差 0.15ms） | 摘除 `_running` + 发布终态 + 计数 + 触发回调合并进同一临界区；`on_failure` 同步纳入；`BaseException` 穿透时也保证摘除 | 竞态压测 complete/failure 各 300 轮 + 并发 200 任务，违规 0 |
| 2 | `pipeline/batch_queue.py::submit_batch` | 先 `submit()` 再回头挂 `t.on_complete`，worker 快于主线程时整批回调**永不触发**；`combined(task=task)` 误用循环遗留变量；批量回调读到仍在 append 的共享列表 | 回调在 `submit()` 时原子挂载；"全部提交完成 且 全部执行完成"双条件触发；传入列表快照；用户回调异常隔离 | 同一压测：旧实现 **196/200 轮丢失**，新实现 **0/200** |
| 3 | `core/llm_gateway.py::_h3_request` | `import aiohttp` 的 `try/except → client_timeout=None` 退化防御 | **撤除防御，恢复直接导入** | 只读诊断插件全量取证：PathFinder 未命中 0 次、sys.path 无丢失、meta_path 无异常、aiohttp 恰在 h3 用例内导入成功；撤防后全量仍 0 failed |

**撤防的真实收益**：该防御并非"无害兜底"，它在生产环境会静默丢掉每次请求的超时设置（退化到 session 级），属于隐藏症状。

最终验证：`5308 passed / 33 skipped / 0 failed / 0 errors in 973.98s`（较复验前 +3，即新增的常驻竞态闸门）。
详见 `00-每日记录/2026-08-27_16-测试套件竞态缺陷修复-开发进度.md`；取证工具已固化为 `scripts/diag_import_guard.py`（导入污染诊断插件）与 `tests/test_batch_queue.py::TestCallbackRaceContract`（竞态闸门，替代原 `tmp/` 一次性压测脚本）。

**提交已落盘（2026-08-27，master 本地两提交，未推送）**：阻塞成因经确认成立——治理批次未入库时，`_import_redirect.py` 的 132 条规则里有 **116 个目标模块既不在 HEAD 也不在索引**，单独提交 `pipeline/batch_queue.py` + 新闸门会得到一个 clean checkout 下**必然失败**的提交（裸名 `from batch_queue import ...` 会解析到未修复的根模块）。故按方案 A 连迁移批次一并入库：

| 提交 | 内容 | 规模 |
|---|---|---|
| `116fa20` `refactor(root)` | 118 处根级 `.py` 按功能域分包 + 59 处 `tests/` 手工脚本移入 `scripts/`（git 识别 rename 共 177）、`_import_redirect.py`、清除 18 个误跟踪 `__pycache__/*.pyc`、`.gitignore` 补 `models/weights/` | 584 files, +113132 / −26257 |
| `648d18d` `fix(pipeline)` | batch_queue 两处竞态修复 + `TestCallbackRaceContract` 闸门 + llm_gateway 撤防 + `scripts/diag_import_guard.py` 转正 + 08-27 三份文档 | 8 files, +5053 / −736 |

原"建议落 `feat/project-consolidation-v1`"**已被否证**：该分支与 master 分叉且相差 1117 个文件，搬运 598 条脏改动风险远高于收益，最终留在 master。强制排除三项：`models/weights/`（32 文件 / **26.5 GB** Qwen3-VL 基座权重，此前未被忽略，`git add -A` 会直接吞入）、无 `.gitmodules` 映射的嵌套仓库 `OpenSpace` 与 `external/OpenMontage`、测试运行期写入的 `user_data/user_test_user.json`。密钥面扫描 332 个未跟踪文件仅 1 处命中，为 `auth/auth_system.py:943` `_run_tests()` 内的测试夹具常量，非真实凭据。

提交后自洽性校验（`scripts/verify_tree_coherence.py`，与 `scripts/secret_scan.py` 同已转正为长期设施）：HEAD 跟踪 3606 文件，131 条重定向规则目标 **131/131 全在库内**，生产代码与测试的项目模块引用缺失 **0**（唯一告警 `style_copy` 为隐式命名空间包，校验脚本误报）；全量收集 `5341 collected in 15.36s` 0 errors，受影响面复跑 `230 passed, 1 skipped`。

**新发现的技术债（供 P1-E）**：全量运行后 `sys.path` 膨胀至约 **300 条**（大量 `tests/`、仓库根、`13-素材获取与搜索/*` 重复条目），源于几乎每个测试文件模块级 `sys.path.insert(0, ...)`；未命中的导入需扫描 300 个目录，是全量耗时 14:55 的因素之一。

**技术债已闭合（测试污染被跟踪数据文件）**：全量运行会写入 `13-素材获取与搜索/03-AI语义搜索/user_data/user_test_user.json`（本次实测 +254 行、`happy` 275→365，累计已膨胀至 1038 行 / 25 KB）。根因是 `smart_matcher.py:77` 构造 `UserPreferenceLearner()` 不传 `data_dir`，而 `user_preference.py:67` 的默认值指向**源码同级目录**——`recent_actions` 按 user_id 无界累积，于是每跑一次测试仓库就脏一次，`git status` 干净这一前提永久失效。修复：

| 改动 | 内容 |
|---|---|
| `user_preference.py` | 新增 `_default_data_dir()`，默认目录移至 `~/.ae-knowledge-vault/user_preference/`（沿用 `core/config.py` 已有的 `~/.ae-knowledge-vault/` 约定）；显式传 `data_dir` 的调用方行为不变 |
| `smart_matcher.py` | `SmartMatcher.__init__` 新增 `preference_data_dir` 并透传给 learner，与既有 `index_path` 注入风格一致 |
| `tests/test_smart_matcher.py` | `TestSmartMatcher.setUp` 注入 `tempfile.mkdtemp()`，与同文件 `TestUserPreference` 一致 |
| 入库处置 | `user_test_user.json` 属误提交的测试残留（该目录仅此一个文件、user_id 固定 `test_user`），`git rm --cached` 取消跟踪并忽略旧路径，本地文件保留不删 |
| 常驻闸门 | `tests/test_user_preference.py::TestDefaultDataDirOutsideRepo` 断言默认目录不在仓库内——盯根因（默认值本身）而非某个用例的后果 |

闸门已反向验证：把默认值临时改回缺陷版，`test_default_data_dir_is_not_inside_repo` 以 AssertionError 指名缺陷路径检出（1/1），还原后 67 passed。验收方式：跑完测试比对仓库内画像文件 sha256 不变。

**端到端验收通过（2026-08-27 21:23，全量）**：`5310 passed, 33 skipped, 0 failed in 626.88s`（较修复前 5308 多出的 2 项即新增常驻闸门），pytest exit code 0；同一轮内 `git status --porcelain -uall` 脏项 **0 → 0 条**；旧画像文件指纹全程未变（size 25165、mtime 1787826878、sha256 前缀 `3ae92bebfaf9a2ac`）。验收脚本固化为 `scripts/verify_no_test_pollution.py`，结论落盘 `tmp/verify_no_test_pollution.log`。判据特意做成**双通道**（git status 一致性 + 旧目录逐文件 mtime/内容哈希）：旧路径现已受 `.gitignore` 中 `13-素材获取与搜索/03-AI语义搜索/user_data/` 规则覆盖，代码若退回缺陷行为，单看 `git status` 会静默判"通过"。

**缺陷已闭合：`.gitignore` 白名单被后写全局规则静默作废**。提升为常驻闸门 `scripts/audit_gitignore_negations.py` 后机器枚举出 **7 条死白名单**（我手工只发现 2 条），根因是两条互不相干的 git 语义：

| 死规则 | 被谁作废 | 语义 |
|---|---|---|
| `!install_adobe_bridges.ps1`、`!close_dialog.ps1`、`!D盘AE脚本管理器.ps1`、`!puppet-automation/scripts/*.ps1`、`!mcp-extension/install.ps1` | 全局 `*.ps1` | 最后匹配生效，白名单写在前面 |
| `!05-测试套件/test_resources/*.png` | 全局 `*.png` + `resources/` | 同上，且其父目录另被排除 |
| `!cache/.gitkeep` | `cache/` | **父目录被排除时文件级 `!` 永远无效**，git 不进入被排除目录匹配 |

修复三处：① 2026-08-16 那段白名单整体下移到文件末尾新增的"误伤白名单"段，并在原位置留注释写明"白名单只能写在末尾"，防止后人再往前追加；② `test_resources` 额外补 `!05-测试套件/test_resources/` 先重新纳入被 `resources/` 排除的目录，文件级白名单才可能生效；③ 直接删除 `!cache/.gitkeep`——全库无任何被跟踪的 `.gitkeep`，将来确需占位须写成三行式 `!cache/` + `cache/*` + `!cache/.gitkeep`（已在注释注明）。

**闸门反向验证**：同一个 gate 跑 `HEAD` 版缺陷配置 → 7 条全检出、exit 1，并逐条指名作废它的具体规则；跑修复后配置 → 有效 11 / 失效 0、exit 0。不是笼统报"配置有问题"。

**顺带补上的功能缺口**：`close_dialog.ps1` 此前**从未进过版本库**——磁盘上存在但被自己的死白名单挡在库外，而它是 `core/pipeline_fault_policy.py:47`（`LICENCE_POPUP_BLOCKING` 的标准处置动作）与 `docs/superpowers/specs/2026-07-31-flagship-pipeline-design.md:143`（"AE 许可证弹窗阻塞｜高风险｜S3 一直挂"的缓解手段）点名的脚本。即任何 clean checkout / 第二台机器都缺这份脚本，而 `git clean -Xdf` 会删掉唯一副本。本次已 `git add` 入库。内容经人工审查：UTF-16 LE 编码，仅对 Premiere Pro 的 CEF 子窗口 `PostMessage` 一次 Enter（WM_KEYDOWN/KEYUP + VK_RETURN），**不含进程终止逻辑**，不触碰"禁止强杀 AE 进程"红线，无凭据字符串。

**修掉 `scripts/secret_scan.py` 一个真实盲区**：PowerShell 默认写 UTF-16，正文每个 ASCII 字符后跟 NUL，被原有"含 NUL 即二进制"启发式直接跳过——即此前所有 `.ps1` 从未真正被扫过。改为先按 BOM 识别 UTF-16 再解码；正向对照验证通过：UTF-16 编码的伪凭据现能被检出（旧逻辑下 `NUL in head: True` 会跳过）。修复后本批扫描 5/5 文件 0 命中。

**仍需人定夺**：① `output/evidence/` 13 份历史证据（被 `.trae/rules/evidence-gate-rules.md` 与 10 个脚本按路径引用）是否继续留库；② `external/OpenMontage`、`external/rife` 两个无 `.gitmodules` 映射的 gitlink（磁盘上是完整克隆，114 / 52 文件 + 各自 `.git`）是补正规 submodule 还是撤索引。另记一笔：`git branch -a` 显示存在一个名为 `origin` 的**本地分支**（指向 `9b956eb`），与远端跟踪引用同名易混，疑似误建，未动。


## 2026-08-26 里程碑

- ✅ **topaz 运行期错误修复**：`TopazEngine` 对齐新 `BaseEngine` 模板方法契约（实现 `_execute_impl` + `_run_subprocess` 4 元组解包），`test_topaz_engine.py` 4 errors→5 passed。
- ✅ **引擎契约批量对齐**：继承 `BaseEngine` 的 12 个引擎（+topaz 共 13）全部实现 `_execute_impl`，`_run_subprocess` 4 元组解包统一；独立引擎 comfyui/flux3 误改已回滚。21 引擎类抽象方法清零、可实例化。
- ✅ **证据闸门合规自检工具链交付**：`scripts/evidence_gate_compliance_audit.py`（五闸门机器化 + GB/T 47507-2026《人工智能 可信赖 通则》/ GB/T 45652-2025 条款映射），16/16 测试通过；运镜 4 元类标签集真实审计五闸全过（`reports/compliance_camera4/`），数字与 2026-08-24 人工核验一致。详见 `00-每日记录/2026-08-26_证据闸门合规工具链与材料核实-开发进度.md`
- ✅ **运镜去噪重标注实验完成（负结果，证据链闭合）**：专家去噪标签重训 2 类 CNN（与基线完全同协议），best bal_acc=0.6525 < 基线 0.6725；2 类 0.67 定性修正为**帧差特征的任务信号上限**而非标签噪声天花板；分层混合架构交付决策不变，运镜方向无剩余未做实验。详见 `00-每日记录/2026-08-26_证据闸门合规工具链与材料核实-开发进度.md` §三
