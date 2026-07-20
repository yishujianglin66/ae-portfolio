"""
software_sdk/base.py - 软件适配器抽象基类

定义所有软件适配器的统一接口。
从 multi_software_bridge.py 提取 BaseSoftwareAdapter。
"""
from __future__ import annotations

import logging
import threading
from abc import ABC, abstractmethod
from typing import Any, Optional

from software_sdk.types import (
    ConnectionStatus,
    SoftwareCapabilities,
    SoftwareConfig,
    SoftwareStatus,
    SoftwareType,
    Task,
)


class BaseSoftwareAdapter(ABC):
    """软件适配器基类 - 定义所有软件适配器的统一接口。

    所有软件适配器必须实现:
    - connect(): 建立连接
    - disconnect(): 断开连接
    - health_check(): 健康检查
    - execute_task(): 执行任务
    - _initialize_capabilities(): 初始化能力列表
    """

    def __init__(
        self,
        config: SoftwareConfig,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.config = config
        self.software_type: SoftwareType = config.software
        self._status: ConnectionStatus = ConnectionStatus.DISCONNECTED
        self._capabilities: SoftwareCapabilities = self._initialize_capabilities()
        self._active_tasks: int = 0
        self._lock = threading.Lock()
        self._last_error: Optional[str] = None
        self.logger = logger or logging.getLogger(
            f"software_sdk.{self.software_type.value}"
        )

    @abstractmethod
    def _initialize_capabilities(self) -> SoftwareCapabilities:
        """初始化软件能力列表"""
        ...

    @abstractmethod
    def connect(self) -> bool:
        """建立与软件的连接"""
        ...

    @abstractmethod
    def disconnect(self) -> bool:
        """断开与软件的连接"""
        ...

    @abstractmethod
    def health_check(self) -> bool:
        """检查软件健康状态"""
        ...

    @abstractmethod
    def execute_task(self, task: Task) -> Any:
        """执行任务 - 子类必须实现"""
        ...

    def get_capabilities(self) -> SoftwareCapabilities:
        """获取软件能力"""
        return self._capabilities

    def get_status(self) -> SoftwareStatus:
        """获取软件状态"""
        from datetime import datetime
        return SoftwareStatus(
            software=self.software_type,
            status=self._status,
            version=self.config.version,
            last_heartbeat=datetime.now(),
            error_message=self._last_error,
            active_tasks=self._active_tasks,
            max_tasks=self.config.max_concurrent_tasks,
        )

    def can_accept_task(self) -> bool:
        """检查是否可以接受新任务"""
        with self._lock:
            return (
                self._status == ConnectionStatus.CONNECTED
                and self._active_tasks < self.config.max_concurrent_tasks
            )

    def _mark_task_start(self) -> None:
        with self._lock:
            self._active_tasks += 1

    def _mark_task_end(self) -> None:
        with self._lock:
            self._active_tasks = max(0, self._active_tasks - 1)

    def _set_error(self, error_msg: str) -> None:
        self._last_error = error_msg
        self._status = ConnectionStatus.ERROR
        self.logger.error(f"{self.software_type.value} error: {error_msg}")

    def _set_connected(self) -> None:
        self._status = ConnectionStatus.CONNECTED
        self._last_error = None
