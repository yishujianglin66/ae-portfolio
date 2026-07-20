"""core.event_bus 单元测试 - 事件总线核心逻辑"""
import os
import sys
import asyncio
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.event_bus import (
    EventPriority,
    EventCategory,
    Event,
    PipelineEvent,
    SilhouetteEvent,
    AEEvent,
    ErrorEvent,
    MetricEvent,
    EventHandler,
    EventBus,
    event_bus,
    publish_pipeline_event,
    publish_silhouette_event,
    publish_ae_event,
    publish_error,
    publish_metric,
)


class TestEnums:
    def test_event_priority_order(self):
        priorities = list(EventPriority)
        values = [p.value for p in priorities]
        assert values == sorted(values)

    def test_event_category_values(self):
        assert EventCategory.PIPELINE.value == "pipeline"
        assert EventCategory.SILHOUETTE.value == "silhouette"
        assert EventCategory.AE.value == "ae"
        assert EventCategory.ERROR.value == "error"
        assert EventCategory.METRIC.value == "metric"
        assert EventCategory.SYSTEM.value == "system"


class TestEventBase:
    def test_event_creation(self):
        evt = Event(
            category=EventCategory.PIPELINE,
            event_type="test.event",
            priority=EventPriority.HIGH,
            payload={"key": "value"},
        )
        assert evt.category == EventCategory.PIPELINE
        assert evt.event_type == "test.event"
        assert evt.priority == EventPriority.HIGH
        assert evt.payload["key"] == "value"
        assert evt.event_id is not None
        assert evt.timestamp > 0

    def test_event_defaults(self):
        evt = Event(
            category=EventCategory.PIPELINE,
            event_type="test.event",
        )
        assert evt.priority == EventPriority.NORMAL
        assert evt.payload == {}
        assert evt.correlation_id is None
        assert evt.causation_id is None

    def test_event_to_dict(self):
        evt = Event(
            category=EventCategory.PIPELINE,
            event_type="test.event",
            payload={"data": 123},
            correlation_id="corr-1",
            causation_id="cause-1",
        )
        d = evt.to_dict()
        assert d["event_id"] == evt.event_id
        assert d["category"] == "pipeline"
        assert d["event_type"] == "test.event"
        assert d["priority"] == "NORMAL"
        assert d["payload"]["data"] == 123
        assert d["correlation_id"] == "corr-1"
        assert d["causation_id"] == "cause-1"

    def test_event_from_dict(self):
        data = {
            "event_id": "test-id-123",
            "category": "ae",
            "event_type": "render.done",
            "timestamp": 1234567890.0,
            "priority": "HIGH",
            "payload": {"result": "ok"},
            "correlation_id": "corr-1",
            "causation_id": "cause-1",
        }
        evt = Event.from_dict(data)
        assert evt.event_id == "test-id-123"
        assert evt.category == EventCategory.AE
        assert evt.event_type == "render.done"
        assert evt.timestamp == 1234567890.0
        assert evt.priority == EventPriority.HIGH
        assert evt.payload["result"] == "ok"
        assert evt.correlation_id == "corr-1"
        assert evt.causation_id == "cause-1"

    def test_event_serialization_roundtrip(self):
        evt = Event(
            category=EventCategory.SILHOUETTE,
            event_type="roto.done",
            priority=EventPriority.CRITICAL,
            payload={"frames": 100},
            correlation_id="c1",
        )
        d = evt.to_dict()
        evt2 = Event.from_dict(d)
        assert evt2.event_id == evt.event_id
        assert evt2.category == evt.category
        assert evt2.event_type == evt.event_type
        assert evt2.priority == evt.priority
        assert evt2.payload == evt.payload
        assert evt2.correlation_id == evt.correlation_id


