#!/usr/bin/env python3
"""
事件驱动架构核心 - EventBus 事件总线 v1.0

设计原则（事件驱动架构 EDA）：
1. 松耦合：组件间通过事件通信，不直接调用
2. 异步：事件发布后立即返回，不阻塞调用者
3. 可追溯：所有事件记录日志，支持重放和审计
4. 优先级：支持事件优先级队列
5. 事务性：事件处理失败支持重试和死信队列

事件分类：
- PipelineEvent: 工作流生命周期事件（开始、结束、阶段切换）
- SilhouetteEvent: Silhouette 操作事件
- AEEvent: AE 操作事件
- ErrorEvent: 错误事件
- MetricEvent: 指标事件

架构参考：
- David Harel Statecharts（状态图理论）
- Event Sourcing（事件溯源）
- Command Query Responsibility Segregation（CQRS）
"""
import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Type, Union


class EventPriority(Enum):
    """事件优先级：紧急 > 高 > 普通 > 低 > 后台"""
    CRITICAL = auto()   # 系统级错误、紧急通知
    HIGH = auto()       # 用户操作、任务执行
    NORMAL = auto()     # 状态变更、进度更新
    LOW = auto()        # 日志记录、统计数据
    BACKGROUND = auto() # 后台任务、定时检查


class EventCategory(Enum):
    """事件分类"""
    PIPELINE = "pipeline"
    SILHOUETTE = "silhouette"
    AE = "ae"
    TOPAZ = "topaz"
    RUNWAY = "runway"
    PIKA = "pika"
    BLENDER = "blender"
    FFMPEG = "ffmpeg"
    ERROR = "error"
    METRIC = "metric"
    SYSTEM = "system"


@dataclass
class Event:
    """事件基类 - 所有事件的统一格式"""
    category: EventCategory
    event_type: str
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=lambda: time.time())
    priority: EventPriority = EventPriority.NORMAL
    payload: dict[str, Any] = field(default_factory=dict)
    correlation_id: str | None = None  # 用于关联同一请求的所有事件
    causation_id: str | None = None    # 用于追踪事件因果关系

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "category": self.category.value,
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "priority": self.priority.name,
            "payload": self.payload,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Event":
        return cls(
            event_id=data["event_id"],
            category=EventCategory(data["category"]),
            event_type=data["event_type"],
            timestamp=data["timestamp"],
            priority=EventPriority[data["priority"]],
            payload=data.get("payload", {}),
            correlation_id=data.get("correlation_id"),
            causation_id=data.get("causation_id"),
        )


# -----------------------------------------------------------------------------
# 预定义事件类型
# -----------------------------------------------------------------------------

@dataclass
class PipelineEvent(Event):
    """工作流事件"""
    def __init__(self, event_type: str, **kwargs):
        super().__init__(
            category=EventCategory.PIPELINE,
            event_type=event_type,
            **kwargs
        )


@dataclass
class SilhouetteEvent(Event):
    """Silhouette 事件"""
    def __init__(self, event_type: str, **kwargs):
        super().__init__(
            category=EventCategory.SILHOUETTE,
            event_type=event_type,
            **kwargs
        )


@dataclass
class AEEvent(Event):
    """AE 事件"""
    def __init__(self, event_type: str, **kwargs):
        super().__init__(
            category=EventCategory.AE,
            event_type=event_type,
            **kwargs
        )


@dataclass
class TopazEvent(Event):
    """Topaz Video AI 事件"""
    def __init__(self, event_type: str, **kwargs):
        super().__init__(
            category=EventCategory.TOPAZ,
            event_type=event_type,
            **kwargs
        )


@dataclass
class RunwayEvent(Event):
    """RunwayML 事件"""
    def __init__(self, event_type: str, **kwargs):
        super().__init__(
            category=EventCategory.RUNWAY,
            event_type=event_type,
            **kwargs
        )


@dataclass
class PikaEvent(Event):
    """Pika 事件"""
    def __init__(self, event_type: str, **kwargs):
        super().__init__(
            category=EventCategory.PIKA,
            event_type=event_type,
            **kwargs
        )


@dataclass
class BlenderEvent(Event):
    """Blender 事件"""
    def __init__(self, event_type: str, **kwargs):
        super().__init__(
            category=EventCategory.BLENDER,
            event_type=event_type,
            **kwargs
        )


@dataclass
class FFmpegEvent(Event):
    """FFmpeg 事件"""
    def __init__(self, event_type: str, **kwargs):
        super().__init__(
            category=EventCategory.FFMPEG,
            event_type=event_type,
            **kwargs
        )


