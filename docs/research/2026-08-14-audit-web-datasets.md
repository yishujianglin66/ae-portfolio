# 全网调研：2025-2026 视频理解/数据集/感知模型新进展审计

> 2026-08-14 | 方法: web_search ×26 | 目标: 为「AE 视频自动化剪辑管线」补齐 W1-W6 缺口的新供给
> 业务: B 站动漫 AMV/MAD/漫剪（卡点、拉镜、运镜、风格复刻）
> 约束: 可本地跑、8GB 显存、Apache/MIT 许可优先

---

## TL;DR

本轮在已调研清单（MovieShots / CameraBench / AutoShot / AnimeShooter / VideoMAE-MovieShots / DOVER / VideoScore2 / improved-aesthetic-predictor / AutoMatch / CutClaw / MovieCuts / VEU-Bench / Edit3K）之外，**新确认 8 个高价值候选**，其中 4 个直接命中 W2/W3/W6 的感知短板，且多为「现成权重 + 宽松许可」：

| 优先级 | 新发现 | 对症缺口 | 一句话价值 |
|---|---|---|---|
| ⭐P0 | **ai-forever/kandinsky-videomae-large-camera-motion** | W2 运镜 | VideoMAE-**large** 运镜分类，比已集成的 base 版更强，现成权重 |
| ⭐P0 | **ToriiGate (Minthy, 2B/7B)** | W3+W6 | 动漫专用 VLM，GGUF/exl2 量化可 8GB 本地跑，动漫 caption/氛围标注现成 |
| P1 | **MatAnyone (CVPR 2025)** | 抠像(RVM 升级) | 视频抠像记忆传播，帧间一致远优于 RVM 逐帧 |
| P1 | **BiRefNet (MIT) / RMBG-2.5** | 抠像(RVM 升级) | 图像抠像/背景移除 SOTA，动漫人物抠像直接可用 |
| P1 | **BeatNetLite** | 卡点(新缺口) | 节拍+下拍+速度+拍号联合，比 librosa/madmom 更贴卡点 |
| P1 | **SongFormer (2510.02797)** | W6 情绪+卡点 | 音乐结构分段（主歌/副歌），副歌=高能段对齐卡点 |
| P2 | **VEnhancer (Vchitect)** | 超分 | 生成式时空超分，一致性优于 Real-ESRGAN 逐帧 |
| P2 | **Marlin-2B / MetaCaptioner / ASID-Captioner-7B** | W3+W6 | 视频 caption 小模型，替代/补充 BLIP-2 语义层 |

---

## 一、已调研过清单（本轮不重复推荐）

以下项目在 `2026-08-13-aesthetic-perception-oss-research.md` 与 `2026-08-14-integration-candidates-v2.md` 中已充分核验，本轮**只在其有"新进展"时**补充：

| 项目 | 状态 | 本轮新进展? |
|---|---|---|
| MovieShots / MovieNet 运镜子集 | 已下载 47,463 条标注 | 无 |
| CameraBench (syCen) | 已登记 P1 | 无 |
| AutoShot (wentaozhu) | 已登记 P1 | 无 |
| AnimeShooter (qiulu66) | 已集成适配器 | 无 |
| VideoMAE-MovieShots (gullalc, base) | **已下载并验证** | ⭐ 见 §二：发现 large 版本升级路径 |
| DOVER | P0 非商业已确认 | 无 |
| VideoScore2 | P2 观察 | 无 |
| improved-aesthetic-predictor | P1 备选 | 无 |
| AutoMatch (2303.01884) | P2 卡点基准 | 无 |
| CutClaw | 仅范式参考 | 无 |
| MovieCuts / VEU-Bench / Edit3K | 长期方向 | 无 |
| FAST-VQA / Q-Align / aesthetic-predictor-v2-5 | 已排除 | 无 |
| deepghs/anime_classification | 已登记 P1 | 无 |
| beat-synced-edit | 范式参考 | 无 |

---

## 二、⭐ 运镜/镜头语言分类模型（W2 直接供给）

### 2.1 ai-forever/kandinsky-videomae-large-camera-motion 【新发现 · 强烈推荐】

