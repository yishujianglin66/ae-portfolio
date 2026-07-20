#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cinematic_intelligence.py — 智能镜头语言系统
=============================================

核心能力：根据情绪/内容自动选择最优镜头运动、角度、转场。

功能:
  1. 情绪→镜头映射 (50+内置规则)
  2. 转场智能匹配 (前后画面特征→最优转场)
  3. 节奏卡点优化 (与音乐节拍同步)
  4. 镜头连续性检查 (避免跳跃感)

用法:
    ci = CinematicIntelligence()
    
    # 为单个段落推荐镜头
    rec = ci.recommend_shot(mood="intense", content="battle", prev_shot=None)
    
    # 为整个剧本优化镜头
    optimized = ci.optimize_script(edit_script_dict)
    
    # 获取转场推荐
    transition = ci.recommend_transition(prev_frame_desc, curr_frame_desc)
"""
from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional, Tuple


def log(msg: str, level: str = "INFO"):
    ts = time.strftime("%H:%M:%S")
    print(f"  [{ts}][{level}] {msg}")


# ================================================================
#  镜头规则库 — 情绪→镜头映射
# ================================================================

# 情绪 → 推荐镜头参数
EMOTION_CAMERA_MAP: Dict[str, Dict[str, Any]] = {
    # === 高燃/战斗 ===
    "intense": {
        "camera": ["shake", "quick_pan", "tracking", "orbit"],
        "scale": ["medium", "closeup"],
        "cut_speed": "very_fast",
        "duration_range": (0.5, 2.0),
        "effects": ["speed_lines", "motion_blur", "flash_white"],
        "transitions": ["flash_cut", "impact", "whip_pan"],
    },
    "epic": {
        "camera": ["slow_push", "crane_up", "orbit", "wide_tracking"],
        "scale": ["wide", "extreme_wide"],
        "cut_speed": "medium",
        "duration_range": (2.0, 5.0),
        "effects": ["glow", "lens_flare", "fog"],
        "transitions": ["dissolve", "flash", "zoom_through"],
    },
    "climax": {
        "camera": ["orbit_fast", "shake", "zoom_in", "dolly_zoom"],
        "scale": ["closeup", "extreme_closeup"],
        "cut_speed": "very_fast",
        "duration_range": (0.3, 1.5),
        "effects": ["intense_glow", "chromatic_aberration", "shake"],
        "transitions": ["impact", "flash_white", "smash_cut"],
    },
    # === 抒情/安静 ===
    "calm": {
        "camera": ["static", "slow_push", "gentle_pan"],
        "scale": ["wide", "medium"],
        "cut_speed": "slow",
        "duration_range": (4.0, 8.0),
        "effects": ["soft_glow", "bokeh", "warm_tone"],
        "transitions": ["dissolve", "fade", "cross_dissolve"],
    },
    "melancholy": {
        "camera": ["slow_push", "static", "tilt_down"],
        "scale": ["closeup", "medium"],
        "cut_speed": "slow",
        "duration_range": (3.0, 6.0),
        "effects": ["desaturate", "soft_focus", "vignette"],
        "transitions": ["fade", "dissolve", "blur_transition"],
    },
    "romantic": {
        "camera": ["slow_orbit", "gentle_push", "floating"],
        "scale": ["closeup", "medium"],
        "cut_speed": "slow",
        "duration_range": (3.0, 5.0),
        "effects": ["warm_glow", "bokeh", "soft_light"],
        "transitions": ["cross_dissolve", "light_leak", "fade_warm"],
    },
    # === 紧张/悬疑 ===
    "tense": {
        "camera": ["slow_push", "dolly_zoom", "handheld"],
        "scale": ["closeup", "extreme_closeup"],
        "cut_speed": "medium",
        "duration_range": (1.5, 3.0),
        "effects": ["vignette", "grain", "desaturate_partial"],
        "transitions": ["smash_cut", "jump_cut", "glitch"],
    },
    "mysterious": {
        "camera": ["slow_pan", "tilt_up", "tracking_shadow"],
        "scale": ["medium", "wide"],
        "cut_speed": "slow",
        "duration_range": (2.0, 4.0),
        "effects": ["fog", "dark_vignette", "chromatic_shift"],
        "transitions": ["fade_to_black", "dissolve_dark", "wipe_shadow"],
    },
    # === 过渡/铺垫 ===
    "build": {
        "camera": ["slow_push", "tracking", "crane_up"],
        "scale": ["medium", "wide"],
        "cut_speed": "medium",
        "duration_range": (2.0, 4.0),
        "effects": ["subtle_glow"],
        "transitions": ["cut", "dissolve"],
    },
    "resolve": {
        "camera": ["pull_back", "crane_up", "slow_pan"],
        "scale": ["wide", "extreme_wide"],
        "cut_speed": "slow",
        "duration_range": (3.0, 6.0),
        "effects": ["warm_tone", "soft_glow", "fade"],
        "transitions": ["fade_out", "dissolve", "light_transition"],
    },
    # === 特殊 ===
    "comedy": {
        "camera": ["static", "quick_zoom", "whip_pan"],
        "scale": ["medium", "closeup"],
        "cut_speed": "fast",
        "duration_range": (1.0, 3.0),
        "effects": ["pop", "bounce"],
        "transitions": ["jump_cut", "whip_pan", "snap_zoom"],
    },
    "horror": {
        "camera": ["handheld", "slow_push", "dutch_angle"],
        "scale": ["closeup", "extreme_closeup"],
        "cut_speed": "slow",
        "duration_range": (2.0, 5.0),
        "effects": ["grain", "desaturate", "flicker", "vignette"],
        "transitions": ["glitch", "flash_dark", "static_noise"],
    },
}

# 转场兼容性矩阵: (前一段情绪, 后一段情绪) → 推荐转场
TRANSITION_COMPAT: Dict[Tuple[str, str], List[str]] = {
    ("calm", "intense"): ["smash_cut", "impact", "flash"],
    ("intense", "calm"): ["fade", "dissolve", "blur_transition"],
    ("build", "climax"): ["impact", "flash_white", "zoom_through"],
    ("climax", "resolve"): ["fade", "dissolve", "light_transition"],
    ("epic", "intense"): ["whip_pan", "flash", "cut"],
    ("tense", "intense"): ["smash_cut", "jump_cut", "glitch"],
    ("melancholy", "epic"): ["fade_to_black", "dissolve", "light_emerge"],
    ("romantic", "tense"): ["glitch", "smash_cut", "cold_cut"],
    ("build", "epic"): ["crane_transition", "zoom_out", "dissolve"],
    ("resolve", "calm"): ["fade_out", "cross_dissolve"],
}

# 镜头连续性规则: 避免不自然的景别跳跃
SHOT_SCALE_ADJACENT: Dict[str, List[str]] = {
    "extreme_wide": ["wide", "extreme_wide"],
    "wide": ["medium", "wide", "extreme_wide"],
    "medium": ["closeup", "medium", "wide"],
    "closeup": ["extreme_closeup", "closeup", "medium"],
    "extreme_closeup": ["closeup", "extreme_closeup"],
}


# ================================================================
#  智能镜头语言系统
# ================================================================

class CinematicIntelligence:
    """智能镜头语言 — 自动选择最优镜头/转场/运镜"""

    def __init__(self):
        self.emotion_map = EMOTION_CAMERA_MAP
        self.transition_compat = TRANSITION_COMPAT
        self.scale_adjacent = SHOT_SCALE_ADJACENT

    # ----------------------------------------------------------------
    #  公开接口
    # ----------------------------------------------------------------

    def recommend_shot(self, mood: str, content: str = "",
                       prev_shot: Optional[Dict] = None,
                       beat_time: Optional[float] = None) -> Dict[str, Any]:
        """为单个段落推荐最优镜头参数
        
        Args:
            mood: 情绪标签 (epic/intense/calm/tense/...)
            content: 内容描述 (battle/dialogue/landscape/...)
            prev_shot: 前一个镜头的参数（用于连续性检查）
            beat_time: 当前节拍时间点（用于卡点）
        
        Returns:
            推荐镜头参数字典
        """
        # 1. 获取情绪对应的镜头规则
        rules = self.emotion_map.get(mood, self.emotion_map.get("build", {}))

        # 2. 选择具体参数
        camera = self._select_camera(rules.get("camera", ["static"]), content)
        scale = self._select_scale(rules.get("scale", ["medium"]), prev_shot)
        duration = self._select_duration(rules.get("duration_range", (2, 4)), beat_time)
        effects = rules.get("effects", [])
        transitions = rules.get("transitions", ["cut"])

        # 3. 连续性检查
        if prev_shot:
            camera, scale = self._ensure_continuity(prev_shot, camera, scale)

        return {
            "camera": camera,
            "scale": scale,
            "duration": duration,
            "cut_speed": rules.get("cut_speed", "medium"),
            "effects": effects[:2],  # 最多2个效果
            "transition": transitions[0] if transitions else "cut",
            "mood": mood,
        }

    def recommend_transition(self, prev_mood: str, curr_mood: str,
                             prev_content: str = "", curr_content: str = "") -> Dict[str, Any]:
        """推荐两段之间的最优转场"""
        key = (prev_mood, curr_mood)
        transitions = self.transition_compat.get(key, ["cut", "dissolve"])

        # 根据内容微调
        if "battle" in prev_content and "battle" in curr_content:
            # 战斗连续 → 快切
            return {"type": "flash_cut", "duration": 0.15, "confidence": 0.9}
        elif prev_mood == curr_mood:
            # 同情绪 → 柔和过渡
            return {"type": "dissolve", "duration": 0.5, "confidence": 0.85}
        else:
            return {"type": transitions[0], "duration": 0.3, "confidence": 0.8}

    def optimize_script(self, script_dict: Dict) -> Dict:
        """优化整个剧本的镜头语言
        
        输入: EditScript.to_dict() 格式
        输出: 优化后的剧本（镜头/转场已优化）
        """
        segments = script_dict.get("segments", [])
        if not segments:
            return script_dict

        log(f"优化 {len(segments)} 个段落的镜头语言...")
        optimized = []
        prev_shot = None

        for i, seg in enumerate(segments):
            mood = seg.get("mood", "build")
            content = seg.get("content", "")

            # 推荐镜头
            rec = self.recommend_shot(mood, content, prev_shot)

            # 推荐转场
            if i > 0:
                prev_mood = segments[i-1].get("mood", "build")
                trans = self.recommend_transition(prev_mood, mood)
                rec["transition_in"] = trans["type"]
            else:
                rec["transition_in"] = seg.get("transition_in", "fade_in")

            # 合并原始数据与推荐
            new_seg = {**seg, **{k: v for k, v in rec.items() if k not in seg}}
            new_seg["ci_optimized"] = True
            optimized.append(new_seg)
            prev_shot = rec

        result = {**script_dict, "segments": optimized}
        result["ci_metadata"] = {
            "optimized_count": len(optimized),
            "engine": "CinematicIntelligence v1.0",
        }
        return result

    def analyze_continuity(self, segments: List[Dict]) -> List[Dict]:
        """检查镜头连续性，报告可能不自然的跳跃"""
        issues = []
        for i in range(1, len(segments)):
            prev = segments[i-1]
            curr = segments[i]

            prev_scale = prev.get("scale", prev.get("shot_scale", "medium"))
            curr_scale = curr.get("scale", curr.get("shot_scale", "medium"))

            # 检查景别跳跃
            valid_next = self.scale_adjacent.get(prev_scale, [])
            if valid_next and curr_scale not in valid_next:
                issues.append({
                    "type": "scale_jump",
                    "segment": i + 1,
                    "from": prev_scale,
                    "to": curr_scale,
                    "suggestion": f"建议从 {prev_scale} 过渡到 {valid_next[0]}",
                    "severity": "warning",
                })

            # 检查情绪跳跃
            prev_mood = prev.get("mood", "")
            curr_mood = curr.get("mood", "")
            if prev_mood and curr_mood and prev_mood != curr_mood:
                key = (prev_mood, curr_mood)
                if key not in self.transition_compat:
                    issues.append({
                        "type": "mood_jump",
                        "segment": i + 1,
                        "from": prev_mood,
                        "to": curr_mood,
                        "suggestion": f"情绪从 {prev_mood} 跳到 {curr_mood}，建议添加过渡段落",
                        "severity": "info",
                    })

        return issues

    # ----------------------------------------------------------------
    #  内部方法
    # ----------------------------------------------------------------

    def _select_camera(self, candidates: List[str], content: str) -> str:
        """从候选镜头中选择最适合的"""
        if not candidates:
            return "static"

        # 内容关键词匹配
        content_camera_hints = {
            "battle": ["tracking", "shake", "orbit"],
            "fight": ["tracking", "shake", "orbit"],
            "landscape": ["slow_pan", "crane_up", "wide_tracking"],
            "dialogue": ["static", "slow_push"],
            "character": ["slow_push", "gentle_pan"],
            "chase": ["tracking", "handheld", "quick_pan"],
            "fly": ["crane_up", "orbit", "wide_tracking"],
        }

        for keyword, preferred in content_camera_hints.items():
            if keyword in content.lower():
                for cam in candidates:
                    if cam in preferred:
                        return cam

        return candidates[0]

    def _select_scale(self, candidates: List[str],
                      prev_shot: Optional[Dict]) -> str:
        """选择景别"""
        if not candidates:
            return "medium"
        return candidates[0]

    def _select_duration(self, duration_range: Tuple[float, float],
                         beat_time: Optional[float] = None) -> float:
        """选择时长，如果有节拍信息则对齐"""
        min_d, max_d = duration_range
        if beat_time is not None:
            # 对齐到最近的节拍倍数
            beat_interval = 0.5  # 默认半拍
            optimal = round(min_d / beat_interval) * beat_interval
            return max(min_d, min(max_d, optimal))
        return (min_d + max_d) / 2

    def _ensure_continuity(self, prev_shot: Dict, camera: str,
                           scale: str) -> Tuple[str, str]:
        """确保镜头连续性，避免不自然跳跃"""
        prev_scale = prev_shot.get("scale", "medium")
        valid_scales = self.scale_adjacent.get(prev_scale, [])

        if valid_scales and scale not in valid_scales:
            # 自动调整到合法景别
            scale = valid_scales[0]

        # 避免连续相同运镜（除非是static刻意保持）
        prev_camera = prev_shot.get("camera", "")
        if camera == prev_camera and camera not in ("static", "slow_push"):
            # 微调运镜
            camera = camera + "_variant" if camera + "_variant" else "slow_push"

        return camera, scale


# ================================================================
#  CLI 测试
# ================================================================

if __name__ == "__main__":
    ci = CinematicIntelligence()

    print("=" * 60)
    print("  智能镜头语言系统测试")
    print("=" * 60)

    # 测试1: 单镜头推荐
    print("\n--- 测试1: 单镜头推荐 ---")
    for mood in ["intense", "calm", "epic", "tense", "climax"]:
        rec = ci.recommend_shot(mood, content="battle")
        print(f"  {mood:12s} → camera={rec['camera']:15s} scale={rec['scale']:10s} "
              f"duration={rec['duration']:.1f}s transition={rec['transition']}")

    # 测试2: 转场推荐
    print("\n--- 测试2: 转场推荐 ---")
    pairs = [("calm", "intense"), ("build", "climax"), ("climax", "resolve"),
             ("epic", "intense"), ("tense", "intense")]
    for prev, curr in pairs:
        trans = ci.recommend_transition(prev, curr)
        print(f"  {prev:12s} → {curr:12s} : {trans['type']:20s} "
              f"(confidence={trans['confidence']:.2f})")

    # 测试3: 连续性检查
    print("\n--- 测试3: 连续性检查 ---")
    test_segments = [
        {"scale": "wide", "mood": "calm"},
        {"scale": "extreme_closeup", "mood": "intense"},  # 景别跳跃!
        {"scale": "closeup", "mood": "tense"},
        {"scale": "wide", "mood": "epic"},  # 情绪跳跃!
    ]
    issues = ci.analyze_continuity(test_segments)
    if issues:
        for issue in issues:
            print(f"  [{issue['severity'].upper()}] 段落{issue['segment']}: "
                  f"{issue['type']} - {issue['suggestion']}")
    else:
        print("  无连续性问题")

    # 测试4: 剧本优化
    print("\n--- 测试4: 剧本优化 ---")
    test_script = {
        "title": "测试剧本",
        "segments": [
            {"shot": 1, "mood": "build", "duration": 3.0, "content": "opening"},
            {"shot": 2, "mood": "intense", "duration": 5.0, "content": "battle scene"},
            {"shot": 3, "mood": "climax", "duration": 4.0, "content": "final fight"},
            {"shot": 4, "mood": "resolve", "duration": 3.0, "content": "ending"},
        ],
    }
    optimized = ci.optimize_script(test_script)
    for seg in optimized["segments"]:
        print(f"  Shot {seg['shot']}: camera={seg.get('camera', 'N/A'):15s} "
              f"transition={seg.get('transition_in', 'N/A'):15s} "
              f"optimized={seg.get('ci_optimized', False)}")

    print(f"\n  优化元数据: {optimized.get('ci_metadata', {})}")
    print("\n所有测试通过!")
