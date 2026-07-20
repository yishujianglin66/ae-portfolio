# Silhouette 实战案例-运动跟踪合成

> 分类: 实战案例
> 更新日期: 2026-07-11
> 概述: 运动跟踪驱动的合成案例，含跟踪数据导出到 After Effects 的完整流程

## 目录
---

- [一、案例背景](#一案例背景)
- [二、跟踪策略](#二跟踪策略)
- [三、跟踪执行](#三跟踪执行)
- [四、跟踪数据导出](#四跟踪数据导出)
- [五、AE 集成](#五ae-集成)
- [六、合成执行](#六合成执行)
- [七、自动化脚本](#七自动化脚本)
- [八、总结](#八总结)

---

## 一、案例背景

### 1.1 项目信息

- **项目名称**：运动品牌广告
- **镜头编号**：AD_SPORTS_003
- **时长**：10 秒（300 帧 @30fps）
- **分辨率**：1920×1080
- **任务**：跟踪运动员运动，在画面中添加动态图形元素
- **下游软件**：Adobe After Effects 2026

### 1.2 需求

1. **人物跟踪**：跟踪运动员身体关键点
2. **场景跟踪**：跟踪场景特征点（用于稳定）
3. **数据导出**：导出到 AE 用于驱动图形元素
4. **遮罩生成**：为前景人物生成遮罩（用于图形避让）

---

## 二、跟踪策略

### 2.1 跟踪点规划

```python
from fx import *

# 运动员关键跟踪点
tracking_points = {
    "head": {"x": 960, "y": 300, "desc": "头部位置"},
    "left_shoulder": {"x": 880, "y": 380, "desc": "左肩"},
    "right_shoulder": {"x": 1040, "y": 380, "desc": "右肩"},
    "left_hand": {"x": 820, "y": 500, "desc": "左手"},
    "right_hand": {"x": 1100, "y": 500, "desc": "右手"},
    "left_foot": {"x": 900, "y": 900, "desc": "左脚"},
    "right_foot": {"x": 1020, "y": 900, "desc": "右脚"}
}

# 场景稳定跟踪点
scene_points = {
    "corner_1": {"x": 100, "y": 100, "desc": "左上角"},
    "corner_2": {"x": 1820, "y": 100, "desc": "右上角"},
    "corner_3": {"x": 100, "y": 980, "desc": "左下角"},
    "corner_4": {"x": 1820, "y": 980, "desc": "右下角"}
}
```

### 2.2 跟踪方法选择

| 目标 | 方法 | 理由 |
|------|------|------|
| 运动员关键点 | 点跟踪 | 需精确位置 |
| 运动整体 | 平面跟踪 | 需整体运动 |
| 场景稳定 | 点跟踪 + 平面跟踪 | 双重保障 |

---

## 三、跟踪执行

### 3.1 项目设置

```python
from fx import *

def setup_project(footage_path):
    """创建跟踪项目"""
    proj = Project()
    activate(proj)
    session = Session()
    session.label = "Motion_Tracking"
    activate(session)
    proj.addItem(session)

    src = Node("SourceNode")
    src.property("mediaPath").setValue(footage_path.replace("\\", "/"), 0)
    src.property("frameRate").setValue(30.0, 0)
    session.addNode(src)

    return proj, session, src

proj, session, src = setup_project("D:/footage/AD_SPORTS_003.mov")
```

### 3.2 人物跟踪

```python
def track_person(session, src, points):
    """跟踪人物关键点"""
    tracker = Node("TrackerNode")
    tracker.label = "Person_Track"
    session.addNode(tracker)
    src.outputs[0].connect(tracker.inputs[1])

    # 跟踪设置
    tracker.property("trackMode").setValue("sub_pixel", 0)
    tracker.property("searchSize").setValue(48, 0)  # 大搜索区域（快速运动）
    tracker.property("adaptTemplate").setValue(True, 0)  # 自适应模板

    # 添加跟踪点
    for name, point in points.items():
        tracker.addTracker(
            name=name,
            x=point["x"],
            y=point["y"],
            startFrame=1,
            endFrame=300
        )

    # 执行跟踪
    tracker.track()
    print("人物跟踪完成")
    return tracker

person_tracker = track_person(session, src, tracking_points)
```

### 3.3 场景稳定跟踪

```python
def track_scene(session, src, points):
    """跟踪场景点（用于稳定）"""
    tracker = Node("TrackerNode")
    tracker.label = "Scene_Stabilize"
    session.addNode(tracker)
    src.outputs[0].connect(tracker.inputs[1])

    tracker.property("trackMode").setValue("robust", 0)  # 鲁棒模式
    tracker.property("searchSize").setValue(32, 0)

    for name, point in points.items():
        tracker.addTracker(
            name=name,
            x=point["x"],
            y=point["y"],
            startFrame=1,
            endFrame=300
        )

    tracker.track()
    print("场景跟踪完成")
    return tracker

scene_tracker = track_scene(session, src, scene_points)
```

### 3.4 遮罩生成

```python
def create_person_matte(session, src):
    """为人物生成遮罩"""
    roto = Node("RotoNode")
    roto.label = "Person_Matte"
    roto.property("shapeType").setValue("x-spline", 0)
    roto.property("alpha.blur").setValue(0.5, 0)
    roto.property("motionBlur").setValue(True, 0)
    session.addNode(roto)
    src.outputs[0].connect(roto.inputs[1])

    # 使用跟踪数据驱动
    roto.property("trackDriven").setValue(True, 0)
    roto.property("trackSource").setValue("Person_Track", 0)

    return roto

person_matte = create_person_matte(session, src)
```

---

## 四、跟踪数据导出

### 4.1 导出到 AE

```python
def export_to_ae(tracker, output_path):
    """导出 AE 兼容的跟踪数据"""
    import os
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # 设置导出格式
    tracker.property("exportFormat").setValue("ae_keyframes", 0)
    tracker.property("exportPath").setValue(output_path.replace("\\", "/"), 0)

    # 导出选项
    tracker.property("ae.nullName").setValue("Silhouette_Tracker", 0)
    tracker.property("ae.applyTo").setValue("new_null", 0)
    tracker.property("ae.frameRate").setValue(30, 0)

    # 执行导出
    tracker.export()
    print(f"AE 跟踪数据已导出: {output_path}")

export_to_ae(person_tracker, "D:/output/AD_SPORTS_003/person_track_ae.txt")
export_to_ae(scene_tracker, "D:/output/AD_SPORTS_003/scene_track_ae.txt")
```

### 4.2 导出 JSON 格式

```python
import json

def export_to_json(tracker, output_path):
    """导出 JSON 格式的跟踪数据"""
    data = {
        "version": "1.0",
        "source": "silhouette",
        "frameRate": 30,
        "trackers": []
    }

    # 提取跟踪数据
    for i in range(tracker.numTrackers):
        track = tracker.getTracker(i)
        track_data = {
            "name": track.name,
            "startFrame": track.startFrame,
            "endFrame": track.endFrame,
            "keyframes": []
        }

        for frame in range(track.startFrame, track.endFrame + 1):
            pos = track.getPosition(frame)
            if pos:
                track_data["keyframes"].append({
                    "frame": frame,
                    "x": pos[0],
                    "y": pos[1]
                })

        data["trackers"].append(track_data)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"JSON 跟踪数据: {output_path}")

export_to_json(person_tracker, "D:/output/AD_SPORTS_003/person_track.json")
```

---

## 五、AE 集成

### 5.1 AE 导入流程

1. **导入跟踪数据**：
   - 在 AE 中打开合成
   - 选中目标图层
   - Animation → Track in Silhouette（或手动导入）

2. **应用跟踪数据**：
   - 创建 Null 对象
   - 应用跟踪数据到 Null
   - 将图形元素父级到 Null

### 5.2 AE 表达式驱动

```javascript
// AE 表达式：从 JSON 读取跟踪数据
var trackData = footage("D:/output/AD_SPORTS_003/person_track.json");
var trackers = trackData.trackers;
var tracker = null;

for (var i = 0; i < trackers.length; i++) {
    if (trackers[i].name === "head") {
        tracker = trackers[i];
        break;
    }
}

if (tracker) {
    var frame = timeToFrames(time);
    var keyframes = tracker.keyframes;
    for (var j = 0; j < keyframes.length; j++) {
        if (keyframes[j].frame === frame) {
            [keyframes[j].x, keyframes[j].y];
            break;
        }
    }
}
```

### 5.3 Silhouette 与 AE 桥接

```python
def generate_ae_bridge_data(session, output_dir):
    """生成 AE 桥接数据"""
    import json
    import os

    bridge_data = {
        "version": "2.0",
        "source": "silhouette",
        "timestamp": datetime.now().isoformat(),
        "aeIntegration": {
            "compName": "AD_SPORTS_003_Track",
            "importPath": output_dir.replace("\\", "/") + "/",
            "applyAs": "tracking_data",
            "targetLayer": "selected",
            "matteMode": "alpha",
            "nullName": "Silhouette_Tracker"
        },
        "roto": {
            "matteSequence": "D:/output/AD_SPORTS_003/matte_[####].exr",
            "shapeType": "x-spline",
            "frameRange": [1, 300],
            "resolution": [1920, 1080]
        },
        "tracking": {
            "trackers": [
                {"name": "head", "file": "person_track_ae.txt"},
                {"name": "scene", "file": "scene_track_ae.txt"}
            ],
            "exportFormat": "ae_keyframes",
            "nullObjectName": "Silhouette_Tracker"
        }
    }

    bridge_path = os.path.join(output_dir, "ae_bridge.json")
    with open(bridge_path, "w", encoding="utf-8") as f:
        json.dump(bridge_data, f, indent=2, ensure_ascii=False)

    print(f"AE 桥接数据: {bridge_path}")

generate_ae_bridge_data(session, "D:/output/AD_SPORTS_003")
```

---

## 六、合成执行

### 6.1 图形元素添加

在 AE 中根据跟踪数据添加：
1. **运动轨迹线**：可视化运动员轨迹
2. **能量光效**：跟随运动员的发光效果
3. **数据可视化**：显示运动速度、距离等
4. **品牌图形**：动态品牌标识

### 6.2 遮罩应用

```python
def setup_matte_output(session, roto, output_path):
    """输出遮罩序列供 AE 使用"""
    out = Node("OutputNode")
    out.label = "Matte_Output"
    session.addNode(out)

    out.property("path").setValue(output_path.replace("\\", "/"), 0)
    out.property("format").setValue("exr", 0)
    out.property("compression").setValue("ZIP", 0)
    out.property("startFrame").setValue(1, 0)
    out.property("endFrame").setValue(300, 0)

    roto.outputs[0].connect(out.inputs[0])

    return out

matte_out = setup_matte_output(
    session,
    person_matte,
    "D:/output/AD_SPORTS_003/matte_[####].exr"
)
```

---

## 七、自动化脚本

### 7.1 完整工作流

```python
"""
运动跟踪合成完整工作流
"""
from fx import *
import os

def create_motion_tracking_pipeline(
    footage_path,
    output_dir,
    frame_rate=30.0
):
    """创建运动跟踪管线"""

    # 1. 创建项目
    print("=== 创建项目 ===")
    proj = Project()
    activate(proj)
    session = Session()
    session.label = "Motion_Tracking"
    activate(session)
    proj.addItem(session)

    # 2. 加载素材
    print("=== 加载素材 ===")
    src = Node("SourceNode")
    src.property("mediaPath").setValue(footage_path.replace("\\", "/"), 0)
    src.property("frameRate").setValue(frame_rate, 0)
    session.addNode(src)

    # 3. 创建跟踪节点
    print("=== 创建跟踪 ===")
    person_tracker = Node("TrackerNode")
    person_tracker.label = "Person_Track"
    person_tracker.property("trackMode").setValue("sub_pixel", 0)
    person_tracker.property("searchSize").setValue(48, 0)
    session.addNode(person_tracker)
    src.outputs[0].connect(person_tracker.inputs[1])

    scene_tracker = Node("TrackerNode")
    scene_tracker.label = "Scene_Stabilize"
    scene_tracker.property("trackMode").setValue("robust", 0)
    session.addNode(scene_tracker)
    src.outputs[0].connect(scene_tracker.inputs[1])

    # 4. 创建遮罩
    print("=== 创建遮罩 ===")
    person_matte = Node("RotoNode")
    person_matte.label = "Person_Matte"
    person_matte.property("alpha.blur").setValue(0.5, 0)
    person_matte.property("motionBlur").setValue(True, 0)
    session.addNode(person_matte)
    src.outputs[0].connect(person_matte.inputs[1])

    # 5. 输出遮罩
    print("=== 配置输出 ===")
    out = Node("OutputNode")
    out.label = "Matte_Output"
    matte_path = os.path.join(output_dir, "matte_[####].exr").replace("\\", "/")
    out.property("path").setValue(matte_path, 0)
    out.property("format").setValue("exr", 0)
    out.property("compression").setValue("ZIP", 0)
    session.addNode(out)
    person_matte.outputs[0].connect(out.inputs[0])

    print("\n=== 管线创建完成 ===")
    print(f"节点数: {session.numNodes}")
    print("下一步: 添加跟踪点，执行跟踪，导出数据")

    return proj, session

if __name__ == "__main__":
    proj, session = create_motion_tracking_pipeline(
        "D:/footage/AD_SPORTS_003.mov",
        "D:/output/AD_SPORTS_003"
    )
```

---

## 八、总结

### 8.1 工时统计

| 任务 | 工时 |
|------|------|
| 素材分析 | 0.5h |
| 跟踪点规划 | 0.5h |
| 人物跟踪 | 2h |
| 场景跟踪 | 1h |
| 遮罩生成 | 2h |
| 数据导出 | 0.5h |
| AE 集成测试 | 1.5h |

### 8.2 关键经验

1. **跟踪点选择**：选择高对比度、稳定的特征
2. **搜索区域**：快速运动需大搜索区域
3. **数据格式**：提供多种格式以适配不同软件
4. **遮罩配合**：遮罩与跟踪数据配合使用
5. **AE 集成**：利用 JSON 桥接实现数据传递

---

> 相关文档：
> - [[Silhouette 实战案例-特效合成辅助]]
> - [[Silhouette 跟踪技术实战手册]]
> - [[Silhouette 与AE集成工作流]]
