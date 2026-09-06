# TASK_STATUS — MasterCut（原 AE-Knowledge-Vault）项目级任务看板

> 更新时间：2026-08-27 · 维护规范：任何会话结束前更新本表；单任务详细进度写 `00-每日记录/` 或 `09-计划文件/`
> 历史：原梁祝模型任务进度已归档至 `03-阶段报告/2026-07-28_梁祝模型修正任务进度归档.md`
> 注：本表为**工程平台**看板（08-31 后冻结）；视频主线（run53 母版精修 v2→v7）进度记录于 `docs/handoff-2026-09-0X-*.md` 交接系列。

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
| 开源增强 E0 波（`09-计划文件/2026-09-05_开源增强选型与规则蒸馏方案.md`） | ✅ E0 全波 READY + **E1-1 规则蒸馏引擎 v1 落地** | **09-05 执行战果**：① E0-3 kb_loader 修复——knowledge/ 轨 6 知识库根全悬空（缓存全零），修复后 470/470 收录、effect_map 0→1508、llm_gateway 注入复活；② performance/ 包按契约重建，5354 收集 0 错误；③ ruff 基线 72→0，**主线 4 处真 bug 修复**（FFPROBE 漂移修复静默失效 / 曲线变速 NameError / 自进化 target_duration / 双 api_server 接口必崩）；④ E0-4 验收 UI `scripts/acceptance_ui.py`；⑤ DVC 备份链路+计划任务每日 03:00+test-health CI 三闸门；⑥ **E0-1 鼓点锚定生产接入（二轮 A/B PASS）**：一轮证伪（切点池未消费锚点，两臂 plan 相同）→ 真接入（`_onsets` 鼓锚 153 替换笼统 222 + beatgrid kick/strong/weak/rolls stem 覆盖 + 拍点吸附/SFX 强集升级）→ **kick|snare 踩拍 0.667 vs 0.519（+14.8pp）、笼统踩拍 0.808（run53 基线 0.7712）、plan 切点 96% 落鼓锚±80ms 中位 28ms、切点 82 vs 115 更少更准**；权重 SHA 终验入 manifest+dvc，证据 `output/evidence/enhance_drum_anchor_20260905/`；⑦ E0-2 python-stretch 可用。⑦ **正式参照集评分：beat_hit_rate 0.8077 超参照均值 0.7559（run53 基线 0.7712），距前三分位 0.8193 差 1.2pp**，语义分 dynamism/pacing/overall 全面领先参照均值，新短板=cut_visibility 0.674（低于参照下限）+ hf_energy 26.5 vs 50（v8 主攻）；⑧ **E1-1 规则蒸馏引擎 v1**：`scripts/rule_registry.py`（seed/list/vote/retire + cut_anchor_allowed 消费 API）+ 首条真规则 R-2026-0001（鼓点锚定，带适用域 schema）+ production_director 规则裁决闭环（retire→自动回退启发式）。⑪ **run55 精修版渲染成功**（用户手动 aerender，polish_pass 同款配方；此前 4 连死=TDR+空渲染队列，死因链已固化进方案文档）+ 正式评分：hf_energy 26.5→62.4 修复、语义分 7/7 平或领先参照均值、beat_hit_rate 0.7912 （超参照均值 0.7559，未过前三分位 0.8193）；新短板=cut_visibility 0.587 （Glow/颗粒与切点帧差指标固有张力）+ peak 1.0 削波（limiter 需留 headroom）；待用户听感复判 R-2026-0001。⑫ **R-2026-0002 验收通过（09-06）**：网格量化锚（事件选择×网格相位）+ 旋律锚 + 13 源多样性 + v9 语法短 dip，四轮迭代 run57→60；用户听感'比之前好'（两次否决后首次正面）+ 正式评分 beat_hit_rate **0.8455 超前三分位线 0.8193**（v9=0.7712），cut_visibility 0.587→0.8696；规则转正 active。剩余空间：cut_visibility 0.87 vs 0.955、peak 削波、composition/texture 微差。⑬ **run61 三项修复验证**（09-06）：闪白覆盖 drop 段 2/3→3/3 → cut_visibility 0.8696→0.8698（**无显著变化**——剩余 0.955 差距是结构性的，参照集为硬内容跳变，需撞击帧内容方案（AEKV_IMPACT_SHIFT 重评）而非闪白频率）；peak 修剪被 AAC 编解码过冲击败（0.85+limiter 解码仍 0.0dB）——**真修点在 upstream SFX 混音 limiter 0.95→0.88**（需全链重建生效）；语义分与 beat_hit_rate 0.8455 全部保持。run61 = 当前最佳候选（master_hr.mp4）。⑨ **分层分类器 OOM 已修复**：根因=VLM 专家 4K 抽帧不缩放（视觉 token 爆炸单次 12.21GiB）；修复=vlm_expert_3class.extract_frames 限边 512px，实测 4K 源 tilt-orbit conf 0.792/66s，run55 全管线运动标注复活；⑩ **v8 候选 run55 成片**（真实运动标注+鼓锚，评分与锚点臂完全一致=确定性验证），beat_hit_rate 0.8077 保持，精修 v2（51 层 MASTER）aerender 渲染中。**新登记缺陷**：分层分类器长素材单次分配 12.21GiB 显存 OOM 降级（运动标注线预存 bug，需分块推理修复）。**下载教训：hf-mirror 分片内容不可信，官方 xet 通道+代理 SHA 精确一致** | 当前会话 |

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

