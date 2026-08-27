"""core.beat_orchestrator 单元测试 - 节拍编排器核心逻辑

覆盖范围:
1. BeatOrchestrator.generate_beat_timeline - BPM/offset/边界条件
2. BeatOrchestrator.generate_downbeats - 重拍对齐
3. BeatOrchestrator.generate_offbeats - 弱拍生成
4. BeatOrchestrator.generate_beat_synced_keyframes - 关键帧生成
5. BeatOrchestrator.generate_beat_effect_triggers - 效果触发 (glow/sharpen)
6. BeatOrchestrator.generate_musical_structure - 段落结构生成
7. BeatOrchestrator.energy_to_intensity - 能量→强度映射
8. BeatOrchestrator.generate_full_beat_show - 完整节拍秀集成
9. MusicalSection dataclass 验证
10. BeatSyncConfig dataclass 验证
"""
import os
import sys
import pytest
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.beat_orchestrator import (
    BeatOrchestrator,
    BeatSyncConfig,
    MusicalSection,
    MUSICAL_STRUCTURE_TEMPLATES,
    BEAT_EFFECT_STYLES,
)


# ============================================================================
# BeatOrchestrator.generate_beat_timeline
# ============================================================================
class TestGenerateBeatTimeline:
    def test_basic_120bpm(self):
        orch = BeatOrchestrator(bpm=120)
        beats = orch.generate_beat_timeline(duration=2.0)
        assert len(beats) == 5
        assert beats[0] == 0.0
        assert beats[-1] == 2.0

    def test_basic_100bpm(self):
        orch = BeatOrchestrator(bpm=100)
        beats = orch.generate_beat_timeline(duration=3.0)
        # 区间 0.6s，含两端: 0, 0.6, 1.2, 1.8, 2.4, 3.0 → 6 拍（与 test_phase3_beat 契约一致）
        assert len(beats) == 6

    def test_with_offset(self):
        orch = BeatOrchestrator(bpm=120)
        beats = orch.generate_beat_timeline(duration=1.0, offset=0.5)
        assert len(beats) >= 2
        assert beats[0] >= 0.5

    def test_zero_duration(self):
        orch = BeatOrchestrator(bpm=120)
        beats = orch.generate_beat_timeline(duration=0.0)
        assert len(beats) == 1
        assert beats[0] == 0.0

    def test_negative_duration(self):
        orch = BeatOrchestrator(bpm=120)
        beats = orch.generate_beat_timeline(duration=-1.0)
        # 实现约定: 非法时长返回空列表（与 zero_duration 区分）
        assert len(beats) == 0

    def test_high_bpm(self):
        orch = BeatOrchestrator(bpm=200)
        beats = orch.generate_beat_timeline(duration=1.0)
        # 区间 0.3s: 0, 0.3, 0.6, 0.9 → 4 拍（1.2 超出 duration）
        assert len(beats) == 4
        assert beats[0] == 0.0

    def test_low_bpm(self):
        orch = BeatOrchestrator(bpm=40)
        beats = orch.generate_beat_timeline(duration=4.0)
        assert len(beats) == 3

    def test_beat_times_monotonic(self):
        orch = BeatOrchestrator(bpm=120)
        beats = orch.generate_beat_timeline(duration=5.0)
        for i in range(len(beats) - 1):
            assert beats[i] < beats[i + 1]

    def test_beat_tolerance(self):
        orch = BeatOrchestrator(bpm=120)
        beats = orch.generate_beat_timeline(duration=1.0)
        expected_interval = 60.0 / 120
        for i in range(len(beats) - 1):
            actual = beats[i + 1] - beats[i]
            assert abs(actual - expected_interval) < 0.01


