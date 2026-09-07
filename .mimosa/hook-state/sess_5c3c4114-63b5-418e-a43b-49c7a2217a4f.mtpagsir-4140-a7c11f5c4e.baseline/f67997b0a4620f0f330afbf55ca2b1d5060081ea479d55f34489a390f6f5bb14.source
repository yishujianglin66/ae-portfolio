#!/usr/bin/env python3
"""
安全执行层测试框架 - SecurityTestFramework v1.0

测试目标：
1. JSX代码注入防护（eval、executeScript、file系统操作）
2. Shell命令注入防护
3. 路径遍历攻击防护
4. 无限循环DoS攻击防护
5. 资源耗尽攻击防护
6. 安全执行层输出扫描机制
7. 熔断机制验证
8. Multi-Agent Orchestrator安全管理功能

参考标准：
- OWASP Top 10 (2021)
- NIST Cybersecurity Framework
- AWS Well-Architected Security Pillar
"""
import os
import sys
import re
import time
import threading
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from core.security import (
    SecurityManager, SecurityLevel, SecurityContext,
    SecurityScanResult, PermissionType, AuditLogEntry
)


@dataclass
class SecurityTestCase:
    test_name: str
    category: str
    attack_type: str
    payload: str
    code_type: str = "jsx"
    expected_block: bool = True
    description: str = ""


@dataclass
class TestResult:
    test_name: str
    category: str
    attack_type: str
    payload: str
    is_blocked: bool
    expected_block: bool
    success: bool
    scan_result: Optional[SecurityScanResult] = None
    response: str = ""
    error: Optional[str] = None
    execution_time: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SecurityTestSuite:
    suite_name: str = "JSX Security Execution Layer Test Suite"
    tests: List[TestResult] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    blocked_attacks: int = 0
    allowed_attacks: int = 0


