# -*- coding: utf-8 -*-
"""rl_drift_sim.py — 时间线漂移仿真的**共享实现**（非测试文件，不会被收集）。

为什么单独放一个模块：`tests/test_rl_run61_realistic.py`（依赖历史产物）与
`tests/test_rl_real_distribution.py`（依赖密封夹具）要对**同一套**累加逻辑做检验。
把仿真写在两处会产生漂移风险 —— 一处改了另一处没改，检验就名不副实。

仿真对应 `ai/production_director._execute` 里的漂移累加与 `_TL_DRIFT_LIMIT` 钳制：
    render_dur = plan_dur + drift          # 按"计划时长+当前漂移"渲染
    read_dur   = plan_dur * clamp(speed)   # 实际读到的时长由速度决定
    actual_dur = min(read_dur + jitter, plan_dur)
    drift     += render_dur - actual_dur
钳制策略：`abs(drift) > TL_DRIFT_LIMIT` 时先归零再累加。
"""
from __future__ import annotations

import json
from pathlib import Path

FPS = 24.0
TL_DRIFT_LIMIT = 2.0 / FPS          # ±2 帧


def load_segs_from_edl(path: str | Path) -> list[tuple[float, float]]:
    """从 run 的 edl.json 取 [(时长, 速度), ...]"""
    edl = json.loads(Path(path).read_text(encoding="utf-8"))
    return [(float(s["end_time"]) - float(s["start_time"]), float(s["speed"]))
            for s in edl["cuts"]]


def load_segs_from_fixture(path: str | Path) -> list[tuple[float, float]]:
    """从密封夹具取 [(时长, 速度), ...]（字段格式见夹具 _provenance）"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [(float(d), float(s)) for d, s in data["segments"]]


def simulate_segs(segs: list[tuple[float, float]],
                  with_clamp: bool = True) -> dict:
    """模拟累加，返回最大漂移 / 最终漂移 / 最大漂移发生处"""
    drift = 0.0
    history: list[float] = []
    for plan_dur, speed in segs:
        if with_clamp and abs(drift) > TL_DRIFT_LIMIT:
            drift = 0.0
        render_dur = plan_dur + drift
        read_dur = plan_dur * max(0.25, min(4.0, speed))
        actual_dur = read_dur + 1.0 / FPS * 0.5      # ±0.5 帧 jitter
        actual_dur = min(actual_dur, plan_dur)
        drift += render_dur - actual_dur
        history.append(drift)
    return {
        "max_drift": max(abs(d) for d in history),
        "final_drift": drift,
        "max_drift_at": history.index(max(history, key=abs)),
    }


def speed_stats(segs: list[tuple[float, float]]) -> dict:
    speeds = [s for _, s in segs]
    slow = sum(1 for s in speeds if s < 1)
    fast = sum(1 for s in speeds if s > 1)
    return {"segments": len(segs), "slow": slow, "fast": fast,
            "steady": len(segs) - slow - fast}
