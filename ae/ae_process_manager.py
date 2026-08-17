#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AE Process Manager
==================
生产级 After Effects 进程管理器。

功能特性：
- WM_CLOSE 优雅关闭，超时降级强制关闭
- 看门狗健康检测与自动恢复
- 崩溃状态全面清理（注册表、AppState、CrashRpt）
- 进程指标监控与内存泄漏检测
- 多种启动模式（normal / headless / safe_mode）
- 状态机管理与状态变化回调

Usage:
    python ae_process_manager.py
    python ae_process_manager.py --api --port 8123
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
        ProcessBackend = None  # type: ignore
        auto_detect_backend = None  # type: ignore

logger = logging.getLogger(__name__)


def setup_logging(level: int = logging.INFO, format_str: str | None = None, log_file: str | None = None) -> logging.Logger:
    """配置结构化日志。

    v2.0: 支持文件输出和日志轮转（单文件上限 10MB）。

    Args:
        level: 日志级别（默认 INFO）
        format_str: 自定义格式字符串
        log_file: 日志文件路径（可选）。如果提供，日志同时写入文件。

    Returns:
        配置好的 root logger 实例。
    """
    fmt = format_str or "[%(asctime)s] %(levelname)-8s [%(component)s] %(name)s: %(message)s"

    # 控制台 Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(ComponentFormatter(fmt, datefmt="%Y-%m-%d %H:%M:%S"))

    root_logger = logging.getLogger()
    root_logger.addHandler(console_handler)
    root_logger.setLevel(level)

    # 文件 Handler（v2.0: 支持日志轮转）
    if log_file:
        try:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            # 使用 RotatingFileHandler 实现日志轮转（10MB 上限，保留 3 个备份）
            from logging.handlers import RotatingFileHandler
            file_handler = RotatingFileHandler(
                str(log_path),
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=3,
                encoding="utf-8",
            )
            file_handler.setFormatter(ComponentFormatter(fmt, datefmt="%Y-%m-%d %H:%M:%S"))
            root_logger.addHandler(file_handler)
            logger.debug(f"Logging to file: {log_file}")
        except OSError as e:
            logger.warning(f"Failed to setup file logging: {e}")

    return root_logger


class ComponentFormatter(logging.Formatter):
    """日志格式化器，支持 component 字段。

    如果 logger 没有 component 属性，默认使用 'general'。
    """

    def format(self, record: logging.LogRecord) -> str:
        if not hasattr(record, "component"):
            record.component = "general"  # type: ignore
        return super().format(record)

try:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    _HAS_HTTP = True
except ImportError:
    _HAS_HTTP = False


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_LISTENER = Path(__file__).parent.parent / "ae_mcp_auto_listener.jsx"
DEFAULT_SEARCH_PATHS: List[Path] = [
    Path(r"C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\AfterFX.exe"),
    Path(r"D:\Program Files\Adobe\Adobe After Effects 2025\Support Files\AfterFX.exe"),
    Path(r"E:\Program Files\Adobe\Adobe After Effects 2025\Support Files\AfterFX.exe"),
]
AE_PROCESS_NAME = "AfterFX.exe"
AE_WINDOW_CLASS = "AfterEffects"
AE_WINDOW_TITLE_KEYWORD = "After Effects"

DEFAULT_CLOSE_TIMEOUT = 30
DEFAULT_FORCE_KILL_TIMEOUT = 10
DEFAULT_START_TIMEOUT = 60
DEFAULT_HEALTH_CHECK_INTERVAL = 5
MEMORY_LEAK_WINDOW_SIZE = 10
MEMORY_LEAK_THRESHOLD_RATIO = 1.5


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class AEState(str, Enum):
    """AE 进程状态枚举。"""

    OFF = "OFF"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    CLOSING = "CLOSING"
    CRASHED = "CRASHED"
    RECOVERING = "RECOVERING"


class HealthStatus(str, Enum):
    """AE 健康状态枚举。"""

    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    CRASHED = "CRASHED"


class LaunchMode(str, Enum):
    """AE 启动模式枚举。"""

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
class AEProcessError(Exception):
    """AE 进程操作基础异常。"""


