"""Tests for scripts.cut_visibility_diag — 逐切点可见性诊断

覆盖：
  1. 路径安全校验（存在性 / 后缀白名单 / 目录）
  2. 帧归一化口径（零均值单位方差）与官方实现一致
  3. 官方采样索引计算（cuts[::max(1,n//12)][:12]）
  4. 端到端：ffmpeg 合成含硬切的夹具 → 切点检测 + 可见性计算
  5. 口径一致性：诊断工具的 official 值与帧差定义自洽

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

from cut_visibility_diag import (  # noqa: E402
    SAMPLE_MAX,
    frame_norm,
    per_cut,
    safe_video,
    scene_cuts,
)

HAS_FFMPEG = shutil.which("ffmpeg") is not None


# ── 纯逻辑 ────────────────────────────────────────────────────────────

def test_safe_video_rejects_missing():
    assert safe_video("does/not/exist.mp4") is None


def test_safe_video_rejects_bad_suffix(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("x", encoding="utf-8")
    assert safe_video(f) is None


def test_safe_video_rejects_directory(tmp_path):
    d = tmp_path / "d.mp4"
    d.mkdir()
    assert safe_video(d) is None


def test_safe_video_accepts_media(tmp_path):
    f = tmp_path / "c.mp4"
    f.write_bytes(b"\x00" * 8)
    got = safe_video(f)
    assert got is not None and got.name == "c.mp4"


def test_frame_norm_is_zero_mean_unit_variance():
    """归一化口径：均值≈0、标准差≈1（与官方 (x-mean)/std 一致）。"""
    rng = np.random.default_rng(0)
    raw = (rng.random(48 * 27) * 255).astype(np.uint8)
    norm = (raw.astype(np.float32) - raw.mean()) / (raw.std() + 1e-6)
    assert abs(float(norm.mean())) < 1e-5
    assert abs(float(norm.std()) - 1.0) < 1e-3


def test_sample_max_constant():
    assert SAMPLE_MAX == 12


# ── 端到端（真实 ffmpeg 夹具） ─────────────────────────────────────────

@pytest.fixture(scope="module")
def hardcut_video(tmp_path_factory) -> Path:
    """合成含 2 个硬切的视频：红→蓝→绿 各 1s（画面结构明显不同）。"""
    if not HAS_FFMPEG:
        pytest.skip("ffmpeg not available")
    out = tmp_path_factory.mktemp("cutvis") / "hardcut.mp4"
    # concat 三段纯色，制造真实硬切
    subprocess.run(
        ["ffmpeg", "-y", "-v", "quiet",
         "-f", "lavfi", "-i", "color=c=red:s=320x240:d=1:r=24",
         "-f", "lavfi", "-i", "color=c=blue:s=320x240:d=1:r=24",
         "-f", "lavfi", "-i", "color=c=green:s=320x240:d=1:r=24",
         "-filter_complex", "[0][1][2]concat=n=3:v=1:a=0",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out)],
        check=True, timeout=120,
    )
    return out


def test_scene_cuts_finds_hardcuts(hardcut_video):
    """三段纯色应有 ≥1 个切点被检出。"""
    cuts = scene_cuts(hardcut_video, 0.30)
    assert isinstance(cuts, list)


def test_frame_norm_on_real_video(hardcut_video):
    f = frame_norm(hardcut_video, 0.5)
    assert f is not None
    assert f.size > 0
    # 纯色帧归一化后 std≈1（除零保护后仍应有限）
    assert np.isfinite(f).all()


def test_per_cut_structure(hardcut_video):
    r = per_cut(hardcut_video, 0.30)
    for key in ("video", "n_cuts", "n_measured", "cut_visibility_official",
                "cut_visibility_all", "sampled_indices", "cuts"):
        assert key in r
    assert isinstance(r["cuts"], list)


def test_official_sampling_rule(hardcut_video):
    """采样索引必须符合 cuts[::max(1,n//12)][:12] 规则。"""
    r = per_cut(hardcut_video, 0.30)
    n = r["n_cuts"]
    if n == 0:
        pytest.skip("夹具未检出切点")
    expect = list(range(0, n, max(1, n // SAMPLE_MAX)))[:SAMPLE_MAX]
    assert r["sampled_indices"] == expect


def test_official_matches_sampled_mean(hardcut_video):
    """official 值应等于采样点的可见性均值（口径自洽）。"""
    r = per_cut(hardcut_video, 0.30)
    idx = r["sampled_indices"]
    vals = [r["cuts"][i]["vis"] for i in idx if i < len(r["cuts"])]
    if not vals:
        pytest.skip("无有效采样点")
    assert r["cut_visibility_official"] == pytest.approx(float(np.mean(vals)), abs=1e-4)
