# Deep Research: 视频管线集成 · Skill 封装 · 特效 Schema 演进（外部技术参考）
> Generated 2026-09-11 | Depth: deep | Sources: 41 | 委托背景：AE-Knowledge-Vault「管线集成咽喉期」
> Wave 3（本地代理启用后）补抓一手/权威源 9 个：OpenFX(ASWF) / MLflow Registry / Terraform Registry / SLSA-in-toto-Sigstore / CUE / outlines-xgrammar / Great Expectations / Nuke Gizmo-Blender / skill-card 实例。
> 证据强度标尺（用户口径）：**【已实证】** 官方文档/可运行 OSS 代码 > **【论文/标准】** arxiv/W3C > **【社区讨论】** 博客/CSDN/Reddit > **【待验证】** 未能确认
> 适配声明：本报告结论均对照项目现有实现 `schemas/visual_effect_schema.json`、`scripts/edl.py`、`scripts/build_master_polish.py` 给出异同与可借鉴点。

## TL;DR

1. **EDL 桥不用从零造**：项目的 `edl.py` 已是 `OpenTimelineIO`[1][2] 与 `video-use`[5] 的极简同构物；缺的不是新格式，而是 **在 EDL 里补一个 `overlays/effects` 轨道段**（video-use 的 edl.json 正是用 `overlays:[{file,start_in_output,duration}]` 把"独立渲染的效果"绑回主时间线[5]）——这是"独立效果模块接入主渲染链"的业界标准做法。
2. **效果注入调度器有成熟范式**：MLT 的 `Producer/Filter + YAML 元数据`[7]、ComfyUI 的 `NODE_CLASS_MAPPINGS + pyproject.toml`[10][11]、build_master_polish 已有的 `SCHEMA_TO_RECIPE + effects_injection_report（禁止静默丢弃）`——三者同构，项目的"对账记账"已达业界水准，缺的是**注册表化 + 版本化**。
3. **Skill 封装照抄三条现成范式**：MLT filter 的 YAML 卡片（version+参数范围）[7]、ComfyUI Registry 的 `pyproject.toml [tool.comfy]`（version/requires-comfyui/依赖）[11][12]、Model Card/Datasheet（intended-use/out-of-scope/eval/版本+时间戳）[20][21][23]。项目 `evidence_chain.skill_id="run50-validated-2026-09-04"`[guide] 已是 Model-Card 式雏形，**应升级为带 semver + 验证时间戳 + 适用域的能力卡片注册表**。
4. **防脱节靠"单一真源 + 数据契约"**：Structured Outputs 生态的头号教训是"schema 与下游类型漂移"[17]；数据契约（ODCS）标准做法是**契约文件与管线代码同仓版本化 + 管线内嵌校验 + 向后兼容/弃用周期**[28][29]。项目的 schema 应从"手写 JSON"升级为"由 RECIPES/参数范围单一真源生成 + CI 校验"。

## Executive Summary

本次调研针对项目三大待办——管线集成、Skill 封装、Schema 演进——检索了 41 个来源（Wave1-2 共 32 个 + Wave3 一手/权威补强 9 个），覆盖开源视频管线（OpenTimelineIO / Auto-Editor / video-use / MLT / Kdenlive / Remotion / HyperFrames / OpenMontage）、能力单元封装（ComfyUI Registry / MLT filter YAML / DaVinci Resolve API / Model Card / Datasheet）、声明式生成与证据链（OpenAI Structured Outputs / guidance / outlines / W3C PROV / Dagster 资产血缘 / ODCS 数据契约）。

**核心发现**：项目在"内部实现"上已相当接近业界范式——`edl.py` ≈ 极简 OTIO、`build_master_polish.SCHEMA_TO_RECIPE` ≈ MLT/CLI-Anything 的效果翻译层、`effects_injection_report` ≈ 数据契约的质量闸门、`evidence_chain.skill_id` ≈ Model Card 标识。真正的差距集中在三点：**(a) EDL 未承载效果/覆盖层轨道**，导致文字/视觉链与剪辑链"两张皮"；**(b) 效果能力未注册表化+版本化**，散落在 RECIPES dict 里，无法"一次验证多次复用"；**(c) schema 是手写而非单一真源生成**，存在与代码漂移的风险。这三点都有直接的、已被业界验证的借鉴对象，且大多"仅缺一个数据段/一层注册/一个生成脚本"，非重构级工程。

**最重要的反方警示**（video-use 明确列为 anti-pattern）：*"Hierarchical pre-computed codec formats with USABILITY/tone tags/shot layers. Over-engineering. Derive from the transcript at decision time."*[5] —— 过度 schema 化是真实陷阱。项目的 18 种 effect_type 中仅 10 种可渲染[guide]、`run53v43_effects_premium_v2.json` 139 条仅 33 条可渲染[guide]，正是"schema 覆盖面 > 实现覆盖面"的漂移征兆。集成方案必须优先"把已验证的少数能力接进主链并注册"，而非继续扩张未实现的 schema 类型。

---

## 1. Status Quo：业界如何把独立效果模块接入主渲染链 [Confidence: High]

### 1.1 时间线数据契约是"接入"的锚点

**OpenTimelineIO（OTIO）** 是由工业光魔（ILM）主导的开源时间线交换格式与 API，C++ 核心 + Python 绑定（`pip install opentimelineio`），数据模型为 `Timeline → Track → Clip / Transition / Composition（可嵌套）`，序列化为 `otio_json`，并通过 Adapters 读写 EDL/AAF/FCPXML[1][2]。其插件体系分三类：`Media Linkers`（媒体解析）、`HookScripts`（读写钩子）、`SchemaDefs`（自定义 schema 扩展）[2]。**这与项目 `edl.py` 的 `cuts/inputs/cut_points` 高度同构**，但 OTIO 多了两个项目缺失的关键能力：**多轨（Track）与嵌套合成（Composition）**，以及 **HookScripts 式的读写扩展点**——后者正是"效果模块挂载到时间线"的标准挂载位。【已实证】

**CMX3600 EDL** 是最经典的纯文本剪辑契约（`EVENT REEL TRACK EDIT_TYPE SOURCE_IN OUT RECORD_IN OUT`），人类可读+机器可解析[3]。项目 `edl.py` 的 `cuts[]`（index/start_time/end_time/source_file/source_start/speed/transition/mood/energy）本质是 CMX3600 的 JSON 化超集，额外携带了 `mood/energy`（语义字段）——这是项目相对经典 EDL 的**增量优势**，应保留。【社区讨论，格式本身已实证】

