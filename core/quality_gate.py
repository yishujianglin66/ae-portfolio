"""
core/quality_gate.py — 质量门 (P4.2)
======================================

在管线 verify 阶段后对成片做多维度质量评估，输出 PASS / FAIL / WARN，
并给出修复建议（Mitigation）。

设计原则:
1. 规则可插拔: 内置 6 条规则，支持通过 add_rule 注册自定义规则
2. 离线纯 Python: 不依赖任何外部质量评估服务
3. 适配器模式: VMAF / 分辨率 / 时长等指标计算均 graceful degrade
4. 评分公式透明: 每条规则返回 0-1 分数 + 文本原因

集成方式:
    from core.quality_gate import get_quality_gate, QualityContext

    gate = get_quality_gate()
    ctx = QualityContext(
        output_path="output/final.mp4",
        vmaf_score=82.5,
        duration_sec=120.0,
        resolution=(1920, 1080),
        audio_peak_db=-1.2,
        file_size_mb=85.0,
        stages_success=True,
    )
    result = gate.evaluate(ctx)
    if result.status == "FAIL":
        for issue in gate.get_blocking_issues(result):
            print(issue)
"""
from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ============================================================================
#  数据类
# ============================================================================

@dataclass
class QualityContext:
    """质量评估上下文 - 封装待评估视频的所有指标

    Attributes:
        output_path: 输出视频路径
        vmaf_score: VMAF 分数 [0, 100]；None 表示未测
        duration_sec: 视频时长（秒）
        resolution: (width, height) 元组
        target_resolution: 目标 (width, height)；None 表示不校验
        audio_peak_db: 音频峰值 (dB)；None 表示未测
        file_size_mb: 文件大小 (MB)
        stages_success: 所有阶段是否成功
        extra: 额外上下文（如配置、元数据）
    """
    output_path: str = ""
    vmaf_score: Optional[float] = None
    duration_sec: float = 0.0
    resolution: Optional[Tuple[int, int]] = None
    target_resolution: Optional[Tuple[int, int]] = None
    audio_peak_db: Optional[float] = None
    file_size_mb: float = 0.0
    stages_success: bool = True
    extra: Dict[str, Any] = field(default_factory=dict)

    # 时长范围配置（可被规则读取）
    min_duration_sec: float = 5.0
    max_duration_sec: float = 600.0


@dataclass
class QualityIssue:
    """质量问题

    Attributes:
        rule_id: 触发的规则 ID
        severity: 严重度 ("error" / "warning" / "info")
        message: 问题描述
        actual: 实际值
        expected: 期望值
    """
    rule_id: str
    severity: str = "warning"
    message: str = ""
    actual: Any = None
    expected: Any = None


@dataclass
class Mitigation:
    """修复建议

    Attributes:
        issue_id: 关联的 rule_id
        action: 建议动作描述
        priority: 优先级 ("high" / "medium" / "low")
        estimated_effort: 预估工作量 ("trivial" / "moderate" / "significant")
    """
    issue_id: str
    action: str = ""
    priority: str = "medium"
    estimated_effort: str = "moderate"


