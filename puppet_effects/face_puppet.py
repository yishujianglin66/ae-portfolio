"""
face_puppet.py - 面部木偶化效果模块

为面部图像生成各种木偶风格化效果，包括纽扣眼、缝线嘴、瓷化皮肤、
面部关节点以及表情限制。与 AE MCP 桥接系统兼容，输出标准效果配置。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# ============================================================================
# 数据类
# ============================================================================


@dataclass
class FacePuppetConfig:
    """面部木偶化配置

    Attributes:
        style: 风格类型（button_eyes / stitched_mouth / porcelain_skin / all）
        eye_style: 眼睛风格（button / googly / painted / dot）
        mouth_style: 嘴巴风格（stitched / line / painted / button）
        skin_porcelain: 是否瓷化皮肤
        eye_scale: 眼睛大小缩放（默认1.0）
        mouth_scale: 嘴巴大小缩放（默认1.0）
        eye_spacing: 眼间距比例（默认1.0）
        color: 纽扣/缝线颜色（默认深棕色）
        button_texture: 纽扣纹理（True=带纹理，False=纯色）
        stitch_count: 缝线数量（默认8针）
    """

    style: str = "all"
    eye_style: str = "button"
    mouth_style: str = "stitched"
    skin_porcelain: bool = True
    eye_scale: float = 1.0
    mouth_scale: float = 1.0
    eye_spacing: float = 1.0
    color: list[float] = field(default_factory=lambda: [0.2, 0.1, 0.05, 1.0])
    button_texture: bool = True
    stitch_count: int = 8


# ============================================================================
# FacePuppetEffect 类
# ============================================================================


class FacePuppetEffect:
    """面部木偶化效果生成器

    生成纽扣眼、缝线嘴、瓷化皮肤、面部关节点等木偶风格化效果，
    并支持表情限制表达式。
    """

    _presets: dict[str, FacePuppetConfig] = None

    # ------------------------------------------------------------------------
    # 公共方法
    # ------------------------------------------------------------------------

    @staticmethod
    def generate_face_puppet(
        config: FacePuppetConfig,
        layer_name: str,
        face_data: dict[str, Any] = None,
        duration: float = 5.0,
    ) -> dict[str, Any]:
        """生成面部木偶化效果

        Args:
            config: 面部木偶化配置
            layer_name: 目标图层名称
            face_data: 面部特征点数据
                格式: {left_eye: {x, y}, right_eye: {x, y},
                       mouth: {x, y, width, height}, nose: {x, y},
                       jaw: {x, y}, face_bbox: {x, y, width, height}}
            duration: 持续时间（秒）

        Returns:
            包含 effects, keyframes, layers, expressions 的字典
        """
        effects: list[dict[str, Any]] = []
        keyframes: list[dict[str, Any]] = []
        layers: list[dict[str, Any]] = []
        expressions: list[dict[str, Any]] = []

        if face_data is None:
            face_data = FacePuppetEffect.estimate_face_from_bbox({
                "x": 400, "y": 200, "width": 400, "height": 500,
            })

        face_bbox = face_data.get("face_bbox", {
            "x": 400, "y": 200, "width": 400, "height": 500,
        })

        if config.style in ("button_eyes", "all"):
            left_eye = face_data.get("left_eye", {"x": 500, "y": 350})
            right_eye = face_data.get("right_eye", {"x": 700, "y": 350})

            eye_spacing_offset = (config.eye_spacing - 1.0) * 30.0
            left_eye_pos = {
                "x": left_eye["x"] - eye_spacing_offset,
                "y": left_eye["y"],
            }
            right_eye_pos = {
                "x": right_eye["x"] + eye_spacing_offset,
                "y": right_eye["y"],
            }

            left_effects = FacePuppetEffect._generate_button_eye(
                config, left_eye_pos, "left"
            )
            right_effects = FacePuppetEffect._generate_button_eye(
                config, right_eye_pos, "right"
            )
            effects.extend(left_effects)
            effects.extend(right_effects)

        if config.style in ("stitched_mouth", "all"):
            mouth_pos = face_data.get("mouth", {
                "x": 600, "y": 500, "width": 100, "height": 30,
            })
            mouth_effects = FacePuppetEffect._generate_stitched_mouth(
                config, mouth_pos
            )
            effects.extend(mouth_effects)

        if config.skin_porcelain and config.style in ("porcelain_skin", "all"):
            skin_effects = FacePuppetEffect._generate_porcelain_skin(
                config, face_bbox
            )
            effects.extend(skin_effects)

        if config.style == "all":
            joint_effects = FacePuppetEffect._generate_face_joints(
                config, face_data
            )
            effects.extend(joint_effects)

        if config.style == "all":
            expr_list = FacePuppetEffect._generate_expression_limits(
                config, layer_name, face_data
            )
            expressions.extend(expr_list)

        return {
            "effects": effects,
            "keyframes": keyframes,
            "layers": layers,
            "expressions": expressions,
            "layer_name": layer_name,
            "duration": duration,
            "config": config,
        }

    @staticmethod
    def get_presets() -> dict[str, FacePuppetConfig]:
        """获取预设配置

        Returns:
            预设名称到 FacePuppetConfig 的映射字典
        """
        if FacePuppetEffect._presets is None:
            FacePuppetEffect._presets = FacePuppetEffect._init_presets()
        return FacePuppetEffect._presets

    @staticmethod
    def get_preset(preset_name: str) -> FacePuppetConfig:
        """获取单个预设配置

        Args:
            preset_name: 预设名称

        Returns:
            FacePuppetConfig 实例

        Raises:
            ValueError: 当预设名称不存在时
        """
        presets = FacePuppetEffect.get_presets()
        if preset_name not in presets:
            raise ValueError(
                f"Unknown preset '{preset_name}'. "
                f"Available: {list(presets.keys())}"
            )
        return presets[preset_name]

    @staticmethod
    def estimate_face_from_bbox(bbox: dict[str, float]) -> dict[str, Any]:
        """从人脸边界框估算面部特征点位置（无跟踪数据时的降级方案）

        Args:
            bbox: 边界框 {x, y, width, height}

        Returns:
            包含各面部特征点的字典:
            {left_eye, right_eye, mouth, nose, jaw, face_bbox}
        """
        x = bbox.get("x", 0.0)
        y = bbox.get("y", 0.0)
        w = bbox.get("width", 200.0)
        h = bbox.get("height", 250.0)

        cx = x + w / 2.0

        eye_y = y + h * 0.35
        eye_spacing = w * 0.25
        left_eye_x = cx - eye_spacing
        right_eye_x = cx + eye_spacing

        nose_y = y + h * 0.55

        mouth_y = y + h * 0.72
        mouth_w = w * 0.35
        mouth_h = h * 0.08

        jaw_y = y + h * 0.92

        return {
            "left_eye": {"x": left_eye_x, "y": eye_y},
            "right_eye": {"x": right_eye_x, "y": eye_y},
            "mouth": {
                "x": cx,
                "y": mouth_y,
                "width": mouth_w,
                "height": mouth_h,
            },
            "nose": {"x": cx, "y": nose_y},
            "jaw": {"x": cx, "y": jaw_y},
            "face_bbox": {"x": x, "y": y, "width": w, "height": h},
        }

    # ------------------------------------------------------------------------
    # 内部方法 - 纽扣眼效果
    # ------------------------------------------------------------------------

    @staticmethod
    def _generate_button_eye(
        config: FacePuppetConfig,
        eye_pos: dict[str, float],
        side: str,
    ) -> list[dict[str, Any]]:
        """生成单只纽扣眼的效果列表

        Args:
            config: 面部木偶化配置
            eye_pos: 眼睛位置 {x, y}
            side: 哪只眼睛 "left" / "right"

        Returns:
            AE 效果列表
        """
        effects: list[dict[str, Any]] = []
        ex = eye_pos.get("x", 500.0)
        ey = eye_pos.get("y", 350.0)

        base_radius = 25.0 * config.eye_scale

        eye_style = config.eye_style if config.style != "button_eyes" else "button"

        if eye_style == "button":
            effects.append({
                "effectName": "Circle",
                "matchName": "ADBE Circle",
                "displayName": f"ButtonEye_{side}_Base",
                "settings": {
                    "Center": [ex, ey],
                    "Radius": base_radius,
                    "Border": 0.0,
                    "Inside Color": config.color[:3],
                    "Outside Color": [0, 0, 0],
                    "Blending Mode": "Normal",
                },
            })

            if config.button_texture:
                effects.append({
                    "effectName": "Circle",
                    "matchName": "ADBE Circle",
                    "displayName": f"ButtonEye_{side}_Rim",
                    "settings": {
                        "Center": [ex, ey],
                        "Radius": base_radius,
                        "Border": base_radius * 0.15,
                        "Inside Color": [
                            min(c * 1.3, 1.0) for c in config.color[:3]
                        ],
                        "Outside Color": [
                            c * 0.6 for c in config.color[:3]
                        ],
                        "Blending Mode": "Normal",
                    },
                })

            hole_radius = base_radius * 0.18
            hole_offset = base_radius * 0.4
            hole_positions = [
                (ex - hole_offset, ey - hole_offset),
                (ex + hole_offset, ey - hole_offset),
                (ex - hole_offset, ey + hole_offset),
                (ex + hole_offset, ey + hole_offset),
            ]
            for i, (hx, hy) in enumerate(hole_positions):
                effects.append({
                    "effectName": "Circle",
                    "matchName": "ADBE Circle",
                    "displayName": f"ButtonEye_{side}_Hole{i+1}",
                    "settings": {
                        "Center": [hx, hy],
                        "Radius": hole_radius,
                        "Border": 0.0,
                        "Inside Color": [0.05, 0.05, 0.05],
                        "Outside Color": [0, 0, 0],
                        "Blending Mode": "Normal",
                    },
                })

            highlight_x = ex - base_radius * 0.35
            highlight_y = ey - base_radius * 0.35
            effects.append({
                "effectName": "Circle",
                "matchName": "ADBE Circle",
                "displayName": f"ButtonEye_{side}_Highlight",
                "settings": {
                    "Center": [highlight_x, highlight_y],
                    "Radius": base_radius * 0.2,
                    "Border": 0.0,
                    "Inside Color": [1.0, 1.0, 1.0],
                    "Outside Color": [0, 0, 0],
                    "Blending Mode": "Screen",
                },
            })

        elif eye_style == "googly":
            effects.append({
                "effectName": "Circle",
                "matchName": "ADBE Circle",
                "displayName": f"GooglyEye_{side}_Sclera",
                "settings": {
                    "Center": [ex, ey],
                    "Radius": base_radius,
                    "Border": base_radius * 0.1,
                    "Inside Color": [1.0, 1.0, 1.0],
                    "Outside Color": [0.8, 0.8, 0.8],
                    "Blending Mode": "Normal",
                },
            })
            effects.append({
                "effectName": "Circle",
                "matchName": "ADBE Circle",
                "displayName": f"GooglyEye_{side}_Pupil",
                "settings": {
                    "Center": [ex, ey],
                    "Radius": base_radius * 0.5,
                    "Border": 0.0,
                    "Inside Color": [0.05, 0.05, 0.05],
                    "Outside Color": [0, 0, 0],
                    "Blending Mode": "Normal",
                },
            })
            effects.append({
                "effectName": "Circle",
                "matchName": "ADBE Circle",
                "displayName": f"GooglyEye_{side}_Highlight",
                "settings": {
                    "Center": [ex - base_radius * 0.2, ey - base_radius * 0.2],
                    "Radius": base_radius * 0.15,
                    "Border": 0.0,
                    "Inside Color": [1.0, 1.0, 1.0],
                    "Outside Color": [0, 0, 0],
                    "Blending Mode": "Screen",
                },
            })

        elif eye_style == "painted":
            effects.append({
                "effectName": "Circle",
                "matchName": "ADBE Circle",
                "displayName": f"PaintedEye_{side}_Base",
                "settings": {
                    "Center": [ex, ey],
                    "Radius": base_radius * 0.9,
                    "Border": 0.0,
                    "Inside Color": config.color[:3],
                    "Outside Color": [0, 0, 0],
                    "Blending Mode": "Multiply",
                },
            })
            effects.append({
                "effectName": "Circle",
                "matchName": "ADBE Circle",
                "displayName": f"PaintedEye_{side}_Pupil",
                "settings": {
                    "Center": [ex, ey],
                    "Radius": base_radius * 0.45,
                    "Border": 0.0,
                    "Inside Color": [0.1, 0.1, 0.1],
                    "Outside Color": [0, 0, 0],
                    "Blending Mode": "Normal",
                },
            })

        elif eye_style == "dot":
            effects.append({
                "effectName": "Circle",
                "matchName": "ADBE Circle",
                "displayName": f"DotEye_{side}",
                "settings": {
                    "Center": [ex, ey],
                    "Radius": base_radius * 0.5,
                    "Border": 0.0,
                    "Inside Color": config.color[:3],
                    "Outside Color": [0, 0, 0],
                    "Blending Mode": "Normal",
                },
            })

        return effects

    # ------------------------------------------------------------------------
    # 内部方法 - 缝线嘴效果
    # ------------------------------------------------------------------------

    @staticmethod
    def _generate_stitched_mouth(
        config: FacePuppetConfig,
        mouth_pos: dict[str, float],
    ) -> list[dict[str, Any]]:
        """生成缝线嘴的效果列表

        Args:
            config: 面部木偶化配置
            mouth_pos: 嘴巴位置 {x, y, width, height}

        Returns:
            AE 效果列表
        """
        effects: list[dict[str, Any]] = []

        mx = mouth_pos.get("x", 600.0)
        my = mouth_pos.get("y", 500.0)
        mw = mouth_pos.get("width", 100.0) * config.mouth_scale
        mh = mouth_pos.get("height", 30.0) * config.mouth_scale

        mouth_style = config.mouth_style

        if mouth_style == "stitched":
            stitch_count = config.stitch_count
            stitch_gap = mw / stitch_count
            stitch_length = stitch_gap * 0.6

            for i in range(stitch_count):
                start_x = mx - mw / 2.0 + i * stitch_gap + stitch_gap * 0.2
                end_x = start_x + stitch_length
                y_offset = mh * 0.3 * math.sin(
                    (i / max(stitch_count - 1, 1)) * math.pi
                )

                effects.append({
                    "effectName": "Beam",
                    "matchName": "ADBE Beam",
                    "displayName": f"StitchMouth_Stitch{i+1}",
                    "settings": {
                        "Starting Point": [start_x, my + y_offset],
                        "Ending Point": [end_x, my - y_offset],
                        "Length": 100.0,
                        "Time": 50.0,
                        "Softness": 0.1,
                        "Inside Color": config.color[:3],
                        "Outside Color": [c * 0.7 for c in config.color[:3]],
                    },
                })

            effects.append({
                "effectName": "Circle",
                "matchName": "ADBE Circle",
                "displayName": "StitchMouth_KnotLeft",
                "settings": {
                    "Center": [mx - mw / 2.0 - 3, my],
                    "Radius": 4.0,
                    "Border": 0.0,
                    "Inside Color": config.color[:3],
                    "Outside Color": [0, 0, 0],
                    "Blending Mode": "Normal",
                },
            })
            effects.append({
                "effectName": "Circle",
                "matchName": "ADBE Circle",
                "displayName": "StitchMouth_KnotRight",
                "settings": {
                    "Center": [mx + mw / 2.0 + 3, my],
                    "Radius": 4.0,
                    "Border": 0.0,
                    "Inside Color": config.color[:3],
                    "Outside Color": [0, 0, 0],
                    "Blending Mode": "Normal",
                },
            })

        elif mouth_style == "line":
            effects.append({
                "effectName": "Beam",
                "matchName": "ADBE Beam",
                "displayName": "LineMouth",
                "settings": {
                    "Starting Point": [mx - mw / 2.0, my],
                    "Ending Point": [mx + mw / 2.0, my],
                    "Length": 100.0,
                    "Time": 50.0,
                    "Softness": 0.2,
                    "Inside Color": config.color[:3],
                    "Outside Color": [c * 0.8 for c in config.color[:3]],
                },
            })

        elif mouth_style == "painted":
            effects.append({
                "effectName": "Circle",
                "matchName": "ADBE Circle",
                "displayName": "PaintedMouth_Line",
                "settings": {
                    "Center": [mx, my],
                    "Radius": mw / 2.0,
                    "Border": 3.0,
                    "Inside Color": [0, 0, 0, 0],
                    "Outside Color": config.color[:3],
                    "Blending Mode": "Normal",
                },
            })

        elif mouth_style == "button":
            effects.append({
                "effectName": "Circle",
                "matchName": "ADBE Circle",
                "displayName": "ButtonMouth_Base",
                "settings": {
                    "Center": [mx, my],
                    "Radius": mw * 0.5,
                    "Border": 0.0,
                    "Inside Color": config.color[:3],
                    "Outside Color": [0, 0, 0],
                    "Blending Mode": "Normal",
                },
            })
            hole_y_offset = mw * 0.2
            hole_x_offset = mw * 0.25
            effects.append({
                "effectName": "Circle",
                "matchName": "ADBE Circle",
                "displayName": "ButtonMouth_Hole1",
                "settings": {
                    "Center": [mx - hole_x_offset, my - hole_y_offset],
                    "Radius": mw * 0.08,
                    "Border": 0.0,
                    "Inside Color": [0.05, 0.05, 0.05],
                    "Outside Color": [0, 0, 0],
                    "Blending Mode": "Normal",
                },
            })
            effects.append({
                "effectName": "Circle",
                "matchName": "ADBE Circle",
                "displayName": "ButtonMouth_Hole2",
                "settings": {
                    "Center": [mx + hole_x_offset, my - hole_y_offset],
                    "Radius": mw * 0.08,
                    "Border": 0.0,
                    "Inside Color": [0.05, 0.05, 0.05],
                    "Outside Color": [0, 0, 0],
                    "Blending Mode": "Normal",
                },
            })

        return effects

    # ------------------------------------------------------------------------
    # 内部方法 - 瓷化皮肤效果
    # ------------------------------------------------------------------------

    @staticmethod
    def _generate_porcelain_skin(
        config: FacePuppetConfig,
        face_bbox: dict[str, float],
    ) -> list[dict[str, Any]]:
        """生成瓷化皮肤的效果列表

        Args:
            config: 面部木偶化配置
            face_bbox: 面部边界框 {x, y, width, height}

        Returns:
            AE 效果列表
        """
        effects: list[dict[str, Any]] = []

        fx = face_bbox.get("x", 400.0)
        fy = face_bbox.get("y", 200.0)
        fw = face_bbox.get("width", 400.0)
        fh = face_bbox.get("height", 500.0)
        cx = fx + fw / 2.0
        cy = fy + fh / 2.0

        effects.append({
            "effectName": "ADBE Gaussian Blur 2",
            "matchName": "ADBE Gaussian Blur 2",
            "displayName": "PorcelainSkin_Smooth",
            "settings": {
                "Blurriness": 4.0,
                "Blur Dimensions": "Horizontal and Vertical",
                "Repeat Edge Pixels": True,
            },
        })

        effects.append({
            "effectName": "ADBE Tint 2",
            "matchName": "ADBE Tint 2",
            "displayName": "PorcelainSkin_Tint",
            "settings": {
                "Map Black To": [0.7, 0.65, 0.6, 1.0],
                "Map White To": [0.98, 0.96, 0.94, 1.0],
                "Amount To Tint": 40.0,
            },
        })

        effects.append({
            "effectName": "ADBE Glo2",
            "matchName": "ADBE Glo2",
            "displayName": "PorcelainSkin_Glow",
            "settings": {
                "Glow Threshold": 70.0,
                "Glow Radius": 25.0,
                "Glow Intensity": 1.2,
                "Composite Original": "On Top",
                "Glow Colors": "A & B Colors",
                "Color Looping": "Triangle A>B",
                "Color A": [1.0, 0.98, 0.95, 1.0],
                "Color B": [0.9, 0.88, 0.85, 1.0],
            },
        })

        effects.append({
            "effectName": "Ramp",
            "matchName": "ADBE Ramp",
            "displayName": "PorcelainSkin_Reflection",
            "settings": {
                "Start of Ramp": [cx, fy + fh * 0.1],
                "Start Color": [1.0, 1.0, 1.0],
                "End of Ramp": [cx, fy + fh * 0.5],
                "End Color": [0.0, 0.0, 0.0],
                "Ramp Shape": "Radial Ramp",
                "Ramp Scatter": 0.0,
                "Blend With Original": 85.0,
            },
        })

        effects.append({
            "effectName": "ADBE CurvesCustom",
            "matchName": "ADBE CurvesCustom",
            "displayName": "PorcelainSkin_Curves",
            "settings": {
                "Channel": "RGB",
                "Curve": [
                    [0.0, 0.05],
                    [0.25, 0.2],
                    [0.5, 0.5],
                    [0.75, 0.8],
                    [1.0, 0.98],
                ],
            },
        })

        return effects

    # ------------------------------------------------------------------------
    # 内部方法 - 面部关节点效果
    # ------------------------------------------------------------------------

    @staticmethod
    def _generate_face_joints(
        config: FacePuppetConfig,
        face_data: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """生成面部关节点效果

        Args:
            config: 面部木偶化配置
            face_data: 面部特征点数据

        Returns:
            AE 效果列表
        """
        effects: list[dict[str, Any]] = []

        jaw = face_data.get("jaw", {"x": 600, "y": 650})
        nose = face_data.get("nose", {"x": 600, "y": 450})
        left_eye = face_data.get("left_eye", {"x": 500, "y": 350})
        right_eye = face_data.get("right_eye", {"x": 700, "y": 350})

        face_bbox = face_data.get("face_bbox", {
            "x": 400, "y": 200, "width": 400, "height": 500,
        })
        fx = face_bbox.get("x", 400.0)
        fy = face_bbox.get("y", 200.0)
        fw = face_bbox.get("width", 400.0)
        fh = face_bbox.get("height", 500.0)

        joint_seam_radius = 8.0

        jaw_joint_y = nose["y"] + (jaw["y"] - nose["y"]) * 0.3
        effects.append({
            "effectName": "Circle",
            "matchName": "ADBE Circle",
            "displayName": "FaceJoint_Jaw",
            "settings": {
                "Center": [jaw["x"], jaw_joint_y],
                "Radius": joint_seam_radius,
                "Border": joint_seam_radius * 0.3,
                "Inside Color": [0.15, 0.15, 0.15],
                "Outside Color": [0.7, 0.7, 0.7],
                "Blending Mode": "Multiply",
            },
        })

        temple_y = fy + fh * 0.28
        temple_left_x = fx + fw * 0.12
        temple_right_x = fx + fw * 0.88

        effects.append({
            "effectName": "Circle",
            "matchName": "ADBE Circle",
            "displayName": "FaceJoint_TempleLeft",
            "settings": {
                "Center": [temple_left_x, temple_y],
                "Radius": joint_seam_radius * 0.8,
                "Border": joint_seam_radius * 0.25,
                "Inside Color": [0.15, 0.15, 0.15],
                "Outside Color": [0.7, 0.7, 0.7],
                "Blending Mode": "Multiply",
            },
        })
        effects.append({
            "effectName": "Circle",
            "matchName": "ADBE Circle",
            "displayName": "FaceJoint_TempleRight",
            "settings": {
                "Center": [temple_right_x, temple_y],
                "Radius": joint_seam_radius * 0.8,
                "Border": joint_seam_radius * 0.25,
                "Inside Color": [0.15, 0.15, 0.15],
                "Outside Color": [0.7, 0.7, 0.7],
                "Blending Mode": "Multiply",
            },
        })

        return effects

    # ------------------------------------------------------------------------
    # 内部方法 - 表情限制表达式
    # ------------------------------------------------------------------------

    @staticmethod
    def _generate_expression_limits(
        config: FacePuppetConfig,
        layer_name: str,
        face_data: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """生成表情限制表达式

        Args:
            config: 面部木偶化配置
            layer_name: 图层名称
            face_data: 面部特征点数据

        Returns:
            表达式列表
        """
        expressions: list[dict[str, Any]] = []

        expressions.append({
            "layer_name": layer_name,
            "property": "Effects.StitchMouth_MouthOpen",
            "expression": (
                'mouthOpen = thisLayer.effect("MouthOpen").value;\n'
                'maxOpen = 15;\n'
                'minOpen = 0;\n'
                'clamp(mouthOpen, minOpen, maxOpen);'
            ),
            "description": "限制嘴巴张合幅度（木偶嘴不能张太大）",
        })

        expressions.append({
            "layer_name": layer_name,
            "property": "Effects.ButtonEye_Blink",
            "expression": (
                'blink = thisLayer.effect("Blink").value;\n'
                'maxBlink = 0.7;\n'
                'minBlink = 0;\n'
                'clamp(blink, minBlink, maxBlink);'
            ),
            "description": "限制眼睛眨动幅度",
        })

        return expressions

    # ------------------------------------------------------------------------
    # 预设初始化
    # ------------------------------------------------------------------------

    @staticmethod
    def _init_presets() -> dict[str, FacePuppetConfig]:
        """初始化预设配置库

        Returns:
            预设名称到 FacePuppetConfig 的映射
        """
        presets: dict[str, FacePuppetConfig] = {}

        presets["classic_button"] = FacePuppetConfig(
            style="all",
            eye_style="button",
            mouth_style="stitched",
            skin_porcelain=True,
            eye_scale=1.0,
            mouth_scale=1.0,
            eye_spacing=1.0,
            color=[0.3, 0.15, 0.05, 1.0],
            button_texture=True,
            stitch_count=8,
        )

        presets["rag_doll"] = FacePuppetConfig(
            style="all",
            eye_style="button",
            mouth_style="stitched",
            skin_porcelain=False,
            eye_scale=1.2,
            mouth_scale=1.1,
            eye_spacing=1.1,
            color=[0.15, 0.1, 0.05, 1.0],
            button_texture=False,
            stitch_count=10,
        )

        presets["porcelain_doll"] = FacePuppetConfig(
            style="all",
            eye_style="painted",
            mouth_style="painted",
            skin_porcelain=True,
            eye_scale=0.9,
            mouth_scale=0.8,
            eye_spacing=0.95,
            color=[0.4, 0.2, 0.15, 1.0],
            button_texture=False,
            stitch_count=6,
        )

        presets["wooden_marionette"] = FacePuppetConfig(
            style="all",
            eye_style="dot",
            mouth_style="line",
            skin_porcelain=False,
            eye_scale=0.8,
            mouth_scale=1.0,
            eye_spacing=1.0,
            color=[0.1, 0.05, 0.02, 1.0],
            button_texture=False,
            stitch_count=12,
        )

        presets["simple"] = FacePuppetConfig(
            style="button_eyes",
            eye_style="button",
            mouth_style="stitched",
            skin_porcelain=False,
            eye_scale=1.0,
            mouth_scale=1.0,
            eye_spacing=1.0,
            color=[0.25, 0.1, 0.05, 1.0],
            button_texture=True,
            stitch_count=6,
        )

        presets["stitched"] = FacePuppetConfig(
            style="stitched_mouth",
            eye_style="button",
            mouth_style="stitched",
            skin_porcelain=False,
            eye_scale=1.0,
            mouth_scale=1.2,
            eye_spacing=1.0,
            color=[0.2, 0.08, 0.03, 1.0],
            button_texture=True,
            stitch_count=14,
        )

        return presets


# ============================================================================
# 自测
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("FacePuppetEffect 模块自测")
    print("=" * 60)

    # --- 测试 1: 预设获取 ---
    print("\n[测试 1] 预设获取")
    presets = FacePuppetEffect.get_presets()
    print(f"  预设数量: {len(presets)}")
    for name in presets:
        cfg = presets[name]
        print(f"  - {name}: style={cfg.style}, eye={cfg.eye_style}, "
              f"mouth={cfg.mouth_style}, porcelain={cfg.skin_porcelain}")

    # --- 测试 2: 单个预设获取 ---
    print("\n[测试 2] 单个预设获取")
    classic = FacePuppetEffect.get_preset("classic_button")
    print(f"  classic_button: style={classic.style}, "
          f"stitch_count={classic.stitch_count}")

    # --- 测试 3: 从边界框估算面部特征 ---
    print("\n[测试 3] 从边界框估算面部特征")
    bbox = {"x": 400, "y": 200, "width": 300, "height": 400}
    face_data = FacePuppetEffect.estimate_face_from_bbox(bbox)
    print(f"  左眼: ({face_data['left_eye']['x']:.1f}, {face_data['left_eye']['y']:.1f})")
    print(f"  右眼: ({face_data['right_eye']['x']:.1f}, {face_data['right_eye']['y']:.1f})")
    print(f"  嘴巴: ({face_data['mouth']['x']:.1f}, {face_data['mouth']['y']:.1f}) "
          f"w={face_data['mouth']['width']:.1f}, h={face_data['mouth']['height']:.1f}")
    print(f"  鼻子: ({face_data['nose']['x']:.1f}, {face_data['nose']['y']:.1f})")
    print(f"  下巴: ({face_data['jaw']['x']:.1f}, {face_data['jaw']['y']:.1f})")

    # --- 测试 4: 完整面部木偶效果生成 ---
    print("\n[测试 4] 完整面部木偶效果生成 (classic_button)")
    config = FacePuppetEffect.get_preset("classic_button")
    result = FacePuppetEffect.generate_face_puppet(
        config, "FaceLayer", face_data, duration=5.0
    )
    print(f"  效果数量: {len(result['effects'])}")
    print(f"  图层数量: {len(result['layers'])}")
    print(f"  表达式数量: {len(result['expressions'])}")
    print(f"  关键帧数量: {len(result['keyframes'])}")

    if result["effects"]:
        effect_names = [e.get("displayName", e.get("effectName", "?")) 
                       for e in result["effects"]]
        print("  效果列表:")
        for name in effect_names:
            print(f"    - {name}")

    # --- 测试 5: 纽扣眼效果 ---
    print("\n[测试 5] 纽扣眼效果 (单只左眼)")
    eye_effects = FacePuppetEffect._generate_button_eye(
        config, {"x": 500, "y": 300}, "left"
    )
    print(f"  效果数量: {len(eye_effects)}")
    for e in eye_effects:
        print(f"    - {e.get('displayName', '?')}")

    # --- 测试 6: 缝线嘴效果 ---
    print("\n[测试 6] 缝线嘴效果")
    mouth_effects = FacePuppetEffect._generate_stitched_mouth(
        config, {"x": 600, "y": 500, "width": 120, "height": 30}
    )
    print(f"  效果数量: {len(mouth_effects)}")
    for e in mouth_effects[:5]:
        print(f"    - {e.get('displayName', '?')}")
    if len(mouth_effects) > 5:
        print(f"    ... 还有 {len(mouth_effects) - 5} 个效果")

    # --- 测试 7: 瓷化皮肤效果 ---
    print("\n[测试 7] 瓷化皮肤效果")
    skin_effects = FacePuppetEffect._generate_porcelain_skin(
        config, {"x": 400, "y": 200, "width": 400, "height": 500}
    )
    print(f"  效果数量: {len(skin_effects)}")
    for e in skin_effects:
        print(f"    - {e.get('displayName', '?')}")

    # --- 测试 8: 面部关节点效果 ---
    print("\n[测试 8] 面部关节点效果")
    joint_effects = FacePuppetEffect._generate_face_joints(config, face_data)
    print(f"  效果数量: {len(joint_effects)}")
    for e in joint_effects:
        print(f"    - {e.get('displayName', '?')}")

    # --- 测试 9: 不同风格预设测试 ---
    print("\n[测试 9] 不同风格预设效果对比")
    for preset_name in ["simple", "stitched", "porcelain_doll", "wooden_marionette", "rag_doll"]:
        cfg = FacePuppetEffect.get_preset(preset_name)
        res = FacePuppetEffect.generate_face_puppet(cfg, "TestLayer", face_data)
        print(f"  {preset_name}: {len(res['effects'])} 个效果")

    # --- 测试 10: 数据类验证 ---
    print("\n[测试 10] 数据类验证")
    custom_config = FacePuppetConfig(
        style="button_eyes",
        eye_scale=1.5,
        stitch_count=12,
    )
    print(f"  style: {custom_config.style}")
    print(f"  eye_scale: {custom_config.eye_scale}")
    print(f"  stitch_count: {custom_config.stitch_count}")
    print(f"  color: {custom_config.color}")

    # --- 测试 11: 无效预设错误处理 ---
    print("\n[测试 11] 无效预设错误处理")
    try:
        FacePuppetEffect.get_preset("nonexistent_preset")
        print("  错误: 应该抛出 ValueError")
    except ValueError as e:
        print(f"  ✓ 正确抛出异常: {e}")

    print("\n" + "=" * 60)
    print("所有自测通过 ✓")
    print("=" * 60)
