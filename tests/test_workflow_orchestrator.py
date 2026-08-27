"""core.workflow_orchestrator 单元测试 - 工作流编排引擎核心逻辑"""
import os
import sys
import asyncio
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.workflow_orchestrator import (
    TaskStatus,
    TaskType,
    WorkflowStatus,
    TaskDefinition,
    TaskInstance,
    WorkflowContext,
    WorkflowOrchestrator,
    create_orchestrator,
)


class TestEnums:
    def test_task_status_values(self):
        assert TaskStatus.PENDING.value == 1
        assert TaskStatus.QUEUED.value == 2
        assert TaskStatus.RUNNING.value == 3
        assert TaskStatus.COMPLETED.value == 4
        assert TaskStatus.FAILED.value == 5
        assert TaskStatus.SKIPPED.value == 6
        assert TaskStatus.RETRYING.value == 7

    def test_task_type_values(self):
        assert TaskType.PERCEPTION.value == "perception"
        assert TaskType.UNDERSTANDING.value == "understanding"
        assert TaskType.PLANNING.value == "planning"
        assert TaskType.AE_COMPILE.value == "ae_compile"
        assert TaskType.AE_EXECUTE.value == "ae_execute"
        assert TaskType.AE_RENDER.value == "ae_render"
        assert TaskType.SUB_WORKFLOW.value == "sub_workflow"

    def test_workflow_status_values(self):
        assert WorkflowStatus.IDLE.value == 1
        assert WorkflowStatus.RUNNING.value == 2
        assert WorkflowStatus.PAUSED.value == 3
        assert WorkflowStatus.COMPLETED.value == 4
        assert WorkflowStatus.FAILED.value == 5
        assert WorkflowStatus.CANCELLED.value == 6


class TestTaskDefinition:
    def test_default_values(self):
        def dummy_func(**kwargs):
            pass

        td = TaskDefinition(
            task_id="test-1",
            task_type=TaskType.PERCEPTION,
            name="Test Task",
            func=dummy_func,
        )
        assert td.task_id == "test-1"
        assert td.task_type == TaskType.PERCEPTION
        assert td.name == "Test Task"
        assert td.func == dummy_func
        assert td.args == {}
        assert td.dependencies == []
        assert td.retry_count == 0
        assert td.retry_delay_ms == 2000
        assert td.timeout_ms is None
        assert td.max_parallel == 1
        assert td.skip_on_failure is False
        assert td.fallback_func is None

    def test_custom_values(self):
        def dummy_func(**kwargs):
            pass

        def fallback_func(**kwargs):
            pass

        td = TaskDefinition(
            task_id="test-2",
            task_type=TaskType.AE_EXECUTE,
            name="Custom Task",
            func=dummy_func,
            args={"param": "value"},
            dependencies=["dep1", "dep2"],
            retry_count=3,
            retry_delay_ms=5000,
            timeout_ms=30000,
            skip_on_failure=True,
            fallback_func=fallback_func,
        )
        assert td.args == {"param": "value"}
        assert td.dependencies == ["dep1", "dep2"]
        assert td.retry_count == 3
        assert td.retry_delay_ms == 5000
        assert td.timeout_ms == 30000
        assert td.skip_on_failure is True
        assert td.fallback_func == fallback_func


class TestTaskInstance:
    def test_default_values(self):
        def dummy_func(**kwargs):
            pass

        td = TaskDefinition(
            task_id="task-1",
            task_type=TaskType.PERCEPTION,
            name="Test",
            func=dummy_func,
        )
        ti = TaskInstance(task_def=td)
        assert ti.task_def == td
        assert ti.instance_id is not None
        assert ti.status == TaskStatus.PENDING
        assert ti.result is None
        assert ti.error is None
        assert ti.retry_attempts == 0
        assert ti.start_time is None
        assert ti.end_time is None
        assert ti.duration == 0.0

    def test_custom_instance_id(self):
        def dummy_func(**kwargs):
            pass

        td = TaskDefinition(
            task_id="task-1",
            task_type=TaskType.PERCEPTION,
            name="Test",
            func=dummy_func,
        )
        ti = TaskInstance(task_def=td, instance_id="custom-id-123")
        assert ti.instance_id == "custom-id-123"


