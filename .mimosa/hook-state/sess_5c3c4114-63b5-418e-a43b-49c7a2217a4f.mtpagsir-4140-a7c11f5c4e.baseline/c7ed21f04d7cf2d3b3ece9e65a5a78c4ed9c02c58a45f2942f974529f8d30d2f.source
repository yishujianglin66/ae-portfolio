#!/usr/bin/env python3
"""
AE 专用追踪工具 - 全链路追踪 v1.0

设计目标：
1. 操作级追踪：为每个 AE 操作创建独立的追踪 Span
2. trace_id 传递：在整个调用链中保持一致的 trace_id
3. 事件关联：追踪数据与事件总线事件关联
4. 指标集成：自动记录关键性能指标（延迟、成功率等）
5. 灵活配置：支持同步/异步追踪、自定义采样率

使用方式：
    >>> from core.ae_tracer import AETracer, ae_operation
    >>> 
    >>> tracer = AETracer()
    >>> 
    >>> @ae_operation("create_composition")
    >>> def create_comp(name, width, height):
    ...     return {"success": True}
    >>> 
    >>> # 或手动使用
    >>> with tracer.start_span("render", trace_id="abc123") as span:
    ...     span.set_attribute("comp_name", "Test")
    ...     # 执行操作
    ...     span.record_success()
"""
from __future__ import annotations

import threading

import asyncio
import time
import uuid
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar, Union

from core.observability import (
    global_tracer,
    global_metrics,
    global_logger,
    create_context,
    ObservabilityContext,
    Span as ObsSpan,
)
from core.event_bus import publish_ae_event, AEEvent

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class AEOperationSpan:
    """AE 操作追踪 Span"""
    
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    operation_name: str = ""
    channel: str = ""
    status: str = "running"
    start_time: float = 0.0
    end_time: float = 0.0
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    
    @property
    def duration_ms(self) -> float:
        """获取操作耗时（毫秒）"""
        return max(0, (self.end_time - self.start_time) * 1000.0)
    
    def set_attribute(self, key: str, value: Any) -> None:
        """设置属性"""
        self.attributes[key] = value
    
    def add_event(self, name: str, **kwargs: Any) -> None:
        """添加事件"""
        self.events.append({
            "name": name,
            "timestamp": time.time(),
            **kwargs,
        })
    
    def record_success(self) -> None:
        """记录成功"""
        self.status = "success"
        self.end_time = time.time()
    
    def record_failure(self, error: str = "") -> None:
        """记录失败"""
        self.status = "failed"
        self.end_time = time.time()
        self.error = error


