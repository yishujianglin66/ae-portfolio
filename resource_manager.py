#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一资源管理器
=============

管理系统资源（CPU、内存、GPU、磁盘），提供资源监控与调度能力。

功能:
- 系统资源实时监控
- GPU 检测与状态查询
- 内存使用监控
- 磁盘空间检查
- 资源阈值告警
- 任务资源需求评估
"""

from __future__ import annotations

import os
import time
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

try:
    from logger import get_logger
    _logger = get_logger("resource-manager")
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    _logger = logging.getLogger("resource-manager")


# ============================================================================
# 资源数据类
# ============================================================================

@dataclass
class CPUInfo:
    """CPU 信息"""
    physical_cores: int = 0
    logical_cores: int = 0
    usage_percent: float = 0.0
    per_core_usage: List[float] = field(default_factory=list)
    freq_current: float = 0.0
    freq_min: float = 0.0
    freq_max: float = 0.0


@dataclass
class MemoryInfo:
    """内存信息"""
    total_gb: float = 0.0
    available_gb: float = 0.0
    used_gb: float = 0.0
    percent: float = 0.0
    swap_total_gb: float = 0.0
    swap_used_gb: float = 0.0
    swap_percent: float = 0.0


@dataclass
class GPUInfo:
    """GPU 信息"""
    index: int = 0
    name: str = ""
    memory_total_gb: float = 0.0
    memory_used_gb: float = 0.0
    memory_free_gb: float = 0.0
    memory_percent: float = 0.0
    utilization_percent: float = 0.0
    temperature_c: float = 0.0
    cuda_available: bool = False
    cuda_version: str = ""


@dataclass
class DiskInfo:
    """磁盘信息"""
    path: str = "/"
    total_gb: float = 0.0
    used_gb: float = 0.0
    free_gb: float = 0.0
    percent: float = 0.0


@dataclass
class ResourceSnapshot:
    """资源快照"""
    timestamp: float = field(default_factory=time.time)
    cpu: CPUInfo = field(default_factory=CPUInfo)
    memory: MemoryInfo = field(default_factory=MemoryInfo)
    gpus: List[GPUInfo] = field(default_factory=list)
    disks: List[DiskInfo] = field(default_factory=list)


@dataclass
class ResourceThresholds:
    """资源阈值配置"""
    cpu_percent: float = 90.0
    memory_percent: float = 85.0
    gpu_memory_percent: float = 90.0
    gpu_utilization_percent: float = 95.0
    disk_percent: float = 90.0


@dataclass
class TaskResourceRequirement:
    """任务资源需求"""
    task_id: str = ""
    task_type: str = ""
    cpu_cores: int = 1
    memory_gb: float = 1.0
    gpu_memory_gb: float = 0.0
    disk_space_gb: float = 1.0
    priority: int = 5


# ============================================================================
# 资源管理器
# ============================================================================

class ResourceManager:
    """统一资源管理器

    提供系统资源监控、阈值检查和任务资源调度能力。
    """

    def __init__(self, thresholds: Optional[ResourceThresholds] = None):
        self._thresholds = thresholds or ResourceThresholds()
        self._lock = threading.RLock()
        self._history: List[ResourceSnapshot] = []
        self._max_history = 60
        self._psutil_available = False
        self._cuda_available = False
        self._pynvml_available = False

        self._detect_libraries()

    def _detect_libraries(self):
        """检测可用的库"""
        try:
            import psutil
            self._psutil_available = True
            _logger.info("psutil 可用，CPU/内存/磁盘监控已启用")
        except ImportError:
            _logger.warning("psutil 未安装，CPU/内存/磁盘监控不可用")

        try:
            import torch
            self._cuda_available = torch.cuda.is_available()
            if self._cuda_available:
                _logger.info(f"CUDA 可用，GPU 数量: {torch.cuda.device_count()}")
        except ImportError:
            pass

        try:
            import pynvml
            pynvml.nvmlInit()
            self._pynvml_available = True
            _logger.info("pynvml 可用，GPU 详细监控已启用")
        except Exception:
            pass

    # --------------------------------------------------------------------
    # CPU 信息
    # --------------------------------------------------------------------

    def get_cpu_info(self) -> CPUInfo:
        """获取 CPU 信息"""
        info = CPUInfo()

        if not self._psutil_available:
            return info

        try:
            import psutil

            info.physical_cores = psutil.cpu_count(logical=False) or 0
            info.logical_cores = psutil.cpu_count(logical=True) or 0
            info.usage_percent = psutil.cpu_percent(interval=0.1)
            info.per_core_usage = psutil.cpu_percent(interval=0.1, percpu=True) or []

            freq = psutil.cpu_freq()
            if freq:
                info.freq_current = freq.current
                info.freq_min = freq.min
                info.freq_max = freq.max
        except Exception as e:
            _logger.error(f"获取 CPU 信息失败: {e}")

        return info

    # --------------------------------------------------------------------
    # 内存信息
    # --------------------------------------------------------------------

    def get_memory_info(self) -> MemoryInfo:
        """获取内存信息"""
        info = MemoryInfo()

        if not self._psutil_available:
            return info

        try:
            import psutil

            mem = psutil.virtual_memory()
            info.total_gb = round(mem.total / (1024 ** 3), 2)
            info.available_gb = round(mem.available / (1024 ** 3), 2)
            info.used_gb = round(mem.used / (1024 ** 3), 2)
            info.percent = mem.percent

            swap = psutil.swap_memory()
            info.swap_total_gb = round(swap.total / (1024 ** 3), 2)
            info.swap_used_gb = round(swap.used / (1024 ** 3), 2)
            info.swap_percent = swap.percent
        except Exception as e:
            _logger.error(f"获取内存信息失败: {e}")

        return info

    # --------------------------------------------------------------------
    # GPU 信息
    # --------------------------------------------------------------------

    def get_gpu_info(self) -> List[GPUInfo]:
        """获取 GPU 信息"""
        gpus: List[GPUInfo] = []

        if self._pynvml_available:
            try:
                import pynvml
                device_count = pynvml.nvmlDeviceGetCount()

                for i in range(device_count):
                    handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                    gpu = GPUInfo(index=i, cuda_available=True)

                    try:
                        name = pynvml.nvmlDeviceGetName(handle)
                        if isinstance(name, bytes):
                            name = name.decode('utf-8', errors='ignore')
                        gpu.name = name
                    except Exception:
                        gpu.name = f"GPU {i}"

                    try:
                        mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                        gpu.memory_total_gb = round(mem_info.total / (1024 ** 3), 2)
                        gpu.memory_used_gb = round(mem_info.used / (1024 ** 3), 2)
                        gpu.memory_free_gb = round(mem_info.free / (1024 ** 3), 2)
                        gpu.memory_percent = round(mem_info.used / mem_info.total * 100, 2) if mem_info.total > 0 else 0
                    except Exception:
                        pass

                    try:
                        utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
                        gpu.utilization_percent = utilization.gpu
                    except Exception:
                        pass

                    try:
                        temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                        gpu.temperature_c = temp
                    except Exception:
                        pass

                    gpus.append(gpu)

            except Exception as e:
                _logger.error(f"通过 pynvml 获取 GPU 信息失败: {e}")

        if not gpus and self._cuda_available:
            try:
                import torch
                device_count = torch.cuda.device_count()

                for i in range(device_count):
                    gpu = GPUInfo(index=i, cuda_available=True)
                    gpu.name = torch.cuda.get_device_name(i)
                    props = torch.cuda.get_device_properties(i)
                    gpu.memory_total_gb = round(props.total_memory / (1024 ** 3), 2)

                    try:
                        allocated = torch.cuda.memory_allocated(i)
                        reserved = torch.cuda.memory_reserved(i)
                        gpu.memory_used_gb = round(max(allocated, reserved) / (1024 ** 3), 2)
                        gpu.memory_free_gb = round(gpu.memory_total_gb - gpu.memory_used_gb, 2)
                        gpu.memory_percent = round(gpu.memory_used_gb / gpu.memory_total_gb * 100, 2) if gpu.memory_total_gb > 0 else 0
                    except Exception:
                        pass

                    gpus.append(gpu)

            except Exception as e:
                _logger.error(f"通过 torch 获取 GPU 信息失败: {e}")

        return gpus

    # --------------------------------------------------------------------
    # 磁盘信息
    # --------------------------------------------------------------------

    def get_disk_info(self, paths: Optional[List[str]] = None) -> List[DiskInfo]:
        """获取磁盘信息

        Args:
            paths: 要检查的路径列表，None 则检查当前工作目录所在磁盘
        """
        disks: List[DiskInfo] = []

        if paths is None:
            paths = [os.getcwd()]

        for path in paths:
            try:
                if self._psutil_available:
                    import psutil
                    usage = psutil.disk_usage(path)
                    disk = DiskInfo(
                        path=path,
                        total_gb=round(usage.total / (1024 ** 3), 2),
                        used_gb=round(usage.used / (1024 ** 3), 2),
                        free_gb=round(usage.free / (1024 ** 3), 2),
                        percent=usage.percent,
                    )
                else:
                    try:
                        import ctypes
                        free_bytes = ctypes.c_ulonglong(0)
                        total_bytes = ctypes.c_ulonglong(0)
                        ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                            ctypes.c_wchar_p(path),
                            None,
                            ctypes.pointer(total_bytes),
                            ctypes.pointer(free_bytes),
                        )
                        total = total_bytes.value
                        free = free_bytes.value
                        used = total - free
                        disk = DiskInfo(
                            path=path,
                            total_gb=round(total / (1024 ** 3), 2),
                            used_gb=round(used / (1024 ** 3), 2),
                            free_gb=round(free / (1024 ** 3), 2),
                            percent=round(used / total * 100, 2) if total > 0 else 0,
                        )
                    except Exception:
                        disk = DiskInfo(path=path)
                disks.append(disk)
            except Exception as e:
                _logger.error(f"获取磁盘信息失败 ({path}): {e}")

        return disks

    # --------------------------------------------------------------------
    # 综合快照
    # --------------------------------------------------------------------

    def get_snapshot(self, disk_paths: Optional[List[str]] = None) -> ResourceSnapshot:
        """获取资源快照

        Args:
            disk_paths: 要检查的磁盘路径

        Returns:
            资源快照
        """
        snapshot = ResourceSnapshot(
            cpu=self.get_cpu_info(),
            memory=self.get_memory_info(),
            gpus=self.get_gpu_info(),
            disks=self.get_disk_info(disk_paths),
        )

        with self._lock:
            self._history.append(snapshot)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

        return snapshot

    def get_history(self) -> List[ResourceSnapshot]:
        """获取历史快照"""
        with self._lock:
            return list(self._history)

    # --------------------------------------------------------------------
    # 阈值检查
    # --------------------------------------------------------------------

    def check_thresholds(self, snapshot: Optional[ResourceSnapshot] = None) -> Dict[str, Any]:
        """检查资源阈值

        Args:
            snapshot: 资源快照，None 则获取新快照

        Returns:
            阈值检查结果
        """
        if snapshot is None:
            snapshot = self.get_snapshot()

        warnings: List[Dict[str, Any]] = []
        critical: List[Dict[str, Any]] = []
        is_critical = False

        if snapshot.cpu.usage_percent > self._thresholds.cpu_percent:
            severity = "critical" if snapshot.cpu.usage_percent > 95 else "warning"
            item = {
                "type": "cpu",
                "metric": "usage_percent",
                "value": snapshot.cpu.usage_percent,
                "threshold": self._thresholds.cpu_percent,
                "severity": severity,
                "message": f"CPU 使用率 {snapshot.cpu.usage_percent:.1f}% 超过阈值 {self._thresholds.cpu_percent:.1f}%",
            }
            if severity == "critical":
                critical.append(item)
                is_critical = True
            else:
                warnings.append(item)

        if snapshot.memory.percent > self._thresholds.memory_percent:
            severity = "critical" if snapshot.memory.percent > 95 else "warning"
            item = {
                "type": "memory",
                "metric": "percent",
                "value": snapshot.memory.percent,
                "threshold": self._thresholds.memory_percent,
                "severity": severity,
                "message": f"内存使用率 {snapshot.memory.percent:.1f}% 超过阈值 {self._thresholds.memory_percent:.1f}%",
            }
            if severity == "critical":
                critical.append(item)
                is_critical = True
            else:
                warnings.append(item)

        for gpu in snapshot.gpus:
            if gpu.memory_percent > self._thresholds.gpu_memory_percent:
                severity = "critical" if gpu.memory_percent > 95 else "warning"
                item = {
                    "type": "gpu",
                    "gpu_index": gpu.index,
                    "metric": "memory_percent",
                    "value": gpu.memory_percent,
                    "threshold": self._thresholds.gpu_memory_percent,
                    "severity": severity,
                    "message": f"GPU {gpu.index} 显存使用率 {gpu.memory_percent:.1f}% 超过阈值",
                }
                if severity == "critical":
                    critical.append(item)
                    is_critical = True
                else:
                    warnings.append(item)

            if gpu.utilization_percent > self._thresholds.gpu_utilization_percent:
                item = {
                    "type": "gpu",
                    "gpu_index": gpu.index,
                    "metric": "utilization_percent",
                    "value": gpu.utilization_percent,
                    "threshold": self._thresholds.gpu_utilization_percent,
                    "severity": "warning",
                    "message": f"GPU {gpu.index} 利用率 {gpu.utilization_percent:.1f}% 较高",
                }
                warnings.append(item)

        for disk in snapshot.disks:
            if disk.percent > self._thresholds.disk_percent:
                severity = "critical" if disk.percent > 95 else "warning"
                item = {
                    "type": "disk",
                    "path": disk.path,
                    "metric": "percent",
                    "value": disk.percent,
                    "threshold": self._thresholds.disk_percent,
                    "severity": severity,
                    "message": f"磁盘 {disk.path} 使用率 {disk.percent:.1f}% 超过阈值",
                }
                if severity == "critical":
                    critical.append(item)
                    is_critical = True
                else:
                    warnings.append(item)

        return {
            "is_critical": is_critical,
            "warnings": warnings,
            "critical": critical,
            "total_issues": len(warnings) + len(critical),
            "snapshot_timestamp": snapshot.timestamp,
        }

    # --------------------------------------------------------------------
    # 任务资源评估
    # --------------------------------------------------------------------

    def can_accept_task(self, requirement: TaskResourceRequirement) -> Tuple[bool, Dict[str, Any]]:
        """评估是否能接受任务

        Args:
            requirement: 任务资源需求

        Returns:
            (是否可接受, 详细信息)
        """
        snapshot = self.get_snapshot()
        issues = []
        can_accept = True

        if snapshot.cpu.logical_cores > 0:
            available_cores = max(1, int(snapshot.cpu.logical_cores * (1 - snapshot.cpu.usage_percent / 100)))
            if requirement.cpu_cores > available_cores:
                issues.append({
                    "type": "cpu",
                    "required": requirement.cpu_cores,
                    "available": available_cores,
                    "message": f"CPU 核心不足 (需要 {requirement.cpu_cores}, 可用约 {available_cores})",
                })
                can_accept = False

        if snapshot.memory.available_gb > 0:
            if requirement.memory_gb > snapshot.memory.available_gb:
                issues.append({
                    "type": "memory",
                    "required_gb": requirement.memory_gb,
                    "available_gb": snapshot.memory.available_gb,
                    "message": f"内存不足 (需要 {requirement.memory_gb:.1f}GB, 可用 {snapshot.memory.available_gb:.1f}GB)",
                })
                can_accept = False

        if requirement.gpu_memory_gb > 0 and snapshot.gpus:
            gpu_ok = False
            for gpu in snapshot.gpus:
                if gpu.memory_free_gb >= requirement.gpu_memory_gb:
                    gpu_ok = True
                    break
            if not gpu_ok:
                issues.append({
                    "type": "gpu",
                    "required_gb": requirement.gpu_memory_gb,
                    "message": f"GPU 显存不足 (需要 {requirement.gpu_memory_gb:.1f}GB)",
                })
                can_accept = False

        return can_accept, {
            "can_accept": can_accept,
            "issues": issues,
            "requirement": {
                "task_id": requirement.task_id,
                "task_type": requirement.task_type,
                "cpu_cores": requirement.cpu_cores,
                "memory_gb": requirement.memory_gb,
                "gpu_memory_gb": requirement.gpu_memory_gb,
            },
        }

    def estimate_task_resource(self, task_type: str, input_size_gb: float = 0.0) -> TaskResourceRequirement:
        """估算任务资源需求

        Args:
            task_type: 任务类型
            input_size_gb: 输入数据大小（GB）

        Returns:
            任务资源需求
        """
        profiles = {
            "puppet_style": TaskResourceRequirement(
                task_type="puppet_style",
                cpu_cores=4,
                memory_gb=4.0,
                gpu_memory_gb=2.0,
                disk_space_gb=max(2.0, input_size_gb * 2),
                priority=5,
            ),
            "quality_assess": TaskResourceRequirement(
                task_type="quality_assess",
                cpu_cores=2,
                memory_gb=2.0,
                gpu_memory_gb=0.0,
                disk_space_gb=max(0.5, input_size_gb * 0.5),
                priority=3,
            ),
            "parameter_optimize": TaskResourceRequirement(
                task_type="parameter_optimize",
                cpu_cores=2,
                memory_gb=1.0,
                gpu_memory_gb=0.0,
                disk_space_gb=0.1,
                priority=2,
            ),
            "video_render": TaskResourceRequirement(
                task_type="video_render",
                cpu_cores=6,
                memory_gb=8.0,
                gpu_memory_gb=4.0,
                disk_space_gb=max(5.0, input_size_gb * 3),
                priority=7,
            ),
        }

        profile = profiles.get(task_type, TaskResourceRequirement(
            task_type=task_type,
            cpu_cores=1,
            memory_gb=1.0,
            gpu_memory_gb=0.0,
            disk_space_gb=1.0,
            priority=5,
        ))

        return profile

    # --------------------------------------------------------------------
    # 统计信息
    # --------------------------------------------------------------------

    def get_summary(self) -> Dict[str, Any]:
        """获取资源摘要"""
        snapshot = self.get_snapshot()
        thresholds_result = self.check_thresholds(snapshot)

        return {
            "timestamp": snapshot.timestamp,
            "cpu": {
                "usage_percent": snapshot.cpu.usage_percent,
                "logical_cores": snapshot.cpu.logical_cores,
                "physical_cores": snapshot.cpu.physical_cores,
            },
            "memory": {
                "percent": snapshot.memory.percent,
                "used_gb": snapshot.memory.used_gb,
                "total_gb": snapshot.memory.total_gb,
                "available_gb": snapshot.memory.available_gb,
            },
            "gpus": [
                {
                    "index": g.index,
                    "name": g.name,
                    "memory_percent": g.memory_percent,
                    "utilization_percent": g.utilization_percent,
                    "temperature_c": g.temperature_c,
                }
                for g in snapshot.gpus
            ],
            "disks": [
                {
                    "path": d.path,
                    "percent": d.percent,
                    "free_gb": d.free_gb,
                    "total_gb": d.total_gb,
                }
                for d in snapshot.disks
            ],
            "thresholds": thresholds_result,
        }


# ============================================================================
# 模块单例
# ============================================================================

_default_manager: Optional[ResourceManager] = None


def get_resource_manager(thresholds: Optional[ResourceThresholds] = None) -> ResourceManager:
    """获取默认资源管理器实例"""
    global _default_manager
    if _default_manager is None:
        _default_manager = ResourceManager(thresholds)
    return _default_manager


# ============================================================================
# 命令行测试入口
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("统一资源管理器测试")
    print("=" * 60)

    manager = ResourceManager()

    print("\n1. 系统资源摘要...")
    summary = manager.get_summary()
    print(f"  CPU: {summary['cpu']['usage_percent']:.1f}% ({summary['cpu']['logical_cores']} 核)")
    print(f"  内存: {summary['memory']['percent']:.1f}% ({summary['memory']['used_gb']:.1f}/{summary['memory']['total_gb']:.1f} GB)")
    print(f"  GPU: {len(summary['gpus'])} 个")
    for gpu in summary['gpus']:
        print(f"    - {gpu['name']}: 显存 {gpu['memory_percent']:.1f}%, 利用率 {gpu['utilization_percent']:.1f}%")
    print(f"  磁盘: {len(summary['disks'])} 个")
    for disk in summary['disks']:
        print(f"    - {disk['path']}: {disk['percent']:.1f}% (剩余 {disk['free_gb']:.1f} GB)")

    print("\n2. 阈值检查...")
    threshold_result = summary['thresholds']
    print(f"  严重问题: {len(threshold_result['critical'])}")
    print(f"  警告: {len(threshold_result['warnings'])}")
    if threshold_result['is_critical']:
        print("  ⚠️ 系统资源处于临界状态")

    print("\n3. 任务资源评估...")
    req = manager.estimate_task_resource("puppet_style", input_size_gb=1.0)
    can_accept, details = manager.can_accept_task(req)
    print(f"  木偶风格化任务: {'可接受' if can_accept else '资源不足'}")
    if details['issues']:
        for issue in details['issues']:
            print(f"    - {issue['message']}")

    print("\n" + "=" * 60)
    print("测试完成！")
