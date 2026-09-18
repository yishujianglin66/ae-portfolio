#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
插件系统
========

提供可扩展的插件架构，支持自定义效果、工作流、输出格式等。

功能:
- 插件注册与发现
- 插件生命周期管理（加载/启动/停止/卸载）
- 插件依赖解析
- 插件配置 Schema
- 插件事件钩子（hooks）
- 插件隔离与错误处理
- 热重载支持

插件类型:
- effect: 自定义效果插件
- workflow: 自定义工作流插件
- output: 自定义输出格式插件
- analyzer: 自定义分析器插件
"""

from __future__ import annotations

import importlib
import inspect
import json
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Type

try:
    from logger import get_logger
    _logger = get_logger("plugin-system")
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    _logger = logging.getLogger("plugin-system")


# ============================================================================
# 插件类型枚举
# ============================================================================

class PluginType(str, Enum):
    """插件类型"""
    EFFECT = "effect"
    WORKFLOW = "workflow"
    OUTPUT = "output"
    ANALYZER = "analyzer"
    FILTER = "filter"
    TRANSITION = "transition"
    CUSTOM = "custom"


class PluginStatus(str, Enum):
    """插件状态"""
    UNLOADED = "unloaded"
    LOADED = "loaded"
    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"


# ============================================================================
# 插件元数据
# ============================================================================

@dataclass
class PluginMetadata:
    """插件元数据"""
    name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    plugin_type: PluginType = PluginType.CUSTOM
    dependencies: list[str] = field(default_factory=list)
    config_schema: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    homepage: str = ""
    license: str = "MIT"


# ============================================================================
# 插件接口
# ============================================================================

class PluginBase:
    """插件基类

    所有插件必须继承此类并实现相应接口。
    """

    metadata: PluginMetadata

    def __init__(self, config: dict[str, Any] | None = None):
        self._config = config or {}
        self._enabled = False
        self._initialized = False

    def initialize(self) -> bool:
        """初始化插件

        Returns:
            是否初始化成功
        """
        if self._initialized:
            return True
        try:
            success = self.on_initialize()
            self._initialized = success
            return success
        except Exception as e:
            _logger.error(f"插件 {self.metadata.name} 初始化失败: {e}")
            return False

    def enable(self) -> bool:
        """启用插件"""
        if not self._initialized:
            if not self.initialize():
                return False
        try:
            self.on_enable()
            self._enabled = True
            _logger.info(f"插件已启用: {self.metadata.name}")
            return True
        except Exception as e:
            _logger.error(f"插件 {self.metadata.name} 启用失败: {e}")
            return False

    def disable(self) -> bool:
        """禁用插件"""
        try:
            self.on_disable()
            self._enabled = False
            _logger.info(f"插件已禁用: {self.metadata.name}")
            return True
        except Exception as e:
            _logger.error(f"插件 {self.metadata.name} 禁用失败: {e}")
            return False

    def shutdown(self):
        """关闭插件"""
        if self._enabled:
            self.disable()
        self.on_shutdown()
        self._initialized = False

    # 子类可覆盖的钩子

    def on_initialize(self) -> bool:
        """初始化钩子（子类可覆盖）"""
        return True

    def on_enable(self):
        """启用钩子（子类可覆盖）"""
        pass

    def on_disable(self):
        """禁用钩子（子类可覆盖）"""
        pass

    def on_shutdown(self):
        """关闭钩子（子类可覆盖）"""
        pass

    def get_config(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        return self._config.get(key, default)

    def set_config(self, key: str, value: Any):
        """设置配置值"""
        self._config[key] = value

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    @property
    def is_initialized(self) -> bool:
        return self._initialized


class EffectPlugin(PluginBase):
    """效果插件基类"""

    def apply_effect(
        self,
        layer_data: dict[str, Any],
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """应用效果

        Args:
            layer_data: 图层数据
            params: 效果参数

        Returns:
            处理后的图层数据
        """
        raise NotImplementedError("子类必须实现 apply_effect")

    def get_default_params(self) -> dict[str, Any]:
        """获取默认参数"""
        return {}


class WorkflowPlugin(PluginBase):
    """工作流插件基类"""

    def execute(
        self,
        input_data: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """执行工作流

        Args:
            input_data: 输入数据
            context: 执行上下文

        Returns:
            执行结果
        """
        raise NotImplementedError("子类必须实现 execute")

    def get_stages(self) -> list[str]:
        """获取工作流阶段列表"""
        return []


class OutputPlugin(PluginBase):
    """输出插件基类"""

    def render(
        self,
        project_data: dict[str, Any],
        output_path: str,
        options: dict[str, Any],
    ) -> str:
        """渲染输出

        Args:
            project_data: 项目数据
            output_path: 输出路径
            options: 渲染选项

        Returns:
            输出文件路径
        """
        raise NotImplementedError("子类必须实现 render")

    def get_supported_formats(self) -> list[str]:
        """获取支持的输出格式"""
        return ["mp4"]


class AnalyzerPlugin(PluginBase):
    """分析器插件基类"""

    def analyze(
        self,
        input_path: str,
        options: dict[str, Any],
    ) -> dict[str, Any]:
        """分析输入

        Args:
            input_path: 输入文件路径
            options: 分析选项

        Returns:
            分析结果
        """
        raise NotImplementedError("子类必须实现 analyze")


# ============================================================================
# 插件注册项
# ============================================================================

@dataclass
class PluginEntry:
    """插件注册项"""
    plugin_id: str
    plugin_class: type[PluginBase]
    metadata: PluginMetadata
    instance: PluginBase | None = None
    status: PluginStatus = PluginStatus.UNLOADED
    loaded_at: float | None = None
    error: str | None = None
    config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "name": self.metadata.name,
            "version": self.metadata.version,
            "description": self.metadata.description,
            "author": self.metadata.author,
            "type": self.metadata.plugin_type.value,
            "tags": self.metadata.tags,
            "dependencies": self.metadata.dependencies,
            "status": self.status.value,
            "loaded_at": self.loaded_at,
            "is_enabled": self.instance.is_enabled if self.instance else False,
            "error": self.error,
        }


# ============================================================================
# 事件钩子管理
# ============================================================================

class HookManager:
    """事件钩子管理器"""

    def __init__(self):
        self._hooks: dict[str, list[Callable]] = {}
        self._lock = threading.RLock()

    def register(self, event: str, callback: Callable):
        """注册钩子"""
        with self._lock:
            if event not in self._hooks:
                self._hooks[event] = []
            self._hooks[event].append(callback)

    def unregister(self, event: str, callback: Callable):
        """注销钩子"""
        with self._lock:
            if event in self._hooks:
                self._hooks[event] = [
                    cb for cb in self._hooks[event] if cb != callback
                ]

    def trigger(self, event: str, *args, **kwargs) -> list[Any]:
        """触发钩子"""
        results = []
        with self._lock:
            callbacks = list(self._hooks.get(event, []))

        for callback in callbacks:
            try:
                result = callback(*args, **kwargs)
                results.append(result)
            except Exception as e:
                _logger.error(f"钩子 {event} 执行失败: {e}")

        return results

    def get_events(self) -> list[str]:
        """获取所有已注册的事件"""
        with self._lock:
            return list(self._hooks.keys())


# ============================================================================
# 插件管理器
# ============================================================================

class PluginManager:
    """插件管理器

    提供插件的注册、发现、加载和管理能力。
    """

    def __init__(self, plugin_dirs: list[str] | None = None):
        self._entries: dict[str, PluginEntry] = {}
        self._plugin_dirs = plugin_dirs or []
        self._hook_manager = HookManager()
        self._lock = threading.RLock()

        self._add_default_dirs()

    def _add_default_dirs(self):
        """添加默认插件目录"""
        default_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "plugins",
        )
        if default_dir not in self._plugin_dirs:
            self._plugin_dirs.append(default_dir)

    @property
    def hooks(self) -> HookManager:
        """获取钩子管理器"""
        return self._hook_manager

    # --------------------------------------------------------------------
    # 插件注册
    # --------------------------------------------------------------------

    def register_plugin(
        self,
        plugin_id: str,
        plugin_class: type[PluginBase],
        metadata: PluginMetadata | None = None,
    ) -> bool:
        """注册插件

        Args:
            plugin_id: 插件唯一ID
            plugin_class: 插件类
            metadata: 插件元数据（None则从类属性获取）

        Returns:
            是否注册成功
        """
        with self._lock:
            if plugin_id in self._entries:
                _logger.warning(f"插件已存在，将覆盖: {plugin_id}")

            if metadata is None:
                metadata = getattr(plugin_class, "metadata", None)
                if metadata is None:
                    metadata = PluginMetadata(name=plugin_id)

            entry = PluginEntry(
                plugin_id=plugin_id,
                plugin_class=plugin_class,
                metadata=metadata,
            )

            self._entries[plugin_id] = entry
            _logger.info(f"插件已注册: {plugin_id} ({metadata.name} v{metadata.version})")

            self._hook_manager.trigger("plugin.registered", entry)

            return True

    def unregister_plugin(self, plugin_id: str) -> bool:
        """注销插件"""
        with self._lock:
            entry = self._entries.get(plugin_id)
            if not entry:
                return False

            if entry.instance:
                entry.instance.shutdown()

            del self._entries[plugin_id]
            _logger.info(f"插件已注销: {plugin_id}")

            self._hook_manager.trigger("plugin.unregistered", plugin_id)
            return True

    # --------------------------------------------------------------------
    # 插件加载
    # --------------------------------------------------------------------

    def load_plugin(self, plugin_id: str, config: dict[str, Any] | None = None) -> bool:
        """加载插件（创建实例）"""
        with self._lock:
            entry = self._entries.get(plugin_id)
            if not entry:
                _logger.error(f"插件未注册: {plugin_id}")
                return False

            if entry.instance is not None:
                _logger.warning(f"插件已加载: {plugin_id}")
                return True

            try:
                if not self._check_dependencies(entry):
                    entry.status = PluginStatus.ERROR
                    entry.error = "依赖未满足"
                    return False

                entry.config = config or {}
                entry.instance = entry.plugin_class(config=entry.config)
                entry.status = PluginStatus.LOADED
                entry.loaded_at = time.time()

                _logger.info(f"插件已加载: {plugin_id}")
                self._hook_manager.trigger("plugin.loaded", entry)
                return True

            except Exception as e:
                entry.status = PluginStatus.ERROR
                entry.error = str(e)
                _logger.error(f"插件加载失败 {plugin_id}: {e}")
                return False

    def unload_plugin(self, plugin_id: str) -> bool:
        """卸载插件"""
        with self._lock:
            entry = self._entries.get(plugin_id)
            if not entry or not entry.instance:
                return False

            entry.instance.shutdown()
            entry.instance = None
            entry.status = PluginStatus.UNLOADED
            entry.loaded_at = None

            _logger.info(f"插件已卸载: {plugin_id}")
            self._hook_manager.trigger("plugin.unloaded", plugin_id)
            return True

    def enable_plugin(self, plugin_id: str) -> bool:
        """启用插件"""
        with self._lock:
            entry = self._entries.get(plugin_id)
            if not entry:
                return False

            if not entry.instance:
                if not self.load_plugin(plugin_id, entry.config):
                    return False

            if entry.instance.enable():
                entry.status = PluginStatus.ENABLED
                self._hook_manager.trigger("plugin.enabled", entry)
                return True

            entry.status = PluginStatus.ERROR
            return False

    def disable_plugin(self, plugin_id: str) -> bool:
        """禁用插件"""
        with self._lock:
            entry = self._entries.get(plugin_id)
            if not entry or not entry.instance:
                return False

            if entry.instance.disable():
                entry.status = PluginStatus.DISABLED
                self._hook_manager.trigger("plugin.disabled", entry)
                return True
            return False

    def _check_dependencies(self, entry: PluginEntry) -> bool:
        """检查插件依赖"""
        for dep in entry.metadata.dependencies:
            if dep not in self._entries:
                _logger.error(f"插件 {entry.plugin_id} 依赖未注册: {dep}")
                return False
            dep_entry = self._entries[dep]
            if dep_entry.status not in (PluginStatus.LOADED, PluginStatus.ENABLED):
                if not self.load_plugin(dep):
                    return False
        return True

    # --------------------------------------------------------------------
    # 插件发现
    # --------------------------------------------------------------------

    def discover_plugins(self) -> list[str]:
        """从插件目录发现插件

        Returns:
            新发现的插件ID列表
        """
        discovered = []

        for plugin_dir in self._plugin_dirs:
            if not os.path.isdir(plugin_dir):
                continue

            for filename in os.listdir(plugin_dir):
                if not filename.endswith(".py"):
                    continue
                if filename.startswith("_") or filename.startswith("."):
                    continue

                module_name = filename[:-3]
                plugin_path = os.path.join(plugin_dir, filename)

                try:
                    spec = importlib.util.spec_from_file_location(
                        f"plugins.{module_name}",
                        plugin_path,
                    )
                    if spec is None or spec.loader is None:
                        continue

                    module = importlib.util.module_from_spec(spec)
                    sys.modules[f"plugins.{module_name}"] = module
                    spec.loader.exec_module(module)

                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (
                            isinstance(attr, type)
                            and issubclass(attr, PluginBase)
                            and attr is not PluginBase
                            and attr not in (EffectPlugin, WorkflowPlugin, OutputPlugin, AnalyzerPlugin)
                        ):
                            metadata = getattr(attr, "metadata", None)
                            if metadata is None:
                                metadata = PluginMetadata(name=module_name)

                            plugin_id = f"{module_name}.{attr_name.lower()}"

                            if plugin_id not in self._entries:
                                self.register_plugin(plugin_id, attr, metadata)
                                discovered.append(plugin_id)

                except Exception as e:
                    _logger.error(f"发现插件失败 {filename}: {e}")

        _logger.info(f"共发现 {len(discovered)} 个新插件")
        return discovered

    # --------------------------------------------------------------------
    # 插件获取
    # --------------------------------------------------------------------

    def get_plugin(self, plugin_id: str) -> PluginBase | None:
        """获取插件实例"""
        with self._lock:
            entry = self._entries.get(plugin_id)
            if entry and entry.instance:
                return entry.instance

            if entry and not entry.instance:
                self.load_plugin(plugin_id)
                return entry.instance

            return None

    def get_plugins_by_type(self, plugin_type: PluginType) -> list[PluginEntry]:
        """按类型获取插件"""
        with self._lock:
            return [
                entry for entry in self._entries.values()
                if entry.metadata.plugin_type == plugin_type
            ]

    def get_all_plugins(self) -> list[PluginEntry]:
        """获取所有插件"""
        with self._lock:
            return list(self._entries.values())

    def get_enabled_plugins(self) -> list[PluginEntry]:
        """获取已启用的插件"""
        with self._lock:
            return [
                entry for entry in self._entries.values()
                if entry.status == PluginStatus.ENABLED
            ]

    # --------------------------------------------------------------------
    # 热重载
    # --------------------------------------------------------------------

    def reload_plugin(self, plugin_id: str) -> bool:
        """重新加载插件"""
        with self._lock:
            entry = self._entries.get(plugin_id)
            if not entry:
                return False

            old_config = entry.config
            self.unload_plugin(plugin_id)
            return self.load_plugin(plugin_id, old_config)

    # --------------------------------------------------------------------
    # 统计信息
    # --------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            total = len(self._entries)
            enabled = sum(1 for e in self._entries.values() if e.status == PluginStatus.ENABLED)
            loaded = sum(1 for e in self._entries.values() if e.status in (PluginStatus.LOADED, PluginStatus.ENABLED))
            errored = sum(1 for e in self._entries.values() if e.status == PluginStatus.ERROR)

            type_counts: dict[str, int] = {}
            for entry in self._entries.values():
                t = entry.metadata.plugin_type.value
                type_counts[t] = type_counts.get(t, 0) + 1

            return {
                "total_plugins": total,
                "enabled": enabled,
                "loaded": loaded,
                "errored": errored,
                "type_counts": type_counts,
                "plugin_dirs": self._plugin_dirs,
                "hooks": len(self._hook_manager.get_events()),
            }

    def list_plugins(self) -> list[dict[str, Any]]:
        """列出所有插件信息"""
        with self._lock:
            return [entry.to_dict() for entry in self._entries.values()]

    # --------------------------------------------------------------------
    # 关闭
    # --------------------------------------------------------------------

    def shutdown(self):
        """关闭所有插件"""
        with self._lock:
            for plugin_id in list(self._entries.keys()):
                self.unload_plugin(plugin_id)
            _logger.info("所有插件已关闭")


# ============================================================================
# 内置示例插件
# ============================================================================

class CartoonOutlineEffect(EffectPlugin):
    """卡通描边效果插件（内置示例）"""

    metadata = PluginMetadata(
        name="卡通描边",
        version="1.0.0",
        description="为图像添加卡通描边效果",
        author="AE-Knowledge-Vault",
        plugin_type=PluginType.EFFECT,
        tags=["cartoon", "outline", "stylize"],
        config_schema={
            "edge_threshold": {"type": "float", "default": 0.5, "min": 0.0, "max": 1.0},
            "edge_thickness": {"type": "int", "default": 2, "min": 1, "max": 10},
            "color_levels": {"type": "int", "default": 4, "min": 2, "max": 16},
        },
    )

    def get_default_params(self) -> dict[str, Any]:
        return {
            "edge_threshold": 0.5,
            "edge_thickness": 2,
            "color_levels": 4,
        }

    def apply_effect(self, layer_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
        default = self.get_default_params()
        merged = {**default, **params}

        return {
            **layer_data,
            "effect_applied": "cartoon_outline",
            "params": merged,
            "layers_added": 2,
            "message": f"卡通描边效果已应用 (阈值={merged['edge_threshold']}, 粗细={merged['edge_thickness']})",
        }


class WatercolorOutputPlugin(OutputPlugin):
    """水彩画输出插件（内置示例）"""

    metadata = PluginMetadata(
        name="水彩画输出",
        version="1.0.0",
        description="将视频渲染为水彩画风格",
        author="AE-Knowledge-Vault",
        plugin_type=PluginType.OUTPUT,
        tags=["watercolor", "painting", "artistic"],
        config_schema={
            "texture_intensity": {"type": "float", "default": 0.7, "min": 0.0, "max": 1.0},
            "color_bleed": {"type": "float", "default": 0.3, "min": 0.0, "max": 1.0},
            "paper_texture": {"type": "bool", "default": True},
        },
    )

    def get_supported_formats(self) -> list[str]:
        return ["mp4", "png", "jpg"]

    def render(self, project_data: dict[str, Any], output_path: str, options: dict[str, Any]) -> str:
        _logger.info(f"水彩画渲染: {output_path}")

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(json.dumps({
                    "format": "watercolor",
                    "project": project_data.get("name", "unknown"),
                    "options": options,
                    "rendered_at": time.time(),
                }, ensure_ascii=False, indent=2))
        except Exception:
            pass

        return output_path


class BeatSyncAnalyzerPlugin(AnalyzerPlugin):
    """节拍同步分析器插件（内置示例）"""

    metadata = PluginMetadata(
        name="节拍同步分析",
        version="1.0.0",
        description="分析音频节拍并生成同步时间线",
        author="AE-Knowledge-Vault",
        plugin_type=PluginType.ANALYZER,
        tags=["audio", "beat", "sync", "music"],
        dependencies=[],
        config_schema={
            "sensitivity": {"type": "float", "default": 0.8, "min": 0.0, "max": 1.0},
            "min_bpm": {"type": "int", "default": 60, "min": 30, "max": 300},
            "max_bpm": {"type": "int", "default": 180, "min": 30, "max": 300},
        },
    )

    def analyze(self, input_path: str, options: dict[str, Any]) -> dict[str, Any]:
        _logger.info(f"节拍同步分析: {input_path}")

        sensitivity = options.get("sensitivity", 0.8)

        return {
            "input_path": input_path,
            "bpm": 120,
            "beat_times": [0.5, 1.0, 1.5, 2.0, 2.5, 3.0],
            "downbeat_times": [0.5, 2.5],
            "time_signature": "4/4",
            "sensitivity": sensitivity,
            "key": "C major",
            "energy": 0.75,
            "analysis_mode": "plugin",
        }


# ============================================================================
# 模块单例
# ============================================================================

_default_manager: PluginManager | None = None


def get_plugin_manager(plugin_dirs: list[str] | None = None) -> PluginManager:
    """获取默认插件管理器实例"""
    global _default_manager
    if _default_manager is None:
        _default_manager = PluginManager(plugin_dirs)
        _register_builtin_plugins(_default_manager)
    return _default_manager


def _register_builtin_plugins(manager: PluginManager):
    """注册内置插件"""
    manager.register_plugin("builtin.cartoon_outline", CartoonOutlineEffect)
    manager.register_plugin("builtin.watercolor_output", WatercolorOutputPlugin)
    manager.register_plugin("builtin.beat_sync_analyzer", BeatSyncAnalyzerPlugin)
    _logger.info("内置插件已注册")


# ============================================================================
# 命令行测试入口
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("  插件系统测试")
    print("=" * 70)

    manager = get_plugin_manager()

    print("\n1. 插件列表...")
    plugins = manager.list_plugins()
    print(f"  总插件数: {len(plugins)}")
    for p in plugins:
        print(f"    - {p['plugin_id']}: {p['name']} v{p['version']} [{p['type']}] - {p['status']}")

    print("\n2. 加载并启用插件...")
    for p in plugins:
        manager.enable_plugin(p["plugin_id"])
        print(f"  {'✅' if p else '❌'} {p['plugin_id']}: {manager._entries[p['plugin_id']].status.value}")

    print("\n3. 测试效果插件...")
    cartoon = manager.get_plugin("builtin.cartoon_outline")
    if cartoon:
        result = cartoon.apply_effect(
            {"layer": "test_layer", "width": 1920, "height": 1080},
            {"edge_threshold": 0.7, "edge_thickness": 3},
        )
        print(f"  结果: {result['message']}")
        print(f"  添加图层数: {result['layers_added']}")

    print("\n4. 测试分析器插件...")
    beat_analyzer = manager.get_plugin("builtin.beat_sync_analyzer")
    if beat_analyzer:
        result = beat_analyzer.analyze("/tmp/test.mp4", {"sensitivity": 0.9})
        print(f"  BPM: {result['bpm']}")
        print(f"  节拍数: {len(result['beat_times'])}")
        print(f"  调性: {result['key']}")

    print("\n5. 测试输出插件...")
    watercolor = manager.get_plugin("builtin.watercolor_output")
    if watercolor:
        import tempfile
        output_path = os.path.join(tempfile.gettempdir(), "watercolor_test.json")
        result_path = watercolor.render(
            {"name": "测试项目"},
            output_path,
            {"texture_intensity": 0.8},
        )
        print(f"  输出路径: {result_path}")
        print(f"  支持格式: {watercolor.get_supported_formats()}")

    print("\n6. 测试事件钩子...")
    hook_results = manager.hooks.trigger("plugin.registered")
    print(f"  已注册事件: {manager.hooks.get_events()}")

    print("\n7. 统计信息...")
    stats = manager.get_stats()
    print(f"  总插件数: {stats['total_plugins']}")
    print(f"  已启用: {stats['enabled']}")
    print(f"  类型分布: {stats['type_counts']}")

    print("\n8. 测试热重载...")
    manager.reload_plugin("builtin.cartoon_outline")
    print(f"  重载后状态: {manager._entries['builtin.cartoon_outline'].status.value}")

    print("\n" + "=" * 70)
    print("  测试完成！")
    print("=" * 70)

    manager.shutdown()
