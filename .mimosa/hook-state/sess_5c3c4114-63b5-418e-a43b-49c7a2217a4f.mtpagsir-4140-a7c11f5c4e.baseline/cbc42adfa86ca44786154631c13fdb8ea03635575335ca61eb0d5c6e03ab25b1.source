#!/usr/bin/env python3
"""
持久化记忆系统 - MemoryStore v1.0

设计参考：cavemem (JuliusBrussee/cavemem)
- SQLite + FTS5 全文检索
- 跨会话上下文积累
- 执行经验学习与复用

集成方式：
    from core.memory_store import memory_store

    # 存储执行经验
    memory_store.remember(
        category="roto_execution",
        key="埼玉_抠像",
        content={"method": "RotoNode", "frames": 18, "success": True},
        tags=["roto", "silhouette"]
    )

    # 检索相关记忆
    results = memory_store.search("roto 抠像", limit=5)

    # 获取相似任务的经验
    exp = memory_store.get_experience("silhouette", "roto")
"""
import json
import logging
import os
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class MemoryEntry:
    """记忆条目"""
    id: int = 0
    category: str = ""
    key: str = ""
    content: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    confidence: float = 0.5
    created_at: float = 0.0
    accessed_at: float = 0.0
    access_count: int = 0
    success_count: int = 0
    failure_count: int = 0


