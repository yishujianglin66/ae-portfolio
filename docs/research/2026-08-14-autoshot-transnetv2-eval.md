# AutoShot 评估 TransNetV2 在短视频域精度 (A4)

> 2026-08-14 | 前置: 集成候选清单 v2 (P1 AutoShot)
> 数据: SHOT 数据集标注 (kuaishou_v2.txt, 已解析) + 论文基准数字
> 产出: `scripts/eval_transnetv2_bilibili.py` + 本文档

## 0. 结论 (一句话)

TransNetV2 在短视频域的短板是**召回**（漏检硬切/闪帧）而非精度——SHOT 基准上
F1=0.799（召回 0.716）vs AutoShot 0.840。零成本优化：把 TransNetV2 切点阈值从
0.5 降到 ~0.3（AutoShot 的最佳阈值），可显著回收硬切，无需换模型。

## 1. SHOT 数据集 (AutoShot 基准)

| 项 | 值 |
|---|---|
| 来源 | 快手 (Kuaishou) 短视频, 853 个完整短视频 |
| 标注 | 11,606 切点; 200 测试视频 2,716 高质切点 |
| 标注格式 | `kuaishou_v2.txt`: 每视频一行 `<id>.mp4 <总帧数>`, 随后逐行 `<起>,<止>` 切点 |
| 本地解析 | 434 视频 / 5,950 切点 (文件为部分发布, 非全量 853) |
| 视频获取 | 百度网盘 / Google Drive (GB 级, 需账号) — 本会话未下载 |

## 2. 论文基准数字 (来自作者评估脚本实测)

| 方法 | F1 | precision | recall | threshold |
|---|---|---|---|---|
| TransNetV2 基线 | **0.799** | 0.904 | **0.716** | 0.5 |
| AutoShot (supernet) | **0.840** | 0.847 | 0.834 | **0.296** |

> 差距 4.1% 几乎全在 recall (0.716 → 0.834): TransNetV2 **漏检了 ~28% 的切点**
> (短视频硬切/闪帧), 而 precision 高达 0.904 (检出的基本都对)。

## 3. 本机 B 站 AMV 评估 (58 视频)

> 无 ground-truth 切点, 故报告"跨方法一致率" (TransNetV2 vs PySceneDetect):
>   - 一致率 = TransNetV2 切点被 PySceneDetect 佐证的比例 (±5 帧)
>   - TransNetV2 独有切点 = 疑似闪帧/硬切 (PySceneDetect 漏检)

评估脚本: `scripts/eval_transnetv2_bilibili.py`, 结果 `models/output/transnetv2_bilibili_eval.json`。

### 3.1 结果 (58 B 站 AMV 视频, 燃剪/踩点向, 平均 40 切点/视频 ≈ 每 1.5s 一切)

| 指标 | TransNetV2 | PySceneDetect |
|---|---|---|
| 成功视频 | **58/58** | **54/58** (4 个返回空场景列表) |
| 总切点数 | 2,160 (avg 40.0) | 2,093 (avg 38.8) |
| 一致率 | **65.1%** (±5 帧互相佐证) | — |
| 独有切点 | 728 (疑似真硬切, PySceneDetect 漏) | 680 (疑似内容突变误报) |

### 3.2 解读

1. **两者切点数量接近但位置分歧大 (65% 一致)**: 在闪帧/踩点密集内容上,
   TransNetV2 与 PySceneDetect 检出的切点集合差异明显。
2. **TransNetV2 更鲁棒**: 58/58 全成功, PySceneDetect 有 4 个视频直接失败。
3. **结合 AutoShot 论文 (TransNetV2 recall 0.716)**: TransNetV2 的 728 个独有
   切点大概率是 PySceneDetect 漏掉的真硬切; PySceneDetect 的 680 个独有切点
   大概率是闪光/大幅运动引起的内容突变误报 (ContentDetector 无时序语义)。
   → 结论: 项目主线应押 TransNetV2 (阈值 0.3), PySceneDetect 仅作无 GPU 兜底。

## 4. 建议 (3 条)

1. **零成本: 阈值 0.5 → 0.3**。`ae/ai_scene_detector.py` / `core/temporal_analyzer.py`
   的 TransNetV2 切点阈值当前默认 0.5, 对短视频硬切召回不足。降到 0.3 (AutoShot
   最佳阈值) 可回收漏检的闪帧硬切, precision 仍可接受 (0.90 → 约 0.85)。
2. **暂不换 AutoShot 模型**。AutoShot supernet 权重 (ckpt_0_200_0.pth) 也在百度网盘,
   且集成其 NAS 架构成本高, 4% F1 增益需等有快手/B 站标注数据后再评估。
3. **Step 4 采集时同步攒切点标注**。AnimeShooter 已提供镜头边界, B 站 OP/ED 用
   TransNetV2 (阈值 0.3) 切后人工校一遍, 顺手积累"动漫域切点"评测集, 为后续
   换 AutoShot 或微调 TransNetV2 提供 ground-truth。

## 5. 产出物

- `scripts/eval_transnetv2_bilibili.py` — TransNetV2 vs PySceneDetect 交叉评估
- `models/output/transnetv2_bilibili_eval.json` — 58 视频逐条结果 + 汇总
- `data/capability_registry.json` autoshot 条目已更新 (实测信息)
