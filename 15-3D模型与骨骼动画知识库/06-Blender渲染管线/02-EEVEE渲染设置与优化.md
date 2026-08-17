# EEVEE渲染设置与优化

## 问题场景

三渲二渲染使用EEVEE（实时渲染引擎）而非Cycles（光线追踪），因为EEVEE速度快且Toon shader效果好。需要正确配置EEVEE参数以获得最佳赛璐璐效果。

## 核心原理

### EEVEE vs Cycles

| 特性 | EEVEE | Cycles |
|------|-------|--------|
| 渲染速度 | 快（实时） | 慢（光线追踪） |
| Toon效果 | 好（硬边明暗） | 一般（需特殊设置） |
| 阴影质量 | 中（需调整） | 高 |
| 反射/折射 | 近似 | 物理准确 |
| 适用场景 | 三渲二/风格化 | 写实渲染 |

### 基本配置

```python
import bpy

def setup_eevee():
    """配置EEVEE渲染"""
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE'
    
    # 分辨率
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 100
    
    # 帧范围
    scene.frame_start = 1
    scene.frame_end = 60
    
    # 输出格式
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'  # 带透明通道
    scene.render.film_transparent = True  # 透明背景
    
    # EEVEE特定设置
    eevee = scene.eevee
    
    # 阴影
    eevee.shadow_cube_size = '2048'
    eevee.shadow_cascade_size = '2048'
    eevee.use_shadow_high_bitdepth = True
    
    # 环境光遮蔽
    eevee.use_gtao = True
    eevee.gtao_distance = 0.5
    
    # 屏幕空间反射（可选）
    eevee.use_ssr = False  # 三渲二通常不需要
    
    # 采样
    eevee.taa_render_samples = 64  # 渲染采样数
```

### Blender 5.x EEVEE Next

```python
# Blender 4.0+ 使用 EEVEE Next（重写版）
# 某些API变化：
# 旧: scene.eevee.use_ssr
# 新: 可能改为 scene.eevee.use_screen_space_reflections

# 检查版本
import bpy
print(f"Blender version: {bpy.app.version_string}")
# 5.1.0 Alpha

# 兼容性处理
if bpy.app.version >= (4, 0, 0):
    # EEVEE Next设置
    pass
```

### 渲染输出路径

```python
def set_output_path(output_dir, frame_start=1, frame_end=60):
    """设置帧输出路径"""
    scene = bpy.context.scene
    
    # 确保目录存在
    import os
    os.makedirs(output_dir, exist_ok=True)
    
    # 设置输出路径（使用帧号占位符）
    scene.render.filepath = os.path.join(output_dir, "frame_")
    # Blender自动添加 #### 帧号
    # 输出: frame_0001.png, frame_0002.png, ...
```

## 常见陷阱

### 陷阱1：EEVEE阴影锯齿
```python
# 解决：增加阴影贴图分辨率
eevee.shadow_cube_size = '4096'
# 或增加采样数
eevee.taa_render_samples = 128
```

### 陷阱2：透明背景不生效
```python
# 必须同时设置：
scene.render.film_transparent = True
scene.render.image_settings.color_mode = 'RGBA'
```

## 本项目代码关联

`cel_shading.py` L200-300：EEVEE渲染设置
- resolution: 1920×1080
- film_transparent: True
- taa_render_samples: 64

## 版本兼容性

- Blender 4.x: EEVEE Next（重写版）
- Blender 5.1.0 Alpha: EEVEE Next稳定

## 参考链接

- [Blender Manual: EEVEE](https://docs.blender.org/manual/en/latest/render/eevee/index.html)
