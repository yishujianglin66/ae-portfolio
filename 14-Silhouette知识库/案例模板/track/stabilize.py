# Stabilize Template
# 稳定化模板 - 适用于画面稳定、抖动去除、反向跟踪

import json
import os

from fx import *


def create_pipeline(source_path, output_path, frame_rate=24.0):
    """
    创建稳定化管线

    参数:
        source_path: 源素材路径
        output_path: 输出路径
        frame_rate: 帧率（默认24fps）

    稳定化特点:
        - 使用平面跟踪分析画面运动
        - 高精度跟踪确保稳定数据准确
        - 输出稳定化数据用于反向应用
        - 适用于手持拍摄稳定、抖动去除
    """
    # 创建或激活项目
    proj = activeProject() or Project()
    activate(proj)

    # 创建或激活会话
    session = activeSession() or Session()
    session.label = "Stabilize"
    activate(session)
    proj.addItem(session)

    # 源节点
    src = Node("SourceNode")
    src.property("mediaPath").setValue(source_path.replace("\\", "/"), 0)
    src.property("frameRate").setValue(frame_rate, 0)
    session.addNode(src)

    # 跟踪节点 - 稳定化需要高精度数据
    track = Node("TrackerNode")
    track.label = "Stabilize_Track"
    # 平面跟踪，获取整体运动
    track.property("trackType").setValue("planar", 0)
    # 较大搜索区域，确保捕获所有运动
    track.property("searchArea").setValue(25, 0)
    # 高精度，确保稳定数据准确
    track.property("accuracy").setValue("high", 0)
    # 适中模板大小
    track.property("patternSize").setValue(11, 0)
    # 频繁关键帧，细致记录运动
    track.property("keyframes").setValue(3, 0)
    # 双向跟踪
    track.property("forward").setValue(true, 0)
    track.property("backward").setValue(true, 0)
    # 自动关键帧
    track.property("autoKeyframe").setValue(true, 0)
    session.addNode(track)

    # 输出节点 - 稳定化结果
    out_node = Node("OutputNode")
    out_node.label = "Stabilize_Output"
    out_node.property("path").setValue(output_path.replace("\\", "/"), 0)
    out_node.property("format").setValue("exr", 0)
    out_node.property("compression").setValue("zip", 0)
    out_node.property("depth").setValue("32f", 0)
    out_node.property("channels").setValue("rgba", 0)
    session.addNode(out_node)

    # 连接节点
    src.outputs[0].connect(track.inputs[0])
    src.outputs[0].connect(out_node.inputs[0])

    # 生成稳定化数据
    stabilize_data = {
        "version": "2026.0.2",
        "track_type": "planar",
        "preset": "stabilize",
        "source": source_path.replace("\\", "/"),
        "parameters": {
            "searchArea": 25,
            "accuracy": "high",
            "patternSize": 11,
            "keyframes": 3,
            "forward": True,
            "backward": True,
            "autoKeyframe": True,
        },
        "stabilize": {
            "method": "inverse_track",
            "smoothness": 0.5,
            "border_mode": "mirror",
            "crop": False,
        },
        "frames": [],
        "fps": frame_rate,
        "notes": "稳定化配置，适用于抖动去除和画面稳定",
    }

    # 确保输出目录存在
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    # 保存稳定化数据
    json_path = output_path.replace("[####].exr", "stabilize_data.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(stabilize_data, f, indent=2, ensure_ascii=False)

    print("[SILHOUETTE] Stabilize pipeline ready")
    print(f"[SILHOUETTE] Source: {source_path}")
    print(f"[SILHOUETTE] Output: {output_path}")
    print(f"[SILHOUETTE] Stabilize data: {json_path}")
    print("[SILHOUETTE] Preset: Stabilize (high accuracy, frequent keyframes)")


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3:
        create_pipeline(sys.argv[1], sys.argv[2])
    else:
        print("Usage: stabilize.py <source_path> <output_path> [frame_rate]")
