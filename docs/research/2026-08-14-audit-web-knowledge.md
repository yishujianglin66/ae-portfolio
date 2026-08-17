# 视频剪辑知识 & 工程最佳实践 · 全网调研报告

> 调研日期：2026-08-14
> 目标项目：AE 知识库 + AI 剪辑管线（知识体系：10-风格化剪辑 / 11-大师 / 12-漫剪拉镜 / 14-Silhouette / 15-3D 与骨骼动画）
> 核心痛点：知识库是散文式 md，机器不可直接消费；「知识断层」——207 个风格文件未被管线读取。
> 调研方法：web_search 23 次，覆盖 7 大主题。评级口径：**P0 = 可直接改造采用（机器可消费/结构化/可执行）**；**P1 = 参考借鉴**；**P2 = 存档备查**。

---

## 0. 结论速览（TL;DR）

1. **最大发现**：`ClipSkills` 与 `LottieFiles/motion-design-skill` 两个项目几乎精确复刻了本项目的目标形态——「把剪辑/运动设计经验沉淀为 AI Agent 可决策、可复现的 SKILL 卡」。前者是中文生态、分层架构（知识内核 + 执行层）与「软件无关知识内核」的提法直接对标本项目「机器可消费结构化知识」的诉求。
2. **机器可消费的「本体/分类法」已有现成标准**：EBU SKOS《视频转场类型码分类法》与 MovieLabs《媒体创作本体》可作项目「效果映射/转场配方」字段枚举的上游 schema 参照，避免自造轮子。
3. **调色知识有完整开源工具链**：colour-science / OpenColorIO / DCTL 合集 / LUT_SLM 数据集，项目已有的 `DCTLs` 目录可直接对齐 mitkunz/resolve_DCTLs 的组织方式。
4. **AE 表达式知识有权威可移植源**：`docsforadobe/after-effects-expression-reference`（结构化、社区维护）是「表达式知识卡」的最佳数据源。
5. **AMV/漫剪方法论的机器可读化仍是空白**：中文社区（B站）只有视频教程/散文，animemusicvideos.org 有经典理论但非结构化——这是本项目可以差异化产出的机会点。
6. **LLM 知识工程方向**：主流共识是「蒸馏（distill）优先于切块向量化（chunk & vector）」，并走向「图 + 向量」混合记忆（A-Mem / MemWeave / Temporal-Stratified Retrieval），与项目「结构化知识卡」路线一致。

---

## 1. 结构化知识项目（对标「知识卡/schema 组织方式」）

| # | 名称 | URL | 类型 | 许可/可用性 | 相关板块 | 评级 |
|---|------|-----|------|------------|---------|------|
| 1.1 | **ClipSkills** | https://github.com/appergb/ClipSkills | 开源仓库（AI Agent 剪辑技能套件） | 公开 GitHub 仓库，可 fork | 10 / 11 / 12 全板块 | **P0** |
| 1.2 | **LottieFiles/motion-design-skill** | https://github.com/lottiefiles/motion-design-skill | SKILL.md 技能卡 | 公开，SKILL.md 标准 | 10-风格化（运动设计原理） | **P0** |
| 1.3 | **EBU SKOS 视频转场类型码分类法** | https://tech-metadata.ebu-it-tools.ch/ontologies/skos/ebu_VideoTransitionTypeCodeCS.htm | 本体/分类法（SKOS） | 标准组织发布，公开 | 10-转场配方（字段枚举） | **P0** |
| 1.4 | **MovieLabs 媒体创作本体** | https://www.digitalcinemareport.com/movielabs-publishes-ontology-for-media-creation/ | 本体/数据模型 | 行业联盟发布 | 全板块（schema 顶层参照） | **P1** |
| 1.5 | **awesome-ae** | https://github.com/inlife/awesome-ae | 精选资源清单 | 公开，MIT 类 | 10 / 14（AE 生态） | **P1** |
| 1.6 | **llm-knowledge-base（AGENTS.md spec）** | https://github.com/arturseo-geo/llm-knowledge-base | LLM 知识库 schema 标准 | 公开仓库 | 知识工程基础设施 | **P1** |
| 1.7 | genmedia-labs/skills | https://github.com/genmedia-labs/skills | SKILL.md 技能合集 | 公开 | 知识卡组织参照 | **P1** |
| 1.8 | michaelboeding/skills | https://github.com/michaelboeding/skills | 个人 SKILL.md 合集 | 公开 | 知识卡组织参照 | P2 |
| 1.9 | Diffbot Video Ontology | https://www.diffbot.com/docs/ontology/video | 商业知识图谱视频本体 | 商业（Diffbot） | schema 字段参照 | P2 |
| 1.10 | skillmd.ai「How to Build video-processing-editing Agent Skill」 | https://skillmd.ai/how-to-build/video-processing-editing/ | 教程/方法论 | 公开文档 | 知识卡构建方法 | P2 |

