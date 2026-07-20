# Silhouette 合成节点与混合模式

> 分类: 节点与合成系统
> 更新日期: 2026-07-11
> 概述: CompositeNode 参数详解、混合模式列表、Alpha 处理、溢色控制完整说明。

## 目录
1. [Composite 节点概述](#1-composite-节点概述)
2. [节点参数详解](#2-节点参数详解)
3. [混合模式列表](#3-混合模式列表)
4. [Alpha 处理](#4-alpha-处理)
5. [溢色控制](#5-溢色控制)
6. [高级合成技术](#6-高级合成技术)
7. [脚本化合成](#7-脚本化合成)
8. [最佳实践](#8-最佳实践)

---

## 1. Composite 节点概述

Composite 节点是 Silhouette 中最核心的合成节点,负责将多个图层按照指定模式进行混合。

### 1.1 节点结构

```
inputs[0] — Background(背景层)
inputs[1] — Foreground(前景层)
inputs[2] — Matte(遮罩层,可选)
inputs[3+] — 额前景层(可选)
         ↓
    [Composite Node]
         ↓
outputs[0] — 合成结果
```

### 1.2 核心能力

| 能力 | 说明 |
|------|------|
| 多层混合 | 支持最多 8 个输入层 |
| 遮罩控制 | 通过 matte 输入限制作用范围 |
| 混合模式 | 20+ 种混合算法 |
| 关键帧动画 | opacity 等参数可关键帧 |
| 色彩管理 | 支持 premultiply/postmultiply |

## 2. 节点参数详解

### 2.1 参数列表

| 参数名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `operation` | menu | "over" | 混合模式 |
| `opacity` | float | 1.0 | 不透明度(0-1) |
| `invertMatte` | bool | false | 反转遮罩 |
| `premultiply` | bool | true | 预乘 Alpha |
| `postmultiply` | bool | false | 后乘 Alpha |
| `matteChannel` | menu | "alpha" | 遮罩通道选择 |
| `mixWith` | menu | "bg" | 混合参照 |
| `extrapolate` | bool | false | 超出范围外推 |

### 2.2 参数说明

#### operation(混合模式)

```python
# 获取所有可选模式
op_prop = comp.property("operation")
# 常见值:"over", "under", "add", "screen", "multiply",
#         "subtract", "difference", "overlay", "soft_light",
#         "hard_light", "color_dodge", "color_burn", etc.
```

#### opacity(不透明度)

```python
# 设置不透明度
comp.property("opacity").setValue(0.8, 0)  # 80%

# 关键帧动画
comp.property("opacity").setValue(0.0, 1)   # 第1帧:0%
comp.property("opacity").setValue(1.0, 30)  # 第30帧:100%
comp.property("opacity").setValue(0.5, 60)  # 第60帧:50%
```

#### invertMatte(反转遮罩)

```python
# 反转遮罩,使遮罩外区域生效
comp.property("invertMatte").setValue(True, 0)
```

### 2.3 完整配置示例

```python
def configure_composite(comp, operation="over", opacity=1.0,
                        invert_matte=False, premultiply=True,
                        matte_channel="alpha"):
    """完整配置 Composite 节点"""
    props = {
        "operation": operation,
        "opacity": opacity,
        "invertMatte": invert_matte,
        "premultiply": premultiply,
        "matteChannel": matte_channel,
    }
    for name, value in props.items():
        prop = comp.property(name)
        if prop:
            prop.setValue(value, 0)
    return comp
```

## 3. 混合模式列表

### 3.1 基础混合模式

| 模式 | 公式(简化) | 适用场景 |
|------|------------|----------|
| `over` | fg + bg × (1 - α_fg) | 标准前景叠加 |
| `under` | bg + fg × (1 - α_bg) | 前景置于背景下 |
| `add` | fg + bg | 光效、粒子 |
| `subtract` | bg - fg | 减法效果 |
| `difference` | | bg - fg | 视觉差异 |
| `multiply` | fg × bg | 阴影、暗化 |
| `screen` | 1 - (1-fg) × (1-bg) | 高光、发光 |
| `replace` | fg | 完全替换 |

### 3.2 高级混合模式

| 模式 | 说明 |
|------|------|
| `overlay` | multiply 与 screen 的组合 |
| `soft_light` | 柔光效果 |
| `hard_light` | 强光效果 |
| `color_dodge` | 颜色减淡 |
| `color_burn` | 颜色加深 |
| `linear_dodge` | 线性减淡(加法) |
| `linear_burn` | 线性加深 |
| `vivid_light` | 鲜艳光 |
| `linear_light` | 线性光 |
| `pin_light` | 点光 |
| `hard_mix` | 硬混合 |

### 3.3 色彩混合模式

| 模式 | 保留属性 | 替换属性 |
|------|----------|----------|
| `hue` | bg 亮度、饱和度 | fg 色相 |
| `saturation` | bg 亮度、色相 | fg 饱和度 |
| `color` | bg 亮度 | fg 色相、饱和度 |
| `luminosity` | bg 色相、饱和度 | fg 亮度 |

### 3.4 模式选择指南

```
需要叠加光效?
├─ 是 → add / screen / linear_dodge
│   └─ 需要强光? → hard_light / vivid_light
└─ 否
    ├─ 需要暗化? → multiply / color_burn
    ├─ 需要差异? → difference / subtract
    ├─ 需要色彩调整? → color / hue / saturation
    └─ 标准叠加 → over
```

## 4. Alpha 处理

### 4.1 Premultiplied Alpha

**预乘 Alpha** 指颜色值已经乘以 Alpha 值:

```
预乘:C_premul = C × α
未预乘:C_straight = C(原始颜色)
```

Silhouette 默认使用预乘 Alpha。

### 4.2 premultiply 参数

```python
# 当输入素材是 straight alpha(未预乘)时,启用 premultiply
comp.property("premultiply").setValue(True, 0)

# 当输入已经是预乘的,关闭以避免双重预乘
comp.property("premultiply").setValue(False, 0)
```

### 4.3 postmultiply 参数

```python
# 输出时后乘 Alpha(某些下游软件需要)
comp.property("postmultiply").setValue(True, 0)
```

### 4.4 Alpha 通道处理策略

| 输入类型 | premultiply | postmultiply | 说明 |
|----------|-------------|--------------|------|
| 3D 渲染(预乘) | False | False | 已预乘,直接使用 |
| 3D 渲染(straight) | True | False | 需要预乘 |
| 视频素材(无 Alpha) | False | False | 无需处理 |
| Roto 输出 | False | True | 输出预乘结果 |

### 4.5 Alpha 溢出处理

```python
# 当 Alpha 边缘出现颜色溢出时
def fix_alpha_fringe(comp):
    """修复 Alpha 边缘溢色"""
    # 方法1:使用 premultiply
    comp.property("premultiply").setValue(True, 0)
    
    # 方法2:降低前景饱和度(概念性)
    # 需要在前景节点上调整
    
    # 方法3:使用 matte 通道清理
    comp.property("matteChannel").setValue("alpha", 0)
```

## 5. 溢色控制

### 5.1 溢色问题

溢色(Spill)通常出现在绿幕/蓝幕抠像后,边缘残留绿色/蓝色。

### 5.2 溢色抑制参数

虽然 Composite 节点本身不直接提供溢色抑制,但可通过以下方式配合:

```python
def setup_spill_suppression(session, fg_node):
    """设置溢色抑制"""
    # 方法1:使用 Color 节点降低特定通道
    color = Node("Color")
    color.label = "Spill_Suppression"
    session.addNode(color)
    color.inputs[0].connect(fg_node.outputs[0])
    
    # 降低绿色通道(针对绿幕)
    gain_prop = color.property("gain")
    if gain_prop:
        # 降低 G 通道
        gain_prop.setValue((1.0, 0.85, 1.0, 1.0), 0)
    
    # 方法2:使用 Matte 节点限制边缘
    matte = Node("Matte")
    matte.label = "Edge_Matte"
    session.addNode(matte)
    
    return color, matte
```

### 5.3 边缘处理

```python
def configure_edge_blur(comp, blur_amount=1.0):
    """配置合成边缘模糊"""
    # 通过在 matte 输入前添加模糊实现
    # (需要在 matte 节点和 comp 之间插入 Filter 节点)
    pass

def configure_edge_grow(comp, grow_amount=1):
    """配置遮罩边缘扩展"""
    matte_prop = comp.property("matteGrow")
    if matte_prop:
        matte_prop.setValue(grow_amount, 0)
```

## 6. 高级合成技术

### 6.1 多层合成

```python
def multilayer_composite(session, layers):
    """
    多层合成
    layers: [(node, mode, opacity, matte_node?), ...]
    """
    if not layers:
        return None
    
    result = layers[0][0]
    
    for i, (node, mode, opacity, *rest) in enumerate(layers[1:], 1):
        comp = Node("Composite")
        comp.label = f"CMP_Layer_{i:02d}"
        session.addNode(comp)
        
        # 背景 = 之前的结果
        comp.inputs[0].connect(result.outputs[0])
        # 前景 = 当前层
        comp.inputs[1].connect(node.outputs[0])
        # 遮罩(可选)
        if rest and rest[0]:
            if len(comp.inputs) > 2:
                comp.inputs[2].connect(rest[0].outputs[0])
        
        configure_composite(comp, operation=mode, opacity=opacity)
        result = comp
    
    return result
```

### 6.2 遮罩限制合成

```python
def masked_composite(session, bg, fg, matte_node, invert=False):
    """使用遮罩限制合成范围"""
    comp = Node("Composite")
    comp.label = "CMP_Masked"
    session.addNode(comp)
    
    comp.inputs[0].connect(bg.outputs[0])
    comp.inputs[1].connect(fg.outputs[0])
    comp.inputs[2].connect(matte_node.outputs[0])
    
    configure_composite(comp, operation="over", opacity=1.0,
                      invert_matte=invert)
    return comp
```

### 6.3 混合模式链式应用

```python
def blend_mode_chain(session, bg, fg_layers):
    """
    对同一背景应用多个不同混合模式的前景
    fg_layers: [(node, mode), ...]
    """
    result = bg
    for fg, mode in fg_layers:
        comp = Node("Composite")
        comp.label = f"CMP_{mode}"
        session.addNode(comp)
        comp.inputs[0].connect(result.outputs[0])
        comp.inputs[1].connect(fg.outputs[0])
        configure_composite(comp, operation=mode, opacity=1.0)
        result = comp
    return result
```

## 7. 脚本化合成

### 7.1 创建完整合成

```python
from fx import *

def create_full_composite(session, bg_source, fg_source, matte_source=None):
    """创建完整的合成设置"""
    # 创建节点
    comp = Node("Composite")
    comp.label = "CMP_Main"
    session.addNode(comp)
    
    output = Node("Output")
    output.label = "OUT_Final"
    session.addNode(output)
    
    # 连接
    comp.inputs[0].connect(bg_source.outputs[0])
    comp.inputs[1].connect(fg_source.outputs[0])
    if matte_source and len(comp.inputs) > 2:
        comp.inputs[2].connect(matte_source.outputs[0])
    
    output.inputs[0].connect(comp.outputs[0])
    
    # 配置
    configure_composite(comp, operation="over", opacity=1.0,
                      premultiply=True, matte_channel="alpha")
    
    return comp, output
```

### 7.2 关键帧动画

```python
def animate_opacity(comp, keyframes):
    """
    为 opacity 添加关键帧
    keyframes: [(frame, value), ...]
    """
    prop = comp.property("opacity")
    if not prop:
        return False
    for frame, value in keyframes:
        prop.setValue(value, frame)
    return True

def fade_in(comp, start_frame, duration=30):
    """淡入效果"""
    animate_opacity(comp, [
        (start_frame, 0.0),
        (start_frame + duration, 1.0)
    ])

def fade_out(comp, start_frame, duration=30):
    """淡出效果"""
    animate_opacity(comp, [
        (start_frame, 1.0),
        (start_frame + duration, 0.0)
    ])

def fade_in_out(comp, in_start, in_dur, hold, out_dur):
    """淡入-保持-淡出"""
    animate_opacity(comp, [
        (in_start, 0.0),
        (in_start + in_dur, 1.0),
        (in_start + in_dur + hold, 1.0),
        (in_start + in_dur + hold + out_dur, 0.0)
    ])
```

### 7.3 批量合成

```python
def batch_composite_with_matte(session, bg, fg_list, matte_list):
    """
    批量为多个前景+遮罩创建合成
    """
    results = []
    for i, (fg, matte) in enumerate(zip(fg_list, matte_list)):
        comp = Node("Composite")
        comp.label = f"CMP_Batch_{i:02d}"
        session.addNode(comp)
        
        comp.inputs[0].connect(bg.outputs[0])
        comp.inputs[1].connect(fg.outputs[0])
        if len(comp.inputs) > 2:
            comp.inputs[2].connect(matte.outputs[0])
        
        configure_composite(comp, operation="over")
        results.append(comp)
    
    return results
```

## 8. 最佳实践

### 8.1 混合模式选择

| 场景 | 推荐模式 | 原因 |
|------|----------|------|
| 角色叠加 | over | 自然的前景叠加 |
| 光效、激光 | add | 累加亮度 |
| 烟雾、雾气 | screen | 亮度叠加但不过曝 |
| 阴影 | multiply | 暗化背景 |
| 玻璃反射 | overlay | 保持对比度 |
| 色彩调整 | color | 替换色调 |

### 8.2 Alpha 处理原则

1. **了解素材类型**:3D 渲染通常预乘,视频通常 straight
2. **避免双重预乘**:已预乘素材不要再 premultiply
3. **输出统一**:整个项目统一输出预乘或 straight
4. **检查边缘**:缩放查看 Alpha 边缘是否有黑边/白边

### 8.3 性能优化

```python
# 避免过多 Composite 串联
# 错误:5个前景各用一个 Composite 串联
# A → CMP1 → CMP2 → CMP3 → CMP4 → CMP5

# 正确:使用一个多输入 Composite
# A → CMP(输入0-5) → 输出
```

### 8.4 调试技巧

```python
def debug_composite(comp):
    """调试 Composite 节点"""
    print(f"=== {comp.label} ===")
    print(f"  operation: {comp.property('operation').value}")
    print(f"  opacity: {comp.property('opacity').value}")
    print(f"  premultiply: {comp.property('premultiply').value}")
    print(f"  invertMatte: {comp.property('invertMatte').value}")
    
    for i, p in enumerate(comp.inputs):
        src = p.source.label if p.source else "未连接"
        print(f"  inputs[{i}]: {src}")

def temp_bypass_composite(comp):
    """临时绕过合成(直接输出背景)"""
    # 保存原连接
    original_fg = comp.inputs[1].source if len(comp.inputs) > 1 else None
    original_matte = comp.inputs[2].source if len(comp.inputs) > 2 else None
    
    # 断开前景和遮罩
    if original_fg:
        comp.inputs[1].disconnect()
    if original_matte:
        comp.inputs[2].disconnect()
    
    return original_fg, original_matte

def restore_composite(comp, fg, matte):
    """恢复合成连接"""
    if fg:
        comp.inputs[1].connect(fg.outputs[0])
    if matte:
        comp.inputs[2].connect(matte.outputs[0])
```

---

## 附录:混合模式速查表

| 模式 | 典型用途 | 亮度变化 |
|------|----------|----------|
| over | 标准叠加 | 不变 |
| under | 前景置底 | 不变 |
| add | 发光、粒子 | 变亮 |
| screen | 高光、雾 | 变亮 |
| multiply | 阴影、暗化 | 变暗 |
| overlay | 强对比混合 | 对比增强 |
| soft_light | 柔和光效 | 轻微变化 |
| difference | 差异检测 | 取决于差值 |
| color | 色调替换 | 保持亮度 |

> **提示**:合成复杂场景时,先用 `over` 模式搭好结构,再逐层调整混合模式,可快速看到效果。