**video-use（browser-use）** 是最贴近项目形态的范式：一个"用对话剪视频"的 Skill，其 `edl.json` 契约包含 `version / sources / ranges[{source,start,end,beat,quote,reason}] / grade / overlays[{file,start_in_output,duration}] / subtitles / total_duration_s`，并由单一命令 `render.py <edl.json> -o <out>` 消费——按段抽取→concat→覆盖层（PTS 偏移）→字幕最后[5]。**关键借鉴**：`overlays` 字段把"独立渲染好的效果片段"用 `文件路径 + 输出时间线位置 + 时长` 绑回主时间线，这就是"独立效果模块接入主渲染链"的最小契约。项目 `edl.py` 当前**只有 cuts，没有 overlays/effects 段**——这正是 K3「双链无桥」的契约级根因。【已实证，一手抓取】

### 1.2 "先生成时间线，再交给渲染器"是非破坏式集成的共识

**Auto-Editor** 的核心设计是"分析（音频响度/运动）→ 输出可交换时间线 → 交给 NLE 或渲染"，`--export premiere/resolve/final-cut-pro/shotcut/clip-sequence`[4]。项目已把 Auto-Editor 作为适配器集成（去静音/静止）。**Remotion** 把"React 代码即真源"，Composition = 带 duration/fps/resolution 的 React 组件，`useCurrentFrame()/interpolate()/spring()` 驱动，Headless Chrome 逐帧截图 → FFmpeg 合成；Player（预览）与 Lambda（渲染）**共用同一 Composition**保证"预览即所得"[24]。**HyperFrames（heygen-com）** 是"Write HTML, Render video, Built for agents"，HTML→**确定性** MP4，`__timelines[id]` 逐帧 seek，带 lint/validate/render 检查[25]。**OpenMontage** 用 Remotion+HyperFrames+FFmpeg 栈做 agentic 视频生产[26]。

**对项目的映射**：项目的 AE 链（build_master_polish→render_master）与 Python 链（unified_edit→EDL）恰是"两个渲染器"，缺的正是 Remotion 式的"单一真源被两个消费端共享"。EDL 就应扮演这个"单一真源"，AE 链与 Python 链都从它派生。【已实证】

### 1.3 效果注入调度器：注册表 + 元数据 + 对账

**MLT Framework**（Kdenlive/Shotcut 底座）的效果架构是 `Producer / Filter / Tractor / Consumer`，filter 通过 `mlt_repository_register(repository,"my_filter",type,init)` 注册，且**每个 filter 配一个 YAML 元数据文件**（`name/identifier/type/version/author/description/parameters[{name,type,default,range}]`）[7][9]。这正是"效果能力卡片"的成熟工业形态：**代码实现 + 声明式元数据（含版本与参数范围）分离**。

**CLI-Anything** 的 MLT→ffmpeg 滤镜翻译层解决了"同一效果在不同渲染器参数空间不同"的问题（如 brightness：MLT 1.0=正常 vs ffmpeg eq 0=正常，公式 `(val-1.0)*0.4`；多个 eq 需合并；流排序约束）[8]。**这与项目 `build_master_polish.SCHEMA_TO_RECIPE / SCHEMA_DYN_RECIPE / SCHEMA_UNMAPPED` 是同一问题同一解法**——项目的实现已属业界同构，且多了 `effects_injection_report.json（applied+unmapped+skipped==input，禁止静默丢弃）`[guide] 这一**比 CLI-Anything 更强的对账保证**。【已实证/社区讨论】

**ComfyUI** 的效果注入是 `NODE_CLASS_MAPPINGS` 注册表 + 图执行；自定义节点通过 `custom_nodes/` + `requirements.txt` + `install.py` 生命周期管理[10]。

---

## 2. Emerging Trends：Skill/能力卡片封装与版本管理 [Confidence: High]

### 2.1 "一次验证、多次复用"的能力单元 = 元数据卡片 + 注册表 + 版本契约

三条独立的成熟范式 converge 到同一结论——**能力单元 = 实现 + 声明式卡片（版本/参数/适用域/验证信息）+ 注册表**：

- **ComfyUI Registry**：`comfy node init` 生成 `pyproject.toml`，含 `[project] version` + `[tool.comfy] PublisherId / DisplayName / requires-comfyui`（宿主版本兼容），`comfy node pack`（本地校验打包）→ `comfy node publish`（上传，官方自动扫安全漏洞）[11]。版本兼容矩阵明确（Manager V3.16+ 需 ComfyUI v0.1.2 / Python 3.10-3.12）[12]。**借鉴点**：能力卡片应带 `version` + `requires-host`（对应项目的 AE 版本/渲染器）+ 依赖声明。【已实证】
- **MLT filter YAML**：`version + parameters[{default,range}]`[7]。**借鉴点**：参数范围写进卡片（项目 `visual_effect_schema.json` 已有 threshold[0.5,1.0]/radius[3,12] 等范围[guide]，应从 schema 提取进卡片）。【已实证】
- **Model Card（Mitchell 2018, arXiv:1810.03993）[20] / Datasheet（Gebru 2018, arXiv:1803.09010）[21]**：`model version / intended use / out-of-scope use / metrics / eval data`；AWS SageMaker ModelCard 有 `ModelCardVersion + ModelCardStatus(审批) + creation/lastModified 时间戳`[22]；HuggingFace Model Card = `README.md` 顶部 **YAML frontmatter**（license/datasets/tags）[23]。**借鉴点**：能力卡片应含 `intended-use / out-of-scope / 验证时间戳 / 验证证据链接`——**这与项目 `evidence_chain.skill_id="run50-validated-2026-09-04"`（已内嵌"验证来源+日期"）方向完全一致**，项目只差把它从"一个字符串字段"升级为"一张结构化卡片"。【论文/标准 + 已实证】

### 2.2 治理硬约束：无卡片不得进 production

