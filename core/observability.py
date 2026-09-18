#!/usr/bin/env python3
"""
可观测性层核心 - Logger/Tracker/Metrics v1.0

设计原则（基于 OpenTelemetry 标准）：
1. 统一接口：日志、追踪、指标使用一致的 API 风格
2. 可插拔：支持多种后端输出（控制台、文件、Prometheus、ELK）
3. 低侵入：通过装饰器和上下文管理器集成
4. 高性能：异步写入，批量发送，不阻塞主流程
5. 可关联：日志、追踪、指标共享同一 trace_id

三大支柱：
- Logs（日志）：结构化事件记录，用于问题排查
- Traces（追踪）：分布式调用链追踪，用于性能分析
- Metrics（指标）：数值型数据收集，用于监控告警

架构参考：
- OpenTelemetry Specification
- Prometheus Metrics Format
- Zipkin Trace Format
- ELK Stack Log Format
"""
import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Union


class LogLevel(Enum):
    """日志级别"""
    DEBUG = auto()
    INFO = auto()
    WARNING = auto()
    ERROR = auto()
    CRITICAL = auto()


class MetricType(Enum):
    """指标类型"""
    COUNTER = auto()      # 累加计数器
    GAUGE = auto()        # 瞬时值
    HISTOGRAM = auto()    # 分布直方图
    SUMMARY = auto()      # 摘要统计


@dataclass
class LogEntry:
    """日志条目"""
    timestamp: float
    level: LogLevel
    message: str
    logger_name: str
    trace_id: str | None = None
    span_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Span:
    """追踪 Span"""
    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    name: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    status: str = "running"
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)

    @property
    def duration(self) -> float:
        return max(0, self.end_time - self.start_time)


@dataclass
class MetricSample:
    """指标样本"""
    name: str
    type: MetricType
    value: float
    timestamp: float = 0.0
    labels: dict[str, str] = field(default_factory=dict)


# -----------------------------------------------------------------------------
# 工具函数
# -----------------------------------------------------------------------------

def _safe_async(coro):
    """安全地运行协程 - 有事件循环时创建任务，否则用 asyncio.run 同步执行"""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(coro)
    except RuntimeError:
        try:
            asyncio.run(coro)
        except Exception:
            pass


# -----------------------------------------------------------------------------
# 日志系统
# -----------------------------------------------------------------------------

class LogHandler:
    """日志处理器接口"""
    async def emit(self, entry: LogEntry) -> None:
        pass


class ConsoleLogHandler(LogHandler):
    """控制台日志处理器"""
    async def emit(self, entry: LogEntry) -> None:
        level_str = entry.level.name.ljust(10)
        time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(entry.timestamp))
        trace_str = f" [{entry.trace_id}]" if entry.trace_id else ""
        extra_str = ""
        if entry.extra:
            extra_str = " " + json.dumps(entry.extra, ensure_ascii=False, separators=(",", ":"))
        print(f"{time_str}{trace_str} [{level_str}] {entry.logger_name}: {entry.message}{extra_str}")


class FileLogHandler(LogHandler):
    """文件日志处理器"""
    def __init__(self, file_path: str, max_size_mb: int = 100):
        self._file_path = file_path
        self._max_size_bytes = max_size_mb * 1024 * 1024
        self._lock = asyncio.Lock()

    async def emit(self, entry: LogEntry) -> None:
        async with self._lock:
            await self._rotate_if_needed()
            with open(self._file_path, "a", encoding="utf-8") as f:
                entry_dict = entry.__dict__.copy()
                entry_dict["level"] = entry.level.name
                f.write(json.dumps(entry_dict, ensure_ascii=False) + "\n")

    async def _rotate_if_needed(self) -> None:
        try:
            if os.path.exists(self._file_path) and os.path.getsize(self._file_path) > self._max_size_bytes:
                backup_path = f"{self._file_path}.{time.strftime('%Y%m%d_%H%M%S')}"
                os.rename(self._file_path, backup_path)
        except Exception:
            pass


