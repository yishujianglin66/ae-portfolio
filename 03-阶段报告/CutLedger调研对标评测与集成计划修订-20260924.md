# CutLedger·SkillsHub 调研对标评测与集成计划修订

*生成时间：2026-09-24 ｜ 依据：网站全站归档（`tmp/grok_site/`，14 文件）+ 本地主线测试走查 + `tmp/integration_plan_20260919.md`*

---

## 一、网站调研深度分析报告（阶段一）

### 1.1 网站概况

该站名为 **「CutLedger · SkillsHub」**（AE、Blender、达芬奇剪辑自动化台账，调研日期 2026-09-23），本质是对 **skillshub.wtf / TerminalSkills/skills**（约 1000 条 agent 技能）全库检索后，筛选出 **26 条剪辑自动化直接相关技能** 做成的结构化台账。站点为四标签 SPA：

| 标签 | 内容 |
|------|------|
| 台账 | 26 技能卡片（分类：After Effects 2 / Blender 8 / 达芬奇 1 / 代码剪辑 3 / VFX-DCC 3 / AI 视频 3 / 音频字幕 5 / 采集投递 1） |
| 产线 | 五条"把技能焊成真实制作"的管线及断点标注 |
| 缺口 | 六条结构性缺口分析 |
| 站外对照 | 登记册相邻项 + 站外更强的同名项目 |

### 1.2 核心发现清单

1. **总论断**：SkillsHub 把「剪辑」写成了代码流水线——桌面 NLE 只有薄薄两张卡片（AE 一条、达芬奇一条），且都是"API 说明书"而非剪辑工作流；**真正深的是 Blender 八件套与无头 FFmpeg**。
2. **统计基线**：26 直接关联技能 / Blender 垂直件 8 / AE·达芬奇各 1 / Premiere·FCP·Nuke 为 **0**。站内搜索命中数：Blender(14) > AE(12) ≈ 剪辑/Resolve(11) > DaVinci(1) > montage(0)。
3. **成熟度分层**（卡片自带标注体系，值得借鉴）：每条技能标 `核心 / 可用 / 相邻` 三级 + `可无头 / 需 GUI` + 技术栈标签。26 条中"核心"仅 8 条（after-effects、davinci-resolve、blender-vse-pipeline、blender-scripting、blender-render-automation、ffmpeg、moviepy、whisper、yt-dlp）。
4. **五条产线及断点**：
   - ①社媒短视频工厂（yt-dlp→Whisper→TTS→MoviePy→FFmpeg）：**完全无头，登记册里唯一焊死的链路**；
   - ②Motion 模板工厂（ExtendScript 换素材→aerender/MOGRT→Lottie）：SkillsHub 对 AE 的真实定位=批量包装，不是剪片子；
   - ③CG 预演到成片（bpy 建场→EXR→合成或 Resolve 调色）：缺 ACES，Resolve 必须开 GUI；
   - ④无头时间线（镜头表→Blender VSE→FFmpeg 封装）：登记册唯一能无头"剪"的 DCC，对白精剪不够；
   - ⑤生成再包装（T2V/I2V→AE/Resolve）：**生成层与 NLE 层在登记册是断开的，要自己焊**。
5. **六大结构缺口**：无 Premiere/FCP/Nuke/Maya/C4D；达芬奇不能无头（脚本只能连运行中实例，渲染农场/CI 出片不可能）；无词级粗剪（Whisper 出 SRT 但没人接自动粗剪）；无 ACES/OCIO/OTIO（3D→成片最容易脏的一跳）；AE 停在 ExtendScript 说明书（无工程读取、无 undo 约定）；Blender 无 Geometry Nodes/完整绑定（每张卡 200 行级速查）。
6. **站外更强的"手"**（登记册未收录但同类工作应优先考虑）：
   - `aedev-tools / adobe-agent-skills`：可读工程、生成并执行 ExtendScript、34 内置脚本——"登记册是地图，这个是手"；
   - `arjun988/blender-skills（94 技能包）`：blender-director 路由 + **MCP 直接驱动 Blender**，远细于八件套；
   - `Forward Future · Alex 达芬奇四技能`：对话清理→粗剪→交叉淡化→画面，是真正的"剪辑"技能；
   - **DaVinci Resolve MCP：Studio 21.1 起有官方 MCP**，免费版需桥——登记册完全没写；
   - `kajisho5/ffmpeg-skill`：42 个带契约的工具（切/拼/响度/多机位/交付检查），比登记册 ffmpeg 卡更像剪辑器。

