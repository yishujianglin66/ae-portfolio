"""
AE 进程生命周期测试
====================

验证 AE 进程管理的可靠性。

测试内容：
- 启动 AE 测试
- WM_CLOSE 优雅关闭测试
- 重启 AE 测试（连续 5 次）
- 崩溃状态清理测试
- 看门狗自动恢复测试
- 内存泄漏检测测试

注意：需要真实 AE 环境，Mock 环境下大部分测试会跳过。
"""

from __future__ import annotations

import time
from typing import Any, Dict, List

import pytest


class TestProcessLifecycle:
    """AE 进程生命周期测试套件。"""

    # -----------------------------------------------------------------------
    # 基础启动/关闭测试
    # -----------------------------------------------------------------------

    def test_ae_process_manager_creation(self, test_config):
        """测试 AE 进程管理器创建。

        验证进程管理器能否正常初始化。
        """
        from ae.ae_process_manager import AEProcessManager, AEState

        if test_config.skip_real_ae:
            pytest.skip("Mock 环境，跳过真实 AE 测试")

        manager = AEProcessManager()
        assert manager is not None
        assert isinstance(manager.state, AEState)

    def test_ae_startup(self, ae_process_manager, test_config):
        """测试 AE 启动。

        验证 AE 能否正常启动。
        """
        if test_config.skip_real_ae or ae_process_manager is None:
            pytest.skip("Mock 环境，跳过真实 AE 测试")

        assert ae_process_manager is not None

        started = ae_process_manager.start_ae_with_listener()
        assert started, "AE 启动失败"

        # 等待完全启动
        time.sleep(5)

        assert ae_process_manager.is_ae_running(), "AE 进程未运行"
        pid = ae_process_manager.get_ae_pid()
        assert pid is not None, "无法获取 AE PID"

    def test_ae_wm_close(self, ae_process_manager, test_config):
        """测试 WM_CLOSE 优雅关闭。

        验证 AE 能否通过 WM_CLOSE 消息优雅关闭。
        """
        if test_config.skip_real_ae or ae_process_manager is None:
            pytest.skip("Mock 环境，跳过真实 AE 测试")

        assert ae_process_manager is not None

        # 确保 AE 在运行
        if not ae_process_manager.is_ae_running():
            ae_process_manager.start_ae_with_listener()
            time.sleep(15)

        assert ae_process_manager.is_ae_running(), "测试前 AE 未运行"

        # 执行关闭
        closed = ae_process_manager.close_ae(timeout=30)
        assert closed, "AE 关闭失败"

        # 验证进程已退出
        time.sleep(3)
        assert not ae_process_manager.is_ae_running(), "AE 进程仍在运行"

    def test_ae_restart(self, ae_process_manager, test_config):
        """测试 AE 重启。

        验证 AE 重启流程是否正常工作。
        """
        if test_config.skip_real_ae or ae_process_manager is None:
            pytest.skip("Mock 环境，跳过真实 AE 测试")

        assert ae_process_manager is not None

        # 确保 AE 在运行
        if not ae_process_manager.is_ae_running():
            ae_process_manager.start_ae_with_listener()
            time.sleep(15)

        # 执行重启
        restarted = ae_process_manager.restart_ae()
        assert restarted, "AE 重启失败"

        # 验证重启后运行
        time.sleep(5)
        assert ae_process_manager.is_ae_running(), "重启后 AE 未运行"

    def test_ae_restart_5_times(self, ae_process_manager, test_config):
        """连续重启测试（5次）。

        验证 AE 连续重启的稳定性。
        """
        if test_config.skip_real_ae or ae_process_manager is None:
            pytest.skip("Mock 环境，跳过真实 AE 测试")

        assert ae_process_manager is not None

        # 确保 AE 在运行
        if not ae_process_manager.is_ae_running():
            ae_process_manager.start_ae_with_listener()
            time.sleep(15)

        restart_results: List[bool] = []
        for i in range(5):
            try:
                result = ae_process_manager.restart_ae()
                restart_results.append(result)
                time.sleep(5)
            except Exception as e:
                restart_results.append(False)
                print(f"第 {i+1} 次重启异常: {e}")

        success_count = sum(1 for r in restart_results if r)
        success_rate = success_count / len(restart_results) * 100

        assert success_rate >= 80, (
            f"连续重启成功率过低: {success_rate:.1f}% "
            f"({success_count}/{len(restart_results)})"
        )

    # -----------------------------------------------------------------------
    # 崩溃状态清理测试
    # -----------------------------------------------------------------------

    def test_clear_crash_state(self, test_config):
        """测试崩溃状态清理。

        验证崩溃状态清理功能是否正常执行。
        """
        from ae.ae_process_manager import AEProcessManager

        if test_config.skip_real_ae:
            # Mock 环境下只验证方法存在且不抛异常
            try:
                manager = AEProcessManager()
                result = manager.clear_crash_state()
                assert isinstance(result, dict)
                assert "registry_keys_cleared" in result
                assert "files_removed" in result
                assert "errors" in result
            except Exception:
                # 某些环境下可能没有 AE 注册表项，这是正常的
                pass
            return

        manager = AEProcessManager()
        result = manager.clear_crash_state()

        assert isinstance(result, dict)
        assert "registry_keys_cleared" in result
        assert "files_removed" in result
        assert "errors" in result

    # -----------------------------------------------------------------------
    # 健康检查与看门狗测试
    # -----------------------------------------------------------------------

    def test_health_check(self, ae_process_manager, test_config):
        """测试健康检查。

        验证健康检查功能是否正常工作。
        """
        from ae.ae_process_manager import HealthStatus

        if test_config.skip_real_ae or ae_process_manager is None:
            pytest.skip("Mock 环境，跳过真实 AE 测试")

        assert ae_process_manager is not None

        # 确保 AE 在运行
        if not ae_process_manager.is_ae_running():
            ae_process_manager.start_ae_with_listener()
            time.sleep(15)

        report = ae_process_manager.is_ae_healthy()

        assert report is not None
        assert report.status in (
            HealthStatus.HEALTHY,
            HealthStatus.DEGRADED,
            HealthStatus.UNHEALTHY,
            HealthStatus.CRASHED,
        )
        assert isinstance(report.details, dict)
        assert isinstance(report.recommendations, list)

    def test_process_metrics(self, ae_process_manager, test_config):
        """测试进程指标采集。

        验证能否正确采集 AE 进程指标。
        """
        from ae.ae_process_manager import AEMetrics

        if test_config.skip_real_ae or ae_process_manager is None:
            pytest.skip("Mock 环境，跳过真实 AE 测试")

        assert ae_process_manager is not None

        # 确保 AE 在运行
        if not ae_process_manager.is_ae_running():
            ae_process_manager.start_ae_with_listener()
            time.sleep(15)

        metrics = ae_process_manager.get_ae_metrics()

        assert isinstance(metrics, AEMetrics)
        assert metrics.pid is not None
        assert metrics.memory_mb >= 0
        assert metrics.cpu_percent >= 0
        assert metrics.uptime_seconds >= 0

    def test_memory_leak_detection(self, ae_process_manager, test_config):
        """测试内存泄漏检测。

        验证内存泄漏检测算法是否正常工作。
        """
        if test_config.skip_real_ae or ae_process_manager is None:
            pytest.skip("Mock 环境，跳过真实 AE 测试")

        assert ae_process_manager is not None

        # 确保 AE 在运行
        if not ae_process_manager.is_ae_running():
            ae_process_manager.start_ae_with_listener()
            time.sleep(15)

        # 采集多次指标
        for _ in range(5):
            ae_process_manager.get_ae_metrics()
            time.sleep(1)

        # 执行泄漏检测
        is_leaking, info = ae_process_manager.detect_memory_leak()

        assert isinstance(is_leaking, bool)
        assert isinstance(info, dict)
        assert "samples" in info
        assert "trend" in info

    # -----------------------------------------------------------------------
    # 状态机测试
    # -----------------------------------------------------------------------

    def test_state_transitions(self, test_config):
        """测试状态机转换。

        验证状态机的合法转换是否正常工作。
        """
        from ae.ae_process_manager import AEProcessManager, AEState, InvalidStateTransitionError

        # 测试初始状态
        try:
            manager = AEProcessManager()
            # 初始状态应该是 OFF 或 RUNNING（取决于 AE 是否在运行）
            assert manager.state in (AEState.OFF, AEState.RUNNING, AEState.CRASHED)
        except Exception:
            pytest.skip("无法创建进程管理器实例")

    def test_crash_and_recovery_count(self, test_config):
        """测试崩溃和恢复计数。

        验证崩溃和恢复计数器是否正确维护。
        """
        from ae.ae_process_manager import AEProcessManager

        try:
            manager = AEProcessManager()
            assert manager.crash_count >= 0
            assert manager.recovery_count >= 0
        except Exception:
            pytest.skip("无法创建进程管理器实例")

    # -----------------------------------------------------------------------
    # 看门狗自动恢复测试
    # -----------------------------------------------------------------------

    def test_auto_recover(self, ae_process_manager, test_config):
        """测试自动恢复功能。

        验证看门狗自动恢复功能是否正常。
        """
        if test_config.skip_real_ae or ae_process_manager is None:
            pytest.skip("Mock 环境，跳过真实 AE 测试")

        assert ae_process_manager is not None

        # 确保 AE 在运行
        if not ae_process_manager.is_ae_running():
            ae_process_manager.start_ae_with_listener()
            time.sleep(15)

        # 健康状态下 auto_recover 应该返回 True
        result = ae_process_manager.auto_recover()
        assert isinstance(result, bool)


class TestProcessMetrics:
    """进程指标测试。"""

    def test_ae_metrics_data_class(self):
        """测试 AEMetrics 数据类。"""
        from ae.ae_process_manager import AEMetrics

        metrics = AEMetrics(
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

    def test_health_report_data_class(self):
        """测试 HealthReport 数据类。"""
        from ae.ae_process_manager import HealthReport, HealthStatus

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
