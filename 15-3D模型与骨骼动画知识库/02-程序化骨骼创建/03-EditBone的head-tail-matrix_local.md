# EditBone的head/tail/matrix_local详解

## 问题场景

程序化创建骨骼时，`head`和`tail`定义了骨骼的位置和方向，`matrix_local`决定了rest pose下的变换矩阵。理解三者的数学关系是正确创建骨骼和计算parent矩阵的基础。

## 核心原理

### head/tail定义骨骼

```
head ●━━━━━━━━━━● tail
     |← length →|
     方向向量 = tail - head (归一化后为骨骼Y轴)
```

- **head**: 骨骼起始点（armature局部空间）
- **tail**: 骨骼终止点（head + 方向 × 长度）
- **length**: `|tail - head|`，必须 > 0
- **roll**: 骨骼绕自身Y轴的旋转（影响X/Z轴方向）

### matrix_local的含义

`bone.matrix_local` 是4×4变换矩阵，将骨骼局部空间映射到armature空间：

```python
# matrix_local的列向量含义：
# col 0: 骨骼X轴（在armature空间中的方向）
# col 1: 骨骼Y轴（head→tail方向）
# col 2: 骨骼Z轴（X×Y叉积）
# col 3: 骨骼head位置（平移分量）

# 验证：
bone = arm.data.bones['Head']
print(bone.matrix_local.translation)  # == bone.head
print(bone.matrix_local.col[1][:3].normalized())  # == (tail-head).normalized()
```

### roll对矩阵的影响

```python
import bpy
from mathutils import Vector
import math

# 创建骨骼后修改roll
bpy.ops.object.mode_set(mode='EDIT')
eb = arm.data.edit_bones['UpperArm_R']

# roll=0: X轴默认对齐世界X（或最近轴）
# roll=π/2: X轴旋转90°
eb.roll = math.radians(90)  # 改变X/Z轴方向，不影响head/tail

bpy.ops.object.mode_set(mode='OBJECT')
# 此时 bone.matrix_local 的 col[0] 和 col[2] 已改变
```

## 代码示例

### 计算骨骼中心（用于权重分配）

```python
def get_bone_center(bone):
    """获取骨骼中心的世界坐标"""
    # 方法1: 直接计算
    center_local = (bone.head + bone.tail) / 2.0
    
    # 方法2: 通过armature的matrix_world转世界坐标
    arm_obj = bpy.data.objects['Armature']
    center_world = arm_obj.matrix_world @ center_local
    return center_world

# 本项目中用于距离反比权重计算
bone_centers = {}
for bone in arm.data.bones:
    bone_centers[bone.name] = get_bone_center(bone)
```

### 获取骨骼TAIL的世界坐标（发冠归位用）

```python
def get_bone_tail_world(arm_obj, bone_name):
    """获取骨骼TAIL的世界坐标 — 发冠parent的关键"""
    pb = arm_obj.pose.bones.get(bone_name)
    if pb:
        # pose bone的matrix是head位置的变换
        bone_mat = arm_obj.matrix_world @ pb.matrix
        bone_len = pb.bone.length
        # TAIL = HEAD + Y轴方向 × length
        from mathutils import Matrix
        tail_mat = bone_mat @ Matrix.Translation((0, bone_len, 0))
        return tail_mat
    return None
```

## 常见陷阱

| 陷阱 | 原因 | 解决 |
|------|------|------|
| head==tail报错 | 零长度骨骼无效 | 确保tail-head长度>0.001 |
| matrix_local.translation ≠ head | armature有变换时 | 需乘armature.matrix_world |
| roll影响变形方向 | roll改变X/Z轴 | 对齐网格后设roll=0 |
| 混淆local和world | bone.head是armature空间 | 世界坐标需乘matrix_world |
| TAIL位置计算错误 | 忘记乘bone.length | Translation(0, length, 0) |

## 关联代码

- `cel_shading.py` L939-941：`_tail_mat_v12 = _bone_mat_v12 @ _MatV12.Translation((0, _bone_len_v12, 0))`
- `cel_shading.py` L870-886：使用bone_centers做距离反比权重
- 发冠下沉bug的根因：用HEAD矩阵做inverse而非TAIL矩阵
