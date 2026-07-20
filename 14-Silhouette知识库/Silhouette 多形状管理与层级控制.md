# Silhouette 多形状管理与层级控制

> 分类: Roto抠像专题
> 更新日期: 2026-07-11
> 概述: 系统讲解多形状组织、父子层级、渲染顺序、形状分组与命名规范，提供复杂场景的形状管理最佳实践。

## 目录
1. [多形状管理总览](#一多形状管理总览)
2. [形状组织结构](#二形状组织结构)
3. [父子关系与层级](#三父子关系与层级)
4. [层级渲染顺序](#四层级渲染顺序)
5. [形状分组](#五形状分组)
6. [命名规范](#六命名规范)
7. [代码示例](#七代码示例)
8. [常见问题与最佳实践](#八常见问题与最佳实践)

---

## 一、多形状管理总览

### 1.1 为什么需要多形状管理

```
单形状方案（不推荐）:          多形状方案（推荐）:
┌───────────────────┐         ┌─ Head ──────────┐
│                   │         ├─ Hair ──────────┤
│   一个形状描述     │         ├─ Body ──────────┤
│   整个复杂角色     │         ├─ LeftArm ───────┤
│                   │         ├─ RightArm ──────┤
│   问题:           │         ├─ LeftLeg ───────┤
│   - 点数过多       │         ├─ RightLeg ──────┤
│   - 动画困难       │         └─ Props ─────────┘
│   - 无法局部调整   │
│   - 性能差         │         优势:
└───────────────────┘         - 独立动画
                              - 局部调整
                              - 性能优
                              - 可复用
```

### 1.2 多形状管理的核心目标

| 目标 | 描述 |
|------|------|
| **组织清晰** | 形状按部位/功能分组，易于定位 |
| **层级合理** | 父子关系正确，变换继承自然 |
| **渲染顺序** | 优先级明确，遮挡关系正确 |
| **命名规范** | 团队统一命名，可读性强 |
| **性能可控** | 单 Node 形状数合理，避免卡顿 |

---

## 二、形状组织结构

### 2.1 RotoNode 内部结构

```
RotoNode
├── Layer "Character"              # 顶层角色层
│   ├── Layer "Head"               # 头部子层
│   │   ├── Shape "Head_Skull"     # 头颅形状
│   │   ├── Shape "Hair_Main"      # 主发形状
│   │   └── Shape "Hair_Flyaway"   # 飘发形状
│   ├── Layer "Torso"              # 躯干子层
│   │   ├── Shape "Body_Shirt"     # 上衣
│   │   └── Shape "Body_Skin"      # 皮肤
│   ├── Layer "Arms"               # 手臂子层
│   │   ├── Shape "Arm_Left"
│   │   └── Shape "Arm_Right"
│   └── Layer "Legs"               # 腿部子层
│       ├── Shape "Leg_Left"
│       └── Shape "Leg_Right"
└── Layer "Props"                  # 道具层
    ├── Shape "Glasses"
    └── Shape "Watch"
```

### 2.2 创建层级结构

```python
from fx import *

def create_structured_character(session, src_node):
    """创建结构化角色"""
    roto = Node("RotoNode")
    roto.label = "Character_Structured"
    session.addNode(roto)

    # === 顶层角色层 ===
    char_layer = roto.createLayer("Character")

    # === 头部子层 ===
    head_layer = char_layer.createLayer("Head")
    head_skull = roto.createObject("X-Spline", parent=head_layer)
    head_skull.name = "Head_Skull"

    hair_main = roto.createObject("X-Spline", parent=head_layer)
    hair_main.name = "Hair_Main"

    hair_flyaway = roto.createObject("X-Spline", parent=head_layer)
    hair_flyaway.name = "Hair_Flyaway"

    # === 躯干子层 ===
    torso_layer = char_layer.createLayer("Torso")
    body_shirt = roto.createObject("X-Spline", parent=torso_layer)
    body_shirt.name = "Body_Shirt"

    body_skin = roto.createObject("X-Spline", parent=torso_layer)
    body_skin.name = "Body_Skin"

    # === 手臂子层 ===
    arms_layer = char_layer.createLayer("Arms")
    arm_left = roto.createObject("X-Spline", parent=arms_layer)
    arm_left.name = "Arm_Left"

    arm_right = roto.createObject("X-Spline", parent=arms_layer)
    arm_right.name = "Arm_Right"

    # === 腿部子层 ===
    legs_layer = char_layer.createLayer("Legs")
    leg_left = roto.createObject("X-Spline", parent=legs_layer)
    leg_left.name = "Leg_Left"

    leg_right = roto.createObject("X-Spline", parent=legs_layer)
    leg_right.name = "Leg_Right"

    # === 道具层 ===
    props_layer = roto.createLayer("Props")
    glasses = roto.createObject("Bezier", parent=props_layer)
    glasses.name = "Glasses"

    watch = roto.createObject("Bezier", parent=props_layer)
    watch.name = "Watch"

    src_node.outputs[0].connect(roto.inputs[1])
    return roto
```

---

## 三、父子关系与层级

### 3.1 父子关系原理

```
父层变换 → 子层继承
位置 (x, y) → 子层位置 += 父层位置
旋转 (θ)    → 子层围绕父层旋转中心旋转
缩放 (s)    → 子层缩放 *= 父层缩放
不透明度    → 子层 opacity *= 父层 opacity
可见性      → 父层不可见 → 子层不可见
```

### 3.2 设置父子关系

```python
def setup_parent_child(roto_node):
    """设置父子关系"""
    # 方法 1: 创建时指定父层
    parent_layer = roto_node.createLayer("Parent")
    child_shape = roto_node.createObject("X-Spline", parent=parent_layer)
    child_shape.name = "Child_Shape"

    # 方法 2: 后期修改父级
    another_shape = roto_node.createObject("X-Spline")
    another_shape.parent = parent_layer

    # 方法 3: 解除父子关系
    another_shape.parent = None  # 移到根级

    return parent_layer, child_shape
```

### 3.3 父层变换动画

```python
def animate_parent_transform(parent_layer, frame_range):
    """动画父层变换（子层自动继承）"""
    # 父层位置动画
    parent_layer.property("transform.position").setValue((960, 540), frame_range[0])
    parent_layer.property("transform.position").setValue((1100, 600), frame_range[-1])

    # 父层旋转动画
    parent_layer.property("transform.rotation").setValue(0, frame_range[0])
    parent_layer.property("transform.rotation").setValue(15, frame_range[-1])

    # 父层缩放动画
    parent_layer.property("transform.scale").setValue(1.0, frame_range[0])
    parent_layer.property("transform.scale").setValue(1.1, frame_range[-1])

    # 子层会自动跟随这些变换
```

### 3.4 嵌套层级示例

```python
def create_nested_hierarchy(roto_node):
    """创建嵌套层级（角色 → 手臂 → 手 → 手指）"""
    # L1: 角色层
    char = roto_node.createLayer("Character")

    # L2: 手臂层
    arm = char.createLayer("Arm_Left")

    # L3: 手层
    hand = arm.createLayer("Hand_Left")

    # L4: 手指层
    for finger_name in ["Thumb", "Index", "Middle", "Ring", "Pinky"]:
        finger = hand.createLayer(f"Finger_{finger_name}")
        finger_shape = roto_node.createObject("X-Spline", parent=finger)
        finger_shape.name = f"Finger_{finger_name}_Shape"

    # 这样，手指会跟随手 → 手臂 → 角色的所有变换
    return char
```

---

## 四、层级渲染顺序

### 4.1 渲染顺序原理

```
渲染顺序（从下到上，后渲染的覆盖先渲染的）:

顶层  ┌─────────────────────┐  最后渲染（最上层）
      │ 眼睛                 │
      ├─────────────────────┤
      │ 嘴唇                 │
      ├─────────────────────┤
      │ 鼻子                 │
      ├─────────────────────┤
      │ 脸部皮肤             │
      ├─────────────────────┤
      │ 头发                 │
      ├─────────────────────┤
      │ 头部轮廓             │
      ├─────────────────────┤
      │ 身体                 │
底层  └─────────────────────┘  最先渲染（最下层）
```

### 4.2 控制渲染顺序

```python
def set_render_order(roto_node):
    """设置渲染顺序"""
    shapes = roto_node.objects

    # 按 priority 值排序（值小的先渲染，在下层）
    render_order = [
        "Body",           # 最底层
        "Head_Skull",
        "Hair_Main",
        "Face_Skin",
        "Nose",
        "Mouth",
        "Eyes",
        "Glasses",        # 最顶层
    ]

    for i, shape_name in enumerate(render_order):
        for shape in shapes:
            if shape.name == shape_name:
                shape.property("priority").setValue(i, 0)
                break

    print(f"[ORDER] 已设置 {len(render_order)} 个形状的渲染顺序")
```

### 4.3 调整形状顺序

```python
def reorder_shapes(roto_node):
    """调整形状顺序"""
    # 将指定形状上移
    shape = find_shape_by_name(roto_node, "Glasses")
    if shape:
        shape.bringToFront()  # 移到最前

    # 将指定形状下移
    shape = find_shape_by_name(roto_node, "Body")
    if shape:
        shape.sendToBack()  # 移到最后

    # 相对调整
    shape = find_shape_by_name(roto_node, "Eyes")
    if shape:
        shape.moveUp()  # 上移一层
        # shape.moveDown()  # 下移一层

def find_shape_by_name(roto_node, name):
    """按名称查找形状"""
    for shape in roto_node.objects:
        if shape.name == name:
            return shape
    return None
```

### 4.4 层级渲染优先级表

| 部位 | priority | 说明 |
|------|----------|------|
| 身体 | 0 | 最底层 |
| 头部轮廓 | 1 | - |
| 头发主层 | 2 | - |
| 面部皮肤 | 3 | - |
| 鼻子 | 4 | - |
| 嘴唇 | 5 | - |
| 眼睛 | 6 | - |
| 眉毛 | 7 | - |
| 眼镜 | 8 | - |
| 帽子 | 9 | 最顶层 |

---

## 五、形状分组

### 5.1 分组策略

```
按部位分组:    按功能分组:    按边缘类型分组:
- 头部组       - 主轮廓组     - 硬边组
- 躯干组       - 细节组       - 柔边组
- 四肢组       - 道具组       - 半透明组
- 道具组       - 遮挡组       - 运动模糊组
```

### 5.2 创建分组

```python
def create_shape_groups(roto_node):
    """创建形状分组"""
    # === 按部位分组 ===
    head_group = roto_node.createLayer("Group_Head")
    body_group = roto_node.createLayer("Group_Body")
    limbs_group = roto_node.createLayer("Group_Limbs")
    props_group = roto_node.createLayer("Group_Props")

    # === 添加形状到分组 ===
    head_shapes = ["Head_Skull", "Hair_Main", "Face_Skin", "Eyes", "Mouth"]
    for name in head_shapes:
        shape = find_shape_by_name(roto_node, name)
        if shape:
            shape.parent = head_group

    body_shapes = ["Body_Shirt", "Body_Skin", "Body_Pants"]
    for name in body_shapes:
        shape = find_shape_by_name(roto_node, name)
        if shape:
            shape.parent = body_group

    return head_group, body_group, limbs_group, props_group
```

### 5.3 分组操作

```python
def group_operations(roto_node):
    """分组批量操作"""
    # === 批量可见性切换 ===
    props_group = find_layer_by_name(roto_node, "Group_Props")
    if props_group:
        props_group.visible = false  # 隐藏所有道具

    # === 批量锁定 ===
    body_group = find_layer_by_name(roto_node, "Group_Body")
    if body_group:
        body_group.locked = true  # 锁定身体组

    # === 批量不透明度 ===
    hair_group = find_layer_by_name(roto_node, "Group_Hair")
    if hair_group:
        hair_group.opacity = 0.8  # 整组不透明度

    # === 批量颜色标识 ===
    head_group = find_layer_by_name(roto_node, "Group_Head")
    if head_group:
        head_group.color = (1, 0, 0)  # 红色标识

def find_layer_by_name(roto_node, name):
    """按名称查找层"""
    for layer in roto_node.layers:
        if layer.name == name:
            return layer
    return None
```

---

## 六、命名规范

### 6.1 命名规则

```
[部位]_[子部位]_[细节]_[方向]

示例:
- Head_Skull_Main
- Arm_Left_Upper
- Hair_Main_Long
- Eye_Right_Iris
```

### 6.2 命名规范表

| 部位 | 命名前缀 | 示例 |
|------|---------|------|
| 头部 | Head_ | Head_Skull, Head_Jaw |
| 头发 | Hair_ | Hair_Main, Hair_Flyaway |
| 面部 | Face_ | Face_Skin, Face_Nose |
| 眼睛 | Eye_ | Eye_Left, Eye_Right |
| 嘴部 | Mouth_ | Mouth_Lips, Mouth_Teeth |
| 躯干 | Body_ | Body_Shirt, Body_Skin |
| 手臂 | Arm_ | Arm_Left, Arm_Right |
| 手部 | Hand_ | Hand_Left, Hand_Right |
| 腿部 | Leg_ | Leg_Left, Leg_Right |
| 脚部 | Foot_ | Foot_Left, Foot_Right |
| 道具 | Prop_ | Prop_Glasses, Prop_Watch |

### 6.3 方向标识

| 方向 | 标识 | 示例 |
|------|------|------|
| 左 | L 或 Left | Arm_Left |
| 右 | R 或 Right | Arm_Right |
| 上 | Upper | Arm_Left_Upper |
| 下 | Lower | Arm_Left_Lower |
| 内 | Inner | Hair_Inner |
| 外 | Outer | Hair_Outer |
| 前 | Front | Hair_Front |
| 后 | Back | Hair_Back |

### 6.4 状态标识

```
[部位]_[子部位]_[状态]

示例:
- Body_Shirt_Static      # 静态
- Hair_Flyaway_Animated  # 动画
- Arm_Left_Holdout       # 遮挡
- Eye_Right_Blink        # 眨眼
```

### 6.5 命名验证脚本

```python
def validate_naming(roto_node):
    """验证形状命名规范"""
    valid_prefixes = [
        "Head_", "Hair_", "Face_", "Eye_", "Mouth_",
        "Body_", "Arm_", "Hand_", "Leg_", "Foot_", "Prop_"
    ]

    issues = []
    for shape in roto_node.objects:
        name = shape.name
        valid = False
        for prefix in valid_prefixes:
            if name.startswith(prefix):
                valid = True
                break

        if not valid:
            issues.append({
                "shape": name,
                "issue": "命名前缀不规范",
                "suggestion": f"应使用以下前缀之一: {valid_prefixes}"
            })

    if issues:
        print(f"[VALIDATE] 发现 {len(issues)} 个命名问题:")
        for issue in issues:
            print(f"  - {issue['shape']}: {issue['issue']}")
    else:
        print("[VALIDATE] 命名规范验证通过")

    return issues
```

---

## 七、代码示例

### 7.1 完整多形状管理

```python
from fx import *

def create_full_character_pipeline(source_path, output_path, frame_rate=24.0):
    """创建完整的多形状角色管线"""
    proj = activeProject() or Project()
    activate(proj)
    session = activeSession() or Session()
    session.label = "Multi_Shape_Character"
    activate(session)
    proj.addItem(session)

    src = Node("SourceNode")
    src.property("mediaPath").setValue(source_path.replace("\\", "/"), 0)
    src.property("frameRate").setValue(frame_rate, 0)
    session.addNode(src)

    roto = Node("RotoNode")
    roto.label = "Character_Roto"
    roto.property("alpha.blur").setValue(0.4, 0)
    roto.property("antialias").setValue(1.0, 0)
    session.addNode(roto)

    # === 创建层级结构 ===
    char_layer = roto.createLayer("Character")

    # 头部组
    head_group = char_layer.createLayer("Group_Head")
    head_skull = roto.createObject("X-Spline", parent=head_group)
    head_skull.name = "Head_Skull"
    head_skull.property("feather").setValue(1.5, 0)

    hair_main = roto.createObject("X-Spline", parent=head_group)
    hair_main.name = "Hair_Main"
    hair_main.property("feather").setValue(4.0, 0)

    eye_left = roto.createObject("Bezier", parent=head_group)
    eye_left.name = "Eye_Left"
    eye_left.property("feather").setValue(0.0, 0)

    eye_right = roto.createObject("Bezier", parent=head_group)
    eye_right.name = "Eye_Right"
    eye_right.property("feather").setValue(0.0, 0)

    # 躯干组
    body_group = char_layer.createLayer("Group_Body")
    body_shirt = roto.createObject("X-Spline", parent=body_group)
    body_shirt.name = "Body_Shirt"
    body_shirt.property("feather").setValue(2.0, 0)

    # 四肢组
    limbs_group = char_layer.createLayer("Group_Limbs")
    arm_left = roto.createObject("X-Spline", parent=limbs_group)
    arm_left.name = "Arm_Left"
    arm_left.property("feather").setValue(2.0, 0)

    arm_right = roto.createObject("X-Spline", parent=limbs_group)
    arm_right.name = "Arm_Right"
    arm_right.property("feather").setValue(2.0, 0)

    # 道具组
    props_group = char_layer.createLayer("Group_Props")
    glasses = roto.createObject("Bezier", parent=props_group)
    glasses.name = "Prop_Glasses"
    glasses.property("feather").setValue(0.0, 0)

    # === 设置渲染顺序 ===
    render_order = [
        "Body_Shirt", "Arm_Left", "Arm_Right",
        "Head_Skull", "Hair_Main",
        "Eye_Left", "Eye_Right",
        "Prop_Glasses"
    ]
    for i, name in enumerate(render_order):
        shape = find_shape_by_name(roto, name)
        if shape:
            shape.property("priority").setValue(i, 0)

    # === 输出 ===
    out_node = Node("OutputNode")
    out_node.property("path").setValue(output_path.replace("\\", "/"), 0)
    out_node.property("format").setValue("exr", 0)
    session.addNode(out_node)

    src.outputs[0].connect(roto.inputs[1])
    roto.outputs[0].connect(out_node.inputs[0])

    # === 统计 ===
    shape_count = len(roto.objects)
    layer_count = len(roto.layers)
    print(f"[SILHOUETTE] 多形状角色管线已创建")
    print(f"  形状数: {shape_count}")
    print(f"  层数: {layer_count}")
    return roto
```

### 7.2 形状查找与批量操作

```python
def batch_operations(roto_node):
    """批量操作示例"""
    # 批量设置所有硬边形状
    hard_edge_names = ["Eye_Left", "Eye_Right", "Prop_Glasses"]
    for name in hard_edge_names:
        shape = find_shape_by_name(roto_node, name)
        if shape:
            shape.property("feather").setValue(0.0, 0)
            shape.property("blur").setValue(0.0, 0)

    # 批量设置所有柔边形状
    soft_edge_names = ["Head_Skull", "Hair_Main", "Body_Shirt", "Arm_Left", "Arm_Right"]
    for name in soft_edge_names:
        shape = find_shape_by_name(roto_node, name)
        if shape:
            shape.property("feather").setValue(2.0, 0)
            shape.property("featherFalloff").setValue(0.5, 0)

    # 批量启用运动模糊（仅快速运动形状）
    motion_blur_names = ["Hair_Main", "Arm_Left", "Arm_Right"]
    for name in motion_blur_names:
        shape = find_shape_by_name(roto_node, name)
        if shape:
            shape.property("motionBlur").setValue(true, 0)
            shape.property("motionBlur.shutter").setValue(0.5, 0)

    print("[BATCH] 批量操作完成")
```

### 7.3 形状导出报告

```python
def export_shape_report(roto_node):
    """导出形状结构报告"""
    report = {
        "total_shapes": 0,
        "total_layers": 0,
        "hierarchy": []
    }

    def traverse_layer(layer, depth=0):
        layer_info = {
            "name": layer.name,
            "depth": depth,
            "type": "layer",
            "children": []
        }

        for child in layer.children:
            if hasattr(child, 'points'):  # 是形状
                shape_info = {
                    "name": child.name,
                    "depth": depth + 1,
                    "type": child.type,
                    "feather": child.property("feather").getValue(0),
                    "point_count": len(child.points)
                }
                layer_info["children"].append(shape_info)
                report["total_shapes"] += 1
            else:  # 是子层
                sub_layer_info = traverse_layer(child, depth + 1)
                layer_info["children"].append(sub_layer_info)

        report["total_layers"] += 1
        return layer_info

    for layer in roto_node.layers:
        report["hierarchy"].append(traverse_layer(layer))

    print("=== 形状结构报告 ===")
    print(f"总形状数: {report['total_shapes']}")
    print(f"总层数: {report['total_layers']}")

    return report
```

---

## 八、常见问题与最佳实践

### 8.1 问题诊断

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 形状找不到 | 命名不规范 | 使用统一命名规范 |
| 渲染顺序错误 | priority 未设 | 按层级表设置 priority |
| 父子变换异常 | 父级错误 | 检查 parent 属性 |
| 性能卡顿 | 单 Node 形状过多 | 拆分多 RotoNode |
| 形状"消失" | 父层不可见 | 检查父层 visible |
| 子形状不跟随 | 父子关系未建立 | 设置 parent 属性 |

### 8.2 最佳实践

1. **结构化命名**：使用 `部位_子部位_方向` 格式。
2. **分层管理**：按部位创建 Layer，形状归入对应 Layer。
3. **渲染顺序明确**：每个形状设置 priority 值。
4. **父子关系合理**：道具跟随身体，手指跟随手。
5. **批量操作**：同类型形状批量设置参数。
6. **定期清理**：删除不可见的废弃形状。
7. **导出报告**：复杂场景生成结构报告，便于团队协作。

### 8.3 性能建议

- 单 RotoNode 形状数 ≤ 30，超过拆分多 Node。
- 嵌套层级 ≤ 5 层，过深影响性能。
- 隐藏不编辑的 Layer，减少渲染负担。
- 使用 `session.property("proxy").setValue(true, 0)` 代理预览。
- 锁定已完成形状，防止误操作。

### 8.4 质量检查清单

- [ ] 所有形状命名规范
- [ ] 层级结构清晰
- [ ] 父子关系正确
- [ ] 渲染顺序正确
- [ ] 无废弃形状
- [ ] 单 Node 形状数合理
- [ ] 批量参数已应用
- [ ] 结构报告已导出

---

## 相关文档

- [Silhouette 形状层与关键帧动画](Silhouette%20形状层与关键帧动画.md)
- [Silhouette 遮罩混合与布尔运算](Silhouette%20遮罩混合与布尔运算.md)
- [Silhouette 硬边与柔边遮罩技巧](Silhouette%20硬边与柔边遮罩技巧.md)
- [Silhouette Roto工作流最佳实践](Silhouette%20Roto工作流最佳实践.md)
