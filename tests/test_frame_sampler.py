"""Tests for core.frame_sampler - 真实帧采样统计

TDD: 用 ffmpeg 合成测试视频, 验证 probe_video 和 sample_frame_stats 的真实解码输出。
"""
import shutil
import subprocess
from pathlib import Path

import pytest

from core.frame_sampler import FrameStats, probe_video, sample_frame_stats

HAS_FFMPEG = shutil.which("ffmpeg") is not None


@pytest.fixture(scope="module")
def synthetic_video(tmp_path_factory) -> Path:
    """ffmpeg 生成 2s 渐变测试视频(真实解码对象)"""
    if not HAS_FFMPEG:
        pytest.skip("ffmpeg not available")
    out = tmp_path_factory.mktemp("fs") / "synthetic.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "quiet", "-f", "lavfi",
         "-i", "testsrc2=size=320x240:rate=10:duration=2",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out)],
        check=True,
    )
    return out


@pytest.fixture(scope="module")
def audio_video(tmp_path_factory) -> Path:
    """ffmpeg 生成 2s 带音频的测试视频"""
    if not HAS_FFMPEG:
        pytest.skip("ffmpeg not available")
    out = tmp_path_factory.mktemp("fs") / "with_audio.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "quiet", "-f", "lavfi",
         "-i", "testsrc2=size=320x240:rate=10:duration=2",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
         "-c:v", "libx264", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-shortest", str(out)],
        check=True,
    )
    return out


# ── probe_video ──────────────────────────────────────────────────────


def test_probe_video_dimensions(synthetic_video):
    """探测视频基本技术参数: 320x240"""
    info = probe_video(str(synthetic_video))
    assert info["width"] == 320
    assert info["height"] == 240


def test_probe_video_fps(synthetic_video):
    """探测帧率: 10fps"""
    info = probe_video(str(synthetic_video))
    assert info["fps"] == pytest.approx(10.0, abs=0.5)


def test_probe_video_duration(synthetic_video):
    """探测时长: 2s"""
    info = probe_video(str(synthetic_video))
    assert info["duration"] == pytest.approx(2.0, abs=0.2)


def test_probe_video_no_audio(synthetic_video):
    """纯视频无音频轨"""
    info = probe_video(str(synthetic_video))
    assert info["has_audio"] is False


def test_probe_video_with_audio(audio_video):
    """带音频轨的视频"""
    info = probe_video(str(audio_video))
    assert info["has_audio"] is True


def test_probe_video_codec(synthetic_video):
    """编码器名称非空"""
    info = probe_video(str(synthetic_video))
    assert info["codec"] != ""


# ── sample_frame_stats ───────────────────────────────────────────────


def test_sample_frame_stats_count(synthetic_video):
    """采样帧数: 请求 8 帧应返回 8 帧"""
    stats = sample_frame_stats(str(synthetic_video), n_frames=8)
    assert stats.n_sampled == 8


def test_sample_frame_stats_luma_range(synthetic_video):
    """平均亮度在 [0, 1] 区间"""
    stats = sample_frame_stats(str(synthetic_video), n_frames=8)
    assert 0.0 <= stats.mean_luma <= 1.0


def test_sample_frame_stats_contrast_positive(synthetic_video):
    """testsrc2 有丰富纹理 → 帧内亮度标准差 > 0"""
    stats = sample_frame_stats(str(synthetic_video), n_frames=8)
    assert stats.luma_contrast > 0.0


def test_sample_frame_stats_temporal_nonneg(synthetic_video):
    """帧间变化 >= 0"""
    stats = sample_frame_stats(str(synthetic_video), n_frames=8)
    assert stats.temporal_change >= 0.0


def test_sample_frame_stats_default_frames(synthetic_video):
    """默认 16 帧采样"""
    stats = sample_frame_stats(str(synthetic_video))
    assert stats.n_sampled == 16


# ── 错误处理 ─────────────────────────────────────────────────────────


def test_probe_missing_file():
    """不存在的文件 → FileNotFoundError"""
    with pytest.raises(FileNotFoundError):
        probe_video("nonexistent_video.mp4")


def test_sample_missing_file():
    """不存在的文件 → FileNotFoundError"""
    with pytest.raises(FileNotFoundError):
        sample_frame_stats("nonexistent_video.mp4")


# ── FrameStats dataclass ─────────────────────────────────────────────


def test_frame_stats_defaults():
    """默认构造: 全零"""
    stats = FrameStats()
    assert stats.n_sampled == 0
    assert stats.mean_luma == 0.0
    assert stats.luma_contrast == 0.0
    assert stats.temporal_change == 0.0