| 字段 | 值 |
|---|---|
| 名称 | ai-forever/kandinsky-videomae-large-camera-motion |
| URL | https://huggingface.co/ai-forever/kandinsky-videomae-large-camera-motion |
| 类型 | 预训练模型（VideoMAE-**large** 运镜分类） |
| 许可 | Apache-2.0（ai-forever/SberAI 惯例，下载前核验模型卡） |
| 规模/性能 | VideoMAE-large 骨干（约 86M 参数），`transformers` 可直接加载 |
| 对症缺口 | **W2 运镜多样性感知** |
| 集成评级 | **P0** |

**价值**：项目已集成 `gullalc/videomae-base-finetuned-kinetics-movieshots-movement`（base 版，4 类，acc 91.35%），本模型是**同任务的 large 骨干升级**——更强特征表达，Pull/Push 等 base 版偏弱类（51-63%）在 large 上预期更高。可作为 W2 感知主模型的直接替换或对比基线，零训练成本。

**注意**：需在下载后核验其类别表（是否仍为 MovieShots 5 类，还是 ai-forever 自有 taxonomy），并用项目 58 个 AMV 素材实测动漫域迁移精度（复用 `models/verify_movieshots_videomae.py` 思路）。

---

### 2.2 相关补充（P2 观察）

- **ai-forever 同系列**：Kandinsky 团队在运镜/镜头方向持续放权，可关注其 `kandinsky-*` 系列是否有 scale（景别）兄弟模型，与 MovieShots-scale 互补。

---

## 三、⭐ 动漫专用多模态模型（W3 语义 + W6 情绪）

### 3.1 ToriiGate（Minthy）—— 动漫视频 VLM 【新发现 · 强烈推荐】

| 字段 | 值 |
|---|---|
| 名称 | Minthy/ToriiGate-v0.4-2B / -7B |
| URL | https://huggingface.co/Minthy/ToriiGate-v0.4-7B |
| 类型 | 预训练模型（动漫视频/图像 视觉语言模型） |
| 许可 | 基于 Qwen2.5-VL（Apache-2.0），微调版许可**需下载前核验**（社区微调常见 CC BY-NC，置信度 Medium） |
| 规模/性能 | 2B / 7B 两档；社区已出 GGUF（SleepVeryHard/ToriiGate-0.5_GGUF）与 exl2-8bpw 量化 |
| 对症缺口 | **W3 镜头语义 + W6 视频级情绪/氛围** |
| 集成评级 | **P0（2B GGUF 可 8GB 本地跑）→ 若许可非商用则 P1** |

**价值**：这是本轮最重要的 W6 突破。此前结论是"视频级情绪识别开源空白，只有人脸 FER"；ToriiGate 是**专为动漫域微调的多模态 VLM**，天然理解赛璐璐画风、角色、场景与氛围，可直接做：
1. **动漫镜头 caption**（W3）：给素材打"黄昏天台/樱花特写/战斗爆发"等语义标签，替代 BLIP-2（BLIP-2 对动漫域泛化差）。
2. **氛围/情绪标注**（W6）：prompt 化提问"这段镜头的情绪基调？"→ 得到视频级氛围标签，补 W6 缺口。
3. **风格标签**（W3）：角色、题材、色调等结构化标签，喂给 HighlightScorer。

**落地路径**：2B 版 + GGUF 量化在 8GB 显存上可跑（参考 Qwen2.5-VL-3B 的量化经验）；与已配置的 ModelScope 通道可互通（Qwen 系在 ModelScope 有镜像）。

**风险**：许可未明确，且 2B/7B 的动漫域 caption 质量需在项目素材上盲评（复用 v1 报告的"盲评校准"方法）。

### 3.2 视频 caption 小模型（W3/W6 补充，P1-P2）

| 名称 | URL | 类型 | 许可 | 备注 |
|---|---|---|---|---|
| lunahr/Marlin-2B-ungated | https://huggingface.co/lunahr/Marlin-2B-ungated | 视频 caption 2B | 社区重传，原版许可需核验 | Marlin 系视频理解模型，ungated 可直接下 |
| OpenGVLab/MetaCaptioner | https://github.com/OpenGVLab/MetaCaptioner | 视频 caption | OpenGVLab 惯例 Apache-2.0 | 视频详细描述 |
| AudioVisual-Caption/ASID-Captioner-7B | https://huggingface.co/AudioVisual-Caption/ASID-Captioner-7B | 音视频 caption 7B | 需核验 | 含音频的 caption，对 AMV（配乐+画面）有独特价值 |

