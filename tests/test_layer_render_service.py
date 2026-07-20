"""
test_layer_render_service.py - LayerRenderService 单元测试
====================================================

测试重点：
1. __init__ 初始化与可选引擎实例
2. render_pipeline 管线渲染（不可见图层跳过、缓存命中/未命中、图层失败短路、无可见图层）
3. render_layer 单层渲染（缓存检查、渲染器分发 AE/Blender/FFmpeg）
4. composite_layers 多层合成（0 层、1 层复制、多层 FFmpeg/AE）
5. check_cache 缓存校验（有效清单、缺少清单、空目录、无效清单）
6. build_from_preset 三种预设构建
7. list_presets 列出预设
8. _generate_cache_key 确定性与唯一性
9. _hex_to_rgb_tuple HEX 颜色转换
10. _get_ffmpeg_codec_params 编码参数映射
11. _get_ae_output_module AE 输出模块映射
12. _calculate_dir_size 目录大小计算
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── 路径设置 ──────────────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(PROJECT_ROOT, "puppet-automation", "src")
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, SRC_DIR)

# layer_render_service.py 使用了相对导入（from ..config / from ..engines.xxx），
# 直接从项目根目录的 tests/ 运行会触发 "attempted relative import beyond top-level package"。
# 解决方案：在 sys.modules 中预先注册所有需要的包和模块，
# 然后通过 importlib 正常导入，让相对导入链能被正确解析。
import importlib

# 1. 注册 src 自身为包
_src_init = type(sys)("src")
_src_init.__path__ = [SRC_DIR]
_src_init.__package__ = "src"
sys.modules["src"] = _src_init

# 2. 注册子包（config / engines / models / services）
for _pkg in ("config", "engines", "models", "services",
             "engines.ae", "engines.blender", "engines.ffmpeg"):
    _mod = type(sys)(f"src.{_pkg}")
    _mod.__path__ = [os.path.join(SRC_DIR, *_pkg.split("."))]
    _mod.__package__ = f"src.{_pkg}"
    sys.modules[f"src.{_pkg}"] = _mod

# 3. 预注册 config.settings 和 engines.base（它们可独立加载）
from config.settings import Settings, get_settings, settings  # noqa: E402
sys.modules["src.config.settings"] = sys.modules["config.settings"]
# 把 src.config.settings 挂到已注册的 src.config 上
_src_config = sys.modules["src.config"]
_src_config.settings = settings
_src_config.Settings = Settings
_src_config.get_settings = get_settings

from engines.base import EngineResult  # noqa: E402
sys.modules["src.engines.base"] = sys.modules["engines.base"]

# 4. 预注册 models.layer_pipeline
from models.layer_pipeline import (  # noqa: E402
    BlendMode,
    LayerConfig,
    LayerRenderResult,
    LayerType,
    OutputFormat,
    PipelinePreset,
    RenderPipeline,
    RendererType,
)
sys.modules["src.models.layer_pipeline"] = sys.modules["models.layer_pipeline"]

# 5. 现在 import src.services.layer_render_service 可以正常解析相对导入
from src.services.layer_render_service import LayerRenderService


# ══════════════════════════════════════════════════════════
# 辅助工具
# ══════════════════════════════════════════════════════════

def _mock_engine() -> MagicMock:
    """创建一个 Mock 引擎实例，常用方法设为 AsyncMock。"""
    engine = MagicMock()
    engine.create_comp = AsyncMock(return_value=EngineResult(success=True))
    engine.render_comp = AsyncMock(return_value=EngineResult(success=True))
    engine.add_layer = AsyncMock()
    engine.add_adjustment_layer = AsyncMock()
    engine.import_footage = AsyncMock()
    engine.create_puppet_stage = AsyncMock(return_value=EngineResult(success=True))
    engine.extract_frames = AsyncMock(return_value=EngineResult(success=True))
    engine.run_script = AsyncMock(return_value=EngineResult(success=True))
    engine.executable_path = Path("/usr/bin/fake")
    engine._run_subprocess = MagicMock(return_value=(0, "", ""))
    return engine


def _make_service(tmp_path: Path | None = None) -> LayerRenderService:
    """创建一个使用 Mock 引擎的 LayerRenderService 实例。"""
    ae = _mock_engine()
    blender = _mock_engine()
    ffmpeg = _mock_engine()
    cache_dir = tmp_path / "cache" if tmp_path else Path("/tmp/test_cache")
    svc = LayerRenderService(
        ae_engine=ae,
        blender_engine=blender,
        ffmpeg_engine=ffmpeg,
        cache_dir=cache_dir,
    )
    return svc


def _make_layer(**overrides) -> LayerConfig:
    """构造 LayerConfig，提供合理默认值。"""
    defaults = dict(
        name="TestLayer",
        type=LayerType.BACKGROUND,
        renderer=RendererType.AE,
        z_index=0,
        visible=True,
        params={"gradient_type": "linear", "colors": ["#1a1a2e", "#0f3460"]},
    )
    defaults.update(overrides)
    return LayerConfig(**defaults)


def _make_pipeline(layers=None, **overrides) -> RenderPipeline:
    """构造 RenderPipeline，提供合理默认值。"""
    if layers is None:
        layers = [_make_layer()]
    defaults = dict(
        name="test_pipeline",
        layers=layers,
        cache_enabled=False,
        output_format=OutputFormat.PNG_SEQUENCE,
    )
    defaults.update(overrides)
    return RenderPipeline(**defaults)


# ══════════════════════════════════════════════════════════
# 1. __init__ 测试
# ══════════════════════════════════════════════════════════

class TestInit:
    """测试 LayerRenderService.__init__"""

    def test_init_with_mock_engines(self, tmp_path):
        """传入 Mock 引擎后，服务应正常初始化且不创建真实引擎。"""
        ae = _mock_engine()
        blender = _mock_engine()
        ffmpeg = _mock_engine()
        svc = LayerRenderService(
            ae_engine=ae,
            blender_engine=blender,
            ffmpeg_engine=ffmpeg,
            cache_dir=tmp_path / "cache",
        )
        assert svc.ae is ae
        assert svc.blender is blender
        assert svc.ffmpeg is ffmpeg
        assert svc.cache_dir == tmp_path / "cache"

    def test_init_creates_cache_dir(self, tmp_path):
        """cache_dir 不存在时，__init__ 应自动创建。"""
        cache_dir = tmp_path / "new_cache"
        assert not cache_dir.exists()
        svc = _make_service(tmp_path)
        # _make_service 用 tmp_path / "cache" 作为 cache_dir
        assert svc.cache_dir.exists()

    def test_init_default_engines_with_mock(self, tmp_path):
        """不传引擎时，默认从 settings 创建（需 mock AEEngine 等构造函数）。"""
        # 直接 patch 已加载的 layer_render_service 模块上的类引用
        import src.services.layer_render_service as _lrs_mod
        with patch.object(_lrs_mod, "AEEngine", return_value=_mock_engine()), \
             patch.object(_lrs_mod, "BlenderEngine", return_value=_mock_engine()), \
             patch.object(_lrs_mod, "FFmpegEngine", return_value=_mock_engine()):
            svc = LayerRenderService(cache_dir=tmp_path / "cache")
            assert svc.ae is not None
            assert svc.blender is not None
            assert svc.ffmpeg is not None


# ══════════════════════════════════════════════════════════
# 2. _generate_cache_key 测试
# ══════════════════════════════════════════════════════════

class TestGenerateCacheKey:
    """测试 LayerRenderService._generate_cache_key"""

    def test_determinism(self):
        """相同 LayerConfig 应生成相同的缓存键。"""
        svc = _make_service()
        cfg = _make_layer()
        key1 = svc._generate_cache_key(cfg)
        key2 = svc._generate_cache_key(cfg)
        assert key1 == key2

    def test_uniqueness(self):
        """不同 LayerConfig 应生成不同的缓存键。"""
        svc = _make_service()
        cfg_a = _make_layer(name="LayerA", params={"color": "#ff0000"})
        cfg_b = _make_layer(name="LayerB", params={"color": "#00ff00"})
        key_a = svc._generate_cache_key(cfg_a)
        key_b = svc._generate_cache_key(cfg_b)
        assert key_a != key_b

    def test_key_contains_layer_type_prefix(self):
        """缓存键应以图层类型值开头。"""
        svc = _make_service()
        cfg = _make_layer(type=LayerType.PARTICLES)
        key = svc._generate_cache_key(cfg)
        assert key.startswith("particles_")

    def test_custom_cache_key(self):
        """如果 LayerConfig.cache_key 已设置，应直接使用。"""
        svc = _make_service()
        cfg = _make_layer(cache_key="my_custom_key")
        key = svc._generate_cache_key(cfg)
        assert key == "my_custom_key"


# ══════════════════════════════════════════════════════════
# 3. _hex_to_rgb_tuple 测试
# ══════════════════════════════════════════════════════════

class TestHexToRgbTuple:
    """测试 LayerRenderService._hex_to_rgb_tuple"""

    def test_valid_hex_with_hash(self):
        svc = _make_service()
        assert svc._hex_to_rgb_tuple("#1a1a2e") == (26, 26, 46)

    def test_valid_hex_without_hash(self):
        svc = _make_service()
        assert svc._hex_to_rgb_tuple("0f3460") == (15, 52, 96)

    def test_full_white(self):
        svc = _make_service()
        assert svc._hex_to_rgb_tuple("#FFFFFF") == (255, 255, 255)

    def test_full_black(self):
        svc = _make_service()
        assert svc._hex_to_rgb_tuple("#000000") == (0, 0, 0)


# ══════════════════════════════════════════════════════════
# 4. _get_ffmpeg_codec_params 测试
# ══════════════════════════════════════════════════════════

class TestGetFFmpegCodecParams:
    """测试 LayerRenderService._get_ffmpeg_codec_params"""

    @pytest.mark.parametrize("fmt,expected_codec,expected_crf", [
        (OutputFormat.H264, "libx264", 18),
        (OutputFormat.H265, "libx265", 23),
        (OutputFormat.PRORES_4444, "prores_ks", 0),
        (OutputFormat.PRORES_422, "prores_ks", 0),
    ])
    def test_known_formats(self, fmt, expected_codec, expected_crf):
        svc = _make_service()
        codec, crf = svc._get_ffmpeg_codec_params(fmt)
        assert codec == expected_codec
        assert crf == expected_crf

    def test_unknown_format_returns_default(self):
        """未映射的格式（如 PNG_SEQUENCE）应返回默认值。"""
        svc = _make_service()
        codec, crf = svc._get_ffmpeg_codec_params(OutputFormat.PNG_SEQUENCE)
        assert codec == "libx264"
        assert crf == 18


# ══════════════════════════════════════════════════════════
# 5. _get_ae_output_module 测试
# ══════════════════════════════════════════════════════════

class TestGetAEOutputModule:
    """测试 LayerRenderService._get_ae_output_module"""

    @pytest.mark.parametrize("fmt,expected_module", [
        (OutputFormat.H264, "H.264"),
        (OutputFormat.H265, "H.265"),
        (OutputFormat.PRORES_4444, "ProRes 4444"),
        (OutputFormat.PRORES_422, "ProRes 422"),
        (OutputFormat.PNG_SEQUENCE, "Lossless with Alpha"),
        (OutputFormat.EXR_SEQUENCE, "OpenEXR"),
    ])
    def test_all_formats(self, fmt, expected_module):
        svc = _make_service()
        assert svc._get_ae_output_module(fmt) == expected_module

    def test_unknown_format_returns_default(self):
        svc = _make_service()
        # 所有已知格式已覆盖，此处验证 default 分支
        # 用 MagicMock 模拟一个不存在的枚举值
        fake_fmt = MagicMock()
        fake_fmt.__hash__ = lambda self: hash("fake")
        result = svc._get_ae_output_module(fake_fmt)
        assert result == "Lossless with Alpha"


# ══════════════════════════════════════════════════════════
# 6. _calculate_dir_size 测试
# ══════════════════════════════════════════════════════════

class TestCalculateDirSize:
    """测试 LayerRenderService._calculate_dir_size"""

    def test_empty_dir(self, tmp_path):
        svc = _make_service()
        assert svc._calculate_dir_size(tmp_path) == 0

    def test_single_file(self, tmp_path):
        svc = _make_service()
        f = tmp_path / "test.txt"
        f.write_text("hello")
        assert svc._calculate_dir_size(tmp_path) == 5

    def test_nested_files(self, tmp_path):
        svc = _make_service()
        sub = tmp_path / "sub"
        sub.mkdir()
        (tmp_path / "a.txt").write_text("12345")      # 5 bytes
        (sub / "b.txt").write_text("1234567890")        # 10 bytes
        assert svc._calculate_dir_size(tmp_path) == 15

    def test_nonexistent_dir_returns_zero(self):
        svc = _make_service()
        assert svc._calculate_dir_size(Path("/nonexistent/path")) == 0


# ══════════════════════════════════════════════════════════
# 7. check_cache 测试
# ══════════════════════════════════════════════════════════

class TestCheckCache:
    """测试 LayerRenderService.check_cache"""

    def test_valid_cache(self, tmp_path):
        """有效清单 + 帧文件 → 返回缓存路径。"""
        svc = _make_service()
        cfg = _make_layer()
        cache_key = svc._generate_cache_key(cfg)
        cache_path = tmp_path / cache_key
        cache_path.mkdir()

        # 写清单
        manifest = {"cache_key": cache_key, "layer_name": cfg.name}
        (cache_path / "cache_manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        # 写一帧
        (cache_path / "frame_000001.png").write_bytes(b"\x89PNG")

        result = svc.check_cache(cfg, tmp_path)
        assert result == cache_path

    def test_missing_manifest(self, tmp_path):
        """缺少清单文件 → 返回 None。"""
        svc = _make_service()
        cfg = _make_layer()
        cache_key = svc._generate_cache_key(cfg)
        cache_path = tmp_path / cache_key
        cache_path.mkdir()
        (cache_path / "frame_000001.png").write_bytes(b"\x89PNG")

        result = svc.check_cache(cfg, tmp_path)
        assert result is None

    def test_empty_cache_dir(self, tmp_path):
        """缓存目录存在但无帧文件 → 返回 None。"""
        svc = _make_service()
        cfg = _make_layer()
        cache_key = svc._generate_cache_key(cfg)
        cache_path = tmp_path / cache_key
        cache_path.mkdir()

        manifest = {"cache_key": cache_key, "layer_name": cfg.name}
        (cache_path / "cache_manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )

        result = svc.check_cache(cfg, tmp_path)
        assert result is None

    def test_invalid_manifest_key_mismatch(self, tmp_path):
        """清单中的 cache_key 与期望不匹配 → 返回 None。"""
        svc = _make_service()
        cfg = _make_layer()
        cache_key = svc._generate_cache_key(cfg)
        cache_path = tmp_path / cache_key
        cache_path.mkdir()

        manifest = {"cache_key": "wrong_key", "layer_name": cfg.name}
        (cache_path / "cache_manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        (cache_path / "frame_000001.png").write_bytes(b"\x89PNG")

        result = svc.check_cache(cfg, tmp_path)
        assert result is None

    def test_nonexistent_cache_dir(self, tmp_path):
        """缓存键对应目录不存在 → 返回 None。"""
        svc = _make_service()
        cfg = _make_layer()
        result = svc.check_cache(cfg, tmp_path)
        assert result is None


# ══════════════════════════════════════════════════════════
# 8. build_from_preset 测试
# ══════════════════════════════════════════════════════════

class TestBuildFromPreset:
    """测试 LayerRenderService.build_from_preset"""

    def test_cinematic_vlog(self):
        svc = _make_service()
        pipeline = svc.build_from_preset(PipelinePreset.CINEMATIC_VLOG)
        assert pipeline.name == "cinematic_vlog_pipeline"
        assert pipeline.preset == PipelinePreset.CINEMATIC_VLOG
        # 应包含 6 层
        assert len(pipeline.layers) == 6
        # 按类型验证
        types = [l.type for l in pipeline.layers]
        assert LayerType.BACKGROUND in types
        assert LayerType.SUBJECT in types
        assert LayerType.MIDGROUND in types
        assert LayerType.PARTICLES in types
        assert LayerType.LIGHT in types
        assert LayerType.ADJUSTMENT in types
        # z_index 应递增
        sorted_z = [l.z_index for l in pipeline.get_sorted_layers()]
        assert sorted_z == sorted(sorted_z)

    def test_music_video(self):
        svc = _make_service()
        pipeline = svc.build_from_preset(PipelinePreset.MUSIC_VIDEO)
        assert pipeline.name == "music_video_pipeline"
        assert pipeline.preset == PipelinePreset.MUSIC_VIDEO
        assert len(pipeline.layers) == 5
        types = [l.type for l in pipeline.layers]
        assert LayerType.BACKGROUND in types
        assert LayerType.SUBJECT in types
        assert LayerType.PARTICLES in types
        assert LayerType.LIGHT in types
        assert LayerType.ADJUSTMENT in types
        sorted_z = [l.z_index for l in pipeline.get_sorted_layers()]
        assert sorted_z == sorted(sorted_z)

    def test_title_sequence(self):
        svc = _make_service()
        pipeline = svc.build_from_preset(PipelinePreset.TITLE_SEQUENCE)
        assert pipeline.name == "title_sequence_pipeline"
        assert pipeline.preset == PipelinePreset.TITLE_SEQUENCE
        assert len(pipeline.layers) == 4
        types = [l.type for l in pipeline.layers]
        assert LayerType.BACKGROUND in types
        assert LayerType.SUBJECT in types
        assert LayerType.LIGHT in types
        assert LayerType.ADJUSTMENT in types
        sorted_z = [l.z_index for l in pipeline.get_sorted_layers()]
        assert sorted_z == sorted(sorted_z)

    def test_string_preset(self):
        """传入字符串应自动转为 PipelinePreset 枚举。"""
        svc = _make_service()
        pipeline = svc.build_from_preset("cinematic_vlog")
        assert pipeline.preset == PipelinePreset.CINEMATIC_VLOG

    def test_custom_name(self):
        """自定义管线名称。"""
        svc = _make_service()
        pipeline = svc.build_from_preset(PipelinePreset.CINEMATIC_VLOG, name="my_pipeline")
        assert pipeline.name == "my_pipeline"


# ══════════════════════════════════════════════════════════
# 9. list_presets 测试
# ══════════════════════════════════════════════════════════

class TestListPresets:
    """测试 LayerRenderService.list_presets"""

    def test_returns_three_items(self):
        svc = _make_service()
        presets = svc.list_presets()
        assert len(presets) == 3

    def test_preset_names(self):
        svc = _make_service()
        presets = svc.list_presets()
        names = [p["name"] for p in presets]
        assert "cinematic_vlog" in names
        assert "music_video" in names
        assert "title_sequence" in names

    def test_preset_has_description(self):
        svc = _make_service()
        presets = svc.list_presets()
        for p in presets:
            assert "description" in p
            assert isinstance(p["description"], str)
            assert len(p["description"]) > 0


# ══════════════════════════════════════════════════════════
# 10. render_layer 测试
# ══════════════════════════════════════════════════════════

class TestRenderLayer:
    """测试 LayerRenderService.render_layer"""

    @pytest.mark.asyncio
    async def test_ae_renderer_dispatch(self, tmp_path):
        """AE 渲染器应调用 ae.create_comp。"""
        svc = _make_service()
        cfg = _make_layer(renderer=RendererType.AE)
        result = await svc.render_layer(cfg, work_dir=tmp_path / "work")
        assert result.success is True
        svc.ae.create_comp.assert_called_once()

    @pytest.mark.asyncio
    async def test_blender_renderer_dispatch(self, tmp_path):
        """Blender 渲染器应调用 blender.create_puppet_stage。"""
        svc = _make_service()
        cfg = _make_layer(renderer=RendererType.BLENDER)
        result = await svc.render_layer(cfg, work_dir=tmp_path / "work")
        assert result.success is True
        svc.blender.create_puppet_stage.assert_called_once()

    @pytest.mark.asyncio
    async def test_ffmpeg_renderer_dispatch_with_source(self, tmp_path):
        """FFmpeg 渲染器有 source_path 且文件存在时应调用 ffmpeg.extract_frames。"""
        svc = _make_service()
        source = tmp_path / "input.mp4"
        source.write_bytes(b"fake")
        cfg = _make_layer(renderer=RendererType.FFMPEG, source_path=str(source))
        result = await svc.render_layer(cfg, work_dir=tmp_path / "work")
        assert result.success is True
        svc.ffmpeg.extract_frames.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_hit(self, tmp_path):
        """缓存命中时应返回 cache_hit=True 且不调用渲染器。"""
        svc = _make_service()
        cfg = _make_layer(renderer=RendererType.AE)
        cache_key = svc._generate_cache_key(cfg)
        cache_path = tmp_path / "cache" / cache_key
        cache_path.mkdir(parents=True)

        manifest = {"cache_key": cache_key, "layer_name": cfg.name}
        (cache_path / "cache_manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        (cache_path / "frame_000001.png").write_bytes(b"\x89PNG")

        result = await svc.render_layer(
            cfg,
            work_dir=tmp_path / "work",
            cache_dir=tmp_path / "cache",
        )
        assert result.cache_hit is True
        assert result.success is True
        svc.ae.create_comp.assert_not_called()


# ══════════════════════════════════════════════════════════
# 11. render_pipeline 测试
# ══════════════════════════════════════════════════════════

class TestRenderPipeline:
    """测试 LayerRenderService.render_pipeline"""

    @pytest.mark.asyncio
    async def test_invisible_layer_skipped(self, tmp_path):
        """不可见图层应被跳过，不调用渲染器。"""
        svc = _make_service()
        invisible_layer = _make_layer(name="InvisibleBG", visible=False)
        pipeline = _make_pipeline(layers=[invisible_layer], cache_enabled=False)
        output_path = tmp_path / "output" / "result.mp4"
        result = await svc.render_pipeline(pipeline, output_path)
        # 没有可见图层 → success=False
        assert result.success is False
        # 不可见图层被记录为 skipped
        assert result.layer_results["InvisibleBG"].metadata.get("skipped") is True
        svc.ae.create_comp.assert_not_called()

    @pytest.mark.asyncio
    async def test_layer_failure_short_circuits(self, tmp_path):
        """某层渲染失败应短路返回，后续层不渲染。"""
        svc = _make_service()
        svc.ae.create_comp = AsyncMock(
            return_value=EngineResult(success=False, error="渲染失败")
        )

        layer1 = _make_layer(name="FailLayer", renderer=RendererType.AE, z_index=0)
        layer2 = _make_layer(name="NextLayer", renderer=RendererType.AE, z_index=10)
        pipeline = _make_pipeline(layers=[layer1, layer2], cache_enabled=False)
        output_path = tmp_path / "output" / "result.mp4"

        result = await svc.render_pipeline(pipeline, output_path)
        assert result.success is False
        assert "FailLayer" in result.error

    @pytest.mark.asyncio
    async def test_no_visible_layers(self, tmp_path):
        """所有图层均不可见 → success=False 且 error 提示无可见图层。"""
        svc = _make_service()
        layers = [
            _make_layer(name="A", visible=False, z_index=0),
            _make_layer(name="B", visible=False, z_index=10),
        ]
        pipeline = _make_pipeline(layers=layers, cache_enabled=False)
        output_path = tmp_path / "output" / "result.mp4"
        result = await svc.render_pipeline(pipeline, output_path)
        assert result.success is False
        assert "没有可合成的可见图层" in result.error


# ══════════════════════════════════════════════════════════
# 12. composite_layers 测试
# ══════════════════════════════════════════════════════════

class TestCompositeLayers:
    """测试 LayerRenderService.composite_layers"""

    @pytest.mark.asyncio
    async def test_zero_layers(self, tmp_path):
        """0 个图层 → 返回失败。"""
        svc = _make_service()
        result = await svc.composite_layers(
            layer_outputs=[],
            output_path=tmp_path / "out.mp4",
        )
        assert result.success is False
        assert "没有可合成的图层" in result.error

    @pytest.mark.asyncio
    async def test_single_layer_copy(self, tmp_path):
        """1 个图层 + PNG_SEQUENCE → 直接复制输出。"""
        svc = _make_service()
        # 构造一个有 output_path 的 LayerRenderResult
        src_dir = tmp_path / "src_layer"
        src_dir.mkdir()
        (src_dir / "frame_000001.png").write_bytes(b"\x89PNG")

        layer_result = LayerRenderResult(
            layer_name="Single",
            success=True,
            output_path=str(src_dir),
        )
        out_dir = tmp_path / "composite_output"
        result = await svc.composite_layers(
            layer_outputs=[layer_result],
            output_path=out_dir,
            output_format=OutputFormat.PNG_SEQUENCE,
        )
        assert result.success is True

    @pytest.mark.asyncio
    async def test_multi_layer_ffmpeg(self, tmp_path):
        """多层合成走 FFmpeg 路径。"""
        svc = _make_service()
        # 构造两个有帧文件的图层
        layer_dirs = []
        for i in range(2):
            d = tmp_path / f"layer_{i}"
            d.mkdir()
            (d / "frame_000001.png").write_bytes(b"\x89PNG")
            layer_dirs.append(d)

        layer_outputs = [
            LayerRenderResult(layer_name=f"Layer{i}", success=True, output_path=str(d))
            for i, d in enumerate(layer_dirs)
        ]
        output_path = tmp_path / "result.mp4"
        result = await svc.composite_layers(
            layer_outputs=layer_outputs,
            output_path=output_path,
            output_format=OutputFormat.H264,
            composite_renderer=RendererType.FFMPEG,
        )
        # Mock 的 _run_subprocess 返回 (0, "", "")，所以成功
        assert result.success is True


# ══════════════════════════════════════════════════════════
# 13. 综合与边界测试
# ══════════════════════════════════════════════════════════

class TestEdgeCases:
    """综合边界情况测试"""

    def test_cache_key_different_params(self):
        """参数不同 → 缓存键不同。"""
        svc = _make_service()
        cfg_a = _make_layer(params={"color": "#ff0000"})
        cfg_b = _make_layer(params={"color": "#00ff00"})
        assert svc._generate_cache_key(cfg_a) != svc._generate_cache_key(cfg_b)

    def test_cache_key_different_renderers(self):
        """渲染器不同 → 缓存键不同。"""
        svc = _make_service()
        cfg_a = _make_layer(renderer=RendererType.AE)
        cfg_b = _make_layer(renderer=RendererType.BLENDER)
        assert svc._generate_cache_key(cfg_a) != svc._generate_cache_key(cfg_b)

    def test_build_all_presets_z_ordering(self):
        """所有预设的 z_index 应满足排序约束（从低到高）。"""
        svc = _make_service()
        for preset in PipelinePreset:
            pipeline = svc.build_from_preset(preset)
            z_indices = [l.z_index for l in pipeline.get_sorted_layers()]
            assert z_indices == sorted(z_indices), f"预设 {preset.value} 的 z_index 未正确排序"

    def test_pipeline_get_visible_layers_excludes_invisible(self):
        """get_visible_layers 应排除不可见图层。"""
        pipeline = _make_pipeline(layers=[
            _make_layer(name="Vis", visible=True, z_index=0),
            _make_layer(name="Invis", visible=False, z_index=10),
        ])
        visible = pipeline.get_visible_layers()
        assert len(visible) == 1
        assert visible[0].name == "Vis"
