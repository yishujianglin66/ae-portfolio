"""
Photoshop Bridge Client
========================

Python 端 Photoshop MCP Bridge 通信客户端。

通过文件交换协议与 ps_mcp_bridge.jsx 通信：
  1. Python 写入命令到 .ps-mcp-bridge/ps_command.json
  2. JSX 在 Photoshop 内轮询读取并执行
  3. JSX 写入结果到 .ps-mcp-bridge/ps_result.json
  4. Python 轮询读取结果

使用方式：
    client = PSBridgeClient()
    result = client.send_command("execute_script", script="app.activeDocument.name")
    result = client.ping()
    result = client.get_document_info()
    result = client.list_layers()
"""
from __future__ import annotations

import os
import time
import json
from pathlib import Path
from typing import Any, Dict, Optional

from ae_bridge_base import AEBridgeClient


class PSBridgeClient(AEBridgeClient):
    """Photoshop MCP Bridge 客户端。"""

    # D-04/D-15 迁移元数据（声明式常量，与 __init__ 文件命名约定一致）
    APP_PREFIX = "ps"
    APP_NAME = "Photoshop"
    COMMAND_FILE_NAME = "ps_command.json"
    RESULT_FILE_NAME = "ps_result.json"
    SECRET_FILE_NAME = ".ps_mcp_secret"

    def __init__(
        self,
        bridge_dir: Optional[str | Path] = None,
        timeout: int = 15,
        poll_interval: float = 0.3,
        signature_enabled: bool = False,
        secret: Optional[str] = None,
    ):
        # 默认使用项目根目录下的 .ps-mcp-bridge/
        if bridge_dir is None:
            project_root = Path(__file__).resolve().parent
            bridge_dir = project_root / ".ps-mcp-bridge"
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
        )

        self.bridge_dir = str(bridge_dir)

    def _load_secret(self) -> str:
        """从 .ps_mcp_secret 加载签名密钥。"""
        secret_file = Path(__file__).resolve().parent / ".ps_mcp_secret"
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
        """发送命令到 Photoshop 并等待结果。

        Args:
            command: 命令类型 (execute_script / ping / getDocumentInfo / listLayers)
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
        cmd_data: Dict[str, Any] = {
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

    def ping(self, timeout: int = 5) -> Dict[str, Any]:
        """发送 Ping 命令，检测 Bridge 是否在线。"""
        return self.send_command("ping", timeout=timeout)

    def get_document_info(self, timeout: int = 5) -> Dict[str, Any]:
        """获取当前 Photoshop 文档信息。"""
        return self.send_command("getDocumentInfo", timeout=timeout)

    def list_layers(self, timeout: int = 5) -> Dict[str, Any]:
        """列出所有图层。"""
        return self.send_command("listLayers", timeout=timeout)

    def execute_script(self, script: str, timeout: int = 15) -> Dict[str, Any]:
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
