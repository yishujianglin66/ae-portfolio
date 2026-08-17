# AE-Knowledge-Vault 知识库体系审计报告

> 审计日期：2026-08-14
> 审计类型：只读审计（未修改任何文件）
> 审计维度：文件类型分布 / 机器可消费性 / 消费链路 / MCP 接线 / 价值×可消费性排序 / 主题缺口

---

## 0. 一句话结论

知识库「知识储备」远超「机器可消费性」：10-风格化剪辑知识库表面服务 262 个文件，但真正能被代码结构化调用的，只有少量含「关键词→matchName」表格与「参数/默认值/调整范围」表格的文件；**核心效果映射与转场配方仍是代码硬编码的影子数据（5053 条模拟效果目录），知识库只做「附加补充」而非「单一事实源」**。同时存在两套并行知识加载器（`knowledge/` vs `knowledge_base/`）、多处文件计数陈旧、以及大量「有知识无消费」的孤儿文档。

---

## 1. 各知识库文件类型分布

| 目录 | 总文件 | md | py | pyc | json | 其他 | 真实性质 |
|------|-------|----|----|-----|------|------|---------|
| `10-风格化剪辑知识库` | **262** | 259 | 0 | 0 | 1 | jsx×1, bat×1 | 知识库（纯 md 为主） |
| `11-大师知识库` | **15** | 15 | 0 | 0 | 0 | 0 | 知识库（纯 md） |
| `12-漫剪拉镜大师` | **9** | 9 | 0 | 0 | 0 | 0 | 知识库（纯 md） |
| `13-素材获取与搜索` | **85** | 4 | 21 | 57 | 3 | 0 | **代码/工具目录，非知识库** |
| `14-Silhouette知识库` | **114** | 88 | 26 | 0 | 0 | 0 | 知识库 + 26 个 py 混装 |
| `15-3D模型与骨骼动画知识库` | **92** | 92 | 0 | 0 | 0 | 0 | 知识库（纯 md，8 个子目录） |
| `knowledge_base/` | 48 | 1 | 13 | 33 | 1 | 0 | 代码侧知识模块 |
| `knowledge/` | 19 | 1 | 7 | 10 | 1 | 0 | 代码侧知识模块（旧） |
| `learning/` | 42 | 0 | 11 | 30 | 1 | 0 | 代码侧反馈学习模块 |

**关键发现**：

1. **`13-素材获取与搜索` 是伪知识库**：85 个文件里 78 个是 `.py`/`.pyc`（21 py + 57 pyc），md 仅 4 个。它是「下载器/API/语义搜索」代码工程，被归入知识库目录序列是分类错误。机器可消费性「高」（它本来就是代码），但「知识」价值低。

2. **`14-Silhouette知识库` 混装了 26 个 py**：88 个 md（API 速查、Roto/Paint 指南）+ 26 个 py（`案例模板/` 下），知识库与代码未分离。

3. **计数口径混乱**：任务描述称「10-风格化剪辑知识库 262 个 md」，实际是 **259 md + 1 jsx + 1 json + 1 bat = 262 总文件**。258 个 md 在顶层，1 个 md（`Phase3-音频驱动自动化/index.md`）在子目录。

---

## 2. 机器可消费性抽样评估

抽样读取代表性文件，按「YAML frontmatter / 结构化字段 / 参数化配方 / 纯散文」四档评估：

| 文件 | frontmatter | 结构化表 | 可调用数值 | 评级 |
|------|------------|---------|-----------|------|
| `10-/风格化预设宝典.md` (6559 行) | ✅ title/date/updated/tags | ✅ `参数/默认值/调整范围/说明` | ✅ 50 转场+50 文字+50 调色… 300+ 预设 | **高** |
| `10-/🎬-风格化剪辑知识库-MOC.md` | ✅ title/date/tags | ✅ 板块索引表 | ⚠️ 仅 `[[wiki-link]]` 索引 | 中（导航用） |
| `10-/AE ExtendScript API 原子级映射手册.md` | 未读全 | ✅ matchName 映射 | ✅ 60 效果 matchName | 高（但未抽样正文） |
| `11-/Andrew-Kramer…md` | ❌（用 `> 标签:` 引述） | ✅ 技法表 | ⚠️ 定性为主，少量参数 | 中低 |
| `12-/漫剪拉镜通用技法.md` | ✅ tags | ⚠️ ASCII 图 + 代码块 | ✅ BPM/帧数/缩放范围（散落） | 中低 |
| `14-/Silhouette Python API 速查手册.md` | ❌（`> 分类/更新日期/概述`） | ✅ `函数/参数/返回值/说明` | ✅ API 签名级 | **高** |
| `15-/01-FBX格式结构解析.md` | ❌ | ❌（`问题场景/核心原理` 散文+代码块） | ✅ Python 代码块 | 中 |

