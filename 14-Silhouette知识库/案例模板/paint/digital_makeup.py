# Digital Makeup Template
# 数字化妆模板 - 适用于皮肤修复、瑕疵去除、妆容调整

import os

from fx import *


def create_pipeline(source_path, output_path, frame_rate=24.0):
    """
    创建数字化妆管线

    参数:
        source_path: 源素材路径
        output_path: 输出路径
        frame_rate: 帧率（默认24fps）

    数字化妆特点:
        - 多层修复：瑕疵去除、皮肤平滑、色彩调整
        - Repair 模式自动融合肤色
        - 启用色彩匹配和纹理保留
        - 跟踪驱动，跟随面部运动
        - 适用于人像修复、美容级处理
    """
    # 创建或激活项目
    proj = activeProject() or Project()
    activate(proj)

    # 创建或激活会话
    session = activeSession() or Session()
    session.label = "Digital_Makeup"
    activate(session)
    proj.addItem(session)

    # 源节点
    src = Node("SourceNode")
    src.property("mediaPath").setValue(source_path.replace("\\", "/"), 0)
    src.property("frameRate").setValue(frame_rate, 0)
    session.addNode(src)

    # 面部跟踪节点
    track = Node("TrackerNode")
    track.label = "Face_Track"
    # 点跟踪，跟踪面部特征点
    track.property("trackType").setValue("point", 0)
    track.property("searchArea").setValue(15, 0)
    track.property("accuracy").setValue("high", 0)
    track.property("patternSize").setValue(9, 0)
    track.property("keyframes").setValue(5, 0)
    track.property("forward").setValue(true, 0)
    track.property("backward").setValue(true, 0)
    track.property("autoKeyframe").setValue(true, 0)
    session.addNode(track)

    # 第1层: 瑕疵去除（Repair）
    paint1 = Node("PaintNode")
    paint1.label = "Blemish_Remove"
    # 小笔刷，精细修复
    paint1.property("brush.size").setValue(8.0, 0)
    # 中等硬度
    paint1.property("brush.hardness").setValue(0.6, 0)
    # 较高流量
    paint1.property("brush.flow").setValue(0.8, 0)
    paint1.property("brush.opacity").setValue(0.9, 0)
    # Repair 模式
    paint1.property("mode").setValue("repair", 0)
    # 色彩匹配
    paint1.property("colorMatch").setValue(true, 0)
    paint1.property("colorRange").setValue(0.15, 0)
    # 跟踪驱动
    paint1.property("propagation").setValue("tracked", 0)
    paint1.property("trackSource").setValue("Face_Track", 0)
    session.addNode(paint1)

    # 第2层: 皮肤平滑（低流量）
    paint2 = Node("PaintNode")
    paint2.label = "Skin_Smooth"
    # 较大笔刷
    paint2.property("brush.size").setValue(20.0, 0)
    # 软边缘
    paint2.property("brush.hardness").setValue(0.3, 0)
    # 低流量，多次叠加
    paint2.property("brush.flow").setValue(0.3, 0)
    paint2.property("brush.opacity").setValue(0.4, 0)
    # Repair 模式
    paint2.property("mode").setValue("repair", 0)
    # 色彩匹配
    paint2.property("colorMatch").setValue(true, 0)
    paint2.property("colorRange").setValue(0.2, 0)
    # 纹理保留，避免塑料感
    paint2.property("texturePreserve").setValue(true, 0)
    paint2.property("textureAmount").setValue(0.5, 0)
    # 时间平滑
    paint2.property("temporalSmooth").setValue(true, 0)
    paint2.property("temporalRange").setValue(3, 0)
    # 跟踪驱动
    paint2.property("propagation").setValue("tracked", 0)
    paint2.property("trackSource").setValue("Face_Track", 0)
    session.addNode(paint2)

    # 第3层: 色彩调整（提亮）
    paint3 = Node("PaintNode")
    paint3.label = "Color_Adjust"
    # 中等笔刷
    paint3.property("brush.size").setValue(15.0, 0)
    # 软边缘
    paint3.property("brush.hardness").setValue(0.4, 0)
    # 低不透明度
    paint3.property("brush.flow").setValue(0.4, 0)
    paint3.property("brush.opacity").setValue(0.5, 0)
    # Repair 模式
    paint3.property("mode").setValue("repair", 0)
    # 色彩调整
    paint3.property("colorMatch").setValue(true, 0)
    paint3.property("colorRange").setValue(0.2, 0)
    # 跟踪驱动
    paint3.property("propagation").setValue("tracked", 0)
    paint3.property("trackSource").setValue("Face_Track", 0)
    session.addNode(paint3)

    # 输出节点
    out_node = Node("OutputNode")
    out_node.property("path").setValue(output_path.replace("\\", "/"), 0)
    out_node.property("format").setValue("exr", 0)
    out_node.property("compression").setValue("zip", 0)
    out_node.property("depth").setValue("16f", 0)  # 16位保留色彩精度
    out_node.property("channels").setValue("rgba", 0)
    session.addNode(out_node)

    # 连接节点
    src.outputs[0].connect(track.inputs[0])
    src.outputs[0].connect(paint1.inputs[0])
    paint1.outputs[0].connect(paint2.inputs[0])
    paint2.outputs[0].connect(paint3.inputs[0])
    paint3.outputs[0].connect(out_node.inputs[0])

    print("[SILHOUETTE] Digital makeup pipeline ready")
    print(f"[SILHOUETTE] Source: {source_path}")
    print(f"[SILHOUETTE] Output: {output_path}")
    print("[SILHOUETTE] Preset: Digital Makeup (3 layers: blemish + smooth + color)")


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3:
        create_pipeline(sys.argv[1], sys.argv[2])
    else:
        print("Usage: digital_makeup.py <source_path> <output_path> [frame_rate]")
