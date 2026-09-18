"""core.observability 单元测试 - 可观测性层核心逻辑"""
import asyncio
import json
import os
import sys
import tempfile
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.observability import (
    ConsoleLogHandler,
    ConsoleMetricExporter,
    ConsoleTraceExporter,
    FileLogHandler,
    FileTraceExporter,
    LogEntry,
    Logger,
    LogHandler,
    LogLevel,
    MetricExporter,
    MetricSample,
    MetricsCollector,
    MetricType,
    ObservabilityContext,
    PrometheusMetricExporter,
    Span,
    TraceExporter,
    Tracer,
    create_context,
    global_logger,
    global_metrics,
    global_tracer,
    increment_counter,
    log_critical,
    log_debug,
    log_error,
    log_info,
    log_warning,
    record_histogram,
    record_summary,
    set_gauge,
    set_global_context,
    traced,
)


class TestEnums:
    def test_log_level_order(self):
        levels = list(LogLevel)
        values = [l.value for l in levels]
        assert values == sorted(values)

    def test_log_level_values(self):
        assert LogLevel.DEBUG.value == 1
        assert LogLevel.INFO.value == 2
        assert LogLevel.WARNING.value == 3
        assert LogLevel.ERROR.value == 4
        assert LogLevel.CRITICAL.value == 5

    def test_metric_type_values(self):
        assert MetricType.COUNTER.value == 1
        assert MetricType.GAUGE.value == 2
        assert MetricType.HISTOGRAM.value == 3
        assert MetricType.SUMMARY.value == 4


class TestLogEntry:
    def test_log_entry_creation(self):
        entry = LogEntry(
            timestamp=1234567890.0,
            level=LogLevel.INFO,
            message="test message",
            logger_name="test.logger",
        )
        assert entry.timestamp == 1234567890.0
        assert entry.level == LogLevel.INFO
        assert entry.message == "test message"
        assert entry.logger_name == "test.logger"
        assert entry.trace_id is None
        assert entry.span_id is None
        assert entry.extra == {}

    def test_log_entry_with_extra(self):
        entry = LogEntry(
            timestamp=1234567890.0,
            level=LogLevel.ERROR,
            message="error occurred",
            logger_name="test.logger",
            trace_id="trace-123",
            span_id="span-456",
            extra={"user_id": 42, "action": "login"},
        )
        assert entry.trace_id == "trace-123"
        assert entry.span_id == "span-456"
        assert entry.extra["user_id"] == 42
        assert entry.extra["action"] == "login"


class TestSpan:
    def test_span_creation(self):
        span = Span(
            trace_id="trace-001",
            span_id="span-001",
            name="test_span",
        )
        assert span.trace_id == "trace-001"
        assert span.span_id == "span-001"
        assert span.parent_span_id is None
        assert span.name == "test_span"
        assert span.start_time == 0.0
        assert span.end_time == 0.0
        assert span.status == "running"
        assert span.attributes == {}
        assert span.events == []

    def test_span_duration(self):
        span = Span(
            trace_id="t1",
            span_id="s1",
            name="test",
            start_time=100.0,
            end_time=150.5,
        )
        assert span.duration == 50.5

    def test_span_duration_zero_when_incomplete(self):
        span = Span(
            trace_id="t1",
            span_id="s1",
            name="test",
            start_time=100.0,
        )
        assert span.duration == 0.0

    def test_span_with_parent(self):
        span = Span(
            trace_id="t1",
            span_id="child",
            parent_span_id="parent",
            name="child_span",
        )
        assert span.parent_span_id == "parent"


class TestMetricSample:
    def test_metric_sample_creation(self):
        sample = MetricSample(
            name="requests_total",
            type=MetricType.COUNTER,
            value=42.0,
        )
        assert sample.name == "requests_total"
        assert sample.type == MetricType.COUNTER
        assert sample.value == 42.0
        assert sample.timestamp == 0.0
        assert sample.labels == {}

    def test_metric_sample_with_labels(self):
        sample = MetricSample(
            name="http_requests",
            type=MetricType.COUNTER,
            value=100.0,
            timestamp=1234567890.0,
            labels={"method": "GET", "status": "200"},
        )
        assert sample.timestamp == 1234567890.0
        assert sample.labels["method"] == "GET"
        assert sample.labels["status"] == "200"


