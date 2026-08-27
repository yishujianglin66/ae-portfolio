"""
integrations/vmaf_quality_adapter.py - VMAF 视频质量评估适配器
=============================================================

将 Netflix VMAF (Video Multi-method Assessment Fusion) 感知质量评估
封装为管线 verify 阶段可调用的质量打分器。

功能:
- 全参考评估: 对比渲染输出与参考视频的感知质量 (VMAF/SSIM/PSNR)
- 无参考降级: 当无参考视频时，使用基础指标(分辨率/码率/帧率)估算
- 逐帧评分: 定位质量最差的片段
- 阈值判定: 自动判断是否达标

集成点: pipeline/unified_pipeline.py → _run_verify() 质量评分
约束: 离线可用、无需GPU、依赖FFmpeg内置libvmaf

用法:
    from integrations.vmaf_quality_adapter import VMAFAdapter
    adapter = VMAFAdapter()
    result = adapter.assess_quality("output.mp4", reference="ref.mp4")
    # result.vmaf_score → 0~100 的感知质量分
    # result.passed → 是否达标
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class QualityAssessment:
    """视频质量评估结果"""
    success: bool = False
    vmaf_score: float = 0.0          # 0~100, Netflix感知质量分
    ssim_score: float = 0.0          # 0~1, 结构相似度
    psnr_score: float = 0.0          # dB, 峰值信噪比
    passed: bool = False             # 是否达标
    threshold: float = 70.0          # 达标阈值
    method: str = ""                 # vmaf / ssim_only / basic_fallback
    worst_segment: Dict[str, float] = field(default_factory=dict)  # 最差片段
    frame_scores: List[float] = field(default_factory=list)        # 逐帧分数(采样)
    error: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class VMAFAdapter:
    """VMAF 视频质量评估适配器
    
    优先使用 FFmpeg 内置 libvmaf；若不可用则降级为 SSIM/PSNR；
    最终降级为基础元数据检查。
    """

    def __init__(self, ffmpeg_bin: str = "", threshold: float = 70.0):
        self._ffmpeg = ffmpeg_bin or shutil.which("ffmpeg") or "ffmpeg"
        self._ffprobe = shutil.which("ffprobe") or "ffprobe"
        self._threshold = threshold
        self._has_vmaf: Optional[bool] = None

    @property
    def available(self) -> bool:
        """FFmpeg 是否可用"""
        return bool(shutil.which(self._ffmpeg) or os.path.isfile(self._ffmpeg))

    @property
    def has_vmaf_support(self) -> bool:
        """检测 FFmpeg 是否编译了 libvmaf"""
        if self._has_vmaf is None:
            try:
                proc = subprocess.run(
                    [self._ffmpeg, "-filters"],
                    capture_output=True, text=True, timeout=10
                )
                self._has_vmaf = "libvmaf" in proc.stdout
            except Exception:
                self._has_vmaf = False
        return self._has_vmaf

    def assess_quality(
        self,
        video_path: str,
        reference: str = "",
        threshold: float = 0.0,
        sample_interval: int = 10,
    ) -> QualityAssessment:
        """评估视频质量
        
        Args:
            video_path: 待评估视频(渲染输出)
            reference: 参考视频(可选，有则用VMAF/SSIM，无则降级)
            threshold: 达标阈值(0=使用默认值)
            sample_interval: 逐帧采样间隔(每N帧取1帧)
            
        Returns:
            QualityAssessment 评估结果
        """
        threshold = threshold or self._threshold
        video_path = str(Path(video_path).resolve())

        if not os.path.isfile(video_path):
            return QualityAssessment(error=f"File not found: {video_path}")

        # 有参考视频 → 全参考评估
        if reference and os.path.isfile(reference):
            if self.has_vmaf_support:
                result = self._assess_with_vmaf(video_path, reference, sample_interval)
            else:
                result = self._assess_with_ssim_psnr(video_path, reference)
        else:
            # 无参考 → 基础质量检查
            result = self._assess_basic(video_path)

        result.threshold = threshold
        result.passed = result.vmaf_score >= threshold if result.vmaf_score > 0 else result.ssim_score >= (threshold / 100.0)
        return result

    def quick_check(self, video_path: str) -> Dict[str, Any]:
        """快速质量检查(不计算VMAF，仅元数据)
        
        用于管线中间环节的轻量级验证。
        """
        info = self._probe_video(video_path)
        if not info:
            return {"valid": False, "error": "Cannot probe video"}

        issues = []
        width = info.get("width", 0)
        height = info.get("height", 0)
        fps = info.get("fps", 0)
        duration = info.get("duration", 0)
        bitrate = info.get("bitrate", 0)

        if width < 640 or height < 360:
            issues.append(f"Low resolution: {width}x{height}")
        if fps < 20:
            issues.append(f"Low framerate: {fps}fps")
        if duration < 1.0:
            issues.append(f"Too short: {duration:.1f}s")
        if bitrate < 500_000 and duration > 5:
            issues.append(f"Low bitrate: {bitrate//1000}kbps")

        file_size = os.path.getsize(video_path) if os.path.isfile(video_path) else 0
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "resolution": f"{width}x{height}",
            "fps": fps,
            "duration_sec": duration,
            "bitrate_kbps": bitrate // 1000,
            "file_size_mb": file_size / (1024 * 1024),
        }

    # ------------------------------------------------------------------
    #  内部方法
    # ------------------------------------------------------------------

    def _assess_with_vmaf(
        self, distorted: str, reference: str, sample_interval: int
    ) -> QualityAssessment:
        """使用 FFmpeg libvmaf 进行全参考评估"""
        try:
            with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
                log_path = tmp.name

            cmd = [
                self._ffmpeg, "-y",
                "-i", distorted,
                "-i", reference,
                "-lavfi",
                f"[0:v][1:v]libvmaf=log_path={log_path}:log_fmt=json"
                f":n_subsample={sample_interval}",
                "-f", "null", "-"
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if proc.returncode != 0:
                # libvmaf 失败，降级到 SSIM
                logger.debug(f"[VMAF] libvmaf failed, fallback to SSIM")
                return self._assess_with_ssim_psnr(distorted, reference)

            # 解析 VMAF JSON 日志
            if os.path.isfile(log_path):
                with open(log_path, "r", encoding="utf-8") as f:
                    vmaf_data = json.load(f)
                os.unlink(log_path)

                pooled = vmaf_data.get("pooled_metrics", {})
                vmaf_mean = pooled.get("vmaf", {}).get("mean", 0)
                
                # 提取逐帧分数
                frames = vmaf_data.get("frames", [])
                frame_scores = [
                    f.get("metrics", {}).get("vmaf", 0) for f in frames
                ]

                # 找最差片段
                worst = {}
                if frame_scores:
                    min_idx = frame_scores.index(min(frame_scores))
                    worst = {
                        "frame_index": min_idx,
                        "score": frame_scores[min_idx],
                        "timestamp_sec": min_idx * sample_interval / 30.0,
                    }

                return QualityAssessment(
                    success=True,
                    vmaf_score=vmaf_mean,
                    method="vmaf",
                    worst_segment=worst,
                    frame_scores=frame_scores[:100],  # 最多保留100帧
                    metadata={"n_frames": len(frames)},
                )
            else:
                return self._assess_with_ssim_psnr(distorted, reference)

        except subprocess.TimeoutExpired:
            return QualityAssessment(error="VMAF computation timeout (>300s)")
        except Exception as e:
            return self._assess_with_ssim_psnr(distorted, reference)

    def _assess_with_ssim_psnr(self, distorted: str, reference: str) -> QualityAssessment:
        """降级: 使用 SSIM + PSNR (不需要 libvmaf)"""
        try:
            # SSIM
            cmd_ssim = [
                self._ffmpeg, "-i", distorted, "-i", reference,
                "-lavfi", "[0:v][1:v]ssim=stats_file=-",
                "-f", "null", "-"
            ]
            proc_ssim = subprocess.run(cmd_ssim, capture_output=True, text=True, timeout=120)
            ssim_val = self._parse_ssim(proc_ssim.stderr)

            # PSNR
            cmd_psnr = [
                self._ffmpeg, "-i", distorted, "-i", reference,
                "-lavfi", "[0:v][1:v]psnr=stats_file=-",
                "-f", "null", "-"
            ]
            proc_psnr = subprocess.run(cmd_psnr, capture_output=True, text=True, timeout=120)
            psnr_val = self._parse_psnr(proc_psnr.stderr)

            # 将 SSIM 映射到 0~100 分 (近似 VMAF 量纲)
            vmaf_approx = max(0, min(100, ssim_val * 100)) if ssim_val > 0 else 0

            return QualityAssessment(
                success=True,
                vmaf_score=vmaf_approx,
                ssim_score=ssim_val,
                psnr_score=psnr_val,
                method="ssim_only",
            )
        except Exception as e:
            return QualityAssessment(error=f"SSIM/PSNR failed: {e}")

    def _assess_basic(self, video_path: str) -> QualityAssessment:
        """无参考降级: 基于元数据的基础质量估算"""
        info = self._probe_video(video_path)
        if not info:
            return QualityAssessment(error="Cannot probe video", method="basic_fallback")

        # 简单评分逻辑: 分辨率+码率+帧率 → 估算分数
        score = 50.0  # 基础分
        width, height = info.get("width", 0), info.get("height", 0)
        fps = info.get("fps", 0)
        bitrate = info.get("bitrate", 0)
        duration = info.get("duration", 0)

        # 分辨率加分
        if width >= 1920 and height >= 1080:
            score += 20
        elif width >= 1280 and height >= 720:
            score += 10

        # 帧率加分
        if fps >= 30:
            score += 10
        elif fps >= 24:
            score += 5

        # 码率加分 (对于1080p, 5Mbps以上算合格)
        expected_bitrate = width * height * fps * 0.1  # 粗略期望
        if bitrate > 0 and expected_bitrate > 0:
            ratio = bitrate / expected_bitrate
            if ratio >= 1.0:
                score += 20
            elif ratio >= 0.5:
                score += 10

        # 时长合理性
        if duration >= 5:
            score += 5

        # 文件大小检查 (>100KB 视为有实际内容)
        file_size = os.path.getsize(video_path)
        if file_size < 100 * 1024:
            score = max(score - 30, 0)

        return QualityAssessment(
            success=True,
            vmaf_score=min(score, 100),
            method="basic_fallback",
            metadata=info,
        )

    def _probe_video(self, video_path: str) -> Dict[str, Any]:
        """ffprobe 获取视频元数据"""
        try:
            cmd = [
                self._ffprobe, "-v", "quiet",
                "-print_format", "json",
                "-show_format", "-show_streams",
                video_path
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if proc.returncode != 0:
                return {}
            data = json.loads(proc.stdout)
            
            video_stream = next(
                (s for s in data.get("streams", []) if s.get("codec_type") == "video"),
                {}
            )
            fmt = data.get("format", {})

            # 解析帧率
            fps_str = video_stream.get("r_frame_rate", "0/1")
            try:
                num, den = fps_str.split("/")
                fps = float(num) / float(den) if float(den) != 0 else 0
            except (ValueError, ZeroDivisionError):
                fps = 0

            return {
                "width": int(video_stream.get("width", 0)),
                "height": int(video_stream.get("height", 0)),
                "fps": round(fps, 2),
                "duration": float(fmt.get("duration", 0)),
                "bitrate": int(fmt.get("bit_rate", 0)),
                "codec": video_stream.get("codec_name", ""),
                "file_size": int(fmt.get("size", 0)),
            }
        except Exception:
            return {}

    @staticmethod
    def _parse_ssim(stderr: str) -> float:
        """从 FFmpeg stderr 解析 SSIM 均值"""
        for line in stderr.split("\n"):
            if "All:" in line and "SSIM" in line.upper():
                try:
                    # 格式: [Parsed_ssim...] SSIM ... All:0.987654 (19.123456)
                    all_part = line.split("All:")[1].strip()
                    return float(all_part.split()[0])
                except (IndexError, ValueError):
                    pass
        return 0.0

    @staticmethod
    def _parse_psnr(stderr: str) -> float:
        """从 FFmpeg stderr 解析 PSNR 均值"""
        for line in stderr.split("\n"):
            if "average:" in line and "PSNR" in line.upper():
                try:
                    avg_part = line.split("average:")[1].strip()
                    return float(avg_part.split()[0])
                except (IndexError, ValueError):
                    pass
        return 0.0
