"""Tests for AuditionEngine."""
from __future__ import annotations

from pathlib import Path
import tempfile

import pytest

from src.engines.base import BaseEngine
from src.engines.audition import AuditionEngine


class TestAuditionEngine:
    """Test AuditionEngine adapter."""

    def test_init(self):
        engine = AuditionEngine()
        assert engine is not None
        assert engine.name == "audition"
        assert hasattr(engine, "executable_path")

    def test_inherits_base(self):
        assert issubclass(AuditionEngine, BaseEngine)

    @pytest.mark.asyncio
    async def test_noise_reduction_missing_audio(self):
        """输入音频不存在时优雅返回错误结果。"""
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            engine = AuditionEngine()
            result = await engine.noise_reduction(
                audio_path=td / "missing.wav",
                output_path=td / "clean.wav",
            )
            assert result.success is False
            assert "Audio not found" in result.error

    @pytest.mark.asyncio
    async def test_noise_reduction_fallback_script(self):
        """Bridge 不可用时降级为生成脚本文件，返回成功而非抛异常。"""
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            engine = AuditionEngine()
            engine._bridge_available = False  # 强制走降级脚本模式
            audio = td / "noisy.wav"
            audio.write_bytes(b"fake audio")
            out = td / "clean.wav"
            result = await engine.noise_reduction(
                audio_path=audio, output_path=out,
            )
            assert result.success is True
            assert result.metadata["bridge_mode"] == "manual_fallback"
            script = Path(result.metadata["script_path"])
            assert script.exists()

    @pytest.mark.asyncio
    async def test_unavailable_engine_short_circuit(self):
        """外部软件不可用时 execute 应短路返回错误而非抛异常。"""
        engine = AuditionEngine(
            executable_path=Path(tempfile.gettempdir()) / "au_missing.exe"
        )
        assert engine.available is False
        result = await engine.execute()
        assert result.success is False
        assert result.available is False
        assert result.error_code == "AUDITION_NOT_AVAILABLE"