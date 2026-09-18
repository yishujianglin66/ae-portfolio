"""resource_manager 模块单元测试

覆盖范围:
- 库检测逻辑（psutil / torch / pynvml 可用与缺失的降级行为）
- CPU / 内存 / 磁盘 / GPU 信息采集路径
- 阈值检查的告警与严重判定边界
- 任务可接受性评估（CPU、内存、显存不足）
- 任务资源需求估算
- 历史快照的容量限制与副本语义
- 端到端 get_summary 在不同库状态下的健壮性

此模块曾出现 psutil 缺失导致监控面板拿不到 CPU/内存数据的问题
（见 project_memory.md），本套件用以锁定「库缺失时优雅降级」与
「关键阈值计算正确」这两条主轴，防止回归。
"""
from __future__ import annotations

import os
import sys
import types
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import resource_manager as rm

# ============================================================================
# 测试夹具
# ============================================================================

@pytest.fixture
def manager():
    """默认阈值的 ResourceManager 实例"""
    return rm.ResourceManager()


@pytest.fixture
def strict_manager():
    """高阈值 ResourceManager 实例，便于触发 critical 分支"""
    return rm.ResourceManager(
        thresholds=rm.ResourceThresholds(
            cpu_percent=50.0,
            memory_percent=50.0,
            gpu_memory_percent=50.0,
            gpu_utilization_percent=50.0,
            disk_percent=50.0,
        )
    )


@pytest.fixture(autouse=True)
def _isolate_singleton():
    """隔离模块级单例，避免测试间互相污染"""
    original = rm._default_manager
    rm._default_manager = None
    yield
    rm._default_manager = original


def _make_psutil(memory_percent=60.0, cpu_percent=70.0):
    """构造一个最小的 psutil MagicMock，覆盖 resource_manager 调用的全部 API"""
    psutil = MagicMock()
    psutil.cpu_count.side_effect = lambda logical=False: 8 if logical else 4
    psutil.cpu_percent.side_effect = [
        cpu_percent,
        [cpu_percent] * 4,
    ]
    freq = MagicMock(current=3000.0, min=1200.0, max=4200.0)
    psutil.cpu_freq.return_value = freq

    mem = MagicMock(
        total=16 * 1024 ** 3,
        available=6 * 1024 ** 3,
        used=10 * 1024 ** 3,
        percent=memory_percent,
    )
    psutil.virtual_memory.return_value = mem

    swap = MagicMock(total=4 * 1024 ** 3, used=1 * 1024 ** 3, percent=25.0)
    psutil.swap_memory.return_value = swap

    disk = MagicMock(
        total=500 * 1024 ** 3,
        used=300 * 1024 ** 3,
        free=200 * 1024 ** 3,
        percent=60.0,
    )
    psutil.disk_usage.return_value = disk
    return psutil


# ============================================================================
# 数据类测试
# ============================================================================

class TestDataclasses:
    """数据类的默认值与构造测试"""

    def test_cpu_info_defaults(self):
        info = rm.CPUInfo()
        assert info.physical_cores == 0
        assert info.logical_cores == 0
        assert info.usage_percent == 0.0
        assert info.per_core_usage == []

    def test_memory_info_defaults(self):
        info = rm.MemoryInfo()
        assert info.total_gb == 0.0
        assert info.swap_percent == 0.0

    def test_gpu_info_defaults(self):
        info = rm.GPUInfo()
        assert info.index == 0
        assert info.cuda_available is False
        assert info.cuda_version == ""

    def test_disk_info_defaults(self):
        info = rm.DiskInfo()
        assert info.path == "/"
        assert info.percent == 0.0

    def test_thresholds_defaults(self):
        t = rm.ResourceThresholds()
        assert t.cpu_percent == 90.0
        assert t.memory_percent == 85.0
        assert t.gpu_memory_percent == 90.0
        assert t.disk_percent == 90.0

    def test_task_requirement_defaults(self):
        r = rm.TaskResourceRequirement()
        assert r.cpu_cores == 1
        assert r.memory_gb == 1.0
        assert r.priority == 5


# ============================================================================
# 库检测
# ============================================================================

