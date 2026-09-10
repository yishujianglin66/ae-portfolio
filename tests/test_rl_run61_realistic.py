# -*- coding: utf-8 -*-
"""test_rl_run61_realistic.py — 用真实 run61 EDL 模拟漂移累加

108 段实际 speed 分布 + 时长，验证 _TL_DRIFT_LIMIT 在真实场景下能控住漂移。
"""
import json
import sys
from pathlib import Path

import pytest

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ))


def load_run61_segs():
    edl = json.loads((PROJ / "output/unified_run61/edl.json").read_text(encoding="utf-8"))
    return [(float(s["end_time"]) - float(s["start_time"]), float(s["speed"]))
            for s in edl["cuts"]]


def simulate_segs(segs, with_clamp: bool = True) -> dict:
    """模拟 _execute 累加, return 最大漂移与最终漂移"""
    fps = 24.0
    TL_DRIFT_LIMIT = 2.0 / 24.0
    drift = 0.0
    history = []
    for plan_dur, speed in segs:
        if with_clamp and abs(drift) > TL_DRIFT_LIMIT:
            drift = 0.0
        render_dur = plan_dur + drift
        read_dur = plan_dur * max(0.25, min(4.0, speed))
        actual_dur = read_dur + 1.0 / 24.0 * 0.5  # ±0.5 帧 jitter
        actual_dur = min(actual_dur, plan_dur)
        drift += render_dur - actual_dur
        history.append(drift)
    return {"max_drift": max(abs(d) for d in history),
            "final_drift": drift,
            "max_drift_at": history.index(max(history, key=abs))}


def test_run61_old_logic_runaway():
    """108 段真实 EDL 旧逻辑失控 (>10s)"""
    segs = load_run61_segs()
    assert len(segs) >= 100, f"应至少 100 段, got {len(segs)}"
    r_old = simulate_segs(segs, with_clamp=False)
    assert r_old["final_drift"] > 10.0, \
        f"旧逻辑应失控, got {r_old['final_drift']:.2f}s"
    print(f"  旧逻辑: final_drift={r_old['final_drift']:.2e}s")


def test_run61_new_logic_clamp():
    """108 段真实 EDL 新逻辑钳制 (<8 帧 ≈ ±250ms)"""
    segs = load_run61_segs()
    r_new = simulate_segs(segs, with_clamp=True)
    assert r_new["max_drift"] * 24 < 8.0, \
        f"新逻辑漂移过大: {r_new['max_drift']*24:.2f} 帧"
    print(f"  新逻辑: max_drift={r_new['max_drift']*24:.2f} 帧, "
          f"final={r_new['final_drift']*24:.2f} 帧")


def test_run61_speed_distribution():
    """统计 speed 分布作为 fix 适用范围的依据"""
    segs = load_run61_segs()
    speeds = [s for _, s in segs]
    slow = sum(1 for s in speeds if s < 1)
    fast = sum(1 for s in speeds if s > 1)
    print(f"  段数 {len(segs)}: 慢放 {slow}, 恒速 {len(segs)-slow-fast}, 加速 {fast}")
    assert slow > 0, "应有不少慢放段 (这是 bug 的温床)"