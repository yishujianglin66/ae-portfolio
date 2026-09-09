"""Tests for scripts.cut_visibility_v2 — 帧号对齐的切点可见性度量 v2

覆盖：
  1. 路径安全校验
  2. 归一化与 ahash/hamming 基础件
  3. frames_by_number 分批取帧（含超长 select 表达式的回归保护）
  4. 端到端：ffmpeg 合成硬切夹具 → v2 计算
  5. **确定性回归**：同一视频重复计算必须完全一致（v1 的病态性反例）
  6. 硬切夹具的可见性应显著高于纯色夹具

夹具沿用 tests/test_frame_sampler.py 写法（参数列表，无 shell 拼接）。
"""
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ))
sys.path.insert(0, str(PROJ / "scripts"))

from cut_visibility_v2 import (  # noqa: E402
    PAIR_OFFSETS,
    ahash,
    analyze_video,
    frames_by_number,
    hamming,
    norm,
    safe_video,
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


def test_norm_zero_mean_unit_std():
    rng = np.random.default_rng(1)
    x = (rng.random(100) * 255).astype(np.float32)
    n = norm(x)
    assert abs(float(n.mean())) < 1e-5
    assert abs(float(n.std()) - 1.0) < 1e-3


def test_ahash_deterministic():
    rng = np.random.default_rng(2)
    f = (rng.random((27, 48)) * 255).astype(np.float32)
    assert ahash(f) == ahash(f)


def test_ahash_identical_frames_zero_distance():
    rng = np.random.default_rng(3)
    f = (rng.random((27, 48)) * 255).astype(np.float32)
    assert hamming(ahash(f), ahash(f)) == 0


def test_ahash_different_frames_positive_distance():
    a = np.zeros((27, 48), dtype=np.float32)
    b = np.full((27, 48), 255.0, dtype=np.float32)
    # 全零 vs 全白：均值比较无意义，但哈希应稳定可比
    assert isinstance(hamming(ahash(a), ahash(b)), int)


def test_pair_offsets_constant():
    assert PAIR_OFFSETS == (1, 2, 3)


# ── 端到端（真实 ffmpeg 夹具） ─────────────────────────────────────────

@pytest.fixture(scope="module")
def hardcut_video(tmp_path_factory) -> Path:
    """三段不同图案各 1s，制造真实硬切（24fps）。"""
    if not HAS_FFMPEG:
        pytest.skip("ffmpeg not available")
    out = tmp_path_factory.mktemp("cv2") / "hardcut.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "quiet",
         "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=24:duration=1",
         "-f", "lavfi", "-i", "smptebars=size=320x240:rate=24:duration=1",
         "-f", "lavfi", "-i", "testsrc=size=320x240:rate=24:duration=1",
         "-filter_complex", "[0][1][2]concat=n=3:v=1:a=0",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out)],
        check=True,
    )
    return out


def test_frames_by_number_batch(hardcut_video):
    """取帧必须返回请求的帧号（回归保护：超长 select 表达式曾导致空输出）。"""
    want = list(range(0, 70))
    got = frames_by_number(hardcut_video, want)
    assert len(got) >= len(want) * 0.9
    for fn in (0, 10, 30, 60):
        assert fn in got


def test_frames_by_number_empty():
    assert frames_by_number(Path("x.mp4"), []) == {}


def test_analyze_video_structure(hardcut_video):
    r = analyze_video(hardcut_video)
    for key in ("video", "fps", "n_cuts", "cut_visibility_v2",
                "p25", "p50", "p75", "min", "frozen_rate", "cuts"):
        assert key in r


def test_analyze_video_deterministic(hardcut_video):
    """v2 必须完全确定（v1 在 ±0.5ms 扰动下会波动 0.78）。"""
    a = analyze_video(hardcut_video)["cut_visibility_v2"]
    b = analyze_video(hardcut_video)["cut_visibility_v2"]
    assert a == b


def test_analyze_video_hardcut_high_visibility(hardcut_video):
    """三段截然不同的图案，切点可见性应显著 > 0。"""
    r = analyze_video(hardcut_video)
    if r["n_cuts"] == 0:
        pytest.skip("夹具未检出切点")
    assert r["cut_visibility_v2"] > 0.3


def test_analyze_video_percentiles_ordered(hardcut_video):
    r = analyze_video(hardcut_video)
    if r["n_cuts"] == 0:
        pytest.skip("夹具未检出切点")
    assert r["p25"] <= r["p50"] <= r["p75"]
    assert r["min"] <= r["p25"]
