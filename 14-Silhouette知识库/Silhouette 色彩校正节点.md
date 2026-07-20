# Silhouette 色彩校正节点

> 分类: 节点与合成系统
> 更新日期: 2026-07-11
> 概述: ColorNode 参数详解、Lift/Gamma/Gain、色相饱和度、曲线调整完整说明。

## 目录
1. [Color 节点概述](#1-color-节点概述)
2. [节点参数详解](#2-节点参数详解)
3. [Lift/Gamma/Gain](#3-liftgammagain)
4. [色相与饱和度](#4-色相与饱和度)
5. [曲线调整](#5-曲线调整)
6. [高级色彩工具](#6-高级色彩工具)
7. [脚本化色彩校正](#7-脚本化色彩校正)
8. [最佳实践](#8-最佳实践)

---

## 1. Color 节点概述

Color 节点是 Silhouette 的核心色彩校正节点,提供 Lift/Gamma/Gain、色相/饱和度、曲线等完整调色工具。

### 1.1 核心能力

| 能力 | 说明 |
|------|------|
| Lift/Gamma/Gain | 三路色彩校正 |
| 色相/饱和度 | 全局或分通道调整 |
| 曲线调整 | RGB/单独通道曲线 |
| 色彩平衡 | 阴影/中间调/高光 |
| 关键帧动画 | 所有参数可关键帧 |
| 遮罩限制 | 可通过 matte 输入限制范围 |

### 1.2 节点结构

```
inputs[0] — 主输入(待校正图像)
inputs[1] — Matte(可选,限制校正范围)
         ↓
    [Color Node]
         ↓
outputs[0] — 校正后图像
```

## 2. 节点参数详解

### 2.1 参数分类

| 分类 | 参数 | 类型 | 说明 |
|------|------|------|------|
| 基础 | `lift` | color | 阴影偏移 |
| 基础 | `gamma` | float/double | 中间调伽马 |
| 基础 | `gain` | color | 高光增益 |
| 基础 | `offset` | color | 整体偏移 |
| 基础 | `contrast` | float | 对比度 |
| 色相 | `hue` | float | 色相旋转 |
| 色相 | `saturation` | float | 饱和度 |
| 色相 | `vibrance` | float | 自然饱和度 |
| 曲线 | `redCurve` | curve | 红通道曲线 |
| 曲线 | `greenCurve` | curve | 绿通道曲线 |
| 曲线 | `blueCurve` | curve | 蓝通道曲线 |
| 曲线 | `rgbCurve` | curve | RGB 主曲线 |
| 混合 | `mixAmount` | float | 原图与校正混合 |
| 输出 | `outputAlpha` | bool | 是否输出 Alpha |

### 2.2 参数范围

| 参数 | 范围 | 默认值 | 单位 |
|------|------|--------|------|
| `lift` | (-1, 1) | (0, 0, 0, 0) | 每通道 |
| `gamma` | (0.01, 10) | 1.0 | 标量或每通道 |
| `gain` | (0, 10) | (1, 1, 1, 1) | 每通道 |
| `offset` | (-1, 1) | (0, 0, 0, 0) | 每通道 |
| `contrast` | (0, 4) | 1.0 | 标量 |
| `hue` | (-180, 180) | 0.0 | 度 |
| `saturation` | (0, 4) | 1.0 | 标量 |
| `vibrance` | (-100, 100) | 0.0 | 百分比 |
| `mixAmount` | (0, 1) | 1.0 | 比例 |

## 3. Lift/Gamma/Gain

### 3.1 Lift(阴影)

Lift 调整图像的阴影区域,主要影响暗部。

```python
def set_lift(color_node, r=0.0, g=0.0, b=0.0):
    """设置 Lift 参数"""
    prop = color_node.property("lift")
    if prop:
        prop.setValue((r, g, b, 0.0), 0)

# 示例:给阴影加暖色(偏红黄)
set_lift(color_node, r=0.05, g=0.02, b=-0.05)
```

**Lift 数学原理**:
```
output = input × (1 - lift) + lift
```
- 正值:提亮阴影,加入该颜色
- 负值:压暗阴影,减少该颜色

### 3.2 Gamma(中间调)

Gamma 调整图像的中间调,使用幂函数。

```python
def set_gamma(color_node, gamma=1.0, r=None, g=None, b=None):
    """设置 Gamma 参数"""
    if r is not None and g is not None and b is not None:
        # 每通道 gamma
        prop = color_node.property("gamma")
        if prop:
            prop.setValue((r, g, b, 1.0), 0)
    else:
        # 全局 gamma
        prop = color_node.property("gamma")
        if prop:
            prop.setValue(gamma, 0)

# 示例:提亮中间调
set_gamma(color_node, gamma=1.2)

# 示例:给中间调加冷色(降低红通道)
set_gamma(color_node, r=1.1, g=1.2, b=1.3)
```

**Gamma 数学原理**:
```
output = input ^ (1/gamma)
```
- gamma > 1:提亮中间调
- gamma < 1:压暗中间调

### 3.3 Gain(高光)

Gain 调整图像的高光区域,主要影响亮部。

```python
def set_gain(color_node, r=1.0, g=1.0, b=1.0):
    """设置 Gain 参数"""
    prop = color_node.property("gain")
    if prop:
        prop.setValue((r, g, b, 1.0), 0)

# 示例:给高光加冷色
set_gain(color_node, r=0.95, g=1.0, b=1.05)
```

**Gain 数学原理**:
```
output = input × gain
```
- gain > 1:提亮高光
- gain < 1:压暗高光

### 3.4 完整 LGD 调色

```python
def apply_lgd(color_node, lift=(0, 0, 0), gamma=1.0, gain=(1, 1, 1)):
    """应用完整的 Lift/Gamma/Gain 调色"""
    set_lift(color_node, *lift)
    set_gamma(color_node, gamma)
    set_gain(color_node, *gain)
    return color_node

# 常用调色预设
PRESETS = {
    "warm_shadow": {
        "lift": (0.05, 0.02, -0.05),
        "gamma": 1.0,
        "gain": (1.05, 1.02, 0.95)
    },
    "cool_highlight": {
        "lift": (-0.02, 0, 0.05),
        "gamma": 1.0,
        "gain": (0.95, 1.0, 1.05)
    },
    "bleach_bypass": {
        "lift": (-0.05, -0.05, -0.05),
        "gamma": 1.1,
        "gain": (1.2, 1.2, 1.2)
    },
    "night_look": {
        "lift": (-0.1, -0.05, 0.05),
        "gamma": 0.9,
        "gain": (0.8, 0.85, 1.0)
    }
}

def apply_preset(color_node, preset_name):
    """应用预设调色"""
    if preset_name in PRESETS:
        apply_lgd(color_node, **PRESETS[preset_name])
```

## 4. 色相与饱和度

### 4.1 色相调整

```python
def set_hue(color_node, hue_shift=0.0):
    """设置色相旋转(度)"""
    prop = color_node.property("hue")
    if prop:
        prop.setValue(hue_shift, 0)

# 示例:色相偏移 10 度
set_hue(color_node, 10.0)
```

### 4.2 饱和度调整

```python
def set_saturation(color_node, sat=1.0):
    """设置饱和度"""
    prop = color_node.property("saturation")
    if prop:
        prop.setValue(sat, 0)

# 示例:增加饱和度
set_saturation(color_node, 1.3)

# 示例:去饱和(黑白效果)
set_saturation(color_node, 0.0)
```

### 4.3 Vibrance(自然饱和度)

```python
def set_vibrance(color_node, vibrance=0):
    """设置自然饱和度
    vibrance: -100 到 100
    正值:增加低饱和度区域的饱和度
    负值:降低饱和度
    """
    prop = color_node.property("vibrance")
    if prop:
        prop.setValue(vibrance, 0)
```

### 4.4 色相饱和度组合

```python
def adjust_hsv(color_node, hue=0, saturation=1.0, vibrance=0):
    """组合调整色相、饱和度、自然饱和度"""
    set_hue(color_node, hue)
    set_saturation(color_node, saturation)
    set_vibrance(color_node, vibrance)
    return color_node

# 常见 HSV 调整
HSV_PRESETS = {
    "vintage": {"hue": -5, "saturation": 0.8, "vibrance": -20},
    "punchy": {"hue": 0, "saturation": 1.3, "vibrance": 30},
    "muted": {"hue": 0, "saturation": 0.7, "vibrance": -30},
    "filmic": {"hue": 2, "saturation": 0.9, "vibrance": 10}
}
```

## 5. 曲线调整

### 5.1 RGB 主曲线

```python
def set_rgb_curve(color_node, points):
    """
    设置 RGB 主曲线
    points: [(input_val, output_val), ...]
    例如:[(0, 0.1), (0.5, 0.5), (1, 0.9)] — S 曲线
    """
    prop = color_node.property("rgbCurve")
    if not prop:
        return False
    
    # 设置曲线点(具体 API 取决于实现)
    for i, (x, y) in enumerate(points):
        # 添加曲线点
        pass  # 实际 API 调用
    
    return True
```

### 5.2 常见曲线预设

```python
# S 曲线(增强对比度)
S_CURVE = [(0, 0), (0.25, 0.15), (0.5, 0.5), (0.75, 0.85), (1, 1)]

# 反 S 曲线(降低对比度)
INVERSE_S = [(0, 0.1), (0.25, 0.3), (0.5, 0.5), (0.75, 0.7), (1, 0.9)]

# 提亮暗部
LIFT_SHADOWS = [(0, 0.1), (0.25, 0.3), (0.5, 0.55), (0.75, 0.8), (1, 1)]

# 压暗高光
CRUSH_HIGHLIGHTS = [(0, 0), (0.25, 0.2), (0.5, 0.5), (0.75, 0.7), (1, 0.85)]

def apply_curve_preset(color_node, preset_name):
    """应用曲线预设"""
    presets = {
        "s_curve": S_CURVE,
        "inverse_s": INVERSE_S,
        "lift_shadows": LIFT_SHADOWS,
        "crush_highlights": CRUSH_HIGHLIGHTS
    }
    if preset_name in presets:
        return set_rgb_curve(color_node, presets[preset_name])
    return False
```

### 5.3 单通道曲线

```python
def set_channel_curve(color_node, channel, points):
    """
    设置单通道曲线
    channel: "red", "green", "blue"
    points: [(input, output), ...]
    """
    prop_name = f"{channel}Curve"
    prop = color_node.property(prop_name)
    if not prop:
        return False
    # 设置曲线点
    return True

# 示例:给红色通道暗部加红
set_channel_curve(color_node, "red", 
                  [(0, 0.05), (0.5, 0.5), (1, 1)])
```

## 6. 高级色彩工具

### 6.1 色彩平衡

```python
def set_color_balance(color_node, shadows=(0,0,0), midtones=(0,0,0), highlights=(0,0,0)):
    """设置色彩平衡(阴影/中间调/高光)"""
    # Silhouette 可能通过单独的属性或子节点实现
    # 概念性实现
    for range_name, values in [("shadows", shadows), 
                                 ("midtones", midtones),
                                 ("highlights", highlights)]:
        prop = color_node.property(f"{range_name}Balance")
        if prop:
            prop.setValue(values, 0)
```

### 6.2 对比度调整

```python
def set_contrast(color_node, contrast=1.0, pivot=0.5):
    """设置对比度"""
    prop = color_node.property("contrast")
    if prop:
        prop.setValue(contrast, 0)
    
    # pivot 是对比度中心点
    pivot_prop = color_node.property("contrastPivot")
    if pivot_prop:
        pivot_prop.setValue(pivot, 0)
```

### 6.3 输出范围

```python
def set_output_range(color_node, low=0.0, high=1.0):
    """设置输出范围(限制亮度范围)"""
    low_prop = color_node.property("outputLow")
    if low_prop:
        low_prop.setValue(low, 0)
    
    high_prop = color_node.property("outputHigh")
    if high_prop:
        high_prop.setValue(high, 0)
```

## 7. 脚本化色彩校正

### 7.1 创建调色节点

```python
from fx import *

def create_color_node(session, source, label="CC"):
    """创建并连接 Color 节点"""
    color = Node("Color")
    color.label = label
    session.addNode(color)
    color.inputs[0].connect(source.outputs[0])
    return color
```

### 7.2 关键帧动画

```python
def animate_gamma(color_node, keyframes):
    """
    为 gamma 添加关键帧
    keyframes: [(frame, value), ...]
    """
    prop = color_node.property("gamma")
    if not prop:
        return False
    for frame, value in keyframes:
        prop.setValue(value, frame)
    return True

def day_to_night_transition(color_node, start_frame, duration):
    """日转夜效果动画"""
    # 初始:明亮暖色
    # 结束:冷色低亮度
    end_frame = start_frame + duration
    
    # gamma 从 1.0 渐变到 0.8
    animate_gamma(color_node, [(start_frame, 1.0), (end_frame, 0.8)])
    
    # 色相从 0 渐变到 -10
    hue_prop = color_node.property("hue")
    if hue_prop:
        hue_prop.setValue(0, start_frame)
        hue_prop.setValue(-10, end_frame)
    
    # 饱和度从 1.0 渐变到 0.7
    sat_prop = color_node.property("saturation")
    if sat_prop:
        sat_prop.setValue(1.0, start_frame)
        sat_prop.setValue(0.7, end_frame)
    
    # gain 从 1.0 渐变到 0.8(整体压暗)
    gain_prop = color_node.property("gain")
    if gain_prop:
        gain_prop.setValue((1.0, 1.0, 1.0, 1.0), start_frame)
        gain_prop.setValue((0.8, 0.85, 1.0, 1.0), end_frame)  # 偏蓝
```

### 7.3 限制范围调色

```python
def masked_color_correction(session, source, matte_node):
    """使用遮罩限制调色范围"""
    color = Node("Color")
    color.label = "CC_Masked"
    session.addNode(color)
    color.inputs[0].connect(source.outputs[0])
    
    # 连接遮罩到第二个输入
    if len(color.inputs) > 1:
        color.inputs[1].connect(matte_node.outputs[0])
    
    return color
```

### 7.4 多节点调色链

```python
def build_grading_chain(session, source):
    """
    构建多节点调色链:
    Source → Primary CC → Secondary CC → Output
    """
    # 一级调色
    primary = create_color_node(session, source, "CC_Primary")
    apply_lgd(primary, 
              lift=(-0.02, -0.02, -0.02),
              gamma=1.05,
              gain=(1.02, 1.02, 1.02))
    
    # 二级调色(色彩风格)
    secondary = create_color_node(session, primary, "CC_Secondary")
    adjust_hsv(secondary, hue=5, saturation=1.1, vibrance=15)
    
    return primary, secondary
```

### 7.5 调色信息导出

```python
def export_grade(color_node):
    """导出调色参数"""
    grade = {
        "label": color_node.label,
        "lift": color_node.property("lift").value if color_node.property("lift") else None,
        "gamma": color_node.property("gamma").value if color_node.property("gamma") else None,
        "gain": color_node.property("gain").value if color_node.property("gain") else None,
        "hue": color_node.property("hue").value if color_node.property("hue") else None,
        "saturation": color_node.property("saturation").value if color_node.property("saturation") else None,
    }
    return grade

def import_grade(color_node, grade_data):
    """导入调色参数"""
    for param, value in grade_data.items():
        if param == "label":
            continue
        prop = color_node.property(param)
        if prop and value is not None:
            prop.setValue(value, 0)
```

## 8. 最佳实践

### 8.1 调色顺序

推荐的调色操作顺序:

```
1. Lift — 调整阴影(黑点)
2. Gain — 调整高光(白点)
3. Gamma — 调整中间调
4. Contrast — 增强对比度
5. Hue/Saturation — 色彩风格
6. Curves — 精细调整
```

### 8.2 节点分离原则

| 调整类型 | 建议节点数 | 说明 |
|----------|-----------|------|
| 一级校正 | 1 个 | Lift/Gamma/Gain |
| 二级校正 | 1 个 | 局部色彩 |
| 风格化 | 1 个 | Hue/Saturation/Curves |
| 最终输出 | 1 个 | 范围限制 |

**避免在单个节点堆叠所有调整**,难以调试和修改。

### 8.3 色彩空间注意

```python
# 在线性空间进行调色
color_node.property("colorspace").setValue("linear", 0)

# 如果输入是 Log,先转换到线性
# 输出时再转回 Log
```

### 8.4 关键帧策略

```python
# 调色关键帧应该平滑过渡
# 使用贝塞尔插值而非线性
def set_smooth_keyframes(prop, keyframes):
    """添加平滑关键帧"""
    for frame, value in keyframes:
        prop.setValue(value, frame)
    # 设置插值类型(如果 API 支持)
    # prop.setInterpolation("bezier")
```

### 8.5 调试技巧

```python
def debug_color_node(color_node):
    """调试 Color 节点"""
    print(f"=== {color_node.label} ===")
    for name in ["lift", "gamma", "gain", "offset", "contrast",
                 "hue", "saturation", "vibrance", "mixAmount"]:
        prop = color_node.property(name)
        if prop:
            val = prop.value
            print(f"  {name}: {val}")

def bypass_color(color_node):
    """临时绕过调色(mixAmount 设为 0)"""
    mix_prop = color_node.property("mixAmount")
    if mix_prop:
        original = mix_prop.value
        mix_prop.setValue(0.0, 0)
        return original
    return None

def restore_color(color_node, original_mix):
    """恢复调色"""
    mix_prop = color_node.property("mixAmount")
    if mix_prop and original_mix is not None:
        mix_prop.setValue(original_mix, 0)
```

---

## 附录:调色参数速查表

| 参数 | 影响范围 | 正值效果 | 负值效果 |
|------|----------|----------|----------|
| lift | 阴影 | 提亮 | 压暗 |
| gamma | 中间调 | 提亮 | 压暗 |
| gain | 高光 | 提亮 | 压暗 |
| offset | 全部 | 偏移 | 偏移 |
| contrast | 对比度 | 增强 | 降低 |
| hue | 色相 | 旋转 | 反向旋转 |
| saturation | 饱和度 | 增加 | 降低 |
| vibrance | 自然饱和度 | 增加 | 降低 |

> **提示**:调色时建议开启 Scopes(波形图、矢量示波器),基于数据而非主观感受进行调整。
