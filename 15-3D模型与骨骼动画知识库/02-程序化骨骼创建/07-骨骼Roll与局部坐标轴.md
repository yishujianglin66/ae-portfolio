# 骨骼Roll与局部坐标轴

## 问题场景

程序化创建骨骼后，骨骼的局部X/Z轴方向可能不符合预期（如手臂骨骼的Z轴不朝前），导致旋转动画时手臂向错误方向弯曲。`roll`参数控制骨骼绕自身Y轴（head→tail方向）的旋转。

## 核心原理

### Roll的几何含义

```
骨骼Y轴 = normalize(tail - head)  ← 始终如此
骨骼X轴 = 由roll决定（绕Y轴旋转）
骨骼Z轴 = X × Y（右手定则）

roll = 0: X轴对齐世界X（如果骨骼沿Z方向）
roll = π/2: X轴旋转90°
```

### 计算正确Roll的方法

```python
from mathutils import Vector
import math

def calculate_roll_for_limb(head, tail, pole_target):
    """
    计算使骨骼Z轴指向pole_target的roll值
    pole_target: 膝盖/手肘应该朝向的方向点
    """
    bone_dir = (tail - head).normalized()
    
    # 期望的Z轴方向（朝向pole）
    desired_z = (pole_target - head).normalized()
    
    # 去除Y分量（投影到垂直于骨骼的平面）
    desired_z -= bone_dir * desired_z.dot(bone_dir)
    desired_z.normalize()
    
    # 计算当前Z轴（roll=0时）与期望Z轴的夹角
    # 这就是需要的roll值
    # 使用atan2确保方向正确
    current_z = Vector((0, 0, 1))  # 简化：假设初始Z朝上
    current_z -= bone_dir * current_z.dot(bone_dir)
    current_z.normalize()
    
    # 叉积确定方向
    cross = current_z.cross(desired_z)
    angle = current_z.angle(desired_z)
    if cross.dot(bone_dir) < 0:
        angle = -angle
    
    return angle

# 使用示例：膝盖朝前（-Y方向）
roll = calculate_roll_for_limb(
    head=Vector((0.5, 0, 3.0)),   # 大腿head
    tail=Vector((0.5, 0, 1.5)),   # 大腿tail（膝盖）
    pole_target=Vector((0.5, -2, 3.0))  # 膝盖朝前
)
```

### Blender的自动Roll计算

```python
import bpy

def auto_align_roll(edit_bone, align_to='Z', axis='Z'):
    """使用Blender内置的roll对齐"""
    # 方法1：对齐到全局轴
    edit_bone.align_roll(Vector((0, 0, 1)))  # Z轴朝上
    
    # 方法2：对齐到向量
    edit_bone.align_roll(Vector((0, -1, 0)))  # Z轴朝前(-Y)
```

### 各骨骼推荐Roll值

| 骨骼 | 推荐Roll | 原因 |
|------|----------|------|
| Spine/Chest/Neck/Head | 0 | Z轴朝前（-Y方向） |
| UpperArm_L | +π/2 | 手肘朝后 |
| UpperArm_R | -π/2 | 手肘朝后（镜像） |
| UpperLeg_L/R | 0 | 膝盖朝前 |
| Hand_L/R | 与ForeArm一致 | 保持连续 |

## 常见陷阱

### 陷阱1：左右对称骨骼Roll不镜像
```python
# 错误：左右臂使用相同roll
upper_arm_l.roll = math.pi / 2
upper_arm_r.roll = math.pi / 2  # ← 右臂弯曲方向错误！

# 正确：镜像roll
upper_arm_l.roll = math.pi / 2
upper_arm_r.roll = -math.pi / 2
```

### 陷阱2：修改head/tail后忘记重算roll
```python
# 修改tail位置后，roll含义改变（因为Y轴方向变了）
eb.tail = new_tail  # Y轴改变
eb.roll = 0  # ← 必须重新设置roll
```

## 本项目代码关联

`cel_shading.py` L870-920：骨骼创建时未显式设置roll（使用默认值0），因为本项目采用A-pose保持策略，不需要精确的骨骼轴向（动画仅用相机环绕）。

## 版本兼容性

- Blender 4.x/5.x: `align_roll()` API稳定
- Blender 5.1.0 Alpha: 测试通过

## 参考链接

- [Blender API: EditBone.align_roll](https://docs.blender.org/api/current/bpy.types.EditBone.html#bpy.types.EditBone.align_roll)
- [Rigify Roll Convention](https://wiki.blender.org/wiki/Reference/Release_Notes)
