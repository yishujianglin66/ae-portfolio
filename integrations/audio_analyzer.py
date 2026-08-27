"""
integrations/audio_analyzer.py - 音频分析器 v1.0
==================================================

分析视频/音频文件的 BPM、能量、情绪，为智能调色提供依据。

后端优先级:
1. librosa（精确分析）
2. FFmpeg astats（快速估算）
3. 默认值回退

用法:
    from integrations.audio_analyzer import AudioAnalyzer

    analyzer = AudioAnalyzer()
    bpm, energy, mood = analyzer.analyze("video.mp4")
    # bpm=128, energy=0.75, mood="energetic"
"""
import os
import subprocess
import sys
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# 情绪映射表：能量+亮度 → 调色预设
MOOD_MAP = {
    ("high", "bright"): "warm",
    ("high", "dark"): "dramatic",
    ("high", "mid"): "rogue",
    ("mid", "bright"): "happy",
    ("mid", "dark"): "cinematic",
    ("mid", "mid"): "cinematic",
    ("low", "bright"): "calm",
    ("low", "dark"): "noir",
    ("low", "mid"): "memories",
}

# 能量阈值
ENERGY_HIGH = 0.6
ENERGY_LOW = 0.3
BRIGHT_HIGH = 0.5
BRIGHT_LOW = 0.3


class AudioAnalyzer:
    """音频分析器 — 提取 BPM、能量、情绪"""

    def __init__(self, ffmpeg_bin: str = ""):
        self.ffmpeg_bin = ffmpeg_bin or self._find_ffmpeg()

    def analyze(self, media_path: str) -> Tuple[float, float, str]:
        """分析音频文件

        Args:
            media_path: 视频/音频文件路径

        Returns:
            (bpm, energy, mood) 元组
            - bpm: 节拍速度 (60-200)
            - energy: 能量 (0.0-1.0)
            - mood: 情绪标签 (energetic/happy/sad/dark/calm/intense/romantic)
        """
        if not os.path.isfile(media_path):
            logger.warning(f"AudioAnalyzer: file not found: {media_path}")
            return 120.0, 0.5, "cinematic"

        # 尝试 librosa
        result = self._analyze_librosa(media_path)
        if result:
            return result

        # 回退到 FFmpeg astats
        result = self._analyze_ffmpeg(media_path)
        if result:
            return result

        # 默认值
        logger.warning("AudioAnalyzer: all methods failed, using defaults")
        return 120.0, 0.5, "cinematic"

    def analyze_full(self, media_path: str) -> Dict[str, Any]:
        """完整分析（返回所有指标）"""
        bpm, energy, mood = self.analyze(media_path)
        return {
            "bpm": bpm,
            "energy": energy,
            "mood": mood,
            "method": self._last_method,
            "media_path": media_path,
        }

    def _analyze_librosa(self, media_path: str) -> Optional[Tuple[float, float, str]]:
        """使用 librosa 精确分析"""
        try:
            import librosa
            import numpy as np
        except ImportError:
            return None

        try:
            self._last_method = "librosa"
            y, sr = librosa.load(media_path, sr=22050, mono=True, duration=120)

            # BPM
            tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
            bpm = float(tempo) if isinstance(tempo, (int, float)) else float(tempo[0])

            # 能量 (RMS)
            rms = librosa.feature.rms(y=y)[0]
            energy = float(np.mean(rms) / (np.max(rms) + 1e-8))

            # 亮度 (spectral centroid)
            centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
            brightness = float(np.mean(centroid) / (np.max(centroid) + 1e-8))

            mood = self._classify_mood(energy, brightness)
            logger.info(f"AudioAnalyzer [librosa]: BPM={bpm:.0f}, energy={energy:.2f}, "
                        f"brightness={brightness:.2f}, mood={mood}")
            return bpm, energy, mood

        except Exception as e:
            logger.warning(f"AudioAnalyzer [librosa] failed: {e}")
            return None

    def _analyze_ffmpeg(self, media_path: str) -> Optional[Tuple[float, float, str]]:
        """使用 FFmpeg astats 快速估算"""
        if not self.ffmpeg_bin:
            return None

        try:
            self._last_method = "ffmpeg"
            cmd = [
                self.ffmpeg_bin, "-i", media_path,
                "-af", "astats=metadata=1:reset=0,ametadata=print:key=lavfi.astats.Overall.RMS_level",
                "-f", "null", "-"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            # 解析 RMS level
            rms_values = []
            for line in result.stderr.split("\n"):
                if "RMS_level" in line:
                    try:
                        val = float(line.split("=")[-1])
                        if val > -100:  # 排除 -inf
                            rms_values.append(val)
                    except (ValueError, IndexError):
                        pass

            if rms_values:
                import statistics
                avg_rms = statistics.mean(rms_values)
                # RMS (-60 ~ 0 dB) → 能量 (0 ~ 1)
                energy = max(0, min(1, (avg_rms + 60) / 60))

                # 粗略 BPM 估算（基于能量）
                bpm = self._estimate_bpm_from_energy(energy)
                brightness = 0.5  # FFmpeg astats 无法直接获取亮度
                mood = self._classify_mood(energy, brightness)

                logger.info(f"AudioAnalyzer [ffmpeg]: RMS={avg_rms:.1f}dB, energy={energy:.2f}, "
                            f"mood={mood}")
                return bpm, energy, mood

        except Exception as e:
            logger.warning(f"AudioAnalyzer [ffmpeg] failed: {e}")

        return None

    def _classify_mood(self, energy: float, brightness: float) -> str:
        """根据能量和亮度分类情绪"""
        e_level = "high" if energy > ENERGY_HIGH else ("low" if energy < ENERGY_LOW else "mid")
        b_level = "bright" if brightness > BRIGHT_HIGH else ("dark" if brightness < BRIGHT_LOW else "mid")
        return MOOD_MAP.get((e_level, b_level), "cinematic")

    def _estimate_bpm_from_energy(self, energy: float) -> float:
        """从能量粗略估算 BPM"""
        if energy > 0.7:
            return 140.0
        elif energy > 0.4:
            return 110.0
        else:
            return 80.0

    @staticmethod
    def _find_ffmpeg() -> str:
        """查找 FFmpeg 可执行文件"""
        import shutil
        candidates = [
            r"C:\ffmpeg\bin\ffmpeg.exe",
            r"C:\ffmpeg-tmp\bin\ffmpeg.exe",
        ]
        for p in candidates:
            if os.path.isfile(p):
                return p
        return shutil.which("ffmpeg") or ""
