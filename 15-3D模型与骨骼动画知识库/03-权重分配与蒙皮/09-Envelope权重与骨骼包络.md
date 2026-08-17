# Envelope权重与骨骼包络

## 问题场景

除vertex_groups外，Blender还支持Envelope（包络）权重模式：每根骨骼有内/外半径，顶点在半径内自动获得权重。适合快速原型但精度不如vertex_groups。

## 核心原理

### Envelope模式原理

```
骨骼包络：
  ┌─────────────────────────────┐  ← 外半径 (dist_max)
  │  ┌───────────────────────┐  │
  │  │  ┌─────────────────┐  │  │  ← 内半径 (dist_min)
  │  │  │    BONE LINE    │  │  │
  │  │  └─────────────────┘  │  │
  │  └───────────────────────┘  │
  └─────────────────────────────┘

权重计算：
  d < dist_min → weight = 1.0
  dist_min < d < dist_max → weight = 1 - (d-dist_min)/(dist_max-dist_min)
  d > dist_max → weight = 0.0
```

### 配置Envelope权重

```python
import bpy

def setup_envelope_weights(armature_obj, mesh_obj):
    """使用Envelope模式而非vertex_groups"""
    
    # 1. 设置骨骼包络参数
    for bone in armature_obj.data.bones:
        bone.envelope_distance = 0.5   # 外半径
        bone.envelope_weight = 1.0     # 权重强度
        # head/tail半径可分别设置
        bone.head_radius = 0.3
        bone.tail_radius = 0.2
    
    # 2. Armature Modifier使用envelope
    mod = mesh_obj.modifiers.get("Armature")
    if mod:
        mod.use_vertex_groups = False    # 不用vertex_groups
        mod.use_deform_preserve_volume = False
        # 当use_vertex_groups=False时，自动使用envelope
```

### Envelope vs Vertex Groups对比

| 特性 | Envelope | Vertex Groups |
|------|----------|---------------|
| 精度 | 低（基于距离） | 高（逐顶点） |
| 设置速度 | 快（调半径） | 慢（逐顶点） |
| 适用场景 | 快速原型、简单模型 | 生产级角色 |
| 多骨骼混合 | 自动（距离衰减） | 手动控制 |
| 程序化控制 | 容易（设半径） | 需要计算 |

### 混合模式

```python
# Blender可以同时使用两种模式
mod.use_vertex_groups = True  # 有vertex_group的顶点用VG
# 没有VG的顶点fallback到envelope
```

## 常见陷阱

### 陷阱1：包络半径过大导致全身联动
```python
# 错误：所有骨骼半径=2.0 → 每个顶点受所有骨骼影响
# 正确：半径应为骨骼长度的30-50%
bone.envelope_distance = bone.length * 0.4
```

## 本项目代码关联

`cel_shading.py`：未使用Envelope模式（使用IDW vertex_groups）

## 版本兼容性

- Blender 4.x/5.x: Envelope API稳定
- Blender 5.1.0 Alpha: 可用但不推荐用于生产

## 参考链接

- [Blender Manual: Envelope Skinning](https://docs.blender.org/manual/en/latest/animation/armatures/skinning/parenting.html#armature-envelope)
