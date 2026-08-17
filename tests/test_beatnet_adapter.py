"""tests/test_beatnet_adapter.py — BeatNetLite 节拍适配器测试

用合成 120BPM 4/4 click 音轨做可验证的真模型测试:
  - tempo 必须 ≈ 120
  - 拍数 ≈ 时长/拍间隔
  - 下拍非空且间隔为拍间隔的整数倍
"""
from __future__ import annotations

import pytest

import numpy as np
import soundfile as sf


@pytest.fixture(scope="module")
def click_track(tmp_path_factory):
    """120 BPM, 30s, 每拍底鼓, 每 4 拍加强 → 4/4 click。"""
    sr = 22050
    dur = 30.0
    beat = 60.0 / 120.0
    y = np.zeros(int(sr * dur))
    for i, t in enumerate(np.arange(0, dur, beat)):
        n = int(t * sr)
        n_samp = int(0.1 * sr)
        idx = np.arange(n_samp)
        kick = 0.8 * np.sin(2 * np.pi * 80 * idx / sr) * np.exp(-idx / (0.05 * sr))
        if i % 4 == 0:
            kick = kick * 1.6
        if n + n_samp <= len(y):
            y[n:n + n_samp] += kick
    path = tmp_path_factory.mktemp("audio") / "click120.wav"
    sf.write(str(path), y, sr)
    return str(path)


class TestDegradation:
    def test_missing_audio(self):
        from models.beat.beatnet_adapter import get_beatnet
        bn = get_beatnet()
        assert bn.analyze(r"Z:\no\such.wav") is None

    def test_available(self):
        from models.beat.beatnet_adapter import get_beatnet
        bn = get_beatnet()
        assert bn.available() is True


class TestSyntheticClick:
    def test_tempo_120(self, click_track):
        from models.beat.beatnet_adapter import get_beatnet
        bn = get_beatnet()
        r = bn.analyze(click_track)
        assert r is not None
        assert abs(r.tempo - 120.0) <= 3.0, f"tempo={r.tempo}"

    def test_beat_count(self, click_track):
        from models.beat.beatnet_adapter import get_beatnet
        r = get_beatnet().analyze(click_track)
        assert r is not None
        # 30s @120BPM ≈ 60 拍 (±3)
        assert 55 <= len(r.beats) <= 65, f"beats={len(r.beats)}"

    def test_downbeats_present(self, click_track):
        from models.beat.beatnet_adapter import get_beatnet
        r = get_beatnet().analyze(click_track)
        assert r is not None
        assert len(r.downbeats) >= 5
        # 下拍间隔 = 拍间隔 × meter (整数倍)
        gaps = [b - a for a, b in zip(r.downbeats[:-1], r.downbeats[1:])]
        beat_len = 60.0 / r.tempo
        for g in gaps[:6]:
            ratio = g / beat_len
            assert abs(ratio - round(ratio)) < 0.35, f"下拍间隔 {g:.2f}s 非拍整数倍"

    def test_to_dict(self, click_track):
        from models.beat.beatnet_adapter import get_beatnet
        r = get_beatnet().analyze(click_track)
        d = r.to_dict()
        assert d["n_beats"] == len(r.beats)
        assert "tempo" in d


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--no-header", "-p", "no:cacheprovider", "-x"])
