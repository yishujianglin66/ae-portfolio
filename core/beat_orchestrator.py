#!/usr/bin/env python3
"""
节拍编排器 (Beat Orchestrator)
基于BPM的音乐节拍编排与关键帧生成系统
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import math


@dataclass
class BeatSyncConfig:
    """节拍同步配置"""
    property_type: str
    base_value: float
    beat_value: float
    attack: float = 0.05
    decay: float = 0.15
    easing: str = "ease_out"
    sync_mode: str = "on_beat"


@dataclass
class MusicalSection:
    """音乐段落"""
    type: str
    start_time: float
    end_time: float
    energy: float
    intensity_multiplier: float = 1.0


MUSICAL_STRUCTURE_TEMPLATES = {
    "pop_song": [
        {"type": "intro", "duration_ratio": 0.1, "energy": 0.3, "intensity": 0.5},
        {"type": "verse", "duration_ratio": 0.25, "energy": 0.5, "intensity": 0.7},
        {"type": "chorus", "duration_ratio": 0.2, "energy": 0.9, "intensity": 1.0},
        {"type": "verse", "duration_ratio": 0.2, "energy": 0.55, "intensity": 0.75},
        {"type": "chorus", "duration_ratio": 0.15, "energy": 0.95, "intensity": 1.0},
        {"type": "bridge", "duration_ratio": 0.07, "energy": 0.4, "intensity": 0.6},
        {"type": "outro", "duration_ratio": 0.03, "energy": 0.2, "intensity": 0.3},
    ],
    "edm_drop": [
        {"type": "intro", "duration_ratio": 0.1, "energy": 0.2, "intensity": 0.4},
        {"type": "build_up", "duration_ratio": 0.2, "energy": 0.6, "intensity": 0.7},
        {"type": "drop", "duration_ratio": 0.35, "energy": 1.0, "intensity": 1.0},
        {"type": "breakdown", "duration_ratio": 0.15, "energy": 0.3, "intensity": 0.5},
        {"type": "drop", "duration_ratio": 0.15, "energy": 1.0, "intensity": 1.0},
        {"type": "outro", "duration_ratio": 0.05, "energy": 0.15, "intensity": 0.25},
    ],
    "short_hook": [
        {"type": "intro", "duration_ratio": 0.1, "energy": 0.4, "intensity": 0.5},
        {"type": "hook", "duration_ratio": 0.6, "energy": 0.9, "intensity": 1.0},
        {"type": "outro", "duration_ratio": 0.3, "energy": 0.3, "intensity": 0.4},
    ],
}

BEAT_EFFECT_STYLES = {
    "energetic": {
        "scale": {"base": 1.0, "beat": 1.15, "attack": 0.03, "decay": 0.12},
        "opacity": {"base": 1.0, "beat": 1.0, "attack": 0.02, "decay": 0.08},
        "position": {"base": 0.0, "beat": 5.0, "attack": 0.04, "decay": 0.15},
        "rotation": {"base": 0.0, "beat": 2.0, "attack": 0.03, "decay": 0.1},
        "effects": ["glow_pulse", "sharpen_pulse"],
        "effect_intensity": 0.8,
    },
    "chill": {
        "scale": {"base": 1.0, "beat": 1.05, "attack": 0.08, "decay": 0.25},
        "opacity": {"base": 0.8, "beat": 1.0, "attack": 0.06, "decay": 0.2},
        "position": {"base": 0.0, "beat": 2.0, "attack": 0.1, "decay": 0.3},
        "rotation": {"base": 0.0, "beat": 0.5, "attack": 0.08, "decay": 0.2},
        "effects": ["glow_pulse"],
        "effect_intensity": 0.3,
    },
    "heavy": {
        "scale": {"base": 1.0, "beat": 1.25, "attack": 0.02, "decay": 0.2},
        "opacity": {"base": 0.7, "beat": 1.0, "attack": 0.01, "decay": 0.15},
        "position": {"base": 0.0, "beat": 10.0, "attack": 0.02, "decay": 0.18},
        "rotation": {"base": 0.0, "beat": 5.0, "attack": 0.02, "decay": 0.15},
        "effects": ["glow_pulse", "sharpen_pulse", "shake"],
        "effect_intensity": 1.0,
    },
    "subtle": {
        "scale": {"base": 1.0, "beat": 1.02, "attack": 0.1, "decay": 0.3},
        "opacity": {"base": 0.95, "beat": 1.0, "attack": 0.08, "decay": 0.25},
        "position": {"base": 0.0, "beat": 1.0, "attack": 0.12, "decay": 0.35},
        "rotation": {"base": 0.0, "beat": 0.2, "attack": 0.1, "decay": 0.3},
        "effects": [],
        "effect_intensity": 0.15,
    },
}


class BeatOrchestrator:
    """节拍编排器"""

    def __init__(self, bpm: float = 120, fps: int = 30, beats_per_measure: int = 4):
        self.bpm = bpm
        self.fps = fps
        self.beats_per_measure = beats_per_measure
        self.beat_interval = 60.0 / bpm
        self.measure_interval = self.beat_interval * beats_per_measure

    def generate_beat_timeline(self, duration: float, offset: float = 0.0) -> List[float]:
        """生成所有节拍时间点"""
        beats = []
        t = offset
        while t <= duration + offset:
            beats.append(round(t, 4))
            t += self.beat_interval
        return beats

    def generate_downbeats(self, duration: float, offset: float = 0.0) -> List[float]:
        """生成重拍时间点（每小节第一拍）"""
        downbeats = []
        t = offset
        beat_index = 0
        while t <= duration + offset:
            if beat_index % self.beats_per_measure == 0:
                downbeats.append(round(t, 4))
            t += self.beat_interval
            beat_index += 1
        return downbeats

    def generate_offbeats(self, duration: float, offset: float = 0.0) -> List[float]:
        """生成弱拍（偶数拍）"""
        offbeats = []
        t = offset
        beat_index = 0
        while t <= duration + offset:
            if beat_index % 2 == 1:
                offbeats.append(round(t, 4))
            t += self.beat_interval
            beat_index += 1
        return offbeats

    def generate_beat_synced_keyframes(
        self,
        layer_name: str,
        beat_times: List[float],
        config: BeatSyncConfig,
    ) -> List[Dict[str, Any]]:
        """生成节拍同步关键帧"""
        keyframes = []
        prop_map = {
            "scale": "Scale",
            "opacity": "Opacity",
            "position": "Position",
            "rotation": "Rotation",
        }
        property_name = prop_map.get(config.property_type, config.property_type)

        for beat_time in beat_times:
            attack_end = beat_time + config.attack
            decay_end = attack_end + config.decay

            keyframes.append({
                "layerName": layer_name,
                "propertyName": property_name,
                "time": round(beat_time, 4),
                "value": config.base_value,
                "easeType": config.easing,
            })

            keyframes.append({
                "layerName": layer_name,
                "propertyName": property_name,
                "time": round(attack_end, 4),
                "value": config.beat_value,
                "easeType": "ease_in",
            })

            keyframes.append({
                "layerName": layer_name,
                "propertyName": property_name,
                "time": round(decay_end, 4),
                "value": config.base_value,
                "easeType": "ease_out",
            })

        return keyframes

    def generate_beat_effect_triggers(
        self,
        layer_name: str,
        beat_times: List[float],
        effect_type: str,
        intensity: float = 1.0,
    ) -> List[Dict[str, Any]]:
        """生成节拍触发效果"""
        triggers = []

        effect_param_map = {
            "glow_pulse": {
                "property": "Glow Intensity",
                "base": 0.0,
                "peak": 100.0 * intensity,
                "attack": 0.03,
                "decay": 0.2,
            },
            "sharpen_pulse": {
                "property": "Sharpen Amount",
                "base": 0.0,
                "peak": 50.0 * intensity,
                "attack": 0.02,
                "decay": 0.15,
            },
        }

        params = effect_param_map.get(effect_type)
        if params is None:
            return triggers

        for beat_time in beat_times:
            attack_end = beat_time + params["attack"]
            decay_end = attack_end + params["decay"]

            triggers.append({
                "layerName": layer_name,
                "propertyName": params["property"],
                "time": round(beat_time, 4),
                "value": params["base"],
                "easeType": "ease_out",
            })

            triggers.append({
                "layerName": layer_name,
                "propertyName": params["property"],
                "time": round(attack_end, 4),
                "value": params["peak"],
                "easeType": "ease_in",
            })

            triggers.append({
                "layerName": layer_name,
                "propertyName": params["property"],
                "time": round(decay_end, 4),
                "value": params["base"],
                "easeType": "ease_out",
            })

        return triggers

    def generate_musical_structure(
        self,
        duration: float,
        template: str = "pop_song",
    ) -> List[MusicalSection]:
        """生成音乐结构段落"""
        template_data = MUSICAL_STRUCTURE_TEMPLATES.get(template)
        if template_data is None:
            template_data = MUSICAL_STRUCTURE_TEMPLATES["pop_song"]

        sections = []
        current_time = 0.0

        for seg in template_data:
            seg_duration = duration * seg["duration_ratio"]
            end_time = current_time + seg_duration

            sections.append(MusicalSection(
                type=seg["type"],
                start_time=round(current_time, 4),
                end_time=round(end_time, 4),
                energy=seg["energy"],
                intensity_multiplier=seg["intensity"],
            ))

            current_time = end_time

        if sections and sections[-1].end_time < duration:
            sections[-1].end_time = round(duration, 4)

        return sections

    def energy_to_intensity(self, energy: float) -> float:
        """能量0-1映射到强度0-1"""
        energy = max(0.0, min(1.0, energy))
        intensity = math.pow(energy, 0.8)
        return round(intensity, 4)

    def generate_full_beat_show(
        self,
        layer_name: str,
        duration: float,
        style: str = "energetic",
        structure_template: str = "pop_song",
    ) -> Dict[str, Any]:
        """生成完整节拍秀（含效果和关键帧）"""
        style_config = BEAT_EFFECT_STYLES.get(style)
        if style_config is None:
            style_config = BEAT_EFFECT_STYLES["energetic"]

        sections = self.generate_musical_structure(duration, structure_template)

        all_keyframes = []
        all_effects = []

        for section in sections:
            section_duration = section.end_time - section.start_time
            if section_duration <= 0:
                continue

            beat_times = self.generate_beat_timeline(
                section_duration, offset=section.start_time
            )

            intensity = self.energy_to_intensity(section.energy) * section.intensity_multiplier

            for prop_type in ["scale", "opacity", "position", "rotation"]:
                prop_style = style_config[prop_type]
                base = prop_style["base"]
                beat_val = base + (prop_style["beat"] - base) * intensity

                config = BeatSyncConfig(
                    property_type=prop_type,
                    base_value=base,
                    beat_value=beat_val,
                    attack=prop_style["attack"],
                    decay=prop_style["decay"],
                    easing="ease_out",
                    sync_mode="on_beat",
                )

                keyframes = self.generate_beat_synced_keyframes(
                    layer_name, beat_times, config
                )
                all_keyframes.extend(keyframes)

            effect_intensity = style_config["effect_intensity"] * intensity
            for effect_type in style_config["effects"]:
                effects = self.generate_beat_effect_triggers(
                    layer_name, beat_times, effect_type, effect_intensity
                )
                all_effects.extend(effects)

        return {
            "layerName": layer_name,
            "duration": duration,
            "style": style,
            "structure_template": structure_template,
            "sections": [
                {
                    "type": s.type,
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                    "energy": s.energy,
                    "intensity_multiplier": s.intensity_multiplier,
                }
                for s in sections
            ],
            "keyframes": all_keyframes,
            "effect_triggers": all_effects,
            "total_keyframes": len(all_keyframes),
            "total_effects": len(all_effects),
        }
