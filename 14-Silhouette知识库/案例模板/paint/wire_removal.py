# Wire Removal Template
# 威亚去除模板 - 适用于威亚擦除、线条状物体去除

from fx import *
import os


def create_pipeline(source_path, output_path, frame_rate=24.0):
    """
    创建威亚去除管线

    参数:
        source_path: 源素材路径
        output_path: 输出路径
        frame_rate: 帧率（默认24fps）

    威亚去除特点:
        - 使用 Clone 模式复制背景
        - 跟踪驱动，笔触跟随威亚运动
        - 适中笔刷大小，覆盖威亚宽度
        - 软边缘，自然融合
        - 多层处理（主修复+边缘融合）
        - 适用于威亚、线缆、吊绳去除
    """
    # 创建或激活项目
    proj = activeProject() or Project()
    activate(proj)

    # 创建或激活会话
    session = activeSession() or Session()
    session.label = "Wire_Removal"
    activate(session)
    proj.addItem(session)

    # 源节点
    src = Node("SourceNode")
    src.property("mediaPath").setValue(source_path.replace("\\", "/"), 0)
    src.property("frameRate").setValue(frame_rate, 0)
    session.addNode(src)

    # 跟踪节点 - 跟踪威亚运动
    track = Node("TrackerNode")
    track.label = "Wire_Track"
    track.property("trackType").setValue("planar", 0)
    track.property("searchArea").setValue(21, 0)
    track.property("accuracy").setValue("high", 0)
    track.property("patternSize").setValue(11, 0)
    track.property("keyframes").setValue(5, 0)
    track.property("forward").setValue(true, 0)
    track.property("backward").setValue(true, 0)
    track.property("autoKeyframe").setValue(true, 0)
    session.addNode(track)

    # 第1层: 主威亚修复（Clone）
    paint1 = Node("PaintNode")
    paint1.label = "Wire_Main_Clone"
    # 笔刷大小覆盖威亚宽度
    paint1.property("brush.size").setValue(15.0, 0)
    # 软边缘
    paint1.property("brush.hardness").setValue(0.4, 0)
    # 较高流量
    paint1.property("brush.flow").setValue(0.8, 0)
    paint1.property("brush.opacity").setValue(0.9, 0)
    # Clone 模式
    paint1.property("mode").setValue("clone", 0)
    # 采样偏移（从下方采样）
    paint1.property("sampleOffset").setValue([0, 30], 0)
    # 跟踪驱动传播
    paint1.property("propagation").setValue("tracked", 0)
    paint1.property("trackSource").setValue("Wire_Track", 0)
    session.addNode(paint1)

    # 第2层: 边缘融合（Repair）
    paint2 = Node("PaintNode")
    paint2.label = "Wire_Edge_Blend"
    # 较小笔刷
    paint2.property("brush.size").setValue(8.0, 0)
    # 中等硬度
    paint2.property("brush.hardness").setValue(0.5, 0)
    # 中等流量
    paint2.property("brush.flow").setValue(0.6, 0)
    paint2.property("brush.opacity").setValue(0.7, 0)
    # Repair 模式
    paint2.property("mode").setValue("repair", 0)
    # 色彩匹配
    paint2.property("colorMatch").setValue(true, 0)
    paint2.property("colorRange").setValue(0.2, 0)
    # 跟踪驱动
    paint2.property("propagation").setValue("tracked", 0)
    paint2.property("trackSource").setValue("Wire_Track", 0)
    session.addNode(paint2)

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
    src.outputs[0].connect(paint1.inputs[0])
    paint1.outputs[0].connect(paint2.inputs[0])
    paint2.outputs[0].connect(out_node.inputs[0])

    print("[SILHOUETTE] Wire removal pipeline ready")
    print(f"[SILHOUETTE] Source: {source_path}")
    print(f"[SILHOUETTE] Output: {output_path}")
    print("[SILHOUETTE] Preset: Wire Removal (2 layers: clone + repair blend)")


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3:
        create_pipeline(sys.argv[1], sys.argv[2])
    else:
        print("Usage: wire_removal.py <source_path> <output_path> [frame_rate]")
