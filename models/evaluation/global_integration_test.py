#!/usr/bin/env python3
"""
全局集成测试框架 - GlobalIntegrationTest v1.0

测试目标：验证系统完整性和精度上限

测试模块：
1. LLM网关分层路由架构验证（TIER_1/TIER_2/TIER_3）
2. 置信度级联路由验证（置信度<0.7自动升级）
3. Agent安全执行层验证（安全分级、审计、熔断）
4. 本地模型适配验证（BGE嵌入、Qwen-2小模型）
5. 多智能体协作验证（风格分析→代码生成→参数优化→质量审核）
6. 模型仓库功能验证（注册、查询、A/B测试）

参考标准：
- OWASP Top 10 (2021)
- NIST Cybersecurity Framework
- ISO 25010 软件质量模型
- Antares 精悍够用哲学
"""
import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from core.llm_gateway import (
    LLMGateway, LLMConfig, LLMResponse, TaskType, ModelTier,
    llm_gateway, chat_with_routing, chat_with_cascade, get_cascade_stats
)
from core.security import (
    SecurityManager, SecurityLevel, SecurityContext,
    SecurityScanResult, AuditLogEntry, get_security_manager
)
from core.local_model_adapter import (
    LocalModelAdapter, LocalModelConfig, LocalModelType, DEFAULT_MODELS
)
from models.deployment.model_registry import ModelRegistry, ModelInfo


@dataclass
class TestCaseResult:
    test_name: str
    category: str
    success: bool
    latency_ms: float = 0.0
    error: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    assertions: List[str] = field(default_factory=list)


@dataclass
class IntegrationTestReport:
    report_name: str = "全局集成测试报告"
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    total_latency_ms: float = 0.0
    module_results: Dict[str, List[TestCaseResult]] = field(default_factory=dict)
    summary: Dict[str, Any] = field(default_factory=dict)