@dataclass
class RuleResult:
    """单条规则评估结果

    Attributes:
        rule_id: 规则 ID
        rule_name: 规则名称
        passed: 是否通过
        score: 评分 [0, 1]
        severity: 失败时的严重度 ("error" / "warning" / "info")
        reason: 原因说明
        issue: 失败时关联的 QualityIssue (None 表示通过)
    """
    rule_id: str
    rule_name: str
    passed: bool
    score: float = 0.0
    severity: str = "info"
    reason: str = ""
    issue: Optional[QualityIssue] = None
    # 原子检查项拆解（atomic checks，向后兼容：默认空 dict 不影响旧规则）
    # 格式: {"check_name": {"passed": bool, "value": Any, "threshold": str}}
    atomic_checks: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QualityGateResult:
    """质量门整体评估结果

    Attributes:
        status: 总体状态 ("PASS" / "FAIL" / "WARN")
        overall_score: 综合评分 [0, 1]（所有规则分数的加权平均）
        rule_results: 每条规则的评估结果
        issues: 所有问题列表
        timestamp: 评估时间戳
    """
    status: str = "PASS"
    overall_score: float = 0.0
    rule_results: List[RuleResult] = field(default_factory=list)
    issues: List[QualityIssue] = field(default_factory=list)
    timestamp: float = 0.0

    @property
    def passed(self) -> bool:
        """是否通过质量门"""
        return self.status == "PASS"

    def to_atomic_report(self) -> Dict[str, Any]:
        """导出原子项级报告（VibeLifeBench atomic checks 思想）。

        逐项可判定、可定位、可统计；任一失败项可回溯到引入阶段
        （introduced_by 由规则层填充，默认 None）。向后兼容：
        旧规则无 atomic_checks 时退化为规则级条目。
        """
        items: List[Dict[str, Any]] = []
        for rr in self.rule_results:
            if rr.atomic_checks:
                for name, detail in rr.atomic_checks.items():
                    items.append({
                        "gate": rr.rule_id,
                        "check": name,
                        "passed": bool(detail.get("passed", False)),
                        "value": detail.get("value"),
                        "threshold": detail.get("threshold", ""),
                        "introduced_by": detail.get("introduced_by"),
                    })
            else:
                items.append({
                    "gate": rr.rule_id,
                    "check": rr.rule_id,
                    "passed": rr.passed,
                    "value": round(rr.score, 4),
                    "threshold": rr.reason,
                    "introduced_by": None,
                })
        return {
            "status": self.status,
            "overall_score": round(self.overall_score, 4),
            "atomic_checks": items,
            "atomic_summary": {
                "total": len(items),
                "passed": sum(1 for i in items if i["passed"]),
            },
            "timestamp": self.timestamp,
        }


# ============================================================================
#  规则接口与内置规则
# ============================================================================

class QualityRule:
    """质量规则基类

    子类必须实现 evaluate(context) -> RuleResult
    """
    rule_id: str = "base_rule"
    rule_name: str = "Base Rule"
    weight: float = 1.0  # 在综合评分中的权重

    def evaluate(self, context: QualityContext) -> RuleResult:
        """评估规则

        Args:
            context: 质量上下文

        Returns:
            RuleResult
        """
        raise NotImplementedError


class VmafThresholdRule(QualityRule):
    """VMAF 分数阈值规则

    评分公式:
        - score >= threshold: score = vmaf / 100, passed=True
        - score < threshold:  score = vmaf / 100, passed=False, severity=error
        - vmaf=None:          score=0.5, passed=True, severity=warning (未测量)
    """
    rule_id = "vmaf_threshold"
    rule_name = "VMAF Threshold"
    weight = 2.0

    def __init__(self, threshold: float = 70.0):
        self.threshold = threshold

    def evaluate(self, context: QualityContext) -> RuleResult:
        vmaf = context.vmaf_score
        if vmaf is None:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                passed=True,
                score=0.5,
                severity="warning",
                reason=f"VMAF 未测量，跳过评估（默认 0.5 分）",
            )
        score = max(0.0, min(1.0, vmaf / 100.0))
        passed = vmaf >= self.threshold
        if passed:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                passed=True,
                score=score,
                reason=f"VMAF={vmaf:.1f} ≥ {self.threshold}",
            )
        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            passed=False,
            score=score,
            severity="error",
            reason=f"VMAF={vmaf:.1f} < {self.threshold}",
            issue=QualityIssue(
                rule_id=self.rule_id,
                severity="error",
                message=f"VMAF 分数 {vmaf:.1f} 低于阈值 {self.threshold}",
                actual=vmaf,
                expected=self.threshold,
            ),
        )