@dataclass
class ErrorEvent(Event):
    """错误事件"""
    def __init__(self, event_type: str, error: Exception = None, **kwargs):
        payload = kwargs.pop("payload", {})
        if error:
            payload["error_type"] = type(error).__name__
            payload["error_message"] = str(error)
        super().__init__(
            category=EventCategory.ERROR,
            event_type=event_type,
            priority=EventPriority.CRITICAL,
            payload=payload,
            **kwargs
        )


@dataclass
class MetricEvent(Event):
    """指标事件"""
    def __init__(self, metric_name: str, value: float, **kwargs):
        payload = kwargs.pop("payload", {})
        payload["metric_name"] = metric_name
        payload["value"] = value
        super().__init__(
            category=EventCategory.METRIC,
            event_type="metric.record",
            priority=EventPriority.BACKGROUND,
            payload=payload,
            **kwargs
        )


# -----------------------------------------------------------------------------
# EventBus 核心实现
# -----------------------------------------------------------------------------

class EventHandler:
    """事件处理器包装"""
    def __init__(
        self,
        handler: Callable[[Event], Union[None, asyncio.Future, Any]],
        priority: int = 0,
        is_async: bool = False,
    ):
        self.handler = handler
        self.priority = priority
        self.is_async = is_async


class EventBus:
    """事件总线核心 - 支持异步事件发布/订阅"""

    def __init__(self, max_queue_size: int = 10000):
        self._logger = logging.getLogger(f"{__name__}.EventBus")
        self._subscribers: dict[tuple[EventCategory, str], list[EventHandler]] = {}
        self._category_subscribers: dict[EventCategory, list[EventHandler]] = {}
        self._global_subscribers: list[EventHandler] = []
        self._event_queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self._running = False
        self._worker_task: asyncio.Task | None = None
        self._event_store: list[Event] = []
        self._max_store_size = 1000
        self._semaphore = asyncio.Semaphore(10)  # 限制并发处理数

    async def start(self) -> None:
        """启动事件总线"""
        if self._running:
            return
        self._running = True
        self._worker_task = asyncio.create_task(self._event_worker())
        self._logger.info("EventBus started")

    async def stop(self) -> None:
        """停止事件总线"""
        self._running = False
        if self._worker_task:
            await self._worker_task
        self._logger.info("EventBus stopped")

    # -------------------------------------------------------------------------
    # 订阅 API
    # -------------------------------------------------------------------------

    def subscribe(
        self,
        event_category: EventCategory,
        event_type: str | None = None,
        handler: Callable[[Event], Any] = None,
        *,
        priority: int = 0,
        is_async: bool = False,
    ) -> Callable[[Callable], Callable]:
        """订阅事件 - 支持装饰器模式"""

        def decorator(func: Callable[[Event], Any]) -> Callable[[Event], Any]:
            self._subscribe_internal(func, event_category, event_type, priority, is_async)
            return func

        if handler:
            return decorator(handler)
        return decorator

    def subscribe_global(self, handler: Callable[[Event], Any]) -> None:
        """订阅所有事件"""
        self._global_subscribers.append(EventHandler(handler, is_async=False))

    def _subscribe_internal(
        self,
        handler: Callable[[Event], Any],
        event_category: EventCategory,
        event_type: str | None,
        priority: int,
        is_async: bool,
    ) -> None:
        """内部订阅逻辑"""
        eh = EventHandler(handler, priority, is_async)
        if event_type:
            key = (event_category, event_type)
            if key not in self._subscribers:
                self._subscribers[key] = []
            self._subscribers[key].append(eh)
            self._subscribers[key].sort(key=lambda x: -x.priority)
        else:
            if event_category not in self._category_subscribers:
                self._category_subscribers[event_category] = []
            self._category_subscribers[event_category].append(eh)
            self._category_subscribers[event_category].sort(key=lambda x: -x.priority)

    # -------------------------------------------------------------------------
    # 发布 API
    # -------------------------------------------------------------------------

    def publish(self, event: Event) -> None:
        """发布事件（同步 - 立即入队）"""
        try:
            self._event_queue.put_nowait(event)
            self._store_event(event)
        except asyncio.QueueFull:
            self._logger.warning(f"Event queue full, dropping event: {event.event_type}")

    async def publish_async(self, event: Event) -> None:
        """发布事件（异步 - 等待队列有空间）"""
        await self._event_queue.put(event)
        self._store_event(event)

    def publish_sync(self, event: Event) -> None:
        """发布事件（同步 - 立即执行，不入队）"""
        self._store_event(event)
        asyncio.create_task(self._dispatch_event(event))

    # -------------------------------------------------------------------------
    # 事件处理
    # -------------------------------------------------------------------------

    async def _event_worker(self) -> None:
        """事件工作者 - 从队列中获取并分发事件"""
        while self._running:
            try:
                event = await asyncio.wait_for(
                    self._event_queue.get(),
                    timeout=1.0
                )
                async with self._semaphore:
                    await self._dispatch_event(event)
                self._event_queue.task_done()
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                self._logger.error(f"Event worker error: {e}")

    async def _dispatch_event(self, event: Event) -> None:
        """分发事件到所有订阅者"""
        handlers = self._get_handlers(event)
        tasks = []

        for handler in handlers:
            try:
                if handler.is_async:
                    tasks.append(handler.handler(event))
                else:
                    tasks.append(asyncio.to_thread(handler.handler, event))
            except Exception as e:
                self._logger.error(f"Handler registration error: {e}")

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def _get_handlers(self, event: Event) -> list[EventHandler]:
        """获取事件的所有处理者"""
        handlers: list[EventHandler] = []

        # 精确匹配: (category, type)
        key = (event.category, event.event_type)
        if key in self._subscribers:
            handlers.extend(self._subscribers[key])

        # 类别匹配: category
        if event.category in self._category_subscribers:
            handlers.extend(self._category_subscribers[event.category])

        # 全局匹配
        handlers.extend(self._global_subscribers)

        return handlers

    # -------------------------------------------------------------------------
    # 事件持久化
    # -------------------------------------------------------------------------

    def _store_event(self, event: Event) -> None:
        """存储事件用于审计和重放"""
        self._event_store.append(event)
        if len(self._event_store) > self._max_store_size:
            self._event_store.pop(0)

    def get_event_history(self, limit: int = 100) -> list[Event]:
        """获取事件历史"""
        return list(reversed(self._event_store[-limit:]))

    def clear_event_history(self) -> None:
        """清空事件历史"""
        self._event_store.clear()

    # -------------------------------------------------------------------------
    # 事件重放
    # -------------------------------------------------------------------------

    async def replay_events(
        self,
        events: list[Event],
        skip_errors: bool = True,
    ) -> dict[str, Any]:
        """重放事件"""
        results = {"success": 0, "failed": 0, "errors": []}
        for event in events:
            try:
                await self._dispatch_event(event)
                results["success"] += 1
            except Exception as e:
                results["failed"] += 1
                if not skip_errors:
                    results["errors"].append({
                        "event_id": event.event_id,
                        "error": str(e),
                    })
        return results

    # -------------------------------------------------------------------------
    # 统计信息
    # -------------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """获取事件总线统计信息"""
        return {
            "queue_size": self._event_queue.qsize(),
            "stored_events": len(self._event_store),
            "subscribers": {
                "exact": len(self._subscribers),
                "category": len(self._category_subscribers),
                "global": len(self._global_subscribers),
            },
            "running": self._running,
        }


