"""AE 渲染进度解析器 - 解析 aerender CLI 输出。

aerender 在执行过程中会向 stdout/stderr 输出形如：

    PROGRESS:  0:00:15:01 (1): 0 Seconds
    PROGRESS:  ...\nRendering layer 1/5: Layer Name
    Total Time Elapsed: 0:00:30
    Total Time Elapsed: 00:00:30:00 (30 Seconds)

的进度信息。本解析器逐行解析这些输出，维护 ``RenderProgress`` 状态机：
``idle → rendering → completed/failed``，并计算 fps 与预计剩余时间。

如果注入了 ``RenderJobRepository``，解析器会在状态变化与帧更新时持久化到
SQLite，支持服务重启后恢复渲染任务状态。
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Optional

from loguru import logger

if TYPE_CHECKING:
    from .render_repository import RenderJobRepository


@dataclass
class RenderProgress:
    """渲染进度信息。

    Attributes:
        current_frame: 当前已渲染帧号。
        total_frames: 总帧数（需在创建解析器时提供，否则无法计算百分比）。
        elapsed_seconds: 已耗时（秒）。
        estimated_remaining_seconds: 预计剩余时间（秒）。
        frames_per_second: 渲染速度（fps）。
        current_layer: 当前正在渲染的图层名。
        status: 渲染状态，取值 idle / rendering / completed / failed。
    """

    current_frame: int = 0
    total_frames: int = 0
    elapsed_seconds: float = 0.0
    estimated_remaining_seconds: float = 0.0
    frames_per_second: float = 0.0
    current_layer: str = ""
    status: str = "idle"  # idle / rendering / completed / failed
    # 内部字段：用于计算 fps 与 ETA
    _first_frame_at: float = field(default=0.0, repr=False)
    _last_frame_at: float = field(default=0.0, repr=False)
    _frame_history: List[tuple] = field(default_factory=list, repr=False)

    @property
    def percent(self) -> float:
        """完成百分比（0-100）。"""
        if self.total_frames <= 0:
            return 0.0
        # 当前帧号从 1 开始计数；用 (current_frame) / total_frames 即可
        return min(100.0, (self.current_frame / self.total_frames) * 100.0)


class RenderProgressParser:
    """解析 aerender CLI 的 stdout/stderr 输出。

    Usage::

        parser = RenderProgressParser(total_frames=300)
        for line in process.stdout:
            progress = parser.parse_line(line)
            if progress:
                print(f"{progress.percent:.1f}%")
    """

    # aerender 输出格式示例：
    # "PROGRESS:  0:00:15:01 (1): 0 Seconds"
    # "PROGRESS:  ...\nRendering layer 1/5: Layer Name"
    # "Total Time Elapsed: 0:00:30"
    # "Total Time Elapsed: 00:00:30:00 (30 Seconds)"
    FRAME_PATTERN = re.compile(r"PROGRESS:.*?\((\d+)\)")
    LAYER_PATTERN = re.compile(r"Rendering layer\s+(\d+)\s*/\s*(\d+)\s*:\s*(.+)")
    TIME_PATTERN = re.compile(
        r"Total Time Elapsed:\s*(\d{1,2}:\d{2}:\d{2}(?::\d{2})?)"
    )
    # 渲染完成 / 失败的常见提示
    COMPLETED_PATTERN = re.compile(r"Total Time Elapsed:", re.IGNORECASE)
    FAILED_PATTERN = re.compile(
        r"(aerender\s+error|rendering\s+failed|fatal\s+error|aborted)",
        re.IGNORECASE,
    )

    def __init__(
        self,
        total_frames: int = 0,
        *,
        job_id: Optional[str] = None,
        repository: Optional["RenderJobRepository"] = None,
    ) -> None:
        """初始化解析器。

        Args:
            total_frames: 渲染总帧数。若未知可传 0，后续可通过
                ``self.progress.total_frames`` 更新。
            job_id: 关联的渲染任务 ID。提供此值且同时传入 ``repository`` 时，
                解析器会在状态变化与帧更新时自动持久化。
            repository: 可选的 ``RenderJobRepository``，用于持久化进度。
        """
        self.total_frames = total_frames
        self.progress = RenderProgress(total_frames=total_frames)
        self._parse_start: float = time.time()
        self._last_completed: bool = False
        self.job_id = job_id
        self.repository = repository
        self._last_persisted_status: Optional[str] = None
        self._last_persisted_frame: int = -1

    # ------------------------------------------------------------------
    # 行解析
    # ------------------------------------------------------------------
    def parse_line(self, line: str) -> Optional[RenderProgress]:
        """解析一行 aerender 输出。

        Args:
            line: 单行输出文本（可包含换行符）。

        Returns:
            更新后的 ``RenderProgress`` 对象；若该行无可识别信息则返回 None。
        """
        if not line:
            return None
        text = line.strip()
        if not text:
            return None

        matched = False
        progress = self.progress
        prev_status = progress.status
        prev_frame = progress.current_frame

        # 1. 帧号解析
        frame_match = self.FRAME_PATTERN.search(text)
        if frame_match:
            try:
                frame_no = int(frame_match.group(1))
            except ValueError:
                frame_no = 0
            if frame_no > 0:
                self._update_frame(frame_no)
                matched = True
                # 收到首帧后切换为 rendering
                if progress.status in ("idle",):
                    progress.status = "rendering"

        # 2. 图层解析
        layer_match = self.LAYER_PATTERN.search(text)
        if layer_match:
            try:
                layer_idx = int(layer_match.group(1))
                layer_total = int(layer_match.group(2))
            except ValueError:
                layer_idx, layer_total = 0, 0
            layer_name = layer_match.group(3).strip()
            progress.current_layer = layer_name
            # 图层总数可作为总帧数的兜底提示（仅日志，不覆盖 total_frames）
            if layer_total > 0:
                logger.debug(
                    f"AE 渲染图层 {layer_idx}/{layer_total}: {layer_name}"
                )
            matched = True
            if progress.status == "idle":
                progress.status = "rendering"

        # 3. 总耗时解析
        time_match = self.TIME_PATTERN.search(text)
        if time_match:
            elapsed = self._parse_timecode(time_match.group(1))
            if elapsed is not None:
                progress.elapsed_seconds = elapsed
                # 总耗时通常只在渲染结束时输出一次
                if not self._last_completed:
                    progress.status = "completed"
                    self._last_completed = True
                    logger.info(
                        f"AE 渲染完成，总耗时 {elapsed:.1f}s，"
                        f"渲染帧数 {progress.current_frame}"
                    )
            matched = True

        # 4. 失败检测
        if self.FAILED_PATTERN.search(text):
            progress.status = "failed"
            matched = True
            logger.error(f"AE 渲染失败: {text}")

        # 5. 同步已耗时（基于 wall-clock）
        if progress.status == "rendering":
            progress.elapsed_seconds = time.time() - self._parse_start

        # 6. 持久化触发：状态变化或帧号增量 >= 1 时调度异步持久化
        if matched and self._should_persist(prev_status, prev_frame):
            self._schedule_persist()

        return progress if matched else None

    def parse_output(self, output: str) -> RenderProgress:
        """解析完整输出（多行）。

        Args:
            output: 完整输出文本。

        Returns:
            最终的 ``RenderProgress`` 状态。
        """
        for raw_line in output.splitlines():
            self.parse_line(raw_line)
        return self.progress

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------
    def _update_frame(self, frame_no: int) -> None:
        """更新当前帧号，并基于帧历史计算 fps 与 ETA。"""
        progress = self.progress
        now = time.time()
        prev_frame = progress.current_frame
        progress.current_frame = max(prev_frame, frame_no)

        # 记录首帧时间
        if progress._first_frame_at == 0.0:
            progress._first_frame_at = now
        progress._last_frame_at = now

        # 维护最近 20 帧的 (timestamp, frame) 列表，用于平滑 fps
        history = progress._frame_history
        history.append((now, frame_no))
        if len(history) > 20:
            del history[: len(history) - 20]

        # 至少两条记录才能计算 fps
        if len(history) >= 2:
            t0, f0 = history[0]
            t1, f1 = history[-1]
            dt = t1 - t0
            df = f1 - f0
            if dt > 0 and df > 0:
                progress.frames_per_second = df / dt
                # ETA：基于剩余帧数 / fps
                if progress.total_frames > 0 and progress.frames_per_second > 0:
                    remaining = max(
                        0, progress.total_frames - progress.current_frame
                    )
                    progress.estimated_remaining_seconds = (
                        remaining / progress.frames_per_second
                    )

    @staticmethod
    def _parse_timecode(code: str) -> Optional[float]:
        """解析 aerender 的时间码为秒。

        支持两种格式：
            - ``HH:MM:SS`` → 秒
            - ``HH:MM:SS:FF`` → 秒（忽略帧部分，或按 30fps 折算）

        Args:
            code: 时间码字符串。

        Returns:
            对应秒数；解析失败返回 None。
        """
        parts = code.split(":")
        try:
            parts_int = [int(p) for p in parts]
        except ValueError:
            return None
        if len(parts_int) == 3:
            h, m, s = parts_int
            return float(h * 3600 + m * 60 + s)
        if len(parts_int) == 4:
            h, m, s, f = parts_int
            # 帧部分按 30fps 折算为秒（AE 默认）
            return float(h * 3600 + m * 60 + s) + f / 30.0
        return None

    # ------------------------------------------------------------------
    # 状态管理辅助
    # ------------------------------------------------------------------
    def mark_completed(self) -> RenderProgress:
        """手动标记渲染完成（用于进程正常退出但未输出 Time Elapsed 的情况）。"""
        prev_status = self.progress.status
        self.progress.status = "completed"
        self._last_completed = True
        # 状态切换时触发持久化
        if prev_status != "completed":
            self._schedule_persist()
        return self.progress

    def mark_failed(self, reason: str = "") -> RenderProgress:
        """手动标记渲染失败。"""
        prev_status = self.progress.status
        self.progress.status = "failed"
        logger.error(f"AE 渲染被标记为失败: {reason}")
        # 持久化失败原因
        if prev_status != "failed" and self.repository is not None and self.job_id:
            self._schedule_persist(failure_reason=reason or None)
        elif prev_status != "failed":
            self._schedule_persist()
        return self.progress

    def reset(self, total_frames: Optional[int] = None) -> None:
        """重置解析器状态，准备新一轮渲染。

        Args:
            total_frames: 新的总帧数；不传则保留原值。
        """
        if total_frames is not None:
            self.total_frames = total_frames
        self.progress = RenderProgress(total_frames=self.total_frames)
        self._parse_start = time.time()
        self._last_completed = False
        self._last_persisted_status = None
        self._last_persisted_frame = -1

    # ------------------------------------------------------------------
    # 持久化辅助
    # ------------------------------------------------------------------
    def _should_persist(self, prev_status: str, prev_frame: int) -> bool:
        """判断当前进度是否需要持久化。

        触发条件：
        1. 状态发生变化（如 idle → rendering）
        2. 当前帧号相对上次持久化增量 >= 1
        3. 进入 completed/failed 终态
        """
        if self.repository is None or not self.job_id:
            return False
        progress = self.progress
        if progress.status != prev_status:
            return True
        if progress.status in ("completed", "failed"):
            return True
        if progress.current_frame != prev_frame:
            return True
        return False

    def _schedule_persist(self, failure_reason: Optional[str] = None) -> None:
        """异步调度持久化，不阻塞解析。

        若当前没有事件循环（同步上下文），跳过持久化并记录一次 debug 日志。
        """
        if self.repository is None or not self.job_id:
            return
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                raise RuntimeError("event loop closed")
            loop.create_task(self._persist_now(failure_reason=failure_reason))
        except RuntimeError:
            # 无事件循环（同步上下文），跳过异步持久化
            logger.debug(
                f"RenderProgressParser: 无事件循环，跳过异步持久化 "
                f"(job_id={self.job_id})"
            )

    async def _persist_now(self, failure_reason: Optional[str] = None) -> None:
        """实际执行持久化，调用 repository.update_job。"""
        if self.repository is None or not self.job_id:
            return
        progress = self.progress
        fields: dict = {
            "status": progress.status,
            "current_frame": progress.current_frame,
            "total_frames": progress.total_frames,
            "elapsed_seconds": round(progress.elapsed_seconds, 2),
            "estimated_remaining_seconds": round(
                progress.estimated_remaining_seconds, 2
            ),
        }
        if failure_reason is not None:
            fields["failure_reason"] = failure_reason
        # 计算 progress 字段 (0.0 ~ 1.0)
        if progress.total_frames > 0:
            fields["progress"] = min(
                1.0, progress.current_frame / progress.total_frames
            )
        try:
            await self.repository.update_job(self.job_id, **fields)
            self._last_persisted_status = progress.status
            self._last_persisted_frame = progress.current_frame
        except Exception as e:  # pragma: no cover - 持久化失败不应中断渲染
            logger.warning(
                f"RenderProgressParser: 持久化失败 (job_id={self.job_id}): {e}"
            )

    async def persist_progress(self) -> None:
        """主动同步当前进度到 repository（供异步上下文调用）。"""
        await self._persist_now()
