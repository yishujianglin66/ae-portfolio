#!/usr/bin/env python3
"""
JSX关键帧动画引擎 — 将静态JSX升级为带专业关键帧动画的脚本

功能模块（按漫剪风格管线需求设计）：
1. EntranceAnimator — 入场动画 (fade-in, blur-in, scale-up, slide, 3D rotate)
2. TextAnimator — 文字动画 (typewriter逐字显现, tracking, opacity pulse, per-character)
3. BeatSyncAnimator — 音乐节奏动画 (根据beat timing生成opacity/scale/position脉冲)
4. CameraAnimator — 运镜模拟 (Ken Burns缓慢推拉, whip pan, dolly zoom, handheld shake)
5. EffectPulseAnimator — 效果参数脉冲 (glow pulse, blur rack, color wash, 动态参数)

主要调用接口：
- animate_entrance() — 为素材层添加入场动画关键帧
- animate_text() — 为文字层添加专业文字动画
- animate_beat_sync() — 为多个层同步节奏脉冲
- animate_camera() — 添加摄像机运动关键帧
- animate_effect_pulse() — 为效果参数添加时间脉冲

版本: 1.0.0 | 基于进度交接_漫剪风格管线_2026-07-25 P0优先级
"""

from __future__ import annotations

import json
import logging
import math
import os
import random
from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


# ============================================================
# 数据模型
# ============================================================

class EaseType(str, Enum):
    """缓动类型 — 映射到AE内置缓动函数"""
    LINEAR = "linear"
    EASE_IN = "easeIn"
    EASE_OUT = "easeOut"
    EASE_IN_OUT = "easeInOut"
    EASE_OUT_QUAD = "easeOut"               # 二次缓出（AE标准）
    EASE_OUT_ELASTIC = "easeOutElastic"     # 弹性缓出（漫剪常用）
    EASE_OUT_BOUNCE = "easeOutBounce"        # 弹跳缓出
    EASE_IN_BACK = "easeInBack"              # 回缩缓入
    CUSTOM_BEZIER = "customBezier"           # 自定义贝塞尔


class AnimationDirection(str, Enum):
    """动画方向"""
    FROM_CENTER = "center"
    FROM_LEFT = "left"
    FROM_RIGHT = "right"
    FROM_TOP = "top"
    FROM_BOTTOM = "bottom"
    FROM_TOP_LEFT = "topLeft"
    FROM_TOP_RIGHT = "topRight"
    FROM_BOTTOM_LEFT = "bottomLeft"
    FROM_BOTTOM_RIGHT = "bottomRight"
    RANDOM = "random"


class EntranceStyle(str, Enum):
    """入场动画风格"""
    FADE_IN = "fadeIn"                     # 淡入
    FADE_IN_ZOOM = "fadeInZoom"            # 淡入+缩放（最常用）
    BLUR_IN = "blurIn"                     # 模糊→清晰
    SLIDE = "slide"                        # 滑入
    SCALE_UP = "scaleUp"                   # 弹性放大
    SCALE_DOWN = "scaleDown"               # 缩小入场
    THREE_D_FLIP = "threeDFlip"            # 3D翻转
    THREE_D_ROTATE = "threeDRotate"        # 3D旋转
    GLITCH_IN = "glitchIn"                 # 故障风格入场
    WHIP_IN = "whipIn"                     # 甩入
    NONE = "none"                          # 无入场动画


class TextAnimationStyle(str, Enum):
    """文字动画风格 — 36种预设覆盖漫剪全场景"""
    # ---- V1 基础 8 种 ----
    TYPEWRITER = "typewriter"              # 打字机
    TRACKING = "tracking"                  # 字间距展开
    OPACITY_RANDOM = "opacityRandom"       # 随机透明
    SCALE_PER_CHAR = "scalePerChar"        # 逐字缩放
    POSITION_JITTER = "positionJitter"     # 位置抖动
    FADE_UP_STAGGER = "fadeUpStagger"      # 交错淡入上升
    DROP_BOUNCE = "dropBounce"             # 弹跳下落
    SLIDE_IN_STAGGER = "slideInStagger"    # 交错滑入
    # ---- V2 新增 12 种 ----
    GLITCH_TEXT = "glitchText"             # 文字故障闪烁
    WAVE_ENTRANCE = "waveEntrance"         # 波浪入场
    ROTATE_IN_STAGGER = "rotateInStagger"  # 逐字旋转入场
    SCALE_DOWN_BOUNCE = "scaleDownBounce"  # 缩放弹跳（从200%弹到100%）
    SLIDE_RIGHT_STAGGER = "slideRightStagger"  # 交错右滑入
    FADE_SCALE_COMBO = "fadeScaleCombo"    # 淡入+缩放组合
    BLUR_IN_TEXT = "blurInText"            # 模糊显现
    FLIP_3D_TEXT = "flip3dText"           # 3D翻转文字
    PULSE_GLOW_TEXT = "pulseGlowText"     # 脉冲发光文字
    SPRING_SCALE = "springScale"           # 弹性缩放
    CASCADE_FALL = "cascadeFall"           # 级联下落
    KINETIC_TYPING = "kineticTyping"       # 动态打字（大小写交替+位移）
    # ---- V3 新增 16 种 (漫剪/AMV深度覆盖) ----
    ELASTIC_OVERSHOOT = "elasticOvershoot"   # 弹性过冲（多次回弹收敛）
    SQUASH_STRETCH = "squashStretch"         # 挤压拉伸（卡通弹性）
    SPIRAL_ENTRANCE = "spiralEntrance"       # 螺旋入场（旋转+缩放到零）
    PER_CHAR_WAVE = "perCharWave"            # 逐字波浪（基线偏移传播）
    RANDOM_POP = "randomPop"                 # 随机弹出（随机顺序放大回弹）
    DOMINO_FALL = "dominoFall"               # 多米诺骨牌（逐字旋转倒下）
    SCATTER_CONVERGE = "scatterConverge"     # 散点汇聚（从随机位置汇聚）
    STROKE_DRAW = "strokeDraw"               # 描边绘制（描边宽度逐字揭示）
    COLOR_WIPE = "colorWipe"                 # 色彩擦除（填充色逐字过渡）
    LETTER_POP = "letterPop"                 # 逐字弹出（放大150%回弹）
    BASELINE_SHIFT = "baselineShift"         # 基线波浪（上下浮动）
    ZOOM_BLUR_RUSH = "zoomBlurRush"          # 缩放模糊冲入（模糊+缩放）
    SWIPE_SLIDE = "swipeSlide"               # 擦除滑入（位置+遮罩组合）
    NEON_FLICKER = "neonFlicker"             # 霓虹闪烁（透明度+颜色脉冲）
    IMPACT_SHAKE = "impactShake"             # 冲击震动（缩放过冲+抖动）
    FLOAT_UP = "floatUp"                     # 悬浮上升（缓慢上升+微浮动）


class AnimationIntensity(str, Enum):
    """动画强度分级 — 智能导演可根据场景节奏自动选择"""
    SUBTLE = "subtle"         # 微妙：小幅运动，适合字幕/引言
    MODERATE = "moderate"     # 中等：标准幅度，适合大多数场景
    INTENSE = "intense"       # 强烈：大幅运动，适合标题/高潮

    @property
    def amplitude_scale(self) -> float:
        """幅度缩放系数"""
        return {"subtle": 0.5, "moderate": 1.0, "intense": 1.8}[self.value]

    @property
    def duration_scale(self) -> float:
        """时长缩放系数（subtle更快，intense更慢更有冲击力）"""
        return {"subtle": 0.7, "moderate": 1.0, "intense": 1.3}[self.value]


class CameraStyle(str, Enum):
    """运镜风格"""
    KEN_BURNS = "kenBurns"                 # 缓慢推拉（最常用）
    WHIP_PAN = "whipPan"                   # 快速甩镜
    DOLLY_ZOOM = "dollyZoom"               # 反向缩放
    HANDHELD_SHAKE = "handheldShake"       # 手持晃动
    PUSH_IN = "pushIn"                     # 推进
    PULL_OUT = "pullOut"                   # 拉远


class PulsePattern(str, Enum):
    """脉冲模式"""
    BEAT = "beat"                          # 跟随节拍
    SINE_WAVE = "sineWave"                 # 正弦波呼吸
    SAW_WAVE = "sawWave"                   # 锯齿波
    RANDOM_BURST = "randomBurst"           # 随机爆发
    DROP_DECAY = "dropDecay"               # 衰减脉冲（如底鼓后的衰减）


@dataclass
class Keyframe:
    """单个关键帧"""
    time: float                            # 时间（秒）
    value: Any                             # 值
    ease_in: EaseType = EaseType.EASE_IN_OUT
    ease_out: EaseType = EaseType.EASE_IN_OUT
    ease_in_speed: float = 0.0
    ease_out_speed: float = 0.0
    
    def to_dict(self) -> dict:
        return {
            "time": round(self.time, 3),
            "value": self.value,
            "easeIn": self.ease_in.value,
            "easeOut": self.ease_out.value,
            "easeInSpeed": round(self.ease_in_speed, 2),
            "easeOutSpeed": round(self.ease_out_speed, 2),
        }


@dataclass
class AnimationTrack:
    """单属性动画轨道"""
    property_path: str           # AE属性路径，如 "ADBE Transform Group/ADBE Position"
    keyframes: List[Keyframe] = field(default_factory=list)
    property_type: str = "float" # float, position, scale, 3d, color


@dataclass
class LayerAnimation:
    """单层完整动画"""
    layer_index: int
    layer_type: str  # "footage", "text", "solid", "adjustment"
    animation_tracks: List[AnimationTrack] = field(default_factory=list)
    entrance_style: EntranceStyle = EntranceStyle.NONE
    entrance_duration: float = 0.5
    entrance_offset: float = 0.0
    
    def add_track(self, track: AnimationTrack) -> None:
        self.animation_tracks.append(track)


@dataclass
class BeatTiming:
    """节拍时间标记"""
    time: float            # 时间（秒）
    strength: float = 1.0  # 节拍强度 0-1
    is_downbeat: bool = False  # 是否重拍


# ============================================================
# 辅助工具
# ============================================================

def lerp(a: float, b: float, t: float) -> float:
    """线性插值"""
    return a + (b - a) * t


def ease_out_quad(t: float) -> float:
    """二次缓出"""
    return 1 - (1 - t) * (1 - t)


def ease_out_cubic(t: float) -> float:
    """三次缓出"""
    return 1 - (1 - t) ** 3


def ease_out_elastic(t: float, amplitude: float = 1.0) -> float:
    """弹性缓出（漫剪风格核心缓动）"""
    if t == 0 or t == 1:
        return t
    c4 = (2 * math.pi) / 3
    return amplitude * (2 ** (-10 * t)) * math.sin((t * 10 - 0.75) * c4) + 1


def ease_out_bounce(t: float) -> float:
    """弹跳缓出"""
    n1, d1 = 7.5625, 2.75
    if t < 1 / d1:
        return n1 * t * t
    elif t < 2 / d1:
        return n1 * (t - 1.5 / d1) * (t - 1.5 / d1) + 0.75
    elif t < 2.5 / d1:
        return n1 * (t - 2.25 / d1) * (t - 2.25 / d1) + 0.9375
    else:
        return n1 * (t - 2.625 / d1) * (t - 2.625 / d1) + 0.984375


def ease_in_out_quad(t: float) -> float:
    """二次缓入缓出"""
    return 2 * t * t if t < 0.5 else 1 - (-2 * t + 2) ** 2 / 2


def sample_beat_strength(time: float, beats: List[BeatTiming], 
                         lookahead: float = 0.05) -> float:
    """采样给定时间点的节拍强度"""
    strength = 0.0
    for beat in beats:
        # 在节拍周围lookahead范围内采样
        if abs(beat.time - time) < lookahead:
            strength = max(strength, beat.strength)
    return strength


def generate_sine_pulse(time: float, freq: float = 2.0, 
                        amplitude: float = 0.3, base: float = 1.0) -> float:
    """正弦波脉冲 — 用于呼吸效果"""
    return base + amplitude * math.sin(2 * math.pi * freq * time)


def clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))


# ============================================================
# 1. 入场动画器 (EntranceAnimator)
# ============================================================

