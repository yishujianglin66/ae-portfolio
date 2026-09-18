"""models/beat/rhythm_fusion.py — 双节拍网格调和 (BeatNet ↔ 项目节奏管线)

把 BeatNet 的节拍/下拍网格与项目现有节奏管线 (rhythm_reward + kick/snare)
的输出调和成统一 beatgrid, 输出:
  - 对齐率 (两系统互证强度)
  - 每拍的下拍归属 (继承 BeatNet 的小节编号)
  - tempo 交叉校验结果

设计原则: 融合只"增补标注"不"改动切点" — 项目切点/onset 是既有事实,
BeatNet 只负责给它们补上拍内编号与下拍标记 (卡点三层信号)。

用法:
    from models.beat.rhythm_fusion import fuse_beatgrids
    f = fuse_beatgrids(project_beats, beatnet_result)
    print(f.tempo_delta, f.alignment_rate, f.downbeat_times)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

ALIGN_TOLERANCE_SEC = 0.08   # ±80ms 视为同一拍
TEMPO_TOLERANCE = 0.08       # 8% tempo 偏差内视为一致


@dataclass
class FusionResult:
    """调和结果。"""
    tempo_project: float = 0.0
    tempo_beatnet: float = 0.0
    tempo_delta: float = 0.0            # 相对差 (0-1)
    tempo_consistent: bool = False      # 两系统 tempo 是否一致
    n_project_beats: int = 0
    n_beatnet_beats: int = 0
    n_aligned: int = 0                  # 项目拍中与 BeatNet 对齐的数量
    alignment_rate: float = 0.0         # n_aligned / n_project_beats
    fused_beats: list[dict[str, Any]] = field(default_factory=list)
    downbeat_times: list[float] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tempo_project": self.tempo_project,
            "tempo_beatnet": self.tempo_beatnet,
            "tempo_delta": round(self.tempo_delta, 4),
            "tempo_consistent": self.tempo_consistent,
            "alignment_rate": round(self.alignment_rate, 4),
            "n_aligned": self.n_aligned,
            "n_project_beats": self.n_project_beats,
            "n_beatnet_beats": self.n_beatnet_beats,
            "n_downbeats": len(self.downbeat_times),
        }


def _nearest_beat(beatnet_beats: Sequence[float],
                  beat_numbers: Sequence[int],
                  t: float) -> tuple | None:
    """找离 t 最近的 BeatNet 拍 (时间, 编号), 超容差返回 None。"""
    if not beatnet_beats:
        return None
    best_i = min(range(len(beatnet_beats)),
                 key=lambda i: abs(beatnet_beats[i] - t))
    if abs(beatnet_beats[best_i] - t) > ALIGN_TOLERANCE_SEC:
        return None
    n = beat_numbers[best_i] if best_i < len(beat_numbers) else 0
    return (beatnet_beats[best_i], n)


def fuse_beatgrids(
    project_beats: Sequence[float],
    beatnet_result: Any,
    tolerance: float = ALIGN_TOLERANCE_SEC,
) -> FusionResult:
    """调和项目节拍与 BeatNet 网格。

    Args:
        project_beats: 项目节奏管线输出的拍点时间 (s, 升序)
        beatnet_result: models.beat.beatnet_adapter.BeatGridResult
            (或任何含 beats/beat_numbers/tempo 属性的对象)
        tolerance: 对齐容差 (s)

    Returns:
        FusionResult
    """
    bn_beats = list(getattr(beatnet_result, "beats", []) or [])
    bn_numbers = list(getattr(beatnet_result, "beat_numbers", []) or [])
    bn_tempo = float(getattr(beatnet_result, "tempo", 0.0) or 0.0)
    proj = sorted(float(t) for t in project_beats)

    result = FusionResult(
        n_project_beats=len(proj),
        n_beatnet_beats=len(bn_beats),
        tempo_beatnet=bn_tempo,
    )

    # tempo_project: 项目拍中位间隔
    if len(proj) >= 2:
        gaps = [b - a for a, b in zip(proj[:-1], proj[1:])]
        gaps = [g for g in gaps if g > 0.05]
        if gaps:
            import statistics
            result.tempo_project = round(
                60.0 / statistics.median(gaps), 1)

    if result.tempo_project > 0 and bn_tempo > 0:
        result.tempo_delta = abs(
            bn_tempo - result.tempo_project) / result.tempo_project
        result.tempo_consistent = result.tempo_delta <= TEMPO_TOLERANCE

    downbeats = []
    for t in proj:
        hit = _nearest_beat(bn_beats, bn_numbers, t)
        if hit is None:
            result.fused_beats.append({
                "t": round(t, 3), "beat_number": 0, "is_downbeat": False,
                "source": "project",
            })
            continue
        bt, num = hit
        is_db = num == 1
        result.fused_beats.append({
            "t": round(t, 3), "beat_number": num,
            "is_downbeat": is_db,
            "source": "fused",
            "beatnet_t": round(bt, 3),
        })
        result.n_aligned += 1
        if is_db:
            downbeats.append(round(t, 3))

    result.alignment_rate = (
        result.n_aligned / result.n_project_beats
        if result.n_project_beats else 0.0)
    result.downbeat_times = downbeats
    return result