### 1.3 技术亮点与可借鉴点

| 亮点 | 说明 | 对本项目的转化 |
|------|------|----------------|
| 三维技能标注法 | 成熟度（核心/可用/相邻）× 无头能力（可无头/需GUI）× 技术栈标签 | 直接采纳为本项目 Skill schema 的必填元数据 |
| "产线+断点"叙事 | 不按工具分类，按真实制作流程焊接并显式标断点 | 本项目 `pipeline/` 文档改用"断点显式化"写法 |
| 缺口页的自我否定 | 明确"覆盖面决定了你能自动化什么" | 避免本项目 SkillHub 只堆数量不标盲区 |
| 地图 vs 手的区分 | 说明书型技能与可执行工具型技能分开评级 | 本项目 JSX/引擎适配属"手"，知识卡属"地图"，分类管理 |
| 客户端过滤搜索 | 26 条卡片上直接做子串搜索（搜技能、API、限制） | 轻量检索即可上线，不必先建数据库 |

### 1.4 与本项目（AE-Knowledge-Vault）的差距分析

> 注意方向是双向的：该台账覆盖的是**公开技能生态**，本项目是**私有深度集成**。

**本项目已领先之处**（台账做不到、我们已有）：
- AE 真实执行链：文件轮询 Bridge + listener + JSX 注入 + `executeAtomScript` 原子操作 + mtime 竞态修复（台账的 AE 卡只是 ExtendScript 说明书）；
- Resolve 自动化引擎：`resolve_engine.py`（fuscript+Lua、CDL 调色、SetProperty 变速、混合渲染）已端到端验证——超出台账那张"需 GUI Python"卡的能力；
- 节拍体系：VRS 真实节拍检测、10.7ms 切点吸附、防累积漂移、onset 驱动运镜、rhythm_reward 95.3%——台账完全没有"剪辑语义"层；
- 3D 桥接：BlenderProc + headless bpy 5.1 实测可用 + `blender_ae_bridge.py`；
- 学习闭环：VRS→知识库→风格模板→执行的感知-决策-执行闭环、自进化评测——台账的 AI 视频卡（MoneyPrinterTurbo 思路）远不及。

**本项目落后/缺失之处**（台账有、我们无或弱）：
- **技能形态标准化**：我们 600+ 脚本没有统一的 Skill 封装（schema、元数据、版本、CLI、可分发），台账虽是说明书但有清晰的技能单元结构；
- **OTIO/ACES 时间线互换**：无覆盖（台账列为结构性缺口，恰是行业空白→差异化机会）；
- **词级粗剪**：我们有 Whisper 类适配（auto_subs_adapter）但未接"按词自动切时间线"；
- **官方 DaVinci Resolve MCP（Studio 21.1+）**：我们停留在 fuscript/Lua 桥，未评估官方 MCP 面；
- **对外生态**：台账站外对照里 aedev-tools/blender-skills 等社区"手"类资产，我们未系统性吸收消费。

### 1.5 潜在风险与机会

