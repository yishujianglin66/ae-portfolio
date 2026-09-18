"""
AE 稳定性测试 pytest 配置与共享 Fixtures
==========================================

提供生产级稳定性测试所需的基础设施：
- AE 进程管理器 fixture (session 级别)
- Bridge 客户端 fixture
- 测试项目文件 fixture
- 测试配置管理
- 失败诊断信息收集（截图、日志、进程状态）
- 测试数据目录管理
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import time
import traceback
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

import pytest

# 确保项目根目录和 ae 模块在 Python 路径中
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
AE_DIR = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(AE_DIR.parent) not in sys.path:
    sys.path.insert(0, str(AE_DIR.parent))


# ---------------------------------------------------------------------------
# 测试配置
# ---------------------------------------------------------------------------

class TestEnvironment(str, Enum):
    """测试环境类型。"""

    MOCK = "mock"
    LOCAL = "local"
    CI = "ci"
    PRODUCTION = "production"


class StabilityTestConfig:
    """稳定性测试配置。

    从环境变量或配置文件读取测试配置。
    环境变量优先级高于配置文件。

    环境变量列表：
    - AE_TEST_ENV: 测试环境 (mock/local/ci/production)
    - AE_TEST_BRIDGE_DIR: Bridge 通信目录
    - AE_TEST_AE_EXE_PATH: AE 可执行文件路径
    - AE_TEST_LISTENER_SCRIPT: Listener 脚本路径
    - AE_TEST_SKIP_REAL_AE: 是否跳过需要真实 AE 的测试
    - AE_TEST_TIMEOUT_MULTIPLIER: 超时时间倍率
    - AE_TEST_OUTPUT_DIR: 测试输出目录
    - AE_TEST_KEEP_AE_RUNNING: 测试后保持 AE 运行
    """

    def __init__(self) -> None:
        self.env: TestEnvironment = TestEnvironment(
            os.environ.get("AE_TEST_ENV", "mock")
        )
        self.bridge_dir: Path = Path(
            os.environ.get(
                "AE_TEST_BRIDGE_DIR",
                Path.home() / "Documents" / "ae-mcp-bridge-test",
            )
        )
        self.ae_exe_path: Path | None = None
        ae_exe = os.environ.get("AE_TEST_AE_EXE_PATH", "")
        if ae_exe:
            self.ae_exe_path = Path(ae_exe)
        self.listener_script: Path | None = None
        listener = os.environ.get("AE_TEST_LISTENER_SCRIPT", "")
        if listener:
            self.listener_script = Path(listener)
        self.skip_real_ae: bool = (
            os.environ.get("AE_TEST_SKIP_REAL_AE", "1") == "1"
            or self.env == TestEnvironment.MOCK
            or self.env == TestEnvironment.CI
        )
        self.timeout_multiplier: float = float(
            os.environ.get("AE_TEST_TIMEOUT_MULTIPLIER", "1.0")
        )
        self.output_dir: Path = Path(
            os.environ.get(
                "AE_TEST_OUTPUT_DIR",
                PROJECT_ROOT / "test_outputs" / "stability",
            )
        )
        self.keep_ae_running: bool = (
            os.environ.get("AE_TEST_KEEP_AE_RUNNING", "0") == "1"
        )
        self.max_restart_attempts: int = int(
            os.environ.get("AE_TEST_MAX_RESTART_ATTEMPTS", "3")
        )
        self.stress_iterations: int = int(
            os.environ.get("AE_TEST_STRESS_ITERATIONS", "100")
        )
        self.soak_duration_minutes: int = int(
            os.environ.get("AE_TEST_SOAK_DURATION_MINUTES", "5")
        )

    @property
    def use_real_ae(self) -> bool:
        """是否使用真实 AE 进行测试。"""
        return not self.skip_real_ae

    def get_timeout(self, base_seconds: float) -> float:
        """获取带倍率的超时时间。"""
        return base_seconds * self.timeout_multiplier

    def ensure_output_dirs(self) -> dict[str, Path]:
        """确保输出目录存在。"""
        dirs = {
            "root": self.output_dir,
            "logs": self.output_dir / "logs",
            "screenshots": self.output_dir / "screenshots",
            "reports": self.output_dir / "reports",
            "artifacts": self.output_dir / "artifacts",
            "diagnostics": self.output_dir / "diagnostics",
        }
        for d in dirs.values():
            d.mkdir(parents=True, exist_ok=True)
        return dirs


# ---------------------------------------------------------------------------
# 全局配置 fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def test_config() -> StabilityTestConfig:
    """测试配置（session 级别）。"""
    config = StabilityTestConfig()
    config.ensure_output_dirs()
    return config


# ---------------------------------------------------------------------------
# 测试数据目录管理
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def test_data_dir(test_config: StabilityTestConfig) -> Path:
    """测试数据根目录（session 级别）。"""
    data_dir = test_config.output_dir / "test_data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


@pytest.fixture
def test_artifacts_dir(
    test_config: StabilityTestConfig, request: pytest.FixtureRequest
) -> Path:
    """每个测试用例的产物目录。"""
    test_name = request.node.name
    test_class = request.node.cls.__name__ if request.node.cls else "no_class"
    artifacts_dir = (
        test_config.output_dir
        / "artifacts"
        / test_class
        / test_name
    )
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    return artifacts_dir


# ---------------------------------------------------------------------------
# Bridge 客户端 Fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def bridge_client(test_config: StabilityTestConfig):
    """Bridge 客户端（session 级别）。

    根据测试环境选择：
    - mock 环境：使用模拟 BridgeServer（内置 Python 实现）
    - 真实环境：连接真实 AE Bridge
    """
    from ae.bridge_protocol import BridgeClient, BridgeServer

    bridge_dir = test_config.bridge_dir
    # 清理旧的测试目录
    if bridge_dir.exists():
        shutil.rmtree(bridge_dir, ignore_errors=True)
    bridge_dir.mkdir(parents=True, exist_ok=True)

    if test_config.env == TestEnvironment.MOCK:
        # 启动模拟服务端
        server = BridgeServer(
            bridge_dir=str(bridge_dir),
            signature_enabled=False,
            poll_interval=0.01,
            use_queue_mode=False,
        )
        # 注册基础处理函数
        server.register_handler("ping", lambda params: {"pong": True, "timestamp": time.time()})
        server.register_handler(
            "echo", lambda params: {"echo": params.get("message", "")}
        )
        server.register_handler(
            "create_composition",
            lambda params: {
                "comp_id": f"comp_{int(time.time())}",
                "name": params.get("name", "TestComp"),
                "width": params.get("width", 1920),
                "height": params.get("height", 1080),
                "duration": params.get("duration", 5.0),
                "frame_rate": params.get("frame_rate", 30),
            },
        )
        server.register_handler(
            "get_project_info",
            lambda params: {
                "project_name": "Test Project",
                "path": str(bridge_dir / "test.aep"),
                "compositions": [],
            },
        )
        server.register_handler(
            "create_solid_layer",
            lambda params: {
                "layer_id": f"layer_{int(time.time())}",
                "name": params.get("name", "Solid"),
                "index": 1,
            },
        )
        server.register_handler(
            "apply_effect",
            lambda params: {
                "effect_name": params.get("effect_name", ""),
                "applied": True,
            },
        )
        server.register_handler(
            "set_property",
            lambda params: {
                "property": params.get("property", ""),
                "value": params.get("value"),
                "set": True,
            },
        )
        server.register_handler(
            "add_keyframe",
            lambda params: {
                "keyframe_id": f"kf_{int(time.time())}",
                "time": params.get("time", 0),
                "value": params.get("value"),
            },
        )
        server.register_handler(
            "undo", lambda params: {"undone": True, "steps": params.get("steps", 1)}
        )
        server.register_handler(
            "redo", lambda params: {"redone": True, "steps": params.get("steps", 1)}
        )
        server.register_handler(
            "save_project",
            lambda params: {
                "saved": True,
                "path": params.get("path", str(bridge_dir / "test.aep")),
            },
        )
        server.register_handler(
            "open_project",
            lambda params: {
                "opened": True,
                "path": params.get("path", ""),
            },
        )
        server.register_handler(
            "delete_layer",
            lambda params: {"deleted": True, "layer_id": params.get("layer_id")},
        )
        server.register_handler(
            "delete_composition",
            lambda params: {"deleted": True, "comp_id": params.get("comp_id")},
        )
        server.register_handler(
            "get_composition_list",
            lambda params: {
                "compositions": [
                    {"id": "comp_1", "name": "Comp 1", "width": 1920, "height": 1080}
                ]
            },
        )
        server.register_handler(
            "get_layer_list",
            lambda params: {
                "layers": [
                    {"id": "layer_1", "name": "Layer 1", "type": "solid", "index": 1}
                ]
            },
        )

        server_thread = server.start_background()
        time.sleep(0.1)  # 等待服务启动

        client = BridgeClient(
            bridge_dir=str(bridge_dir),
            signature_enabled=False,
            poll_interval=0.01,
            max_retries=3,
        )

        yield client

        server.stop()
    else:
        # 真实环境
        client = BridgeClient(
            bridge_dir=str(bridge_dir),
            signature_enabled=False,
            poll_interval=0.1,
            max_retries=3,
        )
        yield client


# ---------------------------------------------------------------------------
# AE 进程管理器 Fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def ae_process_manager(test_config: StabilityTestConfig):
    """AE 进程管理器（session 级别）。

    Mock 环境下返回 None，使用模拟测试。
    真实环境下创建并管理 AE 进程生命周期。
    """
    if test_config.skip_real_ae:
        yield None
        return

    from ae.ae_process_manager import AEProcessManager

    kwargs: dict[str, Any] = {}
    if test_config.ae_exe_path:
        kwargs["ae_exe_path"] = str(test_config.ae_exe_path)
    if test_config.listener_script:
        kwargs["listener_script_path"] = str(test_config.listener_script)

    manager = AEProcessManager(**kwargs)
    yield manager

    # 测试结束后清理
    if not test_config.keep_ae_running:
        try:
            if manager.is_ae_running():
                manager.close_ae()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# 测试项目文件 Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def test_project_path(test_artifacts_dir: Path) -> Path:
    """测试项目文件路径。"""
    return test_artifacts_dir / "test_project.aep"


# ---------------------------------------------------------------------------
# 日志收集 Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def test_logger(
    test_config: StabilityTestConfig,
    test_artifacts_dir: Path,
    request: pytest.FixtureRequest,
) -> dict[str, Any]:
    """测试日志收集器。

    收集测试执行过程中的日志，失败时自动保存。
    """
    import logging

    test_name = request.node.name
    log_file = test_artifacts_dir / f"{test_name}.log"

    logger = logging.getLogger(f"ae_stability_test.{test_name}")
    logger.setLevel(logging.DEBUG)

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    log_info: dict[str, Any] = {
        "logger": logger,
        "log_file": log_file,
        "start_time": time.time(),
        "events": [],
    }

    def log_event(event_type: str, data: Any = None) -> None:
        event = {
            "time": time.time(),
            "type": event_type,
            "data": data,
        }
        log_info["events"].append(event)
        logger.info(f"EVENT [{event_type}]: {json.dumps(data, default=str, ensure_ascii=False) if data else ''}")

    log_info["log_event"] = log_event

    yield log_info

    # 测试结束时清理
    logger.removeHandler(fh)
    fh.close()


# ---------------------------------------------------------------------------
# 失败诊断信息收集
# ---------------------------------------------------------------------------

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """收集测试失败时的诊断信息。"""
    outcome = yield
    rep = outcome.get_result()

    if rep.when == "call" and rep.failed:
        # 测试失败，收集诊断信息
        try:
            config = StabilityTestConfig()
            diag_dir = config.output_dir / "diagnostics"
            diag_dir.mkdir(parents=True, exist_ok=True)

            test_name = item.name
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            diag_file = diag_dir / f"{test_name}_{timestamp}.json"

            diagnostics: dict[str, Any] = {
                "test_name": test_name,
                "test_path": str(item.fspath),
                "timestamp": timestamp,
                "error_type": call.excinfo.typename if call.excinfo else None,
                "error_message": str(call.excinfo.value) if call.excinfo else None,
                "traceback": traceback.format_exc(),
                "environment": {
                    "python_version": sys.version,
                    "platform": sys.platform,
                },
            }

            # 尝试收集进程信息
            try:
                import psutil

                diagnostics["processes"] = []
                for proc in psutil.process_iter(["name", "pid", "cpu_percent", "memory_info"]):
                    try:
                        if "afterfx" in proc.info["name"].lower() or "ae" in proc.info["name"].lower():
                            diagnostics["processes"].append(
                                {
                                    "name": proc.info["name"],
                                    "pid": proc.info["pid"],
                                    "cpu_percent": proc.info["cpu_percent"],
                                    "memory_mb": round(
                                        proc.info["memory_info"].rss / 1024 / 1024, 2
                                    )
                                    if proc.info["memory_info"]
                                    else None,
                                }
                            )
                    except Exception:
                        pass
            except ImportError:
                pass

            with open(diag_file, "w", encoding="utf-8") as f:
                json.dump(diagnostics, f, ensure_ascii=False, indent=2)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# 自定义标记
# ---------------------------------------------------------------------------

def pytest_configure(config):
    """注册 AE 稳定性测试自定义标记。"""
    markers = [
        "smoke: 烟雾测试，快速验证基本功能（30秒内）",
        "process_lifecycle: 进程生命周期测试",
        "bridge_stability: Bridge 通信稳定性测试",
        "ae_operations: AE 操作稳定性测试",
        "stress: 压力测试",
        "soak: 耐久测试（长时间运行）",
        "real_ae_required: 需要真实 AE 环境的测试",
        "benchmark: 基准性能测试",
    ]
    for marker in markers:
        config.addinivalue_line("markers", marker)


def pytest_collection_modifyitems(config, items):
    """自动标记需要真实 AE 的测试。"""
    for item in items:
        # 根据文件名自动标记
        file_path = str(item.fspath)
        if "test_smoke" in file_path:
            item.add_marker(pytest.mark.smoke)
        if "test_process_lifecycle" in file_path:
            item.add_marker(pytest.mark.process_lifecycle)
            item.add_marker(pytest.mark.real_ae_required)
        if "test_bridge_stability" in file_path:
            item.add_marker(pytest.mark.bridge_stability)
        if "test_ae_operations" in file_path:
            item.add_marker(pytest.mark.ae_operations)
            item.add_marker(pytest.mark.real_ae_required)
