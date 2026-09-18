"""Tests for WhisperEngine."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from src.engines.base import BaseEngine
from src.engines.whisper import WhisperEngine


class TestWhisperEngine:
    """Test WhisperEngine adapter."""

    def test_init(self):
        with tempfile.TemporaryDirectory() as td:
            engine = WhisperEngine(model_dir=Path(td) / "models")
            assert engine is not None
            assert engine.name == "whisper"
            assert hasattr(engine, "executable_path")
            assert engine.available is True

    def test_inherits_base(self):
        assert issubclass(WhisperEngine, BaseEngine)

    @pytest.mark.asyncio
    async def test_transcribe_missing_audio(self):
        """输入音频不存在时优雅返回错误结果。"""
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            engine = WhisperEngine(model_dir=td / "models")
            result = await engine.transcribe(audio_path=td / "missing.mp3")
            assert result.success is False
            assert "Audio file not found" in result.error

    def test_seconds_to_srt_time(self):
        """SRT 时间格式化为纯静态函数，不依赖外部软件。"""
        assert WhisperEngine._seconds_to_srt_time(0) == "00:00:00,000"
        assert WhisperEngine._seconds_to_srt_time(3661.5) == "01:01:01,500"

    def test_wrap_text(self):
        """文本换行为纯静态函数，不依赖外部软件。"""
        lines = WhisperEngine._wrap_text("a b c d e", max_length=3, max_lines=2)
        assert isinstance(lines, list)
        assert len(lines) <= 2
        assert lines[0] == "a b"