class Logger:
    """结构化日志器"""
    def __init__(self, name: str, handlers: list[LogHandler] = None):
        self._name = name
        self._handlers = handlers or [ConsoleLogHandler()]
        self._current_trace_id = None

    def _log(self, level: LogLevel, message: str, **extra) -> None:
        entry = LogEntry(
            timestamp=time.time(),
            level=level,
            message=message,
            logger_name=self._name,
            trace_id=self._current_trace_id,
            extra=extra,
        )
        _safe_async(self._emit(entry))

    async def _emit(self, entry: LogEntry) -> None:
        for handler in self._handlers:
            try:
                await handler.emit(entry)
            except Exception as e:
                print(f"Log handler error: {e}")

    def debug(self, message: str, **extra) -> None:
        self._log(LogLevel.DEBUG, message, **extra)

    def info(self, message: str, **extra) -> None:
        self._log(LogLevel.INFO, message, **extra)

    def warning(self, message: str, **extra) -> None:
        self._log(LogLevel.WARNING, message, **extra)

    def error(self, message: str, **extra) -> None:
        self._log(LogLevel.ERROR, message, **extra)

    def critical(self, message: str, **extra) -> None:
        self._log(LogLevel.CRITICAL, message, **extra)

    def exception(self, message: str, exc: Exception = None, **extra) -> None:
        if exc:
            extra["error_type"] = type(exc).__name__
            extra["error_message"] = str(exc)
        self._log(LogLevel.ERROR, message, **extra)

    def set_trace_id(self, trace_id: str) -> None:
        self._current_trace_id = trace_id


# -----------------------------------------------------------------------------
# 追踪系统
# -----------------------------------------------------------------------------

class TraceExporter:
    """追踪导出器接口"""
    async def export(self, spans: list[Span]) -> None:
        pass


class ConsoleTraceExporter(TraceExporter):
    """控制台追踪导出器"""
    async def export(self, spans: list[Span]) -> None:
        for span in spans:
            print(f"[TRACE] {span.trace_id}/{span.span_id} {span.name} "
                  f"{span.duration:.2f}s {span.status}")


class FileTraceExporter(TraceExporter):
    """文件追踪导出器"""
    def __init__(self, file_path: str):
        self._file_path = file_path

    async def export(self, spans: list[Span]) -> None:
        with open(self._file_path, "a", encoding="utf-8") as f:
            for span in spans:
                f.write(json.dumps({
                    "trace_id": span.trace_id,
                    "span_id": span.span_id,
                    "parent_span_id": span.parent_span_id,
                    "name": span.name,
                    "duration": span.duration,
                    "status": span.status,
                    "attributes": span.attributes,
                }, ensure_ascii=False) + "\n")


class Tracer:
    """分布式追踪器"""
    def __init__(self, service_name: str, exporters: list[TraceExporter] = None):
        self._service_name = service_name
        self._exporters = exporters or [ConsoleTraceExporter()]
        self._current_trace_id = None
        self._current_span: Span | None = None
        self._spans_to_export: list[Span] = []
        self._lock = asyncio.Lock()

    def start_span(self, name: str, parent_span: Span = None) -> Span:
        """创建新 Span"""
        trace_id = self._current_trace_id or self._generate_trace_id()
        self._current_trace_id = trace_id

        span = Span(
            trace_id=trace_id,
            span_id=self._generate_span_id(),
            parent_span_id=parent_span.span_id if parent_span else None,
            name=name,
            start_time=time.time(),
        )
        self._current_span = span
        return span

    def end_span(self, span: Span, status: str = "success") -> None:
        """结束 Span"""
        span.end_time = time.time()
        span.status = status
        _safe_async(self._export_span(span))

    async def _export_span(self, span: Span) -> None:
        async with self._lock:
            self._spans_to_export.append(span)
            if len(self._spans_to_export) >= 10:
                await self._flush()

    async def _flush(self) -> None:
        spans = self._spans_to_export
        self._spans_to_export = []
        for exporter in self._exporters:
            try:
                await exporter.export(spans)
            except Exception as e:
                print(f"Trace exporter error: {e}")

    async def force_flush(self) -> None:
        """强制刷新所有待导出的 Span"""
        async with self._lock:
            if self._spans_to_export:
                await self._flush()

    def _generate_trace_id(self) -> str:
        return str(uuid.uuid4()).replace("-", "")[:16]

    def _generate_span_id(self) -> str:
        return str(uuid.uuid4()).replace("-", "")[:8]

    def set_trace_id(self, trace_id: str) -> None:
        self._current_trace_id = trace_id


