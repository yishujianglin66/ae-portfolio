"""
FFmpeg 编辑引擎 — 真实视频处理能力
===================================

提供滤镜链构建、转场效果、文字叠加、速度控制、画面适配等能力，
替代纯 concat 流拷贝，实现有实际编辑意义的视频渲染。

核心类:
- FFmpegFilterBuilder: 构建 FFmpeg 滤镜链
- FFmpegEditEngine: 执行真实视频编辑操作
- TransitionEngine: 转场效果引擎
- TextOverlayEngine: 文字叠加引擎

Author: AE-Knowledge-Vault Team
"""

import json
import logging
import os
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

from core.paths import ffmpeg_bin as _default_ffmpeg
from core.paths import ffprobe_bin as _default_ffprobe

# ============================================================
# 数据结构
# ============================================================

@dataclass
class ColorGradeParams:
    """调色参数"""
    brightness: float = 0.0       # -1.0 ~ 1.0
    contrast: float = 1.0         # 0.5 ~ 2.0
    saturation: float = 1.0       # 0.0 ~ 2.0
    gamma: float = 1.0            # 0.5 ~ 2.0
    temperature: float = 0.0      # -1.0(冷) ~ 1.0(暖)
    tint: float = 0.0             # -1.0(绿) ~ 1.0(紫)

@dataclass
class SharpenParams:
    """锐化参数"""
    amount: float = 1.0           # 0.0 ~ 3.0 (0=关闭)
    radius: float = 0.8           # 0.0 ~ 5.0
    threshold: float = 0.0        # 0.0 ~ 1.0

@dataclass
class BlurParams:
    """模糊参数"""
    radius_x: float = 2.0         # 水平模糊半径
    radius_y: float = 2.0         # 垂直模糊半径

@dataclass
class VignetteParams:
    """暗角参数"""
    angle: float = 3.0            # 暗角角度 (0~10)
    x0: float = 0.5               # 中心X
    y0: float = 0.5               # 中心Y

@dataclass
class SpeedParams:
    """速度控制"""
    video_factor: float = 1.0     # 视频速度倍率 (0.5=慢放, 2.0=快进)
    audio_factor: float = 1.0     # 音频速度倍率

@dataclass
class TextOverlayParams:
    """文字叠加参数"""
    text: str = ""
    fontfile: str = ""            # 字体文件路径
    fontsize: int = 48
    fontcolor: str = "white"
    x: str = "(w-text_w)/2"       # 位置表达式
    y: str = "h-th-40"
    borderw: int = 2
    bordercolor: str = "black"
    enable: str = ""              # 时间条件表达式

@dataclass
class TransitionParams:
    """转场参数"""
    type: str = "fade"            # fade/wipeleft/wiperight/dissolve/...
    duration: float = 0.5         # 转场时长(秒)
    offset: float = 0.0           # 转场起始偏移


# ============================================================
# FFmpeg 滤镜链构建器
# ============================================================

