#!/usr/bin/env python3
"""
tests/test_table_extractor.py - 表格提取器测试 (Phase 1)

TDD: 先定义行为，再实现 table_extractor.py
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from knowledge_base.types import BlockType, MdBlock, TableRow


class TestTableExtractor(unittest.TestCase):
    """table_extractor 测试。"""

    def setUp(self) -> None:
        from knowledge_base.table_extractor import TableExtractor
        self.extractor = TableExtractor()

    def test_extract_basic_table(self) -> None:
        """提取基础 Markdown 表格"""
        table_block = MdBlock(
            block_type=BlockType.TABLE,
            content=(
                "| 类别 | 英文名 | 效果数量 |\n"
                "|------|--------|--------|\n"
                "| 色彩校正 | Color Correction | 30+ |\n"
                "| 模糊锐化 | Blur & Sharpen | 15+ |"
            ),
        )
        rows = self.extractor.extract(table_block)
        self.assertEqual(len(rows), 2)
        self.assertIsInstance(rows[0], TableRow)
        self.assertEqual(rows[0].columns["类别"], "色彩校正")
        self.assertEqual(rows[0].columns["英文名"], "Color Correction")
        self.assertEqual(rows[1].columns["类别"], "模糊锐化")

    def test_extract_table_with_empty_cells(self) -> None:
        """提取包含空单元格的表格"""
        table_block = MdBlock(
            block_type=BlockType.TABLE,
            content=(
                "| A | B | C |\n"
                "|---|---|---|\n"
                "| 1 |   | 3 |\n"
                "|   | 2 |   |"
            ),
        )
        rows = self.extractor.extract(table_block)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].columns["A"], "1")
        self.assertEqual(rows[0].columns["B"].strip(), "")
        self.assertEqual(rows[0].columns["C"], "3")

    def test_extract_table_preserves_header(self) -> None:
        """表头正确映射"""
        table_block = MdBlock(
            block_type=BlockType.TABLE,
            content=(
                "| 效果名称 | matchName | 分类 |\n"
                "|---------|-----------|------|\n"
                "| 高斯模糊 | ADBE Gaussian Blur 2 | blur |"
            ),
        )
        rows = self.extractor.extract(table_block)
        self.assertEqual(len(rows), 1)
        self.assertIn("效果名称", rows[0].columns)
        self.assertEqual(rows[0].columns["效果名称"], "高斯模糊")
        self.assertEqual(rows[0].columns["matchName"], "ADBE Gaussian Blur 2")

    def test_extract_non_table_returns_empty(self) -> None:
        """非表格块返回空列表"""
        para_block = MdBlock(block_type=BlockType.PARAGRAPH, content="普通段落")
        rows = self.extractor.extract(para_block)
        self.assertEqual(rows, [])

    def test_extract_table_with_bold_content(self) -> None:
        """表格内容包含粗体标记（去除标记）"""
        table_block = MdBlock(
            block_type=BlockType.TABLE,
            content=(
                "| 名称 | 说明 |\n"
                "|------|------|\n"
                "| **发光** | 边缘发光效果 |"
            ),
        )
        rows = self.extractor.extract(table_block)
        self.assertEqual(len(rows), 1)
        # 粗体标记应被去除
        self.assertNotIn("**", rows[0].columns["名称"])
        self.assertEqual(rows[0].columns["名称"], "发光")

    def test_extract_from_blocks_list(self) -> None:
        """从多个块中提取所有表格"""
        blocks = [
            MdBlock(block_type=BlockType.HEADING, content="标题", level=1),
            MdBlock(
                block_type=BlockType.TABLE,
                content=(
                    "| A | B |\n"
                    "|---|---|\n"
                    "| 1 | 2 |"
                ),
            ),
            MdBlock(block_type=BlockType.PARAGRAPH, content="段落"),
            MdBlock(
                block_type=BlockType.TABLE,
                content=(
                    "| X | Y |\n"
                    "|---|---|\n"
                    "| 3 | 4 |"
                ),
            ),
        ]
        all_rows = self.extractor.extract_all(blocks)
        self.assertEqual(len(all_rows), 2)  # 两个表格
        self.assertEqual(len(all_rows[0]), 1)  # 第一个表格1行
        self.assertEqual(len(all_rows[1]), 1)  # 第二个表格1行

    def test_extract_table_with_pipe_escape(self) -> None:
        """处理转义管道符"""
        table_block = MdBlock(
            block_type=BlockType.TABLE,
            content=(
                "| 名称 | 说明 |\n"
                "|------|------|\n"
                "| test | a \\| b |"
            ),
        )
        rows = self.extractor.extract(table_block)
        self.assertEqual(len(rows), 1)
        # 转义管道符应被保留为普通字符
        self.assertIn("|", rows[0].columns["说明"])

    def test_extract_table_no_separator(self) -> None:
        """没有分隔行的表格（只有表头）"""
        table_block = MdBlock(
            block_type=BlockType.TABLE,
            content="| A | B | C |",
        )
        rows = self.extractor.extract(table_block)
        # 没有数据行，返回空
        self.assertEqual(len(rows), 0)

    def test_extract_table_strips_whitespace(self) -> None:
        """单元格内容去除首尾空格"""
        table_block = MdBlock(
            block_type=BlockType.TABLE,
            content=(
                "|  A  |  B  |\n"
                "|-----|-----|\n"
                "|  1  |  2  |"
            ),
        )
        rows = self.extractor.extract(table_block)
        self.assertEqual(rows[0].columns["A"], "1")
        self.assertEqual(rows[0].columns["B"], "2")


if __name__ == "__main__":
    unittest.main()
