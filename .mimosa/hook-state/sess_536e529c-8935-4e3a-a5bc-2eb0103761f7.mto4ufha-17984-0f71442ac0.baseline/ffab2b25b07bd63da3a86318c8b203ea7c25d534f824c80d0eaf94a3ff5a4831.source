# Fast Tracking Template
# 快速跟踪模板 - 适用于预览、快速迭代、简单运动场景

from fx import *
import json
import os


def create_pipeline(source_path, output_path, frame_rate=30.0):
    """
    创建快速跟踪管线

    参数:
        source_path: 源素材路径
        output_path: 输出路径
        frame_rate: 帧率（默认30fps）

    快速跟踪特点:
        - 搜索区域小（15像素），提高处理速度
        - 低精度模式（low），快速计算
        - 模板大小小（7像素），减少计算量
        - 关键帧间隔大（20帧），减少校正次数
        - 仅向前跟踪，加快处理
        - 适用于预览、简单运动、快速迭代
    """
    # 创建或激活项目
    proj = activeProject() or Project()
    activate(proj)

    # 创建或激活会话
    session = activeSession() or Session()
    session.label = "Fast_Tracking"
    activate(session)
    proj.addItem(session)

    # 源节点
    src = Node("SourceNode")
    src.property("mediaPath").setValue(source_path.replace("\\", "/"), 0)
    src.property("frameRate").setValue(frame_rate, 0)
    session.addNode(src)

    # 跟踪节点 - 快速配置
    track = Node("TrackerNode")
    track.label = "Fast_Track"
    # 平面跟踪类型
    track.property("trackType").setValue("planar", 0)
    # 搜索区域15像素，小范围快速搜索
    track.property("searchArea").setValue(15, 0)
    # 低精度模式，快速计算
    track.property("accuracy").setValue("low", 0)
    # 模板大小7像素，减少计算量
    track.property("patternSize").setValue(7, 0)
    # 关键帧间隔20帧，减少校正
    track.property("keyframes").setValue(20, 0)
    # 仅向前跟踪，加快速度
    track.property("forward").setValue(true, 0)
    track.property("backward").setValue(false, 0)
    # 自动关键帧关闭，减少计算
    track.property("autoKeyframe").setValue(false, 0)
    session.addNode(track)

    # 连接源到跟踪节点
    src.outputs[0].connect(track.inputs[0])

    # 生成跟踪数据
    tracking_data = {
        "version": "2026.0.2",
        "track_type": "planar",
        "preset": "fast",
        "source": source_path.replace("\\", "/"),
        "parameters": {
            "searchArea": 15,
            "accuracy": "low",
            "patternSize": 7,
            "keyframes": 20,
            "forward": True,
            "backward": False,
            "autoKeyframe": False,
        },
        "frames": [],
        "trackers": [],
        "fps": frame_rate,
        "notes": "快速跟踪配置，适用于预览和简单运动",
    }

    # 确保输出目录存在
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    # 保存跟踪数据
    json_path = output_path.replace("[####].exr", "tracking_data.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(tracking_data, f, indent=2, ensure_ascii=False)

    print("[SILHOUETTE] Fast tracking pipeline ready")
    print(f"[SILHOUETTE] Source: {source_path}")
    print(f"[SILHOUETTE] Output: {output_path}")
    print(f"[SILHOUETTE] Tracking data: {json_path}")
    print("[SILHOUETTE] Preset: Fast (searchArea=15, accuracy=low)")


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3:
        create_pipeline(sys.argv[1], sys.argv[2])
    else:
        print("Usage: fast_track.py <source_path> <output_path> [frame_rate]")
