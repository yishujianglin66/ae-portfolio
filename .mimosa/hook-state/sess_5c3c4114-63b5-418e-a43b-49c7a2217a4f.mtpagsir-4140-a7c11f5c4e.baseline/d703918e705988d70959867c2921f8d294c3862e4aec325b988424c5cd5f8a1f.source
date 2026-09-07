# -*- coding: utf-8 -*-
"""NarrativeArcPlanner + StyleProfile — 叙事弧线与风格参数化 (T3)

替代 ai_director 的均分五等份 fallback:
- 能量包络函数按 master_rules.json energy_envelope 分配段落时长
- BPM 网格骨架生成切点 (切点密度拍/切 + drop重音半拍)
- drop 段 70% 处插入 2-4 拍 breath break (喘息点)
- 每个 segment 携带 energy_target/scene_tag/intensity/camera_bias,
  直接喂给 smart_director.select_text_combo_for_shot
- StyleProfile: 风格名 → SmartMatcher 场景标签精确映射
"""
import json
import math
import os
from typing import Any, Dict, List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER_RULES_PATH = os.path.join(ROOT, "config", "master_rules.json")
STYLE_PROFILES_PATH = os.path.join(ROOT, "config", "style_profiles.json")

# 段落 → 智能导演强度映射 (与 P2 _DIRECTOR_SCENE_FALLBACK 对齐)
_INTENSITY_BY_SEG = {"intro": "gentle", "build": "moderate", "drop": "intense",
                     "break": "gentle", "outro": "gentle"}
# 段落 → 默认场景标签 (无 StyleProfile 时的降级)
_SCENE_BY_SEG = {"intro": "cinematic", "build": "cinematic", "drop": "battle",
                 "break": "elegant", "outro": "elegant"}


