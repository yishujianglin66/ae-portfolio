"""Audio analysis service with Whisper + PyAnnote speaker diarization."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import torch
from core.torch_runtime import get_device
import whisper
from loguru import logger

logger = logging.getLogger(__name__)


class AudioAnalysisService:
    """Service for audio transcription and speaker diarization."""

    def __init__(self, model_name: str = "base"):
        self.model_name = model_name
        self._model: Optional[whisper.Whisper] = None
        self._device = get_device()

    def _load_model(self):
        """Load Whisper model if not already loaded."""
        if self._model is None:
            logger.info(f"Loading Whisper model '{self.model_name}' on {self._device}")
            self._model = whisper.load_model(self.model_name, device=self._device)

    async def transcribe(self, audio_path: str | Path) -> Dict[str, Any]:
        """Transcribe audio file using Whisper."""
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        self._load_model()

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: self._model.transcribe(str(audio_path))
        )

        segments = []
        for seg in result["segments"]:
            segments.append({
                "id": seg["id"],
                "start": round(seg["start"], 2),
                "end": round(seg["end"], 2),
                "text": seg["text"].strip(),
                "confidence": round(seg["confidence"], 4) if "confidence" in seg else None,
            })

        return {
            "language": result.get("language", "unknown"),
            "language_probability": round(result.get("language_probability", 0), 4),
            "duration": round(result.get("duration", 0), 2),
            "text": result.get("text", "").strip(),
            "segments": segments,
            "word_count": len(result.get("text", "").split()),
        }

    async def detect_speakers(self, audio_path: str | Path) -> Dict[str, Any]:
        """Detect speakers in audio file using PyAnnote."""
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        try:
            from pyannote.audio import Pipeline
        except ImportError:
            logger.warning("PyAnnote not available, returning basic transcription")
            return await self.transcribe(audio_path)

        try:
            pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=None
            )
        except Exception as e:
            logger.warning(f"PyAnnote model download failed: {e}")
            return await self.transcribe(audio_path)

        loop = asyncio.get_event_loop()
        diarization = await loop.run_in_executor(
            None,
            lambda: pipeline(str(audio_path))
        )

        speakers = set()
        speaker_segments = []

        for segment, _, speaker in diarization.itertracks(yield_label=True):
            speakers.add(speaker)
            speaker_segments.append({
                "speaker": speaker,
                "start": round(segment.start, 2),
                "end": round(segment.end, 2),
            })

        base_transcription = await self.transcribe(audio_path)
        base_transcription.update({
            "num_speakers": len(speakers),
            "speakers": list(speakers),
            "speaker_segments": speaker_segments,
        })

        return base_transcription

    async def analyze_audio(self, audio_path: str | Path, detect_speakers: bool = True) -> Dict[str, Any]:
        """Perform comprehensive audio analysis."""
        if detect_speakers:
            return await self.detect_speakers(audio_path)
        return await self.transcribe(audio_path)
