"""
knowledge_base/adapters/effect_adapter.py - 效果映射适配器 (Layer 4)

将知识库中解析的效果映射转换为与 KEYWORD_TO_EFFECT_MAP 兼容的 Dict[str, str] 格式。

支持两种提取模式：
1. 表格提取：从包含 "关键词/matchName" 列的表格中提取
2. 文本提取：从 "**关键词** → matchName" 格式的列表中提取

用法：
    from knowledge_base.adapters.effect_adapter import EffectAdapter

    adapter = EffectAdapter()
    mappings = adapter.extract_from_blocks(blocks, source_file="file.md")
    effect_map = adapter.to_dict(mappings)
    merged = adapter.merge_with_fallback(mappings, fallback_map)
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from knowledge_base.table_extractor import TableExtractor
from knowledge_base.types import BlockType, EffectMapping, MdBlock


class EffectAdapter:
    """效果映射适配器 - 输出与 KEYWORD_TO_EFFECT_MAP 兼容的格式。"""

    # 匹配 "**关键词** → matchName" 或 "关键词 -> matchName"
    _ARROW_RE = re.compile(
        r"[-*]?\s*\*{0,2}([^*\n]+?)\*{0,2}\s*(?:→|->|=>)\s*(\S+)"
    )

    # 常见列名变体（仅匹配效果映射专用列名）
    _KEYWORD_COLS = {"关键词", "关键字", "keyword", "效果名称", "效果名"}
    _MATCHNAME_COLS = {"matchname", "match_name", "match name"}
    _CATEGORY_COLS = {"分类", "category", "类别"}

    def __init__(self) -> None:
        self._table_extractor = TableExtractor()

    def extract_from_blocks(
        self,
        blocks: list[MdBlock],
        source_file: str = "",
    ) -> list[EffectMapping]:
        """从 MdBlock 列表中提取效果映射。

        扫描所有 TABLE 块，查找包含"关键词"和"matchName"列的表格。

        Args:
            blocks: MdBlock 列表
            source_file: 来源文件名

        Returns:
            EffectMapping 列表
        """
        mappings: list[EffectMapping] = []

        for block in blocks:
            if block.block_type != BlockType.TABLE:
                continue

            rows = self._table_extractor.extract(block)
            if not rows:
                continue

            # 查找关键词列和 matchName 列
            if not rows:
                continue
            headers = list(rows[0].columns.keys())
            keyword_col = self._find_column(headers, self._KEYWORD_COLS)
            matchname_col = self._find_column(headers, self._MATCHNAME_COLS)

            if not keyword_col or not matchname_col:
                continue

            category_col = self._find_column(headers, self._CATEGORY_COLS)

            for row in rows:
                keyword = row.columns.get(keyword_col, "").strip()
                match_name = row.columns.get(matchname_col, "").strip()
                if not keyword or not match_name:
                    continue

                category = ""
                if category_col:
                    category = row.columns.get(category_col, "").strip()

                mappings.append(EffectMapping(
                    keyword=keyword,
                    match_name=match_name,
                    category=category,
                    source_file=source_file,
                ))

        return mappings

    def extract_from_text_blocks(
        self,
        blocks: list[MdBlock],
        source_file: str = "",
    ) -> list[EffectMapping]:
        """从文本块中提取效果映射（箭头格式）。

        匹配格式：
            - **关键词** → matchName
            - 关键词 -> matchName

        Args:
            blocks: MdBlock 列表
            source_file: 来源文件名

        Returns:
            EffectMapping 列表
        """
        mappings: list[EffectMapping] = []

        for block in blocks:
            if block.block_type not in (BlockType.PARAGRAPH, BlockType.LIST):
                continue

            for line in block.content.split("\n"):
                m = self._ARROW_RE.search(line)
                if m:
                    keyword = m.group(1).strip()
                    match_name = m.group(2).strip()
                    # 去除粗体标记
                    keyword = re.sub(r"\*{1,2}([^*]+)\*{1,2}", r"\1", keyword)
                    if keyword and match_name:
                        mappings.append(EffectMapping(
                            keyword=keyword,
                            match_name=match_name,
                            source_file=source_file,
                        ))

        return mappings

    def to_dict(self, mappings: list[EffectMapping]) -> dict[str, str]:
        """转换为 Dict[str, str] 格式。

        Args:
            mappings: EffectMapping 列表

        Returns:
            keyword -> matchName 字典
        """
        result: dict[str, str] = {}
        for m in mappings:
            result[m.keyword] = m.match_name
        return result

    def merge_with_fallback(
        self,
        kb_mappings: list[EffectMapping],
        fallback: dict[str, str],
    ) -> dict[str, str]:
        """合并知识库映射与硬编码 fallback。

        知识库映射优先，fallback 补充缺失的条目。

        Args:
            kb_mappings: 从知识库提取的映射
            fallback: 硬编码 fallback 映射

        Returns:
            合并后的字典
        """
        result: dict[str, str] = dict(fallback)
        for m in kb_mappings:
            result[m.keyword] = m.match_name
        return result

    @staticmethod
    def _find_column(headers: list[str], candidates: set[str]) -> str | None:
        """在表头中查找匹配候选名称的列。"""
        for h in headers:
            if h.lower().strip() in candidates:
                return h
        return None