class DurationRule(QualityRule):
    """成片时长范围规则"""
    rule_id = "duration_range"
    rule_name = "Duration Range"
    weight = 1.0

    def __init__(
        self,
        min_sec: float = 5.0,
        max_sec: float = 600.0,
    ):
        self.min_sec = min_sec
        self.max_sec = max_sec

    def evaluate(self, context: QualityContext) -> RuleResult:
        d = context.duration_sec
        # 优先使用 context 字段，回退到规则自身配置
        lo = context.min_duration_sec or self.min_sec
        hi = context.max_duration_sec or self.max_sec
        if d <= 0:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                passed=False,
                score=0.0,
                severity="error",
                reason=f"时长未测量或为 0",
                issue=QualityIssue(
                    rule_id=self.rule_id,
                    severity="error",
                    message="时长无效",
                    actual=d,
                    expected=f"[{lo}, {hi}]",
                ),
            )
        if d < lo:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                passed=False,
                score=0.3,
                severity="warning",
                reason=f"时长 {d:.1f}s < 最小 {lo}s",
                issue=QualityIssue(
                    rule_id=self.rule_id,
                    severity="warning",
                    message=f"时长过短: {d:.1f}s < {lo}s",
                    actual=d,
                    expected=lo,
                ),
            )
        if d > hi:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                passed=False,
                score=0.7,
                severity="warning",
                reason=f"时长 {d:.1f}s > 最大 {hi}s",
                issue=QualityIssue(
                    rule_id=self.rule_id,
                    severity="warning",
                    message=f"时长过长: {d:.1f}s > {hi}s",
                    actual=d,
                    expected=hi,
                ),
            )
        # 时长在范围内，分数按位置归一化
        score = 1.0 if hi == lo else max(0.7, 1.0 - abs(d - (lo + hi) / 2) / (hi - lo))
        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            passed=True,
            score=score,
            reason=f"时长 {d:.1f}s 在 [{lo}, {hi}] 范围内",
        )


class ResolutionRule(QualityRule):
    """输出分辨率规则

    比对实际分辨率与目标分辨率（宽高都需匹配，否则 WARN）。
    """
    rule_id = "resolution_match"
    rule_name = "Resolution Match"
    weight = 1.0

    def __init__(self, target: Optional[Tuple[int, int]] = None):
        self.target = target

    def evaluate(self, context: QualityContext) -> RuleResult:
        actual = context.resolution
        target = context.target_resolution or self.target
        if actual is None:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                passed=True,
                score=0.5,
                severity="warning",
                reason="分辨率未测量，跳过评估",
            )
        if target is None:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                passed=True,
                score=0.8,
                reason=f"无目标分辨率约束，实际={actual}",
            )
        if actual == target:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                passed=True,
                score=1.0,
                reason=f"分辨率匹配: {actual}",
            )
        # 宽高比一致但分辨率不同 → WARN；不一致 → ERROR
        ar_actual = actual[0] / max(1, actual[1])
        ar_target = target[0] / max(1, target[1])
        severity = "warning" if abs(ar_actual - ar_target) < 0.05 else "error"
        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            passed=False,
            score=0.4,
            severity=severity,
            reason=f"分辨率不匹配: actual={actual}, target={target}",
            issue=QualityIssue(
                rule_id=self.rule_id,
                severity=severity,
                message=f"分辨率 {actual} ≠ 目标 {target}",
                actual=actual,
                expected=target,
            ),
        )


class AudioPeakRule(QualityRule):
    """音频峰值规则 - 防止削波 (clipping)

    0 dB 是数字音频上限；峰值超过 -0.5 dB 视为有削波风险。
    """
    rule_id = "audio_peak"
    rule_name = "Audio Peak"
    weight = 1.0

    def __init__(self, max_peak_db: float = -0.5):
        self.max_peak_db = max_peak_db

    def evaluate(self, context: QualityContext) -> RuleResult:
        peak = context.audio_peak_db
        if peak is None:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                passed=True,
                score=0.5,
                severity="warning",
                reason="音频峰值未测量，跳过评估",
            )
        if peak > 0:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                passed=False,
                score=0.0,
                severity="error",
                reason=f"音频削波: peak={peak}dB > 0dB",
                issue=QualityIssue(
                    rule_id=self.rule_id,
                    severity="error",
                    message=f"音频已削波 (peak={peak}dB)",
                    actual=peak,
                    expected="≤ 0 dB",
                ),
            )
        if peak > self.max_peak_db:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                passed=False,
                score=0.4,
                severity="warning",
                reason=f"音频峰值临界: peak={peak}dB > {self.max_peak_db}dB",
                issue=QualityIssue(
                    rule_id=self.rule_id,
                    severity="warning",
                    message=f"音频峰值临界削波 (peak={peak}dB)",
                    actual=peak,
                    expected=f"≤ {self.max_peak_db} dB",
                ),
            )
        # 峰值越低越安全，但过低意味着响度不足
        if peak < -24:
            score = 0.7
        else:
            score = 1.0 - max(0, (peak + 6) / -6) * 0.3
        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            passed=True,
            score=score,
            reason=f"音频峰值正常: {peak}dB ≤ {self.max_peak_db}dB",
        )


