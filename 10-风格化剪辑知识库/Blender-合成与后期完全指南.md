# Blender 合成与后期完全指南

> 版本: 2025-v1 | 适用: 节点合成/后期特效/输出

## 一、合成器(Compositor)

### 1.1 节点类型

| 类别 | 节点 | 功能 |
|------|------|------|
| 输入 | Render Layers | 渲染层输出 |
| 输入 | Image | 加载图像 |
| 输入 | Movie Clip | 加载视频 |
| 输出 | Composite | 最终输出 |
| 输出 | Viewer | 预览节点 |
| 颜色 | Color Correction | 色彩校正 |
| 颜色 | Bright/Contrast | 亮度对比度 |
| 颜色 | Hue Saturation | 色相饱和度 |
| 颜色 | Curves | 曲线 |
| 滤镜 | Blur | 模糊 |
| 滤镜 | Sharpen | 锐化 |
| 滤镜 | Glare | 光晕 |
| 滤镜 | Lens Distortion | 镜头畸变 |
| 遮罩 | Alpha Over | Alpha叠加 |
| 遮罩 | Set Alpha | 设置Alpha |
| 遮罩 | ID Mask | ID遮罩 |
| 变换 | Scale | 缩放 |
| 变换 | Translate | 平移 |
| 变换 | Rotate | 旋转 |
| 特效 | Tone Map | 色调映射 |
| 特效 | Sun Beams | 阳光光束 |
| 特效 | Vector Blur | 运动模糊 |

### 1.2 合成工作流

```
标准合成流程:
1. 渲染层输出(Render Layers)
2. 色彩校正(Color Correction)
3. 光效添加(Glare/Sun Beams)
4. 模糊/锐化(Blur/Sharpen)
5. 镜头畸变(Lens Distortion)
6. 运动模糊(Vector Blur)
7. 最终输出(Composite)
```

### 1.3 渲染层合成

```
多通道合成:
├── Beauty(基础层)
├── Diffuse Color(漫反射颜色)
├── Diffuse Direct(漫反射直接光)
├── Diffuse Indirect(漫反射间接光)
├── Glossy Color(高光颜色)
├── Glossy Direct(高光直接光)
├── Transmission(透射)
├── Shadow(阴影)
├── Emission(自发光)
├── Environment(环境光)
├── Depth(深度)
├── Normal(法线)
├── UV(纹理坐标)
└── Mist(雾效)

合成:
1. 分别调整每个通道
2. 使用Math/Mix节点组合
3. 最终合成完整图像
```

## 二、后期特效

### 2.1 光效

| 效果 | 节点 | 参数 |
|------|------|------|
| 镜头光晕 | Glare | 类型/阈值/混合 |
| 阳光光束 | Sun Beams | 源位置/光束数 |
| 体积光 | Glare+Fog | 雾效+光效 |
| 发光 | Glare | 强度/大小 |
| 星芒 | Glare(Star) | 星数/角度 |

### 2.2 模糊效果

| 效果 | 节点 | 参数 |
|------|------|------|
| 高斯模糊 | Blur | X/Y尺寸 |
| 运动模糊 | Vector Blur | 速度缩放 |
| 散景模糊 | Defocus | 光圈/焦距 |
| 径向模糊 | Blur(Circular) | 中心/角度 |
| 变焦模糊 | Blur(Zoom) | 中心/因子 |

### 2.3 色彩分级

```
电影感调色:
1. Color Correction节点
   - Lift(暗部): 偏青蓝
   - Gamma(中间调): 微调
   - Gain(亮部): 偏橙黄
   
2. Curves节点
   - RGB曲线: S型增加对比
   - Red曲线: 暗部提升,亮部降低
   - Blue曲线: 暗部降低,亮部提升

3. Hue Saturation
   - 饱和度: 整体降低
   - 特定颜色: 单独调整
```

## 三、输出设置

### 3.1 输出格式

| 格式 | 位深 | Alpha | 用途 |
|------|------|-------|------|
| PNG | 8/16-bit | ✅ | 序列帧 |
| OpenEXR | 16/32-bit | ✅ | 高质量合成 |
| TIFF | 8/16-bit | ✅ | 印刷 |
| JPEG | 8-bit | ❌ | 预览 |
| FFmpeg Video | 可变 | 可变 | 视频输出 |

### 3.2 视频输出

```
FFmpeg视频输出:
1. 输出属性→输出→FFmpeg Video
2. 容器: MP4/MOV/MKV
3. 编码: H.264/H.265/ProRes
4. 质量: 高/中/低 或 自定义码率
5. 音频: AAC/MP3
6. 输出路径
7. 渲染动画(Ctrl+F12)
```

## 四、Python脚本

### 4.1 批量渲染

```python
import bpy
import os

# 设置输出路径
bpy.context.scene.render.filepath = "//renders/"

# 设置输出格式
bpy.context.scene.render.image_settings.file_format = 'PNG'
bpy.context.scene.render.image_settings.color_depth = '16'

# 渲染当前帧
bpy.ops.render.render(write_still=True)

# 渲染动画
bpy.ops.render.render(animation=True)

# 批量渲染多个场景
for scene in bpy.data.scenes:
    bpy.context.window.scene = scene
    bpy.ops.render.render(animation=True)
```

### 4.2 合成节点自动化

```python
import bpy

# 创建合成节点
scene = bpy.context.scene
scene.use_nodes = True
tree = scene.node_tree
nodes = tree.nodes
links = tree.links

# 清除默认节点
nodes.clear()

# 添加渲染层节点
render_layer = nodes.new('CompositorNodeRLayers')
render_layer.location = (0, 0)

# 添加色彩校正节点
color_corr = nodes.new('CompositorNodeColorCorrection')
color_corr.location = (300, 0)

# 添加输出节点
composite = nodes.new('CompositorNodeComposite')
composite.location = (600, 0)

# 连接节点
links.new(render_layer.outputs['Image'], color_corr.inputs['Image'])
links.new(color_corr.outputs['Image'], composite.inputs['Image'])
```
