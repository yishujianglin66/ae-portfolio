#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库持久化模块
================

从 JSON 文件升级到 SQLite，提供结构化数据存储与复杂查询能力。

功能:
- SQLite 数据库管理
- 任务/项目/历史记录持久化
- 插件配置存储
- 复杂查询与索引
- 数据迁移
- 连接池管理
- 事务支持

数据表:
- tasks: 任务记录
- projects: 项目管理
- history: 历史记录
- plugin_configs: 插件配置
- workflow_runs: 工作流运行记录
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

try:
    from logger import get_logger
    _logger = get_logger("database")
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    _logger = logging.getLogger("database")


# ============================================================================
# 数据库配置
# ============================================================================

@dataclass
class DatabaseConfig:
    """数据库配置"""
    db_path: str = "./data/ae_knowledge_vault.db"
    enable_wal: bool = True
    busy_timeout: int = 5000
    journal_mode: str = "WAL"
    foreign_keys: bool = True


# ============================================================================
# 数据库管理器
# ============================================================================

class Database:
    """SQLite 数据库管理器

    提供连接池、事务支持和 CRUD 操作。
    """

    _SCHEMA_VERSION = 1

    _SCHEMA_SQL = """
    -- 任务表
    CREATE TABLE IF NOT EXISTS tasks (
        task_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        task_type TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        priority INTEGER DEFAULT 5,
        progress REAL DEFAULT 0.0,
        progress_message TEXT DEFAULT '',
        config TEXT DEFAULT '{}',
        result TEXT,
        error TEXT,
        retries INTEGER DEFAULT 0,
        max_retries INTEGER DEFAULT 0,
        created_at REAL NOT NULL,
        started_at REAL,
        completed_at REAL,
        duration REAL DEFAULT 0.0,
        metadata TEXT DEFAULT '{}'
    );

    CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
    CREATE INDEX IF NOT EXISTS idx_tasks_type ON tasks(task_type);
    CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(created_at DESC);

    -- 项目表
    CREATE TABLE IF NOT EXISTS projects (
        project_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT DEFAULT '',
        status TEXT NOT NULL DEFAULT 'draft',
        duration REAL DEFAULT 0.0,
        scene_count INTEGER DEFAULT 0,
        width INTEGER DEFAULT 1920,
        height INTEGER DEFAULT 1080,
        frame_rate INTEGER DEFAULT 30,
        scenes TEXT DEFAULT '[]',
        applied_effects TEXT DEFAULT '[]',
        render_output TEXT,
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
    CREATE INDEX IF NOT EXISTS idx_projects_created ON projects(created_at DESC);

    -- 历史记录表
    CREATE TABLE IF NOT EXISTS history (
        record_id TEXT PRIMARY KEY,
        action TEXT NOT NULL,
        result TEXT DEFAULT 'success',
        details TEXT DEFAULT '',
        project_id TEXT,
        params TEXT,
        created_at REAL NOT NULL,
        FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE SET NULL
    );

    CREATE INDEX IF NOT EXISTS idx_history_created ON history(created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_history_result ON history(result);

    -- 插件配置表
    CREATE TABLE IF NOT EXISTS plugin_configs (
        plugin_id TEXT PRIMARY KEY,
        config TEXT DEFAULT '{}',
        enabled INTEGER DEFAULT 0,
        updated_at REAL NOT NULL
    );

    -- 工作流运行记录表
    CREATE TABLE IF NOT EXISTS workflow_runs (
        run_id TEXT PRIMARY KEY,
        workflow_type TEXT NOT NULL,
        task_id TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        current_stage INTEGER DEFAULT 0,
        total_stages INTEGER DEFAULT 0,
        stages TEXT DEFAULT '[]',
        result TEXT,
        error TEXT,
        mode TEXT DEFAULT 'auto',
        created_at REAL NOT NULL,
        started_at REAL,
        completed_at REAL,
        duration REAL DEFAULT 0.0
    );

    CREATE INDEX IF NOT EXISTS idx_workflow_status ON workflow_runs(status);
    CREATE INDEX IF NOT EXISTS idx_workflow_created ON workflow_runs(created_at DESC);

    -- Schema 版本表
    CREATE TABLE IF NOT EXISTS schema_meta (
        key TEXT PRIMARY KEY,
        value TEXT
    );
    """

    def __init__(self, config: DatabaseConfig | None = None):
        self._config = config or DatabaseConfig()
        self._lock = threading.RLock()
        self._local = threading.local()

        Path(self._config.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """获取线程本地连接"""
        if not hasattr(self._local, "connection"):
            conn = sqlite3.connect(
                self._config.db_path,
                timeout=self._config.busy_timeout / 1000.0,
                check_same_thread=False,
            )
            conn.row_factory = sqlite3.Row
            conn.execute(f"PRAGMA journal_mode={self._config.journal_mode}")
            conn.execute(f"PRAGMA busy_timeout={self._config.busy_timeout}")
            if self._config.foreign_keys:
                conn.execute("PRAGMA foreign_keys=ON")
            self._local.connection = conn
        return self._local.connection

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """事务上下文管理器"""
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def _init_db(self):
        """初始化数据库"""
        with self._lock:
            conn = self._get_connection()
            conn.executescript(self._SCHEMA_SQL)
            conn.execute(
                "INSERT OR REPLACE INTO schema_meta (key, value) VALUES (?, ?)",
                ("version", str(self._SCHEMA_VERSION)),
            )
            conn.commit()
            _logger.info(f"数据库已初始化: {self._config.db_path}")

    # --------------------------------------------------------------------
    # 任务 CRUD
    # --------------------------------------------------------------------

    def insert_task(self, task_data: dict[str, Any]) -> str:
        """插入任务"""
        task_id = task_data.get("task_id") or f"task_{uuid.uuid4().hex[:12]}"
        now = time.time()

        with self.transaction() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO tasks
                (task_id, name, task_type, status, priority, progress, progress_message,
                 config, result, error, retries, max_retries,
                 created_at, started_at, completed_at, duration, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    task_id,
                    task_data.get("name", ""),
                    task_data.get("task_type", ""),
                    task_data.get("status", "pending"),
                    task_data.get("priority", 5),
                    task_data.get("progress", 0.0),
                    task_data.get("progress_message", ""),
                    json.dumps(task_data.get("config", {}), ensure_ascii=False),
                    json.dumps(task_data.get("result"), ensure_ascii=False) if task_data.get("result") else None,
                    task_data.get("error"),
                    task_data.get("retries", 0),
                    task_data.get("max_retries", 0),
                    task_data.get("created_at", now),
                    task_data.get("started_at"),
                    task_data.get("completed_at"),
                    task_data.get("duration", 0.0),
                    json.dumps(task_data.get("metadata", {}), ensure_ascii=False),
                ),
            )
        return task_id

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        """获取任务"""
        conn = self._get_connection()
        row = conn.execute(
            "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
        ).fetchone()
        return self._row_to_task(row) if row else None

    def update_task(self, task_id: str, updates: dict[str, Any]) -> bool:
        """更新任务"""
        set_clauses = []
        values = []

        field_map = {
            "name", "task_type", "status", "priority", "progress",
            "progress_message", "result", "error", "retries", "max_retries",
            "started_at", "completed_at", "duration",
        }

        for key, value in updates.items():
            if key in field_map:
                set_clauses.append(f"{key} = ?")
                if key in ("result",) and value is not None:
                    values.append(json.dumps(value, ensure_ascii=False))
                else:
                    values.append(value)
            elif key in ("config", "metadata"):
                set_clauses.append(f"{key} = ?")
                values.append(json.dumps(value, ensure_ascii=False))

        if not set_clauses:
            return False

        set_clauses.append("completed_at = ?")
        values.append(time.time())
        values.append(task_id)

        with self.transaction() as conn:
            conn.execute(
                f"UPDATE tasks SET {', '.join(set_clauses)} WHERE task_id = ?",
                values,
            )
        return True

    def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        with self.transaction() as conn:
            cursor = conn.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
            return cursor.rowcount > 0

    def query_tasks(
        self,
        status: str | None = None,
        task_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """查询任务"""
        query = "SELECT * FROM tasks"
        conditions = []
        params = []

        if status:
            conditions.append("status = ?")
            params.append(status)
        if task_type:
            conditions.append("task_type = ?")
            params.append(task_type)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        conn = self._get_connection()
        rows = conn.execute(query, params).fetchall()
        return [self._row_to_task(row) for row in rows]

    def count_tasks(self, status: str | None = None) -> int:
        """统计任务数量"""
        query = "SELECT COUNT(*) as cnt FROM tasks"
        params = []
        if status:
            query += " WHERE status = ?"
            params.append(status)

        conn = self._get_connection()
        row = conn.execute(query, params).fetchone()
        return row["cnt"] if row else 0

    @staticmethod
    def _row_to_task(row: sqlite3.Row) -> dict[str, Any]:
        """将数据库行转换为任务字典"""
        return {
            "task_id": row["task_id"],
            "name": row["name"],
            "task_type": row["task_type"],
            "status": row["status"],
            "priority": row["priority"],
            "progress": row["progress"],
            "progress_message": row["progress_message"],
            "config": json.loads(row["config"] or "{}"),
            "result": json.loads(row["result"]) if row["result"] else None,
            "error": row["error"],
            "retries": row["retries"],
            "max_retries": row["max_retries"],
            "created_at": row["created_at"],
            "started_at": row["started_at"],
            "completed_at": row["completed_at"],
            "duration": row["duration"],
            "metadata": json.loads(row["metadata"] or "{}"),
        }

    # --------------------------------------------------------------------
    # 项目 CRUD
    # --------------------------------------------------------------------

    def insert_project(self, project_data: dict[str, Any]) -> str:
        """插入项目"""
        project_id = project_data.get("project_id") or f"proj_{uuid.uuid4().hex[:12]}"
        now = time.time()

        with self.transaction() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO projects
                (project_id, name, description, status, duration, scene_count,
                 width, height, frame_rate, scenes, applied_effects, render_output,
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    project_id,
                    project_data.get("name", "未命名项目"),
                    project_data.get("description", ""),
                    project_data.get("status", "draft"),
                    project_data.get("duration", 0.0),
                    project_data.get("scene_count", 0),
                    project_data.get("width", 1920),
                    project_data.get("height", 1080),
                    project_data.get("frame_rate", 30),
                    json.dumps(project_data.get("scenes", []), ensure_ascii=False),
                    json.dumps(project_data.get("applied_effects", []), ensure_ascii=False),
                    project_data.get("render_output"),
                    project_data.get("created_at", now),
                    project_data.get("updated_at", now),
                ),
            )
        return project_id

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        """获取项目"""
        conn = self._get_connection()
        row = conn.execute(
            "SELECT * FROM projects WHERE project_id = ?", (project_id,)
        ).fetchone()
        return self._row_to_project(row) if row else None

    def query_projects(
        self,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """查询项目"""
        query = "SELECT * FROM projects"
        params = []
        if status:
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        conn = self._get_connection()
        rows = conn.execute(query, params).fetchall()
        return [self._row_to_project(row) for row in rows]

    def delete_project(self, project_id: str) -> bool:
        """删除项目"""
        with self.transaction() as conn:
            cursor = conn.execute("DELETE FROM projects WHERE project_id = ?", (project_id,))
            return cursor.rowcount > 0

    @staticmethod
    def _row_to_project(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "project_id": row["project_id"],
            "name": row["name"],
            "description": row["description"],
            "status": row["status"],
            "duration": row["duration"],
            "scene_count": row["scene_count"],
            "width": row["width"],
            "height": row["height"],
            "frame_rate": row["frame_rate"],
            "scenes": json.loads(row["scenes"] or "[]"),
            "applied_effects": json.loads(row["applied_effects"] or "[]"),
            "render_output": row["render_output"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    # --------------------------------------------------------------------
    # 历史记录 CRUD
    # --------------------------------------------------------------------

    def insert_history(self, record: dict[str, Any]) -> str:
        """插入历史记录"""
        record_id = record.get("record_id") or f"hist_{uuid.uuid4().hex[:12]}"

        with self.transaction() as conn:
            conn.execute(
                """INSERT INTO history (record_id, action, result, details, project_id, params, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    record_id,
                    record.get("action", ""),
                    record.get("result", "success"),
                    record.get("details", ""),
                    record.get("project_id"),
                    json.dumps(record.get("params"), ensure_ascii=False) if record.get("params") else None,
                    record.get("created_at", time.time()),
                ),
            )
        return record_id

    def query_history(
        self,
        limit: int = 50,
        offset: int = 0,
        result_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        """查询历史记录"""
        query = "SELECT * FROM history"
        params = []
        if result_filter:
            query += " WHERE result = ?"
            params.append(result_filter)
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        conn = self._get_connection()
        rows = conn.execute(query, params).fetchall()
        return [
            {
                "record_id": row["record_id"],
                "action": row["action"],
                "result": row["result"],
                "details": row["details"],
                "project_id": row["project_id"],
                "params": json.loads(row["params"]) if row["params"] else None,
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def clear_history(self) -> int:
        """清空历史记录"""
        with self.transaction() as conn:
            cursor = conn.execute("DELETE FROM history")
            return cursor.rowcount

    # --------------------------------------------------------------------
    # 插件配置 CRUD
    # --------------------------------------------------------------------

    def save_plugin_config(self, plugin_id: str, config: dict[str, Any], enabled: bool = False):
        """保存插件配置"""
        with self.transaction() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO plugin_configs
                (plugin_id, config, enabled, updated_at)
                VALUES (?, ?, ?, ?)""",
                (
                    plugin_id,
                    json.dumps(config, ensure_ascii=False),
                    1 if enabled else 0,
                    time.time(),
                ),
            )

    def get_plugin_config(self, plugin_id: str) -> dict[str, Any] | None:
        """获取插件配置"""
        conn = self._get_connection()
        row = conn.execute(
            "SELECT * FROM plugin_configs WHERE plugin_id = ?", (plugin_id,)
        ).fetchone()
        if not row:
            return None
        return {
            "plugin_id": row["plugin_id"],
            "config": json.loads(row["config"] or "{}"),
            "enabled": bool(row["enabled"]),
            "updated_at": row["updated_at"],
        }

    def get_all_plugin_configs(self) -> list[dict[str, Any]]:
        """获取所有插件配置"""
        conn = self._get_connection()
        rows = conn.execute("SELECT * FROM plugin_configs").fetchall()
        return [
            {
                "plugin_id": row["plugin_id"],
                "config": json.loads(row["config"] or "{}"),
                "enabled": bool(row["enabled"]),
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]

    # --------------------------------------------------------------------
    # 统计信息
    # --------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """获取数据库统计信息"""
        conn = self._get_connection()

        task_count = conn.execute("SELECT COUNT(*) as cnt FROM tasks").fetchone()["cnt"]
        project_count = conn.execute("SELECT COUNT(*) as cnt FROM projects").fetchone()["cnt"]
        history_count = conn.execute("SELECT COUNT(*) as cnt FROM history").fetchone()["cnt"]
        plugin_config_count = conn.execute("SELECT COUNT(*) as cnt FROM plugin_configs").fetchone()["cnt"]
        workflow_count = conn.execute("SELECT COUNT(*) as cnt FROM workflow_runs").fetchone()["cnt"]

        db_size = 0
        if os.path.exists(self._config.db_path):
            db_size = os.path.getsize(self._config.db_path)

        task_status_counts: dict[str, int] = {}
        for row in conn.execute("SELECT status, COUNT(*) as cnt FROM tasks GROUP BY status").fetchall():
            task_status_counts[row["status"]] = row["cnt"]

        return {
            "db_path": self._config.db_path,
            "db_size_kb": round(db_size / 1024, 2),
            "tables": {
                "tasks": task_count,
                "projects": project_count,
                "history": history_count,
                "plugin_configs": plugin_config_count,
                "workflow_runs": workflow_count,
            },
            "task_status_counts": task_status_counts,
        }

    # --------------------------------------------------------------------
    # 数据库维护
    # --------------------------------------------------------------------

    def vacuum(self):
        """清理数据库碎片"""
        conn = self._get_connection()
        conn.execute("VACUUM")
        _logger.info("数据库已清理")

    def close(self):
        """关闭数据库连接"""
        if hasattr(self._local, "connection"):
            self._local.connection.close()
            del self._local.connection
        _logger.info("数据库连接已关闭")


# ============================================================================
# 模块单例
# ============================================================================

_default_db: Database | None = None


def get_database(config: DatabaseConfig | None = None) -> Database:
    """获取默认数据库实例"""
    global _default_db
    if _default_db is None:
        _default_db = Database(config)
    return _default_db


# ============================================================================
# 命令行测试
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("  数据库持久化模块测试")
    print("=" * 70)

    import shutil
    import tempfile

    tmp_dir = tempfile.mkdtemp(prefix="db_test_")
    db_path = os.path.join(tmp_dir, "test.db")

    try:
        config = DatabaseConfig(db_path=db_path)
        db = Database(config)

        print("\n1. 插入任务...")
        for i in range(5):
            task_id = db.insert_task({
                "name": f"测试任务-{i}",
                "task_type": "puppet_style" if i < 3 else "quality_assess",
                "status": "completed" if i < 2 else "pending",
                "priority": 5 + i,
                "config": {"style": "wood", "quality": "high"},
                "result": {"output": f"result_{i}"} if i < 2 else None,
                "created_at": time.time() - i * 3600,
            })
            print(f"  插入: {task_id}")

        print("\n2. 查询任务...")
        all_tasks = db.query_tasks(limit=10)
        print(f"  总任务数: {len(all_tasks)}")
        for t in all_tasks:
            print(f"    - {t['name']}: {t['status']}")

        completed = db.query_tasks(status="completed")
        print(f"  已完成: {len(completed)}")

        print("\n3. 插入项目...")
        proj_id = db.insert_project({
            "name": "测试项目",
            "description": "数据库测试项目",
            "status": "processing",
            "duration": 120.0,
            "scene_count": 5,
        })
        print(f"  项目ID: {proj_id}")

        proj = db.get_project(proj_id)
        print(f"  项目名称: {proj['name']}")
        print(f"  状态: {proj['status']}")

        print("\n4. 插入历史记录...")
        for i in range(3):
            db.insert_history({
                "action": f"操作-{i}",
                "result": "success" if i < 2 else "failure",
                "details": f"测试详情-{i}",
                "project_id": proj_id if i == 0 else None,
            })

        history = db.query_history(limit=10)
        print(f"  历史记录数: {len(history)}")

        print("\n5. 插件配置...")
        db.save_plugin_config("test_plugin", {"key": "value"}, enabled=True)
        pconfig = db.get_plugin_config("test_plugin")
        print(f"  插件配置: {pconfig}")

        print("\n6. 统计信息...")
        stats = db.get_stats()
        print(f"  数据库大小: {stats['db_size_kb']:.2f} KB")
        print(f"  任务数: {stats['tables']['tasks']}")
        print(f"  项目数: {stats['tables']['projects']}")
        print(f"  历史记录: {stats['tables']['history']}")
        print(f"  任务状态分布: {stats['task_status_counts']}")

        print("\n7. 更新任务...")
        first_task = all_tasks[0]
        db.update_task(first_task["task_id"], {"status": "completed", "progress": 1.0})
        updated = db.get_task(first_task["task_id"])
        print(f"  更新后状态: {updated['status']}, 进度: {updated['progress']}")

        print("\n8. 清理测试...")
        db.clear_history()
        print(f"  清空历史记录后: {db.query_history()}")

        print("\n" + "=" * 70)
        print("  测试完成！")
        print("=" * 70)

        db.close()

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        print("\n临时目录已清理")
