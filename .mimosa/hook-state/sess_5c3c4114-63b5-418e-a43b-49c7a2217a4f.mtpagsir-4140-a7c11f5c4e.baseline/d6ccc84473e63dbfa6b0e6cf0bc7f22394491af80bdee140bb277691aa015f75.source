"""
pipeline/stages/export_final_cd.py — D-17R C+D 统一导出管线
=============================================================

方案 C+D：AE PNG 序列渲染 → FFmpeg 合成 → Resolve 调色收尾

三阶段流程（铁律不可颠倒）：
    Stage C1 — AE aerender 渲染 PNG 帧序列（无损，保留全部效果/文字动画/BorisFX）
    Stage C2 — FFmpeg 合成帧序列 + 音频 → 中间视频（libx264/ProRes）
    Stage D  — DaVinci Resolve 调色 → 最终成片（37 种预设可选）

降级策略：
    - C1 失败 → 整体失败（AE 效果无法替代）
    - C2 失败 → 整体失败（无中间文件）
    - D  失败 → 返回 C2 中间视频作为最终输出（跳过调色，不阻塞交付）

用法::

    from pipeline.stages.export_final_cd import ExportFinalCD

    pipeline = ExportFinalCD()
    result = await pipeline.run(
        project_path="D:/AE-Work/project.aep",
        comp_name="MainComp",
        output_path="output_production/final.mp4",
        audio_path="D:/AE-Work/resources/bgm.mp3",
        grade_style="cinematic",
    )
"""
from __future__ import annotations

import asyncio
import shutil
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger


# ============================================================================
#  数据结构
# ============================================================================

@dataclass
class ExportCDResult:
    """C+D 导出管线结果。"""

    success: bool = False
    output_path: Optional[Path] = None
    intermediate_path: Optional[Path] = None
    frames_dir: Optional[Path] = None
    stage_c1_ok: bool = False
    stage_c2_ok: bool = False
    stage_d_ok: bool = False
    grade_skipped: bool = False
    grade_style: str = ""
    total_frames: int = 0
    elapsed_seconds: float = 0.0
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
#  C+D 管线主体
# ============================================================================

