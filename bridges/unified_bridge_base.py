"""
DEPRECATED - 统一 Adobe Bridge 基类（本基类已弃用）
======================================

.. deprecated::
    弃用的是**本基类** —— 它已无生产消费方，仅保留向后兼容的导入面
    （自 2026-09-19 起改为惰性导出，访问时才触发 DeprecationWarning）。
    不应新增依赖。

.. warning::
    **不要把上面的弃用读成"`.ae-mcp-bridge` 协议已弃用"** —— 那是两回事。
    该文件轮询协议**仍在产**：`ai/ae_render_channel.py` 自带独立实现
    （含 HMAC 签名与 `core.bridge_failure` 失败链），承载本项目全部自动化
    AE comp 构建 + aerender 渲染。

    三轨接入现状见 `03-阶段报告/AE三轨通道收敛决策_2026-09-19.md`，
    可复跑盘点见 `scripts/ae_channel_status.py`。

原始功能说明：
提取 ae_bridge_base + pr_bridge_client + ps_bridge_client + au_bridge_client 的共性，
提供统一的 Bridge 客户端框架。

各软件 Bridge 只需实现：
- 命令集定义（send_command 的参数格式）
- JSX 脚本路径
- 密钥文件路径

v2.0: 接入 ae.bridge_protocol 的中间件管道和传输层。

Usage:
    class MyBridgeClient(UnifiedBridgeBase):
        APP_PREFIX = "my"
        APP_NAME = "MyApp"

        def _get_command_set(self):
            return {"ping": self._handle_ping, ...}
"""

from __future__ import annotations

import warnings as _warnings

_warnings.warn(
    "bridges.unified_bridge_base 已弃用（本基类无生产消费方）。"
    "注意: .ae-mcp-bridge 协议本身仍在产, 由 ai/ae_render_channel.py 承载。",
    DeprecationWarning,
    stacklevel=2,
)

import logging
import os

# 延迟导入 ae 核心模块
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

# P1 修复：ae_bridge_base.py 位于本 bridges/ 包内，必须将此目录加入 sys.path，
# 而非父目录下的 ae/（原逻辑导致 ModuleNotFoundError）。
_bridges_dir = os.path.dirname(__file__)
if _bridges_dir not in sys.path:
    sys.path.insert(0, _bridges_dir)

try:
    import ae_bridge_base as _base_mod
except ModuleNotFoundError:
    # 兜底：作为包内模块导入
    from . import ae_bridge_base as _base_mod

logger = logging.getLogger(__name__)