class AETracer:
    """AE 专用追踪器"""
    
    def __init__(self, service_name: str = "ae-bridge"):
        self._service_name = service_name
        self._current_trace_id: Optional[str] = None
        self._current_span: Optional[AEOperationSpan] = None
        self._span_stack: List[AEOperationSpan] = []
        # 保护 _span_stack / _current_span 的并发访问。
        # 使用 RLock：span 允许嵌套（父子 span），同一线程可重入。
        self._span_lock = threading.RLock()
    
    @property
    def current_trace_id(self) -> str:
        """获取当前 trace_id，不存在则生成新的"""
        if self._current_trace_id is None:
            self._current_trace_id = self._generate_trace_id()
        return self._current_trace_id
    
    @current_trace_id.setter
    def current_trace_id(self, trace_id: str) -> None:
        """设置当前 trace_id"""
        self._current_trace_id = trace_id
    
    def start_span(
        self,
        operation_name: str,
        trace_id: Optional[str] = None,
        parent_span: Optional[AEOperationSpan] = None,
        channel: str = "",
        **attributes: Any,
    ) -> AEOperationSpan:
        """创建并启动新的操作 Span"""
        if trace_id:
            self._current_trace_id = trace_id
        
        effective_parent = parent_span if parent_span else (self._current_span if self._span_stack else None)
        
        span = AEOperationSpan(
            trace_id=self.current_trace_id,
            span_id=self._generate_span_id(),
            parent_span_id=effective_parent.span_id if effective_parent else None,
            operation_name=operation_name,
            channel=channel,
            start_time=time.time(),
            attributes=attributes,
        )
        
        with self._span_lock:
            self._span_stack.append(span)
            self._current_span = span

        # 发布操作开始事件
        self._publish_operation_event(span, "started")
        
        # 记录指标
        global_metrics.increment(f"ae.operation.started", operation=operation_name)
        
        return span
    
    def end_span(self, span: Optional[AEOperationSpan] = None, status: str = "success") -> None:
        """结束指定的 Span"""
        if span is None:
            span = self._current_span
        if span is None:
            return
        
        span.end_time = time.time()
        span.status = status
        
        # 从栈中移除（线程安全）
        with self._span_lock:
            if span in self._span_stack:
                self._span_stack.remove(span)
        if self._current_span == span:
            self._current_span = self._span_stack[-1] if self._span_stack else None
        
        # 发布操作结束事件
        self._publish_operation_event(span, "completed")
        
        # 记录指标
        global_metrics.histogram(
            f"ae.operation.duration",
            span.duration_ms,
            operation=span.operation_name,
            status=status,
        )
        global_metrics.increment(
            f"ae.operation.completed",
            operation=span.operation_name,
            status=status,
        )
        
        # 记录追踪 Span
        self._record_observability_span(span)
    
    def record_error(self, span: AEOperationSpan, error: Exception) -> None:
        """记录错误"""
        span.record_failure(str(error))
        span.set_attribute("error_type", type(error).__name__)
        span.set_attribute("error_message", str(error))
        
        global_metrics.increment(
            f"ae.operation.errors",
            operation=span.operation_name,
            error_type=type(error).__name__,
        )
    
    async def run_with_trace(
        self,
        operation_name: str,
        func: Callable[..., T],
        *args: Any,
        trace_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Tuple[T, AEOperationSpan]:
        """在追踪上下文中运行函数"""
        span = self.start_span(operation_name, trace_id=trace_id, **kwargs)
        try:
            result = await func(*args) if asyncio.iscoroutinefunction(func) else func(*args)
            span.record_success()
            self.end_span(span, "success")
            return result, span
        except Exception as e:
            self.record_error(span, e)
            self.end_span(span, "failed")
            raise
    
    def _generate_trace_id(self) -> str:
        """生成 trace_id"""
        return str(uuid.uuid4()).replace("-", "")[:16]
    
    def _generate_span_id(self) -> str:
        """生成 span_id"""
        return str(uuid.uuid4()).replace("-", "")[:8]
    
    def _publish_operation_event(self, span: AEOperationSpan, event_type: str) -> None:
        """发布操作事件到事件总线"""
        try:
            payload = {
                "trace_id": span.trace_id,
                "span_id": span.span_id,
                "parent_span_id": span.parent_span_id,
                "operation_name": span.operation_name,
                "channel": span.channel,
                "status": span.status,
                "duration_ms": span.duration_ms,
                "start_time": span.start_time,
                "end_time": span.end_time,
                "error": span.error,
                "attributes": span.attributes,
                "events": span.events,
            }
            publish_ae_event(f"operation.{event_type}", payload=payload)
        except Exception as e:
            logger.debug("发布操作事件失败: %s", e)
    
    def _record_observability_span(self, span: AEOperationSpan) -> None:
        """记录到全局可观测性系统"""
        obs_span = global_tracer.start_span(
            span.operation_name,
            parent_span=ObsSpan(
                trace_id=span.trace_id,
                span_id=span.parent_span_id or "",
            ) if span.parent_span_id else None,
        )
        obs_span.start_time = span.start_time
        obs_span.end_time = span.end_time
        obs_span.status = span.status
        obs_span.attributes.update(span.attributes)
        global_tracer.end_span(obs_span, span.status)
    
    def get_active_spans(self) -> List[AEOperationSpan]:
        """获取所有活跃的 Span"""
        return list(self._span_stack)


# -----------------------------------------------------------------------------
# 全局实例
# -----------------------------------------------------------------------------

ae_tracer = AETracer()


# -----------------------------------------------------------------------------
# 装饰器
# -----------------------------------------------------------------------------

def ae_operation(operation_name: str = ""):
    """AE 操作追踪装饰器"""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        async def async_wrapper(*args, **kwargs):
            op_name = operation_name or func.__name__
            tracer = kwargs.pop("_tracer", ae_tracer)
            
            span = tracer.start_span(op_name, **kwargs.get("span_attrs", {}))
            try:
                result = await func(*args, **kwargs)
                
                if isinstance(result, dict):
                    span.set_attribute("result", result.get("success", "unknown"))
                    if "channel_used" in result:
                        span.channel = result["channel_used"]
                
                span.record_success()
                tracer.end_span(span, "success")
                return result
            except Exception as e:
                tracer.record_error(span, e)
                tracer.end_span(span, "failed")
                raise
        
        def sync_wrapper(*args, **kwargs):
            op_name = operation_name or func.__name__
            tracer = kwargs.pop("_tracer", ae_tracer)
            
            span = tracer.start_span(op_name, **kwargs.get("span_attrs", {}))
            try:
                result = func(*args, **kwargs)
                
                if isinstance(result, dict):
                    span.set_attribute("result", result.get("success", "unknown"))
                    if "channel_used" in result:
                        span.channel = result["channel_used"]
                
                span.record_success()
                tracer.end_span(span, "success")
                return result
            except Exception as e:
                tracer.record_error(span, e)
                tracer.end_span(span, "failed")
                raise
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator


# -----------------------------------------------------------------------------
# 上下文管理器
# -----------------------------------------------------------------------------

class AETraceContext:
    """AE 追踪上下文管理器"""
    
    def __init__(
        self,
        operation_name: str,
        trace_id: Optional[str] = None,
        tracer: AETracer = ae_tracer,
        **attributes: Any,
    ):
        self._operation_name = operation_name
        self._trace_id = trace_id
        self._tracer = tracer
        self._attributes = attributes
        self._span: Optional[AEOperationSpan] = None
    
    @property
    def trace_id(self) -> str:
        """获取 trace_id"""
        return self._span.trace_id if self._span else self._tracer.current_trace_id
    
    @property
    def span(self) -> Optional[AEOperationSpan]:
        """获取当前 Span"""
        return self._span
    
    def __enter__(self) -> "AETraceContext":
        self._span = self._tracer.start_span(
            self._operation_name,
            trace_id=self._trace_id,
            **self._attributes,
        )
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._span:
            if exc_type is not None:
                self._tracer.record_error(self._span, exc_val)
                self._tracer.end_span(self._span, "failed")
            else:
                self._tracer.end_span(self._span, "success")


# -----------------------------------------------------------------------------
# 便捷函数
# -----------------------------------------------------------------------------

def start_ae_operation(
    operation_name: str,
    trace_id: Optional[str] = None,
    channel: str = "",
    **attributes: Any,
) -> AEOperationSpan:
    """便捷启动 AE 操作追踪"""
    return ae_tracer.start_span(operation_name, trace_id=trace_id, channel=channel, **attributes)


def end_ae_operation(span: AEOperationSpan, status: str = "success") -> None:
    """便捷结束 AE 操作追踪"""
    ae_tracer.end_span(span, status)


def set_trace_id(trace_id: str) -> None:
    """设置全局 trace_id"""
    ae_tracer.current_trace_id = trace_id


def get_trace_id() -> str:
    """获取全局 trace_id"""
    return ae_tracer.current_trace_id


__all__ = [
    "AEOperationSpan",
    "AETracer",
    "AETraceContext",
    "ae_tracer",
    "ae_operation",
    "start_ae_operation",
    "end_ae_operation",
    "set_trace_id",
    "get_trace_id",
]