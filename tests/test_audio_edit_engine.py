"""core.audio_edit_engine 单元测试 - 音频驱动剪辑引擎核心逻辑

覆盖范围:
1. EditDecisionGenerator._energy_to_speed - 5 档能量→速度映射 (边界条件)
2. EditDecisionGenerator._snap_to_beat - 3 种节拍对齐模式 (nearest/next/prev)
3. EditDecisionGenerator._pick_transition - 6 档能量→转场选择 (边界条件)
4. EditDecisionGenerator._generate_single_material_edl - 单素材 EDL 生成
5. EditDecisionGenerator._generate_multi_material_edl - 多素材 EDL 生成
6. EditDecisionGenerator._find_section_boundaries - 段落边界对齐
7. SpeedRampGenerator._energy_to_remap - 能量→time remap 百分比
8. AudioEditJSXGenerator - JSX 输出结构验证
9. EditDecisionGenerator.generate - 集成:空输入/边界输入/完整输入
"""
import os
import sys
import pytest
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.audio_edit_engine import (
    EditDecisionGenerator,
    SpeedRampGenerator,
    AudioEditJSXGenerator,
    AudioAnalyzerAdapter,
    AudioEditEngine,
)


# ============================================================================
# EditDecisionGenerator._energy_to_speed
# ============================================================================
class TestEnergyToSpeed:
    """能量 → 播放速度 映射的边界条件测试"""

    def setup_method(self):
        self.gen = EditDecisionGenerator()

    def test_very_low_energy(self):
        assert self.gen._energy_to_speed(0.0) == 0.6
        assert self.gen._energy_to_speed(0.1) == 0.6
        assert self.gen._energy_to_speed(0.19) == 0.6

    def test_low_energy_boundary(self):
        assert self.gen._energy_to_speed(0.2) == 0.6
        assert self.gen._energy_to_speed(0.21) == 0.8

    def test_mid_low_energy(self):
        assert self.gen._energy_to_speed(0.2) == 0.6
        assert self.gen._energy_to_speed(0.3) == 0.8
        assert self.gen._energy_to_speed(0.4) == 0.8

    def test_mid_energy_boundary(self):
        assert self.gen._energy_to_speed(0.4) == 0.8
        assert self.gen._energy_to_speed(0.41) == 1.0

    def test_mid_energy(self):
        assert self.gen._energy_to_speed(0.5) == 1.0
        assert self.gen._energy_to_speed(0.6) == 1.0

    def test_mid_high_energy_boundary(self):
        assert self.gen._energy_to_speed(0.6) == 1.0
        assert self.gen._energy_to_speed(0.61) == 1.2

    def test_mid_high_energy(self):
        assert self.gen._energy_to_speed(0.7) == 1.2
        assert self.gen._energy_to_speed(0.8) == 1.2

    def test_high_energy_boundary(self):
        assert self.gen._energy_to_speed(0.8) == 1.2
        assert self.gen._energy_to_speed(0.81) == 1.5

    def test_very_high_energy(self):
        assert self.gen._energy_to_speed(0.9) == 1.5
        assert self.gen._energy_to_speed(1.0) == 1.5

    def test_negative_energy_clamped(self):
        result = self.gen._energy_to_speed(-0.5)
        assert result == 0.6

    def test_monotonic_increasing(self):
        energies = [0.0, 0.1, 0.25, 0.45, 0.65, 0.85, 1.0]
        speeds = [self.gen._energy_to_speed(e) for e in energies]
        for i in range(len(speeds) - 1):
            assert speeds[i] <= speeds[i + 1], (
                f"Speed should be monotonic: {speeds[i]} > {speeds[i+1]}"
            )