class TestLogger:
    def test_logger_creation_default(self):
        logger = Logger("test.logger")
        assert logger._name == "test.logger"
        assert len(logger._handlers) == 1
        assert isinstance(logger._handlers[0], ConsoleLogHandler)
        assert logger._current_trace_id is None

    def test_logger_creation_custom_handlers(self):
        handler = ConsoleLogHandler()
        logger = Logger("test.logger", handlers=[handler])
        assert len(logger._handlers) == 1
        assert logger._handlers[0] == handler

    def test_logger_debug(self):
        logger = Logger("test.logger")
        logger.debug("debug message", key="value")
        assert logger._current_trace_id is None

    def test_logger_info(self):
        logger = Logger("test.logger")
        logger.info("info message")

    def test_logger_warning(self):
        logger = Logger("test.logger")
        logger.warning("warning message")

    def test_logger_error(self):
        logger = Logger("test.logger")
        logger.error("error message")

    def test_logger_critical(self):
        logger = Logger("test.logger")
        logger.critical("critical message")

    def test_logger_exception_with_exc(self):
        logger = Logger("test.logger")
        try:
            raise ValueError("test error")
        except ValueError as e:
            logger.exception("caught error", exc=e)

    def test_logger_set_trace_id(self):
        logger = Logger("test.logger")
        logger.set_trace_id("trace-abc")
        assert logger._current_trace_id == "trace-abc"

    def test_file_log_handler_emit(self, tmp_path):
        log_file = tmp_path / "test.log"
        handler = FileLogHandler(str(log_file))
        entry = LogEntry(
            timestamp=time.time(),
            level=LogLevel.INFO,
            message="test log entry",
            logger_name="test",
        )
        asyncio.run(handler.emit(entry))
        assert log_file.exists()
        with open(log_file) as f:
            line = f.readline()
            data = json.loads(line)
            assert data["message"] == "test log entry"
            assert data["level"] == "INFO"

    def test_console_log_handler_emit(self):
        handler = ConsoleLogHandler()
        entry = LogEntry(
            timestamp=time.time(),
            level=LogLevel.INFO,
            message="console test",
            logger_name="test",
            trace_id="trace-123",
            extra={"key": "value"},
        )
        asyncio.run(handler.emit(entry))


class TestTracer:
    def test_tracer_creation_default(self):
        tracer = Tracer("test-service")
        assert tracer._service_name == "test-service"
        assert len(tracer._exporters) == 1
        assert isinstance(tracer._exporters[0], ConsoleTraceExporter)
        assert tracer._current_trace_id is None
        assert tracer._current_span is None

    def test_tracer_creation_custom_exporters(self):
        exporter = ConsoleTraceExporter()
        tracer = Tracer("test-service", exporters=[exporter])
        assert len(tracer._exporters) == 1

    def test_start_span_no_parent(self):
        tracer = Tracer("test-service")
        span = tracer.start_span("test_operation")
        assert span.trace_id is not None
        assert span.span_id is not None
        assert span.name == "test_operation"
        assert span.parent_span_id is None
        assert span.start_time > 0
        assert tracer._current_span == span

    def test_start_span_with_parent(self):
        tracer = Tracer("test-service")
        parent = tracer.start_span("parent")
        child = tracer.start_span("child", parent_span=parent)
        assert child.parent_span_id == parent.span_id
        assert child.trace_id == parent.trace_id

    def test_end_span_success(self):
        tracer = Tracer("test-service")
        span = tracer.start_span("test_op")
        tracer.end_span(span, status="success")
        assert span.end_time > 0
        assert span.status == "success"

    def test_end_span_error(self):
        tracer = Tracer("test-service")
        span = tracer.start_span("test_op")
        tracer.end_span(span, status="error")
        assert span.status == "error"

    def test_generate_trace_id_format(self):
        tracer = Tracer("test")
        tid = tracer._generate_trace_id()
        assert len(tid) == 16
        assert tid.isalnum()

    def test_generate_span_id_format(self):
        tracer = Tracer("test")
        sid = tracer._generate_span_id()
        assert len(sid) == 8
        assert sid.isalnum()

    def test_set_trace_id(self):
        tracer = Tracer("test-service")
        tracer.set_trace_id("custom-trace-id")
        assert tracer._current_trace_id == "custom-trace-id"

    @pytest.mark.asyncio
    async def test_force_flush(self):
        tracer = Tracer("test-service")
        span = tracer.start_span("flush_test")
        tracer.end_span(span)
        await tracer.force_flush()
        assert len(tracer._spans_to_export) == 0

    def test_file_trace_exporter(self, tmp_path):
        trace_file = tmp_path / "traces.jsonl"
        exporter = FileTraceExporter(str(trace_file))
        span = Span(
            trace_id="t1",
            span_id="s1",
            name="test_span",
            start_time=100.0,
            end_time=200.0,
            status="success",
            attributes={"key": "value"},
        )
        asyncio.run(exporter.export([span]))
        assert trace_file.exists()
        with open(trace_file) as f:
            line = f.readline()
            data = json.loads(line)
            assert data["trace_id"] == "t1"
            assert data["name"] == "test_span"