**要点与可移植建议：**
- **ClipSkills 是最值得深挖的样本**：其「总调度 + 12 册软件无关知识内核 + Palmier/代码栈/NLE 三路执行」的分层，本质就是「散文知识 → 可决策知识卡 → 可执行动作」的完整范式，与本项目「知识断层」治理目标同构。建议 clone 并拆解其知识卡的字段结构（元数据/前置条件/参数/执行步骤/校验）。
- **EBU SKOS 转场分类法**可直接作为「转场配方」知识卡的 `transition_type` 枚举取值来源，让字段值机器可校验，而非自由文本。
- **LottieFiles motion-design-skill** 的「timing / easing / choreography / 迪士尼十二原则」结构，是「风格化剪辑知识库」中「运动设计」子板块的现成 schema 蓝本。

---

## 2. 风格迁移与复刻

| # | 名称 | URL | 类型 | 许可/可用性 | 相关板块 | 评级 |
|---|------|-----|------|------------|---------|------|
| 2.1 | **spectral_film_lut** | https://github.com/JanLohse/spectral_film_lut | 开源工具（胶片仿真 LUT 生成） | MIT | 10-调色预设（胶片风格） | **P1** |
| 2.2 | **Video Color Grading via LUT Generation（ICCV 2025）** | https://github.com/seunghyuns98/VideoColorGrading | 论文 + 代码 | 公开，研究许可 | 10-调色预设（可学习 LUT） | **P1** |
| 2.3 | TeleStyle | https://github.com/Tele-AI/TeleStyle | 论文（视频风格迁移） | 公开，研究 | 风格迁移技术储备 | P2 |
| 2.4 | EchoStyle（HKUST） | https://github.com/HKUST-C4G/EchoStyle | 论文（视频风格化） | 公开，研究 | 风格迁移技术储备 | P2 |
| 2.5 | VISTA（Triplet-Supervised 风格迁移） | https://www.semanticscholar.org/paper/bbe9cadce3baceb090983bda935dcb7d3f4dc690 | 论文 | 公开 | 风格迁移技术储备 | P2 |
| 2.6 | Raw-Alchemy | https://github.com/shenmintao/Raw-Alchemy | 开源工具（RAW→LUT） | 公开 | 调色工具链 | P2 |

**要点：** 纯视频风格迁移（style transfer）研究论文多为 P2 存档级——它们解决的是「像素级风格化」，而本项目需要的是「可解释、可复现的剪辑配方」。真正可移植的是 **spectral_film_lut（数据驱动的胶片仿真）** 与 **ICCV2025 的可学习 LUT 生成**，二者都输出 `.cube` LUT，能直接沉淀为项目「调色预设」知识卡的可执行载荷。

---

## 3. 调色知识（色彩科学开源生态）

