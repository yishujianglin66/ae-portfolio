"""Bridge Health Monitor 单元测试。"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ae.bridge_health import (
    BridgeHealthMonitor,
    HealthCheckItem,
    HealthReport,
)


class TestHealthCheckItem:
    """健康检查项测试。"""

    def test_create_check_item(self) -> None:
        """创建检查项。"""
        item = HealthCheckItem(
            name="test",
            status="healthy",
            score=100,
            message="Test check",
        )
        assert item.name == "test"
        assert item.status == "healthy"
        assert item.score == 100
        assert item.message == "Test check"

    def test_check_item_failed(self) -> None:
        """失败的检查项。"""
        item = HealthCheckItem(
            name="test",
            status="critical",
            score=0,
            message="Something went wrong",
        )
        assert item.status == "critical"
        assert item.score == 0
        assert item.message == "Something went wrong"


class TestHealthReport:
    """健康报告测试。"""

    def test_create_report(self) -> None:
        """创建健康报告。"""
        report = HealthReport(bridge_dir="/tmp/bridge")
        assert report.bridge_dir == "/tmp/bridge"
        assert report.score == 100
        assert report.status == "healthy"
        assert report.timestamp is not None

    def test_report_with_checks(self) -> None:
        """带检查项的报告。"""
        report = HealthReport(bridge_dir="/tmp/bridge")
        report.checks.append(
            HealthCheckItem(name="check1", status="healthy", score=100, message="Check 1")
        )
        report.checks.append(
            HealthCheckItem(name="check2", status="healthy", score=100, message="Check 2")
        )
        
        report.score = 100
        assert report.status == "healthy"

    def test_report_summary(self) -> None:
        """报告摘要。"""
        report = HealthReport(bridge_dir="/tmp/bridge")
        report.checks.append(
            HealthCheckItem(name="test", status="healthy", score=100, message="Test")
        )
        report.score = 100
        
        summary = report.summary()
        assert "HEALTHY" in summary
        assert "score=100/100" in summary


class TestBridgeHealthMonitor:
    """健康监视器测试。"""

    def test_initialization(self, tmp_path: Path) -> None:
        """初始化健康监视器。"""
        monitor = BridgeHealthMonitor(str(tmp_path))
        assert monitor.bridge_dir == tmp_path

    def test_check_health_empty(self, tmp_path: Path) -> None:
        """空目录健康检查。"""
        monitor = BridgeHealthMonitor(str(tmp_path))
        report = monitor.check_health()
        
        assert isinstance(report, HealthReport)
        assert report.bridge_dir == str(tmp_path)
        assert isinstance(report.score, int)
        assert report.status in ("healthy", "degraded", "unhealthy", "critical")

    def test_check_listener_alive(self, tmp_path: Path) -> None:
        """检查监听器活跃性。"""
        monitor = BridgeHealthMonitor(str(tmp_path))
        
        check = monitor._check_listener_alive()
        assert check.name == "listener_alive"

    def test_check_disk_space(self, tmp_path: Path) -> None:
        """检查磁盘空间。"""
        monitor = BridgeHealthMonitor(str(tmp_path))
        
        check = monitor._check_disk_space()
        assert check.name == "disk_space"

    def test_check_command_queue(self, tmp_path: Path) -> None:
        """检查命令队列。"""
        monitor = BridgeHealthMonitor(str(tmp_path))
        
        check = monitor._check_command_queue()
        assert check.name == "command_queue"

    def test_get_latest_report(self, tmp_path: Path) -> None:
        """获取最新报告。"""
        monitor = BridgeHealthMonitor(str(tmp_path))
        
        report = monitor.check_health()
        latest = monitor._last_report
        
        assert latest is not None
        assert latest.score == report.score

    def test_report_summary_format(self) -> None:
        """报告摘要格式。"""
        report = HealthReport(bridge_dir="/tmp/bridge")
        report.checks.append(
            HealthCheckItem(name="test", status="healthy", score=100, message="Test")
        )
        report.score = 80
        report.status = "healthy"
        
        summary = report.summary()
        assert "Bridge Health:" in summary
        assert "test:" in summary

    def test_report_to_dict(self) -> None:
        """报告转字典。"""
        report = HealthReport(bridge_dir="/tmp/bridge")
        report.checks.append(
            HealthCheckItem(name="test", status="healthy", score=100, message="Test")
        )
        report.score = 80
        
        data = report.to_dict()
        assert data["score"] == 80
        assert data["bridge_dir"] == "/tmp/bridge"
        assert len(data["checks"]) == 1

    def test_check_dead_letter_queue(self, tmp_path: Path) -> None:
        """检查死信队列。"""
        monitor = BridgeHealthMonitor(str(tmp_path))
        
        check = monitor._check_dead_letter_queue()
        assert check.name == "dead_letter"

    def test_check_idempotency_cache(self, tmp_path: Path) -> None:
        """检查幂等缓存。"""
        monitor = BridgeHealthMonitor(str(tmp_path))
        
        check = monitor._check_idempotency_cache()
        assert check.name == "idempotency_cache"

    def test_health_report_with_degraded_status(self) -> None:
        """带降级状态的健康报告。"""
        report = HealthReport(bridge_dir="/tmp/bridge")
        report.checks.append(
            HealthCheckItem(name="test", status="warning", score=50, message="Warning")
        )
        report.score = 50
        report.status = "degraded"
        
        summary = report.summary()
        assert "DEGRADED" in summary

    def test_health_check_item_with_details(self) -> None:
        """带详细信息的检查项。"""
        item = HealthCheckItem(
            name="test",
            status="healthy",
            score=100,
            message="OK",
            details={"key": "value"}
        )
        assert item.details == {"key": "value"}