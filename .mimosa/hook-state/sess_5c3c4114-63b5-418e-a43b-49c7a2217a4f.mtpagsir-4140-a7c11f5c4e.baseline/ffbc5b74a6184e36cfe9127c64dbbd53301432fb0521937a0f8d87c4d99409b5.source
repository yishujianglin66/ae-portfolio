"""Tests for MoviePyEngine."""
from __future__ import annotations

from pathlib import Path
import tempfile

import pytest

from src.engines.base import BaseEngine
from src.engines.moviepy import MoviePyEngine


class TestMoviePyEngine:
    """Test MoviePyEngine adapter."""

    def test_init(self):
        engine = MoviePyEngine()
        assert engine is not None
        assert engine.name == "moviepy"
        assert hasattr(engine, "executable_path")
        # sys.executable 一定存在，因此引擎应可用
        assert engine.available is True

    def test_inherits_base(self):
        assert issubclass(MoviePyEngine, BaseEngine)

    @pytest.mark.asyncio
    async def test_quick_compose_no_clips(self):
        """无片段时优雅返回错误结果。"""
        with tempfile.TemporaryDirectory() as td:
            engine = MoviePyEngine()
            result = await engine.quick_compose(
                clips=[],
                output_path=Path(td) / "out.mp4",
            )
            assert result.success is False
            assert "No clips" in result.error

    @pytest.mark.asyncio
    async def test_quick_compose_moviepy_not_installed(self):
        """moviepy 未安装时优雅返回错误结果而非抛异常。"""
        with tempfile.TemporaryDirectory() as td:
            engine = MoviePyEngine()
            engine._moviepy = None  # 模拟 moviepy 不可用
            result = await engine.quick_compose(
                clips=[{"path": "a.mp4"}],
                output_path=Path(td) / "out.mp4",
            )
            assert result.success is False
            assert "MoviePy not installed" in result.error

    @pytest.mark.asyncio
    async def test_extract_audio_missing_video(self):
        """输入视频不存在时优雅返回错误结果。"""
        with tempfile.TemporaryDirectory() as td:
            engine = MoviePyEngine()
            result = await engine.extract_audio(
                video_path=Path(td) / "missing.mp4",
                output_path=Path(td) / "out.wav",
            )
            assert result.success is False
            assert "Video not found" in result.error