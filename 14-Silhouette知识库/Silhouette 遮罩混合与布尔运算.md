# Silhouette 遮罩混合与布尔运算

> 分类: Roto抠像专题
> 更新日期: 2026-07-11
> 概述: 系统讲解遮罩布尔运算（合并/相减/相交/异或）、混合模式、运算优先级与组合策略，提供生产级代码示例。

## 目录
1. [布尔运算总览](#一布尔运算总览)
2. [四种布尔运算类型](#二四种布尔运算类型)
3. [混合模式](#三混合模式)
4. [运算优先级](#四运算优先级)
5. [组合策略](#五组合策略)
6. [代码示例](#六代码示例)
7. [常见问题与最佳实践](#七常见问题与最佳实践)

---

## 一、布尔运算总览

### 1.1 布尔运算原理

```
形状 A + 形状 B → 布尔运算 → 最终遮罩

┌─────────┐    ┌─────────┐
│         │    │         │
│   A     │    │   B     │
│         │    │         │
└─────────┘    └─────────┘
     ↘            ↙
        布尔运算
            ↓
┌───────────────────┐
│                   │
│   最终遮罩         │
│                   │
└───────────────────┘
```

### 1.2 应用场景

| 场景 | 运算 | 描述 |
|------|------|------|
| 多形状合并 | Union | 多个形状合并为一个遮罩 |
| 遮挡处理 | Subtract | 前景物体遮挡背景 |
| 交集提取 | Intersect | 仅保留重叠区域 |
| 排除区域 | XOR | 排除重叠部分 |
| 半透明叠加 | Add/Subtract | 多层透明度合成 |

---

## 二、四种布尔运算类型

### 2.1 Union（合并/相加）

```
形状 A:     形状 B:     Union 结果:
┌──────┐   ┌──────┐    ┌────────────┐
│      │   │      │    │            │
│  A   │   │  B   │    │   A + B    │
│      │   │      │    │            │
└──────┘   └──────┘    └────────────┘
```

```python
from fx import *

def create_union_shapes(roto_node):
    """创建合并运算的形状"""
    shape_a = roto_node.createObject("X-Spline")
    shape_a.name = "Shape_A"
    shape_a.property("blendMode").setValue("union", 0)

    shape_b = roto_node.createObject("X-Spline")
    shape_b.name = "Shape_B"
    shape_b.property("blendMode").setValue("union", 0)

    # 两个形状合并为一个大遮罩
    return shape_a, shape_b
```

### 2.2 Subtract（相减）

```
形状 A:     形状 B:     Subtract 结果:
┌──────┐   ┌──────┐    ┌──────┐
│      │   │      │    │ A    │
│  A   │ - │  B   │ =  │      │  (B 区域从 A 中减去)
│      │   │      │    │      │
└──────┘   └──────┘    └──────┘
```

```python
def create_subtract_shapes(roto_node):
    """创建相减运算的形状"""
    # 主形状（被减）
    main_shape = roto_node.createObject("X-Spline")
    main_shape.name = "Main_Shape"
    main_shape.property("blendMode").setValue("union", 0)  # 默认合并

    # 减去形状（遮挡物）
    subtract_shape = roto_node.createObject("X-Spline")
    subtract_shape.name = "Subtract_Shape"
    subtract_shape.property("blendMode").setValue("subtract", 0)  # 相减

    # subtract_shape 会从 main_shape 中减去
    return main_shape, subtract_shape
```

### 2.3 Intersect（相交）

```
形状 A:     形状 B:     Intersect 结果:
┌──────┐   ┌──────┐    ┌──────┐
│      │   │      │    │ A∩B  │
│  A   │ ∩ │  B   │ =  │      │  (仅保留重叠区域)
│      │   │      │    │      │
└──────┘   └──────┘    └──────┘
```

```python
def create_intersect_shapes(roto_node):
    """创建相交运算的形状"""
    shape_a = roto_node.createObject("X-Spline")
    shape_a.name = "Shape_A"
    shape_a.property("blendMode").setValue("union", 0)

    shape_b = roto_node.createObject("X-Spline")
    shape_b.name = "Shape_B"
    shape_b.property("blendMode").setValue("intersect", 0)  # 相交

    # 最终遮罩仅包含 A 和 B 重叠的区域
    return shape_a, shape_b
```

### 2.4 XOR（异或）

```
形状 A:     形状 B:     XOR 结果:
┌──────┐   ┌──────┐    ┌──────┐    ┌──────┐
│      │   │      │    │ A    │    │  B   │
│  A   │ ⊕ │  B   │ =  │      │    │      │  (排除重叠区域)
│      │   │      │    │      │    │      │
└──────┘   └──────┘    └──────┘    └──────┘
```

```python
def create_xor_shapes(roto_node):
    """创建异或运算的形状"""
    shape_a = roto_node.createObject("X-Spline")
    shape_a.name = "Shape_A"
    shape_a.property("blendMode").setValue("union", 0)

    shape_b = roto_node.createObject("X-Spline")
    shape_b.name = "Shape_B"
    shape_b.property("blendMode").setValue("xor", 0)  # 异或

    # 最终遮罩排除 A 和 B 重叠的区域
    return shape_a, shape_b
```

### 2.5 运算类型对照表

| 运算 | 标识 | 公式 | 应用 |
|------|------|------|------|
| Union | `"union"` | A ∪ B | 合并多个形状 |
| Subtract | `"subtract"` | A - B | 遮挡、挖洞 |
| Intersect | `"intersect"` | A ∩ B | 提取重叠区 |
| XOR | `"xor"` | A ⊕ B | 排除重叠区 |
| Replace | `"replace"` | B 替换 A | 完全覆盖 |
| Merge | `"merge"` | A + B (透明度叠加) | 半透明合成 |

---

## 三、混合模式

### 3.1 混合模式 vs 布尔运算

```
布尔运算: 二值操作（0/1）
混合模式: 灰度操作（0-1 连续值）
```

### 3.2 混合模式列表

| 模式 | 标识 | 公式 | 应用 |
|------|------|------|------|
| **Over** | `"over"` | A + B(1-A) | 标准合成 |
| **Add** | `"add"` | A + B | 发光叠加 |
| **Subtract** | `"subtract"` | A - B | 减去 |
| **Multiply** | `"multiply"` | A × B | 阴影、遮罩 |
| **Screen** | `"screen"` | 1-(1-A)(1-B) | 屏幕叠加 |
| **Min** | `"min"` | min(A, B) | 取较小值 |
| **Max** | `"max"` | max(A, B) | 取较大值 |
| **Difference** | `"difference"` | \|A - B\| | 差值 |

### 3.3 设置混合模式

```python
def set_blend_modes(roto_node):
    """设置不同混合模式"""
    shapes = roto_node.objects

    # 第一个形状：基础（合并模式）
    shapes[0].property("blendMode").setValue("union", 0)

    # 第二个形状：相减（遮挡）
    shapes[1].property("blendMode").setValue("subtract", 0)

    # 第三个形状：相加（发光）
    shapes[2].property("blendMode").setValue("add", 0)

    # 第四个形状：正片叠底（阴影）
    shapes[3].property("blendMode").setValue("multiply", 0)
```

### 3.4 混合模式 + 透明度

```python
def blended_with_opacity(roto_node):
    """混合模式配合透明度"""
    # 形状 A：基础遮罩 100%
    shape_a = roto_node.createObject("X-Spline")
    shape_a.name = "Base_Matte"
    shape_a.property("blendMode").setValue("union", 0)
    shape_a.property("opacity").setValue(1.0, 0)

    # 形状 B：半透明叠加 50%
    shape_b = roto_node.createObject("X-Spline")
    shape_b.name = "Overlay_Half"
    shape_b.property("blendMode").setValue("over", 0)
    shape_b.property("opacity").setValue(0.5, 0)

    # 形状 C：阴影 30%
    shape_c = roto_node.createObject("X-Spline")
    shape_c.name = "Shadow"
    shape_c.property("blendMode").setValue("multiply", 0)
    shape_c.property("opacity").setValue(0.3, 0)
```

---

## 四、运算优先级

### 4.1 优先级原理

```
形状渲染顺序（从下到上）:
1. Shape_A (union)      ← 先渲染（底层）
2. Shape_B (subtract)   ← 在 A 之上渲染
3. Shape_C (intersect)  ← 在 B 之上渲染
4. Shape_D (add)        ← 最后渲染（顶层）

最终结果: (((A) - B) ∩ C) + D
```

### 4.2 优先级控制

```python
def set_operation_priority(roto_node):
    """设置运算优先级"""
    # 通过 priority 属性控制顺序
    # 值小的先渲染（底层），值大的后渲染（顶层）

    base = roto_node.objects[0]
    base.property("priority").setValue(0, 0)  # 最先
    base.property("blendMode").setValue("union", 0)

    subtractor = roto_node.objects[1]
    subtractor.property("priority").setValue(1, 0)
    subtractor.property("blendMode").setValue("subtract", 0)

    intersector = roto_node.objects[2]
    intersector.property("priority").setValue(2, 0)
    intersector.property("blendMode").setValue("intersect", 0)

    adder = roto_node.objects[3]
    adder.property("priority").setValue(3, 0)  # 最后
    adder.property("blendMode").setValue("add", 0)
```

### 4.3 优先级示例

```
场景：人物 + 道具 + 阴影

priority 0: Body (union)         ← 基础身体遮罩
priority 1: Arm_Left (union)     ← 左臂合并
priority 2: Arm_Right (union)    ← 右臂合并
priority 3: Watch (union)        ← 手表合并
priority 4: Glasses (subtract)   ← 眼镜挖洞（如有需要）
priority 5: Shadow (multiply)    ← 阴影叠加

最终: Body + Arms + Watch - Glasses × Shadow
```

---

## 五、组合策略

### 5.1 遮挡处理策略

```python
def create_occlusion_setup(roto_node):
    """创建遮挡关系"""
    # 前景物体（遮挡者）
    foreground = roto_node.createObject("X-Spline")
    foreground.name = "Foreground"
    foreground.property("blendMode").setValue("union", 0)
    foreground.property("priority").setValue(2, 0)  # 后渲染

    # 背景物体（被遮挡者）
    background = roto_node.createObject("X-Spline")
    background.name = "Background"
    background.property("blendMode").setValue("union", 0)
    background.property("priority").setValue(1, 0)  # 先渲染

    # 遮挡遮罩（从背景中减去前景）
    occlusion = roto_node.createObject("X-Spline")
    occlusion.name = "Occlusion"
    occlusion.property("blendMode").setValue("subtract", 0)
    occlusion.property("priority").setValue(3, 0)  # 最后渲染
    # occlusion 形状与 foreground 一致

    return foreground, background, occlusion
```

### 5.2 多层半透明合成

```python
def create_layered_transparency(roto_node):
    """创建多层半透明合成"""
    layers = []

    # 底层：身体（100%）
    body = roto_node.createObject("X-Spline")
    body.name = "Layer_Body"
    body.property("blendMode").setValue("union", 0)
    body.property("opacity").setValue(1.0, 0)
    body.property("priority").setValue(0, 0)
    layers.append(body)

    # 中层：衣物（70%）
    cloth = roto_node.createObject("X-Spline")
    cloth.name = "Layer_Cloth"
    cloth.property("blendMode").setValue("over", 0)
    cloth.property("opacity").setValue(0.7, 0)
    cloth.property("priority").setValue(1, 0)
    layers.append(cloth)

    # 上层：纱裙（30%）
    veil = roto_node.createObject("X-Spline")
    veil.name = "Layer_Veil"
    veil.property("blendMode").setValue("over", 0)
    veil.property("opacity").setValue(0.3, 0)
    veil.property("priority").setValue(2, 0)
    layers.append(veil)

    # 顶层：高光（50%）
    highlight = roto_node.createObject("X-Spline")
    highlight.name = "Layer_Highlight"
    highlight.property("blendMode").setValue("add", 0)
    highlight.property("opacity").setValue(0.5, 0)
    highlight.property("priority").setValue(3, 0)
    layers.append(highlight)

    return layers
```

### 5.3 复杂物体分解

```python
def decompose_complex_object(roto_node):
    """复杂物体分解（如：手持花朵）"""
    # 主手部
    hand = roto_node.createObject("X-Spline")
    hand.name = "Hand"
    hand.property("blendMode").setValue("union", 0)
    hand.property("priority").setValue(0, 0)

    # 手指间空隙（相减）
    for i in range(4):  # 4 个手指间隙
        gap = roto_node.createObject("X-Spline")
        gap.name = f"Finger_Gap_{i}"
        gap.property("blendMode").setValue("subtract", 0)
        gap.property("priority").setValue(i + 1, 0)

    # 花朵（合并，在手上方）
    flower = roto_node.createObject("X-Spline")
    flower.name = "Flower"
    flower.property("blendMode").setValue("union", 0)
    flower.property("priority").setValue(5, 0)

    # 花茎（相减，被手握住的部分）
    stem_hidden = roto_node.createObject("X-Spline")
    stem_hidden.name = "Stem_Hidden"
    stem_hidden.property("blendMode").setValue("subtract", 0)
    stem_hidden.property("priority").setValue(6, 0)

    return hand, flower
```

---

## 六、代码示例

### 6.1 完整布尔运算管线

```python
from fx import *

def create_boolean_pipeline(source_path, output_path, frame_rate=24.0):
    """创建布尔运算完整管线"""
    proj = activeProject() or Project()
    activate(proj)
    session = activeSession() or Session()
    session.label = "Boolean_Operations"
    activate(session)
    proj.addItem(session)

    src = Node("SourceNode")
    src.property("mediaPath").setValue(source_path.replace("\\", "/"), 0)
    src.property("frameRate").setValue(frame_rate, 0)
    session.addNode(src)

    roto = Node("RotoNode")
    roto.label = "Boolean_Roto"
    roto.property("alpha.blur").setValue(0.3, 0)
    roto.property("antialias").setValue(1.0, 0)
    session.addNode(roto)

    # === 形状 A：基础（union）===
    shape_a = roto.createObject("X-Spline")
    shape_a.name = "Shape_A_Base"
    shape_a.property("blendMode").setValue("union", 0)
    shape_a.property("priority").setValue(0, 0)
    shape_a.property("feather").setValue(1.0, 0)

    # 添加点
    for pt in [(400, 300), (800, 300), (800, 700), (400, 700)]:
        shape_a.addPoint(pt)

    # === 形状 B：合并（union）===
    shape_b = roto.createObject("X-Spline")
    shape_b.name = "Shape_B_Union"
    shape_b.property("blendMode").setValue("union", 0)
    shape_b.property("priority").setValue(1, 0)
    shape_b.property("feather").setValue(1.0, 0)

    for pt in [(700, 400), (1100, 400), (1100, 800), (700, 800)]:
        shape_b.addPoint(pt)

    # === 形状 C：相减（subtract）===
    shape_c = roto.createObject("X-Spline")
    shape_c.name = "Shape_C_Subtract"
    shape_c.property("blendMode").setValue("subtract", 0)
    shape_c.property("priority").setValue(2, 0)
    shape_c.property("feather").setValue(1.0, 0)

    for pt in [(550, 450), (650, 450), (650, 550), (550, 550)]:
        shape_c.addPoint(pt)

    # === 输出 ===
    out_node = Node("OutputNode")
    out_node.property("path").setValue(output_path.replace("\\", "/"), 0)
    out_node.property("format").setValue("exr", 0)
    session.addNode(out_node)

    src.outputs[0].connect(roto.inputs[1])
    roto.outputs[0].connect(out_node.inputs[0])

    print("[SILHOUETTE] 布尔运算管线已创建")
    print("  A (union) + B (union) - C (subtract)")
    return roto
```

### 6.2 遮挡遮罩

```python
def create_holdout_pipeline(source_path, output_path, frame_rate=24.0):
    """创建遮挡遮罩管线"""
    proj = activeProject() or Project()
    activate(proj)
    session = activeSession() or Session()
    session.label = "Holdout_Matte"
    activate(session)
    proj.addItem(session)

    src = Node("SourceNode")
    src.property("mediaPath").setValue(source_path.replace("\\", "/"), 0)
    src.property("frameRate").setValue(frame_rate, 0)
    session.addNode(src)

    roto = Node("RotoNode")
    roto.label = "Holdout_Roto"
    session.addNode(roto)

    # 背景物体
    background = roto.createObject("X-Spline")
    background.name = "Background_Object"
    background.property("blendMode").setValue("union", 0)
    background.property("priority").setValue(0, 0)

    # 前景遮挡（从背景中减去）
    foreground = roto.createObject("X-Spline")
    foreground.name = "Foreground_Occlusion"
    foreground.property("blendMode").setValue("subtract", 0)
    foreground.property("priority").setValue(1, 0)

    out_node = Node("OutputNode")
    out_node.property("path").setValue(output_path.replace("\\", "/"), 0)
    out_node.property("format").setValue("exr", 0)
    session.addNode(out_node)

    src.outputs[0].connect(roto.inputs[1])
    roto.outputs[0].connect(out_node.inputs[0])

    print("[SILHOUETTE] 遮挡遮罩管线已创建")
    return roto
```

### 6.3 多形状合成报告

```python
def analyze_blend_setup(roto_node):
    """分析当前混合设置"""
    report = {
        "total_shapes": 0,
        "blend_modes": {},
        "priority_order": []
    }

    shapes = roto_node.objects
    for shape in shapes:
        blend = shape.property("blendMode").getValue(0)
        priority = shape.property("priority").getValue(0)
        opacity = shape.property("opacity").getValue(0)

        report["total_shapes"] += 1
        report["blend_modes"][blend] = report["blend_modes"].get(blend, 0) + 1
        report["priority_order"].append({
            "name": shape.name,
            "priority": priority,
            "blend": blend,
            "opacity": opacity
        })

    # 按 priority 排序
    report["priority_order"].sort(key=lambda x: x["priority"])

    print("=== 混合设置分析 ===")
    print(f"总形状数: {report['total_shapes']}")
    print(f"混合模式分布: {report['blend_modes']}")
    print("\n渲染顺序:")
    for item in report["priority_order"]:
        print(f"  [{item['priority']}] {item['name']}: "
              f"{item['blend']} (opacity={item['opacity']})")

    return report
```

---

## 七、常见问题与最佳实践

### 7.1 问题诊断

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 相减后"空洞" | subtract 形状过大 | 减小 subtract 形状范围 |
| 合并后边缘不齐 | 羽化不一致 | 统一所有形状的 feather 值 |
| 渲染顺序错误 | priority 未设 | 按 priority 表设置 |
| 半透明叠加异常 | opacity + blendMode 冲突 | 测试不同 blendMode |
| 布尔运算闪烁 | 形状动画不同步 | 同步关键帧 |
| 遮挡关系错误 | priority 反了 | 前景 priority > 背景 |

### 7.2 最佳实践

1. **基础形状用 union**：所有形状默认 union 作为基础。
2. **遮挡用 subtract**：前景物体遮挡背景时用 subtract。
3. **priority 明确**：每个形状设置 priority 值。
4. **羽化统一**：参与布尔运算的形状羽化值一致。
5. **半透明分层**：用 over 模式 + opacity 实现半透明叠加。
6. **测试顺序**：复杂运算后用 `analyze_blend_setup` 验证。

### 7.3 性能建议

- 布尔运算形状数 ≤ 10/Node，过多影响性能。
- 复杂运算拆分多 RotoNode。
- 预览时降低 motionBlur samples。
- 启用 proxy 模式。

### 7.4 质量检查清单

- [ ] 所有 blendMode 设置正确
- [ ] priority 顺序明确
- [ ] 羽化值统一
- [ ] 遮挡关系正确
- [ ] 半透明效果自然
- [ ] 无"空洞"或"穿帮"
- [ ] 动画同步
- [ ] 渲染顺序验证

---

## 相关文档

- [Silhouette 多形状管理与层级控制](Silhouette%20多形状管理与层级控制.md)
- [Silhouette 形状层与关键帧动画](Silhouette%20形状层与关键帧动画.md)
- [Silhouette Roto工作流最佳实践](Silhouette%20Roto工作流最佳实践.md)
- [Silhouette 遮罩质量检查与优化](Silhouette%20遮罩质量检查与优化.md)
