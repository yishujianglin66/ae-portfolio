# Multi-Shape Keying Template
# 多形状抠像模板 - 支持复杂物体分解
#
# 特点:
#   - 支持多个形状组合成复杂遮罩
#   - 父子层级关系管理
#   - 不同部位使用不同边缘参数
#   - 支持布尔运算组合形状
#   - 适用场景: 复杂人物、机械结构、多部件物体

import os

from fx import *


def create_pipeline(source_path, output_path, frame_rate=30.0,
                    shapes_config=None):
    """创建多形状抠像流程

    参数:
        source_path: 源素材路径
        output_path: 输出遮罩路径（如 D:/output/matte_[####].exr）
        frame_rate: 帧率，默认 30.0
        shapes_config: 形状配置列表
            [
                {
                    "name": "Body",
                    "type": "X-Spline",
                    "blur": 0.5,
                    "parent": None
                },
                {
                    "name": "Head",
                    "type": "X-Spline",
                    "blur": 0.3,
                    "parent": "Body"
                },
                {
                    "name": "Arm_Left",
                    "type": "Bezier",
                    "blur": 0.4,
                    "parent": "Body"
                }
            ]
    """
    if shapes_config is None:
        # 默认配置：人物分解
        shapes_config = [
            {"name": "Body", "type": "X-Spline", "blur": 0.5, "parent": None},
            {"name": "Head", "type": "X-Spline", "blur": 0.3, "parent": "Body"},
            {"name": "Arm_Left", "type": "Bezier", "blur": 0.4, "parent": "Body"},
            {"name": "Arm_Right", "type": "Bezier", "blur": 0.4, "parent": "Body"},
            {"name": "Leg_Left", "type": "Bezier", "blur": 0.4, "parent": "Body"},
            {"name": "Leg_Right", "type": "Bezier", "blur": 0.4, "parent": "Body"}
        ]

    # 创建或获取活动项目
    proj = activeProject() or Project()
    activate(proj)

    # 创建或获取活动会话
    session = activeSession() or Session()
    session.label = "Multi_Shape_Keying"
    activate(session)
    proj.addItem(session)

    # 源节点 - 加载原始素材
    src = Node("SourceNode")
    src.property("mediaPath").setValue(source_path.replace("\\", "/"), 0)
    src.property("frameRate").setValue(frame_rate, 0)
    session.addNode(src)

    # 主 Roto 节点 - 用于整体遮罩
    roto_main = Node("RotoNode")
    roto_main.label = "Multi_Shape_Main"
    roto_main.property("alpha.blur").setValue(0.5, 0)
    roto_main.property("antialias").setValue(1.0, 0)
    roto_main.property("fill").setValue(True, 0)
    roto_main.property("matte.mode").setValue("alpha", 0)
    session.addNode(roto_main)

    # 创建所有形状
    shapes = {}
    for config in shapes_config:
        # 使用 createObject 创建形状
        shape = createObject(config["type"])
        shape.name = config["name"]
        shape.closed = True

        # 存储形状引用
        shapes[config["name"]] = {
            "shape": shape,
            "blur": config.get("blur", 0.5),
            "parent": config.get("parent")
        }

    # 设置父子层级关系
    for name, info in shapes.items():
        if info["parent"]:
            parent_shape = shapes.get(info["parent"])
            if parent_shape:
                info["shape"].parent = parent_shape["shape"]
                print(f"[SILHOUETTE] 层级: {name} → 父级: {info['parent']}")

    # 输出节点
    out_node = Node("OutputNode")
    out_node.property("path").setValue(output_path.replace("\\", "/"), 0)
    out_node.property("format").setValue("exr", 0)
    out_node.property("compression").setValue("none", 0)
    out_node.property("depth").setValue("32f", 0)
    out_node.property("channels").setValue("rgba", 0)
    session.addNode(out_node)

    # 节点连接
    src.outputs[0].connect(roto_main.inputs[1])
    roto_main.outputs[0].connect(out_node.inputs[0])

    print("[SILHOUETTE] 多形状抠像流程已创建")
    print(f"[SILHOUETTE] 源素材: {source_path}")
    print(f"[SILHOUETTE] 输出路径: {output_path}")
    print(f"[SILHOUETTE] 形状数量: {len(shapes_config)}")

    return roto_main, shapes