class ExportFinalCD:
    """AE PNG → FFmpeg → Resolve 调色 三段式导出管线。

    所有引擎通过延迟导入获取，避免模块加载时的循环依赖。
    每个阶段独立计时，便于性能分析。
    """

    def __init__(
        self,
        fps: float = 24.0,
        codec: str = "libx264",
        crf: int = 16,
        pixel_format: str = "yuv420p",
        frame_pattern: str = "frame_%06d.png",
        cleanup_frames: bool = True,
    ):
        """
        Args:
            fps: 帧率（默认 24fps 电影标准）
            codec: FFmpeg 视频编码器（libx264 / libx265 / prores_ks）
            crf: 质量因子（16 = 高品质，18 = 默认高质量）
            pixel_format: 像素格式（yuv420p 兼容性最佳）
            frame_pattern: aerender PNG 序列命名模板
            cleanup_frames: 完成后是否清理帧临时目录
        """
        self.fps = fps
        self.codec = codec
        self.crf = crf
        self.pixel_format = pixel_format
        self.frame_pattern = frame_pattern
        self.cleanup_frames = cleanup_frames

    # ------------------------------------------------------------------
    #  主入口
    # ------------------------------------------------------------------

    async def run(
        self,
        project_path: Path | str,
        comp_name: str,
        output_path: Path | str,
        audio_path: Optional[Path | str] = None,
        grade_style: str = "cinematic",
        skip_grade: bool = False,
        multiprocess: Optional[int] = None,
    ) -> ExportCDResult:
        """执行 C+D 完整导出流程。

        Args:
            project_path: AE 工程文件路径 (.aep)
            comp_name: 要渲染的合成名称
            output_path: 最终输出视频路径
            audio_path: 可选音频路径（BGM，FFmpeg 阶段混入）
            grade_style: Resolve 调色预设（默认 cinematic，支持 37 种）
            skip_grade: 跳过 Stage D（仅做 C1+C2，不调色）
            multiprocess: aerender 多进程渲染进程数

        Returns:
            ExportCDResult
        """
        t0 = time.time()
        result = ExportCDResult(grade_style=grade_style)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 临时帧目录（放在 output 同级，避免跨盘移动）
        run_id = uuid.uuid4().hex[:8]
        frames_dir = output_path.parent / f"_frames_cd_{run_id}"
        frames_dir.mkdir(parents=True, exist_ok=True)
        result.frames_dir = frames_dir

        # ── Stage C1: AE → PNG 序列 ──────────────────────────────────
        logger.info(f"[C+D] Stage C1: AE aerender PNG 渲染开始")
        logger.info(f"  project={project_path}  comp={comp_name}")
        logger.info(f"  frames_dir={frames_dir}")

        c1_result = await self._stage_c1_render_png(
            project_path=project_path,
            comp_name=comp_name,
            frames_dir=frames_dir,
            multiprocess=multiprocess,
        )

        if not c1_result.success:
            result.errors.append(f"C1 AE 渲染失败: {c1_result.error}")
            result.elapsed_seconds = time.time() - t0
            self._cleanup(frames_dir)
            return result

        result.stage_c1_ok = True
        result.total_frames = c1_result.metadata.get("frame_count", 0)
        logger.info(
            f"[C+D] C1 完成: {result.total_frames} 帧, "
            f"耗时 {c1_result.duration_seconds:.1f}s"
        )

        # ── Stage C2: FFmpeg 合成 → 中间视频 ─────────────────────────
        intermediate_path = output_path.with_stem(output_path.stem + "_intermediate")
        logger.info(f"[C+D] Stage C2: FFmpeg 合成开始")

        c2_result = await self._stage_c2_ffmpeg_assemble(
            frames_dir=frames_dir,
            output_path=intermediate_path,
            audio_path=audio_path,
        )

        if not c2_result.success:
            result.errors.append(f"C2 FFmpeg 合成失败: {c2_result.error}")
            result.elapsed_seconds = time.time() - t0
            self._cleanup(frames_dir)
            return result

        result.stage_c2_ok = True
        result.intermediate_path = intermediate_path
        logger.info(
            f"[C+D] C2 完成: {intermediate_path.name}, "
            f"耗时 {c2_result.duration_seconds:.1f}s"
        )

        # ── Stage D: Resolve 调色 → 最终成片 ─────────────────────────
        if skip_grade:
            logger.info("[C+D] Stage D: 跳过调色 (skip_grade=True)")
            result.grade_skipped = True
            # 直接将中间文件复制为最终输出
            shutil.copy2(str(intermediate_path), str(output_path))
            result.stage_d_ok = True
        else:
            logger.info(f"[C+D] Stage D: Resolve 调色 (style={grade_style})")

            d_result = await self._stage_d_resolve_grade(
                input_path=intermediate_path,
                output_path=output_path,
                grade_style=grade_style,
            )

            if d_result.success:
                result.stage_d_ok = True
                logger.info(
                    f"[C+D] D 完成: {output_path.name}, "
                    f"耗时 {d_result.duration_seconds:.1f}s"
                )
            else:
                # D 失败 → 降级：用中间文件作为最终输出
                logger.warning(
                    f"[C+D] D 调色失败，降级使用中间文件: {d_result.error}"
                )
                result.grade_skipped = True
                result.errors.append(f"D 调色降级: {d_result.error}")
                shutil.copy2(str(intermediate_path), str(output_path))

        # ── 收尾 ─────────────────────────────────────────────────────
        result.success = output_path.exists() and output_path.stat().st_size > 0
        result.output_path = output_path if result.success else None
        result.elapsed_seconds = time.time() - t0

        if result.success:
            size_mb = output_path.stat().st_size / (1024 * 1024)
            logger.info(
                f"[C+D] 导出完成: {output_path} ({size_mb:.1f} MB, "
                f"总耗时 {result.elapsed_seconds:.1f}s)"
            )
            result.metadata = {
                "file_size_mb": round(size_mb, 1),
                "total_frames": result.total_frames,
                "fps": self.fps,
                "codec": self.codec,
                "crf": self.crf,
                "grade_style": grade_style,
                "stages": {
                    "C1_ae_render": result.stage_c1_ok,
                    "C2_ffmpeg_assemble": result.stage_c2_ok,
                    "D_resolve_grade": result.stage_d_ok and not result.grade_skipped,
                },
            }
        else:
            result.errors.append("最终输出文件不存在或为空")

        # 清理帧临时目录
        if self.cleanup_frames:
            self._cleanup(frames_dir)
            result.frames_dir = None

        # 清理中间文件（最终成片已包含全部内容）
        if result.success and intermediate_path.exists():
            intermediate_path.unlink(missing_ok=True)

        return result

    # ------------------------------------------------------------------
    #  Stage C1: AE aerender → PNG 序列
    # ------------------------------------------------------------------

    async def _stage_c1_render_png(
        self,
        project_path: Path | str,
        comp_name: str,
        frames_dir: Path | str,
        multiprocess: Optional[int] = None,
    ):
        """通过 aerender CLI 渲染合成到 PNG 帧序列。

        使用 'PNG Sequence' 输出模块模板确保无损帧输出。
        """
        ae = self._get_engine("ae")

        # aerender 的 PNG 序列输出：输出路径指向目录，
        # 输出模块 "PNG Sequence" 自动在目录下生成 frame_000001.png ...
        png_output = Path(frames_dir) / self.frame_pattern

        return await ae.render_comp(
            project_path=project_path,
            comp_name=comp_name,
            output_path=png_output,
            output_module="PNG Sequence",
            render_settings="Best Settings",
            multiprocess=multiprocess,
        )

    # ------------------------------------------------------------------
    #  Stage C2: FFmpeg 合成帧序列 → 视频
    # ------------------------------------------------------------------

    async def _stage_c2_ffmpeg_assemble(
        self,
        frames_dir: Path | str,
        output_path: Path | str,
        audio_path: Optional[Path | str] = None,
    ):
        """FFmpeg 将 PNG 帧序列合成为视频，可选混入音频。"""
        ff = self._get_engine("ffmpeg")

        return await ff.image_sequence_to_video(
            frames_dir=frames_dir,
            output_path=output_path,
            fps=self.fps,
            codec=self.codec,
            crf=self.crf,
            preset="slow",
            frame_pattern=self.frame_pattern,
            pixel_format=self.pixel_format,
            audio_path=audio_path,
        )

    # ------------------------------------------------------------------
    #  Stage D: Resolve 调色
    # ------------------------------------------------------------------

    async def _stage_d_resolve_grade(
        self,
        input_path: Path | str,
        output_path: Path | str,
        grade_style: str = "cinematic",
    ):
        """DaVinci Resolve 调色 → 最终成片。

        使用 DavinciEngine.apply_color_grade()，内部自动降级：
        Resolve 不可用时 → FFmpeg 滤镜调色。
        """
        davinci = self._get_engine("davinci")

        return await davinci.apply_color_grade(
            input_path=input_path,
            output_dir=Path(output_path).parent,
            style=grade_style,
        )

    # ------------------------------------------------------------------
    #  引擎获取（延迟导入 + 缓存）
    # ------------------------------------------------------------------

    _engines_cache: Dict[str, Any] = {}

    @classmethod
    def _ensure_puppet_path(cls):
        """确保 puppet-automation/src 在 sys.path 中（幂等）。"""
        import sys
        puppet_src = str(
            Path(__file__).resolve().parent.parent.parent / "puppet-automation" / "src"
        )
        if puppet_src not in sys.path:
            sys.path.insert(0, puppet_src)

    def _get_engine(self, name: str):
        """延迟导入并缓存引擎实例。"""
        if name not in self._engines_cache:
            self._ensure_puppet_path()
            if name == "ae":
                from engines.ae.engine import AEEngine
                self._engines_cache[name] = AEEngine()
            elif name == "ffmpeg":
                from engines.ffmpeg.engine import FFmpegEngine
                self._engines_cache[name] = FFmpegEngine()
            elif name == "davinci":
                from engines.davinci.engine import DavinciEngine
                self._engines_cache[name] = DavinciEngine()
            else:
                raise RuntimeError(f"Unknown engine: {name}")
        return self._engines_cache[name]

    # ------------------------------------------------------------------
    #  工具方法
    # ------------------------------------------------------------------

    @staticmethod
    def _cleanup(path: Path):
        """安全清理临时目录。"""
        try:
            if path.exists():
                shutil.rmtree(str(path), ignore_errors=True)
        except Exception:
            pass