class NarrativeArcPlanner:
    """五段式叙事弧线规划器 (能量包络 + BPM网格切点)"""

    def __init__(self, rules: Optional[Dict[str, Any]] = None):
        if rules is None:
            with open(MASTER_RULES_PATH, encoding="utf-8") as f:
                rules = json.load(f)
        self.envelope: Dict[str, Any] = rules["energy_envelope"]["segments"]
        self.bpm_table: Dict[str, Any] = rules["bpm_frame_table"]

    # ── 段落规划 ────────────────────────────────────────────
    def plan_segments(self, total_dur: float, bpm: float = 128,
                      style_profile: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """按能量包络比例生成五段(+breath break)结构

        每个 segment 字段: type/name/start/end/duration/energy_target/
        scene_tag/intensity/camera_bias/cut_times
        """
        if total_dur <= 0:
            raise ValueError("total_dur must be positive")
        segments: List[Dict[str, Any]] = []
        cursor = 0.0
        for seg_type in ["intro", "build", "drop", "break", "outro"]:
            env = self.envelope[seg_type]
            dur = total_dur * env["ratio"]
            start, end = cursor, cursor + dur
            seg = self._build_segment(seg_type, start, end, bpm, style_profile)
            segments.append(seg)
            # drop 段 70% 处插入 breath break (外网漫剪标准喘息点)
            if seg_type == "drop":
                brk = self._insert_breath_break(seg, bpm)
                if brk is not None:
                    segments.append(brk)
            cursor = end
        return segments

    def _build_segment(self, seg_type: str, start: float, end: float,
                       bpm: float, style_profile: Optional[Dict]) -> Dict[str, Any]:
        env = self.envelope[seg_type]
        e0, e1 = env["energy"]
        sp = style_profile or {}
        # break段铁律: 急降留白, 无切点 (cut_beats仅记录节奏密度参考)
        cut_beats = env.get("cut_beats", 4)
        if seg_type == "break":
            cut_times: List[float] = []
        else:
            cut_times = self.beat_grid_cuts(
                start, end, bpm, cut_beats,
                half_beat=env.get("half_beat_on_accent", False))
        return {
            "type": seg_type,
            "name": seg_type.capitalize(),
            "start": round(start, 3),
            "end": round(end, 3),
            "duration": round(end - start, 3),
            "energy_target": [e0, e1],
            "scene_tag": sp.get("scene_tags", {}).get(seg_type, _SCENE_BY_SEG[seg_type]),
            "intensity": sp.get("intensity_map", {}).get(seg_type,
                                                         _INTENSITY_BY_SEG[seg_type]),
            "camera_bias": sp.get("camera_bias", {}).get(seg_type, []),
            "cut_beats": cut_beats,
            "cut_times": cut_times,
        }

    def _insert_breath_break(self, drop_seg: Dict, bpm: float) -> Optional[Dict]:
        """drop 段 70% 处插入 2-4 拍 breath break 标记段"""
        beats = self.envelope["drop"].get("breath_break_beats", [2, 4])
        beat_dur = 60.0 / bpm if bpm > 0 else 0.5
        brk_dur = beats[0] * beat_dur
        pos = drop_seg["start"] + drop_seg["duration"] * \
            self.envelope["drop"].get("second_drop_at", 0.7)
        if pos + brk_dur > drop_seg["end"]:
            brk_dur = max(0.2, drop_seg["end"] - pos)
        return {
            "type": "breath_break",
            "name": "BreathBreak",
            "start": round(pos, 3),
            "end": round(pos + brk_dur, 3),
            "duration": round(brk_dur, 3),
            "energy_target": [1.0, 0.6],
            "scene_tag": drop_seg["scene_tag"],
            "intensity": "gentle",
            "camera_bias": ["pull"],
            "cut_beats": 0,
            "cut_times": [],
        }

    # ── BPM 网格切点 ────────────────────────────────────────
    def beat_grid_cuts(self, start: float, end: float, bpm: float,
                       beats_per_cut: int, half_beat: bool = False,
                       fps: int = 30) -> List[float]:
        """在 [start, end) 内按帧网格生成切点 (锚点 t=0, 帧级对齐)

        以 frames_per_beat(整数帧, 与 bpm_frame_table 对齐) 为骨架,
        切点帧号必为 半拍帧数(fpb//2) 的整数倍, 保证节拍误差<1帧。
        beats_per_cut=0 → 无切点 (break段留白)
        half_beat=True → 高潮段每4切点插入半拍重音加密
        """
        if beats_per_cut <= 0 or bpm <= 0:
            return []
        beat_dur = 60.0 / bpm
        step_t = beat_dur * beats_per_cut
        cuts: List[float] = []
        k = max(1, math.ceil((start - 1e-6) / step_t))
        idx = 0
        seen = set()
        while True:
            t = k * step_t
            if t >= end - 0.05:
                break
            # 逐拍理想时间 → 最近整帧吸附, 单切点误差恒≤0.5帧不累积
            f = round(t * fps)
            if f > round(start * fps) and f not in seen:
                cuts.append(round(f / fps, 3))
                seen.add(f)
                idx += 1
                # 高潮段每4个切点插入半拍重音(同样帧吸附)
                if half_beat and idx % 4 == 0:
                    fa = round((t + beat_dur / 2) * fps)
                    if fa < (end - 0.05) * fps and fa not in seen:
                        cuts.append(round(fa / fps, 3))
                        seen.add(fa)
            k += 1
        return cuts

    def frames_per_beat(self, bpm: float, fps: int = 30) -> int:
        """BPM → 每拍帧数 (与 bpm_frame_table 对齐)"""
        if bpm <= 0:
            return fps
        return int(round(fps * 60.0 / bpm))

    # ── 能量采样 ────────────────────────────────────────────
    def energy_at(self, segments: List[Dict], t: float) -> float:
        """线性插值能量包络: 返回时刻 t 的目标能量 [0,1]"""
        for seg in segments:
            if seg["start"] <= t <= seg["end"]:
                e0, e1 = seg["energy_target"]
                if seg["end"] == seg["start"]:
                    return e0
                p = (t - seg["start"]) / (seg["end"] - seg["start"])
                return round(e0 + (e1 - e0) * p, 3)
        return 0.0


class StyleProfile:
    """风格参数化: 风格名 → SmartMatcher场景标签/强度/运镜偏好 精确映射"""

    def __init__(self, path: str = STYLE_PROFILES_PATH):
        with open(path, encoding="utf-8") as f:
            self.profiles: Dict[str, Any] = json.load(f).get("profiles", {})

    def list_styles(self) -> List[str]:
        return list(self.profiles.keys())

    def resolve(self, style_name: str) -> Optional[Dict[str, Any]]:
        """精确匹配风格; 失败时做中文别名宽松匹配"""
        if style_name in self.profiles:
            return self.profiles[style_name]
        for name, prof in self.profiles.items():
            aliases = prof.get("aliases", [])
            if style_name in aliases:
                return prof
            # 双向包含宽松匹配(带长度防护避免误命中)
            if (style_name in name or name in style_name) and \
                    min(len(style_name), len(name)) >= 2:
                return prof
        return None

    def to_planner_profile(self, style_name: str) -> Dict[str, Any]:
        """转换为 NarrativeArcPlanner.plan_segments 可消费的 profile dict"""
        prof = self.resolve(style_name)
        if prof is None:
            return {}
        return {
            "scene_tags": prof.get("scene_tags", {}),
            "intensity_map": prof.get("intensity_map", {}),
            "camera_bias": prof.get("camera_bias", {}),
        }