class EntranceAnimator:
    """为素材层生成入场动画关键帧
    
    支持多种漫剪常用入场风格：
    - fadeIn: 纯淡入
    - fadeInZoom: 淡入+缩放（漫剪最常用，100%→原大小）
    - blurIn: 模糊入场
    - slide: 方向滑入
    - threeDFlip/threeDRotate: 3D入场
    - glitchIn: 故障风格入场
    """
    
    # 各风格默认时长（秒）
    DURATIONS = {
        EntranceStyle.FADE_IN: 0.4,
        EntranceStyle.FADE_IN_ZOOM: 0.5,
        EntranceStyle.BLUR_IN: 0.45,
        EntranceStyle.SLIDE: 0.5,
        EntranceStyle.SCALE_UP: 0.5,
        EntranceStyle.SCALE_DOWN: 0.45,
        EntranceStyle.THREE_D_FLIP: 0.6,
        EntranceStyle.THREE_D_ROTATE: 0.6,
        EntranceStyle.GLITCH_IN: 0.4,
        EntranceStyle.WHIP_IN: 0.35,
    }
    
    # 缓动映射 — 漫剪风格偏弹性缓出
    EASE_MAP = {
        EntranceStyle.SCALE_UP: EaseType.EASE_OUT_ELASTIC,
        EntranceStyle.SCALE_DOWN: EaseType.EASE_OUT_ELASTIC,
        EntranceStyle.THREE_D_FLIP: EaseType.EASE_OUT_ELASTIC,
    }
    
    def __init__(self, seed: Optional[int] = 42):
        """seed=None 保留随机抖动(创作自由度); 默认固定 42 保证同树可复现
        (2026-08-16 决策: 入场动画此前用全局 random 无种子, 同树 JSX
        跨进程不可复现 — 见 docs/process/2026-08-16-phase2-architecture-consolidation-log.md)。
        """
        self.default_duration = 0.5
        self._rng = random.Random(seed)
    
    def build_tracks(
        self, 
        style: EntranceStyle, 
        layer_start: float = 0.0,
        duration: Optional[float] = None,
        direction: AnimationDirection = AnimationDirection.FROM_CENTER,
    ) -> List[AnimationTrack]:
        """生成入场动画轨道列表
        
        Args:
            style: 入场风格
            layer_start: 层开始时间（秒）
            duration: 动画时长（秒），None则用默认
            direction: 滑入方向（仅slide风格有效）
            
        Returns:
            List[AnimationTrack]: 动画轨道列表
        """
        duration = duration or self.DURATIONS.get(style, self.default_duration)
        ease = self.EASE_MAP.get(style, EaseType.EASE_OUT_QUAD)
        
        if style == EntranceStyle.NONE:
            return []
        
        if style == EntranceStyle.FADE_IN:
            return self._build_fade_in(layer_start, duration)
        elif style == EntranceStyle.FADE_IN_ZOOM:
            return self._build_fade_in_zoom(layer_start, duration)
        elif style == EntranceStyle.BLUR_IN:
            return self._build_blur_in(layer_start, duration)
        elif style == EntranceStyle.SLIDE:
            return self._build_slide(layer_start, duration, direction)
        elif style == EntranceStyle.SCALE_UP:
            return self._build_scale_up(layer_start, duration)
        elif style == EntranceStyle.SCALE_DOWN:
            return self._build_scale_down(layer_start, duration)
        elif style == EntranceStyle.THREE_D_FLIP:
            return self._build_3d_flip(layer_start, duration)
        elif style == EntranceStyle.THREE_D_ROTATE:
            return self._build_3d_rotate(layer_start, duration)
        elif style == EntranceStyle.GLITCH_IN:
            return self._build_glitch_in(layer_start, duration)
        elif style == EntranceStyle.WHIP_IN:
            return self._build_whip_in(layer_start, duration)
        
        logger.warning(f"未知入场风格 {style}，回退到fadeIn")
        return self._build_fade_in(layer_start, duration)
    
    def _build_fade_in(self, start: float, duration: float) -> List[AnimationTrack]:
        """纯淡入"""
        opacity_track = AnimationTrack(
            property_path="Transform/Opacity",
            property_type="float",
            keyframes=[
                Keyframe(start, 0),
                Keyframe(start + duration, 100),
            ],
        )
        return [opacity_track]
    
    def _build_fade_in_zoom(self, start: float, duration: float) -> List[AnimationTrack]:
        """淡入+缩放（漫剪最常用风格）"""
        # 缩放从1.3→1.0，实现"镜头推进"感
        tracks = []
        
        tracks.append(AnimationTrack(
            property_path="Transform/Opacity",
            property_type="float",
            keyframes=[
                Keyframe(start, 0),
                Keyframe(start + duration * 0.6, 100),
                Keyframe(start + duration, 100),
            ],
        ))
        
        tracks.append(AnimationTrack(
            property_path="Transform/Scale",
            property_type="scale",
            keyframes=[
                Keyframe(start, [130, 130, 100], ease_out=EaseType.EASE_OUT_ELASTIC),
                Keyframe(start + duration, [100, 100, 100]),
            ],
        ))
        
        return tracks
    
    def _build_blur_in(self, start: float, duration: float) -> List[AnimationTrack]:
        """模糊入场 — opacity + gaussian blur"""
        tracks = []
        
        tracks.append(AnimationTrack(
            property_path="Transform/Opacity",
            property_type="float",
            keyframes=[
                Keyframe(start, 0),
                Keyframe(start + duration, 100),
            ],
        ))
        
        # Gaussian Blur 从50→0
        tracks.append(AnimationTrack(
            property_path="Effects/Gaussian Blur/Blurriness",
            property_type="float",
            keyframes=[
                Keyframe(start, 50),
                Keyframe(start + duration, 0),
            ],
        ))
        
        return tracks
    
    def _build_slide(self, start: float, duration: float, 
                     direction: AnimationDirection) -> List[AnimationTrack]:
        """方向滑入"""
        direction = direction if direction != AnimationDirection.RANDOM else \
            self._rng.choice([AnimationDirection.FROM_LEFT, AnimationDirection.FROM_RIGHT])
        
        # 计算起始位置偏移
        offset_map = {
            AnimationDirection.FROM_LEFT: [-960, 0, 0],    # 从左边滑入
            AnimationDirection.FROM_RIGHT: [960, 0, 0],
            AnimationDirection.FROM_TOP: [0, -540, 0],
            AnimationDirection.FROM_BOTTOM: [0, 540, 0],
            AnimationDirection.FROM_TOP_LEFT: [-960, -540, 0],
            AnimationDirection.FROM_TOP_RIGHT: [960, -540, 0],
            AnimationDirection.FROM_BOTTOM_LEFT: [-960, 540, 0],
            AnimationDirection.FROM_BOTTOM_RIGHT: [960, 540, 0],
        }
        
        start_pos = offset_map.get(direction, [0, 0, 0])
        
        tracks = [AnimationTrack(
            property_path="Transform/Position",
            property_type="position",
            keyframes=[
                Keyframe(start, start_pos, ease_out=EaseType.EASE_OUT_QUAD),
                Keyframe(start + duration, [0, 0, 0]),
            ],
        )]
        return tracks
    
    def _build_scale_up(self, start: float, duration: float) -> List[AnimationTrack]:
        """弹性放大入场"""
        return [AnimationTrack(
            property_path="Transform/Scale",
            property_type="scale",
            keyframes=[
                Keyframe(start, [0, 0, 100], ease_out=EaseType.EASE_OUT_ELASTIC),
                Keyframe(start + duration, [100, 100, 100]),
            ],
        )]
    
    def _build_scale_down(self, start: float, duration: float) -> List[AnimationTrack]:
        """缩小入场（从大→正常，用于强调）"""
        tracks = [AnimationTrack(
            property_path="Transform/Scale",
            property_type="scale",
            keyframes=[
                Keyframe(start, [150, 150, 100], ease_out=EaseType.EASE_OUT_ELASTIC),
                Keyframe(start + duration, [100, 100, 100]),
            ],
        )]
        return tracks
    
    def _build_3d_flip(self, start: float, duration: float) -> List[AnimationTrack]:
        """3D Y轴翻转入场"""
        tracks = [AnimationTrack(
            property_path="Transform/Y Rotation",
            property_type="float",
            keyframes=[
                Keyframe(start, 180, ease_out=EaseType.EASE_OUT_QUAD),
                Keyframe(start + duration, 0),
            ],
        )]
        return tracks
    
    def _build_3d_rotate(self, start: float, duration: float) -> List[AnimationTrack]:
        """3D Z轴旋转入场"""
        tracks = [AnimationTrack(
            property_path="Transform/Rotation",
            property_type="float",
            keyframes=[
                Keyframe(start, -90, ease_out=EaseType.EASE_OUT_ELASTIC),
                Keyframe(start + duration, 0),
            ],
        )]
        return tracks
    
    def _build_glitch_in(self, start: float, duration: float) -> List[AnimationTrack]:
        """故障风格入场（快速闪烁+位移抖动）"""
        tracks = []
        # Opacity 快速闪烁
        num_flickers = self._rng.randint(3, 6)
        opacity_kfs = [Keyframe(start, 0)]
        for i in range(num_flickers):
            t = start + duration * (i + 1) / (num_flickers + 1)
            val = self._rng.choice([0, 40, 80, 100])
            opacity_kfs.append(Keyframe(t, val))
        opacity_kfs.append(Keyframe(start + duration, 100))
        
        tracks.append(AnimationTrack(
            property_path="Transform/Opacity",
            property_type="float",
            keyframes=opacity_kfs,
        ))
        
        # 位置微抖
        tracks.append(AnimationTrack(
            property_path="Transform/Position",
            property_type="position",
            keyframes=[
                Keyframe(start, [self._rng.randint(-20, 20), 
                                 self._rng.randint(-20, 20), 0]),
                Keyframe(start + duration * 0.5, [self._rng.randint(-10, 10),
                                                     self._rng.randint(-10, 10), 0]),
                Keyframe(start + duration, [0, 0, 0]),
            ],
        ))
        
        return tracks
    
    def _build_whip_in(self, start: float, duration: float) -> List[AnimationTrack]:
        """甩入（快速滑动+轻微旋转）"""
        tracks = []
        
        tracks.append(AnimationTrack(
            property_path="Transform/Position",
            property_type="position",
            keyframes=[
                Keyframe(start, [-300, 0, 0], ease_out=EaseType.EASE_OUT_QUAD),
                Keyframe(start + duration * 0.3, [20, 0, 0]),
                Keyframe(start + duration, [0, 0, 0]),
            ],
        ))
        
        tracks.append(AnimationTrack(
            property_path="Transform/Rotation",
            property_type="float",
            keyframes=[
                Keyframe(start, -15),
                Keyframe(start + duration, 0),
            ],
        ))
        
        return tracks
    
    def select_entrance_for_style(self, style_category: str) -> EntranceStyle:
        """根据漫剪风格类别智能选择入场动画"""
        style_map = {
            "amv_pull_zoom": EntranceStyle.FADE_IN_ZOOM,
            "amv_fast_cut": EntranceStyle.WHIP_IN,
            "amv_beat_sync": EntranceStyle.SCALE_UP,
            "amv_korean_flash": EntranceStyle.FADE_IN_ZOOM,
            "amv_glitch": EntranceStyle.GLITCH_IN,
            "amv_cinematic": EntranceStyle.FADE_IN,
            "amv_3d_spatial": EntranceStyle.THREE_D_ROTATE,
            "amv_high_burn": EntranceStyle.FADE_IN_ZOOM,
        }
        return style_map.get(style_category, EntranceStyle.FADE_IN_ZOOM)


# ============================================================
# 2. 文字动画器 (TextAnimator)
# ============================================================

