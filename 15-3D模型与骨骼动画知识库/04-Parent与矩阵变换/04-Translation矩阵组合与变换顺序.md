# Translation矩阵组合与变换顺序

## 问题场景

矩阵乘法不满足交换律（A×B ≠ B×A），变换顺序错误会导致物体出现在完全错误的位置。理解"先旋转后平移"vs"先平移后旋转"的区别至关重要。

## 核心原理

### 矩阵乘法顺序

```python
from mathutils import Matrix, Vector
import math

# Blender使用列向量（右乘）：
# result = M × v
# 复合变换：result = A × B × C × v
# 执行顺序：先C，再B，最后A（从右到左）

# 例：先旋转45°，再沿X平移2单位
T = Matrix.Translation(Vector((2, 0, 0)))
R = Matrix.Rotation(math.radians(45), 4, 'Z')

# 正确：先旋转后平移
M = T @ R  # 物体先旋转，再沿世界X平移
v_result = M @ Vector((1, 0, 0, 1))

# 错误：先平移后旋转
M_wrong = R @ T  # 物体先平移，再绕原点旋转（平移方向也旋转了！）
```

### 常用变换矩阵

```python
from mathutils import Matrix, Vector, Euler
import math

# 平移矩阵
T = Matrix.Translation(Vector((x, y, z)))

# 旋转矩阵（绕轴）
Rx = Matrix.Rotation(angle, 4, 'X')
Ry = Matrix.Rotation(angle, 4, 'Y')
Rz = Matrix.Rotation(angle, 4, 'Z')

# 缩放矩阵
S = Matrix.Scale(factor, 4)  # 均匀缩放
Sx = Matrix.Scale(fx, 4, Vector((1, 0, 0)))  # X轴缩放

# 从欧拉角构建
euler = Euler((rx, ry, rz), 'XYZ')
R = euler.to_matrix().to_4x4()

# 从四元数构建
quat = Quaternion((w, x, y, z))
R = quat.to_matrix().to_4x4()

# 组合：TRS（Translation × Rotation × Scale）
M = T @ R @ S  # 标准组合顺序
```

### 本项目的变换应用

```python
# 扇子归位中的变换（cel_shading.py L1707-1744）

# Step 1: 旋转扇柄（先旋转）
from mathutils import Euler
rot = Euler((math.radians(70), 0, math.radians(-45)), 'XYZ')
_fan_handle.rotation_euler = rot

# Step 2: 计算握点世界位置（旋转后的局部点→世界）
bpy.context.view_layer.update()
grip_local = Vector((grip_x, grip_y, grip_z))  # 扇柄局部握点
grip_world = _fan_handle.matrix_world @ grip_local

# Step 3: 平移对齐（后平移）
shift = hand_pos - grip_world
_fan_handle.location += shift
# 注意：这里是世界空间平移，不受旋转影响
```

### 局部空间 vs 世界空间平移

```python
# 世界空间平移（不受物体旋转影响）
obj.location += Vector((1, 0, 0))  # 始终沿世界X

# 局部空间平移（受物体旋转影响）
obj.location += obj.matrix_world.to_3x3() @ Vector((1, 0, 0))  # 沿物体自身X

# 或通过matrix_basis
obj.matrix_basis.translation += Vector((1, 0, 0))  # 局部空间
```

## 常见陷阱

### 陷阱1：旋转后平移方向错误
```python
# 错误：期望沿物体前方移动，但用了世界坐标
obj.rotation_euler.z = math.radians(90)  # 旋转90°
obj.location.x += 1  # ← 沿世界X，不是物体前方！

# 正确：
forward = obj.matrix_world.to_3x3() @ Vector((0, -1, 0))  # 物体前方(-Y)
obj.location += forward
```

### 陷阱2：缩放影响平移
```python
# 如果矩阵包含缩放，平移量也会被缩放
M = T @ R @ S
# T中的平移不受S影响（因为T在最左边）

M2 = S @ T  # ← 平移被缩放！
```

## 本项目代码关联

`cel_shading.py`：
- L1707-1720: 扇柄旋转（Euler）
- L1725-1735: 握点对齐（世界空间平移）
- L1750-1780: 扇面旋转复制+连接点对齐

## 版本兼容性

- Blender 4.x/5.x: mathutils.Matrix API稳定
- Blender 5.1.0 Alpha: 测试通过

## 参考链接

- [Blender API: mathutils.Matrix](https://docs.blender.org/api/current/mathutils.html#mathutils.Matrix)
- [3D Math Primer: Transformation Matrices](https://gamemath.com/)
