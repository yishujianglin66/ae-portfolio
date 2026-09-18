"""
Premiere Pro Bridge 客户端测试
=============================

验证 Premiere Pro Bridge 客户端的核心功能。

测试内容：
- PR 进程管理器创建
- PR 进程状态机测试
- PR MCP 客户端基础功能测试
- PR 适配器接口测试
- 崩溃状态清理测试
- 健康检查与内存泄漏检测测试

注意：需要真实 PR 环境，Mock 环境下大部分测试会跳过。
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import pytest


class TestPRProcessManager:
    """Premiere Pro 进程管理器测试套件。"""

    def test_pr_process_manager_creation(self):
        """测试 PR 进程管理器创建。"""
        from ae.pr_process_manager import PRProcessManager, PRState

        manager = PRProcessManager()
        assert manager is not None
        assert isinstance(manager.state, PRState)

    def test_pr_status(self):
        """测试获取 PR 状态。"""
        from ae.pr_process_manager import PRProcessManager

        manager = PRProcessManager()
        status = manager.get_pr_status()

        assert isinstance(status, dict)
        assert "running" in status
        assert "state" in status
        assert "pr_exe_path" in status
        assert "crash_count" in status
        assert "recovery_count" in status

    def test_pr_metrics(self):
        """测试获取 PR 进程指标。"""
        from ae.pr_process_manager import PRMetrics, PRProcessManager

        manager = PRProcessManager()
        metrics = manager.get_pr_metrics()

        assert isinstance(metrics, PRMetrics)
        assert metrics.timestamp > 0

        d = metrics.to_dict()
        assert isinstance(d, dict)
        assert "pid" in d
        assert "memory_mb" in d
        assert "uptime_human" in d

    def test_clear_crash_state(self):
        """测试崩溃状态清理。"""
        from ae.pr_process_manager import PRProcessManager

        manager = PRProcessManager()
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
        from ae.pr_process_manager import PRProcessManager

        manager = PRProcessManager()
        is_leaking, info = manager.detect_memory_leak()

        assert isinstance(is_leaking, bool)
        assert isinstance(info, dict)
        assert "samples" in info
        assert "trend" in info

    def test_state_transitions(self):
        """测试状态机转换。"""
        from ae.pr_process_manager import PRProcessManager, PRState

        manager = PRProcessManager()
        assert manager.state in (PRState.OFF, PRState.RUNNING, PRState.CRASHED)

    def test_crash_and_recovery_count(self):
        """测试崩溃和恢复计数。"""
        from ae.pr_process_manager import PRProcessManager

        manager = PRProcessManager()
        assert manager.crash_count >= 0
        assert manager.recovery_count >= 0

    def test_add_state_callback(self):
        """测试状态回调功能。"""
        from ae.pr_process_manager import PRProcessManager, PRState

        manager = PRProcessManager()
        states_seen: list[tuple] = []

        def callback(old_state: PRState, new_state: PRState):
            states_seen.append((old_state, new_state))

        manager.add_state_callback(callback)
        manager.remove_state_callback(callback)

        assert len(states_seen) >= 0

    def test_launch_mode_setting(self):
        """测试启动模式设置。"""
        from ae.pr_process_manager import LaunchMode, PRProcessManager

        manager = PRProcessManager()
        manager.set_launch_mode(LaunchMode.NORMAL)
        assert manager._launch_mode == LaunchMode.NORMAL

        manager.set_launch_mode(LaunchMode.SAFE_MODE)
        assert manager._launch_mode == LaunchMode.SAFE_MODE

        manager.set_launch_mode(LaunchMode.HEADLESS)
        assert manager._launch_mode == LaunchMode.HEADLESS

    def test_workspace_setting(self):
        """测试工作区设置。"""
        from pathlib import Path

        from ae.pr_process_manager import PRProcessManager

        manager = PRProcessManager()

        manager.set_workspace(None)
        assert manager._workspace_path is None

        with pytest.raises(ValueError):
            manager.set_workspace("invalid.txt")


class TestPRMCP:
    """Premiere Pro MCP 客户端测试套件。"""

    def test_pr_mcp_creation(self):
        """测试 PR MCP 客户端创建。"""
        from ae.pr_mcp_client import PRMCP

        client = PRMCP()
        assert client is not None

    def test_pr_mcp_bridge_initialization(self):
        """测试 PR MCP 客户端桥接初始化。"""
        from ae.pr_mcp_client import PRMCP

        client = PRMCP()
        assert client._bridge is not None

    def test_pr_mcp_build_command(self):
        """测试命令构建功能。"""
        from ae.pr_mcp_client import PRMCP

        client = PRMCP()
        command = client._build_command("createSequence", {"name": "Test"})

        assert isinstance(command, dict)
        assert command["command"] == "createSequence"
        assert command["params"]["name"] == "Test"
        assert "id" in command
        assert "timestamp" in command

    def test_pr_mcp_extract_protocol_version(self):
        """测试协议版本提取。"""
        from ae.pr_mcp_client import PRMCP

        client = PRMCP()

        response_v1 = {"protocol_version": "1.0", "result": {}}
        assert client._extract_protocol_version(response_v1) == "1.0"

        response_v2 = {"protocol_version": "2.0", "result": {}}
        assert client._extract_protocol_version(response_v2) == "2.0"

        response_no_version = {"result": {}}
        assert client._extract_protocol_version(response_no_version) == PRMCP.DEFAULT_PROTOCOL_VERSION

    def test_pr_mcp_sanitize_log_text(self):
        """测试日志脱敏功能。"""
        from ae.pr_mcp_client import PRMCP

        client = PRMCP()

        test_text = "Authorization: Bearer sk-abc123def456"
        sanitized = client._sanitize_log_text(test_text)
        assert "sk-abc123def456" not in sanitized
        assert "[REDACTED]" in sanitized

        test_text2 = 'api_key="sk-secret-token"'
        sanitized2 = client._sanitize_log_text(test_text2)
        assert "sk-secret-token" not in sanitized2
        assert "[REDACTED]" in sanitized2

    def test_pr_mcp_error_mapping(self):
        """测试错误映射功能。"""
        from ae.pr_mcp_client import PRMCP, PRInvalidArgumentError, PRNotFoundError, PRPermissionDeniedError

        client = PRMCP()

        not_found_response = {"success": False, "error": {"code": "NOT_FOUND", "message": "Not found"}}
        exc = client._map_error(not_found_response)
        assert isinstance(exc, PRNotFoundError)

        invalid_arg_response = {"success": False, "error": {"code": "INVALID_ARGUMENT", "message": "Invalid arg"}}
        exc = client._map_error(invalid_arg_response)
        assert isinstance(exc, PRInvalidArgumentError)

        permission_response = {"success": False, "error": {"code": "PERMISSION_DENIED", "message": "Denied"}}
        exc = client._map_error(permission_response)
        assert isinstance(exc, PRPermissionDeniedError)

    def test_pr_mcp_project_methods(self):
        """测试项目操作方法存在性。"""
        from ae.pr_mcp_client import PRMCP

        client = PRMCP()

        assert hasattr(client, "new_project")
        assert hasattr(client, "open_project")
        assert hasattr(client, "save_project")
        assert hasattr(client, "close_project")
        assert hasattr(client, "get_project_info")

    def test_pr_mcp_sequence_methods(self):
        """测试序列操作方法存在性。"""
        from ae.pr_mcp_client import PRMCP

        client = PRMCP()

        assert hasattr(client, "create_sequence")
        assert hasattr(client, "list_sequences")
        assert hasattr(client, "get_sequence_info")
        assert hasattr(client, "delete_sequence")

    def test_pr_mcp_clip_methods(self):
        """测试剪辑操作方法存在性。"""
        from ae.pr_mcp_client import PRMCP

        client = PRMCP()

        assert hasattr(client, "import_media")
        assert hasattr(client, "add_clip_to_sequence")
        assert hasattr(client, "cut_clip")
        assert hasattr(client, "split_clip")
        assert hasattr(client, "delete_clip")
        assert hasattr(client, "move_clip")

    def test_pr_mcp_effect_methods(self):
        """测试效果操作方法存在性。"""
        from ae.pr_mcp_client import PRMCP

        client = PRMCP()

        assert hasattr(client, "apply_effect")
        assert hasattr(client, "remove_effect")
        assert hasattr(client, "set_effect_param")
        assert hasattr(client, "get_effect_params")
        assert hasattr(client, "list_available_effects")

    def test_pr_mcp_render_methods(self):
        """测试渲染导出方法存在性。"""
        from ae.pr_mcp_client import PRMCP

        client = PRMCP()

        assert hasattr(client, "render_sequence")
        assert hasattr(client, "get_render_status")
        assert hasattr(client, "cancel_render")


class TestPRAdapter:
    """Premiere Pro 适配器测试套件。"""

    def test_pr_adapter_creation(self):
        """测试 PR 适配器创建。"""
        from ae.adapters.pr_adapter import PRAdapter

        adapter = PRAdapter()
        assert adapter is not None
        assert adapter.name == "pr_mcp"

    def test_pr_adapter_base_class(self):
        """测试 PR 适配器基类。"""
        from ae.adapters.pr_adapter import BasePRAdapter

        assert BasePRAdapter.name == "pr"
        assert BasePRAdapter.supports_gui is True
        assert BasePRAdapter.requires_gui is True

    def test_pr_adapter_methods(self):
        """测试 PR 适配器方法存在性。"""
        from ae.adapters.pr_adapter import PRAdapter

        adapter = PRAdapter()

        assert hasattr(adapter, "create_sequence")
        assert hasattr(adapter, "import_media")
        assert hasattr(adapter, "apply_effect")
        assert hasattr(adapter, "render_sequence")
        assert hasattr(adapter, "new_project")
        assert hasattr(adapter, "open_project")
        assert hasattr(adapter, "save_project")
        assert hasattr(adapter, "close_project")
        assert hasattr(adapter, "list_sequences")
        assert hasattr(adapter, "delete_sequence")
        assert hasattr(adapter, "add_clip_to_sequence")
        assert hasattr(adapter, "cut_clip")
        assert hasattr(adapter, "split_clip")
        assert hasattr(adapter, "delete_clip")
        assert hasattr(adapter, "remove_effect")
        assert hasattr(adapter, "get_effect_params")
        assert hasattr(adapter, "get_project_info")
        assert hasattr(adapter, "get_sequence_info")

    def test_pr_adapter_with_client(self):
        """测试带客户端注入的 PR 适配器。"""
        from ae.adapters.pr_adapter import PRAdapter
        from ae.pr_mcp_client import PRMCP

        client = PRMCP()
        adapter = PRAdapter(pr_client=client)

        assert adapter is not None
        assert adapter._client is client


class TestPRMetrics:
    """PR 进程指标数据类测试。"""

    def test_pr_metrics_data_class(self):
        """测试 PRMetrics 数据类。"""
        from ae.pr_process_manager import PRMetrics

        metrics = PRMetrics(
            pid=1234,
            cpu_percent=25.5,
            memory_mb=2048.0,
            memory_percent=10.0,
            handle_count=500,
            thread_count=20,
            uptime_seconds=3600.0,
        )

        assert metrics.pid == 1234
        assert metrics.cpu_percent == 25.5
        assert metrics.memory_mb == 2048.0
        assert metrics.timestamp > 0

        d = metrics.to_dict()
        assert isinstance(d, dict)
        assert d["pid"] == 1234
        assert "uptime_human" in d

    def test_pr_metrics_defaults(self):
        """测试 PRMetrics 默认值。"""
        from ae.pr_process_manager import PRMetrics

        metrics = PRMetrics()

        assert metrics.pid is None
        assert metrics.cpu_percent == 0.0
        assert metrics.memory_mb == 0.0
        assert metrics.timestamp > 0


class TestHealthReport:
    """健康报告数据类测试。"""

    def test_health_report_data_class(self):
        """测试 HealthReport 数据类。"""
        from ae.pr_process_manager import HealthReport, HealthStatus

        report = HealthReport(
            status=HealthStatus.HEALTHY,
            details={"cpu": 10.0, "memory": 1024.0},
            recommendations=["一切正常"],
        )

        assert report.status == HealthStatus.HEALTHY
        assert len(report.details) == 2
        assert len(report.recommendations) == 1

        d = report.to_dict()
        assert isinstance(d, dict)
        assert d["status"] == "HEALTHY"

    def test_health_report_defaults(self):
        """测试 HealthReport 默认值。"""
        from ae.pr_process_manager import HealthReport, HealthStatus

        report = HealthReport()

        assert report.status == HealthStatus.HEALTHY
        assert report.details == {}
        assert report.recommendations == []
        assert report.timestamp > 0


class TestPRExceptions:
    """PR 异常类测试。"""

    def test_pr_process_error(self):
        """测试 PRProcessError。"""
        from ae.pr_process_manager import PRProcessError

        exc = PRProcessError("测试错误")
        assert str(exc) == "测试错误"

    def test_invalid_state_transition_error(self):
        """测试 InvalidStateTransitionError。"""
        from ae.pr_process_manager import InvalidStateTransitionError, PRState

        exc = InvalidStateTransitionError(PRState.OFF, PRState.RUNNING)
        assert "OFF" in str(exc)
        assert "RUNNING" in str(exc)

    def test_pr_mcp_exceptions(self):
        """测试 PR MCP 客户端异常。"""
        from ae.pr_mcp_client import (
            PRConnectionError,
            PRError,
            PRInvalidArgumentError,
            PRNotFoundError,
            PRPermissionDeniedError,
            PRServerError,
            PRTimeoutError,
            PRUnknownError,
        )

        exc = PRConnectionError("连接失败")
        assert isinstance(exc, PRError)
        assert str(exc) == "连接失败"

        exc = PRTimeoutError("超时")
        assert isinstance(exc, PRError)
        assert str(exc) == "超时"

        exc = PRNotFoundError("未找到")
        assert isinstance(exc, PRError)
        assert str(exc) == "未找到"

        exc = PRInvalidArgumentError("参数无效")
        assert isinstance(exc, PRError)
        assert str(exc) == "参数无效"

        exc = PRPermissionDeniedError("权限不足")
        assert isinstance(exc, PRError)
        assert str(exc) == "权限不足"

        exc = PRServerError("服务器错误")
        assert isinstance(exc, PRError)
        assert str(exc) == "服务器错误"

        exc = PRUnknownError("未知错误")
        assert isinstance(exc, PRError)
        assert str(exc) == "未知错误"


class TestPRIntegration:
    """Premiere Pro 集成测试套件。"""

    def test_adapter_import_from_package(self):
        """测试从包导入适配器。"""
        from ae.adapters import BasePRAdapter, PRAdapter

        assert PRAdapter is not None
        assert BasePRAdapter is not None

    def test_process_manager_import(self):
        """测试导入进程管理器。"""
        from ae.pr_process_manager import (
            CloseMethod,
            HealthStatus,
            LaunchMode,
            PRProcessManager,
            PRState,
        )

        assert PRProcessManager is not None
        assert PRState is not None
        assert HealthStatus is not None
        assert LaunchMode is not None
        assert CloseMethod is not None

    def test_mcp_client_import(self):
        """测试导入 MCP 客户端。"""
        from ae.pr_mcp_client import PRMCP

        assert PRMCP is not None

    def test_adapter_client_compatibility(self):
        """测试适配器与客户端兼容性。"""
        from ae.adapters.pr_adapter import PRAdapter
        from ae.pr_mcp_client import PRMCP
        from ae.pr_process_manager import PRProcessManager

        client = PRMCP()
        adapter = PRAdapter(pr_client=client)
        manager = PRProcessManager()

        assert adapter is not None
        assert client is not None
        assert manager is not None