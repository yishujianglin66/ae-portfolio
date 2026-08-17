# Blender Bone对象模型（Bone/EditBone/PoseBone）

## 问题场景

Blender中骨骼有三种访问方式：`Bone`（数据定义）、`EditBone`（编辑模式）、`PoseBone`（姿态模式）。混淆三者是骨骼开发中最常见的错误来源。程序化创建骨骼必须在正确模式下操作正确的对象。

## 核心原理

### 三种Bone对象的关系

```
Armature Data (bpy.data.armatures)
├── bones: [Bone]           # 只读，Rest Position定义
│   ├── name, head, tail, length, matrix_local
│   ├── parent (Bone引用)
│   └── children
│
├── edit_bones: [EditBone]  # 仅在EDIT_MODE可访问
│   ├── head, tail, roll    # 可修改！
│   ├── parent (EditBone引用)
│   └── use_connect
│
Object (bpy.data.objects)
└── pose.bones: [PoseBone]  # 仅在POSE_MODE有意义
    ├── matrix, matrix_basis  # 当前变换
    ├── rotation_euler, location, scale
    ├── bone → 对应的Bone引用
    └── constraints
```

### 模式切换规则

```python
import bpy

arm_obj = bpy.data.objects['Armature']

# 进入编辑模式 → 访问 edit_bones
bpy.context.view_layer.objects.active = arm_obj
bpy.ops.object.mode_set(mode='EDIT')
edit_bone = arm_obj.data.edit_bones['Head']  # 可修改head/tail
edit_bone.tail = (0, 0, 5.0)  # OK

# 进入姿态模式 → 访问 pose.bones
bpy.ops.object.mode_set(mode='POSE')
pose_bone = arm_obj.pose.bones['Head']  # 可设置旋转/位置
pose_bone.rotation_euler = (0, 0, 0.1)  # OK

# 回到物体模式 → 访问 bones (只读)
bpy.ops.object.mode_set(mode='OBJECT')
bone = arm_obj.data.bones['Head']  # 只读
# bone.head = (0,0,0)  # ERROR! 只读属性
```

### 关键属性对比

| 属性 | Bone | EditBone | PoseBone |
|------|------|----------|----------|
| head/tail | 只读(世界) | 可读写(armature空间) | N/A |
| matrix_local | Rest矩阵 | N/A | N/A |
| matrix | N/A | N/A | 当前变换矩阵 |
| rotation_euler | N/A | N/A | 姿态旋转 |
| length | 只读 | 可写 | 只读(via bone) |
| parent | Bone引用 | EditBone引用 | PoseBone引用 |

## 代码示例

### 程序化创建骨骼（完整流程）

```python
import bpy
from mathutils import Vector

def create_skeleton(name="Armature"):
    """创建基础人形骨骼"""
    # 1. 创建Armature对象
    arm_data = bpy.data.armatures.new(name)
    arm_obj = bpy.data.objects.new(name, arm_data)
    bpy.context.collection.objects.link(arm_obj)
    
    # 2. 进入编辑模式
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode='EDIT')
    
    # 3. 创建骨骼（必须在EDIT模式）
    def add_bone(name, head, tail, parent=None):
        bone = arm_data.edit_bones.new(name)
        bone.head = head
        bone.tail = tail
        if parent:
            bone.parent = parent
        return bone
    
    # 脊柱链
    hips = add_bone('Hips', (0, 0, 3.0), (0, 0, 3.3))
    spine = add_bone('Spine', (0, 0, 3.3), (0, 0, 3.8), hips)
    chest = add_bone('Chest', (0, 0, 3.8), (0, 0, 4.3), spine)
    neck = add_bone('Neck', (0, 0, 4.3), (0, 0, 4.6), chest)
    head = add_bone('Head', (0, 0, 4.6), (0, 0, 5.2), neck)
    
    # 4. 回到物体模式
    bpy.ops.object.mode_set(mode='OBJECT')
    
    return arm_obj

arm = create_skeleton()
```

## 常见陷阱

| 陷阱 | 错误代码 | 正确做法 |
|------|----------|----------|
| 在OBJECT模式修改骨骼位置 | `arm.data.bones['X'].head = ...` | 切换到EDIT模式用edit_bones |
| head==tail | 创建零长度骨骼 | 确保head≠tail，长度>0.01 |
| 忘记mode_set | edit_bones访问报错 | 创建前必须`mode_set(mode='EDIT')` |
| PoseBone.matrix混淆 | 用rest矩阵做pose计算 | 区分matrix_local(rest)和matrix(pose) |
| parent设置时机 | 在OBJECT模式设parent | 在EDIT模式设edit_bone.parent |

## 版本兼容

- Blender 5.1.0：三种Bone对象模型与4.x完全一致
- `bpy.ops.object.mode_set()` 需要对象为active且已select
- EditBone的`use_connect`影响子骨骼是否跟随父骨骼tail

## 关联代码

- `cel_shading.py` L700-810：v10骨骼创建（16根骨骼）
- `cel_shading.py` L898-926：POSE模式设置姿态（rotation_euler）
- `cel_shading.py` L936-944：通过pose.bones获取Head矩阵（发冠归位）

## 参考链接

- [bpy.types.Bone](https://docs.blender.org/api/current/bpy.types.Bone.html)
- [bpy.types.EditBone](https://docs.blender.org/api/current/bpy.types.EditBone.html)
- [bpy.types.PoseBone](https://docs.blender.org/api/current/bpy.types.PoseBone.html)
