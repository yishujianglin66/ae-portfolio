# LineArt描边修改器

## 问题场景

三渲二的"二"体现在描边（Line Art）。Blender的LineArt修改器可以生成边缘线、轮廓线、材质边界线，模拟手绘动画的描边效果。

## 核心原理

### LineArt修改器配置

```python
import bpy

def setup_lineart(obj, thickness=2.0):
    """为物体添加LineArt描边"""
    # 添加LineArt修改器
    mod = obj.modifiers.new(name="LineArt", type='LINE_ART')
    
    # 基本设置
    mod.thickness = thickness
    mod.use_multiple_levels = False
    
    # 线条类型
    mod.use_contour = True        # 轮廓线
    mod.use_material = True       # 材质边界
    mod.use_edge_mark = True      # 标记边
    mod.use_crease = True         # 折痕线
    mod.use_intersecting = False  # 相交线（性能开销大）
    
    # 角度阈值
    mod.crease_threshold = 0.5    # 折痕角度阈值（弧度）
    
    # 输出到Grease Pencil
    # LineArt需要Grease Pencil对象来存储线条
    gp = bpy.data.grease_pencils.new("LineArt_GP")
    gp_obj = bpy.data.objects.new("LineArt_GP", gp)
    bpy.context.collection.objects.link(gp_obj)
    
    mod.target = gp_obj
    
    return mod, gp_obj
```

### 线条样式

```python
def setup_line_style(gp_obj, color=(0, 0, 0, 1), thickness=2):
    """配置线条样式"""
    # Grease Pencil材质
    mat = bpy.data.materials.new("LineMat")
    mat.use_nodes = True
    
    # 获取Stroke节点
    stroke_node = mat.node_tree.nodes.get("Principled BSDF")
    if stroke_node:
        # 设置为纯色描边
        stroke_node.inputs['Base Color'].default_value = color
    
    # 应用到Grease Pencil
    if gp_obj.data.materials:
        gp_obj.data.materials[0] = mat
    else:
        gp_obj.data.materials.append(mat)
```

### 渲染顺序

```python
# LineArt修改器在Modifier栈中的位置很重要
# 推荐顺序：
# 1. Armature（骨骼变形）
# 2. LineArt（描边）
# 3. 其他效果

# LineArt会在变形后的网格上计算边缘
# 如果放在Armature之前，描边不会跟随动画
```

## 常见陷阱

### 陷阱1：LineArt不显示
```python
# 原因1：没有Grease Pencil目标
# 原因2：viewport显示设置关闭了Grease Pencil
# 原因3：LineArt修改器被禁用
```

### 陷阱2：描边过密
```python
# 解决：增加crease_threshold
mod.crease_threshold = 1.0  # 更大的角度阈值 = 更少的线
```

## 本项目代码关联

`cel_shading.py` L700-800：
- LineArt修改器配置
- outline_mode="lineart"参数

## 版本兼容性

- Blender 4.x/5.x: LineArt修改器API稳定
- Blender 5.1.0 Alpha: 测试通过

## 参考链接

- [Blender Manual: Line Art Modifier](https://docs.blender.org/manual/en/latest/modeling/modifiers/modify/line_art.html)