class FileSizeRule(QualityRule):
    """文件大小合理性规则

    基于时长估算合理范围:
        estimated_size_mb = duration_sec * bitrate_mbps * 1/8 * 1.05 (5% 容差)
        若实际大小在 [0.4 * est, 2.0 * est] 内则 PASS
    预估码率取 3.0 Mbps（贴近项目 ≥3314kbps 规范与 CRF18 恒定质量
    实际产物），下界放宽至 0.4 倍，为短视频/低复杂度内容的 CRF 浮动留余量。
    """
    rule_id = "file_size"
    rule_name = "File Size Reasonable"
    weight = 0.5

    def __init__(self, assumed_bitrate_mbps: float = 3.0):
        self.assumed_bitrate_mbps = assumed_bitrate_mbps

    def evaluate(self, context: QualityContext) -> RuleResult:
        size = context.file_size_mb
        if size <= 0 or context.duration_sec <= 0:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                passed=True,
                score=0.5,
                severity="warning",
                reason="文件大小或时长未知，跳过评估",
            )
        estimated = context.duration_sec * self.assumed_bitrate_mbps / 8.0 * 1.05
        lo = 0.4 * estimated
        hi = 2.0 * estimated
        if size < lo:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                passed=False,
                score=0.5,
                severity="warning",
                reason=f"文件过小: {size:.1f}MB < 预估下限 {lo:.1f}MB",
                issue=QualityIssue(
                    rule_id=self.rule_id,
                    severity="warning",
                    message=f"文件过小，可能码率过低",
                    actual=size,
                    expected=f"≥ {lo:.1f} MB",
                ),
            )
        if size > hi:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                passed=False,
                score=0.6,
                severity="warning",
                reason=f"文件过大: {size:.1f}MB > 预估上限 {hi:.1f}MB",
                issue=QualityIssue(
                    rule_id=self.rule_id,
                    severity="warning",
                    message=f"文件过大，可能码率过高或编码低效",
                    actual=size,
                    expected=f"≤ {hi:.1f} MB",
                ),
            )
        # 越接近 estimated 越好
        ratio = size / max(0.01, estimated)
        score = max(0.7, 1.0 - abs(1.0 - ratio) * 0.5)
        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            passed=True,
            score=score,
            reason=f"文件大小合理: {size:.1f}MB ≈ 预估 {estimated:.1f}MB",
        )


class StageSuccessRule(QualityRule):
    """阶段成功规则 - 所有阶段必须成功"""
    rule_id = "stage_success"
    rule_name = "All Stages Success"
    weight = 3.0

    def evaluate(self, context: QualityContext) -> RuleResult:
        if context.stages_success:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                passed=True,
                score=1.0,
                reason="所有阶段成功完成",
            )
        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            passed=False,
            score=0.0,
            severity="error",
            reason="存在失败阶段",
            issue=QualityIssue(
                rule_id=self.rule_id,
                severity="error",
                message="管线存在失败阶段，成片质量不可信",
                actual=False,
                expected=True,
            ),
        )


# ============================================================================
#  旗舰管线专用质量规则 (QG-1 / QG-4 / QG-5)
# ============================================================================