| # | 名称 | URL | 类型 | 许可/可用性 | 相关板块 | 评级 |
|---|------|-----|------|------------|---------|------|
| 3.1 | **colour-science/colour** | https://github.com/colour-science/colour | Python 色彩科学库 | BSD-3-Clause | 10-调色预设（计算后端） | **P1** |
| 3.2 | **OpenColorIO（ASWF）** | https://github.com/AcademySoftwareFoundation/OpenColorIO | 色彩管理框架 | BSD-3-Clause（ASWF） | 全板块（色彩管线） | **P1** |
| 3.3 | **mitkunz/resolve_DCTLs** | https://github.com/mitkunz/resolve_DCTLs | DCTL 合集（日常调色任务） | 公开 | 项目已有 `DCTLs` 目录 | **P1** |
| 3.4 | **free-DCTL** | https://github.com/bobtronic73/free-DCTL | DCTL 小工具合集 | 公开 | `DCTLs` 目录 | **P1** |
| 3.5 | jai-panjwani/DCTLS | https://github.com/jai-panjwani/DCTLS | DCTL 脚本 | 公开 | `DCTLs` 目录 | P2 |
| 3.6 | **LUT_SLM 数据集** | https://huggingface.co/datasets/ericrcwu/LUT_SLM | LUT 数据集（HF） | 公开数据集 | 10-调色预设（训练/评测数据） | **P1** |

**要点：** 项目已有 `DCTLs` 目录，建议直接对齐 **mitkunz/resolve_DCTLs** 的文件组织与注释规范（每个 DCTL 头部含用途/参数说明，天然是「可执行预设」）。**colour-science** 可作为「调色预设」知识卡里数值计算（色彩空间转换、ΔE 校验）的可靠后端，避免公式手抄出错。**OpenColorIO** 是全管线色彩一致性的行业事实标准，OCIO config 本身就是结构化 YAML——可作为「调色预设」的另一种机器可消费载体。

---

## 4. 特效/合成知识（Video Copilot 生态 & AE 脚本/表达式）

| # | 名称 | URL | 类型 | 许可/可用性 | 相关板块 | 评级 |
|---|------|-----|------|------------|---------|------|
| 4.1 | **after-effects-expression-reference** | https://github.com/docsforadobe/after-effects-expression-reference | 表达式参考（结构化文档） | 公开，社区维护 | 10 / 11 / 14（表达式知识卡） | **P0** |
| 4.2 | **Fx-Library** | https://github.com/hassaancode/Fx-Library | NLE 效果插件清单 | 公开 | 14-Silhouette（效果映射） | **P1** |
| 4.3 | Yan-K-ToolKit | https://github.com/Yan-K/Yan-K-ToolKit | AE 脚本合集 | 公开 | 10 / 14 | P2 |
| 4.4 | after-effects-expression-panel | https://github.com/azaynzxz/after-effects-expression-panel | AE 脚本面板（表达式/动画） | 公开 | 表达式知识卡 | P2 |
| 4.5 | Video Copilot 免费插件/脚本 roundup | https://www.toolfarm.com/news/freebies_video_copilot_freeafter_effects_plug_ins_templates_roundup/ | 免费插件清单 | 免费 | 11-大师（Andrew Kramer） | P2 |
| 4.6 | EF_After-Effects-Scriptlets | https://github.com/evefalcao/EF_After-Effects-Scriptlets | AE 小脚本合集 | 公开 | 10 / 14 | P2 |

**要点：** **docsforadobe/after-effects-expression-reference** 是「AE 表达式知识卡」的权威结构化数据源——表达式按功能分类、含参数与示例，可直接抽取为 JSON schema（`{name, category, signature, params, example, gotchas}`）。**Fx-Library** 提供 NLE 插件/效果的统一清单，是「效果映射」知识库（14-Silhouette 板块）的去重与命名规范化参照。

---

## 5. 动漫剪辑 / AMV / MAD 社区知识

| # | 名称 | URL | 类型 | 许可/可用性 | 相关板块 | 评级 |
|---|------|-----|------|------------|---------|------|
| 5.1 | **animemusicvideos.org「Three Rules of Three」** | https://www.animemusicvideos.org/forum/viewtopic.php?p=468058 | AMV 剪辑理论（社区经典） | 公开论坛 | 12-漫剪拉镜（方法论） | **P1** |
| 5.2 | 哔哩哔哩「文字排版 typography+拉镜」AMV 教程 | https://www.bilibili.com/video/BV1Fv411a7bC/ | 视频教程 | 公开 | 12-漫剪拉镜 | P2 |
| 5.3 | 哔哩哔哩「无缝衔接拉镜转场+shake」 | https://www.bilibili.com/video/BV14T4y1a7Lr/ | 视频教程 | 公开 | 12-漫剪拉镜 | P2 |
| 5.4 | 哔哩哔哩「缩放拉镜｜剪辑教学」 | https://www.bilibili.com/video/BV1JE421F7xo/ | 视频教程 | 公开 | 12-漫剪拉镜 | P2 |
| 5.5 | Skillshare「Premiere Pro AMV Beginner to Pro」 | https://www.skillshare.com/en/classes/premiere-pro-how-to-edit-anime-amv-from-beginner-to-pro/358039250 | 付费课程 | 付费 | 12 | P2 |

