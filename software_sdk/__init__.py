"""
software_sdk - 统一软件适配器 SDK

提供插件式多软件适配器架构，支持软件注册、发现、连接和任务执行。

用法：
    from software_sdk import SoftwareRegistry, SoftwareConfig, SoftwareType

    registry = SoftwareRegistry()
    registry.register(SoftwareType.AFTER_EFFECTS, ae_adapter)
    adapter = registry.get(SoftwareType.AFTER_EFFECTS)
"""
from software_sdk.base import BaseSoftwareAdapter
from software_sdk.registry import SoftwareRegistry
from software_sdk.types import (
    ConnectionStatus,
    FallbackStrategyType,
    SoftwareCapabilities,
    SoftwareCapability,
    SoftwareConfig,
    SoftwareStatus,
    SoftwareType,
    Task,
    TaskPriority,
    TaskStatus,
)

__all__ = [
    "SoftwareType",
    "ConnectionStatus",
    "TaskStatus",
    "TaskPriority",
    "SoftwareCapability",
    "FallbackStrategyType",
    "SoftwareStatus",
    "SoftwareCapabilities",
    "Task",
    "SoftwareConfig",
    "BaseSoftwareAdapter",
    "SoftwareRegistry",
]