class FrameLuminanceRule(QualityRule):
    """旗舰 QG-1：帧亮度采样规则

    OpenCV 20 帧均匀抽样 → 平均亮度 ∈ [0.05, 0.95]，帧方差 ≥ 0.02。
    防止全黑/全白/静帧视频通过质量门。
    """
    rule_id = "frame_luminance"
    rule_name = "QG-1 Frame Luminance"
    weight = 2.0

    def __init__(
        self,
        min_brightness: float = 0.05,
        max_brightness: float = 0.95,
        min_variance: float = 0.02,
        sample_count: int = 20,
    ):
        self.min_brightness = min_brightness
        self.max_brightness = max_brightness
        self.min_variance = min_variance
        self.sample_count = sample_count

    def evaluate(self, context: QualityContext) -> RuleResult:
        video_path = context.output_path
        if not video_path or not Path(video_path).exists():
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                passed=True,
                score=0.5,
                severity="warning",
                reason="视频文件不存在，跳过亮度检测",
            )

        try:
            import cv2
            import numpy as np
        except ImportError:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                passed=True,
                score=0.5,
                severity="warning",
                reason="OpenCV/numpy 不可用，跳过亮度检测",
            )

        cap = cv2.VideoCapture(str(video_path))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames <= 0:
            cap.release()
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                passed=False,
                score=0.0,
                severity="error",
                reason="无法读取视频帧",
                issue=QualityIssue(
                    rule_id=self.rule_id,
                    severity="error",
                    message="视频文件无法解码",
                ),
            )

        # 均匀抽样
        indices = np.linspace(0, total_frames - 1, self.sample_count, dtype=int)
        luminances = []
        for idx in indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
            ret, frame = cap.read()
            if ret:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                luminances.append(gray.mean() / 255.0)
        cap.release()

        if not luminances:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                passed=False,
                score=0.0,
                severity="error",
                reason="无法采样任何帧",
            )

        avg_lum = float(np.mean(luminances))
        var_lum = float(np.var(luminances))

        # 判定
        issues_found = []
        if avg_lum < self.min_brightness:
            issues_found.append(f"平均亮度 {avg_lum:.3f} < {self.min_brightness}（过暗）")
        if avg_lum > self.max_brightness:
            issues_found.append(f"平均亮度 {avg_lum:.3f} > {self.max_brightness}（过亮）")
        if var_lum < self.min_variance:
            issues_found.append(f"帧方差 {var_lum:.4f} < {self.min_variance}（疑似静帧）")

        if issues_found:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                passed=False,
                score=0.2,
                severity="error",
                reason="; ".join(issues_found),
                issue=QualityIssue(
                    rule_id=self.rule_id,
                    severity="error",
                    message="; ".join(issues_found),
                    actual={"avg_luminance": avg_lum, "variance": var_lum},
                    expected={"brightness": [self.min_brightness, self.max_brightness], "min_var": self.min_variance},
                ),
            )

        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            passed=True,
            score=1.0,
            reason=f"亮度正常: avg={avg_lum:.3f}, var={var_lum:.4f}",
        )