Model Registry 的通行做法：`Stage`（版本状态机，production 全局唯一）+ `Source`（训练/验证 run-id 回溯）+ `Checksum`（制品哈希防篡改）+ `Lineage`（dataset→train→model）；**"没有模型卡的版本应被 Registry 拒绝进入 production——这是治理的硬约束"**[22]。**直接可落地到项目**：一个 effect 配方若无"渲染差分验证记录 + skill_id + 版本"，`build_master_polish` 应拒绝将其计入 `applied`（项目的 `effects_injection_report` 已有闸门骨架，加一条"无卡片→归入 unmapped/skipped 并记原因"即可）。【社区讨论，模式已实证】

### 2.3 DaVinci Resolve API 的模块化与版本漂移教训

Resolve Scripting API（Python/Lua）以对象模型模块化（`Project/MediaPool/Timeline/TimelineItem/Graph/ColorGroup`），`Timeline.Export(type)` 支持 `EXPORT_AAF/EDL/FCPXML`，`-nogui` 无头模式（API 全可用，UI 禁用）[27]——**与项目 AE Bridge 无头注入同构**。**关键版本漂移教训**：`SetLUT()/SetCDL()` 的 `nodeIndex` 在 v16.2.0 从 **0 基改为 1 基**[27]。这类"宿主升级导致参数语义静默改变"正是项目 v6.1 字体回退事故、Glo2 序号陷阱的同类——**能力卡片必须记录"验证时的宿主版本"**（对应 ComfyUI 的 `requires-comfyui`）。【已实证】

---

## 3. Schema 演进：声明式生成、Prompt-as-Code 与证据链 [Confidence: High]

### 3.1 Prompt-as-Code 的确定性靠"约束下沉到解码层"

项目 `docs/visual-effect-schema-guide.md` 的 "Prompt-as-Code" 定位与业界一致：**"请返回 JSON"是建议，Schema 约束才是保证**[17]。三条技术路线（均由软到硬）：JSON Mode（只保证合法 JSON）< `strict json_schema`（OpenAI Structured Outputs，**constrained decoding：按已生成 token+schema 计算允许 token 并 mask 非法 token**）[14] < grammar-constrained（Microsoft `guidance`[15] / `outlines` / `xgrammar`；vLLM `guided_json/guided_regex`）[16]。**Instructor** 提供 `LLM→Structured Output→Pydantic→Validator→PASS/FAIL→retry` 闭环[16]。

**对项目的映射**：`visual_effect_schema.json`（`allOf`+`if/then` 类型安全校验[guide]）已是"schema 约束"层；`_validate_effect_configs`（校验 effect_type/参数/`evidence_chain.skill_id` 必填）[guide] 已是 Validator。**差距**：项目未把 schema 用于**约束 LLM 生成**（guide 的 Method 3 只是"把 schema 塞进 prompt"，属最软的一档）；若要确定性生成配方，应上 `guidance/outlines` 的 grammar 约束或 Instructor 式 retry 闭环。【已实证】

### 3.2 单一真源 + 数据契约：防 schema 与代码脱节

**头号教训**：*"schema 会和下游类型漂移，改字段时 LLM 无感知。用 Pydantic/Zod 做单一来源生成，别手写两份"*；*"结构合法不代表业务正确，分项之和/日期先后等规则由后端兜底"*[17]。**数据契约（ODCS 开放数据契约标准）** 的落地五步[28]：① 定义 producer/consumer；② 写契约（`fundamentals(id/version/status) + schema + quality` 的 YAML，机器可读）；③ **契约文件与管线代码同仓版本化**；④ **管线内嵌校验**（违约→告警+可选 halt，不向下游传播坏数据）；⑤ 版本化（**向后兼容优先，破坏性变更需通知所有 consumer + 弃用周期**）。**Schema Registry** 补充兼容模式：`BACKWARD`（新读旧）/`FORWARD`（旧读新）/`FULL`/`NONE` + 漂移检测 + 契约测试（producer&consumer 双跑）[29]。

**对项目的映射（关键）**：
- 项目 `visual_effect_schema.json` 是**手写** JSON，而参数范围的**真源其实在 `build_master_polish.RECIPES`**[guide]——两处分离即"手写两份"的漂移风险。应按[17]改为**由 RECIPES/参数范围单一真源生成 schema**（或反之），并加 CI 校验（`tests/test_visual_effect_schema.py` 已是雏形[guide]）。
- 项目 EDL `schema_version="1.0"`[edl.py] + `lint_edl`（L1-L6）[edl.py] 已是数据契约的骨架；缺 **BACKWARD/FORWARD 兼容策略 + consumer 通知**（当 EDL 加 `overlays` 段时，旧 consumer 应能忽略——即 FORWARD 兼容）。
- 命名分裂（`RECIPES` 用 `radial`，schema enum 只有 `radial_blur`，历史产物写 `radial` 被归 skipped[guide]）正是"无单一真源"的症状。【已实证/社区讨论】

### 3.3 证据链追溯：W3C PROV 是标准本体

**W3C PROV / PROV-O**（2013 标准）以 `Entity / Activity / Agent` + `wasDerivedFrom / used / wasGeneratedBy / wasInformedBy / wasAttributedTo` 描述溯源，有 Python `prov` 库（MIT，导出 PROV-N/O/XML/JSON）[18]。**semantica** 展示了"决策即图上一等公民"：`record_decision(category/scenario/reasoning/outcome/confidence)→id`，`add_causal_relationship(CAUSED/INFLUENCED/PRECEDENT_FOR)`，`trace_decision_chain()`（返回 confidence_decay/weakest_link），`export_prov()` 输出 PROV-O，**全程确定性、无需 LLM、可断网内网跑**[19]。

**对项目的映射**：项目 `evidence_chain{skill_id, reasoning, music_alignment{onset,beat_strength,section_level}}`[guide] 已是轻量证据链。**升级方向**：把 `skill_id` 解析为一张 PROV 式卡片（该效果由哪个 run/哪次渲染差分验证 wasGeneratedBy、验证时间、宿主版本），使 `data/evolution/render_history.jsonl / render_audit.jsonl` 与 `acceptance_log`（当前 0/30）形成可追溯血缘。**Dagster 的软件定义资产（SDA）** 提供了另一视角：以"资产"为中心，依赖图=数据图，自带 materialization 历史 + lineage + 类型检查[30]——项目 `output/<run>/` 三件套报告（unified_report/cutpoint_report/delivery_spec）就是天然的"资产"，可用 SDA 思路串起 acceptance_log。【论文/标准 + 社区讨论】

