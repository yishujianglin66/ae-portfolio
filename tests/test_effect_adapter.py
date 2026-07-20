#!/usr/bin/env python3
"""
tests/test_effect_adapter.py - 效果映射适配器测试 (Phase 2)

TDD: 验证 effect_adapter 输出与 KEYWORD_TO_EFFECT_MAP 格式兼容。
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from knowledge_base.types import BlockType, MdBlock, EffectMapping


class TestEffectAdapter(unittest.TestCase):
    """effect_adapter 测试。"""

    def setUp(self) -> None:
        from knowledge_base.adapters.effect_adapter import EffectAdapter
        self.adapter = EffectAdapter()

    def test_extract_from_table_block(self) -> None:
        """从表格块中提取效果映射"""
        table_block = MdBlock(
            block_type=BlockType.TABLE,
            content=(
                "| 关键词 | matchName | 分类 |\n"
                "|--------|-----------|------|\n"
                "| 模糊 | ADBE Gaussian Blur 2 | blur |\n"
                "| 发光 | ADBE Glo2 | glow |"
            ),
        )
        mappings = self.adapter.extract_from_blocks(
            [table_block], source_file="test.md"
        )
        self.assertEqual(len(mappings), 2)
        self.assertEqual(mappings[0].keyword, "模糊")
        self.assertEqual(mappings[0].match_name, "ADBE Gaussian Blur 2")
        self.assertEqual(mappings[0].category, "blur")
        self.assertEqual(mappings[0].source_file, "test.md")

    def test_to_dict_format(self) -> None:
        """输出 Dict[str, str] 格式与 KEYWORD_TO_EFFECT_MAP 兼容"""
        mappings = [
            EffectMapping(keyword="模糊", match_name="ADBE Gaussian Blur 2", category="blur"),
            EffectMapping(keyword="发光", match_name="ADBE Glo2", category="glow"),
        ]
        result = self.adapter.to_dict(mappings)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["模糊"], "ADBE Gaussian Blur 2")
        self.assertEqual(result["发光"], "ADBE Glo2")

    def test_extract_from_multiple_tables(self) -> None:
        """从多个表格中提取映射"""
        blocks = [
            MdBlock(
                block_type=BlockType.TABLE,
                content=(
                    "| 关键词 | matchName |\n"
                    "|--------|----------|\n"
                    "| 模糊 | ADBE Gaussian Blur 2 |"
                ),
            ),
            MdBlock(
                block_type=BlockType.TABLE,
                content=(
                    "| 关键词 | matchName |\n"
                    "|--------|----------|\n"
                    "| 发光 | ADBE Glo2 |"
                ),
            ),
        ]
        mappings = self.adapter.extract_from_blocks(blocks)
        self.assertEqual(len(mappings), 2)

    def test_extract_from_section_with_keywords(self) -> None:
        """从包含关键词列表的段落中提取映射"""
        blocks = [
            MdBlock(
                block_type=BlockType.PARAGRAPH,
                content="- **模糊** → ADBE Gaussian Blur 2\n- **发光** → ADBE Glo2",
            ),
        ]
        mappings = self.adapter.extract_from_text_blocks(blocks)
        self.assertGreaterEqual(len(mappings), 2)
        keywords = [m.keyword for m in mappings]
        self.assertIn("模糊", keywords)
        self.assertIn("发光", keywords)

    def test_merge_with_fallback(self) -> None:
        """合并知识库映射与硬编码 fallback"""
        kb_mappings = [
            EffectMapping(keyword="模糊", match_name="ADBE Gaussian Blur 2"),
            EffectMapping(keyword="新效果", match_name="NEW_EFFECT"),
        ]
        fallback = {
            "模糊": "ADBE Gaussian Blur 2",
            "发光": "ADBE Glo2",
        }
        merged = self.adapter.merge_with_fallback(kb_mappings, fallback)
        # 知识库映射优先，fallback 补充
        self.assertIn("模糊", merged)
        self.assertIn("新效果", merged)
        self.assertIn("发光", merged)
        self.assertEqual(merged["新效果"], "NEW_EFFECT")

    def test_empty_input(self) -> None:
        """空输入返回空映射"""
        mappings = self.adapter.extract_from_blocks([])
        self.assertEqual(mappings, [])
        result = self.adapter.to_dict(mappings)
        self.assertEqual(result, {})

    def test_skip_rows_without_matchname(self) -> None:
        """跳过没有 matchName 列的表格"""
        table_block = MdBlock(
            block_type=BlockType.TABLE,
            content=(
                "| 名称 | 说明 |\n"
                "|------|------|\n"
                "| 模糊 | 一种效果 |"
            ),
        )
        mappings = self.adapter.extract_from_blocks([table_block])
        # 没有 matchName 列，应返回空
        self.assertEqual(mappings, [])


class TestEffectAdapterRealKB(unittest.TestCase):
    """effect_adapter 对真实知识库文件的测试。"""

    def setUp(self) -> None:
        from knowledge_base.adapters.effect_adapter import EffectAdapter
        self.adapter = EffectAdapter()

    def test_parse_effect_table_from_kb(self) -> None:
        """解析包含效果映射的表格"""
        # 模拟知识库中常见的效果映射表格
        md_content = (
            "## 效果matchName映射表\n\n"
            "| 效果名称 | matchName | 属性数 |\n"
            "|---------|-----------|-------|\n"
            "| Gaussian Blur | ADBE Gaussian Blur 2 | 3 |\n"
            "| Lumetri Color | ADBE Lumetri Color | 9 |\n"
        )
        from knowledge_base.md_parser import MdParser
        parser = MdParser()
        blocks = parser.parse(md_content)

        mappings = self.adapter.extract_from_blocks(blocks, source_file="test_kb.md")
        self.assertEqual(len(mappings), 2)
        self.assertEqual(mappings[0].match_name, "ADBE Gaussian Blur 2")


if __name__ == "__main__":
    unittest.main()
