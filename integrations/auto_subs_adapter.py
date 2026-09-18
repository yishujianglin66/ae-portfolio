"""
Auto Subs Adapter v1.0
=======================
字幕自动生成适配器，灵感来自 tmoroney/auto-subs (4k★)。

后端引擎:
  - faster-whisper (本地推理，Rust-like 性能)
  - openai-whisper (备选)

支持输出格式:
  - SRT (SubRip)
  - VTT (WebVTT)
  - TXT (纯文本)
  - JSON (带时间戳的结构化数据)

集成来源: tmoroney/auto-subs (GitHub 4k stars)
后端实现: faster-whisper + openai-whisper (已安装)
"""

import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output" / "subtitles"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class SubtitleSegment:
    """字幕片段"""
    id: int
    start: float  # 秒
    end: float    # 秒
    text: str
    speaker: str | None = None

    @property
    def start_srt(self) -> str:
        return self._format_time_srt(self.start)

    @property
    def end_srt(self) -> str:
        return self._format_time_srt(self.end)

    @property
    def start_vtt(self) -> str:
        return self._format_time_vtt(self.start)

    @property
    def end_vtt(self) -> str:
        return self._format_time_vtt(self.end)

    @staticmethod
    def _format_time_srt(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    @staticmethod
    def _format_time_vtt(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


class AutoSubsAdapter:
    """auto-subs 字幕生成适配器

    统一接口，支持 faster-whisper 和 openai-whisper 双后端。
    设计参考 tmoroney/auto-subs 的 Rust 高性能管道架构。
    """

    SUPPORTED_MODELS = ["tiny", "base", "small", "medium", "large", "large-v2", "large-v3"]
    SUPPORTED_FORMATS = ["srt", "vtt", "txt", "json"]
    SUPPORTED_OPERATIONS = [
        "transcribe", "generate_srt", "generate_vtt",
        "generate_txt", "generate_json", "translate_subtitle",
        "batch_transcribe",
    ]

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self._backend = None  # "faster_whisper" or "openai_whisper"
        self._model = None
        self._model_name = None
        self._init_backend()

    def _init_backend(self):
        """初始化后端引擎"""
        # 优先 faster-whisper
        try:
            from faster_whisper import WhisperModel
            self._backend = "faster_whisper"
            logger.info("[AutoSubs] Backend: faster-whisper")
            return
        except ImportError:
            logger.warning("[AutoSubs] faster-whisper not available")

        # 备选 openai-whisper
        try:
            import whisper
            self._backend = "openai_whisper"
            logger.info("[AutoSubs] Backend: openai-whisper")
            return
        except ImportError:
            logger.warning("[AutoSubs] openai-whisper not available")

        logger.error("[AutoSubs] No whisper backend available")

    def _ensure_model(self, model_name: str = "base"):
        """延迟加载模型"""
        if self._model is not None and self._model_name == model_name:
            return

        if self._backend == "faster_whisper":
            from faster_whisper import WhisperModel
            device = "cuda" if self.config.get("device") != "cpu" else "cpu"
            compute_type = "float16" if device == "cuda" else "int8"
            self._model = WhisperModel(
                model_name, device=device, compute_type=compute_type
            )
        elif self._backend == "openai_whisper":
            import whisper
            self._model = whisper.load_model(model_name)
        else:
            raise RuntimeError("No whisper backend available")

        self._model_name = model_name
        logger.info(f"[AutoSubs] Model loaded: {model_name} on {self._model.device if hasattr(self._model, 'device') else 'unknown'}")

    def check_available(self) -> bool:
        """检查工具是否可用"""
        return self._backend is not None

    def list_operations(self) -> list[str]:
        return self.SUPPORTED_OPERATIONS

    def execute(self, operation: str, params: dict[str, Any]) -> dict[str, Any]:
        """执行操作"""
        start = time.time()

        try:
            if operation == "transcribe":
                result = self._transcribe(params)
            elif operation == "generate_srt":
                result = self._generate_subtitle(params, "srt")
            elif operation == "generate_vtt":
                result = self._generate_subtitle(params, "vtt")
            elif operation == "generate_txt":
                result = self._generate_subtitle(params, "txt")
            elif operation == "generate_json":
                result = self._generate_subtitle(params, "json")
            elif operation == "translate_subtitle":
                result = self._translate(params)
            elif operation == "batch_transcribe":
                result = self._batch_transcribe(params)
            else:
                return {"status": "error", "error": f"Unknown operation: {operation}"}

            duration = (time.time() - start) * 1000
            result["duration_ms"] = duration
            result["backend"] = self._backend
            result["status"] = "success"
            return result

        except Exception as e:
            logger.error(f"[AutoSubs] {operation} failed: {e}")
            return {
                "status": "error",
                "operation": operation,
                "error": str(e),
                "duration_ms": (time.time() - start) * 1000,
            }

    def _transcribe(self, params: dict) -> dict:
        """转录音频文件"""
        audio_path = params.get("audio_path") or params.get("file_path")
        if not audio_path or not os.path.isfile(audio_path):
            return {"status": "error", "error": f"Audio file not found: {audio_path}"}

        model_name = params.get("model", "base")
        language = params.get("language")
        self._ensure_model(model_name)

        segments = []
        if self._backend == "faster_whisper":
            segs, info = self._model.transcribe(
                audio_path,
                language=language,
                beam_size=params.get("beam_size", 5),
                vad_filter=params.get("vad_filter", True),
            )
            for i, seg in enumerate(segs):
                segments.append(SubtitleSegment(
                    id=i + 1,
                    start=seg.start,
                    end=seg.end,
                    text=seg.text.strip(),
                ))
            detected_lang = info.language
            lang_prob = info.language_probability
        else:
            result = self._model.transcribe(
                audio_path,
                language=language,
                task=params.get("task", "transcribe"),
            )
            for i, seg in enumerate(result.get("segments", [])):
                segments.append(SubtitleSegment(
                    id=i + 1,
                    start=seg["start"],
                    end=seg["end"],
                    text=seg["text"].strip(),
                ))
            detected_lang = result.get("language", "unknown")
            lang_prob = 1.0

        return {
            "segments": [
                {"id": s.id, "start": s.start, "end": s.end, "text": s.text}
                for s in segments
            ],
            "segment_count": len(segments),
            "language": detected_lang,
            "language_probability": round(lang_prob, 3) if lang_prob else 0,
            "audio_path": audio_path,
        }

    def _generate_subtitle(self, params: dict, fmt: str) -> dict:
        """生成字幕文件"""
        # 先转录
        transcribe_result = self._transcribe(params)
        if transcribe_result.get("status") == "error":
            return transcribe_result

        segments = [
            SubtitleSegment(**s) for s in transcribe_result["segments"]
        ]

        # 格式化输出
        if fmt == "srt":
            content = self._to_srt(segments)
        elif fmt == "vtt":
            content = self._to_vtt(segments)
        elif fmt == "txt":
            content = self._to_txt(segments)
        elif fmt == "json":
            content = self._to_json(segments)
        else:
            return {"status": "error", "error": f"Unsupported format: {fmt}"}

        # 写文件
        audio_path = params.get("audio_path") or params.get("file_path", "input")
        stem = Path(audio_path).stem if audio_path else "output"
        output_filename = params.get("output_filename", f"{stem}.{fmt}")
        output_path = params.get("output_path", str(OUTPUT_DIR / output_filename))

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

        return {
            "format": fmt,
            "output_path": output_path,
            "segment_count": len(segments),
            "language": transcribe_result.get("language"),
            "file_size": os.path.getsize(output_path),
        }

    def _translate(self, params: dict) -> dict:
        """翻译字幕到目标语言"""
        audio_path = params.get("audio_path") or params.get("file_path")
        target_lang = params.get("target_language", "en")
        model_name = params.get("model", "base")
        self._ensure_model(model_name)

        if self._backend == "faster_whisper":
            segs, info = self._model.transcribe(
                audio_path,
                task="translate",
                language=target_lang,
                beam_size=params.get("beam_size", 5),
                vad_filter=True,
            )
            segments = [
                SubtitleSegment(id=i+1, start=s.start, end=s.end, text=s.text.strip())
                for i, s in enumerate(segs)
            ]
        else:
            result = self._model.transcribe(audio_path, task="translate", language=target_lang)
            segments = [
                SubtitleSegment(id=i+1, start=s["start"], end=s["end"], text=s["text"].strip())
                for i, s in enumerate(result.get("segments", []))
            ]

        fmt = params.get("format", "srt")
        if fmt == "srt":
            content = self._to_srt(segments)
        elif fmt == "vtt":
            content = self._to_vtt(segments)
        else:
            content = self._to_txt(segments)

        stem = Path(audio_path).stem if audio_path else "translated"
        output_path = params.get("output_path", str(OUTPUT_DIR / f"{stem}_translated.{fmt}"))
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

        return {
            "format": fmt,
            "output_path": output_path,
            "target_language": target_lang,
            "segment_count": len(segments),
        }

    def _batch_transcribe(self, params: dict) -> dict:
        """批量转录多个音频文件"""
        files = params.get("file_paths", [])
        results = []
        for f in files:
            r = self._transcribe({"audio_path": f, "model": params.get("model", "base")})
            results.append(r)
        return {
            "file_count": len(files),
            "results": results,
        }

    # ── 格式化方法 ─────────────────────────────────────────────

    @staticmethod
    def _to_srt(segments: list[SubtitleSegment]) -> str:
        lines = []
        for s in segments:
            lines.append(str(s.id))
            lines.append(f"{s.start_srt} --> {s.end_srt}")
            lines.append(s.text)
            lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _to_vtt(segments: list[SubtitleSegment]) -> str:
        lines = ["WEBVTT", ""]
        for s in segments:
            lines.append(f"{s.start_vtt} --> {s.end_vtt}")
            lines.append(s.text)
            lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _to_txt(segments: list[SubtitleSegment]) -> str:
        return "\n".join(s.text for s in segments)

    @staticmethod
    def _to_json(segments: list[SubtitleSegment]) -> str:
        data = [
            {"id": s.id, "start": s.start, "end": s.end, "text": s.text}
            for s in segments
        ]
        return json.dumps(data, ensure_ascii=False, indent=2)

    def summary(self) -> dict[str, Any]:
        """适配器状态摘要"""
        return {
            "backend": self._backend,
            "model_loaded": self._model is not None,
            "model_name": self._model_name,
            "operations": len(self.SUPPORTED_OPERATIONS),
            "formats": self.SUPPORTED_FORMATS,
            "models_available": self.SUPPORTED_MODELS,
        }