**要点与机会点：** 中文 AMV/漫剪社区（B站）知识几乎全部以「视频教程 + 散文专栏」形式存在，**机器可读的拉镜/卡点方法论数据库是全网空白**。本项目 12-漫剪拉镜板块若能产出「拉镜类型 → 关键帧参数 → 卡点锚定」的结构化配方，将是差异化产出。`animemusicvideos.org` 的「Three Rules of Three」等经典理论可作为方法论的语义骨架（节奏三拍、镜头三连等），值得人工提炼成结构化卡。

---

## 6. 3D / 骨骼动画知识

| # | 名称 | URL | 类型 | 许可/可用性 | 相关板块 | 评级 |
|---|------|-----|------|------------|---------|------|
| 6.1 | **jasongzy/Mixamo（HF 数据集）** | https://huggingface.co/datasets/jasongzy/Mixamo | 动作捕捉/动画数据集 | 公开数据集 | 15-3D 与骨骼动画 | **P1** |
| 6.2 | **RigMo-data（HF 数据集）** | https://huggingface.co/datasets/haoz19/RigMo-data | 3D rigging/骨骼数据集 | 公开数据集 | 15 | **P1** |
| 6.3 | CMU mocap（cmu-fbx 镜像） | https://huggingface.co/datasets/meitemouss0501-del/cmu-fbx | 动作捕捉数据集 | 公开 | 15 | P2 |
| 6.4 | 3DHuman_action_dataset（ModelScope） | https://modelscope.cn/datasets/iic/3DHuman_action_dataset | 人体动作数据集 | 公开 | 15 | P2 |
| 6.5 | **LSCherry Toon Shader Framework** | https://github.com/lvoxx/LSCherry | Blender 卡通渲染框架 | 公开 | 15（卡通渲染） | **P1** |
| 6.6 | npreevee（非真实感渲染） | https://github.com/kents00/npreevee | Blender NPR 渲染 | 公开 | 15 | P2 |
| 6.7 | 中文「Mixamo 替代 & Mocap 数据库」盘点 | https://www.chuangzaojia.com/hub/topic/show/1783 | 中文盘点文章 | 公开 | 15 | P2 |

**要点：** 骨骼动画数据已有多个现成 HF/ModelScope 数据集（**Mixamo 镜像、RigMo-data**）可直接用于「骨骼动画知识库」的训练/评测。卡通渲染方向 **LSCherry** 提供「跨卡通材质兼容」的 Blender 框架，是「动漫渲染配方」知识卡的执行后端候选。

---

## 7. LLM 时代知识工程最佳实践

