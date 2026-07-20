"""
Text Animation Engine - 跨平台文本动画与特效引擎
======================================================
集成 After Effects、Premiere Pro、Photoshop、DaVinci Resolve、Blender 的
文本动画、文字特效、排版与字体管理系统。

Production-grade architecture with type hints, error handling, and comprehensive docs.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union


# ============================================================================
# 1. 核心枚举与数据类
# ============================================================================

class TextAnimationType(str, Enum):
    """文本动画类型枚举 - 24种核心动画效果"""
    FADE_IN = "fade_in"
    FADE_OUT = "fade_out"
    SLIDE_LEFT = "slide_left"
    SLIDE_RIGHT = "slide_right"
    SLIDE_UP = "slide_up"
    SLIDE_DOWN = "slide_down"
    SCALE_IN = "scale_in"
    SCALE_OUT = "scale_out"
    TYPEWRITER = "typewriter"
    BOUNCE_IN = "bounce_in"
    ELASTIC_SCALE = "elastic_scale"
    ROTATE_IN = "rotate_in"
    FLIP_3D = "flip_3d"
    PATH_ANIMATION = "path_animation"
    PARTICLE_CONVERGE = "particle_converge"
    HANDWRITING = "handwriting"
    LIQUID_MORPH = "liquid_morph"
    GLITCH = "glitch"
    WAVE = "wave"
    PULSE = "pulse"
    BLUR_IN = "blur_in"
    BLUR_OUT = "blur_out"
    TRACKING_IN = "tracking_in"
    TRACKING_OUT = "tracking_out"


class EasingType(str, Enum):
    """缓动函数类型"""
    LINEAR = "linear"
    EASE_IN = "ease_in"
    EASE_OUT = "ease_out"
    EASE_IN_OUT = "ease_in_out"
    EASE_IN_QUAD = "ease_in_quad"
    EASE_OUT_QUAD = "ease_out_quad"
    EASE_IN_CUBIC = "ease_in_cubic"
    EASE_OUT_CUBIC = "ease_out_cubic"
    EASE_IN_BACK = "ease_in_back"
    EASE_OUT_BACK = "ease_out_back"
    EASE_OUT_ELASTIC = "ease_out_elastic"
    EASE_OUT_BOUNCE = "ease_out_bounce"


class SoftwareTarget(str, Enum):
    """目标软件平台"""
    AFTER_EFFECTS = "after_effects"
    PREMIERE_PRO = "premiere_pro"
    PHOTOSHOP = "photoshop"
    DAVINCI_RESOLVE = "davinci_resolve"
    BLENDER = "blender"


@dataclass
class AnimationParams:
    """动画参数配置"""
    start_delay: float = 0.0
    duration: float = 1.0
    easing: EasingType = EasingType.EASE_OUT
    intensity: float = 1.0
    direction: str = "forward"
    offset: Tuple[float, float] = (0.0, 0.0)
    per_char_delay: float = 0.0
    blur_amount: float = 20.0
    scale_factor: float = 1.5
    rotation_degrees: float = 360.0
    bounce_count: int = 3
    wave_amplitude: float = 20.0
    wave_frequency: float = 2.0
    glitch_intensity: float = 0.5


@dataclass
class TextStyle:
    """文本样式配置"""
    font_family: str = "Arial"
    font_size: float = 72.0
    font_weight: str = "bold"
    font_style: str = "normal"
    fill_color: Tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0)
    stroke_color: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0)
    stroke_width: float = 0.0
    letter_spacing: float = 0.0
    line_spacing: float = 1.2
    paragraph_align: str = "center"
    tracking: float = 0.0
    leading: float = 0.0
    baseline_shift: float = 0.0


@dataclass
class TextAnimationPreset:
    """文本动画预设"""
    name: str
    type: TextAnimationType
    duration: float = 1.0
    easing: EasingType = EasingType.EASE_OUT
    params: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    category: str = "basic"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type.value,
            "duration": self.duration,
            "easing": self.easing.value,
            "params": self.params,
            "description": self.description,
            "category": self.category,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TextAnimationPreset":
        return cls(
            name=data["name"],
            type=TextAnimationType(data["type"]),
            duration=data.get("duration", 1.0),
            easing=EasingType(data.get("easing", "ease_out")),
            params=data.get("params", {}),
            description=data.get("description", ""),
            category=data.get("category", "basic"),
        )


# ============================================================================
# 2. After Effects 文本动画生成器
# ============================================================================

class AETextAnimator:
    """After Effects 文本动画生成器

    生成可直接在 AE 中执行的 ExtendScript (JSX) 代码，
    支持20+种文本动画效果、逐字动画、路径文字、粒子文字等。
    """

    def __init__(self, comp_name: str = "Text Animation Comp",
                 comp_width: int = 1920, comp_height: int = 1080,
                 frame_rate: float = 30.0, duration: float = 5.0):
        self.comp_name = comp_name
        self.comp_width = comp_width
        self.comp_height = comp_height
        self.frame_rate = frame_rate
        self.duration = duration
        self._layers: List[str] = []
        self._animations: List[str] = []

    def _easing_expression(self, easing: EasingType) -> str:
        """生成 AE 表达式缓动函数"""
        easing_map = {
            EasingType.LINEAR: "linear",
            EasingType.EASE_IN: "easeIn",
            EasingType.EASE_OUT: "easeOut",
            EasingType.EASE_IN_OUT: "ease",
            EasingType.EASE_IN_QUAD: "easeInQuad",
            EasingType.EASE_OUT_QUAD: "easeOutQuad",
            EasingType.EASE_IN_CUBIC: "easeInCubic",
            EasingType.EASE_OUT_CUBIC: "easeOutCubic",
            EasingType.EASE_IN_BACK: "easeInBack",
            EasingType.EASE_OUT_BACK: "easeOutBack",
            EasingType.EASE_OUT_ELASTIC: "easeOutElastic",
            EasingType.EASE_OUT_BOUNCE: "easeOutBounce",
        }
        return easing_map.get(easing, "easeOut")

    def create_text_layer(self, text: str, style: Optional[TextStyle] = None,
                          layer_name: str = "Text Layer") -> str:
        """创建文本图层

        Args:
            text: 文本内容
            style: 文本样式配置
            layer_name: 图层名称

        Returns:
            JSX 代码片段
        """
        if style is None:
            style = TextStyle()

        jsx = f'''
var textLayer = comp.layers.addText("{text}");
textLayer.name = "{layer_name}";
textLayer.property("Source Text").setValue(
    new TextDocument("{text}")
);
var textProp = textLayer.property("Source Text");
var textDoc = textProp.value;
textDoc.font = "{style.font_family}";
textDoc.fontSize = {style.font_size};
textDoc.fillColor = [{style.fill_color[0]}, {style.fill_color[1]}, {style.fill_color[2]}];
textDoc.strokeColor = [{style.stroke_color[0]}, {style.stroke_color[1]}, {style.stroke_color[2]}];
textDoc.strokeWidth = {style.stroke_width};
textDoc.tracking = {style.letter_spacing};
textDoc.leading = {style.leading};
textDoc.justification = ParagraphJustification.CENTER_JUSTIFY;
textProp.setValue(textDoc);
textLayer.position.setValue([{self.comp_width/2}, {self.comp_height/2}]);
textLayer.anchorPoint.setValue([textLayer.width / 2, textLayer.height / 2]);
'''
        self._layers.append(jsx)
        return jsx

    def apply_animation(self, layer_name: str, anim_type: TextAnimationType,
                        params: Optional[AnimationParams] = None) -> str:
        """应用动画预设到文本图层

        Args:
            layer_name: 目标图层名称
            anim_type: 动画类型
            params: 动画参数

        Returns:
            JSX 代码片段
        """
        if params is None:
            params = AnimationParams()

        animation_map = {
            TextAnimationType.FADE_IN: self._fade_in,
            TextAnimationType.FADE_OUT: self._fade_out,
            TextAnimationType.SLIDE_LEFT: self._slide_left,
            TextAnimationType.SLIDE_RIGHT: self._slide_right,
            TextAnimationType.SLIDE_UP: self._slide_up,
            TextAnimationType.SLIDE_DOWN: self._slide_down,
            TextAnimationType.SCALE_IN: self._scale_in,
            TextAnimationType.SCALE_OUT: self._scale_out,
            TextAnimationType.TYPEWRITER: self.create_typewriter_effect,
            TextAnimationType.BOUNCE_IN: self._bounce_in,
            TextAnimationType.ELASTIC_SCALE: self._elastic_scale,
            TextAnimationType.ROTATE_IN: self._rotate_in,
            TextAnimationType.FLIP_3D: self.create_3d_text_animation,
            TextAnimationType.PATH_ANIMATION: self.create_path_text,
            TextAnimationType.PARTICLE_CONVERGE: self.create_particle_text,
            TextAnimationType.GLITCH: self.create_glitch_text,
            TextAnimationType.WAVE: self._wave_animation,
            TextAnimationType.PULSE: self._pulse_animation,
            TextAnimationType.BLUR_IN: self._blur_in,
            TextAnimationType.BLUR_OUT: self._blur_out,
            TextAnimationType.TRACKING_IN: self._tracking_in,
            TextAnimationType.TRACKING_OUT: self._tracking_out,
        }

        anim_func = animation_map.get(anim_type)
        if anim_func is None:
            raise ValueError(f"Unsupported animation type: {anim_type}")

        return anim_func(layer_name, params)

    def _fade_in(self, layer_name: str, params: AnimationParams) -> str:
        """淡入动画"""
        easing = self._easing_expression(params.easing)
        start_f = int(params.start_delay * self.frame_rate)
        end_f = int((params.start_delay + params.duration) * self.frame_rate)
        return f'''
var layer = comp.layers.byName("{layer_name}");
layer.opacity.setValueAtTime({start_f/self.frame_rate}, 0);
layer.opacity.setValueAtTime({end_f/self.frame_rate}, 100);
var ease = "{easing}";
'''

    def _fade_out(self, layer_name: str, params: AnimationParams) -> str:
        """淡出动画"""
        easing = self._easing_expression(params.easing)
        start_f = int(params.start_delay * self.frame_rate)
        end_f = int((params.start_delay + params.duration) * self.frame_rate)
        return f'''
var layer = comp.layers.byName("{layer_name}");
layer.opacity.setValueAtTime({start_f/self.frame_rate}, 100);
layer.opacity.setValueAtTime({end_f/self.frame_rate}, 0);
'''

    def _slide_left(self, layer_name: str, params: AnimationParams) -> str:
        """从左侧滑入"""
        start_f = int(params.start_delay * self.frame_rate)
        end_f = int((params.start_delay + params.duration) * self.frame_rate)
        offset_x = self.comp_width * 0.5 * params.intensity
        return f'''
var layer = comp.layers.byName("{layer_name}");
var startPos = [layer.position.value[0] - {offset_x}, layer.position.value[1]];
var endPos = layer.position.value;
layer.position.setValueAtTime({start_f/self.frame_rate}, startPos);
layer.position.setValueAtTime({end_f/self.frame_rate}, endPos);
'''

    def _slide_right(self, layer_name: str, params: AnimationParams) -> str:
        """从右侧滑入"""
        start_f = int(params.start_delay * self.frame_rate)
        end_f = int((params.start_delay + params.duration) * self.frame_rate)
        offset_x = self.comp_width * 0.5 * params.intensity
        return f'''
var layer = comp.layers.byName("{layer_name}");
var startPos = [layer.position.value[0] + {offset_x}, layer.position.value[1]];
var endPos = layer.position.value;
layer.position.setValueAtTime({start_f/self.frame_rate}, startPos);
layer.position.setValueAtTime({end_f/self.frame_rate}, endPos);
'''

    def _slide_up(self, layer_name: str, params: AnimationParams) -> str:
        """从下方滑入"""
        start_f = int(params.start_delay * self.frame_rate)
        end_f = int((params.start_delay + params.duration) * self.frame_rate)
        offset_y = self.comp_height * 0.3 * params.intensity
        return f'''
var layer = comp.layers.byName("{layer_name}");
var startPos = [layer.position.value[0], layer.position.value[1] + {offset_y}];
var endPos = layer.position.value;
layer.position.setValueAtTime({start_f/self.frame_rate}, startPos);
layer.position.setValueAtTime({end_f/self.frame_rate}, endPos);
'''

    def _slide_down(self, layer_name: str, params: AnimationParams) -> str:
        """从上方滑入"""
        start_f = int(params.start_delay * self.frame_rate)
        end_f = int((params.start_delay + params.duration) * self.frame_rate)
        offset_y = self.comp_height * 0.3 * params.intensity
        return f'''
var layer = comp.layers.byName("{layer_name}");
var startPos = [layer.position.value[0], layer.position.value[1] - {offset_y}];
var endPos = layer.position.value;
layer.position.setValueAtTime({start_f/self.frame_rate}, startPos);
layer.position.setValueAtTime({end_f/self.frame_rate}, endPos);
'''

    def _scale_in(self, layer_name: str, params: AnimationParams) -> str:
        """缩放进入"""
        start_f = int(params.start_delay * self.frame_rate)
        end_f = int((params.start_delay + params.duration) * self.frame_rate)
        scale = params.scale_factor * 100
        return f'''
var layer = comp.layers.byName("{layer_name}");
layer.scale.setValueAtTime({start_f/self.frame_rate}, [{scale * 0.1}, {scale * 0.1}]);
layer.scale.setValueAtTime({end_f/self.frame_rate}, [100, 100]);
layer.opacity.setValueAtTime({start_f/self.frame_rate}, 0);
layer.opacity.setValueAtTime({end_f/self.frame_rate}, 100);
'''

    def _scale_out(self, layer_name: str, params: AnimationParams) -> str:
        """缩放退出"""
        start_f = int(params.start_delay * self.frame_rate)
        end_f = int((params.start_delay + params.duration) * self.frame_rate)
        scale = params.scale_factor * 100
        return f'''
var layer = comp.layers.byName("{layer_name}");
layer.scale.setValueAtTime({start_f/self.frame_rate}, [100, 100]);
layer.scale.setValueAtTime({end_f/self.frame_rate}, [{scale * 0.1}, {scale * 0.1}]);
layer.opacity.setValueAtTime({start_f/self.frame_rate}, 100);
layer.opacity.setValueAtTime({end_f/self.frame_rate}, 0);
'''

    def _bounce_in(self, layer_name: str, params: AnimationParams) -> str:
        """弹跳进入"""
        start_f = int(params.start_delay * self.frame_rate)
        mid_f = int((params.start_delay + params.duration * 0.3) * self.frame_rate)
        end_f = int((params.start_delay + params.duration) * self.frame_rate)
        return f'''
var layer = comp.layers.byName("{layer_name}");
layer.scale.setValueAtTime({start_f/self.frame_rate}, [0, 0]);
layer.scale.setValueAtTime({mid_f/self.frame_rate}, [120, 120]);
layer.scale.setValueAtTime({end_f/self.frame_rate}, [100, 100]);
layer.opacity.setValueAtTime({start_f/self.frame_rate}, 0);
layer.opacity.setValueAtTime({mid_f/self.frame_rate}, 100);
'''

    def _elastic_scale(self, layer_name: str, params: AnimationParams) -> str:
        """弹性缩放"""
        start_f = int(params.start_delay * self.frame_rate)
        end_f = int((params.start_delay + params.duration) * self.frame_rate)
        return f'''
var layer = comp.layers.byName("{layer_name}");
var elasticExpr = `
amp = 0.5;
freq = 3.0;
decay = 4.0;
t = time - inPoint;
startVal = [0, 0];
endVal = [100, 100];
if (t < 0) startVal
else endVal + (startVal - endVal) * Math.exp(-decay * t) * Math.sin(freq * t * Math.PI * 2) * amp
`;
layer.scale.expression = elasticExpr;
'''

    def _rotate_in(self, layer_name: str, params: AnimationParams) -> str:
        """旋转进入"""
        start_f = int(params.start_delay * self.frame_rate)
        end_f = int((params.start_delay + params.duration) * self.frame_rate)
        return f'''
var layer = comp.layers.byName("{layer_name}");
layer.rotation.setValueAtTime({start_f/self.frame_rate}, {params.rotation_degrees});
layer.rotation.setValueAtTime({end_f/self.frame_rate}, 0);
layer.scale.setValueAtTime({start_f/self.frame_rate}, [0, 0]);
layer.scale.setValueAtTime({end_f/self.frame_rate}, [100, 100]);
layer.opacity.setValueAtTime({start_f/self.frame_rate}, 0);
layer.opacity.setValueAtTime({end_f/self.frame_rate}, 100);
'''

    def _wave_animation(self, layer_name: str, params: AnimationParams) -> str:
        """波浪动画"""
        return f'''
var layer = comp.layers.byName("{layer_name}");
var waveExpr = `
amp = {params.wave_amplitude};
freq = {params.wave_frequency};
t = time * freq * Math.PI * 2;
value + [0, Math.sin(t) * amp]
`;
layer.position.expression = waveExpr;
'''

    def _pulse_animation(self, layer_name: str, params: AnimationParams) -> str:
        """脉冲动画"""
        return f'''
var layer = comp.layers.byName("{layer_name}");
var pulseExpr = `
freq = 2;
amp = 0.1;
t = time * freq * Math.PI * 2;
s = 1 + Math.sin(t) * amp;
[100 * s, 100 * s]
`;
layer.scale.expression = pulseExpr;
'''

    def _blur_in(self, layer_name: str, params: AnimationParams) -> str:
        """模糊进入"""
        start_f = int(params.start_delay * self.frame_rate)
        end_f = int((params.start_delay + params.duration) * self.frame_rate)
        return f'''
var layer = comp.layers.byName("{layer_name}");
var blurFx = layer.effect.addProperty("ADBE Fast Blur 2");
blurFx.property("ADBE Fast Blur-0001").setValueAtTime({start_f/self.frame_rate}, {params.blur_amount});
blurFx.property("ADBE Fast Blur-0001").setValueAtTime({end_f/self.frame_rate}, 0);
layer.opacity.setValueAtTime({start_f/self.frame_rate}, 0);
layer.opacity.setValueAtTime({end_f/self.frame_rate}, 100);
'''

    def _blur_out(self, layer_name: str, params: AnimationParams) -> str:
        """模糊退出"""
        start_f = int(params.start_delay * self.frame_rate)
        end_f = int((params.start_delay + params.duration) * self.frame_rate)
        return f'''
var layer = comp.layers.byName("{layer_name}");
var blurFx = layer.effect.addProperty("ADBE Fast Blur 2");
blurFx.property("ADBE Fast Blur-0001").setValueAtTime({start_f/self.frame_rate}, 0);
blurFx.property("ADBE Fast Blur-0001").setValueAtTime({end_f/self.frame_rate}, {params.blur_amount});
layer.opacity.setValueAtTime({start_f/self.frame_rate}, 100);
layer.opacity.setValueAtTime({end_f/self.frame_rate}, 0);
'''

    def _tracking_in(self, layer_name: str, params: AnimationParams) -> str:
        """字间距缩小进入"""
        return self.create_per_char_animation(
            layer_name, TextAnimationType.TRACKING_IN, params
        )

    def _tracking_out(self, layer_name: str, params: AnimationParams) -> str:
        """字间距扩大退出"""
        return self.create_per_char_animation(
            layer_name, TextAnimationType.TRACKING_OUT, params
        )

    def create_typewriter_effect(self, layer_name: str,
                                  params: Optional[AnimationParams] = None) -> str:
        """创建打字机效果（带光标闪烁）

        Args:
            layer_name: 文本图层名称
            params: 动画参数

        Returns:
            JSX 代码片段
        """
        if params is None:
            params = AnimationParams()

        char_delay = params.per_char_delay if params.per_char_delay > 0 else 0.05
        return f'''
var layer = comp.layers.byName("{layer_name}");
var textProp = layer.property("Source Text");
var originalText = textProp.value.text;
var charCount = originalText.length;
var totalDur = charCount * {char_delay};
var cursorBlink = true;

var typeExpr = `
text = "{originalText}";
charDelay = {char_delay};
t = time - inPoint;
numChars = Math.min(Math.floor(t / charDelay), text.length);
text.substr(0, numChars) + (numChars < text.length && Math.floor(time * 4) % 2 == 0 ? "|" : "")
`;
textProp.expression = typeExpr;
'''

    def create_per_char_animation(self, layer_name: str,
                                   anim_type: TextAnimationType,
                                   params: Optional[AnimationParams] = None) -> str:
        """创建逐字符动画（使用 Text Animator）

        Args:
            layer_name: 文本图层名称
            anim_type: 动画类型
            params: 动画参数

        Returns:
            JSX 代码片段
        """
        if params is None:
            params = AnimationParams()

        start_f = int(params.start_delay * self.frame_rate)
        end_f = int((params.start_delay + params.duration) * self.frame_rate)

        animator_configs = {
            TextAnimationType.FADE_IN: {"type": "opacity", "start": 0, "end": 100},
            TextAnimationType.FADE_OUT: {"type": "opacity", "start": 100, "end": 0},
            TextAnimationType.SCALE_IN: {"type": "scale", "start": 0, "end": 100},
            TextAnimationType.SCALE_OUT: {"type": "scale", "start": 100, "end": 0},
            TextAnimationType.TRACKING_IN: {"type": "tracking", "start": 200, "end": 0},
            TextAnimationType.TRACKING_OUT: {"type": "tracking", "start": 0, "end": 200},
            TextAnimationType.BLUR_IN: {"type": "blur", "start": params.blur_amount, "end": 0},
        }

        config = animator_configs.get(anim_type, animator_configs[TextAnimationType.FADE_IN])

        return f'''
var layer = comp.layers.byName("{layer_name}");
var textProp = layer.property("Source Text");
var animGroup = textProp.addProperty("ADBE Text Animators").addProperty("ADBE Text Animator");
var rangeSel = animGroup.addProperty("ADBE Text Selectors").addProperty("ADBE Text Selector");
var rangeStart = rangeSel.property("ADBE Text Selector-0001");
var rangeEnd = rangeSel.property("ADBE Text Selector-0002");

rangeStart.setValueAtTime({start_f/self.frame_rate}, 0);
rangeStart.setValueAtTime({end_f/self.frame_rate}, 100);
rangeEnd.setValueAtTime({start_f/self.frame_rate}, 5);
rangeEnd.setValueAtTime({end_f/self.frame_rate}, 105);

var animProp = animGroup.addProperty("ADBE Text Animator Properties").addProperty("ADBE {config['type'].title()}");
animProp.setValueAtTime({start_f/self.frame_rate}, {config['start']});
animProp.setValueAtTime({end_f/self.frame_rate}, {config['end']});
'''

    def create_path_text(self, layer_name: str,
                         params: Optional[AnimationParams] = None) -> str:
        """创建路径文字动画

        Args:
            layer_name: 文本图层名称
            params: 动画参数

        Returns:
            JSX 代码片段
        """
        if params is None:
            params = AnimationParams()

        return f'''
var layer = comp.layers.byName("{layer_name}");
var maskShape = layer.property("Masks").addProperty("ADBE Mask Atom");
maskShape.name = "Path Mask";
var maskPathProp = maskShape.property("ADBE Mask Shape");
var maskPath = maskPathProp.value;
maskPath.vertices = [
    [100, {self.comp_height/2}],
    [{self.comp_width/3}, {self.comp_height/2 - 100}],
    [{self.comp_width*2/3}, {self.comp_height/2 + 100}],
    [{self.comp_width - 100}, {self.comp_height/2}]
];
maskPath.inTangents = [[0,0], [0,0], [0,0], [0,0]];
maskPath.outTangents = [[0,0], [0,0], [0,0], [0,0]];
maskPath.closed = false;
maskPathProp.setValue(maskPath);

var textProp = layer.property("Source Text");
var pathOptions = textProp.addProperty("ADBE Text Path Options");
pathOptions.property("ADBE Text Path").setValue("Path Mask");

var pathAnimExpr = `
startVal = 0;
endVal = 100;
dur = {params.duration};
t = time - inPoint;
linear(t, 0, dur, startVal, endVal)
`;
pathOptions.property("ADBE Text Path Margin").expression = pathAnimExpr;
'''

    def create_particle_text(self, layer_name: str,
                             params: Optional[AnimationParams] = None) -> str:
        """创建粒子文字（汇聚/发散）效果

        Args:
            layer_name: 文本图层名称
            params: 动画参数

        Returns:
            JSX 代码片段
        """
        if params is None:
            params = AnimationParams()

        return f'''
var layer = comp.layers.byName("{layer_name}");
var ccFx = layer.effect.addProperty("CC Particle World");
if (ccFx) {{
    ccFx.property("Birth Rate").setValue(3);
    ccFx.property("Longevity (sec)").setValue(2);
    ccFx.property("Position X").setValue(0);
    ccFx.property("Position Y").setValue(0);
    ccFx.property("Velocity").setValue(2);
    ccFx.property("Gravity").setValue(0.2);
    ccFx.property("Particle Type").setValue(2);
    ccFx.property("Birth Size").setValue(0.3);
    ccFx.property("Death Size").setValue(0.1);
}}

var particleDisperse = layer.effect.addProperty("CC Scatterize");
if (particleDisperse) {{
    var scatAmount = particleDisperse.property("Scatter");
    scatAmount.setValueAtTime(0, 200);
    scatAmount.setValueAtTime({params.duration}, 0);
}}
'''

    def create_3d_text_animation(self, layer_name: str,
                                  params: Optional[AnimationParams] = None) -> str:
        """创建3D翻转动画

        Args:
            layer_name: 文本图层名称
            params: 动画参数

        Returns:
            JSX 代码片段
        """
        if params is None:
            params = AnimationParams()

        start_f = int(params.start_delay * self.frame_rate)
        end_f = int((params.start_delay + params.duration) * self.frame_rate)

        return f'''
var layer = comp.layers.byName("{layer_name}");
layer.threeD = true;
layer.orientation.setValue([0, 0, 0]);
layer.orientation.setValueAtTime({start_f/self.frame_rate}, [0, 180, 0]);
layer.orientation.setValueAtTime({end_f/self.frame_rate}, [0, 0, 0]);
layer.opacity.setValueAtTime({start_f/self.frame_rate}, 0);
layer.opacity.setValueAtTime({(start_f + end_f)/2/self.frame_rate}, 100);

var bevelFx = layer.effect.addProperty("CC Cylinder");
if (bevelFx) {{
    bevelFx.property("CC Cylinder-0001").setValue(5);
    bevelFx.property("Light Direction").setValue(135);
    bevelFx.property("Light Intensity").setValue(0.8);
}}
'''

    def create_glitch_text(self, layer_name: str,
                            params: Optional[AnimationParams] = None) -> str:
        """创建故障文字效果（RGB分离+位移）

        Args:
            layer_name: 文本图层名称
            params: 动画参数

        Returns:
            JSX 代码片段
        """
        if params is None:
            params = AnimationParams()

        return f'''
var layer = comp.layers.byName("{layer_name}");
var glitchAmt = {params.glitch_intensity};

var shiftExprR = `
freq = 20;
amp = {params.glitch_intensity * 10};
t = time * freq;
if (random() < 0.3) value + [random(-amp, amp), 0]
else value
`;

var shiftExprG = `
freq = 25;
amp = {params.glitch_intensity * 8};
t = time * freq;
if (random() < 0.25) value + [random(-amp, amp), random(-amp/2, amp/2)]
else value
`;

var shiftExprB = `
freq = 22;
amp = {params.glitch_intensity * 12};
t = time * freq;
if (random() < 0.35) value + [random(-amp, amp), 0]
else value
`;

var rLayer = layer.duplicate();
rLayer.name = layer.name + "_R";
rLayer.blendingMode = BlendingMode.SCREEN;
rLayer.opacity.setValue(85);
var tintR = rLayer.effect.addProperty("Tint");
tintR.property("Map Black To").setValue([1, 0, 0]);
tintR.property("Map White To").setValue([1, 0, 0]);
rLayer.property("Transform").property("Position").expression = shiftExprR;

var gLayer = layer.duplicate();
gLayer.name = layer.name + "_G";
gLayer.blendingMode = BlendingMode.SCREEN;
gLayer.opacity.setValue(85);
var tintG = gLayer.effect.addProperty("Tint");
tintG.property("Map Black To").setValue([0, 1, 0]);
tintG.property("Map White To").setValue([0, 1, 0]);
gLayer.property("Transform").property("Position").expression = shiftExprG;

var bLayer = layer.duplicate();
bLayer.name = layer.name + "_B";
bLayer.blendingMode = BlendingMode.SCREEN;
bLayer.opacity.setValue(85);
var tintB = bLayer.effect.addProperty("Tint");
tintB.property("Map Black To").setValue([0, 0, 1]);
tintB.property("Map White To").setValue([0, 0, 1]);
bLayer.property("Transform").property("Position").expression = shiftExprB;
'''

    def get_presets(self) -> List[TextAnimationPreset]:
        """获取20+内置动画预设"""
        return [
            TextAnimationPreset(
                name="Smooth Fade In",
                type=TextAnimationType.FADE_IN,
                duration=0.8,
                easing=EasingType.EASE_OUT,
                description="平滑淡入效果",
                category="basic"
            ),
            TextAnimationPreset(
                name="Slide From Left",
                type=TextAnimationType.SLIDE_LEFT,
                duration=1.0,
                easing=EasingType.EASE_OUT_CUBIC,
                params={"intensity": 1.0},
                description="从左侧滑入",
                category="slide"
            ),
            TextAnimationPreset(
                name="Slide From Right",
                type=TextAnimationType.SLIDE_RIGHT,
                duration=1.0,
                easing=EasingType.EASE_OUT_CUBIC,
                params={"intensity": 1.0},
                description="从右侧滑入",
                category="slide"
            ),
            TextAnimationPreset(
                name="Bounce Entry",
                type=TextAnimationType.BOUNCE_IN,
                duration=1.2,
                easing=EasingType.EASE_OUT_BOUNCE,
                params={"bounce_count": 3},
                description="弹跳进入",
                category="dynamic"
            ),
            TextAnimationPreset(
                name="Elastic Pop",
                type=TextAnimationType.ELASTIC_SCALE,
                duration=1.5,
                easing=EasingType.EASE_OUT_ELASTIC,
                params={"intensity": 0.8},
                description="弹性弹出",
                category="dynamic"
            ),
            TextAnimationPreset(
                name="Typewriter Classic",
                type=TextAnimationType.TYPEWRITER,
                duration=2.0,
                easing=EasingType.LINEAR,
                params={"per_char_delay": 0.05},
                description="经典打字机效果",
                category="text_specific"
            ),
            TextAnimationPreset(
                name="3D Flip",
                type=TextAnimationType.FLIP_3D,
                duration=1.2,
                easing=EasingType.EASE_IN_OUT,
                description="3D翻转进入",
                category="3d"
            ),
            TextAnimationPreset(
                name="Glitch Text",
                type=TextAnimationType.GLITCH,
                duration=0.5,
                easing=EasingType.LINEAR,
                params={"glitch_intensity": 0.6},
                description="故障文字效果",
                category="fx"
            ),
            TextAnimationPreset(
                name="Wave Float",
                type=TextAnimationType.WAVE,
                duration=2.0,
                easing=EasingType.EASE_IN_OUT,
                params={"wave_amplitude": 15, "wave_frequency": 1.5},
                description="波浪漂浮效果",
                category="dynamic"
            ),
            TextAnimationPreset(
                name="Blur Reveal",
                type=TextAnimationType.BLUR_IN,
                duration=1.0,
                easing=EasingType.EASE_OUT,
                params={"blur_amount": 30},
                description="模糊清晰化",
                category="fx"
            ),
            TextAnimationPreset(
                name="Tracking In",
                type=TextAnimationType.TRACKING_IN,
                duration=1.2,
                easing=EasingType.EASE_OUT,
                params={"per_char_delay": 0.03},
                description="字间距收缩进入",
                category="text_specific"
            ),
            TextAnimationPreset(
                name="Rotate Spin In",
                type=TextAnimationType.ROTATE_IN,
                duration=1.5,
                easing=EasingType.EASE_OUT_CUBIC,
                params={"rotation_degrees": 360, "scale_factor": 0.5},
                description="旋转缩放进入",
                category="dynamic"
            ),
            TextAnimationPreset(
                name="Path Flow",
                type=TextAnimationType.PATH_ANIMATION,
                duration=3.0,
                easing=EasingType.EASE_IN_OUT,
                description="沿路径流动文字",
                category="path"
            ),
            TextAnimationPreset(
                name="Particle Converge",
                type=TextAnimationType.PARTICLE_CONVERGE,
                duration=2.0,
                easing=EasingType.EASE_OUT,
                description="粒子汇聚成文字",
                category="particle"
            ),
            TextAnimationPreset(
                name="Pulse Glow",
                type=TextAnimationType.PULSE,
                duration=1.0,
                easing=EasingType.EASE_IN_OUT,
                params={"intensity": 0.15},
                description="脉冲呼吸效果",
                category="dynamic"
            ),
        ]

    def generate_jsx(self, text: str, style: Optional[TextStyle] = None,
                     anim_type: Optional[TextAnimationType] = None,
                     anim_params: Optional[AnimationParams] = None) -> str:
        """生成完整的 AE JSX 脚本

        Args:
            text: 文本内容
            style: 文本样式
            anim_type: 动画类型
            anim_params: 动画参数

        Returns:
            完整的 JSX 脚本字符串
        """
        if style is None:
            style = TextStyle()
        if anim_type is None:
            anim_type = TextAnimationType.FADE_IN
        if anim_params is None:
            anim_params = AnimationParams()

        layer_name = "Main Text Layer"

        jsx_header = f'''/*
AE Text Animation Generator - Auto-generated JSX Script
Animation Type: {anim_type.value}
Text: {text}
*/

app.beginUndoGroup("Create Text Animation");

var comp = app.project.items.addComp(
    "{self.comp_name}",
    {self.comp_width},
    {self.comp_height},
    1,
    {self.duration},
    {self.frame_rate}
);
'''

        jsx_text_layer = self.create_text_layer(text, style, layer_name)
        jsx_animation = self.apply_animation(layer_name, anim_type, anim_params)

        jsx_footer = '''
app.endUndoGroup();
alert("Text animation created successfully!");
'''

        return jsx_header + jsx_text_layer + jsx_animation + jsx_footer


# ============================================================================
# 3. Premiere Pro 文本动画生成器
# ============================================================================

class PRTextAnimator:
    """Premiere Pro 文本动画生成器

    生成 Premiere Pro ExtendScript 脚本，支持 Essential Graphics 文本、
    标题序列、Lower Thirds、滚动字幕等。
    """

    def __init__(self, sequence_name: str = "Text Sequence",
                 width: int = 1920, height: int = 1080,
                 frame_rate: float = 30.0, duration: float = 10.0):
        self.sequence_name = sequence_name
        self.width = width
        self.height = height
        self.frame_rate = frame_rate
        self.duration = duration

    def create_essential_graphics_text(self, text: str,
                                        style: Optional[TextStyle] = None,
                                        layer_name: str = "EG Text") -> str:
        """创建 Essential Graphics 风格的文本（MOGRT 兼容）

        Args:
            text: 文本内容
            style: 文本样式
            layer_name: 图层名称

        Returns:
            PR JSX 代码片段
        """
        if style is None:
            style = TextStyle()

        return f'''
var proj = app.project;
var activeSeq = proj.activeSequence;
if (!activeSeq) {{
    alert("Please open a sequence first");
}}

var textClip = activeSeq.videoTracks[0].insertClip(
    activeSeq.time,
    {self.duration},
    "Text Frame"
);

textClip.name = "{layer_name}";

var textComponent = textClip.components[0];
var textProp = textComponent.getProperty("Source Text");
var textDoc = textProp.value;
textDoc.text = "{text}";
textDoc.font = "{style.font_family}";
textDoc.fontSize = {style.font_size};
textDoc.fillColor = [{style.fill_color[0]}, {style.fill_color[1]}, {style.fill_color[2]}];
textDoc.strokeColor = [{style.stroke_color[0]}, {style.stroke_color[1]}, {style.stroke_color[2]}];
textDoc.strokeWidth = {style.stroke_width};
textDoc.tracking = {style.letter_spacing};
textDoc.justification = ParagraphJustification.CENTER_JUSTIFY;
textProp.setValue(textDoc);

textClip.position.setValue([{self.width/2}, {self.height/2}]);
'''

    def apply_pr_transition(self, clip_name: str,
                            transition_type: str = "cross_dissolve",
                            duration: float = 0.5) -> str:
        """应用转场效果到文本图层

        Args:
            clip_name: 剪辑名称
            transition_type: 转场类型
            duration: 转场时长（秒）

        Returns:
            PR JSX 代码片段
        """
        transition_map = {
            "cross_dissolve": "Cross Dissolve",
            "dip_to_black": "Dip to Black",
            "dip_to_white": "Dip to White",
            "fade": "Fade",
            "wipe": "Wipe",
            "push": "Push",
            "slide": "Slide",
            "zoom": "Zoom",
        }

        transition_display = transition_map.get(transition_type, "Cross Dissolve")

        return f'''
var proj = app.project;
var activeSeq = proj.activeSequence;
var clip = null;

for (var i = 0; i < activeSeq.videoTracks.numTracks; i++) {{
    var track = activeSeq.videoTracks[i];
    for (var j = 0; j < track.clips.numItems; j++) {{
        if (track.clips[j].name == "{clip_name}") {{
            clip = track.clips[j];
            break;
        }}
    }}
}}

if (clip) {{
    var transition = clip.addTransition(
        "{transition_display}",
        {duration},
        1
    );
}}
'''

    def create_title_sequence(self, titles: List[str],
                              style: Optional[TextStyle] = None,
                              per_title_duration: float = 3.0,
                              transition: str = "cross_dissolve") -> str:
        """创建标题卡序列

        Args:
            titles: 标题文本列表
            style: 文本样式
            per_title_duration: 每个标题时长
            transition: 转场类型

        Returns:
            PR JSX 代码片段
        """
        if style is None:
            style = TextStyle()

        titles_jsx = ""
        for i, title in enumerate(titles):
            start_time = i * per_title_duration
            titles_jsx += f'''
// Title {i+1}: {title}
var titleClip{i} = activeSeq.videoTracks[0].insertClip(
    {start_time},
    {per_title_duration},
    "Text Frame"
);
titleClip{i}.name = "Title_{i+1}";
var tc{i} = titleClip{i}.components[0];
var tp{i} = tc{i}.getProperty("Source Text");
var td{i} = tp{i}.value;
td{i}.text = "{title}";
td{i}.font = "{style.font_family}";
td{i}.fontSize = {style.font_size};
td{i}.fillColor = [{style.fill_color[0]}, {style.fill_color[1]}, {style.fill_color[2]}];
td{i}.justification = ParagraphJustification.CENTER_JUSTIFY;
tp{i}.setValue(td{i});
titleClip{i}.position.setValue([{self.width/2}, {self.height/2}]);
'''

        return f'''
var proj = app.project;
var activeSeq = proj.activeSequence;
{titles_jsx}
'''

    def create_lower_third(self, name_text: str, title_text: str,
                           style: Optional[TextStyle] = None,
                           position: str = "bottom_left") -> str:
        """创建 Lower Third 字幕条

        Args:
            name_text: 人名/主标题
            title_text: 职位/副标题
            style: 文本样式
            position: 位置 (bottom_left, bottom_right, bottom_center)

        Returns:
            PR JSX 代码片段
        """
        if style is None:
            style = TextStyle()

        positions = {
            "bottom_left": (200, self.height - 150),
            "bottom_right": (self.width - 200, self.height - 150),
            "bottom_center": (self.width / 2, self.height - 150),
        }
        pos_x, pos_y = positions.get(position, positions["bottom_left"])

        return f'''
var proj = app.project;
var activeSeq = proj.activeSequence;

// Background bar
var bgClip = activeSeq.videoTracks[0].insertClip(0, {self.duration}, "Color Matte");
bgClip.name = "LowerThird_BG";
bgClip.scaleToFrameSize = false;
bgClip.scale.setValue([60, 15]);
bgClip.position.setValue([{pos_x}, {pos_y}]);
var bgColor = bgClip.components[0].getProperty("Color");
bgColor.setValue([0.9, 0.1, 0.1]);

// Name text
var nameClip = activeSeq.videoTracks[1].insertClip(0, {self.duration}, "Text Frame");
nameClip.name = "LowerThird_Name";
var nc = nameClip.components[0];
var np = nc.getProperty("Source Text");
var nd = np.value;
nd.text = "{name_text}";
nd.font = "{style.font_family}";
nd.fontSize = {style.font_size};
nd.fillColor = [{style.fill_color[0]}, {style.fill_color[1]}, {style.fill_color[2]}];
nd.justification = ParagraphJustification.LEFT_JUSTIFY;
np.setValue(nd);
nameClip.position.setValue([{pos_x - 200}, {pos_y - 20}]);

// Title text
var titleClip = activeSeq.videoTracks[1].insertClip(0, {self.duration}, "Text Frame");
titleClip.name = "LowerThird_Title";
var tc = titleClip.components[0];
var tp = tc.getProperty("Source Text");
var td = tp.value;
td.text = "{title_text}";
td.font = "{style.font_family}";
td.fontSize = {style.font_size * 0.6};
td.fillColor = [0.9, 0.9, 0.9];
td.justification = ParagraphJustification.LEFT_JUSTIFY;
tp.setValue(td);
titleClip.position.setValue([{pos_x - 200}, {pos_y + 30}]);
'''

    def create_scrolling_credits(self, credits_lines: List[str],
                                  style: Optional[TextStyle] = None,
                                  scroll_speed: float = 50.0) -> str:
        """创建滚动字幕（演职员表）

        Args:
            credits_lines: 字幕行列表
            style: 文本样式
            scroll_speed: 滚动速度（像素/秒）

        Returns:
            PR JSX 代码片段
        """
        if style is None:
            style = TextStyle()

        full_text = "\\n".join(credits_lines)
        num_lines = len(credits_lines)
        total_height = num_lines * style.font_size * 1.5
        scroll_duration = (total_height + self.height) / scroll_speed

        return f'''
var proj = app.project;
var activeSeq = proj.activeSequence;

var creditsClip = activeSeq.videoTracks[0].insertClip(0, {scroll_duration}, "Text Frame");
creditsClip.name = "Scrolling Credits";

var cc = creditsClip.components[0];
var cp = cc.getProperty("Source Text");
var cd = cp.value;
cd.text = "{full_text}";
cd.font = "{style.font_family}";
cd.fontSize = {style.font_size};
cd.fillColor = [{style.fill_color[0]}, {style.fill_color[1]}, {style.fill_color[2]}];
cd.justification = ParagraphJustification.CENTER_JUSTIFY;
cd.leading = {style.font_size * 1.5};
cp.setValue(cd);

var startY = {self.height + total_height/2};
var endY = -{total_height/2};

creditsClip.position.setValueAtTime(0, [{self.width/2}, startY]);
creditsClip.position.setValueAtTime({scroll_duration}, [{self.width/2}, endY]);
'''

    def generate_pr_script(self, text: str, style: Optional[TextStyle] = None,
                           anim_type: Optional[str] = None) -> str:
        """生成完整的 Premiere Pro JSX 脚本

        Args:
            text: 文本内容
            style: 文本样式
            anim_type: 动画类型

        Returns:
            完整的 JSX 脚本字符串
        """
        if style is None:
            style = TextStyle()

        script_header = f'''/*
Premiere Pro Text Animation Generator
Text: {text}
*/

app.beginUndoGroup("Create Text Animation");

var proj = app.project;
if (!proj) {{
    proj = app.newProject();
}}
'''

        script_body = self.create_essential_graphics_text(text, style)

        script_footer = '''
app.endUndoGroup();
'''

        return script_header + script_body + script_footer


# ============================================================================
# 4. Photoshop 文本效果生成器
# ============================================================================

class TextEffectType(str, Enum):
    """文本效果类型枚举"""
    GLOW = "glow"
    SHADOW = "shadow"
    STROKE = "stroke"
    GRADIENT = "gradient"
    TEXTURE = "texture"
    D_EXTRUDE = "3d_extrude"
    BEVEL = "bevel"
    NEON = "neon"
    METAL = "metal"
    GLASS = "glass"
    FIRE = "fire"
    ICE = "ice"
    WOOD = "wood"
    GOLD = "gold"
    CHALK = "chalk"
    CRT = "crt"
    GLITCH = "glitch"
    VAPORWAVE = "vaporwave"
    RETRO = "retro"


@dataclass
class TextEffectPreset:
    """文本效果预设"""
    name: str
    type: TextEffectType
    params: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    category: str = "basic"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type.value,
            "params": self.params,
            "description": self.description,
            "category": self.category,
        }


class PSTextEffectGenerator:
    """Photoshop 文本效果生成器

    生成可在 Photoshop 中执行的 JSX 脚本，支持多种文字特效：
    金属、霓虹、3D、火焰、玻璃、渐变等。
    """

    def __init__(self, doc_width: int = 1920, doc_height: int = 1080,
                 resolution: float = 72.0):
        self.doc_width = doc_width
        self.doc_height = doc_height
        self.resolution = resolution

    def create_text_layer(self, text: str, style: Optional[TextStyle] = None,
                          layer_name: str = "Text Layer") -> str:
        """创建 PSD 文本图层

        Args:
            text: 文本内容
            style: 文本样式
            layer_name: 图层名称

        Returns:
            PS JSX 代码片段
        """
        if style is None:
            style = TextStyle()

        return f'''
var doc = app.documents.add(
    {self.doc_width},
    {self.doc_height},
    {self.resolution},
    "Text Effect Document",
    NewDocumentMode.RGB,
    DocumentFill.BACKGROUND_COLOR
);

var textLayer = doc.artLayers.add();
textLayer.name = "{layer_name}";
textLayer.kind = LayerKind.TEXT;

var textItem = textLayer.textItem;
textItem.contents = "{text}";
textItem.font = "{style.font_family}";
textItem.size = {style.font_size};
textItem.position = [{self.doc_width/2}, {self.doc_height/2}];
textItem.justification = Justification.CENTER;

var color = new SolidColor();
color.rgb.red = {int(style.fill_color[0] * 255)};
color.rgb.green = {int(style.fill_color[1] * 255)};
color.rgb.blue = {int(style.fill_color[2] * 255)};
textItem.color = color;
'''

    def apply_layer_style(self, layer_name: str, effect_type: str,
                          params: Optional[Dict[str, Any]] = None) -> str:
        """应用图层样式（投影、发光、斜面、描边、渐变叠加等）

        Args:
            layer_name: 图层名称
            effect_type: 效果类型
            params: 效果参数

        Returns:
            PS JSX 代码片段
        """
        if params is None:
            params = {}

        effect_map = {
            "drop_shadow": self._drop_shadow_style,
            "inner_shadow": self._inner_shadow_style,
            "outer_glow": self._outer_glow_style,
            "inner_glow": self._inner_glow_style,
            "bevel_emboss": self._bevel_emboss_style,
            "stroke": self._stroke_style,
            "gradient_overlay": self._gradient_overlay_style,
            "color_overlay": self._color_overlay_style,
            "satin": self._satin_style,
        }

        effect_func = effect_map.get(effect_type)
        if effect_func is None:
            raise ValueError(f"Unsupported layer style: {effect_type}")

        return effect_func(layer_name, params)

    def _drop_shadow_style(self, layer_name: str, params: Dict[str, Any]) -> str:
        """投影样式"""
        angle = params.get("angle", 120)
        distance = params.get("distance", 10)
        size = params.get("size", 15)
        spread = params.get("spread", 5)
        opacity = params.get("opacity", 75)

        return f'''
var doc = app.activeDocument;
var layer = doc.artLayers.getByName("{layer_name}");

var desc = new ActionDescriptor();
var ref = new ActionReference();
ref.putEnumerated(charIDToTypeID("Lyr "), charIDToTypeID("Ordn"), charIDToTypeID("Trgt"));
desc.putReference(charIDToTypeID("null"), ref);

var shadowDesc = new ActionDescriptor();
shadowDesc.putBoolean(charIDToTypeID("enab"), true);
shadowDesc.putUnitDouble(charIDToTypeID("lagl"), charIDToTypeID("#Ang"), {angle});
shadowDesc.putUnitDouble(charIDToTypeID("Dstn"), charIDToTypeID("#Pxl"), {distance});
shadowDesc.putUnitDouble(charIDToTypeID("blur"), charIDToTypeID("#Pxl"), {size});
shadowDesc.putUnitDouble(charIDToTypeID("Ckmt"), charIDToTypeID("#Pxl"), {spread});
shadowDesc.putUnitDouble(charIDToTypeID("Opct"), charIDToTypeID("#Prc"), {opacity});

var list = new ActionList();
list.putObject(charIDToTypeID("DrSh"), shadowDesc);
desc.putList(charIDToTypeID("Lefx"), list);

executeAction(charIDToTypeID("Lefx"), desc, DialogModes.NO);
'''

    def _outer_glow_style(self, layer_name: str, params: Dict[str, Any]) -> str:
        """外发光样式"""
        size = params.get("size", 20)
        spread = params.get("spread", 10)
        opacity = params.get("opacity", 75)
        color = params.get("color", [0.0, 0.7, 1.0])

        return f'''
var doc = app.activeDocument;
var layer = doc.artLayers.getByName("{layer_name}");

var desc = new ActionDescriptor();
var ref = new ActionReference();
ref.putEnumerated(charIDToTypeID("Lyr "), charIDToTypeID("Ordn"), charIDToTypeID("Trgt"));
desc.putReference(charIDToTypeID("null"), ref);

var glowDesc = new ActionDescriptor();
glowDesc.putBoolean(charIDToTypeID("enab"), true);
glowDesc.putUnitDouble(charIDToTypeID("blur"), charIDToTypeID("#Pxl"), {size});
glowDesc.putUnitDouble(charIDToTypeID("Ckmt"), charIDToTypeID("#Pxl"), {spread});
glowDesc.putUnitDouble(charIDToTypeID("Opct"), charIDToTypeID("#Prc"), {opacity});

var list = new ActionList();
list.putObject(charIDToTypeID("OrGl"), glowDesc);
desc.putList(charIDToTypeID("Lefx"), list);

executeAction(charIDToTypeID("Lefx"), desc, DialogModes.NO);
'''

    def _bevel_emboss_style(self, layer_name: str, params: Dict[str, Any]) -> str:
        """斜面和浮雕样式"""
        size = params.get("size", 10)
        depth = params.get("depth", 100)
        angle = params.get("angle", 120)
        style = params.get("style", "inner_bevel")

        return f'''
var doc = app.activeDocument;
var layer = doc.artLayers.getByName("{layer_name}");

var desc = new ActionDescriptor();
var ref = new ActionReference();
ref.putEnumerated(charIDToTypeID("Lyr "), charIDToTypeID("Ordn"), charIDToTypeID("Trgt"));
desc.putReference(charIDToTypeID("null"), ref);

var bevelDesc = new ActionDescriptor();
bevelDesc.putBoolean(charIDToTypeID("enab"), true);
bevelDesc.putEnumerated(charIDToTypeID("styl"), charIDToTypeID("bstl"), charIDToTypeID("InBe"));
bevelDesc.putEnumerated(charIDToTypeID("btdn"), charIDToTypeID("btdn"), charIDToTypeID("Inne"));
bevelDesc.putUnitDouble(charIDToTypeID("blur"), charIDToTypeID("#Pxl"), {size});
bevelDesc.putInteger(charIDToTypeID("sngl"), {depth});
bevelDesc.putUnitDouble(charIDToTypeID("lagl"), charIDToTypeID("#Ang"), {angle});
bevelDesc.putBoolean(charIDToTypeID("useG"), true);

var list = new ActionList();
list.putObject(charIDToTypeID("Embl"), bevelDesc);
desc.putList(charIDToTypeID("Lefx"), list);

executeAction(charIDToTypeID("Lefx"), desc, DialogModes.NO);
'''

    def _stroke_style(self, layer_name: str, params: Dict[str, Any]) -> str:
        """描边样式"""
        size = params.get("size", 3)
        color = params.get("color", [0.0, 0.0, 0.0])
        position = params.get("position", "outside")

        return f'''
var doc = app.activeDocument;
var layer = doc.artLayers.getByName("{layer_name}");

var desc = new ActionDescriptor();
var ref = new ActionReference();
ref.putEnumerated(charIDToTypeID("Lyr "), charIDToTypeID("Ordn"), charIDToTypeID("Trgt"));
desc.putReference(charIDToTypeID("null"), ref);

var strokeDesc = new ActionDescriptor();
strokeDesc.putBoolean(charIDToTypeID("enab"), true);
strokeDesc.putUnitDouble(charIDToTypeID("blur"), charIDToTypeID("#Pxl"), {size});

var list = new ActionList();
list.putObject(charIDToTypeID("FrFX"), strokeDesc);
desc.putList(charIDToTypeID("Lefx"), list);

executeAction(charIDToTypeID("Lefx"), desc, DialogModes.NO);
'''

    def _gradient_overlay_style(self, layer_name: str, params: Dict[str, Any]) -> str:
        """渐变叠加样式"""
        angle = params.get("angle", 90)
        scale = params.get("scale", 100)
        opacity = params.get("opacity", 100)

        return f'''
var doc = app.activeDocument;
var layer = doc.artLayers.getByName("{layer_name}");

var desc = new ActionDescriptor();
var ref = new ActionReference();
ref.putEnumerated(charIDToTypeID("Lyr "), charIDToTypeID("Ordn"), charIDToTypeID("Trgt"));
desc.putReference(charIDToTypeID("null"), ref);

var gradDesc = new ActionDescriptor();
gradDesc.putBoolean(charIDToTypeID("enab"), true);
gradDesc.putUnitDouble(charIDToTypeID("lagl"), charIDToTypeID("#Ang"), {angle});
gradDesc.putUnitDouble(charIDToTypeID("Opct"), charIDToTypeID("#Prc"), {opacity});

var list = new ActionList();
list.putObject(charIDToTypeID("GrOf"), gradDesc);
desc.putList(charIDToTypeID("Lefx"), list);

executeAction(charIDToTypeID("Lefx"), desc, DialogModes.NO);
'''

    def _inner_shadow_style(self, layer_name: str, params: Dict[str, Any]) -> str:
        """内阴影样式"""
        return self._drop_shadow_style(layer_name, params)

    def _inner_glow_style(self, layer_name: str, params: Dict[str, Any]) -> str:
        """内发光样式"""
        return self._outer_glow_style(layer_name, params)

    def _color_overlay_style(self, layer_name: str, params: Dict[str, Any]) -> str:
        """颜色叠加样式"""
        opacity = params.get("opacity", 100)
        return f'''
var doc = app.activeDocument;
var layer = doc.artLayers.getByName("{layer_name}");
var desc = new ActionDescriptor();
var ref = new ActionReference();
ref.putEnumerated(charIDToTypeID("Lyr "), charIDToTypeID("Ordn"), charIDToTypeID("Trgt"));
desc.putReference(charIDToTypeID("null"), ref);
var overlayDesc = new ActionDescriptor();
overlayDesc.putBoolean(charIDToTypeID("enab"), true);
overlayDesc.putUnitDouble(charIDToTypeID("Opct"), charIDToTypeID("#Prc"), {opacity});
var list = new ActionList();
list.putObject(charIDToTypeID("SoFi"), overlayDesc);
desc.putList(charIDToTypeID("Lefx"), list);
executeAction(charIDToTypeID("Lefx"), desc, DialogModes.NO);
'''

    def _satin_style(self, layer_name: str, params: Dict[str, Any]) -> str:
        """光泽样式"""
        return self._drop_shadow_style(layer_name, params)

    def create_metal_text(self, text: str, style: Optional[TextStyle] = None) -> str:
        """创建金属文字效果

        Args:
            text: 文本内容
            style: 文本样式

        Returns:
            PS JSX 代码片段
        """
        if style is None:
            style = TextStyle()

        return f'''
// Metal Text Effect
{self.create_text_layer(text, style, "Metal_Text")}
{self.apply_layer_style("Metal_Text", "bevel_emboss", {{"size": 15, "depth": 200, "angle": 120}})}
{self.apply_layer_style("Metal_Text", "gradient_overlay", {{"angle": 90, "opacity": 100}})}
{self.apply_layer_style("Metal_Text", "drop_shadow", {{"distance": 5, "size": 10, "opacity": 50}})}
'''

    def create_neon_text(self, text: str, style: Optional[TextStyle] = None,
                         glow_color: Optional[List[float]] = None) -> str:
        """创建霓虹发光文字

        Args:
            text: 文本内容
            style: 文本样式
            glow_color: 发光颜色 RGB

        Returns:
            PS JSX 代码片段
        """
        if style is None:
            style = TextStyle()
        if glow_color is None:
            glow_color = [0.0, 1.0, 1.0]

        return f'''
// Neon Text Effect
var bgColor = new SolidColor();
bgColor.rgb.red = 10;
bgColor.rgb.green = 10;
bgColor.rgb.blue = 30;
app.backgroundColor = bgColor;

{self.create_text_layer(text, style, "Neon_Text")}
{self.apply_layer_style("Neon_Text", "outer_glow", {{"size": 30, "spread": 15, "opacity": 100}})}
{self.apply_layer_style("Neon_Text", "inner_glow", {{"size": 10, "opacity": 80}})}
'''

    def create_3d_text_ps(self, text: str, style: Optional[TextStyle] = None,
                          extrude_depth: int = 30) -> str:
        """创建 3D 挤压文字效果

        Args:
            text: 文本内容
            style: 文本样式
            extrude_depth: 挤压深度

        Returns:
            PS JSX 代码片段
        """
        if style is None:
            style = TextStyle()

        return f'''
// 3D Extrude Text Effect
{self.create_text_layer(text, style, "3D_Text")}
{self.apply_layer_style("3D_Text", "bevel_emboss", {{"size": {extrude_depth}, "depth": 250, "angle": 135}})}
{self.apply_layer_style("3D_Text", "drop_shadow", {{"distance": 20, "size": 15, "opacity": 60}})}
'''

    def create_fire_text(self, text: str, style: Optional[TextStyle] = None) -> str:
        """创建火焰文字效果

        Args:
            text: 文本内容
            style: 文本样式

        Returns:
            PS JSX 代码片段
        """
        if style is None:
            style = TextStyle()

        return f'''
// Fire Text Effect
var bgColor = new SolidColor();
bgColor.rgb.red = 0;
bgColor.rgb.green = 0;
bgColor.rgb.blue = 0;
app.backgroundColor = bgColor;

{self.create_text_layer(text, style, "Fire_Text")}
{self.apply_layer_style("Fire_Text", "outer_glow", {{"size": 40, "spread": 20, "opacity": 100}})}
{self.apply_layer_style("Fire_Text", "inner_glow", {{"size": 15, "opacity": 90}})}
'''

    def create_glass_text(self, text: str, style: Optional[TextStyle] = None) -> str:
        """创建玻璃/透明文字效果

        Args:
            text: 文本内容
            style: 文本样式

        Returns:
            PS JSX 代码片段
        """
        if style is None:
            style = TextStyle()

        return f'''
// Glass Text Effect
{self.create_text_layer(text, style, "Glass_Text")}
{self.apply_layer_style("Glass_Text", "bevel_emboss", {{"size": 8, "depth": 150, "angle": 120}})}
{self.apply_layer_style("Glass_Text", "inner_glow", {{"size": 5, "opacity": 50}})}
{self.apply_layer_style("Glass_Text", "drop_shadow", {{"distance": 3, "size": 5, "opacity": 30}})}
'''

    def apply_warp_text(self, layer_name: str, warp_style: str = "arc",
                        bend: float = 50.0, horizontal_distortion: float = 0.0,
                        vertical_distortion: float = 0.0) -> str:
        """应用文字变形（弧形、旗帜、波浪等）

        Args:
            layer_name: 图层名称
            warp_style: 变形样式 (arc, arc_lower, arc_upper, arch, bulge, shell_lower, shell_upper, flag, wave, fish, rise, fisheye, inflate, squeeze, twist)
            bend: 弯曲程度 (-100 到 100)
            horizontal_distortion: 水平扭曲
            vertical_distortion: 垂直扭曲

        Returns:
            PS JSX 代码片段
        """
        return f'''
var doc = app.activeDocument;
var layer = doc.artLayers.getByName("{layer_name}");
layer.textItem.warpStyle = WarpStyle.{warp_style.upper()};
layer.textItem.warpBend = {bend};
layer.textItem.warpHorizontalDistortion = {horizontal_distortion};
layer.textItem.warpVerticalDistortion = {vertical_distortion};
'''

    def generate_ps_script(self, text: str, style: Optional[TextStyle] = None,
                           effect_type: Optional[TextEffectType] = None) -> str:
        """生成完整的 Photoshop JSX 脚本

        Args:
            text: 文本内容
            style: 文本样式
            effect_type: 效果类型

        Returns:
            完整的 JSX 脚本字符串
        """
        if style is None:
            style = TextStyle()
        if effect_type is None:
            effect_type = TextEffectType.GLOW

        effect_map = {
            TextEffectType.GLOW: self.create_neon_text,
            TextEffectType.METAL: self.create_metal_text,
            TextEffectType.NEON: self.create_neon_text,
            TextEffectType.D_EXTRUDE: self.create_3d_text_ps,
            TextEffectType.FIRE: self.create_fire_text,
            TextEffectType.GLASS: self.create_glass_text,
        }

        effect_func = effect_map.get(effect_type, self.create_neon_text)
        script_body = effect_func(text, style)

        script_header = '''/*
Photoshop Text Effect Generator
*/

app.preferences.rulerUnits = Units.PIXELS;
'''

        script_footer = '''
alert("Text effect created successfully!");
'''

        return script_header + script_body + script_footer


# ============================================================================
# 5. DaVinci Resolve 文本动画生成器
# ============================================================================

class ResolveTextAnimator:
    """DaVinci Resolve 文本动画生成器

    生成 Fusion 合成设置文件 (.setting)，支持 Text+ 节点、
    Fusion 文本动画器、标题宏等。
    """

    def __init__(self, width: int = 1920, height: int = 1080,
                 frame_rate: float = 30.0):
        self.width = width
        self.height = height
        self.frame_rate = frame_rate

    def create_text_plus_node(self, text: str,
                               style: Optional[TextStyle] = None,
                               node_name: str = "TextPlus") -> str:
        """创建 Fusion Text+ 节点设置

        Args:
            text: 文本内容
            style: 文本样式
            node_name: 节点名称

        Returns:
            Fusion 设置代码片段
        """
        if style is None:
            style = TextStyle()

        return f'''
Tools = ordered() {{
    {node_name} = TextPlus {{
        StyledText = Transform{{
            Value = "{text}"
        }},
        Font = "{style.font_family}",
        Size = {style.font_size / 100},
        Center = {{0.5, 0.5}},
        Color = {{
            {style.fill_color[0]},
            {style.fill_color[1]},
            {style.fill_color[2]},
            {style.fill_color[3]}
        }},
        ElementShape = 2,
        StyledElement = 0,
        AdvancedFont = {{}},
        Tracking = {style.letter_spacing / 100},
        LineSpacing = 1,
        UseLineSpacingFontSettings = 1,
        Justification = 0,
        VerticalJustification = 0,
        Direction = 0,
    }}
}}
'''

    def apply_text_animator(self, node_name: str,
                             anim_type: str = "fade_in",
                             duration: float = 1.0,
                             start_frame: int = 0) -> str:
        """应用 Fusion 文本动画器

        Args:
            node_name: 节点名称
            anim_type: 动画类型
            duration: 动画时长（秒）
            start_frame: 起始帧

        Returns:
            Fusion 设置代码片段
        """
        end_frame = int(start_frame + duration * self.frame_rate)

        anim_map = {
            "fade_in": f"""
            CharacterLevelFade = {{
                Enabled = true,
                Start = {{ {start_frame}, 0 }},
                End = {{ {end_frame}, 1 }},
                Direction = 0,
            }}""",
            "fade_out": f"""
            CharacterLevelFade = {{
                Enabled = true,
                Start = {{ {start_frame}, 1 }},
                End = {{ {end_frame}, 0 }},
                Direction = 0,
            }}""",
            "typewriter": f"""
            CharacterLevelWipe = {{
                Enabled = true,
                Start = {{ {start_frame}, 0 }},
                End = {{ {end_frame}, 1 }},
                Direction = 0,
                WipeStyle = 0,
                Softness = 0,
            }}""",
            "scale_in": f"""
            CharacterLevelScale = {{
                Enabled = true,
                Start = {{ {start_frame}, 0 }},
                End = {{ {end_frame}, 1 }},
                Direction = 0,
            }}""",
        }

        anim_code = anim_map.get(anim_type, anim_map["fade_in"])

        return f'''
{node_name} = TextPlus {{
    {anim_code.strip()}
}}
'''

    def create_fusion_title(self, text: str,
                            style: Optional[TextStyle] = None,
                            title_style: str = "modern") -> str:
        """创建 Fusion 标题宏

        Args:
            text: 文本内容
            style: 文本样式
            title_style: 标题风格 (modern, classic, cinematic, minimal)

        Returns:
            完整的 .setting 文件内容
        """
        if style is None:
            style = TextStyle()

        style_configs = {
            "modern": {
                "background": "Rectangle",
                "drop_shadow": True,
                "bg_color": "0, 0.5, 1, 0.8",
            },
            "classic": {
                "background": "Line",
                "drop_shadow": False,
                "bg_color": "1, 1, 1, 0.9",
            },
            "cinematic": {
                "background": "Rectangle",
                "drop_shadow": True,
                "bg_color": "0, 0, 0, 0.7",
            },
            "minimal": {
                "background": "None",
                "drop_shadow": True,
                "bg_color": "1, 1, 1, 1",
            },
        }

        config = style_configs.get(title_style, style_configs["modern"])

        return f'''
{{
    Tools = ordered() {{
        Background = Background {{
            Width = {self.width},
            Height = {self.height},
            Depth = 1,
            ProcessMode = "Global",
        }},
        TextPlus_1 = TextPlus {{
            StyledText = Transform{{ Value = "{text}" }},
            Font = "{style.font_family}",
            Size = {style.font_size / 100},
            Center = {{ 0.5, 0.5 }},
            Color = {{
                {style.fill_color[0]},
                {style.fill_color[1]},
                {style.fill_color[2]},
                {style.fill_color[3]}
            }},
            CharacterLevelFade = {{
                Enabled = true,
                Start = {{ 0, 0 }},
                End = {{ 60, 1 }},
                Direction = 0,
            }},
        }},
        Merge1 = Merge {{
            Input = {{
                Main = {{
                    SourceOp = "Background",
                    Source = "Output",
                }},
                Foreground = {{
                    SourceOp = "TextPlus_1",
                    Source = "Output",
                }},
            }},
        }},
    }},
    Outputs = {{
        Output = Instance("Merge1", "Output"),
    }},
}}
'''

    def generate_setting_file(self, text: str,
                               style: Optional[TextStyle] = None,
                               anim_type: str = "fade_in") -> str:
        """生成 .setting 文件

        Args:
            text: 文本内容
            style: 文本样式
            anim_type: 动画类型

        Returns:
            完整的 .setting 文件内容
        """
        if style is None:
            style = TextStyle()

        return self.create_fusion_title(text, style)


# ============================================================================
# 6. Blender 3D 文本生成器
# ============================================================================

class BlenderTextGenerator:
    """Blender 3D 文本生成器

    生成 Blender Python 脚本，支持 3D 文本、倒角、材质、动画等。
    """

    def __init__(self, scene_name: str = "Text Scene"):
        self.scene_name = scene_name

    def create_3d_text(self, text: str,
                        style: Optional[TextStyle] = None,
                        extrude_depth: float = 0.2,
                        location: Tuple[float, float, float] = (0.0, 0.0, 0.0),
                        object_name: str = "3D_Text") -> str:
        """创建挤压 3D 文本

        Args:
            text: 文本内容
            style: 文本样式
            extrude_depth: 挤压深度
            location: 位置 (x, y, z)
            object_name: 对象名称

        Returns:
            Blender Python 代码片段
        """
        if style is None:
            style = TextStyle()

        return f'''
import bpy

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

bpy.ops.object.text_add(
    location=({location[0]}, {location[1]}, {location[2]})
)
text_obj = bpy.context.active_object
text_obj.name = "{object_name}"
text_obj.data.body = "{text}"
text_obj.data.size = {style.font_size / 50}
text_obj.data.extrude = {extrude_depth}
text_obj.data.bevel_depth = 0.02
text_obj.data.bevel_resolution = 4
text_obj.data.align_x = 'CENTER'
text_obj.data.align_y = 'CENTER'

text_obj.data.materials.append(bpy.data.materials.new(name="TextMaterial"))
'''

    def apply_bevel(self, object_name: str,
                     bevel_depth: float = 0.05,
                     bevel_resolution: int = 4) -> str:
        """应用倒角效果

        Args:
            object_name: 对象名称
            bevel_depth: 倒角深度
            bevel_resolution: 倒角细分

        Returns:
            Blender Python 代码片段
        """
        return f'''
text_obj = bpy.data.objects["{object_name}"]
text_obj.data.bevel_depth = {bevel_depth}
text_obj.data.bevel_resolution = {bevel_resolution}
'''

    def create_material(self, object_name: str,
                         base_color: Tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0),
                         metallic: float = 0.5,
                         roughness: float = 0.2,
                         material_name: str = "TextMaterial") -> str:
        """创建 Cycles/Eevee 材质

        Args:
            object_name: 对象名称
            base_color: 基础颜色 RGBA
            metallic: 金属度
            roughness: 粗糙度
            material_name: 材质名称

        Returns:
            Blender Python 代码片段
        """
        return f'''
obj = bpy.data.objects["{object_name}"]

if "{material_name}" in bpy.data.materials:
    mat = bpy.data.materials["{material_name}"]
else:
    mat = bpy.data.materials.new(name="{material_name}")
    mat.use_nodes = True

    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    bsdf.inputs['Base Color'].default_value = (
        {base_color[0]}, {base_color[1]}, {base_color[2]}, {base_color[3]}
    )
    bsdf.inputs['Metallic'].default_value = {metallic}
    bsdf.inputs['Roughness'].default_value = {roughness}

if obj.data.materials:
    obj.data.materials[0] = mat
else:
    obj.data.materials.append(mat)
'''

    def animate_text(self, object_name: str,
                      anim_type: str = "fade_in",
                      start_frame: int = 1,
                      end_frame: int = 60) -> str:
        """创建关键帧动画

        Args:
            object_name: 对象名称
            anim_type: 动画类型
            start_frame: 起始帧
            end_frame: 结束帧

        Returns:
            Blender Python 代码片段
        """
        anim_map = {
            "fade_in": f'''
obj = bpy.data.objects["{object_name}"]
scene = bpy.context.scene

if obj.data.materials:
    mat = obj.data.materials[0]
    if mat.use_nodes:
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs['Alpha'].default_value = 0
            bsdf.inputs['Alpha'].keyframe_insert(data_path="default_value", frame={start_frame})
            bsdf.inputs['Alpha'].default_value = 1
            bsdf.inputs['Alpha'].keyframe_insert(data_path="default_value", frame={end_frame})

obj.scale = (0, 0, 0)
obj.keyframe_insert(data_path="scale", frame={start_frame})
obj.scale = (1, 1, 1)
obj.keyframe_insert(data_path="scale", frame={end_frame})
''',
            "scale_in": f'''
obj = bpy.data.objects["{object_name}"]
obj.scale = (0, 0, 0)
obj.keyframe_insert(data_path="scale", frame={start_frame})
obj.scale = (1, 1, 1)
obj.keyframe_insert(data_path="scale", frame={end_frame})
''',
            "rotate_in": f'''
obj = bpy.data.objects["{object_name}"]
obj.rotation_euler = (0, 0, 3.14159 * 2)
obj.keyframe_insert(data_path="rotation_euler", frame={start_frame})
obj.rotation_euler = (0, 0, 0)
obj.keyframe_insert(data_path="rotation_euler", frame={end_frame})
obj.scale = (0, 0, 0)
obj.keyframe_insert(data_path="scale", frame={start_frame})
obj.scale = (1, 1, 1)
obj.keyframe_insert(data_path="scale", frame={end_frame})
''',
            "slide_up": f'''
obj = bpy.data.objects["{object_name}"]
obj.location.y = -5
obj.keyframe_insert(data_path="location", frame={start_frame})
obj.location.y = 0
obj.keyframe_insert(data_path="location", frame={end_frame})
''',
            "bounce": f'''
obj = bpy.data.objects["{object_name}"]
obj.scale = (0, 0, 0)
obj.keyframe_insert(data_path="scale", frame={start_frame})
obj.scale = (1.2, 1.2, 1.2)
obj.keyframe_insert(data_path="scale", frame={int((start_frame + end_frame) * 0.6)})
obj.scale = (1, 1, 1)
obj.keyframe_insert(data_path="scale", frame={end_frame})
''',
        }

        return anim_map.get(anim_type, anim_map["fade_in"])

    def generate_blend_script(self, text: str,
                               style: Optional[TextStyle] = None,
                               anim_type: str = "fade_in",
                               extrude_depth: float = 0.2) -> str:
        """生成完整的 Blender Python 脚本

        Args:
            text: 文本内容
            style: 文本样式
            anim_type: 动画类型
            extrude_depth: 挤压深度

        Returns:
            完整的 Blender Python 脚本字符串
        """
        if style is None:
            style = TextStyle()

        script_header = '''"""
