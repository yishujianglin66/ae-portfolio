#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批处理队列系统
=============

提供异步任务队列、进度跟踪和批量处理能力。

功能:
- FIFO 任务队列，支持优先级
- 并发控制（最大并发数）
- 进度跟踪与回调
- 任务状态管理（pending/running/completed/failed/cancelled）
- 重试机制（失败自动重试）
- 批量任务提交与结果汇总
- 任务持久化（可选）

任务状态流转:
  pending → running → completed
              ↘ failed → (retry → pending) → ...
              ↘ cancelled
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple


# ============================================================================
# 任务状态枚举
# ============================================================================

class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"       # 等待中
    RUNNING = "running"       # 执行中
    COMPLETED = "completed"   # 已完成
    FAILED = "failed"         # 失败
    CANCELLED = "cancelled"   # 已取消


# ============================================================================
# 任务数据类
# ============================================================================

@dataclass
class Task:
    """任务对象"""
    task_id: str
    name: str
    func: Callable[..., Any]
    args: Tuple[Any, ...] = ()
    kwargs: Dict[str, Any] = field(default_factory=dict)
    priority: int = 5  # 1-10，越高优先级越高
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    retries: int = 0
    max_retries: int = 0
    progress: float = 0.0  # 0.0 - 1.0
    progress_message: str = ""
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    duration: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    on_complete: Optional[Callable[["Task"], None]] = None
    on_failure: Optional[Callable[["Task"], None]] = None
    on_progress: Optional[Callable[["Task", float, str], None]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "priority": self.priority,
            "status": self.status.value,
            "progress": self.progress,
            "progress_message": self.progress_message,
            "retries": self.retries,
            "max_retries": self.max_retries,
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration": self.duration,
            "metadata": self.metadata,
        }


# ============================================================================
# 进度回调上下文
# ============================================================================

class ProgressContext:
    """任务进度回调上下文，在任务函数内部更新进度"""

    def __init__(self, task: Task):
        self._task = task
        self._cancelled = False

    def update(self, progress: float, message: str = ""):
        """更新进度

        Args:
            progress: 进度 (0.0 - 1.0)
            message: 进度消息
        """
        if self._cancelled:
            return
        self._task.progress = max(0.0, min(1.0, progress))
        self._task.progress_message = message
        if self._task.on_progress:
            try:
                self._task.on_progress(self._task, self._task.progress, message)
            except Exception:
                pass

    def check_cancel(self) -> bool:
        """检查是否被取消"""
        return self._task.status == TaskStatus.CANCELLED

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled or self._task.status == TaskStatus.CANCELLED


# ============================================================================
# 批处理队列
# ============================================================================

