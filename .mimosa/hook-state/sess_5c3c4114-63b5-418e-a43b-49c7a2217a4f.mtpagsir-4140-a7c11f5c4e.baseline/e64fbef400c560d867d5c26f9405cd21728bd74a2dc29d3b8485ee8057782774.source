"""
进程操作后端抽象层
==================

提供统一的进程管理接口，支持多种后端实现：
- PsutilBackend: 优先使用 psutil 库（功能最全面）
- Win32APIBackend: 使用 ctypes + Win32 API（无需额外依赖）
- TasklistBackend: 使用 tasklist 命令行（最终 fallback）

自动检测可用后端，按优先级降级：psutil → win32api → tasklist

Usage:
    from ae.process_backends import auto_detect_backend

    backend = auto_detect_backend()
    if backend.is_running("AfterFX.exe"):
        metrics = backend.get_metrics(pid)
"""

from __future__ import annotations

import logging
import os
import subprocess
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ProcessInfo:
    """进程基本信息。"""

    pid: int
    name: str
    exe_path: str = ""
    create_time: float = 0.0
    is_running: bool = True


@dataclass
class ProcessMetrics:
    """进程性能指标。"""

    pid: int
    cpu_percent: float = 0.0
    memory_rss_mb: float = 0.0
    memory_vms_mb: float = 0.0
    num_threads: int = 0
    num_handles: int = 0
    create_time: float = 0.0
    status: str = "unknown"
    extra: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Abstract backend
# ---------------------------------------------------------------------------