class TestLibraryDetection:
    """_detect_libraries 的可用/缺失分支"""

    def test_psutil_available_sets_flag(self):
        mgr = rm.ResourceManager()
        # 在正常的开发机上 psutil 通常已安装，至少要能给出布尔结论
        assert isinstance(mgr._psutil_available, bool)

    def test_psutil_missing_graceful_degradation(self):
        """psutil 不可用时不能抛异常，且 CPU/内存应返回零值"""
        with patch.dict(sys.modules, {"psutil": None}):
            mgr = rm.ResourceManager()
            assert mgr._psutil_available is False

            cpu = mgr.get_cpu_info()
            assert cpu.usage_percent == 0.0
            assert cpu.logical_cores == 0

            mem = mgr.get_memory_info()
            assert mem.total_gb == 0.0
            assert mem.percent == 0.0

    def test_pynvml_failure_does_not_raise(self):
        """pynvml 存在但 nvmlInit 抛错时必须被吞掉并降级到 torch 分支"""
        fake_pynvml = MagicMock()
        fake_pynvml.nvmlInit.side_effect = RuntimeError("driver not loaded")
        with patch.dict(sys.modules, {"pynvml": fake_pynvml}):
            mgr = rm.ResourceManager()
            # 不应抛异常
            gpus = mgr.get_gpu_info()
            assert isinstance(gpus, list)


# ============================================================================
# CPU / 内存信息
# ============================================================================

class TestCpuInfo:
    """CPU 信息采集路径"""

    def test_cpu_info_with_psutil(self, manager):
        fake = _make_psutil(cpu_percent=42.0)
        with patch.dict(sys.modules, {"psutil": fake}):
            manager._psutil_available = True
            info = manager.get_cpu_info()
        assert info.physical_cores == 4
        assert info.logical_cores == 8
        assert info.usage_percent == 42.0
        assert len(info.per_core_usage) == 4
        assert info.freq_max == 4200.0

    def test_cpu_info_psutil_returns_none_freq(self, manager):
        """cpu_freq 返回 None 时不能崩（部分环境/虚拟机）"""
        fake = _make_psutil()
        fake.cpu_freq.return_value = None
        with patch.dict(sys.modules, {"psutil": fake}):
            manager._psutil_available = True
            info = manager.get_cpu_info()
        assert info.freq_current == 0.0
        assert info.freq_max == 0.0

    def test_cpu_info_psutil_exception_is_logged(self, manager):
        """psutil 抛错时返回零值 CPUInfo，不能传播异常"""
        fake = MagicMock()
        fake.cpu_count.side_effect = OSError("boom")
        with patch.dict(sys.modules, {"psutil": fake}):
            manager._psutil_available = True
            info = manager.get_cpu_info()
        assert info.physical_cores == 0


class TestMemoryInfo:
    """内存信息采集路径"""

    def test_memory_info_with_psutil(self, manager):
        fake = _make_psutil(memory_percent=72.5)
        with patch.dict(sys.modules, {"psutil": fake}):
            manager._psutil_available = True
            info = manager.get_memory_info()
        assert info.total_gb == 16.0
        assert info.percent == 72.5
        assert info.used_gb == 10.0
        assert info.swap_percent == 25.0

    def test_memory_info_psutil_exception(self, manager):
        fake = MagicMock()
        fake.virtual_memory.side_effect = OSError("nope")
        with patch.dict(sys.modules, {"psutil": fake}):
            manager._psutil_available = True
            info = manager.get_memory_info()
        assert info.total_gb == 0.0


# ============================================================================
# 磁盘信息
# ============================================================================

class TestDiskInfo:
    """磁盘采集路径，含 Windows ctypes 降级分支"""

    def test_disk_info_with_psutil(self, manager):
        fake = _make_psutil()
        with patch.dict(sys.modules, {"psutil": fake}):
            manager._psutil_available = True
            disks = manager.get_disk_info(["C:/", "D:/"])
        assert len(disks) == 2
        assert disks[0].path == "C:/"
        assert disks[0].percent == 60.0

    def test_disk_info_default_uses_cwd(self, manager):
        """paths=None 时使用 os.getcwd()"""
        fake = _make_psutil()
        with patch.dict(sys.modules, {"psutil": fake}):
            manager._psutil_available = True
            disks = manager.get_disk_info()
        assert len(disks) == 1
        assert disks[0].path == os.getcwd()

    def test_disk_info_without_psutil_falls_back(self, manager):
        """psutil 缺失时不应抛异常；ctypes 在 Windows 上能拿到数据"""
        with patch.dict(sys.modules, {"psutil": None}):
            manager._psutil_available = False
            disks = manager.get_disk_info([os.getcwd()])
        # ctypes 路径可能在 CI 上失败（返回空 DiskInfo），但绝不能抛
        assert len(disks) == 1
        assert disks[0].path == os.getcwd()


