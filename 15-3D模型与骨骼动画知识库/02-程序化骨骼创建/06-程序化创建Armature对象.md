# 程序化创建Armature对象

## 问题场景

为无骨骼FBX模型创建完整骨骼系统时，需要正确创建Armature对象、进入编辑模式、批量创建EditBone、设置层级关系。操作顺序错误会导致骨骼丢失或层级断裂。

## 核心原理

### 创建流程（严格顺序）

```python
import bpy
from mathutils import Vector

def create_armature(name="Armature"):
    """程序化创建Armature的完整流程"""
    
    # Step 1: 创建Armature数据块
    armature_data = bpy.data.armatures.new(name)
    
    # Step 2: 创建Armature对象并链接到场景
    armature_obj = bpy.data.objects.new(name, armature_data)
    bpy.context.collection.objects.link(armature_obj)
    
    # Step 3: 设为活动对象
    bpy.context.view_layer.objects.active = armature_obj
    armature_obj.select_set(True)
    
    # Step 4: 进入编辑模式（此时才能访问edit_bones）
    bpy.ops.object.mode_set(mode='EDIT')
    
    # Step 5: 创建骨骼（在编辑模式下）
    edit_bones = armature_data.edit_bones
    
    # 创建Root
    root = edit_bones.new("Root")
    root.head = Vector((0, 0, 0))
    root.tail = Vector((0, 0, 0.3))
    
    # 创建Hips（设置parent）
    hips = edit_bones.new("Hips")
    hips.head = Vector((0, 0, 3.0))
    hips.tail = Vector((0, 0, 3.3))
    hips.parent = root  # ← 必须在编辑模式下设置
    
    # Step 6: 退出编辑模式
    bpy.ops.object.mode_set(mode='OBJECT')
    
    return armature_obj
```

### 关键约束

| 操作 | 允许的模式 | 错误后果 |
|------|-----------|----------|
| `armature.edit_bones.new()` | EDIT only | RuntimeError |
| `edit_bone.parent = X` | EDIT only | 层级丢失 |
| `armature.bones[i].select` | OBJECT/POSE | 只读属性 |
| `pose.bones[i].rotation_euler` | POSE (或OBJECT) | 无效果 |
| `bpy.ops.object.mode_set()` | OBJECT | RuntimeError |

### 批量创建骨骼的辅助函数

```python
def batch_create_bones(edit_bones, bone_defs):
    """
    bone_defs: list of dict
    {
        'name': 'Hips',
        'head': (0, 0, 3.0),
        'tail': (0, 0, 3.3),
        'parent': 'Root',  # None表示无parent
        'roll': 0.0,
        'use_connect': False
    }
    """
    created = {}
    
    # 第一遍：创建所有骨骼（不设parent）
    for defn in bone_defs:
        eb = edit_bones.new(defn['name'])
        eb.head = Vector(defn['head'])
        eb.tail = Vector(defn['tail'])
        if 'roll' in defn:
            eb.roll = defn['roll']
        created[defn['name']] = eb
    
    # 第二遍：设置parent关系
    for defn in bone_defs:
        if defn.get('parent') and defn['parent'] in created:
            created[defn['name']].parent = created[defn['parent']]
        if defn.get('use_connect'):
            created[defn['name']].use_connect = True
    
    return created
```

## 常见陷阱

### 陷阱1：tail == head（零长度骨骼）
```python
# 错误：Blender会静默删除零长度骨骼
bone.head = Vector((0, 0, 3.0))
bone.tail = Vector((0, 0, 3.0))  # ← 退出编辑模式后骨骼消失！

# 正确：确保tail != head
bone.tail = bone.head + Vector((0, 0, 0.3))
```

### 陷阱2：忘记设active对象
```python
# 错误：mode_set失败
bpy.ops.object.mode_set(mode='EDIT')  # RuntimeError: no active object

# 正确：
bpy.context.view_layer.objects.active = armature_obj
bpy.ops.object.mode_set(mode='EDIT')
```

### 陷阱3：编辑模式下引用已删除的EditBone
```python
# 错误：删除parent后子骨骼的parent引用悬空
edit_bones.remove(parent_bone)
# child_bone.parent 现在指向无效内存 → 崩溃

# 正确：先解除子骨骼的parent
for child in parent_bone.children:
    child.parent = None
edit_bones.remove(parent_bone)
```

## 本项目代码关联

`cel_shading.py` L855-926：
- L860: `arm_data = bpy.data.armatures.new("Armature")`
- L862: `arm_obj = bpy.data.objects.new("Armature", arm_data)`
- L865: `bpy.ops.object.mode_set(mode='EDIT')`
- L870-920: 批量创建16根骨骼（使用百分比高度定位）

## 版本兼容性

- Blender 4.x/5.x: API稳定，无变化
- Blender 5.1.0 Alpha: 测试通过

## 参考链接

- [Blender API: Armature](https://docs.blender.org/api/current/bpy.types.Armature.html)
- [Blender API: EditBone](https://docs.blender.org/api/current/bpy.types.EditBone.html)
