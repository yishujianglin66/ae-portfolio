"""
Photoshop 适配器层
==================

提供 Photoshop 的统一抽象接口，支持多种连接方式（MCP、Puppet Engine 等）。

设计模式：适配器模式 + 策略模式

使用示例：
    from ae.adapters.ps_adapter import MCPClientPSAdapter, BasePSAdapter

    adapter = MCPClientPSAdapter()
    doc = adapter.create_document("MyDoc", 1920, 1080)
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union

from ae.ps_mcp_client import BlendMode, DocumentInfo, LayerInfo, PSConnectionError, PSMDPClient

logger = logging.getLogger(__name__)


class BasePSAdapter(ABC):
    """Photoshop 适配器抽象基类。

    定义 Photoshop 操作的统一接口，所有具体适配器必须实现这些方法。
    """

    name: str = "ps_base"
    supports_gui: bool = True
    requires_gui: bool = True

    @abstractmethod
    def create_document(
        self,
        name: str,
        width: int = 1920,
        height: int = 1080,
        resolution: float = 72.0,
        color_mode: str = "RGB",
        background_color: list[float] | None = None,
    ) -> dict[str, Any]:
        """创建新文档。"""
        pass

    @abstractmethod
    def open_document(self, file_path: str) -> dict[str, Any]:
        """打开文档。"""
        pass

    @abstractmethod
    def close_document(self, document_name: str, save_changes: bool = False) -> dict[str, Any]:
        """关闭文档。"""
        pass

    @abstractmethod
    def save_document(self, document_name: str, file_path: str | None = None) -> dict[str, Any]:
        """保存文档。"""
        pass

    @abstractmethod
    def export_document(
        self,
        document_name: str,
        file_path: str,
        format: str = "PNG",
        quality: int = 100,
    ) -> dict[str, Any]:
        """导出文档。"""
        pass

    @abstractmethod
    def create_layer(
        self,
        document_name: str,
        layer_name: str | None = None,
        layer_type: str = "pixel",
    ) -> dict[str, Any]:
        """创建图层。"""
        pass

    @abstractmethod
    def delete_layer(self, document_name: str, layer_name: str) -> dict[str, Any]:
        """删除图层。"""
        pass

    @abstractmethod
    def duplicate_layer(
        self,
        document_name: str,
        layer_name: str,
        new_name: str | None = None,
    ) -> dict[str, Any]:
        """复制图层。"""
        pass

    @abstractmethod
    def set_layer_properties(
        self,
        document_name: str,
        layer_name: str,
        properties: dict[str, Any],
    ) -> dict[str, Any]:
        """设置图层属性。"""
        pass

    @abstractmethod
    def set_blend_mode(
        self,
        document_name: str,
        layer_name: str,
        blend_mode: Union[BlendMode, str],
    ) -> dict[str, Any]:
        """设置图层混合模式。"""
        pass

    @abstractmethod
    def apply_filter(
        self,
        document_name: str,
        layer_name: str,
        filter_name: str,
        properties: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """应用滤镜。"""
        pass

    @abstractmethod
    def remove_filter(self, document_name: str, layer_name: str, filter_name: str) -> dict[str, Any]:
        """移除滤镜。"""
        pass

    @abstractmethod
    def create_selection(
        self,
        document_name: str,
        top: int = 0,
        left: int = 0,
        width: int = 100,
        height: int = 100,
    ) -> dict[str, Any]:
        """创建选区。"""
        pass

    @abstractmethod
    def fill_selection(
        self,
        document_name: str,
        color: list[float],
        blend_mode: str = "NORMAL",
        opacity: int = 100,
    ) -> dict[str, Any]:
        """填充选区。"""
        pass

    @abstractmethod
    def get_document_info(self) -> dict[str, Any]:
        """获取当前文档信息。"""
        pass

    @abstractmethod
    def list_documents(self) -> list[DocumentInfo]:
        """列出所有打开的文档。"""
        pass

    @abstractmethod
    def get_layer_info(
        self,
        document_name: str,
        layer_name: str | None = None,
    ) -> Union[LayerInfo, list[LayerInfo]]:
        """获取图层信息。"""
        pass

    @abstractmethod
    def ping(self) -> dict[str, Any]:
        """检测 Photoshop 是否存活。"""
        pass

    @abstractmethod
    def is_alive(self) -> bool:
        """检查 Photoshop 是否存活。"""
        pass

    @abstractmethod
    def execute_script(self, script_content: str) -> dict[str, Any]:
        """执行 ExtendScript 脚本。"""
        pass

    @abstractmethod
    def undo(self) -> dict[str, Any]:
        """撤销上一步操作。"""
        pass

    @abstractmethod
    def redo(self) -> dict[str, Any]:
        """重做上一步操作。"""
        pass


class MCPClientPSAdapter(BasePSAdapter):
    """基于 MCP 客户端的 Photoshop 适配器。

    使用 file polling 机制与 Photoshop 通信，支持所有核心 Photoshop 操作。
    """

    name = "ps_mcp"

    def __init__(self, client: PSMDPClient | None = None, **client_kwargs) -> None:
        """初始化 MCP 客户端适配器。

        Args:
            client: 已初始化的 PSMDPClient 实例
            client_kwargs: 创建 PSMDPClient 时的参数
        """
        self._client: PSMDPClient | None = client
        self._client_kwargs = client_kwargs
        self._client_lock = None

    def _ensure_client(self) -> PSMDPClient:
        """确保客户端已初始化。"""
        if self._client is None:
            self._client = PSMDPClient(**self._client_kwargs)
        return self._client

    def create_document(
        self,
        name: str,
        width: int = 1920,
        height: int = 1080,
        resolution: float = 72.0,
        color_mode: str = "RGB",
        background_color: list[float] | None = None,
    ) -> dict[str, Any]:
        return self._ensure_client().create_document(
            name=name,
            width=width,
            height=height,
            resolution=resolution,
            color_mode=color_mode,
            background_color=background_color,
        )

    def open_document(self, file_path: str) -> dict[str, Any]:
        return self._ensure_client().open_document(file_path)

    def close_document(self, document_name: str, save_changes: bool = False) -> dict[str, Any]:
        return self._ensure_client().close_document(document_name, save_changes)

    def save_document(self, document_name: str, file_path: str | None = None) -> dict[str, Any]:
        return self._ensure_client().save_document(document_name, file_path)

    def export_document(
        self,
        document_name: str,
        file_path: str,
        format: str = "PNG",
        quality: int = 100,
    ) -> dict[str, Any]:
        return self._ensure_client().export_document(
            document_name=document_name,
            file_path=file_path,
            format=format,
            quality=quality,
        )

    def create_layer(
        self,
        document_name: str,
        layer_name: str | None = None,
        layer_type: str = "pixel",
    ) -> dict[str, Any]:
        return self._ensure_client().create_layer(
            document_name=document_name,
            layer_name=layer_name,
            layer_type=layer_type,
        )

    def delete_layer(self, document_name: str, layer_name: str) -> dict[str, Any]:
        return self._ensure_client().delete_layer(document_name, layer_name)

    def duplicate_layer(
        self,
        document_name: str,
        layer_name: str,
        new_name: str | None = None,
    ) -> dict[str, Any]:
        return self._ensure_client().duplicate_layer(document_name, layer_name, new_name)

    def set_layer_properties(
        self,
        document_name: str,
        layer_name: str,
        properties: dict[str, Any],
    ) -> dict[str, Any]:
        return self._ensure_client().set_layer_properties(document_name, layer_name, properties)

    def set_blend_mode(
        self,
        document_name: str,
        layer_name: str,
        blend_mode: Union[BlendMode, str],
    ) -> dict[str, Any]:
        return self._ensure_client().set_blend_mode(document_name, layer_name, blend_mode)

    def apply_filter(
        self,
        document_name: str,
        layer_name: str,
        filter_name: str,
        properties: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._ensure_client().apply_filter(
            document_name=document_name,
            layer_name=layer_name,
            filter_name=filter_name,
            properties=properties,
        )

    def remove_filter(self, document_name: str, layer_name: str, filter_name: str) -> dict[str, Any]:
        return self._ensure_client().remove_filter(document_name, layer_name, filter_name)

    def create_selection(
        self,
        document_name: str,
        top: int = 0,
        left: int = 0,
        width: int = 100,
        height: int = 100,
    ) -> dict[str, Any]:
        return self._ensure_client().create_selection(
            document_name=document_name,
            top=top,
            left=left,
            width=width,
            height=height,
        )

    def fill_selection(
        self,
        document_name: str,
        color: list[float],
        blend_mode: str = "NORMAL",
        opacity: int = 100,
    ) -> dict[str, Any]:
        return self._ensure_client().fill_selection(document_name, color, blend_mode, opacity)

    def get_document_info(self) -> dict[str, Any]:
        return self._ensure_client().get_document_info()

    def list_documents(self) -> list[DocumentInfo]:
        return self._ensure_client().list_documents()

    def get_layer_info(
        self,
        document_name: str,
        layer_name: str | None = None,
    ) -> Union[LayerInfo, list[LayerInfo]]:
        return self._ensure_client().get_layer_info(document_name, layer_name)

    def ping(self) -> dict[str, Any]:
        return self._ensure_client().ping()

    def is_alive(self) -> bool:
        return self._ensure_client().is_alive()

    def execute_script(self, script_content: str) -> dict[str, Any]:
        return self._ensure_client().execute_script(script_content)

    def undo(self) -> dict[str, Any]:
        return self._ensure_client().undo()

    def redo(self) -> dict[str, Any]:
        return self._ensure_client().redo()

    @property
    def client(self) -> PSMDPClient:
        """底层 MCP 客户端实例。"""
        return self._ensure_client()


class PuppetEnginePSAdapter(BasePSAdapter):
    """基于 Puppet Engine 的 Photoshop 适配器。

    通过 puppet-automation 引擎层与 Photoshop 通信。
    """

    name = "ps_puppet"

    def __init__(self, engine=None) -> None:
        self._engine = engine

    def _ensure_engine(self):
        if self._engine is None:
            try:
                import importlib.machinery
                import importlib.util
                import sys
                from pathlib import Path
                _project_root = Path(__file__).resolve().parent.parent.parent
                _pa_dir = _project_root / "puppet-automation"
                _src_dir = _pa_dir / "src"
                if "puppet_automation" not in sys.modules:
                    _pkg = importlib.util.module_from_spec(
                        importlib.machinery.ModuleSpec(
                            "puppet_automation", loader=None, is_package=True
                        )
                    )
                    _pkg.__path__ = [str(_pa_dir)]
                    sys.modules["puppet_automation"] = _pkg
                if "puppet_automation.src" not in sys.modules:
                    _src_init = _src_dir / "__init__.py"
                    if _src_init.exists():
                        _spec = importlib.util.spec_from_file_location(
                            "puppet_automation.src", _src_init,
                            submodule_search_locations=[str(_src_dir)]
                        )
                    else:
                        _spec = importlib.machinery.ModuleSpec(
                            "puppet_automation.src", loader=None, is_package=True
                        )
                        _spec.submodule_search_locations = [str(_src_dir)]
                    _src_pkg = importlib.util.module_from_spec(_spec)
                    sys.modules["puppet_automation.src"] = _src_pkg
                    if _spec.loader is not None:
                        _spec.loader.exec_module(_src_pkg)
                # 注意: 历史上曾使用 puppet_automation.src.engines.ps_engine.PSEngine
                # 现已重命名为 engines.photoshop.PhotoshopEngine (包路径:
                # puppet_automation.src.engines.photoshop)
                from puppet_automation.src.engines.photoshop import PhotoshopEngine
                self._engine = PhotoshopEngine()
            except ImportError:
                raise RuntimeError("Puppet Engine not available")
        return self._engine

    def create_document(
        self,
        name: str,
        width: int = 1920,
        height: int = 1080,
        resolution: float = 72.0,
        color_mode: str = "RGB",
        background_color: list[float] | None = None,
    ) -> dict[str, Any]:
        return self._ensure_engine().execute(
            action="create_document",
            name=name,
            width=width,
            height=height,
            resolution=resolution,
            color_mode=color_mode,
            background_color=background_color,
        )

    def open_document(self, file_path: str) -> dict[str, Any]:
        return self._ensure_engine().execute(action="open_document", file_path=file_path)

    def close_document(self, document_name: str, save_changes: bool = False) -> dict[str, Any]:
        return self._ensure_engine().execute(
            action="close_document",
            document_name=document_name,
            save_changes=save_changes,
        )

    def save_document(self, document_name: str, file_path: str | None = None) -> dict[str, Any]:
        return self._ensure_engine().execute(
            action="save_document",
            document_name=document_name,
            file_path=file_path,
        )

    def export_document(
        self,
        document_name: str,
        file_path: str,
        format: str = "PNG",
        quality: int = 100,
    ) -> dict[str, Any]:
        return self._ensure_engine().execute(
            action="export_document",
            document_name=document_name,
            file_path=file_path,
            format=format,
            quality=quality,
        )

    def create_layer(
        self,
        document_name: str,
        layer_name: str | None = None,
        layer_type: str = "pixel",
    ) -> dict[str, Any]:
        return self._ensure_engine().execute(
            action="create_layer",
            document_name=document_name,
            layer_name=layer_name,
            layer_type=layer_type,
        )

    def delete_layer(self, document_name: str, layer_name: str) -> dict[str, Any]:
        return self._ensure_engine().execute(
            action="delete_layer",
            document_name=document_name,
            layer_name=layer_name,
        )

    def duplicate_layer(
        self,
        document_name: str,
        layer_name: str,
        new_name: str | None = None,
    ) -> dict[str, Any]:
        return self._ensure_engine().execute(
            action="duplicate_layer",
            document_name=document_name,
            layer_name=layer_name,
            new_name=new_name,
        )

    def set_layer_properties(
        self,
        document_name: str,
        layer_name: str,
        properties: dict[str, Any],
    ) -> dict[str, Any]:
        return self._ensure_engine().execute(
            action="set_layer_properties",
            document_name=document_name,
            layer_name=layer_name,
            properties=properties,
        )

    def set_blend_mode(
        self,
        document_name: str,
        layer_name: str,
        blend_mode: Union[BlendMode, str],
    ) -> dict[str, Any]:
        return self._ensure_engine().execute(
            action="set_blend_mode",
            document_name=document_name,
            layer_name=layer_name,
            blend_mode=blend_mode,
        )

    def apply_filter(
        self,
        document_name: str,
        layer_name: str,
        filter_name: str,
        properties: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._ensure_engine().execute(
            action="apply_filter",
            document_name=document_name,
            layer_name=layer_name,
            filter_name=filter_name,
            properties=properties,
        )

    def remove_filter(self, document_name: str, layer_name: str, filter_name: str) -> dict[str, Any]:
        return self._ensure_engine().execute(
            action="remove_filter",
            document_name=document_name,
            layer_name=layer_name,
            filter_name=filter_name,
        )

    def create_selection(
        self,
        document_name: str,
        top: int = 0,
        left: int = 0,
        width: int = 100,
        height: int = 100,
    ) -> dict[str, Any]:
        return self._ensure_engine().execute(
            action="create_selection",
            document_name=document_name,
            top=top,
            left=left,
            width=width,
            height=height,
        )

    def fill_selection(
        self,
        document_name: str,
        color: list[float],
        blend_mode: str = "NORMAL",
        opacity: int = 100,
    ) -> dict[str, Any]:
        return self._ensure_engine().execute(
            action="fill_selection",
            document_name=document_name,
            color=color,
            blend_mode=blend_mode,
            opacity=opacity,
        )

    def get_document_info(self) -> dict[str, Any]:
        return self._ensure_engine().execute(action="get_document_info")

    def list_documents(self) -> list[DocumentInfo]:
        result = self._ensure_engine().execute(action="list_documents")
        docs = result.get("documents", [])
        return [
            DocumentInfo(
                id=d["id"],
                name=d["name"],
                width=d["width"],
                height=d["height"],
                resolution=d["resolution"],
                color_mode=d["colorMode"],
                num_layers=d["numLayers"],
            )
            for d in docs
        ]

    def get_layer_info(
        self,
        document_name: str,
        layer_name: str | None = None,
    ) -> Union[LayerInfo, list[LayerInfo]]:
        result = self._ensure_engine().execute(
            action="get_layer_info",
            document_name=document_name,
            layer_name=layer_name,
        )

        if layer_name:
            layer = result.get("layer", {})
            return LayerInfo(
                index=layer.get("index", 0),
                name=layer.get("name", ""),
                type=layer.get("type", ""),
                visible=layer.get("visible", True),
                locked=layer.get("locked", False),
                opacity=layer.get("opacity", 100),
            )
        else:
            layers = result.get("layers", [])
            return [
                LayerInfo(
                    index=l.get("index", 0),
                    name=l.get("name", ""),
                    type=l.get("type", ""),
                    visible=l.get("visible", True),
                    locked=l.get("locked", False),
                    opacity=l.get("opacity", 100),
                )
                for l in layers
            ]

    def ping(self) -> dict[str, Any]:
        return self._ensure_engine().execute(action="ping")

    def is_alive(self) -> bool:
        try:
            self.ping()
            return True
        except Exception:
            return False

    def execute_script(self, script_content: str) -> dict[str, Any]:
        return self._ensure_engine().execute(action="execute_script", script_content=script_content)

    def undo(self) -> dict[str, Any]:
        return self._ensure_engine().execute(action="undo")

    def redo(self) -> dict[str, Any]:
        return self._ensure_engine().execute(action="redo")

    @property
    def engine(self):
        """底层 Puppet Engine 实例。"""
        return self._ensure_engine()


class PSAdapterFactory:
    """Photoshop 适配器工厂。

    根据配置创建合适的适配器实例。
    """

    @staticmethod
    def create(
        adapter_type: str = "mcp",
        **kwargs,
    ) -> BasePSAdapter:
        """创建 Photoshop 适配器。

        Args:
            adapter_type: 适配器类型 "mcp" | "puppet"
            kwargs: 适配器初始化参数

        Returns:
            适配的 BasePSAdapter 实例
        """
        adapter_type = adapter_type.lower()

        if adapter_type == "mcp":
            return MCPClientPSAdapter(**kwargs)
        elif adapter_type == "puppet":
            return PuppetEnginePSAdapter(**kwargs)
        else:
            raise ValueError(f"Unknown adapter type: {adapter_type}")