# ============================================================================
# 快照与历史
# ============================================================================

class TestSnapshotAndHistory:
    """get_snapshot / get_history 的容量与副本语义"""

    def test_get_snapshot_appends_to_history(self, manager):
        with patch.dict(sys.modules, {"psutil": _make_psutil()}):
            manager._psutil_available = True
            s = manager.get_snapshot()
        assert isinstance(s, rm.ResourceSnapshot)
        assert manager.get_history()[-1] is s

    def test_history_respects_max_length(self, manager):
        manager._max_history = 3
        for _ in range(5):
            manager.get_snapshot()
        assert len(manager.get_history()) == 3

    def test_get_history_returns_copy(self, manager):
        manager.get_snapshot()
        h1 = manager.get_history()
        h1.clear()
        assert len(manager.get_history()) == 1


# ============================================================================
# 阈值检查
# ============================================================================

class TestCheckThresholds:
    """阈值检查的严重性判定（critical / warning 边界）"""

    def test_normal_snapshot_has_no_issue(self, manager):
        snap = rm.ResourceSnapshot(
            cpu=rm.CPUInfo(usage_percent=20.0),
            memory=rm.MemoryInfo(percent=30.0),
        )
        result = manager.check_thresholds(snap)
        assert result["is_critical"] is False
        assert result["warnings"] == []
        assert result["critical"] == []

    def test_cpu_warning_severity(self, manager):
        snap = rm.ResourceSnapshot(
            cpu=rm.CPUInfo(usage_percent=92.0),  # 90 < x ≤ 95
            memory=rm.MemoryInfo(percent=20.0),
        )
        result = manager.check_thresholds(snap)
        assert result["is_critical"] is False
        assert len(result["warnings"]) == 1
        assert result["warnings"][0]["type"] == "cpu"
        assert result["warnings"][0]["severity"] == "warning"

    def test_cpu_critical_severity(self, manager):
        snap = rm.ResourceSnapshot(
            cpu=rm.CPUInfo(usage_percent=98.0),  # > 95
            memory=rm.MemoryInfo(percent=20.0),
        )
        result = manager.check_thresholds(snap)
        assert result["is_critical"] is True
        assert len(result["critical"]) == 1
        assert result["critical"][0]["severity"] == "critical"

    def test_memory_warning_and_critical(self, manager):
        snap_warn = rm.ResourceSnapshot(
            memory=rm.MemoryInfo(percent=90.0),  # 85 < x ≤ 95
        )
        snap_crit = rm.ResourceSnapshot(
            memory=rm.MemoryInfo(percent=99.0),  # > 95
        )
        assert manager.check_thresholds(snap_warn)["is_critical"] is False
        assert manager.check_thresholds(snap_crit)["is_critical"] is True

    def test_gpu_memory_and_utilization(self, manager):
        snap = rm.ResourceSnapshot(
            gpus=[
                rm.GPUInfo(
                    index=0,
                    memory_percent=80.0,  # > 阈值 90? 这里用宽松阈值
                ),
            ]
        )
        # 80 < 90 默认阈值，触发不了
        result = manager.check_thresholds(snap)
        assert result["total_issues"] == 0

        # 改用 92 触发 warning
        snap.gpus[0].memory_percent = 92.0
        result = manager.check_thresholds(snap)
        assert any(
            w["type"] == "gpu" and w["metric"] == "memory_percent"
            for w in result["warnings"]
        )

        # GPU 利用率告警
        snap2 = rm.ResourceSnapshot(
            gpus=[rm.GPUInfo(index=0, utilization_percent=99.0)],
        )
        result2 = manager.check_thresholds(snap2)
        assert any(
            w["metric"] == "utilization_percent" for w in result2["warnings"]
        )

    def test_disk_threshold(self, manager):
        snap = rm.ResourceSnapshot(
            disks=[rm.DiskInfo(path="C:/", percent=80.0)],
        )
        # 80 < 90 默认阈值，不触发
        assert manager.check_thresholds(snap)["total_issues"] == 0

        snap.disks[0].percent = 96.0
        result = manager.check_thresholds(snap)
        assert result["is_critical"] is True
        assert result["critical"][0]["type"] == "disk"

    def test_strict_thresholds_aggregate_issues(self, strict_manager):
        snap = rm.ResourceSnapshot(
            cpu=rm.CPUInfo(usage_percent=80.0),
            memory=rm.MemoryInfo(percent=80.0),
            disks=[rm.DiskInfo(path="/", percent=80.0)],
        )
        result = strict_manager.check_thresholds(snap)
        # 三个指标同时 > 50，应该有三个 warnings
        types = {w["type"] for w in result["warnings"]}
        assert types == {"cpu", "memory", "disk"}


