"""P3 资源配额 + 健康常态化 单元测试（Plan B / 固件稳定性纪律）。

运行：pytest tests/test_engine_health_quota.py -v

覆盖：
- EngineHealthRegistry 状态机（launching/healthy/dead + 快照）
- ResourceQuota 同引擎互斥 + 全局并发上限（含跨线程真并发验证）
- ensure_ready 集成注册表 + 双检锁防并发双拉起 + 假死自愈分支
- 看门狗启停 gating（AEKV_WATCHDOG=1）
- 观测层 getter（get_engine_health / all_engine_health / quota_status）

全程 stub 外部进程调用，离线确定；不触碰真实 AE/PR/Resolve。
"""
import threading
import time

import pytest

import core.engine_watchdog as ew
from core.engine_watchdog import (
    EngineHealthRegistry,
    ResourceQuota,
    all_engine_health,
    ensure_ready,
    get_engine_health,
    quota_status,
    start_ae_watchdog,
    stop_ae_watchdog,
)


@pytest.fixture
def fresh_state(monkeypatch):
    """把模块级单例替换为干净实例，避免跨测试污染。"""
    reg = EngineHealthRegistry()
    quota = ResourceQuota(max_concurrent=2)
    monkeypatch.setattr(ew, "ENGINE_HEALTH", reg)
    monkeypatch.setattr(ew, "ENGINE_QUOTA", quota)
    return reg, quota


# --------------------------------------------------------------------------
# EngineHealthRegistry
# --------------------------------------------------------------------------

def test_health_registry_transitions():
    reg = EngineHealthRegistry()
    assert reg.get("ae")["status"] == "unknown"
    reg.mark_launch_started("ae")
    assert reg.is_launch_in_progress("ae") is True
    assert reg.get("ae")["status"] == "launching"
    reg.mark_launch_done("ae", True)
    assert reg.is_launch_in_progress("ae") is False
    assert reg.get("ae")["status"] == "healthy"
    # last_seen_healthy_ts 仅由 mark_healthy 更新（与 ensure_ready 一致）
    assert reg.get("ae")["last_seen_healthy_ts"] == 0.0
    reg.mark_healthy("ae")
    assert reg.get("ae")["last_seen_healthy_ts"] > 0
    reg.mark_dead("ae", "boom")
    assert reg.get("ae")["status"] == "dead"
    assert reg.get("ae")["last_error"] == "boom"
    snap = reg.snapshot()
    assert "ae" in snap and snap["ae"]["status"] == "dead"


# --------------------------------------------------------------------------
# ResourceQuota
# --------------------------------------------------------------------------

def test_quota_global_cap_single_thread():
    q = ResourceQuota(max_concurrent=1)
    assert q.acquire_engine("ae") is True
    assert q.acquire_engine("pr", timeout=0.1) is False  # 全局上限=1
    q.release_engine("ae")
    assert q.acquire_engine("pr", timeout=0.1) is True
    q.release_engine("pr")
    assert q.status()["active"] == 0
    assert q.status()["max_concurrent"] == 1


def test_quota_per_engine_mutex_across_threads():
    """同引擎锁必须跨线程互斥（防看门狗/编排器并发双拉起）。"""
    q = ResourceQuota(max_concurrent=2)
    enter = threading.Event()
    proceed = threading.Event()
    acquired = []

    def worker():
        name = threading.current_thread().name
        if q.acquire_engine("ae", timeout=2.0):
            acquired.append(name)
            enter.set()           # 已拿锁
            proceed.wait(2.0)     # 持有期间
            q.release_engine("ae")

    t1 = threading.Thread(target=worker, name="t1")
    t2 = threading.Thread(target=worker, name="t2")
    t1.start()
    assert enter.wait(2.0)
    t2.start()
    time.sleep(0.3)
    # t1 持有 ae 锁期间，t2 必须被阻塞，不能拿到
    assert acquired == ["t1"]
    proceed.set()
    t1.join(2.0)
    t2.join(2.0)
    assert set(acquired) == {"t1", "t2"}  # 最终都拿到（串行）


# --------------------------------------------------------------------------
# ensure_ready 集成（注册表 + 双检锁 + 自愈）
# --------------------------------------------------------------------------

def test_ensure_ready_healthy_records_registry(monkeypatch, fresh_state):
    reg, _ = fresh_state
    monkeypatch.setattr(ew, "is_process_running", lambda n: True)
    monkeypatch.setattr(ew, "launch_engine", lambda *a, **k: True)
    monkeypatch.setattr(ew, "probe_bridge", lambda is_avail, timeout=0: is_avail())
    ok = ensure_ready("after_effects", is_available=lambda: True, timeout=1.0)
    assert ok is True
    assert reg.get("after_effects")["status"] == "healthy"


def test_ensure_ready_launch_then_healthy(monkeypatch, fresh_state):
    reg, _ = fresh_state
    calls = {"launch": 0}
    monkeypatch.setattr(ew, "is_process_running", lambda n: False)
    monkeypatch.setattr(ew, "launch_engine",
                        lambda *a, **k: calls.__setitem__("launch", calls["launch"] + 1) or True)
    monkeypatch.setattr(ew, "probe_bridge", lambda is_avail, timeout=0: is_avail())
    ok = ensure_ready("after_effects", is_available=lambda: True, timeout=1.0)
    assert ok is True
    assert calls["launch"] == 1
    assert reg.get("after_effects")["status"] == "healthy"


