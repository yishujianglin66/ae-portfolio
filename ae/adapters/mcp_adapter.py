"""MCP 客户端适配器。

将 AEMCPClient 包装为 BaseAEAdapter 子类，复用其 40+ 工具方法。
本适配器是 "瘦包装"：方法签名与 AEMCPClient 高度一致，
无需在适配器中重新实现业务逻辑。

设计动机：
- 业务代码用统一的 ``UnifiedAEClient`` 调用；
- AEMCPClient 已通过 ``ae_mcp_client.py`` 暴露方法；
- 适配器负责将 dict 风格的返回结果标注 ``channel`` 字段。

依赖：``ae.ae_mcp_client.AEMCPClient``。
当 MCP 客户端未安装时（如最小部署），可通过注入 mock 替代。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .puppet_adapter import BaseAEAdapter

logger = logging.getLogger(__name__)


class MCPClientAdapter(BaseAEAdapter):
    """AEMCPClient 适配器。

    Attributes:
        name: 通道名称 ``"mcp"``
        supports_gui: True（依赖 AE 面板监听）
        requires_gui: True
    """

    name = "mcp"
    supports_gui = True
    requires_gui = True

    def __init__(self, mcp_client: Any = None) -> None:
        """初始化。

        Args:
            mcp_client: 已构造好的 AEMCPClient 实例（依赖注入）。
                None 时延迟创建默认实例。
        """
        self._client = mcp_client

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            from ae.ae_mcp_client import AEMCPClient  # type: ignore
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                f"无法导入 AEMCPClient，请确认 ae.ae_mcp_client 可用: {exc}"
            )
        self._client = AEMCPClient()
        return self._client

    def _wrap(self, payload: Any) -> Dict[str, Any]:
        """标注通道字段。"""
        if isinstance(payload, dict):
            d = dict(payload)
            d.setdefault("channel", self.name)
            d.setdefault("success", True)
            return d
        return {"success": True, "data": payload, "channel": self.name}

    def _wrap_list(self, payload: Any) -> List[Dict[str, Any]]:
        if isinstance(payload, list):
            return [
                {**item, "channel": self.name} if isinstance(item, dict) else {"data": item, "channel": self.name}
                for item in payload
            ]
        return [{"data": payload, "channel": self.name}]

    # ------------------------------------------------------------------
    # 通道能力
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        try:
            client = self._ensure_client()
            return bool(client.is_alive())
        except Exception as exc:  # noqa: BLE001
            logger.debug("MCP 通道不可用: %s", exc)
            return False

    # ------------------------------------------------------------------
    # 合成管理
    # ------------------------------------------------------------------

    def create_composition(
        self,
        name: str,
        width: int,
        height: int,
        fps: float = 30.0,
        duration: float = 10.0,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        client = self._ensure_client()
        return self._wrap(
            client.create_composition(
                name=name,
                width=int(width),
                height=int(height),
                duration=float(duration),
                frame_rate=float(fps),
                bg_color=kwargs.get("bg_color"),
            )
        )

    def list_compositions(self) -> List[Dict[str, Any]]:
        try:
            client = self._ensure_client()
        except Exception:
            return []
        comps = client.list_compositions()
        return [
            {
                "name": c.name,
                "id": c.id,
                "width": c.width,
                "height": c.height,
                "duration": c.duration,
                "frameRate": c.frame_rate,
                "numLayers": c.num_layers,
                "channel": self.name,
            }
            for c in comps
        ]

    # ------------------------------------------------------------------
    # 图层创建
    # ------------------------------------------------------------------

    def create_text_layer(
        self,
        comp_name: str,
        text: str,
        layer_name: Optional[str] = None,
        font_family: Optional[str] = None,
        font_size: Optional[float] = None,
        fill_color: Optional[List[float]] = None,
        position: Optional[List[float]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        client = self._ensure_client()
        return self._wrap(
            client.create_text_layer(
                comp_name=comp_name,
                text=text,
                layer_name=layer_name,
                font_family=font_family,
                font_size=font_size,
                fill_color=fill_color,
                position=position,
            )
        )

    def create_solid_layer(
        self,
        comp_name: str,
        color: List[float],
        layer_name: Optional[str] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        client = self._ensure_client()
        return self._wrap(
            client.create_solid_layer(
                comp_name=comp_name,
                layer_name=layer_name,
                color=color,
                width=width,
                height=height,
            )
        )

    def create_shape_layer(
        self,
        comp_name: str,
        shape_type: str,
        layer_name: Optional[str] = None,
        fill_color: Optional[List[float]] = None,
        size: Optional[List[float]] = None,
        position: Optional[List[float]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        client = self._ensure_client()
        return self._wrap(
            client.create_shape_layer(
                comp_name=comp_name,
                shape_type=shape_type,
                layer_name=layer_name,
                fill_color=fill_color,
                size=size,
                position=position,
            )
        )

    def add_adjustment_layer(
        self,
        comp_name: str,
        layer_name: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        client = self._ensure_client()
        return self._wrap(
            client.add_adjustment_layer(comp_name=comp_name, layer_name=layer_name)
        )

    # ------------------------------------------------------------------
    # 图层属性
    # ------------------------------------------------------------------

    def set_layer_properties(
        self,
        comp_name: str,
        layer_index: int,
        **properties: Any,
    ) -> Dict[str, Any]:
        """MCP 实现：按 layerIndex 找图层后批量设属性。"""
        client = self._ensure_client()
        # MCP 通常按 layer_name 操作；这里使用 layer_index 实际取值
        layer_name = properties.pop("_layer_name", None) or str(layer_index)
        return self._wrap(
            client.set_layer_properties(
                comp_name=comp_name, layer_name=layer_name, properties=properties
            )
        )

    def set_blend_mode(
        self,
        comp_name: str,
        layer_index: int,
        blend_mode: str,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        client = self._ensure_client()
        layer_name = kwargs.get("layer_name") or str(layer_index)
        return self._wrap(
            client.set_blend_mode(
                comp_name=comp_name, layer_name=layer_name, blend_mode=blend_mode
            )
        )

    def set_track_matte(
        self,
        comp_name: str,
        layer_index: int,
        matte_type: str,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        client = self._ensure_client()
        layer_name = kwargs.get("layer_name") or str(layer_index)
        return self._wrap(
            client.set_track_matte(
                comp_name=comp_name, layer_name=layer_name, matte_type=matte_type
            )
        )

    def set_parent_layer(
        self,
        comp_name: str,
        layer_index: int,
        parent_index: int,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        client = self._ensure_client()
        layer_name = kwargs.get("layer_name") or str(layer_index)
        return self._wrap(
            client.set_parent_layer(comp_name=comp_name, layer_name=layer_name, parent_name=str(parent_index))
        )

    # ------------------------------------------------------------------
    # 动画
    # ------------------------------------------------------------------

    def set_layer_keyframe(
        self,
        comp_name: str,
        layer_index: int,
        property_name: str,
        time: float,
        value: Any,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        client = self._ensure_client()
        layer_name = kwargs.get("layer_name") or str(layer_index)
        return self._wrap(
            client.set_layer_keyframe(
                comp_name=comp_name,
                layer_name=layer_name,
                property_name=property_name,
                time=float(time),
                value=value,
            )
        )

    def set_keyframe_easing(
        self,
        comp_name: str,
        layer_index: int,
        property_path: str,
        key_index: int,
        easing_type: str,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        client = self._ensure_client()
        layer_name = kwargs.get("layer_name") or str(layer_index)
        return self._wrap(
            client.set_keyframe_easing(
                comp_name=comp_name,
                layer_name=layer_name,
                property_name=property_path,
                key_index=int(key_index),
                easing_type=easing_type,
            )
        )

    def set_layer_expression(
        self,
        comp_name: str,
        layer_index: int,
        property_name: str,
        expression: str,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        client = self._ensure_client()
        layer_name = kwargs.get("layer_name") or str(layer_index)
        return self._wrap(
            client.set_layer_expression(
                comp_name=comp_name,
                layer_name=layer_name,
                property_name=property_name,
                expression=expression,
            )
        )

    # ------------------------------------------------------------------
    # 效果
    # ------------------------------------------------------------------

    def apply_effect(
        self,
        comp_name: str,
        layer_index: int,
        effect_name: str,
        settings: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        client = self._ensure_client()
        layer_name = kwargs.get("layer_name") or str(layer_index)
        return self._wrap(
            client.apply_effect(
                comp_name=comp_name,
                layer_name=layer_name,
                effect_name=effect_name,
                properties=settings or {},
            )
        )

    def apply_effect_template(
        self,
        comp_name: str,
        layer_index: int,
        template_name: str,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        client = self._ensure_client()
        layer_name = kwargs.get("layer_name") or str(layer_index)
        return self._wrap(
            client.apply_effect_template(
                comp_name=comp_name,
                layer_name=layer_name,
                template_name=template_name,
            )
        )

    def batch_add_effects(
        self,
        comp_name: str,
        layer_index: int,
        effects: List[Dict[str, Any]],
        **kwargs: Any,
    ) -> Dict[str, Any]:
        client = self._ensure_client()
        layer_name = kwargs.get("layer_name") or str(layer_index)
        return self._wrap(
            client.batch_add_effects(
                comp_name=comp_name, layer_name=layer_name, effects=effects or []
            )
        )

    # ------------------------------------------------------------------
    # 蒙版
    # ------------------------------------------------------------------

    def set_layer_mask(
        self,
        comp_name: str,
        layer_index: int,
        shape: str = "rect",
        **mask_params: Any,
    ) -> Dict[str, Any]:
        client = self._ensure_client()
        layer_name = mask_params.pop("layer_name", None) or str(layer_index)
        # 兼容调用方传入的 mask 参数，映射到 create_mask 的命名参数
        return self._wrap(
            client.create_mask(
                comp_name=comp_name,
                layer_name=layer_name,
                mask_name=mask_params.pop("mask_name", None),
                mask_path=mask_params.pop("mask_path", None),
                mask_mode=mask_params.pop("mask_mode", "add"),
            )
        )

    # ------------------------------------------------------------------
    # 渲染
    # ------------------------------------------------------------------

    def render(
        self,
        comp_name: str,
        output_path: str,
        format: str = "h264",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        client = self._ensure_client()
        # AEMCPClient 无 render 方法：通过"加入渲染队列 + 开始渲染"组合实现
        queued = client.add_to_render_queue(
            comp_name=comp_name, output_path=output_path
        )
        started = client.start_render()
        return self._wrap(
            {"queued": queued, "render": started, "channel": self.name}
        )

    # ------------------------------------------------------------------
    # 高级
    # ------------------------------------------------------------------

    def execute_atom_script(
        self,
        script: str,
        dry_run: bool = False,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        client = self._ensure_client()
        if dry_run:
            return {
                "success": True,
                "dry_run": True,
                "script_length": len(script),
                "channel": self.name,
            }
        return self._wrap(client.execute_atom_script(script_content=script))


__all__ = ["MCPClientAdapter"]
