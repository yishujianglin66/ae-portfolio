#!/usr/bin/env python3
"""
节拍-关键帧精密映射引擎 v1.0
基于音乐节拍的精确关键帧位置映射算法，支持动态规划匹配和贝塞尔曲线插值
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
import math


@dataclass
class Beat:
    """单个节拍"""
    time: float       # 时间（秒）
    strength: float   # 强度 (0-1)
    is_downbeat: bool # 是否强拍
    beat_number: int  # 节拍编号
    measure: int      # 小节号


@dataclass
class KeyframeMapping:
    """关键帧映射结果"""
    time: float           # 关键帧时间（秒）
    beat_time: float      # 对应节拍时间
    offset_ms: float      # 偏移量（毫秒，正值=延迟，负值=提前）
    strength: float       # 节拍强度
    property_name: str    # 属性名
    value: Any            # 值
    ease_type: str        # 缓动类型
    confidence: float     # 置信度


@dataclass
class MappingResult:
    """完整映射结果"""
    mappings: List[KeyframeMapping]
    beat_count: int
    keyframe_count: int
    average_offset_ms: float
    max_offset_ms: float
    coverage: float  # 节拍覆盖率 (0-1)


def parse_beats_from_features(audio_features: Dict) -> List[Beat]:
    """
    从音频分析结果中提取节拍信息

    input: audio_features dict (from audio_analyzer_enhanced.py)
    output: List[Beat]
    """
    features = audio_features.get("features", audio_features)

    beat_times = features.get("beats", [])
    downbeat_times = features.get("downbeats", [])
    bpm = features.get("bpm", 120.0)
    energy_curve = features.get("energy_curve", {})
    duration = features.get("duration", 0.0)

    downbeat_set = set(round(t, 3) for t in downbeat_times)

    energy_values = energy_curve.get("values", [])
    energy_times = energy_curve.get("times", [])

    # 构建时间->能量查找
    energy_map: Dict[float, float] = {}
    if energy_times and energy_values:
        for t, v in zip(energy_times, energy_values):
            energy_map[round(float(t), 3)] = float(v)

    avg_energy = sum(energy_values) / len(energy_values) if energy_values else 0.1
    max_energy = max(energy_values) if energy_values else 0.1
    energy_range = max_energy - avg_energy if max_energy > avg_energy else 0.1

    beats: List[Beat] = []
    beats_per_measure = 4
    seconds_per_beat = 60.0 / bpm if bpm > 0 else 0.5

    for i, bt in enumerate(beat_times):
        bt_f = float(bt)

        # 查找最近的能量值
        strength = 0.5
        if energy_map:
            closest_key = min(energy_map.keys(), key=lambda t: abs(t - bt_f))
            if abs(closest_key - bt_f) < 0.1:
                ev = energy_map[closest_key]
                strength = min(1.0, max(0.0, (ev - avg_energy) / energy_range + 0.5))

        is_downbeat = round(bt_f, 3) in downbeat_set
        measure = int(i / beats_per_measure) + 1

        beats.append(Beat(
            time=bt_f,
            strength=strength,
            is_downbeat=is_downbeat,
            beat_number=i + 1,
            measure=measure,
        ))

    # 如果没有检测到强拍，按4拍一小节推算
    if not downbeat_times and beats:
        for b in beats:
            b.is_downbeat = (b.beat_number - 1) % beats_per_measure == 0

    return beats


class BeatKeyframeMapper:
    """节拍-关键帧精密映射引擎"""

    # 风格预设
    STYLE_PRESETS = {
        "default": {"offset_tolerance_ms": 50, "downbeat_weight": 1.0, "allow_offbeat": True},
        "on_beat": {"offset_tolerance_ms": 10, "downbeat_weight": 1.0, "allow_offbeat": False},
        "off_beat": {"offset_tolerance_ms": 50, "downbeat_weight": 0.5, "allow_offbeat": True},
        "double_time": {"offset_tolerance_ms": 30, "downbeat_weight": 0.8, "allow_offbeat": True},
        "half_time": {"offset_tolerance_ms": 80, "downbeat_weight": 1.5, "allow_offbeat": False},
    }

    def __init__(self, precision_ms: float = 10.0):
        """
        precision_ms: 映射精度（毫秒），默认10ms
        """
        self.precision_ms = precision_ms

    def map_beats_to_keyframes(
        self,
        beats: List[Beat],
        target_events: List[Dict],
        strategy: str = "dynamic_programming",
    ) -> MappingResult:
        """
        将节拍映射到目标事件（关键帧位置）

        strategy:
        - "nearest": 最近邻匹配
        - "dynamic_programming": 动态规划最优匹配
        - "downbeat_priority": 强拍优先
        - "energy_based": 基于能量曲线
        """
        if not beats or not target_events:
            return MappingResult(
                mappings=[],
                beat_count=len(beats),
                keyframe_count=len(target_events),
                average_offset_ms=0.0,
                max_offset_ms=0.0,
                coverage=0.0,
            )

        # 按时间排序
        sorted_targets = sorted(target_events, key=lambda t: t.get("time", 0))

        strategy_map = {
            "nearest": self._map_nearest,
            "dynamic_programming": self._map_dynamic_programming,
            "downbeat_priority": self._map_downbeat_priority,
            "energy_based": self._map_energy_based,
        }

        mapper = strategy_map.get(strategy, self._map_dynamic_programming)
        mappings = mapper(beats, sorted_targets)

        # 计算统计信息
        matched_beats = set()
        offsets = []
        for m in mappings:
            matched_beats.add(round(m.beat_time, 3))
            offsets.append(abs(m.offset_ms))

        coverage = len(matched_beats) / len(beats) if beats else 0.0
        avg_offset = sum(offsets) / len(offsets) if offsets else 0.0
        max_offset = max(offsets) if offsets else 0.0

        return MappingResult(
            mappings=mappings,
            beat_count=len(beats),
            keyframe_count=len(target_events),
            average_offset_ms=avg_offset,
            max_offset_ms=max_offset,
            coverage=coverage,
        )

    # ------------------------------------------------------------------
    # 策略实现
    # ------------------------------------------------------------------

    def _map_nearest(self, beats: List[Beat], targets: List[Dict]) -> List[KeyframeMapping]:
        """最近邻匹配：每个目标事件匹配最近的节拍"""
        mappings: List[KeyframeMapping] = []
        max_offset_s = self.precision_ms * 5 / 1000.0

        for target in targets:
            target_time = target.get("time", 0)
            prop_name = target.get("property", target.get("type", "unknown"))
            value = target.get("value", 1.0)
            ease = target.get("ease", "ease_out")

            best_beat = None
            best_dist = float("inf")

            for beat in beats:
                dist = abs(beat.time - target_time)
                if dist < best_dist:
                    best_dist = dist
                    best_beat = beat

            if best_beat is not None and best_dist <= max_offset_s:
                offset_ms = (target_time - best_beat.time) * 1000.0
                confidence = 1.0 - (best_dist / max_offset_s)
                confidence = max(0.0, min(1.0, confidence))

                mappings.append(KeyframeMapping(
                    time=target_time,
                    beat_time=best_beat.time,
                    offset_ms=offset_ms,
                    strength=best_beat.strength,
                    property_name=prop_name,
                    value=value,
                    ease_type=ease,
                    confidence=confidence,
                ))

        return mappings

    def _map_dynamic_programming(self, beats: List[Beat], targets: List[Dict]) -> List[KeyframeMapping]:
        """
        动态规划匹配：最小化总偏移量的全局最优解

        算法：
        1. 构建代价矩阵 cost[i][j] = |beat[i].time - target[j].time|
        2. 使用动态规划求解最优匹配
        3. 允许一个节拍匹配多个目标，但不允许一个目标匹配多个节拍
        4. 约束：匹配偏移量不超过 precision_ms * 5
        """
        n = len(beats)
        m = len(targets)
        max_offset_s = self.precision_ms * 5 / 1000.0
        INF = float("inf")

        # 1. 构建代价矩阵
        cost = [[INF] * m for _ in range(n)]
        for i in range(n):
            for j in range(m):
                time_diff = abs(beats[i].time - targets[j].get("time", 0))
                if time_diff <= max_offset_s:
                    # 强度惩罚：弱拍代价略增
                    strength_penalty = (1.0 - beats[i].strength) * 0.02
                    cost[i][j] = time_diff + strength_penalty

        # 2. 动态规划
        # dp[i][j] = 前i个节拍匹配前j个目标的最小代价
        dp = [[INF] * (m + 1) for _ in range(n + 1)]
        dp[0][0] = 0.0

        # choice[i][j]: dp[i][j]由哪个决策转移而来
        # 0 = 从 dp[i-1][j]（跳过beat i）, 1 = 从 dp[i-1][j-1] + cost（匹配）
        choice = [[0] * (m + 1) for _ in range(n + 1)]

        for i in range(1, n + 1):
            for j in range(0, m + 1):
                # 选项1：跳过 beat i-1
                if dp[i - 1][j] < dp[i][j]:
                    dp[i][j] = dp[i - 1][j]
                    choice[i][j] = 0

                # 选项2：beat i-1 匹配 target j-1
                if j >= 1 and cost[i - 1][j - 1] < INF:
                    candidate = dp[i - 1][j - 1] + cost[i - 1][j - 1]
                    if candidate < dp[i][j]:
                        dp[i][j] = candidate
                        choice[i][j] = 1

        # 3. 回溯得到最优匹配
        match_pairs: List[Tuple[int, int]] = []  # (beat_index, target_index)
        i, j = n, m
        while i > 0 and j > 0:
            if choice[i][j] == 1:
                match_pairs.append((i - 1, j - 1))
                i -= 1
                j -= 1
            else:
                i -= 1
        match_pairs.reverse()

        # 4. 构建映射结果
        mappings: List[KeyframeMapping] = []
        for bi, ti in match_pairs:
            beat = beats[bi]
            target = targets[ti]
            target_time = target.get("time", 0)
            offset_ms = (target_time - beat.time) * 1000.0
            time_diff_s = abs(beat.time - target_time)
            confidence = 1.0 - (time_diff_s / max_offset_s)
            confidence = max(0.0, min(1.0, confidence))

            mappings.append(KeyframeMapping(
                time=target_time,
                beat_time=beat.time,
                offset_ms=offset_ms,
                strength=beat.strength,
                property_name=target.get("property", target.get("type", "unknown")),
                value=target.get("value", 1.0),
                ease_type=target.get("ease", "ease_out"),
                confidence=confidence,
            ))

        return mappings

    def _map_downbeat_priority(self, beats: List[Beat], targets: List[Dict]) -> List[KeyframeMapping]:
        """强拍优先匹配：优先匹配强拍，剩余目标匹配弱拍"""
        max_offset_s = self.precision_ms * 5 / 1000.0

        downbeats = [b for b in beats if b.is_downbeat]
        weakbeats = [b for b in beats if not b.is_downbeat]

        mappings: List[KeyframeMapping] = []
        used_beats: Dict[int, bool] = {}  # beat_number -> used
        matched_targets: set = set()

        # 第一轮：强拍匹配
        for idx, target in enumerate(targets):
            target_time = target.get("time", 0)
            best_beat = None
            best_dist = float("inf")

            for beat in downbeats:
                if used_beats.get(beat.beat_number):
                    continue
                dist = abs(beat.time - target_time)
                if dist < best_dist and dist <= max_offset_s:
                    best_dist = dist
                    best_beat = beat

            if best_beat is not None:
                offset_ms = (target_time - best_beat.time) * 1000.0
                confidence = 1.0 - (best_dist / max_offset_s)
                confidence = max(0.0, min(1.0, confidence))
                mappings.append(KeyframeMapping(
                    time=target_time,
                    beat_time=best_beat.time,
                    offset_ms=offset_ms,
                    strength=best_beat.strength,
                    property_name=target.get("property", target.get("type", "unknown")),
                    value=target.get("value", 1.0),
                    ease_type=target.get("ease", "ease_out"),
                    confidence=confidence,
                ))
                used_beats[best_beat.beat_number] = True
                matched_targets.add(idx)

        # 第二轮：弱拍匹配剩余目标
        for idx, target in enumerate(targets):
            if idx in matched_targets:
                continue
            target_time = target.get("time", 0)
            best_beat = None
            best_dist = float("inf")

            for beat in weakbeats:
                if used_beats.get(beat.beat_number):
                    continue
                dist = abs(beat.time - target_time)
                if dist < best_dist and dist <= max_offset_s:
                    best_dist = dist
                    best_beat = beat

            if best_beat is not None:
                offset_ms = (target_time - best_beat.time) * 1000.0
                confidence = 1.0 - (best_dist / max_offset_s) * 1.2  # 弱拍置信度略低
                confidence = max(0.0, min(1.0, confidence))
                mappings.append(KeyframeMapping(
                    time=target_time,
                    beat_time=best_beat.time,
                    offset_ms=offset_ms,
                    strength=best_beat.strength,
                    property_name=target.get("property", target.get("type", "unknown")),
                    value=target.get("value", 1.0),
                    ease_type=target.get("ease", "ease_out"),
                    confidence=confidence,
                ))
                used_beats[best_beat.beat_number] = True

        # 按时间排序
        mappings.sort(key=lambda m: m.time)
        return mappings

    def _map_energy_based(self, beats: List[Beat], targets: List[Dict]) -> List[KeyframeMapping]:
        """基于能量曲线匹配：高能量目标匹配高能量节拍"""
        max_offset_s = self.precision_ms * 5 / 1000.0

        # 给每个目标计算能量等级
        def target_energy(target: Dict) -> float:
            return target.get("energy", target.get("intensity", 0.5))

        # 按能量对节拍和目标分别排序
        beats_sorted = sorted(beats, key=lambda b: -b.strength)
        targets_with_idx = [(i, t) for i, t in enumerate(targets)]
        targets_sorted = sorted(targets_with_idx, key=lambda x: -target_energy(x[1]))

        mappings: List[KeyframeMapping] = []
        used_beats: set = set()

        for idx, target in targets_sorted:
            target_time = target.get("time", 0)
            t_energy = target_energy(target)

            best_beat = None
            best_score = float("inf")

            for beat in beats_sorted:
                if beat.beat_number in used_beats:
                    continue
                dist = abs(beat.time - target_time)
                if dist > max_offset_s:
                    continue

                # 能量差越小越好
                energy_diff = abs(beat.strength - t_energy)
                score = dist + energy_diff * 0.5

                if score < best_score:
                    best_score = score
                    best_beat = beat

            if best_beat is not None:
                offset_ms = (target_time - best_beat.time) * 1000.0
                dist = abs(best_beat.time - target_time)
                confidence = 1.0 - (dist / max_offset_s)
                confidence = max(0.0, min(1.0, confidence))

                mappings.append(KeyframeMapping(
                    time=target_time,
                    beat_time=best_beat.time,
                    offset_ms=offset_ms,
                    strength=best_beat.strength,
                    property_name=target.get("property", target.get("type", "unknown")),
                    value=target.get("value", 1.0),
                    ease_type=target.get("ease", "ease_out"),
                    confidence=confidence,
                ))
                used_beats.add(best_beat.beat_number)

        # 按时间排序
        mappings.sort(key=lambda m: m.time)
        return mappings

    # ------------------------------------------------------------------
    # 时间线生成
    # ------------------------------------------------------------------

    def generate_beat_synced_timeline(
        self,
        beats: List[Beat],
        total_duration: float,
        clip_events: List[Dict],
        style: str = "default",
    ) -> Dict:
        """
        生成节拍同步的完整时间线

        clip_events: 剪辑事件列表 [{"type": "cut"|"effect"|"transition", "time": float, ...}]
        style: 风格预设
            - "default": 标准卡点
            - "on_beat": 严格节拍对齐（±10ms）
            - "off_beat": 反拍对齐
            - "double_time": 双倍速卡点
            - "half_time": 半速卡点

        返回: {
            "timeline": [...],  # 完整时间线事件
            "beat_map": [...],  # 节拍映射
            "statistics": {...} # 统计信息
        }
        """
        preset = self.STYLE_PRESETS.get(style, self.STYLE_PRESETS["default"])
        tolerance_ms = preset["offset_tolerance_ms"]

        # 根据风格调整节拍列表
        effective_beats = self._adjust_beats_for_style(beats, style, total_duration)

        # 将剪辑事件转化为目标事件格式
        target_events = []
        for evt in clip_events:
            target_events.append({
                "time": evt.get("time", 0),
                "property": evt.get("type", "unknown"),
                "value": evt.get("value", evt.get("intensity", 1.0)),
                "ease": evt.get("ease", "ease_out"),
                "energy": evt.get("intensity", evt.get("energy", 0.5)),
            })

        # 选择策略
        if style == "on_beat":
            strategy = "nearest"
        elif style == "off_beat":
            strategy = "nearest"
        else:
            strategy = "dynamic_programming"

        result = self.map_beats_to_keyframes(effective_beats, target_events, strategy)

        # 构建完整时间线
        timeline: List[Dict] = []
        for m in result.mappings:
            timeline.append({
                "time": round(m.time, 4),
                "beat_time": round(m.beat_time, 4),
                "offset_ms": round(m.offset_ms, 2),
                "type": m.property_name,
                "value": m.value,
                "ease": m.ease_type,
                "strength": round(m.strength, 3),
                "confidence": round(m.confidence, 3),
                "is_downbeat": any(
                    b.is_downbeat and abs(b.time - m.beat_time) < 0.001
                    for b in effective_beats
                ),
            })

        # 节拍映射
        beat_map = [
            {
                "time": round(b.time, 4),
                "strength": round(b.strength, 3),
                "is_downbeat": b.is_downbeat,
                "beat_number": b.beat_number,
                "measure": b.measure,
            }
            for b in effective_beats
        ]

        # 统计信息
        stats = {
            "style": style,
            "total_events": len(clip_events),
            "matched_events": len(result.mappings),
            "beat_count": len(effective_beats),
            "coverage": round(result.coverage, 3),
            "average_offset_ms": round(result.average_offset_ms, 2),
            "max_offset_ms": round(result.max_offset_ms, 2),
            "duration": round(total_duration, 3),
        }

        return {
            "timeline": timeline,
            "beat_map": beat_map,
            "statistics": stats,
        }

    def _adjust_beats_for_style(
        self, beats: List[Beat], style: str, total_duration: float
    ) -> List[Beat]:
        """根据风格预设调整节拍列表"""
        if style == "off_beat":
            # 反拍：在每个节拍之间插入一个偏移节拍
            adjusted: List[Beat] = []
            for i in range(len(beats) - 1):
                mid_time = (beats[i].time + beats[i + 1].time) / 2.0
                adjusted.append(Beat(
                    time=mid_time,
                    strength=beats[i].strength * 0.7,
                    is_downbeat=False,
                    beat_number=beats[i].beat_number * 2,
                    measure=beats[i].measure,
                ))
            return adjusted

        elif style == "double_time":
            # 双倍速：在每个节拍之间插入一个中间节拍
            adjusted = []
            for i in range(len(beats) - 1):
                adjusted.append(beats[i])
                mid_time = (beats[i].time + beats[i + 1].time) / 2.0
                adjusted.append(Beat(
                    time=mid_time,
                    strength=beats[i].strength * 0.8,
                    is_downbeat=False,
                    beat_number=beats[i].beat_number * 2 - 1,
                    measure=beats[i].measure,
                ))
            adjusted.append(beats[-1])
            return adjusted

        elif style == "half_time":
            # 半速：只保留强拍
            return [b for b in beats if b.is_downbeat]

        return beats

    # ------------------------------------------------------------------
    # 贝塞尔包络
    # ------------------------------------------------------------------

    def calculate_bezier_envelope(
        self,
        beat_time: float,
        attack_ms: float,
        decay_ms: float,
        peak_value: float,
        base_value: float,
        sample_rate: int = 30,
    ) -> List[Tuple[float, float]]:
        """
        计算贝塞尔包络线

        用于在节拍处生成平滑的关键帧过渡
        attack_ms: 攻击时间
        decay_ms: 衰减时间
        peak_value: 峰值
        base_value: 基准值

        返回: [(time, value), ...] 采样点列表
        """
        total_ms = attack_ms + decay_ms
        if total_ms <= 0:
            return [(beat_time, base_value)]

        attack_s = attack_ms / 1000.0
        decay_s = decay_ms / 1000.0
        total_s = total_ms / 1000.0
        dt = 1.0 / sample_rate
        num_attack = max(2, int(attack_s / dt))
        num_decay = max(2, int(decay_s / dt))

        samples: List[Tuple[float, float]] = []

        # Attack phase: 贝塞尔从 base_value 到 peak_value
        # 控制点: P0=(0, base), P1=(0.3*attack, peak), P2=(attack, peak)
        for k in range(num_attack + 1):
            t = k / num_attack
            # 二次贝塞尔: B(t) = (1-t)^2*P0 + 2*(1-t)*t*P1 + t^2*P2
            y = (
                (1 - t) ** 2 * base_value
                + 2 * (1 - t) * t * peak_value
                + t ** 2 * peak_value
            )
            time_offset = t * attack_s
            samples.append((round(beat_time + time_offset, 6), round(y, 6)))

        # Decay phase: 贝塞尔从 peak_value 到 base_value
        # 控制点: P0=(attack, peak), P1=(attack+0.4*decay, peak*0.3), P2=(attack+decay, base)
        for k in range(1, num_decay + 1):
            t = k / num_decay
            mid_val = peak_value * 0.3 + base_value * 0.7
            y = (
                (1 - t) ** 2 * peak_value
                + 2 * (1 - t) * t * mid_val
                + t ** 2 * base_value
            )
            time_offset = attack_s + t * decay_s
            samples.append((round(beat_time + time_offset, 6), round(y, 6)))

        return samples

    # ------------------------------------------------------------------
    # 关键帧密度优化
    # ------------------------------------------------------------------

    def optimize_keyframe_density(
        self,
        keyframes: List[KeyframeMapping],
        min_interval_ms: float = 50,
    ) -> List[KeyframeMapping]:
        """
        优化关键帧密度
        如果两个关键帧间隔太近，合并或删除冗余关键帧
        """
        if not keyframes:
            return []

        sorted_kf = sorted(keyframes, key=lambda k: k.time)
        result: List[KeyframeMapping] = [sorted_kf[0]]

        for kf in sorted_kf[1:]:
            prev = result[-1]
            interval = (kf.time - prev.time) * 1000.0

            if interval < min_interval_ms:
                # 合并：保留置信度更高的那个
                if kf.confidence > prev.confidence:
                    result[-1] = kf
                # 否则保留 prev，丢弃 kf
            else:
                result.append(kf)

        return result

    # ------------------------------------------------------------------
    # 映射质量验证
    # ------------------------------------------------------------------

    def validate_mapping(self, result: MappingResult) -> Dict:
        """
        验证映射结果质量
        返回: {
            "valid": bool,
            "issues": [...],
            "score": float,  # 0-100
            "average_offset_ms": float,
            "max_offset_ms": float,
            "coverage": float
        }
        """
        issues: List[str] = []
        max_allowed_offset = self.precision_ms * 5

        if not result.mappings:
            issues.append("无有效映射")
            return {
                "valid": False,
                "issues": issues,
                "score": 0.0,
                "average_offset_ms": 0.0,
                "max_offset_ms": 0.0,
                "coverage": 0.0,
            }

        offsets = [abs(m.offset_ms) for m in result.mappings]
        avg_offset = sum(offsets) / len(offsets)
        max_offset = max(offsets)

        # 评分维度
        offset_score = max(0, 100 - (avg_offset / max_allowed_offset) * 60)
        coverage_score = result.coverage * 100
        confidence_score = (
            sum(m.confidence for m in result.mappings) / len(result.mappings) * 100
        )

        # 综合得分
        score = offset_score * 0.4 + coverage_score * 0.3 + confidence_score * 0.3

        # 检查问题
        if max_offset > max_allowed_offset:
            issues.append(f"最大偏移 {max_offset:.1f}ms 超出阈值 {max_allowed_offset:.1f}ms")
        if avg_offset > max_allowed_offset * 0.5:
            issues.append(f"平均偏移 {avg_offset:.1f}ms 偏高")
        if result.coverage < 0.5:
            issues.append(f"节拍覆盖率 {result.coverage:.1%} 过低")
        low_conf = sum(1 for m in result.mappings if m.confidence < 0.3)
        if low_conf > len(result.mappings) * 0.3:
            issues.append(f"低置信度映射过多 ({low_conf}/{len(result.mappings)})")

        valid = len(issues) == 0 and score >= 40

        return {
            "valid": valid,
            "issues": issues,
            "score": round(score, 1),
            "average_offset_ms": round(avg_offset, 2),
            "max_offset_ms": round(max_offset, 2),
            "coverage": round(result.coverage, 3),
        }
