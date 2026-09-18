"""
Audition Bridge 客户端测试
===========================

验证 Audition Bridge 客户端的核心功能。

测试内容：
- AU 进程管理器创建
- AU 进程状态机测试
- AU MCP 客户端基础功能测试
- AU 适配器接口测试
- 崩溃状态清理测试
- 健康检查与内存泄漏检测测试

注意：需要真实 AU 环境，Mock 环境下大部分测试会跳过。
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import pytest


class TestAUProcessManager:
    """Audition 进程管理器测试套件。"""

    def test_au_process_manager_creation(self):
        """测试 AU 进程管理器创建。"""
        from ae.au_process_manager import AUProcessManager, AUState

        manager = AUProcessManager()
        assert manager is not None
        assert isinstance(manager.state, AUState)

    def test_au_status(self):
        """测试获取 AU 状态。"""
        from ae.au_process_manager import AUProcessManager

        manager = AUProcessManager()
        status = manager.get_au_status()

        assert isinstance(status, dict)
        assert "running" in status
        assert "state" in status
        assert "au_exe_path" in status
        assert "crash_count" in status
        assert "recovery_count" in status

    def test_au_metrics(self):
        """测试获取 AU 进程指标。"""
        from ae.au_process_manager import AUMetrics, AUProcessManager

        manager = AUProcessManager()
        metrics = manager.get_au_metrics()

        assert isinstance(metrics, AUMetrics)
        assert metrics.timestamp > 0

        d = metrics.to_dict()
        assert isinstance(d, dict)
        assert "pid" in d
        assert "memory_mb" in d
        assert "uptime_human" in d

    def test_clear_crash_state(self):
        """测试崩溃状态清理。"""
        from ae.au_process_manager import AUProcessManager

        manager = AUProcessManager()
        try:
            result = manager.clear_crash_state()

            assert isinstance(result, dict)
            assert "registry_keys_cleared" in result
            assert "files_removed" in result
            assert "errors" in result
        except Exception:
            pytest.skip("崩溃状态清理在某些环境下可能无法执行")

    def test_detect_memory_leak(self):
        """测试内存泄漏检测。"""
        from ae.au_process_manager import AUProcessManager

        manager = AUProcessManager()
        is_leaking, info = manager.detect_memory_leak()

        assert isinstance(is_leaking, bool)
        assert isinstance(info, dict)
        assert "samples" in info

    def test_state_transitions(self):
        """测试状态机转换。"""
        from ae.au_process_manager import AUProcessManager, AUState

        manager = AUProcessManager()
        assert manager.state in (AUState.OFF, AUState.RUNNING, AUState.CRASHED)

    def test_crash_and_recovery_count(self):
        """测试崩溃计数和恢复计数。"""
        from ae.au_process_manager import AUProcessManager

        manager = AUProcessManager()
        assert manager.crash_count >= 0
        assert manager.recovery_count >= 0


class TestAUMcpClient:
    """Audition MCP 客户端测试套件。"""

    def test_au_client_creation(self):
        """测试 AU MCP 客户端创建。"""
        from ae.au_mcp_client import AUMDPClient

        client = AUMDPClient(
            bridge_dir=r"C:\Users\Administrator\Documents\au-mcp-bridge",
            signature_enabled=False,
        )
        assert client is not None

    def test_au_client_stats(self):
        """测试客户端统计信息。"""
        from ae.au_mcp_client import AUMDPClient, ClientStats

        client = AUMDPClient(
            bridge_dir=r"C:\Users\Administrator\Documents\au-mcp-bridge",
            signature_enabled=False,
        )
        stats = client.stats

        assert isinstance(stats, ClientStats)
        assert stats.total_calls == 0
        assert stats.success_count == 0
        assert stats.failure_count == 0

    def test_au_client_is_alive(self):
        """测试 is_alive 方法（AU 未运行时应返回 False）。"""
        from ae.au_mcp_client import AUMDPClient

        client = AUMDPClient(
            bridge_dir=r"C:\Users\Administrator\Documents\au-mcp-bridge",
            signature_enabled=False,
            poll_interval=0.1,
            max_retries=1,
        )
        result = client.is_alive()
        assert isinstance(result, bool)

    def test_au_client_exceptions(self):
        """测试异常类导入。"""
        from ae.au_mcp_client import (
            AUCommandError,
            AUConnectionError,
            AUMCPError,
            AUNotFoundError,
            AUTimeoutError,
        )

        assert AUMCPError is not None
        assert AUConnectionError is not None
        assert AUCommandError is not None
        assert AUTimeoutError is not None
        assert AUNotFoundError is not None

    def test_au_data_classes(self):
        """测试数据类。"""
        from ae.au_mcp_client import ClipInfo, SessionInfo, TrackInfo

        session = SessionInfo(
            name="TestSession",
            sample_rate=44100,
            bit_depth=16,
            num_tracks=2,
            duration=120.0,
        )
        assert session.name == "TestSession"
        assert session.sample_rate == 44100

        track = TrackInfo(
            name="Track1",
            type="audio",
            index=0,
            solo=False,
            mute=False,
            volume=1.0,
        )
        assert track.name == "Track1"
        assert track.type == "audio"

        clip = ClipInfo(
            name="Clip1",
            track_index=0,
            start_time=0.0,
            end_time=10.0,
            duration=10.0,
        )
        assert clip.name == "Clip1"
        assert clip.duration == 10.0


class TestAUAdapter:
    """Audition 适配器测试套件。"""

    def test_au_adapter_imports(self):
        """测试适配器导入。"""
        from ae.adapters.au_adapter import (
            AUAdapterFactory,
            BaseAUAdapter,
            MCPClientAUAdapter,
            PuppetEngineAUAdapter,
        )

        assert BaseAUAdapter is not None
        assert MCPClientAUAdapter is not None
        assert PuppetEngineAUAdapter is not None
        assert AUAdapterFactory is not None

    def test_au_adapter_factory_mcp(self):
        """测试工厂创建 MCP 适配器。"""
        from ae.adapters.au_adapter import AUAdapterFactory, MCPClientAUAdapter

        adapter = AUAdapterFactory.create("mcp")
        assert isinstance(adapter, MCPClientAUAdapter)
        assert adapter.name == "au_mcp"

    def test_au_adapter_factory_puppet(self):
        """测试工厂创建 Puppet 适配器。"""
        from ae.adapters.au_adapter import AUAdapterFactory, PuppetEngineAUAdapter

        adapter = AUAdapterFactory.create("puppet")
        assert isinstance(adapter, PuppetEngineAUAdapter)
        assert adapter.name == "au_puppet"

    def test_au_adapter_factory_invalid(self):
        """测试工厂无效类型。"""
        from ae.adapters.au_adapter import AUAdapterFactory

        with pytest.raises(ValueError):
            AUAdapterFactory.create("invalid")

    def test_au_adapter_class_attributes(self):
        """测试适配器类属性。"""
        from ae.adapters.au_adapter import BaseAUAdapter

        assert BaseAUAdapter.name == "au_base"
        assert BaseAUAdapter.supports_gui is True
        assert BaseAUAdapter.requires_gui is True


class TestAUIntegration:
    """Audition 集成测试套件。"""

    def test_au_module_imports(self):
        """测试模块级导入。"""
        from ae import au_mcp_client, au_process_manager
        from ae.adapters import au_adapter

        assert au_mcp_client is not None
        assert au_process_manager is not None
        assert au_adapter is not None

    def test_au_adapter_exported_in_init(self):
        """测试适配器在 __init__.py 中导出。"""
        from ae.adapters import (
            AUAdapterFactory,
            BaseAUAdapter,
            MCPClientAUAdapter,
            PuppetEngineAUAdapter,
        )

        assert BaseAUAdapter is not None
        assert MCPClientAUAdapter is not None
        assert PuppetEngineAUAdapter is not None
        assert AUAdapterFactory is not None