class TestWorkflowContext:
    def test_default_values(self):
        ctx = WorkflowContext(workflow_id="wf-1")
        assert ctx.workflow_id == "wf-1"
        assert ctx.status == WorkflowStatus.IDLE
        assert ctx.tasks == {}
        assert ctx.start_time is None
        assert ctx.end_time is None
        assert ctx.progress == 0.0
        assert ctx.data == {}
        assert ctx.error is None

    def test_with_initial_data(self):
        ctx = WorkflowContext(
            workflow_id="wf-2",
            data={"key": "value", "num": 42},
        )
        assert ctx.data["key"] == "value"
        assert ctx.data["num"] == 42


class TestWorkflowOrchestratorBasics:
    def test_creation(self):
        orch = WorkflowOrchestrator(max_concurrent_tasks=3)
        assert orch._max_concurrent == 3
        assert orch._running is False
        assert orch._context is None
        assert len(orch._tasks_def) == 0

    def test_create_orchestrator_helper(self):
        orch = create_orchestrator(max_concurrent=5)
        assert isinstance(orch, WorkflowOrchestrator)
        assert orch._max_concurrent == 5

    def test_add_task(self):
        orch = WorkflowOrchestrator()

        def dummy(**kwargs):
            pass

        td = TaskDefinition(
            task_id="task-1",
            task_type=TaskType.PERCEPTION,
            name="Test",
            func=dummy,
        )
        orch.add_task(td)
        assert len(orch._tasks_def) == 1
        assert orch._task_dependencies["task-1"] == set()

    def test_add_tasks_batch(self):
        orch = WorkflowOrchestrator()

        def dummy(**kwargs):
            pass

        tasks = [
            TaskDefinition(task_id=f"task-{i}", task_type=TaskType.PERCEPTION,
                           name=f"Task {i}", func=dummy)
            for i in range(3)
        ]
        orch.add_tasks(tasks)
        assert len(orch._tasks_def) == 3

    def test_add_task_with_dependencies(self):
        orch = WorkflowOrchestrator()

        def dummy(**kwargs):
            pass

        t1 = TaskDefinition(
            task_id="t1", task_type=TaskType.PERCEPTION,
            name="T1", func=dummy,
        )
        t2 = TaskDefinition(
            task_id="t2", task_type=TaskType.UNDERSTANDING,
            name="T2", func=dummy, dependencies=["t1"],
        )
        orch.add_task(t1)
        orch.add_task(t2)

        assert orch._task_dependencies["t2"] == {"t1"}
        assert orch._task_dependents["t1"] == {"t2"}

    def test_get_task_def_existing(self):
        orch = WorkflowOrchestrator()

        def dummy(**kwargs):
            pass

        td = TaskDefinition(
            task_id="find-me",
            task_type=TaskType.PLANNING,
            name="Find Me",
            func=dummy,
        )
        orch.add_task(td)
        found = orch.get_task_def("find-me")
        assert found is not None
        assert found.name == "Find Me"

    def test_get_task_def_missing(self):
        orch = WorkflowOrchestrator()
        assert orch.get_task_def("nonexistent") is None

    def test_context_property_before_run(self):
        orch = WorkflowOrchestrator()
        assert orch.context is None

    def test_is_running_before_run(self):
        orch = WorkflowOrchestrator()
        assert orch.is_running is False

    def test_get_stats_idle(self):
        orch = WorkflowOrchestrator()
        stats = orch.get_stats()
        assert stats["status"] == "IDLE"