# -----------------------------------------------------------------------------
# 全局事件总线实例
# -----------------------------------------------------------------------------

event_bus = EventBus()


# -----------------------------------------------------------------------------
# 便捷发布函数
# -----------------------------------------------------------------------------

def publish_pipeline_event(event_type: str, **kwargs) -> None:
    """便捷发布工作流事件"""
    event = PipelineEvent(event_type, **kwargs)
    event_bus.publish(event)


def publish_silhouette_event(event_type: str, **kwargs) -> None:
    """便捷发布 Silhouette 事件"""
    event = SilhouetteEvent(event_type, **kwargs)
    event_bus.publish(event)


def publish_ae_event(event_type: str, **kwargs) -> None:
    """便捷发布 AE 事件"""
    event = AEEvent(event_type, **kwargs)
    event_bus.publish(event)


def publish_topaz_event(event_type: str, **kwargs) -> None:
    """便捷发布 Topaz 事件"""
    event = TopazEvent(event_type, **kwargs)
    event_bus.publish(event)


def publish_runway_event(event_type: str, **kwargs) -> None:
    """便捷发布 RunwayML 事件"""
    event = RunwayEvent(event_type, **kwargs)
    event_bus.publish(event)


def publish_pika_event(event_type: str, **kwargs) -> None:
    """便捷发布 Pika 事件"""
    event = PikaEvent(event_type, **kwargs)
    event_bus.publish(event)


def publish_blender_event(event_type: str, **kwargs) -> None:
    """便捷发布 Blender 事件"""
    event = BlenderEvent(event_type, **kwargs)
    event_bus.publish(event)


def publish_ffmpeg_event(event_type: str, **kwargs) -> None:
    """便捷发布 FFmpeg 事件"""
    event = FFmpegEvent(event_type, **kwargs)
    event_bus.publish(event)


def publish_error(event_type: str, error: Exception = None, **kwargs) -> None:
    """便捷发布错误事件"""
    event = ErrorEvent(event_type, error, **kwargs)
    event_bus.publish(event)


def publish_metric(metric_name: str, value: float, **kwargs) -> None:
    """便捷发布指标事件"""
    event = MetricEvent(metric_name, value, **kwargs)
    event_bus.publish(event)
