"""
tests/test_health_checker.py — 健康检查模块单元测试
====================================================

覆盖率目标：≥ 90%
运行：pytest tests/test_health_checker.py --cov=core.health_checker --cov-fail-under=90 -v
"""
import json
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.health_checker import (
    ASCII_SAFE_PATTERN,
    CheckItem,
    EngineStatus,
    HealthCheckConfig,
    HealthChecker,
    HealthReport,
    _get_default_engine_paths,
    run_health_check,
)

# ============================================================================
#  Fixtures
# ============================================================================

@pytest.fixture
def default_config():
    """默认配置（禁用 Bridge 检查以加速测试）"""
    return HealthCheckConfig(
        check_bridge=False,
        check_disk=True,
        check_ascii_path=False,
        min_disk_free_gb=0.001,  # 极低阈值确保通过
    )


@pytest.fixture
def mock_engine_paths(tmp_path):
    """模拟引擎路径（全部指向 tmp_path 下的假文件）"""
    # 创建假可执行文件
    ae_exe = tmp_path / "aerender.exe"
    ae_exe.write_text("fake")
    pr_exe = tmp_path / "premiere.exe"
    pr_exe.write_text("fake")
    ffmpeg_exe = tmp_path / "ffmpeg.exe"
    ffmpeg_exe.write_text("fake")

    return {
        "after_effects": {
            "executable": str(ae_exe),
            "bridge_dir": str(tmp_path / "ae_bridge"),
            "has_bridge": True,
        },
        "premiere": {
            "executable": str(pr_exe),
            "bridge_dir": str(tmp_path / "pr_bridge"),
            "has_bridge": True,
        },
        "davinci": {
            "executable": str(tmp_path / "nonexist" / "Resolve.exe"),
            "bridge_dir": None,
            "has_bridge": False,
        },
        "media_encoder": {
            "executable": str(tmp_path / "nonexist" / "AME.exe"),
            "bridge_dir": None,
            "has_bridge": False,
        },
        "ffmpeg": {
            "executable": str(ffmpeg_exe),
            "bridge_dir": None,
            "has_bridge": False,
        },
        "whisper": {
            "executable": "",
            "bridge_dir": None,
            "has_bridge": False,
            "python_module": "json",  # 用 json 模块模拟（必定存在）
        },
    }


@pytest.fixture
def checker(default_config, mock_engine_paths):
    """预配置的 HealthChecker"""
    return HealthChecker(config=default_config, engine_paths=mock_engine_paths)


# ============================================================================
#  HealthReport 数据类测试
# ============================================================================

class TestHealthReport:
    def test_to_json_serializable(self):
        report = HealthReport(passed=True, summary="all good")
        json_str = report.to_json()
        data = json.loads(json_str)
        assert data["passed"] is True
        assert data["summary"] == "all good"

    def test_save_creates_file(self, tmp_path):
        report = HealthReport(passed=False, summary="fail")
        out = tmp_path / "sub" / "report.json"
        result_path = report.save(out)
        assert result_path.exists()
        content = json.loads(result_path.read_text(encoding="utf-8"))
        assert content["passed"] is False

    def test_failures_list(self):
        fail_item = CheckItem(check_id="x", name="X", passed=False, message="bad")
        pass_item = CheckItem(check_id="y", name="Y", passed=True)
        report = HealthReport(
            passed=False,
            checks=[fail_item, pass_item],
            failures=[fail_item],
        )
        assert len(report.failures) == 1
        assert report.failures[0].check_id == "x"


# ============================================================================
#  引擎存在性检查
# ============================================================================

