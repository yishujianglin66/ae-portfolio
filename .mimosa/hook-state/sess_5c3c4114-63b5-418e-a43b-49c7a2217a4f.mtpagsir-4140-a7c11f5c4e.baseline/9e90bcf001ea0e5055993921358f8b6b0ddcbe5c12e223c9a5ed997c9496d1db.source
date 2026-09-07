#!/usr/bin/env python3
"""
tests/test_section_parser.py - 章节解析器测试 (Phase 1)

TDD: 先定义行为，再实现 section_parser.py
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from knowledge_base.types import BlockType, MdBlock


class TestSectionParser(unittest.TestCase):
    """section_parser 测试。"""

    def setUp(self) -> None:
        from knowledge_base.section_parser import SectionParser
        self.parser = SectionParser()

    def test_extract_sections_by_heading(self) -> None:
        """按标题提取章节"""
        blocks = [
            MdBlock(block_type=BlockType.HEADING, content="第一章", level=1),
            MdBlock(block_type=BlockType.PARAGRAPH, content="内容1"),
            MdBlock(block_type=BlockType.HEADING, content="第二章", level=1),
            MdBlock(block_type=BlockType.PARAGRAPH, content="内容2"),
        ]
        sections = self.parser.extract_sections(blocks)
        self.assertEqual(len(sections), 2)
        self.assertEqual(sections[0]["title"], "第一章")
        self.assertEqual(sections[0]["level"], 1)
        self.assertEqual(len(sections[0]["blocks"]), 1)
        self.assertEqual(sections[1]["title"], "第二章")

    def test_nested_sections(self) -> None:
        """嵌套章节（h1 > h2 > h3）"""
        blocks = [
            MdBlock(block_type=BlockType.HEADING, content="H1", level=1),
            MdBlock(block_type=BlockType.PARAGRAPH, content="p1"),
            MdBlock(block_type=BlockType.HEADING, content="H2", level=2),
            MdBlock(block_type=BlockType.PARAGRAPH, content="p2"),
            MdBlock(block_type=BlockType.HEADING, content="H3", level=3),
            MdBlock(block_type=BlockType.PARAGRAPH, content="p3"),
        ]
        sections = self.parser.extract_sections(blocks)
        # 默认扁平模式：3 个章节
        self.assertEqual(len(sections), 3)

    def test_section_with_tables(self) -> None:
        """章节中包含表格"""
        blocks = [
            MdBlock(block_type=BlockType.HEADING, content="效果列表", level=2),
            MdBlock(
                block_type=BlockType.TABLE,
                content="| 名称 | matchName |\n|---|---|\n| 模糊 | ADBE Gaussian Blur 2 |",
            ),
        ]
        sections = self.parser.extract_sections(blocks)
        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0]["title"], "效果列表")
        table_blocks = [b for b in sections[0]["blocks"] if b.block_type == BlockType.TABLE]
        self.assertEqual(len(table_blocks), 1)

    def test_content_before_first_heading(self) -> None:
        """第一个标题前的内容"""
        blocks = [
            MdBlock(block_type=BlockType.PARAGRAPH, content="前言段落"),
            MdBlock(block_type=BlockType.HEADING, content="第一章", level=1),
            MdBlock(block_type=BlockType.PARAGRAPH, content="内容"),
        ]
        sections = self.parser.extract_sections(blocks)
        # 前言段落应作为无标题章节
        self.assertGreaterEqual(len(sections), 1)

    def test_find_section_by_title(self) -> None:
        """按标题查找章节"""
        blocks = [
            MdBlock(block_type=BlockType.HEADING, content="概述", level=1),
            MdBlock(block_type=BlockType.PARAGRAPH, content="概述内容"),
            MdBlock(block_type=BlockType.HEADING, content="效果映射", level=2),
            MdBlock(block_type=BlockType.PARAGRAPH, content="映射内容"),
        ]
        sections = self.parser.extract_sections(blocks)
        found = self.parser.find_section(sections, "效果映射")
        self.assertIsNotNone(found)
        self.assertEqual(found["title"], "效果映射")

    def test_find_section_not_found(self) -> None:
        """查找不存在的章节"""
        blocks = [
            MdBlock(block_type=BlockType.HEADING, content="概述", level=1),
        ]
        sections = self.parser.extract_sections(blocks)
        found = self.parser.find_section(sections, "不存在的章节")
        self.assertIsNone(found)

    def test_find_section_case_insensitive(self) -> None:
        """标题查找不区分大小写"""
        blocks = [
            MdBlock(block_type=BlockType.HEADING, content="Effect Map", level=2),
        ]
        sections = self.parser.extract_sections(blocks)
        found = self.parser.find_section(sections, "effect map")
        self.assertIsNotNone(found)

    def test_extract_key_value_pairs(self) -> None:
        """从章节中提取 key-value 对"""
        blocks = [
            MdBlock(block_type=BlockType.HEADING, content="参数", level=2),
            MdBlock(block_type=BlockType.PARAGRAPH, content="- **名称**: 高斯模糊\n- **matchName**: ADBE Gaussian Blur 2"),
        ]
        sections = self.parser.extract_sections(blocks)
        kv = self.parser.extract_key_value_pairs(sections[0])
        self.assertIn("名称", kv)
        self.assertEqual(kv["名称"], "高斯模糊")
        self.assertEqual(kv["matchName"], "ADBE Gaussian Blur 2")

    def test_empty_blocks(self) -> None:
        """空块列表返回空章节"""
        sections = self.parser.extract_sections([])
        self.assertEqual(sections, [])

    def test_section_filter_by_level(self) -> None:
        """按标题级别过滤章节"""
        blocks = [
            MdBlock(block_type=BlockType.HEADING, content="H1", level=1),
            MdBlock(block_type=BlockType.PARAGRAPH, content="p1"),
            MdBlock(block_type=BlockType.HEADING, content="H2", level=2),
            MdBlock(block_type=BlockType.PARAGRAPH, content="p2"),
            MdBlock(block_type=BlockType.HEADING, content="H2b", level=2),
            MdBlock(block_type=BlockType.PARAGRAPH, content="p3"),
        ]
        sections = self.parser.extract_sections(blocks)
        h2_sections = [s for s in sections if s["level"] == 2]
        self.assertEqual(len(h2_sections), 2)


if __name__ == "__main__":
    unittest.main()
