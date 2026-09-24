# -*- coding: utf-8 -*-
"""production_director 助手层特征化测试（2026-09-20）。

背景：覆盖率快照显示 `ai/production_director.py` 是本仓库最大的未覆盖块
（3104 语句 / 现有测试仅覆盖 10.78% / 2734 行未覆盖）。`render()` 编排本身难以
单测（依赖 AE/素材/时长），但其**助手层**完全可测，且本会话的多处修复正落在这层：
帧数探测、段级对账、拼接兜底、转场帧量化、时长守卫读的是视频流而非容器时长。

本文件把这些真实契约钉住（含已知隐患的如实记录），不追求行数而是锁定行为。

ffmpeg 夹具用**全字面量命令行**构造素材：不做任何字符串插值，杜绝注入面。
"""
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

import ai.production_director as pd  # noqa: E402
from ai.production_director import (  # noqa: E402
    COLOR_PRESETS,
    PUNCH_ATTACK_FRAMES,
    PUNCH_ELIGIBLE_EFFECTS,
    PUNCH_ENVELOPE,
    PUNCH_PEAK,
    PUNCH_RELEASE_FRAMES,
    PUNCH_STRENGTH_DEFAULT,
    SPEED_PRESETS,
    XFADE_MAP,
    ProductionDirector,
    RenderResult,
)

FPS = 24


def _mk_std_video(path: Path) -> Path:
    """64x64 @24fps 0.5s = 12 帧（字面量素材，无插值）。"""
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
         "-i", "testsrc=size=64x64:rate=24:duration=0.5",
         "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
         "-bf", "0", str(path)],
        check=True, capture_output=True, timeout=120)
    return path


def _mk_alt_video(path: Path) -> Path:
    """96x96 @30fps 0.5s = 15 帧（参数不同，用于滤镜拼接归一化测试）。"""
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
         "-i", "testsrc=size=96x96:rate=30:duration=0.5",
         "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
         "-bf", "0", str(path)],
        check=True, capture_output=True, timeout=120)
    return path


def _mk_video_with_audio(path: Path) -> Path:
    """视频 + AAC 音轨（用于 _validate 的 audio 分支）。"""
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
         "-i", "testsrc=size=64x64:rate=24:duration=0.5",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=0.5",
         "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
         "-bf", "0", "-c:a", "aac", "-shortest", str(path)],
        check=True, capture_output=True, timeout=120)
    return path


def _director():
    """绕开重型 __init__，只装 ffmpeg/ffprobe 句柄与渲染帧率。"""
    d = ProductionDirector.__new__(ProductionDirector)
    d.ffmpeg = "ffmpeg"
    d.ffprobe = "ffprobe"
    d._render_fps = FPS
    return d


@pytest.fixture(scope="module")
def video(tmp_path_factory):
    return _mk_std_video(tmp_path_factory.mktemp("pdc") / "a.mp4")


@pytest.fixture(scope="module")
def video_audio(tmp_path_factory):
    return _mk_video_with_audio(tmp_path_factory.mktemp("pdc") / "b.mp4")


# ---------------------------------------------------------------------------
# 常量不变量（配置漂移的哨兵）
# ---------------------------------------------------------------------------

