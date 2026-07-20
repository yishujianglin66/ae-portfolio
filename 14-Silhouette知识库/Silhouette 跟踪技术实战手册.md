# Silhouette 跟踪技术实战手册

## 一、TrackerNode 核心概念

### 1.1 跟踪类型

| 类型 | 说明 | 适用场景 |
|------|------|----------|
| **Planar** | 平面跟踪 | 平面物体、屏幕、墙面 |
| **Point** | 点跟踪 | 单点标记、特征点 |
| **Paint-Track** | Paint跟踪 | 修复区域跟踪 |

### 1.2 TrackerNode 端口

**输入端口**:
| 索引 | 名称 | 说明 |
|------|------|------|
| 0 | source | 源视频输入 |

**输出端口**:
| 索引 | 名称 | 说明 |
|------|------|------|
| 0 | output | 跟踪数据输出 |

---

## 二、跟踪参数详解

### 2.1 核心参数

```python
track = Node("TrackerNode")
track.label = "Planar_Track"

# 跟踪类型
track.property("trackType").setValue("planar", 0)

# 搜索区域 - 越大越稳定但越慢
track.property("searchArea").setValue(21, 0)

# 精度
track.property("accuracy").setValue("medium", 0)

# 模板大小 - 越小越精确
track.property("patternSize").setValue(11, 0)

# 关键帧间隔
track.property("keyframes").setValue(1, 0)

session.addNode(track)
```

### 2.2 参数调优表

| 参数 | 值范围 | 效果 |
|------|--------|------|
| **searchArea** | 11-41 | 11=快速但不稳定，41=慢速但稳定 |
| **patternSize** | 5-21 | 5=精确但易丢失，21=鲁棒但粗糙 |
| **keyframes** | 1-10 | 1=逐帧跟踪，10=每10帧一个关键帧 |

### 2.3 精度设置

```python
# 高精度模式（慢但准）
track.property("accuracy").setValue("high", 0)
track.property("searchArea").setValue(31, 0)
track.property("patternSize").setValue(15, 0)

# 低精度模式（快）
track.property("accuracy").setValue("low", 0)
track.property("searchArea").setValue(15, 0)
track.property("patternSize").setValue(7, 0)
```

---

## 三、完整跟踪脚本

### 3.1 平面跟踪

```python
from fx import *

proj = activeProject() or Project()
activate(proj)

session = activeSession() or Session()
session.label = "Planar_Tracking"
activate(session)
proj.addItem(session)

src = Node("SourceNode")
src.property("mediaPath").setValue("D:/footage/video.mov", 0)
src.property("frameRate").setValue(30.0, 0)
session.addNode(src)

track = Node("TrackerNode")
track.label = "Planar_Track"
track.property("trackType").setValue("planar", 0)
track.property("searchArea").setValue(21, 0)
track.property("accuracy").setValue("medium", 0)
track.property("patternSize").setValue(11, 0)
track.property("keyframes").setValue(1, 0)
track.property("forward").setValue(true, 0)
track.property("backward").setValue(false, 0)
track.property("autoKeyframe").setValue(true, 0)
session.addNode(track)

src.outputs[0].connect(track.inputs[0])

print("[SILHOUETTE] Planar tracker configured")
```

### 3.2 双向跟踪

```python
track.property("forward").setValue(true, 0)
track.property("backward").setValue(true, 0)
```

---

## 四、跟踪数据导出

### 4.1 导出到 JSON

```python
import json

tracking_data = {
    "version": "2026.0.2",
    "track_type": "planar",
    "source": "D:/footage/video.mov",
    "search_area": 21,
    "accuracy": "medium",
    "frames": [],
    "trackers": []
}

with open("D:/output/tracking_data.json", "w") as f:
    json.dump(tracking_data, f, indent=2)
```

### 4.2 导出到 AE 关键帧格式

```python
ae_keyframes = {
    "nullObjectName": "Silhouette_Tracker",
    "keyframes": {
        "Position": [],
        "Scale": [],
        "Rotation": []
    },
    "fps": 30.0
}
```

---

## 五、常用预设

### 5.1 标准平面跟踪

```python
def apply_planar_track(track):
    track.property("trackType").setValue("planar", 0)
    track.property("searchArea").setValue(21, 0)
    track.property("accuracy").setValue("medium", 0)
    track.property("patternSize").setValue(11, 0)
    track.property("keyframes").setValue(1, 0)
    track.property("forward").setValue(true, 0)
    track.property("backward").setValue(false, 0)
```

### 5.2 高精度跟踪

```python
def apply_high_precision_track(track):
    track.property("trackType").setValue("planar", 0)
    track.property("searchArea").setValue(31, 0)
    track.property("accuracy").setValue("high", 0)
    track.property("patternSize").setValue(15, 0)
    track.property("keyframes").setValue(1, 0)
```

### 5.3 快速跟踪

```python
def apply_fast_track(track):
    track.property("trackType").setValue("point", 0)
    track.property("searchArea").setValue(15, 0)
    track.property("accuracy").setValue("low", 0)
    track.property("patternSize").setValue(7, 0)
    track.property("keyframes").setValue(5, 0)
```

---

## 六、故障排查

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 跟踪丢失 | 特征不明显 | 增大 searchArea，使用高精度模式 |
| 跟踪抖动 | patternSize 过小 | 增大 patternSize |
| 跟踪速度慢 | searchArea 过大 | 减小 searchArea，降低精度 |
| 向后跟踪失败 | 起始帧特征变化 | 改为单向跟踪 |

---

## 七、与 AE 集成

### 7.1 在 AE 中应用跟踪数据

```javascript
var trackerData = JSON.parse(File("D:/output/tracking_data.json").read());

var nullObj = comp.layers.addNull();
nullObj.name = "Silhouette_Tracker";
nullObj.threeDLayer = true;

var pos = nullObj.property("ADBE Transform Group").property("ADBE Position");
for (var i = 0; i < trackerData.keyframes.Position.length; i++) {
    var key = trackerData.keyframes.Position[i];
    pos.setValueAtTime(key.time, key.value);
}
```

### 7.2 父级链接

```javascript
targetLayer.parent = nullObj;
```
