"""AE 渲染任务持久化仓库。

使用 ``aiosqlite`` 异步访问 SQLite 数据库，存储 aerender 任务的完整生命周期
信息，支持：

1. 服务重启后恢复渲染任务状态
2. 查询历史渲染记录（最近 N 天）
3. 按状态 / 项目 / 时间筛选渲染任务
4. 渲染统计（成功率 / 平均耗时 / 失败原因分布）

数据库文件路径通过 ``settings.render_db_path`` 配置，默认
``puppet-automation/data/render_jobs.db``。所有时间字段统一使用 ISO 8601 UTC
字符串。所有方法均为协程，可在 FastAPI / asyncio 环境中直接 ``await`` 调用。

并发安全策略：
- 使用 ``aiosqlite`` 单连接 + ``asyncio.Lock`` 串行化写操作，避免 SQLite
  ``database is locked`` 错误
- 读操作不加锁，与写操作共享同一连接
- 启用 WAL 模式以提升并发读性能
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import aiosqlite
from loguru import logger

from ..config import settings
from ..models.render_job import (
    ACTIVE_STATUSES,
    RENDER_STATUS_CANCELLED,
    RENDER_STATUS_COMPLETED,
    RENDER_STATUS_FAILED,
    RENDER_STATUS_PENDING,
    RENDER_STATUS_RENDERING,
    TERMINAL_STATUSES,
    RenderJob,
    RenderStats,
    _utc_now_iso,
)


# ============================================================
# 表结构 DDL
# ============================================================

DDL = """
CREATE TABLE IF NOT EXISTS render_jobs (
    job_id TEXT PRIMARY KEY,
    project_path TEXT NOT NULL,
    comp_name TEXT NOT NULL,
    output_path TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    progress REAL DEFAULT 0.0,
    current_frame INTEGER DEFAULT 0,
    total_frames INTEGER DEFAULT 0,
    fps REAL DEFAULT 30.0,
    started_at TEXT,
    completed_at TEXT,
    elapsed_seconds REAL DEFAULT 0,
    estimated_remaining_seconds REAL,
    failure_reason TEXT,
    retry_count INTEGER DEFAULT 0,
    metadata TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_render_jobs_status ON render_jobs(status);
CREATE INDEX IF NOT EXISTS idx_render_jobs_created_at ON render_jobs(created_at);
CREATE INDEX IF NOT EXISTS idx_render_jobs_project_path ON render_jobs(project_path);
"""


# ============================================================
# RenderJobRepository
# ============================================================

class RenderJobRepository:
    """渲染任务的 SQLite 持久化仓库。

    Usage::

        repo = RenderJobRepository()
        await repo.connect()
        job = await repo.create_job("job-1", "/a.aep", "comp", "/out.mp4", 300)
        job = await repo.update_job("job-1", status="rendering", current_frame=50)
        await repo.close()
    """

    # 允许通过 update_job 更新的字段白名单（防止 SQL 注入）
    _UPDATABLE_FIELDS = frozenset({
        "status",
        "progress",
        "current_frame",
        "total_frames",
        "fps",
        "started_at",
        "completed_at",
        "elapsed_seconds",
        "estimated_remaining_seconds",
        "failure_reason",
        "retry_count",
        "metadata",
        "project_path",
        "comp_name",
        "output_path",
    })

    def __init__(
        self,
        db_path: Optional[Path | str] = None,
    ) -> None:
        """初始化仓库。

        Args:
            db_path: SQLite 数据库文件路径。为 ``None`` 时使用
                ``settings.render_db_path``。传入 ``":memory:"`` 时使用
                内存数据库（仅用于测试）。
        """
        if db_path is None:
            db_path = settings.render_db_path
        self.db_path = Path(db_path) if not str(db_path) == ":memory:" else db_path
        self._conn: Optional[aiosqlite.Connection] = None
        self._write_lock: asyncio.Lock = asyncio.Lock()
        self._connected: bool = False

    # ------------------------------------------------------------------
    # 连接管理
    # ------------------------------------------------------------------
    async def connect(self) -> None:
        """打开数据库连接并初始化表结构。"""
        if self._connected:
            return

        # 文件数据库需要确保父目录存在
        if isinstance(self.db_path, Path):
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn = await aiosqlite.connect(str(self.db_path))
        self._conn.row_factory = aiosqlite.Row

        # 启用外键、WAL 模式提升并发性能（文件数据库有效）
        await self._conn.execute("PRAGMA foreign_keys = ON")
        try:
            await self._conn.execute("PRAGMA journal_mode = WAL")
        except aiosqlite.OperationalError:
            # 内存数据库不支持 WAL，忽略
            pass

        await self._conn.executescript(DDL)
        await self._conn.commit()
        self._connected = True
        logger.debug(f"RenderJobRepository connected: {self.db_path}")

    async def close(self) -> None:
        """关闭数据库连接。"""
        if self._conn is not None:
            await self._conn.close()
            self._conn = None
            self._connected = False

    async def __aenter__(self) -> "RenderJobRepository":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    @property
    def is_connected(self) -> bool:
        return self._connected and self._conn is not None

    def _ensure_connected(self) -> None:
        if not self.is_connected:
            raise RuntimeError(
                "RenderJobRepository not connected. Call connect() first."
            )

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------
    async def create_job(
        self,
        job_id: str,
        project_path: str,
        comp_name: str,
        output_path: str,
        total_frames: int = 0,
        **kwargs: Any,
    ) -> RenderJob:
        """创建一个新的渲染任务记录。

        Args:
            job_id: 任务唯一标识。
            project_path: AE 工程文件路径。
            comp_name: 合成名称。
            output_path: 输出文件路径。
            total_frames: 总帧数（可后续更新）。
            **kwargs: 额外可选字段，例如 ``fps``、``metadata``、``status``、
                ``started_at``、``retry_count`` 等。

        Returns:
            创建后的 ``RenderJob`` 对象。

        Raises:
            ValueError: 字段不在白名单中，或 ``job_id`` 已存在。
        """
        self._ensure_connected()
        assert self._conn is not None

        now = _utc_now_iso()
        job = RenderJob(
            job_id=job_id,
            project_path=project_path,
            comp_name=comp_name,
            output_path=output_path,
            total_frames=total_frames,
            created_at=now,
            updated_at=now,
        )

        # 应用可选字段
        for k, v in kwargs.items():
            if k not in self._UPDATABLE_FIELDS:
                raise ValueError(f"不允许的字段: {k}")
            setattr(job, k, v)

        # 如果 metadata 是 dict，序列化为 JSON 字符串
        if isinstance(job.metadata, dict):
            job.metadata = json.dumps(job.metadata, ensure_ascii=False)

        # 构造 INSERT SQL
        columns = [
            "job_id", "project_path", "comp_name", "output_path",
            "status", "progress", "current_frame", "total_frames",
            "fps", "started_at", "completed_at", "elapsed_seconds",
            "estimated_remaining_seconds", "failure_reason", "retry_count",
            "metadata", "created_at", "updated_at",
        ]
        values = [
            job.job_id, job.project_path, job.comp_name, job.output_path,
            job.status, job.progress, job.current_frame, job.total_frames,
            job.fps, job.started_at, job.completed_at, job.elapsed_seconds,
            job.estimated_remaining_seconds, job.failure_reason, job.retry_count,
            job.metadata, job.created_at, job.updated_at,
        ]
        placeholders = ", ".join(["?"] * len(columns))
        sql = f"INSERT INTO render_jobs ({', '.join(columns)}) VALUES ({placeholders})"

        async with self._write_lock:
            try:
                await self._conn.execute(sql, values)
                await self._conn.commit()
            except aiosqlite.IntegrityError as e:
                raise ValueError(f"任务已存在: job_id={job_id}") from e

        logger.debug(f"RenderJob created: {job_id} (status={job.status})")
        return job

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------
    async def get_job(self, job_id: str) -> Optional[RenderJob]:
        """根据 job_id 查询任务，不存在返回 None。"""
        self._ensure_connected()
        assert self._conn is not None

        cursor = await self._conn.execute(
            "SELECT * FROM render_jobs WHERE job_id = ?",
            (job_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return RenderJob.from_row(row)

    async def list_jobs(
        self,
        status: Optional[str] = None,
        project_path: Optional[str] = None,
        days: int = 7,
        limit: int = 50,
        offset: int = 0,
    ) -> list[RenderJob]:
        """列表查询渲染任务。

        Args:
            status: 按状态过滤（pending/rendering/completed/failed/cancelled）。
            project_path: 按项目路径精确匹配过滤。
            days: 只返回最近 N 天内创建的任务（按 ``created_at``）。
            limit: 返回条数上限，默认 50，最大 500。
            offset: 偏移量，用于分页。
        """
        self._ensure_connected()
        assert self._conn is not None

        # 参数约束
        limit = max(1, min(int(limit), 500))
        offset = max(0, int(offset))
        days = max(0, int(days))

        # 计算时间下界
        since_dt = datetime.now(timezone.utc) - timedelta(days=days)
        since_iso = since_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        conditions = ["created_at >= ?"]
        params: list[Any] = [since_iso]

        if status:
            conditions.append("status = ?")
            params.append(status)
        if project_path:
            conditions.append("project_path = ?")
            params.append(project_path)

        where_clause = " AND ".join(conditions)
        sql = (
            f"SELECT * FROM render_jobs WHERE {where_clause} "
            f"ORDER BY created_at DESC LIMIT ? OFFSET ?"
        )
        params.extend([limit, offset])

        cursor = await self._conn.execute(sql, params)
        rows = await cursor.fetchall()
        return [RenderJob.from_row(r) for r in rows]

    async def get_active_jobs(self) -> list[RenderJob]:
        """查询所有进行中的任务 (pending/rendering)。"""
        self._ensure_connected()
        assert self._conn is not None

        placeholders = ", ".join(["?"] * len(ACTIVE_STATUSES))
        sql = (
            f"SELECT * FROM render_jobs WHERE status IN ({placeholders}) "
            f"ORDER BY created_at ASC"
        )
        cursor = await self._conn.execute(sql, list(ACTIVE_STATUSES))
        rows = await cursor.fetchall()
        return [RenderJob.from_row(r) for r in rows]

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------
    async def update_job(self, job_id: str, **fields: Any) -> Optional[RenderJob]:
        """更新任务字段。

        Args:
            job_id: 任务 ID。
            **fields: 待更新字段，必须为 ``_UPDATABLE_FIELDS`` 中的合法字段。
                ``metadata`` 如果传入 dict 会自动 JSON 序列化。

        Returns:
            更新后的 ``RenderJob``；任务不存在返回 ``None``。

        Raises:
            ValueError: 没有提供任何字段，或字段名非法。
        """
        self._ensure_connected()
        assert self._conn is not None

        if not fields:
            raise ValueError("update_job 至少需要一个待更新字段")

        # 校验字段白名单
        for k in fields:
            if k not in self._UPDATABLE_FIELDS:
                raise ValueError(f"不允许更新的字段: {k}")

        # 处理 metadata 序列化
        if "metadata" in fields and isinstance(fields["metadata"], dict):
            fields["metadata"] = json.dumps(fields["metadata"], ensure_ascii=False)

        # 自动维护 updated_at
        fields["updated_at"] = _utc_now_iso()

        # 状态转换时自动填充时间戳
        new_status = fields.get("status")
        if new_status == RENDER_STATUS_RENDERING and not fields.get("started_at"):
            # 进入 rendering 时若未指定 started_at，自动填充
            existing = await self.get_job(job_id)
            if existing and existing.started_at is None:
                fields["started_at"] = fields["updated_at"]
        elif new_status in TERMINAL_STATUSES:
            # 进入终态时自动填充 completed_at
            existing = await self.get_job(job_id)
            if existing and existing.completed_at is None:
                fields["completed_at"] = fields["updated_at"]

        set_clauses = [f"{k} = ?" for k in fields]
        values: list[Any] = list(fields.values())
        values.append(job_id)

        sql = (
            f"UPDATE render_jobs SET {', '.join(set_clauses)} "
            f"WHERE job_id = ?"
        )

        async with self._write_lock:
            cursor = await self._conn.execute(sql, values)
            await self._conn.commit()
            rowcount = cursor.rowcount

        if rowcount == 0:
            return None
        return await self.get_job(job_id)

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------
    async def delete_job(self, job_id: str) -> bool:
        """删除任务记录，返回是否删除成功。"""
        self._ensure_connected()
        assert self._conn is not None

        async with self._write_lock:
            cursor = await self._conn.execute(
                "DELETE FROM render_jobs WHERE job_id = ?",
                (job_id,),
            )
            await self._conn.commit()
            deleted = cursor.rowcount > 0

        if deleted:
            logger.debug(f"RenderJob deleted: {job_id}")
        return deleted

    # ------------------------------------------------------------------
    # 重启恢复：清理卡住的任务
    # ------------------------------------------------------------------
    async def mark_stale_as_failed(self, stale_minutes: int = 30) -> int:
        """将长时间未更新的活跃任务标记为 failed。

        服务重启时调用此方法清理因崩溃 / 重启而卡在 pending / rendering 状态
        的任务。

        Args:
            stale_minutes: 任务超过该分钟数未更新则视为 stale。

        Returns:
            被标记为 failed 的任务数量。
        """
        self._ensure_connected()
        assert self._conn is not None

        stale_minutes = max(0, int(stale_minutes))
        cutoff_dt = datetime.now(timezone.utc) - timedelta(minutes=stale_minutes)
        cutoff_iso = cutoff_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        now_iso = _utc_now_iso()
        placeholders = ", ".join(["?"] * len(ACTIVE_STATUSES))
        sql = (
            f"UPDATE render_jobs "
            f"SET status = ?, failure_reason = ?, updated_at = ? "
            f"WHERE status IN ({placeholders}) "
            f"AND updated_at < ?"
        )
        params: list[Any] = [
            RENDER_STATUS_FAILED,
            f"任务在 {stale_minutes} 分钟内无更新，被标记为失败（可能因服务重启）",
            now_iso,
            *ACTIVE_STATUSES,
            cutoff_iso,
        ]

        async with self._write_lock:
            cursor = await self._conn.execute(sql, params)
            await self._conn.commit()
            count = cursor.rowcount

        if count > 0:
            logger.warning(
                f"RenderJobRepository: {count} 个 stale 任务被标记为 failed "
                f"(stale>{stale_minutes}min)"
            )
        return count

    # ------------------------------------------------------------------
    # 统计
    # ------------------------------------------------------------------
    async def get_stats(self, days: int = 30) -> RenderStats:
        """返回最近 N 天的渲染统计。

        Args:
            days: 统计窗口（天）。

        Returns:
            ``RenderStats`` 数据对象。
        """
        self._ensure_connected()
        assert self._conn is not None

        days = max(1, int(days))
        since_dt = datetime.now(timezone.utc) - timedelta(days=days)
        since_iso = since_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        # 1. 按状态分组计数
        cursor = await self._conn.execute(
            "SELECT status, COUNT(*) AS cnt FROM render_jobs "
            "WHERE created_at >= ? GROUP BY status",
            (since_iso,),
        )
        status_counts = {row["status"]: row["cnt"] for row in await cursor.fetchall()}

        total = sum(status_counts.values())
        completed = status_counts.get(RENDER_STATUS_COMPLETED, 0)
        failed = status_counts.get(RENDER_STATUS_FAILED, 0)
        rendering = status_counts.get(RENDER_STATUS_RENDERING, 0)
        pending = status_counts.get(RENDER_STATUS_PENDING, 0)
        cancelled = status_counts.get(RENDER_STATUS_CANCELLED, 0)

        # 终态任务数（用于成功率分母）
        terminal = completed + failed + cancelled
        success_rate = (completed / terminal) if terminal > 0 else 0.0

        # 2. 已完成任务平均耗时
        cursor = await self._conn.execute(
            "SELECT AVG(elapsed_seconds) AS avg_elapsed FROM render_jobs "
            "WHERE status = ? AND created_at >= ? AND elapsed_seconds > 0",
            (RENDER_STATUS_COMPLETED, since_iso),
        )
        avg_row = await cursor.fetchone()
        avg_elapsed = float(avg_row["avg_elapsed"]) if avg_row and avg_row["avg_elapsed"] else 0.0

        # 3. 失败原因 Top 5
        cursor = await self._conn.execute(
            "SELECT failure_reason, COUNT(*) AS cnt FROM render_jobs "
            "WHERE status = ? AND created_at >= ? "
            "AND failure_reason IS NOT NULL AND failure_reason != '' "
            "GROUP BY failure_reason ORDER BY cnt DESC LIMIT 5",
            (RENDER_STATUS_FAILED, since_iso),
        )
        reasons: list[tuple[str, int]] = []
        for row in await cursor.fetchall():
            reasons.append((row["failure_reason"], int(row["cnt"])))

        return RenderStats(
            total_jobs=total,
            completed=completed,
            failed=failed,
            rendering=rendering,
            pending=pending,
            cancelled=cancelled,
            success_rate=success_rate,
            avg_elapsed_seconds=avg_elapsed,
            common_failure_reasons=reasons,
        )


# ============================================================
# 全局单例（由 main.py lifespan 初始化）
# ============================================================

# 注意：不在模块导入时连接数据库，避免测试与首次启动的副作用。
# FastAPI lifespan 中调用 ``await render_repository.connect()``。
render_repository = RenderJobRepository()
