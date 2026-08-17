# 赛璐璐风格Shader节点

## 问题场景

三渲二（3D渲染为2D动画风格）的核心是Toon Shader，实现硬边明暗分界（赛璐璐风格）。需要配置Principled BSDF或Toon BSDF节点。

## 核心原理

### 赛璐璐Shader节点树

```python
import bpy

def create_cel_shader(material_name, base_color=(0.8, 0.6, 0.5, 1.0)):
    """创建赛璐璐风格材质"""
    mat = bpy.data.materials.new(name=material_name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    
    # 清空默认节点
    nodes.clear()
    
    # 创建节点
    output = nodes.new('ShaderNodeOutputMaterial')
    output.location = (400, 0)
    
    # 方案1：Toon BSDF（简单硬边）
    toon = nodes.new('ShaderNodeBsdfToon')
    toon.location = (0, 0)
    toon.inputs['Base Color'].default_value = base_color
    toon.inputs['Size'].default_value = 0.5  # 明暗分界硬度
    toon.inputs['Smooth'].default_value = 0.1  # 过渡宽度
    
    links.new(toon.outputs['BSDF'], output.inputs['Surface'])
    
    return mat

def create_cel_shader_advanced(base_color, shadow_color, highlight_color):
    """高级赛璐璐Shader（三色分层）"""
    mat = bpy.data.materials.new("CelAdvanced")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    
    output = nodes.new('ShaderNodeOutputMaterial')
    output.location = (600, 0)
    
    # Diffuse BSDF
    diffuse = nodes.new('ShaderNodeBsdfDiffuse')
    diffuse.location = (0, 0)
    diffuse.inputs['Color'].default_value = base_color
    
    # Toon BSDF（阴影层）
    toon = nodes.new('ShaderNodeBsdfToon')
    toon.location = (0, -200)
    toon.inputs['Base Color'].default_value = shadow_color
    toon.inputs['Size'].default_value = 0.3
    
    # Mix Shader
    mix = nodes.new('ShaderNodeMixShader')
    mix.location = (300, 0)
    mix.inputs['Fac'].default_value = 0.5
    
    # Layer Weight（控制混合）
    layer_weight = nodes.new('ShaderNodeLayerWeight')
    layer_weight.location = (100, 200)
    layer_weight.inputs['Blend'].default_value = 0.5
    
    links.new(diffuse.outputs['BSDF'], mix.inputs[1])
    links.new(toon.outputs['BSDF'], mix.inputs[2])
    links.new(layer_weight.outputs['Facing'], mix.inputs['Fac'])
    links.new(mix.outputs['Shader'], output.inputs['Surface'])
    
    return mat
```

### 应用到模型

```python
def apply_cel_material(obj, material):
    """将赛璐璐材质应用到物体"""
    if obj.data.materials:
        obj.data.materials[0] = material
    else:
        obj.data.materials.append(material)
```

### 颜色方案

```python
# 上官婉儿的颜色方案
CEL_COLORS = {
    'skin': {
        'base': (0.95, 0.85, 0.75, 1.0),
        'shadow': (0.85, 0.70, 0.60, 1.0),
    },
    'hair': {
        'base': (0.15, 0.12, 0.10, 1.0),
        'shadow': (0.08, 0.06, 0.05, 1.0),
    },
    'cloth': {
        'base': (0.6, 0.7, 0.9, 1.0),
        'shadow': (0.4, 0.5, 0.7, 1.0),
    }
}
```

## 常见陷阱

### 陷阱1：Toon BSDF在Cycles中不工作
```python
# Toon BSDF仅在EEVEE中有效
# Cycles中需要使用其他方法模拟
```

### 陷阱2：Size/Smooth参数
```python
# Size: 0=完全阴影, 1=完全亮
# Smooth: 0=硬边, 1=完全平滑
# 赛璐璐推荐: Size=0.5, Smooth=0.05~0.1
```

## 本项目代码关联

`cel_shading.py` L500-700：
- 材质创建和配置
- Toon BSDF参数设置

## 版本兼容性

- Blender 4.x/5.x: Toon BSDF API稳定
- Blender 5.1.0 Alpha: 测试通过

## 参考链接

- [Blender Manual: Toon BSDF](https://docs.blender.org/manual/en/latest/render/shader_nodes/shader/toon.html)
