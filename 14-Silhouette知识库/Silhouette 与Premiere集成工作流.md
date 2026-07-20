# Silhouette 与Premiere集成工作流

> 分类: 集成与导出
> 更新日期: 2026-07-11
> 概述: Premiere 集成、动态链接、遮罩传递完整说明。

## 目录
1. [集成概述](#1-集成概述)
2. [数据交换方式](#2-数据交换方式)
3. [遮罩传递](#3-遮罩传递)
4. [动态链接](#4-动态链接)
5. [导出设置](#5-导出设置)
6. [脚本化集成](#6-脚本化集成)
7. [常见工作流](#7-常见工作流)
8. [最佳实践](#8-最佳实践)

---

## 1. 集成概述

### 1.1 Premiere 的角色

| 角色 | 说明 |
|------|------|
| 剪辑 | 视频剪辑和排列 |
| 调色 | 基础调色(Lumetri) |
| 字幕 | 字幕和图形 |
| 输出 | 最终编码输出 |
| 遮罩应用 | 使用 Silhouette 生成的遮罩 |

### 1.2 集成场景

| 场景 | Silhouette 任务 | Premiere 任务 |
|------|----------------|---------------|
| 对象隔离 | 生成 Matte | 应用遮罩限制效果 |
| 背景替换 | Roto 前景 | 替换背景 |
| 局部调色 | 生成区域遮罩 | 应用 Lumetri 到特定区域 |
| 修复传递 | Paint 修复 | 使用修复后的画面 |

### 1.3 集成限制

| 限制 | 说明 | 解决方案 |
|------|------|----------|
| 无节点图 | Premiere 不支持节点图 | 通过文件交换 |
| 无动态链接 | 与 Silhouette 无直接链接 | 使用 AE 中转 |
| 有限遮罩支持 | 仅支持轨道遮罩 | 导出 Alpha 序列 |

## 2. 数据交换方式

### 2.1 支持的交换格式

| 格式 | 用途 | 优势 |
|------|------|------|
| PNG 序列 | 遮罩传输 | 无损、支持 Alpha |
| EXR 序列 | 高质量图像 | HDR、多通道 |
| ProRes | 视频片段 | 高质量、小文件 |
| DNxHR | 视频片段 | 影视标准 |
| XML | 剪辑信息 | 时间线交换 |

### 2.2 推荐工作流

```
Silhouette → PNG/EXR 序列(遮罩) → Premiere
Silhouette → ProRes(修复画面) → Premiere
```

## 3. 遮罩传递

### 3.1 导出遮罩供 Premiere 使用

```python
from fx import *

def export_matte_for_premiere(session, roto_node, source, output_path,
                               frame_range, format="png"):
    """导出适合 Premiere 的遮罩"""
    # 创建 Matte 节点
    matte = Node("Matte")
    matte.label = "MATTE_Export"
    session.addNode(matte)
    matte.inputs[0].connect(source.outputs[0])
    matte.inputs[1].connect(roto_node.outputs[0])
    
    # 创建输出
    output = Node("Output")
    output.label = "OUT_Premiere_Matte"
    session.addNode(output)
    output.inputs[0].connect(matte.outputs[0])
    
    # 配置
    output.property("format").setValue(format, 0)
    output.property("outputPath").setValue(output_path, 0)
    output.property("startFrame").setValue(frame_range[0], 0)
    output.property("endFrame").setValue(frame_range[1], 0)
    
    # Premiere 推荐:PNG 8bit,Alpha 通道
    if format == "png":
        output.property("bitDepth").setValue(8, 0)
        output.property("colorspace").setValue("srgb", 0)
    
    # 命名:Premiere 友好
    output.property("outputName").setValue(
        "matte_[####].png", 0
    )
    
    return output
```

### 3.2 Premiere 中使用遮罩

```
Premiere 中的操作:
1. File → Import → 选择遮罩序列第一帧
2. 勾选 "Image Sequence"
3. 将遮罩序列拖入时间线(放在视频层上方)
4. 选中目标视频层
5. Effect Controls → Track Matte Key
6. 设置 Matte Track 为遮罩序列所在轨道
```

### 3.3 轨道遮罩设置

| 设置项 | 值 | 说明 |
|--------|-----|------|
| Matte Track | 遮罩所在轨道 | V2 或更高 |
| Composite Using | Matte Alpha | 使用 Alpha 通道 |
| Reverse | 否 | 不反转(除非需要) |

## 4. 动态链接

### 4.1 通过 AE 中转

由于 Silhouette 与 Premiere 无直接动态链接,通常通过 After Effects 中转:

```
Silhouette → 导出遮罩 → AE 导入 → 动态链接到 Premiere
```

### 4.2 AE 动态链接设置

```javascript
// AE JavaScript:创建动态链接合成
function createDynamicLinkComp(name, width, height, duration) {
    var comp = app.project.items.addComp(name, width, height, 1, duration, 24);
    
    // 动态链接到 Premiere
    var premiereProject = app.premiere;
    if (premiereProject) {
        // 通过 Adobe Dynamic Link 创建
        premiereProject.createDynamicLink(comp);
    }
    
    return comp;
}
```

### 4.3 Premiere 端接收

```
Premiere 中使用动态链接:
1. File → Adobe Dynamic Link → New After Effects Composition
2. 或:File → Adobe Dynamic Link → Import After Effects Composition
3. AE 合成将作为视频剪辑出现在 Premiere 中
4. 修改 AE 合成自动更新到 Premiere
```

## 5. 导出设置

### 5.1 为 Premiere 优化的导出

```python
def export_for_premiere(session, comp_node, output_path, frame_range):
    """为 Premiere 优化导出"""
    output = Node("Output")
    session.addNode(output)
    output.inputs[0].connect(comp_node.outputs[0])
    
    # Premiere 友好的设置
    output.property("format").setValue("png", 0)  # 或 mov
    output.property("colorspace").setValue("rec709", 0)
    output.property("bitDepth").setValue(8, 0)
    output.property("startFrame").setValue(frame_range[0], 0)
    output.property("endFrame").setValue(frame_range[1], 0)
    
    # 命名:Premiere 友好
    output.property("outputName").setValue(
        "silhouette_output_[####].png", 0
    )
    output.property("outputPath").setValue(output_path, 0)
    
    return output
```

### 5.2 视频格式导出

```python
def export_video_for_premiere(session, comp_node, output_path, 
                               codec="prores", quality="high"):
    """导出视频格式供 Premiere"""
    output = Node("Output")
    session.addNode(output)
    output.inputs[0].connect(comp_node.outputs[0])
    
    # 视频格式
    output.property("format").setValue("mov", 0)
    
    # 编码器选择
    codec_map = {
        "prores": "prores_422_hq",
        "dnxhr": "dnxhr_hqx",
        "h264": "h264_high",
        "h265": "h265_main"
    }
    
    output.property("codec").setValue(
        codec_map.get(codec, "prores_422_hq"), 0
    )
    
    # 质量设置
    quality_map = {
        "high": 100,
        "medium": 75,
        "low": 50
    }
    
    output.property("quality").setValue(
        quality_map.get(quality, 100), 0
    )
    
    output.property("outputPath").setValue(output_path, 0)
    
    return output
```

### 5.3 格式选择建议

| 用途 | 推荐格式 | 原因 |
|------|----------|------|
| 遮罩传递 | PNG 序列 | 无损、Alpha 支持 |
| 修复画面 | ProRes | 高质量、小文件 |
| 最终输出 | H.264/H.265 | 兼容性好 |
| 中间文件 | DNxHR | 影视标准 |

## 6. 脚本化集成

### 6.1 完整集成脚本

```python
class PremiereIntegration:
    """Premiere 集成工具"""
    
    def __init__(self, output_base="/output/premiere/"):
        self.output_base = output_base
    
    def export_all(self, session, source, roto_nodes, frame_range):
        """导出所有内容供 Premiere"""
        import os
        os.makedirs(self.output_base, exist_ok=True)
        
        results = {}
        
        # 1. 导出主图像(修复后)
        main_output = os.path.join(self.output_base, "main/")
        os.makedirs(main_output, exist_ok=True)
        export_for_premiere(session, source, main_output, frame_range)
        results["main"] = main_output
        
        # 2. 导出每个遮罩
        for name, roto_node in roto_nodes.items():
            matte_output = os.path.join(self.output_base, f"matte_{name}/")
            os.makedirs(matte_output, exist_ok=True)
            export_matte_for_premiere(
                session, roto_node, source, 
                matte_output, frame_range
            )
            results[f"matte_{name}"] = matte_output
        
        # 3. 生成 Premiere 项目信息
        self.generate_premiere_info(results, frame_range)
        
        return results
    
    def generate_premiere_info(self, outputs, frame_range):
        """生成 Premiere 项目信息"""
        import json
        
        info = {
            "source": "silhouette",
            "frame_rate": 24,
            "frame_range": frame_range,
            "resolution": [1920, 1080],
            "outputs": outputs,
            "instructions": {
                "main": "导入为视频素材",
                "matte": "导入为序列,用作 Track Matte Key"
            }
        }
        
        info_path = os.path.join(self.output_base, "premiere_info.json")
        with open(info_path, "w") as f:
            json.dump(info, f, indent=2, ensure_ascii=False)
        
        return info_path
```

### 6.2 批量处理

```python
def batch_export_for_premiere(shots, base_output):
    """批量导出多个镜头"""
    for shot in shots:
        print(f"处理镜头: {shot['id']}")
        
        output_dir = os.path.join(base_output, shot["id"])
        os.makedirs(output_dir, exist_ok=True)
        
        # 打开项目
        project = Project.open(shot["project_path"])
        session = project.item(0)
        session.activate()
        
        # 导出
        integration = PremiereIntegration(output_dir)
        results = integration.export_all(
            session, source, roto_nodes, shot["frame_range"]
        )
        
        print(f"镜头 {shot['id']} 完成: {results}")
```

## 7. 常见工作流

### 7.1 局部调色工作流

```
1. Silhouette:
   a. Roto 需要调色的对象
   b. 导出遮罩序列(PNG with Alpha)

2. Premiere:
   a. 导入原始视频和遮罩序列
   b. 将遮罩放在 V2 轨道
   c. 给原始视频添加 Lumetri Color
   d. 添加 Track Matte Key 效果
   e. 设置 Matte Track 为 V2
   f. 调整 Lumetri 参数(仅影响遮罩区域)
```

### 7.2 对象替换工作流

```
1. Silhouette:
   a. Roto 要替换的对象
   b. 导出遮罩

2. Premiere:
   a. 导入遮罩序列
   b. 将替换素材放在 V3 轨道
   c. 给替换素材添加 Track Matte Key
   d. 设置 Matte Track 为遮罩所在轨道
   e. 调整位置和缩放匹配
```

### 7.3 修复画面传递

```
1. Silhouette:
   a. 使用 Paint 修复瑕疵
   b. 导出修复后的画面(ProRes)

2. Premiere:
   a. 导入修复后的视频
   b. 替换原始片段
   c. 或:叠加在原片段上方(V2)
```

## 8. 最佳实践

### 8.1 帧率与分辨率匹配

```python
def ensure_compatibility(session, target_fps=24, target_resolution=(1920, 1080)):
    """确保与 Premiere 兼容"""
    if session.frameRate != target_fps:
        print(f"警告:帧率 {session.frameRate} 与目标 {target_fps} 不匹配")
    
    if session.width != target_resolution[0] or session.height != target_resolution[1]:
        print(f"警告:分辨率不匹配")
    
    return True
```

### 8.2 色彩空间

| Silhouette 设置 | Premiere 设置 | 说明 |
|----------------|---------------|------|
| rec709 | Rec.709 | 标准视频 |
| srgb | sRGB | Web 内容 |
| acescg | ACES | HDR 工作流 |

### 8.3 文件组织

```
/premiere_project/
  /source/          # 原始素材
  /silhouette/
    /mattes/        # 遮罩序列
      /character/
      /background/
    /renders/       # 修复后的画面
  /premiere/
    /project.prproj
    /exports/
```

### 8.4 命名规范

```
遮罩:
  matte_[object]_[####].png
  
修复画面:
  painted_[shot]_v[version]_[####].mov
  
最终输出:
  final_[project]_[shot]_v[version].mp4
```

### 8.5 性能建议

| 优化项 | 建议 |
|--------|------|
| 遮罩格式 | PNG(压缩)或 ProRes 4444(带 Alpha) |
| 预览代理 | 遮罩序列使用低分辨率代理 |
| 渲染设置 | 使用 GPU 加速(Mercury Playback) |
| 缓存 | 启用 Premiere 缓存 |

---

## 附录:Premiere 效果对应

| Silhouette | Premiere | 说明 |
|------------|----------|------|
| Matte | Track Matte Key | 轨道遮罩 |
| Color | Lumetri Color | 色彩校正 |
| Filter(Blur) | Gaussian Blur | 模糊 |
| Filter(Sharpen) | Sharpen | 锐化 |
| Composite | Opacity/Masking | 图层合成 |

> **提示**:Premiere 不支持节点图,复杂合成建议通过 AE 动态链接实现,Silhouette 负责生成遮罩和修复画面。
