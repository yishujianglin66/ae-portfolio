# VQA 视频质量评估候选方案评估表

> 创建时间: 2026-08-13
> 目的: 评估可接入 AutoQualityEvaluator 的视频质量评估方案
> 依据: docs/research/2026-08-13-aesthetic-perception-oss-research.md

## 评估维度

| 维度 | 说明 |
|------|------|
| 离线可用 | 是否无需联网/云端 |
| 依赖大小 | 模型体积 + 运行时依赖 |
| ffmpeg 兼容 | 能否与现有 ffmpeg 管线共存 |
| 接入成本 | 代码改动量 + 测试覆盖难度 |
| 预期增益 | 对 AutoQualityEvaluator 精度提升幅度 |

## 候选方案

| 候选 | 定位 | 许可证 | 离线 | 依赖 | ffmpeg | 接入成本 | 增益 | 结论 |
|------|------|--------|------|------|--------|----------|------|------|
| **VMAF(libvmaf)** | 全参考感知质量 | BSD | ✅ | 小(ffmpeg内置) | ✅ 原生 | **已完成** | 中 | ✅ **已集成** |
| **DOVER** | 无参考美学+技术双分支 | S-Lab License 1.0 (非商业) | ✅ | 大(9.86M参数) | ⚠️ 需PyTorch | 中 | 高 | ⚠️ **限非商业** |
| **improved-aesthetic-predictor** | 图像级美学(CLIP+MLP) | Apache-2.0 | ✅ | 中(CLIP模型) | ❌ 抽帧聚合 | 高 | 中 | ⏳ 备选 |
| **FAST-VQA** | 轻量无参考VQA | MIT | ✅ | 中 | ❌ 需PyTorch | 中 | 中 | ❌ DOVER骨干,单独意义不大 |
| **Q-Align** | VLM打分 | Apache-2.0 | ✅ | 大(7B模型) | ❌ | 高 | 高 | ❌ 成本过高 |
| **VideoScore2** | 视频质量/美学 | 待确认 | ✅ | 中 | ❌ | 待确认 | 待确认 | ⏳ 观察项 |

## 明确不集成清单

| 方案 | 不集成原因 |
|------|-----------|
| Q-Align | 依赖 7B 大模型,推理成本高,不适合批量评估 |
| FAST-VQA | 是 DOVER 的骨干网络,单独评估意义不大 |
| VideoScore2 | 较新方案,细节待核实,作为观察项暂不集成 |

## 已集成方案

### VMAF (Video Multi-method Assessment Fusion)

- **接入位置**: `core/self_evolution_engine.py::_evaluate_visual()`
- **集成方式**: 无参考降级模式(basic_fallback),加权 0.4 与帧统计分 0.6 混合
- **适配器**: `integrations/vmaf_quality_adapter.py` (378 行,已就绪)
- **降级策略**: VMAF 不可用时自动跳过,保持帧统计分
- **验证**: 7/7 测试通过,无回归

## DOVER 接入条件

若项目未来需要商业化,DOVER 需:
1. 联系作者获取商业许可
2. 或替换为 Apache-2.0 的 improved-aesthetic-predictor(抽帧聚合)
3. 当前 S-Lab License 1.0 仅限非商业用途

## 验收证据

```bash
# VMAF 接入后验证
$ py -3.12 -m pytest tests/test_auto_quality_evaluator.py -v
============================= 7 passed in 1.57s ==============================

# 验收脚本确认质量区分度
$ py -3.12 scripts/verify_learning_real_signals.py
[PASS] A1 质量区分度: 动态=47.6 vs 黑屏=37.0, Δ=10.7 (>5.0)
```
