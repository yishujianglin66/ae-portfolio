# Silhouette 渲染引擎与输出系统

> 分类: API与参数手册
> 更新日期: 2026-07-11
> 概述: 包括渲染设置、输出格式、压缩方式、色彩空间、Alpha处理、帧范围控制等渲染输出完整指南

## 目录

- [一、渲染系统概述](#一渲染系统概述)
- [二、OutputNode 完全参数](#二outputnode-完全参数)
- [三、输出格式详解](#三输出格式详解)
- [四、压缩方式对比](#四压缩方式对比)
- [五、位深度与色彩](#五位深度与色彩)
- [六、色彩空间管理](#六色彩空间管理)
- [七、Alpha 通道处理](#七alpha-通道处理)
- [八、帧范围控制](#八帧范围控制)
- [九、渲染 API](#九渲染-api)
- [十、渲染优化与性能](#十渲染优化与性能)
- [十一、最佳实践](#十一最佳实践)

---

## 一、渲染系统概述

Silhouette 的渲染系统将节点图的处理结果输出为图像序列。

### 渲染流程

```
OutputNode 接收输入
       ↓
  帧范围遍历
       ↓
  逐帧求值节点图
       ↓
  色彩空间转换
       ↓
  Alpha 预乘处理
       ↓
  格式编码与压缩
       ↓
  写入文件
```

### 渲染类型

| 类型 | 说明 | 适用场景 |
|------|------|----------|
| 全量渲染 | 渲染整个帧范围 | 最终输出 |
| 预览渲染 | 低质量快速渲染 | 交互预览 |
| 单帧渲染 | 仅渲染当前帧 | 调试检查 |
| 区域渲染 | 渲染画面的局部区域 | 局部检查 |

---

## 二、OutputNode 完全参数

### 2.1 端口映射

| 方向 | 索引 | 名称 | 说明 |
|------|------|------|------|
| 输入 | 0 | input | 主输入（必须连接） |
| 输出 | - | - | 无输出端口（终端节点） |

### 2.2 完整属性表

| 属性名 | 类型 | 默认值 | 取值范围 | 说明 |
|--------|------|--------|----------|------|
| path | string | "" | 任意路径 | 输出路径（支持 [####]） |
| format | string | "exr" | exr/tiff/png/dpx/jpg | 输出格式 |
| compression | string | "none" | none/zip/piz/rle/dwaa/dwab | 压缩方式 |
| depth | string | "32f" | 8i/16i/16f/32f | 位深度 |
| channels | string | "rgba" | rgb/rgba/alpha/aov | 输出通道 |
| frameStart | int | 0 | 0 ~ 999999 | 起始帧 |
| frameEnd | int | 100 | 1 ~ 999999 | 结束帧 |
| frameRate | float | 24.0 | 1.0 ~ 120.0 | 输出帧率 |
| frameStep | int | 1 | 1 ~ 100 | 帧步长（隔帧渲染） |
| colorSpace | string | "linear" | linear/sRGB/Rec709/ACES | 输出色彩空间 |
| premultiply | bool | true | true/false | 预乘 Alpha |
| overwrite | bool | true | true/false | 覆盖已存在文件 |
| padding | int | 4 | 1 ~ 10 | 帧号补零位数 |

### 2.3 创建 OutputNode

```python
from fx import *

def create_output_node(output_path, format_type="exr", start=0, end=100):
    """创建标准输出节点"""
    out = Node("OutputNode")
    out.label = "Render_Output"

    # 基本设置
    out.property("path").setValue(output_path.replace("\\", "/"), 0)
    out.property("format").setValue(format_type, 0)
    out.property("frameStart").setValue(start, 0)
    out.property("frameEnd").setValue(end, 0)

    # 根据格式设置压缩
    if format_type == "exr":
        out.property("compression").setValue("piz", 0)
        out.property("depth").setValue("32f", 0)
    elif format_type == "tiff":
        out.property("compression").setValue("zip", 0)
        out.property("depth").setValue("16f", 0)
    elif format_type == "png":
        out.property("depth").setValue("8i", 0)
    elif format_type == "dpx":
        out.property("depth").setValue("16i", 0)

    session.addNode(out)
    return out
```

---

## 三、输出格式详解

### 3.1 格式对比表

| 格式 | 扩展名 | 位深度 | Alpha | 压缩 | 适用场景 |
|------|--------|--------|-------|------|----------|
| OpenEXR | .exr | 16f/32f | 完整支持 | 多种 | VFX标准，HDR合成 |
| TIFF | .tif | 8/16/32 | 完整支持 | LZW/ZIP | 印刷，高质量 |
| PNG | .png | 8/16 | 完整支持 | DEFLATE | Web，预览 |
| DPX | .dpx | 8/10/12/16 | 有限 | RLE | 电影后期 |
| JPEG | .jpg | 8 | 不支持 | 有损 | 预览参考 |

### 3.2 EXR 格式详解

```python
from fx import *

# EXR 是 VFX 行业的标准格式
out_exr = Node("OutputNode")
out_exr.property("format").setValue("exr", 0)
out_exr.property("compression").setValue("piz", 0)  # 无损压缩
out_exr.property("depth").setValue("32f", 0)         # 32位浮点
out_exr.property("channels").setValue("rgba", 0)     # RGBA四通道
out_exr.property("premultiply").setValue(True, 0)    # 预乘Alpha
out_exr.property("colorSpace").setValue("linear", 0) # 线性色彩空间
```

### 3.3 格式选择指南

| 使用场景 | 推荐格式 | 位深度 | 压缩 |
|----------|----------|--------|------|
| VFX最终输出 | EXR | 32f | piz |
| 中间合成 | EXR | 16f | zip |
| 调色参考 | TIFF | 16i | zip |
| 快速预览 | PNG | 8i | 默认 |
| Web分享 | JPG | 8i | 90% |
| 电影交付 | DPX | 10i | none |

### 3.4 多格式输出

```python
from fx import *

def setup_multi_format_output(input_node, base_path, formats):
    """设置多格式输出
    formats: ["exr", "tiff", "png"]
    """
    outputs = []

    for fmt in formats:
        out = Node("OutputNode")
        out.label = f"Output_{fmt.upper()}"

        # 路径
        path = f"{base_path}_{fmt}/render_[####].{fmt}"
        out.property("path").setValue(path, 0)
        out.property("format").setValue(fmt, 0)

        # 格式特定设置
        if fmt == "exr":
            out.property("compression").setValue("piz", 0)
            out.property("depth").setValue("32f", 0)
        elif fmt == "tiff":
            out.property("compression").setValue("zip", 0)
            out.property("depth").setValue("16f", 0)
        elif fmt == "png":
            out.property("depth").setValue("8i", 0)
        elif fmt == "jpg":
            out.property("depth").setValue("8i", 0)

        session.addNode(out)
        input_node.outputs[0].connect(out.inputs[0])
        outputs.append(out)

    return outputs
```

---

## 四、压缩方式对比

### 4.1 EXR 压缩方式

| 压缩方式 | 压缩比 | 速度 | 质量 | 适用场景 |
|----------|--------|------|------|----------|
| none | 1:1 | 最快 | 无损 | 临时缓存，SSD |
| rle | ~1.5:1 | 快 | 无损 | 简单图形 |
| zip | ~2.5:1 | 中 | 无损 | 通用推荐 |
| piz | ~3:1 | 中 | 无损 | 最佳无损选择 |
| dwaa | ~5:1 | 慢 | 有损 | 存档，网络传输 |
| dwab | ~10:1 | 慢 | 有损 | 高压缩需求 |

### 4.2 压缩选择建议

```python
from fx import *

def set_optimal_compression(output_node, use_case="standard"):
    """根据使用场景设置最优压缩"""
    compression_map = {
        "cache": "none",       # 临时缓存，速度优先
        "preview": "rle",      # 快速预览
        "standard": "zip",     # 通用场景
        "archival": "piz",     # 归档存储
        "network": "dwaa",     # 网络传输
        "max_compress": "dwab",# 最大压缩
    }

    comp = compression_map.get(use_case, "zip")
    output_node.property("compression").setValue(comp, 0)
    print(f"[RENDER] 压缩方式: {comp} (场景: {use_case})")
```

### 4.3 压缩性能测试

```python
import time
import os

def benchmark_compression(output_node, test_frames=10):
    """压缩方式性能基准测试"""
    results = []

    compressions = ["none", "rle", "zip", "piz", "dwaa", "dwab"]

    for comp in compressions:
        output_node.property("compression").setValue(comp, 0)

        start = time.time()
        # render(test_frames)  # 执行渲染
        elapsed = time.time() - start

        # 检查文件大小
        # file_size = os.path.getsize(output_path)

        results.append({
            "compression": comp,
            "time": elapsed,
            # "size_mb": file_size / (1024*1024)
        })

    # 输出报告
    print("=== 压缩性能基准 ===")
    print(f"{'压缩':8s} {'时间':>8s}")
    for r in results:
        print(f"{r['compression']:8s} {r['time']:7.2f}s")
```

---

## 五、位深度与色彩

### 5.1 位深度选项

| 深度字符串 | 说明 | 每通道位数 | 范围 | 适用场景 |
|-----------|------|-----------|------|----------|
| 8i | 8位整数 | 8 | 0-255 | 预览，Web |
| 16i | 16位整数 | 16 | 0-65535 | 视频，印刷 |
| 16f | 16位浮点 | 16 | -65504~65504 | 中间合成 |
| 32f | 32位浮点 | 32 | 极大范围 | VFX，HDR |

### 5.2 位深度选择

```python
from fx import *

def set_depth_for_use_case(output_node, use_case):
    """根据使用场景设置位深度"""
    depth_map = {
        "web_preview": "8i",      # Web预览
        "video_delivery": "16i",  # 视频交付
        "intermediate": "16f",    # 中间合成
        "vfx_final": "32f",       # VFX最终
        "hdr": "32f",             # HDR内容
    }

    depth = depth_map.get(use_case, "16f")
    output_node.property("depth").setValue(depth, 0)

    depth_info = {
        "8i": "8位整数 (0-255)",
        "16i": "16位整数 (0-65535)",
        "16f": "16位浮点 (HDR)",
        "32f": "32位浮点 (全HDR)",
    }
    print(f"[RENDER] 位深度: {depth} - {depth_info[depth]}")
```

### 5.3 文件大小估算

```python
def estimate_file_size(width, height, depth, channels=4, compression_ratio=1.0):
    """估算单帧文件大小（MB）"""
    bytes_per_channel = {
        "8i": 1,
        "16i": 2,
        "16f": 2,
        "32f": 4,
    }

    bpc = bytes_per_channel.get(depth, 2)
    uncompressed = width * height * channels * bpc
    compressed = uncompressed / compression_ratio
    return compressed / (1024 * 1024)

# 估算示例
sizes = {
    "1080p 8i": estimate_file_size(1920, 1080, "8i", 4, 2.5),
    "1080p 16f": estimate_file_size(1920, 1080, "16f", 4, 3.0),
    "1080p 32f": estimate_file_size(1920, 1080, "32f", 4, 3.0),
    "4K 32f": estimate_file_size(3840, 2160, "32f", 4, 3.0),
}

for label, size in sizes.items():
    print(f"{label}: {size:.1f} MB/帧")

# 序列总大小
total_frames = 240
for label, size in sizes.items():
    total = size * total_frames / 1024  # GB
    print(f"{label} x{total_frames}帧: {total:.1f} GB")
```

---

## 六、色彩空间管理

### 6.1 支持的色彩空间

| 色彩空间 | 说明 | 适用场景 |
|----------|------|----------|
| linear | 线性 | VFX合成（推荐） |
| sRGB | sRGB | 显示，Web |
| Rec709 | BT.709 | HDTV视频 |
| ACES | ACES2065-1 | 电影级工作流 |
| Rec2020 | BT.2020 | UHD/4K视频 |
| Gamma22 | Gamma 2.2 | 旧式视频 |

### 6.2 色彩空间配置

```python
from fx import *

def setup_color_management(output_node, working="linear", output="linear"):
    """配置色彩管理"""
    # 工作色彩空间（通常在项目级别设置）
    proj = activeProject()
    if proj:
        # 项目级色彩空间设置
        pass

    # 输出色彩空间
    output_node.property("colorSpace").setValue(output, 0)

    print(f"[COLOR] 工作空间: {working}")
    print(f"[COLOR] 输出空间: {output}")
```

### 6.3 色彩空间转换建议

| 源 | 目标 | 说明 |
|----|------|------|
| linear | linear | 无转换（VFX标准） |
| linear | sRGB | 输出Web预览 |
| linear | Rec709 | 输出视频 |
| sRGB | linear | 输入转工作空间 |
| Rec709 | linear | 视频素材转工作空间 |

---

## 七、Alpha 通道处理

### 7.1 预乘与非预乘

| 类型 | 说明 | 适用场景 |
|------|------|----------|
| 预乘 (Premultiplied) | RGB已乘以Alpha | EXR（默认），合成 |
| 非预乘 (Straight) | RGB与Alpha独立 | PNG，某些视频格式 |

### 7.2 Alpha 配置

```python
from fx import *

def setup_alpha_output(output_node, premultiply=True):
    """配置 Alpha 输出"""
    output_node.property("premultiply").setValue(premultiply, 0)

    if premultiply:
        print("[ALPHA] 预乘Alpha（合成推荐）")
    else:
        print("[ALPHA] 非预乘Alpha（Straight）")

# 格式默认值
ALPHA_DEFAULTS = {
    "exr": True,     # EXR 默认预乘
    "tiff": True,    # TIFF 通常预乘
    "png": False,    # PNG 通常非预乘
    "dpx": False,    # DPX 通常非预乘
    "jpg": None,     # JPG 无Alpha
}

def auto_set_alpha(output_node, format_type):
    """根据格式自动设置Alpha"""
    premult = ALPHA_DEFAULTS.get(format_type)
    if premult is not None:
        output_node.property("premultiply").setValue(premult, 0)
        print(f"[ALPHA] {format_type}: premultiply={premult}")
```

### 7.3 通道输出选项

```python
from fx import *

# 通道输出选项
CHANNEL_OPTIONS = {
    "rgb": "仅 RGB（无Alpha）",
    "rgba": "RGB + Alpha（完整）",
    "alpha": "仅 Alpha 遮罩",
    "aov": "任意输出变量（多层）",
}

def setup_channel_output(output_node, mode="rgba"):
    """配置通道输出"""
    output_node.property("channels").setValue(mode, 0)
    print(f"[CHANNEL] 输出模式: {mode} - {CHANNEL_OPTIONS[mode]}")

# 特殊用途
def output_alpha_only(output_node):
    """仅输出 Alpha 通道（用于遮罩交付）"""
    output_node.property("channels").setValue("alpha", 0)
    output_node.property("format").setValue("exr", 0)
    output_node.property("depth").setValue("32f", 0)
    print("[CHANNEL] 仅Alpha输出模式")
```

---

## 八、帧范围控制

### 8.1 帧范围参数

| 属性 | 说明 |
|------|------|
| frameStart | 起始帧号 |
| frameEnd | 结束帧号 |
| frameStep | 帧步长（隔帧渲染） |
| frameRate | 输出帧率 |

### 8.2 帧范围设置

```python
from fx import *

def set_frame_range(output_node, start, end, step=1, fps=24.0):
    """设置渲染帧范围"""
    output_node.property("frameStart").setValue(start, 0)
    output_node.property("frameEnd").setValue(end, 0)
    output_node.property("frameStep").setValue(step, 0)
    output_node.property("frameRate").setValue(fps, 0)

    actual_frames = (end - start) // step + 1
    print(f"[RENDER] 帧范围: {start}-{end}, 步长: {step}")
    print(f"[RENDER] 实际渲染: {actual_frames}帧, 帧率: {fps}fps")

# 完整渲染
set_frame_range(out, 0, 240, step=1, fps=24.0)

# 隔帧预览
set_frame_range(out, 0, 240, step=2, fps=24.0)  # 只渲染偶数帧

# 测试渲染
set_frame_range(out, 0, 10, step=1, fps=24.0)
```

### 8.3 从源节点自动获取帧范围

```python
def auto_frame_range(source_node, output_node, padding=0):
    """从源节点自动设置输出帧范围"""
    start = source_node.property("frameStart").value
    end = source_node.property("frameEnd").value

    # 可选：添加前后padding
    actual_start = max(0, start - padding)
    actual_end = end + padding

    output_node.property("frameStart").setValue(actual_start, 0)
    output_node.property("frameEnd").setValue(actual_end, 0)

    print(f"[RENDER] 自动帧范围: {actual_start}-{actual_end} (源: {start}-{end})")
```

---

## 九、渲染 API

### 9.1 渲染函数

| 函数 | 参数 | 说明 |
|------|------|------|
| `render(node, start, end)` | node, start: int, end: int | 渲染指定范围 |
| `renderSession(session, start, end)` | session, start, end | 渲染整个会话 |
| `renderFrame(node, frame)` | node, frame: int | 渲染单帧 |
| `stopRender()` | 无 | 停止渲染 |
| `isRendering` | 无 | 是否正在渲染 |

### 9.2 基本渲染

```python
from fx import *

# 渲染整个范围
def render_full(output_node):
    """渲染完整序列"""
    start = output_node.property("frameStart").value
    end = output_node.property("frameEnd").value

    print(f"[RENDER] 开始渲染: 帧 {start}-{end}")
    render(output_node, start, end)
    print("[RENDER] 渲染完成")

# 渲染单帧
def render_single_frame(output_node, frame):
    """渲染单帧（用于检查）"""
    print(f"[RENDER] 渲染单帧: {frame}")
    renderFrame(output_node, frame)

# 使用
render_full(out_node)
render_single_frame(out_node, 50)
```

### 9.3 渐进式渲染

```python
from fx import *

def progressive_render(output_node, total_start, total_end, batch_size=10):
    """分批渲染（避免内存问题）"""
    current = total_start

    while current <= total_end:
        batch_end = min(current + batch_size - 1, total_end)

        print(f"[RENDER] 批次: {current}-{batch_end}")

        # 临时修改帧范围
        output_node.property("frameStart").setValue(current, 0)
        output_node.property("frameEnd").setValue(batch_end, 0)

        render(output_node, current, batch_end)

        current = batch_end + 1

    print("[RENDER] 所有批次完成")
```

### 9.4 多输出渲染

```python
def render_multiple_outputs(output_nodes, start, end):
    """渲染多个输出节点"""
    for out_node in output_nodes:
        label = out_node.label
        print(f"\n[RENDER] 开始: {label}")

        try:
            render(out_node, start, end)
            print(f"[RENDER] 完成: {label}")
        except Exception as e:
            print(f"[RENDER] 失败: {label} - {e}")

    print("\n[RENDER] 所有输出完成")
```

---

## 十、渲染优化与性能

### 10.1 渲染优化检查表

```python
from fx import *
import os

def pre_render_checklist(output_node):
    """渲染前检查清单"""
    checks = []

    # 1. 检查路径
    path = output_node.property("path").value
    if not path:
        checks.append(("FAIL", "输出路径为空"))
    elif "[####]" not in path and "%04d" not in path:
        checks.append(("WARN", f"路径无帧号模式: {path}"))

    # 2. 检查输出目录
    dir_path = os.path.dirname(path.replace("[####]", "0000"))
    if dir_path and not os.path.exists(dir_path):
        try:
            os.makedirs(dir_path, exist_ok=True)
            checks.append(("OK", f"创建输出目录: {dir_path}"))
        except:
            checks.append(("FAIL", f"无法创建目录: {dir_path}"))

    # 3. 检查输入连接
    if not output_node.inputs[0].isConnected():
        checks.append(("FAIL", "输入未连接"))
    else:
        source = output_node.inputs[0].source
        checks.append(("OK", f"输入源: {source.label}"))

    # 4. 检查帧范围
    start = output_node.property("frameStart").value
    end = output_node.property("frameEnd").value
    if end <= start:
        checks.append(("FAIL", f"帧范围无效: {start}-{end}"))
    else:
        checks.append(("OK", f"帧范围: {start}-{end} ({end-start+1}帧)"))

    # 5. 检查格式设置
    fmt = output_node.property("format").value
    depth = output_node.property("depth").value
    comp = output_node.property("compression").value
    checks.append(("INFO", f"格式: {fmt}, 深度: {depth}, 压缩: {comp}"))

    # 输出报告
    print("\n=== 渲染前检查 ===")
    for status, msg in checks:
        icon = {"OK": "[OK]", "WARN": "[!]", "FAIL": "[X]", "INFO": "[i]"}[status]
        print(f"  {icon} {msg}")

    failures = [c for c in checks if c[0] == "FAIL"]
    return len(failures) == 0

# 使用
if pre_render_checklist(out_node):
    print("\n[READY] 可以开始渲染")
else:
    print("\n[BLOCKED] 请修复上述问题")
```

### 10.2 性能优化建议

| 优化项 | 建议 | 效果 |
|--------|------|------|
| 帧步长 | 预览时 step=2 或 4 | 渲染量减半 |
| 位深度 | 预览用 8i，最终用 32f | 速度4倍 |
| 压缩 | 预览用 none，最终用 piz | 速度提升 |
| 分辨率 | 预览用 50% 分辨率 | 速度4倍 |
| Tile大小 | 大画幅用 512 | 内存优化 |
| 渲染线程 | 设为 CPU核心-2 | 平衡系统响应 |

### 10.3 渲染时间估算

```python
import time

def estimate_render_time(output_node, sample_frames=5):
    """通过采样帧估算总渲染时间"""
    start = output_node.property("frameStart").value
    end = output_node.property("frameEnd").value
    total_frames = end - start + 1

    # 采样渲染
    step = max(1, total_frames // sample_frames)
    sample_times = []

    for f in range(start, end + 1, step):
        t0 = time.time()
        # renderFrame(output_node, f)  # 实际渲染
        elapsed = time.time() - t0
        sample_times.append(elapsed)
        print(f"  采样帧 {f}: {elapsed:.2f}秒")

    if not sample_times:
        return 0

    avg_time = sum(sample_times) / len(sample_times)
    estimated_total = avg_time * total_frames

    print(f"\n=== 渲染时间估算 ===")
    print(f"总帧数: {total_frames}")
    print(f"平均每帧: {avg_time:.2f}秒")
    print(f"预计总时间: {estimated_total:.0f}秒 ({estimated_total/60:.1f}分钟)")
    print(f"预计完成时间: {time.ctime(time.time() + estimated_total)}")

    return estimated_total
```

---

## 十一、最佳实践

### 11.1 标准渲染模板

```python
from fx import *

def standard_render_setup(input_node, output_path, frame_range, quality="high"):
    """标准渲染设置模板"""
    out = Node("OutputNode")
    out.label = "Final_Render"

    # 路径
    out.property("path").setValue(output_path.replace("\\", "/"), 0)

    # 质量预设
    QUALITY_PRESETS = {
        "low": {
            "format": "jpg", "depth": "8i", "compression": "none",
        },
        "medium": {
            "format": "png", "depth": "8i", "compression": "none",
        },
        "high": {
            "format": "exr", "depth": "16f", "compression": "zip",
        },
        "production": {
            "format": "exr", "depth": "32f", "compression": "piz",
        },
    }

    preset = QUALITY_PRESETS.get(quality, QUALITY_PRESETS["high"])
    for prop, value in preset.items():
        out.property(prop).setValue(value, 0)

    # 帧范围
    out.property("frameStart").setValue(frame_range[0], 0)
    out.property("frameEnd").setValue(frame_range[1], 0)

    # 通用设置
    out.property("channels").setValue("rgba", 0)
    out.property("premultiply").setValue(True, 0)
    out.property("colorSpace").setValue("linear", 0)
    out.property("overwrite").setValue(True, 0)

    session.addNode(out)
    input_node.outputs[0].connect(out.inputs[0])

    print(f"[RENDER] 渲染设置完成 (质量: {quality})")
    print(f"  格式: {preset['format']}, 深度: {preset['depth']}")
    print(f"  帧范围: {frame_range[0]}-{frame_range[1]}")

    return out

# 使用
out = standard_render_setup(
    roto,
    "D:/output/final_[####].exr",
    (0, 240),
    quality="production"
)
```

### 11.2 渲染队列管理

```python
import os

class RenderQueue:
    """渲染队列管理器"""

    def __init__(self):
        self.queue = []
        self.completed = []
        self.failed = []

    def add(self, output_node, start_frame, end_frame, label=""):
        """添加渲染任务"""
        task = {
            "node": output_node,
            "start": start_frame,
            "end": end_frame,
            "label": label or output_node.label,
            "status": "pending",
        }
        self.queue.append(task)
        print(f"[QUEUE] 添加任务: {task['label']} ({start_frame}-{end_frame})")

    def process(self):
        """处理渲染队列"""
        print(f"\n[QUEUE] 开始处理 {len(self.queue)} 个任务")

        for i, task in enumerate(self.queue):
            print(f"\n[QUEUE] 任务 {i+1}/{len(self.queue)}: {task['label']}")

            try:
                render(task["node"], task["start"], task["end"])
                task["status"] = "completed"
                self.completed.append(task)
                print(f"[QUEUE] 完成: {task['label']}")
            except Exception as e:
                task["status"] = "failed"
                task["error"] = str(e)
                self.failed.append(task)
                print(f"[QUEUE] 失败: {task['label']} - {e}")

        # 汇总报告
        print(f"\n=== 渲染队列报告 ===")
        print(f"总计: {len(self.queue)}")
        print(f"成功: {len(self.completed)}")
        print(f"失败: {len(self.failed)}")

        if self.failed:
            print("\n失败任务:")
            for task in self.failed:
                print(f"  - {task['label']}: {task.get('error', '未知错误')}")

# 使用
queue = RenderQueue()
queue.add(out_exr, 0, 240, "EXR输出")
queue.add(out_png, 0, 240, "PNG预览")
queue.process()
```

### 11.3 完整渲染工作流

```python
from fx import *
import os
import time

def complete_render_workflow(source_path, output_dir, frame_range, quality="production"):
    """完整渲染工作流"""
    print("=" * 60)
    print("[WORKFLOW] 开始完整渲染工作流")
    print("=" * 60)

    start_time = time.time()

    # 1. 项目与会话
    proj = activeProject() or Project()
    activate(proj)
    session = activeSession() or Session()
    session.label = "Render_Workflow"
    activate(session)
    proj.addItem(session)

    # 2. 创建节点链
    src = Node("SourceNode")
    src.property("mediaPath").setValue(source_path.replace("\\", "/"), 0)
    session.addNode(src)

    roto = Node("RotoNode")
    roto.label = "Main_Roto"
    session.addNode(roto)

    out = Node("OutputNode")
    out.label = "Final_Output"
    session.addNode(out)

    # 3. 连接
    src.outputs[0].connect(roto.inputs[1])
    roto.outputs[0].connect(out.inputs[0])

    # 4. 配置输出
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "render_[####].exr").replace("\\", "/")

    out = standard_render_setup(roto, output_path, frame_range, quality)

    # 5. 渲染前检查
    if not pre_render_checklist(out):
        print("[WORKFLOW] 渲染前检查未通过，终止")
        return False

    # 6. 执行渲染
    print(f"\n[WORKFLOW] 开始渲染...")
    render(out, frame_range[0], frame_range[1])

    # 7. 验证输出
    from_fx_module_verify_output(output_dir, frame_range)

    elapsed = time.time() - start_time
    print(f"\n[WORKFLOW] 完成，总耗时: {elapsed:.1f}秒")
    print("=" * 60)

    return True

def from_fx_module_verify_output(output_dir, frame_range):
    """验证渲染输出"""
    import glob
    import os

    files = glob.glob(os.path.join(output_dir, "*.exr"))
    expected = frame_range[1] - frame_range[0] + 1
    actual = len(files)

    if actual == expected:
        print(f"[VERIFY] 输出完整: {actual}/{expected} 帧")
    else:
        print(f"[VERIFY] 帧数不匹配: 期望 {expected}, 实际 {actual}")

# 使用
complete_render_workflow(
    "D:/footage/scene.mov",
    "D:/output/renders",
    (0, 240),
    quality="production"
)
```
