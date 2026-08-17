"""core/content_metrics.py - 内容级质量指标

输入均为导演/管线已掌握的结构化数据, 不解码视频, 零外部依赖。
所有分数归一到 [0, 1]。用于 AutoQualityEvaluator 真实化(替代常数分)。

诊断依据: D1 根因 — self_evolution_engine.py:614-708 四维全为常数分/阶段计数,
此模块提供真实的内容级信号替代。
"""
from __future__ import annotations

import math
from collections import Counter
from typing import Dict, List, Sequence, Tuple


def beat_alignment_score(
    cut_times: Sequence[float],
    beat_times: Sequence[float],
    tolerance: float = 0.05,
) -> float:
    """切点落在节拍容差内的比例。0=完全脱拍, 1=全部卡拍。

    Args:
        cut_times: 导演输出的切点时间序列(秒)
        beat_times: 音频分析得到的节拍时间序列(秒)
        tolerance: 容差(秒), 默认 50ms

    Returns:
        命中率, [0, 1]
    """
    if not cut_times or not beat_times:
        return 0.0
    hits = 0
    for t in cut_times:
        if min(abs(t - b) for b in beat_times) <= tolerance:
            hits += 1
    return hits / len(cut_times)


def camera_diversity_score(moves: Sequence[str]) -> float:
    """运镜序列香农熵归一化。检测 pan_left*12 这类同质化。

    香农熵 H = -Σ p_i * log(p_i), 归一到 H / H_max。
    单一运镜 → 0.0; 均匀分布多种运镜 → 1.0。

    Args:
        moves: 运镜类型序列, 如 ["pan_left", "zoom_in", "push", ...]

    Returns:
        归一化熵, [0, 1]
    """
    if not moves:
        return 0.0
    counts = Counter(moves)
    n = len(moves)
    unique = len(counts)
    if unique <= 1:
        return 0.0
    entropy = -sum((c / n) * math.log(c / n) for c in counts.values())
    max_entropy = math.log(unique)
    return min(entropy / max_entropy, 1.0)


def material_reuse_penalty(windows: Sequence[Tuple[str, float, float]]) -> float:
    """素材窗口重叠率。windows=(source, start, end)。0=无复用, 1=完全复用。

    按素材源分组, 合并重叠区间后计算 overlap/union(Jaccard 式)。
    用于惩罚导演重复使用同一段素材的行为。

    Args:
        windows: (素材源路径, 起始秒, 结束秒) 的序列

    Returns:
        重叠率, [0, 1]
    """
    if len(windows) < 2:
        return 0.0
    by_src: Dict[str, List[Tuple[float, float]]] = {}
    for src, s, e in windows:
        by_src.setdefault(src, []).append((s, e))
    total_overlap = 0.0
    total_union = 0.0
    for spans in by_src.values():
        spans.sort()
        # 合并重叠区间, 同时累计重叠量
        merged: List[Tuple[float, float]] = []
        for s, e in spans:
            if not merged or s >= merged[-1][1]:
                # 无重叠, 新增区间
                merged.append((s, e))
            else:
                # 与前一区间重叠
                overlap_end = min(e, merged[-1][1])
                if overlap_end > s:
                    total_overlap += overlap_end - s
                # 扩展合并区间
                merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        # 并集 = 合并后各区间的时长之和
        union_dur = sum(e - s for s, e in merged)
        total_union += union_dur
    if total_union <= 0:
        return 0.0
    return min(total_overlap / total_union, 1.0)


def temporal_energy_variance(energy_series: Sequence[float]) -> float:
    """能量序列标准差, tanh 归一。0=静止无节奏感, →1=强动态。

    用于衡量视频时序能量的波动程度。高方差意味着画面有强烈的
    动静交替(如战斗场景的攻防节奏), 低方差意味着平淡。

    Args:
        energy_series: 按时间采样的能量值序列(如 RMS 音量、光流幅值)

    Returns:
        tanh(sqrt(var) * 4), [0, 1]
    """
    if len(energy_series) < 2:
        return 0.0
    mean = sum(energy_series) / len(energy_series)
    var = sum((x - mean) ** 2 for x in energy_series) / len(energy_series)
    return math.tanh(math.sqrt(var) * 4.0)