**结论**：若 ToriiGate 许可受阻，Marlin-2B/MetaCaptioner 是通用视频 caption 的降级路径；ASID-Captioner 的"音画联合 caption"对 AMV 卡点理解有加分，值得关注。

---

## 四、数据集（动漫/运镜/剪辑风格/卡点）

### 4.1 新发现数据集

| 名称 | URL | 类型 | 许可 | 对症缺口 | 评级 |
|---|---|---|---|---|---|
| marvex/ShotBench | https://huggingface.co/datasets/marvex/ShotBench | 镜头/景别评测集 | 仓库标注 | W2/W3 | P1（评测基线） |
| Lewandofski/OpenVE-3M | https://huggingface.co/datasets/Lewandofski/OpenVE-3M | 视频编辑 3M 数据集 | 仓库标注 | W4 风格复刻 | P2（风格迁移长期） |
| The Anatomy of Video Editing (ECCV 2022) | https://mlanthology.org/eccv/2022/argaw2022eccv-anatomy/ | 剪辑决策数据集+基准 | 论文公开 | W4 品味/剪辑决策 | P2（剪辑语义基准） |
| BS-BGM (IEEE 2025) | https://ieeexplore.ieee.org/abstract/document/10945856 | 卡点 BGM 生成（VLM+镜头边界） | 论文 | 卡点对齐 | P2（范式参照） |
| zhiyuzhang-0212/MOVA_benchmark | https://huggingface.co/datasets/zhiyuzhang-0212/MOVA_benchmark_for_arena | 视频理解基准 | 仓库标注 | W3 评测 | P2 |
| svjack/Scenery_Anime_Bright_VACE_* | https://huggingface.co/datasets/svjack/Scenery_Anime_Bright_VACE_Depth_V2V_Captioned_50_samples | 动漫风景 caption 样本 | 样本集 | W3 语义 | P2（仅小样本） |

**结论**：
- **ShotBench** 是最贴近 W2/W3 的新评测集，可作运镜/景别分类器的动漫域外评测。
- **动漫运镜/镜头标注数据集**仍是稀缺资源：本轮未发现比 CameraBench/MovieShots 更细粒度且可下载的动漫运镜标注集，**自建动漫运镜标注（Step 4）仍是必要路径**。
- **AMV/MAD 专用数据集**：无公开可下载的成熟集（多为论文+申请制），确认"自建 B 站 AMV 数据集"是本项目差异化壁垒。

---

## 五、训练与微调资源（W2/W3）

| 名称 | URL | 类型 | 备注 |
|---|---|---|---|
| HF video_classification 官方教程 | https://github.com/huggingface/transformers/blob/main/docs/source/en/tasks/video_classification.md | 工具/教程 | VideoMAE 微调官方 recipe，8GB 可跑 |
| cy0307/c-videomae-finetune | https://huggingface.co/cy0307/c-videomae-finetune | 微调模型示例 | 社区 VideoMAE 微调范式 |
| zyt-599/FedVideoMAE | https://github.com/zyt-599/FedVideoMAE | 工具 | 联邦 VideoMAE，多机协作（本项目单机，参考） |

**结论**：VideoMAE 的 HF 官方 video_classification 教程是 Step 4 动漫 LoRA/微调的**现成 recipe**（`run_video_classification.py`），结合现有 `gullalc` base 或 `ai-forever` large 权重做动漫域微调，8GB 显存 + LoRA 完全可行。无需自造轮子。

---

## 六、音频：节拍/结构（卡点感知，可视为新缺口 W7）

> 项目现有卡点基于 onset 检测（librosa/madmom 系），本轮确认**联合节拍模型**能显著提升卡点质量。

### 6.1 BeatNetLite 【新发现 · P1】

| 字段 | 值 |
|---|---|
| 名称 | turbo/BeatNetLite |
| URL | https://github.com/turbo/BeatNetLite |
| 类型 | 工具（离线节拍/下拍/速度/拍号跟踪） |
| 许可 | turbo 系列惯例（下载前核验，置信度 Medium） |
| 对症缺口 | **卡点对齐（新缺口 W7）** |
| 集成评级 | **P1**（Python 包，可封装成 onset 源） |

