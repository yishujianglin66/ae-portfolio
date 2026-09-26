"""回归测试: 撞击运镜的适用范围 (onset 逐拍"拉进-闪回"允许作用于哪些镜头).

根因 (2026-08-15): `_extract_clip` 中 onset 推拉分支优先级高于 zoompan_effect,
而当时的触发源是**全量 onset**(~10 事件/秒), 于是 227/229 段 (含 173 个 static)
全部被鼓点 punch 覆盖 — 用户"每个镜头都晃动推拉闪回"的真实原因。

根因 (2026-09-19 二次反馈): 用户"不够, 没跟小提琴节奏变换, 视觉冲击力不到位"
→ 撞击改由**精选重音**驱动 (强鼓点≥0.5 ∪ 小提琴重音≥0.85, 约 2 事件/秒),
static 重新纳入可撞击类型 (落在静止镜头上的小提琴重音不该被忽略; 静止镜头里
撞击的视觉对比度最高)。此时"每镜头都晃动"的成因(全量触发源)已不存在。

不变式:
  · static 无 onset      → 真静态 (无 zoompan)
  · static 有 onset      → 承载撞击 (PUNCH_ELIGIBLE_EFFECTS)
  · 平移/斜移类          → 永不承载撞击 (基础运镜与撞击叠加会互相干扰)
  · push / zoom_in       → 承载撞击, 幅度峰值 = 1+PUNCH_PEAK (env 可调, 默认 0.22)
    (2026-09-26: 峰值 0.15→0.22 时本文件漏改红过 — 故契约改为**跟随常量
    PUNCH_PEAK**, 不再硬编码字面量, 调参不再需要同步这里)
"""
import subprocess
import types

import pytest

from ai.production_director import PUNCH_PEAK, ProductionDirector


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


def test_static_with_onsets_gets_punch(director, monkeypatch):
    """static 含精选重音时承载撞击 (2026-09-19 起; 见模块 docstring 的不变式)"""
    vf = _run_and_capture(director, monkeypatch,
                          zoompan_effect="static", onset_times=[0.5])
    assert "zoompan" in vf
    assert "between(on," in vf     # 撞击曲线标记
    assert f"{PUNCH_PEAK:g}" in vf  # 幅度峰值跟随 PUNCH_PEAK (env 可调)


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
    """撞击镜头(push)才允许 onset 逐拍 punch, 幅度峰值跟随 PUNCH_PEAK"""
    vf = _run_and_capture(director, monkeypatch,
                          zoompan_effect="push", onset_times=[0.5, 1.0])
    assert "zoompan" in vf
    assert f"{PUNCH_PEAK:g}" in vf


def test_zoom_in_single_onset_gets_punch(director, monkeypatch):
    vf = _run_and_capture(director, monkeypatch,
                          zoompan_effect="zoom_in", onset_times=[0.5])
    assert "zoompan" in vf
    assert "between(on," in vf
    assert f"{PUNCH_PEAK:g}" in vf