# -----------------------------------------------------------------------------
# 指标系统
# -----------------------------------------------------------------------------

class MetricExporter:
    """指标导出器接口"""
    async def export(self, metrics: list[MetricSample]) -> None:
        pass


class ConsoleMetricExporter(MetricExporter):
    """控制台指标导出器"""
    async def export(self, metrics: list[MetricSample]) -> None:
        for metric in metrics:
            labels_str = ",".join(f"{k}={v}" for k, v in metric.labels.items())
            print(f"[METRIC] {metric.name} {metric.type.name} {metric.value:.4f} "
                  f"{labels_str if labels_str else ''}")


class PrometheusMetricExporter(MetricExporter):
    """Prometheus 格式指标导出器"""
    def __init__(self, file_path: str = "metrics.prom"):
        self._file_path = file_path
        self._metrics_cache: dict[str, MetricSample] = {}

    async def export(self, metrics: list[MetricSample]) -> None:
        for metric in metrics:
            key = f"{metric.name}_{','.join(f'{k}={v}' for k, v in metric.labels.items())}"
            self._metrics_cache[key] = metric

        with open(self._file_path, "w", encoding="utf-8") as f:
            for metric in self._metrics_cache.values():
                labels_str = ",".join(f'{k}="{v}"' for k, v in metric.labels.items())
                if labels_str:
                    labels_str = "{" + labels_str + "}"
                f.write(f"{metric.name}{labels_str} {metric.value:.4f}\n")


class MetricsCollector:
    """指标收集器"""
    def __init__(self, exporters: list[MetricExporter] = None):
        self._exporters = exporters or [ConsoleMetricExporter()]
        self._counters: dict[str, float] = {}
        self._gauges: dict[str, float] = {}
        self._lock = asyncio.Lock()

    def increment(self, name: str, value: float = 1.0, **labels) -> None:
        """递增计数器"""
        _safe_async(self._record(MetricType.COUNTER, name, value, labels))

    def gauge(self, name: str, value: float, **labels) -> None:
        """设置仪表盘值"""
        _safe_async(self._record(MetricType.GAUGE, name, value, labels))

    def histogram(self, name: str, value: float, **labels) -> None:
        """记录直方图"""
        _safe_async(self._record(MetricType.HISTOGRAM, name, value, labels))

    def summary(self, name: str, value: float, **labels) -> None:
        """记录摘要"""
        _safe_async(self._record(MetricType.SUMMARY, name, value, labels))

    async def _record(self, metric_type: MetricType, name: str, value: float, labels: dict[str, str]) -> None:
        sample = MetricSample(
            name=name,
            type=metric_type,
            value=value,
            timestamp=time.time(),
            labels=labels,
        )

        async with self._lock:
            # 更新缓存
            if metric_type == MetricType.COUNTER:
                key = f"{name}_{','.join(f'{k}={v}' for k, v in labels.items())}"
                self._counters[key] = self._counters.get(key, 0) + value

        # 导出
        for exporter in self._exporters:
            try:
                await exporter.export([sample])
            except Exception as e:
                print(f"Metric exporter error: {e}")


# -----------------------------------------------------------------------------
# 可观测性上下文管理器
# -----------------------------------------------------------------------------

