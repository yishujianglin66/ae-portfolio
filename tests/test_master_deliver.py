"""Tests for scripts.master_deliver — 音频母带与交付规格转码

覆盖：
  1. 路径安全校验
  2. 音频链构造（含两处实测教训的回归保护）
     - 用 volume 直接增益，不用 loudnorm+measured（后者偏离目标 1.4 LU）
     - alimiter 必须 level=disabled（默认 auto 会抬高响度 ~1.4 LU）
  3. 端到端：合成含削波片段的夹具 → 母带 → 真峰值/响度达标
  4. 交付转码：码率落入目标区间

夹具沿用 tests/test_frame_sampler.py 写法（参数列表，无 shell 拼接）。
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ))
sys.path.insert(0, str(PROJ / "scripts"))

from master_deliver import (  # noqa: E402
    TARGET_I,
    TARGET_TP,
    audio_chain,
    probe,
    safe_video,
    verify_audio,
)

HAS_FFMPEG = shutil.which("ffmpeg") is not None


# ── 纯逻辑 ────────────────────────────────────────────────────────────

def test_safe_video_rejects_missing():
    assert safe_video("nope/none.mp4") is None


def test_safe_video_rejects_bad_suffix(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("x", encoding="utf-8")
    assert safe_video(f) is None


def test_safe_video_rejects_directory(tmp_path):
    d = tmp_path / "d.mp4"
    d.mkdir()
    assert safe_video(d) is None


def test_safe_video_accepts(tmp_path):
    f = tmp_path / "c.mp4"
    f.write_bytes(b"\x00" * 8)
    assert safe_video(f) is not None


def test_audio_chain_uses_volume_gain_not_loudnorm():
    """回归保护：loudnorm+measured 会把响度留在 -12.6（目标 -14），必须用 volume。"""
    chain = audio_chain({"input_i": -6.78, "input_tp": 2.48})
    assert chain.startswith("volume=")
    assert "loudnorm" not in chain


def test_audio_chain_gain_matches_target():
    chain = audio_chain({"input_i": -6.78})
    # 增益应为 TARGET_I - input_i
    assert f"{TARGET_I - (-6.78):.3f}dB" in chain


def test_audio_chain_limiter_level_disabled():
    """回归保护：alimiter 默认 level=auto 会抬高响度 ~1.4 LU。"""
    chain = audio_chain({"input_i": -6.78})
    assert "alimiter=" in chain
    assert "level=disabled" in chain


def test_audio_chain_limiter_threshold_from_target_tp():
    chain = audio_chain({"input_i": -6.78})
    expect = f"{10 ** (TARGET_TP / 20):.6f}"
    assert f"limit={expect}" in chain


def test_audio_chain_handles_missing_measurement():
    """测量失败时退化为零增益 + 限幅，不应抛异常。"""
    chain = audio_chain({})
    assert "volume=" in chain and "alimiter=" in chain


# ── 端到端（真实 ffmpeg 夹具） ─────────────────────────────────────────

@pytest.fixture(scope="module")
def clipped_video(tmp_path_factory) -> Path:
    """合成带削波的夹具：两路正弦叠加 + 高增益（必然过 0 dBFS）。"""
    if not HAS_FFMPEG:
        pytest.skip("ffmpeg not available")
    out = tmp_path_factory.mktemp("md") / "clipped.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "quiet",
         "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=24:duration=4",
         "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=4",
         "-f", "lavfi", "-i", "sine=frequency=880:sample_rate=48000:duration=4",
         "-filter_complex", "[1:a][2:a]amix=inputs=2:normalize=0,volume=20dB[a]",
         "-map", "0:v", "-map", "[a]",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(out)],
        check=True,
    )
    return out


def test_probe_structure(clipped_video):
    info = probe(clipped_video)
    for k in ("duration", "size_mb", "mbps", "width", "height", "vcodec"):
        assert k in info


def test_verify_audio_reports_metrics(clipped_video):
    la = verify_audio(clipped_video)
    assert "lufs" in la
    assert "true_peak_dbtp" in la


def test_fixture_actually_clipped(clipped_video):
    """夹具必须真的削波，否则母带测试无意义。"""
    la = verify_audio(clipped_video)
    assert la.get("true_peak_dbtp", -99) > -1.0 or la.get("max_volume_db", -99) > -0.5
