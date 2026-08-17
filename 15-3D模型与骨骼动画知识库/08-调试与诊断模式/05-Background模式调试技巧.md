# Background模式调试技巧

## 问题场景

Blender background模式（`--background`）无GUI，无法使用视口交互调试。需要特殊的调试技巧：脚本化检查、状态dump、生成调试图像等。

## 核心原理

### Background模式特点

```python
import bpy

# 检测background模式
is_background = bpy.app.background  # True

# Background模式限制：
# - 无3D视口
# - 无UI面板
# - 部分ops不可用（view3d.*, screen.*）
# - 无法交互式调试

# 但仍可以：
# - 执行渲染
# - 操作数据
# - 输出图像
# - 打印日志
```

### 视口截图（调试用）

```python
def render_debug_view(output_path, resolution=(800, 600)):
    """渲染当前视图用于调试"""
    scene = bpy.context.scene
    
    # 保存原始设置
    orig_x = scene.render.resolution_x
    orig_y = scene.render.resolution_y
    orig_path = scene.render.filepath
    
    # 设置调试分辨率
    scene.render.resolution_x = resolution[0]
    scene.render.resolution_y = resolution[1]
    scene.render.filepath = output_path
    
    # 渲染单帧
    bpy.ops.render.render(write_still=True)
    
    # 恢复设置
    scene.render.resolution_x = orig_x
    scene.render.resolution_y = orig_y
    scene.render.filepath = orig_path
    
    print(f"[DEBUG] View rendered to {output_path}")
```

### 多角度调试渲染

```python
import math

def render_debug_views(output_dir, obj_center, distance=5):
    """从多个角度渲染调试图"""
    import os
    os.makedirs(output_dir, exist_ok=True)
    
    scene = bpy.context.scene
    
    # 创建/获取调试相机
    cam_data = bpy.data.cameras.new("DebugCam")
    cam_obj = bpy.data.objects.new("DebugCam", cam_data)
    bpy.context.collection.objects.link(cam_obj)
    scene.camera = cam_obj
    
    # 6个角度
    angles = [
        ("front", (0, -distance, 1)),
        ("back", (0, distance, 1)),
        ("left", (-distance, 0, 1)),
        ("right", (distance, 0, 1)),
        ("top", (0, 0, distance)),
        ("perspective", (distance*0.7, -distance*0.7, distance*0.5)),
    ]
    
    for name, offset in angles:
        cam_obj.location = (
            obj_center[0] + offset[0],
            obj_center[1] + offset[1],
            obj_center[2] + offset[2],
        )
        
        # 看向中心
        direction = Vector(obj_center) - cam_obj.location
        rot_quat = direction.to_track_quat('-Z', 'Y')
        cam_obj.rotation_euler = rot_quat.to_euler()
        
        # 渲染
        output_path = os.path.join(output_dir, f"debug_{name}.png")
        scene.render.filepath = output_path
        bpy.ops.render.render(write_still=True)
        print(f"[DEBUG] {name} view: {output_path}")
    
    # 清理调试相机
    bpy.data.objects.remove(cam_obj, do_unlink=True)
```

### 场景状态文本dump

```python
def dump_scene_info():
    """打印完整场景信息"""
    print("\n" + "="*60)
    print("SCENE STATE DUMP")
    print("="*60)
    
    # 对象列表
    print(f"\n[Objects: {len(bpy.data.objects)}]")
    for obj in bpy.data.objects:
        print(f"  {obj.name} ({obj.type})")
        print(f"    Location: {obj.location[:]}")
        print(f"    Rotation: {obj.rotation_euler[:]}")
        print(f"    Scale: {obj.scale[:]}")
        
        if obj.type == 'MESH':
            mesh = obj.data
            print(f"    Vertices: {len(mesh.vertices)}")
            print(f"    Faces: {len(mesh.polygons)}")
            print(f"    Materials: {[m.name for m in mesh.materials if m]}")
        
        if obj.type == 'ARMATURE':
            print(f"    Bones: {len(obj.data.bones)}")
        
        if obj.parent:
            print(f"    Parent: {obj.parent.name}")
    
    # 渲染设置
    scene = bpy.context.scene
    print(f"\n[Render Settings]")
    print(f"  Engine: {scene.render.engine}")
    print(f"  Resolution: {scene.render.resolution_x}x{scene.render.resolution_y}")
    print(f"  Frame: {scene.frame_current}/{scene.frame_end}")
    print(f"  Camera: {scene.camera.name if scene.camera else 'None'}")
    
    print("="*60 + "\n")
```

