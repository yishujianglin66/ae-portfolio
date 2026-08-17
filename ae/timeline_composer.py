"""
Timeline Composer — 素材时间线智能编排引擎
===========================================
将多个视频素材、音频、转场、特效按时间线智能编排，
生成可直接导入 PR/AE 的时间线描述。

核心能力:
- 多素材智能排序（按节奏/情绪/色彩匹配）
- 起始时间点自动计算（基于时长/转场重叠）
- 时间线间隙自动填充
- 多轨叠加编排（视频主轨 + 覆盖轨 + 音频轨）
- 嵌套序列（Nested Sequence）描述生成
- 导出 PR MCP 兼容的时间线 JSON
- 导出 AE 兼容的合成描述

依赖:
    项目内模块: beat_detector, scene_detector, pr_mcp_client

用法:
    composer = TimelineComposer()
    timeline = composer.build_timeline(
        clips=["clip1.mp4", "clip2.mp4", "clip3.mp4"],
        audio="bgm.mp3",
        style="dynamic_cut"
    )
    # timeline.to_pr_json() → 可直接发送到 PremiereProMCP
"""

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
from copy import deepcopy

sys.path.insert(0, str(Path(__file__).parent.parent))


# ================================================================
#  数据结构
# ================================================================
class TrackType(Enum):
    VIDEO = "video"
    AUDIO = "audio"
    OVERLAY = "overlay"   # 覆盖轨（画中画/字幕等）
    ADJUSTMENT = "adjustment"  # 调整图层


class TimelineStyle(Enum):
    """剪辑风格"""
    DYNAMIC_CUT = "dynamic_cut"       # 节奏卡点剪辑
    SMOOTH_FLOW = "smooth_flow"       # 平滑流畅过渡
    FAST_BEAT = "fast_beat"           # 快节奏
    SLOW_CINEMATIC = "slow_cinematic" # 慢电影感
    GLITCH_STYLE = "glitch_style"     # 故障风格
    VLOG = "vlog"                     # Vlog风格


@dataclass
class ClipItem:
    """时间线中的单个素材片断"""
    id: str                          # 唯一标识
    source_path: str                 # 源文件路径
    source_start: float = 0.0        # 源素材入点（秒）
    source_end: Optional[float] = None  # 源素材出点（秒），None 表示到结尾

    # 时间线位置
    timeline_in: float = 0.0        # 时间线上的入点
    timeline_out: Optional[float] = None  # 时间线上的出点
    duration: float = 0.0           # 时长

    # 变换属性
    scale: float = 1.0
    position_x: float = 0.5
    position_y: float = 0.5
    rotation: float = 0.0
    opacity: float = 1.0

    # 转场
    transition_in: Optional[Dict] = None   # {type, duration}
    transition_out: Optional[Dict] = None  # {type, duration}

    # 特效
    effects: List[Dict] = field(default_factory=list)
    speed: float = 1.0              # 变速
    is_reversed: bool = False
    freeze_frame_at: Optional[float] = None

    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)
    track_index: int = 0
    track_type: TrackType = TrackType.VIDEO

    def __post_init__(self):
        if self.timeline_out is None:
            self.timeline_out = self.timeline_in + self.duration


@dataclass
class Track:
    """时间线轨道"""
    index: int
    track_type: TrackType
    clips: List[ClipItem] = field(default_factory=list)
    muted: bool = False
    locked: bool = False
    label: str = ""


