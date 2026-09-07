"""P3 观测层：engine_health / resource_quota 的 Prometheus 文本 exposition 测试。

只测 core.engine_watchdog.engine_health_metrics_prometheus（零依赖、可独立验证）。
网关 /metrics 端点以 guarded 局部 import 复用此函数，不在此重复拉起 fastapi。
"""
import pytest

import core.engine_watchdog as ew
from core.engine_watchdog import EngineHealthRegistry, ResourceQuota


def _reset(monkeypatch, max_concurrent=2):
    monkeypatch.setattr(ew, "ENGINE_HEALTH", EngineHealthRegistry())
    monkeypatch.setattr(ew, "ENGINE_QUOTA", ResourceQuota(max_concurrent=max_concurrent))


def test_metrics_exposes_engine_and_quota(monkeypatch):
    _reset(monkeypatch)
    ew.ENGINE_HEALTH.mark_healthy("after_effects")
    text = ew.engine_health_metrics_prometheus()
    assert 'engine_health_up{engine="after_effects"} 1' in text
    assert "engine_health_last_seen_healthy_ts{engine=\"after_effects\"}" in text
    assert "engine_quota_max_concurrent 2" in text
    assert "engine_quota_available 2" in text


def test_metrics_status_mapping(monkeypatch):
    _reset(monkeypatch)
    ew.ENGINE_HEALTH.mark_dead("after_effects", "boom")
    text = ew.engine_health_metrics_prometheus()
    # dead -> up=0
    assert 'engine_health_up{engine="after_effects"} 0' in text


def test_metrics_quota_active_reflected(monkeypatch):
    _reset(monkeypatch)
    assert ew.ENGINE_QUOTA.acquire_engine("after_effects", timeout=1.0)
    text = ew.engine_health_metrics_prometheus()
    assert "engine_quota_active 1" in text
    assert "engine_quota_available 1" in text
    ew.ENGINE_QUOTA.release_engine("after_effects")


def test_metrics_multiple_engines(monkeypatch):
    _reset(monkeypatch)
    ew.ENGINE_HEALTH.mark_healthy("after_effects")
    ew.ENGINE_HEALTH.mark_healthy("premiere")
    ew.ENGINE_HEALTH.mark_dead("resolve", "x")
    text = ew.engine_health_metrics_prometheus()
    assert 'engine_health_up{engine="after_effects"} 1' in text
    assert 'engine_health_up{engine="premiere"} 1' in text
    assert 'engine_health_up{engine="resolve"} 0' in text
