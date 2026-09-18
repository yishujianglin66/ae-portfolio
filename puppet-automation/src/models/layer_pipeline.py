"""分层渲染管线数据模型 - Layer Render Pipeline Data Models.

定义六层标准渲染管线的数据结构、配置和预设模板。
六层标准定义（从下到上）：
    1. Background（背景）: 渲染器可选 AE/Blender/FFmpeg
    2. Subject（主体）: 抠像后的主体，带Alpha
    3. Midground（中间层）: 前后景之间的元素
    4. Particles（粒子）: AE粒子系统，叠加模式
    5. Light（光效）: 光斑/镜头光晕，加色混合
    6. Adjustment（调整层）: 调色/全局效果/LUT
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

# ============================================================
# Enums
# ============================================================

class LayerType(str, Enum):
    """图层类型枚举."""
    BACKGROUND = "background"
    SUBJECT = "subject"
    MIDGROUND = "midground"
    PARTICLES = "particles"
    LIGHT = "light"
    ADJUSTMENT = "adjustment"


class RendererType(str, Enum):
    """渲染器类型枚举."""
    AE = "ae"
    BLENDER = "blender"
    FFMPEG = "ffmpeg"


class BlendMode(str, Enum):
    """图层混合模式枚举."""
    NORMAL = "normal"
    ADD = "add"
    SCREEN = "screen"
    MULTIPLY = "multiply"
    OVERLAY = "overlay"
    SOFT_LIGHT = "soft_light"
    HARD_LIGHT = "hard_light"
    COLOR_DODGE = "color_dodge"
    COLOR_BURN = "color_burn"
    DARKEN = "darken"
    LIGHTEN = "lighten"
    DIFFERENCE = "difference"
    EXCLUSION = "exclusion"


class OutputFormat(str, Enum):
    """输出格式枚举."""
    PNG_SEQUENCE = "png_sequence"
    EXR_SEQUENCE = "exr_sequence"
    PRORES_4444 = "prores_4444"
    PRORES_422 = "prores_422"
    H264 = "h264"
    H265 = "h265"


class PipelinePreset(str, Enum):
    """预设管线模板枚举."""
    CINEMATIC_VLOG = "cinematic_vlog"
    MUSIC_VIDEO = "music_video"
    TITLE_SEQUENCE = "title_sequence"


# ============================================================
# Core Data Models
# ============================================================

class LayerConfig(BaseModel):
    """单层渲染配置.

    Attributes:
        name: 图层名称
        type: 图层类型（六层标准之一）
        renderer: 使用的渲染器（AE/Blender/FFmpeg）
        z_index: Z轴层级索引（数值越大越靠上）
        visible: 是否可见
        opacity: 不透明度（0-100）
        blend_mode: 混合模式
        params: 渲染参数字典（渲染器特定）
        source_path: 源素材路径（可选）
        output_path: 输出路径（可选，自动生成时填充）
        cache_key: 缓存键（用于缓存检查）
    """
    name: str
    type: LayerType
    renderer: RendererType
    z_index: int = 0
    visible: bool = True
    opacity: float = 100.0
    blend_mode: BlendMode = BlendMode.NORMAL
    params: dict[str, Any] = Field(default_factory=dict)
    source_path: str | None = None
    output_path: str | None = None
    cache_key: str | None = None


class RenderPipeline(BaseModel):
    """渲染管线配置.

    Attributes:
        name: 管线名称
        layers: 图层配置列表（按 z_index 排序）
        output_format: 最终输出格式
        output_resolution: 输出分辨率 (width, height)
        output_fps: 输出帧率
        duration: 总时长（秒）
        cache_enabled: 是否启用缓存
        cache_dir: 缓存目录路径
        work_dir: 工作目录路径
        composite_renderer: 最终合成使用的渲染器
        preset: 预设模板（可选）
    """
    name: str = "default_pipeline"
    layers: list[LayerConfig] = Field(default_factory=list)
    output_format: OutputFormat = OutputFormat.PNG_SEQUENCE
    output_resolution: tuple[int, int] = (1920, 1080)
    output_fps: float = 30.0
    duration: float = 10.0
    cache_enabled: bool = True
    cache_dir: str | None = None
    work_dir: str | None = None
    composite_renderer: RendererType = RendererType.FFMPEG
    preset: PipelinePreset | None = None

    def get_sorted_layers(self) -> list[LayerConfig]:
        """获取按 z_index 排序的图层列表（从下到上）.

        Returns:
            排序后的图层配置列表
        """
        return sorted(self.layers, key=lambda layer: layer.z_index)

    def get_visible_layers(self) -> list[LayerConfig]:
        """获取可见的图层列表（按 z_index 排序）.

        Returns:
            可见图层配置列表
        """
        return [layer for layer in self.get_sorted_layers() if layer.visible]


class LayerRenderResult(BaseModel):
    """单层渲染结果.

    Attributes:
        layer_name: 图层名称
        success: 是否成功
        output_path: 输出文件路径
        duration_seconds: 渲染耗时（秒）
        file_size_bytes: 文件大小（字节）
        frame_count: 帧数
        cache_hit: 是否命中缓存
        metadata: 附加元数据
        error: 错误信息（失败时）
    """
    layer_name: str
    success: bool = True
    output_path: str | None = None
    duration_seconds: float = 0.0
    file_size_bytes: int = 0
    frame_count: int = 0
    cache_hit: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class PipelineRenderResult(BaseModel):
    """完整管线渲染结果.

    Attributes:
        pipeline_name: 管线名称
        success: 是否成功
        output_path: 最终输出路径
        total_duration_seconds: 总耗时（秒）
        layer_results: 各图层渲染结果字典
        cache_hits: 缓存命中层数
        cache_misses: 缓存未命中层数
        metadata: 附加元数据
        error: 错误信息（失败时）
    """
    pipeline_name: str
    success: bool = True
    output_path: str | None = None
    total_duration_seconds: float = 0.0
    layer_results: dict[str, LayerRenderResult] = Field(default_factory=dict)
    cache_hits: int = 0
    cache_misses: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class LayerStats(BaseModel):
    """图层统计信息.

    Attributes:
        layer_name: 图层名称
        layer_type: 图层类型
        renderer: 使用的渲染器
        z_index: Z轴层级
        file_size_bytes: 文件大小（字节）
        render_duration_seconds: 渲染耗时（秒）
        frame_count: 帧数
        cache_hit: 是否命中缓存
        visible: 是否可见
    """
    layer_name: str
    layer_type: LayerType
    renderer: RendererType
    z_index: int
    file_size_bytes: int = 0
    render_duration_seconds: float = 0.0
    frame_count: int = 0
    cache_hit: bool = False
    visible: bool = True


# ============================================================
# Preset Templates
# ============================================================

def get_preset_pipeline(preset: PipelinePreset) -> RenderPipeline:
    """获取预设的渲染管线配置.

    Args:
        preset: 预设类型

    Returns:
        预设的 RenderPipeline 配置
    """
    presets = {
        PipelinePreset.CINEMATIC_VLOG: _build_cinematic_vlog_preset(),
        PipelinePreset.MUSIC_VIDEO: _build_music_video_preset(),
        PipelinePreset.TITLE_SEQUENCE: _build_title_sequence_preset(),
    }
    return presets.get(preset, _build_cinematic_vlog_preset())


def _build_cinematic_vlog_preset() -> RenderPipeline:
    """构建电影感 Vlog 预设管线.

    配置特点：
    - 背景：Blender 3D 环境
    - 主体：抠像人物（带 Alpha）
    - 中间层：前景装饰元素
    - 粒子：尘埃粒子（ADD 模式）
    - 光效：镜头光晕 + 漏光
    - 调整层：电影级调色 + LUT + 暗角
    """
    return RenderPipeline(
        name="cinematic_vlog",
        preset=PipelinePreset.CINEMATIC_VLOG,
        output_format=OutputFormat.PRORES_4444,
        output_resolution=(1920, 1080),
        output_fps=30.0,
        duration=10.0,
        cache_enabled=True,
        composite_renderer=RendererType.FFMPEG,
        layers=[
            LayerConfig(
                name="Background_3D",
                type=LayerType.BACKGROUND,
                renderer=RendererType.BLENDER,
                z_index=0,
                visible=True,
                opacity=100.0,
                blend_mode=BlendMode.NORMAL,
                params={
                    "scene_style": "cinematic",
                    "render_engine": "CYCLES",
                    "samples": 128,
                    "motion_blur": True,
                    "depth_of_field": True,
                },
            ),
            LayerConfig(
                name="Subject_Keyed",
                type=LayerType.SUBJECT,
                renderer=RendererType.AE,
                z_index=10,
                visible=True,
                opacity=100.0,
                blend_mode=BlendMode.NORMAL,
                params={
                    "keying_method": "keylight",
                    "screen_color": "#00FF00",
                    "edge_refinement": True,
                    "color_correction": True,
                },
            ),
            LayerConfig(
                name="Midground_ForegroundElements",
                type=LayerType.MIDGROUND,
                renderer=RendererType.AE,
                z_index=20,
                visible=True,
                opacity=100.0,
                blend_mode=BlendMode.NORMAL,
                params={
                    "elements": ["lens_dust", "film_grain"],
                },
            ),
            LayerConfig(
                name="Particles_Dust",
                type=LayerType.PARTICLES,
                renderer=RendererType.AE,
                z_index=30,
                visible=True,
                opacity=60.0,
                blend_mode=BlendMode.ADD,
                params={
                    "particle_type": "dust",
                    "particle_count": 200,
                    "speed": 0.5,
                    "size_range": [1, 5],
                },
            ),
            LayerConfig(
                name="Light_LensFlare",
                type=LayerType.LIGHT,
                renderer=RendererType.AE,
                z_index=40,
                visible=True,
                opacity=80.0,
                blend_mode=BlendMode.SCREEN,
                params={
                    "flare_type": "anamorphic",
                    "intensity": 0.8,
                    "animated": True,
                    "light_leak": True,
                },
            ),
            LayerConfig(
                name="Adjustment_FinalGrade",
                type=LayerType.ADJUSTMENT,
                renderer=RendererType.AE,
                z_index=50,
                visible=True,
                opacity=100.0,
                blend_mode=BlendMode.NORMAL,
                params={
                    "lut": "cinematic_teal_orange",
                    "contrast": 1.1,
                    "saturation": 0.9,
                    "vignette": 0.3,
                    "film_grain": 0.05,
                },
            ),
        ],
    )


def _build_music_video_preset() -> RenderPipeline:
    """构建音乐视频预设管线.

    配置特点：
    - 背景：动态视觉效果（AE 合成）
    - 主体：多机位抠像主体
    - 中间层：波形/频谱可视化
    - 粒子：高能粒子系统
    - 光效：节奏同步光效
    - 调整层：高对比度调色 + 故障效果
    """
    return RenderPipeline(
        name="music_video",
        preset=PipelinePreset.MUSIC_VIDEO,
        output_format=OutputFormat.H264,
        output_resolution=(1920, 1080),
        output_fps=30.0,
        duration=10.0,
        cache_enabled=True,
        composite_renderer=RendererType.AE,
        layers=[
            LayerConfig(
                name="Background_Visuals",
                type=LayerType.BACKGROUND,
                renderer=RendererType.AE,
                z_index=0,
                visible=True,
                opacity=100.0,
                blend_mode=BlendMode.NORMAL,
                params={
                    "visual_type": "audio_reactive",
                    "color_scheme": "neon",
                    "beat_sync": True,
                },
            ),
            LayerConfig(
                name="Subject_Performer",
                type=LayerType.SUBJECT,
                renderer=RendererType.AE,
                z_index=10,
                visible=True,
                opacity=100.0,
                blend_mode=BlendMode.NORMAL,
                params={
                    "keying_method": "primatte",
                    "multi_angle": True,
                    "glow_effect": True,
                },
            ),
            LayerConfig(
                name="Midground_Spectrum",
                type=LayerType.MIDGROUND,
                renderer=RendererType.AE,
                z_index=20,
                visible=True,
                opacity=70.0,
                blend_mode=BlendMode.SCREEN,
                params={
                    "spectrum_style": "bars",
                    "audio_bands": 64,
                    "animation_speed": 1.0,
                },
            ),
            LayerConfig(
                name="Particles_HighEnergy",
                type=LayerType.PARTICLES,
                renderer=RendererType.AE,
                z_index=30,
                visible=True,
                opacity=100.0,
                blend_mode=BlendMode.ADD,
                params={
                    "particle_type": "trapezoid",
                    "particle_count": 500,
                    "beat_emission": True,
                    "speed": 3.0,
                },
            ),
            LayerConfig(
                name="Light_BeatSync",
                type=LayerType.LIGHT,
                renderer=RendererType.AE,
                z_index=40,
                visible=True,
                opacity=90.0,
                blend_mode=BlendMode.ADD,
                params={
                    "light_type": "strobe",
                    "beat_sync": True,
                    "color_pulse": True,
                    "intensity": 1.2,
                },
            ),
            LayerConfig(
                name="Adjustment_Stylize",
                type=LayerType.ADJUSTMENT,
                renderer=RendererType.AE,
                z_index=50,
                visible=True,
                opacity=100.0,
                blend_mode=BlendMode.NORMAL,
                params={
                    "contrast": 1.3,
                    "saturation": 1.2,
                    "glitch_effect": True,
                    "chromatic_aberration": 0.02,
                    "scan_lines": 0.1,
                },
            ),
        ],
    )


def _build_title_sequence_preset() -> RenderPipeline:
    """构建标题序列预设管线.

    配置特点：
    - 背景：渐变/粒子背景
    - 主体：3D 标题文字
    - 中间层：装饰性图形元素
    - 粒子：文字粒子消散效果
    - 光效：文字发光 + 镜头光晕
    - 调整层：最终调色 + 景深
    """
    return RenderPipeline(
        name="title_sequence",
        preset=PipelinePreset.TITLE_SEQUENCE,
        output_format=OutputFormat.PRORES_4444,
        output_resolution=(1920, 1080),
        output_fps=30.0,
        duration=5.0,
        cache_enabled=True,
        composite_renderer=RendererType.AE,
        layers=[
            LayerConfig(
                name="Background_Gradient",
                type=LayerType.BACKGROUND,
                renderer=RendererType.AE,
                z_index=0,
                visible=True,
                opacity=100.0,
                blend_mode=BlendMode.NORMAL,
                params={
                    "gradient_type": "radial",
                    "colors": ["#1a1a2e", "#16213e", "#0f3460"],
                    "animated": True,
                },
            ),
            LayerConfig(
                name="Subject_3DTitle",
                type=LayerType.SUBJECT,
                renderer=RendererType.AE,
                z_index=10,
                visible=True,
                opacity=100.0,
                blend_mode=BlendMode.NORMAL,
                params={
                    "title_text": "TITLE",
                    "font_style": "epic",
                    "extrusion_depth": 50,
                    "bevel_style": "round",
                    "material": "metallic",
                },
            ),
            LayerConfig(
                name="Midground_Decorations",
                type=LayerType.MIDGROUND,
                renderer=RendererType.AE,
                z_index=20,
                visible=True,
                opacity=80.0,
                blend_mode=BlendMode.NORMAL,
                params={
                    "elements": ["lines", "shapes", "brackets"],
                    "animation_style": "reveal",
                },
            ),
            LayerConfig(
                name="Particles_TitleDust",
                type=LayerType.PARTICLES,
                renderer=RendererType.AE,
                z_index=30,
                visible=True,
                opacity=70.0,
                blend_mode=BlendMode.ADD,
                params={
                    "particle_type": "sparkle",
                    "emitter": "text_outline",
                    "particle_count": 300,
                    "dissolve_effect": True,
                },
            ),
            LayerConfig(
                name="Light_TextGlow",
                type=LayerType.LIGHT,
                renderer=RendererType.AE,
                z_index=40,
                visible=True,
                opacity=100.0,
                blend_mode=BlendMode.SCREEN,
                params={
                    "glow_type": "outer_glow",
                    "glow_color": "#00FFFF",
                    "glow_size": 30,
                    "lens_flare": True,
                    "flare_position": "top_left",
                },
            ),
            LayerConfig(
                name="Adjustment_Final",
                type=LayerType.ADJUSTMENT,
                renderer=RendererType.AE,
                z_index=50,
                visible=True,
                opacity=100.0,
                blend_mode=BlendMode.NORMAL,
                params={
                    "lut": "cinematic",
                    "bloom": 0.2,
                    "depth_of_field": 0.1,
                    "lens_distortion": 0.05,
                },
            ),
        ],
    )
