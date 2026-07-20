# Silhouette Paint与Roto联合工作流

> 分类: Paint修复专题
> 更新日期: 2026-07-11
> 概述: Paint 与 Roto 联合工作流详解，包括遮罩驱动修复、区域限制、分层处理、数据交互等高级技术，实现高效精确的复杂修复任务。

## 目录

1. [联合工作流概述](#一联合工作流概述)
2. [遮罩驱动修复](#二遮罩驱动修复)
3. [区域限制技术](#三区域限制技术)
4. [分层处理策略](#四分层处理策略)
5. [数据交互机制](#五数据交互机制)
6. [复杂场景实战](#六复杂场景实战)
7. [优化与最佳实践](#七优化与最佳实践)
8. [输出与集成](#八输出与集成)

---

## 一、联合工作流概述

### 1.1 Paint 与 Rolo 的协同价值

| 维度 | 单独 Paint | Paint + Roto 联合 |
|------|-----------|------------------|
| 作用范围 | 全画面 | 精确限定区域 |
| 边缘控制 | 依赖笔刷硬度 | 遮罩边缘精确控制 |
| 多层处理 | 难以分层 | 清晰的层级结构 |
| 修改灵活性 | 修改需重绘 | 调整遮罩即可 |
| 自动化程度 | 手动为主 | 跟踪驱动遮罩 |

### 1.2 联合工作流模式

```
模式1: Roto 遮罩 → 限制 Paint 作用范围
模式2: Roto 提取目标 → Paint 修复背景
模式3: Roto 分层 → 分层 Paint 修复
模式4: Roto 跟踪 → Paint 跟随运动
```

### 1.3 节点连接结构

```
SourceNode ──┬── RotoNode（生成遮罩）
             │       │
             │       └──→ PaintNode（遮罩限制）
             │              │
             └──────────────┴──→ OutputNode
```

---

## 二、遮罩驱动修复

### 2.1 基础架构

```python
from fx import *

# 创建联合工作流
proj = activeProject() or Project()
activate(proj)

session = activeSession() or Session()
session.label = "Roto_Paint_Combined"
activate(session)
proj.addItem(session)

# 源节点
src = Node("SourceNode")
src.property("mediaPath").setValue("D:/footage/scene.####.exr", 0)
src.property("frameRate").setValue(24.0, 0)
session.addNode(src)

# Roto 节点 - 创建修复区域遮罩
roto = Node("RotoNode")
roto.label = "Repair_Mask"
roto.property("matte.mode").setValue("alpha", 0)
roto.property("alpha.blur").setValue(2.0, 0)  # 边缘模糊
roto.property("motionBlur").setValue(true, 0)  # 运动模糊
session.addNode(roto)

# Paint 节点 - 受遮罩限制
paint = Node("PaintNode")
paint.label = "Masked_Paint"
paint.property("brush.size").setValue(25.0, 0)
paint.property("brush.hardness").setValue(0.5, 0)
paint.property("brush.flow").setValue(0.8, 0)
paint.property("mode").setValue("clone", 0)
paint.property("useMatte").setValue(true, 0)  # 启用遮罩限制
paint.property("matteSource").setValue("Repair_Mask", 0)  # 指定遮罩源
session.addNode(paint)

# 输出节点
out_node = Node("OutputNode")
out_node.property("path").setValue("D:/output/repaired.####.exr", 0)
out_node.property("format").setValue("exr", 0)
session.addNode(out_node)

# 连接节点
src.outputs[0].connect(roto.inputs[1])  # Roto 主输入
src.outputs[0].connect(paint.inputs[0])  # Paint 源输入
roto.outputs[0].connect(paint.inputs[0])  # 遮罩输入
paint.outputs[0].connect(out_node.inputs[0])
```

### 2.2 遮罩参数配置

| 参数 | 说明 | 推荐值 |
|------|------|--------|
| matte.mode | 遮罩模式 | "alpha" |
| alpha.blur | 边缘模糊 | 1.0-3.0 |
| matte.invert | 反转遮罩 | false |
| motionBlur | 运动模糊 | true |
| motionBlur.shutter | 快门时间 | 0.5 |

---

## 三、区域限制技术

### 3.1 遮罩限制模式

```python
# 遮罩限制模式
paint.property("useMatte").setValue(true, 0)
paint.property("matteMode").setValue("limit", 0)  # 限制模式
paint.property("matteSource").setValue("Repair_Mask", 0)
```

### 3.2 限制模式类型

| 模式 | 说明 | 适用场景 |
|------|------|---------|
| limit | 仅在遮罩内绘制 | 局部修复 |
| exclude | 遮罩外绘制 | 避开特定区域 |
| blend | 遮罩边缘混合 | 自然过渡 |
| mask_only | 仅显示遮罩 | 预览遮罩 |

### 3.3 多区域限制

```python
# 创建多个遮罩区域
regions = [
    {"name": "Face_Region", "blur": 2.0, "mode": "limit"},
    {"name": "Body_Region", "blur": 3.0, "mode": "limit"},
    {"name": "Background_Region", "blur": 5.0, "mode": "limit"},
]

for region in regions:
    roto = Node("RotoNode")
    roto.label = region["name"]
    roto.property("matte.mode").setValue("alpha", 0)
    roto.property("alpha.blur").setValue(region["blur"], 0)
    session.addNode(roto)

# 为每个区域创建独立 Paint
for region in regions:
    paint = Node("PaintNode")
    paint.label = f"Paint_{region['name']}"
    paint.property("useMatte").setValue(true, 0)
    paint.property("matteSource").setValue(region["name"], 0)
    paint.property("matteMode").setValue(region["mode"], 0)
    session.addNode(paint)
```

---

## 四、分层处理策略

### 4.1 分层架构

```
层1: 背景层 - 背景 Paint 修复
层2: 主体层 - 主体 Paint 修复
层3: 细节层 - 细节 Paint 修复
层4: 融合层 - 边缘融合处理
```

### 4.2 分层实现

```python
# 分层处理实现
def create_layered_pipeline():
    """创建分层修复管线"""

    # 背景层
    bg_roto = Node("RotoNode")
    bg_roto.label = "BG_Mask"
    bg_roto.property("alpha.blur").setValue(5.0, 0)
    session.addNode(bg_roto)

    bg_paint = Node("PaintNode")
    bg_paint.label = "BG_Paint"
    bg_paint.property("brush.size").setValue(50.0, 0)
    bg_paint.property("brush.hardness").setValue(0.3, 0)
    bg_paint.property("mode").setValue("clone", 0)
    bg_paint.property("useMatte").setValue(true, 0)
    bg_paint.property("matteSource").setValue("BG_Mask", 0)
    session.addNode(bg_paint)

    # 主体层
    subject_roto = Node("RotoNode")
    subject_roto.label = "Subject_Mask"
    subject_roto.property("alpha.blur").setValue(2.0, 0)
    session.addNode(subject_roto)

    subject_paint = Node("PaintNode")
    subject_paint.label = "Subject_Paint"
    subject_paint.property("brush.size").setValue(20.0, 0)
    subject_paint.property("brush.hardness").setValue(0.5, 0)
    subject_paint.property("mode").setValue("repair", 0)
    subject_paint.property("useMatte").setValue(true, 0)
    subject_paint.property("matteSource").setValue("Subject_Mask", 0)
    session.addNode(subject_paint)

    # 细节层
    detail_roto = Node("RotoNode")
    detail_roto.label = "Detail_Mask"
    detail_roto.property("alpha.blur").setValue(0.5, 0)
    session.addNode(detail_roto)

    detail_paint = Node("PaintNode")
    detail_paint.label = "Detail_Paint"
    detail_paint.property("brush.size").setValue(5.0, 0)
    detail_paint.property("brush.hardness").setValue(0.8, 0)
    detail_paint.property("mode").setValue("clone", 0)
    detail_paint.property("useMatte").setValue(true, 0)
    detail_paint.property("matteSource").setValue("Detail_Mask", 0)
    session.addNode(detail_paint)

    # 连接
    src.outputs[0].connect(bg_roto.inputs[1])
    src.outputs[0].connect(bg_paint.inputs[0])
    bg_roto.outputs[0].connect(bg_paint.inputs[0])

    bg_paint.outputs[0].connect(subject_paint.inputs[0])
    src.outputs[0].connect(subject_roto.inputs[1])
    subject_roto.outputs[0].connect(subject_paint.inputs[0])

    subject_paint.outputs[0].connect(detail_paint.inputs[0])
    src.outputs[0].connect(detail_roto.inputs[1])
    detail_roto.outputs[0].connect(detail_paint.inputs[0])
```

### 4.3 分层参数策略

| 层级 | 笔刷大小 | 硬度 | 模式 | 模糊 |
|------|---------|------|------|------|
| 背景层 | 50 | 0.3 | clone | 5.0 |
| 主体层 | 20 | 0.5 | repair | 2.0 |
| 细节层 | 5 | 0.8 | clone | 0.5 |
| 融合层 | 15 | 0.4 | repair | 3.0 |

---

## 五、数据交互机制

### 5.1 Roto 到 Paint 的数据流

```
RotoNode 生成遮罩 → PaintNode 读取遮罩 → 限制笔触作用范围
```

### 5.2 遮罩数据格式

```python
# 遮罩数据结构
mask_data = {
    "version": "2026.0.2",
    "node": "Repair_Mask",
    "type": "alpha",
    "frames": [
        {
            "frame": 0,
            "shapes": [
                {
                    "type": "x-spline",
                    "points": [[100, 200], [200, 200], [200, 300], [100, 300]],
                    "closed": true,
                    "feather": 2.0
                }
            ]
        }
    ]
}
```

### 5.3 跟踪数据共享

```python
# 共享跟踪数据
tracker = Node("TrackerNode")
tracker.label = "Shared_Track"
tracker.property("trackType").setValue("planar", 0)
session.addNode(tracker)

# Roto 使用跟踪数据
roto.property("trackSource").setValue("Shared_Track", 0)
roto.property("trackApply").setValue(true, 0)

# Paint 使用相同跟踪数据
paint.property("trackSource").setValue("Shared_Track", 0)
paint.property("propagation").setValue("tracked", 0)
```

---

## 六、复杂场景实战

### 6.1 人物擦除场景

```python
# 人物擦除联合工作流
def create_person_removal_pipeline():
    proj = activeProject() or Project()
    activate(proj)

    session = activeSession() or Session()
    session.label = "Person_Removal"
    activate(session)
    proj.addItem(session)

    # 源节点
    src = Node("SourceNode")
    src.property("mediaPath").setValue("D:/footage/scene.####.exr", 0)
    src.property("frameRate").setValue(24.0, 0)
    session.addNode(src)

    # 人物遮罩（精确）
    person_roto = Node("RotoNode")
    person_roto.label = "Person_Mask"
    person_roto.property("matte.mode").setValue("alpha", 0)
    person_roto.property("alpha.blur").setValue(1.5, 0)
    person_roto.property("motionBlur").setValue(true, 0)
    session.addNode(person_roto)

    # 人物跟踪
    person_track = Node("TrackerNode")
    person_track.label = "Person_Track"
    person_track.property("trackType").setValue("planar", 0)
    person_track.property("accuracy").setValue("high", 0)
    session.addNode(person_track)

    # 背景修复 Paint
    bg_paint = Node("PaintNode")
    bg_paint.label = "BG_Restore"
    bg_paint.property("brush.size").setValue(40.0, 0)
    bg_paint.property("brush.hardness").setValue(0.4, 0)
    bg_paint.property("mode").setValue("clone", 0)
    bg_paint.property("useMatte").setValue(true, 0)
    bg_paint.property("matteSource").setValue("Person_Mask", 0)
    bg_paint.property("matteMode").setValue("limit", 0)
    bg_paint.property("propagation").setValue("tracked", 0)
    bg_paint.property("trackSource").setValue("Person_Track", 0)
    session.addNode(bg_paint)

    # 细节修复
    detail_paint = Node("PaintNode")
    detail_paint.label = "Detail_Fix"
    detail_paint.property("brush.size").setValue(10.0, 0)
    detail_paint.property("brush.hardness").setValue(0.6, 0)
    detail_paint.property("mode").setValue("repair", 0)
    detail_paint.property("useMatte").setValue(true, 0)
    detail_paint.property("matteSource").setValue("Person_Mask", 0)
    session.addNode(detail_paint)

    # 输出
    out_node = Node("OutputNode")
    out_node.property("path").setValue("D:/output/person_removed.####.exr", 0)
    out_node.property("format").setValue("exr", 0)
    session.addNode(out_node)

    # 连接
    src.outputs[0].connect(person_roto.inputs[1])
    src.outputs[0].connect(person_track.inputs[0])
    src.outputs[0].connect(bg_paint.inputs[0])
    person_roto.outputs[0].connect(bg_paint.inputs[0])
    bg_paint.outputs[0].connect(detail_paint.inputs[0])
    detail_paint.outputs[0].connect(out_node.inputs[0])
```

### 6.2 多物体分层修复

```python
# 多物体分层修复
def create_multi_object_pipeline():
    objects = ["Object_A", "Object_B", "Object_C"]

    for obj in objects:
        # 每个物体一个 Roto
        roto = Node("RotoNode")
        roto.label = f"{obj}_Mask"
        roto.property("alpha.blur").setValue(2.0, 0)
        session.addNode(roto)

        # 每个物体一个 Paint
        paint = Node("PaintNode")
        paint.label = f"{obj}_Paint"
        paint.property("brush.size").setValue(30.0, 0)
        paint.property("mode").setValue("clone", 0)
        paint.property("useMatte").setValue(true, 0)
        paint.property("matteSource").setValue(f"{obj}_Mask", 0)
        session.addNode(paint)
```

---

## 七、优化与最佳实践

### 7.1 性能优化

| 优化策略 | 说明 | 效果 |
|---------|------|------|
| 遮罩简化 | 使用简单形状 | 减少计算量 |
| 区域限制 | 限制 Paint 作用范围 | 提高速度 |
| 缓存遮罩 | 缓存 Roto 结果 | 避免重复计算 |
| 分段处理 | 分段渲染 | 减少内存占用 |

### 7.2 质量最佳实践

```python
# 质量优化配置
def optimize_quality():
    # Roto 质量优化
    roto.property("antialias").setValue(1.0, 0)  # 最高抗锯齿
    roto.property("motionBlur").setValue(true, 0)
    roto.property("motionBlur.shutter").setValue(0.5, 0)
    roto.property("alpha.blur").setValue(2.0, 0)  # 适度模糊

    # Paint 质量优化
    paint.property("colorMatch").setValue(true, 0)  # 色彩匹配
    paint.property("texturePreserve").setValue(true, 0)  # 纹理保留
    paint.property("temporalSmooth").setValue(true, 0)  # 时间平滑
    paint.property("temporalRange").setValue(3, 0)
```

### 7.3 工作流最佳实践

1. **先 Roto 后 Paint**: 先完成遮罩，再进行修复
2. **从大到小**: 先大面积修复，后细节处理
3. **分层独立**: 每层独立节点，便于修改
4. **命名规范**: 清晰的节点命名，便于管理
5. **定期检查**: 每完成一层，检查效果

---

## 八、输出与集成

### 8.1 输出配置

```python
# 联合工作流输出
out_node = Node("OutputNode")
out_node.property("path").setValue("D:/output/combined_repair.####.exr", 0)
out_node.property("format").setValue("exr", 0)
out_node.property("compression").setValue("zip", 0)
out_node.property("depth").setValue("32f", 0)
out_node.property("channels").setValue("rgba", 0)
```

### 8.2 多通道输出

```python
# 同时输出修复结果和遮罩
# 修复结果输出
result_out = Node("OutputNode")
result_out.label = "Result_Output"
result_out.property("path").setValue("D:/output/result.####.exr", 0)
result_out.property("channels").setValue("rgba", 0)
session.addNode(result_out)

# 遮罩输出
mask_out = Node("OutputNode")
mask_out.label = "Mask_Output"
mask_out.property("path").setValue("D:/output/mask.####.exr", 0)
mask_out.property("channels").setValue("alpha", 0)
session.addNode(mask_out)
```

### 8.3 与 AE 集成

```python
# 生成 AE 集成配置
ae_config = {
    "version": "2.0",
    "source": "silhouette",
    "aeIntegration": {
        "compName": "Roto_Paint_Combined",
        "importPath": "D:/output/",
        "applyAs": "replace_footage",
        "targetLayer": "selected",
    },
    "roto": {
        "matteSequence": "mask.####.exr",
        "frameRange": [0, 100],
    },
    "paint": {
        "outputSequence": "result.####.exr",
        "frameRange": [0, 100],
    },
}
```

---

## 总结

Paint 与 Roto 联合工作流是 Silhouette 的高级应用模式，关键要点：

1. **遮罩驱动**: 使用 RotoNode 生成遮罩，限制 Paint 作用范围
2. **分层处理**: 将复杂场景分层处理，每层独立控制
3. **数据共享**: 跟踪数据在 Roto 和 Paint 之间共享
4. **区域限制**: 精确控制修复区域，避免误修复
5. **质量优化**: 启用抗锯齿、运动模糊、色彩匹配等质量参数

通过合理组合 Roto 和 Paint 节点，可以实现精确、高效、高质量的复杂修复任务，满足专业级影视后期制作需求。