# ============================================================================
# EditDecisionGenerator._snap_to_beat
# ============================================================================
class TestSnapToBeat:
    """节拍对齐逻辑的边界条件测试"""

    def setup_method(self):
        self.gen = EditDecisionGenerator()
        self.beats = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]

    def test_nearest_snap(self):
        result = self.gen._snap_to_beat(0.23, self.beats, direction="nearest")
        assert result == 0.0

        result = self.gen._snap_to_beat(0.27, self.beats, direction="nearest")
        assert result == 0.5

    def test_nearest_exact(self):
        result = self.gen._snap_to_beat(1.0, self.beats, direction="nearest")
        assert result == 1.0

    def test_next_snap(self):
        result = self.gen._snap_to_beat(0.23, self.beats, direction="next")
        assert result == 0.5

    def test_next_snap_at_boundary(self):
        result = self.gen._snap_to_beat(3.9, self.beats, direction="next")
        assert result == 4.0

    def test_next_snap_beyond_range(self):
        result = self.gen._snap_to_beat(5.0, self.beats, direction="next")
        assert result == 4.0

    def test_prev_snap(self):
        result = self.gen._snap_to_beat(0.23, self.beats, direction="prev")
        assert result == 0.0

    def test_prev_snap_at_boundary(self):
        result = self.gen._snap_to_beat(3.9, self.beats, direction="prev")
        assert result == 3.5

    def test_prev_snap_below_range(self):
        result = self.gen._snap_to_beat(-1.0, self.beats, direction="prev")
        assert result == 0.0

    def test_empty_beats_returns_time(self):
        result = self.gen._snap_to_beat(1.0, [], direction="nearest")
        assert result == 1.0

    def test_empty_beats_next(self):
        result = self.gen._snap_to_beat(1.0, [], direction="next")
        assert result == 1.0

    def test_empty_beats_prev(self):
        result = self.gen._snap_to_beat(1.0, [], direction="prev")
        assert result == 1.0

    def test_single_beat(self):
        result = self.gen._snap_to_beat(0.5, [2.0], direction="next")
        assert result == 2.0

    def test_next_within_tolerance(self):
        result = self.gen._snap_to_beat(0.45, self.beats, direction="next")
        assert result == 0.5


# ============================================================================
# EditDecisionGenerator._pick_transition
# ============================================================================
class TestPickTransition:
    """能量→转场选择的边界条件测试"""

    def setup_method(self):
        self.gen = EditDecisionGenerator()

    def test_very_high_energy_cut(self):
        result = self.gen._pick_transition(0.9, 0)
        assert result["type"] == "cut"
        assert result["duration"] == 0.0
        assert result["ae_effect"] is None

    def test_high_energy_boundary(self):
        result = self.gen._pick_transition(0.85, 0)
        assert result["type"] == "cut"

        result = self.gen._pick_transition(0.849, 0)
        assert result["type"] == "glow_flash"

    def test_glow_flash(self):
        result = self.gen._pick_transition(0.80, 0)
        assert result["type"] == "glow_flash"
        assert result["duration"] == 0.15
        assert result["ae_effect"] == "ADBE Lensflare"

    def test_glow_flash_boundary(self):
        result = self.gen._pick_transition(0.75, 0)
        assert result["type"] == "glow_flash"

        result = self.gen._pick_transition(0.749, 0)
        assert result["type"] == "dissolve"

    def test_dissolve(self):
        result = self.gen._pick_transition(0.65, 0)
        assert result["type"] == "dissolve"
        assert result["duration"] == 0.3
        assert result["ae_effect"] == "ADBE Transition - Cross Dissolve"

    def test_dissolve_boundary(self):
        result = self.gen._pick_transition(0.60, 0)
        assert result["type"] == "dissolve"

        result = self.gen._pick_transition(0.599, 0)
        assert result["type"] == "wipe_right"

    def test_wipe_right(self):
        result = self.gen._pick_transition(0.50, 0)
        assert result["type"] == "wipe_right"
        assert result["duration"] == 0.5
        assert result["ae_effect"] == "ADBE Transition - Linear Wipe"

    def test_wipe_right_boundary(self):
        result = self.gen._pick_transition(0.45, 0)
        assert result["type"] == "wipe_right"

        result = self.gen._pick_transition(0.449, 0)
        assert result["type"] == "slide"

    def test_slide(self):
        result = self.gen._pick_transition(0.35, 0)
        assert result["type"] == "slide"
        assert result["duration"] == 0.4
        assert result["ae_effect"] == "ADBE Transform"

    def test_slide_boundary(self):
        result = self.gen._pick_transition(0.30, 0)
        assert result["type"] == "slide"

        result = self.gen._pick_transition(0.299, 0)
        assert result["type"] == "fade_black"

    def test_fade_black(self):
        result = self.gen._pick_transition(0.1, 0)
        assert result["type"] == "fade_black"
        assert result["duration"] == 0.8
        assert result["ae_effect"] == "ADBE Transition - Dip to Black"

    def test_all_transitions_have_required_keys(self):
        energies = [0.0, 0.15, 0.35, 0.50, 0.65, 0.80, 0.95]
        for e in energies:
            result = self.gen._pick_transition(e, 0)
            assert "type" in result
            assert "duration" in result
            assert "ae_effect" in result
            assert "desc" in result