class FFmpegFilterBuilder:
    """
    FFmpeg 滤镜链构建器
    
    用法:
        fb = FFmpegFilterBuilder()
        fb.color_grade(ColorGradeParams(brightness=0.1, contrast=1.2))
        fb.sharpen(SharpenParams(amount=1.5))
        fb.vignette()
        filter_str = fb.build()
    """

    def __init__(self):
        self._filters: list[str] = []

    def color_grade(self, params: ColorGradeParams | None = None) -> 'FFmpegFilterBuilder':
        """添加调色滤镜"""
        p = params or ColorGradeParams()
        # eq: brightness, contrast, saturation, gamma
        b = p.brightness  # eq brightness: -1.0~1.0
        c = p.contrast    # eq contrast: 0.0~2.0 (1.0=normal)
        s = p.saturation  # eq saturation: 0.0~3.0 (1.0=normal)
        g = p.gamma       # eq gamma: -0.5~0.5 (0=normal) → 映射
        # FFmpeg eq: brightness(-1~1), contrast(0~2), saturation(0~3), gamma(0.1~10)
        gamma_mapped = max(0.1, min(10.0, p.gamma))
        eq_parts = [f"brightness={b:.3f}", f"contrast={c:.3f}",
                    f"saturation={s:.3f}", f"gamma={gamma_mapped:.3f}"]
        self._filters.append(f"eq={':'.join(eq_parts)}")
        # 色温/色调 → colorbalance
        if abs(p.temperature) > 0.01 or abs(p.tint) > 0.01:
            r = p.temperature * 0.3
            g_tint = -p.tint * 0.2
            b_tint = -p.temperature * 0.3
            cb = f"colorbalance=rs={r:.3f}:gs={g_tint:.3f}:bs={b_tint:.3f}"
            self._filters.append(cb)
        return self

    def sharpen(self, params: SharpenParams | None = None) -> 'FFmpegFilterBuilder':
        """添加锐化滤镜 (unsharp)"""
        p = params or SharpenParams()
        if p.amount <= 0.01:
            return self
        # unsharp=luma_msize_x:luma_y:luma_amount:chroma_msize_x:chroma_msize_y:chroma_amount
        # msize must be odd integer >= 3
        import math
        lx = ly = max(3, int(math.ceil(p.radius)) | 1)  # 确保奇数且>=3
        la = min(5.0, max(-2.0, p.amount))
        cx = cy = max(3, (lx - 2) | 1) if lx > 3 else 3
        ca = la * 0.3
        self._filters.append(f"unsharp={lx}:{ly}:{la:.2f}:{cx}:{cy}:{ca:.2f}")
        return self

    def blur(self, params: BlurParams | None = None) -> 'FFmpegFilterBuilder':
        """添加模糊滤镜"""
        p = params or BlurParams()
        self._filters.append(f"boxblur={p.radius_x:.1f}:{p.radius_y:.1f}")
        return self

    def vignette(self, params: VignetteParams | None = None) -> 'FFmpegFilterBuilder':
        """添加暗角效果

        FFmpeg vignette 的 x0/y0 是**像素坐标**(默认 w/2, h/2)，
        传 0.5 会被解释为 0.5 像素 → 暗角中心偏到左上角。
        因此把归一化值 (0~1) 转换为表达式 `w*<x0>`/`h*<y0>`。
        """
        p = params or VignetteParams()
        # 把归一化坐标 0~1 转为基于 w/h 的像素表达式
        self._filters.append(
            f"vignette=angle={p.angle:.3f}:x0=w*{p.x0:.3f}:y0=h*{p.y0:.3f}"
        )
        return self

    def speed(self, params: SpeedParams | None = None) -> 'FFmpegFilterBuilder':
        """添加速度控制"""
        p = params or SpeedParams()
        if abs(p.video_factor - 1.0) > 0.01:
            self._filters.append(f"setpts={1.0/p.video_factor:.4f}*PTS")
        return self

    def text_overlay(self, params: TextOverlayParams) -> 'FFmpegFilterBuilder':
        """添加文字叠加"""
        if not params.text:
            return self
        # 转义 filtergraph 特殊字符（反斜杠最先，按 ffmpeg 转义规则）
        escaped = (
            params.text
            .replace("\\", "\\\\")
            .replace("'", "'\\''")
            .replace(":", "\\:")
            .replace(",", "\\,")
            .replace(";", "\\;")
            .replace("=", "\\=")
            .replace("[", "\\[")
            .replace("]", "\\]")
        )
        parts = [f"text='{escaped}'"]
        if params.fontfile and os.path.isfile(params.fontfile):
            parts.append(f"fontfile='{params.fontfile}'")
        parts.append(f"fontsize={params.fontsize}")
        parts.append(f"fontcolor={params.fontcolor}")
        parts.append(f"x={params.x}")
        parts.append(f"y={params.y}")
        parts.append(f"borderw={params.borderw}")
        parts.append(f"bordercolor={params.bordercolor}")
        if params.enable:
            parts.append(f"enable='{params.enable}'")
        self._filters.append(f"drawtext={':'.join(parts)}")
        return self

    def scale(self, width: int, height: int, force: bool = False) -> 'FFmpegFilterBuilder':
        """添加缩放"""
        if force:
            self._filters.append(f"scale={width}:{height}")
        else:
            self._filters.append(f"scale='min({width},iw)':'min({height},ih)':force_original_aspect_ratio=decrease")
        return self

    def crop(self, w: int, h: int, x: int = 0, y: int = 0) -> 'FFmpegFilterBuilder':
        """添加裁切"""
        self._filters.append(f"crop={w}:{h}:{x}:{y}")
        return self

    def pad_to_aspect(self, target_w: int, target_h: int) -> 'FFmpegFilterBuilder':
        """添加黑边适配比例 (如竖屏9:16)"""
        self._filters.append(
            f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,"
            f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:black"
        )
        return self

    def fps(self, rate: int) -> 'FFmpegFilterBuilder':
        """设置帧率"""
        self._filters.append(f"fps={rate}")
        return self

    def fade_in(self, duration: float = 1.0) -> 'FFmpegFilterBuilder':
        """淡入"""
        self._filters.append(f"fade=t=in:st=0:d={duration:.2f}")
        return self

    def fade_out(self, duration: float = 1.0, total_duration: float = 10.0) -> 'FFmpegFilterBuilder':
        """淡出"""
        st = max(0, total_duration - duration)
        self._filters.append(f"fade=t=out:st={st:.2f}:d={duration:.2f}")
        return self

    def build(self) -> str:
        """构建完整滤镜链字符串"""
        return ",".join(self._filters)

    def build_audio(self) -> str:
        """构建音频滤镜链 (仅速度控制)"""
        audio_filters = []
        for f in self._filters:
            if f.startswith("setpts="):
                # 提取速度因子
                factor_str = f.split("=")[1].split("*")[0]
                try:
                    pts_factor = float(factor_str)
                    audio_speed = 1.0 / pts_factor
                    audio_filters.append(f"atempo={audio_speed:.4f}")
                except ValueError:
                    pass
        return ",".join(audio_filters) if audio_filters else ""

    def reset(self) -> 'FFmpegFilterBuilder':
        """重置滤镜链"""
        self._filters.clear()
        return self


