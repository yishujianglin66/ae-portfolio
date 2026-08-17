# 层级Parent与变换继承

## 问题场景

多层parent嵌套（A→B→C）时，变换会层层继承。理解继承链对于调试"为什么物体出现在意外位置"至关重要。

## 核心原理

### 变换继承链

```
C.matrix_world = A.matrix_world × B.matrix_local × C.matrix_local

更一般地：
child.matrix_world = parent.matrix_world × child.matrix_local

对于BONE parent：
child.matrix_world = armature.matrix_world × bone_tail_matrix × child.matrix_parent_inverse × child.matrix_basis
```

### 多层Parent示例

```python
import bpy
from mathutils import Matrix, Vector

def demonstrate_hierarchy():
    """演示三层parent的变换继承"""
    # 创建三个空物体
    a = bpy.data.objects.new("A", None)
    b = bpy.data.objects.new("B", None)
    c = bpy.data.objects.new("C", None)
    
    bpy.context.collection.objects.link(a)
    bpy.context.collection.objects.link(b)
    bpy.context.collection.objects.link(c)
    
    # 设置层级：C → B → A
    b.parent = a
    c.parent = b
    
    # 设置变换
    a.location = (10, 0, 0)   # A在世界(10,0,0)
    b.location = (0, 5, 0)    # B在A空间(0,5,0) → 世界(10,5,0)
    c.location = (0, 0, 3)    # C在B空间(0,0,3) → 世界(10,5,3)
    
    bpy.context.view_layer.update()
    
    print(f"A world: {a.matrix_world.translation.to_tuple()}")  # (10,0,0)
    print(f"B world: {b.matrix_world.translation.to_tuple()}")  # (10,5,0)
    print(f"C world: {c.matrix_world.translation.to_tuple()}")  # (10,5,3)
    
    # 旋转A → B和C都跟随旋转
    import math
    a.rotation_euler.z = math.radians(90)
    bpy.context.view_layer.update()
    
    print(f"\nAfter A rotates 90° Z:")
    print(f"B world: {b.matrix_world.translation.to_tuple()}")  # (10,-5,0) 旋转了！
    print(f"C world: {c.matrix_world.translation.to_tuple()}")  # (10,-5,3)
```

### 断开继承（保持世界位置）

```python
def break_inheritance_keep_world(child_obj):
    """断开parent继承，保持世界位置"""
    bpy.context.view_layer.update()
    world_mat = child_obj.matrix_world.copy()
    
    child_obj.parent = None
    child_obj.matrix_world = world_mat
    
    bpy.context.view_layer.update()
```

### 部分继承（约束控制）

```python
def partial_inheritance(child_obj, parent_obj):
    """只继承位移，不继承旋转"""
    # 清除parent
    child_obj.parent = None
    
    # 用Copy Location约束代替parent
    constraint = child_obj.constraints.new(type='COPY_LOCATION')
    constraint.target = parent_obj
    constraint.use_x = True
    constraint.use_y = True
    constraint.use_z = True
    # 不添加Copy Rotation → 不继承旋转
```

## 常见陷阱

### 陷阱1：循环Parent
```python
# A.parent = B; B.parent = A → Blender会拒绝或产生未定义行为
# 检查：
def has_circular_parent(obj):
    visited = set()
    current = obj.parent
    while current:
        if current == obj:
            return True
        if current.name in visited:
            return True
        visited.add(current.name)
        current = current.parent
    return False
```

### 陷阱2：缩放继承导致累积缩放
```python
# parent.scale = (2,2,2), child.scale = (2,2,2)
# child世界缩放 = 4×（继承累积）
# 解决：Apply child的缩放，或不继承缩放
```

## 本项目代码关联

`cel_shading.py`：
- 发冠 → parent到Armature(BONE) → 跟随Head
- 扇面 → parent到扇柄 → 扇柄parent到Armature
- 形成两层继承链

## 版本兼容性

- Blender 4.x/5.x: parent继承行为不变
- Blender 5.1.0 Alpha: 测试通过

## 参考链接

- [Blender Manual: Parenting](https://docs.blender.org/manual/en/latest/scene_layout/object/editing/parent.html)
