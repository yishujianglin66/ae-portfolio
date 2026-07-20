# Silhouette 节点系统完全手册

> 分类: 节点与合成系统
> 更新日期: 2026-07-11
> 概述: Silhouette 节点图系统完整说明,涵盖节点创建、连接、端口管理、数据流方向等核心机制。

## 目录
1. [节点系统概述](#1-节点系统概述)
2. [节点图架构](#2-节点图架构)
3. [节点类型分类](#3-节点类型分类)
4. [节点创建与销毁](#4-节点创建与销毁)
5. [节点连接管理](#5-节点连接管理)
6. [输入输出端口](#6-输入输出端口)
7. [数据流方向](#7-数据流方向)
8. [节点属性系统](#8-节点属性系统)
9. [节点查找与遍历](#9-节点查找与遍历)
10. [最佳实践](#10-最佳实践)

---

## 1. 节点系统概述

Silhouette 采用**有向无环图(DAG, Directed Acyclic Graph)**作为底层节点图模型。所有 Roto、Paint、跟踪、合成操作均以节点形式组织,节点之间通过端口连接形成数据流管道。

### 1.1 核心特征

| 特征 | 说明 |
|------|------|
| 图类型 | 有向无环图(DAG) |
| 求值模型 | 拉取式(Pull-based)按需计算 |
| 缓存策略 | 节点级缓存,自动失效 |
| 线程模型 | 多线程并行求值 |
| 数据类型 | 图像、遮罩、跟踪数据、形状 |

### 1.2 节点图与 Session 的关系

```
Project
  └── Session(合成容器)
        ├── Node: Input(源素材)
        ├── Node: RotoShape(形状)
        ├── Node: Tracker(跟踪)
        ├── Node: Composite(合成)
        └── Node: Output(输出)
```

每个 Session 持有一个独立的节点图,Session 之间互不影响。

## 2. 节点图架构

### 2.1 求值流程

Silhouette 采用**拉取式求值**:当用户请求某一帧的输出时,系统从输出节点反向追溯,依次请求上游节点,直到源输入节点。

```
[Output] ← [Composite] ← [Roto] ← [Input]
                ↑
            [Paint]
```

求值顺序(以 Composite 节点为例):
1. Output 节点请求 frame N
2. Composite 节点接收请求,转发给所有输入
3. Roto 节点计算遮罩
4. Input 节点返回源图像
5. Paint 节点应用绘制
6. Composite 合并结果返回 Output

### 2.2 缓存机制

每个节点维护一个帧缓存(LRU Cache),缓存策略:

| 缓存层 | 容量 | 失效条件 |
|--------|------|----------|
| 节点缓存 | 默认 20 帧 | 节点参数变化 |
| Session 缓存 | 内存上限 | 节点结构变化 |
| 磁盘缓存 | 用户配置 | 手动清除 |

## 3. 节点类型分类

### 3.1 节点类型总览

| 分类 | 节点类型 | type 字符串 | 说明 |
|------|----------|-------------|------|
| 输入 | Source | `Source` | 源素材输入 |
| 输入 | Clip | `Clip` | 剪辑片段 |
| Roto | RotoShape | `RotoShape` | Roto 形状节点 |
| Roto | RotoLayer | `RotoLayer` | Roto 图层 |
| Paint | PaintNode | `Paint` | 绘制节点 |
| 跟踪 | Tracker | `Tracker` | 跟踪节点 |
| 合成 | Composite | `Composite` | 合成节点 |
| 合成 | Matte | `Matte` | 遮罩节点 |
| 色彩 | Color | `Color` | 色彩校正 |
| 滤镜 | Filter | `Filter` | 滤镜效果 |
| 输出 | Output | `Output` | 输出节点 |
| 输出 | Export | `Export` | 导出节点 |

### 3.2 节点能力矩阵

| 节点类型 | 输入数 | 输出数 | 可关键帧 | 可屏蔽 |
|----------|--------|--------|----------|--------|
| Source | 0 | 1 | 否 | 否 |
| RotoShape | 1 | 1 | 是 | 是 |
| Paint | 1 | 1 | 是 | 是 |
| Tracker | 1 | 1 | 是 | 否 |
| Composite | 2+ | 1 | 是 | 否 |
| Matte | 1+ | 1 | 是 | 是 |
| Color | 1 | 1 | 是 | 是 |
| Filter | 1 | 1 | 是 | 是 |
| Output | 1 | 0 | 否 | 否 |

## 4. 节点创建与销毁

### 4.1 创建节点

```python
from fx import *

# 获取活动 Session
session = activeSession()
if session is None:
    print("没有活动 Session")
    exit()

# 创建 Roto 节点
roto = Node("RotoShape")
roto.label = "Foreground Roto"
session.addNode(roto)

# 创建合成节点
comp = Node("Composite")
comp.label = "Main Composite"
session.addNode(comp)

# 创建输出节点
out = Node("Output")
session.addNode(out)
```

### 4.2 节点参数初始化

```python
# 创建节点后立即设置参数
def create_color_node(session, lift=(-0.05, -0.05, -0.05), gamma=1.2, gain=1.1):
    node = Node("Color")
    node.label = "Primary CC"
    session.addNode(node)
    
    # 获取属性并设置
    lift_prop = node.property("lift")
    if lift_prop:
        lift_prop.setValue(lift, 0)
    
    gamma_prop = node.property("gamma")
    if gamma_prop:
        gamma_prop.setValue(gamma, 0)
    
    gain_prop = node.property("gain")
    if gain_prop:
        gain_prop.setValue(gain, 0)
    
    return node
```

### 4.3 销毁节点

```python
# 安全销毁节点
def safe_remove_node(node):
    # 先断开所有连接
    for port in node.inputs:
        port.disconnect()
    for port in node.outputs:
        port.disconnect()
    # 再移除节点
    node.remove()

# 批量清理
def remove_nodes_by_type(session, type_name):
    removed = 0
    for i in range(session.numNodes - 1, -1, -1):
        node = session.node(i)
        if node.type == type_name:
            safe_remove_node(node)
            removed += 1
    return removed
```

## 5. 节点连接管理

### 5.1 基本连接

```python
# 节点连接:source_node → target_node
# 调用方式:target_node.inputs[index].connect(source_node.outputs[0])

def connect_nodes(source, target, input_index=0):
    if input_index >= len(target.inputs):
        print(f"目标节点输入端口 {input_index} 不存在")
        return False
    if len(source.outputs) == 0:
        print("源节点没有输出端口")
        return False
    target.inputs[input_index].connect(source.outputs[0])
    return True
```

### 5.2 标准节点链构建

```python
def build_standard_pipeline(session, source_node):
    """构建标准处理管线: Source → Roto → Color → Composite → Output"""
    
    roto = Node("RotoShape")
    roto.label = "Roto"
    session.addNode(roto)
    
    color = Node("Color")
    color.label = "CC"
    session.addNode(color)
    
    comp = Node("Composite")
    comp.label = "Comp"
    session.addNode(comp)
    
    output = Node("Output")
    session.addNode(output)
    
    # 连接节点链
    connect_nodes(source_node, roto, 0)
    connect_nodes(roto, color, 0)
    connect_nodes(color, comp, 0)
    connect_nodes(comp, output, 0)
    
    return {"roto": roto, "color": color, "comp": comp, "output": output}
```

### 5.3 断开连接

```python
# 断开指定端口
def disconnect_port(node, port_index, is_input=True):
    ports = node.inputs if is_input else node.outputs
    if port_index < len(ports):
        ports[port_index].disconnect()
        return True
    return False

# 断开节点所有连接
def disconnect_all(node):
    for p in node.inputs:
        p.disconnect()
    for p in node.outputs:
        p.disconnect()
```

## 6. 输入输出端口

### 6.1 端口对象模型

每个节点拥有 `inputs` 和 `outputs` 两个数组,数组元素为 Port 对象。

| Port 属性/方法 | 说明 |
|----------------|------|
| `source` | 上游连接的 Node(只读) |
| `connect(target)` | 连接到目标 Port |
| `disconnect()` | 断开当前连接 |
| `isConnected()` | 是否已连接 |
| `node` | 所属节点 |

### 6.2 端口数量规则

```python
def inspect_node_ports(node):
    info = {
        "label": node.label,
        "type": node.type,
        "input_count": len(node.inputs),
        "output_count": len(node.outputs),
        "connected_inputs": sum(1 for p in node.inputs if p.isConnected()),
        "connected_outputs": sum(1 for p in node.outputs if p.isConnected()),
    }
    return info
```

### 6.3 端口连接验证

```python
def validate_connection(source, target, input_index):
    """验证连接是否合法"""
    # 1. 检查端口存在
    if len(source.outputs) == 0:
        return False, "源节点无输出端口"
    if input_index >= len(target.inputs):
        return False, "目标输入端口不存在"
    
    # 2. 检查循环引用
    if creates_cycle(source, target):
        return False, "连接将产生循环"
    
    # 3. 检查类型兼容(图像 vs 遮罩)
    # Silhouette 自动处理类型转换,通常无需手动检查
    
    return True, "连接合法"

def creates_cycle(source, target):
    """检查连接是否产生循环(DFS)"""
    visited = set()
    def visit(node):
        if node in visited:
            return False
        if node is source:
            return True
        visited.add(node)
        for p in node.inputs:
            if p.source and visit(p.source):
                return True
        return False
    return visit(target)
```

## 7. 数据流方向

### 7.1 数据流向约定

Silhouette 的数据流遵循**自上而下、从源到汇**的方向:

```
上游(源)                              下游(汇)
Source ─→ Roto ─→ Color ─→ Composite ─→ Output
```

- **inputs 数组**:接收上游数据,索引 0 通常是主输入
- **outputs 数组**:向下游发送数据

### 7.2 多输入节点的数据合并

Composite 节点拥有多个输入端口,索引含义:

| 输入索引 | 语义 | 说明 |
|----------|------|------|
| 0 | Background | 背景层 |
| 1 | Foreground | 前景层 |
| 2 | Matte | 遮罩层(可选) |
| 3+ | 额前景层 | 多层合成 |

```python
def setup_composite_with_matte(session, bg, fg, matte):
    comp = Node("Composite")
    session.addNode(comp)
    
    # 背景连到 0,前景连到 1,遮罩连到 2
    comp.inputs[0].connect(bg.outputs[0])
    comp.inputs[1].connect(fg.outputs[0])
    comp.inputs[2].connect(matte.outputs[0])
    
    return comp
```

### 7.3 分支与合并

```python
def create_branch_merge(session, source):
    """
    分支:Source 同时驱动 Roto 和 Color
    合并:两者结果汇入 Composite
    """
    roto = Node("RotoShape")
    color = Node("Color")
    comp = Node("Composite")
    
    session.addNode(roto)
    session.addNode(color)
    session.addNode(comp)
    
    # 分支:同一个 source 输出到两个节点
    roto.inputs[0].connect(source.outputs[0])
    color.inputs[0].connect(source.outputs[0])
    
    # 合并:roto 作为 matte,color 处理后的图像作为前景
    comp.inputs[0].connect(source.outputs[0])   # 背景
    comp.inputs[1].connect(color.outputs[0])    # 前景
    comp.inputs[2].connect(roto.outputs[0])     # 遮罩
    
    return comp
```

## 8. 节点属性系统

### 8.1 属性类型

| 类型字符串 | Python 类型 | 说明 |
|------------|-------------|------|
| `int` | int | 整数 |
| `float` | float | 浮点数 |
| `double` | float | 双精度 |
| `bool` | bool | 布尔值 |
| `string` | str | 字符串 |
| `color` | tuple(r,g,b,a) | 颜色 |
| `curve` | AnimationCurve | 动画曲线 |
| `menu` | int(索引) | 菜单选项 |

### 8.2 属性遍历

```python
def dump_node_properties(node):
    print(f"=== {node.label} ({node.type}) ===")
    for name in node.properties:
        prop = node.property(name)
        val = prop.value
        print(f"  {name}: type={prop.type}, value={val}")

# 示例输出:
# === Primary CC (Color) ===
#   lift: type=color, value=(-0.05, -0.05, -0.05, 0.0)
#   gamma: type=float, value=1.2
#   gain: type=color, value=(1.1, 1.1, 1.1, 0.0)
```

### 8.3 属性关键帧

```python
def animate_gamma(node, keyframes):
    """为 gamma 属性添加关键帧
    keyframes: [(frame, value), ...]
    """
    prop = node.property("gamma")
    if prop is None:
        return False
    for frame, value in keyframes:
        prop.setValue(value, frame)
    return True

# 使用:gamma 从 1.0 渐变到 1.5
animate_gamma(color_node, [(1, 1.0), (30, 1.2), (60, 1.5)])
```

## 9. 节点查找与遍历

### 9.1 按标签查找

```python
def find_node_by_label(session, label):
    for i in range(session.numNodes):
        node = session.node(i)
        if node.label == label:
            return node
    return None

def find_nodes_by_type(session, type_name):
    return [session.node(i) for i in range(session.numNodes)
            if session.node(i).type == type_name]
```

### 9.2 图遍历算法

```python
def traverse_downstream(node, visited=None):
    """从指定节点向下游遍历"""
    if visited is None:
        visited = set()
    if id(node) in visited:
        return
    visited.add(id(node))
    yield node
    for port in node.outputs:
        if port.source:
            yield from traverse_downstream(port.source, visited)

def traverse_upstream(node, visited=None):
    """从指定节点向上游遍历"""
    if visited is None:
        visited = set()
    if id(node) in visited:
        return
    visited.add(id(node))
    yield node
    for port in node.inputs:
        if port.source:
            yield from traverse_upstream(port.source, visited)

def topological_sort(session):
    """拓扑排序:返回求值顺序(源→汇)"""
    in_degree = {}
    nodes = [session.node(i) for i in range(session.numNodes)]
    for n in nodes:
        in_degree[id(n)] = 0
    for n in nodes:
        for p in n.inputs:
            if p.source:
                in_degree[id(n)] += 1
    
    queue = [n for n in nodes if in_degree[id(n)] == 0]
    result = []
    while queue:
        n = queue.pop(0)
        result.append(n)
        for p in n.outputs:
            if p.source:
                in_degree[id(p.source)] -= 1
                if in_degree[id(p.source)] == 0:
                    queue.append(p.source)
    return result
```

## 10. 最佳实践

### 10.1 节点命名规范

| 前缀 | 用途 | 示例 |
|------|------|------|
| `SRC_` | 源素材 | `SRC_Plate_v01` |
| `ROTO_` | Roto 节点 | `ROTO_Hair_Main` |
| `PNT_` | Paint 节点 | `PNT_Cleanup_Face` |
| `TRK_` | 跟踪节点 | `TRK_Feature_Tracker` |
| `CC_` | 色彩校正 | `CC_Primary_Grade` |
| `CMP_` | 合成 | `CMP_Beauty_Pass` |
| `OUT_` | 输出 | `OUT_Final_EXR` |

### 10.2 节点图组织原则

1. **保持线性结构**:除非必要,避免复杂分支
2. **合理命名**:所有节点使用有意义的 label
3. **分组归类**:相关节点放在同一 RotoLayer 下
4. **避免冗余**:相同处理的节点不要重复创建
5. **及时清理**:无连接的孤立节点应及时删除

### 10.3 性能建议

```python
# 批量操作时暂停求值
beginUndo("Batch Node Creation")
try:
    # 在此处创建/修改大量节点
    for i in range(100):
        n = Node("RotoShape")
        session.addNode(n)
finally:
    endUndo()

# 避免在循环中频繁访问 property
# 错误:
for i in range(1000):
    node.property("gamma").setValue(1.0 + i*0.001, i)

# 正确:缓存属性引用
gamma_prop = node.property("gamma")
for i in range(1000):
    gamma_prop.setValue(1.0 + i*0.001, i)
```

### 10.4 调试技巧

```python
def print_node_graph(session):
    """打印完整节点图结构"""
    print(f"\n=== Session: {session.label} ===")
    print(f"Nodes: {session.numNodes}")
    for i in range(session.numNodes):
        n = session.node(i)
        inputs_str = ", ".join(
            f"[{j}]→{p.source.label if p.source else 'None'}"
            for j, p in enumerate(n.inputs)
        )
        print(f"  {n.label}({n.type}) in:[{inputs_str}]")

def find_disconnected_nodes(session):
    """查找孤立节点(无输入也无输出连接)"""
    orphans = []
    for i in range(session.numNodes):
        n = session.node(i)
        has_in = any(p.isConnected() for p in n.inputs)
        has_out = any(p.isConnected() for p in n.outputs)
        if not has_in and not has_out and n.type not in ("Source", "Clip"):
            orphans.append(n)
    return orphans
```

---

## 附录:节点类型速查表

| 任务 | 推荐节点 | 备选 |
|------|----------|------|
| 抠像遮罩 | RotoShape | Matte |
| 图像修复 | Paint | — |
| 运动跟踪 | Tracker | PlanarTracker |
| 色彩校正 | Color | — |
| 模糊锐化 | Filter | — |
| 多层合成 | Composite | — |
| 通道操作 | Matte | ChannelCopy |
| 最终输出 | Output | Export |

> **提示**:所有节点操作均支持 Undo/Redo,建议在批量操作前调用 `beginUndo()` 包裹,保证可回退。