**总体画像**：

- **有 YAML frontmatter 的是少数**（MOC、风格化预设宝典、漫剪拉镜通用技法等），且 schema 不统一：有的用 `tags: [a,b]` 行内数组，有的用块状列表；`11-大师` 与 `14-Silhouette` 干脆用 `> 标签:` / `> 分类:` 引述行代替 frontmatter。
- **参数化配方真实存在但占比低**：`风格化预设宝典.md`、Silhouette/API 手册是「参数表驱动」的高价值文件；但大量文件是「深度研究报告」纯散文（如各种 `xxx深度研究报告.md`），机器只能全文检索、无法按字段调用。
- **知识库侧已有「原子化/YAML schema」意识但未落地为统一规范**：`AE ExtendScript API 原子级映射手册`、`音效设计原子体系与音画同步` 等标题自述「原子级」，但内容仍是 md 表格/散文，没有统一的 machine-readable JSON/YAML schema 文件。

---

## 3. 消费链路分析（谁在读这些 md）

### 3.1 消费映射总览

| 知识库 | 消费方（代码路径） | 消费方式 | 状态 |
|--------|-------------------|---------|------|
| `10-风格化` | `knowledge_mcp_server.py` → `knowledge_base/kb_loader.py` | MdParser→表格/箭头提取 | **主消费路径（MCP）** |
| | `knowledge_base/kb_scanner.py` | `rglob` + 正则提取 ADBE/CC/BCC… | 效果名提取 |
| | `knowledge/kb_loader.py`（旧 KBLoader） | `glob **` + 正则 | **并行重复实现** |
| | `effects/effect_registry.py` | 合并 KB 映射（fallback 兜底） | 只做加法 |
| | `video/transition_rebuilder.py` | 合并 KB 转场（fallback 兜底） | 只做加法 |
| | `aep_analyzer/template_learner.py`、`ae/ae_extension_integrator.py`、`vrs/vrs_knowledge_rag.py`、`integrations/*`（smart_director/modelscope_vector_search/kb_search_engine）、`scripts/extract_kb_presets.py` | 各自独立引用 | 分散 |
| `11-大师` | `knowledge_mcp_server.py`（`_ensure_master_index`）、`knowledge_base/style_matcher.py`、`knowledge/kb_loader.py`、`integrations/smart_director.py` | 解析 `> 标签:` 行 + 标题 | 已接线 |
| `12-漫剪` | `models/data/prepare_training_data.py`（amv_masters_dir）、`integrations/smart_director.py`（仅注释提及） | 训练数据 / 仅文档引用 | **几乎无实质消费** |
| `13-素材` | `puppet-automation/src/api/media_router.py`、`scripts/media-manager.py`、`tests/*` | 直接 import 下载器/API | 是代码，直接调用 |
| `14-Silhouette` | `silhouette/silhouette_executor.py`、`knowledge/kb_loader.py`（KB_ROOTS 含 14） | 路径指向 + 旧 loader 扫 | 接线弱 |
| `15-3D` | `puppet-automation/src/services/blender_nl_service.py`（`07-Blender Python API参考`） | 单点读取 API 参考 | **单点弱接线** |

### 3.2 知识断层（有知识无消费）

1. **`12-漫剪拉镜大师` 断层**：9 个 md 中 8 位大师 + 1 MOC，唯一实质消费是 `models/data/prepare_training_data.py` 拿它做 AMV 训练目录；`integrations/smart_director.py` 只是 docstring 里提到「漫画剪辑节奏」，无代码读取。**整套拉镜技法库对剪辑管线零价值贡献**（且管线已有 `transition_rebuilder.py` 用硬编码实现推拉转场）。

2. **`15-3D` 大部分子目录断层**：`blender_nl_service.py` 只读了 `07-Blender Python API参考`；其余 7 个子目录（FBX 导入/骨骼创建/蒙皮/矩阵/武器归位/渲染/调试）**没有任何代码消费**，纯人工参考。