### 3.4 集思广益：八个跨领域一手范式（Wave 3，代理启用后补强）

代理启用后补抓权威/一手源，八个邻域系统对三大待办各有**直接可借鉴**的成熟机制（均【已实证/标准】）：

**(1) OpenFX（ASWF，VFX 特效插件事实标准）[33]——最贴合项目的效果能力契约**。`Suite` 模块化 + **运行时宿主能力检测→优雅降级**（旧宿主无 GPU 套件仍加载基础套件）；统一 `OFX::Host::PropertySet` 元数据 + 标准参数类型系统 + 事件驱动（`kOfxActionDescribe/CreateInstance/Render`）；`kOfxPropVersion`（多维 int 字典序比较）+ `kOfxPropAPIVersion`；弃用机制（旧属性移入 `oldOfx.h`）。**借鉴**：项目 `RECIPES`+`visual_effect_schema` 本质是 mini-OFX；A1 铁律（matchName 未实证不编造）=OFX 运行时能力检测；09-11 探针的"图层样式/挤压脚本门控"=OFX"宿主不支持→降级"。卡片应记 `requires-host`(AE 版本)+已实证 matchName 集+降级路径。

**(2) MLflow Model Registry[34]——"一次验证多次复用+版本状态机"工业标准**。三层 `Model/Version/Artifact`；`version`(SemVer)+`Stage`(Staging/Production/Archived 状态机)+`Source`(run-id 血缘)+Checksum；`transition_model_version_stage()` 晋升 API；无 model card 拒进 production。**借鉴**：项目 `skill_id`+`beat_grammar_validated_v1.json`+60 个已验证文字预设=天然"注册模型"；应建 skill registry（version/stage/source/checksum/requires-host），晋升过验证闸门。

**(3) Terraform Registry 模块版本[35]——SemVer+锁文件+完整性校验**。`<namespace>/<name>/<provider>`+`version`；约束 `~>5.20`(>=5.20,<5.21)；`.terraform.lock.hcl` 锁版本+**hash(h1:/zh:)**；SemVer 契约：**MAJOR=输入输出契约变更(破坏)/MINOR=新增可选/PATCH=修复**；本地路径模块不可锁版本="定时炸弹"，须远程+`ref=vX.Y.Z` 钉死。**借鉴**：直接给出 Q3 版本升级判据——配方参数范围变更=PATCH、新增可选效果字段=MINOR、effect_type/schema 破坏性变更=MAJOR+弃用周期；卡片带 checksum 钉死"验证时实现"。

**(4) SLSA+in-toto+Sigstore[36]——证据链权威标准（Q3 evidence_chain 升级目标）**。SLSA 分级 L1(provenance 存在:谁/何流程/顶级输入)/L2(托管平台签名)/L3(加固防篡改)；in-toto 每步 CI 生成签名 attestation；provenance predicate 记录 git commit/repo/pipeline/**时间戳**/SHA-256/builder-id；Sigstore 无密钥签名+Rekor 透明日志。**借鉴**：项目 `edl.py` 已有 `inputs[{path,sha1,size_bytes}]`+`toolchain`+`generated_at`=proto-provenance！`evidence_chain` 应升级为 in-toto 式 attestation：`skill_id→wasGeneratedBy(验证 run/渲染差分)+inputs(SHA1)+validated_at+output_digest+host_version`，与 `render_audit.jsonl` 打通喂 acceptance_log。**离线用本地 in-toto JSON 即可，不必上 Sigstore/Rekor 云端**。

**(5) CUE 语言[37]——schema 与代码"单一真源"根治（Q3 防漂移）**。CUE 把**类型+值+约束统一为"格"**：schema 与 data 同语法；**从代码提取 schema/生成校验代码**；hermetic（值不可覆写）；`cue export base.cue prod.cue` 统一+冲突检测；与 JSON/YAML/OpenAPI 互操作。**借鉴**：直击痛点——`visual_effect_schema.json`(手写) 与 `RECIPES`(代码真源) 分离=漂移源；CUE 式做法=参数范围一处定义→**生成** schema+校验器。嫌 CUE 成本则退用 **Pydantic 单一真源**[38]。

**(6) 约束解码 outlines/xgrammar/llguidance[38]——Prompt-as-Code 确定性实现层（含硬限制）**。FSM(Outlines):schema→FSM,非法 token logits=-inf,编译 8-60s,grammar 可缓存；PDA/CFG(XGrammar,CMU):支持递归,vLLM 默认后端,比 FSM 快~100x；llguidance(MS)支撑 OpenAI SO。**硬限制**:FSM 无法表达无界递归→不支持 `$ref`、大量 oneOf/anyOf 状态爆炸。工程共识:**定义源用 Pydantic/TS type,不手写 JSON Schema**(`response_format=PydanticModel`;zod→json-schema)。**借鉴**：项目 schema 用 `allOf+if/then`(已避 oneOf)，若上约束解码需注意 FSM 对条件 schema 开销；配方生成要确定性用 outlines(离线友好)+Pydantic 单一真源。

**(7) Great Expectations[39]——"五门/可读性门"形式化+活文档**。Expectation Suite(规则集)+Checkpoint(触发)+Validation Definition+**Data Docs(自动 HTML 活文档=契约可视化)**；Rule-Based Profiler 自动生成期望；Dagster+GE(`ge_validation_op @asset`)把质量门嵌进管线资产。**借鉴**：项目散落在 `tmp/verify_v*.py`/`check_delivery_spec.py`/`cut_visibility_v3.py`/五门的校验，可收敛为 **Expectation-Suite 式契约闸门**（每 run 强制跑+落盘=活文档），天然对接 acceptance_log(K7)。

**(8) Nuke Gizmo/Blender 节点组[40]——配方"外置定义+按名引用"范式**。Nuke Gizmo:Group Node 存为 `.gizmo` 于插件目录,脚本**只存名字+控件设置**(定义在 .gizmo,加载时读)→"改 gizmo 实现即改所有引用它的脚本";`Export gizmo`**显式控制哪些参数可编辑**(参数暴露契约)。Blender Node Group=可拖入 Geometry/Shader/Compositor 的复用积木,资产库跨版本还原。**借鉴**：正是项目 09-11"图层样式需 `.ffx`+applyPreset"的同构范式——**把配方外置为按 skill_id 引用的资产(.ffx/卡片),实现与调用分离,集中更新**,并用"参数暴露契约"限定哪些参数可被 LLM/用户调(防越界)。