class TestEngineCheck:
    def test_existing_engine_passes(self, checker):
        report = checker.check_pipeline_requirements(["after_effects"])
        ae_checks = [c for c in report.checks if "after_effects" in c.check_id]
        assert len(ae_checks) == 1
        assert ae_checks[0].passed is True

    def test_missing_engine_fails(self, checker):
        report = checker.check_pipeline_requirements(["davinci"])
        dv_checks = [c for c in report.checks if "davinci" in c.check_id]
        assert len(dv_checks) == 1
        assert dv_checks[0].passed is False
        assert "不存在" in dv_checks[0].message

    def test_unknown_engine_fails(self, checker):
        report = checker.check_pipeline_requirements(["nonexist_engine"])
        assert report.passed is False
        assert any("未知引擎" in c.message for c in report.checks)

    def test_python_module_engine(self, checker):
        """whisper 用 python_module 检测"""
        report = checker.check_pipeline_requirements(["whisper"])
        wh_checks = [c for c in report.checks if "whisper" in c.check_id]
        assert len(wh_checks) == 1
        assert wh_checks[0].passed is True  # json 模块必定存在

    def test_python_module_missing(self, default_config, mock_engine_paths):
        """模拟不存在的 Python 模块"""
        mock_engine_paths["fake_mod"] = {
            "executable": "",
            "bridge_dir": None,
            "has_bridge": False,
            "python_module": "nonexistent_module_xyz_12345",
        }
        checker = HealthChecker(config=default_config, engine_paths=mock_engine_paths)
        report = checker.check_pipeline_requirements(["fake_mod"])
        assert report.passed is False

    def test_engine_status_populated(self, checker):
        report = checker.check_pipeline_requirements(["after_effects", "ffmpeg"])
        assert len(report.engines) == 2
        ae_status = next(e for e in report.engines if e.name == "after_effects")
        assert ae_status.exists is True


# ============================================================================
#  磁盘空间检查
# ============================================================================

class TestDiskCheck:
    def test_disk_pass_with_low_threshold(self, checker):
        report = checker.check_pipeline_requirements(["ffmpeg"])
        disk_checks = [c for c in report.checks if c.check_id == "disk_space"]
        assert len(disk_checks) == 1
        assert disk_checks[0].passed is True
        assert report.disk_free_gb > 0

    def test_disk_fail_with_high_threshold(self, mock_engine_paths):
        config = HealthCheckConfig(
            check_bridge=False,
            check_disk=True,
            check_ascii_path=False,
            min_disk_free_gb=999999.0,  # 不可能满足
        )
        checker = HealthChecker(config=config, engine_paths=mock_engine_paths)
        report = checker.check_pipeline_requirements(["ffmpeg"])
        disk_checks = [c for c in report.checks if c.check_id == "disk_space"]
        assert disk_checks[0].passed is False

    def test_disk_check_disabled(self, mock_engine_paths):
        config = HealthCheckConfig(check_bridge=False, check_disk=False, check_ascii_path=False)
        checker = HealthChecker(config=config, engine_paths=mock_engine_paths)
        report = checker.check_pipeline_requirements(["ffmpeg"])
        disk_checks = [c for c in report.checks if c.check_id == "disk_space"]
        assert len(disk_checks) == 0

    @patch("shutil.disk_usage", side_effect=OSError("mock error"))
    def test_disk_oserror(self, mock_usage, mock_engine_paths):
        config = HealthCheckConfig(check_bridge=False, check_disk=True, check_ascii_path=False)
        checker = HealthChecker(config=config, engine_paths=mock_engine_paths)
        report = checker.check_pipeline_requirements(["ffmpeg"])
        disk_checks = [c for c in report.checks if c.check_id == "disk_space"]
        assert disk_checks[0].passed is False
        assert "无法获取" in disk_checks[0].message


# ============================================================================
#  ASCII 路径检查
# ============================================================================

class TestAsciiPathCheck:
    def test_ascii_path_pass(self, mock_engine_paths, tmp_path):
        run_dir = tmp_path / "flagship_run01"
        run_dir.mkdir()
        config = HealthCheckConfig(
            check_bridge=False, check_disk=False, check_ascii_path=True,
            run_dir=run_dir,
        )
        checker = HealthChecker(config=config, engine_paths=mock_engine_paths)
        report = checker.check_pipeline_requirements(["ffmpeg"])
        ascii_checks = [c for c in report.checks if c.check_id == "ascii_path"]
        assert len(ascii_checks) == 1
        assert ascii_checks[0].passed is True

    def test_non_ascii_path_fail(self, mock_engine_paths, tmp_path):
        run_dir = tmp_path / "旗舰运行_测试"
        run_dir.mkdir()
        config = HealthCheckConfig(
            check_bridge=False, check_disk=False, check_ascii_path=True,
            run_dir=run_dir,
        )
        checker = HealthChecker(config=config, engine_paths=mock_engine_paths)
        report = checker.check_pipeline_requirements(["ffmpeg"])
        ascii_checks = [c for c in report.checks if c.check_id == "ascii_path"]
        assert ascii_checks[0].passed is False
        assert "非 ASCII" in ascii_checks[0].message

    def test_ascii_pattern(self):
        assert ASCII_SAFE_PATTERN.match("flagship_run-01")
        assert ASCII_SAFE_PATTERN.match("S3_ae")
        assert not ASCII_SAFE_PATTERN.match("旗舰")
        assert not ASCII_SAFE_PATTERN.match("test run")  # 空格不允许


