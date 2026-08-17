# Step 4: 自建动漫运镜数据集方案 (Anime Camera Movement Dataset)

> 2026-08-14 | 前置: Step 3 (MovieShots 47,463 条已下载, 分类器管线就绪, VideoMAE 现成基线已验证)
> 状态: **有管线等数据** —— 采集/标注管线设计完成, 数据规模取决于 GPU/人工复核预算
> 最新: 发现现成 VideoMAE-MovieShots 模型 (MIT), Step 4 从"从零训练"升级为"动漫数据 LoRA 微调现成模型"

## 0. 为什么必须自建

| 事实 | 证据 |
|---|---|
| 公开"动漫运镜"数据集不存在 | 2026-08-13 调研确认 (docs/research/2026-08-13-aesthetic-perception-oss-research.md), 运镜领域仅 MovieShots(真人电影预告片) 与 CameraBench(VLM 分类法, 数据为任意视频) |
| 电影域 → 动漫域迁移性差 | MovieShots 运镜 4-5 类太粗, 动漫赛璐璐画风/2D 空间与实拍差异大, 光流特征在动漫上退化 (动漫线条稀疏、大色块、少纹理) |
| 项目素材全为动漫 | 漫剪/AMV 管线 (v23) 消费 B 站动漫素材, 分类器必须在动漫域上有 >80% 准确率 (T3 验收标准) |
| 自建即差异化 | 做出来就是公开唯一, 可反哺社区 |

## 1. 数据集设计目标

- **任务**: 镜头级运镜分类 (训练替代 core/camera_movement_classifier.py 光流规则的分类器)
- **标签体系**: 与项目 CAMERA_LABELS 对齐的细分类 (13 类), 或先做 MovieShots 同款粗分类 (5 类) 再细化
- **规模目标**: v1 基线 2,000-5,000 镜头 (人工复核), v2 扩充 10,000+ (半自动)
- **验收**: 独立盲评集上准确率 >80%, 且超过现有光流规则在动漫素材上的表现

## 2. 三类候选数据源 (P0/P1/P2)

### P0 — B 站动漫 OP/ED/切片 (主力, 已具备下载管线)

- 资产: `ai/t37c_bilibili_download.py` (B站下载)、`bilibili_creator_analyzer.py`、`13-素材获取与搜索/` 知识库
- 来源: 高知名度动漫 OP/ED (镜头语言标准)、漫剪切片 (运镜丰富)、官方 PV
- 优点: 免版权摩擦 (个人学习研究)、量大、风格多样、与项目素材同域
- 缺点: 需自己切镜头边界 (TransNetV2 已就绪)

### P1 — AnimeShooter (HF qiulu66/AnimeShooter, CC BY-NC 4.0)

- 2025 年多镜头动画数据集 (参考引导视频生成用), 镜头级划分现成
- 优点: 已按镜头组织; 缺点: 无运镜标签 (需自标), 学术用途许可
- 用途: 镜头边界 + 视频素材源, 不是标签源

### P1 — 动漫电影/剧集片段 (自行获取, 注意版权)

- 同人研究合理使用; 选镜头语言丰富的知名作品片段
- 与 P0 互补: 电影级运镜 (推拉摇移更规范)

### P2 — 动漫游戏 CM/PV (官方发布)

- 如米哈游/明日方舟/赛马娘官方 PV, 运镜炫技密集, 官方已授权发布 (非商用研究)

## 3. 标注管线 (半自动 + 人工复核)

```
采集 (B站下载) → 镜头边界 (TransNetV2, 已就绪)
     → 候选镜头筛选 (时长 0.3-8s, 去静态黑场)
     → VLM 预标注 (Qwen2.5-VL / SiliconFlow 视觉模型, 已配置)
         prompt: "该镜头相机运动是 pan_left/pan_right/zoom_in/zoom_out/
                   tilt_up/tilt_down/static/push/orbit/complex?"
     → 人工复核 (接受/拒绝/改标, 抽 20% 双人一致性校验)
     → 入库 JSONL (与 Step 3 MovieShots 统一格式)
```

- **VLM 预标注成本**: SiliconFlow Qwen3-VL 每镜头 ~¥0.001, 5,000 镜头 ≈ ¥5 (已配置 API)
- **人工复核**: 逐镜头看 GIF/短视频打标签, 5,000 镜头 ≈ 8-12 小时 (可分批)
- **关键**: VLM 预标注置信度 <0.7 的进人工队列, 高置信的直接入库 (主动学习)

## 4. 与 Step 3 的衔接

