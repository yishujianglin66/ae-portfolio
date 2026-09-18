"""core.ae_tracer 单元测试 - AE 专用追踪工具"""
import asyncio
import os
import sys
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.ae_tracer import (
    AEOperationSpan,
    AETraceContext,
    AETracer,
    ae_operation,
    ae_tracer,
    end_ae_operation,
    get_trace_id,
    set_trace_id,
    start_ae_operation,
)


@pytest.fixture
def mock_metrics():
    with patch("core.ae_tracer.global_metrics") as m:
        m.increment = MagicMock()
        m.histogram = MagicMock()
        yield m


@pytest.fixture
def mock_tracer():
    with patch("core.ae_tracer.global_tracer") as m:
        mock_span = MagicMock()
        mock_span.attributes = {}
        m.start_span = MagicMock(return_value=mock_span)
        m.end_span = MagicMock()
        yield m


@pytest.fixture
def mock_publish():
    with patch("core.ae_tracer.publish_ae_event") as m:
        yield m


class TestAEOperationSpan:
    def test_duration_ms_normal(self):
        span = AEOperationSpan(
            trace_id="t1",
            span_id="s1",
            start_time=100.0,
            end_time=150.5,
        )
        assert span.duration_ms == 50500.0

    def test_duration_ms_end_before_start(self):
        span = AEOperationSpan(
            trace_id="t1",
            span_id="s1",
            start_time=200.0,
            end_time=100.0,
        )
        assert span.duration_ms == 0.0

    def test_duration_ms_zero_when_incomplete(self):
        span = AEOperationSpan(
            trace_id="t1",
            span_id="s1",
            start_time=100.0,
        )
        assert span.duration_ms == 0.0

    def test_set_attribute(self):
        span = AEOperationSpan(trace_id="t1", span_id="s1")
        span.set_attribute("key1", "value1")
        span.set_attribute("key2", 42)
        assert span.attributes["key1"] == "value1"
        assert span.attributes["key2"] == 42

    def test_add_event(self):
        span = AEOperationSpan(trace_id="t1", span_id="s1")
        with patch("core.ae_tracer.time.time", return_value=12345.0):
            span.add_event("render_start", layer="bg", frame=0)
        assert len(span.events) == 1
        assert span.events[0]["name"] == "render_start"
        assert span.events[0]["timestamp"] == 12345.0
        assert span.events[0]["layer"] == "bg"
        assert span.events[0]["frame"] == 0

    def test_add_event_multiple(self):
        span = AEOperationSpan(trace_id="t1", span_id="s1")
        span.add_event("evt1")
        span.add_event("evt2")
        assert len(span.events) == 2
        assert span.events[0]["name"] == "evt1"
        assert span.events[1]["name"] == "evt2"

    def test_record_success(self):
        span = AEOperationSpan(trace_id="t1", span_id="s1", status="running")
        with patch("core.ae_tracer.time.time", return_value=999.0):
            span.record_success()
        assert span.status == "success"
        assert span.end_time == 999.0
        assert span.error is None

    def test_record_failure_with_error(self):
        span = AEOperationSpan(trace_id="t1", span_id="s1", status="running")
        with patch("core.ae_tracer.time.time", return_value=888.0):
            span.record_failure("something went wrong")
        assert span.status == "failed"
        assert span.end_time == 888.0
        assert span.error == "something went wrong"

    def test_record_failure_empty_error(self):
        span = AEOperationSpan(trace_id="t1", span_id="s1", status="running")
        span.record_failure()
        assert span.status == "failed"
        assert span.error == ""

    def test_span_default_values(self):
        span = AEOperationSpan(trace_id="t1", span_id="s1")
        assert span.parent_span_id is None
        assert span.operation_name == ""
        assert span.channel == ""
        assert span.status == "running"
        assert span.start_time == 0.0
        assert span.end_time == 0.0
        assert span.attributes == {}
        assert span.events == []
        assert span.error is None


class TestAETracerInit:
    def test_init_default_service_name(self):
        tracer = AETracer()
        assert tracer._service_name == "ae-bridge"
        assert tracer._current_trace_id is None
        assert tracer._current_span is None
        assert tracer._span_stack == []

    def test_init_custom_service_name(self):
        tracer = AETracer(service_name="custom-service")
        assert tracer._service_name == "custom-service"


