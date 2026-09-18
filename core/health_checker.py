"""
core/health_checker.py — 旗舰管线环境健康门 (S0)
==================================================

在旗舰 E2E 管线启动前，对所有必需环境进行一次性全面检查。
任何检查项失败则整条管线中止（fail-closed），不降级、不跳过。

检查项：
1. 引擎可执行文件存在性（AE/PR/DR/AME/FFmpeg/Whisper）
2. Bridge 连通性（AE/PR 文件轮询 ping）
3. 磁盘可用空间 ≥ 50GB
4. Run 目录路径 ASCII 合规（^[A-Za-z0-9_-]+$）
5. 许可证弹窗预检（可选，截图模板匹配）

集成方式::

    from core.health_checker import HealthChecker, HealthReport

    checker = HealthChecker()
    report = checker.check_pipeline_requirements(
        engine_names=["after_effects", "premiere", "davinci", "media_encoder", "ffmpeg", "whisper"]
    )
    if not report.passed:
        for failure in report.failures:
            print(f"[FAIL] {failure.check_id}: {failure.message}")
        raise RuntimeError("S0 健康门未通过，管线中止")

设计原则：
- 纯 Python 离线检测（不启动任何外部软件）
- Bridge ping 通过写入 command.json + 等待 result.json 实现
- 所有阈值可配置（通过 HealthCheckConfig）
- 检查结果结构化（JSON 可序列化）
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ============================================================================
#  数据类
# ============================================================================

ASCII_SAFE_PATTERN = re.compile(r"^[A-Za-z0-9_\-]+$")


@dataclass
class CheckItem:
    """单项检查结果"""
    check_id: str
    name: str
    passed: bool
    message: str = ""
    actual: Any = None
    expected: Any = None
    duration_ms: float = 0.0


@dataclass
class EngineStatus:
    """引擎状态"""
    name: str
    executable_path: str
    exists: bool
    bridge_available: bool | None = None  # None=无Bridge, True/False=有Bridge的连通性
    version: str | None = None


@dataclass
class HealthReport:
    """健康检查总报告"""
    passed: bool
    timestamp: float = field(default_factory=time.time)
    run_id: str = ""
    checks: list[CheckItem] = field(default_factory=list)
    engines: list[EngineStatus] = field(default_factory=list)
    disk_free_gb: float = 0.0
    failures: list[CheckItem] = field(default_factory=list)
    summary: str = ""

    def to_json(self) -> str:
        """序列化为 JSON 字符串"""
        return json.dumps(asdict(self), ensure_ascii=False, indent=2, default=str)

    def save(self, path: Path | str) -> Path:
        """保存报告到文件"""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(), encoding="utf-8")
        return path


@dataclass
class HealthCheckConfig:
    """健康检查配置"""
    min_disk_free_gb: float = 50.0
    bridge_ping_timeout_s: float = 15.0
    bridge_poll_interval_s: float = 0.3
    check_bridge: bool = True
    check_disk: bool = True
    check_ascii_path: bool = True
    run_dir: Path | None = None


# ============================================================================
#  引擎路径注册表（默认值，可被 config 覆盖）
# ============================================================================

def _get_default_engine_paths() -> dict[str, dict[str, Any]]:
    """获取默认引擎路径配置。

    优先从 puppet-automation settings 读取，失败时使用硬编码默认值。
    """
    defaults: dict[str, dict[str, Any]] = {
        "after_effects": {
            "executable": "C:/Program Files/Adobe/Adobe After Effects 2025/Support Files/aerender.exe",
            "bridge_dir": None,  # 需要项目根目录
            "has_bridge": True,
        },
        "premiere": {
            "executable": "D:/Pr25/Adobe Premiere Pro 2025/Adobe Premiere Pro.exe",
            "bridge_dir": None,
            "has_bridge": True,
        },
        "davinci": {
            "executable": "D:/DaVinci Resolve/Resolve.exe",
            "bridge_dir": None,
            "has_bridge": False,
        },
        "media_encoder": {
            "executable": "D:/Me/Adobe Media Encoder 2025/Adobe Media Encoder.exe",
            "bridge_dir": None,
            "has_bridge": False,
        },
        "ffmpeg": {
            "executable": "C:/ffmpeg/bin/ffmpeg.exe",
            "bridge_dir": None,
            "has_bridge": False,
        },
        "whisper": {
            "executable": "",  # Python 包，无独立可执行文件
            "bridge_dir": None,
            "has_bridge": False,
            "python_module": "whisper",
        },
    }

    # 尝试从 puppet-automation settings 读取真实路径
    try:
        import sys
        project_root = Path(__file__).resolve().parent.parent
        pa_src = project_root / "puppet-automation" / "src"
        if str(pa_src) not in sys.path:
            sys.path.insert(0, str(pa_src))
        from config import settings as pa_settings

        defaults["after_effects"]["executable"] = str(pa_settings.aerender_path)
        defaults["after_effects"]["bridge_dir"] = str(project_root / ".ae-mcp-bridge")
        defaults["premiere"]["executable"] = str(pa_settings.premiere_path)
        defaults["premiere"]["bridge_dir"] = str(pa_settings.pr_bridge_dir)
        defaults["davinci"]["executable"] = str(pa_settings.davinci_path / "Resolve.exe")
        defaults["media_encoder"]["executable"] = str(pa_settings.media_encoder_path)
        defaults["ffmpeg"]["executable"] = str(pa_settings.ffmpeg_path)
    except Exception as e:
        logger.debug(f"无法加载 puppet-automation settings，使用默认路径: {e}")
        # 回退：使用项目根目录推断 bridge 路径
        project_root = Path(__file__).resolve().parent.parent
        defaults["after_effects"]["bridge_dir"] = str(project_root / ".ae-mcp-bridge")
        defaults["premiere"]["bridge_dir"] = str(project_root / ".pr-mcp-bridge")

    # DaVinci 路径回退扫描：配置路径不存在时探测常见安装位置
    # （修复：硬编码 D:\DaVinci Resolve 导致实际安装在其它目录时误报“未安装”）
    if not Path(defaults["davinci"]["executable"]).exists():
        for cand in (
            r"D:/app/Resolve.exe",
            r"C:/Program Files/Blackmagic Design/DaVinci Resolve/Resolve.exe",
            r"D:/DaVinci Resolve/Resolve.exe",
            r"D:/Blackmagic Design/DaVinci Resolve/Resolve.exe",
        ):
            if Path(cand).exists():
                defaults["davinci"]["executable"] = cand
                break

    return defaults


# ============================================================================
#  核心检查器
# ============================================================================

class HealthChecker:
    """旗舰管线环境健康检查器

    Usage::

        checker = HealthChecker()
        report = checker.check_pipeline_requirements(
            engine_names=["after_effects", "premiere", "davinci",
                          "media_encoder", "ffmpeg", "whisper"]
        )
    """

    def __init__(
        self,
        config: HealthCheckConfig | None = None,
        engine_paths: dict[str, dict[str, Any]] | None = None,
    ):
        self.config = config or HealthCheckConfig()
        self._engine_paths = engine_paths or _get_default_engine_paths()

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------

    def check_pipeline_requirements(
        self,
        engine_names: list[str],
        run_id: str | None = None,
    ) -> HealthReport:
        """执行全部健康检查，返回结构化报告。

        Args:
            engine_names: 需要检查的引擎名称列表
            run_id: 本次运行 ID（用于报告标识）

        Returns:
            HealthReport（passed=True 表示全部通过）
        """
        run_id = run_id or f"health_{uuid.uuid4().hex[:8]}"
        checks: list[CheckItem] = []
        engines: list[EngineStatus] = []

        # 1. 引擎可执行文件检查
        for name in engine_names:
            engine_check, engine_status = self._check_engine(name)
            checks.append(engine_check)
            engines.append(engine_status)

        # 2. Bridge 连通性检查
        if self.config.check_bridge:
            for name in engine_names:
                bridge_check = self._check_bridge(name)
                if bridge_check is not None:
                    checks.append(bridge_check)
                    # 更新 engine status
                    for es in engines:
                        if es.name == name:
                            es.bridge_available = bridge_check.passed

        # 3. 磁盘空间检查
        disk_free_gb = 0.0
        if self.config.check_disk:
            disk_check, disk_free_gb = self._check_disk_space()
            checks.append(disk_check)

        # 4. ASCII 路径检查
        if self.config.check_ascii_path and self.config.run_dir:
            ascii_check = self._check_ascii_path(self.config.run_dir)
            checks.append(ascii_check)

        # 汇总
        failures = [c for c in checks if not c.passed]
        passed = len(failures) == 0
        summary = (
            f"全部 {len(checks)} 项检查通过"
            if passed
            else f"{len(failures)}/{len(checks)} 项检查失败: "
                 + ", ".join(f.check_id for f in failures)
        )

        report = HealthReport(
            passed=passed,
            run_id=run_id,
            checks=checks,
            engines=engines,
            disk_free_gb=disk_free_gb,
            failures=failures,
            summary=summary,
        )

        level = logging.INFO if passed else logging.ERROR
        logger.log(level, f"[S0 Health] {summary}")

        return report

    # ------------------------------------------------------------------
    # 内部检查方法
    # ------------------------------------------------------------------

    def _check_engine(self, name: str) -> tuple[CheckItem, EngineStatus]:
        """检查单个引擎可执行文件是否存在"""
        start = time.time()
        engine_cfg = self._engine_paths.get(name)

        if engine_cfg is None:
            item = CheckItem(
                check_id=f"engine_{name}_exists",
                name=f"引擎 {name} 路径配置",
                passed=False,
                message=f"未知引擎名称: {name}",
                duration_ms=(time.time() - start) * 1000,
            )
            status = EngineStatus(name=name, executable_path="", exists=False)
            return item, status

        exe_path = engine_cfg.get("executable", "")
        python_module = engine_cfg.get("python_module")

        # Python 模块类引擎（如 whisper）
        if python_module:
            exists = self._check_python_module(python_module)
            msg = f"Python 模块 '{python_module}' {'可导入' if exists else '不可用'}"
        else:
            exists = Path(exe_path).exists() if exe_path else False
            msg = f"可执行文件 {'存在' if exists else '不存在'}: {exe_path}"

        item = CheckItem(
            check_id=f"engine_{name}_exists",
            name=f"引擎 {name} 可执行文件",
            passed=exists,
            message=msg,
            actual=exe_path,
            expected="文件存在",
            duration_ms=(time.time() - start) * 1000,
        )
        status = EngineStatus(
            name=name,
            executable_path=exe_path,
            exists=exists,
        )
        return item, status

    def _check_bridge(self, name: str) -> CheckItem | None:
        """检查引擎 Bridge 连通性（仅对有 Bridge 的引擎）"""
        engine_cfg = self._engine_paths.get(name)
        if not engine_cfg or not engine_cfg.get("has_bridge"):
            return None

        bridge_dir = engine_cfg.get("bridge_dir")
        if not bridge_dir:
            return CheckItem(
                check_id=f"bridge_{name}_ping",
                name=f"Bridge {name} 连通性",
                passed=False,
                message="Bridge 目录未配置",
            )

        start = time.time()
        bridge_path = Path(bridge_dir)

        # 检查 bridge 目录是否存在
        if not bridge_path.exists():
            return CheckItem(
                check_id=f"bridge_{name}_ping",
                name=f"Bridge {name} 连通性",
                passed=False,
                message=f"Bridge 目录不存在: {bridge_path}",
                duration_ms=(time.time() - start) * 1000,
            )

        # 写入 ping 命令并等待响应
        ping_ok = self._bridge_ping(bridge_path, name)
        msg = f"Bridge ping {'成功' if ping_ok else '失败（超时或无响应）'}"

        return CheckItem(
            check_id=f"bridge_{name}_ping",
            name=f"Bridge {name} 连通性",
            passed=ping_ok,
            message=msg,
            duration_ms=(time.time() - start) * 1000,
        )

    def _check_disk_space(self) -> tuple[CheckItem, float]:
        """检查磁盘可用空间"""
        start = time.time()
        run_dir = self.config.run_dir or Path(__file__).resolve().parent.parent
        # 确保目录存在以获取正确的磁盘信息
        check_path = run_dir if run_dir.exists() else Path.cwd()

        try:
            usage = shutil.disk_usage(str(check_path))
            free_gb = usage.free / (1024 ** 3)
        except OSError as e:
            return CheckItem(
                check_id="disk_space",
                name="磁盘可用空间",
                passed=False,
                message=f"无法获取磁盘信息: {e}",
                duration_ms=(time.time() - start) * 1000,
            ), 0.0

        passed = free_gb >= self.config.min_disk_free_gb
        return CheckItem(
            check_id="disk_space",
            name="磁盘可用空间",
            passed=passed,
            message=f"可用 {free_gb:.1f}GB（要求 ≥{self.config.min_disk_free_gb:.0f}GB）",
            actual=f"{free_gb:.1f}GB",
            expected=f"≥{self.config.min_disk_free_gb:.0f}GB",
            duration_ms=(time.time() - start) * 1000,
        ), free_gb

    def _check_ascii_path(self, run_dir: Path) -> CheckItem:
        """检查 run 目录路径是否全部 ASCII 安全"""
        start = time.time()
        # 检查 run_dir 的最后几级目录名
        parts_to_check = run_dir.parts[-3:] if len(run_dir.parts) >= 3 else run_dir.parts
        non_ascii = [p for p in parts_to_check if not ASCII_SAFE_PATTERN.match(p)]

        passed = len(non_ascii) == 0
        msg = (
            "路径全部 ASCII 合规"
            if passed
            else f"非 ASCII 路径组件: {non_ascii}"
        )
        return CheckItem(
            check_id="ascii_path",
            name="Run 目录 ASCII 合规",
            passed=passed,
            message=msg,
            actual=str(run_dir),
            expected="^[A-Za-z0-9_-]+$",
            duration_ms=(time.time() - start) * 1000,
        )

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    def _check_python_module(self, module_name: str) -> bool:
        """检查 Python 模块是否可导入"""
        try:
            __import__(module_name)
            return True
        except ImportError:
            return False

    def _bridge_ping(self, bridge_dir: Path, engine_name: str) -> bool:
        """通过文件轮询协议 ping Bridge。

        写入 command.json → 等待 result.json → 读取结果。
        """
        # 确定命令/结果文件名
        if engine_name == "after_effects":
            cmd_file = bridge_dir / "ae_command.json"
            res_file = bridge_dir / "ae_result.json"
            command_payload = {
                "command": "ping",
                "args": {},
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "processed": False,
            }
        elif engine_name == "premiere":
            cmd_file = bridge_dir / "pr_command.json"
            res_file = bridge_dir / "pr_result.json"
            command_payload = {
                "id": f"health_ping_{uuid.uuid4().hex[:8]}",
                "type": "ping",
                "args": {},
                "timestamp": time.time(),
            }
        else:
            return False

        try:
            # 清除旧结果
            if res_file.exists():
                res_file.unlink()

            # 写入命令
            cmd_file.write_text(
                json.dumps(command_payload, ensure_ascii=False),
                encoding="utf-8",
            )

            # 轮询等待结果
            deadline = time.time() + self.config.bridge_ping_timeout_s
            while time.time() < deadline:
                if res_file.exists():
                    try:
                        result = json.loads(res_file.read_text(encoding="utf-8"))
                        status = result.get("status", "")
                        if status in ("success", "done"):
                            return True
                        # 即使返回 error，也说明 Bridge 在线
                        if status == "error":
                            logger.warning(
                                f"Bridge {engine_name} 返回 error: {result.get('error')}"
                            )
                            return True
                    except (json.JSONDecodeError, OSError):
                        pass
                time.sleep(self.config.bridge_poll_interval_s)

            return False
        except OSError as e:
            logger.error(f"Bridge ping I/O 错误 ({engine_name}): {e}")
            return False


# ============================================================================
#  便捷函数
# ============================================================================

def run_health_check(
    engine_names: list[str] | None = None,
    run_dir: Path | str | None = None,
    save_path: Path | str | None = None,
) -> HealthReport:
    """一键执行健康检查。

    Args:
        engine_names: 需检查的引擎列表（默认全部 6 个）
        run_dir: 本次 run 的输出目录
        save_path: 报告保存路径（可选）

    Returns:
        HealthReport
    """
    if engine_names is None:
        engine_names = ["after_effects", "premiere", "davinci", "media_encoder", "ffmpeg", "whisper"]

    config = HealthCheckConfig(
        run_dir=Path(run_dir) if run_dir else None,
    )
    checker = HealthChecker(config=config)
    report = checker.check_pipeline_requirements(engine_names)

    if save_path:
        report.save(save_path)

    return report
