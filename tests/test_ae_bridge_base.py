"""
test_ae_bridge_base.py - AE 桥接客户端基类单元测试
"""

import json
import os
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ae_bridge_base import AEBridgeClient


class ConcreteBridgeClient(AEBridgeClient):
    """具体实现类，用于测试基类。"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def _load_secret(self) -> str:
        return "test_secret_key"


class TestAEBridgeClientInit:
    """初始化测试。"""

    def test_basic_init(self):
        client = ConcreteBridgeClient(
            command_file="/tmp/cmd.json",
            result_file="/tmp/res.json",
            signature_enabled=False,
        )
        assert client.command_file == "/tmp/cmd.json"
        assert client.result_file == "/tmp/res.json"
        assert client.timeout == 10
        assert client.poll_interval == 0.5

    def test_custom_timeout_and_poll(self):
        client = ConcreteBridgeClient(
            command_file="/tmp/cmd.json",
            result_file="/tmp/res.json",
            timeout=30,
            poll_interval=0.1,
            signature_enabled=False,
        )
        assert client.timeout == 30
        assert client.poll_interval == 0.1

    def test_secret_via_constructor(self):
        client = ConcreteBridgeClient(
            command_file="/tmp/cmd.json",
            result_file="/tmp/res.json",
            secret="custom_secret",
        )
        assert client.secret == "custom_secret"
        assert client.signature_enabled is True

    def test_secret_from_load_secret(self):
        client = ConcreteBridgeClient(
            command_file="/tmp/cmd.json",
            result_file="/tmp/res.json",
        )
        assert client.secret == "test_secret_key"

    def test_signature_disabled_no_secret(self):
        """无密钥 + signature_enabled=False 时签名关闭。"""
        client = ConcreteBridgeClient(
            command_file="/tmp/cmd.json",
            result_file="/tmp/res.json",
            secret="",
            signature_enabled=False,
        )
        assert client.signature_enabled is False
        assert client._generate_signature({"a": 1}) == ""


class TestSignatureGeneration:
    """签名生成测试。"""

    def test_signature_length(self):
        client = ConcreteBridgeClient(
            command_file="/tmp/cmd.json",
            result_file="/tmp/res.json",
            secret="test_secret",
        )
        sig = client._generate_signature({"op": "test", "params": {}})
        assert isinstance(sig, str)
        assert len(sig) == 64

    def test_signature_consistent(self):
        """相同输入应生成相同签名。"""
        client = ConcreteBridgeClient(
            command_file="/tmp/cmd.json",
            result_file="/tmp/res.json",
            secret="test_secret",
        )
        data = {"op": "test", "params": {"x": 1}}
        sig1 = client._generate_signature(data)
        sig2 = client._generate_signature(data)
        assert sig1 == sig2

    def test_signature_different_data(self):
        """不同输入应生成不同签名。"""
        client = ConcreteBridgeClient(
            command_file="/tmp/cmd.json",
            result_file="/tmp/res.json",
            secret="test_secret",
        )
        sig1 = client._generate_signature({"a": 1})
        sig2 = client._generate_signature({"a": 2})
        assert sig1 != sig2

    def test_signature_disabled_returns_empty(self):
        client = ConcreteBridgeClient(
            command_file="/tmp/cmd.json",
            result_file="/tmp/res.json",
            signature_enabled=False,
        )
        sig = client._generate_signature({"a": 1})
        assert sig == ""


class TestFileOperations:
    """文件操作测试。"""

    def test_write_command_file(self):
        tmp_dir = tempfile.mkdtemp()
        cmd_file = os.path.join(tmp_dir, "cmd.json")
        res_file = os.path.join(tmp_dir, "res.json")
        client = ConcreteBridgeClient(
            command_file=cmd_file,
            result_file=res_file,
            signature_enabled=False,
        )
        client._write_command_file({"op": "test", "status": "pending"})
        assert os.path.exists(cmd_file)
        with open(cmd_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["op"] == "test"
        assert data["status"] == "pending"

    def test_write_creates_parent_dir(self):
        tmp_dir = tempfile.mkdtemp()
        cmd_file = os.path.join(tmp_dir, "sub", "dir", "cmd.json")
        res_file = os.path.join(tmp_dir, "res.json")
        client = ConcreteBridgeClient(
            command_file=cmd_file,
            result_file=res_file,
            signature_enabled=False,
        )
        client._write_command_file({"op": "test"})
        assert os.path.exists(cmd_file)

    def test_read_result_no_file(self):
        tmp_dir = tempfile.mkdtemp()
        client = ConcreteBridgeClient(
            command_file=os.path.join(tmp_dir, "cmd.json"),
            result_file=os.path.join(tmp_dir, "nonexistent.json"),
            signature_enabled=False,
        )
        assert client._read_result() is None

    def test_read_result_valid(self):
        tmp_dir = tempfile.mkdtemp()
        res_file = os.path.join(tmp_dir, "res.json")
        client = ConcreteBridgeClient(
            command_file=os.path.join(tmp_dir, "cmd.json"),
            result_file=res_file,
            signature_enabled=False,
        )
        with open(res_file, "w", encoding="utf-8") as f:
            json.dump({"success": True, "data": "test"}, f)
        result = client._read_result()
        assert result is not None
        assert result["success"] is True
        assert result["data"] == "test"

    def test_read_result_invalid_json(self):
        tmp_dir = tempfile.mkdtemp()
        res_file = os.path.join(tmp_dir, "res.json")
        client = ConcreteBridgeClient(
            command_file=os.path.join(tmp_dir, "cmd.json"),
            result_file=res_file,
            signature_enabled=False,
        )
        with open(res_file, "w", encoding="utf-8") as f:
            f.write("not valid json")
        assert client._read_result() is None

    def test_clear_result_no_file(self):
        tmp_dir = tempfile.mkdtemp()
        res_file = os.path.join(tmp_dir, "res.json")
        client = ConcreteBridgeClient(
            command_file=os.path.join(tmp_dir, "cmd.json"),
            result_file=res_file,
            signature_enabled=False,
        )
        client.clear_result()  # 不应抛异常

    def test_clear_result_removes_file(self):
        tmp_dir = tempfile.mkdtemp()
        res_file = os.path.join(tmp_dir, "res.json")
        client = ConcreteBridgeClient(
            command_file=os.path.join(tmp_dir, "cmd.json"),
            result_file=res_file,
            signature_enabled=False,
        )
        with open(res_file, "w", encoding="utf-8") as f:
            json.dump({"test": 1}, f)
        assert os.path.exists(res_file)
        client.clear_result()
        assert not os.path.exists(res_file)


class TestWaitForResult:
    """结果轮询测试。"""

    def test_timeout_returns_error(self):
        tmp_dir = tempfile.mkdtemp()
        client = ConcreteBridgeClient(
            command_file=os.path.join(tmp_dir, "cmd.json"),
            result_file=os.path.join(tmp_dir, "res.json"),
            timeout=0.3,
            poll_interval=0.1,
            signature_enabled=False,
        )
        result = client._wait_for_result()
        assert result["status"] == "timeout"
        assert result["success"] is False

    def test_result_delivered(self):
        tmp_dir = tempfile.mkdtemp()
        res_file = os.path.join(tmp_dir, "res.json")
        client = ConcreteBridgeClient(
            command_file=os.path.join(tmp_dir, "cmd.json"),
            result_file=res_file,
            timeout=2,
            poll_interval=0.05,
            signature_enabled=False,
        )

        def write_result():
            time.sleep(0.2)
            with open(res_file, "w", encoding="utf-8") as f:
                json.dump({"success": True, "data": "ok"}, f)

        thread = threading.Thread(target=write_result)
        thread.start()
        result = client._wait_for_result()
        thread.join()
        assert result["success"] is True
        assert result["data"] == "ok"

    def test_is_result_ready_custom(self):
        """_is_result_ready 可被重写。"""

        class StatusClient(ConcreteBridgeClient):
            def _is_result_ready(self, result):
                return result.get("status") in ["done", "error"]

        tmp_dir = tempfile.mkdtemp()
        res_file = os.path.join(tmp_dir, "res.json")
        client = StatusClient(
            command_file=os.path.join(tmp_dir, "cmd.json"),
            result_file=res_file,
            timeout=2,
            poll_interval=0.05,
            signature_enabled=False,
        )

        # 先写一个 status=pending 的结果，不应该被认为就绪
        with open(res_file, "w", encoding="utf-8") as f:
            json.dump({"status": "pending", "data": "not yet"}, f)
        assert client._is_result_ready({"status": "pending"}) is False
        assert client._is_result_ready({"status": "done"}) is True
        assert client._is_result_ready({"status": "error"}) is True


class TestBackwardCompatibility:
    """向后兼容测试：两个具体客户端应正常工作。"""

    def test_ae_command_client_inherits_base(self):
        from ae_bridge_base import AEBridgeClient
        from ae_mcp_client import AECommandClient
        client = AECommandClient(signature_enabled=False)
        assert isinstance(client, AEBridgeClient)

    def test_mcp_bridge_client_inherits_base(self):
        from ae_bridge_base import AEBridgeClient
        from mcp_bridge_client import MCPBridgeClient
        client = MCPBridgeClient()
        assert isinstance(client, AEBridgeClient)

    def test_ae_command_client_has_clear_result(self):
        from ae_mcp_client import AECommandClient
        tmp_dir = tempfile.mkdtemp()
        client = AECommandClient(
            command_file=os.path.join(tmp_dir, "cmd.json"),
            result_file=os.path.join(tmp_dir, "res.json"),
            signature_enabled=False,
        )
        assert hasattr(client, "clear_result")
        assert hasattr(client, "send_command")
        assert hasattr(client, "send_batch_commands")

    def test_mcp_bridge_client_has_check_status(self):
        from mcp_bridge_client import MCPBridgeClient
        client = MCPBridgeClient()
        assert hasattr(client, "check_status")
        assert hasattr(client, "get_logs")
        assert hasattr(client, "send_command")
