# Vertex Groups API详解

## 问题场景

权重数据存储在mesh的`vertex_groups`中，每个vertex_group对应一根骨骼。需要掌握创建、查询、修改、删除vertex_group的完整API，以及顶点权重的读写方法。

## 核心原理

### 数据结构

```
Mesh Object
├── vertex_groups: [VertexGroup]
│   ├── [0] name="Hips", index=0
│   ├── [1] name="Spine", index=1
│   └── [2] name="Head", index=2
│
└── vertices: [MeshVertex]
    └── [0] groups: [VertexGroupElement]
        ├── group=0 (Hips), weight=0.3
        ├── group=1 (Spine), weight=0.5
        └── group=2 (Head), weight=0.2
```

### 基本操作

```python
import bpy

obj = bpy.data.objects['body_main']
mesh = obj.data

# === 创建 vertex_group ===
vg = obj.vertex_groups.new(name="Hand_R")
# 或获取已有的
vg = obj.vertex_groups.get("Hand_R")
if vg is None:
    vg = obj.vertex_groups.new(name="Hand_R")

# === 设置权重 ===
# 方式1：单顶点
vg.add(index=[42], weight=0.8, type='REPLACE')  # 替换
vg.add(index=[42], weight=0.1, type='ADD')      # 累加
vg.add(index=[42], weight=0.1, type='SUBTRACT') # 减去
vg.add(index=[42], weight=0.5, type='DIFFERENCE') # 差值

# 方式2：批量顶点
vertex_indices = [0, 1, 2, 3, 4, 5]
vg.add(index=vertex_indices, weight=1.0, type='REPLACE')

# === 读取权重 ===
for vert in mesh.vertices:
    for g in vert.groups:
        group_name = obj.vertex_groups[g.group].name
        print(f"Vertex {vert.index}: {group_name} = {g.weight:.3f}")

# === 查询特定顶点的权重 ===
def get_vertex_weight(obj, vertex_index, group_name):
    """获取特定顶点在特定组的权重"""
    vg = obj.vertex_groups.get(group_name)
    if vg is None:
        return 0.0
    try:
        return vg.weight(vertex_index)
    except RuntimeError:
        return 0.0  # 顶点不在该组中

# === 删除权重 ===
vg.remove(index=[42])           # 删除特定顶点
vg.remove(list(range(len(mesh.vertices))))  # 清空该组

# === 删除 vertex_group ===
obj.vertex_groups.remove(vg)

# === 清空所有组 ===
obj.vertex_groups.clear()
```

### 权重统计与验证

```python
def analyze_weights(obj):
    """分析权重分配质量"""
    mesh = obj.data
    stats = {}
    
    # 初始化统计
    for vg in obj.vertex_groups:
        stats[vg.name] = {'count': 0, 'total_weight': 0.0, 'max_weight': 0.0}
    
    # 遍历所有顶点
    unweighted = []
    over_weighted = []
    
    for vert in mesh.vertices:
        total = sum(g.weight for g in vert.groups)
        
        if len(vert.groups) == 0:
            unweighted.append(vert.index)
        elif total > 1.01:
            over_weighted.append((vert.index, total))
        
        for g in vert.groups:
            name = obj.vertex_groups[g.group].name
            stats[name]['count'] += 1
            stats[name]['total_weight'] += g.weight
            stats[name]['max_weight'] = max(stats[name]['max_weight'], g.weight)
    
    # 输出报告
    print(f"\n=== Weight Analysis: {obj.name} ===")
    print(f"Total vertices: {len(mesh.vertices)}")
    print(f"Unweighted: {len(unweighted)}")
    print(f"Over-weighted (>1.0): {len(over_weighted)}")
    print(f"\nPer-bone stats:")
    for name, s in sorted(stats.items(), key=lambda x: -x[1]['count']):
        avg = s['total_weight'] / max(s['count'], 1)
        print(f"  {name:15s}: {s['count']:5d} verts, avg={avg:.3f}, max={s['max_weight']:.3f}")
    
    return stats, unweighted, over_weighted
```

### 权重归一化修复

```python
def normalize_weights(obj):
    """确保每个顶点的权重总和为1.0"""
    mesh = obj.data
    
    for vert in mesh.vertices:
        if len(vert.groups) == 0:
            continue
        
        total = sum(g.weight for g in vert.groups)
        if abs(total - 1.0) > 0.001:
            # 重新归一化
            for g in vert.groups:
                vg = obj.vertex_groups[g.group]
                new_weight = g.weight / total
                vg.add([vert.index], new_weight, 'REPLACE')
```

## 常见陷阱

### 陷阱1：vertex_group的index vs name
```python
# 错误：用name作为index
vert.groups[0].group  # ← 这是index（整数），不是name！

# 正确：通过index查name
group_name = obj.vertex_groups[vert.groups[0].group].name
```

### 陷阱2：add()的index参数必须是列表
```python
# 错误：
vg.add(42, 1.0, 'REPLACE')  # ← TypeError

# 正确：
vg.add([42], 1.0, 'REPLACE')  # ← 列表！
```

## 本项目代码关联

`cel_shading.py` L950-1020：
- 创建与骨骼同名的vertex_groups
- IDW权重赋值使用`vg.add([idx], weight, 'REPLACE')`

## 版本兼容性

- Blender 4.x/5.x: VertexGroup API稳定
- Blender 5.1.0 Alpha: 测试通过

## 参考链接

- [Blender API: VertexGroup](https://docs.blender.org/api/current/bpy.types.VertexGroup.html)
- [Blender API: MeshVertex.groups](https://docs.blender.org/api/current/bpy.types.MeshVertex.html)