class BeatAlignmentRule(QualityRule):
    """旗舰 QG-4：节拍对齐规则

    解析 S2 beats.json drops vs S4 timeline.xml 标记点，
    每个 drop 点偏移 < 80ms 则通过。
    """
    rule_id = "beat_alignment"
    rule_name = "QG-4 Beat Alignment"
    weight = 2.0

    def __init__(self, max_offset_ms: float = 80.0):
        self.max_offset_ms = max_offset_ms

    def evaluate(self, context: QualityContext) -> RuleResult:
        import json as _json

        extra = context.extra or {}
        beats_json_path = extra.get("beats_json_path")
        timeline_xml_path = extra.get("timeline_xml_path")

        if not beats_json_path or not timeline_xml_path:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                passed=True,
                score=0.5,
                severity="warning",
                reason="缺少 beats_json_path 或 timeline_xml_path，跳过对齐检测",
            )

        beats_path = Path(beats_json_path)
        xml_path = Path(timeline_xml_path)

        if not beats_path.exists():
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                passed=True,
                score=0.5,
                severity="warning",
                reason=f"beats.json 不存在: {beats_path}",
            )

        if not xml_path.exists():
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                passed=True,
                score=0.5,
                severity="warning",
                reason=f"timeline.xml 不存在: {xml_path}",
            )

        # 解析 beats.json drops
        try:
            beats_data = _json.loads(beats_path.read_text(encoding="utf-8"))
            drops = beats_data.get("drops", [])
        except (ValueError, OSError):
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                passed=True,
                score=0.5,
                severity="warning",
                reason="beats.json 解析失败",
            )

        if not drops:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                passed=True,
                score=0.5,
                severity="warning",
                reason="beats.json 无 drops 数据",
            )

        # 解析 timeline.xml 标记点（FCP XML 格式）
        marker_times = self._parse_xml_markers(xml_path)
        if not marker_times:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                passed=True,
                score=0.5,
                severity="warning",
                reason="timeline.xml 无标记点数据",
            )

        # 计算每个 drop 与最近标记的偏移
        max_offset = 0.0
        offsets = []
        for drop_t in drops:
            min_diff = min(abs(drop_t - mt) for mt in marker_times)
            offsets.append(min_diff)
            max_offset = max(max_offset, min_diff)

        max_offset_ms = max_offset * 1000.0
        passed = max_offset_ms < self.max_offset_ms

        if passed:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                passed=True,
                score=1.0,
                reason=f"节拍对齐: 最大偏移 {max_offset_ms:.1f}ms < {self.max_offset_ms}ms",
            )

        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            passed=False,
            score=0.3,
            severity="error",
            reason=f"节拍偏移过大: {max_offset_ms:.1f}ms ≥ {self.max_offset_ms}ms",
            issue=QualityIssue(
                rule_id=self.rule_id,
                severity="error",
                message=f"最大节拍偏移 {max_offset_ms:.1f}ms 超过阈值 {self.max_offset_ms}ms",
                actual=max_offset_ms,
                expected=self.max_offset_ms,
            ),
        )

    @staticmethod
    def _parse_xml_markers(xml_path: Path) -> List[float]:
        """从 FCP XML 解析标记点时间（秒）。"""
        import xml.etree.ElementTree as ET

        markers: List[float] = []
        try:
            tree = ET.parse(str(xml_path))
            root = tree.getroot()
            # FCP XML: <markeritem><start>ticks</start></markeritem>
            # 或 <marker><start>...</start></marker>
            for elem in root.iter():
                if elem.tag in ("markeritem", "marker"):
                    start_elem = elem.find("start")
                    if start_elem is not None and start_elem.text:
                        try:
                            # FCP XML 时间单位可能是 ticks 或秒
                            val = float(start_elem.text)
                            # 如果值很大，可能是 ticks (254016000000/s)
                            if val > 10000:
                                val = val / 254016000000.0
                            markers.append(val)
                        except ValueError:
                            pass
        except (ET.ParseError, OSError):
            pass
        return markers


class GradeNodeRule(QualityRule):
    """旗舰 QG-5：调色节点解析规则

    检查 DaVinci 调色节点数 ≥ 3 且含 LUT 类型。
    通过 context.extra 传入 grade_metadata。
    """
    rule_id = "grade_nodes"
    rule_name = "QG-5 Grade Nodes"
    weight = 1.5

    def __init__(self, min_nodes: int = 3, require_lut: bool = True):
        self.min_nodes = min_nodes
        self.require_lut = require_lut

    def evaluate(self, context: QualityContext) -> RuleResult:
        extra = context.extra or {}
        grade_meta = extra.get("grade_metadata")

        if not grade_meta:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                passed=True,
                score=0.5,
                severity="warning",
                reason="无调色元数据，跳过节点检测",
            )

        node_count = grade_meta.get("node_count", 0)
        has_lut = grade_meta.get("include_lut", False)
        nodes = grade_meta.get("nodes_applied", [])

        issues_found = []
        if node_count < self.min_nodes:
            issues_found.append(f"节点数 {node_count} < {self.min_nodes}")
        if self.require_lut and not has_lut:
            issues_found.append("缺少 LUT 节点")

        if issues_found:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                passed=False,
                score=0.2,
                severity="error",
                reason="; ".join(issues_found),
                issue=QualityIssue(
                    rule_id=self.rule_id,
                    severity="error",
                    message="; ".join(issues_found),
                    actual={"node_count": node_count, "has_lut": has_lut},
                    expected={"min_nodes": self.min_nodes, "require_lut": self.require_lut},
                ),
            )

        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            passed=True,
            score=1.0,
            reason=f"调色节点合规: {node_count} 节点, LUT={'Yes' if has_lut else 'No'}",
        )