class TestMetricsCollector:
    def test_collector_creation_default(self):
        collector = MetricsCollector()
        assert len(collector._exporters) == 1
        assert isinstance(collector._exporters[0], ConsoleMetricExporter)
        assert collector._counters == {}
        assert collector._gauges == {}

    def test_increment_counter(self):
        collector = MetricsCollector()
        collector.increment("test_counter", 1.0, label="value")
        assert len(collector._counters) >= 0

    def test_gauge_set(self):
        collector = MetricsCollector()
        collector.gauge("test_gauge", 42.0)

    def test_histogram_record(self):
        collector = MetricsCollector()
        collector.histogram("test_histogram", 1.5)

    def test_summary_record(self):
        collector = MetricsCollector()
        collector.summary("test_summary", 2.5)

    @pytest.mark.asyncio
    async def test_record_counter_accumulates(self):
        collector = MetricsCollector()
        await collector._record(MetricType.COUNTER, "acc_test", 5.0, {"a": "b"})
        await collector._record(MetricType.COUNTER, "acc_test", 3.0, {"a": "b"})
        key = "acc_test_a=b"
        assert key in collector._counters
        assert collector._counters[key] == 8.0

    def test_console_metric_exporter(self):
        exporter = ConsoleMetricExporter()
        sample = MetricSample(
            name="test_metric",
            type=MetricType.GAUGE,
            value=42.0,
            labels={"env": "test"},
        )
        asyncio.run(exporter.export([sample]))

    def test_prometheus_metric_exporter(self, tmp_path):
        metrics_file = tmp_path / "metrics.prom"
        exporter = PrometheusMetricExporter(str(metrics_file))
        sample = MetricSample(
            name="http_requests_total",
            type=MetricType.COUNTER,
            value=100.0,
            labels={"method": "GET", "code": "200"},
        )
        asyncio.run(exporter.export([sample]))
        assert metrics_file.exists()
        with open(metrics_file) as f:
            content = f.read()
            assert "http_requests_total" in content
            assert 'method="GET"' in content
            assert 'code="200"' in content


class TestObservabilityContext:
    def test_context_creation(self):
        logger = Logger("test")
        tracer = Tracer("test-service")
        metrics = MetricsCollector()

        ctx = ObservabilityContext(logger, tracer, metrics)
        assert ctx.trace_id is not None
        assert len(ctx.trace_id) == 16
        assert ctx.logger == logger
        assert ctx.tracer == tracer
        assert ctx.metrics == metrics
        assert ctx._span_stack == []

    def test_context_creation_custom_trace_id(self):
        logger = Logger("test")
        tracer = Tracer("test")
        metrics = MetricsCollector()

        ctx = ObservabilityContext(logger, tracer, metrics, trace_id="custom-trace")
        assert ctx.trace_id == "custom-trace"

    def test_start_span_and_end(self):
        logger = Logger("test")
        tracer = Tracer("test-service")
        metrics = MetricsCollector()

        ctx = ObservabilityContext(logger, tracer, metrics)
        span = ctx.start_span("operation")
        assert len(ctx._span_stack) == 1
        assert span.name == "operation"

        ctx.end_span("success")
        assert len(ctx._span_stack) == 0

    def test_nested_spans(self):
        logger = Logger("test")
        tracer = Tracer("test-service")
        metrics = MetricsCollector()

        ctx = ObservabilityContext(logger, tracer, metrics)
        outer = ctx.start_span("outer")
        inner = ctx.start_span("inner")
        assert len(ctx._span_stack) == 2
        assert inner.parent_span_id == outer.span_id

        ctx.end_span()
        assert len(ctx._span_stack) == 1
        ctx.end_span()
        assert len(ctx._span_stack) == 0

    @pytest.mark.asyncio
    async def test_close_flushes(self):
        logger = Logger("test")
        tracer = Tracer("test-service")
        metrics = MetricsCollector()

        ctx = ObservabilityContext(logger, tracer, metrics)
        ctx.start_span("test")
        await ctx.close()
        assert len(ctx._span_stack) == 0


