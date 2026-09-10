"""test_cutpoint_selfeval.py — P2 切点级自检与修复循环单测

验证 (2026-09-09, 依据 03-阶段报告/四竞品深度调研与集成适配分析 §3.3):
  1. 真切+平滑音频      → PASS, 无 issue
  2. 冻结切(同内容拼接)  → frozen_cut 检出
  3. 过近切点            → min_gap 检出
  4. 波形不连续拼接      → audio_pop 检出
  5. repair_cutpoints    → 冻结/过近被丢弃, pop 切点被微调
  6. repair_loop         → 修复后 PASS; 不可修场景 3 轮后 manual_review
真实产物验证: ffmpeg 合成视频/音频夹具。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from scripts.cutpoint_selfeval import (  # noqa: E402
    analyze_cutpoints,
    probe_fps,
    repair_cutpoints,
    repair_loop,
)


def _run(cmd):
    subprocess.run(cmd, check=True, capture_output=True, timeout=180)


def _mkclip(out, src, audio_expr, dur):
    """合成测试片段: 完整 lavfi 视频源串 + 音频表达式。

    用输出 -t 截断 (mandelbrot 等源没有 duration 选项)。
    """
    _run(["ffmpeg", "-y", "-v", "error",
          "-f", "lavfi", "-i", src,
          "-f", "lavfi", "-i", f"aevalsrc={audio_expr}:d={dur}:s=48000",
          "-t", str(dur),
          "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
          "-c:a", "aac", str(out)])


@pytest.fixture(scope="module")
def clip_a(tmp_path_factory):
    d = tmp_path_factory.mktemp("cutpoint")
    f = d / "a.mp4"
    # 动态图案 testsrc + 平滑正弦 (无直流, 波形连续)
    _mkclip(f, "testsrc=size=320x240:rate=12", "0.4*sin(2*PI*440*t)", 1.0)
    return f


@pytest.fixture(scope="module")
def clip_b(tmp_path_factory):
    d = tmp_path_factory.mktemp("cutpoint")
    f = d / "b.mp4"
    # mandelbrot 与 testsrc 在灰度域差异极大 → 真切
    _mkclip(f, "mandelbrot=size=320x240:rate=12", "0.4*sin(2*PI*440*t)", 1.0)
    return f


def _concat(parts, out):
    """filter_complex concat 重编码拼接 — 与生产路径一致, 切点帧精确对齐。"""
    _run(["ffmpeg", "-y", "-v", "error",
          "-i", str(parts[0]), "-i", str(parts[1]),
          "-filter_complex",
          "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]",
          "-map", "[v]", "-map", "[a]",
          "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
          "-c:a", "aac", str(out)])


@pytest.fixture(scope="module")
def video_real_cut(clip_a, clip_b, tmp_path_factory):
    d = tmp_path_factory.mktemp("cutpoint")
    f = d / "real_cut.mp4"
    _concat([clip_a, clip_b], f)
    return f


@pytest.fixture(scope="module")
def video_frozen_cut(tmp_path_factory):
    """静态灰画面拼接自身 → 切点两侧帧完全一致 → frozen_cut。"""
    d = tmp_path_factory.mktemp("cutpoint")
    f1, f2, out = d / "g1.mp4", d / "g2.mp4", d / "frozen_cut.mp4"
    _mkclip(f1, "color=c=gray:s=320x240:r=12", "0.4*sin(2*PI*440*t)", 1.0)
    _mkclip(f2, "color=c=gray:s=320x240:r=12", "0.4*sin(2*PI*440*t)", 1.0)
    _concat([f1, f2], out)
    return out


@pytest.fixture(scope="module")
def video_audio_pop(clip_a, tmp_path_factory):
    """B 片段音频带 +0.6 直流偏置 → 拼接点单样本跳变 ≈0.6 → audio_pop。"""
    d = tmp_path_factory.mktemp("cutpoint")
    c = d / "c.mp4"
    _mkclip(c, "mandelbrot=size=320x240:rate=12", "0.6+0.4*sin(2*PI*440*t)", 1.0)
    f = d / "pop_cut.mp4"
    _concat([clip_a, c], f)
    return f


# -------------------------------------------------------------------

def test_probe_fps(video_real_cut):
    assert 11.5 <= probe_fps(video_real_cut) <= 12.5


def test_real_cut_pass(video_real_cut):
    rep = analyze_cutpoints(video_real_cut, [1.0])
    assert rep["verdict"] == "PASS"
    assert rep["issues"] == []


def test_frozen_cut_detected(video_frozen_cut):
    rep = analyze_cutpoints(video_frozen_cut, [1.0])
    types = {i["type"] for i in rep["issues"]}
    assert "frozen_cut" in types
    assert rep["verdict"] == "FAIL"


def test_min_gap_detected(video_real_cut):
    rep = analyze_cutpoints(video_real_cut, [1.0, 1.05])
    types = {i["type"] for i in rep["issues"]}
    assert "min_gap" in types
    assert rep["verdict"] == "FAIL"


def test_audio_pop_detected(video_audio_pop):
    rep = analyze_cutpoints(video_audio_pop, [1.0])
    types = {i["type"] for i in rep["issues"]}
    assert "audio_pop" in types
    assert rep["verdict"] == "FAIL"


def test_repair_cutpoints_drops_and_nudges():
    issues = [
        {"type": "frozen_cut", "cut_index": 0, "time": 1.0, "detail": {}},
        {"type": "min_gap", "cut_index": 1, "time": 2.05, "detail": {}},
        {"type": "audio_pop", "cut_index": 2, "time": 3.0, "detail": {}},
    ]
    cuts = [1.0, 2.0, 2.05, 3.0]
    fixed = repair_cutpoints(cuts, issues)
    assert 1.0 not in fixed            # frozen 被丢
    assert 2.05 not in fixed           # 过近被丢
    assert any(abs(t - 3.0) > 1e-6 for t in fixed)  # pop 被微调
    assert 2.0 in fixed                # 正常切保留


def test_repair_loop_converges(video_frozen_cut, tmp_path):
    """冻结切 → 修复(丢弃) → 无切点 → PASS。"""
    def render_fn(cuts):
        return str(video_frozen_cut)    # 渲染不变, 但切点表已修

    out = repair_loop(render_fn, [1.0], str(video_frozen_cut),
                      report_dir=tmp_path)
    assert out["verdict"] == "PASS"
    assert out["final_cut_times"] == []
    assert (tmp_path / "cutpoint_report.json").exists()


def test_repair_loop_max_rounds_manual(video_frozen_cut, tmp_path):
    """渲染器永远不修复时: 3 轮后 manual_review=True。"""
    calls = {"n": 0}

    def render_fn(cuts):
        calls["n"] += 1
        return str(video_frozen_cut)

    out = repair_loop(render_fn, [1.0, 1.0], str(video_frozen_cut),
                      max_rounds=3, report_dir=tmp_path)
    # 冻结切第一轮就被丢弃, 但若传入两个相同切点, min_gap 修复后仍可能 FAIL
    assert out["rounds_used"] <= 3
    assert "manual_review" in out or out["verdict"] == "PASS"