class SecurityTestFramework:
    def __init__(self):
        self.security_manager = SecurityManager()
        self.test_cases: List[SecurityTestCase] = []
        self.test_results: List[TestResult] = []
        self._load_test_cases()

    def _load_test_cases(self):
        self.test_cases = [
            # ========== JSX Code Injection Tests ==========
            SecurityTestCase(
                test_name="JSX eval injection",
                category="JSX Code Injection",
                attack_type="eval",
                payload='<div>{eval("alert(document.cookie)")}</div>',
                expected_block=True,
                description="检测JSX中嵌入的eval函数调用"
            ),
            SecurityTestCase(
                test_name="JSX Function constructor injection",
                category="JSX Code Injection",
                attack_type="Function",
                payload='<div>{new Function("return process.env")()}</div>',
                expected_block=True,
                description="检测Function构造函数注入"
            ),
            SecurityTestCase(
                test_name="JSX execCommand injection",
                category="JSX Code Injection",
                attack_type="execCommand",
                payload='<div>{document.execCommand("SaveAs")}</div>',
                expected_block=True,
                description="检测execCommand调用"
            ),
            SecurityTestCase(
                test_name="JSX app.system access",
                category="JSX Code Injection",
                attack_type="system_access",
                payload='<div>{app.system.executeScript("rm -rf /")}</div>',
                expected_block=True,
                description="检测app.system访问"
            ),
            SecurityTestCase(
                test_name="JSX File write operation",
                category="JSX Code Injection",
                attack_type="file_write",
                payload='<div>{new File("C:\\\\evil.txt", "w")}</div>',
                expected_block=True,
                description="检测文件写入操作"
            ),
            SecurityTestCase(
                test_name="JSX Folder.fs access",
                category="JSX Code Injection",
                attack_type="folder_access",
                payload='<div>{Folder.fs.readFolder("C:\\\\")}</div>',
                expected_block=True,
                description="检测文件夹系统访问"
            ),
            SecurityTestCase(
                test_name="JSX safe expression",
                category="JSX Code Injection",
                attack_type="safe",
                payload='<div>{2 + 2}</div>',
                expected_block=False,
                description="安全的JSX表达式不应被拦截"
            ),
            SecurityTestCase(
                test_name="JSX safe function call",
                category="JSX Code Injection",
                attack_type="safe",
                payload='<Button onClick={() => setCount(c => c + 1)}>Increment</Button>',
                expected_block=False,
                description="安全的事件处理函数不应被拦截"
            ),

            # ========== Shell Command Injection Tests ==========
            SecurityTestCase(
                test_name="Shell rm -rf injection",
                category="Shell Command Injection",
                attack_type="rm_rf",
                payload='<div>{`rm -rf /`}</div>',
                code_type="jsx",
                expected_block=True,
                description="检测危险的rm -rf命令"
            ),
            SecurityTestCase(
                test_name="Shell format command injection",
                category="Shell Command Injection",
                attack_type="format",
                payload='<div>{`format C:`}</div>',
                code_type="jsx",
                expected_block=True,
                description="检测格式化命令"
            ),
            SecurityTestCase(
                test_name="Shell del /s/q injection",
                category="Shell Command Injection",
                attack_type="del",
                payload='<div>{`del /s/q C:\\\\*.*`}</div>',
                code_type="jsx",
                expected_block=True,
                description="检测危险删除命令"
            ),
            SecurityTestCase(
                test_name="Shell reg add injection",
                category="Shell Command Injection",
                attack_type="reg_add",
                payload='<div>{`reg add HKLM\\\\SYSTEM`}</div>',
                code_type="jsx",
                expected_block=True,
                description="检测注册表修改命令"
            ),
            SecurityTestCase(
                test_name="Shell shutdown /s injection",
                category="Shell Command Injection",
                attack_type="shutdown",
                payload='<div>{`shutdown /s /f`}</div>',
                code_type="jsx",
                expected_block=True,
                description="检测关机命令"
            ),
            SecurityTestCase(
                test_name="Shell pipe injection",
                category="Shell Command Injection",
                attack_type="pipe",
                payload='<div>{`ls -la | cat /etc/passwd`}</div>',
                code_type="jsx",
                expected_block=True,
                description="检测管道命令注入"
            ),
            SecurityTestCase(
                test_name="Shell semicolon injection",
                category="Shell Command Injection",
                attack_type="semicolon",
                payload='<div>{`echo hello; rm -rf /`}</div>',
                code_type="jsx",
                expected_block=True,
                description="检测分号命令分隔"
            ),
            SecurityTestCase(
                test_name="Shell safe string",
                category="Shell Command Injection",
                attack_type="safe",
                payload='<div>{`Hello World`}</div>',
                code_type="jsx",
                expected_block=False,
                description="安全的字符串模板不应被拦截"
            ),

            # ========== Path Traversal Tests ==========
            SecurityTestCase(
                test_name="Path traversal ../../",
                category="Path Traversal Attack",
                attack_type="double_dot",
                payload='<div>{require("fs").readFileSync("../../../etc/passwd")}</div>',
                code_type="jsx",
                expected_block=True,
                description="检测经典路径遍历模式"
            ),
            SecurityTestCase(
                test_name="Path traversal URL encoded",
                category="Path Traversal Attack",
                attack_type="url_encoded",
                payload='<div>{require("fs").readFileSync("%2e%2e%2fetc%2fpasswd")}</div>',
                code_type="jsx",
                expected_block=True,
                description="检测URL编码的路径遍历"
            ),
            SecurityTestCase(
                test_name="Path traversal Windows C:\\",
                category="Path Traversal Attack",
                attack_type="windows_absolute",
                payload='<div>{require("fs").readFileSync("C:\\\\Windows\\\\System32\\\\config\\\\sam")}</div>',
                code_type="jsx",
                expected_block=True,
                description="检测Windows绝对路径访问"
            ),
            SecurityTestCase(
                test_name="Path traversal /etc/passwd",
                category="Path Traversal Attack",
                attack_type="etc_passwd",
                payload='<div>{require("fs").readFileSync("/etc/passwd")}</div>',
                code_type="jsx",
                expected_block=True,
                description="检测敏感文件访问"
            ),
            SecurityTestCase(
                test_name="Path traversal /etc/shadow",
                category="Path Traversal Attack",
                attack_type="etc_shadow",
                payload='<div>{require("fs").readFileSync("/etc/shadow")}</div>',
                code_type="jsx",
                expected_block=True,
                description="检测影子密码文件访问"
            ),
            SecurityTestCase(
                test_name="Path traversal nested",
                category="Path Traversal Attack",
                attack_type="nested_traversal",
                payload='<div>{require("fs").readFileSync("/var/www/../../etc/passwd")}</div>',
                code_type="jsx",
                expected_block=True,
                description="检测嵌套路径遍历"
            ),
            SecurityTestCase(
                test_name="Safe relative path",
                category="Path Traversal Attack",
                attack_type="safe",
                payload='<div>{require("fs").readFileSync("./config.json")}</div>',
                code_type="jsx",
                expected_block=False,
                description="安全的相对路径不应被拦截"
            ),

            # ========== DoS Attack Tests ==========
            SecurityTestCase(
                test_name="Infinite while loop",
                category="DoS Attack",
                attack_type="while_true",
                payload='<div>{while(true) { console.log("loop"); }}</div>',
                code_type="jsx",
                expected_block=True,
                description="检测无限while循环"
            ),
            SecurityTestCase(
                test_name="Infinite for loop",
                category="DoS Attack",
                attack_type="for_ever",
                payload='<div>{for(;;) { } }</div>',
                code_type="jsx",
                expected_block=True,
                description="检测无限for循环"
            ),
            SecurityTestCase(
                test_name="Infinite do-while loop",
                category="DoS Attack",
                attack_type="do_while_true",
                payload='<div>{do { } while(true); }</div>',
                code_type="jsx",
                expected_block=True,
                description="检测无限do-while循环"
            ),
            SecurityTestCase(
                test_name="Recursive infinite loop",
                category="DoS Attack",
                attack_type="recursive",
                payload='<div>{function f() { f(); }; f(); }</div>',
                code_type="jsx",
                expected_block=True,
                description="检测递归无限循环"
            ),
            SecurityTestCase(
                test_name="Safe finite loop",
                category="DoS Attack",
                attack_type="safe",
                payload='<div>{let sum = 0; for(let i=0; i<10; i++) { sum += i; } sum}</div>',
                code_type="jsx",
                expected_block=False,
                description="安全的有限循环不应被拦截"
            ),
            SecurityTestCase(
                test_name="Safe recursive function",
                category="DoS Attack",
                attack_type="safe",
                payload='<div>{function fact(n) { return n <= 1 ? 1 : n * fact(n-1); } fact(5)}</div>',
                code_type="jsx",
                expected_block=False,
                description="安全的递归函数不应被拦截"
            ),

            # ========== Resource Exhaustion Tests ==========
            SecurityTestCase(
                test_name="Memory exhaustion - large array",
                category="Resource Exhaustion Attack",
                attack_type="large_array",
                payload='<div>{Array(100000000).fill("x")}</div>',
                code_type="jsx",
                expected_block=True,
                description="检测大数组内存耗尽攻击"
            ),
            SecurityTestCase(
                test_name="String flood attack",
                category="Resource Exhaustion Attack",
                attack_type="string_flood",
                payload='<div>' + 'a' * 100000 + '</div>',
                code_type="jsx",
                expected_block=True,
                description="检测字符串洪水攻击"
            ),
            SecurityTestCase(
                test_name="Regex catastrophic backtracking",
                category="Resource Exhaustion Attack",
                attack_type="regex_bomb",
                payload='<div>{/^(a+)+$/.test("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaab")}</div>',
                code_type="jsx",
                expected_block=True,
                description="检测正则表达式灾难性回溯"
            ),
            SecurityTestCase(
                test_name="Safe small array",
                category="Resource Exhaustion Attack",
                attack_type="safe",
                payload='<div>{Array(100).fill(0)}</div>',
                code_type="jsx",
                expected_block=False,
                description="安全的小数组不应被拦截"
            ),
            SecurityTestCase(
                test_name="Safe string operation",
                category="Resource Exhaustion Attack",
                attack_type="safe",
                payload='<div>{("hello").repeat(10)}</div>',
                code_type="jsx",
                expected_block=False,
                description="安全的字符串操作不应被拦截"
            ),
        ]

    def run_all_tests(self) -> SecurityTestSuite:
        suite = SecurityTestSuite()
        suite.start_time = datetime.now()
        suite.tests = []

        for tc in self.test_cases:
            result = self._run_test_case(tc)
            suite.tests.append(result)

        suite.end_time = datetime.now()
        suite.total_tests = len(suite.tests)
        suite.passed = sum(1 for t in suite.tests if t.success)
        suite.failed = suite.total_tests - suite.passed
        suite.blocked_attacks = sum(1 for t in suite.tests if t.is_blocked)
        suite.allowed_attacks = sum(1 for t in suite.tests if not t.is_blocked)

        return suite

    def _run_test_case(self, tc: SecurityTestCase) -> TestResult:
        start_time = time.time()

        try:
            scan_result = self.security_manager.scan_code(tc.payload, tc.code_type)
            is_blocked = not scan_result.passed

            exec_time = time.time() - start_time

            return TestResult(
                test_name=tc.test_name,
                category=tc.category,
                attack_type=tc.attack_type,
                payload=tc.payload[:100] + '...' if len(tc.payload) > 100 else tc.payload,
                is_blocked=is_blocked,
                expected_block=tc.expected_block,
                success=is_blocked == tc.expected_block,
                scan_result=scan_result,
                response=str(scan_result.violations) if scan_result.violations else "No violations",
                execution_time=exec_time,
                details={
                    'risk_level': scan_result.risk_level,
                    'blocked_patterns': scan_result.blocked_patterns,
                    'warnings': scan_result.warnings,
                    'scan_duration_ms': scan_result.scan_duration_ms
                }
            )

        except Exception as e:
            exec_time = time.time() - start_time
            return TestResult(
                test_name=tc.test_name,
                category=tc.category,
                attack_type=tc.attack_type,
                payload=tc.payload[:100] + '...' if len(tc.payload) > 100 else tc.payload,
                is_blocked=True,
                expected_block=tc.expected_block,
                success=False,
                error=str(e),
                execution_time=exec_time,
                details={'exception': traceback.format_exc()}
            )

    def run_circuit_breaker_tests(self) -> List[TestResult]:
        results = []
        self.security_manager.reset_circuit_breaker()

        for i in range(6):
            payload = '<div>{eval("alert(1)")}</div>'
            start_time = time.time()

            scan_result = self.security_manager.scan_code(payload, "jsx")
            is_blocked = not scan_result.passed

            audit_entry = AuditLogEntry(
                timestamp=time.time(),
                workflow_id="test_wf",
                task_id=f"test_task_{i}",
                task_type="security_test",
                security_level="high",
                action="scan_code",
                status="denied" if is_blocked else "allowed"
            )
            self.security_manager.log_audit(audit_entry)

            exec_time = time.time() - start_time

            expected_block = True
            is_fused = self.security_manager.check_circuit_breaker()

            results.append(TestResult(
                test_name=f'Circuit breaker test #{i+1}',
                category='Circuit Breaker',
                attack_type='Fuse trigger sequence',
                payload=payload[:50],
                is_blocked=is_blocked,
                expected_block=expected_block,
                success=is_blocked == expected_block,
                scan_result=scan_result,
                response=f"Fused: {is_fused}, Violation count: {self.security_manager._violation_count}",
                execution_time=exec_time,
                details={
                    'fuse_count': self.security_manager._violation_count,
                    'is_fused': is_fused
                }
            ))

        payload = '<div>{2 + 2}</div>'
        start_time = time.time()

        is_fused = self.security_manager.check_circuit_breaker()
        scan_result = self.security_manager.scan_code(payload, "jsx") if not is_fused else None
        is_blocked = is_fused or (scan_result is not None and not scan_result.passed)

        exec_time = time.time() - start_time

        results.append(TestResult(
            test_name='Circuit breaker blocks even safe code',
            category='Circuit Breaker',
            attack_type='Fuse activation verification',
            payload=payload,
            is_blocked=is_blocked,
            expected_block=True,
            success=is_blocked == True,
            scan_result=scan_result,
            response=f"Fused: {is_fused}",
            execution_time=exec_time,
            details={'is_fused': is_fused}
        ))

        self.security_manager.reset_circuit_breaker()

        payload = '<div>{2 + 2}</div>'
        start_time = time.time()

        is_fused = self.security_manager.check_circuit_breaker()
        scan_result = self.security_manager.scan_code(payload, "jsx")
        is_blocked = not scan_result.passed

        exec_time = time.time() - start_time

        results.append(TestResult(
            test_name='Circuit breaker reset allows safe code',
            category='Circuit Breaker',
            attack_type='Fuse reset verification',
            payload=payload,
            is_blocked=is_blocked,
            expected_block=False,
            success=is_blocked == False,
            scan_result=scan_result,
            response=f"Fused: {is_fused}",
            execution_time=exec_time,
            details={'is_fused': is_fused}
        ))

        return results

    def run_path_scan_tests(self) -> List[TestResult]:
        results = []
        allowed_paths = ["./safe_dir", "./data"]

        test_paths = [
            ("../../../etc/passwd", True),
            ("%2e%2e%2fetc%2fpasswd", True),
            ("C:\\Windows\\System32", True),
            ("./safe_dir/config.json", False),
            ("./data/file.txt", False),
        ]

        for path, expected_block in test_paths:
            start_time = time.time()

            scan_result = self.security_manager.scan_path(path, allowed_paths)
            is_blocked = not scan_result.passed

            exec_time = time.time() - start_time

            results.append(TestResult(
                test_name=f'Path scan: {path[:50]}',
                category='Path Security Scan',
                attack_type='path_validation',
                payload=path,
                is_blocked=is_blocked,
                expected_block=expected_block,
                success=is_blocked == expected_block,
                scan_result=scan_result,
                response=str(scan_result.violations) if scan_result.violations else "Path allowed",
                execution_time=exec_time,
                details={
                    'risk_level': scan_result.risk_level,
                    'blocked_patterns': scan_result.blocked_patterns
                }
            ))

        return results

    def run_audit_log_tests(self) -> List[TestResult]:
        results = []
        initial_count = len(self.security_manager._audit_logs)

        for i in range(10):
            entry = AuditLogEntry(
                timestamp=time.time(),
                workflow_id=f"wf_{i}",
                task_id=f"task_{i}",
                task_type="test_task",
                security_level="low",
                action="test_action",
                status="allowed" if i % 2 == 0 else "denied"
            )
            self.security_manager.log_audit(entry)

        stats = self.security_manager.get_audit_stats()

        results.append(TestResult(
            test_name='Audit logging works',
            category='Audit System',
            attack_type='logging',
            payload='N/A',
            is_blocked=False,
            expected_block=False,
            success=stats['total_audits'] == initial_count + 10,
            response=f"Total audits: {stats['total_audits']}, violations: {stats['violation_count']}",
            details=stats
        ))

        logs = self.security_manager.get_audit_logs(action="test_action", limit=5)
        results.append(TestResult(
            test_name='Audit log filtering',
            category='Audit System',
            attack_type='filtering',
            payload='N/A',
            is_blocked=False,
            expected_block=False,
            success=len(logs) == 5,
            response=f"Filtered logs: {len(logs)}",
            details={'filtered_count': len(logs)}
        ))

        return results


