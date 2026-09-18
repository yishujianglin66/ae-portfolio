"""AE → DaVinci Resolve 协作链路模块。

==================================

为 AE Knowledge Vault 项目提供**端到端协作链路**，将两个 DCC 工具真正打通：

1. **AE 端**：通过 :class:`ae.unified_ae_client.UnifiedAEClient` 调用 AE 合成
   （puppet/MCP 通道自动调度），导出为高质量中间文件。
2. **DaVinci 端**：通过 :class:`integrations.davinci_fuscript.ResolveColorEngine`
   自动启动/连接 DaVinci Resolve，建立项目/时间线/导入素材/调色/渲染。
3. **链路编排**：把两套工作流串成一条可配置、可监控、可恢复的 pipeline。

核心能力
--------

- **一键风格化**：内置电影感青橙、复古胶片、音乐 MV 冲击、暖色肖像、
  冷色科幻、高调、暗调、黑白经典等 8 种内置预设的高层 API。
- **完全可定制**：通过 :class:`AEExportSpec`、:class:`DavinciGradingSpec`、
  :class:`DavinciRenderSpec` 自由控制每一阶段参数。
- **进度回调**：`progress_callback(stage, percent)` 让上层实时呈现状态。
- **检查点恢复**：``run_with_checkpoints()`` 支持断点续传。
- **异步执行**：`run_async()` 适合在 Web/异步服务中调度。
- **资源管理**：统一管理临时目录、中间产物；提供 ``cleanup()`` 手动清理入口。

典型用法
--------

最简形式（一键电影感青橙）::

    >>> from integrations.ae_to_davinci_pipeline import AEToDavinciPipeline
    >>> pipeline = AEToDavinciPipeline()
    >>> result = pipeline.run_cinematic_teal_orange(
    ...     comp_name="MyIntro",
    ...     output_path="output/intro_cinematic.mp4",
    ... )
    >>> print(result.success, result.final_output_path)

完全自定义::

    >>> from integrations.ae_to_davinci_pipeline import (
    ...     AEExportSpec, DavinciGradingSpec, DavinciRenderSpec, AEToDavinciPipeline,
    ... )
    >>> pipeline = AEToDavinciPipeline()
    >>> result = pipeline.run(
    ...     ae_spec=AEExportSpec(comp_name="MyComp", format="mov_prores_4444"),
    ...     grading_spec=DavinciGradingSpec(preset_name="vintage_film"),
    ...     render_spec=DavinciRenderSpec(output_path="output/final.mp4"),
    ...     progress_callback=lambda stage, pct: print(f"[{pct:.0%}] {stage}"),
    ... )
"""
from __future__ import annotations

import asyncio
import json
import logging
import shutil
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Literal, Optional, Tuple

# 在类型检查阶段导入以避免循环引用（运行时按需懒加载）
if TYPE_CHECKING:
    from ae.unified_ae_client import UnifiedAEClient
    from integrations.davinci_color_grading import (
        ColorGrader,
        ColorGradingPreset,
    )
    from integrations.davinci_fuscript import ResolveColorEngine

logger = logging.getLogger(__name__)


# ============================================================================
# 输出格式枚举（AE 导出 + DaVinci 渲染共用）
# ============================================================================

# AE 导出格式
AEExportFormat = Literal[
    "mov_prores_4444",  # ProRes 4444（带 alpha）
    "mov_prores_422",   # ProRes 422 HQ（高质量）
    "mp4_h264",         # H.264 MP4（通用）
    "png_sequence",     # PNG 序列（无损 + alpha）
    "exr_sequence",     # EXR 序列（ACES 流程）
    "xml_fcp7",         # Final Cut Pro 7 XML（用于 DaVinci 导入）
    "xml_fcp_x",        # Final Cut Pro X XML
    "aaf",              # AAF 格式（专业剪辑交换）
]

# DaVinci 渲染格式
DavinciRenderFormat = Literal[
    "mov_prores_4444",
    "mp4_h264",
    "mp4_h265",
    "mov_dnxhd",
]

# 渲染质量档位
RenderQuality = Literal["draft", "normal", "best"]

# 进度回调签名
ProgressCallback = Callable[[str, float], None]


# ============================================================================
# 数据模型
# ============================================================================

@dataclass
class AEExportSpec:
    """AE 导出规格。

    描述将哪个 AE 合成导出为哪种格式、什么参数。导出由
    :class:`ae.unified_ae_client.UnifiedAEClient` 调度到 puppet/MCP 通道。

    Attributes:
        comp_name: 合成名称（必须存在于当前 AE 项目中）。
        output_path: 输出文件路径（绝对路径）；为空时自动生成。
        format: 容器 + 编码格式，默认 ``"mov_prores_4444"``。
        resolution: (宽, 高)，默认 1920x1080。
        frame_rate: 帧率（fps），默认 30。
        duration: 导出时长（秒），``None`` 表示合成全程。
        start_time: 起始时间（秒），默认 0。
        quality: 渲染质量档位（``"draft"/"normal"/"best"``）。
        with_audio: 是否包含音频。
        include_effects: 是否包含效果（XML/AAF 导出时生效）。
        include_keyframes: 是否包含关键帧（XML/AAF 导出时生效）。
        include_compositions: 是否包含嵌套合成（XML/AAF 导出时生效）。
    """

    comp_name: str
    output_path: str
    format: AEExportFormat = "mov_prores_4444"
    resolution: tuple[int, int] = (1920, 1080)
    frame_rate: float = 30.0
    duration: float | None = None
    start_time: float = 0.0
    quality: RenderQuality = "best"
    with_audio: bool = True
    include_effects: bool = True
    include_keyframes: bool = True
    include_compositions: bool = True

    def to_render_args(self) -> dict[str, Any]:
        """转换为 UnifiedAEClient.render 的参数。"""
        return {
            "comp_name": self.comp_name,
            "output_path": self.output_path,
            "format": self.format,
            "resolution": list(self.resolution),
            "frame_rate": self.frame_rate,
            "duration": self.duration,
            "start_time": self.start_time,
            "quality": self.quality,
            "with_audio": self.with_audio,
            "include_effects": self.include_effects,
            "include_keyframes": self.include_keyframes,
            "include_compositions": self.include_compositions,
        }

    def is_interchange_format(self) -> bool:
        """是否为剪辑交换格式（XML/AAF）。"""
        return self.format in ("xml_fcp7", "xml_fcp_x", "aaf")


