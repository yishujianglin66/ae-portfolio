# Animation与Keyframe

## 问题场景

Blender的动画系统基于关键帧（Keyframe）和F-Curve。三渲二管线中需要为相机创建环绕动画、为骨骼创建姿态动画、为约束创建influence动画等。

## 核心原理

### 关键帧基础

```python
import bpy

obj = bpy.data.objects["Camera"]

# 插入关键帧
obj.location = (5, 0, 2)
obj.keyframe_insert(data_path="location", frame=1)

obj.location = (0, 5, 2)
obj.keyframe_insert(data_path="location", frame=30)

# 常用data_path：
# "location"          - 位置
# "rotation_euler"    - 欧拉旋转
# "rotation_quaternion" - 四元数旋转
# "scale"             - 缩放
# "constraints[\"Name\"].influence" - 约束影响

# 指定索引（单个分量）
obj.keyframe_insert(data_path="location", index=0, frame=1)  # 只X
```

### F-Curve访问

```python
# 获取动画数据
anim_data = obj.animation_data
if anim_data and anim_data.action:
    action = anim_data.action
    
    # 遍历F-Curves
    for fcurve in action.fcurves:
        print(f"{fcurve.data_path}[{fcurve.array_index}]")
        
        # 关键帧点
        for kp in fcurve.keyframe_points:
            print(f"  Frame {kp.co.x}: Value {kp.co.y}")
            print(f"    Interpolation: {kp.interpolation}")

# 创建Action
action = bpy.data.actions.new(name="CameraAnim")
obj.animation_data_create()
obj.animation_data.action = action
```

### 关键帧插值

```python
# 插值类型
# 'CONSTANT'  - 常数（阶梯）
# 'LINEAR'    - 线性
# 'BEZIER'    - 贝塞尔（默认，平滑）

# 设置插值
for fcurve in action.fcurves:
    for kp in fcurve.keyframe_points:
        kp.interpolation = 'LINEAR'
        
        # 贝塞尔手柄
        kp.handle_left_type = 'AUTO'
        kp.handle_right_type = 'AUTO'

# 批量设置
for fcurve in action.fcurves:
    for kp in fcurve.keyframe_points:
        kp.interpolation = 'BEZIER'
        kp.easing = 'EASE_IN_OUT'
```

### 相机环绕动画

```python
import math

def create_orbit_animation(cam_obj, center, radius, height, 
                           frame_start, frame_end):
    """创建相机环绕动画"""
    # 创建Action
    action = bpy.data.actions.new(name="Orbit")
    cam_obj.animation_data_create()
    cam_obj.animation_data.action = action
    
    total_frames = frame_end - frame_start
    
    for frame in range(frame_start, frame_end + 1):
        t = (frame - frame_start) / total_frames
        angle = t * 2 * math.pi  # 完整一圈
        
        # 位置
        x = center[0] + radius * math.cos(angle)
        y = center[1] + radius * math.sin(angle)
        z = height
        
        cam_obj.location = (x, y, z)
        cam_obj.keyframe_insert("location", frame=frame)
        
        # 旋转（看向中心）
        direction = Vector(center) - cam_obj.location
        rot_quat = direction.to_track_quat('-Z', 'Y')
        cam_obj.rotation_euler = rot_quat.to_euler()
        cam_obj.keyframe_insert("rotation_euler", frame=frame)
    
    # 设置循环（首尾相接）
    for fcurve in action.fcurves:
        # 添加Cycle修改器
        mod = fcurve.modifiers.new(type='CYCLES')
        mod.mode_before = 'REPEAT'
        mod.mode_after = 'REPEAT'
```

### 骨骼动画

```python
def create_pose_animation(arm_obj, poses, frame_step=10):
    """
    创建骨骼姿态动画
    poses: [{"bone_name": {"location": ..., "rotation": ...}}, ...]
    """
    action = bpy.data.actions.new(name="PoseAnim")
    arm_obj.animation_data_create()
    arm_obj.animation_data.action = action
    
    for i, pose in enumerate(poses):
        frame = 1 + i * frame_step
        
        for bone_name, transforms in pose.items():
            pose_bone = arm_obj.pose.bones.get(bone_name)
            if not pose_bone:
                continue
            
            if "location" in transforms:
                pose_bone.location = transforms["location"]
                pose_bone.keyframe_insert(
                    "location", frame=frame)
            
            if "rotation" in transforms:
                pose_bone.rotation_euler = transforms["rotation"]
                pose_bone.keyframe_insert(
                    "rotation_euler", frame=frame)
```

### NLA（非线性动画）

```python
# NLA允许混合多个Action
# 适合复杂动画序列

# 获取NLA轨道
nla_tracks = obj.animation_data.nla_tracks

# 创建轨道
track = nla_tracks.new()
track.name = "WalkCycle"

# 将Action推入轨道
action = bpy.data.actions["Walk"]
strip = track.strips.new("Walk", start=1, action=action)

# 混合
strip.blend_type = 'REPLACE'  # REPLACE/ADD/MULTIPLY
strip.influence = 1.0
```

### 驱动器（Driver）

```python
# 驱动器：用一个属性驱动另一个属性
# 示例：相机距离驱动FOV

# 添加驱动器
fcurve = cam_obj.driver_add("data.lens", 0)
driver = fcurve.driver

# 设置表达式
driver.type = 'SCRIPTED'
driver.expression = "50 - dist * 2"

# 添加变量
var = driver.variables.new()
var.name = "dist"
var.type = 'SINGLE_PROP'
target = var.targets[0]
target.id = cam_obj
target.data_path = "location.x"
```

### 动画播放控制

```python
scene = bpy.context.scene

# 帧控制
scene.frame_set(30)  # 跳转到第30帧（更新depsgraph）
scene.frame_current  # 当前帧

# 播放范围
scene.frame_start = 1
scene.frame_end = 100
scene.frame_preview_start = 1
scene.frame_preview_end = 50

# 播放设置
scene.sync_mode = 'FRAME_DROP'  # 跳帧保持时间
# scene.sync_mode = 'AUDIO_SYNC'  # 音频同步
```

## 常见陷阱

### 陷阱1：keyframe_insert需要活动对象
```python
# 对于某些data_path，需要设置活动对象
bpy.context.view_layer.objects.active = obj
obj.keyframe_insert("location", frame=1)
```

### 陷阱2：PoseBone的data_path
```python
# PoseBone关键帧的data_path包含骨骼名
pose_bone.keyframe_insert("location", frame=1)
# 实际data_path: pose.bones["BoneName"].location
```

### 陷阱3：动画循环不连续
```python
# 首尾帧值不同导致跳变
# 解决：确保frame_start和frame_end的值相同
# 或使用CYCLES修改器
```

## 本项目代码关联

`cel_shading.py` L400-500：
- 相机环绕动画创建
- 60帧完整圆周

## 版本兼容性

- Blender 4.x/5.x: Animation API稳定
- Blender 5.1.0 Alpha: 无重大变更

## 参考链接

- [Blender Manual: Animation](https://docs.blender.org/manual/en/latest/animation/index.html)
- [Blender Python API: Keyframe](https://docs.blender.org/api/current/bpy.types.Keyframe.html)
