# Silhouette 画面修复与数字化妆

> 分类: Paint修复专题
> 更新日期: 2026-07-11
> 概述: 画面修复与数字化妆技术详解，包括皮肤瑕疵去除、皱纹平滑、妆容调整、疤痕修复等美容级修复工作流。

## 目录

1. [数字化妆概述](#一数字化妆概述)
2. [皮肤分析与区域划分](#二皮肤分析与区域划分)
3. [瑕疵修复技术](#三瑕疵修复技术)
4. [皮肤平滑处理](#四皮肤平滑处理)
5. [妆容调整与色彩校正](#五妆容调整与色彩校正)
6. [疤痕与伤痕修复](#六疤痕与伤痕修复)
7. [多帧化妆一致性](#七多帧化妆一致性)
8. [质量评估与输出](#八质量评估与输出)

---

## 一、数字化妆概述

### 1.1 数字化妆的应用场景

| 场景 | 描述 | 技术要点 |
|------|------|---------|
| 瑕疵去除 | 去除痘痘、色斑、痣等 | Clone + Repair 组合 |
| 皱纹平滑 | 减弱皱纹、细纹 | Repair + 低不透明度 |
| 妆容调整 | 改变唇色、眼影、腮红 | 色彩校正 + Clone |
| 疤痕修复 | 去除手术疤、擦伤 | 多层 Clone + 边缘融合 |
| 美白提亮 | 整体肤色提亮 | Repair + 色彩调整 |
| 年龄逆推 | 减龄处理 | 综合技术组合 |

### 1.2 Silhouette 数字化妆优势

- **非破坏性**: 矢量笔触可随时调整
- **多帧跟踪**: 跟踪面部特征点，自动驱动修复
- **精细控制**: 笔刷大小、硬度、流量可独立调整
- **色彩匹配**: 自动匹配周围肤色
- **节点组合**: 与 RotoNode 配合实现区域限制

### 1.3 工作流概览

```
素材分析 → 面部跟踪 → 区域划分 → 瑕疵修复 → 皮肤平滑 → 色彩调整 → 多帧检查
```

---

## 二、皮肤分析与区域划分

### 2.1 皮肤区域识别

```python
from fx import *

# 创建面部 Roto 遮罩，限制 Paint 作用范围
face_roto = Node("RotoNode")
face_roto.label = "Face_Mask"
face_roto.property("matte.mode").setValue("alpha", 0)
face_roto.property("alpha.blur").setValue(3.0, 0)
session.addNode(face_roto)

# 分区遮罩
regions = {
    "forehead": "额头区域",
    "cheeks": "脸颊区域",
    "nose": "鼻部区域",
    "chin": "下巴区域",
    "eyes": "眼周区域",
}

for region_id, region_name in regions.items():
    roto = Node("RotoNode")
    roto.label = f"Mask_{region_id}"
    roto.property("matte.mode").setValue("alpha", 0)
    roto.property("alpha.blur").setValue(2.0, 0)
    session.addNode(roto)
```

### 2.2 面部特征点跟踪

```python
# 跟踪面部特征点，确保修复跟随面部运动
tracker = Node("TrackerNode")
tracker.label = "Face_Track"
tracker.property("trackType").setValue("point", 0)
tracker.property("searchArea").setValue(15, 0)
tracker.property("accuracy").setValue("high", 0)
tracker.property("patternSize").setValue(9, 0)
session.addNode(tracker)

# 特征点位置（参考）
features = {
    "left_eye": [640, 360],
    "right_eye": [800, 360],
    "nose_tip": [720, 420],
    "mouth_left": [680, 480],
    "mouth_right": [760, 480],
}
```

### 2.3 皮肤类型分析

| 皮肤类型 | 特征 | 修复策略 |
|---------|------|---------|
| 干性皮肤 | 纹理粗糙、易脱屑 | 低流量多次叠加 |
| 油性皮肤 | 反光强、毛孔粗大 | 降低反光、平滑毛孔 |
| 混合性 | T区油、U区干 | 分区处理 |
| 敏感性 | 泛红、毛细血管 | 降低红色、平滑 |

---

## 三、瑕疵修复技术

### 3.1 痘痘与色斑去除

```python
# 瑕疵修复 Paint 节点
paint = Node("PaintNode")
paint.label = "Blemish_Remove"
paint.property("brush.size").setValue(8.0, 0)
paint.property("brush.hardness").setValue(0.6, 0)
paint.property("brush.flow").setValue(0.8, 0)
paint.property("mode").setValue("repair", 0)
paint.property("colorMatch").setValue(true, 0)
paint.property("colorRange").setValue(0.15, 0)
session.addNode(paint)
```

### 3.2 修复参数详解

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| brush.size | 5-15 | 根据瑕疵大小调整 |
| brush.hardness | 0.5-0.7 | 中等硬度，避免边缘过硬 |
| brush.flow | 0.7-0.9 | 较高流量，一次修复到位 |
| mode | "repair" | 自动融合周围肤色 |
| colorMatch | true | 启用色彩匹配 |
| colorRange | 0.1-0.2 | 色彩匹配范围 |

### 3.3 多瑕疵批量处理

```python
# 批量修复多个瑕疵
blemishes = [
    {"pos": [650, 350], "size": 6},
    {"pos": [700, 380], "size": 8},
    {"pos": [750, 360], "size": 5},
    {"pos": [680, 420], "size": 7},
    {"pos": [730, 440], "size": 6},
]

for i, blemish in enumerate(blemishes):
    paint = Node("PaintNode")
    paint.label = f"Blemish_{i}"
    paint.property("brush.size").setValue(float(blemish["size"]), 0)
    paint.property("brush.hardness").setValue(0.6, 0)
    paint.property("mode").setValue("repair", 0)
    paint.property("colorMatch").setValue(true, 0)
    session.addNode(paint)
```

---

## 四、皮肤平滑处理

### 4.1 皱纹减弱

```python
# 皱纹减弱 - 低流量多次叠加
wrinkle_paint = Node("PaintNode")
wrinkle_paint.label = "Wrinkle_Smooth"
wrinkle_paint.property("brush.size").setValue(20.0, 0)
wrinkle_paint.property("brush.hardness").setValue(0.3, 0)
wrinkle_paint.property("brush.flow").setValue(0.3, 0)
wrinkle_paint.property("brush.opacity").setValue(0.4, 0)
wrinkle_paint.property("mode").setValue("repair", 0)
wrinkle_paint.property("colorMatch").setValue(true, 0)
wrinkle_paint.property("colorRange").setValue(0.2, 0)
session.addNode(wrinkle_paint)
```

### 4.2 平滑参数策略

| 处理强度 | brush.size | brush.flow | brush.opacity | 适用场景 |
|---------|-----------|------------|---------------|---------|
| 轻度 | 15-25 | 0.2-0.3 | 0.3-0.4 | 细纹、轻微瑕疵 |
| 中度 | 25-35 | 0.3-0.5 | 0.4-0.6 | 明显皱纹、毛孔 |
| 重度 | 35-50 | 0.5-0.7 | 0.6-0.8 | 深层皱纹、疤痕 |

### 4.3 保留皮肤纹理

过度平滑会使皮肤显得"塑料感"，需要保留自然纹理：

```python
# 启用纹理保留
paint.property("texturePreserve").setValue(true, 0)
paint.property("textureAmount").setValue(0.5, 0)  # 纹理保留强度
paint.property("textureScale").setValue(1.0, 0)   # 纹理缩放
```

---

## 五、妆容调整与色彩校正

### 5.1 唇色调整

```python
# 唇色调整
lip_paint = Node("PaintNode")
lip_paint.label = "Lip_Color"
lip_paint.property("brush.size").setValue(15.0, 0)
lip_paint.property("brush.hardness").setValue(0.5, 0)
lip_paint.property("brush.flow").setValue(0.5, 0)
lip_paint.property("brush.opacity").setValue(0.6, 0)
lip_paint.property("mode").setValue("repair", 0)
lip_paint.property("colorAdjust").setValue(true, 0)
lip_paint.property("hueShift").setValue(0.1, 0)    # 色相偏移
lip_paint.property("saturation").setValue(0.3, 0)  # 饱和度提升
lip_paint.property("brightness").setValue(0.1, 0)  # 亮度提升
session.addNode(lip_paint)
```

### 5.2 眼影调整

```python
# 眼影区域
eye_shadow = Node("PaintNode")
eye_shadow.label = "Eye_Shadow"
eye_shadow.property("brush.size").setValue(10.0, 0)
eye_shadow.property("brush.hardness").setValue(0.4, 0)
eye_shadow.property("brush.opacity").setValue(0.4, 0)
eye_shadow.property("mode").setValue("repair", 0)
eye_shadow.property("colorAdjust").setValue(true, 0)
eye_shadow.property("hueShift").setValue(-0.05, 0)
eye_shadow.property("saturation").setValue(0.2, 0)
session.addNode(eye_shadow)
```

### 5.3 腮红添加

```python
# 腮红
blush = Node("PaintNode")
blush.label = "Blush"
blush.property("brush.size").setValue(30.0, 0)
blush.property("brush.hardness").setValue(0.2, 0)
blush.property("brush.opacity").setValue(0.3, 0)
blush.property("brush.flow").setValue(0.4, 0)
blush.property("mode").setValue("repair", 0)
blush.property("colorAdjust").setValue(true, 0)
blush.property("hueShift").setValue(0.05, 0)    # 偏暖色
blush.property("saturation").setValue(0.3, 0)
session.addNode(blush)
```

### 5.4 色彩调整参数对照

| 妆容效果 | hueShift | saturation | brightness |
|---------|----------|------------|------------|
| 自然唇色 | 0.0 | 0.1 | 0.05 |
| 红唇 | 0.0 | 0.4 | 0.0 |
| 粉嫩唇 | 0.1 | 0.3 | 0.1 |
| 深色唇 | -0.05 | 0.2 | -0.1 |
| 眼影-暖 | 0.05 | 0.2 | 0.0 |
| 眼影-冷 | -0.1 | 0.2 | 0.0 |
| 腮红-自然 | 0.05 | 0.3 | 0.1 |
| 腮红-浓郁 | 0.0 | 0.5 | 0.05 |

---

## 六、疤痕与伤痕修复

### 6.1 疤痕修复工作流

```
1. 标记疤痕区域（RotoNode）
2. 跟踪疤痕运动（TrackerNode）
3. 采样周围皮肤（PaintNode Clone）
4. 多层修复（多次 Clone 叠加）
5. 边缘融合（Repair 模式）
6. 纹理重建（细节笔刷）
```

### 6.2 实现代码

```python
# 疤痕修复管线
def create_scar_repair_pipeline():
    proj = activeProject() or Project()
    activate(proj)

    session = activeSession() or Session()
    session.label = "Scar_Repair"
    activate(session)
    proj.addItem(session)

    # 源节点
    src = Node("SourceNode")
    src.property("mediaPath").setValue("D:/footage/portrait.####.exr", 0)
    src.property("frameRate").setValue(24.0, 0)
    session.addNode(src)

    # 疤痕遮罩
    scar_mask = Node("RotoNode")
    scar_mask.label = "Scar_Mask"
    scar_mask.property("matte.mode").setValue("alpha", 0)
    scar_mask.property("alpha.blur").setValue(1.5, 0)
    session.addNode(scar_mask)

    # 跟踪节点
    track = Node("TrackerNode")
    track.label = "Scar_Track"
    track.property("trackType").setValue("planar", 0)
    track.property("accuracy").setValue("high", 0)
    session.addNode(track)

    # 第1层: 主修复（Clone）
    paint1 = Node("PaintNode")
    paint1.label = "Scar_Clone"
    paint1.property("brush.size").setValue(15.0, 0)
    paint1.property("brush.hardness").setValue(0.5, 0)
    paint1.property("brush.flow").setValue(0.8, 0)
    paint1.property("mode").setValue("clone", 0)
    paint1.property("propagation").setValue("tracked", 0)
    session.addNode(paint1)

    # 第2层: 边缘融合（Repair）
    paint2 = Node("PaintNode")
    paint2.label = "Scar_Blend"
    paint2.property("brush.size").setValue(8.0, 0)
    paint2.property("brush.hardness").setValue(0.6, 0)
    paint2.property("brush.flow").setValue(0.6, 0)
    paint2.property("mode").setValue("repair", 0)
    paint2.property("colorMatch").setValue(true, 0)
    session.addNode(paint2)

    # 第3层: 纹理重建
    paint3 = Node("PaintNode")
    paint3.label = "Scar_Texture"
    paint3.property("brush.size").setValue(3.0, 0)
    paint3.property("brush.hardness").setValue(0.8, 0)
    paint3.property("brush.flow").setValue(0.5, 0)
    paint3.property("mode").setValue("clone", 0)
    paint3.property("texturePreserve").setValue(true, 0)
    session.addNode(paint3)

    # 输出节点
    out_node = Node("OutputNode")
    out_node.property("path").setValue("D:/output/scar_fixed.####.exr", 0)
    out_node.property("format").setValue("exr", 0)
    session.addNode(out_node)

    # 连接节点
    src.outputs[0].connect(scar_mask.inputs[1])
    src.outputs[0].connect(track.inputs[0])
    src.outputs[0].connect(paint1.inputs[0])
    paint1.outputs[0].connect(paint2.inputs[0])
    paint2.outputs[0].connect(paint3.inputs[0])
    paint3.outputs[0].connect(out_node.inputs[0])
```

---

## 七、多帧化妆一致性

### 7.1 跟踪驱动传播

```python
# 启用跟踪驱动的自动传播
paint.property("propagation").setValue("tracked", 0)
paint.property("trackSource").setValue("Face_Track", 0)
paint.property("autoUpdate").setValue(true, 0)
```

### 7.2 关键帧策略

| 帧类型 | 间隔 | 操作 |
|--------|------|------|
| 主关键帧 | 每50帧 | 完整修复所有瑕疵 |
| 次关键帧 | 每10帧 | 检查并微调 |
| 检查帧 | 每帧 | 播放检查一致性 |

### 7.3 闪烁处理

```python
# 时间平滑，减少帧间闪烁
paint.property("temporalSmooth").setValue(true, 0)
paint.property("temporalRange").setValue(3, 0)  # 前后3帧平滑
```

---

## 八、质量评估与输出

### 8.1 评估标准

| 维度 | 标准 |
|------|------|
| 自然度 | 修复区域无明显痕迹 |
| 一致性 | 多帧播放无闪烁 |
| 纹理保留 | 保留自然皮肤纹理 |
| 色彩匹配 | 与周围肤色一致 |
| 光影保持 | 保持原始光影关系 |

### 8.2 输出配置

```python
out_node = Node("OutputNode")
out_node.property("path").setValue("D:/output/makeup.####.exr", 0)
out_node.property("format").setValue("exr", 0)
out_node.property("compression").setValue("zip", 0)
out_node.property("depth").setValue("16f", 0)  # 16位浮点，保留色彩精度
out_node.property("channels").setValue("rgba", 0)
```

### 8.3 与 AE 集成

```python
ae_config = {
    "version": "2.0",
    "source": "silhouette",
    "aeIntegration": {
        "compName": "Digital_Makeup",
        "importPath": "D:/output/",
        "applyAs": "replace_footage",
        "targetLayer": "selected",
    },
    "makeup": {
        "outputSequence": "makeup.####.exr",
        "frameRange": [0, 100],
        "resolution": [1920, 1080],
        "colorSpace": "ACES",
    },
}
```

---

## 总结

数字化妆是 Silhouette Paint 模块的高级应用，关键要点：

1. **区域划分**: 使用 RotoNode 精确划分面部区域
2. **跟踪驱动**: 利用面部特征点跟踪驱动修复
3. **分层处理**: 瑕疵修复、平滑、色彩校正分层进行
4. **保留纹理**: 避免过度平滑，保留自然皮肤纹理
5. **多帧一致**: 使用跟踪传播和时间平滑保证一致性

通过合理组合 Clone、Repair 模式，配合色彩调整参数，可以实现专业级的数字化妆效果。