def generate_report(suite: SecurityTestSuite, additional_results: List[TestResult] = None) -> str:
    report = []
    report.append("# JSX 安全执行层测试报告")
    report.append("")
    report.append(f"**测试时间**: {suite.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"**结束时间**: {suite.end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"**测试时长**: {(suite.end_time - suite.start_time).total_seconds():.2f} 秒")
    report.append("")

    all_results = suite.tests + (additional_results or [])

    report.append("## 测试概览")
    report.append("")
    report.append("| 指标 | 数值 |")
    report.append("|------|------|")
    report.append(f"| 总测试用例 | {len(all_results)} |")
    report.append(f"| 通过 | {sum(1 for r in all_results if r.success)} |")
    report.append(f"| 失败 | {sum(1 for r in all_results if not r.success)} |")
    report.append(f"| 拦截攻击 | {sum(1 for r in all_results if r.is_blocked)} |")
    report.append(f"| 允许正常 | {sum(1 for r in all_results if not r.is_blocked)} |")
    pass_rate = sum(1 for r in all_results if r.success) / len(all_results) * 100
    report.append(f"| 通过率 | {pass_rate:.2f}% |")
    report.append("")

    categories = {}
    for test in all_results:
        if test.category not in categories:
            categories[test.category] = {'total': 0, 'passed': 0, 'failed': 0}
        categories[test.category]['total'] += 1
        if test.success:
            categories[test.category]['passed'] += 1
        else:
            categories[test.category]['failed'] += 1

    report.append("## 分类统计")
    report.append("")
    report.append("| 测试类别 | 总数 | 通过 | 失败 | 通过率 |")
    report.append("|----------|------|------|------|--------|")
    for cat, stats in categories.items():
        rate = stats['passed'] / stats['total'] * 100 if stats['total'] > 0 else 0
        report.append(f"| {cat} | {stats['total']} | {stats['passed']} | {stats['failed']} | {rate:.2f}% |")
    report.append("")

    report.append("## 测试详情")
    report.append("")

    for cat in categories.keys():
        report.append(f"### {cat}")
        report.append("")
        report.append("| 测试名称 | 攻击类型 | 拦截 | 期望 | 结果 | 执行时间 |")
        report.append("|----------|----------|------|------|------|----------|")

        for test in all_results:
            if test.category != cat:
                continue

            status_icon = "✅" if test.success else "❌"
            blocked_icon = "🔒" if test.is_blocked else "✅"
            expected_icon = "🔒" if test.expected_block else "✅"

            report.append(f"| {test.test_name} | {test.attack_type} | {blocked_icon} | {expected_icon} | {status_icon} | {test.execution_time:.4f}s |")

        report.append("")

    failed_tests = [t for t in all_results if not t.success]
    if failed_tests:
        report.append("## 失败测试详情")
        report.append("")

        for test in failed_tests:
            report.append(f"### ❌ {test.test_name}")
            report.append(f"- **类别**: {test.category}")
            report.append(f"- **攻击类型**: {test.attack_type}")
            report.append(f"- **Payload**: `{test.payload}`")
            report.append(f"- **实际拦截**: {'是' if test.is_blocked else '否'}")
            report.append(f"- **期望拦截**: {'是' if test.expected_block else '否'}")
            report.append(f"- **响应**: {test.response}")
            if test.error:
                report.append(f"- **错误**: {test.error}")
            report.append("")

    report.append("## 安全评估")
    report.append("")

    overall_score = pass_rate
    if overall_score >= 95:
        score_text = "优秀"
        score_color = "🟢"
    elif overall_score >= 80:
        score_text = "良好"
        score_color = "🟡"
    elif overall_score >= 60:
        score_text = "及格"
        score_color = "🟠"
    else:
        score_text = "不及格"
        score_color = "🔴"

    report.append(f"**整体安全评分**: {score_color} {overall_score:.2f}分 ({score_text})")
    report.append("")

    if any(not r.success for r in all_results):
        report.append("### 安全漏洞")
        report.append("")
        for test in failed_tests:
            if test.expected_block and not test.is_blocked:
                report.append(f"- ⚠️ **未拦截攻击**: {test.test_name} - 可能存在安全漏洞")
            elif not test.expected_block and test.is_blocked:
                report.append(f"- ⚠️ **误报拦截**: {test.test_name} - 可能影响正常功能")
        report.append("")

    report.append("### 安全建议")
    report.append("")
    report.append("1. 确保所有危险函数（eval、exec、require等）被正确拦截")
    report.append("2. 加强路径遍历攻击防护，特别是编码绕过")
    report.append("3. 确保熔断机制正常工作，防止DoS攻击")
    report.append("4. 定期更新安全规则以应对新的攻击手法")
    report.append("5. 考虑添加输入长度限制和速率限制")
    report.append("6. 增加输出扫描，防止敏感信息泄露")
    report.append("")

    report.append("---")
    report.append(f"*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")

    return '\n'.join(report)


def main():
    print("=" * 70)
    print("JSX 安全执行层测试框架")
    print("=" * 70)
    print(f"测试开始: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    framework = SecurityTestFramework()

    print("[1/4] 运行核心安全扫描测试...")
    suite = framework.run_all_tests()
    print(f"  完成: {len(suite.tests)} 个测试用例")

    print("[2/4] 运行熔断机制测试...")
    breaker_results = framework.run_circuit_breaker_tests()
    print(f"  完成: {len(breaker_results)} 个测试用例")

    print("[3/4] 运行路径扫描测试...")
    path_results = framework.run_path_scan_tests()
    print(f"  完成: {len(path_results)} 个测试用例")

    print("[4/4] 运行审计日志测试...")
    audit_results = framework.run_audit_log_tests()
    print(f"  完成: {len(audit_results)} 个测试用例")

    print()
    print(f"测试完成: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    all_results = suite.tests + breaker_results + path_results + audit_results
    passed = sum(1 for r in all_results if r.success)
    failed = len(all_results) - passed
    pass_rate = passed / len(all_results) * 100

    print(f"总测试用例: {len(all_results)}")
    print(f"通过: {passed}")
    print(f"失败: {failed}")
    print(f"通过率: {pass_rate:.2f}%")
    print()

    output_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'output')
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, 'security_report.md')

    additional_results = breaker_results + path_results + audit_results
    report = generate_report(suite, additional_results)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"安全测试报告已生成: {output_path}")
    print("=" * 70)


if __name__ == '__main__':
    main()