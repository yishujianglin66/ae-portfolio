"""
Audition Bridge Client
======================

Python 端 Adobe Audition MCP Bridge 通信客户端。

通过文件交换协议与 au_mcp_bridge.jsx 通信：
  1. Python 写入命令到 .au-mcp-bridge/au_command.json
  2. JSX 在 Audition 内轮询读取并执行
  3. JSX 写入结果到 .au-mcp-bridge/au_result.json
  4. Python 轮询读取结果

使用方式：
    client = AUBridgeClient()
    result = client.send_command("execute_script", script="app.activeDocument.name")
    result = client.ping()
    result = client.get_session_info()
    result = client.list_tracks()
"""
from __future__ import annotations

import os
import time
import json
from pathlib import Path
from typing import Any, Dict, Optional

from ae_bridge_base import AEBridgeClient


class AUBridgeClient(AEBridgeClient):
    """Adobe Audition MCP Bridge 客户端。"""

    def __init__(
        self,
        bridge_dir: Optional[str | Path] = None,
        timeout: int = 15,
        poll_interval: float = 0.3,
        signature_enabled: bool = False,
        secret: Optional[str] = None,
    ):
        if bridge_dir is None:
            project_root = Path(__file__).resolve().parent
            bridge_dir = project_root / ".au-mcp-bridge"
        else:
            bridge_dir = Path(bridge_dir)

        bridge_dir = Path(bridge_dir)
        command_file = str(bridge_dir / "au_command.json")
        result_file = str(bridge_dir / "au_result.json")

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
        """从 .au_mcp_secret 加载签名密钥。"""
        secret_file = Path(__file__).resolve().parent / ".au_mcp_secret"
        if not secret_file.exists():
            return ""
        try:
            return secret_file.read_text(encoding="utf-8").strip()
        except OSError:
            return ""

    def _is_result_ready(self, result: Dict[str, Any]) -> bool:
        """判断结果是否就绪：status 字段为 success/error 即就绪。"""
        return result.get("status") in ("success", "error")

    # ------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------

    def send_command(
        self,
        command: str,
        script: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:
        """发送命令到 Adobe Audition 并等待结果。

        Args:
            command: 命令类型 (execute_script / ping / getSessionInfo / listTracks)
            script: ES 脚本代码（仅 execute_script 命令需要）
            timeout: 超时秒数（None 使用默认值）

        Returns:
            结果字典，包含 status / result / timestamp 等字段
        """
        if timeout is not None:
            self.timeout = timeout

        self.clear_result()

        cmd_data: Dict[str, Any] = {
            "command": command,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "processed": False,
        }
        if script:
            cmd_data["script"] = script

        if self.signature_enabled and self.secret:
            sig = self._generate_signature(cmd_data)
            if sig:
                cmd_data["signature"] = sig
                cmd_data["signature_alg"] = "HMAC-SHA256"

        self._write_command_file(cmd_data)

        result = self._wait_for_result()

        self.clear_result()

        return result

    def ping(self, timeout: int = 5) -> Dict[str, Any]:
        """发送 Ping 命令，检测 Bridge 是否在线。"""
        return self.send_command("ping", timeout=timeout)

    def get_session_info(self, timeout: int = 5) -> Dict[str, Any]:
        """获取当前 Audition 会话信息。"""
        return self.send_command("getSessionInfo", timeout=timeout)

    def list_tracks(self, timeout: int = 5) -> Dict[str, Any]:
        """列出所有轨道（多轨会话或波形）。"""
        return self.send_command("listTracks", timeout=timeout)

    def execute_script(self, script: str, timeout: int = 15) -> Dict[str, Any]:
        """执行 ES 脚本代码。

        Args:
            script: ES 脚本代码字符串
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