class ObservabilityContext:
    """可观测性上下文 - 将日志、追踪、指标绑定到同一个 trace_id"""
    def __init__(
        self,
        logger: Logger,
        tracer: Tracer,
        metrics: MetricsCollector,
        trace_id: str | None = None,
    ):
        self._logger = logger
        self._tracer = tracer
        self._metrics = metrics
        self._trace_id = trace_id or str(uuid.uuid4()).replace("-", "")[:16]
        self._span_stack: list[Span] = []

        # 绑定 trace_id
        self._logger.set_trace_id(self._trace_id)
        self._tracer.set_trace_id(self._trace_id)

    @property
    def trace_id(self) -> str:
        return self._trace_id

    @property
    def logger(self) -> Logger:
        return self._logger

    @property
    def tracer(self) -> Tracer:
        return self._tracer

    @property
    def metrics(self) -> MetricsCollector:
        return self._metrics

    def start_span(self, name: str) -> Span:
        """创建新 Span 并压入栈"""
        parent = self._span_stack[-1] if self._span_stack else None
        span = self._tracer.start_span(name, parent)
        self._span_stack.append(span)
        return span

    def end_span(self, status: str = "success") -> None:
        """弹出并结束最顶层 Span"""
        if self._span_stack:
            span = self._span_stack.pop()
            self._tracer.end_span(span, status)

    async def close(self) -> None:
        """关闭上下文，刷新所有数据"""
        while self._span_stack:
            span = self._span_stack.pop()
            self._tracer.end_span(span, "closed")
        await self._tracer.force_flush()


# -----------------------------------------------------------------------------
# 装饰器
# -----------------------------------------------------------------------------

def traced(logger_name: str = "default", span_name: str = None):
    """追踪装饰器"""
    def decorator(func: Callable) -> Callable:
        async def async_wrapper(*args, **kwargs):
            ctx = _get_global_context()
            if ctx:
                name = span_name or func.__name__
                ctx.start_span(name)
                try:
                    start = time.time()
                    result = await func(*args, **kwargs)
                    ctx.metrics.histogram("function_duration", time.time() - start,
                                         function=name)
                    ctx.end_span("success")
                    return result
                except Exception as e:
                    ctx.end_span("error")
                    ctx.logger.exception(f"Function {name} failed", exc=e)
                    ctx.metrics.increment("function_errors", function=name)
                    raise
            else:
                return await func(*args, **kwargs)

        def sync_wrapper(*args, **kwargs):
            ctx = _get_global_context()
            if ctx:
                name = span_name or func.__name__
                ctx.start_span(name)
                try:
                    start = time.time()
                    result = func(*args, **kwargs)
                    ctx.metrics.histogram("function_duration", time.time() - start,
                                         function=name)
                    ctx.end_span("success")
                    return result
                except Exception as e:
                    ctx.end_span("error")
                    ctx.logger.exception(f"Function {name} failed", exc=e)
                    ctx.metrics.increment("function_errors", function=name)
                    raise
            else:
                return func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator


# -----------------------------------------------------------------------------
# 全局实例
# -----------------------------------------------------------------------------

# 全局日志器
global_logger = Logger("ae-knowledge-vault")

# 全局追踪器
global_tracer = Tracer("ae-knowledge-vault")

# 全局指标收集器
global_metrics = MetricsCollector()

# 全局可观测性上下文（线程本地存储）
_global_context = None


def set_global_context(ctx: ObservabilityContext) -> None:
    """设置全局可观测性上下文"""
    global _global_context
    _global_context = ctx


def _get_global_context() -> ObservabilityContext | None:
    """获取全局可观测性上下文"""
    return _global_context


def create_context(trace_id: str | None = None) -> ObservabilityContext:
    """创建新的可观测性上下文"""
    return ObservabilityContext(global_logger, global_tracer, global_metrics, trace_id)


# -----------------------------------------------------------------------------
# 便捷函数
# -----------------------------------------------------------------------------

def log_debug(message: str, **extra) -> None:
    global_logger.debug(message, **extra)


def log_info(message: str, **extra) -> None:
    global_logger.info(message, **extra)


def log_warning(message: str, **extra) -> None:
    global_logger.warning(message, **extra)


def log_error(message: str, **extra) -> None:
    global_logger.error(message, **extra)


def log_critical(message: str, **extra) -> None:
    global_logger.critical(message, **extra)


def increment_counter(name: str, value: float = 1.0, **labels) -> None:
    global_metrics.increment(name, value, **labels)


def set_gauge(name: str, value: float, **labels) -> None:
    global_metrics.gauge(name, value, **labels)


def record_histogram(name: str, value: float, **labels) -> None:
    global_metrics.histogram(name, value, **labels)


def record_summary(name: str, value: float, **labels) -> None:
    global_metrics.summary(name, value, **labels)


# 确保导入 os
import os
