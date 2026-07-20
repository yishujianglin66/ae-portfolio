#!/usr/bin/env python3
"""
tests/test_kb_scanner.py - 知识库多线程扫描器测试

使用临时目录和已知内容测试 KBScanner 的各项提取与扫描功能，
不依赖真实知识库目录。
"""
from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from kb_scanner import KBScanner


class TestKBScannerInit(unittest.TestCase):
    """KBScanner 初始化测试。"""

    def test_initial_state(self) -> None:
        """初始化后状态为空"""
        scanner = KBScanner()
        self.assertEqual(scanner._files, [])
        self.assertEqual(scanner._results, {})
        self.assertIsInstance(scanner._lock, type(threading.Lock()))
        self.assertEqual(scanner._total_files, 0)
        self.assertEqual(scanner._processed, 0)


class TestExtractTables(unittest.TestCase):
    """_extract_tables 表格提取测试。"""

    def setUp(self) -> None:
        self.scanner = KBScanner()

    def test_valid_table(self) -> None:
        """提取标准 Markdown 表格"""
        content = (
            "| 类别 | 英文名 | 数量 |\n"
            "|------|--------|------|\n"
            "| 色彩校正 | Color Correction | 30+ |\n"
            "| 模糊锐化 | Blur & Sharpen | 15+ |"
        )
        tables = self.scanner._extract_tables(content)
        self.assertEqual(len(tables), 1)
        self.assertIn("类别", tables[0]["header"])
        self.assertEqual(len(tables[0]["rows"]), 2)

    def test_multiple_tables(self) -> None:
        """提取多个表格"""
        content = (
            "| A | B |\n|---|---|\n| 1 | 2 |\n\n"
            "一些文字\n\n"
            "| X | Y |\n|---|---|\n| 3 | 4 |"
        )
        tables = self.scanner._extract_tables(content)
        self.assertEqual(len(tables), 2)

    def test_no_tables(self) -> None:
        """无表格内容返回空列表"""
        content = "# 标题\n\n普通段落，没有表格。"
        tables = self.scanner._extract_tables(content)
        self.assertEqual(tables, [])

    def test_malformed_table_no_separator(self) -> None:
        """缺少分隔行的内容不匹配表格"""
        content = "| A | B |\n| 1 | 2 |"
        tables = self.scanner._extract_tables(content)
        self.assertEqual(tables, [])

    def test_malformed_table_only_separator(self) -> None:
        """仅有分隔行不匹配表格"""
        content = "|---|---|"
        tables = self.scanner._extract_tables(content)
        self.assertEqual(tables, [])


class TestExtractCodeBlocks(unittest.TestCase):
    """_extract_code_blocks 代码块提取测试。"""

    def setUp(self) -> None:
        self.scanner = KBScanner()

    def test_jsx_code_block(self) -> None:
        """提取 jsx 代码块"""
        content = "```jsx\napp.project.item(1).layer(1).effect(1).property(1).setValue(100);\n```"
        blocks = self.scanner._extract_code_blocks(content)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["lang"], "jsx")

    def test_python_code_block(self) -> None:
        """提取 python 代码块"""
        content = "```python\nprint('hello')\n```"
        blocks = self.scanner._extract_code_blocks(content)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["lang"], "python")

    def test_text_code_block_no_lang(self) -> None:
        """无语言标记的代码块默认为 text"""
        content = "```\nsome plain code\nmore lines\n```"
        blocks = self.scanner._extract_code_blocks(content)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["lang"], "text")

    def test_multiple_code_blocks(self) -> None:
        """提取多个代码块"""
        content = (
            "```jsx\nvar x = 1;\n```\n\n"
            "说明文字\n\n"
            "```python\nprint(x)\n```"
        )
        blocks = self.scanner._extract_code_blocks(content)
        self.assertEqual(len(blocks), 2)
        langs = {b["lang"] for b in blocks}
        self.assertIn("jsx", langs)
        self.assertIn("python", langs)

    def test_no_code_blocks(self) -> None:
        """无代码块返回空列表"""
        content = "普通文本，没有代码块。"
        blocks = self.scanner._extract_code_blocks(content)
        self.assertEqual(blocks, [])

    def test_code_block_line_count(self) -> None:
        """代码块行数统计"""
        content = "```python\nline1\nline2\nline3\n```"
        blocks = self.scanner._extract_code_blocks(content)
        self.assertEqual(blocks[0]["lines"], 3)


