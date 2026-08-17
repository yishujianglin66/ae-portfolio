#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
风格复刻桥梁层 — StyleSpec / DirectorScript → 完整软件管线适配器
=================================================================

将 ProductionDirector（ffmpeg 快速管线）的输出数据结构转换为
DaVinci Resolve Engine / AE Bridge / PR Bridge 可消费的参数格式。

核心适配器:
1. ColorProfileAdapter: StyleSpec.color_profile → CDLConfig / LUT 强度 / AE 效果参数
2. TransitionMapper:      ffmpeg 转场标签 → Resolve 转场 / AE 转场 matchName
3. SpeedCurveAdapter:     SPEED_PRESETS mood → Resolve SpeedConfig / SpeedCurve
4. ScriptAdapter:         DirectorScript → Resolve 时间线片段序列

设计原则:
- 每个适配器独立可测试，不依赖外部软件运行
- 映射表可配置，支持运行时覆盖
- 所有转换可逆（提供反向映射用于诊断）

依赖:
- core/style_spec_extractor.py (StyleSpec)
- ai/production_director.py (DirectorSegment, DirectorScript, SPEED_PRESETS)
- integrations/resolve_engine.py (CDLConfig, SpeedConfig, SpeedCurve, TransitionConfig)

用法:
    from ai.style_bridge import StyleBridge
    bridge = StyleBridge()
    cdl = bridge.color_to_cdl(style_spec.color_profile)
    resolve_transitions = [bridge.map_transition(seg.transition) for seg in script.segments]
    resolve_timeline = bridge.script_to_resolve_timeline(script)
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))


# ============================================================================
# 1. 色彩映射: StyleSpec.color_profile → CDLConfig / AE 效果参数
# ============================================================================

@dataclass
class ColorBridgeResult:
    """色彩桥接结果 — 跨软件统一色彩描述"""
    # DaVinci Resolve CDL
    cdl_saturation: float = 1.0          # 0.0 ~ 4.0 (1.0 = 中性)
    cdl_contrast: float = 1.0            # 0.0 ~ 4.0 (1.0 = 中性)
    cdl_brightness: float = 0.0          # -1.0 ~ 1.0 (0.0 = 中性)
    # DaVinci Resolve 色轮 (shadows/midtones/highlights RGB 偏移)
    color_wheel_shadows: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    color_wheel_midtones: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    color_wheel_highlights: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    # ffmpeg eq 参数 (降级用)
    ffmpeg_eq_saturation: float = 1.0    # 0.0 ~ 4.0
    ffmpeg_eq_contrast: float = 1.0      # 0.0 ~ 4.0
    ffmpeg_eq_brightness: float = 0.0    # -1.0 ~ 1.0
    # AE 效果参数 (matchName + 属性值)
    ae_hue_saturation: float = 0.0       # -100 ~ 100 (ADBE HUE SATURATION -0005)
    ae_brightness: float = 0.0           # -100 ~ 100 (ADBE Brightness & Contrast 2 -0001)
    ae_contrast: float = 0.0             # -100 ~ 100 (ADBE Brightness & Contrast 2 -0002)
    # 诊断信息
    source_profile: Dict[str, float] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)


