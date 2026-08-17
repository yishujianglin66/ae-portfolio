# Apply Transform与变换冻结

## 问题场景

物体的location/rotation/scale累积后，后续操作（如布尔运算、法线计算）可能出错。Apply Transform将当前变换"烘焙"到网格数据中，使location/rotation/scale归零。

## 核心原理

### Apply Transform的含义

```
Apply前：
  obj.location = (1, 2, 3)
  obj.rotation_euler = (0, 0, 45°)
  mesh顶点: 原始坐标

Apply后：
  obj.location = (0, 0, 0)
  obj.rotation_euler = (0, 0, 0)
  mesh顶点: 变换后的坐标（已包含位移和旋转）
```

### 代码实现

```python
import bpy

def apply_transform(obj, location=True, rotation=True, scale=True):
    """应用变换到网格数据"""
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    
    bpy.ops.object.transform_apply(
        location=location,
        rotation=rotation,
        scale=scale
    )

def apply_all_objects(objects):
    """批量应用变换"""
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
```

### 何时需要Apply

| 场景 | 需要Apply？ | 原因 |
|------|:---:|------|
| 布尔运算前 | ✅ | 非均匀缩放导致布尔失败 |
| 法线重算前 | ✅ | 缩放影响法线方向 |
| 导出FBX/OBJ前 | ✅ | 某些格式不保留变换 |
| 设置parent前 | ❌ | parent会处理变换 |
| 动画关键帧中 | ❌ | 会破坏动画 |
| 权重计算前 | 可选 | 世界坐标计算已包含变换 |

### 注意事项

```python
# 警告：Apply后无法撤销（除非Ctrl+Z）
# 警告：有parent的物体Apply可能失败
# 警告：有修改器的物体Apply可能产生意外结果

# 安全Apply流程：
def safe_apply(obj):
    # 1. 暂时解除parent
    parent = obj.parent
    if parent:
        obj.parent = None
    
    # 2. Apply
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    
    # 3. 恢复parent
    if parent:
        obj.parent = parent
```

## 常见陷阱

### 陷阱1：Apply后parent关系断裂
```python
# 有parent的物体直接Apply → 位置跳跃
# 解决：先clear parent，Apply，再reparent
```

### 陷阱2：非均匀缩放Apply后法线异常
```python
# 非均匀缩放(如scale=(1,2,1))Apply后
# 法线需要重新计算
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.normals_make_consistent(inside=False)
bpy.ops.object.mode_set(mode='OBJECT')
```

## 本项目代码关联

`cel_shading.py` L820-830：模型导入后Apply缩放
```python
# 归一化后应用缩放
bpy.ops.object.transform_apply(scale=True)
```

## 版本兼容性

- Blender 4.x/5.x: transform_apply API稳定
- Blender 5.1.0 Alpha: 测试通过

## 参考链接

- [Blender API: bpy.ops.object.transform_apply](https://docs.blender.org/api/current/bpy.ops.object.html)
