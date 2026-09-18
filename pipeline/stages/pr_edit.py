"""
pipeline/stages/pr_edit.py — S4 Premiere Pro 卡点粗剪
=====================================================

旗舰管线第四阶段：
- 导入 S3 AE 渲染的 3 段 .mov
- 读取 S2 beats.json 的 drop 时间点
- 通过 PR Bridge 执行卡点粗剪 + 标记
- 导出 FCP XML（供 S5 DaVinci 导入）

零 mock：所有操作通过真实 PR Bridge 执行。
超时：单条 JSX 120s，S4 总超时 600s。
"""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger


@dataclass
class PREditResult:
    """S4 阶段执行结果。"""

    success: bool
    timeline_xml: Path | None = None
    sequence_name: str = "FlagshipEdit"
    clips_imported: int = 0
    markers_added: int = 0
    bpm: float = 0.0
    errors: list[str] = field(default_factory=list)
    elapsed_s: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


# S4 总超时（秒）
S4_TOTAL_TIMEOUT: float = 600.0
# 单条 JSX 超时（秒）
S4_JSX_TIMEOUT: float = 120.0


class PREditStage:
    """S4 Premiere Pro 卡点粗剪阶段。

    Usage::

        stage = PREditStage(engine=premiere_engine)
        result = await stage.run(
            video_paths=[...],
            beats_json_path=Path("output/S2_beat/beats.json"),
            output_dir=Path("output/flagship/S4_premiere"),
        )
    """

    def __init__(self, engine: Any):
        """
        Args:
            engine: PremiereEngine 实例（需支持 auto_beat_edit / export_timeline_xml）
        """
        self._engine = engine

    async def run(
        self,
        video_paths: list[Path | str],
        beats_json_path: Path | str,
        output_dir: Path | str,
        sequence_name: str = "FlagshipEdit",
        project_name: str = "FlagshipPR",
    ) -> PREditResult:
        """执行 S4 卡点粗剪全流程。

        Args:
            video_paths: S3 AE 渲染的 .mov 文件列表
            beats_json_path: S2 产出的 beats.json
            output_dir: S4 输出目录
            sequence_name: PR 序列名
            project_name: PR 工程名

        Returns:
            PREditResult
        """
        t0 = time.time()
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # 验证输入
        beats_path = Path(beats_json_path)
        if not beats_path.exists():
            return PREditResult(
                success=False,
                errors=[f"beats.json not found: {beats_path}"],
                elapsed_s=time.time() - t0,
            )

        missing = [str(v) for v in video_paths if not Path(v).exists()]
        if missing:
            return PREditResult(
                success=False,
                errors=[f"Missing videos: {missing}"],
                elapsed_s=time.time() - t0,
            )

        # Step 1: 卡点粗剪
        logger.info(f"[S4] Starting beat edit: {len(video_paths)} clips, seq={sequence_name}")
        edit_result = await self._engine.auto_beat_edit(
            video_paths=video_paths,
            beats_json_path=beats_path,
            sequence_name=sequence_name,
            timeout=S4_JSX_TIMEOUT,
        )

        if not edit_result.success:
            error_code = getattr(edit_result, "error_code", None) or "UNKNOWN"
            return PREditResult(
                success=False,
                errors=[f"Beat edit failed [{error_code}]: {edit_result.error}"],
                elapsed_s=time.time() - t0,
                metadata={"edit_result": str(edit_result.metadata)},
            )

        # 解析编辑结果
        edit_meta = edit_result.metadata or {}
        result_data = edit_meta.get("result", {})
        if isinstance(result_data, str):
            try:
                result_data = json.loads(result_data)
            except (ValueError, TypeError):
                result_data = {}

        clips_count = result_data.get("clips", len(video_paths))
        markers_count = result_data.get("markers", 0)
        bpm = result_data.get("bpm", 0.0)

        logger.info(f"[S4] Beat edit done: {clips_count} clips, {markers_count} markers")

        # Step 2: 导出 FCP XML
        xml_path = output_dir / "timeline.xml"
        logger.info(f"[S4] Exporting timeline XML: {xml_path}")

        xml_result = await self._engine.export_timeline_xml(
            output_path=xml_path,
            sequence_name=sequence_name,
            timeout=S4_JSX_TIMEOUT,
        )

        if not xml_result.success:
            error_code = getattr(xml_result, "error_code", None) or "UNKNOWN"
            return PREditResult(
                success=False,
                errors=[f"XML export failed [{error_code}]: {xml_result.error}"],
                clips_imported=clips_count,
                markers_added=markers_count,
                bpm=bpm,
                elapsed_s=time.time() - t0,
            )

        # 验证 XML 产物
        if not xml_path.exists():
            # Bridge 可能处于 manual_fallback 模式
            bridge_mode = (xml_result.metadata or {}).get("bridge_mode", "")
            if bridge_mode == "manual_fallback":
                logger.warning("[S4] Bridge offline - JSX file generated for manual execution")
                return PREditResult(
                    success=False,
                    errors=["Bridge offline: timeline.xml not produced (manual fallback)"],
                    clips_imported=clips_count,
                    markers_added=markers_count,
                    bpm=bpm,
                    elapsed_s=time.time() - t0,
                    metadata={"bridge_mode": "manual_fallback"},
                )
            # xml_result.success=True 但 timeline.xml 未落盘 — 状态与产物不一致
            logger.error(f"[S4] XML export reported success but file missing: {xml_path}")
            return PREditResult(
                success=False,
                errors=[f"timeline.xml not found after export: {xml_path}"],
                clips_imported=clips_count,
                markers_added=markers_count,
                bpm=bpm,
                elapsed_s=time.time() - t0,
            )

        elapsed = time.time() - t0
        if elapsed > S4_TOTAL_TIMEOUT:
            logger.warning(f"[S4] Exceeded total timeout: {elapsed:.1f}s > {S4_TOTAL_TIMEOUT}s")

        logger.info(f"[S4] Complete in {elapsed:.1f}s: {xml_path}")
        return PREditResult(
            success=True,
            timeline_xml=xml_path if xml_path.exists() else None,
            sequence_name=sequence_name,
            clips_imported=clips_count,
            markers_added=markers_count,
            bpm=bpm,
            elapsed_s=elapsed,
            metadata={
                "project_name": project_name,
                "xml_size": xml_path.stat().st_size if xml_path.exists() else 0,
            },
        )
