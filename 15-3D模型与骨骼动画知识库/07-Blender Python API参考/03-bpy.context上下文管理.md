# bpy.context上下文管理

## 问题场景

`bpy.context`提供当前操作环境的上下文信息：活动对象、选中对象、场景、视图层等。许多操作依赖正确的context设置，background模式下context可能不完整。

## 核心原理

### Context主要属性

```python
import bpy

# 场景相关
bpy.context.scene           # 当前场景
bpy.context.view_layer      # 当前视图层
bpy.context.collection      # 当前集合

# 对象相关
bpy.context.object          # 活动对象（同active_object）
bpy.context.active_object   # 活动对象
bpy.context.selected_objects  # 选中对象列表
bpy.context.view_layer.objects  # 视图层中的所有对象

# 编辑相关
bpy.context.mode            # 当前模式（'OBJECT', 'EDIT_MESH', 'POSE'等）
bpy.context.edit_object     # 编辑模式中的对象
bpy.context.active_bone     # 活动骨骼（编辑模式）
bpy.context.active_pose_bone  # 活动PoseBone（姿态模式）

# 数据相关
bpy.context.object.data     # 活动对象的数据
bpy.context.mesh            # 编辑模式中的网格
bpy.context.armature        # 编辑模式中的骨骼
```

### 设置活动对象

```python
# 设置活动对象（很多ops依赖此设置）
obj = bpy.data.objects["MyObject"]
bpy.context.view_layer.objects.active = obj

# 设置选中状态
obj.select_set(True)   # 选中
obj.select_set(False)  # 取消选中

# 检查选中状态
is_selected = obj.select_get()

# 批量选中
for obj in objects_list:
    obj.select_set(True)
```

### Context覆盖（temp_override）

```python
# Blender 3.2+ 推荐使用temp_override
# 临时修改context执行操作

# 示例：对非活动对象应用变换
target_obj = bpy.data.objects["Target"]

with bpy.context.temp_override(
    object=target_obj,
    active_object=target_obj,
    selected_objects=[target_obj],
    selected_editable_objects=[target_obj],
):
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# 示例：在特定区域执行ops
# （background模式下通常不需要）
```

### 模式切换

```python
# 切换对象模式
bpy.ops.object.mode_set(mode='OBJECT')   # 对象模式
bpy.ops.object.mode_set(mode='EDIT')     # 编辑模式
bpy.ops.object.mode_set(mode='POSE')     # 姿态模式（骨骼）
bpy.ops.object.mode_set(mode='SCULPT')   # 雕刻模式

# 检查当前模式
print(bpy.context.mode)  # 'OBJECT', 'EDIT_MESH', 'POSE'等

# 注意：模式切换需要活动对象
bpy.context.view_layer.objects.active = armature_obj
bpy.ops.object.mode_set(mode='EDIT')  # 进入骨骼编辑模式
```

### Depsgraph（依赖图）

```python
# 获取求值后的数据（包含修改器效果）
depsgraph = bpy.context.evaluated_depsgraph_get()

# 获取求值后的对象
obj_eval = obj.evaluated_get(depsgraph)

# 获取修改器应用后的网格
mesh_eval = obj_eval.to_mesh()
# 使用后必须释放！
obj_eval.to_mesh_clear()

# 示例：获取Armature变形后的顶点位置
def get_deformed_vertices(obj):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    obj_eval = obj.evaluated_get(depsgraph)
    mesh = obj_eval.to_mesh()
    
    vertices = [v.co.copy() for v in mesh.vertices]
    
    obj_eval.to_mesh_clear()
    return vertices
```

### 场景与视图层

```python
# 多场景管理
scene = bpy.context.scene
print(f"Current scene: {scene.name}")

# 视图层
view_layer = bpy.context.view_layer
print(f"Current view layer: {view_layer.name}")

# LayerCollection（控制集合可见性）
layer_col = view_layer.layer_collection
for child in layer_col.children:
    print(f"  Collection: {child.name}, exclude={child.exclude}")
    child.exclude = True  # 隐藏该集合
```

### 屏幕与区域（GUI模式）

```python
# 以下属性仅在GUI模式可用
# background模式下为None或空

# 3D视图区域
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        for region in area.regions:
            if region.type == 'WINDOW':
                # 3D视图区域
                pass

# background模式检测
import bpy
is_background = bpy.app.background  # True/False
```

## 常见陷阱

### 陷阱1：活动对象为None
```python
# 错误：没有活动对象时调用ops
bpy.ops.object.mode_set(mode='EDIT')  # RuntimeError!

# 正确：先设置活动对象
bpy.context.view_layer.objects.active = obj
bpy.ops.object.mode_set(mode='EDIT')
```

### 陷阱2：selected_objects包含不可编辑对象
```python
# 隐藏/锁定的对象可能被选中但不可编辑
editable = [o for o in bpy.context.selected_objects 
            if o.select_get() and not o.hide_get()]
```

### 陷阱3：to_mesh后未释放
```python
# 错误：内存泄漏
mesh = obj_eval.to_mesh()
# 使用后没有释放！

# 正确：
mesh = obj_eval.to_mesh()
# ... 使用mesh ...
obj_eval.to_mesh_clear()  # 必须释放！
```

## 本项目代码关联

`cel_shading.py`：
- L50-100: 导入后设置活动对象
- L850-900: 骨骼编辑模式切换
- L950-1000: Depsgraph获取变形后顶点

## 版本兼容性

- Blender 3.2+: `temp_override()`可用
- Blender 4.x/5.x: context API稳定
- background模式：screen/area相关属性不可用

## 参考链接

- [Blender Python API: bpy.context](https://docs.blender.org/api/current/bpy.context.html)
- [Blender Manual: Context](https://docs.blender.org/api/current/info_gotcha.html#context)
