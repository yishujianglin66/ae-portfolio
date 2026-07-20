# Silhouette 毛发与半透明物体抠像

> 分类: Roto抠像专题
> 更新日期: 2026-07-11
> 概述: 深入讲解毛发抠像专用技巧、半透明物体处理方法、多通道遮罩策略与细节保留技术，提供生产级代码示例。

## 目录
1. [毛发抠像挑战与策略](#一毛发抠像挑战与策略)
2. [毛发专用技巧](#二毛发专用技巧)
3. [半透明物体处理](#三半透明物体处理)
4. [多通道遮罩策略](#四多通道遮罩策略)
5. [细节保留策略](#五细节保留策略)
6. [代码示例](#六代码示例)
7. [常见问题与最佳实践](#七常见问题与最佳实践)

---

## 一、毛发抠像挑战与策略

### 1.1 毛发抠像的难点

```
硬边物体:    毛发:
┌──────┐    ╱╲ ╱╲ ╱╲ ╱╲
│      │   ╱  V  V  V  ╲
│  ■   │  │ 细碎、半透明、
│      │  │ 飘动、模糊
└──────┘   ╲ ╱╲ ╱╲ ╱╲ ╱
 简单          极复杂
```

| 难点 | 描述 | 影响 |
|------|------|------|
| **细碎边缘** | 单根毛发宽度 < 1px | 形状难以描绘 |
| **半透明** | 毛发透出背景色 | Alpha 不是 0/1 二值 |
| **运动模糊** | 飘动时产生方向性模糊 | 边缘不稳定 |
| **景深虚化** | 部分毛发在焦外 | 边缘更模糊 |
| **色彩溢出** | 背景色反射到毛发 | 颜色不纯 |
| **数量巨大** | 数千根毛发 | 无法逐根描绘 |

### 1.2 三大策略

#### 策略 1：分层抠像（推荐）

```
身体层（硬边） + 毛发内层（中羽化） + 毛发外层（大羽化） + 飘散层（最大羽化）
```

#### 策略 2：通道混合

```
Roto 遮罩（轮廓） + 颜色键（毛发色） + 亮度键（高光） = 最终 Alpha
```

#### 策略 3：AI 辅助 + 手工

```
HairNet 起稿 → 手工精修关键帧 → 智能跟踪传播 → 局部手工修正
```

---

## 二、毛发专用技巧

### 2.1 分层结构

```python
from fx import *

def create_hair_layered_roto(session, src_node):
    """创建分层毛发抠像"""
    roto = Node("RotoNode")
    roto.label = "Hair_Layered"
    session.addNode(roto)

    # === Layer 1: 身体（硬边）===
    body = roto.createObject("X-Spline")
    body.name = "Body"
    body.property("feather").setValue(0.5, 0)
    body.property("blur").setValue(0.2, 0)
    body.property("inverted").setValue(false, 0)

    # === Layer 2: 毛发内层（中羽化）===
    hair_inner = roto.createObject("X-Spline")
    hair_inner.name = "Hair_Inner"
    hair_inner.property("feather").setValue(3.0, 0)
    hair_inner.property("featherFalloff").setValue(0.6, 0)
    hair_inner.property("blur").setValue(0.5, 0)

    # === Layer 3: 毛发外层（大羽化）===
    hair_outer = roto.createObject("X-Spline")
    hair_outer.name = "Hair_Outer"
    hair_outer.property("feather").setValue(8.0, 0)
    hair_outer.property("featherFalloff").setValue(0.7, 0)
    hair_outer.property("blur").setValue(1.0, 0)
    hair_outer.property("opacity").setValue(0.7, 0)  # 降不透明度

    # === Layer 4: 飘散层（最大羽化 + 运动模糊）===
    hair_flyaway = roto.createObject("X-Spline")
    hair_flyaway.name = "Hair_Flyaway"
    hair_flyaway.property("feather").setValue(15.0, 0)
    hair_flyaway.property("featherFalloff").setValue(0.8, 0)
    hair_flyaway.property("blur").setValue(2.0, 0)
    hair_flyaway.property("opacity").setValue(0.5, 0)
    hair_flyaway.property("motionBlur").setValue(true, 0)
    hair_flyaway.property("motionBlur.shutter").setValue(0.7, 0)

    src_node.outputs[0].connect(roto.inputs[1])
    return roto, body, hair_inner, hair_outer, hair_flyaway
```

### 2.2 关键参数配置

| 层 | feather | blur | opacity | motionBlur | 用途 |
|----|---------|------|---------|-----------|------|
| 身体 | 0.5 | 0.2 | 1.0 | false | 主体硬边 |
| 毛发内层 | 3.0 | 0.5 | 1.0 | false | 毛发主体 |
| 毛发外层 | 8.0 | 1.0 | 0.7 | true | 毛发末梢 |
| 飘散层 | 15.0 | 2.0 | 0.5 | true | 飘散碎发 |

### 2.3 逐点羽化（Bézier 毛发）

```python
def create_hair_with_per_point_feather(roto_node):
    """使用 Bézier 逐点羽化模拟毛发边缘"""
    hair = roto_node.createObject("Bezier")
    hair.name = "Hair_PerPoint"
    hair.property("perPointFeather").setValue(true, 0)

    # 毛发轮廓点 - 不同区域不同羽化
    hair_points = [
        # (position, feather, angle)
        ((100, 200), 0.5, 0),     # 头皮紧贴处 - 硬
        ((300, 180), 2.0, 90),    # 头顶 - 中等
        ((500, 220), 5.0, 90),    # 侧边 - 较大
        ((550, 400), 8.0, 90),    # 末梢 - 大羽化
        ((500, 500), 12.0, 180),  # 飘散 - 最大
        ((300, 480), 8.0, 180),   # 末梢
        ((100, 450), 3.0, 270),   # 颈部 - 中等
    ]

    for pt, feather, angle in hair_points:
        hair.addPoint(pt, inTangent=(0, 0), outTangent=(0, 0))

    for i, (_, feather, angle) in enumerate(hair_points):
        hair.points[i].feather = feather
        hair.points[i].featherAngle = angle

    return hair
```

### 2.4 毛发方向性羽化

```python
def create_directional_hair_feather(shape, direction="right"):
    """根据毛发流向设置方向性羽化"""
    direction_map = {
        "right": 0,
        "down": 90,
        "left": 180,
        "up": 270
    }
    base_angle = direction_map.get(direction, 0)

    for i, point in enumerate(shape.points):
        # 沿毛发方向的点羽化更大
        progress = i / len(shape.points)
        feather = 2.0 + progress * 10.0  # 从 2px 增长到 12px

        point.feather = feather
        point.featherAngle = base_angle
```

---

## 三、半透明物体处理

### 3.1 半透明物体类型

| 类型 | Alpha 特征 | 难度 |
|------|-----------|------|
| 玻璃 | 10-40% 透射 | 高 |
| 烟雾 | 0-80% 渐变 | 中 |
| 纱裙 | 30-70% 网格 | 极高 |
| 火焰 | 50-100% 发光 | 中 |
| 水流 | 20-90% 折射 | 高 |
| 半透明塑料 | 40-80% | 中 |

### 3.2 透明度遮罩

```python
def create_transparent_object_roto(session, src_node):
    """创建半透明物体遮罩"""
    roto = Node("RotoNode")
    roto.label = "Transparent_Object"
    session.addNode(roto)

    # === 主体形状（80% 不透明度）===
    main = roto.createObject("X-Spline")
    main.name = "Glass_Body"
    main.property("feather").setValue(2.0, 0)
    main.property("opacity").setValue(0.8, 0)  # 80% 透明度
    main.property("blur").setValue(0.5, 0)

    # === 反光区（50% 不透明度）===
    reflection = roto.createObject("X-Spline")
    reflection.name = "Glass_Reflection"
    reflection.property("feather").setValue(3.0, 0)
    reflection.property("opacity").setValue(0.5, 0)

    # === 折射区（30% 不透明度）===
    refraction = roto.createObject("X-Spline")
    refraction.name = "Glass_Refraction"
    refraction.property("feather").setValue(5.0, 0)
    refraction.property("opacity").setValue(0.3, 0)

    src_node.outputs[0].connect(roto.inputs[1])
    return roto
```

### 3.3 透明度动画

```python
def animate_transparency(shape, frame_range, min_opacity=0.3, max_opacity=0.9):
    """透明度随时间变化（如烟雾扩散）"""
    import math

    for frame in frame_range:
        # 使用正弦波模拟透明度变化
        t = (frame - frame_range[0]) / (frame_range[-1] - frame_range[0])
        opacity = min_opacity + (max_opacity - min_opacity) * (
            0.5 + 0.5 * math.sin(t * 2 * math.pi)
        )
        shape.property("opacity").setValue(opacity, frame)
```

### 3.4 颜色溢出处理

```python
def handle_color_spill(roto_node, spill_color="green"):
    """处理半透明物体边缘的颜色溢出"""
    # 启用 Despill 节点（如果可用）
    despill = Node("DespillNode")
    despill.property("spillColor").setValue(spill_color, 0)
    despill.property("amount").setValue(0.5, 0)
    despill.property("method").setValue("light", 0)  # light/dark/average

    # 在 RotoNode 后插入 Despill
    session.addNode(despill)
    roto_node.outputs[0].connect(despill.inputs[0])

    return despill
```

---

## 四、多通道遮罩策略

### 4.1 多通道合成原理

```
最终 Alpha = Roto_Alpha × Color_Key × Luma_Key × Edge_Enhance
```

每个通道贡献不同的遮罩信息，相乘得到最终结果。

### 4.2 实现多通道遮罩

```python
def create_multi_channel_matte(session, src_node):
    """创建多通道遮罩管线"""
    # === 通道 1: Roto 形状遮罩 ===
    roto = Node("RotoNode")
    roto.label = "Channel_Roto"
    roto.property("alpha.blur").setValue(0.5, 0)
    session.addNode(roto)

    shape = roto.createObject("X-Spline")
    shape.name = "Main_Shape"
    shape.property("feather").setValue(2.0, 0)

    # === 通道 2: 颜色键 ===
    color_key = Node("KeyerNode")  # 假设有颜色键节点
    color_key.label = "Channel_ColorKey"
    color_key.property("keyColor").setValue((0.2, 0.8, 0.3), 0)
    color_key.property("tolerance").setValue(0.3, 0)
    session.addNode(color_key)

    # === 通道 3: 亮度键 ===
    luma_key = Node("LumaKeyerNode")
    luma_key.label = "Channel_LumaKey"
    luma_key.property("minLuma").setValue(0.3, 0)
    luma_key.property("maxLuma").setValue(1.0, 0)
    session.addNode(luma_key)

    # === 合成节点（Multiply 混合）===
    merge = Node("MergeNode")
    merge.label = "Channel_Merge"
    merge.property("operation").setValue("multiply", 0)
    session.addNode(merge)

    # === 连接 ===
    src_node.outputs[0].connect(roto.inputs[1])
    src_node.outputs[0].connect(color_key.inputs[0])
    src_node.outputs[0].connect(luma_key.inputs[0])

    roto.outputs[0].connect(merge.inputs[0])
    color_key.outputs[0].connect(merge.inputs[1])
    luma_key.outputs[0].connect(merge.inputs[2])

    return roto, color_key, luma_key, merge
```

### 4.3 通道优先级

```
高优先级（精度高）  →  Roto 形状（轮廓）
中优先级（颜色准）  →  颜色键（毛发色）
低优先级（细节多）  →  亮度键（高光、反光）
```

### 4.4 通道独立调节

```python
def adjust_channel_balance(roto_node, color_key_node, luma_key_node,
                            roto_weight=0.6, color_weight=0.3, luma_weight=0.1):
    """调节各通道权重"""
    # Roto 通道
    roto_node.property("alpha.gain").setValue(roto_weight, 0)

    # 颜色键通道
    color_key_node.property("alphaGain").setValue(color_weight, 0)

    # 亮度键通道
    luma_key_node.property("alphaGain").setValue(luma_weight, 0)

    print(f"[CHANNEL] Roto={roto_weight}, Color={color_weight}, Luma={luma_weight}")
```

---

## 五、细节保留策略

### 5.1 细节保留原则

```
原则 1: 不要"过度抠干净" - 保留 5-10% 边缘细节比 100% 干净更真实
原则 2: 分层保留 - 主轮廓 + 细节层 + 飘散层
原则 3: 动态调整 - 运动时羽化大，静止时羽化小
原则 4: 颜色优先 - 与其追求 Alpha 完美，不如修正颜色溢出
```

### 5.2 边缘细节增强

```python
def enhance_edge_details(roto_node):
    """增强边缘细节"""
    # 1. 收紧核心 Alpha
    roto_node.property("alpha.shrink").setValue(0.5, 0)

    # 2. 增加边缘检测
    roto_node.property("edgeEnhance").setValue(true, 0)
    roto_node.property("edgeEnhance.amount").setValue(0.3, 0)
    roto_node.property("edgeEnhance.radius").setValue(2.0, 0)

    # 3. 保留高频细节
    roto_node.property("detailPreserve").setValue(true, 0)
    roto_node.property("detailPreserve.threshold").setValue(0.2, 0)
```

### 5.3 毛发细节分层

```python
def create_hair_detail_layers(roto_node):
    """创建毛发细节分层"""
    layers = []

    # === 主毛发层 ===
    main_hair = roto_node.createObject("X-Spline")
    main_hair.name = "Hair_Main"
    main_hair.property("feather").setValue(4.0, 0)
    main_hair.property("opacity").setValue(1.0, 0)
    layers.append(main_hair)

    # === 细发丝层 1 ===
    strand_1 = roto_node.createObject("X-Spline")
    strand_1.name = "Hair_Strand_1"
    strand_1.property("feather").setValue(1.5, 0)
    strand_1.property("opacity").setValue(0.8, 0)
    layers.append(strand_1)

    # === 细发丝层 2 ===
    strand_2 = roto_node.createObject("X-Spline")
    strand_2.name = "Hair_Strand_2"
    strand_2.property("feather").setValue(1.0, 0)
    strand_2.property("opacity").setValue(0.6, 0)
    layers.append(strand_2)

    # === 高光层 ===
    highlight = roto_node.createObject("X-Spline")
    highlight.name = "Hair_Highlight"
    highlight.property("feather").setValue(0.5, 0)
    highlight.property("opacity").setValue(0.4, 0)
    layers.append(highlight)

    return layers
```

### 5.4 动态羽化调节

```python
def dynamic_feather_adjustment(shape, motion_data):
    """根据运动数据动态调整羽化"""
    for frame, motion_speed in motion_data.items():
        # 运动越快，羽化越大（模拟运动模糊）
        if motion_speed < 5:      # 静止
            feather = 2.0
        elif motion_speed < 20:   # 缓慢
            feather = 4.0
        elif motion_speed < 50:   # 正常
            feather = 8.0
        else:                     # 快速
            feather = 15.0

        shape.property("feather").setValue(feather, frame)
```

---

## 六、代码示例

### 6.1 完整毛发抠像管线

```python
from fx import *

def create_hair_keying_pipeline(source_path, output_path, frame_rate=24.0):
    """创建完整毛发抠像管线"""
    proj = activeProject() or Project()
    activate(proj)
    session = activeSession() or Session()
    session.label = "Hair_Keying_Full"
    activate(session)
    proj.addItem(session)

    src = Node("SourceNode")
    src.property("mediaPath").setValue(source_path.replace("\\", "/"), 0)
    src.property("frameRate").setValue(frame_rate, 0)
    session.addNode(src)

    # === 主 RotoNode（身体 + 毛发分层）===
    roto = Node("RotoNode")
    roto.label = "Hair_Roto"
    roto.property("alpha.blur").setValue(0.5, 0)
    roto.property("antialias").setValue(1.0, 0)
    roto.property("motionBlur").setValue(true, 0)
    roto.property("motionBlur.shutter").setValue(0.5, 0)
    session.addNode(roto)

    # 创建分层形状
    create_hair_layered_roto(session, src)

    # === 输出 ===
    out_node = Node("OutputNode")
    out_node.property("path").setValue(output_path.replace("\\", "/"), 0)
    out_node.property("format").setValue("exr", 0)
    out_node.property("compression").setValue("none", 0)
    session.addNode(out_node)

    src.outputs[0].connect(roto.inputs[1])
    roto.outputs[0].connect(out_node.inputs[0])

    print("[SILHOUETTE] 毛发抠像管线已创建")
    print("  层级: 身体 + 毛发内层 + 毛发外层 + 飘散层")
    print("  运动模糊: shutter=0.5")
    return roto
```

### 6.2 半透明纱裙抠像

```python
def create_veil_keying(session, src_node):
    """半透明纱裙抠像"""
    roto = Node("RotoNode")
    roto.label = "Veil_Roto"
    session.addNode(roto)

    # === 纱裙主体（30% 透明度）===
    veil = roto.createObject("X-Spline")
    veil.name = "Veil_Main"
    veil.property("feather").setValue(5.0, 0)
    veil.property("opacity").setValue(0.3, 0)
    veil.property("blur").setValue(1.5, 0)

    # === 纱裙褶皱高光（50% 透明度）===
    fold = roto.createObject("X-Spline")
    fold.name = "Veil_Folds"
    fold.property("feather").setValue(2.0, 0)
    fold.property("opacity").setValue(0.5, 0)

    # === 纱裙边缘飘散（15% 透明度）===
    edge = roto.createObject("X-Spline")
    edge.name = "Veil_Edge"
    edge.property("feather").setValue(10.0, 0)
    edge.property("opacity").setValue(0.15, 0)
    edge.property("motionBlur").setValue(true, 0)
    edge.property("motionBlur.shutter").setValue(0.6, 0)

    src_node.outputs[0].connect(roto.inputs[1])
    return roto
```

### 6.3 玻璃器皿抠像

```python
def create_glass_keying(session, src_node):
    """玻璃器皿抠像"""
    roto = Node("RotoNode")
    roto.label = "Glass_Roto"
    session.addNode(roto)

    # === 玻璃主体（70% 透明度）===
    glass = roto.createObject("Bezier")
    glass.name = "Glass_Body"
    glass.property("feather").setValue(2.0, 0)
    glass.property("opacity").setValue(0.7, 0)

    # === 反光高亮（90% 不透明）===
    highlight = roto.createObject("Bezier")
    highlight.name = "Glass_Highlight"
    highlight.property("feather").setValue(1.0, 0)
    highlight.property("opacity").setValue(0.9, 0)

    # === 折射区（40% 透明度）===
    refraction = roto.createObject("Bezier")
    refraction.name = "Glass_Refraction"
    refraction.property("feather").setValue(3.0, 0)
    refraction.property("opacity").setValue(0.4, 0)

    # === 阴影区（60% 透明度）===
    shadow = roto.createObject("Bezier")
    shadow.name = "Glass_Shadow"
    shadow.property("feather").setValue(4.0, 0)
    shadow.property("opacity").setValue(0.6, 0)

    src_node.outputs[0].connect(roto.inputs[1])
    return roto
```

### 6.4 烟雾抠像

```python
def create_smoke_keying(session, src_node):
    """烟雾抠像（动态透明度）"""
    roto = Node("RotoNode")
    roto.label = "Smoke_Roto"
    session.addNode(roto)

    # === 烟雾核心（动态透明度）===
    core = roto.createObject("X-Spline")
    core.name = "Smoke_Core"
    core.property("feather").setValue(15.0, 0)
    core.property("featherFalloff").setValue(0.8, 0)

    # 透明度动画：从浓到淡
    for frame in range(0, 60):
        if frame < 10:
            opacity = 0.9  # 初始浓密
        elif frame < 30:
            opacity = 0.9 - (frame - 10) * 0.02  # 逐渐稀释
        else:
            opacity = 0.5 - (frame - 30) * 0.01  # 消散
        opacity = max(0.05, opacity)
        core.property("opacity").setValue(opacity, frame)

    # === 烟雾边缘飘散 ===
    edge = roto.createObject("X-Spline")
    edge.name = "Smoke_Edge"
    edge.property("feather").setValue(25.0, 0)
    edge.property("opacity").setValue(0.3, 0)
    edge.property("blur").setValue(3.0, 0)

    src_node.outputs[0].connect(roto.inputs[1])
    return roto
```

---

## 七、常见问题与最佳实践

### 7.1 问题诊断

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 毛发"剪影感" | 羽化过小 | 增加外层羽化到 8-15px |
| 毛发"消失" | 透明度过低 | 提高飘散层 opacity 到 0.5-0.7 |
| 毛发"漂浮" | 边缘溢色 | 启用 Despill，alpha.shrink 0.5px |
| 玻璃"太实" | 透明度未设 | opacity 设为 0.6-0.8 |
| 烟雾"颗粒感" | 羽化太小 | 增加到 15-25px，blur=2-3 |
| 纱裙"网格消失" | 单层遮罩 | 分层 + 多 opacity |
| 运动时毛发断裂 | 关键帧不够 | 增加关键帧，启用 motionBlur |

### 7.2 最佳实践

1. **分层优于单层**：将复杂边缘拆分为 3-5 层，每层不同羽化和透明度。
2. **opacity 关键帧**：半透明物体的 opacity 必须随时间变化，否则不真实。
3. **motionBlur 必开**：毛发和半透明物体运动时必须有运动模糊。
4. **颜色溢出处理**：抠像后用 Despill 节点处理边缘色溢。
5. **多通道融合**：复杂场景用 Roto + Color Key + Luma Key 多通道相乘。
6. **保留细节**：宁可保留 5% 杂色，也不要"抠秃"细节。
7. **测试背景**：抠像后在黑白格背景上检查半透明效果。

### 7.3 性能建议

- 毛发分层 ≤ 5 层，过多会拖慢渲染。
- 飘散层使用 `motionBlur.samples=4`（预览）或 `8`（最终）。
- 半透明形状启用 `blur` 而非 `alpha.blur`（性能更好）。
- 复杂场景使用 `proxy` 模式预览。

### 7.4 质量检查清单

- [ ] 毛发边缘自然过渡（无硬边）
- [ ] 透明度随运动合理变化
- [ ] 运动模糊方向与运动一致
- [ ] 颜色溢出已处理
- [ ] 多层 opacity 协调
- [ ] 黑白格背景测试通过
- [ ] 细节保留充分（不"抠秃"）
- [ ] 半透明区无"沸腾"

---

## 相关文档

- [Silhouette 边缘优化与运动模糊](Silhouette%20边缘优化与运动模糊.md)
- [Silhouette 智能遮罩与AI辅助抠像](Silhouette%20智能遮罩与AI辅助抠像.md)
- [Silhouette 硬边与柔边遮罩技巧](Silhouette%20硬边与柔边遮罩技巧.md)
- [Silhouette 多形状管理与层级控制](Silhouette%20多形状管理与层级控制.md)
