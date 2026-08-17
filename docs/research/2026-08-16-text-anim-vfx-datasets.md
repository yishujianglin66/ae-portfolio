# 文字动画 / 特效 / AE 合成 — 数据集与训练路线调研结论

> 日期：2026-08-15（调研）/ 2026-08-16（落盘）
> 来源：早期会话三方向检索（子代理两次被中断后，由主代理经 GitHub API / 本地 vendored 代码 / 项目内既有调研文档交叉核验）
> 状态标记：✅ = API/本地实证；⭐ = WebSearch 二手信息待核

---

## 一、核心结论（三句话）

1. **文字动画风格化的最优路径是自产合成数据**：项目已有 18 预设（本次 M0 验收 18/18 全绿）+ 8 种缓动 DNA（`jsx_keyframe_animator`）+ 120 条参数模板——程序化生成"文本+风格参数 → 动画 JSON/渲染帧"训练对，数据成本为零，直接衔接 M5 参数预测器。
2. **AE 合成方向**（已完成的 BiRefNet 混合微调之外的）下一步增量是 **VideoMatte240K（时序）+ iHarmony4（融合）**，而非继续堆图像抠像数据。
3. **特效感知方向不需要专门训练**：继续用三通道 VLM 自建标注（项目已有 7612 条先例），公开"特效类别识别"数据集在开源界是空白。

## 二、文字动画 / 动态排版

| 数据集/模型 | 状态 | 结论 |
|---|---|---|
| **KineTy**（SeonmiP/KineTy，ECCV 2024） | ✅ API 实证：官方代码，59 stars，许可证 NOASSERTION | 动态排版扩散模型。社区冷 + 许可不明 → **只读论文与数据组织方式，不做依赖** |
| **AnyText**（tyxsspa/AnyText） | ✅ API 实证：4872 stars，**Apache-2.0** | 多语言文字渲染与编辑，中文支持好、有训练代码。项目文字是 AE 原生渲染（质量已够）→ **留作 M2 视觉评估的文字清晰度参考，不训练** |
| TextDiffuser | ⭐ | 与 AnyText 同类，二选一即可，AnyText 中文生态更合适 |
| **自产合成数据** | ✅ 本地实证 | `text_animation_engine`（18 预设×7 mood×6 位置）+ `jsx_keyframe_animator`（2847 行）= 现成生成器。M5 数据积累的直接来源 |

**行动**：M2 视觉评估（Qwen-MM 评分）→ 每个 CompositionTree 跑 3-5 参数变体 → 积累 300+ 条 → 训 GBDT/小 MLP（CPU 即可）。

## 三、AE 合成（抠像/融合/光照）

| 数据集 | 状态 | 用途 | 建议 |
|---|---|---|---|
| **VideoMatte240K** | ✅ 本地 RVM 训练文档实证（SD 6G / HD 60G，华盛顿大学 BGMv2 项目） | 时序视频抠像 | **下一优先**：补时序能力空白（当前逐帧抠像在运动段质量下降已实证） |
| **iHarmony4** | ✅ GitHub API 实证（bcmi 仓库，MIT，65,742 train + 7,404 test） | 合成和谐化 | **第二优先**：对治"抠出来的人不融合新背景" |
| P3M-10k / AM-2k / PPM-100 | ⭐ | 发丝级人像抠像 | 需向作者申请；与 CelebA 伪 mask（已训 3973 张）功能重叠 → 暂缓 |
| RWP-636 | ⭐ | 重光照人像 | 换背景重光照场景对口，iHarmony4 之后考虑 |

**已完成的训练**（防重复盘点）：BiRefNet 动漫域微调（1111 对，val 0.0526）✅；BiRefNet 混合微调（7699 对：anime+VOC416+cityscapes+ADE1132+CelebA3973）🔄 2026-08-15 云端训练中。

## 四、特效 / VFX 感知

| 方向 | 结论 |
|---|---|
| 动漫运镜 | 公开数据集不存在（项目 2026-08-13 调研已确认）→ 自建 AnimeCamera 7612 条 VLM 标注 ✅ 已完成 |
| 转场检测 | PySceneDetect + TransNetV2 方案已集成，无训练必要 |
| 特效识别 | 无对口公开数据集 → 三通道 VLM 自建（t26 系列管线现成） |
| 长期观察 | `awesome-video-editing` 收录的 MovieCuts / VEU-Bench / Edit3K（剪辑风格迁移），留档不启动 |

## 五、模型选型结论（换不换）

- **BiRefNet 不换**：SOTA 级二值分割，与 MatAnyone 双模型互补策略已定（MatAnyone 主抠时序 + BiRefNet 补缺失帧）
- **SAM2 视频传播模式值得探索**：项目已集成 sam2.1（M0 会话实证加载 224M 参数），天生视频模型，做时序抠像比逐帧更对症——零成本实验
- **VideoMAE 运镜不换**：瓶颈在动漫域数据不在模型（v3b fine-10 已回传）
- **Whisper base → large 蒸馏**：可选，10 倍推理成本换小幅准确率，按需

## 六、与项目里程碑的映射

| 方案里程碑 | 状态 | 本调研对应 |
|---|---|---|
| M0 资产修复 | ✅ 2026-08-16 验收（18/18 预设、硬编码坏链已修） | — |
| M1 合成编排 | ✅ 真机验证（M4_Style 4 层合成） | — |
| M2 视觉评估闭环 | ⏳ 待做 | Qwen-MM 评分网关（AnyText 作文字清晰度参考） |
| M3 节拍锚定 | ✅ 真机验证（M3_Beat_Fate 关键帧落节拍） | — |
| M4 风格生成 | ✅ 真机验证 | — |
| M5 参数预测器 | ⏳ 待做（需 300+ 自产数据） | **本调研核心落点：自产合成数据 → GBDT/MLP** |

## 参考链接

- KineTy: https://github.com/SeonmiP/KineTy （ECCV 2024 官方代码）
- AnyText: https://github.com/tyxsspa/AnyText （Apache-2.0）
- iHarmony4: https://github.com/bcmi/Image_Harmonization_Datasets （MIT）
- BiRefNet: https://github.com/ZhengPeng7/BiRefNet （MIT, 4046 stars）
- RVM/VideoMatte240K: 本地 `external/rvm/documentation/training.md`
- 项目既有调研：`docs/research/2026-08-13-aesthetic-perception-oss-research.md`
