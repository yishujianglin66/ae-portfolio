# Blender 4.x vs 5.x API差异

## 问题场景

Blender版本迭代中API会发生变化：废弃旧接口、引入新功能、修改默认值。本项目使用Blender 5.1.0 Alpha，需要注意与4.x的差异，避免deprecated警告和兼容性问题。

## 核心原理

### 版本检测方法

```python
import bpy

# 获取版本
version = bpy.app.version  # (major, minor, patch)
version_string = bpy.app.version_string  # "5.1.0 Alpha"

print(f"Blender {bpy.app.version_string}")
print(f"Version tuple: {bpy.app.version}")

# 版本检查
if bpy.app.version >= (4, 2, 0):
    # 4.2+ 代码
    pass

if bpy.app.version >= (5, 0, 0):
    # 5.0+ 代码
    pass

# 构建日期
print(f"Build date: {bpy.app.build_date}")
print(f"Build hash: {bpy.app.build_hash}")
```

### EEVEE变更（4.2+）

```python
# Blender 4.2+: EEVEE Next（重写版）
# 旧版EEVEE渲染引擎标识符变更

# 4.0-4.1:
scene.render.engine = 'BLENDER_EEVEE'

# 4.2+:
scene.render.engine = 'BLENDER_EEVEE_NEXT'

# 兼容处理
def set_eevee_engine(scene):
    if bpy.app.version >= (4, 2, 0):
        scene.render.engine = 'BLENDER_EEVEE_NEXT'
    else:
        scene.render.engine = 'BLENDER_EEVEE'

# EEVEE设置变更
# 4.x: scene.eevee.use_ssr, use_gtao, use_bloom
# 5.x: 部分设置移除或重命名
```

### Grease Pencil变更（4.0+）

```python
# Blender 4.0+: Grease Pencil成为独立对象类型

# 3.x: Grease Pencil数据附加到对象
# obj.grease_pencil = bpy.data.grease_pencils.new("GP")

# 4.0+: Grease Pencil是独立对象
gp_data = bpy.data.grease_pencils.new("GP")
gp_obj = bpy.data.objects.new("GP_Object", gp_data)
bpy.context.collection.objects.link(gp_obj)

# LineArt修改器的target设置
lineart_mod.target = gp_obj  # 指向Grease Pencil对象
```

### OBJ导入变更（4.0+）

```python
# 3.x:
# bpy.ops.import_scene.obj(filepath=...)

# 4.0+:
bpy.ops.wm.obj_import(filepath=...)

# 兼容处理
def import_obj(filepath):
    if bpy.app.version >= (4, 0, 0):
        bpy.ops.wm.obj_import(filepath=filepath)
    else:
        bpy.ops.import_scene.obj(filepath=filepath)
```

### 节点接口变更（4.0+）

```python
# 节点组的输入输出接口

# 3.x:
node_group.inputs.new('NodeSocketColor', 'Color')
node_group.outputs.new('NodeSocketFloat', 'Value')

# 4.0+:
node_group.interface.new_socket(
    name='Color', in_out='INPUT', socket_type='NodeSocketColor')
node_group.interface.new_socket(
    name='Value', in_out='OUTPUT', socket_type='NodeSocketFloat')

# 兼容处理
def add_node_input(node_group, name, socket_type):
    if bpy.app.version >= (4, 0, 0):
        node_group.interface.new_socket(
            name=name, in_out='INPUT', socket_type=socket_type)
    else:
        node_group.inputs.new(socket_type, name)
```

### 颜色管理变更（4.0+）

```python
# 4.0+: AgX成为默认颜色管理
# 3.x: Filmic是默认

# 检查当前设置
print(scene.view_settings.view_transform)

# 三渲二推荐Standard（两个版本都支持）
scene.view_settings.view_transform = 'Standard'
```

### Mesh API变更

```python
# 4.1+: use_auto_smooth行为变更
# 3.x/4.0: mesh.use_auto_smooth = True
# 4.1+: 通过Smooth by Angle修改器实现

# 4.x: mesh.calc_normals() 已废弃（自动计算）
# 直接访问mesh.vertices[i].normal即可

# 顶点颜色API变更
# 3.x: mesh.vertex_colors
# 4.0+: mesh.color_attributes（更通用）
```

### Deprecated警告处理

```python
import warnings

# 捕获deprecated警告
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always", DeprecationWarning)
    
    # 执行可能废弃的API
    # ...
    
    for warning in w:
        print(f"Deprecated: {warning.message}")

# 常见deprecated警告：
# - "use_auto_smooth" -> 使用Smooth by Angle修改器
# - "calc_normals" -> 自动计算
# - "import_scene.obj" -> wm.obj_import
```

### 版本兼容工具函数

```python
class BlenderCompat:
    """Blender版本兼容工具"""
    
    @staticmethod
    def version():
        return bpy.app.version
    
    @staticmethod
    def is_4x():
        return bpy.app.version >= (4, 0, 0)
    
    @staticmethod
    def is_5x():
        return bpy.app.version >= (5, 0, 0)
    
    @staticmethod
    def eevee_engine_name():
        if bpy.app.version >= (4, 2, 0):
            return 'BLENDER_EEVEE_NEXT'
        return 'BLENDER_EEVEE'
    
    @staticmethod
    def import_obj(filepath):
        if bpy.app.version >= (4, 0, 0):
            bpy.ops.wm.obj_import(filepath=filepath)
        else:
            bpy.ops.import_scene.obj(filepath=filepath)
    
    @staticmethod
    def create_grease_pencil(name):
        gp = bpy.data.grease_pencils.new(name)
        if bpy.app.version >= (4, 0, 0):
            obj = bpy.data.objects.new(name, gp)
            bpy.context.collection.objects.link(obj)
            return obj
        return gp
```

## 常见陷阱

### 陷阱1：Alpha版本API不稳定
```python
# Blender 5.1.0 Alpha可能有未稳定的API
# 解决：关键功能添加try/except
try:
    scene.render.engine = 'BLENDER_EEVEE_NEXT'
except:
    scene.render.engine = 'CYCLES'  # fallback
```

### 陷阱2：文档版本不匹配
```python
# Blender API文档对应特定版本
# 确保查看正确版本的文档
# https://docs.blender.org/api/5.1/ （5.1版本）
```

## 本项目代码关联

`cel_shading.py`：
- 使用EEVEE_NEXT（5.x）
- Grease Pencil独立对象（4.0+）

`engine.py`：
- 版本检测
- 兼容性处理

## 版本兼容性

- 本文档针对Blender 4.0 → 5.1的变更
- Alpha版本可能有额外变更
- 建议：关键代码添加版本检查

## 参考链接

- [Blender Release Notes](https://wiki.blender.org/wiki/Reference/Release_Notes)
- [Blender Python API Changelog](https://docs.blender.org/api/current/change_log.html)
- [Blender 5.0 Release Notes](https://wiki.blender.org/wiki/Reference/Release_Notes/5.0)
