#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分布式任务调度器
================

提供轻量级分布式任务调度能力，支持多 worker 并发、任务路由、
定时调度等。接口设计兼容 Celery，方便未来迁移。

功能:
- 多 worker 进程/线程并发执行
- 任务路由（按类型分配到不同队列）
- 定时任务调度（cron 表达式）
- 任务优先级与权重
- 任务结果存储与查询
- worker 心跳与注册
- 优雅关闭与任务恢复
- 与数据库持久化集成

架构:
  Producer → [Queue] → Worker(s) → Result Store
                ↑           ↓
              Scheduler   Database
"""

from __future__ import annotations

import heapq
import json
import os
import signal
import threading
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

try:
    from logger import get_logger
    _logger = get_logger("scheduler")
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    _logger = logging.getLogger("scheduler")


# ============================================================================
# 任务状态枚举
# ============================================================================

class TaskState(str, Enum):
    QUEUED = "queued"
    RESERVED = "reserved"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    REVOKED = "revoked"
    RETRY = "retry"


# ============================================================================
# 任务定义
# ============================================================================

@dataclass(order=True)
class ScheduledTask:
    """调度任务"""
    priority: int = 0  # 负数 = 高优先级（heapq 最小堆）
    scheduled_at: float = field(default_factory=time.time)
    task_id: str = field(default_factory=lambda: f"sched_{uuid.uuid4().hex[:12]}")
    name: str = ""
    func: Callable[..., Any] = None
    args: tuple = ()
    kwargs: dict[str, Any] = field(default_factory=dict)
    queue: str = "default"
    retries: int = 0
    max_retries: int = 3
    timeout: float = 300.0
    eta: float | None = None  # 延迟执行时间
    countdown: float = 0.0  # 倒计时（秒）
    expires: float | None = None  # 过期时间
    result: Any = None
    error: str | None = None
    state: TaskState = TaskState.QUEUED
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None
    worker_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "queue": self.queue,
            "state": self.state.value,
            "priority": self.priority,
            "retries": self.retries,
            "max_retries": self.max_retries,
            "timeout": self.timeout,
            "eta": self.eta,
            "expires": self.expires,
            "result": str(self.result) if self.result is not None else None,
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "worker_id": self.worker_id,
            "metadata": self.metadata,
        }


# ============================================================================
# Worker 信息
# ============================================================================

@dataclass
class WorkerInfo:
    """Worker 信息"""
    worker_id: str
    hostname: str = ""
    pid: int = 0
    queues: list[str] = field(default_factory=lambda: ["default"])
    concurrency: int = 1
    last_heartbeat: float = field(default_factory=time.time)
    active_tasks: int = 0
    total_completed: int = 0
    total_failed: int = 0
    is_online: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "hostname": self.hostname,
            "pid": self.pid,
            "queues": self.queues,
            "concurrency": self.concurrency,
            "last_heartbeat": self.last_heartbeat,
            "active_tasks": self.active_tasks,
            "total_completed": self.total_completed,
            "total_failed": self.total_failed,
            "is_online": self.is_online,
            "uptime": time.time() - self.last_heartbeat,
        }


# ============================================================================
# 任务队列
# ============================================================================

class TaskQueue:
    """线程安全的优先级任务队列"""

    def __init__(self, name: str = "default"):
        self._name = name
        self._heap: list[ScheduledTask] = []
        self._lock = threading.Lock()
        self._not_empty = threading.Condition(self._lock)
        self._size = 0

    @property
    def name(self) -> str:
        return self._name

    def put(self, task: ScheduledTask):
        """放入任务"""
        with self._not_empty:
            heapq.heappush(self._heap, task)
            self._size += 1
            self._not_empty.notify()

    def get(self, timeout: float = 1.0) -> ScheduledTask | None:
        """获取任务（阻塞）"""
        with self._not_empty:
            if not self._heap:
                self._not_empty.wait(timeout=timeout)
            if self._heap:
                task = heapq.heappop(self._heap)
                self._size -= 1
                return task
            return None

    def peek(self) -> ScheduledTask | None:
        """查看队列头部任务（不取出）"""
        with self._lock:
            return self._heap[0] if self._heap else None

    @property
    def size(self) -> int:
        with self._lock:
            return self._size

    def clear(self) -> int:
        """清空队列"""
        with self._lock:
            count = self._size
            self._heap.clear()
            self._size = 0
            return count


# ============================================================================
# 任务结果存储
# ============================================================================

class ResultStore:
    """任务结果存储"""

    def __init__(self, max_size: int = 10000):
        self._results: dict[str, ScheduledTask] = {}
        self._lock = threading.RLock()
        self._max_size = max_size

    def store(self, task: ScheduledTask):
        """存储任务结果"""
        with self._lock:
            self._results[task.task_id] = task
            if len(self._results) > self._max_size:
                oldest = sorted(self._results.values(), key=lambda t: t.completed_at or 0)
                for t in oldest[:len(self._results) - self._max_size]:
                    del self._results[t.task_id]

    def get(self, task_id: str) -> ScheduledTask | None:
        """获取任务结果"""
        with self._lock:
            return self._results.get(task_id)

    def remove(self, task_id: str) -> bool:
        """移除结果"""
        with self._lock:
            if task_id in self._results:
                del self._results[task_id]
                return True
            return False

    def get_all(self) -> list[dict[str, Any]]:
        """获取所有结果"""
        with self._lock:
            return [t.to_dict() for t in self._results.values()]

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._results)


# ============================================================================
# 定时任务调度器
# ============================================================================

class CronScheduler:
    """定时任务调度器（简化版 cron）"""

    def __init__(self):
        self._schedules: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()
        self._running = False
        self._thread: threading.Thread | None = None

    def add_schedule(
        self,
        name: str,
        func: Callable,
        interval: float,
        args: tuple = (),
        kwargs: dict[str, Any] | None = None,
        queue: str = "default",
    ):
        """添加定时任务

        Args:
            name: 任务名称
            func: 要执行的函数
            interval: 执行间隔（秒）
            args: 位置参数
            kwargs: 关键字参数
            queue: 目标队列
        """
        with self._lock:
            self._schedules[name] = {
                "func": func,
                "interval": interval,
                "args": args,
                "kwargs": kwargs or {},
                "queue": queue,
                "last_run": 0,
                "next_run": time.time() + interval,
                "run_count": 0,
            }
            _logger.info(f"定时任务已添加: {name} (间隔 {interval}s)")

    def remove_schedule(self, name: str) -> bool:
        """移除定时任务"""
        with self._lock:
            if name in self._schedules:
                del self._schedules[name]
                _logger.info(f"定时任务已移除: {name}")
                return True
            return False

    def start(self, submit_func: Callable[[Callable, tuple, dict, str], str]):
        """启动调度器"""
        self._running = True
        self._submit_func = submit_func

        def loop():
            while self._running:
                now = time.time()
                with self._lock:
                    for name, sched in self._schedules.items():
                        if now >= sched["next_run"]:
                            try:
                                task_id = self._submit_func(
                                    sched["func"],
                                    sched["args"],
                                    sched["kwargs"],
                                    sched["queue"],
                                )
                                sched["last_run"] = now
                                sched["next_run"] = now + sched["interval"]
                                sched["run_count"] += 1
                                _logger.debug(f"定时任务触发: {name} -> {task_id}")
                            except Exception as e:
                                _logger.error(f"定时任务执行失败 {name}: {e}")
                time.sleep(0.5)

        self._thread = threading.Thread(target=loop, daemon=True, name="CronScheduler")
        self._thread.start()
        _logger.info("定时任务调度器已启动")

    def stop(self):
        """停止调度器"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        _logger.info("定时任务调度器已停止")

    def get_schedules(self) -> list[dict[str, Any]]:
        """获取所有定时任务"""
        with self._lock:
            return [
                {
                    "name": name,
                    "interval": sched["interval"],
                    "last_run": sched["last_run"],
                    "next_run": sched["next_run"],
                    "run_count": sched["run_count"],
                    "queue": sched["queue"],
                }
                for name, sched in self._schedules.items()
            ]


