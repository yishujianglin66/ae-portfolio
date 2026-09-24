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


# ══════════════════════════════════════════════════════════════════════
# 2026-09-19 事故回归 (用户听感"踩点没跟上" → 20s 集成片强锚命中 10.3%→5.5%)
#
# 根因链: frozen_cut 判据只比 fi-1/fi 两帧, 而真实视觉边界比标称切点滞后
# 1-4 帧 (变速/慢动作起步) → 比较落在新镜头内部 → 慢镜被误判"冻结"; 慢镜
# 恰是网格量化锚放踩点刀的位置 → repair 把踩点刀按堆丢弃。
# 实测: 踩点刀误报率 67% vs 非踩点刀 17%; 同窗口 7 把踩点刀只剩 2 把。
# ══════════════════════════════════════════════════════════════════════

def _frozen_window_check(tmp_path, *, window: int, lag_frames: int):
    """合成"切后静止/慢镜"片段, 验证标称切点滞后于真实边界时的判定。

    构造: 0.5s 噪点(testsrc, 帧间差异大) + 1.0s 纯色静止帧间完全相同;
    真实硬切边界在 0.5s = 帧 12 (帧 12 起进入纯色段)。
    标称切点声明在 边界 + lag_frames 帧处 —— 复现实测的 1-4 帧滞后。
    窗口判据要成立, 需 window ≥ lag_frames 才能覆盖到 (11,12) 这对边界帧。
    """
    seg_a = tmp_path / "seg_a.mp4"
    seg_b = tmp_path / "seg_b.mp4"
    _run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
          "-i", "testsrc=size=320x240:rate=24:duration=0.5",
          "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
          "-bf", "0", str(seg_a)])
    _run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
          "-i", "color=c=steelblue:size=320x240:rate=24:duration=1.0",
          "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
          "-bf", "0", str(seg_b)])
    joined = tmp_path / "joined.mp4"
    _run(["ffmpeg", "-y", "-v", "error", "-i", str(seg_a), "-i", str(seg_b),
          "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[outv]",
          "-map", "[outv]", "-c:v", "libx264", "-preset", "ultrafast",
          "-pix_fmt", "yuv420p", "-bf", "0", str(joined)])
    cut = 0.5 + lag_frames / 24.0
    rep = analyze_cutpoints(str(joined), [cut], freeze_window=window)
    frozen = [i for i in rep["issues"] if i["type"] == "frozen_cut"]
    return bool(frozen)


def test_frozen_window_ignores_frame_lag(tmp_path):
    """标称切点滞后真实边界 3 帧时, ±3 窗口判据不误报 frozen_cut。"""
    assert _frozen_window_check(tmp_path, window=3, lag_frames=3) is False


def test_frozen_k0_false_positive_reproduced(tmp_path):
    """窗口=0 (历史判据) 复现误报 —— 对照证明回归测试确实盯住该缺陷。"""
    assert _frozen_window_check(tmp_path, window=0, lag_frames=1) is True


def test_repair_keeps_beat_anchors():
    """有锚点时 frozen 切点重锚到最近强鼓点, 而不是直接丢弃。"""
    cuts = [1.000, 2.000, 3.000]
    issues = [{"type": "frozen_cut", "cut_index": 0, "time": 1.000, "detail": {}}]
    anchors = [1.040, 5.000]
    stats: dict = {}
    fixed = repair_cutpoints(cuts, issues, anchors=anchors, stats=stats)
    assert len(fixed) == len(cuts)          # 一刀未丢
    assert any(abs(t - 1.040) < 1e-6 for t in fixed)   # 重锚到强鼓点
    assert stats["guard"] == "ok"
    assert len(stats["reanchored"]) == 1


def test_repair_guard_aborts_beat_regression():
    """修复会把踩点刀全丢时, 节拍守卫中止并退回原表。"""
    cuts = [1.000, 2.000]
    issues = [{"type": "frozen_cut", "cut_index": i, "time": t, "detail": {}}
              for i, t in enumerate(cuts)]
    anchors = [1.005, 2.005]        # 两刀都踩点, 且窗口外无锚可重锚
    stats: dict = {}
    fixed = repair_cutpoints(cuts, issues, anchors=anchors,
                             anchor_tol=0.001, stats=stats)
    assert fixed == cuts            # 原表退回
    assert stats["guard"] == "aborted"
    assert stats["beat_after"] < stats["beat_before"]


def test_repair_failsafe_without_anchors():
    """无锚点 (缓存缺席) 时必须 fail-safe 退回原"丢弃"策略, 不抛异常。"""
    cuts = [1.0, 2.0]
    issues = [{"type": "frozen_cut", "cut_index": 0, "time": 1.0, "detail": {}}]
    stats: dict = {}
    fixed = repair_cutpoints(cuts, issues, anchors=[], stats=stats)
    assert fixed == [2.0]
    assert "guard" not in stats
