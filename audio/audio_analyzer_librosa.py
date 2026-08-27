"""
audio_analyzer_librosa.py
Phase 2-2 感知层增强 — 基于 librosa 的音频深度分析模块

用途：
    对输入音频进行深度 MIR（音乐信息检索）分析，输出 BPM、节拍时间、
    频谱特征、能量曲线、段落分割、情绪估计等结构化数据，
    供理解层在风格识别、节拍编排、能量映射中使用。

设计原则：
    1. 优雅降级：librosa 未安装时返回 success=False，不抛 ImportError。
    2. 与 audio_analyzer_enhanced.py 互补：本模块提供更纯粹的 librosa API，
       EnhancedAudioAnalyzer 综合使用 librosa + 自定义规则；本模块输出可直接
       注入 PerceptionResult.music_features。
    3. 结构化输出：AudioAnalysisResult dataclass，含 to_dict()。
    4. 帧级精度：节拍时间精确到毫秒，便于 BeatKeyframeMapper 使用。

对齐文件: ae_agent_pipeline.py perceive() / beat_keyframe_mapper.py
"""
from __future__ import annotations
import os
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

logger = logging.getLogger(__name__)

# A3 修复：超时保护配置
LIBROSA_TIMEOUT = 60  # librosa 分析超时（秒）
MAX_ANALYSIS_DURATION = 600  # 最大分析音频时长（秒）

try:
    from performance.cache_manager import DiskCache, file_fingerprint
    _audio_cache = DiskCache(name="audio_analysis", cache_dir=".cache/audio")
except ImportError:
    _audio_cache = None

__all__ = [
    "BeatInfo",
    "AudioSegment",
    "AudioAnalysisResult",
    "LibrosaAudioAnalyzer",
    "analyze_audio",
]

# 检测依赖可用性
try:
    import librosa
    import numpy as np
    _LIBROSA_AVAILABLE = True
except ImportError:  # pragma: no cover
    _LIBROSA_AVAILABLE = False
    librosa = None
    np = None


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------

@dataclass
class BeatInfo:
    """节拍信息

    Attributes:
        time: 节拍时间（秒）
        strength: 节拍强度（0~1）
        is_downbeat: 是否为强拍
    """
    time: float = 0.0
    strength: float = 0.0
    is_downbeat: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "time": round(self.time, 4),
            "strength": round(self.strength, 4),
            "is_downbeat": self.is_downbeat,
        }


@dataclass
class AudioSegment:
    """音频段落

    Attributes:
        index: 段落序号
        start_time: 起始时间（秒）
        end_time: 结束时间（秒）
        duration: 时长（秒）
        label: 段落标签（intro/verse/chorus/bridge/outro 等）
        avg_energy: 平均能量（RMS）
    """
    index: int = 0
    start_time: float = 0.0
    end_time: float = 0.0
    duration: float = 0.0
    label: str = ""
    avg_energy: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "start_time": round(self.start_time, 4),
            "end_time": round(self.end_time, 4),
            "duration": round(self.duration, 4),
            "label": self.label,
            "avg_energy": round(self.avg_energy, 6),
        }


