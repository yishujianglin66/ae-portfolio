"""OpenMontage 技能加载器。

加载 skills/INDEX.md 和具体的 skill markdown 文件，
将 OpenMontage 的「项目层技能」注入到 AE-Knowledge-Vault 的 Agent 体系。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from .pipeline_runtime import OPENMONTAGE_ROOT


SKILLS_DIR = OPENMONTAGE_ROOT / "skills"
SKILL_INDEX = SKILLS_DIR / "INDEX.md"


@dataclass
class Skill:
    """技能定义。"""

    name: str
    layer: str  # core / creative / meta
    path: Path
    description: str = ""
    tags: List[str] = field(default_factory=list)
    content: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "layer": self.layer,
            "path": str(self.path),
            "description": self.description,
            "tags": self.tags,
            "content_length": len(self.content),
        }


class SkillLoader:
    """技能加载器。"""

    def __init__(self, skills_dir: Optional[Path] = None):
        self.skills_dir = skills_dir or SKILLS_DIR
        self._skills: Dict[str, Skill] = {}
        logger.info(f"技能加载器初始化: {self.skills_dir}")

    def list_skills(self) -> List[Skill]:
        """列出所有技能。"""
        if self._skills:
            return list(self._skills.values())

        for layer_dir in self.skills_dir.iterdir():
            if not layer_dir.is_dir():
                continue
            layer = layer_dir.name
            for skill_file in layer_dir.glob("*.md"):
                skill = self._parse_skill(skill_file, layer)
                if skill:
                    self._skills[skill.name] = skill
        return list(self._skills.values())

    def _parse_skill(self, path: Path, layer: str) -> Optional[Skill]:
        """解析单个技能 markdown 文件。"""
        try:
            content = path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"读取技能文件失败 {path}: {e}")
            return None

        name = path.stem
        description = ""
        tags: List[str] = []

        lines = content.split("\n")
        in_frontmatter = False
        for line in lines[:20]:
            if line.strip().startswith("---"):
                in_frontmatter = not in_frontmatter
                continue
            if in_frontmatter:
                if line.startswith("description:"):
                    description = line.split(":", 1)[1].strip()
                elif line.startswith("tags:"):
                    tags_str = line.split(":", 1)[1].strip()
                    tags = [t.strip() for t in tags_str.split(",") if t.strip()]
            elif line.startswith("# ") and not description:
                description = line[2:].strip()

        return Skill(
            name=name,
            layer=layer,
            path=path,
            description=description,
            tags=tags,
            content=content,
        )

    def get_skill(self, name: str) -> Optional[Skill]:
        """按名称获取技能。"""
        for skill in self.list_skills():
            if skill.name == name:
                return skill
        return None

    def search_skills(
        self,
        keyword: str,
        layer: Optional[str] = None,
    ) -> List[Skill]:
        """搜索技能。"""
        keyword_lower = keyword.lower()
        results = []
        for skill in self.list_skills():
            if layer and skill.layer != layer:
                continue
            if (
                keyword_lower in skill.name.lower()
                or keyword_lower in skill.description.lower()
                or any(keyword_lower in t.lower() for t in skill.tags)
            ):
                results.append(skill)
        return results

    def get_layer_skills(self, layer: str) -> List[Skill]:
        """获取指定层级的所有技能。"""
        return [s for s in self.list_skills() if s.layer == layer]

    def get_statistics(self) -> Dict[str, Any]:
        """获取技能统计信息。"""
        skills = self.list_skills()
        by_layer: Dict[str, int] = {}
        for skill in skills:
            by_layer[skill.layer] = by_layer.get(skill.layer, 0) + 1
        return {
            "total": len(skills),
            "by_layer": by_layer,
            "skills_dir": str(self.skills_dir),
        }
