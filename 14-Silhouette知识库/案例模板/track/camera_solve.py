# Camera Solve Template
# 摄像机解算模板 - 适用于3D摄像机解算、3D跟踪

import json
import os

from fx import *


def create_pipeline(source_path, output_path, frame_rate=24.0):
    """
    创建摄像机解算管线

    参数:
        source_path: 源素材路径
        output_path: 输出路径
        frame_rate: 帧率（默认24fps）

    摄像机解算特点:
        - 多点跟踪，收集3D解算所需的特征点
        - 高精度跟踪，确保解算准确
        - 输出3D摄像机数据和点云
        - 适用于3D合成、虚拟元素插入
    """
    # 创建或激活项目
    proj = activeProject() or Project()
    activate(proj)

    # 创建或激活会话
    session = activeSession() or Session()
    session.label = "Camera_Solve"
    activate(session)
    proj.addItem(session)

    # 源节点
    src = Node("SourceNode")
    src.property("mediaPath").setValue(source_path.replace("\\", "/"), 0)
    src.property("frameRate").setValue(frame_rate, 0)
    session.addNode(src)

    # 多个跟踪节点 - 收集解算所需的特征点
    # 跟踪器1 - 左上区域特征点
    track1 = Node("TrackerNode")
    track1.label = "Solve_Track_1"
    track1.property("trackType").setValue("point", 0)
    track1.property("searchArea").setValue(21, 0)
    track1.property("accuracy").setValue("high", 0)
    track1.property("patternSize").setValue(11, 0)
    track1.property("keyframes").setValue(5, 0)
    track1.property("forward").setValue(true, 0)
    track1.property("backward").setValue(true, 0)
    track1.property("autoKeyframe").setValue(true, 0)
    session.addNode(track1)

    # 跟踪器2 - 右上区域特征点
    track2 = Node("TrackerNode")
    track2.label = "Solve_Track_2"
    track2.property("trackType").setValue("point", 0)
    track2.property("searchArea").setValue(21, 0)
    track2.property("accuracy").setValue("high", 0)
    track2.property("patternSize").setValue(11, 0)
    track2.property("keyframes").setValue(5, 0)
    track2.property("forward").setValue(true, 0)
    track2.property("backward").setValue(true, 0)
    track2.property("autoKeyframe").setValue(true, 0)
    session.addNode(track2)

    # 跟踪器3 - 中心区域特征点
    track3 = Node("TrackerNode")
    track3.label = "Solve_Track_3"
    track3.property("trackType").setValue("point", 0)
    track3.property("searchArea").setValue(21, 0)
    track3.property("accuracy").setValue("high", 0)
    track3.property("patternSize").setValue(11, 0)
    track3.property("keyframes").setValue(5, 0)
    track3.property("forward").setValue(true, 0)
    track3.property("backward").setValue(true, 0)
    track3.property("autoKeyframe").setValue(true, 0)
    session.addNode(track3)

    # 跟踪器4 - 左下区域特征点
    track4 = Node("TrackerNode")
    track4.label = "Solve_Track_4"
    track4.property("trackType").setValue("point", 0)
    track4.property("searchArea").setValue(21, 0)
    track4.property("accuracy").setValue("high", 0)
    track4.property("patternSize").setValue(11, 0)
    track4.property("keyframes").setValue(5, 0)
    track4.property("forward").setValue(true, 0)
    track4.property("backward").setValue(true, 0)
    track4.property("autoKeyframe").setValue(true, 0)
    session.addNode(track4)

    # 跟踪器5 - 右下区域特征点
    track5 = Node("TrackerNode")
    track5.label = "Solve_Track_5"
    track5.property("trackType").setValue("point", 0)
    track5.property("searchArea").setValue(21, 0)
    track5.property("accuracy").setValue("high", 0)
    track5.property("patternSize").setValue(11, 0)
    track5.property("keyframes").setValue(5, 0)
    track5.property("forward").setValue(true, 0)
    track5.property("backward").setValue(true, 0)
    track5.property("autoKeyframe").setValue(true, 0)
    session.addNode(track5)

    # 连接源到所有跟踪节点
    for track in [track1, track2, track3, track4, track5]:
        src.outputs[0].connect(track.inputs[0])

    # 生成摄像机解算数据
    solve_data = {
        "version": "2026.0.2",
        "track_type": "point",
        "preset": "camera_solve",
        "source": source_path.replace("\\", "/"),
        "parameters": {
            "searchArea": 21,
            "accuracy": "high",
            "patternSize": 11,
            "keyframes": 5,
            "forward": True,
            "backward": True,
            "autoKeyframe": True,
        },
        "camera_solve": {
            "tracker_count": 5,
            "solve_method": "bundle_adjustment",
            "focal_length": "auto",
            "lens_distortion": True,
            "point_cloud": True,
        },
        "trackers": [
            {"name": "Solve_Track_1", "region": "top_left"},
            {"name": "Solve_Track_2", "region": "top_right"},
            {"name": "Solve_Track_3", "region": "center"},
            {"name": "Solve_Track_4", "region": "bottom_left"},
            {"name": "Solve_Track_5", "region": "bottom_right"},
        ],
        "frames": [],
        "fps": frame_rate,
        "notes": "摄像机解算配置，5个跟踪点覆盖画面各区域",
    }

    # 确保输出目录存在
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    # 保存解算数据
    json_path = output_path.replace("[####].exr", "camera_solve_data.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(solve_data, f, indent=2, ensure_ascii=False)

    print("[SILHOUETTE] Camera solve pipeline ready")
    print(f"[SILHOUETTE] Source: {source_path}")
    print(f"[SILHOUETTE] Output: {output_path}")
    print(f"[SILHOUETTE] Solve data: {json_path}")
    print("[SILHOUETTE] Preset: Camera Solve (5 trackers, high accuracy)")


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3:
        create_pipeline(sys.argv[1], sys.argv[2])
    else:
        print("Usage: camera_solve.py <source_path> <output_path> [frame_rate]")
