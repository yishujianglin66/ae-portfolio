# Modifier系统详解

## 问题场景

Modifier（修改器）是Blender非破坏性编辑的核心。每个对象可以叠加多个修改器，按栈顺序依次应用。三渲二管线中常用Armature（骨骼变形）、LineArt（描边）、Subdivision（细分）等修改器。

## 核心原理

### Modifier基础

```python
import bpy

# 添加修改器
obj = bpy.data.objects["MyMesh"]
mod = obj.modifiers.new(name="MyModifier", type='SUBSURF')

# 修改器属性
mod.levels = 2          # 视口细分级别
mod.render_levels = 2   # 渲染细分级别

# 删除修改器
obj.modifiers.remove(mod)

# 清空所有修改器
obj.modifiers.clear()

# 遍历修改器
for mod in obj.modifiers:
    print(f"{mod.name}: {mod.type}")

# 按名称访问
mod = obj.modifiers.get("Subdivision")
```

### 常用Modifier类型

```python
# 变形类
'SUBSURF'       # 细分曲面
'ARMATURE'      # 骨骼变形
'MESH_DEFORM'   # 网格变形
'LATTICE'       # 晶格变形
'SHRINKWRAP'    # 缩裹

# 生成类
'LINE_ART'      # 线条艺术（描边）
'MIRROR'        # 镜像
'ARRAY'         # 阵列
'BOOLEAN'       # 布尔
'SOLIDIFY'      # 实体化

# 修改类
'BEVEL'         # 倒角
'DECIMATE'      # 精简
'SMOOTH'        # 平滑
'WELD'          # 焊接顶点
```

### Armature修改器（骨骼变形）

```python
def add_armature_modifier(mesh_obj, armature_obj):
    """添加骨骼变形修改器"""
    mod = mesh_obj.modifiers.new(name="Armature", type='ARMATURE')
    mod.object = armature_obj  # 关联骨骼对象
    
    # 重要选项
    mod.use_vertex_groups = True   # 使用顶点组权重
    mod.use_deform_preserve_volume = False  # 保持体积（双四元数）
    
    # 多骨骼影响
    # 每个顶点最多受4根骨骼影响（默认）
    
    return mod

# 修改器顺序很重要！
# Armature应该在LineArt之前
# 这样描边会跟随骨骼动画
```

### LineArt修改器

```python
def add_lineart_modifier(mesh_obj, gp_obj, thickness=2.0):
    """添加LineArt描边修改器"""
    mod = mesh_obj.modifiers.new(name="LineArt", type='LINE_ART')
    
    # 目标Grease Pencil对象
    mod.target = gp_obj
    
    # 线条类型
    mod.use_contour = True       # 轮廓线
    mod.use_material = True      # 材质边界
    mod.use_edge_mark = True     # 标记边
    mod.use_crease = True        # 折痕
    mod.use_intersecting = False # 相交线（慢）
    
    # 参数
    mod.thickness = thickness
    mod.crease_threshold = 0.5   # 折痕角度阈值
    
    return mod
```

### 修改器栈顺序

```python
# 修改器按从上到下的顺序应用
# 顺序影响最终结果！

# 推荐顺序（三渲二角色）：
# 1. Armature（骨骼变形）
# 2. Subdivision（细分，可选）
# 3. LineArt（描边）

# 调整顺序
def reorder_modifiers(obj, order):
    """
    重新排列修改器顺序
    order: 修改器名称列表，按期望顺序排列
    """
    for i, name in enumerate(order):
        mod = obj.modifiers.get(name)
        if mod:
            # 移动到位置i
            while obj.modifiers.find(name) > i:
                bpy.ops.object.modifier_move_up(
                    modifier=name,
                    object=obj.name
                )

# 示例
reorder_modifiers(obj, ["Armature", "Subdivision", "LineArt"])
```

### 应用修改器

```python
# 应用修改器（破坏性，不可逆）
# 需要设置活动对象
bpy.context.view_layer.objects.active = obj
bpy.ops.object.modifier_apply(modifier="Subdivision")

# 应用所有修改器
for mod in list(obj.modifiers):  # list()避免迭代问题
    bpy.ops.object.modifier_apply(modifier=mod.name)

# 注意：应用Armature修改器会"烘焙"骨骼变形
# 之后网格不再跟随骨骼动画
```

### 修改器显示控制

```python
# 视口显示
mod.show_viewport = True   # 视口中显示
mod.show_render = True     # 渲染时应用
mod.show_in_editmode = False  # 编辑模式不显示

# 展开/折叠（UI）
mod.show_expanded = False
```

## 常见陷阱

### 陷阱1：Armature修改器无效
```python
# 原因1：mod.object未设置
# 原因2：顶点组名称与骨骼名称不匹配
# 原因3：修改器在LineArt之后（描边不跟随动画）

# 检查：
for vg in obj.vertex_groups:
    print(vg.name)  # 必须与骨骼名称一致
```

### 陷阱2：LineArt不显示
```python
# 原因1：target未设置（需要Grease Pencil对象）
# 原因2：所有线条类型都关闭
# 原因3：crease_threshold太大（没有折痕）

# 修复：
mod.target = gp_obj
mod.use_contour = True
mod.crease_threshold = 0.3
```

### 陷阱3：应用修改器后网格消失
```python
# 原因：Boolean修改器运算失败
# 解决：检查布尔对象是否相交、法线是否正确
```

## 本项目代码关联

`cel_shading.py`：
- L600-700: Armature修改器添加
- L700-800: LineArt修改器配置
- 修改器顺序：Armature → LineArt

## 版本兼容性

- Blender 4.x/5.x: Modifier API稳定
- LINE_ART类型：Blender 2.93+
- Blender 5.1.0 Alpha: 无重大变更

## 参考链接

- [Blender Manual: Modifiers](https://docs.blender.org/manual/en/latest/modeling/modifiers/index.html)
- [Blender Python API: Modifier](https://docs.blender.org/api/current/bpy.types.Modifier.html)
