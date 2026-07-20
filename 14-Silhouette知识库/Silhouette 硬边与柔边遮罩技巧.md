# Silhouette 硬边与柔边遮罩技巧

> 分类: Roto抠像专题
> 更新日期: 2026-07-11
> 概述: 系统讲解硬边遮罩与柔边遮罩的参数配置、过渡技巧、混合策略及产品广告场景应用，提供生产级代码示例。

## 目录
1. [硬边与柔边总览](#一硬边与柔边总览)
2. [硬边参数配置](#二硬边参数配置)
3. [柔边过渡技巧](#三柔边过渡技巧)
4. [硬柔混合策略](#四硬柔混合策略)
5. [产品广告场景应用](#五产品广告场景应用)
6. [代码示例](#六代码示例)
7. [常见问题与最佳实践](#七常见问题与最佳实践)

---

## 一、硬边与柔边总览

### 1.1 硬边 vs 柔边

```
硬边 (Hard Edge):           柔边 (Soft Edge):
┌────────────┐              ╭────────────╮
│            │              │            │
│   100%     │              │  100%→80%  │
│            │              │   ↓70%↓    │
│            │              │   40%↓     │
└────────────┘              ╰────────────╯
   |                        |← feather →|
   0px 过渡                  5-15px 渐变
```

### 1.2 适用场景对比

| 类型 | 适用物体 | 典型场景 | 关键参数 |
|------|---------|---------|---------|
| **硬边** | 产品、建筑、机械、UI | 广告、特效合成 | feather=0, blur=0 |
| **柔边** | 人物、动物、自然物 | 影视角色、生物 | feather=2-8, blur=0.3-1 |
| **混合** | 复合物体（人+产品） | 带道具的人物镜头 | 分形状不同设置 |

### 1.3 决策流程

```
物体类型?
├─ 人造硬物（金属/塑料/玻璃边） → 硬边
├─ 自然有机物（皮肤/衣物/毛发） → 柔边
├─ 半透明物（玻璃/烟雾/纱）    → 大柔边
└─ 混合物体                    → 分形状混合
```

---

## 二、硬边参数配置

### 2.1 硬边核心参数

```python
from fx import *

def create_hard_edge_shape(roto_node):
    """创建硬边形状"""
    shape = roto_node.createObject("Bezier")  # 硬边优先用 Bézier
    shape.name = "HardEdge_Product"

    # === 形状级硬边参数 ===
    shape.property("feather").setValue(0.0, 0)       # 完全无羽化
    shape.property("blur").setValue(0.0, 0)          # 完全无模糊
    shape.property("perPointFeather").setValue(false, 0)

    # === 控制点为角点 ===
    corners = [(400, 300), (800, 300), (800, 600), (400, 600)]
    for c in corners:
        shape.addPoint(c, inTangent=(0, 0), outTangent=(0, 0))  # 角点

    return shape

def configure_hard_edge_node(roto_node):
    """配置硬边节点参数"""
    # === 节点级硬边参数 ===
    roto_node.property("alpha.blur").setValue(0.0, 0)    # Alpha 无模糊
    roto_node.property("alpha.shrink").setValue(0.0, 0)  # 不收缩
    roto_node.property("antialias").setValue(1.0, 0)     # 抗锯齿保留
    roto_node.property("matte.mode").setValue("alpha", 0)

    # 关闭运动模糊（硬边通常不需要）
    roto_node.property("motionBlur").setValue(false, 0)
```

### 2.2 硬边参数对照表

| 参数 | 硬边值 | 说明 |
|------|--------|------|
| feather | 0.0 | 完全无羽化 |
| blur | 0.0 | 完全无模糊 |
| alpha.blur | 0.0 | Alpha 通道无模糊 |
| alpha.shrink | 0.0 | 不收缩 |
| antialias | 1.0 | 抗锯齿（保留） |
| motionBlur | false | 关闭运动模糊 |
| perPointFeather | false | 不需要逐点羽化 |

### 2.3 硬边精度控制

```python
def precision_hard_edge(shape):
    """像素级硬边精度控制"""
    # 1. 使用 Bézier 角点
    for point in shape.points:
        point.inTangent = (0, 0)
        point.outTangent = (0, 0)

    # 2. 启用像素对齐
    shape.property("pixelAlign").setValue(true, 0)

    # 3. 启用子像素精度
    shape.property("subpixel").setValue(true, 0)

    # 4. 关闭任何柔化
    shape.property("feather").setValue(0.0, 0)
    shape.property("blur").setValue(0.0, 0)

    # 5. Alpha 收紧（消除亚像素杂色）
    # 在节点级设置
```

### 2.4 不同硬边物体配置

| 物体 | feather | alpha.blur | 备注 |
|------|---------|-----------|------|
| 手机屏幕 | 0.0 | 0.0 | 绝对硬边 |
| 金属边框 | 0.0 | 0.1 | 微抗锯齿 |
| 玻璃边缘 | 0.5 | 0.2 | 极轻微羽化 |
| 塑料产品 | 0.0 | 0.0 | 硬边 |
| 建筑 | 0.0 | 0.0 | 硬边 |
| UI 元素 | 0.0 | 0.0 | 像素精确 |

---

## 三、柔边过渡技巧

### 3.1 柔边核心参数

```python
def create_soft_edge_shape(roto_node):
    """创建柔边形状"""
    shape = roto_node.createObject("X-Spline")  # 柔边优先用 X-Spline
    shape.name = "SoftEdge_Character"

    # === 形状级柔边参数 ===
    shape.property("feather").setValue(3.0, 0)        # 中等羽化
    shape.property("featherFalloff").setValue(0.5, 0)  # S 曲线
    shape.property("blur").setValue(0.3, 0)            # 轻微模糊

    return shape

def configure_soft_edge_node(roto_node):
    """配置柔边节点参数"""
    roto_node.property("alpha.blur").setValue(0.4, 0)    # 轻微 Alpha 模糊
    roto_node.property("antialias").setValue(1.0, 0)
    roto_node.property("matte.mode").setValue("alpha", 0)
```

### 3.2 柔边等级

| 等级 | feather | blur | alpha.blur | 适用 |
|------|---------|------|-----------|------|
| 微柔 | 0.5-1.0 | 0.1 | 0.1 | 锐利边缘物体 |
| 轻柔 | 1.0-3.0 | 0.3 | 0.3 | 人物皮肤、衣物 |
| 中柔 | 3.0-8.0 | 0.5-1.0 | 0.5 | 毛发、半透明 |
| 大柔 | 8.0-15.0 | 1.0-2.0 | 0.8-1.0 | 烟雾、光晕 |
| 极柔 | 15.0+ | 2.0+ | 1.5+ | 大气效果、景深 |

### 3.3 渐变柔边（Bézier 逐点）

```python
def create_gradient_soft_edge(roto_node):
    """创建渐变柔边（不同部位不同羽化）"""
    shape = roto_node.createObject("Bezier")
    shape.name = "Gradient_Soft"
    shape.property("perPointFeather").setValue(true, 0)

    # 头部轮廓（顶部硬，底部柔）
    points_config = [
        # (position, feather, angle)
        ((500, 200), 0.5, 0),     # 头顶 - 紧贴头皮
        ((700, 250), 2.0, 90),    # 右额
        ((750, 400), 4.0, 90),    # 右脸
        ((700, 550), 6.0, 180),   # 右下颌
        ((500, 600), 8.0, 180),   # 下巴 - 颈部过渡
        ((300, 550), 6.0, 180),   # 左下颌
        ((250, 400), 4.0, 270),   # 左脸
        ((300, 250), 2.0, 270),   # 左额
    ]

    for pos, _, _ in points_config:
        shape.addPoint(pos, inTangent=(0, 0), outTangent=(0, 0))

    for i, (_, feather, angle) in enumerate(points_config):
        shape.points[i].feather = feather
        shape.points[i].featherAngle = angle

    return shape
```

### 3.4 featherFalloff 曲线选择

```
线性 (0.0):    平滑 (0.5):     锐利 (1.0):
1.0 ─╲         1.0 ──╲          1.0 ─┐
     ╲              ╲                │
      ╲               ╲              │
       ╲               ╲             │
0.0    ╲        0.0    ╲      0.0   ╲
   ←f→              ←f→          ←f→
```

```python
# 不同物体的 falloff 选择
falloff_presets = {
    "skin": 0.5,        # 平滑 - 皮肤
    "hair": 0.7,        # 偏锐 - 毛发末梢
    "glass": 0.3,       # 偏线性 - 玻璃
    "smoke": 0.8,       # 锐利 - 烟雾核心
    "product": 0.0,     # 线性 - 产品
}
```

---

## 四、硬柔混合策略

### 4.1 同物体混合（人物 + 道具）

```python
def create_mixed_edge_character(roto_node):
    """创建混合边缘角色：身体柔边 + 手表硬边"""
    # === 身体（柔边）===
    body = roto_node.createObject("X-Spline")
    body.name = "Body_Soft"
    body.property("feather").setValue(2.0, 0)
    body.property("featherFalloff").setValue(0.5, 0)
    body.property("blur").setValue(0.3, 0)

    # === 手表（硬边）===
    watch = roto_node.createObject("Bezier")
    watch.name = "Watch_Hard"
    watch.property("feather").setValue(0.0, 0)
    watch.property("blur").setValue(0.0, 0)
    # 手表形状优先级高于身体（渲染在上层）
    watch.property("inverted").setValue(false, 0)

    return body, watch
```

### 4.2 边缘渐变过渡

```python
def create_edge_transition(roto_node):
    """创建边缘渐变过渡（如衣物到皮肤）"""
    # 皮肤区（轻柔）
    skin = roto_node.createObject("X-Spline")
    skin.name = "Skin"
    skin.property("feather").setValue(1.0, 0)

    # 衣物区（中柔）
    cloth = roto_node.createObject("X-Spline")
    cloth.name = "Cloth"
    cloth.property("feather").setValue(3.0, 0)

    # 过渡区（重叠 + 中等羽化）
    transition = roto_node.createObject("X-Spline")
    transition.name = "Transition"
    transition.property("feather").setValue(2.0, 0)
    transition.property("opacity").setValue(0.5, 0)

    return skin, cloth, transition
```

### 4.3 多形状混合优先级

```
渲染顺序（从下到上）:
┌─────────────────────┐
│ 形状 4: 眼睛（硬边） │  最高优先级
├─────────────────────┤
│ 形状 3: 嘴唇（柔边） │
├─────────────────────┤
│ 形状 2: 头发（大柔） │
├─────────────────────┤
│ 形状 1: 身体（中柔） │  最低优先级
└─────────────────────┘
```

```python
def set_shape_priority(roto_node):
    """设置形状渲染优先级"""
    shapes = roto_node.objects
    # 优先级从低到高
    priority_order = ["Body", "Hair", "Cloth", "Face", "Eyes", "Glasses"]

    for i, shape_name in enumerate(priority_order):
        for shape in shapes:
            if shape.name == shape_name:
                shape.property("priority").setValue(i, 0)
                break
```

---

## 五、产品广告场景应用

### 5.1 产品广告抠像要求

| 要求 | 描述 | 参数 |
|------|------|------|
| 绝对硬边 | 像素级精确 | feather=0, blur=0 |
| 无运动模糊 | 产品清晰 | motionBlur=false |
| 无颜色溢出 | 边缘纯净 | despill=true |
| 抗锯齿完美 | 边缘平滑 | antialias=1.0 |
| 多角度一致 | 旋转时稳定 | 关键帧密 |

### 5.2 产品广告标准配置

```python
def create_product_ad_keying(source_path, output_path, frame_rate=30.0):
    """创建产品广告级抠像管线"""
    proj = activeProject() or Project()
    activate(proj)
    session = activeSession() or Session()
    session.label = "Product_Ad_Keying"
    activate(session)
    proj.addItem(session)

    src = Node("SourceNode")
    src.property("mediaPath").setValue(source_path.replace("\\", "/"), 0)
    src.property("frameRate").setValue(frame_rate, 0)
    session.addNode(src)

    roto = Node("RotoNode")
    roto.label = "Product_Roto"
    session.addNode(roto)

    # === 节点级硬边配置 ===
    roto.property("alpha.blur").setValue(0.0, 0)    # 绝对无模糊
    roto.property("alpha.shrink").setValue(0.3, 0)  # 微收紧，消除杂色
    roto.property("antialias").setValue(1.0, 0)
    roto.property("motionBlur").setValue(false, 0)  # 关闭运动模糊
    roto.property("matte.mode").setValue("alpha", 0)

    # === 创建产品形状 ===
    product = roto.createObject("Bezier")
    product.name = "Product_Body"
    product.property("feather").setValue(0.0, 0)
    product.property("blur").setValue(0.0, 0)
    product.property("perPointFeather").setValue(false, 0)

    # === 反光高光（如有）===
    highlight = roto.createObject("Bezier")
    highlight.name = "Product_Highlight"
    highlight.property("feather").setValue(0.3, 0)  # 极轻羽化
    highlight.property("opacity").setValue(0.9, 0)

    # === 阴影区 ===
    shadow = roto.createObject("Bezier")
    shadow.name = "Product_Shadow"
    shadow.property("feather").setValue(1.5, 0)
    shadow.property("opacity").setValue(0.7, 0)

    # === 输出 ===
    out_node = Node("OutputNode")
    out_node.property("path").setValue(output_path.replace("\\", "/"), 0)
    out_node.property("format").setValue("exr", 0)
    out_node.property("compression").setValue("none", 0)
    session.addNode(out_node)

    src.outputs[0].connect(roto.inputs[1])
    roto.outputs[0].connect(out_node.inputs[0])

    print("[SILHOUETTE] 产品广告级抠像管线已创建")
    return roto, product, highlight, shadow
```

### 5.3 旋转产品抠像

```python
def create_rotating_product_roto(roto_node, num_keyframes=24):
    """为旋转产品创建关键帧（每 15° 一帧）"""
    product = roto_node.createObject("Bezier")
    product.name = "Rotating_Product"
    product.property("feather").setValue(0.0, 0)

    # 假设产品旋转一周 24 帧（15°/帧）
    # 实际形状需根据视频内容手工绘制
    for frame in range(num_keyframes):
        # 此处简化，实际需根据产品轮廓手工调整
        angle = (frame / num_keyframes) * 360

        # 示例：矩形旋转
        cx, cy = 960, 540
        w, h = 200, 400
        import math
        rad = math.radians(angle)

        corners = []
        for dx, dy in [(-w/2, -h/2), (w/2, -h/2), (w/2, h/2), (-w/2, h/2)]:
            x = cx + dx * math.cos(rad) - dy * math.sin(rad)
            y = cy + dx * math.sin(rad) + dy * math.cos(rad)
            corners.append((x, y))

        # 在每帧设置形状
        if frame == 0:
            for c in corners:
                product.addPoint(c, inTangent=(0, 0), outTangent=(0, 0))
        else:
            for i, c in enumerate(corners):
                product.points[i].setValue(c, frame)

    return product
```

### 5.4 多产品组合

```python
def create_multi_product_keying(roto_node):
    """多产品组合抠像（如广告中的多个商品）"""
    products = []

    # 产品 1（左）
    p1 = roto_node.createObject("Bezier")
    p1.name = "Product_Left"
    p1.property("feather").setValue(0.0, 0)
    products.append(p1)

    # 产品 2（中）
    p2 = roto_node.createObject("Bezier")
    p2.name = "Product_Center"
    p2.property("feather").setValue(0.0, 0)
    products.append(p2)

    # 产品 3（右）
    p3 = roto_node.createObject("Bezier")
    p3.name = "Product_Right"
    p3.property("feather").setValue(0.0, 0)
    products.append(p3)

    return products
```

---

## 六、代码示例

### 6.1 硬边模板

```python
from fx import *

def create_hard_edge_pipeline(source_path, output_path, frame_rate=30.0):
    """硬边抠像完整管线"""
    proj = activeProject() or Project()
    activate(proj)
    session = activeSession() or Session()
    session.label = "Hard_Edge"
    activate(session)
    proj.addItem(session)

    src = Node("SourceNode")
    src.property("mediaPath").setValue(source_path.replace("\\", "/"), 0)
    src.property("frameRate").setValue(frame_rate, 0)
    session.addNode(src)

    roto = Node("RotoNode")
    roto.label = "Hard_Roto"
    # 硬边节点配置
    roto.property("alpha.blur").setValue(0.0, 0)
    roto.property("alpha.shrink").setValue(0.3, 0)
    roto.property("antialias").setValue(1.0, 0)
    roto.property("motionBlur").setValue(false, 0)
    session.addNode(roto)

    # 硬边形状
    shape = roto.createObject("Bezier")
    shape.name = "Hard_Shape"
    shape.property("feather").setValue(0.0, 0)
    shape.property("blur").setValue(0.0, 0)

    out_node = Node("OutputNode")
    out_node.property("path").setValue(output_path.replace("\\", "/"), 0)
    out_node.property("format").setValue("exr", 0)
    session.addNode(out_node)

    src.outputs[0].connect(roto.inputs[1])
    roto.outputs[0].connect(out_node.inputs[0])

    print("[SILHOUETTE] 硬边抠像管线已创建")
    return roto
```

### 6.2 柔边模板

```python
def create_soft_edge_pipeline(source_path, output_path, frame_rate=24.0):
    """柔边抠像完整管线"""
    proj = activeProject() or Project()
    activate(proj)
    session = activeSession() or Session()
    session.label = "Soft_Edge"
    activate(session)
    proj.addItem(session)

    src = Node("SourceNode")
    src.property("mediaPath").setValue(source_path.replace("\\", "/"), 0)
    src.property("frameRate").setValue(frame_rate, 0)
    session.addNode(src)

    roto = Node("RotoNode")
    roto.label = "Soft_Roto"
    # 柔边节点配置
    roto.property("alpha.blur").setValue(0.4, 0)
    roto.property("antialias").setValue(1.0, 0)
    roto.property("motionBlur").setValue(true, 0)
    roto.property("motionBlur.shutter").setValue(0.5, 0)
    session.addNode(roto)

    # 柔边形状
    shape = roto.createObject("X-Spline")
    shape.name = "Soft_Shape"
    shape.property("feather").setValue(3.0, 0)
    shape.property("featherFalloff").setValue(0.5, 0)
    shape.property("blur").setValue(0.3, 0)

    out_node = Node("OutputNode")
    out_node.property("path").setValue(output_path.replace("\\", "/"), 0)
    out_node.property("format").setValue("exr", 0)
    session.addNode(out_node)

    src.outputs[0].connect(roto.inputs[1])
    roto.outputs[0].connect(out_node.inputs[0])

    print("[SILHOUETTE] 柔边抠像管线已创建")
    return roto
```

### 6.3 混合边缘模板

```python
def create_mixed_edge_pipeline(source_path, output_path, frame_rate=24.0):
    """混合边缘抠像管线（人物 + 道具）"""
    proj = activeProject() or Project()
    activate(proj)
    session = activeSession() or Session()
    session.label = "Mixed_Edge"
    activate(session)
    proj.addItem(session)

    src = Node("SourceNode")
    src.property("mediaPath").setValue(source_path.replace("\\", "/"), 0)
    src.property("frameRate").setValue(frame_rate, 0)
    session.addNode(src)

    roto = Node("RotoNode")
    roto.label = "Mixed_Roto"
    roto.property("alpha.blur").setValue(0.3, 0)
    roto.property("antialias").setValue(1.0, 0)
    session.addNode(roto)

    # 柔边：人物身体
    body = roto.createObject("X-Spline")
    body.name = "Body_Soft"
    body.property("feather").setValue(2.0, 0)
    body.property("blur").setValue(0.3, 0)

    # 硬边：眼镜
    glasses = roto.createObject("Bezier")
    glasses.name = "Glasses_Hard"
    glasses.property("feather").setValue(0.0, 0)
    glasses.property("blur").setValue(0.0, 0)

    # 硬边：手表
    watch = roto.createObject("Bezier")
    watch.name = "Watch_Hard"
    watch.property("feather").setValue(0.0, 0)

    out_node = Node("OutputNode")
    out_node.property("path").setValue(output_path.replace("\\", "/"), 0)
    out_node.property("format").setValue("exr", 0)
    session.addNode(out_node)

    src.outputs[0].connect(roto.inputs[1])
    roto.outputs[0].connect(out_node.inputs[0])

    print("[SILHOUETTE] 混合边缘抠像管线已创建")
    print("  身体: 柔边 (feather=2.0)")
    print("  眼镜: 硬边 (feather=0.0)")
    print("  手表: 硬边 (feather=0.0)")
    return roto
```

---

## 七、常见问题与最佳实践

### 7.1 问题诊断

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 硬边有锯齿 | antialias 关闭 | 设为 1.0 |
| 硬边有杂色 | alpha 未收紧 | alpha.shrink=0.3-0.5 |
| 硬边"沸腾" | 关键帧不够 | 增加关键帧密度 |
| 柔边"溢色" | feather 过大 | 减小 feather 或 alpha.shrink |
| 柔边"太虚" | feather + blur 叠加 | 二选一，不要同时大 |
| 混合边缘"穿帮" | 优先级错误 | 调整形状 priority |
| 旋转产品"抖动" | 关键帧太少 | 每 5-10° 一帧 |

### 7.2 最佳实践

1. **硬边用 Bézier**：角点控制精确，无手柄干扰。
2. **柔边用 X-Spline**：少点位，自然曲线。
3. **混合分层**：硬边物体优先级高于柔边身体。
4. **产品广告关 motionBlur**：保证产品清晰度。
5. **抗锯齿必开**：antialias=1.0 是底线。
6. **alpha.shrink 微调**：硬边物体 0.3-0.5px 收紧，消除亚像素杂色。
7. **逐点羽化**：渐变边缘用 Bézier 的 perPointFeather。

### 7.3 性能建议

- 硬边形状点数 ≤ 20，避免过密。
- 柔边形状点数 ≤ 30。
- 混合场景形状总数 ≤ 15/Node。
- 关闭不必要的 motionBlur。
- 预览用 proxy 模式。

### 7.4 质量检查清单

- [ ] 硬边绝对锐利（无锯齿、无杂色）
- [ ] 柔边过渡自然（无阶梯）
- [ ] 混合边缘优先级正确
- [ ] 产品广告无运动模糊
- [ ] 抗锯齿启用
- [ ] alpha.shrink 适度
- [ ] 关键帧密度匹配运动速度
- [ ] 多角度一致性验证

---

## 相关文档

- [Silhouette X-Spline与Bézier曲线详解](Silhouette%20X-Spline与Bézier曲线详解.md)
- [Silhouette 边缘优化与运动模糊](Silhouette%20边缘优化与运动模糊.md)
- [Silhouette 毛发与半透明物体抠像](Silhouette%20毛发与半透明物体抠像.md)
- [Silhouette 多形状管理与层级控制](Silhouette%20多形状管理与层级控制.md)
