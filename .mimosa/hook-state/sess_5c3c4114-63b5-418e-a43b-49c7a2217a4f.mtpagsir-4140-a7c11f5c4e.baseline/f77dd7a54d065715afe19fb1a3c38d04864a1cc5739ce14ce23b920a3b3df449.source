# Alpha Composite Template
# Alpha合成模板 - 基于Alpha通道的前后景合成
# 适用于将Roto生成的遮罩应用于合成场景

from fx import *
import os
import time


def create_pipeline(
    foreground_path,
    background_path,
    output_path,
    frame_rate=24.0,
    composite_mode="over",
    premult=True,
    alpha_boost=1.0,
    edge_treatment="soft",
    edge_blur=0.5,
    color_space="ACEScg"
):
    """
    创建Alpha合成管线

    参数:
        foreground_path (str): 前景素材路径（含Alpha）
        background_path (str): 背景素材路径
        output_path (str): 输出路径
        frame_rate (float): 帧率
        composite_mode (str): 合成模式
            "over" - 标准Over合成（前景在上）
            "under" - 前景在背景下方
            "add" - 加法合成
            "screen" - 屏幕合成
            "multiply" - 乘法合成
        premult (bool): 是否预乘Alpha
        alpha_boost (float): Alpha增益（0.5-2.0）
        edge_treatment (str): 边缘处理
            "soft" - 柔和边缘
            "hard" - 锐利边缘
            "feather" - 羽化边缘
        edge_blur (float): 边缘模糊量
        color_space (str): 色彩空间
    """

    # ===== 1. 创建项目与会话 =====
    print("=== 步骤1: 创建项目 ===")
    proj = activeProject() or Project()
    activate(proj)

    session = activeSession() or Session()
    session.label = "Alpha_Composite"
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
    fg_src.label = "Foreground_Source"
    fg_src.property("mediaPath").setValue(foreground_path.replace("\\", "/"), 0)
    fg_src.property("frameRate").setValue(frame_rate, 0)
    session.addNode(fg_src)

    # ===== 4. 加载背景素材 =====
    print("=== 步骤4: 加载背景素材 ===")
    bg_src = Node("SourceNode")
    bg_src.label = "Background_Source"
    bg_src.property("mediaPath").setValue(background_path.replace("\\", "/"), 0)
    bg_src.property("frameRate").setValue(frame_rate, 0)
    session.addNode(bg_src)

    # 获取素材信息
    start_frame = fg_src.property("startFrame").value
    end_frame = fg_src.property("endFrame").value
    print(f"  帧范围: {start_frame}-{end_frame}")

    # ===== 5. 创建Roto节点（用于Alpha生成/优化） =====
    print("=== 步骤5: 创建Alpha优化节点 ===")
    alpha_roto = Node("RotoNode")
    alpha_roto.label = "Alpha_Optimize"
    alpha_roto.property("shapeType").setValue("x-spline", 0)

    # 根据边缘处理模式设置
    if edge_treatment == "soft":
        alpha_roto.property("alpha.blur").setValue(edge_blur, 0)
        alpha_roto.property("antialias").setValue(1.0, 0)
    elif edge_treatment == "hard":
        alpha_roto.property("alpha.blur").setValue(0.0, 0)
        alpha_roto.property("antialias").setValue(0.5, 0)
    elif edge_treatment == "feather":
        alpha_roto.property("alpha.blur").setValue(edge_blur * 2, 0)
        alpha_roto.property("antialias").setValue(1.0, 0)

    alpha_roto.property("motionBlur").setValue(True, 0)
    alpha_roto.property("motionBlurAmount").setValue(1.0, 0)
    session.addNode(alpha_roto)
    fg_src.outputs[0].connect(alpha_roto.inputs[1])

    # ===== 6. 创建Alpha调整节点 =====
    print("=== 步骤6: 创建Alpha调整 ===")
    alpha_adjust = Node("ColorNode")
    alpha_adjust.label = "Alpha_Adjust"
    alpha_adjust.property("alphaGain").setValue(alpha_boost, 0)

    # 预乘设置
    if premult:
        alpha_adjust.property("premultiply").setValue(True, 0)
    else:
        alpha_adjust.property("premultiply").setValue(False, 0)

    session.addNode(alpha_adjust)
    alpha_roto.outputs[0].connect(alpha_adjust.inputs[0])

    # ===== 7. 创建合成节点 =====
    print("=== 步骤7: 创建合成节点 ===")
    composite = Node("CompositeNode")
    composite.label = "Alpha_Composite"
    session.addNode(composite)

    # 设置合成模式
    mode_map = {
        "over": "over",
        "under": "under",
        "add": "add",
        "screen": "screen",
        "multiply": "multiply"
    }
    composite.property("operation").setValue(mode_map.get(composite_mode, "over"), 0)

    # 连接前景和背景
    # inputs[0] = 背景, inputs[1] = 前景
    bg_src.outputs[0].connect(composite.inputs[0])
    alpha_adjust.outputs[0].connect(composite.inputs[1])

    # ===== 8. 创建色彩校正节点（可选） =====
    print("=== 步骤8: 创建色彩校正 ===")
    color_correct = Node("ColorNode")
    color_correct.label = "Final_Color_Correct"

    # 边缘色彩匹配
    color_correct.property("brightness").setValue(0.0, 0)
    color_correct.property("contrast").setValue(1.0, 0)
    color_correct.property("saturation").setValue(1.0, 0)

    # 轻微的边缘溢出抑制
    color_correct.property("spillSuppression").setValue(True, 0)
    color_correct.property("spillAmount").setValue(0.1, 0)

    session.addNode(color_correct)
    composite.outputs[0].connect(color_correct.inputs[0])

    # ===== 9. 创建输出节点 =====
    print("=== 步骤9: 配置输出 ===")
    out = Node("OutputNode")
    out.label = "Composite_Output"
    session.addNode(out)

    out.property("path").setValue(output_path.replace("\\", "/"), 0)
    out.property("format").setValue("exr", 0)
    out.property("compression").setValue("ZIP", 0)
    out.property("bitDepth").setValue("half", 0)
    out.property("colorSpace").setValue(color_space, 0)
    out.property("startFrame").setValue(start_frame, 0)
    out.property("endFrame").setValue(end_frame, 0)

    # 连接
    color_correct.outputs[0].connect(out.inputs[0])

    # ===== 10. 添加元数据 =====
    print("=== 步骤10: 添加元数据 ===")
    meta = out.property("exrMetadata")
    meta.setValue("shotName", "Alpha_Composite", 0)
    meta.setValue("version", "v001", 0)
    meta.setValue("artist", "Silhouette Template", 0)
    meta.setValue("date", time.strftime("%Y-%m-%d"), 0)
    meta.setValue("frameRate", str(frame_rate), 0)
    meta.setValue("colorSpace", color_space, 0)
    meta.setValue("compositeMode", composite_mode, 0)
    meta.setValue("premult", str(premult), 0)
    meta.setValue("alphaBoost", str(alpha_boost), 0)
    meta.setValue("edgeTreatment", edge_treatment, 0)
    meta.setValue("task", "alpha_composite", 0)

    print(f"\n=== Alpha合成管线创建完成 ===")
    print(f"前景: {foreground_path}")
    print(f"背景: {background_path}")
    print(f"输出: {output_path}")
    print(f"合成模式: {composite_mode}")
    print(f"预乘: {premult}")
    print(f"Alpha增益: {alpha_boost}")
    print(f"边缘处理: {edge_treatment}")
    print(f"\n下一步: 绘制Roto形状，执行渲染")

    return proj, session


