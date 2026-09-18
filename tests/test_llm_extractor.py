#!/usr/bin/env python3
"""
tests/test_llm_extractor.py - LLM 知识提取测试 (Phase 4)

TDD: 使用 mock 验证 LLM 提取逻辑。
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from knowledge_base.types import BlockType, KnowledgeItem, MdBlock


class TestLlmExtractor(unittest.TestCase):
    """llm_extractor 测试（mock LLM）。"""

    def setUp(self) -> None:
        from knowledge_base.llm_extractor import LlmExtractor
        self.extractor = LlmExtractor()

    def test_extract_from_paragraph(self) -> None:
        """从段落中提取知识（mock LLM 返回）"""
        mock_response = json.dumps([
            {
                "keyword": "胶片颗粒",
                "match_name": "ADBE Add Grain",
                "category": "noise",
            },
            {
                "keyword": "发光效果",
                "match_name": "ADBE Glo2",
                "category": "glow",
            },
        ])

        with patch.object(self.extractor, "_call_llm", return_value=mock_response):
            block = MdBlock(
                block_type=BlockType.PARAGRAPH,
                content="AE中常用的噪点和发光效果包括胶片颗粒和发光效果。",
            )
            items = self.extractor.extract_effects(block, source_file="test.md")

        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].keyword, "胶片颗粒")
        self.assertEqual(items[0].match_name, "ADBE Add Grain")
        self.assertEqual(items[0].extracted_by, "llm")

    def test_extract_returns_empty_on_invalid_json(self) -> None:
        """LLM 返回无效 JSON 时返回空列表"""
        with patch.object(self.extractor, "_call_llm", return_value="not json"):
            block = MdBlock(
                block_type=BlockType.PARAGRAPH,
                content="一些文本内容",
            )
            items = self.extractor.extract_effects(block, source_file="test.md")

        self.assertEqual(items, [])

    def test_extract_returns_empty_on_empty_response(self) -> None:
        """LLM 返回空字符串时返回空列表"""
        with patch.object(self.extractor, "_call_llm", return_value=""):
            block = MdBlock(
                block_type=BlockType.PARAGRAPH,
                content="一些文本内容",
            )
            items = self.extractor.extract_effects(block, source_file="test.md")

        self.assertEqual(items, [])

    def test_skip_table_blocks(self) -> None:
        """表格块不经过 LLM（已由规则引擎处理）"""
        block = MdBlock(
            block_type=BlockType.TABLE,
            content="| A | B |\n|---|---|\n| 1 | 2 |",
        )
        items = self.extractor.extract_effects(block, source_file="test.md")
        self.assertEqual(items, [])

    def test_skip_code_blocks(self) -> None:
        """代码块不经过 LLM"""
        block = MdBlock(
            block_type=BlockType.CODE_BLOCK,
            content="var x = 1;",
            metadata={"language": "javascript"},
        )
        items = self.extractor.extract_effects(block, source_file="test.md")
        self.assertEqual(items, [])

    def test_offline_mode(self) -> None:
        """离线模式下不调用 LLM"""
        os.environ["AEK_OFFLINE_MODE"] = "1"
        try:
            from knowledge_base.llm_extractor import LlmExtractor
            extractor = LlmExtractor()
            block = MdBlock(
                block_type=BlockType.PARAGRAPH,
                content="一些文本内容",
            )
            items = extractor.extract_effects(block, source_file="test.md")
            self.assertEqual(items, [])
        finally:
            del os.environ["AEK_OFFLINE_MODE"]

    def test_batch_extract(self) -> None:
        """批量提取多个段落"""
        mock_responses = [
            json.dumps([{"keyword": "模糊", "match_name": "ADBE Gaussian Blur 2", "category": "blur"}]),
            json.dumps([{"keyword": "发光", "match_name": "ADBE Glo2", "category": "glow"}]),
        ]
        call_count = [0]

        def mock_call_llm(prompt: str) -> str:
            idx = call_count[0]
            call_count[0] += 1
            if idx < len(mock_responses):
                return mock_responses[idx]
            return "[]"

        with patch.object(self.extractor, "_call_llm", side_effect=mock_call_llm):
            blocks = [
                MdBlock(block_type=BlockType.PARAGRAPH, content="关于模糊效果的描述，包括高斯模糊和径向模糊等多种类型"),
                MdBlock(block_type=BlockType.PARAGRAPH, content="关于发光效果的描述，包括Glow和Deep Glow等插件效果"),
            ]
            all_items = self.extractor.batch_extract_effects(blocks, source_file="test.md")

        self.assertEqual(len(all_items), 2)

    def test_confidence_field(self) -> None:
        """提取结果包含置信度字段"""
        mock_response = json.dumps([
            {"keyword": "模糊", "match_name": "ADBE Gaussian Blur 2", "category": "blur", "confidence": 0.9},
        ])
        with patch.object(self.extractor, "_call_llm", return_value=mock_response):
            block = MdBlock(block_type=BlockType.PARAGRAPH, content="模糊效果是AE中常用的视觉效果类型之一")
            items = self.extractor.extract_effects(block, source_file="test.md")

        self.assertEqual(len(items), 1)
        self.assertAlmostEqual(items[0].confidence, 0.9)


if __name__ == "__main__":
    unittest.main()
