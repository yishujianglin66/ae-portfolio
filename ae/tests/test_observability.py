"""
AE Bridge 可观测性测试
======================

测试全链路追踪和可观测性闭环功能：
- AE Tracer 操作级追踪
- 事件总线事件发布与订阅
- 指标采集与记录
- trace_id 贯穿调用链
- BridgeClient 追踪集成
- UnifiedAEClient 追踪集成
- 健康检查事件发布
- 维护模块指标采集

测试策略：
- 单元测试：验证单个组件功能
- 集成测试：验证组件间协作
- Mock 环境：无需真实 AE 即可运行
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any, Dict, List, Optional
from unittest.mock import Mock, patch, MagicMock

import pytest

# 确保项目根目录在 Python 路径中
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_tracer_state():
    """测试前后重置追踪器状态。"""
    from core.ae_tracer import ae_tracer
    ae_tracer._current_trace_id = None
    ae_tracer._current_span = None
    ae_tracer._span_stack = []
    yield
    ae_tracer._current_trace_id = None
    ae_tracer._current_span = None
    ae_tracer._span_stack = []


@pytest.fixture
def mock_event_bus():
    """Mock 事件总线。"""
    with patch("core.ae_tracer.publish_ae_event") as mock:
        yield mock


@pytest.fixture
def mock_metrics():
    """Mock 指标收集器。"""
    with patch("core.ae_tracer.global_metrics") as mock:
        yield mock


@pytest.fixture
def mock_observability_tracer():
    """Mock 全局可观测性追踪器。"""
    with patch("core.ae_tracer.global_tracer") as mock:
        yield mock


# ---------------------------------------------------------------------------
# AE Tracer 单元测试
# ---------------------------------------------------------------------------

class TestAETracer:
    """AE 专用追踪器测试。"""

    def test_generate_trace_id(self):
        """测试生成唯一的 trace_id。"""
        from core.ae_tracer import AETracer
        
        tracer = AETracer()
        trace_id1 = tracer._generate_trace_id()
        trace_id2 = tracer._generate_trace_id()
        
        assert len(trace_id1) == 16
        assert len(trace_id2) == 16
        assert trace_id1 != trace_id2
        assert trace_id1.isalnum()

    def test_generate_span_id(self):
        """测试生成唯一的 span_id。"""
        from core.ae_tracer import AETracer
        
        tracer = AETracer()
        span_id1 = tracer._generate_span_id()
        span_id2 = tracer._generate_span_id()
        
        assert len(span_id1) == 8
        assert len(span_id2) == 8
        assert span_id1 != span_id2
        assert span_id1.isalnum()

    def test_current_trace_id(self):
        """测试当前 trace_id 的获取和设置。"""
        from core.ae_tracer import AETracer
        
        tracer = AETracer()
        trace_id = tracer.current_trace_id
        
        assert len(trace_id) == 16
        
        new_trace_id = "abc123def4567890"
        tracer.current_trace_id = new_trace_id
        assert tracer.current_trace_id == new_trace_id

    def test_start_span(self, mock_event_bus, mock_metrics):
        """测试启动追踪 Span。"""
        from core.ae_tracer import AETracer
        
        tracer = AETracer()
        span = tracer.start_span("create_composition", channel="mcp")
        
        assert span.operation_name == "create_composition"
        assert span.channel == "mcp"
        assert span.status == "running"
        assert span.start_time > 0
        assert span.trace_id is not None
        assert span.span_id is not None
        
        assert len(tracer._span_stack) == 1
        assert tracer._current_span == span
        
        mock_metrics.increment.assert_called_once()
        mock_event_bus.assert_called_once()

    def test_end_span_success(self, mock_event_bus, mock_metrics):
        """测试成功结束追踪 Span。"""
        from core.ae_tracer import AETracer
        
        tracer = AETracer()
        span = tracer.start_span("create_composition")
        
        time.sleep(0.01)
        tracer.end_span(span, "success")
        
        assert span.status == "success"
        assert span.end_time > span.start_time
        assert span.duration_ms >= 0
        assert len(tracer._span_stack) == 0
        assert tracer._current_span is None
        
        assert mock_metrics.histogram.called
        assert mock_metrics.increment.called

    def test_end_span_failure(self, mock_event_bus, mock_metrics):
        """测试失败结束追踪 Span。"""
        from core.ae_tracer import AETracer
        
        tracer = AETracer()
        span = tracer.start_span("create_composition")
        
        span.record_failure("test error")
        tracer.end_span(span, "failed")
        
        assert span.status == "failed"
        assert span.error == "test error"
        assert len(tracer._span_stack) == 0

    def test_record_error(self, mock_metrics):
        """测试记录错误。"""
        from core.ae_tracer import AETracer
        
        tracer = AETracer()
        span = tracer.start_span("test_operation")
        
        try:
            raise ValueError("test error")
        except ValueError as e:
            tracer.record_error(span, e)
        
        assert span.status == "failed"
        assert span.error == "test error"
        assert span.attributes["error_type"] == "ValueError"
        assert span.attributes["error_message"] == "test error"
        
        assert mock_metrics.increment.call_count >= 2

    def test_nested_spans(self):
        """测试嵌套 Span。"""
        from core.ae_tracer import AETracer
        
        tracer = AETracer()
        parent_span = tracer.start_span("parent_operation")
        child_span = tracer.start_span("child_operation")
        
        assert len(tracer._span_stack) == 2
        assert child_span.parent_span_id == parent_span.span_id
        assert tracer._current_span == child_span
        
        tracer.end_span(child_span)
        assert len(tracer._span_stack) == 1
        assert tracer._current_span == parent_span
        
        tracer.end_span(parent_span)
        assert len(tracer._span_stack) == 0

    def test_span_attributes(self):
        """测试 Span 属性设置。"""
        from core.ae_tracer import AETracer
        
        tracer = AETracer()
        span = tracer.start_span("test", comp_name="TestComp", width=1920)
        
        span.set_attribute("height", 1080)
        span.set_attribute("fps", 30)
        
        assert span.attributes["comp_name"] == "TestComp"
        assert span.attributes["width"] == 1920
        assert span.attributes["height"] == 1080
        assert span.attributes["fps"] == 30

    def test_span_events(self):
        """测试 Span 事件记录。"""
        from core.ae_tracer import AETracer
        
        tracer = AETracer()
        span = tracer.start_span("test")
        
        span.add_event("step_start", step="preprocess")
        span.add_event("step_end", step="preprocess", duration=0.1)
        
        assert len(span.events) == 2
        assert span.events[0]["name"] == "step_start"
        assert span.events[0]["step"] == "preprocess"
        assert span.events[1]["name"] == "step_end"
        assert span.events[1]["duration"] == 0.1


# ---------------------------------------------------------------------------
# ae_operation 装饰器测试
# ---------------------------------------------------------------------------

class TestAeOperationDecorator:
    """AE 操作装饰器测试。"""

    def test_decorator_sync_success(self, mock_event_bus, mock_metrics):
        """测试同步函数装饰器 - 成功场景。"""
        from core.ae_tracer import ae_operation
        
        @ae_operation("test_operation")
        def test_func():
            return {"success": True, "channel_used": "mcp"}
        
        result = test_func()
        
        assert result == {"success": True, "channel_used": "mcp"}
        mock_event_bus.call_count == 2  # started + completed

    def test_decorator_sync_failure(self, mock_event_bus, mock_metrics):
        """测试同步函数装饰器 - 失败场景。"""
        from core.ae_tracer import ae_operation
        
        @ae_operation("test_operation")
        def test_func():
            raise ValueError("test error")
        
        with pytest.raises(ValueError, match="test error"):
            test_func()
        
        mock_metrics.increment.assert_called()

    @pytest.mark.asyncio
    async def test_decorator_async_success(self, mock_event_bus, mock_metrics):
        """测试异步函数装饰器 - 成功场景。"""
        from core.ae_tracer import ae_operation
        
        @ae_operation("async_operation")
        async def test_func():
            await asyncio.sleep(0.01)
            return {"success": True}
        
        result = await test_func()
        
        assert result == {"success": True}
        mock_event_bus.call_count == 2

    @pytest.mark.asyncio
    async def test_decorator_async_failure(self, mock_event_bus, mock_metrics):
        """测试异步函数装饰器 - 失败场景。"""
        from core.ae_tracer import ae_operation
        
        @ae_operation("async_operation")
        async def test_func():
            await asyncio.sleep(0.01)
            raise ValueError("async error")
        
        with pytest.raises(ValueError, match="async error"):
            await test_func()


# ---------------------------------------------------------------------------
# AETraceContext 上下文管理器测试
# ---------------------------------------------------------------------------

class TestAETraceContext:
    """AE 追踪上下文管理器测试。"""

    def test_context_manager_success(self, mock_event_bus, mock_metrics):
        """测试上下文管理器 - 成功场景。"""
        from core.ae_tracer import AETraceContext
        
        with AETraceContext("test_context") as ctx:
            assert ctx.trace_id is not None
            assert ctx.span is not None
            assert ctx.span.operation_name == "test_context"
        
        assert ctx.span.status == "success"

    def test_context_manager_failure(self, mock_event_bus, mock_metrics):
        """测试上下文管理器 - 失败场景。"""
        from core.ae_tracer import AETraceContext
        
        with pytest.raises(ValueError, match="context error"):
            with AETraceContext("test_context") as ctx:
                assert ctx.trace_id is not None
                raise ValueError("context error")
        
        assert ctx.span.status == "failed"
        assert ctx.span.error == "context error"

    def test_context_manager_trace_id_preservation(self):
        """测试上下文管理器保留 trace_id。"""
        from core.ae_tracer import AETraceContext, ae_tracer
        
        original_trace_id = ae_tracer.current_trace_id
        
        with AETraceContext("test_context", trace_id="abc123") as ctx:
            assert ctx.trace_id == "abc123"
        
        assert ae_tracer.current_trace_id == "abc123"


# ---------------------------------------------------------------------------
# 事件总线集成测试
# ---------------------------------------------------------------------------

class TestEventBusIntegration:
    """事件总线集成测试。"""

    def test_operation_started_event(self, mock_event_bus):
        """测试操作开始事件发布。"""
        from core.ae_tracer import AETracer
        
        tracer = AETracer()
        tracer.start_span("test_operation", channel="mcp")
        
        mock_event_bus.assert_called_once()
        args, kwargs = mock_event_bus.call_args
        assert args[0] == "operation.started"
        assert kwargs["payload"]["operation_name"] == "test_operation"
        assert kwargs["payload"]["channel"] == "mcp"
        assert kwargs["payload"]["trace_id"] is not None

    def test_operation_completed_event(self, mock_event_bus):
        """测试操作完成事件发布。"""
        from core.ae_tracer import AETracer
        
        tracer = AETracer()
        span = tracer.start_span("test_operation")
        tracer.end_span(span, "success")
        
        assert mock_event_bus.call_count == 2
        
        completed_call = mock_event_bus.call_args
        args, kwargs = completed_call
        assert args[0] == "operation.completed"
        assert kwargs["payload"]["status"] == "success"
        assert kwargs["payload"]["duration_ms"] >= 0

    def test_event_with_correlation_id(self, mock_event_bus):
        """测试事件关联 ID。"""
        from core.ae_tracer import AETracer
        
        tracer = AETracer()
        span = tracer.start_span("test_operation")
        span.set_attribute("correlation_id", "corr-123")
        tracer.end_span(span)
        
        calls = mock_event_bus.call_args_list
        for call in calls:
            args, kwargs = call
            payload = kwargs["payload"]
            assert payload["trace_id"] == span.trace_id


# ---------------------------------------------------------------------------
# 指标采集集成测试
# ---------------------------------------------------------------------------

class TestMetricsIntegration:
    """指标采集集成测试。"""

    def test_operation_metrics(self, mock_metrics):
        """测试操作指标采集。"""
        from core.ae_tracer import AETracer
        
        tracer = AETracer()
        span = tracer.start_span("create_composition", channel="mcp")
        time.sleep(0.01)
        tracer.end_span(span, "success")
        
        mock_metrics.increment.assert_any_call(
            "ae.operation.started", operation="create_composition"
        )
        mock_metrics.histogram.assert_any_call(
            "ae.operation.duration",
            span.duration_ms,
            operation="create_composition",
            status="success",
        )
        mock_metrics.increment.assert_any_call(
            "ae.operation.completed",
            operation="create_composition",
            status="success",
        )

    def test_error_metrics(self, mock_metrics):
        """测试错误指标采集。"""
        from core.ae_tracer import AETracer
        
        tracer = AETracer()
        span = tracer.start_span("test_operation")
        
        try:
            raise ValueError("test error")
        except ValueError as e:
            tracer.record_error(span, e)
        
        mock_metrics.increment.assert_called_with(
            "ae.operation.errors",
            operation="test_operation",
            error_type="ValueError",
        )


# ---------------------------------------------------------------------------
# BridgeClient 追踪集成测试
# ---------------------------------------------------------------------------

class TestBridgeClientTracing:
    """BridgeClient 追踪集成测试。"""

    def test_bridge_command_tracing(self, test_config):
        """测试 Bridge 命令追踪。"""
        from ae.bridge_protocol import BridgeClient, BridgeServer
        import shutil
        
        bridge_dir = test_config.output_dir / "test_bridge_tracing"
        if bridge_dir.exists():
            shutil.rmtree(bridge_dir, ignore_errors=True)
        bridge_dir.mkdir(parents=True, exist_ok=True)
        
        server = BridgeServer(
            bridge_dir=str(bridge_dir),
            signature_enabled=False,
            poll_interval=0.01,
            use_queue_mode=False,
        )
        server.register_handler("ping", lambda params: {"pong": True})
        
        server_thread = server.start_background()
        time.sleep(0.1)
        
        try:
            client = BridgeClient(
                bridge_dir=str(bridge_dir),
                signature_enabled=False,
                poll_interval=0.01,
                max_retries=1,
            )
            
            from core.ae_tracer import ae_tracer
            initial_trace_id = ae_tracer.current_trace_id
            
            response = client.send_command("ping")
            
            assert response.is_success
            assert ae_tracer._span_stack == []
            
        finally:
            server.stop()


# ---------------------------------------------------------------------------
# UnifiedAEClient 追踪集成测试
# ---------------------------------------------------------------------------

class TestUnifiedAEClientTracing:
    """UnifiedAEClient 追踪集成测试。"""

    def test_unified_client_tracing(self):
        """测试 UnifiedAEClient 追踪集成。"""
        from ae.unified_ae_client import UnifiedAEClient, AEOperation, AEChannel
        from core.ae_tracer import ae_tracer
        
        puppet_mock = Mock()
        puppet_mock.is_available.return_value = True
        puppet_mock.create_composition.return_value = {
            "success": True,
            "data": {"comp_id": "comp_1"},
            "channel": "puppet",
        }
        
        client = UnifiedAEClient(puppet_engine=puppet_mock)
        
        initial_stack_size = len(ae_tracer._span_stack)
        
        result = client.create_composition("TestComp", 1920, 1080)
        
        assert result["success"] is True
        assert len(ae_tracer._span_stack) == initial_stack_size

    def test_unified_client_tracing_fallback(self):
        """测试 UnifiedAEClient 降级追踪。"""
        from ae.unified_ae_client import UnifiedAEClient, AEChannel, AllChannelsFailedError
        from core.ae_tracer import ae_tracer
        
        puppet_mock = Mock()
        puppet_mock.is_available.return_value = True
        puppet_mock.create_composition.return_value = {
            "success": False, "error": "puppet failed"
        }
        
        client = UnifiedAEClient(puppet_engine=puppet_mock, enable_fallback=True)
        client.is_mcp_available = Mock(return_value=False)
        
        with pytest.raises(AllChannelsFailedError):
            client.create_composition("TestComp", 1920, 1080)
        
        assert len(ae_tracer._span_stack) == 0


# ---------------------------------------------------------------------------
# 健康检查事件测试
# ---------------------------------------------------------------------------

class TestHealthCheckEvents:
    """健康检查事件测试。"""

    def test_health_check_event(self, test_config):
        """测试健康检查事件发布。"""
        import shutil
        
        bridge_dir = test_config.output_dir / "test_health_check"
        if bridge_dir.exists():
            shutil.rmtree(bridge_dir, ignore_errors=True)
        bridge_dir.mkdir(parents=True, exist_ok=True)
        
        from ae.bridge_health import BridgeHealthMonitor
        
        monitor = BridgeHealthMonitor(bridge_dir=str(bridge_dir))
        
        from core.event_bus import event_bus
        
        received_events = []
        
        def handler(event):
            if event.event_type == "health.check":
                received_events.append(event)
        
        event_bus.subscribe(
            event_type="health.check",
            event_category=event_bus._category_subscribers.keys().__iter__().__next__() if event_bus._category_subscribers else None,
        )
        
        event_bus.subscribe_global(handler)
        
        try:
            report = monitor.check_health()
            
            assert report.score >= 0
            assert report.score <= 100
            
        finally:
            event_bus._global_subscribers.clear()


# ---------------------------------------------------------------------------
# 维护模块指标测试
# ---------------------------------------------------------------------------

class TestMaintenanceMetrics:
    """维护模块指标测试。"""

    def test_disk_cleaner_metrics(self, test_config):
        """测试磁盘清理指标。"""
        with patch("ae.archive.bridge_maintenance.global_metrics") as mock_metrics:
            from ae.archive.bridge_maintenance import DiskCleaner, DiskCleanerConfig
            
            bridge_dir = test_config.output_dir / "test_disk_cleaner"
            bridge_dir.mkdir(parents=True, exist_ok=True)
            
            config = DiskCleanerConfig(
                bridge_dir=str(bridge_dir),
                max_disk_usage=100,
                min_disk_usage=10,
                dry_run=True,
            )
            cleaner = DiskCleaner(config=config)
            
            cleaner._publish_cleanup_event(10, 50.0)
            
            mock_metrics.increment.assert_called_once_with(
                "ae.maintenance.disk_cleanup.files_deleted", 10
            )
            mock_metrics.summary.assert_called_once_with(
                "ae.maintenance.disk_cleanup.space_freed_mb", 50.0
            )
            mock_metrics.gauge.assert_called_once()

    def test_dlq_retry_metrics(self):
        """测试死信队列重试指标。"""
        with patch("ae.archive.bridge_maintenance.global_metrics") as mock_metrics:
            from ae.archive.bridge_maintenance import DeadLetterRetryService, RetryConfig
            
            config = RetryConfig(dry_run=True)
            retry_service = DeadLetterRetryService(config=config)
            
            retry_service._publish_retry_event("cmd_123", success=True)
            
            mock_metrics.increment.assert_any_call("ae.maintenance.dlq_retry.attempts")
            mock_metrics.increment.assert_any_call(
                "ae.maintenance.dlq_retry.results", status="success"
            )
            
            retry_service._publish_retry_event("cmd_456", success=False, error="timeout")
            
            mock_metrics.increment.assert_any_call(
                "ae.maintenance.dlq_retry.results", status="failure"
            )


# ---------------------------------------------------------------------------
# trace_id 贯穿测试
# ---------------------------------------------------------------------------

class TestTraceIdPropagation:
    """trace_id 贯穿调用链测试。"""

    def test_trace_id_through_operations(self):
        """测试 trace_id 在多个操作间传递。"""
        from core.ae_tracer import AETracer, ae_tracer
        
        tracer = AETracer()
        trace_id = tracer.current_trace_id
        
        span1 = tracer.start_span("operation_1")
        assert span1.trace_id == trace_id
        tracer.end_span(span1)
        
        span2 = tracer.start_span("operation_2")
        assert span2.trace_id == trace_id
        tracer.end_span(span2)
        
        assert tracer.current_trace_id == trace_id

    def test_trace_id_setter(self):
        """测试设置全局 trace_id。"""
        from core.ae_tracer import set_trace_id, get_trace_id
        
        new_trace_id = "custom_trace_12345"
        set_trace_id(new_trace_id)
        
        assert get_trace_id() == new_trace_id


# ---------------------------------------------------------------------------
# 便捷函数测试
# ---------------------------------------------------------------------------

class TestConvenienceFunctions:
    """便捷函数测试。"""

    def test_start_end_ae_operation(self):
        """测试便捷函数 start_ae_operation / end_ae_operation。"""
        from core.ae_tracer import start_ae_operation, end_ae_operation, ae_tracer
        
        span = start_ae_operation("test_op", channel="mcp")
        
        assert span.operation_name == "test_op"
        assert span.channel == "mcp"
        assert len(ae_tracer._span_stack) == 1
        
        end_ae_operation(span, "success")
        
        assert len(ae_tracer._span_stack) == 0
        assert span.status == "success"


# ---------------------------------------------------------------------------
# 集成测试：完整调用链
# ---------------------------------------------------------------------------

class TestFullTraceIntegration:
    """完整调用链集成测试。"""

    def test_full_trace_cycle(self, test_config):
        """测试完整的追踪生命周期。"""
        import shutil
        
        bridge_dir = test_config.output_dir / "test_full_trace"
        if bridge_dir.exists():
            shutil.rmtree(bridge_dir, ignore_errors=True)
        bridge_dir.mkdir(parents=True, exist_ok=True)
        
        from ae.bridge_protocol import BridgeServer
        from core.ae_tracer import AETraceContext, ae_tracer
        
        server = BridgeServer(
            bridge_dir=str(bridge_dir),
            signature_enabled=False,
            poll_interval=0.01,
            use_queue_mode=False,
        )
        server.register_handler("ping", lambda params: {"pong": True})
        server_thread = server.start_background()
        time.sleep(0.1)
        
        try:
            trace_id = None
            
            with AETraceContext("full_cycle_test") as ctx:
                trace_id = ctx.trace_id
                
                from ae.bridge_protocol import BridgeClient
                
                client = BridgeClient(
                    bridge_dir=str(bridge_dir),
                    signature_enabled=False,
                    poll_interval=0.01,
                    max_retries=1,
                )
                
                response = client.send_command("ping")
                
                assert response.is_success
            
            assert ctx.span.status == "success"
            assert ctx.span.trace_id == trace_id
            
        finally:
            server.stop()


# ---------------------------------------------------------------------------
# 性能测试
# ---------------------------------------------------------------------------

class TestPerformance:
    """追踪性能测试。"""

    def test_trace_overhead(self):
        """测试追踪开销。"""
        from core.ae_tracer import AETracer
        
        tracer = AETracer()
        
        start = time.time()
        for _ in range(100):
            span = tracer.start_span("test_op")
            tracer.end_span(span)
        elapsed = time.time() - start
        
        assert elapsed < 2.0, f"追踪 100 次操作耗时 {elapsed:.3f}s，超过预期"


__all__ = [
    "TestAETracer",
    "TestAeOperationDecorator",
    "TestAETraceContext",
    "TestEventBusIntegration",
    "TestMetricsIntegration",
    "TestBridgeClientTracing",
    "TestUnifiedAEClientTracing",
    "TestHealthCheckEvents",
    "TestMaintenanceMetrics",
    "TestTraceIdPropagation",
    "TestConvenienceFunctions",
    "TestFullTraceIntegration",
    "TestPerformance",
]