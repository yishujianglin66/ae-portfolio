# Silhouette 管线与合成工作流

> 分类: 节点与合成系统
> 更新日期: 2026-07-11
> 概述: Pipeline 概念、节点链构建、分支合并策略与合成工作流完整说明。

## 目录
1. [Pipeline 概念](#1-pipeline-概念)
2. [节点链构建](#2-节点链构建)
3. [分支与合并](#3-分支与合并)
4. [合成策略](#4-合成策略)
5. [常见工作流模板](#5-常见工作流模板)
6. [管线优化](#6-管线优化)
7. [错误处理](#7-错误处理)
8. [最佳实践](#8-最佳实践)

---

## 1. Pipeline 概念

### 1.1 什么是 Pipeline

Pipeline(管线)是指将图像处理任务分解为有序的节点链,每个节点完成一项特定操作,数据依次流经各节点完成处理。

```
源图像 → 跟踪 → Roto → 色彩校正 → 合成 → 输出
```

### 1.2 Pipeline 分类

| 类型 | 描述 | 典型场景 |
|------|------|----------|
| 线性 Pipeline | 单链结构,数据顺序流动 | 简单色彩校正 |
| 分支 Pipeline | 一对多结构,并行处理 | 多通道输出 |
| 合并 Pipeline | 多对一结构,结果合成 | 多层合成 |
| 混合 Pipeline | 包含分支和合并 | 复杂合成镜头 |

### 1.3 Pipeline 设计原则

1. **单一职责**:每个节点只做一件事
2. **数据流清晰**:避免回流和循环
3. **可重用性**:常用结构封装为模板
4. **可调试性**:关键节点留出查看点
5. **性能优先**:重计算节点尽量靠后

## 2. 节点链构建

### 2.1 基础链构建

```python
from fx import *

def build_basic_chain(session, source_node):
    """构建基础处理链:Source → Roto → Output"""
    roto = Node("RotoShape")
    roto.label = "Main_Roto"
    session.addNode(roto)
    
    output = Node("Output")
    session.addNode(output)
    
    # 连接
    roto.inputs[0].connect(source_node.outputs[0])
    output.inputs[0].connect(roto.outputs[0])
    
    return roto, output
```

### 2.2 复合链构建

```python
def build_complex_chain(session, source):
    """
    构建复合处理链:
    Source → Tracker → Roto → Paint → Color → Composite → Output
    """
    nodes = {}
    
    # 创建所有节点
    node_specs = [
        ("tracker", "Tracker", "TRK_Planar"),
        ("roto", "RotoShape", "ROTO_Main"),
        ("paint", "Paint", "PNT_Cleanup"),
        ("color", "Color", "CC_Primary"),
        ("comp", "Composite", "CMP_Final"),
        ("output", "Output", "OUT_Final"),
    ]
    
    for key, ntype, label in node_specs:
        n = Node(ntype)
        n.label = label
        session.addNode(n)
        nodes[key] = n
    
    # 顺序连接
    chain = [source, nodes["tracker"], nodes["roto"], nodes["paint"],
             nodes["color"], nodes["comp"], nodes["output"]]
    
    for i in range(len(chain) - 1):
        chain[i+1].inputs[0].connect(chain[i].outputs[0])
    
    return nodes
```

### 2.3 动态链构建

```python
def build_dynamic_chain(session, source, node_types):
    """根据类型列表动态构建节点链"""
    prev = source
    created = []
    for i, ntype in enumerate(node_types):
        n = Node(ntype)
        n.label = f"{ntype}_{i:02d}"
        session.addNode(n)
        if prev and len(n.inputs) > 0:
            n.inputs[0].connect(prev.outputs[0])
        created.append(n)
        prev = n
    return created
```

## 3. 分支与合并

### 3.1 分支结构

分支允许一个节点的输出同时驱动多个下游节点。

```python
def create_branch(session, source, branch_count=2):
    """创建 N 路分支"""
    branches = []
    for i in range(branch_count):
        n = Node("RotoShape")
        n.label = f"Branch_{i}"
        session.addNode(n)
        n.inputs[0].connect(source.outputs[0])
        branches.append(n)
    return branches
```

### 3.2 合并结构

```python
def merge_to_composite(session, layers):
    """将多个层合并到 Composite 节点"""
    comp = Node("Composite")
    comp.label = "Merge_All"
    session.addNode(comp)
    
    # 第一层为背景
    if layers:
        comp.inputs[0].connect(layers[0].outputs[0])
    
    # 其余层依次叠加
    for i, layer in enumerate(layers[1:], start=1):
        if i < len(comp.inputs):
            comp.inputs[i].connect(layer.outputs[0])
    
    return comp
```

### 3.3 典型分支合并模式

```
                    ┌─→ Roto_FG ─────────┐
Source ─┬───────────┤                     ├─→ Composite ─→ Output
        │           └─→ Color_FG ────────┘
        │
        └─→ Roto_BG ─→ Color_BG ─────────┘
```

```python
def build_branch_merge_pattern(session, source):
    # 分支1:前景处理
    roto_fg = Node("RotoShape")
    roto_fg.label = "ROTO_FG"
    session.addNode(roto_fg)
    roto_fg.inputs[0].connect(source.outputs[0])
    
    color_fg = Node("Color")
    color_fg.label = "CC_FG"
    session.addNode(color_fg)
    color_fg.inputs[0].connect(roto_fg.outputs[0])
    
    # 分支2:背景处理
    roto_bg = Node("RotoShape")
    roto_bg.label = "ROTO_BG"
    session.addNode(roto_bg)
    roto_bg.inputs[0].connect(source.outputs[0])
    
    color_bg = Node("Color")
    color_bg.label = "CC_BG"
    session.addNode(color_bg)
    color_bg.inputs[0].connect(roto_bg.outputs[0])
    
    # 合并
    comp = Node("Composite")
    comp.label = "CMP_Merge"
    session.addNode(comp)
    comp.inputs[0].connect(color_bg.outputs[0])  # 背景
    comp.inputs[1].connect(color_fg.outputs[0])  # 前景
    comp.inputs[2].connect(roto_fg.outputs[0])   # 遮罩
    
    output = Node("Output")
    session.addNode(output)
    output.inputs[0].connect(comp.outputs[0])
    
    return comp
```

## 4. 合成策略

### 4.1 合成模式分类

| 策略 | 适用场景 | 关键参数 |
|------|----------|----------|
| Normal | 常规图层叠加 | opacity |
| Over | 前景叠在背景上 | opacity, matte |
| Under | 背景叠在前景下 | opacity, matte |
| Add | 加法混合(光效) | opacity |
| Screen | 屏幕混合(高光) | opacity |
| Multiply | 正片叠底(阴影) | opacity |
| Mask | 使用遮罩限制 | matte input |
| Stencil | 遮罩裁切 | matte input |

### 4.2 合成参数详解

```python
def configure_composite(comp_node, mode="over", opacity=1.0,
                         invert_matte=False, premultiply=True):
    """配置 Composite 节点参数"""
    mode_prop = comp_node.property("operation")
    if mode_prop:
        mode_prop.setValue(mode, 0)
    
    opacity_prop = comp_node.property("opacity")
    if opacity_prop:
        opacity_prop.setValue(opacity, 0)
    
    invert_prop = comp_node.property("invertMatte")
    if invert_prop:
        invert_prop.setValue(invert_matte, 0)
    
    premul_prop = comp_node.property("premultiply")
    if premul_prop:
        premul_prop.setValue(premultiply, 0)
```

### 4.3 多层合成策略

```python
def multilayer_composite(session, layers_config):
    """
    多层合成
    layers_config: [
        {"node": bg_node, "mode": "normal", "opacity": 1.0},
        {"node": fg_node, "mode": "over", "opacity": 0.8, "matte": matte_node},
        ...
    ]
    """
    if not layers_config:
        return None
    
    # 第一层作为背景
    result = layers_config[0]["node"]
    
    for layer in layers_config[1:]:
        comp = Node("Composite")
        comp.label = f"CMP_{layer.get('name', 'layer')}"
        session.addNode(comp)
        
        comp.inputs[0].connect(result.outputs[0])
        comp.inputs[1].connect(layer["node"].outputs[0])
        if "matte" in layer and len(comp.inputs) > 2:
            comp.inputs[2].connect(layer["matte"].outputs[0])
        
        configure_composite(comp, mode=layer.get("mode", "over"),
                          opacity=layer.get("opacity", 1.0))
        result = comp
    
    return result
```

## 5. 常见工作流模板

### 5.1 Roto + 合成工作流

```python
def roto_composite_workflow(session, source):
    """标准 Roto 合成工作流"""
    # Roto 节点生成遮罩
    roto = Node("RotoShape")
    roto.label = "ROTO_Subject"
    session.addNode(roto)
    roto.inputs[0].connect(source.outputs[0])
    
    # Composite 节点应用遮罩
    comp = Node("Composite")
    comp.label = "CMP_Apply_Matte"
    session.addNode(comp)
    comp.inputs[0].connect(source.outputs[0])     # 原图作为背景
    comp.inputs[1].connect(source.outputs[0])     # 原图作为前景
    comp.inputs[2].connect(roto.outputs[0])       # Roto 作为遮罩
    
    output = Node("Output")
    session.addNode(output)
    output.inputs[0].connect(comp.outputs[0])
    
    return roto, comp, output
```

### 5.2 跟踪驱动 Roto 工作流

```python
def tracked_roto_workflow(session, source):
    """跟踪数据驱动 Roto 的工作流"""
    tracker = Node("Tracker")
    tracker.label = "TRK_Feature"
    session.addNode(tracker)
    tracker.inputs[0].connect(source.outputs[0])
    
    roto = Node("RotoShape")
    roto.label = "ROTO_Tracked"
    session.addNode(roto)
    roto.inputs[0].connect(source.outputs[0])
    
    # 将跟踪数据应用到 Roto 节点
    # (实际应用中通过节点内部数据流自动传递)
    
    output = Node("Output")
    session.addNode(output)
    output.inputs[0].connect(roto.outputs[0])
    
    return tracker, roto
```

### 5.3 Paint 修复工作流

```python
def paint_cleanup_workflow(session, source):
    """Paint 修复 + Roto 遮罩工作流"""
    roto = Node("RotoShape")
    roto.label = "ROTO_Cleanup_Area"
    session.addNode(roto)
    roto.inputs[0].connect(source.outputs[0])
    
    paint = Node("Paint")
    paint.label = "PNT_Cleanup"
    session.addNode(paint)
    paint.inputs[0].connect(source.outputs[0])
    
    # 使用 Roto 限制 Paint 范围
    comp = Node("Composite")
    comp.label = "CMP_Limit_Paint"
    session.addNode(comp)
    comp.inputs[0].connect(source.outputs[0])     # 原图背景
    comp.inputs[1].connect(paint.outputs[0])      # Paint 结果
    comp.inputs[2].connect(roto.outputs[0])       # 限制范围
    
    output = Node("Output")
    session.addNode(output)
    output.inputs[0].connect(comp.outputs[0])
    
    return paint, comp
```

## 6. 管线优化

### 6.1 缓存利用

```python
def optimize_pipeline_order(nodes):
    """
    优化节点顺序,将重计算节点后置
    使缓存命中率最大化
    """
    # 按"计算成本"排序:轻量操作在前,重操作在后
    cost = {
        "Source": 0, "RotoShape": 1, "Tracker": 2,
        "Color": 3, "Filter": 4, "Paint": 5, "Composite": 6
    }
    return sorted(nodes, key=lambda n: cost.get(n.type, 99))
```

### 6.2 并行处理

```python
def parallel_branches(session, source, branch_defs):
    """
    创建并行分支以利用多线程求值
    branch_defs: [("branch1", "RotoShape"), ("branch2", "Color"), ...]
    """
    branches = []
    for name, ntype in branch_defs:
        n = Node(ntype)
        n.label = name
        session.addNode(n)
        n.inputs[0].connect(source.outputs[0])
        branches.append(n)
    return branches
```

## 7. 错误处理

### 7.1 连接验证

```python
def safe_connect(session, source, target, input_index=0):
    """安全连接,带完整检查"""
    try:
        # 检查节点是否在 session 中
        nodes_in_session = [session.node(i) for i in range(session.numNodes)]
        if source not in nodes_in_session or target not in nodes_in_session:
            raise ValueError("节点不在当前 Session 中")
        
        # 检查端口
        if len(source.outputs) == 0:
            raise ValueError(f"源节点 {source.label} 无输出端口")
        if input_index >= len(target.inputs):
            raise ValueError(f"目标节点 {target.label} 输入端口 {input_index} 不存在")
        
        # 检查循环
        if check_cycle(source, target):
            raise ValueError("连接将产生循环引用")
        
        # 执行连接
        target.inputs[input_index].connect(source.outputs[0])
        return True
    except Exception as e:
        print(f"连接失败: {e}")
        return False

def check_cycle(source, target):
    visited = set()
    def dfs(n):
        if n is source:
            return True
        if id(n) in visited:
            return False
        visited.add(id(n))
        for p in n.inputs:
            if p.source and dfs(p.source):
                return True
        return False
    return dfs(target)
```

### 7.2 管线完整性检查

```python
def validate_pipeline(session, output_node):
    """验证从 Output 节点向上游的管线完整性"""
    issues = []
    visited = set()
    
    def check(node):
        if id(node) in visited:
            return
        visited.add(id(node))
        
        # 检查必要的输入是否已连接
        for i, p in enumerate(node.inputs):
            if not p.isConnected() and i == 0:
                issues.append(f"节点 {node.label} 主输入未连接")
            if p.source:
                check(p.source)
    
    check(output_node)
    return issues
```

## 8. 最佳实践

### 8.1 Pipeline 命名约定

```
[阶段]_[对象]_[描述]
例如:
  SRC_Plate_v01      源素材
  TRK_Face_Main      面部跟踪
  ROTO_Hair_Strand   头发 Roto
  PNT_Cleanup_Marker 标记点修复
  CC_Primary_Grade   一级调色
  CMP_Beauty_Pass    美颜合成
  OUT_Final_EXR      最终输出
```

### 8.2 版本管理

```python
def save_pipeline_version(session, version_tag):
    """保存 Pipeline 版本快照"""
    import json
    snapshot = {
        "version": version_tag,
        "session": session.label,
        "nodes": []
    }
    for i in range(session.numNodes):
        n = session.node(i)
        node_info = {
            "label": n.label,
            "type": n.type,
            "inputs": [p.source.label if p.source else None for p in n.inputs]
        }
        snapshot["nodes"].append(node_info)
    
    with open(f"pipeline_{version_tag}.json", "w") as f:
        json.dump(snapshot, f, indent=2, ensure_ascii=False)
    
    return snapshot
```

### 8.3 模板复用

```python
# 预定义 Pipeline 模板
PIPELINE_TEMPLATES = {
    "basic_roto": ["RotoShape", "Output"],
    "tracked_roto": ["Tracker", "RotoShape", "Output"],
    "full_vfx": ["Tracker", "RotoShape", "Paint", "Color", "Composite", "Output"],
    "cleanup_only": ["Paint", "Output"],
    "color_only": ["Color", "Output"],
}

def apply_template(session, source, template_name):
    """应用预定义模板"""
    if template_name not in PIPELINE_TEMPLATES:
        raise ValueError(f"未知模板: {template_name}")
    return build_dynamic_chain(session, source, PIPELINE_TEMPLATES[template_name])
```

### 8.4 调试与监控

```python
def monitor_pipeline(session):
    """监控 Pipeline 状态"""
    stats = {
        "total_nodes": session.numNodes,
        "by_type": {},
        "disconnected": 0,
        "max_chain_depth": 0
    }
    
    for i in range(session.numNodes):
        n = session.node(i)
        stats["by_type"][n.type] = stats["by_type"].get(n.type, 0) + 1
        
        # 检查连接
        has_in = any(p.isConnected() for p in n.inputs)
        has_out = any(p.isConnected() for p in n.outputs)
        if not has_in and not has_out and n.type != "Source":
            stats["disconnected"] += 1
    
    return stats
```

---

## 附录:Pipeline 决策树

```
是否需要跟踪?
├─ 是 → 添加 Tracker 节点
│   └─ 是否需要 Roto?
│       ├─ 是 → 添加 RotoShape
│       └─ 否 → 直接进入下一步
└─ 否 → 跳过
    ↓
是否需要 Paint 修复?
├─ 是 → 添加 Paint 节点
└─ 否 → 跳过
    ↓
是否需要色彩校正?
├─ 是 → 添加 Color 节点
└─ 否 → 跳过
    ↓
是否有多层需要合成?
├─ 是 → 添加 Composite 节点
└─ 否 → 跳过
    ↓
添加 Output 节点
```

> **提示**:构建复杂 Pipeline 时,先在纸上画出节点图草图,再编写代码实现,可大幅减少调试时间。
