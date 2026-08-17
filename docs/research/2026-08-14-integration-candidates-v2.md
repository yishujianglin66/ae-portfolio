# 管线强化：可集成候选清单 v2 (技能 / 工具 / 插件 / 开源项目 / 数据集)

> 2026-08-14 | 在 2026-08-13 审美感知调研基础上的第二轮候选核验
> 背景: 用户问"根据我的项目，还有什么可以集成的技能、工具、插件或开源项目、数据集能优化/强化项目性能"
> 方法: 结合项目已确认缺口 (W1-W6) + 本地已有资产盘查 + Web 核验 (HF API 实测为主)

## TL;DR — 本轮新确认的 6 个高价值候选

| # | 候选 | 类型 | 对症缺口 | 许可证/成本 | 结论 |
|---|---|---|---|---|---|
| 1 | **VideoMAE-MovieShots 微调模型** (gullalc) | 预训练模型 | W2 运镜同质化 | MIT, 免费下载 | ✅ **P0 直接集成** (Step 3 现成基线, 91.35% acc) |
| 2 | **CameraBench 数据集** (syCen/CameraBench) | 数据集 | W2 运镜词汇表 | HF 免费, 许可见仓库 | ✅ P1 (运镜 taxonomy + 评测集) |
| 3 | **AutoShot 数据集** (wentaozhu/AutoShot) | 数据集 | W3 镜头边界 | CVPR NAS 2023 | ✅ P1 (短视频切点, 比 TransNetV2 更贴 B 站域) |
| 4 | **AutoMatch 卡点基准** (arXiv 2303.01884) | 数据集+方法 | 卡点对齐 | 论文公开 | ✅ P2 (卡点质量评估基准化) |
| 5 | **AnimeShooter 数据集** (qiulu66) | 数据集 | W6/Step 4 动漫域 | CC BY-NC 4.0 | ✅ P1 (Step 4 素材源) |
| 6 | **deepghs/anime_classification** | 预训练模型 | 动漫内容理解 | MIT | ✅ P1 (动漫帧标签, 补 HighlightScorer) |

另确认: **DOVER**(W1 视频审美, S-Lab 许可) 保持 P0; **beat-synced-edit**(卡点 CLI) 等一批
社区工具作为设计参照, 不引入代码。

---

## 一、W1-W6 缺口与候选映射总表 (v2)

| 缺口 | 已有方案 (v1) | v2 新增候选 | 变化 |
|---|---|---|---|
| W1 奖励常数化 | DOVER / improved-aesthetic-predictor | — | 不变 (DOVER P0) |
| W2 运镜同质化 | MovieShots 自训分类器 | **VideoMAE 微调模型现成** + CameraBench | ⭐ 重大简化 |
| W3 镜头边界+语义 | PySceneDetect + BLIP-2 | **AutoShot 数据集** | 补充训练数据 |
| W4 品味契约 | taste-direction 接入 | — | 不变 |
| W5 知识断层 | 知识卡 schema | — | 不变 |
| W6 视频级情绪 | VLM 自建标注 | **AnimeShooter** (镜头级素材) | 补充 |

---

## 二、⭐ P0 重大发现: VideoMAE-MovieShots 运镜模型已现成

### 2.1 三个现成模型 (HF, MIT 许可)