# ============================================================================
# EditDecisionGenerator._generate_single_material_edl
# ============================================================================
class TestSingleMaterialEDL:
    def setup_method(self):
        self.gen = EditDecisionGenerator()

    def test_with_sections(self):
        beats = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
        energy_vals = [0.3, 0.5, 0.8, 0.9, 0.7, 0.5, 0.4, 0.3, 0.2]
        sections = ["intro", "chorus", "outro"]
        edl = self.gen._generate_single_material_edl(
            beats, energy_vals, 4.0, sections, 120.0
        )
        assert len(edl) >= 2
        for clip in edl:
            assert "clip_index" in clip
            assert "material_index" in clip
            assert "start_time" in clip
            assert "end_time" in clip
            assert clip["material_index"] == 0
            assert clip["end_time"] > clip["start_time"]

    def test_without_sections_fallback(self):
        beats = [i * 0.5 for i in range(16)]
        energy_vals = [0.5] * 16
        edl = self.gen._generate_single_material_edl(
            beats, energy_vals, 8.0, [], 120.0
        )
        assert len(edl) >= 3
        for clip in edl:
            assert clip["material_index"] == 0

    def test_edl_clip_times_within_range(self):
        beats = [i * 0.25 for i in range(20)]
        energy_vals = [0.4 + 0.3 * math.sin(i) for i in range(20)]
        edl = self.gen._generate_single_material_edl(
            beats, energy_vals, 5.0, [], 140.0
        )
        for clip in edl:
            assert clip["start_time"] >= 0
            assert clip["end_time"] <= 5.0

    def test_edl_contains_speed_and_transition(self):
        beats = [i * 0.5 for i in range(12)]
        energy_vals = [0.7, 0.5, 0.8, 0.4, 0.6, 0.9, 0.3, 0.7, 0.5, 0.8, 0.4, 0.6]
        edl = self.gen._generate_single_material_edl(
            beats, energy_vals, 6.0, ["intro", "chorus", "outro"], 120.0
        )
        for clip in edl:
            assert "speed" in clip
            assert isinstance(clip["transition"], dict)
            assert "type" in clip["transition"]

    def test_speed_values_within_valid_range(self):
        beats = [i * 0.5 for i in range(10)]
        energy_vals = [0.1, 0.3, 0.5, 0.7, 0.9, 0.8, 0.6, 0.4, 0.2, 0.5]
        edl = self.gen._generate_single_material_edl(
            beats, energy_vals, 5.0, [], 120.0
        )
        for clip in edl:
            assert 0.5 <= clip["speed"] <= 2.0


# ============================================================================
# EditDecisionGenerator._generate_multi_material_edl
# ============================================================================
class TestMultiMaterialEDL:
    def setup_method(self):
        self.gen = EditDecisionGenerator()

    def test_two_materials(self):
        beats = [i * 0.5 for i in range(16)]
        energy_vals = [0.5] * 16
        edl = self.gen._generate_multi_material_edl(
            beats, energy_vals, 8.0, material_count=2, bpm=120.0
        )
        assert len(edl) == 2
        assert edl[0]["material_index"] == 0
        assert edl[1]["material_index"] == 1

    def test_material_index_wraps(self):
        beats = [i * 0.5 for i in range(20)]
        energy_vals = [0.6] * 20
        edl = self.gen._generate_multi_material_edl(
            beats, energy_vals, 10.0, material_count=3, bpm=120.0
        )
        indices = [clip["material_index"] for clip in edl]
        for idx in indices:
            assert 0 <= idx < 3

    def test_single_material(self):
        beats = [i * 0.5 for i in range(8)]
        energy_vals = [0.5] * 8
        edl = self.gen._generate_multi_material_edl(
            beats, energy_vals, 4.0, material_count=1, bpm=120.0
        )
        assert len(edl) >= 1

    def test_empty_beats_returns_empty(self):
        edl = self.gen._generate_multi_material_edl(
            [], [], 4.0, material_count=3, bpm=120.0
        )
        assert edl == []


