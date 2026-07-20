"""
knowledge_base - 知识库断层弥合系统

从 10-风格化剪辑知识库/ 的 211 个 md 文件中动态提取效果映射、转场配方、
调色预设、风格配方等知识，替代代码中的硬编码映射表。

架构：
    md_parser.py       → Markdown AST 解析（规则引擎）
    table_extractor.py → 表格数据提取
    section_parser.py  → 章节结构提取
    llm_extractor.py   → LLM 知识提取（可选）
    kb_cache.py        → 文件缓存（mtime + hash）
    adapters/          → 输出格式适配层
    kb_loader.py       → 门面 API
"""
from __future__ import annotations

from knowledge_base.types import (
    BlockType,
    MdBlock,
    TableRow,
    EffectMapping,
    TransitionRecipe,
    ColorPreset,
    StyleRecipe,
    KnowledgeItem,
)

__all__ = [
    "BlockType",
    "MdBlock",
    "TableRow",
    "EffectMapping",
    "TransitionRecipe",
    "ColorPreset",
    "StyleRecipe",
    "KnowledgeItem",
]
