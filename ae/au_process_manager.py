#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Audition Process Manager
=========================
生产级 Adobe Audition 进程管理器。

功能特性：
- WM_CLOSE 优雅关闭，超时降级强制关闭
- 看门狗健康检测与自动恢复
- 崩溃状态全面清理（注册表、AppState、CrashRpt）
- 进程指标监控与内存泄漏检测
- 多种启动模式（normal / headless / safe_mode）
- 状态机管理与状态变化回调

Usage:
    python au_process_manager.py
    python au_process_manager.py --api --port 8125
"""

from __future__ import annotations

import argparse
import ctypes
import json
import logging
import os
import subprocess
import sys
import threading
import time
import winreg
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from ctypes import wintypes
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple

try:
    from ae.process_backends import ProcessBackend, auto_detect_backend
except ImportError:
    try:
        from process_backends import ProcessBackend, auto_detect_backend
    except ImportError:
        ProcessBackend = None
        auto_detect_backend = None

logger = logging.getLogger(__name__)


def setup_logging(level: int = logging.INFO, format_str: str | None = None, log_file: str | None = None) -> logging.Logger:
    """配置结构化日志。"""
    fmt = format_str or "[%(asctime)s] %(levelname)-8s [%(component)s] %(name)s: %(message)s"

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S"))

    root_logger = logging.getLogger()
    root_logger.addHandler(console_handler)
    root_logger.setLevel(level)

    if log_file:
        try:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            from logging.handlers import RotatingFileHandler
            file_handler = RotatingFileHandler(
                str(log_path),
                maxBytes=10 * 1024 * 1024,
                backupCount=3,
                encoding="utf-8",
            )
            file_handler.setFormatter(logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S"))
            root_logger.addHandler(file_handler)
            logger.debug(f"Logging to file: {log_file}")
        except OSError as e:
            logger.warning(f"Failed to setup file logging: {e}")

    return root_logger


try:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    _HAS_HTTP = True
except ImportError:
    _HAS_HTTP = False


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_SEARCH_PATHS: list[Path] = [
    Path(r"C:\Program Files\Adobe\Adobe Audition 2025\Audition.exe"),
    Path(r"D:\Program Files\Adobe\Adobe Audition 2025\Audition.exe"),
    Path(r"E:\Program Files\Adobe\Adobe Audition 2025\Audition.exe"),
    Path(r"C:\Program Files\Adobe\Adobe Audition 2024\Audition.exe"),
]
AU_PROCESS_NAME = "Audition.exe"
AU_WINDOW_CLASS = "Audition"
AU_WINDOW_TITLE_KEYWORD = "Audition"

DEFAULT_CLOSE_TIMEOUT = 30
DEFAULT_FORCE_KILL_TIMEOUT = 10
DEFAULT_START_TIMEOUT = 60
DEFAULT_HEALTH_CHECK_INTERVAL = 5
MEMORY_LEAK_WINDOW_SIZE = 10
MEMORY_LEAK_THRESHOLD_RATIO = 1.5


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class AUState(str, Enum):
    """AU 进程状态枚举。"""

    OFF = "OFF"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    CLOSING = "CLOSING"
    CRASHED = "CRASHED"
    RECOVERING = "RECOVERING"


class HealthStatus(str, Enum):
    """AU 健康状态枚举。"""

    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    CRASHED = "CRASHED"


class LaunchMode(str, Enum):
    """AU 启动模式枚举。"""

    NORMAL = "normal"
    HEADLESS = "headless"
    SAFE_MODE = "safe_mode"


class CloseMethod(str, Enum):
    """关闭方式枚举。"""

    WM_CLOSE = "wm_close"
    FORCE_KILL = "force_kill"
    TASKKILL = "taskkill"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
class AUProcessError(Exception):
    """AU 进程操作基础异常。"""


class InvalidStateTransitionError(AUProcessError):
    """非法状态转换异常。"""

    def __init__(self, from_state: AUState, to_state: AUState):
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(
            f"非法状态转换: {from_state.value} -> {to_state.value}"
        )


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
class AUMetrics:
    """AU 进程指标数据。"""

    pid: int | None
    cpu_percent: float
    memory_mb: float
    memory_percent: float
    handle_count: int
    thread_count: int
    uptime_seconds: float
    timestamp: float

    def __init__(
        self,
        pid: int | None = None,
        cpu_percent: float = 0.0,
        memory_mb: float = 0.0,
        memory_percent: float = 0.0,
        handle_count: int = 0,
        thread_count: int = 0,
        uptime_seconds: float = 0.0,
    ):
        self.pid = pid
        self.cpu_percent = cpu_percent
        self.memory_mb = memory_mb
        self.memory_percent = memory_percent
        self.handle_count = handle_count
        self.thread_count = thread_count
        self.uptime_seconds = uptime_seconds
        self.timestamp = time.time()

    def to_dict(self) -> dict[str, Any]:
        return {
            "pid": self.pid,
            "cpu_percent": round(self.cpu_percent, 2),
            "memory_mb": round(self.memory_mb, 2),
            "memory_percent": round(self.memory_percent, 2),
            "handle_count": self.handle_count,
            "thread_count": self.thread_count,
            "uptime_seconds": round(self.uptime_seconds, 1),
            "uptime_human": str(timedelta(seconds=int(self.uptime_seconds))),
            "timestamp": self.timestamp,
        }


class HealthReport:
    """健康检查报告。"""

    status: HealthStatus
    details: dict[str, Any]
    recommendations: list[str]
    timestamp: float

    def __init__(
        self,
        status: HealthStatus = HealthStatus.HEALTHY,
        details: dict[str, Any] | None = None,
        recommendations: list[str] | None = None,
    ):
        self.status = status
        self.details = details or {}
        self.recommendations = recommendations or []
        self.timestamp = time.time()

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "details": self.details,
            "recommendations": self.recommendations,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Win32 API helpers
# ---------------------------------------------------------------------------
class _Win32API:
    """Win32 API 封装，优雅降级。"""

    _available: bool | None = None

    WM_CLOSE = 0x0010
    WM_COMMAND = 0x0111
    BM_CLICK = 0x00F5
    GW_OWNER = 4
    GWL_STYLE = -16
    WS_VISIBLE = 0x10000000

    @classmethod
    def is_available(cls) -> bool:
        if cls._available is None:
            try:
                _ = ctypes.windll.user32.EnumWindows
                cls._available = True
            except Exception:
                cls._available = False
        return cls._available

    @staticmethod
    def _get_window_text(hwnd) -> str:
        try:
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return ""
            buf = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
            return buf.value
        except Exception:
            return ""

    @staticmethod
    def _get_window_class(hwnd) -> str:
        try:
            buf = ctypes.create_unicode_buffer(256)
            ctypes.windll.user32.GetClassNameW(hwnd, buf, 256)
            return buf.value
        except Exception:
            return ""

    @staticmethod
    def _is_window_visible(hwnd) -> bool:
        try:
            return bool(ctypes.windll.user32.IsWindowVisible(hwnd))
        except Exception:
            return False

    @staticmethod
    def _get_window_thread_process_id(hwnd) -> tuple[int, int]:
        try:
            pid = wintypes.DWORD()
            tid = ctypes.windll.user32.GetWindowThreadProcessId(
                hwnd, ctypes.byref(pid)
            )
            return tid, pid.value
        except Exception:
            return 0, 0

    @classmethod
    def find_windows(
        cls,
        title_keyword: str | None = None,
        class_name: str | None = None,
        pid: int | None = None,
        visible_only: bool = True,
    ) -> list[int]:
        if not cls.is_available():
            return []

        results: list[int] = []

        def enum_callback(hwnd, lParam):
            if visible_only and not cls._is_window_visible(hwnd):
                return True

            if title_keyword:
                title = cls._get_window_text(hwnd)
                if title_keyword.lower() not in title.lower():
                    return True

            if class_name:
                wclass = cls._get_window_class(hwnd)
                if class_name.lower() != wclass.lower():
                    return True

            if pid is not None:
                _, win_pid = cls._get_window_thread_process_id(hwnd)
                if win_pid != pid:
                    return True

            results.append(hwnd)
            return True

        try:
            WNDENUMPROC = ctypes.WINFUNCTYPE(
                wintypes.BOOL, wintypes.HWND, wintypes.LPARAM
            )
            callback = WNDENUMPROC(enum_callback)
            ctypes.windll.user32.EnumWindows(callback, 0)
        except Exception:
            pass

        return results

    @classmethod
    def find_au_main_window(cls, pid: int | None = None) -> int | None:
        if not cls.is_available():
            return None

        windows = cls.find_windows(
            class_name=AU_WINDOW_CLASS, pid=pid, visible_only=True
        )
        if windows:
            return windows[0]

        windows = cls.find_windows(
            title_keyword=AU_WINDOW_TITLE_KEYWORD, pid=pid, visible_only=True
        )
        if windows:
            return windows[0]

        return None

    @classmethod
    def send_wm_close(cls, hwnd: int) -> bool:
        if not cls.is_available():
            return False
        try:
            result = ctypes.windll.user32.PostMessageW(
                hwnd, cls.WM_CLOSE, 0, 0
            )
            return bool(result)
        except Exception:
            return False

    @classmethod
    def is_window_responsive(cls, hwnd: int, timeout_ms: int = 5000) -> bool:
        if not cls.is_available():
            return True
        try:
            SMTO_ABORTIFHUNG = 0x0002
            WM_NULL = 0x0000
            result = wintypes.DWORD()
            ret = ctypes.windll.user32.SendMessageTimeoutW(
                hwnd,
                WM_NULL,
                0,
                0,
                SMTO_ABORTIFHUNG,
                timeout_ms,
                ctypes.byref(result),
            )
            return ret != 0
        except Exception:
            return False


# ---------------------------------------------------------------------------
# AUProcessManager
# ---------------------------------------------------------------------------
class AUProcessManager:
    """生产级 Audition 进程生命周期管理器。

    提供完整的进程生命周期管理、健康监控、自动恢复和指标采集功能。
    """

    def __init__(
        self,
        au_exe_path: str | None = None,
        listener_script_path: str | None = None,
        close_timeout: int = DEFAULT_CLOSE_TIMEOUT,
        force_kill_timeout: int = DEFAULT_FORCE_KILL_TIMEOUT,
        start_timeout: int = DEFAULT_START_TIMEOUT,
        memory_leak_threshold_ratio: float = MEMORY_LEAK_THRESHOLD_RATIO,
        memory_leak_window_size: int = MEMORY_LEAK_WINDOW_SIZE,
        backend: Any | None = None,
    ):
        """初始化 AU 进程管理器。

        Args:
            au_exe_path: AU 可执行文件路径，None 则自动查找
            listener_script_path: MCP 监听脚本路径，None 则自动查找
            close_timeout: 优雅关闭超时时间（秒）
            force_kill_timeout: 强制关闭等待时间（秒）
            start_timeout: 启动超时时间（秒）
            memory_leak_threshold_ratio: 内存泄漏检测阈值倍率
            memory_leak_window_size: 内存趋势分析窗口大小
        """
        self.au_exe_path: Path | None = None
        self.listener_script_path: Path | None = None
        self.close_timeout: int = close_timeout
        self.force_kill_timeout: int = force_kill_timeout
        self.start_timeout: int = start_timeout
        self.memory_leak_threshold_ratio: float = memory_leak_threshold_ratio
        self.memory_leak_window_size: int = memory_leak_window_size

        self._last_status: dict[str, Any] = {}
        self._started_by_manager: bool = False
        self._au_pid: int | None = None
        self._state: AUState = AUState.OFF
        self._state_callbacks: list[Callable[[AUState, AUState], None]] = []
        self._metrics_history: deque[AUMetrics] = deque(
            maxlen=memory_leak_window_size
        )
        self._health_history: deque[HealthReport] = deque(maxlen=20)
        self._last_close_method: CloseMethod | None = None
        self._workspace_path: Path | None = None
        self._launch_mode: LaunchMode = LaunchMode.NORMAL
        self._extra_args: list[str] = []
        self._crash_count: int = 0
        self._recovery_count: int = 0
        self._lock = threading.RLock()

        if backend is not None:
            self._backend = backend
        elif auto_detect_backend is not None:
            self._backend = auto_detect_backend()
        else:
            self._backend = None

        if au_exe_path:
            candidate = Path(au_exe_path)
            if candidate.exists():
                self.au_exe_path = candidate.resolve()
            else:
                raise FileNotFoundError(
                    f"Provided AU executable not found: {au_exe_path}"
                )
        else:
            self.au_exe_path = self._find_au_executable()

        self._sync_state_from_process()

    # --------------- State machine ---------------

    @property
    def state(self) -> AUState:
        with self._lock:
            return self._state

    @property
    def crash_count(self) -> int:
        with self._lock:
            return self._crash_count

    @property
    def recovery_count(self) -> int:
        with self._lock:
            return self._recovery_count

    def add_state_callback(
        self, callback: Callable[[AUState, AUState], None]
    ) -> None:
        with self._lock:
            self._state_callbacks.append(callback)

    def remove_state_callback(
        self, callback: Callable[[AUState, AUState], None]
    ) -> None:
        with self._lock:
            if callback in self._state_callbacks:
                self._state_callbacks.remove(callback)

    def _transition_to(self, new_state: AUState) -> None:
        with self._lock:
            if self._state == new_state:
                return

            valid_transitions = {
                AUState.OFF: {AUState.STARTING, AUState.RECOVERING},
                AUState.STARTING: {AUState.RUNNING, AUState.CRASHED, AUState.CLOSING, AUState.OFF},
                AUState.RUNNING: {AUState.CLOSING, AUState.CRASHED, AUState.OFF},
                AUState.CLOSING: {AUState.OFF, AUState.CRASHED},
                AUState.CRASHED: {AUState.RECOVERING, AUState.OFF},
                AUState.RECOVERING: {AUState.STARTING, AUState.OFF, AUState.CRASHED},
            }

            allowed = valid_transitions.get(self._state, set())
            if new_state not in allowed and new_state != self._state:
                raise InvalidStateTransitionError(self._state, new_state)

            old_state = self._state
            self._state = new_state
            callbacks = list(self._state_callbacks)

        for cb in callbacks:
            try:
                cb(old_state, new_state)
            except Exception:
                pass

    def _sync_state_from_process(self) -> None:
        running = self._is_running_fast()
        callbacks_to_invoke: list[tuple[AUState, AUState]] = []
        with self._lock:
            if not running:
                if self._state in (AUState.STARTING, AUState.RUNNING, AUState.RECOVERING):
                    self._crash_count += 1
                    old_state = self._state
                    self._state = AUState.CRASHED
                    callbacks_to_invoke.append((old_state, AUState.CRASHED))
                elif self._state == AUState.CLOSING:
                    old_state = self._state
                    self._state = AUState.OFF
                    callbacks_to_invoke.append((old_state, AUState.OFF))
                else:
                    self._state = AUState.OFF
            else:
                if self._state in (AUState.OFF, AUState.CRASHED):
                    self._state = AUState.RUNNING
                elif self._state == AUState.STARTING:
                    old_state = self._state
                    self._state = AUState.RUNNING
                    callbacks_to_invoke.append((old_state, AUState.RUNNING))

        if callbacks_to_invoke:
            with self._lock:
                callbacks = list(self._state_callbacks)
            for old_state, new_state in callbacks_to_invoke:
                for cb in callbacks:
                    try:
                        cb(old_state, new_state)
                    except Exception:
                        pass

    # --------------- Discovery helpers ---------------

    @staticmethod
    def _find_au_executable() -> Path | None:
        for p in DEFAULT_SEARCH_PATHS:
            if p.exists():
                return p.resolve()
        for root in [Path(r"C:\Program Files\Adobe"), Path(r"D:\Program Files\Adobe")]:
            if not root.exists():
                continue
            for sub in root.iterdir():
                if sub.is_dir() and "Audition" in sub.name:
                    for exe_name in ["Audition.exe"]:
                        exe = sub / exe_name
                        if exe.exists():
                            return exe.resolve()
        return None

    # --------------- Process queries ---------------

    def _is_running_fast(self) -> bool:
        with self._lock:
            cached_pid = self._au_pid
        if cached_pid is not None:
            if self._backend is not None:
                if hasattr(self._backend, 'pid_exists') and self._backend.pid_exists(cached_pid):
                    return True
            else:
                try:
                    import psutil
                    if psutil.pid_exists(cached_pid):
                        return True
                except ImportError:
                    pass

        if self._backend is not None:
            return self._backend.is_running(AU_PROCESS_NAME)
        try:
            import psutil

            for proc in psutil.process_iter(["name"]):
                try:
                    if (
                        proc.info["name"]
                        and proc.info["name"].lower()
                        == AU_PROCESS_NAME.lower()
                    ):
                        with self._lock:
                            self._au_pid = proc.pid
                        return True
                except Exception:
                    continue
            return False
        except ImportError:
            return self._is_running_via_tasklist()

    def is_au_running(self) -> bool:
        running = self._is_running_fast()
        with self._lock:
            if running and self._state == AUState.OFF:
                self._state = AUState.RUNNING
            elif not running and self._state not in (
                AUState.OFF,
                AUState.CRASHED,
                AUState.CLOSING,
            ):
                pass
        if not running:
            self._sync_state_from_process()
        return running

    @staticmethod
    def _is_running_via_tasklist() -> bool:
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {AU_PROCESS_NAME}"],
                capture_output=True,
                text=True,
                check=False,
            )
            return AU_PROCESS_NAME.lower() in result.stdout.lower()
        except Exception:
            return False

    def _get_au_process(self):
        if self._backend is not None:
            return self._backend.find_process(AU_PROCESS_NAME)
        try:
            import psutil

            for proc in psutil.process_iter(["name", "pid"]):
                try:
                    if (
                        proc.info["name"]
                        and proc.info["name"].lower()
                        == AU_PROCESS_NAME.lower()
                    ):
                        return proc
                except Exception:
                    continue
        except ImportError:
            pass
        return None

    def get_au_pid(self) -> int | None:
        proc = self._get_au_process()
        if proc:
            with self._lock:
                self._au_pid = proc.pid
            return proc.pid
        with self._lock:
            self._au_pid = None
        return None

    def get_au_status(self) -> dict[str, Any]:
        running = self.is_au_running()
        with self._lock:
            state_val = self._state.value
            started_by_manager = self._started_by_manager
            crash_count = self._crash_count
            recovery_count = self._recovery_count
            launch_mode_val = self._launch_mode.value
        status = {
            "running": running,
            "state": state_val,
            "au_exe_path": str(self.au_exe_path) if self.au_exe_path else None,
            "started_by_manager": started_by_manager,
            "crash_count": crash_count,
            "recovery_count": recovery_count,
            "launch_mode": launch_mode_val,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        if running:
            pid = self.get_au_pid()
            status["pid"] = pid
            if pid:
                try:
                    import psutil

                    proc = psutil.Process(pid)
                    status["create_time"] = proc.create_time()
                    with proc.oneshot():
                        status["cpu_percent"] = proc.cpu_percent(interval=0.1)
                        mem = proc.memory_info()
                        status["memory_mb"] = round(mem.rss / 1024 / 1024, 2)
                except Exception:
                    pass
        else:
            status["pid"] = None
            status["create_time"] = None

        with self._lock:
            self._last_status = status
        return status

    # --------------- Process metrics ---------------

    def get_au_metrics(self) -> AUMetrics:
        metrics = AUMetrics()

        try:
            import psutil

            proc = self._get_au_process()
            if proc is None:
                with self._lock:
                    self._metrics_history.append(metrics)
                return metrics

            metrics.pid = proc.pid
            with self._lock:
                self._au_pid = proc.pid

            with proc.oneshot():
                metrics.cpu_percent = proc.cpu_percent(interval=0.1)
                mem = proc.memory_info()
                metrics.memory_mb = mem.rss / 1024 / 1024
                metrics.memory_percent = proc.memory_percent()
                metrics.thread_count = proc.num_threads()

                try:
                    metrics.handle_count = proc.num_handles()
                except Exception:
                    metrics.handle_count = 0

                try:
                    create_time = proc.create_time()
                    metrics.uptime_seconds = time.time() - create_time
                except Exception:
                    pass

        except ImportError:
            pid = self.get_au_pid()
            metrics.pid = pid

        with self._lock:
            self._metrics_history.append(metrics)
        return metrics

    def detect_memory_leak(self) -> tuple[bool, dict[str, Any]]:
        with self._lock:
            history_len = len(self._metrics_history)
            if history_len < 3:
                return False, {"reason": "insufficient_data", "samples": history_len}

            mem_values = [m.memory_mb for m in self._metrics_history if m.memory_mb > 0]
            threshold = self.memory_leak_threshold_ratio

        if len(mem_values) < 3:
            return False, {"reason": "insufficient_valid_samples"}

        first_third_avg = sum(mem_values[: len(mem_values) // 3]) / (
            len(mem_values) // 3 or 1
        )
        last_third_avg = sum(mem_values[-len(mem_values) // 3 :]) / (
            len(mem_values) // 3 or 1
        )

        ratio = last_third_avg / first_third_avg if first_third_avg > 0 else 1.0
        is_leaking = ratio > threshold

        return is_leaking, {
            "first_avg_mb": round(first_third_avg, 2),
            "last_avg_mb": round(last_third_avg, 2),
            "ratio": round(ratio, 2),
            "threshold": threshold,
            "samples": len(mem_values),
            "trend": "increasing" if ratio > 1.1 else ("decreasing" if ratio < 0.9 else "stable"),
        }

    # --------------- Health checking (Watchdog) ---------------

    def is_au_healthy(self) -> HealthReport:
        report = HealthReport()
        details: dict[str, Any] = {}
        recommendations: list[str] = []

        if not self.is_au_running():
            report.status = HealthStatus.CRASHED
            report.details = {"process": "not_running"}
            report.recommendations = ["启动 Audition 进程"]
            self._health_history.append(report)
            return report

        pid = self.get_au_pid()
        details["pid"] = pid

        metrics = self.get_au_metrics()
        details["metrics"] = metrics.to_dict()

        window_hwnd = None
        window_responsive = True
        if _Win32API.is_available() and pid:
            window_hwnd = _Win32API.find_au_main_window(pid=pid)
            if window_hwnd:
                window_responsive = _Win32API.is_window_responsive(
                    window_hwnd, timeout_ms=3000
                )
                details["window_handle"] = hex(window_hwnd)
                details["window_responsive"] = window_responsive
            else:
                details["window_found"] = False

        is_leaking, leak_info = self.detect_memory_leak()
        details["memory_leak"] = leak_info

        health_score = 100

        if not window_responsive:
            health_score -= 40
            recommendations.append("主窗口无响应，可能需要重启 Audition")

        if is_leaking:
            health_score -= 25
            recommendations.append("检测到内存泄漏趋势，建议重启 Audition")

        if metrics.memory_mb > 8000:
            health_score -= 20
            recommendations.append("内存使用超过 8GB，建议重启释放内存")

        if metrics.cpu_percent > 95 and metrics.uptime_seconds > 60:
            health_score -= 15
            recommendations.append("CPU 持续高负载，检查是否有长时间处理任务")

        if health_score >= 80:
            report.status = HealthStatus.HEALTHY
        elif health_score >= 50:
            report.status = HealthStatus.DEGRADED
        elif health_score >= 20:
            report.status = HealthStatus.UNHEALTHY
        else:
            report.status = HealthStatus.CRASHED

        details["health_score"] = health_score
        report.details = details
        report.recommendations = recommendations
        with self._lock:
            self._health_history.append(report)

        return report

    def auto_recover(self) -> bool:
        health = self.is_au_healthy()

        if health.status == HealthStatus.HEALTHY:
            return True

        logger.warning(f"Audition 健康状态: {health.status.value}")
        for rec in health.recommendations:
            logger.warning(f"建议: {rec}")

        if health.status in (HealthStatus.UNHEALTHY, HealthStatus.CRASHED):
            logger.info("触发自动恢复流程...")
            with self._lock:
                self._recovery_count += 1

            try:
                self._transition_to(AUState.RECOVERING)
            except InvalidStateTransitionError:
                with self._lock:
                    self._state = AUState.RECOVERING

            try:
                self._close_au_gracefully_or_force()
            except Exception:
                pass

            time.sleep(2)
            self.clear_crash_state()
            time.sleep(1)

            return self.start_au_with_listener()

        return False

    # --------------- Crash state cleanup ---------------

    def clear_crash_state(self) -> dict[str, Any]:
        result = {
            "registry_keys_cleared": [],
            "files_removed": [],
            "errors": [],
        }

        au_versions = ["25.0", "24.0", "23.0", "22.0"]

        for version_key in au_versions:
            reg_path = rf"Software\Adobe\Audition\{version_key}"
            try:
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    reg_path,
                    0,
                    winreg.KEY_SET_VALUE | winreg.KEY_READ,
                )
                try:
                    winreg.SetValueEx(key, "AppState", 0, winreg.REG_DWORD, 0)
                    result["registry_keys_cleared"].append(
                        f"{reg_path}\\AppState"
                    )

                    crash_values = [
                        "AppStateDunamisSessionID",
                        "SessionDuration",
                        "CrashRptEnabled",
                        "LastCrashTime",
                        "CrashCount",
                        "DunamisCrashSessionID",
                    ]
                    for crash_val in crash_values:
                        try:
                            winreg.DeleteValue(key, crash_val)
                            result["registry_keys_cleared"].append(
                                f"{reg_path}\\{crash_val}"
                            )
                        except FileNotFoundError:
                            pass
                finally:
                    winreg.CloseKey(key)
            except FileNotFoundError:
                pass
            except Exception as e:
                result["errors"].append(f"Registry {reg_path}: {e}")

        au_roaming = Path(
            os.path.join(
                str(Path.home()), "AppData", "Roaming", "Adobe", "Audition"
            )
        )
        if au_roaming.exists():
            for version_dir in au_roaming.iterdir():
                if not version_dir.is_dir():
                    continue

                for pattern in ["*crash*", "*Crash*", "*CrashRpt*", "*.dmp"]:
                    for crash_file in version_dir.glob(pattern):
                        try:
                            if crash_file.is_file():
                                crash_file.unlink()
                                result["files_removed"].append(str(crash_file))
                        except Exception as e:
                            result["errors"].append(f"{crash_file}: {e}")

                crash_dirs = ["CrashReports", "CrashDumps", "logs"]
                for dname in crash_dirs:
                    dpath = version_dir / dname
                    if dpath.exists() and dpath.is_dir():
                        try:
                            for f in dpath.iterdir():
                                if f.is_file():
                                    f.unlink()
                                    result["files_removed"].append(str(f))
                        except Exception as e:
                            result["errors"].append(f"{dpath}: {e}")

        return result

    def _clear_crash_state(self) -> None:
        try:
            self.clear_crash_state()
        except Exception:
            pass

    # --------------- Startup configuration ---------------

    def set_launch_mode(self, mode: LaunchMode) -> None:
        with self._lock:
            self._launch_mode = mode

    def set_workspace(self, workspace_path: str | Path | None) -> None:
        if workspace_path is None:
            with self._lock:
                self._workspace_path = None
            return
        p = Path(workspace_path)
        if p.suffix.lower() not in (".sesx",):
            raise ValueError(f"工作区文件必须是 .sesx 格式: {workspace_path}")
        with self._lock:
            self._workspace_path = p.resolve()

    def set_extra_args(self, args: list[str]) -> None:
        with self._lock:
            self._extra_args = list(args)

    def _build_launch_args(self) -> list[str]:
        if not self.au_exe_path:
            raise AUProcessError("AU 可执行文件路径未设置")

        with self._lock:
            launch_mode = self._launch_mode
            workspace_path = self._workspace_path
            extra_args = list(self._extra_args)

        args: list[str] = [str(self.au_exe_path)]

        if launch_mode == LaunchMode.SAFE_MODE:
            args.append("-safe")

        if workspace_path and workspace_path.exists():
            args.append(str(workspace_path))

        args.extend(extra_args)

        return args

    # --------------- Lifecycle actions ---------------

    def start_au_with_listener(
        self,
        mode: LaunchMode | None = None,
        workspace: str | Path | None = None,
    ) -> bool:
        if self.is_au_running():
            logger.info("Audition is already running.")
            try:
                self._transition_to(AUState.RUNNING)
            except InvalidStateTransitionError:
                pass
            return True

        if not self.au_exe_path:
            logger.error("Audition executable not found.")
            return False

        if mode is not None:
            with self._lock:
                self._launch_mode = mode
        if workspace is not None:
            self.set_workspace(workspace)

        try:
            self._transition_to(AUState.STARTING)
        except InvalidStateTransitionError:
            with self._lock:
                self._state = AUState.STARTING

        self.clear_crash_state()

        try:
            launch_args = self._build_launch_args()
            with self._lock:
                launch_mode_val = self._launch_mode.value
                workspace_path = self._workspace_path
            logger.info(f"Starting Audition ({launch_mode_val}): {self.au_exe_path}")
            if workspace_path:
                logger.info(f"Workspace: {workspace_path}")

            subprocess.Popen(
                launch_args,
                shell=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            with self._lock:
                self._started_by_manager = True
            logger.info("Audition launched (waiting for startup)...")

            detected = False
            for i in range(self.start_timeout):
                time.sleep(1)
                if self.is_au_running():
                    pid = self.get_au_pid()
                    with self._lock:
                        self._au_pid = pid
                    logger.info(f"Audition process detected ({i+1}s)")
                    detected = True
                    break

            if not detected:
                logger.error(f"Audition did not start within {self.start_timeout}s")
                try:
                    self._transition_to(AUState.CRASHED)
                except InvalidStateTransitionError:
                    with self._lock:
                        self._state = AUState.CRASHED
                return False

            logger.info("Waiting for Audition to fully initialize (10s)...")
            time.sleep(10)

            try:
                self._transition_to(AUState.RUNNING)
            except InvalidStateTransitionError:
                with self._lock:
                    self._state = AUState.RUNNING

            return True

        except Exception as exc:
            logger.error(f"Failed to start Audition: {exc}")
            try:
                self._transition_to(AUState.CRASHED)
            except InvalidStateTransitionError:
                with self._lock:
                    self._state = AUState.CRASHED
            return False

    def start_au_async(
        self,
        mode: LaunchMode | None = None,
        workspace: str | Path | None = None,
    ) -> "Future[bool]":
        future: Future[bool] = Future()

        def _worker() -> None:
            try:
                result = self.start_au_with_listener(mode=mode, workspace=workspace)
                future.set_result(result)
            except Exception as exc:
                logger.error(f"Async AU start failed: {exc}")
                future.set_exception(exc)

        thread = threading.Thread(
            target=_worker,
            name="au-async-start",
            daemon=True,
        )
        thread.start()
        logger.info("AU async start initiated (thread: au-async-start)")
        return future

    def close_au(self, timeout: int | None = None) -> bool:
        if not self.is_au_running():
            logger.info("Audition is not running.")
            try:
                self._transition_to(AUState.OFF)
            except InvalidStateTransitionError:
                with self._lock:
                    self._state = AUState.OFF
            return True

        wait_timeout = timeout if timeout is not None else self.close_timeout

        try:
            self._transition_to(AUState.CLOSING)
        except InvalidStateTransitionError:
            with self._lock:
                self._state = AUState.CLOSING

        return self._close_au_gracefully_or_force(wait_timeout)

    def _close_au_gracefully_or_force(self, timeout: int | None = None) -> bool:
        wait_timeout = timeout if timeout is not None else self.close_timeout
        closed_via_wm = False

        if _Win32API.is_available():
            pid = self.get_au_pid()
            hwnd = _Win32API.find_au_main_window(pid=pid)
            if hwnd:
                logger.info("Found Audition window, sending WM_CLOSE...")
                if _Win32API.send_wm_close(hwnd):
                    closed_via_wm = True
                    with self._lock:
                        self._last_close_method = CloseMethod.WM_CLOSE

                    for i in range(wait_timeout):
                        if not self.is_au_running():
                            logger.info(f"Audition exited gracefully via WM_CLOSE ({i+1}s)")
                            try:
                                self._transition_to(AUState.OFF)
                            except InvalidStateTransitionError:
                                with self._lock:
                                    self._state = AUState.OFF
                            with self._lock:
                                self._started_by_manager = False
                                self._au_pid = None
                            return True
                        time.sleep(1)

                    logger.warning("Audition did not exit after WM_CLOSE, trying force-kill...")
                else:
                    logger.warning("Failed to send WM_CLOSE, trying force-kill...")
            else:
                logger.warning("Could not find Audition main window, trying force-kill...")
        else:
            logger.warning("Win32 API not available, using force-kill...")

        return self._force_kill_au()

    def _force_kill_au(self) -> bool:
        logger.info("Force-killing Audition...")
        with self._lock:
            self._last_close_method = CloseMethod.FORCE_KILL

        try:
            subprocess.run(
                ["taskkill", "/F", "/IM", AU_PROCESS_NAME],
                capture_output=True,
                text=True,
            )
        except Exception as e:
            logger.warning(f"Failed to force-kill AU via taskkill: {e}")

        time.sleep(self.force_kill_timeout)

        if not self.is_au_running():
            logger.info("Audition force-killed successfully")
            try:
                self._transition_to(AUState.OFF)
            except InvalidStateTransitionError:
                with self._lock:
                    self._state = AUState.OFF
            with self._lock:
                self._started_by_manager = False
                self._au_pid = None
            self.clear_crash_state()
            return True

        logger.error("Failed to force-kill Audition")
        return False

    def restart_au(self) -> bool:
        logger.info("Restarting Audition...")
        self.close_au()
        time.sleep(2)
        return self.start_au_with_listener()