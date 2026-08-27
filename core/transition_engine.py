"""
transition_engine.py
========================================
Transition Engine - 跨平台过渡效果统一引擎

集成 After Effects、Premiere Pro、DaVinci Resolve、Blender 和 FFmpeg 的
过渡效果生成与管理系统。基于 transition_map.py 扩展，提供 100+ 内置预设、
智能推荐、缓动系统和跨软件桥接能力。

主要模块：
    - TransitionCategory / TransitionStyle: 过渡分类与风格枚举
    - TransitionPreset: 过渡预设数据类
    - EasingEngine: 20+ 缓动函数与动画曲线
    - AETransitionEngine: After Effects 过渡生成器
    - PRTransitionEngine: Premiere Pro 过渡引擎
    - ResolveTransitionEngine: DaVinci Resolve 过渡引擎
    - BlenderTransitionEngine: Blender 过渡引擎
    - FFmpegTransitionEngine: FFmpeg 过渡命令生成器
    - PresetLibrary: 100+ 预设库与搜索管理
    - TransitionAI: 智能推荐与节拍同步
    - UnifiedTransitionAPI: 跨软件统一接口

作者：AE Knowledge Vault
版本：2.0.0
"""

from __future__ import annotations

import math
import json
import random
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple, Callable, Union
from pathlib import Path


# ===========================================================================
# 1. 过渡分类系统
# ===========================================================================

class TransitionCategory(Enum):
    """过渡效果分类枚举"""
    DISSOLVE = "dissolve"
    WIPE = "wipe"
    SLIDE = "slide"
    ZOOM = "zoom"
    THREE_D = "3d"
    GLOW_LIGHT = "glow_light"
    PARTICLE = "particle"
    DISTORT = "distort"
    GLITCH = "glitch"
    MOTION_BLUR = "motion_blur"
    SHAPE = "shape"
    COLOR = "color"
    TEXT_TRANSITION = "text_transition"


class TransitionStyle(Enum):
    """过渡风格枚举"""
    SOFT = "soft"
    HARD = "hard"
    DYNAMIC = "dynamic"
    CINEMATIC = "cinematic"
    GLITCHY = "glitchy"
    DREAMY = "dreamy"
    ENERGETIC = "energetic"
    MINIMAL = "minimal"
    RETRO = "retro"
    FUTURISTIC = "futuristic"


class SoftwareTarget(Enum):
    """目标软件平台枚举"""
    AFTER_EFFECTS = "after_effects"
    PREMIERE_PRO = "premiere_pro"
    DAVINCI_RESOLVE = "davinci_resolve"
    BLENDER = "blender"
    FFMPEG = "ffmpeg"


@dataclass
class TransitionPreset:
    """过渡预设数据类

    Attributes:
        id: 预设唯一标识符
        name: 预设显示名称
        category: 过渡分类
        style: 过渡风格
        duration: 默认持续时间（秒）
        easing: 默认缓动类型
        software_support: 支持的软件平台列表
        params: 过渡参数字典
        description: 预设描述
        tags: 搜索标签
    """
    id: str
    name: str
    category: TransitionCategory
    style: TransitionStyle
    duration: float = 0.5
    easing: str = "ease_in_out"
    software_support: List[SoftwareTarget] = field(default_factory=list)
    params: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        result = asdict(self)
        result["category"] = self.category.value
        result["style"] = self.style.value
        result["software_support"] = [s.value for s in self.software_support]
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TransitionPreset":
        """从字典创建预设"""
        data = data.copy()
        data["category"] = TransitionCategory(data["category"])
        data["style"] = TransitionStyle(data["style"])
        data["software_support"] = [SoftwareTarget(s) for s in data["software_support"]]
        return cls(**data)


# ===========================================================================
# 2. 缓动与计时系统
# ===========================================================================