class ProcessBackend(ABC):
    """进程操作抽象接口。

    所有后端实现必须提供以下能力：
    - 检查进程是否存在
    - 获取进程信息
    - 获取进程性能指标
    - 终止进程
    - 启动进程
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """后端名称（用于日志）。"""
        ...

    @abstractmethod
    def is_running(self, process_name: str) -> bool:
        """检查指定名称的进程是否存在。

        Args:
            process_name: 进程名（如 "AfterFX.exe"）

        Returns:
            进程是否存在
        """
        ...

    @abstractmethod
    def find_process(self, process_name: str) -> Optional[ProcessInfo]:
        """查找指定名称的进程。

        Args:
            process_name: 进程名

        Returns:
            ProcessInfo 或 None
        """
        ...

    @abstractmethod
    def get_metrics(self, pid: int) -> Optional[ProcessMetrics]:
        """获取进程性能指标。

        Args:
            pid: 进程 ID

        Returns:
            ProcessMetrics 或 None（进程不存在）
        """
        ...

    @abstractmethod
    def kill(self, pid: int, force: bool = False) -> bool:
        """终止进程。

        Args:
            pid: 进程 ID
            force: 是否强制终止

        Returns:
            是否成功终止
        """
        ...

    def launch(self, exe_path: str, args: Optional[List[str]] = None) -> subprocess.Popen:
        """启动进程。

        Args:
            exe_path: 可执行文件路径
            args: 命令行参数

        Returns:
            Popen 对象
        """
        cmd = [str(exe_path)] + (args or [])
        return subprocess.Popen(
            cmd,
            shell=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def pid_exists(self, pid: int) -> bool:
        """检查指定 PID 是否存在（默认实现：遍历查找）。"""
        # 子类可覆盖为更高效实现
        try:
            import psutil
            return psutil.pid_exists(pid)
        except ImportError:
            # Fallback: 尝试打开进程句柄
            try:
                import ctypes
                kernel32 = ctypes.windll.kernel32
                PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
                handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
                if handle:
                    kernel32.CloseHandle(handle)
                    return True
            except Exception:
                pass
            return False


# ---------------------------------------------------------------------------
# Psutil backend
# ---------------------------------------------------------------------------

class PsutilBackend(ProcessBackend):
    """基于 psutil 的进程后端（功能最全面）。"""

    def __init__(self) -> None:
        try:
            import psutil
            self._psutil = psutil
        except ImportError:
            raise RuntimeError("psutil not installed")
        # PID 缓存（优化进程查找）
        self._pid_cache: Dict[str, tuple[int, float]] = {}  # name -> (pid, timestamp)
        self._pid_cache_ttl = 5.0  # 5秒 TTL

    @property
    def name(self) -> str:
        return "psutil"

    def is_running(self, process_name: str) -> bool:
        # 快速路径：检查 PID 缓存
        now = time.time()
        cached = self._pid_cache.get(process_name.lower())
        if cached:
            pid, ts = cached
            if now - ts < self._pid_cache_ttl:
                if self._psutil.pid_exists(pid):
                    return True
                # PID 已失效，清除缓存
                del self._pid_cache[process_name.lower()]

        # 慢路径：全量扫描
        name_lower = process_name.lower()
        for proc in self._psutil.process_iter(["name"]):
            try:
                if proc.info["name"] and proc.info["name"].lower() == name_lower:
                    # 更新缓存
                    self._pid_cache[name_lower] = (proc.pid, now)
                    return True
            except (self._psutil.NoSuchProcess, self._psutil.AccessDenied):
                continue
        return False

    def find_process(self, process_name: str) -> Optional[ProcessInfo]:
        name_lower = process_name.lower()
        for proc in self._psutil.process_iter(["name", "pid"]):
            try:
                if proc.info["name"] and proc.info["name"].lower() == name_lower:
                    try:
                        exe = proc.exe()
                    except (self._psutil.AccessDenied, self._psutil.NoSuchProcess):
                        exe = ""
                    try:
                        create_time = proc.create_time()
                    except (self._psutil.AccessDenied, self._psutil.NoSuchProcess):
                        create_time = 0.0
                    return ProcessInfo(
                        pid=proc.pid,
                        name=proc.info["name"],
                        exe_path=exe,
                        create_time=create_time,
                        is_running=proc.is_running(),
                    )
            except (self._psutil.NoSuchProcess, self._psutil.AccessDenied):
                continue
        return None

    def get_metrics(self, pid: int) -> Optional[ProcessMetrics]:
        try:
            proc = self._psutil.Process(pid)
            with proc.oneshot():
                cpu = proc.cpu_percent(interval=0.1)
                mem = proc.memory_info()
                threads = proc.num_threads()
                status = proc.status()
                create_time = proc.create_time()

            # Windows 句柄数
            handles = 0
            try:
                handles = proc.num_handles()
            except (self._psutil.AccessDenied, AttributeError):
                pass

            return ProcessMetrics(
                pid=pid,
                cpu_percent=cpu,
                memory_rss_mb=round(mem.rss / (1024 * 1024), 1),
                memory_vms_mb=round(mem.vms / (1024 * 1024), 1),
                num_threads=threads,
                num_handles=handles,
                create_time=create_time,
                status=status,
            )
        except (self._psutil.NoSuchProcess, self._psutil.AccessDenied):
            return None

    def kill(self, pid: int, force: bool = False) -> bool:
        try:
            proc = self._psutil.Process(pid)
            if force:
                proc.kill()
            else:
                proc.terminate()
            proc.wait(timeout=10)
            return True
        except (self._psutil.NoSuchProcess, self._psutil.AccessDenied):
            return False
        except Exception:
            return False

    def pid_exists(self, pid: int) -> bool:
        return self._psutil.pid_exists(pid)


# ---------------------------------------------------------------------------
# Win32 API backend
# ---------------------------------------------------------------------------

class Win32APIBackend(ProcessBackend):
    """基于 Win32 API (ctypes) 的进程后端。"""

    def __init__(self) -> None:
        import ctypes
        self._ctypes = ctypes
        try:
            self._kernel32 = ctypes.windll.kernel32
            self._psapi = ctypes.windll.psapi
        except AttributeError:
            raise RuntimeError("Win32 API not available")

    @property
    def name(self) -> str:
        return "win32api"

    def is_running(self, process_name: str) -> bool:
        return self.find_process(process_name) is not None

    def find_process(self, process_name: str) -> Optional[ProcessInfo]:
        # 使用 tasklist 作为 Win32 后端的进程查找方式
        try:
            result = subprocess.run(
                ["tasklist", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, check=False, timeout=10,
            )
            name_lower = process_name.lower()
            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                parts = line.split(",")
                if len(parts) >= 2:
                    name = parts[0].strip('"')
                    pid = int(parts[1].strip('"'))
                    if name.lower() == name_lower:
                        return ProcessInfo(pid=pid, name=name)
        except Exception:
            pass
        return None

    def get_metrics(self, pid: int) -> Optional[ProcessMetrics]:
        # Win32 API 获取指标较复杂，使用简化版本
        if not self.pid_exists(pid):
            return None
        return ProcessMetrics(pid=pid, status="running")

    def kill(self, pid: int, force: bool = False) -> bool:
        try:
            if force:
                subprocess.run(
                    ["taskkill", "/F", "/PID", str(pid)],
                    capture_output=True, timeout=10,
                )
            else:
                subprocess.run(
                    ["taskkill", "/PID", str(pid)],
                    capture_output=True, timeout=10,
                )
            return not self.pid_exists(pid)
        except Exception:
            return False

    def pid_exists(self, pid: int) -> bool:
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = self._kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, pid
        )
        if handle:
            self._kernel32.CloseHandle(handle)
            return True
        return False


# ---------------------------------------------------------------------------
# Tasklist backend (ultimate fallback)
# ---------------------------------------------------------------------------

class TasklistBackend(ProcessBackend):
    """基于 tasklist 命令行的进程后端（最终 fallback）。"""

    @property
    def name(self) -> str:
        return "tasklist"

    def is_running(self, process_name: str) -> bool:
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {process_name}"],
                capture_output=True, text=True, check=False, timeout=10,
            )
            return process_name.lower() in result.stdout.lower()
        except Exception:
            return False

    def find_process(self, process_name: str) -> Optional[ProcessInfo]:
        try:
            result = subprocess.run(
                ["tasklist", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, check=False, timeout=10,
            )
            name_lower = process_name.lower()
            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                parts = line.split(",")
                if len(parts) >= 2:
                    name = parts[0].strip('"')
                    pid = int(parts[1].strip('"'))
                    if name.lower() == name_lower:
                        return ProcessInfo(pid=pid, name=name)
        except Exception:
            pass
        return None

    def get_metrics(self, pid: int) -> Optional[ProcessMetrics]:
        if not self.is_running(f"PID:{pid}"):
            return None
        return ProcessMetrics(pid=pid, status="running")

    def kill(self, pid: int, force: bool = False) -> bool:
        try:
            cmd = ["taskkill"]
            if force:
                cmd.append("/F")
            cmd.extend(["/PID", str(pid)])
            subprocess.run(cmd, capture_output=True, timeout=10)
            return True
        except Exception:
            return False


# ---------------------------------------------------------------------------
# Auto-detection
# ---------------------------------------------------------------------------

def auto_detect_backend() -> ProcessBackend:
    """自动检测最佳可用后端。

    优先级：psutil → win32api → tasklist

    Returns:
        可用的 ProcessBackend 实例
    """
    # 尝试 psutil
    try:
        backend = PsutilBackend()
        logger.info(f"Process backend: {backend.name}")
        return backend
    except (ImportError, RuntimeError):
        pass

    # 尝试 Win32 API
    try:
        backend = Win32APIBackend()
        logger.info(f"Process backend: {backend.name}")
        return backend
    except (ImportError, RuntimeError, AttributeError):
        pass

    # Fallback: tasklist
    backend = TasklistBackend()
    logger.info(f"Process backend: {backend.name} (fallback)")
    return backend