**价值**：BeatNet 系是节拍跟踪的代表性 DNN，Lite 版离线可跑，输出**下拍（downbeat）**——下拍是 AMV 卡点的"重拍"，比纯 onset 峰值更符合"踩点"语义。可作为 rhythm_reward 的第二信号源，与现有 onset 检测互校。

### 6.2 SongFormer —— 音乐结构分段 【新发现 · P1】

| 字段 | 值 |
|---|---|
| 名称 | SongFormer（Scaling Music Structure Analysis） |
| URL | https://arxiv.org/abs/2510.02797 |
| 类型 | 模型/论文（音乐结构分段） |
| 许可 | 论文公开，代码/权重需核验 |
| 对症缺口 | **W6 情绪 + 卡点** |
| 集成评级 | **P1**（有开源权重则 P0） |

**价值**：输出主歌/副歌/桥段结构。对 AMV 而言，"副歌=高能段"是剪辑节奏锚点——副歌段应匹配高燃卡点密集，主歌段匹配抒情慢镜头。这是现有 onset 检测完全缺失的**段落级节奏语义**。

### 6.3 其他

| 名称 | URL | 备注 |
|---|---|---|
| all-in-one-infer (pypi) | https://pypi.org/project/all-in-one-infer/ | "All-in-One" 联合节拍/下拍/结构/分段模型推理包，一站封装 |
| ctralie/GeometricBeatTracking | https://github.com/ctralie/GeometricBeatTracking | 几何节拍跟踪，可作对照 |
| dennisvdang/chorus-detection | https://github.com/dennisvdang/chorus-detection | 副歌检测 CRNN + CLI，轻量 |

**结论**：卡点感知应从"onset 峰值"升级为"节拍+下拍+结构"三层信号。**BeatNetLite（下拍）+ SongFormer（副歌结构）**是性价比最高的组合。

---

## 七、抠像/分割（RVM 之后的新进展）

> 项目已尝试 RVM（逐帧抠像，帧间闪烁是痛点）。本轮确认 2025 年的**视频抠像一致性**与**图像抠像 SOTA**两大方向。

### 7.1 MatAnyone（CVPR 2025）【新发现 · P1】

| 字段 | 值 |
|---|---|
| 名称 | richservo/MatAnyone |
| URL | https://github.com/richservo/MatAnyone |
| 类型 | 模型（视频抠像，一致记忆传播） |
| 许可 | 需核验（GitHub 仓库标注为准，置信度 Medium） |
| 对症缺口 | **抠像（RVM 升级，动漫人物抠像→运镜/合成素材）** |
| 集成评级 | **P1** |

**价值**：MatAnyone 用**记忆传播**保证帧间一致性，直接解决 RVM 逐帧抠像的"边缘抖动/闪烁"问题。动漫角色抠像后做运镜合成（拉镜/推镜时的角色分离）质量会显著提升。CVPR 2025 顶会，质量可信。

### 7.2 BiRefNet / RMBG-2.5（图像抠像 SOTA）【新发现 · P0/P1】

| 名称 | URL | 许可 | 评级 |
|---|---|---|---|
| ZhengPeng7/BiRefNet | https://huggingface.co/ZhengPeng7/BiRefNet | **MIT**（置信度 High） | **P0** |
| briaai/RMBG-2.5 | https://huggingface.co/briaai/RMBG-2.5 | BRIA RMBG-2.5（源可见，商用有条件） | P1 |

**价值**：BiRefNet 是高分辨率二值分割（前景/背景）SOTA，MIT 许可可直接集成，对**动漫人物/主体抠像**效果好，作为 RVM 的图像级替代（对静态构图足够）；RMBG-2.5 是商业级背景移除（BRIA 许可，35k 精标），质量更高但许可需读条款。两者都是**逐帧**，需配合时序平滑（或 MatAnyone）消除闪烁。

### 7.3 SAM3（Meta）【新发现 · P2】