**当时的两项待定，现已全部处置**：① `output/evidence/` 13 份历史证据 → 决定维持"已跟踪 + 目录仍忽略"，理由与量化后的真实风险见下方"`output/evidence/` 刻意不加白名单"；② `external/OpenMontage`、`external/rife` 两个无 `.gitmodules` 映射的 gitlink → 撤索引，并把其中一个不可公网拉取的私有补丁转为受跟踪的 `.patch`，见下方"external/ 两个 gitlink 处置"。另记一笔：此前此处写过"存在一个名为 `origin` 的本地分支（指向 `9b956eb`）"——**该记录有误，2026-08-30 更正**：不存在名为 `origin` 的本地分支（`git rev-parse origin` → fatal: unknown revision）；当时 `git branch -a` 里看到的 `origin/...` 是 `remotes/` 命名空间下的远端跟踪引用，与本地分支列表并排显示造成误读。`9b956eb` 实为本地分支 `feat/project-consolidation-v1` 的 head，是正常特性分支，不可删。


## tracked-but-ignored 积压清零完成（2026-08-27 深夜）

**结果**：`git ls-files -ci --exclude-standard` 计数 **144 → 137 → 15 → 13**。第一阶段（144→137）由 `.gitignore` 白名单修复自动完成；第二阶段取消跟踪 122 个运行产物（`d61aab0`），当时剩 15 项 = 13 份 `output/evidence/` + 2 个 gitlink；gitlink 处置见下一节，终值 13 项全部为有意保留的历史证据。

**删除前的引用依赖审计**：对清理集逐文件 `git grep -F` 反向搜索（扫 `*.py *.jsx *.json *.ps1 *.sh`）。结论是这些路径全部为**写入目标**或**带存在性守卫的读取**——`tests/test_v17_e2e.py` 只有 `os.makedirs(OUTPUT_DIR, exist_ok=True)` + `open(..., "w")`；`core/experience_harvester.py` 的四处读取均包在 `if not path.exists(): return` 内。唯一看似强引用的 `output/evidence/git_branch_diff_20260818.json` 出现在文档正文里，是**已存证据中记录的路径字符串**，不是代码依赖。

**干净检出三向对照验证**（临时 worktree，验毕即删）：

| 检出点 | `pytest --collect-only -q` |
|---|---|
| 主工作树 `d61aab0` | 5343 collected，exit 0 |
| 清理后 `d61aab0` 干净检出（122 文件已不存在） | 5343 collected in 41.74s，exit 0 |
| 清理前 `9e639d2` 干净检出（122 文件仍在） | 5343 collected in 33.36s，exit 0 |

三向数字完全一致，说明没有任何测试模块在 import 期依赖被取消跟踪的产物。差异真实性也做了机器核对：清理集中 116/122 在"清理前检出"存在而在"清理后检出"缺失；另外 6 个是 `puppet-automation/src/engines/*/__pycache__/*.pyc`，两侧都在——因为它们**被我这次收集运行自己重新生成了**。这既排除了假阴性，也直接证明这 6 个就是每次运行都会自愈的产物，本就不该进库。

**踩坑记一笔**：`git -C <repo> worktree add ./clean` 的相对路径是相对 `-C` 切换后的目录（仓库根）解析的，不是相对调用时的 shell cwd——结果 worktree 落在了 `AE-Knowledge-Vault/clean`，一个 3488 文件的嵌套检出。已 `git worktree remove` 干净撤除，主仓库脏项未受影响（验证前后 `git status --porcelain -uall` 均为并行会话的 20 项）。**临时 worktree 一律传绝对路径。**

**`output/evidence/` 刻意不加白名单**（推翻上表 ①的默认倾向）：`.trae/rules/evidence-gate-rules.md` 已明确"检查目标是**文件系统**，不是 git 索引"，而证据闸门每跑一次就写入新文件——把该目录纳入跟踪等于重新打开刚闭合的测试污染通道。因此那 13 份历史证据维持跟踪现状不动，同时 `output/evidence/` 的 ignore 规则保留。

