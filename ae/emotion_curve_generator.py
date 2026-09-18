"""
Emotion Curve Generator — 情绪曲线生成器
========================================
基于 BGM 的 BPM、节拍强度分布、能量曲线，生成情绪曲线。

核心能力:
- 基于音频特征生成 0.0~1.0 的情绪曲线
- 自动划分段落（intro/build/drop/break/outro）
- 为每个段落分配视觉风格参数

依赖:
    pip install librosa numpy

用法:
    generator = EmotionCurveGenerator()
    curve = generator.generate("bgm.mp3", duration=48.0)
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))


# ================================================================
#  数据结构
# ================================================================

class EmotionLevel(str, Enum):
    """情绪等级"""
    INTRO = "intro"       # 前奏/引入
    BUILD = "build"       #  buildup
    DROP = "drop"         # 高潮
    BREAK = "break"       # 喘息
    OUTRO = "outro"       # 尾奏
    CLIMAX = "climax"     # 最高潮


@dataclass
class EmotionPoint:
    """情绪曲线上的点"""
    time: float           # 时间（秒）
    value: float          # 情绪值 (0.0~1.0)
    level: str            # 情绪等级
    bpm: float            # 瞬时 BPM
    energy: float         # 能量值


@dataclass
class EmotionSegment:
    """情绪段落"""
    label: str            # 段落标签
    start_time: float     # 开始时间
    end_time: float       # 结束时间
    duration: float       # 时长
    avg_emotion: float    # 平均情绪值
    peak_emotion: float   # 峰值情绪
    visual_style: dict[str, Any]  # 视觉风格参数


@dataclass
class EmotionCurve:
    """情绪曲线"""
    duration: float                           # 总时长
    points: list[EmotionPoint]                # 情绪点列表
    segments: list[EmotionSegment]            # 段落列表
    avg_emotion: float                        # 平均情绪值
    peak_time: float                          # 峰值时间
    overall_level: str                        # 整体情绪等级


# ================================================================
#  情绪曲线生成器
# ================================================================

class EmotionCurveGenerator:
    """情绪曲线生成器"""

    # 视觉风格预设
    VISUAL_STYLES = {
        EmotionLevel.INTRO.value: {
            "text_animation": "fade_in",
            "text_size": 60,
            "color_scheme": "gold",
            "transition": "crossfade",
            "camera_motion": "slow_zoom_in",
        },
        EmotionLevel.BUILD.value: {
            "text_animation": "slide_up",
            "text_size": 68,
            "color_scheme": "cyan",
            "transition": "cut",
            "camera_motion": "pan_right",
        },
        EmotionLevel.DROP.value: {
            "text_animation": "shockwave",
            "text_size": 80,
            "color_scheme": "red",
            "transition": "flash",
            "camera_motion": "shake",
        },
        EmotionLevel.CLIMAX.value: {
            "text_animation": "bounce_in",
            "text_size": 88,
            "color_scheme": "red",
            "transition": "glitch",
            "camera_motion": "rapid_cut",
        },
        EmotionLevel.BREAK.value: {
            "text_animation": "pulse",
            "text_size": 64,
            "color_scheme": "purple",
            "transition": "dissolve",
            "camera_motion": "slow_pan",
        },
        EmotionLevel.OUTRO.value: {
            "text_animation": "fade_out",
            "text_size": 56,
            "color_scheme": "gold",
            "transition": "fade",
            "camera_motion": "zoom_out",
        },
    }

    def __init__(
        self,
        sample_rate: int = 22050,
        hop_length: int = 512,
    ):
        self.sr = sample_rate
        self.hop_length = hop_length

    def generate(
        self,
        audio_path: str,
        target_duration: float | None = None,
        start_time: float = 0.0,
    ) -> EmotionCurve:
        """
        生成情绪曲线。

        Args:
            audio_path: 音频文件路径
            target_duration: 目标时长（秒），None 表示使用全长
            start_time: 开始时间（秒）

        Returns:
            EmotionCurve 对象
        """
        import librosa
        import numpy as np

        # 加载音频
        y, sr = librosa.load(audio_path, sr=self.sr)
        total_duration = len(y) / sr

        # 截取目标段落
        if target_duration:
            end_time = min(start_time + target_duration, total_duration)
            y = y[int(start_time * sr):int(end_time * sr)]
            # 修复: duration 必须用实际截取后的时长(end_time - start_time),
            # 而非 target_duration —— 否则 BGM 比目标短时, 情绪曲线/切点
            # 规划在"不存在的时长"上, 后半段切点全错位 (v23 实测 40s 计划
            # vs 19.38s 成片, 卡点丢失根因)
            duration = max(0.1, end_time - start_time)
        else:
            duration = total_duration
            start_time = 0.0

        # 1. 提取音频特征
        features = self._extract_features(y, sr)

        # 2. 生成情绪曲线
        points = self._generate_points(features, duration, start_time)

        # 3. 划分段落
        segments = self._segment_curve(points, duration)

        # 4. 计算统计信息
        avg_emotion = np.mean([p.value for p in points]) if points else 0.5
        peak_idx = np.argmax([p.value for p in points]) if points else 0
        peak_time = points[peak_idx].time if points else 0.0

        # 5. 确定整体情绪等级
        overall_level = self._classify_overall_level(avg_emotion)

        return EmotionCurve(
            duration=duration,
            points=points,
            segments=segments,
            avg_emotion=float(avg_emotion),
            peak_time=float(peak_time),
            overall_level=overall_level,
        )

    def _extract_features(self, y, sr: int) -> dict:
        """提取音频特征"""
        import librosa
        import numpy as np

        # RMS 能量
        rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=self.hop_length)[0]
        
        # 频谱质心（音色亮度）
        spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=self.hop_length)[0]
        
        # 频谱对比度
        spectral_contrast = librosa.feature.spectral_contrast(y=y, sr=sr, hop_length=self.hop_length)
        contrast_mean = np.mean(spectral_contrast, axis=0)
        
        # BPM
        tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
        if hasattr(tempo, '__len__'):
            tempo = tempo[0] if len(tempo) > 0 else 120.0
        
        # Onset 强度
        onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=self.hop_length)
        
        return {
            "rms": rms,
            "spectral_centroid": spectral_centroid,
            "spectral_contrast": contrast_mean,
            "tempo": tempo,
            "onset_env": onset_env,
            "hop_length": self.hop_length,
            "sr": sr,
        }

    def _generate_points(
        self,
        features: dict,
        duration: float,
        start_time: float,
    ) -> list[EmotionPoint]:
        """生成情绪点"""
        import numpy as np

        rms = features["rms"]
        onset_env = features["onset_env"]
        tempo = features["tempo"]
        hop_length = features["hop_length"]
        sr = features["sr"]

        # 归一化 RMS 到 0-1
        rms_norm = (rms - rms.min()) / (rms.max() - rms.min() + 1e-6)
        
        # 归一化 onset 强度
        onset_norm = (onset_env - onset_env.min()) / (onset_env.max() - onset_env.min() + 1e-6)
        
        # 综合情绪值（加权平均）
        emotion_values = 0.6 * rms_norm + 0.4 * onset_norm
        
        # 平滑处理
        from scipy.ndimage import uniform_filter1d
        emotion_smooth = uniform_filter1d(emotion_values, size=10)

        # 生成点
        points = []
        times = np.linspace(0, duration, len(emotion_smooth))
        
        for t, e in zip(times, emotion_smooth):
            time_sec = float(t) + start_time
            emotion_val = float(np.clip(e, 0, 1))
            level = self._classify_emotion_level(emotion_val)
            
            points.append(EmotionPoint(
                time=round(time_sec, 3),
                value=round(emotion_val, 3),
                level=level,
                bpm=round(float(tempo), 1),
                energy=round(emotion_val, 3),
            ))

        return points

    def _classify_emotion_level(self, value: float) -> str:
        """分类情绪等级"""
        if value < 0.2:
            return EmotionLevel.INTRO.value
        elif value < 0.4:
            return EmotionLevel.BUILD.value
        elif value < 0.6:
            return EmotionLevel.BREAK.value
        elif value < 0.8:
            return EmotionLevel.DROP.value
        else:
            return EmotionLevel.CLIMAX.value

    def _classify_overall_level(self, avg_emotion: float) -> str:
        """分类整体情绪等级"""
        if avg_emotion < 0.3:
            return EmotionLevel.INTRO.value
        elif avg_emotion < 0.5:
            return EmotionLevel.BUILD.value
        elif avg_emotion < 0.7:
            return EmotionLevel.DROP.value
        else:
            return EmotionLevel.CLIMAX.value

    def _segment_curve(
        self,
        points: list[EmotionPoint],
        duration: float,
    ) -> list[EmotionSegment]:
        """划分段落"""
        import numpy as np

        if not points:
            return []

        # 基于情绪变化检测段落边界
        segments = []
        current_level = points[0].level
        current_start = points[0].time
        current_values = [points[0].value]

        for p in points[1:]:
            if p.level != current_level:
                # 段落结束
                avg_val = np.mean(current_values)
                peak_val = max(current_values)
                
                segments.append(EmotionSegment(
                    label=current_level,
                    start_time=round(current_start, 3),
                    end_time=round(p.time, 3),
                    duration=round(p.time - current_start, 3),
                    avg_emotion=round(float(avg_val), 3),
                    peak_emotion=round(float(peak_val), 3),
                    visual_style=self.VISUAL_STYLES.get(current_level, {}),
                ))
                
                # 新段落开始
                current_level = p.level
                current_start = p.time
                current_values = [p.value]
            else:
                current_values.append(p.value)

        # 最后一个段落
        if current_values:
            avg_val = np.mean(current_values)
            peak_val = max(current_values)
            segments.append(EmotionSegment(
                label=current_level,
                start_time=round(current_start, 3),
                end_time=round(duration, 3),
                duration=round(duration - current_start, 3),
                avg_emotion=round(float(avg_val), 3),
                peak_emotion=round(float(peak_val), 3),
                visual_style=self.VISUAL_STYLES.get(current_level, {}),
            ))

        return segments

    def export_json(self, curve: EmotionCurve, output_path: str) -> None:
        """导出情绪曲线为 JSON"""
        data = asdict(curve)
        Path(output_path).write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        print(f"[OK] 情绪曲线已导出: {output_path}")


# ================================================================
#  便捷函数
# ================================================================

def generate_emotion_curve(
    audio_path: str,
    target_duration: float | None = None,
    start_time: float = 0.0,
) -> EmotionCurve:
    """快速生成情绪曲线"""
    generator = EmotionCurveGenerator()
    return generator.generate(audio_path, target_duration, start_time)


__all__ = [
    "EmotionCurveGenerator",
    "EmotionCurve",
    "EmotionPoint",
    "EmotionSegment",
    "EmotionLevel",
    "generate_emotion_curve",
]


# ================================================================
#  自测入口
# ================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("EmotionCurveGenerator 自测")
    print("=" * 60)

    # 测试音频
    audio_path = r"D:\AE-Work\音频素材库\BGM\DiorGoFlex_AllEyesOnMe_v2.mp3"
    
    if not Path(audio_path).exists():
        print(f"[ERROR] 音频文件不存在: {audio_path}")
        sys.exit(1)

    # 生成情绪曲线（48秒，从120秒开始）
    print("\n生成情绪曲线...")
    generator = EmotionCurveGenerator()
    curve = generator.generate(audio_path, target_duration=48.0, start_time=120.0)

    print(f"  总时长: {curve.duration:.1f}s")
    print(f"  平均情绪: {curve.avg_emotion:.3f}")
    print(f"  峰值时间: {curve.peak_time:.1f}s")
    print(f"  整体等级: {curve.overall_level}")
    print(f"  段落数: {len(curve.segments)}")

    print("\n  段落详情:")
    for seg in curve.segments:
        print(f"    [{seg.label:8s}] {seg.start_time:.1f}s ~ {seg.end_time:.1f}s | "
              f"时长: {seg.duration:.1f}s | 平均: {seg.avg_emotion:.3f} | 峰值: {seg.peak_emotion:.3f}")

    # 导出
    output_dir = Path(r"D:\AE-Work\output\levi_mad_director_v1")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "emotion_curve.json"
    generator.export_json(curve, str(output_path))
