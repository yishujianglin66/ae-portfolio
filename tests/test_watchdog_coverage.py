"""P3 收尾：验证看门狗启动覆盖到 PR / Resolve 路径（选项 2）。

不依赖真实 Adobe 进程：_DISPATCHER_AVAILABLE=False 让各 readiness 函数在
探活前即返回，subprocess.Popen 全程 mock 杜绝真拉起。仅断言 start_ae_watchdog
被调用——它是幂等的，监控 AE/PR/Resolve/ME 四引擎。
"""
from unittest import mock

import pipeline.flagship_runner as fr


def _fake_run(stdout=""):
    return mock.Mock(returncode=0, stdout=stdout, stderr="")


def test_watchdog_starts_from_ae_path(monkeypatch):
    monkeypatch.setattr(fr, "_DISPATCHER_AVAILABLE", False)
    monkeypatch.delenv("AEKV_WATCHDOG", raising=False)
    with mock.patch("core.engine_watchdog.start_ae_watchdog") as wd, \
         mock.patch("subprocess.run", return_value=_fake_run()), \
         mock.patch("subprocess.Popen"):
        fr._ensure_ae_bridge_ready(timeout=1.0)
    wd.assert_called_once()


def test_watchdog_starts_from_pr_path(monkeypatch):
    monkeypatch.setattr(fr, "_DISPATCHER_AVAILABLE", False)
    monkeypatch.delenv("AEKV_WATCHDOG", raising=False)
    with mock.patch("core.engine_watchdog.start_ae_watchdog") as wd, \
         mock.patch("subprocess.run", return_value=_fake_run()), \
         mock.patch("subprocess.Popen"):
        fr._ensure_pr_bridge_ready(timeout=1.0)
    wd.assert_called_once()


def test_watchdog_starts_from_resolve_path(monkeypatch):
    monkeypatch.setattr(fr, "_DISPATCHER_AVAILABLE", False)
    monkeypatch.delenv("AEKV_WATCHDOG", raising=False)
    with mock.patch("core.engine_watchdog.start_ae_watchdog") as wd, \
         mock.patch("subprocess.run", return_value=_fake_run()), \
         mock.patch("subprocess.Popen"), \
         mock.patch.object(fr, "find_resolve_exe", return_value=None):
        fr._ensure_resolve_ready(timeout=1.0)
    wd.assert_called_once()
