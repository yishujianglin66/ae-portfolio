# Silhouette IO模块与文件操作

> 分类: API与参数手册
> 更新日期: 2026-07-11
> 概述: 包括文件读写、序列帧处理、EXR多通道IO、项目保存加载、数据序列化等文件操作

## 目录

- [一、IO 模块概述](#一io-模块概述)
- [二、文件读写操作](#二文件读写操作)
- [三、序列帧处理](#三序列帧处理)
- [四、EXR 多通道 IO](#四exr-多通道-io)
- [五、项目保存与加载](#五项目保存与加载)
- [六、数据序列化](#六数据序列化)
- [七、媒体素材加载](#七媒体素材加载)
- [八、路径处理工具](#八路径处理工具)
- [九、数据导出格式](#九数据导出格式)
- [十、最佳实践](#十最佳实践)

---

## 一、IO 模块概述

Silhouette 提供完整的文件 IO 能力，涵盖媒体素材、项目文件、跟踪数据、形状数据的读写。

### IO 能力分类

| 分类 | 说明 | 支持格式 |
|------|------|----------|
| 媒体加载 | 加载视频和图像序列 | mov, mp4, exr, tiff, png, dpx, jpg |
| 媒体输出 | 渲染输出图像序列 | exr, tiff, png, dpx, jpg |
| 项目文件 | 保存/加载完整项目 | sfx |
| 数据导出 | 导出跟踪/形状数据 | json, xml, aep, ma |
| 数据导入 | 导入外部数据 | json, xml, aep |

### 核心 IO 函数

| 函数 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `loadClip(path)` | path: str | Clip | 加载媒体素材 |
| `saveProject(path)` | path: str | None | 保存项目 |
| `loadProject(path)` | path: str | Project | 加载项目 |
| `importFile(path)` | path: str | None | 导入文件 |
| `exportData(node, path)` | node: Node, path: str | None | 导出节点数据 |

---

## 二、文件读写操作

### 2.1 Python 标准文件 IO

```python
# 文件读取
def read_text_file(path):
    """读取文本文件"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"[ERROR] 文件不存在: {path}")
        return None
    except Exception as e:
        print(f"[ERROR] 读取失败: {e}")
        return None

# 文件写入
def write_text_file(path, content):
    """写入文本文件"""
    try:
        # 确保目录存在
        import os
        dir_path = os.path.dirname(path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"[OK] 文件已保存: {path}")
        return True
    except Exception as e:
        print(f"[ERROR] 写入失败: {e}")
        return False

# 使用
content = read_text_file("D:/config/settings.txt")
write_text_file("D:/output/log.txt", "处理完成")
```

### 2.2 二进制文件 IO

```python
def read_binary_file(path):
    """读取二进制文件"""
    with open(path, "rb") as f:
        return f.read()

def write_binary_file(path, data):
    """写入二进制文件"""
    import os
    dir_path = os.path.dirname(path)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
```

### 2.3 文件信息查询

```python
import os

def get_file_info(path):
    """获取文件信息"""
    if not os.path.exists(path):
        return None

    stat = os.stat(path)
    return {
        "path": path,
        "size": stat.st_size,
        "size_mb": stat.st_size / (1024 * 1024),
        "modified": stat.st_mtime,
        "is_dir": os.path.isdir(path),
        "is_file": os.path.isfile(path),
        "extension": os.path.splitext(path)[1].lower(),
        "dirname": os.path.dirname(path),
        "basename": os.path.basename(path),
    }

# 使用
info = get_file_info("D:/footage/scene.mov")
if info:
    print(f"文件: {info['basename']}")
    print(f"大小: {info['size_mb']:.2f} MB")
    print(f"扩展名: {info['extension']}")
```

### 2.4 目录操作

```python
import os
import glob

def list_files(directory, pattern="*", recursive=False):
    """列出目录中的文件"""
    if recursive:
        search_pattern = os.path.join(directory, "**", pattern)
        return glob.glob(search_pattern, recursive=True)
    else:
        search_pattern = os.path.join(directory, pattern)
        return glob.glob(search_pattern)

def ensure_directory(path):
    """确保目录存在"""
    os.makedirs(path, exist_ok=True)
    return path

# 使用
files = list_files("D:/footage", "*.exr")
print(f"找到 {len(files)} 个 EXR 文件")

ensure_directory("D:/output/renders")
```

---

## 三、序列帧处理

### 3.1 序列帧路径格式

Silhouette 使用 `[####]` 或 `%04d` 格式表示序列帧。

| 格式 | 示例 | 说明 |
|------|------|------|
| `[####]` | `frame_[####].exr` | 4位数字补零 |
| `%04d` | `frame_%04d.exr` | C语言风格 |
| `####` | `frame_####.exr` | 无括号 |

### 3.2 序列帧路径工具

```python
import re
import os

def expand_frame_pattern(pattern, frame):
    """将序列帧模式展开为具体帧路径
    pattern: "D:/output/frame_[####].exr"
    frame: 42
    返回: "D:/output/frame_0042.exr"
    """
    # 匹配 [####] 格式
    match = re.search(r'\[(#+)\]', pattern)
    if match:
        num_hashes = len(match.group(1))
        frame_str = str(frame).zfill(num_hashes)
        return pattern.replace(f"[{match.group(1)}]", frame_str)

    # 匹配 %04d 格式
    match = re.search(r'%(\d+)d', pattern)
    if match:
        return pattern % frame

    # 匹配 #### 格式
    match = re.search(r'(?<!\[)(#+)(?!\])', pattern)
    if match:
        num_hashes = len(match.group(1))
        frame_str = str(frame).zfill(num_hashes)
        return pattern.replace(match.group(1), frame_str, 1)

    return pattern

def parse_frame_from_path(path):
    """从文件路径解析帧号"""
    import re

    # 尝试匹配数字序列
    match = re.search(r'(\d+)(?=\.\w+$)', path)
    if match:
        return int(match.group(1))
    return None

# 使用
pattern = "D:/output/frame_[####].exr"
for frame in [0, 1, 10, 100, 1000]:
    path = expand_frame_pattern(pattern, frame)
    print(f"帧 {frame}: {path}")
```

### 3.3 序列帧扫描

```python
import os
import re
import glob

def scan_sequence(directory, base_name, extension):
    """扫描目录中的序列帧"""
    pattern = os.path.join(directory, f"{base_name}*.{extension}")
    files = glob.glob(pattern)

    frames = []
    for f in files:
        frame = parse_frame_from_path(f)
        if frame is not None:
            frames.append((frame, f))

    frames.sort(key=lambda x: x[0])
    return frames

def get_sequence_info(directory, base_name, extension):
    """获取序列帧信息"""
    frames = scan_sequence(directory, base_name, extension)

    if not frames:
        return None

    frame_numbers = [f[0] for f in frames]

    # 检测是否有缺失帧
    min_frame = min(frame_numbers)
    max_frame = max(frame_numbers)
    expected_count = max_frame - min_frame + 1
    actual_count = len(frame_numbers)
    missing = expected_count - actual_count

    return {
        "directory": directory,
        "base_name": base_name,
        "extension": extension,
        "frame_start": min_frame,
        "frame_end": max_frame,
        "frame_count": actual_count,
        "missing_frames": missing,
        "is_complete": missing == 0,
        "files": [f[1] for f in frames],
    }

# 使用
info = get_sequence_info("D:/footage/renders", "comp_", "exr")
if info:
    print(f"序列: {info['frame_start']}-{info['frame_end']}")
    print(f"帧数: {info['frame_count']}")
    print(f"缺失: {info['missing_frames']}")
    print(f"完整: {info['is_complete']}")
```

### 3.4 序列帧验证

```python
def validate_sequence(directory, base_name, extension, expected_start, expected_end):
    """验证序列帧完整性"""
    info = get_sequence_info(directory, base_name, extension)

    if info is None:
        print(f"[ERROR] 未找到序列帧: {base_name}*.{extension}")
        return False

    issues = []

    if info["frame_start"] != expected_start:
        issues.append(f"起始帧不匹配: 期望 {expected_start}, 实际 {info['frame_start']}")

    if info["frame_end"] != expected_end:
        issues.append(f"结束帧不匹配: 期望 {expected_end}, 实际 {info['frame_end']}")

    if not info["is_complete"]:
        # 找出缺失的帧
        existing = set(info["frame_start"] + i
                       for i in range(info["frame_count"]))
        # 实际上需要重新计算
        actual_frames = set()
        for filepath in info["files"]:
            frame = parse_frame_from_path(filepath)
            if frame is not None:
                actual_frames.add(frame)

        expected_frames = set(range(expected_start, expected_end + 1))
        missing = sorted(expected_frames - actual_frames)
        issues.append(f"缺失帧: {missing[:10]}{'...' if len(missing) > 10 else ''}")

    if issues:
        print(f"[WARN] 序列帧问题:")
        for issue in issues:
            print(f"  - {issue}")
        return False
    else:
        print(f"[OK] 序列帧完整: {expected_start}-{expected_end} ({info['frame_count']}帧)")
        return True
```

---

## 四、EXR 多通道 IO

### 4.1 EXR 格式概述

OpenEXR 是视觉效果行业标准格式，支持高动态范围和多通道。

| 特性 | 说明 |
|------|------|
| 位深度 | 16位浮点(half), 32位浮点(float) |
| 通道 | RGB, RGBA, 任意命名通道 |
| 压缩 | None, ZIP, PIZ, RLE, DWAA, DWAB |
| 多层 | 支持多图层（Multi-part） |

### 4.2 EXR 通道配置

```python
from fx import *

def setup_exr_output(output_node, channels="rgba", compression="piz", depth="32f"):
    """配置 EXR 输出"""
    output_node.property("format").setValue("exr", 0)
    output_node.property("channels").setValue(channels, 0)
    output_node.property("compression").setValue(compression, 0)
    output_node.property("depth").setValue(depth, 0)

# 通道选项
# "rgb"    - 仅 RGB
# "rgba"   - RGB + Alpha
# "alpha"  - 仅 Alpha
# "aov"    - 任意输出变量（AOV）

# 压缩方式对比
COMPRESSION_INFO = {
    "none": {"ratio": "1:1", "speed": "快", "quality": "无损"},
    "rle": {"ratio": "2:1", "speed": "快", "quality": "无损"},
    "zip": {"ratio": "2.5:1", "speed": "中", "quality": "无损"},
    "piz": {"ratio": "3:1", "speed": "中", "quality": "无损"},
    "dwaa": {"ratio": "5:1", "speed": "慢", "quality": "有损"},
    "dwab": {"ratio": "10:1", "speed": "慢", "quality": "有损"},
}

for name, info in COMPRESSION_INFO.items():
    print(f"{name:6s}: 压缩比 {info['ratio']}, 速度 {info['speed']}, {info['quality']}")
```

### 4.3 多通道 EXR 写入

```python
from fx import *

def setup_multi_channel_output(output_node, channel_configs):
    """配置多通道 EXR 输出
    channel_configs: [
        {"name": "rgba", "channels": ["R", "G", "B", "A"]},
        {"name": "depth", "channels": ["Z"]},
        {"name": "motion", "channels": ["motion.X", "motion.Y"]},
    ]
    """
    output_node.property("format").setValue("exr", 0)
    output_node.property("channels").setValue("aov", 0)
    output_node.property("compression").setValue("piz", 0)
    output_node.property("depth").setValue("32f", 0)

    # 存储通道配置（供渲染时使用）
    print("[EXR] 多通道配置:")
    for cfg in channel_configs:
        print(f"  层 '{cfg['name']}': {cfg['channels']}")
```

### 4.4 EXR 元数据

```python
def setup_exr_metadata(output_node, metadata):
    """设置 EXR 元数据"""
    # 常用元数据字段
    default_metadata = {
        "software": "Silhouette 2026.0.2",
        "host": "Silhouette",
        "creationTime": None,  # 自动填充
        "displayWindow": None,  # 自动填充
        "pixelAspectRatio": 1.0,
        "screenWindowCenter": [0.0, 0.0],
        "screenWindowWidth": 1.0,
        "lineOrder": "INCREASING_Y",
    }

    default_metadata.update(metadata)

    print("[EXR] 元数据配置:")
    for key, value in default_metadata.items():
        if value is not None:
            print(f"  {key}: {value}")
```

---

## 五、项目保存与加载

### 5.1 项目文件格式

Silhouette 项目文件（.sfx）包含完整的节点图、形状、跟踪数据、动画等。

```python
from fx import *

def save_project_as(path):
    """另存项目"""
    proj = activeProject()
    if proj is None:
        print("[ERROR] 无活动项目")
        return False

    # 确保目录存在
    import os
    dir_path = os.path.dirname(path)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)

    proj.save(path)
    print(f"[OK] 项目已保存: {path}")
    return True

def open_project(path):
    """打开项目"""
    if not os.path.exists(path):
        print(f"[ERROR] 文件不存在: {path}")
        return None

    proj = Project.load(path)
    if proj:
        activate(proj)
        print(f"[OK] 项目已加载: {path}")
        print(f"  会话数: {proj.numItems}")
    return proj

# 使用
save_project_as("D:/projects/my_project.sfx")
open_project("D:/projects/my_project.sfx")
```

### 5.2 自动保存

```python
import os
import time
from fx import *

class AutoSaver:
    """自动保存管理器"""

    def __init__(self, interval=300, max_backups=5):
        self.interval = interval  # 秒
        self.max_backups = max_backups
        self.last_save = time.time()

    def check_and_save(self):
        """检查并执行自动保存"""
        now = time.time()
        if now - self.last_save < self.interval:
            return

        proj = activeProject()
        if proj is None or not proj.path:
            return

        # 创建备份路径
        backup_dir = os.path.join(os.path.dirname(proj.path), "backups")
        os.makedirs(backup_dir, exist_ok=True)

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"autosave_{timestamp}.sfx")

        proj.save(backup_path)
        self.last_save = now

        # 清理旧备份
        self.cleanup_backups(backup_dir)

        print(f"[AUTOSAVE] 已保存: {backup_path}")

    def cleanup_backups(self, backup_dir):
        """清理旧备份文件"""
        import glob
        backups = sorted(glob.glob(os.path.join(backup_dir, "autosave_*.sfx")))

        while len(backups) > self.max_backups:
            oldest = backups.pop(0)
            os.remove(oldest)
            print(f"[AUTOSAVE] 删除旧备份: {os.path.basename(oldest)}")

# 使用
saver = AutoSaver(interval=300, max_backups=5)
# 在事件回调中调用 saver.check_and_save()
```

---

## 六、数据序列化

### 6.1 JSON 序列化

```python
import json
import os

def save_json(data, path, indent=2):
    """保存数据为 JSON"""
    dir_path = os.path.dirname(path)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False, default=str)

    print(f"[OK] JSON 已保存: {path}")

def load_json(path):
    """加载 JSON 数据"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"[ERROR] 文件不存在: {path}")
        return None
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON 解析失败: {e}")
        return None
```

### 6.2 节点数据序列化

```python
from fx import *
import json

def serialize_node(node):
    """序列化节点为字典"""
    data = {
        "type": node.type,
        "label": node.label,
        "enabled": node.enabled,
        "properties": {}
    }

    # 序列化属性
    for name in node.properties:
        prop = node.property(name)
        prop_data = {
            "value": prop.value,
            "animated": prop.isAnimated,
        }

        # 序列化关键帧
        if prop.isAnimated:
            prop_data["keys"] = []
            for i in range(prop.numKeys):
                prop_data["keys"].append({
                    "frame": prop.keyTime(i),
                    "value": prop.keyValue(i),
                })

        data["properties"][name] = prop_data

    return data

def serialize_session(session):
    """序列化整个会话"""
    data = {
        "label": session.label,
        "width": session.width,
        "height": session.height,
        "frameRate": session.frameRate,
        "frameStart": session.frameStart,
        "frameEnd": session.frameEnd,
        "nodes": []
    }

    for i in range(session.numNodes):
        node = session.node(i)
        node_data = serialize_node(node)
        data["nodes"].append(node_data)

    return data

# 使用
session = activeSession()
if session:
    data = serialize_session(session)
    save_json(data, "D:/export/session_data.json")
```

### 6.3 反序列化与恢复

```python
from fx import *

def deserialize_node(session, node_data):
    """从字典反序列化节点"""
    node = Node(node_data["type"])
    node.label = node_data["label"]
    node.enabled = node_data.get("enabled", True)
    session.addNode(node)

    # 恢复属性
    for name, prop_data in node_data.get("properties", {}).items():
        if name in node.properties:
            prop = node.property(name)

            if prop_data.get("animated", False):
                # 恢复关键帧
                for key in prop_data.get("keys", []):
                    prop.setValue(key["value"], key["frame"])
            else:
                # 恢复静态值
                prop.setValue(prop_data["value"], 0)

    return node

def deserialize_session(session_data):
    """从字典反序列化会话"""
    session = Session()
    session.label = session_data["label"]
    session.width = session_data["width"]
    session.height = session_data["height"]
    session.frameRate = session_data["frameRate"]
    session.frameStart = session_data["frameStart"]
    session.frameEnd = session_data["frameEnd"]
    activate(session)

    # 恢复节点
    for node_data in session_data.get("nodes", []):
        deserialize_node(session, node_data)

    return session

# 使用
data = load_json("D:/export/session_data.json")
if data:
    session = deserialize_session(data)
    print(f"恢复会话: {session.label}, 节点数: {session.numNodes}")
```

---

## 七、媒体素材加载

### 7.1 加载素材

```python
from fx import *

def load_media(path):
    """加载媒体素材"""
    import os
    if not os.path.exists(path):
        print(f"[ERROR] 文件不存在: {path}")
        return None

    clip = loadClip(path)
    if clip:
        print(f"[OK] 素材已加载: {path}")
        print(f"  尺寸: {clip.width}x{clip.height}")
        print(f"  帧率: {clip.frameRate}")
        print(f"  帧范围: {clip.frameStart}-{clip.frameEnd}")
    return clip

# 使用
clip = load_media("D:/footage/scene.mov")
```

### 7.2 创建源节点

```python
from fx import *

def create_source_node(path, frame_rate=30.0):
    """创建源节点并加载素材"""
    src = Node("SourceNode")
    src.label = "Source"
    src.property("mediaPath").setValue(path.replace("\\", "/"), 0)
    src.property("frameRate").setValue(frame_rate, 0)

    # 自动获取帧范围
    clip = loadClip(path)
    if clip:
        src.property("frameStart").setValue(clip.frameStart, 0)
        src.property("frameEnd").setValue(clip.frameEnd, 0)
        print(f"[OK] 源节点创建: {clip.width}x{clip.height}, {clip.frameRate}fps")

    session.addNode(src)
    return src
```

### 7.3 支持的媒体格式

| 格式 | 扩展名 | 特点 |
|------|--------|------|
| QuickTime | .mov | 最常用，支持多种编码 |
| MP4 | .mp4 | 通用格式 |
| OpenEXR | .exr | HDR，多通道 |
| TIFF | .tif, .tiff | 无损，序列帧 |
| PNG | .png | 带Alpha |
| DPX | .dpx | 电影行业标准 |
| JPEG | .jpg | 有损压缩 |

---

## 八、路径处理工具

### 8.1 路径标准化

```python
import os

def normalize_path(path):
    """标准化路径"""
    # 统一路径分隔符
    path = path.replace("\\", "/")
    # 规范化
    path = os.path.normpath(path)
    # 再次统一为正斜杠
    path = path.replace("\\", "/")
    return path

def to_absolute_path(relative_path, base_dir=None):
    """转为绝对路径"""
    if os.path.isabs(relative_path):
        return normalize_path(relative_path)

    if base_dir is None:
        base_dir = os.getcwd()

    return normalize_path(os.path.join(base_dir, relative_path))

def get_relative_path(file_path, base_dir):
    """获取相对路径"""
    return os.path.relpath(file_path, base_dir)

# 使用
print(normalize_path("D:\\footage\\..\\output\\file.exr"))
# 输出: D:/output/file.exr
```

### 8.2 路径分析

```python
import os

def analyze_path(path):
    """分析路径组件"""
    normalized = normalize_path(path)
    dirname = os.path.dirname(normalized)
    basename = os.path.basename(normalized)
    name, ext = os.path.splitext(basename)

    return {
        "full_path": normalized,
        "directory": dirname,
        "filename": basename,
        "name": name,
        "extension": ext.lower(),
        "is_absolute": os.path.isabs(normalized),
    }

# 使用
info = analyze_path("D:/footage/scene_001.exr")
print(f"目录: {info['directory']}")
print(f"文件名: {info['filename']}")
print(f"名称: {info['name']}")
print(f"扩展名: {info['extension']}")
```

---

## 九、数据导出格式

### 9.1 跟踪数据导出

```python
import json
import os

def export_tracking_data_json(tracker_node, output_path):
    """导出跟踪数据为 JSON"""
    data = {
        "version": "1.0",
        "source": "silhouette",
        "tracker_node": tracker_node.label,
        "trackers": []
    }

    for i in range(tracker_node.numTrackers):
        t = tracker_node.tracker(i)
        tracker_data = {
            "name": t.name,
            "keyframes": []
        }

        for k in range(t.numKeys):
            pos = t.keyPosition(k)
            tracker_data["keyframes"].append({
                "frame": int(t.keyTime(k)),
                "x": pos[0],
                "y": pos[1],
            })

        data["trackers"].append(tracker_data)

    save_json(data, output_path)
    print(f"[EXPORT] 跟踪数据已导出: {output_path}")
    return output_path

def export_tracking_data_ae(tracker_node, output_path):
    """导出跟踪数据为 AE 格式"""
    data = {
        "version": "2.0",
        "source": "silhouette",
        "aeIntegration": {
            "exportFormat": "ae_keyframes",
            "nullObjectName": "Silhouette_Tracker",
        },
        "tracking": {"trackers": []}
    }

    for i in range(tracker_node.numTrackers):
        t = tracker_node.tracker(i)
        keyframes = []
        for k in range(t.numKeys):
            pos = t.keyPosition(k)
            keyframes.append({
                "frame": int(t.keyTime(k)),
                "x": pos[0],
                "y": pos[1],
            })
        data["tracking"]["trackers"].append({
            "name": t.name,
            "keyframes": keyframes
        })

    save_json(data, output_path)
    print(f"[EXPORT] AE跟踪数据已导出: {output_path}")
```

### 9.2 形状数据导出

```python
def export_shapes_json(roto_node, output_path):
    """导出形状数据为 JSON"""
    data = {
        "version": "1.0",
        "source": "silhouette",
        "node": roto_node.label,
        "shapes": []
    }

    for i in range(roto_node.numObjects):
        shape = roto_node.object(i)
        shape_data = {
            "name": shape.name,
            "type": shape.type,
            "closed": shape.closed,
            "feather": shape.feather,
            "blur": shape.blur,
            "opacity": shape.opacity,
            "inverted": shape.inverted,
            "points": []
        }

        for j in range(shape.numPoints):
            p = shape.point(j)
            shape_data["points"].append({
                "x": p.x,
                "y": p.y,
            })

        data["shapes"].append(shape_data)

    save_json(data, output_path)
    print(f"[EXPORT] 形状数据已导出: {output_path}")
    return data
```

### 9.3 综合导出

```python
def export_full_session(session, output_dir):
    """导出完整会话数据"""
    import os
    os.makedirs(output_dir, exist_ok=True)

    # 会话数据
    session_data = serialize_session(session)
    save_json(session_data, os.path.join(output_dir, "session.json"))

    # 各节点专用数据
    for i in range(session.numNodes):
        node = session.node(i)

        if node.type == "TrackerNode":
            export_tracking_data_json(
                node,
                os.path.join(output_dir, f"tracking_{node.label}.json")
            )

        elif node.type == "RotoNode":
            export_shapes_json(
                node,
                os.path.join(output_dir, f"shapes_{node.label}.json")
            )

    print(f"[EXPORT] 完整会话已导出到: {output_dir}")
```

---

## 十、最佳实践

### 10.1 文件路径安全

```python
import os

def safe_path(path):
    """安全路径处理"""
    # 统一分隔符
    path = path.replace("\\", "/")
    # 移除多余斜杠
    path = os.path.normpath(path)
    # 验证路径合法性
    try:
        os.path.normpath(path)
        return path
    except Exception:
        return None

def validate_output_path(path):
    """验证输出路径可写"""
    path = safe_path(path)
    if path is None:
        return False

    dir_path = os.path.dirname(path)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)

    # 测试写入权限
    try:
        test_file = os.path.join(dir_path, ".write_test")
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
        return True
    except PermissionError:
        print(f"[ERROR] 无写入权限: {dir_path}")
        return False
```

### 10.2 文件操作错误处理

```python
def safe_file_operation(operation, path, *args, **kwargs):
    """安全的文件操作包装"""
    try:
        return operation(path, *args, **kwargs)
    except FileNotFoundError:
        print(f"[ERROR] 文件不存在: {path}")
    except PermissionError:
        print(f"[ERROR] 无权限: {path}")
    except OSError as e:
        print(f"[ERROR] 系统错误: {e}")
    except Exception as e:
        print(f"[ERROR] 未知错误: {type(e).__name__}: {e}")
    return None
```

### 10.3 批量文件处理

```python
import os
import glob

def batch_process_sequences(base_dir, pattern="*.exr", process_func=None):
    """批量处理序列帧"""
    sequences = {}

    # 分组序列
    files = glob.glob(os.path.join(base_dir, "**", pattern), recursive=True)
    for filepath in files:
        dirname = os.path.dirname(filepath)
        basename = os.path.basename(filepath)

        # 提取基础名（去除帧号）
        import re
        base = re.sub(r'\d+(?=\.\w+$)', '', basename)
        key = os.path.join(dirname, base)

        if key not in sequences:
            sequences[key] = []
        sequences[key].append(filepath)

    # 处理每个序列
    for key, files in sequences.items():
        files.sort()
        print(f"[BATCH] 序列: {key} ({len(files)}帧)")
        if process_func:
            process_func(key, files)

    return sequences
```
