# matrix_world vs matrix_local vs pose.bones[].matrix

## 问题场景

Blender中有多种变换矩阵，混淆使用是矩阵计算错误的最大来源。需要明确每种矩阵的坐标空间、更新时机和适用场景。

## 核心原理

### 矩阵类型对比

| 矩阵 | 所属 | 坐标空间 | 含义 |
|------|------|----------|------|
| `obj.matrix_world` | Object | 世界 | 物体→世界的完整变换 |
| `obj.matrix_local` | Object | Parent | 物体→parent的变换 |
| `obj.matrix_basis` | Object | 自身 | location/rotation/scale组合 |
| `bone.matrix_local` | Bone | Armature | 骨骼rest pose→armature空间 |
| `pb.matrix` | PoseBone | Armature | 骨骼当前pose→armature空间 |
| `pb.matrix_basis` | PoseBone | 自身 | pose变换（旋转/位移/缩放） |

### 变换链

```
世界空间
  ↑ obj.matrix_world
Parent空间（如果有parent）
  ↑ obj.matrix_local (= matrix_parent_inverse × matrix_basis)
物体局部空间
  ↑ mesh顶点坐标

对于骨骼：
世界空间
  ↑ armature.matrix_world × pb.matrix
Armature空间
  ↑ pb.matrix (= rest_matrix × pose_transform)
骨骼Rest空间
  ↑ bone.matrix_local
```

### 代码示例

```python
import bpy
from mathutils import Matrix, Vector

def demonstrate_matrices(obj, armature_obj, bone_name):
    """展示各种矩阵的关系"""
    bpy.context.view_layer.update()
    
    # === Object矩阵 ===
    print(f"\n=== {obj.name} ===")
    print(f"matrix_world translation: {obj.matrix_world.translation.to_tuple()}")
    print(f"matrix_local translation: {obj.matrix_local.translation.to_tuple()}")
    print(f"matrix_basis translation: {obj.matrix_basis.translation.to_tuple()}")
    
    # 关系：matrix_world = parent.matrix_world × matrix_local
    if obj.parent:
        expected = obj.parent.matrix_world @ obj.matrix_local
        actual = obj.matrix_world
        diff = (expected.translation - actual.translation).length
        print(f"Verification: parent_world × local == world? diff={diff:.6f}")
    
    # === Bone矩阵 ===
    print(f"\n=== Bone: {bone_name} ===")
    bone = armature_obj.data.bones[bone_name]
    pb = armature_obj.pose.bones[bone_name]
    
    print(f"bone.matrix_local (rest): {bone.matrix_local.translation.to_tuple()}")
    print(f"pb.matrix (pose): {pb.matrix.translation.to_tuple()}")
    print(f"pb.matrix_basis (pose delta): {pb.matrix_basis.translation.to_tuple()}")
    
    # 骨骼世界位置
    bone_world = armature_obj.matrix_world @ pb.matrix
    print(f"Bone world pos: {bone_world.translation.to_tuple()}")
    
    # TAIL世界位置
    tail_world = bone_world @ Matrix.Translation(Vector((0, bone.length, 0)))
    print(f"Tail world pos: {tail_world.translation.to_tuple()}")
```

### 何时使用哪个矩阵

```python
# 获取物体世界位置 → matrix_world.translation
world_pos = obj.matrix_world.translation

# 获取物体在parent空间的位置 → matrix_local.translation
local_pos = obj.matrix_local.translation

# 获取骨骼世界位置 → armature.matrix_world × pb.matrix
bone_world = armature.matrix_world @ armature.pose.bones['Head'].matrix

# 将世界坐标转为物体局部坐标 → matrix_world.inverted() × point
local_point = obj.matrix_world.inverted() @ world_point

# 获取物体的世界旋转 → matrix_world.to_quaternion()
world_rot = obj.matrix_world.to_quaternion()

# 获取物体的世界缩放 → matrix_world.to_scale()
world_scale = obj.matrix_world.to_scale()
```

## 常见陷阱

### 陷阱1：matrix_world未更新
```python
# 修改location后，matrix_world不会立即更新！
obj.location = (1, 2, 3)
print(obj.matrix_world.translation)  # ← 可能是旧值！

# 正确：
obj.location = (1, 2, 3)
bpy.context.view_layer.update()
print(obj.matrix_world.translation)  # ← 现在是(1,2,3)
```

### 陷阱2：混淆bone.matrix_local和pb.matrix
```python
# bone.matrix_local = rest pose（永远不变）
# pb.matrix = 当前pose（随动画变化）

# 错误：用rest pose计算当前世界位置
bone_world = armature.matrix_world @ bone.matrix_local  # ← rest pose！

# 正确：用pose matrix
bone_world = armature.matrix_world @ pb.matrix  # ← 当前pose
```

## 本项目代码关联

`cel_shading.py`：
- L940: `_bone_mat_v12 = _armature_obj.matrix_world @ _pb_head_v12.matrix`（pose矩阵）
- L945: `_crown_part.matrix_world.translation.to_tuple()`（世界位置诊断）

## 版本兼容性

- Blender 4.x/5.x: 矩阵API稳定
- Blender 5.1.0 Alpha: 测试通过

## 参考链接

- [Blender API: Object.matrix_world](https://docs.blender.org/api/current/bpy.types.Object.html)
- [Blender API: PoseBone.matrix](https://docs.blender.org/api/current/bpy.types.PoseBone.html)
