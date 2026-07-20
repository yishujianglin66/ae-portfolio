# Silhouette 属性类型完全手册

> 分类: API与参数手册
> 更新日期: 2026-07-11
> 概述: 详细说明 Property 类的所有操作，包括值读写、关键帧动画、插值类型、表达式与动画曲线编辑

## 目录

- [一、Property 类概述](#一property-类概述)
- [二、基础属性操作](#二基础属性操作)
- [三、属性类型详解](#三属性类型详解)
- [四、关键帧动画系统](#四关键帧动画系统)
- [五、插值类型](#五插值类型)
- [六、表达式系统](#六表达式系统)
- [七、动画曲线编辑](#七动画曲线编辑)
- [八、高级操作](#八高级操作)
- [九、最佳实践](#九最佳实践)

---

## 一、Property 类概述

Property 是 Silhouette 节点参数的核心载体，所有节点参数都通过 Property 对象进行读写和动画控制。

### 核心关系

```
Node
 ├── property("name") → Property
 │     ├── value (当前值)
 │     ├── keys (关键帧列表)
 │     ├── expression (表达式)
 │     └── interpolation (插值类型)
```

### 创建属性

```python
from fx import *

# 创建属性
prop = Property("myValue", "float")
prop.setValue(0.5, 0)

# 添加到节点
node.addProperty(prop)
```

---

## 二、基础属性操作

### 2.1 值读写方法

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `setValue(value, frame)` | value: Any, frame: int | None | 在指定帧设置值 |
| `getValue(frame)` | frame: int | Any | 获取指定帧的值（含动画插值） |
| `value` | 无 | Any | 当前帧值（只读属性） |
| `defaultValue` | 无 | Any | 默认值 |
| `reset()` | 无 | None | 重置为默认值 |

### 2.2 基本读写示例

```python
from fx import *

node = Node("RotoNode")
session.addNode(node)

prop = node.property("alpha.blur")

# 设置值
prop.setValue(0.5, 0)       # 在第0帧设置为0.5
prop.setValue(1.2, 100)     # 在第100帧设置为1.2

# 读取值
current = prop.value         # 当前帧值
val_at_50 = prop.getValue(50)  # 第50帧的插值
print(f"当前值: {current}, 第50帧: {val_at_50}")

# 重置
prop.reset()
```

### 2.3 动画值与静态值

```python
prop = node.property("alpha.blur")

# 检查是否有动画
is_animated = prop.numKeys > 0
print(f"是否动画: {is_animated}")

# getValue 自动处理插值
# 如果有关键帧，返回插值后的值
# 如果无关键帧，返回静态值
static_val = prop.getValue(999)
```

---

## 三、属性类型详解

### 3.1 基础类型

| 类型字符串 | Python 类型 | 示例值 | 说明 |
|-----------|-------------|--------|------|
| "string" | str | "alpha" | 字符串 |
| "bool" | bool | True/False | 布尔值 |
| "int" | int | 25 | 整数 |
| "float" | float | 0.5 | 浮点数 |
| "color" | list[float, float, float] | [1.0, 0.5, 0.0] | RGB 颜色 |
| "point" | list[float, float] | [1920, 1080] | 2D 坐标点 |
| "vector" | list[float, float, float] | [0, 0, 1] | 3D 向量 |
| "matrix" | list[16 floats] | 4×4 矩阵 | 变换矩阵 |
| "enum" | str | "medium" | 枚举值 |

### 3.2 各类型操作示例

```python
from fx import *

# string
node.property("label").setValue("My_Node", 0)

# bool
node.property("enabled").setValue(True, 0)

# int
node.property("frameStart").setValue(10, 0)

# float
node.property("opacity").setValue(0.85, 0)

# color
node.property("fill.color").setValue([1.0, 0.5, 0.0], 0)

# point
node.property("translate").setValue([100.5, 200.3], 0)

# vector
node.property("direction").setValue([0.0, 0.0, 1.0], 0)

# enum
node.property("mode").setValue("over", 0)
```

### 3.3 枚举值查询

```python
prop = node.property("matte.mode")
# 获取所有可选枚举值
enums = prop.enums
# 返回: ["alpha", "luma", "replace"]
print(f"可选值: {enums}")
```

---

## 四、关键帧动画系统

### 4.1 关键帧操作方法

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `numKeys` | 无 | int | 关键帧数量 |
| `keyValue(keyIndex)` | keyIndex: int | Any | 获取关键帧值 |
| `keyTime(keyIndex)` | keyIndex: int | float | 获取关键帧时间 |
| `keyIndex(frame)` | frame: int | int | 获取指定帧附近的关键帧索引 |
| `addKey(frame, value)` | frame: int, value: Any | None | 添加关键帧 |
| `removeKey(keyIndex)` | keyIndex: int | None | 删除关键帧 |
| `removeAllKeys()` | 无 | None | 删除所有关键帧 |
| `isAnimated` | 无 | bool | 是否有动画 |
| `hasKey(frame)` | frame: int | bool | 指定帧是否有关键帧 |

### 4.2 创建动画

```python
from fx import *

node = Node("TransformNode")
session.addNode(node)
prop = node.property("translate")

# 方法一：通过 setValue 自动生成关键帧
prop.setValue([0, 0], 0)
prop.setValue([100, 50], 30)
prop.setValue([200, 100], 60)
prop.setValue([150, 80], 90)
prop.setValue([0, 0], 120)

# 方法二：显式添加关键帧
prop.addKey(0, [0, 0])
prop.addKey(60, [200, 100])
prop.addKey(120, [0, 0])

print(f"关键帧数量: {prop.numKeys}")
```

### 4.3 遍历关键帧

```python
prop = node.property("translate")

for i in range(prop.numKeys):
    time = prop.keyTime(i)
    value = prop.keyValue(i)
    print(f"关键帧 {i}: 帧={time}, 值={value}")
```

### 4.4 修改关键帧

```python
prop = node.property("opacity")

# 删除第2个关键帧
prop.removeKey(1)

# 修改关键帧值（通过重新 setValue）
frame = prop.keyTime(0)
prop.setValue(0.9, frame)

# 清除所有动画
prop.removeAllKeys()
```

### 4.5 关键帧时间查询

```python
prop = node.property("translate")

# 查询第30帧附近的关键帧
idx = prop.keyIndex(30)
if idx >= 0:
    print(f"找到关键帧: 索引={idx}, 时间={prop.keyTime(idx)}")
else:
    print("该帧无关键帧")

# 检查特定帧
if prop.hasKey(60):
    print("第60帧有关键帧")
```

---

## 五、插值类型

### 5.1 插值类型列表

| 类型 | 说明 | 适用场景 |
|------|------|----------|
| linear | 线性插值 | 机械运动、匀速变化 |
| bezier | 贝塞尔曲线 | 平滑动画（默认） |
| step | 阶跃 | 离散变化、开关切换 |
| hold | 保持 | 保持值不变直到下一个关键帧 |
| easeIn | 缓入 | 逐渐加速 |
| easeOut | 缓出 | 逐渐减速 |
| easeInOut | 缓入缓出 | 自然运动 |

### 5.2 设置插值类型

```python
prop = node.property("opacity")

# 设置全局插值类型
prop.interpolation = "bezier"

# 逐关键帧设置
prop.setValue(0.0, 0)
prop.setValue(1.0, 30)

# 设置关键帧的切线
prop.setTangent(0, outTangent=[0.3, 0.0])  # 第0帧的输出切线
prop.setTangent(1, inTangent=[-0.3, 0.0])  # 第1帧的输入切线
```

### 5.3 插值对比示例

```python
from fx import *

def create_interpolation_test(session):
    """对比不同插值类型的效果"""
    interp_types = ["linear", "bezier", "step", "easeIn", "easeOut", "easeInOut"]

    for itype in interp_types:
        node = Node("ColorNode")
        node.label = f"Test_{itype}"
        session.addNode(node)

        prop = node.property("brightness")
        prop.interpolation = itype
        prop.setValue(0.0, 0)
        prop.setValue(1.0, 60)

        # 采样各帧值
        values = [prop.getValue(f) for f in range(0, 61, 10)]
        print(f"{itype}: {values}")
```

---

## 六、表达式系统

### 6.1 表达式概述

Property 支持使用表达式动态计算值，表达式在每帧求值，可引用其他属性。

### 6.2 表达式方法

| 方法/属性 | 参数 | 返回值 | 说明 |
|-----------|------|--------|------|
| `expression` | 无 | str | 当前表达式字符串 |
| `setExpression(expr)` | expr: str | None | 设置表达式 |
| `removeExpression()` | 无 | None | 移除表达式 |
| `hasExpression` | 无 | bool | 是否有表达式 |

### 6.3 表达式语法

```python
prop = node.property("opacity")

# 简单数学表达式
prop.setExpression("0.5 + 0.5 * sin(time * 0.1)")

# 引用其他属性
prop.setExpression("thisNode.property('brightness').value * 2")

# 条件表达式
prop.setExpression("frame > 30 ? 1.0 : 0.0")

# 引用其他节点
prop.setExpression("node('Transform_01').property('translate').value[0] / 100")
```

### 6.4 表达式可用变量

| 变量 | 类型 | 说明 |
|------|------|------|
| `time` | float | 当前时间（秒） |
| `frame` | int | 当前帧号 |
| `thisNode` | Node | 当前属性所属节点 |
| `pi` | float | 圆周率 |
| `thisProperty` | Property | 当前属性 |

### 6.5 表达式可用函数

| 函数 | 说明 | 示例 |
|------|------|------|
| `sin(x)` | 正弦 | `sin(time)` |
| `cos(x)` | 余弦 | `cos(time * 2)` |
| `abs(x)` | 绝对值 | `abs(frame - 30)` |
| `min(a,b)` | 最小值 | `min(1.0, x)` |
| `max(a,b)` | 最大值 | `max(0.0, x)` |
| `clamp(x, min, max)` | 限制范围 | `clamp(x, 0, 1)` |
| `lerp(a, b, t)` | 线性插值 | `lerp(0, 1, 0.5)` |
| `smoothstep(a, b, x)` | 平滑过渡 | `smoothstep(0, 30, frame)` |
| `noise(x)` | 噪声 | `noise(time)` |
| `random()` | 随机数 | `random()` |

### 6.6 表达式示例

```python
from fx import *

# 闪烁效果
node = Node("ColorNode")
session.addNode(node)
node.property("brightness").setExpression(
    "0.5 + 0.3 * sin(time * 5)"
)

# 渐入渐出
node.property("opacity").setExpression(
    "smoothstep(0, 30, frame) * (1 - smoothstep(90, 120, frame))"
)

# 循环动画
node.property("rotate").setExpression(
    "(frame % 60) / 60 * 360"
)
```

---

## 七、动画曲线编辑

### 7.1 切线操作

| 方法 | 参数 | 说明 |
|------|------|------|
| `setTangent(keyIndex, inTangent, outTangent)` | keyIndex: int, inTangent: [x,y], outTangent: [x,y] | 设置关键帧切线 |
| `getTangent(keyIndex)` | keyIndex: int | 获取切线 [in, out] |
| `setAutoTangent(keyIndex, mode)` | keyIndex: int, mode: str | 自动切线模式 |

### 7.2 自动切线模式

| 模式 | 说明 |
|------|------|
| "auto" | 自动平滑 |
| "flat" | 水平切线 |
| "linear" | 线性切线 |
| "smooth" | 平滑过渡 |

### 7.3 曲线编辑示例

```python
from fx import *

prop = node.property("opacity")

# 创建关键帧
prop.setValue(0.0, 0)
prop.setValue(1.0, 30)
prop.setValue(1.0, 90)
prop.setValue(0.0, 120)

# 设置第1个关键帧为缓出
prop.setAutoTangent(0, "flat")

# 设置第2个关键帧为线性
prop.setAutoTangent(1, "linear")

# 手动设置切线
# 切线格式: [x方向, y方向]，x通常为帧比例
prop.setTangent(0, None, [0.2, 0.8])  # 输出切线
prop.setTangent(1, [-0.2, 0.8], [0.2, 0.0])  # 输入和输出
```

### 7.4 循环动画

```python
prop = node.property("rotate")

# 创建基础关键帧
prop.setValue(0, 0)
prop.setValue(360, 60)

# 设置循环
prop.preExtrapolation = "cycle"    # 前循环
prop.postExtrapolation = "cycle"   # 后循环

# 外推类型
# "cycle" - 循环
# "oscillate" - 来回
# "linear" - 线性延伸
# "constant" - 保持
```

---

## 八、高级操作

### 8.1 属性查询与遍历

```python
node = Node("RotoNode")

# 获取所有属性名
prop_names = node.properties
print(f"属性列表: {prop_names}")

# 遍历所有属性
for name in node.properties:
    prop = node.property(name)
    val = prop.value
    animated = prop.isAnimated
    print(f"  {name}: {val} (动画: {animated})")
```

### 8.2 属性连接

```python
# 将属性A的值连接到属性B（属性B跟随A变化）
prop_a = node_a.property("opacity")
prop_b = node_b.property("opacity")
prop_b.connect(prop_a)
```

### 8.3 批量设置属性

```python
def setup_node(node, props_dict, frame=0):
    """批量设置节点属性"""
    for name, value in props_dict.items():
        if name in node.properties:
            node.property(name).setValue(value, frame)
        else:
            print(f"警告: 属性 {name} 不存在")

# 使用示例
setup_node(roto, {
    "alpha.blur": 0.5,
    "antialias": 1.0,
    "fill": True,
    "motionBlur": True,
    "motionBlur.shutter": 0.7,
})
```

### 8.4 属性状态保存与恢复

```python
def save_properties(node):
    """保存节点所有属性状态"""
    state = {}
    for name in node.properties:
        prop = node.property(name)
        state[name] = {
            "value": prop.value,
            "animated": prop.isAnimated,
            "keys": []
        }
        if prop.isAnimated:
            for i in range(prop.numKeys):
                state[name]["keys"].append({
                    "frame": prop.keyTime(i),
                    "value": prop.keyValue(i)
                })
    return state

def restore_properties(node, state):
    """恢复节点属性状态"""
    for name, data in state.items():
        if name in node.properties:
            prop = node.property(name)
            prop.removeAllKeys()
            if data["animated"]:
                for key in data["keys"]:
                    prop.setValue(key["value"], key["frame"])
            else:
                prop.setValue(data["value"], 0)
```

---

## 九、最佳实践

### 9.1 动画性能建议

- 避免过多关键帧，合理使用插值类型
- 表达式比关键帧更灵活但可能更慢，复杂逻辑优先用关键帧
- `getValue()` 每次调用都会计算插值，循环中注意缓存

### 9.2 属性访问安全检查

```python
def safe_set_property(node, name, value, frame=0):
    """安全的属性设置"""
    if name in node.properties:
        node.property(name).setValue(value, frame)
        return True
    else:
        print(f"[WARNING] 属性 '{name}' 不存在于节点 {node.label}")
        return False
```

### 9.3 动画模板

```python
def apply_fade_in(node, prop_name, start_frame, duration):
    """应用淡入动画"""
    prop = node.property(prop_name)
    prop.setValue(0.0, start_frame)
    prop.setValue(1.0, start_frame + duration)
    prop.setAutoTangent(0, "flat")
    prop.setAutoTangent(1, "flat")

def apply_fade_out(node, prop_name, start_frame, duration):
    """应用淡出动画"""
    prop = node.property(prop_name)
    prop.setValue(1.0, start_frame)
    prop.setValue(0.0, start_frame + duration)
    prop.setAutoTangent(0, "flat")
    prop.setAutoTangent(1, "flat")

# 使用
apply_fade_in(roto, "alpha.opacity", 0, 15)
apply_fade_out(roto, "alpha.opacity", 100, 15)
```

### 9.4 完整动画示例

```python
from fx import *

# 创建带动画的变换节点
transform = Node("TransformNode")
transform.label = "Animated_Move"
session.addNode(transform)

translate = transform.property("translate")
rotate = transform.property("rotate")
scale = transform.property("scale")

# 平移动画（贝塞尔曲线插值）
translate.interpolation = "bezier"
translate.setValue([0, 0], 0)
translate.setValue([500, 100], 30)
translate.setValue([500, 400], 60)
translate.setValue([0, 500], 90)
translate.setValue([0, 0], 120)

# 旋转动画（线性）
rotate.interpolation = "linear"
for f in range(0, 121, 20):
    rotate.setValue(f * 3, f)

# 缩放动画（缓入缓出）
scale.interpolation = "easeInOut"
scale.setValue([1.0, 1.0], 0)
scale.setValue([1.5, 1.5], 60)
scale.setValue([1.0, 1.0], 120)

print(f"平移关键帧: {translate.numKeys}")
print(f"旋转关键帧: {rotate.numKeys}")
print(f"缩放关键帧: {scale.numKeys}")
```
