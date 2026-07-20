"""MCP Bridge 命令签名工具 - HMAC-SHA256

提供命令签名和验证功能，确保 MCP Bridge 命令的完整性和真实性。

使用方式：
    from config.mcp_signature import sign_command, verify_command

    signed = sign_command({"command": "execute_script", "script": "..."}, secret)
    valid = verify_command(signed, secret)
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any, Dict, Optional


def _canonicalize(obj: Dict[str, Any]) -> str:
    """将对象序列化为规范 JSON 字符串（用于签名）。

    按 key 排序，确保相同内容产生相同的签名。
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sign_command(
    command_data: Dict[str, Any],
    secret: str,
    timestamp: Optional[int] = None,
) -> Dict[str, Any]:
    """为命令数据添加签名。

    Args:
        command_data: 命令数据字典
        secret: 签名密钥
        timestamp: 时间戳（秒），默认使用当前时间

    Returns:
        带有 signature 和 timestamp 字段的命令字典
    """
    if timestamp is None:
        timestamp = int(time.time())

    data = dict(command_data)
    data["timestamp"] = timestamp

    canonical = _canonicalize(data)
    signature = hmac.new(
        secret.encode("utf-8"),
        canonical.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    data["signature"] = signature
    data["signature_alg"] = "HMAC-SHA256"
    return data


def verify_command(
    signed_data: Dict[str, Any],
    secret: str,
    max_age_seconds: int = 300,
) -> bool:
    """验证命令签名。

    Args:
        signed_data: 带有签名的命令数据
        secret: 签名密钥
        max_age_seconds: 最大允许的时间差（秒），防止重放攻击

    Returns:
        验证通过返回 True，否则返回 False
    """
    if not secret:
        return False

    signature = signed_data.get("signature")
    timestamp = signed_data.get("timestamp")
    alg = signed_data.get("signature_alg", "HMAC-SHA256")

    if not signature or not timestamp:
        return False

    # signature 必须是字符串，否则 hmac.compare_digest 会抛出 TypeError
    if not isinstance(signature, str):
        return False

    if alg != "HMAC-SHA256":
        return False

    try:
        ts = int(timestamp)
    except (ValueError, TypeError):
        return False

    now = int(time.time())
    if abs(now - ts) > max_age_seconds:
        return False

    verify_data = {k: v for k, v in signed_data.items()
                   if k not in ("signature", "signature_alg")}

    canonical = _canonicalize(verify_data)
    expected = hmac.new(
        secret.encode("utf-8"),
        canonical.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


def generate_secret() -> str:
    """生成一个安全的随机密钥。

    Returns:
        十六进制编码的 256 位随机密钥
    """
    import secrets
    return secrets.token_hex(32)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "generate":
        print(generate_secret())
    else:
        print("Usage: python mcp_signature.py generate")
        print("  Generate a new MCP Bridge signing secret.")
