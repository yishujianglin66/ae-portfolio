# Mesh数据操作

## 问题场景

直接操作网格数据（顶点、边、面）是高级脚本的基础。包括顶点位置读写、法线计算、UV操作、顶点组管理等。三渲二管线中需要读取顶点位置进行手部检测、包围盒计算等。

## 核心原理

### Mesh数据结构

```python
import bpy
from mathutils import Vector

# 获取网格数据
obj = bpy.data.objects["MyMesh"]
mesh = obj.data  # bpy.types.Mesh

# 三大元素
mesh.vertices   # 顶点 (MeshVertex)
mesh.edges      # 边 (MeshEdge)
mesh.polygons   # 面 (MeshPolygon)
mesh.loops      # 循环 (MeshLoop) - 面的顶点引用
```

### 顶点操作

```python
# 读取顶点
for v in mesh.vertices:
    print(f"Vertex {v.index}: {v.co}")  # 局部坐标
    print(f"  Normal: {v.normal}")
    print(f"  Groups: {[(g.group, g.weight) for g in v.groups]}")

# 修改顶点位置（需要更新）
mesh.vertices[0].co = Vector((1, 0, 0))
mesh.update()  # 必须调用！

# 顶点数量
print(f"Vertices: {len(mesh.vertices)}")
print(f"Edges: {len(mesh.edges)}")
print(f"Faces: {len(mesh.polygons)}")

# 世界坐标顶点
world_matrix = obj.matrix_world
for v in mesh.vertices:
    world_co = world_matrix @ v.co
    print(f"World: {world_co}")
```

### 面操作

```python
# 读取面
for poly in mesh.polygons:
    print(f"Face {poly.index}:")
    print(f"  Vertices: {list(poly.vertices)}")
    print(f"  Normal: {poly.normal}")
    print(f"  Area: {poly.area}")
    print(f"  Center: {poly.center}")
    print(f"  Material: {poly.material_index}")

# 计算网格总面积
total_area = sum(p.area for p in mesh.polygons)
```

### 包围盒计算

```python
def get_mesh_bounds(obj):
    """计算网格包围盒（世界坐标）"""
    mesh = obj.data
    world_matrix = obj.matrix_world
    
    # 局部坐标包围盒
    xs = [v.co.x for v in mesh.vertices]
    ys = [v.co.y for v in mesh.vertices]
    zs = [v.co.z for v in mesh.vertices]
    
    local_min = Vector((min(xs), min(ys), min(zs)))
    local_max = Vector((max(xs), max(ys), max(zs)))
    local_center = (local_min + local_max) / 2
    
    # 转换到世界坐标
    world_min = world_matrix @ local_min
    world_max = world_matrix @ local_max
    world_center = world_matrix @ local_center
    
    return {
        'min': world_min,
        'max': world_max,
        'center': world_center,
        'size': world_max - world_min,
    }

# 使用Blender内置（更快）
def get_bounds_builtin(obj):
    """使用内置bound_box"""
    # bound_box是8个角点（局部坐标）
    bbox = [obj.matrix_world @ Vector(corner) 
            for corner in obj.bound_box]
    
    xs = [v.x for v in bbox]
    ys = [v.y for v in bbox]
    zs = [v.z for v in bbox]
    
    return {
        'min': Vector((min(xs), min(ys), min(zs))),
        'max': Vector((max(xs), max(ys), max(zs))),
    }
```

### 顶点组操作

```python
# 创建顶点组
vg = obj.vertex_groups.new(name="Hand_L")

# 添加顶点到组
vg.add(
    index=[0, 1, 2, 3],  # 顶点索引列表
    weight=1.0,           # 权重
    type='REPLACE'        # REPLACE/ADD/SUBTRACT
)

# 读取顶点权重
for v in mesh.vertices:
    for g in v.groups:
        group_name = obj.vertex_groups[g.group].name
        print(f"Vertex {v.index} -> {group_name}: {g.weight}")

# 删除顶点组
obj.vertex_groups.remove(vg)

# 按名称查找
vg = obj.vertex_groups.get("Hand_L")
```

### 法线操作

```python
# 计算法线
mesh.calc_normals()  # 重新计算（已废弃，自动计算）

# 自定义法线
mesh.use_auto_smooth = True  # 启用自动平滑
mesh.auto_smooth_angle = 0.5  # 平滑角度阈值

# 面法线
for poly in mesh.polygons:
    print(f"Face {poly.index} normal: {poly.normal}")

# 顶点法线
for v in mesh.vertices:
    print(f"Vertex {v.index} normal: {v.normal}")

# 翻转法线（需要bmesh）
import bmesh
bm = bmesh.new()
bm.from_mesh(mesh)
bmesh.ops.reverse_faces(bm, faces=bm.faces)
bm.to_mesh(mesh)
bm.free()
```

### BMesh高级操作

```python
import bmesh

# 从网格创建BMesh
bm = bmesh.new()
bm.from_mesh(mesh)

# 顶点操作
for v in bm.verts:
    v.co.x += 1.0  # 移动所有顶点

# 边操作
for e in bm.edges:
    print(f"Edge: {e.verts[0].index} - {e.verts[1].index}")

# 面操作
for f in bm.faces:
    print(f"Face area: {f.calc_area()}")

# 挤出
bmesh.ops.extrude_face_region(bm, geom=bm.faces[:])

# 写回网格
bm.to_mesh(mesh)
bm.free()  # 必须释放！
```

### 网格创建

```python
# 从顶点/面创建网格
def create_mesh_from_data(name, verts, faces):
    """
    verts: [(x,y,z), ...]
    faces: [(v0,v1,v2,...), ...]
    """
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj

# 示例：创建三角形
obj = create_mesh_from_data(
    "Triangle",
    [(0, 0, 0), (1, 0, 0), (0.5, 1, 0)],
    [(0, 1, 2)]
)
```

## 常见陷阱

### 陷阱1：修改顶点后未更新
```python
# 错误：修改不生效
mesh.vertices[0].co = Vector((1, 0, 0))
# 视口/渲染看不到变化！

# 正确：
mesh.vertices[0].co = Vector((1, 0, 0))
mesh.update()
```

### 陷阱2：BMesh未释放
```python
# 错误：内存泄漏
bm = bmesh.new()
bm.from_mesh(mesh)
# 使用后没有bm.free()！

# 正确：
bm.free()
```

### 陷阱3：顶点索引与循环索引混淆
```python
# mesh.vertices - 顶点（唯一）
# mesh.loops - 循环（每个面的每个顶点一个）
# 一个顶点可能对应多个loop（不同面的法线/UV不同）
```

## 本项目代码关联

`cel_shading.py` L1637-1667：
- 读取武器网格顶点
- X坐标最小5%顶点聚类（手部检测）
- 计算手部中心位置

## 版本兼容性

- Blender 4.x: `calc_normals()`已废弃（自动计算）
- Blender 4.1+: `use_auto_smooth`行为变更
- Blender 5.1.0 Alpha: BMesh API稳定

## 参考链接

- [Blender Python API: Mesh](https://docs.blender.org/api/current/bpy.types.Mesh.html)
- [Blender Python API: BMesh](https://docs.blender.org/api/current/bmesh.html)
