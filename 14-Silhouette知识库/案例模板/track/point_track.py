# Point Tracking Template
# 点跟踪模板 - 适用于单点/多点跟踪、特征点跟踪

import json
import os

from fx import *


def create_pipeline(source_path, output_path, frame_rate=24.0):
    """
    创建点跟踪管线

    参数:
        source_path: 源素材路径
        output_path: 输出路径
        frame_rate: 帧率（默认24fps）

    点跟踪特点:
        - 跟踪类型为 point，跟踪单个特征点
        - 搜索区域适中（17像素）
        - 中等精度（medium），平衡精度与速度
        - 模板大小小（9像素），适合小特征点
        - 关键帧间隔10帧，适中校正频率
        - 适用于面部特征点、物体角点、标记点跟踪
    """
    # 创建或激活项目
    proj = activeProject() or Project()
    activate(proj)

    # 创建或激活会话
    session = activeSession() or Session()
    session.label = "Point_Tracking"
    activate(session)
    proj.addItem(session)

    # 源节点
    src = Node("SourceNode")
    src.property("mediaPath").setValue(source_path.replace("\\", "/"), 0)
    src.property("frameRate").setValue(frame_rate, 0)
    session.addNode(src)

    # 多个点跟踪节点（可扩展）
    # 点跟踪器1 - 主跟踪点
    track1 = Node("TrackerNode")
    track1.label = "Point_Track_1"
    # 点跟踪类型
    track1.property("trackType").setValue("point", 0)
    # 搜索区域17像素
    track1.property("searchArea").setValue(17, 0)
    # 中等精度
    track1.property("accuracy").setValue("medium", 0)
    # 模板大小9像素，适合小特征点
    track1.property("patternSize").setValue(9, 0)
    # 关键帧间隔10帧
    track1.property("keyframes").setValue(10, 0)
    # 双向跟踪
    track1.property("forward").setValue(true, 0)
    track1.property("backward").setValue(true, 0)
    # 自动关键帧
    track1.property("autoKeyframe").setValue(true, 0)
    session.addNode(track1)

    # 点跟踪器2 - 辅助跟踪点
    track2 = Node("TrackerNode")
    track2.label = "Point_Track_2"
    track2.property("trackType").setValue("point", 0)
    track2.property("searchArea").setValue(17, 0)
    track2.property("accuracy").setValue("medium", 0)
    track2.property("patternSize").setValue(9, 0)
    track2.property("keyframes").setValue(10, 0)
    track2.property("forward").setValue(true, 0)
    track2.property("backward").setValue(true, 0)
    track2.property("autoKeyframe").setValue(true, 0)
    session.addNode(track2)

    # 连接源到跟踪节点
    src.outputs[0].connect(track1.inputs[0])
    src.outputs[0].connect(track2.inputs[0])

    # 生成跟踪数据
    tracking_data = {
        "version": "2026.0.2",
        "track_type": "point",
        "preset": "point_track",
        "source": source_path.replace("\\", "/"),
        "parameters": {
            "searchArea": 17,
            "accuracy": "medium",
            "patternSize": 9,
            "keyframes": 10,
            "forward": True,
            "backward": True,
            "autoKeyframe": True,
        },
        "trackers": [
            {"name": "Point_Track_1", "type": "point"},
            {"name": "Point_Track_2", "type": "point"},
        ],
        "frames": [],
        "fps": frame_rate,
        "notes": "点跟踪配置，适用于特征点和标记点跟踪",
    }

    # 确保输出目录存在
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    # 保存跟踪数据
    json_path = output_path.replace("[####].exr", "tracking_data.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(tracking_data, f, indent=2, ensure_ascii=False)

    print("[SILHOUETTE] Point tracking pipeline ready")
    print(f"[SILHOUETTE] Source: {source_path}")
    print(f"[SILHOUETTE] Output: {output_path}")
    print(f"[SILHOUETTE] Tracking data: {json_path}")
    print("[SILHOUETTE] Preset: Point Track (2 trackers configured)")


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3:
        create_pipeline(sys.argv[1], sys.argv[2])
    else:
        print("Usage: point_track.py <source_path> <output_path> [frame_rate]")
