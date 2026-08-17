# Armature Modifier与蒙皮变形

## 问题场景

权重分配后，网格需要通过Armature Modifier才能跟随骨骼变形。缺少modifier或modifier配置错误会导致"有权重但不动"的问题。

## 核心原理

### Armature Modifier的作用

```
渲染管线：
Rest Pose顶点 → Armature Modifier(权重+骨骼矩阵) → Deformed顶点 → 渲染

没有Modifier：
Rest Pose顶点 → 直接渲染（不动！）
```

### 添加与配置

```python
import bpy

def setup_armature_modifier(mesh_obj, armature_obj):
    """为mesh添加并配置Armature修改器"""
    
    # 检查是否已有
    existing = None
    for mod in mesh_obj.modifiers:
        if mod.type == 'ARMATURE':
            existing = mod
            break
    
    if existing:
        existing.object = armature_obj
        return existing
    
    # 添加新modifier
    mod = mesh_obj.modifiers.new(name="Armature", type='ARMATURE')
    mod.object = armature_obj
    
    # 关键设置
    mod.use_vertex_groups = True      # 使用vertex_groups权重
    mod.use_deform_preserve_volume = False  # 不保持体积（性能优先）
    mod.use_multi_modifier = False    # 不与其他modifier混合
    
    return mod
```

### Modifier执行顺序

```python
# Modifier按列表顺序执行（从上到下）
# 对于蒙皮模型，推荐顺序：
# 1. Armature (骨骼变形)
# 2. Subdivision Surface (细分，可选)
# 3. LineArt (描边，渲染用)

def reorder_modifiers(obj):
    """确保Armature在第一位"""
    arm_mod_idx = None
    for i, mod in enumerate(obj.modifiers):
        if mod.type == 'ARMATURE':
            arm_mod_idx = i
            break
    
    if arm_mod_idx and arm_mod_idx > 0:
        # 移到顶部
        bpy.context.view_layer.objects.active = obj
        for _ in range(arm_mod_idx):
            bpy.ops.object.modifier_move_up(modifier="Armature")
```

### 变形原理（Dual Quaternion vs Linear）

```python
# Blender支持两种蒙皮变形算法：
mod.use_deform_preserve_volume = False   # Linear Blend Skinning (LBS)
mod.use_deform_preserve_volume = True    # Dual Quaternion (DQ)

# LBS: 线性混合，关节处会"糖果纸"收缩
# DQ: 保持体积，但多骨骼影响时可能膨胀
# 推荐：静态渲染用LBS（简单快速）
```

### 验证变形是否生效

```python
import bpy
from mathutils import Vector

def test_deformation(mesh_obj, armature_obj, bone_name, angle=0.5):
    """测试旋转骨骼后网格是否变形"""
    bpy.context.view_layer.update()
    
    # 记录变形前顶点位置
    mesh = mesh_obj.data
    before = [v.co.copy() for v in mesh.vertices]
    
    # 旋转骨骼
    pb = armature_obj.pose.bones[bone_name]
    original_rot = pb.rotation_euler.copy()
    pb.rotation_euler.x += angle
    bpy.context.view_layer.update()
    
    # 获取变形后位置（需要应用modifier）
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = mesh_obj.evaluated_get(depsgraph)
    eval_mesh = eval_obj.to_mesh()
    
    after = [v.co.copy() for v in eval_mesh.vertices]
    
    # 计算位移
    moved = sum(1 for b, a in zip(before, after) if (a - b).length > 0.001)
    print(f"[Deform Test] {bone_name} rotated {angle:.2f}rad → {moved}/{len(before)} vertices moved")
    
    # 恢复
    pb.rotation_euler = original_rot
    eval_obj.to_mesh_clear()
    
    return moved > 0
```

## 常见陷阱

### 陷阱1：mesh未parent到armature
```python
# 仅有modifier不够，还需要parent关系
mesh_obj.parent = armature_obj  # ← 必须！
# 或者在parent_set时自动添加modifier
```

### 陷阱2：vertex_group名称与骨骼名不匹配
```python
# modifier通过名称匹配vertex_group和bone
# 如果vertex_group叫"Hand_R"但骨骼叫"Hand.R" → 不匹配 → 不变形
# 解决：确保名称完全一致
```

### 陷阱3：多mesh共享同一armature
```python
# 每个mesh都需要独立的Armature modifier
for obj in body_parts:
    setup_armature_modifier(obj, armature_obj)
```

## 本项目代码关联

`cel_shading.py` L930-945：
- parent_set(type='ARMATURE_AUTO')自动添加modifier
- 或手动`obj.modifiers.new(type='ARMATURE')`

## 版本兼容性

- Blender 4.x/5.x: Armature Modifier API稳定
- Blender 5.1.0 Alpha: 测试通过

## 参考链接

- [Blender Manual: Armature Modifier](https://docs.blender.org/manual/en/latest/modeling/modifiers/deform/armature.html)
- [Blender API: ArmatureModifier](https://docs.blender.org/api/current/bpy.types.ArmatureModifier.html)