class OverallQualityRule(QualityRule):
    """整体质量分硬规则 — 统一 verify 实测分与 QualityGate 门状态口径

    读取 context.extra["overall_score"]（VideoQualityAssessor 实测综合分 0-100，
    或等效的整体分）作为唯一硬性门槛：低于阈值 → FAIL(error)；
    无实测分时 warning 跳过（0.5 分），避免数据缺失误判。

    引入背景（统一两套质量体系）:
    - verify 阶段以 VideoQualityAssessor.passed（实测分 ≥ min）判定通过
    - QualityGate 此前只做"附加诊断"，status 与实测分结论互相独立，
      出现 "QualityGate FAIL" 与 "Quality gate score=70.6 passed=True" 打架。
    - 本规则让 QualityGate 的 status 直接反映实测分是否达标，两套口径一致。
    """
    rule_id = "overall_quality"
    rule_name = "Overall Quality Score"
    weight = 3.0

    def __init__(self, threshold: float = 60.0):
        self.threshold = threshold

    def evaluate(self, context: QualityContext) -> RuleResult:
        extra = context.extra or {}
        raw = extra.get("overall_score")
        if raw is None:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                passed=True,
                score=0.5,
                severity="warning",
                reason="整体质量分未测量，跳过评估",
            )
        try:
            score100 = float(raw)
        except (TypeError, ValueError):
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                passed=True,
                score=0.5,
                severity="warning",
                reason=f"整体质量分非数值: {raw!r}，跳过评估",
            )
        threshold = float(extra.get("min_score") or self.threshold)
        score = max(0.0, min(1.0, score100 / 100.0))
        if score100 >= threshold:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                passed=True,
                score=score,
                reason=f"整体质量分 {score100:.1f} ≥ {threshold}",
            )
        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            passed=False,
            score=score,
            severity="error",
            reason=f"整体质量分 {score100:.1f} < {threshold}",
            issue=QualityIssue(
                rule_id=self.rule_id,
                severity="error",
                message=f"整体质量分 {score100:.1f} 低于阈值 {threshold}",
                actual=score100,
                expected=threshold,
            ),
        )


# ============================================================================
#  QualityGate
# ============================================================================

