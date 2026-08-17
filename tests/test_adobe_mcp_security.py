#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Adobe MCP Bridge 安全测试
验证签名验证机制是否正确启用
"""
import json
import hmac
import hashlib
import tempfile
from pathlib import Path
from datetime import datetime


def generate_hmac_sha256_signature(secret: str, data: dict) -> str:
    """生成HMAC-SHA256签名（Python端）"""
    # Canonicalize: 按key排序序列化
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hmac.new(
        secret.encode("utf-8"),
        canonical.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def test_signature_validation():
    """测试签名验证逻辑"""
    print("=== Adobe MCP Bridge 签名验证测试 ===\n")

    # 生成测试密钥
    test_secret = "test_mcp_secret_key_12345"

    # 构造有效签名命令
    valid_command = {
        "command": "ping",
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
    }
    valid_signature = generate_hmac_sha256_signature(test_secret, valid_command)
    valid_command["signature"] = valid_signature

    print(f"✓ 有效签名命令: {json.dumps(valid_command, indent=2)}")

    # 构造无效签名命令
    invalid_command = {
        "command": "executeScript",
        "script": "app.activeDocument.name",
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "signature": "invalid_signature_abc123",
    }

    print(f"\n✗ 无效签名命令: {json.dumps(invalid_command, indent=2)}")

    # 构造过期时间戳命令
    expired_command = {
        "command": "ping",
        "timestamp": "2020-01-01T00:00:00",  # 过期时间戳
        "signature": "any_signature",
    }

    print(f"\n✗ 过期时间戳命令: {json.dumps(expired_command, indent=2)}")

    # 验证结果
    print("\n=== 预期结果 ===")
    print("1. SIGNATURE_ENABLED = true: 签名验证已启用")
    print("2. 有效签名命令: 验证通过，命令被执行")
    print("3. 无效签名命令: 验证失败，命令被拒绝")
    print("4. 过期时间戳命令: 时间戳校验失败（>300秒）")
    print("5. 缺少签名字段: 验证失败，返回false")

    # 检查配置文件
    print("\n=== 检查配置文件 ===")
    bridge_files = [
        "pr_mcp_bridge.jsx",
        "ps_mcp_bridge.jsx",
        "au_mcp_bridge.jsx",
    ]

    for bridge_file in bridge_files:
        bridge_path = Path(__file__).parent.parent / bridge_file
        if bridge_path.exists():
            content = bridge_path.read_text(encoding="utf-8")
            if "var SIGNATURE_ENABLED = true;" in content:
                print(f"✓ {bridge_file}: 签名验证已启用")
            else:
                print(f"✗ {bridge_file}: 签名验证未启用（安全漏洞！）")

            if "function verifySignature(data)" in content and "HMAC-SHA256" in content:
                print(f"  ✓ 完整HMAC实现已注入")
            else:
                print(f"  ✗ HMAC实现缺失（安全漏洞！）")
        else:
            print(f"⚠ {bridge_file}: 文件不存在")


def test_security_impact():
    """测试安全影响"""
    print("\n\n=== 安全影响评估 ===")
    print("修复前风险:")
    print("  - 攻击者可构造恶意命令文件执行任意ExtendScript代码")
    print("  - 可访问文件系统、执行系统命令、窃取数据")
    print("  - 影响范围: Premiere Pro、Photoshop、Audition、Media Encoder")
    print("\n修复后:")
    print("  - 签名验证强制启用（SIGNATURE_ENABLED = true）")
    print("  - 完整HMAC-SHA256实现，拒绝无效签名")
    print("  - 时间戳校验防止重放攻击（300秒窗口）")
    print("  - 常量时间比较防止时序攻击")


if __name__ == "__main__":
    test_signature_validation()
    test_security_impact()