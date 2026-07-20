# Silhouette Paint跟踪与自动修复

> 分类: Paint修复专题
> 更新日期: 2026-07-11
> 概述: Paint跟踪与自动修复技术详解，包括跟踪数据驱动、自动传播、帧间插值、智能修复策略等核心技术。

## 目录

1. [Paint跟踪原理](#一paint跟踪原理)
2. [跟踪数据驱动修复](#二跟踪数据驱动修复)
3. [自动传播模式](#三自动传播模式)
4. [帧间插值算法](#四帧间插值算法)
5. [智能修复策略](#五智能修复策略)
6. [偏移修正与补偿](#六偏移修正与补偿)
7. [复杂运动处理](#七复杂运动处理)
8. [性能优化与输出](#八性能优化与输出)

---

## 一、Paint跟踪原理

### 1.1 Paint跟踪的工作机制

Paint 跟踪是将跟踪数据应用到 Paint 笔触上，使笔触随目标物体运动，实现自动化修复：

```
跟踪数据（TrackerNode） → 笔触位置/形状/参数 → 自动多帧修复
```

### 1.2 跟踪类型与 Paint 配合

| 跟踪类型 | 适用场景 | Paint 应用方式 |
|---------|---------|---------------|
| Point（点跟踪） | 小面积瑕疵、点状物体 | 单点位置驱动笔触位置 |
| Planar（平面跟踪） | 大面积区域、平面物体 | 变换矩阵驱动笔触形状 |
| Paint-Track（Paint跟踪） | 复杂运动、序列修复 | 直接跟踪笔触运动 |

### 1.3 跟踪数据结构

```python
# 跟踪数据格式
tracking_data = {
    "version": "2026.0.2",
    "track_type": "planar",
    "frames": [
        {
            "frame": 0,
            "transform": {
                "translation": [100, 200],
                "rotation": 0.0,
                "scale": [1.0, 1.0],
                "shear": [0.0, 0.0]
            },
            "corners": [
                [100, 200], [200, 200],
                [200, 250], [100, 250]
            ]
        },
        {
            "frame": 1,
            "transform": {
                "translation": [102, 203],
                "rotation": 0.5,
                "scale": [1.01, 1.01],
                "shear": [0.0, 0.0]
            }
        }
    ]
}
```

---

## 二、跟踪数据驱动修复

### 2.1 基础配置

```python
from fx import *

# 创建跟踪驱动的 Paint 修复管线
proj = activeProject() or Project()
activate(proj)

session = activeSession() or Session()
session.label = "Tracked_Paint"
activate(session)
proj.addItem(session)

# 源节点
src = Node("SourceNode")
src.property("mediaPath").setValue("D:/footage/scene.####.exr", 0)
src.property("frameRate").setValue(24.0, 0)
session.addNode(src)

# 跟踪节点
tracker = Node("TrackerNode")
tracker.label = "Paint_Track"
tracker.property("trackType").setValue("planar", 0)
tracker.property("searchArea").setValue(21, 0)
tracker.property("accuracy").setValue("high", 0)
tracker.property("patternSize").setValue(11, 0)
tracker.property("forward").setValue(true, 0)
tracker.property("backward").setValue(true, 0)
session.addNode(tracker)

# Paint 节点
paint = Node("PaintNode")
paint.label = "Tracked_Paint"
paint.property("brush.size").setValue(25.0, 0)
paint.property("brush.hardness").setValue(0.5, 0)
paint.property("brush.flow").setValue(0.8, 0)
paint.property("mode").setValue("clone", 0)
paint.property("propagation").setValue("tracked", 0)  # 跟踪驱动传播
paint.property("trackSource").setValue("Paint_Track", 0)  # 指定跟踪源
session.addNode(paint)

# 连接
src.outputs[0].connect(tracker.inputs[0])
src.outputs[0].connect(paint.inputs[0])
```

### 2.2 跟踪源配置

| 参数 | 说明 |
|------|------|
| propagation | 传播模式: tracked/auto/manual/interpolate |
| trackSource | 跟踪数据源节点名称 |
| autoUpdate | 是否自动更新笔触位置 |
| offsetCompensation | 是否启用偏移补偿 |

---

## 三、自动传播模式

### 3.1 传播模式详解

| 模式 | 说明 | 适用场景 |
|------|------|---------|
| tracked | 跟踪数据驱动 | 物体运动规律明确 |
| auto | 自动分析并传播 | 背景相对静态 |
| manual | 手动逐帧 | 复杂场景、自动失效 |
| interpolate | 关键帧插值 | 关键帧之间的过渡 |

### 3.2 Tracked 模式

```python
# 跟踪驱动传播
paint.property("propagation").setValue("tracked", 0)
paint.property("trackSource").setValue("Paint_Track", 0)
paint.property("autoUpdate").setValue(true, 0)
```

工作流程：
1. 在第0帧绘制笔触
2. 跟踪数据自动驱动笔触位置
3. 每帧根据跟踪数据更新笔触
4. Clone 源跟随笔触运动

### 3.3 Auto 模式

```python
# 自动传播
paint.property("propagation").setValue("auto", 0)
paint.property("autoRange").setValue(5, 0)  # 自动传播5帧
paint.property("autoThreshold").setValue(0.3, 0)  # 相似度阈值
```

工作流程：
1. 在第0帧绘制笔触
2. 系统自动分析周围像素
3. 在相邻帧寻找相似区域
4. 自动应用相同修复

### 3.4 Interpolate 模式

```python
# 关键帧插值
paint.property("propagation").setValue("interpolate", 0)

# 设置关键帧
keyframes = [0, 25, 50, 75, 100]
positions = [[100, 200], [120, 210], [140, 220], [160, 230], [180, 240]]

for frame, pos in zip(keyframes, positions):
    paint.property("strokePosition").setValue(pos, frame)
```

---

## 四、帧间插值算法

### 4.1 线性插值

```python
# 线性插值（默认）
paint.property("interpolation").setValue("linear", 0)
```

适用于运动平稳、匀速的场景。

### 4.2 贝塞尔插值

```python
# 贝塞尔曲线插值
paint.property("interpolation").setValue("bezier", 0)
paint.property("bezierTension").setValue(0.5, 0)  # 张力
paint.property("bezierContinuity").setValue(0.5, 0)  # 连续性
```

适用于运动有加速、减速的场景。

### 4.3 运动匹配插值

```python
# 基于跟踪数据的运动匹配插值
paint.property("interpolation").setValue("motion", 0)
paint.property("trackSource").setValue("Paint_Track", 0)
paint.property("motionSmoothing").setValue(0.5, 0)  # 运动平滑度
```

适用于跟踪数据质量高、需要精确匹配的场景。

---

## 五、智能修复策略

### 5.1 自适应笔刷大小

```python
# 根据跟踪特征自动调整笔刷大小
paint.property("adaptiveBrush").setValue(true, 0)
paint.property("brushScaleMin").setValue(0.8, 0)  # 最小缩放
paint.property("brushScaleMax").setValue(1.2, 0)  # 最大缩放
paint.property("brushScaleRange").setValue(0.3, 0)  # 缩放范围
```

### 5.2 智能采样源

```python
# 智能选择 Clone 源
paint.property("smartSource").setValue(true, 0)
paint.property("sourceSearchRange").setValue(50, 0)  # 搜索范围
paint.property("sourceSimilarity").setValue(0.7, 0)  # 相似度阈值
```

### 5.3 多源融合

```python
# 多个 Clone 源融合
paint.property("multiSource").setValue(true, 0)
paint.property("sourceCount").setValue(3, 0)  # 使用3个源
paint.property("fusionMode").setValue("weighted", 0)  # 加权融合
```

### 5.4 修复策略对照

| 策略 | 参数 | 优势 | 适用场景 |
|------|------|------|---------|
| 自适应笔刷 | adaptiveBrush=true | 自动调整大小 | 物体有缩放变化 |
| 智能采样源 | smartSource=true | 自动找最佳源 | 背景复杂 |
| 多源融合 | multiSource=true | 融合多个源 | 纹理复杂区域 |
| 时间平滑 | temporalSmooth=true | 减少闪烁 | 长序列修复 |

---

## 六、偏移修正与补偿

### 6.1 偏移产生原因

- **跟踪漂移**: 长时间跟踪后跟踪点偏移
- **运动模糊**: 模糊导致跟踪不准
- **遮挡**: 目标被遮挡导致跟踪丢失
- **参数变化**: 笔触参数未随运动调整

### 6.2 手动偏移修正

```python
# 在关键帧设置偏移修正
corrections = {
    0: [0, 0],      # 无需修正
    25: [2, 1],     # X偏2像素，Y偏1像素
    50: [5, 3],     # 累积偏移
    75: [3, 2],     # 修正后
    100: [0, 0],    # 完全修正
}

for frame, offset in corrections.items():
    paint.property("offsetCorrection").setValue(offset, frame)
```

### 6.3 自动偏移补偿

```python
# 启用自动偏移补偿
paint.property("offsetCompensation").setValue(true, 0)
paint.property("compensationRange").setValue(10, 0)  # 补偿范围（像素）
paint.property("compensationSmooth").setValue(0.5, 0)  # 平滑度
```

### 6.4 跟踪质量检测

```python
# 启用跟踪质量检测
paint.property("qualityCheck").setValue(true, 0)
paint.property("qualityThreshold").setValue(0.7, 0)  # 质量阈值
paint.property("markLowQuality").setValue(true, 0)  # 标记低质量帧
```

---

## 七、复杂运动处理

### 7.1 旋转运动

```python
# 处理旋转运动
paint.property("rotationTrack").setValue(true, 0)
paint.property("rotationRange").setValue(360, 0)  # 旋转范围
paint.property("rotationSmooth").setValue(0.3, 0)  # 旋转平滑
```

### 7.2 缩放运动

```python
# 处理缩放运动
paint.property("scaleTrack").setValue(true, 0)
paint.property("scaleRange").setValue([0.5, 2.0], 0)  # 缩放范围
paint.property("scaleSmooth").setValue(0.3, 0)
paint.property("brushScaleWithObject").setValue(true, 0)  # 笔刷跟随缩放
```

### 7.3 透视变化

```python
# 处理透视变化
paint.property("perspectiveTrack").setValue(true, 0)
paint.property("perspectiveMode").setValue("corner_pin", 0)
paint.property("perspectiveSmooth").setValue(0.5, 0)
```

### 7.4 遮挡处理

```python
# 遮挡时自动暂停
paint.property("occlusionDetect").setValue(true, 0)
paint.property("occlusionThreshold").setValue(0.5, 0)
paint.property("occlusionAction").setValue("pause", 0)  # 暂停/插值
```

---

## 八、性能优化与输出

### 8.1 性能优化策略

| 策略 | 说明 | 效果 |
|------|------|------|
| 区域限制 | 使用 RotoNode 限制 Paint 作用范围 | 减少计算量 |
| 分辨率适配 | 低分辨率预览，高分辨率输出 | 提高预览速度 |
| 帧间隔 | 设置处理帧间隔 | 减少处理时间 |
| 多线程 | 启用多线程计算 | 加速处理 |

### 8.2 缓存配置

```python
# 启用缓存
paint.property("useCache").setValue(true, 0)
paint.property("cacheSize").setValue(2048, 0)  # 缓存大小（MB）
paint.property("cacheRange").setValue(20, 0)  # 缓存帧范围
```

### 8.3 输出设置

```python
out_node = Node("OutputNode")
out_node.property("path").setValue("D:/output/auto_repair.####.exr", 0)
out_node.property("format").setValue("exr", 0)
out_node.property("compression").setValue("zip", 0)
out_node.property("depth").setValue("32f", 0)
out_node.property("channels").setValue("rgba", 0)
```

### 8.4 跟踪数据导出

```python
# 导出跟踪数据供 AE 使用
tracking_export = {
    "version": "2.0",
    "source": "silhouette",
    "tracking": {
        "trackType": "planar",
        "trackers": [
            {
                "name": "Paint_Track",
                "frames": tracking_data["frames"],
                "exportFormat": "ae_keyframes",
            }
        ],
        "nullObjectName": "Silhouette_Paint_Tracker",
    },
    "paint": {
        "propagation": "tracked",
        "outputSequence": "auto_repair.####.exr",
    },
}
```

---

## 总结

Paint 跟踪与自动修复是 Silhouette 的高级功能，关键要点：

1. **跟踪驱动**: 使用 TrackerNode 提供跟踪数据，驱动 Paint 笔触
2. **传播模式**: 根据场景选择 tracked/auto/interpolate 模式
3. **智能修复**: 启用自适应笔刷、智能采样源、多源融合
4. **偏移修正**: 定期检查并修正跟踪偏移
5. **复杂运动**: 配置旋转、缩放、透视跟踪参数
6. **性能优化**: 合理使用缓存、区域限制、多线程

通过合理配置传播模式和智能修复参数，可以大幅提升 Paint 修复的自动化程度和效果质量。