**自我纠错：上一段写的"这 13 份文件受 `git clean -Xdf` 威胁"是错的**。`git clean` 只删**未跟踪**文件，而 tracked-but-ignored 恰恰在索引里，所以 clean 会跳过它们。实测方法：`git clean -Xnd` 全量 dry-run（2186 个待删条目）与 `git ls-files -ci --exclude-standard`（15 项）做集合交集 → **交集 0**，15 项逐个判"安全"。真正的暴露面是同一目录下的**未跟踪且被忽略**文件：`git ls-files -o -i --exclude-standard` 数出 `output/evidence/` 下 **29 个 / 0.50 MB**（全是 2026-08-18 那批，含 `cloud_backup_20260818/logs/*.log` 等），这些不在任何 git 历史里，`git clean -Xdf` 一删就找不回来。结论：风险确实存在但对象和我原先写的不是一批文件，量级 0.5 MB 可接受；若要保守，先把该目录整体备份一次再跑 `git clean`。

## external/ 两个 gitlink 处置（2026-08-29）

`git ls-tree HEAD external/` 只有两条 mode 160000 记录，`git status` 里 `?? external/OpenMontage` 与 ` M external/OpenMontage` 交替出现（后者是嵌套仓库内部脏项的外溢）。逐个取证：

| gitlink | pin | 远端 | pin 性质 |
|---|---|---|---|
| `external/OpenMontage` | `c2045ad` | `github.com/calesthio/OpenMontage` | 公开提交，`branch -r --contains HEAD` 命中 `origin/main`，无本地私有提交 |
| `external/rife` | `a1ad751` | `github.com/hzwer/ECCV2022-RIFE` | **本项目私有提交**：作者 `AE Knowledge Vault <aekv@local.dev>`，2026-08-14，改 `inference_video.py` +18/−3，且该克隆是 **shallow**（`.git/shallow` 存在），`origin/main..HEAD` 恰好就是这一个提交 |

由此暴露出一个比"submodule 还是撤索引"更要紧的问题：**`external/rife` 里那枚音频迁移兜底修复只存在于这台机器的一个浅克隆内，公网拉不到、超级项目的 gitlink 也指向一个别人取不到的 sha**——换机器或误删目录即永久丢失。处置：

```
git -C external/rife format-patch -1 HEAD --stdout > docs/vendor/external-rife-audio-fallback-20260814.patch
```

2357 字节，并用 `git -C external/rife apply -R --check <该 patch>` 校验（exit 0）——即补丁内容与当前已应用状态逐字节等价，不是"大概备份了"。

**端到端可重现性验证**：在 `external/rife` 的独立临时 worktree 中检出上游基线 `5d8adbd`，直接跑文档里写的那条命令 `git am docs/vendor/external-rife-audio-fallback-20260814.patch` → `Applying: fix: 音频迁移失败…`，exit 0；还原出的 `inference_video.py` 与在用的那份**内容寻址三重等值**（2026-08-30 升级判据）：`git -C external/rife rev-parse HEAD:inference_video.py` = `rev-parse a1ad751:inference_video.py` = 工作树 `git hash-object inference_video.py` = `54d786908e5188657df81b394bb7fafb131df04e`，blob OID 相同即逐字节一致——比原先记录的截断 sha256 前缀 `4e2c54fe1423a505` 对比更强、且可机器复跑。临时 worktree 验毕已 `git worktree remove`，`external/rife` 回到单 worktree、HEAD `a1ad751`、脏项 0。

**顺带堵掉一个会让备份静默失效的配置**：本仓库 `core.autocrlf=true` 且原先没有 `.patch` 规则，补丁在 Windows 签出时会被转成 CRLF，`git am` 随即失败或打出错误行尾——即"备份在库里但换机器用不了"。已在 `.gitattributes` 追加 `*.patch text eol=lf`（`git check-attr` 确认 `text: set / eol: lf`，`git add --renormalize` 无差异，说明库内 blob 本就是 LF）。

**两个 gitlink 都撤索引，不补 `.gitmodules`**。理由是 `.gitignore:103` 的 `external/` 必须保留：该前缀下有 **9212 个未跟踪且被忽略**的文件，一旦取消忽略，`git status` 会永久脏几千行，刚闭合的"仓库干净"前提再次失效。而在一个被忽略的目录里挂 submodule 属对抗性配置，git 各版本行为不一致。故：

```
git rm --cached external/OpenMontage external/rife   # 仅动索引，磁盘两个克隆完好
```

重现方式（写在此处，不另建 README）：`git clone https://github.com/calesthio/OpenMontage.git external/OpenMontage`（对应 `c2045ad`）；`git clone https://github.com/hzwer/ECCV2022-RIFE.git external/rife` 后 `git am docs/vendor/external-rife-audio-fallback-20260814.patch` 复现那枚私有修复。

**净效果**：tracked-but-ignored **15 → 13**，剩余 13 项全部是有意保留的 `output/evidence/` 历史记录，`external/` 归零。

## 新增常驻闸门 scripts/audit_vendored_repos.py（2026-08-29）

把"vendored 克隆里的孤本"从一次性排查变成可重复机器判定，三类结论：

| 判定 | 条件 | 致命性 |
|---|---|---|
| 孤本 | HEAD 不被任何 `refs/remotes/*` 包含，且 `docs/vendor/` 下没有兜得住的受跟踪 `.patch` | FAIL，exit 1 |
| 断链 gitlink | 索引里是 mode 160000，但 pin 的 sha 无法从子仓库远端拉到 | FAIL，exit 1 |
| 未备份本地改动 | 子仓库对已跟踪文件有未提交 diff | WARN（不致命） |