class InvalidStateTransitionError(AEProcessError):
    """非法状态转换异常。"""

    def __init__(self, from_state: AEState, to_state: AEState):
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(
            f"非法状态转换: {from_state.value} -> {to_state.value}"
        )


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
class AEMetrics:
    """AE 进程指标数据。"""

    pid: Optional[int]
    cpu_percent: float
    memory_mb: float
    memory_percent: float
    handle_count: int
    thread_count: int
    uptime_seconds: float
    timestamp: float

    def __init__(
        self,
        pid: Optional[int] = None,
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

    def to_dict(self) -> Dict[str, Any]:
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
    details: Dict[str, Any]
    recommendations: List[str]
    timestamp: float

    def __init__(
        self,
        status: HealthStatus = HealthStatus.HEALTHY,
        details: Optional[Dict[str, Any]] = None,
        recommendations: Optional[List[str]] = None,
    ):
        self.status = status
        self.details = details or {}
        self.recommendations = recommendations or []
        self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
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

    _available: Optional[bool] = None

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
    def _get_window_thread_process_id(hwnd) -> Tuple[int, int]:
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
        title_keyword: Optional[str] = None,
        class_name: Optional[str] = None,
        pid: Optional[int] = None,
        visible_only: bool = True,
    ) -> List[int]:
        """按多种条件查找窗口句柄列表。

        Args:
            title_keyword: 窗口标题关键词（模糊匹配）
            class_name: 窗口类名（精确匹配）
            pid: 进程 ID
            visible_only: 仅查找可见窗口

        Returns:
            匹配的窗口句柄列表
        """
        if not cls.is_available():
            return []

        results: List[int] = []

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
    def find_ae_main_window(cls, pid: Optional[int] = None) -> Optional[int]:
        """查找 AE 主窗口。

        优先按类名查找，其次按标题关键词。
        """
        if not cls.is_available():
            return None

        windows = cls.find_windows(
            class_name=AE_WINDOW_CLASS, pid=pid, visible_only=True
        )
        if windows:
            return windows[0]

        windows = cls.find_windows(
            title_keyword=AE_WINDOW_TITLE_KEYWORD, pid=pid, visible_only=True
        )
        if windows:
            return windows[0]

        return None

    @classmethod
    def find_save_dialog(cls, owner_pid: Optional[int] = None) -> Optional[int]:
        """查找保存对话框。

        Args:
            owner_pid: 所属进程 ID

        Returns:
            对话框句柄或 None
        """
        if not cls.is_available():
            return None

        dialog_classes = [
            "#32770",
            "SaveDialog",
            "Save As",
        ]

        for dlg_class in dialog_classes:
            windows = cls.find_windows(
                class_name=dlg_class, visible_only=True
            )
            for hwnd in windows:
                title = cls._get_window_text(hwnd)
                if any(
                    kw in title.lower()
                    for kw in ["save", "保存", "另存", "did you save"]
                ):
                    if owner_pid:
                        _, win_pid = cls._get_window_thread_process_id(hwnd)
                        if win_pid == owner_pid:
                            return hwnd
                    else:
                        return hwnd

        return None

    @classmethod
    def send_wm_close(cls, hwnd: int) -> bool:
        """向指定窗口发送 WM_CLOSE 消息。"""
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
        """检测窗口是否响应（使用 SendMessageTimeout）。"""
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
# AEProcessManager
# ---------------------------------------------------------------------------
class AEProcessManager:
    """生产级 After Effects 进程生命周期管理器。

    提供完整的进程生命周期管理、健康监控、自动恢复和指标采集功能。
    """

    def __init__(
        self,
        ae_exe_path: Optional[str] = None,
        listener_script_path: Optional[str] = None,
        close_timeout: int = DEFAULT_CLOSE_TIMEOUT,
        force_kill_timeout: int = DEFAULT_FORCE_KILL_TIMEOUT,
        start_timeout: int = DEFAULT_START_TIMEOUT,
        memory_leak_threshold_ratio: float = MEMORY_LEAK_THRESHOLD_RATIO,
        memory_leak_window_size: int = MEMORY_LEAK_WINDOW_SIZE,
        backend: Optional[Any] = None,
    ):
        """初始化 AE 进程管理器。

        Args:
            ae_exe_path: AE 可执行文件路径，None 则自动查找
            listener_script_path: MCP 监听脚本路径，None 则自动查找
            close_timeout: 优雅关闭超时时间（秒）
            force_kill_timeout: 强制关闭等待时间（秒）
            start_timeout: 启动超时时间（秒）
            memory_leak_threshold_ratio: 内存泄漏检测阈值倍率
            memory_leak_window_size: 内存趋势分析窗口大小
        """
        self.ae_exe_path: Optional[Path] = None
        self.listener_script_path: Optional[Path] = None
        self.close_timeout: int = close_timeout
        self.force_kill_timeout: int = force_kill_timeout
        self.start_timeout: int = start_timeout
        self.memory_leak_threshold_ratio: float = memory_leak_threshold_ratio
        self.memory_leak_window_size: int = memory_leak_window_size

        self._last_status: Dict[str, Any] = {}
        self._started_by_manager: bool = False
        self._ae_pid: Optional[int] = None
        self._state: AEState = AEState.OFF
        self._state_callbacks: List[Callable[[AEState, AEState], None]] = []
        self._metrics_history: Deque[AEMetrics] = deque(
            maxlen=memory_leak_window_size
        )
        self._health_history: Deque[HealthReport] = deque(maxlen=20)
        self._last_close_method: Optional[CloseMethod] = None
        self._workspace_path: Optional[Path] = None
        self._launch_mode: LaunchMode = LaunchMode.NORMAL
        self._extra_args: List[str] = []
        self._crash_count: int = 0
        self._recovery_count: int = 0
        self._lock = threading.RLock()

        # Process backend
        if backend is not None:
            self._backend = backend
        elif auto_detect_backend is not None:
            self._backend = auto_detect_backend()
        else:
            self._backend = None

        if ae_exe_path:
            candidate = Path(ae_exe_path)
            if candidate.exists():
                self.ae_exe_path = candidate.resolve()
            else:
                raise FileNotFoundError(
                    f"Provided AE executable not found: {ae_exe_path}"
                )
        else:
            self.ae_exe_path = self._find_ae_executable()

        if listener_script_path:
            candidate = Path(listener_script_path)
            if candidate.exists():
                self.listener_script_path = candidate.resolve()
            else:
                raise FileNotFoundError(
                    f"Provided listener script not found: {listener_script_path}"
                )
        else:
            self.listener_script_path = self._find_listener_script()

        self._sync_state_from_process()

    # --------------- State machine ---------------

    @property
    def state(self) -> AEState:
        """当前 AE 状态。"""
        with self._lock:
            return self._state

    @property
    def crash_count(self) -> int:
        """累计崩溃次数。"""
        with self._lock:
            return self._crash_count

    @property
    def recovery_count(self) -> int:
        """累计恢复次数。"""
        with self._lock:
            return self._recovery_count

    def add_state_callback(
        self, callback: Callable[[AEState, AEState], None]
    ) -> None:
        """注册状态变化回调。

        Args:
            callback: 回调函数，签名为 callback(old_state, new_state)
        """
        with self._lock:
            self._state_callbacks.append(callback)

    def remove_state_callback(
        self, callback: Callable[[AEState, AEState], None]
    ) -> None:
        """移除状态变化回调。"""
        with self._lock:
            if callback in self._state_callbacks:
                self._state_callbacks.remove(callback)

    def _transition_to(self, new_state: AEState) -> None:
        """执行状态转换，带守卫检查。

        Args:
            new_state: 目标状态

        Raises:
            InvalidStateTransitionError: 非法状态转换
        """
        with self._lock:
            if self._state == new_state:
                return

            valid_transitions = {
                AEState.OFF: {AEState.STARTING, AEState.RECOVERING},
                AEState.STARTING: {AEState.RUNNING, AEState.CRASHED, AEState.CLOSING, AEState.OFF},
                AEState.RUNNING: {AEState.CLOSING, AEState.CRASHED, AEState.OFF, AEState.DEGRADED if False else AEState.RUNNING},
                AEState.CLOSING: {AEState.OFF, AEState.CRASHED},
                AEState.CRASHED: {AEState.RECOVERING, AEState.OFF},
                AEState.RECOVERING: {AEState.STARTING, AEState.OFF, AEState.CRASHED},
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
        """根据实际进程状态同步内部状态机。"""
        running = self._is_running_fast()
        callbacks_to_invoke: List[Tuple[AEState, AEState]] = []
        with self._lock:
            if not running:
                if self._state in (AEState.STARTING, AEState.RUNNING, AEState.RECOVERING):
                    self._crash_count += 1
                    old_state = self._state
                    self._state = AEState.CRASHED
                    callbacks_to_invoke.append((old_state, AEState.CRASHED))
                elif self._state == AEState.CLOSING:
                    old_state = self._state
                    self._state = AEState.OFF
                    callbacks_to_invoke.append((old_state, AEState.OFF))
                else:
                    self._state = AEState.OFF
            else:
                if self._state in (AEState.OFF, AEState.CRASHED):
                    self._state = AEState.RUNNING
                elif self._state == AEState.STARTING:
                    old_state = self._state
                    self._state = AEState.RUNNING
                    callbacks_to_invoke.append((old_state, AEState.RUNNING))

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
    def _find_ae_executable() -> Optional[Path]:
        for p in DEFAULT_SEARCH_PATHS:
            if p.exists():
                return p.resolve()
        for root in [Path(r"C:\Program Files\Adobe"), Path(r"D:\Program Files\Adobe")]:
            if not root.exists():
                continue
            for sub in root.iterdir():
                if sub.is_dir() and "After Effects" in sub.name:
                    exe = sub / "Support Files" / "AfterFX.exe"
                    if exe.exists():
                        return exe.resolve()
        return None

    @staticmethod
    def _find_listener_script() -> Optional[Path]:
        candidate = DEFAULT_LISTENER
        if candidate.exists():
            return candidate.resolve()
        cwd_candidate = Path.cwd() / "ae_mcp_auto_listener.jsx"
        if cwd_candidate.exists():
            return cwd_candidate.resolve()
        return None

    # --------------- Process queries ---------------

    def _is_running_fast(self) -> bool:
        """快速检查进程是否存在（不带详细信息）。

        优化策略：
        1. 优先使用缓存的 PID 快速检查
        2. 后端自带 PID 缓存（5秒 TTL）
        3. Fallback: psutil 全量扫描或 tasklist
        """
        # 快速路径：检查缓存的 PID
        with self._lock:
            cached_pid = self._ae_pid
        if cached_pid is not None:
            # 使用后端或 psutil 快速检查已知 PID
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

        # 优先使用后端
        if self._backend is not None:
            return self._backend.is_running(AE_PROCESS_NAME)
        # Fallback: 直接调用 psutil
        try:
            import psutil

            for proc in psutil.process_iter(["name"]):
                try:
                    if (
                        proc.info["name"]
                        and proc.info["name"].lower()
                        == AE_PROCESS_NAME.lower()
                    ):
                        # 更新缓存
                        with self._lock:
                            self._ae_pid = proc.pid
                        return True
                except Exception:
                    continue
            return False
        except ImportError:
            return self._is_running_via_tasklist()

    def is_ae_running(self) -> bool:
        """Return True if AfterFX.exe is currently running."""
        running = self._is_running_fast()
        with self._lock:
            if running and self._state == AEState.OFF:
                self._state = AEState.RUNNING
            elif not running and self._state not in (
                AEState.OFF,
                AEState.CRASHED,
                AEState.CLOSING,
            ):
                pass
        if not running:
            self._sync_state_from_process()
        return running

    @staticmethod
    def _is_running_via_tasklist() -> bool:
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {AE_PROCESS_NAME}"],
                capture_output=True,
                text=True,
                check=False,
            )
            return AE_PROCESS_NAME.lower() in result.stdout.lower()
        except Exception:
            return False

    def _get_ae_process(self):
        """获取 AE 进程对象。"""
        # 优先使用后端
        if self._backend is not None:
            return self._backend.find_process(AE_PROCESS_NAME)
        # Fallback: 直接调用 psutil
        try:
            import psutil

            for proc in psutil.process_iter(["name", "pid"]):
                try:
                    if (
                        proc.info["name"]
                        and proc.info["name"].lower()
                        == AE_PROCESS_NAME.lower()
                    ):
                        return proc
                except Exception:
                    continue
        except ImportError:
            pass
        return None

    def get_ae_pid(self) -> Optional[int]:
        """获取 AE 进程 PID。"""
        proc = self._get_ae_process()
        if proc:
            with self._lock:
                self._ae_pid = proc.pid
            return proc.pid
        with self._lock:
            self._ae_pid = None
        return None

    def get_ae_status(self) -> Dict[str, Any]:
        """Return a dict with current AE process status."""
        running = self.is_ae_running()
        with self._lock:
            state_val = self._state.value
            started_by_manager = self._started_by_manager
            crash_count = self._crash_count
            recovery_count = self._recovery_count
            launch_mode_val = self._launch_mode.value
        status = {
            "running": running,
            "state": state_val,
            "ae_exe_path": str(self.ae_exe_path) if self.ae_exe_path else None,
            "listener_script_path": str(self.listener_script_path)
            if self.listener_script_path
            else None,
            "started_by_manager": started_by_manager,
            "crash_count": crash_count,
            "recovery_count": recovery_count,
            "launch_mode": launch_mode_val,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        if running:
            pid = self.get_ae_pid()
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

    def get_ae_metrics(self) -> AEMetrics:
        """获取 AE 进程指标。

        Returns:
            AEMetrics 对象，包含 CPU、内存、句柄数、运行时长等指标
        """
        metrics = AEMetrics()

        try:
            import psutil

            proc = self._get_ae_process()
            if proc is None:
                with self._lock:
                    self._metrics_history.append(metrics)
                return metrics

            metrics.pid = proc.pid
            with self._lock:
                self._ae_pid = proc.pid

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
            pid = self.get_ae_pid()
            metrics.pid = pid

        with self._lock:
            self._metrics_history.append(metrics)
        return metrics

    def detect_memory_leak(self) -> Tuple[bool, Dict[str, Any]]:
        """检测内存泄漏趋势。

        通过对比历史内存使用趋势判断是否存在内存泄漏。

        Returns:
            (是否泄漏, 详细信息字典)
        """
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

    def is_ae_healthy(self) -> HealthReport:
        """检查 AE 健康状态。

        检查项：
        - 进程是否存在
        - 主窗口是否响应
        - 内存使用是否异常
        - CPU 是否持续过高

        Returns:
            HealthReport 健康报告对象
        """
        report = HealthReport()
        details: Dict[str, Any] = {}
        recommendations: List[str] = []

        if not self.is_ae_running():
            report.status = HealthStatus.CRASHED
            report.details = {"process": "not_running"}
            report.recommendations = ["启动 AE 进程"]
            self._health_history.append(report)
            return report

        pid = self.get_ae_pid()
        details["pid"] = pid

        metrics = self.get_ae_metrics()
        details["metrics"] = metrics.to_dict()

        window_hwnd = None
        window_responsive = True
        if _Win32API.is_available() and pid:
            window_hwnd = _Win32API.find_ae_main_window(pid=pid)
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

        save_dialog_found = False
        if _Win32API.is_available() and pid:
            save_dlg = _Win32API.find_save_dialog(owner_pid=pid)
            if save_dlg:
                save_dialog_found = True
                details["save_dialog_found"] = True

        health_score = 100

        if not window_responsive:
            health_score -= 40
            recommendations.append("主窗口无响应，可能需要重启 AE")

        if is_leaking:
            health_score -= 25
            recommendations.append("检测到内存泄漏趋势，建议重启 AE")

        if metrics.memory_mb > 16000:
            health_score -= 20
            recommendations.append("内存使用超过 16GB，建议重启释放内存")

        if metrics.cpu_percent > 95 and metrics.uptime_seconds > 60:
            health_score -= 15
            recommendations.append("CPU 持续高负载，检查是否有长时间渲染任务")

        if save_dialog_found:
            health_score -= 10
            recommendations.append("检测到保存对话框，关闭过程可能被阻塞")

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
        """自动恢复崩溃或卡死的 AE 进程。

        Returns:
            是否成功触发恢复流程
        """
        health = self.is_ae_healthy()

        if health.status == HealthStatus.HEALTHY:
            return True

        logger.warning(f"AE 健康状态: {health.status.value}")
        for rec in health.recommendations:
            logger.warning(f"建议: {rec}")

        if health.status in (HealthStatus.UNHEALTHY, HealthStatus.CRASHED):
            logger.info("触发自动恢复流程...")
            with self._lock:
                self._recovery_count += 1

            try:
                self._transition_to(AEState.RECOVERING)
            except InvalidStateTransitionError:
                with self._lock:
                    self._state = AEState.RECOVERING

            try:
                self._close_ae_gracefully_or_force()
            except Exception:
                pass

            time.sleep(2)
            self.clear_crash_state()
            time.sleep(1)

            return self.start_ae_with_listener()

        return False

    # --------------- Crash state cleanup ---------------

    def clear_crash_state(self) -> Dict[str, Any]:
        """全面清理 AE 崩溃状态。

        清理内容包括：
        1. 注册表 AppState 崩溃标记（多版本）
        2. Session 跟踪相关注册表项
        3. SCRPriorState.json
        4. CrashRpt 崩溃报告
        5. 崩溃恢复文件
        6. 临时渲染缓存

        Returns:
            清理结果字典
        """
        result = {
            "registry_keys_cleared": [],
            "files_removed": [],
            "errors": [],
        }

        ae_versions = ["25.0", "25.3", "24.0", "24.3", "23.0", "23.3"]

        for version_key in ae_versions:
            reg_path = rf"Software\Adobe\After Effects\{version_key}"
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

        crashrpt_paths = [
            r"Software\Adobe\CrashRpt",
            r"Software\Adobe\After Effects\CrashRpt",
        ]
        for cr_path in crashrpt_paths:
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, cr_path)
                result["registry_keys_cleared"].append(cr_path)
            except FileNotFoundError:
                pass
            except Exception:
                pass

        ae_roaming = Path(
            os.path.join(
                str(Path.home()), "AppData", "Roaming", "Adobe", "After Effects"
            )
        )
        if ae_roaming.exists():
            for version_dir in ae_roaming.iterdir():
                if not version_dir.is_dir():
                    continue

                files_to_remove = [
                    "SCRPriorState.json",
                    "AEActiveDetails.json",
                ]
                for fname in files_to_remove:
                    fpath = version_dir / fname
                    if fpath.exists():
                        try:
                            fpath.unlink()
                            result["files_removed"].append(str(fpath))
                        except Exception as e:
                            result["errors"].append(f"{fpath}: {e}")

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

        ae_local = Path(
            os.path.join(
                str(Path.home()), "AppData", "Local", "Adobe", "After Effects"
            )
        )
        if ae_local.exists():
            for version_dir in ae_local.iterdir():
                if not version_dir.is_dir():
                    continue
                temp_dir = version_dir / "Temp"
                if temp_dir.exists() and temp_dir.is_dir():
                    try:
                        for f in temp_dir.glob("*.tmp"):
                            if f.is_file():
                                f.unlink()
                                result["files_removed"].append(str(f))
                    except Exception:
                        pass

        return result

    def _clear_crash_state(self) -> None:
        """内部版本的崩溃状态清理，兼容旧代码。"""
        try:
            self.clear_crash_state()
        except Exception:
            pass

    # --------------- Startup configuration ---------------

    def set_launch_mode(self, mode: LaunchMode) -> None:
        """设置启动模式。

        Args:
            mode: 启动模式枚举值
        """
        with self._lock:
            self._launch_mode = mode

    def set_workspace(self, workspace_path: Optional[str | Path]) -> None:
        """设置启动时加载的工作区文件。

        Args:
            workspace_path: 工作区文件路径 (.aep)，None 清除设置
        """
        if workspace_path is None:
            with self._lock:
                self._workspace_path = None
            return
        p = Path(workspace_path)
        if p.suffix.lower() not in (".aep",):
            raise ValueError(f"工作区文件必须是 .aep 格式: {workspace_path}")
        with self._lock:
            self._workspace_path = p.resolve()

    def set_extra_args(self, args: List[str]) -> None:
        """设置额外启动参数。

        Args:
            args: 额外命令行参数列表
        """
        with self._lock:
            self._extra_args = list(args)

    def _build_launch_args(self) -> List[str]:
        """构建启动参数列表。

        Returns:
            完整的命令行参数列表
        """
        if not self.ae_exe_path:
            raise AEProcessError("AE 可执行文件路径未设置")

        with self._lock:
            launch_mode = self._launch_mode
            workspace_path = self._workspace_path
            extra_args = list(self._extra_args)

        args: List[str] = [str(self.ae_exe_path)]

        if launch_mode == LaunchMode.SAFE_MODE:
            args.append("-safe")

        if launch_mode == LaunchMode.HEADLESS:
            args.append("-noui")

        if workspace_path and workspace_path.exists():
            args.append(str(workspace_path))

        args.extend(extra_args)

        return args

    # --------------- Lifecycle actions ---------------

    def start_ae_with_listener(
        self,
        mode: Optional[LaunchMode] = None,
        workspace: Optional[str | Path] = None,
    ) -> bool:
        """Launch AE and set up Bridge Listener (non-blocking).

        AE 2025 不支持 -r 命令行参数，改用:
        1. 清理 Startup 目录中的第三方脚本（防止崩溃）
        2. 清除崩溃状态（避免 Crash Repair 对话框）
        3. 根据配置启动 AE
        4. 等待 AE 就绪

        Args:
            mode: 启动模式，None 使用当前设置
            workspace: 工作区文件路径，None 使用当前设置

        Returns:
            是否成功启动
        """
        if self.is_ae_running():
            logger.info("After Effects is already running.")
            try:
                self._transition_to(AEState.RUNNING)
            except InvalidStateTransitionError:
                pass
            return True

        if not self.ae_exe_path:
            logger.error("After Effects executable not found.")
            return False

        if mode is not None:
            with self._lock:
                self._launch_mode = mode
        if workspace is not None:
            self.set_workspace(workspace)

        try:
            self._transition_to(AEState.STARTING)
        except InvalidStateTransitionError:
            with self._lock:
                self._state = AEState.STARTING

        self._clean_startup_scripts()
        # DEPRECATED: 自研 bridge loader 已弃用，AE MCP 已转向开源基线（mcp-bridge-auto.jsx）
        # self._deploy_bridge_loader()
        self.clear_crash_state()

        try:
            launch_args = self._build_launch_args()
            with self._lock:
                launch_mode_val = self._launch_mode.value
                workspace_path = self._workspace_path
            logger.info(f"Starting AE ({launch_mode_val}): {self.ae_exe_path}")
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
            logger.info("After Effects launched (waiting for startup)...")

            detected = False
            for i in range(self.start_timeout):
                time.sleep(1)
                if self.is_ae_running():
                    pid = self.get_ae_pid()
                    with self._lock:
                        self._ae_pid = pid
                    logger.info(f"AE process detected ({i+1}s)")
                    detected = True
                    break

            if not detected:
                logger.error(f"AE did not start within {self.start_timeout}s")
                try:
                    self._transition_to(AEState.CRASHED)
                except InvalidStateTransitionError:
                    with self._lock:
                        self._state = AEState.CRASHED
                return False

            logger.info("Waiting for AE to fully initialize (10s)...")
            time.sleep(10)

            try:
                self._transition_to(AEState.RUNNING)
            except InvalidStateTransitionError:
                with self._lock:
                    self._state = AEState.RUNNING

            return True

        except Exception as exc:
            logger.error(f"Failed to start AE: {exc}")
            try:
                self._transition_to(AEState.CRASHED)
            except InvalidStateTransitionError:
                with self._lock:
                    self._state = AEState.CRASHED
            return False

    def start_ae_async(
        self,
        mode: Optional[LaunchMode] = None,
        workspace: Optional[str | Path] = None,
    ) -> "Future[bool]":
        """异步启动 AE（非阻塞）。

        将 AE 进程启动和 listener 部署放入独立线程，
        主线程通过返回的 Future 获取结果。

        Args:
            mode: 启动模式
            workspace: 工作区文件路径

        Returns:
            Future[bool] - 启动是否成功
        """
        future: Future[bool] = Future()

        def _worker() -> None:
            try:
                result = self.start_ae_with_listener(mode=mode, workspace=workspace)
                future.set_result(result)
            except Exception as exc:
                logger.error(f"Async AE start failed: {exc}")
                future.set_exception(exc)

        thread = threading.Thread(
            target=_worker,
            name="ae-async-start",
            daemon=True,
        )
        thread.start()
        logger.info("AE async start initiated (thread: ae-async-start)")
        return future

    def close_ae(self, timeout: Optional[int] = None) -> bool:
        """优雅关闭 AE，超时后降级为强制关闭。

        关闭策略：
        1. 检测保存对话框（如果有则记录但不自动点击）
        2. 发送 WM_CLOSE 消息（模拟点击关闭按钮）
        3. 等待优雅退出
        4. 超时后强制 kill
        5. 强制关闭后清理崩溃状态

        Args:
            timeout: 优雅关闭超时时间（秒），None 使用默认值

        Returns:
            是否成功关闭
        """
        if not self.is_ae_running():
            logger.info("AE is not running.")
            try:
                self._transition_to(AEState.OFF)
            except InvalidStateTransitionError:
                with self._lock:
                    self._state = AEState.OFF
            return True

        wait_timeout = timeout if timeout is not None else self.close_timeout

        try:
            self._transition_to(AEState.CLOSING)
        except InvalidStateTransitionError:
            with self._lock:
                self._state = AEState.CLOSING

        pid = self.get_ae_pid()

        if _Win32API.is_available() and pid:
            save_dlg = _Win32API.find_save_dialog(owner_pid=pid)
            if save_dlg:
                logger.warning("检测到保存对话框，关闭可能被阻塞")

        return self._close_ae_gracefully_or_force(wait_timeout)

    def _close_ae_gracefully_or_force(self, timeout: Optional[int] = None) -> bool:
        """内部方法：优雅关闭或强制关闭。"""
        wait_timeout = timeout if timeout is not None else self.close_timeout
        closed_via_wm = False

        if _Win32API.is_available():
            pid = self.get_ae_pid()
            hwnd = _Win32API.find_ae_main_window(pid=pid)
            if hwnd:
                logger.info(f"Found AE window, sending WM_CLOSE...")
                if _Win32API.send_wm_close(hwnd):
                    closed_via_wm = True
                    with self._lock:
                        self._last_close_method = CloseMethod.WM_CLOSE

                    for i in range(wait_timeout):
                        if not self.is_ae_running():
                            logger.info(f"AE exited gracefully via WM_CLOSE ({i+1}s)")
                            try:
                                self._transition_to(AEState.OFF)
                            except InvalidStateTransitionError:
                                with self._lock:
                                    self._state = AEState.OFF
                            with self._lock:
                                self._started_by_manager = False
                                self._ae_pid = None
                            return True
                        time.sleep(1)

                    logger.warning("AE did not exit after WM_CLOSE, trying force-kill...")
                else:
                    logger.warning("Failed to send WM_CLOSE, trying force-kill...")
            else:
                logger.warning("Could not find AE main window, trying force-kill...")
        else:
            logger.info("Win32 API unavailable, using force-kill...")

        return self._force_kill_ae()

    def _force_kill_ae(self) -> bool:
        """强制关闭 AE 进程。"""
        with self._lock:
            self._last_close_method = CloseMethod.FORCE_KILL

        # 优先使用后端
        if self._backend is not None:
            proc_info = self._backend.find_process(AE_PROCESS_NAME)
            if proc_info:
                logger.info(f"Force-terminating PID {proc_info.pid} via backend")
                self._backend.kill(proc_info.pid, force=True)
            else:
                logger.debug("No AE process found to kill")
        else:
            # Fallback: 直接调用 psutil
            try:
                import psutil

                for proc in psutil.process_iter(["name"]):
                    try:
                        if (
                            proc.info["name"]
                            and proc.info["name"].lower()
                            == AE_PROCESS_NAME.lower()
                        ):
                            logger.info(f"Force-terminating PID {proc.pid}")
                            proc.kill()
                    except Exception:
                        continue
            except ImportError:
                with self._lock:
                    self._last_close_method = CloseMethod.TASKKILL
                subprocess.run(
                    ["taskkill", "/F", "/IM", AE_PROCESS_NAME],
                    capture_output=True,
                    check=False,
                )

        for _ in range(self.force_kill_timeout):
            if not self.is_ae_running():
                break
            time.sleep(1)

        time.sleep(2)
        self.clear_crash_state()

        with self._lock:
            self._started_by_manager = False
            self._ae_pid = None
        try:
            self._transition_to(AEState.OFF)
        except InvalidStateTransitionError:
            with self._lock:
                self._state = AEState.OFF

        logger.info("AE process terminated.")
        return True

    def _kill_ae(self) -> None:
        """兼容旧代码的内部关闭方法。"""
        self._close_ae_gracefully_or_force()

    def restart_ae(self) -> bool:
        """重启 AE 进程。

        Returns:
            是否成功重启
        """
        logger.info("Restarting After Effects...")

        if self.is_ae_running():
            self.close_ae()
            for _ in range(30):
                if not self.is_ae_running():
                    break
                time.sleep(1)
            else:
                logger.error("AE did not terminate in time.")
                return False
            time.sleep(2)
            self.clear_crash_state()

        return self.start_ae_with_listener()

    # --------------- Startup script management ---------------

    def _startup_listener_exists(self) -> bool:
        """检查 AE Startup 文件夹是否已安装 Listener 脚本"""
        ae_scripts_startup = Path(
            r"C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\Scripts\Startup"
        )
        if ae_scripts_startup.exists():
            listener_in_startup = (
                ae_scripts_startup / "2_mcp_bridge_listener.jsx"
            )
            return listener_in_startup.exists()
        return False

    def _load_listener_via_bridge(self):
        """通过 Bridge 命令文件触发 Listener 加载"""
        try:
            bridge_dir = Path(
                os.path.join(
                    str(Path.home()), "Documents", "ae-mcp-bridge"
                )
            )
            bridge_dir.mkdir(parents=True, exist_ok=True)

            command_file = bridge_dir / "command.json"
            command = {
                "command": "executeAtomScript",
                "args": {
                    "script": (
                        'var f = new File("{}"); '
                        "if (f.exists) {{ $.evalFile(f); }}"
                    ).format(
                        str(self.listener_script_path).replace("\\", "/")
                    )
                },
                "timestamp": datetime.now().isoformat(),
                "signature": "",
            }

            with open(command_file, "w", encoding="utf-8") as f:
                json.dump(command, f, ensure_ascii=False)

            logger.info(f"Bridge command written: {command_file}")
            logger.info("Waiting for Bridge Listener to load...")
            time.sleep(3)

        except Exception as e:
            logger.warning(f"Could not load listener via Bridge: {e}")
            logger.warning(
                "You may need to manually run the listener script in AE:"
            )
            logger.warning(
                f"       File > Scripts > Run Script File > {self.listener_script_path}"
            )

    def _clean_startup_scripts(self) -> None:
        """Remove third-party scripts from AE Startup folders.

        AE 2025 crashes if ANY .jsx file exists in Startup folders,
        even if the file only contains comments. Only keep the original
        AE files (About the Startup folder.txt, commandLineRenderer.jsx).
        """
        startup_dirs = [
            Path(
                r"C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\Scripts\Startup"
            ),
            Path(
                r"C:\Program Files (x86)\Adobe\Adobe After Effects 2025\Support Files\Scripts\Startup"
            ),
        ]
        user_appdata = Path(
            os.path.join(
                str(Path.home()),
                "AppData",
                "Roaming",
                "Adobe",
                "After Effects",
            )
        )
        if user_appdata.exists():
            for ver_dir in user_appdata.iterdir():
                if ver_dir.is_dir():
                    startup_dirs.append(ver_dir / "Scripts" / "Startup")

        safe_files = {
            "about the startup folder.txt",
            "commandlinerenderer.jsx",
            "2_mcp_bridge_loader.jsx",  # Our MCP Bridge auto-loader (crash cause was force-kill, not startup scripts)
        }

        for startup_dir in startup_dirs:
            if not startup_dir.exists():
                continue
            for item in startup_dir.iterdir():
                if item.is_file() and item.name.lower() not in safe_files:
                    if item.suffix.lower() in (".jsx", ".js"):
                        try:
                            item.unlink()
                            logger.info(f"Removed Startup script: {item.name}")
                        except PermissionError:
                            try:
                                import base64

                                file_path_b64 = base64.b64encode(
                                    str(item).encode("utf-16-le")
                                ).decode("ascii")

                                ps_inner = f'''
$filePathB64 = [string]$args[0]
$filePath = [System.Text.Encoding]::Unicode.GetString([System.Convert]::FromBase64String($filePathB64))
$ErrorActionPreference = "Stop"
if (Test-Path $filePath) {{
    Remove-Item -Path $filePath -Force
    exit 0
}} else {{
    exit 1
}}
'''
                                inner_bytes = ps_inner.encode("utf-16-le")
                                inner_b64 = base64.b64encode(inner_bytes).decode("ascii")

                                ps_outer = f'''
$argList = @('-EncodedCommand', '{inner_b64}', '-Args', '{file_path_b64}')
Start-Process powershell -Verb RunAs -Wait -ArgumentList $argList
'''
                                outer_bytes = ps_outer.encode("utf-16-le")
                                outer_b64 = base64.b64encode(outer_bytes).decode("ascii")

                                subprocess.run(
                                    ["powershell", "-EncodedCommand", outer_b64],
                                    timeout=15,
                                    capture_output=True,
                                    text=True,
                                )
                                if not item.exists():
                                    logger.info(
                                        f"Removed (elevated): {item.name}"
                                    )
                                else:
                                    logger.warning(
                                        f"Could not remove: {item.name}"
                                    )
                            except Exception:
                                logger.warning(
                                    f"Could not remove: {item.name}"
                                )
                        except Exception as e:
                            logger.warning(
                                f"Could not remove {item.name}: {e}"
                            )

    def _deploy_bridge_loader(self) -> None:
        """DEPRECATED - Deploy MCP Bridge loader to user-level Startup directory.

        .. deprecated::
            自研 .ae-mcp-bridge 协议已弃用，AE MCP 已转向开源基线。
            此方法不再被调用，保留仅供参考。

        This ensures the Bridge listener auto-starts when AE launches,
        without requiring admin privileges (user-level Startup dir).
        """
        loader_src = Path(__file__).parent.parent / ".ae-mcp-bridge" / "2_mcp_bridge_loader.jsx"
        if not loader_src.exists():
            return

        user_startup = Path(
            os.path.join(
                str(Path.home()),
                "AppData",
                "Roaming",
                "Adobe",
                "After Effects",
                "25.3",
                "Scripts",
                "Startup",
            )
        )
        try:
            user_startup.mkdir(parents=True, exist_ok=True)
            loader_dst = user_startup / "2_mcp_bridge_loader.jsx"
            import shutil
            shutil.copy2(str(loader_src), str(loader_dst))
            logger.info(f"Deployed bridge loader to Startup")
        except Exception as e:
            logger.warning(f"Could not deploy bridge loader: {e}")

    # --------------- Deprecated / backward compat ---------------

    def _quit_via_wm_close(self) -> bool:
        """兼容旧代码的 WM_CLOSE 方法。

        Returns:
            是否成功发送 WM_CLOSE 消息
        """
        if not _Win32API.is_available():
            return False

        pid = self.get_ae_pid()
        hwnd = _Win32API.find_ae_main_window(pid=pid)
        if hwnd:
            return _Win32API.send_wm_close(hwnd)
        return False

    def _quit_ae_gracefully(self) -> None:
        """DEPRECATED: Use close_ae() instead.

        Kept for backward compatibility with older code.
        """
        if self._quit_via_wm_close():
            return
        bridge_dir = Path(
            os.path.join(str(Path.home()), "Documents", "ae-mcp-bridge")
        )
        bridge_dir.mkdir(parents=True, exist_ok=True)

        command_file = bridge_dir / "command.json"
        command = {
            "command": "run_script",
            "args": {"script": "try { app.quit(); } catch(e) {}"},
            "timestamp": datetime.now().isoformat(),
        }
        with open(command_file, "w", encoding="utf-8") as f:
            json.dump(command, f, ensure_ascii=False)
        logger.info("Sent quit command via Bridge (fallback)")

    # --------------- Monitoring loop ---------------

    def monitor(
        self,
        interval_sec: int = 5,
        auto_start: bool = True,
        auto_recover: bool = True,
    ) -> None:
        """阻塞式 AE 健康监控循环。

        Args:
            interval_sec: 检查间隔秒数
            auto_start: 进程退出时是否自动启动
            auto_recover: 检测到不健康时是否自动恢复
        """
        logger.info("Starting AE monitor (Ctrl+C to stop)...")
        try:
            while True:
                status = self.get_ae_status()
                health = self.is_ae_healthy()

                if not status["running"] and auto_start:
                    logger.warning("AE not running; auto-starting...")
                    self.start_ae_with_listener()
                elif status["running"] and auto_recover and health.status in (
                    HealthStatus.UNHEALTHY,
                    HealthStatus.CRASHED,
                ):
                    logger.warning(f"AE unhealthy ({health.status}); auto-recovering...")
                    self.auto_recover()
                else:
                    state_info = f"{status['state']}"
                    health_info = f"health={health.status.value}"
                    if health.status != HealthStatus.HEALTHY:
                        logger.info(
                            f"AE status: {state_info}, {health_info}"
                        )
                    else:
                        logger.info(f"AE status: {state_info}")

                time.sleep(interval_sec)
        except KeyboardInterrupt:
            logger.info("Monitor stopped by user.")

    # --------------- Additional utilities ---------------

    def get_health_history(self) -> List[Dict[str, Any]]:
        """获取健康检查历史记录。"""
        with self._lock:
            return [r.to_dict() for r in self._health_history]

    def get_last_close_method(self) -> Optional[str]:
        """获取上一次关闭方式。"""
        with self._lock:
            return self._last_close_method.value if self._last_close_method else None

    def reset_stats(self) -> None:
        """重置统计数据（崩溃次数、恢复次数等）。"""
        with self._lock:
            self._crash_count = 0
            self._recovery_count = 0
            self._metrics_history.clear()
            self._health_history.clear()