### 生成调试网格

```python
def create_debug_marker(name, location, size=0.1, color=(1, 0, 0)):
    """创建调试标记（小球）"""
    # 创建UV球
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=size, location=location)
    marker = bpy.context.active_object
    marker.name = f"DEBUG_{name}"
    
    # 红色材质
    mat = bpy.data.materials.new(f"DebugMat_{name}")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    if bsdf:
        bsdf.inputs['Base Color'].default_value = (*color, 1)
        bsdf.inputs['Emission Strength'].default_value = 1.0
        bsdf.inputs['Emission Color'].default_value = (*color, 1)
    marker.data.materials.append(mat)
    
    # 不渲染（仅视口）
    marker.hide_render = True
    
    return marker

def create_debug_line(name, start, end, color=(0, 1, 0)):
    """创建调试线段"""
    # 使用曲线
    curve = bpy.data.curves.new(f"DebugLine_{name}", 'CURVE')
    curve.dimensions = '3D'
    
    spline = curve.splines.new('POLY')
    spline.points.add(1)  # 默认1个点，再加1个
    spline.points[0].co = (*start, 1)
    spline.points[1].co = (*end, 1)
    
    obj = bpy.data.objects.new(f"DEBUG_LINE_{name}", curve)
    bpy.context.collection.objects.link(obj)
    obj.hide_render = True
    
    return obj

# 使用：标记手部位置
create_debug_marker("hand", hand_position, color=(1, 0, 0))
create_debug_line("weapon_offset", weapon_pos, hand_position)
```

### 条件断点

```python
# 在脚本中设置条件断点
DEBUG_BREAK = False  # 通过环境变量控制
import os
if os.environ.get('BLENDER_DEBUG_BREAK') == '1':
    DEBUG_BREAK = True

def debug_break(condition, msg=""):
    """条件断点"""
    if DEBUG_BREAK and condition:
        print(f"\n[BREAK] {msg}")
        dump_scene_info()
        # 在background模式下无法真正暂停
        # 但可以输出详细状态后退出
        import sys
        sys.exit(1)

# 使用
debug_break(
    weapon.location.z < 0, 
    f"Weapon below ground: {weapon.location}"
)
```

### 增量调试

```python
# 将大脚本分成多个阶段，逐步执行
# stage1.py: 只执行导入
# stage2.py: 导入 + 骨骼
# stage3.py: 导入 + 骨骼 + 权重
# ...

# 通过命令行参数控制
import sys
argv = sys.argv
stage = int(argv[argv.index('--stage') + 1]) if '--stage' in argv else 99

if stage >= 1:
    import_fbx()
if stage >= 2:
    create_bones()
if stage >= 3:
    assign_weights()
# ...

# 运行：
# blender --background --python script.py -- --stage 2
```

## 常见陷阱

### 陷阱1：view3d ops不可用
```python
# 错误：background模式无3D视图
bpy.ops.view3d.view_all()  # RuntimeError!

# 替代：直接设置相机
```

### 陷阱2：调试代码忘记删除
```python
# 调试标记会影响正式渲染
# 解决：使用hide_render=True
# 或：调试代码放在if DEBUG块中
```

## 本项目代码关联

`cel_shading.py`：
- 大量print调试输出
- 状态dump

`engine.py`：
- 分阶段执行
- 错误后dump状态

## 版本兼容性

- Background模式所有版本通用
- 调试技巧与版本无关

## 参考链接

- [Blender Command Line](https://docs.blender.org/manual/en/latest/advanced/command_line/index.html)