# ============================================================================
# 任务可接受性评估
# ============================================================================

class TestCanAcceptTask:
    """can_accept_task 的资源判定逻辑"""

    def test_accept_when_resources_available(self, manager):
        snap = rm.ResourceSnapshot(
            cpu=rm.CPUInfo(usage_percent=10.0, logical_cores=8),
            memory=rm.MemoryInfo(available_gb=10.0, percent=20.0),
            gpus=[rm.GPUInfo(memory_free_gb=8.0)],
        )
        req = rm.TaskResourceRequirement(
            task_id="t1", task_type="render",
            cpu_cores=2, memory_gb=4.0, gpu_memory_gb=2.0,
        )
        with patch.object(manager, "get_snapshot", return_value=snap):
            can_accept, info = manager.can_accept_task(req)
        assert can_accept is True
        assert info["can_accept"] is True
        assert info["issues"] == []

    def test_reject_when_cpu_shortage(self, manager):
        snap = rm.ResourceSnapshot(
            cpu=rm.CPUInfo(usage_percent=90.0, logical_cores=4),
            memory=rm.MemoryInfo(available_gb=10.0, percent=20.0),
        )
        req = rm.TaskResourceRequirement(
            task_id="t1", cpu_cores=4, memory_gb=1.0,
        )
        with patch.object(manager, "get_snapshot", return_value=snap):
            can_accept, info = manager.can_accept_task(req)
        assert can_accept is False
        assert any(i["type"] == "cpu" for i in info["issues"])

    def test_reject_when_memory_shortage(self, manager):
        snap = rm.ResourceSnapshot(
            cpu=rm.CPUInfo(usage_percent=10.0, logical_cores=8),
            memory=rm.MemoryInfo(available_gb=1.0, percent=90.0),
        )
        req = rm.TaskResourceRequirement(
            task_id="t1", cpu_cores=1, memory_gb=4.0,
        )
        with patch.object(manager, "get_snapshot", return_value=snap):
            can_accept, info = manager.can_accept_task(req)
        assert can_accept is False
        assert any(i["type"] == "memory" for i in info["issues"])

    def test_reject_when_gpu_memory_shortage(self, manager):
        snap = rm.ResourceSnapshot(
            cpu=rm.CPUInfo(usage_percent=10.0, logical_cores=8),
            memory=rm.MemoryInfo(available_gb=10.0, percent=20.0),
            gpus=[rm.GPUInfo(memory_free_gb=1.0)],
        )
        req = rm.TaskResourceRequirement(
            task_id="t1", cpu_cores=1, memory_gb=1.0, gpu_memory_gb=4.0,
        )
        with patch.object(manager, "get_snapshot", return_value=snap):
            can_accept, info = manager.can_accept_task(req)
        assert can_accept is False
        assert any(i["type"] == "gpu" for i in info["issues"])

    def test_no_gpu_detected_skips_gpu_check(self, manager):
        """GPU 列表为空时 `and snapshot.gpus` 短路掉 GPU 校验。

        这是当前实现的有意行为：未探测到任何 GPU 信息时，调度器
        不在 GPU 维度拒绝任务（其它系统可能通过 CPU 回退完成）。
        若后续调整此策略，请同步更新本测试。
        """
        snap = rm.ResourceSnapshot(
            cpu=rm.CPUInfo(usage_percent=10.0, logical_cores=8),
            memory=rm.MemoryInfo(available_gb=10.0, percent=20.0),
            gpus=[],
        )
        req = rm.TaskResourceRequirement(
            task_id="t1", cpu_cores=1, memory_gb=1.0, gpu_memory_gb=2.0,
        )
        with patch.object(manager, "get_snapshot", return_value=snap):
            can_accept, info = manager.can_accept_task(req)
        assert can_accept is True
        # GPU 维度不应产生 issues
        assert not any(i["type"] == "gpu" for i in info["issues"])

    def test_multiple_issues_collected(self, manager):
        snap = rm.ResourceSnapshot(
            cpu=rm.CPUInfo(usage_percent=99.0, logical_cores=2),
            memory=rm.MemoryInfo(available_gb=0.1, percent=99.0),
        )
        req = rm.TaskResourceRequirement(
            task_id="t1", cpu_cores=4, memory_gb=8.0,
        )
        with patch.object(manager, "get_snapshot", return_value=snap):
            can_accept, info = manager.can_accept_task(req)
        assert can_accept is False
        types = {i["type"] for i in info["issues"]}
        assert "cpu" in types and "memory" in types


