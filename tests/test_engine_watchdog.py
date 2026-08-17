"""P0-1 / P0-2 稳定性加固单元测试。

运行：pytest tests/test_engine_watchdog.py -v
注意：test_run_cmd_timeout_no_orphan 会真实启动一个长进程并超时杀掉，属实跑测试。
"""
import os
import subprocess
import time

import pytest

from core.engine_watchdog import is_process_running
from pipeline.flagship_runner import run_cmd


def _long_cmd():
    if os.name == "nt":
        return ["ping", "-n", "20", "127.0.0.1"]
    return ["sleep", "20"]


def test_run_cmd_timeout_no_orphan():
    """P0-1：超时后子进程树必须被回收，无孤儿残留。"""
    with pytest.raises(subprocess.TimeoutExpired):
        run_cmd(_long_cmd(), timeout=2)
    time.sleep(1)
    name = "ping.exe" if os.name == "nt" else "sleep"
    assert not is_process_running(name), f"孤儿进程 {name} 仍存在"


def test_run_cmd_success_returns_completed():
    cmd = ["cmd", "/c", "echo ok"] if os.name == "nt" else ["echo", "ok"]
    assert run_cmd(cmd).returncode == 0


def test_is_process_running_self():
    # 当前 Python 解释器自身必然在运行
    assert is_process_running("python") or is_process_running("python.exe")
