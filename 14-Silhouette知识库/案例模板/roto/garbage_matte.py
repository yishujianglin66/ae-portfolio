# Garbage Matte Template
# 垃圾遮罩模板 - 用于快速创建粗略遮罩
#
# 特点:
#   - 简单形状（矩形、椭圆）快速创建
#   - 粗略边缘处理（大羽化值）
#   - 用于排除大面积不需要的区域
#   - 作为精细 Roto 的基础层
#   - 适用场景: 初步清理、背景排除、工作区域限定
#
# 工作流:
#   垃圾遮罩（粗略） → 精细 Roto（精确） → 最终输出

import os

from fx import *


def create_pipeline(source_path, output_path, frame_rate=30.0,
                    matte_type="rectangle", feather=5.0,
                    blur=2.0, invert=False):
    """创建垃圾遮罩流程

    参数:
        source_path: 源素材路径
        output_path: 输出遮罩路径（如 D:/output/garbage_[####].exr）
        frame_rate: 帧率，默认 30.0
        matte_type: 遮罩类型
            "rectangle" - 矩形（快速排除）
            "ellipse" - 椭圆（圆形区域）
            "freeform" - 自由形状（多边形）
        feather: 边缘羽化值，默认 5.0（大羽化）
        blur: alpha 模糊值，默认 2.0
        invert: 是否反转遮罩，默认 False
    """
    # 创建或获取活动项目
    proj = activeProject() or Project()
    activate(proj)

    # 创建或获取活动会话
    session = activeSession() or Session()
    session.label = "Garbage_Matte"
    activate(session)
    proj.addItem(session)

    # 源节点 - 加载原始素材
    src = Node("SourceNode")
    src.property("mediaPath").setValue(source_path.replace("\\", "/"), 0)
    src.property("frameRate").setValue(frame_rate, 0)
    session.addNode(src)

    # Roto 节点 - 垃圾遮罩
    roto = Node("RotoNode")
    roto.label = f"Garbage_Matte_{matte_type.title()}"

    # 垃圾遮罩参数配置 - 粗略处理
    # alpha.blur: 较大值产生柔和边缘
    roto.property("alpha.blur").setValue(blur, 0)
    # antialias: 1.0 标准抗锯齿
    roto.property("antialias").setValue(1.0, 0)
    # fill: 启用填充
    roto.property("fill").setValue(True, 0)
    # stroke: 关闭描边
    roto.property("stroke").setValue(False, 0)
    # matte.mode: 使用 Alpha 通道
    roto.property("matte.mode").setValue("alpha", 0)
    # matte.invert: 是否反转（用于排除区域）
    roto.property("matte.invert").setValue(invert, 0)
    # motionBlur: 垃圾遮罩通常不需要运动模糊
    roto.property("motionBlur").setValue(False, 0)

    session.addNode(roto)

    # 创建垃圾遮罩形状
    shape = create_garbage_shape(matte_type, feather)
    if shape:
        print(f"[SILHOUETTE] 垃圾遮罩形状已创建: {matte_type}")

    # 输出节点
    out_node = Node("OutputNode")
    out_node.property("path").setValue(output_path.replace("\\", "/"), 0)
    out_node.property("format").setValue("exr", 0)
    out_node.property("compression").setValue("none", 0)
    out_node.property("depth").setValue("16f", 0)
    out_node.property("channels").setValue("rgba", 0)
    session.addNode(out_node)

    # 节点连接
    src.outputs[0].connect(roto.inputs[1])
    roto.outputs[0].connect(out_node.inputs[0])

    print("[SILHOUETTE] 垃圾遮罩流程已创建")
    print(f"[SILHOUETTE] 源素材: {source_path}")
    print(f"[SILHOUETTE] 输出路径: {output_path}")
    print(f"[SILHOUETTE] 遮罩类型: {matte_type}")
    print(f"[SILHOUETTE] 参数: feather={feather}, blur={blur}, "
          f"invert={invert}")

    return roto