**风险**：
1. 沙箱站点为一次性预览（本次访问原 URL 已"Port not found"，靠浏览器缓存抢救归档）——凡依赖外部沙箱/临时 URL 的调研结论必须**当场落盘归档**（本次已做，`tmp/grok_site/`）；
2. 台账"AE 自动化=批量包装非剪辑"的定位若被照搬，会把本项目带偏到模板工厂方向——我们的差异化恰恰是"用 agent 剪片子"（节拍语义+叙事弧线），**不能丢**；
3. 站外项目（arjun988/blender-skills、kajisho5/ffmpeg-skill 等）成熟度未经我们独立验证，引入前需走 skill 评测流程（防"700+ 技能"式数量泡沫）。

**机会（按价值排序）**：
1. **差异化空位确认**：全生态"专业 NLE 深度剪辑自动化"大面积空白（Premiere/FCP=0，Resolve 不能无头，montage 检索=0），本项目的 VRS+叙事+节拍体系正好卡位；
2. **官方 Resolve MCP**：升级 Studio 21.1 可直接获得官方 agent 面，替代自维护 Lua 桥的一大半成本（需先验证 SetProperty/CDL 在新 API 的等价性）；
3. **技能生态消费**：把台账 26 条 + 站外 5 组"手"类资产作为我们 Skill 库的**外部包源**，用统一 schema 收编；
4. **无头能力矩阵**：借鉴"可无头/需GUI"标注，为本项目 9 引擎建能力矩阵，直接指导编排器降级路由（如 Resolve 不可用时走 FFmpeg——已有此模式，缺显式声明）。

---

## 二、专业评测与差距矩阵（阶段二）

评测基线：`tmp/integration_plan_20260919.md` 三阶段路线图 × CutLedger 台账 × 本次实测证据。

### 2.1 六维评测

| 维度 | 本项目现状（实测） | SkillsHub 台账基线 | 评分（10 制） |
|------|--------------------|--------------------|----------------|
| **Bridge/MCP 层成熟度** | 34 个 MCP 工具注册，HTTP 联调 10/10 通过；统一 bridge base + 自愈测试；但发现并修复了 401 认证回归（SecretStr 比较缺陷），/api/v1 测试无 token 惯例 | 无 Bridge 层（纯说明书），MCP 直接性被点名"官方 21.1 才有" | 本 8 / 台账 2 |
| **Skill 生态覆盖度** | 脚本 600+ 但无标准 Skill 封装；`skill_loader.py`（OpenMontage 集成）已有雏形；缺 CLI/分发/市场 | 26 条统一卡片 + 客户端搜索 + 三级成熟度标注 | 本 5 / 台账 7 |
| **AE 深度集成能力** | JSX 真执行链、undo 保护、listener 命令集、aerender、粒子/文字主脚本、MOGRT 工具；真实闭环本次因 AE 未运行未验证 | 1 张 ExtendScript 说明书卡；站外 aedev-tools（34 脚本）才是"手" | 本 9 / 台账 2（站外 5） |
| **节拍检测与运镜标注精度** | VRS 真实音频 3/3 通过（bpm 143.6/120.2/69.8），beat/vrs 全组测试绿；10.7ms 吸附、防漂移、onset 运镜已沉淀 | 零覆盖（montage 检索 0 命中） | 本 9 / 台账 0 |
| **成本模型合理性** | 本地化推理（librosa/VLM 4bit 5.82GB 已部署），边际成本≈电费；但无 per-task 成本计量表 | 台账无成本维度；对照基线 OpenMontage $0.02/条 | 本 6 / 台账 3 |
| **社区可扩展性** | 私有 vault，无对外分发面；知识归档极强（260+15+88+库）但不可被他人"安装" | 生态位天然可分发（skillshub.wtf 全库检索） | 本 3 / 台账 8 |

**总判断**：项目在"深度"（AE/节拍/闭环）上全面压制公开生态，在"形态"（Skill 标准化、可分发、成本计量）上落后于公开生态。原计划（integration_plan_20260919）把"700+ Skill 库数量"当目标有数量泡沫风险，应改为 **"统一 schema + 外部生态收编 + 深度能力技能化"**。

### 2.2 差距矩阵（台账/站外资产 → 本项目模块映射）