@dataclass
class Timeline:
    """完整时间线"""
    name: str
    fps: float = 30.0
    resolution: Tuple[int, int] = (1920, 1080)
    sample_rate: int = 48000
    total_duration: float = 0.0

    tracks: List[Track] = field(default_factory=list)
    markers: List[Dict] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    audio_source: Optional[str] = None
    style: TimelineStyle = TimelineStyle.DYNAMIC_CUT

    def to_pr_json(self) -> Dict[str, Any]:
        """导出为 PremiereProMCP 兼容的时间线 JSON"""
        video_tracks = []
        audio_tracks = []

        for track in self.tracks:
            track_data = {
                "track_index": track.index,
                "track_type": track.track_type.value,
                "muted": track.muted,
                "locked": track.locked,
                "label": track.label,
                "clips": []
            }

            for clip in track.clips:
                clip_data = {
                    "id": clip.id,
                    "source_path": clip.source_path,
                    "source_start": clip.source_start,
                    "media_duration": clip.source_end - clip.source_start if clip.source_end else clip.duration,
                    "timeline_in": clip.timeline_in,
                    "timeline_out": clip.timeline_out,
                    "duration": clip.duration,
                    "scale": clip.scale,
                    "position": {"x": clip.position_x, "y": clip.position_y},
                    "rotation": clip.rotation,
                    "opacity": clip.opacity,
                    "speed": clip.speed,
                    "is_reversed": clip.is_reversed,
                    "transition_in": clip.transition_in,
                    "transition_out": clip.transition_out,
                    "effects": clip.effects,
                }
                track_data["clips"].append(clip_data)

            if track.track_type in (TrackType.AUDIO,):
                audio_tracks.append(track_data)
            else:
                video_tracks.append(track_data)

        return {
            "sequence_name": self.name,
            "fps": self.fps,
            "resolution": {"width": self.resolution[0], "height": self.resolution[1]},
            "sample_rate": self.sample_rate,
            "total_duration": self.total_duration,
            "audio_source": self.audio_source or "",
            "style": self.style.value,
            "video_tracks": video_tracks,
            "audio_tracks": audio_tracks,
            "markers": self.markers,
            "metadata": self.metadata,
        }

    def to_ae_json(self) -> Dict[str, Any]:
        """导出为 AE MCP 兼容的合成描述"""
        pr_json = self.to_pr_json()
        comp = {
            "composition_name": self.name,
            "width": self.resolution[0],
            "height": self.resolution[1],
            "frame_rate": self.fps,
            "duration": self.total_duration,
            "layers": [],
        }

        all_clips = []
        for track in self.tracks:
            for clip in track.clips:
                layer = {
                    "name": Path(clip.source_path).stem,
                    "source": clip.source_path,
                    "in_point": clip.timeline_in,
                    "out_point": clip.timeline_out,
                    "duration": clip.duration,
                    "opacity": clip.opacity * 100,
                    "scale": [clip.scale * 100, clip.scale * 100],
                    "position": [clip.position_x * self.resolution[0], clip.position_y * self.resolution[1]],
                    "rotation": clip.rotation,
                    "effects": clip.effects,
                    "speed": clip.speed,
                    "reversed": clip.is_reversed,
                    "track_index": track.index,
                    "track_type": track.track_type.value,
                }
                if clip.transition_in:
                    layer["transition_in"] = clip.transition_in
                if clip.transition_out:
                    layer["transition_out"] = clip.transition_out
                all_clips.append(layer)

        comp["layers"] = sorted(all_clips, key=lambda x: x["track_index"])
        return comp