# ============================================================
# 转场效果引擎
# ============================================================

class TransitionEngine:
    """
    FFmpeg xfade 转场引擎
    
    支持的转场类型:
    - fade: 淡入淡出
    - wipeleft/wiperight/wipeup/wipedown: 擦除
    - dissolve: 溶解
    - smoothleft/smoothright: 平滑
    - slideright/slideleft: 滑动
    - circlecrop: 圆形裁切
    - radial: 径向
    """

    TRANSITIONS = [
        "fade", "wipeleft", "wiperight", "wipeup", "wipedown",
        "dissolve", "smoothleft", "smoothright",
        "slideright", "slideleft", "circlecrop", "radial"
    ]

    @staticmethod
    def apply_transition(input_a: str, input_b: str, output: str,
                         transition: str = "fade", duration: float = 0.5,
                         offset: float | None = None,
                         ffmpeg_bin: str = "") -> bool:
        """
        在两个视频之间应用转场效果
        
        Args:
            input_a: 第一个输入文件
            input_b: 第二个输入文件
            output: 输出文件
            transition: 转场类型
            duration: 转场时长(秒)
            offset: 转场起始时间(默认=视频A时长-duration)
            ffmpeg_bin: FFmpeg路径
        """
        ff = ffmpeg_bin or _default_ffmpeg()
        fp = _default_ffprobe()

        if transition not in TransitionEngine.TRANSITIONS:
            transition = "fade"

        # 获取视频A时长
        dur_a = TransitionEngine._get_duration(input_a, fp)
        if dur_a <= 0:
            return False

        if offset is None:
            offset = max(0, dur_a - duration)

        cmd = [
            ff, "-y",
            "-i", input_a,
            "-i", input_b,
            "-filter_complex",
            f"[0:v][1:v]xfade=transition={transition}:duration={duration}:offset={offset},scale=1920:1080:flags=lanczos[v]",
            "-map", "[v]",
            "-c:v", "libx264", "-preset", "slow", "-crf", "18",
            "-b:v", "4M", "-maxrate", "8M", "-bufsize", "16M",
            "-pix_fmt", "yuv420p",
            output
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120)
            return result.returncode == 0 and os.path.isfile(output) and os.path.getsize(output) > 1000
        except Exception as e:
            logger.error(f"转场失败: {e}")
            return False

    @staticmethod
    def chain_transitions(inputs: list[str], output: str,
                          transitions: list[str], durations: list[float],
                          ffmpeg_bin: str = "") -> bool:
        """
        链式转场: 多个视频依次应用转场
        
        Args:
            inputs: 输入视频列表
            output: 最终输出
            transitions: 每对视频之间的转场类型
            durations: 每个转场的时长
        """
        if len(inputs) < 2:
            if inputs:
                import shutil
                shutil.copy2(inputs[0], output)
                return True
            return False

        ff = ffmpeg_bin or _default_ffmpeg()
        temp_dir = tempfile.mkdtemp(prefix="ffmpeg_xfade_")
        try:
            current = inputs[0]

            for i in range(1, len(inputs)):
                t = transitions[i-1] if i-1 < len(transitions) else "fade"
                d = durations[i-1] if i-1 < len(durations) else 0.5
                if i == len(inputs) - 1:
                    next_out = output
                else:
                    next_out = os.path.join(temp_dir, f"step_{i}.mp4")

                success = TransitionEngine.apply_transition(
                    current, inputs[i], next_out, t, d, ffmpeg_bin=ff
                )
                if not success:
                    # 降级: 直接拼接
                    logger.warning(f"转场 {i} 失败，降级为直接拼接")
                    TransitionEngine._simple_concat(current, inputs[i], next_out, ff)
                current = next_out

            return os.path.isfile(output) and os.path.getsize(output) > 1000
        finally:
            # 确保异常路径也清理临时目录，防止磁盘空间泄漏
            shutil.rmtree(temp_dir, ignore_errors=True)

    @staticmethod
    def _get_duration(filepath: str, ffprobe: str = "") -> float:
        fp = ffprobe or _default_ffprobe()
        try:
            cmd = [fp, "-v", "error", "-show_entries", "format=duration",
                   "-of", "default=noprint_wrappers=1:nokey=1", filepath]
            r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10)
            return float(r.stdout.strip())
        except Exception:
            return 0.0

    @staticmethod
    def _simple_concat(a: str, b: str, out: str, ff: str):
        """简单拼接降级"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(f"file '{a}'\nfile '{b}'\n")
            list_file = f.name
        try:
            cmd = [ff, "-y", "-f", "concat", "-safe", "0", "-i", list_file,
                   "-c", "copy", out]
            subprocess.run(cmd, capture_output=True, timeout=60)
        finally:
            os.unlink(list_file)


# ============================================================
# 文字叠加引擎
# ============================================================

class TextOverlayEngine:
    """文字/标题叠加"""

    @staticmethod
    def add_title(input_video: str, output: str, title: str,
                  subtitle: str = "", font_size: int = 64,
                  duration: float = 3.0, ffmpeg_bin: str = "") -> bool:
        """添加片头标题"""
        ff = ffmpeg_bin or _default_ffmpeg()
        fb = FFmpegFilterBuilder()

        # 主标题
        fb.text_overlay(TextOverlayParams(
            text=title, fontsize=font_size, fontcolor="white",
            x="(w-text_w)/2", y="(h-text_h)/2-30",
            borderw=3, bordercolor="black",
            enable=f"between(t,0,{duration:.1f})"
        ))
        # 副标题
        if subtitle:
            fb.text_overlay(TextOverlayParams(
                text=subtitle, fontsize=int(font_size * 0.5),
                fontcolor="0xCCCCCC",
                x="(w-text_w)/2", y="(h-text_h)/2+40",
                borderw=2, bordercolor="black",
                enable=f"between(t,0,{duration:.1f})"
            ))

        filter_str = fb.build()
        # 追加 scale 到 1080p (lanczos 高质量缩放), 保证输出 >= 1920x1080
        _scale = "scale=1920:1080:flags=lanczos"
        filter_str = f"{filter_str},{_scale}" if filter_str else _scale
        cmd = [
            ff, "-y", "-i", input_video,
            "-vf", filter_str,
            "-c:v", "libx264", "-preset", "slow", "-crf", "18",
            "-b:v", "4M", "-maxrate", "8M", "-bufsize", "16M",
            "-pix_fmt", "yuv420p",
            "-c:a", "copy", output
        ]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120)
            return r.returncode == 0 and os.path.isfile(output) and os.path.getsize(output) > 1000
        except Exception as e:
            logger.error(f"文字叠加失败: {e}")
            return False


# ============================================================
# FFmpeg 编辑引擎 (主入口)
# ============================================================

class FFmpegEditEngine:
    """
    FFmpeg 编辑引擎 — 真实视频处理主入口
    
    能力:
    - 调色 (color grading)
    - 锐化 (sharpening)
    - 模糊 (blur)
    - 暗角 (vignette)
    - 转场 (transitions)
    - 文字叠加 (text overlay)
    - 速度控制 (speed)
    - 画面适配 (aspect ratio)
    - 滤镜链组合 (filter chain)
    """

    def __init__(self, ffmpeg_bin: str = ""):
        self.ffmpeg_bin = ffmpeg_bin or _default_ffmpeg()
        self.ffprobe_bin = _default_ffprobe()

    def apply_filters(self, input_video: str, output: str,
                      filter_builder: FFmpegFilterBuilder,
                      total_duration: float | None = None) -> bool:
        """
        应用滤镜链到视频
        
        Args:
            input_video: 输入视频
            output: 输出视频
            filter_builder: 已配置好的滤镜构建器
            total_duration: 总时长(秒) — 用于显式截断输出, 防止流映射异常导致时长漂移
        """
        vf = filter_builder.build()
        if not vf:
            # 无滤镜，直接复制
            import shutil
            shutil.copy2(input_video, output)
            return True

        af = filter_builder.build_audio()
        # 标准命令格式: -y -hide_banner -i input -vf "..." -t <dur> -c:v libx264 -preset slow -crf 18 -b:v 4M -maxrate 8M -bufsize 16M -pix_fmt yuv420p -c:a aac -b:a 128k output
        # 高质量编码: CRF 18 (视觉无损) + preset slow (质量优先) + 码率上限约束 + scale 到 1080p
        _scale = "scale=1920:1080:flags=lanczos"
        vf = f"{vf},{_scale}" if vf else _scale
        cmd: list[str] = [self.ffmpeg_bin, "-y", "-hide_banner", "-i", input_video, "-vf", vf]
        # 时长处理: 显式 -t 防止滤镜(setpts/trim 等)改变时长后输出漂移
        if total_duration and total_duration > 0:
            cmd.extend(["-t", f"{float(total_duration):.3f}"])
        if af:
            cmd.extend(["-af", af])
        cmd.extend([
            "-map", "0:v:0",   # 显式选第一个视频流
            "-c:v", "libx264", "-preset", "slow", "-crf", "18",
            "-b:v", "4M", "-maxrate", "8M", "-bufsize", "16M",
            "-pix_fmt", "yuv420p",  # 兼容性
        ])
        # 音频: 若源有音频则转 aac, 否则 an
        has_audio = self._has_audio_stream(input_video)
        if has_audio:
            cmd.extend(["-map", "0:a:0?", "-c:a", "aac", "-b:a", "128k"])
        else:
            cmd.append("-an")
        cmd.append(output)

        try:
            r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=300)
            if r.returncode == 0 and os.path.isfile(output) and os.path.getsize(output) > 1000:
                return True
            # 失败: 记录完整 stderr 用于定位根因
            logger.error(
                f"滤镜应用失败 returncode={r.returncode}\n"
                f"CMD: {' '.join(cmd)}\n"
                f"STDERR: {r.stderr[-2000:] if r.stderr else '(empty)'}"
            )
            return False
        except Exception as e:
            logger.error(f"滤镜应用异常: {e}\nCMD: {' '.join(cmd)}")
            return False

    def _has_audio_stream(self, filepath: str) -> bool:
        """探测视频是否含音频流"""
        try:
            cmd = [self.ffprobe_bin, "-v", "error", "-select_streams", "a",
                   "-show_entries", "stream=codec_type", "-of", "csv=p=0", filepath]
            r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10)
            return "audio" in (r.stdout or "")
        except Exception:
            return True  # 默认按有音频处理, 让 FFmpeg 自己处理

    def process_clip(self, input_video: str, output: str,
                     color: ColorGradeParams | None = None,
                     sharpen: SharpenParams | None = None,
                     vignette: VignetteParams | None = None,
                     speed: SpeedParams | None = None,
                     text: TextOverlayParams | None = None,
                     target_aspect: tuple[int, int] | None = None,
                     fade_in: float = 0.0,
                     fade_out: float = 0.0) -> bool:
        """
        一站式处理单个片段 — 组合多种效果
        
        Args:
            input_video: 输入视频
            output: 输出视频
            color: 调色参数
            sharpen: 锐化参数
            vignette: 暗角参数
            speed: 速度参数
            text: 文字叠加参数
            target_aspect: 目标比例 (w,h) 如 (1080,1920) 竖屏
            fade_in: 淡入时长
            fade_out: 淡出时长
        """
        fb = FFmpegFilterBuilder()

        # 获取时长(用于fade_out)
        total_dur = self._get_duration(input_video)
        if speed and abs(speed.video_factor - 1.0) > 0.01:
            total_dur /= speed.video_factor

        # 按顺序添加滤镜
        if color:
            fb.color_grade(color)
        if sharpen and sharpen.amount > 0.01:
            fb.sharpen(sharpen)
        if vignette:
            fb.vignette(vignette)
        if speed and abs(speed.video_factor - 1.0) > 0.01:
            fb.speed(speed)
        if text:
            fb.text_overlay(text)
        if target_aspect:
            fb.pad_to_aspect(target_aspect[0], target_aspect[1])
        if fade_in > 0:
            fb.fade_in(fade_in)
        if fade_out > 0:
            fb.fade_out(fade_out, total_dur)

        return self.apply_filters(input_video, output, fb, total_dur)

    def concat_with_transitions(self, clips: list[str], output: str,
                                transitions: list[str] | None = None,
                                durations: list[float] | None = None) -> bool:
        """带转场的多片段拼接"""
        if not clips:
            return False
        if len(clips) == 1:
            import shutil
            shutil.copy2(clips[0], output)
            return True

        n = len(clips) - 1
        if not transitions:
            transitions = ["fade"] * n
        if not durations:
            durations = [0.5] * n

        return TransitionEngine.chain_transitions(
            clips, output, transitions, durations, self.ffmpeg_bin
        )

    def enhance_quality(self, input_video: str, output: str) -> bool:
        """
        自动画质增强 — 用于 FeedbackLoop 建议"画质偏低"时自动应用
        
        策略: 适度锐化 + 对比度提升 + 饱和度微调
        """
        fb = FFmpegFilterBuilder()
        fb.sharpen(SharpenParams(amount=1.2, radius=0.8))
        fb.color_grade(ColorGradeParams(contrast=1.1, saturation=1.1, gamma=1.05))
        return self.apply_filters(input_video, output, fb)

    def color_correct(self, input_video: str, output: str,
                      target_brightness: float = 0.0,
                      target_contrast: float = 1.0) -> bool:
        """
        自动色彩校正 — 用于 FeedbackLoop 建议"色彩不一致"时自动应用
        """
        fb = FFmpegFilterBuilder()
        fb.color_grade(ColorGradeParams(
            brightness=target_brightness,
            contrast=target_contrast,
            saturation=1.05
        ))
        return self.apply_filters(input_video, output, fb)

    def _get_duration(self, filepath: str) -> float:
        try:
            cmd = [self.ffprobe_bin, "-v", "error",
                   "-show_entries", "format=duration",
                   "-of", "default=noprint_wrappers=1:nokey=1", filepath]
            r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10)
            return float(r.stdout.strip())
        except Exception:
            return 10.0  # 默认10秒

    def get_video_info(self, filepath: str) -> dict:
        """获取视频信息"""
        fp = self.ffprobe_bin
        info = {"file": filepath, "exists": os.path.isfile(filepath)}
        if not info["exists"]:
            return info
        try:
            cmd = [fp, "-v", "error", "-select_streams", "v:0",
                   "-show_entries", "stream=width,height,codec_name,r_frame_rate,duration",
                   "-show_entries", "format=duration,size,bit_rate",
                   "-of", "json", filepath]
            r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10)
            data = json.loads(r.stdout)
            if data.get("streams"):
                info.update(data["streams"][0])
            if data.get("format"):
                info["file_size"] = data["format"].get("size")
                info["file_duration"] = data["format"].get("duration")
        except Exception:
            pass
        return info


# ============================================================
# 便捷函数
# ============================================================

def quick_enhance(input_video: str, output: str, ffmpeg_bin: str = "") -> bool:
    """快速画质增强"""
    engine = FFmpegEditEngine(ffmpeg_bin)
    return engine.enhance_quality(input_video, output)

def quick_color(input_video: str, output: str,
                brightness: float = 0.0, contrast: float = 1.0,
                saturation: float = 1.0, ffmpeg_bin: str = "") -> bool:
    """快速调色"""
    engine = FFmpegEditEngine(ffmpeg_bin)
    return engine.color_correct(input_video, output, brightness, contrast)

def quick_transition(clip_a: str, clip_b: str, output: str,
                     transition: str = "fade", duration: float = 0.5,
                     ffmpeg_bin: str = "") -> bool:
    """快速转场"""
    return TransitionEngine.apply_transition(
        clip_a, clip_b, output, transition, duration, ffmpeg_bin
    )
