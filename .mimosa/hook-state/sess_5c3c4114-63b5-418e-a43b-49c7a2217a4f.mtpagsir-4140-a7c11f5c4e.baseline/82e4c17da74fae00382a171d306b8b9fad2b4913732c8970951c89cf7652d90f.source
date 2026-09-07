"""
knowledge_base/kb_cache.py - 知识库文件缓存 (Layer 3)

基于文件 mtime 的增量缓存，避免重复解析未修改的文件。

缓存格式：JSON 文件存储在 cache_dir 中。
首次加载全库约 5-10s，后续缓存命中 <100ms。

用法：
    from knowledge_base.kb_cache import KbCache

    cache = KbCache(cache_dir="data/kb_cache")
    cache.load()

    if cache.needs_reparse("file.md"):
        data = parse("file.md")
        cache.set("file.md", data, mtime=os.path.getmtime("file.md"))
        cache.save()
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional


class KbCache:
    """知识库文件缓存。"""

    def __init__(self, cache_dir: str = "") -> None:
        """初始化缓存。

        Args:
            cache_dir: 缓存目录路径。为空则不持久化。
        """
        self._cache_dir = cache_dir
        self._entries: Dict[str, Dict[str, Any]] = {}
        # entry: {file_path: {"data": ..., "mtime": float, "cached_at": float}}

        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)
            self.load()

    def get(self, file_path: str, mtime: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """获取缓存数据。

        Args:
            file_path: 文件路径
            mtime: 文件当前 mtime。如果与缓存不一致则返回 None。

        Returns:
            缓存的数据，未命中返回 None
        """
        entry = self._entries.get(file_path)
        if entry is None:
            return None

        if mtime is not None:
            cached_mtime = entry.get("mtime", 0)
            if abs(mtime - cached_mtime) > 0.01:
                return None

        return entry.get("data")

    def set(self, file_path: str, data: Dict[str, Any], mtime: float = 0.0) -> None:
        """设置缓存数据。

        Args:
            file_path: 文件路径
            data: 要缓存的数据
            mtime: 文件 mtime
        """
        self._entries[file_path] = {
            "data": data,
            "mtime": mtime,
            "cached_at": time.time(),
        }

    def needs_reparse(self, file_path: str) -> bool:
        """检查文件是否需要重新解析。

        Args:
            file_path: 文件路径

        Returns:
            True 表示需要重新解析（缓存未命中或文件已修改）
        """
        if not os.path.exists(file_path):
            return False

        try:
            current_mtime = os.path.getmtime(file_path)
        except OSError:
            return True

        cached = self.get(file_path, mtime=current_mtime)
        return cached is None

    def clear(self) -> None:
        """清空所有缓存。"""
        self._entries.clear()

    def save(self) -> None:
        """持久化缓存到磁盘。"""
        if not self._cache_dir:
            return

        cache_file = os.path.join(self._cache_dir, "kb_cache.json")
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(self._entries, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def load(self) -> None:
        """从磁盘加载缓存。"""
        if not self._cache_dir:
            return

        cache_file = os.path.join(self._cache_dir, "kb_cache.json")
        if not os.path.exists(cache_file):
            return

        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                self._entries = json.load(f)
        except (OSError, json.JSONDecodeError):
            self._entries = {}