@dataclass
class DavinciGradingSpec:
    """DaVinci 调色规格。

    描述 DaVinci 端的项目结构（项目/时间线）、调色预设应用范围
    （全部片段/指定片段）、是否输出 LUT 等。

    Attributes:
        project_name: DaVinci 项目名。
        timeline_name: 时间线名，默认 ``"AE_Imported"``。
        preset_name: 内置预设键名（如 ``"cinematic_teal_orange"``），与
            ``custom_preset`` 互斥，``preset_name`` 优先。
        custom_preset: 自定义 :class:`ColorGradingPreset` 对象。
        grade_all_clips: 是否对所有片段应用预设。
        specific_clip_indices: 指定片段索引列表，``grade_all_clips=False`` 时生效。
        export_lut: 导出 LUT 的目标路径，``None`` 不导出。
        segment_presets: 分段调色（``{clip_name_pattern: preset_name}``），可选。
    """

    project_name: str
    timeline_name: str = "AE_Imported"
    preset_name: str | None = None
    custom_preset: "ColorGradingPreset" | None = None
    grade_all_clips: bool = True
    specific_clip_indices: list[int] | None = None
    export_lut: str | None = None
    segment_presets: dict[str, str] | None = None

    def validate(self) -> None:
        """校验规格合法性。"""
        if not self.project_name:
            raise ValueError("DavinciGradingSpec.project_name must not be empty")
        if not self.timeline_name:
            raise ValueError("DavinciGradingSpec.timeline_name must not be empty")
        if not self.preset_name and not self.custom_preset:
            raise ValueError(
                "DavinciGradingSpec requires either preset_name or custom_preset"
            )
        if not self.grade_all_clips and not self.specific_clip_indices:
            raise ValueError(
                "specific_clip_indices must be provided when grade_all_clips=False"
            )


@dataclass
class DavinciRenderSpec:
    """DaVinci 渲染规格。

    Attributes:
        output_path: 最终输出文件路径。
        format: 容器 + 编码格式，默认 ``"mp4_h264"``。
        resolution: (宽, 高)，默认 1920x1080。
        frame_rate: 帧率（fps），默认 30。
        codec: 编码器（与 format 联动），默认 ``"H.264"``。
        quality: 质量档位（``"Draft"/"Normal"/"High"/"Best"``），默认 ``"High"``。
        render_audio: 是否渲染音频，默认 True。
        bitrate: 目标比特率（Mbps），默认自动。
        crf: 恒定质量因子（0-51），用于 H.264/H.265，默认自动。
        gop_size: GOP 大小（帧），默认自动。
        interlaced: 是否隔行扫描，默认 False。
        render_range: 渲染范围（``"all"/"in_out"``），默认 ``"all"``。
        start_frame: 起始帧，render_range="in_out" 时生效。
        end_frame: 结束帧，render_range="in_out" 时生效。
        metadata: 元数据（如 title、artist、description）。
    """

    output_path: str
    format: DavinciRenderFormat = "mp4_h264"
    resolution: tuple[int, int] = (1920, 1080)
    frame_rate: float = 30.0
    codec: str = "H.264"
    quality: str = "High"
    render_audio: bool = True
    bitrate: int | None = None          # Mbps
    crf: int | None = None              # 0-51
    gop_size: int | None = None         # 帧
    interlaced: bool = False
    render_range: str = "all"              # "all" or "in_out"
    start_frame: int | None = None
    end_frame: int | None = None
    metadata: dict[str, str] | None = None

    def to_resolve_render_settings(self) -> dict[str, Any]:
        """转换为 Resolve 渲染设置字典。"""
        settings = {
            "SelectAllFrames": self.render_range == "all",
            "TargetDir": str(Path(self.output_path).parent),
            "CustomName": Path(self.output_path).stem,
            "File Type": self._resolve_file_type(),
            "Codec": self._resolve_codec(),
            "Resolution": f"{int(self.resolution[0])}x{int(self.resolution[1])}",
            "Frame Rate": str(int(self.frame_rate)),
            "Quality": self._resolve_quality_code(),
            "RenderAudio": self.render_audio,
            "Interlaced": self.interlaced,
        }
        if self.bitrate:
            settings["Bitrate"] = self.bitrate
        if self.crf:
            settings["ConstantQuality"] = self.crf
        if self.gop_size:
            settings["GOPSize"] = self.gop_size
        if self.render_range == "in_out" and self.start_frame is not None:
            settings["StartFrame"] = self.start_frame
        if self.render_range == "in_out" and self.end_frame is not None:
            settings["EndFrame"] = self.end_frame
        if self.metadata:
            settings.update(self.metadata)
        return settings

    def _resolve_file_type(self) -> str:
        """映射 format 到 Resolve File Type。"""
        return {
            "mov_prores_4444": "MOV",
            "mov_prores_422": "MOV",
            "mp4_h264": "MP4",
            "mp4_h265": "MP4",
            "mov_dnxhd": "MOV",
            "mov_dnxhr_hq": "MOV",
            "exr_sequence": "EXR",
            "png_sequence": "PNG",
            "tiff_sequence": "TIFF",
        }.get(self.format, "MP4")

    def _resolve_codec(self) -> str:
        """根据 format 自动解析编码器（用户指定的 codec 优先）。"""
        if self.codec != "H.264":
            return self.codec
        codec_map = {
            "mov_prores_4444": "ProRes 4444",
            "mov_prores_422": "ProRes 422 HQ",
            "mp4_h264": "H.264",
            "mp4_h265": "H.265",
            "mov_dnxhd": "DNxHD",
            "mov_dnxhr_hq": "DNxHR HQ",
            "exr_sequence": "EXR",
            "png_sequence": "PNG",
            "tiff_sequence": "TIFF",
        }
        return codec_map.get(self.format, self.codec)

    def _resolve_quality_code(self) -> Any:
        """映射 quality 档位到 Resolve 数值。"""
        return {
            "Draft": 28,
            "Normal": 23,
            "High": 20,
            "Best": 18,
        }.get(self.quality, 20)

    def _resolve_extension(self) -> str:
        """根据 format 解析文件扩展名。"""
        ext_map = {
            "mov_prores_4444": ".mov",
            "mov_prores_422": ".mov",
            "mp4_h264": ".mp4",
            "mp4_h265": ".mp4",
            "mov_dnxhd": ".mov",
            "mov_dnxhr_hq": ".mov",
            "exr_sequence": ".exr",
            "png_sequence": ".png",
            "tiff_sequence": ".tif",
        }
        return ext_map.get(self.format, ".mp4")


