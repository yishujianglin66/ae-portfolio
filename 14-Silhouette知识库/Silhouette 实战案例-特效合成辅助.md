# Silhouette 实战案例-特效合成辅助

> 分类: 实战案例
> 更新日期: 2026-07-11
> 概述: 为特效合成提供遮罩与跟踪数据的完整案例，涵盖爆炸、烟雾、CG 元素合成

## 目录
---

- [一、案例背景](#一案例背景)
- [二、素材分析](#二素材分析)
- [三、遮罩生成策略](#三遮罩生成策略)
- [四、跟踪数据生成](#四跟踪数据生成)
- [五、多通道输出](#五多通道输出)
- [六、与合成软件对接](#六与合成软件对接)
- [七、自动化脚本](#七自动化脚本)
- [八、总结](#八总结)

---

## 一、案例背景

### 1.1 项目信息

- **项目名称**：电影《烈焰行动》特效镜头
- **镜头编号**：VFX_045
- **时长**：5 秒（120 帧 @24fps）
- **分辨率**：4K（4096×2160）
- **任务**：为爆炸特效合成提供遮罩与跟踪数据
- **下游软件**：The Foundry Nuke 14.0

### 1.2 合成需求

1. **前景遮罩**：演员身体遮罩（用于前景保留）
2. **背景遮罩**：建筑遮罩（用于爆炸遮挡）
3. **跟踪数据**：摄像机运动数据（用于 CG 元素定位）
4. **元素分离**：实拍烟雾与 CG 爆炸分离

### 1.3 团队与周期

- **Artist**：1 名 Senior Roto/Track Artist
- **周期**：1.5 天（12 工时）

---

## 二、素材分析

### 2.1 镜头内容

- **场景**：城市街道，建筑背景
- **演员**：1 名演员从左向右奔跑
- **运动**：手持摄影，有明显 camera shake
- **环境**：干燥白天，阳光直射

### 2.2 跟踪点分析

```python
from fx import *

def analyze_tracking_points(footage_path):
    """分析跟踪点"""
    proj = Project()
    activate(proj)
    session = Session()
    session.label = "Track_Analysis"
    activate(session)
    proj.addItem(session)

    src = Node("SourceNode")
    src.property("mediaPath").setValue(footage_path.replace("\\", "/"), 0)
    session.addNode(src)

    # 分析画面特征
    tracking_features = {
        "good_features": [
            {"x": 800, "y": 600, "desc": "建筑窗角"},
            {"x": 1200, "y": 800, "desc": "路灯底部"},
            {"x": 2000, "y": 1000, "desc": "地面标记"},
            {"x": 1500, "y": 500, "desc": "屋顶边缘"}
        ],
        "bad_features": [
            {"x": 1000, "y": 1200, "desc": "演员身体（移动）"},
            {"x": 1800, "y": 900, "desc": "阴影（变化）"}
        ]
    }

    print("推荐跟踪点:")
    for f in tracking_features["good_features"]:
        print(f"  ({f['x']}, {f['y']}) - {f['desc']}")

    return tracking_features

features = analyze_tracking_points("D:/footage/VFX_045_plate.exr")
```

---

## 三、遮罩生成策略

### 3.1 遮罩分层

```
遮罩输出
├──前景层（演员）
│  ├── Body_Matte（身体）
│  └── Head_Matte（头部）
├──中景层（街道设施）
│  ├── Car_Matte（车辆）
│  └── Pole_Matte（路灯）
└──背景层（建筑）
   └── Building_Matte（建筑轮廓）
```

### 3.2 前景遮罩生成

```python
from fx import *

def create_foreground_mattes(session, src):
    """创建前景遮罩"""

    # 身体遮罩
    body_roto = Node("RotoNode")
    body_roto.label = "Actor_Body_Matte"
    body_roto.property("shapeType").setValue("x-spline", 0)
    body_roto.property("alpha.blur").setValue(0.5, 0)
    body_roto.property("motionBlur").setValue(True, 0)
    body_roto.property("motionBlurAmount").setValue(1.5, 0)
    session.addNode(body_roto)
    src.outputs[0].connect(body_roto.inputs[1])

    # 头部遮罩（独立层，便于细化）
    head_roto = Node("RotoNode")
    head_roto.label = "Actor_Head_Matte"
    head_roto.property("shapeType").setValue("x-spline", 0)
    head_roto.property("alpha.blur").setValue(0.3, 0)
    session.addNode(head_roto)
    src.outputs[0].connect(head_roto.inputs[1])

    print("前景遮罩节点已创建")
    return body_roto, head_roto

body_roto, head_roto = create_foreground_mattes(session, src)
```

### 3.3 背景遮罩生成

```python
def create_background_matte(session, src):
    """创建背景建筑遮罩"""
    building_roto = Node("RotoNode")
    building_roto.label = "Building_Matte"
    building_roto.property("shapeType").setValue("bezier", 0)
    building_roto.property("alpha.blur").setValue(0.0, 0)  # 锐利边缘
    session.addNode(building_roto)
    src.outputs[0].connect(building_roto.inputs[1])

    # 使用平面跟踪驱动形状
    building_roto.property("trackDriven").setValue(True, 0)
    building_roto.property("trackSource").setValue("planar", 0)

    print("背景遮罩节点已创建")
    return building_roto

building_roto = create_background_matte(session, src)
```

---

## 四、跟踪数据生成

### 4.1 点跟踪

```python
from fx import *

def create_point_tracking(session, src, track_points):
    """创建点跟踪"""
    tracker = Node("TrackerNode")
    tracker.label = "Camera_Track"
    session.addNode(tracker)
    src.outputs[0].connect(tracker.inputs[1])

    # 设置跟踪参数
    tracker.property("trackMode").setValue("sub_pixel", 0)  # 亚像素精度
    tracker.property("searchSize").setValue(32, 0)
    tracker.property("adaptiveSearch").setValue(True, 0)

    # 添加跟踪点
    for i, point in enumerate(track_points):
        tracker.addTracker(
            name=f"Track_{i:02d}",
            x=point["x"],
            y=point["y"],
            startFrame=1,
            endFrame=120
        )

    # 执行跟踪
    tracker.track()

    print(f"完成 {len(track_points)} 个点的跟踪")
    return tracker

# 跟踪点列表
track_points = [
    {"x": 800, "y": 600},
    {"x": 1200, "y": 800},
    {"x": 2000, "y": 1000},
    {"x": 1500, "y": 500}
]

tracker = create_point_tracking(session, src, track_points)
```

### 4.2 平面跟踪

```python
def create_planar_tracking(session, src):
    """创建平面跟踪"""
    planar = Node("PlanarTrackerNode")
    planar.label = "Building_Planar_Track"
    session.addNode(planar)
    src.outputs[0].connect(planar.inputs[1])

    # 设置跟踪区域（建筑墙面）
    planar.property("region").setValue([1000, 400, 1800, 1200], 0)

    # 跟踪参数
    planar.property("trackMode").setValue("forward", 0)
    planar.property("adaptModel").setValue(True, 0)

    # 执行跟踪
    planar.track()

    print("平面跟踪完成")
    return planar

planar_tracker = create_planar_tracking(session, src)
```

### 4.3 跟踪数据导出

```python
def export_tracking_data(tracker, output_dir):
    """导出跟踪数据为多种格式"""
    import os
    os.makedirs(output_dir, exist_ok=True)

    # Nuke 格式
    nuke_path = os.path.join(output_dir, "track_nuke.nk")
    tracker.property("exportFormat").setValue("nuke_tracker", 0)
    tracker.property("exportPath").setValue(nuke_path, 0)
    tracker.export()
    print(f"Nuke 跟踪数据: {nuke_path}")

    # AE 格式
    ae_path = os.path.join(output_dir, "track_ae.txt")
    tracker.property("exportFormat").setValue("ae_keyframes", 0)
    tracker.property("exportPath").setValue(ae_path, 0)
    tracker.export()
    print(f"AE 跟踪数据: {ae_path}")

    # Boujou 格式
    boujou_path = os.path.join(output_dir, "track_boujou.txt")
    tracker.property("exportFormat").setValue("boujou", 0)
    tracker.property("exportPath").setValue(boujou_path, 0)
    tracker.export()
    print(f"Boujou 跟踪数据: {boujou_path}")

export_tracking_data(tracker, "D:/output/VFX_045/tracking")
```

---

## 五、多通道输出

### 5.1 多通道 EXR 配置

```python
from fx import *

def setup_multi_channel_output(session, mattes, output_path):
    """设置多通道 EXR 输出"""
    out = Node("OutputNode")
    out.label = "Multi_Channel_Output"
    session.addNode(out)

    out.property("path").setValue(output_path.replace("\\", "/"), 0)
    out.property("format").setValue("exr", 0)
    out.property("compression").setValue("ZIP", 0)
    out.property("bitDepth").setValue("half", 0)

    # 启用多通道
    out.property("multiChannel").setValue(True, 0)

    # 配置通道
    channels = [
        {"name": "RGBA", "source": "main"},  # 主 RGBA
        {"name": "bodyMatte", "source": mattes["body"]},
        {"name": "headMatte", "source": mattes["head"]},
        {"name": "buildingMatte", "source": mattes["building"]}
    ]

    for ch in channels:
        out.addChannel(ch["name"], ch["source"])

    # 色彩空间
    out.property("colorSpace").setValue("ACEScg", 0)

    # 元数据
    meta = out.property("exrMetadata")
    meta.setValue("shotName", "VFX_045", 0)
    meta.setValue("version", "v002", 0)
    meta.setValue("task", "vfx_support", 0)

    return out

mattes = {
    "body": body_roto,
    "head": head_roto,
    "building": building_roto
}

output_node = setup_multi_channel_output(
    session,
    mattes,
    "D:/output/VFX_045/VFX_045_mattes_v002.####.exr"
)
```

---

## 六、与合成软件对接

### 6.1 Nuke 对接

**Nuke 脚本模板**：
```
# Nuke 读取节点配置
Read {
  file "D:/output/VFX_045/VFX_045_mattes_v002.####.exr"
  first 1
  last 120
  channels "RGBA bodyMatte headMatte buildingMatte"
}

# 使用遮罩
Shuffle {
  in "bodyMatte"
  out "alpha"
}
```

### 6.2 数据交接清单

```python
def generate_handoff_package(output_dir):
    """生成交接包"""
    import json
    import os

    package = {
        "shot": "VFX_045",
        "version": "v002",
        "date": "2026-07-11",
        "artist": "Zhang San",
        "deliverables": {
            "multi_channel_exr": "VFX_045_mattes_v002.####.exr",
            "tracking_nuke": "tracking/track_nuke.nk",
            "tracking_ae": "tracking/track_ae.txt",
            "project_file": "VFX_045.sfx"
        },
        "matte_channels": [
            "RGBA - 主色彩",
            "bodyMatte - 演员身体遮罩",
            "headMatte - 演员头部遮罩",
            "buildingMatte - 建筑遮罩"
        ],
        "tracking_info": {
            "point_track_count": 4,
            "planar_track": True,
            "frame_range": [1, 120]
        },
        "technical_specs": {
            "resolution": [4096, 2160],
            "frame_rate": 24,
            "color_space": "ACEScg",
            "bit_depth": "16-bit half"
        }
    }

    manifest_path = os.path.join(output_dir, "handoff_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(package, f, indent=2, ensure_ascii=False)

    print(f"交接包清单: {manifest_path}")
    return package

generate_handoff_package("D:/output/VFX_045")
```

---

## 七、自动化脚本

### 7.1 完整工作流

```python
"""
特效合成辅助完整工作流
"""
from fx import *
import os

def create_vfx_support_pipeline(
    footage_path,
    output_path,
    frame_rate=24.0
):
    """创建特效合成辅助管线"""

    # 1. 创建项目
    print("=== 创建项目 ===")
    proj = Project()
    activate(proj)
    session = Session()
    session.label = "VFX_Support"
    activate(session)
    proj.addItem(session)

    # 2. 加载素材
    print("=== 加载素材 ===")
    src = Node("SourceNode")
    src.property("mediaPath").setValue(footage_path.replace("\\", "/"), 0)
    src.property("frameRate").setValue(frame_rate, 0)
    session.addNode(src)

    # 3. 创建遮罩节点
    print("=== 创建遮罩 ===")
    body_roto = Node("RotoNode")
    body_roto.label = "Actor_Body_Matte"
    body_roto.property("alpha.blur").setValue(0.5, 0)
    body_roto.property("motionBlur").setValue(True, 0)
    session.addNode(body_roto)
    src.outputs[0].connect(body_roto.inputs[1])

    head_roto = Node("RotoNode")
    head_roto.label = "Actor_Head_Matte"
    head_roto.property("alpha.blur").setValue(0.3, 0)
    session.addNode(head_roto)
    src.outputs[0].connect(head_roto.inputs[1])

    building_roto = Node("RotoNode")
    building_roto.label = "Building_Matte"
    building_roto.property("alpha.blur").setValue(0.0, 0)
    session.addNode(building_roto)
    src.outputs[0].connect(building_roto.inputs[1])

    # 4. 跟踪节点
    print("=== 创建跟踪 ===")
    tracker = Node("TrackerNode")
    tracker.label = "Camera_Track"
    tracker.property("trackMode").setValue("sub_pixel", 0)
    session.addNode(tracker)
    src.outputs[0].connect(tracker.inputs[1])

    planar = Node("PlanarTrackerNode")
    planar.label = "Building_Planar_Track"
    session.addNode(planar)
    src.outputs[0].connect(planar.inputs[1])

    # 5. 多通道输出
    print("=== 配置输出 ===")
    out = Node("OutputNode")
    out.label = "Multi_Channel_Output"
    out.property("path").setValue(output_path.replace("\\", "/"), 0)
    out.property("format").setValue("exr", 0)
    out.property("compression").setValue("ZIP", 0)
    out.property("multiChannel").setValue(True, 0)
    out.property("colorSpace").setValue("ACEScg", 0)
    session.addNode(out)

    body_roto.outputs[0].connect(out.inputs[0])
    head_roto.outputs[0].connect(out.inputs[1])
    building_roto.outputs[0].connect(out.inputs[2])

    print("\n=== 管线创建完成 ===")
    print(f"节点数: {session.numNodes}")
    print("下一步: 绘制遮罩形状，执行跟踪，渲染输出")

    return proj, session

if __name__ == "__main__":
    proj, session = create_vfx_support_pipeline(
        "D:/footage/VFX_045_plate.exr",
        "D:/output/VFX_045/VFX_045_mattes_v002.####.exr"
    )
```

---

## 八、总结

### 8.1 工时统计

| 任务 | 工时 |
|------|------|
| 素材分析 | 1h |
| 前景遮罩 | 3h |
| 背景遮罩 | 2h |
| 点跟踪 | 2h |
| 平面跟踪 | 1h |
| 多通道输出 | 1h |
| 交接包生成 | 0.5h |
| QC | 1.5h |

### 8.2 关键经验

1. **分层遮罩**便于合成师灵活使用
2. **多通道 EXR**是 VFX 交付的标准格式
3. **跟踪数据**需提供多种格式以适配不同软件
4. **交接清单**确保数据完整交付
5. **与合成师沟通**了解具体需求

---

> 相关文档：
> - [[Silhouette 实战案例-运动跟踪合成]]
> - [[Silhouette 跟踪技术实战手册]]
> - [[Silhouette 与AE集成工作流]]
