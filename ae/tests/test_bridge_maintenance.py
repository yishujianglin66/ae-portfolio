"""Bridge Maintenance 单元测试。"""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ae.bridge_maintenance import (
    BridgeMaintenanceService,
    DeadLetterRetryService,
    DiskCleaner,
    DiskCleanerConfig,
)


class TestDiskCleaner:
    """磁盘清理器测试。"""

    def test_initialization(self, tmp_path: Path) -> None:
        """初始化磁盘清理器。"""
        config = DiskCleanerConfig(bridge_dir=str(tmp_path))
        cleaner = DiskCleaner(config)
        assert cleaner._bridge_path == tmp_path

    @pytest.mark.asyncio
    async def test_start_and_stop(self, tmp_path: Path) -> None:
        """启动和停止磁盘清理器。"""
        config = DiskCleanerConfig(bridge_dir=str(tmp_path))
        cleaner = DiskCleaner(config)
        
        cleaner.start()
        assert cleaner._running
        
        await asyncio.sleep(0.1)
        cleaner.stop()
        assert not cleaner._running


class TestDeadLetterRetryService:
    """死信重试服务测试。"""

    def test_initialization(self, tmp_path: Path) -> None:
        """初始化重试服务。"""
        from ae.bridge_maintenance import RetryConfig
        config = RetryConfig(bridge_dir=str(tmp_path))
        service = DeadLetterRetryService(config)
        assert service._bridge_path == tmp_path

    @pytest.mark.asyncio
    async def test_start_and_stop(self, tmp_path: Path) -> None:
        """启动和停止服务。"""
        from ae.bridge_maintenance import RetryConfig
        config = RetryConfig(bridge_dir=str(tmp_path))
        service = DeadLetterRetryService(config)
        
        service.start()
        assert service._running
        
        await asyncio.sleep(0.1)
        service.stop()
        assert not service._running


class TestBridgeMaintenanceService:
    """桥接维护服务测试。"""

    def test_initialization(self, tmp_path: Path) -> None:
        """初始化维护服务。"""
        service = BridgeMaintenanceService(bridge_dir=str(tmp_path))
        assert service._disk_cleaner is not None
        assert service._retry_service is not None

    @pytest.mark.asyncio
    async def test_start_all(self, tmp_path: Path) -> None:
        """启动所有维护服务。"""
        service = BridgeMaintenanceService(bridge_dir=str(tmp_path))
        
        service.start()
        assert service._disk_cleaner._running
        assert service._retry_service._running
        
        await asyncio.sleep(0.1)
        service.stop()

    @pytest.mark.asyncio
    async def test_stop_all(self, tmp_path: Path) -> None:
        """停止所有维护服务。"""
        service = BridgeMaintenanceService(bridge_dir=str(tmp_path))
        
        service.start()
        await asyncio.sleep(0.1)
        service.stop()
        
        assert not service._disk_cleaner._running
        assert not service._retry_service._running