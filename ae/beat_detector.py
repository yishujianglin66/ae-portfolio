"""
Beat Detector — 音频节拍检测与节奏分析引擎
============================================
基于 librosa (https://github.com/librosa/librosa) 和
madmom (https://github.com/CPJKU/madmom) 开源项目，
提供 BPM 检测、节拍追踪、音乐结构分析能力。

核心能力:
- BPM/节拍检测 (librosa beat tracking)
- 实时节拍追踪 (madmom RNNBeatProcessor)
- 音乐段落检测 (前奏/主歌/副歌/间奏/尾奏)
- 能量/情绪曲线分析
- 节奏自适应剪辑建议
- Onset 检测 (音符起始点)

依赖:
    pip install librosa madmom soundfile numpy scipy

用法:
    detector = BeatDetector()
    beats = detector.detect_beats("music.mp3")
    # beats = [0.23, 0.69, 1.15, 1.62, ...]
    structure = detector.analyze_structure("music.mp3")
"""

from __future__ import annotations

import json
import math
import os
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# 延迟导入的依赖（在实际使用时导入）
# import numpy as np
# import librosa

sys.path.insert(0, str(Path(__file__).parent.parent))


# ================================================================
#  数据结构
# ================================================================
@dataclass
class BeatInfo:
    """节拍信息"""
    time: float           # 节拍时间点（秒）
    beat_index: int       # 节拍序号（从1开始）
    bar: int              # 小节序号
    beat_in_bar: int      # 小节内第几拍
    strength: float = 1.0 # 节拍强度
    is_downbeat: bool = False  # 是否为强拍（每小节第一拍）


@dataclass
class MusicStructure:
    """音乐结构分析结果"""
    sections: list[dict[str, Any]] = field(default_factory=list)  # [{label, start, end, confidence}]
    key: str = "unknown"          # 调性
    tempo: float | None = None # BPM
    time_signature: str = "4/4"   # 拍号
    energy_curve: list[float] = field(default_factory=list)  # 能量曲线
    climax_regions: list[dict] = field(default_factory=list) # 高潮段
    quiet_regions: list[dict] = field(default_factory=list)  # 安静段


@dataclass
class ClipSuggestion:
    """剪辑建议"""
    start_beat: BeatInfo
    end_beat: BeatInfo
    duration: float
    cut_type: str          # "on_beat" | "off_beat" | "fill"
    energy_level: float
    suitable_effects: list[str] = field(default_factory=list)


