# CameraBench 运镜词汇表校准 (A3)

> 2026-08-14 | 前置: 集成候选清单 v2 (P1 CameraBench)
> 数据: HF syCen/CameraBench, test.jsonl 1071 样本 + videos.csv 645 视频
> 产出: `core/camera_vocabulary.py` (映射表 + 映射函数 + Step4 标注 schema) + 本文档

## 0. 结论 (一句话)

CameraBench 用 34 个运镜原语、**4 个正交维度** (方向/速度/稳定/复杂度) 标注镜头，
而项目 `core/camera_movement_classifier.py` 的 13 类 `CAMERA_LABELS` 是**单维扁平**的
方向标签。校准产出方向映射表 (1:1/多:1)，并给出 Step 4 VLM 预标注应升级的**多维 schema**。

## 1. CameraBench 34 原语 (4 维度)

| 维度 | 原语 | 数量 |
|---|---|---|
| 方向 motion | static/no-motion/minor-motion, pan/truck×L/R, tilt/pedestal×up/down, zoom×in/out, dolly×in/out, arc×CW/CCW, roll×CW/CCW | 19 |
| 跟拍 tracking | side/pan/tilt/arc/aerial/tail/lead-tracking | 7 |
| 速度 speed | regular/slow/fast-speed | 3 |
| 稳定 stability | no-shaking/minimal-shaking/unsteady/very-unsteady | 4 |
| 复杂度 complexity | complex-motion | 1 |

标注是**多标签** (每样本 3-8 个标签, 方向维基本单主方向 + 可选跟拍)。

## 2. 方向映射表 (CameraBench → 项目 13 类)

见 `core/camera_vocabulary.py` `DIRECTION_TO_PROJECT`。要点:

| CameraBench | 项目 | 说明 |
|---|---|---|
| static / no-motion / minor-motion | `static` | 静态组 |
| pan-left/right, truck-left/right | `pan_left`/`pan_right` | truck=横向轨道 ≈ pan (2D 光流等价) |
| tilt-up/down, pedestal-up/down | `tilt_up`/`tilt_down` | pedestal=升降 ≈ tilt |
| zoom-in / zoom-out | `zoom_in`/`zoom_out` | lens 变焦 |
| **dolly-in / dolly-out** | **`push` / `zoom_back`** | ⭐ 物理推拉 (透视变化), 精确对应项目 push/zoom_back |
| arc-CW/CCW, roll-CW/CCW | `orbit` | 环绕 + 绕光轴旋转 (roll 项目无, 归 orbit) |
| 7 种 tracking | 与显式方向同轴合并; 无方向时 → `complex` | 跟拍方向多义 |

## 3. 关键发现 (3 条)

1. **`push`/`zoom_back` 语义补全**: 项目 13 类里的 `push`(推近) / `zoom_back`(拉远)
   长期语义模糊, CameraBench 精确对应 **dolly-in / dolly-out** (物理推拉, 与 lens zoom
   的 zoom-in/out 区分)。→ 光流规则与 VLM prompt 应明确这个区分。
2. **项目缺 `roll`(绕光轴旋转)**: CameraBench 有 roll-CW/roll-CCW, 项目无对应类,
   现归 `orbit`。动漫里"天旋地转"转场常见, 建议 Step 4 细分类补 roll。
3. **速度/稳定维度缺失**: 项目 13 类只有方向, 无速度 (快慢推拉) 和稳定 (手持晃动)。
   CameraBench 证明这两个维度对"运镜质感"影响大, Step 4 应三维标注。

## 4. 真实数据校准统计 (1071 样本)

映射到项目扁平标签:

| 标签 | 数量 | 占比 |
|---|---|---|
| complex | 358 | 33% |
| static | 194 | 18% |
| orbit | 122 | 11% |
| push | 90 | 8% |
| pan_right / pan_left | 79 / 67 | 14% |
| tilt_down / tilt_up | 37 / 31 | 6% |
| zoom_in / zoom_out / zoom_back | 32 / 30 / 31 | 9% |

> 对比 MovieShots (static 65% 严重不均衡), CameraBench 方向分布健康得多,
> 更适合做**平衡的评测集**。

速度维: regular 940 / slow 79 / fast 52。
稳定维: no-shaking 519 / minimal-shaking 299 / unsteady 197 / very-unsteady 56。

## 5. 对 Step 4 的建议

Step 4 VLM 预标注 prompt 从单标签升级为**三维 schema** (见
`core/camera_vocabulary.py` `ANNOTATION_LABEL_SCHEMA`):

```
direction: static / pan_left / pan_right / tilt_up / tilt_down /
           zoom_in / zoom_out / push / zoom_back / orbit / complex
speed:     regular-speed / slow-speed / fast-speed
stability: no-shaking / minimal-shaking / unsteady / very-unsteady
```

这样动漫自建数据能同时训练方向分类器 + 速度/稳定回归器, 信息量比 MovieShots 单维更足。
