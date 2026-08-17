# 渲染层与Compositor合成

## 问题场景

三渲二渲染中，需要将角色、描边、背景分层渲染，再通过Compositor合成。分层渲染允许独立调整各层参数（如描边粗细、背景模糊），避免整体重渲。

## 核心原理

### View Layer（渲染层）

```python
import bpy

def setup_view_layers():
    """配置渲染层分离"""
    scene = bpy.context.scene
    
    # 默认View Layer
    main_layer = scene.view_layers["ViewLayer"]
    
    # 创建角色层
    char_layer = scene.view_layers.new(name="Character")
    char_layer.use_solid = True
    char_layer.use_ztransp = True  # 透明背景
    
    # 创建描边层
    line_layer = scene.view_layers.new(name="LineArt")
    line_layer.use_solid = False
    line_layer.use_ztransp = True
    
    # 创建背景层
    bg_layer = scene.view_layers.new(name="Background")
    bg_layer.use_solid = True
```

### Collection与View Layer的关联

```python
def assign_collections_to_layers():
    """将Collection分配到对应View Layer"""
    scene = bpy.context.scene
    
    # 创建Collection
    char_col = bpy.data.collections.new("COL_Character")
    line_col = bpy.data.collections.new("COL_LineArt")
    bg_col = bpy.data.collections.new("COL_Background")
    
    # 链接到场景
    scene.collection.children.link(char_col)
    scene.collection.children.link(line_col)
    scene.collection.children.link(bg_col)
    
    # View Layer排除控制
    # 每个View Layer可以排除特定Collection
    for vl in scene.view_layers:
        # 获取LayerCollection
        lc = vl.layer_collection
        for child in lc.children:
            if child.name == "COL_Character":
                child.exclude = (vl.name != "Character")
            elif child.name == "COL_LineArt":
                child.exclude = (vl.name != "LineArt")
            elif child.name == "COL_Background":
                child.exclude = (vl.name != "Background")
```

### Compositor节点合成

```python
def setup_compositor():
    """Compositor节点树配置"""
    scene = bpy.context.scene
    scene.use_nodes = True
    tree = scene.node_tree
    tree.nodes.clear()
    
    # 输入节点（各渲染层）
    rl_char = tree.nodes.new('CompositorNodeRLayers')
    rl_char.name = "RL_Character"
    rl_char.layer = "Character"
    rl_char.location = (-400, 200)
    
    rl_line = tree.nodes.new('CompositorNodeRLayers')
    rl_line.name = "RL_LineArt"
    rl_line.layer = "LineArt"
    rl_line.location = (-400, 0)
    
    rl_bg = tree.nodes.new('CompositorNodeRLayers')
    rl_bg.name = "RL_Background"
    rl_bg.layer = "Background"
    rl_bg.location = (-400, -200)
    
    # Alpha Over合成
    # 先合成背景+角色
    mix1 = tree.nodes.new('CompositorNodeAlphaOver')
    mix1.location = (0, 100)
    
    # 再叠加描边
    mix2 = tree.nodes.new('CompositorNodeAlphaOver')
    mix2.location = (200, 0)
    
    # 输出
    composite = tree.nodes.new('CompositorNodeComposite')
    composite.location = (400, 0)
    
    # 连接
    tree.links.new(rl_bg.outputs['Image'], mix1.inputs[1])
    tree.links.new(rl_char.outputs['Image'], mix1.inputs[2])
    tree.links.new(mix1.outputs['Image'], mix2.inputs[1])
    tree.links.new(rl_line.outputs['Image'], mix2.inputs[2])
    tree.links.new(mix2.outputs['Image'], composite.inputs['Image'])
```

### 单层渲染（简化方案）

```python
def single_layer_cel_render():
    """
    简化方案：所有元素在同一View Layer
    LineArt通过Grease Pencil叠加在角色上方
    不需要Compositor分层
    """
    scene = bpy.context.scene
    
    # 确保只用一个View Layer
    while len(scene.view_layers) > 1:
        scene.view_layers.remove(scene.view_layers[-1])
    
    # 渲染顺序由对象在Outliner中的顺序决定
    # Grease Pencil（描边）默认渲染在Mesh上方
    
    # 开启透明背景
    scene.render.film_transparent = True
```

### Render Pass分离

```python
def setup_render_passes():
    """配置渲染Pass（用于后期调整）"""
    vl = bpy.context.scene.view_layers["ViewLayer"]
    
    # 常用Pass
    vl.use_pass_combined = True    # 最终合成图
    vl.use_pass_z = True           # 深度（用于DOF）
    vl.use_pass_normal = True      # 法线（用于重新打光）
    vl.use_pass_mist = True        # 雾效（深度渐变）
    
    # Cryptomatte（物体ID遮罩）
    vl.use_pass_cryptomatte_object = True
    vl.pass_cryptomatte_depth = 6  # 精度
```

## 常见陷阱

### 陷阱1：Compositor不生效
```python
# 原因：scene.use_nodes = False
# 解决：
scene.use_nodes = True
# 且渲染设置中Post Processing → Compositing必须勾选
scene.render.use_compositing = True
```

### 陷阱2：Alpha Over顺序错误
```python
# AlphaOver的inputs[1]是底层，inputs[2]是顶层
# 搞反会导致角色被背景遮挡
```

### 陷阱3：View Layer排除逻辑
```python
# exclude=True表示该View Layer不渲染此Collection
# 注意：子Collection的排除是独立的
# 父Collection排除不影响子Collection的设置
```

## 本项目代码关联

`cel_shading.py` L200-300：
- 使用单层渲染方案（简化）
- LineArt通过Grease Pencil叠加
- 未使用Compositor分层（性能优先）

`engine.py`：
- 渲染输出后直接FFmpeg合成
- 无Compositor后处理

## 版本兼容性

- Blender 4.x/5.x: View Layer API稳定
- Blender 5.1.0 Alpha: Compositor节点兼容
- 注意：Blender 4.0+ Grease Pencil改为独立对象类型

## 参考链接

- [Blender Manual: View Layers](https://docs.blender.org/manual/en/latest/scene_layout/view_layers/introduction.html)
- [Blender Manual: Compositor](https://docs.blender.org/manual/en/latest/compositing/index.html)
- [Blender Manual: Render Passes](https://docs.blender.org/manual/en/latest/render/layers/passes.html)
