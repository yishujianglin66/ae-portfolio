"""Tests for engine base and all engine adapters."""
from __future__ import annotations

from pathlib import Path

import pytest
from src.engines.base import BaseEngine, EngineResult


class TestEngineResult:
    """Test EngineResult data class."""

    def test_success_result(self):
        r = EngineResult(
            success=True,
            output_path=Path("/tmp/out.mp4"),
            metadata={"codec": "h264"},
        )
        assert r.success is True
        assert r.output_path == Path("/tmp/out.mp4")
        assert r.metadata == {"codec": "h264"}
        assert r.error is None
        assert r.duration_seconds == 0.0

    def test_failure_result(self):
        r = EngineResult(
            success=False,
            error="Something went wrong",
        )
        assert r.success is False
        assert r.output_path is None
        assert r.error == "Something went wrong"
        assert r.metadata == {}


class TestBaseEngine:
    """Test BaseEngine abstract class."""

    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            BaseEngine()

    def test_subclass_must_implement_execute(self):
        class IncompleteEngine(BaseEngine):
            pass

        with pytest.raises(TypeError):
            IncompleteEngine()

    def test_subclass_with_execute(self, tmp_path):
        exe = tmp_path / "mock.exe"
        exe.touch()

        class CompleteEngine(BaseEngine):
            # 接口演进同步（2026-09-25）：execute 是模板方法，子类实现 _execute_impl
            async def _execute_impl(self, *args, **kwargs):
                return EngineResult(success=True)

        engine = CompleteEngine(exe)
        assert hasattr(engine, "execute")
        assert hasattr(engine, "executable_path")
        assert engine.executable_path == exe


class TestFFmpegEngine:
    """Test FFmpegEngine adapter."""

    def test_ffmpeg_engine_init(self):
        from src.engines.ffmpeg import FFmpegEngine
        engine = FFmpegEngine()
        assert engine is not None
        assert hasattr(engine, "executable_path")

    def test_ffmpeg_engine_has_actions(self):
        from src.engines.ffmpeg import FFmpegEngine
        engine = FFmpegEngine()
        # Should have action methods
        assert hasattr(engine, "convert")
        assert hasattr(engine, "extract_frames")
        assert hasattr(engine, "extract_audio")
        assert hasattr(engine, "concat")


class TestAEEngine:
    """Test AEEngine adapter."""

    def test_ae_engine_init(self):
        from src.engines.ae import AEEngine
        engine = AEEngine()
        assert engine is not None
        assert hasattr(engine, "executable_path")

    def test_ae_engine_has_actions(self):
        from src.engines.ae import AEEngine
        engine = AEEngine()
        assert hasattr(engine, "render_comp")
        assert hasattr(engine, "run_script")


class TestTopazEngine:
    """Test TopazEngine adapter."""

    def test_topaz_engine_init(self):
        from src.engines.topaz import TopazEngine
        engine = TopazEngine()
        assert engine is not None
        assert hasattr(engine, "executable_path")

    def test_topaz_engine_has_actions(self):
        from src.engines.topaz import TopazEngine
        engine = TopazEngine()
        assert hasattr(engine, "enhance")


class TestSilhouetteEngine:
    """Test SilhouetteEngine adapter."""

    def test_silhouette_engine_init(self):
        from src.engines.silhouette import SilhouetteEngine
        engine = SilhouetteEngine()
        assert engine is not None
        assert hasattr(engine, "executable_path")

    def test_silhouette_engine_has_actions(self):
        from src.engines.silhouette import SilhouetteEngine
        engine = SilhouetteEngine()
        assert hasattr(engine, "create_roto_session")
        assert hasattr(engine, "run_tracker")


class TestBlenderEngine:
    """Test BlenderEngine adapter."""

    def test_blender_engine_init(self):
        from src.engines.blender import BlenderEngine
        engine = BlenderEngine()
        assert engine is not None
        assert hasattr(engine, "executable_path")

    def test_blender_engine_has_actions(self):
        from src.engines.blender import BlenderEngine
        engine = BlenderEngine()
        assert hasattr(engine, "create_puppet_stage")
        assert hasattr(engine, "run_script")
        assert hasattr(engine, "render_animation")


class TestDavinciEngine:
    """Test DavinciEngine adapter."""

    def test_davinci_engine_init(self):
        from src.engines.davinci import DavinciEngine
        engine = DavinciEngine()
        assert engine is not None

    def test_davinci_engine_has_actions(self):
        from src.engines.davinci import DavinciEngine
        engine = DavinciEngine()
        assert hasattr(engine, "apply_color_grade")
        assert hasattr(engine, "export_lut")


class TestAllEnginesInheritBase:
    """Verify all engines properly inherit from BaseEngine."""

    @pytest.mark.parametrize("engine_module,engine_class", [
        ("src.engines.ffmpeg", "FFmpegEngine"),
        ("src.engines.ae", "AEEngine"),
        ("src.engines.topaz", "TopazEngine"),
        ("src.engines.silhouette", "SilhouetteEngine"),
        ("src.engines.blender", "BlenderEngine"),
        ("src.engines.davinci", "DavinciEngine"),
    ])
    def test_engine_inherits_base(self, engine_module, engine_class):
        import importlib
        mod = importlib.import_module(engine_module)
        cls = getattr(mod, engine_class)
        assert issubclass(cls, BaseEngine)

    @pytest.mark.parametrize("engine_module,engine_class", [
        ("src.engines.ffmpeg", "FFmpegEngine"),
        ("src.engines.ae", "AEEngine"),
        ("src.engines.topaz", "TopazEngine"),
        ("src.engines.silhouette", "SilhouetteEngine"),
        ("src.engines.blender", "BlenderEngine"),
        ("src.engines.davinci", "DavinciEngine"),
    ])
    def test_engine_has_execute_method(self, engine_module, engine_class):
        import importlib
        mod = importlib.import_module(engine_module)
        cls = getattr(mod, engine_class)
        assert hasattr(cls, "execute")
