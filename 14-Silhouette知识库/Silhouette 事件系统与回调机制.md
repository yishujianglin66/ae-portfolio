# Silhouette 事件系统与回调机制

> 分类: API与参数手册
> 更新日期: 2026-07-11
> 概述: 说明 Silhouette 事件类型、回调注册、事件过滤器与自定义事件机制

## 目录

- [一、事件系统概述](#一事件系统概述)
- [二、事件类型](#二事件类型)
- [三、回调注册](#三回调注册)
- [四、事件过滤器](#四事件过滤器)
- [五、自定义事件](#五自定义事件)
- [六、事件对象](#六事件对象)
- [七、实战示例](#七实战示例)
- [八、最佳实践](#八最佳实践)

---

## 一、事件系统概述

Silhouette 提供事件驱动的脚本系统，允许在特定操作发生时自动执行自定义代码。

### 事件流

```
用户操作 / 系统变更
        ↓
   事件触发 (Event)
        ↓
   事件分发 (Dispatcher)
        ↓
   回调函数执行 (Callback)
```

### 核心组件

| 组件 | 说明 |
|------|------|
| Event | 事件对象，包含事件类型与数据 |
| Hook | 事件钩子，注册回调函数 |
| Filter | 事件过滤器，拦截或修改事件 |
| Dispatcher | 事件分发器，管理事件队列 |

---

## 二、事件类型

### 2.1 完整事件类型表

| 事件名 | 触发时机 | 事件数据 | 可取消 |
|--------|----------|----------|--------|
| `frameChanged` | 当前帧改变 | frame: int | 否 |
| `nodeAdded` | 节点添加 | node: Node | 是 |
| `nodeRemoved` | 节点删除 | node: Node | 是 |
| `nodeRenamed` | 节点重命名 | node: Node, oldLabel: str | 否 |
| `nodeConnected` | 节点连接 | srcNode, dstNode, srcPort, dstPort | 是 |
| `nodeDisconnected` | 节点断开 | srcNode, dstNode | 否 |
| `propertyChanged` | 属性值改变 | node, property, frame, oldValue, newValue | 是 |
| `propertyAnimated` | 属性添加动画 | node, property | 否 |
| `keyAdded` | 关键帧添加 | node, property, frame, value | 否 |
| `keyRemoved` | 关键帧删除 | node, property, frame | 否 |
| `shapeAdded` | 形状添加 | node, shape | 是 |
| `shapeRemoved` | 形状删除 | node, shape | 是 |
| `sessionActivated` | 会话激活 | session: Session | 否 |
| `sessionCreated` | 会话创建 | session: Session | 否 |
| `projectLoaded` | 项目加载 | project: Project | 否 |
| `projectSaved` | 项目保存 | project: Project, path: str | 否 |
| `renderStarted` | 渲染开始 | session, startFrame, endFrame | 否 |
| `renderFrame` | 渲染单帧 | frame: int | 否 |
| `renderCompleted` | 渲染完成 | session, output | 否 |
| `renderCanceled` | 渲染取消 | session | 否 |
| `selectionChanged` | 选择改变 | selected: list | 否 |
| `viewUpdated` | 视图更新 | frame: int | 否 |
| `playbackStarted` | 播放开始 | frame: int | 否 |
| `playbackStopped` | 播放停止 | frame: int | 否 |
| `customEvent` | 自定义事件 | data: dict | 否 |

### 2.2 事件分类

#### 节点事件

```python
# 节点添加
def on_node_added(event):
    print(f"节点添加: {event.node.label} ({event.node.type})")

# 节点删除
def on_node_removed(event):
    print(f"节点删除: {event.node.label}")
```

#### 属性事件

```python
# 属性改变
def on_property_changed(event):
    print(f"属性改变: {event.node.label}.{event.property.name}")
    print(f"  旧值: {event.oldValue}")
    print(f"  新值: {event.newValue}")
    print(f"  帧: {event.frame}")
```

#### 渲染事件

```python
# 渲染开始
def on_render_started(event):
    print(f"渲染开始: 帧 {event.startFrame}-{event.endFrame}")

# 渲染帧
def on_render_frame(event):
    print(f"渲染帧: {event.frame}")

# 渲染完成
def on_render_completed(event):
    print("渲染完成")
```

---

## 三、回调注册

### 3.1 注册方法

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `addHook(event, callback)` | event: str, callback: func | hook_id | 注册回调 |
| `removeHook(hook_id)` | hook_id: int | None | 移除回调 |
| `addHookOnce(event, callback)` | event: str, callback: func | hook_id | 注册一次性回调 |

### 3.2 基本注册示例

```python
from fx import *

# 注册回调
def on_frame_changed(event):
    print(f"当前帧: {event.frame}")

hook_id = addHook("frameChanged", on_frame_changed)

# 移除回调
# removeHook(hook_id)
```

### 3.3 多回调注册

```python
from fx import *

# 同一事件可注册多个回调
def log_node_added(event):
    print(f"[LOG] 节点添加: {event.node.label}")

def auto_connect_node(event):
    if event.node.type == "RotoNode":
        src = session.findNode("SourceNode")
        if src:
            src.outputs[0].connect(event.node.inputs[1])
            print(f"[AUTO] 自动连接到 {event.node.label}")

addHook("nodeAdded", log_node_added)
addHook("nodeAdded", auto_connect_node)
```

### 3.4 一次性回调

```python
from fx import *

# 只执行一次的回调
def on_first_render(event):
    print("首次渲染开始！")
    # 此回调执行后自动移除

addHookOnce("renderStarted", on_first_render)
```

---

## 四、事件过滤器

### 4.1 过滤器概念

事件过滤器可以在事件到达回调前拦截或修改事件。

### 4.2 过滤器方法

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `addFilter(event, filter_func)` | event: str, filter: func | filter_id | 添加过滤器 |
| `removeFilter(filter_id)` | filter_id: int | None | 移除过滤器 |

### 4.3 过滤器示例

```python
from fx import *

# 过滤器：只处理特定节点的属性变化
def filter_property_event(event):
    # 只放行 RotoNode 的属性变化
    if event.node.type == "RotoNode":
        return event  # 放行
    else:
        return None   # 拦截

addFilter("propertyChanged", filter_property_event)

# 过滤器：限制渲染帧范围
def filter_render(event):
    if event.frame > 100:
        print(f"[FILTER] 跳过帧 {event.frame}")
        return None
    return event

addFilter("renderFrame", filter_render)
```

### 4.4 条件过滤器模板

```python
def make_node_type_filter(node_type):
    """创建节点类型过滤器工厂"""
    def filter_func(event):
        if hasattr(event, 'node') and event.node.type == node_type:
            return event
        return None
    return filter_func

# 只处理 RotoNode 事件
addFilter("propertyChanged", make_node_type_filter("RotoNode"))
# 只处理 PaintNode 事件
addFilter("propertyChanged", make_node_type_filter("PaintNode"))
```

---

## 五、自定义事件

### 5.1 发送自定义事件

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `sendEvent(event_name, data)` | event_name: str, data: dict | None | 发送自定义事件 |
| `postEvent(event_name, data)` | event_name: str, data: dict | None | 异步发送事件 |

### 5.2 自定义事件示例

```python
from fx import *

# 定义自定义事件处理
def on_custom_roto_complete(event):
    print(f"Roto完成: {event.data.get('shape_count')} 个形状")
    print(f"耗时: {event.data.get('duration')}秒")

addHook("rotoComplete", on_custom_roto_complete)

# 触发自定义事件
def batch_roto(shapes_config):
    import time
    start = time.time()

    roto = Node("RotoNode")
    session.addNode(roto)

    for cfg in shapes_config:
        shape = createObject("X-Spline")
        shape.name = cfg["name"]
        roto.addObject(shape)

    duration = time.time() - start

    # 发送自定义事件
    sendEvent("rotoComplete", {
        "node": roto.label,
        "shape_count": len(shapes_config),
        "duration": duration
    })
```

### 5.3 事件链

```python
from fx import *

# 事件链：跟踪完成 → 导出数据 → 通知AE
def on_tracking_done(event):
    print("跟踪完成，开始导出...")
    export_tracking_data(event.data["tracker_node"])
    sendEvent("exportDone", {"path": "D:/export/tracking.json"})

def on_export_done(event):
    print(f"导出完成: {event.data['path']}")
    sendEvent("notifyAE", {"path": event.data["path"]})

def on_notify_ae(event):
    print(f"通知AE: {event.data['path']}")

addHook("trackingComplete", on_tracking_done)
addHook("exportDone", on_export_done)
addHook("notifyAE", on_notify_ae)
```

---

## 六、事件对象

### 6.1 Event 类属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `type` | str | 事件类型名 |
| `time` | float | 事件时间戳 |
| `data` | dict | 事件数据 |
| `canceled` | bool | 是否已取消（可取消事件） |
| `node` | Node | 相关节点（节点事件） |
| `property` | Property | 相关属性（属性事件） |
| `frame` | int | 相关帧 |
| `session` | Session | 相关会话 |

### 6.2 Event 方法

| 方法 | 参数 | 说明 |
|------|------|------|
| `cancel()` | 无 | 取消事件（仅可取消事件） |
| `isCanceled()` | 无 | 检查是否已取消 |

### 6.3 取消事件示例

```python
from fx import *

# 阻止特定节点的删除
def prevent_delete(event):
    if event.node.label == "DoNotDelete":
        print(f"[BLOCK] 阻止删除节点: {event.node.label}")
        event.cancel()

addHook("nodeRemoved", prevent_delete)

# 阻止属性修改超出范围
def clamp_property(event):
    if event.property.name == "opacity":
        if event.newValue > 1.0:
            print("[CLAMP] 阻止 opacity 超过 1.0")
            event.cancel()

addHook("propertyChanged", clamp_property)
```

---

## 七、实战示例

### 7.1 自动命名节点

```python
from fx import *

node_counter = {"RotoNode": 0, "PaintNode": 0, "TrackerNode": 0}

def auto_name_node(event):
    if event.node.type in node_counter:
        node_counter[event.node.type] += 1
        prefix = event.node.type.replace("Node", "")
        event.node.label = f"{prefix}_{node_counter[event.node.type]:03d}"
        print(f"[AUTO] 重命名: {event.node.label}")

addHook("nodeAdded", auto_name_node)
```

### 7.2 渲染进度监控

```python
from fx import *

render_start_time = 0
total_frames = 0
current_frame = 0

def on_render_start(event):
    global render_start_time, total_frames, current_frame
    import time
    render_start_time = time.time()
    total_frames = event.endFrame - event.startFrame + 1
    current_frame = 0
    print(f"[RENDER] 开始渲染 {total_frames} 帧")

def on_render_frame(event):
    global current_frame
    current_frame += 1
    progress = current_frame / total_frames * 100
    print(f"\r[RENDER] 进度: {progress:.1f}% ({current_frame}/{total_frames})", end="")

def on_render_complete(event):
    import time
    duration = time.time() - render_start_time
    print(f"\n[RENDER] 完成，耗时 {duration:.1f}秒，平均 {duration/total_frames:.2f}秒/帧")

addHook("renderStarted", on_render_start)
addHook("renderFrame", on_render_frame)
addHook("renderCompleted", on_render_complete)
```

### 7.3 自动保存

```python
from fx import *

change_count = 0
AUTO_SAVE_THRESHOLD = 50

def on_any_change(event):
    global change_count
    change_count += 1
    if change_count >= AUTO_SAVE_THRESHOLD:
        proj = activeProject()
        if proj and proj.path:
            proj.save(proj.path)
            print(f"[AUTOSAVE] 已自动保存到 {proj.path}")
            change_count = 0

addHook("propertyChanged", on_any_change)
addHook("nodeAdded", on_any_change)
addHook("nodeRemoved", on_any_change)
addHook("shapeAdded", on_any_change)
addHook("shapeRemoved", on_any_change)
```

### 7.4 属性联动

```python
from fx import *

# 当 A 节点的 opacity 变化时，B 节点跟随变化
def link_opacity(event):
    if (event.node.label == "Master_Roto" and
        event.property.name == "alpha.opacity"):
        target = session.findNode("Slave_Roto")
        if target:
            target.property("alpha.opacity").setValue(
                event.newValue, event.frame
            )
            print(f"[LINK] 同步 opacity = {event.newValue}")

addHook("propertyChanged", link_opacity)
```

### 7.5 选择变化监控

```python
from fx import *

def on_selection_changed(event):
    selected = event.data.get("selected", [])
    print(f"[SELECT] 选中 {len(selected)} 个对象:")
    for obj in selected:
        print(f"  - {obj.label} ({obj.type})")

addHook("selectionChanged", on_selection_changed)
```

---

## 八、最佳实践

### 8.1 回调性能注意

```python
from fx import *

# 避免在频繁事件中做重操作
def on_frame_changed(event):
    # 错误：每帧都执行耗时操作
    # all_shapes = [s for n in session.nodes for s in n.objects]
    # process_shapes(all_shapes)

    # 正确：缓存数据，仅在需要时更新
    pass

# 将重操作放在低频事件中
def on_render_complete(event):
    # 渲染完成后才做数据汇总
    pass

addHook("frameChanged", on_frame_changed)
addHook("renderCompleted", on_render_complete)
```

### 8.2 回调清理

```python
from fx import *

registered_hooks = []

def register_hook(event_name, callback):
    """注册并记录 hook，便于后续清理"""
    hook_id = addHook(event_name, callback)
    registered_hooks.append(hook_id)
    return hook_id

def cleanup_hooks():
    """清理所有已注册的 hook"""
    for hook_id in registered_hooks:
        removeHook(hook_id)
    registered_hooks.clear()
    print(f"[CLEANUP] 已清理 {len(registered_hooks)} 个 hook")

# 使用
register_hook("nodeAdded", auto_name_node)
register_hook("propertyChanged", log_changes)

# 脚本退出时清理
# cleanup_hooks()
```

### 8.3 防止递归

```python
from fx import *

updating = False

def sync_property(event):
    global updating
    if updating:
        return  # 防止递归

    if event.property.name == "alpha.blur":
        updating = True
        try:
            target = session.findNode("SyncTarget")
            if target:
                target.property("alpha.blur").setValue(
                    event.newValue, event.frame
                )
        finally:
            updating = False

addHook("propertyChanged", sync_property)
```

### 8.4 事件调试

```python
from fx import *

def debug_event(event):
    """调试用：打印所有事件"""
    print(f"[EVENT] type={event.type}, time={event.time:.3f}")
    if hasattr(event, 'node') and event.node:
        print(f"  node: {event.node.label}")
    if hasattr(event, 'property') and event.property:
        print(f"  property: {event.property.name}")
    if hasattr(event, 'frame'):
        print(f"  frame: {event.frame}")
    if event.data:
        print(f"  data: {event.data}")

# 注册到所有事件
for evt in ["frameChanged", "nodeAdded", "nodeRemoved",
            "propertyChanged", "renderStarted", "renderCompleted"]:
    addHook(evt, debug_event)
```