class TestAETracerTraceId:
    def test_current_trace_id_lazy_generation(self):
        tracer = AETracer()
        assert tracer._current_trace_id is None
        tid = tracer.current_trace_id
        assert tid is not None
        assert len(tid) == 16
        assert tracer._current_trace_id == tid

    def test_current_trace_id_cached(self):
        tracer = AETracer()
        tid1 = tracer.current_trace_id
        tid2 = tracer.current_trace_id
        assert tid1 == tid2

    def test_current_trace_id_setter(self):
        tracer = AETracer()
        tracer.current_trace_id = "my-custom-id"
        assert tracer._current_trace_id == "my-custom-id"
        assert tracer.current_trace_id == "my-custom-id"

    def test_current_trace_id_setter_overrides_lazy(self):
        tracer = AETracer()
        _ = tracer.current_trace_id
        tracer.current_trace_id = "override-id"
        assert tracer.current_trace_id == "override-id"


class TestAETracerStartSpan:
    def test_start_span_creates_span(self, mock_metrics, mock_publish):
        tracer = AETracer()
        with patch("core.ae_tracer.time.time", return_value=100.0):
            span = tracer.start_span("test_op")
        assert span.operation_name == "test_op"
        assert span.trace_id is not None
        assert span.span_id is not None
        assert span.status == "running"
        assert span.start_time == 100.0
        assert span.parent_span_id is None

    def test_start_span_pushes_to_stack(self, mock_metrics, mock_publish):
        tracer = AETracer()
        span = tracer.start_span("op1")
        assert len(tracer._span_stack) == 1
        assert tracer._current_span == span
        assert tracer._span_stack[0] == span

    def test_start_span_with_trace_id(self, mock_metrics, mock_publish):
        tracer = AETracer()
        span = tracer.start_span("op", trace_id="trace-abc")
        assert span.trace_id == "trace-abc"
        assert tracer._current_trace_id == "trace-abc"

    def test_start_span_with_custom_parent(self, mock_metrics, mock_publish):
        tracer = AETracer()
        parent = AEOperationSpan(trace_id="t1", span_id="parent-span")
        child = tracer.start_span("child", parent_span=parent)
        assert child.parent_span_id == "parent-span"
        assert child.trace_id == tracer.current_trace_id

    def test_start_span_nested_parent_from_stack(self, mock_metrics, mock_publish):
        tracer = AETracer()
        outer = tracer.start_span("outer")
        inner = tracer.start_span("inner")
        assert inner.parent_span_id == outer.span_id
        assert len(tracer._span_stack) == 2
        assert tracer._current_span == inner

    def test_start_span_passes_attributes(self, mock_metrics, mock_publish):
        tracer = AETracer()
        span = tracer.start_span("op", foo="bar", num=42)
        assert span.attributes["foo"] == "bar"
        assert span.attributes["num"] == 42

    def test_start_span_with_channel(self, mock_metrics, mock_publish):
        tracer = AETracer()
        span = tracer.start_span("op", channel="ae")
        assert span.channel == "ae"

    def test_start_span_records_metric(self, mock_metrics, mock_publish):
        tracer = AETracer()
        tracer.start_span("test_op")
        mock_metrics.increment.assert_called()
        call_args = mock_metrics.increment.call_args
        assert call_args[0][0] == "ae.operation.started"
        assert call_args[1]["operation"] == "test_op"

    def test_start_span_publishes_event(self, mock_metrics, mock_publish):
        tracer = AETracer()
        tracer.start_span("test_op")
        mock_publish.assert_called()
        call_args = mock_publish.call_args
        assert call_args[0][0] == "operation.started"
        assert call_args[1]["payload"]["operation_name"] == "test_op"