3. **`14-Silhouette` 断层**：`silhouette_executor.py` 只声明了 `KNOWLEDGE_BASE_DIR` 路径常量，未抽样到实际读取 md 的调用；88 个 md 几乎无人消费。

4. **`10-风格化` 内部大量「深度研究报告」孤儿文档**：MOC 索引表之外的 md（如 `色彩科学体系完全知识库.md`、`MG动画制作完整指南.md`、`MG动画效率工具链-Cavalry-Rive-Lottie.md`、`Particular粒子实战案例大全.md`、`字体预设库.md`）**未挂入 MOC**，`knowledge_base` 加载器 `list_files()` 又只用 `os.listdir` 非递归扫描，若将来这些文件移入子目录会被静默漏掉。

### 3.3 硬编码影子（代码 hardcode 而未读知识库）

这是最严重的问题 —— **知识库只是「影子数据」的补充，而非权威源**：

1. **`knowledge_base/kb_scanner.py` 内嵌 5000+ 条模拟效果数据库**：`_generate_plugin_effects()` 手工构造 Adobe 内置/Cycore/Trapcode/Magic Bullet/Universe/BCC/Sapphire 等 15 个插件包的效果清单，注释明写「**这是为了达到 5000+ 效果的目标而设计的模拟数据**」。最终产物 `knowledge_base/effect_catalog.json`（1.6MB，`total_effects: 5053`，生成于 2026-07-20）。**这 5053 条效果与 md 知识库基本无关**，md 仅被 `_extract_effects_from_md()` 用正则扫出 `ADBE/CC/BCC/...` 前缀字符串。

2. **`effects/effect_registry.py` 硬编码映射 + 强制保护**：`KEYWORD_TO_EFFECT_MAP`（~100+ 条中文/英文关键词→matchName）、`_HARDCODED_EFFECT_MAP` 兜底，末尾还有 `_CRITICAL_MAPPINGS`（模糊→`ADBE Gaussian Blur 2`、发光→`ADBE Glo2`、粒子→`ADBE Particle Playground` 等 6 条）**在 KB 合并后强制覆盖回硬编码值** —— 意味着知识库里即便写了更准的映射，也被硬编码压回。

3. **`video/transition_rebuilder.py` 硬编码转场 + KB 只增不覆盖**：`TRANSITION_IMPL_MAP`（linear_wipe/zoom_blur/glitch/light_leak/… 具体 `Transition Completion` 关键帧参数）硬编码，`_load_knowledge_base()` 只把「KB 有而代码没有」的转场类型追加进来，`if trans_type not in TRANSITION_IMPL_MAP` 意味着**代码已有的转场永不信任知识库**。

4. **`knowledge_base/kb_loader.py` 内嵌 `_PARAM_TEMPLATES` / `_USAGE_SCENARIOS` / `_generate_default_presets`**：blur/color/light/particle 等 17 类参数的默认值、范围、使用场景，全部硬编码在 loader 里；`enrich_effect_with_kb()` 名为「用知识库丰富」，实则当 `effect.params` 为空时用**硬编码模板**填充，而非查 md。

> 结论：效果映射、转场配方、参数模板的「单一事实源」目前仍是 **Python 源码**，md 知识库处于「装饰性加载」地位。

---

## 4. 知识库与 MCP 的接线核查

`knowledge_mcp_server.py`（根目录，`FastMCP("Knowledge-Bridge")`）声明服务「262 个 md（10-风格化）+ 15 个 md（11-大师）」，实际核查：

| 检查项 | 结论 |
|--------|------|
| `_KB_DIR` / `_MASTER_KB_DIR` 路径 | ✅ 正确（`_PROJECT_ROOT / "10-风格化剪辑知识库"` / `"11-大师知识库"`） |
| `search_knowledge_base` → `KnowledgeBaseLoader.search` | ✅ 走 `knowledge_base/kb_loader.py` 门面 |
| `list_knowledge_files` | ⚠️ 用 `kb_dir.glob("*.md")` **非递归**，只见 258 个顶层 md，漏 `Phase3-音频驱动自动化/index.md`；且 docstring「262 个文件」与真实 259 md 不符 |
| `search_master_knowledge` | ✅ `_ensure_master_index` 用 `glob("*.md")`（11-大师无子目录，OK）；但 docstring「15 位大师」实为 **14 位大师 + 1 个 MOC**（`🎓-大师知识库-MOC.md` 不是大师） |
| 计数一致性 | ❌ 三处计数互相矛盾：MCP docstring「262 md」、`knowledge_base/__init__.py`「211 个 md」、`knowledge/kb_loader.py`「400+ MD」。真实：10-风格化 259 md，10+11+14 合计 362 md |

