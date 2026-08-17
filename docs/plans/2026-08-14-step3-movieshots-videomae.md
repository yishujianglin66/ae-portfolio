# Step 3: MovieShots 运镜感知 (VideoMAE 基线 + 动漫微调路径)

> 2026-08-14 | 状态: **集成+验证已完成 (V1)** —— 不再从零训练, 用现成 VideoMAE 基线
> 前置: Step 2 (素材管线) | 后续: Step 4 (自建动漫运镜数据集)
> 关联: docs/research/2026-08-14-integration-candidates-v2.md (P0 候选核验)

## 0. 结论 (一句话)

W2「运镜同质化」缺口的解法, 已从「自训光流 MLP」**升级**为「现成 VideoMAE-MovieShots
模型集成 + 动漫数据 LoRA 微调」—— Step 3 的"训练"变"集成+验证", 冷启动成本归零。

## 1. 已完成 (V1 集成+验证)

| 项 | 结果 |
|---|---|
| 模型 | [gullalc/videomae-base-finetuned-kinetics-movieshots-movement](https://huggingface.co/gullalc/videomae-base-finetuned-kinetics-movieshots-movement) (MIT, 329MB) |
| 基线指标 | acc 91.35% (类级: Static 92.94% / Motion 91.7% / Pull 51.25% / Push 62.73%) |
| 项目素材验证 | 58 个 B 站 AMV 素材全通过 (0 错误), 平均 0.33s/视频 (RTX 4060) |
| 结果分布 | Motion 38 / Static 20 (符合动漫 AMV 动态为主) |
| 局限 | 仅 4 类 (Static/Motion/Pull/Push), 无 pan/tilt 方向; Pull/Push 原始 acc 51-63%, 动漫域需微调 |

产出物:
- `models/verify_movieshots_videomae.py` → `models/output/videomae_verify.json` (58 条结果)
- `models/data/movieshots_dataset.py` (MovieShots 47,463 条标注适配器)
- `models/train_movieshots_camera.py` (光流 MLP 兜底路径, 见 §4)
- 登记: `data/capability_registry.json` (`datasets.movieshots` + `pretrained_models.videomae_movieshots_movement`)

## 2. 训练路径变更 (本次核心决策)

```
旧 (v1 方案):   MovieShots 16.9GB 视频 → 光流特征 → 自训 MLP (8 维 → 5 类)
新 (v2 方案):   现成 VideoMAE 模型 → 直接集成推理 (V1 已跑通)
                └→ 动漫自建数据 (Step 4) → LoRA 微调 (V2, 8GB 可跑)
```

| 路径 | 数据 | 训练 | 定位 |
|---|---|---|---|
| **主路径** | MovieShots 47K (电影域) | 现成 VideoMAE (无需训练) | V1 基线, 已上线验证 |
| 微调 | 动漫粗分类 2,000-5,000 (Step 4a) | VideoMAE LoRA 微调 | V2 动漫域迁移 |
| 兜底 | 光流 8 维特征 | 轻量 MLP | 置信度低时回退 (与 ai/camera_decision.py 降级逻辑一致) |

## 3. 类别映射 (关键)

MovieShots movement 5 类 → 项目 CAMERA_LABELS:

| MovieShots | 项目标签 | 说明 |
|---|---|---|
| Static | `static` | |
| Motion | `pan_left` (合并类) | 平移/旋转合并, 方向细分留推理侧 |
| Pull | `zoom_out` | |
| Push | `zoom_in` | |
| Multi_movement | `complex` | |

47,463 条真实分布: static 31,067 / pan_left(Motion) 13,530 / zoom_in(Push) 2,075 /
zoom_out(Pull) 458 / complex 333 —— **类严重不均衡** (static 占 65%), 微调时需
class-weighted loss / 重采样。

## 4. 接入路径 (V1→V3)

```
V1 (已完成): 加载现成模型 → data/real_amv_test 验证 58 素材 ✅
V2 (Step 4 后): 自建动漫数据对 VideoMAE 做 LoRA 微调 (8GB 可跑)
V3: 接入 SourceCameraInventory.inject() 输出标签 → camera_diversity_score
```

- 注入口已预留: `ai/camera_decision.py` L121-130 (`SourceCameraInventory.inject()`)
- 两个分类器共存: VideoMAE 为主, 光流规则兜底

## 5. 里程碑

- [x] S1: 下载 MovieShots 标注 (v1 33,653 + v2 606 + v3 13,204 = 47,463)
- [x] S2: 标注适配器 `models/data/movieshots_dataset.py` (单测 6/6)
- [x] S3: 现成 VideoMAE 模型集成 + 58 素材验证 (acc 基线确认)
- [ ] S4 (→Step 4): 动漫数据 LoRA 微调, 动漫盲评集 >80%
- [ ] S5: 接入 SourceCameraInventory + camera_diversity_score 验收