class TestExtractEffects(unittest.TestCase):
    """_extract_effects AE 效果关键词提取测试。"""

    def setUp(self) -> None:
        self.scanner = KBScanner()

    def test_adbe_prefixed(self) -> None:
        """提取 ADBE 前缀效果"""
        content = "ADBE Gaussian Blur 和 ADBE Glo 都是内置效果"
        effects = self.scanner._extract_effects(content)
        self.assertGreater(len(effects), 0)
        effect_str = " ".join(effects)
        self.assertIn("ADBE Gaussian Blur", effect_str)

    def test_cc_prefixed(self) -> None:
        """提取 CC 前缀效果"""
        content = "CC Cylinder 用于3D效果"
        effects = self.scanner._extract_effects(content)
        self.assertGreater(len(effects), 0)
        self.assertIn("CC Cylinder", effects)

    def test_bcc_prefixed(self) -> None:
        """提取 BCC 前缀效果（BCC 后接空格+字母下划线）"""
        content = "BCC Gaussian_Blur 是第三方效果"
        effects = self.scanner._extract_effects(content)
        self.assertGreater(len(effects), 0)
        self.assertIn("BCC Gaussian_Blur", effects)

    def test_mixed_prefixes(self) -> None:
        """混合前缀效果提取"""
        content = (
            "ADBE Gaussian Blur 2, CC Cylinder, "
            "TC Barrell, VC Reflect, "
            "BCC_Gaussian_Blur, RB Corner "
            "都是常见效果"
        )
        effects = self.scanner._extract_effects(content)
        self.assertGreaterEqual(len(effects), 4)

    def test_no_effects(self) -> None:
        """无效果关键词返回空列表"""
        content = "这是一段普通文本，没有任何效果关键词。"
        effects = self.scanner._extract_effects(content)
        self.assertEqual(effects, [])


class TestExtractTransitions(unittest.TestCase):
    """_extract_transitions 转场类型提取测试。"""

    def setUp(self) -> None:
        self.scanner = KBScanner()

    def test_wipe_transition(self) -> None:
        """提取 wipe 转场"""
        content = "线性擦除 Linear Wipe 效果"
        transitions = self.scanner._extract_transitions(content)
        self.assertIn("wipe", transitions)

    def test_dissolve_transition(self) -> None:
        """提取 dissolve 转场"""
        content = "交叉溶解 Cross Dissolve"
        transitions = self.scanner._extract_transitions(content)
        self.assertIn("dissolve", transitions)

    def test_case_insensitive(self) -> None:
        """转场关键词不区分大小写"""
        content = "FADE 过渡效果"
        transitions = self.scanner._extract_transitions(content)
        self.assertIn("fade", transitions)

    def test_multiple_transitions(self) -> None:
        """提取多个转场类型"""
        content = "使用 wipe 或 dissolve 或 fade 进行转场，也可以用 glitch 和 zoom"
        transitions = self.scanner._extract_transitions(content)
        self.assertGreaterEqual(len(transitions), 5)

    def test_no_transitions(self) -> None:
        """无转场关键词返回空列表"""
        content = "普通内容，没有任何转场描述。"
        transitions = self.scanner._extract_transitions(content)
        self.assertEqual(transitions, [])


class TestExtractColorPresets(unittest.TestCase):
    """_extract_color_presets 调色预设名称提取测试。"""

    def setUp(self) -> None:
        self.scanner = KBScanner()

    def test_chinese_preset_name(self) -> None:
        """提取中文调色预设名称"""
        content = "使用赛博朋克调色预设可以快速上色"
        presets = self.scanner._extract_color_presets(content)
        self.assertGreater(len(presets), 0)

    def test_multiple_presets(self) -> None:
        """提取多个预设名称"""
        content = "推荐复古调色预设和电影感风格以及HDR预设"
        presets = self.scanner._extract_color_presets(content)
        self.assertGreaterEqual(len(presets), 1)

    def test_no_presets(self) -> None:
        """无调色预设返回空列表"""
        content = "普通文本，没有相关关键字。"
        presets = self.scanner._extract_color_presets(content)
        self.assertEqual(presets, [])


