"""
关键帧动画生成系统
提供入场/出场/循环/强调等动画模板，并支持节拍-关键帧精密映射
"""

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class KeyframePoint:
    """单个关键帧点"""
    time: float  # 时间（秒）
    value: Any   # 值（可以是数字、数组）
    ease_in: str = "linear"   # 入缓动: linear, ease_in, ease_out, ease_in_out, bezier
    ease_out: str = "linear"  # 出缓动
    bezier_in: tuple[float, float, float, float] = None  # 贝塞尔控制点 (x1,y1,x2,y2)
    bezier_out: tuple[float, float, float, float] = None


@dataclass
class AnimationTemplate:
    """动画模板"""
    name: str
    category: str  # entrance, exit, loop, emphasis, camera
    description: str
    keyframes: list[KeyframePoint]
    property_name: str  # Position, Scale, Rotation, Opacity, etc.
    duration: float  # 默认持续时间（秒）


# AE 贝塞尔缓动值
EASE_PRESETS = {
    "linear": None,
    "ease_in": (0.42, 0, 1, 1),
    "ease_out": (0, 0, 0.58, 1),
    "ease_in_out": (0.42, 0, 0.58, 1),
    "spring": (0.175, 0.885, 0.32, 1.275),
    "bounce": (0.6, -0.28, 0.735, 0.045),
    "elastic": (0.68, -0.55, 0.265, 1.55),
}


def _apply_ease(kf: KeyframePoint, ease_name: str, direction: str = "out") -> KeyframePoint:
    """为关键帧应用预设缓动"""
    bezier = EASE_PRESETS.get(ease_name)
    if direction == "out":
        kf.ease_out = ease_name
        kf.bezier_out = bezier
    else:
        kf.ease_in = ease_name
        kf.bezier_in = bezier
    return kf


