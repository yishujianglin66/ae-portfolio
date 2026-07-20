# Silhouette Python API 速查手册

> 分类: API与参数手册
> 更新日期: 2026-07-11
> 概述: 按功能分类的 Silhouette fx 模块 Python API 速查表，覆盖项目管理到渲染输出的完整工作流

## 目录

- [一、模块导入与初始化](#一模块导入与初始化)
- [二、项目管理 API](#二项目管理-api)
- [三、会话管理 API](#三会话管理-api)
- [四、节点操作 API](#四节点操作-api)
- [五、属性操作 API](#五属性操作-api)
- [六、形状操作 API](#六形状操作-api)
- [七、跟踪操作 API](#七跟踪操作-api)
- [八、Paint 操作 API](#八paint-操作-api)
- [九、渲染输出 API](#九渲染输出-api)
- [十、文件 IO API](#十文件-io-api)
- [十一、视图与交互 API](#十一视图与交互-api)
- [十二、工具函数 API](#十二工具函数-api)
- [十三、常用代码片段](#十三常用代码片段)

---

## 一、模块导入与初始化

```python
from fx import *           # 导入核心模块（推荐）
import fx                   # 带命名空间导入
```

### 全局函数

| 函数 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `version` | 无 | str | Silhouette 版本号 |
| `activeProject()` | 无 | Project/None | 获取活动项目 |
| `activeSession()` | 无 | Session/None | 获取活动会话 |
| `activate(obj)` | obj: Project/Session | None | 激活项目或会话 |
| `createObject(type)` | type: str | Object | 创建对象（Shape等） |
| `beginUndo(name)` | name: str | None | 开始撤销组 |
| `endUndo()` | 无 | None | 结束撤销组 |
| `alert(msg)` | msg: str | None | 弹窗提示 |
| `confirm(msg)` | msg: str | bool | 确认对话框 |

---

## 二、项目管理 API

### Project 类

| 方法/属性 | 参数 | 返回值 | 说明 |
|-----------|------|--------|------|
| `Project()` | 无 | Project | 创建新项目 |
| `label` | 无 | str | 项目标签 |
| `path` | 无 | str | 项目文件路径 |
| `width` | 无 | int | 项目宽度 |
| `height` | 无 | int | 项目高度 |
| `frameRate` | 无 | float | 项目帧率 |
| `addItem(item)` | item: Session/Clip | None | 添加项目项 |
| `removeItem(item)` | item: Session/Clip | None | 移除项目项 |
| `numItems` | 无 | int | 项目项数量 |
| `item(index)` | index: int | ProjectItem | 获取项目项 |
| `save(path)` | path: str | None | 保存项目 |
| `load(path)` | path: str | Project | 加载项目 |

### 示例

```python
from fx import *

# 创建/获取项目
proj = activeProject()
if proj is None:
    proj = Project()
    activate(proj)

# 项目属性
proj.label = "My_Project"
print(f"尺寸: {proj.width}x{proj.height}, 帧率: {proj.frameRate}")

# 保存项目
proj.save("D:/projects/my_project.sfx")

# 加载项目
loaded = Project.load("D:/projects/my_project.sfx")
activate(loaded)
```

---

## 三、会话管理 API

### Session 类

| 方法/属性 | 参数 | 返回值 | 说明 |
|-----------|------|--------|------|
| `Session()` | 无 | Session | 创建新会话 |
| `label` | 无 | str | 会话标签 |
| `width` | 无 | int | 会话宽度 |
| `height` | 无 | int | 会话高度 |
| `frameRate` | 无 | float | 会话帧率 |
| `frameStart` | 无 | int | 起始帧 |
| `frameEnd` | 无 | int | 结束帧 |
| `addNode(node)` | node: Node | None | 添加节点 |
| `removeNode(node)` | node: Node | None | 移除节点 |
| `numNodes` | 无 | int | 节点数量 |
| `node(index)` | index: int | Node | 获取节点 |
| `findNode(label)` | label: str | Node/None | 按标签查找节点 |
| `nodes` | 无 | list | 所有节点列表 |

### 示例

```python
from fx import *

# 创建会话
session = activeSession()
if session is None:
    session = Session()
    session.label = "Roto_Session"
    session.width = 1920
    session.height = 1080
    session.frameRate = 30.0
    session.frameStart = 0
    session.frameEnd = 240
    activate(session)
    proj.addItem(session)

# 查找节点
roto = session.findNode("Body_Roto")
if roto:
    print(f"找到节点: {roto.label}")
```

---

## 四、节点操作 API

### Node 类

| 方法/属性 | 参数 | 返回值 | 说明 |
|-----------|------|--------|------|
| `Node(type)` | type: str | Node | 创建节点 |
| `label` | 无 | str | 节点标签 |
| `type` | 无 | str | 节点类型（只读） |
| `enabled` | 无 | bool | 是否启用 |
| `selected` | 无 | bool | 是否选中 |
| `inputs` | 无 | list[Port] | 输入端口列表 |
| `outputs` | 无 | list[Port] | 输出端口列表 |
| `property(name)` | name: str | Property | 获取属性 |
| `properties` | 无 | list[str] | 属性名列表 |
| `addProperty(prop)` | prop: Property | None | 添加属性 |
| `remove()` | 无 | None | 删除节点 |
| `clone()` | 无 | Node | 克隆节点 |

### Port 类

| 方法/属性 | 参数 | 返回值 | 说明 |
|-----------|------|--------|------|
| `connect(target)` | target: Port | None | 连接到目标端口 |
| `disconnect()` | 无 | None | 断开连接 |
| `isConnected()` | 无 | bool | 是否已连接 |
| `source` | 无 | Node | 源节点（只读） |
| `target` | 无 | Node | 目标节点（只读） |
| `index` | 无 | int | 端口索引 |
| `node` | 无 | Node | 所属节点 |

### 示例

```python
from fx import *

# 创建节点
src = Node("SourceNode")
src.label = "Input"
session.addNode(src)

roto = Node("RotoNode")
roto.label = "Main_Roto"
session.addNode(roto)

# 连接节点
src.outputs[0].connect(roto.inputs[1])

# 克隆节点
roto_clone = roto.clone()
roto_clone.label = "Main_Roto_Copy"
session.addNode(roto_clone)

# 遍历所有节点
for i in range(session.numNodes):
    n = session.node(i)
    print(f"节点 {i}: {n.label} (类型: {n.type})")
```

---

## 五、属性操作 API

### Property 类

| 方法/属性 | 参数 | 返回值 | 说明 |
|-----------|------|--------|------|
| `Property(name, type)` | name: str, type: str | Property | 创建属性 |
| `name` | 无 | str | 属性名 |
| `type` | 无 | str | 属性类型 |
| `value` | 无 | Any | 当前值 |
| `defaultValue` | 无 | Any | 默认值 |
| `setValue(value, frame)` | value: Any, frame: int | None | 设置值 |
| `getValue(frame)` | frame: int | Any | 获取值 |
| `reset()` | 无 | None | 重置默认值 |
| `numKeys` | 无 | int | 关键帧数 |
| `keyValue(i)` | i: int | Any | 关键帧值 |
| `keyTime(i)` | i: int | float | 关键帧时间 |
| `addKey(frame, value)` | frame: int, value: Any | None | 添加关键帧 |
| `removeKey(i)` | i: int | None | 删除关键帧 |
| `removeAllKeys()` | 无 | None | 清除所有关键帧 |
| `isAnimated` | 无 | bool | 是否有动画 |
| `setExpression(expr)` | expr: str | None | 设置表达式 |
| `removeExpression()` | 无 | None | 移除表达式 |

### 示例

```python
from fx import *

prop = roto.property("alpha.blur")
prop.setValue(0.5, 0)

# 动画
prop.setValue(0.0, 0)
prop.setValue(2.0, 30)
prop.setValue(0.0, 60)
print(f"关键帧数: {prop.numKeys}")

# 表达式
prop.setExpression("sin(time * 2) * 0.5 + 0.5")
```

---

## 六、形状操作 API

### Shape 类

| 方法/属性 | 参数 | 返回值 | 说明 |
|-----------|------|--------|------|
| `createObject(type)` | type: str | Shape | 创建形状 |
| `name` | 无 | str | 形状名 |
| `type` | 无 | str | 形状类型 |
| `points` | 无 | list | 控制点列表 |
| `closed` | 无 | bool | 是否闭合 |
| `feather` | 无 | float | 羽化值 |
| `blur` | 无 | float | 模糊值 |
| `visible` | 无 | bool | 是否可见 |
| `locked` | 无 | bool | 是否锁定 |
| `opacity` | 无 | float | 不透明度 |
| `inverted` | 无 | bool | 是否反转 |
| `color` | 无 | list | 显示颜色 |
| `addPoint(x, y)` | x: float, y: float | Point | 添加控制点 |
| `removePoint(index)` | index: int | None | 删除控制点 |
| `numPoints` | 无 | int | 控制点数量 |
| `point(index)` | index: int | Point | 获取控制点 |

### Point 类

| 方法/属性 | 参数 | 返回值 | 说明 |
|-----------|------|--------|------|
| `x` | 无 | float | X 坐标 |
| `y` | 无 | float | Y 坐标 |
| `feather` | 无 | float | 点的羽化 |
| `tangent` | 无 | list | 切线方向 |

### 形状类型

| 类型字符串 | 说明 |
|-----------|------|
| "X-Spline" | X样条曲线（推荐，平滑有机形状） |
| "Bezier" | 贝塞尔曲线（精确硬边） |
| "Circle" | 圆形 |
| "Rectangle" | 矩形 |
| "Ellipse" | 椭圆 |
| "Freehand" | 自由绘制 |

### 示例

```python
from fx import *

# 创建 X-Spline 形状
shape = createObject("X-Spline")
shape.name = "Body_Mask"
shape.closed = True
shape.feather = 2.0
shape.opacity = 1.0
shape.color = [1.0, 0.0, 0.0]

# 添加控制点
shape.addPoint(100, 100)
shape.addPoint(300, 100)
shape.addPoint(300, 300)
shape.addPoint(100, 300)

# 将形状添加到 RotoNode
roto = session.findNode("Main_Roto")
roto.addObject(shape)

# 遍历控制点
for i in range(shape.numPoints):
    p = shape.point(i)
    print(f"点 {i}: ({p.x}, {p.y})")
```

---

## 七、跟踪操作 API

### Tracker 类

| 方法/属性 | 参数 | 返回值 | 说明 |
|-----------|------|--------|------|
| `addTracker(name)` | name: str | Tracker | 添加跟踪器 |
| `removeTracker(index)` | index: int | None | 删除跟踪器 |
| `numTrackers` | 无 | int | 跟踪器数量 |
| `tracker(index)` | index: int | Tracker | 获取跟踪器 |
| `trackForward()` | 无 | None | 向前跟踪 |
| `trackBackward()` | 无 | None | 向后跟踪 |
| `trackAll()` | 无 | None | 跟踪所有帧 |
| `clearTrack()` | 无 | None | 清除跟踪数据 |

### 单个 Tracker 项

| 方法/属性 | 参数 | 返回值 | 说明 |
|-----------|------|--------|------|
| `name` | 无 | str | 跟踪器名 |
| `position` | 无 | point | 跟踪位置 |
| `searchRegion` | 无 | point | 搜索区域大小 |
| `patternRegion` | 无 | point | 模板区域大小 |
| `numKeys` | 无 | int | 跟踪关键帧数 |
| `keyPosition(i)` | i: int | point | 获取跟踪数据 |
| `keyTime(i)` | i: int | float | 获取关键帧时间 |

### 示例

```python
from fx import *

tracker_node = Node("TrackerNode")
tracker_node.label = "Motion_Track"
session.addNode(tracker_node)

# 添加跟踪点
t1 = tracker_node.addTracker("Point_01")
t1.position = [500, 300]
t1.searchRegion = [50, 50]
t1.patternRegion = [15, 15]

# 执行跟踪
tracker_node.trackForward()

# 导出跟踪数据
for i in range(t1.numKeys):
    pos = t1.keyPosition(i)
    time = t1.keyTime(i)
    print(f"帧 {time}: ({pos[0]}, {pos[1]})")
```

---

## 八、Paint 操作 API

### Paint 类

| 方法/属性 | 参数 | 返回值 | 说明 |
|-----------|------|--------|------|
| `addStroke()` | 无 | Stroke | 添加笔触 |
| `removeStroke(index)` | index: int | None | 删除笔触 |
| `numStrokes` | 无 | int | 笔触数量 |
| `stroke(index)` | index: int | Stroke | 获取笔触 |

### Stroke 类

| 方法/属性 | 参数 | 返回值 | 说明 |
|-----------|------|--------|------|
| `size` | 无 | float | 笔刷大小 |
| `hardness` | 无 | float | 硬度 |
| `opacity` | 无 | float | 不透明度 |
| `mode` | 无 | str | 模式 |
| `frame` | 无 | int | 笔触所在帧 |
| `sourceFrame` | 无 | int | 采样源帧 |
| `sourceOffset` | 无 | point | 采样偏移 |
| `addPoint(x, y, pressure)` | x, y, pressure | None | 添加笔触点 |
| `numPoints` | 无 | int | 笔触点数 |
| `point(index)` | index: int | point | 获取笔触点 |

### 示例

```python
from fx import *

paint = Node("PaintNode")
paint.label = "Cleanup"
session.addNode(paint)

# 添加笔触
stroke = paint.addStroke()
stroke.size = 35.0
stroke.hardness = 0.8
stroke.opacity = 1.0
stroke.mode = "clone"
stroke.frame = 10
stroke.sourceFrame = 8
stroke.sourceOffset = [50, 0]

# 添加笔触路径点
stroke.addPoint(100, 200, 1.0)
stroke.addPoint(150, 210, 0.9)
stroke.addPoint(200, 220, 1.0)

print(f"笔触数: {paint.numStrokes}, 点数: {stroke.numPoints}")
```

---

## 九、渲染输出 API

### 渲染函数

| 函数 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `render(node, start, end)` | node: Node, start: int, end: int | None | 渲染指定范围 |
| `renderSession(session, start, end)` | session: Session, start: int, end: int | None | 渲染整个会话 |
| `renderFrame(node, frame)` | node: Node, frame: int | None | 渲染单帧 |
| `stopRender()` | 无 | None | 停止渲染 |
| `isRendering` | 无 | bool | 是否正在渲染 |

### OutputNode 常用属性

| 属性 | 说明 |
|------|------|
| path | 输出路径（支持 [####]） |
| format | exr/tiff/png/dpx/jpg |
| compression | none/zip/piz/rle/dwaa |
| depth | 8i/16i/16f/32f |
| channels | rgb/rgba/alpha |
| frameStart | 起始帧 |
| frameEnd | 结束帧 |

### 示例

```python
from fx import *

out_node = Node("OutputNode")
out_node.property("path").setValue("D:/output/clip_[####].exr", 0)
out_node.property("format").setValue("exr", 0)
out_node.property("compression").setValue("piz", 0)
out_node.property("depth").setValue("32f", 0)
out_node.property("frameStart").setValue(0, 0)
out_node.property("frameEnd").setValue(240, 0)
session.addNode(out_node)

# 连接
roto.outputs[0].connect(out_node.inputs[0])

# 渲染
render(out_node, 0, 240)
```

---

## 十、文件 IO API

| 函数 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `loadClip(path)` | path: str | Clip | 加载媒体素材 |
| `saveProject(path)` | path: str | None | 保存项目 |
| `loadProject(path)` | path: str | Project | 加载项目 |
| `importFile(path)` | path: str | None | 导入文件 |
| `exportData(node, path)` | node: Node, path: str | None | 导出节点数据 |

### 示例

```python
from fx import *

# 加载素材
clip = loadClip("D:/footage/scene.mov")
print(f"素材: {clip.width}x{clip.height}, {clip.frameRate}fps")

# 导出跟踪数据为 JSON
import json
track_data = {
    "trackers": [],
    "frameRange": [0, 240]
}
for i in range(tracker.numTrackers):
    t = tracker.tracker(i)
    data = []
    for k in range(t.numKeys):
        data.append({
            "frame": int(t.keyTime(k)),
            "x": t.keyPosition(k)[0],
            "y": t.keyPosition(k)[1]
        })
    track_data["trackers"].append({"name": t.name, "data": data})

with open("D:/export/tracking.json", "w") as f:
    json.dump(track_data, f, indent=2)
```

---

## 十一、视图与交互 API

| 函数/属性 | 参数 | 返回值 | 说明 |
|-----------|------|--------|------|
| `viewer` | 无 | Viewer | 获取视图对象 |
| `currentFrame` | 无 | int | 当前帧 |
| `setCurrentFrame(frame)` | frame: int | None | 设置当前帧 |
| `startTime` | 无 | int | 时间线起始 |
| `endTime` | 无 | int | 时间线结束 |
| `play()` | 无 | None | 播放 |
| `stop()` | 无 | None | 停止播放 |
| `refresh()` | 无 | None | 刷新视图 |
| `zoomToFit()` | 无 | None | 适配窗口 |

### 示例

```python
from fx import *

# 获取/设置当前帧
frame = currentFrame
print(f"当前帧: {frame}")
setCurrentFrame(50)

# 播放控制
play()
stop()

# 刷新视图
refresh()
```

---

## 十二、工具函数 API

| 函数 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `beginUndo(name)` | name: str | None | 开始撤销组 |
| `endUndo()` | 无 | None | 结束撤销组 |
| `alert(msg)` | msg: str | None | 弹窗 |
| `confirm(msg)` | msg: str | bool | 确认框 |
| `prompt(msg, default)` | msg: str, default: str | str | 输入框 |
| `getOpenFileName(filter)` | filter: str | str | 打开文件对话框 |
| `getSaveFileName(filter)` | filter: str | str | 保存文件对话框 |
| `getExistingDirectory()` | 无 | str | 选择目录对话框 |

### 示例

```python
from fx import *

# 撤销组
beginUndo("Batch Roto")
for i in range(5):
    roto = Node("RotoNode")
    roto.label = f"Roto_{i}"
    session.addNode(roto)
endUndo()

# 用户交互
if confirm("确定要删除所有节点？"):
    for n in session.nodes:
        n.remove()

# 文件选择
path = getOpenFileName("Video (*.mov *.mp4);;Image (*.exr *.png)")
if path:
    print(f"选择文件: {path}")
```

---

## 十三、常用代码片段

### 13.1 创建完整 Roto 流水线

```python
from fx import *

def create_roto_pipeline(source_path, output_path, frame_end=100):
    proj = activeProject() or Project()
    activate(proj)
    session = activeSession() or Session()
    session.label = "Roto_Pipeline"
    activate(session)
    proj.addItem(session)

    src = Node("SourceNode")
    src.property("mediaPath").setValue(source_path.replace("\\", "/"), 0)
    session.addNode(src)

    roto = Node("RotoNode")
    roto.label = "Main_Roto"
    session.addNode(roto)

    out_node = Node("OutputNode")
    out_node.property("path").setValue(output_path.replace("\\", "/"), 0)
    out_node.property("frameEnd").setValue(frame_end, 0)
    session.addNode(out_node)

    src.outputs[0].connect(roto.inputs[1])
    roto.outputs[0].connect(out_node.inputs[0])

    return roto
```

### 13.2 批量创建形状

```python
def create_multiple_shapes(roto_node, shape_configs):
    """批量创建形状
    shape_configs: [{"name": "...", "type": "X-Spline", "points": [[x,y],...]}]
    """
    shapes = []
    for cfg in shape_configs:
        shape = createObject(cfg.get("type", "X-Spline"))
        shape.name = cfg["name"]
        shape.closed = cfg.get("closed", True)
        shape.feather = cfg.get("feather", 1.0)
        for pt in cfg["points"]:
            shape.addPoint(pt[0], pt[1])
        roto_node.addObject(shape)
        shapes.append(shape)
    return shapes
```

### 13.3 节点查找与批量操作

```python
def find_all_nodes_by_type(session, node_type):
    """查找指定类型的所有节点"""
    return [n for n in session.nodes if n.type == node_type]

def disable_all_filters(session):
    """禁用所有滤镜节点"""
    for n in find_all_nodes_by_type(session, "FilterNode"):
        n.enabled = False
```

### 13.4 导出跟踪数据为 AE 格式

```python
def export_tracking_to_ae(tracker_node, output_path):
    """导出跟踪数据为AE兼容格式"""
    import json
    ae_data = {
        "version": "2.0",
        "source": "silhouette",
        "tracking": {"trackers": [], "exportFormat": "ae_keyframes"}
    }
    for i in range(tracker_node.numTrackers):
        t = tracker_node.tracker(i)
        keyframes = []
        for k in range(t.numKeys):
            pos = t.keyPosition(k)
            keyframes.append({
                "frame": int(t.keyTime(k)),
                "x": pos[0], "y": pos[1]
            })
        ae_data["tracking"]["trackers"].append({
            "name": t.name,
            "keyframes": keyframes
        })
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(ae_data, f, indent=2, ensure_ascii=False)
    print(f"[SILHOUETTE] 导出完成: {output_path}")
```