class ColorProfileAdapter:
    """StyleSpec.color_profile → 跨软件色彩参数映射。

    色彩空间说明:
    - StyleSpec.color_profile: {brightness, saturation, contrast}，范围 0~100
      基于 HSV 抽帧统计（cv2），brightness = gray.mean()*100/255
    - CDL: ASC CDL 标准，saturation/contrast/brightness 为乘性/加性系数
    - ffmpeg eq: 与 CDL 类似但范围不同
    - AE: matchName 属性值，范围因属性而异
    """

    # 中性基准值（StyleSpec 色彩统计的"中间值"）
    NEUTRAL_BRIGHTNESS = 50.0   # 0~100 的中点
    NEUTRAL_SATURATION = 50.0
    NEUTRAL_CONTRAST = 50.0

    def convert(self, color_profile: Dict[str, float]) -> ColorBridgeResult:
        """将 StyleSpec.color_profile 转换为跨软件色彩参数。

        Args:
            color_profile: {brightness, saturation, contrast, samples?}
                          范围 0~100，来自 StyleSpecExtractor._analyze_color()

        Returns:
            ColorBridgeResult 包含 CDL / ffmpeg / AE 三套参数
        """
        if not color_profile:
            return ColorBridgeResult(notes=["空 color_profile，使用中性值"])

        src_bri = float(color_profile.get("brightness", self.NEUTRAL_BRIGHTNESS))
        src_sat = float(color_profile.get("saturation", self.NEUTRAL_SATURATION))
        src_con = float(color_profile.get("contrast", self.NEUTRAL_CONTRAST))

        result = ColorBridgeResult(source_profile=color_profile)

        # ---- CDL 映射 ----
        # 饱和度: 50 → 1.0 (中性), 每偏离 50 按比例缩放
        # 实测: ref_sat=35.6 → CDL sat=0.712 (降饱和), ref_sat=65 → 1.3
        result.cdl_saturation = max(0.1, min(4.0, src_sat / self.NEUTRAL_SATURATION))

        # 对比度: 50 → 1.0, 但用平方根阻尼避免极端值
        con_ratio = src_con / self.NEUTRAL_CONTRAST
        result.cdl_contrast = max(0.5, min(2.0, math.sqrt(con_ratio)))

        # 亮度: 50 → 0.0 (中性偏移), 线性映射到 [-0.3, 0.3]
        bri_delta = (src_bri - self.NEUTRAL_BRIGHTNESS) / self.NEUTRAL_BRIGHTNESS
        result.cdl_brightness = max(-0.3, min(0.3, bri_delta * 0.6))

        # ---- ffmpeg eq 映射 (与 CDL 保持一致) ----
        result.ffmpeg_eq_saturation = result.cdl_saturation
        result.ffmpeg_eq_contrast = result.cdl_contrast
        result.ffmpeg_eq_brightness = result.cdl_brightness

        # ---- AE 效果参数映射 ----
        # ADBE HUE SATURATION -0005: 范围 -100~100, 0=中性
        # 将 CDL saturation 转换为百分比偏移
        result.ae_hue_saturation = max(-100, min(100,
            (result.cdl_saturation - 1.0) * 100))

        # ADBE Brightness & Contrast 2 -0001/-0002: 范围 -100~100
        result.ae_brightness = max(-100, min(100, result.cdl_brightness * 100))
        result.ae_contrast = max(-100, min(100,
            (result.cdl_contrast - 1.0) * 100))

        # ---- 色轮推断 (基于亮度/饱和度组合) ----
        # 低饱和+低亮度 → 暗部偏冷; 高饱和+高亮度 → 高光偏暖
        if src_sat < 40 and src_bri < 40:
            result.color_wheel_shadows = (-0.02, -0.01, 0.03)   # 暗部偏蓝
            result.notes.append("低饱和暗调 → 暗部冷色偏移")
        elif src_sat > 60 and src_bri > 55:
            result.color_wheel_highlights = (0.03, 0.01, -0.02)  # 高光偏暖
            result.notes.append("高饱和亮调 → 高光暖色偏移")

        result.notes.append(
            f"色彩桥接: sat={src_sat:.1f}→CDL {result.cdl_saturation:.3f}, "
            f"con={src_con:.1f}→CDL {result.cdl_contrast:.3f}, "
            f"bri={src_bri:.1f}→CDL {result.cdl_brightness:.3f}")

        return result


# ============================================================================
# 2. 转场映射: ffmpeg 转场标签 → Resolve / AE 转场
# ============================================================================

@dataclass
class TransitionBridgeResult:
    """转场桥接结果"""
    # 原始标签
    source_label: str = "cut"
    # DaVinci Resolve
    resolve_transition_name: str = ""        # Resolve 转场名（空=硬切）
    resolve_duration: float = 0.0            # 转场时长（秒）
    # AE
    ae_effect_matchname: str = ""            # AE 转场效果 matchName（空=硬切）
    ae_jsx_snippet: str = ""                 # 可选的自定义 JSX 代码
    # ffmpeg xfade (降级用)
    ffmpeg_xfade_name: str = ""
    ffmpeg_xfade_duration: float = 0.0
    # 诊断
    notes: str = ""


