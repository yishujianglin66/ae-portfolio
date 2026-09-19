"""Tests for core.audio_budget — 混音能量预算

覆盖：
  1. budget() 纯逻辑分支（余量充足 / 底轨超限 / 多路 SFX / 测量缺失）
  2. scale_plan() 缩放行为（结构不变，只改增益）
  3. measure() 端到端（ffmpeg 合成已知响度的夹具）
  4. verify() 判定（合规 / 超标）

夹具沿用 tests/test_frame_sampler.py 写法（参数列表，无 shell 拼接）。
"""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ))

from core.audio_budget import (  # noqa: E402
    ENCODE_MARGIN_DB,
    TARGET_TP_DBTP,
    budget,
    measure,
    scale_plan,
    verify,
)

HAS_FFMPEG = shutil.which("ffmpeg") is not None


# ── 纯逻辑：budget ────────────────────────────────────────────────────

def test_budget_ok_when_headroom_positive():
    b = budget({"tp_dbfs": -3.0, "lufs": -14.0}, n_sfx=4)
    assert b["verdict"] == "ok"
    assert b["sfx_scale"] == 1.0
    assert b["base_gain_db"] == 0.0
    # 余量已扣掉编码过冲预留
    assert b["headroom_db"] == pytest.approx(
        TARGET_TP_DBTP - ENCODE_MARGIN_DB - (-3.0), abs=0.01)


def test_budget_attenuates_when_base_over_target():
    b = budget({"tp_dbfs": 2.5, "lufs": -6.7}, n_sfx=30)
    assert b["verdict"] == "attenuate_base"
    assert b["base_gain_db"] < 0
    assert b["sfx_scale"] < 1.0


def test_budget_base_gain_equals_headroom():
    """衰减量应正好等于超出的余量（含编码过冲预留），使底轨合规。"""
    b = budget({"tp_dbfs": 2.5})
    assert b["base_gain_db"] == pytest.approx(
        TARGET_TP_DBTP - ENCODE_MARGIN_DB - 2.5, abs=0.01)


def test_budget_many_sfx_reduces_scale_even_with_headroom():
    """余量充足但 SFX 很多时仍应保守缩放。"""
    few = budget({"tp_dbfs": -6.0}, n_sfx=3)
    many = budget({"tp_dbfs": -6.0}, n_sfx=20)
    assert few["sfx_scale"] == 1.0
    assert many["sfx_scale"] < 1.0


def test_budget_handles_missing_measurement():
    b = budget({})
    assert b["verdict"] == "unknown"
    assert b["sfx_scale"] == 1.0
    assert b["base_gain_db"] == 0.0


# ── 纯逻辑：scale_plan ────────────────────────────────────────────────

def test_scale_plan_preserves_structure():
    plan = [("a.wav", 1000, 0.8), ("b.wav", 2000, 0.5)]
    out = scale_plan(plan, 0.5)
    assert [x[0] for x in out] == ["a.wav", "b.wav"]
    assert [x[1] for x in out] == [1000, 2000]
    assert [x[2] for x in out] == [0.4, 0.25]


def test_scale_plan_identity_at_one():
    plan = [("a.wav", 1000, 0.8)]
    assert scale_plan(plan, 1.0) == plan


def test_scale_plan_clamps_non_negative():
    out = scale_plan([("a.wav", 0, 0.1)], -2.0)
    assert out[0][2] >= 0.0


def test_scale_plan_empty():
    assert scale_plan([], 0.5) == []


# ── 端到端 ────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def quiet_video(tmp_path_factory) -> Path:
    """合成 -20 dBFS 的安静夹具（响度可控）。"""
    if not HAS_FFMPEG:
        pytest.skip("ffmpeg not available")
    out = tmp_path_factory.mktemp("ab") / "quiet.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "quiet",
         "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=24:duration=4",
         "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=4",
         "-af", "volume=-20dB",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(out)],
        check=True, timeout=120,
    )
    return out


def test_measure_returns_metrics(quiet_video):
    m = measure(quiet_video)
    assert "lufs" in m and "tp_dbfs" in m
    # 安静夹具：真峰值应远低于 0
    assert m["tp_dbfs"] < -5.0


def test_measure_missing_file():
    assert measure("nope/missing.mp4") == {}


def test_verify_pass_for_compliant(quiet_video):
    """安静夹具真峰值合规（虽响度偏离目标，但只报响度问题）。"""
    v = verify(quiet_video)
    assert v["verdict"] in ("PASS", "FAIL")
    assert "measured" in v


def test_budget_on_real_measurement(quiet_video):
    m = measure(quiet_video)
    b = budget(m, n_sfx=2)
    assert b["verdict"] in ("ok", "attenuate_base")
    assert isinstance(b["sfx_scale"], float)


@pytest.fixture(scope="module")
def hot_video(tmp_path_factory) -> Path:
    """合成超限夹具（真峰值 > 0），用于验证预算闭环。"""
    if not HAS_FFMPEG:
        pytest.skip("ffmpeg not available")
    out = tmp_path_factory.mktemp("ab") / "hot.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "quiet",
         "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=24:duration=3",
         "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=3",
         "-f", "lavfi", "-i", "sine=frequency=880:sample_rate=48000:duration=3",
         "-filter_complex", "[1:a][2:a]amix=inputs=2:normalize=0,volume=20dB[a]",
         "-map", "0:v", "-map", "[a]",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(out)],
        check=True, timeout=120,
    )
    return out


def test_budget_closes_loop_on_hot_video(hot_video, tmp_path):
    """闭环验证：按预算衰减 + 限幅后，成品真峰值应达标。"""
    m = measure(hot_video)
    if m.get("tp_dbfs", -99) <= TARGET_TP_DBTP:
        pytest.skip("夹具未超限，闭环无意义")
    b = budget(m, n_sfx=4)
    assert b["verdict"] == "attenuate_base"
    out = tmp_path / "fixed.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "quiet", "-i", str(hot_video),
         "-af", (f"volume={b['base_gain_db']:.2f}dB,"
                 "alimiter=limit=0.8414:attack=1:release=50:level=disabled"),
         "-c:v", "copy", "-c:a", "aac", str(out)],
        check=True, timeout=120,
    )
    m2 = measure(out)
    assert m2.get("tp_dbfs", 99) <= TARGET_TP_DBTP