class TestConstants:
    def test_punch_envelope_is_attack_plus_release(self):
        assert PUNCH_ENVELOPE == PUNCH_ATTACK_FRAMES + PUNCH_RELEASE_FRAMES == 7

    def test_punch_gap_matches_envelope(self):
        """间隔必须 ≥ 包络，否则撞击叠成持续晃动（2026-09-19 听感事故）。"""
        assert pd.PUNCH_MIN_GAP_FRAMES >= PUNCH_ENVELOPE

    def test_punch_peak_within_ae_clamp(self):
        """幅度上限 1.15 是既有约定；PUNCH_PEAK 不得越过。"""
        assert 0 < PUNCH_PEAK <= 0.15
        assert PUNCH_STRENGTH_DEFAULT == 0.5

    def test_punch_eligible_effects_are_real_effects(self):
        for fx in PUNCH_ELIGIBLE_EFFECTS:
            assert isinstance(fx, str) and fx

    def test_xfade_map_entries_wellformed(self):
        for tag, (name, dur) in XFADE_MAP.items():
            assert isinstance(tag, str) and isinstance(name, str) and name
            assert 0 < dur <= 0.5, f"{tag} 转场时长越界: {dur}"

    def test_color_and_speed_presets_share_mood_keys(self):
        """调色与变速预设必须覆盖同一套情绪键（缺键会静默退回默认）。"""
        assert set(COLOR_PRESETS) == set(SPEED_PRESETS)
        for mood, p in COLOR_PRESETS.items():
            assert {"saturation", "contrast", "brightness"} <= set(p), mood

    def test_render_result_video_duration_defaults_zero(self):
        """2026-09-19 新增字段：必须默认 0（缺失时下游不得误判为"等长"）。"""
        assert RenderResult(output_path="x", success=True).video_duration == 0.0


# ---------------------------------------------------------------------------
# _xfade_for —— 转场标签 → (滤镜名, 时长) 的全部分支
# ---------------------------------------------------------------------------

def _seg(**kw):
    kw.setdefault("transition", "cut")
    kw.setdefault("transition_params", None)
    kw.setdefault("speed", 1.0)
    return SimpleNamespace(**kw)


class TestXfadeFor:
    def test_cut_returns_empty(self):
        assert _director()._xfade_for(_seg(transition="cut")) == ("", 0.0)

    def test_unknown_tag_returns_empty(self):
        assert _director()._xfade_for(_seg(transition="no_such_transition")) == ("", 0.0)

    def test_known_tag_returns_filter_and_duration(self):
        name, dur = _director()._xfade_for(_seg(transition="fade"))
        assert name == XFADE_MAP["fade"][0]
        assert 0 < dur <= 0.5

    def test_transition_params_type_overrides_tag(self):
        seg = _seg(transition="cut", transition_params={"type": "glitch"})
        assert _director()._xfade_for(seg)[0] == XFADE_MAP["glitch"][0]

    def test_duration_is_frame_quantized_and_clamped(self):
        """帧量化：时长对齐整帧；上限 0.5s 体现在钳制分支。"""
        seg = _seg(transition="fade", transition_params={"type": "fade",
                                                         "duration": 9.9})
        _, dur = _director()._xfade_for(seg)
        assert dur == pytest.approx(0.5)
        assert abs(dur * FPS - round(dur * FPS)) < 1e-9

    def test_speed_changed_forces_hard_cut(self):
        """变速镜头强制硬切（xfade×setpts 叠加会造成切点漂移）。"""
        assert _director()._xfade_for(_seg(transition="fade", speed=0.55)) == ("", 0.0)

    def test_force_cut_env_returns_none(self, monkeypatch):
        monkeypatch.setenv("V23_FORCE_CUT", "1")
        assert _director()._xfade_for(_seg(transition="fade")) == (None, 0.0)


# ---------------------------------------------------------------------------
# _group_for_transitions —— 链式分组
# ---------------------------------------------------------------------------

class TestGroupForTransitions:
    def test_all_cuts_yield_singletons(self):
        clips = [(f"c{i}.mp4", _seg(transition="cut")) for i in range(4)]
        groups = _director()._group_for_transitions(clips)
        assert [len(g) for g in groups] == [1, 1, 1, 1]

    def test_consecutive_transitions_chain(self):
        """分组由**后续镜头**携带的转场决定：a 与 b/c 同链，因为 b、c 带 fade。

        即在 `_group_for_transitions` 语义里，"进入该段的转场"决定它与前一段是否同链；
        首个镜头无论自身标签如何都起始一条链。
        """
        clips = [("a.mp4", _seg(transition="cut")),
                 ("b.mp4", _seg(transition="fade")),
                 ("c.mp4", _seg(transition="fade")),
                 ("d.mp4", _seg(transition="cut"))]
        groups = _director()._group_for_transitions(clips)
        assert [len(g) for g in groups] == [3, 1]

    def test_group_size_cap_enforced(self):
        clips = [("a.mp4", _seg(transition="cut"))] + \
                [(f"b{i}.mp4", _seg(transition="fade"))
                 for i in range(pd.XFADE_GROUP_SIZE + 2)]
        groups = _director()._group_for_transitions(clips)
        assert max(len(g) for g in groups) <= pd.XFADE_GROUP_SIZE


