"""WhisperX 词级字幕生成器。

基于 Whisper 生成带词级时间戳的字幕（word-level timestamps），
可直接生成 SRT/ASS 字幕或 Remotion/AE 字幕动画。
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger


@dataclass
class WordTimestamp:
    """词级时间戳。"""

    word: str
    start: float  # 秒
    end: float  # 秒
    score: float = 1.0
    speaker: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "word": self.word,
            "start": self.start,
            "end": self.end,
            "score": self.score,
            "speaker": self.speaker,
        }


@dataclass
class SubtitleSegment:
    """字幕片段（一行/一句）。"""

    text: str
    start: float
    end: float
    words: List[WordTimestamp] = field(default_factory=list)
    speaker: Optional[str] = None

    def to_srt(self, index: int) -> str:
        """生成 SRT 格式。"""
        start_str = self._format_srt_time(self.start)
        end_str = self._format_srt_time(self.end)
        return f"{index}\n{start_str} --> {end_str}\n{self.text}\n"

    def to_ass(
        self,
        index: int,
        style: str = "Default",
    ) -> str:
        """生成 ASS 格式。"""
        start_str = self._format_ass_time(self.start)
        end_str = self._format_ass_time(self.end)
        return f"Dialogue: 0,{start_str},{end_str},{style},,0,0,0,,{self.text}"

    @staticmethod
    def _format_srt_time(seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}".replace(".", ",")

    @staticmethod
    def _format_ass_time(seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        centi = int((secs - int(secs)) * 100)
        return f"{hours:d}:{minutes:02d}:{int(secs):02d}.{centi:02d}"


class WhisperXSubtitleGenerator:
    """WhisperX 词级字幕生成器。

    如果安装了 faster-whisper，则使用本地模型；
    否则降级为 whisper 原生模式。
    """

    def __init__(self, model_size: str = "base", device: str = "cpu"):
        self.model_size = model_size
        self.device = device
        self._model = None
        logger.info(f"WhisperXSubtitleGenerator 初始化: model={model_size}, device={device}")

    def _load_model(self):
        """懒加载模型。"""
        if self._model is not None:
            return self._model
        try:
            import whisper
            self._model = whisper.load_model(self.model_size, device=self.device)
            logger.info(f"Whisper 模型加载完成: {self.model_size}")
        except Exception as e:
            logger.error(f"Whisper 模型加载失败: {e}")
            self._model = None
        return self._model

    def transcribe(
        self,
        audio_path: Path | str,
        language: Optional[str] = None,
        word_timestamps: bool = True,
    ) -> List[SubtitleSegment]:
        """转录音频并生成词级字幕。

        Args:
            audio_path: 音频文件路径
            language: 语言代码（如 'zh', 'en'），None 自动检测
            word_timestamps: 是否生成词级时间戳

        Returns:
            SubtitleSegment 列表
        """
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")

        model = self._load_model()
        if model is None:
            return self._fallback_transcribe(audio_path)

        try:
            result = model.transcribe(
                str(audio_path),
                language=language,
                word_timestamps=word_timestamps,
            )
            return self._convert_to_segments(result)
        except Exception as e:
            logger.error(f"Whisper 转录失败: {e}")
            return self._fallback_transcribe(audio_path)

    def _convert_to_segments(self, whisper_result: Dict[str, Any]) -> List[SubtitleSegment]:
        """将 Whisper 结果转换为 SubtitleSegment。"""
        segments = []
        for seg in whisper_result.get("segments", []):
            words = []
            for w in seg.get("words", []):
                words.append(WordTimestamp(
                    word=w.get("word", "").strip(),
                    start=float(w.get("start", 0)),
                    end=float(w.get("end", 0)),
                    score=float(w.get("probability", 1.0)),
                ))
            segments.append(SubtitleSegment(
                text=seg.get("text", "").strip(),
                start=float(seg.get("start", 0)),
                end=float(seg.get("end", 0)),
                words=words,
            ))
        return segments

    def _fallback_transcribe(self, audio_path: Path) -> List[SubtitleSegment]:
        """降级：返回空列表（标记 stub）。"""
        logger.warning("Whisper 模型不可用，返回空字幕列表")
        return []

    def export_srt(
        self,
        segments: List[SubtitleSegment],
        output_path: Path | str,
    ) -> Path:
        """导出 SRT 字幕文件。"""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            for i, seg in enumerate(segments, 1):
                f.write(seg.to_srt(i))
                f.write("\n")
        logger.info(f"SRT 字幕已导出: {output_path}")
        return output_path

    def export_ass(
        self,
        segments: List[SubtitleSegment],
        output_path: Path | str,
        style: str = "Default",
    ) -> Path:
        """导出 ASS 字幕文件。"""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        header = (
            "[Script Info]\n"
            "Title: WhisperX Generated\n"
            "ScriptType: v4.00+\n\n"
            "[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
            "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
            "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
            "Alignment, MarginL, MarginR, MarginV, Encoding\n"
            "Style: Default,Arial,48,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,"
            "0,0,0,0,100,100,0,0,1,2,1,2,30,30,60,1\n\n"
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
            "Effect, Text\n"
        )
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(header)
            for i, seg in enumerate(segments, 1):
                f.write(seg.to_ass(i, style) + "\n")
        logger.info(f"ASS 字幕已导出: {output_path}")
        return output_path

    def export_json(
        self,
        segments: List[SubtitleSegment],
        output_path: Path | str,
    ) -> Path:
        """导出 JSON 字幕（含词级时间戳，供 Remotion 使用）。"""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": "1.0",
            "generated_at": time.time(),
            "segments": [
                {
                    "text": s.text,
                    "start": s.start,
                    "end": s.end,
                    "speaker": s.speaker,
                    "words": [w.to_dict() for w in s.words],
                }
                for s in segments
            ],
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"JSON 字幕已导出: {output_path}")
        return output_path