# ============================================================================
# 任务资源估算
# ============================================================================

class TestEstimateTaskResource:
    """estimate_task_resource 的预设与默认值"""

    def test_known_profiles(self, manager):
        profiles = {
            "puppet_style": (4, 4.0, 2.0),
            "quality_assess": (2, 2.0, 0.0),
            "parameter_optimize": (2, 1.0, 0.0),
            "video_render": (6, 8.0, 4.0),
        }
        for task_type, (cores, mem, gpu) in profiles.items():
            req = manager.estimate_task_resource(task_type, input_size_gb=1.0)
            assert req.task_type == task_type
            assert req.cpu_cores == cores, task_type
            assert req.memory_gb == mem, task_type
            assert req.gpu_memory_gb == gpu, task_type

    def test_input_size_scales_disk(self, manager):
        req_small = manager.estimate_task_resource("puppet_style", input_size_gb=0.1)
        req_large = manager.estimate_task_resource("puppet_style", input_size_gb=5.0)
        # 大输入需要更多磁盘空间（max(2.0, input*2)）
        assert req_large.disk_space_gb > req_small.disk_space_gb
        assert req_small.disk_space_gb == 2.0  # 触发下限

    def test_unknown_task_falls_back_to_default(self, manager):
        req = manager.estimate_task_resource("totally_unknown_xyz")
        assert req.cpu_cores == 1
        assert req.memory_gb == 1.0
        assert req.gpu_memory_gb == 0.0
        assert req.task_type == "totally_unknown_xyz"


# ============================================================================
# 摘要与单例
# ============================================================================

class TestSummaryAndSingleton:
    """get_summary 与 get_resource_manager 的端到端表现"""

    def test_get_summary_keys(self, manager):
        fake = _make_psutil()
        with patch.dict(sys.modules, {"psutil": fake}):
            manager._psutil_available = True
            summary = manager.get_summary()
        assert set(summary.keys()) == {
            "timestamp", "cpu", "memory", "gpus", "disks", "thresholds",
        }
        assert "usage_percent" in summary["cpu"]
        assert "warnings" in summary["thresholds"]
        assert "critical" in summary["thresholds"]
        assert isinstance(summary["gpus"], list)
        assert isinstance(summary["disks"], list)

    def test_get_summary_handles_missing_psutil(self, manager):
        with patch.dict(sys.modules, {"psutil": None}):
            manager._psutil_available = False
            summary = manager.get_summary()
        # 即便没有 psutil，也不应抛异常；CPU/内存字段应全为 0
        assert summary["cpu"]["usage_percent"] == 0.0
        assert summary["memory"]["percent"] == 0.0

    def test_singleton_returns_same_instance(self, manager):
        rm._default_manager = manager
        again = rm.get_resource_manager()
        assert again is manager

    def test_singleton_creates_on_first_call(self):
        rm._default_manager = None
        first = rm.get_resource_manager()
        assert isinstance(first, rm.ResourceManager)
        assert rm._default_manager is first