| # | 外部资产 | 类型 | 对应本项目模块 | 差距 | 吸收动作 |
|---|----------|------|----------------|------|----------|
| 1 | after-effects 卡（说明书） | 地图 | `bridges/ae_bridge_base.py` + listener | 我们反超 | 仅作 schema 参考 |
| 2 | aedev-tools / adobe-agent-skills | 手 | `ae_additive_scripts/`、`core/fx/` | 工程读取面可互鉴 | 调研其 34 脚本清单，补缺项 |
| 3 | davinci-resolve 卡 | 地图 | `integrations/resolve_engine.py` | 我们已超 | 核对官方 MCP 差异 |
| 4 | **DaVinci Resolve 官方 MCP（Studio 21.1）** | 手 | `davinci_fuscript.py`（Lua 桥） | 我们停 21.0.3 自研桥 | **P0 评估升级** |
| 5 | Forward Future 达芬奇四技能 | 手 | `vrs/video_reproduce_pipeline.py` | 词级粗剪缺失 | 补"Whisper 词时间码→Resolve EDL 切" |
| 6 | arjun988/blender-skills（94）+ MCP | 手 | `integrations/blender_proc_adapter.py`、`bridges/blender_ae_bridge.py` | Geometry Nodes/完整绑定薄 | 收编为外部 Blender 包 |
| 7 | kajisho5/ffmpeg-skill（42 契约工具） | 手 | `scripts/` 各 ffmpeg 封装、`ffmpeg` MCP 4 工具 | 契约化/交付检查缺 | 引入"工具契约"写法 |
| 8 | ACES/OCIO/OTIO | 空白 | 无 | 全行业空白 | **P1 差异化：OTIO 时间线互换层** |
| 9 | MoviePy 程序化剪辑 | 手 | `integrations/moviepy_renderer.py`（已有） | 已覆盖 | 无 |
| 10 | Remotion 代码出片 | 手 | 无 | 缺 Web 模板态出片 | P2 评估（与文字动画系统互补） |
| 11 | Lottie/Bodymovin 交付端 | 手 | 无 | AE→Web 动效交付断 | P2（若做作品集页面则提级） |
| 12 | Whisper/yt-dlp/comfyui/elevenlabs | 手 | `auto_subs_adapter`、`13-素材获取与搜索`、`comfyui_mcp_server` 等 | 基本已覆盖 | 统一收编进 Skill 清单 |

### 2.3 修订后的集成计划（P0/P1/P2）

**P0（立即，1-2 周）——修地基 + 摘官方红利**
1. ✅ *本次已完成*：MCP Gateway 401 认证回归修复（`mcp_gateway/gateway.py` SecretStr 解包，13/13 测试转绿）；
2. ✅ *本次已完成*：`vrs/__init__` 导入链断裂修复（`video_reproduce_pipeline.py` 路径+包导入、`effects/effect_reproducer.py` 相对导入，65 项回归绿）；
3. **puppet-automation 测试基线补齐**：conftest 统一注入 `PUPPET_DISABLE_AUTH=1`（dev）或 Bearer token，消除 /api/v1 存量 24 个 401 失败；
4. **blenderproc 环境对齐**：安装进 `.venv`（当前在系统 Python312，环境漂移）；`transition_rebuilder` 的 `kb_loader` 缺失补 shim；
5. **Resolve Studio 21.1 官方 MCP 评估**：升级测试→验证 SetProperty/CDL/渲染队列 API 等价性→决定 Lua 桥的去留策略（保留为降级路径）；
6. **AE 真执行链例行验证脚本化**：将"启动 AE→listener→ping→listCompositions→渲染→回收"做成一键 smoke（本次因 AE 未运行无法闭环，须能在需要时 10 分钟内出结论）。

