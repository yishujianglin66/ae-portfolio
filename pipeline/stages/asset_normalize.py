"""
pipeline/stages/asset_normalize.py — S1 素材规范化阶段
======================================================

将用户提供的任意格式视频/音频统一规范化为旗舰管线标准格式：
- 视频：1920×1080 H.264 High Profile, yuv420p, 24fps
- 音频：WAV PCM 16-bit 48kHz 立体声

设计原则：
- 零 fallback：ffprobe/ffmpeg 不可用时直接 fail，不降级
- 幂等：已合规的素材不重复转码（通过 ffprobe 检测）
- MD5 校验：所有产物落盘后计算 MD5 写入 md5sums.txt

集成方式::

    from pipeline.stages.asset_normalize import AssetNormalizeStage

    stage = AssetNormalizeStage(ffmpeg_path="C:/ffmpeg/bin/ffmpeg.exe")
    result = stage.run(
        source_videos=["clip1.mp4", "clip2.mov", "clip3.avi"],
        source_audio="bgm.mp3",
        output_dir=Path("output/flagship_001/S1_assets"),
    )
"""
from __future__ import annotations

import hashlib
import json
import logging
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 目标规格
TARGET_WIDTH = 1920
TARGET_HEIGHT = 1080
TARGET_FPS = 24
TARGET_VCODEC = "h264"
TARGET_PIX_FMT = "yuv420p"
TARGET_ACODEC = "pcm_s16le"
TARGET_SAMPLE_RATE = 48000
TARGET_CHANNELS = 2