class KeyframeAnimationGenerator:
    """关键帧动画生成器"""

    def __init__(self):
        self.templates = self._init_templates()

    def _init_templates(self) -> dict[str, list[AnimationTemplate]]:
        """初始化动画模板库"""
        templates: dict[str, list[AnimationTemplate]] = {
            "entrance": [],
            "exit": [],
            "loop": [],
            "emphasis": [],
            "camera": [],
        }

        # ========== 入场动画 ==========
        templates["entrance"].append(AnimationTemplate(
            name="fade_in",
            category="entrance",
            description="淡入",
            keyframes=[
                KeyframePoint(time=0, value=0, ease_out="ease_in_out",
                              bezier_out=EASE_PRESETS["ease_in_out"]),
                KeyframePoint(time=1, value=100, ease_in="ease_in_out",
                              bezier_in=EASE_PRESETS["ease_in_out"]),
            ],
            property_name="Opacity",
            duration=1.0,
        ))

        templates["entrance"].append(AnimationTemplate(
            name="slide_left",
            category="entrance",
            description="从左滑入",
            keyframes=[
                KeyframePoint(time=0, value=[-1920, 540], ease_out="ease_out",
                              bezier_out=EASE_PRESETS["ease_out"]),
                KeyframePoint(time=1, value=[960, 540], ease_in="ease_out",
                              bezier_in=EASE_PRESETS["ease_out"]),
            ],
            property_name="Position",
            duration=0.8,
        ))

        templates["entrance"].append(AnimationTemplate(
            name="slide_right",
            category="entrance",
            description="从右滑入",
            keyframes=[
                KeyframePoint(time=0, value=[3840, 540], ease_out="ease_out",
                              bezier_out=EASE_PRESETS["ease_out"]),
                KeyframePoint(time=1, value=[960, 540], ease_in="ease_out",
                              bezier_in=EASE_PRESETS["ease_out"]),
            ],
            property_name="Position",
            duration=0.8,
        ))

        templates["entrance"].append(AnimationTemplate(
            name="scale_up",
            category="entrance",
            description="缩放入场",
            keyframes=[
                KeyframePoint(time=0, value=0, ease_out="spring",
                              bezier_out=EASE_PRESETS["spring"]),
                KeyframePoint(time=1, value=100, ease_in="spring",
                              bezier_in=EASE_PRESETS["spring"]),
            ],
            property_name="Scale",
            duration=0.6,
        ))

        templates["entrance"].append(AnimationTemplate(
            name="zoom_in",
            category="entrance",
            description="缩小+淡入",
            keyframes=[
                KeyframePoint(time=0, value=200, ease_out="ease_out",
                              bezier_out=EASE_PRESETS["ease_out"]),
                KeyframePoint(time=1, value=100, ease_in="ease_out",
                              bezier_in=EASE_PRESETS["ease_out"]),
            ],
            property_name="Scale",
            duration=0.8,
        ))

        templates["entrance"].append(AnimationTemplate(
            name="rotate_in",
            category="entrance",
            description="旋转入场",
            keyframes=[
                KeyframePoint(time=0, value=-180, ease_out="ease_out",
                              bezier_out=EASE_PRESETS["ease_out"]),
                KeyframePoint(time=1, value=0, ease_in="ease_out",
                              bezier_in=EASE_PRESETS["ease_out"]),
            ],
            property_name="Rotation",
            duration=0.8,
        ))

        templates["entrance"].append(AnimationTemplate(
            name="slide_up",
            category="entrance",
            description="从下滑入",
            keyframes=[
                KeyframePoint(time=0, value=[960, 1620], ease_out="ease_out",
                              bezier_out=EASE_PRESETS["ease_out"]),
                KeyframePoint(time=1, value=[960, 540], ease_in="ease_out",
                              bezier_in=EASE_PRESETS["ease_out"]),
            ],
            property_name="Position",
            duration=0.8,
        ))

        templates["entrance"].append(AnimationTemplate(
            name="slide_down",
            category="entrance",
            description="从上滑入",
            keyframes=[
                KeyframePoint(time=0, value=[960, -540], ease_out="ease_out",
                              bezier_out=EASE_PRESETS["ease_out"]),
                KeyframePoint(time=1, value=[960, 540], ease_in="ease_out",
                              bezier_in=EASE_PRESETS["ease_out"]),
            ],
            property_name="Position",
            duration=0.8,
        ))

        templates["entrance"].append(AnimationTemplate(
            name="scale_down",
            category="entrance",
            description="大缩小到正常",
            keyframes=[
                KeyframePoint(time=0, value=200, ease_out="ease_out",
                              bezier_out=EASE_PRESETS["ease_out"]),
                KeyframePoint(time=1, value=100, ease_in="ease_out",
                              bezier_in=EASE_PRESETS["ease_out"]),
            ],
            property_name="Scale",
            duration=0.6,
        ))

        templates["entrance"].append(AnimationTemplate(
            name="blur_in",
            category="entrance",
            description="模糊到清晰",
            keyframes=[
                KeyframePoint(time=0, value=0, ease_out="ease_in_out",
                              bezier_out=EASE_PRESETS["ease_in_out"]),
                KeyframePoint(time=1, value=100, ease_in="ease_in_out",
                              bezier_in=EASE_PRESETS["ease_in_out"]),
            ],
            property_name="Opacity",
            duration=0.8,
        ))

        # ========== 出场动画 ==========
        templates["exit"].append(AnimationTemplate(
            name="fade_out",
            category="exit",
            description="淡出",
            keyframes=[
                KeyframePoint(time=0, value=100, ease_out="ease_in",
                              bezier_out=EASE_PRESETS["ease_in"]),
                KeyframePoint(time=1, value=0, ease_in="ease_in",
                              bezier_in=EASE_PRESETS["ease_in"]),
            ],
            property_name="Opacity",
            duration=0.8,
        ))

        templates["exit"].append(AnimationTemplate(
            name="slide_left_out",
            category="exit",
            description="向左滑出",
            keyframes=[
                KeyframePoint(time=0, value=[960, 540], ease_out="ease_in",
                              bezier_out=EASE_PRESETS["ease_in"]),
                KeyframePoint(time=1, value=[-1920, 540], ease_in="ease_in",
                              bezier_in=EASE_PRESETS["ease_in"]),
            ],
            property_name="Position",
            duration=0.8,
        ))

        templates["exit"].append(AnimationTemplate(
            name="slide_right_out",
            category="exit",
            description="向右滑出",
            keyframes=[
                KeyframePoint(time=0, value=[960, 540], ease_out="ease_in",
                              bezier_out=EASE_PRESETS["ease_in"]),
                KeyframePoint(time=1, value=[3840, 540], ease_in="ease_in",
                              bezier_in=EASE_PRESETS["ease_in"]),
            ],
            property_name="Position",
            duration=0.8,
        ))

        templates["exit"].append(AnimationTemplate(
            name="slide_up_out",
            category="exit",
            description="向上滑出",
            keyframes=[
                KeyframePoint(time=0, value=[960, 540], ease_out="ease_in",
                              bezier_out=EASE_PRESETS["ease_in"]),
                KeyframePoint(time=1, value=[960, -540], ease_in="ease_in",
                              bezier_in=EASE_PRESETS["ease_in"]),
            ],
            property_name="Position",
            duration=0.8,
        ))

        templates["exit"].append(AnimationTemplate(
            name="slide_down_out",
            category="exit",
            description="向下滑出",
            keyframes=[
                KeyframePoint(time=0, value=[960, 540], ease_out="ease_in",
                              bezier_out=EASE_PRESETS["ease_in"]),
                KeyframePoint(time=1, value=[960, 1620], ease_in="ease_in",
                              bezier_in=EASE_PRESETS["ease_in"]),
            ],
            property_name="Position",
            duration=0.8,
        ))

        templates["exit"].append(AnimationTemplate(
            name="scale_up_out",
            category="exit",
            description="放大消失",
            keyframes=[
                KeyframePoint(time=0, value=100, ease_out="ease_in",
                              bezier_out=EASE_PRESETS["ease_in"]),
                KeyframePoint(time=1, value=200, ease_in="ease_in",
                              bezier_in=EASE_PRESETS["ease_in"]),
            ],
            property_name="Scale",
            duration=0.6,
        ))

        templates["exit"].append(AnimationTemplate(
            name="scale_down_out",
            category="exit",
            description="缩小消失",
            keyframes=[
                KeyframePoint(time=0, value=100, ease_out="ease_in",
                              bezier_out=EASE_PRESETS["ease_in"]),
                KeyframePoint(time=1, value=0, ease_in="ease_in",
                              bezier_in=EASE_PRESETS["ease_in"]),
            ],
            property_name="Scale",
            duration=0.6,
        ))

        templates["exit"].append(AnimationTemplate(
            name="rotate_out",
            category="exit",
            description="旋转出场",
            keyframes=[
                KeyframePoint(time=0, value=0, ease_out="ease_in",
                              bezier_out=EASE_PRESETS["ease_in"]),
                KeyframePoint(time=1, value=180, ease_in="ease_in",
                              bezier_in=EASE_PRESETS["ease_in"]),
            ],
            property_name="Rotation",
            duration=0.8,
        ))

        templates["exit"].append(AnimationTemplate(
            name="zoom_out",
            category="exit",
            description="放大+淡出",
            keyframes=[
                KeyframePoint(time=0, value=100, ease_out="ease_in",
                              bezier_out=EASE_PRESETS["ease_in"]),
                KeyframePoint(time=1, value=200, ease_in="ease_in",
                              bezier_in=EASE_PRESETS["ease_in"]),
            ],
            property_name="Scale",
            duration=0.8,
        ))

        # ========== 循环动画 ==========
        templates["loop"].append(AnimationTemplate(
            name="pulse",
            category="loop",
            description="脉冲缩放",
            keyframes=[
                KeyframePoint(time=0, value=100, ease_out="ease_in_out",
                              bezier_out=EASE_PRESETS["ease_in_out"]),
                KeyframePoint(time=0.5, value=105, ease_in="ease_in_out",
                              bezier_in=EASE_PRESETS["ease_in_out"],
                              ease_out="ease_in_out",
                              bezier_out=EASE_PRESETS["ease_in_out"]),
                KeyframePoint(time=1, value=100, ease_in="ease_in_out",
                              bezier_in=EASE_PRESETS["ease_in_out"]),
            ],
            property_name="Scale",
            duration=1.0,
        ))

        templates["loop"].append(AnimationTemplate(
            name="breathe",
            category="loop",
            description="呼吸缩放（慢速）",
            keyframes=[
                KeyframePoint(time=0, value=100, ease_out="ease_in_out",
                              bezier_out=EASE_PRESETS["ease_in_out"]),
                KeyframePoint(time=0.5, value=103, ease_in="ease_in_out",
                              bezier_in=EASE_PRESETS["ease_in_out"],
                              ease_out="ease_in_out",
                              bezier_out=EASE_PRESETS["ease_in_out"]),
                KeyframePoint(time=1, value=100, ease_in="ease_in_out",
                              bezier_in=EASE_PRESETS["ease_in_out"]),
            ],
            property_name="Scale",
            duration=3.0,
        ))

        templates["loop"].append(AnimationTemplate(
            name="swing",
            category="loop",
            description="摆动",
            keyframes=[
                KeyframePoint(time=0, value=-3, ease_out="ease_in_out",
                              bezier_out=EASE_PRESETS["ease_in_out"]),
                KeyframePoint(time=0.5, value=3, ease_in="ease_in_out",
                              bezier_in=EASE_PRESETS["ease_in_out"],
                              ease_out="ease_in_out",
                              bezier_out=EASE_PRESETS["ease_in_out"]),
                KeyframePoint(time=1, value=-3, ease_in="ease_in_out",
                              bezier_in=EASE_PRESETS["ease_in_out"]),
            ],
            property_name="Rotation",
            duration=1.5,
        ))

        templates["loop"].append(AnimationTemplate(
            name="rotate_loop",
            category="loop",
            description="持续旋转",
            keyframes=[
                KeyframePoint(time=0, value=0, ease_out="linear"),
                KeyframePoint(time=1, value=360, ease_in="linear"),
            ],
            property_name="Rotation",
            duration=2.0,
        ))

        templates["loop"].append(AnimationTemplate(
            name="float",
            category="loop",
            description="浮动",
            keyframes=[
                KeyframePoint(time=0, value=0, ease_out="ease_in_out",
                              bezier_out=EASE_PRESETS["ease_in_out"]),
                KeyframePoint(time=0.5, value=-15, ease_in="ease_in_out",
                              bezier_in=EASE_PRESETS["ease_in_out"],
                              ease_out="ease_in_out",
                              bezier_out=EASE_PRESETS["ease_in_out"]),
                KeyframePoint(time=1, value=0, ease_in="ease_in_out",
                              bezier_in=EASE_PRESETS["ease_in_out"]),
            ],
            property_name="Position",
            duration=2.0,
        ))

        templates["loop"].append(AnimationTemplate(
            name="bounce",
            category="loop",
            description="弹跳",
            keyframes=[
                KeyframePoint(time=0, value=0, ease_out="ease_out",
                              bezier_out=EASE_PRESETS["ease_out"]),
                KeyframePoint(time=0.3, value=-30, ease_in="ease_in",
                              bezier_in=EASE_PRESETS["ease_in"],
                              ease_out="bounce",
                              bezier_out=EASE_PRESETS["bounce"]),
                KeyframePoint(time=0.6, value=0, ease_in="bounce",
                              bezier_in=EASE_PRESETS["bounce"],
                              ease_out="ease_out",
                              bezier_out=EASE_PRESETS["ease_out"]),
                KeyframePoint(time=0.8, value=-10, ease_in="ease_in",
                              bezier_in=EASE_PRESETS["ease_in"],
                              ease_out="bounce",
                              bezier_out=EASE_PRESETS["bounce"]),
                KeyframePoint(time=1, value=0, ease_in="bounce",
                              bezier_in=EASE_PRESETS["bounce"]),
            ],
            property_name="Position",
            duration=1.0,
        ))

        # ========== 强调动画 ==========
        templates["emphasis"].append(AnimationTemplate(
            name="shake",
            category="emphasis",
            description="抖动（5次振荡）",
            keyframes=[
                KeyframePoint(time=0, value=0, ease_out="linear"),
                KeyframePoint(time=0.1, value=10, ease_in="linear", ease_out="linear"),
                KeyframePoint(time=0.2, value=-10, ease_in="linear", ease_out="linear"),
                KeyframePoint(time=0.3, value=10, ease_in="linear", ease_out="linear"),
                KeyframePoint(time=0.4, value=-10, ease_in="linear", ease_out="linear"),
                KeyframePoint(time=0.5, value=10, ease_in="linear", ease_out="linear"),
                KeyframePoint(time=0.6, value=-10, ease_in="linear", ease_out="linear"),
                KeyframePoint(time=0.7, value=10, ease_in="linear", ease_out="linear"),
                KeyframePoint(time=0.8, value=-10, ease_in="linear", ease_out="linear"),
                KeyframePoint(time=0.9, value=5, ease_in="linear", ease_out="linear"),
                KeyframePoint(time=1.0, value=0, ease_in="linear"),
            ],
            property_name="Position",
            duration=0.6,
        ))

        templates["emphasis"].append(AnimationTemplate(
            name="flash",
            category="emphasis",
            description="闪烁",
            keyframes=[
                KeyframePoint(time=0, value=100, ease_out="linear"),
                KeyframePoint(time=0.15, value=30, ease_in="linear", ease_out="linear"),
                KeyframePoint(time=0.3, value=100, ease_in="linear", ease_out="linear"),
                KeyframePoint(time=0.45, value=30, ease_in="linear", ease_out="linear"),
                KeyframePoint(time=0.6, value=100, ease_in="linear"),
            ],
            property_name="Opacity",
            duration=0.6,
        ))

        templates["emphasis"].append(AnimationTemplate(
            name="pop",
            category="emphasis",
            description="弹出",
            keyframes=[
                KeyframePoint(time=0, value=100, ease_out="spring",
                              bezier_out=EASE_PRESETS["spring"]),
                KeyframePoint(time=0.3, value=120, ease_in="spring",
                              bezier_in=EASE_PRESETS["spring"],
                              ease_out="spring",
                              bezier_out=EASE_PRESETS["spring"]),
                KeyframePoint(time=1, value=100, ease_in="spring",
                              bezier_in=EASE_PRESETS["spring"]),
            ],
            property_name="Scale",
            duration=0.5,
        ))

        templates["emphasis"].append(AnimationTemplate(
            name="wiggle",
            category="emphasis",
            description="摆动（3次随机偏移）",
            keyframes=[
                KeyframePoint(time=0, value=0, ease_out="linear"),
                KeyframePoint(time=0.17, value=5, ease_in="linear", ease_out="linear"),
                KeyframePoint(time=0.33, value=-3, ease_in="linear", ease_out="linear"),
                KeyframePoint(time=0.5, value=5, ease_in="linear", ease_out="linear"),
                KeyframePoint(time=0.67, value=-2, ease_in="linear", ease_out="linear"),
                KeyframePoint(time=0.83, value=3, ease_in="linear", ease_out="linear"),
                KeyframePoint(time=1.0, value=0, ease_in="linear"),
            ],
            property_name="Rotation",
            duration=0.6,
        ))

        templates["emphasis"].append(AnimationTemplate(
            name="rubber_band",
            category="emphasis",
            description="橡皮筋",
            keyframes=[
                KeyframePoint(time=0, value=100, ease_out="spring",
                              bezier_out=EASE_PRESETS["spring"]),
                KeyframePoint(time=0.15, value=110, ease_in="spring",
                              bezier_in=EASE_PRESETS["spring"],
                              ease_out="spring",
                              bezier_out=EASE_PRESETS["spring"]),
                KeyframePoint(time=0.35, value=92, ease_in="spring",
                              bezier_in=EASE_PRESETS["spring"],
                              ease_out="spring",
                              bezier_out=EASE_PRESETS["spring"]),
                KeyframePoint(time=0.55, value=104, ease_in="spring",
                              bezier_in=EASE_PRESETS["spring"],
                              ease_out="spring",
                              bezier_out=EASE_PRESETS["spring"]),
                KeyframePoint(time=0.75, value=98, ease_in="spring",
                              bezier_in=EASE_PRESETS["spring"],
                              ease_out="spring",
                              bezier_out=EASE_PRESETS["spring"]),
                KeyframePoint(time=1.0, value=100, ease_in="spring",
                              bezier_in=EASE_PRESETS["spring"]),
            ],
            property_name="Scale",
            duration=0.8,
        ))

        templates["emphasis"].append(AnimationTemplate(
            name="jello",
            category="emphasis",
            description="果冻抖动",
            keyframes=[
                KeyframePoint(time=0, value=0, ease_out="elastic",
                              bezier_out=EASE_PRESETS["elastic"]),
                KeyframePoint(time=0.15, value=8, ease_in="elastic",
                              bezier_in=EASE_PRESETS["elastic"],
                              ease_out="elastic",
                              bezier_out=EASE_PRESETS["elastic"]),
                KeyframePoint(time=0.3, value=-6, ease_in="elastic",
                              bezier_in=EASE_PRESETS["elastic"],
                              ease_out="elastic",
                              bezier_out=EASE_PRESETS["elastic"]),
                KeyframePoint(time=0.45, value=4, ease_in="elastic",
                              bezier_in=EASE_PRESETS["elastic"],
                              ease_out="elastic",
                              bezier_out=EASE_PRESETS["elastic"]),
                KeyframePoint(time=0.6, value=-2, ease_in="elastic",
                              bezier_in=EASE_PRESETS["elastic"],
                              ease_out="elastic",
                              bezier_out=EASE_PRESETS["elastic"]),
                KeyframePoint(time=0.8, value=1, ease_in="elastic",
                              bezier_in=EASE_PRESETS["elastic"],
                              ease_out="linear"),
                KeyframePoint(time=1.0, value=0, ease_in="linear"),
            ],
            property_name="Rotation",
            duration=0.9,
        ))

        return templates

    def _rescale_keyframes(self, template_kfs: list[KeyframePoint],
                           target_duration: float,
                           template_duration: float) -> list[KeyframePoint]:
        """将模板关键帧按时间比例缩放到目标时长"""
        if template_duration <= 0:
            return template_kfs
        ratio = target_duration / template_duration
        result = []
        for kf in template_kfs:
            new_kf = KeyframePoint(
                time=round(kf.time * ratio, 6),
                value=kf.value,
                ease_in=kf.ease_in,
                ease_out=kf.ease_out,
                bezier_in=kf.bezier_in,
                bezier_out=kf.bezier_out,
            )
            result.append(new_kf)
        return result

    def generate_entrance_animation(self, anim_type: str, duration: float, **kwargs) -> list[KeyframePoint]:
        """生成入场动画关键帧
        anim_type: fade_in, slide_left, slide_right, slide_up, slide_down,
                   scale_up, scale_down, rotate_in, zoom_in, blur_in
        """
        for tmpl in self.templates.get("entrance", []):
            if tmpl.name == anim_type:
                kfs = self._rescale_keyframes(tmpl.keyframes, duration, tmpl.duration)
                # 如果 kwargs 中提供了偏移/位置参数，调整 Position 类型的值
                if tmpl.property_name == "Position" and "y" in kwargs:
                    y = kwargs["y"]
                    for kf in kfs:
                        if isinstance(kf.value, list) and len(kf.value) == 2:
                            kf.value = [kf.value[0], y]
                return kfs
        raise ValueError(f"未知的入场动画类型: {anim_type}")

    def generate_exit_animation(self, anim_type: str, duration: float, **kwargs) -> list[KeyframePoint]:
        """生成出场动画关键帧
        anim_type: fade_out, slide_left_out, slide_right_out, slide_up_out,
                   slide_down_out, scale_up_out, scale_down_out, rotate_out, zoom_out
        """
        for tmpl in self.templates.get("exit", []):
            if tmpl.name == anim_type:
                kfs = self._rescale_keyframes(tmpl.keyframes, duration, tmpl.duration)
                if tmpl.property_name == "Position" and "y" in kwargs:
                    y = kwargs["y"]
                    for kf in kfs:
                        if isinstance(kf.value, list) and len(kf.value) == 2:
                            kf.value = [kf.value[0], y]
                return kfs
        raise ValueError(f"未知的出场动画类型: {anim_type}")

    def generate_loop_animation(self, anim_type: str, duration: float, **kwargs) -> list[KeyframePoint]:
        """生成循环动画关键帧
        anim_type: pulse, breathe, swing, rotate_loop, float, bounce
        """
        for tmpl in self.templates.get("loop", []):
            if tmpl.name == anim_type:
                kfs = self._rescale_keyframes(tmpl.keyframes, duration, tmpl.duration)
                return kfs
        raise ValueError(f"未知的循环动画类型: {anim_type}")

    def generate_emphasis_animation(self, anim_type: str, duration: float, **kwargs) -> list[KeyframePoint]:
        """生成强调动画关键帧
        anim_type: shake, flash, pop, wiggle, rubber_band, jello
        """
        for tmpl in self.templates.get("emphasis", []):
            if tmpl.name == anim_type:
                kfs = self._rescale_keyframes(tmpl.keyframes, duration, tmpl.duration)
                # shake / wiggle 支持自定义振幅
                amplitude = kwargs.get("amplitude", None)
                if amplitude is not None and anim_type == "shake":
                    for kf in kfs:
                        if isinstance(kf.value, (int, float)) and kf.value != 0:
                            sign = 1 if kf.value > 0 else -1
                            kf.value = sign * amplitude * abs(kf.value) / 10
                return kfs
        raise ValueError(f"未知的强调动画类型: {anim_type}")

    def generate_beat_synced_keyframes(self, beat_times: list[float],
                                        property_name: str,
                                        base_value: Any,
                                        beat_value: Any,
                                        attack_ms: float = 30,
                                        decay_ms: float = 200,
                                        ease_type: str = "ease_out") -> list[KeyframePoint]:
        """节拍同步关键帧生成
        beat_times: 节拍时间点列表（秒）
        property_name: 属性名
        base_value: 基准值
        beat_value: 节拍击打值
        attack_ms: 攻击时间（毫秒）
        decay_ms: 衰减时间（毫秒）
        """
        bezier = EASE_PRESETS.get(ease_type)
        keyframes: list[KeyframePoint] = []

        attack_s = attack_ms / 1000.0
        decay_s = decay_ms / 1000.0

        for bt in beat_times:
            # 攻击帧：从基准值快速到达节拍击打值
            kf_attack = KeyframePoint(
                time=round(bt, 6),
                value=beat_value,
                ease_out=ease_type,
                bezier_out=bezier,
            )
            # 衰减帧：从节拍击打值衰减回基准值
            kf_decay = KeyframePoint(
                time=round(bt + attack_s + decay_s, 6),
                value=base_value,
                ease_in=ease_type,
                bezier_in=bezier,
            )
            keyframes.append(kf_attack)
            keyframes.append(kf_decay)

        # 按时间排序
        keyframes.sort(key=lambda kf: kf.time)
        return keyframes

    def generate_beat_scale_animation(self, beat_times: list[float],
                                       base_scale: float = 100,
                                       beat_scale: float = 110,
                                       attack_ms: float = 30,
                                       decay_ms: float = 200) -> list[dict]:
        """节拍缩放动画 - 卡点放大效果"""
        kfs = self.generate_beat_synced_keyframes(
            beat_times=beat_times,
            property_name="Scale",
            base_value=base_scale,
            beat_value=beat_scale,
            attack_ms=attack_ms,
            decay_ms=decay_ms,
            ease_type="ease_out",
        )
        return self.to_ae_keyframe_commands(kfs, layer_name="", property_name="Scale")

    def generate_beat_opacity_animation(self, beat_times: list[float],
                                         base_opacity: float = 100,
                                         beat_opacity: float = 70,
                                         attack_ms: float = 20,
                                         decay_ms: float = 150) -> list[dict]:
        """节拍透明度动画 - 闪烁效果"""
        kfs = self.generate_beat_synced_keyframes(
            beat_times=beat_times,
            property_name="Opacity",
            base_value=base_opacity,
            beat_value=beat_opacity,
            attack_ms=attack_ms,
            decay_ms=decay_ms,
            ease_type="ease_out",
        )
        return self.to_ae_keyframe_commands(kfs, layer_name="", property_name="Opacity")

    def generate_beat_position_animation(self, beat_times: list[float],
                                          direction: str = "up",
                                          distance: float = 20,
                                          attack_ms: float = 30,
                                          decay_ms: float = 200) -> list[dict]:
        """节拍位移动画 - 弹跳效果"""
        # 根据方向确定偏移
        direction_map = {
            "up": [0, -distance],
            "down": [0, distance],
            "left": [-distance, 0],
            "right": [distance, 0],
        }
        offset = direction_map.get(direction, [0, -distance])

        kfs: list[KeyframePoint] = []
        attack_s = attack_ms / 1000.0
        decay_s = decay_ms / 1000.0
        bezier = EASE_PRESETS["ease_out"]

        for bt in beat_times:
            # 节拍时刻：偏移到目标位置
            kf_attack = KeyframePoint(
                time=round(bt, 6),
                value=offset,
                ease_out="ease_out",
                bezier_out=bezier,
            )
            # 衰减回零位
            kf_decay = KeyframePoint(
                time=round(bt + attack_s + decay_s, 6),
                value=[0, 0],
                ease_in="ease_out",
                bezier_in=bezier,
            )
            kfs.append(kf_attack)
            kfs.append(kf_decay)

        kfs.sort(key=lambda kf: kf.time)
        return self.to_ae_keyframe_commands(kfs, layer_name="", property_name="Position")

    def to_ae_keyframe_commands(self, keyframes: list[KeyframePoint],
                                 layer_name: str,
                                 property_name: str,
                                 comp_name: str = None) -> list[dict]:
        """将关键帧转换为AE命令格式"""
        commands = []
        for kf in keyframes:
            cmd: dict[str, Any] = {
                "command": "setKeyframe",
                "layer": layer_name,
                "property": property_name,
                "time": kf.time,
                "value": kf.value,
            }
            if comp_name:
                cmd["comp"] = comp_name

            # 缓动信息
            easing: dict[str, Any] = {}
            if kf.ease_out != "linear" and kf.bezier_out is not None:
                easing["out"] = {
                    "type": kf.ease_out,
                    "bezier": list(kf.bezier_out),
                }
            elif kf.ease_out != "linear":
                easing["out"] = {"type": kf.ease_out}

            if kf.ease_in != "linear" and kf.bezier_in is not None:
                easing["in"] = {
                    "type": kf.ease_in,
                    "bezier": list(kf.bezier_in),
                }
            elif kf.ease_in != "linear":
                easing["in"] = {"type": kf.ease_in}

            if easing:
                cmd["easing"] = easing

            commands.append(cmd)
        return commands


