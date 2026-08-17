# 审美与感知认知能力开源调研与集成决策

> Generated 2026-08-13 | Depth: standard(deep-research 流程) | Sources: 14 | 验证方式: GitHub REST API ×4 + 本地文件核查

## TL;DR

**impeccable 与 surreal-pop-collage 都不是视频剪辑项目**(前者是 AI 前端设计审美技能,后者是图像拼贴风格化 skill),但两者的**方法论**(确定性缺陷规则、品味契约、质量门)可移植为本项目的视频品味治理机制。真正值得集成的外部能力是三类:**视频审美评分**(DOVER,需先审许可证)、**运镜感知分类**(MovieShots/CameraBench,直接对症 v23 运镜同质化)、**镜头边界与语义标注**(PySceneDetect + BLIP-2,补齐感知地基)。同时确认两个重要事实:项目本地已存在完整的品味系统(`external/OpenMontage/skills/meta/taste-direction.md`)且未被消费;"审美分驱动剪辑选片"在开源界是空白,自建即差异化。

---

## 一、两个目标项目的身份核定

### 1. impeccable → `pbakaus/impeccable` [置信度: High,API 实测]

| 项 | 值 |
|---|---|
| URL | https://github.com/pbakaus/impeccable |
| Stars / Forks | 58,572 / 3,579 |
| 许可证 | **Apache-2.0** |
| 创建 / 最近 push | 2025-11-16 / 2026-08-12(极度活跃) |
| 官方描述 | "The design language that makes your AI harness better at design." |

**实质**:面向 AI 编程代理的前端设计审美技能——1 个 skill + 23 条命令(critique/audit/polish 等)+ 59 条确定性设计缺陷检测规则,目标是消除 AI 生成前端的"千篇一律审美"(Inter 字体、紫蓝渐变、卡片套卡片)。**与视频剪辑无直接关系** [1]。

**对本项目的价值(方法论移植,非代码集成)**:
- 其"确定性缺陷规则清单"模式 = 视频版 anti-default checklist 的现成范式
- 项目本地 `external/OpenMontage/skills/meta/taste-direction.md` 已有同构物:三旋钮品味契约(`visual_variance`/`motion_intensity`/`information_density`)+ Anti-Default Checklist + Review Hooks [14]
- **可执行动作**:把 taste-direction 的品味契约接入 v23 导演(当前导演完全没有品味契约输入),并用 impeccable 的规则化思路把 checklist 变成**可机检的规则**而非人读文档

### 2. surreal-pop-collage → `2998980-hue/surreal-pop-collage` [置信度: High,API 实测]

| 项 | 值 |
|---|---|
| URL | https://github.com/2998980-hue/surreal-pop-collage |
| Stars | 118(2026-08-08 创建,5 天涨到百星) |
| 许可证 | **MIT** |
| 实质 | 图像生成 agent skill:照片→超现实波普拼贴(黑白现实锚点+平涂色形+单一巨物) |

**实质**:零代码依赖的风格化生图 skill,核心价值在结构——「场景卡→色形推导→巨物选择→四段式 prompt 编译」+ **铁律 + 纠偏表 + 质量门** [2]。

**对本项目的价值(结构移植)**:
- 项目存在已确认的"知识断层":207 个风格化剪辑知识库文件未被任何管线程序化读取,`effect_registry.py`/`transition_rebuilder.py` 仍用硬编码映射
- surreal-pop-collage 的 SKILL.md 结构(**铁律=硬约束、纠偏表=失败模式映射、质量门=验收条件**)正是把这些 md 知识改造成机器可消费知识卡的模板
- **可执行动作**:选取 3-5 个高价值风格知识文件,按此 schema 重构为结构化知识卡试点

---

## 二、全管线薄弱点 → 能力缺口映射

