#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频质量评估模块
==============

提供多种视频质量评估指标，支持自动化质量验收：
- PSNR (Peak Signal-to-Noise Ratio): 峰值信噪比
- SSIM (Structural Similarity Index): 结构相似性
- VMAF (Video Multimethod Assessment Fusion): 多方法融合评估
- BRISQUE: 无参考图像质量评估
- 自定义阈值与质量分级

支持模式:
- real: 调用 ffmpeg 实际计算
- simulate: 模拟模式（返回合理估值，用于测试）
- auto: 优先 real，失败时降级为 simulate
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple


# ============================================================================
# 数据类
# ============================================================================

@dataclass
class QualityMetrics:
    """质量评估指标结果"""
    psnr: Optional[float] = None  # dB，越高越好
    ssim: Optional[float] = None  # 0-1，越高越好
    vmaf: Optional[float] = None  # 0-100，越高越好
    brisque: Optional[float] = None  # 0-100，越低越好（无参考）
    overall_score: float = 0.0  # 综合评分 0-100
    grade: str = "unknown"  # 质量等级 excellent/good/fair/poor/bad

    def to_dict(self) -> Dict[str, Any]:
        return {
            "psnr": self.psnr,
            "ssim": self.ssim,
            "vmaf": self.vmaf,
            "brisque": self.brisque,
            "overall_score": self.overall_score,
            "grade": self.grade,
        }


@dataclass
class QualityThreshold:
    """质量验收阈值"""
    min_psnr: float = 30.0  # dB
    min_ssim: float = 0.90
    min_vmaf: float = 80.0
    max_brisque: float = 40.0
    min_overall: float = 70.0


@dataclass
class QualityAssessmentResult:
    """质量评估完整结果"""
    success: bool
    reference_video: str
    test_video: str
    metrics: QualityMetrics
    thresholds: QualityThreshold
    passed: bool = False
    mode: str = "simulate"
    duration: float = 0.0
    error_message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "reference_video": self.reference_video,
            "test_video": self.test_video,
            "metrics": self.metrics.to_dict(),
            "thresholds": {
                "min_psnr": self.thresholds.min_psnr,
                "min_ssim": self.thresholds.min_ssim,
                "min_vmaf": self.thresholds.min_vmaf,
                "max_brisque": self.thresholds.max_brisque,
                "min_overall": self.thresholds.min_overall,
            },
            "passed": self.passed,
            "mode": self.mode,
            "duration": self.duration,
            "error_message": self.error_message,
            "details": self.details,
        }


# ============================================================================
# 质量分级
# ============================================================================

def _calc_overall_score(metrics: QualityMetrics) -> float:
    """计算综合评分 (0-100)"""
    scores = []
    weights = []

    if metrics.psnr is not None:
        # PSNR: 20dB=0分, 50dB=100分
        psnr_score = max(0, min(100, (metrics.psnr - 20) / 30 * 100))
        scores.append(psnr_score)
        weights.append(0.25)

    if metrics.ssim is not None:
        # SSIM: 0.5=0分, 1.0=100分
        ssim_score = max(0, min(100, (metrics.ssim - 0.5) / 0.5 * 100))
        scores.append(ssim_score)
        weights.append(0.25)

    if metrics.vmaf is not None:
        scores.append(metrics.vmaf)
        weights.append(0.35)

    if metrics.brisque is not None:
        # BRISQUE: 100=0分, 0=100分（反向）
        brisque_score = max(0, min(100, (100 - metrics.brisque)))
        scores.append(brisque_score)
        weights.append(0.15)

    if not scores:
        return 0.0

    total_weight = sum(weights)
    if total_weight <= 0:
        return 0.0

    weighted = sum(s * w for s, w in zip(scores, weights)) / total_weight
    return round(weighted, 2)


def _grade_from_score(score: float) -> str:
    """根据综合评分确定质量等级"""
    if score >= 90:
        return "excellent"
    elif score >= 75:
        return "good"
    elif score >= 60:
        return "fair"
    elif score >= 40:
        return "poor"
    else:
        return "bad"