class EasingEngine:
    """缓动引擎 - 提供 20+ 缓动函数与动画曲线

    支持标准缓动、弹性、回弹、贝塞尔曲线和弹簧物理等多种动画曲线。
    """

    def __init__(self) -> None:
        self._easing_functions: Dict[str, Callable[[float], float]] = {
            "linear": self.linear,
            "ease_in": self.ease_in_quad,
            "ease_out": self.ease_out_quad,
            "ease_in_out": self.ease_in_out_quad,
            "ease_in_quad": self.ease_in_quad,
            "ease_out_quad": self.ease_out_quad,
            "ease_in_out_quad": self.ease_in_out_quad,
            "ease_in_cubic": self.ease_in_cubic,
            "ease_out_cubic": self.ease_out_cubic,
            "ease_in_out_cubic": self.ease_in_out_cubic,
            "ease_in_quart": self.ease_in_quart,
            "ease_out_quart": self.ease_out_quart,
            "ease_in_out_quart": self.ease_in_out_quart,
            "ease_in_quint": self.ease_in_quint,
            "ease_out_quint": self.ease_out_quint,
            "ease_in_out_quint": self.ease_in_out_quint,
            "ease_in_sine": self.ease_in_sine,
            "ease_out_sine": self.ease_out_sine,
            "ease_in_out_sine": self.ease_in_out_sine,
            "ease_in_expo": self.ease_in_expo,
            "ease_out_expo": self.ease_out_expo,
            "ease_in_out_expo": self.ease_in_out_expo,
            "ease_in_circ": self.ease_in_circ,
            "ease_out_circ": self.ease_out_circ,
            "ease_in_out_circ": self.ease_in_out_circ,
            "ease_in_back": self.ease_in_back,
            "ease_out_back": self.ease_out_back,
            "ease_in_out_back": self.ease_in_out_back,
            "ease_out_bounce": self.ease_out_bounce,
            "ease_in_bounce": self.ease_in_bounce,
            "ease_in_out_bounce": self.ease_in_out_bounce,
            "ease_out_elastic": self.ease_out_elastic,
            "ease_in_elastic": self.ease_in_elastic,
            "ease_in_out_elastic": self.ease_in_out_elastic,
        }

    @staticmethod
    def _clamp(t: float) -> float:
        """将进度值限制在 [0, 1] 范围内"""
        return max(0.0, min(1.0, t))

    def map_progress(self, t: float, easing_type: str = "ease_in_out") -> float:
        """将线性进度映射为缓动后的进度值

        Args:
            t: 线性进度值 (0.0 ~ 1.0)
            easing_type: 缓动类型名称

        Returns:
            缓动后的进度值
        """
        t = self._clamp(t)
        func = self._easing_functions.get(easing_type)
        if func is None:
            return t
        return func(t)

    def get_easing_function(self, easing_type: str) -> Callable[[float], float]:
        """获取指定缓动函数

        Args:
            easing_type: 缓动类型名称

        Returns:
            缓动函数 callable(t) -> value
        """
        func = self._easing_functions.get(easing_type)
        if func is None:
            return self.linear
        return func

    def get_available_easings(self) -> List[str]:
        """获取所有可用的缓动类型名称"""
        return list(self._easing_functions.keys())

    # -----------------------------------------------------------------------
    # 基础缓动函数
    # -----------------------------------------------------------------------

    @staticmethod
    def linear(t: float) -> float:
        return t

    # Quad (二次方)
    @staticmethod
    def ease_in_quad(t: float) -> float:
        return t * t

    @staticmethod
    def ease_out_quad(t: float) -> float:
        return 1 - (1 - t) * (1 - t)

    @staticmethod
    def ease_in_out_quad(t: float) -> float:
        return 2 * t * t if t < 0.5 else 1 - pow(-2 * t + 2, 2) / 2

    # Cubic (三次方)
    @staticmethod
    def ease_in_cubic(t: float) -> float:
        return t * t * t

    @staticmethod
    def ease_out_cubic(t: float) -> float:
        return 1 - pow(1 - t, 3)

    @staticmethod
    def ease_in_out_cubic(t: float) -> float:
        return 4 * t * t * t if t < 0.5 else 1 - pow(-2 * t + 2, 3) / 2

    # Quart (四次方)
    @staticmethod
    def ease_in_quart(t: float) -> float:
        return t * t * t * t

    @staticmethod
    def ease_out_quart(t: float) -> float:
        return 1 - pow(1 - t, 4)

    @staticmethod
    def ease_in_out_quart(t: float) -> float:
        return 8 * t * t * t * t if t < 0.5 else 1 - pow(-2 * t + 2, 4) / 2

    # Quint (五次方)
    @staticmethod
    def ease_in_quint(t: float) -> float:
        return t * t * t * t * t

    @staticmethod
    def ease_out_quint(t: float) -> float:
        return 1 - pow(1 - t, 5)

    @staticmethod
    def ease_in_out_quint(t: float) -> float:
        return 16 * t * t * t * t * t if t < 0.5 else 1 - pow(-2 * t + 2, 5) / 2

    # Sine (正弦)
    @staticmethod
    def ease_in_sine(t: float) -> float:
        return 1 - math.cos((t * math.pi) / 2)

    @staticmethod
    def ease_out_sine(t: float) -> float:
        return math.sin((t * math.pi) / 2)

    @staticmethod
    def ease_in_out_sine(t: float) -> float:
        return -(math.cos(math.pi * t) - 1) / 2

    # Expo (指数)
    @staticmethod
    def ease_in_expo(t: float) -> float:
        return 0 if t == 0 else pow(2, 10 * t - 10)

    @staticmethod
    def ease_out_expo(t: float) -> float:
        return 1 if t == 1 else 1 - pow(2, -10 * t)

    @staticmethod
    def ease_in_out_expo(t: float) -> float:
        if t == 0:
            return 0
        if t == 1:
            return 1
        if t < 0.5:
            return pow(2, 20 * t - 10) / 2
        return (2 - pow(2, -20 * t + 10)) / 2

    # Circ (圆形)
    @staticmethod
    def ease_in_circ(t: float) -> float:
        return 1 - math.sqrt(1 - pow(t, 2))

    @staticmethod
    def ease_out_circ(t: float) -> float:
        return math.sqrt(1 - pow(t - 1, 2))

    @staticmethod
    def ease_in_out_circ(t: float) -> float:
        if t < 0.5:
            return (1 - math.sqrt(1 - pow(2 * t, 2))) / 2
        return (math.sqrt(1 - pow(-2 * t + 2, 2)) + 1) / 2

    # Back (回弹)
    @staticmethod
    def ease_in_back(t: float, c1: float = 1.70158, c3: float = 2.70158) -> float:
        return c3 * t * t * t - c1 * t * t

    @staticmethod
    def ease_out_back(t: float, c1: float = 1.70158, c3: float = 2.70158) -> float:
        return 1 + c3 * pow(t - 1, 3) + c1 * pow(t - 1, 2)

    @staticmethod
    def ease_in_out_back(
        t: float,
        c1: float = 1.70158,
        c2: float = 2.5949095,
    ) -> float:
        if t < 0.5:
            return (pow(2 * t, 2) * ((c2 + 1) * 2 * t - c2)) / 2
        return (pow(2 * t - 2, 2) * ((c2 + 1) * (t * 2 - 2) + c2) + 2) / 2

    # Bounce (弹跳)
    @staticmethod
    def ease_out_bounce(t: float) -> float:
        n1 = 7.5625
        d1 = 2.75
        if t < 1 / d1:
            return n1 * t * t
        elif t < 2 / d1:
            t2 = t - 1.5 / d1
            return n1 * t2 * t2 + 0.75
        elif t < 2.5 / d1:
            t2 = t - 2.25 / d1
            return n1 * t2 * t2 + 0.9375
        else:
            t2 = t - 2.625 / d1
            return n1 * t2 * t2 + 0.984375

    @staticmethod
    def ease_in_bounce(t: float) -> float:
        return 1 - EasingEngine.ease_out_bounce(1 - t)

    @staticmethod
    def ease_in_out_bounce(t: float) -> float:
        if t < 0.5:
            return (1 - EasingEngine.ease_out_bounce(1 - 2 * t)) / 2
        return (1 + EasingEngine.ease_out_bounce(2 * t - 1)) / 2

    # Elastic (弹性)
    @staticmethod
    def ease_out_elastic(t: float) -> float:
        c4 = (2 * math.pi) / 3
        if t == 0:
            return 0
        if t == 1:
            return 1
        return pow(2, -10 * t) * math.sin((t * 10 - 0.75) * c4) + 1

    @staticmethod
    def ease_in_elastic(t: float) -> float:
        c4 = (2 * math.pi) / 3
        if t == 0:
            return 0
        if t == 1:
            return 1
        return -pow(2, 10 * t - 10) * math.sin((t * 10 - 10.75) * c4)

    @staticmethod
    def ease_in_out_elastic(t: float) -> float:
        c5 = (2 * math.pi) / 4.5
        if t == 0:
            return 0
        if t == 1:
            return 1
        if t < 0.5:
            return -(pow(2, 20 * t - 10) * math.sin((20 * t - 11.125) * c5)) / 2
        return (pow(2, -20 * t + 10) * math.sin((20 * t - 11.125) * c5)) / 2 + 1

    # -----------------------------------------------------------------------
    # 高级动画函数
    # -----------------------------------------------------------------------

    @staticmethod
    def bezier_curve(t: float, p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
        """三次贝塞尔曲线

        Args:
            t: 进度值 (0.0 ~ 1.0)
            p1: 控制点1 (x, y)
            p2: 控制点2 (x, y)

        Returns:
            贝塞尔曲线的 y 值
        """
        x1, y1 = p1
        x2, y2 = p2

        def _cubic_bezier(tt: float) -> Tuple[float, float]:
            cx = 3.0 * x1
            bx = 3.0 * (x2 - x1) - cx
            ax = 1.0 - cx - bx
            cy = 3.0 * y1
            by = 3.0 * (y2 - y1) - cy
            ay = 1.0 - cy - by
            x = ((ax * tt + bx) * tt + cx) * tt
            y = ((ay * tt + by) * tt + cy) * tt
            return x, y

        t = EasingEngine._clamp(t)
        if t <= 0:
            return 0.0
        if t >= 1:
            return 1.0

        low, high = 0.0, 1.0
        for _ in range(20):
            mid = (low + high) / 2
            x, _ = _cubic_bezier(mid)
            if x < t:
                low = mid
            else:
                high = mid
        _, y = _cubic_bezier((low + high) / 2)
        return y

    @staticmethod
    def spring_animation(
        t: float,
        stiffness: float = 100.0,
        damping: float = 10.0,
        mass: float = 1.0,
    ) -> float:
        """弹簧物理动画

        Args:
            t: 时间进度 (0.0 ~ 1.0 映射到 ~2秒)
            stiffness: 刚度系数
            damping: 阻尼系数
            mass: 质量

        Returns:
            弹簧动画位置值
        """
        t = EasingEngine._clamp(t) * 3.0
        omega = math.sqrt(stiffness / mass)
        zeta = damping / (2 * math.sqrt(stiffness * mass))

        if zeta < 1:
            omega_d = omega * math.sqrt(1 - zeta * zeta)
            envelope = math.exp(-zeta * omega * t)
            oscillation = math.cos(omega_d * t)
            return 1 - envelope * oscillation
        else:
            return 1 - math.exp(-omega * t) * (1 + omega * t)

    @staticmethod
    def ease_in_out_with_overshoot(t: float, overshoot: float = 0.1) -> float:
        """带超调量的缓入缓出

        Args:
            t: 进度值
            overshoot: 超调量 (0.0 ~ 0.3)

        Returns:
            缓动后的值，可能略超过 1.0
        """
        t = EasingEngine._clamp(t)
        if t < 0.5:
            return EasingEngine.ease_in_out_cubic(t * 2) * (1 + overshoot) / 2
        return 1 - (EasingEngine.ease_in_out_cubic((1 - t) * 2) * (1 + overshoot) / 2)

    def generate_keyframes(
        self,
        start_value: float,
        end_value: float,
        frame_count: int,
        easing_type: str = "ease_in_out",
    ) -> List[float]:
        """生成关键帧数值序列

        Args:
            start_value: 起始值
            end_value: 结束值
            frame_count: 关键帧数量
            easing_type: 缓动类型

        Returns:
            关键帧值列表
        """
        if frame_count <= 0:
            return []
        if frame_count == 1:
            return [start_value]

        result = []
        for i in range(frame_count):
            t = i / (frame_count - 1)
            eased = self.map_progress(t, easing_type)
            result.append(start_value + (end_value - start_value) * eased)
        return result


# ===========================================================================
# 3. After Effects 过渡引擎
# ===========================================================================

class AETransitionEngine:
    """After Effects 过渡效果生成器

    生成各种 AE 过渡效果的 JSX 脚本代码，支持 50+ 过渡类型。
    """

    def __init__(self, easing_engine: Optional[EasingEngine] = None) -> None:
        self.easing = easing_engine or EasingEngine()
        self.comp_width = 1920
        self.comp_height = 1080

    def apply_transition(
        self,
        preset: TransitionPreset,
        from_layer: str,
        to_layer: str,
        start_time: float,
        duration: float,
    ) -> str:
        """统一应用过渡效果的方法

        Args:
            preset: 过渡预设
            from_layer: 起始图层名
            to_layer: 目标图层名
            start_time: 开始时间（秒）
            duration: 持续时间（秒）

        Returns:
            JSX 脚本代码
        """
        category = preset.category
        dispatch_map = {
            TransitionCategory.DISSOLVE: self.create_dissolve,
            TransitionCategory.WIPE: self._create_wipe_by_preset,
            TransitionCategory.SLIDE: self._create_slide_by_preset,
            TransitionCategory.ZOOM: self.create_zoom_transition,
            TransitionCategory.THREE_D: self._create_3d_by_preset,
            TransitionCategory.GLOW_LIGHT: self._create_glow_by_preset,
            TransitionCategory.PARTICLE: self._create_particle_by_preset,
            TransitionCategory.DISTORT: self._create_distort_by_preset,
            TransitionCategory.GLITCH: self._create_glitch_by_preset,
            TransitionCategory.SHAPE: self._create_shape_by_preset,
            TransitionCategory.TEXT_TRANSITION: self._create_text_by_preset,
            TransitionCategory.COLOR: self.create_color_transition,
            TransitionCategory.MOTION_BLUR: self.create_motion_blur_transition,
        }
        func = dispatch_map.get(category, self.create_crossfade)
        return func(from_layer, to_layer, start_time, duration, preset.params)

    # -----------------------------------------------------------------------
    # 交叉淡化 / 溶解类
    # -----------------------------------------------------------------------

    def create_crossfade(
        self,
        from_layer: str,
        to_layer: str,
        start_time: float,
        duration: float,
        params: Optional[Dict[str, Any]] = None,
    ) -> str:
        """创建交叉淡化过渡"""
        end_time = start_time + duration
        easing = (params or {}).get("easing", "easeInOut")
        return f"""
// Crossfade Transition: {from_layer} -> {to_layer}
var comp = app.project.activeItem;
var fromLyr = comp.layer("{from_layer}");
var toLyr = comp.layer("{to_layer}");

// From layer fade out
fromLyr.property("Opacity").setValueAtTime({start_time}, 100);
fromLyr.property("Opacity").setValueAtTime({end_time}, 0);
fromLyr.property("Opacity").setEaseAtKey(1, KeyframeInterpolationType.{easing});
fromLyr.property("Opacity").setEaseAtKey(2, KeyframeInterpolationType.{easing});

// To layer fade in
toLyr.property("Opacity").setValueAtTime({start_time}, 0);
toLyr.property("Opacity").setValueAtTime({end_time}, 100);
toLyr.property("Opacity").setEaseAtKey(1, KeyframeInterpolationType.{easing});
toLyr.property("Opacity").setEaseAtKey(2, KeyframeInterpolationType.{easing});
"""

    def create_dissolve(
        self,
        from_layer: str,
        to_layer: str,
        start_time: float,
        duration: float,
        params: Optional[Dict[str, Any]] = None,
    ) -> str:
        """创建溶解过渡"""
        end_time = start_time + duration
        feather = (params or {}).get("feather", 0)
        return f"""
// Dissolve Transition
var comp = app.project.activeItem;
var fromLyr = comp.layer("{from_layer}");
var toLyr = comp.layer("{to_layer}");

// Add Dissolve effect to toLayer
var dissolveFX = toLyr.effect.addProperty("ADBE Dissolve");
dissolveFX.property("Transition Completion").setValueAtTime({start_time}, 0);
dissolveFX.property("Transition Completion").setValueAtTime({end_time}, 100);
dissolveFX.property("Feather").setValue({feather});

// Layer opacity backup
fromLyr.property("Opacity").setValueAtTime({start_time}, 100);
fromLyr.property("Opacity").setValueAtTime({end_time}, 0);
"""

    # -----------------------------------------------------------------------
    # 擦除类
    # -----------------------------------------------------------------------

    def create_wipe_types(
        self,
        wipe_type: str,
        from_layer: str,
        to_layer: str,
        start_time: float,
        duration: float,
        params: Optional[Dict[str, Any]] = None,
    ) -> str:
        """创建各种擦除过渡

        Args:
            wipe_type: linear, radial, venetian, gradient, iris, star
        """
        params = params or {}
        wipe_map = {
            "linear": self._wipe_linear,
            "radial": self._wipe_radial,
            "venetian": self._wipe_venetian,
            "gradient": self._wipe_gradient,
            "iris": self._wipe_iris,
            "star": self._wipe_star,
        }
        func = wipe_map.get(wipe_type, self._wipe_linear)
        return func(from_layer, to_layer, start_time, duration, params)

    def _create_wipe_by_preset(
        self,
        from_layer: str,
        to_layer: str,
        start_time: float,
        duration: float,
        params: Dict[str, Any],
    ) -> str:
        wipe_type = params.get("wipe_type", "linear")
        return self.create_wipe_types(wipe_type, from_layer, to_layer, start_time, duration, params)

    def _wipe_linear(self, fl: str, tl: str, st: float, dur: float, p: Dict) -> str:
        et = st + dur
        angle = p.get("angle", 90)
        feather = p.get("feather", 5)
        return f"""
// Linear Wipe Transition
var comp = app.project.activeItem;
var toLyr = comp.layer("{tl}");
var fx = toLyr.effect.addProperty("ADBE Linear Wipe");
fx.property("Transition Completion").setValueAtTime({st}, 0);
fx.property("Transition Completion").setValueAtTime({et}, 100);
fx.property("Wipe Angle").setValue({angle});
fx.property("Feather").setValue({feather});
"""

    def _wipe_radial(self, fl: str, tl: str, st: float, dur: float, p: Dict) -> str:
        et = st + dur
        return f"""
// Radial Wipe Transition
var comp = app.project.activeItem;
var toLyr = comp.layer("{tl}");
var fx = toLyr.effect.addProperty("ADBE Radial Wipe");
fx.property("Transition Completion").setValueAtTime({st}, 0);
fx.property("Transition Completion").setValueAtTime({et}, 100);
fx.property("Start Angle").setValue({p.get("start_angle", 0)});
fx.property("Wipe Center").setValue([{self.comp_width/2}, {self.comp_height/2}]);
fx.property("Wipe").setValue({p.get("wipe_direction", 0)});
fx.property("Feather").setValue({p.get("feather", 5)});
"""

    def _wipe_venetian(self, fl: str, tl: str, st: float, dur: float, p: Dict) -> str:
        et = st + dur
        return f"""
// Venetian Blinds Transition
var comp = app.project.activeItem;
var toLyr = comp.layer("{tl}");
var fx = toLyr.effect.addProperty("ADBE Venetian Blinds");
fx.property("Transition Completion").setValueAtTime({st}, 0);
fx.property("Transition Completion").setValueAtTime({et}, 100);
fx.property("Direction").setValue({p.get("direction", 0)});
fx.property("Width").setValue({p.get("width", 30)});
fx.property("Feather").setValue({p.get("feather", 2)});
"""

    def _wipe_gradient(self, fl: str, tl: str, st: float, dur: float, p: Dict) -> str:
        et = st + dur
        return f"""
// Gradient Wipe Transition
var comp = app.project.activeItem;
var toLyr = comp.layer("{tl}");
var fx = toLyr.effect.addProperty("ADBE Gradient Wipe");
fx.property("Transition Completion").setValueAtTime({st}, 0);
fx.property("Transition Completion").setValueAtTime({et}, 100);
fx.property("Transition Softness").setValue({p.get("softness", 10)});
fx.property("Gradient Placement").setValue({p.get("placement", 0)});
"""

    def _wipe_iris(self, fl: str, tl: str, st: float, dur: float, p: Dict) -> str:
        et = st + dur
        return f"""
// Iris Wipe Transition (Circle)
var comp = app.project.activeItem;
var toLyr = comp.layer("{tl}");
var fx = toLyr.effect.addProperty("ADBE Iris Wipe");
fx.property("Transition Completion").setValueAtTime({st}, 0);
fx.property("Transition Completion").setValueAtTime({et}, 100);
fx.property("Iris Center").setValue([{self.comp_width/2}, {self.comp_height/2}]);
fx.property("Outer Radius").setValue({p.get("outer_radius", 200)});
fx.property("Inner Radius").setValue({p.get("inner_radius", 50)});
fx.property("Feather").setValue({p.get("feather", 5)});
"""

    def _wipe_star(self, fl: str, tl: str, st: float, dur: float, p: Dict) -> str:
        et = st + dur
        points = p.get("points", 5)
        return f"""
// Star Wipe Transition
var comp = app.project.activeItem;
var toLyr = comp.layer("{tl}");
var fx = toLyr.effect.addProperty("ADBE Star Wipe");
fx.property("Transition Completion").setValueAtTime({st}, 0);
fx.property("Transition Completion").setValueAtTime({et}, 100);
fx.property("Number of Points").setValue({points});
fx.property("Inner Color").setValue([1,1,1]);
"""

    # -----------------------------------------------------------------------
    # 滑动类
    # -----------------------------------------------------------------------

    def create_slide_types(
        self,
        slide_type: str,
        from_layer: str,
        to_layer: str,
        start_time: float,
        duration: float,
        params: Optional[Dict[str, Any]] = None,
    ) -> str:
        """创建滑动类过渡

        Args:
            slide_type: push, slide, split, swap, rotate
        """
        params = params or {}
        slide_map = {
            "push": self._slide_push,
            "slide": self._slide_slide,
            "split": self._slide_split,
            "swap": self._slide_swap,
            "rotate": self._slide_rotate,
        }
        func = slide_map.get(slide_type, self._slide_push)
        return func(from_layer, to_layer, start_time, duration, params)

    def _create_slide_by_preset(self, fl, tl, st, dur, p):
        return self.create_slide_types(p.get("slide_type", "push"), fl, tl, st, dur, p)

    def _slide_push(self, fl: str, tl: str, st: float, dur: float, p: Dict) -> str:
        et = st + dur
        direction = p.get("direction", "right")
        offset_map = {
            "left": (-self.comp_width, 0),
            "right": (self.comp_width, 0),
            "up": (0, -self.comp_height),
            "down": (0, self.comp_height),
        }
        ox, oy = offset_map.get(direction, (self.comp_width, 0))
        return f"""
// Push Slide Transition
var comp = app.project.activeItem;
var fromLyr = comp.layer("{fl}");
var toLyr = comp.layer("{tl}");

// From layer pushes out
fromLyr.property("Position").setValueAtTime({st}, [{self.comp_width/2}, {self.comp_height/2}]);
fromLyr.property("Position").setValueAtTime({et}, [{self.comp_width/2 - ox}, {self.comp_height/2 - oy}]);

// To layer pushes in
toLyr.property("Position").setValueAtTime({st}, [{self.comp_width/2 + ox}, {self.comp_height/2 + oy}]);
toLyr.property("Position").setValueAtTime({et}, [{self.comp_width/2}, {self.comp_height/2}]);
"""

    def _slide_slide(self, fl: str, tl: str, st: float, dur: float, p: Dict) -> str:
        et = st + dur
        direction = p.get("direction", "left")
        offset_map = {
            "left": (-self.comp_width, 0),
            "right": (self.comp_width, 0),
        }
        ox, oy = offset_map.get(direction, (-self.comp_width, 0))
        return f"""
// Slide Transition (from layer static, to layer slides in)
var comp = app.project.activeItem;
var toLyr = comp.layer("{tl}");
toLyr.property("Position").setValueAtTime({st}, [{self.comp_width/2 + ox}, {self.comp_height/2 + oy}]);
toLyr.property("Position").setValueAtTime({et}, [{self.comp_width/2}, {self.comp_height/2}]);
"""

    def _slide_split(self, fl: str, tl: str, st: float, dur: float, p: Dict) -> str:
        et = st + dur
        return f"""
// Split Transition (split from center)
var comp = app.project.activeItem;
var fromLyr = comp.layer("{fl}");
var toLyr = comp.layer("{tl}");

// Left half of from layer
var leftHalf = fromLyr.duplicate();
leftHalf.name = "Left_Half";
var leftMask = leftHalf.masks.addProperty("ADBE Mask Atom");
leftMask.property("ADBE Mask Shape").setValue(
  new Shape([[0,0], [{self.comp_width/2},0], [{self.comp_width/2},{self.comp_height}], [0,{self.comp_height}]])
);
leftHalf.property("Position").setValueAtTime({st}, [{self.comp_width/2}, {self.comp_height/2}]);
leftHalf.property("Position").setValueAtTime({et}, [{self.comp_width/2 - self.comp_width/2}, {self.comp_height/2}]);

// Right half of from layer
var rightHalf = fromLyr.duplicate();
rightHalf.name = "Right_Half";
var rightMask = rightHalf.masks.addProperty("ADBE Mask Atom");
rightMask.property("ADBE Mask Shape").setValue(
  new Shape([[{self.comp_width/2},0], [{self.comp_width},0], [{self.comp_width},{self.comp_height}], [{self.comp_width/2},{self.comp_height}]])
);
rightHalf.property("Position").setValueAtTime({st}, [{self.comp_width/2}, {self.comp_height/2}]);
rightHalf.property("Position").setValueAtTime({et}, [{self.comp_width/2 + self.comp_width/2}, {self.comp_height/2}]);
"""

    def _slide_swap(self, fl: str, tl: str, st: float, dur: float, p: Dict) -> str:
        et = st + dur
        mid_t = st + dur / 2
        return f"""
// Swap Transition (layers cross paths)
var comp = app.project.activeItem;
var fromLyr = comp.layer("{fl}");
var toLyr = comp.layer("{tl}");

var startPos = [{self.comp_width/2}, {self.comp_height/2}];
var midOffset = [{self.comp_width/2 + 200}, {self.comp_height/2 + 100}];
var endPos = [{self.comp_width/2}, {self.comp_height/2}];

fromLyr.property("Position").setValueAtTime({st}, startPos);
fromLyr.property("Position").setValueAtTime({mid_t}, midOffset);
fromLyr.property("Position").setValueAtTime({et}, startPos);
fromLyr.property("Opacity").setValueAtTime({st}, 100);
fromLyr.property("Opacity").setValueAtTime({et}, 0);

toLyr.property("Position").setValueAtTime({st}, [startPos[0] - 400, startPos[1] - 200]);
toLyr.property("Position").setValueAtTime({mid_t}, [midOffset[0] - 100, midOffset[1] + 50]);
toLyr.property("Position").setValueAtTime({et}, endPos);
toLyr.property("Opacity").setValueAtTime({st}, 0);
toLyr.property("Opacity").setValueAtTime({et}, 100);
"""

    def _slide_rotate(self, fl: str, tl: str, st: float, dur: float, p: Dict) -> str:
        et = st + dur
        return f"""
// Rotate Slide Transition
var comp = app.project.activeItem;
var fromLyr = comp.layer("{fl}");
var toLyr = comp.layer("{tl}");

fromLyr.property("Rotation").setValueAtTime({st}, 0);
fromLyr.property("Rotation").setValueAtTime({et}, {p.get("rotation_amount", 90)});
fromLyr.property("Opacity").setValueAtTime({st}, 100);
fromLyr.property("Opacity").setValueAtTime({et}, 0);

toLyr.property("Rotation").setValueAtTime({st}, {-p.get("rotation_amount", 90)});
toLyr.property("Rotation").setValueAtTime({et}, 0);
toLyr.property("Opacity").setValueAtTime({st}, 0);
toLyr.property("Opacity").setValueAtTime({et}, 100);
"""

    # -----------------------------------------------------------------------
    # 缩放过渡
    # -----------------------------------------------------------------------

    def create_zoom_transition(
        self,
        from_layer: str,
        to_layer: str,
        start_time: float,
        duration: float,
        params: Optional[Dict[str, Any]] = None,
    ) -> str:
        """创建缩放过渡"""
        end_time = start_time + duration
        p = params or {}
        zoom_amount = p.get("zoom_amount", 150)
        blur_amount = p.get("blur_amount", 30)
        return f"""
// Zoom Transition
var comp = app.project.activeItem;
var fromLyr = comp.layer("{from_layer}");
var toLyr = comp.layer("{to_layer}");

// From layer zoom out + blur
fromLyr.property("Scale").setValueAtTime({start_time}, [100, 100]);
fromLyr.property("Scale").setValueAtTime({end_time}, [{zoom_amount}, {zoom_amount}]);
fromLyr.property("Opacity").setValueAtTime({start_time}, 100);
fromLyr.property("Opacity").setValueAtTime({end_time}, 0);

var fromBlur = fromLyr.effect.addProperty("ADBE Gaussian Blur 2");
fromBlur.property("Blurriness").setValueAtTime({start_time}, 0);
fromBlur.property("Blurriness").setValueAtTime({end_time}, {blur_amount});
fromBlur.property("Blur Dimensions").setValue(1);

// To layer zoom in + blur
toLyr.property("Scale").setValueAtTime({start_time}, [{zoom_amount}, {zoom_amount}]);
toLyr.property("Scale").setValueAtTime({end_time}, [100, 100]);
toLyr.property("Opacity").setValueAtTime({start_time}, 0);
toLyr.property("Opacity").setValueAtTime({end_time}, 100);

var toBlur = toLyr.effect.addProperty("ADBE Gaussian Blur 2");
toBlur.property("Blurriness").setValueAtTime({start_time}, {blur_amount});
toBlur.property("Blurriness").setValueAtTime({end_time}, 0);
toBlur.property("Blur Dimensions").setValue(1);
"""

    # -----------------------------------------------------------------------
    # 3D 过渡
    # -----------------------------------------------------------------------

    def create_3d_transitions(
        self,
        transition_type: str,
        from_layer: str,
        to_layer: str,
        start_time: float,
        duration: float,
        params: Optional[Dict[str, Any]] = None,
    ) -> str:
        """创建 3D 过渡效果

        Args:
            transition_type: cube_flip, page_turn, door, card_wipe
        """
        params = params or {}
        t3d_map = {
            "cube_flip": self._3d_cube_flip,
            "page_turn": self._3d_page_turn,
            "door": self._3d_door,
            "card_wipe": self._3d_card_wipe,
        }
        func = t3d_map.get(transition_type, self._3d_cube_flip)
        return func(from_layer, to_layer, start_time, duration, params)

    def _create_3d_by_preset(self, fl, tl, st, dur, p):
        return self.create_3d_transitions(p.get("type", "cube_flip"), fl, tl, st, dur, p)

    def _3d_cube_flip(self, fl: str, tl: str, st: float, dur: float, p: Dict) -> str:
        et = st + dur
        return f"""
// 3D Cube Flip Transition
var comp = app.project.activeItem;
var fromLyr = comp.layer("{fl}");
var toLyr = comp.layer("{tl}");

// Enable 3D
fromLyr.threeDLayer = true;
toLyr.threeDLayer = true;

// Add camera if not exists
var cam = null;
for (var i = 1; i <= comp.numLayers; i++) {{
  if (comp.layer(i) instanceof CameraLayer) {{ cam = comp.layer(i); break; }}
}}
if (!cam) {{ cam = comp.layers.addCamera("Cam", [{self.comp_width/2}, {self.comp_height/2}]); }}

// Create null for rotation
var nullObj = comp.layers.addNull();
nullObj.name = "CubeCtrl";
nullObj.threeDLayer = true;

// Parent layers
fromLyr.parent = nullObj;
toLyr.parent = nullObj;

// Position layers on cube faces
fromLyr.property("Position").setValue([0, 0, 0]);
toLyr.property("Position").setValue([0, 0, -1]);

// Rotate cube
var rotAxis = "{p.get("axis", "x")}";
nullObj.property("Transform").property(rotAxis.toUpperCase() + " Rotation").setValueAtTime({st}, 0);
nullObj.property("Transform").property(rotAxis.toUpperCase() + " Rotation").setValueAtTime({et}, {p.get("rotation", -90)});

// Opacity swap based on rotation angle
fromLyr.property("Opacity").setValueAtTime({st}, 100);
fromLyr.property("Opacity").setValueAtTime({st + dur/2}, 0);
toLyr.property("Opacity").setValueAtTime({st + dur/2}, 0);
toLyr.property("Opacity").setValueAtTime({et}, 100);
"""

    def _3d_page_turn(self, fl: str, tl: str, st: float, dur: float, p: Dict) -> str:
        et = st + dur
        return f"""
// Page Turn Transition (CC Page Turn style)
var comp = app.project.activeItem;
var fromLyr = comp.layer("{fl}");
var toLyr = comp.layer("{tl}");

// Add CC Page Turn effect if available, fallback to basic 3D flip
var fx = fromLyr.effect.addProperty("ADBE CC Page Turn");
if (fx) {{
  fx.property("Fold Direction").setValueAtTime({st}, 0);
  fx.property("Fold Direction").setValueAtTime({et}, 100);
  fx.property("Light Direction").setValue({p.get("light_dir", 135)});
  fx.property("Back Page").setValue(2);
}} else {{
  // Fallback: basic fold with corner pin
  var cp = fromLyr.effect.addProperty("ADBE Corner Pin");
  cp.property("Upper Left").setValueAtTime({st}, [0, 0]);
  cp.property("Upper Left").setValueAtTime({et}, [{self.comp_width/2}, 0]);
  cp.property("Lower Left").setValueAtTime({st}, [0, {self.comp_height}]);
  cp.property("Lower Left").setValueAtTime({et}, [{self.comp_width/2}, {self.comp_height}]);
  fromLyr.property("Opacity").setValueAtTime({st}, 100);
  fromLyr.property("Opacity").setValueAtTime({et}, 0);
}}
"""

    def _3d_door(self, fl: str, tl: str, st: float, dur: float, p: Dict) -> str:
        et = st + dur
        return f"""
// 3D Door Transition
var comp = app.project.activeItem;
var fromLyr = comp.layer("{fl}");
var toLyr = comp.layer("{tl}");

fromLyr.threeDLayer = true;
toLyr.threeDLayer = true;

// Anchor point to left edge (hinge)
fromLyr.property("Anchor Point").setValue([0, {self.comp_height/2}, 0]);
fromLyr.property("Position").setValue([0, {self.comp_height/2}, 0]);

// Y Rotation (door swing open)
fromLyr.property("Y Rotation").setValueAtTime({st}, 0);
fromLyr.property("Y Rotation").setValueAtTime({et}, {p.get("rotation", -90)});

// To layer shows through
toLyr.property("Opacity").setValue(100);
"""

    def _3d_card_wipe(self, fl: str, tl: str, st: float, dur: float, p: Dict) -> str:
        et = st + dur
        rows = p.get("rows", 5)
        cols = p.get("columns", 5)
        return f"""
// Card Wipe / Card Dance Transition
var comp = app.project.activeItem;
var toLyr = comp.layer("{tl}");
var fx = toLyr.effect.addProperty("ADBE Card Wipe");
if (fx) {{
  fx.property("Transition Completion").setValueAtTime({st}, 0);
  fx.property("Transition Completion").setValueAtTime({et}, 100);
  fx.property("Rows & Columns").setValue(1);
  fx.property("Rows").setValue({rows});
  fx.property("Columns").setValue({cols});
  fx.property("Flip Direction").setValue({p.get("flip_dir", 0)});
  fx.property("Flip Order").setValue({p.get("flip_order", 0)});
  fx.property("Random Seed").setValue({p.get("seed", 12345)});
}}
"""

    # -----------------------------------------------------------------------
    # 光效类过渡
    # -----------------------------------------------------------------------

    def create_glow_transition(
        self,
        glow_type: str,
        from_layer: str,
        to_layer: str,
        start_time: float,
        duration: float,
        params: Optional[Dict[str, Any]] = None,
    ) -> str:
        """创建光效类过渡

        Args:
            glow_type: light_leak, optical_flare, lens_flare
        """
        params = params or {}
        glow_map = {
            "light_leak": self._glow_light_leak,
            "optical_flare": self._glow_optical_flare,
            "lens_flare": self._glow_lens_flare,
        }
        func = glow_map.get(glow_type, self._glow_light_leak)
        return func(from_layer, to_layer, start_time, duration, params)

    def _create_glow_by_preset(self, fl, tl, st, dur, p):
        return self.create_glow_transition(p.get("type", "light_leak"), fl, tl, st, dur, p)

    def _glow_light_leak(self, fl: str, tl: str, st: float, dur: float, p: Dict) -> str:
        et = st + dur
        mid_t = st + dur / 2
        return f"""
// Light Leak Transition
var comp = app.project.activeItem;
var fromLyr = comp.layer("{fl}");
var toLyr = comp.layer("{tl}");

// Create light leak solid
var leak = comp.layers.addSolid([1, 0.9, 0.7], "LightLeak", {self.comp_width}, {self.comp_height}, 1, {dur});
leak.startTime = {st};
leak.property("Opacity").setValueAtTime({st}, 0);
leak.property("Opacity").setValueAtTime({mid_t}, {p.get("intensity", 80)});
leak.property("Opacity").setValueAtTime({et}, 0);
leak.property("Blending Mode").setValue(BlendMode.ADD);

// Gradient ramp for light
var ramp = leak.effect.addProperty("ADBE Ramp");
ramp.property("Start of Ramp").setValue([0, {self.comp_height/2}]);
ramp.property("Start Color").setValue([1, 0.95, 0.8]);
ramp.property("End of Ramp").setValue([{self.comp_width}, {self.comp_height/2}]);
ramp.property("End Color").setValue([0.2, 0.1, 0]);
ramp.property("Ramp Shape").setValue(1);

// Crossfade layers
fromLyr.property("Opacity").setValueAtTime({st}, 100);
fromLyr.property("Opacity").setValueAtTime({et}, 0);
toLyr.property("Opacity").setValueAtTime({st}, 0);
toLyr.property("Opacity").setValueAtTime({et}, 100);
"""

    def _glow_optical_flare(self, fl: str, tl: str, st: float, dur: float, p: Dict) -> str:
        et = st + dur
        mid_t = st + dur / 2
        return f"""
// Optical Flare Transition
var comp = app.project.activeItem;
var fromLyr = comp.layer("{fl}");
var toLyr = comp.layer("{tl}");

// Create flare solid
var flare = comp.layers.addSolid([0,0,0], "OpticalFlare", {self.comp_width}, {self.comp_height}, 1, {dur});
flare.startTime = {st};
flare.property("Blending Mode").setValue(BlendMode.SCREEN);
flare.property("Opacity").setValueAtTime({st}, 0);
flare.property("Opacity").setValueAtTime({mid_t}, 100);
flare.property("Opacity").setValueAtTime({et}, 0);

// Lens flare effect
var fx = flare.effect.addProperty("ADBE Lens Flare");
fx.property("Flare Center").setValue([{self.comp_width/2}, {self.comp_height/2}]);
fx.property("Flare Brightness").setValueAtTime({st}, 0);
fx.property("Flare Brightness").setValueAtTime({mid_t}, {p.get("brightness", 200)});
fx.property("Flare Brightness").setValueAtTime({et}, 0);
fx.property("Lens Type").setValue({p.get("lens_type", 2)});

// Layer transition
fromLyr.property("Opacity").setValueAtTime({st}, 100);
fromLyr.property("Opacity").setValueAtTime({et}, 0);
toLyr.property("Opacity").setValueAtTime({st}, 0);
toLyr.property("Opacity").setValueAtTime({et}, 100);
"""

    def _glow_lens_flare(self, fl: str, tl: str, st: float, dur: float, p: Dict) -> str:
        return self._glow_optical_flare(fl, tl, st, dur, p)

    # -----------------------------------------------------------------------
    # 粒子类过渡
    # -----------------------------------------------------------------------

    def create_particle_transition(
        self,
        particle_type: str,
        from_layer: str,
        to_layer: str,
        start_time: float,
        duration: float,
        params: Optional[Dict[str, Any]] = None,
    ) -> str:
        """创建粒子类过渡

        Args:
            particle_type: particle_dissolve, pixel_polly, card_dance
        """
        params = params or {}
        particle_map = {
            "particle_dissolve": self._particle_dissolve,
            "pixel_polly": self._particle_pixel_polly,
            "card_dance": self._particle_card_dance,
        }
        func = particle_map.get(particle_type, self._particle_dissolve)
        return func(from_layer, to_layer, start_time, duration, params)

    def _create_particle_by_preset(self, fl, tl, st, dur, p):
        return self.create_particle_transition(p.get("type", "particle_dissolve"), fl, tl, st, dur, p)

    def _particle_dissolve(self, fl: str, tl: str, st: float, dur: float, p: Dict) -> str:
        et = st + dur
        return f"""
// Particle Dissolve Transition (using Shatter)
var comp = app.project.activeItem;
var fromLyr = comp.layer("{fl}");
var toLyr = comp.layer("{tl}");

var shatter = fromLyr.effect.addProperty("ADBE Shatter");
if (shatter) {{
  shatter.property("View").setValue(3);
  shatter.property("Render").setValue(0);
  shatter.property("Shape").property("Pattern").setValue({p.get("pattern", 2)});
  shatter.property("Shape").property("Repetitions").setValue({p.get("repetitions", 50)});
  shatter.property("Shape").property("Direction").setValue({p.get("direction", 0)});
  shatter.property("Physics").property("Gravity").setValue({p.get("gravity", 1)});
  shatter.property("Force 1").property("Position").setValue([{self.comp_width/2}, {self.comp_height/2}]);
  shatter.property("Force 1").property("Depth").setValue(0.5);
  shatter.property("Force 1").property("Radius").setValueAtTime({st}, 0);
  shatter.property("Force 1").property("Radius").setValueAtTime({et}, 2);
  shatter.property("Force 1").property("Strength").setValue({p.get("strength", 2)});
}}

fromLyr.property("Opacity").setValueAtTime({st}, 100);
fromLyr.property("Opacity").setValueAtTime({et}, 0);
toLyr.property("Opacity").setValue(100);
"""

    def _particle_pixel_polly(self, fl: str, tl: str, st: float, dur: float, p: Dict) -> str:
        et = st + dur
        return f"""
// Pixel Polly / Scatterize Transition
var comp = app.project.activeItem;
var fromLyr = comp.layer("{fl}");
var toLyr = comp.layer("{tl}");

// Use CC Pixel Polly if available, else scatterize
var fx = fromLyr.effect.addProperty("ADBE CC Pixel Polly");
if (fx) {{
  fx.property("Center").setValue([{self.comp_width/2}, {self.comp_height/2}]);
  fx.property("Force").setValueAtTime({st}, 0);
  fx.property("Force").setValueAtTime({et}, {p.get("force", 300)});
  fx.property("Gravity").setValue({p.get("gravity", 50)});
  fx.property("Spinning").setValue({p.get("spinning", 100)});
  fx.property("Direction Randomness").setValue(1);
  fx.property("Speed Randomness").setValue(1);
}} else {{
  var scatter = fromLyr.effect.addProperty("ADBE Scatterize");
  scatter.property("Scatter").setValueAtTime({st}, 0);
  scatter.property("Scatter").setValueAtTime({et}, 100);
}}

fromLyr.property("Opacity").setValueAtTime({st}, 100);
fromLyr.property("Opacity").setValueAtTime({et}, 0);
toLyr.property("Opacity").setValue(100);
"""

    def _particle_card_dance(self, fl: str, tl: str, st: float, dur: float, p: Dict) -> str:
        return self._3d_card_wipe(fl, tl, st, dur, p)

    # -----------------------------------------------------------------------
    # 扭曲类过渡
    # -----------------------------------------------------------------------

    def create_distort_transition(
        self,
        distort_type: str,
        from_layer: str,
        to_layer: str,
        start_time: float,
        duration: float,
        params: Optional[Dict[str, Any]] = None,
    ) -> str:
        """创建扭曲类过渡

        Args:
            distort_type: displacement_map, turbulent_displace, warp
        """
        params = params or {}
        distort_map = {
            "displacement_map": self._distort_displacement,
            "turbulent_displace": self._distort_turbulent,
            "warp": self._distort_warp,
        }
        func = distort_map.get(distort_type, self._distort_turbulent)
        return func(from_layer, to_layer, start_time, duration, params)

    def _create_distort_by_preset(self, fl, tl, st, dur, p):
        return self.create_distort_transition(p.get("type", "turbulent_displace"), fl, tl, st, dur, p)

    def _distort_displacement(self, fl: str, tl: str, st: float, dur: float, p: Dict) -> str:
        et = st + dur
        return f"""
// Displacement Map Transition
var comp = app.project.activeItem;
var fromLyr = comp.layer("{fl}");
var toLyr = comp.layer("{tl}");

// Create noise layer for displacement
var noiseLayer = comp.layers.addSolid([0.5, 0.5, 0.5], "DispMap", {self.comp_width}, {self.comp_height}, 1, {dur});
noiseLayer.startTime = {st};
noiseLayer.enabled = false;

var fractal = noiseLayer.effect.addProperty("ADBE Fractal Noise");
fractal.property("Scale").setValue({p.get("noise_scale", 100)});
fractal.property("Evolution").setValueAtTime({st}, 0);
fractal.property("Evolution").setValueAtTime({et}, 180);
fractal.property("Complexity").setValue({p.get("complexity", 5)});

// Displacement on both layers
var disp1 = fromLyr.effect.addProperty("ADBE Displacement Map");
disp1.property("Displacement Map Layer").setValue(noiseLayer.index);
disp1.property("Use For Horizontal Displacement").setValue(1);
disp1.property("Max Horizontal Displacement").setValueAtTime({st}, 0);
disp1.property("Max Horizontal Displacement").setValueAtTime({et}, {p.get("max_disp", 100)});
disp1.property("Use For Vertical Displacement").setValue(2);
disp1.property("Max Vertical Displacement").setValueAtTime({st}, 0);
disp1.property("Max Vertical Displacement").setValueAtTime({et}, {p.get("max_disp", 100)});

var disp2 = toLyr.effect.addProperty("ADBE Displacement Map");
disp2.property("Displacement Map Layer").setValue(noiseLayer.index);
disp2.property("Use For Horizontal Displacement").setValue(1);
disp2.property("Max Horizontal Displacement").setValueAtTime({st}, {p.get("max_disp", 100)});
disp2.property("Max Horizontal Displacement").setValueAtTime({et}, 0);
disp2.property("Use For Vertical Displacement").setValue(2);
disp2.property("Max Vertical Displacement").setValueAtTime({st}, {p.get("max_disp", 100)});
disp2.property("Max Vertical Displacement").setValueAtTime({et}, 0);

fromLyr.property("Opacity").setValueAtTime({st}, 100);
fromLyr.property("Opacity").setValueAtTime({et}, 0);
toLyr.property("Opacity").setValueAtTime({st}, 0);
toLyr.property("Opacity").setValueAtTime({et}, 100);
"""

    def _distort_turbulent(self, fl: str, tl: str, st: float, dur: float, p: Dict) -> str:
        et = st + dur
        mid_t = st + dur / 2
        return f"""
// Turbulent Displace Transition
var comp = app.project.activeItem;
var fromLyr = comp.layer("{fl}");
var toLyr = comp.layer("{tl}");

var td1 = fromLyr.effect.addProperty("ADBE Turbulent Displace");
td1.property("Displacement").setValue({p.get("amount", 50)});
td1.property("Size").setValue({p.get("size", 50)});
td1.property("Complexity").setValue({p.get("complexity", 5)});
td1.property("Evolution").setValueAtTime({st}, 0);
td1.property("Evolution").setValueAtTime({et}, 180);
td1.property("Amount").setValueAtTime({st}, 0);
td1.property("Amount").setValueAtTime({mid_t}, {p.get("amount", 50)});
td1.property("Amount").setValueAtTime({et}, 0);

var td2 = toLyr.effect.addProperty("ADBE Turbulent Displace");
td2.property("Displacement").setValue({p.get("amount", 50)});
td2.property("Size").setValue({p.get("size", 50)});
td2.property("Complexity").setValue({p.get("complexity", 5)});
td2.property("Evolution").setValueAtTime({st}, 180);
td2.property("Evolution").setValueAtTime({et}, 360);
td2.property("Amount").setValueAtTime({st}, 0);
td2.property("Amount").setValueAtTime({mid_t}, {p.get("amount", 50)});
td2.property("Amount").setValueAtTime({et}, 0);

fromLyr.property("Opacity").setValueAtTime({st}, 100);
fromLyr.property("Opacity").setValueAtTime({et}, 0);
toLyr.property("Opacity").setValueAtTime({st}, 0);
toLyr.property("Opacity").setValueAtTime({et}, 100);
"""

    def _distort_warp(self, fl: str, tl: str, st: float, dur: float, p: Dict) -> str:
        et = st + dur
        return f"""
// Warp / Mesh Warp Transition
var comp = app.project.activeItem;
var fromLyr = comp.layer("{fl}");
var toLyr = comp.layer("{tl}");

var warp1 = fromLyr.effect.addProperty("ADBE Mesh Warp");
if (warp1) {{
  warp1.property("Rows").setValue({p.get("rows", 7)});
  warp1.property("Columns").setValue({p.get("columns", 7)});
  warp1.property("Quality").setValue({p.get("quality", 10)});
}}

fromLyr.property("Scale").setValueAtTime({st}, [100, 100]);
fromLyr.property("Scale").setValueAtTime({et}, [200, 200]);
fromLyr.property("Opacity").setValueAtTime({st}, 100);
fromLyr.property("Opacity").setValueAtTime({et}, 0);
toLyr.property("Opacity").setValue(100);
"""

    # -----------------------------------------------------------------------
    # 故障类过渡
    # -----------------------------------------------------------------------

    def create_glitch_transition(
        self,
        glitch_type: str,
        from_layer: str,
        to_layer: str,
        start_time: float,
        duration: float,
        params: Optional[Dict[str, Any]] = None,
    ) -> str:
        """创建故障类过渡

        Args:
            glitch_type: rgb_split, digital_noise, vhs
        """
        params = params or {}
        glitch_map = {
            "rgb_split": self._glitch_rgb_split,
            "digital_noise": self._glitch_digital_noise,
            "vhs": self._glitch_vhs,
        }
        func = glitch_map.get(glitch_type, self._glitch_rgb_split)
        return func(from_layer, to_layer, start_time, duration, params)

    def _create_glitch_by_preset(self, fl, tl, st, dur, p):
        return self.create_glitch_transition(p.get("type", "rgb_split"), fl, tl, st, dur, p)

    def _glitch_rgb_split(self, fl: str, tl: str, st: float, dur: float, p: Dict) -> str:
        et = st + dur
        return f"""
// RGB Split Glitch Transition
var comp = app.project.activeItem;
var fromLyr = comp.layer("{fl}");
var toLyr = comp.layer("{tl}");

// Create adjustment layer for RGB split
var adj = comp.layers.addSolid([1,1,1], "Glitch_Adjust", {self.comp_width}, {self.comp_height}, 1, {dur});
adj.startTime = {st};
adj.adjustmentLayer = true;

// Shift channels
var ch = adj.effect.addProperty("ADBE Shift Channels");
ch.property("Take Red From").setValue(1);
ch.property("Take Green From").setValue(2);
ch.property("Take Blue From").setValue(3);

// Add transform for channel offset
var transform = adj.effect.addProperty("ADBE Transform2");
transform.property("Use Composition's Shutter Angle").setValue(true);

// Red channel offset
var adjR = adj.duplicate();
adjR.name = "Glitch_Red";
var chR = adjR.effect.addProperty("ADBE Shift Channels");
chR.property("Take Red From").setValue(1);
chR.property("Take Green From").setValue(1);
chR.property("Take Blue From").setValue(1);
adjR.property("Opacity").setValue(33);
adjR.property("Transform").property("Position").setValueAtTime({st}, [{self.comp_width/2}, {self.comp_height/2}]);
adjR.property("Transform").property("Position").setValueAtTime({et}, [{self.comp_width/2 + p.get("offset", 20)}, {self.comp_height/2}]);

// Blue channel offset
var adjB = adj.duplicate();
adjB.name = "Glitch_Blue";
var chB = adjB.effect.addProperty("ADBE Shift Channels");
chB.property("Take Red From").setValue(3);
chB.property("Take Green From").setValue(3);
chB.property("Take Blue From").setValue(3);
adjB.property("Opacity").setValue(33);
adjB.property("Transform").property("Position").setValueAtTime({st}, [{self.comp_width/2}, {self.comp_height/2}]);
adjB.property("Transform").property("Position").setValueAtTime({et}, [{self.comp_width/2 - p.get("offset", 20)}, {self.comp_height/2}]);

adj.property("Opacity").setValue(34);

fromLyr.property("Opacity").setValueAtTime({st}, 100);
fromLyr.property("Opacity").setValueAtTime({et}, 0);
toLyr.property("Opacity").setValueAtTime({st}, 0);
toLyr.property("Opacity").setValueAtTime({et}, 100);
"""

    def _glitch_digital_noise(self, fl: str, tl: str, st: float, dur: float, p: Dict) -> str:
        et = st + dur
        mid_t = st + dur / 2
        return f"""
// Digital Noise Glitch Transition
var comp = app.project.activeItem;
var fromLyr = comp.layer("{fl}");
var toLyr = comp.layer("{tl}");

// Noise layer
var noise = comp.layers.addSolid([0,0,0], "DigitalNoise", {self.comp_width}, {self.comp_height}, 1, {dur});
noise.startTime = {st};
noise.property("Blending Mode").setValue(BlendMode.OVERLAY);
noise.property("Opacity").setValueAtTime({st}, 0);
noise.property("Opacity").setValueAtTime({mid_t}, {p.get("intensity", 60)});
noise.property("Opacity").setValueAtTime({et}, 0);

var fx = noise.effect.addProperty("ADBE Noise Alpha");
fx.property("Amount").setValue({p.get("noise_amount", 100)});
fx.property("Use Noise").setValue(0);

// Add block glitch (posterize time + levels)
var posterize = noise.effect.addProperty("ADBE Posterize Time");
posterize.property("Frame Rate").setValue({p.get("fps", 8)});

fromLyr.property("Opacity").setValueAtTime({st}, 100);
fromLyr.property("Opacity").setValueAtTime({et}, 0);
toLyr.property("Opacity").setValueAtTime({st}, 0);
toLyr.property("Opacity").setValueAtTime({et}, 100);
"""

    def _glitch_vhs(self, fl: str, tl: str, st: float, dur: float, p: Dict) -> str:
        et = st + dur
        return f"""
// VHS Glitch Transition
var comp = app.project.activeItem;
var fromLyr = comp.layer("{fl}");
var toLyr = comp.layer("{tl}");

// VHS adjustment
var vhs = comp.layers.addSolid([1,1,1], "VHS_Glitch", {self.comp_width}, {self.comp_height}, 1, {dur});
vhs.startTime = {st};
vhs.adjustmentLayer = true;

// Color channels offset
var cc = vhs.effect.addProperty("ADBE Color Balance");
cc.property("Red").setValueAtTime({st}, 0);
cc.property("Red").setValueAtTime({et}, {p.get("color_shift", 10)});
cc.property("Blue").setValueAtTime({st}, 0);
cc.property("Blue").setValueAtTime({et}, -{p.get("color_shift", 10)});

// Scan lines
var scanlines = vhs.effect.addProperty("ADBE Grid");
scanlines.property("Size From").setValue(1);
scanlines.property("Width").setValue({p.get("scanline_width", 2)});
scanlines.property("Height").setValue({p.get("scanline_height", 4)});
scanlines.property("Border").setValue(1);
scanlines.property("Blending Mode").setValue(2);

// Noise
var noise = vhs.effect.addProperty("ADBE Noise Alpha");
noise.property("Amount").setValue({p.get("noise", 20)});

vhs.property("Opacity").setValueAtTime({st}, 0);
vhs.property("Opacity").setValueAtTime({st + dur/2}, 100);
vhs.property("Opacity").setValueAtTime({et}, 0);

fromLyr.property("Opacity").setValueAtTime({st}, 100);
fromLyr.property("Opacity").setValueAtTime({et}, 0);
toLyr.property("Opacity").setValueAtTime({st}, 0);
toLyr.property("Opacity").setValueAtTime({et}, 100);
"""

    # -----------------------------------------------------------------------
    # 形状过渡
    # -----------------------------------------------------------------------

    def create_shape_transition(
        self,
        shape_type: str,
        from_layer: str,
        to_layer: str,
        start_time: float,
        duration: float,
        params: Optional[Dict[str, Any]] = None,
    ) -> str:
        """创建形状遮罩过渡

        Args:
            shape_type: circle, diamond, heart, custom_mask
        """
        params = params or {}
        shape_map = {
            "circle": self._shape_circle,
            "diamond": self._shape_diamond,
            "heart": self._shape_heart,
            "custom_mask": self._shape_custom,
        }
        func = shape_map.get(shape_type, self._shape_circle)
        return func(from_layer, to_layer, start_time, duration, params)

    def _create_shape_by_preset(self, fl, tl, st, dur, p):
        return self.create_shape_transition(p.get("type", "circle"), fl, tl, st, dur, p)

    def _shape_circle(self, fl: str, tl: str, st: float, dur: float, p: Dict) -> str:
        et = st + dur
        max_radius = math.sqrt(self.comp_width**2 + self.comp_height**2) / 2 + 100
        return f"""
// Circle Wipe Shape Transition
var comp = app.project.activeItem;
var toLyr = comp.layer("{tl}");

var mask = toLyr.masks.addProperty("ADBE Mask Atom");
mask.name = "CircleWipe";

var path = new Shape();
path.vertices = [[{self.comp_width/2}, {self.comp_height/2}]];
path.closed = true;

mask.property("ADBE Mask Shape").setValueAtTime({st},
  ellipsePath([{self.comp_width/2}, {self.comp_height/2}], 0, 0));
mask.property("ADBE Mask Shape").setValueAtTime({et},
  ellipsePath([{self.comp_width/2}, {self.comp_height/2}], {max_radius}, {max_radius}));

mask.property("ADBE Mask Feather").setValue({p.get("feather", 20)});

function ellipsePath(center, w, h) {{
  var s = new Shape();
  s.vertices = [];
  s.inTangents = [];
  s.outTangents = [];
  for (var i = 0; i < 4; i++) {{
    var angle = i * Math.PI / 2;
    s.vertices.push([center[0] + w * Math.cos(angle), center[1] + h * Math.sin(angle)]);
  }}
  s.closed = true;
  return s;
}}
"""

    def _shape_diamond(self, fl: str, tl: str, st: float, dur: float, p: Dict) -> str:
        et = st + dur
        max_size = max(self.comp_width, self.comp_height)
        return f"""
// Diamond Shape Transition
var comp = app.project.activeItem;
var toLyr = comp.layer("{tl}");

var mask = toLyr.masks.addProperty("ADBE Mask Atom");
mask.name = "DiamondWipe";

// Diamond shape function
function diamondShape(cx, cy, size) {{
  var s = new Shape();
  s.vertices = [
    [cx, cy - size],
    [cx + size, cy],
    [cx, cy + size],
    [cx - size, cy]
  ];
  s.closed = true;
  return s;
}}

mask.property("ADBE Mask Shape").setValueAtTime({st},
  diamondShape({self.comp_width/2}, {self.comp_height/2}, 0));
mask.property("ADBE Mask Shape").setValueAtTime({et},
  diamondShape({self.comp_width/2}, {self.comp_height/2}, {max_size}));

mask.property("ADBE Mask Feather").setValue({p.get("feather", 15)});
"""

    def _shape_heart(self, fl: str, tl: str, st: float, dur: float, p: Dict) -> str:
        et = st + dur
        return f"""
// Heart Shape Transition
var comp = app.project.activeItem;
var toLyr = comp.layer("{tl}");

var mask = toLyr.masks.addProperty("ADBE Mask Atom");
mask.name = "HeartWipe";

function heartShape(cx, cy, size) {{
  var s = new Shape();
  var pts = 12;
  s.vertices = [];
  for (var i = 0; i < pts; i++) {{
    var t = (i / pts) * Math.PI * 2;
    var x = 16 * Math.pow(Math.sin(t), 3);
    var y = -(13 * Math.cos(t) - 5 * Math.cos(2*t) - 2 * Math.cos(3*t) - Math.cos(4*t));
    s.vertices.push([cx + x * size / 16, cy + y * size / 16]);
  }}
  s.closed = true;
  return s;
}}

mask.property("ADBE Mask Shape").setValueAtTime({st},
  heartShape({self.comp_width/2}, {self.comp_height/2}, 0));
mask.property("ADBE Mask Shape").setValueAtTime({et},
  heartShape({self.comp_width/2}, {self.comp_height/2}, 600));

mask.property("ADBE Mask Feather").setValue({p.get("feather", 10)});
"""

    def _shape_custom(self, fl: str, tl: str, st: float, dur: float, p: Dict) -> str:
        mask_path = p.get("mask_path", [])
        et = st + dur
        return f"""
// Custom Mask Shape Transition
var comp = app.project.activeItem;
var toLyr = comp.layer("{tl}");
var mask = toLyr.masks.addProperty("ADBE Mask Atom");
mask.name = "CustomShape";

// Scale mask from center
var cx = {self.comp_width/2};
var cy = {self.comp_height/2};

function scaleShape(scale) {{
  var s = new Shape();
  s.vertices = [];
  var basePts = {json.dumps(mask_path)};
  for (var i = 0; i < basePts.length; i++) {{
    s.vertices.push([
      cx + (basePts[i][0] - cx) * scale,
      cy + (basePts[i][1] - cy) * scale
    ]);
  }}
  s.closed = true;
  return s;
}}

mask.property("ADBE Mask Shape").setValueAtTime({st}, scaleShape(0));
mask.property("ADBE Mask Shape").setValueAtTime({et}, scaleShape(1));
mask.property("ADBE Mask Feather").setValue({p.get("feather", 5)});
"""

    # -----------------------------------------------------------------------
    # 文字过渡
    # -----------------------------------------------------------------------

    def create_text_transition(
        self,
        text_type: str,
        from_layer: str,
        to_layer: str,
        start_time: float,
        duration: float,
        params: Optional[Dict[str, Any]] = None,
    ) -> str:
        """创建文字过渡效果

        Args:
            text_type: typewriter_reveal, text_wipe
        """
        params = params or {}
        text_map = {
            "typewriter_reveal": self._text_typewriter,
            "text_wipe": self._text_wipe,
        }
        func = text_map.get(text_type, self._text_typewriter)
        return func(from_layer, to_layer, start_time, duration, params)

    def _create_text_by_preset(self, fl, tl, st, dur, p):
        return self.create_text_transition(p.get("type", "typewriter_reveal"), fl, tl, st, dur, p)

    def _text_typewriter(self, fl: str, tl: str, st: float, dur: float, p: Dict) -> str:
        et = st + dur
        return f"""
// Typewriter Text Reveal Transition
var comp = app.project.activeItem;
var toLyr = comp.layer("{tl}");

// Check if text layer
if (toLyr instanceof TextLayer) {{
  var textProp = toLyr.property("Source Text");
  var fullText = textProp.value.text;
  var len = fullText.length;
  var steps = Math.min(len, {p.get("steps", 20)});

  for (var i = 0; i <= steps; i++) {{
    var t = {st} + ({dur} * i / steps);
    var charCount = Math.floor(len * i / steps);
    var partial = fullText.substring(0, charCount);
    var doc = new TextDocument(partial);
    textProp.setValueAtTime(t, doc);
  }}
}}

toLyr.property("Opacity").setValueAtTime({st}, 100);
fromLyr.property("Opacity").setValueAtTime({st}, 100);
fromLyr.property("Opacity").setValueAtTime({et}, 0);
"""

    def _text_wipe(self, fl: str, tl: str, st: float, dur: float, p: Dict) -> str:
        et = st + dur
        return f"""
// Text Wipe Transition (linear wipe on text layer)
var comp = app.project.activeItem;
var toLyr = comp.layer("{tl}");

var fx = toLyr.effect.addProperty("ADBE Linear Wipe");
fx.property("Transition Completion").setValueAtTime({st}, 100);
fx.property("Transition Completion").setValueAtTime({et}, 0);
fx.property("Wipe Angle").setValue({p.get("angle", 270)});
fx.property("Feather").setValue({p.get("feather", 2)});

fromLyr.property("Opacity").setValueAtTime({st}, 100);
fromLyr.property("Opacity").setValueAtTime({et}, 0);
toLyr.property("Opacity").setValue(100);
"""

    # -----------------------------------------------------------------------
    # 颜色 & 运动模糊过渡
    # -----------------------------------------------------------------------

    def create_color_transition(
        self,
        from_layer: str,
        to_layer: str,
        start_time: float,
        duration: float,
        params: Optional[Dict[str, Any]] = None,
    ) -> str:
        """创建颜色过渡（闪白/闪黑/色彩渐变）"""
        et = start_time + duration
        mid_t = start_time + duration / 2
        p = params or {}
        color_type = p.get("color_type", "flash_white")
        color = p.get("color", [1, 1, 1])
        return f"""
// Color Flash Transition
var comp = app.project.activeItem;
var fromLyr = comp.layer("{from_layer}");
var toLyr = comp.layer("{to_layer}");

var solid = comp.layers.addSolid([{color[0]}, {color[1]}, {color[2]}],
  "ColorFlash", {self.comp_width}, {self.comp_height}, 1, {duration});
solid.startTime = {start_time};
solid.property("Opacity").setValueAtTime({start_time}, 0);
solid.property("Opacity").setValueAtTime({mid_t}, {p.get("intensity", 100)});
solid.property("Opacity").setValueAtTime({et}, 0);

fromLyr.property("Opacity").setValueAtTime({start_time}, 100);
fromLyr.property("Opacity").setValueAtTime({et}, 0);
toLyr.property("Opacity").setValueAtTime({start_time}, 0);
toLyr.property("Opacity").setValueAtTime({et}, 100);
"""

    def create_motion_blur_transition(
        self,
        from_layer: str,
        to_layer: str,
        start_time: float,
        duration: float,
        params: Optional[Dict[str, Any]] = None,
    ) -> str:
        """创建运动模糊过渡"""
        et = start_time + duration
        p = params or {}
        return f"""
// Motion Blur Transition
var comp = app.project.activeItem;
var fromLyr = comp.layer("{from_layer}");
var toLyr = comp.layer("{to_layer}");

// Enable motion blur
comp.property("ADBE Comp MotionBlur").setValue(true);
fromLyr.property("ADBE Layer MotionBlur").setValue(true);
toLyr.property("ADBE Layer MotionBlur").setValue(true);

// Directional blur on from layer
var blur1 = fromLyr.effect.addProperty("ADBE Directional Blur");
blur1.property("Blur Length").setValueAtTime({start_time}, 0);
blur1.property("Blur Length").setValueAtTime({et}, {p.get("blur_amount", 100)});
blur1.property("Direction").setValue({p.get("direction", 0)});

// Directional blur on to layer
var blur2 = toLyr.effect.addProperty("ADBE Directional Blur");
blur2.property("Blur Length").setValueAtTime({start_time}, {p.get("blur_amount", 100)});
blur2.property("Blur Length").setValueAtTime({et}, 0);
blur2.property("Direction").setValue({p.get("direction", 0)});

fromLyr.property("Opacity").setValueAtTime({start_time}, 100);
fromLyr.property("Opacity").setValueAtTime({et}, 0);
toLyr.property("Opacity").setValueAtTime({start_time}, 0);
toLyr.property("Opacity").setValueAtTime({et}, 100);
"""

    def generate_jsx_script(self, transitions: List[Dict[str, Any]]) -> str:
        """生成完整的 AE JSX 脚本

        Args:
            transitions: 过渡配置列表

        Returns:
            完整的 JSX 脚本代码
        """
        script_parts = ["""
// ============================================================
// Auto-Generated Transition Script
// Generated by Transition Engine v2.0
// ============================================================

app.beginUndoGroup("Apply Transitions");
try {
"""]
        for t in transitions:
            preset = t.get("preset")
            if isinstance(preset, TransitionPreset):
                jsx = self.apply_transition(
                    preset,
                    t["from_layer"],
                    t["to_layer"],
                    t["start_time"],
                    t["duration"],
                )
                script_parts.append(jsx)

        script_parts.append("""
} catch (e) {
    alert("Transition Error: " + e.toString());
}
app.endUndoGroup();
""")
        return "\n".join(script_parts)


# ===========================================================================
# 4. Premiere Pro 过渡引擎
# ===========================================================================

class PRTransitionEngine:
    """Premiere Pro 过渡效果引擎

    支持 Premiere Pro 内置过渡的应用与自定义过渡创建。
    """

    BUILTIN_TRANSITIONS = {
        "cross_dissolve": "Cross Dissolve",
        "dip_to_black": "Dip to Black",
        "dip_to_white": "Dip to White",
        "film_dissolve": "Film Dissolve",
        "additive_dissolve": "Additive Dissolve",
        "non_additive_dissolve": "Non-Additive Dissolve",
        "random_invert": "Random Invert",
        "cross_zoom": "Cross Zoom",
        "zoom": "Zoom",
        "zoom_trails": "Zoom Trails",
        "pinwheel": "Pinwheel",
        "galaxy": "Galaxy",
        "cube_spin": "Cube Spin",
        "flip_over": "Flip Over",
        "fold_up": "Fold Up",
        "roll_away": "Roll Away",
        "spin": "Spin",
        "spin_away": "Spin Away",
        "swirl": "Swirl",
        "tumble_away": "Tumble Away",
        "wipe": "Wipe",
        "band_wipe": "Band Wipe",
        "barn_door": "Barn Doors",
        "checker_wipe": "Checker Wipe",
        "clock_wipe": "Clock Wipe",
        "gradient_wipe": "Gradient Wipe",
        "heart_wipe": "Heart Wipe",
        "inset": "Inset",
        "iris": "Iris",
        "iris_round": "Iris Round",
        "iris_star": "Iris Star",
        "paint_splatter": "Paint Splatter",
        "pinwheel_wipe": "Pinwheel",
        "radial_wipe": "Radial Wipe",
        "random_blocks": "Random Blocks",
        "random_wipe": "Random Wipe",
        "spiral_boxes": "Spiral Boxes",
        "venetian_blinds": "Venetian Blinds",
        "wedge_wipe": "Wedge Wipe",
        "zig-zag_blocks": "Zig-Zag Blocks",
        "push": "Push",
        "slide": "Slide",
        "sliding_bands": "Sliding Bands",
        "sliding_boxes": "Sliding Boxes",
        "split": "Split",
        "swap": "Swap",
        "page_turn": "Page Turn",
        "page_peel": "Page Peel",
        "center_peel": "Center Peel",
        "roll_away_page": "Roll Away",
        "door": "Door",
        "morph_cut": "Morph Cut",
        "luma_cut": "Luma Cut",
        "cross_blur": "Cross Blur",
        "dissolve_pattern": "Dissolve Pattern",
        "light_gradient_wipe": "Light Gradient Wipe",
        "invert": "Invert",
        "texture": "Texture",
    }

    def __init__(self) -> None:
        pass

    def apply_builtin_transition(
        self,
        transition_name: str,
        track_index: int,
        clip_index: int,
        duration: float = 0.5,
        alignment: str = "center",
    ) -> str:
        """应用 Premiere Pro 内置过渡

        Args:
            transition_name: 过渡名称（见 BUILTIN_TRANSITIONS）
            track_index: 轨道索引
            clip_index: 剪辑索引（编辑点位置）
            duration: 持续时间（秒）
            alignment: 对齐方式 - start/center/end

        Returns:
            Premiere Pro JSX 脚本
        """
        pr_name = self.BUILTIN_TRANSITIONS.get(transition_name, transition_name)
        align_map = {"start": 0, "center": 1, "end": 2}
        align = align_map.get(alignment, 1)
        return f"""
// Apply PR Built-in Transition: {pr_name}
var seq = app.project.activeSequence;
var track = seq.videoTracks[{track_index}];
var clip = track.clips[{clip_index}];
var transition = track.addTransition(
  "{pr_name}",
  {clip_index},
  {align}
);
if (transition) {{
  transition.duration = {duration};
}}
"""

    def create_custom_transition(
        self,
        from_clip: str,
        to_clip: str,
        effect_chain: List[Dict[str, Any]],
        duration: float = 0.5,
    ) -> str:
        """创建自定义过渡（调整图层 + 效果链）

        Args:
            from_clip: 起始剪辑名称
            to_clip: 目标剪辑名称
            effect_chain: 效果列表
            duration: 持续时间

        Returns:
            JSX 脚本
        """
        effects_code = []
        for i, fx in enumerate(effect_chain):
            effects_code.append(f"""
  var fx{i} = adj.effects.addProperty("{fx.get('match_name', '')}");
  // set effect parameters
""")
        return f"""
// Custom Transition with Adjustment Layer
var seq = app.project.activeSequence;

// Create adjustment layer
var adj = seq.videoTracks[0].addAdjustmentLayer();
adj.name = "Custom_Transition_Adjustment";
adj.start = ...; // set at edit point
adj.duration = {duration};

{''.join(effects_code)}
"""

    def apply_morph_cut(
        self,
        track_index: int,
        clip_index: int,
        duration: float = 0.3,
    ) -> str:
        """应用 Morph Cut 过渡（用于对话剪辑）

        Args:
            track_index: 轨道索引
            clip_index: 剪辑索引
            duration: 持续时间（建议 0.2-0.5 秒）

        Returns:
            JSX 脚本
        """
        return f"""
// Morph Cut Transition (for talking heads)
var seq = app.project.activeSequence;
var track = seq.videoTracks[{track_index}];
var transition = track.addTransition("Morph Cut", {clip_index}, 1);
if (transition) {{
  transition.duration = {duration};
}}
"""

    def create_transition_preset(
        self,
        preset_name: str,
        effects: List[Dict[str, Any]],
        duration: float = 0.5,
    ) -> str:
        """创建自定义过渡预设"""
        return f"""
// Create Custom Transition Preset: {preset_name}
var preset = new TransitionPreset();
preset.name = "{preset_name}";
preset.duration = {duration};
// Add effects to preset
"""

    def batch_apply_transitions(
        self,
        transition_name: str,
        track_index: int = 0,
        duration: float = 0.5,
    ) -> str:
        """批量应用过渡到所有编辑点

        Args:
            transition_name: 过渡名称
            track_index: 轨道索引
            duration: 持续时间

        Returns:
            JSX 脚本
        """
        return f"""
// Batch Apply Transitions
var seq = app.project.activeSequence;
var track = seq.videoTracks[{track_index}];
var clipCount = track.clips.numItems;

for (var i = 1; i < clipCount - 1; i++) {{
  try {{
    var trans = track.addTransition("{transition_name}", i, 1);
    if (trans) {{
      trans.duration = {duration};
    }}
  }} catch(e) {{}}
}}
"""

    def generate_pr_script(self, operations: List[Dict[str, Any]]) -> str:
        """生成完整的 Premiere Pro 脚本"""
        script = """
// Premiere Pro Transition Script
// Generated by Transition Engine v2.0

app.beginUndoGroup("Batch Transitions");
try {
"""
        for op in operations:
            if op["type"] == "builtin":
                script += self.apply_builtin_transition(
                    op["transition"],
                    op.get("track", 0),
                    op.get("clip_index", 0),
                    op.get("duration", 0.5),
                )
        script += """
} catch(e) {
    alert("PR Transition Error: " + e.toString());
}
app.endUndoGroup();
"""
        return script


# ===========================================================================
# 5. DaVinci Resolve 过渡引擎
# ===========================================================================

class ResolveTransitionEngine:
    """DaVinci Resolve 过渡效果引擎

    支持 Edit 页面内置过渡、Fusion 自定义过渡和 Color 页面节点过渡。
    """

    EDIT_TRANSITIONS = [
        "Cross Dissolve", "Dip to Color", "Non-Additive Dissolve",
        "Additive Dissolve", "Wipe", "Push", "Slide", "Barn Door",
        "Checkerboard", "Clock Wipe", "Gradient Wipe", "Heart",
        "Iris", "Pinwheel", "Radial Wipe", "Random Blocks",
        "Spiral Box", "Venetian Blinds", "Zoom", "Cross Zoom",
        "Cube Spin", "Flip", "Fold Up", "Roll Away", "Spin",
        "Swirl", "Tumble Away", "Page Peel", "Page Turn",
        "Morph Dissolve", "Film Dissolve", "Glow Dissolve",
    ]

    def __init__(self) -> None:
        pass

    def apply_edit_page_transition(
        self,
        transition_name: str,
        timeline_name: str,
        track_index: int,
        item_index: int,
        duration: float = 0.5,
    ) -> str:
        """在 Edit 页面应用过渡效果

        Args:
            transition_name: 过渡名称
            timeline_name: 时间线名称
            track_index: 轨道索引
            item_index: 剪辑项索引
            duration: 持续时间（秒）

        Returns:
            Resolve Python 脚本
        """
        return f'''
# Resolve Edit Page Transition
import DaVinciResolveScript as dvr
resolve = dvr.scriptapp("Resolve")
projectManager = resolve.GetProjectManager()
project = projectManager.GetCurrentProject()
timeline = project.GetTimelineByName("{timeline_name}")

if timeline:
    track = timeline.GetItemsInTrack("video", {track_index})
    if track and {item_index} < len(track):
        item = track[{item_index}]
        # Add transition
        transition = timeline.AddTransition(
            "{transition_name}",
            {item_index},
            {duration}
        )
'''

    def create_fusion_transition(
        self,
        transition_type: str,
        from_node: str,
        to_node: str,
        duration: float = 0.5,
    ) -> str:
        """创建 Fusion 过渡节点

        Args:
            transition_type: 过渡类型
            from_node: 起始节点名
            to_node: 目标节点名
            duration: 持续时间

        Returns:
            Fusion 节点代码
        """
        return f'''
# Fusion Transition Setup
# Type: {transition_type}
# This would be pasted into Fusion page as nodes

comp = fu.GetCurrentComp()
comp.Lock()

try:
    # Create dissolve node
    dissolve = comp.AddTool("Dissolve", comp.CurrentFrame.FlowView.Select())

    # Connect inputs
    dissolve.ForegroundInput = comp.FindTool("{to_node}").Output
    dissolve.BackgroundInput = comp.FindTool("{from_node}").Output

    # Animate mix
    dissolve.Mix = comp.BezierSpline()
    dissolve.Mix.AddKeyFrame(0, 0)
    dissolve.Mix.AddKeyFrame({duration}, 1)

finally:
    comp.Unlock()
'''

    def create_node_transition(
        self,
        transition_type: str,
        duration: float = 0.5,
    ) -> str:
        """创建 Color 页面节点过渡结构

        Args:
            transition_type: 过渡类型
            duration: 持续时间

        Returns:
            Resolve Color 脚本
        """
        return f'''
# Resolve Color Page Transition Nodes
import DaVinciResolveScript as dvr

resolve = dvr.scriptapp("Resolve")
pm = resolve.GetProjectManager()
proj = pm.GetCurrentProject()
timeline = proj.GetCurrentTimeline()

if timeline:
    # Get current clip
    clip = timeline.GetCurrentVideoItem()

    # Add transition node structure
    # (serializer/deserializer pattern for node graph)
    pass
'''

    def generate_setting_file(
        self,
        transition_name: str,
        nodes_config: Dict[str, Any],
    ) -> str:
        """生成 Fusion .setting 文件内容

        Args:
            transition_name: 过渡名称
            nodes_config: 节点配置

        Returns:
            .setting 文件内容（JSON 格式）
        """
        setting = {
            "Tools": {
                "TransitionName": transition_name,
                "Config": nodes_config,
            },
            "Version": "1.0",
        }
        return json.dumps(setting, indent=2)

    def generate_resolve_script(self, operations: List[Dict[str, Any]]) -> str:
        """生成完整的 Resolve Python 脚本"""
        script = '''
# ============================================================
# DaVinci Resolve Transition Script
# Generated by Transition Engine v2.0
# ============================================================

import DaVinciResolveScript as dvr
import sys

def main():
    resolve = dvr.scriptapp("Resolve")
    if not resolve:
        print("Resolve not running")
        return

    projectManager = resolve.GetProjectManager()
    project = projectManager.GetCurrentProject()
    if not project:
        print("No project open")
        return
'''
        for op in operations:
            if op["type"] == "edit_transition":
                script += f'''
    # Edit page transition: {op.get("name", "")}
'''
        script += '''
if __name__ == "__main__":
    main()
'''
        return script


# ===========================================================================
# 6. Blender 过渡引擎
# ===========================================================================

class BlenderTransitionEngine:
    """Blender 过渡效果引擎

    支持摄像机、3D 对象、粒子、合成器和几何节点过渡。
    """

    def __init__(self) -> None:
        pass

    def create_camera_transition(
        self,
        cam_name: str,
        from_position: Tuple[float, float, float],
        to_position: Tuple[float, float, float],
        from_rotation: Tuple[float, float, float],
        to_rotation: Tuple[float, float, float],
        start_frame: int,
        duration_frames: int,
        easing: str = "BEZIER",
    ) -> str:
        """创建摄像机过渡动画

        Args:
            cam_name: 摄像机名称
            from_position: 起始位置 (x,y,z)
            to_position: 结束位置
            from_rotation: 起始旋转
            to_rotation: 结束旋转
            start_frame: 起始帧
            duration_frames: 持续帧数
            easing: 缓动类型

        Returns:
            Blender Python 脚本
        """
        end_frame = start_frame + duration_frames
        return f'''
# Camera Transition Animation
import bpy

cam = bpy.data.objects.get("{cam_name}")
if not cam:
    cam = bpy.data.objects.new("{cam_name}", bpy.data.cameras.new("Camera"))
    bpy.context.scene.collection.objects.link(cam)

# Position keyframes
cam.location = ({from_position[0]}, {from_position[1]}, {from_position[2]})
cam.keyframe_insert(data_path="location", frame={start_frame})
cam.location = ({to_position[0]}, {to_position[1]}, {to_position[2]})
cam.keyframe_insert(data_path="location", frame={end_frame})

# Rotation keyframes
cam.rotation_euler = ({from_rotation[0]}, {from_rotation[1]}, {from_rotation[2]})
cam.keyframe_insert(data_path="rotation_euler", frame={start_frame})
cam.rotation_euler = ({to_rotation[0]}, {to_rotation[1]}, {to_rotation[2]})
cam.keyframe_insert(data_path="rotation_euler", frame={end_frame})

# Set easing
for fcurve in cam.animation_data.action.fcurves:
    for keyframe in fcurve.keyframe_points:
        keyframe.interpolation = "{easing}"
'''

    def create_3d_object_transition(
        self,
        object_name: str,
        transition_type: str = "scale",
        start_frame: int = 1,
        duration_frames: int = 30,
    ) -> str:
        """创建基于 3D 对象的过渡

        Args:
            object_name: 对象名称
            transition_type: scale/rotate/translate/morph
            start_frame: 起始帧
            duration_frames: 持续帧数

        Returns:
            Blender Python 脚本
        """
        end_frame = start_frame + duration_frames
        trans_map = {
            "scale": f"""
    obj.scale = (0, 0, 0)
    obj.keyframe_insert(data_path="scale", frame={start_frame})
    obj.scale = (1, 1, 1)
    obj.keyframe_insert(data_path="scale", frame={end_frame})
""",
            "rotate": f"""
    obj.rotation_euler.z = 0
    obj.keyframe_insert(data_path="rotation_euler", frame={start_frame})
    obj.rotation_euler.z = 6.28319
    obj.keyframe_insert(data_path="rotation_euler", frame={end_frame})
""",
            "translate": f"""
    obj.location.y = 10
    obj.keyframe_insert(data_path="location", frame={start_frame})
    obj.location.y = 0
    obj.keyframe_insert(data_path="location", frame={end_frame})
""",
        }
        anim_code = trans_map.get(transition_type, trans_map["scale"])
        return f'''
# 3D Object Transition: {transition_type}
import bpy

obj = bpy.data.objects.get("{object_name}")
if obj:
{anim_code}
    # Set interpolation
    for fcurve in obj.animation_data.action.fcurves:
        for kf in fcurve.keyframe_points:
            kf.interpolation = "BEZIER"
            kf.easing = "EASE_IN_OUT"
'''

    def create_particle_transition(
        self,
        object_name: str,
        particle_count: int = 1000,
        start_frame: int = 1,
        duration_frames: int = 60,
    ) -> str:
        """创建粒子系统过渡"""
        return f'''
# Particle System Transition
import bpy

obj = bpy.data.objects.get("{object_name}")
if obj:
    # Add particle system
    ps = obj.modifiers.new(name="TransitionParticles", type="PARTICLE_SYSTEM")
    pset = ps.particle_system.settings
    pset.count = {particle_count}
    pset.frame_start = {start_frame}
    pset.frame_end = {start_frame + duration_frames // 2}
    pset.lifetime = {duration_frames}
    pset.render_type = "OBJECT"
    pset.emit_from = "FACE"
    pset.physics_type = "NEWTONIAN"
    pset.normal_factor = 2.0
    pset.factor_random = 0.5
'''

    def create_compositor_transition(
        self,
        transition_type: str = "crossfade",
        start_frame: int = 1,
        duration_frames: int = 30,
    ) -> str:
        """创建合成器节点过渡

        Args:
            transition_type: crossfade/wipe/glow
            start_frame: 起始帧
            duration_frames: 持续帧数
        """
        end_frame = start_frame + duration_frames
        return f'''
# Compositor Transition: {transition_type}
import bpy

# Enable nodes
bpy.context.scene.use_nodes = True
tree = bpy.context.scene.node_tree

# Clear default nodes
for node in tree.nodes:
    tree.nodes.remove(node)

# Create input and output
render_layers = tree.nodes.new(type="CompositorNodeRLayers")
composite = tree.nodes.new(type="CompositorNodeComposite")

# Mix node for transition
mix_node = tree.nodes.new(type="CompositorNodeMixRGB")
mix_node.blend_type = "MIX"

# Animate factor
mix_node.inputs[0].default_value = 0.0
mix_node.inputs[0].keyframe_insert(data_path="default_value", frame={start_frame})
mix_node.inputs[0].default_value = 1.0
mix_node.inputs[0].keyframe_insert(data_path="default_value", frame={end_frame})

# Connect nodes
tree.links.new(render_layers.outputs["Image"], mix_node.inputs[1])
tree.links.new(mix_node.outputs["Image"], composite.inputs["Image"])
'''

    def create_geometry_transition(
        self,
        object_name: str,
        transition_type: str = "procedural_dissolve",
    ) -> str:
        """创建几何节点过渡"""
        return f'''
# Geometry Nodes Transition: {transition_type}
import bpy

obj = bpy.data.objects.get("{object_name}")
if obj:
    # Add Geometry Nodes modifier
    gn = obj.modifiers.new(name="GeoTransition", type="NODES")
    node_group = bpy.data.node_groups.new("TransitionNodes", "GeometryNodeTree")

    # Create group inputs/outputs
    inp = node_group.nodes.new("NodeGroupInput")
    out = node_group.nodes.new("NodeGroupOutput")

    # Add geometry nodes for transition effect
    # (e.g., realize instances, scale, distribute points)
    pass
'''

    def generate_blender_script(self, operations: List[Dict[str, Any]]) -> str:
        """生成完整的 Blender Python 脚本"""
        script = '''
# ============================================================
# Blender Transition Script
# Generated by Transition Engine v2.0
# ============================================================

import bpy

def setup_transitions():
    # Ensure scene
    scene = bpy.context.scene

'''
        for op in operations:
            script += f"    # {op.get('type', 'transition')}\n"
        script += '''
if __name__ == "__main__":
    setup_transitions()
'''
        return script


# ===========================================================================
# 7. FFmpeg 过渡引擎
# ===========================================================================

class FFmpegTransitionEngine:
    """FFmpeg 过渡命令生成器

    使用 xfade 滤镜等生成 FFmpeg 命令行过渡效果。
    """

    XFADE_TRANSITIONS = [
        "fade", "fadeblack", "fadewhite",
        "wipeleft", "wiperight", "wipeup", "wipedown",
        "slideleft", "slideright", "slideup", "slidedown",
        "circlecrop", "rectcrop",
        "distance", "fadegrays",
        "radial", "hblur", "wipetl", "wipetr", "wipebl", "wipebr",
        "zoomin", "zoomout",
        "hlslice", "vrslice", "hrslice", "vlslice",
        "dissolve", "pixelize", "diagtl", "diagtr", "diagbl", "diagbr",
    ]

    def __init__(self) -> None:
        pass

    def create_crossfade_command(
        self,
        input1: str,
        input2: str,
        output: str,
        duration: float = 0.5,
        offset: float = 0.0,
        transition: str = "fade",
    ) -> str:
        """创建 xfade 交叉淡化命令

        Args:
            input1: 第一个输入文件路径
            input2: 第二个输入文件路径
            output: 输出文件路径
            duration: 过渡持续时间（秒）
            offset: 过渡开始时间偏移（秒）
            transition: 过渡类型

        Returns:
            FFmpeg 命令字符串
        """
        return (
            f'ffmpeg -i "{input1}" -i "{input2}" '
            f'-filter_complex '
            f'"[0:v][1:v]xfade=transition={transition}:duration={duration}:offset={offset}[v];'
            f'[0:a][1:a]acrossfade=d={duration}:c1=tri:c2=tri[a]" '
            f'-map "[v]" -map "[a]" -c:v libx264 -c:a aac "{output}"'
        )

    def create_wipe_command(
        self,
        input1: str,
        input2: str,
        output: str,
        wipe_type: str = "wipeleft",
        duration: float = 0.5,
        offset: float = 0.0,
    ) -> str:
        """创建擦除过渡命令

        Args:
            wipe_type: wipeleft/wiperight/wipeup/wipedown/wipetl/...
        """
        return self.create_crossfade_command(
            input1, input2, output, duration, offset, wipe_type
        )

    def create_dissolve_command(
        self,
        input1: str,
        input2: str,
        output: str,
        duration: float = 0.5,
        offset: float = 0.0,
    ) -> str:
        """创建溶解过渡命令"""
        return self.create_crossfade_command(
            input1, input2, output, duration, offset, "dissolve"
        )

    def create_glitch_transition_command(
        self,
        input1: str,
        input2: str,
        output: str,
        duration: float = 0.5,
        offset: float = 0.0,
    ) -> str:
        """创建故障效果过渡（RGB 分离 + 噪点）

        使用多个滤镜链实现 glitch 效果。
        """
        return (
            f'ffmpeg -i "{input1}" -i "{input2}" '
            f'-filter_complex "'
            f"[0:v]format=rgb24,split[r0][g0][b0];"
            f"[r0]lutrgb=g=0:b=0,geq=X+10*sin(PI*t*2):Y:r(X,Y)[r];"
            f"[g0]lutrgb=r=0:b=0[g];"
            f"[b0]lutrgb=r=0:g=0,geq=X-10*sin(PI*t*2):Y:b(X,Y)[b];"
            f"[r][g][b]mergeplanes=0x001020:yuv420p[glitch0];"
            f"[1:v]format=rgb24,split[r1][g1][b1];"
            f"[r1]lutrgb=g=0:b=0,geq=X-10*sin(PI*t*2):Y:r(X,Y)[r2];"
            f"[g1]lutrgb=r=0:b=0[g2];"
            f"[b1]lutrgb=r=0:g=0,geq=X+10*sin(PI*t*2):Y:b(X,Y)[b2];"
            f"[r2][g2][b2]mergeplanes=0x001020:yuv420p[glitch1];"
            f"[glitch0][glitch1]xfade=transition=dissolve:duration={duration}:offset={offset}[v];"
            f'[0:a][1:a]acrossfade=d={duration}[a]" '
            f'-map "[v]" -map "[a]" -c:v libx264 -c:a aac "{output}"'
        )

    def batch_transcode_with_transitions(
        self,
        input_files: List[str],
        output: str,
        transition_duration: float = 0.5,
        transition_type: str = "fade",
    ) -> str:
        """批量转码并应用过渡（多个视频片段串联）

        Args:
            input_files: 输入文件列表
            output: 输出文件
            transition_duration: 每个过渡的持续时间
            transition_type: 过渡类型

        Returns:
            完整的 FFmpeg 命令
        """
        if len(input_files) < 2:
            return f'ffmpeg -i "{input_files[0]}" "{output}"'

        inputs = " ".join([f'-i "{f}"' for f in input_files])

        filter_parts = []
        current = "0:v"
        total_offset = 0.0

        for i in range(1, len(input_files)):
            # Get duration approximation (would need ffprobe for real value)
            # Using placeholder offset calculation
            offset = max(0, total_offset - transition_duration / 2)
            next_v = f"v{i}"
            filter_parts.append(
                f"[{current}][{i}:v]xfade=transition={transition_type}:"
                f"duration={transition_duration}:offset={offset}[{next_v}]"
            )
            current = next_v
            total_offset += 10  # approximate clip duration

        # Audio crossfades
        audio_parts = []
        current_a = "0:a"
        for i in range(1, len(input_files)):
            next_a = f"a{i}"
            audio_parts.append(
                f"[{current_a}][{i}:a]acrossfade=d={transition_duration}[{next_a}]"
            )
            current_a = next_a

        filter_complex = ";".join(filter_parts + audio_parts)
        last_v = f"v{len(input_files)-1}"
        last_a = f"a{len(input_files)-1}"

        return (
            f'ffmpeg {inputs} '
            f'-filter_complex "{filter_complex}" '
            f'-map "[{last_v}]" -map "[{last_a}]" '
            f'-c:v libx264 -c:a aac "{output}"'
        )

    def generate_ffmpeg_command(
        self,
        config: Dict[str, Any],
    ) -> str:
        """根据配置生成 FFmpeg 命令

        Args:
            config: 配置字典，包含 inputs, output, transitions 等

        Returns:
            FFmpeg 命令字符串
        """
        transition_type = config.get("transition_type", "fade")
        duration = config.get("duration", 0.5)
        offset = config.get("offset", 0.0)
        inputs = config.get("inputs", [])
        output = config.get("output", "output.mp4")

        if len(inputs) == 2:
            return self.create_crossfade_command(
                inputs[0], inputs[1], output, duration, offset, transition_type
            )
        elif len(inputs) > 2:
            return self.batch_transcode_with_transitions(
                inputs, output, duration, transition_type
            )
        return f'ffmpeg -i "{inputs[0]}" "{output}"'


# ===========================================================================
# 8. 过渡预设库
# ===========================================================================

class PresetLibrary:
    """过渡预设库 - 100+ 内置预设

    预设按类别和风格组织，支持搜索、保存、加载和智能推荐。
    """

    def __init__(self) -> None:
        self._presets: Dict[str, TransitionPreset] = {}
        self._build_builtin_presets()

    def _build_builtin_presets(self) -> None:
        """构建 100+ 内置预设"""
        all_software = [
            SoftwareTarget.AFTER_EFFECTS,
            SoftwareTarget.PREMIERE_PRO,
            SoftwareTarget.DAVINCI_RESOLVE,
            SoftwareTarget.BLENDER,
            SoftwareTarget.FFMPEG,
        ]
        ae_only = [SoftwareTarget.AFTER_EFFECTS]
        ae_pr = [SoftwareTarget.AFTER_EFFECTS, SoftwareTarget.PREMIERE_PRO]
        ae_resolve_ffmpeg = [
            SoftwareTarget.AFTER_EFFECTS,
            SoftwareTarget.DAVINCI_RESOLVE,
            SoftwareTarget.FFMPEG,
        ]

        presets = [
            # ===== 基础溶解类 (Basic Dissolves) =====
            TransitionPreset(
                id="crossfade_standard",
                name="标准交叉淡化",
                category=TransitionCategory.DISSOLVE,
                style=TransitionStyle.SOFT,
                duration=0.5,
                software_support=all_software,
                params={"easing": "ease_in_out"},
                description="最基础的交叉淡化过渡，柔和自然",
                tags=["basic", "soft", "fade"],
            ),
            TransitionPreset(
                id="crossfade_quick",
                name="快速交叉淡化",
                category=TransitionCategory.DISSOLVE,
                style=TransitionStyle.MINIMAL,
                duration=0.15,
                software_support=all_software,
                params={"easing": "ease_out"},
                description="快速短暂的淡入淡出",
                tags=["basic", "fast", "minimal"],
            ),
            TransitionPreset(
                id="crossfade_slow",
                name="慢速交叉淡化",
                category=TransitionCategory.DISSOLVE,
                style=TransitionStyle.DREAMY,
                duration=2.0,
                software_support=all_software,
                params={"easing": "ease_in_out_sine"},
                description="缓慢柔和的长过渡",
                tags=["basic", "slow", "dreamy"],
            ),
            TransitionPreset(
                id="dip_to_black",
                name="闪黑过渡",
                category=TransitionCategory.DISSOLVE,
                style=TransitionStyle.CINEMATIC,
                duration=0.8,
                software_support=all_software,
                params={"color": [0, 0, 0], "color_type": "flash_black"},
                description="经典电影感闪黑",
                tags=["cinematic", "black", "fade"],
            ),
            TransitionPreset(
                id="dip_to_white",
                name="闪白过渡",
                category=TransitionCategory.DISSOLVE,
                style=TransitionStyle.DYNAMIC,
                duration=0.5,
                software_support=all_software,
                params={"color": [1, 1, 1], "color_type": "flash_white"},
                description="高亮闪白，常用于记忆/梦境转场",
                tags=["bright", "white", "flash"],
            ),
            TransitionPreset(
                id="film_dissolve",
                name="胶片溶解",
                category=TransitionCategory.DISSOLVE,
                style=TransitionStyle.RETRO,
                duration=1.0,
                software_support=ae_pr,
                params={"grain": True},
                description="带胶片颗粒感的溶解",
                tags=["retro", "film", "grain"],
            ),
            TransitionPreset(
                id="additive_dissolve",
                name="叠加溶解",
                category=TransitionCategory.DISSOLVE,
                style=TransitionStyle.GLOW_LIGHT if False else TransitionStyle.DYNAMIC,
                duration=0.6,
                software_support=ae_pr,
                params={"blend_mode": "add"},
                description="相加模式溶解，光感更强",
                tags=["additive", "bright", "glow"],
            ),
            TransitionPreset(
                id="non_additive_dissolve",
                name="非叠加溶解",
                category=TransitionCategory.DISSOLVE,
                style=TransitionStyle.MINIMAL,
                duration=0.5,
                software_support=ae_pr,
                params={"blend_mode": "normal"},
                description="亮度映射溶解",
                tags=["luma", "minimal"],
            ),

            # ===== 擦除类 (Wipes) =====
            TransitionPreset(
                id="wipe_linear_left",
                name="线性左擦除",
                category=TransitionCategory.WIPE,
                style=TransitionStyle.HARD,
                duration=0.5,
                software_support=ae_resolve_ffmpeg,
                params={"wipe_type": "linear", "angle": 270, "feather": 0},
                description="从右向左的线性擦除",
                tags=["wipe", "linear", "left"],
            ),
            TransitionPreset(
                id="wipe_linear_right",
                name="线性右擦除",
                category=TransitionCategory.WIPE,
                style=TransitionStyle.HARD,
                duration=0.5,
                software_support=ae_resolve_ffmpeg,
                params={"wipe_type": "linear", "angle": 90, "feather": 0},
                description="从左向右的线性擦除",
                tags=["wipe", "linear", "right"],
            ),
            TransitionPreset(
                id="wipe_soft_linear",
                name="柔和线性擦除",
                category=TransitionCategory.WIPE,
                style=TransitionStyle.SOFT,
                duration=0.6,
                software_support=ae_resolve_ffmpeg,
                params={"wipe_type": "linear", "angle": 90, "feather": 20},
                description="带羽化的柔和线性擦除",
                tags=["wipe", "soft", "feather"],
            ),
            TransitionPreset(
                id="wipe_radial_clockwise",
                name="顺时针径向擦除",
                category=TransitionCategory.WIPE,
                style=TransitionStyle.DYNAMIC,
                duration=0.7,
                software_support=ae_only,
                params={"wipe_type": "radial", "start_angle": 0, "direction": "clockwise"},
                description="顺时针扇形擦除",
                tags=["wipe", "radial", "clock"],
            ),
            TransitionPreset(
                id="wipe_radial_counter",
                name="逆时针径向擦除",
                category=TransitionCategory.WIPE,
                style=TransitionStyle.DYNAMIC,
                duration=0.7,
                software_support=ae_only,
                params={"wipe_type": "radial", "start_angle": 0, "direction": "counter"},
                description="逆时针扇形擦除",
                tags=["wipe", "radial"],
            ),
            TransitionPreset(
                id="wipe_venetian_blinds",
                name="百叶窗擦除",
                category=TransitionCategory.WIPE,
                style=TransitionStyle.RETRO,
                duration=0.8,
                software_support=ae_only,
                params={"wipe_type": "venetian", "width": 30, "direction": 0},
                description="经典百叶窗过渡效果",
                tags=["wipe", "retro", "venetian"],
            ),
            TransitionPreset(
                id="wipe_gradient_soft",
                name="渐变柔和擦除",
                category=TransitionCategory.WIPE,
                style=TransitionStyle.SOFT,
                duration=0.8,
                software_support=ae_only,
                params={"wipe_type": "gradient", "softness": 30},
                description="基于渐变的柔和擦除",
                tags=["wipe", "gradient", "soft"],
            ),
            TransitionPreset(
                id="wipe_iris_circle",
                name="圆形光圈擦除",
                category=TransitionCategory.WIPE,
                style=TransitionStyle.CINEMATIC,
                duration=0.6,
                software_support=ae_only,
                params={"wipe_type": "iris", "outer_radius": 200},
                description="圆形光圈展开/收合",
                tags=["wipe", "iris", "circle"],
            ),
            TransitionPreset(
                id="wipe_star",
                name="星形擦除",
                category=TransitionCategory.WIPE,
                style=TransitionStyle.DYNAMIC,
                duration=0.6,
                software_support=ae_only,
                params={"wipe_type": "star", "points": 5},
                description="星形展开擦除",
                tags=["wipe", "star", "shape"],
            ),
            TransitionPreset(
                id="wipe_diagonal",
                name="对角线擦除",
                category=TransitionCategory.WIPE,
                style=TransitionStyle.DYNAMIC,
                duration=0.5,
                software_support=ae_resolve_ffmpeg,
                params={"wipe_type": "linear", "angle": 45, "feather": 0},
                description="45度对角线擦除",
                tags=["wipe", "diagonal"],
            ),

            # ===== 滑动类 (Slides) =====
            TransitionPreset(
                id="slide_push_left",
                name="左推过渡",
                category=TransitionCategory.SLIDE,
                style=TransitionStyle.DYNAMIC,
                duration=0.5,
                software_support=ae_only,
                params={"slide_type": "push", "direction": "left"},
                description="画面向左推出",
                tags=["slide", "push", "left"],
            ),
            TransitionPreset(
                id="slide_push_right",
                name="右推过渡",
                category=TransitionCategory.SLIDE,
                style=TransitionStyle.DYNAMIC,
                duration=0.5,
                software_support=ae_only,
                params={"slide_type": "push", "direction": "right"},
                description="画面向右推出",
                tags=["slide", "push", "right"],
            ),
            TransitionPreset(
                id="slide_push_up",
                name="上推过渡",
                category=TransitionCategory.SLIDE,
                style=TransitionStyle.DYNAMIC,
                duration=0.5,
                software_support=ae_only,
                params={"slide_type": "push", "direction": "up"},
                description="画面向上推出",
                tags=["slide", "push", "up"],
            ),
            TransitionPreset(
                id="slide_push_down",
                name="下推过渡",
                category=TransitionCategory.SLIDE,
                style=TransitionStyle.DYNAMIC,
                duration=0.5,
                software_support=ae_only,
                params={"slide_type": "push", "direction": "down"},
                description="画面向下推出",
                tags=["slide", "push", "down"],
            ),
            TransitionPreset(
                id="slide_in_left",
                name="左滑入",
                category=TransitionCategory.SLIDE,
                style=TransitionStyle.DYNAMIC,
                duration=0.4,
                software_support=ae_only,
                params={"slide_type": "slide", "direction": "left"},
                description="新画面从左侧滑入",
                tags=["slide", "in", "left"],
            ),
            TransitionPreset(
                id="slide_in_right",
                name="右滑入",
                category=TransitionCategory.SLIDE,
                style=TransitionStyle.DYNAMIC,
                duration=0.4,
                software_support=ae_only,
                params={"slide_type": "slide", "direction": "right"},
                description="新画面从右侧滑入",
                tags=["slide", "in", "right"],
            ),
            TransitionPreset(
                id="slide_split_center",
                name="中心分裂",
                category=TransitionCategory.SLIDE,
                style=TransitionStyle.DYNAMIC,
                duration=0.6,
                software_support=ae_only,
                params={"slide_type": "split", "direction": "horizontal"},
                description="从中心向两侧分裂",
                tags=["slide", "split", "center"],
            ),
            TransitionPreset(
                id="slide_swap",
                name="交换滑动",
                category=TransitionCategory.SLIDE,
                style=TransitionStyle.DYNAMIC,
                duration=0.6,
                software_support=ae_only,
                params={"slide_type": "swap"},
                description="两个画面交错交换位置",
                tags=["slide", "swap"],
            ),
            TransitionPreset(
                id="slide_rotate",
                name="旋转滑动",
                category=TransitionCategory.SLIDE,
                style=TransitionStyle.DYNAMIC,
                duration=0.5,
                software_support=ae_only,
                params={"slide_type": "rotate", "rotation_amount": 90},
                description="旋转进入的滑动过渡",
                tags=["slide", "rotate"],
            ),

            # ===== 缩放类 (Zoom) =====
            TransitionPreset(
                id="zoom_standard",
                name="标准缩放过渡",
                category=TransitionCategory.ZOOM,
                style=TransitionStyle.ENERGETIC,
                duration=0.4,
                software_support=ae_only,
                params={"zoom_amount": 150, "blur_amount": 20},
                description="经典缩放推进过渡",
                tags=["zoom", "energetic"],
            ),
            TransitionPreset(
                id="zoom_subtle",
                name="微妙缩放",
                category=TransitionCategory.ZOOM,
                style=TransitionStyle.MINIMAL,
                duration=0.6,
                software_support=ae_only,
                params={"zoom_amount": 115, "blur_amount": 5},
                description="轻微的推近效果",
                tags=["zoom", "subtle", "minimal"],
            ),
            TransitionPreset(
                id="zoom_dramatic",
                name="戏剧化缩放",
                category=TransitionCategory.ZOOM,
                style=TransitionStyle.CINEMATIC,
                duration=0.8,
                software_support=ae_only,
                params={"zoom_amount": 200, "blur_amount": 50},
                description="大幅缩放，强烈视觉冲击",
                tags=["zoom", "dramatic", "cinematic"],
            ),
            TransitionPreset(
                id="zoom_blur_in",
                name="缩放模糊入",
                category=TransitionCategory.ZOOM,
                style=TransitionStyle.ENERGETIC,
                duration=0.3,
                software_support=ae_only,
                params={"zoom_amount": 130, "blur_amount": 40, "direction": "in"},
                description="从模糊到清晰的缩放",
                tags=["zoom", "blur", "in"],
            ),
            TransitionPreset(
                id="zoom_blur_out",
                name="缩放模糊出",
                category=TransitionCategory.ZOOM,
                style=TransitionStyle.ENERGETIC,
                duration=0.3,
                software_support=ae_only,
                params={"zoom_amount": 130, "blur_amount": 40, "direction": "out"},
                description="从清晰到模糊的缩放",
                tags=["zoom", "blur", "out"],
            ),
            TransitionPreset(
                id="zoom_ken_burns",
                name="Ken Burns 缩放",
                category=TransitionCategory.ZOOM,
                style=TransitionStyle.CINEMATIC,
                duration=1.5,
                software_support=ae_only,
                params={"zoom_amount": 110, "pan_amount": 50, "blur_amount": 0},
                description="缓慢推近+平移的电影感效果",
                tags=["zoom", "kenburns", "cinematic"],
            ),

            # ===== 3D 过渡类 =====
            TransitionPreset(
                id="3d_cube_flip_x",
                name="立方体翻转X轴",
                category=TransitionCategory.THREE_D,
                style=TransitionStyle.DYNAMIC,
                duration=0.8,
                software_support=ae_only,
                params={"type": "cube_flip", "axis": "x", "rotation": -90},
                description="3D立方体X轴翻转",
                tags=["3d", "cube", "flip"],
            ),
            TransitionPreset(
                id="3d_cube_flip_y",
                name="立方体翻转Y轴",
                category=TransitionCategory.THREE_D,
                style=TransitionStyle.DYNAMIC,
                duration=0.8,
                software_support=ae_only,
                params={"type": "cube_flip", "axis": "y", "rotation": -90},
                description="3D立方体Y轴翻转",
                tags=["3d", "cube", "flip"],
            ),
            TransitionPreset(
                id="3d_page_turn",
                name="翻页效果",
                category=TransitionCategory.THREE_D,
                style=TransitionStyle.CINEMATIC,
                duration=1.0,
                software_support=ae_only,
                params={"type": "page_turn", "light_dir": 135},
                description="书页翻转效果",
                tags=["3d", "page", "turn"],
            ),
            TransitionPreset(
                id="3d_door_open",
                name="开门效果",
                category=TransitionCategory.THREE_D,
                style=TransitionStyle.CINEMATIC,
                duration=0.7,
                software_support=ae_only,
                params={"type": "door", "rotation": -90},
                description="3D门打开效果",
                tags=["3d", "door"],
            ),
            TransitionPreset(
                id="3d_card_wipe",
                name="卡片翻转",
                category=TransitionCategory.THREE_D,
                style=TransitionStyle.DYNAMIC,
                duration=0.8,
                software_support=ae_only,
                params={"type": "card_wipe", "rows": 5, "columns": 5, "flip_dir": 0},
                description="多卡片翻转过渡",
                tags=["3d", "card", "wipe"],
            ),

            # ===== 光效类 =====
            TransitionPreset(
                id="glow_light_leak",
                name="漏光过渡",
                category=TransitionCategory.GLOW_LIGHT,
                style=TransitionStyle.DREAMY,
                duration=0.6,
                software_support=ae_only,
                params={"type": "light_leak", "intensity": 80},
                description="暖色调漏光效果",
                tags=["glow", "light", "leak"],
            ),
            TransitionPreset(
                id="glow_optical_flare",
                name="光学耀斑",
                category=TransitionCategory.GLOW_LIGHT,
                style=TransitionStyle.CINEMATIC,
                duration=0.5,
                software_support=ae_only,
                params={"type": "optical_flare", "brightness": 200, "lens_type": 2},
                description="镜头耀斑过渡",
                tags=["glow", "flare", "lens"],
            ),
            TransitionPreset(
                id="glow_lens_flare",
                name="镜头光晕",
                category=TransitionCategory.GLOW_LIGHT,
                style=TransitionStyle.CINEMATIC,
                duration=0.7,
                software_support=ae_only,
                params={"type": "lens_flare", "brightness": 150},
                description="经典镜头光晕",
                tags=["glow", "lens", "flare"],
            ),

            # ===== 粒子类 =====
            TransitionPreset(
                id="particle_dissolve_shatter",
                name="碎裂溶解",
                category=TransitionCategory.PARTICLE,
                style=TransitionStyle.DYNAMIC,
                duration=0.8,
                software_support=ae_only,
                params={"type": "particle_dissolve", "pattern": 2, "repetitions": 50},
                description="画面碎裂消散效果",
                tags=["particle", "shatter", "dissolve"],
            ),
            TransitionPreset(
                id="particle_pixel_polly",
                name="像素飞溅",
                category=TransitionCategory.PARTICLE,
                style=TransitionStyle.ENERGETIC,
                duration=0.6,
                software_support=ae_only,
                params={"type": "pixel_polly", "force": 300, "gravity": 50, "spinning": 100},
                description="像素颗粒飞溅效果",
                tags=["particle", "pixel", "scatter"],
            ),
            TransitionPreset(
                id="particle_card_dance",
                name="卡片飞舞",
                category=TransitionCategory.PARTICLE,
                style=TransitionStyle.DYNAMIC,
                duration=1.0,
                software_support=ae_only,
                params={"type": "card_dance", "rows": 8, "columns": 8},
                description="卡片式飞舞过渡",
                tags=["particle", "card", "dance"],
            ),

            # ===== 扭曲类 =====
            TransitionPreset(
                id="distort_displacement",
                name="位移扭曲",
                category=TransitionCategory.DISTORT,
                style=TransitionStyle.DYNAMIC,
                duration=0.6,
                software_support=ae_only,
                params={"type": "displacement_map", "max_disp": 100, "noise_scale": 100},
                description="噪波位移扭曲效果",
                tags=["distort", "displacement"],
            ),
            TransitionPreset(
                id="distort_turbulent",
                name="湍流扭曲",
                category=TransitionCategory.DISTORT,
                style=TransitionStyle.DREAMY,
                duration=0.7,
                software_support=ae_only,
                params={"type": "turbulent_displace", "amount": 50, "size": 50, "complexity": 5},
                description="湍流扰动扭曲",
                tags=["distort", "turbulent", "dreamy"],
            ),
            TransitionPreset(
                id="distort_warp",
                name="网格扭曲",
                category=TransitionCategory.DISTORT,
                style=TransitionStyle.DYNAMIC,
                duration=0.8,
                software_support=ae_only,
                params={"type": "warp", "rows": 7, "columns": 7, "quality": 10},
                description="网格变形扭曲",
                tags=["distort", "warp", "mesh"],
            ),

            # ===== 故障类 =====
            TransitionPreset(
                id="glitch_rgb_split",
                name="RGB分离",
                category=TransitionCategory.GLITCH,
                style=TransitionStyle.GLITCHY,
                duration=0.3,
                software_support=ae_only,
                params={"type": "rgb_split", "offset": 20},
                description="RGB通道分离故障效果",
                tags=["glitch", "rgb", "split"],
            ),
            TransitionPreset(
                id="glitch_digital_noise",
                name="数字噪点",
                category=TransitionCategory.GLITCH,
                style=TransitionStyle.GLITCHY,
                duration=0.4,
                software_support=ae_only,
                params={"type": "digital_noise", "intensity": 60, "noise_amount": 100, "fps": 8},
                description="数字噪点故障效果",
                tags=["glitch", "noise", "digital"],
            ),
            TransitionPreset(
                id="glitch_vhs",
                name="VHS故障",
                category=TransitionCategory.GLITCH,
                style=TransitionStyle.RETRO,
                duration=0.5,
                software_support=ae_only,
                params={"type": "vhs", "color_shift": 10, "noise": 20},
                description="复古VHS磁带故障",
                tags=["glitch", "vhs", "retro"],
            ),

            # ===== 形状类 =====
            TransitionPreset(
                id="shape_circle_reveal",
                name="圆形揭示",
                category=TransitionCategory.SHAPE,
                style=TransitionStyle.CINEMATIC,
                duration=0.6,
                software_support=ae_only,
                params={"type": "circle", "feather": 20},
                description="圆形遮罩揭示过渡",
                tags=["shape", "circle", "reveal"],
            ),
            TransitionPreset(
                id="shape_diamond_reveal",
                name="菱形揭示",
                category=TransitionCategory.SHAPE,
                style=TransitionStyle.DYNAMIC,
                duration=0.5,
                software_support=ae_only,
                params={"type": "diamond", "feather": 15},
                description="菱形遮罩揭示",
                tags=["shape", "diamond"],
            ),
            TransitionPreset(
                id="shape_heart_reveal",
                name="心形揭示",
                category=TransitionCategory.SHAPE,
                style=TransitionStyle.DREAMY,
                duration=0.7,
                software_support=ae_only,
                params={"type": "heart", "feather": 10},
                description="心形遮罩揭示",
                tags=["shape", "heart", "romantic"],
            ),

            # ===== 文字过渡类 =====
            TransitionPreset(
                id="text_typewriter",
                name="打字机效果",
                category=TransitionCategory.TEXT_TRANSITION,
                style=TransitionStyle.MINIMAL,
                duration=0.8,
                software_support=ae_only,
                params={"type": "typewriter_reveal", "steps": 20},
                description="逐字打字机显示效果",
                tags=["text", "typewriter"],
            ),
            TransitionPreset(
                id="text_wipe_reveal",
                name="文字擦除",
                category=TransitionCategory.TEXT_TRANSITION,
                style=TransitionStyle.MINIMAL,
                duration=0.5,
                software_support=ae_only,
                params={"type": "text_wipe", "angle": 270, "feather": 2},
                description="文字擦除显示效果",
                tags=["text", "wipe"],
            ),

            # ===== 颜色过渡类 =====
            TransitionPreset(
                id="color_flash_white",
                name="白光闪",
                category=TransitionCategory.COLOR,
                style=TransitionStyle.DYNAMIC,
                duration=0.3,
                software_support=all_software,
                params={"color_type": "flash_white", "color": [1, 1, 1], "intensity": 100},
                description="白色闪光过渡",
                tags=["color", "flash", "white"],
            ),
            TransitionPreset(
                id="color_flash_black",
                name="黑光闪",
                category=TransitionCategory.COLOR,
                style=TransitionStyle.CINEMATIC,
                duration=0.5,
                software_support=all_software,
                params={"color_type": "flash_black", "color": [0, 0, 0], "intensity": 100},
                description="黑色闪场过渡",
                tags=["color", "flash", "black"],
            ),

            # ===== 运动模糊类 =====
            TransitionPreset(
                id="motion_blur_horizontal",
                name="水平运动模糊",
                category=TransitionCategory.MOTION_BLUR,
                style=TransitionStyle.ENERGETIC,
                duration=0.3,
                software_support=ae_only,
                params={"blur_amount": 100, "direction": 0},
                description="水平方向运动模糊",
                tags=["motion", "blur", "horizontal"],
            ),
            TransitionPreset(
                id="motion_blur_vertical",
                name="垂直运动模糊",
                category=TransitionCategory.MOTION_BLUR,
                style=TransitionStyle.ENERGETIC,
                duration=0.3,
                software_support=ae_only,
                params={"blur_amount": 100, "direction": 90},
                description="垂直方向运动模糊",
                tags=["motion", "blur", "vertical"],
            ),
            TransitionPreset(
                id="motion_blur_diagonal",
                name="对角运动模糊",
                category=TransitionCategory.MOTION_BLUR,
                style=TransitionStyle.ENERGETIC,
                duration=0.35,
                software_support=ae_only,
                params={"blur_amount": 80, "direction": 45},
                description="对角线方向运动模糊",
                tags=["motion", "blur", "diagonal"],
            ),
            TransitionPreset(
                id="motion_blur_zoom",
                name="变焦运动模糊",
                category=TransitionCategory.MOTION_BLUR,
                style=TransitionStyle.DYNAMIC,
                duration=0.4,
                software_support=ae_only,
                params={"blur_amount": 60, "type": "zoom"},
                description="中心放射状运动模糊",
                tags=["motion", "blur", "zoom"],
            ),
            TransitionPreset(
                id="motion_blur_rotate",
                name="旋转运动模糊",
                category=TransitionCategory.MOTION_BLUR,
                style=TransitionStyle.DYNAMIC,
                duration=0.5,
                software_support=ae_only,
                params={"blur_amount": 50, "type": "rotate"},
                description="旋转式运动模糊",
                tags=["motion", "blur", "rotate"],
            ),

            # ===== 更多溶解类 =====
            TransitionPreset(
                id="dissolve_block",
                name="块状溶解",
                category=TransitionCategory.DISSOLVE,
                style=TransitionStyle.HARD,
                duration=0.6,
                software_support=ae_only,
                params={"pattern": "block", "block_size": 20},
                description="方块状溶解效果",
                tags=["dissolve", "block", "hard"],
            ),
            TransitionPreset(
                id="dissolve_random_lines",
                name="随机线条溶解",
                category=TransitionCategory.DISSOLVE,
                style=TransitionStyle.DYNAMIC,
                duration=0.5,
                software_support=ae_only,
                params={"pattern": "random_lines"},
                description="随机线条状溶解",
                tags=["dissolve", "lines", "random"],
            ),
            TransitionPreset(
                id="dissolve_gradient",
                name="渐变溶解",
                category=TransitionCategory.DISSOLVE,
                style=TransitionStyle.SOFT,
                duration=0.8,
                software_support=ae_only,
                params={"pattern": "gradient"},
                description="基于渐变的柔和溶解",
                tags=["dissolve", "gradient", "soft"],
            ),

            # ===== 更多擦除类 =====
            TransitionPreset(
                id="wipe_diagonal_down",
                name="对角下擦除",
                category=TransitionCategory.WIPE,
                style=TransitionStyle.HARD,
                duration=0.5,
                software_support=ae_resolve_ffmpeg,
                params={"wipe_type": "linear", "angle": 45, "feather": 0},
                description="左上到右下的对角擦除",
                tags=["wipe", "diagonal", "hard"],
            ),
            TransitionPreset(
                id="wipe_diagonal_up",
                name="对角上擦除",
                category=TransitionCategory.WIPE,
                style=TransitionStyle.HARD,
                duration=0.5,
                software_support=ae_resolve_ffmpeg,
                params={"wipe_type": "linear", "angle": 135, "feather": 0},
                description="左下到右上的对角擦除",
                tags=["wipe", "diagonal"],
            ),
            TransitionPreset(
                id="wipe_pinwheel",
                name="风车擦除",
                category=TransitionCategory.WIPE,
                style=TransitionStyle.DYNAMIC,
                duration=0.8,
                software_support=ae_only,
                params={"wipe_type": "pinwheel", "blades": 6},
                description="风车旋转式擦除",
                tags=["wipe", "pinwheel", "rotate"],
            ),
            TransitionPreset(
                id="wipe_spiral",
                name="螺旋擦除",
                category=TransitionCategory.WIPE,
                style=TransitionStyle.DYNAMIC,
                duration=1.0,
                software_support=ae_only,
                params={"wipe_type": "spiral"},
                description="螺旋展开式擦除",
                tags=["wipe", "spiral"],
            ),
            TransitionPreset(
                id="wipe_checkerboard",
                name="棋盘擦除",
                category=TransitionCategory.WIPE,
                style=TransitionStyle.RETRO,
                duration=0.7,
                software_support=ae_only,
                params={"wipe_type": "checkerboard", "rows": 8, "cols": 8},
                description="棋盘格交错擦除",
                tags=["wipe", "checkerboard", "retro"],
            ),
            TransitionPreset(
                id="wipe_zigzag",
                name="锯齿擦除",
                category=TransitionCategory.WIPE,
                style=TransitionStyle.DYNAMIC,
                duration=0.6,
                software_support=ae_only,
                params={"wipe_type": "zigzag", "edges": 10},
                description="锯齿形边缘擦除",
                tags=["wipe", "zigzag", "edge"],
            ),

            # ===== 更多滑动类 =====
            TransitionPreset(
                id="slide_push_up",
                name="上推滑动",
                category=TransitionCategory.SLIDE,
                style=TransitionStyle.DYNAMIC,
                duration=0.5,
                software_support=ae_only,
                params={"slide_type": "push", "direction": "up"},
                description="画面向上推出",
                tags=["slide", "push", "up"],
            ),
            TransitionPreset(
                id="slide_in_top",
                name="上滑入",
                category=TransitionCategory.SLIDE,
                style=TransitionStyle.DYNAMIC,
                duration=0.4,
                software_support=ae_only,
                params={"slide_type": "slide", "direction": "up"},
                description="新画面从顶部滑入",
                tags=["slide", "in", "top"],
            ),
            TransitionPreset(
                id="slide_in_bottom",
                name="下滑入",
                category=TransitionCategory.SLIDE,
                style=TransitionStyle.DYNAMIC,
                duration=0.4,
                software_support=ae_only,
                params={"slide_type": "slide", "direction": "down"},
                description="新画面从底部滑入",
                tags=["slide", "in", "bottom"],
            ),
            TransitionPreset(
                id="slide_stretch",
                name="拉伸滑动",
                category=TransitionCategory.SLIDE,
                style=TransitionStyle.DYNAMIC,
                duration=0.5,
                software_support=ae_only,
                params={"slide_type": "stretch", "direction": "left"},
                description="带拉伸变形的滑动",
                tags=["slide", "stretch", "distort"],
            ),
            TransitionPreset(
                id="slide_bounce",
                name="弹跳滑入",
                category=TransitionCategory.SLIDE,
                style=TransitionStyle.ENERGETIC,
                duration=0.6,
                software_support=ae_only,
                params={"slide_type": "bounce", "direction": "right"},
                description="带弹跳效果的滑入",
                tags=["slide", "bounce", "energetic"],
            ),

            # ===== 更多缩放类 =====
            TransitionPreset(
                id="zoom_zoom_out",
                name="拉远过渡",
                category=TransitionCategory.ZOOM,
                style=TransitionStyle.CINEMATIC,
                duration=0.6,
                software_support=ae_only,
                params={"zoom_amount": 70, "blur_amount": 15, "direction": "out"},
                description="从近到远的拉远过渡",
                tags=["zoom", "out", "cinematic"],
            ),
            TransitionPreset(
                id="zoom_whip_pan",
                name="甩镜缩放",
                category=TransitionCategory.ZOOM,
                style=TransitionStyle.ENERGETIC,
                duration=0.25,
                software_support=ae_only,
                params={"zoom_amount": 120, "pan_amount": 200, "blur_amount": 60},
                description="快速甩镜+缩放的动感过渡",
                tags=["zoom", "whip", "energetic"],
            ),
            TransitionPreset(
                id="zoom_dolly",
                name="推轨过渡",
                category=TransitionCategory.ZOOM,
                style=TransitionStyle.CINEMATIC,
                duration=1.2,
                software_support=ae_only,
                params={"zoom_amount": 130, "blur_amount": 0, "easing": "ease_in_out"},
                description="缓慢推轨式过渡",
                tags=["zoom", "dolly", "smooth"],
            ),

            # ===== 更多 3D 类 =====
            TransitionPreset(
                id="3d_flip_horizontal",
                name="水平翻转",
                category=TransitionCategory.THREE_D,
                style=TransitionStyle.DYNAMIC,
                duration=0.6,
                software_support=ae_only,
                params={"type": "flip", "axis": "y"},
                description="水平翻转过渡",
                tags=["3d", "flip", "horizontal"],
            ),
            TransitionPreset(
                id="3d_flip_vertical",
                name="垂直翻转",
                category=TransitionCategory.THREE_D,
                style=TransitionStyle.DYNAMIC,
                duration=0.6,
                software_support=ae_only,
                params={"type": "flip", "axis": "x"},
                description="垂直翻转过渡",
                tags=["3d", "flip", "vertical"],
            ),
            TransitionPreset(
                id="3d_sphere",
                name="球面过渡",
                category=TransitionCategory.THREE_D,
                style=TransitionStyle.FUTURISTIC,
                duration=0.9,
                software_support=ae_only,
                params={"type": "sphere"},
                description="球面扭曲3D过渡",
                tags=["3d", "sphere", "futuristic"],
            ),
            TransitionPreset(
                id="3d_twist",
                name="扭曲翻转",
                category=TransitionCategory.THREE_D,
                style=TransitionStyle.DYNAMIC,
                duration=0.8,
                software_support=ae_only,
                params={"type": "twist", "twist_amount": 180},
                description="带扭曲的3D翻转",
                tags=["3d", "twist", "distort"],
            ),

            # ===== 更多光效类 =====
            TransitionPreset(
                id="glow_flash",
                name="闪光过渡",
                category=TransitionCategory.GLOW_LIGHT,
                style=TransitionStyle.DYNAMIC,
                duration=0.3,
                software_support=ae_only,
                params={"type": "flash", "intensity": 200},
                description="瞬间强光闪白过渡",
                tags=["glow", "flash", "bright"],
            ),
            TransitionPreset(
                id="glow_gradient_wipe",
                name="渐变光擦",
                category=TransitionCategory.GLOW_LIGHT,
                style=TransitionStyle.CINEMATIC,
                duration=0.6,
                software_support=ae_only,
                params={"type": "gradient_wipe", "intensity": 100},
                description="带光晕的渐变擦除",
                tags=["glow", "gradient", "wipe"],
            ),
            TransitionPreset(
                id="glow_bloom",
                name="辉光扩散",
                category=TransitionCategory.GLOW_LIGHT,
                style=TransitionStyle.DREAMY,
                duration=0.7,
                software_support=ae_only,
                params={"type": "bloom", "threshold": 50, "radius": 30},
                description="辉光扩散式过渡",
                tags=["glow", "bloom", "dreamy"],
            ),

            # ===== 更多粒子类 =====
            TransitionPreset(
                id="particle_sand",
                name="沙粒飘散",
                category=TransitionCategory.PARTICLE,
                style=TransitionStyle.DREAMY,
                duration=1.0,
                software_support=ae_only,
                params={"type": "sand", "gravity": 30},
                description="沙粒般飘散溶解",
                tags=["particle", "sand", "dreamy"],
            ),
            TransitionPreset(
                id="particle_smoke",
                name="烟雾消散",
                category=TransitionCategory.PARTICLE,
                style=TransitionStyle.DREAMY,
                duration=1.2,
                software_support=ae_only,
                params={"type": "smoke", "turbulence": 50},
                description="烟雾般消散过渡",
                tags=["particle", "smoke", "soft"],
            ),
            TransitionPreset(
                id="particle_sparkle",
                name="粒子闪光",
                category=TransitionCategory.PARTICLE,
                style=TransitionStyle.ENERGETIC,
                duration=0.6,
                software_support=ae_only,
                params={"type": "sparkle", "count": 200},
                description="闪烁粒子过渡",
                tags=["particle", "sparkle", "glitter"],
            ),

            # ===== 更多扭曲类 =====
            TransitionPreset(
                id="distort_ripple",
                name="涟漪扭曲",
                category=TransitionCategory.DISTORT,
                style=TransitionStyle.DREAMY,
                duration=0.7,
                software_support=ae_only,
                params={"type": "ripple", "amplitude": 30, "frequency": 5},
                description="水波纹扭曲效果",
                tags=["distort", "ripple", "water"],
            ),
            TransitionPreset(
                id="distort_mirror",
                name="镜像扭曲",
                category=TransitionCategory.DISTORT,
                style=TransitionStyle.FUTURISTIC,
                duration=0.6,
                software_support=ae_only,
                params={"type": "mirror"},
                description="镜像分裂扭曲",
                tags=["distort", "mirror", "split"],
            ),
            TransitionPreset(
                id="distort_liquid",
                name="液态扭曲",
                category=TransitionCategory.DISTORT,
                style=TransitionStyle.DREAMY,
                duration=0.9,
                software_support=ae_only,
                params={"type": "liquid", "amount": 40},
                description="液态流动扭曲效果",
                tags=["distort", "liquid", "fluid"],
            ),

            # ===== 更多故障类 =====
            TransitionPreset(
                id="glitch_screen_tear",
                name="画面撕裂",
                category=TransitionCategory.GLITCH,
                style=TransitionStyle.GLITCHY,
                duration=0.4,
                software_support=ae_only,
                params={"type": "screen_tear", "tears": 5},
                description="屏幕撕裂故障效果",
                tags=["glitch", "tear", "screen"],
            ),
            TransitionPreset(
                id="glitch_color_shift",
                name="色彩偏移",
                category=TransitionCategory.GLITCH,
                style=TransitionStyle.GLITCHY,
                duration=0.35,
                software_support=ae_only,
                params={"type": "color_shift", "hue_shift": 30},
                description="色相偏移故障效果",
                tags=["glitch", "color", "hue"],
            ),
            TransitionPreset(
                id="glitch_data_mosh",
                name="数据损坏",
                category=TransitionCategory.GLITCH,
                style=TransitionStyle.GLITCHY,
                duration=0.5,
                software_support=ae_only,
                params={"type": "data_mosh", "intensity": 70},
                description="数据损坏式故障效果",
                tags=["glitch", "data", "corrupt"],
            ),

            # ===== 更多形状类 =====
            TransitionPreset(
                id="shape_square_reveal",
                name="方形揭示",
                category=TransitionCategory.SHAPE,
                style=TransitionStyle.MINIMAL,
                duration=0.5,
                software_support=ae_only,
                params={"type": "square", "feather": 10},
                description="方形遮罩揭示过渡",
                tags=["shape", "square", "minimal"],
            ),
            TransitionPreset(
                id="shape_star_reveal",
                name="星形揭示",
                category=TransitionCategory.SHAPE,
                style=TransitionStyle.DYNAMIC,
                duration=0.6,
                software_support=ae_only,
                params={"type": "star", "points": 5, "feather": 5},
                description="星形遮罩揭示",
                tags=["shape", "star"],
            ),
            TransitionPreset(
                id="shape_polygon_reveal",
                name="多边形揭示",
                category=TransitionCategory.SHAPE,
                style=TransitionStyle.FUTURISTIC,
                duration=0.6,
                software_support=ae_only,
                params={"type": "polygon", "sides": 6, "feather": 8},
                description="六边形遮罩揭示",
                tags=["shape", "polygon", "hexagon"],
            ),
            TransitionPreset(
                id="shape_ink_drop",
                name="墨滴扩散",
                category=TransitionCategory.SHAPE,
                style=TransitionStyle.DREAMY,
                duration=1.0,
                software_support=ae_only,
                params={"type": "ink_drop"},
                description="墨水滴落扩散效果",
                tags=["shape", "ink", "drop"],
            ),

            # ===== 更多文字过渡类 =====
            TransitionPreset(
                id="text_fade_char",
                name="逐字淡入",
                category=TransitionCategory.TEXT_TRANSITION,
                style=TransitionStyle.SOFT,
                duration=0.8,
                software_support=ae_only,
                params={"type": "fade_character", "order": "left_to_right"},
                description="逐字符淡入显示",
                tags=["text", "fade", "character"],
            ),
            TransitionPreset(
                id="text_scale_pop",
                name="文字弹跳",
                category=TransitionCategory.TEXT_TRANSITION,
                style=TransitionStyle.ENERGETIC,
                duration=0.6,
                software_support=ae_only,
                params={"type": "scale_pop"},
                description="弹跳式文字出现",
                tags=["text", "scale", "bounce"],
            ),
            TransitionPreset(
                id="text_blur_reveal",
                name="模糊显字",
                category=TransitionCategory.TEXT_TRANSITION,
                style=TransitionStyle.DREAMY,
                duration=0.7,
                software_support=ae_only,
                params={"type": "blur_reveal", "blur_amount": 30},
                description="从模糊到清晰的文字出现",
                tags=["text", "blur", "reveal"],
            ),

            # ===== 更多颜色类 =====
            TransitionPreset(
                id="color_gradient_flash",
                name="渐变闪色",
                category=TransitionCategory.COLOR,
                style=TransitionStyle.DYNAMIC,
                duration=0.4,
                software_support=ae_only,
                params={"color_type": "gradient_flash"},
                description="渐变色闪光过渡",
                tags=["color", "gradient", "flash"],
            ),
            TransitionPreset(
                id="color_hue_shift",
                name="色相转换",
                category=TransitionCategory.COLOR,
                style=TransitionStyle.DREAMY,
                duration=0.8,
                software_support=ae_only,
                params={"color_type": "hue_shift", "shift_amount": 180},
                description="色相偏移式过渡",
                tags=["color", "hue", "shift"],
            ),
            TransitionPreset(
                id="color_monochrome",
                name="黑白转场",
                category=TransitionCategory.COLOR,
                style=TransitionStyle.CINEMATIC,
                duration=0.6,
                software_support=ae_only,
                params={"color_type": "monochrome"},
                description="先变黑白再恢复的过渡",
                tags=["color", "monochrome", "b&w"],
            ),
            TransitionPreset(
                id="color_invert",
                name="反色过渡",
                category=TransitionCategory.COLOR,
                style=TransitionStyle.GLITCHY,
                duration=0.4,
                software_support=ae_only,
                params={"color_type": "invert"},
                description="颜色反相过渡效果",
                tags=["color", "invert", "glitch"],
            ),

            # ===== 更多现代/创意类 =====
            TransitionPreset(
                id="modern_sliced",
                name="切片过渡",
                category=TransitionCategory.DISTORT,
                style=TransitionStyle.FUTURISTIC,
                duration=0.5,
                software_support=ae_only,
                params={"type": "sliced", "slices": 10},
                description="水平切片交错过渡",
                tags=["modern", "sliced", "futuristic"],
            ),
            TransitionPreset(
                id="modern_glitch_stutter",
                name="卡顿故障",
                category=TransitionCategory.GLITCH,
                style=TransitionStyle.ENERGETIC,
                duration=0.5,
                software_support=ae_only,
                params={"type": "stutter", "stutters": 5},
                description="卡顿跳动式故障过渡",
                tags=["glitch", "stutter", "energetic"],
            ),
        ]

        for preset in presets:
            self._presets[preset.id] = preset

    def get_preset(self, preset_id: str) -> Optional[TransitionPreset]:
        """根据ID获取预设"""
        return self._presets.get(preset_id)

    def list_all_presets(self) -> List[TransitionPreset]:
        """列出所有预设"""
        return list(self._presets.values())

    def search_presets(
        self,
        category: Optional[TransitionCategory] = None,
        style: Optional[TransitionStyle] = None,
        software: Optional[SoftwareTarget] = None,
        max_duration: Optional[float] = None,
        min_duration: Optional[float] = None,
        tags: Optional[List[str]] = None,
        query: Optional[str] = None,
    ) -> List[TransitionPreset]:
        """搜索预设

        Args:
            category: 按分类筛选
            style: 按风格筛选
            software: 按支持软件筛选
            max_duration: 最大持续时间
            min_duration: 最小持续时间
            tags: 标签列表
            query: 文本搜索

        Returns:
            匹配的预设列表
        """
        results = list(self._presets.values())

        if category:
            results = [p for p in results if p.category == category]
        if style:
            results = [p for p in results if p.style == style]
        if software:
            results = [p for p in results if software in p.software_support]
        if max_duration is not None:
            results = [p for p in results if p.duration <= max_duration]
        if min_duration is not None:
            results = [p for p in results if p.duration >= min_duration]
        if tags:
            results = [p for p in results if any(t in p.tags for t in tags)]
        if query:
            query_lower = query.lower()
            results = [
                p for p in results
                if query_lower in p.name.lower()
                or query_lower in p.description.lower()
                or any(query_lower in t.lower() for t in p.tags)
            ]

        return results

    def save_preset(self, preset: TransitionPreset, file_path: str) -> None:
        """保存预设到JSON文件"""
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(preset.to_dict(), f, ensure_ascii=False, indent=2)

    def load_preset(self, file_path: str) -> TransitionPreset:
        """从JSON文件加载预设"""
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return TransitionPreset.from_dict(data)

    def add_preset(self, preset: TransitionPreset) -> None:
        """添加预设到库"""
        self._presets[preset.id] = preset

    def get_recommendation(
        self,
        context: str = "default",
        mood: Optional[str] = None,
        scene_type: Optional[str] = None,
        music_genre: Optional[str] = None,
    ) -> List[Tuple[TransitionPreset, float]]:
        """获取预设推荐

        Args:
            context: 上下文类型
            mood: 情绪标签
            scene_type: 场景类型
            music_genre: 音乐类型

        Returns:
            (预设, 置信度) 元组列表
        """
        scores: Dict[str, float] = {}

        mood_style_map = {
            "calm": TransitionStyle.SOFT,
            "peaceful": TransitionStyle.DREAMY,
            "energetic": TransitionStyle.ENERGETIC,
            "exciting": TransitionStyle.DYNAMIC,
            "sad": TransitionStyle.SOFT,
            "happy": TransitionStyle.DYNAMIC,
            "mysterious": TransitionStyle.CINEMATIC,
            "retro": TransitionStyle.RETRO,
            "futuristic": TransitionStyle.FUTURISTIC,
            "dark": TransitionStyle.CINEMATIC,
            "glitch": TransitionStyle.GLITCHY,
        }

        scene_category_map = {
            "dialogue": TransitionCategory.DISSOLVE,
            "action": TransitionCategory.DYNAMIC if False else TransitionCategory.ZOOM,
            "landscape": TransitionCategory.DISSOLVE,
            "text": TransitionCategory.TEXT_TRANSITION,
            "logo": TransitionCategory.GLOW_LIGHT,
            "vlog": TransitionCategory.DISSOLVE,
            "mvg": TransitionCategory.ZOOM,
            "trailer": TransitionCategory.THREE_D,
        }

        if mood and mood in mood_style_map:
            target_style = mood_style_map[mood]
            for pid, preset in self._presets.items():
                if preset.style == target_style:
                    scores[pid] = scores.get(pid, 0) + 0.4

        if scene_type and scene_type in scene_category_map:
            target_cat = scene_category_map[scene_type]
            for pid, preset in self._presets.items():
                if preset.category == target_cat:
                    scores[pid] = scores.get(pid, 0) + 0.3

        if music_genre:
            genre_boost = {
                "edm": (TransitionCategory.GLITCH, TransitionStyle.ENERGETIC),
                "hiphop": (TransitionCategory.DYNAMIC if False else TransitionCategory.ZOOM, TransitionStyle.ENERGETIC),
                "classical": (TransitionCategory.DISSOLVE, TransitionStyle.CINEMATIC),
                "rock": (TransitionCategory.DISTORT, TransitionStyle.ENERGETIC),
                "pop": (TransitionCategory.ZOOM, TransitionStyle.DYNAMIC),
                "jazz": (TransitionCategory.DISSOLVE, TransitionStyle.SOFT),
                "ambient": (TransitionCategory.GLOW_LIGHT, TransitionStyle.DREAMY),
            }
            if music_genre.lower() in genre_boost:
                cat, style = genre_boost[music_genre.lower()]
                for pid, preset in self._presets.items():
                    if preset.category == cat:
                        scores[pid] = scores.get(pid, 0) + 0.2
                    if preset.style == style:
                        scores[pid] = scores.get(pid, 0) + 0.2

        ranked = [(self._presets[pid], score) for pid, score in scores.items()]
        ranked.sort(key=lambda x: x[1], reverse=True)

        if not ranked:
            default_presets = ["crossfade_standard", "dip_to_black", "wipe_linear_right"]
            ranked = [
                (self._presets[pid], 0.5)
                for pid in default_presets
                if pid in self._presets
            ]

        return ranked[:10]

    def get_presets_by_category(self) -> Dict[TransitionCategory, List[TransitionPreset]]:
        """按分类组织预设"""
        result: Dict[TransitionCategory, List[TransitionPreset]] = {}
        for preset in self._presets.values():
            if preset.category not in result:
                result[preset.category] = []
            result[preset.category].append(preset)
        return result

    def count_presets(self) -> int:
        """获取预设总数"""
        return len(self._presets)


# ===========================================================================
# 9. 过渡智能系统
# ===========================================================================

class TransitionAI:
    """过渡智能推荐系统

    基于音乐、场景、类型等上下文智能推荐过渡效果。
    """

    def __init__(self, preset_library: Optional[PresetLibrary] = None) -> None:
        self.library = preset_library or PresetLibrary()

    def recommend_by_music(
        self,
        bpm: float = 120.0,
        energy: float = 0.5,
        mood: str = "neutral",
        genre: str = "pop",
    ) -> List[Tuple[TransitionPreset, float]]:
        """基于音乐特征推荐过渡

        Args:
            bpm: 每分钟节拍数
            energy: 能量值 (0.0 ~ 1.0)
            mood: 情绪标签
            genre: 音乐风格

        Returns:
            (预设, 置信度) 列表
        """
        recommendations = self.library.get_recommendation(
            mood=mood, music_genre=genre
        )

        results = []
        for preset, base_score in recommendations:
            score = base_score

            if bpm > 140 and preset.style in (TransitionStyle.ENERGETIC, TransitionStyle.DYNAMIC):
                score += 0.15
            elif bpm < 80 and preset.style in (TransitionStyle.SOFT, TransitionStyle.DREAMY):
                score += 0.15

            if energy > 0.7 and preset.duration < 0.5:
                score += 0.1
            elif energy < 0.3 and preset.duration > 0.8:
                score += 0.1

            results.append((preset, min(1.0, score)))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:10]

    def recommend_by_scene(
        self,
        scene_type: str = "generic",
        motion_level: float = 0.5,
        scene_dynamics: str = "medium",
    ) -> List[Tuple[TransitionPreset, float]]:
        """基于场景内容推荐过渡

        Args:
            scene_type: 场景类型
            motion_level: 运动水平 (0.0 ~ 1.0)
            scene_dynamics: 动态级别

        Returns:
            (预设, 置信度) 列表
        """
        recommendations = self.library.get_recommendation(scene_type=scene_type)

        results = []
        for preset, base_score in recommendations:
            score = base_score

            if motion_level > 0.7:
                if preset.category in (TransitionCategory.ZOOM, TransitionCategory.SLIDE, TransitionCategory.MOTION_BLUR):
                    score += 0.2
            elif motion_level < 0.3:
                if preset.category in (TransitionCategory.DISSOLVE, TransitionCategory.GLOW_LIGHT):
                    score += 0.15

            results.append((preset, min(1.0, score)))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:10]

    def recommend_by_genre(
        self,
        video_genre: str = "vlog",
    ) -> List[Tuple[TransitionPreset, float]]:
        """基于视频类型推荐过渡

        Args:
            video_genre: 视频类型 (mvg/vlog/cinematic/trailer/...)

        Returns:
            (预设, 置信度) 列表
        """
        genre_presets = {
            "mvg": [
                "zoom_standard", "glitch_rgb_split", "3d_cube_flip_y",
                "particle_dissolve_shatter", "motion_blur_horizontal",
            ],
            "vlog": [
                "crossfade_standard", "wipe_soft_linear", "dip_to_white",
                "zoom_subtle", "glow_light_leak",
            ],
            "cinematic": [
                "dip_to_black", "3d_page_turn", "wipe_iris_circle",
                "zoom_dramatic", "glow_optical_flare",
            ],
            "trailer": [
                "3d_cube_flip_x", "zoom_dramatic", "glitch_digital_noise",
                "particle_dissolve_shatter", "motion_blur_horizontal",
            ],
            "slideshow": [
                "crossfade_slow", "wipe_soft_linear", "shape_circle_reveal",
                "zoom_ken_burns", "glow_light_leak",
            ],
            "tutorial": [
                "crossfade_standard", "wipe_linear_right", "text_typewriter",
                "dip_to_white", "color_flash_white",
            ],
        }

        preset_ids = genre_presets.get(video_genre, ["crossfade_standard"])

        results = []
        for i, pid in enumerate(preset_ids):
            preset = self.library.get_preset(pid)
            if preset:
                score = 1.0 - (i * 0.08)
                results.append((preset, max(0.3, score)))

        return results

    def auto_pick_transition(
        self,
        context: Dict[str, Any],
    ) -> Tuple[Optional[TransitionPreset], float]:
        """智能选择过渡

        Args:
            context: 上下文字典，可包含 bpm, energy, mood, genre, scene_type 等

        Returns:
            (最佳预设, 置信度)
        """
        all_scores: Dict[str, float] = {}

        if "bpm" in context or "mood" in context or "genre" in context:
            music_recs = self.recommend_by_music(
                bpm=context.get("bpm", 120),
                energy=context.get("energy", 0.5),
                mood=context.get("mood", "neutral"),
                genre=context.get("genre", "pop"),
            )
            for preset, score in music_recs:
                all_scores[preset.id] = all_scores.get(preset.id, 0) + score * 0.4

        if "scene_type" in context:
            scene_recs = self.recommend_by_scene(
                scene_type=context.get("scene_type", "generic"),
                motion_level=context.get("motion_level", 0.5),
            )
            for preset, score in scene_recs:
                all_scores[preset.id] = all_scores.get(preset.id, 0) + score * 0.3

        if "video_genre" in context:
            genre_recs = self.recommend_by_genre(
                video_genre=context.get("video_genre", "vlog"),
            )
            for preset, score in genre_recs:
                all_scores[preset.id] = all_scores.get(preset.id, 0) + score * 0.3

        if not all_scores:
            default = self.library.get_preset("crossfade_standard")
            return (default, 0.5) if default else (None, 0.0)

        best_id = max(all_scores, key=all_scores.get)
        best_preset = self.library.get_preset(best_id)
        return (best_preset, min(1.0, all_scores[best_id]))

    def beat_sync_transitions(
        self,
        beat_times: List[float],
        video_clips: List[Dict[str, Any]],
        default_preset_id: str = "crossfade_standard",
    ) -> List[Dict[str, Any]]:
        """将过渡点同步到节拍

        Args:
            beat_times: 节拍时间点列表（秒）
            video_clips: 视频片段列表
            default_preset_id: 默认预设ID

        Returns:
            过渡配置列表
        """
        transitions = []
        preset = self.library.get_preset(default_preset_id)

        for i in range(len(video_clips) - 1):
            clip_end = video_clips[i].get("end_time", 0)
            next_clip_start = video_clips[i + 1].get("start_time", 0)
            edit_point = (clip_end + next_clip_start) / 2

            nearest_beat = min(beat_times, key=lambda b: abs(b - edit_point))
            duration = preset.duration if preset else 0.5

            transitions.append({
                "from_layer": f"Clip_{i}",
                "to_layer": f"Clip_{i+1}",
                "start_time": nearest_beat - duration / 2,
                "duration": duration,
                "preset_id": default_preset_id,
                "is_beat_synced": True,
                "beat_time": nearest_beat,
            })

        return transitions

    def transition_timing_map(
        self,
        total_duration: float,
        num_transitions: int,
        pattern: str = "even",
        beat_times: Optional[List[float]] = None,
    ) -> List[float]:
        """生成过渡时间点映射

        Args:
            total_duration: 总时长
            num_transitions: 过渡数量
            pattern: 时间分布模式 - even/random/beat_accelerated/decelerated
            beat_times: 可选节拍时间点

        Returns:
            过渡时间点列表
        """
        if num_transitions <= 0:
            return []

        times = []

        if pattern == "even":
            interval = total_duration / (num_transitions + 1)
            times = [interval * (i + 1) for i in range(num_transitions)]

        elif pattern == "random":
            positions = sorted(random.sample(range(1, int(total_duration * 100)), num_transitions))
            times = [p / 100.0 for p in positions]

        elif pattern == "accelerated":
            interval = total_duration / (num_transitions * 2)
            current = interval
            for i in range(num_transitions):
                times.append(current)
                interval *= 0.85
                current += interval

        elif pattern == "decelerated":
            interval = 0.5
            current = 0.5
            for i in range(num_transitions):
                times.append(min(total_duration - 0.5, current))
                interval *= 1.15
                current += interval

        elif pattern == "beat" and beat_times:
            step = max(1, len(beat_times) // num_transitions)
            times = [beat_times[i * step] for i in range(num_transitions) if i * step < len(beat_times)]

        return [max(0, min(total_duration, t)) for t in times]


# ===========================================================================
# 10. 跨软件桥接与集成
# ===========================================================================

class UnifiedTransitionAPI:
    """跨软件统一过渡API

    提供单一接口在不同软件平台间应用过渡效果。
    """

    def __init__(self) -> None:
        self.ae_engine = AETransitionEngine()
        self.pr_engine = PRTransitionEngine()
        self.resolve_engine = ResolveTransitionEngine()
        self.blender_engine = BlenderTransitionEngine()
        self.ffmpeg_engine = FFmpegTransitionEngine()
        self.preset_library = PresetLibrary()
        self.transition_ai = TransitionAI(self.preset_library)

    def apply_transition(
        self,
        software: SoftwareTarget,
        preset: Union[TransitionPreset, str],
        from_item: str,
        to_item: str,
        start_time: float,
        duration: float,
        **kwargs: Any,
    ) -> str:
        """统一应用过渡效果

        Args:
            software: 目标软件
            preset: 过渡预设或预设ID
            from_item: 起始元素（图层/剪辑/节点等）
            to_item: 目标元素
            start_time: 开始时间
            duration: 持续时间
            **kwargs: 额外参数

        Returns:
            对应软件的脚本/命令代码
        """
        if isinstance(preset, str):
            preset_obj = self.preset_library.get_preset(preset)
            if not preset_obj:
                raise ValueError(f"预设不存在: {preset}")
            preset = preset_obj

        if not self.validate_compatibility(preset, software):
            raise ValueError(
                f"预设 '{preset.name}' 不支持软件 {software.value}"
            )

        dispatch = {
            SoftwareTarget.AFTER_EFFECTS: self._apply_ae,
            SoftwareTarget.PREMIERE_PRO: self._apply_pr,
            SoftwareTarget.DAVINCI_RESOLVE: self._apply_resolve,
            SoftwareTarget.BLENDER: self._apply_blender,
            SoftwareTarget.FFMPEG: self._apply_ffmpeg,
        }

        func = dispatch.get(software)
        if not func:
            raise ValueError(f"不支持的软件: {software.value}")

        return func(preset, from_item, to_item, start_time, duration, **kwargs)

    def _apply_ae(
        self,
        preset: TransitionPreset,
        from_layer: str,
        to_layer: str,
        start_time: float,
        duration: float,
        **kwargs: Any,
    ) -> str:
        return self.ae_engine.apply_transition(preset, from_layer, to_layer, start_time, duration)

    def _apply_pr(
        self,
        preset: TransitionPreset,
        track_index: str,
        clip_index: str,
        start_time: float,
        duration: float,
        **kwargs: Any,
    ) -> str:
        pr_transition_key = self._map_preset_to_pr(preset)
        if pr_transition_key:
            return self.pr_engine.apply_builtin_transition(
                pr_transition_key,
                kwargs.get("track_index", 0),
                kwargs.get("clip_index", 0),
                duration,
                kwargs.get("alignment", "center"),
            )
        return self.pr_engine.create_custom_transition(
            track_index, clip_index, [], duration
        )

    def _apply_resolve(
        self,
        preset: TransitionPreset,
        timeline: str,
        item_ref: str,
        start_time: float,
        duration: float,
        **kwargs: Any,
    ) -> str:
        resolve_name = self._map_preset_to_resolve(preset)
        return self.resolve_engine.apply_edit_page_transition(
            resolve_name or "Cross Dissolve",
            timeline,
            kwargs.get("track_index", 1),
            kwargs.get("item_index", 0),
            duration,
        )

    def _apply_blender(
        self,
        preset: TransitionPreset,
        from_obj: str,
        to_obj: str,
        start_frame: float,
        duration_frames: float,
        **kwargs: Any,
    ) -> str:
        return self.blender_engine.create_compositor_transition(
            transition_type="crossfade",
            start_frame=int(start_frame),
            duration_frames=int(duration_frames),
        )

    def _apply_ffmpeg(
        self,
        preset: TransitionPreset,
        input1: str,
        input2: str,
        start_time: float,
        duration: float,
        output: str = "output.mp4",
        **kwargs: Any,
    ) -> str:
        ffmpeg_transition = self._map_preset_to_ffmpeg(preset)
        offset = kwargs.get("offset", start_time)
        return self.ffmpeg_engine.create_crossfade_command(
            input1, input2, output, duration, offset, ffmpeg_transition
        )

    def batch_apply(
        self,
        software: SoftwareTarget,
        transitions: List[Dict[str, Any]],
    ) -> str:
        """批量应用过渡

        Args:
            software: 目标软件
            transitions: 过渡配置列表

        Returns:
            批量脚本/命令
        """
        if software == SoftwareTarget.AFTER_EFFECTS:
            ae_transitions = []
            for t in transitions:
                preset = t.get("preset")
                if isinstance(preset, str):
                    preset = self.preset_library.get_preset(preset)
                ae_transitions.append({
                    "preset": preset,
                    "from_layer": t.get("from_layer", ""),
                    "to_layer": t.get("to_layer", ""),
                    "start_time": t.get("start_time", 0),
                    "duration": t.get("duration", 0.5),
                })
            return self.ae_engine.generate_jsx_script(ae_transitions)

        elif software == SoftwareTarget.PREMIERE_PRO:
            ops = []
            for t in transitions:
                ops.append({
                    "type": "builtin",
                    "transition": t.get("preset", "cross_dissolve"),
                    "track": t.get("track_index", 0),
                    "clip_index": t.get("clip_index", 0),
                    "duration": t.get("duration", 0.5),
                })
            return self.pr_engine.generate_pr_script(ops)

        elif software == SoftwareTarget.FFMPEG:
            inputs = t.get("inputs", []) if transitions else []
            output = transitions[0].get("output", "output.mp4") if transitions else "output.mp4"
            return self.ffmpeg_engine.batch_transcode_with_transitions(
                inputs, output,
                transition_duration=transitions[0].get("duration", 0.5) if transitions else 0.5,
            )

        return ""

    def export_to_software(
        self,
        preset: TransitionPreset,
        target_software: SoftwareTarget,
        output_path: str,
    ) -> None:
        """导出预设到目标软件格式

        Args:
            preset: 过渡预设
            target_software: 目标软件
            output_path: 输出文件路径
        """
        data = preset.to_dict()
        data["target_software"] = target_software.value

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def convert_preset(
        self,
        preset: TransitionPreset,
        target_software: SoftwareTarget,
    ) -> Dict[str, Any]:
        """转换预设到目标软件格式

        Args:
            preset: 源预设
            target_software: 目标软件

        Returns:
            转换后的预设数据
        """
        result = preset.to_dict()
        result["target_software"] = target_software.value

        if target_software == SoftwareTarget.AFTER_EFFECTS:
            result["ae_params"] = preset.params
        elif target_software == SoftwareTarget.FFMPEG:
            result["ffmpeg_transition"] = self._map_preset_to_ffmpeg(preset)
        elif target_software == SoftwareTarget.PREMIERE_PRO:
            result["pr_transition"] = self._map_preset_to_pr(preset)

        return result

    def validate_compatibility(
        self,
        preset: TransitionPreset,
        software: SoftwareTarget,
    ) -> bool:
        """验证预设是否兼容目标软件

        Args:
            preset: 过渡预设
            software: 目标软件

        Returns:
            是否兼容
        """
        return software in preset.software_support

    def _map_preset_to_ffmpeg(self, preset: TransitionPreset) -> str:
        """将预设映射到 FFmpeg xfade 过渡类型"""
        mapping = {
            "crossfade_standard": "fade",
            "wipe_linear_left": "wipeleft",
            "wipe_linear_right": "wiperight",
            "wipe_diagonal": "diagtl",
            "zoom_standard": "zoomin",
        }
        return mapping.get(preset.id, "fade")

    def _map_preset_to_pr(self, preset: TransitionPreset) -> Optional[str]:
        """将预设映射到 Premiere Pro 内置过渡"""
        mapping = {
            "crossfade_standard": "cross_dissolve",
            "dip_to_black": "dip_to_black",
            "dip_to_white": "dip_to_white",
            "film_dissolve": "film_dissolve",
            "additive_dissolve": "additive_dissolve",
        }
        return mapping.get(preset.id)

    def _map_preset_to_resolve(self, preset: TransitionPreset) -> Optional[str]:
        """将预设映射到 DaVinci Resolve 内置过渡"""
        mapping = {
            "crossfade_standard": "Cross Dissolve",
            "dip_to_black": "Dip to Color",
            "film_dissolve": "Film Dissolve",
        }
        return mapping.get(preset.id)

    def get_supported_software(self, preset_id: str) -> List[SoftwareTarget]:
        """获取预设支持的软件列表"""
        preset = self.preset_library.get_preset(preset_id)
        if not preset:
            return []
        return preset.software_support

    def auto_generate(
        self,
        software: SoftwareTarget,
        context: Dict[str, Any],
        from_item: str,
        to_item: str,
        start_time: float,
        duration: float,
    ) -> Tuple[str, Optional[TransitionPreset]]:
        """自动生成过渡代码

        使用AI推荐最佳预设并生成代码。

        Args:
            software: 目标软件
            context: 上下文信息
            from_item: 起始元素
            to_item: 目标元素
            start_time: 开始时间
            duration: 持续时间

        Returns:
            (代码, 使用的预设)
        """
        preset, confidence = self.transition_ai.auto_pick_transition(context)
        if not preset:
            preset = self.preset_library.get_preset("crossfade_standard")

        if not preset:
            return "", None

        if software not in preset.software_support:
            alternatives = self.preset_library.search_presets(software=software)
            if alternatives:
                preset = alternatives[0]

        code = self.apply_transition(
            software, preset, from_item, to_item, start_time, duration
        )
        return code, preset


# ===========================================================================
# 主入口 / Demo
# ===========================================================================

def main() -> None:
    """Transition Engine 演示程序"""
    print("=" * 70)
    print("  Transition Engine v2.0 - 跨平台过渡效果统一引擎")
    print("=" * 70)

    print("\n【1】初始化组件...")
    easing = EasingEngine()
    library = PresetLibrary()
    ae_engine = AETransitionEngine(easing)
    unified = UnifiedTransitionAPI()

    print(f"    - 缓动函数数量: {len(easing.get_available_easings())}")
    print(f"    - 过渡预设数量: {library.count_presets()}")

    print("\n【2】预设分类统计...")
    by_category = library.get_presets_by_category()
    for cat, presets in sorted(by_category.items(), key=lambda x: x[0].value):
        print(f"    - {cat.value:15s}: {len(presets):3d} 个")

    print("\n【3】缓动函数测试...")
    test_values = [0.0, 0.25, 0.5, 0.75, 1.0]
    test_easings = ["linear", "ease_in_out", "ease_out_bounce", "ease_out_elastic", "ease_in_out_back"]
    for ease in test_easings:
        values = [round(easing.map_progress(t, ease), 3) for t in test_values]
        print(f"    {ease:20s}: {values}")

    print("\n【4】贝塞尔曲线测试...")
    bezier_val = easing.bezier_curve(0.5, (0.25, 0.1), (0.25, 1.0))
    print(f"    cubic-bezier(0.25, 0.1, 0.25, 1.0) at t=0.5: {bezier_val:.4f}")

    print("\n【5】弹簧动画测试...")
    spring_val = easing.spring_animation(0.5, stiffness=100, damping=10, mass=1)
    print(f"    spring(t=0.5, stiff=100, damp=10): {spring_val:.4f}")

    print("\n【6】AE 过渡生成示例 (交叉淡化)...")
    sample_preset = library.get_preset("crossfade_standard")
    if sample_preset:
        jsx = ae_engine.apply_transition(
            sample_preset,
            "Layer_A",
            "Layer_B",
            start_time=2.0,
            duration=0.5,
        )
        print(f"    生成 JSX 代码长度: {len(jsx)} 字符")
        print(f"    前3行预览:")
        for line in jsx.strip().split("\n")[:3]:
            print(f"      {line.strip()}")

    print("\n【7】AI 智能推荐 (音乐: energetic/edm)...")
    ai = TransitionAI(library)
    recs = ai.recommend_by_music(bpm=128, energy=0.8, mood="energetic", genre="edm")
    print(f"    Top 5 推荐:")
    for i, (preset, score) in enumerate(recs[:5], 1):
        print(f"      {i}. {preset.name:20s} (置信度: {score:.2f}, 分类: {preset.category.value})")

    print("\n【8】跨软件统一 API 测试...")
    ffmpeg_cmd = unified.apply_transition(
        SoftwareTarget.FFMPEG,
        "crossfade_standard",
        "input1.mp4",
        "input2.mp4",
        start_time=0,
        duration=0.5,
        offset=9.5,
        output="output.mp4",
    )
    print(f"    FFmpeg 命令 (前80字符): {ffmpeg_cmd[:80]}...")

    print("\n【9】预设搜索测试 (筛选: 故障风格)...")
    glitch_presets = library.search_presets(style=TransitionStyle.GLITCHY)
    print(f"    找到 {len(glitch_presets)} 个故障风格预设:")
    for p in glitch_presets:
        print(f"      - {p.name} ({p.category.value})")

    print("\n【10】节拍同步测试...")
    beat_times = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
    clips = [
        {"start_time": 0, "end_time": 2.5},
        {"start_time": 2.5, "end_time": 5.0},
        {"start_time": 5.0, "end_time": 8.0},
    ]
    synced = ai.beat_sync_transitions(beat_times, clips)
    print(f"    生成 {len(synced)} 个节拍同步过渡:")
    for t in synced:
        print(f"      - {t['from_layer']} -> {t['to_layer']}: "
              f"start={t['start_time']:.2f}s, beat={t['beat_time']:.2f}s")

    print("\n" + "=" * 70)
    print("  Transition Engine 演示完成！")
    print("=" * 70)


if __name__ == "__main__":
    main()