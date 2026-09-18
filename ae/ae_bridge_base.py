"""
AE 桥接客户端基类 — 权威实现。

原始功能说明：
抽象 AECommandClient 与 MCPBridgeClient 的共性逻辑：
- 文件交换（写命令文件 / 读结果文件 / 清除结果）
- HMAC-SHA256 签名生成与验证
- 结果轮询（超时控制 + 轮询间隔）
- 目录创建

v2.0 新增:
- 可选接入 ae.bridge_protocol.BridgeClient 获得中间件/传输层/幂等缓存能力
- 响应签名验证
- 中间件管道支持

子类需实现：
- _load_secret()         : 加载签名密钥
- _is_result_ready(result): 判断结果是否就绪（不同协议 status 字段不同）

子类可重写：
- _canonical_json(data)  : 自定义规范 JSON 序列化方式
"""
import hashlib
import hmac
import json
import logging
import os
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# 延迟导入 ae 核心模块（可选依赖）
_BridgeClient = None
_MiddlewarePipeline = None


def _try_import_core():
    """尝试导入 ae 核心模块（失败时静默降级）。"""
    global _BridgeClient, _MiddlewarePipeline
    if _BridgeClient is not None:
        return
    try:
        from ae.bridge_protocol import BridgeClient as _BC
        _BridgeClient = _BC
    except ImportError:
        logger.debug("ae.bridge_protocol.BridgeClient not available")
    try:
        from ae.bridge_middleware import MiddlewarePipeline as _MP
        _MiddlewarePipeline = _MP
    except ImportError:
        logger.debug("ae.bridge_middleware.MiddlewarePipeline not available")


class AEBridgeClient(ABC):
    """AE 桥接客户端基类，封装文件交换与签名通用逻辑。

    v2.0: 支持可选接入 ae.bridge_protocol 的中间件管道与签名验证。
    """

    def __init__(
        self,
        command_file: str,
        result_file: str,
        timeout: int = 10,
        poll_interval: float = 0.5,
        signature_enabled: bool = True,
        secret: str | None = None,
        # v2.0 新增参数
        middleware_pipeline: Any = None,
        idempotency_enabled: bool = False,
    ):
        self.command_file = command_file
        self.result_file = result_file
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.signature_enabled = signature_enabled
        self.idempotency_enabled = idempotency_enabled
        # secret 优先用构造函数传入，否则由子类 _load_secret 提供
        self.secret = secret if secret is not None else self._load_secret()

        # v2.0: 中间件管道
        _try_import_core()
        self._pipeline = middleware_pipeline
        self._metrics_middleware = None  # 子类可设置

    # ------------------------------------------------------------------
    # 子类必须实现
    # ------------------------------------------------------------------
    @abstractmethod
    def _load_secret(self) -> str:
        """加载签名密钥，返回字符串（无密钥返回空串）。"""
        ...

    def _is_result_ready(self, result: dict[str, Any]) -> bool:
        """判断结果是否就绪。默认只要读到非空即就绪，子类可重写。

        例如 MCPBridgeClient 要求 status in ['success','error','timeout']。
        """
        return bool(result)

    # ------------------------------------------------------------------
    # 通用方法
    # ------------------------------------------------------------------
    def _verify_response_signature(self, result: dict[str, Any]) -> bool:
        """验证响应签名（如果存在）。

        Returns:
            True 如果签名有效、无签名、或签名未启用
        """
        if not self.signature_enabled or not self.secret:
            return True
        signature = result.get("signature")
        if not signature:
            return True  # 服务端未返回签名，向后兼容
        try:
            sign_data = {k: v for k, v in result.items() if k != "signature"}
            expected = self._generate_signature(sign_data)
            return hmac.compare_digest(expected, signature)
        except Exception as e:
            logger.warning(f"Response signature verification failed: {e}")
            return False

    def _canonical_json(self, data: dict[str, Any]) -> str:
        """生成规范 JSON 字符串（用于签名）。

        默认与 mcp_bridge_client._canonicalize 一致：sort_keys + 紧凑分隔符。
        """
        return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    def _generate_signature(self, data: dict[str, Any]) -> str:
        """HMAC-SHA256 签名。无密钥或签名关闭时返回空串。"""
        if not self.signature_enabled or not self.secret:
            return ""
        canonical = self._canonical_json(data)
        return hmac.new(
            self.secret.encode("utf-8"),
            canonical.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _write_command_file(self, command: dict[str, Any]) -> None:
        """写入命令文件（自动创建父目录）。"""
        parent = os.path.dirname(self.command_file)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(self.command_file, "w", encoding="utf-8") as f:
            json.dump(command, f, ensure_ascii=False, indent=2)

    def _read_result(self) -> dict[str, Any] | None:
        """读取结果文件，文件不存在或解析失败返回 None。"""
        if not os.path.exists(self.result_file):
            return None
        try:
            with open(self.result_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    def _wait_for_result(self) -> dict[str, Any]:
        """轮询等待结果，超时返回错误 dict。

        v2.0: 读取结果后自动验证签名。
        """
        start_time = time.time()
        while self.timeout is None or time.time() - start_time < self.timeout:
            result = self._read_result()
            if result and self._is_result_ready(result):
                # v2.0: 验证响应签名
                if not self._verify_response_signature(result):
                    logger.warning("Response signature verification failed")
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

    def clear_command(self) -> None:
        """清除命令文件（若存在）。"""
        if os.path.exists(self.command_file):
            try:
                os.remove(self.command_file)
            except OSError:
                pass