**P1（3-4 周）——技能化 + 差异化**
7. **Skill schema v0.1**（采纳台账三维标注：`核心/可用/相邻` × `可无头/需GUI` × 技术栈），将 Top 50 高频脚本封装为 Skill 单元 + `mcc skill list/add/test` CLI；
8. **词级粗剪链路**：Whisper 词时间码 → 静音/语气词检测 → 自动生成 Resolve EDL / VSE 切点（对应缺口③，站外 Alex 四技能思路落地）；
9. **无头能力矩阵进编排器**：9 引擎声明 `headless_capable`，`pipeline_orchestrator` 按矩阵自动降级路由（Resolve GUI 不可用→FFmpeg，已有实例化此模式，缺显式声明）；
10. **成本计量表**：`cost_tracker.py`（已有 OpenMontage 集成雏形）接本地推理计时/显存占用，产出 $/条 实测报表，替换计划文档中的拍脑袋 $0.01。

**P2（5-8 周）——生态与空白卡位**
11. **OTIO 时间线互换层**（行业空白）：Resolve timeline ↔ AE ↔ Blender VSE 经 OTIO 互导，做成差异化卖点；
12. **外部技能包收编**：arjun988/blender-skills、kajisho5/ffmpeg-skill 经评测后注册进本项目 Skill 库（含来源/成熟度/许可证三元记录）；
13. **社区分发面 MVP**：技能清单只读导出（静态 HTML，参考 CutLedger 四标签形态），先"可看"后"可装"；
14. Remotion / Lottie 交付端评估。

**降级/取消**（对原 integration_plan_20260919 的修订）：
- "100+ Skill 数量目标" → 取消指标化，改为 Top 50 高质量封装（数量目标即泡沫）；
- "GitHub Star ≥10,000 (Week 6)" → 不切实际，删除；
- "adobe-mcp 全面替代现有 Bridge" → 改为"保留自研 Bridge 为主（已验证领先），adobe-mcp 作为对照参考"；
- 原 Phase 2.2 AE 2026 新特性清单 → 保留，但优先级让位于官方 Resolve MCP（P0-5）。

---

## 三、集成测试与主线功能走查结果（阶段三）

### 3.1 测试执行日志摘要

| # | 主线 | 验证方式 | 结果 | 证据文件 |
|---|------|----------|------|----------|
| 1 | MCP Gateway 通信链路 | 启动 `_start_api.py` → `scripts/mcp_integration_test.py` | **10/10 通过**；34 工具注册（ae2/blender3/comfyui3/config2/davinci2/ffmpeg4/media3/plugin4/resource8/silhouette2/topaz1） | `tmp/mcp_gateway_test_20260924.log` |
| 2 | AE Bridge 命令下发→JSX→回传闭环 | 进程检查 + bridge 目录状态 | ⚠️ **环境前置未满足**：AE 未运行、无 `ae_result.json`、listener 日志止于 09-20（`Unknown command: runScript`，后由 executeAtomScript 方案绕过）；单元层 `test_ae_bridge_base` 等全绿 | 走查命令输出 |
| 3 | VRS 节拍分析 | 真实音频 3 条过 `analyze_audio_features` | **3/3 通过**：bpm=143.6/120.2/69.8，beats=19/1/158，librosa 降级路径工作正常 | `tmp/vrs_beat_check.py` |
| 4 | 节拍/编排/学习闭环/文字特效/风格/Blender/Resolve 单元与集成层 | pytest 28 文件主线批次 | **431 项全部通过，0 失败**（40.5s） | `tmp/pytest_mainline_20260924.log` |
| 5 | Blender 无头 bpy 真执行 | `blender.exe -b -P`（5.1.0 Alpha，建文本对象） | **通过**：`BPY_OK version= 5.1.0 Alpha`（一条无害 rigify  addon 警告） | 走查命令输出 |
| 6 | BlenderProc 适配器 | `check_available()` | ❌ `.venv` 内 `blenderproc` 不可导入（记忆中装在系统 Python312/external，环境漂移） | 走查命令输出 |
| 7 | Resolve 真实渲染 | 进程检查 | ⚠️ 环境前置未满足：Resolve 未运行（与台账"达芬奇不能无头"结论一致）；discovery/engine 单测全绿 | 走查命令输出 |
| 8 | puppet-automation API 测试面 | `tests/test_api.py` | 修复前 MCP 组 **11 failed(401)** → 修复后 **13/13 passed**；全量 24 failed 为 /api/v1 存量缺 token 问题（修复前即失败，非本次引入） | pytest 输出 |
| 9 | Skill 生命周期 | 代码定位 | 部分存在：`puppet-automation/src/integrations/openmontage/skill_loader.py`（含 list_skills）；无统一 Skill schema/CLI → 对应 P1-7 | 检索结果 |
| 10 | 站点调研通道 | browser-use MCP → 夸克缓存 + ComputerUse 归档 | 原 URL 已下线；**内容经浏览器缓存完整抢救**（14 文件，台账/产线/缺口/站外 + 9 组搜索） | `tmp/grok_site/` |