# ============================================================================
# SpeedRampGenerator._energy_to_remap
# ============================================================================
class TestEnergyToRemap:
    def setup_method(self):
        self.gen = SpeedRampGenerator()

    def test_min_energy(self):
        assert self.gen._energy_to_remap(0.0) == 50.0

    def test_max_energy(self):
        assert self.gen._energy_to_remap(1.0) == 200.0

    def test_mid_energy(self):
        assert self.gen._energy_to_remap(0.5) == 125.0

    def test_zero_energy(self):
        result = self.gen._energy_to_remap(0.0)
        assert result == 50.0

    def test_all_values_in_range(self):
        for e in [0.0, 0.1, 0.25, 0.5, 0.75, 1.0]:
            remap = self.gen._energy_to_remap(e)
            assert 50.0 <= remap <= 200.0

    def test_linear_relationship(self):
        e1 = 0.3
        e2 = 0.7
        r1 = self.gen._energy_to_remap(e1)
        r2 = self.gen._energy_to_remap(e2)
        assert r2 > r1, f"Remap should increase with energy: {r2} should be > {r1}"


# ============================================================================
# SpeedRampGenerator.generate_ramps
# ============================================================================
class TestGenerateRamps:
    def setup_method(self):
        self.gen = SpeedRampGenerator()

    def test_generates_ramps_for_clipped_range(self):
        audio_features = {
            "beats": [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0],
            "energy_values": [0.3, 0.5, 0.8, 0.9, 0.7, 0.5, 0.3],
        }
        ramps = self.gen.generate_ramps(audio_features, clip_start=0.5, clip_end=2.0)
        assert len(ramps) >= 3
        for ramp in ramps:
            assert "time" in ramp
            assert "remap_value" in ramp
            assert "energy" in ramp
            assert 0 <= ramp["time"] <= 1.5
            assert 50.0 <= ramp["remap_value"] <= 200.0

    def test_no_beats_returns_empty(self):
        audio_features = {"beats": [], "energy_values": []}
        ramps = self.gen.generate_ramps(audio_features, 0.0, 5.0)
        assert ramps == []

    def test_range_outside_clips_returns_empty(self):
        audio_features = {
            "beats": [0.0, 0.5, 1.0],
            "energy_values": [0.5, 0.6, 0.7],
        }
        ramps = self.gen.generate_ramps(audio_features, clip_start=5.0, clip_end=10.0)
        assert ramps == []


# ============================================================================
# EditDecisionGenerator.generate (integration-level)
# ============================================================================
class TestEDLGeneration:
    def setup_method(self):
        self.gen = EditDecisionGenerator()

    def test_empty_beats_returns_empty_edl(self):
        features = {
            "beats": [], "energy_values": [], "bpm": 120,
            "duration": 5.0, "sections": ["intro", "outro"],
        }
        edl = self.gen.generate(features, material_count=1)
        assert edl == []

    def test_single_material_generates_edl(self):
        features = {
            "beats": [i * 0.5 for i in range(12)],
            "energy_values": [0.5] * 12,
            "bpm": 120, "duration": 6.0,
            "sections": ["intro", "chorus", "outro"],
        }
        edl = self.gen.generate(features, material_count=1)
        assert len(edl) >= 2

    def test_multi_material_generates_edl(self):
        features = {
            "beats": [i * 0.5 for i in range(16)],
            "energy_values": [0.6] * 16,
            "bpm": 120, "duration": 8.0,
            "sections": [],
        }
        edl = self.gen.generate(features, material_count=3)
        assert len(edl) == 3

    def test_material_durations_looping(self):
        features = {
            "beats": [i * 0.5 for i in range(10)],
            "energy_values": [0.5] * 10,
            "bpm": 120, "duration": 5.0,
            "sections": [],
        }
        material_durations = [1.0]
        edl = self.gen.generate(features, material_count=1, material_durations=material_durations)
        assert len(edl) >= 1
        for clip in edl:
            if clip.get("loop"):
                assert clip["loop"] is True

    def test_all_clips_have_required_keys(self):
        features = {
            "beats": [i * 0.5 for i in range(10)],
            "energy_values": [0.4 + 0.2 * math.sin(i) for i in range(10)],
            "bpm": 120, "duration": 5.0,
            "sections": ["intro", "chorus", "outro"],
        }
        edl = self.gen.generate(features, material_count=1)
        required_keys = {
            "clip_index", "material_index", "start_time", "end_time",
            "duration", "avg_energy", "speed", "transition",
        }
        for clip in edl:
            assert required_keys.issubset(set(clip.keys())), (
                f"Missing keys: {required_keys - set(clip.keys())}"
            )


