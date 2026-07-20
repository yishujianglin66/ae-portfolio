"""
AE 桥接客户端基类
=================

抽象 ae_mcp_client.AECommandClient 与 mcp_bridge_client.MCPBridgeClient 的共性逻辑：
- 文件交换（写命令文件 / 读结果文件 / 清除结果）
- HMAC-SHA256 签名生成
- 结果轮询（超时控制 + 轮询间隔）
- 目录创建

子类需实现：
- _load_secret()         : 加载签名密钥
- _is_result_ready(result): 判断结果是否就绪（不同协议 status 字段不同）

子类可重写：
- _canonical_json(data)  : 自定义规范 JSON 序列化方式
"""
import os
import json
import time
import hmac
import hashlib
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class AEBridgeClient(ABC):
    """AE 桥接客户端基类，封装文件交换与签名通用逻辑。"""

    def __init__(
        self,
        command_file: str,
        result_file: str,
        timeout: int = 10,
        poll_interval: float = 0.5,
        signature_enabled: bool = True,
        secret: Optional[str] = None,
    ):
        self.command_file = command_file
        self.result_file = result_file
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.signature_enabled = signature_enabled
        # secret 优先用构造函数传入，否则由子类 _load_secret 提供
        self.secret = secret if secret is not None else self._load_secret()

    # ------------------------------------------------------------------
    # 子类必须实现
    # ------------------------------------------------------------------
    @abstractmethod
    def _load_secret(self) -> str:
        """加载签名密钥，返回字符串（无密钥返回空串）。"""
        ...

    def _is_result_ready(self, result: Dict[str, Any]) -> bool:
        """判断结果是否就绪。默认只要读到非空即就绪，子类可重写。

        例如 MCPBridgeClient 要求 status in ['success','error','timeout']。
        """
        return bool(result)

    # ------------------------------------------------------------------
    # 通用方法
    # ------------------------------------------------------------------
    def _canonical_json(self, data: Dict[str, Any]) -> str:
        """生成规范 JSON 字符串（用于签名）。

        默认与 mcp_bridge_client._canonicalize 一致：sort_keys + 紧凑分隔符。
        """
        return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    def _generate_signature(self, data: Dict[str, Any]) -> str:
        """HMAC-SHA256 签名。无密钥或签名关闭时返回空串。"""
        if not self.signature_enabled or not self.secret:
            return ""
        canonical = self._canonical_json(data)
        return hmac.new(
            self.secret.encode("utf-8"),
            canonical.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _write_command_file(self, command: Dict[str, Any]) -> None:
        """写入命令文件（自动创建父目录）。"""
        parent = os.path.dirname(self.command_file)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(self.command_file, "w", encoding="utf-8") as f:
            json.dump(command, f, ensure_ascii=False, indent=2)

    def _read_result(self) -> Optional[Dict[str, Any]]:
        """读取结果文件，文件不存在或解析失败返回 None。"""
        if not os.path.exists(self.result_file):
            return None
        try:
            with open(self.result_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    def _wait_for_result(self) -> Dict[str, Any]:
        """轮询等待结果，超时返回错误 dict。"""
        start_time = time.time()
        while time.time() - start_time < self.timeout:
            result = self._read_result()
            if result and self._is_result_ready(result):
                return result
            time.sleep(self.poll_interval)
        return {
            "success": False,
            "status": "timeout",
            "error": f"Timeout after {self.timeout}s",
        }

    def clear_result(self) -> None:
        """清除结果文件（若存在）。"""
        if os.path.exists(self.result_file):
            try:
                os.remove(self.result_file)
            except OSError:
                pass
