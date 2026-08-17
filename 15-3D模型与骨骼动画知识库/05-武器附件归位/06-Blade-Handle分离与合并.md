# Blade/Handle分离与合并

## 问题场景

复杂武器（如扇子=扇柄+扇面、剑=剑柄+剑身）由多个mesh组成。归位时需要分别处理各部件，然后组装为整体。组装后内部parent关系影响后续操作。

## 核心原理

### 组装策略

```python
import bpy
from mathutils import Vector

def assemble_weapon(handle, blade):
    """
    组装武器：blade → parent → handle
    后续只需操作handle即可控制整个武器
    """
    bpy.context.view_layer.update()
    
    # 记录blade当前世界矩阵
    blade_world = blade.matrix_world.copy()
    
    # 设置parent
    blade.parent = handle
    blade.matrix_parent_inverse = handle.matrix_world.inverted() @ blade_world
    
    bpy.context.view_layer.update()
    
    # 验证：blade世界位置不应改变
    new_pos = blade.matrix_world.translation
    old_pos = blade_world.translation
    diff = (new_pos - old_pos).length
    print(f"[Assembly] Position diff: {diff:.6f} (should be ~0)")
    
    return handle  # 返回根部件

def disassemble_weapon(handle):
    """拆解武器（保持世界位置）"""
    for child in handle.children:
        child_world = child.matrix_world.copy()
        child.parent = None
        child.matrix_world = child_world
```

### 多部件武器

```python
def assemble_multi_part_weapon(parts):
    """
    组装多部件武器
    parts: 按层级排序 [root, child1, child2, ...]
    """
    root = parts[0]
    
    for i in range(1, len(parts)):
        child = parts[i]
        parent = parts[i-1]  # 或都parent到root
        
        child_world = child.matrix_world.copy()
        child.parent = parent
        child.matrix_parent_inverse = parent.matrix_world.inverted() @ child_world
    
    return root
```

### 合并为单一Mesh（可选）

```python
def merge_weapon_parts(handle, blade):
    """将武器部件合并为单一mesh（不可逆！）"""
    bpy.ops.object.select_all(action='DESELECT')
    handle.select_set(True)
    blade.select_set(True)
    bpy.context.view_layer.objects.active = handle
    
    bpy.ops.object.join()  # 合并
    
    # 合并后只有一个mesh对象
    # 优点：减少draw call
    # 缺点：无法独立控制部件
    return handle
```

## 常见陷阱

### 陷阱1：parent后blade位置跳跃
```python
# 必须正确设置matrix_parent_inverse
# 否则blade会跳到handle的origin
```

### 陷阱2：合并后材质丢失
```python
# join()会保留所有材质槽
# 但如果有同名材质，可能合并
```

## 本项目代码关联

`cel_shading.py` L1785-1791：
- 扇面parent到扇柄
- 保持扇面世界位置不变

## 版本兼容性

- Blender 4.x/5.x: parent/join API稳定
- Blender 5.1.0 Alpha: 测试通过

## 参考链接

- [Blender API: bpy.ops.object.join](https://docs.blender.org/api/current/bpy.ops.object.html)
