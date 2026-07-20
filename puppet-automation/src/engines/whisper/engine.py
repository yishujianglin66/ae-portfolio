"""
Whisper Engine - 语音转文字/字幕
=================================

封装 OpenAI Whisper 的语音转写能力：
- 语音转文字（多语言）
- 高精度时间轴（逐字对齐）
- 语音翻译
- 自动生成SRT字幕

国内网络适配：
- 模型预下载到本地 D:\AE-Work\models\whisper\
- 安装使用清华/阿里云 PyPI 镜像
- 无需翻墙即可使用（模型本地加载）

使用方式：
    engine = WhisperEngine()
    result = await engine.transcribe("audio.mp3", model="base")
    result = await engine.generate_srt("audio.mp3", output_srt="subtitles.srt")
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Optional

from loguru import logger

from ..base import BaseEngine, EngineResult  # noqa: E402

# 默认模型目录
_DEFAULT_MODEL_DIR = Path(r"D:\AE-Work\models\whisper")


class WhisperEngine(BaseEngine):
    """Whisper speech-to-text engine."""

    name = "whisper"

    def __init__(
        self,
        executable_path: Path | str = sys.executable,
        model_dir: Optional[Path] = None,
    ):
        self.model_dir = model_dir or _DEFAULT_MODEL_DIR
        self.model_dir.mkdir(parents=True, exist_ok=True)
        super().__init__(executable_path)
        self._whisper = None
        self._check_installation()

    def _check_installation(self) -> None:
        """检查 whisper 是否已安装。"""
        try:
            import whisper
            self._whisper = whisper
            logger.info("[Whisper] whisper module loaded")
        except ImportError:
            logger.warning(
                "[Whisper] whisper not installed. "
                "Run: pip install -i https://pypi.tuna.tsinghua.edu.cn/simple openai-whisper"
            )

    async def execute(self, *args, **kwargs) -> EngineResult:
        """Dispatch to specific methods."""
        task = kwargs.get("task", "transcribe")
        if task == "transcribe":
            return await self.transcribe(*args, **{k: v for k, v in kwargs.items() if k != "task"})
        if task == "translate":
            return await self.translate(*args, **{k: v for k, v in kwargs.items() if k != "task"})
        if task == "srt":
            return await self.generate_srt(*args, **{k: v for k, v in kwargs.items() if k != "task"})
        return EngineResult(success=False, error=f"Unknown task: {task}")

    async def transcribe(
        self,
        audio_path: Path | str,
        model: str = "base",
        language: Optional[str] = "zh",
        word_level: bool = False,
    ) -> EngineResult:
        """语音转文字。

        Args:
            audio_path: 音频/视频文件路径
            model: 模型大小 (tiny/base/small/medium/large)
            language: 语言代码 (zh/en/ja/等)，None=自动检测
            word_level: 是否返回逐字时间戳
        """
        import time

        start = time.time()
        audio_path = Path(audio_path)

        if not audio_path.exists():
            return EngineResult(
                success=False, error=f"Audio file not found: {audio_path}",
            )

        if self._whisper is None:
            return EngineResult(
                success=False,
                error="Whisper not installed. "
                      "Run: pip install -i https://pypi.tuna.tsinghua.edu.cn/simple openai-whisper",
            )

        try:
            # 设置模型下载目录
            os.environ["WHISPER_MODEL_DIR"] = str(self.model_dir)

            # 加载模型（缓存到本地）
            logger.info(f"[Whisper] Loading model '{model}'...")
            model_obj = await asyncio.to_thread(
                self._whisper.load_model, model,
            )

            # 转写
            logger.info(f"[Whisper] Transcribing {audio_path}...")
            result = await asyncio.to_thread(
                model_obj.transcribe,
                str(audio_path),
                language=language,
                word_timestamps=word_level,
            )

            duration = time.time() - start

            # 格式化输出
            segments = result.get("segments", [])
            text = result.get("text", "").strip()

            formatted_segments = []
            for seg in segments:
                formatted_segments.append({
                    "id": seg.get("id"),
                    "start": seg.get("start"),
                    "end": seg.get("end"),
                    "text": seg.get("text", "").strip(),
                    "words": [
                        {"word": w["word"], "start": w["start"], "end": w["end"]}
                        for w in seg.get("words", [])
                    ] if word_level else [],
                })

            logger.success(
                f"[Whisper] Transcribed {len(text)} chars, "
                f"{len(segments)} segments in {duration:.1f}s"
            )

            return EngineResult(
                success=True,
                metadata={
                    "text": text,
                    "language": result.get("language", language or "auto"),
                    "segments": formatted_segments,
                    "segment_count": len(segments),
                    "model": model,
                    "word_level": word_level,
                },
                duration_seconds=duration,
            )

        except Exception as e:
            return EngineResult(
                success=False,
                error=f"Transcription failed: {str(e)[:500]}",
            )

    async def translate(
        self,
        audio_path: Path | str,
        target_language: str = "zh",
        model: str = "large",
    ) -> EngineResult:
        """语音翻译（如日文→中文）。

        Args:
            audio_path: 音频/视频文件路径
            target_language: 目标语言
            model: 推荐使用 large 模型获得更好翻译质量
        """
        import time

        start = time.time()
        audio_path = Path(audio_path)

        if not audio_path.exists():
            return EngineResult(
                success=False, error=f"Audio file not found: {audio_path}",
            )

        if self._whisper is None:
            return EngineResult(
                success=False, error="Whisper not installed",
            )

        try:
            os.environ["WHISPER_MODEL_DIR"] = str(self.model_dir)

            model_obj = await asyncio.to_thread(
                self._whisper.load_model, model,
            )

            # 使用 task="translate" 进行翻译
            result = await asyncio.to_thread(
                model_obj.transcribe,
                str(audio_path),
                task="translate",
                language=None,  # 自动检测源语言
            )

            duration = time.time() - start

            return EngineResult(
                success=True,
                metadata={
                    "translation": result.get("text", "").strip(),
                    "detected_language": result.get("language", "unknown"),
                    "target_language": target_language,
                    "segments": [
                        {"start": s["start"], "end": s["end"], "text": s["text"]}
                        for s in result.get("segments", [])
                    ],
                },
                duration_seconds=duration,
            )

        except Exception as e:
            return EngineResult(
                success=False,
                error=f"Translation failed: {str(e)[:500]}",
            )

    async def generate_srt(
        self,
        audio_path: Path | str,
        output_srt: Path | str,
        model: str = "base",
        language: Optional[str] = "zh",
        max_line_length: int = 40,
        max_lines: int = 2,
    ) -> EngineResult:
        """生成SRT字幕文件。

        Args:
            audio_path: 音频/视频文件路径
            output_srt: 输出SRT文件路径
            model: 模型大小
            language: 语言
            max_line_length: 每行最大字符数
            max_lines: 每条字幕最大行数
        """
        import time

        start = time.time()
        output_srt = Path(output_srt)

        # 先转写
        result = await self.transcribe(
            audio_path, model=model, language=language, word_level=False,
        )

        if not result.success:
            return result

        segments = result.metadata.get("segments", [])
        if not segments:
            return EngineResult(
                success=False, error="No speech detected in audio",
            )

        # 生成SRT
        srt_lines = []
        for i, seg in enumerate(segments, 1):
            start_time = self._seconds_to_srt_time(seg["start"])
            end_time = self._seconds_to_srt_time(seg["end"])
            text = seg["text"]

            # 长文本分行
            lines = self._wrap_text(text, max_line_length, max_lines)

            srt_lines.append(f"{i}")
            srt_lines.append(f"{start_time} --> {end_time}")
            srt_lines.extend(lines)
            srt_lines.append("")

        srt_content = "\n".join(srt_lines)
        output_srt.write_text(srt_content, encoding="utf-8")

        duration = time.time() - start

        logger.success(
            f"[Whisper] SRT generated: {output_srt} ({len(segments)} segments)"
        )

        return EngineResult(
            success=True,
            output_path=output_srt,
            metadata={
                "segment_count": len(segments),
                "srt_path": str(output_srt),
                "language": result.metadata.get("language"),
            },
            duration_seconds=duration,
        )

    @staticmethod
    def _seconds_to_srt_time(seconds: float) -> str:
        """将秒数转换为SRT时间格式 HH:MM:SS,mmm。"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    @staticmethod
    def _wrap_text(text: str, max_length: int, max_lines: int) -> list:
        """将长文本按最大长度分行。"""
        if len(text) <= max_length:
            return [text]

        words = text.split()
        lines = []
        current_line = ""

        for word in words:
            if len(current_line) + len(word) + 1 <= max_length:
                current_line += (" " if current_line else "") + word
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
                if len(lines) >= max_lines - 1:
                    # 剩余所有词放最后一行
                    break

        if current_line:
            lines.append(current_line)

        return lines[:max_lines]

    def get_info(self) -> dict:
        """返回引擎信息。"""
        return {
            "name": self.name,
            "installed": self._whisper is not None,
            "model_dir": str(self.model_dir),
            "model_dir_exists": self.model_dir.exists(),
            "capabilities": [
                "transcribe",
                "translate",
                "generate_srt",
            ],
            "available_models": ["tiny", "base", "small", "medium", "large"],
            "install_command": (
                "pip install -i https://pypi.tuna.tsinghua.edu.cn/simple "
                "openai-whisper"
            ),
        }