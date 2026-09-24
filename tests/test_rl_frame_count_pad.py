# -*- coding: utf-8 -*-
"""R1 第五类根因单测: 超短片段渲染丢帧 → 时间线累积前移 → 切点落进段内部。

背景
----
r1_fixed_v5 逐 clip 比对：

    seg57  计划 5 帧 → 实际 2 帧   (−3)
    seg40  计划 6 帧 → 实际 4 帧   (−2)
    seg52  计划 6 帧 → 实际 5 帧   (−1)
    seg38  计划 5 帧 → 实际 4 帧   (−1)
    seg43  计划 5 帧 → 实际 4 帧   (−1)

片段比计划短 → 时间线整体前移 → EDL 声明的切点时刻落进**相邻片段内部**
→ 前后帧同源 → 切点消失。段内运动诊断佐证：段内 ahash 峰值 28~43（画面在动），
切点处 0~2（没跳变）。

`_tl_drift` 被钳制在 ±2 帧后**无法补偿**这种累积短帧（钳制防住了失控，
也挡住了补偿），故改为在源头补齐：`_ensure_frame_count` 用 tpad 克隆末帧。
"""

import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FPS = 24


def _director():
    """绕开重型 __init__，只装 ffmpeg/ffprobe 句柄。"""
    from ai.production_director import ProductionDirector
    d = ProductionDirector.__new__(ProductionDirector)
    d.ffmpeg = "ffmpeg"
    d.ffprobe = "ffprobe"
    return d


def _mk_clip(path, frames, fps=FPS):
    """生成指定帧数的短片。"""
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
         f"testsrc=size=64x64:rate={fps}:duration={frames / fps:.4f}",
         "-frames:v", str(frames), "-c:v", "libx264", "-preset", "ultrafast",
         "-pix_fmt", "yuv420p", str(path)],
        check=True, capture_output=True, timeout=120,
    )
    return path


def _count(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v",
         "-show_entries", "stream=nb_read_frames", "-of",
         "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, timeout=120)
    return int(r.stdout.strip().splitlines()[0])


def _has_b_frames(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v",
         "-show_entries", "stream=has_b_frames", "-of",
         "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, timeout=60)
    return int(r.stdout.strip().splitlines()[0] or 0)


# ── 1. 帧数探测 ────────────────────────────────────────────────────

def test_probe_frame_count_accurate():
    d = _director()
    with tempfile.TemporaryDirectory() as td:
        p = _mk_clip(os.path.join(td, "a.mp4"), 5)
        assert d._probe_frame_count(p) == 5


def test_probe_frame_count_returns_negative_on_missing_file():
    d = _director()
    assert d._probe_frame_count(os.path.join(tempfile.gettempdir(),
                                             "_nope_xyz.mp4")) == -1


# ── 2. 补帧行为 ────────────────────────────────────────────────────

def test_no_pad_when_already_enough():
    d = _director()
    with tempfile.TemporaryDirectory() as td:
        p = _mk_clip(os.path.join(td, "a.mp4"), 5)
        assert d._ensure_frame_count(p, 3, FPS) == 0
        assert _count(p) == 5          # 不缩短、不动文件


def test_pad_short_clip_to_target():
    d = _director()
    with tempfile.TemporaryDirectory() as td:
        p = _mk_clip(os.path.join(td, "a.mp4"), 2)   # 复现 seg57 的 5→2
        assert d._ensure_frame_count(p, 5, FPS) == 3
        assert _count(p) == 5


def test_pad_keeps_no_b_frames_for_clean_concat():
    """补帧后必须仍是无 B 帧，否则 concat 流拷贝边界会复制帧。"""
    d = _director()
    with tempfile.TemporaryDirectory() as td:
        p = _mk_clip(os.path.join(td, "a.mp4"), 2)
        d._ensure_frame_count(p, 5, FPS)
        assert _has_b_frames(p) == 0


def test_pad_leaves_no_temp_file():
    d = _director()
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "a.mp4")
        _mk_clip(p, 2)
        d._ensure_frame_count(p, 5, FPS)
        assert not os.path.exists(p + ".pad.mp4")
        assert sorted(os.listdir(td)) == ["a.mp4"]


# ── 3. 时间线漂移仿真（核心）──────────────────────────────────────

def _simulate(plan_frames, actual_frames, pad):
    """返回每个切点的边界误差（帧）。pad=True 时补到计划帧数。"""
    d = _director()
    drift, errs = 0, []
    with tempfile.TemporaryDirectory() as td:
        for i, (want, got) in enumerate(zip(plan_frames, actual_frames)):
            p = os.path.join(td, f"c{i}.mp4")
            _mk_clip(p, got)
            if pad:
                d._ensure_frame_count(p, want, FPS)
            real = _count(p)
            drift += real - want
            errs.append(drift)
    return errs


def test_without_pad_timeline_drifts():
    """不补帧：切点边界逐步偏离计划（负=时间线前移）。"""
    plan = [5, 6, 5, 5, 6, 5]
    actual = [5, 4, 5, 2, 4, 5]          # 复现实测丢帧
    errs = _simulate(plan, actual, pad=False)
    # 计划 32 帧 vs 实际 25 帧 → 累计前移 7 帧（≈0.29s）
    assert errs[-1] == -7, errs
    # 前移 5 帧 > 钳制上限 2 帧 → drift 补偿不了
    assert abs(errs[-1]) > 2


def test_with_pad_timeline_locked():
    """补帧后：每个切点边界都精确等于计划，零漂移。"""
    plan = [5, 6, 5, 5, 6, 5]
    actual = [5, 4, 5, 2, 4, 5]
    errs = _simulate(plan, actual, pad=True)
    assert errs[-1] == 0, errs
    assert all(e == 0 for e in errs)


def test_pad_is_idempotent():
    """重复补帧不会让帧数越补越多。"""
    d = _director()
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "a.mp4")
        _mk_clip(p, 2)
        d._ensure_frame_count(p, 5, FPS)
        assert d._ensure_frame_count(p, 5, FPS) == 0
        assert _count(p) == 5


