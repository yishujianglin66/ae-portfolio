"""tests/test_taste_contract.py - 品味契约接入导演系统测试

T4: 品味契约接入导演 (零依赖, 直接提升 v23 编排)
- 品味参数化: motion_intensity 映射运镜池
- Anti-Default Checklist 前 3 条机检化
"""
import pytest

from ai.taste_contract import (
    DEFAULT_TASTE,
    HIGH_MOTION_POOL,
    LOW_MOTION_POOL,
    MID_MOTION_POOL,
    TasteProfile,
    camera_pool_for_intensity,
    check_anti_defaults,
)

# ---- TasteProfile 数据类 ----

def test_default_taste_values():
    t = DEFAULT_TASTE
    assert 1 <= t.visual_variance <= 10
    assert 1 <= t.motion_intensity <= 10
    assert 1 <= t.information_density <= 10


def test_taste_profile_from_dict():
    d = {
        "visual_variance": 7,
        "motion_intensity": 8,
        "information_density": 3,
        "design_read": "高燃混剪: 快切、强动态、高密度运镜",
    }
    t = TasteProfile.from_dict(d)
    assert t.motion_intensity == 8
    assert t.design_read.startswith("高燃")


def test_taste_profile_clamps_range():
    t = TasteProfile(visual_variance=0, motion_intensity=15, information_density=-1)
    assert t.visual_variance == 1
    assert t.motion_intensity == 10
    assert t.information_density == 1


# ---- motion_intensity → 运镜池映射 ----

def test_high_motion_pool_is_larger():
    """高运动强度必须提供更多运镜种类"""
    high = camera_pool_for_intensity(8)
    low = camera_pool_for_intensity(2)
    assert len(set(high)) >= len(set(low))


def test_low_motion_pool_has_calm_moves():
    """低运动强度应以静态/缓移为主"""
    pool = camera_pool_for_intensity(2)
    # 不应包含快速脉冲运镜
    assert "zoom_in" not in pool or pool.count("zoom_in") <= 1


def test_high_motion_pool_has_kinetic_moves():
    """高运动强度应包含多种方向性运镜"""
    pool = camera_pool_for_intensity(9)
    assert len(set(pool)) >= 4  # 至少 4 种不同运镜


def test_mid_motion_pool_balanced():
    pool = camera_pool_for_intensity(5)
    assert len(pool) >= 3


# ---- Anti-Default Checklist 机检 ----

def test_anti_default_same_transition_high_variance():
    """Anti-Default #2: visual_variance >= 4 时不应所有切点用同一转场"""
    segments = [
        {"transition": "cross_dissolve", "zoompan_effect": "pan_left"},
        {"transition": "cross_dissolve", "zoompan_effect": "zoom_in"},
        {"transition": "cross_dissolve", "zoompan_effect": "zoom_out"},
        {"transition": "cross_dissolve", "zoompan_effect": "diag_pan"},
    ]
    taste = TasteProfile(visual_variance=6, motion_intensity=5, information_density=5)
    violations = check_anti_defaults(segments, taste)
    assert any("transition" in v["rule"] for v in violations)


def test_anti_default_no_violation_varied_transitions():
    """转场多样化时不应触发 Anti-Default #2"""
    segments = [
        {"transition": "cross_dissolve", "zoompan_effect": "pan_left"},
        {"transition": "wipe", "zoompan_effect": "zoom_in"},
        {"transition": "cut", "zoompan_effect": "zoom_out"},
        {"transition": "cross_dissolve", "zoompan_effect": "diag_pan"},
    ]
    taste = TasteProfile(visual_variance=6, motion_intensity=5, information_density=5)
    violations = check_anti_defaults(segments, taste)
    transition_violations = [v for v in violations if "transition" in v["rule"]]
    assert len(transition_violations) == 0


def test_anti_default_kinetic_motion_blocks_narration():
    """Anti-Default #3: 低 information_density + 高 motion_intensity 时警告"""
    segments = [
        {"transition": "cut", "zoompan_effect": "zoom_in"},
        {"transition": "cut", "zoompan_effect": "pan_left"},
    ]
    taste = TasteProfile(visual_variance=5, motion_intensity=9, information_density=2)
    violations = check_anti_defaults(segments, taste)
    assert any("narration" in v["rule"].lower() or "motion" in v["rule"].lower()
               for v in violations)


def test_anti_default_low_variance_same_camera_ok():
    """低 visual_variance 时,相同运镜不触发 Anti-Default #2"""
    segments = [
        {"transition": "cross_dissolve", "zoompan_effect": "pan_left"},
        {"transition": "cross_dissolve", "zoompan_effect": "pan_left"},
        {"transition": "cross_dissolve", "zoompan_effect": "pan_left"},
    ]
    taste = TasteProfile(visual_variance=2, motion_intensity=3, information_density=5)
    violations = check_anti_defaults(segments, taste)
    transition_violations = [v for v in violations if "transition" in v["rule"]]
    assert len(transition_violations) == 0


def test_anti_default_empty_segments():
    taste = DEFAULT_TASTE
    assert check_anti_defaults([], taste) == []
