# Silhouette 导出格式参考手册

> 分类: 集成与导出
> 更新日期: 2026-07-11
> 概述: 所有支持格式详解、压缩方式、元数据、色彩空间完整说明。

## 目录
1. [格式概述](#1-格式概述)
2. [图像格式](#2-图像格式)
3. [视频格式](#3-视频格式)
4. [数据格式](#4-数据格式)
5. [压缩方式](#5-压缩方式)
6. [元数据](#6-元数据)
7. [色彩空间](#7-色彩空间)
8. [最佳实践](#8-最佳实践)

---

## 1. 格式概述

### 1.1 格式分类

| 大类 | 格式 | 用途 |
|------|------|------|
| 图像序列 | EXR, TIFF, PNG, DPX, TGA | 逐帧存储 |
| 视频 | MOV, MP4, AVI, WebM | 连续视频 |
| 数据 | JSON, XML, TXT, CSV | 跟踪/元数据 |
| 项目 | SFX, JSX, NK | 软件特定 |

### 1.2 格式选择决策树

```
需要无损质量?
├─ 是 → EXR(PIZ) 或 TIFF
│   └─ 需要 HDR? → EXR(16/32bit)
└─ 否
    ├─ 需要视频? → MOV(ProRes) 或 MP4(H.264)
    ├─ 需要预览? → PNG 或 JPEG
    └─ 需要数据? → JSON 或 XML
```

## 2. 图像格式

### 2.1 OpenEXR (.exr)

**影视后期行业标准格式**

| 特性 | 说明 |
|------|------|
| 位深 | 16bit half, 32bit float |
| 通道 | 任意多通道 |
| 压缩 | PIZ, ZIP, ZIPS, RLE, B44 等 |
| HDR | 支持 |
| Alpha | 支持 |
| 元数据 | 丰富 |

```python
def configure_exr_output(output_node, bit_depth=16, compression="piz",
                          colorspace="acescg"):
    """配置 EXR 输出"""
    output_node.property("format").setValue("exr", 0)
    output_node.property("bitDepth").setValue(bit_depth, 0)
    output_node.property("compression").setValue(compression, 0)
    output_node.property("colorspace").setValue(colorspace, 0)
```

**适用场景**:
- 最终交付
- 多通道输出
- HDR 内容
- 与 Nuke/AE 交换

### 2.2 TIFF (.tif/.tiff)

**灵活的无损格式**

| 特性 | 说明 |
|------|------|
| 位深 | 8, 16, 32 bit |
| 通道 | RGBA |
| 压缩 | LZW, ZIP, 无 |
| HDR | 有限支持 |
| Alpha | 支持 |

```python
def configure_tiff_output(output_node, bit_depth=16, compression="lzw"):
    """配置 TIFF 输出"""
    output_node.property("format").setValue("tiff", 0)
    output_node.property("bitDepth").setValue(bit_depth, 0)
    output_node.property("compression").setValue(compression, 0)
```

**适用场景**:
- 中间文件
- 平面设计
- 印刷

### 2.3 PNG (.png)

**Web 友好的无损格式**

| 特性 | 说明 |
|------|------|
| 位深 | 8, 16 bit |
| 通道 | RGBA |
| 压缩 | 无损 ZIP |
| HDR | 不支持 |
| Alpha | 支持 |

```python
def configure_png_output(output_node, bit_depth=8):
    """配置 PNG 输出"""
    output_node.property("format").setValue("png", 0)
    output_node.property("bitDepth").setValue(bit_depth, 0)
```

**适用场景**:
- 预览
- Web 内容
- 简单遮罩

### 2.4 DPX (.dpx)

**影视行业标准**

| 特性 | 说明 |
|------|------|
| 位深 | 8, 10, 12, 16 bit |
| 通道 | RGB, RGBA |
| 压缩 | 通常无压缩 |
| HDR | 有限 |
| Alpha | 支持 |

```python
def configure_dpx_output(output_node, bit_depth=10):
    """配置 DPX 输出"""
    output_node.property("format").setValue("dpx", 0)
    output_node.property("bitDepth").setValue(bit_depth, 0)
```

**适用场景**:
- 影院交付
- 调色工作流
- DI(数字中间片)

### 2.5 TGA (.tga)

**传统格式**

| 特性 | 说明 |
|------|------|
| 位深 | 8, 16 bit |
| 通道 | RGB, RGBA |
| 压缩 | RLE |
| HDR | 不支持 |
| Alpha | 支持 |

```python
def configure_tga_output(output_node):
    """配置 TGA 输出"""
    output_node.property("format").setValue("tga", 0)
```

**适用场景**:
- 传统系统
- 游戏开发
- 简单图形

### 2.6 图像格式对比

| 格式 | 位深 | 压缩 | Alpha | HDR | 文件大小 | 推荐用途 |
|------|------|------|-------|-----|----------|----------|
| EXR | 16/32 | PIZ/ZIP | ✓ | ✓ | 中 | 最终交付 |
| TIFF | 8/16/32 | LZW/ZIP | ✓ | 有限 | 中 | 中间文件 |
| PNG | 8/16 | ZIP | ✓ | ✗ | 小 | 预览/Web |
| DPX | 8/10/12/16 | 无 | ✓ | 有限 | 大 | 影视 |
| TGA | 8/16 | RLE | ✓ | ✗ | 小 | 传统 |

## 3. 视频格式

### 3.1 QuickTime (.mov)

| 编码器 | 质量 | 大小 | 用途 |
|--------|------|------|------|
| ProRes 422 HQ | 高 | 大 | 中间文件 |
| ProRes 4444 | 最高 | 最大 | 带 Alpha |
| ProRes 422 | 中 | 中 | 预览 |
| ProRes Proxy | 低 | 小 | 代理 |
| H.264 | 中 | 小 | 交付 |
| H.265 | 中 | 最小 | 交付 |

```python
def configure_mov_output(output_node, codec="prores_422_hq", quality=100):
    """配置 MOV 输出"""
    output_node.property("format").setValue("mov", 0)
    output_node.property("codec").setValue(codec, 0)
    output_node.property("quality").setValue(quality, 0)
```

### 3.2 MP4 (.mp4)

| 编码器 | 质量 | 大小 | 用途 |
|--------|------|------|------|
| H.264 | 中 | 小 | Web 交付 |
| H.265/HEVC | 中 | 最小 | 4K/8K 交付 |
| AV1 | 中 | 极小 | 未来标准 |

```python
def configure_mp4_output(output_node, codec="h264", quality=85):
    """配置 MP4 输出"""
    output_node.property("format").setValue("mp4", 0)
    output_node.property("codec").setValue(codec, 0)
    output_node.property("quality").setValue(quality, 0)
```

### 3.3 编码器选择

```
用途?
├─ 最终交付
│   ├─ Web → H.264/H.265
│   ├─ 影院 → ProRes 422 HQ
│   └─ 广播 → ProRes/DNxHR
├─ 中间文件
│   ├─ 带 Alpha → ProRes 4444
│   └─ 不带 Alpha → ProRes 422 HQ
└─ 代理
    └─ ProRes Proxy / H.264 低质量
```

### 3.4 质量设置

| 质量等级 | 码率(1080p) | 用途 |
|----------|-------------|------|
| 最高 | 50+ Mbps | 母版 |
| 高 | 20-50 Mbps | 交付 |
| 中 | 10-20 Mbps | 预览 |
| 低 | 5-10 Mbps | 代理 |
| 最低 | < 5 Mbps | Web 预览 |

## 4. 数据格式

### 4.1 JSON (.json)

```python
import json

def export_track_json(track_data, output_path):
    """导出跟踪数据为 JSON"""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(track_data, f, indent=2, ensure_ascii=False)
```

**优势**:
- 结构化
- 可读性好
- 跨平台
- 易于解析

### 4.2 XML (.xml)

```python
def export_xml(data, output_path):
    """导出为 XML"""
    import xml.etree.ElementTree as ET
    
    root = ET.Element("silhouette_data")
    
    for track in data["tracks"]:
        track_elem = ET.SubElement(root, "track")
        track_elem.set("name", track["name"])
        
        for frame in track["frames"]:
            frame_elem = ET.SubElement(track_elem, "frame")
            frame_elem.set("number", str(frame["frame"]))
            frame_elem.set("x", str(frame["x"]))
            frame_elem.set("y", str(frame["y"]))
    
    tree = ET.ElementTree(root)
    tree.write(output_path, encoding="utf-8", xml_declaration=True)
```

### 4.3 CSV (.csv)

```python
def export_csv(track_data, output_path):
    """导出为 CSV"""
    lines = ["frame,x,y,confidence"]
    
    for track in track_data["tracks"]:
        for frame in track["frames"]:
            lines.append(f'{frame["frame"]},{frame["x"]},{frame["y"]},'
                        f'{frame.get("confidence", 1.0)}')
    
    with open(output_path, "w") as f:
        f.write("\n".join(lines))
```

### 4.4 AE 关键帧格式 (.txt)

```python
def export_ae_keyframes(track_data, output_path):
    """导出 AE 关键帧格式"""
    # 详见"跟踪数据AE导入规范"
    pass
```

## 5. 压缩方式

### 5.1 EXR 压缩对比

| 压缩 | 压缩率 | 速度 | 质量 | 用途 |
|------|--------|------|------|------|
| none | 1:1 | 最快 | 无损 | 临时 |
| RLE | 2:1 | 快 | 无损 | 简单图像 |
| ZIPS | 2:1 | 中 | 无损 | 单行 |
| ZIP | 2:1 | 中 | 无损 | 块 |
| PIZ | 3:1 | 慢 | 无损 | 最终输出 |
| PXR24 | 2:1 | 中 | 有损(24bit) | Pixar |
| B44 | 4:1 | 快 | 有损(16bit) | 预览 |
| B44A | 4:1 | 快 | 有损 | 预览 |

### 5.2 压缩选择

```python
def select_compression(use_case):
    """根据用途选择压缩"""
    recommendations = {
        "final_delivery": "piz",      # 最终交付:最高压缩比
        "intermediate": "zip",         # 中间文件:平衡
        "preview": "b44",              # 预览:快速
        "archival": "piz",             # 归档:最高压缩
        "network_transfer": "piz",     # 网络传输:小文件
        "local_work": "zips"           # 本地工作:快速读取
    }
    return recommendations.get(use_case, "zip")
```

### 5.3 视频压缩

| 编码器 | 压缩方式 | 质量保留 | 速度 |
|--------|----------|----------|------|
| ProRes | 帧内 | 高 | 快 |
| DNxHR | 帧内 | 高 | 快 |
| H.264 | 帧间 | 中 | 中 |
| H.265 | 帧间 | 中 | 慢 |

## 6. 元数据

### 6.1 支持的元数据类型

| 类型 | 说明 | 示例 |
|------|------|------|
| 项目信息 | 项目名称、镜头号 | PROJ001_SH0100 |
| 色彩空间 | 色彩管理信息 | acescg |
| 时间码 | SMPTE 时间码 | 01:00:00:00 |
| 帧信息 | 帧率、帧范围 | 24fps, 1-100 |
| 艺术家 | 创建者信息 | Artist Name |
| 版本 | 版本号 | v01 |
| 自定义 | 用户定义字段 | 任意 |

### 6.2 设置元数据

```python
def set_metadata(output_node, metadata):
    """设置输出元数据"""
    # 项目信息
    if "project" in metadata:
        prop = output_node.property("meta_project")
        if prop:
            prop.setValue(metadata["project"], 0)
    
    # 色彩空间
    if "colorspace" in metadata:
        output_node.property("colorspace").setValue(metadata["colorspace"], 0)
    
    # 帧率
    if "frame_rate" in metadata:
        prop = output_node.property("meta_frame_rate")
        if prop:
            prop.setValue(metadata["frame_rate"], 0)
    
    # 艺术家
    if "artist" in metadata:
        prop = output_node.property("meta_artist")
        if prop:
            prop.setValue(metadata["artist"], 0)
    
    # 版本
    if "version" in metadata:
        prop = output_node.property("meta_version")
        if prop:
            prop.setValue(metadata["version"], 0)
```

### 6.3 EXR 元数据

EXR 支持丰富的元数据头:

```python
def set_exr_metadata(output_node, metadata_dict):
    """设置 EXR 特定元数据"""
    for key, value in metadata_dict.items():
        prop_name = f"exr_header_{key}"
        prop = output_node.property(prop_name)
        if prop:
            prop.setValue(value, 0)
```

常见的 EXR 头信息:
- `camera`: 摄像机信息
- `lens`: 镜头信息
- `scene`: 场景信息
- `take`: 拍摄条数
- `iso`: ISO 设置
- `shutter`: 快门速度
- `aperture`: 光圈

## 7. 色彩空间

### 7.1 支持的色彩空间

| 色彩空间 | 说明 | 用途 |
|----------|------|------|
| linear | 线性 | 通用 |
| srgb | sRGB | Web/显示器 |
| rec709 | Rec.709 | HDTV |
| rec2020 | Rec.2020 | UHDTV |
| aces2065-1 | ACES AP0 | ACES 交换 |
| acescg | ACES AP1 | ACES 工作 |
| arri_logc | ARRI LogC | ARRI 摄影机 |
| slog3 | Sony S-Log3 | Sony 摄影机 |
| red_log3g10 | RED Log3G10 | RED 摄影机 |
| dci_p3 | DCI-P3 | 影院 |

### 7.2 色彩空间设置

```python
def set_colorspace(output_node, colorspace):
    """设置色彩空间"""
    output_node.property("colorspace").setValue(colorspace, 0)

def get_recommended_colorspace(delivery_target):
    """获取推荐色彩空间"""
    recommendations = {
        "web": "srgb",
        "hdtv": "rec709",
        "uhdtv": "rec2020",
        "cinema": "dci_p3",
        "aces_workflow": "acescg",
        "aces_delivery": "aces2065-1",
        "arri": "arri_logc",
        "sony": "slog3"
    }
    return recommendations.get(delivery_target, "linear")
```

### 7.3 色彩管线

```
拍摄(Log) → Silhouette(线性工作) → 输出(目标空间)
    ↓              ↓                    ↓
 arri_logc      linear              rec709
 slog3          acescg              srgb
 red_log        linear              dci_p3
```

### 7.4 色彩管理最佳实践

1. **统一工作空间**:项目内统一使用一个工作色彩空间
2. **正确标记输入**:导入素材时标记正确的色彩空间
3. **输出转换**:输出时转换到目标色彩空间
4. **元数据保留**:输出文件包含色彩空间元数据
5. **下游一致**:确保下游软件使用相同色彩管理

## 8. 最佳实践

### 8.1 格式选择速查

| 场景 | 推荐格式 | 原因 |
|------|----------|------|
| Roto Matte 导出 | EXR(PIZ) | 无损+多通道 |
| 跟踪数据导出 | JSON | 结构化+可读 |
| 预览输出 | PNG | 无损+小文件 |
| 最终交付 | EXR 或 ProRes | 行业标准 |
| Web 交付 | MP4(H.264) | 兼容性 |
| 影院交付 | DPX 或 ProRes | 影视标准 |

### 8.2 质量与文件大小权衡

```python
def optimize_output_settings(quality_priority="balanced"):
    """优化输出设置"""
    if quality_priority == "max_quality":
        return {
            "format": "exr",
            "bit_depth": 32,
            "compression": "piz",
            "colorspace": "aces2065-1"
        }
    elif quality_priority == "balanced":
        return {
            "format": "exr",
            "bit_depth": 16,
            "compression": "zip",
            "colorspace": "acescg"
        }
    elif quality_priority == "small_file":
        return {
            "format": "exr",
            "bit_depth": 16,
            "compression": "piz",
            "colorspace": "rec709"
        }
    elif quality_priority == "preview":
        return {
            "format": "png",
            "bit_depth": 8,
            "compression": "default",
            "colorspace": "srgb"
        }
```

### 8.3 命名规范

```
文件命名:[项目]_[镜头]_[类型]_[对象]_[版本]_[帧号].[扩展名]

示例:
PROJ001_SH0100_MATTE_character_v01_0001.exr
PROJ001_SH0100_TRACK_face_v01.json
PROJ001_SH0100_COMP_final_v03_0001.exr
PROJ001_SH0100_PREVIEW_web_v01.mp4
```

### 8.4 输出验证

```python
def validate_output(output_path, expected_settings):
    """验证输出文件"""
    import os
    
    issues = []
    
    # 检查文件存在
    if not os.path.exists(output_path):
        return ["文件不存在"]
    
    # 检查文件大小
    size = os.path.getsize(output_path)
    if size == 0:
        issues.append("文件为空")
    elif size < 1000:
        issues.append(f"文件异常小: {size} bytes")
    
    # 检查扩展名
    ext = os.path.splitext(output_path)[1].lower()
    expected_ext = f".{expected_settings.get('format', 'exr')}"
    if ext != expected_ext:
        issues.append(f"扩展名不匹配: {ext} vs {expected_ext}")
    
    return issues
```

### 8.5 性能考虑

| 格式 | 写入速度 | 读取速度 | 内存占用 |
|------|----------|----------|----------|
| EXR(PIZ) | 慢 | 中 | 中 |
| EXR(ZIP) | 中 | 快 | 中 |
| EXR(无压缩) | 快 | 最快 | 高 |
| TIFF | 中 | 快 | 低 |
| PNG | 中 | 中 | 低 |
| DPX | 快 | 快 | 高 |

---

## 附录:格式速查表

### 图像格式

| 格式 | 扩展名 | 位深 | Alpha | HDR | 压缩 |
|------|--------|------|-------|-----|------|
| EXR | .exr | 16/32 | ✓ | ✓ | PIZ/ZIP |
| TIFF | .tif | 8/16/32 | ✓ | 有限 | LZW/ZIP |
| PNG | .png | 8/16 | ✓ | ✗ | ZIP |
| DPX | .dpx | 8/10/12/16 | ✓ | 有限 | 无 |
| TGA | .tga | 8/16 | ✓ | ✗ | RLE |
| JPEG | .jpg | 8 | ✗ | ✗ | 有损 |

### 视频格式

| 格式 | 扩展名 | 编码器 | Alpha | 质量 |
|------|--------|--------|-------|------|
| QuickTime | .mov | ProRes | ✓(4444) | 高 |
| MP4 | .mp4 | H.264/265 | ✗ | 中 |
| AVI | .avi | 各种 | 取决编码 | 取决编码 |
| WebM | .webm | VP8/VP9 | ✗ | 中 |

### 数据格式

| 格式 | 扩展名 | 用途 | 可读性 |
|------|--------|------|--------|
| JSON | .json | 跟踪/元数据 | 好 |
| XML | .xml | 剪辑信息 | 中 |
| CSV | .csv | 表格数据 | 好 |
| TXT | .txt | AE 关键帧 | 好 |

> **提示**:选择输出格式时,优先考虑下游软件的需求和兼容性,而不是个人偏好。与团队统一格式可大幅减少集成问题。