class TextAnimator:
    """专业文字动画生成器
    
    用于漫剪标题、歌词字幕等文字层的关键帧动画。
    基于AE Text Animator系统，支持逐字级动画。
    """
    
    def __init__(self, seed: Optional[int] = 42):
        """seed=None 保留随机(创作自由度); 默认固定 42 与 EntranceAnimator 同口径。"""
        self._rng = random.Random(seed)
    
    def build_tracks(
        self,
        style: TextAnimationStyle,
        text_start: float = 0.0,
        text_duration: float = 2.0,
        char_count: int = 10,
        stagger: float = 0.05,   # 逐字延迟
        magnitude: float = 50,   # 动画幅度
    ) -> List[AnimationTrack]:
        """生成文字动画轨道 — 20种预设全覆盖
        
        Returns:
            List[AnimationTrack]: 动画轨道（包含Text Animator Range Selector设置）
        """
        # 统一签名：所有方法接收相同参数
        args = (text_start, text_duration, char_count, stagger, magnitude)
        dispatch = {
            TextAnimationStyle.TYPEWRITER:          self._build_typewriter,
            TextAnimationStyle.TRACKING:            self._build_tracking,
            TextAnimationStyle.OPACITY_RANDOM:      self._build_opacity_random,
            TextAnimationStyle.SCALE_PER_CHAR:      self._build_scale_per_char,
            TextAnimationStyle.POSITION_JITTER:     self._build_position_jitter,
            TextAnimationStyle.FADE_UP_STAGGER:     self._build_fade_up_stagger,
            TextAnimationStyle.DROP_BOUNCE:         self._build_drop_bounce,
            TextAnimationStyle.SLIDE_IN_STAGGER:    self._build_slide_in_stagger,
            TextAnimationStyle.GLITCH_TEXT:         self._build_glitch_text,
            TextAnimationStyle.WAVE_ENTRANCE:       self._build_wave_entrance,
            TextAnimationStyle.ROTATE_IN_STAGGER:   self._build_rotate_in_stagger,
            TextAnimationStyle.SCALE_DOWN_BOUNCE:   self._build_scale_down_bounce,
            TextAnimationStyle.SLIDE_RIGHT_STAGGER: self._build_slide_right_stagger,
            TextAnimationStyle.FADE_SCALE_COMBO:    self._build_fade_scale_combo,
            TextAnimationStyle.BLUR_IN_TEXT:        self._build_blur_in_text,
            TextAnimationStyle.FLIP_3D_TEXT:        self._build_flip_3d_text,
            TextAnimationStyle.PULSE_GLOW_TEXT:     self._build_pulse_glow_text,
            TextAnimationStyle.SPRING_SCALE:        self._build_spring_scale,
            TextAnimationStyle.CASCADE_FALL:        self._build_cascade_fall,
            TextAnimationStyle.KINETIC_TYPING:      self._build_kinetic_typing,
            # V3 新增 16 种
            TextAnimationStyle.ELASTIC_OVERSHOOT:   self._build_elastic_overshoot,
            TextAnimationStyle.SQUASH_STRETCH:      self._build_squash_stretch,
            TextAnimationStyle.SPIRAL_ENTRANCE:     self._build_spiral_entrance,
            TextAnimationStyle.PER_CHAR_WAVE:       self._build_per_char_wave,
            TextAnimationStyle.RANDOM_POP:          self._build_random_pop,
            TextAnimationStyle.DOMINO_FALL:         self._build_domino_fall,
            TextAnimationStyle.SCATTER_CONVERGE:    self._build_scatter_converge,
            TextAnimationStyle.STROKE_DRAW:         self._build_stroke_draw,
            TextAnimationStyle.COLOR_WIPE:          self._build_color_wipe,
            TextAnimationStyle.LETTER_POP:          self._build_letter_pop,
            TextAnimationStyle.BASELINE_SHIFT:      self._build_baseline_shift,
            TextAnimationStyle.ZOOM_BLUR_RUSH:      self._build_zoom_blur_rush,
            TextAnimationStyle.SWIPE_SLIDE:         self._build_swipe_slide,
            TextAnimationStyle.NEON_FLICKER:        self._build_neon_flicker,
            TextAnimationStyle.IMPACT_SHAKE:        self._build_impact_shake,
            TextAnimationStyle.FLOAT_UP:            self._build_float_up,
        }
        handler = dispatch.get(style)
        if handler:
            return handler(*args)
        logger.warning(f"未知文字动画风格 {style}，回退到fadeUpStagger")
        return self._build_fade_up_stagger(*args)
    
    # ============================================================
    # 文字动画实现 — 统一签名 (start, duration, char_count, stagger, magnitude)
    # ============================================================

    def _build_typewriter(self, start, duration, char_count, stagger, magnitude):
        """打字机效果 — rangeSelector Start从0%→100%"""
        return [AnimationTrack(
            property_path="ADBE Text Properties/Animators/Animator 1/Range Selector 1/Start",
            property_type="float",
            keyframes=[Keyframe(start, 0), Keyframe(start + duration, 100)],
        )]

    def _build_tracking(self, start, duration, char_count, stagger, magnitude):
        """字间距动画 — tracking从负值展开"""
        return [AnimationTrack(
            property_path="ADBE Text Properties/Animators/Animator 1/Tracking",
            property_type="float",
            keyframes=[
                Keyframe(start, -magnitude, ease_out=EaseType.EASE_OUT_ELASTIC),
                Keyframe(start + duration, 0),
            ],
        )]

    def _build_opacity_random(self, start, duration, char_count, stagger, magnitude):
        """随机透明逐个显现"""
        return [
            AnimationTrack(
                property_path="ADBE Text Properties/Animators/Animator 1/Range Selector 1/Start",
                property_type="float",
                keyframes=[Keyframe(start, 0), Keyframe(start + duration, 100)],
            ),
            AnimationTrack(
                property_path="ADBE Text Properties/Animators/Animator 1/Opacity",
                property_type="float",
                keyframes=[Keyframe(start, 0), Keyframe(start + duration, 100)],
            ),
        ]

    def _build_scale_per_char(self, start, duration, char_count, stagger, magnitude):
        """逐字缩放动画"""
        return [AnimationTrack(
            property_path="ADBE Text Properties/Animators/Animator 1/Scale",
            property_type="scale",
            keyframes=[
                Keyframe(start, [magnitude * 2, magnitude * 2], ease_out=EaseType.EASE_OUT_ELASTIC),
                Keyframe(start + duration, [100, 100]),
            ],
        )]

    def _build_position_jitter(self, start, duration, char_count, stagger, magnitude):
        """位置抖动 — 每个字符随机偏移后归位"""
        tracks = []
        n_jit = max(3, min(8, int(duration / 0.1)))
        pos_kfs = []
        for i in range(n_jit):
            t = start + duration * i / n_jit
            jx = self._rng.uniform(-magnitude, magnitude)
            jy = self._rng.uniform(-magnitude * 0.6, magnitude * 0.6)
            pos_kfs.append(Keyframe(t, [jx, jy, 0]))
        pos_kfs.append(Keyframe(start + duration, [0, 0, 0]))
        tracks.append(AnimationTrack(
            property_path="ADBE Text Properties/Animators/Animator 1/Position",
            property_type="position", keyframes=pos_kfs,
        ))
        tracks.append(AnimationTrack(
            property_path="ADBE Text Properties/Animators/Animator 1/Opacity",
            property_type="float",
            keyframes=[Keyframe(start, 0), Keyframe(start + duration * 0.3, 100),
                       Keyframe(start + duration, 100)],
        ))
        return tracks

    def _build_fade_up_stagger(self, start, duration, char_count, stagger, magnitude):
        """交错淡入上升"""
        return [
            AnimationTrack(
                property_path="ADBE Text Properties/Animators/Animator 1/Position",
                property_type="position",
                keyframes=[
                    Keyframe(start, [0, magnitude, 0], ease_out=EaseType.EASE_OUT_QUAD),
                    Keyframe(start + duration, [0, 0, 0]),
                ],
            ),
            AnimationTrack(
                property_path="ADBE Text Properties/Animators/Animator 1/Opacity",
                property_type="float",
                keyframes=[Keyframe(start, 0), Keyframe(start + duration * 0.7, 100),
                           Keyframe(start + duration, 100)],
            ),
        ]

    def _build_drop_bounce(self, start, duration, char_count, stagger, magnitude):
        """弹跳下落"""
        drop = magnitude * 2
        return [AnimationTrack(
            property_path="ADBE Text Properties/Animators/Animator 1/Position",
            property_type="position",
            keyframes=[
                Keyframe(start, [0, -drop, 0]),
                Keyframe(start + duration * 0.6, [0, 10, 0]),
                Keyframe(start + duration * 0.8, [0, -5, 0]),
                Keyframe(start + duration, [0, 0, 0]),
            ],
        )]

    def _build_slide_in_stagger(self, start, duration, char_count, stagger, magnitude):
        """交错左滑入"""
        return [AnimationTrack(
            property_path="ADBE Text Properties/Animators/Animator 1/Position",
            property_type="position",
            keyframes=[
                Keyframe(start, [-magnitude * 2, 0, 0], ease_out=EaseType.EASE_OUT_QUAD),
                Keyframe(start + duration, [0, 0, 0]),
            ],
        )]

    # ---- V2 新增 12 种 ----

    def _build_glitch_text(self, start, duration, char_count, stagger, magnitude):
        """文字故障闪烁 — opacity快速闪+位置微偏移"""
        tracks = []
        n_flick = self._rng.randint(4, 8)
        op_kfs = [Keyframe(start, 0)]
        for i in range(n_flick):
            t = start + duration * (i + 1) / (n_flick + 1)
            op_kfs.append(Keyframe(t, self._rng.choice([0, 30, 80, 100])))
        op_kfs.append(Keyframe(start + duration, 100))
        tracks.append(AnimationTrack(
            property_path="ADBE Text Properties/Animators/Animator 1/Opacity",
            property_type="float", keyframes=op_kfs,
        ))
        tracks.append(AnimationTrack(
            property_path="ADBE Text Properties/Animators/Animator 1/Position",
            property_type="position",
            keyframes=[
                Keyframe(start, [self._rng.randint(-15, 15), self._rng.randint(-10, 10), 0]),
                Keyframe(start + duration * 0.5, [self._rng.randint(-8, 8), 0, 0]),
                Keyframe(start + duration, [0, 0, 0]),
            ],
        ))
        return tracks

    def _build_wave_entrance(self, start, duration, char_count, stagger, magnitude):
        """波浪入场 — 字符依次从下方波浪升起"""
        return [
            AnimationTrack(
                property_path="ADBE Text Properties/Animators/Animator 1/Position",
                property_type="position",
                keyframes=[
                    Keyframe(start, [0, magnitude * 1.5, 0], ease_out=EaseType.EASE_OUT_ELASTIC),
                    Keyframe(start + duration, [0, 0, 0]),
                ],
            ),
            AnimationTrack(
                property_path="ADBE Text Properties/Animators/Animator 1/Opacity",
                property_type="float",
                keyframes=[Keyframe(start, 0), Keyframe(start + duration * 0.5, 100),
                           Keyframe(start + duration, 100)],
            ),
            AnimationTrack(
                property_path="ADBE Text Properties/Animators/Animator 1/Rotation",
                property_type="float",
                keyframes=[
                    Keyframe(start, self._rng.choice([-15, 15])),
                    Keyframe(start + duration, 0),
                ],
            ),
        ]

    def _build_rotate_in_stagger(self, start, duration, char_count, stagger, magnitude):
        """逐字旋转入场"""
        return [
            AnimationTrack(
                property_path="ADBE Text Properties/Animators/Animator 1/Rotation",
                property_type="float",
                keyframes=[
                    Keyframe(start, self._rng.choice([-180, 180]), ease_out=EaseType.EASE_OUT_ELASTIC),
                    Keyframe(start + duration, 0),
                ],
            ),
            AnimationTrack(
                property_path="ADBE Text Properties/Animators/Animator 1/Opacity",
                property_type="float",
                keyframes=[Keyframe(start, 0), Keyframe(start + duration * 0.6, 100),
                           Keyframe(start + duration, 100)],
            ),
        ]

    def _build_scale_down_bounce(self, start, duration, char_count, stagger, magnitude):
        """缩放弹跳 — 从200%弹到100%"""
        return [AnimationTrack(
            property_path="ADBE Text Properties/Animators/Animator 1/Scale",
            property_type="scale",
            keyframes=[
                Keyframe(start, [magnitude * 4, magnitude * 4], ease_out=EaseType.EASE_OUT_BOUNCE),
                Keyframe(start + duration, [100, 100]),
            ],
        )]

    def _build_slide_right_stagger(self, start, duration, char_count, stagger, magnitude):
        """交错右滑入"""
        return [AnimationTrack(
            property_path="ADBE Text Properties/Animators/Animator 1/Position",
            property_type="position",
            keyframes=[
                Keyframe(start, [magnitude * 2, 0, 0], ease_out=EaseType.EASE_OUT_QUAD),
                Keyframe(start + duration, [0, 0, 0]),
            ],
        )]

    def _build_fade_scale_combo(self, start, duration, char_count, stagger, magnitude):
        """淡入+缩放组合"""
        return [
            AnimationTrack(
                property_path="ADBE Text Properties/Animators/Animator 1/Opacity",
                property_type="float",
                keyframes=[Keyframe(start, 0), Keyframe(start + duration * 0.6, 100),
                           Keyframe(start + duration, 100)],
            ),
            AnimationTrack(
                property_path="ADBE Text Properties/Animators/Animator 1/Scale",
                property_type="scale",
                keyframes=[
                    Keyframe(start, [50, 50], ease_out=EaseType.EASE_OUT_ELASTIC),
                    Keyframe(start + duration, [100, 100]),
                ],
            ),
        ]

    def _build_blur_in_text(self, start, duration, char_count, stagger, magnitude):
        """模糊显现"""
        return [
            AnimationTrack(
                property_path="ADBE Text Properties/Animators/Animator 1/Opacity",
                property_type="float",
                keyframes=[Keyframe(start, 0), Keyframe(start + duration, 100)],
            ),
            AnimationTrack(
                property_path="ADBE Text Properties/Animators/Animator 1/Blur",
                property_type="float",
                keyframes=[
                    Keyframe(start, magnitude),
                    Keyframe(start + duration, 0),
                ],
            ),
        ]

    def _build_flip_3d_text(self, start, duration, char_count, stagger, magnitude):
        """3D翻转文字"""
        return [
            AnimationTrack(
                property_path="ADBE Text Properties/Animators/Animator 1/Rotation",
                property_type="float",
                keyframes=[
                    Keyframe(start, 90, ease_out=EaseType.EASE_OUT_QUAD),
                    Keyframe(start + duration, 0),
                ],
            ),
            AnimationTrack(
                property_path="ADBE Text Properties/Animators/Animator 1/Opacity",
                property_type="float",
                keyframes=[Keyframe(start, 0), Keyframe(start + duration * 0.5, 100),
                           Keyframe(start + duration, 100)],
            ),
        ]

    def _build_pulse_glow_text(self, start, duration, char_count, stagger, magnitude):
        """脉冲发光文字 — opacity呼吸+scale微胀缩"""
        tracks = []
        n_pulse = max(2, int(duration / 0.3))
        op_kfs, sc_kfs = [], []
        for i in range(n_pulse):
            t = start + duration * i / n_pulse
            op_kfs.append(Keyframe(t, 100))
            op_kfs.append(Keyframe(t + duration / n_pulse * 0.5, 70))
            sc_kfs.append(Keyframe(t, [100, 100]))
            sc_kfs.append(Keyframe(t + duration / n_pulse * 0.5, [100 + magnitude * 0.1, 100 + magnitude * 0.1]))
        op_kfs.append(Keyframe(start + duration, 100))
        sc_kfs.append(Keyframe(start + duration, [100, 100]))
        tracks.append(AnimationTrack(
            property_path="ADBE Text Properties/Animators/Animator 1/Opacity",
            property_type="float", keyframes=op_kfs,
        ))
        tracks.append(AnimationTrack(
            property_path="ADBE Text Properties/Animators/Animator 1/Scale",
            property_type="scale", keyframes=sc_kfs,
        ))
        return tracks

    def _build_spring_scale(self, start, duration, char_count, stagger, magnitude):
        """弹性缩放 — 从0弹到100%"""
        return [AnimationTrack(
            property_path="ADBE Text Properties/Animators/Animator 1/Scale",
            property_type="scale",
            keyframes=[
                Keyframe(start, [0, 0], ease_out=EaseType.EASE_OUT_ELASTIC),
                Keyframe(start + duration, [100, 100]),
            ],
        )]

    def _build_cascade_fall(self, start, duration, char_count, stagger, magnitude):
        """级联下落 — 从上方依次落下"""
        return [
            AnimationTrack(
                property_path="ADBE Text Properties/Animators/Animator 1/Position",
                property_type="position",
                keyframes=[
                    Keyframe(start, [0, -magnitude * 3, 0], ease_out=EaseType.EASE_OUT_BOUNCE),
                    Keyframe(start + duration, [0, 0, 0]),
                ],
            ),
            AnimationTrack(
                property_path="ADBE Text Properties/Animators/Animator 1/Opacity",
                property_type="float",
                keyframes=[Keyframe(start, 0), Keyframe(start + duration * 0.4, 100),
                           Keyframe(start + duration, 100)],
            ),
        ]

    def _build_kinetic_typing(self, start, duration, char_count, stagger, magnitude):
        """动态打字 — 大小写交替+位移跳动"""
        tracks = []
        n_step = max(3, min(10, int(duration / 0.15)))
        pos_kfs, sc_kfs = [Keyframe(start, [0, 0, 0])], [Keyframe(start, [100, 100])]
        for i in range(1, n_step):
            t = start + duration * i / n_step
            py = self._rng.choice([-1, 1]) * self._rng.uniform(5, magnitude * 0.4)
            pos_kfs.append(Keyframe(t, [0, py, 0]))
            sv = self._rng.uniform(90, 120)
            sc_kfs.append(Keyframe(t, [sv, sv]))
        pos_kfs.append(Keyframe(start + duration, [0, 0, 0]))
        sc_kfs.append(Keyframe(start + duration, [100, 100]))
        tracks.append(AnimationTrack(
            property_path="ADBE Text Properties/Animators/Animator 1/Position",
            property_type="position", keyframes=pos_kfs,
        ))
        tracks.append(AnimationTrack(
            property_path="ADBE Text Properties/Animators/Animator 1/Scale",
            property_type="scale", keyframes=sc_kfs,
        ))
        tracks.append(AnimationTrack(
            property_path="ADBE Text Properties/Animators/Animator 1/Opacity",
            property_type="float",
            keyframes=[Keyframe(start, 0), Keyframe(start + duration * 0.3, 100),
                       Keyframe(start + duration, 100)],
        ))
        return tracks

    # ---- V3 新增 16 种 ----

    def _build_elastic_overshoot(self, start, duration, char_count, stagger, magnitude):
        """弹性过冲 — Scale多次回弹收敛 + 表达式余震"""
        return [AnimationTrack(
            property_path="ADBE Text Properties/Animators/Animator 1/Scale",
            property_type="scale",
            keyframes=[
                Keyframe(start, [0, 0]),
                Keyframe(start + duration * 0.3, [120, 120], ease_out=EaseType.EASE_OUT_ELASTIC),
                Keyframe(start + duration * 0.5, [95, 95]),
                Keyframe(start + duration * 0.65, [103, 103]),
                Keyframe(start + duration, [100, 100]),
            ],
        )]

    def _build_squash_stretch(self, start, duration, char_count, stagger, magnitude):
        """挤压拉伸 — 先纵后横卡通弹性"""
        return [AnimationTrack(
            property_path="ADBE Text Properties/Animators/Animator 1/Scale",
            property_type="scale",
            keyframes=[
                Keyframe(start, [0, 0]),
                Keyframe(start + duration * 0.15, [60, 140]),
                Keyframe(start + duration * 0.3, [130, 80]),
                Keyframe(start + duration * 0.45, [95, 105]),
                Keyframe(start + duration * 0.55, [100, 100]),
            ],
        )]

    def _build_spiral_entrance(self, start, duration, char_count, stagger, magnitude):
        """螺旋入场 — 旋转-360°+缩放0→100%"""
        return [
            AnimationTrack(
                property_path="ADBE Text Properties/Animators/Animator 1/Rotation",
                property_type="float",
                keyframes=[
                    Keyframe(start, -360, ease_out=EaseType.EASE_OUT_ELASTIC),
                    Keyframe(start + duration, 0),
                ],
            ),
            AnimationTrack(
                property_path="ADBE Text Properties/Animators/Animator 1/Scale",
                property_type="scale",
                keyframes=[
                    Keyframe(start, [0, 0], ease_out=EaseType.EASE_OUT_ELASTIC),
                    Keyframe(start + duration, [100, 100]),
                ],
            ),
            AnimationTrack(
                property_path="ADBE Text Properties/Animators/Animator 1/Opacity",
                property_type="float",
                keyframes=[Keyframe(start, 0), Keyframe(start + duration * 0.3, 100),
                           Keyframe(start + duration, 100)],
            ),
        ]

    def _build_per_char_wave(self, start, duration, char_count, stagger, magnitude):
        """逐字波浪 — 基线偏移传播"""
        return [AnimationTrack(
            property_path="ADBE Text Properties/Animators/Animator 1/Position",
            property_type="position",
            keyframes=[
                Keyframe(start, [0, magnitude * 0.8, 0], ease_out=EaseType.EASE_OUT_ELASTIC),
                Keyframe(start + duration * 0.5, [0, -magnitude * 0.8, 0]),
                Keyframe(start + duration, [0, 0, 0]),
            ],
        )]

    def _build_random_pop(self, start, duration, char_count, stagger, magnitude):
        """随机弹出 — 随机顺序放大200%后回弹"""
        return [
            AnimationTrack(
                property_path="ADBE Text Properties/Animators/Animator 1/Scale",
                property_type="scale",
                keyframes=[
                    Keyframe(start, [0, 0], ease_out=EaseType.EASE_OUT_ELASTIC),
                    Keyframe(start + duration * 0.4, [150, 150]),
                    Keyframe(start + duration * 0.7, [95, 95]),
                    Keyframe(start + duration, [100, 100]),
                ],
            ),
            AnimationTrack(
                property_path="ADBE Text Properties/Animators/Animator 1/Opacity",
                property_type="float",
                keyframes=[Keyframe(start, 0), Keyframe(start + duration * 0.2, 100),
                           Keyframe(start + duration, 100)],
            ),
        ]

    def _build_domino_fall(self, start, duration, char_count, stagger, magnitude):
        """多米诺骨牌 — 逐字旋转90°倒下"""
        return [
            AnimationTrack(
                property_path="ADBE Text Properties/Animators/Animator 1/Rotation",
                property_type="float",
                keyframes=[
                    Keyframe(start, 90, ease_out=EaseType.EASE_OUT_BOUNCE),
                    Keyframe(start + duration, 0),
                ],
            ),
            AnimationTrack(
                property_path="ADBE Text Properties/Animators/Animator 1/Opacity",
                property_type="float",
                keyframes=[Keyframe(start, 0), Keyframe(start + duration * 0.3, 100),
                           Keyframe(start + duration, 100)],
            ),
        ]

    def _build_scatter_converge(self, start, duration, char_count, stagger, magnitude):
        """散点汇聚 — 从随机位置汇聚到最终位置"""
        tracks = []
        n_scatter = max(3, int(duration / 0.15))
        pos_kfs = []
        for i in range(n_scatter):
            t = start + duration * i / n_scatter
            scatter = 1.0 - (i / n_scatter)
            px = self._rng.uniform(-magnitude * 3, magnitude * 3) * scatter
            py = self._rng.uniform(-magnitude * 2, magnitude * 2) * scatter
            pos_kfs.append(Keyframe(t, [px, py, 0]))
        pos_kfs.append(Keyframe(start + duration, [0, 0, 0]))
        tracks.append(AnimationTrack(
            property_path="ADBE Text Properties/Animators/Animator 1/Position",
            property_type="position", keyframes=pos_kfs,
        ))
        tracks.append(AnimationTrack(
            property_path="ADBE Text Properties/Animators/Animator 1/Opacity",
            property_type="float",
            keyframes=[Keyframe(start, 0), Keyframe(start + duration * 0.4, 100),
                       Keyframe(start + duration, 100)],
        ))
        return tracks

    def _build_stroke_draw(self, start, duration, char_count, stagger, magnitude):
        """描边绘制 — 描边宽度从0逐字揭示"""
        return [AnimationTrack(
            property_path="ADBE Text Properties/Animators/Animator 1/Stroke Width",
            property_type="float",
            keyframes=[
                Keyframe(start, 0),
                Keyframe(start + duration * 0.6, magnitude * 0.06),
                Keyframe(start + duration, magnitude * 0.04),
            ],
        )]

    def _build_color_wipe(self, start, duration, char_count, stagger, magnitude):
        """色彩擦除 — 填充色渐变过渡"""
        return [
            AnimationTrack(
                property_path="ADBE Text Properties/Animators/Animator 1/Fill Color",
                property_type="color",
                keyframes=[
                    Keyframe(start, [1.0, 0.2, 0.4]),
                    Keyframe(start + duration * 0.5, [0.2, 0.8, 1.0]),
                    Keyframe(start + duration, [1.0, 1.0, 1.0]),
                ],
            ),
            AnimationTrack(
                property_path="ADBE Text Properties/Animators/Animator 1/Opacity",
                property_type="float",
                keyframes=[Keyframe(start, 0), Keyframe(start + duration * 0.3, 100),
                           Keyframe(start + duration, 100)],
            ),
        ]

    def _build_letter_pop(self, start, duration, char_count, stagger, magnitude):
        """逐字弹出 — 放大150%后回弹"""
        return [AnimationTrack(
            property_path="ADBE Text Properties/Animators/Animator 1/Scale",
            property_type="scale",
            keyframes=[
                Keyframe(start, [50, 50], ease_out=EaseType.EASE_OUT_ELASTIC),
                Keyframe(start + duration * 0.3, [150, 150]),
                Keyframe(start + duration * 0.6, [90, 90]),
                Keyframe(start + duration, [100, 100]),
            ],
        )]

    def _build_baseline_shift(self, start, duration, char_count, stagger, magnitude):
        """基线波浪 — 上下浮动"""
        n_wave = max(4, int(duration / 0.12))
        shift_kfs = []
        for i in range(n_wave):
            t = start + duration * i / n_wave
            shift = math.sin(i * 0.8) * magnitude * 0.6
            shift_kfs.append(Keyframe(t, shift))
        shift_kfs.append(Keyframe(start + duration, 0))
        return [AnimationTrack(
            property_path="ADBE Text Properties/Animators/Animator 1/Baseline Shift",
            property_type="float", keyframes=shift_kfs,
        )]

    def _build_zoom_blur_rush(self, start, duration, char_count, stagger, magnitude):
        """缩放模糊冲入 — 从大+模糊到正常+清晰"""
        return [
            AnimationTrack(
                property_path="ADBE Text Properties/Animators/Animator 1/Scale",
                property_type="scale",
                keyframes=[
                    Keyframe(start, [200, 200], ease_out=EaseType.EASE_OUT_QUAD),
                    Keyframe(start + duration, [100, 100]),
                ],
            ),
            AnimationTrack(
                property_path="ADBE Text Properties/Animators/Animator 1/Blur",
                property_type="float",
                keyframes=[
                    Keyframe(start, magnitude),
                    Keyframe(start + duration, 0),
                ],
            ),
            AnimationTrack(
                property_path="ADBE Text Properties/Animators/Animator 1/Opacity",
                property_type="float",
                keyframes=[Keyframe(start, 0), Keyframe(start + duration * 0.3, 100),
                           Keyframe(start + duration, 100)],
            ),
        ]

    def _build_swipe_slide(self, start, duration, char_count, stagger, magnitude):
        """擦除滑入 — 位置滑入+透明度"""
        return [
            AnimationTrack(
                property_path="ADBE Text Properties/Animators/Animator 1/Position",
                property_type="position",
                keyframes=[
                    Keyframe(start, [-magnitude * 3, 0, 0], ease_out=EaseType.EASE_OUT_QUAD),
                    Keyframe(start + duration, [0, 0, 0]),
                ],
            ),
            AnimationTrack(
                property_path="ADBE Text Properties/Animators/Animator 1/Opacity",
                property_type="float",
                keyframes=[
                    Keyframe(start, 0),
                    Keyframe(start + duration * 0.25, 100),
                    Keyframe(start + duration, 100),
                ],
            ),
        ]

    def _build_neon_flicker(self, start, duration, char_count, stagger, magnitude):
        """霓虹闪烁 — 透明度+颜色脉冲"""
        tracks = []
        n_flick = max(4, int(duration / 0.15))
        op_kfs = []
        for i in range(n_flick):
            t = start + duration * i / n_flick
            op_val = 100 if i % 3 != 0 else self._rng.randint(40, 70)
            op_kfs.append(Keyframe(t, op_val))
        op_kfs.append(Keyframe(start + duration, 100))
        tracks.append(AnimationTrack(
            property_path="ADBE Text Properties/Animators/Animator 1/Opacity",
            property_type="float", keyframes=op_kfs,
        ))
        tracks.append(AnimationTrack(
            property_path="ADBE Text Properties/Animators/Animator 1/Fill Color",
            property_type="color",
            keyframes=[
                Keyframe(start, [1.0, 0.3, 0.6]),
                Keyframe(start + duration * 0.5, [0.3, 0.8, 1.0]),
                Keyframe(start + duration, [1.0, 0.5, 0.8]),
            ],
        ))
        return tracks

    def _build_impact_shake(self, start, duration, char_count, stagger, magnitude):
        """冲击震动 — Scale过冲130%+多次Position回弹"""
        tracks = []
        n_shake = max(4, int(duration / 0.08))
        pos_kfs = []
        for i in range(n_shake):
            t = start + duration * i / n_shake
            decay = 1.0 - (i / n_shake)
            jx = self._rng.uniform(-magnitude * 0.4, magnitude * 0.4) * decay
            jy = self._rng.uniform(-magnitude * 0.3, magnitude * 0.3) * decay
            pos_kfs.append(Keyframe(t, [jx, jy, 0]))
        pos_kfs.append(Keyframe(start + duration, [0, 0, 0]))
        tracks.append(AnimationTrack(
            property_path="ADBE Text Properties/Animators/Animator 1/Position",
            property_type="position", keyframes=pos_kfs,
        ))
        tracks.append(AnimationTrack(
            property_path="ADBE Text Properties/Animators/Animator 1/Scale",
            property_type="scale",
            keyframes=[
                Keyframe(start, [0, 0]),
                Keyframe(start + duration * 0.15, [130, 130]),
                Keyframe(start + duration * 0.35, [90, 90]),
                Keyframe(start + duration * 0.55, [105, 105]),
                Keyframe(start + duration, [100, 100]),
            ],
        ))
        tracks.append(AnimationTrack(
            property_path="ADBE Text Properties/Animators/Animator 1/Opacity",
            property_type="float",
            keyframes=[Keyframe(start, 0), Keyframe(start + duration * 0.1, 100),
                       Keyframe(start + duration, 100)],
        ))
        return tracks

    def _build_float_up(self, start, duration, char_count, stagger, magnitude):
        """悬浮上升 — 缓慢上升+微浮动"""
        return [
            AnimationTrack(
                property_path="ADBE Text Properties/Animators/Animator 1/Position",
                property_type="position",
                keyframes=[
                    Keyframe(start, [0, magnitude * 1.5, 0], ease_out=EaseType.EASE_OUT_QUAD),
                    Keyframe(start + duration * 0.7, [0, 0, 0]),
                    Keyframe(start + duration, [0, -magnitude * 0.1, 0]),
                ],
            ),
            AnimationTrack(
                property_path="ADBE Text Properties/Animators/Animator 1/Opacity",
                property_type="float",
                keyframes=[
                    Keyframe(start, 0),
                    Keyframe(start + duration * 0.4, 100),
                    Keyframe(start + duration, 100),
                ],
            ),
        ]


