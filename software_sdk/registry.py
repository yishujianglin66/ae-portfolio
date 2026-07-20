"""
software_sdk/registry.py - 软件注册中心

插件式软件适配器注册与发现机制。

用法：
    registry = SoftwareRegistry()
    registry.register(SoftwareType.AFTER_EFFECTS, ae_adapter)
    adapter = registry.get(SoftwareType.AFTER_EFFECTS)
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

from software_sdk.types import (
    ConnectionStatus,
    SoftwareCapability,
    SoftwareType,
)
from software_sdk.base import BaseSoftwareAdapter


class SoftwareRegistry:
    """软件注册中心 - 管理所有软件适配器的注册、发现和生命周期。

    支持：
    - 注册/注销适配器
    - 按软件类型查找
    - 按能力查找
    - 批量连接/断开
    """

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        self._adapters: Dict[SoftwareType, BaseSoftwareAdapter] = {}
        self.logger = logger or logging.getLogger("software_sdk.registry")

    def register(
        self,
        software_type: SoftwareType,
        adapter: BaseSoftwareAdapter,
    ) -> None:
        """注册软件适配器。

        Args:
            software_type: 软件类型
            adapter: 适配器实例

        Raises:
            ValueError: 如果该软件类型已注册
        """
        if software_type in self._adapters:
            raise ValueError(
                f"Software type '{software_type.value}' is already registered. "
                f"Unregister it first."
            )
        self._adapters[software_type] = adapter
        self.logger.info(f"Registered adapter: {software_type.value}")

    def unregister(self, software_type: SoftwareType) -> None:
        """注销软件适配器。

        Args:
            software_type: 软件类型
        """
        if software_type in self._adapters:
            del self._adapters[software_type]
            self.logger.info(f"Unregistered adapter: {software_type.value}")

    def get(self, software_type: SoftwareType) -> Optional[BaseSoftwareAdapter]:
        """获取软件适配器。

        Args:
            software_type: 软件类型

        Returns:
            适配器实例，未注册则返回 None
        """
        return self._adapters.get(software_type)

    def has(self, software_type: SoftwareType) -> bool:
        """检查软件是否已注册。

        Args:
            software_type: 软件类型

        Returns:
            是否已注册
        """
        return software_type in self._adapters

    def list_available(self) -> List[SoftwareType]:
        """列出所有已注册的软件类型。

        Returns:
            软件类型列表
        """
        return list(self._adapters.keys())

    def get_by_capability(
        self,
        capability: SoftwareCapability,
    ) -> List[BaseSoftwareAdapter]:
        """按能力查找适配器。

        Args:
            capability: 软件能力

        Returns:
            具有该能力的适配器列表
        """
        result: List[BaseSoftwareAdapter] = []
        for adapter in self._adapters.values():
            caps = adapter.get_capabilities()
            if caps.has_capability(capability):
                result.append(adapter)
        return result

    def connect_all(self) -> Dict[SoftwareType, bool]:
        """连接所有已注册的软件。

        Returns:
            软件类型 -> 连接结果
        """
        results: Dict[SoftwareType, bool] = {}
        for sw_type, adapter in self._adapters.items():
            try:
                results[sw_type] = adapter.connect()
            except Exception as e:
                self.logger.error(f"Failed to connect {sw_type.value}: {e}")
                results[sw_type] = False
        return results

    def disconnect_all(self) -> Dict[SoftwareType, bool]:
        """断开所有已注册的软件。

        Returns:
            软件类型 -> 断开结果
        """
        results: Dict[SoftwareType, bool] = {}
        for sw_type, adapter in self._adapters.items():
            try:
                results[sw_type] = adapter.disconnect()
            except Exception as e:
                self.logger.error(f"Failed to disconnect {sw_type.value}: {e}")
                results[sw_type] = False
        return results

    def get_connected(self) -> List[BaseSoftwareAdapter]:
        """获取所有已连接的适配器。

        Returns:
            已连接的适配器列表
        """
        return [
            adapter for adapter in self._adapters.values()
            if adapter.get_status().status == ConnectionStatus.CONNECTED
        ]

    def get_available_for_task(self) -> List[SoftwareType]:
        """获取可以接受任务的软件列表。

        Returns:
            可以接受任务的软件类型列表
        """
        return [
            sw_type for sw_type, adapter in self._adapters.items()
            if adapter.can_accept_task()
        ]
