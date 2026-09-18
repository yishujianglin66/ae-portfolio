# Smart Repair Template
# 智能修复模板 - 自动检测并修复画面瑕疵

import os

from fx import *


def create_pipeline(source_path, output_path, frame_rate=24.0):
    """
    创建智能修复管线

    参数:
        source_path: 源素材路径
        output_path: 输出路径
        frame_rate: 帧率（默认24fps）

    智能修复特点:
        - 使用 Repair 模式自动融合
        - 启用色彩匹配
        - 启用纹理保留
        - 时间平滑减少闪烁
        - 跟踪驱动自动传播
        - 适用于瑕疵修复、皮肤修饰
    """
    # 创建或激活项目
    proj = activeProject() or Project()
    activate(proj)

    # 创建或激活会话
    session = activeSession() or Session()
    session.label = "Smart_Repair"
    activate(session)
    proj.addItem(session)

    # 源节点
    src = Node("SourceNode")
    src.property("mediaPath").setValue(source_path.replace("\\", "/"), 0)
    src.property("frameRate").setValue(frame_rate, 0)
    session.addNode(src)

    # 跟踪节点 - 用于驱动修复
    track = Node("TrackerNode")
    track.label = "Repair_Track"
    track.property("trackType").setValue("planar", 0)
    track.property("searchArea").setValue(21, 0)
    track.property("accuracy").setValue("high", 0)
    track.property("patternSize").setValue(11, 0)
    track.property("keyframes").setValue(5, 0)
    track.property("forward").setValue(true, 0)
    track.property("backward").setValue(true, 0)
    track.property("autoKeyframe").setValue(true, 0)
    session.addNode(track)

    # 智能修复 Paint 节点
    paint = Node("PaintNode")
    paint.label = "Smart_Paint"
    # 笔刷参数 - 适中大小，软边缘
    paint.property("brush.size").setValue(20.0, 0)
    paint.property("brush.hardness").setValue(0.4, 0)
    paint.property("brush.flow").setValue(0.6, 0)
    paint.property("brush.opacity").setValue(0.8, 0)
    # Repair 模式 - 自动融合
    paint.property("mode").setValue("repair", 0)
    # 启用色彩匹配
    paint.property("colorMatch").setValue(true, 0)
    paint.property("colorRange").setValue(0.2, 0)
    # 启用纹理保留
    paint.property("texturePreserve").setValue(true, 0)
    paint.property("textureAmount").setValue(0.5, 0)
    # 时间平滑
    paint.property("temporalSmooth").setValue(true, 0)
    paint.property("temporalRange").setValue(3, 0)
    # 跟踪驱动传播
    paint.property("propagation").setValue("tracked", 0)
    paint.property("trackSource").setValue("Repair_Track", 0)
    paint.property("autoUpdate").setValue(true, 0)
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

    print("[SILHOUETTE] Smart repair pipeline ready")
    print(f"[SILHOUETTE] Source: {source_path}")
    print(f"[SILHOUETTE] Output: {output_path}")
    print("[SILHOUETTE] Preset: Smart Repair (repair mode, color match, texture preserve)")


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3:
        create_pipeline(sys.argv[1], sys.argv[2])
    else:
        print("Usage: smart_repair.py <source_path> <output_path> [frame_rate]")
