# Silhouette 多通道输出与EXR工作流

> 分类: 节点与合成系统
> 更新日期: 2026-07-11
> 概述: EXR 多通道输出、通道命名规范、RGBA/深度/运动矢量通道管理及与 AE 集成工作流。

## 目录
1. [EXR 格式概述](#1-exr-格式概述)
2. [多通道架构](#2-多通道架构)
3. [通道命名规范](#3-通道命名规范)
4. [通道类型详解](#4-通道类型详解)
5. [多通道输出配置](#5-多通道输出配置)
6. [AE 集成工作流](#6-ae-集成工作流)
7. [脚本化多通道输出](#7-脚本化多通道输出)
8. [最佳实践](#8-最佳实践)

---

## 1. EXR 格式概述

### 1.1 为什么使用 EXR

OpenEXR 是影视后期行业标准的多通道图像格式,具备以下优势:

| 特性 | 说明 |
|------|------|
| 高动态范围 | 16位/32位浮点,支持 HDR |
| 多通道 | 单文件存储任意数量的通道 |
| 无损压缩 | 支持 PIZ、ZIP、ZIPS 等 |
| 元数据 | 支持 ARRI、ACES 等元数据标准 |
| 广泛支持 | AE、Nuke、Premiere、Resolve 等均支持 |

### 1.2 Silhouette 与 EXR

Silhouette 原生支持 EXR 读写,可用于:
- 输入多通道素材(如 3D 渲染的 beauty + matte + depth)
- 输出多通道结果(RGBA + matte + tracking data)
- 与 AE/Nuke 进行多通道数据交换

## 2. 多通道架构

### 2.1 通道层级

EXR 通道采用**层级命名**结构:

```
通道组(Layer).通道(Component)
```

例如:
- `rgba.R` / `rgba.G` / `rgba.B` / `rgba.A` — 主 RGBA
- `matte.R` / `matte.G` / `matte.B` / `matte.A` — 遮罩通道
- `depth.Z` — 深度通道
- `motion.UV` — 运动矢量

### 2.2 Silhouette 输出通道

| 通道组 | 通道 | 说明 |
|--------|------|------|
| rgba | R, G, B, A | 主图像 |
| matte | R, G, B, A | 遮罩(灰度) |
| depth | Z | 深度信息 |
| motion | U, V | 运动矢量 |
| forward | U, V | 前向运动矢量 |
| backward | U, V | 后向运动矢量 |
| custom | * | 自定义命名的通道 |

## 3. 通道命名规范

### 3.1 标准命名

遵循 EXR 行业标准命名约定:

```
<layer_name>.<channel_name>
```

### 3.2 常见通道命名

| 用途 | 命名 | 示例 |
|------|------|------|
| 主图像 | `rgba.RGBA` | `rgba.R`, `rgba.G`, `rgba.B`, `rgba.A` |
| Roto 遮罩 | `matte.RGBA` | `matte.R`, `matte.A` |
| 深度 | `depth.Z` | `depth.Z` |
| 运动矢量 | `motion.UV` | `motion.U`, `motion.V` |
| 对象遮罩 | `<object>_matte.RGBA` | `character_matte.A` |
| 加速通道 | `crypto.*` | `crypto00.R`, `crypto01.R` |

### 3.3 自定义通道命名

```python
def define_custom_channel(name, components):
    """
    定义自定义通道
    name: 通道组名(如 "effect_matte")
    components: ["R", "G", "B", "A"] 或 ["Z"]
    """
    return [f"{name}.{c}" for c in components]

# 示例
hair_matte = define_custom_channel("hair_matte", ["R", "G", "B", "A"])
face_matte = define_custom_channel("face_matte", ["R", "G", "B", "A"])
```

## 4. 通道类型详解

### 4.1 RGBA 通道

标准 RGBA 通道,存储最终的合成图像。

```python
def configure_rgba_output(output_node, premultiply=True):
    """配置 RGBA 输出"""
    output_node.property("channels").setValue("rgba", 0)
    output_node.property("premultiply").setValue(premultiply, 0)
```

### 4.2 深度通道

深度通道存储每个像素到摄像机的距离,常用于景深、雾化等后期效果。

```python
def output_depth_channel(output_node):
    """配置深度通道输出"""
    # Silhouette 不原生生成深度,但可传递 3D 渲染的深度通道
    output_node.property("extraChannels").setValue("depth.Z", 0)
```

### 4.3 运动矢量

运动矢量(Motion Vectors)用于运动模糊、帧插值等。

| 方向 | 通道 | 说明 |
|------|------|------|
| 前向 | `forward.U`, `forward.V` | 当前帧到下一帧 |
| 后向 | `backward.U`, `backward.V` | 当前帧到上一帧 |

```python
def configure_motion_output(output_node, direction="both"):
    """配置运动矢量输出"""
    channels = []
    if direction in ("forward", "both"):
        channels.extend(["forward.U", "forward.V"])
    if direction in ("backward", "both"):
        channels.extend(["backward.U", "backward.V"])
    output_node.property("extraChannels").setValue(channels, 0)
```

### 4.4 自定义遮罩通道

```python
def add_custom_matte_channel(output_node, matte_name):
    """添加自定义遮罩通道"""
    channel_name = f"{matte_name}.RGBA"
    existing = output_node.property("extraChannels").value or []
    if channel_name not in existing:
        existing.append(channel_name)
        output_node.property("extraChannels").setValue(existing, 0)
```

## 5. 多通道输出配置

### 5.1 Output 节点配置

```python
from fx import *

def setup_multi_channel_output(session, comp_node, channels_config):
    """
    配置多通道 EXR 输出
    channels_config: {
        "primary": "rgba",
        "matte": "character_matte",
        "depth": "depth",
        "motion": "forward"
    }
    """
    output = Node("Output")
    output.label = "OUT_EXR_Multi"
    session.addNode(output)
    output.inputs[0].connect(comp_node.outputs[0])
    
    # 设置输出格式为 EXR
    output.property("format").setValue("exr", 0)
    
    # 配置压缩
    output.property("compression").setValue("piz", 0)
    
    # 配置主通道
    primary = channels_config.get("primary", "rgba")
    output.property("channels").setValue(primary, 0)
    
    # 配置额外通道
    extra_channels = []
    if "matte" in channels_config:
        matte_name = channels_config["matte"]
        extra_channels.extend([f"{matte_name}.R", f"{matte_name}.G",
                               f"{matte_name}.B", f"{matte_name}.A"])
    if "depth" in channels_config:
        extra_channels.append("depth.Z")
    if "motion" in channels_config:
        motion = channels_config["motion"]
        if motion in ("forward", "both"):
            extra_channels.extend(["forward.U", "forward.V"])
        if motion in ("backward", "both"):
            extra_channels.extend(["backward.U", "backward.V"])
    
    if extra_channels:
        output.property("extraChannels").setValue(extra_channels, 0)
    
    return output
```

### 5.2 压缩方式对比

| 压缩方式 | 压缩率 | 速度 | 适用场景 |
|----------|--------|------|----------|
| `none` | 1:1 | 最快 | 临时预览 |
| `rle` | 低 | 快 | 简单图像 |
| `zips` | 中 | 中 | 单行压缩 |
| `zip` | 中 | 中 | 块压缩 |
| `piz` | 高 | 慢 | 影视最终输出 |
| `pxr24` | 中 | 中 | Pixar 24位 |
| `b44` | 中 | 快 | 16位预览 |
| `b44a` | 中 | 快 | B44 改进 |

推荐:
- **预览/中间文件**:`zip` 或 `zips`
- **最终交付**:`piz`
- **快速存档**:`b44`

### 5.3 色彩空间配置

```python
def configure_colorspace(output_node, colorspace="aces2065-1"):
    """配置色彩空间元数据"""
    # 设置色彩空间
    output_node.property("colorspace").setValue(colorspace, 0)
    
    # 常见色彩空间:
    # aces2065-1 — ACES AP0
    # acescg — ACES AP1
    # linear — 线性
    # srgb — sRGB
    # rec709 — Rec.709
    # arri_logc — ARRI LogC
    # slog3 — Sony S-Log3
```

## 6. AE 集成工作流

### 6.1 多通道 EXR 在 AE 中的使用

After Effects 通过 `EXtractoR` 效果或 `OpenEXR` 插件读取多通道 EXR。

### 6.2 通道映射表

| Silhouette 输出 | AE EXtractoR 通道 |
|----------------|-------------------|
| `rgba.RGBA` | 主图层 RGB+Alpha |
| `matte.A` | EXtractoR 提取为遮罩 |
| `depth.Z` | EXtractoR 提取用于景深 |
| `motion.UV` | 提取用于运动模糊 |

### 6.3 输出适合 AE 的 EXR

```python
def output_for_ae(session, comp_node, matte_node=None, depth_passthrough=None):
    """配置适合 AE 工作流的 EXR 输出"""
    output = Node("Output")
    output.label = "OUT_AE_EXR"
    session.addNode(output)
    output.inputs[0].connect(comp_node.outputs[0])
    
    # 基础配置
    output.property("format").setValue("exr", 0)
    output.property("compression").setValue("zip", 0)  # AE 偏好 zip
    output.property("colorspace").setValue("linear", 0)
    output.property("premultiply").setValue(True, 0)
    
    # 额外通道
    extra = []
    if matte_node:
        # 添加遮罩通道
        extra.extend(["matte.R", "matte.G", "matte.B", "matte.A"])
    
    if depth_passthrough:
        extra.append("depth.Z")
    
    if extra:
        output.property("extraChannels").setValue(extra, 0)
    
    # 命名规范:便于 AE 脚本识别
    output.property("outputName").setValue(
        "[project]_[shot]_[version]_v[####].exr", 0
    )
    
    return output
```

### 6.4 AE 导入设置

在 AE 中导入多通道 EXR 时的设置:

1. **Import As**:Footage
2. **Color Space**:与 Silhouette 输出一致
3. **Color Management**:启用,选择 Working Space
4. **EXtractoR**:对额外通道使用 EXtractoR 效果提取

```
AE 中的操作流程:
1. File → Import → 选择 EXR 序列
2. 拖入合成
3. 对需要提取的通道添加 Effect → 3D Channel → EXtractoR
4. 在 EXtractoR 中选择通道(如 matte.A)
5. 将提取结果用于遮罩或效果
```

## 7. 脚本化多通道输出

### 7.1 批量通道输出

```python
def batch_channel_output(session, comp_node, matte_nodes):
    """
    批量输出多个遮罩通道
    matte_nodes: {"character": node, "hair": node, "background": node}
    """
    output = Node("Output")
    output.label = "OUT_MultiMatte"
    session.addNode(output)
    output.inputs[0].connect(comp_node.outputs[0])
    
    output.property("format").setValue("exr", 0)
    output.property("compression").setValue("piz", 0)
    
    # 添加所有遮罩通道
    extra = []
    for name, node in matte_nodes.items():
        # 每个对象一个独立的通道组
        extra.extend([
            f"{name}_matte.R",
            f"{name}_matte.G",
            f"{name}_matte.B",
            f"{name}_matte.A"
        ])
    
    output.property("extraChannels").setValue(extra, 0)
    return output
```

### 7.2 通道分离输出

```python
def split_channel_output(session, source, channels):
    """
    将多通道输入拆分为单独的输出文件
    channels: ["matte", "depth", "forward"]
    """
    outputs = []
    for ch in channels:
        out = Node("Output")
        out.label = f"OUT_{ch}"
        session.addNode(out)
        out.inputs[0].connect(source.outputs[0])
        
        out.property("format").setValue("exr", 0)
        out.property("channels").setValue(ch, 0)
        out.property("outputName").setValue(
            f"[project]_{ch}_v[####].exr", 0
        )
        outputs.append(out)
    
    return outputs
```

### 7.3 ID 通道输出

```python
def output_id_matte(session, comp_node, id_objects):
    """
    输出 ID Matte(每个对象一个唯一颜色)
    id_objects: {"obj1": (1,0,0,1), "obj2": (0,1,0,1), ...}
    """
    # 创建 ID Matte 节点(概念性)
    id_node = Node("Matte")
    id_node.label = "ID_Matte"
    session.addNode(id_node)
    id_node.inputs[0].connect(comp_node.outputs[0])
    
    # 为每个对象分配 ID 通道
    extra = []
    for obj_name in id_objects:
        extra.extend([
            f"id_{obj_name}.R",
            f"id_{obj_name}.G",
            f"id_{obj_name}.B",
            f"id_{obj_name}.A"
        ])
    
    output = Node("Output")
    output.label = "OUT_ID_Matte"
    session.addNode(output)
    output.inputs[0].connect(id_node.outputs[0])
    output.property("format").setValue("exr", 0)
    output.property("extraChannels").setValue(extra, 0)
    
    return output
```

## 8. 最佳实践

### 8.1 通道命名最佳实践

1. **使用小写+下划线**:`character_matte` 而非 `CharacterMatte`
2. **语义化命名**:`hair_matte` 而非 `matte01`
3. **保持一致性**:整个项目使用相同命名规则
4. **避免特殊字符**:不使用空格、中文、特殊符号

### 8.2 性能优化

| 优化项 | 建议 |
|--------|------|
| 通道数量 | 不超过 32 个通道,否则文件过大 |
| 压缩选择 | 最终输出用 PIZ,中间用 ZIP |
| 比特深度 | 一般 16 位足够,32 位仅用于极端 HDR |
| 分辨率 | 4K 以上慎用 32 位 + PIZ |

### 8.3 错误排查

```python
def verify_exr_output(output_node):
    """验证 EXR 输出配置"""
    issues = []
    
    fmt = output_node.property("format").value
    if fmt != "exr":
        issues.append("输出格式不是 EXR")
    
    comp = output_node.property("compression").value
    if comp not in ("none", "rle", "zips", "zip", "piz", "pxr24", "b44", "b44a"):
        issues.append(f"未知压缩方式: {comp}")
    
    channels = output_node.property("extraChannels").value or []
    if len(channels) > 32:
        issues.append(f"通道数过多({len(channels)}),可能影响性能")
    
    return issues
```

### 8.4 与其他软件的通道对应

| Silhouette | Nuke | AE |
|------------|------|-----|
| `rgba.RGBA` | rgba | 主图层 |
| `matte.A` | matte.alpha | EXtractoR 提取 |
| `depth.Z` | depth.Z | EXtractoR → 景深 |
| `forward.UV` | motion.forward | CC Force Motion Blur |
| `backward.UV` | motion.backward | CC Force Motion Blur |
| `custom.X` | custom.X | EXtractoR |

---

## 附录:完整工作流示例

```
[3D 渲染输出]
   ↓ (多通道 EXR: rgba + depth + motion)
[Silhouette 输入]
   ↓
[Roto 节点] — 生成 character_matte
   ↓
[Paint 节点] — 修复瑕疵
   ↓
[Composite] — 合成
   ↓
[Output: EXR]
   ├─ rgba.RGBA (主图像)
   ├─ character_matte.RGBA (Roto 遮罩)
   ├─ depth.Z (透传 3D 深度)
   └─ motion.UV (透传运动矢量)
   ↓
[AE 导入]
   ├─ 主图层用于显示
   ├─ EXtractoR 提取 character_matte 用于二次遮罩
   ├─ EXtractoR 提取 depth 用于景深模糊
   └─ EXtractoR 提取 motion 用于像素运动模糊
```

> **提示**:与下游软件约定通道命名时,务必在项目启动阶段统一,避免后期改名造成脚本失效。