class BatchQueue:
    """批处理队列系统

    支持:
    - 多线程并发执行
    - 优先级调度
    - 任务重试
    - 进度跟踪
    - 批量提交/等待
    """

    def __init__(
        self,
        max_workers: int = 3,
        max_retries: int = 0,
        retry_delay: float = 1.0,
    ):
        """
        Args:
            max_workers: 最大并发工作线程数
            max_retries: 默认最大重试次数
            retry_delay: 重试延迟（秒）
        """
        self._max_workers = max_workers
        self._max_retries = max_retries
        self._retry_delay = retry_delay

        self._tasks: Dict[str, Task] = {}
        self._pending: List[Task] = []
        self._running: List[Task] = []
        self._lock = threading.RLock()

        self._stop_event = threading.Event()
        self._workers: List[threading.Thread] = []
        self._started = False

        # 统计
        self._total_submitted = 0
        self._total_completed = 0
        self._total_failed = 0

    # --------------------------------------------------------------------
    # 生命周期管理
    # --------------------------------------------------------------------

    def start(self):
        """启动工作线程"""
        with self._lock:
            if self._started:
                return
            self._started = True
            self._stop_event.clear()
            for i in range(self._max_workers):
                t = threading.Thread(
                    target=self._worker_loop,
                    name=f"BatchWorker-{i}",
                    daemon=True,
                )
                t.start()
                self._workers.append(t)

    def stop(self, wait: bool = True):
        """停止队列

        Args:
            wait: 是否等待正在运行的任务完成
        """
        with self._lock:
            if not self._started:
                return
            self._stop_event.set()
            self._started = False

        if wait:
            for t in self._workers:
                t.join(timeout=30)
        self._workers = []

    def shutdown(self, wait: bool = True):
        """关闭队列（同 stop）"""
        self.stop(wait=wait)

    # --------------------------------------------------------------------
    # 任务提交
    # --------------------------------------------------------------------

    def submit(
        self,
        func: Callable[..., Any],
        *args,
        name: Optional[str] = None,
        priority: int = 5,
        max_retries: Optional[int] = None,
        on_complete: Optional[Callable[[Task], None]] = None,
        on_failure: Optional[Callable[[Task], None]] = None,
        on_progress: Optional[Callable[[Task, float, str], None]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Task:
        """提交单个任务

        Args:
            func: 要执行的函数
            *args: 位置参数
            name: 任务名称
            priority: 优先级 (1-10)
            max_retries: 最大重试次数（None则使用队列默认值）
            on_complete: 完成回调
            on_failure: 失败回调
            on_progress: 进度回调 fn(task, progress, message)
            metadata: 元数据
            **kwargs: 关键字参数

        Returns:
            Task 对象
        """
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        task = Task(
            task_id=task_id,
            name=name or func.__name__,
            func=func,
            args=args,
            kwargs=kwargs,
            priority=max(1, min(10, priority)),
            max_retries=max_retries if max_retries is not None else self._max_retries,
            on_complete=on_complete,
            on_failure=on_failure,
            on_progress=on_progress,
            metadata=metadata or {},
        )

        with self._lock:
            self._tasks[task_id] = task
            self._pending.append(task)
            # 按优先级排序（高优先级在前）
            self._pending.sort(key=lambda t: -t.priority)
            self._total_submitted += 1

        # 确保工作线程已启动
        self.start()

        return task

    def submit_batch(
        self,
        tasks: List[Tuple[Callable, Tuple, Dict]],
        batch_name: str = "batch",
        priority: int = 5,
        on_batch_complete: Optional[Callable[[List[Task]], None]] = None,
    ) -> List[Task]:
        """批量提交任务

        Args:
            tasks: 任务列表 [(func, args_tuple, kwargs_dict), ...]
        """
        results = []
        for func, args, kwargs in tasks:
            task = self.submit(
                func,
                *args,
                name=f"{batch_name}-{len(results)}",
                priority=priority,
                **kwargs,
            )
            results.append(task)

        # 批量完成回调
        if on_batch_complete:
            batch_ids = [t.task_id for t in results]
            remaining = len(batch_ids)
            lock = threading.Lock()

            def check_all_done(task: Task):
                nonlocal remaining
                with lock:
                    remaining -= 1
                    if remaining <= 0:
                        try:
                            on_batch_complete(results)
                        except Exception:
                            pass

            for t in results:
                old_complete = t.on_complete

                def combined(task=task, old=old_complete):
                    if old:
                        old(task)
                    check_all_done(task)

                t.on_complete = combined

        return results

    # --------------------------------------------------------------------
    # 任务查询
    # --------------------------------------------------------------------

    def get_task(self, task_id: str) -> Optional[Task]:
        """根据ID获取任务"""
        with self._lock:
            return self._tasks.get(task_id)

    def get_all_tasks(self) -> List[Task]:
        """获取所有任务"""
        with self._lock:
            return list(self._tasks.values())

    def get_tasks_by_status(self, status: TaskStatus) -> List[Task]:
        """根据状态获取任务列表"""
        with self._lock:
            return [t for t in self._tasks.values() if t.status == status]

    @property
    def pending_count(self) -> int:
        with self._lock:
            return len(self._pending)

    @property
    def running_count(self) -> int:
        with self._lock:
            return len(self._running)

    @property
    def completed_count(self) -> int:
        return self._total_completed

    @property
    def failed_count(self) -> int:
        return self._total_failed

    def get_stats(self) -> Dict[str, Any]:
        """获取队列统计信息"""
        with self._lock:
            return {
                "total_submitted": self._total_submitted,
                "total_completed": self._total_completed,
                "total_failed": self._total_failed,
                "pending": len(self._pending),
                "running": len(self._running),
                "max_workers": self._max_workers,
            }

    # --------------------------------------------------------------------
    # 任务控制
    # --------------------------------------------------------------------

    def cancel_task(self, task_id: str) -> bool:
        """取消任务

        Returns:
            是否成功取消
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                return False
            if task.status == TaskStatus.PENDING:
                # 从待执行列表移除
                self._pending = [t for t in self._pending if t.task_id != task_id]
                task.status = TaskStatus.CANCELLED
                return True
            # 正在运行的任务，设置取消标记（任务需要自行检查）
            task.status = TaskStatus.CANCELLED
            return True

    def wait_for_task(self, task_id: str, timeout: Optional[float] = None) -> Task:
        """等待任务完成

        Args:
            task_id: 任务ID
            timeout: 超时时间（秒），None表示无限等待

        Returns:
            Task 对象
        """
        start = time.time()
        while True:
            with self._lock:
                task = self._tasks.get(task_id)
                if not task:
                    raise ValueError(f"任务不存在: {task_id}")
                if task.status in (
                    TaskStatus.COMPLETED,
                    TaskStatus.FAILED,
                    TaskStatus.CANCELLED,
                ):
                    return task
            if timeout is not None and time.time() - start > timeout:
                return task
            time.sleep(0.1)

    def wait_all(self, timeout: Optional[float] = None) -> bool:
        """等待所有任务完成

        Returns:
            是否所有任务都完成
        """
        start = time.time()
        while True:
            with self._lock:
                if not self._pending and not self._running:
                    return True
            if timeout is not None and time.time() - start > timeout:
                return False
            time.sleep(0.1)

    # --------------------------------------------------------------------
    # 工作线程
    # --------------------------------------------------------------------

    def _worker_loop(self):
        """工作线程主循环"""
        while not self._stop_event.is_set():
            task = self._pick_next_task()
            if task is None:
                # 没有任务，等待一下
                time.sleep(0.1)
                continue

            self._execute_task(task)

    def _pick_next_task(self) -> Optional[Task]:
        """取下一个待执行任务"""
        with self._lock:
            if not self._pending:
                return None
            # 按优先级排序，取最高的
            task = self._pending.pop(0)
            if task.status != TaskStatus.PENDING:
                # 已被取消或其他状态，跳过
                return None
            task.status = TaskStatus.RUNNING
            task.started_at = time.time()
            self._running.append(task)
            return task

    def _execute_task(self, task: Task):
        """执行任务"""
        try:
            # 创建进度上下文
            ctx = ProgressContext(task)

            # 函数第一个参数如果是 ProgressContext，则传入
            import inspect
            sig = inspect.signature(task.func)
            params = list(sig.parameters.keys())

            if params and params[0] in ("progress", "ctx", "progress_ctx"):
                result = task.func(ctx, *task.args, **task.kwargs)
            else:
                result = task.func(*task.args, **task.kwargs)

            task.result = result
            task.status = TaskStatus.COMPLETED
            task.progress = 1.0
            task.progress_message = "已完成"

        except Exception as e:
            task.error = str(e)
            task.retries += 1

            if task.retries <= task.max_retries:
                task.status = TaskStatus.PENDING
                task.progress = 0.0
                task.progress_message = f"重试中 ({task.retries}/{task.max_retries})"

                with self._lock:
                    self._running = [t for t in self._running if t.task_id != task.task_id]

                time.sleep(self._retry_delay)

                with self._lock:
                    self._pending.append(task)
                    self._pending.sort(key=lambda t: -t.priority)
                return
            else:
                task.status = TaskStatus.FAILED
                if task.on_failure:
                    try:
                        task.on_failure(task)
                    except Exception:
                        pass

        finally:
            task.completed_at = time.time()
            if task.started_at:
                task.duration = task.completed_at - task.started_at

            # 从 running 移除
            with self._lock:
                self._running = [
                    t for t in self._running if t.task_id != task.task_id
                ]
                if task.status == TaskStatus.COMPLETED:
                    self._total_completed += 1
                    if task.on_complete:
                        try:
                            task.on_complete(task)
                        except Exception:
                            pass
                elif task.status == TaskStatus.FAILED:
                    self._total_failed += 1


# ============================================================================
# 批量处理结果汇总
# ============================================================================

@dataclass
class BatchResult:
    """批量处理结果"""
    tasks: List[Task] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.tasks)

    @property
    def completed(self) -> int:
        return sum(1 for t in self.tasks if t.status == TaskStatus.COMPLETED)

    @property
    def failed(self) -> int:
        return sum(1 for t in self.tasks if t.status == TaskStatus.FAILED)

    @property
    def cancelled(self) -> int:
        return sum(1 for t in self.tasks if t.status == TaskStatus.CANCELLED)

    @property
    def success_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return self.completed / self.total

    @property
    def results(self) -> List[Any]:
        return [t.result for t in self.tasks if t.status == TaskStatus.COMPLETED]

    @property
    def errors(self) -> List[Tuple[str, str]]:
        return [(t.name, t.error or "") for t in self.tasks if t.status == TaskStatus.FAILED]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total": self.total,
            "completed": self.completed,
            "failed": self.failed,
            "cancelled": self.cancelled,
            "success_rate": round(self.success_rate * 100, 2),
            "total_duration": sum(t.duration for t in self.tasks),
            "tasks": [t.to_dict() for t in self.tasks],
        }


# ============================================================================
# 模块单例
# ============================================================================

_default_queue: Optional[BatchQueue] = None


def get_default_queue(max_workers: int = 3) -> BatchQueue:
    """获取默认队列实例"""
    global _default_queue
    if _default_queue is None:
        _default_queue = BatchQueue(max_workers=max_workers)
        _default_queue.start()
    return _default_queue


# ============================================================================
# 便捷函数：示例任务函数
# ============================================================================

def example_task(progress: ProgressContext, total_steps: int = 10, delay: float = 0.1) -> str:
    """示例任务：模拟带进度的任务"""
    for i in range(total_steps):
        if progress.check_cancel():
            return "已取消"
        progress.update(
            (i + 1) / total_steps,
            f"处理中 {i + 1}/{total_steps}"
        )
        time.sleep(delay)
    return "完成"


# ============================================================================
# 命令行测试入口
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("批处理队列系统测试")
    print("=" * 60)

    queue = BatchQueue(max_workers=2, max_retries=1)
    queue.start()

    # 提交测试任务
    print("\n提交 5 个测试任务...")
    tasks = []
    for i in range(5):
        task = queue.submit(
            example_task,
            total_steps=5,
            delay=0.2,
            name=f"测试任务-{i}",
            priority=5 + i % 3,
            on_progress=lambda t, p, m: print(f"  [{t.name}] {int(p*100)}% {m}"),
        )
        tasks.append(task)

    # 等待完成
    print("\n等待所有任务完成...")
    queue.wait_all()

    # 输出结果
    print("\n" + "=" * 60)
    print("执行结果")
    print("=" * 60)
    stats = queue.get_stats()
    print(f"总提交: {stats['total_submitted']}")
    print(f"已完成: {stats['total_completed']}")
    print(f"失败: {stats['total_failed']}")
    print(f"成功率: {stats['total_completed']/stats['total_submitted']*100:.1f}%" if stats['total_submitted'] > 0 else "0%")

    for task in tasks:
        print(f"\n  {task.name}: {task.status.value} ({task.duration:.2f}s)")
        if task.result:
            print(f"    结果: {task.result}")
        if task.error:
            print(f"    错误: {task.error}")

    queue.stop()
    print("\n测试完成！")
