"""
Premiere Pro Bridge Client
==========================

Python 端 Premiere Pro MCP Bridge 通信客户端。

通过文件交换协议与 pr_mcp_bridge.jsx 通信：
  1. Python 写入命令到 .pr-mcp-bridge/pr_command.json
  2. JSX 在 Premiere 内轮询读取并执行
  3. JSX 写入结果到 .pr-mcp-bridge/pr_result.json
  4. Python 轮询读取结果

使用方式：
    client = PRBridgeClient()
    result = client.send_command("execute_script", script="app.project.name")
    result = client.ping()
    result = client.get_project_info()
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

from ae_bridge_base import AEBridgeClient


class PRBridgeClient(AEBridgeClient):
    """Premiere Pro MCP Bridge 客户端。"""

    def __init__(
        self,
        bridge_dir: str | Path | None = None,
        timeout: int = 15,
        poll_interval: float = 0.3,
        signature_enabled: bool = False,
        secret: str | None = None,
    ):
        # 默认使用项目根目录下的 .pr-mcp-bridge/
        if bridge_dir is None:
            project_root = Path(__file__).resolve().parent
            bridge_dir = project_root / ".pr-mcp-bridge"
        else:
            bridge_dir = Path(bridge_dir)

        bridge_dir = Path(bridge_dir)
        command_file = str(bridge_dir / "pr_command.json")
        result_file = str(bridge_dir / "pr_result.json")

        super().__init__(
            command_file=command_file,
            result_file=result_file,
            timeout=timeout,
            poll_interval=poll_interval,
            signature_enabled=signature_enabled,
            secret=secret,
        )

        self.bridge_dir = str(bridge_dir)

    def _load_secret(self) -> str:
        """从 .pr_mcp_secret 加载签名密钥。"""
        secret_file = Path(__file__).resolve().parent / ".pr_mcp_secret"
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
    # 公共 API
    # ------------------------------------------------------------------

    def send_command(
        self,
        command: str,
        script: str | None = None,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        """发送命令到 Premiere Pro 并等待结果。

        Args:
            command: 命令类型 (execute_script / ping / getProjectInfo / listSequences)
            script: ExtendScript 代码（仅 execute_script 命令需要）
            timeout: 超时秒数（None 使用默认值）

        Returns:
            结果字典，包含 status / result / timestamp 等字段
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

        # 签名（如果启用）
        if self.signature_enabled and self.secret:
            sig = self._generate_signature(cmd_data)
            if sig:
                cmd_data["signature"] = sig
                cmd_data["signature_alg"] = "HMAC-SHA256"

        # 写入命令文件
        self._write_command_file(cmd_data)

        # 轮询等待结果
        result = self._wait_for_result()

        # 清除结果文件（读取完毕）
        self.clear_result()

        return result

    def ping(self, timeout: int = 5) -> dict[str, Any]:
        """发送 Ping 命令，检测 Bridge 是否在线。"""
        return self.send_command("ping", timeout=timeout)

    def get_project_info(self, timeout: int = 5) -> dict[str, Any]:
        """获取当前 Premiere 项目信息。"""
        return self.send_command("getProjectInfo", timeout=timeout)

    def list_sequences(self, timeout: int = 5) -> dict[str, Any]:
        """列出所有序列。"""
        return self.send_command("listSequences", timeout=timeout)

    def execute_script(self, script: str, timeout: int = 15) -> dict[str, Any]:
        """执行 ExtendScript 代码。

        Args:
            script: ExtendScript 代码字符串
            timeout: 超时秒数

        Returns:
            结果字典
        """
        return self.send_command("execute_script", script=script, timeout=timeout)

    def is_online(self) -> bool:
        """检测 Bridge 是否在线（非阻塞快速检测）。"""
        try:
            result = self.ping(timeout=3)
            return result.get("status") == "success"
        except Exception:
            return False