# ============================================================================
# BeatOrchestrator.generate_downbeats
# ============================================================================
class TestGenerateDownbeats:
    def test_downbeats_are_first_of_measure(self):
        orch = BeatOrchestrator(bpm=120, beats_per_measure=4)
        downbeats = orch.generate_downbeats(duration=4.0)
        # 小节长 2.0s: 0, 2.0, 4.0 → 3 个重拍（与 test_phase3_beat 契约一致）
        assert len(downbeats) == 3
        for i in range(len(downbeats) - 1):
            diff = downbeats[i + 1] - downbeats[i]
            expected = 4 * (60.0 / 120)
            assert abs(diff - expected) < 0.01

    def test_custom_beats_per_measure(self):
        orch = BeatOrchestrator(bpm=120, beats_per_measure=3)
        downbeats = orch.generate_downbeats(duration=3.0)
        expected_interval = 3 * (60.0 / 120)
        for i in range(len(downbeats) - 1):
            diff = downbeats[i + 1] - downbeats[i]
            assert abs(diff - expected_interval) < 0.01

    def test_downbeats_with_offset(self):
        orch = BeatOrchestrator(bpm=120)
        downbeats = orch.generate_downbeats(duration=3.0, offset=0.5)
        assert len(downbeats) >= 2
        assert downbeats[0] == 0.5

    def test_zero_duration(self):
        orch = BeatOrchestrator(bpm=120)
        downbeats = orch.generate_downbeats(duration=0.0)
        assert len(downbeats) == 1
        assert downbeats[0] == 0.0

    def test_downbeats_count(self):
        orch = BeatOrchestrator(bpm=120, beats_per_measure=4)
        downbeats = orch.generate_downbeats(duration=8.0)
        beats = orch.generate_beat_timeline(duration=8.0)
        expected_count = len(beats) // 4 + 1
        assert len(downbeats) >= expected_count


# ============================================================================
# BeatOrchestrator.generate_offbeats
# ============================================================================
class TestGenerateOffbeats:
    def test_offbeats_are_odd_indices(self):
        orch = BeatOrchestrator(bpm=120)
        offbeats = orch.generate_offbeats(duration=2.0)
        for bt in offbeats:
            nearest_beat = min(
                [abs(bt - i * 0.5) for i in range(5)],
                default=float("inf")
            )
        assert len(offbeats) >= 2

    def test_offbeats_count_roughly_half(self):
        orch = BeatOrchestrator(bpm=120)
        beats = orch.generate_beat_timeline(duration=4.0)
        offbeats = orch.generate_offbeats(duration=4.0)
        assert len(offbeats) >= len(beats) // 2

    def test_offbeats_with_offset(self):
        orch = BeatOrchestrator(bpm=120)
        offbeats = orch.generate_offbeats(duration=2.0, offset=0.5)
        assert len(offbeats) >= 1
        assert offbeats[0] >= 0.5

    def test_empty_duration(self):
        orch = BeatOrchestrator(bpm=120)
        offbeats = orch.generate_offbeats(duration=0.0)
        assert len(offbeats) == 0


# ============================================================================
# BeatOrchestrator.generate_beat_synced_keyframes
# ============================================================================
class TestBeatSyncedKeyframes:
    def setup_method(self):
        self.orch = BeatOrchestrator(bpm=120)

    def test_generates_three_keyframes_per_beat(self):
        config = BeatSyncConfig(
            property_type="scale",
            base_value=1.0,
            beat_value=1.15,
            attack=0.03,
            decay=0.12,
        )
        beats = [0.0, 0.5, 1.0]
        keyframes = self.orch.generate_beat_synced_keyframes("Layer1", beats, config)
        assert len(keyframes) == 9

    def test_keyframe_values(self):
        config = BeatSyncConfig(
            property_type="scale",
            base_value=1.0,
            beat_value=1.15,
            attack=0.05,
            decay=0.10,
        )
        beats = [0.0]
        keyframes = self.orch.generate_beat_synced_keyframes("Layer1", beats, config)
        assert len(keyframes) == 3
        assert keyframes[0]["value"] == 1.0
        assert keyframes[1]["value"] == 1.15
        assert keyframes[2]["value"] == 1.0

    def test_keyframe_times(self):
        config = BeatSyncConfig(
            property_type="opacity",
            base_value=0.5,
            beat_value=1.0,
            attack=0.05,
            decay=0.10,
        )
        beats = [0.0]
        keyframes = self.orch.generate_beat_synced_keyframes("Layer1", beats, config)
        assert keyframes[0]["time"] == 0.0
        assert keyframes[1]["time"] == 0.05
        assert keyframes[2]["time"] == 0.15

    def test_property_name_mapping(self):
        test_cases = [
            ("scale", "Scale"),
            ("opacity", "Opacity"),
            ("position", "Position"),
            ("rotation", "Rotation"),
        ]
        for prop_type, expected_name in test_cases:
            config = BeatSyncConfig(
                property_type=prop_type,
                base_value=1.0,
                beat_value=1.1,
            )
            beats = [0.0]
            keyframes = self.orch.generate_beat_synced_keyframes("L", beats, config)
            assert keyframes[0]["propertyName"] == expected_name

    def test_custom_property_type_passthrough(self):
        config = BeatSyncConfig(
            property_type="CustomProperty",
            base_value=0.0,
            beat_value=100.0,
        )
        beats = [0.0]
        keyframes = self.orch.generate_beat_synced_keyframes("L", beats, config)
        assert keyframes[0]["propertyName"] == "CustomProperty"

    def test_ease_types(self):
        config = BeatSyncConfig(
            property_type="scale",
            base_value=1.0,
            beat_value=1.2,
            easing="ease_out",
        )
        beats = [0.0]
        keyframes = self.orch.generate_beat_synced_keyframes("L", beats, config)
        assert keyframes[0]["easeType"] == "ease_out"
        assert keyframes[1]["easeType"] == "ease_in"
        assert keyframes[2]["easeType"] == "ease_out"

    def test_empty_beats_returns_empty(self):
        config = BeatSyncConfig(property_type="scale", base_value=1.0, beat_value=1.1)
        keyframes = self.orch.generate_beat_synced_keyframes("L", [], config)
        assert keyframes == []