# ---------------------------------------------------------------------------
# Optional REST API
# ---------------------------------------------------------------------------
class _AEStatusHandler(BaseHTTPRequestHandler):
    manager: Optional[AEProcessManager] = None

    def log_message(self, format, *args):
        pass

    def _send_json(self, data: Dict[str, Any], code: int = 200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2, default=str).encode("utf-8"))

    def do_GET(self):
        if self.manager is None:
            self._send_json({"error": "Manager not initialized"}, 500)
            return

        if self.path in ("/", "/status"):
            self._send_json(self.manager.get_ae_status())
        elif self.path == "/health":
            report = self.manager.is_ae_healthy()
            self._send_json(report.to_dict())
        elif self.path == "/metrics":
            metrics = self.manager.get_ae_metrics()
            leak, leak_info = self.manager.detect_memory_leak()
            result = metrics.to_dict()
            result["memory_leak"] = {"detected": leak, "details": leak_info}
            self._send_json(result)
        elif self.path == "/start":
            ok = self.manager.start_ae_with_listener()
            self._send_json({"started": ok})
        elif self.path == "/stop":
            ok = self.manager.close_ae()
            self._send_json({"stopped": ok})
        elif self.path == "/restart":
            ok = self.manager.restart_ae()
            self._send_json({"restarted": ok})
        elif self.path == "/clear-crash":
            result = self.manager.clear_crash_state()
            self._send_json({"cleared": True, "details": result})
        elif self.path == "/recover":
            ok = self.manager.auto_recover()
            self._send_json({"recovered": ok})
        else:
            self._send_json({"error": "Not found"}, 404)


