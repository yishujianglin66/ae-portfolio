# parent_type='BONE'的TAIL原点特性

## 问题场景

将发冠parent到Head骨骼时，发冠出现在骨骼TAIL（末端）而非HEAD（起始点），导致发冠悬浮在头顶上方。这是`parent_type='BONE'`的核心特性：**parent空间的原点在骨骼TAIL**。

## 核心原理

### BONE Parent的坐标系

```
骨骼结构：
  HEAD ●━━━━━━━━━━● TAIL  ← parent空间原点在这里！
       |← length →|

parent_type='BONE'时：
- 子物体的(0,0,0)对齐到骨骼TAIL
- 子物体的Y轴对齐骨骼方向（HEAD→TAIL）
- 子物体跟随骨骼旋转/移动
```

### 数学表达

```python
# parent_type='BONE'的变换链：
# child_world = armature_world × bone_pose_matrix × Translation(0, bone_length, 0) × matrix_parent_inverse × child_local

# 关键：Translation(0, bone_length, 0) 就是TAIL偏移！
```

### 本项目的问题

```python
# cel_shading.py L928-946 的发冠归位
_crown_part.parent = _armature_obj
_crown_part.parent_type = 'BONE'
_crown_part.parent_bone = 'Head'

# 如果不设置matrix_parent_inverse：
# 发冠原点 → Head TAIL → 头顶上方0.9单位（Head bone length）
# 结果：发冠悬浮！

# 解决：计算matrix_parent_inverse补偿TAIL偏移
```

### 正确的matrix_parent_inverse计算

```python
import bpy
from mathutils import Matrix, Vector

def parent_to_bone_tail(child_obj, armature_obj, bone_name):
    """
    将物体parent到骨骼，保持物体当前位置不变
    关键：正确计算matrix_parent_inverse
    """
    bpy.context.view_layer.update()
    
    # 获取骨骼的pose矩阵（世界空间）
    pb = armature_obj.pose.bones[bone_name]
    bone_world = armature_obj.matrix_world @ pb.matrix
    
    # 计算TAIL世界矩阵
    bone_length = pb.bone.length
    tail_matrix = bone_world @ Matrix.Translation(Vector((0, bone_length, 0)))
    
    # 设置parent
    child_obj.parent = armature_obj
    child_obj.parent_type = 'BONE'
    child_obj.parent_bone = bone_name
    
    # 关键：matrix_parent_inverse = TAIL矩阵的逆
    # 这样 child_world = tail_matrix × matrix_parent_inverse × child_local
    #                   = tail_matrix × tail_matrix^-1 × child_local
    #                   = child_local （保持原位！）
    child_obj.matrix_parent_inverse = tail_matrix.inverted()
    
    bpy.context.view_layer.update()
    
    # 验证
    print(f"Child world pos after parent: {child_obj.matrix_world.translation.to_tuple()}")
```

### 对比：parent_type='OBJECT'

```python
# parent_type='OBJECT'：原点在armature对象的origin
# 没有TAIL偏移问题，但无法跟随特定骨骼旋转

# parent_type='BONE'：跟随特定骨骼，但有TAIL偏移
# 需要matrix_parent_inverse补偿
```

## 常见陷阱

### 陷阱1：忘记设置matrix_parent_inverse
```python
# 错误：
child.parent = armature
child.parent_type = 'BONE'
child.parent_bone = 'Head'
# → 物体跳到TAIL位置！

# 正确：必须设置matrix_parent_inverse
```

### 陷阱2：使用错误的bone矩阵
```python
# 错误：用rest pose矩阵
bone_mat = armature.data.bones['Head'].matrix_local  # ← rest pose

# 正确：用pose矩阵（当前姿态）
bone_mat = armature.matrix_world @ armature.pose.bones['Head'].matrix
```

### 陷阱3：bone_length为0
```python
# 如果骨骼长度为0，TAIL==HEAD，无偏移
# 但Blender不允许零长度骨骼（会被删除）
```

## 本项目代码关联

`cel_shading.py` L928-946：
```python
_crown_part.parent = _armature_obj
_crown_part.parent_type = 'BONE'
_crown_part.parent_bone = 'Head'
# 计算tail矩阵
_pb_head_v12 = _armature_obj.pose.bones.get('Head')
_bone_mat_v12 = _armature_obj.matrix_world @ _pb_head_v12.matrix
_bone_len_v12 = _pb_head_v12.bone.length
_tail_mat_v12 = _bone_mat_v12 @ _MatV12.Translation(_V10Vec((0, _bone_len_v12, 0)))
_crown_part.matrix_parent_inverse = _tail_mat_v12.inverted()
```

## 版本兼容性

- Blender 4.x/5.x: parent_type='BONE'行为不变
- Blender 5.1.0 Alpha: 测试确认TAIL原点特性

## 参考链接

- [Blender API: Object.parent_type](https://docs.blender.org/api/current/bpy.types.Object.html)
- [Blender Manual: Parenting Objects](https://docs.blender.org/manual/en/latest/scene_layout/object/editing/parent.html)
