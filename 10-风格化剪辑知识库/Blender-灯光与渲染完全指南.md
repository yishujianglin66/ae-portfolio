# Blender 灯光与渲染完全指南

> 版本: 2025-v1 | 适用: 灯光系统/Cycles渲染/Eevee设置

## 一、灯光系统

### 1.1 灯光类型

| 类型 | 特性 | 用途 |
|------|------|------|
| Point Light | 全方向发光 | 灯泡/蜡烛 |
| Sun Light | 平行光 | 太阳光 |
| Spot Light | 锥形聚光 | 舞台灯/手电筒 |
| Area Light | 矩形面光 | 柔光箱/窗户 |
| Emission | 材质自发光 | 任意形状光源 |

### 1.2 灯光参数

| 参数 | 说明 | 推荐范围 |
|------|------|---------|
| Power(W) | 光功率 | 1-10000W |
| Color | 光颜色 | 色温决定 |
| Radius | 光源大小 | 影响阴影柔和度 |
| Shadow | 投射阴影 | 通常开启 |

### 1.3 色温对照表

| 光源 | 色温(K) | RGB近似 |
|------|---------|---------|
| 蜡烛 | 1850K | #FF8A1E |
| 钨丝灯 | 2700K | #FFA657 |
| 日出 | 3500K | #FFB87A |
| 正午太阳 | 5500K | #FFEDD3 |
| 阴天 | 6500K | #E0E8F0 |
| 蓝天 | 8000K+ | #B3D4FF |

## 二、三点布光

### 2.1 经典三点布光

```
主光(Key Light):
- 位置: 45°侧前, 高于主体
- 强度: 最强(100%)
- 作用: 定义主体形态和阴影方向

辅光(Fill Light):
- 位置: 主光对侧
- 强度: 主光的30-50%
- 作用: 填充阴影,降低对比

背光/轮廓光(Back/Rim Light):
- 位置: 主体后方
- 强度: 与主光相当
- 作用: 勾勒轮廓,分离背景
```

### 2.2 布光方案

| 方案 | 特征 | 情感 |
|------|------|------|
| 高调 | 整体明亮,低对比 | 清新/快乐 |
| 低调 | 整体暗,高对比 | 神秘/戏剧 |
| 伦勃朗 | 45°主光,暗面三角光斑 | 经典肖像 |
| 蝴蝶光 | 正上方主光 | 优雅/时尚 |
| 分割光 | 正侧光,半明半暗 | 双面性 |
| 环形光 | 正面均匀柔光 | 美容/产品 |

## 三、HDRI环境光照

### 3.1 HDRI设置

```
1. Shader Editor → World
2. Environment Texture → 加载HDRI(.hdr/.exr)
3. 调整Mapping节点(旋转/缩放)
4. 调整Strength(强度)
5. 配合ColorRamp控制动态范围
```

### 3.2 HDRI + 额外灯光

```
推荐设置:
- HDRI: 提供环境反射和柔和填充(强度0.3-0.8)
- Sun Light: 提供主光源和硬阴影
- Area Light: 提供辅助柔光
- Emission: 特殊光源(霓虹/屏幕)
```

## 四、Cycles渲染设置

### 4.1 采样设置

| 参数 | 预览 | 最终 | 说明 |
|------|------|------|------|
| Samples | 64-128 | 512-4096 | 采样数 |
| Denoise | 开启 | 开启 | 降噪 |
| Denoise Algorithm | OpenImageDenoise | OptiX/OID | AI降噪 |
| Time Limit | 0 | 0 | 限时渲染 |

### 4.2 光线弹射

| 参数 | 预览 | 最终 | 说明 |
|------|------|------|------|
| Total Bounces | 4 | 12 | 总弹射次数 |
| Diffuse | 2 | 4 | 漫反射弹射 |
| Glossy | 2 | 4 | 镜面反射弹射 |
| Transmission | 4 | 12 | 折射弹射 |
| Volume | 0 | 256 | 体积弹射 |

### 4.3 性能优化

| 设置 | 建议 | 说明 |
|------|------|------|
| GPU渲染 | CUDA/OptiX/HIP | 比CPU快5-10x |
| 降噪 | 开启 | 减少采样需求 |
| 简化 | 预览时降低细分 | 减少几何复杂度 |
| 砖纹理缓存 | 开启 | 避免重复加载 |
| 持久数据 | 开启 | 缓存渲染数据 |

## 五、Eevee渲染设置

### 5.1 关键设置

| 设置 | 作用 | 建议 |
|------|------|------|
| Ambient Occlusion | 环境遮蔽 | 开启 |
| Bloom | 泛光 | 自发光物体开启 |
| Depth of Field | 景深 | 配合摄像机 |
| Screen Space Reflections | 屏幕空间反射 | 开启 |
| Subsurface Scattering | 次表面散射 | 皮肤开启 |
| Shadows | 阴影 | Cascade阴影 |
| Volumetrics | 体积 | 雾/烟/光柱 |

### 5.2 光照探针(Eevee GI)

```
Eevee全局光照:
1. 添加Irradiance Volume(光照探针体积)
2. 添加Reflection Cubemap(反射探针)
3. 烘焙光照: 渲染 → 烘焙间接光照
4. 调整探针密度和范围
```

## 六、渲染输出

### 6.1 输出设置

| 格式 | 用途 | 说明 |
|------|------|------|
| PNG | 序列帧 | 无损,推荐 |
| OpenEXR | 高质量序列 | 32bit浮点,HDR |
| FFmpeg Video | 直接视频 | H.264/H.265 |
| JPEG | 预览 | 有损 |

### 6.2 渲染层(AOV)

| 层 | 用途 |
|----|------|
| Combined | 最终合成 |
| Depth | 深度(后期DOF) |
| Normal | 法线(后期调色) |
| Diffuse Color | 漫反射颜色 |
| Glossy Color | 镜面反射颜色 |
| Emission | 自发光 |
| Shadow | 阴影 |
| Mist | 雾效 |
| Cryptomatte | 物体ID遮罩 |

## 七、Python自动化

### 7.1 基础脚本

```python
import bpy

# 创建物体
bpy.ops.mesh.primitive_cube_add(location=(0,0,0))
obj = bpy.context.active_object

# 设置材质
mat = bpy.data.materials.new("MyMaterial")
mat.use_nodes = True
obj.data.materials.append(mat)

# 修改节点
nodes = mat.node_tree.nodes
principled = nodes["Principled BSDF"]
principled.inputs["Base Color"].default_value = (1, 0, 0, 1)  # 红色
principled.inputs["Metallic"].default_value = 1.0

# 渲染
bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.samples = 128
bpy.ops.render.render(write_still=True)
```

### 7.2 批量渲染脚本

```python
import bpy
import os

# 遍历材质变体
materials = ["Gold", "Silver", "Copper"]
for mat_name in materials:
    mat = bpy.data.materials[mat_name]
    obj.data.materials[0] = mat
    
    # 设置输出路径
    output_path = f"//renders/{mat_name}/frame_####.png"
    bpy.context.scene.render.filepath = output_path
    
    # 渲染
    bpy.ops.render.render(animation=True, write_still=True)
```