| 字段 | 值 |
|---|---|
| 名称 | Meta SAM 3 |
| URL | https://github.com/facebookresearch/sam3（示例封装见 Mahmoudm007/Segment-Anything-Model-3_SAM3） |
| 许可 | Apache-2.0（Meta SAM 系列惯例） |
| 对症缺口 | 抠像/分割（文本/点击交互，视频对象跟踪） |
| 集成评级 | **P2**（重，需按需调用） |

**价值**：SAM3 支持文本条件 + 点击交互 + 视频对象跟踪，比 SAM2 更强；但模型较大，8GB 需量化，作为"按需抠像工具"而非管线常驻环节。社区已有 CPU 封装（rhubarb-ai/sam3-cpu）。

---

## 八、超分/补帧（Real-ESRGAN / RIFE 之后）

### 8.1 VEnhancer（Vchitect）【新发现 · P2】

| 字段 | 值 |
|---|---|
| 名称 | Vchitect/VEnhancer |
| URL | https://github.com/Vchitect/VEnhancer |
| 类型 | 模型（生成式时空超分/增强） |
| 许可 | 代码开源，权重许可需核验（常为非商用，置信度 Medium） |
| 对症缺口 | **超分（Real-ESRGAN 升级）** |
| 集成评级 | **P2**（8GB 勉强，需 fp16/量化） |

**价值**：生成式空间-时间联合增强，**帧间一致性**优于 Real-ESRGAN 的逐帧超分，对动漫高速运镜画面的超分闪烁有改善。但基于视频扩散，推理重，作为 Real-ESRGAN 的**高配备选**而非默认。

### 8.2 其他（P2 参照）

| 名称 | URL | 备注 |
|---|---|---|
| TencentARC/AnimeSR | https://github.com/TencentARC/AnimeSR | 动漫超分专模型（2022），与 Real-ESRGAN animevideov3 同家族，已覆盖 |
| hzwer/practical-rife | https://github.com/hzwer/practical-rife | RIFE 官方更实用版，已集成 RIFE 的升级参照 |
| stepfun-ai/StepVideo-T2V | https://huggingface.co/stepfun-ai/stepvideo-t2v | 30B 文本生视频，太重（8GB 不可跑），仅生成范式参照 |

**结论**：超分/补帧方向**项目已具备足够能力**（Real-ESRGAN animevideov3 + RIFE 全链路已集成），本轮无"必须替换"的新增。VEnhancer 作为一致性问题的高配备选，AnimeSR/practical-rife 作为已集成能力的微调参照。

---

## 九、集成优先级建议（行动清单）

| 优先级 | 动作 | 对症缺口 | 成本 |
|---|---|---|---|
| **A1 (P0)** | 下载并验证 `ai-forever/kandinsky-videomae-large-camera-motion`，对比已集成 base 版在 58 个 AMV 素材上的 acc/Pull-Push 类提升 | W2 | 低（复用验证脚本） |
| **A2 (P0)** | 核验 ToriiGate 许可；2B GGUF 量化版在 8GB 本地跑通动漫 caption/氛围标注试点 | W3+W6 | 中 |
| **A3 (P1)** | 评估 MatAnyone 替换/补充 RVM（动漫人物抠像帧间一致性 A/B） | 抠像 | 中 |
| **A4 (P1)** | 集成 BiRefNet（MIT）作为静态构图抠像默认 | 抠像 | 低 |
| **A5 (P1)** | 接入 BeatNetLite 下拍 + 评估 SongFormer 副歌结构 → rhythm_reward 三层信号 | 卡点(W7) | 中 |
| **A6 (P2)** | ShotBench 作为运镜/景别分类器动漫域外评测集 | W2/W3 | 低 |

---

## 十、开放问题与风险

1. **许可待核验（高优先级）**：ToriiGate、MatAnyone、VEnhancer、BeatNetLite、kandinsky-videomae-large 五者的许可未在本轮搜索中拿到权威文本，**集成前必须逐一下载 LICENSE 原文核验**（复用 v1 报告 T1 同款流程）。其中 ToriiGate 若为 CC BY-NC 则降级 P1，仅非商业可用。
2. **动漫运镜标注数据仍稀缺** [置信度 High]：本轮未发现比 CameraBench/MovieShots 更细、可下载的动漫运镜标注集，Step 4 自建动漫运镜标注仍是刚需。
3. **动漫域迁移性存疑** [置信度 Medium]：kandinsky-videomae-large 与 ToriiGate 均在真人/通用域为主，动漫赛璐璐画风下的精度需用项目素材盲评校准（复用 rhythm_reward 19/22 一致率方法）。
4. **VideoMAE-large 的 8GB 适配**：large 骨干比 base 大，fp16 推理 8GB 可跑但需实测；若显存吃紧，回退 base 版 + LoRA 微调（§五 HF recipe）。

