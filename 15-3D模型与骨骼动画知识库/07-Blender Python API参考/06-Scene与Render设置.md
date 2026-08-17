# Scene与Render设置

## 问题场景

Scene是Blender的顶层容器，包含渲染设置、帧范围、世界环境、视图层等。脚本中需要正确配置Scene才能输出预期的渲染结果。

## 核心原理

### Scene基础

```python
import bpy

# 获取当前场景
scene = bpy.context.scene

# 创建新场景
new_scene = bpy.data.scenes.new("RenderScene")

# 切换活动场景
bpy.context.window.scene = new_scene  # GUI模式
# background模式下通常只有一个场景

# 场景属性
scene.name          # 场景名称
scene.collection    # 根集合（包含所有对象）
scene.world         # 世界环境
scene.camera        # 活动相机
```

### 渲染引擎设置

```python
# 选择渲染引擎
scene.render.engine = 'BLENDER_EEVEE_NEXT'  # EEVEE Next (4.2+)
scene.render.engine = 'BLENDER_EEVEE'       # EEVEE旧版 (4.0-)
scene.render.engine = 'CYCLES'              # Cycles
scene.render.engine = 'BLENDER_WORKBENCH'   # Workbench（简单）

# 检查可用引擎
print(bpy.context.preferences.addons.keys())
```

### 分辨率与帧率

```python
# 分辨率
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.resolution_percentage = 100  # 百分比缩放

# 帧率
scene.render.fps = 30
scene.render.fps_base = 1.0  # 帧率基数（实际fps = fps/fps_base）

# 帧范围
scene.frame_start = 1
scene.frame_end = 60
scene.frame_current = 1  # 当前帧

# 设置当前帧（触发depsgraph更新）
scene.frame_set(30)  # 跳转到第30帧
```

### 输出设置

```python
import os

# 输出路径
scene.render.filepath = "/path/to/output/frame_"
# Blender自动添加帧号：frame_0001.png, frame_0002.png...

# 图像格式
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'  # RGB/RGBA/BW
scene.render.image_settings.color_depth = '8'    # 8/16位
scene.render.image_settings.compression = 15     # PNG压缩(0-100)

# 视频格式（直接输出视频）
scene.render.image_settings.file_format = 'FFMPEG'
scene.render.ffmpeg.format = 'MPEG4'
scene.render.ffmpeg.codec = 'H264'
scene.render.ffmpeg.constant_rate_factor = 'PERC_LOSSLESS'

# 透明背景
scene.render.film_transparent = True  # Alpha通道
```

### 世界环境

```python
# 创建/获取World
world = scene.world
if not world:
    world = bpy.data.worlds.new("World")
    scene.world = world

# 使用节点
world.use_nodes = True
tree = world.node_tree

# 设置背景颜色
bg_node = tree.nodes.get('Background')
if bg_node:
    bg_node.inputs['Color'].default_value = (0.5, 0.5, 0.5, 1.0)  # 灰色
    bg_node.inputs['Strength'].default_value = 0.3  # 强度

# 使用HDRI环境贴图
tex_node = tree.nodes.new('ShaderNodeTexEnvironment')
tex_node.image = bpy.data.images.load("/path/to/hdri.exr")
tree.links.new(tex_node.outputs['Color'], bg_node.inputs['Color'])
```

### 渲染层（View Layer）

```python
# 获取/创建View Layer
vl = scene.view_layers.get("ViewLayer")  # 默认
vl = scene.view_layers.new("Character")  # 新建

# View Layer设置
vl.use_solid = True        # 实体渲染
vl.use_ztransp = True      # 透明
vl.use_strand = True       # 毛发
vl.use_volumes = False     # 体积（关闭提升性能）

# Render Pass
vl.use_pass_combined = True   # 合成图
vl.use_pass_z = True          # 深度
vl.use_pass_normal = True     # 法线
vl.use_pass_mist = True       # 雾效

# Layer Collection排除
lc = vl.layer_collection
for child in lc.children:
    if child.name == "Background":
        child.exclude = True  # 此View Layer不渲染Background集合
```

### 颜色管理

```python
# 颜色管理设置
scene.view_settings.view_transform = 'Standard'  # 标准（无色调映射）
# scene.view_settings.view_transform = 'Filmic'  # 电影感
# scene.view_settings.view_transform = 'AgX'     # Blender 4.0+默认

scene.view_settings.look = 'None'  # 外观LUT

# 三渲二推荐：Standard（保持颜色准确）
scene.view_settings.view_transform = 'Standard'
scene.view_settings.exposure = 0.0
scene.view_settings.gamma = 1.0
```

### 渲染后处理

```python
# Compositor
scene.render.use_compositing = True  # 启用合成器

# 序列编辑器
scene.render.use_sequencer = False

# 边缘/抗锯齿
# EEVEE: 通过采样控制
scene.eevee.taa_render_samples = 64

# Cycles: 通过采样控制
scene.cycles.samples = 128
scene.cycles.use_denoising = True
```

## 常见陷阱

### 陷阱1：输出路径不存在
```python
# Blender不会自动创建输出目录
output_dir = os.path.dirname(scene.render.filepath)
os.makedirs(output_dir, exist_ok=True)
```

### 陷阱2：帧号格式
```python
# filepath末尾的_会自动变成_0001
# 如果想要不同格式：
scene.render.filepath = "/output/frame"  # frame0001.png
scene.render.filepath = "/output/frame_" # frame_0001.png
scene.render.filepath = "/output/"       # 0001.png
```

### 陷阱3：颜色管理导致颜色偏差
```python
# Filmic/AgX会改变颜色输出
# 三渲二需要准确颜色时用Standard
scene.view_settings.view_transform = 'Standard'
```

## 本项目代码关联

`cel_shading.py` L100-200：
- 渲染引擎设置（EEVEE）
- 分辨率1920x1080
- 透明背景

`engine.py`：
- 输出路径配置
- FFmpeg后处理

## 版本兼容性

- Blender 4.0+: AgX为默认颜色管理
- Blender 4.2+: EEVEE_NEXT替代EEVEE
- Blender 5.1.0 Alpha: Scene API稳定

## 参考链接

- [Blender Manual: Scene](https://docs.blender.org/manual/en/latest/scene_layout/scene/index.html)
- [Blender Manual: Render Settings](https://docs.blender.org/manual/en/latest/render/output.html)
