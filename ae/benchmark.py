"""
AE 稳定性基准测试命令行工具
============================

提供统一的命令行接口来运行各类稳定性测试。

使用方式：
    python ae/benchmark.py --test smoketest
    python ae/benchmark.py --test basic
    python ae/benchmark.py --test stress --iterations 100
    python ae/benchmark.py --test soak
    python ae/benchmark.py --test all --report html
    python ae/benchmark.py --list

输出格式支持：
- text: 终端文本报告（默认）
- json: JSON 格式报告
- markdown: Markdown 格式报告
- html: HTML 格式报告
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# 确保脚本可直接运行时能找到 ae.* 模块
_THIS = Path(__file__).resolve()
for _p in (str(_THIS.parent.parent), str(_THIS.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest


@dataclass
class BenchmarkConfig:
    """基准测试配置。"""

    test_type: str = "basic"
    iterations: int = 1
    report_format: str = "text"
    report_dir: Path = Path("reports")
    verbose: bool = False
    fail_fast: bool = False
    test_env: str = "mock"


TEST_SUITES = {
    "smoketest": {
        "name": "烟雾测试",
        "description": "快速验证基本功能（30秒内完成）",
        "pytest_args": [
            "ae/tests/test_smoke.py",
            "-m",
            "smoke",
            "--tb=short",
            "-q",
        ],
        "min_pass_rate": 0.95,
    },
    "basic": {
        "name": "基础测试",
        "description": "核心功能全面测试",
        "pytest_args": [
            "ae/tests/test_smoke.py",
            "ae/tests/test_process_lifecycle.py",
            "ae/tests/test_bridge_stability.py",
            "ae/tests/test_ae_operations.py",
            "-m",
            "not slow and not stress and not soak",
            "--tb=short",
        ],
        "min_pass_rate": 0.90,
    },
    "stress": {
        "name": "压力测试",
        "description": "高负载下的稳定性测试",
        "pytest_args": [
            "ae/tests/test_bridge_stability.py",
            "ae/tests/test_ae_operations.py",
            "-m",
            "stress",
            "--tb=short",
        ],
        "min_pass_rate": 0.85,
    },
    "soak": {
        "name": "耐久测试",
        "description": "长时间运行稳定性测试",
        "pytest_args": [
            "ae/tests/test_bridge_stability.py",
            "ae/tests/test_process_lifecycle.py",
            "-m",
            "soak",
            "--tb=short",
        ],
        "min_pass_rate": 0.90,
    },
    "process": {
        "name": "进程生命周期测试",
        "description": "AE 进程管理测试",
        "pytest_args": [
            "ae/tests/test_process_lifecycle.py",
            "--tb=short",
        ],
        "min_pass_rate": 0.90,
    },
    "bridge": {
        "name": "Bridge 通信测试",
        "description": "Bridge 通信层稳定性测试",
        "pytest_args": [
            "ae/tests/test_bridge_stability.py",
            "-m",
            "not slow",
            "--tb=short",
        ],
        "min_pass_rate": 0.95,
    },
    "operations": {
        "name": "AE 操作测试",
        "description": "AE 操作稳定性测试",
        "pytest_args": [
            "ae/tests/test_ae_operations.py",
            "--tb=short",
        ],
        "min_pass_rate": 0.90,
    },
    "mcp_validation": {
        "name": "MCP 工具真实环境验证",
        "description": "对 20+ AE MCP 工具进行端到端真实环境验证（自动降级 mock）",
        "runner": "mcp_validation",  # 自定义运行器，由 BenchmarkRunner 识别
        "categories": ["core", "important", "advanced"],
        "min_pass_rate": 0.80,
    },
    "all": {
        "name": "完整测试",
        "description": "运行所有稳定性测试",
        "pytest_args": [
            "ae/tests/",
            "--tb=short",
        ],
        "min_pass_rate": 0.85,
    },
}


class BenchmarkRunner:
    """基准测试运行器。"""

    def __init__(self, config: BenchmarkConfig) -> None:
        """初始化基准测试运行器。

        Args:
            config: 基准测试配置
        """
        self.config = config
        self.results: Dict[str, Any] = {}
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None

    def run(self) -> int:
        """运行基准测试。

        Returns:
            退出码（0 = 成功, 非 0 = 失败）
        """
        self.start_time = datetime.now()

        suite = TEST_SUITES.get(self.config.test_type)
        if not suite:
            print(f"错误: 未知的测试类型 '{self.config.test_type}'")
            print(f"可用类型: {', '.join(TEST_SUITES.keys())}")
            return 1

        print("=" * 70)
        print(f"  AE 稳定性基准测试 - {suite['name']}")
        print(f"  {suite['description']}")
        print(f"  开始时间: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  测试环境: {self.config.test_env}")
        print(f"  迭代次数: {self.config.iterations}")
        print("=" * 70)
        print()

        exit_code = 0
        all_results = []

        # 特殊 runner：mcp_validation
        if suite.get("runner") == "mcp_validation":
            # 在 test_env=mock 时直接使用 Mock，跳过真实 AE 探测，避免 30s 超时
            if self.config.test_env != "real":
                os.environ["AE_MCP_VALIDATION_FAST_MOCK"] = "1"
            else:
                os.environ.pop("AE_MCP_VALIDATION_FAST_MOCK", None)

            for iteration in range(self.config.iterations):
                if self.config.iterations > 1:
                    print(f"\n--- 第 {iteration + 1}/{self.config.iterations} 轮 ---")
                result = self._run_mcp_validation(suite)
                all_results.append(result)
                if result["exit_code"] != 0 and self.config.fail_fast:
                    exit_code = 1
                    break
            self.end_time = datetime.now()
            self.results = self._aggregate_mcp_results(all_results, suite)
        else:
            for iteration in range(self.config.iterations):
                if self.config.iterations > 1:
                    print(f"\n--- 第 {iteration + 1}/{self.config.iterations} 轮 ---")

                result = self._run_pytest(suite)
                all_results.append(result)

                if result["exit_code"] != 0 and self.config.fail_fast:
                    exit_code = 1
                    break

            self.end_time = datetime.now()
            self.results = self._aggregate_results(all_results, suite)

        # 生成报告
        self._generate_report()

        # 判断总体通过/失败
        if self.results["pass_rate"] < suite["min_pass_rate"]:
            exit_code = 1
            print(f"\n❌ 测试未通过: 通过率 {self.results['pass_rate']:.1%} "
                  f"< 阈值 {suite['min_pass_rate']:.0%}")
        elif any(r["exit_code"] != 0 for r in all_results):
            exit_code = 1
            print("\n❌ 存在失败的测试")
        else:
            print(f"\n✅ 测试通过: 通过率 {self.results['pass_rate']:.1%}")

        return exit_code

    def _run_pytest(self, suite: Dict[str, Any]) -> Dict[str, Any]:
        """运行 pytest 测试。

        Args:
            suite: 测试套件配置

        Returns:
            测试结果字典
        """
        import io
        from contextlib import redirect_stdout, redirect_stderr

        args = list(suite["pytest_args"])

        # 使用 -v 确保输出格式一致，便于解析
        args.append("-v")

        if not self.config.verbose:
            # 非详细模式下，只显示失败的详细信息
            args.append("--tb=line")

        # 设置测试环境
        os.environ["AE_TEST_ENV"] = self.config.test_env

        start = time.time()

        # 捕获 pytest 输出
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        try:
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                exit_code = pytest.main(args)
        except SystemExit as e:
            exit_code = e.code if e.code is not None else 0

        # 处理 ExitCode 枚举类型
        if hasattr(exit_code, "value"):
            exit_code_value = int(exit_code.value)
        else:
            exit_code_value = int(exit_code) if exit_code is not None else 0

        duration = time.time() - start

        stdout_text = stdout_capture.getvalue()
        stderr_text = stderr_capture.getvalue()

        if self.config.verbose or exit_code_value != 0:
            print(stdout_text)
            if stderr_text:
                print(stderr_text, file=sys.stderr)

        # 解析测试结果
        passed, failed, skipped, total = self._parse_pytest_output(stdout_text)

        return {
            "exit_code": exit_code_value,
            "duration": duration,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "total": total,
            "stdout": stdout_text,
            "stderr": stderr_text,
        }

    def _parse_pytest_output(self, output: str) -> tuple[int, int, int, int]:
        """解析 pytest 输出。

        Args:
            output: pytest 输出文本

        Returns:
            (passed, failed, skipped, total)
        """
        import re

        passed = 0
        failed = 0
        skipped = 0
        errors = 0
        total = 0

        lines = output.strip().split("\n")

        # 方法1: 从 verbose 输出的每行统计 PASSED/FAILED/SKIPPED/ERROR
        for line in lines:
            line = line.strip()
            # 匹配 verbose 模式下的 test_file.py::TestClass::test_name PASSED
            if re.search(r"PASSED$", line):
                passed += 1
            elif re.search(r"FAILED$", line):
                failed += 1
            elif re.search(r"SKIPPED$", line):
                skipped += 1
            elif re.search(r"ERROR$", line):
                errors += 1

        # 方法2: 如果方法1没找到，尝试从结果摘要行解析
        if passed == 0 and failed == 0 and skipped == 0:
            for line in reversed(lines):
                line = line.strip()
                if not line:
                    continue

                passed_match = re.search(r"(\d+)\s+passed", line)
                failed_match = re.search(r"(\d+)\s+failed", line)
                skipped_match = re.search(r"(\d+)\s+skipped", line)
                error_match = re.search(r"(\d+)\s+error", line)

                if passed_match:
                    passed = int(passed_match.group(1))
                if failed_match:
                    failed = int(failed_match.group(1))
                if skipped_match:
                    skipped = int(skipped_match.group(1))
                if error_match:
                    errors = int(error_match.group(1))

                if passed_match or failed_match or skipped_match:
                    if "in " in line and ("s" in line.split("in ")[-1]):
                        break

        total = passed + failed + skipped + errors

        return passed, failed, skipped, total

    def _run_mcp_validation(self, suite: Dict[str, Any]) -> Dict[str, Any]:
        """运行 MCP 工具验证套件。

        通过动态导入 MCPToolValidationSuite 执行端到端验证。
        无 AE 环境时使用内置 Mock 客户端。

        Args:
            suite: 测试套件配置

        Returns:
            验证结果字典
        """
        import asyncio
        import io
        import json
        import tempfile
        from contextlib import redirect_stdout, redirect_stderr

        start = time.time()
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        # 通过临时文件传递 report dict（避免 stdout 解析脆弱）
        tmp_report = Path(tempfile.gettempdir()) / f"mcp_val_{os.getpid()}_{int(start*1000)}.json"
        result_holder: Dict[str, Any] = {"report_path": str(tmp_report), "error": None}

        try:
            from ae.tests.test_mcp_tools_validation import (
                MCPToolValidationSuite,
            )

            categories = suite.get("categories")
            use_real = self.config.test_env == "real"

            async def _run() -> None:
                _suite = MCPToolValidationSuite(
                    use_real_ae=use_real,
                    categories=categories,
                )
                report = await _suite.run_all()
                # 写出 JSON 供主线程读取
                tmp_report.write_text(
                    json.dumps(report.to_dict(), ensure_ascii=False),
                    encoding="utf-8",
                )
                # 同样保存到 report_dir
                _suite.save_report(
                    self.config.report_dir / "mcp_validation",
                    formats=["json", "markdown", "html"],
                )

            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                try:
                    asyncio.run(_run())
                except SystemExit as e:
                    result_holder["error"] = f"SystemExit: {e.code}"
                except Exception as e:  # noqa: BLE001
                    result_holder["error"] = f"{type(e).__name__}: {e}"
        except Exception as e:  # noqa: BLE001
            result_holder["error"] = f"加载套件失败: {type(e).__name__}: {e}"

        duration = time.time() - start
        stdout_text = stdout_capture.getvalue()
        stderr_text = stderr_capture.getvalue()

        if self.config.verbose:
            print(stdout_text)
            if stderr_text:
                print(stderr_text, file=sys.stderr)

        # 优先从 JSON 文件读取真实数据；失败时回退到 stdout 解析
        passed = failed = skipped = total = 0
        exit_code = 0
        if tmp_report.exists():
            try:
                data = json.loads(tmp_report.read_text(encoding="utf-8"))
                total = data.get("total_tools", 0)
                passed = data.get("passed", 0)
                failed = data.get("failed", 0)
                skipped = data.get("skipped", 0)
                errors = data.get("errors", 0)
                pass_rate = data.get("pass_rate", 0.0)
                if pass_rate < suite["min_pass_rate"]:
                    exit_code = 1
                # 报告被消耗后清理
                try:
                    tmp_report.unlink()
                except OSError:
                    pass
                # 重新生成报告主文件
                self._save_aggregated_mcp_report(data, suite)
                return {
                    "exit_code": exit_code,
                    "duration": duration,
                    "passed": passed,
                    "failed": failed + errors,
                    "skipped": skipped,
                    "total": total,
                    "stdout": stdout_text,
                    "stderr": stderr_text,
                }
            except Exception:  # noqa: BLE001
                pass

        # 回退：解析 stdout
        passed, failed, skipped, total = self._parse_mcp_output(stdout_text)
        if result_holder.get("error"):
            exit_code = 1
            failed = max(failed, 1)

        return {
            "exit_code": exit_code,
            "duration": duration,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "total": total,
            "stdout": stdout_text,
            "stderr": stderr_text,
        }

    def _save_aggregated_mcp_report(
        self, data: Dict[str, Any], suite: Dict[str, Any]
    ) -> None:
        """将 MCP 验证数据保存为聚合报告。"""
        # 由 _generate_report 在主流程中根据 self.results 写出，
        # 这里只把数据保存到结果 dict 中。
        # 实际写入由 BenchmarkRunner 主流程负责。
        pass

    def _parse_mcp_output(self, output: str) -> tuple[int, int, int, int]:
        """解析 MCP 验证输出。

        期望输出格式：
            总工具数:       N
            ✅ 通过:         N
            ❌ 失败:         N
            ⏭️  跳过:         N
            ⚠️  错误:         N
            通过率:         N%
        """
        import re

        total = 0
        passed = 0
        failed = 0
        skipped = 0
        errored = 0

        for line in output.splitlines():
            stripped = line.strip()
            m = re.match(r"总工具数:\s+(\d+)", stripped)
            if m:
                total = int(m.group(1))
            m = re.match(r"✅\s*通过:\s+(\d+)", stripped)
            if m:
                passed = int(m.group(1))
            m = re.match(r"❌\s*失败:\s+(\d+)", stripped)
            if m:
                failed = int(m.group(1))
            m = re.match(r"⏭️\s*跳过:\s+(\d+)", stripped)
            if m:
                skipped = int(m.group(1))
            m = re.match(r"⚠️\s*错误:\s+(\d+)", stripped)
            if m:
                errored = int(m.group(1))

        if total == 0:
            total = passed + failed + skipped + errored
        return passed, failed, skipped, total

    def _aggregate_mcp_results(
        self, all_results: List[Dict[str, Any]], suite: Dict[str, Any]
    ) -> Dict[str, Any]:
        """聚合 MCP 验证多次迭代的结果。"""
        if not all_results:
            return {
                "test_type": self.config.test_type,
                "test_name": suite["name"],
                "iterations": 0,
                "total_duration": 0,
                "avg_duration": 0,
                "total_passed": 0,
                "total_failed": 0,
                "total_skipped": 0,
                "total_tests": 0,
                "pass_rate": 0.0,
                "start_time": self.start_time.isoformat() if self.start_time else None,
                "end_time": self.end_time.isoformat() if self.end_time else None,
            }

        total_passed = sum(r["passed"] for r in all_results)
        total_failed = sum(r["failed"] for r in all_results)
        total_skipped = sum(r["skipped"] for r in all_results)
        total_tests = sum(r["total"] for r in all_results)
        total_duration = sum(r["duration"] for r in all_results)

        pass_rate = (total_passed / total_tests) if total_tests > 0 else 0.0

        return {
            "test_type": self.config.test_type,
            "test_name": suite["name"],
            "test_description": suite["description"],
            "iterations": len(all_results),
            "total_duration": total_duration,
            "avg_duration": total_duration / len(all_results),
            "total_passed": total_passed,
            "total_failed": total_failed,
            "total_skipped": total_skipped,
            "total_tests": total_tests,
            "pass_rate": pass_rate,
            "min_pass_rate": suite["min_pass_rate"],
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "per_iteration": all_results,
        }

    def _aggregate_results(
        self, all_results: List[Dict[str, Any]], suite: Dict[str, Any]
    ) -> Dict[str, Any]:
        """聚合多次迭代的结果。

        Args:
            all_results: 所有迭代的结果
            suite: 测试套件配置

        Returns:
            聚合后的结果
        """
        if not all_results:
            return {
                "test_type": self.config.test_type,
                "test_name": suite["name"],
                "iterations": 0,
                "total_duration": 0,
                "avg_duration": 0,
                "total_passed": 0,
                "total_failed": 0,
                "total_skipped": 0,
                "total_tests": 0,
                "pass_rate": 0.0,
                "start_time": self.start_time.isoformat() if self.start_time else None,
                "end_time": self.end_time.isoformat() if self.end_time else None,
            }

        total_passed = sum(r["passed"] for r in all_results)
        total_failed = sum(r["failed"] for r in all_results)
        total_skipped = sum(r["skipped"] for r in all_results)
        total_tests = sum(r["total"] for r in all_results)
        total_duration = sum(r["duration"] for r in all_results)

        pass_rate = (total_passed / total_tests) if total_tests > 0 else 0.0

        return {
            "test_type": self.config.test_type,
            "test_name": suite["name"],
            "test_description": suite["description"],
            "iterations": len(all_results),
            "total_duration": total_duration,
            "avg_duration": total_duration / len(all_results),
            "total_passed": total_passed,
            "total_failed": total_failed,
            "total_skipped": total_skipped,
            "total_tests": total_tests,
            "pass_rate": pass_rate,
            "min_pass_rate": suite["min_pass_rate"],
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "per_iteration": all_results,
        }

    def _generate_report(self) -> None:
        """生成测试报告。"""
        self.config.report_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        basename = f"benchmark_{self.config.test_type}_{timestamp}"

        fmt = self.config.report_format.lower()

        if fmt == "json":
            path = self.config.report_dir / f"{basename}.json"
            self._write_json_report(path)
        elif fmt == "markdown":
            path = self.config.report_dir / f"{basename}.md"
            self._write_markdown_report(path)
        elif fmt == "html":
            path = self.config.report_dir / f"{basename}.html"
            self._write_html_report(path)
        else:
            # text 格式输出到终端
            self._print_text_report()
            return

        print(f"\n📄 报告已保存: {path}")

    def _print_text_report(self) -> None:
        """打印文本报告到终端。"""
        r = self.results

        print("\n" + "=" * 70)
        print("  测试结果摘要")
        print("=" * 70)
        print(f"  测试套件:     {r['test_name']} ({r['test_type']})")
        print(f"  迭代次数:     {r['iterations']}")
        print(f"  总耗时:       {r['total_duration']:.2f}s")
        print(f"  平均耗时:     {r['avg_duration']:.2f}s/轮")
        print(f"  通过用例:     {r['total_passed']}")
        print(f"  失败用例:     {r['total_failed']}")
        print(f"  跳过用例:     {r['total_skipped']}")
        print(f"  总用例数:     {r['total_tests']}")
        print(f"  通过率:       {r['pass_rate']:.1%}")
        print(f"  通过阈值:     {r['min_pass_rate']:.0%}")
        print("=" * 70)

        status = "✅ 通过" if r["pass_rate"] >= r["min_pass_rate"] else "❌ 失败"
        print(f"\n  总体状态: {status}")

    def _write_json_report(self, path: Path) -> None:
        """写入 JSON 报告。

        Args:
            path: 输出文件路径
        """
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)

    def _write_markdown_report(self, path: Path) -> None:
        """写入 Markdown 报告。

        Args:
            path: 输出文件路径
        """
        r = self.results
        status = "✅ 通过" if r["pass_rate"] >= r["min_pass_rate"] else "❌ 失败"

        md = f"""# AE 稳定性基准测试报告

