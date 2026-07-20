# Soft Edge Keying Template
# 柔边抠像模板 - 适用于有羽化边缘的物体
#
# 特点:
#   - 中等边缘模糊（alpha.blur = 0.5-1.5）
#   - 抗锯齿平滑过渡（antialias = 1.0）
#   - 使用 X-Spline 曲线获得平滑形状
#   - 可选启用运动模糊
#   - 适用场景: 人物轮廓、动物、自然物体、布料

from fx import *
import os


def create_pipeline(source_path, output_path, frame_rate=30.0,
                    feather=1.0, blur=0.8, motion_blur=False,
                    shutter=0.5, invert=False):
    """创建柔边抠像流程

    参数:
        source_path: 源素材路径
        output_path: 输出遮罩路径（如 D:/output/matte_[####].exr）
        frame_rate: 帧率，默认 30.0
        feather: 边缘羽化值，默认 1.0
        blur: alpha 模糊值，默认 0.8
        motion_blur: 是否启用运动模糊，默认 False
        shutter: 运动模糊快门值，默认 0.5
        invert: 是否反转遮罩，默认 False
    """
    # 创建或获取活动项目
    proj = activeProject() or Project()
    activate(proj)

    # 创建或获取活动会话
    session = activeSession() or Session()
    session.label = "Soft_Edge_Keying"
    activate(session)
    proj.addItem(session)

    # 源节点 - 加载原始素材
    src = Node("SourceNode")
    src.property("mediaPath").setValue(source_path.replace("\\", "/"), 0)
    src.property("frameRate").setValue(frame_rate, 0)
    session.addNode(src)

    # Roto 节点 - 主抠像节点
    roto = Node("RotoNode")
    roto.label = "Soft_Edge_Roto"

    # 柔边抠像核心参数配置
    # alpha.blur: 中等值产生平滑过渡
    roto.property("alpha.blur").setValue(blur, 0)
    # antialias: 1.0 保持边缘平滑
    roto.property("antialias").setValue(1.0, 0)
    # fill: 启用填充
    roto.property("fill").setValue(True, 0)
    # stroke: 关闭描边
    roto.property("stroke").setValue(False, 0)
    # matte.mode: 使用 Alpha 通道
    roto.property("matte.mode").setValue("alpha", 0)
    # matte.invert: 是否反转
    roto.property("matte.invert").setValue(invert, 0)
    # motionBlur: 可选启用运动模糊
    roto.property("motionBlur").setValue(motion_blur, 0)
    if motion_blur:
        roto.property("motionBlur.shutter").setValue(shutter, 0)

    session.addNode(roto)

    # 输出节点 - 导出遮罩序列
    out_node = Node("OutputNode")
    out_node.property("path").setValue(output_path.replace("\\", "/"), 0)
    out_node.property("format").setValue("exr", 0)
    out_node.property("compression").setValue("none", 0)
    out_node.property("depth").setValue("32f", 0)
    out_node.property("channels").setValue("rgba", 0)
    session.addNode(out_node)

    # 节点连接：源 → Roto（foreground） → 输出
    src.outputs[0].connect(roto.inputs[1])
    roto.outputs[0].connect(out_node.inputs[0])

    print("[SILHOUETTE] 柔边抠像流程已创建")
    print(f"[SILHOUETTE] 源素材: {source_path}")
    print(f"[SILHOUETTE] 输出路径: {output_path}")
    print(f"[SILHOUETTE] 参数: feather={feather}, blur={blur}, "
          f"motion_blur={motion_blur}")

    return roto


def apply_soft_edge_preset(roto_node, preset="character"):
    """应用柔边抠像预设

    参数:
        roto_node: Roto 节点实例
        preset: 预设类型
            "character" - 人物角色（标准柔边）
            "animal" - 动物（较多羽化）
            "fabric" - 布料（中等柔边）
            "nature" - 自然物体（柔和过渡）
    """
    presets = {
        "character": {
            "alpha.blur": 0.8,
            "antialias": 1.0,
            "motion_blur": False,
            "description": "人物角色预设 - 标准柔边"
        },
        "animal": {
            "alpha.blur": 1.2,
            "antialias": 1.0,
            "motion_blur": True,
            "shutter": 0.5,
            "description": "动物预设 - 较多羽化和运动模糊"
        },
        "fabric": {
            "alpha.blur": 1.0,
            "antialias": 1.0,
            "motion_blur": False,
            "description": "布料预设 - 中等柔边"
        },
        "nature": {
            "alpha.blur": 1.5,
            "antialias": 1.0,
            "motion_blur": False,
            "description": "自然物体预设 - 柔和过渡"
        }
    }

    config = presets.get(preset, presets["character"])

    roto_node.property("alpha.blur").setValue(config["alpha.blur"], 0)
    roto_node.property("antialias").setValue(config["antialias"], 0)
    roto_node.property("motionBlur").setValue(config["motion_blur"], 0)
    if config.get("motion_blur") and "shutter" in config:
        roto_node.property("motionBlur.shutter").setValue(
            config["shutter"], 0
        )

    print(f"[SILHOUETTE] 已应用预设: {preset}")
    print(f"  {config['description']}")
    print(f"  alpha.blur: {config['alpha.blur']}")
    print(f"  motion_blur: {config['motion_blur']}")


def create_xspline_shape(roto_node, shape_name="SoftEdge_Shape"):
    """创建 X-Spline 形状（适用于柔边物体）

    X-Spline 曲线提供平滑的形状控制，适合柔边物体的抠像。
    支持每个点的权重调节，可以创建自然的有机形状。
    """
    # 使用 createObject 创建形状（不能直接实例化 Object 类）
    shape = createObject("X-Spline")
    shape.name = shape_name
    shape.closed = True
    shape.feather = 1.0

    print(f"[SILHOUETTE] X-Spline 形状已创建: {shape_name}")
    return shape


def create_layered_soft_edge(roto_node, layers_config):
    """创建分层柔边结构

    适用于需要不同柔边程度的复杂物体。

    参数:
        roto_node: Roto 节点实例
        layers_config: 层配置列表
            [
                {"name": "Body", "blur": 0.8, "feather": 1.0},
                {"name": "Hair", "blur": 1.5, "feather": 2.0},
                {"name": "Clothing", "blur": 1.0, "feather": 1.5}
            ]
    """
    shapes = []

    for layer in layers_config:
        shape = createObject("X-Spline")
        shape.name = layer["name"]
        shape.closed = True
        shape.feather = layer.get("feather", 1.0)
        shapes.append(shape)

        print(f"[SILHOUETTE] 创建层: {layer['name']} "
              f"(blur={layer.get('blur', 0.8)}, "
              f"feather={layer.get('feather', 1.0)})")

    print(f"[SILHOUETTE] 分层柔边结构已创建，共 {len(shapes)} 层")
    return shapes


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3:
        create_pipeline(sys.argv[1], sys.argv[2])
    else:
        print("Usage: soft_edge_keying.py <source_path> <output_path>")
        print("Example: soft_edge_keying.py D:/footage/character.mov "
              "D:/output/matte_[####].exr")
