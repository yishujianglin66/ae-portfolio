import os
import sys
import pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from beat_orchestrator import (
    BeatOrchestrator,
    BeatSyncConfig,
    MusicalSection,
    MUSICAL_STRUCTURE_TEMPLATES,
    BEAT_EFFECT_STYLES,
)


class TestBeatOrchestratorInitialization:
    def test_initialization(self):
        bo = BeatOrchestrator(bpm=120, fps=30, beats_per_measure=4)
        assert bo.bpm == 120
        assert bo.fps == 30
        assert bo.beats_per_measure == 4
        assert bo.beat_interval == pytest.approx(0.5)
        assert bo.measure_interval == pytest.approx(2.0)

    def test_initialization_defaults(self):
        bo = BeatOrchestrator()
        assert bo.bpm == 120
        assert bo.fps == 30
        assert bo.beats_per_measure == 4


class TestBeatInterval:
    def test_beat_interval_calculation(self):
        bo = BeatOrchestrator(bpm=60)
        assert bo.beat_interval == pytest.approx(1.0)
        assert bo.measure_interval == pytest.approx(4.0)

        bo2 = BeatOrchestrator(bpm=120)
        assert bo2.beat_interval == pytest.approx(0.5)
        assert bo2.measure_interval == pytest.approx(2.0)

        bo3 = BeatOrchestrator(bpm=150)
        assert bo3.beat_interval == pytest.approx(0.4)


class TestBeatTimeline:
    def test_generate_beat_timeline(self):
        bo = BeatOrchestrator(bpm=120)
        beats = bo.generate_beat_timeline(duration=2.0)
        assert len(beats) == 5
        assert beats[0] == 0.0
        assert beats[1] == pytest.approx(0.5)
        assert beats[2] == pytest.approx(1.0)
        assert beats[3] == pytest.approx(1.5)
        assert beats[4] == pytest.approx(2.0)

    def test_generate_beat_timeline_with_offset(self):
        bo = BeatOrchestrator(bpm=120)
        beats = bo.generate_beat_timeline(duration=1.0, offset=0.25)
        assert len(beats) == 3
        assert beats[0] == pytest.approx(0.25)
        assert beats[1] == pytest.approx(0.75)
        assert beats[2] == pytest.approx(1.25)

    def test_generate_downbeats(self):
        bo = BeatOrchestrator(bpm=120, beats_per_measure=4)
        downbeats = bo.generate_downbeats(duration=4.0)
        assert len(downbeats) == 3
        assert downbeats[0] == 0.0
        assert downbeats[1] == pytest.approx(2.0)
        assert downbeats[2] == pytest.approx(4.0)


class TestBeatAnimation:
    def test_beat_scale_animation(self):
        bo = BeatOrchestrator(bpm=120)
        beat_times = bo.generate_beat_timeline(duration=1.0)
        config = BeatSyncConfig(
            property_type="scale",
            base_value=100.0,
            beat_value=115.0,
            attack=0.05,
            decay=0.15,
        )
        keyframes = bo.generate_beat_synced_keyframes("layer1", beat_times, config)
        assert len(keyframes) == len(beat_times) * 3
        assert keyframes[0]["propertyName"] == "Scale"
        assert keyframes[0]["value"] == 100.0
        assert keyframes[1]["value"] == 115.0

    def test_beat_opacity_animation(self):
        bo = BeatOrchestrator(bpm=120)
        beat_times = bo.generate_beat_timeline(duration=0.5)
        config = BeatSyncConfig(
            property_type="opacity",
            base_value=80.0,
            beat_value=100.0,
            attack=0.02,
            decay=0.08,
        )
        keyframes = bo.generate_beat_synced_keyframes("layer1", beat_times, config)
        assert keyframes[0]["propertyName"] == "Opacity"
        assert keyframes[0]["value"] == 80.0
        assert keyframes[1]["value"] == 100.0

    def test_effect_on_beat(self):
        bo = BeatOrchestrator(bpm=120)
        beat_times = bo.generate_beat_timeline(duration=1.0)
        triggers = bo.generate_beat_effect_triggers(
            "layer1", beat_times, "glow_pulse", intensity=1.0
        )
        assert len(triggers) == len(beat_times) * 3
        assert triggers[0]["propertyName"] == "Glow Intensity"
        assert triggers[0]["value"] == 0.0
        assert triggers[1]["value"] == 100.0

    def test_effect_on_beat_intensity(self):
        bo = BeatOrchestrator(bpm=120)
        beat_times = [0.0]
        triggers = bo.generate_beat_effect_triggers(
            "layer1", beat_times, "glow_pulse", intensity=0.5
        )
        assert triggers[1]["value"] == 50.0


class TestMusicalStructure:
    def test_musical_structure_sections(self):
        bo = BeatOrchestrator()
        sections = bo.generate_musical_structure(duration=100.0, template="pop_song")
        assert len(sections) == 7
        assert sections[0].type == "intro"
        assert sections[0].start_time == 0.0
        assert sections[-1].type == "outro"
        assert sections[-1].end_time == 100.0
        total_duration = sum(s.end_time - s.start_time for s in sections)
        assert total_duration == pytest.approx(100.0)

    def test_musical_structure_edm(self):
        bo = BeatOrchestrator()
        sections = bo.generate_musical_structure(duration=60.0, template="edm_drop")
        assert len(sections) == 6
        section_types = [s.type for s in sections]
        assert "drop" in section_types
        assert "build_up" in section_types

    def test_musical_structure_unknown_template(self):
        bo = BeatOrchestrator()
        sections = bo.generate_musical_structure(duration=10.0, template="nonexistent")
        assert len(sections) > 0

    def test_energy_to_intensity_mapping(self):
        bo = BeatOrchestrator()
        intensity_0 = bo.energy_to_intensity(0.0)
        intensity_1 = bo.energy_to_intensity(1.0)
        intensity_05 = bo.energy_to_intensity(0.5)

        assert intensity_0 == 0.0
        assert intensity_1 == 1.0
        assert 0.0 < intensity_05 < 1.0

        clamped_high = bo.energy_to_intensity(1.5)
        clamped_low = bo.energy_to_intensity(-0.5)
        assert clamped_high == 1.0
        assert clamped_low == 0.0


class TestFullBeatShow:
    def test_generate_full_beat_show(self):
        bo = BeatOrchestrator(bpm=120)
        result = bo.generate_full_beat_show(
            layer_name="test_layer",
            duration=10.0,
            style="energetic",
            structure_template="short_hook",
        )
        assert result["layerName"] == "test_layer"
        assert result["duration"] == 10.0
        assert result["style"] == "energetic"
        assert "sections" in result
        assert "keyframes" in result
        assert "effect_triggers" in result
        assert result["total_keyframes"] > 0
        assert len(result["sections"]) > 0

    def test_generate_full_beat_show_styles(self):
        bo = BeatOrchestrator(bpm=120)
        for style in BEAT_EFFECT_STYLES.keys():
            result = bo.generate_full_beat_show(
                layer_name="layer1",
                duration=5.0,
                style=style,
                structure_template="short_hook",
            )
            assert result["style"] == style
            assert result["total_keyframes"] > 0
