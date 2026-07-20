# Multi-Channel EXR Export Template
# 多通道EXR导出模板 - 生成包含多个遮罩通道的EXR序列
# 适用于为下游合成软件（Nuke/AE）提供完整遮罩数据

from fx import *
import os
import json
import time


def create_pipeline(
    source_path,
    output_path,
    frame_rate=24.0,
    resolution=None,
    channels=None,
    compression="ZIP",
    bit_depth="half",
    color_space="ACEScg"
):
    """
    创建多通道EXR导出管线

    参数:
        source_path (str): 源素材路径
        output_path (str): 输出EXR序列路径（含####占位符）
        frame_rate (float): 帧率，默认24.0
        resolution (list): 分辨率[宽,高]，None则使用源素材
        channels (list): 通道配置列表，每个元素为字典:
            {
                "name": "通道名称",
                "roto_label": "对应Roto节点标签",
                "blur": 边缘模糊值,
                "motion_blur": 是否启用运动模糊
            }
        compression (str): 压缩格式 ZIP/DWAA/DWAB/none
        bit_depth (str): 色深 half/float
        color_space (str): 色彩空间 ACEScg/Rec.709/Rec.2020
    """

    # ===== 1. 创建项目与会话 =====
    print("=== 步骤1: 创建项目 ===")
    proj = activeProject() or Project()
    activate(proj)

    session = activeSession() or Session()
    session.label = "Multi_Channel_Export"
    activate(session)
    proj.addItem(session)

    # ===== 2. 加载源素材 =====
    print("=== 步骤2: 加载源素材 ===")
    src = Node("SourceNode")
    src.property("mediaPath").setValue(source_path.replace("\\", "/"), 0)
    src.property("frameRate").setValue(frame_rate, 0)
    session.addNode(src)

    # 获取源素材信息
    src_width = session.width
    src_height = session.height
    start_frame = src.property("startFrame").value
    end_frame = src.property("endFrame").value
    print(f"  分辨率: {src_width}x{src_height}")
    print(f"  帧范围: {start_frame}-{end_frame}")

    # ===== 3. 配置色彩管理 =====
    print("=== 步骤3: 配置色彩管理 ===")
    color = proj.property("colorManagement")
    color.setValue("enabled", True)
    color.setValue("config", "ACES 1.3")
    color.setValue("workingSpace", color_space)

    # ===== 4. 创建多通道Roto节点 =====
    print("=== 步骤4: 创建多通道Roto ===")
    if channels is None:
        # 默认通道配置
        channels = [
            {
                "name": "bodyMatte",
                "roto_label": "Body_Roto",
                "blur": 0.3,
                "motion_blur": True,
                "motion_blur_amount": 1.2
            },
            {
                "name": "hairMatte",
                "roto_label": "Hair_Roto",
                "blur": 0.8,
                "motion_blur": True,
                "motion_blur_amount": 2.0
            },
            {
                "name": "clothingMatte",
                "roto_label": "Clothing_Roto",
                "blur": 0.5,
                "motion_blur": True,
                "motion_blur_amount": 1.5
            }
        ]

    roto_nodes = []
    for ch in channels:
        roto = Node("RotoNode")
        roto.label = ch["roto_label"]
        roto.property("shapeType").setValue("x-spline", 0)
        roto.property("alpha.blur").setValue(ch["blur"], 0)
        roto.property("antialias").setValue(1.0, 0)
        roto.property("fill").setValue(True, 0)

        # 运动模糊设置
        if ch.get("motion_blur", False):
            roto.property("motionBlur").setValue(True, 0)
            roto.property("motionBlurAmount").setValue(
                ch.get("motion_blur_amount", 1.0), 0
            )

        # 遮罩模式
        roto.property("matte.mode").setValue("alpha", 0)
        roto.property("matte.invert").setValue(False, 0)

        session.addNode(roto)
        # 连接源到Roto
        src.outputs[0].connect(roto.inputs[1])
        roto_nodes.append(roto)
        print(f"  创建通道: {ch['name']} (节点: {ch['roto_label']})")

    # ===== 5. 创建合并节点 =====
    print("=== 步骤5: 创建合并节点 ===")
    merge = Node("MergeNode")
    merge.label = "Channel_Merge"
    merge.property("operation").setValue("add", 0)
    session.addNode(merge)

    # 连接所有Roto到合并节点
    for i, roto in enumerate(roto_nodes):
        if i < len(merge.inputs):
            roto.outputs[0].connect(merge.inputs[i])

    # ===== 6. 创建多通道输出节点 =====
    print("=== 步骤6: 配置多通道输出 ===")
    out = Node("OutputNode")
    out.label = "Multi_Channel_Output"
    session.addNode(out)

    # 基本输出设置
    out.property("path").setValue(output_path.replace("\\", "/"), 0)
    out.property("format").setValue("exr", 0)
    out.property("compression").setValue(compression, 0)
    out.property("bitDepth").setValue(bit_depth, 0)
    out.property("colorSpace").setValue(color_space, 0)

    # 帧范围
    out.property("startFrame").setValue(start_frame, 0)
    out.property("endFrame").setValue(end_frame, 0)

    # 启用多通道输出
    out.property("multiChannel").setValue(True, 0)

    # 配置通道映射
    # 主RGBA通道
    out.addChannel("RGBA", "main")

    # 为每个Roto节点添加独立通道
    for i, ch in enumerate(channels):
        out.addChannel(ch["name"], ch["roto_label"])

    # 连接合并节点到输出
    merge.outputs[0].connect(out.inputs[0])

    # ===== 7. 添加EXR元数据 =====
    print("=== 步骤7: 添加元数据 ===")
    meta = out.property("exrMetadata")
    meta.setValue("shotName", "Multi_Channel_Export", 0)
    meta.setValue("version", "v001", 0)
    meta.setValue("artist", "Silhouette Template", 0)
    meta.setValue("date", time.strftime("%Y-%m-%d"), 0)
    meta.setValue("frameRate", str(frame_rate), 0)
    meta.setValue("colorSpace", color_space, 0)
    meta.setValue("compression", compression, 0)
    meta.setValue("channels", ",".join([c["name"] for c in channels]), 0)
    meta.setValue("task", "multi_channel_export", 0)

    # ===== 8. 生成通道清单 =====
    print("=== 步骤8: 生成通道清单 ===")
    manifest = {
        "version": "1.0",
        "source": "silhouette",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "output": output_path,
        "frameRate": frame_rate,
        "resolution": [src_width, src_height],
        "frameRange": [start_frame, end_frame],
        "colorSpace": color_space,
        "compression": compression,
        "bitDepth": bit_depth,
        "channels": [
            {
                "name": "RGBA",
                "description": "主色彩通道"
            }
        ] + [
            {
                "name": ch["name"],
                "description": f"遮罩通道 - {ch['roto_label']}",
                "blur": ch["blur"],
                "motion_blur": ch.get("motion_blur", False)
            }
            for ch in channels
        ]
    }

    # 保存清单文件
    manifest_path = os.path.join(
        os.path.dirname(output_path),
        "channel_manifest.json"
    )
    os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"\n=== 管线创建完成 ===")
    print(f"源素材: {source_path}")
    print(f"输出路径: {output_path}")
    print(f"通道数: {len(channels) + 1} (含RGBA)")
    print(f"色彩空间: {color_space}")
    print(f"压缩: {compression}")
    print(f"清单文件: {manifest_path}")
    print(f"\n下一步: 手动绘制各通道Roto形状，然后执行渲染")

    return proj, session


if __name__ == "__main__":
    import sys

    if len(sys.argv) >= 3:
        source = sys.argv[1]
        output = sys.argv[2]
    else:
        # 默认测试路径
        source = "D:/footage/sample_plate.exr"
        output = "D:/output/multi_channel/multi_channel.####.exr"

    # 自定义通道配置
    custom_channels = [
        {
            "name": "characterMatte",
            "roto_label": "Character_Roto",
            "blur": 0.3,
            "motion_blur": True,
            "motion_blur_amount": 1.2
        },
        {
            "name": "propMatte",
            "roto_label": "Prop_Roto",
            "blur": 0.5,
            "motion_blur": True,
            "motion_blur_amount": 1.0
        },
        {
            "name": "backgroundMatte",
            "roto_label": "Background_Roto",
            "blur": 0.0,
            "motion_blur": False
        }
    ]

    create_pipeline(
        source_path=source,
        output_path=output,
        frame_rate=24.0,
        channels=custom_channels,
        compression="ZIP",
        bit_depth="half",
        color_space="ACEScg"
    )
