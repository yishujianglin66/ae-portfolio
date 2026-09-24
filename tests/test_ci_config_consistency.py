# -*- coding: utf-8 -*-
"""CI/配置一致性闸门（P1-B, 2026-09-20）。

起因：覆盖率 ratchet 的**地板值曾有两个真相源且互相矛盾** ——
`pyproject.toml` 写 `fail_under = 35`，而同段注释与 CI 命令都用 29。
因 CLI 的 `--cov-fail-under` 覆盖配置文件，CI 行为一直正确；但**本地不带 flag
跑 `--cov` 会被 35 卡红**（实测覆盖约 32.9%），是"本地假红、CI 绿"的隐性陷阱。

本闸门锁住这类"同一事实写两处"的漂移：
  1. pyproject 的 fail_under 必须与 CI workflow 的 --cov-fail-under 一致
  2. CI 必须真的上传覆盖率产物（否则历史无从追溯）
  3. 覆盖率地板必须是**低于实测**的 ratchet（不许把地板设在实测之上 → 必红）
"""
import re
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
PYPROJECT = PROJECT / "pyproject.toml"
WORKFLOW = PROJECT / ".github" / "workflows" / "quality-hardening.yml"


def _toml_text() -> str:
    return PYPROJECT.read_text(encoding="utf-8")


def _fail_under_config() -> int | None:
    m = re.search(r"(?m)^\s*fail_under\s*=\s*(\d+)", _toml_text())
    return int(m.group(1)) if m else None


def _fail_under_ci() -> int | None:
    if not WORKFLOW.exists():
        return None
    m = re.search(r"--cov-fail-under=(\d+)", WORKFLOW.read_text(encoding="utf-8"))
    return int(m.group(1)) if m else None


def test_fail_under_single_source_of_truth():
    """配置地板与 CI 地板必须一致（曾经 35 vs 29 不一致）。"""
    cfg, ci = _fail_under_config(), _fail_under_ci()
    assert cfg is not None, "pyproject 缺少 [tool.coverage.report] fail_under"
    assert ci is not None, "CI 缺少 --cov-fail-under"
    assert cfg == ci, (
        f"覆盖率地板两处不一致: pyproject fail_under={cfg}, CI={ci} —— "
        f"CLI 会覆盖配置, 于是本地与 CI 行为分叉")


def test_fail_under_is_a_ratchet_below_measured():
    """地板必须低于当前实测覆盖率（否则立刻红，失去 ratchet 意义）。

    实测值来自 reports/coverage_summary.json（由 scripts/coverage_summary.py 生成）。
    """
    summary = PROJECT / "reports" / "coverage_summary.json"
    if not summary.exists():
        pytest.skip("尚无覆盖率快照（先跑 scripts/coverage_summary.py）")
    import json
    measured = json.loads(summary.read_text(encoding="utf-8"))["totals"]["percent_covered"]
    cfg = _fail_under_config()
    assert cfg is not None
    assert cfg < measured, (
        f"地板 {cfg}% >= 实测 {measured}% —— 会让覆盖运行直接红；"
        f"ratchet 应设在实测略下方，随补测逐步上调")


def test_ci_uploads_coverage_artifact():
    """CI 必须上传覆盖率产物, 否则趋势无从追溯。"""
    if not WORKFLOW.exists():
        pytest.skip("无 quality-hardening.yml")
    src = WORKFLOW.read_text(encoding="utf-8")
    assert "coverage.xml" in src, "CI 未产出/上传 coverage.xml"
    assert "upload-artifact" in src, "CI 未上传产物"


def test_coverage_source_covers_core_packages():
    """source 必须含核心库主包（历史事故: 只列 ~17 个根模块, 主体从未被测量）。"""
    src = _toml_text()
    m = re.search(r"(?ms)^\[tool\.coverage\.run\].*?^source\s*=\s*\[(.*?)\]", src)
    assert m, "找不到 [tool.coverage.run] source"
    listed = set(re.findall(r'"([^"]+)"', m.group(1)))
    for pkg in ("core", "ai", "pipeline", "integrations", "agents"):
        assert pkg in listed, f"source 缺核心包 {pkg}（覆盖率将漏测代码主体）"


def test_summary_snapshot_is_committable_size():
    """快照必须是小文件 —— 原始 coverage.json 是 6MB 级, 不适合入仓。"""
    summary = PROJECT / "reports" / "coverage_summary.json"
    if not summary.exists():
        pytest.skip("尚无覆盖率快照")
    size_kb = summary.stat().st_size / 1024
    assert size_kb < 200, f"快照 {size_kb:.0f}KB 过大, 应只保留摘要（原始报告留 CI 产物）"