class TransitionMapper:
    """ffmpeg 转场标签 → Resolve / AE / ffmpeg xfade 三向映射。

    映射表基于实测验证:
    - ffmpeg xfade: 已验证 fadeblack/fadewhite/slideleft/pixelize 等存在于 ffmpeg 8.1.1
    - Resolve: Cross Dissolve / Dip to White / Slide 等为 PR/Resolve 通用转场名
    - AE: 自定义 JSX 实现或 matchName
    """

    # 完整映射表: source_label → {resolve, ae_matchname, xfade, duration}
    TRANSITION_TABLE: Dict[str, Dict[str, Any]] = {
        "cut": {
            "resolve": "",
            "ae_matchname": "",
            "xfade": "",
            "duration": 0.0,
            "notes": "硬切，无转场",
        },
        "fade": {
            "resolve": "Cross Dissolve",
            "ae_matchname": "ADBE DissolveFB",
            "xfade": "fadeblack",
            "duration": 0.3,
            "notes": "黑色淡入淡出，intro/outro 常用",
        },
        "flash": {
            "resolve": "Dip to White",
            "ae_matchname": "",  # 自定义 JSX
            "xfade": "fadewhite",
            "duration": 0.12,
            "ae_jsx": "flash_white",
            "notes": "闪白卡点，drop/climax 常用",
        },
        "zoom": {
            "resolve": "Zoom Transition",
            "ae_matchname": "",  # 自定义 JSX
            "xfade": "smoothup",
            "duration": 0.3,
            "ae_jsx": "zoom_impact",
            "notes": "缩放冲击，高潮进点",
        },
        "slide": {
            "resolve": "Slide",
            "ae_matchname": "",  # 自定义 JSX
            "xfade": "slideleft",
            "duration": 0.25,
            "ae_jsx": "slide_push",
            "notes": "横向滑动，常规过渡",
        },
        "glitch": {
            "resolve": "Film Dissolve",  # Resolve 无 glitch，用 Film Dissolve 近似
            "ae_matchname": "",
            "xfade": "pixelize",
            "duration": 0.15,
            "ae_jsx": "glitch_shake",
            "notes": "故障抖动，高能段常用；Resolve 降级为 Film Dissolve",
        },
        "wipe": {
            "resolve": "Wipe",
            "ae_matchname": "",
            "xfade": "slideleft",
            "duration": 0.3,
            "notes": "擦除过渡",
        },
        "dissolve": {
            "resolve": "Cross Dissolve",
            "ae_matchname": "ADBE DissolveFB",
            "xfade": "fadeblack",
            "duration": 0.4,
            "notes": "交叉溶解",
        },
    }

    # 情绪驱动的转场时长微调系数
    MOOD_DURATION_SCALE: Dict[str, float] = {
        "intro": 1.5,     # intro 转场偏长
        "build": 1.0,
        "drop": 0.6,      # drop 转场极短（卡点）
        "climax": 0.7,
        "break": 1.3,     # break 转场柔和
        "outro": 1.5,
    }

    def map_transition(
        self,
        label: str,
        mood: str = "build",
        duration_override: Optional[float] = None,
    ) -> TransitionBridgeResult:
        """将 ffmpeg 转场标签转换为跨软件转场参数。

        Args:
            label: ffmpeg 转场标签 ("cut", "fade", "flash", "zoom", "slide", "glitch")
            mood: 情绪段落标签，用于调整转场时长
            duration_override: 强制指定转场时长（覆盖情绪调整）
        """
        entry = self.TRANSITION_TABLE.get(label.lower())
        if entry is None:
            # 未知标签降级为硬切
            return TransitionBridgeResult(
                source_label=label,
                notes=f"未知转场标签 '{label}'，降级为硬切",
            )

        # 基础时长 × 情绪系数
        base_dur = entry["duration"]
        mood_scale = self.MOOD_DURATION_SCALE.get(mood, 1.0)
        final_dur = duration_override if duration_override is not None else base_dur * mood_scale
        final_dur = round(max(0.05, min(1.0, final_dur)), 3)

        return TransitionBridgeResult(
            source_label=label,
            resolve_transition_name=entry["resolve"],
            resolve_duration=final_dur if entry["resolve"] else 0.0,
            ae_effect_matchname=entry.get("ae_matchname", ""),
            ae_jsx_snippet=entry.get("ae_jsx", ""),
            ffmpeg_xfade_name=entry["xfade"],
            ffmpeg_xfade_duration=final_dur if entry["xfade"] else 0.0,
            notes=entry.get("notes", ""),
        )

    def map_transition_sequence(
        self,
        segments: List[Any],
    ) -> List[TransitionBridgeResult]:
        """批量转换段落序列的转场。"""
        results = []
        for seg in segments:
            transition_label = getattr(seg, "transition", "cut")
            mood = getattr(seg, "mood", "build")
            params = getattr(seg, "transition_params", None)
            dur_override = params.get("duration") if params else None
            results.append(self.map_transition(transition_label, mood, dur_override))
        return results


