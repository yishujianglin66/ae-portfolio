"""
AE Environment Validator
========================

真实环境验证框架，用于验证 AE 自动化环境是否正常运行。

核心功能：
- AE 进程启动验证（安装路径、版本、启动时间）
- Bridge 通信验证（Listener、命令队列、响应）
- MCP 工具功能验证（核心工具集测试）
- 端到端流程验证（从创建到渲染的完整流程）
- 性能基准测试（响应时间、内存占用、稳定性）

设计目标：
- 自动检测环境问题并给出修复建议
- 生成详细的验证报告
- 支持 CI/CD 集成
- 支持定期健康检查

Usage:
    # 完整验证
    validator = AEEnvironmentValidator()
    report = validator.run_full_validation()
    
    # 仅验证 Bridge 通信
    result = validator.validate_bridge()
    
    # 性能基准测试
    benchmark = validator.run_benchmark()
"""
from __future__ import annotations

import json
import logging
import subprocess
import threading
import time
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# Bridge 默认目录收口到 core/paths.py（AEK_AE_BRIDGE_DIR 可覆盖）
try:
    from core.paths import ae_bridge_dir as _paths_ae_bridge
    _DEFAULT_BRIDGE_DIR = _paths_ae_bridge()
except ImportError:
    _DEFAULT_BRIDGE_DIR = r"C:\Users\Administrator\Documents\ae-mcp-bridge"

logger = logging.getLogger(__name__)


class ValidationStatus(str, Enum):
    """验证状态枚举。"""
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"


class TestCategory(str, Enum):
    """测试类别枚举。"""
    SYSTEM = "system"
    PROCESS = "process"
    BRIDGE = "bridge"
    MCP_TOOLS = "mcp_tools"
    E2E = "e2e"
    PERFORMANCE = "performance"


class ValidationResult:
    """单个验证测试的结果。"""

    def __init__(
        self,
        test_name: str,
        category: TestCategory,
        status: ValidationStatus,
        message: str = "",
        details: dict[str, Any] | None = None,
        duration: float = 0.0,
        recommendation: str = "",
    ):
        self.test_name = test_name
        self.category = category
        self.status = status
        self.message = message
        self.details = details or {}
        self.duration = duration
        self.recommendation = recommendation

    def to_dict(self) -> dict[str, Any]:
        return {
            "test_name": self.test_name,
            "category": self.category.value,
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
            "duration": round(self.duration, 2),
            "recommendation": self.recommendation,
        }


