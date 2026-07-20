#!/usr/bin/env python3
"""
tests/test_kb_loader.py - 知识库门面集成测试 (Phase 3)

TDD: 验证 KnowledgeBaseLoader 整合所有层。
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestKnowledgeBaseLoader(unittest.TestCase):
    """KnowledgeBaseLoader 门面测试。"""

    def setUp(self) -> None:
        """创建临时知识库目录和测试文件。"""
        from knowledge_base.kb_loader import KnowledgeBaseLoader

        self.tmp_dir = tempfile.mkdtemp()
        self.kb_dir = os.path.join(self.tmp_dir, "knowledge_base")
        os.makedirs(self.kb_dir)

        # 创建测试知识库文件
        self._create_test_file(
            "效果映射表.md",
            (
                "# 效果映射\n\n"
                "## 模糊效果\n\n"
                "| 关键词 | matchName | 分类 |\n"
                "|--------|-----------|------|\n"
                "| 模糊 | ADBE Gaussian Blur 2 | blur |\n"
                "| 高斯模糊 | ADBE Gaussian Blur 2 | blur |\n\n"
                "## 发光效果\n\n"
                "| 关键词 | matchName | 分类 |\n"
                "|--------|-----------|------|\n"
                "| 发光 | ADBE Glo2 | glow |\n"
            ),
        )
        self._create_test_file(
            "转场配方.md",
            (
                "# 转场配方\n\n"
                "| 转场类型 | 显示名 | 效果match |\n"
                "|---------|--------|----------|\n"
                "| linear_wipe | 线性擦除 | ADBE Linear Wipe |\n"
                "| fade | 淡入淡出 | opacity |\n"
            ),
        )

        self.loader = KnowledgeBaseLoader(
            kb_dir=self.kb_dir,
            cache_dir=os.path.join(self.tmp_dir, "cache"),
        )

    def _create_test_file(self, name: str, content: str) -> None:
        path = os.path.join(self.kb_dir, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def test_get_effect_map(self) -> None:
        """获取效果映射字典"""
        effect_map = self.loader.get_effect_map()
        self.assertIsInstance(effect_map, dict)
        self.assertIn("模糊", effect_map)
        self.assertEqual(effect_map["模糊"], "ADBE Gaussian Blur 2")
        self.assertIn("发光", effect_map)

    def test_get_transition_map(self) -> None:
        """获取转场配方字典"""
        trans_map = self.loader.get_transition_map()
        self.assertIsInstance(trans_map, dict)
        self.assertIn("linear_wipe", trans_map)
        self.assertEqual(trans_map["linear_wipe"]["display_name"], "线性擦除")

    def test_get_all_files(self) -> None:
        """获取所有知识库文件列表"""
        files = self.loader.list_files()
        self.assertEqual(len(files), 2)

    def test_parse_single_file(self) -> None:
        """解析单个文件"""
        blocks = self.loader.parse_file("效果映射表.md")
        self.assertGreater(len(blocks), 0)

    def test_get_color_presets(self) -> None:
        """获取调色预设（可能为空）"""
        presets = self.loader.get_color_presets()
        self.assertIsInstance(presets, list)

    def test_get_style_recipes(self) -> None:
        """获取风格配方（可能为空）"""
        recipes = self.loader.get_style_recipes()
        self.assertIsInstance(recipes, list)

    def test_empty_kb_dir(self) -> None:
        """空知识库目录不报错"""
        empty_dir = os.path.join(self.tmp_dir, "empty_kb")
        os.makedirs(empty_dir)
        from knowledge_base.kb_loader import KnowledgeBaseLoader
        loader = KnowledgeBaseLoader(kb_dir=empty_dir)
        effect_map = loader.get_effect_map()
        self.assertEqual(effect_map, {})

    def test_nonexistent_kb_dir(self) -> None:
        """不存在的路径不报错"""
        from knowledge_base.kb_loader import KnowledgeBaseLoader
        loader = KnowledgeBaseLoader(kb_dir="/nonexistent/path")
        effect_map = loader.get_effect_map()
        self.assertEqual(effect_map, {})

    def test_effect_map_with_fallback(self) -> None:
        """效果映射与 fallback 合并"""
        fallback = {"模糊": "ADBE Gaussian Blur 2", "新效果": "NEW_FX"}
        merged = self.loader.get_effect_map(fallback=fallback)
        # 知识库映射 + fallback 补充
        self.assertIn("模糊", merged)
        self.assertIn("发光", merged)
        self.assertIn("新效果", merged)


class TestKnowledgeBaseLoaderSingleton(unittest.TestCase):
    """KnowledgeBaseLoader 单例模式测试。"""

    def test_singleton_returns_same_instance(self) -> None:
        """get_instance 返回同一实例"""
        from knowledge_base.kb_loader import KnowledgeBaseLoader
        # 清除已有实例
        KnowledgeBaseLoader._instance = None
        a = KnowledgeBaseLoader.get_instance()
        b = KnowledgeBaseLoader.get_instance()
        self.assertIs(a, b)
        # 清理
        KnowledgeBaseLoader._instance = None


if __name__ == "__main__":
    unittest.main()
