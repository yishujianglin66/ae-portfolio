#!/usr/bin/env python3
"""
通用重试与进度回调工具
======================

提供可复用的重试装饰器、指数退避策略和进度回调上下文管理器。

Usage:
    from core.retry_utils import retry_with_backoff, ProgressCallback

    # 重试装饰器
    @retry_with_backoff(max_retries=3, base_delay=3.0, backoff_factor=2.0)
    def my_function():
        ...

    # 进度回调上下文管理器
    with ProgressCallback(callback, total_steps=5) as progress:
        progress.step("Starting...")
        progress.step("Processing...")
"""

from __future__ import annotations

import asyncio
import functools
import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class RetryConfig:
    """重试配置"""

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_factor: float = 2.0
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)
    on_retry: Optional[Callable[[int, Exception, float], None]] = None


@dataclass
class RetryResult:
    """重试结果"""

    success: bool = False
    attempts: int = 0
    total_delay: float = 0.0
    last_error: Optional[Exception] = None
    errors: List[str] = field(default_factory=list)


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[int, Exception, float], None]] = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """重试装饰器（指数退避）

    Args:
        max_retries: 最大重试次数
        base_delay: 初始延迟秒数
        max_delay: 最大延迟秒数
        backoff_factor: 退避因子（每次重试延迟乘以此值）
        retryable_exceptions: 可重试的异常类型
        on_retry: 重试时的回调函数 (attempt, exception, delay)

    Returns:
        装饰后的函数

    Example:
        @retry_with_backoff(max_retries=3, base_delay=2.0)
        def call_api():
            ...
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs) -> T:
                delay = base_delay
                last_exception: Optional[Exception] = None

                for attempt in range(1 + max_retries):
                    try:
                        return await func(*args, **kwargs)
                    except retryable_exceptions as e:
                        last_exception = e
                        if attempt < max_retries:
                            actual_delay = min(delay, max_delay)
                            if on_retry:
                                on_retry(attempt, e, actual_delay)
                            logger.warning(
                                f"Retry {attempt + 1}/{max_retries + 1} for {func.__name__} "
                                f"after {actual_delay:.1f}s: {e}"
                            )
                            await asyncio.sleep(actual_delay)
                            delay *= backoff_factor
                        else:
                            raise

                # 不应该到达这里，但为了类型安全
                if last_exception:
                    raise last_exception
                raise RuntimeError("Unexpected retry state")

            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs) -> T:
                delay = base_delay
                last_exception: Optional[Exception] = None

                for attempt in range(1 + max_retries):
                    try:
                        return func(*args, **kwargs)
                    except retryable_exceptions as e:
                        last_exception = e
                        if attempt < max_retries:
                            actual_delay = min(delay, max_delay)
                            if on_retry:
                                on_retry(attempt, e, actual_delay)
                            logger.warning(
                                f"Retry {attempt + 1}/{max_retries + 1} for {func.__name__} "
                                f"after {actual_delay:.1f}s: {e}"
                            )
                            time.sleep(actual_delay)
                            delay *= backoff_factor
                        else:
                            raise

                # 不应该到达这里，但为了类型安全
                if last_exception:
                    raise last_exception
                raise RuntimeError("Unexpected retry state")

            return sync_wrapper

    return decorator


def call_with_retry(
    func: Callable[..., T],
    args: tuple = (),
    kwargs: Optional[Dict[str, Any]] = None,
    config: Optional[RetryConfig] = None,
    **retry_kwargs,
) -> RetryResult:
    """使用重试调用函数（非装饰器模式）

    Args:
        func: 要调用的函数
        args: 位置参数
        kwargs: 关键字参数
        config: RetryConfig 实例
        **retry_kwargs: 直接传入的 retry 参数

    Returns:
        RetryResult 包含调用结果和重试信息
    """
    if kwargs is None:
        kwargs = {}

    cfg = config or RetryConfig(**retry_kwargs)
    result = RetryResult()
    delay = cfg.base_delay

    for attempt in range(1 + cfg.max_retries):
        result.attempts = attempt + 1
        try:
            func(*args, **kwargs)
            result.success = True
            return result
        except cfg.retryable_exceptions as e:
            result.last_error = e
            result.errors.append(f"{type(e).__name__}: {e}")

            if attempt < cfg.max_retries:
                actual_delay = min(delay, cfg.max_delay)
                if cfg.on_retry:
                    cfg.on_retry(attempt, e, actual_delay)
                time.sleep(actual_delay)
                result.total_delay += actual_delay
                delay *= cfg.backoff_factor

    return result


class ProgressCallback:
    """进度回调上下文管理器

    用于简化进度报告代码，支持步骤计数和自动完成。

    Example:
        def my_callback(progress: float, msg: str):
            print(f"{progress*100:.0f}%: {msg}")

        with ProgressCallback(my_callback, total_steps=5) as progress:
            progress.step("Starting...")      # 0.2
            progress.step("Processing...")    # 0.4
            progress.step("Finishing...")     # 0.6
            progress.step("Done")             # 0.8
            # 自动调用 progress.update(1.0, "Complete")
    """

    def __init__(
        self,
        callback: Optional[Callable[[float, str], None]],
        total_steps: int = 1,
        start_msg: str = "",
        complete_msg: str = "Complete",
    ):
        """初始化进度回调

        Args:
            callback: 进度回调函数 (progress, message)
            total_steps: 总步骤数
            start_msg: 起始消息
            complete_msg: 完成消息
        """
        self._callback = callback
        self._total_steps = total_steps
        self._complete_msg = complete_msg
        self._current_step = 0
        self._base_progress: float = 0.0

        if callback and start_msg:
            callback(0.0, start_msg)

    def __enter__(self) -> "ProgressCallback":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._callback:
            if exc_type is None:
                self._callback(1.0, self._complete_msg)
            else:
                self._callback(1.0, f"Failed: {exc_val}")

    def step(self, msg: str = "") -> float:
        """前进一步并报告进度

        Args:
            msg: 进度消息

        Returns:
            当前进度 (0.0-1.0)
        """
        self._current_step += 1
        progress = self._current_step / self._total_steps
        if self._callback:
            self._callback(progress, msg)
        return progress

    def update(self, progress: float, msg: str = "") -> float:
        """直接更新进度

        Args:
            progress: 进度值 (0.0-1.0)
            msg: 进度消息

        Returns:
            当前进度
        """
        if self._callback:
            self._callback(progress, msg)
        return progress

    def subprogress(self, msg: str, start: float, end: float) -> "SubProgressReporter":
        """创建子进度报告器

        Args:
            msg: 子进度消息前缀
            start: 子进度起始值 (0.0-1.0)
            end: 子进度结束值 (0.0-1.0)

        Returns:
            SubProgressReporter 子进度报告器
        """
        return SubProgressReporter(self, msg, start, end)


class SubProgressReporter:
    """子进度报告器

    用于报告大步骤内的子进度。

    Example:
        with progress.subprogress("Processing items", 0.2, 0.8) as sub:
            for i, item in enumerate(items):
                sub.update(i / len(items), f"Processing item {i}")
    """

    def __init__(
        self,
        parent: ProgressCallback,
        msg_prefix: str,
        start: float,
        end: float,
    ):
        self._parent = parent
        self._msg_prefix = msg_prefix
        self._start = start
        self._end = end
        self._range = end - start

    def __enter__(self) -> "SubProgressReporter":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is None:
            self.update(1.0, "Done")

    def update(self, sub_progress: float, msg: str = "") -> float:
        """更新子进度

        Args:
            sub_progress: 子进度 (0.0-1.0)
            msg: 子进度消息

        Returns:
            映射到父进度的进度值
        """
        actual_progress = self._start + self._range * sub_progress
        full_msg = f"{self._msg_prefix}: {msg}" if msg else self._msg_prefix
        self._parent.update(actual_progress, full_msg)
        return actual_progress


@contextmanager
def progress_context(
    callback: Optional[Callable[[float, str], None]],
    start_msg: str = "",
    complete_msg: str = "Complete",
):
    """简单的进度上下文管理器

    Args:
        callback: 进度回调函数
        start_msg: 起始消息
        complete_msg: 完成消息

    Yields:
        更新进度的函数 (progress, message)
    """
    if callback and start_msg:
        callback(0.0, start_msg)

    def update(progress: float, msg: str = ""):
        if callback:
            callback(progress, msg)

    try:
        yield update
    finally:
        if callback:
            callback(1.0, complete_msg)


def exponential_backoff(
    attempt: int,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
) -> float:
    """计算指数退避延迟

    Args:
        attempt: 当前尝试次数（从 0 开始）
        base_delay: 基础延迟秒数
        max_delay: 最大延迟秒数
        backoff_factor: 退避因子

    Returns:
        计算后的延迟秒数
    """
    delay = base_delay * (backoff_factor**attempt)
    return min(delay, max_delay)