# ---------------------------------------------------------------------------
# 探测层（真实 ffprobe）
# ---------------------------------------------------------------------------

class TestProbes:
    def test_probe_duration_and_frames(self, video):
        d = _director()
        assert d._probe_duration(str(video)) == pytest.approx(0.5, abs=0.1)
        assert d._probe_nframes(str(video)) == 12
        assert d._probe_frame_count(str(video)) == 12

    def test_probe_video_duration_matches_stream(self, video):
        assert _director()._probe_video_duration(str(video)) == pytest.approx(0.5, abs=0.1)

    def test_probe_nframes_missing_file_returns_negative(self, tmp_path):
        assert _director()._probe_nframes(str(tmp_path / "nope.mp4")) < 0

    def test_probe_duration_failure_falls_back_to_60(self, tmp_path):
        """已知隐患（如实记录）：探测失败回退 60.0 秒，会让时长守卫误判超长。

        此处锁住当前行为，避免有人误以为失败会返回 0 或抛异常；真要修需全链复核
        （已在踩点修复报告 §五 登记为遗留项）。
        """
        assert _director()._probe_duration(str(tmp_path / "nope.mp4")) == 60.0

    def test_probe_has_audio(self, video, video_audio):
        d = _director()
        assert d._probe_has_audio(str(video_audio)) is True
        assert d._probe_has_audio(str(video)) is False


# ---------------------------------------------------------------------------
# _validate —— 结果字段（含 2026-09-19 新增 video_duration）
# ---------------------------------------------------------------------------

class TestValidate:
    def test_validate_populates_result(self, video_audio):
        r = _director()._validate(str(video_audio))
        assert r.success is True
        assert r.fps == FPS
        assert r.resolution == (64, 64)
        assert r.has_audio is True
        assert r.duration > 0
        assert r.video_duration > 0, "video_duration 必须被填充（容器时长会掩盖短视频）"

    def test_missing_file_reports_error(self, tmp_path):
        r = _director()._validate(str(tmp_path / "nope.mp4"))
        assert r.success is False and r.error_message


# ---------------------------------------------------------------------------
# 拼接层（2026-09-19 丢帧事故的两个兜底）
# ---------------------------------------------------------------------------

class TestConcat:
    def test_concat_hard_preserves_frames(self, tmp_path):
        clips = [_mk_std_video(tmp_path / f"c{i}.mp4") for i in range(3)]
        d = _director()
        out = tmp_path / "joined.mp4"
        assert d._concat_hard([str(c) for c in clips], str(out)) is True
        assert d._probe_nframes(str(out)) == 36

    def test_concat_hard_force_reencode_path(self, tmp_path):
        """force_reencode 跳过流拷贝（流拷贝丢帧时用）。"""
        clips = [_mk_std_video(tmp_path / f"r{i}.mp4") for i in range(2)]
        d = _director()
        out = tmp_path / "re.mp4"
        assert d._concat_hard([str(c) for c in clips], str(out),
                              force_reencode=True) is True
        assert d._probe_nframes(str(out)) == 24

    def test_concat_filter_normalizes_mixed_params(self, tmp_path):
        """滤镜兜底：输入参数不一致（分辨率/帧率不同）也能全量拼出。

        时长守恒：3 段各 0.5s → 24fps 归一化后各 12 帧。
        """
        clips = [_mk_std_video(tmp_path / "n1.mp4"),
                 _mk_alt_video(tmp_path / "n2.mp4"),
                 _mk_std_video(tmp_path / "n3.mp4")]
        d = _director()
        out = tmp_path / "fc.mp4"
        assert d._concat_filter([str(c) for c in clips], str(out),
                                size=(64, 64), fps=24) is True
        assert d._probe_nframes(str(out)) == 36
