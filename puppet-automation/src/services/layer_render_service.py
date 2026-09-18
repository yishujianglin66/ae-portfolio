"""分层渲染服务 - Layer Render Service.

实现六层结构完整渲染管线：
    1. Background（背景）: 渲染器可选 AE/Blender/FFmpeg
    2. Subject（主体）: 抠像后的主体，带Alpha
    3. Midground（中间层）: 前后景之间的元素
    4. Particles（粒子）: AE粒子系统，叠加模式
    5. Light（光效）: 光斑/镜头光晕，加色混合
    6. Adjustment（调整层）: 调色/全局效果/LUT

支持缓存机制、多层合成、统计信息等功能。
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from ..config import settings
from ..engines.ae.engine import AEEngine
from ..engines.base import EngineResult
from ..engines.blender.engine import BlenderEngine
from ..engines.ffmpeg.engine import FFmpegEngine
from ..models.layer_pipeline import (
    BlendMode,
    LayerConfig,
    LayerRenderResult,
    LayerStats,
    OutputFormat,
    PipelineRenderResult,
    RendererType,
    RenderPipeline,
)


class LayerRenderService:
    """分层渲染服务系统 - 支持六层标准渲染管线.

    负责按层级顺序渲染各图层，支持缓存复用，最后合成输出。
    """

    def __init__(
        self,
        ae_engine: AEEngine | None = None,
        blender_engine: BlenderEngine | None = None,
        ffmpeg_engine: FFmpegEngine | None = None,
        cache_dir: Path | None = None,
    ):
        """初始化分层渲染服务.

        Args:
            ae_engine: AE 引擎实例（可选，默认使用全局配置）
            blender_engine: Blender 引擎实例（可选，默认使用全局配置）
            ffmpeg_engine: FFmpeg 引擎实例（可选，默认使用全局配置）
            cache_dir: 缓存目录（可选，默认使用 settings.cache_dir / 'layer_render'）
        """
        self.ae = ae_engine or AEEngine(settings.aerender_path)
        self.blender = blender_engine or BlenderEngine(settings.blender_path)
        self.ffmpeg = ffmpeg_engine or FFmpegEngine(settings.ffmpeg_path)
        self.cache_dir = Path(cache_dir) if cache_dir else settings.cache_dir / "layer_render"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info("LayerRenderService initialized")

    # ============================================================
    # Public API - 核心渲染方法
    # ============================================================

    async def render_pipeline(
        self,
        pipeline: RenderPipeline,
        output_path: Path | str,
        **kwargs: Any,
    ) -> PipelineRenderResult:
        """按层级顺序渲染完整管线，支持缓存，最后合成输出.

        Args:
            pipeline: 渲染管线配置
            output_path: 最终输出文件路径
            **kwargs: 额外参数

        Returns:
            PipelineRenderResult: 管线渲染结果
        """
        start_time = time.time()
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        work_dir = Path(pipeline.work_dir) if pipeline.work_dir else settings.temp_dir / f"pipeline_{pipeline.name}"
        work_dir.mkdir(parents=True, exist_ok=True)

        cache_dir = Path(pipeline.cache_dir) if pipeline.cache_dir else self.cache_dir / pipeline.name
        if pipeline.cache_enabled:
            cache_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"开始渲染管线: {pipeline.name}, 输出: {output_path}")

        layer_outputs: dict[str, LayerRenderResult] = {}
        cache_hits = 0
        cache_misses = 0

        sorted_layers = pipeline.get_sorted_layers()
        logger.info(f"共 {len(sorted_layers)} 个图层待渲染")

        try:
            for layer_config in sorted_layers:
                if not layer_config.visible:
                    logger.debug(f"跳过不可见图层: {layer_config.name}")
                    layer_outputs[layer_config.name] = LayerRenderResult(
                        layer_name=layer_config.name,
                        success=True,
                        cache_hit=False,
                        metadata={"skipped": True, "reason": "invisible"},
                    )
                    continue

                layer_work_dir = work_dir / layer_config.name
                layer_work_dir.mkdir(parents=True, exist_ok=True)

                layer_result = await self.render_layer(
                    layer_config=layer_config,
                    work_dir=layer_work_dir,
                    cache_dir=cache_dir if pipeline.cache_enabled else None,
                    resolution=pipeline.output_resolution,
                    fps=pipeline.output_fps,
                    duration=pipeline.duration,
                    **kwargs,
                )

                layer_outputs[layer_config.name] = layer_result

                if layer_result.cache_hit:
                    cache_hits += 1
                    logger.info(f"图层缓存命中: {layer_config.name}")
                else:
                    cache_misses += 1
                    if not layer_result.success:
                        logger.error(f"图层渲染失败: {layer_config.name}, 错误: {layer_result.error}")
                        return PipelineRenderResult(
                            pipeline_name=pipeline.name,
                            success=False,
                            error=f"图层 {layer_config.name} 渲染失败: {layer_result.error}",
                            layer_results=layer_outputs,
                            cache_hits=cache_hits,
                            cache_misses=cache_misses,
                            total_duration_seconds=time.time() - start_time,
                        )

            visible_layer_outputs = [
                layer_outputs[layer.name]
                for layer in pipeline.get_visible_layers()
                if layer.name in layer_outputs and layer_outputs[layer.name].output_path
            ]

            if len(visible_layer_outputs) == 0:
                return PipelineRenderResult(
                    pipeline_name=pipeline.name,
                    success=False,
                    error="没有可合成的可见图层",
                    layer_results=layer_outputs,
                    cache_hits=cache_hits,
                    cache_misses=cache_misses,
                    total_duration_seconds=time.time() - start_time,
                )

            logger.info(f"开始合成 {len(visible_layer_outputs)} 个图层")
            composite_result = await self.composite_layers(
                layer_outputs=visible_layer_outputs,
                output_path=output_path,
                output_format=pipeline.output_format,
                composite_renderer=pipeline.composite_renderer,
                resolution=pipeline.output_resolution,
                fps=pipeline.output_fps,
                **kwargs,
            )

            total_duration = time.time() - start_time
            logger.info(f"管线渲染完成: {pipeline.name}, 耗时: {total_duration:.2f}s, 缓存命中: {cache_hits}/{cache_hits + cache_misses}")

            return PipelineRenderResult(
                pipeline_name=pipeline.name,
                success=composite_result.success,
                output_path=str(output_path) if composite_result.success else None,
                total_duration_seconds=total_duration,
                layer_results=layer_outputs,
                cache_hits=cache_hits,
                cache_misses=cache_misses,
                metadata=composite_result.metadata,
                error=composite_result.error,
            )

        except Exception as e:
            logger.exception(f"管线渲染异常: {pipeline.name}, 错误: {e}")
            return PipelineRenderResult(
                pipeline_name=pipeline.name,
                success=False,
                error=str(e),
                layer_results=layer_outputs,
                cache_hits=cache_hits,
                cache_misses=cache_misses,
                total_duration_seconds=time.time() - start_time,
            )

    async def render_layer(
        self,
        layer_config: LayerConfig,
        work_dir: Path | str,
        cache_dir: Path | str | None = None,
        resolution: tuple[int, int] = (1920, 1080),
        fps: float = 30.0,
        duration: float = 10.0,
        **kwargs: Any,
    ) -> LayerRenderResult:
        """渲染单层，输出带Alpha的序列帧.

        Args:
            layer_config: 图层配置
            work_dir: 工作目录
            cache_dir: 缓存目录（None 表示禁用缓存）
            resolution: 输出分辨率 (width, height)
            fps: 输出帧率
            duration: 时长（秒）
            **kwargs: 额外参数

        Returns:
            LayerRenderResult: 图层渲染结果
        """
        start_time = time.time()
        work_dir = Path(work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"开始渲染图层: {layer_config.name} (类型: {layer_config.type.value}, 渲染器: {layer_config.renderer.value})")

        if cache_dir and layer_config.visible:
            cache_dir = Path(cache_dir)
            cached_path = self.check_cache(layer_config, cache_dir)
            if cached_path:
                logger.info(f"缓存命中: {layer_config.name}")
                frame_count = len(list(cached_path.glob("*.png"))) + len(list(cached_path.glob("*.exr")))
                file_size = self._calculate_dir_size(cached_path)
                return LayerRenderResult(
                    layer_name=layer_config.name,
                    success=True,
                    output_path=str(cached_path),
                    duration_seconds=0.0,
                    file_size_bytes=file_size,
                    frame_count=frame_count,
                    cache_hit=True,
                )

        output_path = work_dir / "output"
        output_path.mkdir(parents=True, exist_ok=True)

        try:
            if layer_config.renderer == RendererType.AE:
                result = await self._render_layer_ae(
                    layer_config=layer_config,
                    output_dir=output_path,
                    resolution=resolution,
                    fps=fps,
                    duration=duration,
                    **kwargs,
                )
            elif layer_config.renderer == RendererType.BLENDER:
                result = await self._render_layer_blender(
                    layer_config=layer_config,
                    output_dir=output_path,
                    resolution=resolution,
                    fps=fps,
                    duration=duration,
                    **kwargs,
                )
            elif layer_config.renderer == RendererType.FFMPEG:
                result = await self._render_layer_ffmpeg(
                    layer_config=layer_config,
                    output_dir=output_path,
                    resolution=resolution,
                    fps=fps,
                    duration=duration,
                    **kwargs,
                )
            else:
                return LayerRenderResult(
                    layer_name=layer_config.name,
                    success=False,
                    error=f"不支持的渲染器: {layer_config.renderer}",
                )

            duration_seconds = time.time() - start_time
            frame_count = len(list(output_path.glob("*.png"))) + len(list(output_path.glob("*.exr")))
            file_size = self._calculate_dir_size(output_path)

            if result.success and cache_dir and layer_config.visible:
                await self._save_cache(layer_config, output_path, Path(cache_dir))

            logger.info(f"图层渲染完成: {layer_config.name}, 耗时: {duration_seconds:.2f}s, 帧数: {frame_count}")

            return LayerRenderResult(
                layer_name=layer_config.name,
                success=result.success,
                output_path=str(output_path) if result.success else None,
                duration_seconds=duration_seconds,
                file_size_bytes=file_size,
                frame_count=frame_count,
                cache_hit=False,
                metadata=result.metadata,
                error=result.error,
            )

        except Exception as e:
            logger.exception(f"图层渲染异常: {layer_config.name}, 错误: {e}")
            return LayerRenderResult(
                layer_name=layer_config.name,
                success=False,
                error=str(e),
                duration_seconds=time.time() - start_time,
            )

    async def composite_layers(
        self,
        layer_outputs: list[LayerRenderResult],
        output_path: Path | str,
        output_format: OutputFormat = OutputFormat.PNG_SEQUENCE,
        composite_renderer: RendererType = RendererType.FFMPEG,
        resolution: tuple[int, int] = (1920, 1080),
        fps: float = 30.0,
        **kwargs: Any,
    ) -> EngineResult:
        """多层合成（使用 FFmpeg 或 AE）.

        Args:
            layer_outputs: 图层渲染结果列表（按从下到上顺序）
            output_path: 输出文件路径
            output_format: 输出格式
            composite_renderer: 合成使用的渲染器
            resolution: 输出分辨率
            fps: 输出帧率
            **kwargs: 额外参数

        Returns:
            EngineResult: 合成结果
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"开始合成 {len(layer_outputs)} 个图层，使用 {composite_renderer.value}")

        if len(layer_outputs) == 0:
            return EngineResult(
                success=False,
                error="没有可合成的图层",
            )

        if len(layer_outputs) == 1:
            single_output = Path(layer_outputs[0].output_path) if layer_outputs[0].output_path else None
            if single_output and single_output.exists():
                logger.info("只有一个图层，直接复制输出")
                if output_format == OutputFormat.PNG_SEQUENCE or output_format == OutputFormat.EXR_SEQUENCE:
                    import shutil
                    if output_path.is_dir() or output_path.suffix == "":
                        output_path.mkdir(parents=True, exist_ok=True)
                        for f in single_output.glob("*"):
                            shutil.copy2(f, output_path / f.name)
                    return EngineResult(success=True, output_path=output_path)
                else:
                    return await self._convert_sequence_to_video(
                        seq_dir=single_output,
                        output_path=output_path,
                        output_format=output_format,
                        fps=fps,
                    )

        if composite_renderer == RendererType.FFMPEG:
            return await self._composite_with_ffmpeg(
                layer_outputs=layer_outputs,
                output_path=output_path,
                output_format=output_format,
                resolution=resolution,
                fps=fps,
                **kwargs,
            )
        elif composite_renderer == RendererType.AE:
            return await self._composite_with_ae(
                layer_outputs=layer_outputs,
                output_path=output_path,
                output_format=output_format,
                resolution=resolution,
                fps=fps,
                **kwargs,
            )
        else:
            return EngineResult(
                success=False,
                error=f"不支持的合成渲染器: {composite_renderer}",
            )

    def check_cache(
        self,
        layer_config: LayerConfig,
        cache_dir: Path | str,
    ) -> Path | None:
        """检查该层是否有缓存可复用.

        Args:
            layer_config: 图层配置
            cache_dir: 缓存目录

        Returns:
            缓存目录路径（如果存在且有效），否则 None
        """
        cache_dir = Path(cache_dir)
        cache_key = self._generate_cache_key(layer_config)
        cache_path = cache_dir / cache_key

        if not cache_path.exists():
            return None

        manifest_path = cache_path / "cache_manifest.json"
        if not manifest_path.exists():
            return None

        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)

            if manifest.get("cache_key") != cache_key:
                logger.debug(f"缓存键不匹配: {layer_config.name}")
                return None

            frame_files = list(cache_path.glob("*.png")) + list(cache_path.glob("*.exr"))
            if len(frame_files) == 0:
                logger.debug(f"缓存目录为空: {cache_path}")
                return None

            logger.debug(f"缓存有效: {layer_config.name} -> {cache_path}")
            return cache_path

        except Exception as e:
            logger.warning(f"读取缓存清单失败: {e}")
            return None

    def list_presets(self) -> list[dict[str, str]]:
        """列出所有预设模板。"""
        from ..models.layer_pipeline import PipelinePreset

        preset_descriptions = {
            "cinematic_vlog": "电影感 Vlog — 6 层完整结构，适合高品质短视频",
            "music_video": "音乐视频 — 粒子 + 灯光层丰富，重视觉冲击",
            "title_sequence": "标题序列 — 文字 + 光效为主，适合开场/转场",
        }
        return [
            {
                "name": preset.value,
                "description": preset_descriptions.get(preset.value, ""),
            }
            for preset in PipelinePreset
        ]

    def build_from_preset(
        self,
        preset: PipelinePreset | str,
        name: str | None = None,
        resolution: tuple[int, int] = (1920, 1080),
        fps: float = 30.0,
        duration: float = 10.0,
    ) -> RenderPipeline:
        """根据预设模板构建渲染管线.

        Args:
            preset: 预设模板枚举或字符串 (cinematic_vlog/music_video/title_sequence)
            name: 管线名称（可选，默认使用 preset 值）
            resolution: 输出分辨率
            fps: 输出帧率
            duration: 总时长（秒）

        Returns:
            RenderPipeline: 构建好的渲染管线配置
        """
        from ..models.layer_pipeline import (
            BlendMode,
            LayerConfig,
            LayerType,
            OutputFormat,
            PipelinePreset,
            RendererType,
        )

        if isinstance(preset, str):
            preset = PipelinePreset(preset)

        pipeline_name = name or f"{preset.value}_pipeline"
        layers: list[LayerConfig] = []

        if preset == PipelinePreset.CINEMATIC_VLOG:
            layers = [
                LayerConfig(
                    name="Background",
                    type=LayerType.BACKGROUND,
                    renderer=RendererType.AE,
                    z_index=0,
                    params={"gradient_type": "linear", "colors": ["#1a1a2e", "#0f3460"]},
                ),
                LayerConfig(
                    name="Subject",
                    type=LayerType.SUBJECT,
                    renderer=RendererType.AE,
                    z_index=10,
                    params={"keying_method": "keylight"},
                ),
                LayerConfig(
                    name="Midground",
                    type=LayerType.MIDGROUND,
                    renderer=RendererType.AE,
                    z_index=5,
                    visible=False,
                    params={"elements": []},
                ),
                LayerConfig(
                    name="Particles",
                    type=LayerType.PARTICLES,
                    renderer=RendererType.AE,
                    z_index=20,
                    blend_mode=BlendMode.SCREEN,
                    opacity=60.0,
                    params={"particle_type": "dust", "particle_count": 100},
                ),
                LayerConfig(
                    name="Light",
                    type=LayerType.LIGHT,
                    renderer=RendererType.AE,
                    z_index=30,
                    blend_mode=BlendMode.ADD,
                    opacity=40.0,
                    params={"flare_type": "anamorphic", "intensity": 0.8},
                ),
                LayerConfig(
                    name="Adjustment",
                    type=LayerType.ADJUSTMENT,
                    renderer=RendererType.FFMPEG,
                    z_index=100,
                    params={"lut_path": None, "color_temperature": 5500},
                ),
            ]

        elif preset == PipelinePreset.MUSIC_VIDEO:
            layers = [
                LayerConfig(
                    name="Background",
                    type=LayerType.BACKGROUND,
                    renderer=RendererType.BLENDER,
                    z_index=0,
                    params={"style": "minimal", "animated": True},
                ),
                LayerConfig(
                    name="Subject",
                    type=LayerType.SUBJECT,
                    renderer=RendererType.AE,
                    z_index=10,
                    params={"keying_method": "keylight"},
                ),
                LayerConfig(
                    name="Particles",
                    type=LayerType.PARTICLES,
                    renderer=RendererType.AE,
                    z_index=20,
                    blend_mode=BlendMode.SCREEN,
                    opacity=80.0,
                    params={"particle_type": "sparkle", "particle_count": 500},
                ),
                LayerConfig(
                    name="Light",
                    type=LayerType.LIGHT,
                    renderer=RendererType.AE,
                    z_index=30,
                    blend_mode=BlendMode.ADD,
                    opacity=70.0,
                    params={"flare_type": "lens_flare", "intensity": 1.2},
                ),
                LayerConfig(
                    name="Adjustment",
                    type=LayerType.ADJUSTMENT,
                    renderer=RendererType.FFMPEG,
                    z_index=100,
                    params={"beat_sync": True, "flash_intensity": 0.3},
                ),
            ]

        elif preset == PipelinePreset.TITLE_SEQUENCE:
            layers = [
                LayerConfig(
                    name="Background",
                    type=LayerType.BACKGROUND,
                    renderer=RendererType.BLENDER,
                    z_index=0,
                    params={"style": "wooden", "animated": False},
                ),
                LayerConfig(
                    name="Subject",
                    type=LayerType.SUBJECT,
                    renderer=RendererType.BLENDER,
                    z_index=10,
                    params={"element_type": "text", "text": "TITLE"},
                ),
                LayerConfig(
                    name="Light",
                    type=LayerType.LIGHT,
                    renderer=RendererType.AE,
                    z_index=30,
                    blend_mode=BlendMode.ADD,
                    opacity=50.0,
                    params={"flare_type": "volumetric", "intensity": 1.0},
                ),
                LayerConfig(
                    name="Adjustment",
                    type=LayerType.ADJUSTMENT,
                    renderer=RendererType.FFMPEG,
                    z_index=100,
                    params={"cinematic_crop": True, "grain": 0.1},
                ),
            ]

        return RenderPipeline(
            name=pipeline_name,
            layers=layers,
            output_resolution=resolution,
            output_fps=fps,
            duration=duration,
            preset=preset,
        )

    def get_layer_stats(
        self,
        pipeline: RenderPipeline,
    ) -> dict[str, LayerStats]:
        """获取各层统计信息（渲染时间、文件大小等）.

        Args:
            pipeline: 渲染管线配置

        Returns:
            图层名称 -> LayerStats 字典
        """
        stats: dict[str, LayerStats] = {}

        for layer in pipeline.layers:
            file_size = 0
            if layer.output_path:
                output_path = Path(layer.output_path)
                if output_path.exists():
                    if output_path.is_dir():
                        file_size = self._calculate_dir_size(output_path)
                    else:
                        file_size = output_path.stat().st_size

            stats[layer.name] = LayerStats(
                layer_name=layer.name,
                layer_type=layer.type,
                renderer=layer.renderer,
                z_index=layer.z_index,
                file_size_bytes=file_size,
                visible=layer.visible,
            )

        return stats

    # ============================================================
    # Private - 各渲染器实现
    # ============================================================

    async def _render_layer_ae(
        self,
        layer_config: LayerConfig,
        output_dir: Path,
        resolution: tuple[int, int],
        fps: float,
        duration: float,
        **kwargs: Any,
    ) -> EngineResult:
        """使用 AE 渲染图层.

        Args:
            layer_config: 图层配置
            output_dir: 输出目录
            resolution: 分辨率
            fps: 帧率
            duration: 时长
            **kwargs: 额外参数

        Returns:
            EngineResult: 渲染结果
        """
        logger.debug(f"AE 渲染图层: {layer_config.name}, 类型: {layer_config.type.value}")

        params = layer_config.params
        width, height = resolution
        total_frames = int(duration * fps)

        comp_name = f"Layer_{layer_config.name}"

        output_pattern = str(output_dir / "frame_%06d.png")

        try:
            create_result = await self.ae.create_comp(
                name=comp_name,
                width=width,
                height=height,
                fps=fps,
                duration=duration,
            )
            if not create_result.success:
                return EngineResult(
                    success=False,
                    error=f"创建合成失败: {create_result.error}",
                )

            await self._build_ae_layer_content(
                comp_name=comp_name,
                layer_config=layer_config,
                total_frames=total_frames,
            )

            project_path = kwargs.get("project_path")
            if project_path:
                render_result = await self.ae.render_comp(
                    project_path=Path(project_path),
                    comp_name=comp_name,
                    output_path=Path(output_pattern),
                    output_module="Lossless with Alpha",
                )
            else:
                render_result = EngineResult(
                    success=True,
                    output_path=output_dir,
                    metadata={"comp_name": comp_name, "mode": "script_only"},
                )
                logger.warning("未提供 project_path，AE 渲染跳过，仅创建合成结构")

            return render_result

        except Exception as e:
            logger.exception(f"AE 渲染图层异常: {e}")
            return EngineResult(success=False, error=str(e))

    async def _build_ae_layer_content(
        self,
        comp_name: str,
        layer_config: LayerConfig,
        total_frames: int,
    ) -> None:
        """构建 AE 图层内容（根据图层类型应用不同效果）.

        Args:
            comp_name: 合成名称
            layer_config: 图层配置
            total_frames: 总帧数
        """
        params = layer_config.params

        if layer_config.type.value == "background":
            await self._ae_build_background(comp_name, params, total_frames)
        elif layer_config.type.value == "subject":
            await self._ae_build_subject(comp_name, params, total_frames)
        elif layer_config.type.value == "midground":
            await self._ae_build_midground(comp_name, params, total_frames)
        elif layer_config.type.value == "particles":
            await self._ae_build_particles(comp_name, params, total_frames)
        elif layer_config.type.value == "light":
            await self._ae_build_light(comp_name, params, total_frames)
        elif layer_config.type.value == "adjustment":
            await self._ae_build_adjustment(comp_name, params, total_frames)

    async def _ae_build_background(
        self,
        comp_name: str,
        params: dict[str, Any],
        total_frames: int,
    ) -> None:
        """构建 AE 背景层."""
        gradient_type = params.get("gradient_type", "linear")
        colors = params.get("colors", ["#1a1a2e", "#0f3460"])
        animated = params.get("animated", False)

        await self.ae.add_layer(
            comp_name=comp_name,
            layer_type="solid",
            name="BG_Base",
            color=[0.1, 0.1, 0.2],
        )

        logger.debug(f"背景层构建完成: {comp_name}")

    async def _ae_build_subject(
        self,
        comp_name: str,
        params: dict[str, Any],
        total_frames: int,
    ) -> None:
        """构建 AE 主体层."""
        source_path = params.get("source_path")
        keying_method = params.get("keying_method", "keylight")

        if source_path:
            try:
                await self.ae.import_footage(
                    footage_path=Path(source_path),
                    comp_name=comp_name,
                )
            except Exception as e:
                logger.warning(f"导入主体素材失败: {e}")

        logger.debug(f"主体层构建完成: {comp_name}, 抠像方式: {keying_method}")

    async def _ae_build_midground(
        self,
        comp_name: str,
        params: dict[str, Any],
        total_frames: int,
    ) -> None:
        """构建 AE 中间层."""
        elements = params.get("elements", [])
        logger.debug(f"中间层构建完成: {comp_name}, 元素: {elements}")

    async def _ae_build_particles(
        self,
        comp_name: str,
        params: dict[str, Any],
        total_frames: int,
    ) -> None:
        """构建 AE 粒子层."""
        particle_type = params.get("particle_type", "dust")
        particle_count = params.get("particle_count", 200)

        await self.ae.add_layer(
            comp_name=comp_name,
            layer_type="solid",
            name="Particles",
            color=[0, 0, 0],
        )

        logger.debug(f"粒子层构建完成: {comp_name}, 类型: {particle_type}, 数量: {particle_count}")

    async def _ae_build_light(
        self,
        comp_name: str,
        params: dict[str, Any],
        total_frames: int,
    ) -> None:
        """构建 AE 光效层."""
        flare_type = params.get("flare_type", "anamorphic")
        intensity = params.get("intensity", 1.0)

        await self.ae.add_layer(
            comp_name=comp_name,
            layer_type="solid",
            name="LightFX",
            color=[0, 0, 0],
        )

        logger.debug(f"光效层构建完成: {comp_name}, 类型: {flare_type}, 强度: {intensity}")

    async def _ae_build_adjustment(
        self,
        comp_name: str,
        params: dict[str, Any],
        total_frames: int,
    ) -> None:
        """构建 AE 调整层."""
        effects: list[dict[str, Any]] = []

        if params.get("lut"):
            effects.append({"effectName": "ADBE Lumetri", "params": {}})

        if params.get("contrast", 1.0) != 1.0:
            effects.append({"effectName": "ADBE Brightness & Contrast", "params": {"Contrast": params["contrast"]}})

        if params.get("saturation", 1.0) != 1.0:
            effects.append({"effectName": "ADBE HUE SATURATION", "params": {}})

        await self.ae.add_adjustment_layer(
            comp_name=comp_name,
            name="Adjustment",
            effects=effects,
        )

        logger.debug(f"调整层构建完成: {comp_name}, 效果数: {len(effects)}")

    async def _render_layer_blender(
        self,
        layer_config: LayerConfig,
        output_dir: Path,
        resolution: tuple[int, int],
        fps: float,
        duration: float,
        **kwargs: Any,
    ) -> EngineResult:
        """使用 Blender 渲染图层.

        Args:
            layer_config: 图层配置
            output_dir: 输出目录
            resolution: 分辨率
            fps: 帧率
            duration: 时长
            **kwargs: 额外参数

        Returns:
            EngineResult: 渲染结果
        """
        logger.debug(f"Blender 渲染图层: {layer_config.name}, 类型: {layer_config.type.value}")

        params = layer_config.params
        scene_style = params.get("scene_style", "minimal")
        render_engine = params.get("render_engine", "BLENDER_EEVEE")

        try:
            result = await self.blender.create_puppet_stage(
                output_dir=output_dir,
                style=scene_style if scene_style in ["wooden", "minimal", "vintage"] else "minimal",
                resolution=resolution,
                render_engine=render_engine,
                export_ae=params.get("export_ae", False),
                ae_frame_start=1,
                ae_frame_end=int(duration * fps),
            )

            if result.success:
                frames_dir = output_dir / "frames"
                if frames_dir.exists():
                    result.output_path = frames_dir

            return result

        except Exception as e:
            logger.exception(f"Blender 渲染图层异常: {e}")
            return EngineResult(success=False, error=str(e))

    async def _render_layer_ffmpeg(
        self,
        layer_config: LayerConfig,
        output_dir: Path,
        resolution: tuple[int, int],
        fps: float,
        duration: float,
        **kwargs: Any,
    ) -> EngineResult:
        """使用 FFmpeg 渲染图层（主要用于素材转换/生成纯色背景等）.

        Args:
            layer_config: 图层配置
            output_dir: 输出目录
            resolution: 分辨率
            fps: 帧率
            duration: 时长
            **kwargs: 额外参数

        Returns:
            EngineResult: 渲染结果
        """
        logger.debug(f"FFmpeg 渲染图层: {layer_config.name}, 类型: {layer_config.type.value}")

        source_path = layer_config.source_path
        width, height = resolution

        try:
            if source_path and Path(source_path).exists():
                output_pattern = str(output_dir / "frame_%06d.png")
                result = await self.ffmpeg.extract_frames(
                    video_path=Path(source_path),
                    output_dir=output_dir,
                    fps=fps,
                    image_format="png",
                )
                return result
            else:
                color = layer_config.params.get("color", "#000000")
                color_rgb = self._hex_to_rgb_tuple(color)
                output_pattern = str(output_dir / "frame_%06d.png")

                cmd = [
                    str(self.ffmpeg.executable_path),
                    "-y",
                    "-f", "lavfi",
                    "-i", f"color=c=0x{color.lstrip('#')}:s={width}x{height}:d={duration}:r={fps}",
                    "-vf", "format=rgba",
                    output_pattern,
                ]

                code, stdout, stderr = await asyncio.to_thread(
                    self.ffmpeg._run_subprocess, cmd, timeout=3600
                )

                return EngineResult(
                    success=code == 0,
                    output_path=output_dir if code == 0 else None,
                    error=stderr if code != 0 else None,
                    metadata={"frames": len(list(output_dir.glob("*.png")))},
                )

        except Exception as e:
            logger.exception(f"FFmpeg 渲染图层异常: {e}")
            return EngineResult(success=False, error=str(e))

    # ============================================================
    # Private - 合成实现
    # ============================================================

    async def _composite_with_ffmpeg(
        self,
        layer_outputs: list[LayerRenderResult],
        output_path: Path,
        output_format: OutputFormat,
        resolution: tuple[int, int],
        fps: float,
        **kwargs: Any,
    ) -> EngineResult:
        """使用 FFmpeg 进行多层合成.

        通过 filter_complex 的 overlay 滤镜逐层叠加。

        Args:
            layer_outputs: 图层渲染结果列表（从下到上）
            output_path: 输出路径
            output_format: 输出格式
            resolution: 分辨率
            fps: 帧率
            **kwargs: 额外参数

        Returns:
            EngineResult: 合成结果
        """
        logger.info(f"使用 FFmpeg 合成 {len(layer_outputs)} 个图层")

        try:
            valid_layers = [
                layer for layer in layer_outputs
                if layer.output_path and Path(layer.output_path).exists()
            ]

            if len(valid_layers) == 0:
                return EngineResult(success=False, error="没有有效的图层输出")

            if len(valid_layers) == 1:
                seq_dir = Path(valid_layers[0].output_path)
                if output_format in [OutputFormat.PNG_SEQUENCE, OutputFormat.EXR_SEQUENCE]:
                    import shutil
                    if output_path.suffix == "":
                        output_path.mkdir(parents=True, exist_ok=True)
                        for f in seq_dir.glob("*"):
                            shutil.copy2(f, output_path / f.name)
                    return EngineResult(success=True, output_path=output_path)
                else:
                    return await self._convert_sequence_to_video(
                        seq_dir=seq_dir,
                        output_path=output_path,
                        output_format=output_format,
                        fps=fps,
                    )

            seq_dirs = [Path(layer.output_path) for layer in valid_layers]
            first_frames = sorted(seq_dirs[0].glob("*.png"))
            if not first_frames:
                first_frames = sorted(seq_dirs[0].glob("*.exr"))
            if not first_frames:
                return EngineResult(success=False, error="找不到序列帧文件")

            cmd = [str(self.ffmpeg.executable_path), "-y"]

            for seq_dir in seq_dirs:
                input_pattern = str(seq_dir / "frame_%06d.png")
                alt_pattern = str(seq_dir / "frame_%06d.exr")
                if list(seq_dir.glob("*.png")):
                    cmd.extend(["-framerate", str(fps), "-i", input_pattern])
                elif list(seq_dir.glob("*.exr")):
                    cmd.extend(["-framerate", str(fps), "-i", alt_pattern])
                else:
                    cmd.extend(["-framerate", str(fps), "-i", input_pattern])

            filter_parts = []
            for i in range(1, len(valid_layers)):
                if i == 1:
                    filter_parts.append(f"[0:v][1:v]overlay=0:0[v{i}]")
                else:
                    filter_parts.append(f"[v{i-1}][{i}:v]overlay=0:0[v{i}]")

            if filter_parts:
                filter_complex = ";".join(filter_parts)
                last_label = f"v{len(valid_layers) - 1}"
                cmd.extend(["-filter_complex", filter_complex])
                cmd.extend(["-map", f"[{last_label}]"])

            if output_format == OutputFormat.PNG_SEQUENCE:
                if output_path.suffix == "":
                    output_path.mkdir(parents=True, exist_ok=True)
                    output_pattern = str(output_path / "frame_%06d.png")
                else:
                    output_pattern = str(output_path)
                cmd.extend(["-frames:v", str(int(resolution[1] * fps))])
                cmd.append(output_pattern)
            elif output_format == OutputFormat.EXR_SEQUENCE:
                if output_path.suffix == "":
                    output_path.mkdir(parents=True, exist_ok=True)
                    output_pattern = str(output_path / "frame_%06d.exr")
                else:
                    output_pattern = str(output_path)
                cmd.extend(["-pix_fmt", "rgbaf"])
                cmd.append(output_pattern)
            else:
                codec, crf = self._get_ffmpeg_codec_params(output_format)
                cmd.extend(["-c:v", codec, "-crf", str(crf), "-pix_fmt", "yuv420p"])
                cmd.append(str(output_path))

            code, stdout, stderr = await asyncio.to_thread(
                self.ffmpeg._run_subprocess, cmd, timeout=14400
            )

            return EngineResult(
                success=code == 0,
                output_path=output_path if code == 0 else None,
                error=stderr[:1000] if code != 0 else None,
                metadata={
                    "layer_count": len(valid_layers),
                    "method": "ffmpeg_overlay",
                },
            )

        except Exception as e:
            logger.exception(f"FFmpeg 合成异常: {e}")
            return EngineResult(success=False, error=str(e))

    async def _composite_with_ae(
        self,
        layer_outputs: list[LayerRenderResult],
        output_path: Path,
        output_format: OutputFormat,
        resolution: tuple[int, int],
        fps: float,
        **kwargs: Any,
    ) -> EngineResult:
        """使用 AE 进行多层合成.

        Args:
            layer_outputs: 图层渲染结果列表（从下到上）
            output_path: 输出路径
            output_format: 输出格式
            resolution: 分辨率
            fps: 帧率
            **kwargs: 额外参数

        Returns:
            EngineResult: 合成结果
        """
        logger.info(f"使用 AE 合成 {len(layer_outputs)} 个图层")

        comp_name = "Composite_Main"
        width, height = resolution

        try:
            create_result = await self.ae.create_comp(
                name=comp_name,
                width=width,
                height=height,
                fps=fps,
                duration=kwargs.get("duration", 10.0),
            )

            if not create_result.success:
                return EngineResult(
                    success=False,
                    error=f"创建合成失败: {create_result.error}",
                )

            for i, layer_result in enumerate(layer_outputs):
                if layer_result.output_path:
                    layer_dir = Path(layer_result.output_path)
                    frame_files = sorted(layer_dir.glob("*.png"))
                    if not frame_files:
                        frame_files = sorted(layer_dir.glob("*.exr"))
                    if frame_files:
                        try:
                            await self.ae.import_footage(
                                footage_path=frame_files[0],
                                comp_name=comp_name,
                                as_sequence=True,
                            )
                        except Exception as e:
                            logger.warning(f"导入图层 {layer_result.layer_name} 失败: {e}")

            project_path = kwargs.get("project_path")
            if project_path:
                output_module = self._get_ae_output_module(output_format)
                render_result = await self.ae.render_comp(
                    project_path=Path(project_path),
                    comp_name=comp_name,
                    output_path=output_path,
                    output_module=output_module,
                )
                return render_result
            else:
                return EngineResult(
                    success=True,
                    output_path=output_path,
                    metadata={"comp_name": comp_name, "mode": "script_only"},
                )

        except Exception as e:
            logger.exception(f"AE 合成异常: {e}")
            return EngineResult(success=False, error=str(e))

    async def _convert_sequence_to_video(
        self,
        seq_dir: Path,
        output_path: Path,
        output_format: OutputFormat,
        fps: float,
    ) -> EngineResult:
        """将序列帧转换为视频文件.

        Args:
            seq_dir: 序列帧目录
            output_path: 输出视频路径
            output_format: 输出格式
            fps: 帧率

        Returns:
            EngineResult: 转换结果
        """
        seq_dir = Path(seq_dir)
        output_path = Path(output_path)

        png_files = sorted(seq_dir.glob("*.png"))
        exr_files = sorted(seq_dir.glob("*.exr"))

        if png_files:
            input_pattern = str(seq_dir / "frame_%06d.png")
        elif exr_files:
            input_pattern = str(seq_dir / "frame_%06d.exr")
        else:
            return EngineResult(success=False, error="序列帧目录为空")

        codec, crf = self._get_ffmpeg_codec_params(output_format)

        cmd = [
            str(self.ffmpeg.executable_path),
            "-y",
            "-framerate", str(fps),
            "-i", input_pattern,
            "-c:v", codec,
            "-crf", str(crf),
            "-pix_fmt", "yuv420p",
            str(output_path),
        ]

        code, stdout, stderr = await asyncio.to_thread(
            self.ffmpeg._run_subprocess, cmd, timeout=7200
        )

        return EngineResult(
            success=code == 0,
            output_path=output_path if code == 0 else None,
            error=stderr[:1000] if code != 0 else None,
            metadata={"frame_count": len(png_files) + len(exr_files)},
        )

    # ============================================================
    # Private - 缓存管理
    # ============================================================

    def _generate_cache_key(self, layer_config: LayerConfig) -> str:
        """生成图层的缓存键.

        Args:
            layer_config: 图层配置

        Returns:
            缓存键字符串
        """
        if layer_config.cache_key:
            return layer_config.cache_key

        config_dict = layer_config.model_dump()
        config_str = json.dumps(config_dict, sort_keys=True, ensure_ascii=False)
        hash_obj = hashlib.md5(config_str.encode("utf-8"))
        return f"{layer_config.type.value}_{hash_obj.hexdigest()[:16]}"

    async def _save_cache(
        self,
        layer_config: LayerConfig,
        output_dir: Path,
        cache_dir: Path,
    ) -> None:
        """保存渲染结果到缓存.

        Args:
            layer_config: 图层配置
            output_dir: 渲染输出目录
            cache_dir: 缓存根目录
        """
        try:
            import shutil

            cache_key = self._generate_cache_key(layer_config)
            cache_path = cache_dir / cache_key
            cache_path.mkdir(parents=True, exist_ok=True)

            for item in output_dir.iterdir():
                dest = cache_path / item.name
                if item.is_dir():
                    if dest.exists():
                        shutil.rmtree(dest)
                    shutil.copytree(item, dest)
                else:
                    shutil.copy2(item, dest)

            manifest = {
                "cache_key": cache_key,
                "layer_name": layer_config.name,
                "layer_type": layer_config.type.value,
                "renderer": layer_config.renderer.value,
                "params": layer_config.params,
                "created_at": time.time(),
            }

            manifest_path = cache_path / "cache_manifest.json"
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, ensure_ascii=False, indent=2)

            logger.debug(f"缓存已保存: {layer_config.name} -> {cache_path}")

        except Exception as e:
            logger.warning(f"保存缓存失败: {layer_config.name}, 错误: {e}")

    # ============================================================
    # Private - 工具方法
    # ============================================================

    def _calculate_dir_size(self, dir_path: Path) -> int:
        """计算目录的总文件大小.

        Args:
            dir_path: 目录路径

        Returns:
            总字节数
        """
        total = 0
        try:
            for item in Path(dir_path).rglob("*"):
                if item.is_file():
                    total += item.stat().st_size
        except Exception:
            pass
        return total

    def _hex_to_rgb_tuple(self, hex_color: str) -> tuple[int, int, int]:
        """将 HEX 颜色转换为 RGB 元组.

        Args:
            hex_color: HEX 颜色字符串

        Returns:
            (R, G, B) 元组 (0-255)
        """
        hex_color = hex_color.lstrip("#")
        return (
            int(hex_color[0:2], 16),
            int(hex_color[2:4], 16),
            int(hex_color[4:6], 16),
        )

    def _get_ffmpeg_codec_params(self, output_format: OutputFormat) -> tuple[str, int]:
        """获取 FFmpeg 编码参数.

        Args:
            output_format: 输出格式

        Returns:
            (codec, crf) 元组
        """
        codec_map = {
            OutputFormat.H264: ("libx264", 18),
            OutputFormat.H265: ("libx265", 23),
            OutputFormat.PRORES_4444: ("prores_ks", 0),
            OutputFormat.PRORES_422: ("prores_ks", 0),
        }
        return codec_map.get(output_format, ("libx264", 18))

    def _get_ae_output_module(self, output_format: OutputFormat) -> str:
        """获取 AE 输出模块模板名称.

        Args:
            output_format: 输出格式

        Returns:
            输出模块模板名称
        """
        module_map = {
            OutputFormat.H264: "H.264",
            OutputFormat.H265: "H.265",
            OutputFormat.PRORES_4444: "ProRes 4444",
            OutputFormat.PRORES_422: "ProRes 422",
            OutputFormat.PNG_SEQUENCE: "Lossless with Alpha",
            OutputFormat.EXR_SEQUENCE: "OpenEXR",
        }
        return module_map.get(output_format, "Lossless with Alpha")
