# Silhouette 形状层与关键帧动画

> 分类: Roto抠像专题
> 更新日期: 2026-07-11
> 概述: 系统讲解 Shape 对象结构、关键帧生命周期、插值模式、动画曲线编辑与循环动画，覆盖 Roto 抠像的全部动画需求。

## 目录
1. [Shape 对象详解](#一shape-对象详解)
2. [关键帧创建](#二关键帧创建)
3. [关键帧编辑与删除](#三关键帧编辑与删除)
4. [插值模式](#四插值模式)
5. [动画曲线编辑](#五动画曲线编辑)
6. [循环动画](#六循环动画)
7. [代码示例](#七代码示例)
8. [常见问题](#八常见问题)

---

## 一、Shape 对象详解

### 1.1 Shape 层级结构

```
RotoNode
├── Layer（层，可嵌套）
│   ├── Shape_1（X-Spline / Bezier / Rectangle / Ellipse）
│   │   ├── points[]（控制点列表）
│   │   ├── properties（feather / blur / opacity...）
│   │   └── keyframes（每属性的动画关键帧）
│   ├── Shape_2
│   └── Layer_Child（子层）
└── Layer_2
```

### 1.2 Shape 核心属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `name` | str | 形状名称 |
| `type` | str | "X-Spline" / "Bezier" / "Rectangle" / "Ellipse" |
| `visible` | bool | 是否可见 |
| `locked` | bool | 是否锁定 |
| `selected` | bool | 是否选中 |
| `color` | tuple | (r, g, b) 显示色 |
| `opacity` | float | 0.0~1.0 |
| `inverted` | bool | 反转遮罩 |
| `closed` | bool | 是否闭合 |
| `points` | list | 控制点数组 |
| `feather` | float | 整体羽化 |
| `blur` | float | 边缘模糊 |
| `blendMode` | str | 混合模式（见布尔运算章节） |
| `parent` | Layer | 父层引用 |
| `motionBlur` | bool | 形状级运动模糊 |

### 1.3 形状类型一览

```python
from fx import *

roto = Node("RotoNode")
session.addNode(roto)

# X-Spline - 有机曲线
xspline = roto.createObject("X-Spline")

# Bézier - 精确硬边
bezier = roto.createObject("Bezier")

# 矩形
rect = roto.createObject("Rectangle")
rect.property("width").setValue(400, 0)
rect.property("height").setValue(300, 0)
rect.property("center").setValue((960, 540), 0)

# 椭圆
ellipse = roto.createObject("Ellipse")
ellipse.property("radius").setValue((200, 150), 0)
```

### 1.4 Layer（层）对象

```python
layer = roto.createLayer("Character_Layer")
layer.addChild(shape_body)
layer.addChild(shape_arm)

# 层级嵌套
sub_layer = layer.createLayer("Head_SubLayer")
```

层的属性：
- `opacity` - 整层不透明度
- `visible` - 整层可见性
- `blendMode` - 整层混合模式
- `transform` - 整层变换（位置/旋转/缩放）

---

## 二、关键帧创建

### 2.1 关键帧原理

Silhouette 的所有可动画属性都基于"时间-值"对：

```
Property.setValue(value, frame)
├── 若该帧无关键帧 → 创建新关键帧
├── 若该帧已有关键帧 → 覆盖
└── 若 value 与相邻关键帧相同 → 仍创建（显式关键帧）
```

### 2.2 控制点关键帧

```python
from fx import *

# 在第 0 帧创建初始形状
shape.addPoint((100, 200), frame=0)
shape.addPoint((300, 200), frame=0)
shape.addPoint((200, 400), frame=0)

# 在第 24 帧更新位置（自动创建关键帧）
shape.points[0].position = (150, 180)  # 在 frame=24 时
shape.points[1].position = (350, 220)
shape.points[2].position = (250, 420)
```

### 2.3 属性关键帧

```python
# 在第 0 帧设置羽化=2.0
shape.property("feather").setValue(2.0, 0)

# 在第 12 帧羽化=5.0（如毛发飘散时增大羽化）
shape.property("feather").setValue(5.0, 12)

# 在第 24 帧回到 2.0
shape.property("feather").setValue(2.0, 24)

# 节点级属性也可关键帧
roto.property("alpha.blur").setValue(0.3, 0)
roto.property("alpha.blur").setValue(0.8, 12)
roto.property("alpha.blur").setValue(0.3, 24)
```

### 2.4 关键帧创建策略

| 场景 | 策略 |
|------|------|
| 缓慢运动 | 每 12-24 帧一个关键帧 |
| 正常运动 | 每 4-8 帧一个关键帧 |
| 快速运动 | 每 1-2 帧一个关键帧（接近逐帧） |
| 形状突变 | 在突变前后各加一帧，使用阶跃插值 |
| 循环动画 | 起始与结束帧一致，中间均匀分布 |

---

## 三、关键帧编辑与删除

### 3.1 关键帧查询

```python
prop = shape.property("feather")

# 关键帧数量
print(f"关键帧数: {prop.numKeys}")

# 遍历所有关键帧
for i in range(prop.numKeys):
    time = prop.keyTime(i)
    value = prop.keyValue(i)
    print(f"  Key {i}: frame={time}, value={value}")
```

### 3.2 关键帧编辑

```python
# 修改第 3 个关键帧的值
prop.setKeyValue(2, 8.0)  # 索引从 0 开始

# 移动关键帧时间
prop.moveKey(2, 18)  # 移动到第 18 帧

# 修改插值类型
prop.setKeyInterpolation(2, "bezier")  # linear / bezier / step
```

### 3.3 关键帧删除

```python
# 删除指定索引的关键帧
prop.removeKey(2)

# 删除指定时间的关键帧
prop.removeKeyAtTime(12)

# 清空所有关键帧
prop.clearKeys()

# 删除指定帧的所有控制点关键帧
def clear_all_points_at_frame(shape, frame):
    for point in shape.points:
        if point.hasKeyAtTime(frame):
            point.removeKeyAtTime(frame)
```

### 3.4 关键帧拷贝与粘贴

```python
# 复制第 12 帧的形状到第 24 帧
def copy_shape_frame(shape, src_frame, dst_frame):
    for point in shape.points:
        pos = point.getValue(src_frame)  # 获取源帧位置
        point.setValue(pos, dst_frame)  # 写入目标帧

    # 同时复制属性
    for prop_name in ["feather", "blur", "opacity"]:
        prop = shape.property(prop_name)
        if prop.numKeys > 0:
            val = prop.getValue(src_frame)
            prop.setValue(val, dst_frame)
```

---

## 四、插值模式

### 4.1 三种插值模式

| 模式 | 标识 | 行为 | 适用场景 |
|------|------|------|---------|
| **线性** | `"linear"` | 直线连接两关键帧 | 机械运动、匀速 |
| **贝塞尔** | `"bezier"` | 平滑曲线（默认） | 生物运动、自然过渡 |
| **阶跃** | `"step"` | 保持上一帧值直到下一帧 | 突变、开关切换 |

### 4.2 设置插值

```python
prop = shape.property("feather")

# 设置第 2 个关键帧的"出"插值为线性
prop.setKeyInterpolationOut(2, "linear")

# 设置第 2 个关键帧的"入"插值为阶跃
prop.setKeyInterpolationIn(2, "step")

# 默认全局插值模式
roto.property("defaultInterpolation").setValue("bezier", 0)
```

### 4.3 插值示意图

```
线性:        贝塞尔:        阶跃:
  10 ─╮       10 ─╮           10 ─┐
      │           ╲              │
      │            ╲             │
   5  │  ╭─5       │ ╭─5      5  │   ┌─5
      │ /            ╰            │   │
      │/             /            │___│
      └────────      └──────      └──────
      0   12  24     0   12  24    0   12  24
```

### 4.4 控制点插值特殊处理

控制点的位置插值默认是**线性插值**，因为贝塞尔插值会导致曲线"鼓包"。若要平滑：

```python
# 启用控制点的样条插值
shape.property("pointInterpolation").setValue("smooth", 0)

# 或在 UI 中：选中点 → Animation → Smooth Interpolation
```

---

## 五、动画曲线编辑

### 5.1 Curve Editor（曲线编辑器）

Silhouette 内置 Animation 面板提供曲线编辑：
- **横轴**：时间（帧）
- **纵轴**：属性值
- **切线手柄**：调节贝塞尔过渡速率

### 5.2 曲线操作 API

```python
prop = shape.property("feather")

# 获取关键帧的切线
key_idx = 1
in_tangent = prop.keyInTangent(key_idx)   # (time, value) 偏移
out_tangent = prop.keyOutTangent(key_idx)

# 设置切线（控制曲线弯曲）
prop.setKeyTangents(
    key_idx,
    inTangent=(-3, 0),    # 入切线水平（缓入）
    outTangent=(3, 2)     # 出切线向上（缓出）
)

# 自动平滑切线
prop.autoTangent(key_idx)
```

### 5.3 常见曲线形态

```
缓入缓出（生物运动）:    缓入（减速到位）:    缓出（启动加速）:
   ╱                       ╱                    __╱
  ╱                       ╱                    ╱
 ╱                       ╱                    ╱
─╱                      ╱                    ╱
```

```python
# 预设：缓入缓出
def apply_ease_in_out(prop, key_idx):
    prop.setKeyInterpolation(key_idx, "bezier")
    prop.setKeyTangents(
        key_idx,
        inTangent=(-2, 0),
        outTangent=(2, 0)
    )

# 预设：弹性（过冲）
def apply_overshoot(prop, key_idx, amount=0.15):
    val = prop.keyValue(key_idx)
    prop.setKeyTangents(
        key_idx,
        inTangent=(-2, val * amount),
        outTangent=(2, -val * amount * 0.5)
    )
```

### 5.4 多属性同步动画

```python
# 同步动画 feather 和 alpha.blur
def sync_fade_in(shape, start_frame, end_frame, max_feather=3.0):
    """从透明到不透明，羽化逐渐收紧"""
    duration = end_frame - start_frame
    for i in range(duration + 1):
        frame = start_frame + i
        t = i / duration  # 0.0 → 1.0

        # 使用平滑函数
        smooth_t = t * t * (3 - 2 * t)  # smoothstep

        shape.property("opacity").setValue(smooth_t, frame)
        shape.property("feather").setValue(max_feather * (1 - smooth_t), frame)
```

---

## 六、循环动画

### 6.1 循环原理

循环动画要求起始帧（frame=0）与结束帧（frame=N）的关键帧值完全一致，中间帧通过插值自然过渡。

### 6.2 创建循环动画

```python
import math

def create_breathing_animation(shape, duration=60, amplitude=5.0):
    """创建呼吸式缩放循环动画（60 帧一循环）"""
    for i in range(duration + 1):
        # 正弦波，0 → 2π
        phase = (i / duration) * 2 * math.pi
        scale = 1.0 + amplitude * math.sin(phase) / 100

        # 应用到所有控制点（围绕中心缩放）
        center = (960, 540)
        for point in shape.points:
            base_pos = point.getValue(0)  # 初始位置
            new_pos = (
                center[0] + (base_pos[0] - center[0]) * scale,
                center[1] + (base_pos[1] - center[1]) * scale
            )
            point.setValue(new_pos, i)

    # 确保首尾一致
    last_frame = shape.points[0].getValue(duration)
    first_frame = shape.points[0].getValue(0)
    print(f"[LOOP] 首尾差异: {abs(last_frame[0] - first_frame[0])}")
```

### 6.3 循环扩展

```python
def extend_loop(shape, loop_duration, total_frames):
    """将循环动画扩展到总时长"""
    num_loops = total_frames // loop_duration

    for loop_i in range(1, num_loops + 1):
        offset = loop_i * loop_duration
        for i in range(loop_duration):
            src_frame = i
            dst_frame = offset + i
            if dst_frame > total_frames:
                break

            for point in shape.points:
                pos = point.getValue(src_frame)
                point.setValue(pos, dst_frame)
```

### 6.4 循环类型

| 类型 | 公式 | 应用 |
|------|------|------|
| **Ping-Pong（往返）** | `i ≤ N ? i : 2N - i` | 摆动、呼吸 |
| **Repeat（重复）** | `i mod N` | 走路、跑步 |
| **Offset（偏移）** | `value(i) + offset * floor(i/N)` | 持续移动 |

---

## 七、代码示例

### 7.1 完整动画形状创建

```python
from fx import *

def create_animated_shape():
    proj = activeProject() or Project()
    activate(proj)
    session = activeSession() or Session()
    session.label = "Animated_Shape"
    activate(session)
    proj.addItem(session)

    src = Node("SourceNode")
    src.property("mediaPath").setValue("D:/footage/walk.mov", 0)
    src.property("frameRate").setValue(24.0, 0)
    session.addNode(src)

    roto = Node("RotoNode")
    roto.label = "Body_Roto"
    roto.property("alpha.blur").setValue(0.5, 0)
    session.addNode(roto)

    # 创建身体形状
    body = roto.createObject("X-Spline")
    body.name = "Body"
    body.closed = true

    # 第 0 帧：站立姿势
    body_points_frame_0 = [
        (800, 400), (1100, 400),
        (1100, 800), (800, 800)
    ]
    for pt in body_points_frame_0:
        body.addPoint(pt, frame=0)

    # 第 12 帧：行走中（腿部张开）
    body_points_frame_12 = [
        (810, 400), (1090, 400),
        (1150, 800), (750, 800)
    ]
    for i, pt in enumerate(body_points_frame_12):
        body.points[i].position = pt
        body.points[i].setKeyframe(12)  # 显式创建关键帧

    # 第 24 帧：回到站立
    for i, pt in enumerate(body_points_frame_0):
        body.points[i].position = pt
        body.points[i].setKeyframe(24)

    # 设置所有关键帧为贝塞尔插值
    for point in body.points:
        for key_idx in range(point.numKeys):
            point.setKeyInterpolation(key_idx, "bezier")

    body.property("feather").setValue(2.0, 0)
    body.property("feather").setValue(3.0, 12)
    body.property("feather").setValue(2.0, 24)

    src.outputs[0].connect(roto.inputs[1])

    print("[SILHOUETTE] 动画形状创建完成")
    print(f"[SILHOUETTE] 关键帧数: {body.points[0].numKeys}")
    return roto, body
```

### 7.2 关键帧清理脚本

```python
def cleanup_redundant_keyframes(shape, threshold=0.5):
    """清理冗余关键帧（值变化小于阈值的）"""
    removed = 0
    for point in shape.points:
        if point.numKeys < 3:
            continue

        keys_to_remove = []
        for i in range(1, point.numKeys - 1):
            prev_val = point.keyValue(i - 1)
            curr_val = point.keyValue(i)
            next_val = point.keyValue(i + 1)

            # 计算与线性插值的偏差
            expected_x = (prev_val[0] + next_val[0]) / 2
            expected_y = (prev_val[1] + next_val[1]) / 2
            deviation = abs(curr_val[0] - expected_x) + abs(curr_val[1] - expected_y)

            if deviation < threshold:
                keys_to_remove.append(i)

        # 从后往前删除（避免索引偏移）
        for idx in reversed(keys_to_remove):
            point.removeKey(idx)
            removed += 1

    print(f"[CLEANUP] 删除 {removed} 个冗余关键帧")
    return removed
```

### 7.3 关键帧时间偏移

```python
def offset_animation(shape, frame_offset):
    """将整个动画向后偏移若干帧"""
    for point in shape.points:
        # 收集所有关键帧
        keys = []
        for i in range(point.numKeys):
            keys.append((point.keyTime(i), point.keyValue(i)))

        # 清空原关键帧
        point.clearKeys()

        # 重新写入偏移后的关键帧
        for time, value in keys:
            point.setValue(value, time + frame_offset)

    # 同样处理属性
    for prop_name in ["feather", "blur", "opacity"]:
        prop = shape.property(prop_name)
        if prop.numKeys > 0:
            keys = []
            for i in range(prop.numKeys):
                keys.append((prop.keyTime(i), prop.keyValue(i)))
            prop.clearKeys()
            for time, value in keys:
                prop.setValue(value, time + frame_offset)
```

---

## 八、常见问题

### 8.1 问题诊断

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 形状在中间帧"鼓包" | 控制点贝塞尔插值 | 改用线性插值或减少关键帧 |
| 动画"抖动" | 关键帧过多 | 启用 `cleanup_redundant_keyframes` |
| 循环接缝明显 | 首尾值不一致 | 强制首尾帧值相同 |
| 关键帧丢失 | 误删控制点 | 撤销 Ctrl+Z，或从备份恢复 |
| 插值不正确 | 混合插值模式 | 统一为 `bezier` 或 `linear` |
| 曲线过冲 | 切线过长 | 缩短切线手柄或用 `autoTangent` |

### 8.2 动画质量检查清单

- [ ] 首尾帧一致（循环动画）
- [ ] 关键帧数量合理（避免过密）
- [ ] 插值模式统一
- [ ] 切线方向正确（避免反向运动）
- [ ] 形状未自相交
- [ ] 边缘抖动 < 1px
- [ ] 羽化随运动合理变化

### 8.3 性能建议

- 单个形状关键帧数建议 ≤ 100
- 复杂动画拆分多形状，分别管理
- 启用 `session.property("motionBlur").setValue(true, 0)` 减少逐帧需求
- 关键帧过多的形状，使用 `simplify_keys()` 抽稀

---

## 相关文档

- [Silhouette X-Spline与Bézier曲线详解](Silhouette%20X-Spline与Bézier曲线详解.md)
- [Silhouette 逐帧与插值策略](Silhouette%20逐帧与插值策略.md)
- [Silhouette 边缘优化与运动模糊](Silhouette%20边缘优化与运动模糊.md)
- [Silhouette Roto遮罩完全指南](Silhouette%20Roto遮罩完全指南.md)