@dataclass
class AudioAnalysisResult:
    """音频深度分析结果

    Attributes:
        success: 是否成功
        error: 错误信息
        audio_path: 音频路径
        duration: 总时长（秒）
        sample_rate: 采样率
        bpm: 估计 BPM
        bpm_confidence: BPM 置信度（0~1）
        beats: 节拍列表（BeatInfo）
        downbeats: 强拍时间列表
        spectral_centroid: 频谱质心（亮度）
        spectral_bandwidth: 频谱带宽
        spectral_rolloff: 频谱滚降点
        zero_crossing_rate: 过零率
        rms_energy: 总 RMS 能量
        energy_curve: 能量曲线（{times:[], values:[]}）
        mfccs: MFCC 特征均值（13 维）
        chroma: 色度特征均值（12 维）
        tempo: 估计速度（与 bpm 一致，保留兼容字段）
        key: 估计调性（如 "C major"）
        mood: 情绪标签
        mood_score: 情绪强度（0~1）
        segments: 段落列表
        from_cache: 是否来自缓存
    """
    success: bool = False
    error: str = ""
    audio_path: str = ""
    duration: float = 0.0
    sample_rate: int = 0
    bpm: float = 0.0
    bpm_confidence: float = 0.0
    beats: List[BeatInfo] = field(default_factory=list)
    downbeats: List[float] = field(default_factory=list)
    spectral_centroid: float = 0.0
    spectral_bandwidth: float = 0.0
    spectral_rolloff: float = 0.0
    zero_crossing_rate: float = 0.0
    rms_energy: float = 0.0
    energy_curve: Dict[str, List] = field(default_factory=dict)
    mfccs: List[float] = field(default_factory=list)
    chroma: List[float] = field(default_factory=list)
    tempo: float = 0.0
    key: str = ""
    mood: str = ""
    mood_score: float = 0.0
    segments: List[AudioSegment] = field(default_factory=list)
    from_cache: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "error": self.error,
            "audio_path": self.audio_path,
            "duration": round(self.duration, 4),
            "sample_rate": self.sample_rate,
            "bpm": round(self.bpm, 2),
            "bpm_confidence": round(self.bpm_confidence, 4),
            "beats": [b.to_dict() for b in self.beats],
            "downbeats": [round(d, 4) for d in self.downbeats],
            "spectral_centroid": round(self.spectral_centroid, 4),
            "spectral_bandwidth": round(self.spectral_bandwidth, 4),
            "spectral_rolloff": round(self.spectral_rolloff, 4),
            "zero_crossing_rate": round(self.zero_crossing_rate, 6),
            "rms_energy": round(self.rms_energy, 6),
            "energy_curve": self.energy_curve,
            "mfccs": [round(m, 4) for m in self.mfccs],
            "chroma": [round(c, 4) for c in self.chroma],
            "tempo": round(self.tempo, 2),
            "key": self.key,
            "mood": self.mood,
            "mood_score": round(self.mood_score, 4),
            "segments": [s.to_dict() for s in self.segments],
            "from_cache": self.from_cache,
        }

    def to_music_features(self) -> Dict[str, Any]:
        """转换为 PerceptionResult.music_features 兼容格式

        与 EnhancedAudioAnalyzer.analyze_audio 输出 features 字段对齐，
        便于下游 understand() / plan() 无缝替换。
        """
        return {
            "bpm": self.bpm,
            "tempo": self.tempo,
            "duration": self.duration,
            "beat_times": [b.time for b in self.beats],
            "downbeats": self.downbeats,
            "mood": self.mood,
            "mood_score": self.mood_score,
            "key": self.key,
            "energy": self.rms_energy,
            "spectral_centroid": self.spectral_centroid,
            "spectral_bandwidth": self.spectral_bandwidth,
            "spectral_rolloff": self.spectral_rolloff,
            "zero_crossing_rate": self.zero_crossing_rate,
            "segments": [s.to_dict() for s in self.segments],
        }


# ---------------------------------------------------------------------------
# 分析器
# ---------------------------------------------------------------------------