补丁"兜得住"是实质核验而非看名字：索引用 `--error-unmatch` 确认受跟踪、工作树里存在、非空、且首行 `From <sha>` 与该仓库 HEAD 一致。

**闸门自身缺陷由反向验证暴露**：第一版只用 `git ls-files -- docs/vendor` 拿到名字列表做包含匹配——而 `ls-files` 读的是索引，不读工作树，所以我把补丁 `mv` 走后闸门仍输出 exit 0。这是"闸门从未对缺陷版实现失败"的教科书案例，修成实质核验后，三重反证各自以正确理由失败并指名：清空文件 → `候选补丁不可用 —— …: 文件为空`；删工作树文件 → `索引里有但工作树缺文件`；改成 `From 0000…` → `补丁记录的 sha 0000000 与该仓库 HEAD a1ad751 不符`。三次 `git checkout --` 还原后正向复跑 exit 0，补丁与还原前 `cmp` 一致。

**首跑即查出两类新事实**（28 个嵌套仓库，深度上限 3 层）：

- WARN ×4 —— 这四个 vendored 仓库里有**未提交的本地修改**：`OpenSpace`（2 文件：`examples/my-daily-monitor/server/index.ts`、`openspace/grounding/core/search_tools.py`）、`external/premiere-pro-mcp`（`src/bridge/uxp-websocket-bridge.ts`）、`external/BlenderProc`（`RendererUtility.py`）、`external/F-s-PluginsProjects`（72 文件，多为 `_DL_windowsbinary/*.zip`）。其中 `premiere-pro-mcp` 那处正是 AE 桥接链路相关，价值最高、也最容易被一次 `git checkout` 抹掉。
- 索引里其实有 **3 个** gitlink 而非 2 个：`OpenSpace`、`ae/gl-transitions`、`portfolio`，全都无 `.gitmodules`。三者的 pin 经验证都能从各自远端拉到（与 `external/rife` 不同），但 clean checkout 只会得到三个没有出处的空目录。

**两项待决**：① 上面 4 处未提交改动是否要 `git -C <子仓> diff > docs/vendor/<name>-local-edits.patch` 备份入库（可能属并行会话在做的实验，不擅自处理）；② 剩下 3 个 gitlink 是补 `.gitmodules`（三者 pin 均可公网拉取，技术上可行）还是照 `external/` 的做法撤索引。


## external/ 删除事故定损与工作树清点闸门（2026-08-30）

**事故定损（全部数字经磁盘重新清点、互相咬合）**：`external/` 下未跟踪且被忽略的内容遭到删除。现存 **72 个文件 / 8,024,036 字节**，此前记录为 **9,212 个文件**——约 9,140 个文件已不在磁盘。嵌套仓库从 `audit_vendored_repos.py` 首跑记录的 **28 个**降为 **1 个**（仅存 `external/rife`，HEAD 仍 `a1ad751`，其私有修复已有 `docs/vendor/` 补丁兜底）。三个仍挂 gitlink 的目录工作树被清空、只剩空壳：`OpenSpace`（pin `2c5cc40`）、`ae/gl-transitions`（pin `902218a`）、`portfolio`（pin `45cc0af`）——索引里 mode 160000 记录还在，指向的目录是空的。上面"两项待决"之①因此**无法从磁盘补做**：4 处未提交改动（含价值最高的 `premiere-pro-mcp` AE 桥接改动）已随仓库灭失，除非快照恢复成功。并行会话的一批未提交文件（`core/synthesis_orchestrator.py`、`core/temporal_analyzer.py`、`core/visual_scorer.py`、`scripts/m2_auto_iterate.py`、`requirements.txt`、`docs/handoff-2026-08-16-m2-tuner.md`、`项目全面扫描分析报告.html` 等）同样在磁盘上消失。

**损失口径纠错与一处撤回**：此前对外口径写的是"4 个 vendored 仓库受影响"，实测远大于此，正确口径是上面的 28→1。另撤回我自己清点日志 `gitlinks.log` 里的总量 1,375,327,448 字节：逐目录复核发现该枚举漏掉顶层文件与点目录，少计 3,957,378 字节，该总数作废，以 `find` 全量求和 **3,566 文件 / 1,379,289,942 字节**为准。

**为什么当时所有 git 完整性检查全绿**：`.gitignore:103` 的 `external/` 使其下全部内容对 `ls-files`、`ls-tree`、`status --porcelain`、`fsck`、bundle、LFS 对象备份统统不可见——删除发生时 `git status` 只有 1–2 行、vendored 闸门报致命 0 / 警告 0，是"真绿"也是"真丢"。教训：**"status 干净"≠"工作树完好"**，被忽略文件的存在性只能由文件系统清点证明。