# ══════════════════════════════════════════════════════════════════════
# 2026-09-19 事故回归: 27s 集成片视频流 25.33s (短 40 帧 ≈ 1.67s), 画面比
# 音乐提前结束。定位过程见 production_director 的 [帧数核对]/[段级对账]:
#   ① 速度曲线段把段落拆成 2-3 个子片段, 各子片段按 round(子段时长×fps)
#      独立取整 → 21 个曲线段累积少 40 帧 (缺口主要来源)
#   ② 漂移累加器的亚帧级系统偏差逐段累积 → 再少 11 帧
# 修法: 子片段帧数由边界帧号差分得出 (帧级守恒) + 段级对账在段末片段补齐。
# ══════════════════════════════════════════════════════════════════════

def test_reconcile_pads_only_segment_tail():
    """段内缺口补在段末片段, 段间切点与后续段不受影响。"""
    from types import SimpleNamespace
    d = _director()
    with tempfile.TemporaryDirectory() as td:
        a = _mk_clip(os.path.join(td, "s1a.mp4"), 3)
        b = _mk_clip(os.path.join(td, "s1b.mp4"), 2)
        c = _mk_clip(os.path.join(td, "s2.mp4"), 12)
        clips = [(a, SimpleNamespace(index=1, duration=0.25)),   # 计划 6
                 (b, SimpleNamespace(index=1, duration=0.25)),
                 (c, SimpleNamespace(index=2, duration=0.5))]    # 计划 12
        rec = d._reconcile_segment_frames(clips, FPS)
        assert rec["pads"] == 1 and rec["trims"] == []
        assert _count(a) == 3          # 段内首片段不动
        assert _count(b) == 3          # 段末片段 +1 → 该段回到 6 帧计划
        assert _count(c) == 12         # 下一段不受影响


def test_reconcile_reports_oversize_segment():
    """段落超长只记录不减帧 (_ensure_frame_count 只支持补帧)。"""
    from types import SimpleNamespace
    d = _director()
    with tempfile.TemporaryDirectory() as td:
        a = _mk_clip(os.path.join(td, "s1.mp4"), 8)
        rec = d._reconcile_segment_frames(
            [(a, SimpleNamespace(index=1, duration=0.25))], FPS)   # 计划 6
        assert rec["pads"] == 0
        assert rec["trims"] and rec["trims"][0][1] == -2


def test_reconcile_conserves_total_frames():
    """对账后总帧数 == Σ round(段时长×fps)。"""
    from types import SimpleNamespace
    d = _director()
    with tempfile.TemporaryDirectory() as td:
        specs = [(1, 0.25, [3, 2]), (2, 0.5, [12]), (3, 0.375, [4, 3, 2])]
        clips = []
        for idx, dur, fr in specs:
            for j, n in enumerate(fr):
                p = _mk_clip(os.path.join(td, f"s{idx}_{j}.mp4"), n)
                clips.append((p, SimpleNamespace(index=idx, duration=dur)))
        d._reconcile_segment_frames(clips, FPS)
        plan = sum(max(2, round(dur * FPS)) for _, dur, _ in specs)
        got = sum(_count(p) for p, _ in clips)
        assert got == plan, f"{got} != {plan}"
