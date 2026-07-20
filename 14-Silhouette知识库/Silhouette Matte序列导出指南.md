# Silhouette Matte序列导出指南

> 分类: 集成与导出
> 更新日期: 2026-07-11
> 概述: Matte 序列格式、命名规范、帧范围控制、AE 导入设置完整说明。

## 目录
1. [Matte 序列概述](#1-matte-序列概述)
2. [导出格式](#2-导出格式)
3. [命名规范](#3-命名规范)
4. [帧范围控制](#4-帧范围控制)
5. [导出配置](#5-导出配置)
6. [AE 导入设置](#6-ae-导入设置)
7. [脚本化导出](#7-脚本化导出)
8. [最佳实践](#8-最佳实践)

---

## 1. Matte 序列概述

### 1.1 什么是 Matte 序列

Matte 序列是一组连续的图像文件,每帧存储一个遮罩(通常是灰度或 Alpha 通道),用于在后期合成中控制图层可见性。

### 1.2 Matte 的用途

| 用途 | 说明 |
|------|------|
| 抠像 | 将对象从背景中分离 |
| 合成控制 | 限制效果作用范围 |
| 深度合成 | 基于 Z 深度的合成 |
| 对象隔离 | 独立调整特定对象 |
| 特效遮罩 | 限制粒子、光效等范围 |

### 1.3 Matte 类型

| 类型 | 通道 | 说明 |
|------|------|------|
| 二值遮罩 | 0 或 1 | 硬边缘,无抗锯齿 |
| 灰度遮罩 | 0-255 | 支持半透明和羽化 |
| Alpha 遮罩 | RGBA | 带颜色的遮罩 |
| 多通道遮罩 | 多通道 | 多个对象独立遮罩 |

## 2. 导出格式

### 2.1 支持的格式

| 格式 | 扩展名 | 优点 | 缺点 | 推荐场景 |
|------|--------|------|------|----------|
| EXR | .exr | HDR、多通道、无损 | 文件大 | 最终交付 |
| PNG | .png | 无损压缩、广泛支持 | 无 HDR | 预览、Web |
| TIFF | .tif | 无损、支持 Alpha | 文件较大 | 中间文件 |
| DPX | .dpx | 影视标准、10bit | 无压缩大 | 影视流程 |
| TGA | .tga | 简单、支持 Alpha | 8bit 限制 | 传统流程 |

### 2.2 格式选择建议

```
最终交付?
├─ 是 → EXR(PIZ 压缩)
├─ 影视交付 → DPX(10bit)
└─ 否(中间/预览)
    ├─ 需要无损? → TIFF
    ├─ 需要小文件? → PNG
    └─ 快速预览? → JPEG(仅预览)
```

### 2.3 位深选择

| 位深 | 每通道值数 | 文件大小 | 推荐场景 |
|------|-----------|----------|----------|
| 8bit | 256 | 最小 | 预览、Web |
| 16bit | 65536 | 2x | 标准工作流 |
| 32bit float | 无限 | 4x | HDR、最终输出 |

## 3. 命名规范

### 3.1 标准命名格式

```
[项目]_[镜头]_[对象]_[版本]_[帧号].[扩展名]
```

示例:
```
PROJ001_SH0100_CHARACTER_v01_0001.exr
PROJ001_SH0100_CHARACTER_v01_0002.exr
...
PROJ001_SH0100_CHARACTER_v01_0100.exr
```

### 3.2 帧号填充

| 帧数 | 填充位数 | 示例 |
|------|----------|------|
| < 100 | 4 | `0001` |
| 100-999 | 4 | `0100` |
| 1000-9999 | 4 | `1000` |
| > 9999 | 5 | `10000` |

### 3.3 Silhouette 命名模板

```python
# Silhouette 输出命名模板
OUTPUT_NAME_TEMPLATES = {
    "standard": "[project]_[shot]_[object]_v[version]_[####].[ext]",
    "simple": "[shot]_[####].[ext]",
    "with_date": "[project]_[shot]_[YYYYMMDD]_[####].[ext]",
    "matte_specific": "[project]_[shot]_MATTE_[object]_v[version]_[####].[ext]"
}

# 模板变量说明
TEMPLATE_VARIABLES = {
    "[project]": "项目名称",
    "[shot]": "镜头编号",
    "[object]": "对象名称",
    "[version]": "版本号",
    "[####]": "帧号(4位填充)",
    "[ext]": "文件扩展名",
    "[YYYYMMDD]": "日期(年月日)",
    "[YYYY]": "年份",
    "[MM]": "月份",
    "[DD]": "日期"
}
```

### 3.4 设置输出名称

```python
from fx import *

def set_output_name(output_node, project, shot, obj, version, ext="exr"):
    """设置标准输出名称"""
    name = f"{project}_{shot}_MATTE_{obj}_v{version:02d}_####.{ext}"
    output_node.property("outputName").setValue(name, 0)
    return name

# 使用
set_output_name(output, "PROJ001", "SH0100", "CHARACTER", 1, "exr")
# 输出: PROJ001_SH0100_MATTE_CHARACTER_v01_0001.exr
```

## 4. 帧范围控制

### 4.1 帧范围参数

| 参数 | 说明 |
|------|------|
| `startFrame` | 起始帧 |
| `endFrame` | 结束帧 |
| `frameStep` | 帧步长(默认1) |
| `padding` | 帧号填充位数 |

### 4.2 设置帧范围

```python
def set_frame_range(output_node, start, end, step=1, padding=4):
    """设置输出帧范围"""
    output_node.property("startFrame").setValue(start, 0)
    output_node.property("endFrame").setValue(end, 0)
    output_node.property("frameStep").setValue(step, 0)
    output_node.property("padding").setValue(padding, 0)

# 示例:导出 1-100 帧,每帧都导
set_frame_range(output, 1, 100, step=1)

# 示例:隔帧导出(预览用)
set_frame_range(output, 1, 100, step=2)
```

### 4.3 自定义帧列表

```python
def export_custom_frames(output_node, frame_list):
    """导出自定义帧列表"""
    for frame in frame_list:
        render(output_node, frame, frame)
        print(f"已导出帧: {frame}")

# 示例:只导出关键帧
key_frames = [1, 10, 25, 50, 75, 100]
export_custom_frames(output, key_frames)
```

## 5. 导出配置

### 5.1 Output 节点配置

```python
def configure_matte_output(output_node, format="exr", colorspace="linear",
                            compression="piz", premultiply=True):
    """配置 Matte 输出"""
    # 基本设置
    output_node.property("format").setValue(format, 0)
    output_node.property("colorspace").setValue(colorspace, 0)
    output_node.property("premultiply").setValue(premultiply, 0)
    
    # 格式特定设置
    if format == "exr":
        output_node.property("compression").setValue(compression, 0)
        output_node.property("bitDepth").setValue(16, 0)
    elif format == "png":
        output_node.property("bitDepth").setValue(8, 0)
    elif format == "dpx":
        output_node.property("bitDepth").setValue(10, 0)
    
    return output_node
```

### 5.2 多对象 Matte 导出

```python
def export_multi_object_mattes(session, source, objects_config):
    """
    导出多个对象的独立 Matte
    objects_config: [
        {"name": "character", "roto_node": roto1},
        {"name": "hair", "roto_node": roto2},
        {"name": "background", "roto_node": roto3}
    ]
    """
    outputs = []
    
    for obj in objects_config:
        # 创建 Matte 节点提取遮罩
        matte = Node("Matte")
        matte.label = f"MATTE_{obj['name']}"
        session.addNode(matte)
        matte.inputs[0].connect(source.outputs[0])
        matte.inputs[1].connect(obj["roto_node"].outputs[0])
        
        # 创建输出节点
        output = Node("Output")
        output.label = f"OUT_{obj['name']}"
        session.addNode(output)
        output.inputs[0].connect(matte.outputs[0])
        
        # 配置输出
        configure_matte_output(output, format="exr")
        set_output_name(output, "PROJ", "SH001", obj["name"], 1)
        
        outputs.append(output)
    
    return outputs
```

### 5.3 遮罩优化

```python
def optimize_matte_for_export(matte_node, feather=0.5, grow=0, blur=0):
    """优化遮罩用于导出"""
    # 羽化边缘
    feather_prop = matte_node.property("feather")
    if feather_prop:
        feather_prop.setValue(feather, 0)
    
    # 扩展边缘
    grow_prop = matte_node.property("grow")
    if grow_prop:
        grow_prop.setValue(grow, 0)
    
    # 边缘模糊
    blur_prop = matte_node.property("blur")
    if blur_prop:
        blur_prop.setValue(blur, 0)
    
    return matte_node
```

## 6. AE 导入设置

### 6.1 导入步骤

```
1. After Effects → File → Import → File
2. 选择序列第一帧(如 0001.exr)
3. 勾选 "PNG Sequence" 或 "EXR Sequence"
4. 点击 Import
5. 将序列拖入合成
```

### 6.2 导入选项

| 选项 | 推荐值 | 说明 |
|------|--------|------|
| Import As | Footage | 作为素材导入 |
| Color Space | 与 Silhouette 输出一致 | 保持色彩一致 |
| Alpha | Straight 或 Premultiplied | 根据输出设置 |
| Frame Rate | 与项目一致 | 匹配帧率 |
| Start Frame | 0 或 1 | 根据项目设置 |

### 6.3 AE 脚本导入

```javascript
// After Effects JavaScript
function importMatteSequence(path, name) {
    var importOptions = new ImportOptions();
    importOptions.file = new File(path + "/0001.exr");
    importOptions.sequence = true;
    
    var footage = app.project.importFile(importOptions);
    footage.name = name;
    
    // 设置帧率
    footage.mainSource.conformFrameRate = 24;
    
    return footage;
}

// 使用
importMatteSequence("/path/to/matte", "Character_Matte");
```

### 6.4 Matte 在 AE 中的使用

```javascript
// 将 Matte 用作轨道遮罩
function applyTrackMatte(layer, matteLayer) {
    // 将 matte 层放在目标层上方
    matteLayer.moveBefore(layer);
    
    // 设置轨道遮罩
    layer.trackMatteType = TrackMatteType.ALPHA;
    layer.parent = matteLayer;
}

// 使用 EXtractoR 提取通道(多通道 EXR)
function extractChannel(layer, channelName) {
    var effect = layer.Effects.addProperty("EXtractoR");
    effect.property("channel").setValue(channelName);
}
```

## 7. 脚本化导出

### 7.1 完整导出脚本

```python
#!/usr/bin/env python
"""Matte 序列导出脚本"""

from fx import *
import os

class MatteExporter:
    """Matte 导出器"""
    
    def __init__(self, project_name, shot_name):
        self.project_name = project_name
        self.shot_name = shot_name
        self.version = 1
    
    def export_matte(self, session, source_node, roto_node, object_name,
                     frame_range, output_dir, format="exr"):
        """导出单个对象的 Matte"""
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        
        # 创建 Matte 节点
        matte = Node("Matte")
        matte.label = f"MATTE_{object_name}"
        session.addNode(matte)
        matte.inputs[0].connect(source_node.outputs[0])
        matte.inputs[1].connect(roto_node.outputs[0])
        
        # 优化遮罩
        optimize_matte_for_export(matte, feather=0.5)
        
        # 创建输出节点
        output = Node("Output")
        output.label = f"OUT_{object_name}"
        session.addNode(output)
        output.inputs[0].connect(matte.outputs[0])
        
        # 配置输出
        configure_matte_output(output, format=format)
        set_output_name(output, self.project_name, self.shot_name,
                       object_name, self.version)
        set_frame_range(output, frame_range[0], frame_range[1])
        
        # 设置输出路径
        output_path = os.path.join(output_dir, f"{object_name}_v{self.version:02d}")
        os.makedirs(output_path, exist_ok=True)
        output.property("outputPath").setValue(output_path, 0)
        
        # 渲染
        print(f"导出 {object_name} Matte: {frame_range[0]}-{frame_range[1]}")
        render(output, frame_range[0], frame_range[1])
        
        # 清理临时节点
        matte.remove()
        output.remove()
        
        return output_path
    
    def export_all_mattes(self, session, source, objects, frame_range, output_dir):
        """导出所有对象的 Matte"""
        results = {}
        for obj_name, roto_node in objects.items():
            try:
                path = self.export_matte(session, source, roto_node,
                                        obj_name, frame_range, output_dir)
                results[obj_name] = {"status": "success", "path": path}
            except Exception as e:
                results[obj_name] = {"status": "failed", "error": str(e)}
        
        return results

# 使用
exporter = MatteExporter("PROJ001", "SH0100")
results = exporter.export_all_mattes(
    session, source,
    {"character": roto_char, "hair": roto_hair, "bg": roto_bg},
    (1, 100),
    "/output/mattes/"
)
```

### 7.2 批量导出多个镜头

```python
def batch_export_mattes(shot_list, base_output_dir):
    """批量导出多个镜头的 Matte"""
    for shot in shot_list:
        print(f"\n处理镜头: {shot['id']}")
        
        # 打开项目
        project = Project.open(shot["project_path"])
        session = project.item(0)
        session.activate()
        
        # 查找源和 Roto 节点
        source = find_node_by_type(session, "Source")
        roto_nodes = find_nodes_by_type(session, "RotoShape")
        
        # 导出
        exporter = MatteExporter(shot["project"], shot["id"])
        objects = {n.label: n for n in roto_nodes}
        
        results = exporter.export_all_mattes(
            session, source, objects,
            shot["frame_range"],
            os.path.join(base_output_dir, shot["id"])
        )
        
        print(f"镜头 {shot['id']} 完成: {results}")
```

## 8. 最佳实践

### 8.1 导出前检查

```python
def pre_export_checklist(session, frame_range, output_dir):
    """导出前检查清单"""
    checks = []
    
    # 检查帧范围
    if frame_range[0] > frame_range[1]:
        checks.append("✗ 帧范围无效:起始帧大于结束帧")
    else:
        checks.append("✓ 帧范围有效")
    
    # 检查输出目录
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        checks.append("✓ 创建输出目录")
    else:
        checks.append("✓ 输出目录存在")
    
    # 检查磁盘空间
    free_space = get_free_space(output_dir)
    if free_space < 1024 * 1024 * 1024:  # < 1GB
        checks.append("✗ 磁盘空间不足(< 1GB)")
    else:
        checks.append(f"✓ 磁盘空间充足({free_space / 1024**3:.1f}GB)")
    
    # 检查节点连接
    output_nodes = find_nodes_by_type(session, "Output")
    if not output_nodes:
        checks.append("✗ 没有 Output 节点")
    else:
        checks.append(f"✓ 找到 {len(output_nodes)} 个 Output 节点")
    
    return checks

def get_free_space(path):
    """获取磁盘剩余空间"""
    import shutil
    total, used, free = shutil.disk_usage(path)
    return free
```

### 8.2 质量验证

```python
def verify_matte_quality(output_path, expected_frames):
    """验证 Matte 质量"""
    import os
    
    issues = []
    
    # 检查文件数量
    files = [f for f in os.listdir(output_path) if f.endswith((".exr", ".png", ".tif"))]
    if len(files) != expected_frames:
        issues.append(f"帧数不匹配: 期望 {expected_frames}, 实际 {len(files)}")
    
    # 检查文件大小(异常小的文件可能有问题)
    for f in files:
        filepath = os.path.join(output_path, f)
        size = os.path.getsize(filepath)
        if size < 1000:  # < 1KB
            issues.append(f"文件异常小: {f} ({size} bytes)")
    
    # 检查连续性
    frame_nums = sorted(extract_frame_number(f) for f in files)
    for i in range(1, len(frame_nums)):
        if frame_nums[i] - frame_nums[i-1] != 1:
            issues.append(f"帧不连续: {frame_nums[i-1]} → {frame_nums[i]}")
    
    return issues

def extract_frame_number(filename):
    """从文件名提取帧号"""
    import re
    match = re.search(r'(\d+)\.\w+$', filename)
    return int(match.group(1)) if match else -1
```

### 8.3 命名最佳实践

| 规则 | 示例 | 说明 |
|------|------|------|
| 使用大写 | `CHARACTER` | 提高可读性 |
| 用下划线分隔 | `PROJ_SH001` | 避免空格 |
| 版本号填充 | `v01`, `v02` | 保持排序 |
| 帧号填充 | `0001`, `0100` | 保持排序 |
| 避免特殊字符 | 无 `&%#` | 避免兼容问题 |
| 包含日期(可选) | `20260711` | 便于追踪 |

### 8.4 性能建议

| 优化项 | 建议 |
|--------|------|
| 输出到本地 SSD | 避免网络存储 |
| 分批渲染 | 大量帧分批处理 |
| 使用合适格式 | 预览用 PNG,交付用 EXR |
| 关闭预览 | 导出时关闭实时预览 |
| 清理缓存 | 导出前清理内存缓存 |

---

## 附录:导出检查清单

| 检查项 | 说明 |
|--------|------|
| □ 帧范围正确 | 起始和结束帧匹配 |
| □ 输出路径有效 | 目录存在且有权限 |
| □ 磁盘空间充足 | 预估输出大小 |
| □ 命名规范 | 遵循项目命名约定 |
| □ 格式选择 | 匹配下游软件需求 |
| □ 色彩空间 | 与项目设置一致 |
| □ Alpha 处理 | premultiply 设置正确 |
| □ 质量验证 | 导出后检查文件完整性 |

> **提示**:导出前务必与下游环节(AE/Nuke)确认格式、命名和帧率要求,避免因不兼容导致返工。