def create_multi_layer_composite(
    layers,
    output_path,
    frame_rate=24.0,
    color_space="ACEScg"
):
    """
    创建多层Alpha合成

    参数:
        layers (list): 图层列表，从底到顶排列
            [
                {"path": "路径", "mode": "over", "opacity": 1.0, "blur": 0.3},
                ...
            ]
        output_path (str): 输出路径
    """

    print("=== 创建多层Alpha合成 ===")

    proj = activeProject() or Project()
    activate(proj)
    session = activeSession() or Session()
    session.label = "Multi_Layer_Composite"
    activate(session)
    proj.addItem(session)

    # 配置色彩管理
    color = proj.property("colorManagement")
    color.setValue("enabled", True)
    color.setValue("workingSpace", color_space)

    # 创建所有图层
    sources = []
    rotos = []
    composites = []

    for i, layer in enumerate(layers):
        # 源节点
        src = Node("SourceNode")
        src.label = f"Layer_{i:02d}_Source"
        src.property("mediaPath").setValue(layer["path"].replace("\\", "/"), 0)
        src.property("frameRate").setValue(frame_rate, 0)
        session.addNode(src)
        sources.append(src)

        # Roto节点（Alpha优化）
        roto = Node("RotoNode")
        roto.label = f"Layer_{i:02d}_Alpha"
        roto.property("alpha.blur").setValue(layer.get("blur", 0.3), 0)
        session.addNode(roto)
        src.outputs[0].connect(roto.inputs[1])
        rotos.append(roto)

    # 逐层合成
    prev_output = rotos[0].outputs[0]
    for i in range(1, len(rotos)):
        comp = Node("CompositeNode")
        comp.label = f"Composite_{i:02d}"
        comp.property("operation").setValue(layers[i].get("mode", "over"), 0)
        comp.property("opacity").setValue(layers[i].get("opacity", 1.0), 0)
        session.addNode(comp)

        prev_output.connect(comp.inputs[0])  # 背景（下层）
        rotos[i].outputs[0].connect(comp.inputs[1])  # 前景（上层）
        prev_output = comp.outputs[0]
        composites.append(comp)

    # 输出节点
    out = Node("OutputNode")
    out.label = "Multi_Layer_Output"
    out.property("path").setValue(output_path.replace("\\", "/"), 0)
    out.property("format").setValue("exr", 0)
    out.property("compression").setValue("ZIP", 0)
    out.property("bitDepth").setValue("half", 0)
    out.property("colorSpace").setValue(color_space, 0)
    session.addNode(out)
    prev_output.connect(out.inputs[0])

    print(f"多层合成完成: {len(layers)} 层")
    return proj, session


if __name__ == "__main__":
    import sys

    if len(sys.argv) >= 4:
        fg = sys.argv[1]
        bg = sys.argv[2]
        out = sys.argv[3]
    else:
        fg = "D:/footage/foreground.exr"
        bg = "D:/footage/background.exr"
        out = "D:/output/alpha_composite.####.exr"

    create_pipeline(
        foreground_path=fg,
        background_path=bg,
        output_path=out,
        frame_rate=24.0,
        composite_mode="over",
        premult=True,
        alpha_boost=1.0,
        edge_treatment="soft",
        edge_blur=0.5,
        color_space="ACEScg"
    )
