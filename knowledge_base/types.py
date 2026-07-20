"""
knowledge_base/types.py - 知识库数据类型定义

所有 mypy 兼容的 dataclass 和 Enum 定义。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class BlockType(Enum):
    """Markdown 块类型。"""
    HEADING = "heading"
    TABLE = "table"
    PARAGRAPH = "paragraph"
    CODE_BLOCK = "code_block"
    LIST = "list"
    HR = "hr"


@dataclass
class MdBlock:
    """Markdown AST 节点。"""
    block_type: BlockType
    content: str
    level: int = 0  # heading level (1-6)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TableRow:
    """表格行。"""
    columns: Dict[str, str]  # header -> value


@dataclass
class EffectMapping:
    """效果映射条目。"""
    keyword: str
    match_name: str
    category: str = ""
    source_file: str = ""
    confidence: float = 0.8
    extracted_by: str = "rule"  # "rule" | "llm"


@dataclass
class TransitionRecipe:
    """转场配方。"""
    transition_type: str
    display_name: str
    effect_match: str
    params: Dict[str, Any] = field(default_factory=dict)
    animate: Dict[str, Any] = field(default_factory=dict)
    source_file: str = ""


@dataclass
class ColorPreset:
    """调色预设。"""
    name: str
    parameters: str
    ae_recipe: str
    ae_params: str
    category: str = ""
    source_file: str = ""


@dataclass
class StyleRecipe:
    """风格配方。"""
    name: str
    display_name: str
    category: str
    description: str
    keywords: List[str] = field(default_factory=list)
    effects: List[Dict[str, Any]] = field(default_factory=list)
    source_file: str = ""


@dataclass
class KnowledgeItem:
    """通用知识条目。"""
    item_type: str
    title: str
    content: Dict[str, Any]
    source_file: str
    confidence: float = 0.8
    extracted_by: str = "rule"  # "rule" | "llm"