class TestSpecializedEvents:
    def test_pipeline_event(self):
        evt = PipelineEvent("started", payload={"id": "p1"})
        assert evt.category == EventCategory.PIPELINE
        assert evt.event_type == "started"
        assert evt.payload["id"] == "p1"

    def test_silhouette_event(self):
        evt = SilhouetteEvent("roto_started", payload={"task": "hair"})
        assert evt.category == EventCategory.SILHOUETTE
        assert evt.event_type == "roto_started"

    def test_ae_event(self):
        evt = AEEvent("comp_created", payload={"name": "Comp1"})
        assert evt.category == EventCategory.AE
        assert evt.event_type == "comp_created"

    def test_error_event(self):
        error = RuntimeError("test error")
        evt = ErrorEvent("failed", error=error)
        assert evt.category == EventCategory.ERROR
        assert evt.priority == EventPriority.CRITICAL
        assert evt.payload["error_type"] == "RuntimeError"
        assert evt.payload["error_message"] == "test error"

    def test_error_event_without_exception(self):
        evt = ErrorEvent("warning")
        assert evt.category == EventCategory.ERROR
        assert evt.priority == EventPriority.CRITICAL

    def test_metric_event(self):
        evt = MetricEvent("render_time", 1.5, payload={"tags": {"layer": "v1"}})
        assert evt.category == EventCategory.METRIC
        assert evt.event_type == "metric.record"
        assert evt.priority == EventPriority.BACKGROUND
        assert evt.payload["metric_name"] == "render_time"
        assert evt.payload["value"] == 1.5
        assert evt.payload["tags"]["layer"] == "v1"


class TestEventHandler:
    def test_handler_creation(self):
        def handler(evt):
            pass

        h = EventHandler(handler, priority=5, is_async=False)
        assert h.handler == handler
        assert h.priority == 5
        assert h.is_async is False


class TestEventBusSync:
    def test_bus_creation(self):
        bus = EventBus(max_queue_size=100)
        assert bus._running is False
        assert bus._worker_task is None
        assert len(bus._event_store) == 0

    def test_subscribe_exact(self):
        bus = EventBus()
        received = []

        def handler(evt):
            received.append(evt)

        bus.subscribe(EventCategory.PIPELINE, "test.event", handler)
        assert (EventCategory.PIPELINE, "test.event") in bus._subscribers
        assert len(bus._subscribers[(EventCategory.PIPELINE, "test.event")]) == 1

    def test_subscribe_category(self):
        bus = EventBus()
        received = []

        def handler(evt):
            received.append(evt)

        bus.subscribe(EventCategory.PIPELINE, None, handler)
        assert EventCategory.PIPELINE in bus._category_subscribers
        assert len(bus._category_subscribers[EventCategory.PIPELINE]) == 1

    def test_subscribe_global(self):
        bus = EventBus()
        received = []

        def handler(evt):
            received.append(evt)

        bus.subscribe_global(handler)
        assert len(bus._global_subscribers) == 1

    def test_subscribe_decorator(self):
        bus = EventBus()
        received = []

        @bus.subscribe(EventCategory.PIPELINE, "decorated.event")
        def my_handler(evt):
            received.append(evt)
            return "ok"

        assert (EventCategory.PIPELINE, "decorated.event") in bus._subscribers
        assert my_handler(None) == "ok"

    def test_subscribe_priority_order(self):
        bus = EventBus()
        order = []

        def low_handler(evt):
            order.append("low")

        def high_handler(evt):
            order.append("high")

        bus.subscribe(EventCategory.PIPELINE, "test", low_handler, priority=1)
        bus.subscribe(EventCategory.PIPELINE, "test", high_handler, priority=10)

        handlers = bus._subscribers[(EventCategory.PIPELINE, "test")]
        assert handlers[0].priority == 10
        assert handlers[1].priority == 1

    def test_publish_stores_event(self):
        bus = EventBus()
        evt = Event(
            category=EventCategory.PIPELINE,
            event_type="test.event",
            payload={"x": 1},
        )
        bus.publish(evt)
        assert len(bus._event_store) == 1
        assert bus._event_store[0].event_id == evt.event_id

    def test_event_history(self):
        bus = EventBus()
        for i in range(5):
            evt = Event(
                category=EventCategory.PIPELINE,
                event_type=f"event.{i}",
            )
            bus.publish(evt)

        history = bus.get_event_history(limit=3)
        assert len(history) == 3
        assert history[0].event_type == "event.4"
        assert history[2].event_type == "event.2"

    def test_clear_event_history(self):
        bus = EventBus()
        evt = Event(category=EventCategory.PIPELINE, event_type="test")
        bus.publish(evt)
        assert len(bus._event_store) == 1

        bus.clear_event_history()
        assert len(bus._event_store) == 0

    def test_event_store_max_size(self):
        bus = EventBus(max_queue_size=100)
        bus._max_store_size = 10
        for i in range(15):
            evt = Event(
                category=EventCategory.PIPELINE,
                event_type=f"evt.{i}",
            )
            bus.publish(evt)

        assert len(bus._event_store) == 10
        assert bus._event_store[0].event_type == "evt.5"

    def test_get_stats(self):
        bus = EventBus()
        bus.subscribe(EventCategory.PIPELINE, "test", lambda e: None)
        bus.subscribe(EventCategory.AE, None, lambda e: None)
        bus.subscribe_global(lambda e: None)

        stats = bus.get_stats()
        assert stats["subscribers"]["exact"] == 1
        assert stats["subscribers"]["category"] == 1
        assert stats["subscribers"]["global"] == 1
        assert stats["running"] is False
        assert stats["stored_events"] == 0

    def test_get_handlers_exact_match(self):
        bus = EventBus()
        calls = []

        def exact_handler(evt):
            calls.append("exact")

        def category_handler(evt):
            calls.append("category")

        def global_handler(evt):
            calls.append("global")

        bus.subscribe(EventCategory.PIPELINE, "test.event", exact_handler)
        bus.subscribe(EventCategory.PIPELINE, None, category_handler)
        bus.subscribe_global(global_handler)

        evt = Event(category=EventCategory.PIPELINE, event_type="test.event")
        handlers = bus._get_handlers(evt)
        assert len(handlers) == 3


