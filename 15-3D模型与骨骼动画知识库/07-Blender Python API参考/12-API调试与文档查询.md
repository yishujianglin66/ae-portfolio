# API调试与文档查询

## 问题场景

Blender Python API庞大且文档分散，调试脚本时需要快速查找API用法、理解参数含义、定位错误原因。掌握调试技巧可以大幅提升开发效率。

## 核心原理

### 内置文档查询

```python
import bpy

# 1. 查看对象类型
print(type(bpy.data.objects["Cube"]))
# <class 'bpy_types.Object'>

# 2. 查看属性列表
print(dir(obj))
# ['animation_data', 'bound_box', 'children', 'constraints', ...]

# 3. 查看属性文档
print(obj.location.__doc__)
# 某些属性有内置文档

# 4. 查看函数签名
import inspect
print(inspect.signature(bpy.ops.import_scene.fbx))

# 5. 使用help()
help(bpy.types.Object)
help(bpy.ops.render.render)
```

### RNA属性查询

```python
# Blender使用RNA系统定义属性
# 可以查询属性的元数据

obj = bpy.data.objects["Cube"]

# 获取RNA定义
rna = obj.bl_rna

# 遍历属性
for prop in rna.properties:
    print(f"{prop.identifier}: {prop.name} ({prop.type})")
    if hasattr(prop, 'default'):
        print(f"  Default: {prop.default}")

# 查询特定属性
loc_prop = rna.properties['location']
print(f"Type: {loc_prop.type}")
print(f"Array length: {loc_prop.array_length}")
print(f"Default: {loc_prop.default_array}")
```

### Operator参数查询

```python
# 查看Operator的所有参数
def show_operator_params(op_path):
    """显示Operator参数"""
    # op_path格式: "import_scene.fbx"
    parts = op_path.split('.')
    module = getattr(bpy.ops, parts[0])
    op = getattr(module, parts[1])
    
    # 获取RNA
    rna = op.get_rna_type()
    
    print(f"Operator: {op_path}")
    print(f"Description: {rna.description}")
    print("Parameters:")
    
    for prop in rna.properties:
        if prop.identifier in ('self', 'register'):
            continue
        default = ""
        if hasattr(prop, 'default'):
            default = f" = {prop.default}"
        print(f"  {prop.identifier}: {prop.type}{default}")

# 使用
show_operator_params("import_scene.fbx")
show_operator_params("render.render")
```

### 调试输出技巧

```python
import bpy
import sys

# 1. 基本打印
print(f"Object: {obj.name}, Type: {obj.type}")
print(f"Location: {obj.location[:]}")  # 转为tuple

# 2. 格式化矩阵
def print_matrix(mat, name="Matrix"):
    print(f"{name}:")
    for row in mat:
        print(f"  [{row[0]:8.4f}, {row[1]:8.4f}, "
              f"{row[2]:8.4f}, {row[3]:8.4f}]")

print_matrix(obj.matrix_world, "World Matrix")

# 3. 对象树打印
def print_object_tree(obj, indent=0):
    prefix = "  " * indent
    print(f"{prefix}{obj.name} ({obj.type})")
    for child in obj.children:
        print_object_tree(child, indent + 1)

for obj in bpy.context.scene.objects:
    if not obj.parent:
        print_object_tree(obj)

# 4. 顶点组权重打印
def print_vertex_groups(obj, vertex_index):
    print(f"Vertex {vertex_index} weights:")
    v = obj.data.vertices[vertex_index]
    for g in v.groups:
        name = obj.vertex_groups[g.group].name
        print(f"  {name}: {g.weight:.4f}")
```

### 日志系统

```python
import logging
import sys

def setup_blender_logging(log_file=None, level=logging.DEBUG):
    """配置Blender脚本日志"""
    logger = logging.getLogger("blender_script")
    logger.setLevel(level)
    
    # 控制台输出
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(
        '[%(levelname)s] %(message)s'))
    logger.addHandler(console)
    
    # 文件输出（可选）
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] %(funcName)s: %(message)s'))
        logger.addHandler(file_handler)
    
    return logger

# 使用
logger = setup_blender_logging("script.log")
logger.info("Script started")
logger.debug(f"Object count: {len(bpy.data.objects)}")
logger.warning("Something might be wrong")
logger.error("Something went wrong")
```

### 异常调试

```python
import traceback

def safe_execute(func, *args, **kwargs):
    """安全执行函数，捕获并打印异常"""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        print(f"[ERROR] {type(e).__name__}: {e}")
        print("[TRACEBACK]")
        traceback.print_exc()
        
        # Blender特定错误处理
        if isinstance(e, RuntimeError):
            # 通常是context问题
            print("[HINT] Check if active object is set correctly")
        
        return None

# 使用
result = safe_execute(bpy.ops.render.render, animation=True)
```

### 性能分析

```python
import time
from functools import wraps

def timer(func):
    """函数计时装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        print(f"[Timer] {func.__name__}: {elapsed:.3f}s")
        return result
    return wrapper

@timer
def heavy_operation():
    # ...
    pass

# 手动计时
start = time.perf_counter()
bpy.ops.render.render(animation=True)
print(f"Render time: {time.perf_counter() - start:.2f}s")
```

### 在线文档资源

```python
# 官方文档
# https://docs.blender.org/api/current/  - 当前版本API
# https://docs.blender.org/api/5.1/     - 5.1版本API

# 快速搜索技巧：
# 1. 在文档页面使用Ctrl+F搜索类名
# 2. 搜索 "bpy.types.ClassName"
# 3. 搜索 "bpy.ops.module.operator"

# 社区资源
# https://blender.stackexchange.com/  - 问答
# https://blenderartists.org/         - 论坛
# https://devtalk.blender.org/        - 开发者论坛

# 源码查看
# Blender Python API源码在：
# blender/scripts/modules/bpy/
# blender/scripts/startup/bl_operators/
```

### 交互式调试（GUI模式）

```python
# 在Blender GUI中打开Python控制台
# Window > Toggle System Console (Windows)

# 使用Text Editor运行脚本
# 可以设置断点（有限支持）

# 交互式调试
import pdb
# pdb.set_trace()  # 在background模式不可用

# 替代：手动检查点
def checkpoint(name, **vars):
    print(f"\n[CHECKPOINT] {name}")
    for k, v in vars.items():
        print(f"  {k} = {v}")

checkpoint("After import", 
           obj_count=len(bpy.data.objects),
           meshes=[o.name for o in bpy.data.objects if o.type=='MESH'])
```

## 常见陷阱

### 陷阱1：dir()输出太多
```python
# 过滤有用信息
useful = [attr for attr in dir(obj) 
          if not attr.startswith('_')]
print(useful)
```

### 陷阱2：print矩阵/向量不直观
```python
# Vector/Matrix直接print可能截断
# 解决：格式化输出
print(f"Location: ({obj.location.x:.4f}, "
      f"{obj.location.y:.4f}, {obj.location.z:.4f})")
```

## 本项目代码关联

`cel_shading.py`：
- 大量print调试输出
- 检查点日志

`engine.py`：
- subprocess输出捕获
- 错误日志解析

## 版本兼容性

- 调试技巧适用于所有版本
- API文档需对应版本查看

## 参考链接

- [Blender Python API](https://docs.blender.org/api/current/)
- [Blender Stack Exchange](https://blender.stackexchange.com/)
- [Blender Developer Documentation](https://developer.blender.org/)
