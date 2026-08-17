"""
AE 烟雾测试
===========

快速验证 AE 系统基本功能是否正常。

目标：30秒内完成，快速诊断系统状态。

测试内容：
- AE 进程是否启动
- Bridge 通信是否正常
- 基本命令是否可用
- 项目基本操作
"""

from __future__ import annotations

import time
from typing import Any, Dict

import pytest


class TestSmokeSuite:
    """AE 烟雾测试套件。

    快速验证 AE 系统核心功能是否可用。
    所有测试应在 30 秒内完成。
    """

    # -----------------------------------------------------------------------
    # Bridge 通信测试
    # -----------------------------------------------------------------------

    def test_bridge_ping(self, bridge_client):
        """测试 Bridge 基础 ping 命令。

        验证 Bridge 通信通道是否正常工作。
        """
        response = bridge_client.send_command("ping")
        assert response.is_success, f"ping 失败: {response.error}"
        assert response.result is not None
        assert response.result.get("pong") is True

    def test_bridge_echo(self, bridge_client):
        """测试 Bridge echo 命令。

        验证命令参数传递是否正确。
        """
        test_message = "smoke_test_hello_123"
        response = bridge_client.send_command(
            "echo", {"message": test_message}
        )
        assert response.is_success, f"echo 失败: {response.error}"
        assert response.result is not None
        assert response.result.get("echo") == test_message

    def test_bridge_protocol_version(self, bridge_client):
        """测试 Bridge 协议版本兼容性。

        验证客户端与服务端协议版本是否兼容。
        """
        from ae.bridge_protocol import PROTOCOL_VERSION, is_protocol_compatible

        response = bridge_client.send_command("ping")
        assert response.protocol_version is not None
        assert is_protocol_compatible(response.protocol_version, PROTOCOL_VERSION), (
            f"协议版本不兼容: client={PROTOCOL_VERSION}, server={response.protocol_version}"
        )

    def test_bridge_response_time(self, bridge_client):
        """测试 Bridge 基本响应时间。

        验证单次命令往返延迟是否在可接受范围内（<2秒）。
        """
        start = time.time()
        response = bridge_client.send_command("ping")
        duration = time.time() - start

        assert response.is_success
        assert duration < 2.0, f"响应时间过长: {duration:.3f}s (阈值: 2s)"

    # -----------------------------------------------------------------------
    # 基本操作测试
    # -----------------------------------------------------------------------

    def test_create_composition(self, bridge_client):
        """测试创建合成。

        验证基本合成创建功能是否正常。
        """
        response = bridge_client.send_command(
            "create_composition",
            {
                "name": "SmokeTest_Comp",
                "width": 1920,
                "height": 1080,
                "duration": 5.0,
                "frame_rate": 30,
            },
        )
        assert response.is_success, f"创建合成失败: {response.error}"
        assert response.result is not None
        assert "comp_id" in response.result
        assert response.result.get("name") == "SmokeTest_Comp"

    def test_get_project_info(self, bridge_client):
        """测试获取项目信息。

        验证项目状态查询功能。
        """
        response = bridge_client.send_command("get_project_info")
        assert response.is_success, f"获取项目信息失败: {response.error}"
        assert response.result is not None
        assert "project_name" in response.result

    def test_create_solid_layer(self, bridge_client):
        """测试创建固态图层。

        验证基本图层创建功能。
        """
        response = bridge_client.send_command(
            "create_solid_layer",
            {
                "name": "SmokeTest_Layer",
                "width": 1920,
                "height": 1080,
                "color": [1.0, 0.0, 0.0],
            },
        )
        assert response.is_success, f"创建图层失败: {response.error}"
        assert response.result is not None
        assert "layer_id" in response.result

    def test_apply_effect(self, bridge_client):
        """测试应用效果。

        验证效果应用功能是否正常。
        """
        response = bridge_client.send_command(
            "apply_effect",
            {
                "layer_id": "layer_1",
                "effect_name": "ADBE Gaussian Blur 2",
            },
        )
        assert response.is_success, f"应用效果失败: {response.error}"
        assert response.result is not None
        assert response.result.get("applied") is True

    def test_set_property(self, bridge_client):
        """测试设置属性。

        验证属性设置功能。
        """
        response = bridge_client.send_command(
            "set_property",
            {
                "layer_id": "layer_1",
                "property": "ADBE Transform Group-ADBE Position",
                "value": [960, 540],
            },
        )
        assert response.is_success, f"设置属性失败: {response.error}"
        assert response.result is not None
        assert response.result.get("set") is True

    def test_add_keyframe(self, bridge_client):
        """测试添加关键帧。

        验证关键帧操作功能。
        """
        response = bridge_client.send_command(
            "add_keyframe",
            {
                "layer_id": "layer_1",
                "property": "ADBE Transform Group-ADBE Position",
                "time": 1.0,
                "value": [960, 540],
            },
        )
        assert response.is_success, f"添加关键帧失败: {response.error}"
        assert response.result is not None
        assert "keyframe_id" in response.result

    def test_undo(self, bridge_client):
        """测试撤销操作。

        验证撤销功能是否可用。
        """
        response = bridge_client.send_command("undo", {"steps": 1})
        assert response.is_success, f"撤销失败: {response.error}"
        assert response.result is not None
        assert response.result.get("undone") is True

    def test_redo(self, bridge_client):
        """测试重做操作。

        验证重做功能是否可用。
        """
        response = bridge_client.send_command("redo", {"steps": 1})
        assert response.is_success, f"重做失败: {response.error}"
        assert response.result is not None
        assert response.result.get("redone") is True

    def test_save_project(self, bridge_client, test_project_path):
        """测试保存项目。

        验证项目保存功能。
        """
        response = bridge_client.send_command(
            "save_project",
            {"path": str(test_project_path)},
        )
        assert response.is_success, f"保存项目失败: {response.error}"
        assert response.result is not None
        assert response.result.get("saved") is True

    # -----------------------------------------------------------------------
    # 性能烟雾测试
    # -----------------------------------------------------------------------

    def test_sequential_ping_10x(self, bridge_client):
        """连续 10 次 ping 测试。

        验证连续命令执行的稳定性。
        """
        durations = []
        for i in range(10):
            start = time.time()
            response = bridge_client.send_command("ping")
            duration = time.time() - start
            assert response.is_success, f"第 {i+1} 次 ping 失败"
            durations.append(duration)

        avg_duration = sum(durations) / len(durations)
        max_duration = max(durations)

        assert max_duration < 3.0, f"单次最大延迟过高: {max_duration:.3f}s"
        assert avg_duration < 1.0, f"平均延迟过高: {avg_duration:.3f}s"