**新增常驻闸门 `scripts/verify_worktree_inventory.sh`（提交 `b0f17c0`）**：以基线清单对磁盘做存在性清点。基线 `manifest.txt`（3,566 行 `<字节>\t<路径>`，不含 `.git`，sha256 `e78224406b2d944b58c7d5ab316d0cb382d36798d522528ea9882d07d219fdfc`，存于库外 `Desktop/ae-kv-inventory-20260830/`；该目录在 2026-08-31 桌面归档整理中被特意留在原位、未迁入 `Desktop/AE-KV-Audit-20260830/`——闸门脚本的默认基线路径 `BASE_DEFAULT` 硬编码指向 `manifest.txt`，移走就会静默破坏默认调用（仅 `AE_KV_INV_BASE` 可覆盖））；compare 模式输出 `MISSING`/`ADDED`/`SIZE_CHANGED`，基线内文件缺失即 exit 1。反向验证 **PASS=24 FAIL=0**（8 类拒止 + 6 类损失检测，全部在合成仓库与脚本内 dry-run 完成，未触碰真实数据）。闸门自身两个缺陷在反向验证中暴露并修复：① `refuse()` 的告警写 stdout 会被 `$( )` 命令替换吞掉，必须写 stderr 并以 `REFUSING:` 前缀作判定信号；② 路径归一化须折叠 MSYS/Windows 形式、拒绝 `..`、在大小写不敏感文件系统上做大小写折叠的包含判断。标签 `kv-gates-20260830` 只盖到 `d24129c`，不含本闸门。

**清点过程踩的两个坑**：① `core.quotePath=true`（默认）对非 ASCII 路径做八进制转义，`git ls-files` 与 `find` 对比凭空多出 890 个假差异；加 `-c core.quotePath=false` 后真实差集是 79 个未跟踪且被忽略文件，索引独有项恰为上述 3 个 gitlink。**本库任何路径对比必须关 quotePath**。② 索引项与磁盘文件不在同一计数域：gitlink 计入索引，`find -type f` 看不见目录。

**当前状态（提交 `b0f17c0` 后实测）**：工作树 3,566 文件 / 1,379,289,942 字节，与基线、与新跑 `find` 求和三向全等；受跟踪文件 3,491；嵌套 `.git` 仅 2 个（`./.git`、`./external/rife/.git`）；`git fsck` 干净。本地 heads：`master`（`b0f17c0`）、`feat/phase1.1-gateway-consolidation`（`4b8aa81`）、`feat/project-consolidation-v1`（`9b956eb`）；`remotes/origin/master → 446cddc` 已落后，`remotes/origin/feat/*` 与本地 heads 镜像。注意：本地克隆产生的 `refs/remotes/*` 只是克隆时点的镜像，不能当作上游血缘证据。

**仍可能的恢复途径**：① 提权终端跑 `vssadmin list shadows` / File History 查询（本会话权限不足，未成）；② 并行会话被毁的未提交文件可从其会话转录 `6b126afc-6153-4248-9c64-94a1a246555c.jsonl` 重建。库外锚点（`01-备份-bundles/ae-kv-allrefs-20260829.bundle`、`01-备份-bundles/ae-kv-backup-20260816.bundle`、`01-备份-bundles/ae-kv-lfs-backup-20260829/`、`02-快照-snapshots/ae-kv-restore-drill/`）**均不含 `external/` 内容**。`03-测试副本-testcopies/ae-kv-amtest-20260829/`（HEAD `029320085cbec82d25bbab1b56ce4f439ad6633c`）与 `ae-kv-amtest-20260830/`（HEAD `ce7d7397646be963001f80efc9d10bbf94e39f89`）合起来是 rife 的 git 历史仅存副本：2026-08-31 实测两者体积与文件数完全相同但 HEAD 不同，交叉 `git cat-file -t` 均失败，即各持对方没有的提交，共同祖先才是索引记录的 gitlink OID `a1ad751a1849bfe851f8c53dd4b4115a2c0ec7e2`。**两份都不得再作为任何破坏性试验的目标，也不得"删掉重复的那份"。**


## 三个 gitlink 撤索引：证据落档（2026-08-30，撤索引前写入并提交）

**为何先落档再撤**：这 3 个完整 OID 在本地只以 mode-160000 索引项形式存在；`git rm --cached` 本身不写任何文档。先让本证据块随 TASK_STATUS.md 提交入库，撤索引后 OID 仍有两个永久来源：本节与所有撤索引前提交的历史树（`git ls-tree -r <撤索引前的任意提交>`）。顺序不可颠倒。

**精确完整 OID（2026-08-30 `git ls-files -s` 实时读取，未截断）**：

| 路径 | OID | 磁盘状态 |
|---|---|---|
| `OpenSpace` | `2c5cc409b0c14364bc5fce268cd24eaa215c2d92` | 目录全空，无 `.git` |
| `ae/gl-transitions` | `902218a1b63773ac0d0d9f491951da3392365bfe` | 目录全空，无 `.git` |
| `portfolio` | `45cc0af6a6c2054b853fde3096586924b5874bf6` | 目录全空，无 `.git` |