def create_garbage_shape(matte_type="rectangle", feather=5.0):
    """创建垃圾遮罩形状

    参数:
        matte_type: 遮罩类型
            "rectangle" - 矩形
            "ellipse" - 椭圆
            "freeform" - 自由形状
        feather: 边缘羽化值

    返回:
        shape: 创建的形状对象
    """
    if matte_type == "rectangle":
        # 矩形遮罩 - 最快速的排除方式
        shape = createObject("Rectangle")
        shape.name = "Garbage_Rectangle"
        shape.feather = feather

    elif matte_type == "ellipse":
        # 椭圆遮罩 - 适合圆形区域
        shape = createObject("Ellipse")
        shape.name = "Garbage_Ellipse"
        shape.feather = feather

    elif matte_type == "freeform":
        # 自由形状 - 多边形排除
        shape = createObject("X-Spline")
        shape.name = "Garbage_Freeform"
        shape.closed = True
        shape.feather = feather

    else:
        # 默认使用矩形
        shape = createObject("Rectangle")
        shape.name = "Garbage_Default"
        shape.feather = feather

    return shape


def create_multi_garbage_matte(roto_node, regions):
    """创建多个垃圾遮罩区域

    用于排除多个不需要的区域。

    参数:
        roto_node: Roto 节点实例
        regions: 区域配置列表
            [
                {
                    "type": "rectangle",
                    "name": "Exclude_Top",
                    "feather": 5.0
                },
                {
                    "type": "ellipse",
                    "name": "Exclude_BottomLeft",
                    "feather": 3.0
                }
            ]
    """
    shapes = []

    for region in regions:
        shape = create_garbage_shape(
            region.get("type", "rectangle"),
            region.get("feather", 5.0)
        )
        shape.name = region.get("name", f"Garbage_{len(shapes)}")
        shapes.append(shape)

        print(f"[SILHOUETTE] 创建垃圾遮罩: {shape.name} "
              f"(类型: {region.get('type', 'rectangle')})")

    print(f"[SILHOUETTE] 共创建 {len(shapes)} 个垃圾遮罩区域")
    return shapes


def apply_garbage_preset(roto_node, preset="quick_exclude"):
    """应用垃圾遮罩预设

    参数:
        roto_node: Roto 节点实例
        preset: 预设类型
            "quick_exclude" - 快速排除（大羽化）
            "tight_bounds" - 紧凑边界（小羽化）
            "soft_blend" - 柔和混合（超大羽化）
    """
    presets = {
        "quick_exclude": {
            "alpha.blur": 2.0,
            "antialias": 1.0,
            "description": "快速排除预设 - 大羽化快速清理"
        },
        "tight_bounds": {
            "alpha.blur": 0.5,
            "antialias": 1.0,
            "description": "紧凑边界预设 - 较小羽化精确限定"
        },
        "soft_blend": {
            "alpha.blur": 5.0,
            "antialias": 1.0,
            "description": "柔和混合预设 - 超大羽化自然过渡"
        }
    }

    config = presets.get(preset, presets["quick_exclude"])

    roto_node.property("alpha.blur").setValue(config["alpha.blur"], 0)
    roto_node.property("antialias").setValue(config["antialias"], 0)

    print(f"[SILHOUETTE] 已应用预设: {preset}")
    print(f"  {config['description']}")


def link_to_fine_roto(garbage_roto, fine_roto):
    """将垃圾遮罩连接到精细 Roto 节点

    垃圾遮罩作为精细 Roto 的 obey_matte 输入，
    限定精细 Roto 的工作范围。

    参数:
        garbage_roto: 垃圾遮罩 Roto 节点
        fine_roto: 精细 Roto 节点
    """
    # 垃圾遮罩输出连接到精细 Roto 的 obey_matte 输入（索引 0）
    garbage_roto.outputs[0].connect(fine_roto.inputs[0])

    print("[SILHOUETTE] 垃圾遮罩已连接到精细 Roto")
    print(f"  {garbage_roto.label} → {fine_roto.label} (obey_matte)")


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3:
        create_pipeline(sys.argv[1], sys.argv[2])
    else:
        print("Usage: garbage_matte.py <source_path> <output_path>")
        print("Example: garbage_matte.py D:/footage/scene.mov "
              "D:/output/garbage_[####].exr")
        print("\n可选参数:")
        print("  --type=rectangle|ellipse|freeform")
        print("  --feather=5.0")
        print("  --invert=true|false")
