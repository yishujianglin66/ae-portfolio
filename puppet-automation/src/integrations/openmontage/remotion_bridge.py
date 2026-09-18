"""Remotion 合成桥接器。

将 OpenMontage 的 Remotion 组件集成到 AE-Knowledge-Vault，
支持基于 React 组件的视频合成。
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

REMOTION_DIR = Path(
    r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault\external\OpenMontage\remotion-composer"
)


@dataclass
class RemotionComponent:
    """Remotion 组件信息。"""

    name: str
    type: str  # text / image / chart / overlay
    path: Path
    description: str = ""
    props_schema: dict[str, Any] = field(default_factory=dict)


class RemotionBridge:
    """Remotion 合成桥接器。"""

    def __init__(self, remotion_dir: Path | None = None):
        self.remotion_dir = remotion_dir or REMOTION_DIR
        self._components: dict[str, RemotionComponent] = {}
        logger.info(f"Remotion Bridge 初始化: {self.remotion_dir}")

    def list_components(self) -> list[RemotionComponent]:
        """列出所有 Remotion 组件。"""
        if self._components:
            return list(self._components.values())

        components_dir = self.remotion_dir / "src" / "components"
        if not components_dir.exists():
            logger.warning(f"Remotion 组件目录不存在: {components_dir}")
            return []

        # 内置组件
        builtin_types = {
            "TextCard": "text",
            "StatCard": "chart",
            "EndTag": "text",
            "LyricOverlay": "text",
            "TitledVideo": "text",
            "TalkingHead": "video",
            "Explainer": "video",
            "CollageBurst": "image",
        }

        for comp_name, comp_type in builtin_types.items():
            comp_path = components_dir / f"{comp_name}.tsx"
            if comp_path.exists():
                self._components[comp_name] = RemotionComponent(
                    name=comp_name,
                    type=comp_type,
                    path=comp_path,
                    description=self._extract_description(comp_path),
                )
        return list(self._components.values())

    def _extract_description(self, path: Path) -> str:
        """从 tsx 文件第一行注释提取描述。"""
        try:
            content = path.read_text(encoding="utf-8")
            for line in content.split("\n")[:30]:
                line = line.strip()
                if line.startswith("//") and len(line) > 4:
                    return line[2:].strip()
                if line.startswith("/*") and "*/" in line:
                    return line.split("*/")[0].lstrip("/*").strip()
        except Exception:
            pass
        return ""

    def get_component(self, name: str) -> RemotionComponent | None:
        """按名称获取组件。"""
        for comp in self.list_components():
            if comp.name == name:
                return comp
        return None

    def render_lyric_overlay(
        self,
        subtitles: list[dict[str, Any]],
        output_path: Path | str,
        style: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """生成歌词叠加层 Remotion 渲染配置。

        Args:
            subtitles: 字幕列表，每项含 text/start/end
            output_path: 输出路径
            style: 样式（颜色、字体、位置等）

        Returns:
            渲染配置字典
        """
        style = style or {
            "fontFamily": "Inter",
            "fontSize": 64,
            "color": "#ffffff",
            "stroke": "#000000",
            "strokeWidth": 2,
            "y": "85%",
        }
        config = {
            "composition": "LyricOverlay",
            "version": "1.0",
            "props": {
                "subtitles": subtitles,
                "style": style,
            },
            "output": str(output_path),
            "render_command": (
                f"npx remotion render LyricOverlay "
                f"--props={json.dumps({'subtitles': subtitles, 'style': style})}"
            ),
        }
        logger.info(f"生成 LyricOverlay 渲染配置: {len(subtitles)} 条字幕")
        return config

    def render_text_card(
        self,
        text: str,
        output_path: Path | str,
        style: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """生成 TextCard 渲染配置。"""
        style = style or {
            "backgroundColor": "#1a1a2e",
            "textColor": "#ffffff",
            "accentColor": "#ff5500",
        }
        config = {
            "composition": "TextCard",
            "props": {"text": text, "style": style},
            "output": str(output_path),
        }
        return config

    def render_stat_card(
        self,
        stats: list[dict[str, Any]],
        output_path: Path | str,
    ) -> dict[str, Any]:
        """生成 StatCard 渲染配置。

        Args:
            stats: 统计数据列表 [{"label": "用户", "value": "1.2M"}, ...]
            output_path: 输出路径
        """
        config = {
            "composition": "StatCard",
            "props": {"stats": stats},
            "output": str(output_path),
        }
        return config

    def render_titled_video(
        self,
        video_path: str,
        title: str,
        subtitle: str | None,
        output_path: Path | str,
    ) -> dict[str, Any]:
        """生成 TitledVideo 渲染配置。"""
        config = {
            "composition": "TitledVideo",
            "props": {
                "videoSrc": video_path,
                "title": title,
                "subtitle": subtitle,
            },
            "output": str(output_path),
        }
        return config

    def export_props_json(
        self,
        config: dict[str, Any],
        output_path: Path | str,
    ) -> Path:
        """导出 props JSON 供 Remotion CLI 使用。"""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(config.get("props", {}), f, ensure_ascii=False, indent=2)
        logger.info(f"Remotion props 已导出: {output_path}")
        return output_path

    def get_statistics(self) -> dict[str, Any]:
        """获取 Remotion 组件统计。"""
        comps = self.list_components()
        by_type: dict[str, int] = {}
        for c in comps:
            by_type[c.type] = by_type.get(c.type, 0) + 1
        return {
            "total": len(comps),
            "by_type": by_type,
            "components": [c.name for c in comps],
        }
