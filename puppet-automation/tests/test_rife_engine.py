"""Tests for RifeEngine."""
from __future__ import annotations

from pathlib import Path
import tempfile

import pytest

from src.engines.base import BaseEngine
from src.engines.rife import RifeEngine


class TestRifeEngine:
    """Test RifeEngine adapter."""

    def test_init(self):
        engine = RifeEngine()
        assert engine is not None
        assert engine.name == "rife"
        assert hasattr(engine, "executable_path")
        assert hasattr(engine, "rife_root")
        # sys.executable 一定存在，因此引擎应可用
        assert engine.available is True

    def test_inherits_base(self):
        assert issubclass(RifeEngine, BaseEngine)

    @pytest.mark.asyncio
    async def test_interpolate_input_not_found(self):
        """输入视频不存在时优雅返回错误结果而非调用子进程。"""
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            engine = RifeEngine()
            result = await engine.interpolate(
                input_path=td / "missing.mp4",
                output_path=td / "out.mp4",
                multiplier=2,
            )
            assert result.success is False
            assert "Input video not found" in result.error

    @pytest.mark.asyncio
    async def test_slomo_input_not_found(self):
        """慢动作输入视频不存在时优雅返回错误结果。"""
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            engine = RifeEngine()
            result = await engine.slomo(
                input_path=td / "missing.mp4",
                output_path=td / "out.mp4",
                slow_factor=4.0,
            )
            assert result.success is False
            assert "Input video not found" in result.error