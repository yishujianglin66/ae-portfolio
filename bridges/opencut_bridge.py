"""
opencut_bridge.py — OpenCut ↔ AE-Knowledge-Vault 桥接模块
===========================================================

OpenCut 是 GitHub 最火的开源剪映替代品 (74k+ Stars, MIT 协议)。
本模块实现 EditScript/VRS 分析结果 ↔ OpenCut 工程格式的双向转换。

架构:
  EditScript (内部) ──→ OpenCutProject (JSON) ──→ OpenCut Web/Desktop
  OpenCutProject (JSON) ──→ EditScript (内部) ──→ AE 自动化管线

功能:
  1. EditScript → OpenCut 工程导出 (时间轴/字幕/特效/转场)
  2. OpenCut 工程 → EditScript 导入 (反向解析)
  3. VRS 分析结果 → OpenCut 时间轴标注
  4. 多平台导出 (抖音/B站/YouTube 格式适配)

用法:
    bridge = OpenCutBridge()

    # 导出到 OpenCut
    bridge.export_to_opencut(edit_script, "project.opc")

    # 从 OpenCut 导入
    script = bridge.import_from_opencut("project.opc")

    # VRS 分析结果 → OpenCut 时间轴
    bridge.vrs_to_timeline(vrs_result, "timeline.opc")
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


def log(msg: str, level: str = "INFO"):
    ts = time.strftime("%H:%M:%S")
    print(f"  [{ts}][{level}] {msg}")


# ================================================================
#  OpenCut 工程数据结构
# ================================================================

@dataclass
class OpenCutClip:
    """OpenCut 时间轴片段。"""
    id: str = ""
    source_path: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    timeline_start: float = 0.0
    track_index: int = 0
    transition_in: str = ""
    transition_out: str = ""
    transition_duration: float = 0.5
    effects: list[dict[str, Any]] = field(default_factory=list)
    filters: list[dict[str, Any]] = field(default_factory=list)
    text_overlays: list[dict[str, Any]] = field(default_factory=list)
    speed: float = 1.0
    opacity: float = 1.0
    volume: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source": self.source_path,
            "in": self.start_time,
            "out": self.end_time,
            "timeline_start": self.timeline_start,
            "track": self.track_index,
            "transition_in": {"type": self.transition_in, "duration": self.transition_duration},
            "transition_out": {"type": self.transition_out, "duration": self.transition_duration},
            "effects": self.effects,
            "filters": self.filters,
            "text": self.text_overlays,
            "speed": self.speed,
            "opacity": self.opacity,
            "volume": self.volume,
        }


@dataclass
class OpenCutTrack:
    """OpenCut 轨道。"""
    id: str = ""
    name: str = ""
    track_type: str = "video"  # video / audio / text
    clips: list[OpenCutClip] = field(default_factory=list)
    muted: bool = False
    locked: bool = False
    visible: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.track_type,
            "clips": [c.to_dict() for c in self.clips],
            "muted": self.muted,
            "locked": self.locked,
            "visible": self.visible,
        }


@dataclass
class OpenCutProject:
    """OpenCut 工程文件。"""
    name: str = "Untitled"
    version: str = "2.0"
    canvas_width: int = 1920
    canvas_height: int = 1080
    fps: int = 30
    duration: float = 0.0
    tracks: list[OpenCutTrack] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "canvas": {"width": self.canvas_width, "height": self.canvas_height},
            "fps": self.fps,
            "duration": self.duration,
            "tracks": [t.to_dict() for t in self.tracks],
            "metadata": self.metadata,
        }

    def save(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        log(f"  OpenCut project saved: {path}")

    @classmethod
    def load(cls, path: str) -> "OpenCutProject":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        project = cls(
            name=data.get("name", "Untitled"),
            canvas_width=data.get("canvas", {}).get("width", 1920),
            canvas_height=data.get("canvas", {}).get("height", 1080),
            fps=data.get("fps", 30),
            duration=data.get("duration", 0),
            metadata=data.get("metadata", {}),
        )
        for td in data.get("tracks", []):
            track = OpenCutTrack(
                id=td.get("id", ""),
                name=td.get("name", ""),
                track_type=td.get("type", "video"),
                muted=td.get("muted", False),
                locked=td.get("locked", False),
                visible=td.get("visible", True),
            )
            for cd in td.get("clips", []):
                clip = OpenCutClip(
                    id=cd.get("id", ""),
                    source_path=cd.get("source", ""),
                    start_time=cd.get("in", 0),
                    end_time=cd.get("out", 0),
                    timeline_start=cd.get("timeline_start", 0),
                    track_index=td.get("track", 0),
                    speed=cd.get("speed", 1.0),
                    opacity=cd.get("opacity", 1.0),
                    volume=cd.get("volume", 1.0),
                    effects=cd.get("effects", []),
                    filters=cd.get("filters", []),
                    text_overlays=cd.get("text", []),
                )
                ti = cd.get("transition_in", {})
                to = cd.get("transition_out", {})
                clip.transition_in = ti.get("type", "") if isinstance(ti, dict) else str(ti)
                clip.transition_out = to.get("type", "") if isinstance(to, dict) else str(to)
                clip.transition_duration = ti.get("duration", 0.5) if isinstance(ti, dict) else 0.5
                track.clips.append(clip)
            project.tracks.append(track)
        return project


# ================================================================
#  转场映射表: EditScript → OpenCut
# ================================================================

TRANSITION_MAP = {
    # EditScript 转场名 → OpenCut 转场名
    "cut": "none",
    "dissolve": "dissolve",
    "cross_dissolve": "dissolve",
    "fade_in": "fade_in",
    "fade_out": "fade_out",
    "fade_black": "fade_black",
    "wipe_left": "wipe_left",
    "wipe_right": "wipe_right",
    "wipe_up": "wipe_up",
    "wipe_down": "wipe_down",
    "slide_left": "slide_left",
    "slide_right": "slide_right",
    "zoom_in": "zoom_in",
    "zoom_out": "zoom_out",
    "flash_cut": "flash_white",
    "flash_white": "flash_white",
    "impact": "impact",
    "whip_pan": "whip_pan",
    "glitch": "glitch",
    "spin": "spin",
    "blur_transition": "blur_dissolve",
    "light_leak": "light_leak",
    "film_burn": "film_burn",
}

# 特效映射
EFFECT_MAP = {
    "motion_blur": {"name": "MotionBlur", "params": {"amount": 50}},
    "speed_lines": {"name": "SpeedLines", "params": {"density": 0.7}},
    "glow": {"name": "Glow", "params": {"intensity": 0.6, "radius": 20}},
    "lens_flare": {"name": "LensFlare", "params": {"intensity": 0.5}},
    "shake": {"name": "CameraShake", "params": {"magnitude": 5, "frequency": 10}},
    "vignette": {"name": "Vignette", "params": {"amount": 0.5}},
    "film_grain": {"name": "FilmGrain", "params": {"amount": 0.3}},
    "chromatic_aberration": {"name": "ChromaticAberration", "params": {"offset": 3}},
    "bloom": {"name": "Bloom", "params": {"threshold": 0.8, "intensity": 0.5}},
}

# 滤镜映射
FILTER_MAP = {
    "cinematic": {"name": "Cinematic", "params": {"contrast": 1.2, "saturation": 0.9, "temp": 5800}},
    "warm": {"name": "WarmTone", "params": {"temperature": 6500, "tint": 10}},
    "cool": {"name": "CoolTone", "params": {"temperature": 4500, "tint": -5}},
    "vintage": {"name": "Vintage", "params": {"contrast": 1.1, "saturation": 0.7, "grain": 0.2}},
    "noir": {"name": "Noir", "params": {"saturation": 0, "contrast": 1.5}},
    "punchy": {"name": "Punchy", "params": {"contrast": 1.3, "saturation": 1.3, "vibrance": 20}},
}


# ================================================================
#  桥接器
# ================================================================

class OpenCutBridge:
    """OpenCut ↔ AE-Knowledge-Vault 桥接器。

    实现 EditScript / VRS 分析结果与 OpenCut 工程格式的双向转换。
    """

    def __init__(self):
        self._transition_map = TRANSITION_MAP.copy()
        self._effect_map = EFFECT_MAP.copy()
        self._filter_map = FILTER_MAP.copy()

    # ---- EditScript → OpenCut ----

    def export_to_opencut(self, edit_script: dict[str, Any], output_path: str) -> dict[str, Any]:
        """将 EditScript 导出为 OpenCut 工程文件。

        Args:
            edit_script: EditScript dict (from MultimodalDirector / AIDirector)
            output_path: 输出 .opc 文件路径

        Returns:
            导出结果
        """
        log("--- EditScript → OpenCut 导出 ---")

        project = OpenCutProject(
            name=edit_script.get("title", "AE-Vault Export"),
            fps=edit_script.get("fps", 30),
            metadata={
                "source": "AE-Knowledge-Vault",
                "export_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "style": edit_script.get("style", {}),
            },
        )

        # 解析画布尺寸
        resolution = edit_script.get("resolution", "1920x1080")
        if "x" in resolution:
            w, h = resolution.split("x")
            project.canvas_width = int(w)
            project.canvas_height = int(h)

        # 主视频轨道
        video_track = OpenCutTrack(id="track_v1", name="Video", track_type="video")
        audio_track = OpenCutTrack(id="track_a1", name="Audio", track_type="audio")
        text_track = OpenCutTrack(id="track_t1", name="Text", track_type="text")

        timeline_pos = 0.0
        segments = edit_script.get("segments", [])

        for i, seg in enumerate(segments):
            clip_id = f"clip_{i:03d}"
            duration = seg.get("duration", 3.0)

            # 视频片段
            clip = OpenCutClip(
                id=clip_id,
                source_path=seg.get("source", seg.get("media_path", "")),
                start_time=seg.get("in_point", 0),
                end_time=seg.get("out_point", duration),
                timeline_start=timeline_pos,
                track_index=0,
                speed=seg.get("speed", 1.0),
            )

            # 转场
            transition = seg.get("transition", "")
            if transition:
                clip.transition_in = self._transition_map.get(transition, transition)
                clip.transition_duration = seg.get("transition_duration", 0.5)

            # 特效
            effects = seg.get("effects", [])
            for eff_name in effects:
                if eff_name in self._effect_map:
                    clip.effects.append(self._effect_map[eff_name])
                else:
                    clip.effects.append({"name": eff_name, "params": {}})

            # 滤镜
            color_grade = seg.get("color_grade", seg.get("filter", ""))
            if color_grade and color_grade in self._filter_map:
                clip.filters.append(self._filter_map[color_grade])

            video_track.clips.append(clip)

            # 字幕/文字叠加
            subtitle = seg.get("subtitle", seg.get("text", ""))
            if subtitle:
                text_clip = OpenCutClip(
                    id=f"text_{i:03d}",
                    timeline_start=timeline_pos,
                    track_index=2,
                )
                text_clip.text_overlays.append({
                    "text": subtitle,
                    "font": seg.get("font", "思源黑体"),
                    "size": seg.get("font_size", 48),
                    "color": seg.get("font_color", "#FFFFFF"),
                    "position": seg.get("text_position", "bottom_center"),
                    "animation": seg.get("text_animation", "fade_in"),
                })
                text_track.clips.append(text_clip)

            timeline_pos += duration

        # 音频轨道
        bgm = edit_script.get("bgm_path", edit_script.get("audio", ""))
        if bgm:
            audio_clip = OpenCutClip(
                id="bgm_000",
                source_path=bgm,
                start_time=0,
                end_time=timeline_pos,
                timeline_start=0,
                track_index=1,
            )
            audio_track.clips.append(audio_clip)

        project.tracks = [video_track, audio_track, text_track]
        project.duration = timeline_pos

        # 保存
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        project.save(str(output))

        log(f"  Exported: {len(segments)} segments, {project.duration:.1f}s")
        return {
            "success": True,
            "path": str(output),
            "segments": len(segments),
            "duration": project.duration,
            "tracks": len(project.tracks),
        }

    # ---- OpenCut → EditScript ----

    def import_from_opencut(self, project_path: str) -> dict[str, Any]:
        """从 OpenCut 工程文件导入为 EditScript。

        Args:
            project_path: .opc 文件路径

        Returns:
            EditScript dict
        """
        log("--- OpenCut → EditScript 导入 ---")

        project = OpenCutProject.load(project_path)

        edit_script = {
            "title": project.name,
            "fps": project.fps,
            "resolution": f"{project.canvas_width}x{project.canvas_height}",
            "total_duration": project.duration,
            "segments": [],
            "style": project.metadata.get("style", {}),
            "metadata": project.metadata,
        }

        # 从视频轨道提取片段
        for track in project.tracks:
            if track.track_type == "video":
                for clip in track.clips:
                    segment = {
                        "source": clip.source_path,
                        "duration": clip.end_time - clip.start_time,
                        "in_point": clip.start_time,
                        "out_point": clip.end_time,
                        "timeline_start": clip.timeline_start,
                        "speed": clip.speed,
                        "transition": self._reverse_transition(clip.transition_in),
                        "effects": [e.get("name", "") for e in clip.effects],
                        "filters": [f.get("name", "") for f in clip.filters],
                    }
                    edit_script["segments"].append(segment)

            elif track.track_type == "audio":
                for clip in track.clips:
                    if "bgm" in clip.id:
                        edit_script["bgm_path"] = clip.source_path

            elif track.track_type == "text":
                for clip in track.clips:
                    for txt in clip.text_overlays:
                        # 找到对应时间位置的视频片段，添加字幕
                        for seg in edit_script["segments"]:
                            if abs(seg.get("timeline_start", 0) - clip.timeline_start) < 0.1:
                                seg["subtitle"] = txt.get("text", "")
                                seg["font"] = txt.get("font", "")
                                break

        log(f"  Imported: {len(edit_script['segments'])} segments")
        return edit_script

    # ---- VRS → OpenCut ----

    def vrs_to_timeline(self, vrs_result: dict[str, Any], output_path: str) -> dict[str, Any]:
        """将 VRS 分析结果转换为 OpenCut 时间轴。

        Args:
            vrs_result: VRS 分析结果 (from VRSOrchestrator)
            output_path: 输出路径

        Returns:
            导出结果
        """
        log("--- VRS → OpenCut 时间轴 ---")

        edit_script = {
            "title": vrs_result.get("title", "VRS Analysis Export"),
            "fps": vrs_result.get("fps", 30),
            "resolution": vrs_result.get("resolution", "1920x1080"),
            "segments": [],
            "style": vrs_result.get("style", {}),
        }

        # 从 VRS 效果分析提取时间轴
        effects_timeline = vrs_result.get("effects_timeline", [])
        for item in effects_timeline:
            segment = {
                "source": item.get("source", ""),
                "duration": item.get("duration", 3.0),
                "in_point": item.get("start_time", 0),
                "out_point": item.get("end_time", 3.0),
                "effects": item.get("effects", []),
                "transition": item.get("transition", ""),
                "color_grade": item.get("color_grade", ""),
                "speed": item.get("speed", 1.0),
            }
            edit_script["segments"].append(segment)

        # 如果没有 effects_timeline，尝试从 segments 直接映射
        if not effects_timeline:
            for seg in vrs_result.get("segments", []):
                segment = {
                    "source": seg.get("source", ""),
                    "duration": seg.get("duration", 3.0),
                    "effects": seg.get("detected_effects", []),
                    "transition": seg.get("transition", ""),
                    "color_grade": seg.get("color_palette", {}).get("preset", ""),
                }
                edit_script["segments"].append(segment)

        return self.export_to_opencut(edit_script, output_path)

    # ---- 辅助方法 ----

    def _reverse_transition(self, opencut_transition: str) -> str:
        """反向映射: OpenCut 转场名 → EditScript 转场名。"""
        reverse_map = {v: k for k, v in self._transition_map.items()}
        return reverse_map.get(opencut_transition, opencut_transition)

    def get_supported_transitions(self) -> list[str]:
        """获取所有支持的转场类型。"""
        return list(TRANSITION_MAP.keys())

    def get_supported_effects(self) -> list[str]:
        """获取所有支持的特效。"""
        return list(EFFECT_MAP.keys())

    def get_supported_filters(self) -> list[str]:
        """获取所有支持的滤镜。"""
        return list(FILTER_MAP.keys())


# ================================================================
#  快捷函数
# ================================================================

def export_to_opencut(edit_script: dict, output_path: str) -> dict:
    """快捷导出到 OpenCut。"""
    bridge = OpenCutBridge()
    return bridge.export_to_opencut(edit_script, output_path)


def import_from_opencut(project_path: str) -> dict:
    """快捷从 OpenCut 导入。"""
    bridge = OpenCutBridge()
    return bridge.import_from_opencut(project_path)


if __name__ == "__main__":
    # 自测
    bridge = OpenCutBridge()

    # 测试 EditScript → OpenCut
    test_script = {
        "title": "Test Export",
        "fps": 30,
        "resolution": "1920x1080",
        "segments": [
            {
                "source": "clip1.mp4",
                "duration": 3.0,
                "transition": "dissolve",
                "effects": ["glow", "shake"],
                "color_grade": "cinematic",
                "subtitle": "测试字幕",
            },
            {
                "source": "clip2.mp4",
                "duration": 5.0,
                "transition": "flash_cut",
                "effects": ["motion_blur"],
                "speed": 1.5,
            },
        ],
        "bgm_path": "bgm.mp3",
    }

    result = bridge.export_to_opencut(test_script, "test_output.opc")
    print(f"Export result: {result}")

    # 测试反向导入
    imported = bridge.import_from_opencut("test_output.opc")
    print(f"Import result: {len(imported.get('segments', []))} segments")

    # 清理测试文件
    if os.path.exists("test_output.opc"):
        os.remove("test_output.opc")