# ============================================================================
# Worker
# ============================================================================

class Worker:
    """任务执行 Worker"""

    def __init__(
        self,
        worker_id: str | None = None,
        queues: list[str] | None = None,
        concurrency: int = 2,
        scheduler: DistributedScheduler | None = None,
    ):
        self.worker_id = worker_id or f"worker_{uuid.uuid4().hex[:8]}"
        self.queues = queues or ["default"]
        self.concurrency = concurrency
        self._scheduler = scheduler
        self._info = WorkerInfo(
            worker_id=self.worker_id,
            hostname=os.environ.get("COMPUTERNAME", "localhost"),
            pid=os.getpid(),
            queues=self.queues,
            concurrency=concurrency,
        )
        self._threads: list[threading.Thread] = []
        self._running = False
        self._stop_event = threading.Event()

    def start(self):
        """启动 Worker"""
        if self._running:
            return
        self._running = True
        self._stop_event.clear()

        for i in range(self.concurrency):
            t = threading.Thread(
                target=self._process_loop,
                name=f"{self.worker_id}-{i}",
                daemon=True,
            )
            t.start()
            self._threads.append(t)

        _logger.info(f"Worker {self.worker_id} 已启动 (并发数: {self.concurrency})")

    def stop(self, timeout: float = 10):
        """停止 Worker"""
        self._running = False
        self._stop_event.set()

        for t in self._threads:
            t.join(timeout=timeout)
        self._threads.clear()

        if self._info:
            self._info.is_online = False

        _logger.info(f"Worker {self.worker_id} 已停止")

    def _process_loop(self):
        """任务处理主循环"""
        while self._running and not self._stop_event.is_set():
            task = self._fetch_task()
            if task is None:
                time.sleep(0.1)
                continue
            self._execute_task(task)

    def _fetch_task(self) -> ScheduledTask | None:
        """从队列获取任务"""
        if not self._scheduler:
            return None

        for queue_name in self.queues:
            queue = self._scheduler.get_queue(queue_name)
            if queue:
                task = queue.get(timeout=0.1)
                if task:
                    return task
        return None

    def _execute_task(self, task: ScheduledTask):
        """执行任务"""
        task.state = TaskState.RUNNING
        task.started_at = time.time()
        task.worker_id = self.worker_id
        self._info.active_tasks += 1

        if self._scheduler:
            self._scheduler._update_worker_heartbeat(self.worker_id)

        _logger.info(f"执行任务: {task.name} ({task.task_id})")

        try:
            if task.timeout > 0:
                result = self._run_with_timeout(task)
            else:
                result = task.func(*task.args, **task.kwargs)

            task.result = result
            task.state = TaskState.SUCCESS
            task.completed_at = time.time()
            self._info.total_completed += 1
            _logger.info(f"任务完成: {task.name} ({task.task_id})")

        except Exception as e:
            task.error = str(e)
            task.completed_at = time.time()

            if task.retries < task.max_retries:
                task.retries += 1
                task.state = TaskState.RETRY
                _logger.warning(f"任务重试: {task.name} ({task.retries}/{task.max_retries})")

                time.sleep(min(2 ** task.retries, 30))

                task.state = TaskState.QUEUED
                task.started_at = None
                task.completed_at = None
                task.error = None

                if self._scheduler:
                    queue = self._scheduler.get_queue(task.queue)
                    if queue:
                        queue.put(task)
            else:
                task.state = TaskState.FAILURE
                self._info.total_failed += 1
                _logger.error(f"任务失败: {task.name} ({task.task_id}): {e}")

        finally:
            self._info.active_tasks -= 1

            if self._scheduler and self._scheduler._result_store:
                self._scheduler._result_store.store(task)

            if self._scheduler:
                self._scheduler._update_worker_heartbeat(self.worker_id)

    def _run_with_timeout(self, task: ScheduledTask) -> Any:
        """带超时执行"""
        result_container: list[Any] = [None]
        exception_container: list[Exception | None] = [None]

        def target():
            try:
                result_container[0] = task.func(*task.args, **task.kwargs)
            except Exception as e:
                exception_container[0] = e

        thread = threading.Thread(target=target, daemon=True)
        thread.start()
        thread.join(timeout=task.timeout)

        if thread.is_alive():
            raise TimeoutError(f"任务超时 ({task.timeout}s)")

        if exception_container[0]:
            raise exception_container[0]

        return result_container[0]

    @property
    def info(self) -> WorkerInfo:
        return self._info


