"""Tests for MediaEncoderEngine."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from src.engines.base import BaseEngine
from src.engines.media_encoder import MediaEncoderEngine


class TestMediaEncoderEngine:
    """Test MediaEncoderEngine adapter."""

    def test_init(self):
        engine = MediaEncoderEngine()
        assert engine is not None
        assert engine.name == "media_encoder"
        assert hasattr(engine, "executable_path")
        assert hasattr(engine, "watch_folder_path")

    def test_inherits_base(self):
        assert issubclass(MediaEncoderEngine, BaseEngine)

    @pytest.mark.asyncio
    async def test_list_presets(self):
        """list_presets 不依赖外部软件，应返回全部平台预设。"""
        engine = MediaEncoderEngine()
        result = await engine.list_presets()
        assert result.success is True
        platforms = result.metadata["platforms"]
        assert "douyin" in platforms
        assert "youtube" in platforms
        assert "bilibili" in platforms

    @pytest.mark.asyncio
    async def test_get_preset_known(self):
        engine = MediaEncoderEngine()
        result = await engine.get_preset("douyin")
        assert result.success is True
        assert result.metadata["platform"] == "douyin"
        assert result.metadata["resolution"] == (1080, 1920)

    @pytest.mark.asyncio
    async def test_get_preset_unknown(self):
        engine = MediaEncoderEngine()
        result = await engine.get_preset("not_a_platform")
        assert result.success is False
        assert "Unknown platform" in result.error

    @pytest.mark.asyncio
    async def test_encode_input_not_found_graceful(self):
        """输入文件不存在时应优雅返回错误结果而非抛异常。"""
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            engine = MediaEncoderEngine()
            result = await engine.encode(
                input_path=td / "missing.mp4",
                output_path=td / "out.mp4",
            )
            assert result.success is False
            assert "Input not found" in result.error

    @pytest.mark.asyncio
    async def test_unavailable_engine_short_circuit(self):
        """外部软件不可用（exe 不存在）时 execute 应短路返回错误。"""
        exe = Path(tempfile.gettempdir()) / "me_does_not_exist.exe"
        engine = MediaEncoderEngine(executable_path=exe)
        assert engine.available is False
        result = await engine.execute()
        assert result.success is False
        assert result.available is False
        assert result.error_code == "MEDIA_ENCODER_NOT_AVAILABLE"