class QualityGate:
    """质量门 - 评估视频成片的多维度质量

    使用流程:
        1. 创建 QualityGate 实例（或用 get_quality_gate 单例）
        2. 调用 evaluate(context) 评估
        3. 通过 result.status 判断 PASS / FAIL / WARN
        4. 通过 get_blocking_issues / suggest_mitigations 获取修复建议

    评分公式:
        overall_score = Σ(rule_score_i * weight_i) / Σ(weight_i)
        status:
            - 任意 error 级别规则失败 → FAIL
            - 任意 warning 级别规则失败 → WARN
            - 全部规则通过 → PASS
    """

    def __init__(self):
        self._rules: List[QualityRule] = []
        # 注册内置规则
        self._register_builtin_rules()

    def _register_builtin_rules(self) -> None:
        """注册内置规则（含整体质量分硬规则，统一 verify 实测分与门状态口径）"""
        self._rules.extend([
            VmafThresholdRule(),
            DurationRule(),
            ResolutionRule(),
            AudioPeakRule(),
            FileSizeRule(),
            StageSuccessRule(),
            OverallQualityRule(),
        ])

    def add_rule(self, rule: QualityRule) -> None:
        """添加自定义质量规则

        Args:
            rule: QualityRule 实例
        """
        if not isinstance(rule, QualityRule):
            raise TypeError(f"rule must be QualityRule, got {type(rule)}")
        self._rules.append(rule)
        logger.debug("[QualityGate] rule added: %s", rule.rule_id)

    def remove_rule(self, rule_id: str) -> bool:
        """移除规则

        Args:
            rule_id: 规则 ID

        Returns:
            是否成功移除
        """
        for i, r in enumerate(self._rules):
            if r.rule_id == rule_id:
                self._rules.pop(i)
                return True
        return False

    def list_rules(self) -> List[str]:
        """列出所有规则 ID"""
        return [r.rule_id for r in self._rules]

    def evaluate(self, context: QualityContext) -> QualityGateResult:
        """评估所有规则

        Args:
            context: 质量上下文

        Returns:
            QualityGateResult
        """
        import time
        rule_results: List[RuleResult] = []
        issues: List[QualityIssue] = []
        total_weighted = 0.0
        total_weight = 0.0
        has_error = False
        has_warning = False

        for rule in self._rules:
            try:
                rr = rule.evaluate(context)
            except Exception as e:
                logger.warning("[QualityGate] rule %s failed: %s", rule.rule_id, e)
                rr = RuleResult(
                    rule_id=rule.rule_id,
                    rule_name=rule.rule_name,
                    passed=True,
                    score=0.5,
                    severity="warning",
                    reason=f"规则评估异常: {e}",
                )
            rule_results.append(rr)
            total_weighted += rr.score * rule.weight
            total_weight += rule.weight
            if not rr.passed:
                if rr.issue is not None:
                    issues.append(rr.issue)
                # 根据 severity 设置标志，即使 issue 为 None 也应触发 FAIL/WARN
                if rr.severity == "error":
                    has_error = True
                elif rr.severity == "warning":
                    has_warning = True

        overall = total_weighted / total_weight if total_weight > 0 else 0.0
        if has_error:
            status = "FAIL"
        elif has_warning:
            status = "WARN"
        else:
            status = "PASS"

        return QualityGateResult(
            status=status,
            overall_score=overall,
            rule_results=rule_results,
            issues=issues,
            timestamp=time.time(),
        )

    def get_blocking_issues(
        self,
        result: QualityGateResult,
    ) -> List[QualityIssue]:
        """获取阻塞性问题（severity=error 的问题）

        Args:
            result: QualityGateResult

        Returns:
            阻塞性问题列表
        """
        return [i for i in result.issues if i.severity == "error"]

    def suggest_mitigations(
        self,
        result: QualityGateResult,
    ) -> List[Mitigation]:
        """根据问题生成修复建议

        Args:
            result: QualityGateResult

        Returns:
            修复建议列表
        """
        mitigations: List[Mitigation] = []
        # 内置修复策略表
        strategy = {
            "vmaf_threshold": Mitigation(
                issue_id="vmaf_threshold",
                action="提升渲染质量参数: 增加码率、启用更高 CRF、检查源素材质量",
                priority="high",
                estimated_effort="moderate",
            ),
            "duration_range": Mitigation(
                issue_id="duration_range",
                action="调整素材剪辑时长: 重新审视脚本节奏，增删片段",
                priority="medium",
                estimated_effort="moderate",
            ),
            "resolution_match": Mitigation(
                issue_id="resolution_match",
                action="重新渲染至目标分辨率，或修改发布平台目标",
                priority="high",
                estimated_effort="trivial",
            ),
            "audio_peak": Mitigation(
                issue_id="audio_peak",
                action="应用限幅器 (limiter) 或降低整体音量 1-3 dB",
                priority="high",
                estimated_effort="trivial",
            ),
            "file_size": Mitigation(
                issue_id="file_size",
                action="调整编码参数 (CRF / 预设) 以匹配目标码率",
                priority="low",
                estimated_effort="moderate",
            ),
            "stage_success": Mitigation(
                issue_id="stage_success",
                action="重跑失败阶段，参考失败日志定位根因",
                priority="high",
                estimated_effort="significant",
            ),
        }
        for issue in result.issues:
            m = strategy.get(issue.rule_id)
            if m is None:
                m = Mitigation(
                    issue_id=issue.rule_id,
                    action=f"检查 {issue.rule_id} 规则详情: {issue.message}",
                    priority="medium" if issue.severity == "warning" else "high",
                    estimated_effort="moderate",
                )
            mitigations.append(m)
        return mitigations


# ============================================================================
#  全局单例
# ============================================================================

_global_quality_gate: Optional[QualityGate] = None
_global_quality_gate_lock = threading.Lock()


def get_quality_gate() -> QualityGate:
    """获取全局 QualityGate 单例

    Returns:
        QualityGate 实例
    """
    global _global_quality_gate
    # D8 修复: double-checked locking, 防止多线程首次调用创建多个实例
    if _global_quality_gate is None:
        with _global_quality_gate_lock:
            if _global_quality_gate is None:
                _global_quality_gate = QualityGate()
    return _global_quality_gate


def reset_quality_gate() -> None:
    """重置全局 QualityGate（仅用于测试）"""
    global _global_quality_gate
    _global_quality_gate = None
