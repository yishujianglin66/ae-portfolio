# 武器Parent到Armature的策略

## 问题场景

武器归位后需要parent到armature以跟随角色运动。选择parent_type='OBJECT'还是'BONE'取决于是否需要跟随特定骨骼旋转。

## 核心原理

### 两种Parent策略

```python
# 策略1：parent_type='OBJECT'（跟随armature整体）
def parent_weapon_to_armature(weapon_obj, armature_obj):
    """武器跟随armature整体移动，不跟随特定骨骼旋转"""
    bpy.context.view_layer.update()
    weapon_world = weapon_obj.matrix_world.copy()
    
    weapon_obj.parent = armature_obj
    weapon_obj.parent_type = 'OBJECT'
    weapon_obj.matrix_parent_inverse = armature_obj.matrix_world.inverted() @ weapon_world
    
    # 效果：armature移动时武器跟随，但骨骼旋转不影响武器

# 策略2：parent_type='BONE'（跟随特定骨骼）
def parent_weapon_to_bone(weapon_obj, armature_obj, bone_name):
    """武器跟随特定骨骼（如Hand_R）旋转"""
    bpy.context.view_layer.update()
    weapon_world = weapon_obj.matrix_world.copy()
    
    pb = armature_obj.pose.bones[bone_name]
    bone_world = armature_obj.matrix_world @ pb.matrix
    tail_mat = bone_world @ Matrix.Translation(Vector((0, pb.bone.length, 0)))
    
    weapon_obj.parent = armature_obj
    weapon_obj.parent_type = 'BONE'
    weapon_obj.parent_bone = bone_name
    weapon_obj.matrix_parent_inverse = tail_mat.inverted() @ weapon_world
    
    # 效果：Hand_R旋转时武器跟随旋转
```

### 本项目的选择

```
上官婉儿v12策略：
- 扇子 → parent_type='OBJECT'（不跟随Hand_R旋转）
- 原因：v12保持A-pose，Hand_R不旋转
- 如果未来启用骨骼动画，需改为'BONE'

发冠 → parent_type='BONE'（跟随Head）
- 原因：头部微摆时发冠应跟随
```

### 组装后的Parent层级

```
Armature
├── body_main (权重蒙皮)
├── Object001/发冠 (parent_type='BONE', parent_bone='Head')
└── 5133_Weapon_High/扇柄 (parent_type='OBJECT')
    └── 5133_Weapon_High002/扇面 (parent=扇柄)
```

## 常见陷阱

### 陷阱1：先parent扇面再parent扇柄
```python
# 错误顺序：
fan_blade.parent = fan_handle  # 扇面→扇柄
fan_handle.parent = armature   # 扇柄→armature
# 此时扇面的matrix_parent_inverse可能需要重算

# 正确：先归位所有部件，最后统一设置parent
```

### 陷阱2：parent后武器位置跳跃
```python
# 必须正确设置matrix_parent_inverse
# 否则武器会跳到armature原点
```

## 本项目代码关联

`cel_shading.py` L1821-1855：
- 清除武器原有parent
- 扇面parent到扇柄
- 扇柄parent到armature（OBJECT模式）

## 版本兼容性

- Blender 4.x/5.x: parent API稳定
- Blender 5.1.0 Alpha: 测试通过

## 参考链接

- [Blender API: Object.parent_type](https://docs.blender.org/api/current/bpy.types.Object.html)
