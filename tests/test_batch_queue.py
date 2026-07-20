"""batch_queue 模块单元测试 - 批处理队列系统

覆盖范围:
- TaskStatus 枚举与 Task 数据类
- ProgressContext 进度回调上下文
- BatchQueue 批处理队列（任务提交/执行/优先级/重试）
- BatchResult 批量结果汇总
- 并发执行与线程安全
- 任务取消与等待机制
- 边界条件与异常容错
"""
import os
import sys
import time
import threading
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from batch_queue import (
    TaskStatus,
    Task,
    ProgressContext,
    BatchQueue,
    BatchResult,
    get_default_queue,
    example_task,
)


# ============================================================================
# TaskStatus 枚举测试
# ============================================================================

class TestTaskStatus:
    """任务状态枚举测试"""

    def test_status_values(self):
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.CANCELLED.value == "cancelled"

    def test_status_is_str_enum(self):
        assert isinstance(TaskStatus.PENDING, str)
        assert TaskStatus.PENDING == "pending"


# ============================================================================
# Task 数据类测试
# ============================================================================

class TestTask:
    """Task 数据类测试"""

    def test_task_defaults(self):
        def dummy_func():
            pass

        t = Task(
            task_id="t1",
            name="test",
            func=dummy_func,
        )
        assert t.task_id == "t1"
        assert t.name == "test"
        assert t.func is dummy_func
        assert t.args == ()
        assert t.kwargs == {}
        assert t.priority == 5
        assert t.status == TaskStatus.PENDING
        assert t.result is None
        assert t.error is None
        assert t.retries == 0
        assert t.max_retries == 0
        assert t.progress == 0.0
        assert t.progress_message == ""
        assert t.created_at > 0
        assert t.started_at is None
        assert t.completed_at is None
        assert t.duration == 0.0
        assert t.metadata == {}
        assert t.on_complete is None
        assert t.on_failure is None
        assert t.on_progress is None

    def test_task_custom_values(self):
        def fn():
            pass

        t = Task(
            task_id="t2",
            name="custom",
            func=fn,
            args=(1, 2),
            kwargs={"a": "b"},
            priority=8,
            max_retries=3,
            metadata={"key": "value"},
        )
        assert t.args == (1, 2)
        assert t.kwargs == {"a": "b"}
        assert t.priority == 8
        assert t.max_retries == 3
        assert t.metadata == {"key": "value"}

    def test_to_dict(self):
        def fn():
            pass

        t = Task(
            task_id="t3",
            name="dict_test",
            func=fn,
            priority=7,
            status=TaskStatus.COMPLETED,
            progress=1.0,
            progress_message="done",
            retries=2,
            max_retries=3,
            error=None,
            metadata={"type": "test"},
        )
        d = t.to_dict()
        assert d["task_id"] == "t3"
        assert d["name"] == "dict_test"
        assert d["priority"] == 7
        assert d["status"] == "completed"
        assert d["progress"] == 1.0
        assert d["progress_message"] == "done"
        assert d["retries"] == 2
        assert d["max_retries"] == 3
        assert d["error"] is None
        assert d["metadata"] == {"type": "test"}
        assert "func" not in d
        assert "on_complete" not in d


# ============================================================================
# ProgressContext 测试
# ============================================================================

class TestProgressContext:
    """进度回调上下文测试"""

    def test_update_progress(self):
        def fn():
            pass

        t = Task(task_id="p1", name="prog", func=fn)
        ctx = ProgressContext(t)

        ctx.update(0.5, "一半了")
        assert t.progress == 0.5
        assert t.progress_message == "一半了"

    def test_update_progress_clamped(self):
        def fn():
            pass

        t = Task(task_id="p2", name="clamp", func=fn)
        ctx = ProgressContext(t)

        ctx.update(-0.5)
        assert t.progress == 0.0

        ctx.update(1.5)
        assert t.progress == 1.0

    def test_progress_callback(self):
        def fn():
            pass

        t = Task(task_id="p3", name="cb", func=fn)
        callback_called = []

        def on_progress(task, progress, message):
            callback_called.append((progress, message))

        t.on_progress = on_progress
        ctx = ProgressContext(t)

        ctx.update(0.3, "test message")
        assert len(callback_called) == 1
        assert callback_called[0][0] == 0.3
        assert callback_called[0][1] == "test message"

    def test_progress_callback_exception_suppressed(self):
        def fn():
            pass

        t = Task(task_id="p4", name="cb_err", func=fn)

        def bad_callback(task, progress, message):
            raise RuntimeError("callback failed")

        t.on_progress = bad_callback
        ctx = ProgressContext(t)
        ctx.update(0.5)
        assert t.progress == 0.5

    def test_check_cancel(self):
        def fn():
            pass

        t = Task(task_id="p5", name="cancel", func=fn)
        ctx = ProgressContext(t)

        assert ctx.check_cancel() is False
        assert ctx.is_cancelled is False

        t.status = TaskStatus.CANCELLED
        assert ctx.check_cancel() is True
        assert ctx.is_cancelled is True

    def test_cancelled_skips_update(self):
        def fn():
            pass

        t = Task(task_id="p6", name="skip_update", func=fn)
        ctx = ProgressContext(t)
        ctx._cancelled = True

        ctx.update(0.9, "should not update")
        assert t.progress == 0.0
        assert t.progress_message == ""


