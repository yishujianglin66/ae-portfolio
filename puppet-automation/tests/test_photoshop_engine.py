"""Tests for PhotoshopEngine."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from src.engines.base import BaseEngine
from src.engines.photoshop import PhotoshopEngine


class TestPhotoshopEngine:
    """Test PhotoshopEngine adapter."""

    def test_init(self):
        engine = PhotoshopEngine()
        assert engine is not None
        assert engine.name == "photoshop"
        assert hasattr(engine, "executable_path")

    def test_inherits_base(self):
        assert issubclass(PhotoshopEngine, BaseEngine)

    @pytest.mark.asyncio
    async def test_smart_object_export_missing_psd(self):
        """PSD 不存在时优雅返回错误结果。"""
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            engine = PhotoshopEngine()
            result = await engine.smart_object_export(
                psd_path=td / "missing.psd",
                output_dir=td / "out",
            )
            assert result.success is False
            assert "PSD not found" in result.error

    @pytest.mark.asyncio
    async def test_batch_process_missing_dir(self):
        """输入目录不存在时优雅返回错误结果。"""
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            engine = PhotoshopEngine()
            result = await engine.batch_process(
                image_dir=td / "missing",
                action_name="foo",
                output_dir=td / "out",
            )
            assert result.success is False
            assert "Directory not found" in result.error

    @pytest.mark.asyncio
    async def test_generate_texture_fallback_jsx(self):
        """Bridge 不可用时降级为生成 JSX 文件，返回成功而非抛异常。"""
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            engine = PhotoshopEngine()
            engine._bridge_available = False  # 强制走降级脚本模式
            result = await engine.generate_texture(
                prompt="test", output_path=td / "tex.png",
            )
            assert result.success is True
            assert result.metadata["bridge_mode"] == "manual_fallback"

    @pytest.mark.asyncio
    async def test_unavailable_engine_short_circuit(self):
        """外部软件不可用时 execute 应短路返回错误而非抛异常。"""
        engine = PhotoshopEngine(
            executable_path=Path(tempfile.gettempdir()) / "ps_missing.exe"
        )
        assert engine.available is False
        result = await engine.execute()
        assert result.success is False
        assert result.available is False
        assert result.error_code == "PHOTOSHOP_NOT_AVAILABLE"