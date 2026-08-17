"""Bridge Middleware 单元测试。"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from ae.bridge_middleware import (
    MiddlewarePipeline,
    LoggingMiddleware,
    ValidationMiddleware,
    RateLimitMiddleware,
    MetricsMiddleware,
    RetryMiddleware,
)
from ae.bridge_protocol import BridgeCommand, BridgeResponse


class TestMiddlewarePipeline:
    """中间件管道测试。"""

    def test_pipeline_empty(self) -> None:
        """空管道。"""
        pipeline = MiddlewarePipeline()
        handler = MagicMock(return_value={"success": True})
        
        result = pipeline.process_command({}, handler)
        
        assert result == {"success": True}
        handler.assert_called_once_with({})

    def test_pipeline_with_single_middleware(self) -> None:
        """单个中间件。"""
        pipeline = MiddlewarePipeline()
        handler = MagicMock(return_value={"success": True})
        
        middleware = MagicMock()
        middleware.process_command = MagicMock(side_effect=lambda cmd, h: h(cmd))
        
        pipeline.add(middleware)
        result = pipeline.process_command({}, handler)
        
        assert result == {"success": True}
        middleware.process_command.assert_called_once()
        handler.assert_called_once()

    def test_pipeline_with_multiple_middlewares(self) -> None:
        """多个中间件。"""
        pipeline = MiddlewarePipeline()
        handler = MagicMock(return_value={"success": True})
        
        m1 = MagicMock()
        m1.process_command = MagicMock(side_effect=lambda cmd, h: h(cmd))
        
        m2 = MagicMock()
        m2.process_command = MagicMock(side_effect=lambda cmd, h: h(cmd))
        
        pipeline.add(m1).add(m2)
        result = pipeline.process_command({}, handler)
        
        assert result == {"success": True}
        m1.process_command.assert_called_once()
        m2.process_command.assert_called_once()
        handler.assert_called_once()


class TestLoggingMiddleware:
    """日志中间件测试。"""

    def test_process_command(self) -> None:
        """处理命令。"""
        middleware = LoggingMiddleware()
        handler = MagicMock(return_value={"success": True})
        
        result = middleware.process_command({"action": "test"}, handler)
        
        assert result == {"success": True}
        handler.assert_called_once()


class TestValidationMiddleware:
    """验证中间件测试。"""

    def test_valid_command(self) -> None:
        """有效命令。"""
        middleware = ValidationMiddleware()
        handler = MagicMock(return_value={"success": True})
        
        class MockCommand:
            command = "test"
            params = {"key": "value"}
        
        result = middleware.process_command(MockCommand(), handler)
        
        assert result == {"success": True}
        handler.assert_called_once()

    def test_invalid_command(self) -> None:
        """无效命令（缺少必需参数）。"""
        middleware = ValidationMiddleware(required_params={"test": ["required_param"]})
        handler = MagicMock(return_value={"success": True})
        
        class MockCommand:
            command = "test"
            params = {}
        
        with pytest.raises(ValueError):
            middleware.process_command(MockCommand(), handler)
        
        handler.assert_not_called()


class TestRateLimitMiddleware:
    """限流中间件测试。"""

    def test_under_limit(self) -> None:
        """在限制内。"""
        middleware = RateLimitMiddleware(max_requests=10, window_seconds=60)
        handler = MagicMock(return_value={"success": True})
        
        class MockCommand:
            command = "test"
        
        for _ in range(5):
            result = middleware.process_command(MockCommand(), handler)
            assert result == {"success": True}
        
        assert handler.call_count == 5

    def test_over_limit(self) -> None:
        """超过限制。"""
        middleware = RateLimitMiddleware(max_requests=2, window_seconds=60)
        handler = MagicMock(return_value={"success": True})
        
        class MockCommand:
            command = "test"
        
        middleware.process_command(MockCommand(), handler)
        middleware.process_command(MockCommand(), handler)
        
        with pytest.raises(RuntimeError):
            middleware.process_command(MockCommand(), handler)
        
        assert handler.call_count == 2


class TestMetricsMiddleware:
    """指标中间件测试。"""

    def test_process_command(self) -> None:
        """处理命令。"""
        middleware = MetricsMiddleware()
        handler = MagicMock(return_value={"success": True})
        
        result = middleware.process_command({"action": "test"}, handler)
        
        assert result == {"success": True}
        handler.assert_called_once()


class TestRetryMiddleware:
    """重试中间件测试。"""

    def test_success_on_first_attempt(self) -> None:
        """第一次尝试成功。"""
        middleware = RetryMiddleware(max_retries=2)
        handler = MagicMock(return_value={"success": True})
        
        class MockCommand:
            command = "test"
        
        result = middleware.process_command(MockCommand(), handler)
        
        assert result == {"success": True}
        handler.assert_called_once()

    def test_retry_on_failure(self) -> None:
        """失败后重试。"""
        middleware = RetryMiddleware(max_retries=2)
        handler = MagicMock(side_effect=[
            RuntimeError("fail 1"),
            RuntimeError("fail 2"),
            {"success": True},
        ])
        
        class MockCommand:
            command = "test"
        
        result = middleware.process_command(MockCommand(), handler)
        
        assert result == {"success": True}
        assert handler.call_count == 3

    def test_exhausted_retries(self) -> None:
        """重试耗尽。"""
        middleware = RetryMiddleware(max_retries=2)
        handler = MagicMock(side_effect=RuntimeError("always fails"))
        
        class MockCommand:
            command = "test"
        
        with pytest.raises(RuntimeError):
            middleware.process_command(MockCommand(), handler)
        
        assert handler.call_count == 3