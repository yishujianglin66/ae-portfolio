# Silhouette 智能遮罩与AI辅助抠像

> 分类: Roto抠像专题
> 更新日期: 2026-07-11
> 概述: 系统讲解 Silhouette 集成的 AI 辅助抠像能力，包括自动边缘检测、智能跟踪、机器学习模型应用与人工精修协作工作流。

## 目录
1. [AI 辅助能力总览](#一ai-辅助能力总览)
2. [自动边缘检测](#二自动边缘检测)
3. [智能跟踪与传播](#三智能跟踪与传播)
4. [机器学习模型应用](#四机器学习模型应用)
5. [AI 与人工精修协作](#五ai-与人工精修协作)
6. [代码示例](#六代码示例)
7. [常见问题与最佳实践](#七常见问题与最佳实践)

---

## 一、AI 辅助能力总览

### 1.1 Silhouette AI 抠像能力栈

```
┌─────────────────────────────────────────┐
│  应用层  │ AI 工作流编排、人工精修接口    │
├─────────────────────────────────────────┤
│  模型层  │ ML 模型：边缘检测、分割、跟踪 │
├─────────────────────────────────────────┤
│  数据层  │ 训练数据：图像特征、运动向量   │
├─────────────────────────────────────────┤
│  计算层  │ GPU/CPU 推理引擎              │
└─────────────────────────────────────────┘
```

### 1.2 核心 AI 功能

| 功能 | 模块 | 适用场景 | 精度 |
|------|------|---------|------|
| **Magic Brush** | 智能画笔 | 快速起稿 | 70-85% |
| **Edge Detect** | 边缘检测 | 硬边物体 | 85-95% |
| **Object Segmentation** | 实例分割 | 多目标分离 | 80-90% |
| **Smart Tracker** | 智能跟踪 | 形状传播 | 90-95% |
| **Roto Assist** | 智能插值 | 减少关键帧 | 80-90% |
| **Hair/Fur Detection** | 毛发检测 | 毛发抠像 | 60-75% |

### 1.3 AI 适用与不适用场景

**适合 AI 辅助**：
- 高对比度物体（前景背景清晰）
- 刚体或缓慢变形物体
- 大量相似镜头的批量处理
- 起稿阶段快速生成基础形状

**不适合 AI（需手工）**：
- 低对比度（前景背景颜色相近）
- 极细毛发、半透明纱裙
- 快速运动模糊严重
- 多物体重叠交叉
- 影院级精度要求（像素级）

---

## 二、自动边缘检测

### 2.1 工作原理

```
输入图像 → 特征提取（Canny/Sobel） → 语义分割（CNN）
         → 边缘候选 → 形状拟合（Bézier/X-Spline） → 输出形状
```

### 2.2 启用自动边缘检测

```python
from fx import *

roto = Node("RotoNode")
session.addNode(roto)

# 启用 AI 边缘检测
roto.property("ai.edgeDetect").setValue(true, 0)
roto.property("ai.edgeSensitivity").setValue(0.7, 0)  # 0-1
roto.property("ai.edgeSmoothness").setValue(0.5, 0)   # 0-1
roto.property("ai.edgeMode").setValue("precise", 0)    # precise/balanced/fast
```

### 2.3 参数详解

| 参数 | 类型 | 默认 | 范围 | 说明 |
|------|------|------|------|------|
| ai.edgeDetect | bool | false | - | 启用 AI 边缘检测 |
| ai.edgeSensitivity | float | 0.5 | 0-1 | 灵敏度，高=捕捉更多边缘 |
| ai.edgeSmoothness | float | 0.5 | 0-1 | 平滑度，高=曲线更平滑 |
| ai.edgeMode | str | "balanced" | precise/balanced/fast | 工作模式 |
| ai.minArea | int | 100 | 10-10000 | 最小检测区域（像素） |
| ai.confidence | float | 0.6 | 0-1 | 置信度阈值 |

### 2.4 检测模式对比

| 模式 | 速度 | 精度 | 关键帧密度 | 适用 |
|------|------|------|----------|------|
| precise | 慢（2-3x） | 95% | 低 | 影院级、产品广告 |
| balanced | 中（1x） | 85% | 中 | 大多数场景 |
| fast | 快（0.5x） | 70% | 高 | 预览、起稿 |

### 2.5 边缘检测工作流

```python
def ai_edge_detect_workflow(roto_node, frame, seed_point):
    """AI 边缘检测工作流"""
    # 1. 设置检测参数
    roto_node.property("ai.edgeDetect").setValue(true, 0)
    roto_node.property("ai.edgeMode").setValue("balanced", 0)
    roto_node.property("ai.edgeSensitivity").setValue(0.7, 0)
    roto_node.property("ai.confidence").setValue(0.6, 0)

    # 2. 提供种子点（用户指定检测起点）
    roto_node.property("ai.seedPoint").setValue(seed_point, frame)

    # 3. 触发检测（异步）
    roto_node.triggerAI("detectEdge", frame)

    # 4. 等待结果（实际为同步等待）
    shape = roto_node.getLastDetectedShape()

    if shape:
        print(f"[AI] 检测到形状，点数: {len(shape.points)}")
        return shape
    else:
        print("[AI] 未检测到形状，请调整参数或种子点")
        return None
```

---

## 三、智能跟踪与传播

### 3.1 智能跟踪原理

```
关键帧 N (手工形状) → AI 跟踪 → 关键帧 N+1, N+2, ... (自动生成)
                     ↑
                     特征匹配 + 形状变形
```

### 3.2 启用智能跟踪

```python
# 启用智能跟踪
roto.property("ai.smartTrack").setValue(true, 0)
roto.property("ai.trackMode").setValue("hybrid", 0)  # optical/planar/hybrid
roto.property("ai.trackRange").setValue("forward", 0)  # forward/backward/both
roto.property("ai.trackQuality").setValue(0.8, 0)  # 0-1
```

### 3.3 跟踪模式对比

| 模式 | 原理 | 适用 | 局限 |
|------|------|------|------|
| **optical** | 光流法 | 短距离运动、变形 | 模糊时失效 |
| **planar** | 平面跟踪 | 平面物体、刚体 | 非平面变形差 |
| **hybrid** | 光流+平面混合 | 通用（推荐） | 计算量大 |
| **point** | 点跟踪 + 形状变换 | 简单运动 | 不适合变形 |

### 3.4 形状传播（Shape Propagation）

```python
def propagate_shape_forward(roto_node, shape, start_frame, end_frame):
    """将形状从起始帧向前传播到结束帧"""
    roto_node.property("ai.smartTrack").setValue(true, 0)
    roto_node.property("ai.trackMode").setValue("hybrid", 0)
    roto_node.property("ai.trackRange").setValue("forward", 0)
    roto_node.property("ai.trackQuality").setValue(0.8, 0)

    # 设置传播参数
    roto_node.property("ai.propagateSource").setValue(shape.id, 0)
    roto_node.property("ai.propagateStart").setValue(start_frame, 0)
    roto_node.property("ai.propagateEnd").setValue(end_frame, 0)

    # 触发传播
    roto_node.triggerAI("propagateShape")

    print(f"[AI] 形状 {shape.name} 传播: {start_frame} → {end_frame}")
```

### 3.5 跟踪质量评估

```python
def evaluate_tracking_quality(shape, start_frame, end_frame):
    """评估跟踪质量，返回需手工修正的帧"""
    review_frames = []

    for frame in range(start_frame, end_frame + 1):
        # 获取该帧的形状位置
        positions = [p.getValue(frame) for p in shape.points]

        # 检查形状是否合理（无自相交、面积变化合理）
        area = calculate_polygon_area(positions)
        base_area = calculate_polygon_area(
            [p.getValue(start_frame) for p in shape.points]
        )

        area_ratio = area / base_area if base_area > 0 else 0

        # 面积变化超过 30% 需要检查
        if area_ratio < 0.7 or area_ratio > 1.3:
            review_frames.append({
                "frame": frame,
                "issue": "area_anomaly",
                "ratio": area_ratio
            })

    return review_frames

def calculate_polygon_area(points):
    """计算多边形面积（Shoelace 公式）"""
    n = len(points)
    area = 0
    for i in range(n):
        j = (i + 1) % n
        area += points[i][0] * points[j][1]
        area -= points[j][0] * points[i][1]
    return abs(area) / 2
```

---

## 四、机器学习模型应用

### 4.1 内置 ML 模型

Silhouette 2026 内置以下预训练模型：

| 模型 | 任务 | 训练数据 | 精度 |
|------|------|---------|------|
| **PortraitNet v3** | 人物肖像分割 | 50万张人像 | 92% IoU |
| **HairNet v2** | 毛发分割 | 20万张毛发样本 | 75% IoU |
| **VehicleNet v2** | 车辆分割 | 30万张车辆 | 95% IoU |
| **ProductNet** | 产品分割 | 15万张产品图 | 90% IoU |
| **GenericSeg v4** | 通用分割 | 100万张多类 | 85% IoU |

### 4.2 模型选择与加载

```python
# 选择模型
roto.property("ai.model").setValue("PortraitNet_v3", 0)

# 加载模型（首次使用）
roto.property("ai.loadModel").setValue(true, 0)

# 检查模型状态
model_loaded = roto.property("ai.modelLoaded").getValue(0)
print(f"模型已加载: {model_loaded}")

# 模型推理参数
roto.property("ai.inferenceResolution").setValue(0.5, 0)  # 0.5x 分辨率推理
roto.property("ai.batchSize").setValue(4, 0)  # 批处理大小
```

### 4.3 模型推理工作流

```python
def run_model_inference(roto_node, model_name, frame_range):
    """运行 ML 模型推理"""
    # 1. 加载模型
    roto_node.property("ai.model").setValue(model_name, 0)
    roto_node.property("ai.loadModel").setValue(true, 0)

    # 2. 设置推理参数
    roto_node.property("ai.inferenceResolution").setValue(1.0, 0)  # 全分辨率
    roto_node.property("ai.confidence").setValue(0.7, 0)  # 置信度阈值

    # 3. 对每帧推理
    shapes_created = []
    for frame in frame_range:
        # 触发推理
        roto_node.triggerAI("inferFrame", frame)

        # 获取结果形状
        shape = roto_node.getLastDetectedShape()
        if shape:
            shape.name = f"{model_name}_frame_{frame}"
            shapes_created.append(shape)
            print(f"[AI] 帧 {frame}: 检测到形状, 点数={len(shape.points)}")

    print(f"[AI] 推理完成，共 {len(shapes_created)} 个形状")
    return shapes_created
```

### 4.4 自定义模型集成

```python
def load_custom_model(roto_node, model_path):
    """加载用户自定义 ONNX/TensorFlow 模型"""
    roto_node.property("ai.customModelPath").setValue(
        model_path.replace("\\", "/"), 0
    )
    roto_node.property("ai.model").setValue("custom", 0)
    roto_node.property("ai.loadModel").setValue(true, 0)

    # 验证加载
    if roto_node.property("ai.modelLoaded").getValue(0):
        print(f"[AI] 自定义模型加载成功: {model_path}")
        return True
    else:
        print(f"[AI] 模型加载失败，请检查路径和格式")
        return False
```

### 4.5 模型精度优化

```python
def optimize_model_accuracy(roto_node, target_object="person"):
    """根据目标物体类型优化模型精度"""
    presets = {
        "person": {
            "model": "PortraitNet_v3",
            "confidence": 0.7,
            "edgeMode": "precise",
            "edgeSensitivity": 0.8
        },
        "hair": {
            "model": "HairNet_v2",
            "confidence": 0.5,  # 毛发置信度低
            "edgeMode": "precise",
            "edgeSensitivity": 0.9
        },
        "vehicle": {
            "model": "VehicleNet_v2",
            "confidence": 0.8,
            "edgeMode": "balanced",
            "edgeSensitivity": 0.6
        },
        "product": {
            "model": "ProductNet",
            "confidence": 0.85,
            "edgeMode": "precise",
            "edgeSensitivity": 0.5
        }
    }

    preset = presets.get(target_object, presets["person"])
    for key, value in preset.items():
        if key == "model":
            roto_node.property("ai.model").setValue(value, 0)
        elif key == "confidence":
            roto_node.property("ai.confidence").setValue(value, 0)
        elif key == "edgeMode":
            roto_node.property("ai.edgeMode").setValue(value, 0)
        elif key == "edgeSensitivity":
            roto_node.property("ai.edgeSensitivity").setValue(value, 0)

    print(f"[AI] 已应用 {target_object} 预设")
```

---

## 五、AI 与人工精修协作

### 5.1 协作工作流

```
1. AI 起稿      → 70% 准确度，5 分钟生成基础形状
2. 人工检查     → 标记需修正区域
3. AI 局部重检  → 仅针对标记区域重新推理
4. 人工精修     → 调整控制点、羽化、关键帧
5. AI 跟踪传播  → 将精修后的形状传播到相邻帧
6. 人工终检     → 逐帧检查，微调
```

### 5.2 局部修正接口

```python
def local_ai_refine(roto_node, shape, frame, region_bbox):
    """对指定区域进行 AI 局部重新检测"""
    # 设置局部检测区域
    roto_node.property("ai.localRegion").setValue(region_bbox, frame)
    roto_node.property("ai.localRefine").setValue(true, 0)
    roto_node.property("ai.edgeMode").setValue("precise", 0)
    roto_node.property("ai.edgeSensitivity").setValue(0.9, 0)

    # 触发局部推理
    roto_node.triggerAI("localRefine", frame)

    # 获取修正后的形状
    refined_shape = roto_node.getLastDetectedShape()
    if refined_shape:
        # 替换原形状的局部控制点
        print(f"[AI] 局部修正完成，新点数: {len(refined_shape.points)}")
        return refined_shape
    return None
```

### 5.3 置信度热力图

```python
def generate_confidence_heatmap(roto_node, frame):
    """生成 AI 置信度热力图，辅助人工决策"""
    roto_node.property("ai.showConfidence").setValue(true, 0)
    roto_node.property("ai.confidenceThreshold").setValue(0.5, 0)

    # 渲染置信度图（输出到临时文件）
    roto_node.triggerAI("renderConfidenceMap", frame)

    print(f"[AI] 置信度热力图已生成 (frame={frame})")
    print("  红色区域 = 低置信度（需人工检查）")
    print("  绿色区域 = 高置信度（可信任）")
```

### 5.4 批量 AI 处理

```python
def batch_ai_process(session, frames, model_name="GenericSeg_v4"):
    """批量 AI 处理多帧"""
    results = []

    for frame in frames:
        # 创建临时 RotoNode
        roto = Node("RotoNode")
        roto.label = f"AI_Frame_{frame}"
        session.addNode(roto)

        # 配置 AI
        roto.property("ai.model").setValue(model_name, 0)
        roto.property("ai.edgeMode").setValue("fast", 0)  # 批量用 fast
        roto.property("ai.confidence").setValue(0.6, 0)

        # 推理
        roto.triggerAI("inferFrame", frame)
        shape = roto.getLastDetectedShape()

        if shape:
            shape.name = f"AI_Shape_{frame}"
            results.append({
                "frame": frame,
                "shape": shape,
                "point_count": len(shape.points)
            })

    print(f"[AI] 批量处理完成: {len(results)}/{len(frames)} 帧成功")
    return results
```

---

## 六、代码示例

### 6.1 完整 AI 辅助抠像管线

```python
from fx import *

def create_ai_assisted_pipeline(source_path, output_path,
                                  model="PortraitNet_v3", frame_rate=24.0):
    """创建 AI 辅助抠像完整管线"""
    proj = activeProject() or Project()
    activate(proj)
    session = activeSession() or Session()
    session.label = "AI_Assisted_Keying"
    activate(session)
    proj.addItem(session)

    src = Node("SourceNode")
    src.property("mediaPath").setValue(source_path.replace("\\", "/"), 0)
    src.property("frameRate").setValue(frame_rate, 0)
    session.addNode(src)

    roto = Node("RotoNode")
    roto.label = "AI_Roto"
    session.addNode(roto)

    # === AI 配置 ===
    roto.property("ai.model").setValue(model, 0)
    roto.property("ai.loadModel").setValue(true, 0)
    roto.property("ai.edgeDetect").setValue(true, 0)
    roto.property("ai.edgeMode").setValue("balanced", 0)
    roto.property("ai.edgeSensitivity").setValue(0.7, 0)
    roto.property("ai.confidence").setValue(0.65, 0)

    # === 智能跟踪 ===
    roto.property("ai.smartTrack").setValue(true, 0)
    roto.property("ai.trackMode").setValue("hybrid", 0)
    roto.property("ai.trackQuality").setValue(0.8, 0)

    # === 边缘优化 ===
    roto.property("alpha.blur").setValue(0.4, 0)
    roto.property("antialias").setValue(1.0, 0)

    # === 输出 ===
    out_node = Node("OutputNode")
    out_node.property("path").setValue(output_path.replace("\\", "/"), 0)
    out_node.property("format").setValue("exr", 0)
    session.addNode(out_node)

    src.outputs[0].connect(roto.inputs[1])
    roto.outputs[0].connect(out_node.inputs[0])

    print(f"[SILHOUETTE] AI 辅助管线已创建")
    print(f"  模型: {model}")
    print(f"  模式: balanced, 灵敏度: 0.7")
    print(f"  跟踪: hybrid, 质量: 0.8")
    return roto
```

### 6.2 AI 起稿 + 人工精修

```python
def ai_draft_then_refine(roto_node, key_frames):
    """AI 起稿，然后人工精修"""
    shapes = {}

    # === Phase 1: AI 起稿 ===
    for frame in key_frames:
        roto_node.triggerAI("inferFrame", frame)
        shape = roto_node.getLastDetectedShape()
        if shape:
            shape.name = f"AI_Draft_{frame}"
            shapes[frame] = shape
            print(f"[AI] 帧 {frame} 起稿完成, 点数: {len(shape.points)}")

    # === Phase 2: AI 传播 ===
    for i in range(len(key_frames) - 1):
        start = key_frames[i]
        end = key_frames[i + 1]
        propagate_shape_forward(roto_node, shapes[start], start, end)

    # === Phase 3: 标记需修正帧 ===
    review_list = []
    for frame, shape in shapes.items():
        issues = evaluate_tracking_quality(shape, frame, frame + 24)
        if issues:
            review_list.extend(issues)

    print(f"[AI] 需人工修正帧: {len(review_list)}")
    return shapes, review_list
```

### 6.3 AI 质量评估报告

```python
def generate_ai_quality_report(roto_node, frame_range):
    """生成 AI 抠像质量报告"""
    report = {
        "total_frames": len(frame_range),
        "detected_frames": 0,
        "high_confidence": 0,
        "low_confidence": 0,
        "failed_frames": [],
        "average_confidence": 0.0
    }

    confidences = []

    for frame in frame_range:
        roto_node.triggerAI("evaluateFrame", frame)
        confidence = roto_node.property("ai.lastConfidence").getValue(frame)

        if confidence > 0:
            report["detected_frames"] += 1
            confidences.append(confidence)

            if confidence >= 0.8:
                report["high_confidence"] += 1
            elif confidence < 0.5:
                report["low_confidence"] += 1
        else:
            report["failed_frames"].append(frame)

    if confidences:
        report["average_confidence"] = sum(confidences) / len(confidences)

    print("=== AI 质量报告 ===")
    print(f"总帧数: {report['total_frames']}")
    print(f"检测成功: {report['detected_frames']}")
    print(f"高置信度: {report['high_confidence']}")
    print(f"低置信度: {report['low_confidence']}")
    print(f"平均置信度: {report['average_confidence']:.2f}")
    print(f"失败帧: {report['failed_frames']}")

    return report
```

---

## 七、常见问题与最佳实践

### 7.1 问题诊断

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| AI 检测不到目标 | 对比度低 / 模型不匹配 | 切换模型，提高 edgeSensitivity |
| 边缘"沸腾" | AI 帧间不稳定 | 增加关键帧，关闭 ai.smartTrack |
| 毛发区丢失 | HairNet 精度有限 | AI 起稿后手工精修 |
| 跟踪"漂移" | 光流估计错误 | 改用 planar 模式，缩短跟踪距离 |
| 模型加载失败 | 路径错误 / 格式不支持 | 检查 ONNX 格式，路径用 `/` |
| GPU 内存不足 | 分辨率过高 | 降低 inferenceResolution 到 0.5 |

### 7.2 最佳实践

1. **AI 起稿 + 人工精修**：AI 用于起稿（70% 准确），人工精修关键帧，再 AI 传播。
2. **模型匹配场景**：人物用 PortraitNet，车辆用 VehicleNet，通用场景用 GenericSeg。
3. **关键帧优先**：在运动转折点手工精修，让 AI 在转折点之间插值。
4. **置信度分级**：>0.8 直接采用，0.5-0.8 人工检查，<0.5 手工重做。
5. **局部精修**：用 `localRefine` 仅对问题区域重新检测，节省时间。
6. **混合工作流**：AI 起稿 → 跟踪传播 → 人工终检 → AI 局部重检。

### 7.3 性能建议

- 预览用 `fast` 模式，最终用 `precise`。
- 批量处理用 `inferenceResolution=0.5`，最终全分辨率。
- GPU 加速：`roto.property("ai.device").setValue("gpu", 0)`。
- 模型缓存：首次加载后保留在内存，避免重复加载。
- 批处理大小：`batchSize=4` 平衡速度与内存。

### 7.4 质量检查清单

- [ ] AI 模型匹配场景类型
- [ ] 置信度 > 0.7 的帧占 80% 以上
- [ ] 关键转折点已手工精修
- [ ] 跟踪传播后逐帧检查
- [ ] 边缘无"沸腾"
- [ ] 毛发/半透明区手工补充
- [ ] 与源素材运动模糊匹配

---

## 相关文档

- [Silhouette 毛发与半透明物体抠像](Silhouette%20毛发与半透明物体抠像.md)
- [Silhouette 边缘优化与运动模糊](Silhouette%20边缘优化与运动模糊.md)
- [Silhouette Roto工作流最佳实践](Silhouette%20Roto工作流最佳实践.md)
- [Silhouette 遮罩质量检查与优化](Silhouette%20遮罩质量检查与优化.md)