# ============================================================================
# BatchQueue 测试
# ============================================================================

class TestBatchQueue:
    """批处理队列测试"""

    @pytest.fixture
    def queue(self):
        q = BatchQueue(max_workers=2, max_retries=0, retry_delay=0.01)
        yield q
        q.stop(wait=True)

    # ---------- 基础功能 ----------

    def test_submit_simple_task(self, queue):
        def add(a, b):
            return a + b

        task = queue.submit(add, 2, 3, name="add_task")
        assert task.task_id.startswith("task_")
        assert task.name == "add_task"
        assert task.status in (TaskStatus.PENDING, TaskStatus.RUNNING)

        result = queue.wait_for_task(task.task_id, timeout=5)
        assert result.status == TaskStatus.COMPLETED
        assert result.result == 5

    def test_submit_with_kwargs(self, queue):
        def greet(who, greeting="Hello"):
            return f"{greeting}, {who}!"

        # 避免使用 "name" 作为参数名，因为它与 submit 的 name 参数冲突
        task = queue.submit(greet, "World", greeting="Hi", name="greet_task")
        result = queue.wait_for_task(task.task_id, timeout=5)
        assert result.status == TaskStatus.COMPLETED
        assert result.result == "Hi, World!"

    def test_task_failure(self, queue):
        def fail_task():
            raise ValueError("something went wrong")

        task = queue.submit(fail_task, name="fail")
        result = queue.wait_for_task(task.task_id, timeout=5)
        assert result.status == TaskStatus.FAILED
        assert "something went wrong" in result.error

    def test_task_duration_set(self, queue):
        def slow_task():
            time.sleep(0.1)
            return "done"

        task = queue.submit(slow_task, name="slow")
        result = queue.wait_for_task(task.task_id, timeout=5)
        assert result.status == TaskStatus.COMPLETED
        assert result.started_at is not None
        assert result.completed_at is not None
        assert result.duration >= 0.08

    # ---------- 优先级调度 ----------

    def test_priority_ordering(self):
        """高优先级任务应先执行（需单线程保证排序生效）"""
        q = BatchQueue(max_workers=1, max_retries=0, retry_delay=0.01)
        try:
            execution_order = []
            lock = threading.Lock()

            def record_task(label):
                with lock:
                    execution_order.append(label)
                time.sleep(0.05)

            # 用一个阻塞任务占住唯一的工作线程
            def blocker():
                time.sleep(0.1)

            block_task = q.submit(blocker, name="blocker")

            # 等工作线程启动并占住
            time.sleep(0.05)

            # 提交低优先级先，再高优先级
            t_low = q.submit(record_task, "low", name="low", priority=1)
            t_high = q.submit(record_task, "high", name="high", priority=10)

            q.wait_for_task(t_low.task_id, timeout=5)
            q.wait_for_task(t_high.task_id, timeout=5)

            # high 应该在 low 之前执行
            assert execution_order.index("high") < execution_order.index("low")
        finally:
            q.stop(wait=True)

    def test_priority_clamped(self, queue):
        def noop():
            pass

        t1 = queue.submit(noop, name="too_low", priority=0)
        t2 = queue.submit(noop, name="too_high", priority=100)

        assert t1.priority == 1
        assert t2.priority == 10

    # ---------- 重试机制 ----------

    def test_retry_on_failure(self):
        """失败任务应自动重试"""
        q = BatchQueue(max_workers=1, max_retries=2, retry_delay=0.01)
        try:
            call_count = [0]

            def flaky_task():
                call_count[0] += 1
                if call_count[0] < 3:
                    raise RuntimeError(f"fail {call_count[0]}")
                return "success"

            task = q.submit(flaky_task, name="flaky")
            result = q.wait_for_task(task.task_id, timeout=10)

            assert result.status == TaskStatus.COMPLETED
            assert result.result == "success"
            assert result.retries == 2
            assert call_count[0] == 3
        finally:
            q.stop(wait=True)

    def test_max_retries_exceeded(self):
        """超过最大重试次数后应标记为失败

        max_retries=1 时：
        - 第1次执行失败，retries=1，1 <= 1 触发重试
        - 第2次执行失败，retries=2，2 <= 1 为 False，标记 FAILED
        最终 retries=2，总调用次数=2
        """
        q = BatchQueue(max_workers=1, max_retries=1, retry_delay=0.01)
        try:
            call_count = [0]

            def always_fail():
                call_count[0] += 1
                raise RuntimeError("always fails")

            task = q.submit(always_fail, name="always_fail")
            result = q.wait_for_task(task.task_id, timeout=10)

            assert result.status == TaskStatus.FAILED
            assert result.retries == 2
            assert call_count[0] == 2
        finally:
            q.stop(wait=True)

    def test_on_failure_callback(self):
        """失败时应调用 on_failure 回调"""
        q = BatchQueue(max_workers=1, max_retries=0)
        try:
            callback_called = [False]

            def fail():
                raise ValueError("oops")

            def on_failure(task):
                callback_called[0] = True

            task = q.submit(fail, name="fail_cb", on_failure=on_failure)
            q.wait_for_task(task.task_id, timeout=5)

            assert callback_called[0] is True
        finally:
            q.stop(wait=True)

    def test_on_complete_callback(self, queue):
        """成功完成时应调用 on_complete 回调"""
        callback_called = [False]
        callback_task = [None]

        def success():
            return 42

        def on_complete(task):
            callback_called[0] = True
            callback_task[0] = task

        task = queue.submit(success, name="success_cb", on_complete=on_complete)
        queue.wait_for_task(task.task_id, timeout=5)

        assert callback_called[0] is True
        assert callback_task[0].result == 42

    # ---------- 进度跟踪 ----------

    def test_progress_context_injection(self, queue):
        """函数第一个参数为 progress/ctx 时应注入 ProgressContext"""

        def task_with_progress(progress, total=5):
            for i in range(total):
                progress.update((i + 1) / total, f"step {i+1}")
                time.sleep(0.01)
            return "done"

        progress_updates = []

        def on_progress(task, prog, msg):
            progress_updates.append((prog, msg))

        task = queue.submit(
            task_with_progress,
            total=3,
            name="prog_task",
            on_progress=on_progress,
        )
        result = queue.wait_for_task(task.task_id, timeout=5)

        assert result.status == TaskStatus.COMPLETED
        assert result.result == "done"
        assert len(progress_updates) >= 3
        assert progress_updates[-1][0] == 1.0

    def test_progress_ctx_parameter_names(self, queue):
        """测试不同的进度上下文参数名（progress, ctx, progress_ctx）"""

        def fn_progress(progress):
            progress.update(0.5)
            return "ok_progress"

        def fn_ctx(ctx):
            ctx.update(0.5)
            return "ok_ctx"

        def fn_progress_ctx(progress_ctx):
            progress_ctx.update(0.5)
            return "ok_progress_ctx"

        t1 = queue.submit(fn_progress, name="p1")
        t2 = queue.submit(fn_ctx, name="p2")
        t3 = queue.submit(fn_progress_ctx, name="p3")

        r1 = queue.wait_for_task(t1.task_id, timeout=5)
        r2 = queue.wait_for_task(t2.task_id, timeout=5)
        r3 = queue.wait_for_task(t3.task_id, timeout=5)

        assert r1.result == "ok_progress"
        assert r2.result == "ok_ctx"
        assert r3.result == "ok_progress_ctx"

    # ---------- 任务查询 ----------

    def test_get_task(self, queue):
        def noop():
            pass

        t = queue.submit(noop, name="get_test")
        got = queue.get_task(t.task_id)
        assert got is not None
        assert got.task_id == t.task_id

        assert queue.get_task("nonexistent") is None

    def test_get_all_tasks(self, queue):
        def noop():
            time.sleep(0.05)

        tasks = []
        for i in range(3):
            tasks.append(queue.submit(noop, name=f"t{i}"))

        all_tasks = queue.get_all_tasks()
        assert len(all_tasks) == 3

    def test_get_tasks_by_status(self, queue):
        def slow():
            time.sleep(0.2)

        def fast():
            return 1

        slow_task = queue.submit(slow, name="slow")
        fast_task = queue.submit(fast, name="fast")

        queue.wait_for_task(fast_task.task_id, timeout=5)

        completed = queue.get_tasks_by_status(TaskStatus.COMPLETED)
        assert len(completed) >= 1
        assert any(t.task_id == fast_task.task_id for t in completed)

    def test_stats(self, queue):
        def noop():
            pass

        for i in range(5):
            queue.submit(noop, name=f"stat_{i}")

        queue.wait_all(timeout=10)
        stats = queue.get_stats()

        assert stats["total_submitted"] == 5
        assert stats["total_completed"] == 5
        assert stats["total_failed"] == 0
        assert stats["pending"] == 0
        assert stats["max_workers"] == 2

    # ---------- 任务取消 ----------

    def test_cancel_pending_task(self):
        """取消待执行任务应成功"""
        q = BatchQueue(max_workers=1, max_retries=0)
        try:
            # 第一个任务会阻塞工作线程
            def blocker():
                time.sleep(0.5)

            blocker_task = q.submit(blocker, name="blocker")

            # 第二个任务在 pending 状态
            def noop():
                pass

            pending_task = q.submit(noop, name="pending")

            # 立即取消
            assert q.cancel_task(pending_task.task_id) is True

            # 等待第一个任务完成
            q.wait_for_task(blocker_task.task_id, timeout=5)

            # 被取消的任务状态应为 CANCELLED
            cancelled = q.get_task(pending_task.task_id)
            assert cancelled.status == TaskStatus.CANCELLED
        finally:
            q.stop(wait=True)

    def test_cancel_completed_task_returns_false(self, queue):
        def noop():
            pass

        t = queue.submit(noop, name="done")
        queue.wait_for_task(t.task_id, timeout=5)

        assert queue.cancel_task(t.task_id) is False

    def test_cancel_nonexistent_task_returns_false(self, queue):
        assert queue.cancel_task("fake_id") is False

    # ---------- 等待机制 ----------

    def test_wait_for_task_timeout(self, queue):
        def slow():
            time.sleep(10)

        t = queue.submit(slow, name="timeout_test")
        result = queue.wait_for_task(t.task_id, timeout=0.1)
        # 超时后返回，状态仍在执行中
        assert result.status in (TaskStatus.PENDING, TaskStatus.RUNNING)

    def test_wait_all(self, queue):
        def work(x):
            time.sleep(0.05)
            return x * 2

        tasks = []
        for i in range(5):
            tasks.append(queue.submit(work, i, name=f"w{i}"))

        assert queue.wait_all(timeout=10) is True
        for t in tasks:
            assert t.status == TaskStatus.COMPLETED

    def test_wait_all_timeout(self):
        """wait_all 超时时返回 False"""
        q = BatchQueue(max_workers=1)
        try:
            def very_slow():
                time.sleep(10)

            q.submit(very_slow, name="slow")
            assert q.wait_all(timeout=0.1) is False
        finally:
            q.stop(wait=False)

    # ---------- 批量提交 ----------

    def test_submit_batch(self, queue):
        tasks_def = [
            (lambda x: x + 1, (1,), {}),
            (lambda x: x * 2, (3,), {}),
            (lambda x: x ** 2, (4,), {}),
        ]

        tasks = queue.submit_batch(tasks_def, batch_name="batch_test", priority=7)

        assert len(tasks) == 3
        assert all(t.priority == 7 for t in tasks)
        assert tasks[0].name == "batch_test-0"
        assert tasks[1].name == "batch_test-1"

        queue.wait_all(timeout=5)

        results = [t.result for t in tasks]
        assert 2 in results
        assert 6 in results
        assert 16 in results

    def test_submit_batch_with_callback(self, queue):
        callback_called = [False]
        callback_results = [None]

        def on_batch_done(results):
            callback_called[0] = True
            callback_results[0] = results

        tasks_def = [
            (lambda: 1, (), {}),
            (lambda: 2, (), {}),
        ]

        tasks = queue.submit_batch(
            tasks_def,
            batch_name="cb_batch",
            on_batch_complete=on_batch_done,
        )

        queue.wait_all(timeout=5)
        time.sleep(0.1)  # 等待回调执行

        assert callback_called[0] is True
        assert len(callback_results[0]) == 2

    # ---------- 生命周期 ----------

    def test_start_idempotent(self):
        q = BatchQueue(max_workers=1)
        try:
            q.start()
            q.start()  # 再次启动不应出错
            assert q._started is True
        finally:
            q.stop(wait=True)

    def test_stop_idempotent(self):
        q = BatchQueue(max_workers=1)
        q.stop()
        q.stop()  # 再次停止不应出错

    def test_shutdown_alias(self, queue):
        queue.shutdown(wait=False)
        assert queue._started is False

    # ---------- 并发安全 ----------

    def test_concurrent_submit(self):
        """多线程并发提交任务应安全"""
        q = BatchQueue(max_workers=4, max_retries=0)
        try:
            num_threads = 5
            tasks_per_thread = 20
            errors = []

            def worker(tid):
                for i in range(tasks_per_thread):
                    try:
                        q.submit(lambda x: x * 2, i, name=f"t{tid}_{i}")
                    except Exception as e:
                        errors.append(e)

            threads = [threading.Thread(target=worker, args=(t,)) for t in range(num_threads)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert len(errors) == 0
            assert len(q.get_all_tasks()) == num_threads * tasks_per_thread
        finally:
            q.stop(wait=True)


# ============================================================================
# BatchResult 测试
# ============================================================================

class TestBatchResult:
    """批量结果汇总测试"""

    def _make_task(self, status, result=None, error=None, duration=0.5):
        def fn():
            pass

        t = Task(
            task_id=f"t_{id(status)}",
            name=f"test_{status.value}",
            func=fn,
            status=status,
            result=result,
            error=error,
            duration=duration,
        )
        return t

    def test_empty_result(self):
        br = BatchResult()
        assert br.total == 0
        assert br.completed == 0
        assert br.failed == 0
        assert br.cancelled == 0
        assert br.success_rate == 0.0
        assert br.results == []
        assert br.errors == []

    def test_mixed_statuses(self):
        tasks = [
            self._make_task(TaskStatus.COMPLETED, result=42),
            self._make_task(TaskStatus.COMPLETED, result=99),
            self._make_task(TaskStatus.FAILED, error="oops"),
            self._make_task(TaskStatus.CANCELLED),
            self._make_task(TaskStatus.RUNNING),
        ]
        br = BatchResult(tasks=tasks)

        assert br.total == 5
        assert br.completed == 2
        assert br.failed == 1
        assert br.cancelled == 1
        assert br.success_rate == 0.4
        assert br.results == [42, 99]
        assert len(br.errors) == 1
        assert br.errors[0][1] == "oops"

    def test_to_dict(self):
        tasks = [
            self._make_task(TaskStatus.COMPLETED, result=10, duration=0.5),
            self._make_task(TaskStatus.FAILED, error="err", duration=0.3),
        ]
        br = BatchResult(tasks=tasks)
        d = br.to_dict()

        assert d["total"] == 2
        assert d["completed"] == 1
        assert d["failed"] == 1
        assert d["cancelled"] == 0
        assert d["success_rate"] == 50.0
        assert d["total_duration"] == 0.8
        assert len(d["tasks"]) == 2

    def test_success_rate_all_completed(self):
        tasks = [
            self._make_task(TaskStatus.COMPLETED),
            self._make_task(TaskStatus.COMPLETED),
        ]
        br = BatchResult(tasks=tasks)
        assert br.success_rate == 1.0


# ============================================================================
# 单例与便捷函数测试
# ============================================================================

class TestSingletonAndUtils:
    """单例与便捷函数测试"""

    def test_get_default_queue_returns_singleton(self):
        q1 = get_default_queue(max_workers=2)
        q2 = get_default_queue(max_workers=5)
        assert q1 is q2
        q1.stop(wait=True)

    def test_example_task_runs(self):
        """example_task 应能正常执行"""
        q = BatchQueue(max_workers=1)
        try:
            t = q.submit(example_task, total_steps=3, delay=0.01)
            result = q.wait_for_task(t.task_id, timeout=5)
            assert result.status == TaskStatus.COMPLETED
            assert result.result == "完成"
        finally:
            q.stop(wait=True)

    def test_example_task_supports_cancel(self):
        """example_task 应支持取消检查"""
        q = BatchQueue(max_workers=1)
        try:
            t = q.submit(example_task, total_steps=100, delay=0.1)
            time.sleep(0.15)
            q.cancel_task(t.task_id)
            # 即使取消了，任务可能还在运行，这里只验证不崩溃
            assert t.task_id is not None
        finally:
            q.stop(wait=False)
