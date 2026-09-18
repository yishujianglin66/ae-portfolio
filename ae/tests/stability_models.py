"""
AE 稳定性测试数据模型与工具函数
=================================

提供测试报告、结果数据类和通用工具函数。
"""

from __future__ import annotations

import json
import statistics
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


class Category(str, Enum):
    """测试分类枚举。"""

    __test__ = False

    SMOKE = "smoke"
    BASIC = "basic"
    STRESS = "stress"
    SOAK = "soak"


class Status(str, Enum):
    """测试状态枚举。"""

    __test__ = False

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"
    TIMEOUT = "timeout"


# 保留向后兼容别名
TestCategory = Category
TestStatus = Status


@dataclass
class CaseResult:
    """单个测试用例结果。"""

    name: str
    category: str
    status: TestStatus
    duration_seconds: float = 0.0
    error_message: str | None = None
    error_type: str | None = None
    metrics: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="milliseconds")
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "status": self.status.value,
            "duration_seconds": round(self.duration_seconds, 4),
            "error_message": self.error_message,
            "error_type": self.error_type,
            "metrics": self.metrics,
            "timestamp": self.timestamp,
        }


@dataclass
class SuiteReport:
    """完整测试报告。"""

    suite_name: str
    category: TestCategory
    start_time: float
    end_time: float = 0.0
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    skipped_tests: int = 0
    error_tests: int = 0
    results: list[CaseResult] = field(default_factory=list)
    summary_metrics: dict[str, Any] = field(default_factory=dict)

    @property
    def pass_rate(self) -> float:
        """通过率（百分比）。"""
        if self.total_tests == 0:
            return 0.0
        return (self.passed_tests / self.total_tests) * 100

    @property
    def total_duration(self) -> float:
        """总耗时（秒）。"""
        return self.end_time - self.start_time

    @property
    def avg_duration(self) -> float:
        """平均测试耗时（秒）。"""
        completed = [
            r
            for r in self.results
            if r.status
            in (TestStatus.PASSED, TestStatus.FAILED, TestStatus.ERROR)
        ]
        if not completed:
            return 0.0
        return statistics.mean(r.duration_seconds for r in completed)

    @property
    def error_distribution(self) -> dict[str, int]:
        """错误类型分布。"""
        dist: dict[str, int] = {}
        for r in self.results:
            if r.status == TestStatus.FAILED and r.error_type:
                dist[r.error_type] = dist.get(r.error_type, 0) + 1
        return dist

    @property
    def latency_stats(self) -> dict[str, float]:
        """延迟统计（从 metrics 中聚合）。"""
        all_latencies: list[float] = []
        for r in self.results:
            if "latency_ms" in r.metrics:
                all_latencies.append(r.metrics["latency_ms"])
        if not all_latencies:
            return {}
        sorted_lat = sorted(all_latencies)
        return {
            "min_ms": min(all_latencies),
            "max_ms": max(all_latencies),
            "avg_ms": statistics.mean(all_latencies),
            "median_ms": statistics.median(all_latencies),
            "p95_ms": sorted_lat[int(len(sorted_lat) * 0.95)],
            "p99_ms": sorted_lat[int(len(sorted_lat) * 0.99)],
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "suite_name": self.suite_name,
            "category": self.category.value,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "total_duration": self.total_duration,
            "total_tests": self.total_tests,
            "passed_tests": self.passed_tests,
            "failed_tests": self.failed_tests,
            "skipped_tests": self.skipped_tests,
            "error_tests": self.error_tests,
            "pass_rate": self.pass_rate,
            "avg_duration": self.avg_duration,
            "error_distribution": self.error_distribution,
            "latency_stats": self.latency_stats,
            "summary_metrics": self.summary_metrics,
            "results": [r.to_dict() for r in self.results],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def to_markdown(self) -> str:
        """生成 Markdown 格式报告。"""
        lines = [
            f"# {self.suite_name} 测试报告",
            "",
            f"**分类**: {self.category.value}",
            f"**开始时间**: {datetime.fromtimestamp(self.start_time).strftime('%Y-%m-%d %H:%M:%S')}",
            f"**结束时间**: {datetime.fromtimestamp(self.end_time).strftime('%Y-%m-%d %H:%M:%S')}",
            f"**总耗时**: {self.total_duration:.2f}s",
            "",
            "## 概览",
            "",
            "| 指标 | 值 |",
            "|------|-----|",
            f"| 总用例数 | {self.total_tests} |",
            f"| ✅ 通过 | {self.passed_tests} |",
            f"| ❌ 失败 | {self.failed_tests} |",
            f"| ⏭️ 跳过 | {self.skipped_tests} |",
            f"| ⚠️ 错误 | {self.error_tests} |",
            f"| **通过率** | **{self.pass_rate:.1f}%** |",
            f"| 平均耗时 | {self.avg_duration:.2f}s |",
            "",
        ]

        if self.latency_stats:
            lines.extend([
                "## 延迟统计",
                "",
                "| 指标 | 值 (ms) |",
                "|------|---------|",
                f"| 最小 | {self.latency_stats['min_ms']:.2f} |",
                f"| 平均 | {self.latency_stats['avg_ms']:.2f} |",
                f"| 中位 | {self.latency_stats['median_ms']:.2f} |",
                f"| P95 | {self.latency_stats['p95_ms']:.2f} |",
                f"| P99 | {self.latency_stats['p99_ms']:.2f} |",
                f"| 最大 | {self.latency_stats['max_ms']:.2f} |",
                "",
            ])

        if self.error_distribution:
            lines.extend([
                "## 错误分布",
                "",
                "| 错误类型 | 数量 |",
                "|----------|------|",
            ])
            for err_type, count in sorted(
                self.error_distribution.items(), key=lambda x: -x[1]
            ):
                lines.append(f"| {err_type} | {count} |")
            lines.append("")

        lines.extend([
            "## 详细结果",
            "",
            "| 状态 | 用例名 | 分类 | 耗时(s) |",
            "|------|--------|------|---------|",
        ])
        for r in self.results:
            status_icon = {
                TestStatus.PASSED: "✅",
                TestStatus.FAILED: "❌",
                TestStatus.SKIPPED: "⏭️",
                TestStatus.ERROR: "⚠️",
                TestStatus.TIMEOUT: "⏰",
            }.get(r.status, "❓")
            lines.append(
                f"| {status_icon} | {r.name} | {r.category} | {r.duration_seconds:.2f} |"
            )

        return "\n".join(lines)


class StabilityTestSuite:
    """稳定性测试套件。"""

    def __init__(self, name: str, category: TestCategory) -> None:
        self.name = name
        self.category = category
        self.report = SuiteReport(
            suite_name=name,
            category=category,
            start_time=time.time(),
        )

    def add_result(self, result: CaseResult) -> None:
        self.report.results.append(result)
        self.report.total_tests += 1
        if result.status == TestStatus.PASSED:
            self.report.passed_tests += 1
        elif result.status == TestStatus.FAILED:
            self.report.failed_tests += 1
        elif result.status == TestStatus.SKIPPED:
            self.report.skipped_tests += 1
        elif result.status == TestStatus.ERROR:
            self.report.error_tests += 1

    def finish(self) -> SuiteReport:
        self.report.end_time = time.time()
        return self.report

    def save_report(self, output_dir: Path, formats: list[str]) -> list[Path]:
        """保存报告到多种格式。"""
        output_dir.mkdir(parents=True, exist_ok=True)
        report = self.finish()
        paths: list[Path] = []

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if "json" in formats:
            path = output_dir / f"report_{self.category.value}_{timestamp}.json"
            path.write_text(report.to_json(), encoding="utf-8")
            paths.append(path)

        if "markdown" in formats or "md" in formats:
            path = output_dir / f"report_{self.category.value}_{timestamp}.md"
            path.write_text(report.to_markdown(), encoding="utf-8")
            paths.append(path)

        return paths


def measure_latency(
    func: Callable[[], Any],
    iterations: int = 100,
) -> dict[str, Any]:
    """测量函数执行延迟。

    Args:
        func: 要测量的函数
        iterations: 迭代次数

    Returns:
        延迟统计字典
    """
    durations: list[float] = []
    errors = 0
    start_total = time.time()

    for _ in range(iterations):
        try:
            t0 = time.time()
            func()
            durations.append(time.time() - t0)
        except Exception:
            errors += 1

    total_time = time.time() - start_total
    success_count = len(durations)
    success_rate = (success_count / iterations) * 100 if iterations > 0 else 0

    if not durations:
        return {
            "iterations": iterations,
            "success_count": 0,
            "error_count": errors,
            "success_rate": 0.0,
            "total_time_s": total_time,
            "avg_ms": 0.0,
            "min_ms": 0.0,
            "max_ms": 0.0,
            "median_ms": 0.0,
            "p95_ms": 0.0,
            "p99_ms": 0.0,
            "throughput_per_second": 0.0,
        }

    sorted_durations = sorted(durations)
    durations_ms = [d * 1000 for d in sorted_durations]

    return {
        "iterations": iterations,
        "success_count": success_count,
        "error_count": errors,
        "success_rate": success_rate,
        "total_time_s": total_time,
        "avg_ms": statistics.mean(durations_ms),
        "min_ms": durations_ms[0],
        "max_ms": durations_ms[-1],
        "median_ms": statistics.median(durations_ms),
        "p95_ms": durations_ms[int(len(durations_ms) * 0.95)],
        "p99_ms": durations_ms[int(len(durations_ms) * 0.99)],
        "throughput_per_second": success_count / total_time if total_time > 0 else 0,
    }


class HistoricalComparator:
    """历史结果对比器。"""

    def __init__(self, history_dir: Path) -> None:
        self.history_dir = history_dir

    def load_history(self, category: TestCategory) -> list[SuiteReport]:
        """加载某分类的历史报告。"""
        reports: list[SuiteReport] = []
        pattern = f"report_{category.value}_*.json"
        for path in sorted(self.history_dir.glob(pattern)):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                # 简单重建（不完整重建，只用于趋势对比）
                report = SuiteReport(
                    suite_name=data.get("suite_name", "unknown"),
                    category=TestCategory(data.get("category", category.value)),
                    start_time=data.get("start_time", 0),
                    end_time=data.get("end_time", 0),
                    total_tests=data.get("total_tests", 0),
                    passed_tests=data.get("passed_tests", 0),
                    failed_tests=data.get("failed_tests", 0),
                    skipped_tests=data.get("skipped_tests", 0),
                    error_tests=data.get("error_tests", 0),
                    summary_metrics=data.get("summary_metrics", {}),
                )
                reports.append(report)
            except Exception:
                continue
        return reports

    def compare(self, current: SuiteReport, category: TestCategory) -> dict[str, Any]:
        """对比当前报告与历史数据。"""
        history = self.load_history(category)
        if not history:
            return {"has_history": False, "message": "无历史数据"}

        avg_pass_rate = statistics.mean(r.pass_rate for r in history)
        avg_duration = statistics.mean(r.total_duration for r in history)

        return {
            "has_history": True,
            "history_count": len(history),
            "current_pass_rate": current.pass_rate,
            "avg_history_pass_rate": avg_pass_rate,
            "pass_rate_delta": current.pass_rate - avg_pass_rate,
            "current_duration": current.total_duration,
            "avg_history_duration": avg_duration,
            "duration_delta": current.total_duration - avg_duration,
            "trend": (
                "improving"
                if current.pass_rate >= avg_pass_rate
                else "declining"
            ),
        }