三个目录经 `find <dir> -mindepth 1` 清点均为 0 条目（mtime 2026-08-30 08:20）——克隆本体是本次事故牺牲品，其 `.git/config` 里的远端 URL 随之灭失。

**远端 URL 穷尽搜索（负面结果，六类独立来源全部查空）**：

1. `.gitmodules` 在全部历史中从未存在：`git log --all --oneline -- .gitmodules` 为空；`git show 46ca744:.gitmodules` 报 `fatal: path '.gitmodules' does not exist`（exit 128）。
2. 历史树全量扫描：对 `git rev-list --all` 的每个提交跑 `git ls-tree -r`，全部历史中出现过的 mode-160000 条目只有不变的 5 个（上表 3 个 + 已在 HEAD 撤索引的 `external/rife` `a1ad751a1849bfe851f8c53dd4b4115a2c0ec7e2`、`external/OpenMontage` `c2045ad5f0c952a3d110965abbb874da121f4050`），全是裸 OID，无任何附带出处元数据。
3. 唯一会话转录 `6b126afc-6153-4248-9c64-94a1a246555c.jsonl` 对 `remote.origin.url`、`git clone` 等探针的定串检索，对这 3 个仓库无可用命中（命中均为 `external/rife` 恢复操作或本会话自身追加文本的自指）。
4. 早期探针存档 `Desktop/AE-KV-Audit-20260830/02-快照-snapshots/ae-kv-restored-20260830/gitlink-remote-probe.txt`（29 个唯一 URL）全部属 OpenMontage/RIFE。
5. 受跟踪文档中仅有 `deploy-portfolio-github.bat` 的占位模板（`GITHUB_USERNAME=你的GitHub用户名`），无实际远端。
6. 本项目仅一份会话转录，无第二归档。

**结论**：三个远端 URL 在本地不可恢复。唯一出处记录是此前审计时的验证结论：三者 pin 均可从各自 `origin/main` 拉到、克隆私有提交为 0（其中 `OpenSpace` 克隆曾有 2 处未提交本地改动，即上文 WARN ×4 中的 2 文件，已随克隆灭失）。因此本次损失的独有内容为零，丢失的只是三个远端身份本身。

**决定**：撤索引，与 `external/` 两个 gitlink 的处理同理——无 `.gitmodules` 的裸 gitlink 在 clean checkout 只会产出三个无出处空目录，而索引继续指向磁盘上已不存在的克隆没有意义。恢复方式：将来若想起远端地址，凭上表 OID 用 `git ls-remote <url>` 核对包含关系后即可重建克隆。

**可复跑验证**（撤索引后执行，结果应逐条吻合）：

```
git ls-files -s | grep 160000                # 无输出：索引不再有任何 gitlink
git ls-tree -r dd1ac63 | grep 160000         # 三个完整 OID 仍在历史树中可查
bash scripts/verify_worktree_inventory.sh    # RESULT: PASS 且 missing=0（撤索引不动磁盘）
```

**执行记录（2026-08-30 当日完成，撤索引提交 634a455）**：

- 撤索引提交：`634a455`，暂存区差异精确等于三条 mode-160000 删除（`OpenSpace` `2c5cc40…`、`ae/gl-transitions` `902218a…`、`portfolio` `45cc0af…`），无任何其他条目混入。
- 验证 A：`git ls-files -s | grep 160000` 无输出（grep exit 1）——索引中 gitlink 清零。
- 验证 B：`git ls-tree -r dd1ac63 | grep 160000` 返回三个完整 OID，与上表逐字吻合——证据在撤索引后仍可从历史树取回。
- 验证 C：`git status --porcelain` 仅剩 `?? .workbuddy/automations/`（并行会话目录，未触碰）；`git log --oneline -3` 为 `634a455 → 6c3ad6b → dd1ac63`。
- 验证 D：HEAD 树条目 3,488 = dd1ac63 的 3,491 − 3，差值恰为三条 gitlink，无多余变动。
- 磁盘完整性闸门：`bash scripts/verify_worktree_inventory.sh` 复跑 `RESULT: PASS`、`GATE_EXIT=0`、`missing=0`。其中 `added=6` 全部为并行会话运行期产物（`bridges/.media_encoder-mcp-bridge/mcp_server.log`、`bridges/__pycache__/adobe_universal_bridge.cpython-312.pyc`、`bridges/__pycache__/adobe_mcp_manager.cpython-312.pyc`、`bridges/.premiere-mcp-bridge/mcp_server.log`、`bridges/.photoshop-mcp-bridge/mcp_server.log` 等 6 项），属新增而非丢失；`size_changed=1` 为本文件自身（文档追加），均符合预期。

至此三个 gitlink 撤索引闭环：索引已清、证据双份留存（本节 + 撤索引前全部提交的树）、工作树经闸门验证零丢失。


## 项目全面扫描分析报告.html 恢复调查（2026-08-30，穷尽式负面结果）

