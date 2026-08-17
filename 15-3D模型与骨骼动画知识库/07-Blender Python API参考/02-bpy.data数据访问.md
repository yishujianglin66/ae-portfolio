# bpy.data数据访问

## 问题场景

`bpy.data`是Blender所有数据块的容器，包含对象、网格、材质、纹理、图像等。理解数据块的生命周期和引用关系是脚本开发的基础。

## 核心原理

### 数据块类型

```python
import bpy

# bpy.data的主要集合：
bpy.data.objects      # 场景中的所有对象
bpy.data.meshes       # 网格数据
bpy.data.armatures    # 骨骼数据
bpy.data.materials    # 材质
bpy.data.textures     # 纹理
bpy.data.images       # 图像
bpy.data.cameras      # 相机数据
bpy.data.lights       # 灯光数据
bpy.data.collections  # 集合
bpy.data.scenes       # 场景
bpy.data.worlds       # 世界环境
bpy.data.grease_pencils  # Grease Pencil数据
bpy.data.node_groups  # 节点组
bpy.data.actions      # 动画Action
bpy.data.curves       # 曲线数据
```

### 数据块访问

```python
# 按名称访问
obj = bpy.data.objects["Cube"]
mat = bpy.data.materials["Material.001"]

# 安全访问（不存在返回None）
obj = bpy.data.objects.get("NonExistent")  # None

# 遍历
for obj in bpy.data.objects:
    print(obj.name, obj.type)

# 按类型过滤
meshes = [o for o in bpy.data.objects if o.type == 'MESH']
armatures = [o for o in bpy.data.objects if o.type == 'ARMATURE']
```

### 数据块创建

```python
# 创建网格对象
mesh = bpy.data.meshes.new("MyMesh")
obj = bpy.data.objects.new("MyObject", mesh)
bpy.context.collection.objects.link(obj)  # 必须链接到场景！

# 创建材质
mat = bpy.data.materials.new("MyMaterial")
mat.use_nodes = True

# 创建空物体
empty = bpy.data.objects.new("Empty", None)
bpy.context.collection.objects.link(empty)

# 创建骨骼
armature = bpy.data.armatures.new("MyArmature")
arm_obj = bpy.data.objects.new("Armature", armature)
bpy.context.collection.objects.link(arm_obj)
```

### 数据块删除

```python
# 删除对象
obj = bpy.data.objects["Cube"]
bpy.data.objects.remove(obj, do_unlink=True)

# 删除网格数据
mesh = bpy.data.meshes["Cube"]
bpy.data.meshes.remove(mesh)

# 删除材质
mat = bpy.data.materials["Material"]
bpy.data.materials.remove(mat)

# 批量清理未使用的数据块
def cleanup_unused_data():
    """清理users=0的数据块"""
    for collection in [
        bpy.data.meshes, bpy.data.materials,
        bpy.data.textures, bpy.data.images,
        bpy.data.armatures
    ]:
        for block in list(collection):  # list()避免迭代时修改
            if block.users == 0:
                collection.remove(block)
```

### 数据块引用关系

```python
# 对象 → 数据
obj.data  # Mesh/Armature/Camera/Light等

# 网格 → 材质
mesh.materials  # MaterialSlot列表

# 材质 → 节点树
mat.node_tree  # ShaderNodeTree

# 对象 → 修改器
obj.modifiers  # Modifier列表

# 对象 → 约束
obj.constraints  # Constraint列表

# 骨骼 → PoseBone
arm_obj.pose.bones  # PoseBone列表
```

### 数据块命名

```python
# Blender自动处理重名
# 创建同名数据块会自动添加.001, .002后缀
mat1 = bpy.data.materials.new("Mat")  # "Mat"
mat2 = bpy.data.materials.new("Mat")  # "Mat.001"

# 重命名
obj.name = "NewName"
obj.data.name = "NewMeshName"  # 数据块名称可以不同

# 查找（支持通配符）
import fnmatch
matching = [o for o in bpy.data.objects 
            if fnmatch.fnmatch(o.name, "Weapon_*")]
```

### Fake User与数据持久化

```python
# 数据块users=0时会被自动清理
# fake_user=True可以防止清理

mat = bpy.data.materials.new("Important")
mat.use_fake_user = True  # 即使无引用也保留

# 检查数据块状态
print(f"Users: {mat.users}")
print(f"Fake User: {mat.use_fake_user}")
```

## 常见陷阱

### 陷阱1：创建对象后未链接到场景
```python
# 错误：对象存在但不可见
obj = bpy.data.objects.new("Obj", mesh)
# 对象不在任何Collection中！

# 正确：
bpy.context.collection.objects.link(obj)
# 或
bpy.data.scenes[0].collection.objects.link(obj)
```

### 陷阱2：删除对象但数据块残留
```python
# 删除对象不会自动删除数据
obj = bpy.data.objects["Cube"]
mesh = obj.data
bpy.data.objects.remove(obj)
# mesh仍然存在！users变为0

# 正确：
bpy.data.objects.remove(obj, do_unlink=True)
# 然后清理
if mesh.users == 0:
    bpy.data.meshes.remove(mesh)
```

### 陷阱3：迭代时修改集合
```python
# 错误：迭代时删除
for obj in bpy.data.objects:
    if obj.type == 'MESH':
        bpy.data.objects.remove(obj)  # RuntimeError!

# 正确：先收集再删除
to_delete = [o for o in bpy.data.objects if o.type == 'MESH']
for obj in to_delete:
    bpy.data.objects.remove(obj)
```

## 本项目代码关联

`cel_shading.py`：
- L100-200: 遍历bpy.data.objects查找导入的网格
- L850-900: 创建Armature数据块
- L1400-1500: 材质数据块操作

## 版本兼容性

- Blender 4.x/5.x: bpy.data API稳定
- 数据块类型在不同版本可能有增减
- Blender 5.1.0 Alpha: 无重大变更

## 参考链接

- [Blender Python API: bpy.data](https://docs.blender.org/api/current/bpy.data.html)
- [Blender Manual: Data System](https://docs.blender.org/api/current/info_gotcha.html)