# ============================================================================
# 分布式调度器
# ============================================================================

class DistributedScheduler:
    """分布式任务调度器

    管理多个队列、worker 和定时任务，提供统一的任务调度接口。
    """

    def __init__(self, default_queues: list[str] | None = None):
        self._queues: dict[str, TaskQueue] = {}
        self._workers: dict[str, Worker] = {}
        self._result_store = ResultStore()
        self._cron = CronScheduler()
        self._lock = threading.RLock()

        for q in (default_queues or ["default"]):
            self._queues[q] = TaskQueue(q)

        self._heartbeat_thread: threading.Thread | None = None
        self._running = False

    # --------------------------------------------------------------------
    # 队列管理
    # --------------------------------------------------------------------

    def get_queue(self, name: str) -> TaskQueue | None:
        """获取队列"""
        with self._lock:
            return self._queues.get(name)

    def ensure_queue(self, name: str) -> TaskQueue:
        """确保队列存在"""
        with self._lock:
            if name not in self._queues:
                self._queues[name] = TaskQueue(name)
            return self._queues[name]

    def get_queue_stats(self) -> dict[str, int]:
        """获取队列统计"""
        with self._lock:
            return {name: q.size for name, q in self._queues.items()}

    # --------------------------------------------------------------------
    # 任务提交
    # --------------------------------------------------------------------

    def submit(
        self,
        func: Callable[..., Any],
        args: tuple = (),
        kwargs: dict[str, Any] | None = None,
        queue: str = "default",
        priority: int = 5,
        name: str = "",
        timeout: float = 300.0,
        countdown: float = 0.0,
        max_retries: int = 3,
    ) -> str:
        """提交任务

        Args:
            func: 要执行的函数
            args: 位置参数
            kwargs: 关键字参数
            queue: 目标队列
            priority: 优先级（1-10，越高越优先）
            name: 任务名称
            timeout: 超时时间
            countdown: 延迟执行（秒）
            max_retries: 最大重试次数

        Returns:
            任务 ID
        """
        task = ScheduledTask(
            func=func,
            args=args,
            kwargs=kwargs or {},
            queue=queue,
            priority=-priority,  # heapq 是最小堆
            name=name or func.__name__,
            timeout=timeout,
            countdown=countdown,
            max_retries=max_retries,
            eta=time.time() + countdown if countdown > 0 else None,
        )

        q = self.ensure_queue(queue)

        if countdown > 0:
            def delayed_put():
                time.sleep(countdown)
                q.put(task)
            threading.Thread(target=delayed_put, daemon=True).start()
        else:
            q.put(task)

        _logger.info(f"任务已提交: {task.name} -> {queue} ({task.task_id})")
        return task.task_id

    def submit_task(self, task: ScheduledTask) -> str:
        """提交预构建的任务"""
        q = self.ensure_queue(task.queue)
        q.put(task)
        return task.task_id

    # --------------------------------------------------------------------
    # 任务查询
    # --------------------------------------------------------------------

    def get_result(self, task_id: str) -> dict[str, Any] | None:
        """获取任务结果"""
        task = self._result_store.get(task_id)
        return task.to_dict() if task else None

    def wait_for_result(self, task_id: str, timeout: float = 60.0) -> dict[str, Any] | None:
        """等待任务结果"""
        start = time.time()
        while time.time() - start < timeout:
            result = self.get_result(task_id)
            if result and result["state"] in (TaskState.SUCCESS.value, TaskState.FAILURE.value):
                return result
            time.sleep(0.2)
        return None

    def revoke_task(self, task_id: str) -> bool:
        """撤销任务"""
        with self._lock:
            for queue in self._queues.values():
                if queue.size > 0:
                    result = self._result_store.get(task_id)
                    if result:
                        result.state = TaskState.REVOKED
                        return True
        return False

    # --------------------------------------------------------------------
    # Worker 管理
    # --------------------------------------------------------------------

    def add_worker(
        self,
        worker_id: str | None = None,
        queues: list[str] | None = None,
        concurrency: int = 2,
    ) -> Worker:
        """添加 Worker"""
        worker = Worker(
            worker_id=worker_id,
            queues=queues or ["default"],
            concurrency=concurrency,
            scheduler=self,
        )
        with self._lock:
            self._workers[worker.worker_id] = worker
        worker.start()
        return worker

    def remove_worker(self, worker_id: str, timeout: float = 10):
        """移除 Worker"""
        with self._lock:
            worker = self._workers.pop(worker_id, None)
        if worker:
            worker.stop(timeout=timeout)

    def get_workers(self) -> list[dict[str, Any]]:
        """获取所有 Worker 信息"""
        with self._lock:
            return [w.info.to_dict() for w in self._workers.values()]

    def _update_worker_heartbeat(self, worker_id: str):
        """更新 Worker 心跳"""
        with self._lock:
            worker = self._workers.get(worker_id)
            if worker:
                worker.info.last_heartbeat = time.time()

    def _check_worker_health(self):
        """检查 Worker 健康"""
        now = time.time()
        with self._lock:
            for worker in self._workers.values():
                if now - worker.info.last_heartbeat > 60:
                    worker.info.is_online = False
                    _logger.warning(f"Worker 离线: {worker.worker_id}")

    # --------------------------------------------------------------------
    # 定时任务
    # --------------------------------------------------------------------

    def add_cron_schedule(
        self,
        name: str,
        func: Callable,
        interval: float,
        args: tuple = (),
        kwargs: dict[str, Any] | None = None,
        queue: str = "default",
    ):
        """添加定时任务"""
        self._cron.add_schedule(name, func, interval, args, kwargs, queue)

    def remove_cron_schedule(self, name: str) -> bool:
        """移除定时任务"""
        return self._cron.remove_schedule(name)

    def get_cron_schedules(self) -> list[dict[str, Any]]:
        """获取定时任务列表"""
        return self._cron.get_schedules()

    # --------------------------------------------------------------------
    # 生命周期
    # --------------------------------------------------------------------

    def start(self):
        """启动调度器"""
        self._running = True
        self._cron.start(self.submit)

        def heartbeat_loop():
            while self._running:
                self._check_worker_health()
                time.sleep(10)

        self._heartbeat_thread = threading.Thread(
            target=heartbeat_loop, daemon=True, name="HeartbeatChecker"
        )
        self._heartbeat_thread.start()

        _logger.info("分布式调度器已启动")

    def stop(self):
        """停止调度器"""
        self._running = False
        self._cron.stop()

        with self._lock:
            for worker in list(self._workers.values()):
                worker.stop()

        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=5)

        _logger.info("分布式调度器已停止")

    # --------------------------------------------------------------------
    # 统计
    # --------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            total_queued = sum(q.size for q in self._queues.values())
            online_workers = sum(1 for w in self._workers.values() if w.info.is_online)
            total_completed = sum(w.info.total_completed for w in self._workers.values())
            total_failed = sum(w.info.total_failed for w in self._workers.values())

            return {
                "queues": {name: q.size for name, q in self._queues.items()},
                "total_queued": total_queued,
                "workers": {
                    "total": len(self._workers),
                    "online": online_workers,
                    "offline": len(self._workers) - online_workers,
                },
                "results_stored": self._result_store.size,
                "total_completed": total_completed,
                "total_failed": total_failed,
                "cron_schedules": len(self._cron.get_schedules()),
            }