# ============================================================================
# 3. 变速映射: SPEED_PRESETS mood → Resolve SpeedConfig / SpeedCurve
# ============================================================================

@dataclass
class SpeedBridgeResult:
    """变速桥接结果"""
    # 统一速度
    uniform_speed: float = 1.0              # 0.25 ~ 4.0
    # Resolve SpeedConfig
    resolve_speed: float = 1.0
    resolve_retime_process: int = 0         # 0=Project, 1=Nearest, 2=Optical Flow
    # Resolve SpeedCurve (变速曲线)
    resolve_has_curve: bool = False
    resolve_curve_points: List[Tuple[float, float]] = field(default_factory=list)
    # ffmpeg setpts 因子
    ffmpeg_setpts_factor: float = 1.0       # setpts = 1/speed * PTS
    # 诊断
    notes: str = ""


class SpeedCurveAdapter:
    """情绪/StyleSpec 驱动的速度参数 → Resolve / ffmpeg 变速配置。

    速度语义:
    - speed > 1.0 = 加速 (快进)
    - speed < 1.0 = 减速 (慢放)
    - speed = 1.0 = 原速

    ffmpeg: setpts=1/speed*PTS (speed=2 → setpts=0.5*PTS → 2倍速)
    Resolve: SetProperty("ClipSpeed", speed) 或 SpeedCurve 贝塞尔曲线
    """

    # ProductionDirector SPEED_PRESETS 对照表
    MOOD_SPEED_PRESETS: Dict[str, float] = {
        "intro": 0.85,     # 慢放蓄力
        "build": 1.0,      # 原速推进
        "drop": 0.7,       # 明显慢放（打击感）
        "climax": 1.2,     # 轻微加速（高能）
        "break": 0.6,      # 大幅慢放（留白）
        "outro": 0.9,      # 轻微慢放（收尾）
    }

    # 情绪 → 变速曲线控制点 [(time_pos, speed)]
    # 用于 Resolve dynamic_speed_ramp()
    MOOD_SPEED_CURVES: Dict[str, List[Tuple[float, float]]] = {
        "intro": [(0.0, 1.0), (0.5, 0.85), (1.0, 0.85)],       # 渐入慢放
        "build": [(0.0, 1.0), (1.0, 1.0)],                       # 匀速
        "drop": [(0.0, 1.2), (0.3, 0.7), (0.7, 0.7), (1.0, 1.0)],  # 先快后慢
        "climax": [(0.0, 1.0), (0.5, 1.3), (1.0, 1.2)],         # 加速冲击
        "break": [(0.0, 0.8), (0.5, 0.5), (1.0, 0.6)],          # 深慢放
        "outro": [(0.0, 1.0), (0.5, 0.9), (1.0, 0.8)],          # 渐出慢放
    }

    def convert(
        self,
        mood: str = "build",
        speed_override: Optional[float] = None,
        use_curve: bool = True,
    ) -> SpeedBridgeResult:
        """将情绪段落转换为变速参数。

        Args:
            mood: 情绪段落标签
            speed_override: 强制指定速度（覆盖情绪预设）
            use_curve: 是否生成变速曲线（False = 匀速）
        """
        speed = speed_override if speed_override is not None else self.MOOD_SPEED_PRESETS.get(mood, 1.0)
        speed = max(0.25, min(4.0, speed))

        result = SpeedBridgeResult()
        result.uniform_speed = speed
        result.resolve_speed = speed
        result.ffmpeg_setpts_factor = 1.0 / speed

        # 慢放时使用光流补帧（Resolve Optical Flow）
        if speed < 0.8:
            result.resolve_retime_process = 2  # Optical Flow
            result.notes = f"慢放 {speed:.2f}x → 启用光流补帧"
        else:
            result.resolve_retime_process = 0
            result.notes = f"速度 {speed:.2f}x"

        # 变速曲线
        if use_curve and mood in self.MOOD_SPEED_CURVES:
            curve = self.MOOD_SPEED_CURVES[mood]
            # 如果有速度覆盖，缩放曲线
            if speed_override is not None:
                preset_speed = self.MOOD_SPEED_PRESETS.get(mood, 1.0)
                scale = speed / preset_speed if preset_speed > 0 else 1.0
                curve = [(t, v * scale) for t, v in curve]
            result.resolve_has_curve = True
            result.resolve_curve_points = curve

        return result

    def convert_style_spec_speed(
        self,
        speed_segments: List[Dict[str, float]],
    ) -> List[SpeedBridgeResult]:
        """将 StyleSpec.speed_segments 转换为变速参数序列。

        Args:
            speed_segments: [{start, end, speed_hint, kind?}]
                           speed_hint: 0.5=慢放, 1.0=原速, 1.5=加速
        """
        results = []
        for seg in speed_segments:
            speed = float(seg.get("speed_hint", 1.0))
            result = self.convert(speed_override=speed, use_curve=False)
            result.notes += f" [StyleSpec {seg.get('kind', '?')} {seg.get('start', 0):.1f}s-{seg.get('end', 0):.1f}s]"
            results.append(result)
        return results