# ============================================================================
#  Bridge 连通性检查
# ============================================================================

class TestBridgeCheck:
    def test_bridge_dir_not_exist(self, mock_engine_paths, tmp_path):
        """Bridge 目录不存在 → 失败"""
        config = HealthCheckConfig(
            check_bridge=True, check_disk=False, check_ascii_path=False,
            bridge_ping_timeout_s=1.0,
        )
        checker = HealthChecker(config=config, engine_paths=mock_engine_paths)
        report = checker.check_pipeline_requirements(["after_effects"])
        bridge_checks = [c for c in report.checks if "bridge" in c.check_id]
        assert len(bridge_checks) == 1
        assert bridge_checks[0].passed is False
        assert "不存在" in bridge_checks[0].message

    def test_bridge_ping_success(self, mock_engine_paths, tmp_path):
        """模拟 Bridge ping 成功（后台线程延迟写入 result）"""
        bridge_dir = tmp_path / "ae_bridge"
        bridge_dir.mkdir()
        mock_engine_paths["after_effects"]["bridge_dir"] = str(bridge_dir)

        result_file = bridge_dir / "ae_result.json"

        def _delayed_response():
            time.sleep(0.3)
            result_file.write_text(
                json.dumps({"status": "success", "result": {"pong": True}}),
                encoding="utf-8",
            )

        t = threading.Thread(target=_delayed_response, daemon=True)
        t.start()

        config = HealthCheckConfig(
            check_bridge=True, check_disk=False, check_ascii_path=False,
            bridge_ping_timeout_s=3.0,
            bridge_poll_interval_s=0.1,
        )
        checker = HealthChecker(config=config, engine_paths=mock_engine_paths)
        report = checker.check_pipeline_requirements(["after_effects"])
        t.join(timeout=5)
        bridge_checks = [c for c in report.checks if "bridge" in c.check_id]
        assert bridge_checks[0].passed is True

    def test_bridge_ping_timeout(self, mock_engine_paths, tmp_path):
        """Bridge 无响应 → 超时失败"""
        bridge_dir = tmp_path / "ae_bridge"
        bridge_dir.mkdir()
        mock_engine_paths["after_effects"]["bridge_dir"] = str(bridge_dir)

        config = HealthCheckConfig(
            check_bridge=True, check_disk=False, check_ascii_path=False,
            bridge_ping_timeout_s=0.5,
            bridge_poll_interval_s=0.1,
        )
        checker = HealthChecker(config=config, engine_paths=mock_engine_paths)
        report = checker.check_pipeline_requirements(["after_effects"])
        bridge_checks = [c for c in report.checks if "bridge" in c.check_id]
        assert bridge_checks[0].passed is False
        assert "超时" in bridge_checks[0].message or "失败" in bridge_checks[0].message

    def test_bridge_no_bridge_engine_skipped(self, mock_engine_paths):
        """无 Bridge 的引擎（如 davinci）不检查 Bridge"""
        config = HealthCheckConfig(
            check_bridge=True, check_disk=False, check_ascii_path=False,
        )
        checker = HealthChecker(config=config, engine_paths=mock_engine_paths)
        report = checker.check_pipeline_requirements(["davinci"])
        bridge_checks = [c for c in report.checks if "bridge" in c.check_id]
        assert len(bridge_checks) == 0

    def test_bridge_premiere_ping(self, mock_engine_paths, tmp_path):
        """PR Bridge ping"""
        bridge_dir = tmp_path / "pr_bridge"
        bridge_dir.mkdir()
        mock_engine_paths["premiere"]["bridge_dir"] = str(bridge_dir)

        result_file = bridge_dir / "pr_result.json"

        def _delayed_response():
            time.sleep(0.3)
            result_file.write_text(
                json.dumps({"status": "success", "result": {}}),
                encoding="utf-8",
            )

        t = threading.Thread(target=_delayed_response, daemon=True)
        t.start()

        config = HealthCheckConfig(
            check_bridge=True, check_disk=False, check_ascii_path=False,
            bridge_ping_timeout_s=3.0,
            bridge_poll_interval_s=0.1,
        )
        checker = HealthChecker(config=config, engine_paths=mock_engine_paths)
        report = checker.check_pipeline_requirements(["premiere"])
        t.join(timeout=5)
        bridge_checks = [c for c in report.checks if "bridge" in c.check_id]
        assert bridge_checks[0].passed is True

    def test_bridge_error_status_still_online(self, mock_engine_paths, tmp_path):
        """Bridge 返回 error 状态仍视为在线"""
        bridge_dir = tmp_path / "ae_bridge"
        bridge_dir.mkdir()
        mock_engine_paths["after_effects"]["bridge_dir"] = str(bridge_dir)

        result_file = bridge_dir / "ae_result.json"

        def _delayed_response():
            time.sleep(0.3)
            result_file.write_text(
                json.dumps({"status": "error", "error": "script failed"}),
                encoding="utf-8",
            )

        t = threading.Thread(target=_delayed_response, daemon=True)
        t.start()

        config = HealthCheckConfig(
            check_bridge=True, check_disk=False, check_ascii_path=False,
            bridge_ping_timeout_s=3.0,
            bridge_poll_interval_s=0.1,
        )
        checker = HealthChecker(config=config, engine_paths=mock_engine_paths)
        report = checker.check_pipeline_requirements(["after_effects"])
        t.join(timeout=5)
        bridge_checks = [c for c in report.checks if "bridge" in c.check_id]
        assert bridge_checks[0].passed is True


