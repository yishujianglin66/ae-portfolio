# Holdout Matte Template
# 遮挡遮罩模板 - 用于处理遮挡关系
#
# 特点:
#   - 处理前景物体遮挡背景物体的情况
#   - 生成遮挡遮罩（Holdout Matte）
#   - 支持多层遮挡关系
#   - 连接到 RotoNode 的 occlusion 输入
#   - 适用场景: 人物相互遮挡、物体前后关系、复杂场景合成
#
# 工作流:
#   前景 Roto → 遮挡遮罩 → 背景 Roto → 最终输出

from fx import *
import os


def create_pipeline(source_path, output_path, frame_rate=30.0,
                    foreground_blur=0.5, background_blur=0.8,
                    motion_blur=False):
    """创建遮挡遮罩流程

    参数:
        source_path: 源素材路径
        output_path: 输出遮罩路径（如 D:/output/matte_[####].exr）
        frame_rate: 帧率，默认 30.0
        foreground_blur: 前景遮罩模糊值，默认 0.5
        background_blur: 背景遮罩模糊值，默认 0.8
        motion_blur: 是否启用运动模糊，默认 False
    """
    # 创建或获取活动项目
    proj = activeProject() or Project()
    activate(proj)

    # 创建或获取活动会话
    session = activeSession() or Session()
    session.label = "Holdout_Matte"
    activate(session)
    proj.addItem(session)

    # 源节点 - 加载原始素材
    src = Node("SourceNode")
    src.property("mediaPath").setValue(source_path.replace("\\", "/"), 0)
    src.property("frameRate").setValue(frame_rate, 0)
    session.addNode(src)

    # 前景 Roto 节点 - 遮挡物
    roto_foreground = Node("RotoNode")
    roto_foreground.label = "Foreground_Holdout"
    roto_foreground.property("alpha.blur").setValue(foreground_blur, 0)
    roto_foreground.property("antialias").setValue(1.0, 0)
    roto_foreground.property("fill").setValue(True, 0)
    roto_foreground.property("matte.mode").setValue("alpha", 0)
    roto_foreground.property("motionBlur").setValue(motion_blur, 0)
    session.addNode(roto_foreground)

    # 背景 Roto 节点 - 被遮挡物
    roto_background = Node("RotoNode")
    roto_background.label = "Background_Main"
    roto_background.property("alpha.blur").setValue(background_blur, 0)
    roto_background.property("antialias").setValue(1.0, 0)
    roto_background.property("fill").setValue(True, 0)
    roto_background.property("matte.mode").setValue("alpha", 0)
    roto_background.property("motionBlur").setValue(motion_blur, 0)
    session.addNode(roto_background)

    # 输出节点
    out_node = Node("OutputNode")
    out_node.property("path").setValue(output_path.replace("\\", "/"), 0)
    out_node.property("format").setValue("exr", 0)
    out_node.property("compression").setValue("none", 0)
    out_node.property("depth").setValue("32f", 0)
    out_node.property("channels").setValue("rgba", 0)
    session.addNode(out_node)

    # 节点连接
    # 源 → 前景 Roto（foreground）
    src.outputs[0].connect(roto_foreground.inputs[1])
    # 源 → 背景 Roto（foreground）
    src.outputs[0].connect(roto_background.inputs[1])
    # 前景 Roto → 背景 Roto（occlusion 输入，索引 3）
    roto_foreground.outputs[0].connect(roto_background.inputs[3])
    # 背景 Roto → 输出
    roto_background.outputs[0].connect(out_node.inputs[0])

    print(f"[SILHOUETTE] 遮挡遮罩流程已创建")
    print(f"[SILHOUETTE] 源素材: {source_path}")
    print(f"[SILHOUETTE] 输出路径: {output_path}")
    print(f"[SILHOUETTE] 前景模糊: {foreground_blur}")
    print(f"[SILHOUETTE] 背景模糊: {background_blur}")
    print(f"[SILHOUETTE] 节点关系: 前景 → 背景的 occlusion 输入")

    return roto_foreground, roto_background