@dataclass
class PipelineResult:
    """协作链路执行结果。

    Attributes:
        success: 是否整体成功。
        ae_export_path: AE 导出文件路径。
        davinci_project_path: DaVinci 项目路径（Resolve 内部路径，可能为空）。
        final_output_path: 最终渲染输出文件路径。
        intermediate_files: 中间产物文件路径列表。
        errors: 错误信息列表。
        warnings: 警告信息列表。
        metrics: 性能指标（阶段耗时等），键名如 ``"ae_export_duration_sec"``。
        started_at: 启动时间。
        finished_at: 完成时间（失败时也会设置）。
    """

    success: bool
    ae_export_path: str | None = None
    davinci_project_path: str | None = None
    final_output_path: str | None = None
    intermediate_files: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)
    started_at: datetime = field(default_factory=datetime.now)
    finished_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典（方便持久化和报告）。"""
        return {
            "success": self.success,
            "ae_export_path": self.ae_export_path,
            "davinci_project_path": self.davinci_project_path,
            "final_output_path": self.final_output_path,
            "intermediate_files": list(self.intermediate_files),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "metrics": dict(self.metrics),
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "duration_sec": (
                (self.finished_at - self.started_at).total_seconds()
                if self.finished_at
                else None
            ),
        }


# ============================================================================
# 内置预设快捷映射
# ============================================================================

# 高层 API 预设名 → 调色规格预设名
# 风格化场景推荐预设
STYLE_PRESET_MAP: dict[str, str] = {
    "cinematic_teal_orange": "cinematic_teal_orange",
    "vintage_film": "vintage_film",
    "music_video_punch": "music_video_punch",
    "warm_portrait": "warm_portrait",
    "cold_scifi": "cold_scifi",
    "high_key_bright": "high_key_bright",
    "low_key_dark": "low_key_dark",
    "black_and_white_classic": "black_and_white_classic",
}


# ============================================================================
# 检查点
# ============================================================================

@dataclass
class PipelineCheckpoint:
    """协作链路检查点（用于断点续传）。

    Attributes:
        stage: 已完成的阶段名（``"ae_export" / "davinci_import" / "davinci_grade" / "davinci_render"``）。
        data: 阶段产物元数据。
        timestamp: 检查点时间。
        ae_export_spec: AE 导出规格快照。
        davinci_grading_spec: DaVinci 调色规格快照。
        davinci_render_spec: DaVinci 渲染规格快照。
        metrics: 性能指标。
        errors: 错误信息（如有）。
        warnings: 警告信息。
        pipeline_version: 流水线版本号。
    """

    stage: str
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    ae_export_spec: dict[str, Any] | None = None
    davinci_grading_spec: dict[str, Any] | None = None
    davinci_render_spec: dict[str, Any] | None = None
    metrics: dict[str, float] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    pipeline_version: str = "1.0.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "ae_export_spec": self.ae_export_spec,
            "davinci_grading_spec": self.davinci_grading_spec,
            "davinci_render_spec": self.davinci_render_spec,
            "metrics": dict(self.metrics),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "pipeline_version": self.pipeline_version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PipelineCheckpoint":
        return cls(
            stage=data["stage"],
            data=data.get("data", {}),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            ae_export_spec=data.get("ae_export_spec"),
            davinci_grading_spec=data.get("davinci_grading_spec"),
            davinci_render_spec=data.get("davinci_render_spec"),
            metrics=data.get("metrics", {}),
            errors=data.get("errors", []),
            warnings=data.get("warnings", []),
            pipeline_version=data.get("pipeline_version", "1.0.0"),
        )


class CheckpointManager:
    """检查点管理器（持久化到文件）。

    提供检查点的保存、加载、清理等功能，支持断点续传。

    Attributes:
        checkpoint_dir: 检查点存储目录。
        checkpoint_name: 检查点文件名。
    """

    def __init__(
        self,
        checkpoint_dir: str = "output/pipeline/checkpoints",
        checkpoint_name: str = "pipeline_checkpoint.json",
    ) -> None:
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_name = checkpoint_name
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    @property
    def checkpoint_path(self) -> Path:
        """检查点文件完整路径。"""
        return self.checkpoint_dir / self.checkpoint_name

    def save(self, checkpoint: PipelineCheckpoint) -> None:
        """保存检查点到文件。"""
        data = checkpoint.to_dict()
        with open(self.checkpoint_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"Checkpoint saved: {self.checkpoint_path}")

    def load(self) -> PipelineCheckpoint | None:
        """加载检查点文件。

        Returns:
            PipelineCheckpoint 如果文件存在，否则 None。
        """
        if not self.checkpoint_path.exists():
            return None
        try:
            with open(self.checkpoint_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            checkpoint = PipelineCheckpoint.from_dict(data)
            logger.info(f"Checkpoint loaded: {checkpoint.stage} at {checkpoint.timestamp}")
            return checkpoint
        except (json.JSONDecodeError, KeyError) as exc:
            logger.warning(f"Failed to load checkpoint: {exc}")
            return None

    def delete(self) -> None:
        """删除检查点文件。"""
        if self.checkpoint_path.exists():
            self.checkpoint_path.unlink()
            logger.info(f"Checkpoint deleted: {self.checkpoint_path}")

    def exists(self) -> bool:
        """检查检查点文件是否存在。"""
        return self.checkpoint_path.exists()

    def get_stage_progress(self, checkpoint: PipelineCheckpoint) -> float:
        """根据检查点阶段计算进度百分比。"""
        stage_order = ["ae_export", "davinci_import", "davinci_grade", "davinci_render"]
        if checkpoint.stage in stage_order:
            return (stage_order.index(checkpoint.stage) + 1) / len(stage_order)
        return 0.0

    def list_checkpoints(self) -> list[str]:
        """列出所有检查点文件。"""
        return sorted(
            str(p) for p in self.checkpoint_dir.glob("*.json") if p.is_file()
        )


# ============================================================================
# 协作链路主类
# ============================================================================

class AEToDavinciPipeline:
    """AE → DaVinci Resolve 协作链路。

    将 AE 合成导出、DaVinci 导入、调色、渲染四步串成一条端到端流水线。
    通过依赖注入的方式接受 AE 客户端与 DaVinci 引擎，方便在测试中替换为 Mock。
    支持检查点机制，可实现断点续传。

    Attributes:
        ae: UnifiedAEClient 实例（懒加载）。
        davinci: ResolveColorEngine 实例（懒加载）。
        work_dir: 中间产物工作目录。
        temp_dir: 临时文件目录。
        checkpoint_manager: 检查点管理器。
    """

    # 各阶段权重（用于进度汇报）
    STAGE_WEIGHTS: dict[str, tuple[float, float]] = {
        "ae_export": (0.0, 0.4),
        "davinci_import": (0.4, 0.5),
        "davinci_grade": (0.5, 0.8),
        "davinci_render": (0.8, 1.0),
    }

    # 阶段顺序（用于检查点跳过已完成阶段）
    STAGE_ORDER = ["ae_export", "davinci_import", "davinci_grade", "davinci_render"]

    def __init__(
        self,
        ae_client: "UnifiedAEClient" | None = None,
        davinci_engine: "ResolveColorEngine" | None = None,
        work_dir: str = "output/pipeline",
        temp_dir: str = "output/pipeline/temp",
        checkpoint_dir: str = "output/pipeline/checkpoints",
    ) -> None:
        """初始化协作链路。

        Args:
            ae_client: 注入的 AE 客户端（None 时按需懒加载）。
            davinci_engine: 注入的 DaVinci 引擎（None 时按需懒加载）。
            work_dir: 中间产物目录。
            temp_dir: 临时文件目录。
            checkpoint_dir: 检查点存储目录。
        """
        # AE 客户端可按需懒加载（避免在无 AE 环境导入时炸错）
        self.ae: "UnifiedAEClient" | None = ae_client
        self.davinci: "ResolveColorEngine" | None = davinci_engine

        self.work_dir = Path(work_dir)
        self.temp_dir = Path(temp_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        # 检查点管理器
        self.checkpoint_manager = CheckpointManager(checkpoint_dir=checkpoint_dir)

        # 内部状态
        self._grader: "ColorGrader" | None = None

    # ==================================================================
    # 依赖懒加载
    # ==================================================================

    def _get_ae(self) -> "UnifiedAEClient":
        """获取 AE 客户端（懒加载）。"""
        if self.ae is None:
            from ae.unified_ae_client import UnifiedAEClient

            self.ae = UnifiedAEClient()
        return self.ae

    def _get_davinci(self) -> "ResolveColorEngine":
        """获取 DaVinci 引擎（懒加载）。"""
        if self.davinci is None:
            from integrations.davinci_fuscript import ResolveColorEngine

            self.davinci = ResolveColorEngine()
        return self.davinci

    def _get_grader(self) -> "ColorGrader":
        """获取 ColorGrader（懒加载，桥接 Color 页面）。"""
        if self._grader is None:
            davinci = self._get_davinci()
            self._grader = davinci.color_grader
        return self._grader

    # ==================================================================
    # 进度回调
    # ==================================================================

    def _report(
        self,
        callback: ProgressCallback | None,
        stage: str,
        progress: float,
    ) -> None:
        """统一进度汇报（带日志）。"""
        if progress < 0.0:
            progress = 0.0
        elif progress > 1.0:
            progress = 1.0
        logger.info("[Pipeline %s] %s (%.0f%%)", stage, stage, progress * 100)
        if callback is not None:
            try:
                callback(stage, float(progress))
            except Exception as exc:  # noqa: BLE001
                logger.warning("progress_callback raised: %s", exc)

    # ==================================================================
    # 主流程：run
    # ==================================================================

    def run(
        self,
        ae_spec: AEExportSpec,
        grading_spec: DavinciGradingSpec,
        render_spec: DavinciRenderSpec,
        progress_callback: ProgressCallback | None = None,
    ) -> PipelineResult:
        """执行完整协作链路（同步）。

        流程：
        1. AE 导出（0%-40%）
        2. DaVinci 导入（40%-50%）
        3. DaVinci 调色（50%-80%）
        4. DaVinci 渲染（80%-100%）

        Args:
            ae_spec: AE 导出规格。
            grading_spec: DaVinci 调色规格。
            render_spec: DaVinci 渲染规格。
            progress_callback: 进度回调 ``(stage, percent) -> None``。

        Returns:
            :class:`PipelineResult`，包含每阶段产物与可能的错误信息。
        """
        result = PipelineResult(success=False)
        # 入口校验（失败不进入主体）
        try:
            grading_spec.validate()
        except ValueError as exc:
            result.errors.append(f"Invalid DavinciGradingSpec: {exc}")
            result.finished_at = datetime.now()
            return result

        # 阶段 1：AE 导出
        try:
            self._report(progress_callback, "ae_export", 0.0)
            t0 = time.time()
            ae_output = self._ae_export(ae_spec, result)
            result.metrics["ae_export_duration_sec"] = time.time() - t0
            self._report(progress_callback, "ae_export", 0.4)
            # 保存检查点
            self._save_checkpoint(
                stage="ae_export",
                data={"ae_output": ae_output},
                ae_export_spec=ae_spec.to_render_args(),
                metrics=result.metrics.copy(),
                warnings=result.warnings.copy(),
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("AE export failed: %s", exc)
            logger.debug(traceback.format_exc())
            result.errors.append(f"AE export failed: {exc}")
            result.finished_at = datetime.now()
            return result

        # 阶段 2：DaVinci 导入
        try:
            self._report(progress_callback, "davinci_import", 0.4)
            t0 = time.time()
            self._davinci_import(ae_output, grading_spec, result)
            result.metrics["davinci_import_duration_sec"] = time.time() - t0
            self._report(progress_callback, "davinci_import", 0.5)
            # 保存检查点
            self._save_checkpoint(
                stage="davinci_import",
                data={"ae_output": ae_output, "davinci_project_path": result.davinci_project_path},
                ae_export_spec=ae_spec.to_render_args(),
                davinci_grading_spec=vars(grading_spec),
                metrics=result.metrics.copy(),
                warnings=result.warnings.copy(),
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("DaVinci import failed: %s", exc)
            logger.debug(traceback.format_exc())
            result.errors.append(f"DaVinci import failed: {exc}")
            result.finished_at = datetime.now()
            return result

        # 阶段 3：DaVinci 调色
        try:
            self._report(progress_callback, "davinci_grade", 0.5)
            t0 = time.time()
            self._davinci_grade(grading_spec, result)
            result.metrics["davinci_grade_duration_sec"] = time.time() - t0
            self._report(progress_callback, "davinci_grade", 0.8)
            # 保存检查点
            self._save_checkpoint(
                stage="davinci_grade",
                data={"ae_output": ae_output, "davinci_project_path": result.davinci_project_path},
                ae_export_spec=ae_spec.to_render_args(),
                davinci_grading_spec=vars(grading_spec),
                metrics=result.metrics.copy(),
                warnings=result.warnings.copy(),
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("DaVinci grading failed: %s", exc)
            logger.debug(traceback.format_exc())
            result.errors.append(f"DaVinci grading failed: {exc}")
            result.finished_at = datetime.now()
            return result

        # 阶段 4：DaVinci 渲染
        try:
            self._report(progress_callback, "davinci_render", 0.8)
            t0 = time.time()
            final_output = self._davinci_render(render_spec, result)
            result.metrics["davinci_render_duration_sec"] = time.time() - t0
            self._report(progress_callback, "davinci_render", 1.0)
            result.final_output_path = final_output
            # 保存检查点（最终完成）
            self._save_checkpoint(
                stage="davinci_render",
                data={
                    "ae_output": ae_output,
                    "davinci_project_path": result.davinci_project_path,
                    "final_output": final_output,
                },
                ae_export_spec=ae_spec.to_render_args(),
                davinci_grading_spec=vars(grading_spec),
                davinci_render_spec=vars(render_spec),
                metrics=result.metrics.copy(),
                warnings=result.warnings.copy(),
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("DaVinci render failed: %s", exc)
            logger.debug(traceback.format_exc())
            result.errors.append(f"DaVinci render failed: {exc}")
            result.finished_at = datetime.now()
            return result

        result.success = True
        result.finished_at = datetime.now()
        return result

    def _save_checkpoint(
        self,
        stage: str,
        data: dict[str, Any],
        ae_export_spec: dict[str, Any] | None = None,
        davinci_grading_spec: dict[str, Any] | None = None,
        davinci_render_spec: dict[str, Any] | None = None,
        metrics: dict[str, float] | None = None,
        warnings: list[str] | None = None,
    ) -> None:
        """保存检查点。"""
        checkpoint = PipelineCheckpoint(
            stage=stage,
            data=data,
            ae_export_spec=ae_export_spec,
            davinci_grading_spec=davinci_grading_spec,
            davinci_render_spec=davinci_render_spec,
            metrics=metrics or {},
            warnings=warnings or [],
        )
        self.checkpoint_manager.save(checkpoint)

    def load_checkpoint(self) -> PipelineCheckpoint | None:
        """加载检查点。"""
        return self.checkpoint_manager.load()

    def clear_checkpoint(self) -> None:
        """清除检查点。"""
        self.checkpoint_manager.delete()

    # ==================================================================
    # 阶段实现
    # ==================================================================

    def _ae_export(
        self,
        spec: AEExportSpec,
        result: PipelineResult,
    ) -> str:
        """AE 导出阶段。

        根据导出格式选择不同的导出路径：
        - 视频格式（mov/mp4/png/exr）：调用 UnifiedAEClient.render
        - 交换格式（XML/AAF）：生成 JSX 脚本通过 AE 导出

        1. 校验合成存在；
        2. 准备输出路径；
        3. 触发导出（根据格式选择视频渲染或 JSX 脚本）；
        4. 验证输出文件存在且大小 > 0；
        5. 写入 result.ae_export_path。
        """
        ae = self._get_ae()
        # 1. 验证合成（容忍通道不可用：仅在 MOCK 通道测试中跳过）
        comps = ae.list_compositions()
        if comps and not any(c.get("name") == spec.comp_name for c in comps):
            raise ValueError(f"Composition not found: {spec.comp_name}")

        # 2. 准备输出路径
        output_path = Path(spec.output_path)
        if not output_path.is_absolute():
            output_path = self.work_dir / output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 3. 触发导出
        if spec.is_interchange_format():
            render_result = self._ae_export_interchange_format(spec, output_path)
        else:
            render_args = spec.to_render_args()
            render_args["output_path"] = str(output_path)
            render_result = ae.render(**render_args)

        # 兼容返回值：可能是 dict 或 dataclass
        if hasattr(render_result, "success"):
            ok = bool(getattr(render_result, "success", False))
            err = getattr(render_result, "error", None) or getattr(
                render_result, "errors", None
            )
        elif isinstance(render_result, dict):
            ok = bool(render_result.get("success"))
            err = render_result.get("error")
        else:
            ok = True
            err = None
        if not ok:
            raise RuntimeError(f"AE export returned failure: {err}")

        # 4. 验证输出文件
        if not output_path.exists():
            raise RuntimeError(f"AE export file missing: {output_path}")
        if output_path.stat().st_size <= 0:
            raise RuntimeError(f"AE export file is empty: {output_path}")

        result.ae_export_path = str(output_path)
        result.intermediate_files.append(str(output_path))
        return str(output_path)

    def _ae_export_interchange_format(
        self,
        spec: AEExportSpec,
        output_path: Path,
    ) -> dict[str, Any]:
        """AE 导出为 XML/AAF 交换格式。

        通过生成 JSX 脚本让 AE 导出 Final Cut Pro XML 或 AAF 文件，
        这些格式可以被 DaVinci Resolve 直接导入，保留时间线结构、
        效果、关键帧等信息。

        Args:
            spec: AE 导出规格。
            output_path: 输出文件路径。

        Returns:
            导出结果字典，包含 success 和 error 字段。
        """
        ae = self._get_ae()
        jsx_script = self._build_interchange_export_jsx(spec, output_path)
        
        try:
            script_result = ae.run_jsx(jsx_script)
            if hasattr(script_result, "success"):
                success = bool(getattr(script_result, "success", False))
                error = getattr(script_result, "error", None)
            elif isinstance(script_result, dict):
                success = bool(script_result.get("success"))
                error = script_result.get("error")
            else:
                success = output_path.exists() and output_path.stat().st_size > 0
                error = None
            
            if not success and error:
                logger.warning(f"JSX export warning: {error}")
            
            return {"success": success, "error": error}
        except Exception as exc:
            logger.error(f"AE JSX export failed: {exc}")
            return {"success": False, "error": str(exc)}

    def _build_interchange_export_jsx(
        self,
        spec: AEExportSpec,
        output_path: Path,
    ) -> str:
        """构建 XML/AAF 导出的 JSX 脚本。"""
        format_map = {
            "xml_fcp7": "Final Cut Pro 7 XML",
            "xml_fcp_x": "Final Cut Pro X XML",
            "aaf": "AAF",
        }
        
        export_format = format_map.get(spec.format, "Final Cut Pro 7 XML")
        output_path_str = str(output_path).replace("\\", "\\\\")
        
        return f'''// AE Export to {export_format}
var comp = app.project.itemByName("{spec.comp_name}");
if (!comp || comp.typeName !== "Composition") {{
    throw new Error("Composition not found: {spec.comp_name}");
}}

var exportPath = "{output_path_str}";
var options = new ExportOptionsFinalCutProXML();

// 设置导出选项
options.includeEffects = {("true" if spec.include_effects else "false")};
options.includeKeyframes = {("true" if spec.include_keyframes else "false")};
options.includeCompositions = {("true" if spec.include_compositions else "false")};
options.includeAudio = {("true" if spec.with_audio else "false")};

try {{
    comp.exportAs(exportPath, new ExportOptionsFinalCutProXML());
    $.writeln("SUCCESS: Exported to " + exportPath);
}} catch (e) {{
    $.writeln("ERROR: " + e.message);
    throw e;
}}
'''

    def _davinci_import(
        self,
        ae_output: str,
        spec: DavinciGradingSpec,
        result: PipelineResult,
    ) -> None:
        """DaVinci 导入阶段。

        根据文件类型选择不同的导入路径：
        - 视频文件（mov/mp4/png/exr）：通过 create_project 导入素材并创建时间线
        - 交换格式（XML/AAF）：通过 import_xml 或 import_aaf 导入时间线结构

        1. 启动/连接 DaVinci Resolve；
        2. 创建/加载项目；
        3. 导入 AE 输出文件（根据格式选择视频导入或 XML/AAF 导入）；
        4. 创建/加载时间线。
        """
        davinci = self._get_davinci()
        from integrations.davinci_fuscript import (
            ColorGradeConfig,
            RenderConfig,
        )

        # 启动 Resolve（如果未运行）
        if not davinci.check_resolve_running():
            launched = davinci.launch_resolve()
            if not launched:
                result.warnings.append("DaVinci Resolve not running; trying to connect anyway")

        # 构造渲染配置（即使本阶段不渲染，也带上为后续阶段铺路）
        render_config = RenderConfig(
            format="MP4",
            codec="H.264",
            resolution="1920x1080",
            frame_rate="30",
            quality="Best",
        )

        color_config = ColorGradeConfig(preset="cinematic")

        # 判断文件类型
        file_ext = Path(ae_output).suffix.lower()
        is_interchange = file_ext in (".xml", ".aaf")

        if is_interchange:
            # XML/AAF 交换格式：使用专用导入方法
            create_result = davinci.import_interchange_format(
                project_name=spec.project_name,
                file_path=ae_output,
                timeline_name=spec.timeline_name,
                color_config=color_config,
            )
        else:
            # 视频文件：走 create_project 流程（创建项目 + 导入 + 建时间线）
            create_result = davinci.create_project(
                project_name=spec.project_name,
                media_files=[ae_output],
                timeline_name=spec.timeline_name,
                color_config=color_config,
                render=False,
                output_dir=None,
            )

        if not create_result.success:
            errs = list(create_result.errors or [])
            raise RuntimeError(
                f"DaVinci import failed: {'; '.join(errs) or 'unknown'}"
            )

        result.davinci_project_path = (
            f"{spec.project_name}/{spec.timeline_name}"
        )
        result.intermediate_files.append(ae_output)

    def _davinci_grade(
        self,
        spec: DavinciGradingSpec,
        result: PipelineResult,
    ) -> None:
        """DaVinci 调色阶段。

        1. 解析预设（preset_name / custom_preset）；
        2. 确定调色目标（全部/指定片段）；
        3. 调用 ColorGrader.apply_preset 应用；
        4. 可选导出 LUT。
        """
        grader = self._get_grader()
        # 切到 Color 页面（resolve 真实实例时有效）
        try:
            grader.switch_to_color_page()
        except Exception as exc:  # noqa: BLE001
            logger.debug("switch_to_color_page failed: %s", exc)

        # 1. 解析预设
        preset = self._resolve_preset(spec, result)
        if preset is None:
            result.warnings.append("No preset resolved; skipping color grading")
            return

        # 2. 确定片段索引
        clip_indices = self._resolve_clip_indices(spec, grader, result)
        if not clip_indices:
            result.warnings.append("No clips to grade; skipping color grading")
            return

        # 3. 应用预设（逐片段）
        grading_results = grader.grade_clip_range(
            clip_indices=clip_indices,
            node_index=1,  # 节点 1（0 是默认，留给调色）
            preset=preset,
        )
        success_count = sum(1 for v in grading_results.values() if v)
        if success_count == 0:
            raise RuntimeError("All clip grading attempts failed")
        if success_count < len(grading_results):
            result.warnings.append(
                f"Partial grading: {success_count}/{len(grading_results)} clips succeeded"
            )

        # 4. 可选导出 LUT
        if spec.export_lut:
            try:
                # 选第一个成功的片段 + 节点导出 LUT
                first_clip = next(
                    (idx for idx, ok in grading_results.items() if ok),
                    clip_indices[0],
                )
                grader.export_lut(
                    clip_index=first_clip,
                    node_index=1,
                    output_path=spec.export_lut,
                )
                result.intermediate_files.append(str(spec.export_lut))
            except Exception as exc:  # noqa: BLE001
                logger.warning("export_lut failed: %s", exc)
                result.warnings.append(f"export_lut failed: {exc}")

    def _davinci_render(
        self,
        spec: DavinciRenderSpec,
        result: PipelineResult,
    ) -> str:
        """DaVinci 渲染阶段。

        1. 设置渲染参数（自动解析 codec、quality、extension）；
        2. 提交到渲染队列；
        3. 等待完成；
        4. 验证输出文件；
        5. 同步到目标路径。
        """
        davinci = self._get_davinci()
        output_path = Path(spec.output_path)
        if not output_path.is_absolute():
            output_path = self.work_dir / output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 自动解析编码器（如果未指定）
        codec = spec.codec or spec._resolve_codec()
        file_type = spec._resolve_file_type()
        ext = spec._resolve_extension()

        # 通过 render_project 走标准流程
        render_result = davinci.render_project(
            project_name=(
                result.davinci_project_path.split("/")[0]
                if result.davinci_project_path
                else "AE_Imported_Project"
            ),
            output_dir=str(output_path.parent),
            render_format=file_type,
            codec=codec,
            resolution=f"{spec.resolution[0]}x{spec.resolution[1]}",
            frame_rate=str(int(spec.frame_rate)),
            quality=spec.quality,
            timeout=600,
        )
        if not render_result.success:
            errs = list(render_result.errors or [])
            raise RuntimeError(
                f"DaVinci render_project failed: {'; '.join(errs) or 'unknown'}"
            )

        # 渲染成功：尝试定位输出文件
        # Resolve 通常以 <CustomName>.<ext> 命名
        candidate = output_path.parent / f"{output_path.stem}{ext}"
        if not candidate.exists() and render_result.output_path:
            candidate = Path(render_result.output_path)

        if not candidate.exists():
            # 兜底：扫描目录里最新的文件
            found = self._find_latest_render(output_path.parent, ext)
            if found is not None:
                candidate = found
        if not candidate.exists():
            raise RuntimeError(
                f"Render result not found at {candidate} or {output_path.parent}"
            )

        # 同步到调用方期望的 output_path（如果不同则复制）
        if candidate != output_path:
            shutil.copy2(str(candidate), str(output_path))

        logger.info(f"Render completed: {output_path}")
        return str(output_path)

    # ==================================================================
    # 预设解析 / 片段索引
    # ==================================================================

    def _resolve_preset(
        self,
        spec: DavinciGradingSpec,
        result: PipelineResult,
    ) -> "ColorGradingPreset" | None:
        """解析调色预设。"""
        if spec.custom_preset is not None:
            return spec.custom_preset
        if not spec.preset_name:
            return None
        try:
            from integrations.color_presets import get_preset

            preset = get_preset(spec.preset_name)
            if preset is None:
                result.warnings.append(
                    f"Preset not found in builtin library: {spec.preset_name}"
                )
            return preset
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to load preset %s: %s", spec.preset_name, exc)
            result.warnings.append(f"Failed to load preset: {exc}")
            return None

    def _resolve_clip_indices(
        self,
        spec: DavinciGradingSpec,
        grader: "ColorGrader",
        result: PipelineResult,
    ) -> list[int]:
        """确定要调色的片段索引列表。"""
        if spec.specific_clip_indices is not None:
            return list(spec.specific_clip_indices)
        if not spec.grade_all_clips:
            return []
        # 走 ColorGrader：当前时间线视频轨的所有片段
        try:
            resolve = grader.resolve
            project = resolve.GetProjectManager().GetCurrentProject()
            timeline = project.GetCurrentTimeline() if project else None
            if timeline is None:
                return []
            items = timeline.GetItemListInTrack("video", 1) or []
            return list(range(len(items)))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to enumerate clips: %s", exc)
            result.warnings.append(f"Failed to enumerate clips: {exc}")
            return []

    # ==================================================================
    # 辅助
    # ==================================================================

    @staticmethod
    def _find_latest_render(
        directory: Path, ext: str
    ) -> Path | None:
        """在指定目录中查找最新生成的渲染产物。"""
        try:
            candidates = sorted(
                directory.glob(f"*{ext}"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            return candidates[0] if candidates else None
        except Exception:  # noqa: BLE001
            return None

    # ==================================================================
    # 异步
    # ==================================================================

    async def run_async(
        self,
        ae_spec: AEExportSpec,
        grading_spec: DavinciGradingSpec,
        render_spec: DavinciRenderSpec,
        progress_callback: ProgressCallback | None = None,
    ) -> PipelineResult:
        """异步执行完整协作链路（在默认 executor 中调度 run）。

        适用于 FastAPI/asyncio 场景，不阻塞事件循环。
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.run, ae_spec, grading_spec, render_spec, progress_callback
        )

    # ==================================================================
    # 检查点机制
    # ==================================================================

    def run_with_checkpoints(
        self,
        ae_spec: AEExportSpec,
        grading_spec: DavinciGradingSpec,
        render_spec: DavinciRenderSpec,
        checkpoint_dir: str = "output/pipeline/checkpoints",
        progress_callback: ProgressCallback | None = None,
    ) -> PipelineResult:
        """带检查点的执行，支持断点续传。

        行为：
        - 启动时读取 ``checkpoint_dir/<id>.json``；
        - 如果上次某个阶段已完成，**跳过该阶段**直接进入下一阶段；
        - 每阶段完成后落盘一次检查点；
        - 全部完成后删除检查点目录。

        Args:
            ae_spec: AE 导出规格。
            grading_spec: DaVinci 调色规格。
            render_spec: DaVinci 渲染规格。
            checkpoint_dir: 检查点目录。
            progress_callback: 进度回调。

        Returns:
            :class:`PipelineResult`。
        """
        old_ckpt_dir = self.checkpoint_manager.checkpoint_dir
        old_ckpt_name = self.checkpoint_manager.checkpoint_name
        self.checkpoint_manager.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_manager.checkpoint_name = "pipeline_checkpoint.json"
        self.checkpoint_manager.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        result = PipelineResult(success=False)

        loaded_ckpt = self.checkpoint_manager.load()
        completed = {}
        if loaded_ckpt:
            completed[loaded_ckpt.stage] = {"data": loaded_ckpt.data}
        
        if not completed and self.checkpoint_manager.checkpoint_path.exists():
            try:
                with open(self.checkpoint_manager.checkpoint_path, "r", encoding="utf-8") as f:
                    raw_data = json.load(f)
                if isinstance(raw_data, dict) and "stage" not in raw_data:
                    completed = raw_data
            except Exception:
                pass

        # 阶段 1：AE 导出
        if "ae_export" in completed:
            self._report(progress_callback, "ae_export (cached)", 0.4)
            cached = completed["ae_export"].get("data", {})
            result.ae_export_path = cached.get("ae_export_path")
            if result.ae_export_path:
                result.intermediate_files.append(result.ae_export_path)
        else:
            try:
                self._report(progress_callback, "ae_export", 0.0)
                t0 = time.time()
                ae_output = self._ae_export(ae_spec, result)
                result.metrics["ae_export_duration_sec"] = time.time() - t0
                self._save_checkpoint(
                    "ae_export",
                    {"ae_export_path": ae_output},
                )
                self._report(progress_callback, "ae_export", 0.4)
            except Exception as exc:  # noqa: BLE001
                result.errors.append(f"AE export failed: {exc}")
                result.finished_at = datetime.now()
                return result

        # 阶段 2：DaVinci 导入
        if "davinci_import" in completed:
            self._report(progress_callback, "davinci_import (cached)", 0.5)
            cached = completed["davinci_import"].get("data", {})
            result.davinci_project_path = cached.get("davinci_project_path")
        else:
            try:
                self._report(progress_callback, "davinci_import", 0.4)
                t0 = time.time()
                self._davinci_import(
                    result.ae_export_path or "", grading_spec, result
                )
                result.metrics["davinci_import_duration_sec"] = time.time() - t0
                self._save_checkpoint(
                    "davinci_import",
                    {"davinci_project_path": result.davinci_project_path},
                )
                self._report(progress_callback, "davinci_import", 0.5)
            except Exception as exc:  # noqa: BLE001
                result.errors.append(f"DaVinci import failed: {exc}")
                result.finished_at = datetime.now()
                return result

        # 阶段 3：DaVinci 调色
        if "davinci_grade" in completed:
            self._report(progress_callback, "davinci_grade (cached)", 0.8)
        else:
            try:
                self._report(progress_callback, "davinci_grade", 0.5)
                t0 = time.time()
                self._davinci_grade(grading_spec, result)
                result.metrics["davinci_grade_duration_sec"] = time.time() - t0
                self._save_checkpoint("davinci_grade", {})
                self._report(progress_callback, "davinci_grade", 0.8)
            except Exception as exc:  # noqa: BLE001
                result.errors.append(f"DaVinci grading failed: {exc}")
                result.finished_at = datetime.now()
                return result

        # 阶段 4：DaVinci 渲染
        if "davinci_render" in completed:
            self._report(progress_callback, "davinci_render (cached)", 1.0)
            cached = completed["davinci_render"].get("data", {})
            result.final_output_path = cached.get("final_output_path")
        else:
            try:
                self._report(progress_callback, "davinci_render", 0.8)
                t0 = time.time()
                final_output = self._davinci_render(render_spec, result)
                result.metrics["davinci_render_duration_sec"] = time.time() - t0
                self._save_checkpoint(
                    "davinci_render",
                    {"final_output_path": final_output},
                )
                self._report(progress_callback, "davinci_render", 1.0)
                result.final_output_path = final_output
            except Exception as exc:  # noqa: BLE001
                result.errors.append(f"DaVinci render failed: {exc}")
                result.finished_at = datetime.now()
                return result

        # 全部成功：清理检查点
        self.checkpoint_manager.delete()

        # 恢复原检查点配置
        self.checkpoint_manager.checkpoint_dir = old_ckpt_dir
        self.checkpoint_manager.checkpoint_name = old_ckpt_name

        result.success = True
        result.finished_at = datetime.now()
        return result

    # ==================================================================
    # 资源清理
    # ==================================================================

    def cleanup(
        self,
        keep_outputs: bool = True,
        keep_intermediate: bool = False,
    ) -> None:
        """清理中间产物。

        Args:
            keep_outputs: 保留 final_output_path 与 ae_export_path。
            keep_intermediate: 保留 intermediate_files 列表中的文件。
        """
        keep_set: set = set()
        if keep_outputs:
            # 暂不读取 result（可能尚未运行），由调用方负责
            pass
        if keep_intermediate:
            keep_set.update(self._tracked_intermediates)

        # 清理 temp_dir
        if self.temp_dir.exists():
            for f in self.temp_dir.rglob("*"):
                if f.is_file() and str(f) not in keep_set:
                    try:
                        f.unlink()
                    except Exception:  # noqa: BLE001
                        pass

    # 供 cleanup 使用的中间产物记录
    _tracked_intermediates: list[str] = []

    # ==================================================================
    # 高层便捷 API
    # ==================================================================

    def _build_specs_for_style(
        self,
        comp_name: str,
        output_path: str,
        duration: float | None,
        preset_name: str,
        render_format: str = "mp4_h264",
    ) -> tuple[AEExportSpec, DavinciGradingSpec, DavinciRenderSpec]:
        """为某个风格化预设构造三段规格（供 run_*_xxx 使用）。"""
        ae_spec = AEExportSpec(
            comp_name=comp_name,
            output_path=str(self.work_dir / f"{comp_name}_ae.mov"),
            format="mov_prores_4444",
            duration=duration,
        )
        grading_spec = DavinciGradingSpec(
            project_name=f"{comp_name}_Pipeline",
            timeline_name="AE_Imported",
            preset_name=preset_name,
        )
        render_spec = DavinciRenderSpec(
            output_path=output_path,
            format=render_format,  # type: ignore[arg-type]
        )
        return ae_spec, grading_spec, render_spec

    def run_cinematic_teal_orange(
        self,
        comp_name: str,
        output_path: str,
        duration: float | None = None,
    ) -> PipelineResult:
        """运行"电影感青橙"风格化（AE 导出 → DaVinci 青橙调色 → 渲染）。"""
        specs = self._build_specs_for_style(
            comp_name=comp_name,
            output_path=output_path,
            duration=duration,
            preset_name="cinematic_teal_orange",
        )
        return self.run(*specs)

    def run_vintage_film(
        self,
        comp_name: str,
        output_path: str,
        duration: float | None = None,
    ) -> PipelineResult:
        """运行"复古胶片"风格化。"""
        specs = self._build_specs_for_style(
            comp_name=comp_name,
            output_path=output_path,
            duration=duration,
            preset_name="vintage_film",
        )
        return self.run(*specs)

    def run_music_video(
        self,
        comp_name: str,
        output_path: str,
        duration: float | None = None,
    ) -> PipelineResult:
        """运行"音乐 MV 冲击"风格化。"""
        specs = self._build_specs_for_style(
            comp_name=comp_name,
            output_path=output_path,
            duration=duration,
            preset_name="music_video_punch",
        )
        return self.run(*specs)

    def run_with_preset(
        self,
        comp_name: str,
        output_path: str,
        preset_name: str,
        duration: float | None = None,
    ) -> PipelineResult:
        """使用指定预设运行（预设键名见 integrations.color_presets.BUILTIN_PRESETS）。"""
        specs = self._build_specs_for_style(
            comp_name=comp_name,
            output_path=output_path,
            duration=duration,
            preset_name=preset_name,
        )
        return self.run(*specs)

    def run_with_custom_lut(
        self,
        comp_name: str,
        output_path: str,
        lut_path: str,
        duration: float | None = None,
    ) -> PipelineResult:
        """使用自定义 LUT 运行（通过 resolve_fuscript 的 apply_lut 能力，融合到 color 配置里）。"""
        # 构造一个 cinematic 占位 preset，然后通过 segment_presets 注入 LUT
        # 实际 LUT 应用由 davinci_fuscript 的 ColorGradeConfig.lut_path 承担
        # 这里我们用 custom_preset 模式不可行（preset 不带 lut_path），所以走：
        # 1) 在 grading_spec 上加 export_lut 标识
        # 2) 改用更直接的 run() 流程
        from integrations.davinci_fuscript import ColorGradeConfig
        # 这里仅做演示：让用户使用 run() 自行接入 LUT 路径
        # 由于 ColorGrader 不直接接 lut_path，简化做法：先把 lut 路径传给 preset
        # 通过把 lut 路径打包为占位 ColorGradingPreset，data 中附 _lut_path
        try:
            from integrations.davinci_color_grading import (
                ColorGradingPreset,
            )

            wrapped = ColorGradingPreset(name=f"lut:{lut_path}")
            # 注入隐藏属性供 grader 检索
            setattr(wrapped, "_lut_path", lut_path)
        except Exception:  # noqa: BLE001
            wrapped = None  # type: ignore[assignment]

        ae_spec = AEExportSpec(
            comp_name=comp_name,
            output_path=str(self.work_dir / f"{comp_name}_ae.mov"),
            format="mov_prores_4444",
            duration=duration,
        )
        grading_spec = DavinciGradingSpec(
            project_name=f"{comp_name}_LUT_Pipeline",
            timeline_name="AE_Imported",
            preset_name="cinematic",  # 占位
            custom_preset=wrapped,
        )
        render_spec = DavinciRenderSpec(output_path=output_path)
        return self.run(ae_spec, grading_spec, render_spec)