class TestEventBusAsync:
    @pytest.mark.asyncio
    async def test_start_and_stop(self):
        bus = EventBus(max_queue_size=100)
        assert bus._running is False

        await bus.start()
        assert bus._running is True
        assert bus._worker_task is not None

        await bus.stop()
        assert bus._running is False

    @pytest.mark.asyncio
    async def test_start_idempotent(self):
        bus = EventBus(max_queue_size=100)
        await bus.start()
        task_id = id(bus._worker_task)
        await bus.start()
        assert id(bus._worker_task) == task_id
        await bus.stop()

    @pytest.mark.asyncio
    async def test_publish_async(self):
        bus = EventBus(max_queue_size=100)
        await bus.start()

        evt = Event(category=EventCategory.PIPELINE, event_type="async.test")
        await bus.publish_async(evt)
        assert bus._event_queue.qsize() == 1

        await bus.stop()

    @pytest.mark.asyncio
    async def test_dispatch_event_calls_handlers(self):
        bus = EventBus(max_queue_size=100)
        received = []

        def handler(evt):
            received.append(evt)

        bus.subscribe(EventCategory.PIPELINE, "dispatch.test", handler)
        evt = Event(category=EventCategory.PIPELINE, event_type="dispatch.test")

        await bus._dispatch_event(evt)
        assert len(received) == 1
        assert received[0].event_id == evt.event_id

    @pytest.mark.asyncio
    async def test_dispatch_calls_all_handler_types(self):
        bus = EventBus(max_queue_size=100)
        received = []

        def exact_handler(evt):
            received.append("exact")

        def category_handler(evt):
            received.append("category")

        def global_handler(evt):
            received.append("global")

        bus.subscribe(EventCategory.AE, "render.done", exact_handler)
        bus.subscribe(EventCategory.AE, None, category_handler)
        bus.subscribe_global(global_handler)

        evt = Event(category=EventCategory.AE, event_type="render.done")
        await bus._dispatch_event(evt)

        assert len(received) == 3
        assert "exact" in received
        assert "category" in received
        assert "global" in received

    @pytest.mark.asyncio
    async def test_handler_error_does_not_break_dispatch(self):
        bus = EventBus(max_queue_size=100)
        received = []

        def bad_handler(evt):
            raise RuntimeError("handler failed")

        def good_handler(evt):
            received.append("good")

        bus.subscribe(EventCategory.PIPELINE, "test", bad_handler, priority=10)
        bus.subscribe(EventCategory.PIPELINE, "test", good_handler, priority=1)

        evt = Event(category=EventCategory.PIPELINE, event_type="test")
        await bus._dispatch_event(evt)

        assert len(received) == 1
        assert received[0] == "good"

    @pytest.mark.asyncio
    async def test_async_handler(self):
        bus = EventBus(max_queue_size=100)
        received = []

        async def async_handler(evt):
            await asyncio.sleep(0.01)
            received.append(evt)

        bus.subscribe(EventCategory.PIPELINE, "async.test", async_handler, is_async=True)
        evt = Event(category=EventCategory.PIPELINE, event_type="async.test")

        await bus._dispatch_event(evt)
        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_replay_events(self):
        bus = EventBus(max_queue_size=100)
        replayed = []

        def handler(evt):
            replayed.append(evt.event_type)

        bus.subscribe(EventCategory.PIPELINE, None, handler)

        events = [
            Event(category=EventCategory.PIPELINE, event_type="evt1"),
            Event(category=EventCategory.PIPELINE, event_type="evt2"),
            Event(category=EventCategory.PIPELINE, event_type="evt3"),
        ]

        results = await bus.replay_events(events)
        assert results["success"] == 3
        assert results["failed"] == 0
        assert replayed == ["evt1", "evt2", "evt3"]

    @pytest.mark.asyncio
    async def test_replay_events_with_errors(self):
        bus = EventBus(max_queue_size=100)

        def bad_handler(evt):
            if evt.event_type == "bad":
                raise RuntimeError("fail")

        bus.subscribe(EventCategory.PIPELINE, None, bad_handler)

        events = [
            Event(category=EventCategory.PIPELINE, event_type="good1"),
            Event(category=EventCategory.PIPELINE, event_type="bad"),
            Event(category=EventCategory.PIPELINE, event_type="good2"),
        ]

        results = await bus.replay_events(events, skip_errors=True)
        assert results["success"] == 3  # gather with return_exceptions still counts
        assert results["failed"] == 0


