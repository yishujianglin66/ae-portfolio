# Rotate-First扇子归位策略

## 问题场景

扇子由扇柄(handle)和扇面(blade)两个独立mesh组成，FBX中它们在地面(z=-6.2)。需要：(1)旋转扇柄到握持角度 (2)对齐握点到手部 (3)扇面跟随扇柄旋转 (4)扇面连接点对齐扇柄tip。

## 核心原理

### Rotate-First vs Translate-First

```
Translate-First（失败方案）：
1. 移动扇柄握点到手部 → 2. 旋转扇柄
问题：旋转后握点偏移（旋转中心不是握点）

Rotate-First（成功方案）：
1. 旋转扇柄到握持角度 → 2. 计算旋转后的握点 → 3. 平移对齐
优点：旋转不改变相对位置，平移精确对齐
```

### 完整实现

```python
import bpy
import math
from mathutils import Vector, Euler

def position_fan_rotate_first(fan_handle, fan_blade, hand_pos):
    """
    Rotate-First扇子归位
    fan_handle: 扇柄mesh
    fan_blade: 扇面mesh
    hand_pos: 手部世界坐标 (Vector)
    """
    bpy.context.view_layer.update()
    
    # === Step 1: 旋转扇柄到握持角度 ===
    # 扇子自然握持：X轴旋转70°（扇面朝上），Z轴旋转-45°（斜握）
    grip_rotation = Euler((math.radians(70), 0, math.radians(-45)), 'XYZ')
    fan_handle.rotation_euler = grip_rotation
    bpy.context.view_layer.update()
    
    # === Step 2: 计算旋转后的握点世界坐标 ===
    # 握点 = 扇柄的-X端（局部坐标）
    bbox = [Vector(v) for v in fan_handle.bound_box]
    grip_local = Vector((
        min(v.x for v in bbox),  # -X端
        sum(v.y for v in bbox) / 8,  # Y中心
        sum(v.z for v in bbox) / 8   # Z中心
    ))
    grip_world = fan_handle.matrix_world @ grip_local
    
    # === Step 3: 平移对齐握点到手部 ===
    shift = hand_pos - grip_world
    fan_handle.location += shift
    bpy.context.view_layer.update()
    
    print(f"[Fan] Handle grip_world: {grip_world.to_tuple()}")
    print(f"[Fan] Shift: ({shift.x:.2f}, {shift.y:.2f}, {shift.z:.2f})")
    
    # === Step 4: 扇面跟随扇柄旋转 ===
    fan_blade.rotation_euler = fan_handle.rotation_euler.copy()
    bpy.context.view_layer.update()
    
    # === Step 5: 扇面连接点对齐扇柄tip ===
    # 扇面连接点 = 扇面的-X端
    blade_bbox = [Vector(v) for v in fan_blade.bound_box]
    connect_local = Vector((
        min(v.x for v in blade_bbox),
        sum(v.y for v in blade_bbox) / 8,
        sum(v.z for v in blade_bbox) / 8
    ))
    connect_world = fan_blade.matrix_world @ connect_local
    
    # 扇柄tip = 扇柄的+X端
    handle_bbox_world = [fan_handle.matrix_world @ Vector(v) for v in fan_handle.bound_box]
    tip_world = Vector((
        max(v.x for v in handle_bbox_world),
        sum(v.y for v in handle_bbox_world) / 8,
        sum(v.z for v in handle_bbox_world) / 8
    ))
    
    # 平移扇面
    blade_shift = tip_world - connect_world
    fan_blade.location += blade_shift
    bpy.context.view_layer.update()
    
    print(f"[Fan] Blade shift: ({blade_shift.x:.2f}, {blade_shift.y:.2f}, {blade_shift.z:.2f})")
    
    # === Step 6: Parent组装 ===
    fan_blade.parent = fan_handle  # 扇面→扇柄
    # 后续扇柄parent到armature
```

### 上官婉儿的实际数据

```
v12第3次运行：
- 扇柄旋转: (70°, 0°, -45°)
- 握点grip_world: (-0.6, 0.7, -2.72)（与手部检测一致）
- 扇柄shift: (X+0.54, Y-0.98, Z+3.52)
- 扇面shift: (X+0.09, Y+5.43, Z+1.83)
- 结果：扇子贴合右手，扇面朝上展开
```

## 常见陷阱

### 陷阱1：握点计算用局部坐标而非世界坐标
```python
# 错误：旋转后局部坐标不变，但世界坐标变了
grip_local = Vector((-0.5, 0, 0))
# 必须转换：
grip_world = fan_handle.matrix_world @ grip_local
```

### 陷阱2：扇面旋转与扇柄不一致
```python
# 必须复制完全相同的rotation_euler
fan_blade.rotation_euler = fan_handle.rotation_euler.copy()
# 不能只复制部分轴
```

## 本项目代码关联

`cel_shading.py` L1707-1791：
- L1707-1720: 扇柄旋转(70°, -45°)
- L1725-1735: 握点对齐
- L1750-1780: 扇面旋转+连接点对齐

## 版本兼容性

- Blender 4.x/5.x: rotation_euler/location API稳定
- Blender 5.1.0 Alpha: 测试通过

## 参考链接

- [Blender API: Object.rotation_euler](https://docs.blender.org/api/current/bpy.types.Object.html)
