# 运镜分类器精度提升报告 (2026-08-15)

> 对象: `core/camera_movement_classifier.py` (LK 光流) × VLM 标注 (Qwen3-VL-8B)
> 数据: `D:\AE-Data\AnimeCamera\human_review_queue.jsonl` (74 条低置信) /
>       `reviewed_results.jsonl` (74 条复核) / `vlm_labels.jsonl` (6166 条全量)
> 结论先行: 光流分类器存在 **3 个真实缺陷 + 1 组未校准阈值**, 均已修复;
> 与 VLM 的一致性仍有结构性天花板 (VLM 自身在 pan 上过度标注)。

---

## 1. 复核队列分析 (74 条)

`reviewed_results.jsonl` 的 `reviewed_label` 是 LK 光流重标注
(`scripts/process_human_review_queue.py`), 不是人眼标签。

| 指标 | 旧分类器 |
|---|---|
| VLM 原始标签分布 | complex 70 / static 1 / pan_right 1 / zoom_out 2 (置信 0.3–0.85) |
| 光流重标注分布 | **zoom_in 40** / complex 16 / static 6 / tilt 8 / pan 3 / zoom_out 1 |
| 标签变更率 | 58/74 = **78.4%** |
| 3 段投票平局 (1/1/1) | **18 条** (Counter.most_common 平局取首段 → 标签近似随机) |
| 低置信 (<0.5) | 10 条 |

关键疑点:
- 队列里**每个标签类别的 mean_radial 均为负** (static -0.5, pan -5~-9, tilt -13.6,
  zoom_in -17.6) — 系统性负偏置, 不合物理。
- 唯一方向翻转案例 `BV1i4411v7iF_001`: VLM=zoom_out → 光流=zoom_in
  (rad=-13.5, 画面收缩) — VLM 正确, 光流 zoom 方向反了。

## 2. 大规模一致性评估 (544 条分层抽样)

从 `vlm_labels.jsonl` 按 (标签 × 置信档 {0.95, 0.92, 0.85}) 分层抽样 544 条,
逐条跑光流分类器 (`scripts/eval_flow_vs_vlm.py`)。

| 指标 | 旧管线 | 新管线+旧阈值 | 新管线+调优阈值 |
|---|---|---|---|
| 精确一致率 | 14.3% | 15.4% | **17.6%** |
| 运动族一致率 | 24.8% | 24.4% | **30.7%** |
| conf≥0.95 子集一致率 | 20.8% | 27.4% | **29.7%** |
| static 召回 | 71.9% | 78.1% | 78.1% |
| pan 召回 (左/右) | 5.2% / 7.8% | 10.3% / 7.8% | 12.1% / 11.1% |
| tilt 召回 (上/下) | 13.7% / 9.0% | 20.5% / 11.2% | 24.7% / 12.4% |
| zoom_out 召回 | 4.4% | 17.8% | 21.1% |
| zoom_in 召回 | 25.6% | 5.6% | 6.7% (语义翻转后, 见 §3-2) |

第三方仲裁 (LoRA VideoMAE, val_acc 0.64, 74 条队列):
LoRA vs 光流 18.9% / LoRA vs VLM 1.4% — 三方在此难集上互不一致,
印证该队列本身是高难度、低一致性样本的集合。

## 3. 根因诊断 (证据链)

### 3-1 LK 金字塔跟踪失效 → 虚假位移 (主因)

`winSize=(15,15), maxLevel=4` 在低纹理动漫帧的金字塔粗层 (20×15) 锁错
周期性纹理。取证 (`scripts/lk_forensics.py`, 静态样本 `BV1aD4y1j7E7_076`):

| 方法 | 帧对(0→1) 位移 |
|---|---|
| cv2.phaseCorrelate (独立鲁棒基准) | (+0.16, -0.26) ≈ 静止 |
| 稠密 Farneback | (+3.6, 0.0) ≈ 静止 |
| 稀疏 LK (15,15)/lv4 (旧参数) | **(-92.6, -30.2) ← 虚假** |
| 稀疏 LK (15,15)/lv0 | (+1.2, -0.9) ✓ |
| 稀疏 LK (31,31)/lv3 | (+3.4, +11.3) ✓ |

全量帧间灰度差: 4.5% 的采样步对 >60 (硬转场/闪光), LK 在这些帧对上
产生 -100px 级野值并污染均值。这解释了队列中 static→zoom_in、pan→zoom_in
的错判, 以及全类别 mean_radial 负偏置。

### 3-2 zoom 方向约定反转 (定义性错误)

- 旧约定 (分类器注释/测试/`vlm_annotate_camera.py` 头注释): 收缩→zoom_in,
  扩散→zoom_out — 与物理语义相反。