**MCP 之外的接线缺陷**：`knowledge_mcp_server.py` 只服务 10-风格化 + 11-大师；**12-漫剪、13-素材、14-Silhouette、15-3D 四个库完全不在 MCP 工具面**（`list_knowledge_files` 的 category 仅 `style/master/all`），Agent 通过 MCP 无法检索这四个库。

---

## 5. 六库排序（对剪辑管线价值 × 机器可消费性）

| 排名 | 目录 | 管线价值 | 机器可消费性 | 综合评级 | 处置建议 |
|------|------|---------|-------------|---------|---------|
| 🥇 1 | `10-风格化剪辑知识库` | 极高（效果/转场/调色/预设全栈） | 中（部分结构化，前端异构） | **核心资产，优先结构化改造** | 抽取「风格化预设宝典/映射手册」为 YAML/JSON schema，其余散文保留为 RAG 语料 |
| 🥈 2 | `15-3D模型与骨骼动画知识库` | 高（Blender/骨骼/FBX 管线） | 中高（Python 代码块+清晰子目录） | **高价值但消费断链** | 已有 8 子目录结构好，补 YAML frontmatter + 参数表，接入 blender_nl_service 之外的消费方 |
| 🥉 3 | `14-Silhouette知识库` | 中高（Roto/Paint 专业） | 高（API 速查表） | **可消费性最好但价值窄** | API 手册可直接转 schema；清理 26 个 py 出知识库 |
| 4 | `11-大师知识库` | 中（方法论/大师经验） | 中低（引述行+散文） | 参考价值为主 | 保留为 RAG 语料，统一 `> 标签:` 为 frontmatter |
| 5 | `12-漫剪拉镜大师` | 中低（AMV 拉镜小众） | 中低（ASCII 图+散文） | **低价值纯收藏** | 不改造；技法并入 10-风格化的转场体系 |
| 6 | `13-素材获取与搜索` | 中（素材工具链） | 高（本就是代码） | **分类错误，非知识库** | 移出知识库编号序列，归入 `puppet-automation` 或独立 tools 目录 |

---

## 6. 应立即结构化改造的对象（含 schema 建议）

### 6.1 优先改造清单

1. **`10-风格化剪辑知识库/风格化预设宝典.md`**（6559 行，最高价值）
2. **`10-风格化剪辑知识库/AE ExtendScript API 原子级映射手册.md`**（matchName 映射）
3. **`10-风格化剪辑知识库/AE效果视觉特征库.md` / `参数-效果原子级映射库`**（效果指纹）
4. **`14-Silhouette知识库/Silhouette Python API 速查手册.md`**（API 签名）
5. **`10-风格化剪辑知识库/音效设计原子体系与音画同步.md`**（音效原子库，已被多处 [[引用]] 却无代码消费）

### 6.2 统一 YAML frontmatter schema 建议

```yaml
---
# 必填
schema: "ae-kb/1.0"          # 声明机器可读 schema 版本
id: "style-preset-baodian"    # 稳定 id（英文 slug）
title: "风格化预设宝典"
kind: "preset_catalog"        # preset_catalog | effect_mapping | transition_recipe | color_preset | sound_design | api_reference | prose_report | moc
category: ["转场","文字动画","调色"]   # 主题标签数组（统一 list 格式）
version: "2026-07-12"

# 可选
consumed_by: ["effect_registry","kb_loader"]   # 声明哪些代码模块应消费
params_schema:                  # 参数化配方的显式字段定义
  transition:
    fields: ["name","effect","default","range","unit"]
---
```

配套动作：把 md 内散落的参数表固化为同目录 `*.params.json`（或 `data/kb_schema/`），让 `knowledge_base/kb_loader.py` 优先读 JSON，md 仅作人工阅读与 RAG 语料——从根源消除「正则猜表格」的脆弱性。

### 6.3 消除硬编码影子

- 把 `kb_scanner._generate_plugin_effects()` 的模拟数据、`effect_registry.KEYWORD_TO_EFFECT_MAP`、`transition_rebuilder.TRANSITION_IMPL_MAP` 迁出源码，落盘为 `data/effect_catalog.json`（已存在）与 `data/transition_recipes.json`（需新建），代码只读 JSON。
- 删除 `_CRITICAL_MAPPINGS` 的「强制覆盖」逻辑，改为「知识库优先、代码仅兜底」且记录来源与置信度。

