# -*- coding: utf-8 -*-
"""ae.archive.bridge_middleware — 08-29 事故最小重建（透传语义）。"""
from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class MiddlewarePipeline:
    """中间件管道：顺序执行 process_command 钩子，透传语义。"""

    def __init__(self) -> None:
        self._middlewares: List[Any] = []

    def add(self, middleware: Any) -> None:
        self._middlewares.append(middleware)

    def process_command(self, command: Any, handler: Optional[Callable] = None,
                        **kwargs: Any) -> Any:
        for mw in self._middlewares:
            hook = getattr(mw, "process_command", None)
            if hook is not None:
                result = hook(command, **kwargs)
                if result is not None:
                    command = result
        if handler is not None:
            return handler(command)
        return command


class LoggingMiddleware:
    def process_command(self, command: Any, **kwargs: Any) -> Any:
        logger.debug("bridge command: %s", getattr(command, "action", command))
        return None


class MetricsMiddleware:
    def __init__(self) -> None:
        self.count = 0
        self.errors = 0

    def process_command(self, command: Any, **kwargs: Any) -> Any:
        self.count += 1
        return None

    def get_metrics(self) -> Dict[str, int]:
        return {"count": self.count, "errors": self.errors}


class RateLimitMiddleware:
    def __init__(self, max_requests: int = 100, window_seconds: int = 60,
                 **kwargs: Any) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._timestamps: List[float] = []

    def process_command(self, command: Any, **kwargs: Any) -> Any:
        now = time.time()
        cutoff = now - self.window_seconds
        self._timestamps = [t for t in self._timestamps if t > cutoff]
        self._timestamps.append(now)
        return None


class ValidationMiddleware:
    def process_command(self, command: Any, **kwargs: Any) -> Any:
        return None


class RetryMiddleware:
    def __init__(self, max_retries: int = 2, base_delay_ms: float = 100,
                 max_delay_ms: float = 3000, **kwargs: Any) -> None:
        self.max_retries = max_retries
        self.base_delay_ms = base_delay_ms
        self.max_delay_ms = max_delay_ms

    def process_command(self, command: Any, **kwargs: Any) -> Any:
        return None
