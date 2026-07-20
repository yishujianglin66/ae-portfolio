# Silhouette 跟踪数据导出与格式转换

> 分类: 跟踪技术专题
> 更新日期: 2026-07-11
> 概述: 跟踪数据导出完整指南，涵盖AE/NUKE/Mocha格式导出、数据结构规范、坐标系转换与跨软件集成。

## 目录
1. [导出概述](#一导出概述)
2. [数据结构规范](#二数据结构规范)
3. [AE 格式导出](#三ae-格式导出)
4. [NUKE 格式导出](#四nuke-格式导出)
5. [Mocha 格式导出](#五mocha-格式导出)
6. [坐标系转换](#六坐标系转换)
7. [通用 JSON 导出](#七通用-json-导出)
8. [跨软件集成](#八跨软件集成)

---

## 一、导出概述

### 1.1 导出场景

Silhouette 跟踪数据需导出到其他软件进行后续应用：

| 目标软件 | 主要用途 | 推荐格式 |
|----------|----------|----------|
| After Effects | 合成、稳定化、屏幕替换 | AE 关键帧 / JSON |
| NUKE | 节点合成、3D 跟踪 | NUKE track / .nk |
| Mocha | 跟踪数据交换 | Mocha 数据 |
| Boujou/3DE | 摄像机解算 | 3D track 点 |
| Flame | 合成 | ASE / JSON |

### 1.2 导出原则

1. **保真性**：导出数据应完全反映原始跟踪结果
2. **可逆性**：保留足够信息支持反向工程
3. **标准化**：遵循目标软件的数据格式规范
4. **元数据完整**：包含帧率、分辨率、坐标系等元信息

---

## 二、数据结构规范

### 2.1 通用跟踪数据结构

```python
tracking_data = {
    "version": "2026.0.2",
    "source": "D:/footage/scene.mov",
    "track_type": "planar",  # planar / point
    "motion_model": "perspective",
    "fps": 24.0,
    "resolution": [1920, 1080],
    "frame_range": [0, 120],
    "coordinate_system": "top_left",  # top_left / bottom_left
    "frames": [
        {
            "frame": 0,
            "transform": {
                "translate": [0.0, 0.0],
                "rotate": 0.0,
                "scale": [1.0, 1.0],
                "perspective": [[1,0,0],[0,1,0],[0,0,1]]
            },
            "corners": [
                [100.0, 100.0],
                [200.0, 100.0],
                [200.0, 200.0],
                [100.0, 200.0]
            ]
        }
    ],
    "trackers": []  # 点跟踪数据
}
```

### 2.2 点跟踪数据结构

```python
point_track_data = {
    "version": "2026.0.2",
    "track_type": "point",
    "fps": 24.0,
    "resolution": [1920, 1080],
    "point_count": 4,
    "points": [
        {
            "id": "P1",
            "label": "TopLeft",
            "frames": [
                {"frame": 0, "x": 100.0, "y": 200.0},
                {"frame": 1, "x": 101.2, "y": 200.5}
            ]
        },
        {
            "id": "P2",
            "label": "TopRight",
            "frames": []
        }
    ]
}
```

### 2.3 元数据规范

| 字段 | 类型 | 说明 |
|------|------|------|
| version | string | Silhouette 版本 |
| source | string | 源素材路径 |
| track_type | string | 跟踪类型 |
| fps | float | 帧率 |
| resolution | [int, int] | 分辨率 [width, height] |
| frame_range | [int, int] | 帧范围 [start, end] |
| coordinate_system | string | 坐标系原点位置 |

---

## 三、AE 格式导出

### 3.1 AE 关键帧格式

After Effects 接受的关键帧格式：

```javascript
// AE 关键帧数据结构
{
    "nullObjectName": "Silhouette_Tracker",
    "fps": 24.0,
    "keyframes": {
        "Position": [
            {"time": 0.0, "value": [100.0, 200.0]},
            {"time": 0.0417, "value": [101.2, 200.5]}
        ],
        "Scale": [
            {"time": 0.0, "value": [100.0, 100.0]}
        ],
        "Rotation": [
            {"time": 0.0, "value": 0.0}
        ]
    }
}
```

### 3.2 导出脚本

```python
from fx import *
import json
import os
import math

def export_to_ae(track_node, output_path, fps=24.0):
    """导出跟踪数据为 AE 关键帧格式"""

    ae_data = {
        "version": "2.0",
        "source": "silhouette",
        "nullObjectName": "Silhouette_Tracker",
        "fps": fps,
        "keyframes": {
            "Position": [],
            "Scale": [],
            "Rotation": []
        }
    }

    # 遍历所有帧提取跟踪数据
    frame_start = 0
    frame_end = 120  # 实际应从 session 获取

    for frame in range(frame_start, frame_end + 1):
        time_sec = frame / fps

        # 获取变换数据（伪代码，实际通过 API 获取）
        translate = track_node.property("transform.translate").getValue(frame)
        rotate = track_node.property("transform.rotate").getValue(frame)
        scale = track_node.property("transform.scale").getValue(frame)

        ae_data["keyframes"]["Position"].append({
            "time": time_sec,
            "value": [translate[0], translate[1]]
        })
        ae_data["keyframes"]["Rotation"].append({
            "time": time_sec,
            "value": rotate
        })
        ae_data["keyframes"]["Scale"].append({
            "time": time_sec,
            "value": [scale[0] * 100, scale[1] * 100]  # AE 缩放为百分比
        })

    # 写入文件
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(ae_data, f, indent=2, ensure_ascii=False)

    print(f"[SILHOUETTE] AE export completed: {output_path}")
    return output_path


def export_corner_pin_to_ae(track_node, output_path, fps=24.0):
    """导出四点跟踪数据为 AE Corner Pin 效果"""

    corner_pin_data = {
        "version": "2.0",
        "effect": "Corner Pin",
        "fps": fps,
        "keyframes": {
            "TopLeft": [],
            "TopRight": [],
            "BottomRight": [],
            "BottomLeft": []
        }
    }

    frame_start = 0
    frame_end = 120

    for frame in range(frame_start, frame_end + 1):
        time_sec = frame / fps
        corners = track_node.property("corners").getValue(frame)

        corner_pin_data["keyframes"]["TopLeft"].append({
            "time": time_sec,
            "value": corners[0]
        })
        corner_pin_data["keyframes"]["TopRight"].append({
            "time": time_sec,
            "value": corners[1]
        })
        corner_pin_data["keyframes"]["BottomRight"].append({
            "time": time_sec,
            "value": corners[2]
        })
        corner_pin_data["keyframes"]["BottomLeft"].append({
            "time": time_sec,
            "value": corners[3]
        })

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(corner_pin_data, f, indent=2, ensure_ascii=False)

    print(f"[SILHOUETTE] AE Corner Pin export completed: {output_path}")
    return output_path
```

### 3.3 AE 端应用脚本

```javascript
// 在 AE 中应用跟踪数据
var trackerData = JSON.parse(File("D:/output/ae_track.json").read());

var nullObj = comp.layers.addNull();
nullObj.name = trackerData.nullObjectName;

var pos = nullObj.property("ADBE Transform Group").property("ADBE Position");
var rot = nullObj.property("ADBE Transform Group").property("ADBE Rotate Z");
var scale = nullObj.property("ADBE Transform Group").property("ADBE Scale");

// 应用位置关键帧
for (var i = 0; i < trackerData.keyframes.Position.length; i++) {
    var key = trackerData.keyframes.Position[i];
    pos.setValueAtTime(key.time, key.value);
}

// 应用旋转关键帧
for (var i = 0; i < trackerData.keyframes.Rotation.length; i++) {
    var key = trackerData.keyframes.Rotation[i];
    rot.setValueAtTime(key.time, key.value);
}

// 应用缩放关键帧
for (var i = 0; i < trackerData.keyframes.Scale.length; i++) {
    var key = trackerData.keyframes.Scale[i];
    scale.setValueAtTime(key.time, key.value);
}
```

---

## 四、NUKE 格式导出

### 4.1 NUKE track 文件格式

NUKE 接受的跟踪文件格式（.nk 片段）：

```
Tracker4 {
 track1 {{100 200} {101 200.5} {102 201}}
 track2 {{300 200} {301 200.5} {302 201}}
}
```

### 4.2 导出脚本

```python
def export_to_nuke(track_node, output_path, fps=24.0):
    """导出跟踪数据为 NUKE 格式"""

    nuke_data = {
        "version": "2026.0.2",
        "node_type": "Tracker4",
        "fps": fps,
        "tracks": []
    }

    # 假设多点跟踪
    point_count = 4
    frame_start = 0
    frame_end = 120

    for point_idx in range(point_count):
        track_points = {
            "id": f"track{point_idx + 1}",
            "label": f"Point_{point_idx + 1}",
            "frames": []
        }

        for frame in range(frame_start, frame_end + 1):
            point = track_node.property(f"point{point_idx}.position").getValue(frame)
            track_points["frames"].append({
                "frame": frame,
                "x": point[0],
                "y": point[1]
            })

        nuke_data["tracks"].append(track_points)

    # 生成 NUKE 脚本格式
    nuke_script = generate_nuke_script(nuke_data)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(nuke_script)

    print(f"[SILHOUETTE] NUKE export completed: {output_path}")
    return output_path


def generate_nuke_script(data):
    """生成 NUKE 脚本"""
    lines = ["Tracker4 {"]

    for track in data["tracks"]:
        track_name = track["id"]
        points_str = " ".join([f"{{{p['x']} {p['y']}}}" for p in track["frames"]])
        lines.append(f" {track_name} {{{points_str}}}")

    lines.append("}")
    return "\n".join(lines)
```

### 4.3 NUKE 端导入

在 NUKE 中导入跟踪数据：
1. 创建 Tracker4 节点
2. 右键 → Import Track Data
3. 选择导出的 .nk 文件

---

## 五、Mocha 格式导出

### 5.1 Mocha 数据格式

Mocha 使用 XML 格式存储跟踪数据：

```xml
<?xml version="1.0"?>
<mochaData>
  <tracks>
    <track name="Layer_1">
      <frame id="0" x="100.0" y="200.0"/>
      <frame id="1" x="101.2" y="200.5"/>
    </track>
  </tracks>
</mochaData>
```

### 5.2 导出脚本

```python
def export_to_mocha(track_node, output_path, fps=24.0):
    """导出跟踪数据为 Mocha XML 格式"""

    mocha_xml = ['<?xml version="1.0"?>']
    mocha_xml.append('<mochaData>')
    mocha_xml.append(f'  <metadata fps="{fps}"/>')
    mocha_xml.append('  <tracks>')

    frame_start = 0
    frame_end = 120

    # 假设单层平面跟踪
    mocha_xml.append('    <track name="Silhouette_Layer">')
    for frame in range(frame_start, frame_end + 1):
        corners = track_node.property("corners").getValue(frame)
        # Mocha 使用四角点
        mocha_xml.append(
            f'      <frame id="{frame}" '
            f'x="{corners[0][0]}" y="{corners[0][1]}" '
            f'x2="{corners[1][0]}" y2="{corners[1][1]}" '
            f'x3="{corners[2][0]}" y3="{corners[2][1]}" '
            f'x4="{corners[3][0]}" y4="{corners[3][1]}"/>'
        )
    mocha_xml.append('    </track>')

    mocha_xml.append('  </tracks>')
    mocha_xml.append('</mochaData>')

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(mocha_xml))

    print(f"[SILHOUETTE] Mocha export completed: {output_path}")
    return output_path
```

---

## 六、坐标系转换

### 6.1 坐标系差异

不同软件使用不同的坐标系原点：

| 软件 | 坐标系原点 | Y 轴方向 |
|------|-----------|----------|
| Silhouette | 左上角 | Y 向下 |
| After Effects | 左上角 | Y 向下 |
| NUKE | 左下角 | Y 向上 |
| Mocha | 左上角 | Y 向下 |
| 3D 软件 | 中心点 | Y 向上 |

### 6.2 转换公式

**Silhouette → NUKE（Y 翻转）**：
```python
def sil_to_nuke(x, y, height):
    """Silhouette 坐标转 NUKE 坐标"""
    nuke_x = x
    nuke_y = height - y
    return [nuke_x, nuke_y]
```

**Silhouette → 3D（中心化 + Y 翻转）**：
```python
def sil_to_3d(x, y, width, height):
    """Silhouette 坐标转 3D 中心坐标"""
    center_x = x - width / 2
    center_y = height / 2 - y
    return [center_x, center_y]
```

**归一化坐标**：
```python
def normalize_coord(x, y, width, height):
    """归一化到 [0, 1] 范围"""
    return [x / width, y / height]
```

### 6.3 批量转换

```python
def convert_track_coordinates(track_data, target_system, width, height):
    """批量转换跟踪数据坐标系"""

    if target_system == "nuke":
        for frame_data in track_data["frames"]:
            for i, corner in enumerate(frame_data["corners"]):
                frame_data["corners"][i] = [
                    corner[0],
                    height - corner[1]
                ]
        track_data["coordinate_system"] = "bottom_left"

    elif target_system == "normalized":
        for frame_data in track_data["frames"]:
            for i, corner in enumerate(frame_data["corners"]):
                frame_data["corners"][i] = [
                    corner[0] / width,
                    corner[1] / height
                ]
        track_data["coordinate_system"] = "normalized"

    return track_data
```

---

## 七、通用 JSON 导出

### 7.1 完整导出脚本

```python
from fx import *
import json
import os

def export_to_json(track_node, output_path, source_path, fps=24.0,
                   width=1920, height=1080, frame_range=[0, 120]):
    """导出完整跟踪数据为 JSON"""

    tracking_data = {
        "version": "2026.0.2",
        "source": source_path.replace("\\", "/"),
        "track_type": track_node.property("trackType").getValue(0),
        "motion_model": track_node.property("motionModel").getValue(0),
        "fps": fps,
        "resolution": [width, height],
        "frame_range": frame_range,
        "coordinate_system": "top_left",
        "search_area": track_node.property("searchArea").getValue(0),
        "accuracy": track_node.property("accuracy").getValue(0),
        "pattern_size": track_node.property("patternSize").getValue(0),
        "frames": [],
        "export_timestamp": "2026-07-11"
    }

    frame_start, frame_end = frame_range

    for frame in range(frame_start, frame_end + 1):
        frame_data = {
            "frame": frame,
            "time": frame / fps,
            "transform": {
                "translate": [0.0, 0.0],
                "rotate": 0.0,
                "scale": [1.0, 1.0]
            },
            "corners": []
        }

        # 获取变换数据
        try:
            translate = track_node.property("transform.translate").getValue(frame)
            frame_data["transform"]["translate"] = list(translate)
        except:
            pass

        try:
            rotate = track_node.property("transform.rotate").getValue(frame)
            frame_data["transform"]["rotate"] = rotate
        except:
            pass

        try:
            scale = track_node.property("transform.scale").getValue(frame)
            frame_data["transform"]["scale"] = list(scale)
        except:
            pass

        # 获取四角点
        try:
            corners = track_node.property("corners").getValue(frame)
            frame_data["corners"] = [list(c) for c in corners]
        except:
            pass

        tracking_data["frames"].append(frame_data)

    # 写入文件
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(tracking_data, f, indent=2, ensure_ascii=False)

    print(f"[SILHOUETTE] JSON export completed: {output_path}")
    print(f"[SILHOUETTE] Total frames: {len(tracking_data['frames'])}")
    return output_path
```

### 7.2 验证脚本

```python
def validate_track_data(json_path):
    """验证导出的跟踪数据完整性"""

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    issues = []

    # 检查必需字段
    required_fields = ["version", "source", "track_type", "fps", "frames"]
    for field in required_fields:
        if field not in data:
            issues.append(f"缺少必需字段: {field}")

    # 检查帧数据
    if "frames" in data:
        frame_range = data.get("frame_range", [0, 0])
        expected_count = frame_range[1] - frame_range[0] + 1
        actual_count = len(data["frames"])
        if actual_count != expected_count:
            issues.append(f"帧数不匹配: 期望 {expected_count}, 实际 {actual_count}")

    # 检查坐标有效性
    for frame_data in data.get("frames", []):
        for corner in frame_data.get("corners", []):
            if len(corner) != 2:
                issues.append(f"帧 {frame_data['frame']} 角点坐标格式错误")
                break

    if issues:
        print("[SILHOUETTE] 验证发现问题:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("[SILHOUETTE] 数据验证通过")

    return issues
```

---

## 八、跨软件集成

### 8.1 集成工作流

```
Silhouette 跟踪 → 导出 JSON / 专用格式
                → 传输到目标软件
                → 目标软件导入并应用
                → 验证应用效果
                → 必要时回传修正
```

### 8.2 与 AE 集成

**步骤**：
1. 在 Silhouette 完成跟踪
2. 导出 AE 关键帧 JSON
3. 在 AE 中运行导入脚本
4. 创建 Null 对象并应用关键帧
5. 将目标图层父级链接到 Null

### 8.3 与 NUKE 集成

**步骤**：
1. 在 Silhouette 完成多点跟踪
2. 导出 NUKE track 文件
3. 在 NUKE 中创建 Tracker4 节点
4. 导入跟踪数据
5. 使用 match-move 节点应用跟踪

### 8.4 多软件协同

对于需要多软件协作的复杂项目：

1. **统一 JSON 中间格式**：所有软件通过 JSON 交换
2. **坐标系标注**：明确标注每份数据的坐标系
3. **版本控制**：对跟踪数据进行版本管理
4. **验证流程**：每次传输后验证数据完整性

### 8.5 注意事项

- 帧率必须一致（如 24fps 与 30fps 不匹配会导致时序错乱）
- 分辨率必须一致（或进行坐标缩放）
- 坐标系必须明确（避免 Y 轴方向错误）
- 时间基准必须一致（帧号 vs 时间秒）
- 关键帧插值方式可能不同（线性 vs 贝塞尔）