def run_api_server(manager: AEProcessManager, host: str, port: int):
    if not _HAS_HTTP:
        logger.error("HTTP server module not available in this Python build.")
        sys.exit(1)

    _AEStatusHandler.manager = manager
    server = HTTPServer((host, port), _AEStatusHandler)
    logger.info(f"API server listening on http://{host}:{port}")
    logger.info(
        "Endpoints: GET /status, /health, /metrics, /start, /stop, /restart, /clear-crash, /recover"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("API server stopped.")


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="After Effects Process Manager")
    parser.add_argument(
        "--ae-exe",
        dest="ae_exe",
        default=None,
        help="Path to AfterFX.exe",
    )
    parser.add_argument(
        "--listener",
        dest="listener",
        default=None,
        help="Path to ae_mcp_auto_listener.jsx",
    )
    parser.add_argument(
        "--monitor",
        action="store_true",
        help="Monitor AE and auto-restart if needed",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="Monitor interval in seconds (default: 5)",
    )
    parser.add_argument(
        "--api",
        action="store_true",
        help="Run REST API server",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="API bind address (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8123,
        help="API port (default: 8123)",
    )
    parser.add_argument(
        "--safe-mode",
        action="store_true",
        help="Start AE in safe mode",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Start AE in headless (no UI) mode",
    )
    parser.add_argument(
        "--workspace",
        default=None,
        help="Path to .aep workspace file to open on startup",
    )
    parser.add_argument(
        "--health-check",
        action="store_true",
        help="Run a single health check and exit",
    )
    parser.add_argument(
        "--clear-crash",
        action="store_true",
        help="Clear AE crash state and exit",
    )
    parser.add_argument(
        "--close",
        action="store_true",
        help="Close AE gracefully and exit",
    )
    args = parser.parse_args()

    try:
        mgr = AEProcessManager(
            ae_exe_path=args.ae_exe,
            listener_script_path=args.listener,
        )
    except FileNotFoundError as exc:
        logger.error(f"{exc}")
        sys.exit(1)

    if args.safe_mode:
        mgr.set_launch_mode(LaunchMode.SAFE_MODE)
    elif args.headless:
        mgr.set_launch_mode(LaunchMode.HEADLESS)

    if args.workspace:
        mgr.set_workspace(args.workspace)

    logger.info("=" * 50)
    logger.info("AE Process Manager (Production)")
    logger.info("=" * 50)
    logger.info(f"AE exe       : {mgr.ae_exe_path}")
    logger.info(f"Listener     : {mgr.listener_script_path}")
    logger.info(f"State        : {mgr.state.value}")
    logger.info(f"Launch mode  : {mgr._launch_mode.value}")
    logger.info(f"Crash count  : {mgr.crash_count}")
    logger.info("=" * 50)

    if args.clear_crash:
        logger.info("Clearing crash state...")
        result = mgr.clear_crash_state()
        logger.info(
            f"Cleared {len(result['registry_keys_cleared'])} registry keys, "
            f"{len(result['files_removed'])} files"
        )
        return

    if args.close:
        logger.info("Closing AE...")
        ok = mgr.close_ae()
        logger.info(f"Closed: {ok}")
        return

    if args.health_check:
        logger.info("Running health check...")
        report = mgr.is_ae_healthy()
        logger.info(f"Health status: {report.status.value}")
        for rec in report.recommendations:
            logger.info(f" - {rec}")
        print(json.dumps(report.to_dict(), indent=2, default=str))
        return

    if args.api:
        run_api_server(mgr, args.host, args.port)
    elif args.monitor:
        mgr.monitor(interval_sec=args.interval, auto_start=True, auto_recover=True)
    else:
        if not mgr.is_ae_running():
            mgr.start_ae_with_listener()
        else:
            logger.info("AE is already running.")
        print(json.dumps(mgr.get_ae_status(), indent=2, default=str))


if __name__ == "__main__":
    main()