### 3.2 失败项根因分析

| 失败项 | 根因 | 级别 | 处置 |
|--------|------|------|------|
| MCP 端点全量 401 | `_validate_token` 将 `settings.mcp_auth_token`（SecretStr）与 str 直接比较，恒不相等；`main.py` 有解包函数但 gateway 未复用 | **代码回归（P0）** | ✅ 已修复并验证（解包 + 注释锚定两实现一致；13/13 绿；联调 10/10 绿） |
| `import vrs.*` 必炸 | `video_reproduce_pipeline.py` 的 `_PROJECT_ROOT = parent`（少一层）+ 三个目录迁移遗留的扁平导入（模块实际位于 style/effects/transition 包） | **代码缺陷（P0）** | ✅ 已修复并验证（65 项 vrs/bridge 回归绿 + 真实音频 3/3） |
| `effects.effect_reproducer` 导入失败 | 同族扁平导入遗留（`from effect_registry import`） | 同上 | ✅ 已改相对导入 |
| /api/v1 存量 24 failed | 测试未携带认证头且 dev 空 token 策略拒绝匿名访问（`_check_mcp_auth_token` 的 `if token and ...` 使空 token 无法命中弱 token 分支） | 测试基建缺口（P0-3） | 计划：conftest 统一 fixture；或明确匿名访问语义 |
| blenderproc 不可用 | 安装落在系统 Python312（记忆时点），`.venv` 环境不含 → 文档/记忆与实际环境漂移 | 环境（P0-4） | 计划：`.venv` 内 `pip install -e external/BlenderProc` |
| `transition_rebuilder` kb_loader 缺失 | 扁平导入遗留（非致命分支，已静默降级） | 低 | 与 P0-2 同批清理 |
| AE/Resolve 真执行链不可验证 | 应用未运行（文件轮询桥的固有前置） | 环境前置 | P0-6：一键 smoke 脚本 |

### 3.3 修复验证计划（对已改代码）

1. ✅ gateway 修复后：`tests/test_api.py -k MCP` 11→0 失败；HTTP 联调 10/10；
2. ✅ vrs/effects 修复后：主线 28 文件回归 431 通过 + 真实音频分析 3/3；
3. ⏳ 待办：`ruff` 全量扫改动文件；提交前跑 `tests/` 全量（后台空闲时段）；
4. ⏳ 验证环境恢复（AE/Resolve 启动）后补跑：Bridge ping→listCompositions→渲染回传 smoke；Resolve 渲染队列 smoke；届时把结果追加到本报告。

---

---

## 五、实战跑通记录（2026-09-24 下午追加）

> 目标：把主线系统真实跑通一条成片。前置：用户重装 Resolve 后升级到 **21.1.0.14**，携带官方 MCP（ResolveMCP.exe）。

### 5.1 P0 落地情况

