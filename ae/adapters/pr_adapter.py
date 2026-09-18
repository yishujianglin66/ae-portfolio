"""Premiere Pro 适配器。

将 PRMCP 客户端包装为统一接口，与 AE 适配器架构保持一致。

设计动机：
- 上层统一调用，与 AE 适配器保持一致的接口风格
- 将 dict 风格的返回结果标注 ``channel`` 字段
- 支持依赖注入，便于单元测试

依赖：``ae.pr_mcp_client.PRMCP``。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class BasePRAdapter:
    """Premiere Pro 通道适配器抽象基类。

    所有具体通道必须实现以下方法。
    """

    name: str = "pr"
    supports_gui: bool = True
    requires_gui: bool = True

    def is_available(self) -> bool:
        return False

    def create_sequence(
        self,
        name: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return self._not_implemented("create_sequence")

    def list_sequences(self) -> list[dict[str, Any]]:
        return self._not_implemented("list_sequences")

    def import_media(
        self,
        files: list[str],
        **kwargs: Any,
    ) -> dict[str, Any]:
        return self._not_implemented("import_media")

    def add_to_sequence(
        self,
        clip_name: str,
        track_index: int = 0,
        position: float = 0.0,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return self._not_implemented("add_to_sequence")

    def apply_effect(
        self,
        clip_name: str,
        effect_name: str,
        settings: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return self._not_implemented("apply_effect")

    def export_sequence(
        self,
        output_path: str,
        preset: str = "H.264",
        **kwargs: Any,
    ) -> dict[str, Any]:
        return self._not_implemented("export_sequence")

    def execute_script(
        self,
        script: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return self._not_implemented("execute_script")

    def _not_implemented(self, method_name: str) -> dict[str, Any]:
        return {
            "success": False,
            "error": f"method '{method_name}' not implemented in {self.name}",
            "channel": self.name,
        }


class PRAdapter(BasePRAdapter):
    """Premiere Pro MCP 客户端适配器。

    Attributes:
        name: 通道名称 ``"pr_mcp"``
        supports_gui: True
        requires_gui: True
    """

    name = "pr_mcp"
    supports_gui = True
    requires_gui = True

    def __init__(self, pr_client: Any = None) -> None:
        self._client = pr_client

    def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            from ae.pr_mcp_client import PRMCP
        except Exception as exc:
            raise RuntimeError(
                f"无法导入 PRMCP，请确认 ae.pr_mcp_client 可用: {exc}"
            )
        self._client = PRMCP()
        return self._client

    def _wrap(self, payload: Any) -> dict[str, Any]:
        if isinstance(payload, dict):
            d = dict(payload)
            d.setdefault("channel", self.name)
            d.setdefault("success", True)
            return d
        return {"success": True, "data": payload, "channel": self.name}

    def _wrap_list(self, payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [
                {**item, "channel": self.name} if isinstance(item, dict) else {"data": item, "channel": self.name}
                for item in payload
            ]
        return [{"data": payload, "channel": self.name}]

    def is_available(self) -> bool:
        try:
            client = self._ensure_client()
            return bool(client.is_alive())
        except Exception as exc:
            logger.debug("PR MCP 通道不可用: %s", exc)
            return False

    def create_sequence(
        self,
        name: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        client = self._ensure_client()
        return self._wrap(client.create_sequence(name=name, **kwargs))

    def list_sequences(self) -> list[dict[str, Any]]:
        try:
            client = self._ensure_client()
        except Exception:
            return []
        seqs = client.list_sequences()
        return [
            {
                "name": s.name,
                "duration": s.duration,
                "width": s.width,
                "height": s.height,
                "fps": s.fps,
                "channel": self.name,
            }
            for s in seqs
        ]

    def import_media(
        self,
        files: list[str],
        **kwargs: Any,
    ) -> dict[str, Any]:
        client = self._ensure_client()
        return self._wrap(client.import_media(files=files, **kwargs))

    def add_to_sequence(
        self,
        clip_name: str,
        track_index: int = 0,
        position: float = 0.0,
        **kwargs: Any,
    ) -> dict[str, Any]:
        client = self._ensure_client()
        return self._wrap(
            client.add_to_sequence(
                clip_name=clip_name,
                track_index=track_index,
                position=position,
                **kwargs,
            )
        )

    def apply_effect(
        self,
        clip_name: str,
        effect_name: str,
        settings: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        client = self._ensure_client()
        return self._wrap(
            client.apply_effect(
                clip_name=clip_name,
                effect_name=effect_name,
                settings=settings or {},
                **kwargs,
            )
        )

    def export_sequence(
        self,
        output_path: str,
        preset: str = "H.264",
        **kwargs: Any,
    ) -> dict[str, Any]:
        client = self._ensure_client()
        return self._wrap(client.export_sequence(output_path=output_path, preset=preset, **kwargs))

    def render_sequence(
        self,
        output_path: str,
        preset: str = "H.264",
        **kwargs: Any,
    ) -> dict[str, Any]:
        return self.export_sequence(output_path=output_path, preset=preset, **kwargs)

    def execute_script(
        self,
        script: str,
        dry_run: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        client = self._ensure_client()
        if dry_run:
            return {
                "success": True,
                "dry_run": True,
                "script_length": len(script),
                "channel": self.name,
            }
        return self._wrap(client.execute_script(script=script))

    def new_project(self, name: str, path: str | None = None, **kwargs: Any) -> dict[str, Any]:
        client = self._ensure_client()
        return self._wrap(client.new_project(name=name, path=path, **kwargs))

    def open_project(self, path: str, **kwargs: Any) -> dict[str, Any]:
        client = self._ensure_client()
        return self._wrap(client.open_project(path=path, **kwargs))

    def save_project(self, path: str | None = None, **kwargs: Any) -> dict[str, Any]:
        client = self._ensure_client()
        return self._wrap(client.save_project(path=path, **kwargs))

    def close_project(self, **kwargs: Any) -> dict[str, Any]:
        client = self._ensure_client()
        return self._wrap(client.close_project(**kwargs))

    def get_project_info(self) -> dict[str, Any]:
        client = self._ensure_client()
        info = client.get_project_info()
        return {
            "name": info.name,
            "path": info.path,
            "sequence_count": info.sequence_count,
            "channel": self.name,
            "success": True,
        }

    def get_sequence_info(self, sequence_name: str, **kwargs: Any) -> dict[str, Any]:
        client = self._ensure_client()
        return self._wrap(client.get_sequence_info(sequence_name=sequence_name, **kwargs))

    def delete_sequence(self, sequence_name: str, **kwargs: Any) -> dict[str, Any]:
        client = self._ensure_client()
        return self._wrap(client.delete_sequence(sequence_name=sequence_name, **kwargs))

    def add_clip_to_sequence(
        self,
        clip_name: str,
        track_index: int = 0,
        position: float = 0.0,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return self.add_to_sequence(clip_name=clip_name, track_index=track_index, position=position, **kwargs)

    def cut_clip(
        self,
        track_index: int,
        clip_index: int,
        cut_time: float,
        **kwargs: Any,
    ) -> dict[str, Any]:
        client = self._ensure_client()
        return self._wrap(client.cut_clip(track_index=track_index, clip_index=clip_index, cut_time=cut_time, **kwargs))

    def split_clip(
        self,
        track_index: int,
        clip_index: int,
        split_time: float,
        **kwargs: Any,
    ) -> dict[str, Any]:
        client = self._ensure_client()
        return self._wrap(client.split_clip(track_index=track_index, clip_index=clip_index, split_time=split_time, **kwargs))

    def delete_clip(
        self,
        track_index: int,
        clip_index: int,
        **kwargs: Any,
    ) -> dict[str, Any]:
        client = self._ensure_client()
        return self._wrap(client.delete_clip(track_index=track_index, clip_index=clip_index, **kwargs))

    def remove_effect(
        self,
        clip_name: str,
        effect_name: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        client = self._ensure_client()
        return self._wrap(client.remove_effect(clip_name=clip_name, effect_name=effect_name, **kwargs))

    def get_effect_params(
        self,
        clip_name: str,
        effect_name: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        client = self._ensure_client()
        return self._wrap(client.get_effect_params(clip_name=clip_name, effect_name=effect_name, **kwargs))


__all__ = ["BasePRAdapter", "PRAdapter"]