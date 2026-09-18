# Object Removal Template
# 物体擦除模板 - 适用于大面积物体去除、背景重建

import os

from fx import *


def create_pipeline(source_path, output_path, frame_rate=24.0):
    """
    创建物体擦除管线

    参数:
        source_path: 源素材路径
        output_path: 输出路径
        frame_rate: 帧率（默认24fps）

    物体擦除特点:
        - RotoNode 创建物体遮罩
        - TrackerNode 跟踪物体运动
        - PaintNode 受遮罩限制，精确擦除
        - 多层修复：主擦除 + 细节修复 + 边缘融合
        - 适用于大面积物体、人物、标记去除
    """
    # 创建或激活项目
    proj = activeProject() or Project()
    activate(proj)

    # 创建或激活会话
    session = activeSession() or Session()
    session.label = "Object_Removal"
    activate(session)
    proj.addItem(session)

    # 源节点
    src = Node("SourceNode")
    src.property("mediaPath").setValue(source_path.replace("\\", "/"), 0)
    src.property("frameRate").setValue(frame_rate, 0)
    session.addNode(src)

    # 物体遮罩节点 - 标记要擦除的区域
    roto = Node("RotoNode")
    roto.label = "Object_Mask"
    roto.property("matte.mode").setValue("alpha", 0)
    # 适度边缘模糊
    roto.property("alpha.blur").setValue(2.0, 0)
    # 启用运动模糊
    roto.property("motionBlur").setValue(true, 0)
    roto.property("motionBlur.shutter").setValue(0.5, 0)
    session.addNode(roto)

    # 跟踪节点 - 跟踪物体运动
    track = Node("TrackerNode")
    track.label = "Object_Track"
    track.property("trackType").setValue("planar", 0)
    track.property("searchArea").setValue(31, 0)
    track.property("accuracy").setValue("high", 0)
    track.property("patternSize").setValue(13, 0)
    track.property("keyframes").setValue(5, 0)
    track.property("forward").setValue(true, 0)
    track.property("backward").setValue(true, 0)
    track.property("autoKeyframe").setValue(true, 0)
    session.addNode(track)

    # 第1层: 主擦除（Clone，受遮罩限制）
    paint1 = Node("PaintNode")
    paint1.label = "Main_Removal"
    # 大笔刷，覆盖大面积
    paint1.property("brush.size").setValue(40.0, 0)
    # 软边缘
    paint1.property("brush.hardness").setValue(0.3, 0)
    # 高流量
    paint1.property("brush.flow").setValue(0.8, 0)
    paint1.property("brush.opacity").setValue(1.0, 0)
    # Clone 模式
    paint1.property("mode").setValue("clone", 0)
    # 采样偏移
    paint1.property("sampleOffset").setValue([0, 50], 0)
    # 启用遮罩限制
    paint1.property("useMatte").setValue(true, 0)
    paint1.property("matteSource").setValue("Object_Mask", 0)
    paint1.property("matteMode").setValue("limit", 0)
    # 跟踪驱动
    paint1.property("propagation").setValue("tracked", 0)
    paint1.property("trackSource").setValue("Object_Track", 0)
    session.addNode(paint1)

    # 第2层: 细节修复（Repair）
    paint2 = Node("PaintNode")
    paint2.label = "Detail_Repair"
    # 中等笔刷
    paint2.property("brush.size").setValue(15.0, 0)
    # 中等硬度
    paint2.property("brush.hardness").setValue(0.5, 0)
    # 适中流量
    paint2.property("brush.flow").setValue(0.6, 0)
    paint2.property("brush.opacity").setValue(0.8, 0)
    # Repair 模式
    paint2.property("mode").setValue("repair", 0)
    # 色彩匹配
    paint2.property("colorMatch").setValue(true, 0)
    paint2.property("colorRange").setValue(0.2, 0)
    # 启用遮罩限制
    paint2.property("useMatte").setValue(true, 0)
    paint2.property("matteSource").setValue("Object_Mask", 0)
    paint2.property("matteMode").setValue("limit", 0)
    # 跟踪驱动
    paint2.property("propagation").setValue("tracked", 0)
    paint2.property("trackSource").setValue("Object_Track", 0)
    session.addNode(paint2)

    # 第3层: 边缘融合（Repair，软笔刷）
    paint3 = Node("PaintNode")
    paint3.label = "Edge_Blend"
    # 小笔刷
    paint3.property("brush.size").setValue(8.0, 0)
    # 软边缘
    paint3.property("brush.hardness").setValue(0.3, 0)
    # 低流量
    paint3.property("brush.flow").setValue(0.5, 0)
    paint3.property("brush.opacity").setValue(0.6, 0)
    # Repair 模式
    paint3.property("mode").setValue("repair", 0)
    # 色彩匹配
    paint3.property("colorMatch").setValue(true, 0)
    paint3.property("colorRange").setValue(0.15, 0)
    # 纹理保留
    paint3.property("texturePreserve").setValue(true, 0)
    paint3.property("textureAmount").setValue(0.5, 0)
    # 时间平滑
    paint3.property("temporalSmooth").setValue(true, 0)
    paint3.property("temporalRange").setValue(3, 0)
    session.addNode(paint3)

    # 输出节点
    out_node = Node("OutputNode")
    out_node.property("path").setValue(output_path.replace("\\", "/"), 0)
    out_node.property("format").setValue("exr", 0)
    out_node.property("compression").setValue("zip", 0)
    out_node.property("depth").setValue("32f", 0)
    out_node.property("channels").setValue("rgba", 0)
    session.addNode(out_node)

    # 连接节点
    src.outputs[0].connect(roto.inputs[1])  # Roto 主输入（foreground）
    src.outputs[0].connect(track.inputs[0])  # 跟踪源
    src.outputs[0].connect(paint1.inputs[0])  # Paint 源
    roto.outputs[0].connect(paint1.inputs[0])  # 遮罩输入
    paint1.outputs[0].connect(paint2.inputs[0])
    paint2.outputs[0].connect(paint3.inputs[0])
    paint3.outputs[0].connect(out_node.inputs[0])

    print("[SILHOUETTE] Object removal pipeline ready")
    print(f"[SILHOUETTE] Source: {source_path}")
    print(f"[SILHOUETTE] Output: {output_path}")
    print("[SILHOUETTE] Preset: Object Removal (3 layers: clone + repair + blend, roto masked)")


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3:
        create_pipeline(sys.argv[1], sys.argv[2])
    else:
        print("Usage: object_removal.py <source_path> <output_path> [frame_rate]")