| P0 项 | 状态 |
|---|---|
| P0-3 测试 token 基建 | ✅ conftest 注入 `PUPPET_DISABLE_AUTH=1` + `RESOLVE_SCRIPT_LIB`；补装 `aiosqlite`/`celery` 两缺失依赖；`tests/test_api.py` 从 **24 失败 → 全绿** |
| P0-4 blenderproc | ✅ 结案：`external/BlenderProc` 实测已不存在（非环境漂移而是资产已移除），已修正记忆；Blender 能力走 headless bpy（实测可用） |
| P0-5 官方 Resolve MCP | ✅ 评估+接入完成：新建 `engines/davinci/official_mcp.py` 客户端；Gateway 新增 `davinci_run_script`/`davinci_mcp_status`/`davinci_mcp_call`（透传官方 14 工具） |
| P0-6 AE 真执行链 smoke | ✅ 完成：启动 AE 2025 + 手动注入 listener 后全链路真实跑通——ping 0s/listCompositions ✓/建合成+2层 ✓/渲染 6s 出片（h264 640x360 3.0s，ffprobe 验证），新烟测脚本 `tmp/ae_smoke_0924.py`；发现并归档 4 个新坑至 docs/ae_bridge_lessons.md 第 10 节（eval 型 listener 拒 return 前缀/Start 目录多版本冲突/rq.render 正确 API/om.file 后缀漂移） |

### 5.2 实战链路（全部真实执行）

```
VRS 节拍分析(bpm=143.6, 50 beats, librosa_direct)
 → resolve_engine.beat_sync_edit(3 素材×BGM → beat_mix.mp4, 7MB, 15s 出片)
 → MCP Gateway HTTP(8765) → davinci_mcp_call → 官方 launch_resolve
 → davinci_run_script → 建工程/ImportMedia/时间线/AddRenderJob → StartRendering
 → 轮询 status=Complete pct=100 → 输出校验（ffprobe h264 1080p 20.4s）
 → CDL 调色走 Lua 桥 apply_cdl(True) + render_timeline("H.264 Master")
 → graded_master.mp4（11MB, SATAVG 3.94→6.81，调色量证明生效）= GRADING_PASS
```

产物：`tmp/e2e_0924/{beat_mix.mp4, e2e_graded.mov, graded_master.mp4}`；日志：`tmp/e2e_v4.log`、`tmp/e2e_grading2.log`；脚本：`tmp/e2e_full_system_v2.py`、`tmp/e2e_grading_lua.py`。

### 5.3 实战撞到的坑（已全部修复并沉淀记忆）

1. **User 级环境变量劫持**：`RESOLVE_SCRIPT_LIB` 残留指向旧路径 `D:\DaVinci Resolve\...`，`setdefault` 不覆盖 → 全量 initialize 失败。双修：客户端强制覆盖 + 修正系统变量（已写入 common_pitfalls）；
2. **官方 run_script 沙箱硬约束**：禁 import os/json、timeout max 60s、`OpenPage` 在 resolve 不在 project → 渲染长任务拆成多次调用；
3. **CDL 在 Python API 不可用**（SetCDL 返回 falsy）→ 确认双桥分工：MCP 做编排/查询，调色渲染走已验证 Lua 桥——正好符合台账“达芬奇自动化各有断点”的判断，我们是两条都通；
4. **重名工程残留**：崩一次后 CreateProject 失败 → 唯一时间戳工程名；
5. **apply_cdl Lua 1-based 索引**：首片段传 1 不是 0。

### 5.4 对评测结论的更新

六维评测中“Bridge/MCP 层成熟度 8 分”修正为 **9 分**：项目现已同时持有 自研 Lua 桥（调色/渲染深水区）与 官方 MCP 桥（14 工具含 API 文档检索/LUT 生成）双通道，且经真实成片验证。原计划 P1-9“无头能力矩阵”新增现成事实：Resolve 侧官方 `get_resolve_status` 可直接供编排器做存活路由。

---

## 六、总体结论

