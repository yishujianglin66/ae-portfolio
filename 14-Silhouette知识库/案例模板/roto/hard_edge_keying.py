# Hard Edge Keying Template
# 硬边抠像模板 - 适用于产品、建筑、车辆等硬边物体
#
# 特点:
#   - 极低的边缘模糊（alpha.blur = 0.0-0.1）
#   - 抗锯齿保持锐利（antialias = 1.0）
#   - 使用 Bezier 曲线获得精确控制
#   - 不启用运动模糊（静态或匀速运动）
#   - 适用场景: 产品广告、建筑可视化、机械零件

from fx import *
import os


def create_pipeline(source_path, output_path, frame_rate=30.0,
                    feather=0.0, blur=0.1, invert=False):
    """创建硬边抠像流程

    参数:
        source_path: 源素材路径
        output_path: 输出遮罩路径（如 D:/output/matte_[####].exr）
        frame_rate: 帧率，默认 30.0
        feather: 边缘羽化值，默认 0.0（完全硬边）
        blur: alpha 模糊值，默认 0.1（轻微抗锯齿）
        invert: 是否反转遮罩，默认 False
    """
    # 创建或获取活动项目
    proj = activeProject() or Project()
    activate(proj)

    # 创建或获取活动会话
    session = activeSession() or Session()
    session.label = "Hard_Edge_Keying"
    activate(session)
    proj.addItem(session)

    # 源节点 - 加载原始素材
    src = Node("SourceNode")
    src.property("mediaPath").setValue(source_path.replace("\\", "/"), 0)
    src.property("frameRate").setValue(frame_rate, 0)
    session.addNode(src)

    # Roto 节点 - 主抠像节点
    roto = Node("RotoNode")
    roto.label = "Hard_Edge_Roto"

    # 硬边抠像核心参数配置
    # alpha.blur: 极低值保持锐利边缘
    roto.property("alpha.blur").setValue(blur, 0)
    # antialias: 1.0 保持边缘清晰
    roto.property("antialias").setValue(1.0, 0)
    # fill: 启用填充
    roto.property("fill").setValue(True, 0)
    # stroke: 关闭描边
    roto.property("stroke").setValue(False, 0)
    # matte.mode: 使用 Alpha 通道
    roto.property("matte.mode").setValue("alpha", 0)
    # matte.invert: 是否反转
    roto.property("matte.invert").setValue(invert, 0)
    # motionBlur: 硬边物体通常不需要运动模糊
    roto.property("motionBlur").setValue(False, 0)

    session.addNode(roto)

    # 输出节点 - 导出遮罩序列
    out_node = Node("OutputNode")
    out_node.property("path").setValue(output_path.replace("\\", "/"), 0)
    out_node.property("format").setValue("exr", 0)
    out_node.property("compression").setValue("none", 0)
    out_node.property("depth").setValue("16f", 0)
    out_node.property("channels").setValue("rgba", 0)
    session.addNode(out_node)

    # 节点连接：源 → Roto（foreground） → 输出
    src.outputs[0].connect(roto.inputs[1])
    roto.outputs[0].connect(out_node.inputs[0])

    print("[SILHOUETTE] 硬边抠像流程已创建")
    print(f"[SILHOUETTE] 源素材: {source_path}")
    print(f"[SILHOUETTE] 输出路径: {output_path}")
    print(f"[SILHOUETTE] 参数: feather={feather}, blur={blur}, "
          f"invert={invert}")

    return roto


def apply_hard_edge_preset(roto_node, preset="product"):
    """应用硬边抠像预设

    参数:
        roto_node: Roto 节点实例
        preset: 预设类型
            "product" - 产品广告（最锐利）
            "architecture" - 建筑（轻微羽化）
            "vehicle" - 车辆（标准硬边）
            "mechanical" - 机械零件（完全硬边）
    """
    presets = {
        "product": {
            "alpha.blur": 0.0,
            "antialias": 1.0,
            "description": "产品广告预设 - 完全锐利边缘"
        },
        "architecture": {
            "alpha.blur": 0.2,
            "antialias": 1.0,
            "description": "建筑预设 - 轻微抗锯齿"
        },
        "vehicle": {
            "alpha.blur": 0.1,
            "antialias": 1.0,
            "description": "车辆预设 - 标准硬边"
        },
        "mechanical": {
            "alpha.blur": 0.0,
            "antialias": 0.5,
            "description": "机械零件预设 - 极致硬边"
        }
    }

    config = presets.get(preset, presets["product"])

    roto_node.property("alpha.blur").setValue(config["alpha.blur"], 0)
    roto_node.property("antialias").setValue(config["antialias"], 0)

    print(f"[SILHOUETTE] 已应用预设: {preset}")
    print(f"  {config['description']}")
    print(f"  alpha.blur: {config['alpha.blur']}")
    print(f"  antialias: {config['antialias']}")


def create_bezier_shape(roto_node, shape_name="HardEdge_Shape"):
    """创建 Bezier 形状（适用于硬边物体）

    Bezier 曲线提供精确的边缘控制，适合硬边物体的抠像。
    """
    # 使用 createObject 创建形状（不能直接实例化 Object 类）
    shape = createObject("Bezier")
    shape.name = shape_name
    shape.closed = True

    print(f"[SILHOUETTE] Bezier 形状已创建: {shape_name}")
    return shape


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3:
        create_pipeline(sys.argv[1], sys.argv[2])
    else:
        print("Usage: hard_edge_keying.py <source_path> <output_path>")
        print("Example: hard_edge_keying.py D:/footage/product.mov "
              "D:/output/matte_[####].exr")