# ============================================================================
# 任务装饰器（兼容 Celery 风格）
# ============================================================================

_default_scheduler: DistributedScheduler | None = None


def get_scheduler() -> DistributedScheduler:
    """获取默认调度器"""
    global _default_scheduler
    if _default_scheduler is None:
        _default_scheduler = DistributedScheduler()
        _default_scheduler.start()
    return _default_scheduler


def task(
    queue: str = "default",
    priority: int = 5,
    timeout: float = 300.0,
    max_retries: int = 3,
):
    """任务装饰器（类似 Celery @task）

    使用方式:
        @task(queue="render", priority=8)
        def render_video(input_path, output_path):
            ...

        # 同步调用
        result = render_video("input.mp4", "output.mp4")

        # 异步提交
        task_id = render_video.delay("input.mp4", "output.mp4")
    """
    def decorator(func: Callable):
        def delay(*args, **kwargs) -> str:
            scheduler = get_scheduler()
            return scheduler.submit(
                func,
                args=args,
                kwargs=kwargs,
                queue=queue,
                priority=priority,
                name=func.__name__,
                timeout=timeout,
                max_retries=max_retries,
            )

        def apply_async(args=(), kwargs=None, **options) -> str:
            scheduler = get_scheduler()
            return scheduler.submit(
                func,
                args=args,
                kwargs=kwargs or {},
                queue=options.get("queue", queue),
                priority=options.get("priority", priority),
                name=func.__name__,
                timeout=options.get("timeout", timeout),
                countdown=options.get("countdown", 0),
                max_retries=options.get("max_retries", max_retries),
            )

        func.delay = delay
        func.apply_async = apply_async
        func.queue = queue
        func.priority = priority
        return func

    return decorator