def test_ensure_ready_no_double_launch_on_race(monkeypatch, fresh_state):
    """双检锁：锁内复检发现已被别处拉起 -> 不重复拉起。"""
    reg, _ = fresh_state
    calls = {"running": 0, "launch": 0}

    def fake_running(n):
        calls["running"] += 1
        # 第一次 False（认为没跑），锁内复检 True（被别处拉起）
        return calls["running"] > 1

    monkeypatch.setattr(ew, "is_process_running", fake_running)
    monkeypatch.setattr(ew, "launch_engine",
                        lambda *a, **k: calls.__setitem__("launch", calls["launch"] + 1) or True)
    monkeypatch.setattr(ew, "probe_bridge", lambda is_avail, timeout=0: is_avail())
    ok = ensure_ready("after_effects", is_available=lambda: True, timeout=1.0)
    assert ok is True
    assert calls["launch"] == 0  # 复检命中 -> 不拉起
    assert reg.get("after_effects")["status"] == "healthy"


def test_ensure_ready_dead_records_registry(monkeypatch, fresh_state):
    reg, _ = fresh_state
    monkeypatch.setattr(ew, "is_process_running", lambda n: False)
    monkeypatch.setattr(ew, "launch_engine", lambda *a, **k: False)  # 启动失败
    monkeypatch.setattr(ew, "probe_bridge", lambda is_avail, timeout=0: is_avail())
    ok = ensure_ready("after_effects", is_available=lambda: True, timeout=1.0)
    assert ok is False
    assert reg.get("after_effects")["status"] == "dead"
    assert "启动失败" in reg.get("after_effects")["last_error"]


def test_ensure_ready_selfheal_restarts_when_stuck(monkeypatch, fresh_state):
    """进程在但 Bridge 无响应（假死）-> 杀树重启再探 -> 健康。"""
    reg, _ = fresh_state
    monkeypatch.setattr(ew, "is_process_running", lambda n: True)
    monkeypatch.setattr(ew, "probe_bridge", lambda is_avail, timeout=0: is_avail())
    monkeypatch.setattr(ew, "kill_process_tree_by_name", lambda n: None)
    monkeypatch.setattr(ew, "time", __import__("unittest").mock.MagicMock())  # 免除 sleep(2)
    monkeypatch.setattr(ew, "launch_engine", lambda *a, **k: True)
    state = {"n": 0}

    def avail():
        state["n"] += 1
        return state["n"] >= 2  # 重启前 False，重启后 True

    ok = ensure_ready("after_effects", is_available=avail, timeout=1.0)
    assert ok is True
    assert reg.get("after_effects")["status"] == "healthy"


def test_ensure_ready_quota_exhausted_fails_fast(monkeypatch, fresh_state):
    """全局配额耗尽 -> fail-fast 返回 False（不野蛮抢占）。"""
    reg, quota = fresh_state
    quota.acquire_engine("after_effects")  # 占满一个槽
    quota.acquire_engine("premiere")       # 占满第二个槽（max_concurrent=2）
    monkeypatch.setattr(ew, "is_process_running", lambda n: False)
    monkeypatch.setattr(ew, "launch_engine", lambda *a, **k: True)
    monkeypatch.setattr(ew, "probe_bridge", lambda is_avail, timeout=0: is_avail())
    ok = ensure_ready("resolve", is_available=lambda: True, timeout=0.1)
    assert ok is False
    assert reg.get("resolve")["status"] == "dead"
    quota.release_engine("after_effects")
    quota.release_engine("premiere")


# --------------------------------------------------------------------------
# 看门狗启停 gating
# --------------------------------------------------------------------------

def test_watchdog_start_gated_off(monkeypatch):
    monkeypatch.delenv("AEKV_WATCHDOG", raising=False)
    monkeypatch.setattr(ew, "_WATCHDOG_THREAD", None)
    start_ae_watchdog()
    assert ew._WATCHDOG_THREAD is None


def test_watchdog_start_runs_when_enabled(monkeypatch):
    monkeypatch.setenv("AEKV_WATCHDOG", "1")
    monkeypatch.setattr(ew, "_WATCHDOG_THREAD", None)
    # 阻断巡检对真实 engine_task_dispatcher 的依赖（best-effort）
    try:
        import pipeline.engine_task_dispatcher as etd
        monkeypatch.setattr(etd, "get_dispatcher", lambda n: None)
    except Exception:
        pass
    try:
        start_ae_watchdog(interval=1.0)
        assert ew._WATCHDOG_THREAD is not None
        assert ew._WATCHDOG_THREAD.is_alive()
    finally:
        stop_ae_watchdog()
        ew._WATCHDOG_THREAD.join(timeout=2)


# --------------------------------------------------------------------------
# 观测层 getter
# --------------------------------------------------------------------------

def test_observability_getters(monkeypatch, fresh_state):
    reg, quota = fresh_state
    reg.mark_healthy("after_effects")
    assert get_engine_health("after_effects")["status"] == "healthy"
    assert all_engine_health()["after_effects"]["status"] == "healthy"
    assert quota_status()["max_concurrent"] == 2