class TestDependencyAnalysis:
    def test_linear_dependencies(self):
        orch = WorkflowOrchestrator()

        def dummy(**kwargs):
            pass

        t1 = TaskDefinition(task_id="t1", task_type=TaskType.PERCEPTION,
                            name="T1", func=dummy)
        t2 = TaskDefinition(task_id="t2", task_type=TaskType.UNDERSTANDING,
                            name="T2", func=dummy, dependencies=["t1"])
        t3 = TaskDefinition(task_id="t3", task_type=TaskType.PLANNING,
                            name="T3", func=dummy, dependencies=["t2"])
        orch.add_tasks([t1, t2, t3])

        order = orch._analyze_dependencies()
        assert order.index("t1") < order.index("t2")
        assert order.index("t2") < order.index("t3")

    def test_parallel_dependencies(self):
        orch = WorkflowOrchestrator()

        def dummy(**kwargs):
            pass

        t1 = TaskDefinition(task_id="t1", task_type=TaskType.PERCEPTION,
                            name="T1", func=dummy)
        t2 = TaskDefinition(task_id="t2", task_type=TaskType.UNDERSTANDING,
                            name="T2", func=dummy, dependencies=["t1"])
        t3 = TaskDefinition(task_id="t3", task_type=TaskType.PLANNING,
                            name="T3", func=dummy, dependencies=["t1"])
        t4 = TaskDefinition(task_id="t4", task_type=TaskType.AE_COMPILE,
                            name="T4", func=dummy, dependencies=["t2", "t3"])
        orch.add_tasks([t1, t2, t3, t4])

        order = orch._analyze_dependencies()
        assert order.index("t1") < order.index("t2")
        assert order.index("t1") < order.index("t3")
        assert order.index("t2") < order.index("t4")
        assert order.index("t3") < order.index("t4")

    def test_no_dependencies(self):
        orch = WorkflowOrchestrator()

        def dummy(**kwargs):
            pass

        tasks = [
            TaskDefinition(task_id=f"t{i}", task_type=TaskType.PERCEPTION,
                           name=f"T{i}", func=dummy)
            for i in range(3)
        ]
        orch.add_tasks(tasks)

        order = orch._analyze_dependencies()
        assert len(order) == 3

    def test_circular_dependency(self):
        orch = WorkflowOrchestrator()

        def dummy(**kwargs):
            pass

        t1 = TaskDefinition(task_id="t1", task_type=TaskType.PERCEPTION,
                            name="T1", func=dummy, dependencies=["t2"])
        t2 = TaskDefinition(task_id="t2", task_type=TaskType.UNDERSTANDING,
                            name="T2", func=dummy, dependencies=["t1"])
        orch.add_tasks([t1, t2])

        order = orch._analyze_dependencies()
        assert len(order) < 2

    def test_get_ready_tasks_no_deps(self):
        orch = WorkflowOrchestrator()

        def dummy(**kwargs):
            pass

        t1 = TaskDefinition(task_id="t1", task_type=TaskType.PERCEPTION,
                            name="T1", func=dummy)
        orch.add_task(t1)
        orch._context = WorkflowContext(workflow_id="test")
        orch._context.tasks["t1"] = TaskInstance(task_def=t1)
        orch._completed_tasks = set()
        orch._failed_tasks = set()

        ready = orch._get_ready_tasks()
        assert "t1" in ready

    def test_get_ready_tasks_with_unmet_deps(self):
        orch = WorkflowOrchestrator()

        def dummy(**kwargs):
            pass

        t1 = TaskDefinition(task_id="t1", task_type=TaskType.PERCEPTION,
                            name="T1", func=dummy)
        t2 = TaskDefinition(task_id="t2", task_type=TaskType.UNDERSTANDING,
                            name="T2", func=dummy, dependencies=["t1"])
        orch.add_tasks([t1, t2])
        orch._context = WorkflowContext(workflow_id="test")
        orch._context.tasks["t1"] = TaskInstance(task_def=t1)
        orch._context.tasks["t2"] = TaskInstance(task_def=t2)
        orch._completed_tasks = set()
        orch._failed_tasks = set()

        ready = orch._get_ready_tasks()
        assert "t1" in ready
        assert "t2" not in ready

    def test_get_ready_tasks_with_met_deps(self):
        orch = WorkflowOrchestrator()

        def dummy(**kwargs):
            pass

        t1 = TaskDefinition(task_id="t1", task_type=TaskType.PERCEPTION,
                            name="T1", func=dummy)
        t2 = TaskDefinition(task_id="t2", task_type=TaskType.UNDERSTANDING,
                            name="T2", func=dummy, dependencies=["t1"])
        orch.add_tasks([t1, t2])
        orch._context = WorkflowContext(workflow_id="test")
        orch._context.tasks["t1"] = TaskInstance(task_def=t1)
        orch._context.tasks["t2"] = TaskInstance(task_def=t2)
        orch._completed_tasks = {"t1"}
        orch._failed_tasks = set()

        ready = orch._get_ready_tasks()
        assert "t2" in ready