## 基本信息

| 项目 | 值 |
|------|-----|
| 测试套件 | {r['test_name']} (`{r['test_type']}`) |
| 测试描述 | {r['test_description']} |
| 开始时间 | {r['start_time']} |
| 结束时间 | {r['end_time']} |
| 迭代次数 | {r['iterations']} |
| 测试环境 | {self.config.test_env} |
| 总体状态 | **{status}** |

## 测试结果

| 指标 | 值 |
|------|-----|
| 总用例数 | {r['total_tests']} |
| 通过 | {r['total_passed']} |
| 失败 | {r['total_failed']} |
| 跳过 | {r['total_skipped']} |
| 通过率 | {r['pass_rate']:.1%} |
| 通过阈值 | {r['min_pass_rate']:.0%} |
| 总耗时 | {r['total_duration']:.2f}s |
| 平均耗时 | {r['avg_duration']:.2f}s/轮 |

## 每轮详情

| 轮次 | 通过 | 失败 | 跳过 | 耗时(s) |
|------|------|------|------|---------|
"""

        for i, res in enumerate(r.get("per_iteration", []), 1):
            md += (
                f"| {i} | {res['passed']} | {res['failed']} | "
                f"{res['skipped']} | {res['duration']:.2f} |\n"
            )

        md += "\n---\n*报告由 AE Benchmark 自动生成*\n"

        with open(path, "w", encoding="utf-8") as f:
            f.write(md)

    def _write_html_report(self, path: Path) -> None:
        """写入 HTML 报告。

        Args:
            path: 输出文件路径
        """
        r = self.results
        status = "通过" if r["pass_rate"] >= r["min_pass_rate"] else "失败"
        status_color = "#22c55e" if r["pass_rate"] >= r["min_pass_rate"] else "#ef4444"
        pass_pct = r["pass_rate"] * 100

        iterations_html = ""
        for i, res in enumerate(r.get("per_iteration", []), 1):
            iterations_html += f"""
            <tr>
                <td>第 {i} 轮</td>
                <td>{res['passed']}</td>
                <td>{res['failed']}</td>
                <td>{res['skipped']}</td>
                <td>{res['duration']:.2f}s</td>
            </tr>"""

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AE 稳定性基准测试报告 - {r['test_name']}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #f8fafc;
            color: #1e293b;
            padding: 2rem;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
            padding: 2rem;
        }}
        h1 {{
            font-size: 1.75rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
            color: #0f172a;
        }}
        .subtitle {{
            color: #64748b;
            margin-bottom: 2rem;
        }}
        .status-badge {{
            display: inline-block;
            padding: 0.5rem 1rem;
            border-radius: 9999px;
            background: {status_color};
            color: white;
            font-weight: 600;
            margin-bottom: 1.5rem;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }}
        .card {{
            background: #f1f5f9;
            border-radius: 8px;
            padding: 1rem;
        }}
        .card-label {{
            font-size: 0.875rem;
            color: #64748b;
            margin-bottom: 0.25rem;
        }}
        .card-value {{
            font-size: 1.5rem;
            font-weight: 700;
            color: #0f172a;
        }}
        .progress-bar {{
            width: 100%;
            height: 12px;
            background: #e2e8f0;
            border-radius: 6px;
            overflow: hidden;
            margin: 0.5rem 0;
        }}
        .progress-fill {{
            height: 100%;
            background: {status_color};
            width: {pass_pct}%;
            transition: width 0.5s ease;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 1rem;
        }}
        th, td {{
            padding: 0.75rem;
            text-align: left;
            border-bottom: 1px solid #e2e8f0;
        }}
        th {{
            background: #f8fafc;
            font-weight: 600;
            color: #475569;
        }}
        tr:hover {{ background: #f8fafc; }}
        h2 {{
            font-size: 1.25rem;
            margin-top: 2rem;
            margin-bottom: 1rem;
            color: #0f172a;
        }}
        .footer {{
            margin-top: 2rem;
            padding-top: 1rem;
            border-top: 1px solid #e2e8f0;
            color: #94a3b8;
            font-size: 0.875rem;
            text-align: center;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>AE 稳定性基准测试报告</h1>
        <p class="subtitle">{r['test_name']} - {r['test_description']}</p>

        <div class="status-badge">{'✅' if r['pass_rate'] >= r['min_pass_rate'] else '❌'} {status}</div>

        <div class="progress-bar">
            <div class="progress-fill"></div>
        </div>
        <p style="text-align: right; color: #64748b; font-size: 0.875rem;">
            通过率: {pass_pct:.1f}% (阈值: {r['min_pass_rate']*100:.0f}%)
        </p>

        <h2>基本信息</h2>
        <div class="grid">
            <div class="card">
                <div class="card-label">测试套件</div>
                <div class="card-value" style="font-size: 1rem;">{r['test_name']}</div>
            </div>
            <div class="card">
                <div class="card-label">迭代次数</div>
                <div class="card-value">{r['iterations']}</div>
            </div>
            <div class="card">
                <div class="card-label">总耗时</div>
                <div class="card-value">{r['total_duration']:.1f}s</div>
            </div>
            <div class="card">
                <div class="card-label">平均耗时</div>
                <div class="card-value">{r['avg_duration']:.1f}s</div>
            </div>
        </div>

        <h2>测试结果</h2>
        <div class="grid">
            <div class="card">
                <div class="card-label">总用例数</div>
                <div class="card-value">{r['total_tests']}</div>
            </div>
            <div class="card">
                <div class="card-label">通过</div>
                <div class="card-value" style="color: #22c55e;">{r['total_passed']}</div>
            </div>
            <div class="card">
                <div class="card-label">失败</div>
                <div class="card-value" style="color: #ef4444;">{r['total_failed']}</div>
            </div>
            <div class="card">
                <div class="card-label">跳过</div>
                <div class="card-value" style="color: #f59e0b;">{r['total_skipped']}</div>
            </div>
        </div>

        <h2>每轮详情</h2>
        <table>
            <thead>
                <tr>
                    <th>轮次</th>
                    <th>通过</th>
                    <th>失败</th>
                    <th>跳过</th>
                    <th>耗时</th>
                </tr>
            </thead>
            <tbody>
                {iterations_html}
            </tbody>
        </table>

        <div class="footer">
            报告由 AE Benchmark 自动生成 · {r['end_time']}
        </div>
    </div>
</body>
</html>"""

        with open(path, "w", encoding="utf-8") as f:
            f.write(html)