# ================================================================
#  节拍检测引擎
# ================================================================
class BeatDetector:
    """基于 librosa + madmom 的节拍检测器"""

    def __init__(
        self,
        sample_rate: int = 22050,
        hop_length: int = 512,
        bpm_range: tuple[float, float] = (60, 200),
        use_madmom: bool = True,
    ):
        self.sr = sample_rate
        self.hop_length = hop_length
        self.bpm_range = bpm_range
        self.use_madmom = use_madmom
        self._madmom_available = self._check_madmom()

    @staticmethod
    def _check_madmom() -> bool:
        try:
            import madmom
            return True
        except ImportError:
            return False

    def detect_bpm(self, audio_path: str) -> tuple[float, float]:
        """
        检测音频 BPM 和置信度。

        Returns:
            (bpm, confidence) — 节拍数和置信度 (0~1)
        """
        import librosa
        import numpy as np

        y, sr = librosa.load(audio_path, sr=self.sr)

        # 使用多方法交叉验证
        tempo_beats, _ = librosa.beat.beat_track(y=y, sr=sr)
        # librosa 0.11+ 可能返回数组，取第一个元素
        if hasattr(tempo_beats, '__len__'):
            tempo_beats = tempo_beats[0] if len(tempo_beats) > 0 else 120.0

        # 使用 onset 强度估计置信度
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        pulse = librosa.beat.plp(onset_envelope=onset_env, sr=sr, tempo_min=self.bpm_range[0], tempo_max=self.bpm_range[1])
        beats_plp = np.flatnonzero(librosa.util.localmax(pulse))

        if len(beats_plp) > 0:
            durations = np.diff(beats_plp * self.hop_length / sr)
            if len(durations) > 0:
                std_dev = np.std(durations) / np.mean(durations) if np.mean(durations) > 0 else 1.0
                confidence = 1.0 / (1.0 + std_dev)
            else:
                confidence = 0.5
        else:
            confidence = 0.3

        return round(float(tempo_beats), 1), round(float(confidence), 3)

    def detect_beats(self, audio_path: str) -> list[BeatInfo]:
        """
        检测所有节拍位置。

        Returns:
            节拍信息列表（按时间排序）
        """
        import librosa
        import numpy as np

        y, sr = librosa.load(audio_path, sr=self.sr)

        # Librosa 节拍追踪
        tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
        beat_times = librosa.frames_to_time(beat_frames, sr=sr, hop_length=self.hop_length)

        # Onset 强度（用于节拍强度）
        onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=self.hop_length)
        onset_times = librosa.times_like(onset_env, sr=sr, hop_length=self.hop_length)

        # 构建 BeatInfo 列表
        beats = []
        time_signature = 4  # 默认 4/4

        for i, bt in enumerate(beat_times):
            # 计算在 onset_env 中的对应强度
            onset_idx = np.argmin(np.abs(onset_times - bt))
            if onset_idx < len(onset_env):
                strength = float(onset_env[onset_idx])
            else:
                strength = 1.0

            # 小节省略计算
            bar = i // time_signature + 1
            beat_in_bar = i % time_signature + 1
            is_downbeat = beat_in_bar == 1

            beats.append(BeatInfo(
                time=round(float(bt), 4),
                beat_index=i + 1,
                bar=bar,
                beat_in_bar=beat_in_bar,
                strength=round(strength, 4),
                is_downbeat=is_downbeat,
            ))

        return beats

    def detect_beats_madmom(self, audio_path: str) -> list[BeatInfo]:
        """
        使用 madmom RNN 进行高精度节拍追踪（需要 madmom 库）。

        madmom 使用双向 LSTM + 动态贝叶斯网络，精度显著高于 librosa。
        """
        if not self._madmom_available:
            return self.detect_beats(audio_path)

        try:
            import numpy as np
            from madmom.features.beats import DBNBeatTrackingProcessor, RNNBeatProcessor

            # RNN 节拍激活函数
            beat_processor = RNNBeatProcessor()(audio_path)

            # DBN 动态贝叶斯网络追踪
            dbn_processor = DBNBeatTrackingProcessor(fps=100)
            beat_times = dbn_processor(beat_processor)

            beats = []
            for i, bt in enumerate(beat_times):
                bar = i // 4 + 1
                beat_in_bar = i % 4 + 1
                beats.append(BeatInfo(
                    time=round(float(bt), 4),
                    beat_index=i + 1,
                    bar=bar,
                    beat_in_bar=beat_in_bar,
                    strength=1.0,
                    is_downbeat=beat_in_bar == 1,
                ))
            return beats

        except Exception as e:
            print(f"[BeatDetector] madmom error: {e}, falling back to librosa")
            return self.detect_beats(audio_path)

    def analyze_structure(self, audio_path: str) -> MusicStructure:
        """
        分析音乐结构：段落、高潮、安静段。

        Returns:
            MusicStructure 对象
        """
        import librosa
        import numpy as np

        y, sr = librosa.load(audio_path, sr=self.sr)
        tempo, _ = self.detect_bpm(audio_path)

        structure = MusicStructure(tempo=tempo)

        # --- 频谱分析 ---
        S = np.abs(librosa.stft(y, n_fft=2048, hop_length=self.hop_length))
        freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)

        # --- 能量曲线 ---
        rms = librosa.feature.rms(S=S)[0]
        rms_times = librosa.times_like(rms, sr=sr, hop_length=self.hop_length)
        structure.energy_curve = [round(float(v), 4) for v in rms]

        # --- 频谱对比度 ---
        contrast = librosa.feature.spectral_contrast(S=S, sr=sr)
        contrast_mean = np.mean(contrast, axis=0)

        # --- MFCC ---
        mfcc = librosa.feature.mfcc(S=librosa.amplitude_to_db(S, ref=np.max), sr=sr, n_mfcc=13)
        mfcc_delta = librosa.feature.delta(mfcc)

        # --- 段落分割 ---
        # 基于 MFCC 变化检测段落边界
        mfcc_diff = np.mean(np.abs(mfcc_delta), axis=0)
        mfcc_diff_smooth = np.convolve(mfcc_diff, np.ones(10) / 10, mode='same')

        # 使用 RMS 能量变化 + MFCC 变化找段落边界
        rms_diff = np.abs(np.diff(rms, prepend=rms[0]))
        combined = (mfcc_diff_smooth / (np.max(mfcc_diff_smooth) + 1e-6) +
                    rms_diff / (np.max(rms_diff) + 1e-6))

        threshold = np.median(combined) * 2.5
        boundaries = np.where(combined > threshold)[0]
        boundaries = boundaries[boundaries > 5]  # 过滤太近的边界
        boundaries = boundaries[np.diff(boundaries, prepend=0) > 20]  # 合并太近的

        # --- 高潮/安静段识别 ---
        rms_percentile_80 = np.percentile(rms, 80)
        rms_percentile_20 = np.percentile(rms, 20)

        # 临时高潮段
        climax_mask = rms > rms_percentile_80
        quiet_mask = rms < rms_percentile_20

        # 合并相邻段
        climax_regions = self._merge_regions(rms_times, climax_mask)
        quiet_regions = self._merge_regions(rms_times, quiet_mask)

        structure.climax_regions = [{"start": round(s, 3), "end": round(e, 3), "duration": round(e - s, 3)} for s, e in climax_regions]
        structure.quiet_regions = [{"start": round(s, 3), "end": round(e, 3), "duration": round(e - s, 3)} for s, e in quiet_regions]

        # --- 段落标注 ---
        section_names = ["intro", "verse", "chorus", "bridge", "outro"]  # 简化模式
        boundary_times = [rms_times[min(b, len(rms_times) - 1)] for b in boundaries] if len(boundaries) > 0 else [0, len(rms_times) * self.hop_length / sr]

        # 简化段落标注
        sections = []
        prev_t = 0
        for i, t in enumerate(boundary_times):
            section_rms = rms[int(prev_t / (self.hop_length / sr)):int(t / (self.hop_length / sr)) + 1]
            avg_energy = np.mean(section_rms) if len(section_rms) > 0 else 0
            label = "chorus" if avg_energy > rms_percentile_80 else ("verse" if avg_energy > rms_percentile_20 else "quiet")
            sections.append({
                "label": label,
                "start": round(prev_t, 3),
                "end": round(float(t), 3),
                "duration": round(float(t) - prev_t, 3),
                "confidence": 0.7 if len(section_rms) > 30 else 0.4,
            })
            prev_t = t

        # 最后一段
        if prev_t < len(y) / sr:
            section_rms = rms[int(prev_t / (self.hop_length / sr)):]
            avg_energy = np.mean(section_rms) if len(section_rms) > 0 else 0
            label = "outro" if prev_t > len(y) / sr * 0.7 else "chorus" if avg_energy > rms_percentile_80 else "verse"
            sections.append({
                "label": label,
                "start": round(prev_t, 3),
                "end": round(len(y) / sr, 3),
                "duration": round(len(y) / sr - prev_t, 3),
                "confidence": 0.6,
            })

        structure.sections = sections

        # --- 调性检测 ---
        try:
            chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
            chroma_mean = np.mean(chroma, axis=1)
            key_idx = np.argmax(chroma_mean)
            notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
            structure.key = notes[key_idx]
        except Exception:
            structure.key = "unknown"

        return structure

    def generate_clip_suggestions(
        self,
        audio_path: str,
        target_duration: float | None = None,
        min_clip_duration: float = 0.5,
        max_clip_duration: float = 5.0,
    ) -> list[ClipSuggestion]:
        """
        根据节拍生成剪辑建议 — 每个剪辑点对齐到强拍。

        Args:
            audio_path: 音频路径
            target_duration: 目标总时长（默认使用音频全长）
            min_clip_duration: 最小剪辑段时长
            max_clip_duration: 最大剪辑段时长

        Returns:
            剪辑建议列表
        """
        import librosa
        import numpy as np

        beats = self.detect_beats(audio_path)
        if len(beats) < 4:
            return []

        y, sr = librosa.load(audio_path, sr=self.sr)
        total_duration = len(y) / sr
        effective_duration = target_duration or total_duration

        # 只使用强拍（每小节第一拍）作为剪辑点
        downbeats = [b for b in beats if b.is_downbeat]

        suggestions = []
        i = 0

        while i < len(downbeats) - 1:
            start = downbeats[i]
            j = i + 1

            # 找到合适的结束强拍
            while j < len(downbeats) and (downbeats[j].time - start.time) < min_clip_duration:
                j += 1

            if j >= len(downbeats):
                break

            end = downbeats[j]
            dur = end.time - start.time

            # 如果超过最大时长，回退
            while dur > max_clip_duration and j > i + 1:
                j -= 1
                end = downbeats[j]
                dur = end.time - start.time

            if dur < min_clip_duration:
                i += 1
                continue

            # 计算能量水平
            start_sample = int(start.time * sr)
            end_sample = int(end.time * sr)
            segment = y[start_sample:end_sample]
            energy = np.sqrt(np.mean(segment ** 2)) if len(segment) > 0 else 0

            # 剪辑类型
            if energy > 0.1:
                cut_type = "on_beat"
                effects = ["smooth_fade", "motion_blur"]
            elif start.beat_in_bar == 4:
                cut_type = "fill"
                effects = ["speed_ramp", "glitch"]
            else:
                cut_type = "off_beat"
                effects = ["crossfade"]

            suggestions.append(ClipSuggestion(
                start_beat=start,
                end_beat=end,
                duration=round(dur, 3),
                cut_type=cut_type,
                energy_level=round(float(energy), 4),
                suitable_effects=effects,
            ))

            i = j

            # 检查是否超出目标时长
            if start.time > effective_duration:
                break

        return suggestions

    def _merge_regions(self, times, mask, min_gap: int = 3) -> list[tuple[float, float]]:
        """合并相邻区域"""
        regions = []
        start = None
        for i, val in enumerate(mask):
            if val and start is None:
                start = i
            elif not val and start is not None:
                if i - start >= min_gap:
                    regions.append((times[start], times[min(i - 1, len(times) - 1)]))
                start = None
        if start is not None and len(times) - start >= min_gap:
            regions.append((times[start], times[-1]))
        return regions

    def detect_onsets(self, audio_path: str) -> list[float]:
        """检测音符起始点（Onset Detection）"""
        import librosa

        y, sr = librosa.load(audio_path, sr=self.sr)
        onset_frames = librosa.onset.onset_detect(
            y=y, sr=sr, units='time',
            hop_length=self.hop_length,
            backtrack=True,
        )
        return [round(float(t), 4) for t in onset_frames]

    def export_beat_markers_json(self, audio_path: str, output_path: str) -> str:
        """导出节拍标记为 JSON（对接 PR MCP Marker 接口）"""
        beats = self.detect_beats(audio_path)
        structure = self.analyze_structure(audio_path)

        markers = []
        for b in beats:
            marker = {
                "time": b.time,
                "name": f"Beat_{b.beat_index}" if not b.is_downbeat else f"Bar_{b.bar}_Downbeat",
                "color": "red" if b.is_downbeat else "white",
                "type": "beat",
                "beat_index": b.beat_index,
                "bar": b.bar,
                "beat_in_bar": b.beat_in_bar,
                "strength": b.strength,
                "is_downbeat": b.is_downbeat,
            }
            markers.append(marker)

        # 添加段落标记
        for i, sec in enumerate(structure.sections):
            markers.append({
                "time": sec["start"],
                "name": f"Section_{i}_{sec['label']}",
                "color": "blue",
                "type": "section",
                "label": sec["label"],
                "duration": sec["duration"],
            })

        output = {
            "source": str(Path(audio_path).absolute()),
            "bpm": structure.tempo,
            "key": structure.key,
            "total_duration": beats[-1].time if beats else 0,
            "beat_count": len(beats),
            "markers": sorted(markers, key=lambda m: m["time"]),
            "climax_regions": structure.climax_regions,
            "quiet_regions": structure.quiet_regions,
        }

        Path(output_path).write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8')
        return output_path


__all__ = [
    "BeatDetector",
    "BeatInfo",
    "MusicStructure",
    "ClipSuggestion",
]
