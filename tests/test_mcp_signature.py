"""MCP 签名验证单元测试"""
import json
import os
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.mcp_signature import (
    _canonicalize,
    generate_secret,
    sign_command,
    verify_command,
)


class TestCanonicalize(unittest.TestCase):
    def test_simple_object(self):
        obj = {"b": 2, "a": 1}
        result = _canonicalize(obj)
        self.assertTrue(result.index('"a"') < result.index('"b"'))

    def test_nested_object(self):
        obj = {"z": {"b": 2, "a": 1}, "a": 1}
        result = _canonicalize(obj)
        self.assertIn('"a":1', result)

    def test_array_preserves_order(self):
        obj = {"arr": [3, 1, 2]}
        result = _canonicalize(obj)
        self.assertIn("[3,1,2]", result)

    def test_string_escaping(self):
        obj = {"key": 'hello "world"\n'}
        result = _canonicalize(obj)
        self.assertIn('\\"world\\"', result)


class TestGenerateSecret(unittest.TestCase):
    def test_generates_string(self):
        secret = generate_secret()
        self.assertIsInstance(secret, str)

    def test_generates_unique(self):
        s1 = generate_secret()
        s2 = generate_secret()
        self.assertNotEqual(s1, s2)

    def test_hex_format(self):
        secret = generate_secret()
        int(secret, 16)  # Should not raise


class TestSignAndVerify(unittest.TestCase):
    def setUp(self):
        self.secret = generate_secret()

    def test_sign_adds_signature(self):
        cmd = {"command": "test", "data": "hello"}
        signed = sign_command(cmd, self.secret)
        self.assertIn("signature", signed)
        self.assertIn("timestamp", signed)
        self.assertEqual(signed["signature_alg"], "HMAC-SHA256")

    def test_verify_valid_signature(self):
        cmd = {"command": "test", "data": "hello world"}
        signed = sign_command(cmd, self.secret)
        valid = verify_command(signed, self.secret)
        self.assertTrue(valid)

    def test_verify_tampered_fails(self):
        cmd = {"command": "test", "data": "hello"}
        signed = sign_command(cmd, self.secret)
        signed["command"] = "tampered"
        valid = verify_command(signed, self.secret)
        self.assertFalse(valid)

    def test_verify_wrong_secret_fails(self):
        cmd = {"command": "test"}
        signed = sign_command(cmd, self.secret)
        wrong_secret = generate_secret()
        valid = verify_command(signed, wrong_secret)
        self.assertFalse(valid)

    def test_verify_missing_signature_fails(self):
        cmd = {"command": "test", "timestamp": int(time.time())}
        valid = verify_command(cmd, self.secret)
        self.assertFalse(valid)

    def test_verify_expired_timestamp_fails(self):
        cmd = {"command": "test"}
        old_timestamp = int(time.time()) - 600  # 10 minutes ago
        signed = sign_command(cmd, self.secret, timestamp=old_timestamp)
        valid = verify_command(signed, self.secret, max_age_seconds=300)
        self.assertFalse(valid)

    def test_verify_future_timestamp_fails(self):
        cmd = {"command": "test"}
        future_timestamp = int(time.time()) + 600  # 10 minutes in future
        signed = sign_command(cmd, self.secret, timestamp=future_timestamp)
        valid = verify_command(signed, self.secret, max_age_seconds=300)
        self.assertFalse(valid)

    def test_verify_empty_secret_fails(self):
        cmd = {"command": "test"}
        signed = sign_command(cmd, self.secret)
        valid = verify_command(signed, "")
        self.assertFalse(valid)

    def test_sign_deterministic(self):
        cmd = {"command": "test", "data": "hello"}
        ts = 1234567890
        s1 = sign_command(cmd, self.secret, timestamp=ts)
        s2 = sign_command(cmd, self.secret, timestamp=ts)
        self.assertEqual(s1["signature"], s2["signature"])

    def test_verify_non_string_signature_fails(self):
        """非字符串类型的 signature 不应引发 TypeError，应返回 False"""
        cmd = {"command": "test"}
        signed = sign_command(cmd, self.secret)
        # 替换为整型签名
        signed["signature"] = 123456
        valid = verify_command(signed, self.secret)
        self.assertFalse(valid)

    def test_verify_list_signature_fails(self):
        """列表类型的 signature 应返回 False"""
        cmd = {"command": "test"}
        signed = sign_command(cmd, self.secret)
        signed["signature"] = ["a", "b", "c"]
        valid = verify_command(signed, self.secret)
        self.assertFalse(valid)


if __name__ == "__main__":
    unittest.main(verbosity=2)
