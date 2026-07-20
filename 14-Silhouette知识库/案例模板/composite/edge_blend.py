# Edge Blend Template
# 边缘融合模板 - 实现前景与背景的自然边缘过渡
# 适用于合成时消除边缘瑕疵、溢出、硬边等问题

from fx import *
import os
import time


def create_pipeline(
    foreground_path,
    background_path,
    output_path,
    frame_rate=24.0,
    blend_mode="auto",
    edge_softness=1.0,
    edge_extend=0.5,
    despill_strength=0.5,
    spill_color="green",
    light_wrap=0.2,
    color_match=True,
    noise_match=True,
    color_space="ACEScg"
):
    """
    创建边缘融合管线

    参数:
        foreground_path (str): 前景素材路径（含Alpha）
        background_path (str): 背景素材路径
        output_path (str): 输出路径
        frame_rate (float): 帧率
        blend_mode (str): 融合模式
            "auto" - 自动选择
            "soft" - 柔和融合
            "hard" - 锐利融合
            "feather" - 羽化融合
            "morph" - 形态学融合
        edge_softness (float): 边缘柔和度 (0.0-3.0)
        edge_extend (float): 边缘扩展量 (0.0-2.0)
        despill_strength (float): 溢出抑制强度 (0.0-1.0)
        spill_color (str): 溢出颜色 green/blue/red
        light_wrap (float): 光包裹强度 (0.0-1.0)
        color_match (bool): 是否匹配色彩
        noise_match (bool): 是否匹配噪点
        color_space (str): 色彩空间
    """

    # ===== 1. 创建项目与会话 =====
    print("=== 步骤1: 创建项目 ===")
    proj = activeProject() or Project()
    activate(proj)

    session = activeSession() or Session()
    session.label = "Edge_Blend"
    activate(session)
    proj.addItem(session)

    # ===== 2. 配置色彩管理 =====
    print("=== 步骤2: 配置色彩管理 ===")
    color = proj.property("colorManagement")
    color.setValue("enabled", True)
    color.setValue("config", "ACES 1.3")
    color.setValue("workingSpace", color_space)

    # ===== 3. 加载前景素材 =====
    print("=== 步骤3: 加载前景素材 ===")
    fg_src = Node("SourceNode")
    fg_src.label = "Foreground"
    fg_src.property("mediaPath").setValue(foreground_path.replace("\\", "/"), 0)
    fg_src.property("frameRate").setValue(frame_rate, 0)
    session.addNode(fg_src)

    # ===== 4. 加载背景素材 =====
    print("=== 步骤4: 加载背景素材 ===")
    bg_src = Node("SourceNode")
    bg_src.label = "Background"
    bg_src.property("mediaPath").setValue(background_path.replace("\\", "/"), 0)
    bg_src.property("frameRate").setValue(frame_rate, 0)
    session.addNode(bg_src)

    start_frame = fg_src.property("startFrame").value
    end_frame = fg_src.property("endFrame").value

    # ===== 5. 创建Roto节点（边缘提取） =====
    print("=== 步骤5: 创建边缘Roto ===")
    edge_roto = Node("RotoNode")
    edge_roto.label = "Edge_Mask"
    edge_roto.property("shapeType").setValue("x-spline", 0)

    # 根据融合模式设置边缘参数
    if blend_mode == "auto":
        # 自动模式：中等柔和度
        edge_roto.property("alpha.blur").setValue(edge_softness, 0)
        edge_roto.property("antialias").setValue(1.0, 0)
    elif blend_mode == "soft":
        # 柔和模式：大模糊
        edge_roto.property("alpha.blur").setValue(edge_softness * 1.5, 0)
        edge_roto.property("antialias").setValue(1.0, 0)
    elif blend_mode == "hard":
        # 锐利模式：小模糊
        edge_roto.property("alpha.blur").setValue(edge_softness * 0.3, 0)
        edge_roto.property("antialias").setValue(0.5, 0)
    elif blend_mode == "feather":
        # 羽化模式：渐变边缘
        edge_roto.property("alpha.blur").setValue(edge_softness * 2.0, 0)
        edge_roto.property("antialias").setValue(1.0, 0)
    elif blend_mode == "morph":
        # 形态学模式：先膨胀再腐蚀
        edge_roto.property("alpha.blur").setValue(edge_softness, 0)
        edge_roto.property("morph.dilate").setValue(edge_extend, 0)
        edge_roto.property("morph.erode").setValue(edge_extend * 0.5, 0)

    edge_roto.property("motionBlur").setValue(True, 0)
    edge_roto.property("motionBlurAmount").setValue(1.0, 0)
    session.addNode(edge_roto)
    fg_src.outputs[0].connect(edge_roto.inputs[1])

    # ===== 6. 创建边缘扩展节点 =====
    print("=== 步骤6: 创建边缘扩展 ===")
    edge_extend_node = Node("MatteNode")
    edge_extend_node.label = "Edge_Extend"
    edge_extend_node.property("grow").setValue(edge_extend, 0)  # 向外扩展
    edge_extend_node.property("blur").setValue(edge_softness * 0.5, 0)
    session.addNode(edge_extend_node)
    edge_roto.outputs[0].connect(edge_extend_node.inputs[0])

    # ===== 7. 创建溢出抑制节点 =====
    print("=== 步骤7: 创建溢出抑制 ===")
    despill = Node("ColorNode")
    despill.label = "Despill"

    # 溢出抑制设置
    despill.property("spillSuppression").setValue(True, 0)
    despill.property("spillAmount").setValue(despill_strength, 0)
    despill.property("spillColor").setValue(spill_color, 0)

    # 高级溢出控制
    despill.property("spill.algorithm").setValue("advanced", 0)
    despill.property("spill.edgeOnly").setValue(True, 0)  # 仅边缘区域
    despill.property("spill.radius").setValue(edge_softness * 2, 0)

    session.addNode(despill)
    fg_src.outputs[0].connect(despill.inputs[0])
    edge_extend_node.outputs[0].connect(despill.inputs[1])  # 使用扩展的遮罩

    # ===== 8. 创建光包裹节点 =====
    print("=== 步骤8: 创建光包裹 ===")
    light_wrap_node = Node("CompositeNode")
    light_wrap_node.label = "Light_Wrap"

    # 光包裹设置
    light_wrap_node.property("operation").setValue("screen", 0)
    light_wrap_node.property("opacity").setValue(light_wrap, 0)
    light_wrap_node.property("blur").setValue(edge_softness * 3, 0)  # 背景模糊后包裹

    session.addNode(light_wrap_node)
    bg_src.outputs[0].connect(light_wrap_node.inputs[0])  # 背景作为光
    despill.outputs[0].connect(light_wrap_node.inputs[1])  # 前景

    # ===== 9. 创建色彩匹配节点 =====
    current_output = light_wrap_node
    if color_match:
        print("=== 步骤9: 创建色彩匹配 ===")
        color_match_node = Node("ColorNode")
        color_match_node.label = "Color_Match"

        # 自动色彩匹配
        color_match_node.property("autoMatch").setValue(True, 0)
        color_match_node.property("matchTarget").setValue("background", 0)
        color_match_node.property("matchStrength").setValue(0.7, 0)

        # 手动微调
        color_match_node.property("brightness").setValue(0.0, 0)
        color_match_node.property("contrast").setValue(1.0, 0)
        color_match_node.property("saturation").setValue(1.0, 0)

        # 色温匹配
        color_match_node.property("temperature").setValue(0.0, 0)
        color_match_node.property("tint").setValue(0.0, 0)

        session.addNode(color_match_node)
        current_output.outputs[0].connect(color_match_node.inputs[0])
        bg_src.outputs[0].connect(color_match_node.inputs[1])  # 参考背景
        current_output = color_match_node

    # ===== 10. 创建噪点匹配节点 =====
    if noise_match:
        print("=== 步骤10: 创建噪点匹配 ===")
        noise_node = Node("NoiseNode")
        noise_node.label = "Noise_Match"

        # 从背景采样噪点
        noise_node.property("sampleSource").setValue("background", 0)
        noise_node.property("applyTo").setValue("foreground", 0)
        noise_node.property("strength").setValue(0.8, 0)
        noise_node.property("frequency").setValue(1.0, 0)
        noise_node.property("luminanceOnly").setValue(True, 0)

        session.addNode(noise_node)
        current_output.outputs[0].connect(noise_node.inputs[0])
        bg_src.outputs[0].connect(noise_node.inputs[1])
        current_output = noise_node

    # ===== 11. 创建最终合成节点 =====
    print("=== 步骤11: 创建最终合成 ===")
    final_comp = Node("CompositeNode")
    final_comp.label = "Final_Composite"
    final_comp.property("operation").setValue("over", 0)

    session.addNode(final_comp)
    bg_src.outputs[0].connect(final_comp.inputs[0])  # 背景
    current_output.outputs[0].connect(final_comp.inputs[1])  # 前景

    # ===== 12. 创建边缘锐化节点 =====
    print("=== 步骤12: 创建边缘锐化 ===")
    sharpen = Node("SharpenNode")
    sharpen.label = "Edge_Sharpen"
    sharpen.property("amount").setValue(0.2, 0)  # 轻微锐化
    sharpen.property("radius").setValue(1.0, 0)
    sharpen.property("edgeOnly").setValue(True, 0)  # 仅锐化边缘

    session.addNode(sharpen)
    final_comp.outputs[0].connect(sharpen.inputs[0])
    edge_extend_node.outputs[0].connect(sharpen.inputs[1])  # 边缘遮罩

    # ===== 13. 创建输出节点 =====
    print("=== 步骤13: 配置输出 ===")
    out = Node("OutputNode")
    out.label = "Edge_Blend_Output"
    session.addNode(out)

    out.property("path").setValue(output_path.replace("\\", "/"), 0)
    out.property("format").setValue("exr", 0)
    out.property("compression").setValue("ZIP", 0)
    out.property("bitDepth").setValue("half", 0)
    out.property("colorSpace").setValue(color_space, 0)
    out.property("startFrame").setValue(start_frame, 0)
    out.property("endFrame").setValue(end_frame, 0)

    sharpen.outputs[0].connect(out.inputs[0])

    # ===== 14. 添加元数据 =====
    print("=== 步骤14: 添加元数据 ===")
    meta = out.property("exrMetadata")
    meta.setValue("shotName", "Edge_Blend", 0)
    meta.setValue("version", "v001", 0)
    meta.setValue("artist", "Silhouette Template", 0)
    meta.setValue("date", time.strftime("%Y-%m-%d"), 0)
    meta.setValue("frameRate", str(frame_rate), 0)
    meta.setValue("colorSpace", color_space, 0)
    meta.setValue("blendMode", blend_mode, 0)
    meta.setValue("edgeSoftness", str(edge_softness), 0)
    meta.setValue("edgeExtend", str(edge_extend), 0)
    meta.setValue("despillStrength", str(despill_strength), 0)
    meta.setValue("spillColor", spill_color, 0)
    meta.setValue("lightWrap", str(light_wrap), 0)
    meta.setValue("colorMatch", str(color_match), 0)
    meta.setValue("noiseMatch", str(noise_match), 0)
    meta.setValue("task", "edge_blend", 0)

    print(f"\n=== 边缘融合管线创建完成 ===")
    print(f"前景: {foreground_path}")
    print(f"背景: {background_path}")
    print(f"输出: {output_path}")
    print(f"融合模式: {blend_mode}")
    print(f"边缘柔和度: {edge_softness}")
    print(f"边缘扩展: {edge_extend}")
    print(f"溢出抑制: {despill_strength} ({spill_color})")
    print(f"光包裹: {light_wrap}")
    print(f"色彩匹配: {'是' if color_match else '否'}")
    print(f"噪点匹配: {'是' if noise_match else '否'}")
    print(f"节点数: {session.numNodes}")
    print(f"\n下一步: 绘制Roto形状，执行渲染")

    return proj, session


