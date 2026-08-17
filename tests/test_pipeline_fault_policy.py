"""P1 一致性收口 单元测试（降级 opt-in + 八类 postmortem，规格 §0.4）。

运行：pytest tests/test_pipeline_fault_policy.py -v
依赖：仅标准库 + loguru（core.pipeline_fault_policy 无重型依赖）。
"""
import os
import tempfile
from pathlib import Path

from core.pipeline_fault_policy import (
    FAILURE_CATEGORIES,
    engine_fallback_enabled,
    classify_failure,
    write_postmortem,
    FlagshipStageError,
)


def test_default_strict_disabled():
    os.environ.pop("AEKV_ENGINE_FALLBACK", None)
    assert engine_fallback_enabled() is False


def test_opt_in_enabled():
    os.environ["AEKV_ENGINE_FALLBACK"] = "1"
    try:
        assert engine_fallback_enabled() is True
    finally:
        os.environ.pop("AEKV_ENGINE_FALLBACK", None)


def test_flagship_stage_error_carries_category():
    err = FlagshipStageError("S3", "BRIDGE_DOWN", "AE 不可用")
    assert err.stage == "S3"
    assert err.category == "BRIDGE_DOWN"


def test_flagship_stage_error_invalid_category_defaults():
    err = FlagshipStageError("S3", "NOT_A_CATEGORY", "x")
    assert err.category == "BRIDGE_DOWN"


def test_classify_eight_categories():
    cases = [
        ("S0", RuntimeError("No space left on device (ENOSPC)"), "DISK_FULL"),
        ("S5", TimeoutError("operation timed out after 1800s"), "TIMEOUT"),
        ("S3", RuntimeError("licence popup blocking dialog detected"), "LICENCE_POPUP_BLOCKING"),
        ("S3", RuntimeError("license file missing"), "LICENSE_MISSING"),
        ("S3", RuntimeError("jsx syntax error near line 12"), "SCRIPT_SYNTAX"),
        ("S3", RuntimeError("user cancelled"), "USER_CANCELLED"),
        ("S6", RuntimeError("output file corrupt"), "OUTPUT_CORRUPT"),
        ("S3", RuntimeError("Bridge connection refused"), "BRIDGE_DOWN"),
        ("S3", RuntimeError("some unknown native failure"), "BRIDGE_DOWN"),  # 默认回退
    ]
    for stage, exc, expect in cases:
        assert classify_failure(stage, exc) == expect, f"{stage}/{exc} -> {classify_failure(stage, exc)}"


def test_write_postmortem_all_eight():
    tmp = Path(tempfile.mkdtemp(prefix="p1_pm_"))
    for cat in FAILURE_CATEGORIES:
        p = write_postmortem(tmp, cat, "SX", f"test {cat}", {"S0": {}})
        t = p.read_text(encoding="utf-8")
        assert cat in t and "修复建议" in t, f"{cat} postmortem 缺要素"


def test_write_postmortem_invalid_category_defaults():
    tmp = Path(tempfile.mkdtemp(prefix="p1_pm_"))
    p = write_postmortem(tmp, "BOGUS", "S3", "err", {})
    assert "BRIDGE_DOWN" in p.read_text(encoding="utf-8")
