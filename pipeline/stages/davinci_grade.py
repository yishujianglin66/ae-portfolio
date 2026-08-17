"""
pipeline/stages/davinci_grade.py — S5 DaVinci Resolve 调色
==========================================================

旗舰管线第五阶段：
- 从 S4 导出的 timeline.xml 创建 DaVinci 工程
- 添加 ≥3 调色节点（含 1 个 LUT）
- 渲染 graded.mov

零 mock：所有操作通过 DaVinci Scripting API 真实执行。
路径约束：所有文件名强制 ASCII（^[A-Za-z0-9_-]+$）。
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger


@dataclass
class DaVinciGradeResult:
    """S5 阶段执行结果。"""

    success: bool
    graded_mov: Optional[Path] = None
    project_name: str = "FlagshipDR"
    nodes_applied: int = 0
    has_lut: bool = False
    errors: List[str] = field(default_factory=list)
    elapsed_s: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


# ASCII 文件名校验正则
_ASCII_RE = re.compile(r"^[A-Za-z0-9_-]+$")


class DaVinciGradeStage:
    """S5 DaVinci Resolve 调色阶段。

    Usage::

        stage = DaVinciGradeStage(engine=davinci_engine)
        result = await stage.run(
            timeline_xml=Path("output/S4_premiere/timeline.xml"),
            output_dir=Path("output/flagship/S5_davinci"),
        )
    """

    def __init__(self, engine: Any):
        """
        Args:
            engine: DavinciEngine 实例（需支持 create_project_from_xml /
                    apply_grade_nodes / render_graded）
        """
        self._engine = engine

    async def run(
        self,
        timeline_xml: Path | str,
        output_dir: Path | str,
        project_name: str = "FlagshipDR",
        node_count: int = 4,
        lut_name: str = "FlagshipCine",
        style_preset: str = "cinematic",
        output_filename: str = "graded.mov",
    ) -> DaVinciGradeResult:
        """执行 S5 调色全流程。

        Args:
            timeline_xml: S4 产出的 FCP XML 路径
            output_dir: S5 输出目录
            project_name: DaVinci 工程名（必须 ASCII）
            node_count: 调色节点数（≥3）
            lut_name: LUT 名称
            style_preset: 风格预设
            output_filename: 输出文件名（必须 ASCII）

        Returns:
            DaVinciGradeResult
        """
        t0 = time.time()
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # ASCII 校验
        if not _ASCII_RE.match(project_name):
            return DaVinciGradeResult(
                success=False,
                errors=[f"Project name not ASCII: {project_name}"],
                elapsed_s=time.time() - t0,
            )
        if not re.match(r"^[A-Za-z0-9_.-]+$", output_filename):
            return DaVinciGradeResult(
                success=False,
                errors=[f"Output filename not ASCII: {output_filename}"],
                elapsed_s=time.time() - t0,
            )

        # 验证输入
        xml_path = Path(timeline_xml)
        if not xml_path.exists():
            return DaVinciGradeResult(
                success=False,
                errors=[f"Timeline XML not found: {xml_path}"],
                elapsed_s=time.time() - t0,
            )

        # Step 1: 创建工程 + 导入 XML
        logger.info(f"[S5] Creating project '{project_name}' from {xml_path.name}")
        proj_result = await self._engine.create_project_from_xml(
            xml_path=xml_path,
            project_name=project_name,
        )

        if not proj_result.success:
            error_code = getattr(proj_result, "error_code", None) or "UNKNOWN"
            return DaVinciGradeResult(
                success=False,
                errors=[f"Project creation failed [{error_code}]: {proj_result.error}"],
                elapsed_s=time.time() - t0,
            )

        logger.info(f"[S5] Project created: {proj_result.metadata}")

        # Step 2: 添加调色节点
        logger.info(f"[S5] Applying {node_count} grade nodes (LUT={lut_name})")
        grade_result = await self._engine.apply_grade_nodes(
            node_count=node_count,
            include_lut=True,
            lut_name=lut_name,
            style_preset=style_preset,
        )

        if not grade_result.success:
            error_code = getattr(grade_result, "error_code", None) or "UNKNOWN"
            return DaVinciGradeResult(
                success=False,
                project_name=project_name,
                errors=[f"Grade nodes failed [{error_code}]: {grade_result.error}"],
                elapsed_s=time.time() - t0,
            )

        grade_meta = grade_result.metadata or {}
        nodes_applied = grade_meta.get("node_count", node_count)
        has_lut = grade_meta.get("include_lut", True)

        logger.info(f"[S5] Grade nodes applied: {nodes_applied} nodes, LUT={has_lut}")

        # Step 3: 渲染 graded.mov
        graded_path = output_dir / output_filename
        logger.info(f"[S5] Rendering graded output: {graded_path}")
        render_result = await self._engine.render_graded(
            output_path=graded_path,
            codec="prores",
            resolution="1920x1080",
            fps=24.0,
        )

        if not render_result.success:
            error_code = getattr(render_result, "error_code", None) or "UNKNOWN"
            return DaVinciGradeResult(
                success=False,
                project_name=project_name,
                nodes_applied=nodes_applied,
                has_lut=has_lut,
                errors=[f"Render failed [{error_code}]: {render_result.error}"],
                elapsed_s=time.time() - t0,
            )

        # 验证产物
        if not graded_path.exists():
            return DaVinciGradeResult(
                success=False,
                project_name=project_name,
                nodes_applied=nodes_applied,
                has_lut=has_lut,
                errors=["Render reported success but output file missing"],
                elapsed_s=time.time() - t0,
            )

        elapsed = time.time() - t0
        file_size = graded_path.stat().st_size
        logger.info(f"[S5] Complete in {elapsed:.1f}s: {graded_path} ({file_size} bytes)")

        return DaVinciGradeResult(
            success=True,
            graded_mov=graded_path,
            project_name=project_name,
            nodes_applied=nodes_applied,
            has_lut=has_lut,
            elapsed_s=elapsed,
            metadata={
                "file_size": file_size,
                "codec": "prores",
                "resolution": "1920x1080",
                "fps": 24.0,
                "lut_name": lut_name,
                "style_preset": style_preset,
            },
        )
