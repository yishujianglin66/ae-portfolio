# deepghs/anime_classification 动漫内容标签接入 (A6)

> 2026-08-14 | 前置: 集成候选清单 v2 (P1 deepghs/anime_classification)
> 模型: HF deepghs/anime_classification (MIT), 5 类动漫内容标签
> 产出: `scripts/tag_anime_content.py` + 本文档

## 0. 结论 (一句话)

deepghs/anime_classification 给素材打 5 类动漫内容标签 (3d/bangumi/comic/
illustration/not_painting), 补 HighlightScorer 的内容语义特征 (W3)。默认用
mobilenetv3_v1.2_dist (96.53% acc, 0.63G FLOPS, CPU 0.075s/帧)。

## 1. 模型概览

| 变体 | 参数 | FLOPS | acc | 用途 |
|---|---|---|---|---|
| **mobilenetv3_v1.2_dist** (默认) | 4.18M | 0.63G | **96.53%** | 逐帧批量打标, CPU 友好 |
| caformer_s36_v1.4_focal_fixed | 37.22M | 22.1G | 96.21% | 备选 (慢 30x, 精度相当) |

- 5 类标签: `3d`(3D渲染/MMD) / `bangumi`(番剧截图) / `comic`(漫画) /
  `illustration`(插画) / `not_painting`(宣传图/游戏截图/教程录屏等)
- 本地: `D:\AE-Data\Models\anime_classification\{variant}\model.onnx`

## 2. 关键经验 (实测 2026-08-14)

1. **置信度校准偏低是特性不是 bug**: 该系列为 focal loss 训练, softmax 输出
   平坦 (max 0.25-0.40 属正常), 金标准测试 (干净番剧帧 → bangumi, 教程录屏 →
   not_painting, 可视化图 → not_painting) 均证实 **argmax 是可靠信号**。
   集成时禁止用置信度阈值做决策, 用 argmax/投票。
2. **预处理**: resize 384x384 (BICUBIC) + ImageNet 归一化 (timm 风格), RGB。
3. **视频级聚合**: 多数投票 > 概率平均 (概率校准偏差会污染平均)。
4. **坑**: HF 直连不稳, 用 hf-mirror.com; imgutils 的 PyPI 包名是 `dghs-imgutils`
   (裸 `imgutils` 是占位包); onnxruntime 本机为 CPU-only (无 CUDA EP)。

## 3. 本机 58 B 站 AMV 视频打标结果

脚本: `scripts/tag_anime_content.py`, 结果 `models/output/anime_content_tags.json`。

### 3.1 结果 (58 视频, 每视频 16 帧投票, 4.6 分钟, 全 CPU)

| 标签 | 视频数 | 典型 |
|---|---|---|
| bangumi | 20 | 地缚少年花子君 (12/16 票), 海贼王, FATE 系 |
| not_painting | 20 | PR/AE 教程录屏, 特效演示 (黑岩射手系 AMV) |
| illustration | 8 | 时光代理人系 (静态卡/插画风) |
| 3d | 7 | 裸眼3D 效果, DL_Move 系 |
| comic | 3 | 漫画分格风素材 |

### 3.2 解读

1. **测试目录本身混合三类内容** (番剧 AMV + 剪辑教程 + 3D 特效演示), 模型正确
   分流: 教程/录屏 → not_painting, 干净番剧 → bangumi (高票), 特效重的 AMV 落在
   3d/not_painting (特效后画面确实偏离"绘画"域)。
2. **对漫剪管线的价值**: 素材池加 `anime_content` 维度后, 可自动过滤掉 20 个
   not_painting (教程/录屏) 不让它进漫剪素材池; 同时 3d 标签区分 MMD 类素材。
3. **性能**: 0.075s/帧 × 16 帧 ≈ 1.2s/视频, 58 视频 4.6 分钟纯 CPU, 无需 GPU。

## 4. 接入点 (W3 HighlightScorer)

- 素材入库时逐视频采样 16 帧 → 投票得内容标签 (成本 ~0.075s/帧)
- 漫剪管线素材池新增 `anime_content` 维度: bangumi 优先作画面素材,
  illustration 可作静态帧/过渡卡, not_painting 素材直接降权 (教程/录屏不适合漫剪)
- `data/capability_registry.json` pretrained_models 已登记 deepghs_anime_classification

## 5. 产出物

- `scripts/tag_anime_content.py` — 单图/视频打标 CLI (双模型变体支持)
- `models/output/anime_content_tags.json` — 58 视频逐条结果 (本地, 不入 git)
