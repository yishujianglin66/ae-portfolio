# Silhouette 节点连接与数据流

> 分类: 节点与合成系统
> 更新日期: 2026-07-11
> 概述: inputs/outputs 数组详解、连接规则、数据类型系统、端口限制与数据流控制。

## 目录
1. [inputs/outputs 数组](#1-inputsoutputs-数组)
2. [连接规则](#2-连接规则)
3. [数据类型系统](#3-数据类型系统)
4. [端口限制](#4-端口限制)
5. [连接管理 API](#5-连接管理-api)
6. [数据流控制](#6-数据流控制)
7. [常见连接模式](#7-常见连接模式)
8. [故障排查](#8-故障排查)

---

## 1. inputs/outputs 数组

### 1.1 数组结构

每个节点拥有两个 Port 数组:

```python
node.inputs   # 输入端口数组(接收数据)
node.outputs  # 输出端口数组(发送数据)
```

### 1.2 Port 对象

| 属性/方法 | 类型 | 说明 |
|-----------|------|------|
| `source` | Node/None | 上游连接的节点(只读) |
| `connect(target_port)` | method | 连接到目标端口 |
| `disconnect()` | method | 断开当前连接 |
| `isConnected()` | method | 返回是否已连接 |
| `node` | Node | 所属节点 |

### 1.3 端口数量

```python
def get_port_info(node):
    return {
        "label": node.label,
        "type": node.type,
        "inputs": len(node.inputs),
        "outputs": len(node.outputs),
        "connected_inputs": sum(1 for p in node.inputs if p.isConnected()),
        "connected_outputs": sum(1 for p in node.outputs if p.isConnected()),
    }
```

## 2. 连接规则

### 2.1 连接方向

连接操作总是**从目标(下游)节点的输入端口发起**,连接到源(上游)节点的输出端口。

```python
# 正确:从下游节点的 input 发起
target.inputs[0].connect(source.outputs[0])

# 错误:不能从上游 output 发起
# source.outputs[0].connect(target.inputs[0])  # 不支持
```

### 2.2 一对一连接

每个输入端口只能连接一个源:

```python
# 第一次连接
node_a.inputs[0].connect(source.outputs[0])

# 第二次连接会覆盖第一次
node_a.inputs[0].connect(other.outputs[0])
# 现在 node_a.inputs[0].source == other
```

### 2.3 一对多输出

一个输出端口可连接到多个下游输入:

```python
# 一个 source 同时驱动多个节点
source.outputs[0] → node_a.inputs[0]
source.outputs[0] → node_b.inputs[0]
source.outputs[0] → node_c.inputs[0]
```

```python
# 实现一对多连接
def connect_to_many(source, targets, input_index=0):
    for t in targets:
        if input_index < len(t.inputs):
            t.inputs[input_index].connect(source.outputs[0])
```

### 2.4 禁止循环连接

DAG 不允许循环引用:

```python
def would_create_cycle(source, target):
    """检查 source→target 连接是否产生循环"""
    visited = set()
    
    def visit(node):
        if node is source:
            return True
        if id(node) in visited:
            return False
        visited.add(id(node))
        for p in node.inputs:
            if p.source and visit(p.source):
                return True
        return False
    
    return visit(target)

# 检查后再连接
if not would_create_cycle(source, target):
    target.inputs[0].connect(source.outputs[0])
```

## 3. 数据类型系统

### 3.1 数据类型分类

Silhouette 节点间传递的数据类型:

| 类型 | 说明 | 典型节点 |
|------|------|----------|
| Image | 图像数据(RGBA 像素) | Source, Color, Composite |
| Matte | 遮罩数据(单通道灰度) | RotoShape, Matte |
| Shape | 矢量形状数据 | RotoShape |
| Track | 跟踪点数据 | Tracker |
| Paint | 绘制笔触数据 | Paint |

### 3.2 类型兼容性

| 源类型 | 目标输入接受类型 | 备注 |
|--------|------------------|------|
| Image | Image, Matte | Image 可作为 Matte 使用(取亮度) |
| Matte | Matte, Image(作为 Alpha) | Matte 可附加到 Image 的 Alpha |
| Shape | Shape | 仅在 Roto 节点间传递 |
| Track | Track | 跟踪数据特殊传递 |

### 3.3 自动转换

Silhouette 在连接时会自动处理部分类型转换:

```python
# Image 节点输出连接到 Matte 输入端口
# 系统自动取 Image 的 Alpha 或亮度作为 Matte
roto.inputs[0].connect(color_node.outputs[0])  # 自动转换
```

## 4. 端口限制

### 4.1 各节点端口数

| 节点类型 | 输入端口数 | 输出端口数 | 备注 |
|----------|-----------|-----------|------|
| Source | 0 | 1 | 纯输出 |
| Clip | 0 | 1 | 纯输出 |
| RotoShape | 1 | 1 | 标准 |
| Paint | 1 | 1 | 标准 |
| Tracker | 1 | 1 | 标准 |
| Color | 1 | 1 | 标准 |
| Filter | 1 | 1 | 标准 |
| Matte | 1-4 | 1 | 可变输入 |
| Composite | 2-8 | 1 | 多输入 |
| Output | 1 | 0 | 纯输入 |
| Export | 1 | 0 | 纯输入 |

### 4.2 端口索引语义

#### Composite 节点

| 索引 | 语义 | 是否必需 |
|------|------|----------|
| 0 | Background | 是 |
| 1 | Foreground A | 是 |
| 2 | Matte(遮罩) | 否 |
| 3 | Foreground B | 否 |
| 4+ | 额前景层 | 否 |

#### Matte 节点

| 索引 | 语义 | 用途 |
|------|------|------|
| 0 | 主输入 | 待处理图像 |
| 1 | Matte A | 第一遮罩 |
| 2 | Matte B | 第二遮罩(用于运算) |
| 3 | Matte C | 第三遮罩(可选) |

### 4.3 连接前检查

```python
def safe_connect(source, target, input_index=0):
    """安全连接,带完整检查"""
    # 检查源是否有输出
    if len(source.outputs) == 0:
        print(f"错误:{source.label} 无输出端口")
        return False
    
    # 检查目标输入索引
    if input_index >= len(target.inputs):
        print(f"错误:{target.label} 输入端口 {input_index} 不存在")
        return False
    
    # 检查循环
    if would_create_cycle(source, target):
        print(f"错误:连接 {source.label} → {target.label} 产生循环")
        return False
    
    # 执行连接
    target.inputs[input_index].connect(source.outputs[0])
    return True
```

## 5. 连接管理 API

### 5.1 标准连接函数

```python
def connect(source, target, input_index=0):
    """标准连接函数"""
    target.inputs[input_index].connect(source.outputs[0])

def disconnect_input(node, input_index):
    """断开指定输入"""
    if input_index < len(node.inputs):
        node.inputs[input_index].disconnect()

def disconnect_all_inputs(node):
    """断开所有输入"""
    for p in node.inputs:
        p.disconnect()

def disconnect_all_outputs(node):
    """断开所有输出(实际上是断开下游节点的对应输入)"""
    for p in node.outputs:
        # 遍历所有下游节点,断开它们的输入
        p.disconnect()

def is_connected(source, target, input_index=0):
    """检查是否已连接"""
    if input_index >= len(target.inputs):
        return False
    return target.inputs[input_index].source is source
```

### 5.2 批量连接

```python
def connect_chain(nodes):
    """将节点列表顺序连接成链"""
    for i in range(len(nodes) - 1):
        if not safe_connect(nodes[i], nodes[i+1], 0):
            return False
    return True

def connect_tree(root, children, input_index=0):
    """将根节点连接到多个子节点"""
    for child in children:
        if not safe_connect(root, child, input_index):
            return False
    return True
```

### 5.3 连接信息查询

```python
def get_upstream_nodes(node):
    """获取所有上游节点"""
    result = []
    visited = set()
    
    def collect(n):
        if id(n) in visited:
            return
        visited.add(id(n))
        for p in n.inputs:
            if p.source:
                result.append(p.source)
                collect(p.source)
    
    collect(node)
    return result

def get_downstream_nodes(node):
    """获取所有下游节点"""
    result = []
    visited = set()
    
    def collect(n):
        if id(n) in visited:
            return
        visited.add(id(n))
        for p in n.outputs:
            if p.source:
                result.append(p.source)
                collect(p.source)
    
    collect(node)
    return result

def get_input_sources(node):
    """获取直接上游节点列表(按输入端口顺序)"""
    return [p.source for p in node.inputs if p.source]
```

## 6. 数据流控制

### 6.1 求值触发

数据流由**输出节点的请求**触发:

```python
# 当用户查看 frame N 时:
# 1. Output 节点请求 frame N
# 2. 向上游传播请求
# 3. 上游节点计算并返回结果
# 4. 结果沿连接链返回到 Output
```

### 6.2 帧范围与数据流

```python
def get_effective_frame_range(session):
    """获取有效帧范围"""
    # 通常由 Source 节点的素材决定
    sources = [session.node(i) for i in range(session.numNodes)
               if session.node(i).type == "Source"]
    if not sources:
        return 0, 0
    
    start = min(s.property("startFrame").value for s in sources)
    end = max(s.property("endFrame").value for s in sources)
    return start, end
```

### 6.3 缓存与失效

```python
def invalidate_downstream_cache(node):
    """失效节点及其下游的所有缓存"""
    # 修改节点参数后,Silhouette 自动失效相关缓存
    # 如需手动失效(例如修改了外部数据):
    downstream = get_downstream_nodes(node)
    for n in [node] + downstream:
        # 触发属性变更以失效缓存
        # (实际 API 可能提供显式的 invalidate 方法)
        pass
```

## 7. 常见连接模式

### 7.1 串行链

```
A → B → C → D
```

```python
def serial_chain(*nodes):
    for i in range(len(nodes) - 1):
        safe_connect(nodes[i], nodes[i+1], 0)
```

### 7.2 并行分支

```
       ┌→ B
A ─────┼→ C
       └→ D
```

```python
def parallel_branches(source, targets):
    for t in targets:
        safe_connect(source, t, 0)
```

### 7.3 多源合并

```
A ─┐
B ─┼→ D
C ─┘
```

```python
def merge_sources(target, sources, start_index=0):
    for i, s in enumerate(sources):
        safe_connect(s, target, start_index + i)
```

### 7.4 反馈式(伪反馈)

DAG 不支持真反馈,但可通过**帧偏移**模拟:

```
A(frame N) → B → C
A(frame N-1) ──→ C(作为参考)
```

```python
# 使用 TimeShift 节点实现帧偏移
time_shift = Node("TimeShift")
time_shift.label = "REF_Previous_Frame"
time_shift.property("offset").setValue(-1, 0)
# 连接到 C 的参考输入
```

## 8. 故障排查

### 8.1 常见连接问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 输出黑屏 | 主输入未连接 | 检查 inputs[0] 是否连接 |
| 遮罩无效 | Matte 输入端口错误 | 确认连接到正确的 matte 端口 |
| 循环报错 | 存在回路 | 检查节点图,移除回路 |
| 性能骤降 | 节点链过深 | 合并节点,使用缓存 |

### 8.2 诊断脚本

```python
def diagnose_connections(session):
    """诊断所有连接问题"""
    issues = []
    
    for i in range(session.numNodes):
        n = session.node(i)
        
        # 检查主输入(Source/Clip 除外)
        if n.type not in ("Source", "Clip", "Output"):
            if len(n.inputs) == 0 or not n.inputs[0].isConnected():
                issues.append(f"[警告] {n.label}({n.type}) 主输入未连接")
        
        # 检查 Output 节点是否连接
        if n.type == "Output":
            if not n.inputs[0].isConnected():
                issues.append(f"[错误] Output 节点 {n.label} 未连接输入")
        
        # 检查 Composite 的必要输入
        if n.type == "Composite":
            if not n.inputs[0].isConnected():
                issues.append(f"[错误] {n.label} 缺少背景输入")
            if len(n.inputs) > 1 and not n.inputs[1].isConnected():
                issues.append(f"[警告] {n.label} 缺少前景输入")
    
    return issues

def find_orphan_nodes(session):
    """查找孤立节点"""
    orphans = []
    for i in range(session.numNodes):
        n = session.node(i)
        has_in = any(p.isConnected() for p in n.inputs)
        has_out = any(p.isConnected() for p in n.outputs)
        if not has_in and not has_out and n.type not in ("Source", "Clip"):
            orphans.append(n)
    return orphans
```

### 8.3 连接可视化

```python
def print_connection_map(session):
    """打印连接关系图"""
    print(f"\n{'='*60}")
    print(f"Session: {session.label} ({session.numNodes} nodes)")
    print(f"{'='*60}")
    
    for i in range(session.numNodes):
        n = session.node(i)
        print(f"\n[{i}] {n.label} ({n.type})")
        
        for j, p in enumerate(n.inputs):
            src = p.source.label if p.source else "—"
            print(f"  in[{j}] ← {src}")
        
        downstream = []
        for k in range(session.numNodes):
            other = session.node(k)
            for p in other.inputs:
                if p.source is n:
                    downstream.append(other.label)
        
        if downstream:
            print(f"  out → {', '.join(downstream)}")
```

### 8.4 连接备份与恢复

```python
def backup_connections(session):
    """备份所有连接关系"""
    backup = []
    for i in range(session.numNodes):
        n = session.node(i)
        for j, p in enumerate(n.inputs):
            if p.source:
                backup.append({
                    "target_label": n.label,
                    "input_index": j,
                    "source_label": p.source.label
                })
    return backup

def restore_connections(session, backup):
    """从备份恢复连接"""
    label_to_node = {
        session.node(i).label: session.node(i)
        for i in range(session.numNodes)
    }
    
    for conn in backup:
        target = label_to_node.get(conn["target_label"])
        source = label_to_node.get(conn["source_label"])
        if target and source:
            safe_connect(source, target, conn["input_index"])
```

---

## 附录:连接速查表

| 操作 | 代码 |
|------|------|
| 连接 | `target.inputs[i].connect(source.outputs[0])` |
| 断开 | `target.inputs[i].disconnect()` |
| 检查 | `port.isConnected()` |
| 获取源 | `port.source` |
| 输入数 | `len(node.inputs)` |
| 输出数 | `len(node.outputs)` |

> **提示**:复杂的节点图建议先用 `print_connection_map()` 打印结构,确认无误后再执行批量操作。
