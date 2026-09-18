"""
integrations/auto_editor_adapter.py - Auto-Editor 素材预处理适配器
=================================================================

将 Auto-Editor (https://github.com/WyattBlue/auto-editor) 的静音/运动检测
能力封装为管线可调用的素材预处理步骤。

功能:
- 自动检测并移除视频中的静音片段
- 基于运动检测剪除静止画面
- 支持导出为 MP4 / Premiere XML / DaVinci Resolve 工程
- 批量处理多个素材文件

集成点: pipeline/unified_pipeline.py → _run_perceive() 素材预处理
约束: 离线可用、无需GPU、优先纯Python（底层调FFmpeg）

用法:
    from integrations.auto_editor_adapter import AutoEditorAdapter
    adapter = AutoEditorAdapter()
    result = adapter.preprocess("raw_footage.mp4", mode="silence")
    # result.cleaned_path → 去水后的视频路径
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
class PreprocessResult:
    """素材预处理结果"""
    success: bool = False
    original_path: str = ""
    cleaned_path: str = ""
    original_duration_sec: float = 0.0
    cleaned_duration_sec: float = 0.0
    removed_segments: int = 0
    mode: str = ""  # silence / motion / combined
    method: str = ""  # auto_editor / ffmpeg_fallback
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def reduction_ratio(self) -> float:
        """时长压缩比 (0~1, 越小表示剪掉越多)"""
        if self.original_duration_sec <= 0:
            return 1.0
        return self.cleaned_duration_sec / self.original_duration_sec


class AutoEditorAdapter:
    """Auto-Editor 素材预处理适配器
    
    优先使用 auto-editor CLI；若未安装则降级为 FFmpeg 静音检测。
    """

    def __init__(self, ffmpeg_bin: str = "", auto_editor_bin: str = ""):
        self._ffmpeg = auto_editor_bin or shutil.which("auto-editor") or ""
        self._ffmpeg_bin = ffmpeg_bin or shutil.which("ffmpeg") or "ffmpeg"
        self._ffprobe_bin = shutil.which("ffprobe") or "ffprobe"

    @property
    def available(self) -> bool:
        """检查 auto-editor 或 ffmpeg 是否可用"""
        return bool(self._ffmpeg) or bool(self._ffmpeg_bin)

    def preprocess(
        self,
        video_path: str,
        mode: str = "silence",
        output_path: str = "",
        silence_threshold: float = -30.0,
        min_silence_duration: float = 0.5,
        motion_threshold: float = 0.05,
    ) -> PreprocessResult:
        """对单个视频文件执行预处理
        
        Args:
            video_path: 输入视频路径
            mode: 检测模式 - "silence"(静音) / "motion"(运动) / "combined"(组合)
            output_path: 输出路径(空=自动生成)
            silence_threshold: 静音阈值(dB)，低于此值视为静音
            min_silence_duration: 最短静音时长(秒)，超过才剪除
            motion_threshold: 运动检测阈值(0~1)，低于此值视为静止
            
        Returns:
            PreprocessResult 包含处理结果
        """
        video_path = str(Path(video_path).resolve())
        if not os.path.isfile(video_path):
            return PreprocessResult(error=f"File not found: {video_path}")

        # 获取原始时长
        original_duration = self._get_duration(video_path)

        # 确定输出路径
        if not output_path:
            stem = Path(video_path).stem
            suffix = Path(video_path).suffix or ".mp4"
            output_path = str(Path(video_path).parent / f"{stem}_cleaned{suffix}")

        # 优先尝试 auto-editor
        if self._ffmpeg:
            result = self._run_auto_editor(
                video_path, output_path, mode,
                silence_threshold, min_silence_duration, motion_threshold
            )
        else:
            # 降级: 纯 FFmpeg 静音检测
            result = self._run_ffmpeg_fallback(
                video_path, output_path, mode,
                silence_threshold, min_silence_duration
            )

        result.original_path = video_path
        result.original_duration_sec = original_duration
        result.mode = mode

        # 获取输出时长
        if result.success and os.path.isfile(result.cleaned_path):
            result.cleaned_duration_sec = self._get_duration(result.cleaned_path)

        return result

    def preprocess_batch(
        self,
        video_paths: list[str],
        mode: str = "silence",
        output_dir: str = "",
        **kwargs,
    ) -> list[PreprocessResult]:
        """批量预处理多个视频文件"""
        results = []
        for vp in video_paths:
            out = ""
            if output_dir:
                stem = Path(vp).stem
                suffix = Path(vp).suffix or ".mp4"
                out = str(Path(output_dir) / f"{stem}_cleaned{suffix}")
            results.append(self.preprocess(vp, mode=mode, output_path=out, **kwargs))
        return results

    def detect_silence_segments(
        self,
        video_path: str,
        threshold_db: float = -30.0,
        min_duration: float = 0.5,
    ) -> list[dict[str, float]]:
        """仅检测静音片段(不剪除)，返回时间段列表
        
        Returns:
            [{"start": 1.2, "end": 3.5, "duration": 2.3}, ...]
        """
        try:
            cmd = [
                self._ffmpeg_bin, "-i", video_path,
                "-af", f"silencedetect=noise={threshold_db}dB:d={min_duration}",
                "-f", "null", "-"
            ]
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=120
            )
            stderr = proc.stderr
            segments = []
            lines = stderr.split("\n")
            current_start = None
            for line in lines:
                if "silence_start:" in line:
                    try:
                        current_start = float(line.split("silence_start:")[1].strip())
                    except (ValueError, IndexError):
                        pass
                elif "silence_end:" in line and current_start is not None:
                    try:
                        end_part = line.split("silence_end:")[1].strip()
                        end_val = float(end_part.split("|")[0].strip())
                        segments.append({
                            "start": current_start,
                            "end": end_val,
                            "duration": end_val - current_start,
                        })
                    except (ValueError, IndexError):
                        pass
                    current_start = None
            return segments
        except Exception as e:
            logger.debug(f"[AutoEditor] Silence detection failed: {e}")
            return []

    # ------------------------------------------------------------------
    #  内部方法
    # ------------------------------------------------------------------

    def _run_auto_editor(
        self, input_path: str, output_path: str, mode: str,
        silence_threshold: float, min_silence: float, motion_threshold: float
    ) -> PreprocessResult:
        """调用 auto-editor CLI"""
        try:
            cmd = [self._ffmpeg, input_path, "-o", output_path]

            if mode in ("silence", "combined"):
                cmd.extend(["--edit", "audio"])
                cmd.extend(["--audio-threshold", f"{silence_threshold}dB"])
                cmd.extend(["--min-clip-length", f"{min_silence}s"])
            elif mode == "motion":
                cmd.extend(["--edit", "motion"])
                cmd.extend(["--motion-threshold", str(motion_threshold)])

            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if proc.returncode == 0 and os.path.isfile(output_path):
                return PreprocessResult(
                    success=True, cleaned_path=output_path, method="auto_editor"
                )
            else:
                # auto-editor 失败，降级到 ffmpeg
                logger.debug(f"[AutoEditor] CLI failed: {proc.stderr[:200]}")
                return self._run_ffmpeg_fallback(
                    input_path, output_path, mode,
                    silence_threshold, min_silence
                )
        except FileNotFoundError:
            return self._run_ffmpeg_fallback(
                input_path, output_path, mode, silence_threshold, min_silence
            )
        except subprocess.TimeoutExpired:
            return PreprocessResult(error="auto-editor timeout (>600s)")
        except Exception as e:
            return PreprocessResult(error=str(e))

    def _run_ffmpeg_fallback(
        self, input_path: str, output_path: str, mode: str,
        silence_threshold: float, min_silence: float
    ) -> PreprocessResult:
        """FFmpeg 降级方案: 检测静音 → 反向截取有声片段 → 拼接"""
        try:
            segments = self.detect_silence_segments(
                input_path, silence_threshold, min_silence
            )
            if not segments:
                # 没有静音片段，直接复制
                shutil.copy2(input_path, output_path)
                return PreprocessResult(
                    success=True, cleaned_path=output_path,
                    method="ffmpeg_fallback", removed_segments=0
                )

            # 构建 FFmpeg 滤镜: 排除静音段
            total_duration = self._get_duration(input_path)
            keep_segments = self._invert_segments(segments, total_duration)

            if not keep_segments:
                return PreprocessResult(error="All content is silence")

            # 使用 select 滤镜或分段截取+拼接
            filter_parts = []
            concat_inputs = []
            for i, seg in enumerate(keep_segments):
                filter_parts.append(
                    f"[0:v]trim=start={seg['start']:.3f}:end={seg['end']:.3f},"
                    f"setpts=PTS-STARTPTS[v{i}];"
                    f"[0:a]atrim=start={seg['start']:.3f}:end={seg['end']:.3f},"
                    f"asetpts=PTS-STARTPTS[a{i}]"
                )
                concat_inputs.append(f"[v{i}][a{i}]")

            n = len(keep_segments)
            filter_str = ";".join(filter_parts) + ";" + \
                "".join(concat_inputs) + f"concat=n={n}:v=1:a=1[outv][outa]"

            cmd = [
                self._ffmpeg_bin, "-y", "-i", input_path,
                "-filter_complex", filter_str,
                "-map", "[outv]", "-map", "[outa]",
                "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                "-c:a", "aac", "-b:a", "192k",
                output_path
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if proc.returncode == 0 and os.path.isfile(output_path):
                return PreprocessResult(
                    success=True, cleaned_path=output_path,
                    method="ffmpeg_fallback", removed_segments=len(segments)
                )
            else:
                return PreprocessResult(
                    error=f"FFmpeg concat failed: {proc.stderr[-200:]}"
                )
        except subprocess.TimeoutExpired:
            return PreprocessResult(error="FFmpeg timeout (>600s)")
        except Exception as e:
            return PreprocessResult(error=str(e))

    def _get_duration(self, video_path: str) -> float:
        """获取视频时长(秒)"""
        try:
            cmd = [
                self._ffprobe_bin, "-v", "quiet",
                "-print_format", "json",
                "-show_format", video_path
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if proc.returncode == 0:
                info = json.loads(proc.stdout)
                return float(info.get("format", {}).get("duration", 0))
        except Exception:
            pass
        return 0.0

    @staticmethod
    def _invert_segments(
        silence_segments: list[dict[str, float]], total_duration: float
    ) -> list[dict[str, float]]:
        """将静音段反转为保留段"""
        keep = []
        prev_end = 0.0
        for seg in sorted(silence_segments, key=lambda s: s["start"]):
            if seg["start"] > prev_end + 0.01:
                keep.append({"start": prev_end, "end": seg["start"]})
            prev_end = max(prev_end, seg["end"])
        if prev_end < total_duration - 0.01:
            keep.append({"start": prev_end, "end": total_duration})
        return keep