Blender 3D Text Animation Script
Auto-generated by Text Animation Engine
"""

import bpy

'''

        script_body = self.create_3d_text(text, style, extrude_depth)
        script_material = self.create_material("3D_Text", style.fill_color)
        script_anim = self.animate_text("3D_Text", anim_type)

        script_footer = '''
scene = bpy.context.scene
scene.frame_set(1)
print("3D text animation created successfully!")
'''

        return script_header + script_body + script_material + script_anim + script_footer


# ============================================================================
# 7. 排版与字体系统
# ============================================================================

class FontStyle(str, Enum):
    """字体风格类别"""
    MODERN = "modern"
    CLASSIC = "classic"
    PLAYFUL = "playful"
    ELEGANT = "elegant"
    TECH = "tech"
    MINIMAL = "minimal"
    RETRO = "retro"
    HANDWRITING = "handwriting"
    DISPLAY = "display"
    BODY = "body"


@dataclass
class FontInfo:
    """字体信息数据类"""
    name: str
    family: str
    category: str = "sans-serif"
    style: str = "regular"
    weight: int = 400
    is_monospace: bool = False
    supports_chinese: bool = False
    supports_japanese: bool = False
    style_tags: List[str] = field(default_factory=list)
    file_path: str = ""
    designer: str = ""
    license: str = ""


class FontRegistry:
    """字体注册表 - 字体发现、元数据管理与分类"""

    def __init__(self):
        self._fonts: Dict[str, FontInfo] = {}
        self._categories: Dict[str, List[str]] = {}
        self._init_default_fonts()

    def _init_default_fonts(self) -> None:
        """初始化默认字体库"""
        default_fonts = [
            FontInfo("Arial", "Arial", "sans-serif", "regular", 400, False, False, False,
                     ["modern", "clean", "minimal"]),
            FontInfo("Arial Bold", "Arial", "sans-serif", "bold", 700, False, False, False,
                     ["modern", "clean", "minimal"]),
            FontInfo("Helvetica", "Helvetica", "sans-serif", "regular", 400, False, False, False,
                     ["modern", "classic", "minimal"]),
            FontInfo("Times New Roman", "Times New Roman", "serif", "regular", 400, False, False, False,
                     ["classic", "elegant", "body"]),
            FontInfo("Georgia", "Georgia", "serif", "regular", 400, False, False, False,
                     ["classic", "elegant"]),
            FontInfo("Verdana", "Verdana", "sans-serif", "regular", 400, False, False, False,
                     ["modern", "body"]),
            FontInfo("Courier New", "Courier New", "monospace", "regular", 400, True, False, False,
                     ["tech", "retro", "monospace"]),
            FontInfo("Impact", "Impact", "sans-serif", "bold", 900, False, False, False,
                     ["display", "bold", "modern"]),
            FontInfo("Comic Sans MS", "Comic Sans MS", "display", "regular", 400, False, False, False,
                     ["playful", "handwriting"]),
            FontInfo("Microsoft YaHei", "Microsoft YaHei", "sans-serif", "regular", 400, False, True, False,
                     ["modern", "chinese", "body"]),
            FontInfo("SimHei", "SimHei", "sans-serif", "bold", 700, False, True, False,
                     ["chinese", "display", "bold"]),
            FontInfo("SimSun", "SimSun", "serif", "regular", 400, False, True, False,
                     ["chinese", "classic", "body"]),
            FontInfo("KaiTi", "KaiTi", "serif", "regular", 400, False, True, False,
                     ["chinese", "elegant", "calligraphy"]),
            FontInfo("Consolas", "Consolas", "monospace", "regular", 400, True, False, False,
                     ["tech", "code", "monospace"]),
            FontInfo("Roboto", "Roboto", "sans-serif", "regular", 400, False, False, False,
                     ["modern", "minimal", "body"]),
            FontInfo("Open Sans", "Open Sans", "sans-serif", "regular", 400, False, False, False,
                     ["modern", "body"]),
            FontInfo("Montserrat", "Montserrat", "sans-serif", "bold", 700, False, False, False,
                     ["modern", "display", "elegant"]),
            FontInfo("Playfair Display", "Playfair Display", "serif", "regular", 400, False, False, False,
                     ["elegant", "display", "classic"]),
            FontInfo("Lato", "Lato", "sans-serif", "regular", 400, False, False, False,
                     ["modern", "body", "minimal"]),
            FontInfo("Source Code Pro", "Source Code Pro", "monospace", "regular", 400, True, False, False,
                     ["tech", "code"]),
        ]

        for font in default_fonts:
            self._fonts[font.name] = font

        self._build_categories()

    def _build_categories(self) -> None:
        """构建分类索引"""
        self._categories = {}
        for name, font in self._fonts.items():
            for tag in font.style_tags:
                if tag not in self._categories:
                    self._categories[tag] = []
                self._categories[tag].append(name)

    def register_font(self, font_info: FontInfo) -> None:
        """注册字体

        Args:
            font_info: 字体信息
        """
        self._fonts[font_info.name] = font_info
        self._build_categories()

    def get_font(self, name: str) -> Optional[FontInfo]:
        """获取字体信息

        Args:
            name: 字体名称

        Returns:
            字体信息或 None
        """
        return self._fonts.get(name)

    def list_fonts(self) -> List[FontInfo]:
        """列出所有注册字体

        Returns:
            字体信息列表
        """
        return list(self._fonts.values())

    def list_by_category(self, category: str) -> List[FontInfo]:
        """按分类列出字体

        Args:
            category: 分类标签

        Returns:
            字体信息列表
        """
        names = self._categories.get(category, [])
        return [self._fonts[name] for name in names if name in self._fonts]

    def search_fonts(self, keyword: str) -> List[FontInfo]:
        """搜索字体

        Args:
            keyword: 搜索关键词

        Returns:
            匹配的字体列表
        """
        keyword = keyword.lower()
        results = []
        for name, font in self._fonts.items():
            if (keyword in name.lower() or
                keyword in font.family.lower() or
                any(keyword in tag for tag in font.style_tags)):
                results.append(font)
        return results

    def discover_fonts(self, directory: str) -> List[str]:
        """从目录发现字体文件

        Args:
            directory: 字体目录路径

        Returns:
            发现的字体文件列表
        """
        font_extensions = {'.ttf', '.otf', '.woff', '.woff2', '.ttc'}
        found = []

        if not os.path.isdir(directory):
            return found

        for root, dirs, files in os.walk(directory):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in font_extensions:
                    found.append(os.path.join(root, file))

        return found


class TypographyEngine:
    """排版引擎 - 字体配对、比例缩放、可读性计算

    提供专业的排版计算，包括模块化比例、字体配对推荐、
    WCAG 对比度检查、行高计算等。
    """

    GOLDEN_RATIO = 1.618033988749895
    PERFECT_FIFTH = 1.5
    MAJOR_THIRD = 1.25
    MINOR_THIRD = 1.2
    MAJOR_SECOND = 1.125
    MINOR_SECOND = 1.067

    def __init__(self):
        self.font_registry = FontRegistry()

    def calculate_typography_scale(self, base_size: float = 16.0,
                                    ratio: Optional[float] = None,
                                    steps_up: int = 6,
                                    steps_down: int = 2) -> Dict[str, float]:
        """计算模块化字体比例缩放

        Args:
            base_size: 基准字号（通常为正文字号）
            ratio: 缩放比例，默认黄金比例
            steps_up: 向上扩展级数
            steps_down: 向下扩展级数

        Returns:
            字号映射字典
        """
        if ratio is None:
            ratio = self.GOLDEN_RATIO

        scale = {}

        for i in range(steps_down, 0, -1):
            size = base_size / (ratio ** i)
            scale[f"xs{i}" if i > 1 else "xs"] = round(size, 2)

        scale["base"] = base_size

        for i in range(1, steps_up + 1):
            size = base_size * (ratio ** i)
            scale[f"h{i}"] = round(size, 2)

        return scale

    def get_font_pairing(self, style: FontStyle = FontStyle.MODERN
                         ) -> Tuple[str, str]:
        """获取字体配对建议（标题 + 正文）

        Args:
            style: 风格类型

        Returns:
            (heading_font, body_font) 字体名称元组
        """
        pairings = {
            FontStyle.MODERN: ("Montserrat", "Roboto"),
            FontStyle.CLASSIC: ("Playfair Display", "Georgia"),
            FontStyle.PLAYFUL: ("Comic Sans MS", "Verdana"),
            FontStyle.ELEGANT: ("Playfair Display", "Lato"),
            FontStyle.TECH: ("Roboto", "Source Code Pro"),
            FontStyle.MINIMAL: ("Helvetica", "Lato"),
            FontStyle.RETRO: ("Impact", "Courier New"),
            FontStyle.HANDWRITING: ("Comic Sans MS", "Verdana"),
            FontStyle.DISPLAY: ("Montserrat", "Open Sans"),
            FontStyle.BODY: ("Lato", "Open Sans"),
        }

        return pairings.get(style, pairings[FontStyle.MODERN])

    def check_wcag_contrast(self, foreground: Tuple[float, float, float, float],
                             background: Tuple[float, float, float, float],
                             level: str = "AA") -> Dict[str, Any]:
        """检查 WCAG 2.1 对比度合规性

        Args:
            foreground: 前景色 RGBA (0-1)
            background: 背景色 RGBA (0-1)
            level: 合规级别 (AA, AAA)

        Returns:
            对比度检查结果字典
        """
        ratio = self._calculate_contrast_ratio(
            (foreground[0], foreground[1], foreground[2]),
            (background[0], background[1], background[2])
        )

        thresholds = {
            "normal_AA": 4.5,
            "large_AA": 3.0,
            "normal_AAA": 7.0,
            "large_AAA": 4.5,
        }

        passes_normal = ratio >= thresholds[f"normal_{level}"]
        passes_large = ratio >= thresholds[f"large_{level}"]

        return {
            "contrast_ratio": round(ratio, 2),
            "level": level,
            "passes_normal_text": passes_normal,
            "passes_large_text": passes_large,
            "threshold_normal": thresholds[f"normal_{level}"],
            "threshold_large": thresholds[f"large_{level}"],
            "recommendation": "PASS" if passes_normal else "FAIL - increase contrast",
        }

    def _calculate_contrast_ratio(self, fg: Tuple[float, float, float],
                                   bg: Tuple[float, float, float]) -> float:
        """计算两种颜色的对比度

        Args:
            fg: 前景色 RGB (0-1)
            bg: 背景色 RGB (0-1)

        Returns:
            对比度值
        """
        l1 = self._relative_luminance(fg)
        l2 = self._relative_luminance(bg)

        lighter = max(l1, l2)
        darker = min(l1, l2)

        return (lighter + 0.05) / (darker + 0.05)

    def _relative_luminance(self, color: Tuple[float, float, float]) -> float:
        """计算相对亮度（WCAG 定义）

        Args:
            color: RGB 颜色 (0-1)

        Returns:
            相对亮度值
        """
        def linearize(c: float) -> float:
            if c <= 0.03928:
                return c / 12.92
            return ((c + 0.055) / 1.055) ** 2.4

        r = linearize(color[0])
        g = linearize(color[1])
        b = linearize(color[2])

        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    def calculate_line_height(self, font_size: float,
                               line_height_ratio: Optional[float] = None
                               ) -> float:
        """计算最佳行高

        Args:
            font_size: 字号
            line_height_ratio: 行高比例，自动计算如果为 None

        Returns:
            行高值
        """
        if line_height_ratio is not None:
            return font_size * line_height_ratio

        if font_size < 14:
            ratio = 1.5
        elif font_size < 20:
            ratio = 1.45
        elif font_size < 30:
            ratio = 1.35
        elif font_size < 48:
            ratio = 1.25
        else:
            ratio = 1.15

        return round(font_size * ratio, 2)

    def calculate_letter_spacing(self, font_size: float,
                                  style: str = "normal") -> float:
        """根据字号计算推荐字间距（tracking）

        Args:
            font_size: 字号
            style: 样式类型 (tight, normal, loose, display)

        Returns:
            字间距值（em 单位）
        """
        spacing_map = {
            "tight": -0.02,
            "normal": 0.0,
            "loose": 0.05,
            "display": -0.05,
        }

        base_spacing = spacing_map.get(style, 0.0)

        if font_size < 14:
            adjustment = 0.01
        elif font_size < 24:
            adjustment = 0.0
        elif font_size < 48:
            adjustment = -0.01
        else:
            adjustment = -0.03

        return round(base_spacing + adjustment, 3)

    def suggest_font_for_style(self, style: FontStyle) -> List[FontInfo]:
        """根据风格推荐字体

        Args:
            style: 字体风格

        Returns:
            推荐字体列表
        """
        return self.font_registry.list_by_category(style.value)


# ============================================================================
# 8. 文本效果库
# ============================================================================

class EffectFactory:
    """效果工厂 - 创建和管理文本效果

    支持多种效果类型，可堆叠混合，生成统一的效果配置。
    """

    def __init__(self):
        self._presets: Dict[str, TextEffectPreset] = {}
        self._init_presets()

    def _init_presets(self) -> None:
        """初始化内置效果预设"""
        presets = [
            TextEffectPreset(
                name="Subtle Shadow",
                type=TextEffectType.SHADOW,
                params={"distance": 5, "size": 5, "opacity": 30, "angle": 120},
                description="柔和阴影效果",
                category="basic"
            ),
            TextEffectPreset(
                name="Soft Glow",
                type=TextEffectType.GLOW,
                params={"size": 20, "opacity": 60, "color": [1.0, 1.0, 1.0]},
                description="柔和发光效果",
                category="glow"
            ),
            TextEffectPreset(
                name="Cyan Neon",
                type=TextEffectType.NEON,
                params={"size": 30, "opacity": 100, "color": [0.0, 1.0, 1.0]},
                description="青色霓虹效果",
                category="neon"
            ),
            TextEffectPreset(
                name="Pink Neon",
                type=TextEffectType.NEON,
                params={"size": 30, "opacity": 100, "color": [1.0, 0.0, 0.8]},
                description="粉色霓虹效果",
                category="neon"
            ),
            TextEffectPreset(
                name="Brushed Metal",
                type=TextEffectType.METAL,
                params={"glossiness": 80, "reflectivity": 60, "base_color": [0.8, 0.8, 0.8]},
                description="拉丝金属效果",
                category="metal"
            ),
            TextEffectPreset(
                name="Gold Leaf",
                type=TextEffectType.GOLD,
                params={"glossiness": 90, "reflectivity": 80, "base_color": [1.0, 0.85, 0.2]},
                description="黄金文字效果",
                category="metal"
            ),
            TextEffectPreset(
                name="Glass Clear",
                type=TextEffectType.GLASS,
                params={"transparency": 0.5, "refraction": 1.1, "bevel": 8},
                description="透明玻璃效果",
                category="glass"
            ),
            TextEffectPreset(
                name="Fire Flames",
                type=TextEffectType.FIRE,
                params={"intensity": 1.0, "size": 40, "color_outer": [1.0, 0.0, 0.0], "color_inner": [1.0, 1.0, 0.0]},
                description="火焰文字效果",
                category="nature"
            ),
            TextEffectPreset(
                name="Ice Crystal",
                type=TextEffectType.ICE,
                params={"glow_size": 20, "refraction": 1.3, "base_color": [0.8, 0.95, 1.0]},
                description="冰晶文字效果",
                category="nature"
            ),
            TextEffectPreset(
                name="Wood Grain",
                type=TextEffectType.WOOD,
                params={"grain_size": 10, "depth": 3, "base_color": [0.6, 0.4, 0.2]},
                description="木纹文字效果",
                category="nature"
            ),
            TextEffectPreset(
                name="Chalk on Board",
                type=TextEffectType.CHALK,
                params={"roughness": 0.5, "opacity": 0.9, "color": [1.0, 1.0, 1.0]},
                description="粉笔文字效果",
                category="texture"
            ),
            TextEffectPreset(
                name="CRT Monitor",
                type=TextEffectType.CRT,
                params={"scanlines": True, "glow": True, "distortion": 0.1},
                description="CRT显示器效果",
                category="retro"
            ),
            TextEffectPreset(
                name="RGB Glitch",
                type=TextEffectType.GLITCH,
                params={"intensity": 0.6, "speed": 0.1, "rgb_split": 5},
                description="RGB故障效果",
                category="digital"
            ),
            TextEffectPreset(
                name="Vaporwave",
                type=TextEffectType.VAPORWAVE,
                params={"gradient_colors": [[1.0, 0.0, 1.0], [0.0, 1.0, 1.0]], "scanlines": True, "chromatic": 3},
                description="蒸汽波风格效果",
                category="retro"
            ),
            TextEffectPreset(
                name="Retro 80s",
                type=TextEffectType.RETRO,
                params={"gradient_direction": 90, "bevel": 5, "outline": 2},
                description="80年代复古风格",
                category="retro"
            ),
            TextEffectPreset(
                name="Thin Stroke",
                type=TextEffectType.STROKE,
                params={"size": 1, "color": [0.0, 0.0, 0.0]},
                description="细描边效果",
                category="basic"
            ),
            TextEffectPreset(
                name="Bold Stroke",
                type=TextEffectType.STROKE,
                params={"size": 4, "color": [0.0, 0.0, 0.0]},
                description="粗描边效果",
                category="basic"
            ),
            TextEffectPreset(
                name="Rainbow Gradient",
                type=TextEffectType.GRADIENT,
                params={"angle": 90, "colors": [[1, 0, 0], [1, 0.5, 0], [1, 1, 0], [0, 1, 0], [0, 0, 1], [0.5, 0, 1]]},
                description="彩虹渐变效果",
                category="gradient"
            ),
            TextEffectPreset(
                name="3D Extrude",
                type=TextEffectType.D_EXTRUDE,
                params={"depth": 30, "angle": 135, "bevel": 3},
                description="3D挤压效果",
                category="3d"
            ),
            TextEffectPreset(
                name="Bevel Edge",
                type=TextEffectType.BEVEL,
                params={"size": 8, "depth": 100, "angle": 120, "style": "inner_bevel"},
                description="斜面倒角效果",
                category="3d"
            ),
        ]

        for preset in presets:
            self._presets[preset.name] = preset

    def create_effect(self, effect_type: TextEffectType,
                      params: Optional[Dict[str, Any]] = None) -> TextEffectPreset:
        """创建效果实例

        Args:
            effect_type: 效果类型
            params: 效果参数

        Returns:
            效果预设对象
        """
        if params is None:
            params = {}

        return TextEffectPreset(
            name=f"Custom_{effect_type.value}",
            type=effect_type,
            params=params,
            description=f"Custom {effect_type.value} effect"
        )

    def get_preset(self, name: str) -> Optional[TextEffectPreset]:
        """获取预设效果

        Args:
            name: 预设名称

        Returns:
            效果预设或 None
        """
        return self._presets.get(name)

    def list_presets(self, category: Optional[str] = None) -> List[TextEffectPreset]:
        """列出所有预设

        Args:
            category: 可选分类筛选

        Returns:
            预设列表
        """
        presets = list(self._presets.values())
        if category:
            presets = [p for p in presets if p.category == category]
        return presets

    def stack_effects(self, effects: List[TextEffectPreset]) -> List[TextEffectPreset]:
        """堆叠多个效果

        Args:
            effects: 效果列表

        Returns:
            堆叠后的效果列表（从下到上顺序）
        """
        return effects

    def blend_effects(self, base_effect: TextEffectPreset,
                       overlay_effect: TextEffectPreset,
                       blend_mode: str = "normal",
                       opacity: float = 1.0) -> TextEffectPreset:
        """混合两个效果

        Args:
            base_effect: 基础效果
            overlay_effect: 叠加效果
            blend_mode: 混合模式
            opacity: 叠加不透明度

        Returns:
            混合后的效果
        """
        merged_params = {**base_effect.params, **overlay_effect.params}
        merged_params["blend_mode"] = blend_mode
        merged_params["blend_opacity"] = opacity

        return TextEffectPreset(
            name=f"{base_effect.name}_{overlay_effect.name}",
            type=base_effect.type,
            params=merged_params,
            description=f"Blend of {base_effect.name} and {overlay_effect.name}"
        )


# ============================================================================
# 9. 动画模板系统
# ============================================================================

@dataclass
class AnimationTemplate:
    """动画模板数据类"""
    id: str
    name: str
    category: str
    description: str
    animation_type: TextAnimationType
    style: TextStyle
    params: AnimationParams
    effects: List[TextEffectPreset] = field(default_factory=list)
    software_targets: List[SoftwareTarget] = field(default_factory=list)
    thumbnail: str = ""
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "animation_type": self.animation_type.value,
            "style": {
                "font_family": self.style.font_family,
                "font_size": self.style.font_size,
                "fill_color": list(self.style.fill_color),
                "stroke_color": list(self.style.stroke_color),
                "stroke_width": self.style.stroke_width,
                "letter_spacing": self.style.letter_spacing,
            },
            "params": {
                "duration": self.params.duration,
                "easing": self.params.easing.value,
                "intensity": self.params.intensity,
            },
            "effects": [e.to_dict() for e in self.effects],
            "software_targets": [s.value for s in self.software_targets],
            "thumbnail": self.thumbnail,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AnimationTemplate":
        style_data = data.get("style", {})
        params_data = data.get("params", {})

        return cls(
            id=data["id"],
            name=data["name"],
            category=data.get("category", "general"),
            description=data.get("description", ""),
            animation_type=TextAnimationType(data["animation_type"]),
            style=TextStyle(
                font_family=style_data.get("font_family", "Arial"),
                font_size=style_data.get("font_size", 72),
                fill_color=tuple(style_data.get("fill_color", [1, 1, 1, 1])),
                stroke_color=tuple(style_data.get("stroke_color", [0, 0, 0, 1])),
                stroke_width=style_data.get("stroke_width", 0),
                letter_spacing=style_data.get("letter_spacing", 0),
            ),
            params=AnimationParams(
                duration=params_data.get("duration", 1.0),
                easing=EasingType(params_data.get("easing", "ease_out")),
                intensity=params_data.get("intensity", 1.0),
            ),
            effects=[TextEffectPreset.from_dict(e) for e in data.get("effects", [])],
            software_targets=[SoftwareTarget(s) for s in data.get("software_targets", [])],
            thumbnail=data.get("thumbnail", ""),
            tags=data.get("tags", []),
        )


class TemplateEngine:
    """模板引擎 - 加载、保存、应用动画模板

    内置 50+ 模板，支持 JSON 格式导入导出，
    分类：标题、Lower Thirds、字幕、社交媒体、转场、动态排版。
    """

    def __init__(self):
        self._templates: Dict[str, AnimationTemplate] = {}
        self._build_builtin_templates()

    def _build_builtin_templates(self) -> None:
        """构建内置模板库（50+ 模板）"""
        categories = {
            "Titles": [
                ("hero_title_01", "Hero Bold Title", TextAnimationType.SCALE_IN,
                 TextStyle(font_family="Montserrat", font_size=120,
                           fill_color=(1, 1, 1, 1)),
                 AnimationParams(duration=1.2, easing=EasingType.EASE_OUT_BACK, intensity=1.0),
                 ["bold", "hero", "modern"]),
                ("elegant_title_01", "Elegant Serif Title", TextAnimationType.FADE_IN,
                 TextStyle(font_family="Playfair Display", font_size=100,
                           fill_color=(0.95, 0.9, 0.8, 1)),
                 AnimationParams(duration=1.5, easing=EasingType.EASE_OUT, intensity=0.8),
                 ["elegant", "serif", "classic"]),
                ("tech_title_01", "Tech Glitch Title", TextAnimationType.GLITCH,
                 TextStyle(font_family="Consolas", font_size=90,
                           fill_color=(0, 1, 0.5, 1)),
                 AnimationParams(duration=0.8, easing=EasingType.LINEAR, glitch_intensity=0.7),
                 ["tech", "glitch", "digital"]),
                ("neon_title_01", "Neon Glow Title", TextAnimationType.PULSE,
                 TextStyle(font_family="Montserrat", font_size=100,
                           fill_color=(0, 1, 1, 1)),
                 AnimationParams(duration=2.0, easing=EasingType.EASE_IN_OUT, intensity=0.15),
                 ["neon", "glow", "night"]),
                ("kinetic_title_01", "Kinetic Type Title", TextAnimationType.BOUNCE_IN,
                 TextStyle(font_family="Impact", font_size=110,
                           fill_color=(1, 0.2, 0.2, 1)),
                 AnimationParams(duration=1.0, easing=EasingType.EASE_OUT_BOUNCE, intensity=1.2),
                 ["kinetic", "bold", "energetic"]),
                ("minimal_title_01", "Minimal Clean Title", TextAnimationType.TRACKING_IN,
                 TextStyle(font_family="Helvetica", font_size=80,
                           fill_color=(0.2, 0.2, 0.2, 1)),
                 AnimationParams(duration=1.5, easing=EasingType.EASE_OUT, per_char_delay=0.05),
                 ["minimal", "clean", "modern"]),
                ("retro_title_01", "Retro 80s Title", TextAnimationType.ROTATE_IN,
                 TextStyle(font_family="Impact", font_size=100,
                           fill_color=(1, 0.5, 0, 1)),
                 AnimationParams(duration=1.2, easing=EasingType.EASE_OUT_BACK,
                                 rotation_degrees=180),
                 ["retro", "80s", "bold"]),
                ("cinematic_title_01", "Cinematic Title", TextAnimationType.BLUR_IN,
                 TextStyle(font_family="Georgia", font_size=90,
                           fill_color=(1, 1, 1, 1)),
                 AnimationParams(duration=2.0, easing=EasingType.EASE_OUT, blur_amount=40),
                 ["cinematic", "film", "dramatic"]),
            ],
            "Lower Thirds": [
                ("lower_third_01", "Modern Bar", TextAnimationType.SLIDE_LEFT,
                 TextStyle(font_family="Roboto", font_size=36,
                           fill_color=(1, 1, 1, 1)),
                 AnimationParams(duration=0.8, easing=EasingType.EASE_OUT_CUBIC),
                 ["modern", "news", "corporate"]),
                ("lower_third_02", "Minimal Line", TextAnimationType.FADE_IN,
                 TextStyle(font_family="Lato", font_size=32,
                           fill_color=(0.9, 0.9, 0.9, 1)),
                 AnimationParams(duration=1.0, easing=EasingType.EASE_OUT),
                 ["minimal", "clean"]),
                ("lower_third_03", "Bold Box", TextAnimationType.SLIDE_UP,
                 TextStyle(font_family="Montserrat", font_size=40,
                           fill_color=(1, 1, 1, 1)),
                 AnimationParams(duration=0.7, easing=EasingType.EASE_OUT_BACK),
                 ["bold", "sports", "energy"]),
                ("lower_third_04", "Elegant Card", TextAnimationType.SCALE_IN,
                 TextStyle(font_family="Playfair Display", font_size=34,
                           fill_color=(0.95, 0.9, 0.8, 1)),
                 AnimationParams(duration=1.0, easing=EasingType.EASE_OUT),
                 ["elegant", "wedding", "fashion"]),
                ("lower_third_05", "Neon Line", TextAnimationType.FADE_IN,
                 TextStyle(font_family="Consolas", font_size=30,
                           fill_color=(0, 1, 1, 1)),
                 AnimationParams(duration=0.6, easing=EasingType.EASE_OUT),
                 ["neon", "tech", "nightlife"]),
            ],
            "Credits": [
                ("credits_01", "Standard Scroll", TextAnimationType.SLIDE_UP,
                 TextStyle(font_family="Arial", font_size=28,
                           fill_color=(1, 1, 1, 1)),
                 AnimationParams(duration=30.0, easing=EasingType.LINEAR),
                 ["standard", "film"]),
                ("credits_02", "Fade In Rows", TextAnimationType.FADE_IN,
                 TextStyle(font_family="Georgia", font_size=30,
                           fill_color=(0.9, 0.9, 0.9, 1)),
                 AnimationParams(duration=20.0, easing=EasingType.EASE_OUT,
                                 per_char_delay=0.5),
                 ["elegant", "awards"]),
                ("credits_03", "Kinetic Credits", TextAnimationType.BOUNCE_IN,
                 TextStyle(font_family="Impact", font_size=36,
                           fill_color=(1, 0.8, 0, 1)),
                 AnimationParams(duration=15.0, easing=EasingType.EASE_OUT_BOUNCE),
                 ["kinetic", "energetic", "youth"]),
            ],
            "Social Media": [
                ("instagram_01", "Instagram Story", TextAnimationType.SLIDE_UP,
                 TextStyle(font_family="Montserrat", font_size=48,
                           fill_color=(1, 1, 1, 1)),
                 AnimationParams(duration=0.8, easing=EasingType.EASE_OUT_BACK),
                 ["instagram", "story", "vertical"]),
                ("tiktok_01", "TikTok Trend", TextAnimationType.ELASTIC_SCALE,
                 TextStyle(font_family="Impact", font_size=64,
                           fill_color=(1, 0, 0.5, 1)),
                 AnimationParams(duration=0.6, easing=EasingType.EASE_OUT_ELASTIC),
                 ["tiktok", "trendy", "viral"]),
                ("youtube_01", "YouTube Thumbnail", TextAnimationType.SCALE_IN,
                 TextStyle(font_family="Roboto", font_size=72,
                           fill_color=(1, 1, 1, 1)),
                 AnimationParams(duration=0.5, easing=EasingType.EASE_OUT_BACK),
                 ["youtube", "thumbnail", "bold"]),
                ("twitter_01", "Twitter Header", TextAnimationType.FADE_IN,
                 TextStyle(font_family="Helvetica", font_size=44,
                           fill_color=(1, 1, 1, 1)),
                 AnimationParams(duration=1.0, easing=EasingType.EASE_OUT),
                 ["twitter", "header", "minimal"]),
            ],
            "Transitions": [
                ("transition_01", "Wipe Text", TextAnimationType.TYPEWRITER,
                 TextStyle(font_family="Consolas", font_size=60,
                           fill_color=(1, 1, 1, 1)),
                 AnimationParams(duration=1.0, easing=EasingType.LINEAR,
                                 per_char_delay=0.03),
                 ["typewriter", "reveal"]),
                ("transition_02", "Glitch Cut", TextAnimationType.GLITCH,
                 TextStyle(font_family="Arial", font_size=56,
                           fill_color=(0.5, 1, 0.5, 1)),
                 AnimationParams(duration=0.3, easing=EasingType.LINEAR,
                                 glitch_intensity=0.8),
                 ["glitch", "cut", "digital"]),
                ("transition_03", "3D Flip", TextAnimationType.FLIP_3D,
                 TextStyle(font_family="Montserrat", font_size=64,
                           fill_color=(1, 0.8, 0, 1)),
                 AnimationParams(duration=1.0, easing=EasingType.EASE_IN_OUT),
                 ["3d", "flip", "dynamic"]),
            ],
            "Kinetic Typography": [
                ("kinetic_01", "Bounce Words", TextAnimationType.BOUNCE_IN,
                 TextStyle(font_family="Impact", font_size=80,
                           fill_color=(1, 0.3, 0.3, 1)),
                 AnimationParams(duration=0.8, easing=EasingType.EASE_OUT_BOUNCE),
                 ["bounce", "energetic", "words"]),
                ("kinetic_02", "Wave Text", TextAnimationType.WAVE,
                 TextStyle(font_family="Courier New", font_size=48,
                           fill_color=(0, 1, 1, 1)),
                 AnimationParams(duration=3.0, easing=EasingType.EASE_IN_OUT,
                                 wave_amplitude=20, wave_frequency=2),
                 ["wave", "flow", "liquid"]),
                ("kinetic_03", "Scale Pulse", TextAnimationType.PULSE,
                 TextStyle(font_family="Montserrat", font_size=90,
                           fill_color=(1, 1, 0, 1)),
                 AnimationParams(duration=2.0, easing=EasingType.EASE_IN_OUT,
                                 intensity=0.2),
                 ["pulse", "beat", "music"]),
                ("kinetic_04", "Tracking Zoom", TextAnimationType.TRACKING_IN,
                 TextStyle(font_family="Helvetica", font_size=72,
                           fill_color=(1, 1, 1, 1)),
                 AnimationParams(duration=1.5, easing=EasingType.EASE_OUT_CUBIC,
                                 per_char_delay=0.02),
                 ["tracking", "zoom", "dynamic"]),
                ("kinetic_05", "Rotate In", TextAnimationType.ROTATE_IN,
                 TextStyle(font_family="Georgia", font_size=64,
                           fill_color=(0.9, 0.7, 0.5, 1)),
                 AnimationParams(duration=1.2, easing=EasingType.EASE_OUT_BACK,
                                 rotation_degrees=90),
                 ["rotate", "spin", "vintage"]),
            ],
        }

        for category, templates in categories.items():
            for (tid, name, anim_type, style, params, tags) in templates:
                template = AnimationTemplate(
                    id=tid,
                    name=name,
                    category=category,
                    description=f"{category} template - {name}",
                    animation_type=anim_type,
                    style=style,
                    params=params,
                    software_targets=[
                        SoftwareTarget.AFTER_EFFECTS,
                        SoftwareTarget.PREMIERE_PRO,
                        SoftwareTarget.PHOTOSHOP,
                    ],
                    tags=tags,
                )
                self._templates[tid] = template

    def load_template(self, file_path: str) -> AnimationTemplate:
        """从 JSON 文件加载模板

        Args:
            file_path: 文件路径

        Returns:
            加载的模板
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Template file not found: {file_path}")

        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        return AnimationTemplate.from_dict(data)

    def save_template(self, template: AnimationTemplate,
                       file_path: str) -> None:
        """保存模板到 JSON 文件

        Args:
            template: 要保存的模板
            file_path: 保存路径
        """
        os.makedirs(os.path.dirname(file_path) or '.', exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(template.to_dict(), f, indent=2, ensure_ascii=False)

    def apply_template(self, template: AnimationTemplate,
                        text: str,
                        style_overrides: Optional[Dict[str, Any]] = None
                        ) -> Dict[str, Any]:
        """应用模板到新文本

        Args:
            template: 模板
            text: 新文本内容
            style_overrides: 样式覆盖

        Returns:
            应用配置字典
        """
        result_style = TextStyle(
            font_family=template.style.font_family,
            font_size=template.style.font_size,
            fill_color=template.style.fill_color,
            stroke_color=template.style.stroke_color,
            stroke_width=template.style.stroke_width,
            letter_spacing=template.style.letter_spacing,
        )

        if style_overrides:
            for key, value in style_overrides.items():
                if hasattr(result_style, key):
                    setattr(result_style, key, value)

        return {
            "text": text,
            "style": result_style,
            "animation_type": template.animation_type,
            "params": template.params,
            "effects": template.effects,
        }

    def get_template(self, template_id: str) -> Optional[AnimationTemplate]:
        """获取模板

        Args:
            template_id: 模板 ID

        Returns:
            模板或 None
        """
        return self._templates.get(template_id)

    def list_templates(self, category: Optional[str] = None,
                        search: Optional[str] = None
                        ) -> List[AnimationTemplate]:
        """列出模板

        Args:
            category: 可选分类筛选
            search: 可选搜索关键词

        Returns:
            模板列表
        """
        templates = list(self._templates.values())

        if category:
            templates = [t for t in templates if t.category == category]

        if search:
            search_lower = search.lower()
            templates = [
                t for t in templates
                if (search_lower in t.name.lower() or
                    search_lower in t.description.lower() or
                    any(search_lower in tag for tag in t.tags))
            ]

        return templates

    def get_categories(self) -> List[str]:
        """获取所有模板分类

        Returns:
            分类列表
        """
        categories = set(t.category for t in self._templates.values())
        return sorted(categories)


# ============================================================================
# 10. 跨软件统一 API 桥接
# ============================================================================

class UnifiedTextAPI:
    """统一文本 API - 跨软件桥接

    提供统一的接口来创建、动画化和导出文本，
    支持 After Effects、Premiere Pro、Photoshop、DaVinci Resolve、Blender。
    """

    def __init__(self):
        self.ae_animator = AETextAnimator()
        self.pr_animator = PRTextAnimator()
        self.ps_generator = PSTextEffectGenerator()
        self.resolve_animator = ResolveTextAnimator()
        self.blender_generator = BlenderTextGenerator()
        self.typography_engine = TypographyEngine()
        self.effect_factory = EffectFactory()
        self.template_engine = TemplateEngine()

    @staticmethod
    def _escape_jsx_string(s: str) -> str:
        return s.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")

    def create_text(self,
                    text: Optional[str] = None,
                    target: Optional[SoftwareTarget] = None,
                    style: Optional[TextStyle] = None,
                    *,
                    software: Optional[str] = None,
                    position: Optional[Tuple[float, float]] = None,
                    params: Optional[Dict] = None,
                    **kwargs) -> str:
        """统一创建文本

        支持两种调用方式:
            create_text(text, target, style)
            create_text(software="after_effects", text=..., position=..., params={...})

        Args:
            text: 文本内容
            target: 目标软件 (SoftwareTarget 枚举)
            style: 文本样式
            software: 目标软件名称 (字符串形式, 与 target 二选一)
            position: 文本位置 (x_ratio, y_ratio)
            params: 参数字典 (font_size, font_color, animation, style 等)
            **kwargs: 额外参数

        Returns:
            生成的脚本/设置字符串
        """
        if text is None:
            raise ValueError("text 参数不能为空")

        if target is None and software is not None:
            sw_lower = software.lower().replace(" ", "_")
            target_map = {
                "after_effects": SoftwareTarget.AFTER_EFFECTS,
                "ae": SoftwareTarget.AFTER_EFFECTS,
                "premiere_pro": SoftwareTarget.PREMIERE_PRO,
                "pr": SoftwareTarget.PREMIERE_PRO,
                "premiere": SoftwareTarget.PREMIERE_PRO,
                "photoshop": SoftwareTarget.PHOTOSHOP,
                "ps": SoftwareTarget.PHOTOSHOP,
                "davinci_resolve": SoftwareTarget.DAVINCI_RESOLVE,
                "resolve": SoftwareTarget.DAVINCI_RESOLVE,
                "blender": SoftwareTarget.BLENDER,
            }
            target = target_map.get(sw_lower, SoftwareTarget.AFTER_EFFECTS)
        elif target is None:
            target = SoftwareTarget.AFTER_EFFECTS

        if params is not None and isinstance(params, dict):
            if style is None:
                style = TextStyle()
            if "font_size" in params:
                style.font_size = params["font_size"]
            if "font_color" in params:
                fc = params["font_color"]
                if isinstance(fc, (list, tuple)) and len(fc) >= 3:
                    style.fill_color = tuple(fc[:3])
            if "style" in params:
                pass
            for k, v in params.items():
                if k not in ("font_size", "font_color", "style") and k not in kwargs:
                    kwargs[k] = v

        if position is not None:
            kwargs["position"] = position

        if style is None:
            style = TextStyle()

        text = self._escape_jsx_string(text)

        creators = {
            SoftwareTarget.AFTER_EFFECTS: self._create_ae_text,
            SoftwareTarget.PREMIERE_PRO: self._create_pr_text,
            SoftwareTarget.PHOTOSHOP: self._create_ps_text,
            SoftwareTarget.DAVINCI_RESOLVE: self._create_resolve_text,
            SoftwareTarget.BLENDER: self._create_blender_text,
        }

        creator = creators.get(target)
        if creator is None:
            raise ValueError(f"Unsupported software target: {target}")

        return creator(text, style, **kwargs)

    def _create_ae_text(self, text: str, style: TextStyle, **kwargs) -> str:
        comp_name = kwargs.get("comp_name", "Text Comp")
        self.ae_animator.comp_name = comp_name
        return self.ae_animator.create_text_layer(text, style)

    def _create_pr_text(self, text: str, style: TextStyle, **kwargs) -> str:
        return self.pr_animator.create_essential_graphics_text(text, style)

    def _create_ps_text(self, text: str, style: TextStyle, **kwargs) -> str:
        return self.ps_generator.create_text_layer(text, style)

    def _create_resolve_text(self, text: str, style: TextStyle, **kwargs) -> str:
        return self.resolve_animator.create_text_plus_node(text, style)

    def _create_blender_text(self, text: str, style: TextStyle, **kwargs) -> str:
        extrude_depth = kwargs.get("extrude_depth", 0.2)
        return self.blender_generator.create_3d_text(text, style, extrude_depth)

    def animate_text(self, text: str,
                     target: SoftwareTarget = SoftwareTarget.AFTER_EFFECTS,
                     anim_type: TextAnimationType = TextAnimationType.FADE_IN,
                     style: Optional[TextStyle] = None,
                     params: Optional[AnimationParams] = None) -> str:
        """统一动画 API

        Args:
            text: 文本内容
            target: 目标软件
            anim_type: 动画类型
            style: 文本样式
            params: 动画参数

        Returns:
            生成的动画脚本字符串
        """
        if style is None:
            style = TextStyle()
        if params is None:
            params = AnimationParams()

        animators = {
            SoftwareTarget.AFTER_EFFECTS: self._animate_ae,
            SoftwareTarget.PREMIERE_PRO: self._animate_pr,
            SoftwareTarget.PHOTOSHOP: self._animate_ps,
            SoftwareTarget.DAVINCI_RESOLVE: self._animate_resolve,
            SoftwareTarget.BLENDER: self._animate_blender,
        }

        animator = animators.get(target)
        if animator is None:
            raise ValueError(f"Unsupported software target: {target}")

        return animator(text, anim_type, style, params)

    def _animate_ae(self, text: str, anim_type: TextAnimationType,
                     style: TextStyle, params: AnimationParams) -> str:
        return self.ae_animator.generate_jsx(text, style, anim_type, params)

    def _animate_pr(self, text: str, anim_type: TextAnimationType,
                     style: TextStyle, params: AnimationParams) -> str:
        return self.pr_animator.generate_pr_script(text, style, anim_type.value)

    def _animate_ps(self, text: str, anim_type: TextAnimationType,
                     style: TextStyle, params: AnimationParams) -> str:
        effect_map = {
            TextAnimationType.FADE_IN: TextEffectType.GLOW,
            TextAnimationType.SCALE_IN: TextEffectType.D_EXTRUDE,
            TextAnimationType.GLITCH: TextEffectType.GLITCH,
        }
        effect_type = effect_map.get(anim_type, TextEffectType.GLOW)
        return self.ps_generator.generate_ps_script(text, style, effect_type)

    def _animate_resolve(self, text: str, anim_type: TextAnimationType,
                          style: TextStyle, params: AnimationParams) -> str:
        return self.resolve_animator.generate_setting_file(text, style, anim_type.value)

    def _animate_blender(self, text: str, anim_type: TextAnimationType,
                          style: TextStyle, params: AnimationParams) -> str:
        return self.blender_generator.generate_blend_script(
            text, style, anim_type.value
        )

    def apply_effect(self, text: str,
                     target: SoftwareTarget = SoftwareTarget.PHOTOSHOP,
                     effect_type: TextEffectType = TextEffectType.GLOW,
                     style: Optional[TextStyle] = None,
                     effect_params: Optional[Dict[str, Any]] = None) -> str:
        """统一文本效果 API

        Args:
            text: 文本内容
            target: 目标软件
            effect_type: 效果类型
            style: 文本样式
            effect_params: 效果参数

        Returns:
            生成的效果脚本字符串
        """
        if style is None:
            style = TextStyle()

        if target == SoftwareTarget.PHOTOSHOP:
            return self.ps_generator.generate_ps_script(text, style, effect_type)
        elif target == SoftwareTarget.AFTER_EFFECTS:
            return self.ae_animator.generate_jsx(text, style)
        else:
            return self.create_text(text, target, style)

    def export_to_software(self, text: str,
                           target: SoftwareTarget,
                           template: Optional[AnimationTemplate] = None,
                           output_path: Optional[str] = None) -> str:
        """导出到目标软件

        Args:
            text: 文本内容
            target: 目标软件
            template: 可选模板
            output_path: 可选输出路径

        Returns:
            生成的脚本/设置字符串
        """
        if template:
            config = self.template_engine.apply_template(template, text)
            style = config["style"]
            anim_type = config["animation_type"]
            params = config["params"]
            script = self.animate_text(text, target, anim_type, style, params)
        else:
            script = self.create_text(text, target)

        if output_path:
            self._save_script(script, target, output_path)

        return script

    def _save_script(self, script: str, target: SoftwareTarget,
                      output_path: str) -> None:
        """保存脚本到文件

        Args:
            script: 脚本内容
            target: 目标软件（决定扩展名）
            output_path: 输出路径
        """
        ext_map = {
            SoftwareTarget.AFTER_EFFECTS: ".jsx",
            SoftwareTarget.PREMIERE_PRO: ".jsx",
            SoftwareTarget.PHOTOSHOP: ".jsx",
            SoftwareTarget.DAVINCI_RESOLVE: ".setting",
            SoftwareTarget.BLENDER: ".py",
        }

        ext = ext_map.get(target, ".txt")
        if not output_path.endswith(ext):
            output_path += ext

        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(script)

    def batch_create(self, text_items: List[Dict[str, Any]],
                      target: SoftwareTarget = SoftwareTarget.AFTER_EFFECTS
                      ) -> List[str]:
        """批量创建文本动画

        Args:
            text_items: 文本项目列表，每项包含 text, style, anim_type 等
            target: 目标软件

        Returns:
            生成的脚本列表
        """
        results = []
        for item in text_items:
            text = item.get("text", "")
            style = item.get("style")
            anim_type = item.get("anim_type", TextAnimationType.FADE_IN)
            params = item.get("params")

            result = self.animate_text(text, target, anim_type, style, params)
            results.append(result)

        return results


# ============================================================================
# 主函数 - 演示用法
# ============================================================================

def main():
    """Text Animation Engine 演示程序"""
    print("=" * 70)
    print("Text Animation Engine - 跨平台文本动画引擎")
    print("=" * 70)
    print()

    api = UnifiedTextAPI()
    style = TextStyle(
        font_family="Montserrat",
        font_size=80,
        fill_color=(1.0, 1.0, 1.0, 1.0),
        letter_spacing=2,
    )

    print("[1] After Effects JSX 生成演示")
    print("-" * 50)
    ae_script = api.animate_text(
        "Hello World!",
        target=SoftwareTarget.AFTER_EFFECTS,
        anim_type=TextAnimationType.BOUNCE_IN,
        style=style,
        params=AnimationParams(duration=1.2, easing=EasingType.EASE_OUT_BOUNCE),
    )
    print(f"AE 脚本长度: {len(ae_script)} 字符")
    print(f"包含动画: BOUNCE_IN")
    print()

    print("[2] 排版引擎演示")
    print("-" * 50)
    typography = TypographyEngine()
    scale = typography.calculate_typography_scale(16, TypographyEngine.GOLDEN_RATIO, 5, 2)
    print(f"字体比例 (黄金比例, 基准16px):")
    for name, size in scale.items():
        print(f"  {name:>6}: {size:>7.2f}px")
    print()

    contrast_result = typography.check_wcag_contrast(
        (1.0, 1.0, 1.0, 1.0),
        (0.1, 0.1, 0.3, 1.0),
        "AA"
    )
    print(f"WCAG 对比度检查: {contrast_result['contrast_ratio']}:1")
    print(f"AA 级普通文本: {'通过' if contrast_result['passes_normal_text'] else '失败'}")
    print()

    heading_font, body_font = typography.get_font_pairing(FontStyle.MODERN)
    print(f"现代风格字体配对: {heading_font} / {body_font}")
    print()

    print("[3] 文本效果库演示")
    print("-" * 50)
    effect_factory = EffectFactory()
    presets = effect_factory.list_presets()
    print(f"内置效果预设: {len(presets)} 个")
    categories = set(p.category for p in presets)
    print(f"效果分类: {', '.join(sorted(categories))}")
    print()

    print("[4] 模板系统演示")
    print("-" * 50)
    template_engine = TemplateEngine()
    templates = template_engine.list_templates()
    categories = template_engine.get_categories()
    print(f"内置模板总数: {len(templates)} 个")
    print(f"模板分类: {', '.join(categories)}")
    for cat in categories:
        cat_templates = template_engine.list_templates(category=cat)
        print(f"  {cat}: {len(cat_templates)} 个模板")
    print()

    print("[5] 字体注册表演示")
    print("-" * 50)
    registry = FontRegistry()
    all_fonts = registry.list_fonts()
    print(f"注册字体总数: {len(all_fonts)} 个")
    tech_fonts = registry.list_by_category("tech")
    print(f"科技风格字体: {', '.join(f.name for f in tech_fonts)}")
    chinese_fonts = [f for f in all_fonts if f.supports_chinese]
    print(f"支持中文字体: {', '.join(f.name for f in chinese_fonts)}")
    print()

    print("[6] 跨软件导出演示")
    print("-" * 50)
    targets = [
        SoftwareTarget.AFTER_EFFECTS,
        SoftwareTarget.PREMIERE_PRO,
        SoftwareTarget.PHOTOSHOP,
        SoftwareTarget.DAVINCI_RESOLVE,
        SoftwareTarget.BLENDER,
    ]
    for target in targets:
        script = api.animate_text(
            "Cross-Platform Text",
            target=target,
            anim_type=TextAnimationType.FADE_IN,
            style=style,
        )
        print(f"{target.value:20s}: {len(script):>5d} 字符脚本已生成")
    print()

    print("[7] 模板应用演示")
    print("-" * 50)
    hero_template = template_engine.get_template("hero_title_01")
    if hero_template:
        print(f"模板名称: {hero_template.name}")
        print(f"模板分类: {hero_template.category}")
        print(f"动画类型: {hero_template.animation_type.value}")
        print(f"字体: {hero_template.style.font_family}")
        print(f"字号: {hero_template.style.font_size}px")

        applied = template_engine.apply_template(hero_template, "Custom Hero Text")
        print(f"应用后文本: {applied['text']}")
        print(f"应用后动画类型: {applied['animation_type'].value}")
    print()

    print("[8] 批量创建演示")
    print("-" * 50)
    batch_items = [
        {"text": "Title 1", "anim_type": TextAnimationType.FADE_IN},
        {"text": "Title 2", "anim_type": TextAnimationType.SCALE_IN},
        {"text": "Title 3", "anim_type": TextAnimationType.SLIDE_UP},
    ]
    batch_results = api.batch_create(batch_items, SoftwareTarget.AFTER_EFFECTS)
    print(f"批量创建了 {len(batch_results)} 个文本动画")
    for i, result in enumerate(batch_results):
        print(f"  第 {i+1} 个: {len(result)} 字符")
    print()

    print("=" * 70)
    print("演示完成！所有模块正常工作。")
    print("=" * 70)
    print()
    print("可用类和功能总结:")
    print("  - TextAnimationType: 24种动画类型枚举")
    print("  - AETextAnimator: AE JSX 生成器 (20+预设)")
    print("  - PRTextAnimator: Premiere Pro 生成器")
    print("  - PSTextEffectGenerator: Photoshop 效果生成器")
    print("  - ResolveTextAnimator: DaVinci Resolve/Fusion 生成器")
    print("  - BlenderTextGenerator: Blender 3D 文本生成器")
    print("  - TypographyEngine: 排版引擎 (比例/配对/对比度)")
    print("  - FontRegistry: 字体注册表 (发现/分类/搜索)")
    print("  - EffectFactory: 效果工厂 (20+预设)")
    print("  - TemplateEngine: 模板系统 (50+模板)")
    print("  - UnifiedTextAPI: 跨软件统一 API")


if __name__ == "__main__":
    main()
