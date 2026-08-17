"""P3 收尾：桥进程自愈单元测试（非破坏性，全 mock，零真实进程操作）。

验证：
  1. _bridge_launch_spec 从仓库根 .mcp.json 读取桥启动规格（唯一事实源）；
  2. find_bridge_pids 按唯一脚本子串精确解析 PID（Windows=PowerShell / 其它=pgrep），
     绝不按 'python.exe' 歧义名匹配；
  3. restart_bridge 先精确定杀旧桥进程、再以规格重新拉起；
  4. ensure_ready / _watchdog_loop 的假死自愈仅在 AEKV_BRIDGE_RESTART=1 时调用 restart_bridge。

固件视角：自愈必须恢复『整个子系统』（应用 + 桥），而非只拉起一个进程；
同时任何『按名杀进程』操作都必须精确匹配，避免误伤同名无关进程。
"""
import pytest

import core.engine_watchdog as ew
from core.engine_watchdog import EngineHealthRegistry, ResourceQuota


def _reset(monkeypatch):
    monkeypatch.setattr(ew, "ENGINE_HEALTH", EngineHealthRegistry())
    monkeypatch.setattr(ew, "ENGINE_QUOTA", ResourceQuota())


# ---------------------------------------------------------------------------
# 1) 启动规格读取
# ---------------------------------------------------------------------------
def test_bridge_spec_reads_mcpjson():
    spec = ew._bridge_launch_spec("after_effects")
    assert spec is not None
    assert spec["command"]
    assert any("adobe_mcp_server.py" in a for a in spec["args"])
    assert spec["marker"] == "adobe_mcp_server.py"

    spec2 = ew._bridge_launch_spec("premiere")
    assert spec2 and spec2["marker"]

    # media_encoder 无对应 MCP server -> 禁用桥自愈
    assert ew._bridge_launch_spec("media_encoder") is None


def test_bridge_spec_missing_mcpjson(monkeypatch, tmp_path):
    # 指向不存在的 .mcp.json -> 安全返回 None（不抛）
    monkeypatch.setattr(ew.Path, "resolve", lambda self: tmp_path / "x")
    assert ew._bridge_launch_spec("after_effects") is None


# ---------------------------------------------------------------------------
# 2) PID 精确定位
# ---------------------------------------------------------------------------
def test_find_bridge_pids_powershell(monkeypatch):
    monkeypatch.setattr(ew.os, "name", "nt")
    monkeypatch.setattr(ew, "_bridge_launch_spec", lambda e: {"marker": "adobe_mcp_server.py"})

    class CP:
        returncode = 0
        stdout = "1234\n5678\n"
        stderr = ""

    monkeypatch.setattr(ew.subprocess, "run", lambda *a, **k: CP())
    assert ew.find_bridge_pids("after_effects") == [1234, 5678]


def test_find_bridge_pids_pgrep(monkeypatch):
    monkeypatch.setattr(ew.os, "name", "posix")
    monkeypatch.setattr(ew, "_bridge_launch_spec", lambda e: {"marker": "adobe_mcp_server.py"})

    class CP:
        returncode = 0
        stdout = "1234\n"
        stderr = ""

    monkeypatch.setattr(ew.subprocess, "run", lambda *a, **k: CP())
    assert ew.find_bridge_pids("after_effects") == [1234]


# ---------------------------------------------------------------------------
# 3) 重启：先精确定杀旧进程，再按规格拉起
# ---------------------------------------------------------------------------
def test_restart_bridge_kills_old_and_relaunches(monkeypatch):
    spec = {"command": "py", "args": ["x.py", "--app", "after_effects"],
            "cwd": "C:/repo", "marker": "x.py"}
    monkeypatch.setattr(ew, "_bridge_launch_spec", lambda e: spec)
    monkeypatch.setattr(ew, "find_bridge_pids", lambda e: [999])

    killed = []
    relaunched = []

    def fake_run(cmd, **k):
        killed.append(list(cmd))
        class CP:
            returncode = 0
            stdout = ""
            stderr = ""
        return CP()

    monkeypatch.setattr(ew.subprocess, "run", fake_run)
    monkeypatch.setattr(ew.subprocess, "Popen", lambda cmd, **k: relaunched.append(list(cmd)))

    ok = ew.restart_bridge("after_effects")
    assert ok is True
    assert any("999" in str(c) for c in killed)          # taskkill /PID 999
    assert relaunched and relaunched[0][0] == "py"       # 重新拉起
    assert "x.py" in relaunched[0]


def test_restart_bridge_no_spec_is_noop(monkeypatch):
    monkeypatch.setattr(ew, "_bridge_launch_spec", lambda e: None)
    called = []
    monkeypatch.setattr(ew.subprocess, "Popen", lambda *a, **k: called.append(1))
    assert ew.restart_bridge("after_effects") is False
    assert called == []


# ---------------------------------------------------------------------------
# 4) ensure_ready 假死自愈：桥重启仅在 AEKV_BRIDGE_RESTART=1 时触发
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("enabled", [False, True])
def test_ensure_ready_selfheal_restarts_bridge_gated(monkeypatch, enabled):
    _reset(monkeypatch)
    monkeypatch.setattr(ew, "is_process_running", lambda name: True)
    monkeypatch.setattr(ew, "launch_engine", lambda *a, **k: True)
    monkeypatch.setattr(ew, "kill_process_tree_by_name", lambda name: None)
    monkeypatch.setattr(ew, "probe_bridge", lambda *a, **k: False)  # 强制假死分支
    monkeypatch.setattr(ew, "bridge_restart_enabled", lambda: enabled)

    calls = []
    monkeypatch.setattr(ew, "restart_bridge", lambda name: calls.append(name))

    ok = ew.ensure_ready("after_effects", is_available=lambda: False, timeout=1)
    assert ok is False  # 桥未恢复，按预期返回 False
    assert (len(calls) == 1) is enabled, calls
    if enabled:
        assert calls[0] == "after_effects"