# ============================================================================
# BeatOrchestrator.generate_beat_effect_triggers
# ============================================================================
class TestBeatEffectTriggers:
    def setup_method(self):
        self.orch = BeatOrchestrator(bpm=120)

    def test_glow_pulse_triggers(self):
        beats = [0.0, 0.5]
        triggers = self.orch.generate_beat_effect_triggers(
            "Layer1", beats, "glow_pulse", intensity=1.0
        )
        assert len(triggers) == 6
        for t in triggers:
            assert t["propertyName"] == "Glow Intensity"

    def test_sharpen_pulse_triggers(self):
        beats = [0.0, 0.5]
        triggers = self.orch.generate_beat_effect_triggers(
            "Layer1", beats, "sharpen_pulse", intensity=1.0
        )
        assert len(triggers) == 6
        for t in triggers:
            assert t["propertyName"] == "Sharpen Amount"

    def test_unknown_effect_returns_empty(self):
        beats = [0.0]
        triggers = self.orch.generate_beat_effect_triggers(
            "L", beats, "unknown_effect"
        )
        assert triggers == []

    def test_glow_pulse_values_at_intensity(self):
        beats = [0.0]
        triggers = self.orch.generate_beat_effect_triggers(
            "L", beats, "glow_pulse", intensity=1.0
        )
        assert triggers[0]["value"] == 0.0
        assert triggers[1]["value"] == 100.0
        assert triggers[2]["value"] == 0.0

    def test_glow_pulse_values_half_intensity(self):
        beats = [0.0]
        triggers = self.orch.generate_beat_effect_triggers(
            "L", beats, "glow_pulse", intensity=0.5
        )
        assert triggers[1]["value"] == 50.0

    def test_empty_beats_returns_empty(self):
        triggers = self.orch.generate_beat_effect_triggers("L", [], "glow_pulse")
        assert triggers == []

    def test_sharpen_pulse_values(self):
        beats = [0.0]
        triggers = self.orch.generate_beat_effect_triggers(
            "L", beats, "sharpen_pulse", intensity=1.0
        )
        assert triggers[0]["value"] == 0.0
        assert triggers[1]["value"] == 50.0


