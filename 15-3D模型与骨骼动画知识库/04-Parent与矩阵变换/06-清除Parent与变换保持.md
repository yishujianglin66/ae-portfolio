# 清除Parent与变换保持

## 问题场景

重新定位物体前需要清除现有parent关系。直接`obj.parent = None`会导致物体跳跃（因为matrix_parent_inverse被移除）。需要正确清除parent同时保持世界位置。

## 核心原理

### 清除Parent的方式

```python
import bpy

# 方式1：保持世界位置（推荐）
def clear_parent_keep_transform(obj):
    """清除parent，保持世界位置不变"""
    bpy.context.view_layer.update()
    
    # 记录当前世界矩阵
    world_mat = obj.matrix_world.copy()
    
    # 清除parent
    obj.parent = None
    obj.parent_type = 'OBJECT'
    obj.parent_bone = ''
    obj.matrix_parent_inverse.identity()
    
    # 恢复世界矩阵
    obj.matrix_world = world_mat
    
    bpy.context.view_layer.update()

# 方式2：使用ops（自动保持）
def clear_parent_via_ops(obj):
    """通过ops清除parent"""
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    
    # CLEAR_KEEP_TRANSFORM = 保持世界位置
    bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')

# 方式3：完全清除（物体会跳到局部坐标位置）
def clear_parent_raw(obj):
    """直接清除（不保持位置）"""
    obj.parent = None
    # 物体的matrix_world变为matrix_basis
```

### 重新Parent的流程

```python
def reparent_object(obj, new_parent, bone_name=None):
    """重新设置parent（先清除旧的）"""
    # 1. 清除旧parent
    clear_parent_keep_transform(obj)
    
    # 2. 设置新parent
    bpy.context.view_layer.update()
    obj_world = obj.matrix_world.copy()
    
    obj.parent = new_parent
    if bone_name:
        obj.parent_type = 'BONE'
        obj.parent_bone = bone_name
        # 计算TAIL矩阵...
        pb = new_parent.pose.bones[bone_name]
        bone_world = new_parent.matrix_world @ pb.matrix
        tail_mat = bone_world @ Matrix.Translation(Vector((0, pb.bone.length, 0)))
        obj.matrix_parent_inverse = tail_mat.inverted() @ obj_world
    else:
        obj.parent_type = 'OBJECT'
        obj.matrix_parent_inverse = new_parent.matrix_world.inverted() @ obj_world
    
    bpy.context.view_layer.update()
```

## 常见陷阱

### 陷阱1：清除parent后物体消失
```python
# 原因：物体的local坐标在很远的地方
# 之前靠parent_inverse补偿到正确位置
# 清除后local坐标暴露 → 物体飞到远处
# 解决：用CLEAR_KEEP_TRANSFORM
```

### 陷阱2：批量清除时active对象错误
```python
# bpy.ops.object.parent_clear需要正确的active对象
# 批量操作时逐个设置active
```

## 本项目代码关联

`cel_shading.py` L1821-1830：武器归位前清除parent
```python
# 清除武器原有parent
_fan_handle.parent = None
_fan_blade.parent = None
```

## 版本兼容性

- Blender 4.x/5.x: parent_clear API稳定
- Blender 5.1.0 Alpha: 测试通过

## 参考链接

- [Blender API: bpy.ops.object.parent_clear](https://docs.blender.org/api/current/bpy.ops.object.html)