class TestSmokeReport:
    """烟雾测试报告生成。"""

    def test_smoke_suite_generation(self, test_config):
        """测试烟雾测试套件生成。"""
        from ae.tests.stability_models import (
            CaseResult,
            StabilityTestSuite,
            TestCategory,
            TestStatus,
        )

        suite = StabilityTestSuite(
            "AE_Smoke_Test",
            TestCategory.SMOKE,
        )

        suite.add_result(
            CaseResult(
                name="ping",
                category="smoke",
                status=TestStatus.PASSED,
                duration_seconds=0.01,
            )
        )
        suite.add_result(
            CaseResult(
                name="echo",
                category="smoke",
                status=TestStatus.PASSED,
                duration_seconds=0.02,
            )
        )
        suite.add_result(
            CaseResult(
                name="create_comp",
                category="smoke",
                status=TestStatus.PASSED,
                duration_seconds=0.1,
            )
        )
        suite.add_result(
            CaseResult(
                name="ae_process_check",
                category="smoke",
                status=TestStatus.SKIPPED,
                error_message="Mock 环境跳过",
            )
        )

        report = suite.finish()

        assert report.total_tests == 4
        assert report.passed_tests == 3
        assert report.skipped_tests == 1
        assert report.pass_rate == 75.0

        # 测试报告生成
        report_dir = test_config.output_dir / "reports"
        paths = suite.save_report(report_dir, ["json", "markdown"])
        assert len(paths) == 2
        assert all(p.exists() for p in paths)