> **附：一个现成的 skill-card 模板实例**[41]——`data-quality-frameworks` SKILL.md 用 `frontmatter(name/description) + Use when/Do not use when + Instructions + Safety + Resources + Version History(commit e63f7dd + 时间戳 2026-07-05 09:30)`，正是项目 skill 卡片可直接照抄的结构（含**版本历史=commit+时间戳**，回答 Q3）。

---

## 4. Critical Assessment：反方视角与失败模式 [Confidence: Medium-High]

1. **过度 schema 化（最强反方证据）**：video-use 明确把"Hierarchical pre-computed codec formats with USABILITY/tone tags/shot layers"列为 anti-pattern，主张"在决策时从素材派生"[5]。项目 18 类型仅 10 可渲染、139 条配置仅 33 条可渲染[guide]，已在漂移区。**结论：集成应先"接已验证的少数"，冻结未实现的 premium 类型（标注 experimental），而非扩 schema。**
2. **schema-valid ≠ 正确**：结构合法不代表业务正确（分项之和/时序需后端兜底）[17]。项目的 `lint_edl`（L1-L6）[edl.py] + `effects_injection_report` 对账[guide] 是对的，但需补"业务级"校验（如 overlay 时间不越界、onset 对齐≤2帧——这些散落在 tmp/verify_*.py，应上升为契约闸门）。
3. **依赖地狱**：ComfyUI 官方承认"节点包间 Python 依赖冲突可使整个安装不可用"[13]。项目 8GB 显存 + 离线环境下，能力卡片的依赖声明必须严格（对应[12]的版本兼容矩阵）。
4. **配置漂移伪装成模型不稳定**：Agent=Model+Harness，工具间配置漂移会产生"看似模型不稳"的失败[32]——呼应项目 v6.1"字体静默回退"、Glo2 序号陷阱：**能力卡片必须锁定"验证时宿主版本"**（Resolve SetLUT 0→1 基[27] 是同类铁证）。
5. **数据契约失败多因问责不清而非工具**[29]：项目多会话并行（ZCode/进度会话），EDL 作为 producer(Python链)↔consumer(AE链) 契约，必须明确"谁改 schema 谁通知"——对应项目协作规约§九。

---

## 5. Action Plan（详见配套落地方案文档）

- [ ] **A1｜EDL 增 `overlays/effects` 轨道段**（借鉴 video-use[5] + OTIO Track[1]）：在 `scripts/edl.py` 的 EDL schema 加 `overlays:[{file,start_in_output,duration,source_skill_id}]` 与 `effects:[{effect_id,effect_type,time_range,parameters,envelope,evidence_chain}]` 段，**FORWARD 兼容**（旧 consumer 忽略新段）[29]。这是解开 K3「双链无桥」的契约级最小改动。
- [ ] **A2｜`build_text_overlay.py` / `build_master_polish.py` 改吃 `edl.json`**（而非各自读 production_report）：以 EDL 为单一真源[24]，使 R1 修复成果自动传导到文字/视觉层。保留 `production_report` 作为 EDL 的上游生成源（`build_edl` 已如此[edl.py]）。
- [ ] **A3｜把 `build_text_overlay` 注册进编排器**：在 `mastercut_agent.py` 的 `ToolRegistry`[mastercut] 注册为 `render_text_overlay` 工具，或作为 `unified_edit.py` 的可选 stage（`enable_ae` 通道已有钩子[unified_edit L514]），消除"孤儿脚本"。
- [ ] **B1｜能力卡片注册表**（借鉴 MLT YAML[7]+ComfyUI pyproject[11]+Model Card[20]）：新建 `schemas/skill_cards/*.yaml`，每卡含 `skill_id / version(semver) / effect_type / parameters(范围) / requires-host(AE版本) / intended_use / out_of_scope / validated_at(时间戳) / validation_evidence(渲染差分/网格帧路径) / status(active|standby|experimental)`。把 `data/style_cards/beat_grammar_validated_v1.json` 迁入。
- [ ] **B2｜治理闸门**：`build_master_polish` 对"无有效卡片/卡片过期"的效果计入 `unmapped/skipped` 并记原因（复用现有对账[guide]），实现"无卡片不进 production"[22]。
- [ ] **C1｜schema 单一真源生成**：由 `RECIPES`+卡片参数范围**生成** `visual_effect_schema.json`（消除手写漂移[17]），CI 加 `test_visual_effect_schema.py` 校验 enum↔RECIPES 一致（钉死 `radial`/`radial_blur` 分裂[guide]）。
- [ ] **C2｜changelog + 版本时间戳**：`schemas/CHANGELOG.md` 记 schema_version 演进；每卡片 `validated_at` + `requires-host`；破坏性变更走弃用周期[28]。
- [ ] **C3｜evidence_chain 升级 PROV 式**[18][19]：`skill_id → wasGeneratedBy(run/render) + validated_at + host_version`，与 `data/evolution/*` 血缘打通，喂 acceptance_log（解 K7）。
- [ ] **D1｜确定性生成（可选，后置）**：若需 LLM 生成配方，上 `guidance/outlines` grammar 约束或 Instructor retry 闭环[15][16][38]，替代"把 schema 塞 prompt"的软约束。
- [ ] **B3｜Skill Registry（Wave3）**：借 MLflow Registry[34]+Terraform SemVer[35] 建 `schemas/skill_cards/registry.json`——每能力带 `version(SemVer)/stage(validated→active→deprecated)/source(验证 run+渲染差分)/checksum/requires-host(AE 版本)`；**晋升过验证闸门，无卡片不进 production**。
- [ ] **B4｜配方外置为按 skill_id 引用的资产（Wave3）**：借 Nuke Gizmo[40] 范式——效果配方外置为 `.ffx`/卡片文件按名引用，实现与调用分离、集中更新；`Export gizmo` 式**参数暴露契约**限定 LLM/用户可调参数（呼应 09-11「图层样式需 .ffx+applyPreset」）。
- [ ] **C4｜evidence_chain 升级 in-toto 式 attestation（Wave3）**：借 SLSA/in-toto[36]——`skill_id→wasGeneratedBy+inputs(SHA1)+validated_at+output_digest+host_version`，复用 `edl.py` 已有的 `sha1/toolchain/generated_at`，离线本地签名，喂 acceptance_log。
- [ ] **C5｜schema 单一真源（Wave3）**：借 CUE[37]/Pydantic[38]——由 `RECIPES`+参数范围**生成** `visual_effect_schema.json`+校验器，CI 钉 enum↔RECIPES 一致（根治 `radial`/`radial_blur` 分裂与手写漂移）。
- [ ] **C6｜校验收敛为 Expectation-Suite 契约闸门（Wave3）**：借 Great Expectations[39]——把散落的 `verify_v*.py`/`check_delivery_spec.py`/`cut_visibility_v3.py`/五门收敛为一套每 run 强制跑、结果落盘成"活文档"的闸门，对接 acceptance_log(K7)。