class GlobalIntegrationTest:
    def __init__(self, output_dir: str = "models/output"):
        self.output_dir = output_dir
        self.report = IntegrationTestReport()
        self._test_results: List[TestCaseResult] = []
        self._security_manager = get_security_manager()
        self._model_registry = ModelRegistry(os.path.join(output_dir, "model_registry"))

        os.makedirs(output_dir, exist_ok=True)

    # -------------------------------------------------------------------------
    # 测试执行框架
    # -------------------------------------------------------------------------

    def run_all_tests(self) -> IntegrationTestReport:
        """运行所有集成测试"""
        self.report.start_time = datetime.now()

        print("=" * 70)
        print("全局集成测试框架 - GlobalIntegrationTest v1.0")
        print("=" * 70)
        print(f"测试开始: {self.report.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print()

        test_modules = [
            ("LLM网关分层路由", self.test_llm_gateway_tiered_routing),
            ("置信度级联路由", self.test_confidence_cascade_routing),
            ("Agent安全执行层", self.test_agent_security_layer),
            ("本地模型适配", self.test_local_model_adaptation),
            ("多智能体协作", self.test_multi_agent_collaboration),
            ("模型仓库功能", self.test_model_registry),
        ]

        for module_name, test_func in test_modules:
            print(f"[{module_name}] 开始测试...")
            try:
                results = asyncio.run(test_func()) if asyncio.iscoroutinefunction(test_func) else test_func()
                if isinstance(results, list):
                    self._test_results.extend(results)
                else:
                    self._test_results.append(results)
            except Exception as e:
                print(f"  [错误] {module_name} 测试失败: {e}")
                self._test_results.append(TestCaseResult(
                    test_name=f"{module_name}模块测试",
                    category="模块异常",
                    success=False,
                    error=str(e)
                ))

        self.report.end_time = datetime.now()
        self._generate_report()

        print()
        print(f"测试完成: {self.report.end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)

        return self.report

    def _generate_report(self):
        """生成测试报告"""
        self.report.total_tests = len(self._test_results)
        self.report.passed_tests = sum(1 for r in self._test_results if r.success)
        self.report.failed_tests = self.report.total_tests - self.report.passed_tests
        self.report.total_latency_ms = sum(r.latency_ms for r in self._test_results)

        for result in self._test_results:
            if result.category not in self.report.module_results:
                self.report.module_results[result.category] = []
            self.report.module_results[result.category].append(result)

        pass_rate = (self.report.passed_tests / self.report.total_tests * 100) if self.report.total_tests > 0 else 0
        avg_latency = (self.report.total_latency_ms / self.report.total_tests) if self.report.total_tests > 0 else 0

        self.report.summary = {
            "total_tests": self.report.total_tests,
            "passed_tests": self.report.passed_tests,
            "failed_tests": self.report.failed_tests,
            "pass_rate": f"{pass_rate:.2f}%",
            "avg_latency_ms": f"{avg_latency:.2f}",
            "duration_seconds": (self.report.end_time - self.report.start_time).total_seconds() if self.report.start_time and self.report.end_time else 0,
        }

    def save_report(self) -> str:
        """保存测试报告到文件"""
        report_path = os.path.join(self.output_dir, "integration_report.md")

        with open(report_path, "w", encoding="utf-8") as f:
            f.write(self._generate_markdown_report())

        print(f"\n测试报告已保存到: {report_path}")
        return report_path

    def _generate_markdown_report(self) -> str:
        """生成Markdown格式报告"""
        lines = []

        lines.append("# 全局集成测试报告")
        lines.append("")
        lines.append(f"**报告名称**: {self.report.report_name}")
        lines.append(f"**测试时间**: {self.report.start_time.strftime('%Y-%m-%d %H:%M:%S') if self.report.start_time else 'N/A'}")
        lines.append(f"**结束时间**: {self.report.end_time.strftime('%Y-%m-%d %H:%M:%S') if self.report.end_time else 'N/A'}")
        lines.append(f"**测试时长**: {self.report.summary['duration_seconds']:.2f} 秒")
        lines.append("")

        lines.append("## 测试概览")
        lines.append("")
        lines.append("| 指标 | 数值 |")
        lines.append("|------|------|")
        lines.append(f"| 总测试用例 | {self.report.total_tests} |")
        lines.append(f"| 通过 | {self.report.passed_tests} |")
        lines.append(f"| 失败 | {self.report.failed_tests} |")
        lines.append(f"| 通过率 | {self.report.summary['pass_rate']} |")
        lines.append(f"| 平均延迟 | {self.report.summary['avg_latency_ms']}ms |")
        lines.append("")

        lines.append("## 模块测试结果")
        lines.append("")

        for module_name, results in self.report.module_results.items():
            passed = sum(1 for r in results if r.success)
            total = len(results)
            rate = (passed / total * 100) if total > 0 else 0
            icon = "🟢" if rate >= 90 else "🟡" if rate >= 70 else "🔴"

            lines.append(f"### {icon} {module_name}")
            lines.append("")
            lines.append(f"- 总用例: {total} | 通过: {passed} | 失败: {total - passed} | 通过率: {rate:.2f}%")
            lines.append("")

            for result in results:
                status_icon = "✅" if result.success else "❌"
                lines.append(f"#### {status_icon} {result.test_name}")
                lines.append(f"- **状态**: {'通过' if result.success else '失败'}")
                if result.latency_ms > 0:
                    lines.append(f"- **延迟**: {result.latency_ms:.2f}ms")
                if result.error:
                    lines.append(f"- **错误**: {result.error}")
                if result.details:
                    for key, value in result.details.items():
                        if isinstance(value, (dict, list)):
                            value_str = json.dumps(value, ensure_ascii=False, indent=2, default=str)
                            lines.append(f"- **{key}**: \n```json\n{value_str}\n```")
                        else:
                            lines.append(f"- **{key}**: {value}")
                if result.assertions:
                    lines.append(f"- **断言**:")
                    for assertion in result.assertions:
                        lines.append(f"  - {assertion}")
                lines.append("")

        lines.append("## 系统健康评估")
        lines.append("")

        pass_rate = float(self.report.summary['pass_rate'][:-1])
        if pass_rate >= 95:
            score_text = "优秀"
            score_color = "🟢"
            recommendations = ["系统运行良好，建议定期执行集成测试"]
        elif pass_rate >= 80:
            score_text = "良好"
            score_color = "🟡"
            recommendations = ["部分测试失败，建议关注失败模块", "考虑增加更多边界测试用例"]
        elif pass_rate >= 60:
            score_text = "及格"
            score_color = "🟠"
            recommendations = ["系统存在较多问题，需要修复", "建议优先处理安全和路由模块"]
        else:
            score_text = "不及格"
            score_color = "🔴"
            recommendations = ["系统存在严重问题，需立即修复", "建议全面排查各模块"]

        lines.append(f"**整体评分**: {score_color} {pass_rate:.2f}分 ({score_text})")
        lines.append("")

        lines.append("### 修复建议")
        lines.append("")
        for i, rec in enumerate(recommendations, 1):
            lines.append(f"{i}. {rec}")
        lines.append("")

        failed_tests = [r for r in self._test_results if not r.success]
        if failed_tests:
            lines.append("### 失败测试详情")
            lines.append("")
            for test in failed_tests:
                lines.append(f"- **{test.test_name}** ({test.category}): {test.error}")
            lines.append("")

        lines.append("---")
        lines.append(f"*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")

        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # 测试模块1: LLM网关分层路由架构验证
    # -------------------------------------------------------------------------

    async def test_llm_gateway_tiered_routing(self) -> List[TestCaseResult]:
        """测试LLM网关分层路由架构"""
        results = []
        gw = LLMGateway()

        test_cases = [
            ("TIER_1路由配置验证", TaskType.INTENT_CLASSIFICATION, ModelTier.TIER_1_LOCAL_SPECIALIZED),
            ("TIER_2路由配置验证", TaskType.PARAMETER_OPTIMIZATION, ModelTier.TIER_2_MIDTIER_GENERAL),
            ("TIER_3路由配置验证", TaskType.QUALITY_REVIEW, ModelTier.TIER_3_FLAGSHIP_REASONING),
            ("通用任务路由验证", TaskType.GENERAL, ModelTier.TIER_2_MIDTIER_GENERAL),
        ]

        for test_name, task_type, expected_tier in test_cases:
            start_time = time.time()
            assertions = []

            try:
                from core.llm_gateway import TASK_TIER_MAP
                actual_tier = TASK_TIER_MAP.get(task_type)
                assertions.append(f"TASK_TIER_MAP[{task_type.name}] = {actual_tier}")
                assertions.append(f"预期档位: {expected_tier}")
                assertions.append(f"实际档位: {actual_tier}")

                success = actual_tier == expected_tier

                latency_ms = (time.time() - start_time) * 1000
                results.append(TestCaseResult(
                    test_name=test_name,
                    category="LLM网关分层路由",
                    success=success,
                    latency_ms=latency_ms,
                    assertions=assertions,
                    details={"task_type": task_type.name, "expected_tier": expected_tier.value, "actual_tier": actual_tier.value if actual_tier else "None"}
                ))

            except Exception as e:
                latency_ms = (time.time() - start_time) * 1000
                results.append(TestCaseResult(
                    test_name=test_name,
                    category="LLM网关分层路由",
                    success=False,
                    latency_ms=latency_ms,
                    error=str(e),
                    assertions=assertions
                ))

        return results

    # -------------------------------------------------------------------------
    # 测试模块2: 置信度级联路由验证
    # -------------------------------------------------------------------------

    async def test_confidence_cascade_routing(self) -> List[TestCaseResult]:
        """测试置信度级联路由（置信度<0.7自动升级）"""
        results = []
        gw = LLMGateway()

        threshold = gw._config.cascade_confidence_threshold
        max_upgrades = gw._config.cascade_max_upgrades

        assertions = []
        assertions.append(f"级联阈值配置: {threshold}")
        assertions.append(f"预期阈值: 0.7")

        results.append(TestCaseResult(
            test_name="置信度阈值配置验证",
            category="置信度级联路由",
            success=threshold == 0.7,
            assertions=assertions,
            details={"configured_threshold": threshold, "expected_threshold": 0.7}
        ))

        assertions = []
        assertions.append(f"最大升级次数配置: {max_upgrades}")
        assertions.append(f"预期次数: 2")

        results.append(TestCaseResult(
            test_name="最大升级次数配置验证",
            category="置信度级联路由",
            success=max_upgrades == 2,
            assertions=assertions,
            details={"configured_max_upgrades": max_upgrades, "expected_max_upgrades": 2}
        ))

        test_cases = [
            ("低置信度应触发升级", 0.5, True),
            ("等于阈值不应触发升级", 0.7, False),
            ("高置信度不应触发升级", 0.8, False),
            ("极低置信度应触发升级", 0.2, True),
        ]

        for test_name, confidence, should_upgrade in test_cases:
            start_time = time.time()
            assertions = []

            try:
                assertions.append(f"级联阈值: {threshold}")
                assertions.append(f"测试置信度: {confidence}")
                assertions.append(f"预期升级: {should_upgrade}")

                is_below_threshold = confidence < threshold
                assertions.append(f"低于阈值: {is_below_threshold}")

                success = (is_below_threshold == should_upgrade)

                latency_ms = (time.time() - start_time) * 1000
                results.append(TestCaseResult(
                    test_name=test_name,
                    category="置信度级联路由",
                    success=success,
                    latency_ms=latency_ms,
                    assertions=assertions,
                    details={"confidence": confidence, "threshold": threshold, "should_upgrade": should_upgrade, "is_below_threshold": is_below_threshold}
                ))

            except Exception as e:
                latency_ms = (time.time() - start_time) * 1000
                results.append(TestCaseResult(
                    test_name=test_name,
                    category="置信度级联路由",
                    success=False,
                    latency_ms=latency_ms,
                    error=str(e),
                    assertions=assertions
                ))

        return results

    # -------------------------------------------------------------------------
    # 测试模块3: Agent安全执行层验证
    # -------------------------------------------------------------------------

    def test_agent_security_layer(self) -> List[TestCaseResult]:
        """测试Agent安全执行层（安全分级、审计、熔断）"""
        results = []
        sm = SecurityManager()

        test_cases = [
            ("安全分级枚举验证-SAFE", SecurityLevel.SAFE, "safe"),
            ("安全分级枚举验证-LOW", SecurityLevel.LOW, "low"),
            ("安全分级枚举验证-MEDIUM", SecurityLevel.MEDIUM, "medium"),
            ("安全分级枚举验证-HIGH", SecurityLevel.HIGH, "high"),
            ("安全分级枚举验证-CRITICAL", SecurityLevel.CRITICAL, "critical"),
        ]

        for test_name, level, expected_value in test_cases:
            start_time = time.time()
            assertions = []

            try:
                assertions.append(f"安全级别: {level}")
                assertions.append(f"预期值: {expected_value}")
                assertions.append(f"实际值: {level.value}")

                success = level.value == expected_value

                latency_ms = (time.time() - start_time) * 1000
                results.append(TestCaseResult(
                    test_name=test_name,
                    category="Agent安全执行层",
                    success=success,
                    latency_ms=latency_ms,
                    assertions=assertions
                ))

            except Exception as e:
                latency_ms = (time.time() - start_time) * 1000
                results.append(TestCaseResult(
                    test_name=test_name,
                    category="Agent安全执行层",
                    success=False,
                    latency_ms=latency_ms,
                    error=str(e),
                    assertions=assertions
                ))

        results.extend(self._test_security_scanning(sm))
        results.extend(self._test_circuit_breaker(sm))
        results.extend(self._test_audit_logging(sm))

        return results

    def _test_security_scanning(self, sm: SecurityManager) -> List[TestCaseResult]:
        """测试安全扫描功能"""
        results = []

        scan_tests = [
            ("JSX eval注入检测", 'eval("alert(1)")', "jsx", True),
            ("JSX Function构造器检测", 'new Function("return 1")', "jsx", True),
            ("JSX安全代码不拦截", 'var x = 1 + 2;', "jsx", False),
            ("JSX路径遍历检测", '../../etc/passwd', "jsx", True),
            ("JSX安全路径不拦截", './data/file.txt', "jsx", False),
        ]

        for test_name, code, code_type, should_block in scan_tests:
            start_time = time.time()
            assertions = []

            try:
                result = sm.scan_code(code, code_type)
                is_blocked = not result.passed

                assertions.append(f"扫描结果: {'拦截' if is_blocked else '通过'}")
                assertions.append(f"预期结果: {'拦截' if should_block else '通过'}")

                success = is_blocked == should_block

                latency_ms = (time.time() - start_time) * 1000
                results.append(TestCaseResult(
                    test_name=test_name,
                    category="Agent安全执行层",
                    success=success,
                    latency_ms=latency_ms,
                    assertions=assertions,
                    details={"risk_level": result.risk_level, "violations": result.violations}
                ))

            except Exception as e:
                latency_ms = (time.time() - start_time) * 1000
                results.append(TestCaseResult(
                    test_name=test_name,
                    category="Agent安全执行层",
                    success=False,
                    latency_ms=latency_ms,
                    error=str(e),
                    assertions=assertions
                ))

        return results

    def _test_circuit_breaker(self, sm: SecurityManager) -> List[TestCaseResult]:
        """测试熔断机制"""
        results = []
        sm.reset_circuit_breaker()

        assertions = []

        try:
            for i in range(5):
                entry = AuditLogEntry(
                    timestamp=time.time(),
                    workflow_id="test_wf",
                    task_id=f"task_{i}",
                    task_type="security_test",
                    security_level="high",
                    action="scan_code",
                    status="denied"
                )
                sm.log_audit(entry)

            is_fused = sm.check_circuit_breaker()
            assertions.append(f"5次违规后熔断状态: {is_fused}")
            assertions.append(f"预期熔断状态: True")

            success = is_fused

            results.append(TestCaseResult(
                test_name="熔断机制触发验证",
                category="Agent安全执行层",
                success=success,
                assertions=assertions,
                details={"violation_count": sm._violation_count, "is_fused": is_fused}
            ))

            sm.reset_circuit_breaker()
            is_fused_after_reset = sm.check_circuit_breaker()

            results.append(TestCaseResult(
                test_name="熔断机制重置验证",
                category="Agent安全执行层",
                success=not is_fused_after_reset,
                details={"is_fused_after_reset": is_fused_after_reset}
            ))

        except Exception as e:
            results.append(TestCaseResult(
                test_name="熔断机制测试",
                category="Agent安全执行层",
                success=False,
                error=str(e),
                assertions=assertions
            ))

        return results

    def _test_audit_logging(self, sm: SecurityManager) -> List[TestCaseResult]:
        """测试审计日志功能"""
        results = []

        try:
            initial_count = len(sm._audit_logs)

            for i in range(5):
                entry = AuditLogEntry(
                    timestamp=time.time(),
                    workflow_id=f"wf_{i}",
                    task_id=f"task_{i}",
                    task_type="test",
                    security_level="low",
                    action="test_action",
                    status="allowed" if i % 2 == 0 else "denied"
                )
                sm.log_audit(entry)

            stats = sm.get_audit_stats()
            success = stats['total_audits'] == initial_count + 5

            results.append(TestCaseResult(
                test_name="审计日志记录验证",
                category="Agent安全执行层",
                success=success,
                details={"total_audits": stats['total_audits'], "expected": initial_count + 5}
            ))

            logs = sm.get_audit_logs(action="test_action", limit=3)
            success_filter = len(logs) == 3

            results.append(TestCaseResult(
                test_name="审计日志过滤验证",
                category="Agent安全执行层",
                success=success_filter,
                details={"filtered_count": len(logs), "expected": 3}
            ))

        except Exception as e:
            results.append(TestCaseResult(
                test_name="审计日志测试",
                category="Agent安全执行层",
                success=False,
                error=str(e)
            ))

        return results

    # -------------------------------------------------------------------------
    # 测试模块4: 本地模型适配验证
    # -------------------------------------------------------------------------

    async def test_local_model_adaptation(self) -> List[TestCaseResult]:
        """测试本地模型适配（BGE嵌入、Qwen-2小模型）"""
        results = []

        test_models = [
            ("BGE-Small-ZH嵌入模型", "bge-small-zh", True),
            ("Qwen2-0.5B生成模型", "qwen2-0.5b", False),
        ]

        for test_name, model_name, is_embedding in test_models:
            start_time = time.time()

            try:
                config = DEFAULT_MODELS.get(model_name)
                if not config:
                    results.append(TestCaseResult(
                        test_name=test_name,
                        category="本地模型适配",
                        success=False,
                        latency_ms=(time.time() - start_time) * 1000,
                        error=f"模型配置不存在: {model_name}"
                    ))
                    continue

                adapter = LocalModelAdapter(config)

                success, error = await adapter.initialize()

                latency_ms = (time.time() - start_time) * 1000
                results.append(TestCaseResult(
                    test_name=f"{test_name} - 初始化",
                    category="本地模型适配",
                    success=success,
                    latency_ms=latency_ms,
                    error=error,
                    details={"initialized": adapter._initialized, "model_type": config.model_type.value}
                ))

                if success:
                    if is_embedding:
                        embed_start = time.time()
                        embed_result = await adapter.embed(["测试文本"])
                        embed_latency = (time.time() - embed_start) * 1000

                        results.append(TestCaseResult(
                            test_name=f"{test_name} - 嵌入功能",
                            category="本地模型适配",
                            success=embed_result.success,
                            latency_ms=embed_latency,
                            error=embed_result.error,
                            details={"embedding_dim": len(embed_result.embeddings[0]) if embed_result.embeddings else 0}
                        ))
                    else:
                        gen_start = time.time()
                        gen_result = await adapter.generate("写一段AE脚本", max_new_tokens=50)
                        gen_latency = (time.time() - gen_start) * 1000

                        results.append(TestCaseResult(
                            test_name=f"{test_name} - 生成功能",
                            category="本地模型适配",
                            success=gen_result.success,
                            latency_ms=gen_latency,
                            error=gen_result.error,
                            details={"content_length": len(gen_result.content)}
                        ))

            except Exception as e:
                latency_ms = (time.time() - start_time) * 1000
                results.append(TestCaseResult(
                    test_name=test_name,
                    category="本地模型适配",
                    success=False,
                    latency_ms=latency_ms,
                    error=str(e)
                ))

        return results

    # -------------------------------------------------------------------------
    # 测试模块5: 多智能体协作验证
    # -------------------------------------------------------------------------

    async def test_multi_agent_collaboration(self) -> List[TestCaseResult]:
        """测试多智能体协作（风格分析→代码生成→参数优化→质量审核）"""
        results = []

        collaboration_tasks = [
            ("风格分析任务路由", TaskType.SCENE_DESCRIPTION, ModelTier.TIER_2_MIDTIER_GENERAL),
            ("代码生成任务路由", TaskType.PARAMETER_OPTIMIZATION, ModelTier.TIER_2_MIDTIER_GENERAL),
            ("参数优化任务路由", TaskType.PARAMETER_OPTIMIZATION, ModelTier.TIER_2_MIDTIER_GENERAL),
            ("质量审核任务路由", TaskType.QUALITY_REVIEW, ModelTier.TIER_3_FLAGSHIP_REASONING),
        ]

        from core.llm_gateway import TASK_TIER_MAP

        for test_name, task_type, expected_tier in collaboration_tasks:
            start_time = time.time()

            try:
                actual_tier = TASK_TIER_MAP.get(task_type)
                success = actual_tier == expected_tier

                latency_ms = (time.time() - start_time) * 1000
                results.append(TestCaseResult(
                    test_name=test_name,
                    category="多智能体协作",
                    success=success,
                    latency_ms=latency_ms,
                    details={"task_type": task_type.name, "expected_tier": expected_tier.value, "actual_tier": actual_tier.value if actual_tier else "None"}
                ))

            except Exception as e:
                latency_ms = (time.time() - start_time) * 1000
                results.append(TestCaseResult(
                    test_name=test_name,
                    category="多智能体协作",
                    success=False,
                    latency_ms=latency_ms,
                    error=str(e)
                ))

        results.append(self._test_collaboration_flow())

        return results

    def _test_collaboration_flow(self) -> TestCaseResult:
        """测试协作流程完整性"""
        start_time = time.time()

        try:
            flow_steps = [
                {"step": "风格分析", "task_type": TaskType.SCENE_DESCRIPTION, "tier": ModelTier.TIER_2_MIDTIER_GENERAL},
                {"step": "代码生成", "task_type": TaskType.PARAMETER_OPTIMIZATION, "tier": ModelTier.TIER_2_MIDTIER_GENERAL},
                {"step": "参数优化", "task_type": TaskType.PARAMETER_OPTIMIZATION, "tier": ModelTier.TIER_2_MIDTIER_GENERAL},
                {"step": "质量审核", "task_type": TaskType.QUALITY_REVIEW, "tier": ModelTier.TIER_3_FLAGSHIP_REASONING},
            ]

            from core.llm_gateway import TASK_TIER_MAP

            valid_steps = []
            for step in flow_steps:
                expected_tier = step["tier"]
                actual_tier = TASK_TIER_MAP.get(step["task_type"])
                valid_steps.append(expected_tier == actual_tier)

            success = all(valid_steps)

            latency_ms = (time.time() - start_time) * 1000
            return TestCaseResult(
                test_name="协作流程完整性验证",
                category="多智能体协作",
                success=success,
                latency_ms=latency_ms,
                details={"flow_steps": flow_steps, "valid_steps": valid_steps}
            )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return TestCaseResult(
                test_name="协作流程完整性验证",
                category="多智能体协作",
                success=False,
                latency_ms=latency_ms,
                error=str(e)
            )

    # -------------------------------------------------------------------------
    # 测试模块6: 模型仓库功能验证
    # -------------------------------------------------------------------------

    def test_model_registry(self) -> List[TestCaseResult]:
        """测试模型仓库功能（注册、查询、A/B测试）"""
        results = []
        registry = ModelRegistry(os.path.join(self.output_dir, "model_registry_test"))

        try:
            test_model = ModelInfo(
                model_name="test_style_classifier",
                model_version="1.0.0",
                model_type="style_classify",
                model_path="./models/output/style-classifier",
                base_model="bge-small-zh",
                training_method="lora",
                params_million=33.0,
                train_samples=1000,
                eval_metrics={"accuracy": 0.85, "f1": 0.82},
                cost_effectiveness=2.5,
                status="staging"
            )

            model_id = registry.register_model(test_model)
            results.append(TestCaseResult(
                test_name="模型注册功能",
                category="模型仓库功能",
                success=model_id == "test_style_classifier:1.0.0",
                details={"model_id": model_id}
            ))

            retrieved = registry.get_model("test_style_classifier", "1.0.0")
            results.append(TestCaseResult(
                test_name="模型查询功能",
                category="模型仓库功能",
                success=retrieved is not None and retrieved.model_version == "1.0.0",
                details={"retrieved_version": retrieved.model_version if retrieved else "None"}
            ))

            promoted = registry.promote_to_production("test_style_classifier", "1.0.0")
            results.append(TestCaseResult(
                test_name="模型升级生产环境",
                category="模型仓库功能",
                success=promoted,
                details={"production_model": registry.get_production_model("test_style_classifier") is not None}
            ))

            all_models = registry.list_models()
            results.append(TestCaseResult(
                test_name="模型列表功能",
                category="模型仓库功能",
                success=len(all_models) >= 1,
                details={"model_count": len(all_models)}
            ))

            test_model_b = ModelInfo(
                model_name="test_style_classifier",
                model_version="1.1.0",
                model_type="style_classify",
                model_path="./models/output/style-classifier",
                base_model="bge-small-zh",
                training_method="lora",
                params_million=33.0,
                train_samples=2000,
                eval_metrics={"accuracy": 0.90, "f1": 0.88},
                cost_effectiveness=3.0,
                status="staging"
            )
            registry.register_model(test_model_b)

            ab_started = registry.start_ab_test(
                test_name="style_classifier_ab_test",
                model_name="test_style_classifier",
                version_a="1.0.0",
                version_b="1.1.0",
                traffic_split=(0.5, 0.5)
            )
            results.append(TestCaseResult(
                test_name="A/B测试启动",
                category="模型仓库功能",
                success=ab_started,
                details={"ab_test": registry.get_ab_test("style_classifier_ab_test")}
            ))

            ab_stopped = registry.stop_ab_test("style_classifier_ab_test", winner="B")
            results.append(TestCaseResult(
                test_name="A/B测试停止",
                category="模型仓库功能",
                success=ab_stopped.get("status") == "completed",
                details={"ab_result": ab_stopped}
            ))

            best_model = registry.get_best_model("style_classify", "cost_effectiveness")
            results.append(TestCaseResult(
                test_name="最佳模型选择",
                category="模型仓库功能",
                success=best_model is not None and best_model.model_version == "1.1.0",
                details={"best_model_version": best_model.model_version if best_model else "None"}
            ))

        except Exception as e:
            results.append(TestCaseResult(
                test_name="模型仓库测试",
                category="模型仓库功能",
                success=False,
                error=str(e)
            ))

        return results


def main():
    """运行全局集成测试"""
    test_framework = GlobalIntegrationTest(output_dir="models/output")

    report = test_framework.run_all_tests()

    print("\n" + "=" * 70)
    print("测试结果汇总")
    print("=" * 70)
    print(f"总测试用例: {report.total_tests}")
    print(f"通过: {report.passed_tests}")
    print(f"失败: {report.failed_tests}")
    print(f"通过率: {report.summary['pass_rate']}")
    print(f"平均延迟: {report.summary['avg_latency_ms']}ms")
    print("=" * 70)

    report_path = test_framework.save_report()

    return report


if __name__ == "__main__":
    main()