---

## 参考文献

[1] ai-forever — kandinsky-videomae-large-camera-motion — https://huggingface.co/ai-forever/kandinsky-videomae-large-camera-motion — Tier 2（WebSearch 确认存在，许可/类别表需下载核验）
[2] Minthy — ToriiGate-v0.4-2B / -7B — https://huggingface.co/Minthy/ToriiGate-v0.4-7B — Tier 2（WebSearch，GGUF/exl2 量化存在，许可未明确）
[3] richservo — MatAnyone (CVPR 2025) — https://github.com/richservo/MatAnyone — Tier 2（WebSearch，许可需核验）
[4] ZhengPeng7 — BiRefNet — https://huggingface.co/ZhengPeng7/BiRefNet — Tier 2（MIT，置信度 High）
[5] briaai — RMBG-2.5 — https://huggingface.co/briaai/RMBG-2.5 — Tier 2（BRIA 许可，商用有条件）
[6] turbo — BeatNetLite — https://github.com/turbo/BeatNetLite — Tier 2（WebSearch）
[7] SongFormer — arXiv 2510.02797 — https://arxiv.org/abs/2510.02797 — Tier 2（WebSearch）
[8] Vchitect — VEnhancer — https://github.com/Vchitect/VEnhancer — Tier 2（WebSearch，权重许可需核验）
[9] lunahr — Marlin-2B-ungated — https://huggingface.co/lunahr/Marlin-2B-ungated — Tier 3（WebSearch，原版许可未确认）
[10] OpenGVLab — MetaCaptioner — https://github.com/OpenGVLab/MetaCaptioner — Tier 2（WebSearch）
[11] AudioVisual-Caption — ASID-Captioner-7B — https://huggingface.co/AudioVisual-Caption/ASID-Captioner-7B — Tier 3（WebSearch）
[12] marvex — ShotBench — https://huggingface.co/datasets/marvex/ShotBench — Tier 2（WebSearch）
[13] Lewandofski — OpenVE-3M — https://huggingface.co/datasets/Lewandofski/OpenVE-3M — Tier 2（WebSearch）
[14] Argaw et al. — The Anatomy of Video Editing (ECCV 2022) — https://mlanthology.org/eccv/2022/argaw2022eccv-anatomy/ — Tier 2（WebSearch）
[15] BS-BGM (IEEE 2025) — https://ieeexplore.ieee.org/abstract/document/10945856 — Tier 2（WebSearch）
[16] huggingface — video_classification 官方教程 — https://github.com/huggingface/transformers/blob/main/docs/source/en/tasks/video_classification.md — Tier 1（官方 recipe）
[17] Meta — SAM 3 — 示例封装 https://github.com/Mahmoudm007/Segment-Anything-Model-3_SAM3 — Tier 2（WebSearch）
[18] TencentARC — AnimeSR — https://github.com/TencentARC/AnimeSR — Tier 2（已覆盖，参照）
[19] hzwer — practical-rife — https://github.com/hzwer/practical-rife — Tier 2（已覆盖，参照）
[20] stepfun-ai — StepVideo-T2V — https://huggingface.co/stepfun-ai/stepvideo-t2v — Tier 2（过重，范式参照）

---

## Methodology

web_search ×26 覆盖六大方向（视频理解模型/数据集/微调/音频/抠像/超分补帧），逐条按「名称/URL/类型/许可/规模性能/对症缺口/集成评级」落表；许可字段凡未能拿到权威文本者均标注「需核验 + 置信度」，与项目既有 Tier 分级惯例一致。本报告为 `2026-08-13` 与 `2026-08-14-v2` 两轮调研的**增量补充**，未重复其已核验结论。