# ================================================================
#  Timeline Composer 核心编排引擎
# ================================================================
class TimelineComposer:
    """
    时间线智能编排引擎。

    支持:
    - 节奏驱动编排（BPM → 节拍对齐剪辑点）
    - 场景驱动编排（场景检测 → 高光优先）
    - 手动驱动编排（自定义顺序和时长）
    """

    def __init__(
        self,
        fps: float = 30.0,
        resolution: Tuple[int, int] = (1920, 1080),
        default_transition_duration: float = 0.3,
    ):
        self.fps = fps
        self.resolution = resolution
        self.default_transition_duration = default_transition_duration

        # 延迟导入依赖模块
        self._scene_detector = None
        self._beat_detector = None

    @property
    def scene_detector(self):
        if self._scene_detector is None:
            from .scene_detector import SceneDetector
            self._scene_detector = SceneDetector(fps=int(self.fps))
        return self._scene_detector

    @property
    def beat_detector(self):
        if self._beat_detector is None:
            from .beat_detector import BeatDetector
            self._beat_detector = BeatDetector()
        return self._beat_detector

    # ================================================================
    #  自动编排
    # ================================================================
    def build_timeline(
        self,
        clips: List[str],
        audio: str = None,
        style: TimelineStyle = TimelineStyle.DYNAMIC_CUT,
        target_duration: Optional[float] = None,
        clip_duration_range: Tuple[float, float] = (0.5, 4.0),
        with_transitions: bool = True,
        transition_type: str = "crossfade",
    ) -> Timeline:
        """
        智能编排时间线。

        Args:
            clips: 视频素材路径列表
            audio: 背景音乐路径
            style: 剪辑风格
            target_duration: 目标总时长
            clip_duration_range: 每个片段的时长范围
            with_transitions: 是否自动添加转场
            transition_type: 默认转场类型

        Returns:
            编排好的 Timeline 对象
        """
        import cv2

        timeline = Timeline(
            name=f"Timeline_{style.value}",
            fps=self.fps,
            resolution=self.resolution,
            style=style,
        )

        # --- 音频分析和节拍生成 ---
        beats = []
        structure = None
        clip_suggestions = []
        if audio and Path(audio).exists():
            try:
                beats = self.beat_detector.detect_beats(audio)
                structure = self.beat_detector.analyze_structure(audio)
                clip_suggestions = self.beat_detector.generate_clip_suggestions(
                    audio,
                    target_duration=target_duration,
                    min_clip_duration=clip_duration_range[0],
                    max_clip_duration=clip_duration_range[1],
                )
            except Exception as e:
                print(f"[TimelineComposer] Beat detection failed: {e}, using static timing")

        # --- 获取所有素材时长 ---
        clip_durations = {}
        for clip_path in clips:
            cap = cv2.VideoCapture(clip_path)
            if cap.isOpened():
                duration = cap.get(cv2.CAP_PROP_FRAME_COUNT) / cap.get(cv2.CAP_PROP_FPS)
                clip_durations[clip_path] = max(0.5, duration)
            else:
                clip_durations[clip_path] = 2.0
            cap.release()

        # --- 根据风格生成编排策略 ---
        if style == TimelineStyle.DYNAMIC_CUT and clip_suggestions:
            arrangement = self._style_dynamic_cut(clips, clip_suggestions, clip_durations, clip_duration_range, transition_type, with_transitions)

        elif style == TimelineStyle.FAST_BEAT and beats:
            arrangement = self._style_fast_beat(clips, beats, clip_durations, clip_duration_range, transition_type, with_transitions)

        elif style == TimelineStyle.SMOOTH_FLOW:
            arrangement = self._style_smooth_flow(clips, clip_durations, clip_duration_range, target_duration, transition_type, with_transitions)

        elif style == TimelineStyle.SLOW_CINEMATIC:
            arrangement = self._style_slow_cinematic(clips, clip_durations, target_duration, transition_type, with_transitions)

        elif style == TimelineStyle.GLITCH_STYLE and beats:
            arrangement = self._style_glitch(clips, beats, clip_durations, clip_duration_range, transition_type, with_transitions)

        elif style == TimelineStyle.VLOG:
            arrangement = self._style_vlog(clips, clip_durations, clip_duration_range, target_duration, transition_type, with_transitions)

        else:
            arrangement = self._style_dynamic_cut(clips, clip_suggestions, clip_durations, clip_duration_range, transition_type, with_transitions)

        # --- 构建轨道 ---
        video_track = Track(index=0, track_type=TrackType.VIDEO, label="Main Video")
        overlay_track = Track(index=1, track_type=TrackType.OVERLAY, label="Overlay")
        audio_track = Track(index=0, track_type=TrackType.AUDIO, label="Audio")

        current_time = 0.0
        clip_counter = 0
        transition_overlap = self.default_transition_duration if with_transitions else 0.0

        for item in arrangement:
            clip_counter += 1
            clip_id = item.get("id", f"clip_{clip_counter:04d}")
            source_path = item["source"]
            source_duration = clip_durations.get(source_path, 2.0)
            clip_dur = min(item.get("duration", source_duration), source_duration)

            # 随机选择源素材入点（在可用范围内）
            max_start = source_duration - clip_dur
            source_start = item.get("source_start", 0.0)
            if max_start > 0:
                import random
                source_start = random.uniform(0, max(0, max_start))

            # 应用变速
            speed = item.get("speed", 1.0)
            effective_dur = clip_dur / speed

            clip = ClipItem(
                id=clip_id,
                source_path=source_path,
                source_start=source_start,
                source_end=source_start + clip_dur,
                timeline_in=current_time,
                duration=effective_dur,
                speed=speed,
                scale=item.get("scale", 1.0),
                position_x=item.get("position_x", 0.5),
                position_y=item.get("position_y", 0.5),
                opacity=item.get("opacity", 1.0),
                metadata={
                    "style_match": item.get("style_match", ""),
                    "energy_level": item.get("energy_level", 0.5),
                },
            )

            # 转场
            if with_transitions and clip_counter > 1:
                clip.transition_in = {
                    "type": item.get("transition", transition_type),
                    "duration": transition_overlap,
                }
                # 上一个 clip 的出点转场
                if video_track.clips:
                    prev = video_track.clips[-1]
                    prev.transition_out = {
                        "type": item.get("transition", transition_type),
                        "duration": transition_overlap,
                    }
                    # 将当前 clip 入点前移 overlap
                    clip.timeline_in = max(0, current_time - transition_overlap)

            # 特效
            for effect in item.get("effects", []):
                clip.effects.append(effect)

            video_track.clips.append(clip)
            current_time = clip.timeline_in + effective_dur

        # --- 构建音频轨 ---
        if audio and Path(audio).exists():
            import cv2
            audio_clip = ClipItem(
                id="audio_bgm",
                source_path=audio,
                timeline_in=0.0,
                duration=current_time,
                track_type=TrackType.AUDIO,
            )
            audio_track.clips.append(audio_clip)

        # --- 添加节拍标记 ---
        if beats:
            for b in beats[:500]:  # 最多500个标记
                if b.time <= current_time:
                    timeline.markers.append({
                        "time": b.time,
                        "name": f"Bar_{b.bar}" if b.is_downbeat else f"Beat_{b.beat_index}",
                        "color": "red" if b.is_downbeat else "green",
                    })

        # --- 组装时间线 ---
        timeline.tracks = [video_track, overlay_track, audio_track]
        timeline.total_duration = current_time
        timeline.audio_source = audio

        if structure:
            timeline.metadata["music_structure"] = {
                "bpm": structure.tempo,
                "key": structure.key,
                "sections": structure.sections,
                "climax_regions": structure.climax_regions,
            }

        return timeline

    # ================================================================
    #  风格编排策略
    # ================================================================
    def _style_dynamic_cut(
        self,
        clips: List[str],
        suggestions: list,
        clip_durations: Dict[str, float],
        dur_range: Tuple[float, float],
        transition: str,
        with_transitions: bool,
    ) -> List[Dict]:
        """节奏卡点风格：按节拍建议分配素材"""
        arrangement = []
        min_dur, max_dur = dur_range

        for i, sug in enumerate(suggestions):
            if i >= len(clips):
                break
            effects = sug.suitable_effects if hasattr(sug, 'suitable_effects') else []
            arrangement.append({
                "id": f"dyn_{i:04d}",
                "source": clips[i % len(clips)],
                "duration": min(sug.duration, max_dur),
                "speed": 1.0,
                "energy_level": sug.energy_level,
                "transition": transition,
                "effects": effects,
                "style_match": "beat_aligned",
            })

        # 如果建议不够，用剩余素材填充
        if len(suggestions) < len(clips):
            remaining = clips[len(suggestions):]
            avg_dur = (min_dur + max_dur) / 2
            for i, clip in enumerate(remaining):
                arrangement.append({
                    "id": f"dyn_{len(arrangement):04d}",
                    "source": clip,
                    "duration": avg_dur,
                    "speed": 1.0,
                    "transition": transition,
                    "effects": [],
                    "style_match": "fill",
                })

        return arrangement

    def _style_fast_beat(
        self,
        clips: List[str],
        beats: list,
        clip_durations: Dict[str, float],
        dur_range: Tuple[float, float],
        transition: str,
        with_transitions: bool,
    ) -> List[Dict]:
        """快节奏风格：每2-4个节拍切一次"""
        arrangement = []
        min_dur, max_dur = dur_range
        beats_per_cut = 2  # 每2个节拍切换

        # 使用强拍（无强拍时降级为全体节拍，避免返回空编排）
        downbeats = [b for b in beats if b.is_downbeat] or beats

        for i, db in enumerate(downbeats):
            if i >= len(clips) * 3:
                break

            # 每隔 beats_per_cut 个小节切
            if i % beats_per_cut == 0:
                beat_time = max(beats[0].time, 0.01) if beats else 1.0
                dur = min(max_dur, 60.0 / (beat_time * 4) * beats_per_cut)
                effects = [{"name": "motion_blur", "intensity": 0.7}] if db.strength > 0.8 else []

                arrangement.append({
                    "id": f"fast_{i:04d}",
                    "source": clips[(i // beats_per_cut) % len(clips)],
                    "duration": dur,
                    "speed": 1.0 + db.strength * 0.3,
                    "energy_level": db.strength,
                    "transition": "glitch" if db.strength > 0.8 else transition,
                    "effects": effects,
                    "style_match": "fast_beat",
                })

        return arrangement

    def _style_smooth_flow(
        self,
        clips: List[str],
        clip_durations: Dict[str, float],
        dur_range: Tuple[float, float],
        target_duration: Optional[float],
        transition: str,
        with_transitions: bool,
    ) -> List[Dict]:
        """平滑风格：均衡分配时长，使用长渐隐转场"""
        min_dur, max_dur = dur_range
        avg_dur = (min_dur + max_dur) / 2

        # 计算总可用时长
        total_available = sum(clip_durations.get(c, 2.0) for c in clips)
        if target_duration and target_duration > total_available:
            effective_dur = avg_dur
        else:
            effective_dur = min(avg_dur * 1.5, total_available / max(len(clips), 1))

        arrangement = []
        for i, clip in enumerate(clips):
            arrangement.append({
                "id": f"smooth_{i:04d}",
                "source": clip,
                "duration": effective_dur,
                "speed": 0.9,
                "transition": "crossfade",
                "effects": [{"name": "soft_glow", "intensity": 0.3}],
                "style_match": "smooth",
            })

        return arrangement

    def _style_slow_cinematic(
        self,
        clips: List[str],
        clip_durations: Dict[str, float],
        target_duration: Optional[float],
        transition: str,
        with_transitions: bool,
    ) -> List[Dict]:
        """电影感慢节奏：长片段 + 慢速 + 黑边"""
        arrangement = []
        dur_each = 5.0 if not target_duration else target_duration / max(len(clips), 1)

        for i, clip in enumerate(clips):
            arrangement.append({
                "id": f"cinema_{i:04d}",
                "source": clip,
                "duration": dur_each,
                "speed": 0.8,
                "scale": 1.0,
                "transition": "dissolve",
                "effects": [
                    {"name": "letterbox", "ratio": 2.35},
                    {"name": "film_grain", "intensity": 0.2},
                    {"name": "color_grade_warm", "intensity": 0.4},
                ],
                "style_match": "cinematic",
            })

        return arrangement

    def _style_glitch(
        self,
        clips: List[str],
        beats: list,
        clip_durations: Dict[str, float],
        dur_range: Tuple[float, float],
        transition: str,
        with_transitions: bool,
    ) -> List[Dict]:
        """故障风格：短片段 + 故障转场 + RGB分离"""
        min_dur, _ = dur_range
        arrangement = []

        for i in range(min(len(clips) * 3, 60)):
            arrangement.append({
                "id": f"glitch_{i:04d}",
                "source": clips[i % len(clips)],
                "duration": min_dur * (0.5 + 0.5 * (i % 3 == 0)),
                "speed": 1.0 + (i % 3) * 0.5,
                "transition": "glitch",
                "effects": [
                    {"name": "rgb_split", "intensity": 0.6 + (i % 4) * 0.1},
                    {"name": "noise", "intensity": 0.3},
                    {"name": "shake", "intensity": 0.1},
                ],
                "style_match": "glitch",
            })

        return arrangement

    def _style_vlog(
        self,
        clips: List[str],
        clip_durations: Dict[str, float],
        dur_range: Tuple[float, float],
        target_duration: Optional[float],
        transition: str,
        with_transitions: bool,
    ) -> List[Dict]:
        """Vlog风格：自由节奏 + 缩放转场 + 文字覆盖"""
        min_dur, max_dur = dur_range
        arrangement = []

        for i, clip in enumerate(clips):
            dur = clip_durations.get(clip, max_dur)
            arrangement.append({
                "id": f"vlog_{i:04d}",
                "source": clip,
                "duration": min(dur, max_dur * 2),
                "speed": 1.0,
                "scale": 1.0,
                "transition": "zoom_in" if i % 3 == 0 else transition,
                "effects": [{"name": "color_boost", "intensity": 0.5}],
                "style_match": "vlog",
            })

        return arrangement

    # ================================================================
    #  手动编排 API
    # ================================================================
    def add_clip_to_track(
        self,
        timeline: Timeline,
        track_index: int,
        clip_item: ClipItem,
        auto_position: bool = True,
    ) -> Timeline:
        """手动向时间线轨道添加素材片段"""
        # 确保轨道存在
        while len(timeline.tracks) <= track_index:
            timeline.tracks.append(Track(
                index=len(timeline.tracks),
                track_type=TrackType.VIDEO,
                label=f"Track {len(timeline.tracks)}",
            ))

        track = timeline.tracks[track_index]

        if auto_position and track.clips:
            last = track.clips[-1]
            clip_item.timeline_in = (last.timeline_out or last.timeline_in + last.duration)

        track.clips.append(clip_item)

        # 更新总时长
        max_time = max(
            (c.timeline_out or c.timeline_in + c.duration)
            for t in timeline.tracks for c in t.clips
        ) if any(t.clips for t in timeline.tracks) else 0
        timeline.total_duration = max_time

        return timeline

    def add_nested_sequence(
        self,
        timeline: Timeline,
        sub_timeline: Timeline,
        insert_at: float,
        track_index: int = 0,
    ) -> Timeline:
        """将子时间线作为嵌套序列插入"""
        nested_clip = ClipItem(
            id=f"nested_{sub_timeline.name}",
            source_path="__NESTED__",
            timeline_in=insert_at,
            duration=sub_timeline.total_duration,
            metadata={"nested_timeline": sub_timeline.to_pr_json()},
        )
        return self.add_clip_to_track(timeline, track_index, nested_clip, auto_position=False)

    def fill_gaps(
        self,
        timeline: Timeline,
        fill_clips: List[str],
        track_index: int = 0,
    ) -> Timeline:
        """自动填充时间线间隙"""
        track = next((t for t in timeline.tracks if t.index == track_index), None)
        if not track or not track.clips:
            return timeline

        # 按时间排序
        sorted_clips = sorted(track.clips, key=lambda c: c.timeline_in)

        gaps = []
        current = 0.0

        for clip in sorted_clips:
            if clip.timeline_in > current + 0.05:  # 50ms 以上视为间隙
                gaps.append((current, clip.timeline_in))
            current = max(current, clip.timeline_out or clip.timeline_in + clip.duration)

        # 填充间隙
        for i, (gap_start, gap_end) in enumerate(gaps):
            if not fill_clips:
                break
            gap_dur = gap_end - gap_start
            fill_clip = fill_clips[i % len(fill_clips)]

            filler = ClipItem(
                id=f"fill_{i:04d}",
                source_path=fill_clip,
                timeline_in=gap_start,
                duration=gap_dur,
                metadata={"type": "gap_fill"},
            )
            track.clips.append(filler)

        return timeline

    # ================================================================
    #  导出
    # ================================================================
    def export_timeline_json(self, timeline: Timeline, output_path: str) -> str:
        """导出时间线为 JSON 文件"""
        data = timeline.to_pr_json()
        Path(output_path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
        return output_path

    def export_timeline_edl(self, timeline: Timeline, output_path: str) -> str:
        """导出 EDL 格式"""
        lines = [f'TITLE: {timeline.name}', 'FCM: NON-DROP FRAME', '']

        for track in timeline.tracks:
            for i, clip in enumerate(track.clips, 1):
                tc_in = self._sec_to_tc(clip.timeline_in)
                tc_out = self._sec_to_tc(clip.timeline_out or clip.timeline_in + clip.duration)
                src_tc = self._sec_to_tc(clip.source_start)
                lines.append(f'{i:03d}  {track.label[:4]:4s} V     C        {tc_in} {tc_out} {src_tc} {self._sec_to_tc(clip.source_start + clip.duration)}')
                lines.append(f'* FROM CLIP NAME:  {Path(clip.source_path).name}')
                lines.append('')

        Path(output_path).write_text('\n'.join(lines), encoding='utf-8')
        return output_path

    @staticmethod
    def _sec_to_tc(seconds: float, fps: int = 30) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        f = int((seconds - int(seconds)) * fps)
        return f"{h:02d}:{m:02d}:{s:02d}:{f:02d}"


__all__ = [
    "TimelineComposer",
    "Timeline",
    "Track",
    "ClipItem",
    "TimelineStyle",
    "TrackType",
]