def create_multi_layer_holdout(source_path, output_path, layers_config,
                               frame_rate=30.0):
    """创建多层遮挡关系

    处理多个物体之间的复杂遮挡关系。
    层级顺序：从前景到背景。

    参数:
        source_path: 源素材路径
        output_path: 输出遮罩路径
        layers_config: 层配置列表（从前到后）
            [
                {"name": "Front_Person", "blur": 0.5, "shape_type": "X-Spline"},
                {"name": "Middle_Object", "blur": 0.8, "shape_type": "Bezier"},
                {"name": "Back_Background", "blur": 1.0, "shape_type": "X-Spline"}
            ]
        frame_rate: 帧率
    """
    if not layers_config:
        layers_config = [
            {"name": "Layer_1_Front", "blur": 0.5, "shape_type": "X-Spline"},
            {"name": "Layer_2_Middle", "blur": 0.8, "shape_type": "Bezier"},
            {"name": "Layer_3_Back", "blur": 1.0, "shape_type": "X-Spline"}
        ]

    # 创建或获取活动项目
    proj = activeProject() or Project()
    activate(proj)

    session = activeSession() or Session()
    session.label = "Multi_Layer_Holdout"
    activate(session)
    proj.addItem(session)

    # 源节点
    src = Node("SourceNode")
    src.property("mediaPath").setValue(source_path.replace("\\", "/"), 0)
    src.property("frameRate").setValue(frame_rate, 0)
    session.addNode(src)

    # 创建多层 Roto 节点
    roto_nodes = []
    for i, layer in enumerate(layers_config):
        roto = Node("RotoNode")
        roto.label = layer["name"]
        roto.property("alpha.blur").setValue(layer.get("blur", 0.5), 0)
        roto.property("antialias").setValue(1.0, 0)
        roto.property("fill").setValue(True, 0)
        roto.property("matte.mode").setValue("alpha", 0)
        session.addNode(roto)
        roto_nodes.append(roto)

    # 输出节点
    out_node = Node("OutputNode")
    out_node.property("path").setValue(output_path.replace("\\", "/"), 0)
    out_node.property("format").setValue("exr", 0)
    out_node.property("compression").setValue("none", 0)
    out_node.property("depth").setValue("32f", 0)
    out_node.property("channels").setValue("rgba", 0)
    session.addNode(out_node)

    # 连接节点 - 建立遮挡关系链
    # 每一层都接收源素材作为 foreground
    # 前一层的输出连接到后一层的 occlusion 输入
    for i, roto in enumerate(roto_nodes):
        # 源 → 当前层（foreground）
        src.outputs[0].connect(roto.inputs[1])

        # 前一层的输出 → 当前层的 occlusion
        if i > 0:
            prev_roto = roto_nodes[i - 1]
            prev_roto.outputs[0].connect(roto.inputs[3])

    # 最后一层 → 输出
    roto_nodes[-1].outputs[0].connect(out_node.inputs[0])

    print(f"[SILHOUETTE] 多层遮挡遮罩已创建")
    print(f"[SILHOUETTE] 层数: {len(layers_config)}")
    for i, layer in enumerate(layers_config):
        print(f"  层 {i+1}: {layer['name']} (blur={layer.get('blur', 0.5)})")

    return roto_nodes


def create_holdout_shape(roto_node, shape_name="Holdout_Shape",
                         shape_type="X-Spline"):
    """创建遮挡遮罩形状

    参数:
        roto_node: Roto 节点实例
        shape_name: 形状名称
        shape_type: 形状类型
            "X-Spline" - 平滑曲线（有机形状）
            "Bezier" - 精确控制（硬边物体）
            "Rectangle" - 矩形（快速遮挡）
            "Ellipse" - 椭圆（圆形遮挡）
    """
    shape = createObject(shape_type)
    shape.name = shape_name
    shape.closed = True

    print(f"[SILHOUETTE] 遮挡形状已创建: {shape_name} (类型: {shape_type})")
    return shape


def apply_holdout_preset(roto_node, preset="standard"):
    """应用遮挡遮罩预设

    参数:
        roto_node: Roto 节点实例
        preset: 预设类型
            "standard" - 标准遮挡
            "soft_holdout" - 柔和遮挡（毛发等）
            "hard_holdout" - 硬边遮挡（固体物体）
            "character" - 人物遮挡
    """
    presets = {
        "standard": {
            "alpha.blur": 0.5,
            "antialias": 1.0,
            "motion_blur": False,
            "description": "标准遮挡预设 - 通用场景"
        },
        "soft_holdout": {
            "alpha.blur": 1.5,
            "antialias": 1.0,
            "motion_blur": True,
            "shutter": 0.5,
            "description": "柔和遮挡预设 - 毛发、半透明物体"
        },
        "hard_holdout": {
            "alpha.blur": 0.1,
            "antialias": 1.0,
            "motion_blur": False,
            "description": "硬边遮挡预设 - 固体物体"
        },
        "character": {
            "alpha.blur": 0.8,
            "antialias": 1.0,
            "motion_blur": True,
            "shutter": 0.5,
            "description": "人物遮挡预设 - 标准人物场景"
        }
    }

    config = presets.get(preset, presets["standard"])

    roto_node.property("alpha.blur").setValue(config["alpha.blur"], 0)
    roto_node.property("antialias").setValue(config["antialias"], 0)
    roto_node.property("motionBlur").setValue(config["motion_blur"], 0)
    if config.get("motion_blur") and "shutter" in config:
        roto_node.property("motionBlur.shutter").setValue(
            config["shutter"], 0
        )

    print(f"[SILHOUETTE] 已应用预设: {preset}")
    print(f"  {config['description']}")


def invert_holdout(roto_node, frame_range=None):
    """反转遮挡遮罩

    将前景遮挡转换为背景保留，或反之。

    参数:
        roto_node: Roto 节点实例
        frame_range: 帧范围（None 表示所有帧）
    """
    if frame_range:
        for f in range(frame_range[0], frame_range[1] + 1):
            current = roto_node.property("matte.invert").getValue(f)
            roto_node.property("matte.invert").setValue(not current, f)
    else:
        current = roto_node.property("matte.invert").getValue(0)
        roto_node.property("matte.invert").setValue(not current, 0)

    print(f"[SILHOUETTE] 遮挡遮罩已反转")


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3:
        create_pipeline(sys.argv[1], sys.argv[2])
    else:
        print("Usage: holdout_matte.py <source_path> <output_path>")
        print("Example: holdout_matte.py D:/footage/scene.mov "
              "D:/output/matte_[####].exr")
