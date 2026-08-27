# 2-Class Camera Motion Classifier

## 概述

轻量级 2 类运镜分类器（static vs motion），用于动漫视频镜头运动检测。

## 性能指标

| 方法 | bal_acc | 模型大小 | 推理时间 | 依赖 |
|------|---------|---------|---------|------|
| CNN（推荐） | 0.6725 | 1.5 MB | CPU ~1-2s | torch, cv2 |
| 帧差阈值 | 0.6615 | 0 | CPU ~0.5s | cv2 |

**性能天花板说明**：0.67 是当前标签质量下的理论最优（VLM 2 类噪声率 25.7%），非模型能力瓶颈。

## 使用方法

### Python API

```python
from camera_classifier_2class import CameraClassifier2Class

# 初始化（加载 CNN 模型）
classifier = CameraClassifier2Class(
    model_path='models/camera_classifier/d2_cnn_2class_best.pt',
    device='cpu'
)

# 预测
pred, conf, method = classifier.predict('video.mp4')
print(f"Prediction: {pred}, Confidence: {conf:.3f}")
```

### 命令行

```bash
# 使用 CNN 模型
python camera_classifier_2class.py video.mp4 --model d2_cnn_2class_best.pt

# 使用帧差阈值（零训练 fallback）
python camera_classifier_2class.py video.mp4 --threshold-fallback
```

## 文件说明

- `d2_cnn_2class_best.pt` — CNN 模型权重（1.5 MB，0.5M 参数）
- `camera_classifier_2class.py` — 推理脚本（含 CNN + 阈值 fallback）
- `README.md` — 本文档

## 技术细节

### CNN 架构

```
4 层卷积：3→32→64→128→256
输入：帧差均值图（3×128×128）
输出：2 类概率（static/motion）
```

### 训练数据

- 数据：7690 条动漫视频 clips（均衡采样）
- 标签：VLM 弱标签（static vs motion）
- 增强：随机相邻帧对 + 水平翻转
- 训练：AdamW lr=1e-3，CosineAnnealing 20 epochs

### 性能瓶颈

- 2 类 bal_acc 天花板 ~0.67（四种独立方法收敛）
- 根因：VLM 标签噪声率 25.7%（static 准确率仅 26.3%）
- 改进方向：标签去噪（需专家模型重新标注）

## 后续扩展

### 分层混合架构（已实现）

1. **第一层**：`camera_classifier_2class.py`（static vs motion，0.67，CPU 秒级）
2. **第二层**：`vlm_expert_3class.py`（zoom vs tilt-orbit，~3s/条，GPU）
3. **端到端**：`camera_classifier_hierarchical.py`（3 类 static/zoom/tilt-orbit）

仅对 motion 样本调用 VLM，整体 3 类 bal_acc 预期 0.50-0.60。

### 使用分层分类器

```python
from camera_classifier_hierarchical import HierarchicalCameraClassifier

# 初始化（自动加载 CNN，VLM 懒加载）
classifier = HierarchicalCameraClassifier(
    cnn_model_path='d2_cnn_2class_best.pt',
    vlm_model_name='chancharikm/qwen2.5-vl-7b-cam-motion',
    device='cuda'
)

# 3 类预测
pred, conf, method, desc = classifier.predict('video.mp4')
print(f"Prediction: {pred}, Confidence: {conf:.3f}")
```

```bash
# 命令行（3 类）
python camera_classifier_hierarchical.py video.mp4 --device cuda

# 仅 2 类（不加载 VLM）
python camera_classifier_hierarchical.py video.mp4 --no-vlm
```

## 引用

实验详情：`00-每日记录/2026-08-25_00-运镜v6云端对账与开训-开发进度.md` §12