@dataclass
class NormalizeResult:
    """规范化结果"""
    success: bool
    output_videos: List[str] = field(default_factory=list)
    output_audio: Optional[str] = None
    md5sums_path: Optional[str] = None
    errors: List[str] = field(default_factory=list)
    elapsed_s: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class AssetNormalizeStage:
    """S1 素材规范化阶段

    将 3 条视频 + 1 条音频规范化为统一格式。
    """

    def __init__(
        self,
        ffmpeg_path: str | Path = "C:/ffmpeg/bin/ffmpeg.exe",
        ffprobe_path: str | Path = "C:/ffmpeg/bin/ffprobe.exe",
    ):
        self.ffmpeg_path = Path(ffmpeg_path)
        self.ffprobe_path = Path(ffprobe_path)

        # 零 fallback：启动时验证工具存在
        if not self.ffmpeg_path.exists():
            raise FileNotFoundError(
                f"FFmpeg 不存在: {self.ffmpeg_path}（S1 禁止 fallback）"
            )
        if not self.ffprobe_path.exists():
            raise FileNotFoundError(
                f"FFprobe 不存在: {self.ffprobe_path}（S1 禁止 fallback）"
            )

    def run(
        self,
        source_videos: List[str | Path],
        source_audio: str | Path,
        output_dir: str | Path,
    ) -> NormalizeResult:
        """执行素材规范化。

        Args:
            source_videos: 3 条源视频路径
            source_audio: 1 条源音频路径
            output_dir: 输出目录

        Returns:
            NormalizeResult
        """
        start = time.time()
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        errors: List[str] = []
        output_videos: List[str] = []
        output_audio: Optional[str] = None

        # 验证输入数量
        if len(source_videos) != 3:
            return NormalizeResult(
                success=False,
                errors=[f"需要恰好 3 条视频，实际 {len(source_videos)} 条"],
                elapsed_s=time.time() - start,
            )

        # 规范化视频
        for i, src in enumerate(source_videos, 1):
            src = Path(src)
            if not src.exists():
                errors.append(f"视频不存在: {src}")
                continue

            out_path = output_dir / f"clip{i}.mp4"
            try:
                self._normalize_video(src, out_path)
                output_videos.append(str(out_path))
            except Exception as e:
                errors.append(f"视频 {i} 规范化失败: {e}")

        # 规范化音频
        src_audio = Path(source_audio)
        if not src_audio.exists():
            errors.append(f"音频不存在: {src_audio}")
        else:
            out_audio = output_dir / "bgm.wav"
            try:
                self._normalize_audio(src_audio, out_audio)
                output_audio = str(out_audio)
            except Exception as e:
                errors.append(f"音频规范化失败: {e}")

        # 生成 MD5 校验
        md5sums_path = output_dir / "md5sums.txt"
        self._write_md5sums(output_dir, md5sums_path)

        elapsed = time.time() - start
        success = len(errors) == 0 and len(output_videos) == 3 and output_audio is not None

        result = NormalizeResult(
            success=success,
            output_videos=output_videos,
            output_audio=output_audio,
            md5sums_path=str(md5sums_path),
            errors=errors,
            elapsed_s=elapsed,
            metadata={
                "target_spec": f"{TARGET_WIDTH}x{TARGET_HEIGHT} {TARGET_VCODEC} {TARGET_FPS}fps",
                "audio_spec": f"{TARGET_ACODEC} {TARGET_SAMPLE_RATE}Hz {TARGET_CHANNELS}ch",
            },
        )

        level = logging.INFO if success else logging.ERROR
        logger.log(
            level,
            f"[S1] 素材规范化{'成功' if success else '失败'}: "
            f"{len(output_videos)}/3 视频, 音频={'OK' if output_audio else 'FAIL'}, "
            f"耗时 {elapsed:.1f}s"
        )
        return result

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _probe_video(self, path: Path) -> Dict[str, Any]:
        """用 ffprobe 获取视频信息"""
        cmd = [
            str(self.ffprobe_path),
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(path),
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30, encoding="utf-8"
        )
        if result.returncode != 0:
            raise RuntimeError(f"ffprobe 失败: {result.stderr}")
        return json.loads(result.stdout)

    def _is_video_compliant(self, path: Path) -> bool:
        """检查视频是否已合规（避免重复转码）"""
        try:
            info = self._probe_video(path)
            for stream in info.get("streams", []):
                if stream.get("codec_type") == "video":
                    w = int(stream.get("width", 0))
                    h = int(stream.get("height", 0))
                    codec = stream.get("codec_name", "")
                    return (
                        w == TARGET_WIDTH
                        and h == TARGET_HEIGHT
                        and codec == TARGET_VCODEC
                    )
        except Exception:
            pass
        return False

    def _normalize_video(self, src: Path, dst: Path) -> None:
        """将视频规范化为 1920×1080 H.264 24fps"""
        # 幂等：已合规则跳过
        if dst.exists() and self._is_video_compliant(dst):
            logger.info(f"[S1] 已合规，跳过: {dst.name}")
            return

        cmd = [
            str(self.ffmpeg_path),
            "-y",
            "-i", str(src),
            "-vf", f"scale={TARGET_WIDTH}:{TARGET_HEIGHT}:force_original_aspect_ratio=decrease,"
                   f"pad={TARGET_WIDTH}:{TARGET_HEIGHT}:(ow-iw)/2:(oh-ih)/2:black",
            "-c:v", "libx264",
            "-profile:v", "high",
            "-pix_fmt", TARGET_PIX_FMT,
            "-r", str(TARGET_FPS),
            "-an",  # 视频轨不含音频（音频单独处理）
            "-movflags", "+faststart",
            str(dst),
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300, encoding="utf-8", errors="replace"
        )
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg 视频转码失败: {result.stderr[-500:]}")

        if not dst.exists() or dst.stat().st_size == 0:
            raise RuntimeError(f"输出文件无效: {dst}")

    def _normalize_audio(self, src: Path, dst: Path) -> None:
        """将音频规范化为 WAV PCM 16-bit 48kHz 立体声"""
        if dst.exists() and dst.stat().st_size > 0:
            logger.info(f"[S1] 音频已存在，跳过: {dst.name}")
            return

        cmd = [
            str(self.ffmpeg_path),
            "-y",
            "-i", str(src),
            "-acodec", TARGET_ACODEC,
            "-ar", str(TARGET_SAMPLE_RATE),
            "-ac", str(TARGET_CHANNELS),
            str(dst),
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120, encoding="utf-8", errors="replace"
        )
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg 音频转码失败: {result.stderr[-500:]}")

        if not dst.exists() or dst.stat().st_size == 0:
            raise RuntimeError(f"输出音频无效: {dst}")

    def _write_md5sums(self, directory: Path, output_path: Path) -> None:
        """为目录内所有媒体文件生成 MD5 校验"""
        lines = []
        for f in sorted(directory.iterdir()):
            if f.suffix.lower() in (".mp4", ".wav", ".mov", ".mp3"):
                md5 = hashlib.md5(f.read_bytes()).hexdigest()
                lines.append(f"{md5}  {f.name}")
        output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
