# Material与Node系统

## 问题场景

Blender的材质系统基于节点树（Node Tree），通过连接不同的Shader节点实现各种材质效果。三渲二需要将PBR材质转换为Toon材质，理解节点系统是必要的。

## 核心原理

### 材质基础

```python
import bpy

# 创建材质
mat = bpy.data.materials.new(name="CelMaterial")
mat.use_nodes = True  # 启用节点

# 获取节点树
tree = mat.node_tree
nodes = tree.nodes
links = tree.links

# 默认节点：Principled BSDF + Material Output
# 清空重建
nodes.clear()

# 应用到对象
obj = bpy.data.objects["MyMesh"]
if obj.data.materials:
    obj.data.materials[0] = mat
else:
    obj.data.materials.append(mat)
```

### Shader节点类型

```python
# 常用Shader节点
'BSDF_PRINCIPLED'    # 原理化BSDF（PBR）
'BSDF_DIFFUSE'       # 漫反射
'BSDF_GLOSSY'        # 高光
'BSDF_TOON'          # 卡通（三渲二核心）
'BSDF_TRANSPARENT'   # 透明
'BSDF_GLASS'         # 玻璃
'EMISSION'           # 自发光
'MIX_SHADER'         # 混合Shader
'ADD_SHADER'         # 叠加Shader

# 纹理节点
'TEX_IMAGE'          # 图像纹理
'TEX_NOISE'          # 噪波
'TEX_GRADIENT'       # 渐变
'TEX_CHECKER'        # 棋盘格

# 输入节点
'RGB'                # 纯色
'VALUE'              # 数值
'TEX_COORD'          # 纹理坐标
'NORMAL'             # 法线

# 颜色节点
'MIX_RGB'            # 混合颜色（4.0+改为ColorRamp）
'COLOR_RAMP'         # 颜色渐变
'BRIGHTCONTRAST'     # 亮度对比度
'HUE_SAT'            # 色相饱和度
```

### 创建Toon材质

```python
def create_toon_material(name, base_color, shadow_color):
    """创建赛璐璐Toon材质"""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    tree = mat.node_tree
    nodes = tree.nodes
    links = tree.links
    nodes.clear()
    
    # Toon BSDF
    toon = nodes.new('ShaderNodeBsdfToon')
    toon.inputs['Base Color'].default_value = base_color
    toon.inputs['Size'].default_value = 0.5    # 明暗分界柔和度
    toon.inputs['Smooth'].default_value = 0.1  # 过渡平滑度
    toon.location = (0, 0)
    
    # Material Output
    output = nodes.new('ShaderNodeOutputMaterial')
    output.location = (300, 0)
    
    # 连接
    links.new(toon.outputs['BSDF'], output.inputs['Surface'])
    
    return mat
```

### 图像纹理材质

```python
def create_texture_material(name, texture_path):
    """创建带贴图的材质"""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    tree = mat.node_tree
    nodes = tree.nodes
    links = tree.links
    
    # 找到或创建Image Texture节点
    tex_node = None
    for node in nodes:
        if node.type == 'TEX_IMAGE':
            tex_node = node
            break
    
    if not tex_node:
        tex_node = nodes.new('ShaderNodeTexImage')
        tex_node.location = (-400, 0)
    
    # 加载图像
    img = bpy.data.images.load(texture_path, check_existing=True)
    tex_node.image = img
    
    # 连接到Principled BSDF
    principled = nodes.get('Principled BSDF')
    if principled:
        links.new(tex_node.outputs['Color'], 
                  principled.inputs['Base Color'])
    
    return mat
```

### 节点连接操作

```python
# 创建连接
link = links.new(
    node_a.outputs['Color'],   # 输出插槽
    node_b.inputs['Base Color']  # 输入插槽
)

# 删除连接
links.remove(link)

# 清空所有连接
links.clear()

# 查找连接
for link in links:
    print(f"{link.from_node.name}.{link.from_socket.name} -> "
          f"{link.to_node.name}.{link.to_socket.name}")
```

### 材质插槽管理

```python
# 对象可以有多个材质插槽
obj = bpy.data.objects["MyMesh"]

# 添加材质插槽
obj.data.materials.append(mat1)
obj.data.materials.append(mat2)

# 替换材质
obj.data.materials[0] = new_mat

# 删除材质插槽
obj.data.materials.pop(index=0)

# 网格面指定材质索引
# 在编辑模式下选择面，设置material_index
for poly in obj.data.polygons:
    poly.material_index = 0  # 使用第一个材质
```

### 节点组（Node Group）

```python
# 创建节点组（可复用的节点集合）
node_group = bpy.data.node_groups.new("CelShader", 'ShaderNodeTree')

# 添加输入/输出接口
# Blender 4.0+ 使用接口系统
if hasattr(node_group, 'interface'):
    # 4.0+
    node_group.interface.new_socket(
        name="Base Color", in_out='INPUT', socket_type='NodeSocketColor')
else:
    # 3.x
    node_group.inputs.new('NodeSocketColor', 'Base Color')
```

## 常见陷阱

### 陷阱1：材质不显示
```python
# 原因1：use_nodes = False
# 原因2：Output节点未连接
# 原因3：视口显示模式不是Material Preview/Rendered

mat.use_nodes = True
# 确保有Material Output节点且已连接
```

### 陷阱2：纹理路径丢失
```python
# FBX导入后纹理路径可能无效
# 检查：
for img in bpy.data.images:
    if img.source == 'FILE':
        print(f"{img.name}: {img.filepath}")
        if not os.path.exists(bpy.path.abspath(img.filepath)):
            print("  [!] File not found!")
```

### 陷阱3：Toon BSDF在EEVEE Next中表现不同
```python
# Blender 4.2+ EEVEE Next对Toon BSDF的支持有变化
# 可能需要调整Size/Smooth参数
```

## 本项目代码关联

`cel_shading.py` L300-600：
- 材质转换为Toon BSDF
- 保留原始贴图
- 阴影颜色计算

## 版本兼容性

- Blender 4.0+: 节点接口系统变更（interface vs inputs/outputs）
- Blender 4.2+: EEVEE Next材质渲染差异
- Blender 5.1.0 Alpha: Toon BSDF正常工作

## 参考链接

- [Blender Manual: Materials](https://docs.blender.org/manual/en/latest/render/materials/index.html)
- [Blender Manual: Shader Nodes](https://docs.blender.org/manual/en/latest/render/shader_nodes/index.html)
