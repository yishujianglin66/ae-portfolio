import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ae_mcp_client import AECommandClient


def test_client_initialization():
    client = AECommandClient()
    assert client.command_file is not None
    assert client.result_file is not None

def test_send_command():
    import tempfile
    import threading
    import time as _time
    tmp_dir = tempfile.mkdtemp()
    cmd_file = os.path.join(tmp_dir, "cmd.json")
    res_file = os.path.join(tmp_dir, "res.json")

    client = AECommandClient(
        command_file=cmd_file,
        result_file=res_file,
        timeout=2,
        poll_interval=0.1,
        signature_enabled=False
    )

    # 模拟 AE Listener 延迟写入结果
    def write_result():
        _time.sleep(0.3)
        with open(res_file, "w") as f:
            json.dump({"success": True, "status": "success"}, f)

    thread = threading.Thread(target=write_result)
    thread.start()

    result = client.send_command("test", {"message": "hello"})
    thread.join()

    assert isinstance(result, dict)
    assert result["success"] is True

def test_signature_generation():
    client = AECommandClient(signature_enabled=True)
    client.secret = "test_secret_key_123"
    data = {"op": "test", "params": {"a": 1}}
    signature = client._generate_signature(data)
    assert isinstance(signature, str)
    assert len(signature) == 64

def test_read_result_file_not_found():
    import tempfile
    tmp_dir = tempfile.mkdtemp()
    client = AECommandClient(
        command_file=os.path.join(tmp_dir, "cmd.json"),
        result_file=os.path.join(tmp_dir, "nonexistent.json"),
        signature_enabled=False
    )
    result = client._read_result()
    assert result is None

def test_clear_result():
    import tempfile
    tmp_dir = tempfile.mkdtemp()
    res_file = os.path.join(tmp_dir, "res.json")
    
    client = AECommandClient(
        command_file=os.path.join(tmp_dir, "cmd.json"),
        result_file=res_file,
        signature_enabled=False
    )
    
    with open(res_file, "w") as f:
        json.dump({"test": 1}, f)
    
    assert os.path.exists(res_file)
    client.clear_result()
    assert not os.path.exists(res_file)

def test_send_batch_commands():
    import tempfile
    import threading
    import time as _time
    tmp_dir = tempfile.mkdtemp()
    cmd_file = os.path.join(tmp_dir, "cmd.json")
    res_file = os.path.join(tmp_dir, "res.json")

    client = AECommandClient(
        command_file=cmd_file,
        result_file=res_file,
        timeout=2,
        poll_interval=0.1,
        signature_enabled=False
    )

    call_count = [0]
    original_send = client.send_command

    def mock_send(op, params):
        call_count[0] += 1
        # 模拟 AE 延迟写入结果
        def write_res():
            _time.sleep(0.2)
            with open(res_file, "w") as f:
                json.dump({"success": True, "op": op}, f)
        t = threading.Thread(target=write_res)
        t.start()
        result = original_send(op, params)
        t.join()
        return result

    client.send_command = mock_send

    commands = [
        {"op": "op1", "params": {"a": 1}},
        {"op": "op2", "params": {"b": 2}},
        {"op": "op3", "params": {"c": 3}}
    ]
    results = client.send_batch_commands(commands)
    assert len(results) == 3
    assert call_count[0] == 3