| # | 薄弱点(已确证) | 缺的能力 | 开源供给情况 |
|---|---|---|---|
| W1 | 学习系统奖励常数化(quality 恒 68.5) | 视频级审美+技术实测评分 | DOVER 一枝独秀;VideoScore2 较新 |
| W2 | v23 运镜同质化(build 段全 pan_left) | 运镜感知分类(量化多样性) | CameraBench 分类法 + MovieShots 可训分类器 |
| W3 | 导演无内容感知(选材靠 HighlightScorer 局部特征) | 镜头边界 + 语义标签 | PySceneDetect(CPU)+ TransNetV2 + BLIP-2 captioning |
| W4 | 品味契约缺失(导演无风格输入) | 品味治理机制 | 本地 OpenMontage taste-direction 已有,**零外部依赖** |
| W5 | 207 知识文件断层 | 机器可消费知识卡 schema | surreal-pop-collage 结构模板(MIT) |
| W6 | 视频级情绪/氛围识别 | — | **开源空白**(现存的只有人脸 FER) |

---

## 三、候选开源项评估表

| 候选 | 功能 | Stars | 许可证 | 依赖 | 结论 |
|---|---|---|---|---|---|
| **DOVER**(VQAssessment)[3] | 视频级审美+技术双分支评分,ICCV2023;DOVER-Mobile 9.86M 参数可 CPU(1.4s/视频) | 520 | **S-Lab License 1.0(非商业 OK)** ✅ | PyTorch | ✅ **P0 可集成**(非商业用途);商业化需联系作者或降级 Apache 方案 |
| **VideoScore2**(TIGER-AI-Lab)[11] | 视频质量/美学打分,较新 | 未确认 | 未确认 | 待查 | P2 观察,作为 DOVER 备选 |
| **improved-aesthetic-predictor** [5] | 图像级美学分(CLIP+MLP),抽帧聚合可用 | 1.3k | **Apache-2.0** | CLIP 运行时 | P1:DOVER 许可不过关时的降级方案 |
| aesthetic-predictor-v2-5 [6] | 图像美学,对插画/动漫域改进 | 433 | **AGPL-3.0** ⚠️ | SigLIP+GPU | 不集成(传染性许可) |
| **PySceneDetect** [7] | 镜头边界检测,CPU 即可 | 成熟 | **BSD-3** | OpenCV | P1:切片地基 |
| TransNetV2 [8] | 深度镜头边界,软转场 F1 高 | 稳定期 | 未确认 | TF/PyTorch | P2:PySceneDetect 精度不足时再上 |
| BLIP-2 / mllm-video-captioner [9] | 关键帧语义标签 | 成熟 | Apache-2.0 | ~1GB 模型 | P1:配合已配置的 ModelScope 通道 |
| **CameraBench**(arXiv 2504.15376)[10] | 运镜原语分类法(与专业摄影师共建) | 论文 | 待查 | VLM | P1:**作为运镜词汇表标准**引入 |
| **MovieShots**(MovieNet 子集)[10] | 21,614 条运镜五分类标注 | 数据集 | 待查 | 可训轻量分类器 | P0:**直接对症 W2** |
| impeccable [1] | 前端设计审美技能 | 58.5k | Apache-2.0 | — | 方法论移植(见第一节) |
| surreal-pop-collage [2] | 拼贴风格化 skill | 118 | MIT | — | 结构移植(见第一节) |
| CutClaw(GVCLab)[4] | 音乐同步多智能体长视频剪辑,948 stars | 948 | **无许可证** ⚠️ | LiteLLM/scenedetect | **仅范式参考,禁复制代码** |
| AutoMV(M-A-P)[13] | 生成式 MV 多智能体 | 论文 | 未确认 | 扩散模型栈 | 不集成(生成范式与剪辑管线不同) |
| awesome-video-editing [12] | 剪辑风格迁移论文/数据集藏宝图(MovieCuts/VEU-Bench/Edit3K) | 索引 | — | — | 作为长期研究入口存档 |
| NVIDIA VSS Blueprint | VLM 视频理解代理 | 官方 | 企业级 | 数据中心 GPU+DeepStream | 不集成(过重) |

---

## 四、三档结论

### ✅ 建议集成(P0/P1)