class TestAETracerEndSpan:
    def test_end_span_sets_status_and_time(self, mock_metrics, mock_tracer, mock_publish):
        tracer = AETracer()
        span = tracer.start_span("op")
        with patch("core.ae_tracer.time.time", return_value=200.0):
            tracer.end_span(span, status="success")
        assert span.status == "success"
        assert span.end_time == 200.0

    def test_end_span_removes_from_stack(self, mock_metrics, mock_tracer, mock_publish):
        tracer = AETracer()
        span = tracer.start_span("op")
        assert len(tracer._span_stack) == 1
        tracer.end_span(span)
        assert len(tracer._span_stack) == 0
        assert tracer._current_span is None

    def test_end_span_nested_restores_parent(self, mock_metrics, mock_tracer, mock_publish):
        tracer = AETracer()
        outer = tracer.start_span("outer")
        inner = tracer.start_span("inner")
        assert tracer._current_span == inner
        tracer.end_span(inner)
        assert tracer._current_span == outer
        assert len(tracer._span_stack) == 1
        tracer.end_span(outer)
        assert tracer._current_span is None
        assert len(tracer._span_stack) == 0

    def test_end_span_none_uses_current(self, mock_metrics, mock_tracer, mock_publish):
        tracer = AETracer()
        span = tracer.start_span("op")
        tracer.end_span(None)
        assert span.status == "success"
        assert len(tracer._span_stack) == 0

    def test_end_span_none_when_no_current_no_error(self, mock_metrics, mock_tracer, mock_publish):
        tracer = AETracer()
        tracer.end_span(None)

    def test_end_span_records_duration_metric(self, mock_metrics, mock_tracer, mock_publish):
        tracer = AETracer()
        span = tracer.start_span("op")
        span.start_time = 100.0
        span.end_time = 200.0
        tracer.end_span(span, status="success")
        mock_metrics.histogram.assert_called()
        call_args = mock_metrics.histogram.call_args
        assert call_args[0][0] == "ae.operation.duration"
        assert call_args[1]["operation"] == "op"
        assert call_args[1]["status"] == "success"

    def test_end_span_records_completed_metric(self, mock_metrics, mock_tracer, mock_publish):
        tracer = AETracer()
        span = tracer.start_span("op")
        tracer.end_span(span, status="failed")
        assert mock_metrics.increment.call_count >= 2
        completed_call = None
        for call in mock_metrics.increment.call_args_list:
            if call[0][0] == "ae.operation.completed":
                completed_call = call
                break
        assert completed_call is not None
        assert completed_call[1]["operation"] == "op"
        assert completed_call[1]["status"] == "failed"

    def test_end_span_publishes_completed_event(self, mock_metrics, mock_tracer, mock_publish):
        tracer = AETracer()
        span = tracer.start_span("op")
        mock_publish.reset_mock()
        tracer.end_span(span)
        mock_publish.assert_called()
        call_args = mock_publish.call_args
        assert call_args[0][0] == "operation.completed"


class TestAETracerRecordError:
    def test_record_error_sets_failure(self, mock_metrics):
        tracer = AETracer()
        span = AEOperationSpan(trace_id="t1", span_id="s1", operation_name="test_op")
        err = ValueError("test error message")
        tracer.record_error(span, err)
        assert span.status == "failed"
        assert span.error == "test error message"
        assert span.attributes["error_type"] == "ValueError"
        assert span.attributes["error_message"] == "test error message"

    def test_record_error_records_metric(self, mock_metrics):
        tracer = AETracer()
        span = AEOperationSpan(trace_id="t1", span_id="s1", operation_name="render_op")
        err = RuntimeError("crash")
        tracer.record_error(span, err)
        mock_metrics.increment.assert_called()
        call_args = mock_metrics.increment.call_args
        assert call_args[0][0] == "ae.operation.errors"
        assert call_args[1]["operation"] == "render_op"
        assert call_args[1]["error_type"] == "RuntimeError"


class TestAETracerActiveSpans:
    def test_get_active_spans_empty(self, mock_metrics, mock_publish):
        tracer = AETracer()
        spans = tracer.get_active_spans()
        assert spans == []

    def test_get_active_spans_single(self, mock_metrics, mock_publish):
        tracer = AETracer()
        span = tracer.start_span("op")
        spans = tracer.get_active_spans()
        assert len(spans) == 1
        assert spans[0] == span

    def test_get_active_spans_returns_copy(self, mock_metrics, mock_publish):
        tracer = AETracer()
        tracer.start_span("op")
        spans = tracer.get_active_spans()
        spans.append("fake")
        assert len(tracer._span_stack) == 1


