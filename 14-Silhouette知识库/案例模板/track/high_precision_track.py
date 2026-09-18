# High Precision Tracking Template
# 高精度跟踪模板 - 适用于复杂运动、高精度要求的跟踪任务

import json
import os

from fx import *


def create_pipeline(source_path, output_path, frame_rate=24.0):
    """
    创建高精度跟踪管线

    参数:
        source_path: 源素材路径
        output_path: 输出路径
        frame_rate: 帧率（默认24fps）

    高精度跟踪特点:
        - 搜索区域大（31像素），确保捕获快速运动
        - 高精度模式（high），亚像素级匹配
        - 模板大小适中（13像素），平衡精度与稳定性
        - 关键帧间隔小（5帧），频繁校正
        - 双向跟踪，确保数据完整性
        - 自动关键帧启用，适应运动变化
    """
    # 创建或激活项目
    proj = activeProject() or Project()
    activate(proj)

    # 创建或激活会话
    session = activeSession() or Session()
    session.label = "High_Precision_Tracking"
    activate(session)
    proj.addItem(session)

    # 源节点 - 加载原始素材
    src = Node("SourceNode")
    src.property("mediaPath").setValue(source_path.replace("\\", "/"), 0)
    src.property("frameRate").setValue(frame_rate, 0)
    session.addNode(src)

    # 跟踪节点 - 高精度配置
    track = Node("TrackerNode")
    track.label = "HighPrecision_Track"
    # 平面跟踪类型，适用于大多数高精度场景
    track.property("trackType").setValue("planar", 0)
    # 搜索区域31像素，覆盖快速运动
    track.property("searchArea").setValue(31, 0)
    # 高精度模式，亚像素级匹配
    track.property("accuracy").setValue("high", 0)
    # 模板大小13像素，平衡精度与稳定性
    track.property("patternSize").setValue(13, 0)
    # 每5帧设置关键帧，频繁校正避免漂移
    track.property("keyframes").setValue(5, 0)
    # 向前跟踪
    track.property("forward").setValue(true, 0)
    # 向后跟踪，确保数据完整性
    track.property("backward").setValue(true, 0)
    # 自动关键帧，适应运动变化
    track.property("autoKeyframe").setValue(true, 0)
    session.addNode(track)

    # 连接源到跟踪节点
    src.outputs[0].connect(track.inputs[0])

    # 生成跟踪数据文件
    tracking_data = {
        "version": "2026.0.2",
        "track_type": "planar",
        "preset": "high_precision",
        "source": source_path.replace("\\", "/"),
        "parameters": {
            "searchArea": 31,
            "accuracy": "high",
            "patternSize": 13,
            "keyframes": 5,
            "forward": True,
            "backward": True,
            "autoKeyframe": True,
        },
        "frames": [],
        "trackers": [],
        "fps": frame_rate,
        "notes": "高精度跟踪配置，适用于复杂运动场景",
    }

    # 确保输出目录存在
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    # 保存跟踪数据JSON
    json_path = output_path.replace("[####].exr", "tracking_data.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(tracking_data, f, indent=2, ensure_ascii=False)

    print("[SILHOUETTE] High precision tracking pipeline ready")
    print(f"[SILHOUETTE] Source: {source_path}")
    print(f"[SILHOUETTE] Output: {output_path}")
    print(f"[SILHOUETTE] Tracking data: {json_path}")
    print("[SILHOUETTE] Preset: High Precision (searchArea=31, accuracy=high)")


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3:
        create_pipeline(sys.argv[1], sys.argv[2])
    else:
        print("Usage: high_precision_track.py <source_path> <output_path> [frame_rate]")