# ============================================================
# 3. 节拍同步动画器 (BeatSyncAnimator)
# ============================================================

class BeatSyncAnimator:
    """音乐节拍同步动画 — 漫剪管线的核心差异化能力
    
    根据BeatTiming列表生成多层同步动画：
    - 每个节拍触发opacity脉冲
    - 每个节拍触发scale脉冲
    - 支持不同强度的节拍产生不同幅度
    """
    
    def __init__(self):
        self.min_pulse_scale = 1.0
        self.max_pulse_scale = 1.15    # 最大缩放幅度
        self.pulse_duration = 0.08     # 脉冲持续（秒）
        self.pulse_recovery = 0.12     # 脉冲恢复（秒）
    
    def build_beat_pulses(
        self,
        beats: List[BeatTiming],
        layer_start: float = 0.0,
        amplitude: float = 1.0,
        properties: Optional[List[str]] = None,
    ) -> List[AnimationTrack]:
        """根据节拍列表生成脉冲动画轨道
        
        Args:
            beats: 节拍时间列表
            layer_start: 层起始时间
            amplitude: 全局幅度系数
            properties: 需要脉冲的属性，默认['opacity', 'scale']
            
        Returns:
            List[AnimationTrack]: 脉冲动画轨道
        """
        if not beats:
            return []
        
        properties = properties or ["opacity", "scale"]
        tracks = []
        
        if "opacity" in properties:
            tracks.append(self._build_opacity_pulses(beats, layer_start, amplitude))
        
        if "scale" in properties:
            tracks.append(self._build_scale_pulses(beats, layer_start, amplitude))
        
        return tracks
    
    def _build_opacity_pulses(self, beats: List[BeatTiming], 
                              layer_start: float, amplitude: float) -> AnimationTrack:
        """build opacity pulses for each beat"""
        kfs = [Keyframe(layer_start, 100)]  # 起始帧
        last_time = layer_start
        
        for beat in beats:
            t = beat.time
            str_adj = beat.strength * amplitude
            
            # 脉冲值: 基础100 + 强度*幅度*额外亮度
            pulse_val = 100 + str_adj * 20  # max +20 opacity
            
            # 脉冲上升
            kfs.append(Keyframe(t, pulse_val, 
                                ease_in=EaseType.LINEAR, 
                                ease_out=EaseType.LINEAR))
            # 脉冲恢复
            kfs.append(Keyframe(t + self.pulse_duration, 105,
                                ease_out=EaseType.EASE_OUT_QUAD))
            kfs.append(Keyframe(t + self.pulse_duration + self.pulse_recovery, 100))
            
            last_time = t + self.pulse_duration + self.pulse_recovery
        
        return AnimationTrack(
            property_path="Transform/Opacity",
            property_type="float",
            keyframes=kfs,
        )
    
    def _build_scale_pulses(self, beats: List[BeatTiming],
                            layer_start: float, amplitude: float) -> AnimationTrack:
        """build scale pulses for each beat"""
        kfs = [Keyframe(layer_start, [100, 100, 100])]
        
        for beat in beats:
            t = beat.time
            str_adj = beat.strength * amplitude
            
            pulse_scale = 100 + str_adj * (self.max_pulse_scale - self.min_pulse_scale) * 100
            
            kfs.append(Keyframe(t, [pulse_scale, pulse_scale, 100],
                                ease_in=EaseType.LINEAR,
                                ease_out=EaseType.LINEAR))
            kfs.append(Keyframe(t + self.pulse_duration, [105, 105, 100],
                                ease_out=EaseType.EASE_OUT_QUAD))
            kfs.append(Keyframe(t + self.pulse_duration + self.pulse_recovery, 
                                [100, 100, 100]))
        
        return AnimationTrack(
            property_path="Transform/Scale",
            property_type="scale",
            keyframes=kfs,
        )
    
    def build_sine_breath(
        self,
        total_duration: float,
        freq: float = 0.5,
        amplitude: float = 0.1,
        sample_rate: float = 0.1,
    ) -> AnimationTrack:
        """正弦呼吸效果 — 匀速缓慢的缩放呼吸
        
        适用于氛围类漫剪（cinematic, ambient风格）
        """
        # 防御：非法采样率会导致无限循环 / 无界分配
        if sample_rate <= 0:
            sample_rate = 0.1
        if total_duration < 0:
            total_duration = 0.0
        # 硬上限：最多 600 关键帧（约 60s @ 0.1s），防止内存爆炸
        max_keyframes = 600

        kfs = []
        t = 0.0
        count = 0
        while t <= total_duration and count < max_keyframes:
            val = 100 + amplitude * 100 * math.sin(2 * math.pi * freq * t)
            kfs.append(Keyframe(t, [val, val, 100]))
            t += sample_rate
            count += 1
        
        return AnimationTrack(
            property_path="Transform/Scale",
            property_type="scale",
            keyframes=kfs,
        )
    
    def build_drop_decay(
        self,
        beat_time: float,
        decay_duration: float = 0.3,
        amplitude: float = 0.3,
    ) -> AnimationTrack:
        """衰减脉冲 — 节拍后快速衰减（模拟底鼓后效）"""
        kfs = [
            Keyframe(beat_time, [100, 100, 100]),
            Keyframe(beat_time + 0.02, [100 + amplitude * 100, 100 + amplitude * 100, 100]),
            Keyframe(beat_time + decay_duration, [100, 100, 100]),
        ]
        return AnimationTrack(
            property_path="Transform/Scale",
            property_type="scale",
            keyframes=kfs,
        )