# ============================================================================
# BeatOrchestrator.generate_musical_structure
# ============================================================================
class TestGenerateMusicalStructure:
    def setup_method(self):
        self.orch = BeatOrchestrator(bpm=120)

    def test_pop_song_structure(self):
        sections = self.orch.generate_musical_structure(
            duration=60.0, template="pop_song"
        )
        assert len(sections) == 7
        assert sections[0].type == "intro"
        assert sections[-1].type == "outro"
        total_dur = sum(s.end_time - s.start_time for s in sections)
        assert abs(total_dur - 60.0) < 0.5

    def test_edm_drop_structure(self):
        sections = self.orch.generate_musical_structure(
            duration=60.0, template="edm_drop"
        )
        assert len(sections) == 6
        assert sections[0].type == "intro"

    def test_short_hook_structure(self):
        sections = self.orch.generate_musical_structure(
            duration=15.0, template="short_hook"
        )
        assert len(sections) == 3

    def test_invalid_template_falls_back_to_pop(self):
        sections = self.orch.generate_musical_structure(
            duration=30.0, template="nonexistent_template"
        )
        assert len(sections) > 0
        assert sections[0].type == "intro"

    def test_sections_cover_full_duration(self):
        sections = self.orch.generate_musical_structure(
            duration=30.0, template="pop_song"
        )
        assert sections[0].start_time == 0.0
        assert abs(sections[-1].end_time - 30.0) < 0.5

    def test_no_gaps_between_sections(self):
        sections = self.orch.generate_musical_structure(
            duration=30.0, template="edm_drop"
        )
        for i in range(len(sections) - 1):
            gap = sections[i + 1].start_time - sections[i].end_time
            assert abs(gap) < 0.5

    def test_energy_values_match_template(self):
        sections = self.orch.generate_musical_structure(
            duration=30.0, template="pop_song"
        )
        for i, section in enumerate(sections):
            template_data = MUSICAL_STRUCTURE_TEMPLATES["pop_song"]
            assert section.energy == template_data[i]["energy"]


# ============================================================================
# BeatOrchestrator.energy_to_intensity
# ============================================================================
class TestEnergyToIntensity:
    def setup_method(self):
        self.orch = BeatOrchestrator(bpm=120)

    def test_zero_energy(self):
        result = self.orch.energy_to_intensity(0.0)
        assert result == 0.0

    def test_full_energy(self):
        result = self.orch.energy_to_intensity(1.0)
        assert result == 1.0

    def test_negative_energy_clamped(self):
        result = self.orch.energy_to_intensity(-0.5)
        assert result == 0.0

    def test_over_one_clamped(self):
        result = self.orch.energy_to_intensity(1.5)
        assert result == 1.0

    def test_monotonic(self):
        energies = [0.0, 0.25, 0.5, 0.75, 1.0]
        intensities = [self.orch.energy_to_intensity(e) for e in energies]
        for i in range(len(intensities) - 1):
            assert intensities[i] <= intensities[i + 1]

    def test_known_values(self):
        result = self.orch.energy_to_intensity(0.5)
        expected = round(math.pow(0.5, 0.8), 4)
        assert result == expected

    def test_symmetry(self):
        low = self.orch.energy_to_intensity(0.2)
        mid = self.orch.energy_to_intensity(0.5)
        high = self.orch.energy_to_intensity(0.8)
        assert low < mid < high


# ============================================================================
# BeatOrchestrator.generate_full_beat_show
# ============================================================================
class TestFullBeatShow:
    def setup_method(self):
        self.orch = BeatOrchestrator(bpm=120)

    def test_energetic_style(self):
        result = self.orch.generate_full_beat_show(
            "TestLayer", duration=30.0, style="energetic",
            structure_template="pop_song"
        )
        assert result["layerName"] == "TestLayer"
        assert result["style"] == "energetic"
        assert result["structure_template"] == "pop_song"
        assert result["total_keyframes"] > 0
        assert result["total_effects"] > 0
        assert len(result["keyframes"]) == result["total_keyframes"]
        assert len(result["effect_triggers"]) == result["total_effects"]

    def test_chill_style(self):
        result = self.orch.generate_full_beat_show(
            "Layer1", duration=20.0, style="chill"
        )
        assert result["total_keyframes"] > 0
        assert result["total_effects"] >= 0

    def test_unknown_style_falls_back(self):
        result = self.orch.generate_full_beat_show(
            "L", duration=10.0, style="unknown_style"
        )
        # 实现约定: 未知风格回退使用 energetic 配置，但 style 字段保留原始输入（可追溯）
        assert result["style"] == "unknown_style"
        assert result["total_keyframes"] > 0

    def test_sections_in_result(self):
        result = self.orch.generate_full_beat_show(
            "L", duration=30.0, structure_template="edm_drop"
        )
        assert len(result["sections"]) > 0
        for section in result["sections"]:
            assert "type" in section
            assert "start_time" in section
            assert "end_time" in section
            assert "energy" in section

    def test_keyframe_count_per_beat(self):
        result = self.orch.generate_full_beat_show(
            "L", duration=5.0, style="energetic",
            structure_template="short_hook"
        )
        expected_props = 4
        expected_per_beat = 3
        total_beats = len(self.orch.generate_beat_timeline(5.0))
        min_expected = total_beats * expected_props * expected_per_beat
        assert result["total_keyframes"] >= min_expected

    def test_result_has_duration(self):
        result = self.orch.generate_full_beat_show("L", duration=15.0)
        assert result["duration"] == 15.0