class TestConvenienceFunctions:
    def test_publish_pipeline_event(self):
        bus = EventBus(max_queue_size=100)
        import core.event_bus as eb
        old_bus = eb.event_bus
        eb.event_bus = bus
        try:
            publish_pipeline_event("test", payload={"x": 1})
            assert len(bus._event_store) == 1
            assert bus._event_store[0].category == EventCategory.PIPELINE
            assert bus._event_store[0].event_type == "test"
        finally:
            eb.event_bus = old_bus

    def test_publish_silhouette_event(self):
        bus = EventBus(max_queue_size=100)
        import core.event_bus as eb
        old_bus = eb.event_bus
        eb.event_bus = bus
        try:
            publish_silhouette_event("roto_done")
            assert bus._event_store[0].category == EventCategory.SILHOUETTE
        finally:
            eb.event_bus = old_bus

    def test_publish_ae_event(self):
        bus = EventBus(max_queue_size=100)
        import core.event_bus as eb
        old_bus = eb.event_bus
        eb.event_bus = bus
        try:
            publish_ae_event("render_done")
            assert bus._event_store[0].category == EventCategory.AE
        finally:
            eb.event_bus = old_bus

    def test_publish_error(self):
        bus = EventBus(max_queue_size=100)
        import core.event_bus as eb
        old_bus = eb.event_bus
        eb.event_bus = bus
        try:
            publish_error("test_error", error=ValueError("oops"))
            assert bus._event_store[0].category == EventCategory.ERROR
            assert bus._event_store[0].priority == EventPriority.CRITICAL
        finally:
            eb.event_bus = old_bus

    def test_publish_metric(self):
        bus = EventBus(max_queue_size=100)
        import core.event_bus as eb
        old_bus = eb.event_bus
        eb.event_bus = bus
        try:
            publish_metric("test_metric", 42.0)
            assert bus._event_store[0].category == EventCategory.METRIC
            assert bus._event_store[0].payload["metric_name"] == "test_metric"
            assert bus._event_store[0].payload["value"] == 42.0
        finally:
            eb.event_bus = old_bus
