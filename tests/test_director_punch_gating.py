"""回归测试: 静态镜头必须真正静态 — onset 逐拍"拉进-闪回"不得覆盖 static/pan 镜头.

根因 (2026-08-15): `_extract_clip` 中 onset 推拉分支优先级高于 zoompan_effect,
导致 227/229 段 (含 173 个 static) 全部被鼓点 punch 覆盖 — 用户"每个镜头都
晃动推拉闪回"的真实原因。v22 无此分支, 静态镜头真静态。
"""
import subprocess
import types

import pytest

from ai.production_director import ProductionDirector


@pytest.fixture()
def director():
    # object.__new__ 跳过重初始化; 只补齐 _extract_clip 所需属性
    d = object.__new__(ProductionDirector)
    d.ffmpeg = "ffmpeg"
    d._source_durations = {"fake.mp4": 120.0}
    return d


def _run_and_capture(d, monkeypatch, **kwargs):
    """伪造 subprocess.run, 返回捕获的 -vf 滤镜串"""
    captured = {}

    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        return types.SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr("ai.production_director.subprocess.run", fake_run)
    ok = d._extract_clip(
        source="fake.mp4",
        output="C:/tmp/clip_000.mp4",
        start_time=10.0,
        duration=2.0,
        resolution=(1920, 1080),
        fps=24,
        color={"saturation": 1.2, "contrast": 1.05, "brightness": 0.0},
        speed=1.0,
        **kwargs,
    )
    assert ok is True
    vf_idx = captured["cmd"].index("-vf") + 1
    return captured["cmd"][vf_idx]


def test_static_with_onsets_has_no_zoompan(director, monkeypatch):
    """静态镜头即使含鼓点 onset 也不得注入任何 zoompan"""
    vf = _run_and_capture(director, monkeypatch,
                          zoompan_effect="static", onset_times=[0.5])
    assert "zoompan" not in vf


def test_static_without_onsets_has_no_zoompan(director, monkeypatch):
    vf = _run_and_capture(director, monkeypatch,
                          zoompan_effect="static", onset_times=[])
    assert "zoompan" not in vf


def test_pan_left_with_onsets_no_punch(director, monkeypatch):
    """摇镜头保持自身平移动画, 不叠加鼓点撞击"""
    vf = _run_and_capture(director, monkeypatch,
                          zoompan_effect="pan_left", onset_times=[0.5])
    assert "zoompan" in vf
    assert "z='1.06'" in vf
    assert "between(on," not in vf  # 撞击曲线标记


def test_zoom_back_with_onsets_no_punch(director, monkeypatch):
    vf = _run_and_capture(director, monkeypatch,
                          zoompan_effect="zoom_back", onset_times=[0.5, 1.0])
    assert "zoompan" in vf
    assert "between(on," not in vf


def test_push_with_onsets_gets_punch(director, monkeypatch):
    """撞击镜头(push)才允许 onset 逐拍 punch, 且幅度收敛至 1.15"""
    vf = _run_and_capture(director, monkeypatch,
                          zoompan_effect="push", onset_times=[0.5, 1.0])
    assert "zoompan" in vf
    assert "1.15" in vf


def test_zoom_in_single_onset_gets_punch(director, monkeypatch):
    vf = _run_and_capture(director, monkeypatch,
                          zoompan_effect="zoom_in", onset_times=[0.5])
    assert "zoompan" in vf
    assert "between(on," in vf
    assert "1.15" in vf