class UnifiedBridgeBase(_base_mod.AEBridgeClient):
    """统一 Adobe Bridge 基类。

    提取 PR/PS/AU Bridge 客户端的共性：
    - 标准化的 __init__（bridge_dir, timeout, poll_interval, signature_enabled）
    - 通用的 _load_secret（从 .{app}_mcp_secret 加载）
    - 通用的 _is_result_ready（status in success/error）
    - 通用的 send_command / ping / is_online
    - v2.0: 中间件管道支持

    子类需设置：
    - APP_PREFIX: 应用前缀（如 "pr", "ps", "au"）
    - APP_NAME: 应用名称（如 "Premiere Pro", "Photoshop"）
    - COMMAND_FILE_NAME: 命令文件名（如 "pr_command.json"）
    - RESULT_FILE_NAME: 结果文件名（如 "pr_result.json"）
    - SECRET_FILE_NAME: 密钥文件名（如 ".pr_mcp_secret"）
    """

    # 子类必须覆盖这些类属性
    APP_PREFIX: str = ""
    APP_NAME: str = ""
    COMMAND_FILE_NAME: str = "command.json"
    RESULT_FILE_NAME: str = "result.json"
    SECRET_FILE_NAME: str = ".mcp_secret"

    def __init__(
        self,
        bridge_dir: str | Path | None = None,
        timeout: int = 15,
        poll_interval: float = 0.3,
        signature_enabled: bool = False,
        secret: str | None = None,
        middleware_pipeline: Any = None,
        idempotency_enabled: bool = False,
        auto_setup_middleware: bool = True,
    ):
        # 默认 bridge_dir: 项目根目录/.{APP_PREFIX}-mcp-bridge/
        if bridge_dir is None:
            project_root = Path(__file__).resolve().parent
            bridge_dir = project_root / f".{self.APP_PREFIX}-mcp-bridge"
        else:
            bridge_dir = Path(bridge_dir)

        bridge_dir = Path(bridge_dir)
        command_file = str(bridge_dir / self.COMMAND_FILE_NAME)
        result_file = str(bridge_dir / self.RESULT_FILE_NAME)

        super().__init__(
            command_file=command_file,
            result_file=result_file,
            timeout=timeout,
            poll_interval=poll_interval,
            signature_enabled=signature_enabled,
            secret=secret,
            middleware_pipeline=middleware_pipeline,
            idempotency_enabled=idempotency_enabled,
        )

        self.bridge_dir = str(bridge_dir)

        # v2.0: 自动设置中间件管道
        if self._pipeline is None and auto_setup_middleware:
            self._setup_default_pipeline()

    def _setup_default_pipeline(self) -> None:
        """创建默认中间件管道。"""
        _base_mod._try_import_core()
        if _base_mod._MiddlewarePipeline is None:
            return
        try:
            from bridge_middleware import LoggingMiddleware, MetricsMiddleware
            pipeline = _base_mod._MiddlewarePipeline()
            pipeline.add(LoggingMiddleware())
            metrics_mw = MetricsMiddleware()
            pipeline.add(metrics_mw)
            self._pipeline = pipeline
            self._metrics_middleware = metrics_mw
        except ImportError:
            pass

    def _load_secret(self) -> str:
        """从 .{APP_PREFIX}_mcp_secret 加载签名密钥。"""
        secret_file = Path(__file__).resolve().parent / self.SECRET_FILE_NAME
        if not secret_file.exists():
            return ""
        try:
            return secret_file.read_text(encoding="utf-8").strip()
        except OSError:
            return ""

    def _is_result_ready(self, result: dict[str, Any]) -> bool:
        """判断结果是否就绪：status 字段为 success/error 即就绪。"""
        return result.get("status") in ("success", "error")

    # ------------------------------------------------------------------
    # 通用命令 API
    # ------------------------------------------------------------------

    def send_command(
        self,
        command: str,
        script: str | None = None,
        timeout: int | None = None,
        **extra_params: Any,
    ) -> dict[str, Any]:
        """发送命令到目标 Adobe 应用并等待结果。

        Args:
            command: 命令类型
            script: ExtendScript 代码（仅 execute_script 命令需要）
            timeout: 超时秒数（None 使用默认值）
            **extra_params: 额外参数

        Returns:
            结果字典
        """
        if timeout is not None:
            self.timeout = timeout

        # 清除旧结果
        self.clear_result()

        # 构建命令
        cmd_data: dict[str, Any] = {
            "command": command,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "processed": False,
        }
        if script:
            cmd_data["script"] = script
        cmd_data.update(extra_params)

        # 签名（如果启用）
        if self.signature_enabled and self.secret:
            sig = self._generate_signature(cmd_data)
            if sig:
                cmd_data["signature"] = sig
                cmd_data["signature_alg"] = "HMAC-SHA256"

        # v2.0: 通过中间件管道执行
        if self._pipeline is not None:
            return self._send_via_pipeline(cmd_data)
        else:
            self._write_command_file(cmd_data)
            result = self._wait_for_result()
            self.clear_result()
            return result

    def _send_via_pipeline(self, cmd_data: dict[str, Any]) -> dict[str, Any]:
        """通过中间件管道发送命令。"""
        def _execute(cmd: dict[str, Any]) -> dict[str, Any]:
            self._write_command_file(cmd)
            result = self._wait_for_result()
            self.clear_result()
            # 验证响应签名
            if self.signature_enabled and self.secret:
                if not self._verify_response_signature(result):
                    logger.warning(
                        f"[{self.APP_NAME}] Response signature verification failed"
                    )
            return result

        try:
            return self._pipeline.process_command(cmd_data, _execute)
        except Exception as e:
            logger.error(f"[{self.APP_NAME}] Middleware pipeline error: {e}")
            self._write_command_file(cmd_data)
            result = self._wait_for_result()
            self.clear_result()
            return result

    def ping(self, timeout: int = 5) -> dict[str, Any]:
        """发送 Ping 命令，检测 Bridge 是否在线。"""
        return self.send_command("ping", timeout=timeout)

    def is_online(self) -> bool:
        """检测 Bridge 是否在线（非阻塞快速检测）。"""
        try:
            result = self.ping(timeout=3)
            return result.get("status") == "success"
        except Exception:
            return False

    def get_metrics(self) -> dict[str, Any] | None:
        """获取中间件收集的指标数据。"""
        if self._metrics_middleware is not None:
            return self._metrics_middleware.metrics.to_dict()
        return None

    def add_middleware(self, middleware: Any) -> None:
        """添加自定义中间件到管道。"""
        if self._pipeline is None:
            _base_mod._try_import_core()
            if _base_mod._MiddlewarePipeline is None:
                logger.warning("MiddlewarePipeline not available")
                return
            self._pipeline = _base_mod._MiddlewarePipeline()
        self._pipeline.add(middleware)