| 步骤 | 数据 | 训练 | 产出 |
|---|---|---|---|
| Step 3 | MovieShots 47,463 条 (电影域) + **现成 VideoMAE 微调模型** (acc 91.35%, MIT) | 加载现成模型验证 ✅ 已完成 (0.33s/视频, 58 素材全通过) | VideoMAE-MovieShots 基线 |
| Step 4a | 自建动漫粗分类 2,000-5,000 条 | **VideoMAE LoRA 微调** (动漫域迁移) | 动漫域运镜分类器 (4-5 类) |
| Step 4b | 自建细分类 (13 类, 需更多标注) | 同上 + 方向细分 | 动漫域细分类器 |

- **2026-08-14 重大简化**: 发现 `gullalc/videomae-base-finetuned-kinetics-movieshots-movement`
  (MIT) 已现成——Step 4 不再从零训练, 而是**用动漫数据微调现成 VideoMAE** (LoRA 在
  8GB 可跑), 冷启动标注量需求减半。详见 docs/research/2026-08-14-integration-candidates-v2.md
- MovieShots 预训练 → 动漫数据微调 (迁移学习) = 项目主路径
- 两个分类器共存: `SourceCameraInventory.inject()` 已预留注入口 (ai/camera_decision.py L121-130)

## 5. GPU/数据规模预算

| 方案 | 数据量 | GPU 时长 (RTX 4060 8GB) | 成本 |
|---|---|---|---|
| v1 基线 (粗 5 类) | 2,000 标注 | MLP <5min + 特征提取 ~3h (CPU 光流) | ¥0 (本地) |
| v1.5 迁移学习 | MovieShots 47K 预训练 + 2K 动漫微调 | ~1h | ¥0 (本地) |
| v2 扩充 | 10,000 标注 | VLM 预标注 API + 特征提取 ~15h | ~¥10-20 (VLM) |
| 进阶: 视频分类器 (帧序列 CNN) | 10,000+ | ~4-6h | ¥0 (本地) |

## 6. 里程碑

- [x] A1 ✅ 2026-08-14: 采集完成 — **153 视频 (47 OP/ED + 106 AMV, 39 部动漫, 8.9h 素材, 3.3GB)**
  - 工具: `scripts/collect_anime_camera_data.py` (WBI 签名搜索 + yt-dlp 下载 + manifest 断点续传)
  - 关键坑: B站搜索 API 风控 412/-352 → WBI 签名解决; 空格关键词必须 %20 编码 (quote_plus 的 + 会导致签名 md5 不匹配, 返回空结果)
  - OP/ED 质量过滤 (排除翻唱/演奏/盘点); 数据落盘 `D:\AE-Data\AnimeCamera\`
- [x] A2 ✅ 2026-08-14: 切镜头完成 — **153 视频 → 18,235 候选 (0.3-8s), 18,122 切片成功** (工具 `scripts/cut_anime_shots.py`, 1.9h)
- [~] A3: VLM 预标注 **完成 4,998/5,000 (¥0.90, 3.8h)** + 人工复核 64 条硬队列完成
  - 复核结论 1: 运镜标签绝大多数正确 ✅ (VLM 预标注质量过关)
  - 复核结论 2: 21 条内容归属与搜索词不符 (混剪/风格化相近) → anime=mixed + content_note, 对训练零影响
  - 已知偏差: VLM 对风格化推镜有 complex 误判倾向 (光流规则对照发现), v2 加规则二道校验
- [~] A4: LoRA 微调 v1 完成 (best val_acc 63.65%) → **三方评估: 基座 22.9% / LoRA 70.4% / 光流规则 32.0%** (300 条 VLM 盲评集)
  - 关键结论: 电影域 91.35% 基座在动漫域崩到 22.9% (Step 4 必要性实锤); LoRA +47.5 点
  - 短板: Pull 4.2% (348 样本) → **v2 重训中** (权重上限 20x + WeightedRandomSampler, 5 epochs)
- [ ] A5: 接入 SourceCameraInventory + camera_diversity_score, 验收 >80%

## 7. 关键风险与对策

1. **版权**: 只做本地研究, 不公开发布视频; 发布仅限标注 JSON (标签不侵权)
2. **VLM 误标**: 人工复核 + 主动学习, 置信度阈值分流
3. **动漫运镜判定主观**: 标注指南写死判定规则 (光流方向约定同 core/camera_movement_classifier.py), 双人一致率 >85% 才放行
4. **GPU 不在线时**: 特征提取可纯 CPU (光流 320x240), 训练 MLP 秒级

## 8. 产出物

- `D:\AE-Data\AnimeCamera\` (原始视频/镜头切片, 不入 git)
- `data/anime_camera_dataset.jsonl` (统一标注, 入 git 可)
- `models/anime_camera_clf.pt` + meta + model_registry 登记
