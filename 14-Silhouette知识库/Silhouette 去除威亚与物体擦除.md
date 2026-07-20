# Silhouette 去除威亚与物体擦除

> 分类: Paint修复专题
> 更新日期: 2026-07-11
> 概述: 威亚去除、物体擦除的多帧修复工作流、背景重建与边缘融合技术详解，覆盖从单帧修复到长序列批量处理的完整方案。

## 目录

1. [威亚去除概述](#一威亚去除概述)
2. [威亚检测与区域规划](#二威亚检测与区域规划)
3. [多帧修复策略](#三多帧修复策略)
4. [背景重建技术](#四背景重建技术)
5. [边缘融合与色彩匹配](#五边缘融合与色彩匹配)
6. [物体擦除工作流](#六物体擦除工作流)
7. [复杂场景处理](#七复杂场景处理)
8. [质量检查与输出](#八质量检查与输出)

---

## 一、威亚去除概述

### 1.1 威亚去除的挑战

威亚去除是影视后期最常见的修复任务之一，其难点在于：

- **细长形状**: 威亚通常为细长线条，跨越多个像素区域
- **运动模糊**: 快速运动时威亚产生模糊，边缘不清晰
- **背景复杂**: 威亚经过的区域背景可能包含复杂纹理
- **多帧连续性**: 需要保证多帧之间的修复结果稳定无闪烁
- **光影变化**: 威亚投影和反射需要一并处理

### 1.2 Silhouette Paint 优势

| 优势 | 说明 |
|------|------|
| 跟踪驱动修复 | 利用 PlanarTracker 跟踪威亚轨迹，自动驱动 Clone 笔刷 |
| 多种修复模式 | Clone、Repair、Erase 三种模式应对不同场景 |
| 序列传播 | 单帧修复结果可自动传播到相邻帧 |
| 节点组合 | PaintNode 与 RotoNode、TrackerNode 灵活组合 |
| 矢量笔触 | 笔触为矢量数据，可随时调整大小、位置、不透明度 |

### 1.3 典型工作流

```
素材分析 → 威亚检测 → 跟踪定位 → 背景采样 → 多帧修复 → 边缘融合 → 质量检查
```

---

## 二、威亚检测与区域规划

### 2.1 威亚检测方法

#### 2.1.1 视觉检测

```python
# 在 Silhouette Viewer 中标记威亚区域
# 使用 RotoNode 创建威亚遮罩，便于后续 Paint 修复
roto = Node("RotoNode")
roto.label = "Wire_Mask"
roto.property("matte.mode").setValue("alpha", 0)
roto.property("stroke").setValue(true, 0)
roto.property("stroke.width").setValue(2.0, 0)
roto.property("stroke.color").setValue([1, 0, 0], 0)
session.addNode(roto)
```

#### 2.1.2 自动检测辅助

- **对比帧分析**: 利用相邻帧差异自动定位威亚
- **色彩分析**: 威亚通常具有与背景不同的色彩特征
- **运动分析**: 威亚运动模式与主体不同，可通过跟踪数据区分

### 2.2 区域规划原则

| 规划维度 | 建议 |
|---------|------|
| 分段处理 | 长威亚分段处理，每段单独跟踪 |
| 优先级 | 先处理背景简单区域，后处理复杂区域 |
| 重叠区 | 威亚与主体重叠区单独标记，避免误修复 |
| 边缘区 | 威亚经过物体边缘时，需保留物体边缘完整性 |

### 2.3 威亚分段策略

```python
# 多段威亚分别处理
wire_segments = [
    {"start": [100, 200], "end": [500, 220], "label": "Wire_Seg1"},
    {"start": [500, 220], "end": [900, 240], "label": "Wire_Seg2"},
    {"start": [900, 240], "end": [1200, 260], "label": "Wire_Seg3"},
]

for seg in wire_segments:
    paint = Node("PaintNode")
    paint.label = seg["label"]
    paint.property("brush.size").setValue(15.0, 0)
    paint.property("brush.hardness").setValue(0.4, 0)
    paint.property("mode").setValue("clone", 0)
    session.addNode(paint)
```

---

## 三、多帧修复策略

### 3.1 单帧修复 + 自动传播

适用于背景静态、威亚运动规律的场景：

```python
paint = Node("PaintNode")
paint.label = "Wire_Removal"
paint.property("brush.size").setValue(20.0, 0)
paint.property("brush.hardness").setValue(0.5, 0)
paint.property("brush.flow").setValue(0.8, 0)
paint.property("mode").setValue("clone", 0)
paint.property("propagation").setValue("tracked", 0)
paint.property("sampleOffset").setValue([0, 30], 0)
```

### 3.2 关键帧 + 插值修复

适用于威亚轨迹变化较大的场景：

| 帧 | 操作 | 说明 |
|----|------|------|
| 0 | 手动修复 | 设置关键帧，调整 Clone 源 |
| 25 | 手动修复 | 调整 Clone 源位置 |
| 50 | 手动修复 | 调整 Clone 源位置 |
| 75 | 手动修复 | 调整 Clone 源位置 |
| 100 | 手动修复 | 调整 Clone 源位置 |

```python
# 关键帧插值修复
keyframes = [0, 25, 50, 75, 100]
sample_positions = [
    [100, 200],  # frame 0
    [120, 205],  # frame 25
    [140, 210],  # frame 50
    [160, 215],  # frame 75
    [180, 220],  # frame 100
]

for frame, pos in zip(keyframes, sample_positions):
    paint.property("sampleOffset").setValue(pos, frame)
```

### 3.3 逐帧修复

适用于复杂场景、自动传播失效的情况：

- 每帧手动调整 Clone 源
- 利用时间线导航快速切换帧
- 建议使用数位笔进行精细操作
- 开启 Onion Skin（洋葱皮）辅助对齐

### 3.4 修复模式选择

| 场景 | 推荐模式 | 参数建议 |
|------|---------|---------|
| 静态背景 | Clone | sampleOffset=[0,30], flow=0.8 |
| 动态背景 | Repair | brush.size=25, hardness=0.6 |
| 边缘修复 | Clone + Repair 组合 | 分层处理 |
| 细密纹理 | Clone | brush.size=10, hardness=0.3 |

---

## 四、背景重建技术

### 4.1 背景采样策略

#### 4.1.1 同帧采样

从威亚附近的干净背景区域采样：

```python
# 威亚位于 [500, 300]，从下方干净区域采样
paint.property("cloneSource").setValue("current", 0)
paint.property("sampleOffset").setValue([0, 50], 0)  # 下方50像素采样
```

#### 4.1.2 跨帧采样

从相邻帧的干净区域采样，适用于威亚经过区域在当前帧无法找到干净背景的情况：

```python
# 从前一帧采样
paint.property("cloneSource").setValue("frame", 0)
paint.property("cloneFrame").setValue(-1, 0)  # 前一帧
paint.property("sampleOffset").setValue([0, 0], 0)
```

#### 4.1.3 静态背景帧采样

使用无威亚的空镜帧作为背景源：

```python
# 使用 clean plate 作为背景源
paint.property("cloneSource").setValue("external", 0)
paint.property("externalSource").setValue("D:/footage/clean_plate.####.exr", 0)
```

### 4.2 背景重建方法

| 方法 | 适用场景 | 优势 | 劣势 |
|------|---------|------|------|
| Clone 复制 | 简单纹理 | 速度快、效果自然 | 不适合复杂纹理 |
| Repair 修复 | 复杂纹理 | 自动融合、边缘平滑 | 计算量大 |
| 多点采样 | 渐变背景 | 色彩过渡自然 | 需手动调整 |
| 外部背景 | 复杂场景 | 效果最佳 | 需要 clean plate |

### 4.3 复杂背景处理

```python
# 多笔刷组合处理复杂背景
# 笔刷1: 主背景 Clone
paint1 = Node("PaintNode")
paint1.label = "BG_Clone"
paint1.property("mode").setValue("clone", 0)
paint1.property("brush.size").setValue(30.0, 0)

# 笔刷2: 细节 Repair
paint2 = Node("PaintNode")
paint2.label = "Detail_Repair"
paint2.property("mode").setValue("repair", 0)
paint2.property("brush.size").setValue(10.0, 0)
paint2.property("brush.hardness").setValue(0.7, 0)

# 笔刷3: 边缘融合
paint3 = Node("PaintNode")
paint3.label = "Edge_Blend"
paint3.property("mode").setValue("repair", 0)
paint3.property("brush.size").setValue(5.0, 0)
paint3.property("brush.flow").setValue(0.5, 0)
```

---

## 五、边缘融合与色彩匹配

### 5.1 边缘融合技术

#### 5.1.1 羽化边缘

```python
# 使用较低硬度实现边缘羽化
paint.property("brush.hardness").setValue(0.3, 0)
paint.property("brush.size").setValue(25.0, 0)
```

#### 5.1.2 多层叠加

```python
# 多层低不透明度叠加，实现自然过渡
paint.property("brush.opacity").setValue(0.3, 0)
paint.property("brush.flow").setValue(0.5, 0)
# 多次绘制，逐渐累积
```

#### 5.1.3 色彩匹配

```python
# 使用 Repair 模式自动匹配色彩
paint.property("mode").setValue("repair", 0)
paint.property("colorMatch").setValue(true, 0)
paint.property("colorRange").setValue(0.2, 0)
```

### 5.2 色彩匹配参数

| 参数 | 默认值 | 范围 | 说明 |
|------|--------|------|------|
| colorMatch | false | true/false | 是否启用色彩匹配 |
| colorRange | 0.1 | 0.0-1.0 | 色彩匹配范围 |
| brightness | 0.0 | -1.0 to 1.0 | 亮度调整 |
| contrast | 0.0 | -1.0 to 1.0 | 对比度调整 |
| saturation | 0.0 | -1.0 to 1.0 | 饱和度调整 |

### 5.3 光影保持

威亚去除后，需要保持原始场景的光影关系：

- **高光保留**: 物体表面的高光不应被破坏
- **阴影重建**: 威亚遮挡的阴影需要重建
- **反射处理**: 威亚在物体表面的反射需要清除
- **环境光**: 修复区域的环境光应与周围一致

---

## 六、物体擦除工作流

### 6.1 物体擦除与威亚去除的差异

| 维度 | 威亚去除 | 物体擦除 |
|------|---------|---------|
| 形状 | 细长线条 | 不规则区域 |
| 面积 | 较小 | 较大 |
| 背景 | 通常简单 | 通常复杂 |
| 跟踪 | 沿轨迹跟踪 | 区域跟踪 |
| 修复 | Clone 为主 | Clone + Repair 组合 |

### 6.2 物体擦除工作流

```
1. 标记物体区域（RotoNode）
2. 跟踪物体运动（TrackerNode）
3. 采样背景区域
4. 多帧修复（PaintNode）
5. 边缘融合
6. 质量检查
```

### 6.3 实现代码

```python
from fx import *

# 创建物体擦除管线
proj = activeProject() or Project()
activate(proj)

session = activeSession() or Session()
session.label = "Object_Removal"
activate(session)
proj.addItem(session)

# 源节点
src = Node("SourceNode")
src.property("mediaPath").setValue("D:/footage/scene.####.exr", 0)
src.property("frameRate").setValue(24.0, 0)
session.addNode(src)

# 物体遮罩
roto = Node("RotoNode")
roto.label = "Object_Mask"
roto.property("matte.mode").setValue("alpha", 0)
roto.property("alpha.blur").setValue(2.0, 0)
session.addNode(roto)

# 跟踪节点
track = Node("TrackerNode")
track.label = "Object_Track"
track.property("trackType").setValue("planar", 0)
track.property("searchArea").setValue(31, 0)
track.property("accuracy").setValue("high", 0)
session.addNode(track)

# Paint 修复节点
paint = Node("PaintNode")
paint.label = "Object_Paint"
paint.property("brush.size").setValue(40.0, 0)
paint.property("brush.hardness").setValue(0.4, 0)
paint.property("brush.flow").setValue(0.8, 0)
paint.property("mode").setValue("clone", 0)
paint.property("propagation").setValue("tracked", 0)
session.addNode(paint)

# 输出节点
out_node = Node("OutputNode")
out_node.property("path").setValue("D:/output/clean.####.exr", 0)
out_node.property("format").setValue("exr", 0)
session.addNode(out_node)

# 连接节点
src.outputs[0].connect(roto.inputs[1])
src.outputs[0].connect(track.inputs[0])
src.outputs[0].connect(paint.inputs[0])
roto.outputs[0].connect(paint.inputs[0])
paint.outputs[0].connect(out_node.inputs[0])
```

---

## 七、复杂场景处理

### 7.1 威亚经过主体

当威亚经过演员或物体时，需要分层处理：

1. **背景层**: 威亚经过背景的部分，使用 Clone 修复
2. **主体层**: 威亚经过主体的部分，需要保留主体细节
3. **边缘层**: 威亚经过主体边缘的部分，使用 Repair 模式精细修复

```python
# 分层 Paint 节点
bg_paint = Node("PaintNode")
bg_paint.label = "BG_Wire"
bg_paint.property("mode").setValue("clone", 0)

subject_paint = Node("PaintNode")
subject_paint.label = "Subject_Wire"
subject_paint.property("mode").setValue("repair", 0)
subject_paint.property("brush.size").setValue(8.0, 0)

edge_paint = Node("PaintNode")
edge_paint.label = "Edge_Wire"
edge_paint.property("mode").setValue("repair", 0)
edge_paint.property("brush.size").setValue(3.0, 0)
edge_paint.property("brush.hardness").setValue(0.8, 0)
```

### 7.2 多威亚处理

```python
# 多条威亚同时处理
wires = [
    {"id": 1, "position": [200, 300], "size": 15},
    {"id": 2, "position": [500, 350], "size": 12},
    {"id": 3, "position": [800, 400], "size": 18},
]

for wire in wires:
    paint = Node("PaintNode")
    paint.label = f"Wire_{wire['id']}"
    paint.property("brush.size").setValue(float(wire["size"]), 0)
    paint.property("mode").setValue("clone", 0)
    session.addNode(paint)
```

### 7.3 运动模糊威亚

```python
# 处理运动模糊的威亚
paint.property("brush.size").setValue(25.0, 0)
paint.property("brush.hardness").setValue(0.2, 0)  # 低硬度模拟模糊
paint.property("brush.flow").setValue(0.6, 0)
paint.property("motionBlur").setValue(true, 0)
paint.property("motionBlur.shutter").setValue(0.5, 0)
```

---

## 八、质量检查与输出

### 8.1 质量检查清单

- [ ] 修复区域无残留威亚痕迹
- [ ] 多帧播放无闪烁
- [ ] 边缘过渡自然
- [ ] 色彩匹配准确
- [ ] 光影关系保持
- [ ] 细节纹理合理

### 8.2 闪烁检测

```python
# 启用差异检测
diff_check = Node("DifferenceNode")
diff_check.label = "Flicker_Check"
diff_check.property("threshold").setValue(0.05, 0)
diff_check.property("showDifference").setValue(true, 0)
```

### 8.3 输出设置

```python
out_node = Node("OutputNode")
out_node.property("path").setValue("D:/output/wire_removed.####.exr", 0)
out_node.property("format").setValue("exr", 0)
out_node.property("compression").setValue("zip", 0)
out_node.property("depth").setValue("32f", 0)
out_node.property("channels").setValue("rgba", 0)
```

### 8.4 与 AE 集成

```python
# 生成 AE 集成配置
ae_config = {
    "version": "2.0",
    "source": "silhouette",
    "aeIntegration": {
        "compName": "Wire_Removal",
        "importPath": "D:/output/",
        "applyAs": "replace_footage",
        "targetLayer": "selected",
    },
    "paint": {
        "outputSequence": "wire_removed.####.exr",
        "frameRange": [0, 100],
        "resolution": [1920, 1080],
    },
}
```

---

## 总结

威亚去除与物体擦除是 Silhouette Paint 模块的核心应用场景。关键要点：

1. **跟踪先行**: 利用 PlanarTracker 跟踪威亚/物体轨迹
2. **背景采样**: 选择合适的背景采样策略
3. **多帧连续**: 保证多帧修复结果稳定
4. **边缘融合**: 使用低硬度笔刷和 Repair 模式实现自然过渡
5. **质量检查**: 严格检查闪烁、色彩、光影等问题

通过合理组合 Clone、Repair、Erase 三种模式，配合跟踪数据驱动，可以高效完成各类威亚去除和物体擦除任务。