并行会话的未提交文件 `项目全面扫描分析报告.html` 在 external/ 删除事故中灭失。对该文件内容执行穷尽式恢复调查，覆盖全部 5 条可用本地通道，结果全部为负面。

### 五条恢复通道与结果

| # | 通道 | 方法 | 结果 |
|---|------|------|------|
| 1 | Write/Edit tool_use 重放 | 流式解析会话转录 `6b126afc-…555c.jsonl`（4,993→5,050 行），重放所有 file_path 匹配目标文件的 Write（覆盖 state）与 Edit（`state.replace(old, new, 1)`） | **0 次 Write、0 次 Edit** |
| 2 | Bash heredoc/重定向创建 | 同上扫描中检查 Bash tool_use 的 command 字段是否含目标文件名 | 3 次命中，全部为存在性探测（`for f in ...项目全面扫描分析报告.html; do if [ -f "$f"`）与 git 历史查询（`git log --all --oneline -- 项目全面扫描分析报告.html`），无创建操作 |
| 3 | 悬空 blob | `git fsck --dangling --no-reflogs` 查找曾被 `git add` 但从未被任何提交引用的 blob | **0 个悬空 blob**——该文件从未进入过索引 |
| 4 | stash | `git stash list` | **空**——无任何 stash 记录 |
| 5 | 全转录 .html Write 分类 | 一行不落地扫描全部 5,050 行，提取所有 Write tool_use 且 file_path 以 `.html` 结尾的操作（覆盖"写到不同文件名再 mv"的模式） | **HTML_WRITES=0**——整个转录中没有任何 .html 文件的 Write 操作 |

### 补充证据

- 该文件在转录中最早出现于第 2,451 行（2026-08-29T12:59:02.754Z），身份为 `git status` tool_result 中的 `?? 项目全面扫描分析报告.html`——即**始终为未跟踪状态**，从未被 `git add`、从未进入任何提交。
- 52 次关键词命中全部分类为：tool_result（目录列表显示文件名）、text（助手/用户消息中的丢失报告）、Bash（存在性探测与 git 历史查询）。无任何创建或写入操作。
- `FULL_PROJECT_SCAN_ANALYSIS.md`（5,863 字节）在 HEAD 树、工作树、快照中各存一份，三份完全一致——扫描分析报告的 Markdown 版本完好无损。

### 结论

`项目全面扫描分析报告.html` 的 HTML 渲染内容**在任何可用本地来源中均不可恢复**。该文件是并行会话在工作树中直接生成的未跟踪产物，从未进入 git 索引、从未被任何工具写入会话转录、未被 stash 捕获。Markdown  twin `FULL_PROJECT_SCAN_ANALYSIS.md` 是扫描报告内容的唯一权威存留副本。

~~唯一剩余恢复可能性为用户侧操作：提权终端执行 `vssadmin list shadows` 查询卷影副本，或检查 File History / 回收站。~~ → 已于 2026-08-31 全部执行完毕，结果见下方补记：**三条通道全为负面，恢复调查正式闭环，无任何剩余通道**。

### 补记（2026-08-31）：OS 级恢复通道（卷影副本 / 回收站 / 文件历史）穷尽核查——全部负面

前文的五条通道均属 git/会话转录层。2026-08-31 按用户指示对操作系统层的三条剩余通道逐一执行核查，结果全部为负面：

| # | 通道 | 方法 | 结果 |
|---|------|------|------|
| 6 | VSS 卷影副本 | 提权运行 `vssadmin list shadows` 与 `vssadmin list shadowstorage`（普通权限被拒后以 UAC 提权子进程写文件回读） | **"找不到满足查询的项目"×2**——本机不存在任何卷影副本，也没有任何卷配置了卷影存储关联 |
| 7 | 回收站 | Shell.Application COM 枚举回收站全部项目并按文件名匹配 | **4,935 项全量枚举，0 命中**——目标文件不在回收站（与"删除走 shell 命令、绕过回收站"的推断一致） |
| 8 | 文件历史（File History） | 检查本地目录 `%LOCALAPPDATA%\Microsoft\Windows\FileHistory` 与注册表 `HKCU\...\FileHistory` | 本地目录**不存在**；注册表键下仅有空的 RestoreUI 子键、无任何配置值——文件历史**从未启用** |

**最终结论（2026-08-31 起生效，八通道全负面）**：`项目全面扫描分析报告.html` 的 HTML 渲染内容在本机一切来源中均确认不可恢复——既不在 git 层（索引/提交/悬空 blob/stash/转录），也不在 OS 层（卷影副本/回收站/文件历史）。该文件的报告内容以 Markdown twin `FULL_PROJECT_SCAN_ANALYSIS.md`（5,863 字节，HEAD/工作树/快照三份一致）为唯一权威存留。若日后可视化呈现有需要，可从该 Markdown 重新渲染生成 HTML，不再追索原文件。


## 桌面审计产物归档整理（2026-08-31）

