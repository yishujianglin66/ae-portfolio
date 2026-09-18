"""core.state_machine 单元测试 - 工作流状态机核心逻辑"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.state_machine import (
    AEStatus,
    PipelinePhase,
    PipelineStateMachine,
    PipelineStatus,
    SilhouetteStatus,
    StateContext,
    StateListener,
    Transition,
)


class TestEnums:
    def test_pipeline_status_values(self):
        assert PipelineStatus.IDLE.value == 1
        assert PipelineStatus.RUNNING.value == 2
        assert PipelineStatus.PAUSED.value == 3
        assert PipelineStatus.COMPLETED.value == 4
        assert PipelineStatus.FAILED.value == 5
        assert PipelineStatus.CANCELLED.value == 6

    def test_pipeline_phase_values(self):
        assert PipelinePhase.IDLE.value == 1
        assert PipelinePhase.PERCEPTION.value == 2
        assert PipelinePhase.UNDERSTANDING.value == 3
        assert PipelinePhase.PLANNING.value == 4
        assert PipelinePhase.EXECUTION.value == 5
        assert PipelinePhase.FEEDBACK.value == 6

    def test_silhouette_status_values(self):
        assert SilhouetteStatus.IDLE.value == 1
        assert SilhouetteStatus.ROUTING.value == 2
        assert SilhouetteStatus.WAITING.value == 3
        assert SilhouetteStatus.PROCESSING.value == 4
        assert SilhouetteStatus.COMPLETED.value == 5
        assert SilhouetteStatus.FAILED.value == 6
        assert SilhouetteStatus.FALLBACK.value == 7

    def test_ae_status_values(self):
        assert AEStatus.IDLE.value == 1
        assert AEStatus.COMPILING.value == 2
        assert AEStatus.EXECUTING.value == 3
        assert AEStatus.RENDERING.value == 4
        assert AEStatus.COMPLETED.value == 5
        assert AEStatus.FAILED.value == 6


class TestStateContext:
    def test_default_state(self):
        ctx = StateContext(pipeline_id="test-123")
        assert ctx.pipeline_id == "test-123"
        assert ctx.status == PipelineStatus.IDLE
        assert ctx.phase == PipelinePhase.IDLE
        assert ctx.silhouette_status == SilhouetteStatus.IDLE
        assert ctx.ae_status == AEStatus.IDLE
        assert ctx.start_time is None
        assert ctx.end_time is None
        assert ctx.error is None
        assert ctx.progress == 0.0
        assert ctx.data == {}

    def test_state_context_data(self):
        ctx = StateContext(pipeline_id="test", data={"key": "value"})
        assert ctx.data["key"] == "value"


class TestTransition:
    def test_transition_creation(self):
        t = Transition(
            from_state=PipelineStatus.IDLE,
            to_state=PipelineStatus.RUNNING,
            event="start",
        )
        assert t.from_state == PipelineStatus.IDLE
        assert t.to_state == PipelineStatus.RUNNING
        assert t.event == "start"
        assert t.guard is None
        assert t.action is None
        assert t.priority == 0

    def test_transition_with_guard_and_action(self):
        guard_called = []
        action_called = []

        def guard(ctx):
            guard_called.append(1)
            return True

        def action(ctx):
            action_called.append(1)

        t = Transition(
            from_state=PipelineStatus.IDLE,
            to_state=PipelineStatus.RUNNING,
            event="start",
            guard=guard,
            action=action,
            priority=10,
        )
        assert t.priority == 10


class TestPipelineStateMachine:
    def test_initial_state(self):
        sm = PipelineStateMachine()
        assert sm.status == PipelineStatus.IDLE
        assert sm.phase == PipelinePhase.IDLE
        assert sm.is_running is False
        assert sm.is_completed is False
        assert sm.is_failed is False
        assert sm.context.pipeline_id is not None

    def test_start_pipeline(self):
        sm = PipelineStateMachine()
        sm.start("pipe-001")
        assert sm.status == PipelineStatus.RUNNING
        assert sm.phase == PipelinePhase.PERCEPTION
        assert sm.is_running is True
        assert sm.context.pipeline_id == "pipe-001"
        assert sm.context.start_time is not None

    def test_pause_and_resume(self):
        sm = PipelineStateMachine()
        sm.start()
        assert sm.is_running is True

        sm.pause()
        assert sm.status == PipelineStatus.PAUSED
        assert sm.is_running is False

        sm.resume()
        assert sm.status == PipelineStatus.RUNNING
        assert sm.is_running is True

    def test_cancel_pipeline(self):
        sm = PipelineStateMachine()
        sm.start()
        sm.cancel()
        assert sm.status == PipelineStatus.CANCELLED
        assert sm.context.end_time is not None

    def test_complete_pipeline(self):
        sm = PipelineStateMachine()
        sm.start()
        sm.complete()
        assert sm.status == PipelineStatus.COMPLETED
        assert sm.is_completed is True
        assert sm.context.end_time is not None

    def test_fail_pipeline(self):
        sm = PipelineStateMachine()
        sm.start()
        error = RuntimeError("test error")
        sm.fail(error)
        assert sm.status == PipelineStatus.FAILED
        assert sm.is_failed is True
        assert sm.context.error == error
        assert sm.context.end_time is not None

    def test_reset_pipeline(self):
        sm = PipelineStateMachine()
        sm.start("pipe-1")
        sm.complete()
        assert sm.is_completed is True

        sm.reset()
        assert sm.status == PipelineStatus.IDLE
        assert sm.phase == PipelinePhase.IDLE
        assert sm.context.pipeline_id != "pipe-1"

    def test_phase_transitions(self):
        sm = PipelineStateMachine()
        sm.start()
        assert sm.phase == PipelinePhase.PERCEPTION

        sm.phase_perception_done()
        assert sm.phase == PipelinePhase.UNDERSTANDING
        assert sm.context.progress == 0.2

        sm.phase_understanding_done()
        assert sm.phase == PipelinePhase.PLANNING
        assert sm.context.progress == 0.4

        sm.phase_planning_done()
        assert sm.phase == PipelinePhase.EXECUTION
        assert sm.context.progress == 0.6

        sm.phase_execution_done()
        assert sm.phase == PipelinePhase.FEEDBACK
        assert sm.context.progress == 0.8

        sm.phase_feedback_done()
        assert sm.phase == PipelinePhase.IDLE
        assert sm.context.progress == 1.0
        assert sm.is_completed is True

    def test_phase_failure_resets_to_idle(self):
        sm = PipelineStateMachine()
        sm.start()
        assert sm.phase == PipelinePhase.PERCEPTION

        sm.trigger("fail")
        assert sm.phase == PipelinePhase.IDLE

    def test_silhouette_substate_transitions(self):
        sm = PipelineStateMachine()
        assert sm.context.silhouette_status == SilhouetteStatus.IDLE

        sm.silhouette_start()
        assert sm.context.silhouette_status == SilhouetteStatus.ROUTING

        sm.silhouette_routed()
        assert sm.context.silhouette_status == SilhouetteStatus.WAITING

        sm.silhouette_start_process()
        assert sm.context.silhouette_status == SilhouetteStatus.PROCESSING

        sm.silhouette_done()
        assert sm.context.silhouette_status == SilhouetteStatus.COMPLETED

    def test_silhouette_fallback_path(self):
        sm = PipelineStateMachine()
        sm.silhouette_start()
        sm.silhouette_routed()
        sm.silhouette_start_process()
        assert sm.context.silhouette_status == SilhouetteStatus.PROCESSING

        sm.silhouette_fallback()
        assert sm.context.silhouette_status == SilhouetteStatus.FALLBACK

        sm.trigger("fallback_done")
        assert sm.context.silhouette_status == SilhouetteStatus.COMPLETED

    def test_silhouette_failure(self):
        sm = PipelineStateMachine()
        sm.silhouette_start()
        sm.silhouette_routed()
        sm.silhouette_start_process()

        error = RuntimeError("silhouette error")
        sm.silhouette_fail(error)
        assert sm.context.silhouette_status == SilhouetteStatus.FAILED
        assert sm.context.data["silhouette_error"] == str(error)

    def test_ae_substate_transitions(self):
        sm = PipelineStateMachine()
        assert sm.context.ae_status == AEStatus.IDLE

        sm.ae_compile()
        assert sm.context.ae_status == AEStatus.COMPILING

        sm.ae_compiled()
        assert sm.context.ae_status == AEStatus.EXECUTING

        sm.ae_executed()
        assert sm.context.ae_status == AEStatus.RENDERING

        sm.ae_rendered()
        assert sm.context.ae_status == AEStatus.COMPLETED

    def test_ae_failure_compile(self):
        sm = PipelineStateMachine()
        sm.ae_compile()
        error = RuntimeError("compile error")
        sm.ae_fail("compile", error)
        assert sm.context.ae_status == AEStatus.FAILED
        assert sm.context.data["ae_error"]["phase"] == "compile"

    def test_ae_failure_execute(self):
        sm = PipelineStateMachine()
        sm.ae_compile()
        sm.ae_compiled()
        error = RuntimeError("execute error")
        sm.ae_fail("execute", error)
        assert sm.context.ae_status == AEStatus.FAILED
        assert sm.context.data["ae_error"]["phase"] == "execute"

    def test_ae_failure_render(self):
        sm = PipelineStateMachine()
        sm.ae_compile()
        sm.ae_compiled()
        sm.ae_executed()
        error = RuntimeError("render error")
        sm.ae_fail("render", error)
        assert sm.context.ae_status == AEStatus.FAILED
        assert sm.context.data["ae_error"]["phase"] == "render"

    def test_trigger_invalid_event_no_change(self):
        sm = PipelineStateMachine()
        result = sm.trigger("nonexistent_event")
        assert result is False
        assert sm.status == PipelineStatus.IDLE

    def test_trigger_with_data(self):
        sm = PipelineStateMachine()
        sm.start()
        sm.trigger("perception_done", data={"clips": 3, "bpm": 120})
        assert sm.context.data["clips"] == 3
        assert sm.context.data["bpm"] == 120

    def test_state_listeners(self):
        sm = PipelineStateMachine()
        state_changes = []
        phase_changes = []

        class TestListener(StateListener):
            def on_state_changed(self, context):
                state_changes.append(context.status)

            def on_phase_changed(self, context):
                phase_changes.append(context.phase)

        listener = TestListener()
        sm.add_listener(listener)

        sm.start()
        assert len(state_changes) >= 1
        assert len(phase_changes) >= 1

        sm.remove_listener(listener)
        prev_count = len(state_changes)
        sm.pause()
        assert len(state_changes) == prev_count

    def test_listener_error_does_not_break(self):
        sm = PipelineStateMachine()

        class BadListener(StateListener):
            def on_state_changed(self, context):
                raise RuntimeError("listener error")

        sm.add_listener(BadListener())
        sm.start()
        assert sm.status == PipelineStatus.RUNNING

    def test_serialization_roundtrip(self):
        sm = PipelineStateMachine()
        sm.start("test-pipe")
        sm.phase_perception_done(data={"key": "value"})

        d = sm.to_dict()
        assert d["pipeline_id"] == "test-pipe"
        assert d["status"] == "RUNNING"
        assert d["phase"] == "UNDERSTANDING"
        assert d["progress"] == 0.2
        assert d["data"]["key"] == "value"

        sm2 = PipelineStateMachine.from_dict(d)
        assert sm2.context.pipeline_id == "test-pipe"
        assert sm2.status == PipelineStatus.RUNNING
        assert sm2.phase == PipelinePhase.UNDERSTANDING
        assert sm2.context.progress == 0.2
        assert sm2.context.data["key"] == "value"

    def test_validate_state_idle(self):
        sm = PipelineStateMachine()
        assert sm.validate_state() is True

    def test_validate_state_running_without_phase(self):
        sm = PipelineStateMachine()
        sm._context.status = PipelineStatus.RUNNING
        sm._context.phase = PipelinePhase.IDLE
        assert sm.validate_state() is False

    def test_validate_state_completed_progress(self):
        sm = PipelineStateMachine()
        sm._context.status = PipelineStatus.COMPLETED
        sm._context.progress = 0.5
        assert sm.validate_state() is False

    def test_validate_state_execution_no_substate(self):
        sm = PipelineStateMachine()
        sm.start()
        sm.phase_perception_done()
        sm.phase_understanding_done()
        sm.phase_planning_done()
        sm._context.silhouette_status = SilhouetteStatus.IDLE
        sm._context.ae_status = AEStatus.IDLE
        assert sm.validate_state() is False

    def test_get_stats(self):
        sm = PipelineStateMachine()
        sm.start("stats-test")
        stats = sm.get_stats()
        assert stats["pipeline_id"] == "stats-test"
        assert stats["status"] == "RUNNING"
        assert stats["phase"] == "PERCEPTION"
        assert "progress" in stats
        assert "duration_seconds" in stats
        assert stats["is_valid"] is True


class TestTransitionPriority:
    def test_higher_priority_chosen_first(self):
        sm = PipelineStateMachine()
        low_action_called = []
        high_action_called = []

        def low_action(ctx):
            low_action_called.append(1)

        def high_action(ctx):
            high_action_called.append(1)

        sm._top_transitions.append(Transition(
            from_state=PipelineStatus.IDLE,
            to_state=PipelineStatus.RUNNING,
            event="start",
            action=low_action,
            priority=0,
        ))
        sm._top_transitions.append(Transition(
            from_state=PipelineStatus.IDLE,
            to_state=PipelineStatus.RUNNING,
            event="start",
            action=high_action,
            priority=10,
        ))

        sm.trigger("start")
        assert len(high_action_called) == 1
        assert len(low_action_called) == 0


class TestTransitionGuard:
    def test_guard_false_skips_transition(self):
        sm = PipelineStateMachine()

        def guard(ctx):
            return False

        sm._top_transitions = [
            Transition(
                from_state=PipelineStatus.IDLE,
                to_state=PipelineStatus.RUNNING,
                event="test_event",
                guard=guard,
            ),
        ]

        result = sm.trigger("test_event")
        assert result is False
        assert sm.status == PipelineStatus.IDLE

    def test_guard_true_allows_transition(self):
        sm = PipelineStateMachine()

        def guard(ctx):
            return True

        sm._top_transitions = [
            Transition(
                from_state=PipelineStatus.IDLE,
                to_state=PipelineStatus.RUNNING,
                event="test_event",
                guard=guard,
            ),
        ]

        result = sm.trigger("test_event")
        assert result is True
        assert sm.status == PipelineStatus.RUNNING
