# -*- coding: utf-8 -*-
"""test_rl_run61_realistic.py — 用真实 run61 EDL 模拟漂移累加

108 段实际 speed 分布 + 时长，验证 _TL_DRIFT_LIMIT 在真实场景下能控住漂移。

⚠️ 2026-09-24：本文件依赖的历史构建产物 **`output/unified_run61/edl.json` 已被清理**
（该产物从未入版本库）。产物不在时本文件**显式跳过**（跳因里写明缺什么），不再硬失败 ——
原先它会在全量回归里直接 FileNotFoundError，使"代码没改却全量变红"。

真实分布的等价不变量检验已迁到 **`tests/test_rl_real_distribution.py`**（用密封夹具
`tests/fixtures/real_run_segment_distribution_v9.json`，不依赖 output/）。
本文件保留：若 run61 产物被重新生成，它会自动恢复运行。
"""
import sys
from pathlib import Path

import pytest

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ))
sys.path.insert(0, str(Path(__file__).resolve().parent))   # 便于 import rl_drift_sim

from rl_drift_sim import load_segs_from_edl, simulate_segs  # noqa: E402

RUN61_EDL = PROJ / "output" / "unified_run61" / "edl.json"

pytestmark = pytest.mark.skipif(
    not RUN61_EDL.exists(),
    reason=(
        f"缺历史构建产物 {RUN61_EDL}（未入版本库，已被产物治理清理）。"
        "真实分布的等价检验见 tests/test_rl_real_distribution.py"
    ),
)


def load_run61_segs():
    return load_segs_from_edl(RUN61_EDL)


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
