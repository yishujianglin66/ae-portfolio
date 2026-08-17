# PoseBone动画控制（旋转/位移/IK）

## 问题场景

创建骨骼后需要通过PoseBone设置动画关键帧。直接修改`bone.head`无效（那是rest pose），必须通过`pose.bones[]`的`rotation_euler`/`location`属性驱动动画。

## 核心原理

### PoseBone的变换属性

```python
import bpy
import math

armature_obj = bpy.data.objects['Armature']
pose_bone = armature_obj.pose.bones['UpperArm_R']

# 旋转（欧拉角，弧度）
pose_bone.rotation_euler = (math.radians(30), 0, 0)  # X轴旋转30°

# 旋转（四元数）
pose_bone.rotation_mode = 'QUATERNION'
pose_bone.rotation_quaternion = (1, 0, 0, 0)  # w,x,y,z

# 位移（局部空间）
pose_bone.location = (0, 0.1, 0)  # 沿骨骼Y轴移动0.1

# 缩放
pose_bone.scale = (1, 1, 1)
```

### 关键帧插入

```python
import bpy

def add_rotation_keyframe(armature_obj, bone_name, frame, rotation):
    """为骨骼添加旋转关键帧"""
    pb = armature_obj.pose.bones[bone_name]
    pb.rotation_euler = rotation
    pb.keyframe_insert(data_path="rotation_euler", frame=frame)

def add_location_keyframe(armature_obj, bone_name, frame, location):
    """为骨骼添加位移关键帧"""
    pb = armature_obj.pose.bones[bone_name]
    pb.location = location
    pb.keyframe_insert(data_path="location", frame=frame)

# 使用示例：手臂摆动动画
for frame in range(1, 61):
    t = frame / 60.0  # 0~1
    angle = math.sin(t * math.pi * 2) * math.radians(15)  # ±15°摆动
    add_rotation_keyframe(arm_obj, 'UpperArm_R', frame, (angle, 0, 0))
```

### 旋转模式选择

| 模式 | 属性 | 适用场景 | 万向锁 |
|------|------|----------|--------|
| EULER (XYZ) | rotation_euler | 单轴简单旋转 | 有 |
| QUATERNION | rotation_quaternion | 多轴复合旋转 | 无 |
| AXIS_ANGLE | rotation_axis_angle | 绕特定轴旋转 | 无 |

```python
# 推荐：复杂动画用四元数
pb.rotation_mode = 'QUATERNION'

# 从欧拉角转换
from mathutils import Euler
euler = Euler((math.radians(30), math.radians(-45), 0), 'XYZ')
quat = euler.to_quaternion()
pb.rotation_quaternion = quat
```

### IK约束（反向运动学）

```python
def setup_ik(armature_obj, chain_bone, target_obj, target_bone=None):
    """
    为骨骼链添加IK约束
    chain_bone: 链末端骨骼（如Hand_R）
    target_obj: IK目标对象
    """
    pb = armature_obj.pose.bones[chain_bone]
    
    # 添加IK约束
    ik = pb.constraints.new(type='IK')
    ik.target = target_obj
    if target_bone:
        ik.subtarget = target_bone
    ik.chain_count = 3  # 影响3根骨骼（Hand→ForeArm→UpperArm）
    ik.use_stretch = False
    
    # 设置pole target（控制手肘方向）
    # ik.pole_target = pole_obj
    # ik.pole_subtarget = 'Pole_R'
    # ik.pole_angle = math.radians(90)
    
    return ik
```

### 获取PoseBone的世界矩阵

```python
def get_bone_world_matrix(armature_obj, bone_name):
    """获取骨骼当前姿态的世界变换矩阵"""
    bpy.context.view_layer.update()
    
    pb = armature_obj.pose.bones[bone_name]
    
    # 方法1：armature世界矩阵 × pose bone矩阵
    world_mat = armature_obj.matrix_world @ pb.matrix
    
    # 方法2：直接获取（等价）
    # world_mat = pb.matrix  ← 仅在armature无变换时正确
    
    return world_mat

def get_bone_tail_world(armature_obj, bone_name):
    """获取骨骼TAIL的世界坐标"""
    pb = armature_obj.pose.bones[bone_name]
    bone_length = pb.bone.length
    
    # TAIL = HEAD + Y轴方向 × 长度
    from mathutils import Vector
    tail_local = pb.matrix @ Vector((0, bone_length, 0))
    tail_world = armature_obj.matrix_world @ tail_local
    
    return tail_world
```

## 常见陷阱

### 陷阱1：在OBJECT模式设置pose无效
```python
# 错误：需要先确保armature是活动对象
bpy.context.view_layer.objects.active = armature_obj
# 然后才能设置pose.bones的值（不需要进入POSE模式）
armature_obj.pose.bones['Head'].rotation_euler = (0.1, 0, 0)
bpy.context.view_layer.update()  # ← 必须更新！
```

### 陷阱2：keyframe_insert的data_path错误
```python
# 错误：
pb.keyframe_insert("rotation")  # ← 属性不存在

# 正确：
pb.keyframe_insert(data_path="rotation_euler", frame=1)
pb.keyframe_insert(data_path="rotation_quaternion", frame=1)
pb.keyframe_insert(data_path="location", frame=1)
```

## 本项目代码关联

`cel_shading.py` L894-926：
- v12策略保持A-pose，不使用骨骼动画
- 动画通过相机环绕实现（非PoseBone旋转）
- 但发冠归位使用了`pose.bones.get('Head')`获取Head骨骼矩阵

## 版本兼容性

- Blender 4.x/5.x: PoseBone API稳定
- Blender 5.1.0 Alpha: 测试通过

## 参考链接

- [Blender API: PoseBone](https://docs.blender.org/api/current/bpy.types.PoseBone.html)
- [Blender API: IK Constraint](https://docs.blender.org/api/current/bpy.types.KinematicConstraint.html)
