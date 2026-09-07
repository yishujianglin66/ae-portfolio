#!/usr/bin/env python3
"""
tests/test_md_parser.py - Markdown 解析器测试 (Phase 1)

TDD: 先定义行为，再实现 md_parser.py
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from knowledge_base.types import BlockType, MdBlock


class TestMdParserBasic(unittest.TestCase):
    """md_parser 基础解析测试。"""

    def setUp(self) -> None:
        from knowledge_base.md_parser import MdParser
        self.parser = MdParser()

    def test_parse_heading_h1(self) -> None:
        """解析 # 标题"""
        md = "# 一级标题\n\n段落内容"
        blocks = self.parser.parse(md)
        headings = [b for b in blocks if b.block_type == BlockType.HEADING]
        self.assertEqual(len(headings), 1)
        self.assertEqual(headings[0].content, "一级标题")
        self.assertEqual(headings[0].level, 1)

    def test_parse_heading_levels(self) -> None:
        """解析 h1-h6 标题"""
        md = "# H1\n## H2\n### H3\n#### H4\n##### H5\n###### H6"
        blocks = self.parser.parse(md)
        headings = [b for b in blocks if b.block_type == BlockType.HEADING]
        self.assertEqual(len(headings), 6)
        for i, h in enumerate(headings, 1):
            self.assertEqual(h.level, i)

    def test_parse_paragraph(self) -> None:
        """解析普通段落"""
        md = "这是第一段。\n\n这是第二段。"
        blocks = self.parser.parse(md)
        paras = [b for b in blocks if b.block_type == BlockType.PARAGRAPH]
        self.assertEqual(len(paras), 2)
        self.assertIn("第一段", paras[0].content)
        self.assertIn("第二段", paras[1].content)

    def test_parse_code_block(self) -> None:
        """解析代码块"""
        md = "```javascript\nvar x = 1;\nconsole.log(x);\n```"
        blocks = self.parser.parse(md)
        code_blocks = [b for b in blocks if b.block_type == BlockType.CODE_BLOCK]
        self.assertEqual(len(code_blocks), 1)
        self.assertIn("var x = 1", code_blocks[0].content)
        self.assertEqual(code_blocks[0].metadata.get("language"), "javascript")

    def test_parse_code_block_no_lang(self) -> None:
        """解析无语言标记的代码块"""
        md = "```\nsome code\n```"
        blocks = self.parser.parse(md)
        code_blocks = [b for b in blocks if b.block_type == BlockType.CODE_BLOCK]
        self.assertEqual(len(code_blocks), 1)
        self.assertIn("some code", code_blocks[0].content)

    def test_parse_horizontal_rule(self) -> None:
        """解析水平线 ---"""
        md = "段落\n\n---\n\n下一段"
        blocks = self.parser.parse(md)
        hrs = [b for b in blocks if b.block_type == BlockType.HR]
        self.assertGreaterEqual(len(hrs), 1)

    def test_parse_list_unordered(self) -> None:
        """解析无序列表"""
        md = "- 项目1\n- 项目2\n- 项目3"
        blocks = self.parser.parse(md)
        lists = [b for b in blocks if b.block_type == BlockType.LIST]
        self.assertGreaterEqual(len(lists), 1)
        self.assertIn("项目1", lists[0].content)

    def test_parse_list_ordered(self) -> None:
        """解析有序列表"""
        md = "1. 第一步\n2. 第二步\n3. 第三步"
        blocks = self.parser.parse(md)
        lists = [b for b in blocks if b.block_type == BlockType.LIST]
        self.assertGreaterEqual(len(lists), 1)

    def test_parse_table_basic(self) -> None:
        """解析基础 Markdown 表格"""
        md = (
            "| 类别 | 英文名 | 效果数量 |\n"
            "|------|--------|--------|\n"
            "| 色彩校正 | Color Correction | 30+ |\n"
            "| 模糊锐化 | Blur & Sharpen | 15+ |\n"
        )
        blocks = self.parser.parse(md)
        tables = [b for b in blocks if b.block_type == BlockType.TABLE]
        self.assertEqual(len(tables), 1)
        # 表格内容应包含原始行
        self.assertIn("色彩校正", tables[0].content)

    def test_parse_empty_input(self) -> None:
        """空输入返回空列表"""
        blocks = self.parser.parse("")
        self.assertEqual(blocks, [])

    def test_parse_file(self) -> None:
        """从文件解析"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write("# 测试标题\n\n段落内容\n")
            f.flush()
            path = f.name

        try:
            blocks = self.parser.parse_file(path)
            headings = [b for b in blocks if b.block_type == BlockType.HEADING]
            self.assertEqual(len(headings), 1)
            self.assertEqual(headings[0].content, "测试标题")
        finally:
            os.unlink(path)

    def test_block_order_preserved(self) -> None:
        """块顺序与原文一致"""
        md = "# 标题\n\n段落\n\n---\n\n```\ncode\n```\n\n- list"
        blocks = self.parser.parse(md)
        types = [b.block_type for b in blocks]
        self.assertEqual(types[0], BlockType.HEADING)
        self.assertIn(BlockType.PARAGRAPH, types)
        self.assertIn(BlockType.HR, types)
        self.assertIn(BlockType.CODE_BLOCK, types)


class TestMdParserEdgeCases(unittest.TestCase):
    """md_parser 边界情况测试。"""

    def setUp(self) -> None:
        from knowledge_base.md_parser import MdParser
        self.parser = MdParser()

    def test_nested_bold_italic(self) -> None:
        """段落中包含粗体/斜体标记（保留原文）"""
        md = "这是**粗体**和*斜体*文本"
        blocks = self.parser.parse(md)
        paras = [b for b in blocks if b.block_type == BlockType.PARAGRAPH]
        self.assertEqual(len(paras), 1)
        self.assertIn("**粗体**", paras[0].content)

    def test_chinese_content(self) -> None:
        """中文内容正确解析"""
        md = "# 高斯模糊\n\n模糊效果包括：高斯模糊、径向模糊、方框模糊。"
        blocks = self.parser.parse(md)
        self.assertGreater(len(blocks), 0)
        headings = [b for b in blocks if b.block_type == BlockType.HEADING]
        self.assertEqual(headings[0].content, "高斯模糊")

    def test_table_with_pipes_in_content(self) -> None:
        """表格内容中包含管道符转义"""
        md = (
            "| 名称 | 说明 |\n"
            "|------|------|\n"
            "| test | a \\| b |\n"
        )
        blocks = self.parser.parse(md)
        tables = [b for b in blocks if b.block_type == BlockType.TABLE]
        self.assertGreaterEqual(len(tables), 1)

    def test_multiline_paragraph(self) -> None:
        """连续行属于同一段落"""
        md = "第一行\n第二行\n第三行"
        blocks = self.parser.parse(md)
        paras = [b for b in blocks if b.block_type == BlockType.PARAGRAPH]
        self.assertEqual(len(paras), 1)
        self.assertIn("第一行", paras[0].content)
        self.assertIn("第三行", paras[0].content)


if __name__ == "__main__":
    unittest.main()
