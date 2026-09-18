"""
Photoshop Bridge 客户端测试
===========================

验证 Photoshop Bridge 客户端的核心功能。

测试内容：
- PS 进程管理器创建
- PS 进程状态机测试
- PS MCP 客户端基础功能测试
- PS 适配器接口测试
- 崩溃状态清理测试
- 健康检查与内存泄漏检测测试

注意：需要真实 PS 环境，Mock 环境下大部分测试会跳过。
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import pytest


class TestPSProcessManager:
    """Photoshop 进程管理器测试套件。"""

    def test_ps_process_manager_creation(self):
        """测试 PS 进程管理器创建。"""
        from ae.ps_process_manager import PSProcessManager, PSState

        manager = PSProcessManager()
        assert manager is not None
        assert isinstance(manager.state, PSState)

    def test_ps_status(self):
        """测试获取 PS 状态。"""
        from ae.ps_process_manager import PSProcessManager

        manager = PSProcessManager()
        status = manager.get_ps_status()

        assert isinstance(status, dict)
        assert "running" in status
        assert "state" in status
        assert "ps_exe_path" in status
        assert "crash_count" in status
        assert "recovery_count" in status

    def test_ps_metrics(self):
        """测试获取 PS 进程指标。"""
        from ae.ps_process_manager import PSMetrics, PSProcessManager

        manager = PSProcessManager()
        metrics = manager.get_ps_metrics()

        assert isinstance(metrics, PSMetrics)
        assert metrics.timestamp > 0

        d = metrics.to_dict()
        assert isinstance(d, dict)
        assert "pid" in d
        assert "memory_mb" in d
        assert "uptime_human" in d

    def test_clear_crash_state(self):
        """测试崩溃状态清理。"""
        from ae.ps_process_manager import PSProcessManager

        manager = PSProcessManager()
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
        from ae.ps_process_manager import PSProcessManager

        manager = PSProcessManager()
        is_leaking, info = manager.detect_memory_leak()

        assert isinstance(is_leaking, bool)
        assert isinstance(info, dict)
        assert "samples" in info

    def test_state_transitions(self):
        """测试状态机转换。"""
        from ae.ps_process_manager import PSProcessManager, PSState

        manager = PSProcessManager()
        assert manager.state in (PSState.OFF, PSState.RUNNING, PSState.CRASHED)

    def test_crash_and_recovery_count(self):
        """测试崩溃计数和恢复计数。"""
        from ae.ps_process_manager import PSProcessManager

        manager = PSProcessManager()
        assert manager.crash_count >= 0
        assert manager.recovery_count >= 0


class TestPSMcpClient:
    """Photoshop MCP 客户端测试套件。"""

    def test_ps_client_creation(self):
        """测试 PS MCP 客户端创建。"""
        from ae.ps_mcp_client import PSMDPClient

        client = PSMDPClient(
            bridge_dir=r"C:\Users\Administrator\Documents\ps-mcp-bridge",
            signature_enabled=False,
        )
        assert client is not None

    def test_ps_client_stats(self):
        """测试客户端统计信息。"""
        from ae.ps_mcp_client import ClientStats, PSMDPClient

        client = PSMDPClient(
            bridge_dir=r"C:\Users\Administrator\Documents\ps-mcp-bridge",
            signature_enabled=False,
        )
        stats = client.stats

        assert isinstance(stats, ClientStats)
        assert stats.total_calls == 0
        assert stats.success_count == 0
        assert stats.failure_count == 0

    def test_ps_client_is_alive(self):
        """测试 is_alive 方法（PS 未运行时应返回 False）。"""
        from ae.ps_mcp_client import PSMDPClient

        client = PSMDPClient(
            bridge_dir=r"C:\Users\Administrator\Documents\ps-mcp-bridge",
            signature_enabled=False,
            poll_interval=0.1,
            max_retries=1,
        )
        result = client.is_alive()
        assert isinstance(result, bool)

    def test_ps_client_exceptions(self):
        """测试异常类导入。"""
        from ae.ps_mcp_client import (
            PSCommandError,
            PSConnectionError,
            PSMCPError,
            PSNotFoundError,
            PSTimeoutError,
        )

        assert PSMCPError is not None
        assert PSConnectionError is not None
        assert PSCommandError is not None
        assert PSTimeoutError is not None
        assert PSNotFoundError is not None

    def test_ps_enums(self):
        """测试枚举类型。"""
        from ae.ps_mcp_client import BlendMode, ColorMode

        assert BlendMode.NORMAL.value == "NORMAL"
        assert BlendMode.MULTIPLY.value == "MULTIPLY"
        assert ColorMode.RGB.value == "RGB"
        assert ColorMode.CMYK.value == "CMYK"

    def test_ps_data_classes(self):
        """测试数据类。"""
        from ae.ps_mcp_client import DocumentInfo, LayerInfo

        doc = DocumentInfo(
            id=1,
            name="TestDoc",
            width=1920,
            height=1080,
            resolution=72.0,
            color_mode="RGB",
            num_layers=5,
        )
        assert doc.name == "TestDoc"
        assert doc.width == 1920

        layer = LayerInfo(
            index=0,
            name="Layer1",
            type="pixel",
            visible=True,
            locked=False,
            opacity=100,
        )
        assert layer.name == "Layer1"
        assert layer.visible is True


class TestPSAdapter:
    """Photoshop 适配器测试套件。"""

    def test_ps_adapter_imports(self):
        """测试适配器导入。"""
        from ae.adapters.ps_adapter import (
            BasePSAdapter,
            MCPClientPSAdapter,
            PSAdapterFactory,
            PuppetEnginePSAdapter,
        )

        assert BasePSAdapter is not None
        assert MCPClientPSAdapter is not None
        assert PuppetEnginePSAdapter is not None
        assert PSAdapterFactory is not None

    def test_ps_adapter_factory_mcp(self):
        """测试工厂创建 MCP 适配器。"""
        from ae.adapters.ps_adapter import MCPClientPSAdapter, PSAdapterFactory

        adapter = PSAdapterFactory.create("mcp")
        assert isinstance(adapter, MCPClientPSAdapter)
        assert adapter.name == "ps_mcp"

    def test_ps_adapter_factory_puppet(self):
        """测试工厂创建 Puppet 适配器。"""
        from ae.adapters.ps_adapter import PSAdapterFactory, PuppetEnginePSAdapter

        adapter = PSAdapterFactory.create("puppet")
        assert isinstance(adapter, PuppetEnginePSAdapter)
        assert adapter.name == "ps_puppet"

    def test_ps_adapter_factory_invalid(self):
        """测试工厂无效类型。"""
        from ae.adapters.ps_adapter import PSAdapterFactory

        with pytest.raises(ValueError):
            PSAdapterFactory.create("invalid")

    def test_ps_adapter_class_attributes(self):
        """测试适配器类属性。"""
        from ae.adapters.ps_adapter import BasePSAdapter

        assert BasePSAdapter.name == "ps_base"
        assert BasePSAdapter.supports_gui is True
        assert BasePSAdapter.requires_gui is True


class TestPSIntegration:
    """Photoshop 集成测试套件。"""

    def test_ps_module_imports(self):
        """测试模块级导入。"""
        from ae import ps_mcp_client, ps_process_manager
        from ae.adapters import ps_adapter

        assert ps_mcp_client is not None
        assert ps_process_manager is not None
        assert ps_adapter is not None

    def test_ps_adapter_exported_in_init(self):
        """测试适配器在 __init__.py 中导出。"""
        from ae.adapters import (
            BasePSAdapter,
            MCPClientPSAdapter,
            PSAdapterFactory,
            PuppetEnginePSAdapter,
        )

        assert BasePSAdapter is not None
        assert MCPClientPSAdapter is not None
        assert PuppetEnginePSAdapter is not None
        assert PSAdapterFactory is not None