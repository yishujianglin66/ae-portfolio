"""test_edl_regression.py — P0 确定性渲染框架单测 (EDL + 帧哈希回归)

验证 (2026-09-09, 依据 03-阶段报告/四竞品深度调研与集成适配分析_2026-09-09.md §5.2):
  1. EDL 构建: production_report → cuts/cut_points/inputs 完整
  2. EDL lint: 缺文件/重叠切点/负 source_start/时长不符 → 对应 L 码错误
  3. 帧哈希确定性: 同一视频两次解码 → 哈希完全一致
  4. 自比对: 视频对自身基线 → PASS 且 0 漂移帧
  5. 漂移检出: 亮度扰动重编码后 → FAIL 且漂移帧比例显著
  6. 结构变化: 帧数变化 → FAIL (structural_change)
  7. CLI: baseline/compare 子命令退出码正确

真实产物验证: ffmpeg lavfi 合成 testsrc 视频夹具 (非 mock)。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from scripts.edl import build_edl, lint_edl, save_edl, EDL_SCHEMA_VERSION  # noqa: E402
from scripts.render_regression import (  # noqa: E402
    compare_to_baseline,
    make_baseline,
)


# ---------------------------------------------------------------- fixtures

@pytest.fixture(scope="module")
def sample_video(tmp_path_factory):
    """ffmpeg 合成 2s 320x240 测试视频 (含运动, 保证帧间有差异)。"""
    d = tmp_path_factory.mktemp("regression")
    v = d / "src.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error",
         "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=12",
         "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
         str(v)], check=True, capture_output=True, timeout=120)
    return v


@pytest.fixture()
def brightened_video(sample_video, tmp_path):
    """亮度扰动 + 重编码 → 应被检出漂移。"""
    out = tmp_path / "bright.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(sample_video),
         "-vf", "eq=brightness=0.12", "-c:v", "libx264", "-preset",
         "ultrafast", "-pix_fmt", "yuv420p", str(out)],
        check=True, capture_output=True, timeout=120)
    return out


@pytest.fixture()
def shorter_video(tmp_path):
    """帧数不同的视频 → structural_change。"""
    out = tmp_path / "short.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error",
         "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=12",
         "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
         str(out)], check=True, capture_output=True, timeout=120)
    return out


def _make_report(tmp_path, src_file=None):
    """合成最小 production_report.json。"""
    pr = {
        "script": {"segments": [
            {"index": 0, "start_time": 0.0, "end_time": 1.0,
             "source_file": src_file, "source_start": 2.0,
             "speed": 1.0, "transition": "cut", "mood": "intro",
             "energy": 0.2},
            {"index": 1, "start_time": 1.0, "end_time": 2.5,
             "source_file": src_file, "source_start": 5.0,
             "speed": 0.8, "transition": "cut", "mood": "build",
             "energy": 0.5},
        ]}
    }
    p = tmp_path / "production_report.json"
    p.write_text(json.dumps(pr), encoding="utf-8")
    return p


# ---------------------------------------------------------------- EDL tests

def test_edl_build_cuts_and_cut_points(tmp_path, sample_video):
    pr = _make_report(tmp_path, str(sample_video))
    edl = build_edl(pr, bgm_path=None, sources=[str(sample_video)],
                    style="amv_highenergy", duration=2.5)
    assert len(edl["cuts"]) == 2
    assert edl["cut_points"] == [1.0]          # 第二段起点即切点
    assert edl["render"]["style"] == "amv_highenergy"
    assert edl["render"]["duration"] == 2.5
    assert edl["schema_version"] == EDL_SCHEMA_VERSION  # 版本无关(1.0→1.1 升级不再硬断言)
    # 素材哈希: unique 去重后只 1 个 input
    assert len(edl["inputs"]) == 1
    assert edl["inputs"][0]["sha1"] and len(edl["inputs"][0]["sha1"]) == 40
    assert "ffmpeg" in edl["toolchain"]
    # 落盘可读回
    saved = save_edl(edl, tmp_path / "edl.json")
    back = json.loads(saved.read_text(encoding="utf-8"))
    assert back["cuts"] == edl["cuts"]


def test_edl_lint_pass(tmp_path, sample_video):
    pr = _make_report(tmp_path, str(sample_video))
    edl = build_edl(pr, sources=[str(sample_video)], duration=2.5)
    assert lint_edl(edl) == []


def test_edl_lint_catches_missing_file(tmp_path):
    pr = _make_report(tmp_path, r"D:\nonexistent\ghost.mp4")
    edl = build_edl(pr, duration=2.5)
    errs = lint_edl(edl)
    assert any(e.startswith("L2") or e.startswith("L4") for e in errs)


def test_edl_lint_catches_overlap(tmp_path, sample_video):
    pr = _make_report(tmp_path, str(sample_video))
    edl = build_edl(pr, sources=[str(sample_video)], duration=2.5)
    # 人为制造重叠
    edl["cuts"][1]["start_time"] = 0.5
    errs = lint_edl(edl)
    assert any(e.startswith("L3") for e in errs)


def test_edl_lint_catches_duration_mismatch(tmp_path, sample_video):
    pr = _make_report(tmp_path, str(sample_video))
    edl = build_edl(pr, sources=[str(sample_video)], duration=99.0)
    errs = lint_edl(edl)
    assert any(e.startswith("L5") for e in errs)


def test_edl_lint_catches_negative_source_start(tmp_path, sample_video):
    pr = _make_report(tmp_path, str(sample_video))
    edl = build_edl(pr, sources=[str(sample_video)], duration=2.5)
    edl["cuts"][0]["source_start"] = -1
    errs = lint_edl(edl)
    assert any(e.startswith("L6") for e in errs)


# ------------------------------------------------------- frame-hash tests

def test_frame_hash_determinism(sample_video):
    """同一文件两次解码 → 哈希序列完全一致 (确定性前提)。"""
    b1 = make_baseline(sample_video)
    b2 = make_baseline(sample_video)
    assert b1["hashes"] == b2["hashes"]
    assert b1["frame_count"] == b2["frame_count"] > 0


def test_compare_self_pass_zero_drift(sample_video):
    b = make_baseline(sample_video)
    rep = compare_to_baseline(sample_video, b)
    assert rep["verdict"] == "PASS"
    assert rep["flagged_frames"] == 0
    assert rep["max_distance"] == 0


def test_compare_brightness_drift_fail(sample_video, brightened_video):
    b = make_baseline(sample_video)
    rep = compare_to_baseline(brightened_video, b)
    assert rep["verdict"] == "FAIL"
    assert rep["reason"] == "frame_drift"
    assert rep["flagged_frames"] > 0
    assert rep["flag_ratio"] > 0.02


def test_compare_structural_change_fail(sample_video, shorter_video):
    b = make_baseline(sample_video)
    rep = compare_to_baseline(shorter_video, b)
    assert rep["verdict"] == "FAIL"
    assert rep["reason"] == "structural_change"


# ----------------------------------------------------------------- CLI tests

def test_cli_baseline_and_compare(sample_video, tmp_path):
    base = tmp_path / "base.json"
    r1 = subprocess.run([sys.executable, str(PROJECT / "scripts" /
                        "render_regression.py"),
                         "baseline", str(sample_video), str(base)],
                        capture_output=True, text=True, timeout=300)
    assert r1.returncode == 0 and base.exists()
    r2 = subprocess.run([sys.executable, str(PROJECT / "scripts" /
                        "render_regression.py"),
                         "compare", str(sample_video), str(base)],
                        capture_output=True, text=True, encoding="utf-8",
                        errors="replace", timeout=300)
    assert r2.returncode == 0 and "PASS" in r2.stdout


def test_cli_compare_fail_exit_code(sample_video, brightened_video, tmp_path):
    base = tmp_path / "base.json"
    subprocess.run([sys.executable, str(PROJECT / "scripts" /
                    "render_regression.py"),
                    "baseline", str(sample_video), str(base)],
                    capture_output=True, timeout=300)
    r = subprocess.run([sys.executable, str(PROJECT / "scripts" /
                       "render_regression.py"),
                       "compare", str(brightened_video), str(base)],
                      capture_output=True, text=True, encoding="utf-8",
                      errors="replace", timeout=300)
    assert r.returncode == 1 and "FAIL" in r.stdout