class LibrosaAudioAnalyzer:
    """基于 librosa 的音频深度分析器

    Usage:
        analyzer = LibrosaAudioAnalyzer()
        result = analyzer.analyze("music.mp3")
        if result.success:
            print(f"BPM={result.bpm}, beats={len(result.beats)}")
    """

    # 情绪映射表（基于 spectral_centroid + energy 的简单启发式）
    _MOOD_MAP = [
        # (centroid_min, energy_min, mood, mood_score)
        (3000, 0.05, "energetic", 0.85),
        (2000, 0.03, "happy", 0.70),
        (1500, 0.02, "neutral", 0.50),
        (1000, 0.01, "calm", 0.35),
        (0,    0.00, "sad", 0.20),
    ]

    def __init__(
        self,
        sr: int = 22050,
        hop_length: int = 512,
        enable_cache: bool = True,
        cache_dir: Optional[str] = None,
    ):
        """
        Args:
            sr: 采样率（默认 22050，与 librosa 默认一致）
            hop_length: 跳跃长度（影响帧级精度）
            enable_cache: 是否启用磁盘缓存
            cache_dir: 缓存目录
        """
        self.sr = sr
        self.hop_length = hop_length
        self._enable_cache = enable_cache
        self._cache_dir = cache_dir or os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            ".cache", "audio_librosa"
        )
        self._disk_cache = None
        self._fingerprint = None
        if enable_cache:
            try:
                from performance.cache_manager import DiskCache, file_fingerprint
                self._disk_cache = DiskCache(
                    cache_dir=self._cache_dir, name="audio_librosa"
                )
                self._fingerprint = file_fingerprint
            except ImportError:
                self._enable_cache = False

    # ------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------

    def analyze(self, audio_path: str) -> AudioAnalysisResult:
        """对单个音频文件执行深度分析

        Args:
            audio_path: 音频文件路径（mp3/wav/flac/ogg 等 librosa 支持格式）

        Returns:
            AudioAnalysisResult，失败时 success=False
        """
        if not _LIBROSA_AVAILABLE:
            return AudioAnalysisResult(
                success=False,
                error="librosa 未安装，请执行 pip install librosa soundfile",
                audio_path=audio_path,
            )

        if not os.path.exists(audio_path):
            return AudioAnalysisResult(
                success=False,
                error=f"音频文件不存在: {audio_path}",
                audio_path=audio_path,
            )

        # 缓存命中检查
        cache_key = None
        if self._enable_cache and self._disk_cache is not None:
            fp_extra = f"{self.sr}:{self.hop_length}"
            cache_key = self._fingerprint(audio_path, fp_extra)
            cached = self._disk_cache.get(cache_key, source_path=audio_path)
            if cached is not None:
                return self._result_from_cache(cached, audio_path)

        # 执行分析（A3 修复：添加超时保护）
        try:
            def _do_analyze():
                y, sr = librosa.load(audio_path, sr=self.sr, duration=MAX_ANALYSIS_DURATION)
                return y, sr

            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(_do_analyze)
                y, sr = future.result(timeout=LIBROSA_TIMEOUT)

            duration = librosa.get_duration(y=y, sr=sr)
            result = AudioAnalysisResult(
                success=True,
                audio_path=audio_path,
                duration=duration,
                sample_rate=sr,
            )

            # 节拍与速度
            self._analyze_beats(y, sr, result)
            # 频谱特征
            self._analyze_spectral(y, sr, result)
            # 能量曲线
            self._analyze_energy(y, sr, result)
            # MFCC + Chroma
            self._analyze_tonal(y, sr, result)
            # 调性估计
            self._estimate_key(y, sr, result)
            # 情绪估计
            self._estimate_mood(result)
            # 段落分割
            self._segment_audio(y, sr, result)

        except Exception as e:
            return AudioAnalysisResult(
                success=False,
                error=f"音频分析失败: {type(e).__name__}: {e}",
                audio_path=audio_path,
            )

        # 写入缓存
        if self._enable_cache and self._disk_cache is not None and cache_key:
            try:
                self._disk_cache.set(
                    cache_key, result.to_dict(), source_path=audio_path
                )
            except Exception:
                pass

        return result

    # ------------------------------------------------------------------
    # 子任务
    # ------------------------------------------------------------------

    def _analyze_beats(self, y, sr, result: AudioAnalysisResult):
        """节拍与速度分析"""
        tempo, beat_frames = librosa.beat.beat_track(
            y=y, sr=sr, hop_length=self.hop_length
        )
        beat_times = librosa.frames_to_time(beat_frames, sr=sr,
                                             hop_length=self.hop_length)

        # 节拍强度（基于 onset envelope）
        onset_env = librosa.onset.onset_strength(
            y=y, sr=sr, hop_length=self.hop_length
        )
        max_env = float(onset_env.max()) if onset_env.size else 1.0
        if max_env <= 0:
            max_env = 1.0

        beats: List[BeatInfo] = []
        for i, t in enumerate(beat_times):
            frame_idx = beat_frames[i] if i < len(beat_frames) else 0
            strength = float(onset_env[frame_idx]) / max_env if frame_idx < onset_env.size else 0.0
            # 简单强拍判定：每 4 拍一个强拍
            is_downbeat = (i % 4 == 0)
            beats.append(BeatInfo(
                time=float(t),
                strength=round(strength, 4),
                is_downbeat=is_downbeat,
            ))

        result.bpm = float(tempo)
        result.tempo = float(tempo)
        result.beats = beats
        result.downbeats = [b.time for b in beats if b.is_downbeat]
        # BPM 置信度：基于节拍数与时长比例
        if duration := result.duration:
            expected_beats = duration * float(tempo) / 60.0
            if expected_beats > 0:
                ratio = min(len(beats) / expected_beats, 1.0)
                result.bpm_confidence = round(max(0.0, min(1.0, ratio)), 4)
            else:
                result.bpm_confidence = 0.0
        else:
            result.bpm_confidence = 0.0

    def _analyze_spectral(self, y, sr, result: AudioAnalysisResult):
        """频谱特征"""
        # 频谱质心（亮度）
        result.spectral_centroid = float(
            librosa.feature.spectral_centroid(
                y=y, sr=sr, hop_length=self.hop_length
            ).mean()
        )
        # 频谱带宽
        result.spectral_bandwidth = float(
            librosa.feature.spectral_bandwidth(
                y=y, sr=sr, hop_length=self.hop_length
            ).mean()
        )
        # 频谱滚降点
        result.spectral_rolloff = float(
            librosa.feature.spectral_rolloff(
                y=y, sr=sr, hop_length=self.hop_length
            ).mean()
        )
        # 过零率
        result.zero_crossing_rate = float(
            librosa.feature.zero_crossing_rate(y, hop_length=self.hop_length).mean()
        )

    def _analyze_energy(self, y, sr, result: AudioAnalysisResult):
        """RMS 能量曲线"""
        rms = librosa.feature.rms(y=y, hop_length=self.hop_length)[0]
        times = librosa.frames_to_time(
            range(len(rms)), sr=sr, hop_length=self.hop_length
        )
        result.rms_energy = float(rms.mean())
        # 降采样到 100 个点以减少数据量
        if len(rms) > 100:
            step = len(rms) // 100
            rms_sampled = rms[::step][:100]
            times_sampled = times[::step][:100]
        else:
            rms_sampled = rms
            times_sampled = times
        result.energy_curve = {
            "times": [round(float(t), 4) for t in times_sampled],
            "values": [round(float(v), 6) for v in rms_sampled],
        }

    def _analyze_tonal(self, y, sr, result: AudioAnalysisResult):
        """MFCC + Chroma"""
        mfccs = librosa.feature.mfcc(
            y=y, sr=sr, n_mfcc=13, hop_length=self.hop_length
        )
        result.mfccs = [round(float(v), 4) for v in mfccs.mean(axis=1)]

        chroma = librosa.feature.chroma_stft(
            y=y, sr=sr, hop_length=self.hop_length
        )
        result.chroma = [round(float(v), 4) for v in chroma.mean(axis=1)]

    def _estimate_key(self, y, sr, result: AudioAnalysisResult):
        """调性估计（基于 chroma 特征）"""
        if not result.chroma:
            return
        # 12 个调名
        pitch_names = ["C", "C#", "D", "D#", "E", "F",
                       "F#", "G", "G#", "A", "A#", "B"]
        # 取能量最强的音
        max_idx = int(np.argmax(result.chroma))
        # 简单大/小调判定：比较主音与小三度（主音+3半音）的能量
        minor_third = (max_idx + 3) % 12
        major_third = (max_idx + 4) % 12
        if result.chroma[minor_third] > result.chroma[major_third]:
            mode = "minor"
        else:
            mode = "major"
        result.key = f"{pitch_names[max_idx]} {mode}"

    def _estimate_mood(self, result: AudioAnalysisResult):
        """情绪估计（基于频谱质心 + 能量的启发式）"""
        for centroid_min, energy_min, mood, score in self._MOOD_MAP:
            if (result.spectral_centroid >= centroid_min
                    and result.rms_energy >= energy_min):
                result.mood = mood
                result.mood_score = score
                return
        result.mood = "neutral"
        result.mood_score = 0.5

    def _segment_audio(self, y, sr, result: AudioAnalysisResult):
        """基于 chroma + RMS 的段落分割"""
        if not result.beats or result.duration < 5.0:
            return
        # 使用 librosa 的 self-similarity 分割
        try:
            bound_frames = librosa.segment.agglomerative(
                librosa.feature.chroma_stft(
                    y=y, sr=sr, hop_length=self.hop_length
                ),
                k=max(3, min(8, int(result.duration // 10)))
            )
            bound_times = librosa.frames_to_time(
                bound_frames, sr=sr, hop_length=self.hop_length
            )
            # 段落标签（基于位置）
            labels = self._label_segments(len(bound_times))
            rms = librosa.feature.rms(y=y, hop_length=self.hop_length)[0]
            rms_times = librosa.frames_to_time(
                range(len(rms)), sr=sr, hop_length=self.hop_length
            )

            segments: List[AudioSegment] = []
            for i, start_t in enumerate(bound_times):
                end_t = bound_times[i + 1] if i + 1 < len(bound_times) else result.duration
                # 计算段落平均能量
                mask = (rms_times >= start_t) & (rms_times <= end_t)
                avg_energy = float(rms[mask].mean()) if mask.any() else 0.0
                segments.append(AudioSegment(
                    index=i,
                    start_time=float(start_t),
                    end_time=float(end_t),
                    duration=round(float(end_t - start_t), 4),
                    label=labels[i] if i < len(labels) else "unknown",
                    avg_energy=avg_energy,
                ))
            result.segments = segments
        except Exception:
            # 段落分割失败不影响整体结果
            pass

    @staticmethod
    def _label_segments(n: int) -> List[str]:
        """根据段落数量生成标签"""
        if n <= 1:
            return ["intro"]
        if n == 2:
            return ["intro", "outro"]
        if n == 3:
            return ["intro", "main", "outro"]
        if n == 4:
            return ["intro", "verse", "chorus", "outro"]
        if n == 5:
            return ["intro", "verse", "chorus", "bridge", "outro"]
        # 6+ 段：循环 verse/chorus
        labels = ["intro"]
        middle_patterns = ["verse", "chorus", "verse", "chorus", "bridge"]
        for i in range(n - 2):
            labels.append(middle_patterns[i % len(middle_patterns)])
        labels.append("outro")
        return labels

    # ------------------------------------------------------------------
    # 缓存辅助
    # ------------------------------------------------------------------

    def _result_from_cache(
        self, cached: Dict, audio_path: str
    ) -> AudioAnalysisResult:
        """从缓存字典重建 AudioAnalysisResult"""
        beats = [BeatInfo(**b) for b in cached.get("beats", [])]
        segments = [AudioSegment(**s) for s in cached.get("segments", [])]
        return AudioAnalysisResult(
            success=True,
            audio_path=audio_path,
            duration=cached.get("duration", 0.0),
            sample_rate=cached.get("sample_rate", 0),
            bpm=cached.get("bpm", 0.0),
            bpm_confidence=cached.get("bpm_confidence", 0.0),
            beats=beats,
            downbeats=cached.get("downbeats", []),
            spectral_centroid=cached.get("spectral_centroid", 0.0),
            spectral_bandwidth=cached.get("spectral_bandwidth", 0.0),
            spectral_rolloff=cached.get("spectral_rolloff", 0.0),
            zero_crossing_rate=cached.get("zero_crossing_rate", 0.0),
            rms_energy=cached.get("rms_energy", 0.0),
            energy_curve=cached.get("energy_curve", {}),
            mfccs=cached.get("mfccs", []),
            chroma=cached.get("chroma", []),
            tempo=cached.get("tempo", 0.0),
            key=cached.get("key", ""),
            mood=cached.get("mood", ""),
            mood_score=cached.get("mood_score", 0.0),
            segments=segments,
            from_cache=True,
        )


# ---------------------------------------------------------------------------
# 模块级便捷 API
# ---------------------------------------------------------------------------

def analyze_audio(audio_path: str, sr: int = 22050) -> AudioAnalysisResult:
    """便捷 API：对单个音频执行深度分析

    Args:
        audio_path: 音频文件路径
        sr: 采样率

    Returns:
        AudioAnalysisResult
    """
    # 磁盘缓存：同一音频+采样率不重复分析
    if _audio_cache and os.path.exists(audio_path):
        cache_key = file_fingerprint(audio_path, extra=f"sr={sr}")
        cached = _audio_cache.get(cache_key)
        if cached is not None:
            return cached

    analyzer = LibrosaAudioAnalyzer(sr=sr, enable_cache=False)
    result = analyzer.analyze(audio_path)

    # 缓存成功结果
    if _audio_cache and result.success and os.path.exists(audio_path):
        cache_key = file_fingerprint(audio_path, extra=f"sr={sr}")
        _audio_cache.set(cache_key, result)

    return result


# ---------------------------------------------------------------------------
# 自检
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    print(f"librosa available: {_LIBROSA_AVAILABLE}")
    if len(sys.argv) > 1:
        result = analyze_audio(sys.argv[1])
        print(f"\n音频: {sys.argv[1]}")
        print(f"成功: {result.success}")
        if result.success:
            print(f"时长: {result.duration:.2f}s")
            print(f"BPM: {result.bpm:.1f} (置信度: {result.bpm_confidence:.2f})")
            print(f"调性: {result.key}")
            print(f"情绪: {result.mood} (score={result.mood_score:.2f})")
            print(f"节拍数: {len(result.beats)}")
            print(f"强拍数: {len(result.downbeats)}")
            print(f"段落数: {len(result.segments)}")
            for seg in result.segments:
                print(f"  [{seg.index}] {seg.start_time:.2f}s -> "
                      f"{seg.end_time:.2f}s ({seg.label})")
        else:
            print(f"错误: {result.error}")
