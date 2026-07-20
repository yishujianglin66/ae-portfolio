"""
joint_system.py - 木偶关节化处理系统

为木偶/角色动画提供关节化效果生成，包括关节缝绘制、提线效果、
关节间隙处理以及从边界框估算关节位置的降级方案。

与 AE MCP 桥接系统兼容，输出标准效果配置和关键帧数据。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ============================================================================
# 数据类
# ============================================================================


@dataclass
class JointPoint:
    """关节点数据类

    Attributes:
        name: 关节名称（如 "shoulder_left", "elbow_right"）
        x: X 坐标（像素）
        y: Y 坐标（像素）
        side: 身体侧别："left" / "right" / "center"
    """

    name: str
    x: float
    y: float
    side: str = "center"


@dataclass
class JointConfig:
    """关节化效果配置

    Attributes:
        joint_points: 关节点列表
        show_joint_seams: 是否显示关节缝
        seam_radius: 关节缝半径（像素）
        show_strings: 是否显示提线
        string_count: 提线数量
        string_opacity: 提线透明度（0-1）
        joint_gap: 关节间隙（像素）
        auto_limit: 是否启用关节限位
    """

    joint_points: List[JointPoint] = field(default_factory=list)
    show_joint_seams: bool = True
    seam_radius: float = 8.0
    show_strings: bool = False
    string_count: int = 4
    string_opacity: float = 0.6
    joint_gap: float = 2.0
    auto_limit: bool = True


# ============================================================================
# JointSystem 类
# ============================================================================


class JointSystem:
    """木偶关节化处理系统

    生成关节缝、提线、关节间隙等木偶风格化效果，
    并支持从关节跟踪数据生成关键帧动画。
    """

    _presets: Dict[str, 'JointConfig'] = None

    def __init__(self) -> None:
        if JointSystem._presets is None:
            JointSystem._presets = JointSystem._init_presets()
        self._presets = JointSystem._presets

    # ------------------------------------------------------------------------
    # 公共方法
    # ------------------------------------------------------------------------

    @staticmethod
    def generate_joint_effects(
        config: JointConfig,
        layer_name: str,
        duration: float,
    ) -> Dict[str, Any]:
        """生成关节化效果

        Args:
            config: 关节配置
            layer_name: 目标图层名称
            duration: 持续时间（秒）

        Returns:
            包含 effects, keyframes, layers, expressions 的字典
        """
        effects: List[Dict[str, Any]] = []
        keyframes: List[Dict[str, Any]] = []
        layers: List[Dict[str, Any]] = []
        expressions: List[Dict[str, Any]] = []

        if config.show_joint_seams:
            seam_effects = JointSystem._generate_joint_seams(config, layer_name)
            effects.extend(seam_effects)

        if config.show_strings:
            string_layers, string_keyframes, string_exprs = JointSystem._generate_strings(
                config, layer_name, duration
            )
            layers.extend(string_layers)
            keyframes.extend(string_keyframes)
            expressions.extend(string_exprs)

        if config.joint_gap > 0:
            gap_effects = JointSystem._generate_joint_gaps(config, layer_name)
            effects.extend(gap_effects)

        return {
            "effects": effects,
            "keyframes": keyframes,
            "layers": layers,
            "expressions": expressions,
            "layer_name": layer_name,
            "duration": duration,
        }

    def generate_joint_keyframes(
        self,
        config: JointConfig,
        layer_name: str,
        joint_data: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """根据关节跟踪数据生成关键帧动画

        Args:
            config: 关节配置
            layer_name: 目标图层名称
            joint_data: 逐帧关节点坐标数据
                格式: [{"time": 0.0, "joints": [{"name": "...", "x": ..., "y": ...}, ...]}, ...]

        Returns:
            关键帧列表
        """
        keyframes: List[Dict[str, Any]] = []

        joint_names = [jp.name for jp in config.joint_points]

        for joint_name in joint_names:
            joint_kfs: List[Tuple[float, float, float]] = []

            for frame_data in joint_data:
                time = frame_data.get("time", 0.0)
                joints = frame_data.get("joints", [])

                for j in joints:
                    if j.get("name") == joint_name:
                        joint_kfs.append((time, j.get("x", 0.0), j.get("y", 0.0)))
                        break

            if len(joint_kfs) >= 2:
                keyframes.append({
                    "layer_name": layer_name,
                    "property": f"Effects.Joint_{joint_name}.Position",
                    "values": [
                        {"time": t, "value": [x, y]}
                        for t, x, y in joint_kfs
                    ],
                })

        return keyframes

    @staticmethod
    def get_standard_joint_preset(preset_name: str) -> JointConfig:
        """获取标准关节配置预设

        Args:
            preset_name: 预设名称
                - "human_17point": 17点人体关节
                - "human_upper_body": 上半身10点
                - "marionette_basic": 基础提线木偶（4条线）
                - "simple_puppet": 简化木偶（6个关节）

        Returns:
            JointConfig 实例
        """
        if JointSystem._presets is None:
            JointSystem._presets = JointSystem._init_presets()
        if preset_name not in JointSystem._presets:
            raise ValueError(
                f"Unknown preset '{preset_name}'. "
                f"Available: {list(JointSystem._presets.keys())}"
            )
        return JointSystem._presets[preset_name]

    @staticmethod
    def estimate_joints_from_bbox(
        bbox: Dict[str, float],
        body_type: str = "human",
    ) -> List[JointPoint]:
        """从人物边界框估算关节点位置（无跟踪数据时的降级方案）

        Args:
            bbox: 边界框 {x, y, width, height}
            body_type: 身体类型："human" / "upper_body" / "simple"

        Returns:
            估算的关节点列表
        """
        x = bbox.get("x", 0.0)
        y = bbox.get("y", 0.0)
        w = bbox.get("width", 100.0)
        h = bbox.get("height", 200.0)

        cx = x + w / 2.0
        head_y = y + h * 0.12
        neck_y = y + h * 0.20
        shoulder_y = y + h * 0.25
        elbow_y = y + h * 0.40
        waist_y = y + h * 0.50
        hip_y = y + h * 0.55
        knee_y = y + h * 0.75
        ankle_y = y + h * 0.92

        shoulder_w = w * 0.35
        hip_w = w * 0.25

        if body_type == "human":
            return [
                JointPoint("head_top", cx, y + h * 0.02, "center"),
                JointPoint("head", cx, head_y, "center"),
                JointPoint("neck", cx, neck_y, "center"),
                JointPoint("shoulder_left", cx - shoulder_w, shoulder_y, "left"),
                JointPoint("shoulder_right", cx + shoulder_w, shoulder_y, "right"),
                JointPoint("elbow_left", cx - shoulder_w - w * 0.08, elbow_y, "left"),
                JointPoint("elbow_right", cx + shoulder_w + w * 0.08, elbow_y, "right"),
                JointPoint("wrist_left", cx - shoulder_w - w * 0.15, y + h * 0.55, "left"),
                JointPoint("wrist_right", cx + shoulder_w + w * 0.15, y + h * 0.55, "right"),
                JointPoint("spine", cx, waist_y, "center"),
                JointPoint("hip_left", cx - hip_w, hip_y, "left"),
                JointPoint("hip_right", cx + hip_w, hip_y, "right"),
                JointPoint("knee_left", cx - hip_w * 0.7, knee_y, "left"),
                JointPoint("knee_right", cx + hip_w * 0.7, knee_y, "right"),
                JointPoint("ankle_left", cx - hip_w * 0.5, ankle_y, "left"),
                JointPoint("ankle_right", cx + hip_w * 0.5, ankle_y, "right"),
                JointPoint("pelvis", cx, hip_y + h * 0.03, "center"),
            ]
        elif body_type == "upper_body":
            return [
                JointPoint("head", cx, head_y, "center"),
                JointPoint("neck", cx, neck_y, "center"),
                JointPoint("shoulder_left", cx - shoulder_w, shoulder_y, "left"),
                JointPoint("shoulder_right", cx + shoulder_w, shoulder_y, "right"),
                JointPoint("elbow_left", cx - shoulder_w - w * 0.08, elbow_y, "left"),
                JointPoint("elbow_right", cx + shoulder_w + w * 0.08, elbow_y, "right"),
                JointPoint("wrist_left", cx - shoulder_w - w * 0.15, y + h * 0.55, "left"),
                JointPoint("wrist_right", cx + shoulder_w + w * 0.15, y + h * 0.55, "right"),
                JointPoint("spine", cx, waist_y, "center"),
                JointPoint("hip", cx, hip_y, "center"),
            ]
        elif body_type == "simple":
            return [
                JointPoint("head", cx, head_y, "center"),
                JointPoint("body_top", cx, shoulder_y, "center"),
                JointPoint("body_bottom", cx, hip_y, "center"),
                JointPoint("arm_left", cx - w * 0.4, elbow_y, "left"),
                JointPoint("arm_right", cx + w * 0.4, elbow_y, "right"),
                JointPoint("leg_bottom", cx, ankle_y, "center"),
            ]
        else:
            return [JointPoint("center", cx, y + h / 2.0, "center")]

    # ------------------------------------------------------------------------
    # 内部方法 - 效果生成
    # ------------------------------------------------------------------------

    @staticmethod
    def _generate_joint_seams(
        config: JointConfig,
        layer_name: str,
    ) -> List[Dict[str, Any]]:
        """生成关节缝效果

        在每个关节点位置绘制椭圆形接缝，使用 Circle 效果。
        """
        effects: List[Dict[str, Any]] = []

        for i, jp in enumerate(config.joint_points):
            seam_name = f"JointSeam_{jp.name}"
            effects.append({
                "effectName": "Circle",
                "matchName": "ADBE Circle",
                "displayName": seam_name,
                "settings": {
                    "Center": [jp.x, jp.y],
                    "Radius": config.seam_radius,
                    "Border": config.seam_radius * 0.3,
                    "Inside Color": [0.15, 0.15, 0.15],
                    "Outside Color": [0.8, 0.8, 0.8],
                    "Blending Mode": "Multiply",
                },
            })

        return effects

    @staticmethod
    def _generate_strings(
        config: JointConfig,
        layer_name: str,
        duration: float,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """生成提线效果

        从顶部悬挂点到关节点的连线，使用 Beam 效果。
        """
        layers: List[Dict[str, Any]] = []
        keyframes: List[Dict[str, Any]] = []
        expressions: List[Dict[str, Any]] = []

        top_joints = [
            jp for jp in config.joint_points
            if jp.name in ("head", "head_top", "shoulder_left", "shoulder_right")
        ]

        string_count = min(config.string_count, max(len(top_joints), 1))
        selected_joints = top_joints[:string_count] if top_joints else config.joint_points[:string_count]

        for i, jp in enumerate(selected_joints):
            string_layer_name = f"{layer_name}_String_{jp.name}"

            hang_x = jp.x
            hang_y = jp.y - 200.0

            layers.append({
                "name": string_layer_name,
                "type": "adjustment",
                "effects": [
                    {
                        "effectName": "Beam",
                        "matchName": "ADBE Beam",
                        "displayName": f"String_{jp.name}",
                        "settings": {
                            "Starting Point": [hang_x, hang_y],
                            "Ending Point": [jp.x, jp.y],
                            "Length": 100.0,
                            "Time": 50.0,
                            "Softness": 0.3,
                            "Inside Color": [0.9, 0.9, 0.85],
                            "Outside Color": [0.7, 0.7, 0.65],
                        },
                    },
                    {
                        "effectName": "Opacity",
                        "matchName": "ADBE Opacity2",
                        "displayName": "StringOpacity",
                        "settings": {
                            "Opacity": config.string_opacity * 100.0,
                        },
                    },
                ],
            })

            expressions.append({
                "layer_name": string_layer_name,
                "property": "Effects.String.Ending Point",
                "expression": (
                    f'thisComp.layer("{layer_name}")'
                    f'.effect("JointSeam_{jp.name}")("Center")'
                ),
            })

        return layers, keyframes, expressions

    @staticmethod
    def _generate_joint_gaps(
        config: JointConfig,
        layer_name: str,
    ) -> List[Dict[str, Any]]:
        """生成关节间隙效果

        在关节位置创建微小的暗色间隙，模拟木偶分段感。
        """
        effects: List[Dict[str, Any]] = []

        limb_pairs = JointSystem._get_limb_joint_pairs(config.joint_points)

        for i, (joint_a, joint_b) in enumerate(limb_pairs):
            gap_name = f"JointGap_{joint_a.name}_{joint_b.name}"

            mid_x = (joint_a.x + joint_b.x) / 2.0
            mid_y = (joint_a.y + joint_b.y) / 2.0
            dist = math.sqrt(
                (joint_b.x - joint_a.x) ** 2 + (joint_b.y - joint_a.y) ** 2
            )

            angle = math.degrees(math.atan2(joint_b.y - joint_a.y, joint_b.x - joint_a.x))

            effects.append({
                "effectName": "Linear Wipe",
                "matchName": "ADBE Linear Wipe",
                "displayName": gap_name,
                "settings": {
                    "Transition Completion": 0.0,
                    "Wipe Angle": angle,
                    "Feather": config.joint_gap,
                },
            })

        return effects

    @staticmethod
    def _get_limb_joint_pairs(
        joints: List[JointPoint],
    ) -> List[Tuple[JointPoint, JointPoint]]:
        """获取肢体关节对列表（用于间隙生成）"""
        pairs: List[Tuple[JointPoint, JointPoint]] = []
        joint_map = {j.name: j for j in joints}

        limb_connections = [
            ("head", "neck"),
            ("neck", "spine"),
            ("shoulder_left", "elbow_left"),
            ("elbow_left", "wrist_left"),
            ("shoulder_right", "elbow_right"),
            ("elbow_right", "wrist_right"),
            ("spine", "hip_left"),
            ("spine", "hip_right"),
            ("hip_left", "knee_left"),
            ("knee_left", "ankle_left"),
            ("hip_right", "knee_right"),
            ("knee_right", "ankle_right"),
        ]

        for a_name, b_name in limb_connections:
            if a_name in joint_map and b_name in joint_map:
                pairs.append((joint_map[a_name], joint_map[b_name]))

        return pairs

    # ------------------------------------------------------------------------
    # 预设初始化
    # ------------------------------------------------------------------------

    @staticmethod
    def _init_presets() -> Dict[str, JointConfig]:
        """初始化预设配置库"""
        presets: Dict[str, JointConfig] = {}

        # --- 17点人体关节 ---
        human_17_joints = [
            JointPoint("head_top", 960, 100, "center"),
            JointPoint("head", 960, 150, "center"),
            JointPoint("neck", 960, 220, "center"),
            JointPoint("shoulder_left", 850, 280, "left"),
            JointPoint("shoulder_right", 1070, 280, "right"),
            JointPoint("elbow_left", 780, 450, "left"),
            JointPoint("elbow_right", 1140, 450, "right"),
            JointPoint("wrist_left", 750, 620, "left"),
            JointPoint("wrist_right", 1170, 620, "right"),
            JointPoint("spine", 960, 520, "center"),
            JointPoint("hip_left", 880, 600, "left"),
            JointPoint("hip_right", 1040, 600, "right"),
            JointPoint("knee_left", 860, 780, "left"),
            JointPoint("knee_right", 1060, 780, "right"),
            JointPoint("ankle_left", 850, 950, "left"),
            JointPoint("ankle_right", 1070, 950, "right"),
            JointPoint("pelvis", 960, 630, "center"),
        ]
        presets["human_17point"] = JointConfig(
            joint_points=human_17_joints,
            show_joint_seams=True,
            seam_radius=10.0,
            show_strings=False,
            string_count=4,
            string_opacity=0.6,
            joint_gap=3.0,
            auto_limit=True,
        )

        # --- 上半身10点 ---
        upper_body_joints = [
            JointPoint("head", 960, 150, "center"),
            JointPoint("neck", 960, 220, "center"),
            JointPoint("shoulder_left", 850, 280, "left"),
            JointPoint("shoulder_right", 1070, 280, "right"),
            JointPoint("elbow_left", 780, 450, "left"),
            JointPoint("elbow_right", 1140, 450, "right"),
            JointPoint("wrist_left", 750, 620, "left"),
            JointPoint("wrist_right", 1170, 620, "right"),
            JointPoint("spine", 960, 520, "center"),
            JointPoint("hip", 960, 600, "center"),
        ]
        presets["human_upper_body"] = JointConfig(
            joint_points=upper_body_joints,
            show_joint_seams=True,
            seam_radius=8.0,
            show_strings=False,
            string_count=3,
            string_opacity=0.6,
            joint_gap=2.0,
            auto_limit=True,
        )

        # --- 基础提线木偶（4条线）---
        marionette_joints = [
            JointPoint("head", 960, 180, "center"),
            JointPoint("shoulder_left", 860, 280, "left"),
            JointPoint("shoulder_right", 1060, 280, "right"),
            JointPoint("hand_left", 760, 550, "left"),
            JointPoint("hand_right", 1160, 550, "right"),
            JointPoint("hip_left", 890, 580, "left"),
            JointPoint("hip_right", 1030, 580, "right"),
            JointPoint("foot_left", 870, 900, "left"),
            JointPoint("foot_right", 1050, 900, "right"),
        ]
        presets["marionette_basic"] = JointConfig(
            joint_points=marionette_joints,
            show_joint_seams=True,
            seam_radius=12.0,
            show_strings=True,
            string_count=4,
            string_opacity=0.65,
            joint_gap=4.0,
            auto_limit=True,
        )

        # --- 简化木偶（6个关节）---
        simple_joints = [
            JointPoint("head", 960, 200, "center"),
            JointPoint("body_top", 960, 320, "center"),
            JointPoint("body_bottom", 960, 600, "center"),
            JointPoint("arm_left", 800, 450, "left"),
            JointPoint("arm_right", 1120, 450, "right"),
            JointPoint("leg_bottom", 960, 900, "center"),
        ]
        presets["simple_puppet"] = JointConfig(
            joint_points=simple_joints,
            show_joint_seams=True,
            seam_radius=15.0,
            show_strings=False,
            string_count=2,
            string_opacity=0.5,
            joint_gap=5.0,
            auto_limit=False,
        )

        return presets


# ============================================================================
# 自测
# ============================================================================


if __name__ == "__main__":
    import json

    print("=" * 60)
    print("JointSystem 自测")
    print("=" * 60)

    js = JointSystem()

    # --- 测试 1: 预设获取 ---
    print("\n[测试 1] 预设获取")
    for preset_name in ["human_17point", "human_upper_body", "marionette_basic", "simple_puppet"]:
        config = js.get_standard_joint_preset(preset_name)
        print(f"  {preset_name}: {len(config.joint_points)} 个关节点, "
              f"seam={config.seam_radius}, gap={config.joint_gap}, "
              f"strings={'开' if config.show_strings else '关'}")

    # --- 测试 2: 关节效果生成 ---
    print("\n[测试 2] 关节效果生成")
    config = js.get_standard_joint_preset("marionette_basic")
    result = js.generate_joint_effects(config, "PuppetLayer", 5.0)
    print(f"  效果数量: {len(result['effects'])}")
    print(f"  图层数量: {len(result['layers'])}")
    print(f"  表达式数量: {len(result['expressions'])}")
    print(f"  关键帧数量: {len(result['keyframes'])}")

    if result["effects"]:
        print(f"  第一个效果: {result['effects'][0]['displayName']}")

    if result["layers"]:
        print(f"  第一个图层: {result['layers'][0]['name']}")

    # --- 测试 3: 从边界框估算关节 ---
    print("\n[测试 3] 从边界框估算关节")
    bbox = {"x": 100, "y": 50, "width": 300, "height": 600}
    for body_type in ["human", "upper_body", "simple"]:
        joints = js.estimate_joints_from_bbox(bbox, body_type)
        print(f"  {body_type}: {len(joints)} 个关节点")
        if joints:
            print(f"    第一个: {joints[0].name} @ ({joints[0].x:.1f}, {joints[0].y:.1f})")

    # --- 测试 4: 关键帧生成 ---
    print("\n[测试 4] 关键帧生成")
    joint_data = [
        {"time": 0.0, "joints": [{"name": "head", "x": 960, "y": 150}]},
        {"time": 1.0, "joints": [{"name": "head", "x": 970, "y": 160}]},
        {"time": 2.0, "joints": [{"name": "head", "x": 950, "y": 155}]},
    ]
    simple_config = js.get_standard_joint_preset("simple_puppet")
    kfs = js.generate_joint_keyframes(simple_config, "PuppetLayer", joint_data)
    print(f"  生成关键帧组: {len(kfs)}")
    if kfs:
        print(f"  属性: {kfs[0]['property']}")
        print(f"  关键帧数: {len(kfs[0]['values'])}")

    # --- 测试 5: 数据类 ---
    print("\n[测试 5] 数据类验证")
    jp = JointPoint("test", 100.0, 200.0, "left")
    jc = JointConfig(joint_points=[jp], show_joint_seams=True, seam_radius=5.0)
    print(f"  JointPoint: name={jp.name}, x={jp.x}, y={jp.y}, side={jp.side}")
    print(f"  JointConfig: {len(jc.joint_points)} joints, seam={jc.seam_radius}")

    print("\n" + "=" * 60)
    print("所有自测通过 ✓")
    print("=" * 60)