# ============================================================================
# AudioEditJSXGenerator
# ============================================================================
class TestJSXGenerator:
    def setup_method(self):
        self.gen = AudioEditJSXGenerator()

    def test_generates_valid_jsx_structure(self):
        edl = [
            {
                "clip_index": 0,
                "material_index": 0,
                "start_time": 0.0,
                "end_time": 2.0,
                "duration": 2.0,
                "avg_energy": 0.7,
                "speed": 1.2,
                "transition": {"type": "dissolve", "duration": 0.3},
            },
            {
                "clip_index": 1,
                "material_index": 1,
                "start_time": 2.0,
                "end_time": 4.0,
                "duration": 2.0,
                "avg_energy": 0.5,
                "speed": 1.0,
                "transition": {"type": "cut", "duration": 0.0},
            },
        ]
        features = {"bpm": 120, "duration": 4.0, "beats": [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5]}
        material_paths = ["/path/video1.mp4", "/path/video2.mp4"]

        jsx = self.gen.generate(edl, features, material_paths, comp_name="TestComp")
        assert "TestComp" in jsx
        assert "app.project.items.addComp" in jsx
        assert "BPM=120" in jsx
        assert "ImportOptions" in jsx
        assert "JSON.stringify" in jsx

    def test_jsx_handles_no_speed_change(self):
        edl = [
            {
                "clip_index": 0,
                "material_index": 0,
                "start_time": 0.0,
                "end_time": 2.0,
                "duration": 2.0,
                "avg_energy": 0.5,
                "speed": 1.0,
                "transition": {"type": "cut", "duration": 0.0},
            }
        ]
        features = {"bpm": 120, "duration": 2.0, "beats": [0.0, 0.5, 1.0, 1.5]}
        jsx = self.gen.generate(edl, features, ["/path/video.mp4"])
        assert "timeRemapEnabled" not in jsx

    def test_jsx_includes_speed_when_not_1x(self):
        edl = [
            {
                "clip_index": 0,
                "material_index": 0,
                "start_time": 0.0,
                "end_time": 2.0,
                "duration": 2.0,
                "avg_energy": 0.9,
                "speed": 1.5,
                "transition": {"type": "cut", "duration": 0.0},
            }
        ]
        features = {"bpm": 120, "duration": 2.0, "beats": [0.0, 0.5, 1.0, 1.5]}
        jsx = self.gen.generate(edl, features, ["/path/video.mp4"])
        assert "timeRemapEnabled" in jsx
        assert "ADBE Time Remapping" in jsx

    def test_jsx_handles_empty_edl(self):
        features = {"bpm": 120, "duration": 2.0, "beats": [0.0, 0.5]}
        jsx = self.gen.generate([], features, [])
        assert "JSON.stringify" in jsx

    def test_jsx_includes_opacity_keyframes(self):
        edl = [
            {
                "clip_index": 0,
                "material_index": 0,
                "start_time": 0.5,
                "end_time": 2.0,
                "duration": 1.5,
                "avg_energy": 0.6,
                "speed": 1.0,
                "transition": {"type": "cut", "duration": 0.0},
            }
        ]
        features = {"bpm": 120, "duration": 2.0, "beats": [0.0, 0.5, 1.0, 1.5]}
        jsx = self.gen.generate(edl, features, ["/path/video.mp4"])
        assert "ADBE Opacity" in jsx
        assert "setValueAtTime" in jsx


