"""
knowledge_base/section_parser.py - 章节解析器 (Layer 2)

按标题层级提取章节结构，支持章节查找和 key-value 提取。

用法：
    from knowledge_base.section_parser import SectionParser

    parser = SectionParser()
    sections = parser.extract_sections(blocks)
    found = parser.find_section(sections, "效果映射")
    kv = parser.extract_key_value_pairs(found)
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from knowledge_base.types import BlockType, MdBlock


class SectionParser:
    """章节解析器 - 按标题提取章节结构。"""

    # 匹配 **key**: value 或 - **key**: value
    _KV_RE = re.compile(r"[-*]?\s*\*{0,2}([^*:]+)\*{0,2}\s*[:：]\s*(.+)")

    def extract_sections(self, blocks: list[MdBlock]) -> list[dict[str, Any]]:
        """按标题提取章节列表。

        Args:
            blocks: MdBlock 列表

        Returns:
            章节列表，每个章节为 dict:
            {
                "title": str,       # 标题文本
                "level": int,       # 标题层级 (1-6)
                "blocks": List[MdBlock],  # 章节内的块
            }
        """
        if not blocks:
            return []

        sections: list[dict[str, Any]] = []
        current_section: dict[str, Any] | None = None

        for block in blocks:
            if block.block_type == BlockType.HEADING:
                # 开始新章节
                current_section = {
                    "title": block.content,
                    "level": block.level,
                    "blocks": [],
                }
                sections.append(current_section)
            else:
                if current_section is None:
                    # 第一个标题前的内容
                    current_section = {
                        "title": "",
                        "level": 0,
                        "blocks": [],
                    }
                    sections.append(current_section)
                current_section["blocks"].append(block)

        return sections

    def find_section(
        self, sections: list[dict[str, Any]], title: str
    ) -> dict[str, Any] | None:
        """按标题查找章节（不区分大小写）。

        Args:
            sections: extract_sections 返回的章节列表
            title: 要查找的标题文本

        Returns:
            匹配的章节 dict，未找到返回 None
        """
        title_lower = title.lower()
        for section in sections:
            if section["title"].lower() == title_lower:
                return section
        return None

    def extract_key_value_pairs(self, section: dict[str, Any]) -> dict[str, str]:
        """从章节内容中提取 key-value 对。

        支持格式：
            - **key**: value
            - key: value
            * key: value

        Args:
            section: extract_sections 返回的单个章节

        Returns:
            key-value 字典
        """
        kv: dict[str, str] = {}

        for block in section.get("blocks", []):
            if block.block_type in (BlockType.PARAGRAPH, BlockType.LIST):
                lines = block.content.split("\n")
                for line in lines:
                    line = line.strip()
                    m = self._KV_RE.match(line)
                    if m:
                        key = m.group(1).strip()
                        value = m.group(2).strip()
                        # 去除粗体标记
                        key = re.sub(r"\*{1,2}([^*]+)\*{1,2}", r"\1", key)
                        kv[key] = value

        return kv