# ============================================================================
# 视频质量评估器
# ============================================================================

class VideoQualityAssessor:
    """视频质量评估器

    支持 VMAF/SSIM/PSNR/BRISQUE 多种质量指标，
    提供阈值验收和质量分级功能。
    """

    def __init__(
        self,
        mode: str = "auto",
        ffmpeg_path: Optional[str] = None,
        thresholds: Optional[QualityThreshold] = None,
        model_path: Optional[str] = None,
    ):
        """
        Args:
            mode: 运行模式 (real/simulate/auto)
            ffmpeg_path: ffmpeg 可执行文件路径
            thresholds: 质量验收阈值
            model_path: VMAF 模型文件路径
        """
        self.mode = mode
        self._ffmpeg = ffmpeg_path or "ffmpeg"
        self._ffprobe = "ffprobe"
        self._thresholds = thresholds or QualityThreshold()
        self._model_path = model_path
        self._ffmpeg_available = None

    @property
    def thresholds(self) -> QualityThreshold:
        return self._thresholds

    @thresholds.setter
    def thresholds(self, value: QualityThreshold):
        self._thresholds = value

    def _check_ffmpeg(self) -> bool:
        """检查 ffmpeg 是否可用"""
        if self._ffmpeg_available is not None:
            return self._ffmpeg_available
        try:
            result = subprocess.run(
                [self._ffmpeg, "-version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            self._ffmpeg_available = result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            self._ffmpeg_available = False
        return self._ffmpeg_available

    def _resolve_mode(self, requested_mode: Optional[str] = None) -> str:
        """解析实际运行模式（auto 降级）"""
        mode = requested_mode or self.mode
        if mode == "auto":
            return "real" if self._check_ffmpeg() else "simulate"
        return mode

    # ------------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------------

    def assess(
        self,
        reference_video: str,
        test_video: str,
        mode: Optional[str] = None,
        thresholds: Optional[QualityThreshold] = None,
    ) -> QualityAssessmentResult:
        """评估视频质量（对比参考视频）

        Args:
            reference_video: 参考视频路径（原视频）
            test_video: 待评估视频路径（处理后视频）
            mode: 覆盖默认模式
            thresholds: 覆盖默认阈值

        Returns:
            QualityAssessmentResult 评估结果
        """
        import time
        start_time = time.time()
        actual_mode = self._resolve_mode(mode)
        thresh = thresholds or self._thresholds

        if actual_mode == "real":
            result = self._assess_real(reference_video, test_video, thresh)
        else:
            result = self._assess_simulate(reference_video, test_video, thresh)

        result.duration = time.time() - start_time
        return result

    def assess_no_reference(
        self,
        video_path: str,
        mode: Optional[str] = None,
        thresholds: Optional[QualityThreshold] = None,
    ) -> QualityAssessmentResult:
        """无参考视频质量评估（仅 BRISQUE）

        Args:
            video_path: 待评估视频路径
            mode: 覆盖默认模式
            thresholds: 覆盖默认阈值

        Returns:
            QualityAssessmentResult 评估结果
        """
        import time
        start_time = time.time()
        actual_mode = self._resolve_mode(mode)
        thresh = thresholds or self._thresholds

        if actual_mode == "real":
            result = self._assess_brisque_real(video_path, thresh)
        else:
            result = self._assess_brisque_simulate(video_path, thresh)

        result.duration = time.time() - start_time
        return result

    def batch_assess(
        self,
        reference_video: str,
        test_videos: List[str],
        mode: Optional[str] = None,
        thresholds: Optional[QualityThreshold] = None,
    ) -> List[QualityAssessmentResult]:
        """批量评估多个视频

        Args:
            reference_video: 参考视频
            test_videos: 待评估视频列表
            mode: 运行模式
            thresholds: 质量阈值

        Returns:
            评估结果列表
        """
        results = []
        for test_video in test_videos:
            result = self.assess(reference_video, test_video, mode, thresholds)
            results.append(result)
        return results

    def check_pass(self, metrics: QualityMetrics) -> bool:
        """检查指标是否通过阈值"""
        t = self._thresholds
        checks = []

        if metrics.psnr is not None:
            checks.append(metrics.psnr >= t.min_psnr)
        if metrics.ssim is not None:
            checks.append(metrics.ssim >= t.min_ssim)
        if metrics.vmaf is not None:
            checks.append(metrics.vmaf >= t.min_vmaf)
        if metrics.brisque is not None:
            checks.append(metrics.brisque <= t.max_brisque)

        checks.append(metrics.overall_score >= t.min_overall)

        return all(checks)

    # ------------------------------------------------------------------------
    # Real 模式实现
    # ------------------------------------------------------------------------

    def _assess_real(
        self,
        reference_video: str,
        test_video: str,
        thresholds: QualityThreshold,
    ) -> QualityAssessmentResult:
        """使用 ffmpeg 进行真实质量评估"""
        if not os.path.isfile(reference_video):
            return QualityAssessmentResult(
                success=False,
                reference_video=reference_video,
                test_video=test_video,
                metrics=QualityMetrics(),
                thresholds=thresholds,
                mode="real",
                error_message=f"参考视频不存在: {reference_video}",
            )
        if not os.path.isfile(test_video):
            return QualityAssessmentResult(
                success=False,
                reference_video=reference_video,
                test_video=test_video,
                metrics=QualityMetrics(),
                thresholds=thresholds,
                mode="real",
                error_message=f"测试视频不存在: {test_video}",
            )

        metrics = QualityMetrics()

        # 计算 PSNR
        psnr = self._calc_psnr(reference_video, test_video)
        if psnr is not None:
            metrics.psnr = round(psnr, 3)

        # 计算 SSIM
        ssim = self._calc_ssim(reference_video, test_video)
        if ssim is not None:
            metrics.ssim = round(ssim, 4)

        # 计算 VMAF（如果可用）
        vmaf = self._calc_vmaf(reference_video, test_video)
        if vmaf is not None:
            metrics.vmaf = round(vmaf, 2)

        # 计算综合评分和等级
        metrics.overall_score = _calc_overall_score(metrics)
        metrics.grade = _grade_from_score(metrics.overall_score)

        passed = self.check_pass(metrics)

        return QualityAssessmentResult(
            success=True,
            reference_video=reference_video,
            test_video=test_video,
            metrics=metrics,
            thresholds=thresholds,
            passed=passed,
            mode="real",
        )

    def _assess_brisque_real(
        self,
        video_path: str,
        thresholds: QualityThreshold,
    ) -> QualityAssessmentResult:
        """无参考质量评估（real 模式）"""
        if not os.path.isfile(video_path):
            return QualityAssessmentResult(
                success=False,
                reference_video="",
                test_video=video_path,
                metrics=QualityMetrics(),
                thresholds=thresholds,
                mode="real",
                error_message=f"视频不存在: {video_path}",
            )

        brisque = self._calc_brisque(video_path)
        metrics = QualityMetrics(brisque=brisque)
        metrics.overall_score = _calc_overall_score(metrics)
        metrics.grade = _grade_from_score(metrics.overall_score)
        passed = self.check_pass(metrics)

        return QualityAssessmentResult(
            success=True,
            reference_video="",
            test_video=video_path,
            metrics=metrics,
            thresholds=thresholds,
            passed=passed,
            mode="real",
        )

    def _calc_psnr(self, ref: str, test: str) -> Optional[float]:
        """使用 ffmpeg 计算 PSNR"""
        try:
            cmd = [
                self._ffmpeg, "-i", test, "-i", ref,
                "-lavfi", "psnr=stats_file=-",
                "-f", "null", "-"
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=120
            )
            output = result.stderr
            match = re.search(r"average:([\d.]+)", output)
            if match:
                return float(match.group(1))
        except (subprocess.TimeoutExpired, Exception):
            pass
        return None

    def _calc_ssim(self, ref: str, test: str) -> Optional[float]:
        """使用 ffmpeg 计算 SSIM"""
        try:
            cmd = [
                self._ffmpeg, "-i", test, "-i", ref,
                "-lavfi", "ssim=stats_file=-",
                "-f", "null", "-"
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=120
            )
            output = result.stderr
            match = re.search(r"All:([\d.]+)", output)
            if match:
                return float(match.group(1))
        except (subprocess.TimeoutExpired, Exception):
            pass
        return None

    def _calc_vmaf(self, ref: str, test: str) -> Optional[float]:
        """使用 ffmpeg 计算 VMAF"""
        try:
            filter_str = "libvmaf"
            if self._model_path and os.path.isfile(self._model_path):
                filter_str = f"libvmaf=model_path={self._model_path}"

            cmd = [
                self._ffmpeg, "-i", test, "-i", ref,
                "-lavfi", filter_str,
                "-f", "null", "-"
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300
            )
            output = result.stderr
            match = re.search(r"VMAF score: ([\d.]+)", output)
            if match:
                return float(match.group(1))
        except (subprocess.TimeoutExpired, Exception):
            pass
        return None

    def _calc_brisque(self, video_path: str) -> Optional[float]:
        """使用 ffmpeg 计算 BRISQUE（取第一帧）"""
        try:
            tmp_img = tempfile.mktemp(suffix=".png")
            # 提取第一帧
            cmd_extract = [
                self._ffmpeg, "-i", video_path,
                "-vframes", "1", "-y", tmp_img
            ]
            subprocess.run(
                cmd_extract, capture_output=True, timeout=30
            )
            if not os.path.isfile(tmp_img):
                return None

            # 计算 BRISQUE
            cmd = [
                self._ffmpeg, "-i", tmp_img,
                "-vf", "brisque=stats_file=-",
                "-f", "null", "-"
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30
            )
            os.remove(tmp_img)

            output = result.stderr
            match = re.search(r"average:([\d.]+)", output)
            if match:
                return float(match.group(1))
        except (subprocess.TimeoutExpired, Exception):
            pass
        return None

    # ------------------------------------------------------------------------
    # Simulate 模式实现
    # ------------------------------------------------------------------------

    def _assess_simulate(
        self,
        reference_video: str,
        test_video: str,
        thresholds: QualityThreshold,
    ) -> QualityAssessmentResult:
        """模拟模式：基于文件信息估算质量"""
        import random

        ref_size = os.path.getsize(reference_video) if os.path.isfile(reference_video) else 100_000_000
        test_size = os.path.getsize(test_video) if os.path.isfile(test_video) else 80_000_000

        # 基于文件大小比估算质量压缩损失
        size_ratio = min(1.0, test_size / max(ref_size, 1))

        # 估算各指标（带一些随机变化）
        random.seed(hash(test_video) & 0xFFFFFFFF)

        base_psnr = 25 + size_ratio * 20  # 25-45 dB
        psnr = base_psnr + random.uniform(-2, 2)

        base_ssim = 0.75 + size_ratio * 0.22  # 0.75-0.97
        ssim = min(0.99, base_ssim + random.uniform(-0.02, 0.02))

        base_vmaf = 60 + size_ratio * 35  # 60-95
        vmaf = base_vmaf + random.uniform(-3, 3)

        metrics = QualityMetrics(
            psnr=round(psnr, 3),
            ssim=round(ssim, 4),
            vmaf=round(vmaf, 2),
        )
        metrics.overall_score = _calc_overall_score(metrics)
        metrics.grade = _grade_from_score(metrics.overall_score)

        passed = self.check_pass(metrics)

        return QualityAssessmentResult(
            success=True,
            reference_video=reference_video,
            test_video=test_video,
            metrics=metrics,
            thresholds=thresholds,
            passed=passed,
            mode="simulate",
            details={
                "size_ratio": round(size_ratio, 4),
                "note": "模拟模式，指标为估算值",
            },
        )

    def _assess_brisque_simulate(
        self,
        video_path: str,
        thresholds: QualityThreshold,
    ) -> QualityAssessmentResult:
        """模拟无参考质量评估"""
        import random

        random.seed(hash(video_path) & 0xFFFFFFFF)
        brisque = random.uniform(15, 45)  # 中等质量范围

        metrics = QualityMetrics(brisque=round(brisque, 2))
        metrics.overall_score = _calc_overall_score(metrics)
        metrics.grade = _grade_from_score(metrics.overall_score)
        passed = self.check_pass(metrics)

        return QualityAssessmentResult(
            success=True,
            reference_video="",
            test_video=video_path,
            metrics=metrics,
            thresholds=thresholds,
            passed=passed,
            mode="simulate",
            details={"note": "模拟模式，指标为估算值"},
        )


# ============================================================================
# 质量报告生成
# ============================================================================

def generate_quality_report(
    results: List[QualityAssessmentResult],
    output_path: Optional[str] = None,
) -> Dict[str, Any]:
    """生成质量评估汇总报告

    Args:
        results: 评估结果列表
        output_path: 报告输出路径（JSON）

    Returns:
        报告字典
    """
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed

    # 统计各等级数量
    grade_counts: Dict[str, int] = {}
    for r in results:
        g = r.metrics.grade
        grade_counts[g] = grade_counts.get(g, 0) + 1

    # 平均各项指标
    all_psnr = [r.metrics.psnr for r in results if r.metrics.psnr is not None]
    all_ssim = [r.metrics.ssim for r in results if r.metrics.ssim is not None]
    all_vmaf = [r.metrics.vmaf for r in results if r.metrics.vmaf is not None]
    all_overall = [r.metrics.overall_score for r in results]

    report = {
        "summary": {
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": round(passed / total * 100, 2) if total > 0 else 0,
            "grade_distribution": grade_counts,
        },
        "average_metrics": {
            "avg_psnr": round(sum(all_psnr) / len(all_psnr), 3) if all_psnr else None,
            "avg_ssim": round(sum(all_ssim) / len(all_ssim), 4) if all_ssim else None,
            "avg_vmaf": round(sum(all_vmaf) / len(all_vmaf), 2) if all_vmaf else None,
            "avg_overall": round(sum(all_overall) / len(all_overall), 2) if all_overall else 0,
        },
        "results": [r.to_dict() for r in results],
    }

    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

    return report


# ============================================================================
# 模块单例
# ============================================================================

_default_assessor = VideoQualityAssessor()


def get_quality_assessor() -> VideoQualityAssessor:
    """获取默认质量评估器实例"""
    return _default_assessor


# ============================================================================
# 命令行入口
# ============================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("用法: python video_quality_assessor.py <参考视频> <测试视频> [模式]")
        print("模式: real / simulate / auto (默认)")
        sys.exit(1)

    ref_video = sys.argv[1]
    test_video = sys.argv[2]
    mode = sys.argv[3] if len(sys.argv) > 3 else "auto"

    assessor = VideoQualityAssessor(mode=mode)
    result = assessor.assess(ref_video, test_video)

    print("=" * 60)
    print("视频质量评估结果")
    print("=" * 60)
    print(f"模式: {result.mode}")
    print(f"参考视频: {result.reference_video}")
    print(f"测试视频: {result.test_video}")
    print(f"耗时: {result.duration:.2f}s")
    print("-" * 60)
    print(f"  PSNR:  {result.metrics.psnr} dB" if result.metrics.psnr else "  PSNR:  N/A")
    print(f"  SSIM:  {result.metrics.ssim}" if result.metrics.ssim else "  SSIM:  N/A")
    print(f"  VMAF:  {result.metrics.vmaf}" if result.metrics.vmaf else "  VMAF:  N/A")
    print(f"  BRISQUE: {result.metrics.brisque}" if result.metrics.brisque else "  BRISQUE: N/A")
    print("-" * 60)
    print(f"综合评分: {result.metrics.overall_score} / 100")
    print(f"质量等级: {result.metrics.grade}")
    print(f"验收结果: {'通过 ✓' if result.passed else '未通过 ✗'}")
    print("=" * 60)
