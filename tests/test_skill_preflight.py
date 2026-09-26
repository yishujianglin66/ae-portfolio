# -*- coding: utf-8 -*-
"""skill_preflight 测试（P2 真融入：主管线读卡预检）。

核心不变式：
 1. 预检永不抛异常（预检坏不能拦出片）
 2. 管线声明的技能必须全部在 registry（脱节=预检 FAIL，这是融入的牙齿）
 3. 非 active 卡进生产管线声明 -> 必出警告（stage 闸门运行时侧）
 4. 预算聚合正确（耗时求和、GPU/API 计数）
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.skill_preflight import (  # noqa: E402
    PIPELINE_SKILLS, REGISTRY_PATH, preflight, preflight_for_pipeline,
)


def test_never_raises():
    # 不存在的管线名也不许抛
    r = preflight_for_pipeline("no_such_pipeline_xyz")
    assert isinstance(r, dict) and "warnings" in r


def test_pipeline_declared_skills_all_in_registry():
    """融入的牙齿：管线依赖声明与卡片库不许脱节。"""
    import json
    reg = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))["skills"]
    for pipe, ids in PIPELINE_SKILLS.items():
        for sid in ids:
            assert sid in reg, f"管线 {pipe} 声明了不存在的卡 {sid}"


def test_non_active_declared_warned():
    r = preflight("unified_edit", skill_ids=["fx_badtv"])  # 该卡 stage=validated
    assert any("非 active" in w for w in r["warnings"])
    assert r["ready"] is False


def test_budget_aggregation():
    r = preflight("unified_edit", skill_ids=["vrs_beat_analysis", "beat_sync_edit"])
    assert r["budget"]["total_typical_sec"] == 70.0  # 10+60
    assert r["ready"] is True
    assert r["headless_matrix"].get("headless") == 2


def test_missing_card_flagged():
    r = preflight("unified_edit", skill_ids=["totally_missing_card"])
    assert r["ready"] is False
    assert any("脱节" in w for w in r["warnings"])
