"""Dashboard 数据存储 - SQLite 持久化项目和历史记录。

为 ae-dashboard 前端提供真实的数据持久化支持，替代 mock 数据。
使用标准库 sqlite3 + asyncio.to_thread 实现异步访问，零额外依赖。
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from ..config import settings

DB_PATH = settings.db_path
_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    """获取线程本地数据库连接。"""
    if not hasattr(_local, "conn") or _local.conn is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.conn = conn
    return _local.conn


def _run_sync(func, *args, **kwargs):
    """在同步线程中执行数据库操作。"""
    conn = _get_conn()
    return func(conn, *args, **kwargs)


async def _run_async(func, *args, **kwargs):
    """在事件循环中异步执行数据库操作。"""
    return await asyncio.to_thread(_run_sync, func, *args, **kwargs)


DDL = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    duration REAL DEFAULT 0,
    scene_count INTEGER DEFAULT 0,
    width INTEGER DEFAULT 1920,
    height INTEGER DEFAULT 1080,
    frame_rate REAL DEFAULT 30,
    scenes TEXT DEFAULT '[]',
    applied_effects TEXT DEFAULT '[]',
    render_output TEXT,
    metadata TEXT DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
CREATE INDEX IF NOT EXISTS idx_projects_created_at ON projects(created_at);

CREATE TABLE IF NOT EXISTS history (
    id TEXT PRIMARY KEY,
    action TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    result TEXT NOT NULL DEFAULT 'success',
    details TEXT,
    project_id TEXT,
    params TEXT DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_history_timestamp ON history(timestamp);
CREATE INDEX IF NOT EXISTS idx_history_result ON history(result);
CREATE INDEX IF NOT EXISTS idx_history_project_id ON history(project_id);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _init_schema(conn: sqlite3.Connection):
    """初始化数据库表结构。"""
    conn.executescript(DDL)
    conn.commit()


def _row_to_project(row: sqlite3.Row) -> dict[str, Any]:
    """将数据库行转换为项目字典。"""
    d = dict(row)
    for field in ("scenes", "applied_effects", "metadata"):
        if d.get(field):
            try:
                d[field] = json.loads(d[field])
            except (json.JSONDecodeError, TypeError):
                d[field] = [] if field != "metadata" else {}
    return d


def _row_to_history(row: sqlite3.Row) -> dict[str, Any]:
    """将数据库行转换为历史字典。"""
    d = dict(row)
    if d.get("params"):
        try:
            d["params"] = json.loads(d["params"])
        except (json.JSONDecodeError, TypeError):
            d["params"] = {}
    return d


class DashboardStorage:
    """Dashboard 数据存储管理器。"""

    async def connect(self) -> None:
        """初始化数据库连接和表结构。"""
        await _run_async(_init_schema)
        logger.info(f"Dashboard storage connected at {DB_PATH}")

    async def get_stats(self) -> dict[str, Any]:
        """获取 Dashboard 统计数据。"""
        def _query(conn: sqlite3.Connection):
            total = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
            completed = conn.execute(
                "SELECT COUNT(*) FROM projects WHERE status='completed'"
            ).fetchone()[0]
            processing = conn.execute(
                "SELECT COUNT(*) FROM projects WHERE status='processing'"
            ).fetchone()[0]
            failed = conn.execute(
                "SELECT COUNT(*) FROM projects WHERE status='failed'"
            ).fetchone()[0]
            drafts = conn.execute(
                "SELECT COUNT(*) FROM projects WHERE status='draft'"
            ).fetchone()[0]

            total_hist = conn.execute("SELECT COUNT(*) FROM history").fetchone()[0]
            success_hist = conn.execute(
                "SELECT COUNT(*) FROM history WHERE result='success'"
            ).fetchone()[0]
            failure_hist = conn.execute(
                "SELECT COUNT(*) FROM history WHERE result='failure'"
            ).fetchone()[0]

            recent = conn.execute(
                "SELECT id, name, status, updated_at FROM projects "
                "ORDER BY updated_at DESC LIMIT 5"
            ).fetchall()
            recent_data = [dict(r) for r in recent]

            actions = conn.execute(
                "SELECT action, COUNT(*) as cnt FROM history GROUP BY action"
            ).fetchall()
            action_counts = {r["action"]: r["cnt"] for r in actions}

            return {
                "totalProjects": total,
                "completedProjects": completed,
                "processingProjects": processing,
                "failedProjects": failed,
                "draftProjects": drafts,
                "totalHistory": total_hist,
                "successHistory": success_hist,
                "failureHistory": failure_hist,
                "recentProjects": recent_data,
                "actionCounts": action_counts,
            }

        return await _run_async(_query)

    # ========== Projects ==========

    async def list_projects(
        self, status: str | None = None, page: int = 1, page_size: int = 50
    ) -> dict[str, Any]:
        """分页获取项目列表。"""
        def _query(conn: sqlite3.Connection):
            where_clause = ""
            params: list[Any] = []
            if status:
                where_clause = "WHERE status = ?"
                params.append(status)

            total = conn.execute(
                f"SELECT COUNT(*) FROM projects {where_clause}", params
            ).fetchone()[0]

            offset = (page - 1) * page_size
            rows = conn.execute(
                f"SELECT * FROM projects {where_clause} ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                params + [page_size, offset],
            ).fetchall()

            return {
                "items": [_row_to_project(r) for r in rows],
                "total": total,
                "page": page,
                "page_size": page_size,
            }

        return await _run_async(_query)

    async def get_project(self, project_id: str) -> dict[str, Any] | None:
        """获取单个项目。"""
        def _query(conn: sqlite3.Connection):
            row = conn.execute(
                "SELECT * FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
            return _row_to_project(row) if row else None

        return await _run_async(_query)

    async def create_project(self, data: dict[str, Any]) -> dict[str, Any]:
        """创建项目。"""
        now = _now_iso()
        pid = data.get("id") or f"proj-{abs(hash(str(data.get('name', 'new')))) % 1000000}"
        row_data = {
            "id": pid,
            "name": data.get("name", "New Project"),
            "description": data.get("description", ""),
            "status": data.get("status", "draft"),
            "created_at": data.get("created_at", now),
            "updated_at": data.get("updated_at", now),
            "duration": data.get("duration", 0),
            "scene_count": data.get("scene_count", 0),
            "width": data.get("width", 1920),
            "height": data.get("height", 1080),
            "frame_rate": data.get("frame_rate", 30),
            "scenes": json.dumps(data.get("scenes", []), ensure_ascii=False),
            "applied_effects": json.dumps(data.get("applied_effects", []), ensure_ascii=False),
            "render_output": data.get("render_output"),
            "metadata": json.dumps(data.get("metadata", {}), ensure_ascii=False),
        }

        def _insert(conn: sqlite3.Connection):
            conn.execute(
                """INSERT INTO projects
                   (id, name, description, status, created_at, updated_at,
                    duration, scene_count, width, height, frame_rate,
                    scenes, applied_effects, render_output, metadata)
                   VALUES (:id, :name, :description, :status, :created_at, :updated_at,
                           :duration, :scene_count, :width, :height, :frame_rate,
                           :scenes, :applied_effects, :render_output, :metadata)""",
                row_data,
            )
            conn.commit()
            return _row_to_project(
                conn.execute("SELECT * FROM projects WHERE id = ?", (pid,)).fetchone()
            )

        return await _run_async(_insert)

    async def update_project(self, project_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        """更新项目。"""
        now = _now_iso()

        def _update(conn: sqlite3.Connection):
            existing = conn.execute(
                "SELECT * FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
            if not existing:
                return None
            merged = _row_to_project(existing)
            merged.update(data)
            merged["updated_at"] = now

            conn.execute(
                """UPDATE projects SET
                   name=?, description=?, status=?, updated_at=?,
                   duration=?, scene_count=?, width=?, height=?, frame_rate=?,
                   scenes=?, applied_effects=?, render_output=?, metadata=?
                   WHERE id=?""",
                (
                    merged["name"],
                    merged.get("description", ""),
                    merged["status"],
                    merged["updated_at"],
                    merged.get("duration", 0),
                    merged.get("scene_count", 0),
                    merged.get("width", 1920),
                    merged.get("height", 1080),
                    merged.get("frame_rate", 30),
                    json.dumps(merged.get("scenes", []), ensure_ascii=False),
                    json.dumps(merged.get("applied_effects", []), ensure_ascii=False),
                    merged.get("render_output"),
                    json.dumps(merged.get("metadata", {}), ensure_ascii=False),
                    project_id,
                ),
            )
            conn.commit()
            return _row_to_project(
                conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
            )

        return await _run_async(_update)

    async def delete_project(self, project_id: str) -> bool:
        """删除项目。"""
        def _delete(conn: sqlite3.Connection):
            cur = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            conn.commit()
            return cur.rowcount > 0

        return await _run_async(_delete)

    # ========== History ==========

    async def list_history(
        self, limit: int = 50, offset: int = 0, result: str | None = None
    ) -> dict[str, Any]:
        """获取历史记录。"""
        def _query(conn: sqlite3.Connection):
            where = ""
            params: list[Any] = []
            if result:
                where = "WHERE result = ?"
                params.append(result)

            total = conn.execute(
                f"SELECT COUNT(*) FROM history {where}", params
            ).fetchone()[0]

            rows = conn.execute(
                f"SELECT * FROM history {where} ORDER BY timestamp DESC LIMIT ? OFFSET ?",
                params + [limit, offset],
            ).fetchall()

            return {
                "items": [_row_to_history(r) for r in rows],
                "total": total,
                "limit": limit,
                "offset": offset,
            }

        return await _run_async(_query)

    async def add_history(self, data: dict[str, Any]) -> dict[str, Any]:
        """添加历史记录。"""
        now = _now_iso()
        import uuid
        hid = data.get("id") or f"hist-{uuid.uuid4().hex[:12]}"

        row_data = {
            "id": hid,
            "action": data.get("action", "unknown"),
            "timestamp": data.get("timestamp", now),
            "result": data.get("result", "success"),
            "details": data.get("details"),
            "project_id": data.get("project_id"),
            "params": json.dumps(data.get("params", {}), ensure_ascii=False),
        }

        def _insert(conn: sqlite3.Connection):
            conn.execute(
                """INSERT INTO history
                   (id, action, timestamp, result, details, project_id, params)
                   VALUES (:id, :action, :timestamp, :result, :details, :project_id, :params)""",
                row_data,
            )
            conn.commit()
            return _row_to_history(
                conn.execute("SELECT * FROM history WHERE id = ?", (hid,)).fetchone()
            )

        return await _run_async(_insert)

    async def clear_history(self) -> bool:
        """清空历史记录。"""
        def _clear(conn: sqlite3.Connection):
            conn.execute("DELETE FROM history")
            conn.commit()
            return True

        return await _run_async(_clear)

    async def list_alert_history(
        self, hours: int = 24, limit: int = 100
    ) -> list[dict[str, Any]]:
        """获取历史告警记录。

        当前尚无独立的告警持久化表，返回空列表作为占位实现，
        待告警存储表落地后在此对接真实查询。
        """
        return []


# 全局单例
dashboard_storage = DashboardStorage()


# ========== Demo Data Seeding ==========

async def _seed_demo_data(storage: DashboardStorage) -> None:
    """首次运行时填充演示数据（项目和历史独立检查）。"""
    stats = await storage.get_stats()
    projects_exist = stats["totalProjects"] > 0

    if not projects_exist:
        demo_projects = [
            {
                "id": "proj-demo-1",
                "name": "木偶风格化 - 产品宣传片",
                "description": "木质木偶风格产品展示视频，30秒，4K",
                "status": "processing",
                "duration": 30.0,
                "scene_count": 12,
                "width": 3840,
                "height": 2160,
                "frame_rate": 30,
                "scenes": [
                    {"id": 1, "name": "开场", "duration": 3.0, "description": "产品logo出场"},
                    {"id": 2, "name": "主体展示", "duration": 15.0, "description": "360度旋转展示"},
                    {"id": 3, "name": "特写", "duration": 8.0, "description": "关键卖点特写"},
                    {"id": 4, "name": "结尾", "duration": 4.0, "description": "品牌口号"},
                ],
                "applied_effects": ["lens_flare", "grain", "vignette"],
                "render_output": None,
                "metadata": {"style": "wooden_puppet", "quality": "4K"},
            },
            {
                "id": "proj-demo-2",
                "name": "赛博朋克 - 音乐MV",
                "description": "霓虹风格音乐视频，2分钟，1080p",
                "status": "completed",
                "duration": 120.0,
                "scene_count": 24,
                "width": 1920,
                "height": 1080,
                "frame_rate": 24,
                "scenes": [
                    {"id": 1, "name": "城市远景", "duration": 10.0},
                    {"id": 2, "name": "角色特写", "duration": 20.0},
                    {"id": 3, "name": "舞蹈场景", "duration": 60.0},
                    {"id": 4, "name": "结尾字幕", "duration": 5.0},
                ],
                "applied_effects": ["neon_glow", "chromatic_aberration", "scanlines"],
                "render_output": "output/cyberpunk_mv_final.mp4",
                "metadata": {"style": "cyberpunk", "quality": "high"},
            },
            {
                "id": "proj-demo-3",
                "name": "水彩动画 - 品牌宣传片",
                "description": "手绘水彩风格品牌故事，45秒",
                "status": "completed",
                "duration": 45.0,
                "scene_count": 8,
                "width": 1920,
                "height": 1080,
                "frame_rate": 30,
                "scenes": [
                    {"id": 1, "name": "水彩开场", "duration": 5.0},
                    {"id": 2, "name": "品牌故事", "duration": 30.0},
                    {"id": 3, "name": "logo定格", "duration": 10.0},
                ],
                "applied_effects": ["watercolor", "paper_texture", "ink_bleed"],
                "render_output": "output/watercolor_brand.mp4",
                "metadata": {"style": "watercolor", "quality": "medium"},
            },
            {
                "id": "proj-demo-4",
                "name": "黏土定格 - 广告短片",
                "description": "黏土动画风格广告，15秒",
                "status": "failed",
                "duration": 15.0,
                "scene_count": 6,
                "width": 1920,
                "height": 1080,
                "frame_rate": 24,
                "scenes": [
                    {"id": 1, "name": "产品出场", "duration": 3.0},
                    {"id": 2, "name": "功能展示", "duration": 10.0},
                    {"id": 3, "name": "结尾", "duration": 2.0},
                ],
                "applied_effects": ["clay_texture", "stop_motion_jitter"],
                "render_output": None,
                "metadata": {"style": "claymation", "error": "AE渲染超时"},
            },
            {
                "id": "proj-demo-5",
                "name": "水墨风格 - 纪录片片头",
                "description": "中国水墨画风格纪录片开场，20秒",
                "status": "draft",
                "duration": 20.0,
                "scene_count": 5,
                "width": 3840,
                "height": 2160,
                "frame_rate": 25,
                "scenes": [
                    {"id": 1, "name": "远山", "duration": 5.0},
                    {"id": 2, "name": "流水", "duration": 8.0},
                    {"id": 3, "name": "落款", "duration": 7.0},
                ],
                "applied_effects": ["ink_wash", "rice_paper", "calligraphy_stroke"],
                "render_output": None,
                "metadata": {"style": "ink_wash", "quality": "4K"},
            },
        ]

        for proj in demo_projects:
            try:
                await storage.create_project(proj)
            except Exception:
                pass

    history_result = await storage.list_history(limit=1)
    history_exists = history_result.get("total", 0) > 0

    if not history_exists:
        demo_history = [
            {"id": "hist-demo-1", "action": "import", "result": "success", "project_id": "proj-demo-1", "details": "导入素材 12 个", "params": {"file_count": 12}},
            {"id": "hist-demo-2", "action": "analyze", "result": "success", "project_id": "proj-demo-1", "details": "BPM 分析完成: 120 BPM", "params": {"bpm": 120}},
            {"id": "hist-demo-3", "action": "plan", "result": "success", "project_id": "proj-demo-1", "details": "生成 12 个镜头分镜", "params": {"shots": 12}},
            {"id": "hist-demo-4", "action": "render", "result": "success", "project_id": "proj-demo-2", "details": "AE 渲染完成: cyberpunk_mv_final.mp4", "params": {"duration": 120, "output": "mp4"}},
            {"id": "hist-demo-5", "action": "enhance", "result": "success", "project_id": "proj-demo-2", "details": "Topaz Video AI 增强完成", "params": {"model": "proteus", "scale": 2}},
            {"id": "hist-demo-6", "action": "encode", "result": "success", "project_id": "proj-demo-2", "details": "H.264 编码完成", "params": {"codec": "h264", "bitrate": "15M"}},
            {"id": "hist-demo-7", "action": "render", "result": "success", "project_id": "proj-demo-3", "details": "AE 渲染完成: watercolor_brand.mp4", "params": {"duration": 45}},
            {"id": "hist-demo-8", "action": "render", "result": "failure", "project_id": "proj-demo-4", "details": "AE 渲染超时: 超过 30 分钟", "params": {"timeout": 1800}},
            {"id": "hist-demo-9", "action": "quality_check", "result": "success", "project_id": "proj-demo-2", "details": "VMAF 评分: 92.5", "params": {"vmaf": 92.5}},
            {"id": "hist-demo-10", "action": "upload", "result": "success", "project_id": "proj-demo-2", "details": "上传至交付服务器", "params": {"size_mb": 345}},
            {"id": "hist-demo-11", "action": "clone_style", "result": "success", "project_id": "proj-demo-3", "details": "风格复刻完成，相似度 95%", "params": {"similarity": 0.95}},
            {"id": "hist-demo-12", "action": "segment", "result": "success", "project_id": "proj-demo-1", "details": "SAM2 分割完成，生成 8 个 mask", "params": {"masks": 8}},
        ]

        for h in demo_history:
            try:
                await storage.add_history(h)
            except Exception:
                pass

        logger.info(f"Seeded {len(demo_history)} history entries")