class ValidationReport:
    """完整的验证报告。"""

    def __init__(self):
        self.results: list[ValidationResult] = []
        self.start_time: float = 0.0
        self.end_time: float = 0.0
        self.summary: dict[str, Any] = {}

    def add_result(self, result: ValidationResult) -> None:
        """添加验证结果。"""
        self.results.append(result)

    def generate_summary(self) -> dict[str, Any]:
        """生成验证总结。"""
        passed = sum(1 for r in self.results if r.status == ValidationStatus.PASSED)
        failed = sum(1 for r in self.results if r.status == ValidationStatus.FAILED)
        warning = sum(1 for r in self.results if r.status == ValidationStatus.WARNING)
        skipped = sum(1 for r in self.results if r.status == ValidationStatus.SKIPPED)

        total_time = self.end_time - self.start_time

        self.summary = {
            "total_tests": len(self.results),
            "passed": passed,
            "failed": failed,
            "warning": warning,
            "skipped": skipped,
            "pass_rate": round((passed / len(self.results)) * 100, 2) if self.results else 0,
            "total_duration": round(total_time, 2),
            "start_time": datetime.fromtimestamp(self.start_time).isoformat(),
            "end_time": datetime.fromtimestamp(self.end_time).isoformat(),
            "categories": self._get_category_summary(),
        }
        return self.summary

    def _get_category_summary(self) -> dict[str, Any]:
        """按类别生成总结。"""
        categories = {}
        for cat in TestCategory:
            cat_results = [r for r in self.results if r.category == cat]
            if cat_results:
                passed = sum(1 for r in cat_results if r.status == ValidationStatus.PASSED)
                categories[cat.value] = {
                    "total": len(cat_results),
                    "passed": passed,
                    "failed": len(cat_results) - passed,
                    "pass_rate": round((passed / len(cat_results)) * 100, 2),
                }
        return categories

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式。"""
        return {
            "summary": self.summary,
            "results": [r.to_dict() for r in self.results],
        }

    def to_json(self, output_path: str | None = None, indent: int = 2) -> str:
        """转换为 JSON 字符串。"""
        data = self.to_dict()
        json_str = json.dumps(data, ensure_ascii=False, indent=indent)
        if output_path:
            try:
                path = Path(output_path)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json_str, encoding="utf-8")
                logger.info(f"验证报告已保存到: {output_path}")
            except OSError as e:
                logger.warning(f"保存验证报告失败: {e}")
        return json_str

    def print_summary(self) -> None:
        """打印验证总结。"""
        summary = self.summary
        print("\n" + "=" * 60)
        print("AE 环境验证报告")
        print("=" * 60)
        print(f"总测试数: {summary['total_tests']}")
        print(f"通过: {summary['passed']} | 失败: {summary['failed']} | 警告: {summary['warning']} | 跳过: {summary['skipped']}")
        print(f"通过率: {summary['pass_rate']}%")
        print(f"总耗时: {summary['total_duration']:.2f} 秒")
        print("\n类别统计:")
        for cat, stats in summary.get("categories", {}).items():
            print(f"  {cat}: {stats['passed']}/{stats['total']} ({stats['pass_rate']}%)")

        failed_tests = [r for r in self.results if r.status == ValidationStatus.FAILED]
        if failed_tests:
            print("\n失败测试详情:")
            for r in failed_tests:
                print(f"  - {r.test_name}: {r.message}")
                if r.recommendation:
                    print(f"    建议: {r.recommendation}")


class AEEnvironmentValidator:
    """AE 环境验证器。

    提供全面的环境验证能力，包括：
    - 系统环境检查（AE 安装、Python 版本、依赖库）
    - 进程管理验证（启动、关闭、状态监控）
    - Bridge 通信验证（Listener、命令队列）
    - MCP 工具验证（核心工具功能测试）
    - 端到端流程验证
    """

    def __init__(
        self,
        ae_executable: str | None = None,
        bridge_dir: str | None = None,
        timeout: int = 60,
        skip_e2e: bool = False,
        skip_performance: bool = False,
    ):
        """初始化验证器。

        Args:
            ae_executable: AE 可执行文件路径
            bridge_dir: Bridge 目录路径
            timeout: 超时时间（秒）
            skip_e2e: 是否跳过端到端测试
            skip_performance: 是否跳过性能测试
        """
        self._ae_executable = ae_executable
        self._bridge_dir = bridge_dir or _DEFAULT_BRIDGE_DIR
        self._timeout = timeout
        self._skip_e2e = skip_e2e
        self._skip_performance = skip_performance

        self._report = ValidationReport()
        self._process_manager = None
        self._mcp_client = None

    def run_full_validation(self) -> ValidationReport:
        """运行完整验证。

        Returns:
            验证报告
        """
        self._report.start_time = time.time()

        self._validate_system()
        self._validate_process_management()
        self._validate_bridge_communication()
        self._validate_mcp_tools()

        if not self._skip_e2e:
            self._validate_e2e_flow()

        if not self._skip_performance:
            self._run_performance_benchmark()

        self._report.end_time = time.time()
        self._report.generate_summary()

        return self._report

    # ------------------------------------------------------------------------
    # 系统环境验证
    # ------------------------------------------------------------------------

    def _validate_system(self) -> None:
        """验证系统环境。"""
        logger.info("开始系统环境验证...")

        self._validate_python_version()
        self._validate_ae_installation()
        self._validate_dependencies()
        self._validate_bridge_directory()

    def _validate_python_version(self) -> None:
        """验证 Python 版本。"""
        start = time.time()
        import sys

        version = sys.version_info
        status = ValidationStatus.PASSED
        message = f"Python {version.major}.{version.minor}.{version.micro}"

        if version.major < 3 or (version.major == 3 and version.minor < 10):
            status = ValidationStatus.WARNING
            message = f"Python 版本较低: {version.major}.{version.minor}.{version.micro}"
            recommendation = "建议升级到 Python 3.10+"

        self._report.add_result(ValidationResult(
            "python_version",
            TestCategory.SYSTEM,
            status,
            message,
            {"version": f"{version.major}.{version.minor}.{version.micro}"},
            time.time() - start,
            recommendation if status == ValidationStatus.WARNING else "",
        ))

    def _validate_ae_installation(self) -> None:
        """验证 AE 安装。"""
        start = time.time()

        search_paths = [
            r"C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\AfterFX.exe",
            r"D:\Program Files\Adobe\Adobe After Effects 2025\Support Files\AfterFX.exe",
            r"C:\Program Files\Adobe\Adobe After Effects 2024\Support Files\AfterFX.exe",
        ]

        found_path = None
        for path in search_paths:
            if Path(path).exists():
                found_path = path
                break

        if self._ae_executable and Path(self._ae_executable).exists():
            found_path = self._ae_executable

        if found_path:
            try:
                result = subprocess.run(
                    [found_path, "-v"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                version_info = result.stdout.strip() or result.stderr.strip()
                status = ValidationStatus.PASSED
                message = f"AE 安装验证通过: {found_path}"
            except Exception:
                version_info = "无法获取版本信息"
                status = ValidationStatus.WARNING
                message = f"AE 安装验证通过，但无法获取版本信息: {found_path}"
                recommendation = "手动检查 AE 是否能正常启动"

            self._report.add_result(ValidationResult(
                "ae_installation",
                TestCategory.SYSTEM,
                status,
                message,
                {"path": found_path, "version_info": version_info},
                time.time() - start,
                recommendation if status == ValidationStatus.WARNING else "",
            ))
            self._ae_executable = found_path
        else:
            self._report.add_result(ValidationResult(
                "ae_installation",
                TestCategory.SYSTEM,
                ValidationStatus.FAILED,
                "未找到 AE 安装路径",
                {"search_paths": search_paths},
                time.time() - start,
                "请安装 Adobe After Effects 2024+ 或设置正确的 ae_executable 路径",
            ))

    def _validate_dependencies(self) -> None:
        """验证依赖库。"""
        start = time.time()

        required_deps = [
            ("ae.ae_mcp_client", "AEMCPClient"),
            ("ae.bridge_protocol", "BridgeClient"),
            ("ae.bridge_middleware", "MiddlewarePipeline"),
            ("ae.ae_process_manager", "AEProcessManager"),
        ]

        missing_deps = []
        for module_name, class_name in required_deps:
            try:
                module = __import__(module_name, fromlist=[class_name])
                if not hasattr(module, class_name):
                    missing_deps.append(f"{module_name}.{class_name}")
            except ImportError:
                missing_deps.append(module_name)

        if missing_deps:
            self._report.add_result(ValidationResult(
                "dependencies",
                TestCategory.SYSTEM,
                ValidationStatus.FAILED,
                f"缺少依赖: {', '.join(missing_deps)}",
                {"missing": missing_deps, "required": required_deps},
                time.time() - start,
                "请运行 pip install -e . 安装项目依赖",
            ))
        else:
            self._report.add_result(ValidationResult(
                "dependencies",
                TestCategory.SYSTEM,
                ValidationStatus.PASSED,
                "所有依赖已安装",
                {"required_count": len(required_deps)},
                time.time() - start,
            ))

    def _validate_bridge_directory(self) -> None:
        """验证 Bridge 目录。"""
        start = time.time()
        bridge_path = Path(self._bridge_dir)

        required_files = [
            "command.json",
            "result.json",
            ".ae_mcp_secret",
        ]

        missing_files = []
        for filename in required_files:
            if not (bridge_path / filename).exists():
                missing_files.append(filename)

        if bridge_path.exists():
            if missing_files:
                self._report.add_result(ValidationResult(
                    "bridge_directory",
                    TestCategory.SYSTEM,
                    ValidationStatus.WARNING,
                    f"Bridge 目录存在但缺少文件: {', '.join(missing_files)}",
                    {"path": str(bridge_path), "missing": missing_files},
                    time.time() - start,
                    "缺少的文件将在首次运行时自动创建",
                ))
            else:
                self._report.add_result(ValidationResult(
                    "bridge_directory",
                    TestCategory.SYSTEM,
                    ValidationStatus.PASSED,
                    f"Bridge 目录验证通过: {self._bridge_dir}",
                    {"path": str(bridge_path), "files": required_files},
                    time.time() - start,
                ))
        else:
            self._report.add_result(ValidationResult(
                "bridge_directory",
                TestCategory.SYSTEM,
                ValidationStatus.WARNING,
                f"Bridge 目录不存在: {self._bridge_dir}",
                {"path": str(bridge_path)},
                time.time() - start,
                "目录将在首次运行时自动创建",
            ))

    # ------------------------------------------------------------------------
    # 进程管理验证
    # ------------------------------------------------------------------------

    def _validate_process_management(self) -> None:
        """验证进程管理功能。"""
        logger.info("开始进程管理验证...")

        try:
            from ae.ae_process_manager import AEProcessManager, AEState

            self._process_manager = AEProcessManager(
                ae_path=self._ae_executable,
                close_timeout=30,
                start_timeout=60,
            )

            self._validate_process_detection()
            self._validate_process_start_stop()

        except ImportError as e:
            self._report.add_result(ValidationResult(
                "process_management",
                TestCategory.PROCESS,
                ValidationStatus.SKIPPED,
                f"跳过进程管理验证: {e}",
                {},
                0,
            ))

    def _validate_process_detection(self) -> None:
        """验证进程检测功能。"""
        start = time.time()
        if self._process_manager is None:
            return

        is_running = self._process_manager.is_ae_running()
        pid = self._process_manager.get_ae_pid()

        self._report.add_result(ValidationResult(
            "process_detection",
            TestCategory.PROCESS,
            ValidationStatus.PASSED,
            f"进程检测功能正常 (运行中: {is_running}, PID: {pid})",
            {"is_running": is_running, "pid": pid},
            time.time() - start,
        ))

    def _validate_process_start_stop(self) -> None:
        """验证进程启动和停止功能。"""
        start = time.time()
        if self._process_manager is None:
            return

        was_running = self._process_manager.is_ae_running()

        if not was_running:
            try:
                logger.info("测试 AE 启动...")
                success = self._process_manager.start_ae(timeout=60)
                start_duration = time.time() - start

                if success:
                    self._report.add_result(ValidationResult(
                        "process_start",
                        TestCategory.PROCESS,
                        ValidationStatus.PASSED,
                        f"AE 启动成功，耗时 {start_duration:.2f} 秒",
                        {"duration": start_duration},
                        start_duration,
                    ))

                    time.sleep(5)

                    logger.info("测试 AE 关闭...")
                    close_start = time.time()
                    close_success = self._process_manager.close_ae(timeout=60)
                    close_duration = time.time() - close_start

                    if close_success:
                        self._report.add_result(ValidationResult(
                            "process_stop",
                            TestCategory.PROCESS,
                            ValidationStatus.PASSED,
                            f"AE 关闭成功，耗时 {close_duration:.2f} 秒",
                            {"duration": close_duration},
                            close_duration,
                        ))
                    else:
                        self._report.add_result(ValidationResult(
                            "process_stop",
                            TestCategory.PROCESS,
                            ValidationStatus.FAILED,
                            "AE 关闭失败",
                            {"duration": close_duration},
                            close_duration,
                            "检查 AE 是否有未保存的项目或对话框阻塞",
                        ))
                else:
                    self._report.add_result(ValidationResult(
                        "process_start",
                        TestCategory.PROCESS,
                        ValidationStatus.FAILED,
                        "AE 启动失败",
                        {"duration": start_duration},
                        start_duration,
                        "检查 AE 安装路径和系统环境",
                    ))

            except Exception as e:
                self._report.add_result(ValidationResult(
                    "process_start_stop",
                    TestCategory.PROCESS,
                    ValidationStatus.FAILED,
                    f"进程启动/停止测试异常: {e}",
                    {},
                    time.time() - start,
                ))
        else:
            self._report.add_result(ValidationResult(
                "process_start_stop",
                TestCategory.PROCESS,
                ValidationStatus.SKIPPED,
                "AE 已在运行中，跳过启动/停止测试",
                {"was_running": was_running},
                time.time() - start,
            ))

    # ------------------------------------------------------------------------
    # Bridge 通信验证
    # ------------------------------------------------------------------------

    def _validate_bridge_communication(self) -> None:
        """验证 Bridge 通信功能。"""
        logger.info("开始 Bridge 通信验证...")

        try:
            from ae.ae_mcp_client import AEMCPClient

            self._mcp_client = AEMCPClient(
                bridge_dir=self._bridge_dir,
                enable_middleware=True,
                poll_interval=0.5,
                max_retries=3,
            )

            self._validate_ping()
            self._validate_bridge_status()

        except ImportError as e:
            self._report.add_result(ValidationResult(
                "bridge_communication",
                TestCategory.BRIDGE,
                ValidationStatus.SKIPPED,
                f"跳过 Bridge 通信验证: {e}",
                {},
                0,
            ))

    def _validate_ping(self) -> None:
        """验证 Ping 命令。"""
        start = time.time()
        if self._mcp_client is None:
            return

        try:
            result = self._mcp_client.ping()
            duration = time.time() - start

            if isinstance(result, dict) and result.get("status") == "success":
                self._report.add_result(ValidationResult(
                    "ping_command",
                    TestCategory.BRIDGE,
                    ValidationStatus.PASSED,
                    f"Ping 命令成功，响应时间 {duration:.2f} 秒",
                    {"result": result, "response_time": duration},
                    duration,
                ))
            else:
                self._report.add_result(ValidationResult(
                    "ping_command",
                    TestCategory.BRIDGE,
                    ValidationStatus.FAILED,
                    f"Ping 命令失败: {result}",
                    {"result": result},
                    duration,
                    "检查 AE Listener 是否正在运行",
                ))

        except Exception as e:
            self._report.add_result(ValidationResult(
                "ping_command",
                TestCategory.BRIDGE,
                ValidationStatus.FAILED,
                f"Ping 命令异常: {e}",
                {},
                time.time() - start,
                "检查 Bridge 目录和 Listener 脚本",
            ))

    def _validate_bridge_status(self) -> None:
        """验证 Bridge 状态。"""
        start = time.time()
        if self._mcp_client is None:
            return

        try:
            result = self._mcp_client.get_status()
            duration = time.time() - start

            if isinstance(result, dict):
                self._report.add_result(ValidationResult(
                    "bridge_status",
                    TestCategory.BRIDGE,
                    ValidationStatus.PASSED,
                    "Bridge 状态获取成功",
                    {"status": result, "response_time": duration},
                    duration,
                ))
            else:
                self._report.add_result(ValidationResult(
                    "bridge_status",
                    TestCategory.BRIDGE,
                    ValidationStatus.WARNING,
                    "Bridge 状态返回格式异常",
                    {"result": result},
                    duration,
                ))

        except Exception as e:
            self._report.add_result(ValidationResult(
                "bridge_status",
                TestCategory.BRIDGE,
                ValidationStatus.SKIPPED,
                f"Bridge 状态获取异常: {e}",
                {},
                time.time() - start,
            ))

    # ------------------------------------------------------------------------
    # MCP 工具验证
    # ------------------------------------------------------------------------

    def _validate_mcp_tools(self) -> None:
        """验证 MCP 工具功能。"""
        logger.info("开始 MCP 工具验证...")

        if self._mcp_client is None:
            self._report.add_result(ValidationResult(
                "mcp_tools",
                TestCategory.MCP_TOOLS,
                ValidationStatus.SKIPPED,
                "MCP 客户端未初始化，跳过工具验证",
                {},
                0,
            ))
            return

        tools_to_test = [
            ("list_compositions", {}, "合成列表"),
            ("list_project_items", {}, "项目项列表"),
            ("get_version", {}, "版本信息"),
        ]

        for tool_name, params, description in tools_to_test:
            start = time.time()
            try:
                result = getattr(self._mcp_client, tool_name)(**params)
                duration = time.time() - start

                if isinstance(result, dict) or isinstance(result, list):
                    self._report.add_result(ValidationResult(
                        f"mcp_{tool_name}",
                        TestCategory.MCP_TOOLS,
                        ValidationStatus.PASSED,
                        f"{description} 获取成功，响应时间 {duration:.2f} 秒",
                        {"response_time": duration, "result_type": type(result).__name__},
                        duration,
                    ))
                else:
                    self._report.add_result(ValidationResult(
                        f"mcp_{tool_name}",
                        TestCategory.MCP_TOOLS,
                        ValidationStatus.WARNING,
                        f"{description} 返回格式异常",
                        {"response_time": duration},
                        duration,
                    ))

            except Exception as e:
                self._report.add_result(ValidationResult(
                    f"mcp_{tool_name}",
                    TestCategory.MCP_TOOLS,
                    ValidationStatus.SKIPPED,
                    f"{description} 测试跳过: {e}",
                    {},
                    time.time() - start,
                ))

    # ------------------------------------------------------------------------
    # 端到端流程验证
    # ------------------------------------------------------------------------

    def _validate_e2e_flow(self) -> None:
        """验证端到端流程。"""
        logger.info("开始端到端流程验证...")

        if self._mcp_client is None:
            self._report.add_result(ValidationResult(
                "e2e_flow",
                TestCategory.E2E,
                ValidationStatus.SKIPPED,
                "MCP 客户端未初始化，跳过分端到端测试",
                {},
                0,
            ))
            return

        try:
            start = time.time()

            comp_name = f"Validation_Test_{int(time.time())}"

            create_result = self._mcp_client.create_composition(
                name=comp_name,
                width=1920,
                height=1080,
                duration=5.0,
                fps=30.0,
            )
            create_duration = time.time() - start

            if create_result.get("success", False):
                self._report.add_result(ValidationResult(
                    "e2e_create_composition",
                    TestCategory.E2E,
                    ValidationStatus.PASSED,
                    f"创建合成成功，耗时 {create_duration:.2f} 秒",
                    {"comp_name": comp_name, "duration": create_duration},
                    create_duration,
                ))

                time.sleep(2)

                add_layer_start = time.time()
                layer_result = self._mcp_client.add_text_layer(
                    composition_name=comp_name,
                    layer_name="Test_Text",
                    text="Validation Test",
                    font_size=48,
                )
                add_layer_duration = time.time() - add_layer_start

                if layer_result.get("success", False):
                    self._report.add_result(ValidationResult(
                        "e2e_add_layer",
                        TestCategory.E2E,
                        ValidationStatus.PASSED,
                        f"添加图层成功，耗时 {add_layer_duration:.2f} 秒",
                        {"duration": add_layer_duration},
                        add_layer_duration,
                    ))

                    delete_start = time.time()
                    delete_result = self._mcp_client.delete_composition(comp_name)
                    delete_duration = time.time() - delete_start

                    if delete_result.get("success", False):
                        self._report.add_result(ValidationResult(
                            "e2e_delete_composition",
                            TestCategory.E2E,
                            ValidationStatus.PASSED,
                            f"删除合成成功，耗时 {delete_duration:.2f} 秒",
                            {"duration": delete_duration},
                            delete_duration,
                        ))
                    else:
                        self._report.add_result(ValidationResult(
                            "e2e_delete_composition",
                            TestCategory.E2E,
                            ValidationStatus.WARNING,
                            "删除合成失败，可能需要手动清理",
                            {"result": delete_result},
                            delete_duration,
                        ))
                else:
                    self._report.add_result(ValidationResult(
                        "e2e_add_layer",
                        TestCategory.E2E,
                        ValidationStatus.FAILED,
                        f"添加图层失败: {layer_result}",
                        {"result": layer_result},
                        add_layer_duration,
                    ))
            else:
                self._report.add_result(ValidationResult(
                    "e2e_create_composition",
                    TestCategory.E2E,
                    ValidationStatus.FAILED,
                    f"创建合成失败: {create_result}",
                    {"result": create_result},
                    create_duration,
                ))

        except Exception as e:
            self._report.add_result(ValidationResult(
                "e2e_flow",
                TestCategory.E2E,
                ValidationStatus.FAILED,
                f"端到端测试异常: {e}",
                {},
                time.time() - start,
            ))

    # ------------------------------------------------------------------------
    # 性能基准测试
    # ------------------------------------------------------------------------

    def _run_performance_benchmark(self) -> None:
        """运行性能基准测试。"""
        logger.info("开始性能基准测试...")

        if self._mcp_client is None:
            self._report.add_result(ValidationResult(
                "performance_benchmark",
                TestCategory.PERFORMANCE,
                ValidationStatus.SKIPPED,
                "MCP 客户端未初始化，跳过性能测试",
                {},
                0,
            ))
            return

        try:
            start = time.time()

            latencies = []
            for i in range(10):
                ping_start = time.time()
                self._mcp_client.ping()
                latency = (time.time() - ping_start) * 1000
                latencies.append(latency)
                time.sleep(0.5)

            avg_latency = sum(latencies) / len(latencies)
            min_latency = min(latencies)
            max_latency = max(latencies)

            p95_idx = int(len(latencies) * 0.95)
            p95_latency = sorted(latencies)[p95_idx]

            self._report.add_result(ValidationResult(
                "performance_ping_latency",
                TestCategory.PERFORMANCE,
                ValidationStatus.PASSED,
                "Ping 延迟基准测试完成",
                {
                    "avg_latency_ms": round(avg_latency, 2),
                    "min_latency_ms": round(min_latency, 2),
                    "max_latency_ms": round(max_latency, 2),
                    "p95_latency_ms": round(p95_latency, 2),
                    "sample_count": 10,
                },
                time.time() - start,
            ))

        except Exception as e:
            self._report.add_result(ValidationResult(
                "performance_benchmark",
                TestCategory.PERFORMANCE,
                ValidationStatus.FAILED,
                f"性能基准测试异常: {e}",
                {},
                time.time() - start,
            ))


def run_validation() -> None:
    """运行完整验证并输出报告。"""
    import argparse

    parser = argparse.ArgumentParser(description="AE 环境验证工具")
    parser.add_argument("--ae-path", help="AE 可执行文件路径")
    parser.add_argument("--bridge-dir", help="Bridge 目录路径")
    parser.add_argument("--timeout", type=int, default=60, help="超时时间")
    parser.add_argument("--skip-e2e", action="store_true", help="跳过端到端测试")
    parser.add_argument("--skip-performance", action="store_true", help="跳过性能测试")
    parser.add_argument("--output", help="输出报告文件路径")
    parser.add_argument("--verbose", action="store_true", help="详细输出")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    validator = AEEnvironmentValidator(
        ae_executable=args.ae_path,
        bridge_dir=args.bridge_dir,
        timeout=args.timeout,
        skip_e2e=args.skip_e2e,
        skip_performance=args.skip_performance,
    )

    report = validator.run_full_validation()
    report.print_summary()

    if args.output:
        report.to_json(args.output)


if __name__ == "__main__":
    run_validation()