| 模型 | 任务 | 指标 |
|---|---|---|
| [videomae-base-finetuned-kinetics-movieshots-movement](https://huggingface.co/gullalc/videomae-base-finetuned-kinetics-movieshots-movement) | 运镜 5 类 (Static/Motion/Pull/Push/…) | acc **91.35%**, macro-F1 79.37%; 类级: Static 92.94% / Motion 91.7% / Pull 51.25% / Push 62.73% |
| videomae-base-finetuned-kinetics-movieshots-scale | 景别 5 类 | 同体系 |
| videomae-base-finetuned-kinetics-movieshots-multitask | 运镜+景别多任务 | 同体系 |

### 2.2 对项目的意义

1. **Step 3 从"训练"变成"集成+验证"**: 不再需要自己下载 16.9GB 视频训练,
   直接加载模型在项目动漫素材上验证 (pull/push 类 51-62% 偏低, 动漫域可能更低,
   正好作为迁移学习的起点)。
2. **用法**: `transformers.VideoMAEForVideoClassification` + 16 帧采样,
   RTX 4060 8GB 单镜头推理 ~0.1-0.3s, 完全可在线路里跑。
3. **配合 Step 4**: 动漫域自建数据微调该模型 (VideoMAE 迁移), 比从零训 MLP 强得多。
4. **保留光流规则做兜底**: 分类器置信度低时回退现有规则 (与 ai/camera_decision.py
   的降级逻辑一致)。

### 2.3 建议接入路径

```
V1 (本周): 加载现成模型 → 在 data/real_amv_test 与 v23 素材库上跑通验证
V2 (Step 4 后): 用自建动漫数据对 VideoMAE 做 LoRA 微调 (8GB 可跑)
V3: 接入 SourceCameraInventory.inject() 输出标签 → camera_diversity_score
```

---

## 三、P1 候选详解

### 3.1 CameraBench (W2 运镜词汇表标准)

- [HF syCen/CameraBench](https://huggingface.co/datasets/syCen/CameraBench) (test.jsonl 403KB + videos.csv + videos_gif)
- 价值: 运镜原语分类法 (与专业摄影师共建) 作为**项目运镜词汇表校准**,
  与 MovieShots 粗类互补; 不直接训练 (VLM 微调成本高, 维持 v1 结论)。

### 3.2 AutoShot 数据集 (W3 镜头边界)

- [GitHub wentaozhu/AutoShot](https://github.com/wentaozhu/AutoShot) (CVPR NAS 2023)
- 价值: **短视频**镜头边界数据集 + SOTA 方法。项目素材是 B 站动漫 (短视频域),
  TransNetV2 在电影/软转场上强, 短视频硬切/闪帧场景 AutoShot 更贴。
- 用途: 评估 TransNetV2 在 B 站域的精度, 或作为补充训练/微调数据。

### 3.3 AnimeShooter (W6/Step 4 素材源)

- [HF qiulu66/AnimeShooter](https://huggingface.co/datasets/qiulu66/AnimeShooter) (CC BY-NC 4.0, 学术)
- 价值: 多镜头动画数据集 (2025), 镜头级组织, 直接作 Step 4 自建数据的
  **镜头边界+视频素材源** (无运镜标签, 需自标, 但省去切镜头工作)。

### 3.4 deepghs/anime_classification (动漫内容理解)

- [HF deepghs/anime_classification](https://huggingface.co/deepghs/anime_classification) (MIT)
- 价值: 动漫图像分类模型 (题材/风格标签), 给素材打"动漫内容标签",
  补 HighlightScorer 的内容语义特征 (W3 相关)。

---

## 四、P2 观察项

| 候选 | 类型 | 价值 | 暂缓原因 |
|---|---|---|---|
| [AutoMatch](https://ar5iv.labs.arxiv.org/html/2303.01884) (arXiv 2303.01884) | 卡点基准 | 卡点质量评估基准化, 补 rhythm_reward 的对照 | 数据需向作者申请, 先读方法 |
| beat-synced-edit (GitHub) | 卡点 CLI | 纯 Python/ffmpeg 卡点剪辑范式 | 与项目已有节奏管线重叠, 仅范式参照 |
| AutoShot 模型权重 | 切点模型 | 短视频域切点 SOTA | 先评估 TransNetV2 在 B 站域差距 |
| Video-RAG / MobileViCLIP | 视频理解 | 长视频检索/移动端视频文本 | 与现有 VLM 方案重叠, 成本高 |
| RIFE 插帧 (external/rife 已本地化) | 工具 | 补帧增强已具备 | 已集成, 维持 |
| Demucs / UVR5 人声分离 | 音频工具 | 分离人声/伴奏做卡点或混音 | 漫剪卡点基于鼓点/onset, 人声分离增益有限; 需要时再评估 (set-soft/AudioSeparation 可作 CLI) |
| Real-ESRGAN animevideov3 | 超分模型 | 动漫超分已接入 frame_enhancement_pipeline.py | ✅ 已集成 (含 Topaz 回退), 维持 |
| 视频级情绪识别 (多模态 FER 系) | 模型 | W6 缺口 | 公开项全是人脸/多模态, 与"视频整体氛围"不对口; 维持"VLM 自建标注"结论 |

## 五、本地资产盘查 (已就绪, 勿重复引入)

`external/` 下已本地化: rife (补帧)、ComfyUI、nexrender (AE 渲染)、
MediaCrawler (采集)、auto-subs (字幕)、BlenderProc、DCTLs (达芬奇)、
多个 PR/AE/Resolve MCP 桥。`.trae/rules/` 有 4 条工作流规则。
`frame_enhancement_pipeline.py` 已含 RIFE 补帧 + Real-ESRGAN/Topaz 超分全链路。

**结论**: 项目不缺"工具地基", 缺的是**感知模型权重** (W2/W6) 与**数据** (Step 3/4)——
本轮确认 VideoMAE 模型现成 + 4 个数据集可用, 是性价比最高的强化路径。

---

## 六、行动清单 (按优先级)

- [x] **A1 (P0) ✅ 2026-08-14**: 下载 VideoMAE-MovieShots movement 模型 (329MB, MIT) → **已在项目素材验证通过**:
  - 58 个 B 站 AMV 素材全部推理成功 (0 错误), 平均 0.33s/视频 (RTX 4060)
  - 结果分布: Motion 38 / Static 20 (符合动漫 AMV 动态为主特性)
  - 验证脚本: `models/verify_movieshots_videomae.py`, 输出 `models/output/videomae_verify.json`
  - 局限: 4 类标签 (Static/Motion/Pull/Push), 无 pan/tilt 方向细分; Pull/Push 类原始 acc 51-63%, 动漫域需微调
- [x] **A2 (P0) ✅ 2026-08-14**: 更新 Step 3 方案 → `docs/plans/2026-08-14-step3-movieshots-videomae.md` (主路径=现成 VideoMAE, 微调=动漫 LoRA, 兜底=光流 MLP)
- [x] **A3 (P1) ✅ 2026-08-14**: CameraBench 已下载+校准 → `core/camera_vocabulary.py` (34 原语/4 维度 → 项目 13 类映射) + `docs/research/2026-08-14-camerabench-vocabulary.md`, 单测 13/13
- [x] **A4 (P1) ✅ 2026-08-14**: AutoShot/SHOT 评估 TransNetV2 → `scripts/eval_transnetv2_bilibili.py` + `docs/research/2026-08-14-autoshot-transnetv2-eval.md`; 关键发现: TransNetV2 短视频域 recall 仅 0.716 (漏硬切), 已把 `core/temporal_analyzer.py` 阈值 0.5→0.3 (与 ae/ai_scene_detector 对齐)
- [x] **A5 (P1) ✅ 2026-08-14**: AnimeShooter 镜头级素材源适配器 → `models/data/animeshooter_dataset.py` + `tests/test_animeshooter_dataset.py` (单测 5/5); 视频下载+VLM 标注见 Step 4 A1-A3
- [x] **A6 (P1) ✅ 2026-08-14**: deepghs/anime_classification 已下载+接入 → `scripts/tag_anime_content.py` + `docs/research/2026-08-14-anime-classification-tagger.md`; 58 素材打标: bangumi 20 / not_painting 20 / illustration 8 / 3d 7 / comic 3
- [x] **A7 ✅ 2026-08-14**: 6 候选登记进 data/capability_registry.json (datasets: movieshots/animeshooter/camerabench/autoshot; pretrained_models: videomae_movieshots_movement/deepghs_anime_classification)

## 参考文献

[1] gullalc — VideoMAE MovieShots 微调模型 (movement/scale/multitask) — HF API 实测 (2026-08-14, MIT, movement acc 91.35%)
[2] syCen/CameraBench — HF API 实测 (test.jsonl 403KB + videos.csv)
[3] wentaozhu/AutoShot — CVPR NAS 2023, GitHub (2026-08-14 WebSearch)
[4] AutoMatch — arXiv 2303.01884 (2026-08-14 WebSearch)
[5] qiulu66/AnimeShooter — HF (CC BY-NC 4.0) + arXiv 2506.03126 (2026-08-14 WebSearch)
[6] deepghs/anime_classification — HF API 实测 (MIT, 21 likes)
[7] ZiadAbdelkarim/beat-synced-edit — GitHub (2026-08-14 WebSearch)
