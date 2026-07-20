# Silhouette 对象模型与继承体系

> 分类: API与参数手册
> 更新日期: 2026-07-11
> 概述: 详细说明 fx 模块的对象继承关系，包括 Object 基类、Node 体系、Property 体系、Session、Project、Shape 等

## 目录

- [一、对象模型总览](#一对象模型总览)
- [二、Object 基类](#二object-基类)
- [三、Node 继承体系](#三node-继承体系)
- [四、Property 继承体系](#四property-继承体系)
- [五、Project 与 Session](#五project-与-session)
- [六、Shape 与 Point](#六shape-与-point)
- [七、Port 端口对象](#七port-端口对象)
- [八、Tracker 与 Stroke](#八tracker-与-stroke)
- [九、Clip 与媒体对象](#九clip-与媒体对象)
- [十、对象生命周期](#十对象生命周期)
- [十一、最佳实践](#十一最佳实践)

---

## 一、对象模型总览

Silhouette 的 fx 模块采用分层继承体系，所有对象最终继承自 `Object` 基类。

### 继承体系图

```
Object
├── Project
├── Session
├── Node
│   ├── SourceNode
│   ├── RotoNode
│   ├── TrackerNode
│   ├── PaintNode
│   ├── OutputNode
│   ├── CompositeNode
│   ├── ColorNode
│   ├── FilterNode
│   ├── MatteNode
│   └── TransformNode
├── Property
│   ├── FloatProperty
│   ├── IntProperty
│   ├── BoolProperty
│   ├── StringProperty
│   ├── ColorProperty
│   ├── PointProperty
│   ├── VectorProperty
│   ├── MatrixProperty
│   └── EnumProperty
├── Shape
│   ├── XSpline
│   ├── Bezier
│   ├── Circle
│   ├── Rectangle
│   └── Freehand
├── Point
├── Port
├── Tracker
├── Stroke
└── Clip
```

### 核心对象关系

```
Project
├── Session (1..n)
│   ├── Node (1..n)
│   │   ├── Property (1..n)
│   │   ├── Port (input/output)
│   │   ├── Shape (RotoNode)
│   │   ├── Tracker (TrackerNode)
│   │   └── Stroke (PaintNode)
│   └── Clip (source media)
```

---

## 二、Object 基类

`Object` 是所有 Silhouette 对象的基类，提供通用的属性和方法。

### Object 通用属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `name` | str | 对象名称 |
| `label` | str | 显示标签 |
| `type` | str | 对象类型（只读） |
| `enabled` | bool | 是否启用 |
| `selected` | bool | 是否选中 |
| `valid` | bool | 对象是否有效（未被删除） |

### Object 通用方法

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `property(name)` | name: str | Property/None | 获取属性 |
| `properties` | 无 | list[str] | 属性名列表 |
| `clone()` | 无 | Object | 克隆对象 |
| `remove()` | 无 | None | 删除对象 |
| `toString()` | 无 | str | 字符串表示 |

### 示例

```python
from fx import *

node = Node("RotoNode")
print(f"类型: {node.type}")
print(f"有效: {node.valid}")
print(f"属性列表: {node.properties}")

# 类型检查
if node.type == "RotoNode":
    print("这是一个 Roto 节点")
```

---

## 三、Node 继承体系

### 3.1 Node 基类

`Node` 继承自 `Object`，是所有处理节点的基类。

| 方法/属性 | 参数 | 返回值 | 说明 |
|-----------|------|--------|------|
| `Node(type)` | type: str | Node | 创建指定类型节点 |
| `inputs` | 无 | list[Port] | 输入端口 |
| `outputs` | 无 | list[Port] | 输出端口 |
| `addProperty(prop)` | prop: Property | None | 添加自定义属性 |
| `position` | 无 | point | 节点图中位置 |

### 3.2 SourceNode

```python
src = Node("SourceNode")
# 特有属性: mediaPath, frameStart, frameEnd, frameRate, loop, premultiplied, colorSpace
```

| 特有属性 | 继承自 | 说明 |
|----------|--------|------|
| mediaPath | - | 媒体文件路径 |
| frameStart | - | 起始帧 |
| frameEnd | - | 结束帧 |
| frameRate | - | 帧率 |

### 3.3 RotoNode

RotoNode 扩展了形状管理能力。

| 特有方法 | 参数 | 返回值 | 说明 |
|----------|------|--------|------|
| `addObject(shape)` | shape: Shape | None | 添加形状 |
| `removeObject(shape)` | shape: Shape | None | 移除形状 |
| `numObjects` | 无 | int | 形状数量 |
| `object(index)` | index: int | Shape | 获取形状 |
| `objects` | 无 | list[Shape] | 所有形状 |

```python
roto = Node("RotoNode")
shape = createObject("X-Spline")
roto.addObject(shape)
print(f"形状数: {roto.numObjects}")
```

### 3.4 TrackerNode

TrackerNode 扩展了跟踪器管理。

| 特有方法 | 参数 | 返回值 | 说明 |
|----------|------|--------|------|
| `addTracker(name)` | name: str | Tracker | 添加跟踪器 |
| `removeTracker(index)` | index: int | None | 删除跟踪器 |
| `numTrackers` | 无 | int | 跟踪器数 |
| `tracker(index)` | index: int | Tracker | 获取跟踪器 |
| `trackForward()` | 无 | None | 向前跟踪 |
| `trackBackward()` | 无 | None | 向后跟踪 |

### 3.5 PaintNode

PaintNode 扩展了笔触管理。

| 特有方法 | 参数 | 返回值 | 说明 |
|----------|------|--------|------|
| `addStroke()` | 无 | Stroke | 添加笔触 |
| `removeStroke(index)` | index: int | None | 删除笔触 |
| `numStrokes` | 无 | int | 笔触数 |
| `stroke(index)` | index: int | Stroke | 获取笔触 |

### 3.6 OutputNode

OutputNode 是终端节点，无输出端口。

### 3.7 节点类型枚举

| 类型字符串 | 继承自 | 输入数 | 输出数 | 特殊能力 |
|-----------|--------|--------|--------|----------|
| SourceNode | Node | 0 | 1 | 媒体加载 |
| RotoNode | Node | 5 | 5 | 形状管理 |
| TrackerNode | Node | 1 | 1 | 跟踪器管理 |
| PaintNode | Node | 2 | 1 | 笔触管理 |
| OutputNode | Node | 1 | 0 | 渲染输出 |
| CompositeNode | Node | 2 | 1 | 图层合成 |
| ColorNode | Node | 1 | 1 | 色彩校正 |
| FilterNode | Node | 1 | 1 | 图像滤波 |
| MatteNode | Node | 1 | 1 | 遮罩生成 |
| TransformNode | Node | 1 | 1 | 几何变换 |

---

## 四、Property 继承体系

### 4.1 Property 基类

`Property` 继承自 `Object`，管理节点的所有可动画参数。

| 属性 | 类型 | 说明 |
|------|------|------|
| `name` | str | 属性名 |
| `type` | str | 数据类型 |
| `value` | Any | 当前值 |
| `defaultValue` | Any | 默认值 |
| `numKeys` | int | 关键帧数 |
| `isAnimated` | bool | 是否有动画 |
| `interpolation` | str | 插值类型 |
| `expression` | str | 表达式 |

### 4.2 属性子类对照

| 子类 | 类型字符串 | Python 类型 | 示例 |
|------|-----------|-------------|------|
| FloatProperty | "float" | float | 0.5 |
| IntProperty | "int" | int | 25 |
| BoolProperty | "bool" | bool | True |
| StringProperty | "string" | str | "alpha" |
| ColorProperty | "color" | list[3] | [1.0, 0.5, 0.0] |
| PointProperty | "point" | list[2] | [100, 200] |
| VectorProperty | "vector" | list[3] | [0, 0, 1] |
| MatrixProperty | "matrix" | list[16] | 4×4矩阵 |
| EnumProperty | "enum" | str | "medium" |

### 4.3 类型特定方法

**FloatProperty / IntProperty:**
```python
prop = node.property("opacity")  # float
prop.setValue(0.5, 0)
val = prop.getValue(50)
```

**ColorProperty:**
```python
prop = node.property("fill.color")  # color
prop.setValue([1.0, 0.0, 0.0], 0)
r, g, b = prop.value
```

**PointProperty:**
```python
prop = node.property("translate")  # point
prop.setValue([100.5, 200.3], 0)
x, y = prop.value
```

**EnumProperty:**
```python
prop = node.property("mode")  # enum
enums = prop.enums  # 获取可选值
prop.setValue("over", 0)
```

---

## 五、Project 与 Session

### 5.1 Project

`Project` 继承自 `Object`，是顶层容器。

| 方法/属性 | 参数 | 返回值 | 说明 |
|-----------|------|--------|------|
| `Project()` | 无 | Project | 创建项目 |
| `Project.load(path)` | path: str | Project | 加载项目 |
| `width` | 无 | int | 项目宽度 |
| `height` | 无 | int | 项目高度 |
| `frameRate` | 无 | float | 项目帧率 |
| `path` | 无 | str | 项目路径 |
| `addItem(item)` | item: Session/Clip | None | 添加项 |
| `removeItem(item)` | item: Session/Clip | None | 移除项 |
| `numItems` | 无 | int | 项数量 |
| `item(index)` | index: int | ProjectItem | 获取项 |
| `save(path)` | path: str | None | 保存项目 |

### 5.2 Session

`Session` 继承自 `Object`，是节点图的容器。

| 方法/属性 | 参数 | 返回值 | 说明 |
|-----------|------|--------|------|
| `Session()` | 无 | Session | 创建会话 |
| `width` | 无 | int | 宽度 |
| `height` | 无 | int | 高度 |
| `frameRate` | 无 | float | 帧率 |
| `frameStart` | 无 | int | 起始帧 |
| `frameEnd` | 无 | int | 结束帧 |
| `addNode(node)` | node: Node | None | 添加节点 |
| `removeNode(node)` | node: Node | None | 移除节点 |
| `numNodes` | 无 | int | 节点数 |
| `node(index)` | index: int | Node | 获取节点 |
| `findNode(label)` | label: str | Node/None | 按标签查找 |
| `nodes` | 无 | list[Node] | 所有节点 |

### 5.3 关系示例

```python
from fx import *

proj = Project()
activate(proj)

session = Session()
session.label = "Main"
session.width = 1920
session.height = 1080
session.frameRate = 24.0
activate(session)
proj.addItem(session)

# Project 包含多个 Session
session2 = Session()
session2.label = "Secondary"
proj.addItem(session2)

print(f"项目项数: {proj.numItems}")
for i in range(proj.numItems):
    item = proj.item(i)
    print(f"  项 {i}: {item.label} (类型: {item.type})")
```

---

## 六、Shape 与 Point

### 6.1 Shape 基类

`Shape` 继承自 `Object`，是所有形状的基类。

| 方法/属性 | 参数 | 返回值 | 说明 |
|-----------|------|--------|------|
| `name` | 无 | str | 形状名 |
| `closed` | 无 | bool | 是否闭合 |
| `feather` | 无 | float | 羽化值 |
| `blur` | 无 | float | 模糊值 |
| `visible` | 无 | bool | 可见性 |
| `locked` | 无 | bool | 锁定状态 |
| `opacity` | 无 | float | 不透明度 |
| `inverted` | 无 | bool | 是否反转 |
| `color` | 无 | list[3] | 显示颜色 |
| `addPoint(x, y)` | x, y: float | Point | 添加控制点 |
| `removePoint(index)` | index: int | None | 删除控制点 |
| `numPoints` | 无 | int | 控制点数 |
| `point(index)` | index: int | Point | 获取控制点 |

### 6.2 Shape 子类

| 子类 | 类型字符串 | 特点 | 适用场景 |
|------|-----------|------|----------|
| XSpline | "X-Spline" | 平滑曲线，控制点带权重 | 有机形状（人物、动物） |
| Bezier | "Bezier" | 贝塞尔曲线，切线控制 | 硬边物体（建筑、车辆） |
| Circle | "Circle" | 正圆 | 圆形遮罩 |
| Rectangle | "Rectangle" | 矩形 | 矩形遮罩 |
| Freehand | "Freehand" | 自由绘制 | 快速草图 |

### 6.3 Point 类

`Point` 是形状的控制点。

| 属性 | 类型 | 说明 |
|------|------|------|
| `x` | float | X 坐标 |
| `y` | float | Y 坐标 |
| `feather` | float | 点级羽化 |
| `tangent` | list | 切线方向（Bezier） |
| `weight` | float | 权重（X-Spline） |

### 6.4 示例

```python
from fx import *

# 创建 X-Spline
shape = createObject("X-Spline")
shape.name = "Character"
shape.closed = True
shape.feather = 2.0
shape.color = [1.0, 0.5, 0.0]

# 添加点
p1 = shape.addPoint(100, 100)
p1.weight = 1.0

p2 = shape.addPoint(300, 100)
p2.weight = 0.5  # 减小权重使曲线更尖锐

p3 = shape.addPoint(200, 300)

# 修改点
p3.x = 250
p3.y = 350

print(f"形状: {shape.name}, 点数: {shape.numPoints}")
```

---

## 七、Port 端口对象

`Port` 继承自 `Object`，表示节点的输入/输出连接点。

| 方法/属性 | 参数 | 返回值 | 说明 |
|-----------|------|--------|------|
| `connect(target)` | target: Port | None | 连接到目标端口 |
| `disconnect()` | 无 | None | 断开连接 |
| `isConnected()` | 无 | bool | 是否已连接 |
| `source` | 无 | Node | 源节点（只读） |
| `target` | 无 | Node | 目标节点（只读） |
| `index` | 无 | int | 端口索引 |
| `node` | 无 | Node | 所属节点 |
| `name` | 无 | str | 端口名 |
| `direction` | 无 | str | "input" 或 "output" |

### 示例

```python
from fx import *

src = Node("SourceNode")
roto = Node("RotoNode")
session.addNode(src)
session.addNode(roto)

# 连接
out_port = src.outputs[0]
in_port = roto.inputs[1]
out_port.connect(in_port)

# 检查连接状态
print(f"输出端口 {out_port.name} 已连接: {out_port.isConnected()}")
print(f"输入端口 {in_port.name} 已连接: {in_port.isConnected()}")
print(f"源节点: {out_port.node.label}")
print(f"目标节点: {in_port.node.label}")

# 断开
out_port.disconnect()
```

---

## 八、Tracker 与 Stroke

### 8.1 Tracker

`Tracker` 继承自 `Object`，表示单个跟踪点。

| 方法/属性 | 参数 | 返回值 | 说明 |
|-----------|------|--------|------|
| `name` | 无 | str | 跟踪器名 |
| `position` | 无 | point | 跟踪位置 |
| `searchRegion` | 无 | list | 搜索区域 [w, h] |
| `patternRegion` | 无 | list | 模板区域 [w, h] |
| `numKeys` | 无 | int | 跟踪关键帧数 |
| `keyPosition(i)` | i: int | point | 第i个跟踪位置 |
| `keyTime(i)` | i: int | float | 第i个关键帧时间 |
| `clearKeys()` | 无 | None | 清除跟踪数据 |

### 8.2 Stroke

`Stroke` 继承自 `Object`，表示一个 Paint 笔触。

| 方法/属性 | 参数 | 返回值 | 说明 |
|-----------|------|--------|------|
| `size` | 无 | float | 笔刷大小 |
| `hardness` | 无 | float | 硬度 |
| `opacity` | 无 | float | 不透明度 |
| `mode` | 无 | str | 模式 |
| `frame` | 无 | int | 笔触帧 |
| `sourceFrame` | 无 | int | 采样源帧 |
| `sourceOffset` | 无 | point | 采样偏移 |
| `addPoint(x, y, pressure)` | x, y, pressure | None | 添加笔触点 |
| `numPoints` | 无 | int | 点数 |
| `point(index)` | index: int | point | 获取点 |

### 示例

```python
from fx import *

# Tracker 示例
tracker_node = Node("TrackerNode")
session.addNode(tracker_node)

t1 = tracker_node.addTracker("Track_01")
t1.position = [500, 300]
t1.searchRegion = [50, 50]
t1.patternRegion = [15, 15]

# Stroke 示例
paint = Node("PaintNode")
session.addNode(paint)

stroke = paint.addStroke()
stroke.size = 30.0
stroke.mode = "clone"
stroke.frame = 10
stroke.sourceOffset = [50, 0]
stroke.addPoint(100, 200, 1.0)
stroke.addPoint(200, 210, 0.8)
```

---

## 九、Clip 与媒体对象

`Clip` 继承自 `Object`，表示媒体素材。

| 方法/属性 | 参数 | 返回值 | 说明 |
|-----------|------|--------|------|
| `loadClip(path)` | path: str | Clip | 加载素材（全局函数） |
| `path` | 无 | str | 文件路径 |
| `width` | 无 | int | 宽度 |
| `height` | 无 | int | 高度 |
| `frameRate` | 无 | float | 帧率 |
| `frameStart` | 无 | int | 起始帧 |
| `frameEnd` | 无 | int | 结束帧 |
| `duration` | 无 | float | 时长（秒） |
| `numChannels` | 无 | int | 通道数 |

### 示例

```python
from fx import *

clip = loadClip("D:/footage/scene.mov")
print(f"素材: {clip.width}x{clip.height}")
print(f"帧率: {clip.frameRate}fps")
print(f"时长: {clip.duration}秒 ({clip.frameEnd - clip.frameStart + 1}帧)")
```

---

## 十、对象生命周期

### 10.1 对象创建

```python
from fx import *

# 通过构造函数创建
node = Node("RotoNode")
prop = Property("myProp", "float")

# 通过工厂函数创建
shape = createObject("X-Spline")
clip = loadClip("path/to/file.mov")
```

### 10.2 对象添加到容器

```python
# 节点必须添加到 Session 才生效
session.addNode(node)

# 形状必须添加到 RotoNode
roto.addObject(shape)

# 跟踪器必须添加到 TrackerNode
tracker_node.addTracker("name")

# 项目项必须添加到 Project
proj.addItem(session)
```

### 10.3 对象删除

```python
# 显式删除
node.remove()
shape.remove()

# 从容器移除
session.removeNode(node)
roto.removeObject(shape)
proj.removeItem(session)
```

### 10.4 有效性检查

```python
# 删除后对象变为无效
node.remove()
if not node.valid:
    print("节点已被删除")

# 安全访问
for n in session.nodes[:]:  # 复制列表避免迭代时修改
    if n.valid and n.type == "FilterNode":
        n.remove()
```

---

## 十一、最佳实践

### 11.1 类型安全检查

```python
def is_roto_node(node):
    """安全检查节点类型"""
    return node.valid and node.type == "RotoNode"

def get_shapes_safely(roto_node):
    """安全获取形状列表"""
    if not is_roto_node(roto_node):
        return []
    return [s for s in roto_node.objects if s.valid]
```

### 11.2 对象遍历模板

```python
def traverse_project(proj):
    """遍历项目中的所有对象"""
    for i in range(proj.numItems):
        item = proj.item(i)
        if not item.valid:
            continue
        print(f"项目项: {item.label} ({item.type})")

        if item.type == "Session":
            for j in range(item.numNodes):
                node = item.node(j)
                if not node.valid:
                    continue
                print(f"  节点: {node.label} ({node.type})")

                # 遍历属性
                for name in node.properties:
                    prop = node.property(name)
                    animated = "动画" if prop.isAnimated else "静态"
                    print(f"    {name}: {prop.value} ({animated})")

                # RotoNode 遍历形状
                if node.type == "RotoNode":
                    for k in range(node.numObjects):
                        shape = node.object(k)
                        print(f"    形状: {shape.name} ({shape.numPoints}点)")
```

### 11.3 对象克隆与复制

```python
def clone_roto_setup(source_roto, target_session):
    """克隆 RotoNode 的设置"""
    new_roto = Node("RotoNode")
    new_roto.label = source_roto.label + "_Copy"
    target_session.addNode(new_roto)

    # 复制属性
    for name in source_roto.properties:
        prop = source_roto.property(name)
        new_roto.property(name).setValue(prop.value, 0)

    # 复制形状
    for i in range(source_roto.numObjects):
        orig_shape = source_roto.object(i)
        new_shape = createObject(orig_shape.type)
        new_shape.name = orig_shape.name + "_Copy"
        new_shape.closed = orig_shape.closed
        new_shape.feather = orig_shape.feather
        for j in range(orig_shape.numPoints):
            p = orig_shape.point(j)
            new_shape.addPoint(p.x, p.y)
        new_roto.addObject(new_shape)

    return new_roto
```

### 11.4 撤销与事务

```python
from fx import *

# 将多个操作包装为单个撤销步骤
beginUndo("Create Roto Pipeline")

src = Node("SourceNode")
src.property("mediaPath").setValue("D:/footage/scene.mov", 0)
session.addNode(src)

roto = Node("RotoNode")
session.addNode(roto)

out_node = Node("OutputNode")
session.addNode(out_node)

src.outputs[0].connect(roto.inputs[1])
roto.outputs[0].connect(out_node.inputs[0])

endUndo()  # 用户可一次撤销所有操作
```