class MemoryStore:
    """
    持久化记忆系统

    特性：
    1. SQLite 存储：跨会话持久化
    2. FTS5 全文检索：快速搜索相关记忆
    3. 置信度学习：根据成功/失败自动调整
    4. 经验复用：相似任务自动推荐历史经验
    5. 衰减机制：长时间未访问的记忆降低权重
    """

    def __init__(self, db_path: Optional[str] = None):
        self._logger = logging.getLogger(f"{__name__}.MemoryStore")

        if db_path is None:
            db_dir = os.path.expanduser("~/.ae-knowledge-vault")
            os.makedirs(db_dir, exist_ok=True)
            db_path = os.path.join(db_dir, "memory.db")

        self._db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _init_db(self) -> None:
        """初始化数据库"""
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                key TEXT NOT NULL,
                content TEXT NOT NULL,
                tags TEXT DEFAULT '',
                confidence REAL DEFAULT 0.5,
                created_at REAL DEFAULT 0,
                accessed_at REAL DEFAULT 0,
                access_count INTEGER DEFAULT 0,
                success_count INTEGER DEFAULT 0,
                failure_count INTEGER DEFAULT 0,
                UNIQUE(category, key)
            );

            CREATE INDEX IF NOT EXISTS idx_memories_category
                ON memories(category);
            CREATE INDEX IF NOT EXISTS idx_memories_tags
                ON memories(tags);
        """)

        # FTS5 全文检索表
        try:
            self._conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts
                USING fts5(category, key, content, tags,
                           content='memories',
                           content_rowid='id')
            """)
            self._conn.execute("""
                CREATE TRIGGER IF NOT EXISTS memories_ai
                AFTER INSERT ON memories
                BEGIN
                    INSERT INTO memories_fts(rowid, category, key, content, tags)
                    VALUES (new.id, new.category, new.key, new.content, new.tags);
                END
            """)
            self._conn.execute("""
                CREATE TRIGGER IF NOT EXISTS memories_ad
                AFTER DELETE ON memories
                BEGIN
                    INSERT INTO memories_fts(memories_fts, rowid, category, key, content, tags)
                    VALUES ('delete', old.id, old.category, old.key, old.content, old.tags);
                END
            """)
            self._conn.execute("""
                CREATE TRIGGER IF NOT EXISTS memories_au
                AFTER UPDATE ON memories
                BEGIN
                    INSERT INTO memories_fts(memories_fts, rowid, category, key, content, tags)
                    VALUES ('delete', old.id, old.category, old.key, old.content, old.tags);
                    INSERT INTO memories_fts(rowid, category, key, content, tags)
                    VALUES (new.id, new.category, new.key, new.content, new.tags);
                END
            """)
        except sqlite3.OperationalError:
            self._logger.warning("FTS5 不可用，降级为 LIKE 查询")

        self._conn.commit()
        self._logger.info(f"记忆系统已初始化: {self._db_path}")

    # -------------------------------------------------------------------------
    # 核心操作
    # -------------------------------------------------------------------------

    def remember(
        self,
        category: str,
        key: str,
        content: Dict[str, Any],
        tags: Optional[List[str]] = None,
        confidence: float = 0.5,
    ) -> int:
        """
        存储或更新记忆

        Args:
            category: 记忆类别（如 "roto_execution", "effect_planning"）
            key: 唯一键（如 "埼玉_抠像"）
            content: 记忆内容
            tags: 标签列表
            confidence: 初始置信度 (0-1)

        Returns:
            记忆 ID
        """
        tags_str = ",".join(tags) if tags else ""
        content_str = json.dumps(content, ensure_ascii=False)
        now = time.time()

        cursor = self._conn.execute(
            """
            INSERT INTO memories (category, key, content, tags, confidence,
                                  created_at, accessed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(category, key) DO UPDATE SET
                content = excluded.content,
                tags = excluded.tags,
                confidence = MAX(memories.confidence, excluded.confidence),
                accessed_at = excluded.accessed_at
            """,
            (category, key, content_str, tags_str, confidence, now, now)
        )
        self._conn.commit()

        memory_id = cursor.lastrowid
        self._logger.debug(f"记忆已存储: [{category}] {key} (id={memory_id})")
        return memory_id or 0

    def recall(self, category: str, key: str) -> Optional[MemoryEntry]:
        """精确检索记忆"""
        row = self._conn.execute(
            "SELECT * FROM memories WHERE category = ? AND key = ?",
            (category, key)
        ).fetchone()

        if row is None:
            return None

        mem_id = row["id"]

        # 更新访问统计
        self._conn.execute(
            "UPDATE memories SET accessed_at = ?, access_count = access_count + 1 WHERE id = ?",
            (time.time(), mem_id)
        )
        self._conn.commit()

        updated_row = self._conn.execute(
            "SELECT * FROM memories WHERE id = ?",
            (mem_id,)
        ).fetchone()

        return self._row_to_entry(updated_row)

    def search(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 10,
    ) -> List[MemoryEntry]:
        """
        全文检索记忆

        Args:
            query: 搜索关键词
            category: 限定类别（None 则搜索全部）
            limit: 返回数量上限
        """
        results: List[MemoryEntry] = []

        # 尝试 FTS5 搜索
        try:
            if category:
                sql = """
                    SELECT m.* FROM memories m
                    JOIN memories_fts f ON m.id = f.rowid
                    WHERE memories_fts MATCH ? AND m.category = ?
                    ORDER BY rank
                    LIMIT ?
                """
                rows = self._conn.execute(sql, (query, category, limit)).fetchall()
            else:
                sql = """
                    SELECT m.* FROM memories m
                    JOIN memories_fts f ON m.id = f.rowid
                    WHERE memories_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                """
                rows = self._conn.execute(sql, (query, limit)).fetchall()

            results = [self._row_to_entry(r) for r in rows]
        except sqlite3.OperationalError:
            # FTS5 不可用，降级为 LIKE
            pattern = f"%{query}%"
            if category:
                sql = """
                    SELECT * FROM memories
                    WHERE (content LIKE ? OR key LIKE ? OR tags LIKE ?)
                      AND category = ?
                    ORDER BY accessed_at DESC
                    LIMIT ?
                """
                rows = self._conn.execute(
                    sql, (pattern, pattern, pattern, category, limit)
                ).fetchall()
            else:
                sql = """
                    SELECT * FROM memories
                    WHERE content LIKE ? OR key LIKE ? OR tags LIKE ?
                    ORDER BY accessed_at DESC
                    LIMIT ?
                """
                rows = self._conn.execute(
                    sql, (pattern, pattern, pattern, limit)
                ).fetchall()

            results = [self._row_to_entry(r) for r in rows]

        return results

    def forget(self, category: str, key: str) -> bool:
        """删除记忆"""
        cursor = self._conn.execute(
            "DELETE FROM memories WHERE category = ? AND key = ?",
            (category, key)
        )
        self._conn.commit()
        deleted = cursor.rowcount > 0
        if deleted:
            self._logger.debug(f"记忆已删除: [{category}] {key}")
        return deleted

    # -------------------------------------------------------------------------
    # 经验学习
    # -------------------------------------------------------------------------

    def record_outcome(
        self,
        category: str,
        key: str,
        success: bool,
    ) -> None:
        """
        记录执行结果，更新置信度

        Args:
            category: 记忆类别
            key: 记忆键
            success: 是否成功
        """
        entry = self.recall(category, key)
        if entry is None:
            return

        if success:
            new_success = entry.success_count + 1
            new_failure = entry.failure_count
        else:
            new_success = entry.success_count
            new_failure = entry.failure_count + 1

        total = new_success + new_failure
        # 置信度 = 成功次数 / 总次数，带衰减
        base_confidence = new_success / max(total, 1)

        # 时间衰减：最近访问的记忆权重更高
        age_days = (time.time() - entry.accessed_at) / 86400
        decay = max(0.3, 1.0 - age_days * 0.01)  # 每天衰减 1%，最低 30%

        new_confidence = base_confidence * decay

        self._conn.execute(
            """
            UPDATE memories
            SET success_count = ?, failure_count = ?, confidence = ?
            WHERE id = ?
            """,
            (new_success, new_failure, new_confidence, entry.id)
        )
        self._conn.commit()

    def get_experience(
        self,
        category: str,
        task_keyword: str = "",
        limit: int = 5,
        min_confidence: float = 0.3,
    ) -> List[MemoryEntry]:
        """
        获取相关经验

        Args:
            category: 记忆类别
            task_keyword: 任务关键词
            limit: 返回数量
            min_confidence: 最低置信度阈值
        """
        if task_keyword:
            entries = self.search(task_keyword, category=category, limit=limit * 2)
        else:
            rows = self._conn.execute(
                """
                SELECT * FROM memories
                WHERE category = ? AND confidence >= ?
                ORDER BY confidence DESC, access_count DESC
                LIMIT ?
                """,
                (category, min_confidence, limit * 2)
            ).fetchall()
            entries = [self._row_to_entry(r) for r in rows]

        # 过滤置信度
        entries = [e for e in entries if e.confidence >= min_confidence]

        return entries[:limit]

    # -------------------------------------------------------------------------
    # 统计
    # -------------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        """获取记忆系统统计"""
        row = self._conn.execute(
            "SELECT COUNT(*) as count, "
            "AVG(confidence) as avg_confidence, "
            "SUM(success_count) as total_success, "
            "SUM(failure_count) as total_failure "
            "FROM memories"
        ).fetchone()

        categories = self._conn.execute(
            "SELECT category, COUNT(*) as count "
            "FROM memories GROUP BY category ORDER BY count DESC"
        ).fetchall()

        return {
            "total_memories": row["count"] if row else 0,
            "avg_confidence": round(row["avg_confidence"], 3) if row and row["avg_confidence"] is not None else 0.0,
            "total_success": row["total_success"] if row and row["total_success"] is not None else 0,
            "total_failure": row["total_failure"] if row and row["total_failure"] is not None else 0,
            "categories": {
                r["category"]: r["count"] for r in categories
            } if categories else {},
        }

    def close(self) -> None:
        """关闭数据库"""
        if self._conn:
            self._conn.close()
            self._conn = None
            self._logger.info("记忆系统已关闭")

    # -------------------------------------------------------------------------
    # 内部方法
    # -------------------------------------------------------------------------

    def _row_to_entry(self, row: sqlite3.Row) -> MemoryEntry:
        """数据库行转 MemoryEntry"""
        try:
            content = json.loads(row["content"]) if row["content"] else {}
        except (json.JSONDecodeError, TypeError):
            content = {"raw": row["content"]}

        tags = row["tags"].split(",") if row["tags"] else []

        return MemoryEntry(
            id=row["id"],
            category=row["category"],
            key=row["key"],
            content=content,
            tags=[t.strip() for t in tags if t.strip()],
            confidence=row["confidence"],
            created_at=row["created_at"],
            accessed_at=row["accessed_at"],
            access_count=row["access_count"],
            success_count=row["success_count"],
            failure_count=row["failure_count"],
        )


# -----------------------------------------------------------------------------
# 全局实例
# -----------------------------------------------------------------------------

memory_store = MemoryStore()
