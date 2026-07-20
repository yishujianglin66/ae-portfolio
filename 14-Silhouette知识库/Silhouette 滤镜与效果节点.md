# Silhouette 滤镜与效果节点

> 分类: 节点与合成系统
> 更新日期: 2026-07-11
> 概述: FilterNode 详解、模糊/锐化/噪点/扭曲效果及参数详解。

## 目录
1. [Filter 节点概述](#1-filter-节点概述)
2. [节点参数详解](#2-节点参数详解)
3. [模糊效果](#3-模糊效果)
4. [锐化效果](#4-锐化效果)
5. [噪点效果](#5-噪点效果)
6. [扭曲效果](#6-扭曲效果)
7. [其他效果](#7-其他效果)
8. [最佳实践](#8-最佳实践)

---

## 1. Filter 节点概述

Filter 节点提供各种图像处理滤镜,包括模糊、锐化、噪点、扭曲等。

### 1.1 节点结构

```
inputs[0] — 主输入(待处理图像)
inputs[1] — Matte(可选,限制效果范围)
         ↓
    [Filter Node]
         ↓
outputs[0] — 处理结果
```

### 1.2 效果分类

| 分类 | 效果 | 典型用途 |
|------|------|----------|
| 模糊 | Box Blur, Gaussian Blur, Motion Blur, Defocus | 景深、运动模糊 |
| 锐化 | Sharpen, Unsharp Mask | 细节增强 |
| 噪点 | Add Noise, Remove Noise, Film Grain | 质感、降噪 |
| 扭曲 | Displacement, Warp, Lens Distortion | 变形、镜头校正 |
| 风格化 | Edge Detect, Posterize, Threshold | 特殊效果 |
| 时间 | Optical Flow, Temporal Blur | 帧间处理 |

## 2. 节点参数详解

### 2.1 通用参数

| 参数名 | 类型 | 说明 |
|--------|------|------|
| `filterType` | menu | 滤镜类型选择 |
| `amount` | float | 效果强度(0-1) |
| `radius` | float | 作用半径(像素) |
| `threshold` | float | 阈值 |
| `mixAmount` | float | 原图与效果混合 |
| `matteChannel` | menu | 遮罩通道选择 |
| `invertMatte` | bool | 反转遮罩 |

### 2.2 filterType 选项

| 值 | 说明 |
|----|------|
| `box_blur` | 盒式模糊(快速) |
| `gaussian_blur` | 高斯模糊(平滑) |
| `motion_blur` | 运动模糊 |
| `defocus` | 散焦模糊(景深) |
| `sharpen` | 锐化 |
| `unsharp_mask` | USM 锐化 |
| `add_noise` | 添加噪点 |
| `remove_noise` | 降噪 |
| `film_grain` | 胶片颗粒 |
| `displacement` | 置换 |
| `warp` | 弯曲变形 |
| `lens_distortion` | 镜头畸变 |
| `edge_detect` | 边缘检测 |
| `posterize` | 色调分离 |
| `threshold` | 阈值二值化 |

## 3. 模糊效果

### 3.1 Box Blur(盒式模糊)

最快的模糊算法,质量较低但速度极快。

```python
from fx import *

def apply_box_blur(session, source, radius=5.0):
    """应用盒式模糊"""
    f = Node("Filter")
    f.label = "Box_Blur"
    session.addNode(f)
    f.inputs[0].connect(source.outputs[0])
    
    f.property("filterType").setValue("box_blur", 0)
    f.property("radius").setValue(radius, 0)
    
    return f
```

**参数**:
- `radius`:模糊半径(像素),范围 0-100
- 适合预览和快速处理

### 3.2 Gaussian Blur(高斯模糊)

高质量模糊,边缘平滑。

```python
def apply_gaussian_blur(session, source, radius=5.0, amount=1.0):
    """应用高斯模糊"""
    f = Node("Filter")
    f.label = "Gaussian_Blur"
    session.addNode(f)
    f.inputs[0].connect(source.outputs[0])
    
    f.property("filterType").setValue("gaussian_blur", 0)
    f.property("radius").setValue(radius, 0)
    f.property("amount").setValue(amount, 0)
    
    return f
```

**参数**:
- `radius`:模糊半径(像素),范围 0-100
- `amount`:模糊强度(0-1),1.0 为完全模糊
- 适合最终输出

### 3.3 Motion Blur(运动模糊)

模拟运动产生的模糊。

```python
def apply_motion_blur(session, source, angle=0, length=10):
    """应用运动模糊
    angle: 运动方向(度)
    length: 模糊长度(像素)
    """
    f = Node("Filter")
    f.label = "Motion_Blur"
    session.addNode(f)
    f.inputs[0].connect(source.outputs[0])
    
    f.property("filterType").setValue("motion_blur", 0)
    f.property("angle").setValue(angle, 0)
    f.property("length").setValue(length, 0)
    
    return f

# 示例:水平运动模糊
apply_motion_blur(session, source, angle=0, length=15)

# 示例:对角线运动模糊
apply_motion_blur(session, source, angle=45, length=20)
```

**参数**:
- `angle`:运动方向(0-360 度)
- `length`:模糊长度(像素)
- 适合模拟快速运动物体

### 3.4 Defocus(散焦模糊)

模拟镜头散焦效果,用于景深。

```python
def apply_defocus(session, source, radius=10, blades=8, bokeh="round"):
    """应用散焦模糊
    radius: 散焦半径
    blades: 光圈叶片数
    bokeh: 散焦形状
    """
    f = Node("Filter")
    f.label = "Defocus"
    session.addNode(f)
    f.inputs[0].connect(source.outputs[0])
    
    f.property("filterType").setValue("defocus", 0)
    f.property("radius").setValue(radius, 0)
    
    blades_prop = f.property("blades")
    if blades_prop:
        blades_prop.setValue(blades, 0)
    
    bokeh_prop = f.property("bokehShape")
    if bokeh_prop:
        bokeh_prop.setValue(bokeh, 0)
    
    return f
```

**参数**:
- `radius`:散焦半径(像素)
- `blades`:光圈叶片数(影响焦外光斑形状)
- `bokeh`:散焦形状(round, hexagonal, octagonal)
- 适合景深效果

### 3.5 模糊效果对比

| 类型 | 速度 | 质量 | 适用场景 |
|------|------|------|----------|
| Box Blur | 最快 | 低 | 预览、遮罩边缘 |
| Gaussian Blur | 中 | 高 | 最终输出 |
| Motion Blur | 中 | 高 | 运动模拟 |
| Defocus | 慢 | 最高 | 景深效果 |

## 4. 锐化效果

### 4.1 Sharpen(基本锐化)

```python
def apply_sharpen(session, source, amount=0.5, radius=1.0):
    """应用锐化"""
    f = Node("Filter")
    f.label = "Sharpen"
    session.addNode(f)
    f.inputs[0].connect(source.outputs[0])
    
    f.property("filterType").setValue("sharpen", 0)
    f.property("amount").setValue(amount, 0)
    f.property("radius").setValue(radius, 0)
    
    return f
```

**参数**:
- `amount`:锐化强度(0-1)
- `radius`:锐化半径(像素),通常 0.5-2

### 4.2 Unsharp Mask(USM 锐化)

更精细的锐化算法,通过提取高频细节进行增强。

```python
def apply_unsharp_mask(session, source, amount=0.5, radius=1.0, threshold=0.0):
    """应用 USM 锐化
    amount: 锐化强度
    radius: 半径
    threshold: 阈值(低于此值不锐化)
    """
    f = Node("Filter")
    f.label = "USM_Sharpen"
    session.addNode(f)
    f.inputs[0].connect(source.outputs[0])
    
    f.property("filterType").setValue("unsharp_mask", 0)
    f.property("amount").setValue(amount, 0)
    f.property("radius").setValue(radius, 0)
    f.property("threshold").setValue(threshold, 0)
    
    return f

# 示例:轻度锐化
apply_unsharp_mask(session, source, amount=0.3, radius=1.0, threshold=0.05)

# 示例:强锐化(适合细节丰富的图像)
apply_unsharp_mask(session, source, amount=0.8, radius=0.5, threshold=0.0)
```

**参数详解**:
- `amount`:锐化强度(0-1),过高会产生光晕
- `radius`:影响边缘的范围(像素),小半径=细节锐化
- `threshold`:阈值(0-1),只锐化对比度高于此值的区域

### 4.3 锐化策略

| 图像类型 | amount | radius | threshold |
|----------|--------|--------|-----------|
| 人像 | 0.2-0.4 | 1.0-2.0 | 0.05-0.1 |
| 风景 | 0.4-0.6 | 0.5-1.0 | 0.0-0.03 |
| 建筑 | 0.5-0.8 | 0.5-1.0 | 0.0 |
| 文字/图形 | 0.6-1.0 | 0.3-0.5 | 0.0 |

## 5. 噪点效果

### 5.1 Add Noise(添加噪点)

```python
def add_noise(session, source, amount=0.1, type="gaussian", monochrome=False):
    """添加噪点
    amount: 噪点强度(0-1)
    type: 噪点类型(gaussian, uniform, salt_pepper)
    monochrome: 是否单色噪点
    """
    f = Node("Filter")
    f.label = "Add_Noise"
    session.addNode(f)
    f.inputs[0].connect(source.outputs[0])
    
    f.property("filterType").setValue("add_noise", 0)
    f.property("amount").setValue(amount, 0)
    f.property("noiseType").setValue(type, 0)
    f.property("monochrome").setValue(monochrome, 0)
    
    return f

# 示例:添加胶片质感噪点
add_noise(session, source, amount=0.05, type="gaussian", monochrome=True)
```

### 5.2 Remove Noise(降噪)

```python
def remove_noise(session, source, amount=0.3, radius=2.0, preserve_edges=True):
    """降噪
    amount: 降噪强度
    radius: 采样半径
    preserve_edges: 是否保留边缘
    """
    f = Node("Filter")
    f.label = "Denoise"
    session.addNode(f)
    f.inputs[0].connect(source.outputs[0])
    
    f.property("filterType").setValue("remove_noise", 0)
    f.property("amount").setValue(amount, 0)
    f.property("radius").setValue(radius, 0)
    f.property("preserveEdges").setValue(preserve_edges, 0)
    
    return f
```

### 5.3 Film Grain(胶片颗粒)

模拟真实胶片的颗粒感。

```python
def add_film_grain(session, source, amount=0.1, size=1.0, iso=400):
    """添加胶片颗粒
    amount: 颗粒强度
    size: 颗粒大小
    iso: 模拟的 ISO 感光度(影响颗粒粗细)
    """
    f = Node("Filter")
    f.label = "Film_Grain"
    session.addNode(f)
    f.inputs[0].connect(source.outputs[0])
    
    f.property("filterType").setValue("film_grain", 0)
    f.property("amount").setValue(amount, 0)
    
    size_prop = f.property("grainSize")
    if size_prop:
        size_prop.setValue(size, 0)
    
    iso_prop = f.property("iso")
    if iso_prop:
        iso_prop.setValue(iso, 0)
    
    return f

# 常见胶片颗粒预设
GRAIN_PRESETS = {
    "fine": {"amount": 0.03, "size": 0.8, "iso": 100},
    "medium": {"amount": 0.06, "size": 1.0, "iso": 400},
    "coarse": {"amount": 0.12, "size": 1.5, "iso": 1600},
    "vintage": {"amount": 0.15, "size": 1.2, "iso": 800}
}

def apply_grain_preset(session, source, preset_name):
    """应用胶片颗粒预设"""
    if preset_name in GRAIN_PRESETS:
        return add_film_grain(session, source, **GRAIN_PRESETS[preset_name])
    return None
```

## 6. 扭曲效果

### 6.1 Displacement(置换)

使用置换图扭曲图像。

```python
def apply_displacement(session, source, displacement_map, amount=10):
    """应用置换扭曲
    displacement_map: 置换图节点(通常是灰度图)
    amount: 置换强度(像素)
    """
    f = Node("Filter")
    f.label = "Displacement"
    session.addNode(f)
    f.inputs[0].connect(source.outputs[0])
    f.inputs[1].connect(displacement_map.outputs[0])  # 置换图
    
    f.property("filterType").setValue("displacement", 0)
    f.property("amount").setValue(amount, 0)
    
    return f
```

### 6.2 Warp(弯曲变形)

```python
def apply_warp(session, source, warp_type="twirl", amount=0.5, center=(0.5, 0.5)):
    """应用弯曲变形
    warp_type: 变形类型(twirl, bulge, pinch, wave)
    amount: 变形强度
    center: 变形中心(归一化坐标)
    """
    f = Node("Filter")
    f.label = f"Warp_{warp_type}"
    session.addNode(f)
    f.inputs[0].connect(source.outputs[0])
    
    f.property("filterType").setValue("warp", 0)
    f.property("warpType").setValue(warp_type, 0)
    f.property("amount").setValue(amount, 0)
    
    center_prop = f.property("center")
    if center_prop:
        center_prop.setValue(center, 0)
    
    return f

# 示例:中心涡旋
apply_warp(session, source, warp_type="twirl", amount=0.8, center=(0.5, 0.5))

# 示例:边缘膨胀
apply_warp(session, source, warp_type="bulge", amount=0.5, center=(0.5, 0.5))
```

### 6.3 Lens Distortion(镜头畸变)

```python
def apply_lens_distortion(session, source, distortion_type="barrel", amount=0.1):
    """应用镜头畸变
    distortion_type: 畸变类型(barrel, pincushion, mustache)
    amount: 畸变量(正值=桶形,负值=枕形)
    """
    f = Node("Filter")
    f.label = "Lens_Distortion"
    session.addNode(f)
    f.inputs[0].connect(source.outputs[0])
    
    f.property("filterType").setValue("lens_distortion", 0)
    f.property("distortionType").setValue(distortion_type, 0)
    f.property("amount").setValue(amount, 0)
    
    return f

# 示例:校正广角镜头畸变
apply_lens_distortion(session, source, distortion_type="barrel", amount=-0.15)
```

## 7. 其他效果

### 7.1 Edge Detect(边缘检测)

```python
def apply_edge_detect(session, source, sensitivity=0.5, invert=False):
    """边缘检测"""
    f = Node("Filter")
    f.label = "Edge_Detect"
    session.addNode(f)
    f.inputs[0].connect(source.outputs[0])
    
    f.property("filterType").setValue("edge_detect", 0)
    f.property("sensitivity").setValue(sensitivity, 0)
    f.property("invert").setValue(invert, 0)
    
    return f
```

### 7.2 Posterize(色调分离)

```python
def apply_posterize(session, source, levels=8):
    """色调分离
    levels: 色阶数(每通道)
    """
    f = Node("Filter")
    f.label = "Posterize"
    session.addNode(f)
    f.inputs[0].connect(source.outputs[0])
    
    f.property("filterType").setValue("posterize", 0)
    f.property("levels").setValue(levels, 0)
    
    return f
```

### 7.3 Threshold(阈值二值化)

```python
def apply_threshold(session, source, threshold=0.5, channel="luminance"):
    """阈值二值化"""
    f = Node("Filter")
    f.label = "Threshold"
    session.addNode(f)
    f.inputs[0].connect(source.outputs[0])
    
    f.property("filterType").setValue("threshold", 0)
    f.property("threshold").setValue(threshold, 0)
    f.property("channel").setValue(channel, 0)
    
    return f
```

## 8. 最佳实践

### 8.1 效果选择指南

```
需要模糊?
├─ 快速预览 → Box Blur
├─ 高质量 → Gaussian Blur
├─ 运动模拟 → Motion Blur
└─ 景深 → Defocus

需要锐化?
├─ 简单锐化 → Sharpen
└─ 精细控制 → Unsharp Mask

需要噪点?
├─ 添加质感 → Add Noise / Film Grain
└─ 降噪 → Remove Noise

需要变形?
├─ 基于贴图 → Displacement
├─ 程序化 → Warp
└─ 镜头校正 → Lens Distortion
```

### 8.2 性能优化

```python
# 1. 预览时用低质量,最终输出用高质量
def preview_blur(session, source):
    """预览用快速模糊"""
    return apply_box_blur(session, source, radius=5)

def final_blur(session, source):
    """最终用高质量模糊"""
    return apply_gaussian_blur(session, source, radius=5, amount=1.0)

# 2. 使用遮罩限制效果范围,减少计算量
def localized_blur(session, source, matte_node):
    """局部模糊"""
    f = apply_gaussian_blur(session, source, radius=10)
    # 连接遮罩限制范围
    if len(f.inputs) > 1:
        f.inputs[1].connect(matte_node.outputs[0])
    return f

# 3. 合并相似效果
# 错误:先模糊再添加噪点(两次遍历)
# 正确:如果可能,使用一个复合滤镜
```

### 8.3 参数动画

```python
def animate_blur(f_node, keyframes):
    """为模糊半径添加关键帧"""
    prop = f_node.property("radius")
    if not prop:
        return False
    for frame, value in keyframes:
        prop.setValue(value, frame)
    return True

def focus_pull(session, source, start_frame, duration, near_radius=2, far_radius=15):
    """模拟焦点转换"""
    f = apply_gaussian_blur(session, source, radius=near_radius)
    animate_blur(f, [
        (start_frame, near_radius),
        (start_frame + duration, far_radius)
    ])
    return f
```

### 8.4 调试技巧

```python
def debug_filter(f_node):
    """调试 Filter 节点"""
    print(f"=== {f_node.label} ===")
    for name in ["filterType", "amount", "radius", "threshold",
                 "mixAmount", "matteChannel", "invertMatte"]:
        prop = f_node.property(name)
        if prop:
            print(f"  {name}: {prop.value}")

def bypass_filter(f_node):
    """临时绕过效果"""
    mix_prop = f_node.property("mixAmount")
    if mix_prop:
        original = mix_prop.value
        mix_prop.setValue(0.0, 0)
        return original
    return None
```

### 8.5 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 效果不明显 | amount 太低 | 提高 amount 值 |
| 边缘出现光晕 | 锐化过度 | 降低 amount 或提高 threshold |
| 画面变慢 | 模糊半径过大 | 减小 radius 或用 Box Blur |
| 噪点过强 | amount 太高 | 降低 amount 或改用 Film Grain |
| 扭曲失真 | amount 过大 | 减小 amount,检查置换图 |

---

## 附录:效果参数速查表

| 效果 | 关键参数 | 范围 | 推荐值 |
|------|----------|------|--------|
| Box Blur | radius | 0-100 | 2-10 |
| Gaussian Blur | radius, amount | 0-100, 0-1 | 2-10, 1.0 |
| Motion Blur | angle, length | 0-360, 0-100 | 视场景 |
| Defocus | radius, blades | 0-50, 3-16 | 5-20, 8 |
| Sharpen | amount, radius | 0-1, 0-10 | 0.2-0.6, 0.5-2 |
| USM Sharpen | amount, radius, threshold | 0-1, 0-10, 0-1 | 0.3-0.8, 0.5-2, 0-0.1 |
| Add Noise | amount | 0-1 | 0.02-0.1 |
| Film Grain | amount, size | 0-1, 0-5 | 0.03-0.15, 0.8-1.5 |
| Displacement | amount | 0-100 | 5-30 |
| Lens Distortion | amount | -1 to 1 | ±0.1-0.3 |

> **提示**:所有滤镜效果都支持遮罩输入,通过遮罩可以精确控制效果作用范围,避免影响不需要处理的区域。