---

## 7. 主题覆盖与缺口清单

### 7.1 任务点名主题的覆盖结论（均「有覆盖」，但质量分层）

| 主题 | 覆盖文件 | 覆盖质量 | 机器可消费 |
|------|---------|---------|-----------|
| 音效设计 | `音效设计原子体系与音画同步.md`、`音效体系与图层操作工具链.md`、`Audition-音频处理与专业工作流完全指南.md`、`Premiere-Pro-音频处理与音效设计指南.md` | **好**（36 原子音效/6 分类） | ❌ 无代码消费（断层） |
| 字体排版 | `字体设计与排版系统深度研究报告.md`、`字体运用知识库.md`、`字体预设库.md`、`Photoshop-文字与排版设计完全指南.md` | 好 | ⚠️ `字体预设库.md` 被 `config/_validate_jsx.py` 硬编码路径引用，无 schema |
| 色彩科学 | `色彩科学体系完全知识库.md`、`AE-色彩管理与HDR工作流完全指南.md`、`AE-色彩心理学与调色理论.md` | 好 | ⚠️ 纯散文为主，缺 OKLab/色彩空间数值 schema（四维映射库有 OKLab 提及） |
| 粒子 | `Particular粒子实战案例大全.md`、`Trapcode Suite 全插件参数详解`、`AE效果插件完全速查手册` | 好 | 部分（kb_scanner 有 particle 分类+参数模板） |
| MG 动画 | `MG动画制作完整指南.md`、`MG动画效率工具链-Cavalry-Rive-Lottie.md`、`Illustrator-矢量图形与MG动画完全手册.md`、`Ben-Morris-MG动画大师.md` | 中 | ❌ 无代码消费 |
| 转场节奏 | `AE-转场效果系统深度研究报告.md`、`段落结构-效果编排与转场联动库.md`、`节拍-关键帧精密映射库.md` | 中 | 部分（transition_rebuilder 硬编码，KB 只增不覆盖） |

### 7.2 真正的缺口（而非任务猜测的空白）

1. **转场节奏量化最薄弱**：转场「种类」丰富，但「节奏/时长/缓动」没有统一的机器可读节奏 schema（如 `{bpm, beat, transition_type, duration_frames, easing}`）。这是音画匹配引擎最需要、却最缺失的一环。
2. **音效设计「有知识无 schema 无消费」**：`音效设计原子体系与音画同步.md` 明确写了「音效库索引.yaml」格式，但代码库里**没有任何消费者**读取该文件/格式 —— 是典型的「知识断层」。
3. **大量「深度研究报告」未入 MOC（孤儿文档）**：`色彩科学体系完全知识库.md`、`MG动画制作完整指南.md`、`MG动画效率工具链`、`Particular粒子实战案例大全.md`、`字体预设库.md` 等未出现在 MOC 索引表，人工导航与 MOC 遍历会漏掉。
4. **知识库内无统一 schema 文件**：全库没有 `*.schema.json`/`*.params.json` 这类机器直接消费的契约文件，参数全部藏在 md 表格/散文中。

---

## 8. 审计建议摘要（按优先级）

1. **【P0】统一单一事实源**：把硬编码效果/转场/参数模板迁入 `data/*.json`，删除 `kb_scanner` 模拟数据与 `_CRITICAL_MAPPINGS` 覆盖逻辑，让 md/JSON 知识库成为权威源，代码只读不写。
2. **【P0】合并两套加载器**：`knowledge/kb_loader.py`（旧）与 `knowledge_base/kb_loader.py`（新）二选一，统一扫描范围（递归 rglob）与 schema 解析，避免「一个文件两处解析结果不一致」。
3. **【P1】修正 MCP 计数与扫描**：`list_knowledge_files` 改递归、修正「262/211/400+」三处矛盾口径，并把 12/14/15 库纳入 MCP 工具面。
4. **【P1】结构化改造高价值文件**：对 `风格化预设宝典`、ExtendScript 映射手册、Silhouette API 手册落地统一 YAML frontmatter + params JSON。
5. **【P2】补断链**：为音效原子库、MG 动画、3D 骨骼、漫剪拉镜接上实际消费方，或明确降级为「人工参考」。
6. **【P2】目录治理**：`13-素材获取与搜索` 移出知识库序列；`14-Silhouette` 的 26 个 py 分离。
