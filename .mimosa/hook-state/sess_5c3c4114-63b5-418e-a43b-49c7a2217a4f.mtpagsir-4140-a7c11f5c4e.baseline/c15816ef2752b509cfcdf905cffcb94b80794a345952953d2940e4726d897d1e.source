#!/usr/bin/env python3
"""
tests/test_kb_cache.py - 知识库缓存测试 (Phase 3)

TDD: 验证基于 mtime + hash 的增量缓存。
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestKbCache(unittest.TestCase):
    """kb_cache 测试。"""

    def setUp(self) -> None:
        from knowledge_base.kb_cache import KbCache
        self.tmp_dir = tempfile.mkdtemp()
        self.cache = KbCache(cache_dir=self.tmp_dir)

    def test_cache_miss(self) -> None:
        """缓存未命中返回 None"""
        result = self.cache.get("/nonexistent/file.md")
        self.assertIsNone(result)

    def test_cache_set_and_get(self) -> None:
        """设置和获取缓存"""
        data = {"key": "value", "list": [1, 2, 3]}
        self.cache.set("/test/file.md", data, mtime=1000.0)
        result = self.cache.get("/test/file.md")
        self.assertIsNotNone(result)
        self.assertEqual(result["key"], "value")
        self.assertEqual(result["list"], [1, 2, 3])

    def test_cache_invalidate_on_mtime_change(self) -> None:
        """文件 mtime 变化时缓存失效"""
        self.cache.set("/test/file.md", {"data": "old"}, mtime=1000.0)
        # mtime 变化 → 缓存失效
        result = self.cache.get("/test/file.md", mtime=2000.0)
        self.assertIsNone(result)

    def test_cache_hit_same_mtime(self) -> None:
        """mtime 相同时缓存命中"""
        self.cache.set("/test/file.md", {"data": "value"}, mtime=1000.0)
        result = self.cache.get("/test/file.md", mtime=1000.0)
        self.assertIsNotNone(result)
        self.assertEqual(result["data"], "value")

    def test_cache_persistence(self) -> None:
        """缓存持久化到磁盘"""
        from knowledge_base.kb_cache import KbCache

        self.cache.set("/test/file.md", {"data": "persist"}, mtime=1000.0)
        self.cache.save()

        # 创建新实例读取同一缓存目录
        cache2 = KbCache(cache_dir=self.tmp_dir)
        cache2.load()
        result = cache2.get("/test/file.md", mtime=1000.0)
        self.assertIsNotNone(result)
        self.assertEqual(result["data"], "persist")

    def test_cache_clear(self) -> None:
        """清空缓存"""
        self.cache.set("/test/file1.md", {"data": "1"}, mtime=1000.0)
        self.cache.set("/test/file2.md", {"data": "2"}, mtime=1000.0)
        self.cache.clear()
        self.assertIsNone(self.cache.get("/test/file1.md"))
        self.assertIsNone(self.cache.get("/test/file2.md"))

    def test_cache_file_check(self) -> None:
        """检查文件是否需要重新解析"""
        # 创建临时文件
        fd, path = tempfile.mkstemp(suffix=".md")
        os.close(fd)
        with open(path, "w", encoding="utf-8") as f:
            f.write("# test")

        try:
            mtime = os.path.getmtime(path)
            self.cache.set(path, {"data": "cached"}, mtime=mtime)

            # 未修改 → 不需要重新解析
            self.assertFalse(self.cache.needs_reparse(path))

            # 修改文件 → 需要重新解析
            time.sleep(0.1)
            with open(path, "w", encoding="utf-8") as f:
                f.write("# modified")
            self.assertTrue(self.cache.needs_reparse(path))
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