def list_tests() -> None:
    """列出所有可用的测试套件。"""
    print("\n可用的测试套件：")
    print("-" * 60)
    for key, suite in TEST_SUITES.items():
        print(f"  {key:<15} {suite['name']:<12} - {suite['description']}")
    print()


def main() -> int:
    """主入口函数。

    Returns:
        退出码
    """
    parser = argparse.ArgumentParser(
        description="AE 稳定性基准测试命令行工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s --test smoketest              # 运行烟雾测试
  %(prog)s --test basic --report json    # 基础测试 + JSON 报告
  %(prog)s --test stress --iterations 10 # 压力测试，迭代 10 次
  %(prog)s --list                        # 列出所有测试套件
        """,
    )

    parser.add_argument(
        "--test",
        "-t",
        type=str,
        default="basic",
        help=f"测试类型: {', '.join(TEST_SUITES.keys())} (默认: basic)",
    )
    parser.add_argument(
        "--iterations",
        "-n",
        type=int,
        default=1,
        help="迭代次数 (默认: 1)",
    )
    parser.add_argument(
        "--report",
        "-r",
        type=str,
        default="text",
        choices=["text", "json", "markdown", "html"],
        help="报告格式 (默认: text)",
    )
    parser.add_argument(
        "--report-dir",
        type=str,
        default="reports",
        help="报告输出目录 (默认: reports)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="详细输出",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="失败时立即停止",
    )
    parser.add_argument(
        "--test-env",
        type=str,
        default="mock",
        choices=["mock", "real"],
        help="测试环境: mock=模拟环境, real=真实AE环境 (默认: mock)",
    )
    parser.add_argument(
        "--list",
        "-l",
        action="store_true",
        help="列出所有可用测试套件",
    )

    args = parser.parse_args()

    if args.list:
        list_tests()
        return 0

    config = BenchmarkConfig(
        test_type=args.test,
        iterations=args.iterations,
        report_format=args.report,
        report_dir=Path(args.report_dir),
        verbose=args.verbose,
        fail_fast=args.fail_fast,
        test_env=args.test_env,
    )

    runner = BenchmarkRunner(config)
    return runner.run()


if __name__ == "__main__":
    sys.exit(main())