1. **P0 — MovieShots 运镜分类器**(W2):用 MovieShots 五分类标注训轻量分类器,给导演素材库镜头打"推拉摇移"标签 → `camera_diversity_score` 从"自己数运镜字符串"升级为"对素材真实感知"。这是感知能力对编排质量的最直接杠杆。
2. **P0 — DOVER-Mobile 接入学习系统奖励**(W1,✅ 许可证已确认):S-Lab License 1.0 允许非商业用途使用,本项目可集成。替代 VMAF 作为无参考视觉质量主信号(学习系统计划 Task 9 的候选表已据此更新)。
3. **P1 — PySceneDetect + BLIP-2 语义层**(W3):BSD/CPU 零门槛垫高感知下限;BLIP-2 走已配置的 ModelScope 通道,给 HighlightScorer 补内容语义特征。
4. **P1 — 品味契约接入导演**(W4,零外部依赖):把本地 `taste-direction.md` 的三旋钮契约做成导演的输入参数(motion_intensity 直接映射运镜池选择策略),impeccable 式规则把 Anti-Default Checklist 机检化。
5. **P2 — 知识卡 schema 试点**(W5):按 surreal-pop-collage 结构重构 3-5 个风格知识文件。

### 🟡 可观察(暂不集成)

- **VideoScore2**:等 DOVER 许可证结论出来后对比;较新但信息不全
- **TransNetV2**:仅当 PySceneDetect 在漫剪软转场上精度不足时引入
- **CameraBench 微调 VLM**:成本高,先取其分类法作为词汇表标准即可
- **MovieCuts/VEU-Bench/Edit3K 数据集**:训练剪辑风格迁移模型的数据基础,属长期方向

### ❌ 明确不集成

| 项 | 理由 |
|---|---|
| CutClaw 代码 | 无许可证(法律风险)+ 4 个月未更新;**只读论文与架构范式**(其"先听音乐再决定剪哪里"的逆向流程与本项目 v23 方向一致,可作设计参照) |
| AutoMV | 生成式范式(扩散模型合成画面),与"剪辑既有动漫素材"的管线目标不同 |
| aesthetic-predictor-v2-5 | AGPL-3.0 传染性许可 |
| NVIDIA VSS | 数据中心级依赖,与离线/单机约束冲突 |
| 人脸 FER 类情绪识别 | 与"视频整体氛围情绪"不对口,开源该领域是空白 → 用已配置的 ModelScope VLM 自建标注,不引入 FER |

---

## 五、落地任务清单(与既有计划的衔接)

- [ ] **T1(先决)**:~~读取 DOVER 仓库 LICENSE 原文~~ ✅ 已完成(2026-08-13,S-Lab License 1.0,非商业 OK)
- [ ] **T2**:更新 `docs/plans/2026-08-13-learning-real-signals.md` Task 9 候选表——DOVER 许可证状态修正为 NOASSERTION,补 VideoScore2 与 Apache 降级路径
- [ ] **T3**:MovieShots 分类器训练与验证(验收:在 v23 素材库上运镜标签准确率 >80%,接入 `camera_diversity_score`)
  - **2026-08-14 更新**:发现**现成 VideoMAE-MovieShots 微调模型** (gullalc/videomae-base-finetuned-kinetics-movieshots-movement, MIT, acc 91.35%), 已下载 (329MB) 并在项目素材上验证通过 (推理 0.83s/视频)。T3 从"自训"简化为"集成现成模型 + 动漫域微调"。MovieShots 标注 47,463 条 (v1 33,653 + v2 606 + v3 13,204) 已下载至 `D:\AE-Data\MovieNet\MovieShots`, 统一 JSONL 已导出。详见 docs/research/2026-08-14-integration-candidates-v2.md
- [ ] **T4**:品味契约参数化——`production_director.py` 增加 `taste_profile` 输入,motion_intensity 映射运镜池;Anti-Default Checklist 前 3 条机检化
- [ ] **T5**:PySceneDetect 接入素材预处理(注册进 `integration_registry`,遵守三件套登记)
- [ ] **T6**:知识卡 schema 试点(3-5 个风格文件,产出 schema 规范文档)
- [ ] **T7**:把本调研登记进集成状态矩阵(复用既有能力机制)

优先级:T1 → T2(5 分钟)→ T4(与学习系统计划并行,零依赖)→ T3 → T5 → T6。

---

## 六、开放问题与注意事项