# ============================================================================
# 命令行测试
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("  分布式任务调度器测试")
    print("=" * 70)

    scheduler = DistributedScheduler(default_queues=["default", "render", "analyze"])
    scheduler.start()

    print("\n1. 添加 Workers...")
    worker1 = scheduler.add_worker(queues=["default", "render"], concurrency=2)
    worker2 = scheduler.add_worker(queues=["default", "analyze"], concurrency=1)
    print(f"  Worker 1: {worker1.worker_id} (并发: {worker1.concurrency})")
    print(f"  Worker 2: {worker2.worker_id} (并发: {worker2.concurrency})")

    print("\n2. 提交任务...")

    def sample_task(idx: int, delay: float = 0.2) -> str:
        time.sleep(delay)
        return f"任务 {idx} 完成"

    def render_task(name: str) -> str:
        time.sleep(0.3)
        return f"渲染完成: {name}"

    task_ids = []
    for i in range(5):
        tid = scheduler.submit(
            sample_task,
            args=(i,),
            kwargs={"delay": 0.1 + i * 0.05},
            queue="default",
            priority=5 + i,
            name=f"任务-{i}",
        )
        task_ids.append(tid)

    render_id = scheduler.submit(
        render_task,
        args=("测试视频",),
        queue="render",
        priority=8,
        name="渲染任务",
    )

    print(f"  提交了 {len(task_ids)} 个普通任务 + 1 个渲染任务")

    print("\n3. 等待任务完成...")
    time.sleep(3)

    print("\n4. 查询结果...")
    for tid in task_ids[:3]:
        result = scheduler.get_result(tid)
        if result:
            print(f"  {result['name']}: {result['state']} -> {result.get('result', 'N/A')}")

    render_result = scheduler.get_result(render_id)
    if render_result:
        print(f"  渲染任务: {render_result['state']} -> {render_result.get('result', 'N/A')}")

    print("\n5. 定时任务...")
    cron_count = [0]
    def periodic_task():
        cron_count[0] += 1
        return f"定时执行 #{cron_count[0]}"

    scheduler.add_cron_schedule(
        "heartbeat",
        periodic_task,
        interval=1.0,
        queue="default",
    )
    time.sleep(3.5)

    schedules = scheduler.get_cron_schedules()
    for s in schedules:
        print(f"  {s['name']}: 执行 {s['run_count']} 次, 间隔 {s['interval']}s")

    print("\n6. 统计信息...")
    stats = scheduler.get_stats()
    print(f"  队列: {stats['queues']}")
    print(f"  待执行: {stats['total_queued']}")
    print(f"  Workers: {stats['workers']['online']} 在线 / {stats['workers']['total']} 总计")
    print(f"  已完成: {stats['total_completed']}")
    print(f"  失败: {stats['total_failed']}")
    print(f"  结果存储: {stats['results_stored']}")

    print("\n7. 任务装饰器测试...")

    @task(queue="default", priority=7)
    def decorated_task(x: int, y: int) -> int:
        return x + y

    sync_result = decorated_task(3, 4)
    print(f"  同步调用: 3 + 4 = {sync_result}")

    async_id = decorated_task.delay(10, 20)
    print(f"  异步提交: task_id = {async_id}")

    async_result = scheduler.wait_for_result(async_id, timeout=5)
    if async_result:
        print(f"  异步结果: {async_result.get('result')}")

    print("\n8. Worker 信息...")
    for w in scheduler.get_workers():
        print(f"  {w['worker_id']}: 在线={w['is_online']}, 完成={w['total_completed']}, 失败={w['total_failed']}")

    print("\n" + "=" * 70)
    print("  测试完成！")
    print("=" * 70)

    scheduler.stop()
