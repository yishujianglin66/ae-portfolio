# -*- coding: utf-8 -*-
"""BeatStrengthEngine — 节拍强弱分级引擎 (v21a P0)

借鉴 ai-montage-agent beat_engine 设计:
  将纯时间点节拍升级为 强/中/弱 三级语义, 使每个切点获得不同优先级。
  
  强拍(downbeat/重拍): 关键画面 + 强冲击技巧 + 高评分素材
  中拍(regular beat):   常规画面 + 中等素材
  弱拍(offbeat/过渡):   过渡画面 + 低要求素材

用法:
    from core.beat_strength_engine import BeatStrengthEngine
    engine = BeatStrengthEngine()
    classified = engine.classify_beats(beats_sec, downbeats_sec, onset_env, sr, hop_length)
    # classified: List[BeatInfo], 按时间排序, 每个含 strength_level + score
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("beat_strength_engine")


class BeatStrength(Enum):
    """节拍强弱等级"""
    STRONG = "strong"   # 强拍 (downbeat + 高onset)
    MEDIUM = "medium"   # 中拍 (regular beat)
    WEAK = "weak"       # 弱拍 (offbeat / 低能量)


@dataclass
class BeatInfo:
    """单个拍点的完整信息"""
    time_sec: float          # 拍点时间(秒)
    frame: int               # 帧号
    strength: BeatStrength   # 强弱等级
    score: float             # 0.0-1.0 强度评分
    is_downbeat: bool = False    # 是否重拍
    onset_strength: float = 0.0  # 该位置的onset包络值
    energy: float = 0.0          # 该位置的能量
    beat_index: int = 0          # 在拍序列中的索引
    bar_position: int = 0        # 在bar内的位置 (0=downbeat)
    
    @property
    def is_strong(self) -> bool:
        return self.strength == BeatStrength.STRONG
    
    @property
    def is_medium(self) -> bool:
        return self.strength == BeatStrength.MEDIUM
    
    @property
    def is_weak(self) -> bool:
        return self.strength == BeatStrength.WEAK


@dataclass
class BeatClassificationResult:
    """节拍分级结果"""
    beats: List[BeatInfo]                    # 所有拍点
    strong_beats: List[BeatInfo]             # 强拍
    medium_beats: List[BeatInfo]             # 中拍
    weak_beats: List[BeatInfo]               # 弱拍
    total_beats: int = 0
    bpm: float = 0.0
    bar_count: int = 0
    
    def get_beat_at_time(self, t: float, tolerance: float = 0.05) -> Optional[BeatInfo]:
        """获取指定时间最近的拍点信息"""
        for b in self.beats:
            if abs(b.time_sec - t) <= tolerance:
                return b
        return None
    
    def get_beats_in_range(self, start: float, end: float) -> List[BeatInfo]:
        """获取时间范围内的所有拍点"""
        return [b for b in self.beats if start <= b.time_sec < end]
    
    def statistics(self) -> Dict[str, Any]:
        """返回统计信息"""
        return {
            "total": self.total_beats,
            "strong": len(self.strong_beats),
            "medium": len(self.medium_beats),
            "weak": len(self.weak_beats),
            "bpm": round(self.bpm, 1),
            "bars": self.bar_count,
        }


class BeatStrengthEngine:
    """节拍强弱分级引擎
    
    分级策略 (三因子加权):
      1. downbeat加分: 是重拍 → +0.4
      2. onset强度: 该拍位置onset包络值在全曲的百分位 → 0~0.35
      3. 能量位置: 该拍处RMS能量在全曲百分位 → 0~0.25
    
    阈值:
      score >= 0.7 → STRONG
      0.4 <= score < 0.7 → MEDIUM  
      score < 0.4 → WEAK
    
    Parameters:
        strong_threshold: 强拍阈值 (默认0.7)
        medium_threshold: 中拍阈值 (默认0.4)
        downbeat_weight: 重拍加分权重 (默认0.4)
        onset_weight: onset强度权重 (默认0.35)
        energy_weight: 能量权重 (默认0.25)
        fps: 视频帧率 (用于frame计算)
    """

    def __init__(self, strong_threshold: float = 0.7, medium_threshold: float = 0.4,
                 downbeat_weight: float = 0.4, onset_weight: float = 0.35,
                 energy_weight: float = 0.25, fps: int = 24):
        self.strong_threshold = strong_threshold
        self.medium_threshold = medium_threshold
        self.downbeat_weight = downbeat_weight
        self.onset_weight = onset_weight
        self.energy_weight = energy_weight
        self.fps = fps

    # ────────────────────────────────────────────────────────────────
    # 主接口: 分级
    # ────────────────────────────────────────────────────────────────
    def classify_beats(self, beats_sec: np.ndarray, downbeats_sec: np.ndarray,
                       onset_envelope: Optional[np.ndarray] = None,
                       rms_energy: Optional[np.ndarray] = None,
                       times: Optional[np.ndarray] = None,
                       sr: int = 44100, hop_length: int = 512) -> BeatClassificationResult:
        """对所有拍点进行强弱分级
        
        Args:
            beats_sec: 拍点时间数组 (秒)
            downbeats_sec: 重拍时间数组 (秒)
            onset_envelope: onset包络 (帧域)
            rms_energy: RMS能量 (帧域)
            times: onset/rms对应的时间轴 (秒)
            sr: 采样率
            hop_length: hop长度
            
        Returns:
            BeatClassificationResult 包含分级后的所有拍点
        """
        beats_sec = np.asarray(beats_sec, dtype=float)
        downbeats_sec = np.asarray(downbeats_sec, dtype=float)
        
        if len(beats_sec) == 0:
            return BeatClassificationResult(beats=[], strong_beats=[], medium_beats=[], weak_beats=[])

        # BPM
        ivs = np.diff(beats_sec) if len(beats_sec) > 1 else [0.6]
        bpm = 60.0 / np.median(ivs)
        
        # 构建downbeat集合 (100ms容差匹配)
        downbeat_set = set()
        for b in beats_sec:
            for d in downbeats_sec:
                if abs(b - d) < 0.1:
                    downbeat_set.add(round(b, 4))
                    break

        # onset包络归一化
        if onset_envelope is not None and times is not None:
            onset_norm = self._normalize_onset(onset_envelope, times)
        else:
            onset_norm = None

        # RMS能量归一化
        if rms_energy is not None and times is not None:
            energy_norm = self._normalize_energy(rms_energy, times)
        else:
            energy_norm = None

        # 估计bar结构 (假设4/4拍)
        beats_per_bar = 4
        bar_count = int(np.ceil(len(beats_sec) / beats_per_bar))

        # 逐拍分级
        classified: List[BeatInfo] = []
        for i, t in enumerate(beats_sec):
            is_downbeat = round(t, 4) in downbeat_set
            bar_pos = i % beats_per_bar
            
            # 因子1: downbeat
            downbeat_score = 1.0 if is_downbeat else 0.0
            
            # 因子2: onset强度
            if onset_norm is not None:
                onset_val = self._interp_at_time(times, onset_norm, t)
            else:
                onset_val = 0.5  # 无onset数据时给中等值
            
            # 因子3: 能量
            if energy_norm is not None:
                energy_val = self._interp_at_time(times, energy_norm, t)
            else:
                energy_val = 0.5

            # 加权总分
            score = (downbeat_score * self.downbeat_weight +
                     onset_val * self.onset_weight +
                     energy_val * self.energy_weight)
            score = float(np.clip(score, 0.0, 1.0))

            # 分级
            if score >= self.strong_threshold:
                strength = BeatStrength.STRONG
            elif score >= self.medium_threshold:
                strength = BeatStrength.MEDIUM
            else:
                strength = BeatStrength.WEAK

            beat_info = BeatInfo(
                time_sec=float(t),
                frame=round(t * self.fps),
                strength=strength,
                score=score,
                is_downbeat=is_downbeat,
                onset_strength=onset_val,
                energy=energy_val,
                beat_index=i,
                bar_position=bar_pos,
            )
            classified.append(beat_info)

        # 统计
        strong = [b for b in classified if b.strength == BeatStrength.STRONG]
        medium = [b for b in classified if b.strength == BeatStrength.MEDIUM]
        weak = [b for b in classified if b.strength == BeatStrength.WEAK]

        result = BeatClassificationResult(
            beats=classified,
            strong_beats=strong,
            medium_beats=medium,
            weak_beats=weak,
            total_beats=len(classified),
            bpm=bpm,
            bar_count=bar_count,
        )
        
        logger.info(f"节拍分级: {len(classified)}拍 → "
                    f"强{len(strong)}/中{len(medium)}/弱{len(weak)}, BPM={bpm:.1f}")
        return result

    # ────────────────────────────────────────────────────────────────
    # 素材-节拍匹配: 根据强弱选择不同等级的素材
    # ────────────────────────────────────────────────────────────────
    def assign_materials(self, result: BeatClassificationResult,
                         scored_segments: List[Any],
                         min_segments_per_level: int = 3) -> Dict[BeatStrength, List[Any]]:
        """根据节拍强弱分配不同评分等级的素材
        
        策略:
          STRONG拍 → Top 20% 高分素材
          MEDIUM拍 → 40%-70% 中等素材
          WEAK拍   → 任意素材 (低要求)
          
        Args:
            result: 分级结果
            scored_segments: 按highlight分排序的素材段列表 (需有.total属性)
            min_segments_per_level: 每级最少分配的素材数
            
        Returns:
            {BeatStrength: [匹配的素材段列表]}
        """
        if not scored_segments:
            return {s: [] for s in BeatStrength}

        # 按分排序
        sorted_segs = sorted(scored_segments, key=lambda s: s.total, reverse=True)
        n = len(sorted_segs)
        
        # 划分区间
        top_20 = max(min_segments_per_level, int(n * 0.2))
        mid_50 = max(min_segments_per_level, int(n * 0.5))
        
        assignment = {
            BeatStrength.STRONG: sorted_segs[:top_20],
            BeatStrength.MEDIUM: sorted_segs[top_20:mid_50],
            BeatStrength.WEAK: sorted_segs[mid_50:],
        }
        return assignment

    # ────────────────────────────────────────────────────────────────
    # 内部方法
    # ────────────────────────────────────────────────────────────────
    def _normalize_onset(self, onset_env: np.ndarray, times: np.ndarray) -> np.ndarray:
        """onset包络归一化到0-1 (百分位归一化)"""
        if len(onset_env) == 0:
            return np.zeros(len(onset_env))
        p10 = np.percentile(onset_env, 10)
        p90 = np.percentile(onset_env, 90)
        if p90 - p10 < 1e-6:
            return np.ones(len(onset_env)) * 0.5
        normed = np.clip((onset_env - p10) / (p90 - p10), 0, 1)
        return normed

    def _normalize_energy(self, rms: np.ndarray, times: np.ndarray) -> np.ndarray:
        """RMS能量归一化到0-1 (百分位归一化)"""
        if len(rms) == 0:
            return np.zeros(len(rms))
        p10 = np.percentile(rms, 10)
        p90 = np.percentile(rms, 90)
        if p90 - p10 < 1e-6:
            return np.ones(len(rms)) * 0.5
        normed = np.clip((rms - p10) / (p90 - p10), 0, 1)
        return normed

    def _interp_at_time(self, times: np.ndarray, values: np.ndarray, t: float) -> float:
        """在时间轴上插值取值"""
        return float(np.interp(t, times, values))

    def __repr__(self) -> str:
        return (f"BeatStrengthEngine(strong>={self.strong_threshold}, "
                f"medium>={self.medium_threshold}, fps={self.fps})")


# ────────────────────────────────────────────────────────────────────
# CLI 快速验证
# ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    
    # 用BGM验证
    bgm_path = r"D:\AE-Work\音频素材库\BGM\独自升级.mp3"
    
    import librosa
    y, sr = librosa.load(bgm_path, sr=44100, mono=True)
    duration = len(y) / sr
    print(f"BGM: {duration:.2f}s")
    
    # beat_this检测
    from beat_this.inference import Audio2Beats
    from core.torch_runtime import get_device
    model = Audio2Beats(device=get_device())
    result = model(y, sr)
    if isinstance(result, tuple):
        beats_sec = np.array(result[0], dtype=float)
        downbeats_sec = np.array(result[1], dtype=float)
    else:
        beats_sec = np.array(result.beats, dtype=float)
        downbeats_sec = np.array(result.downbeats, dtype=float)
    
    # onset & rms
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=512)[0]
    times = librosa.frames_to_time(np.arange(len(onset_env)), sr=sr, hop_length=512)
    
    # 分级
    engine = BeatStrengthEngine(fps=24)
    classified = engine.classify_beats(beats_sec, downbeats_sec, onset_env, rms, times, sr)
    
    stats = classified.statistics()
    print(f"\n分级结果: {stats}")
    print(f"\n逐拍详情:")
    print(f"{'#':>3s} {'时间':>8s} {'等级':>6s} {'评分':>6s} {'DB':>3s} {'onset':>6s} {'energy':>6s}")
    print("-" * 50)
    for b in classified.beats:
        level = {"strong": "强", "medium": "中", "weak": "弱"}[b.strength.value]
        print(f"{b.beat_index:3d} {b.time_sec:7.3f}s {level:>4s} {b.score:6.3f} "
              f"{'Y' if b.is_downbeat else 'N':>3s} {b.onset_strength:6.3f} {b.energy:6.3f}")