用户反馈桌面散落大量审计产物，要求整理。整理对象是本仓库审计过程产生在**库外**的 `ae-kv-*` 临时产物，不涉及任何被跟踪文件。

**做法与零丢失保证**：全部产物集中移入 `C:\Users\Administrator\Desktop\AE-KV-Audit-20260830\`，按性质分四个带序号的子目录。移动一律用同盘符 `mv`（等于重命名，不产生第二份副本、不删任何字节），移动前后文件数与字节数一致；桌面 `ae-kv-*` 条目从 **33 个降为 2 个**（归档文件夹 + 刻意留下的基线文件夹）。

**实测清点（2026-08-31 复核，与归档内 README 表格逐字吻合）**：

| 目录 | 文件数 | 字节数 | 删除判据 |
|---|---|---|---|
| `01-备份-bundles/` | 12 | 805,190,569 | 不可删——唯一的离线 git 历史与 LFS 副本 |
| `02-快照-snapshots/` | 7,040 | 544,360,150 | 不可删——含事故后唯一恢复证据源 |
| `03-测试副本-testcopies/` | 173 | 16,084,025 | 不可删——两份 RIFE 副本持有不同提交 |
| `04-证据日志-logs/` | 24 | 30,549 | 可删——纯文本日志，价值最低，但仅 30 KB |
| 合计 | **7,249** | **1,365,665,293** | 不含归档根 `README.md` 自身 |

**闸门基线刻意未动**：`Desktop/ae-kv-inventory-20260830/`（15 文件 / 181,990 字节，含 `manifest.txt` 166,779 字节与 14 个 08-30 探针日志）留在桌面原位未归档——`verify_worktree_inventory.sh` 的 `BASE_DEFAULT` 硬编码指向该 `manifest.txt`，移走会静默破坏闸门默认调用。整理后重算 sha256 为 `e78224406b2d944b58c7d5ab316d0cb382d36798d522528ea9882d07d219fdfc`，与本文先前记录一致，基线未损坏。

**两处自查抓到的文档缺陷（已修）**：① 归档根 `README.md` 会被自己的清点命令计数，造成"文档一改数字就失效"——改为只排除顶层 `./README.md`，并给出可复跑的复核命令块。② 复核命令初版写成 `find . -type f ! -name README.md`，实测返回 7,225 文件 / 1,365,565,495 字节，与文档标的 7,249 / 1,365,665,293 不符；逐一列出所有 `README.md` 后发现**归档内部还有 24 个来自被存档仓库的同名 README**，`-name` 把它们一起误排了。改成路径锚定的 `! -path ./README.md` 后命令恰好复现文档数字。教训：**排除"我自己"必须用路径锚定，不能用文件名匹配**——同名文件在被存档的树里很常见。

**一处事实纠正**：本文此前把 `03-测试副本-testcopies/ae-kv-amtest-20260829/` 描述为 rife 的 git 历史"仅存副本"，暗示另一份是冗余。实测两份 `ae-kv-amtest-*` 各有 76 文件 / 8,021,755 字节但 HEAD 不同（`02932008…` 与 `ce7d7397…`），交叉 `git cat-file -t` 双向失败，共同祖先才是 gitlink OID `a1ad751a1849bfe851f8c53dd4b4115a2c0ec7e2`——**两份合起来才是仅存副本，任何一份都不是可删的冗余**。该结论已同步写进归档 README 与本文"仍可能的恢复途径"段。


## 2026-08-26 里程碑

- ✅ **topaz 运行期错误修复**：`TopazEngine` 对齐新 `BaseEngine` 模板方法契约（实现 `_execute_impl` + `_run_subprocess` 4 元组解包），`test_topaz_engine.py` 4 errors→5 passed。
- ✅ **引擎契约批量对齐**：继承 `BaseEngine` 的 12 个引擎（+topaz 共 13）全部实现 `_execute_impl`，`_run_subprocess` 4 元组解包统一；独立引擎 comfyui/flux3 误改已回滚。21 引擎类抽象方法清零、可实例化。
- ✅ **证据闸门合规自检工具链交付**：`scripts/evidence_gate_compliance_audit.py`（五闸门机器化 + GB/T 47507-2026《人工智能 可信赖 通则》/ GB/T 45652-2025 条款映射），16/16 测试通过；运镜 4 元类标签集真实审计五闸全过（`reports/compliance_camera4/`），数字与 2026-08-24 人工核验一致。详见 `00-每日记录/2026-08-26_证据闸门合规工具链与材料核实-开发进度.md`
- ✅ **运镜去噪重标注实验完成（负结果，证据链闭合）**：专家去噪标签重训 2 类 CNN（与基线完全同协议），best bal_acc=0.6525 < 基线 0.6725；2 类 0.67 定性修正为**帧差特征的任务信号上限**而非标签噪声天花板；分层混合架构交付决策不变，运镜方向无剩余未做实验。详见 `00-每日记录/2026-08-26_证据闸门合规工具链与材料核实-开发进度.md` §三
