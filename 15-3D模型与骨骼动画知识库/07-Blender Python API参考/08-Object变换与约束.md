# Object变换与约束

## 问题场景

Object的变换（位置、旋转、缩放）和约束（Constraint）是控制物体运动的核心。三渲二管线中需要设置相机约束（Track To）、物体跟随骨骼（Child Of）等。

## 核心原理

### 变换属性

```python
import bpy
from mathutils import Vector, Euler, Quaternion, Matrix
import math

obj = bpy.data.objects["MyObject"]

# 位置（Location）
obj.location = (1.0, 2.0, 3.0)  # 世界坐标（无Parent时）
obj.location.x = 1.0
obj.location = Vector((0, 0, 0))

# 旋转（Rotation）- 三种表示
obj.rotation_euler = (0, 0, math.radians(45))  # 欧拉角
obj.rotation_quaternion = Quaternion((1, 0, 0, 0))  # 四元数
obj.rotation_axis_angle = (0, 0, 1, math.radians(45))  # 轴角

# 缩放（Scale）
obj.scale = (1.0, 1.0, 1.0)
obj.scale = Vector((2, 2, 2))  # 统一缩放2倍

# 变换模式
obj.rotation_mode = 'XYZ'      # 欧拉角顺序
obj.rotation_mode = 'QUATERNION'  # 四元数
```

### 矩阵变换

```python
# 变换矩阵
obj.matrix_world      # 世界变换矩阵（4x4）
obj.matrix_local      # 局部变换矩阵（相对Parent）
obj.matrix_parent_inverse  # Parent逆矩阵
obj.matrix_basis      # 基础变换（location/rotation/scale组合）

# 从矩阵提取
loc, rot, scale = obj.matrix_world.decompose()
print(f"Location: {loc}")
print(f"Rotation: {rot.to_euler()}")
print(f"Scale: {scale}")

# 设置矩阵
obj.matrix_world = Matrix.Translation((1, 2, 3))
```

### 约束系统

```python
# 添加约束
constraint = obj.constraints.new(type='TRACK_TO')

# 常用约束类型：
# 'TRACK_TO'      - 追踪目标（相机看向物体）
# 'COPY_LOCATION' - 复制位置
# 'COPY_ROTATION' - 复制旋转
# 'COPY_TRANSFORMS' - 复制全部变换
# 'CHILD_OF'      - 子级（类似Parent但可动画）
# 'LIMIT_LOCATION' - 限制位置
# 'LIMIT_ROTATION' - 限制旋转
# 'IK'            - 反向运动学
# 'FLOOR'         - 地面约束
# 'SHRINKWRAP'    - 缩裹

# 删除约束
obj.constraints.remove(constraint)

# 遍历约束
for c in obj.constraints:
    print(f"{c.name}: {c.type}")
```

### Track To约束（相机追踪）

```python
def setup_camera_track(camera_obj, target_obj):
    """相机始终看向目标"""
    # 方法1：使用约束
    track = camera_obj.constraints.new(type='TRACK_TO')
    track.target = target_obj
    track.track_axis = 'TRACK_NEGATIVE_Z'  # 相机朝向-Z
    track.up_axis = 'UP_Y'                 # 上方为Y
    
    # 方法2：每帧手动设置（更灵活）
    # 见相机环绕动画文档

# 方法3：直接计算（无约束）
def look_at(obj, target):
    """物体看向目标点"""
    direction = target - obj.location
    rot_quat = direction.to_track_quat('-Z', 'Y')
    obj.rotation_euler = rot_quat.to_euler()
```

### Child Of约束（动态Parent）

```python
def setup_child_of(child_obj, parent_obj, bone_name=None):
    """使用Child Of约束（可动画的Parent）"""
    constraint = child_obj.constraints.new(type='CHILD_OF')
    constraint.target = parent_obj
    
    if bone_name:
        constraint.subtarget = bone_name  # 跟随特定骨骼
    
    # 设置逆矩阵（保持当前位置）
    # 需要先调用Set Inverse
    bpy.context.view_layer.objects.active = child_obj
    bpy.ops.constraint.childof_set_inverse(
        constraint=constraint.name,
        owner='OBJECT'
    )
    
    return constraint

# Child Of vs Parent的区别：
# - Parent: 静态关系，设置后固定
# - Child Of: 动态约束，可以动画化influence
```

### Copy Transforms约束

```python
def copy_transforms(obj, target_obj):
    """完全复制目标物体的变换"""
    constraint = obj.constraints.new(type='COPY_TRANSFORMS')
    constraint.target = target_obj
    constraint.target_space = 'WORLD'
    constraint.owner_space = 'WORLD'
```

### 约束动画

```python
# 约束的influence可以动画化
constraint = obj.constraints["Track To"]

# 设置关键帧
constraint.influence = 1.0
constraint.keyframe_insert("influence", frame=1)

constraint.influence = 0.0
constraint.keyframe_insert("influence", frame=30)

# 效果：前30帧逐渐停止追踪
```

### 变换应用与冻结

```python
# 应用变换（将变换"烘焙"到网格）
bpy.context.view_layer.objects.active = obj
bpy.ops.object.transform_apply(
    location=True,
    rotation=True,
    scale=True
)

# 应用后：
# obj.location = (0, 0, 0)
# obj.rotation_euler = (0, 0, 0)
# obj.scale = (1, 1, 1)
# 但网格顶点已更新

# 注意：应用变换会破坏Parent关系的某些情况
```

## 常见陷阱

### 陷阱1：有Parent时location是局部坐标
```python
# 有Parent时，obj.location是相对Parent的局部坐标
# 获取世界坐标：
world_loc = obj.matrix_world.translation

# 设置世界坐标：
obj.matrix_world.translation = Vector((1, 2, 3))
```

### 陷阱2：约束顺序影响结果
```python
# 约束按列表顺序应用
# 后面的约束在前面的基础上
# 调整顺序：
obj.constraints.move(from_index, to_index)
```

### 陷阱3：Child Of未设置逆矩阵
```python
# 添加Child Of后物体会跳到目标位置
# 解决：设置逆矩阵保持原位
bpy.ops.constraint.childof_set_inverse(...)
```

## 本项目代码关联

`cel_shading.py`：
- 相机使用直接计算look_at（无约束）
- 武器使用Parent而非Child Of

`engine.py`：
- 物体变换验证

## 版本兼容性

- Blender 4.x/5.x: 约束API稳定
- Blender 5.1.0 Alpha: 无重大变更

## 参考链接

- [Blender Manual: Constraints](https://docs.blender.org/manual/en/latest/animation/constraints/index.html)
- [Blender Python API: Object](https://docs.blender.org/api/current/bpy.types.Object.html)
