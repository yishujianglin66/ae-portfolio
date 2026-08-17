"""Tests for core.content_metrics - 内容级质量指标

TDD: 这些测试先于实现编写, 验证四个纯函数的边界行为。
"""
import math
import pytest
from core.content_metrics import (
    beat_alignment_score,
    camera_diversity_score,
    material_reuse_penalty,
    temporal_energy_variance,
)


# ── beat_alignment_score ─────────────────────────────────────────────


def test_beat_alignment_perfect():
    """所有切点都落在节拍 50ms 容差内 → 1.0"""
    beats = [1.0, 2.0, 3.0, 4.0]
    cuts = [1.02, 1.98, 3.01, 4.0]  # 全部在 50ms 容差内
    assert beat_alignment_score(cuts, beats, tolerance=0.05) == pytest.approx(1.0)


def test_beat_alignment_all_off():
    """切点全落在两拍正中 → <0.2"""
    beats = [1.0, 2.0, 3.0, 4.0]
    cuts = [1.5, 2.5, 3.5]  # 全部落在两拍正中
    assert beat_alignment_score(cuts, beats, tolerance=0.05) < 0.2


def test_beat_alignment_no_cuts():
    """零切点 → 0.0"""
    assert beat_alignment_score([], [1.0, 2.0]) == 0.0


def test_beat_alignment_no_beats():
    """零节拍 → 0.0"""
    assert beat_alignment_score([1.0, 2.0], []) == 0.0


def test_beat_alignment_partial():
    """一半切点对齐 → 0.5"""
    beats = [1.0, 2.0, 3.0, 4.0]
    cuts = [1.0, 2.5, 3.0, 3.5]  # 2/4 对齐
    assert beat_alignment_score(cuts, beats, tolerance=0.05) == pytest.approx(0.5)


# ── camera_diversity_score ───────────────────────────────────────────


def test_camera_diversity_uniform():
    """6 种运镜各一次 → 最大熵 → 1.0"""
    moves = ["pan_left", "zoom_in", "push", "orbit", "zoom_out", "pan_right"]
    assert camera_diversity_score(moves) == pytest.approx(1.0, abs=0.05)


def test_camera_diversity_homogeneous():
    """v23 实际缺陷复现: build 段全 pan_left → <0.1"""
    moves = ["pan_left"] * 12
    assert camera_diversity_score(moves) < 0.1


def test_camera_diversity_empty():
    """空序列 → 0.0"""
    assert camera_diversity_score([]) == 0.0


def test_camera_diversity_single():
    """单一运镜 → 0.0(无多样性)"""
    assert camera_diversity_score(["pan_left"]) == 0.0


def test_camera_diversity_two_types():
    """两种运镜均匀分布 → 1.0(二分类最大熵)"""
    moves = ["pan_left", "zoom_in"] * 5
    assert camera_diversity_score(moves) == pytest.approx(1.0, abs=0.05)


# ── material_reuse_penalty ───────────────────────────────────────────


def test_material_reuse_no_reuse():
    """不同素材无重叠 → 0.0"""
    windows = [("src_a.mp4", 1.0, 3.0), ("src_b.mp4", 5.0, 8.0)]
    assert material_reuse_penalty(windows) == pytest.approx(0.0)


def test_material_reuse_full_overlap():
    """同素材窗口几乎完全重叠 → >0.8"""
    windows = [("src_a.mp4", 1.0, 3.0), ("src_a.mp4", 1.1, 3.1)]
    assert material_reuse_penalty(windows) > 0.8


def test_material_reuse_single_window():
    """单一窗口 → 0.0(无复用可能)"""
    assert material_reuse_penalty([("src_a.mp4", 1.0, 3.0)]) == 0.0


def test_material_reuse_empty():
    """空窗口列表 → 0.0"""
    assert material_reuse_penalty([]) == 0.0


def test_material_reuse_adjacent_no_overlap():
    """同素材但相邻不重叠 → 0.0"""
    windows = [("src_a.mp4", 1.0, 3.0), ("src_a.mp4", 3.0, 5.0)]
    assert material_reuse_penalty(windows) == pytest.approx(0.0)


def test_material_reuse_partial_overlap():
    """同素材部分重叠 → 0<penalty<1"""
    windows = [("src_a.mp4", 1.0, 4.0), ("src_a.mp4", 3.0, 6.0)]
    penalty = material_reuse_penalty(windows)
    assert 0.0 < penalty < 1.0


# ── temporal_energy_variance ─────────────────────────────────────────


def test_temporal_energy_variance_identical():
    """恒定能量 → 0.0(无节奏感)"""
    assert temporal_energy_variance([0.5, 0.5, 0.5, 0.5]) == pytest.approx(0.0)


def test_temporal_energy_variance_dynamic():
    """高低交替能量 → >0.5(强节奏感)"""
    series = [0.1, 0.9, 0.2, 0.8, 0.15, 0.85]
    assert temporal_energy_variance(series) > 0.5


def test_temporal_energy_variance_single():
    """单一采样点 → 0.0"""
    assert temporal_energy_variance([0.5]) == 0.0


def test_temporal_energy_variance_empty():
    """空序列 → 0.0"""
    assert temporal_energy_variance([]) == 0.0


def test_temporal_energy_variance_bounded():
    """所有输出应在 [0, 1] 区间(tanh 归一保证)"""
    series = [0.0, 1.0, 0.0, 1.0, 0.0, 1.0]
    result = temporal_energy_variance(series)
    assert 0.0 <= result <= 1.0