def create_hair_edge_blend(
    foreground_path,
    background_path,
    output_path,
    frame_rate=24.0,
    color_space="ACEScg"
):
    """
    创建头发边缘专用融合管线
    头发边缘需要特殊处理：高模糊、细节保留
    """

    print("=== 创建头发边缘专用融合 ===")

    return create_pipeline(
        foreground_path=foreground_path,
        background_path=background_path,
        output_path=output_path,
        frame_rate=frame_rate,
        blend_mode="feather",
        edge_softness=2.0,       # 头发需要更大柔和度
        edge_extend=1.0,         # 扩展边缘覆盖发丝
        despill_strength=0.7,    # 强溢出抑制
        spill_color="green",
        light_wrap=0.3,          # 较强光包裹
        color_match=True,
        noise_match=True,
        color_space=color_space
    )


def create_hard_edge_blend(
    foreground_path,
    background_path,
    output_path,
    frame_rate=24.0,
    color_space="ACEScg"
):
    """
    创建硬边融合管线
    适用于产品广告等需要锐利边缘的场景
    """

    print("=== 创建硬边融合 ===")

    return create_pipeline(
        foreground_path=foreground_path,
        background_path=background_path,
        output_path=output_path,
        frame_rate=frame_rate,
        blend_mode="hard",
        edge_softness=0.3,       # 极小柔和度
        edge_extend=0.2,         # 最小扩展
        despill_strength=0.3,    # 轻微溢出抑制
        spill_color="green",
        light_wrap=0.1,          # 极弱光包裹
        color_match=True,
        noise_match=False,       # 产品广告通常不需要噪点匹配
        color_space=color_space
    )


if __name__ == "__main__":
    import sys

    if len(sys.argv) >= 4:
        fg = sys.argv[1]
        bg = sys.argv[2]
        out = sys.argv[3]
    else:
        fg = "D:/footage/foreground.exr"
        bg = "D:/footage/background.exr"
        out = "D:/output/edge_blend.####.exr"

    # 默认使用自动模式
    create_pipeline(
        foreground_path=fg,
        background_path=bg,
        output_path=out,
        frame_rate=24.0,
        blend_mode="auto",
        edge_softness=1.0,
        edge_extend=0.5,
        despill_strength=0.5,
        spill_color="green",
        light_wrap=0.2,
        color_match=True,
        noise_match=True,
        color_space="ACEScg"
    )

    # 也可以使用预设
    # create_hair_edge_blend(fg, bg, out)
    # create_hard_edge_blend(fg, bg, out)