1. 调研站本身（CutLedger）的最大价值不是告诉我们"有什么"，而是**证明了公开生态在"专业 NLE 深度剪辑自动化"上的大面积空白**——本项目的节拍/叙事/AE 真执行链正是空白区，应放弃数量型 Skill 目标，改走"深度能力技能化 + 空白卡位（OTIO/词级粗剪/官方 MCP 红利）"。
2. 阶段三实测显示主线功能**单元与集成层全绿（431 + 10/10 + 3/3 + Blender 真执行）**，但走查揪出并当场修复了 2 类 3 处真实回归（MCP 认证、导入链），验证了"测试走查先行"的必要性。
3. 遗留风险集中在**环境前置层**（AE/Resolve 未运行、blenderproc 环境漂移、测试 token 基建）——已全部排入 P0。

**晚间补充（2026-09-24）**：P0 全部落地后，① listener 协议分叉已在 `ae_mcp_auto_listener.jsx::executeScript` 层统一（双兑底，PROTO_CHECK 双风格实测 PASS，客户端零改动）；② 达芬奇 4 个测试工程（KV_E2E_*/KV_LUA_*）已经官方 MCP 定点删除（因 API 不能删当前工程的限制，留有空工程 `__cleanup_holder__` 可直接手动删）；③ 发现新问题：系统盘/缓存盘空间告警（网关 resource_monitor disk=93.7%，AE 启动也弹磁盘缓存警告），建议列入待办清理。

*SkillHub 26 技能逐项整合清单见：`03-阶段报告/SkillHub生态整合清单报告-20260924.md`*

---

## 七、P1-1 落地记录：Skill schema v0.1 + Top50 封装（2026-09-25）

针对六维对标唯一落后项（Skill 标准化 5 vs 7）的翻身仗，已完成：

### 产物清单
| 产物 | 位置 | 说明 |
|---|---|---|
| 元 schema | `schemas/skill_card_schema_v0.1.json` | Draft-07；三类 skill_type（effect_recipe / tool_wrapper / pipeline_step）；**headless 无头矩阵 + cost 成本计量并入字段**（P1 并行两项提前闭环） |
| CLI | `scripts/skill_cli.py` | validate / gen-tool-cards / build-registry / list / show |
| 卡片库 | `schemas/skill_cards/<domain>/*.yaml` | **64 张**：37 tool_wrapper（AST 自 gateway 提取，一工具一卡）+ 19 effect_recipe（自 RECIPES）+ 8 pipeline_step（09-24 实战链附实测证据） |
| 索引 | `schemas/skill_cards/registry.json` | 含 by_stage/headless/cost/domain 四维统计 |
| 守门测试 | `tests/test_skill_schema.py` | 六条不变式，**70 passed/1.4s** |

### 关键设计决策
1. **治理闸门写进 schema**：`stage:active` 条件约束 `evidence_chain.status=real_execution`，自动生成的卡诚实停在 experimental/validated，防"假晋升"；active 当前 9 张（bloom + 8 条实战链）。
2. **无头能力矩阵即 registry 统计**：headless 25 / requires_running_host 39 / requires_gui 0；成本 gpu_local 仅 4 项（ComfyUI/Topaz/Blender anim/Silhouette）——编排器可直接消费 registry.json 做调度预判。
3. **定义外置按名引用**（Nuke gizmo 式）：recipe_ref 指向实现位置，卡片不拷贝代码；checksum 留 v0.1 可选。
4. 粒度按 9-11 方案「效果类型×功能域」17 域，不按管线阶段。

### 小坎
- 早前正则数出"43 工具"实为嵌套 `name` 字段误计；AST 提取为准 = 37 真工具（含 1 占位 tool_name 已排除）。教训：工具清单统计用 AST 不用正则。

### 遗留（P1 后续）
- 词级粗剪链路（Whisper→EDL）未动；文本动画 60 预设成卡（第二批）；卡片 checksum 实钉；网关消费 registry（skill_list/skill_invoke 工具）待 P1-4。
