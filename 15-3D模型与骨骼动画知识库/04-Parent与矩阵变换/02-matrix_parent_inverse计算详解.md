# matrix_parent_inverse计算详解

## 问题场景

`matrix_parent_inverse`是parent关系中的核心矩阵，决定了子物体在parent空间中的初始变换。计算错误会导致物体跳跃、旋转异常、缩放失真。

## 核心原理

### 变换链公式

```
child_world = parent_world × parent_space_matrix × matrix_parent_inverse × child_local

对于parent_type='BONE':
  parent_space_matrix = bone_pose_matrix × Translation(0, bone_length, 0)

对于parent_type='OBJECT':
  parent_space_matrix = Identity（单位矩阵）
```

### matrix_parent_inverse的含义

```python
# matrix_parent_inverse = "设置parent那一刻，parent空间的逆矩阵"
# 它记录了"parent空间相对于世界的初始状态"
# 后续parent移动/旋转时，child跟随变化，但保持相对关系

# 如果想让child保持当前世界位置不变：
# matrix_parent_inverse = parent_space_matrix.inverted()
# 这样：child_world = parent_space × parent_space^-1 × child_local = child_local
```

### 三种常见场景

```python
import bpy
from mathutils import Matrix, Vector

# 场景1：保持物体当前位置（最常用）
def parent_keep_position(child, parent_obj):
    """parent后物体不跳动"""
    bpy.context.view_layer.update()
    
    # 记录当前世界矩阵
    child_world = child.matrix_world.copy()
    
    # 设置parent
    child.parent = parent_obj
    child.parent_type = 'OBJECT'
    
    # 计算inverse使世界位置不变
    # child_world = parent_world × mpi × child_local
    # 设child_local = Identity:
    # child_world = parent_world × mpi
    # mpi = parent_world^-1 × child_world
    child.matrix_parent_inverse = parent_obj.matrix_world.inverted() @ child_world

# 场景2：parent到BONE（有TAIL偏移）
def parent_to_bone_keep_position(child, armature, bone_name):
    """parent到骨骼TAIL，保持位置"""
    bpy.context.view_layer.update()
    
    child_world = child.matrix_world.copy()
    
    pb = armature.pose.bones[bone_name]
    bone_world = armature.matrix_world @ pb.matrix
    tail_offset = Matrix.Translation(Vector((0, pb.bone.length, 0)))
    tail_world = bone_world @ tail_offset
    
    child.parent = armature
    child.parent_type = 'BONE'
    child.parent_bone = bone_name
    
    # mpi = tail_world^-1 × child_world
    child.matrix_parent_inverse = tail_world.inverted() @ child_world

# 场景3：物体对齐到骨骼TAIL（不保持原位）
def parent_align_to_bone_tail(child, armature, bone_name):
    """物体原点对齐到骨骼TAIL"""
    pb = armature.pose.bones[bone_name]
    bone_world = armature.matrix_world @ pb.matrix
    tail_offset = Matrix.Translation(Vector((0, pb.bone.length, 0)))
    tail_world = bone_world @ tail_offset
    
    child.parent = armature
    child.parent_type = 'BONE'
    child.parent_bone = bone_name
    
    # mpi = tail_world^-1（物体原点→TAIL）
    child.matrix_parent_inverse = tail_world.inverted()
```

### 验证方法

```python
def verify_parent(child_obj, expected_world_pos, tolerance=0.01):
    """验证parent后世界位置是否正确"""
    bpy.context.view_layer.update()
    actual = child_obj.matrix_world.translation
    diff = (actual - Vector(expected_world_pos)).length
    
    if diff < tolerance:
        print(f"[OK] Position preserved (diff={diff:.6f})")
    else:
        print(f"[FAIL] Position jumped! diff={diff:.4f}")
        print(f"  Expected: {expected_world_pos}")
        print(f"  Actual: {actual.to_tuple()}")
    
    return diff < tolerance
```

## 常见陷阱

### 陷阱1：设置parent前未update
```python
# 错误：matrix_world是旧值
child.matrix_parent_inverse = parent.matrix_world.inverted() @ child.matrix_world
# 如果之前有未应用的变换，matrix_world可能过期

# 正确：
bpy.context.view_layer.update()
# 然后再计算
```

### 陷阱2：修改parent后忘记重算mpi
```python
# 如果parent的matrix_world改变（如移动了armature）
# 已设置的mpi不会自动更新
# 需要重新计算或clear_parent()后重新parent
```

## 本项目代码关联

`cel_shading.py` L940-946：
- `_tail_mat_v12 = _bone_mat_v12 @ Translation(0, bone_length, 0)`
- `_crown_part.matrix_parent_inverse = _tail_mat_v12.inverted()`

## 版本兼容性

- Blender 4.x/5.x: matrix_parent_inverse行为不变
- Blender 5.1.0 Alpha: 测试通过

## 参考链接

- [Blender API: Object.matrix_parent_inverse](https://docs.blender.org/api/current/bpy.types.Object.html)
- [Blender Source: object_parent.c](https://developer.blender.org/)