# ============================================================
# 4. 运镜模拟器 (CameraAnimator)
# ============================================================

class CameraAnimator:
    """摄像机运动模拟 — 为2D层模拟摄像机运动效果
    
    AMV/漫剪风格中，运镜是核心差异化手段：
    - Ken Burns: 缓慢推拉 + 轻微平移
    - Whip Pan: 快速滑动切换
    - Dolly Zoom: 前景放大+背景不变/收缩
    - Handheld Shake: 手持晃动模拟
    """
    
    def __init__(self):
        pass
    
    def build_camera_tracks(
        self,
        style: CameraStyle,
        layer_duration: float,
        layer_start: float = 0.0,
        intensity: float = 1.0,
    ) -> List[AnimationTrack]:
        """生成运镜关键帧轨道"""
        if style == CameraStyle.KEN_BURNS:
            return self._build_ken_burns(layer_start, layer_duration, intensity)
        elif style == CameraStyle.WHIP_PAN:
            return self._build_whip_pan(layer_start, layer_duration)
        elif style == CameraStyle.DOLLY_ZOOM:
            return self._build_dolly_zoom(layer_start, layer_duration, intensity)
        elif style == CameraStyle.HANDHELD_SHAKE:
            return self._build_handheld_shake(layer_start, layer_duration, intensity)
        elif style == CameraStyle.PUSH_IN:
            return self._build_push_in(layer_start, layer_duration, intensity)
        elif style == CameraStyle.PULL_OUT:
            return self._build_pull_out(layer_start, layer_duration, intensity)
        
        return []
    
    def _build_ken_burns(self, start: float, duration: float, 
                         intensity: float) -> List[AnimationTrack]:
        """Ken Burns效果 — 缓慢缩放 + 随机平移"""
        tracks = []
        
        # 缩放: 100%→110% 或 115%→100%
        if self._rng.random() > 0.5:
            tracks.append(AnimationTrack(
                property_path="Transform/Scale",
                property_type="scale",
                keyframes=[
                    Keyframe(start, [100, 100, 100]),
                    Keyframe(start + duration, [100 + 10 * intensity, 
                                                  100 + 10 * intensity, 100]),
                ],
            ))
        else:
            tracks.append(AnimationTrack(
                property_path="Transform/Scale",
                property_type="scale",
                keyframes=[
                    Keyframe(start, [100 + 15 * intensity, 100 + 15 * intensity, 100]),
                    Keyframe(start + duration, [100, 100, 100]),
                ],
            ))
        
        # 位置轻微平移
        pan_x = self._rng.randint(-30, 30) * intensity
        pan_y = self._rng.randint(-20, 20) * intensity
        tracks.append(AnimationTrack(
            property_path="Transform/Position",
            property_type="position",
            keyframes=[
                Keyframe(start, [0, 0, 0]),
                Keyframe(start + duration, [pan_x, pan_y, 0]),
            ],
        ))
        
        return tracks
    
    def _build_whip_pan(self, start: float, duration: float) -> List[AnimationTrack]:
        """快速甩镜 — 极快滑动+运动模糊"""
        direction = self._rng.choice([[-400, 0, 0], [400, 0, 0], [0, -300, 0], [0, 300, 0]])
        
        tracks = [AnimationTrack(
            property_path="Transform/Position",
            property_type="position",
            keyframes=[
                Keyframe(start, direction),
                Keyframe(start + duration * 0.7, 
                         [-direction[0]*0.1, -direction[1]*0.1, 0],
                         ease_out=EaseType.EASE_OUT_QUAD),
                Keyframe(start + duration, [0, 0, 0]),
            ],
        )]
        return tracks
    
    def _build_dolly_zoom(self, start: float, duration: float,
                          intensity: float) -> List[AnimationTrack]:
        """Dolly Zoom — 反向缩放（缩放+反方向位置补偿）"""
        tracks = []
        
        # 缩放放大
        tracks.append(AnimationTrack(
            property_path="Transform/Scale",
            property_type="scale",
            keyframes=[
                Keyframe(start, [100, 100, 100]),
                Keyframe(start + duration, [100 + 25 * intensity, 
                                              100 + 25 * intensity, 100]),
            ],
        ))
        
        # 位置补偿（缩放时轻微向上平移模拟背景远离）
        tracks.append(AnimationTrack(
            property_path="Transform/Position",
            property_type="position",
            keyframes=[
                Keyframe(start, [0, 0, 0]),
                Keyframe(start + duration, [0, 20 * intensity, 0]),
            ],
        ))
        
        return tracks
    
    def _build_handheld_shake(self, start: float, duration: float,
                              intensity: float) -> List[AnimationTrack]:
        """手持晃动 — 高频小幅度随机位置晃动"""
        kfs = []
        sample_rate = 0.05  # 20Hz抖动采样
        # 防御：非法 duration 导致无界分配
        if duration < 0:
            duration = 0.0
        max_keyframes = 1200  # 约 60s @ 20Hz
        t = start
        count = 0
        end = start + duration
        while t <= end and count < max_keyframes:
            shake_x = self._rng.uniform(-5, 5) * intensity
            shake_y = self._rng.uniform(-3, 3) * intensity
            kfs.append(Keyframe(t, [shake_x, shake_y, 0]))
            t += sample_rate
            count += 1
        
        return [AnimationTrack(
            property_path="Transform/Position",
            property_type="position",
            keyframes=kfs,
        )]
    
    def _build_push_in(self, start: float, duration: float,
                       intensity: float) -> List[AnimationTrack]:
        """推进 — 从正常推近到特写"""
        return [AnimationTrack(
            property_path="Transform/Scale",
            property_type="scale",
            keyframes=[
                Keyframe(start, [100, 100, 100]),
                Keyframe(start + duration, [100 + 20 * intensity,
                                              100 + 20 * intensity, 100]),
            ],
        )]
    
    def _build_pull_out(self, start: float, duration: float,
                        intensity: float) -> List[AnimationTrack]:
        """拉远 — 从特写拉远到广角"""
        return [AnimationTrack(
            property_path="Transform/Scale",
            property_type="scale",
            keyframes=[
                Keyframe(start, [100 + 25 * intensity, 100 + 25 * intensity, 100]),
                Keyframe(start + duration, [100, 100, 100]),
            ],
        )]
    
    def select_camera_for_style(self, style_category: str, 
                                has_beats: bool = False) -> CameraStyle:
        """根据漫剪风格类别智能选择运镜"""
        style_map = {
            "amv_pull_zoom": CameraStyle.PUSH_IN,
            "amv_fast_cut": CameraStyle.WHIP_PAN if has_beats else CameraStyle.PUSH_IN,
            "amv_beat_sync": CameraStyle.PUSH_IN,
            "amv_korean_flash": CameraStyle.PUSH_IN,
            "amv_glitch": CameraStyle.HANDHELD_SHAKE,
            "amv_cinematic": CameraStyle.KEN_BURNS,
            "amv_3d_spatial": CameraStyle.DOLLY_ZOOM,
            "amv_high_burn": CameraStyle.PUSH_IN,
        }
        return style_map.get(style_category, CameraStyle.KEN_BURNS)


# ============================================================
# 5. 效果脉冲动画器 (EffectPulseAnimator)
# ============================================================

class EffectPulseAnimator:
    """效果参数动态脉冲 — 让静态效果"活"起来
    
    支持的效果参数脉冲：
    - Glow: intensity/threshold 随时间脉动
    - Blur: blurriness 随节拍变化
    - Hue/Saturation: 颜色周期性变化
    - Lens Flare: brightness 闪烁
    """
    
    def __init__(self):
        pass
    
    def build_glow_pulse(
        self,
        effect_path: str,
        duration: float,
        start: float = 0.0,
        pulse_amplitude: float = 0.2,
        pulse_freq: float = 1.0,
    ) -> AnimationTrack:
        """Glow强度脉冲 — 漫剪常见的效果动态化
        
        Args:
            effect_path: AE效果属性路径，如 "Effects/Glow/Glow Intensity"
            duration: 脉冲持续时间
            start: 开始时间
            pulse_amplitude: 脉冲幅度（相对比例）
            pulse_freq: 脉冲频率（Hz）
        """
        kfs = []
        t = start
        sample = 0.1
        if duration < 0:
            duration = 0.0
        max_keyframes = 600
        count = 0
        end = start + duration
        while t <= end and count < max_keyframes:
            # 正弦波脉冲：base + amplitude * sin
            phase = (t - start) * pulse_freq * 2 * math.pi
            val = 1.0 + pulse_amplitude * math.sin(phase)
            kfs.append(Keyframe(t, round(val, 3)))
            t += sample
            count += 1
        
        return AnimationTrack(
            property_path=effect_path,
            property_type="float",
            keyframes=kfs,
        )
    
    def build_blur_rack(
        self,
        effect_path: str,
        duration: float,
        start: float = 0.0,
        max_blur: float = 20,
        min_blur: float = 0,
    ) -> AnimationTrack:
        """模糊变焦效果 — 从模糊到清晰（常用于转场）"""
        return AnimationTrack(
            property_path=effect_path,
            property_type="float",
            keyframes=[
                Keyframe(start, max_blur),
                Keyframe(start + duration * 0.4, min_blur, ease_out=EaseType.EASE_OUT_QUAD),
                Keyframe(start + duration, min_blur),
            ],
        )
    
    def build_color_wash(
        self,
        effect_path: str,
        duration: float,
        start: float = 0.0,
        colors: Optional[List[List[float]]] = None,
    ) -> AnimationTrack:
        """颜色冲刷 — Hue周期性变化"""
        if colors is None:
            # 默认使用R→G→B循环
            colors = [[0, 100, 100], [120, 100, 100], [240, 100, 100]]
        
        kfs = []
        for i, color in enumerate(colors):
            t = start + duration * i / len(colors)
            kfs.append(Keyframe(t, color))
        
        return AnimationTrack(
            property_path=effect_path,
            property_type="color",
            keyframes=kfs,
        )
    
    def build_effect_beat_pulse(
        self,
        effect_path: str,
        beats: List[BeatTiming],
        start: float = 0.0,
        pulse_magnitude: float = 0.3,
    ) -> Optional[AnimationTrack]:
        """效果参数随节拍脉冲"""
        if not beats:
            return None
        
        kfs = []
        for beat in beats:
            str_mag = beat.strength * pulse_magnitude
            kfs.append(Keyframe(beat.time, 1.0 + str_mag))
            kfs.append(Keyframe(beat.time + 0.05, 1.0 - str_mag * 0.3))
            kfs.append(Keyframe(beat.time + 0.15, 1.0))
        
        return AnimationTrack(
            property_path=effect_path,
            property_type="float",
            keyframes=kfs,
        )


# ============================================================
# 6-A. AE安全字体管理
# ============================================================