class TestAETracerNestedSpans:
    def test_three_level_nesting(self, mock_metrics, mock_tracer, mock_publish):
        tracer = AETracer()
        l1 = tracer.start_span("level1")
        l2 = tracer.start_span("level2")
        l3 = tracer.start_span("level3")

        assert l2.parent_span_id == l1.span_id
        assert l3.parent_span_id == l2.span_id
        assert len(tracer._span_stack) == 3
        assert tracer._current_span == l3

        tracer.end_span(l3)
        assert tracer._current_span == l2
        assert len(tracer._span_stack) == 2

        tracer.end_span(l2)
        assert tracer._current_span == l1
        assert len(tracer._span_stack) == 1

        tracer.end_span(l1)
        assert tracer._current_span is None
        assert len(tracer._span_stack) == 0

    def test_sibling_spans_share_parent(self, mock_metrics, mock_tracer, mock_publish):
        tracer = AETracer()
        parent = tracer.start_span("parent")
        child1 = tracer.start_span("child1")
        tracer.end_span(child1)
        child2 = tracer.start_span("child2")

        assert child1.parent_span_id == parent.span_id
        assert child2.parent_span_id == parent.span_id
        assert child1.span_id != child2.span_id
        assert tracer._current_span == child2

    def test_trace_id_consistent_through_nesting(self, mock_metrics, mock_tracer, mock_publish):
        tracer = AETracer()
        tracer.current_trace_id = "fixed-trace-id"
        outer = tracer.start_span("outer")
        inner = tracer.start_span("inner")
        assert outer.trace_id == "fixed-trace-id"
        assert inner.trace_id == "fixed-trace-id"


class TestAEOperationDecoratorSync:
    def test_sync_decorator_normal_return(self, mock_metrics, mock_tracer, mock_publish):
        tracer = AETracer()

        @ae_operation("sync_op")
        def my_func(x, y):
            return x + y

        result = my_func(3, 4, _tracer=tracer)
        assert result == 7
        assert len(tracer._span_stack) == 0

    def test_sync_decorator_propagates_exception(self, mock_metrics, mock_tracer, mock_publish):
        tracer = AETracer()

        @ae_operation("failing_op")
        def my_func():
            raise ValueError("sync error")

        with pytest.raises(ValueError, match="sync error"):
            my_func(_tracer=tracer)
        assert len(tracer._span_stack) == 0

    def test_sync_decorator_result_dict_success(self, mock_metrics, mock_tracer, mock_publish):
        tracer = AETracer()

        @ae_operation("dict_op")
        def my_func():
            return {"success": True, "channel_used": "deepseek", "data": 123}

        result = my_func(_tracer=tracer)
        assert result["success"] is True
        active = tracer.get_active_spans()
        assert len(active) == 0

    def test_sync_decorator_result_dict_no_channel(self, mock_metrics, mock_tracer, mock_publish):
        tracer = AETracer()

        @ae_operation("dict_op2")
        def my_func():
            return {"success": False}

        result = my_func(_tracer=tracer)
        assert result["success"] is False

    def test_sync_decorator_default_name_from_func(self, mock_metrics, mock_tracer, mock_publish):
        tracer = AETracer()

        @ae_operation()
        def custom_name_func():
            return 42

        result = custom_name_func(_tracer=tracer)
        assert result == 42

    def test_sync_decorator_with_span_attrs(self, mock_metrics, mock_tracer, mock_publish):
        tracer = AETracer()

        @ae_operation("attrs_op")
        def my_func(**kwargs):
            return "ok"

        result = my_func(_tracer=tracer, span_attrs={"layer": "bg", "comp": "Test"})
        assert result == "ok"
        assert len(tracer._span_stack) == 0


