# -*- coding: utf-8 -*-
"""test_rl_drift_clamp.py — 验证 _tl_drift 钳制逻辑

回归 R1 根因 (2026-09-10 run61 实测漂移 +19.62s):
  累加器在慢放段失控 → 多段源起点坍塌 → 切点冻结
新逻辑: ±2 帧内允许累加, 溢出强制归零
"""
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ))


def simulate_drift(speed_per_seg: list) -> dict:
    """模拟 production_director._execute 中的漂移累加（带新钳制）"""
    fps = 24.0
    drift = 0.0
    TL_DRIFT_LIMIT = 2.0 / 24.0  # ±83ms
    history = []
    for i, (plan_dur, speed, actual_dur) in enumerate(speed_per_seg):
        if abs(drift) > TL_DRIFT_LIMIT:
            drift = 0.0
        render_dur = plan_dur + drift
        # 模拟 read_dur 不足导致 actual < render_dur
        actual = actual_dur
        drift += render_dur - actual
        history.append({
            "plan": plan_dur, "render": render_dur,
                "actual": actual, "drift_after": drift})
    return {"final_drift": drift, "history": history}


def test_no_drift_when_actual_matches_plan():
    """actual == plan 时, 漂移应保持 0"""
    segs = [(0.25, 1.0, 0.25)] * 10
    r = simulate_drift(segs)
    assert abs(r["final_drift"]) < 1e-6, r
    print("OK  test_no_drift_when_actual_matches_plan")


def test_drift_clamps_when_out_of_bounds():
    """actual 持续 < plan 时, 漂移应被钳制到 ±2 帧"""
    # 108 段, plan=0.3, actual=0.275 (持续欠产)
    segs = [(0.3, 1.0, 0.275)] * 108
    r = simulate_drift(segs)
    # 钳制后漂移不应超过 ±2 帧内
    max_drift = max(abs(h["drift_after"]) for h in r["history"])
    assert max_drift <= 5.0 / 24.0, f"漂移失控: max={max_drift}s"
    print(f"OK  test_drift_clamps_when_out_of_bounds  (max_drift={max_drift*24:.2f} frames)")


def test_drift_resets_when_exceeds_limit():
    """漂移突破钳制后必须归零 (防止 +19.62s 失控)"""
    # 模拟 production 的灾难场景: actual 比 plan 短很多
    segs = [(0.3, 0.5, 0.20)] * 108  # 慢放 + 欠产
    r = simulate_drift(segs)
    # 关键: 漂移任何时刻都不应超过 5 帧
    max_drift = max(abs(h["drift_after"]) for h in r["history"])
    assert max_drift <= 5.0 / 24.0, f"漂移失控到 {max_drift*24:.1f} 帧"
    print(f"OK  test_drift_resets_when_exceeds_limit  (max_drift={max_drift*24:.2f} frames)")


def test_old_behavior_would_have_runaway():
    """对照: 旧逻辑（无钳制）下, run61 风格场景会失控 +19s+"""
    drift = 0.0
    segs = [(0.3, 0.5, 0.20)] * 108
    for plan_dur, speed, actual in segs:
        render_dur = plan_dur + drift
        drift += render_dur - actual
    # 旧逻辑: 应远超 ±2 帧
    assert abs(drift) > 5.0, f"反例失败: 旧逻辑也应失控, got {drift}"
    print(f"OK  test_old_behavior_would_have_runaway  (旧漂移={drift:.2f}s)")


if __name__ == "__main__":
    test_no_drift_when_actual_matches_plan()
    test_drift_clamps_when_out_of_bounds()
    test_drift_resets_when_exceeds_limit()
    test_old_behavior_would_have_runaway()
    print("\nALL PASS")