# AE ExtendScript 不支持带空格的字体名，必须用无空格版本
AE_SAFE_FONTS = {
    "Arial": "Arial",
    "Arial Narrow": "ArialNarrow",
    "Arial Black": "ArialBlack",
    "Arial Bold": "Arial-BoldMT",
    "Microsoft YaHei": "MicrosoftYaHei",
    "Microsoft YaHei Bold": "MicrosoftYaHeiBold",
    "SimHei": "SimHei",
    "SimSun": "SimSun",
    "KaiTi": "KaiTi",
    "Impact": "Impact",
    "Courier New": "CourierNewPSMT",
    "Times New Roman": "TimesNewRomanPSMT",
    "Trebuchet MS": "TrebuchetMS",
    "Comic Sans MS": "ComicSansMS",
    # FONT_LIBRARY 覆盖（50款精选字体的显示名映射）
    "Consolas": "Consolas",
    "YouYuan": "YouYuan",
    "Helvetica": "Helvetica",
    "Georgia Bold": "Georgia-Bold",
    "DengXian Bold": "DengXian-Bold",
    "FangSong": "FangSong",
    "LiSu": "LiSu",
    "STHeiti": "STHeiti",
    "STKaiti": "STKaiti",
    "STSong": "STSong",
    "STXihei": "STXihei",
    "Ma Shan Zheng": "MaShanZheng",
    "Noto Sans SC": "NotoSansSC-VF",
    "Noto Serif SC": "NotoSerifSC-VF",
    "Alibaba PuHuiTi Bold": "AlibabaPuHuiTi-3-85-Bold",
    "Alibaba PuHuiTi Light": "AlibabaPuHuiTi-3-45-Light",
    "FZ CuHeiSong": "FZCuHeiSongS-B-GB",
    "FZ ZhengHei": "FZZhengHei-M-02",
    "DIN Next": "DINNextLTPro-Regular",
    "Bebas Neue": "BebasNeue",
    "Black Ops One": "BlackOpsOne",
    "Fredoka One": "FredokaOne",
    "Luckiest Guy": "LuckiestGuy",
    "Oswald Bold": "Oswald-Bold",
    "Playfair Display": "PlayfairDisplay",
    "Dancing Script": "DancingScript",
    "Great Vibes": "GreatVibes",
}

def ae_safe_font_name(display_name: str) -> str:
    """将显示字体名转为AE ExtendScript安全名称"""
    return AE_SAFE_FONTS.get(display_name, display_name.replace(" ", ""))


# ============================================================
# 6-B. 文字动画预设注册表（20种）+ 覆盖率追踪
# ============================================================

ALL_TEXT_STYLES: List[TextAnimationStyle] = list(TextAnimationStyle)

# 风格分组（用于智能选择）
_STYLE_GROUPS = {
    "entrance": [
        TextAnimationStyle.FADE_UP_STAGGER, TextAnimationStyle.DROP_BOUNCE,
        TextAnimationStyle.SLIDE_IN_STAGGER, TextAnimationStyle.SLIDE_RIGHT_STAGGER,
        TextAnimationStyle.WAVE_ENTRANCE, TextAnimationStyle.ROTATE_IN_STAGGER,
        TextAnimationStyle.SCALE_DOWN_BOUNCE, TextAnimationStyle.CASCADE_FALL,
        TextAnimationStyle.SPRING_SCALE, TextAnimationStyle.FADE_SCALE_COMBO,
        TextAnimationStyle.BLUR_IN_TEXT, TextAnimationStyle.FLIP_3D_TEXT,
        # V3 入场类
        TextAnimationStyle.ELASTIC_OVERSHOOT, TextAnimationStyle.SQUASH_STRETCH,
        TextAnimationStyle.SPIRAL_ENTRANCE, TextAnimationStyle.RANDOM_POP,
        TextAnimationStyle.DOMINO_FALL, TextAnimationStyle.SCATTER_CONVERGE,
        TextAnimationStyle.STROKE_DRAW, TextAnimationStyle.COLOR_WIPE,
        TextAnimationStyle.LETTER_POP, TextAnimationStyle.ZOOM_BLUR_RUSH,
        TextAnimationStyle.SWIPE_SLIDE, TextAnimationStyle.FLOAT_UP,
    ],
    "continuous": [
        TextAnimationStyle.TYPEWRITER, TextAnimationStyle.TRACKING,
        TextAnimationStyle.OPACITY_RANDOM, TextAnimationStyle.SCALE_PER_CHAR,
        TextAnimationStyle.POSITION_JITTER, TextAnimationStyle.GLITCH_TEXT,
        TextAnimationStyle.PULSE_GLOW_TEXT, TextAnimationStyle.KINETIC_TYPING,
        # V3 持续类
        TextAnimationStyle.PER_CHAR_WAVE, TextAnimationStyle.BASELINE_SHIFT,
        TextAnimationStyle.NEON_FLICKER, TextAnimationStyle.IMPACT_SHAKE,
    ],
}


class PresetTracker:
    """文字动画预设覆盖率追踪器"""

    def __init__(self):
        self._usage: Dict[str, int] = {s.value: 0 for s in TextAnimationStyle}
        self._history: List[str] = []
        # 【P2-3】三维组合覆盖追踪: 特效×动画×字体
        self._combos: Dict[str, int] = {}

    def record(self, style: TextAnimationStyle):
        self._usage[style.value] = self._usage.get(style.value, 0) + 1
        self._history.append(style.value)

    def record_combo(self, effect_id: str, anim_style: TextAnimationStyle,
                     font: str):
        """【P2-3】记录一次 特效×动画×字体 三维组合使用"""
        key = f"{effect_id}|{anim_style.value}|{font}"
        self._combos[key] = self._combos.get(key, 0) + 1

    @property
    def combo_count(self) -> int:
        return len(self._combos)

    def combo_coverage_rate(self, total_space: int = 0) -> float:
        """组合覆盖率: 未指定总空间时返回唯一组合/总使用次数(多样性指标)"""
        total_uses = sum(self._combos.values())
        denom = total_space if total_space > 0 else total_uses
        if denom <= 0:
            return 0.0
        return self.combo_count / denom

    def get_combo_stats(self) -> Dict[str, Any]:
        total_uses = sum(self._combos.values())
        top = sorted(self._combos.items(), key=lambda kv: -kv[1])[:10]
        return {
            "unique_combos": self.combo_count,
            "total_combo_uses": total_uses,
            "diversity_rate": f"{self.combo_coverage_rate():.0%}",
            "top_combos": [
                {"combo": k, "uses": v} for k, v in top
            ],
        }

    @property
    def total_uses(self) -> int:
        return sum(self._usage.values())

    @property
    def used_count(self) -> int:
        return sum(1 for v in self._usage.values() if v > 0)

    @property
    def coverage_rate(self) -> float:
        total = len(self._usage)
        return self.used_count / total if total else 0.0

    @property
    def unused(self) -> List[str]:
        return [k for k, v in self._usage.items() if v == 0]

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_presets": len(self._usage),
            "used": self.used_count,
            "coverage_rate": f"{self.coverage_rate:.0%}",
            "unused": self.unused,
            "usage_distribution": dict(self._usage),
        }

    def reset(self):
        self._usage = {s.value: 0 for s in TextAnimationStyle}
        self._history.clear()
        self._combos.clear()


# 全局追踪器（单例）
_preset_tracker = PresetTracker()

def get_preset_tracker() -> PresetTracker:
    return _preset_tracker


# ============================================================
# 6-C. 视觉层次配置
# ============================================================

@dataclass
class TextHierarchyConfig:
    """文字视觉层次配置
    
    确保主标题与副标题在字号、位置、动画风格上有明显差异。
    """
    # 字号（主标题 vs 副标题，差异≥2.0x）
    title_font_size: float = 96.0
    subtitle_font_size: float = 36.0
    # 字体
    title_font: str = "Arial"
    subtitle_font: str = "Arial"
    # 位置多样性（AE comp坐标 1920x1080）
    title_positions: List[Tuple[float, float]] = field(
        default_factory=lambda: [
            (960, 440), (960, 380), (960, 540), (480, 440), (1440, 440),
        ])
    subtitle_positions: List[Tuple[float, float]] = field(
        default_factory=lambda: [
            (960, 560), (960, 620), (960, 300), (480, 560), (1440, 560),
        ])
    # 动画风格偏好（主标题用入场类，副标题用连续类）
    title_style_pool: Optional[List[TextAnimationStyle]] = None
    subtitle_style_pool: Optional[List[TextAnimationStyle]] = None

    def __post_init__(self):
        if self.title_style_pool is None:
            self.title_style_pool = list(_STYLE_GROUPS["entrance"])
        if self.subtitle_style_pool is None:
            self.subtitle_style_pool = list(_STYLE_GROUPS["continuous"])


# ============================================================
# 6-D. 空间层效果生成器 (EffectLayerBuilder) + 三维智能匹配 (SmartMatcher)
#      —— "特效+动画"一体化融合层
# ============================================================

@dataclass
class EffectConfig:
    """空间层效果配置 — EFFECT_COMBOS 的运行时实例"""
    combo_id: str
    combo_name: str
    effects: List[Dict[str, Any]] = field(default_factory=list)
    font: str = "Arial"
    font_size: float = 96.0
    intensity: AnimationIntensity = AnimationIntensity.MODERATE
    visual_style: str = ""
    best_for: List[str] = field(default_factory=list)


@dataclass
class MatchResult:
    """三维匹配结果: 字体 × 特效 × 动画"""
    scene_tag: str
    font: str
    font_id: str
    effect_combo_id: str
    effect_combo_name: str
    animation: TextAnimationStyle
    anim_preset_id: str
    intensity: AnimationIntensity
    confidence: float = 0.0
    reason: str = ""


class EffectLayerBuilder:
    """空间层效果生成器 — 将 EFFECT_COMBOS 转为 AE JSX 效果器配置

    防坑铁律 (来自 style_migrator.py 实测验证表):
    - Glow matchName 为 "ADBE Glo2"(非 "ADBE Glo 2")，参数索引 -0002~-0013
    - 未实测验证索引的效果器(Turbulent Displace/Bevel Emboss 等)
      使用显示名 + 递归查找的 JSX helper，避免硬编码错误索引
    - JSX 单行化，return 后禁止换行 (ASI 陷阱)
    """

    # 已实测验证的 matchName → (显示名, 参数键 → 属性索引) 映射
    VERIFIED_EFFECT_MAP: Dict[str, Dict[str, Any]] = {
        "ADBE Glo2": {
            "display": "Glow",
            "params": {"threshold": 2, "radius": 3, "intensity": 4,
                       "color_mode": 7, "colorA": 12, "colorB": 13},
        },
        "ADBE Tint": {
            "display": "Tint",
            "params": {"black": 1, "white": 2, "amount": 3},
        },
        "ADBE Ramp": {
            "display": "Ramp (渐变渐变/4-Color Gradient 替代)",
            "params": {"startPoint": 1, "startColor": 2,
                       "endPoint": 3, "endColor": 4, "type": 5},
        },
        "ADBE Drop Shadow": {
            "display": "Drop Shadow",
            "params": {"direction": 1, "angle": 1, "distance": 2, "softness": 3,
                       "color": 4, "opacity": 5},
        },
        "ADBE Fractal Noise": {
            "display": "Fractal Noise",
            "params": {"fractal_type": 1, "noise_type": 2, "invert": 3,
                       "contrast": 4, "brightness": 5},
        },
        "ADBE Venetian Blinds": {
            "display": "Venetian Blinds",
            "params": {"direction": 1, "width": 2, "feather": 3,
                       "completion": 4},
        },
    }

    # 未验证索引的效果器 → 显示名 + (参数键 → 显示名) 回退查找
    UNVERIFIED_EFFECT_MAP: Dict[str, Dict[str, Any]] = {
        "ADBE Turbulent Displace": {
            "display": "Turbulent Displace",
            "params": {"amount": "Amount", "size": "Size"},
        },
        "ADBE Bevel Emboss": {
            "display": "Bevel Emboss",
            "params": {"edgeThickness": "Edge Thickness",
                       "direction": "Light Direction", "angle": "Light Angle",
                       "altitude": "Light Altitude",
                       "highlightOpacity": "Highlight Opacity",
                       "shadowOpacity": "Shadow Opacity",
                       "highlightColor": "Highlight/Shadow Color",
                       "shadowColor": "Highlight/Shadow Color",
                       "softness": "Softness"},
        },
    }

    # 强度分级对空间层效果参数的缩放规则
    _INTENSITY_AMPLIFY_KEYS = {"amount", "radius", "intensity", "distance",
                               "edgeThickness", "contrast", "completion"}

    # JSX helper: 按显示名递归查找效果属性（单行化，防 ASI）
    _JSX_HELPER = (
        "function __fxByDisplay(grp, name) {"
        "for (var i = 1; i <= grp.numProperties; i++) {"
        "var p = grp.property(i);"
        "if (p.name === name) { return p; }"
        "if (p.numProperties > 0) { var r = __fxByDisplay(p, name); if (r) { return r; } }"
        "} return null; }\n"
        "function __fxAdd(layer, matchName, displayName) {"
        "var fx = null; try { fx = layer.property(\"Effects\").addProperty(matchName); } catch (e) {}"
        "if (!fx) { try { fx = layer.property(\"Effects\").addProperty(displayName); } catch (e2) {} }"
        "return fx; }\n"
        "function __fxSet(fx, idx, displayName, val) {"
        "var p = null; try { p = fx.property(idx); } catch (e) {}"
        "if (!p || (displayName && p.name !== displayName)) { var q = __fxByDisplay(fx, displayName); if (q) { p = q; } }"
        "if (p) { try { p.setValue(val); } catch (e3) {} } }\n"
    )

    def __init__(self, effect_combos: Optional[List[Dict[str, Any]]] = None):
        if effect_combos is None:
            effect_combos = _load_preset_matrix_data()["effect_combos"]
        self._combos = {c["id"]: c for c in effect_combos}

    @property
    def combo_ids(self) -> List[str]:
        return list(self._combos.keys())

    def build_effect_config(
        self,
        combo_id: str,
        font: str = "Arial",
        font_size: float = 96.0,
        intensity: AnimationIntensity = AnimationIntensity.MODERATE,
    ) -> Optional[EffectConfig]:
        """从 EFFECT_COMBOS 数据库构建运行时效果配置"""
        combo = self._combos.get(combo_id)
        if not combo:
            return None
        amp = intensity.amplitude_scale
        scaled_effects = []
        for fx in combo.get("effects", []):
            params = {}
            for k, v in fx.get("params", {}).items():
                if isinstance(v, (int, float)) and k in self._INTENSITY_AMPLIFY_KEYS:
                    params[k] = round(v * amp, 2)
                else:
                    params[k] = v
            scaled_effects.append({"matchName": fx["matchName"], "params": params})
        return EffectConfig(
            combo_id=combo_id,
            combo_name=combo.get("name", combo_id),
            effects=scaled_effects,
            font=font,
            font_size=font_size,
            intensity=intensity,
            visual_style=combo.get("visual_style", ""),
            best_for=list(combo.get("best_for", [])),
        )

    def to_jsx(self, config: EffectConfig, layer_var: str) -> str:
        """生成效果器设置 JSX — 单行化安全风格"""
        if not config.effects:
            return ""
        lines = ["// ── 空间层效果: {} ──".format(config.combo_name), self._JSX_HELPER]
        for i, fx in enumerate(config.effects):
            mn = fx["matchName"]
            var = f"fx{i}"
            verified = self.VERIFIED_EFFECT_MAP.get(mn)
            if verified:
                display = verified["display"]
                lines.append(
                    f'var {var} = __fxAdd({layer_var}, "{mn}", "{display}");'
                    f'if ({var}) {{'
                )
                for key, val in fx["params"].items():
                    idx = verified["params"].get(key)
                    if idx is None:
                        continue
                    lines.append(
                        f'__fxSet({var}, {idx}, null, {self._fmt(val)});'
                    )
                lines.append("}")
            else:
                info = self.UNVERIFIED_EFFECT_MAP.get(mn, {})
                display = info.get("display", mn.replace("ADBE ", ""))
                lines.append(
                    f'var {var} = __fxAdd({layer_var}, "{mn}", "{display}");'
                    f'if ({var}) {{'
                )
                # 同一显示名的多键合并(如 Bevel Emboss 双色控件:
                # highlightColor+shadowColor → [hl, sh] 单次赋值，避免覆盖)
                disp_groups: Dict[str, List[Any]] = {}
                for key, val in fx["params"].items():
                    disp = info.get("params", {}).get(key)
                    if disp is None:
                        continue
                    disp_groups.setdefault(disp, []).append(val)
                for disp, vals in disp_groups.items():
                    merged = vals[0] if len(vals) == 1 else vals
                    lines.append(
                        f'__fxSet({var}, 0, "{disp}", {self._fmt(merged)});'
                    )
                lines.append("}")
        return "\n".join(lines)

    def to_multi_layer_jsx(self, config: EffectConfig,
                           text_layer_var: str,
                           comp_var: str = "comp") -> str:
        """生成多层架构 JSX: TXT_ + GLOW_ (ADD) — 参考 TextEffectService 五层模式

        混合模式必须使用枚举对象 BlendingMode.ADD (禁止裸数字)
        """
        glow = next((f for f in config.effects if f["matchName"] == "ADBE Glo2"), None)
        if not glow:
            return self.to_jsx(config, text_layer_var)
        lines = [
            "// ── 多层架构: GLOW_ 辉光副本层 ──",
            f'var glowLayer = {text_layer_var}.duplicate();',
            'glowLayer.name = "GLOW_" + glowLayer.name;',
            "glowLayer.blendingMode = BlendingMode.ADD;",
            self.to_jsx(EffectConfig(combo_id=config.combo_id,
                                     combo_name=config.combo_name,
                                     effects=[glow]), "glowLayer"),
        ]
        return "\n".join(lines)

    @staticmethod
    def _fmt(val: Any) -> str:
        if isinstance(val, bool):
            return str(val).lower()
        if isinstance(val, (list, tuple)):
            # 嵌套数组(双色控件 [hl,sh])递归格式化
            return "[{}]".format(", ".join(
                EffectLayerBuilder._fmt(v) if isinstance(v, (list, tuple))
                else (f"{v:.3f}" if isinstance(v, float) else str(v))
                for v in val))
        if isinstance(val, float):
            return f"{val:.2f}"
        return str(val)


