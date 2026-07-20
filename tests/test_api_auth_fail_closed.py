"""api_server 认证 fail-closed 行为测试

覆盖 Bug：require_auth 在 auth_system 不可用时返回 None，导致多个端点隐式放行，
触发未授权访问（特别是 list_alert_history、metrics_summary 等不使用 user 的端点）。

修复后行为：
- 当 _AUTH_AVAILABLE=False 或 _auth=None 时，require_auth 必须抛出 HTTPException(503)
- 不允许返回 None 后由业务层隐式放行
"""
import os
import sys

import pytest
from fastapi import HTTPException

# 将项目根目录加入路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import api_server


class TestRequireAuthFailClosed:
    """当 auth_system 不可用时，require_auth 必须 fail-closed（返回 503）"""

    def test_require_auth_returns_503_when_auth_module_unavailable(self, monkeypatch):
        """修复点：返回 None 会让上层端点隐式放行。修复后必须抛 HTTPException(503)"""
        # 模拟 auth 模块不可用
        monkeypatch.setattr(api_server, "_AUTH_AVAILABLE", False)
        monkeypatch.setattr(api_server, "_auth", None)

        with pytest.raises(HTTPException) as exc_info:
            api_server.require_auth(credentials=None)

        assert exc_info.value.status_code == 503, (
            f"认证不可用时应返回 503，实际返回 {exc_info.value.status_code}。"
            "如果返回 401 或 200/None，将造成未授权访问。"
        )

    def test_require_auth_returns_503_when_auth_object_is_none(self, monkeypatch):
        """_AUTH_AVAILABLE=True 但 _auth=None（初始化失败）时也必须 fail-closed"""
        monkeypatch.setattr(api_server, "_AUTH_AVAILABLE", True)
        monkeypatch.setattr(api_server, "_auth", None)

        with pytest.raises(HTTPException) as exc_info:
            api_server.require_auth(credentials=None)

        assert exc_info.value.status_code == 503, (
            "即使 _AUTH_AVAILABLE=True，若 _auth 本身为 None 也必须 503。"
        )

    def test_metrics_summary_endpoint_rejects_when_auth_unavailable(self, monkeypatch):
        """/api/v1/metrics/summary 在 auth 不可用时必须返回 503（修复前是 200）"""
        from fastapi.testclient import TestClient

        monkeypatch.setattr(api_server, "_AUTH_AVAILABLE", False)
        monkeypatch.setattr(api_server, "_auth", None)
        # 注入一个最小可用的 monitoring，使端点能执行到 auth 检查
        monkeypatch.setattr(api_server, "_MONITORING_AVAILABLE", True)
        monkeypatch.setattr(api_server, "_metrics", object())

        client = TestClient(api_server.app, raise_server_exceptions=False)
        resp = client.get("/api/v1/metrics/summary")

        assert resp.status_code == 503, (
            f"metrics_summary 在 auth 不可用时必须 503，"
            f"实际 {resp.status_code}。这会让任何人无授权读取系统指标。"
        )

    def test_alert_history_endpoint_rejects_when_auth_unavailable(self, monkeypatch):
        """/api/v1/alerts/history 在 auth 不可用时必须返回 503（修复前是 200）"""
        from fastapi.testclient import TestClient

        class _FakeAlerts:
            def list_history(self, limit):
                # 返回敏感数据模拟
                return [{"id": "secret-alert-001", "severity": "critical"}]

        monkeypatch.setattr(api_server, "_AUTH_AVAILABLE", False)
        monkeypatch.setattr(api_server, "_auth", None)
        monkeypatch.setattr(api_server, "_MONITORING_AVAILABLE", True)
        monkeypatch.setattr(api_server, "_alerts", _FakeAlerts())

        client = TestClient(api_server.app, raise_server_exceptions=False)
        resp = client.get("/api/v1/alerts/history")

        assert resp.status_code == 503, (
            f"alerts/history 在 auth 不可用时必须 503，"
            f"实际 {resp.status_code}。修复前会泄露告警历史（含 critical 级告警）。"
        )
        # 同时确认敏感数据没有被包含在响应中
        assert "secret-alert-001" not in resp.text, (
            "503 响应中不能包含任何 alert 数据"
        )
