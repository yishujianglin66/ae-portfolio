#!/usr/bin/env python3
"""
tests/test_transition_adapter.py - 转场配方适配器测试 (Phase 2)

TDD: 验证 transition_adapter 输出与 TRANSITION_IMPL_MAP 格式兼容。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from knowledge_base.types import BlockType, MdBlock, TransitionRecipe


class TestTransitionAdapter(unittest.TestCase):
    """transition_adapter 测试。"""

    def setUp(self) -> None:
        from knowledge_base.adapters.transition_adapter import TransitionAdapter
        self.adapter = TransitionAdapter()

    def test_extract_from_table_block(self) -> None:
        """从表格块中提取转场配方"""
        table_block = MdBlock(
            block_type=BlockType.TABLE,
            content=(
                "| 转场类型 | 显示名 | 效果match | 参数 |\n"
                "|---------|--------|-----------|------|\n"
                "| linear_wipe | 线性擦除 | ADBE Linear Wipe | Wipe Angle=0, Feather=30 |\n"
                "| fade | 淡入淡出 | opacity | |"
            ),
        )
        recipes = self.adapter.extract_from_blocks(
            [table_block], source_file="test.md"
        )
        self.assertGreaterEqual(len(recipes), 2)
        self.assertEqual(recipes[0].transition_type, "linear_wipe")
        self.assertEqual(recipes[0].display_name, "线性擦除")
        self.assertEqual(recipes[0].effect_match, "ADBE Linear Wipe")

    def test_to_dict_format(self) -> None:
        """输出 Dict[str, Dict[str, Any]] 格式与 TRANSITION_IMPL_MAP 兼容"""
        recipes = [
            TransitionRecipe(
                transition_type="linear_wipe",
                display_name="线性擦除",
                effect_match="ADBE Linear Wipe",
                params={"Wipe Angle": 0, "Feather": 30},
                animate={"Transition Completion": {"from": 0, "to": 100}},
            ),
        ]
        result = self.adapter.to_dict(recipes)
        self.assertIsInstance(result, dict)
        self.assertIn("linear_wipe", result)
        self.assertEqual(result["linear_wipe"]["display_name"], "线性擦除")
        self.assertEqual(result["linear_wipe"]["effect_match"], "ADBE Linear Wipe")
        self.assertIn("Wipe Angle", result["linear_wipe"]["params"])

    def test_extract_from_key_value_section(self) -> None:
        """从 key-value 格式的章节中提取转场配方"""
        blocks = [
            MdBlock(
                block_type=BlockType.PARAGRAPH,
                content=(
                    "- **linear_wipe**: display_name=线性擦除, effect=ADBE Linear Wipe\n"
                    "- **fade**: display_name=淡入淡出, effect=opacity"
                ),
            ),
        ]
        recipes = self.adapter.extract_from_text_blocks(blocks)
        self.assertGreaterEqual(len(recipes), 2)

    def test_merge_with_fallback(self) -> None:
        """合并知识库配方与硬编码 fallback"""
        kb_recipes = [
            TransitionRecipe(
                transition_type="linear_wipe",
                display_name="线性擦除",
                effect_match="ADBE Linear Wipe",
                params={"Wipe Angle": 0},
            ),
        ]
        fallback = {
            "linear_wipe": {
                "display_name": "线性擦除",
                "effect_match": "ADBE Linear Wipe",
                "params": {"Wipe Angle": 0, "Feather": 30},
                "animate": {"Transition Completion": {"from": 0, "to": 100}},
            },
            "fade": {
                "display_name": "淡入淡出",
                "type": "opacity_keyframes",
            },
        }
        merged = self.adapter.merge_with_fallback(kb_recipes, fallback)
        # 知识库配方优先，fallback 补充
        self.assertIn("linear_wipe", merged)
        self.assertIn("fade", merged)

    def test_empty_input(self) -> None:
        """空输入返回空配方"""
        recipes = self.adapter.extract_from_blocks([])
        self.assertEqual(recipes, [])

    def test_transition_type_snake_case(self) -> None:
        """转场类型转为 snake_case"""
        table_block = MdBlock(
            block_type=BlockType.TABLE,
            content=(
                "| 转场类型 | 显示名 | effect_match |\n"
                "|---------|--------|---------------|\n"
                "| Card Flip | 卡片翻转 | ADBE Card Wipe |"
            ),
        )
        recipes = self.adapter.extract_from_blocks([table_block])
        self.assertEqual(len(recipes), 1)
        # "Card Flip" 应转为 "card_flip"
        self.assertEqual(recipes[0].transition_type, "card_flip")


if __name__ == "__main__":
    unittest.main()