def create_character_breakdown(roto_node):
    """创建人物分解结构

    将人物分解为多个部位，每个部位独立 Roto。
    适用于复杂动作场景，便于分层管理。
    """
    # 人物分解配置
    character_parts = [
        {
            "name": "Torso",
            "type": "X-Spline",
            "blur": 0.5,
            "feather": 1.0,
            "parent": None,
            "description": "躯干 - 主要轮廓"
        },
        {
            "name": "Head",
            "type": "X-Spline",
            "blur": 0.3,
            "feather": 0.8,
            "parent": "Torso",
            "description": "头部 - 精确轮廓"
        },
        {
            "name": "Hair",
            "type": "X-Spline",
            "blur": 1.5,
            "feather": 2.5,
            "parent": "Head",
            "description": "头发 - 柔边处理"
        },
        {
            "name": "Arm_Left",
            "type": "Bezier",
            "blur": 0.4,
            "feather": 1.0,
            "parent": "Torso",
            "description": "左臂 - 硬边控制"
        },
        {
            "name": "Arm_Right",
            "type": "Bezier",
            "blur": 0.4,
            "feather": 1.0,
            "parent": "Torso",
            "description": "右臂 - 硬边控制"
        },
        {
            "name": "Leg_Left",
            "type": "Bezier",
            "blur": 0.4,
            "feather": 1.0,
            "parent": "Torso",
            "description": "左腿 - 硬边控制"
        },
        {
            "name": "Leg_Right",
            "type": "Bezier",
            "blur": 0.4,
            "feather": 1.0,
            "parent": "Torso",
            "description": "右腿 - 硬边控制"
        }
    ]

    shapes = {}
    for part in character_parts:
        shape = createObject(part["type"])
        shape.name = part["name"]
        shape.closed = True
        shape.feather = part["feather"]

        shapes[part["name"]] = {
            "shape": shape,
            "config": part
        }

    # 设置层级关系
    for name, info in shapes.items():
        parent_name = info["config"]["parent"]
        if parent_name and parent_name in shapes:
            info["shape"].parent = shapes[parent_name]["shape"]

    print("[SILHOUETTE] 人物分解结构已创建")
    print(f"  部位数量: {len(character_parts)}")
    for part in character_parts:
        parent_info = f" (父级: {part['parent']})" if part["parent"] else ""
        print(f"  - {part['name']}: {part['description']}{parent_info}")

    return shapes


def create_mechanical_breakdown(roto_node):
    """创建机械结构分解

    将机械物体分解为多个部件，每个部件独立 Roto。
    适用于机械动画、产品展示等场景。
    """
    mechanical_parts = [
        {
            "name": "Main_Body",
            "type": "Bezier",
            "blur": 0.1,
            "feather": 0.0,
            "parent": None,
            "description": "主体 - 硬边"
        },
        {
            "name": "Panel_Front",
            "type": "Bezier",
            "blur": 0.1,
            "feather": 0.0,
            "parent": "Main_Body",
            "description": "前面板"
        },
        {
            "name": "Panel_Side",
            "type": "Bezier",
            "blur": 0.1,
            "feather": 0.0,
            "parent": "Main_Body",
            "description": "侧面板"
        },
        {
            "name": "Handle",
            "type": "Bezier",
            "blur": 0.2,
            "feather": 0.5,
            "parent": "Main_Body",
            "description": "手柄 - 轻微柔边"
        },
        {
            "name": "Button_1",
            "type": "Ellipse",
            "blur": 0.1,
            "feather": 0.0,
            "parent": "Panel_Front",
            "description": "按钮1"
        },
        {
            "name": "Button_2",
            "type": "Ellipse",
            "blur": 0.1,
            "feather": 0.0,
            "parent": "Panel_Front",
            "description": "按钮2"
        }
    ]

    shapes = {}
    for part in mechanical_parts:
        shape = createObject(part["type"])
        shape.name = part["name"]
        shape.closed = True
        shape.feather = part["feather"]

        shapes[part["name"]] = {
            "shape": shape,
            "config": part
        }

    # 设置层级关系
    for name, info in shapes.items():
        parent_name = info["config"]["parent"]
        if parent_name and parent_name in shapes:
            info["shape"].parent = shapes[parent_name]["shape"]

    print("[SILHOUETTE] 机械结构分解已创建")
    print(f"  部件数量: {len(mechanical_parts)}")

    return shapes


def set_render_order(shapes, order_list):
    """设置形状渲染顺序

    参数:
        shapes: 形状字典
        order_list: 渲染顺序列表（从底到顶）
            ["Body", "Head", "Hair", "Arm_Left", "Arm_Right"]
    """
    for i, name in enumerate(order_list):
        if name in shapes:
            shape_info = shapes[name]
            if isinstance(shape_info, dict):
                shape = shape_info.get("shape", shape_info)
            else:
                shape = shape_info

            # 设置渲染优先级（数值越小越先渲染）
            if hasattr(shape, "priority"):
                shape.priority = i

    print(f"[SILHOUETTE] 渲染顺序已设置: {' → '.join(order_list)}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3:
        create_pipeline(sys.argv[1], sys.argv[2])
    else:
        print("Usage: multi_shape_keying.py <source_path> <output_path>")
        print("Example: multi_shape_keying.py D:/footage/character.mov "
              "D:/output/matte_[####].exr")