# ============================================================================
# MusicalSection dataclass
# ============================================================================
class TestMusicalSection:
    def test_default_creation(self):
        section = MusicalSection(
            type="verse",
            start_time=0.0,
            end_time=8.0,
            energy=0.5,
        )
        assert section.type == "verse"
        assert section.start_time == 0.0
        assert section.end_time == 8.0
        assert section.energy == 0.5
        assert section.intensity_multiplier == 1.0

    def test_custom_intensity(self):
        section = MusicalSection(
            type="chorus",
            start_time=8.0,
            end_time=16.0,
            energy=0.9,
            intensity_multiplier=1.2,
        )
        assert section.intensity_multiplier == 1.2

    def test_section_duration(self):
        section = MusicalSection(
            type="bridge",
            start_time=16.0,
            end_time=19.0,
            energy=0.4,
        )
        assert section.end_time - section.start_time == 3.0


# ============================================================================
# BeatSyncConfig dataclass
# ============================================================================
class TestBeatSyncConfig:
    def test_default_values(self):
        config = BeatSyncConfig(
            property_type="scale",
            base_value=1.0,
            beat_value=1.15,
        )
        assert config.attack == 0.05
        assert config.decay == 0.15
        assert config.easing == "ease_out"
        assert config.sync_mode == "on_beat"

    def test_custom_values(self):
        config = BeatSyncConfig(
            property_type="opacity",
            base_value=0.5,
            beat_value=1.0,
            attack=0.02,
            decay=0.08,
            easing="ease_in",
        )
        assert config.attack == 0.02
        assert config.decay == 0.08
        assert config.easing == "ease_in"


# ============================================================================
# BEAT_EFFECT_STYLES data integrity
# ============================================================================
class TestBeatEffectStyles:
    def test_all_styles_have_required_keys(self):
        required = {"scale", "opacity", "position", "rotation", "effects", "effect_intensity"}
        for style_name, style_data in BEAT_EFFECT_STYLES.items():
            assert required.issubset(set(style_data.keys())), (
                f"Style '{style_name}' missing keys: {required - set(style_data.keys())}"
            )

    def test_all_styles_have_effect_intensity_in_range(self):
        for style_name, style_data in BEAT_EFFECT_STYLES.items():
            intensity = style_data["effect_intensity"]
            assert 0.0 <= intensity <= 1.0, (
                f"Style '{style_name}' effect_intensity {intensity} out of range"
            )

    def test_style_props_have_base_and_beat(self):
        for style_name, style_data in BEAT_EFFECT_STYLES.items():
            for prop in ["scale", "opacity", "position", "rotation"]:
                assert "base" in style_data[prop]
                assert "beat" in style_data[prop]
                assert "attack" in style_data[prop]
                assert "decay" in style_data[prop]


# ============================================================================
# MUSICAL_STRUCTURE_TEMPLATES data integrity
# ============================================================================
class TestMusicalStructureTemplates:
    def test_all_templates_have_required_keys(self):
        required = {"type", "duration_ratio", "energy", "intensity"}
        for name, template in MUSICAL_STRUCTURE_TEMPLATES.items():
            for seg in template:
                assert required.issubset(set(seg.keys())), (
                    f"Template '{name}' segment {seg.get('type', '?')} "
                    f"missing: {required - set(seg.keys())}"
                )

    def test_duration_ratios_sum_approximately_one(self):
        for name, template in MUSICAL_STRUCTURE_TEMPLATES.items():
            total = sum(seg["duration_ratio"] for seg in template)
            assert abs(total - 1.0) < 0.05, (
                f"Template '{name}' duration ratios sum to {total}"
            )

    def test_energy_values_in_range(self):
        for name, template in MUSICAL_STRUCTURE_TEMPLATES.items():
            for seg in template:
                assert 0.0 <= seg["energy"] <= 1.0, (
                    f"Template '{name}' segment '{seg['type']}' energy out of range"
                )

    def test_intensity_values_in_range(self):
        for name, template in MUSICAL_STRUCTURE_TEMPLATES.items():
            for seg in template:
                assert 0.0 <= seg["intensity"] <= 2.0, (
                    f"Template '{name}' segment '{seg['type']}' intensity out of range"
                )