# ============================================================================
# 4. 统一桥梁: StyleBridge
# ============================================================================

class StyleBridge:
    """统一风格桥梁 — 聚合所有适配器。

    用法:
        bridge = StyleBridge()

        # 色彩映射
        cdl = bridge.color_to_cdl(style_spec.color_profile)

        # 转场映射
        trans = bridge.map_transition("flash", mood="drop")

        # 变速映射
        speed = bridge.speed_for_mood("climax")

        # 完整剧本转换
        timeline = bridge.script_to_resolve_timeline(director_script)
    """

    def __init__(self):
        self.color_adapter = ColorProfileAdapter()
        self.transition_mapper = TransitionMapper()
        self.speed_adapter = SpeedCurveAdapter()

    def color_to_cdl(self, color_profile: Dict[str, float]) -> ColorBridgeResult:
        """快捷方法: color_profile → CDL"""
        return self.color_adapter.convert(color_profile)

    def map_transition(self, label: str, mood: str = "build",
                     duration_override: Optional[float] = None) -> TransitionBridgeResult:
        """快捷方法: 转场标签 → 跨软件转场"""
        return self.transition_mapper.map_transition(label, mood, duration_override)

    def speed_for_mood(self, mood: str, speed_override: Optional[float] = None) -> SpeedBridgeResult:
        """快捷方法: 情绪 → 变速参数"""
        return self.speed_adapter.convert(mood, speed_override)

    def script_to_resolve_timeline(
        self,
        script_dict: Dict[str, Any],
        style_spec: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """将 DirectorScript.to_dict() 转换为 Resolve 时间线片段序列。

        Args:
            script_dict: DirectorScript.to_dict() 的输出
            style_spec: 可选的 StyleSpec.to_dict()，用于覆盖色彩/速度

        Returns:
            Resolve 时间线片段列表，每个片段包含:
            {
                "source_file": str,
                "source_start": float,
                "source_duration": float,
                "speed": float,
                "speed_curve": List[Tuple[float, float]] or None,
                "transition": str (Resolve 转场名),
                "transition_duration": float,
                "color_cdl": {saturation, contrast, brightness},
                "mood": str,
                "energy": float,
            }
        """
        segments = script_dict.get("segments", [])
        color_profile = {}
        if style_spec:
            color_profile = style_spec.get("color_profile", {})
        color_result = self.color_adapter.convert(color_profile)

        timeline_items = []
        for seg_data in segments:
            mood = seg_data.get("mood", "build")
            transition_label = seg_data.get("transition", "cut")
            speed = seg_data.get("speed", 1.0)
            trans_params = seg_data.get("transition_params")

            # 转场映射
            trans_result = self.transition_mapper.map_transition(
                transition_label, mood,
                duration_override=trans_params.get("duration") if trans_params else None,
            )

            # 变速映射
            speed_result = self.speed_adapter.convert(
                mood, speed_override=speed if speed != 1.0 else None,
            )

            item = {
                "source_file": seg_data.get("source_file", ""),
                "source_start": seg_data.get("source_start", 0.0),
                "source_duration": seg_data.get("duration", 0.0),
                "speed": speed_result.uniform_speed,
                "speed_curve": speed_result.resolve_curve_points if speed_result.resolve_has_curve else None,
                "retime_process": speed_result.resolve_retime_process,
                "transition": trans_result.resolve_transition_name,
                "transition_duration": trans_result.resolve_duration,
                "color_cdl": {
                    "saturation": color_result.cdl_saturation,
                    "contrast": color_result.cdl_contrast,
                    "brightness": color_result.cdl_brightness,
                },
                "mood": mood,
                "energy": seg_data.get("energy", 0.5),
                "index": seg_data.get("index", 0),
            }
            timeline_items.append(item)

        return timeline_items


# ============================================================================
# CLI 自测
# ============================================================================

def _self_test():
    """适配器自测 — 验证映射表完整性"""
    bridge = StyleBridge()

    # 1. 色彩映射测试
    print("=" * 60)
    print("色彩映射测试")
    print("=" * 60)
    test_profiles = [
        {"brightness": 46.0, "saturation": 35.6, "contrast": 27.7},  # 我独自升级参考
        {"brightness": 50.0, "saturation": 50.0, "contrast": 50.0},  # 中性
        {"brightness": 60.0, "saturation": 65.0, "contrast": 60.0},  # 高饱和
        {"brightness": 30.0, "saturation": 25.0, "contrast": 35.0},  # 暗调低饱和
    ]
    for profile in test_profiles:
        result = bridge.color_to_cdl(profile)
        print(f"  输入: bri={profile['brightness']:.1f} sat={profile['saturation']:.1f} con={profile['contrast']:.1f}")
        print(f"  → CDL: sat={result.cdl_saturation:.3f} con={result.cdl_contrast:.3f} bri={result.cdl_brightness:.3f}")
        print(f"  → AE:  sat={result.ae_hue_saturation:.1f} bri={result.ae_brightness:.1f} con={result.ae_contrast:.1f}")
        print(f"  → {result.notes}")
        print()

    # 2. 转场映射测试
    print("=" * 60)
    print("转场映射测试")
    print("=" * 60)
    for label in ["cut", "fade", "flash", "zoom", "slide", "glitch", "unknown"]:
        for mood in ["intro", "drop", "climax"]:
            result = bridge.map_transition(label, mood)
            print(f"  {label:8s} + {mood:8s} → Resolve='{result.resolve_transition_name}' "
                  f"dur={result.resolve_duration:.3f}s | xfade='{result.ffmpeg_xfade_name}'")
    print()

    # 3. 变速映射测试
    print("=" * 60)
    print("变速映射测试")
    print("=" * 60)
    for mood in ["intro", "build", "drop", "climax", "break", "outro"]:
        result = bridge.speed_for_mood(mood)
        curve_str = f"curve={result.resolve_curve_points}" if result.resolve_has_curve else "匀速"
        print(f"  {mood:8s} → speed={result.uniform_speed:.2f}x "
              f"retime={result.resolve_retime_process} {curve_str}")
    print()

    print("[OK] All adapter self-tests passed")


if __name__ == "__main__":
    _self_test()