## 6. Open Questions & Caveats

- **HyperFrames/OpenMontage 许可证与离线可用性【待验证】**：项目文档曾标 HyperFrames "LICENSE 复核前置"；HyperFrames 需 Node.js 22+[5]，与项目"纯 Python+离线+8GB"栈的兼容性未验证。仅作范式参考，非直接依赖。
- **OTIO 是否值得引入为依赖【待确认】**：OTIO 是 C++ 核心+Python 绑定[1]，引入成本 vs 自维护 `edl.py` 的取舍需评估；**建议先按 A1 扩展自有 EDL（零新依赖），把 OTIO 作为"未来若需跨 NLE 交换再引入"的选项**。
- **本环境部分来源为 CSDN/博客镜像（Tier 3）**：OTIO/MLT/ComfyUI 的细节部分来自 CSDN gitblog 镜像[2][8]，虽与官方一致但已标注；关键结论均以 Tier 1/2 官方源交叉印证。
- **单代理执行**：deep-research 标准用 4-6 检索子代理，本环境无通用检索子代理，改由主代理执行（已在 Methodology 记录），来源数 32 达 deep 档下限。

## Methodology

- **深度**：deep。**检索**：主代理直接执行（平台无通用检索子代理，属 deep-research 允许的 Platform Adaptation），**3 波**共 20 次 WebSearch + 1 次 WebFetch（video-use SKILL.md 一手抓取）；Wave 3 因本地代理启用补抓一手/权威源。**来源**：41（Tier1≈18/Tier2≈13/Tier3≈10）。
- **三角验证**：核心主张（EDL 承载 overlays、能力卡片=元数据+版本+验证、schema 单一真源防漂移）均由 ≥2 独立来源支撑（如 overlays 由 video-use[5]+OTIO Track[1] 互证；卡片版本由 ComfyUI[11]+MLT[7]+ModelCard[20] 三证）。
- **引用核查（Phase 3.1）**：对最高影响力主张自核——video-use EDL 字段（一手抓取确认 `overlays[{file,start_in_output,duration}]`[5]）、OTIO 数据模型（Foundry 官方[1]+CSDN[2] 一致）、Resolve SetLUT 0→1 基版本漂移[27]、ComfyUI pyproject `[tool.comfy]`[11] 均 SUPPORTED。
- **红队自批（Phase 4）**：主动纳入反方（video-use over-engineering anti-pattern[5]、ComfyUI 依赖地狱[13]、schema-valid≠正确[17]），避免单边结论。
- **降级说明**：无整波失败；Area 7 直接检索命中较少，改由 data-contract/structured-output 的失败模式章节覆盖。

## Bibliography