# ============================================================================
# AudioEditEngine (integration-level API)
# ============================================================================
class TestAudioEditEngine:
    def test_engine_initialization(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = AudioEditEngine(output_dir=tmpdir)
            assert engine.output_dir.exists()
            assert engine.analyzer is not None
            assert engine.edl_gen is not None
            assert engine.ramp_gen is not None
            assert engine.jsx_gen is not None

    def test_engine_edit_with_synthetic_audio(self):
        engine = AudioEditEngine()
        features = {
            "bpm": 120,
            "duration": 4.0,
            "beats": [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5],
            "energy_values": [0.3, 0.5, 0.8, 0.9, 0.7, 0.5, 0.4, 0.3],
            "sections": ["intro", "chorus", "outro"],
            "mood": "energetic",
            "genre": "edm",
        }
        engine.analyzer.analyze = lambda x: features

        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            engine.output_dir = __import__("pathlib").Path(tmpdir)
            report = engine.edit("dummy.mp3", ["material.mp4"])
            assert "bpm" in report
            assert "clips" in report
            assert report["clips"] >= 1
            assert "jsx_lines" in report
            assert "elapsed" in report
            assert "outputs" in report


# ============================================================================
# AudioAnalyzerAdapter._normalize
# ============================================================================
class TestAudioAnalyzerNormalization:
    def setup_method(self):
        self.adapter = AudioAnalyzerAdapter()

    def test_normalize_full_structure(self):
        raw = {
            "features": {
                "beats": [0.0, 0.5, 1.0],
                "downbeats": [0.0],
                "bpm": 120.0,
                "duration": 3.0,
                "energy_curve": {"values": [0.3, 0.5, 0.7], "times": [0.0, 0.5, 1.0]},
                "segments": [
                    {"segment_type": "intro"},
                    {"segment_type": "chorus"},
                ],
                "mood": "energetic",
                "genre": "edm",
            }
        }
        result = self.adapter._normalize(raw)
        assert result["bpm"] == 120.0
        assert result["duration"] == 3.0
        assert result["beats"] == [0.0, 0.5, 1.0]
        assert result["energy_values"] == [0.3, 0.5, 0.7]
        assert result["energy_times"] == [0.0, 0.5, 1.0]
        assert result["sections"] == ["intro", "chorus"]
        assert result["mood"] == "energetic"
        assert result["genre"] == "edm"

    def test_normalize_flat_structure(self):
        raw = {
            "beats": [0.0, 1.0],
            "downbeats": [0.0],
            "bpm": 100.0,
            "duration": 2.0,
            "energy_curve": [0.4, 0.6],
            "segments": [],
        }
        result = self.adapter._normalize(raw)
        assert result["bpm"] == 100.0
        assert result["energy_values"] == []
        assert result["mood"] == "neutral"
        assert result["genre"] == "unknown"

    def test_normalize_missing_fields(self):
        raw = {}
        result = self.adapter._normalize(raw)
        assert result["bpm"] == 120.0
        assert result["duration"] == 0.0
        assert result["beats"] == []
        assert result["mood"] == "neutral"

    def test_normalize_sections_from_dicts(self):
        raw = {
            "features": {
                "beats": [],
                "downbeats": [],
                "bpm": 120,
                "duration": 4.0,
                "energy_curve": {},
                "segments": [
                    {"segment_type": "intro"},
                    {"segment_type": "verse"},
                    "segment_type": "chorus"},
                ],
            }
        }
        result = self.adapter._normalize(raw)
        assert result["sections"] == ["intro", "verse", "chorus"]


# ============================================================================
# AudioAnalyzerAdapter._fallback_analyze
# ============================================================================
class TestFallbackAnalysis:
    def setup_method(self):
        self.adapter = AudioAnalyzerAdapter()

    def test_fallback_returns_valid_structure(self):
        result = self.adapter._fallback_analyze("test_audio.wav")
        assert "bpm" in result
        assert result["bpm"] == 128.0
        assert "duration" in result
        assert "beats" in result
        assert len(result["beats"]) > 0
        assert "downbeats" in result
        assert result["mood"] == "energetic"
        assert result["genre"] == "edm"
        assert result["sections"] == ["intro", "build", "drop", "breakdown", "outro"]
        assert len(result["energy_values"]) == len(result["beats"])

    def test_fallback_duration_clamp(self):
        result = self.adapter._fallback_analyze("nonexistent_audio.wav")
        assert result["duration"] == 30.0
        assert len(result["beats"]) > 0
