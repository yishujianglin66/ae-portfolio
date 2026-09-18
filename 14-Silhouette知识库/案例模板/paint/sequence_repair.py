# Sequence Repair Template
# 序列修复模板 - 适用于长序列多帧修复

import os

from fx import *


def create_pipeline(source_path, output_path, frame_rate=24.0):
    """
    创建序列修复管线

    参数:
        source_path: 源素材路径
        output_path: 输出路径
        frame_rate: 帧率（默认24fps）

    序列修复特点:
        - 跟踪驱动自动传播
        - 时间平滑减少帧间闪烁
        - 关键帧插值模式
        - 适用于长序列、多帧修复任务
    """
    # 创建或激活项目
    proj = activeProject() or Project()
    activate(proj)

    # 创建或激活会话
    session = activeSession() or Session()
    session.label = "Sequence_Repair"
    activate(session)
    proj.addItem(session)

    # 源节点
    src = Node("SourceNode")
    src.property("mediaPath").setValue(source_path.replace("\\", "/"), 0)
    src.property("frameRate").setValue(frame_rate, 0)
    session.addNode(src)

    # 跟踪节点 - 高精度跟踪
    track = Node("TrackerNode")
    track.label = "Sequence_Track"
    track.property("trackType").setValue("planar", 0)
    track.property("searchArea").setValue(25, 0)
    track.property("accuracy").setValue("high", 0)
    track.property("patternSize").setValue(13, 0)
    track.property("keyframes").setValue(5, 0)
    track.property("forward").setValue(true, 0)
    track.property("backward").setValue(true, 0)
    track.property("autoKeyframe").setValue(true, 0)
    session.addNode(track)

    # 主修复 Paint 节点
    paint = Node("PaintNode")
    paint.label = "Sequence_Paint"
    # 适中笔刷
    paint.property("brush.size").setValue(25.0, 0)
    # 中等硬度
    paint.property("brush.hardness").setValue(0.5, 0)
    # 适中流量
    paint.property("brush.flow").setValue(0.7, 0)
    paint.property("brush.opacity").setValue(0.8, 0)
    # Clone 模式
    paint.property("mode").setValue("clone", 0)
    # 采样偏移
    paint.property("sampleOffset").setValue([0, 40], 0)
    # 跟踪驱动传播
    paint.property("propagation").setValue("tracked", 0)
    paint.property("trackSource").setValue("Sequence_Track", 0)
    paint.property("autoUpdate").setValue(true, 0)
    # 时间平滑，减少闪烁
    paint.property("temporalSmooth").setValue(true, 0)
    paint.property("temporalRange").setValue(5, 0)
    # 偏移补偿
    paint.property("offsetCompensation").setValue(true, 0)
    paint.property("compensationRange").setValue(10, 0)
    session.addNode(paint)

    # 输出节点
    out_node = Node("OutputNode")
    out_node.property("path").setValue(output_path.replace("\\", "/"), 0)
    out_node.property("format").setValue("exr", 0)
    out_node.property("compression").setValue("zip", 0)
    out_node.property("depth").setValue("32f", 0)
    out_node.property("channels").setValue("rgba", 0)
    session.addNode(out_node)

    # 连接节点
    src.outputs[0].connect(track.inputs[0])
    src.outputs[0].connect(paint.inputs[0])
    paint.outputs[0].connect(out_node.inputs[0])

    print("[SILHOUETTE] Sequence repair pipeline ready")
    print(f"[SILHOUETTE] Source: {source_path}")
    print(f"[SILHOUETTE] Output: {output_path}")
    print("[SILHOUETTE] Preset: Sequence Repair (tracked, temporal smooth, offset compensation)")


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3:
        create_pipeline(sys.argv[1], sys.argv[2])
    else:
        print("Usage: sequence_repair.py <source_path> <output_path> [frame_rate]")