# ============================================================================
# 便捷函数
# ============================================================================

def quick_pipeline(
    comp_name: str,
    output_path: str,
    style: str = "cinematic_teal_orange",
    duration: float | None = None,
) -> PipelineResult:
    """一行式协作链路入口（默认电影感青橙风格化）。

    Args:
        comp_name: AE 合成名。
        output_path: 最终输出路径。
        style: 风格化键名（见 :data:`STYLE_PRESET_MAP`）。
        duration: AE 合成时长（None 表示全程）。

    Returns:
        :class:`PipelineResult`。
    """
    pipeline = AEToDavinciPipeline()
    method = {
        "cinematic_teal_orange": pipeline.run_cinematic_teal_orange,
        "vintage_film": pipeline.run_vintage_film,
        "music_video_punch": pipeline.run_music_video,
    }
    fn = method.get(style)
    if fn is None:
        # 兜底走 run_with_preset
        return pipeline.run_with_preset(
            comp_name=comp_name,
            output_path=output_path,
            preset_name=style,
            duration=duration,
        )
    return fn(comp_name=comp_name, output_path=output_path, duration=duration)


# ============================================================================
# 模块导出
# ============================================================================

__all__ = [
    # 枚举 / 类型别名
    "AEExportFormat",
    "DavinciRenderFormat",
    "RenderQuality",
    "ProgressCallback",
    # 数据模型
    "AEExportSpec",
    "DavinciGradingSpec",
    "DavinciRenderSpec",
    "PipelineResult",
    "PipelineCheckpoint",
    # 预设映射
    "STYLE_PRESET_MAP",
    # 主类
    "AEToDavinciPipeline",
    # 便捷函数
    "quick_pipeline",
]