class TestExtractTags(unittest.TestCase):
    """_extract_tags YAML frontmatter 标签提取测试。"""

    def setUp(self) -> None:
        self.scanner = KBScanner()

    def test_valid_tags(self) -> None:
        """提取有效的 YAML tags"""
        content = "---\ntags: [\"模糊\", \"效果\", \"AE\"]\n---\n\n# 标题"
        tags = self.scanner._extract_tags(content)
        self.assertEqual(len(tags), 3)
        self.assertIn("模糊", tags)
        self.assertIn("效果", tags)
        self.assertIn("AE", tags)

    def test_missing_tags(self) -> None:
        """无 tags 字段返回空列表"""
        content = "---\ntitle: 测试\n---\n\n# 标题"
        tags = self.scanner._extract_tags(content)
        self.assertEqual(tags, [])

    def test_no_frontmatter(self) -> None:
        """无 frontmatter 返回空列表"""
        content = "# 标题\n\n段落内容"
        tags = self.scanner._extract_tags(content)
        self.assertEqual(tags, [])

    def test_malformed_tags(self) -> None:
        """格式错误的 tags 返回空列表"""
        content = "---\ntags: not-a-json-array\n---\n\n# 标题"
        tags = self.scanner._extract_tags(content)
        self.assertEqual(tags, [])