| # | 名称 | URL | 类型 | 许可/可用性 | 相关板块 | 评级 |
|---|------|-----|------|------------|---------|------|
| 7.1 | **greennode「Distill, Don't Chunk and Vector」** | https://greennode.ai/tutorial/building-a-personal-llm-wiki-part-1-distill-dont-chunk-and-vector | 方法论（知识蒸馏） | 公开文章 | 知识工程顶层策略 | **P1** |
| 7.2 | **A-Mem: Agentic Memory for LLM Agents（NeurIPS 2025）** | https://papers.neurips.cc/paper_files/paper/2025/hash/19909c36f51abc4856b4560aff3d36d6-Abstract-Conference.html | 论文 | 公开 | 记忆/知识架构 | **P1** |
| 7.3 | **MemWeave（图+向量统一记忆）** | https://ieeexplore.ieee.org/document/11621567 | 论文 | 公开 | 记忆/知识架构 | P2 |
| 7.4 | Temporal-Stratified Retrieval（结构优先检索） | https://zenodo.org/records/19617135 | 论文 | 公开（Zenodo） | 检索策略 | P2 |
| 7.5 | **VideoRAG（KDD 2026）** | https://arxiv-org.ezproxy.obspm.fr/html/2502.01549v1 | 论文（视频 RAG） | 公开 | 视频域 RAG | **P1** |
| 7.6 | **VRAG-Bench（DISLab 评测基准）** | https://huggingface.co/datasets/DISLab/VRAG-Bench | 评测数据集 | 公开 | 视频 RAG 评测 | **P1** |
| 7.7 | Complex Knowledge Curation（Agentic Ontological Notebook） | https://dl.acm.org/doi/full/10.1145/3786335.3813226 | 论文 | 公开 | 本体化记忆 | P2 |

**要点与路线建议：**
1. **「蒸馏优先」是共识**：greennode 明确反对「无脑切块 + 向量化」，主张先让 LLM 把散文知识**蒸馏成结构化条目**再入库——这正是项目治理「散文式 md → 机器可消费」的正确方法论背书。
2. **走向「图 + 向量」混合**：A-Mem / MemWeave / Temporal-Stratified 共同指向「符号化结构（知识图）+ 语义向量」双轨，项目的「知识卡 schema + 枚举字段」天然构成图节点，后续可挂向量索引做模糊匹配。
3. **评测先行**：VideoRAG 与 VRAG-Bench 提供视频域 RAG 的可复用评测方法，可用于量化「207 个风格文件被管线读取」后的实际提升。

---

## 8. 可移植价值 Top 8（行动清单）

| 优先级 | 来源 | 落地动作 |
|-------|------|---------|
| P0 | ClipSkills | clone 拆解其「知识卡」字段结构，作为项目 10/11/12 知识卡 schema 的对照蓝本 |
| P0 | LottieFiles motion-design-skill | 抽取「运动设计原理」结构，补齐风格化库的「运动设计」子板块 |
| P0 | EBU SKOS 转场分类法 | 作为「转场配方」`transition_type` 字段的枚举取值来源 |
| P0 | after-effects-expression-reference | 抽取表达式 → JSON 知识卡（name/category/params/example） |
| P1 | colour-science + OpenColorIO + DCTL 合集 | 对齐项目 `DCTLs` 目录组织，用 colour-science 做预设数值校验 |
| P1 | LUT_SLM + ICCV2025 VideoColorGrading | 构建「调色预设」可执行载荷（.cube LUT）与评测数据 |
| P1 | Mixamo 镜像 + RigMo-data | 作为 15-骨骼动画板块的训练/评测数据集 |
| P1 | greennode「蒸馏优先」+ A-Mem | 定调知识工程路线：散文→蒸馏结构化→图+向量双轨 |

---

## 附：本次调研的搜索查询清单（23 条）

1. video editing knowledge graph structured data schema
2. motion design system github open source
3. after effects preset library open source github
4. video editing skill library LLM agent tool calling
5. agent skills markdown SKILL.md claude video editing
6. video style transfer editing 2026 method
7. cinematic LUT pack open source github free
8. colour-science python library OpenColorIO ecosystem github
9. DaVinci Resolve DCTL open source github collection
10. anime AMV style editing tutorial beat sync knowledge
11. color grading presets github LUT dataset
12. Video Copilot After Effects expression library open source collection
13. awesome after effects scripts expressions github
14. Mixamo alternative open source skeletal animation dataset
15. Blender toon shader anime rendering tutorial system github
16. knowledge base LLM structured schema best practice RAG
17. agent memory knowledge base design 2026 structured knowledge
18. RAG video domain knowledge base evaluation
19. 漫剪 AMV 卡点 剪辑 方法论 拉镜 运镜 教程 整理
20. machine readable preset json yaml after effects motion recipe
21. anime skeletal animation rigging dataset Live2D VRM open source
22. aescripts free after effects scripts github collection 2026
23. ontology video editing effects transitions machine readable