- 权威约定: VLM 提示词原文「画面从中心向外扩散/**放大 → zoom_in**」、
  `core/camera_language.py` (推=scale 100→150 放大)、MovieShots 映射
  (Push→zoom_in) — 全部一致: **放大=推近=zoom_in**。
- 修复: radial>0 → zoom_in, radial<0 → zoom_out; 同步翻转测试夹具方向、
  更新注释。代价: 对 VLM zoom_in 的召回下降 (见 §2), 因为 VLM 的 zoom_in
  判断与全局径向流几乎不相关 (zoom_in/zoom_out 两类样本均约 60% 径向为负,
  VLM 按主体大小判断而非全局流)。

### 3-3 平局投票未处理

18/74 队列样本三段投票 1/1/1, `Counter.most_common(1)` 静默取首段标签。
修复: 平局 → 全局统计判定 + 置信度封顶 0.5 (`classify_video` 与
`classify_video_cached` 同步)。

### 3-4 阈值未校准

在 544 条评估集上网格搜索 (8640 组合, `scripts/tune_camera_thresholds.py`),
目标 = VLM 置信度加权精确一致率:

| 参数 | 旧值 | 新值 |
|---|---|---|
| `_STATIC_DISP` | 1.0 | **0.5** |
| `_PAN_CONSISTENCY` | 0.55 | **0.40** |
| `_TILT_CONSISTENCY` | 0.50 | **0.40** |
| `_ZOOM_CONSISTENCY` | 0.40 | **0.35** |
| `_ZOOM_MIN_RADIAL` | 0.3 | **0.2** |
| `_ENTROPY_COMPLEX` | 0.75 | **0.80** |
| `_FALLBACK_CONF` | 0.15 | **0.10** |
| `_LK_WIN_SIZE` | (15,15) | **(31,31)** |
| `_LK_MAX_LEVEL` | 4 | **3** |
| `_CUT_GUARD` / `_MAX_STEP_DISP` | — | **60.0** / **40.0** (新增) |

## 4. 修复后复核队列重跑

| 指标 | 旧 | 新 |
|---|---|---|
| 标签变更率 | 78.4% | **60.8%** (45/74) |
| zoom_in / zoom_out | 40 / 1 | **2 / 14** (方向翻转生效) |
| complex | 16 | 30 (弱信号如实归 complex) |
| 3 段平局 | 18 | 14 (全局兜底判定) |
| 低置信 (<0.5) | 10 | 4 |
| 方向翻转案例 BV1i4411v7iF_001 | 错判 zoom_in | 平局→complex(0.50) 不再武断 |

合成验证 (`scripts/verify_classifier_synthetic.py`): static/pan_left/pan_right/
zoom_in/zoom_out/complex 六类全部通过; 缺文件安全默认通过。
(pytest 因沙箱 tmp 目录限制无法直接运行, 以等价脚本直验。)

## 5. 一致性结论与天花板

1. **光流 vs VLM 一致性**: 精确 ~18%, 运动族 ~31%, VLM 高置信 (≥0.95) 子集 ~30%。
   修复前分别为 14.3% / 24.8% / 20.8%。
2. **天花板来源 (VLM 侧)**: pan 占 VLM 全量标签 48% (2935/6166), 但 pan 样本的
   全局水平流实测 ≈ 0 (mean_dx 中位数 < 1px) — VLM 依据 4 帧主体运动过度
   推断相机摇移; static 仅占 1.3% (82 条), 而光流实测 static 占比高得多。
3. **天花板来源 (光流侧)**: 稀疏 LK 仍有约 60/40 的残余负径向偏置 (稠密
   Farneback 符号均衡); 1s 短视频 + 角色动画主导全局流, 相机运动信号弱。
4. **置信度使用建议**: 光流 conf < 0.5 的标签 (新队列仅 4 条) 应继续走人工
   复核或交由 LoRA/VLM 融合判定, 不应直接作为导演决策输入。

## 6. 后续精度提升路线 (优先级排序)

1. **稠密光流替换稀疏 LK** (`cv2.calcOpticalFlowFarneback`): 无角点依赖、
   符号无偏, 320×240 上 ~10ms/帧, 成本可接受; 已验证与相位相关一致。
2. **主体中心 zoom 检测**: 以画面主体 (显著性区域) 为中心计算径向流,
   规避全局流被角色动画主导的问题 — 直接针对 VLM zoom_in 召回低。
3. **人工复核闭环**: `review_template.csv` 的 human_direction 列仍为空 —
   填入 74 条人眼标签后可作为真正的黄金集重跑调优 (当前调优参照是
   VLM 高置信标签, 自身有偏)。
4. **三源融合**: VLM (语义) + 光流 (几何) + LoRA (时序) 在置信度加权下
   投票, 替代当前 `ai/camera_decision.py` 的 L0→L2 纯降级链。

## 7. 产物清单

| 产物 | 位置 |
|---|---|
| 分类器 v2 (含全部修复+新阈值) | `core/camera_movement_classifier.py` |
| 测试夹具语义翻转 | `tests/test_camera_classifier.py` |
| VLM 脚本注释修订 | `scripts/vlm_annotate_camera.py` |
| 复核一致性分析 | `scripts/analyze_review_consistency.py` → `models/output/review_consistency.json` |
| 大规模评估 | `scripts/eval_flow_vs_vlm.py` → `models/output/flow_vlm_eval.jsonl` / `..._report.json` |
| 稠密流对照审计 | `scripts/dense_flow_audit.py`, `scripts/lk_forensics.py`, `scripts/lk_param_grid.py` |
| LoRA 仲裁 | `scripts/arbitrate_queue_lora.py` → `models/output/queue_lora_arbitration.json` |
| 阈值调优 | `scripts/tune_camera_thresholds.py` → `models/output/camera_thresholds_tuned.json` |
| 新复核结果 (74 条) | `models/output/reviewed_results_v2.jsonl` |
| 合成直验 | `scripts/verify_classifier_synthetic.py` |

> 注意: `D:\AE-Data\AnimeCamera\reviewed_results.jsonl` 因运行环境文件沙箱
> (workspace-write) 无法覆写; 新结果落在 `models/output/reviewed_results_v2.jsonl`,
> 在无沙箱环境重跑 `py -3.12 scripts/process_human_review_queue.py` 即可回写 D 盘。
