"""
AE 稳定性测试套件
================

生产级 After Effects 稳定性与基准测试体系。

测试分类：
- smoke: 烟雾测试，快速验证基本功能（30秒内）
- process_lifecycle: 进程生命周期测试
- bridge_stability: Bridge 通信稳定性测试
- ae_operations: AE 操作稳定性测试
- stress: 压力测试
- soak: 耐久测试
"""

from .stability_models import (
    CaseResult,
    HistoricalComparator,
    StabilityTestSuite,
    SuiteReport,
    TestCategory,
    TestStatus,
    measure_latency,
)

__all__ = [
    "CaseResult",
    "HistoricalComparator",
    "StabilityTestSuite",
    "SuiteReport",
    "TestCategory",
    "TestStatus",
    "measure_latency",
]