class TestAEOperationDecoratorAsync:
    @pytest.mark.asyncio
    async def test_async_decorator_normal_return(self, mock_metrics, mock_tracer, mock_publish):
        tracer = AETracer()

        @ae_operation("async_op")
        async def my_func(x, y):
            return x * y

        result = await my_func(3, 4, _tracer=tracer)
        assert result == 12
        assert len(tracer._span_stack) == 0

    @pytest.mark.asyncio
    async def test_async_decorator_propagates_exception(self, mock_metrics, mock_tracer, mock_publish):
        tracer = AETracer()

        @ae_operation("async_fail")
        async def my_func():
            raise RuntimeError("async error")

        with pytest.raises(RuntimeError, match="async error"):
            await my_func(_tracer=tracer)
        assert len(tracer._span_stack) == 0

    @pytest.mark.asyncio
    async def test_async_decorator_result_dict_channel(self, mock_metrics, mock_tracer, mock_publish):
        tracer = AETracer()

        @ae_operation("async_dict")
        async def my_func():
            return {"success": True, "channel_used": "doubao"}

        result = await my_func(_tracer=tracer)
        assert result["channel_used"] == "doubao"


class TestAETraceContext:
    def test_enter_exit_normal(self, mock_metrics, mock_tracer, mock_publish):
        tracer = AETracer()
        with AETraceContext("ctx_op", tracer=tracer) as ctx:
            assert ctx.span is not None
            assert ctx.span.operation_name == "ctx_op"
            assert len(tracer._span_stack) == 1
        assert len(tracer._span_stack) == 0
        assert ctx.span.status == "success"

    def test_exit_with_exception_marks_failed(self, mock_metrics, mock_tracer, mock_publish):
        tracer = AETracer()
        ctx = None
        with pytest.raises(ValueError, match="ctx error"):
            with AETraceContext("fail_ctx", tracer=tracer) as c:
                ctx = c
                raise ValueError("ctx error")
        assert ctx.span.status == "failed"
        assert ctx.span.error == "ctx error"
        assert len(tracer._span_stack) == 0

    def test_trace_id_property_with_span(self, mock_metrics, mock_publish):
        tracer = AETracer()
        with AETraceContext("tid_op", trace_id="ctx-trace-123", tracer=tracer) as ctx:
            assert ctx.trace_id == "ctx-trace-123"

    def test_trace_id_property_without_span(self):
        tracer = AETracer()
        tracer.current_trace_id = "pre-set-id"
        ctx = AETraceContext("test", tracer=tracer)
        assert ctx.trace_id == "pre-set-id"

    def test_span_property_none_before_enter(self):
        tracer = AETracer()
        ctx = AETraceContext("test", tracer=tracer)
        assert ctx.span is None

    def test_with_attributes(self, mock_metrics, mock_tracer, mock_publish):
        tracer = AETracer()
        with AETraceContext("attr_op", tracer=tracer, foo="bar", num=99) as ctx:
            assert ctx.span.attributes["foo"] == "bar"
            assert ctx.span.attributes["num"] == 99


class TestConvenienceFunctions:
    def test_start_ae_operation(self, mock_metrics, mock_publish):
        with patch("core.ae_tracer.ae_tracer") as mock_global:
            mock_span = MagicMock()
            mock_global.start_span = MagicMock(return_value=mock_span)
            result = start_ae_operation("test_op", trace_id="t1", channel="ch", key="val")
            mock_global.start_span.assert_called_once_with(
                "test_op", trace_id="t1", channel="ch", key="val"
            )
            assert result == mock_span

    def test_end_ae_operation(self, mock_metrics):
        with patch("core.ae_tracer.ae_tracer") as mock_global:
            span = MagicMock()
            end_ae_operation(span, status="failed")
            mock_global.end_span.assert_called_once_with(span, "failed")

    def test_set_trace_id(self, mock_metrics):
        tracer = AETracer()
        with patch("core.ae_tracer.ae_tracer", tracer):
            set_trace_id("new-trace-id")
            assert tracer._current_trace_id == "new-trace-id"

    def test_get_trace_id(self):
        with patch("core.ae_tracer.ae_tracer") as mock_global:
            type(mock_global).current_trace_id = PropertyMock(return_value="got-trace-id")
            result = get_trace_id()
            assert result == "got-trace-id"