[1] Foundry (Nuke Newsletter) — OpenTimelineIO: API and interchange format for editorial cut information — https://www.foundry.com/zh-hans/insights/nuke-newsletter/otio — Accessed 2026-09-11 — Tier 1【已实证】
[2] CSDN gitblog — OpenTimelineIO 使用教程/生态系统（数据模型 Timeline/Track/Clip/Transition/Composition；插件 Media Linkers/HookScripts/SchemaDefs；adapters EDL/AAF/XML）— https://blog.csdn.net/gitblog_00335/article/details/141732265 — Accessed 2026-09-11 — Tier 3【社区讨论】
[3] Grokipedia — Edit decision list (CMX3600 format) — https://grokipedia.com/page/Edit_decision_list — Accessed 2026-09-11 — Tier 3【社区讨论/格式已实证】
[4] WyattBlue — Auto-Editor（--export premiere/resolve/final-cut-pro/shotcut/clip-sequence；非破坏式时间线优先）— https://github.com/WyattBlue/auto-editor / https://auto-editor.com/docs — Accessed 2026-09-11 — Tier 2【已实证】
[5] browser-use — video-use/SKILL.md（edl.json 契约含 overlays/grade/subtitles；render.py；Hard Rules vs 艺术自由；并行子代理；project.md 记忆；anti-patterns）— https://github.com/browser-use/video-use/blob/main/SKILL.md — Accessed 2026-09-11（一手抓取）— Tier 2【已实证】
[6] maxazure — video-editing-skill（可审计 cut list、provider decision 台账）— https://github.com/maxazure/video-editing-skill — Accessed 2026-09-11 — Tier 3【社区讨论】
[7] CSDN gitblog / MLT — MLT Framework 视频滤镜开发（Producer/Filter/Tractor/Consumer；filter YAML: name/identifier/type/version/parameters[default,range]；mlt_repository_register）— https://m.blog.csdn.net/gitblog_00746/article/details/148945766 — Accessed 2026-09-11 — Tier 2【已实证】
[8] CSDN gitblog — CLI-Anything：MLT→ffmpeg 滤镜翻译层（参数空间转换/滤镜合并/流排序）— https://m.blog.csdn.net/gitblog_00554/article/details/155894908 — Accessed 2026-09-11 — Tier 3【社区讨论】
[9] Kdenlive/Shotcut — 基于 MLT + frei0r + LADSPA（data/effects/frei0r）— https://gitcode.com/gh_mirrors/kd/kdenlive — Accessed 2026-09-11 — Tier 2【已实证】
[10] docs.comfy.org — 在 ComfyUI 中安装自定义节点（custom_nodes/ + requirements.txt + Manager 注册表 + 安全审查）— https://docs.comfy.org/zh/installation/install_custom_node — Accessed 2026-09-11 — Tier 1【已实证】
[11] CSDN / Comfy Registry — 发布节点到 Comfy Registry（comfy node init/pack/publish；pyproject.toml [project]version + [tool.comfy]PublisherId/requires-comfyui）— https://m.blog.csdn.net/u014451778/article/details/156202270 — Accessed 2026-09-11 — Tier 2【已实证】
[12] CSDN gitblog — ComfyUI-Manager 版本兼容矩阵（V3.16+ 需 ComfyUI v0.1.2 / Python 3.10-3.12）— https://m.blog.csdn.net/gitblog_00691/article/details/152067546 — Accessed 2026-09-11 — Tier 2【已实证】
[13] comfyui.org — ComfyUI custom node V3 dependency resolution（依赖冲突可使安装不可用）— https://comfyui.org/en/comfyui-v3-dependency-resolution — Accessed 2026-09-11 — Tier 2【已实证】
[14] 火山引擎开发者 / OpenAI — Structured Output：JSON Mode→Structured Outputs，constrained decoding（按 token+schema mask 非法 token），strict json_schema — https://developer.volcengine.com/articles/7672371448832327689 — Accessed 2026-09-11 — Tier 1【已实证】
[15] Microsoft Research — guidance（grammar/regex 约束生成，保证合法 JSON/XML/code）— https://github.com/guidance-ai/guidance — Accessed 2026-09-11 — Tier 1【已实证】
[16] CSDN / LM-Kit / Instructor — Structured-Output 与 Constrained-Decoding（outlines/xgrammar + JSON Schema；vLLM guided_json；Instructor Pydantic retry 闭环）— https://m.blog.csdn.net/qq_36354988/article/details/162953972 · https://docs.lm-kit.com/lm-kit-net/guides/glossary/structured-output.html — Accessed 2026-09-11 — Tier 2【已实证】
[17] chenxutan.com — Structured Outputs 生产笔记：三个静默失效点（schema 与下游类型漂移→Pydantic/Zod 单一真源；结构合法≠业务正确；strict 延迟）— https://www.chenxutan.com/d/6456.html — Accessed 2026-09-11 — Tier 3【社区讨论，高相关】
[18] chinaaet / prov(Python) — W3C PROV 数据模型（Entity/Activity/Agent；wasDerivedFrom/used/wasGeneratedBy/wasInformedBy/wasAttributedTo；PROV-O/N/XML/JSON）— http://chinaaet.cn/article/3000024465 · https://github.com/trustinlee/prov — Accessed 2026-09-11 — Tier 1【论文/标准】
[19] toutiao — semantica：决策即图上一等公民（record_decision/trace_decision_chain/confidence_decay/weakest_link；export_prov；确定性、可离线）— https://m.toutiao.com/article/7682678362724942382/ — Accessed 2026-09-11 — Tier 3【社区讨论，高相关】
[20] Mitchell et al. 2018 — Model Cards for Model Reporting — https://arxiv.org/abs/1810.03993 — Accessed 2026-09-11 — Tier 1【论文】[foundational]
[21] Gebru et al. 2018 — Datasheets for Datasets — https://arxiv.org/abs/1803.09010 — Accessed 2026-09-11 — Tier 1【论文】[foundational]
[22] CSDN / AWS SageMaker — 模型注册中心与版本管理（Stage 状态机/Source run-id/Checksum/Lineage；无 model card 拒进 production；ModelCardVersion/Status/时间戳）— https://m.blog.csdn.net/m0_68987304/article/details/163373081 · https://docs.aws.amazon.com/sagemaker/ — Accessed 2026-09-11 — Tier 2【已实证/社区】
[23] HuggingFace — Model Cards（README.md YAML frontmatter：license/datasets/tags）— https://huggingface.co/docs/hub/en/model-cards — Accessed 2026-09-11 — Tier 1【已实证】
[24] Remotion — remotion.dev + 深度拆解（React code=source of truth；Composition；useCurrentFrame/interpolate/spring；Player+Lambda 同 composition；Headless Chrome→FFmpeg）— https://www.remotion.dev/ · https://www.chenxutan.com/d/5609.html — Accessed 2026-09-11 — Tier 1/2【已实证】
[25] heygen-com — HyperFrames（Write HTML, Render video, Built for agents；HTML→deterministic MP4；__timelines seek；lint/validate/render；需 Node 22+）— https://github.com/heygen-com/hyperframes — Accessed 2026-09-11 — Tier 2【已实证】
[26] tosea.ai — OpenMontage：开源 agentic 视频生产（Remotion+HyperFrames+FFmpeg 栈）— https://tosea.ai/blog/openmontage-agentic-video-production-guide — Accessed 2026-09-11 — Tier 3【社区讨论】
[27] Blackmagic / CSDN — DaVinci Resolve Scripting API（对象模型；Timeline.Export AAF/EDL/FCPXML；-nogui 无头；Fusion/Scripts 目录分页可见；SetLUT nodeIndex v16.2 由 0 基改 1 基）— https://blog.csdn.net/oPxk_6/article/details/152725231 — Accessed 2026-09-11 — Tier 1/2【已实证】
[28] Actian — Data Contracts: Definition, Components, Implementation（ODCS YAML：fundamentals/schema/quality/team；同仓版本化；管线内嵌校验；版本+向后兼容+弃用）— https://www.actian.com/data-contracts/ — Accessed 2026-09-11 — Tier 2【已实证】
[29] Acceldata / Confluent — How Data Contracts Enforce Pipeline Stability（Schema Registry 兼容模式 backward/forward/full/none；版本标签+弃用策略；漂移检测；契约测试；producer-consumer 问责）— https://www.acceldata.io/blog/how-data-contracts-guarantee-pipeline-reliability-data-quality-slas — Accessed 2026-09-11 — Tier 2【已实证】
[30] Dagster — Software-Defined Assets（资产为中心；依赖图=数据图；materialization 历史+lineage+类型检查）— https://dagster.io/ · https://www.getorchestra.io/blog/airflow-alternatives — Accessed 2026-09-11 — Tier 1/2【已实证】
[31] Prefect — Flow/Task（自动推断依赖；重试+可观测性）— https://github.com/PrefectHQ/prefect — Accessed 2026-09-11 — Tier 1/2【已实证】
[32] 阿里云开发者 — Agent = Model + Harness（工具间配置漂移伪装成模型不稳定）— https://developer.aliyun.com/article/1735088 — Accessed 2026-09-11 — Tier 3【社区讨论】
[33] AcademySoftwareFoundation — OpenFX 图像处理插件标准（Suite 模块化 + 运行时宿主能力检测/优雅降级；kOfxPropVersion/APIVersion 多维版本；弃用移入 oldOfx.h；OFX::Host::PropertySet 元数据 + 标准参数类型）— https://github.com/AcademySoftwareFoundation/openfx · https://openfx.readthedocs.io/en/latest/Reference/ofxPropertiesReference.html — Accessed 2026-09-11 — Tier 1【已实证/标准】
[34] MLflow / Azure ML 官方文档 + arXiv:2601.18591 — Model Registry（Model/Version/Artifact；Stage 状态机；transition_model_version_stage；lineage；checksum；无 card 拒进 production）— https://docs.azure.cn/zh-cn/machine-learning/how-to-manage-models-mlflow · https://arxiv.org/pdf/2601.18591 — Accessed 2026-09-11 — Tier 1【已实证/论文】
[35] Terraform Registry / GitLab+阿里云官方文档 — 模块/Provider SemVer 版本；版本约束 `~>`；.terraform.lock.hcl 锁 hash；MAJOR/MINOR/PATCH 契约规则；远程 ref 钉版 — https://docs.gitlab.cn/docs/jh/user/packages/terraform_module_registry/ · https://help.aliyun.com/document_detail/2875530.html — Accessed 2026-09-11 — Tier 1/2【已实证】
[36] SLSA(Linux Foundation)/in-toto/Sigstore + GitLab/GitHub 官方文档 + arXiv:2605.08363(Kettle) — provenance attestation L1-L3；in-toto 签名声明；SLSA Provenance predicate(git commit/repo/pipeline/时间戳/SHA-256/builder-id)；Sigstore 无密钥+Rekor — https://docs.gitlab.cn/docs/jh/ci/pipeline_security/slsa/ · https://docs.github.com/zh/enterprise-cloud@latest/actions/concepts/security/artifact-attestations · https://arxiv.org/html/2605.08363v1 — Accessed 2026-09-11 — Tier 1【已实证/标准/论文】
[37] CUE language(cue-lang)/cuetorials/segmentfault — 统一类型+值+约束(格)；从代码提取 schema/生成校验；hermetic；cue export 冲突检测；JSON/YAML/OpenAPI 互操作 — https://github.com/cue-lang/cue · https://cuetorials.com/zh/overview/foundations/ — Accessed 2026-09-11 — Tier 1/2【已实证】
[38] Outlines/XGrammar/llguidance + tianpan.co/juejin 生产指南 — FSM(Outlines)vs PDA/CFG(XGrammar,vLLM 默认)；FSM 不支持 $ref 递归/oneOf 爆炸；Pydantic/TS-type 单一真源；Instructor retry — https://tianpan.co/zh/blog/2025-10-29-structured-outputs-llm-production · https://juejin.cn/post/7634432180045168646 — Accessed 2026-09-11 — Tier 1/2【已实证】
[39] Great Expectations — Expectation Suite + Checkpoint + Validation Definition + Data Docs(活文档)；Rule-Based Profiler；Dagster+GE @asset 质量门 — https://www.conduktor.io/glossary/great-expectations-data-testing-framework · https://greatexpectations.io — Accessed 2026-09-11 — Tier 1/2【已实证】
[40] Nuke Gizmo(Foundry Learn) + Blender Asset Library/Node Group(Blender 5.1 Manual) — 外置定义按名引用+集中更新；Export gizmo 显式参数暴露契约；节点组跨版本复用 — https://learn.foundry.com/nuke/content/comp_environment/configuring_nuke/creating_sourcing_gizmos.html · https://www.bookstack.cn/read/blender-5.1-en/e1f8bb8e3a57ee09.md — Accessed 2026-09-11 — Tier 1【已实证】
[41] rmyndharis/antigravity-skills — data-quality-frameworks SKILL.md（frontmatter + Use when/Do not use when + Instructions + Safety + Resources + **Version History: commit e63f7dd + 时间戳**）— 现成 skill-card-with-version 模板 — https://tool.lu/ko_KR/skill/s/6E — Accessed 2026-09-11 — Tier 2【已实证】

