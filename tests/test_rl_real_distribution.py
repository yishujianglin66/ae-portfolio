# -*- coding: utf-8 -*-
"""test_rl_real_distribution.py — 用**密封夹具**的真实段分布验证漂移钳制。

来源与理由（2026-09-24）：
  · 原 `tests/test_rl_run61_realistic.py` 依赖 `output/unified_run61/edl.json`
    （历史构建产物，未入版本库）。该产物被产物治理清理删除后，**代码未改而全量回归变红**
    （FileNotFoundError）—— 测试依赖不受管治理的构建产物，是结构性问题。
  · 本文件改用密封夹具 `tests/fixtures/real_run_segment_distribution_v9.json`：
    取自 **真实 run 的 EDL**（unified_integration_27s_v9，94 段，含 44 段慢放），
    入库固定，不再随 output/ 清理而失效。
  · **替代的正当性已实测**：run61 的三条不变量在这份分布上**都成立**
    （旧逻辑仍灾难级失控、新逻辑仍 <8 帧、慢放段仍 >0）——说明这些不变量检验的是
    **缺陷类别**，不依赖那 108 段的具体数值。此处如实标注这是**替代分布**，不冒充 run61。

仿真实现见 `tests/rl_drift_sim.py`（与 run61 测试共用同一份，避免两处漂移）。
"""
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
PROJ = HERE.parent
sys.path.insert(0, str(PROJ))
sys.path.insert(0, str(HERE))

from rl_drift_sim import (  # noqa: E402
    FPS,
    load_segs_from_fixture,
    simulate_segs,
    speed_stats,
)

FIXTURE = HERE / "fixtures" / "real_run_segment_distribution_v9.json"


def test_fixture_exists_and_is_provenanced():
    """夹具必须在库且写明出处 —— 否则"密封"就无从追溯"""
    assert FIXTURE.exists(), f"缺密封夹具 {FIXTURE}"
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    prov = data.get("_provenance", {})
    for key in ("source", "run", "extracted", "why", "segments"):
        assert key in prov, f"夹具缺 _provenance.{key}"
    assert data["segments"], "夹具段列表为空"


def test_real_distribution_has_enough_segments():
    segs = load_segs_from_fixture(FIXTURE)
    assert len(segs) >= 50, f"段数过少({len(segs)})，不足以承载累加检验"


def test_old_logic_runs_away_on_real_distribution():
    """旧逻辑（无钳制）在真实分布上必须失控 —— 这是修复动机本身"""
    segs = load_segs_from_fixture(FIXTURE)
    r = simulate_segs(segs, with_clamp=False)
    assert r["final_drift"] > 10.0, (
        f"旧逻辑应失控（>10s），实测 {r['final_drift']:.2e}s —— "
        f"若不成立，说明夹具分布已失去'能暴露该缺陷'的性质")


def test_clamp_holds_on_real_distribution():
    """新逻辑（有钳制）在真实分布上必须把漂移压住（<8 帧 ≈ ±250ms）"""
    segs = load_segs_from_fixture(FIXTURE)
    r = simulate_segs(segs, with_clamp=True)
    assert r["max_drift"] * FPS < 8.0, (
        f"新逻辑漂移过大: {r['max_drift'] * FPS:.2f} 帧")


def test_clamp_beats_no_clamp_on_same_data():
    """同分布下的对照：钳制必须显著优于不钳制（防"两边都失控也算过"）"""
    segs = load_segs_from_fixture(FIXTURE)
    old = simulate_segs(segs, with_clamp=False)
    new = simulate_segs(segs, with_clamp=True)
    assert new["max_drift"] < old["max_drift"], "钳制后漂移未变小？"


def test_real_distribution_contains_slow_segments():
    """慢放段是该缺陷的温床；分布里必须有"""
    segs = load_segs_from_fixture(FIXTURE)
    st = speed_stats(segs)
    assert st["slow"] > 0, f"分布里没有慢放段: {st}"
    print(f"  真实分布: {st}")