# ============================================================================
#  综合检查
# ============================================================================

class TestFullCheck:
    def test_all_pass(self, checker):
        """全部引擎存在 + 磁盘够 → passed"""
        report = checker.check_pipeline_requirements(
            ["after_effects", "premiere", "ffmpeg", "whisper"]
        )
        assert report.passed is True
        assert report.summary.startswith("全部")
        assert len(report.failures) == 0

    def test_partial_fail(self, checker):
        """部分引擎不存在 → failed"""
        report = checker.check_pipeline_requirements(
            ["after_effects", "davinci", "media_encoder"]
        )
        assert report.passed is False
        assert len(report.failures) >= 2

    def test_run_id_generated(self, checker):
        report = checker.check_pipeline_requirements(["ffmpeg"])
        assert report.run_id.startswith("health_")

    def test_custom_run_id(self, checker):
        report = checker.check_pipeline_requirements(["ffmpeg"], run_id="my_run")
        assert report.run_id == "my_run"

    def test_timestamp_populated(self, checker):
        before = time.time()
        report = checker.check_pipeline_requirements(["ffmpeg"])
        after = time.time()
        assert before <= report.timestamp <= after


# ============================================================================
#  便捷函数测试
# ============================================================================

class TestRunHealthCheck:
    def test_basic_call(self):
        """默认调用不崩溃"""
        report = run_health_check(engine_names=["ffmpeg"])
        assert isinstance(report, HealthReport)

    def test_with_save(self, tmp_path):
        out = tmp_path / "S0_health.json"
        report = run_health_check(
            engine_names=["ffmpeg"],
            save_path=out,
        )
        assert out.exists()
        data = json.loads(out.read_text(encoding="utf-8"))
        assert "passed" in data

    def test_with_run_dir(self, tmp_path):
        run_dir = tmp_path / "flagship_test"
        run_dir.mkdir()
        report = run_health_check(
            engine_names=["ffmpeg"],
            run_dir=run_dir,
        )
        assert isinstance(report, HealthReport)


# ============================================================================
#  默认路径加载测试
# ============================================================================

class TestDefaultEnginePaths:
    def test_returns_dict(self):
        paths = _get_default_engine_paths()
        assert isinstance(paths, dict)
        assert "after_effects" in paths
        assert "ffmpeg" in paths

    def test_has_bridge_flags(self):
        paths = _get_default_engine_paths()
        assert paths["after_effects"]["has_bridge"] is True
        assert paths["premiere"]["has_bridge"] is True
        assert paths["davinci"]["has_bridge"] is False
        assert paths["ffmpeg"]["has_bridge"] is False
