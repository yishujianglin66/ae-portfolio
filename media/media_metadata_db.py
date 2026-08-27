#!/usr/bin/env python3
"""
素材元数据 SQLite 数据库 (D1a)

替代 JSON 文件索引，提供高效的素材元数据存储与查询。

架构：
    SQLite 负责元数据（路径/时长/BPM/情绪/曲风/标签等）
    FAISS 负责向量相似度检索（见 vector_index_faiss.py）

用法：
    from media_metadata_db import MediaMetadataDB

    db = MediaMetadataDB()
    db.add_item("/path/to/video.mp4", duration=120.5, bpm=128, mood="energetic")
    results = db.search(mood="energetic", min_duration=60)
    stats = db.get_stats()

迁移：
    python media_metadata_db.py --migrate-from-json path/to/index.json
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# 默认数据库路径
_PROJECT_ROOT = Path(__file__).resolve().parent
_DEFAULT_DB_PATH = _PROJECT_ROOT / "data" / "media_metadata.db"


@dataclass
class MediaItem:
    """素材元数据记录"""
    id: int = 0
    file_path: str = ""
    file_name: str = ""
    file_type: str = ""        # video / audio / image
    file_ext: str = ""         # mp4 / mp3 / wav / png ...
    file_size: int = 0         # bytes
    duration: float = 0.0      # seconds
    width: int = 0
    height: int = 0
    fps: float = 0.0
    bpm: float = 0.0
    mood: str = ""
    mood_score: float = 0.0
    genre: str = ""
    key: str = ""              # 调性
    mode: str = ""             # major / minor
    energy: float = 0.0
    tags: str = ""             # 逗号分隔标签
    source_platform: str = ""  # douyin / bilibili / youtube / pexels ...
    download_url: str = ""
    thumbnail_path: str = ""
    created_at: str = ""
    updated_at: str = ""
    extra: str = "{}"          # JSON 扩展字段

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}


# SQL 建表语句
_SCHEMA = """
CREATE TABLE IF NOT EXISTS media_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path   TEXT UNIQUE NOT NULL,
    file_name   TEXT NOT NULL DEFAULT '',
    file_type   TEXT NOT NULL DEFAULT '',
    file_ext    TEXT NOT NULL DEFAULT '',
    file_size   INTEGER DEFAULT 0,
    duration    REAL DEFAULT 0.0,
    width       INTEGER DEFAULT 0,
    height      INTEGER DEFAULT 0,
    fps         REAL DEFAULT 0.0,
    bpm         REAL DEFAULT 0.0,
    mood        TEXT DEFAULT '',
    mood_score  REAL DEFAULT 0.0,
    genre       TEXT DEFAULT '',
    key         TEXT DEFAULT '',
    mode        TEXT DEFAULT '',
    energy      REAL DEFAULT 0.0,
    tags        TEXT DEFAULT '',
    source_platform TEXT DEFAULT '',
    download_url TEXT DEFAULT '',
    thumbnail_path TEXT DEFAULT '',
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT DEFAULT (datetime('now')),
    extra       TEXT DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_file_type ON media_items(file_type);
