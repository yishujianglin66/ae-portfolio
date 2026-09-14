"""mastercut_agent `analyze_beat` 能力回归测试。

背景（2026-09-14）：该能力曾调用**已不存在的旧 API**
（`BeatStrengthEngine.detect(path)` / `MusicDynamicsAnalyzer.analyze(path)`），
任何调用即 `AttributeError` 硬崩。重实现后改用正确的三口：
    ae.beat_detector.BeatTracker/BeatDetector（路径→拍点+onset）
    core.beat_strength_engine（强弱分级统计）
    core.music_dynamics（逐帧 RMS→动态分段）
本测试用**合成 click 轨**（stdlib wave 写盘，无需外部素材/网络）钉死输出契约，
确保该能力不会再静默退化为坏 API。慢（librosa 分析 ~1-3s），标记 slow。
"""
from __future__ import annotations

import wave

import numpy as np
import pytest

from agents.mastercut_agent import _stage_analyze_beat


def _write_click_track(path, sr: int = 22050, duration: float = 6.0, bpm: int = 120) -> None:
    """写一个每拍一击的 16-bit PCM 单声道 wav（可被 librosa 读取）。"""
    t = np.arange(int(sr * duration)) / sr
    y = np.zeros_like(t)
    interval = 60.0 / bpm
    for k in range(int(duration / interval)):
        i = int(k * interval * sr)
        y[i:i + 200] = 0.8
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((y * 32767).astype("<i2").tobytes())


@pytest.mark.slow
def test_analyze_beat_contract_on_synthetic_click_track(tmp_path) -> None:
    audio = tmp_path / "click.wav"
    _write_click_track(audio)

    result = _stage_analyze_beat(str(audio))

    assert set(result) >= {"beat_count", "beats", "sections", "beat_strength"}
    assert result["beat_count"] > 0
    assert len(result["beats"]) > 0
    assert all({"time", "strength"} <= set(b) for b in result["beats"])
    # 分级统计来自 beat_strength_engine（不再走已删除的 detect()）
    assert {"total", "strong", "medium", "weak", "bpm", "bars"} <= set(result["beat_strength"])
    assert result["beat_strength"]["total"] == result["beat_count"]
    # 动态分段来自 music_dynamics（不再走已删除的 analyze(path)）
    assert len(result["sections"]) > 0
    assert all({"start", "end", "level", "energy"} <= set(s) for s in result["sections"])


@pytest.mark.slow
def test_analyze_beat_silent_input_does_not_crash(tmp_path) -> None:
    """静音输入应安全返回空拍点，而不是抛异常（守卫分支）。"""
    silent = tmp_path / "silent.wav"
    with wave.open(str(silent), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(22050)
        w.writeframes((np.zeros(22050 * 2)).astype("<i2").tobytes())

    result = _stage_analyze_beat(str(silent))
    assert "beat_count" in result
    assert isinstance(result["sections"], list)