1. **动漫域迁移性存疑** [置信度: Medium]:DOVER/审美预测器训练集偏 UGC 与真人图像,对动漫赛璐璐画风的评分有效性需在 T3/T4 中用盲评校准(rhythm_reward 的 19/22 一致率方法是现成模板)。
2. **感知≠决策**:运镜分类器只提供信号,运镜同质化的根治仍在导演决策规则(运镜池轮换+重复惩罚)——感知模块是"眼睛",规则是"大脑",两者缺一不可。
3. **CutClaw 范式验证缺口**:其多智能体分工(编剧/剪辑师/审阅者)仅有二手描述,未读源码(无许可证禁止复制),若借鉴架构需读论文(arXiv 2603.29664,编号未经独立验证,标注 Low)。
4. **子代理 3 数据降级说明**:感知类项目数据来自 WebSearch 而非 GitHub 页面直读(当时 GitHub 限流),stars/许可证字段置信度 Medium,集成前按 T1 同款流程逐一核验。

---

## Methodology

deep-research 技能 standard 模式:Phase 0 澄清(用户确认:GitHub 自定位/全管线/集成决策方案)→ 3 个 Browser 检索代理并行(审美评分模型/目标项目定位/感知与品味系统)→ Phase 3 三角互验 → Phase 3.1 独立验证代理被取消,改由主代理用 GitHub REST API 直接核验 4 个最高影响论断(impeccable、surreal-pop-collage、DOVER、CutClaw 均 SUPPORTED,其中 **DOVER 许可证由"MIT"更正为 NOASSERTION**)→ Phase 4 红队批判 → Phase 5 落盘。报告存放位置遵循项目约定(docs/research/)而非技能默认的根目录。

## 参考文献

[1] pbakaus — impeccable — https://github.com/pbakaus/impeccable — Accessed 2026-08-13 — Tier 1(API 实测:58572 stars, Apache-2.0)
[2] 2998980-hue — surreal-pop-collage — https://github.com/2998980-hue/surreal-pop-collage — Accessed 2026-08-13 — Tier 1(API 实测:118 stars, MIT, 创建 2026-08-08)
[3] VQAssessment — DOVER (ICCV 2023 Official) — https://github.com/VQAssessment/DOVER — Accessed 2026-08-13 — Tier 1(API 实测:520 stars, 许可证 NOASSERTION)
[4] GVCLab — CutClaw: Agentic Hours-Long Video Editing via Music Synchronization — https://github.com/GVCLab/CutClaw — Accessed 2026-08-13 — Tier 1(API 实测:948 stars, license=null, 最后 push 2026-04-17)
[5] christophschuhmann — improved-aesthetic-predictor — https://github.com/christophschuhmann/improved-aesthetic-predictor — Tier 2(GitHub 页面直读:1.3k stars, Apache-2.0)
[6] discus0434 — aesthetic-predictor-v2-5 — https://github.com/discus0434/aesthetic-predictor-v2-5 — Tier 2(页面直读:433 stars, AGPL-3.0)
[7] Breakthrough — PySceneDetect — https://github.com/Breakthrough/PySceneDetect — Tier 2(WebSearch:BSD-3, CPU, v0.6.4)
[8] soCzech — TransNetV2 — https://github.com/soCzech/TransNetV2 — Tier 2(WebSearch:F1 77.9/ClipShots, 96.2/BBC)
[9] salesforce/BLIP-2; chunhuizng — mllm-video-captioner (arXiv 2502.13363) — Tier 2(WebSearch)
[10] CameraBench — Towards Understanding Camera Motions in Any Video — arXiv 2504.15376;MovieShots(MovieNet 运镜子集,21,614 条五分类) — Tier 2(WebSearch)
[11] TIGER-AI-Lab — VideoScore2 — https://github.com/orgs/TIGER-AI-Lab — Tier 3(WebSearch,细节未确认)
[12] wentianli — awesome-video-editing — https://github.com/wentianli/awesome-video-editing — Tier 2(WebSearch:收录 MovieCuts/VEU-Bench/Edit3K)
[13] multimodal-art-projection — AutoMV (arXiv 2512.12196) — Tier 3(WebSearch)
[14] 本地文件 — external/OpenMontage/skills/meta/taste-direction.md(127 行品味契约技能,随 OpenMontage 集成引入) — Tier 1(本地实证)
