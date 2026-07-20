"""渲染任务数据模型。

定义 ``RenderJob`` 与 ``RenderStats`` 两个数据类，对应 ``render_jobs`` 表的行结构
以及渲染统计聚合结果。所有时间字段统一使用 ISO 8601 字符串（UTC）。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional


# ============================================================
# 渲染状态常量
# ============================================================

# 状态取值：pending / rendering / completed / failed / cancelled
RENDER_STATUS_PENDING = "pending"
RENDER_STATUS_RENDERING = "rendering"
RENDER_STATUS_COMPLETED = "completed"
RENDER_STATUS_FAILED = "failed"
RENDER_STATUS_CANCELLED = "cancelled"

ACTIVE_STATUSES = (RENDER_STATUS_PENDING, RENDER_STATUS_RENDERING)
TERMINAL_STATUSES = (RENDER_STATUS_COMPLETED, RENDER_STATUS_FAILED, RENDER_STATUS_CANCELLED)


def _utc_now_iso() -> str:
    """返回当前 UTC 时间的 ISO 8601 字符串。"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ============================================================
# RenderJob
# ============================================================

@dataclass
class RenderJob:
    """渲染任务数据类，对应 ``render_jobs`` 表的一行。

    Attributes:
        job_id: 任务唯一标识。
        project_path: AE 工程文件路径 (.aep)。
        comp_name: 合成名称。
        output_path: 输出文件路径。
        status: 任务状态 (pending/rendering/completed/failed/cancelled)。
        progress: 进度 0.0 ~ 1.0。
        current_frame: 当前已渲染帧号。
        total_frames: 总帧数。
        fps: 渲染帧率。
        started_at: 渲染开始时间 (ISO 8601 UTC)。
        completed_at: 渲染完成时间 (ISO 8601 UTC)。
        elapsed_seconds: 已耗时（秒）。
        estimated_remaining_seconds: 预计剩余时间（秒）。
        failure_reason: 失败原因（仅 status=failed 时有效）。
        retry_count: 重试次数。
        metadata: 额外元数据（JSON 字符串或 dict）。
        created_at: 记录创建时间 (ISO 8601 UTC)。
        updated_at: 记录最后更新时间 (ISO 8601 UTC)。
    """

    job_id: str
    project_path: str
    comp_name: str
    output_path: str
    status: str = RENDER_STATUS_PENDING
    progress: float = 0.0
    current_frame: int = 0
    total_frames: int = 0
    fps: float = 30.0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    elapsed_seconds: float = 0.0
    estimated_remaining_seconds: Optional[float] = None
    failure_reason: Optional[str] = None
    retry_count: int = 0
    metadata: Optional[str] = None  # JSON 字符串
    created_at: str = field(default_factory=_utc_now_iso)
    updated_at: str = field(default_factory=_utc_now_iso)

    # ------------------------------------------------------------------
    # 便捷属性
    # ------------------------------------------------------------------
    @property
    def is_active(self) -> bool:
        """任务是否仍在进行中 (pending/rendering)。"""
        return self.status in ACTIVE_STATUSES

    @property
    def is_terminal(self) -> bool:
        """任务是否处于终态 (completed/failed/cancelled)。"""
        return self.status in TERMINAL_STATUSES

    @property
    def percent(self) -> float:
        """完成百分比 0-100。"""
        if self.total_frames <= 0:
            return float(self.progress) * 100.0
        return min(100.0, (self.current_frame / self.total_frames) * 100.0)

    @property
    def metadata_dict(self) -> dict[str, Any]:
        """解析 metadata JSON 字符串为 dict，失败返回空 dict。"""
        if not self.metadata:
            return {}
        try:
            return json.loads(self.metadata)
        except (ValueError, TypeError):
            return {}

    # ------------------------------------------------------------------
    # 序列化
    # ------------------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        """转换为字典（适合 JSON 序列化）。"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RenderJob":
        """从字典构造 RenderJob，忽略未知字段。"""
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)

    @classmethod
    def from_row(cls, row: Any) -> "RenderJob":
        """从 aiosqlite.Row / sqlite3.Row 构造 RenderJob。"""
        return cls.from_dict(dict(row))


# ============================================================
# RenderStats
# ============================================================

@dataclass
class RenderStats:
    """渲染统计聚合结果。

    Attributes:
        total_jobs: 最近 N 天内的任务总数。
        completed: 已成功任务数。
        failed: 失败任务数。
        rendering: 当前渲染中任务数。
        pending: 当前等待中任务数。
        cancelled: 已取消任务数。
        success_rate: 成功率（0.0 ~ 1.0），无完成任务时为 0.0。
        avg_elapsed_seconds: 已完成任务的平均耗时（秒）。
        common_failure_reasons: 失败原因 Top 5 列表，每项 (reason, count)。
    """

    total_jobs: int = 0
    completed: int = 0
    failed: int = 0
    rendering: int = 0
    pending: int = 0
    cancelled: int = 0
    success_rate: float = 0.0
    avg_elapsed_seconds: float = 0.0
    common_failure_reasons: list[tuple[str, int]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典（适合 JSON 序列化）。"""
        return {
            "total_jobs": self.total_jobs,
            "completed": self.completed,
            "failed": self.failed,
            "rendering": self.rendering,
            "pending": self.pending,
            "cancelled": self.cancelled,
            "success_rate": round(self.success_rate, 4),
            "avg_elapsed_seconds": round(self.avg_elapsed_seconds, 2),
            "common_failure_reasons": [
                {"reason": r, "count": c} for r, c in self.common_failure_reasons
            ],
        }
