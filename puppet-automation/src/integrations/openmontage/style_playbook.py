"""OpenMontage 风格手册加载器。

将 OpenMontage 的「风格手册」(playbook) 集成到 AE 制作中。
风格手册定义：颜色、字体、动效、声音等设计 token。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from loguru import logger

from .pipeline_runtime import OPENMONTAGE_ROOT


STYLES_DIR = OPENMONTAGE_ROOT / "styles"


@dataclass
class DesignTokens:
    """设计 token（颜色、字体、动效等）。"""

    chart_palette: List[str] = field(default_factory=list)
    scale_system: Dict[str, float] = field(default_factory=dict)
    weight_matrix: Dict[str, int] = field(default_factory=dict)
    color_rules: Dict[str, Any] = field(default_factory=dict)
    fonts: Dict[str, str] = field(default_factory=dict)
    motion: Dict[str, Any] = field(default_factory=dict)
    audio: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chart_palette": self.chart_palette,
            "scale_system": self.scale_system,
            "weight_matrix": self.weight_matrix,
            "color_rules": self.color_rules,
            "fonts": self.fonts,
            "motion": self.motion,
            "audio": self.audio,
        }


@dataclass
class StylePlaybook:
    """风格手册。"""

    name: str
    path: Path
    description: str = ""
    tags: List[str] = field(default_factory=list)
    tokens: DesignTokens = field(default_factory=DesignTokens)
    typography: Dict[str, Any] = field(default_factory=dict)
    visual_language: Dict[str, Any] = field(default_factory=dict)
    motion_design: Dict[str, Any] = field(default_factory=dict)
    audio_design: Dict[str, Any] = field(default_factory=dict)
    asset_constraints: Dict[str, Any] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "tags": self.tags,
            "tokens": self.tokens.to_dict(),
            "typography": self.typography,
            "visual_language": self.visual_language,
            "motion_design": self.motion_design,
            "audio_design": self.audio_design,
            "asset_constraints": self.asset_constraints,
        }


class StylePlaybookLoader:
    """风格手册加载器。"""

    def __init__(self, styles_dir: Optional[Path] = None):
        self.styles_dir = styles_dir or STYLES_DIR
        self._cache: Dict[str, StylePlaybook] = {}
        logger.info(f"风格手册加载器初始化: {self.styles_dir}")

    def list_playbooks(self) -> List[str]:
        """列出所有风格手册。"""
        if not self.styles_dir.exists():
            return []
        return sorted([p.stem for p in self.styles_dir.glob("*.yaml")])

    def load(self, name: str) -> StylePlaybook:
        """加载指定风格手册。"""
        if name in self._cache:
            return self._cache[name]

        path = self.styles_dir / f"{name}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"Style playbook not found: {path}")

        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

        tokens = DesignTokens()
        tokens_data = raw.get("design_tokens", {}) or {}
        tokens.chart_palette = tokens_data.get("chart_palette", [])
        tokens.scale_system = tokens_data.get("scale_system", {})
        tokens.weight_matrix = tokens_data.get("weight_matrix", {})
        tokens.color_rules = tokens_data.get("color_rules", {})
        tokens.fonts = tokens_data.get("fonts", {})

        playbook = StylePlaybook(
            name=name,
            path=path,
            description=raw.get("description", "").strip(),
            tags=raw.get("tags", []),
            tokens=tokens,
            typography=raw.get("typography", {}),
            visual_language=raw.get("visual_language", {}),
            motion_design=raw.get("motion_design", {}),
            audio_design=raw.get("audio_design", {}),
            asset_constraints=raw.get("asset_constraints", {}),
            raw=raw,
        )

        self._cache[name] = playbook
        logger.info(f"已加载风格手册: {name}")
        return playbook

    def load_all(self) -> List[StylePlaybook]:
        """加载所有风格手册。"""
        playbooks = []
        for name in self.list_playbooks():
            try:
                playbooks.append(self.load(name))
            except Exception as e:
                logger.error(f"加载风格手册 {name} 失败: {e}")
        return playbooks

    def get_playbook_info(self, name: str) -> Dict[str, Any]:
        """获取风格手册概要。"""
        pb = self.load(name)
        return {
            "name": pb.name,
            "description": pb.description,
            "tags": pb.tags,
            "palette_colors": len(pb.tokens.chart_palette),
            "scale_levels": len(pb.tokens.scale_system),
            "has_motion": bool(pb.motion_design),
            "has_audio": bool(pb.audio_design),
            "has_typography": bool(pb.typography),
        }

    def apply_to_ae_comp(self, playbook_name: str, comp_name: str) -> Dict[str, Any]:
        """生成 AE 合成的应用指令。

        Args:
            playbook_name: 风格手册名
            comp_name: AE 合成名

        Returns:
            AE JSX 指令字典
        """
        pb = self.load(playbook_name)
        instructions = {
            "comp_name": comp_name,
            "background_color": pb.visual_language.get("background_color", "#000000"),
            "primary_color": pb.visual_language.get("primary_color", "#ffffff"),
            "accent_color": pb.visual_language.get("accent_color", "#ff5500"),
            "font_family": pb.tokens.fonts.get("primary", "Inter"),
            "font_size_scale": pb.tokens.scale_system.get("base", 1.0),
            "motion_easing": pb.motion_design.get("easing", "easeInOut"),
            "motion_duration": pb.motion_design.get("default_duration", 0.5),
            "audio_target_lufs": pb.audio_design.get("target_lufs", -14),
        }
        return instructions
