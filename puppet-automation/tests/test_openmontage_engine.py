"""Tests for OpenMontageEngine."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from src.engines.base import BaseEngine
from src.engines.openmontage import OpenMontageEngine


class TestOpenMontageEngine:
    """Test OpenMontageEngine adapter."""

    def test_init(self):
        engine = OpenMontageEngine()
        assert engine is not None
        assert engine.name == "openmontage"
        assert hasattr(engine, "executable_path")
        assert hasattr(engine, "om_root")

    def test_inherits_base(self):
        assert issubclass(OpenMontageEngine, BaseEngine)

    @pytest.mark.asyncio
    async def test_compose_no_clips(self):
        """无片段时优雅返回错误结果。"""
        with tempfile.TemporaryDirectory() as td:
            engine = OpenMontageEngine()
            result = await engine.compose_video(
                clips=[],
                output_path=Path(td) / "out.mp4",
            )
            assert result.success is False
            assert "No clips" in result.error

    @pytest.mark.asyncio
    async def test_search_stock_graceful_no_results(self):
        """默认国内源不在白名单内，应返回无结果的错误而非抛异常。"""
        engine = OpenMontageEngine()
        result = await engine.search_stock(query="test", kind="video")
        assert result.success is False
        assert "No results" in result.error

    def test_build_filter_complex(self):
        """滤镜图构建为纯函数，不依赖外部软件。"""
        engine = OpenMontageEngine()
        fc = engine._build_filter_complex(
            [{"path": "a.mp4", "duration": 5, "start": 0}], "fade"
        )
        assert "concat=n=1" in fc
        assert "[0:v]" in fc