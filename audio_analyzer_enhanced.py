#!/usr/bin/env python3
"""
音频分析增强版 v2.0
增强功能：
1. 精确节拍检测 - librosa beat_track + onset_detect
2. 能量曲线分析 - RMS能量、频谱能量、能量峰值检测
3. 智能段落分割 - librosa segment + 自定义规则
4. 情感分析 - 基于声学特征的情绪识别
5. 音频指纹 - chroma特征、MFCC、频谱特征
6. 和弦检测 - 基于chroma的和弦识别
"""
import os
import json
import math
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "media-config.json")


@dataclass
class AudioSegment:
    start_time: float
    end_time: float
    duration: float
    segment_type: str
    beat_count: int
    avg_energy: float
    energy_variance: float


@dataclass
class AudioFeaturesEnhanced:
    bpm: float = 0.0
    tempo: float = 0.0
    key: str = ""
    mode: str = ""
    duration: float = 0.0
    loudness: float = 0.0
    spectral_centroid: float = 0.0
    spectral_bandwidth: float = 0.0
    spectral_rolloff: float = 0.0
    zero_crossing_rate: float = 0.0
    mfccs: List[float] = None
    chroma: List[float] = None
    energy: float = 0.0
    energy_curve: Dict = None
    mood: str = ""
    mood_score: float = 0.0
    genre: str = ""
    beats: List[float] = None
    downbeats: List[float] = None
    segments: List[AudioSegment] = None
    chords: List[Dict] = None
    danceability: float = 0.0
    valence: float = 0.0
    arousal: float = 0.0

    @staticmethod
    def _safe_round(val, ndigits):
        """安全round，兼容numpy类型"""
        try:
            return round(float(val), ndigits)
        except (TypeError, ValueError):
            return 0

    def to_dict(self):
        return {
            "bpm": self._safe_round(self.bpm, 1),
            "tempo": self._safe_round(self.tempo, 1),
            "key": self.key,
            "mode": self.mode,
            "duration": self._safe_round(self.duration, 2),
            "loudness": self._safe_round(self.loudness, 2),
            "spectral_centroid": self._safe_round(self.spectral_centroid, 2),
            "spectral_bandwidth": self._safe_round(self.spectral_bandwidth, 2),
            "spectral_rolloff": self._safe_round(self.spectral_rolloff, 2),
            "zero_crossing_rate": self._safe_round(self.zero_crossing_rate, 4),
            "mfccs": [self._safe_round(v, 3) for v in (self.mfccs or [])],
            "chroma": [self._safe_round(v, 3) for v in (self.chroma or [])],
            "energy": self._safe_round(self.energy, 3),
            "energy_curve": {
                "times": [self._safe_round(t, 3) for t in (self.energy_curve.get("times", []) if self.energy_curve else [])],
                "values": [self._safe_round(v, 4) for v in (self.energy_curve.get("values", []) if self.energy_curve else [])],
                "peaks": self.energy_curve.get("peaks", []) if self.energy_curve else []
            },
            "mood": self.mood,
            "mood_score": self._safe_round(self.mood_score, 3),
            "genre": self.genre,
            "beat_count": len(self.beats) if self.beats else 0,
            "beats": [self._safe_round(t, 3) for t in (self.beats or [])],
            "downbeats": [self._safe_round(t, 3) for t in (self.downbeats or [])],
            "segments": [
                {
                    "start_time": self._safe_round(s.start_time, 3),
                    "end_time": self._safe_round(s.end_time, 3),
                    "duration": self._safe_round(s.duration, 3),
                    "segment_type": s.segment_type,
                    "beat_count": s.beat_count,
                    "avg_energy": self._safe_round(s.avg_energy, 4),
                    "energy_variance": self._safe_round(s.energy_variance, 4)
                }
                for s in (self.segments or [])
            ],
            "chords": self.chords or [],
            "danceability": self._safe_round(self.danceability, 3),
            "valence": self._safe_round(self.valence, 3),
            "arousal": self._safe_round(self.arousal, 3)
        }