class TestWorkflowExecution:
    @pytest.mark.asyncio
    async def test_single_task_success(self):
        orch = WorkflowOrchestrator()
        results = []

        async def task_func(**kwargs):
            results.append("executed")
            return "result-1"

        td = TaskDefinition(
            task_id="t1",
            task_type=TaskType.PERCEPTION,
            name="Test Task",
            func=task_func,
        )
        orch.add_task(td)

        ctx = await orch.run(workflow_id="wf-single")
        assert ctx.status == WorkflowStatus.COMPLETED
        assert ctx.tasks["t1"].status == TaskStatus.COMPLETED
        assert ctx.tasks["t1"].result == "result-1"
        assert len(results) == 1
        assert ctx.progress == 1.0

    @pytest.mark.asyncio
    async def test_sequential_tasks(self):
        orch = WorkflowOrchestrator()
        execution_order = []

        async def task_a(**kwargs):
            execution_order.append("A")
            return "A-result"

        async def task_b(**kwargs):
            execution_order.append("B")
            return "B-result"

        t1 = TaskDefinition(task_id="t1", task_type=TaskType.PERCEPTION,
                            name="A", func=task_a)
        t2 = TaskDefinition(task_id="t2", task_type=TaskType.UNDERSTANDING,
                            name="B", func=task_b, dependencies=["t1"])
        orch.add_tasks([t1, t2])

        ctx = await orch.run(workflow_id="wf-seq")
        assert ctx.status == WorkflowStatus.COMPLETED
        assert execution_order == ["A", "B"]
        assert ctx.tasks["t2"].result == "B-result"

    @pytest.mark.asyncio
    async def test_parallel_tasks(self):
        orch = WorkflowOrchestrator(max_concurrent_tasks=3)
        results = set()

        async def task_1(**kwargs):
            await asyncio.sleep(0.01)
            results.add("t1")
            return 1

        async def task_2(**kwargs):
            await asyncio.sleep(0.01)
            results.add("t2")
            return 2

        async def task_3(**kwargs):
            await asyncio.sleep(0.01)
            results.add("t3")
            return 3

        t1 = TaskDefinition(task_id="t1", task_type=TaskType.PERCEPTION,
                            name="T1", func=task_1)
        t2 = TaskDefinition(task_id="t2", task_type=TaskType.PERCEPTION,
                            name="T2", func=task_2)
        t3 = TaskDefinition(task_id="t3", task_type=TaskType.PERCEPTION,
                            name="T3", func=task_3)
        orch.add_tasks([t1, t2, t3])

        ctx = await orch.run(workflow_id="wf-parallel")
        assert ctx.status == WorkflowStatus.COMPLETED
        assert results == {"t1", "t2", "t3"}
        assert ctx.progress == 1.0

    @pytest.mark.asyncio
    async def test_task_failure_no_skip(self):
        orch = WorkflowOrchestrator()

        async def failing_task(**kwargs):
            raise ValueError("task failed")

        async def next_task(**kwargs):
            return "should not run"

        t1 = TaskDefinition(task_id="t1", task_type=TaskType.PERCEPTION,
                            name="Fail", func=failing_task)
        t2 = TaskDefinition(task_id="t2", task_type=TaskType.UNDERSTANDING,
                            name="Next", func=next_task, dependencies=["t1"])
        orch.add_tasks([t1, t2])

        ctx = await orch.run(workflow_id="wf-fail")
        assert ctx.status == WorkflowStatus.FAILED
        assert ctx.tasks["t1"].status == TaskStatus.FAILED
        assert isinstance(ctx.tasks["t1"].error, ValueError)
        assert ctx.tasks["t2"].status == TaskStatus.PENDING

    @pytest.mark.asyncio
    async def test_task_failure_skip_on_failure(self):
        orch = WorkflowOrchestrator()

        async def failing_task(**kwargs):
            raise ValueError("skippable failure")

        async def next_task(**kwargs):
            return "runs anyway"

        t1 = TaskDefinition(task_id="t1", task_type=TaskType.PERCEPTION,
                            name="Fail", func=failing_task, skip_on_failure=True)
        t2 = TaskDefinition(task_id="t2", task_type=TaskType.UNDERSTANDING,
                            name="Next", func=next_task, dependencies=["t1"])
        orch.add_tasks([t1, t2])

        ctx = await orch.run(workflow_id="wf-skip")
        assert ctx.status == WorkflowStatus.COMPLETED
        assert ctx.tasks["t1"].status == TaskStatus.FAILED
        assert ctx.tasks["t2"].status == TaskStatus.COMPLETED
        assert ctx.tasks["t2"].result == "runs anyway"
        assert ctx.progress == 1.0

    @pytest.mark.asyncio
    async def test_task_retry(self):
        orch = WorkflowOrchestrator()
        call_count = 0

        async def flaky_task(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RuntimeError("transient error")
            return "success-after-retry"

        td = TaskDefinition(
            task_id="retry-task",
            task_type=TaskType.PERCEPTION,
            name="Flaky",
            func=flaky_task,
            retry_count=2,
            retry_delay_ms=10,
        )
        orch.add_task(td)

        ctx = await orch.run(workflow_id="wf-retry")
        assert ctx.status == WorkflowStatus.COMPLETED
        assert ctx.tasks["retry-task"].status == TaskStatus.COMPLETED
        assert ctx.tasks["retry-task"].result == "success-after-retry"
        assert ctx.tasks["retry-task"].retry_attempts == 1
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_task_retry_exhausted(self):
        orch = WorkflowOrchestrator()
        call_count = 0

        async def always_fails(**kwargs):
            nonlocal call_count
            call_count += 1
            raise RuntimeError("persistent error")

        td = TaskDefinition(
            task_id="fail-task",
            task_type=TaskType.PERCEPTION,
            name="Always Fail",
            func=always_fails,
            retry_count=2,
            retry_delay_ms=10,
        )
        orch.add_task(td)

        ctx = await orch.run(workflow_id="wf-retry-exhaust")
        assert ctx.status == WorkflowStatus.FAILED
        assert ctx.tasks["fail-task"].status == TaskStatus.FAILED
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_fallback_function(self):
        orch = WorkflowOrchestrator()

        async def failing_task(**kwargs):
            raise ValueError("main task failed")

        async def fallback_task(**kwargs):
            return "fallback-result"

        td = TaskDefinition(
            task_id="fb-task",
            task_type=TaskType.PERCEPTION,
            name="With Fallback",
            func=failing_task,
            fallback_func=fallback_task,
        )
        orch.add_task(td)

        ctx = await orch.run(workflow_id="wf-fallback")
        assert ctx.status == WorkflowStatus.COMPLETED
        assert ctx.tasks["fb-task"].status == TaskStatus.COMPLETED
        assert ctx.tasks["fb-task"].result == "fallback-result"

    @pytest.mark.asyncio
    async def test_task_timeout(self):
        orch = WorkflowOrchestrator()

        async def slow_task(**kwargs):
            await asyncio.sleep(10)
            return "too-slow"

        td = TaskDefinition(
            task_id="slow",
            task_type=TaskType.PERCEPTION,
            name="Slow",
            func=slow_task,
            timeout_ms=50,
        )
        orch.add_task(td)

        ctx = await orch.run(workflow_id="wf-timeout")
        assert ctx.status == WorkflowStatus.FAILED
        assert ctx.tasks["slow"].status == TaskStatus.FAILED
        assert isinstance(ctx.tasks["slow"].error, TimeoutError)

    @pytest.mark.asyncio
    async def test_sync_task_function(self):
        orch = WorkflowOrchestrator()

        def sync_task(**kwargs):
            return "sync-result"

        td = TaskDefinition(
            task_id="sync",
            task_type=TaskType.PERCEPTION,
            name="Sync Task",
            func=sync_task,
        )
        orch.add_task(td)

        ctx = await orch.run(workflow_id="wf-sync")
        assert ctx.status == WorkflowStatus.COMPLETED
        assert ctx.tasks["sync"].result == "sync-result"

    @pytest.mark.asyncio
    async def test_dependency_result_passing(self):
        orch = WorkflowOrchestrator()

        async def produce(**kwargs):
            return {"value": 42}

        async def consume(**kwargs):
            dep_result = kwargs.get("_produce_result")
            return dep_result["value"] * 2

        t1 = TaskDefinition(task_id="produce", task_type=TaskType.PERCEPTION,
                            name="Produce", func=produce)
        t2 = TaskDefinition(task_id="consume", task_type=TaskType.UNDERSTANDING,
                            name="Consume", func=consume, dependencies=["produce"])
        orch.add_tasks([t1, t2])

        ctx = await orch.run(workflow_id="wf-deps")
        assert ctx.status == WorkflowStatus.COMPLETED
        assert ctx.tasks["consume"].result == 84

    @pytest.mark.asyncio
    async def test_initial_data_passed(self):
        orch = WorkflowOrchestrator()

        async def use_data(**kwargs):
            context = kwargs.get("context")
            return context.data.get("initial_key")

        td = TaskDefinition(
            task_id="data-task",
            task_type=TaskType.PERCEPTION,
            name="Data Test",
            func=use_data,
        )
        orch.add_task(td)

        ctx = await orch.run(
            workflow_id="wf-data",
            initial_data={"initial_key": "initial_value"},
        )
        assert ctx.status == WorkflowStatus.COMPLETED
        assert ctx.tasks["data-task"].result == "initial_value"


class TestWorkflowControl:
    @pytest.mark.asyncio
    async def test_pause_and_resume(self):
        orch = WorkflowOrchestrator()
        paused_hit = False

        async def long_task(**kwargs):
            nonlocal paused_hit
            for _ in range(20):
                await asyncio.sleep(0.01)
            return "done"

        td = TaskDefinition(
            task_id="long",
            task_type=TaskType.PERCEPTION,
            name="Long",
            func=long_task,
        )
        orch.add_task(td)

        async def run_workflow():
            return await orch.run(workflow_id="wf-pause")

        task = asyncio.create_task(run_workflow())
        await asyncio.sleep(0.02)

        orch.pause()
        assert orch.context.status == WorkflowStatus.PAUSED
        assert orch.is_running is False

        orch.resume()
        assert orch.is_running is True

        ctx = await task
        assert ctx.status == WorkflowStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_cancel_workflow(self):
        orch = WorkflowOrchestrator()

        async def long_task(**kwargs):
            for _ in range(50):
                await asyncio.sleep(0.01)
            return "done"

        td = TaskDefinition(
            task_id="long",
            task_type=TaskType.PERCEPTION,
            name="Long",
            func=long_task,
        )
        orch.add_task(td)

        async def run_workflow():
            return await orch.run(workflow_id="wf-cancel")

        task = asyncio.create_task(run_workflow())
        await asyncio.sleep(0.02)

        orch.cancel()
        ctx = await task
        assert ctx.status == WorkflowStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_progress_callback(self):
        orch = WorkflowOrchestrator()
        progress_updates = []

        def on_progress(progress, info):
            progress_updates.append((progress, info["completed"], info["total"]))

        async def task_a(**kwargs):
            return "a"

        async def task_b(**kwargs):
            return "b"

        t1 = TaskDefinition(task_id="t1", task_type=TaskType.PERCEPTION,
                            name="A", func=task_a)
        t2 = TaskDefinition(task_id="t2", task_type=TaskType.UNDERSTANDING,
                            name="B", func=task_b, dependencies=["t1"])
        orch.add_tasks([t1, t2])
        orch.add_progress_callback(on_progress)

        ctx = await orch.run(workflow_id="wf-progress")
        assert ctx.status == WorkflowStatus.COMPLETED
        assert len(progress_updates) >= 1
        final_progress, final_completed, final_total = progress_updates[-1]
        assert final_progress == 1.0
        assert final_completed == 2
        assert final_total == 2


class TestStatusQuery:
    @pytest.mark.asyncio
    async def test_get_task_status(self):
        orch = WorkflowOrchestrator()

        async def task_func(**kwargs):
            return "ok"

        td = TaskDefinition(
            task_id="q-task",
            task_type=TaskType.PERCEPTION,
            name="Query Test",
            func=task_func,
        )
        orch.add_task(td)

        assert orch.get_task_status("q-task") is None

        await orch.run(workflow_id="wf-query")
        assert orch.get_task_status("q-task") == TaskStatus.COMPLETED
        assert orch.get_task_status("nonexistent") is None

    @pytest.mark.asyncio
    async def test_get_task_result(self):
        orch = WorkflowOrchestrator()

        async def task_func(**kwargs):
            return "test-result"

        td = TaskDefinition(
            task_id="r-task",
            task_type=TaskType.PERCEPTION,
            name="Result Test",
            func=task_func,
        )
        orch.add_task(td)

        assert orch.get_task_result("r-task") is None

        await orch.run(workflow_id="wf-result")
        assert orch.get_task_result("r-task") == "test-result"
        assert orch.get_task_result("nonexistent") is None

    @pytest.mark.asyncio
    async def test_get_stats_running(self):
        orch = WorkflowOrchestrator()

        async def task_func(**kwargs):
            await asyncio.sleep(0.02)
            return "ok"

        td = TaskDefinition(
            task_id="s-task",
            task_type=TaskType.PERCEPTION,
            name="Stats Test",
            func=task_func,
        )
        orch.add_task(td)

        async def run_workflow():
            return await orch.run(workflow_id="wf-stats")

        task = asyncio.create_task(run_workflow())
        await asyncio.sleep(0.005)

        stats = orch.get_stats()
        assert "workflow_id" in stats
        assert stats["total_tasks"] == 1
        assert "task_stats" in stats
        assert "duration_seconds" in stats

        await task


class TestSerialization:
    @pytest.mark.asyncio
    async def test_to_dict_completed(self):
        orch = WorkflowOrchestrator()

        async def task_func(**kwargs):
            return "done"

        td = TaskDefinition(
            task_id="ser-task",
            task_type=TaskType.PERCEPTION,
            name="Ser Test",
            func=task_func,
        )
        orch.add_task(td)

        ctx = await orch.run(workflow_id="wf-ser")
        d = orch.to_dict()

        assert d["workflow_id"] == "wf-ser"
        assert d["status"] == "COMPLETED"
        assert "tasks" in d
        assert "ser-task" in d["tasks"]
        assert d["tasks"]["ser-task"]["status"] == "COMPLETED"
        assert d["tasks"]["ser-task"]["result"] == "done"

    def test_to_dict_idle(self):
        orch = WorkflowOrchestrator()
        d = orch.to_dict()
        assert d == {}

    @pytest.mark.asyncio
    async def test_save_to_file(self, tmp_path):
        orch = WorkflowOrchestrator()

        async def task_func(**kwargs):
            return "file-test"

        td = TaskDefinition(
            task_id="file-task",
            task_type=TaskType.PERCEPTION,
            name="File Test",
            func=task_func,
        )
        orch.add_task(td)

        await orch.run(workflow_id="wf-file")
        file_path = tmp_path / "workflow.json"
        orch.save_to_file(str(file_path))

        assert file_path.exists()
        import json
        with open(file_path) as f:
            data = json.load(f)
        assert data["workflow_id"] == "wf-file"
        assert data["status"] == "COMPLETED"


class TestDefaultPipeline:
    def test_build_default_pipeline(self):
        orch = WorkflowOrchestrator()

        funcs = {
            "perceive": lambda **kw: None,
            "understand": lambda **kw: None,
            "plan": lambda **kw: None,
            "execute_silhouette": lambda **kw: None,
            "compile": lambda **kw: None,
            "execute_ae": lambda **kw: None,
            "feedback": lambda **kw: None,
        }

        orch.build_default_pipeline(funcs)
        assert len(orch._tasks_def) == 19

        perception = orch.get_task_def("perception")
        assert perception is not None
        assert perception.task_type == TaskType.PERCEPTION

        ae_exec = orch.get_task_def("ae_execute")
        assert ae_exec is not None
        assert "ae_compile" in ae_exec.dependencies
        assert "silhouette" in ae_exec.dependencies

    @pytest.mark.asyncio
    async def test_default_pipeline_runs(self):
        orch = WorkflowOrchestrator()
        called = set()

        async def perceive(**kw):
            called.add("perceive")
            return {"bpm": 120}

        async def understand(**kw):
            called.add("understand")
            return {"style": "cinematic"}

        async def plan(**kw):
            called.add("plan")
            return {"layers": []}

        async def compile(**kw):
            called.add("compile")
            return "compiled"

        async def execute_ae(**kw):
            called.add("execute_ae")
            return {"rendered": True}

        async def feedback(**kw):
            called.add("feedback")
            return {"quality": "good"}

        funcs = {
            "perceive": perceive,
            "understand": understand,
            "plan": plan,
            "execute_silhouette": lambda **kw: None,
            "compile": compile,
            "execute_ae": execute_ae,
            "feedback": feedback,
        }

        orch.build_default_pipeline(funcs)
        ctx = await asyncio.wait_for(orch.run(workflow_id="wf-default"), timeout=10)

        assert ctx.status == WorkflowStatus.COMPLETED
        assert "perceive" in called
        assert "understand" in called
        assert "plan" in called
        assert "compile" in called
        assert "execute_ae" in called
        assert "feedback" in called


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_empty_workflow(self):
        orch = WorkflowOrchestrator()
        ctx = await orch.run(workflow_id="wf-empty")
        assert ctx.status == WorkflowStatus.COMPLETED
        assert ctx.progress == 0.0

    @pytest.mark.asyncio
    async def test_workflow_id_auto_generated(self):
        orch = WorkflowOrchestrator()

        async def task_func(**kwargs):
            return "ok"

        td = TaskDefinition(
            task_id="t1",
            task_type=TaskType.PERCEPTION,
            name="T1",
            func=task_func,
        )
        orch.add_task(td)

        ctx = await orch.run()
        assert ctx.workflow_id is not None
        assert len(ctx.workflow_id) > 0

    @pytest.mark.asyncio
    async def test_callback_error_does_not_break(self):
        orch = WorkflowOrchestrator()

        def bad_callback(progress, info):
            raise RuntimeError("callback failed")

        async def task_func(**kwargs):
            return "ok"

        td = TaskDefinition(
            task_id="t1",
            task_type=TaskType.PERCEPTION,
            name="T1",
            func=task_func,
        )
        orch.add_task(td)
        orch.add_progress_callback(bad_callback)

        ctx = await orch.run(workflow_id="wf-bad-cb")
        assert ctx.status == WorkflowStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_can_run_task_nonexistent(self):
        orch = WorkflowOrchestrator()
        orch._context = WorkflowContext(workflow_id="test")
        assert orch._can_run_task("nonexistent") is False

    @pytest.mark.asyncio
    async def test_is_workflow_complete_all_tasks(self):
        orch = WorkflowOrchestrator()

        def dummy(**kw):
            pass

        tasks = [
            TaskDefinition(task_id=f"t{i}", task_type=TaskType.PERCEPTION,
                           name=f"T{i}", func=dummy)
            for i in range(3)
        ]
        orch.add_tasks(tasks)
        orch._completed_tasks = {"t0", "t1", "t2"}
        assert orch._is_workflow_complete() is True

    @pytest.mark.asyncio
    async def test_update_progress_zero_tasks(self):
        orch = WorkflowOrchestrator()
        orch._context = WorkflowContext(workflow_id="test")
        orch._update_progress()
        assert orch._context.progress == 0.0