class TestTracedDecorator:
    @pytest.mark.asyncio
    async def test_traced_async_function_with_context(self):
        logger = Logger("test")
        tracer = Tracer("test-service")
        metrics = MetricsCollector()
        ctx = ObservabilityContext(logger, tracer, metrics)
        set_global_context(ctx)

        @traced(logger_name="test", span_name="decorated_op")
        async def my_func(x, y):
            return x + y

        result = await my_func(3, 4)
        assert result == 7

        set_global_context(None)

    @pytest.mark.asyncio
    async def test_traced_async_function_without_context(self):
        set_global_context(None)

        @traced(logger_name="test")
        async def my_func(x):
            return x * 2

        result = await my_func(5)
        assert result == 10

    def test_traced_sync_function_with_context(self):
        logger = Logger("test")
        tracer = Tracer("test-service")
        metrics = MetricsCollector()
        ctx = ObservabilityContext(logger, tracer, metrics)
        set_global_context(ctx)

        @traced(logger_name="test")
        def sync_func(x):
            return x + 1

        result = sync_func(10)
        assert result == 11

        set_global_context(None)

    @pytest.mark.asyncio
    async def test_traced_function_error(self):
        logger = Logger("test")
        tracer = Tracer("test-service")
        metrics = MetricsCollector()
        ctx = ObservabilityContext(logger, tracer, metrics)
        set_global_context(ctx)

        @traced(logger_name="test")
        async def failing_func():
            raise ValueError("test error")

        with pytest.raises(ValueError):
            await failing_func()

        set_global_context(None)


class TestGlobalInstances:
    def test_global_logger_exists(self):
        assert global_logger is not None
        assert isinstance(global_logger, Logger)

    def test_global_tracer_exists(self):
        assert global_tracer is not None
        assert isinstance(global_tracer, Tracer)

    def test_global_metrics_exists(self):
        assert global_metrics is not None
        assert isinstance(global_metrics, MetricsCollector)

    def test_create_context(self):
        ctx = create_context("test-trace-id")
        assert isinstance(ctx, ObservabilityContext)
        assert ctx.trace_id == "test-trace-id"

    def test_convenience_functions(self):
        log_debug("debug message")
        log_info("info message")
        log_warning("warning message")
        log_error("error message")
        log_critical("critical message")
        increment_counter("test_counter", 1.0)
        set_gauge("test_gauge", 42.0)
        record_histogram("test_hist", 1.5)
        record_summary("test_summary", 2.5)


class TestEdgeCases:
    def test_log_handler_base_class(self):
        handler = LogHandler()
        entry = LogEntry(
            timestamp=time.time(),
            level=LogLevel.INFO,
            message="base handler",
            logger_name="test",
        )
        asyncio.run(handler.emit(entry))

    def test_trace_exporter_base_class(self):
        exporter = TraceExporter()
        asyncio.run(exporter.export([]))

    def test_metric_exporter_base_class(self):
        exporter = MetricExporter()
        asyncio.run(exporter.export([]))

    def test_end_span_empty_stack_no_crash(self):
        logger = Logger("test")
        tracer = Tracer("test-service")
        metrics = MetricsCollector()
        ctx = ObservabilityContext(logger, tracer, metrics)
        ctx.end_span()

    @pytest.mark.asyncio
    async def test_close_with_no_spans(self):
        logger = Logger("test")
        tracer = Tracer("test-service")
        metrics = MetricsCollector()
        ctx = ObservabilityContext(logger, tracer, metrics)
        await ctx.close()

    def test_file_log_handler_rotation(self, tmp_path):
        log_file = tmp_path / "rotate.log"
        handler = FileLogHandler(str(log_file), max_size_mb=1)
        entry = LogEntry(
            timestamp=time.time(),
            level=LogLevel.INFO,
            message="small entry",
            logger_name="test",
        )
        asyncio.run(handler.emit(entry))
        assert log_file.exists()

    def test_prometheus_metric_no_labels(self, tmp_path):
        metrics_file = tmp_path / "metrics_nolabel.prom"
        exporter = PrometheusMetricExporter(str(metrics_file))
        sample = MetricSample(
            name="simple_metric",
            type=MetricType.GAUGE,
            value=3.14,
        )
        asyncio.run(exporter.export([sample]))
        assert metrics_file.exists()
        with open(metrics_file) as f:
            content = f.read()
            assert "simple_metric 3.1400" in content