class EnhancedAudioAnalyzer:
    def __init__(self, config_path: str = CONFIG_PATH, enable_cache: bool = True):
        self._librosa = None
        self._scipy = None
        self._enable_cache = enable_cache
        self._disk_cache = None
        self._fingerprint = None
        self._get_config_cached = None
        if enable_cache:
            try:
                from performance.cache_manager import DiskCache, file_fingerprint, get_config_cached
                self._fingerprint = file_fingerprint
                self._get_config_cached = get_config_cached
                cache_dir = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    ".cache", "audio_analysis"
                )
                self._disk_cache = DiskCache(cache_dir=cache_dir, name="audio_analysis")
            except ImportError:
                self._enable_cache = False
                self._get_config_cached = None
        self.config = self._load_config(config_path)

    def _load_config(self, path: str) -> Dict:
        # 优先用缓存读取，多模块共享同一配置文件时只读一次磁盘
        if self._get_config_cached is not None:
            data = self._get_config_cached(path)
            if data:
                return data
        if not os.path.exists(path):
            return {"audio": {"default_sample_rate": 22050}}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {"audio": {"default_sample_rate": 22050}}

    def _ensure_librosa(self):
        if self._librosa is None:
            try:
                import librosa
                self._librosa = librosa
            except ImportError:
                raise ImportError("librosa 未安装，请执行: pip install librosa")
        return self._librosa

    def _ensure_scipy(self):
        if self._scipy is None:
            try:
                import scipy
                self._scipy = scipy
            except ImportError:
                raise ImportError("scipy 未安装，请执行: pip install scipy")
        return self._scipy

    def analyze_audio(self, audio_path: str) -> Dict:
        if not os.path.exists(audio_path):
            return {"success": False, "error": "音频文件不存在"}

        # 缓存命中检查：音频分析（librosa STFT/beat_track 等）是 CPU 密集型操作
        if self._enable_cache and self._disk_cache is not None and self._fingerprint is not None:
            cache_key = self._fingerprint(audio_path, str(self.config.get("audio", {}).get("default_sample_rate", 22050)))
            cached = self._disk_cache.get(cache_key, source_path=audio_path)
            if cached is not None:
                cached = dict(cached)
                cached["_from_cache"] = True
                return cached

        try:
            librosa = self._ensure_librosa()
            y, sr = librosa.load(audio_path, sr=self.config["audio"]["default_sample_rate"])
            duration = librosa.get_duration(y=y, sr=sr)

            tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
            # 兼容不同版本librosa: tempo可能是numpy数组或标量
            if hasattr(tempo, '__len__'):
                tempo = float(tempo[0]) if len(tempo) > 0 else 120.0
            else:
                tempo = float(tempo)
            # beat_frames可能是numpy数组
            if hasattr(beat_frames, '__len__'):
                beat_frames = np.array(beat_frames)
            onset_frames = librosa.onset.onset_detect(y=y, sr=sr, units='frames')
            if hasattr(onset_frames, '__len__'):
                onset_frames = np.array(onset_frames)
            
            chroma = librosa.feature.chroma_stft(y=y, sr=sr)
            mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=20)
            spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
            spectral_bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr)
            spectral_rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)
            zero_crossing_rate = librosa.feature.zero_crossing_rate(y)
            rms = librosa.feature.rms(y=y)

            energy = float(rms.mean())
            loudness = float(20 * math.log10(energy + 1e-10))
            avg_spectral_centroid = float(spectral_centroid.mean())
            avg_spectral_bandwidth = float(spectral_bandwidth.mean())
            avg_spectral_rolloff = float(spectral_rolloff.mean())
            avg_zcr = float(zero_crossing_rate.mean())

            chroma_avg = chroma.mean(axis=1).tolist()
            mfccs_avg = mfccs.mean(axis=1).tolist()

            key, mode = self._detect_key(chroma_avg)
            mood, mood_score = self._infer_mood_enhanced(tempo, energy, avg_spectral_centroid, avg_zcr, mfccs_avg)
            genre = self._infer_genre_enhanced(tempo, energy, key, avg_zcr)

            beat_times = librosa.frames_to_time(beat_frames, sr=sr).tolist()
            onset_times = librosa.frames_to_time(onset_frames, sr=sr).tolist()
            downbeat_times = self._detect_downbeats(beat_times, tempo)

            energy_curve = self._analyze_energy_curve(rms, sr)
            segments = self._detect_segments_enhanced(y, sr, beat_times, energy_curve, chroma)
            chords = self._detect_chords(chroma, sr)

            danceability = self._calculate_danceability(tempo, energy, avg_zcr)
            valence = self._calculate_valence(chroma_avg, tempo)
            arousal = self._calculate_arousal(tempo, energy, avg_spectral_centroid)

            features = AudioFeaturesEnhanced(
                bpm=float(tempo),
                tempo=float(tempo),
                key=key,
                mode=mode,
                duration=duration,
                loudness=loudness,
                spectral_centroid=avg_spectral_centroid,
                spectral_bandwidth=avg_spectral_bandwidth,
                spectral_rolloff=avg_spectral_rolloff,
                zero_crossing_rate=avg_zcr,
                mfccs=mfccs_avg,
                chroma=chroma_avg,
                energy=energy,
                energy_curve=energy_curve,
                mood=mood,
                mood_score=mood_score,
                genre=genre,
                beats=beat_times,
                downbeats=downbeat_times,
                segments=segments,
                chords=chords,
                danceability=danceability,
                valence=valence,
                arousal=arousal
            )

            result = {
                "success": True,
                "features": features.to_dict(),
                "beat_count": len(beat_times),
                "onset_count": len(onset_times),
                "downbeat_count": len(downbeat_times),
                "segment_count": len(segments),
                "audio_path": audio_path,
                "filename": os.path.basename(audio_path)
            }

            # 写入缓存（仅成功结果）
            if self._enable_cache and self._disk_cache is not None:
                try:
                    self._disk_cache.set(cache_key, result, source_path=audio_path)
                except Exception:
                    pass

            return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _detect_key(self, chroma: List[float]) -> Tuple[str, str]:
        key_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        mode_names = ['major', 'minor']

        chroma_sum = sum(chroma)
        if chroma_sum == 0:
            return "Unknown", "unknown"

        normalized = [c / chroma_sum for c in chroma]

        key_index = normalized.index(max(normalized))
        key = key_names[key_index]

        mode_score = self._calculate_mode_score(chroma)
        mode = mode_names[0] if mode_score > 0 else mode_names[1]

        return key, mode

    def _calculate_mode_score(self, chroma: List[float]) -> float:
        major_pattern = [1, 0.6, 0.8, 0.6, 1, 0.8, 0.6, 1, 0.8, 0.6, 0.8, 0.6]
        minor_pattern = [1, 0.8, 0.6, 0.8, 0.6, 1, 0.6, 1, 0.8, 0.6, 0.8, 0.6]

        major_score = sum(c * p for c, p in zip(chroma, major_pattern))
        minor_score = sum(c * p for c, p in zip(chroma, minor_pattern))

        return major_score - minor_score

    def _infer_mood_enhanced(self, tempo: float, energy: float, spectral_centroid: float, zcr: float, mfccs: List[float]) -> Tuple[str, float]:
        mood_scores = {}

        mfcc_mean = np.mean(mfccs) if mfccs else 0

        mood_scores["excited"] = (
            min(tempo / 140, 1.0) * 0.25 +
            min(energy / 0.3, 1.0) * 0.25 +
            min(spectral_centroid / 2500, 1.0) * 0.2 +
            min(zcr / 0.15, 1.0) * 0.15 +
            max(0, 1 - mfcc_mean / 50) * 0.15
        )

        mood_scores["calm"] = (
            max(1 - tempo / 110, 0) * 0.3 +
            max(1 - energy / 0.2, 0) * 0.3 +
            max(1 - spectral_centroid / 1800, 0) * 0.2 +
            max(1 - zcr / 0.1, 0) * 0.1 +
            min(mfcc_mean / 80, 1.0) * 0.1
        )

        mood_scores["happy"] = (
            min(tempo / 130, 1.0) * 0.2 +
            min(energy / 0.25, 1.0) * 0.3 +
            min(spectral_centroid / 2000, 1.0) * 0.25 +
            max(0, 1 - abs(mfcc_mean) / 60) * 0.25
        )

        mood_scores["sad"] = (
            max(1 - tempo / 90, 0) * 0.25 +
            max(1 - energy / 0.15, 0) * 0.3 +
            max(1 - spectral_centroid / 1200, 0) * 0.25 +
            max(mfcc_mean / 100, 0) * 0.2
        )

        mood_scores["epic"] = (
            min(tempo / 100, 1.0) * 0.2 +
            min(energy / 0.4, 1.0) * 0.35 +
            min(spectral_centroid / 2500, 1.0) * 0.25 +
            max(0, 1 - zcr / 0.12) * 0.2
        )

        mood_scores["mysterious"] = (
            max(1 - tempo / 80, 0) * 0.25 +
            max(1 - energy / 0.18, 0) * 0.25 +
            min(spectral_centroid / 1000, 1.0) * 0.3 +
            max(zcr / 0.08, 0) * 0.2
        )

        mood_scores["romantic"] = (
            min(tempo / 95, 1.0) * 0.2 +
            min(energy / 0.18, 1.0) * 0.25 +
            min(spectral_centroid / 1500, 1.0) * 0.3 +
            min(abs(mfcc_mean) / 40, 1.0) * 0.25
        )

        best_mood = max(mood_scores, key=mood_scores.get)
        return best_mood, mood_scores[best_mood]

    def _infer_genre_enhanced(self, tempo: float, energy: float, key: str, zcr: float) -> str:
        if tempo > 150 and energy > 0.28 and zcr > 0.12:
            return "hardcore"
        elif tempo > 140 and energy > 0.25:
            return "rock"
        elif tempo > 125 and energy > 0.22 and zcr > 0.08:
            return "pop"
        elif tempo > 110 and energy > 0.18:
            return "electronic"
        elif tempo > 100 and energy > 0.15 and zcr > 0.06:
            return "dance"
        elif tempo < 75 and energy < 0.12:
            return "ambient"
        elif tempo < 85 and energy < 0.15:
            return "classical"
        elif 85 <= tempo <= 105 and 0.12 <= energy <= 0.22:
            return "jazz"
        elif tempo > 95 and energy > 0.35:
            return "epic"
        elif tempo < 80 and energy < 0.18 and zcr < 0.05:
            return "lofi"
        elif 90 <= tempo <= 110 and energy > 0.2:
            return "hiphop"
        else:
            return "other"

    def _detect_downbeats(self, beat_times: List[float], tempo: float) -> List[float]:
        if len(beat_times) < 4:
            return []

        beats_per_measure = 4
        seconds_per_beat = 60 / tempo
        measure_duration = seconds_per_beat * beats_per_measure

        downbeats = []
        current_time = 0

        for i, beat_time in enumerate(beat_times):
            if abs(beat_time - current_time) < seconds_per_beat * 0.5:
                downbeats.append(beat_time)
                current_time += measure_duration

        return downbeats

    def _analyze_energy_curve(self, rms: np.ndarray, sr: int) -> Dict:
        times = self._librosa.frames_to_time(range(len(rms[0])), sr=sr)
        values = [float(v) for v in rms[0]]

        peaks = []
        threshold = np.mean(values) + np.std(values) * 0.8
        max_val = max(values) if values else 1.0

        for i in range(1, len(values) - 1):
            if values[i] > values[i-1] and values[i] > values[i+1] and values[i] > threshold:
                peaks.append({
                    "time": round(float(times[i]), 3),
                    "energy": round(float(values[i]), 4),
                    "intensity": min(values[i] / max_val, 1.0)
                })

        peaks_sorted = sorted(peaks, key=lambda x: -x["energy"])[:20]

        return {
            "times": [float(t) for t in times],
            "values": values,
            "peaks": peaks_sorted,
            "avg_energy": float(np.mean(values)),
            "max_energy": float(np.max(values)),
            "min_energy": float(np.min(values)),
            "energy_range": float(np.max(values) - np.min(values))
        }

    def _detect_segments_enhanced(self, y: np.ndarray, sr: int, beat_times: List[float], energy_curve: Dict, chroma: np.ndarray = None) -> List[AudioSegment]:
        librosa = self._ensure_librosa()

        # 复用上游已计算的 chroma，避免重复 STFT（CPU 密集型）
        if chroma is None:
            chroma = librosa.feature.chroma_stft(y=y, sr=sr)

        try:
            segment_boundaries = librosa.segment.agglomerative(chroma, k=8)
            segment_times = librosa.frames_to_time(segment_boundaries, sr=sr)
        except:
            segment_times = np.linspace(0, librosa.get_duration(y=y, sr=sr), 8)

        segments = []
        values = np.array(energy_curve["values"])
        times = np.array(energy_curve["times"])

        for i in range(len(segment_times) - 1):
            start_time = float(segment_times[i])
            end_time = float(segment_times[i + 1])
            duration = end_time - start_time

            mask = (times >= start_time) & (times <= end_time)
            segment_energy = values[mask]
            avg_energy = float(np.mean(segment_energy)) if len(segment_energy) > 0 else 0
            energy_variance = float(np.std(segment_energy)) if len(segment_energy) > 0 else 0

            segment_beats = [bt for bt in beat_times if start_time <= bt <= end_time]
            beat_count = len(segment_beats)

            segment_type = self._classify_segment_type(i, len(segment_times), avg_energy, beat_count)

            segments.append(AudioSegment(
                start_time=start_time,
                end_time=end_time,
                duration=duration,
                segment_type=segment_type,
                beat_count=beat_count,
                avg_energy=avg_energy,
                energy_variance=energy_variance
            ))

        return segments

    def _classify_segment_type(self, index: int, total: int, avg_energy: float, beat_count: int) -> str:
        if index == 0:
            if avg_energy < 0.1:
                return "intro_silent"
            elif avg_energy < 0.2:
                return "intro_build"
            else:
                return "intro_immediate"
        elif index == total - 2:
            if avg_energy < 0.15:
                return "outro_fade"
            else:
                return "outro_climax"
        elif index == total - 1:
            return "ending"
        elif beat_count >= 8 and avg_energy > 0.25:
            return "chorus"
        elif beat_count >= 6 and avg_energy > 0.18:
            return "verse"
        elif beat_count >= 4 and avg_energy > 0.15:
            return "pre_chorus"
        elif avg_energy < 0.12:
            return "bridge"
        else:
            return "transition"

    def _detect_chords(self, chroma: np.ndarray, sr: int) -> List[Dict]:
        chord_names = [
            "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B",
            "Cm", "C#m", "Dm", "D#m", "Em", "Fm", "F#m", "Gm", "G#m", "Am", "A#m", "Bm"
        ]

        chord_patterns = {
            "C": [1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0],
            "C#": [0, 1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0],
            "D": [0, 0, 1, 0, 0, 0, 1, 0, 0, 1, 0, 0],
            "D#": [0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 1, 0],
            "E": [0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 1],
            "F": [1, 0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0],
            "F#": [0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 1, 0],
            "G": [0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 1],
            "G#": [0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0],
            "A": [0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0],
            "A#": [0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0],
            "B": [0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
            "Cm": [1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0],
            "C#m": [0, 1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0],
            "Dm": [0, 0, 1, 0, 0, 1, 0, 0, 0, 1, 0, 0],
            "D#m": [0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 1, 0],
            "Em": [0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 1],
            "Fm": [1, 0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0],
            "F#m": [0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 1, 0],
            "Gm": [0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 1, 0],
            "G#m": [0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 1],
            "Am": [0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0],
            "A#m": [0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0],
            "Bm": [0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
        }

        frame_times = self._librosa.frames_to_time(range(chroma.shape[1]), sr=sr)
        chords = []
        window_size = 10

        for i in range(0, chroma.shape[1], window_size):
            window_end = min(i + window_size, chroma.shape[1])
            window_chroma = chroma[:, i:window_end].mean(axis=1)
            
            chroma_sum = window_chroma.sum()
            if chroma_sum < 0.1:
                continue

            normalized = window_chroma / chroma_sum

            best_chord = None
            best_score = 0

            for chord, pattern in chord_patterns.items():
                score = sum(n * p for n, p in zip(normalized, pattern))
                if score > best_score:
                    best_score = score
                    best_chord = chord

            if best_chord and best_score > 0.4:
                chords.append({
                    "chord": best_chord,
                    "time": round(float(frame_times[i]), 3),
                    "confidence": round(best_score, 3)
                })

        return chords

    def _calculate_danceability(self, tempo: float, energy: float, zcr: float) -> float:
        return (
            min(tempo / 120, 1.0) * 0.3 +
            min(energy / 0.25, 1.0) * 0.3 +
            min(zcr / 0.1, 1.0) * 0.2 +
            max(0, 1 - abs(tempo - 100) / 60) * 0.2
        )

    def _calculate_valence(self, chroma: List[float], tempo: float) -> float:
        bright_keys = [0, 4, 7, 9, 11]
        dark_keys = [2, 3, 5, 8, 10]

        bright_score = sum(chroma[i] for i in bright_keys)
        dark_score = sum(chroma[i] for i in dark_keys)

        key_balance = (bright_score - dark_score) / max(bright_score + dark_score, 0.1)

        return (
            (key_balance + 1) / 2 * 0.5 +
            min(tempo / 130, 1.0) * 0.3 +
            max(0, 1 - abs(tempo - 110) / 80) * 0.2
        )

    def _calculate_arousal(self, tempo: float, energy: float, spectral_centroid: float) -> float:
        return (
            min(tempo / 140, 1.0) * 0.3 +
            min(energy / 0.3, 1.0) * 0.35 +
            min(spectral_centroid / 2500, 1.0) * 0.25 +
            max(0, 1 - abs(tempo - 120) / 80) * 0.1
        )

    def generate_beat_map(self, audio_path: str) -> Dict:
        analysis = self.analyze_audio(audio_path)
        if not analysis["success"]:
            return analysis

        features = analysis["features"]
        
        return {
            "success": True,
            "beat_times": features["beats"],
            "beat_count": features["beat_count"],
            "duration": features["duration"],
            "bpm": features["bpm"],
            "downbeats": features["downbeats"],
            "downbeat_count": len(features["downbeats"]),
            "segments": features["segments"],
            "energy_curve": features["energy_curve"],
            "features": features
        }

    def find_best_bgm_match(self, target_features: Dict, bgm_directory: str, max_results: int = 5) -> List[Dict]:
        if not os.path.exists(bgm_directory):
            return []

        matches = []
        audio_extensions = ["mp3", "m4a", "wav", "flac", "ogg"]

        for root, dirs, files in os.walk(bgm_directory):
            for file in files:
                ext = file.split(".")[-1].lower()
                if ext in audio_extensions:
                    full_path = os.path.join(root, file)
                    analysis = self.analyze_audio(full_path)
                    
                    if analysis["success"]:
                        features = analysis["features"]
                        similarity = self._calculate_similarity_enhanced(target_features, features)
                        
                        matches.append({
                            "name": file,
                            "path": full_path,
                            "features": features,
                            "similarity": similarity,
                            "duration": features["duration"]
                        })

        return sorted(matches, key=lambda x: x["similarity"], reverse=True)[:max_results]

    def _calculate_similarity_enhanced(self, target: Dict, candidate: Dict) -> float:
        score = 0.0

        if "tempo" in target and "tempo" in candidate:
            tempo_diff = abs(target["tempo"] - candidate["tempo"])
            score += max(0, 1 - tempo_diff / 40) * 0.25

        if "mood" in target and "mood" in candidate:
            if target["mood"] == candidate["mood"]:
                score += 0.25
            else:
                mood_similarity = self._calculate_mood_similarity(target["mood"], candidate["mood"])
                score += mood_similarity * 0.15

        if "duration" in target and "duration" in candidate:
            duration_diff = abs(target["duration"] - candidate["duration"])
            max_duration = max(target["duration"], candidate["duration"])
            score += max(0, 1 - duration_diff / max_duration) * 0.15

        if "energy" in target and "energy" in candidate:
            energy_diff = abs(target["energy"] - candidate["energy"])
            score += max(0, 1 - energy_diff / 0.4) * 0.1

        if "key" in target and "key" in candidate:
            if target["key"] == candidate["key"]:
                score += 0.1

        if "danceability" in target and "danceability" in candidate:
            dance_diff = abs(target["danceability"] - candidate["danceability"])
            score += max(0, 1 - dance_diff) * 0.1

        if "genre" in target and "genre" in candidate:
            if target["genre"] == candidate["genre"]:
                score += 0.05

        return round(score, 3)

    def _calculate_mood_similarity(self, mood1: str, mood2: str) -> float:
        mood_groups = {
            "excited": ["excited", "happy", "epic"],
            "calm": ["calm", "romantic"],
            "sad": ["sad", "mysterious"]
        }

        for group, moods in mood_groups.items():
            if mood1 in moods and mood2 in moods:
                return 0.7
            elif mood1 in moods or mood2 in moods:
                return 0.3

        return 0.5

    def test_librosa(self) -> Dict:
        librosa_available = False
        scipy_available = False
        
        try:
            import librosa
            librosa_available = True
        except:
            pass
        
        try:
            import scipy
            scipy_available = True
        except:
            pass
        
        return {
            "librosa_available": librosa_available,
            "scipy_available": scipy_available
        }


def main():
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--json-input":
        try:
            if len(sys.argv) > 2:
                input_data = sys.argv[2]
            else:
                input_data = sys.stdin.read()
            
            if input_data:
                request = json.loads(input_data)
                analyzer = EnhancedAudioAnalyzer()
                
                func_name = request.get("func")
                params = request.get("params", {})
                
                func_map = {
                    "analyze_audio": analyzer.analyze_audio,
                    "find_best_bgm_match": analyzer.find_best_bgm_match,
                    "generate_beat_map": analyzer.generate_beat_map,
                    "test_librosa": analyzer.test_librosa
                }
                
                if func_name in func_map:
                    result = func_map[func_name](**params)
                else:
                    result = {"success": False, "error": f"Unknown function: {func_name}"}
                
                print(json.dumps(result, ensure_ascii=False, indent=2))
        except Exception as e:
            print(json.dumps({"success": False, "error": str(e)}))
        return
    
    analyzer = EnhancedAudioAnalyzer()
    
    bgm_dir = r"D:\AE-Work\音频素材库\BGM"
    
    if os.path.exists(bgm_dir):
        print("分析 BGM 库...")
        for f in os.listdir(bgm_dir):
            if f.endswith((".mp3", ".m4a")):
                full_path = os.path.join(bgm_dir, f)
                print(f"\n分析: {f}")
                result = analyzer.analyze_audio(full_path)
                if result["success"]:
                    features = result["features"]
                    print(f"  BPM: {features['bpm']}")
                    print(f"  情绪: {features['mood']} ({features['mood_score']:.2f})")
                    print(f"  曲风: {features['genre']}")
                    print(f"  调性: {features['key']} {features['mode']}")
                    print(f"  舞池度: {features['danceability']:.2f}")
                    print(f"  情感值: {features['valence']:.2f}")
                    print(f"  兴奋度: {features['arousal']:.2f}")
                    print(f"  节拍数: {features['beat_count']}")
                    print(f"  段落数: {len(features['segments'])}")
                else:
                    print(f"  分析失败: {result['error']}")
    else:
        print(f"BGM目录不存在: {bgm_dir}")


if __name__ == "__main__":
    main()