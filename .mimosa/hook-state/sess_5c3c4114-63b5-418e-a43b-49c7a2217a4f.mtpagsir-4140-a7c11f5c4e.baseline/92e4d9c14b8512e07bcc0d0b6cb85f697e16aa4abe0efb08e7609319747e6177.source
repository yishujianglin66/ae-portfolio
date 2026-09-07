"""
AE 稳定性测试套件主入口
========================

生产级稳定性测试套件，提供：
- 测试分类管理（烟雾测试/基础测试/压力测试/耐久测试）
- 测试报告生成（HTML/Markdown/JSON）
- 历史结果对比（趋势分析）
- 通过率、平均延迟、错误分布统计

注意：核心数据模型和工具函数定义在 stability_models.py 中，
以避免 pytest 将 Test* 开头的类误认为是测试类。
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List

import pytest

from ae.tests.stability_models import (
    CaseResult,
    HistoricalComparator,
    StabilityTestSuite,
    SuiteReport,
    TestCategory,
    TestStatus,
    measure_latency,
)


class TestStabilitySuiteCore:
    """稳定性测试套件核心功能测试。"""

    def test_case_result_creation(self):
        """测试用例结果创建。"""
        result = CaseResult(
            name="test_example",
            category="smoke",
            status=TestStatus.PASSED,
            duration_seconds=0.5,
        )

        assert result.name == "test_example"
        assert result.category == "smoke"
        assert result.status == TestStatus.PASSED
        assert result.duration_seconds == 0.5
        assert result.error_message is None

    def test_case_result_to_dict(self):
        """测试用例结果序列化。"""
        result = CaseResult(
            name="test_dict",
            category="basic",
            status=TestStatus.FAILED,
            duration_seconds=1.23,
            error_message="something went wrong",
            error_type="ValueError",
            metrics={"latency_ms": 123.45},
        )

        d = result.to_dict()
        assert d["name"] == "test_dict"
        assert d["status"] == "failed"
        assert d["duration_seconds"] == 1.23
        assert d["error_message"] == "something went wrong"
        assert d["metrics"]["latency_ms"] == 123.45

    def test_suite_report_pass_rate(self):
        """测试报告通过率计算。"""
        suite = StabilityTestSuite("Test Suite", TestCategory.SMOKE)

        suite.add_result(
            CaseResult(name="t1", category="smoke", status=TestStatus.PASSED)
        )
        suite.add_result(
            CaseResult(name="t2", category="smoke", status=TestStatus.PASSED)
        )
        suite.add_result(
            CaseResult(name="t3", category="smoke", status=TestStatus.FAILED)
        )
        suite.add_result(
            CaseResult(name="t4", category="smoke", status=TestStatus.SKIPPED)
        )

        report = suite.finish()

        assert report.total_tests == 4
        assert report.passed_tests == 2
        assert report.failed_tests == 1
        assert report.skipped_tests == 1
        assert report.pass_rate == 50.0

    def test_suite_report_latency_stats(self):
        """测试报告延迟统计。"""
        suite = StabilityTestSuite("Latency Test", TestCategory.BASIC)

        for i in range(10):
            suite.add_result(
                CaseResult(
                    name=f"latency_test_{i}",
                    category="basic",
                    status=TestStatus.PASSED,
                    metrics={"latency_ms": float(10 + i * 10)},
                )
            )

        report = suite.finish()
        stats = report.latency_stats

        assert stats["min_ms"] == 10.0
        assert stats["max_ms"] == 100.0
        assert stats["avg_ms"] == 55.0
        assert "p95_ms" in stats
        assert "p99_ms" in stats

    def test_suite_report_error_distribution(self):
        """测试报告错误分布。"""
        suite = StabilityTestSuite("Error Test", TestCategory.STRESS)

        suite.add_result(
            CaseResult(
                name="e1",
                category="stress",
                status=TestStatus.FAILED,
                error_type="TimeoutError",
            )
        )
        suite.add_result(
            CaseResult(
                name="e2",
                category="stress",
                status=TestStatus.FAILED,
                error_type="TimeoutError",
            )
        )
        suite.add_result(
            CaseResult(
                name="e3",
                category="stress",
                status=TestStatus.FAILED,
                error_type="ConnectionError",
            )
        )

        report = suite.finish()
        dist = report.error_distribution

        assert dist["TimeoutError"] == 2
        assert dist["ConnectionError"] == 1

    def test_suite_report_to_json(self):
        """测试报告 JSON 序列化。"""
        suite = StabilityTestSuite("JSON Test", TestCategory.SOAK)
        suite.add_result(
            CaseResult(name="json_t1", category="soak", status=TestStatus.PASSED)
        )

        report = suite.finish()
        json_str = report.to_json()

        assert isinstance(json_str, str)
        data = json.loads(json_str)
        assert data["suite_name"] == "JSON Test"
        assert data["category"] == "soak"
        assert data["total_tests"] == 1

    def test_suite_report_to_markdown(self):
        """测试报告 Markdown 生成。"""
        suite = StabilityTestSuite("MD Test", TestCategory.SMOKE)
        suite.add_result(
            CaseResult(name="md_t1", category="smoke", status=TestStatus.PASSED, duration_seconds=0.1)
        )
        suite.add_result(
            CaseResult(
                name="md_t2",
                category="smoke",
                status=TestStatus.FAILED,
                duration_seconds=0.2,
                error_type="AssertionError",
            )
        )

        report = suite.finish()
        md = report.to_markdown()

        assert "# MD Test" in md
        assert "通过率" in md
        assert "50.0%" in md
        assert "错误分布" in md


class TestMeasureLatency:
    """延迟测量工具测试。"""

    def test_measure_latency_basic(self):
        """基本延迟测量。"""

        def fast_func():
            time.sleep(0.001)

        result = measure_latency(fast_func, iterations=10)

        assert result["iterations"] == 10
        assert result["success_count"] == 10
        assert result["error_count"] == 0
        assert result["success_rate"] == 100.0
        assert result["avg_ms"] > 0
        assert result["min_ms"] > 0
        assert result["max_ms"] >= result["min_ms"]
        assert result["throughput_per_second"] > 0

    def test_measure_latency_with_errors(self):
        """带错误的延迟测量。"""
        call_count = 0

        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count % 3 == 0:
                raise ValueError("transient error")

        result = measure_latency(flaky_func, iterations=9)

        assert result["iterations"] == 9
        assert result["error_count"] == 3
        assert result["success_count"] == 6
        assert result["success_rate"] == pytest.approx(66.67, rel=0.01)

    def test_measure_latency_zero_success(self):
        """零成功的延迟测量。"""

        def always_fail():
            raise RuntimeError("always fails")

        result = measure_latency(always_fail, iterations=5)

        assert result["success_count"] == 0
        assert result["error_count"] == 5
        assert result["success_rate"] == 0.0
        assert result["avg_ms"] == 0.0


class TestHistoricalComparator:
    """历史结果对比器测试。"""

    def test_comparator_no_history(self, tmp_path):
        """无历史数据时的对比。"""
        comparator = HistoricalComparator(tmp_path)

        current = SuiteReport(
            suite_name="Current",
            category=TestCategory.SMOKE,
            start_time=time.time(),
            end_time=time.time() + 10,
            total_tests=10,
            passed_tests=9,
        )

        result = comparator.compare(current, TestCategory.SMOKE)
        assert result["has_history"] is False

    def test_comparator_with_history(self, tmp_path):
        """有历史数据时的对比。"""
        # 手动创建两个不同时间戳的历史报告文件
        import os

        suite1 = StabilityTestSuite("Hist1", TestCategory.SMOKE)
        suite1.add_result(
            CaseResult(name="t1", category="smoke", status=TestStatus.PASSED)
        )
        suite1.add_result(
            CaseResult(name="t2", category="smoke", status=TestStatus.FAILED)
        )
        report1 = suite1.finish()

        suite2 = StabilityTestSuite("Hist2", TestCategory.SMOKE)
        suite2.add_result(
            CaseResult(name="t1", category="smoke", status=TestStatus.PASSED)
        )
        suite2.add_result(
            CaseResult(name="t2", category="smoke", status=TestStatus.PASSED)
        )
        report2 = suite2.finish()

        # 直接写入两个不同名称的文件
        file1 = tmp_path / "report_smoke_20240101_000001.json"
        file2 = tmp_path / "report_smoke_20240102_000002.json"
        file1.write_text(report1.to_json(), encoding="utf-8")
        file2.write_text(report2.to_json(), encoding="utf-8")

        # 当前报告
        current = SuiteReport(
            suite_name="Current",
            category=TestCategory.SMOKE,
            start_time=time.time(),
            end_time=time.time() + 5,
            total_tests=10,
            passed_tests=9,
        )

        comparator = HistoricalComparator(tmp_path)
        result = comparator.compare(current, TestCategory.SMOKE)

        assert result["has_history"] is True
        assert result["history_count"] >= 2
        assert "pass_rate_delta" in result
        assert "trend" in result


class TestStabilitySuiteSaveReport:
    """测试报告保存功能。"""

    def test_save_json_report(self, tmp_path):
        """保存 JSON 报告。"""
        suite = StabilityTestSuite("Save Test", TestCategory.SMOKE)
        suite.add_result(
            CaseResult(name="save_t1", category="smoke", status=TestStatus.PASSED)
        )

        paths = suite.save_report(tmp_path, ["json"])

        assert len(paths) == 1
        assert paths[0].suffix == ".json"
        assert paths[0].exists()
        assert "report_smoke_" in paths[0].name

    def test_save_markdown_report(self, tmp_path):
        """保存 Markdown 报告。"""
        suite = StabilityTestSuite("MD Save", TestCategory.BASIC)
        suite.add_result(
            CaseResult(name="md_save_t1", category="basic", status=TestStatus.PASSED)
        )

        paths = suite.save_report(tmp_path, ["markdown"])

        assert len(paths) == 1
        assert paths[0].suffix == ".md"
        assert paths[0].exists()

    def test_save_multiple_formats(self, tmp_path):
        """保存多种格式报告。"""
        suite = StabilityTestSuite("Multi Save", TestCategory.STRESS)
        suite.add_result(
            CaseResult(name="multi_t1", category="stress", status=TestStatus.PASSED)
        )

        paths = suite.save_report(tmp_path, ["json", "markdown"])

        assert len(paths) == 2
        suffixes = {p.suffix for p in paths}
        assert ".json" in suffixes
        assert ".md" in suffixes