if __name__ == "__main__":
    gen = KeyframeAnimationGenerator()

    # 入场动画示例
    print("=== 入场动画：fade_in (0.5s) ===")
    kfs = gen.generate_entrance_animation("fade_in", 0.5)
    for kf in kfs:
        print(f"  t={kf.time:.3f}s  val={kf.value}  ease_out={kf.ease_out}  ease_in={kf.ease_in}")

    print("\n=== 入场动画：slide_left (1.0s, y=600) ===")
    kfs = gen.generate_entrance_animation("slide_left", 1.0, y=600)
    for kf in kfs:
        print(f"  t={kf.time:.3f}s  val={kf.value}  ease_out={kf.ease_out}")

    # 出场动画示例
    print("\n=== 出场动画：fade_out (0.6s) ===")
    kfs = gen.generate_exit_animation("fade_out", 0.6)
    for kf in kfs:
        print(f"  t={kf.time:.3f}s  val={kf.value}  ease_out={kf.ease_out}")

    # 循环动画示例
    print("\n=== 循环动画：pulse (1.2s) ===")
    kfs = gen.generate_loop_animation("pulse", 1.2)
    for kf in kfs:
        print(f"  t={kf.time:.3f}s  val={kf.value}")

    # 强调动画示例
    print("\n=== 强调动画：pop (0.4s) ===")
    kfs = gen.generate_emphasis_animation("pop", 0.4)
    for kf in kfs:
        print(f"  t={kf.time:.3f}s  val={kf.value}  ease_out={kf.ease_out}")

    # 节拍同步示例
    print("\n=== 节拍同步关键帧 ===")
    beats = [0.5, 1.0, 1.5, 2.0, 2.5]
    kfs = gen.generate_beat_synced_keyframes(
        beat_times=beats,
        property_name="Scale",
        base_value=100,
        beat_value=115,
        attack_ms=30,
        decay_ms=200,
    )
    for kf in kfs:
        print(f"  t={kf.time:.3f}s  val={kf.value}")

    # AE命令格式示例
    print("\n=== AE关键帧命令 ===")
    cmds = gen.to_ae_keyframe_commands(kfs[:4], layer_name="Layer 1", property_name="Scale", comp_name="Comp 1")
    for cmd in cmds:
        print(f"  {cmd}")

    # 节拍缩放动画
    print("\n=== 节拍缩放动画 ===")
    cmds = gen.generate_beat_scale_animation(beats, base_scale=100, beat_scale=112)
    for cmd in cmds[:4]:
        print(f"  {cmd}")

    # 节拍位移动画
    print("\n=== 节拍位移动画（向上） ===")
    cmds = gen.generate_beat_position_animation(beats, direction="up", distance=25)
    for cmd in cmds[:4]:
        print(f"  {cmd}")
