"""
tests/test_software_sdk.py - 软件 SDK 基类/注册中心/类型定义测试 (TDD)

Phase A1: 测试先行
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional, Set

import pytest

from software_sdk.base import BaseSoftwareAdapter
from software_sdk.registry import SoftwareRegistry
from software_sdk.types import (
    ConnectionStatus,
    FallbackStrategyType,
    SoftwareCapabilities,
    SoftwareCapability,
    SoftwareConfig,
    SoftwareStatus,
    SoftwareType,
    Task,
    TaskPriority,
    TaskStatus,
)

# ============================================================================
# Types Tests
# ============================================================================

class TestSoftwareType:
    """SoftwareType 枚举测试"""

    def test_enum_values(self) -> None:
        assert SoftwareType.AFTER_EFFECTS.value == "after_effects"
        assert SoftwareType.BLENDER.value == "blender"
        assert SoftwareType.SILHOUETTE.value == "silhouette"
        assert SoftwareType.TOPAZ_VIDEO_AI.value == "topaz_video_ai"
        assert SoftwareType.DAVINCI_RESOLVE.value == "davinci_resolve"
        assert SoftwareType.FFMPEG.value == "ffmpeg"

    def test_all_software_types_exist(self) -> None:
        expected = {
            "after_effects", "premiere_pro", "photoshop", "davinci_resolve",
            "blender", "topaz_video_ai", "ffmpeg", "media_encoder",
            "illustrator", "silhouette",
        }
        actual = {st.value for st in SoftwareType}
        assert expected.issubset(actual)


class TestConnectionStatus:
    def test_status_values(self) -> None:
        assert ConnectionStatus.CONNECTED.value == "connected"
        assert ConnectionStatus.DISCONNECTED.value == "disconnected"
        assert ConnectionStatus.ERROR.value == "error"


class TestTaskPriority:
    def test_priority_ordering(self) -> None:
        assert TaskPriority.CRITICAL.value > TaskPriority.HIGH.value
        assert TaskPriority.HIGH.value > TaskPriority.NORMAL.value
        assert TaskPriority.NORMAL.value > TaskPriority.LOW.value


class TestSoftwareCapability:
    def test_capability_values(self) -> None:
        assert SoftwareCapability.COMPOSITING.value == "compositing"
        assert SoftwareCapability.ROTOSCOPING.value == "rotoscoping"
        assert SoftwareCapability.UPSCALING.value == "upscaling"


class TestSoftwareStatus:
    def test_to_dict(self) -> None:
        status = SoftwareStatus(
            software=SoftwareType.AFTER_EFFECTS,
            status=ConnectionStatus.CONNECTED,
            version="24.0",
            cpu_usage=25.0,
        )
        d = status.to_dict()
        assert d["software"] == "after_effects"
        assert d["status"] == "connected"
        assert d["version"] == "24.0"
        assert d["cpu_usage"] == 25.0

    def test_defaults(self) -> None:
        status = SoftwareStatus(
            software=SoftwareType.BLENDER,
            status=ConnectionStatus.DISCONNECTED,
        )
        assert status.version is None
        assert status.cpu_usage == 0.0
        assert status.active_tasks == 0


class TestSoftwareCapabilities:
    def test_has_capability(self) -> None:
        caps = SoftwareCapabilities(
            software=SoftwareType.AFTER_EFFECTS,
            capabilities={SoftwareCapability.COMPOSITING, SoftwareCapability.SCRIPTING},
        )
        assert caps.has_capability(SoftwareCapability.COMPOSITING) is True
        assert caps.has_capability(SoftwareCapability.ROTOSCOPING) is False

    def test_to_dict(self) -> None:
        caps = SoftwareCapabilities(
            software=SoftwareType.FFMPEG,
            capabilities={SoftwareCapability.RENDERING},
            gpu_accelerated=True,
        )
        d = caps.to_dict()
        assert d["software"] == "ffmpeg"
        assert "rendering" in d["capabilities"]
        assert d["gpu_accelerated"] is True


class TestTask:
    def test_task_creation(self) -> None:
        task = Task(task_type="render", target_software=SoftwareType.AFTER_EFFECTS)
        assert task.task_type == "render"
        assert task.status == TaskStatus.PENDING
        assert task.priority == TaskPriority.NORMAL
        assert task.retry_count == 0
        assert task.task_id  # auto-generated

    def test_task_priority_comparison(self) -> None:
        high = Task(priority=TaskPriority.HIGH)
        low = Task(priority=TaskPriority.LOW)
        assert high < low  # higher priority = lower sort value

    def test_task_to_dict(self) -> None:
        task = Task(
            task_type="export",
            target_software=SoftwareType.BLENDER,
            params={"format": "fbx"},
        )
        d = task.to_dict()
        assert d["task_type"] == "export"
        assert d["target_software"] == "blender"
        assert d["params"]["format"] == "fbx"


class TestSoftwareConfig:
    def test_config_creation(self) -> None:
        config = SoftwareConfig(
            software=SoftwareType.TOPAZ_VIDEO_AI,
            executable_path="C:/Topaz/topazcli.exe",
            max_concurrent_tasks=2,
        )
        assert config.software == SoftwareType.TOPAZ_VIDEO_AI
        assert config.enabled is True
        assert config.max_concurrent_tasks == 2

    def test_config_to_dict(self) -> None:
        config = SoftwareConfig(
            software=SoftwareType.SILHOUETTE,
            executable_path="/opt/silhouette/Silhouette",
        )
        d = config.to_dict()
        assert d["software"] == "silhouette"
        assert d["executable_path"] == "/opt/silhouette/Silhouette"


# ============================================================================
# Base Adapter Tests
# ============================================================================

class ConcreteAdapter(BaseSoftwareAdapter):
    """用于测试的具体适配器实现"""

    def _initialize_capabilities(self) -> SoftwareCapabilities:
        return SoftwareCapabilities(
            software=self.software_type,
            capabilities={SoftwareCapability.COMPOSITING},
            scriptable=True,
        )

    def connect(self) -> bool:
        self._status = ConnectionStatus.CONNECTING
        self._set_connected()
        return True

    def disconnect(self) -> bool:
        self._status = ConnectionStatus.DISCONNECTED
        return True

    def health_check(self) -> bool:
        return self._status == ConnectionStatus.CONNECTED

    def execute_task(self, task: Task) -> Any:
        self._mark_task_start()
        try:
            result = {"executed": True, "task": task.task_type}
            return result
        finally:
            self._mark_task_end()


class TestBaseSoftwareAdapter:
    """BaseSoftwareAdapter 测试"""

    def _make_adapter(self) -> ConcreteAdapter:
        config = SoftwareConfig(
            software=SoftwareType.AFTER_EFFECTS,
            max_concurrent_tasks=2,
        )
        return ConcreteAdapter(config)

    def test_initial_status(self) -> None:
        adapter = self._make_adapter()
        status = adapter.get_status()
        assert status.status == ConnectionStatus.DISCONNECTED

    def test_connect(self) -> None:
        adapter = self._make_adapter()
        assert adapter.connect() is True
        status = adapter.get_status()
        assert status.status == ConnectionStatus.CONNECTED

    def test_disconnect(self) -> None:
        adapter = self._make_adapter()
        adapter.connect()
        assert adapter.disconnect() is True
        assert adapter.get_status().status == ConnectionStatus.DISCONNECTED

    def test_health_check(self) -> None:
        adapter = self._make_adapter()
        assert adapter.health_check() is False
        adapter.connect()
        assert adapter.health_check() is True

    def test_execute_task(self) -> None:
        adapter = self._make_adapter()
        adapter.connect()
        task = Task(task_type="test_task")
        result = adapter.execute_task(task)
        assert result["executed"] is True

    def test_can_accept_task_when_connected(self) -> None:
        adapter = self._make_adapter()
        assert adapter.can_accept_task() is False  # not connected
        adapter.connect()
        assert adapter.can_accept_task() is True

    def test_capabilities(self) -> None:
        adapter = self._make_adapter()
        caps = adapter.get_capabilities()
        assert caps.has_capability(SoftwareCapability.COMPOSITING)
        assert caps.scriptable is True

    def test_task_counting(self) -> None:
        adapter = self._make_adapter()
        adapter.connect()
        task = Task(task_type="test")
        adapter.execute_task(task)
        # After task completes, active tasks should be 0
        assert adapter.get_status().active_tasks == 0


# ============================================================================
# Registry Tests
# ============================================================================

class TestSoftwareRegistry:
    """SoftwareRegistry 测试"""

    def test_register_and_get(self) -> None:
        registry = SoftwareRegistry()
        config = SoftwareConfig(software=SoftwareType.AFTER_EFFECTS)
        adapter = ConcreteAdapter(config)
        registry.register(SoftwareType.AFTER_EFFECTS, adapter)
        
        retrieved = registry.get(SoftwareType.AFTER_EFFECTS)
        assert retrieved is adapter

    def test_get_unregistered_returns_none(self) -> None:
        registry = SoftwareRegistry()
        assert registry.get(SoftwareType.BLENDER) is None

    def test_list_available(self) -> None:
        registry = SoftwareRegistry()
        registry.register(SoftwareType.AFTER_EFFECTS, ConcreteAdapter(
            SoftwareConfig(software=SoftwareType.AFTER_EFFECTS)
        ))
        registry.register(SoftwareType.FFMPEG, ConcreteAdapter(
            SoftwareConfig(software=SoftwareType.FFMPEG)
        ))
        available = registry.list_available()
        assert SoftwareType.AFTER_EFFECTS in available
        assert SoftwareType.FFMPEG in available
        assert len(available) == 2

    def test_unregister(self) -> None:
        registry = SoftwareRegistry()
        config = SoftwareConfig(software=SoftwareType.BLENDER)
        adapter = ConcreteAdapter(config)
        registry.register(SoftwareType.BLENDER, adapter)
        
        registry.unregister(SoftwareType.BLENDER)
        assert registry.get(SoftwareType.BLENDER) is None

    def test_has_software(self) -> None:
        registry = SoftwareRegistry()
        config = SoftwareConfig(software=SoftwareType.SILHOUETTE)
        adapter = ConcreteAdapter(config)
        registry.register(SoftwareType.SILHOUETTE, adapter)
        
        assert registry.has(SoftwareType.SILHOUETTE) is True
        assert registry.has(SoftwareType.PHOTOSHOP) is False

    def test_connect_all(self) -> None:
        registry = SoftwareRegistry()
        for sw in [SoftwareType.AFTER_EFFECTS, SoftwareType.FFMPEG]:
            registry.register(sw, ConcreteAdapter(SoftwareConfig(software=sw)))
        
        results = registry.connect_all()
        assert results[SoftwareType.AFTER_EFFECTS] is True
        assert results[SoftwareType.FFMPEG] is True

    def test_disconnect_all(self) -> None:
        registry = SoftwareRegistry()
        for sw in [SoftwareType.AFTER_EFFECTS, SoftwareType.FFMPEG]:
            registry.register(sw, ConcreteAdapter(SoftwareConfig(software=sw)))
        
        registry.connect_all()
        results = registry.disconnect_all()
        assert all(v is True for v in results.values())

    def test_get_by_capability(self) -> None:
        registry = SoftwareRegistry()
        # AE has compositing
        registry.register(SoftwareType.AFTER_EFFECTS, ConcreteAdapter(
            SoftwareConfig(software=SoftwareType.AFTER_EFFECTS)
        ))
        # FFmpeg - override capabilities
        ffmpeg_adapter = ConcreteAdapter(
            SoftwareConfig(software=SoftwareType.FFMPEG)
        )
        registry.register(SoftwareType.FFMPEG, ffmpeg_adapter)
        
        # Both have COMPOSITING from ConcreteAdapter
        matching = registry.get_by_capability(SoftwareCapability.COMPOSITING)
        assert len(matching) == 2

    def test_duplicate_register_raises(self) -> None:
        registry = SoftwareRegistry()
        config = SoftwareConfig(software=SoftwareType.AFTER_EFFECTS)
        registry.register(SoftwareType.AFTER_EFFECTS, ConcreteAdapter(config))
        
        with pytest.raises(ValueError):
            registry.register(SoftwareType.AFTER_EFFECTS, ConcreteAdapter(config))

    def test_empty_registry(self) -> None:
        registry = SoftwareRegistry()
        assert registry.list_available() == []
        assert registry.connect_all() == {}
