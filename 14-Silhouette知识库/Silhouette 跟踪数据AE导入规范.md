# Silhouette 跟踪数据AE导入规范

> 分类: 集成与导出
> 更新日期: 2026-07-11
> 概述: 跟踪数据格式、AE 表达式转换、坐标系统一完整说明。

## 目录
1. [跟踪数据概述](#1-跟踪数据概述)
2. [数据格式](#2-数据格式)
3. [坐标系差异](#3-坐标系差异)
4. [AE 表达式转换](#4-ae-表达式转换)
5. [导入流程](#5-导入流程)
6. [脚本化转换](#6-脚本化转换)
7. [常见问题](#7-常见问题)
8. [最佳实践](#8-最佳实践)

---

## 1. 跟踪数据概述

### 1.1 跟踪数据类型

| 类型 | 说明 | 用途 |
|------|------|------|
| 点跟踪 | 单点位置数据 | 位置匹配、稳定 |
| 双点跟踪 | 位置+旋转+缩放 | 变换匹配 |
| 四点跟踪 | 四角透视变换 | 屏幕替换 |
| 平面跟踪 | 整个平面的变换矩阵 | 高级跟踪 |
| 形状跟踪 | Roto 形状的逐帧变形 | Roto 辅助 |

### 1.2 跟踪数据用途

```
Silhouette 跟踪 → 导出数据 → AE 导入 → 应用到图层
                                       ├─ 位置
                                       ├─ 旋转
                                       ├─ 缩放
                                       └─ 锚点
```

## 2. 数据格式

### 2.1 Silhouette 跟踪数据结构

```python
# Silhouette 跟踪数据示例
track_data = {
    "version": "1.0",
    "source": "silhouette",
    "frame_rate": 24,
    "resolution": [1920, 1080],
    "tracks": [
        {
            "name": "Track_Point_01",
            "type": "point",
            "frames": [
                {"frame": 1, "x": 100.5, "y": 200.3, "confidence": 0.95},
                {"frame": 2, "x": 101.2, "y": 201.1, "confidence": 0.93},
                {"frame": 3, "x": 102.0, "y": 202.0, "confidence": 0.97}
            ]
        }
    ]
}
```

### 2.2 导出格式

| 格式 | 扩展名 | 说明 | AE 支持 |
|------|--------|------|---------|
| AE Mask | .txt | AE 原生遮罩格式 | 直接导入 |
| JavaScript | .jsx | AE 脚本 | 脚本执行 |
| JSON | .json | 通用数据格式 | 需脚本转换 |
| CSV | .csv | 表格数据 | 需脚本转换 |
| Boujou | .txt | 3D 跟踪格式 | 需转换 |

### 2.3 AE 原生格式

```
# AE 遮罩数据格式(.txt)
Adobe After Effects 8.0 Keyframe Data

Units Per Second 24
Source Width 1920
Source Height 1080
Source Pixel Aspect Ratio 1
Comp Pixel Aspect Ratio 1

Transform Position
Frame degrees pixels
1 0 100.5 200.3
2 0 101.2 201.1
3 0 102.0 202.0

End of Keyframe Data
```

## 3. 坐标系差异

### 3.1 坐标系对比

| 软件 | 原点 | Y 轴方向 | 坐标单位 |
|------|------|----------|----------|
| Silhouette | 左下角 | 向上 | 像素 |
| After Effects | 左上角 | 向下 | 像素 |
| Nuke | 左下角 | 向上 | 像素 |

### 3.2 坐标转换公式

```
Silhouette (x_s, y_s) → AE (x_ae, y_ae):

x_ae = x_s
y_ae = height - y_s

其中 height 是图像高度
```

```python
def silhouette_to_ae_coords(x, y, height):
    """Silhouette 坐标转 AE 坐标"""
    ae_x = x
    ae_y = height - y
    return ae_x, ae_y

def ae_to_silhouette_coords(x, y, height):
    """AE 坐标转 Silhouette 坐标"""
    s_x = x
    s_y = height - y
    return s_x, s_y
```

### 3.3 归一化坐标

```python
def to_normalized(x, y, width, height):
    """转换为归一化坐标(0-1)"""
    return x / width, y / height

def from_normalized(nx, ny, width, height):
    """从归一化坐标转换回来"""
    return nx * width, ny * height
```

### 3.4 变换矩阵

```python
class TransformMatrix:
    """变换矩阵"""
    
    def __init__(self, a=1, b=0, c=0, d=1, tx=0, ty=0):
        # AE 2D 变换矩阵
        # | a  b  tx |
        # | c  d  ty |
        # | 0  0  1  |
        self.a = a   # X 缩放
        self.b = b   # X 倾斜
        self.c = c   # Y 倾斜
        self.d = d   # Y 缩放
        self.tx = tx  # X 平移
        self.ty = ty  # Y 平移
    
    @classmethod
    def from_rotation_scale_translation(cls, angle=0, sx=1, sy=1, tx=0, ty=0):
        """从旋转、缩放、平移创建矩阵"""
        import math
        rad = math.radians(angle)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)
        
        return cls(
            a=cos_a * sx,
            b=sin_a * sx,
            c=-sin_a * sy,
            d=cos_a * sy,
            tx=tx,
            ty=ty
        )
    
    def to_ae_format(self):
        """转换为 AE 矩阵格式"""
        return [self.a, self.b, self.c, self.d, self.tx, self.ty]
```

## 4. AE 表达式转换

### 4.1 位置表达式

```javascript
// AE 表达式:从外部数据应用位置
// 将此表达式粘贴到图层的 Position 属性

var data = footage("track_data.json");
var frame = timeToFrames(time);
var trackPoint = data.sourceText.value.split("\n")[frame];

// 解析坐标
var coords = trackPoint.split(",");
var x = parseFloat(coords[0]);
var y = parseFloat(coords[1]);

// 应用坐标(注意 Y 轴翻转)
[x, 1080 - y];
```

### 4.2 关键帧数据生成

```python
def generate_ae_keyframe_data(tracks, frame_rate=24, width=1920, height=1080):
    """生成 AE 关键帧数据格式"""
    lines = []
    
    # 头部
    lines.append("Adobe After Effects 8.0 Keyframe Data")
    lines.append("")
    lines.append(f"Units Per Second {frame_rate}")
    lines.append(f"Source Width {width}")
    lines.append(f"Source Height {height}")
    lines.append("Source Pixel Aspect Ratio 1")
    lines.append("Comp Pixel Aspect Ratio 1")
    lines.append("")
    
    # 位置数据
    lines.append("Transform Position")
    lines.append("Frame degrees pixels")
    
    for track in tracks:
        for frame_data in track["frames"]:
            frame = frame_data["frame"]
            x = frame_data["x"]
            y = height - frame_data["y"]  # Y 轴翻转
            lines.append(f"{frame} 0 {x} {y}")
    
    lines.append("")
    lines.append("End of Keyframe Data")
    
    return "\n".join(lines)

# 使用
ae_data = generate_ae_keyframe_data(track_data["tracks"])
with open("track_for_ae.txt", "w") as f:
    f.write(ae_data)
```

### 4.3 JavaScript 脚本生成

```python
def generate_ae_script(tracks, layer_name="Tracked Layer"):
    """生成 AE JavaScript 脚本"""
    script = f"""// Silhouette 跟踪数据导入脚本
// 自动生成

(function() {{
    var layer = app.project.activeItem.layer("{layer_name}");
    if (!layer) {{
        alert("未找到图层: {layer_name}");
        return;
    }}
    
    var position = layer.property("ADBE Transform Group").property("ADBE Position");
    
    // 清除现有关键帧
    while (position.numKeys > 0) {{
        position.removeKey(1);
    }}
    
    // 添加关键帧
"""
    
    for track in tracks:
        for frame_data in track["frames"]:
            frame = frame_data["frame"]
            x = frame_data["x"]
            y = 1080 - frame_data["y"]  # Y 轴翻转
            time_sec = frame / 24.0
            script += f'    position.setValueAtTime({time_sec}, [{x}, {y}]);\n'
    
    script += """})();
"""
    
    return script
```

### 4.4 旋转和缩放

```python
def calculate_rotation_scale(point1, point2, reference_distance, reference_angle=0):
    """
    从两点跟踪计算旋转和缩放
    point1, point2: 当前帧的两个跟踪点
    reference_distance: 参考距离(第一帧的距离)
    reference_angle: 参考角度(第一帧的角度)
    """
    import math
    
    # 当前距离
    dx = point2["x"] - point1["x"]
    dy = point2["y"] - point1["y"]
    current_distance = math.sqrt(dx*dx + dy*dy)
    
    # 当前角度
    current_angle = math.degrees(math.atan2(dy, dx))
    
    # 缩放
    scale = current_distance / reference_distance if reference_distance > 0 else 1
    
    # 旋转
    rotation = current_angle - reference_angle
    
    return {
        "rotation": rotation,
        "scale": scale * 100  # AE 使用百分比
    }

def generate_transform_keyframes(track1, track2, height=1080):
    """生成变换关键帧(位置、旋转、缩放)"""
    import math
    
    if len(track1["frames"]) < 1:
        return None
    
    # 计算参考值(第一帧)
    p1 = track1["frames"][0]
    p2 = track2["frames"][0]
    ref_dx = p2["x"] - p1["x"]
    ref_dy = p2["y"] - p1["y"]
    ref_distance = math.sqrt(ref_dx*ref_dx + ref_dy*ref_dy)
    ref_angle = math.degrees(math.atan2(ref_dy, ref_dx))
    
    keyframes = []
    for f1, f2 in zip(track1["frames"], track2["frames"]):
        # 中心点(位置)
        cx = (f1["x"] + f2["x"]) / 2
        cy = height - (f1["y"] + f2["y"]) / 2  # Y 轴翻转
        
        # 旋转和缩放
        transform = calculate_rotation_scale(f1, f2, ref_distance, ref_angle)
        
        keyframes.append({
            "frame": f1["frame"],
            "position": [cx, cy],
            "rotation": transform["rotation"],
            "scale": [transform["scale"], transform["scale"]]
        })
    
    return keyframes
```

## 5. 导入流程

### 5.1 手动导入流程

```
1. 在 Silhouette 中完成跟踪
2. 导出跟踪数据(.txt 或 .jsx)
3. 在 AE 中:
   a. 选择目标图层
   b. 选中 Position/Rotation/Scale 属性
   c. Animation → Apply Data → 选择 .txt 文件
   或
   d. File → Scripts → 运行 .jsx 脚本
```

### 5.2 自动导入脚本

```python
def export_track_for_ae(track_data, output_path, format="txt"):
    """导出跟踪数据供 AE 使用"""
    if format == "txt":
        # AE 原生关键帧格式
        content = generate_ae_keyframe_data(track_data["tracks"],
                                           track_data["frame_rate"],
                                           track_data["resolution"][0],
                                           track_data["resolution"][1])
    elif format == "jsx":
        # AE JavaScript 脚本
        content = generate_ae_script(track_data["tracks"])
    elif format == "json":
        # JSON 格式(需 AE 脚本解析)
        import json
        content = json.dumps(track_data, indent=2)
    else:
        raise ValueError(f"不支持的格式: {format}")
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    
    return output_path
```

### 5.3 AE 端导入脚本

```javascript
// AE JavaScript:导入 Silhouette 跟踪数据
function importSilhouetteTrack(filePath) {
    var file = new File(filePath);
    file.open("r");
    var content = file.read();
    file.close();
    
    // 解析数据
    var lines = content.split("\n");
    var tracks = [];
    var currentTrack = null;
    
    for (var i = 0; i < lines.length; i++) {
        var line = lines[i].trim();
        
        if (line.indexOf("Transform Position") === 0) {
            currentTrack = { type: "position", frames: [] };
            tracks.push(currentTrack);
        } else if (line.match(/^\d+/)) {
            var parts = line.split(/\s+/);
            if (parts.length >= 4 && currentTrack) {
                currentTrack.frames.push({
                    frame: parseInt(parts[0]),
                    x: parseFloat(parts[2]),
                    y: parseFloat(parts[3])
                });
            }
        }
    }
    
    // 应用到当前图层
    var layer = app.project.activeItem.selectedLayers[0];
    if (!layer) {
        alert("请先选择一个图层");
        return;
    }
    
    var position = layer.property("ADBE Transform Group").property("ADBE Position");
    
    // 清除现有关键帧
    while (position.numKeys > 0) {
        position.removeKey(1);
    }
    
    // 应用跟踪数据
    var frameRate = 24;
    for (var t = 0; t < tracks.length; t++) {
        var track = tracks[t];
        for (var f = 0; f < track.frames.length; f++) {
            var frame = track.frames[f];
            var time = frame.frame / frameRate;
            position.setValueAtTime(time, [frame.x, frame.y]);
        }
    }
    
    alert("跟踪数据导入完成: " + track.frames.length + " 帧");
}

// 使用
importSilhouetteTrack("/path/to/track_data.txt");
```

## 6. 脚本化转换

### 6.1 完整转换工具

```python
class SilhouetteToAEConverter:
    """Silhouette 跟踪数据转 AE 工具"""
    
    def __init__(self, width=1920, height=1080, frame_rate=24):
        self.width = width
        self.height = height
        self.frame_rate = frame_rate
    
    def convert_point_track(self, track_data):
        """转换单点跟踪"""
        ae_track = {
            "type": "position",
            "frames": []
        }
        
        for frame in track_data["frames"]:
            ae_x = frame["x"]
            ae_y = self.height - frame["y"]  # Y 轴翻转
            ae_track["frames"].append({
                "frame": frame["frame"],
                "x": ae_x,
                "y": ae_y
            })
        
        return ae_track
    
    def convert_two_point_track(self, track1, track2):
        """转换双点跟踪(位置+旋转+缩放)"""
        import math
        
        # 计算参考值
        p1 = track1["frames"][0]
        p2 = track2["frames"][0]
        ref_dist = math.sqrt((p2["x"]-p1["x"])**2 + (p2["y"]-p1["y"])**2)
        ref_angle = math.degrees(math.atan2(p2["y"]-p1["y"], p2["x"]-p1["x"]))
        
        ae_track = {
            "type": "transform",
            "frames": []
        }
        
        for f1, f2 in zip(track1["frames"], track2["frames"]):
            # 中心位置
            cx = (f1["x"] + f2["x"]) / 2
            cy = self.height - (f1["y"] + f2["y"]) / 2
            
            # 旋转
            dx = f2["x"] - f1["x"]
            dy = f2["y"] - f1["y"]
            angle = math.degrees(math.atan2(dy, dx)) - ref_angle
            
            # 缩放
            dist = math.sqrt(dx*dx + dy*dy)
            scale = (dist / ref_dist * 100) if ref_dist > 0 else 100
            
            ae_track["frames"].append({
                "frame": f1["frame"],
                "position": [cx, cy],
                "rotation": angle,
                "scale": [scale, scale]
            })
        
        return ae_track
    
    def export_to_ae_format(self, ae_track, output_path):
        """导出为 AE 格式"""
        lines = [
            "Adobe After Effects 8.0 Keyframe Data",
            "",
            f"Units Per Second {self.frame_rate}",
            f"Source Width {self.width}",
            f"Source Height {self.height}",
            "Source Pixel Aspect Ratio 1",
            "Comp Pixel Aspect Ratio 1",
            ""
        ]
        
        # 位置
        lines.append("Transform Position")
        lines.append("Frame degrees pixels")
        for f in ae_track["frames"]:
            pos = f["position"]
            lines.append(f'{f["frame"]} 0 {pos[0]} {pos[1]}')
        lines.append("")
        
        # 旋转(如果是变换跟踪)
        if "rotation" in ae_track["frames"][0]:
            lines.append("Transform Rotation")
            lines.append("Frame degrees")
            for f in ae_track["frames"]:
                lines.append(f'{f["frame"]} {f["rotation"]}')
            lines.append("")
            
            # 缩放
            lines.append("Transform Scale")
            lines.append("Frame percent percent")
            for f in ae_track["frames"]:
                scale = f["scale"]
                lines.append(f'{f["frame"]} {scale[0]} {scale[1]}')
            lines.append("")
        
        lines.append("End of Keyframe Data")
        
        with open(output_path, "w") as f:
            f.write("\n".join(lines))
        
        return output_path
```

### 6.2 使用示例

```python
# 转换跟踪数据
converter = SilhouetteToAEConverter(1920, 1080, 24)

# 单点跟踪
ae_track = converter.convert_point_track(sil_track_data)
converter.export_to_ae_format(ae_track, "track_ae.txt")

# 双点跟踪
ae_transform = converter.convert_two_point_track(track1, track2)
converter.export_to_ae_format(ae_transform, "transform_ae.txt")
```

## 7. 常见问题

### 7.1 坐标偏移

**问题**:跟踪数据导入 AE 后位置偏移。

**原因**:坐标系不统一(Silhouette Y 轴向上,AE Y 轴向下)。

**解决**:确保使用 `height - y` 进行 Y 轴翻转。

### 7.2 帧率不匹配

**问题**:跟踪数据在 AE 中播放速度不对。

**原因**:Silhouette 和 AE 的帧率设置不一致。

**解决**:
```python
# 确保导出时包含帧率信息
track_data["frame_rate"] = 24  # 与 AE 合成一致
```

### 7.3 分辨率不匹配

**问题**:跟踪位置与画面不对齐。

**原因**:Silhouette 项目分辨率与 AE 合成不同。

**解决**:
```python
def scale_track_coordinates(track, src_width, src_height, dst_width, dst_height):
    """缩放跟踪坐标到目标分辨率"""
    sx = dst_width / src_width
    sy = dst_height / src_height
    
    for frame in track["frames"]:
        frame["x"] *= sx
        frame["y"] *= sy
    
    return track
```

### 7.4 关键帧插值

**问题**:跟踪数据在 AE 中运动不平滑。

**原因**:AE 默认使用线性插值。

**解决**:在 AE 中将关键帧改为贝塞尔插值,或在脚本中设置:
```javascript
// AE 脚本:设置贝塞尔插值
var keyIndex = position.nearestKeyIndex(time);
position.setInterpolationTypeAtKey(keyIndex, KeyframeInterpolationType.BEZIER);
```

## 8. 最佳实践

### 8.1 数据格式选择

| 场景 | 推荐格式 | 原因 |
|------|----------|------|
| 简单位置跟踪 | AE TXT | 直接粘贴 |
| 复杂变换 | JSX 脚本 | 可编程 |
| 大量数据 | JSON | 结构化 |
| 跨平台 | JSON | 通用 |

### 8.2 命名规范

```
跟踪数据文件命名:
[项目]_[镜头]_[跟踪类型]_[版本].txt

示例:
PROJ001_SH0100_PointTrack_v01.txt
PROJ001_SH0100_TwoPoint_v02.txt
PROJ001_SH0100_Planar_v01.json
```

### 8.3 验证检查

```python
def validate_track_data(track_data):
    """验证跟踪数据"""
    issues = []
    
    # 检查必要字段
    if "tracks" not in track_data:
        issues.append("缺少 tracks 字段")
        return issues
    
    # 检查每个跟踪点
    for i, track in enumerate(track_data["tracks"]):
        if "frames" not in track:
            issues.append(f"跟踪点 {i} 缺少 frames")
            continue
        
        if len(track["frames"]) == 0:
            issues.append(f"跟踪点 {i} 没有帧数据")
            continue
        
        # 检查帧连续性
        frames = [f["frame"] for f in track["frames"]]
        if frames != sorted(frames):
            issues.append(f"跟踪点 {i} 帧序不正确")
        
        # 检查坐标范围
        for f in track["frames"]:
            if f["x"] < 0 or f["x"] > track_data["resolution"][0]:
                issues.append(f"跟踪点 {i} 帧 {f['frame']} X 坐标越界")
            if f["y"] < 0 or f["y"] > track_data["resolution"][1]:
                issues.append(f"跟踪点 {i} 帧 {f['frame']} Y 坐标越界")
    
    return issues
```

### 8.4 版本管理

```python
def add_metadata(track_data, project, shot, version):
    """添加元数据"""
    track_data["metadata"] = {
        "project": project,
        "shot": shot,
        "version": version,
        "created": "2026-07-11",
        "source": "silhouette",
        "converter_version": "1.0"
    }
    return track_data
```

---

## 附录:坐标转换速查

| 转换 | 公式 | 说明 |
|------|------|------|
| Silhouette → AE X | x_ae = x_s | X 轴相同 |
| Silhouette → AE Y | y_ae = height - y_s | Y 轴翻转 |
| 归一化 → 像素 | x = nx × width | 按分辨率缩放 |
| 像素 → 归一化 | nx = x / width | 归一化 |
| 帧 → 时间(秒) | t = frame / fps | 时间转换 |

> **提示**:导出跟踪数据时,务必在文件中包含分辨率和帧率信息,便于 AE 端正确解析和对齐。
