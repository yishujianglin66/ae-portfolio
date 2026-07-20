# Silhouette 渲染设置参考

> 分类: 预设与配置
> 更新日期: 2026-07-11
> 概述: 渲染参数详解、格式选择、质量权衡、性能优化完整说明。

## 目录
1. [渲染设置概述](#1-渲染设置概述)
2. [渲染参数详解](#2-渲染参数详解)
3. [格式选择](#3-格式选择)
4. [质量权衡](#4-质量权衡)
5. [性能优化](#5-性能优化)
6. [渲染预设](#6-渲染预设)
7. [脚本化渲染](#7-脚本化渲染)
8. [最佳实践](#8-最佳实践)

---

## 1. 渲染设置概述

### 1.1 渲染的重要性

渲染是将节点图转化为最终图像的过程,设置直接影响输出质量和效率。

### 1.2 渲染设置分类

| 分类 | 参数 | 影响 |
|------|------|------|
| 格式设置 | 格式、编码、位深 | 文件兼容性 |
| 质量设置 | 采样、抗锯齿、运动模糊 | 图像质量 |
| 性能设置 | 线程数、GPU、缓存 | 渲染速度 |
| 输出设置 | 路径、命名、帧范围 | 文件管理 |
| 色彩设置 | 色彩空间、LUT | 色彩准确性 |

### 1.3 渲染流程

```
准备阶段 → 设置参数 → 预检查 → 渲染执行 → 验证输出
    ↓           ↓          ↓          ↓          ↓
 加载项目   配置Output   检查资源   逐帧渲染   检查文件
```

## 2. 渲染参数详解

### 2.1 基本参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `format` | string | "exr" | 输出格式 |
| `bitDepth` | int | 16 | 位深 |
| `compression` | string | "piz" | 压缩方式 |
| `colorspace` | string | "acescg" | 色彩空间 |
| `premultiply` | bool | true | 预乘 Alpha |
| `startFrame` | int | 1 | 起始帧 |
| `endFrame` | int | 100 | 结束帧 |
| `frameStep` | int | 1 | 帧步长 |
| `padding` | int | 4 | 帧号填充 |

### 2.2 质量参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `antiAliasing` | int | 4 | 抗锯齿级别 |
| `motionBlur` | bool | false | 运动模糊 |
| `motionBlurShutter` | float | 0.5 | 快门角度 |
| `motionBlurSamples` | int | 8 | 运动模糊采样 |
| `superSampling` | int | 1 | 超采样 |
| `dithering` | bool | true | 抖动 |

### 2.3 性能参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `threads` | int | 自动 | 线程数 |
| `gpu` | bool | true | GPU 加速 |
| `cacheSize` | int | 20 | 缓存帧数 |
| `tileSize` | int | 256 | 分块大小 |
| `memoryLimit` | int | 0 | 内存限制(MB) |

### 2.4 完整配置示例

```python
from fx import *

def configure_render_output(output_node, config):
    """配置渲染输出"""
    # 基本设置
    output_node.property("format").setValue(config.get("format", "exr"), 0)
    output_node.property("bitDepth").setValue(config.get("bitDepth", 16), 0)
    output_node.property("compression").setValue(config.get("compression", "piz"), 0)
    output_node.property("colorspace").setValue(config.get("colorspace", "acescg"), 0)
    output_node.property("premultiply").setValue(config.get("premultiply", True), 0)
    
    # 帧范围
    output_node.property("startFrame").setValue(config.get("startFrame", 1), 0)
    output_node.property("endFrame").setValue(config.get("endFrame", 100), 0)
    output_node.property("frameStep").setValue(config.get("frameStep", 1), 0)
    output_node.property("padding").setValue(config.get("padding", 4), 0)
    
    # 质量设置
    output_node.property("antiAliasing").setValue(config.get("antiAliasing", 4), 0)
    output_node.property("motionBlur").setValue(config.get("motionBlur", False), 0)
    output_node.property("motionBlurShutter").setValue(config.get("motionBlurShutter", 0.5), 0)
    output_node.property("motionBlurSamples").setValue(config.get("motionBlurSamples", 8), 0)
    
    # 输出路径
    output_node.property("outputPath").setValue(config.get("outputPath", "/output/"), 0)
    output_node.property("outputName").setValue(config.get("outputName", "output_[####].exr"), 0)
    
    return output_node
```

## 3. 格式选择

### 3.1 格式决策树

```
输出用途?
├─ 最终交付
│   ├─ 影视 → EXR(PIZ) 或 DPX
│   ├─ 广播 → ProRes 或 DNxHR
│   └─ Web → H.264/H.265
├─ 中间文件
│   ├─ 需要多通道 → EXR
│   └─ 简单图像 → TIFF/PNG
└─ 预览
    ├─ 高质量 → PNG
    └─ 快速 → JPEG
```

### 3.2 格式参数对照

| 格式 | 位深选项 | 压缩选项 | Alpha | 适用场景 |
|------|----------|----------|-------|----------|
| EXR | 16/32 | PIZ/ZIP/RLE/B44 | ✓ | 最终交付 |
| TIFF | 8/16/32 | LZW/ZIP/None | ✓ | 中间文件 |
| PNG | 8/16 | ZIP | ✓ | 预览 |
| DPX | 8/10/12/16 | None | ✓ | 影视 |
| MOV | - | ProRes/H.264 | ✓(4444) | 视频 |
| MP4 | - | H.264/H.265 | ✗ | Web |

### 3.3 格式设置示例

```python
# EXR 最终交付
exr_config = {
    "format": "exr",
    "bitDepth": 16,
    "compression": "piz",
    "colorspace": "acescg",
    "premultiply": True
}

# TIFF 中间文件
tiff_config = {
    "format": "tiff",
    "bitDepth": 16,
    "compression": "lzw",
    "colorspace": "linear"
}

# PNG 预览
png_config = {
    "format": "png",
    "bitDepth": 8,
    "colorspace": "srgb"
}

# ProRes 视频
prores_config = {
    "format": "mov",
    "codec": "prores_422_hq",
    "quality": 100,
    "colorspace": "rec709"
}
```

## 4. 质量权衡

### 4.1 质量与性能

| 质量等级 | 抗锯齿 | 运动模糊采样 | 渲染时间 | 文件大小 |
|----------|--------|-------------|----------|----------|
| 草稿 | 1 | 2 | 1x | 小 |
| 预览 | 2 | 4 | 2x | 中 |
| 标准 | 4 | 8 | 4x | 中 |
| 高质量 | 8 | 16 | 8x | 大 |
| 最终 | 16 | 32 | 16x | 大 |

### 4.2 位深选择

| 位深 | 每通道值数 | 文件大小 | 质量损失 | 推荐用途 |
|------|-----------|----------|----------|----------|
| 8bit | 256 | 1x | 明显 | 预览、Web |
| 16bit | 65536 | 2x | 轻微 | 标准工作流 |
| 32bit float | 无限 | 4x | 无 | HDR、最终交付 |

### 4.3 运动模糊设置

```python
def configure_motion_blur(output_node, motion_type="standard"):
    """配置运动模糊"""
    presets = {
        "off": {"motionBlur": False},
        "preview": {
            "motionBlur": True,
            "motionBlurShutter": 0.5,
            "motionBlurSamples": 4
        },
        "standard": {
            "motionBlur": True,
            "motionBlurShutter": 0.5,
            "motionBlurSamples": 8
        },
        "high_quality": {
            "motionBlur": True,
            "motionBlurShutter": 1.0,
            "motionBlurSamples": 16
        },
        "extreme": {
            "motionBlur": True,
            "motionBlurShutter": 2.0,
            "motionBlurSamples": 32
        }
    }
    
    settings = presets.get(motion_type, presets["standard"])
    for key, value in settings.items():
        prop = output_node.property(key)
        if prop:
            prop.setValue(value, 0)
    
    return output_node
```

### 4.4 质量预设

```python
QUALITY_PRESETS = {
    "draft": {
        "antiAliasing": 1,
        "motionBlur": False,
        "superSampling": 1,
        "dithering": False
    },
    "preview": {
        "antiAliasing": 2,
        "motionBlur": True,
        "motionBlurSamples": 4,
        "superSampling": 1,
        "dithering": True
    },
    "standard": {
        "antiAliasing": 4,
        "motionBlur": True,
        "motionBlurSamples": 8,
        "superSampling": 2,
        "dithering": True
    },
    "high": {
        "antiAliasing": 8,
        "motionBlur": True,
        "motionBlurSamples": 16,
        "superSampling": 4,
        "dithering": True
    },
    "final": {
        "antiAliasing": 16,
        "motionBlur": True,
        "motionBlurSamples": 32,
        "superSampling": 8,
        "dithering": True
    }
}

def apply_quality_preset(output_node, quality="standard"):
    """应用质量预设"""
    preset = QUALITY_PRESETS.get(quality, QUALITY_PRESETS["standard"])
    for key, value in preset.items():
        prop = output_node.property(key)
        if prop:
            prop.setValue(value, 0)
    return output_node
```

## 5. 性能优化

### 5.1 性能影响因素

| 因素 | 影响 | 优化方法 |
|------|------|----------|
| 分辨率 | 线性影响 | 降低预览分辨率 |
| 位深 | 2-4x | 预览用 8bit |
| 抗锯齿 | 2-16x | 预览降低级别 |
| 运动模糊 | 2-32x | 减少采样数 |
| 节点数 | 线性 | 简化节点图 |
| 缓存 | 内存 | 调整缓存大小 |

### 5.2 渲染优化策略

```python
def optimize_for_speed(output_node):
    """优化渲染速度"""
    # 降低质量
    output_node.property("antiAliasing").setValue(2, 0)
    output_node.property("motionBlurSamples").setValue(4, 0)
    output_node.property("superSampling").setValue(1, 0)
    
    # 使用快速压缩
    output_node.property("compression").setValue("zip", 0)
    
    # 降低位深
    output_node.property("bitDepth").setValue(8, 0)
    
    return output_node

def optimize_for_quality(output_node):
    """优化渲染质量"""
    # 最高质量
    output_node.property("antiAliasing").setValue(16, 0)
    output_node.property("motionBlurSamples").setValue(32, 0)
    output_node.property("superSampling").setValue(8, 0)
    output_node.property("dithering").setValue(True, 0)
    
    # 无损压缩
    output_node.property("compression").setValue("piz", 0)
    
    # 最高位深
    output_node.property("bitDepth").setValue(32, 0)
    
    return output_node

def optimize_for_balance(output_node):
    """平衡质量和速度"""
    output_node.property("antiAliasing").setValue(4, 0)
    output_node.property("motionBlurSamples").setValue(8, 0)
    output_node.property("superSampling").setValue(2, 0)
    output_node.property("compression").setValue("zip", 0)
    output_node.property("bitDepth").setValue(16, 0)
    
    return output_node
```

### 5.3 内存管理

```python
def configure_memory(output_node, available_memory_mb):
    """根据可用内存配置"""
    if available_memory_mb < 4096:
        # 低内存:减少缓存
        output_node.property("cacheSize").setValue(5, 0)
        output_node.property("tileSize").setValue(128, 0)
    elif available_memory_mb < 8192:
        # 中等内存
        output_node.property("cacheSize").setValue(10, 0)
        output_node.property("tileSize").setValue(256, 0)
    else:
        # 高内存
        output_node.property("cacheSize").setValue(20, 0)
        output_node.property("tileSize").setValue(512, 0)
    
    return output_node
```

### 5.4 分块渲染

```python
def render_in_tiles(output_node, frame, tile_size=256):
    """分块渲染大图像"""
    # 获取图像尺寸
    width = session.width
    height = session.height
    
    # 计算分块
    tiles_x = (width + tile_size - 1) // tile_size
    tiles_y = (height + tile_size - 1) // tile_size
    
    for ty in range(tiles_y):
        for tx in range(tiles_x):
            x0 = tx * tile_size
            y0 = ty * tile_size
            x1 = min(x0 + tile_size, width)
            y1 = min(y0 + tile_size, height)
            
            # 渲染分块
            render_tile(output_node, frame, x0, y0, x1, y1)
```

## 6. 渲染预设

### 6.1 预设集合

```python
RENDER_PRESETS = {
    "preview_fast": {
        "format": "png",
        "bitDepth": 8,
        "compression": "default",
        "colorspace": "srgb",
        "antiAliasing": 1,
        "motionBlur": False,
        "superSampling": 1,
        "description": "快速预览"
    },
    "preview_quality": {
        "format": "png",
        "bitDepth": 16,
        "compression": "default",
        "colorspace": "srgb",
        "antiAliasing": 2,
        "motionBlur": True,
        "motionBlurSamples": 4,
        "superSampling": 1,
        "description": "高质量预览"
    },
    "intermediate": {
        "format": "exr",
        "bitDepth": 16,
        "compression": "zip",
        "colorspace": "linear",
        "antiAliasing": 4,
        "motionBlur": True,
        "motionBlurSamples": 8,
        "superSampling": 2,
        "description": "中间文件"
    },
    "final_delivery": {
        "format": "exr",
        "bitDepth": 16,
        "compression": "piz",
        "colorspace": "acescg",
        "antiAliasing": 8,
        "motionBlur": True,
        "motionBlurSamples": 16,
        "superSampling": 4,
        "description": "最终交付"
    },
    "archival": {
        "format": "exr",
        "bitDepth": 32,
        "compression": "piz",
        "colorspace": "aces2065-1",
        "antiAliasing": 16,
        "motionBlur": True,
        "motionBlurSamples": 32,
        "superSampling": 8,
        "description": "存档质量"
    }
}

def apply_render_preset(output_node, preset_name):
    """应用渲染预设"""
    preset = RENDER_PRESETS.get(preset_name)
    if not preset:
        raise ValueError(f"未知预设: {preset_name}")
    
    for key, value in preset.items():
        if key == "description":
            continue
        prop = output_node.property(key)
        if prop:
            prop.setValue(value, 0)
    
    print(f"已应用渲染预设: {preset_name} - {preset.get('description', '')}")
    return output_node
```

## 7. 脚本化渲染

### 7.1 渲染函数

```python
def render_with_config(output_node, config, frame_range=None):
    """使用配置渲染"""
    # 应用配置
    configure_render_output(output_node, config)
    
    # 确定帧范围
    if frame_range is None:
        frame_range = (config.get("startFrame", 1), 
                       config.get("endFrame", 100))
    
    # 执行渲染
    print(f"开始渲染: {frame_range[0]}-{frame_range[1]}")
    render(output_node, frame_range[0], frame_range[1])
    print("渲染完成")
    
    return True
```

### 7.2 批量渲染

```python
def batch_render(render_tasks):
    """
    批量渲染
    render_tasks: [(output_node, config, frame_range), ...]
    """
    results = []
    
    for i, (output_node, config, frame_range) in enumerate(render_tasks):
        print(f"\n渲染任务 {i+1}/{len(render_tasks)}")
        
        try:
            render_with_config(output_node, config, frame_range)
            results.append({"status": "success", "task": i})
        except Exception as e:
            print(f"渲染失败: {e}")
            results.append({"status": "failed", "task": i, "error": str(e)})
    
    return results
```

### 7.3 渐进式渲染

```python
def progressive_render(output_node, frame_range, quality_stages=None):
    """
    渐进式渲染:先低质量全帧,再高质量
    """
    if quality_stages is None:
        quality_stages = ["draft", "preview", "standard", "high"]
    
    for stage in quality_stages:
        print(f"\n=== 渲染阶段: {stage} ===")
        apply_quality_preset(output_node, stage)
        render_with_config(output_node, {}, frame_range)
    
    print("渐进式渲染完成")
```

## 8. 最佳实践

### 8.1 渲染前检查

```python
def pre_render_check(output_node, frame_range, output_path):
    """渲染前检查"""
    checks = []
    
    # 检查输出节点连接
    if not output_node.inputs[0].isConnected():
        checks.append("✗ Output 节点未连接输入")
    else:
        checks.append("✓ Output 节点已连接")
    
    # 检查帧范围
    if frame_range[0] > frame_range[1]:
        checks.append("✗ 帧范围无效")
    else:
        total = frame_range[1] - frame_range[0] + 1
        checks.append(f"✓ 帧范围: {frame_range[0]}-{frame_range[1]} ({total}帧)")
    
    # 检查输出路径
    import os
    if not os.path.exists(output_path):
        os.makedirs(output_path)
        checks.append("✓ 创建输出目录")
    else:
        checks.append("✓ 输出目录存在")
    
    # 检查磁盘空间
    free_space = get_free_space(output_path)
    if free_space < 1024 * 1024 * 1024:
        checks.append("✗ 磁盘空间不足")
    else:
        checks.append(f"✓ 磁盘空间: {free_space / 1024**3:.1f}GB")
    
    return checks
```

### 8.2 渲染监控

```python
class RenderMonitor:
    """渲染监控"""
    
    def __init__(self):
        self.start_time = None
        self.frames_completed = 0
        self.total_frames = 0
    
    def start(self, total_frames):
        """开始监控"""
        import time
        self.start_time = time.time()
        self.total_frames = total_frames
        self.frames_completed = 0
    
    def update(self, frame):
        """更新进度"""
        self.frames_completed = frame
        self._print_progress()
    
    def _print_progress(self):
        """打印进度"""
        import time
        elapsed = time.time() - self.start_time
        progress = self.frames_completed / self.total_frames * 100
        
        if self.frames_completed > 0:
            eta = (elapsed / self.frames_completed) * \
                  (self.total_frames - self.frames_completed)
        else:
            eta = 0
        
        print(f"\r渲染: {self.frames_completed}/{self.total_frames} "
              f"({progress:.1f}%) | 用时: {elapsed:.0f}s | 剩余: {eta:.0f}s",
              end="")
    
    def summary(self):
        """输出摘要"""
        import time
        elapsed = time.time() - self.start_time
        print(f"\n\n渲染完成")
        print(f"总帧数: {self.total_frames}")
        print(f"总用时: {elapsed:.1f}s")
        print(f"平均: {elapsed/self.total_frames:.2f}s/帧")
```

### 8.3 错误处理

```python
def safe_render(output_node, start_frame, end_frame, max_retries=3):
    """安全的渲染(带重试)"""
    for attempt in range(max_retries):
        try:
            render(output_node, start_frame, end_frame)
            return True
        except MemoryError:
            print(f"内存不足,尝试 {attempt + 1}/{max_retries}")
            # 清理缓存
            clear_cache()
            # 减少缓存大小
            output_node.property("cacheSize").setValue(5, 0)
        except Exception as e:
            print(f"渲染错误: {e}")
            if attempt < max_retries - 1:
                print(f"重试 {attempt + 1}/{max_retries}")
                continue
            return False
    
    return False
```

### 8.4 输出验证

```python
def validate_render_output(output_path, expected_frames):
    """验证渲染输出"""
    import os
    
    issues = []
    
    # 检查文件数量
    files = [f for f in os.listdir(output_path) 
             if f.endswith((".exr", ".png", ".tif", ".dpx"))]
    
    if len(files) != expected_frames:
        issues.append(f"帧数不匹配: 期望 {expected_frames}, 实际 {len(files)}")
    
    # 检查缺失帧
    frame_nums = sorted(extract_frame_num(f) for f in files)
    expected_nums = list(range(1, expected_frames + 1))
    missing = set(expected_nums) - set(frame_nums)
    
    if missing:
        issues.append(f"缺失帧: {sorted(missing)}")
    
    # 检查文件大小
    for f in files:
        size = os.path.getsize(os.path.join(output_path, f))
        if size < 1000:
            issues.append(f"文件异常小: {f}")
    
    return issues
```

---

## 附录:渲染参数速查

### 质量与速度权衡

| 预设 | 质量 | 速度 | 文件大小 | 用途 |
|------|------|------|----------|------|
| draft | 低 | 最快 | 小 | 预览 |
| preview | 中 | 快 | 中 | 审核 |
| standard | 高 | 中 | 中 | 工作 |
| high | 很高 | 慢 | 大 | 交付 |
| final | 最高 | 最慢 | 大 | 存档 |

### 格式速查

| 用途 | 格式 | 位深 | 压缩 |
|------|------|------|------|
| 最终交付 | EXR | 16 | PIZ |
| 中间文件 | EXR/TIFF | 16 | ZIP |
| 预览 | PNG | 8 | 默认 |
| 视频 | MOV | - | ProRes |
| Web | MP4 | - | H.264 |

> **提示**:渲染前务必进行预检查,确认输出路径、磁盘空间和帧范围正确。大规模渲染时,建议先用 1-2 帧测试,确认效果后再全量渲染。