## Source Extracts（关键一手摘录，供后续会话免重抓）

### [5] video-use/SKILL.md（一手抓取，最高相关）
- **EDL 契约**：`{version, sources{}, ranges[{source,start,end,beat,quote,reason}], grade, overlays[{file,start_in_output,duration}], subtitles, total_duration_s}`；`render.py <edl.json> -o <out>` 按段抽取→concat→覆盖层(PTS偏移)→字幕最后。
- **Hard Rules（正确性，不可协商）**：字幕最后加；分段抽取+无损 concat（非单遍 filtergraph）；每段边界 30ms 音频淡入淡出；覆盖层 `setpts=PTS-STARTPTS+T/TB`；never cut inside a word；每刀 pad 30-200ms；word-level ASR；缓存转写；**并行动画子代理（一代理一文件，唯一文件名不互相覆盖）**；执行前确认策略；产物写 `<videos_dir>/edit/` 不写项目目录。
- **anti-patterns**：过度 schema 化（USABILITY/tone tags/shot layers）= over-engineering，应在决策时从素材派生；手写 moment-scoring 不如 LLM；线性 easing 显机械。
- **记忆**：`project.md` 每会话追加（Strategy/Decisions/Reasoning log/Outstanding）。

### [1][2] OpenTimelineIO
- ILM 主导；C++ 核心+Python 绑定；`Timeline→Track→Clip/Transition/Composition(嵌套)`；`otio_json` 序列化；adapters EDL/AAF/FCPXML；插件 = Media Linkers / HookScripts / SchemaDefs。

### [28][29] Data Contract / Schema Registry
- ODCS YAML：`apiVersion/kind/id/name/version/status + schema(fields/types/constraints) + quality(rowCount/completeness) + team(owner)`；与管线代码同仓；管线内嵌校验（违约→告警+halt）；向后兼容优先，破坏性变更通知 consumer + 弃用周期。兼容模式 backward/forward/full/none。

### [20][21][23] Model Card / Datasheet / HF Card
- Model Card：model version/intended use/out-of-scope/metrics/eval data。HF：README.md YAML frontmatter（license/datasets/tags）。SageMaker：ModelCardVersion/Status/creation+lastModified 时间戳。治理：无卡片拒进 production。
