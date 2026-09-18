"""
Audio Processor — 音频处理与淡入淡出自动匹配引擎
=================================================
提供音频处理全流程能力：混音、淡入淡出、音量均衡、背景音乐自适应。

核心能力:
- 智能 BGM 音量自适应（根据人声/主音频动态调整）
- 音频淡入淡出自动匹配（转场对应音频平滑过渡）
- 多音轨混音
- 音频标准化/均衡化
- 生成 AE/PR 音频关键帧数据

依赖:
    pip install librosa soundfile numpy scipy pydub

用法:
    proc = AudioProcessor()
    proc.match_fade_to_transition("video.mp4", transitions=[
        {"time": 2.0, "type": "cut", "duration": 0.3}
    ])
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

sys.path.insert(0, str(Path(__file__).parent.parent))


# ================================================================
#  数据结构
# ================================================================
@dataclass
class AudioFade:
    """音频淡入淡出定义"""
    time: float                      # 淡入淡出中心时间
    fade_in_duration: float          # 淡入时长（秒）
    fade_out_duration: float         # 淡出时长（秒）
    curve_type: str = "linear"       # "linear", "exponential", "logarithmic", "s_curve"
    target_volume_db: float = 0.0    # 目标音量（dB）
    transition_type: str = "crossfade"  # 关联的转场类型


@dataclass
class AudioTrackConfig:
    """音频轨道配置"""
    source_path: str
    volume_db: float = 0.0
    pan: float = 0.0          # -1.0 (左) ~ 1.0 (右)
    muted: bool = False
    effects: list[dict] = field(default_factory=list)
    start_offset: float = 0.0  # 起始偏移（秒）


@dataclass
class AudioMixResult:
    """混音结果"""
    output_path: str
    duration: float
    peak_db: float
    rms_db: float
    loudness_lufs: float
    fades: list[AudioFade]
    tracks: list[AudioTrackConfig]


# ================================================================
#  音频处理器
# ================================================================
class AudioProcessor:
    """音频处理与淡入淡出匹配引擎"""

    def __init__(
        self,
        sample_rate: int = 48000,
        fade_analysis_window: float = 0.5,  # 淡入淡出分析窗口（秒）
        min_fade_duration: float = 0.01,     # 最短淡入淡出时长
        max_fade_duration: float = 2.0,      # 最长淡入淡出时长
    ):
        self.sr = sample_rate
        self.fade_analysis_window = fade_analysis_window
        self.min_fade_duration = min_fade_duration
        self.max_fade_duration = max_fade_duration

    # ================================================================
    #  淡入淡出自动匹配
    # ================================================================
    def match_fade_to_transition(
        self,
        audio_path: str,
        transitions: list[dict[str, Any]],
        video_fps: float = 30.0,
    ) -> list[AudioFade]:
        """
        根据视频转场自动匹配音频淡入淡出。

        Args:
            audio_path: 音频文件路径
            transitions: 视频转场列表 [{"time": 2.0, "type": "cut", "duration": 0.3}, ...]
            video_fps: 视频帧率

        Returns:
            音频淡入淡出列表
        """
        import librosa
        import numpy as np

        y, sr = librosa.load(audio_path, sr=self.sr)

        fades = []
        prev_time = 0.0

        for i, trans in enumerate(transitions):
            trans_time = trans.get("time", 0.0)
            trans_type = trans.get("type", "cut")
            trans_duration = trans.get("duration", 0.3)

            # 根据转场类型确定淡入淡出策略
            if trans_type in ("cut", "hard_cut"):
                # 硬切：短促的音频淡出+淡入（约 10ms）
                fade_out_dur = 0.01
                fade_in_dur = 0.005
                curve = "linear"
            elif trans_type in ("crossfade", "dissolve"):
                # 溶解：渐进式淡出淡入
                fade_out_dur = trans_duration * 0.8
                fade_in_dur = trans_duration * 0.8
                curve = "s_curve"
            elif trans_type in ("glitch", "shake"):
                # 故障：不规则的短淡出淡入
                fade_out_dur = 0.03
                fade_in_dur = 0.02
                curve = "linear"
            elif trans_type in ("wipe_left", "wipe_right", "wipe_up", "wipe_down"):
                # 擦除：方向性淡入淡出
                fade_out_dur = trans_duration * 0.6
                fade_in_dur = trans_duration * 0.6
                curve = "exponential"
            elif trans_type in ("zoom_in", "zoom_out", "push"):
                # 缩放/推拉：S曲线
                fade_out_dur = trans_duration * 0.5
                fade_in_dur = trans_duration * 0.7
                curve = "s_curve"
            else:
                fade_out_dur = trans_duration * 0.5
                fade_in_dur = trans_duration * 0.5
                curve = "logarithmic"

            # 限制时长范围
            fade_out_dur = max(self.min_fade_duration, min(fade_out_dur, self.max_fade_duration))
            fade_in_dur = max(self.min_fade_duration, min(fade_in_dur, self.max_fade_duration))

            # 根据前后音频内容微调
            actual_fade_out = self._adaptive_fade_duration(
                y, sr, trans_time, fade_out_dur, direction="out"
            )
            actual_fade_in = self._adaptive_fade_duration(
                y, sr, trans_time, fade_in_dur, direction="in"
            )

            fades.append(AudioFade(
                time=trans_time,
                fade_in_duration=round(actual_fade_in, 4),
                fade_out_duration=round(actual_fade_out, 4),
                curve_type=curve,
                transition_type=trans_type,
            ))

            prev_time = trans_time

        return fades

    def _adaptive_fade_duration(
        self,
        y: Any,
        sr: int,
        time_point: float,
        base_duration: float,
        direction: str = "out",
    ) -> float:
        """
        自适应淡入淡出时长 — 根据音频能量自动调整。

        Args:
            y: 音频信号
            sr: 采样率
            time_point: 时间点（秒）
            base_duration: 基础时长
            direction: "out" 淡出（分析时间点前）或 "in" 淡入（分析时间点后）
        """
        import numpy as np

        center_sample = int(time_point * sr)
        window_samples = int(self.fade_analysis_window * sr)

        if direction == "out":
            start = max(0, center_sample - window_samples)
            end = min(center_sample, len(y))
        else:
            start = min(center_sample, len(y))
            end = min(center_sample + window_samples, len(y))

        if end <= start:
            return base_duration

        segment = y[start:end]
        if len(segment) == 0:
            return base_duration

        rms = np.sqrt(np.mean(segment ** 2))

        # 能量高 → 淡出快一些；能量低 → 淡出慢一些
        energy_factor = 1.0 - min(rms * 5, 0.8)

        adjusted = base_duration * (0.5 + energy_factor)
        return max(self.min_fade_duration, min(adjusted, self.max_fade_duration))

    def generate_fade_envelope(
        self,
        fades: list[AudioFade],
        total_duration: float,
    ) -> list[dict[str, float]]:
        """
        生成完整的音量包络（用于 AE/PR 关键帧）。

        Returns:
            [{"time": 0.0, "volume": 0.0}, {"time": 0.5, "volume": 1.0}, ...]
        """
        envelope = []
        envelope.append({"time": 0.0, "volume": 0.0})  # 起始静音

        # 为每个淡入淡出生成包络点
        for fade in fades:
            if fade.fade_out_duration > 0:
                # 淡出段
                fade_out_start = max(0, fade.time - fade.fade_out_duration)
                volume_samples = self._generate_curve_samples(
                    fade.fade_out_duration, "out", fade.curve_type
                )

                for i, vol in enumerate(volume_samples):
                    t = fade_out_start + (i / len(volume_samples)) * fade.fade_out_duration
                    envelope.append({"time": round(t, 4), "volume": round(float(vol), 4)})

            if fade.fade_in_duration > 0:
                # 淡入段
                volume_samples = self._generate_curve_samples(
                    fade.fade_in_duration, "in", fade.curve_type
                )

                for i, vol in enumerate(volume_samples):
                    t = fade.time + (i / len(volume_samples)) * fade.fade_in_duration
                    envelope.append({"time": round(t, 4), "volume": round(float(vol), 4)})

        # 末尾淡出
        if total_duration > 0:
            envelope.append({"time": total_duration - 0.5, "volume": 1.0})
            envelope.append({"time": total_duration, "volume": 0.0})

        # 去重排序
        envelope.sort(key=lambda e: e["time"])
        unique_envelope = []
        for e in envelope:
            if not unique_envelope or abs(e["time"] - unique_envelope[-1]["time"]) > 0.001:
                unique_envelope.append(e)

        return unique_envelope

    def _generate_curve_samples(
        self,
        duration: float,
        direction: str,
        curve_type: str,
        resolution: int = 20,
    ) -> list[float]:
        """生成淡入淡出曲线采样点"""
        import numpy as np

        t = np.linspace(0, 1, resolution)

        if curve_type == "linear":
            curve = t
        elif curve_type == "exponential":
            curve = t ** 2
        elif curve_type == "logarithmic":
            curve = np.log(1 + 9 * t) / np.log(10)
        elif curve_type == "s_curve":
            curve = 1 / (1 + np.exp(-12 * (t - 0.5)))
        else:
            curve = t

        if direction == "out":
            curve = 1 - curve

        return curve.tolist()

    # ================================================================
    #  BGM 自适应混音
    # ================================================================
    def auto_duck_bgm(
        self,
        narration_path: str,
        bgm_path: str,
        output_path: str,
        duck_amount_db: float = -12.0,
        attack_ms: float = 100.0,
        release_ms: float = 500.0,
    ) -> str:
        """
        BGM 自动避让 — 人声/旁白时自动降低背景音乐音量。

        Args:
            narration_path: 人声/旁白文件
            bgm_path: 背景音乐文件
            output_path: 输出路径
            duck_amount_db: 避让衰减量（dB）
            attack_ms: 启动时间（ms）
            release_ms: 释放时间（ms）

        Returns:
            输出文件路径
        """
        import librosa
        import numpy as np
        import soundfile as sf

        # 加载音频
        narration, sr_n = librosa.load(narration_path, sr=self.sr)
        bgm, sr_b = librosa.load(bgm_path, sr=self.sr)

        # 对齐长度
        max_len = max(len(narration), len(bgm))
        if len(narration) < max_len:
            narration = np.pad(narration, (0, max_len - len(narration)))
        if len(bgm) < max_len:
            bgm = np.pad(bgm, (0, max_len - len(bgm)))

        # 计算旁白能量包络
        hop_length = 256
        nar_rms = librosa.feature.rms(y=narration, hop_length=hop_length, frame_length=1024)[0]

        # 生成避让包络
        threshold = np.median(nar_rms) * 2.0  # 自适应阈值
        duck_mask = (nar_rms > threshold).astype(np.float32)

        # 平滑处理（attack/release）
        attack_samples = int(attack_ms / 1000 * self.sr / hop_length)
        release_samples = int(release_ms / 1000 * self.sr / hop_length)

        if attack_samples > 0:
            attack_kernel = np.linspace(0, 1, attack_samples)
            duck_mask = np.convolve(duck_mask, np.ones(release_samples) / release_samples, mode='same')

        # 插值到采样级别
        duck_envelope = np.interp(
            np.arange(len(bgm)),
            np.arange(len(duck_mask)) * hop_length,
            duck_mask,
        )

        # 应用避让
        duck_factor = 10 ** (duck_amount_db / 20)  # dB → 线性
        duck_envelope = 1.0 + (duck_factor - 1.0) * duck_envelope[:len(bgm)]
        duck_envelope = np.clip(duck_envelope, 0.01, 1.0)

        bgm_ducked = bgm * duck_envelope[:len(bgm)]

        # 混音
        mix = narration[:len(bgm)] + bgm_ducked

        # 防止削波
        peak = np.max(np.abs(mix))
        if peak > 0.95:
            mix = mix / peak * 0.95

        sf.write(output_path, mix, self.sr)
        return output_path

    # ================================================================
    #  音频标准化
    # ================================================================
    def normalize_audio(
        self,
        audio_path: str,
        output_path: str,
        target_lufs: float = -14.0,
    ) -> str:
        """
        LUFS 响度标准化。

        Args:
            audio_path: 输入音频
            output_path: 输出路径
            target_lufs: 目标响度 (LUFS)，默认 -14 (流媒体标准)

        Returns:
            输出路径
        """
        import librosa
        import numpy as np
        import soundfile as sf

        y, sr = librosa.load(audio_path, sr=self.sr)

        # 计算当前响度（简化 ITU-R BS.1770）
        rms = np.sqrt(np.mean(y ** 2))
        current_db = 20 * np.log10(rms + 1e-10)
        target_linear = 10 ** (target_lufs / 20)

        # 归一化
        gain = target_linear / (rms + 1e-10)
        normalized = y * gain

        # 防止削波
        peak = np.max(np.abs(normalized))
        if peak > 0.98:
            normalized = normalized / peak * 0.98

        sf.write(output_path, normalized, sr)
        return output_path

    def mix_tracks(
        self,
        tracks: list[AudioTrackConfig],
        output_path: str,
    ) -> AudioMixResult:
        """
        多轨混音。

        Args:
            tracks: 轨道配置列表
            output_path: 输出路径

        Returns:
            AudioMixResult 对象
        """
        import librosa
        import numpy as np
        import soundfile as sf

        max_duration = 0.0
        mixed_audio = None

        for track in tracks:
            if not os.path.exists(track.source_path):
                continue

            y, sr = librosa.load(track.source_path, sr=self.sr)

            # 应用增益
            gain = 10 ** (track.volume_db / 20)
            y = y * gain

            # 应用 Pan
            if track.pan != 0 and len(y.shape) == 1:
                # 模拟立体声 Pan
                left_gain = math.cos((track.pan + 1) * math.pi / 4)
                right_gain = math.sin((track.pan + 1) * math.pi / 4)
                y = np.array([y * left_gain, y * right_gain])

            # 偏移
            if track.start_offset > 0:
                offset_samples = int(track.start_offset * sr)
                y = np.pad(y, (offset_samples, 0))[:max(len(y) + offset_samples, 1)]

            # 混合
            if mixed_audio is None:
                mixed_audio = y
            else:
                min_len = min(len(mixed_audio), len(y))
                mixed_audio[:min_len] += y[:min_len]
                if len(y) > len(mixed_audio):
                    mixed_audio = np.pad(mixed_audio, (0, len(y) - len(mixed_audio)))
                    mixed_audio[len(mixed_audio) - (len(y) - min_len):] += y[min_len:]

            max_duration = max(max_duration, len(mixed_audio) / sr)

        if mixed_audio is None:
            return AudioMixResult(
                output_path=output_path,
                duration=0,
                peak_db=-100,
                rms_db=-100,
                loudness_lufs=-100,
                fades=[],
                tracks=tracks,
            )

        # 防止削波
        peak = np.max(np.abs(mixed_audio))
        if peak > 0.98:
            mixed_audio = mixed_audio / peak * 0.98

        sf.write(output_path, mixed_audio, sr)

        # 计算指标
        rms = np.sqrt(np.mean(mixed_audio ** 2))
        peak_db = 20 * np.log10(peak + 1e-10)
        rms_db = 20 * np.log10(rms + 1e-10)
        lufs = rms_db  # 简化计算

        return AudioMixResult(
            output_path=output_path,
            duration=max_duration,
            peak_db=round(float(peak_db), 2),
            rms_db=round(float(rms_db), 2),
            loudness_lufs=round(float(lufs), 2),
            fades=[],
            tracks=tracks,
        )

    def export_fade_keyframes_json(
        self,
        fades: list[AudioFade],
        total_duration: float,
        output_path: str = None,
    ) -> dict[str, Any]:
        """导出淡入淡出关键帧为 AE/PR 兼容 JSON"""
        envelope = self.generate_fade_envelope(fades, total_duration)

        keyframes = {
            "type": "audio_volume",
            "total_duration": total_duration,
            "keyframes": envelope,
            "fade_points": [
                {
                    "time": f.time,
                    "fade_in": f.fade_in_duration,
                    "fade_out": f.fade_out_duration,
                    "curve": f.curve_type,
                    "transition": f.transition_type,
                }
                for f in fades
            ],
        }

        if output_path:
            Path(output_path).write_text(json.dumps(keyframes, indent=2, ensure_ascii=False), encoding='utf-8')

        return keyframes


__all__ = [
    "AudioProcessor",
    "AudioFade",
    "AudioTrackConfig",
    "AudioMixResult",
]
