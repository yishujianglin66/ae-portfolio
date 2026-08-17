"""tests/test_error_diagnostician.py — AE 崩溃诊断器测试

覆盖: 规则引擎匹配 / 缓存 TTL / LLM 响应解析与校准 / 统计持久化。
(该模块此前零测试, 属审计"最该优先补测试"第 1 位)
"""
from __future__ import annotations

import asyncio

import pytest

from core.error_diagnostician import (
    DiagnosticResult,
    ErrorDiagnostician,
    FixType,
)


@pytest.fixture
def diag(tmp_path):
    d = ErrorDiagnostician(stats_file=str(tmp_path / "diag_stats.json"))
    d._gateway = None  # 强制仅规则引擎 (不触发 LLM)
    return d


def _run(coro):
    # asyncio.run 每次新建循环, 与 pytest-asyncio 会话循环隔离
    # (原 get_event_loop 模式在全量套件下 RuntimeError: no current event loop)
    return asyncio.run(coro)


# ── 1. 规则引擎 ──────────────────────────────────────────────

def test_rule_match_layer_move(diag):
    err = ValueError("layer.move is not a function")
    result = _run(diag.diagnose(err, use_llm=False))
    assert result.success is True
    assert result.fix_type == FixType.WORKAROUND
    assert result.confidence >= 0.9
    assert result.source == "rule_engine"
    assert "parent" in result.fix_code


def test_rule_match_opacity(diag):
    err = RuntimeError("Opacity value out of range: 0.5 (AE expects 0-100)")
    result = _run(diag.diagnose(err, use_llm=False))
    assert result.fix_type == FixType.PARAMETER_FIX
    assert "100" in result.fix_code


def test_rule_match_ffmpeg_tonemap(diag):
    err = RuntimeError("HDR video tonemap color offset after conversion")
    result = _run(diag.diagnose(err, use_llm=False))
    assert result.success is True
    assert "tonemap" in result.fix_code


def test_no_match_returns_low_confidence(diag):
    err = ValueError("完全未知的诡异错误 zzz-qqq-123")
    result = _run(diag.diagnose(err, use_llm=False))
    assert result.success is False
    assert result.fix_type == FixType.MANUAL_REQUIRED
    assert result.confidence == 0.1
    assert "zzz-qqq-123" in result.root_cause


# ── 2. 缓存 ──────────────────────────────────────────────────

def test_cache_hit_on_repeat(diag):
    err = ValueError("layer.move is not a function")
    r1 = _run(diag.diagnose(err, use_llm=False))
    r2 = _run(diag.diagnose(err, use_llm=False))
    assert r1.success and r2.success
    stats = diag.get_statistics()
    assert stats["cache_hits"] == 1
    assert stats["total_diagnoses"] == 2
    # 缓存命中延迟应接近 0
    assert r2.latency_ms < 10


def test_clear_cache(diag):
    err = ValueError("layer.move is not a function")
    _run(diag.diagnose(err, use_llm=False))
    diag.clear_cache()
    assert diag.get_statistics()["cache_size"] == 0


# ── 3. LLM 响应解析与校准 ────────────────────────────────────

def test_parse_llm_markdown_wrapped_json(diag):
    content = '''```json
{"fix_type": "parameter_fix",
 "fix_description": "使用matchName",
 "fix_code": "layer.property('ADBE Position')",
 "confidence": 0.9,
 "root_cause": "显示名错误",
 "alternatives": ["a", "b"]}
```'''
    r = diag._parse_llm_response(content)
    assert r.success is True
    assert r.fix_type == FixType.PARAMETER_FIX
    assert r.source == "llm"
    # S2.2 校准: 0.9 × 0.85 = 0.765
    assert abs(r.confidence - 0.765) < 1e-6
    assert r.alternatives == ["a", "b"]


def test_parse_llm_plain_json(diag):
    r = diag._parse_llm_response(
        '{"fix_type": "workaround", "fix_description": "d", '
        '"fix_code": "c", "confidence": 0.5, "root_cause": "r"}')
    assert r.success is True
    assert r.fix_type == FixType.WORKAROUND


def test_parse_llm_garbage(diag):
    r = diag._parse_llm_response("这不是JSON")
    assert r.success is False
    assert "解析失败" in r.error


def test_parse_llm_unknown_fix_type_falls_back(diag):
    r = diag._parse_llm_response(
        '{"fix_type": "quantum_fix", "fix_description": "d", '
        '"fix_code": "c", "confidence": 0.8, "root_cause": "r"}')
    assert r.fix_type == FixType.MANUAL_REQUIRED  # 未知类型兜底


# ── 4. 统计持久化 ───────────────────────────────────────────

def test_statistics_persisted(tmp_path):
    d = ErrorDiagnostician(stats_file=str(tmp_path / "s.json"))
    d._gateway = None
    _run(d.diagnose(ValueError("layer.move is not a function"), use_llm=False))
    # 重新加载 → 统计从磁盘恢复
    d2 = ErrorDiagnostician(stats_file=str(tmp_path / "s.json"))
    assert d2.get_statistics()["total_diagnoses"] == 1
    assert d2.get_statistics()["rule_engine_hits"] == 1


def test_get_statistics_shape(diag):
    s = diag.get_statistics()
    for key in ("total_diagnoses", "rule_engine_hits", "llm_diagnoses",
                "llm_failures", "cache_hits", "cache_size", "llm_available"):
        assert key in s


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--no-header", "-p", "no:cacheprovider", "-x"])