CREATE INDEX IF NOT EXISTS idx_mood ON media_items(mood);
CREATE INDEX IF NOT EXISTS idx_genre ON media_items(genre);
CREATE INDEX IF NOT EXISTS idx_bpm ON media_items(bpm);
CREATE INDEX IF NOT EXISTS idx_source_platform ON media_items(source_platform);
CREATE INDEX IF NOT EXISTS idx_duration ON media_items(duration);
CREATE INDEX IF NOT EXISTS idx_file_ext ON media_items(file_ext);
"""


class MediaMetadataDB:
    """素材元数据 SQLite 数据库"""

    def __init__(self, db_path: Optional[str] = None):
        self._db_path = db_path or str(_DEFAULT_DB_PATH)
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._init_schema()

    def _init_schema(self):
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    @contextmanager
    def _transaction(self):
        try:
            yield self._conn
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    def _row_to_item(self, row: sqlite3.Row) -> MediaItem:
        return MediaItem(**{k: row[k] for k in row.keys()})

    # ------------------------------------------------------------------
    # CRUD 操作
    # ------------------------------------------------------------------

    def add_item(self, file_path: str, **kwargs) -> int:
        """添加素材记录，返回 ID。如已存在则更新。"""
        kwargs["file_path"] = file_path
        kwargs["file_name"] = kwargs.get("file_name", os.path.basename(file_path))
        kwargs["file_ext"] = kwargs.get("file_ext", os.path.splitext(file_path)[1].lstrip(".").lower())
        kwargs["updated_at"] = _now_iso()

        if "file_type" not in kwargs:
            kwargs["file_type"] = _guess_file_type(kwargs["file_ext"])

        columns = ", ".join(kwargs.keys())
        placeholders = ", ".join(["?"] * len(kwargs))
        values = list(kwargs.values())

        with self._transaction():
            cursor = self._conn.execute(
                f"INSERT INTO media_items ({columns}) VALUES ({placeholders}) "
                f"ON CONFLICT(file_path) DO UPDATE SET {', '.join(f'{k}=excluded.{k}' for k in kwargs.keys() if k != 'file_path')}",
                values,
            )
            return cursor.lastrowid

    def add_items_batch(self, items: List[Dict[str, Any]]) -> int:
        """批量添加，返回添加数量。"""
        count = 0
        with self._transaction():
            for item_data in items:
                file_path = item_data.get("file_path", "")
                if not file_path:
                    continue
                item_data["file_name"] = item_data.get("file_name", os.path.basename(file_path))
                item_data["file_ext"] = item_data.get("file_ext", os.path.splitext(file_path)[1].lstrip(".").lower())
                item_data["updated_at"] = _now_iso()
                if "file_type" not in item_data:
                    item_data["file_type"] = _guess_file_type(item_data["file_ext"])

                columns = ", ".join(item_data.keys())
                placeholders = ", ".join(["?"] * len(item_data))
                values = list(item_data.values())

                self._conn.execute(
                    f"INSERT INTO media_items ({columns}) VALUES ({placeholders}) "
                    f"ON CONFLICT(file_path) DO UPDATE SET {', '.join(f'{k}=excluded.{k}' for k in item_data.keys() if k != 'file_path')}",
                    values,
                )
                count += 1
        return count

    def get_item(self, item_id: int) -> Optional[MediaItem]:
        row = self._conn.execute("SELECT * FROM media_items WHERE id=?", (item_id,)).fetchone()
        return self._row_to_item(row) if row else None

    def get_item_by_path(self, file_path: str) -> Optional[MediaItem]:
        row = self._conn.execute("SELECT * FROM media_items WHERE file_path=?", (file_path,)).fetchone()
        return self._row_to_item(row) if row else None

    def delete_item(self, item_id: int) -> bool:
        with self._transaction():
            cursor = self._conn.execute("DELETE FROM media_items WHERE id=?", (item_id,))
            return cursor.rowcount > 0

    def delete_by_path(self, file_path: str) -> bool:
        with self._transaction():
            cursor = self._conn.execute("DELETE FROM media_items WHERE file_path=?", (file_path,))
            return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # 搜索
    # ------------------------------------------------------------------

    def search(
        self,
        file_type: str = "",
        mood: str = "",
        genre: str = "",
        platform: str = "",
        min_duration: float = 0,
        max_duration: float = 0,
        min_bpm: float = 0,
        max_bpm: float = 0,
        tags_contain: str = "",
        ext: str = "",
        limit: int = 50,
        offset: int = 0,
        order_by: str = "updated_at DESC",
    ) -> List[MediaItem]:
        """条件搜索素材"""
        conditions = []
        params: list = []

        if file_type:
            conditions.append("file_type = ?")
            params.append(file_type)
        if mood:
            conditions.append("mood = ?")
            params.append(mood)
        if genre:
            conditions.append("genre = ?")
            params.append(genre)
        if platform:
            conditions.append("source_platform = ?")
            params.append(platform)
        if min_duration > 0:
            conditions.append("duration >= ?")
            params.append(min_duration)
        if max_duration > 0:
            conditions.append("duration <= ?")
            params.append(max_duration)
        if min_bpm > 0:
            conditions.append("bpm >= ?")
            params.append(min_bpm)
        if max_bpm > 0:
            conditions.append("bpm <= ?")
            params.append(max_bpm)
        if tags_contain:
            conditions.append("tags LIKE ?")
            params.append(f"%{tags_contain}%")
        if ext:
            conditions.append("file_ext = ?")
            params.append(ext.lower())

        where = " AND ".join(conditions) if conditions else "1=1"
        # 安全排序
        allowed_orders = {
            "updated_at DESC", "updated_at ASC",
            "created_at DESC", "created_at ASC",
            "duration DESC", "duration ASC",
            "bpm DESC", "bpm ASC",
            "file_name ASC", "file_name DESC",
        }
        if order_by not in allowed_orders:
            order_by = "updated_at DESC"

        sql = f"SELECT * FROM media_items WHERE {where} ORDER BY {order_by} LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_item(r) for r in rows]

    def full_text_search(self, query: str, limit: int = 20) -> List[MediaItem]:
        """全文搜索（文件名/标签/情绪/曲风）"""
        like = f"%{query}%"
        sql = """
            SELECT * FROM media_items
            WHERE file_name LIKE ? OR tags LIKE ? OR mood LIKE ? OR genre LIKE ? OR source_platform LIKE ?
            ORDER BY updated_at DESC LIMIT ?
        """
        rows = self._conn.execute(sql, (like, like, like, like, like, limit)).fetchall()
        return [self._row_to_item(r) for r in rows]

    # ------------------------------------------------------------------
    # 统计
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        """获取素材库统计信息"""
        total = self._conn.execute("SELECT COUNT(*) FROM media_items").fetchone()[0]
        by_type = dict(self._conn.execute(
            "SELECT file_type, COUNT(*) FROM media_items GROUP BY file_type"
        ).fetchall())
        by_ext = dict(self._conn.execute(
            "SELECT file_ext, COUNT(*) FROM media_items GROUP BY file_ext ORDER BY COUNT(*) DESC"
        ).fetchall())
        by_mood = dict(self._conn.execute(
            "SELECT mood, COUNT(*) FROM media_items WHERE mood != '' GROUP BY mood ORDER BY COUNT(*) DESC"
        ).fetchall())
        by_platform = dict(self._conn.execute(
            "SELECT source_platform, COUNT(*) FROM media_items WHERE source_platform != '' GROUP BY source_platform ORDER BY COUNT(*) DESC"
        ).fetchall())
        avg_duration = self._conn.execute("SELECT AVG(duration) FROM media_items WHERE duration > 0").fetchone()[0] or 0
        total_size = self._conn.execute("SELECT SUM(file_size) FROM media_items").fetchone()[0] or 0

        return {
            "total_items": total,
            "by_type": by_type,
            "by_ext": by_ext,
            "by_mood": by_mood,
            "by_platform": by_platform,
            "avg_duration": round(avg_duration, 2),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "db_path": self._db_path,
        }

    # ------------------------------------------------------------------
    # JSON 迁移
    # ------------------------------------------------------------------

    def migrate_from_json_index(self, json_path: str) -> Dict[str, int]:
        """从 CLIP index.json 迁移数据到 SQLite"""
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        items = data.get("items", [])
        count = 0
        for item in items:
            file_path = item.get("file_path", "")
            if not file_path:
                continue
            metadata = item.get("metadata", {})
            self.add_item(
                file_path=file_path,
                duration=metadata.get("duration", 0),
                bpm=metadata.get("bpm", 0),
                mood=metadata.get("mood", ""),
                genre=metadata.get("genre", ""),
                key=metadata.get("key", ""),
                mode=metadata.get("mode", ""),
                energy=metadata.get("energy", 0),
                tags=metadata.get("tags", ""),
                source_platform=metadata.get("source_platform", metadata.get("source", "")),
                extra=json.dumps({"vector_dim": data.get("vector_dim", 0)}, ensure_ascii=False),
            )
            count += 1

        return {"migrated": count, "total_in_json": len(items)}

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None


# ------------------------------------------------------------------
# 工具函数
# ------------------------------------------------------------------

def _now_iso() -> str:
    from datetime import datetime
    return datetime.now().isoformat(timespec="seconds")


def _guess_file_type(ext: str) -> str:
    video_exts = {"mp4", "mov", "avi", "mkv", "webm", "flv", "wmv", "m4v"}
    audio_exts = {"mp3", "wav", "flac", "aac", "ogg", "m4a", "wma", "aiff"}
    image_exts = {"jpg", "jpeg", "png", "gif", "bmp", "tiff", "webp", "psd", "ai"}
    ext = ext.lower()
    if ext in video_exts:
        return "video"
    if ext in audio_exts:
        return "audio"
    if ext in image_exts:
        return "image"
    return "other"


# ------------------------------------------------------------------
# CLI 入口
# ------------------------------------------------------------------

def _cli_main():
    import argparse
    parser = argparse.ArgumentParser(description="素材元数据 SQLite 数据库")
    parser.add_argument("--db", type=str, help="数据库路径")
    parser.add_argument("--stats", action="store_true", help="显示统计")
    parser.add_argument("--search", type=str, help="全文搜索")
    parser.add_argument("--migrate-from-json", type=str, help="从 JSON 索引迁移")
    parser.add_argument("--add", type=str, help="添加文件路径")
    parser.add_argument("--list", action="store_true", help="列出所有素材")
    args = parser.parse_args()

    db = MediaMetadataDB(args.db)

    if args.stats:
        print(json.dumps(db.get_stats(), ensure_ascii=False, indent=2))
    elif args.search:
        results = db.full_text_search(args.search)
        for item in results:
            print(f"  {item.file_name} [{item.file_type}] {item.duration:.1f}s mood={item.mood}")
        print(f"共 {len(results)} 条结果")
    elif args.migrate_from_json:
        result = db.migrate_from_json_index(args.migrate_from_json)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.add:
        item_id = db.add_item(args.add)
        print(f"已添加: id={item_id}")
    elif args.list:
        items = db.search(limit=100)
        for item in items:
            print(f"  [{item.id}] {item.file_name} ({item.file_type}/{item.file_ext}) {item.duration:.1f}s")
    else:
        parser.print_help()

    db.close()


if __name__ == "__main__":
    _cli_main()