# ── 预设矩阵数据库加载(带缓存) ──────────────────────────────
_preset_matrix_cache: Optional[Dict[str, Any]] = None


def _load_preset_matrix_data() -> Dict[str, Any]:
    """加载 scripts/build_text_preset_matrix.py 的三维数据库

    使用 importlib 按路径加载，避免对 scripts 包的硬依赖。
    """
    global _preset_matrix_cache
    if _preset_matrix_cache is not None:
        return _preset_matrix_cache
    import importlib.util, contextlib, io as _io
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "scripts", "build_text_preset_matrix.py")
    spec = importlib.util.spec_from_file_location("build_text_preset_matrix", path)
    mod = importlib.util.module_from_spec(spec)
    buf = _io.StringIO()
    with contextlib.redirect_stdout(buf):  # 抑制模块导入时的 [OK] 打印
        spec.loader.exec_module(mod)
    _preset_matrix_cache = {
        "effect_combos": mod.EFFECT_COMBOS,
        "entrance_animations": mod.ENTRANCE_ANIMATIONS,
        "font_library": mod.FONT_LIBRARY,
    }
    return _preset_matrix_cache


# ── 矩阵动画ID → TextAnimationStyle 枚举映射 ─────────────────
ANIM_ID_TO_STYLE: Dict[str, TextAnimationStyle] = {
    "anim_bounce_in": TextAnimationStyle.DROP_BOUNCE,
    "anim_glitch_pop": TextAnimationStyle.GLITCH_TEXT,
    "anim_kinetic_smash": TextAnimationStyle.IMPACT_SHAKE,
    "anim_tracking_fade": TextAnimationStyle.TRACKING,
    "anim_typewriter": TextAnimationStyle.TYPEWRITER,
    "anim_scale_zoom": TextAnimationStyle.FADE_SCALE_COMBO,
    "anim_slide_from_left": TextAnimationStyle.SLIDE_IN_STAGGER,
    "anim_slide_from_right": TextAnimationStyle.SLIDE_RIGHT_STAGGER,
    "anim_slide_from_top": TextAnimationStyle.FADE_UP_STAGGER,
    "anim_slide_from_bottom": TextAnimationStyle.FLOAT_UP,
    "anim_rotate_spin": TextAnimationStyle.ROTATE_IN_STAGGER,
    "anim_blur_reveal": TextAnimationStyle.BLUR_IN_TEXT,
    "anim_stroke_draw": TextAnimationStyle.STROKE_DRAW,
    "anim_color_wipe": TextAnimationStyle.COLOR_WIPE,
    "anim_letter_pop": TextAnimationStyle.LETTER_POP,
    "anim_baseline_wave": TextAnimationStyle.BASELINE_SHIFT,
    "anim_elastic_overshoot": TextAnimationStyle.ELASTIC_OVERSHOOT,
    "anim_squash_stretch": TextAnimationStyle.SQUASH_STRETCH,
    "anim_flip_3d_x": TextAnimationStyle.FLIP_3D_TEXT,
    "anim_flip_3d_y": TextAnimationStyle.FLIP_3D_TEXT,
    "anim_spiral_in": TextAnimationStyle.SPIRAL_ENTRANCE,
    "anim_wave_per_char": TextAnimationStyle.PER_CHAR_WAVE,
    "anim_cascade_fall": TextAnimationStyle.CASCADE_FALL,
    "anim_random_pop": TextAnimationStyle.RANDOM_POP,
    "anim_domino_fall": TextAnimationStyle.DOMINO_FALL,
    "anim_scatter_converge": TextAnimationStyle.SCATTER_CONVERGE,
}


class SmartMatcher:
    """三维智能匹配引擎: 场景标签 → (字体 × 特效 × 动画 × 强度)

    匹配优先级:
    1. SCENE_TABLE 精确匹配 → 直接查表 (Ground Truth)
    2. best_for 倒排索引模糊匹配 → 打分选最优
    3. role/intensity 约束修正
    4. 字体 fallback → FONT_STRATEGY primary
    """

    # 20组 Ground Truth 场景表 (来源: 整合方案 §2.2, verified=True 基准推导)
    SCENE_TABLE: Dict[str, Dict[str, str]] = {
        "battle":      {"font_id": "font_impact",    "effect": "effect_cyber_glitch",  "anim": "anim_kinetic_smash",   "intensity": "intense"},
        "cyberpunk":   {"font_id": "font_consolas",  "effect": "effect_rgb_split",     "anim": "anim_glitch_pop",      "intensity": "intense"},
        "cinematic":   {"font_id": "font_arial_bold","effect": "effect_golden_logo",   "anim": "anim_elastic_overshoot","intensity": "moderate"},
        "anime":       {"font_id": "font_impact",    "effect": "effect_fire_burn",     "anim": "anim_kinetic_smash",   "intensity": "intense"},
        "ink_wash":    {"font_id": "font_kaiti",     "effect": "effect_ink_wash",      "anim": "anim_baseline_wave",   "intensity": "subtle"},
        "neon":        {"font_id": "font_impact",    "effect": "effect_neon_pulse",    "anim": "anim_glitch_pop",      "intensity": "moderate"},
        "social":      {"font_id": "font_youyuan",   "effect": "effect_soft_glow",     "anim": "anim_letter_pop",      "intensity": "subtle"},
        "horror":      {"font_id": "font_kaiti",     "effect": "effect_smoke_dissolve","anim": "anim_cascade_fall",    "intensity": "moderate"},
        "tech":        {"font_id": "font_consolas",  "effect": "effect_hologram_hud",  "anim": "anim_wave_per_char",   "intensity": "subtle"},
        "elegant":     {"font_id": "font_helvetica", "effect": "effect_elegant_fade",  "anim": "anim_tracking_fade",   "intensity": "subtle"},
        "sport":       {"font_id": "font_impact",    "effect": "effect_electric_shock","anim": "anim_bounce_in",       "intensity": "intense"},
        "retro":       {"font_id": "font_courier",   "effect": "effect_retro_vhs",     "anim": "anim_typewriter",      "intensity": "moderate"},
        "magic":       {"font_id": "font_kaiti",     "effect": "effect_aurora",        "anim": "anim_spiral_in",       "intensity": "intense"},
        "industrial":  {"font_id": "font_impact",    "effect": "effect_metallic_bevel","anim": "anim_domino_fall",     "intensity": "moderate"},
        "cute":        {"font_id": "font_youyuan",   "effect": "effect_neon_sign",     "anim": "anim_squash_stretch",  "intensity": "subtle"},
        "data":        {"font_id": "font_consolas",  "effect": "effect_matrix_digital","anim": "anim_scatter_converge","intensity": "moderate"},
        "brand":       {"font_id": "font_arial_bold","effect": "effect_chrome_reflect","anim": "anim_scale_zoom",      "intensity": "moderate"},
        "comic":       {"font_id": "font_impact",    "effect": "effect_rgb_split",     "anim": "anim_random_pop",      "intensity": "intense"},
        "title_kit":   {"font_id": "font_arial_bold","effect": "effect_clean_shadow",  "anim": "anim_slide_from_top",  "intensity": "subtle"},
        "lyric":       {"font_id": "font_kaiti",     "effect": "effect_light_leak",    "anim": "anim_baseline_wave",   "intensity": "subtle"},
    }

    def __init__(self):
        db = _load_preset_matrix_data()
        self.effects = {c["id"]: c for c in db["effect_combos"]}
        self.anims = {a["id"]: a for a in db["entrance_animations"]}
        self.fonts = {f["id"]: f for f in db["font_library"] if f.get("id")}
        self._build_scene_index()

    def _build_scene_index(self):
        """建立 场景关键词 → 候选ID 倒排索引"""
        self._fx_index: Dict[str, List[str]] = {}
        self._anim_index: Dict[str, List[str]] = {}
        for cid, c in self.effects.items():
            for tag in c.get("best_for", []):
                self._fx_index.setdefault(tag, []).append(cid)
        for aid, a in self.anims.items():
            for tag in a.get("best_for", []):
                self._anim_index.setdefault(tag, []).append(aid)

    def match(
        self,
        scene_tag: str,
        role: str = "title",
        intensity: Optional[AnimationIntensity] = None,
    ) -> MatchResult:
        """根据场景标签返回最佳三维组合"""
        tag = (scene_tag or "").strip().lower()
        # 1. 精确查表
        if tag in self.SCENE_TABLE:
            entry = self.SCENE_TABLE[tag]
            inten = intensity or AnimationIntensity(entry["intensity"])
            return self._build_result(tag, entry["font_id"], entry["effect"],
                                      entry["anim"], inten, 1.0, "scene_table")
        # 2. 中文标签 → 表内中文别名映射
        cn_alias = {
            "热血": "battle", "战斗": "battle", "赛博": "cyberpunk", "科幻": "tech",
            "国风": "ink_wash", "水墨": "ink_wash", "电影": "cinematic", "史诗": "cinematic",
            "霓虹": "neon", "潮流": "neon", "恐怖": "horror", "悬疑": "horror",
            "可爱": "cute", "童趣": "cute", "复古": "retro", "歌词": "lyric",
            "品牌": "brand", "运动": "sport", "电竞": "sport",
        }
        for kw, mapped in cn_alias.items():
            # 边界条件: 别名必须在标签首/尾或标签较短，
            # 防止子串误匹配(如 "帝国风格" 误含 "国风")
            hit = (tag.startswith(kw) or tag.endswith(kw)
                   or len(tag) <= len(kw) + 2)
            if kw in tag and hit and mapped in self.SCENE_TABLE:
                entry = self.SCENE_TABLE[mapped]
                inten = intensity or AnimationIntensity(entry["intensity"])
                return self._build_result(tag, entry["font_id"], entry["effect"],
                                          entry["anim"], inten, 0.8, f"alias:{mapped}")
        # 3. best_for 倒排索引精确匹配
        fx_candidates = self._fx_index.get(scene_tag, [])
        anim_candidates = self._anim_index.get(scene_tag, [])
        if fx_candidates or anim_candidates:
            fx_id = self._score_best_effect(fx_candidates) if fx_candidates else "effect_clean_shadow"
            anim_id = anim_candidates[0] if anim_candidates else "anim_scale_zoom"
            font_id = self._pick_font_for(fx_id, anim_id)
            inten = intensity or self._infer_intensity(fx_id)
            return self._build_result(tag, font_id, fx_id, anim_id, inten,
                                      0.6, "inverted_index")
        # 4. 字符重叠模糊匹配（任意 scene_tag 均返回合理组合）
        fx_id, fx_score = self._fuzzy_best(self.effects, scene_tag)
        anim_id, _ = self._fuzzy_best(self.anims, scene_tag)
        fx_id = fx_id or "effect_clean_shadow"
        anim_id = anim_id or "anim_scale_zoom"
        font_id = self._pick_font_for(fx_id, anim_id)
        inten = intensity or self._infer_intensity(fx_id)
        conf = 0.45 if fx_score >= 2 else 0.25
        return self._build_result(tag, font_id, fx_id, anim_id, inten,
                                  conf, f"fuzzy(score={fx_score})")

    @staticmethod
    def _char_overlap(query: str, tag: str) -> int:
        """中文字符重叠数(去重)"""
        return sum(1 for ch in set(query) if ch in tag)

    def _fuzzy_best(self, entries: Dict[str, Dict], query: str) -> Tuple[Optional[str], int]:
        """字符重叠打分选最优候选: 子串包含加2分"""
        best_id, best_score = None, 0
        for eid, e in entries.items():
            for tg in e.get("best_for", []):
                s = self._char_overlap(query, tg)
                if query in tg or tg in query:
                    s += 2
                if s > best_score:
                    best_id, best_score = eid, s
        return best_id, best_score

    def _score_best_effect(self, candidates: List[str]) -> str:
        """verified + rating 打分选最优特效"""
        def score(cid):
            c = self.effects[cid]
            return (2.0 if c.get("verified") else 0.0) + float(c.get("quality_rating", 3))
        return max(candidates, key=score)

    def _pick_font_for(self, fx_id: str, anim_id: str) -> str:
        """选同时推荐该特效与动画的字体; 无交集则取推荐特效的第一个"""
        best, best_score = "font_impact", -1
        for fid, f in self.fonts.items():
            rec_fx = f.get("recommended_effects", [])
            rec_anim = f.get("recommended_animations", [])
            s = (2 if fx_id in rec_fx else 0) + (2 if anim_id in rec_anim else 0)
            if f.get("verified"):
                s += 1
            if s > best_score:
                best, best_score = fid, s
        return best

    def _infer_intensity(self, fx_id: str) -> AnimationIntensity:
        rating = self.effects.get(fx_id, {}).get("quality_rating", 3)
        return AnimationIntensity.INTENSE if rating >= 5 else (
            AnimationIntensity.MODERATE if rating == 4 else AnimationIntensity.SUBTLE)

    def _build_result(self, tag: str, font_id: str, fx_id: str, anim_id: str,
                      intensity: AnimationIntensity, confidence: float,
                      reason: str) -> MatchResult:
        font_entry = self.fonts.get(font_id) or {"postscript_name": "Impact"}
        fx_entry = self.effects.get(fx_id, {})
        style = ANIM_ID_TO_STYLE.get(anim_id, TextAnimationStyle.FADE_SCALE_COMBO)
        # role/强度约束: subtle 限制剧烈动画
        return MatchResult(
            scene_tag=tag,
            font=ae_safe_font_name(font_entry.get("postscript_name", "Impact")),
            font_id=font_id,
            effect_combo_id=fx_id,
            effect_combo_name=fx_entry.get("name", fx_id),
            animation=style,
            anim_preset_id=anim_id,
            intensity=intensity,
            confidence=confidence,
            reason=reason,
        )


