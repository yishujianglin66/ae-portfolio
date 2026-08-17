# bpy.ops常用操作速查

## 问题场景

`bpy.ops`是Blender的Operator系统，封装了几乎所有用户界面操作。脚本中频繁使用ops进行对象操作、编辑、渲染等。但ops依赖context，background模式下部分ops不可用。

## 核心原理

### Operator基本结构

```python
import bpy

# bpy.ops的层级结构：
# bpy.ops.<模块>.<操作符>(参数)

# 常用模块：
# bpy.ops.object    - 对象操作
# bpy.ops.mesh      - 网格编辑
# bpy.ops.armature  - 骨骼编辑
# bpy.ops.render    - 渲染
# bpy.ops.import_scene / export_scene - 导入导出
# bpy.ops.transform - 变换
# bpy.ops.view3d    - 3D视图
```

### 对象操作

```python
# 选择
bpy.ops.object.select_all(action='SELECT')   # 全选
bpy.ops.object.select_all(action='DESELECT') # 取消全选

# 删除
bpy.ops.object.delete(use_global=False)  # 删除选中

# 添加
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 0))
bpy.ops.object.camera_add(location=(0, -5, 2))
bpy.ops.object.light_add(type='AREA', location=(3, -3, 5))

# 复制
bpy.ops.object.duplicate(linked=False)  # 独立复制
bpy.ops.object.duplicate(linked=True)   # 链接复制（共享数据）

# 应用变换
bpy.ops.object.transform_apply(
    location=True, rotation=True, scale=True)

# Parent设置
bpy.ops.object.parent_set(type='OBJECT')  # 物体Parent
bpy.ops.object.parent_set(type='BONE')    # 骨骼Parent
bpy.ops.object.parent_clear(type='CLEAR') # 清除Parent

# 连接/分离
bpy.ops.object.join()  # 合并选中物体
```

### 编辑模式操作

```python
# 进入/退出编辑模式
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.mode_set(mode='POSE')  # 姿态模式（骨骼）

# 网格编辑（需要EDIT模式）
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.remove_doubles(threshold=0.0001)  # 合并顶点
bpy.ops.mesh.normals_make_consistent()  # 统一法线
bpy.ops.mesh.separate(type='LOOSE')  # 按松散部分分离

# 骨骼编辑（需要EDIT模式）
bpy.ops.armature.bone_primitive_add(name="Bone")
bpy.ops.armature.parent_set(type='CONNECTED')
bpy.ops.armature.select_all(action='SELECT')
```

### 渲染操作

```python
# 渲染单帧
bpy.ops.render.render(write_still=True)

# 渲染动画
bpy.ops.render.render(animation=True)

# 渲染当前视图
bpy.ops.render.opengl(animation=False)
```

### 导入导出

```python
# FBX导入
bpy.ops.import_scene.fbx(
    filepath="model.fbx",
    use_anim=False,
    ignore_leaf_bones=True,
    automatic_bone_orientation=True,
)

# FBX导出
bpy.ops.export_scene.fbx(
    filepath="output.fbx",
    use_selection=True,
    object_types={'MESH', 'ARMATURE'},
)

# OBJ导入（Blender 4.0+新API）
bpy.ops.wm.obj_import(filepath="model.obj")

# GLTF导入
bpy.ops.import_scene.gltf(filepath="model.glb")
```

### Context覆盖（重要）

```python
# 很多ops需要特定的context（如活动对象、编辑模式）
# background模式下可能缺少context

# 方法1：手动设置context
bpy.context.view_layer.objects.active = obj
obj.select_set(True)

# 方法2：使用context覆盖（Blender 3.2+）
with bpy.context.temp_override(
    active_object=obj,
    selected_objects=[obj],
    selected_editable_objects=[obj],
):
    bpy.ops.object.transform_apply(location=True)

# 方法3：直接操作数据（绕过ops）
obj.location = (0, 0, 0)  # 比ops.transform更可靠
```

### 常用ops速查表

| 操作 | API |
|------|-----|
| 全选 | `bpy.ops.object.select_all(action='SELECT')` |
| 删除 | `bpy.ops.object.delete()` |
| 合并物体 | `bpy.ops.object.join()` |
| 应用变换 | `bpy.ops.object.transform_apply()` |
| 设置Parent | `bpy.ops.object.parent_set(type='OBJECT')` |
| 进入编辑模式 | `bpy.ops.object.mode_set(mode='EDIT')` |
| 渲染动画 | `bpy.ops.render.render(animation=True)` |
| FBX导入 | `bpy.ops.import_scene.fbx(filepath=...)` |
| 添加骨骼 | `bpy.ops.armature.bone_primitive_add()` |

## 常见陷阱

### 陷阱1：ops需要活动对象
```python
# 错误：没有设置活动对象
bpy.ops.object.transform_apply()  # RuntimeError!

# 正确：
bpy.context.view_layer.objects.active = obj
bpy.ops.object.transform_apply()
```

### 陷阱2：编辑模式ops需要正确模式
```python
# 错误：在OBJECT模式调用mesh ops
bpy.ops.mesh.select_all()  # RuntimeError!

# 正确：
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all()
bpy.ops.object.mode_set(mode='OBJECT')
```

### 陷阱3：background模式部分ops不可用
```python
# 以下ops在background模式可能失败：
# bpy.ops.view3d.* （无3D视图）
# bpy.ops.screen.* （无屏幕）
# bpy.ops.wm.window_* （无窗口）

# 替代方案：直接操作数据
```

## 本项目代码关联

`cel_shading.py`：
- L50-100: FBX导入ops
- L850-870: 骨骼创建ops
- L1900-1950: 渲染ops

`engine.py`：
- subprocess调用包含ops的脚本

## 版本兼容性

- Blender 3.2+: `context.temp_override()`可用
- Blender 4.0+: OBJ导入API变更（`wm.obj_import`）
- Blender 5.1.0 Alpha: ops API基本稳定

## 参考链接

- [Blender Python API: bpy.ops](https://docs.blender.org/api/current/bpy.ops.html)
- [Blender Manual: Operators](https://docs.blender.org/manual/en/latest/interface/operators.html)
