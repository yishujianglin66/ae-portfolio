"""Tests for AutoQualityEvaluator 真实化 (D1 根因修复)

核心回归: 不同内容的视频必须得到不同分数。
旧实现(常数分)会在此测试中原形毕露。
"""
import asyncio
import shutil
import subprocess
from pathlib import Path

import pytest

from core.self_evolution_engine import AutoQualityEvaluator

HAS_FFMPEG = shutil.which("ffmpeg") is not None


def _make_video(path: Path, src: str, duration: float = 2.0):
    """ffmpeg 合成测试视频"""
    subprocess.run(
        ["ffmpeg", "-y", "-v", "quiet", "-f", "lavfi",
         "-i", f"{src}=size=320x240:rate=10:duration={duration}",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)],
        check=True,
    )


@pytest.fixture(scope="module")
def two_videos(tmp_path_factory):
    """动态画面(testsrc2) vs 静态黑屏"""
    if not HAS_FFMPEG:
        pytest.skip("ffmpeg not available")
    d = tmp_path_factory.mktemp("aqe")
    a, b = d / "dynamic.mp4", d / "static.mp4"
    _make_video(a, "testsrc2")
    # 纯黑静态画面
    subprocess.run(
        ["ffmpeg", "-y", "-v", "quiet", "-f", "lavfi",
         "-i", "color=c=black:size=320x240:rate=10:duration=2",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(b)],
        check=True,
    )
    return a, b


def _run(coro):
    """同步运行 async"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── D1 回归: 不同内容必须不同分 ──────────────────────────────────────


def test_different_content_different_score(two_videos):
    """D1 核心回归: 动态画面 vs 黑屏 → 分数必须不同(差 >1.0)"""
    a, b = two_videos
    ev = AutoQualityEvaluator()
    sa = _run(ev.evaluate(str(a), {}, {"target_resolution": (320, 240)}, {}))
    sb = _run(ev.evaluate(str(b), {}, {"target_resolution": (320, 240)}, {}))
    assert abs(sa.overall_score - sb.overall_score) > 1.0, (
        f"D1 回归! 动态={sa.overall_score:.1f}, 黑屏={sb.overall_score:.1f}, "
        f"差={abs(sa.overall_score - sb.overall_score):.1f} (需 >1.0)"
    )


def test_dynamic_video_higher_visual(two_videos):
    """动态画面的视觉分应高于黑屏"""
    a, b = two_videos
    ev = AutoQualityEvaluator()
    sa = _run(ev.evaluate(str(a), {}, {"target_resolution": (320, 240)}, {}))
    sb = _run(ev.evaluate(str(b), {}, {"target_resolution": (320, 240)}, {}))
    assert sa.visual_quality > sb.visual_quality, (
        f"动态视觉={sa.visual_quality:.1f} 应 > 黑屏视觉={sb.visual_quality:.1f}"
    )


# ── 可重复性 ─────────────────────────────────────────────────────────


def test_same_video_stable_score(two_videos):
    """同一视频两次评估波动 < 2 分"""
    a, _ = two_videos
    ev = AutoQualityEvaluator()
    s1 = _run(ev.evaluate(str(a), {}, {}, {}))
    s2 = _run(ev.evaluate(str(a), {}, {}, {}))
    assert abs(s1.overall_score - s2.overall_score) < 2.0, (
        f"可重复性差! 第一次={s1.overall_score:.1f}, 第二次={s2.overall_score:.1f}"
    )


# ── 错误处理 ─────────────────────────────────────────────────────────


def test_missing_file_low_score():
    """不存在的文件 → 低分(<35)"""
    ev = AutoQualityEvaluator()
    s = _run(ev.evaluate("nonexistent.mp4", {}, {}, {}))
    assert s.overall_score < 35, (
        f"缺失文件应得低分, 实际={s.overall_score:.1f}"
    )


def test_missing_file_technical_low():
    """不存在的文件 → 技术分低"""
    ev = AutoQualityEvaluator()
    s = _run(ev.evaluate("nonexistent.mp4", {}, {}, {}))
    assert s.technical_quality < 40


# ── 分数范围 ─────────────────────────────────────────────────────────


def test_all_scores_in_range(two_videos):
    """所有维度分数在 [0, 100] 区间"""
    a, b = two_videos
    ev = AutoQualityEvaluator()
    for video in [a, b]:
        s = _run(ev.evaluate(str(video), {}, {"target_resolution": (320, 240)}, {}))
        for name in ["overall_score", "technical_quality", "visual_quality",
                      "audio_quality", "style_consistency"]:
            val = getattr(s, name)
            assert 0.0 <= val <= 100.0, f"{name}={val} 越界"


def test_visual_has_temporal_signal(two_videos):
    """动态视频的 temporal_change > 0 → 视觉分利用了帧间差信号"""
    a, _ = two_videos
    ev = AutoQualityEvaluator()
    s = _run(ev.evaluate(str(a), {}, {"target_resolution": (320, 240)}, {}))
    # 动态 testsrc2 的 temporal_change 应 > 0
    # 如果 visual_quality 仍然是常数(如 60.0), 说明没有用到帧采样
    assert s.visual_quality != 60.0, (
        "visual_quality=60.0 说明仍在用旧常数逻辑, 未接入帧采样"
    )