# 全局单例
_smart_matcher: Optional[SmartMatcher] = None
_effect_builder: Optional[EffectLayerBuilder] = None


def get_smart_matcher() -> SmartMatcher:
    global _smart_matcher
    if _smart_matcher is None:
        _smart_matcher = SmartMatcher()
    return _smart_matcher


def get_effect_builder() -> EffectLayerBuilder:
    global _effect_builder
    if _effect_builder is None:
        _effect_builder = EffectLayerBuilder()
    return _effect_builder


# ============================================================
# 6-E. 动画编排器 (AnimationOrchestrator) — V2
# ============================================================

class AnimationOrchestrator:
    """动画编排器 V2 — 统一调度所有动画器，生成完整层动画配置
    
    V2 改进：
    - 20种文字动画全覆盖（原先只用3种）
    - 视觉层次：主标题/副标题字号差异≥2.0x，位置多样
    - AE安全字体名处理
    - 预设覆盖率追踪
    - 参数随机化（stagger/magnitude 不再硬编码）
    """

    def __init__(self, hierarchy: Optional[TextHierarchyConfig] = None,
                 seed: Optional[int] = 42):
        self.entrance = EntranceAnimator()
        self.text = TextAnimator()
        self.beat_sync = BeatSyncAnimator()
        self.camera = CameraAnimator()
        self.effect_pulse = EffectPulseAnimator()
        self.hierarchy = hierarchy or TextHierarchyConfig()
        self._tracker = _preset_tracker
        # 参数随机化种子（与 EntranceAnimator 同口径：默认42可复现）
        self._rng = random.Random(seed)
        # 轮转索引：确保每种风格被均匀使用
        self._style_rotation_idx = 0
        # 三维匹配引擎(懒加载，避免导入时加载数据库)
        self._matcher: Optional[SmartMatcher] = None
        self._effect_builder: Optional[EffectLayerBuilder] = None
    
    def _pick_text_style(self, role: str = "title") -> TextAnimationStyle:
        """智能选择文字动画风格 — 轮转确保覆盖率(调用方负责 record)"""
        pool = (self.hierarchy.title_style_pool if role == "title"
                else self.hierarchy.subtitle_style_pool)
        # 轮转选择：确保每种风格被均匀使用
        style = pool[self._style_rotation_idx % len(pool)]
        self._style_rotation_idx += 1
        return style

    def _pick_position(self, role: str = "title") -> Tuple[float, float]:
        """从位置池中随机选择，确保多样性"""
        positions = (self.hierarchy.title_positions if role == "title"
                     else self.hierarchy.subtitle_positions)
        return self._rng.choice(positions)

    def _random_params(self, role: str = "title") -> Tuple[float, float]:
        """随机化 stagger 和 magnitude，避免硬编码"""
        if role == "title":
            stagger = self._rng.uniform(0.03, 0.08)
            magnitude = self._rng.uniform(40, 80)
        else:
            stagger = self._rng.uniform(0.02, 0.06)
            magnitude = self._rng.uniform(20, 50)
        return stagger, magnitude
    
    def orchestrate_layer(
        self,
        layer_config: Dict[str, Any],
        style_category: str = "amv_pull_zoom",
        beats: Optional[List[BeatTiming]] = None,
        duration: float = 2.0,
        start_time: float = 0.0,
    ) -> LayerAnimation:
        """为单个层编排完整动画 — V2"""
        layer_type = layer_config.get("type", "footage")
        layer_index = layer_config.get("index", 0)
        role = layer_config.get("role", "title")  # "title" or "subtitle"
        
        anim = LayerAnimation(
            layer_index=layer_index,
            layer_type=layer_type,
            entrance_duration=min(0.5, duration * 0.3),
            entrance_offset=start_time,
        )
        
        # === 1. 入场动画 ===
        entrance_style = self.entrance.select_entrance_for_style(style_category)
        anim.entrance_style = entrance_style
        
        entrance_tracks = self.entrance.build_tracks(
            style=entrance_style,
            layer_start=start_time,
            duration=anim.entrance_duration,
        )
        for track in entrance_tracks:
            anim.add_track(track)
        
        # === 2. 文字动画（仅文字层）— V2全覆盖 + V3三维匹配 ===
        if layer_type == "text":
            scene_tag = layer_config.get("scene_tag")
            match_result: Optional[MatchResult] = None
            if scene_tag:
                # 三维智能匹配: 场景标签 → 字体×特效×动画×强度
                if self._matcher is None:
                    self._matcher = get_smart_matcher()
                    self._effect_builder = get_effect_builder()
                req_intensity = layer_config.get("intensity")
                match_result = self._matcher.match(
                    scene_tag=scene_tag,
                    role=role,
                    intensity=(AnimationIntensity(req_intensity)
                               if req_intensity else None),
                )
                text_style = match_result.animation
                stagger, magnitude = self._random_params(role)
                magnitude *= match_result.intensity.amplitude_scale
                font_size = (self.hierarchy.title_font_size if role == "title"
                             else self.hierarchy.subtitle_font_size)
                position = self._pick_position(role)
                font_name = match_result.font
            else:
                # 无场景标签 → 保持 V2 轮转逻辑
                text_style = self._pick_text_style(role)
                stagger, magnitude = self._random_params(role)
                font_size = (self.hierarchy.title_font_size if role == "title"
                             else self.hierarchy.subtitle_font_size)
                position = self._pick_position(role)
                font_name = ae_safe_font_name(
                    self.hierarchy.title_font if role == "title"
                    else self.hierarchy.subtitle_font
                )
            self._tracker.record(text_style)
            # 【P2-3】三维组合覆盖追踪(仅三维匹配命中时)
            if match_result is not None:
                self._tracker.record_combo(
                    match_result.effect_combo_id, text_style,
                    match_result.font)
            
            text_tracks = self.text.build_tracks(
                style=text_style,
                text_start=start_time,
                text_duration=duration * 0.6,
                char_count=layer_config.get("char_count", 10),
                stagger=stagger,
                magnitude=magnitude,
            )
            for track in text_tracks:
                anim.add_track(track)
            
            # 将字体/字号/位置信息附加到 anim 元数据（供 JSX 生成器使用）
            anim._text_meta = {
                "style": text_style.value,
                "font": font_name,
                "font_size": font_size,
                "position": position,
                "role": role,
                "stagger": stagger,
                "magnitude": magnitude,
            }
            
            # === 空间层特效（仅三维匹配命中时）===
            if match_result is not None and self._effect_builder is not None:
                effect_config = self._effect_builder.build_effect_config(
                    combo_id=match_result.effect_combo_id,
                    font=match_result.font,
                    font_size=font_size,
                    intensity=match_result.intensity,
                )
                if effect_config:
                    anim._text_meta["effect_combo"] = match_result.effect_combo_id
                    anim._text_meta["effect_name"] = match_result.effect_combo_name
                    anim._text_meta["effect_config"] = effect_config
                    anim._text_meta["intensity"] = match_result.intensity.value
                    anim._text_meta["scene_tag"] = match_result.scene_tag
                    anim._text_meta["match_confidence"] = match_result.confidence
                    anim._text_meta["match_reason"] = match_result.reason
        
        # === 3. 节拍同步动画（可选） ===
        if beats and layer_type in ("footage", "adjustment"):
            beat_tracks = self.beat_sync.build_beat_pulses(
                beats=beats,
                layer_start=start_time,
                amplitude=0.8,
                properties=["scale"],
            )
            for track in beat_tracks:
                anim.add_track(track)
        
        # === 4. 运镜动画 ===
        has_beats = beats is not None and len(beats) > 0
        camera_style = self.camera.select_camera_for_style(style_category, has_beats)
        if camera_style != CameraStyle.KEN_BURNS or duration > 2.0:
            cam_tracks = self.camera.build_camera_tracks(
                style=camera_style,
                layer_duration=duration,
                layer_start=start_time,
                intensity=0.8,
            )
            for track in cam_tracks:
                anim.add_track(track)
        
        # === 5. 效果脉冲（可选） ===
        if beats and layer_type != "text":
            glow_track = self.effect_pulse.build_effect_beat_pulse(
                effect_path="Effects/Glow/Glow Intensity",
                beats=beats,
                start=start_time,
                pulse_magnitude=0.15,
            )
            if glow_track:
                anim.add_track(glow_track)
        
        return anim
    
    def orchestrate_sequence(
        self,
        layers: List[Dict[str, Any]],
        style_category: str = "amv_pull_zoom",
        beats: Optional[List[BeatTiming]] = None,
    ) -> List[LayerAnimation]:
        """为整个序列编排动画
        
        Args:
            layers: 层列表 [{'type': 'footage', 'index': 0, 'duration': 2.0, 'start': 0.0}, ...]
            style_category: 风格类别
            beats: 节拍列表
            
        Returns:
            List[LayerAnimation]: 所有层的动画配置
        """
        result = []
        for layer in layers:
            anim = self.orchestrate_layer(
                layer_config=layer,
                style_category=style_category,
                beats=beats,
                duration=layer.get("duration", 2.0),
                start_time=layer.get("start", 0.0),
            )
            result.append(anim)
        return result
    
    def to_jsx_snippet(self, layer_anim: LayerAnimation, 
                       comp_name: str = "MainComp") -> str:
        """将LayerAnimation转换为JSX脚本片段
        
        生成可直接插入JSX脚本的关键帧设置代码。
        若 _text_meta 包含 effect_config，额外输出空间层效果器 JSX
        (动画关键帧 + 效果器设置 一体化输出)。
        
        Returns:
            str: JSX关键帧设置代码片段
        """
        lines = []
        layer_var = f"layer{layer_anim.layer_index}"
        
        for track in layer_anim.animation_tracks:
            if not track.keyframes:
                continue
            
            prop_path = track.property_path
            
            for kf in track.keyframes:
                val_str = self._format_jsx_value(kf.value)
                lines.append(
                    f"{layer_var}.property(\"{prop_path}\")"
                    f".setValueAtTime({kf.time}, {val_str});"
                )
                
                # 设置缓动（如果非默认）
                if kf.ease_in != EaseType.EASE_IN_OUT:
                    lines.append(
                        f"{layer_var}.property(\"{prop_path}\")"
                        f".setTemporalEaseAtKey(/*keyIndex*/, "
                        f"[new KeyframeEase({kf.ease_in_speed}, {kf.ease_in_speed}), "
                        f"new KeyframeEase({kf.ease_out_speed}, {kf.ease_out_speed})]);"
                    )
        
        # 空间层效果器 JSX（三维匹配命中时）
        meta = getattr(layer_anim, "_text_meta", None)
        if meta and meta.get("effect_config"):
            effect_jsx = get_effect_builder().to_jsx(
                meta["effect_config"], layer_var)
            if effect_jsx:
                lines.append("")
                lines.append(effect_jsx)
        
        return "\n".join(lines)
    
    def _format_jsx_value(self, val: Any) -> str:
        """将Python值转换为JSX字符串"""
        if isinstance(val, (list, tuple)):
            return f"[{', '.join(str(v) for v in val)}]"
        elif isinstance(val, float):
            return f"{val:.3f}"
        elif isinstance(val, bool):
            return str(val).lower()
        return str(val)


# ============================================================
# 7. 导出接口
# ============================================================

def animate_layer(
    layer_config: Dict[str, Any],
    style_category: str = "amv_pull_zoom",
    beats: Optional[List[BeatTiming]] = None,
    duration: float = 2.0,
    start_time: float = 0.0,
) -> LayerAnimation:
    """便捷函数：为单个层生成动画
    
    Returns:
        LayerAnimation: 动画配置
    """
    orchestrator = AnimationOrchestrator()
    return orchestrator.orchestrate_layer(
        layer_config=layer_config,
        style_category=style_category,
        beats=beats,
        duration=duration,
        start_time=start_time,
    )


def animate_sequence(
    layers: List[Dict[str, Any]],
    style_category: str = "amv_pull_zoom",
    beats: Optional[List[BeatTiming]] = None,
) -> List[LayerAnimation]:
    """便捷函数：为序列生成动画
    
    Returns:
        List[LayerAnimation]: 动画配置列表
    """
    orchestrator = AnimationOrchestrator()
    return orchestrator.orchestrate_sequence(
        layers=layers,
        style_category=style_category,
        beats=beats,
    )


def beats_from_times(beat_times: List[float], 
                     strengths: Optional[List[float]] = None,
                     downbeat_indices: Optional[List[int]] = None) -> List[BeatTiming]:
    """从节拍时间列表构建BeatTiming列表
    
    Args:
        beat_times: 节拍时间（秒）
        strengths: 可选强度列表
        downbeat_indices: 可选重拍索引
        
    Returns:
        List[BeatTiming]
    """
    downbeat_indices = downbeat_indices or []
    beats = []
    for i, t in enumerate(beat_times):
        strength = strengths[i] if strengths and i < len(strengths) else 1.0
        is_downbeat = i in downbeat_indices or (i % 4 == 0)  # 每4拍一个重拍
        beats.append(BeatTiming(time=t, strength=strength, is_downbeat=is_downbeat))
    return beats