class TestScanFile(unittest.TestCase):
    """_scan_file 单文件扫描测试。"""

    def setUp(self) -> None:
        self.scanner = KBScanner()
        self.tmp_dir = tempfile.mkdtemp()

    def _create_file(self, name: str, content: str) -> str:
        path = os.path.join(self.tmp_dir, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def test_scan_file_with_all_features(self) -> None:
        """扫描包含表格、代码块、效果的文件"""
        path = self._create_file("full.md", (
            "---\ntags: [\"测试\"]\n---\n\n"
            "# 效果文档\n\n"
            "| 参数 | 值 |\n|-----|-----|\n| a | 1 |\n\n"
            "```jsx\napp.project;\n```\n\n"
            "ADBE Gaussian Blur 2 效果\n"
            "使用 wipe 转场\n"
            "复古调色预设"
        ))
        self.scanner._scan_file(path)
        # _scan_file 使用 KB_ROOT 做 relpath，此处直接检查 _results 有内容
        self.assertEqual(len(self.scanner._results), 1)
        key = os.path.basename(path)
        result = self.scanner._results[key]
        self.assertIn("tables", result)
        self.assertIn("code_blocks", result)
        self.assertIn("effects_found", result)
        self.assertIn("tags", result)

    def test_scan_nonexistent_file(self) -> None:
        """扫描不存在的文件不崩溃，结果为空"""
        self.scanner._scan_file("/nonexistent/file.md")
        self.assertEqual(len(self.scanner._results), 0)

    def test_scan_empty_file(self) -> None:
        """扫描空文件"""
        path = self._create_file("empty.md", "")
        self.scanner._scan_file(path)
        self.assertEqual(len(self.scanner._results), 1)
        key = os.path.basename(path)
        self.assertEqual(self.scanner._results[key]["size"], 0)
        self.assertEqual(self.scanner._results[key]["lines"], 0)


class TestDiscoverFiles(unittest.TestCase):
    """discover_files 文件发现测试。"""

    def setUp(self) -> None:
        self.scanner = KBScanner()
        self.tmp_dir = tempfile.mkdtemp()

    def test_discover_in_temp_dir(self) -> None:
        """在临时目录中发现 MD 文件（需临时替换 KB_ROOT）"""
        import kb_scanner as mod
        original_root = mod.KB_ROOT
        try:
            mod.KB_ROOT = self.tmp_dir
            self.scanner.discover_files()
            self.assertEqual(self.scanner._total_files, 0)
            # 创建测试文件
            for name in ["a.md", "b.md", "c.txt"]:
                with open(os.path.join(self.tmp_dir, name), "w", encoding="utf-8") as f:
                    f.write("# test")
            self.scanner.discover_files()
            self.assertEqual(self.scanner._total_files, 2)  # 仅 .md
        finally:
            mod.KB_ROOT = original_root


class TestScanParallel(unittest.TestCase):
    """scan_parallel 多线程扫描测试。"""

    def setUp(self) -> None:
        self.scanner = KBScanner()
        self.tmp_dir = tempfile.mkdtemp()
        # 创建一组临时 MD 文件
        for i in range(6):
            path = os.path.join(self.tmp_dir, f"test_{i}.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"# 文件{i}\n\nADBE Gaussian Blur {i}\n")

    def test_parallel_scan(self) -> None:
        """多线程扫描临时文件"""
        import kb_scanner as mod
        original_root = mod.KB_ROOT
        try:
            mod.KB_ROOT = self.tmp_dir
            self.scanner.discover_files()
            self.assertEqual(self.scanner._total_files, 6)
            results = self.scanner.scan_parallel(threads=3)
            self.assertEqual(len(results), 6)
        finally:
            mod.KB_ROOT = original_root

    def test_thread_safety(self) -> None:
        """并发写入 _results 字典线程安全（无数据丢失）"""
        import kb_scanner as mod
        original_root = mod.KB_ROOT
        try:
            mod.KB_ROOT = self.tmp_dir
            self.scanner.discover_files()
            self.scanner.scan_parallel(threads=4)
            # 所有文件结果都应存在
            self.assertEqual(len(self.scanner._results), self.scanner._total_files)
            self.assertEqual(self.scanner._processed, self.scanner._total_files)
        finally:
            mod.KB_ROOT = original_root


class TestGenerateReport(unittest.TestCase):
    """generate_report 报告生成测试。"""

    def test_empty_report(self) -> None:
        """空结果生成报告"""
        scanner = KBScanner()
        scanner._total_files = 0
        scanner._processed = 0
        report = scanner.generate_report()
        self.assertEqual(report["total_files"], 0)
        self.assertEqual(report["scanned_files"], 0)
        self.assertEqual(report["stats"]["total_size"], 0)
        self.assertEqual(report["stats"]["total_lines"], 0)
        self.assertEqual(report["stats"]["files_with_tables"], 0)
        self.assertEqual(report["stats"]["files_with_code"], 0)
        self.assertEqual(report["stats"]["files_with_effects"], 0)
        self.assertEqual(report["top_effect_files"], [])
        self.assertEqual(report["top_table_files"], [])
        self.assertEqual(report["files_by_category"], {})

    def test_populated_report(self) -> None:
        """有扫描结果时生成报告"""
        scanner = KBScanner()
        scanner._total_files = 2
        scanner._processed = 2
        scanner._results = {
            "effects.md": {
                "filename": "effects.md",
                "rel_path": "subdir/effects.md",
                "size": 500,
                "lines": 20,
                "effects_found": 3,
                "tables": 1,
            },
            "code.md": {
                "filename": "code.md",
                "rel_path": "code.md",
                "size": 300,
                "lines": 15,
                "code_blocks": 2,
            },
        }
        report = scanner.generate_report()
        self.assertEqual(report["total_files"], 2)
        self.assertEqual(report["scanned_files"], 2)
        self.assertEqual(report["stats"]["total_size"], 800)
        self.assertEqual(report["stats"]["total_lines"], 35)
        self.assertEqual(report["stats"]["files_with_tables"], 1)
        self.assertEqual(report["stats"]["files_with_code"], 1)
        self.assertEqual(report["stats"]["files_with_effects"], 1)
        # 效果文件排名
        self.assertEqual(len(report["top_effect_files"]), 1)
        self.assertEqual(report["top_effect_files"][0][0], "effects.md")
        self.assertEqual(report["top_effect_files"][0][1], 3)
        # 表格文件排名
        self.assertEqual(len(report["top_table_files"]), 1)
        self.assertEqual(report["top_table_files"][0][0], "effects.md")
        self.assertEqual(report["top_table_files"][0][1], 1)
        # 分类
        self.assertIn("subdir", report["files_by_category"])
        self.assertIn("root", report["files_by_category"])


class TestConcurrentAccess(unittest.TestCase):
    """并发访问线程安全性测试。"""

    def test_concurrent_scan_file_writes(self) -> None:
        """多线程同时调用 _scan_file 不丢数据"""
        scanner = KBScanner()
        tmp_dir = tempfile.mkdtemp()
        files = []
        for i in range(20):
            path = os.path.join(tmp_dir, f"concurrent_{i}.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"# 文件{i}\n\nADBE Test Effect {i}\n")
            files.append(path)

        threads = []
        for f in files:
            t = threading.Thread(target=scanner._scan_file, args=(f,))
            threads.append(t)
            t.start()
        for t in threads:
            t.join()

        # 所有 20 个文件结果都应存在
        self.assertEqual(len(scanner._results), 20)
        self.assertEqual(scanner._processed, 20)

    def test_lock_prevents_corruption(self) -> None:
        """_lock 确保 _processed 计数准确"""
        scanner = KBScanner()
        scanner._total_files = 50
        tmp_dir = tempfile.mkdtemp()
        files = []
        for i in range(50):
            path = os.path.join(tmp_dir, f"lock_{i}.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"# {i}\n")
            files.append(path)

        threads = []
        for f in files:
            t = threading.Thread(target=scanner._scan_file, args=(f,))
            threads.append(t)
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(scanner._processed, 50)
        self.assertEqual(len(scanner._results), 50)


if __name__ == "__main__":
    unittest.main()
