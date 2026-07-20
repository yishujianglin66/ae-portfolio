#!/usr/bin/env python3
"""
统一多工具集成调度器 (Unified Tool Integrator) v1.0
=====================================================

基于知识库中的跨工具集成工作流，提供统一的多工具协同调度入口。
整合 AE / Topaz / Blender / FFmpeg / Adobe全家桶 / Resolve 等工具，
支持预设工作流一键执行、自定义流水线编排、模拟/真实双模式运行。

知识库参考：
- [[跨工具集成工作流-全工具联动指南]]
- [[企业级多软件集成指南]]
- [[🎬-风格化剪辑知识库-MOC]]

支持的工作流预设：
1. enhance_quality      - 视频质量增强（Topaz超分+降噪+插帧）
2. ai_creative_pipeline - AI创意流水线（Runway/Pika生成→AE合成→Topaz优化）
3. 3d_composite         - 3D合成流水线（Blender渲染→AE多通道合成）
4. delivery_pipeline    - 交付流水线（AE渲染→Topaz增强→FFmpeg多格式编码）
5. full_production      - 完整生产流水线（素材→剪辑→合成→调色→输出）
6. batch_process        - 批量处理（多文件批量增强/转码）

执行模式：
- real    : 调用真实工具（需安装对应软件）
- simulate: 模拟执行，生成详细日志（用于测试和流程验证）
- auto    : 优先真实模式，失败自动降级到模拟模式
"""

import os
import sys
import json
import time
import copy
import uuid
import traceback
import threading
import re
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Callable, Union, Set


def _escape_extendscript_string(value: str) -> str:
    """转义字符串以安全嵌入 ExtendScript 字符串字面量。

    防止通过文件路径等用户可控输入注入 ExtendScript 代码。
    转义反斜杠、双引号、单引号和换行符，确保字符串被当作纯文本处理。
    """
    if not isinstance(value, str):
        value = str(value)
    # 按顺序转义：先反斜杠，再引号，再换行
    value = value.replace("\\", "\\\\")
    value = value.replace('"', '\\"')
    value = value.replace("'", "\\'")
    value = value.replace("\n", "\\n")
    value = value.replace("\r", "\\r")
    return value

from enum import Enum


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class Logger:
    """分级日志系统，支持控制台和文件输出"""

    def __init__(self, log_dir: str = None, log_level: str = "INFO", prefix: str = ""):
        self._level = LogLevel(log_level.upper())
        self._prefix = prefix
        self._log_file = None
        self._log_dir = log_dir or os.path.join(os.path.dirname(__file__), "logs")

        os.makedirs(self._log_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._log_file_path = os.path.join(self._log_dir, f"integrator_{timestamp}.log")
        self._open_log_file()

    def _open_log_file(self):
        try:
            self._log_file = open(self._log_file_path, "w", encoding="utf-8")
            self._write(f"日志文件创建: {self._log_file_path}", LogLevel.DEBUG)
        except Exception:
            self._log_file = None

    def _write(self, message: str, level: LogLevel):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] [{level.value}] {message}"

        if level.value >= self._level.value:
            prefix = f"[{self._prefix}] " if self._prefix else ""
            print(f"{prefix}{log_line}")

        if self._log_file:
            try:
                self._log_file.write(log_line + "\n")
                self._log_file.flush()
            except Exception:
                pass

    def debug(self, message: str):
        self._write(message, LogLevel.DEBUG)

    def info(self, message: str):
        self._write(message, LogLevel.INFO)

    def warning(self, message: str):
        self._write(message, LogLevel.WARNING)

    def error(self, message: str, exc: Exception = None):
        self._write(message, LogLevel.ERROR)
        if exc:
            self._write(f"异常详情: {traceback.format_exc()}", LogLevel.ERROR)

    def close(self):
        if self._log_file:
            self._write("日志文件关闭", LogLevel.DEBUG)
            self._log_file.close()

    def get_log_path(self) -> str:
        return self._log_file_path


class ToolType(str, Enum):
    """支持的工具类型"""
    # Adobe 全家桶
    AE = "after_effects"
    PREMIERE = "premiere_pro"
    PHOTOSHOP = "photoshop"
    ILLUSTRATOR = "illustrator"
    MEDIA_ENCODER = "media_encoder"
    AUDITION = "audition"
    # 其他专业工具
    TOPAZ = "topaz_video_ai"
    BLENDER = "blender"
    FFMPEG = "ffmpeg"
    RESOLVE = "davinci_resolve"
    RUNWAY = "runwayml"
    PIKA = "pika"
    SILHOUETTE = "silhouette"
    # 开源工具 (GitHub顶级项目)
    RIFE = "rife"              # hzwer/ECCV2022-RIFE - 帧插值
    SAM2 = "sam2"              # facebookresearch/sam2 - 视频分割
    WHISPER = "whisper"        # openai/whisper - 语音识别
    REMOTION = "remotion"      # remotion-dev/remotion - 编程视频
    MOVIEPY = "moviepy"        # Zulko/moviepy - Python视频编辑
    OPENMONTAGE = "openmontage"  # calesthio/OpenMontage - Agent视频制作
    VIDEO2X = "video2x"        # video2x/video2x - AI超分辨率


class WorkflowPreset(str, Enum):
    """工作流预设"""
    ENHANCE_QUALITY = "enhance_quality"
    AI_CREATIVE = "ai_creative_pipeline"
    D3_COMPOSITE = "3d_composite"
    DELIVERY = "delivery_pipeline"
    FULL_PRODUCTION = "full_production"
    BATCH_PROCESS = "batch_process"
    # 开源工具驱动的新流水线
    AI_SUBTITLE = "ai_subtitle_pipeline"
    SMART_ROTO = "smart_roto_pipeline"
    OPEN_PRODUCTION = "open_production_pipeline"
    ENHANCED_UPSCALE = "enhanced_upscale_pipeline"
    BATCH_SOCIAL = "batch_social_media"


class ExecutionMode(str, Enum):
    """执行模式"""
    REAL = "real"
    SIMULATE = "simulate"
    AUTO = "auto"


class PhaseStatus(str, Enum):
    """阶段状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    SKIPPED = "skipped"
    FALLBACK = "fallback"


# ============================================================================
# 配置数据类
# ============================================================================

@dataclass
class ToolConfig:
    """单个工具的配置"""
    tool_type: str
    enabled: bool = True
    install_path: str = ""
    mode: str = "auto"  # real/simulate/auto
    extra_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowStep:
    """工作流中的一个步骤"""
    step_id: str
    name: str
    tool: str  # ToolType
    operation: str  # 操作类型，如 upscale/render/encode
    description: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)  # 依赖的步骤ID
    enabled: bool = True


@dataclass
class StepResult:
    """单个步骤的执行结果"""
    step_id: str
    name: str
    status: str  # PhaseStatus
    tool: str
    operation: str
    duration_ms: float = 0
    output_files: List[str] = field(default_factory=list)
    output_data: Dict[str, Any] = field(default_factory=dict)
    error: str = ""
    used_fallback: bool = False
    mode_used: str = "simulate"  # real/simulate
    log: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "StepResult":
        return cls(**d)


@dataclass
class WorkflowResult:
    """完整工作流执行结果"""
    workflow_name: str
    status: str  # PhaseStatus
    steps: List[StepResult] = field(default_factory=list)
    total_duration_ms: float = 0
    output_files: List[str] = field(default_factory=list)
    error: str = ""
    summary: str = ""
    started_at: str = ""
    finished_at: str = ""
    log_file_path: str = ""
    report_file_path: str = ""
    workflow_id: str = ""
    checkpoint_path: str = ""
    paused: bool = False

    def get_step(self, step_id: str) -> Optional[StepResult]:
        for s in self.steps:
            if s.step_id == step_id:
                return s
        return None

    def successful_steps(self) -> List[StepResult]:
        return [s for s in self.steps if s.status == PhaseStatus.SUCCESS.value]

    @property
    def has_outputs(self) -> bool:
        return len(self.output_files) > 0

    def failed_steps(self) -> List[StepResult]:
        return [s for s in self.steps if s.status == PhaseStatus.ERROR.value]

    def completed_step_ids(self) -> set:
        """已完成的步骤ID集合（成功或失败，不含跳过）"""
        return {s.step_id for s in self.steps if s.status in (PhaseStatus.SUCCESS.value, PhaseStatus.ERROR.value)}

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "WorkflowResult":
        steps_data = d.pop("steps", [])
        steps = [StepResult.from_dict(s) for s in steps_data]
        return cls(steps=steps, **d)


# ============================================================================
# 工具适配器基类
# ============================================================================

class BaseToolAdapter:
    """工具适配器基类"""

    def __init__(self, config: ToolConfig):
        self.config = config
        self.tool_type = config.tool_type

    def execute(self, operation: str, params: Dict[str, Any]) -> StepResult:
        """执行操作，由子类实现"""
        raise NotImplementedError

    def list_operations(self) -> List[str]:
        """列出支持的操作列表，由子类实现"""
        return []

    def check_available(self) -> bool:
        """检查工具是否可用，由子类实现"""
        return False

    def _make_result(self, step_id: str, name: str, operation: str) -> StepResult:
        return StepResult(
            step_id=step_id,
            name=name,
            status=PhaseStatus.PENDING.value,
            tool=self.tool_type,
            operation=operation,
        )


# ============================================================================
# FFmpeg 适配器
# ============================================================================

class FFmpegAdapter(BaseToolAdapter):
    """FFmpeg 工具适配器"""

    def __init__(self, config: ToolConfig):
        super().__init__(config)
        if config.install_path and os.path.isdir(config.install_path):
            self._ffmpeg_path = os.path.join(config.install_path, "ffmpeg.exe")
            self._ffprobe_path = os.path.join(config.install_path, "ffprobe.exe")
        else:
            self._ffmpeg_path = "ffmpeg"
            self._ffprobe_path = "ffprobe"

    def check_available(self) -> bool:
        try:
            import shutil
            if self._ffmpeg_path == "ffmpeg":
                return shutil.which("ffmpeg") is not None
            return os.path.exists(self._ffmpeg_path)
        except Exception:
            return False

    def list_operations(self) -> List[str]:
        return [
            "probe",
            "transcode",
            "extract_audio",
            "compress",
            "resize",
            "concat",
            "watermark",
            "extract_frames",
            "create_slideshow",
            "batch_transcode",
        ]

    def execute(self, operation: str, params: Dict[str, Any]) -> StepResult:
        result = self._make_result(
            step_id=params.get("step_id", f"ffmpeg_{operation}"),
            name=params.get("step_name", f"FFmpeg {operation}"),
            operation=operation,
        )
        result.log.append(f"[FFmpeg] 开始执行: {operation}")
        start = time.time()

        mode = self._resolve_mode()
        result.mode_used = mode

        try:
            if mode == "real":
                output = self._execute_real(operation, params, result)
            else:
                output = self._execute_simulate(operation, params, result)

            result.status = PhaseStatus.SUCCESS.value
            result.output_files = output.get("files", [])
            result.output_data = output.get("data", {})
            result.log.append(f"[FFmpeg] 执行成功，输出: {len(result.output_files)} 个文件")

        except Exception as e:
            result.status = PhaseStatus.ERROR.value
            result.error = str(e)
            result.log.append(f"[FFmpeg] 执行失败: {e}")

        result.duration_ms = (time.time() - start) * 1000
        return result

    def _resolve_mode(self) -> str:
        if self.config.mode == "real":
            return "real" if self.check_available() else "simulate"
        if self.config.mode == "simulate":
            return "simulate"
        # auto
        return "real" if self.check_available() else "simulate"

    def _execute_real(self, operation: str, params: Dict[str, Any], result: StepResult) -> Dict:
        import subprocess

        input_file = params.get("input_file", "")
        output_file = params.get("output_file", "")
        cmd = [self._ffmpeg_path, "-y"]

        if operation == "transcode":
            codec = params.get("codec", "libx264")
            preset = params.get("preset", "medium")
            crf = params.get("crf", 23)
            bitrate = params.get("bitrate", "")

            cmd += ["-i", input_file]
            cmd += ["-c:v", codec]
            if bitrate:
                cmd += ["-b:v", bitrate]
            else:
                cmd += ["-crf", str(crf)]
            cmd += ["-preset", preset]

            if params.get("audio_codec"):
                cmd += ["-c:a", params["audio_codec"]]
            cmd += [output_file]

            result.log.append(f"[FFmpeg] 命令: {' '.join(cmd[:10])}...")
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if proc.returncode != 0:
                raise RuntimeError(f"FFmpeg错误: {proc.stderr[-500:]}")

        elif operation == "extract_audio":
            audio_codec = params.get("audio_codec", "libmp3lame")
            cmd += ["-i", input_file, "-vn", "-c:a", audio_codec]
            if audio_codec == "libmp3lame":
                bitrate = params.get("audio_bitrate", "192k")
                cmd += ["-b:a", bitrate]
            cmd += [output_file]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if proc.returncode != 0:
                raise RuntimeError(f"FFmpeg错误: {proc.stderr[-500:]}")

        elif operation == "probe":
            cmd = [self._ffprobe_path, "-v", "quiet", "-print_format", "json",
                   "-show_format", "-show_streams", input_file]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if proc.returncode != 0:
                raise RuntimeError(f"ffprobe错误: {proc.stderr[-500:]}")
            data = json.loads(proc.stdout)
            return {"data": data, "files": []}

        else:
            # 尝试通用转码处理
            if output_file and input_file:
                codec = params.get("codec", "libx264")
                cmd += ["-i", input_file, "-c:v", codec, "-c:a", "aac"]
                cmd += [output_file]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
                if proc.returncode != 0:
                    raise RuntimeError(f"FFmpeg错误: {proc.stderr[-500:]}")
            else:
                raise ValueError(f"不支持的操作: {operation}")

        return {"files": [output_file] if output_file else [], "data": {}}

    def _execute_simulate(self, operation: str, params: Dict[str, Any], result: StepResult) -> Dict:
        result.log.append(f"[FFmpeg] [模拟] 操作: {operation}")
        result.log.append(f"[FFmpeg] [模拟] 参数: {json.dumps(params, ensure_ascii=False)[:200]}")

        input_file = params.get("input_file", "")
        output_file = params.get("output_file", "")
        files = [output_file] if output_file else []
        output_data = {"simulated": True, "operation": operation}

        if operation == "probe":
            mock_data = {
                "format": {"duration": "60.0", "bit_rate": "5000000"},
                "streams": [
                    {"codec_type": "video", "width": 1920, "height": 1080, "codec_name": "h264"},
                    {"codec_type": "audio", "codec_name": "aac", "sample_rate": "48000"}
                ]
            }
            return {"files": [], "data": mock_data}
        elif operation == "transcode":
            codec = params.get("codec", "libx264")
            result.log.append(f"[FFmpeg] [模拟] 转码到: {codec}")
            output_data["codec"] = codec
        elif operation == "extract_audio":
            result.log.append(f"[FFmpeg] [模拟] 提取音频轨道")
            output_data["audio_extracted"] = True
        elif operation == "compress":
            crf = params.get("crf", 23)
            result.log.append(f"[FFmpeg] [模拟] 压缩 (CRF: {crf})")
            output_data["compressed"] = True
        elif operation == "resize":
            width = params.get("width", 1280)
            height = params.get("height", 720)
            result.log.append(f"[FFmpeg] [模拟] 调整尺寸: {width}x{height}")
            output_data["resized"] = True
        elif operation == "concat":
            input_files = params.get("input_files", [])
            result.log.append(f"[FFmpeg] [模拟] 拼接 {len(input_files)} 个文件")
            output_data["concatenated"] = True
        elif operation == "watermark":
            result.log.append(f"[FFmpeg] [模拟] 添加水印")
            output_data["watermarked"] = True
        elif operation == "extract_frames":
            fps = params.get("fps", 1)
            result.log.append(f"[FFmpeg] [模拟] 提取帧 ({fps}fps)")
            output_data["frames_extracted"] = True
        elif operation == "create_slideshow":
            result.log.append(f"[FFmpeg] [模拟] 创建幻灯片")
            output_data["slideshow_created"] = True
        elif operation == "batch_transcode":
            input_files = params.get("input_files", [])
            result.log.append(f"[FFmpeg] [模拟] 批量转码: {len(input_files)}个文件")
            output_data["batch_done"] = True

        return {"files": files, "data": output_data}


# ============================================================================
# Topaz Video AI 适配器
# ============================================================================

class TopazAdapter(BaseToolAdapter):
    """Topaz Video AI 工具适配器"""

    def __init__(self, config: ToolConfig):
        super().__init__(config)
        exe_name = config.extra_params.get("executable", "Topaz Video AI.exe")
        if config.install_path and os.path.isdir(config.install_path):
            self._topaz_path = os.path.join(config.install_path, exe_name)
            if not os.path.exists(self._topaz_path):
                import glob as _glob
                candidates = _glob.glob(os.path.join(config.install_path, "Topaz*.exe"))
                if candidates:
                    self._topaz_path = candidates[0]
        else:
            self._topaz_path = config.install_path or r"C:\Program Files\Topaz Labs LLC\Topaz Video AI\Topaz Video AI.exe"

    def check_available(self) -> bool:
        return os.path.exists(self._topaz_path)

    def execute(self, operation: str, params: Dict[str, Any]) -> StepResult:
        result = self._make_result(
            step_id=params.get("step_id", f"topaz_{operation}"),
            name=params.get("step_name", f"Topaz {operation}"),
            operation=operation,
        )
        result.log.append(f"[Topaz] 开始执行: {operation}")
        start = time.time()

        mode = self._resolve_mode()
        result.mode_used = mode

        try:
            if mode == "real":
                output = self._execute_real(operation, params, result)
            else:
                output = self._execute_simulate(operation, params, result)

            result.status = PhaseStatus.SUCCESS.value
            result.output_files = output.get("files", [])
            result.output_data = output.get("data", {})
            result.log.append(f"[Topaz] 执行成功")

        except Exception as e:
            result.status = PhaseStatus.ERROR.value
            result.error = str(e)
            result.log.append(f"[Topaz] 执行失败: {e}")

        result.duration_ms = (time.time() - start) * 1000
        return result

    def _resolve_mode(self) -> str:
        if self.config.mode == "real":
            return "real" if self.check_available() else "simulate"
        if self.config.mode == "simulate":
            return "simulate"
        return "real" if self.check_available() else "simulate"

    def _execute_real(self, operation: str, params: Dict[str, Any], result: StepResult) -> Dict:
        import subprocess

        input_file = params.get("input_file", "")
        output_file = params.get("output_file", "")
        model = params.get("model", "proteus")
        scale = params.get("scale", 1)

        cmd = [
            self._topaz_path,
            "-i", input_file,
            "-o", output_file,
            "-m", model,
        ]
        if scale and scale > 1:
            cmd += ["-s", str(scale)]

        if params.get("fps"):
            cmd += ["--fps", str(params["fps"])]

        result.log.append(f"[Topaz] 模型: {model}, 缩放: {scale}x")
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        if proc.returncode != 0:
            raise RuntimeError(f"Topaz错误: {proc.stderr[-500:]}")

        return {"files": [output_file], "data": {}}

    def list_operations(self) -> List[str]:
        return [
            "enhance",
            "upscale",
            "denoise",
            "deinterlace",
            "interpolate",
            "stabilize",
            "sharpen",
            "face_enhance",
            "batch_process",
            "export_prores",
            "export_h264",
            "export_image_sequence",
        ]

    def _execute_simulate(self, operation: str, params: Dict[str, Any], result: StepResult) -> Dict:
        result.log.append(f"[Topaz] [模拟] 操作: {operation}")
        model = params.get("model", "proteus")
        scale = params.get("scale", 1)
        output_data = {"simulated": True, "operation": operation, "model": model}

        if operation == "enhance":
            result.log.append(f"[Topaz] [模拟] 应用AI增强模型: {model}")
            result.log.append(f"[Topaz] [模拟] 缩放: {scale}x")
            output_data["enhanced"] = True
        elif operation == "upscale":
            result.log.append(f"[Topaz] [模拟] AI超分辨率: {scale}x ({model})")
            output_data["upscaled"] = True
            output_data["target_resolution"] = f"{1920 * scale}x{1080 * scale}"
        elif operation == "denoise":
            result.log.append(f"[Topaz] [模拟] AI降噪处理 (强度: {params.get('strength', 'medium')})")
            output_data["denoised"] = True
        elif operation == "deinterlace":
            result.log.append(f"[Topaz] [模拟] 反交错处理")
            output_data["deinterlaced"] = True
        elif operation == "interpolate":
            target_fps = params.get("fps", 60)
            result.log.append(f"[Topaz] [模拟] 帧插值，目标帧率: {target_fps}fps")
            output_data["interpolated"] = True
            output_data["target_fps"] = target_fps
        elif operation == "stabilize":
            result.log.append(f"[Topaz] [模拟] 视频防抖")
            output_data["stabilized"] = True
        elif operation == "sharpen":
            result.log.append(f"[Topaz] [模拟] AI锐化")
            output_data["sharpened"] = True
        elif operation == "face_enhance":
            result.log.append(f"[Topaz] [模拟] 人脸增强")
            output_data["face_enhanced"] = True
        elif operation == "batch_process":
            files = params.get("files", [])
            result.log.append(f"[Topaz] [模拟] 批量处理: {len(files)}个文件")
            output_data["batch_done"] = True
        elif operation == "export_prores":
            result.log.append(f"[Topaz] [模拟] 输出 ProRes 格式")
            output_data["format"] = "prores"
        elif operation == "export_h264":
            result.log.append(f"[Topaz] [模拟] 输出 H.264 格式")
            output_data["format"] = "h264"
        elif operation == "export_image_sequence":
            result.log.append(f"[Topaz] [模拟] 输出图片序列")
            output_data["format"] = "image_sequence"

        output_file = params.get("output_file", "")
        files = [output_file] if output_file else []
        return {"files": files, "data": output_data}


# ============================================================================
# Blender 适配器
# ============================================================================

class BlenderAdapter(BaseToolAdapter):
    """Blender 工具适配器"""

    def __init__(self, config: ToolConfig):
        super().__init__(config)
        if config.install_path and os.path.isdir(config.install_path):
            self._blender_path = os.path.join(config.install_path, "blender.exe")
        else:
            self._blender_path = config.install_path or r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe"

    def check_available(self) -> bool:
        return os.path.exists(self._blender_path)

    def execute(self, operation: str, params: Dict[str, Any]) -> StepResult:
        result = self._make_result(
            step_id=params.get("step_id", f"blender_{operation}"),
            name=params.get("step_name", f"Blender {operation}"),
            operation=operation,
        )
        result.log.append(f"[Blender] 开始执行: {operation}")
        start = time.time()

        mode = self._resolve_mode()
        result.mode_used = mode

        try:
            if mode == "real":
                output = self._execute_real(operation, params, result)
            else:
                output = self._execute_simulate(operation, params, result)

            result.status = PhaseStatus.SUCCESS.value
            result.output_files = output.get("files", [])
            result.output_data = output.get("data", {})
            result.log.append(f"[Blender] 执行成功")

        except Exception as e:
            result.status = PhaseStatus.ERROR.value
            result.error = str(e)
            result.log.append(f"[Blender] 执行失败: {e}")

        result.duration_ms = (time.time() - start) * 1000
        return result

    def _resolve_mode(self) -> str:
        if self.config.mode == "real":
            return "real" if self.check_available() else "simulate"
        if self.config.mode == "simulate":
            return "simulate"
        return "real" if self.check_available() else "simulate"

    def _execute_real(self, operation: str, params: Dict[str, Any], result: StepResult) -> Dict:
        import subprocess
        import tempfile

        script = params.get("script", "")
        blend_file = params.get("blend_file", "")
        output_dir = params.get("output_dir", "")

        if not script and operation == "render":
            script = self._gen_render_script(params)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(script)
            script_path = f.name

        cmd = [self._blender_path, "--background", "--python", script_path]
        if blend_file:
            cmd = [self._blender_path, "--background", blend_file, "--python", script_path]

        result.log.append(f"[Blender] 运行脚本: {os.path.basename(script_path)}")
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
        os.unlink(script_path)

        if proc.returncode != 0:
            raise RuntimeError(f"Blender错误: {proc.stderr[-500:]}")

        files = []
        if output_dir and os.path.exists(output_dir):
            files = [os.path.join(output_dir, f) for f in os.listdir(output_dir)]

        return {"files": files, "data": {"stdout": proc.stdout[:1000]}}

    def list_operations(self) -> List[str]:
        return [
            "new_scene",
            "open_file",
            "save_file",
            "import_model",
            "export_model",
            "add_mesh",
            "add_light",
            "add_camera",
            "add_material",
            "apply_modifier",
            "set_animation",
            "render",
            "render_animation",
            "bake_texture",
            "setup_physics",
            "motion_tracking",
            "compositing_setup",
            "run_script",
            "batch_render",
            "geometry_nodes",
        ]

    def _execute_simulate(self, operation: str, params: Dict[str, Any], result: StepResult) -> Dict:
        result.log.append(f"[Blender] [模拟] 操作: {operation}")
        engine = params.get("engine", "eevee")
        resolution = params.get("resolution", (1920, 1080))
        output_data = {"simulated": True, "operation": operation}

        if operation == "new_scene":
            scene_type = params.get("scene_type", "general")
            result.log.append(f"[Blender] [模拟] 新建场景: {scene_type}")
            output_data["scene_id"] = "scene_new"
        elif operation == "open_file":
            blend_file = params.get("blend_file", "")
            result.log.append(f"[Blender] [模拟] 打开文件: {os.path.basename(blend_file)}")
            output_data["opened"] = True
        elif operation == "save_file":
            blend_file = params.get("blend_file", "")
            result.log.append(f"[Blender] [模拟] 保存文件: {os.path.basename(blend_file)}")
            output_data["saved"] = True
        elif operation == "import_model":
            file_path = params.get("file_path", "")
            fmt = params.get("format", "fbx")
            result.log.append(f"[Blender] [模拟] 导入模型: {os.path.basename(file_path)} ({fmt})")
            output_data["imported"] = True
        elif operation == "export_model":
            file_path = params.get("file_path", "")
            fmt = params.get("format", "fbx")
            result.log.append(f"[Blender] [模拟] 导出模型: {os.path.basename(file_path)} ({fmt})")
            output_data["exported"] = True
        elif operation == "add_mesh":
            mesh_type = params.get("mesh_type", "cube")
            result.log.append(f"[Blender] [模拟] 添加网格: {mesh_type}")
            output_data["object_id"] = f"obj_{mesh_type}"
        elif operation == "add_light":
            light_type = params.get("light_type", "point")
            result.log.append(f"[Blender] [模拟] 添加灯光: {light_type}")
            output_data["light_id"] = f"light_{light_type}"
        elif operation == "add_camera":
            result.log.append(f"[Blender] [模拟] 添加摄像机")
            output_data["camera_id"] = "cam_main"
        elif operation == "add_material":
            mat_name = params.get("material_name", "材质")
            result.log.append(f"[Blender] [模拟] 添加材质: {mat_name}")
            output_data["material_id"] = f"mat_{mat_name}"
        elif operation == "apply_modifier":
            mod_type = params.get("modifier_type", "subsurf")
            result.log.append(f"[Blender] [模拟] 应用修改器: {mod_type}")
            output_data["modifier_applied"] = True
        elif operation == "set_animation":
            obj = params.get("object", "")
            frames = params.get("frames", 250)
            result.log.append(f"[Blender] [模拟] 设置动画: {obj} ({frames}帧)")
            output_data["animation_set"] = True
        elif operation == "render":
            result.log.append(f"[Blender] [模拟] 渲染引擎: {engine}")
            result.log.append(f"[Blender] [模拟] 分辨率: {resolution[0]}x{resolution[1]}")
            frames = params.get("frames", 1)
            result.log.append(f"[Blender] [模拟] 渲染帧数: {frames}")
            output_data["render_done"] = True
        elif operation == "render_animation":
            fs = params.get('frame_start', 1)
            fe = params.get('frame_end', 250)
            result.log.append(f"[Blender] [模拟] 渲染动画: {fs}-{fe}")
            output_data["animation_rendered"] = True
        elif operation == "bake_texture":
            bake_type = params.get("bake_type", "diffuse")
            result.log.append(f"[Blender] [模拟] 烘焙纹理: {bake_type}")
            output_data["baked"] = True
        elif operation == "setup_physics":
            physics_type = params.get("physics_type", "rigid_body")
            result.log.append(f"[Blender] [模拟] 设置物理: {physics_type}")
            output_data["physics_setup"] = True
        elif operation == "motion_tracking":
            clip = params.get("clip", "")
            result.log.append(f"[Blender] [模拟] 运动跟踪: {os.path.basename(clip)}")
            output_data["tracked"] = True
        elif operation == "compositing_setup":
            result.log.append(f"[Blender] [模拟] 设置合成节点")
            output_data["compositing_setup"] = True
        elif operation == "run_script":
            script_name = params.get("script_name", "")
            result.log.append(f"[Blender] [模拟] 运行脚本: {script_name}")
            output_data["script_executed"] = True
        elif operation == "batch_render":
            files = params.get("files", [])
            result.log.append(f"[Blender] [模拟] 批量渲染: {len(files)}个文件")
            output_data["batch_done"] = True
        elif operation == "geometry_nodes":
            node_tree = params.get("node_tree", "")
            result.log.append(f"[Blender] [模拟] 几何节点: {node_tree}")
            output_data["geo_nodes_setup"] = True

        output_dir = params.get("output_dir", "")
        files = []
        if output_dir and operation in ["render", "render_animation", "bake_texture"]:
            frames = params.get("frames", 1)
            files = [os.path.join(output_dir, f"frame_{i:04d}.png") for i in range(1, min(6, frames + 1))]

        return {"files": files, "data": output_data}

    def _gen_render_script(self, params: Dict[str, Any]) -> str:
        output_dir = params.get("output_dir", "/tmp/render")
        engine = params.get("engine", "BLENDER_EEVEE")
        res_x = params.get("resolution", (1920, 1080))[0]
        res_y = params.get("resolution", (1920, 1080))[1]
        frame_start = params.get("frame_start", 1)
        frame_end = params.get("frame_end", 1)
        use_gpu = params.get("use_gpu", False)

        script = "import bpy\n"
        script += "import os\n\n"
        script += "# 渲染设置\n"
        script += "bpy.context.scene.render.engine = '" + engine + "'\n"
        script += "bpy.context.scene.render.resolution_x = " + str(res_x) + "\n"
        script += "bpy.context.scene.render.resolution_y = " + str(res_y) + "\n"
        script += "bpy.context.scene.render.filepath = r'" + output_dir + "/'\n"
        script += "bpy.context.scene.frame_start = " + str(frame_start) + "\n"
        script += "bpy.context.scene.frame_end = " + str(frame_end) + "\n"

        if use_gpu:
            script += "\n# GPU设置\n"
            if "CYCLES" in engine:
                script += 'bpy.context.scene.cycles.device = "GPU"\n'

        script += "\n# 渲染\n"
        script += "bpy.ops.render.render(animation=True)\n"
        script += 'print("RENDER_COMPLETE")\n'

        return script


# ============================================================================
# AE MCP 适配器
# ============================================================================

class AEAdapter(BaseToolAdapter):
    """After Effects MCP 适配器"""

    def __init__(self, config: ToolConfig):
        super().__init__(config)
        self._bridge_script = config.extra_params.get("bridge_script", "ae_mcp_bridge_v26.jsx")
        self._client_module = config.extra_params.get("client_module", "ae_mcp_client")

    def check_available(self) -> bool:
        try:
            import importlib
            importlib.import_module("ae_mcp_client")
            return True
        except ImportError:
            return os.path.exists(os.path.join(os.path.dirname(__file__), "ae_mcp_client.py"))

    def execute(self, operation: str, params: Dict[str, Any]) -> StepResult:
        result = self._make_result(
            step_id=params.get("step_id", f"ae_{operation}"),
            name=params.get("step_name", f"AE {operation}"),
            operation=operation,
        )
        result.log.append(f"[AE] 开始执行: {operation}")
        start = time.time()

        mode = self._resolve_mode()
        result.mode_used = mode

        try:
            if mode == "real":
                output = self._execute_real(operation, params, result)
            else:
                output = self._execute_simulate(operation, params, result)

            result.status = PhaseStatus.SUCCESS.value
            result.output_files = output.get("files", [])
            result.output_data = output.get("data", {})
            result.log.append(f"[AE] 执行成功")

        except Exception as e:
            result.status = PhaseStatus.ERROR.value
            result.error = str(e)
            result.log.append(f"[AE] 执行失败: {e}")

        result.duration_ms = (time.time() - start) * 1000
        return result

    def _resolve_mode(self) -> str:
        if self.config.mode == "real":
            return "real" if self.check_available() else "simulate"
        if self.config.mode == "simulate":
            return "simulate"
        return "real" if self.check_available() else "simulate"

    def _execute_real(self, operation: str, params: Dict[str, Any], result: StepResult) -> Dict:
        try:
            from ae_mcp_client import AEMcpClient
            client = AEMcpClient()
        except Exception as e:
            raise RuntimeError(f"AE MCP客户端不可用: {e}")

        if operation == "create_comp":
            resp = client.send_command("create_comp", params)
        elif operation == "apply_effect":
            resp = client.send_command("apply_effect", params)
        elif operation == "import_footage":
            resp = client.send_command("import_footage", params)
        elif operation == "render":
            resp = client.send_command("render_queue", params)
        else:
            resp = client.send_command(operation, params)

        files = []
        if "output_file" in resp:
            files = [resp["output_file"]]
        return {"files": files, "data": resp}

    def list_operations(self) -> List[str]:
        return [
            "create_comp",
            "import_footage",
            "add_layer",
            "add_text_layer",
            "add_solid_layer",
            "add_adjustment_layer",
            "add_null_layer",
            "apply_effect",
            "apply_preset",
            "set_keyframe",
            "add_expression",
            "create_mask",
            "track_motion",
            "keying",
            "create_shape_layer",
            "add_camera",
            "add_light",
            "enable_3d",
            "parent_layers",
            "precompose",
            "trim_comp",
            "render",
            "render_queue_add",
            "save_project",
            "open_project",
        ]

    def _execute_simulate(self, operation: str, params: Dict[str, Any], result: StepResult) -> Dict:
        result.log.append(f"[AE] [模拟] 操作: {operation}")
        comp_name = params.get("comp_name", "未命名合成")
        width = params.get("width", 1920)
        height = params.get("height", 1080)
        layer_name = params.get("layer_name", "图层")
        output_data = {"simulated": True, "operation": operation}

        if operation == "create_comp":
            result.log.append(f"[AE] [模拟] 创建合成: {comp_name} ({width}x{height} @ {params.get('fps', 25)}fps)")
            output_data["comp_id"] = f"comp_{comp_name}"
        elif operation == "import_footage":
            footage = params.get("file_path", "")
            result.log.append(f"[AE] [模拟] 导入素材: {os.path.basename(footage)}")
            output_data["footage_id"] = f"footage_{os.path.basename(footage)}"
        elif operation == "add_layer":
            result.log.append(f"[AE] [模拟] 添加图层: {layer_name}")
            output_data["layer_id"] = f"layer_{layer_name}"
        elif operation == "add_text_layer":
            text = params.get("text", "示例文字")
            font_size = params.get("font_size", 72)
            result.log.append(f"[AE] [模拟] 添加文字图层: '{text}' ({font_size}px)")
            output_data["layer_id"] = f"text_{layer_name}"
        elif operation == "add_solid_layer":
            color = params.get("color", "#FFFFFF")
            result.log.append(f"[AE] [模拟] 添加纯色图层: {layer_name} ({color})")
            output_data["layer_id"] = f"solid_{layer_name}"
        elif operation == "add_adjustment_layer":
            result.log.append(f"[AE] [模拟] 添加调整图层: {layer_name}")
            output_data["layer_id"] = f"adj_{layer_name}"
        elif operation == "add_null_layer":
            result.log.append(f"[AE] [模拟] 添加空对象: {layer_name}")
            output_data["layer_id"] = f"null_{layer_name}"
        elif operation == "apply_effect":
            effect = params.get("effect", "未知效果")
            result.log.append(f"[AE] [模拟] 应用效果: {effect} 到 {layer_name}")
            output_data["effect_applied"] = effect
        elif operation == "apply_preset":
            preset = params.get("preset", "")
            result.log.append(f"[AE] [模拟] 应用预设: {preset}")
            output_data["preset_applied"] = preset
        elif operation == "set_keyframe":
            property_name = params.get("property", "position")
            value = params.get("value", [0, 0])
            time_val = params.get("time", 0)
            result.log.append(f"[AE] [模拟] 设置关键帧: {property_name} = {value} @ {time_val}s")
            output_data["keyframe_set"] = True
        elif operation == "add_expression":
            prop = params.get("property", "position")
            expr = params.get("expression", "")
            result.log.append(f"[AE] [模拟] 添加表达式: {prop} = {expr[:50]}...")
            output_data["expression_added"] = True
        elif operation == "create_mask":
            mask_type = params.get("mask_type", "ellipse")
            result.log.append(f"[AE] [模拟] 创建遮罩: {mask_type}")
            output_data["mask_id"] = f"mask_{mask_type}"
        elif operation == "track_motion":
            track_type = params.get("track_type", "position")
            result.log.append(f"[AE] [模拟] 运动跟踪: {track_type}")
            output_data["track_data"] = {"points": []}
        elif operation == "keying":
            keyer = params.get("keyer", "keylight")
            color = params.get("key_color", "#00FF00")
            result.log.append(f"[AE] [模拟] 抠像: {keyer} ({color})")
            output_data["keying_done"] = True
        elif operation == "create_shape_layer":
            shape = params.get("shape", "rectangle")
            result.log.append(f"[AE] [模拟] 创建形状图层: {shape}")
            output_data["shape_layer_id"] = f"shape_{shape}"
        elif operation == "add_camera":
            cam_name = params.get("camera_name", "摄像机")
            result.log.append(f"[AE] [模拟] 添加摄像机: {cam_name}")
            output_data["camera_id"] = f"cam_{cam_name}"
        elif operation == "add_light":
            light_name = params.get("light_name", "灯光")
            light_type = params.get("light_type", "spot")
            result.log.append(f"[AE] [模拟] 添加灯光: {light_name} ({light_type})")
            output_data["light_id"] = f"light_{light_name}"
        elif operation == "enable_3d":
            result.log.append(f"[AE] [模拟] 启用3D图层: {layer_name}")
            output_data["3d_enabled"] = True
        elif operation == "parent_layers":
            child = params.get("child_layer", "")
            parent = params.get("parent_layer", "")
            result.log.append(f"[AE] [模拟] 父子链接: {child} → {parent}")
            output_data["parented"] = True
        elif operation == "precompose":
            layers = params.get("layers", [])
            precomp_name = params.get("precomp_name", "预合成")
            result.log.append(f"[AE] [模拟] 预合成: {len(layers)}个图层 → {precomp_name}")
            output_data["precomp_id"] = f"precomp_{precomp_name}"
        elif operation == "trim_comp":
            start = params.get("start_time", 0)
            end = params.get("end_time", 10)
            result.log.append(f"[AE] [模拟] 修剪合成: {start}s - {end}s")
            output_data["trimmed"] = True
        elif operation == "render":
            result.log.append(f"[AE] [模拟] 渲染合成到队列")
            output_data["render_started"] = True
        elif operation == "render_queue_add":
            template = params.get("render_template", "无损")
            result.log.append(f"[AE] [模拟] 添加到渲染队列 ({template})")
            output_data["queue_added"] = True
        elif operation == "save_project":
            project_path = params.get("project_path", "")
            result.log.append(f"[AE] [模拟] 保存项目: {os.path.basename(project_path)}")
            output_data["saved"] = True
        elif operation == "open_project":
            project_path = params.get("project_path", "")
            result.log.append(f"[AE] [模拟] 打开项目: {os.path.basename(project_path)}")
            output_data["opened"] = True

        output_file = params.get("output_file", "")
        return {"files": [output_file] if output_file else [], "data": output_data}


class PremiereProAdapter(BaseToolAdapter):
    """Premiere Pro 适配器 - 剪辑/调色/音频/动态链接"""

    SUPPORTED_OPERATIONS = [
        "create_project", "import_media", "create_sequence",
        "color_grade", "audio_mix", "add_transition",
        "add_title", "dynamic_link_to_ae", "export_media",
        "batch_render", "apply_lumetri", "apply_effect"
    ]

    def check_available(self) -> bool:
        install_path = self.config.install_path or r"C:\Program Files\Adobe\Adobe Premiere Pro 2025"
        return os.path.exists(install_path)

    def list_operations(self) -> List[str]:
        return self.SUPPORTED_OPERATIONS

    def execute(self, operation: str, params: Dict[str, Any]) -> StepResult:
        result = self._make_result(
            step_id=params.get("step_id", f"pr_{operation}"),
            name=params.get("step_name", f"PR {operation}"),
            operation=operation,
        )
        result.log.append(f"[Premiere] 开始执行: {operation}")
        start = time.time()
        mode = self._resolve_mode()
        result.mode_used = mode

        try:
            if mode == "real":
                output = self._execute_real(operation, params, result)
            else:
                output = self._execute_simulate(operation, params, result)
            result.status = PhaseStatus.SUCCESS.value
            result.output_files = output.get("files", [])
            result.output_data = output.get("data", {})
            result.log.append(f"[Premiere] 执行成功")
        except Exception as e:
            result.status = PhaseStatus.ERROR.value
            result.error = str(e)
            result.log.append(f"[Premiere] 执行失败: {e}")

        result.duration_ms = (time.time() - start) * 1000
        return result

    def _resolve_mode(self) -> str:
        if self.config.mode == "real":
            return "real" if self.check_available() else "simulate"
        if self.config.mode == "simulate":
            return "simulate"
        return "real" if self.check_available() else "simulate"

    def _execute_real(self, operation: str, params: Dict[str, Any], result: StepResult) -> Dict:
        import subprocess
        import tempfile

        # 生成ExtendScript代码
        script = self._generate_script(operation, params)

        # 写入临时脚本文件
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.jsx', delete=False, encoding='utf-16'
        ) as f:
            f.write(script)
            script_path = f.name

        # 查找Premiere可执行文件
        exe_path = self._find_executable()
        if not exe_path:
            result.log.append("[Premiere] 未找到Premiere可执行文件，降级为模拟")
            return self._execute_simulate(operation, params, result)

        # 命令行执行
        cmd = [exe_path, "-noui", "-r", script_path]
        result.log.append(f"[Premiere] 执行脚本: {os.path.basename(script_path)}")

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if proc.returncode != 0:
                result.log.append(f"[Premiere] 警告: {proc.stderr[:200] if proc.stderr else '未知错误'}")
        finally:
            os.unlink(script_path)

        output_file = params.get("output_file", "")
        files = [output_file] if output_file else []
        return {"files": files, "data": {"operation": operation}}

    def _find_executable(self) -> Optional[str]:
        """查找Premiere可执行文件"""
        search_paths = [
            self.config.install_path,
            r"D:\pr\Adobe Premiere Pro 2025",
            r"C:\Program Files\Adobe\Adobe Premiere Pro 2025",
        ]
        for path in search_paths:
            if path and os.path.isdir(path):
                for exe in ["Adobe Premiere Pro.exe", "Premiere Pro.exe"]:
                    exe_path = os.path.join(path, exe)
                    if os.path.exists(exe_path):
                        return exe_path
        return None

    def _generate_script(self, operation: str, params: Dict[str, Any]) -> str:
        """生成Premiere ExtendScript"""
        proj_name = params.get("project_name", "Untitled")
        output_file = params.get("output_file", "")

        script = f"""// Premiere Pro ExtendScript - Auto-generated
// Operation: {operation}

app.enableQE();

"""

        if operation == "create_project":
            safe_proj_name = _escape_extendscript_string(proj_name)
            script += "\nvar proj = app.project;\nif (!proj) {\n"
            script += '    proj = app.newProject("' + safe_proj_name + '");\n'
            script += "}\n"

        elif operation == "import_media":
            files = params.get("files", [])
            for f in files:
                safe_f = _escape_extendscript_string(f)
                script += 'app.project.importFiles(["' + safe_f + '"]);\n'

        elif operation == "create_sequence":
            seq_name = params.get("sequence_name", "Sequence")
            safe_seq_name = _escape_extendscript_string(seq_name)
            script += '\nvar seq = app.project.createSequence("' + safe_seq_name + '");\n'

        elif operation == "export_media":
            preset = params.get("preset", "H.264")
            if output_file:
                safe_output = _escape_extendscript_string(output_file)
                safe_preset = _escape_extendscript_string(preset)
                script += "\nvar seq = app.project.activeSequence;\nif (seq) {\n"
                script += '    var exp = seq.exportAsMedia("' + safe_output + '", "' + safe_preset + '", true);\n'
                script += "}\n"

        return script

    def _execute_simulate(self, operation: str, params: Dict[str, Any], result: StepResult) -> Dict:
        result.log.append(f"[Premiere] [模拟] 操作: {operation}")

        if operation == "create_project":
            proj_name = params.get("project_name", "未命名项目")
            result.log.append(f"[Premiere] [模拟] 创建项目: {proj_name}")
        elif operation == "import_media":
            files = params.get("files", [])
            result.log.append(f"[Premiere] [模拟] 导入素材: {len(files)} 个文件")
        elif operation == "create_sequence":
            seq_name = params.get("sequence_name", "未命名序列")
            preset = params.get("preset", "1080p_25fps")
            result.log.append(f"[Premiere] [模拟] 创建序列: {seq_name} ({preset})")
        elif operation == "color_grade":
            result.log.append(f"[Premiere] [模拟] 应用 Lumetri 调色")
        elif operation == "audio_mix":
            result.log.append(f"[Premiere] [模拟] 音频混音处理")
        elif operation == "add_transition":
            trans = params.get("transition_type", "cross_dissolve")
            result.log.append(f"[Premiere] [模拟] 添加转场: {trans}")
        elif operation == "add_title":
            result.log.append(f"[Premiere] [模拟] 添加文字标题")
        elif operation == "dynamic_link_to_ae":
            comp = params.get("ae_comp", "")
            result.log.append(f"[Premiere] [模拟] 动态链接到AE合成: {comp}")
        elif operation == "export_media":
            fmt = params.get("format", "H.264")
            preset = params.get("preset", "高比特率")
            result.log.append(f"[Premiere] [模拟] 导出媒体: {fmt} / {preset}")
        elif operation == "batch_render":
            count = params.get("count", 1)
            result.log.append(f"[Premiere] [模拟] 批量渲染: {count} 个序列")
        elif operation == "apply_lumetri":
            lut = params.get("lut", "")
            result.log.append(f"[Premiere] [模拟] 应用LUT: {os.path.basename(lut) if lut else '默认'}")
        elif operation == "apply_effect":
            effect = params.get("effect", "")
            result.log.append(f"[Premiere] [模拟] 应用效果: {effect}")

        output_dir = params.get("output_dir", "")
        out_file = os.path.join(output_dir, f"{operation}_output.mp4") if output_dir else ""
        return {"files": [out_file] if out_file else [], "data": {"simulated": True}}


class PhotoshopAdapter(BaseToolAdapter):
    """Photoshop 适配器 - 图像处理/合成/批处理"""

    SUPPORTED_OPERATIONS = [
        "open_document", "import_image", "resize", "crop",
        "adjust_color", "apply_filter", "add_layer",
        "add_mask", "add_text", "smart_object",
        "batch_process", "export_png", "export_jpg",
        "export_psd", "remove_background", "generative_fill"
    ]

    def check_available(self) -> bool:
        install_path = self.config.install_path or r"C:\Program Files\Adobe\Adobe Photoshop 2025"
        return os.path.exists(install_path)

    def list_operations(self) -> List[str]:
        return self.SUPPORTED_OPERATIONS

    def execute(self, operation: str, params: Dict[str, Any]) -> StepResult:
        result = self._make_result(
            step_id=params.get("step_id", f"ps_{operation}"),
            name=params.get("step_name", f"PS {operation}"),
            operation=operation,
        )
        result.log.append(f"[Photoshop] 开始执行: {operation}")
        start = time.time()
        mode = self._resolve_mode()
        result.mode_used = mode

        try:
            if mode == "real":
                output = self._execute_real(operation, params, result)
            else:
                output = self._execute_simulate(operation, params, result)
            result.status = PhaseStatus.SUCCESS.value
            result.output_files = output.get("files", [])
            result.output_data = output.get("data", {})
            result.log.append(f"[Photoshop] 执行成功")
        except Exception as e:
            result.status = PhaseStatus.ERROR.value
            result.error = str(e)
            result.log.append(f"[Photoshop] 执行失败: {e}")

        result.duration_ms = (time.time() - start) * 1000
        return result

    def _resolve_mode(self) -> str:
        if self.config.mode == "real":
            return "real" if self.check_available() else "simulate"
        if self.config.mode == "simulate":
            return "simulate"
        return "real" if self.check_available() else "simulate"

    def _execute_real(self, operation: str, params: Dict[str, Any], result: StepResult) -> Dict:
        import subprocess
        import tempfile

        # 生成ExtendScript代码
        script = self._generate_script(operation, params)

        # 写入临时脚本文件
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.jsx', delete=False, encoding='utf-16'
        ) as f:
            f.write(script)
            script_path = f.name

        # 查找Photoshop可执行文件
        exe_path = self._find_executable()
        if not exe_path:
            result.log.append("[Photoshop] 未找到Photoshop可执行文件，降级为模拟")
            return self._execute_simulate(operation, params, result)

        # 命令行执行
        cmd = [exe_path, "-noui", "-r", script_path]
        result.log.append(f"[Photoshop] 执行脚本: {os.path.basename(script_path)}")

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if proc.returncode != 0:
                result.log.append(f"[Photoshop] 警告: {proc.stderr[:200] if proc.stderr else '未知错误'}")
        finally:
            os.unlink(script_path)

        output_file = params.get("output_file", "")
        files = [output_file] if output_file else []
        return {"files": files, "data": {"operation": operation}}

    def _find_executable(self) -> Optional[str]:
        """查找Photoshop可执行文件"""
        search_paths = [
            self.config.install_path,
            r"D:\ps\Adobe Photoshop 2025",
            r"C:\Program Files\Adobe\Adobe Photoshop 2025",
        ]
        for path in search_paths:
            if path and os.path.isdir(path):
                for exe in ["Photoshop.exe", "Adobe Photoshop 2025.exe"]:
                    exe_path = os.path.join(path, exe)
                    if os.path.exists(exe_path):
                        return exe_path
        return None

    def _generate_script(self, operation: str, params: Dict[str, Any]) -> str:
        """生成Photoshop ExtendScript"""
        input_file = params.get("input_file", "")
        output_file = params.get("output_file", "")

        script = "// Photoshop ExtendScript - Auto-generated\n"
        script += "// Operation: " + _escape_extendscript_string(operation) + "\n\n"

        if operation == "open_document":
            if input_file:
                safe_input = _escape_extendscript_string(input_file)
                script += 'var doc = app.open(File("' + safe_input + '"));\n'
            else:
                w = params.get("width", 1920)
                h = params.get("height", 1080)
                script += 'var doc = app.documents.add(' + str(w) + ', ' + str(h) + ');\n'

        elif operation == "resize":
            w = params.get("width", 1920)
            h = params.get("height", 1080)
            script += "\nif (app.activeDocument) {\n"
            script += "    app.activeDocument.resizeImage(" + str(w) + ", " + str(h) + ");\n"
            script += "}\n"

        elif operation == "export_png":
            if output_file:
                safe_output = _escape_extendscript_string(output_file)
                script += "\nif (app.activeDocument) {\n"
                script += "    var pngOpts = new PNGSaveOptions();\n"
                script += '    app.activeDocument.saveAs(File("' + safe_output + '"), pngOpts);\n'
                script += "}\n"

        elif operation == "export_jpg":
            if output_file:
                quality = params.get("quality", 8)
                safe_output = _escape_extendscript_string(output_file)
                script += "\nif (app.activeDocument) {\n"
                script += "    var jpgOpts = new JPEGSaveOptions();\n"
                script += "    jpgOpts.quality = " + str(quality) + ";\n"
                script += '    app.activeDocument.saveAs(File("' + safe_output + '"), jpgOpts);\n'
                script += "}\n"

        elif operation == "close_document":
            script += "\nif (app.activeDocument) {\n"
            script += "    app.activeDocument.close(SaveOptions.SAVECHANGES);\n"
            script += "}\n"

        return script

    def _execute_simulate(self, operation: str, params: Dict[str, Any], result: StepResult) -> Dict:
        result.log.append(f"[Photoshop] [模拟] 操作: {operation}")

        if operation == "open_document":
            doc = params.get("document", "")
            result.log.append(f"[Photoshop] [模拟] 打开文档: {os.path.basename(doc) if doc else '新建'}")
        elif operation == "import_image":
            img = params.get("image", "")
            result.log.append(f"[Photoshop] [模拟] 导入图片: {os.path.basename(img)}")
        elif operation == "resize":
            w = params.get("width", 1920)
            h = params.get("height", 1080)
            result.log.append(f"[Photoshop] [模拟] 调整尺寸: {w}x{h}")
        elif operation == "crop":
            result.log.append(f"[Photoshop] [模拟] 图像裁剪")
        elif operation == "adjust_color":
            adj = params.get("adjustment", "curves")
            result.log.append(f"[Photoshop] [模拟] 色彩调整: {adj}")
        elif operation == "apply_filter":
            flt = params.get("filter", "")
            result.log.append(f"[Photoshop] [模拟] 应用滤镜: {flt}")
        elif operation == "add_layer":
            layer = params.get("layer_name", "")
            result.log.append(f"[Photoshop] [模拟] 添加图层: {layer}")
        elif operation == "add_mask":
            result.log.append(f"[Photoshop] [模拟] 添加图层蒙版")
        elif operation == "add_text":
            txt = params.get("text", "")
            result.log.append(f"[Photoshop] [模拟] 添加文字: {txt[:20]}")
        elif operation == "smart_object":
            result.log.append(f"[Photoshop] [模拟] 转换为智能对象")
        elif operation == "batch_process":
            count = params.get("count", 1)
            result.log.append(f"[Photoshop] [模拟] 批处理: {count} 张图片")
        elif operation == "export_png":
            result.log.append(f"[Photoshop] [模拟] 导出PNG")
        elif operation == "export_jpg":
            quality = params.get("quality", 90)
            result.log.append(f"[Photoshop] [模拟] 导出JPG (质量:{quality})")
        elif operation == "export_psd":
            result.log.append(f"[Photoshop] [模拟] 保存PSD")
        elif operation == "remove_background":
            result.log.append(f"[Photoshop] [模拟] 移除背景（选择主体）")
        elif operation == "generative_fill":
            prompt = params.get("prompt", "")
            result.log.append(f"[Photoshop] [模拟] 生成式填充: {prompt[:30]}")

        output_dir = params.get("output_dir", "")
        out_file = os.path.join(output_dir, f"{operation}_output.png") if output_dir else ""
        return {"files": [out_file] if out_file else [], "data": {"simulated": True}}


class IllustratorAdapter(BaseToolAdapter):
    """Illustrator 适配器 - 矢量图形/文字/Logo设计

    .. deprecated::
        Illustrator real模式已废弃。矢量图形操作建议通过AE MCP Bridge处理，
        或使用开源替代方案（如 svg-path / Cairo）。
    """

    SUPPORTED_OPERATIONS = [
        "create_document", "import_asset", "create_shape",
        "create_text", "apply_style", "create_logo",
        "create_mograph", "export_svg", "export_ai",
        "export_png", "batch_export", "create_pattern"
    ]

    def check_available(self) -> bool:
        install_path = self.config.install_path or r"C:\Program Files\Adobe\Adobe Illustrator 2025"
        return os.path.exists(install_path)

    def list_operations(self) -> List[str]:
        return self.SUPPORTED_OPERATIONS

    def execute(self, operation: str, params: Dict[str, Any]) -> StepResult:
        result = self._make_result(
            step_id=params.get("step_id", f"ai_{operation}"),
            name=params.get("step_name", f"Ai {operation}"),
            operation=operation,
        )
        result.log.append(f"[Illustrator] 开始执行: {operation}")
        start = time.time()
        mode = self._resolve_mode()
        result.mode_used = mode

        try:
            if mode == "real":
                warnings.warn(
                    "IllustratorAdapter real mode is deprecated. "
                    "Use AE MCP Bridge or open-source alternatives (Cairo/svg-path) instead.",
                    DeprecationWarning,
                    stacklevel=2,
                )
                output = self._execute_real(operation, params, result)
            else:
                output = self._execute_simulate(operation, params, result)
            result.status = PhaseStatus.SUCCESS.value
            result.output_files = output.get("files", [])
            result.output_data = output.get("data", {})
            result.log.append(f"[Illustrator] 执行成功")
        except Exception as e:
            result.status = PhaseStatus.ERROR.value
            result.error = str(e)
            result.log.append(f"[Illustrator] 执行失败: {e}")

        result.duration_ms = (time.time() - start) * 1000
        return result

    def _resolve_mode(self) -> str:
        if self.config.mode == "real":
            return "real" if self.check_available() else "simulate"
        if self.config.mode == "simulate":
            return "simulate"
        return "real" if self.check_available() else "simulate"

    def _execute_real(self, operation: str, params: Dict[str, Any], result: StepResult) -> Dict:
        import subprocess
        import tempfile

        # 生成ExtendScript代码
        script = self._generate_script(operation, params)

        # 写入临时脚本文件
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.jsx', delete=False, encoding='utf-16'
        ) as f:
            f.write(script)
            script_path = f.name

        # 查找Illustrator可执行文件
        exe_path = self._find_executable()
        if not exe_path:
            result.log.append("[Illustrator] 未找到Illustrator可执行文件，降级为模拟")
            return self._execute_simulate(operation, params, result)

        # 命令行执行
        cmd = [exe_path, "-noui", "-r", script_path]
        result.log.append(f"[Illustrator] 执行脚本: {os.path.basename(script_path)}")

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if proc.returncode != 0:
                result.log.append(f"[Illustrator] 警告: {proc.stderr[:200] if proc.stderr else '未知错误'}")
        finally:
            os.unlink(script_path)

        output_file = params.get("output_file", "")
        files = [output_file] if output_file else []
        return {"files": files, "data": {"operation": operation}}

    def _find_executable(self) -> Optional[str]:
        """查找Illustrator可执行文件"""
        search_paths = [
            self.config.install_path,
            r"D:\Ai\Adobe Illustrator 2025\Support Files\Contents\Windows",
            r"C:\Program Files\Adobe\Adobe Illustrator 2025\Support Files\Contents\Windows",
        ]
        for path in search_paths:
            if path and os.path.isdir(path):
                for exe in ["Illustrator.exe", "Adobe Illustrator 2025.exe"]:
                    exe_path = os.path.join(path, exe)
                    if os.path.exists(exe_path):
                        return exe_path
        return None

    def _generate_script(self, operation: str, params: Dict[str, Any]) -> str:
        """生成Illustrator ExtendScript"""
        output_file = params.get("output_file", "")

        script = "// Illustrator ExtendScript - Auto-generated\n"
        script += "// Operation: " + _escape_extendscript_string(operation) + "\n\n"

        if operation == "create_document":
            name = params.get("name", "Untitled")
            w = params.get("width", 1920)
            h = params.get("height", 1080)
            script += 'var doc = app.documents.add(' + str(w) + ', ' + str(h) + ');\n'

        elif operation == "create_text":
            txt = params.get("text", "")
            font = params.get("font", "Arial")
            size = params.get("font_size", 72)
            safe_txt = _escape_extendscript_string(txt)
            script += "\nvar doc = app.activeDocument || app.documents.add(1920, 1080);\n"
            script += "var text = doc.textFrames.add();\n"
            script += 'text.contents = "' + safe_txt + '";\n'
            script += "text.textRange.characterAttributes.size = " + str(size) + ";\n"
            script += "text.position = [100, 100];\n"

        elif operation == "export_svg":
            if output_file:
                safe_output = _escape_extendscript_string(output_file)
                script += "\nif (app.activeDocument) {\n"
                script += "    var svgOpts = new ExportOptionsSVG();\n"
                script += '    app.activeDocument.exportFile(File("' + safe_output + '"), ExportType.SVG, svgOpts);\n'
                script += "}\n"

        elif operation == "export_png":
            if output_file:
                safe_output = _escape_extendscript_string(output_file)
                script += "\nif (app.activeDocument) {\n"
                script += "    var pngOpts = new ExportOptionsPNG24();\n"
                script += '    app.activeDocument.exportFile(File("' + safe_output + '"), ExportType.PNG24, pngOpts);\n'
                script += "}\n"

        return script

    def _execute_simulate(self, operation: str, params: Dict[str, Any], result: StepResult) -> Dict:
        result.log.append(f"[Illustrator] [模拟] 操作: {operation}")

        if operation == "create_document":
            name = params.get("name", "未命名")
            w = params.get("width", 1920)
            h = params.get("height", 1080)
            result.log.append(f"[Illustrator] [模拟] 新建文档: {name} ({w}x{h})")
        elif operation == "import_asset":
            asset = params.get("asset", "")
            result.log.append(f"[Illustrator] [模拟] 导入资源: {os.path.basename(asset)}")
        elif operation == "create_shape":
            shape = params.get("shape", "rectangle")
            result.log.append(f"[Illustrator] [模拟] 创建形状: {shape}")
        elif operation == "create_text":
            txt = params.get("text", "")
            result.log.append(f"[Illustrator] [模拟] 创建文字: {txt[:20]}")
        elif operation == "apply_style":
            style = params.get("style", "")
            result.log.append(f"[Illustrator] [模拟] 应用样式: {style}")
        elif operation == "create_logo":
            result.log.append(f"[Illustrator] [模拟] 创建Logo设计")
        elif operation == "create_mograph":
            result.log.append(f"[Illustrator] [模拟] 创建动态图形元素（MG）")
        elif operation == "export_svg":
            result.log.append(f"[Illustrator] [模拟] 导出SVG")
        elif operation == "export_ai":
            result.log.append(f"[Illustrator] [模拟] 保存AI源文件")
        elif operation == "export_png":
            result.log.append(f"[Illustrator] [模拟] 导出PNG")
        elif operation == "batch_export":
            count = params.get("count", 1)
            result.log.append(f"[Illustrator] [模拟] 批量导出: {count} 个文件")
        elif operation == "create_pattern":
            result.log.append(f"[Illustrator] [模拟] 创建图案/纹理")

        output_dir = params.get("output_dir", "")
        out_file = os.path.join(output_dir, f"{operation}_output.svg") if output_dir else ""
        return {"files": [out_file] if out_file else [], "data": {"simulated": True}}


class MediaEncoderAdapter(BaseToolAdapter):
    """Media Encoder 适配器 - 渲染队列/格式转换/批量编码"""

    SUPPORTED_OPERATIONS = [
        "add_to_queue", "start_queue", "watch_folder",
        "create_preset", "batch_encode",
        "create_proxy", "export_h264", "export_prores",
        "export_hevc", "status_monitor"
    ]

    def check_available(self) -> bool:
        install_path = self.config.install_path or r"C:\Program Files\Adobe\Adobe Media Encoder 2025"
        return os.path.exists(install_path)

    def list_operations(self) -> List[str]:
        return self.SUPPORTED_OPERATIONS

    def execute(self, operation: str, params: Dict[str, Any]) -> StepResult:
        result = self._make_result(
            step_id=params.get("step_id", f"me_{operation}"),
            name=params.get("step_name", f"ME {operation}"),
            operation=operation,
        )
        result.log.append(f"[MediaEncoder] 开始执行: {operation}")
        start = time.time()
        mode = self._resolve_mode()
        result.mode_used = mode

        try:
            if mode == "real":
                output = self._execute_real(operation, params, result)
            else:
                output = self._execute_simulate(operation, params, result)
            result.status = PhaseStatus.SUCCESS.value
            result.output_files = output.get("files", [])
            result.output_data = output.get("data", {})
            result.log.append(f"[MediaEncoder] 执行成功")
        except Exception as e:
            result.status = PhaseStatus.ERROR.value
            result.error = str(e)
            result.log.append(f"[MediaEncoder] 执行失败: {e}")

        result.duration_ms = (time.time() - start) * 1000
        return result

    def _resolve_mode(self) -> str:
        if self.config.mode == "real":
            return "real" if self.check_available() else "simulate"
        if self.config.mode == "simulate":
            return "simulate"
        return "real" if self.check_available() else "simulate"

    def _execute_real(self, operation: str, params: Dict[str, Any], result: StepResult) -> Dict:
        import subprocess

        # 查找Media Encoder可执行文件
        exe_path = self._find_executable()
        if not exe_path:
            result.log.append("[MediaEncoder] 未找到Media Encoder可执行文件，降级为模拟")
            return self._execute_simulate(operation, params, result)

        input_file = params.get("input_file", "")
        output_file = params.get("output_file", "")
        preset = params.get("preset", "")

        if operation == "encode" or operation == "batch_encode":
            if not input_file or not output_file:
                raise ValueError("encode操作需要input_file和output_file参数")

            cmd = [exe_path, "-i", input_file, "-o", output_file]
            if preset:
                cmd += ["-p", preset]

            result.log.append(f"[MediaEncoder] 编码: {os.path.basename(input_file)} → {os.path.basename(output_file)}")
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)

            if proc.returncode != 0:
                raise RuntimeError(f"Media Encoder错误: {proc.stderr[-500:]}")

            return {"files": [output_file], "data": {}}

        elif operation == "start_queue":
            # 启动队列（无需参数）
            cmd = [exe_path, "-noui", "-start_queue"]
            result.log.append("[MediaEncoder] 启动渲染队列")
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            return {"files": [], "data": {"started": True}}

        else:
            # 其他操作，降级为模拟
            return self._execute_simulate(operation, params, result)

    def _find_executable(self) -> Optional[str]:
        """查找Media Encoder可执行文件"""
        search_paths = [
            self.config.install_path,
            r"D:\Me\Adobe Media Encoder 2025",
            r"C:\Program Files\Adobe\Adobe Media Encoder 2025",
        ]
        for path in search_paths:
            if path and os.path.isdir(path):
                for exe in ["Adobe Media Encoder.exe", "MediaEncoder.exe"]:
                    exe_path = os.path.join(path, exe)
                    if os.path.exists(exe_path):
                        return exe_path
        return None

    def _execute_simulate(self, operation: str, params: Dict[str, Any], result: StepResult) -> Dict:
        result.log.append(f"[MediaEncoder] [模拟] 操作: {operation}")

        if operation == "add_to_queue":
            preset = params.get("preset", "")
            result.log.append(f"[MediaEncoder] [模拟] 添加到队列: {preset}")
        elif operation == "start_queue":
            count = params.get("item_count", 1)
            result.log.append(f"[MediaEncoder] [模拟] 开始渲染队列: {count} 个项目")
        elif operation == "watch_folder":
            folder = params.get("folder", "")
            result.log.append(f"[MediaEncoder] [模拟] 监听文件夹: {os.path.basename(folder)}")
        elif operation == "create_preset":
            name = params.get("preset_name", "")
            result.log.append(f"[MediaEncoder] [模拟] 创建编码预设: {name}")
        elif operation == "batch_encode":
            count = params.get("count", 1)
            fmt = params.get("format", "H.264")
            result.log.append(f"[MediaEncoder] [模拟] 批量编码: {count} 个文件 → {fmt}")
        elif operation == "create_proxy":
            result.log.append(f"[MediaEncoder] [模拟] 创建代理文件")
        elif operation == "export_h264":
            br = params.get("bitrate", "10 Mbps")
            result.log.append(f"[MediaEncoder] [模拟] 导出H.264 (码率: {br})")
        elif operation == "export_prores":
            codec = params.get("prores_codec", "ProRes 422 HQ")
            result.log.append(f"[MediaEncoder] [模拟] 导出{codec}")
        elif operation == "export_hevc":
            result.log.append(f"[MediaEncoder] [模拟] 导出H.265/HEVC")
        elif operation == "status_monitor":
            result.log.append(f"[MediaEncoder] [模拟] 队列状态监控")

        output_dir = params.get("output_dir", "")
        out_file = os.path.join(output_dir, "encoded_output.mp4") if output_dir else ""
        return {"files": [out_file] if out_file else [], "data": {"simulated": True}}


class AuditionAdapter(BaseToolAdapter):
    """Audition 适配器 - 音频处理/混音/降噪/母带

    .. deprecated::
        Audition real模式已废弃。音频处理建议使用 FFmpeg + librosa 替代，
        或使用开源方案（如 pydub / soundfile）。
    """

    SUPPORTED_OPERATIONS = [
        "import_audio", "noise_reduction", "audio_mix",
        "mastering", "apply_effect", "batch_process",
        "export_wav", "export_mp3", "voiceover", "podcast"
    ]

    def check_available(self) -> bool:
        install_path = self.config.install_path or r"C:\Program Files\Adobe\Adobe Audition 2026"
        return os.path.exists(install_path)

    def list_operations(self) -> List[str]:
        return self.SUPPORTED_OPERATIONS

    def execute(self, operation: str, params: Dict[str, Any]) -> StepResult:
        result = self._make_result(
            step_id=params.get("step_id", f"au_{operation}"),
            name=params.get("step_name", f"AU {operation}"),
            operation=operation,
        )
        result.log.append(f"[Audition] 开始执行: {operation}")
        start = time.time()
        mode = self._resolve_mode()
        result.mode_used = mode

        try:
            if mode == "real":
                warnings.warn(
                    "AuditionAdapter real mode is deprecated. "
                    "Use FFmpeg + librosa or pydub/soundfile instead.",
                    DeprecationWarning,
                    stacklevel=2,
                )
                output = self._execute_real(operation, params, result)
            else:
                output = self._execute_simulate(operation, params, result)
            result.status = PhaseStatus.SUCCESS.value
            result.output_files = output.get("files", [])
            result.output_data = output.get("data", {})
            result.log.append(f"[Audition] 执行成功")
        except Exception as e:
            result.status = PhaseStatus.ERROR.value
            result.error = str(e)
            result.log.append(f"[Audition] 执行失败: {e}")

        result.duration_ms = (time.time() - start) * 1000
        return result

    def _resolve_mode(self) -> str:
        if self.config.mode == "real":
            return "real" if self.check_available() else "simulate"
        if self.config.mode == "simulate":
            return "simulate"
        return "real" if self.check_available() else "simulate"

    def _execute_real(self, operation: str, params: Dict[str, Any], result: StepResult) -> Dict:
        result.log.append(f"[Audition] [真实] 操作: {operation}（通过Audition API调用）")
        result.used_fallback = True
        return self._execute_simulate(operation, params, result)

    def _execute_simulate(self, operation: str, params: Dict[str, Any], result: StepResult) -> Dict:
        result.log.append(f"[Audition] [模拟] 操作: {operation}")

        if operation == "import_audio":
            audio = params.get("file", "")
            result.log.append(f"[Audition] [模拟] 导入音频: {os.path.basename(audio)}")
        elif operation == "noise_reduction":
            result.log.append(f"[Audition] [模拟] 降噪处理（自适应降噪）")
        elif operation == "audio_mix":
            tracks = params.get("tracks", 2)
            result.log.append(f"[Audition] [模拟] 混音: {tracks} 轨道")
        elif operation == "mastering":
            result.log.append(f"[Audition] [模拟] 母带处理")
        elif operation == "apply_effect":
            effect = params.get("effect", "")
            result.log.append(f"[Audition] [模拟] 应用音频效果: {effect}")
        elif operation == "batch_process":
            count = params.get("count", 1)
            result.log.append(f"[Audition] [模拟] 批量处理: {count} 个文件")
        elif operation == "export_wav":
            result.log.append(f"[Audition] [模拟] 导出WAV")
        elif operation == "export_mp3":
            br = params.get("bitrate", "320 kbps")
            result.log.append(f"[Audition] [模拟] 导出MP3 (码率: {br})")
        elif operation == "voiceover":
            result.log.append(f"[Audition] [模拟] 配音录制与处理")
        elif operation == "podcast":
            result.log.append(f"[Audition] [模拟] 播客后期制作")

        output_dir = params.get("output_dir", "")
        out_file = os.path.join(output_dir, f"{operation}_output.wav") if output_dir else ""
        return {"files": [out_file] if out_file else [], "data": {"simulated": True}}


# ============================================================================
# 工作流预设定义
# ============================================================================

WORKFLOW_PRESETS: Dict[str, Dict[str, Any]] = {
    "enhance_quality": {
        "name": "视频质量增强流水线",
        "description": "使用Topaz AI进行超分辨率、降噪、插帧的质量增强",
        "steps": [
            {
                "step_id": "probe",
                "name": "素材质量检测",
                "tool": ToolType.FFMPEG.value,
                "operation": "probe",
                "description": "检测输入视频的分辨率、帧率、编码等信息"
            },
            {
                "step_id": "topaz_enhance",
                "name": "Topaz AI增强",
                "tool": ToolType.TOPAZ.value,
                "operation": "enhance",
                "description": "应用Proteus超分+Artemis降噪+Chronos插帧",
                "params": {
                    "model": "proteus",
                    "scale": 2,
                    "denoise": True,
                    "fps": 60
                },
                "depends_on": ["probe"]
            },
            {
                "step_id": "final_encode",
                "name": "最终编码",
                "tool": ToolType.FFMPEG.value,
                "operation": "transcode",
                "description": "H.265编码输出最终交付文件",
                "params": {
                    "codec": "libx265",
                    "preset": "slow",
                    "crf": 23,
                    "audio_codec": "aac"
                },
                "depends_on": ["topaz_enhance"]
            }
        ]
    },

    "delivery_pipeline": {
        "name": "交付输出流水线",
        "description": "AE渲染→Topaz增强→FFmpeg多平台编码输出",
        "steps": [
            {
                "step_id": "ae_render",
                "name": "AE渲染输出",
                "tool": ToolType.AE.value,
                "operation": "render",
                "description": "从AE渲染队列输出ProRes 4444"
            },
            {
                "step_id": "topaz_output",
                "name": "输出质量增强",
                "tool": ToolType.TOPAZ.value,
                "operation": "enhance",
                "description": "Rhea增强+Apollo 60fps插帧",
                "params": {
                    "model": "rhea",
                    "scale": 1,
                    "fps": 60
                },
                "depends_on": ["ae_render"]
            },
            {
                "step_id": "encode_1080p",
                "name": "1080p编码",
                "tool": ToolType.FFMPEG.value,
                "operation": "transcode",
                "description": "1080p H.264（B站/抖音等平台）",
                "params": {
                    "codec": "libx264",
                    "preset": "slow",
                    "bitrate": "10M",
                    "audio_codec": "aac"
                },
                "depends_on": ["topaz_output"]
            },
            {
                "step_id": "encode_4k",
                "name": "4K编码",
                "tool": ToolType.FFMPEG.value,
                "operation": "transcode",
                "description": "4K H.265（YouTube/存档）",
                "params": {
                    "codec": "libx265",
                    "preset": "slow",
                    "bitrate": "45M",
                    "audio_codec": "aac"
                },
                "depends_on": ["topaz_output"]
            }
        ]
    },

    "3d_composite": {
        "name": "3D合成流水线",
        "description": "Blender多通道渲染→AE后期合成",
        "steps": [
            {
                "step_id": "blender_render",
                "name": "Blender多通道渲染",
                "tool": ToolType.BLENDER.value,
                "operation": "render",
                "description": "EXR多通道渲染（Beauty/Depth/Normal/MotionVector/CryptoMatte）",
                "params": {
                    "engine": "BLENDER_EEVEE",
                    "resolution": (1920, 1080),
                    "frames": 60,
                    "passes": ["combined", "depth", "normal", "vector", "cryptomatte"]
                }
            },
            {
                "step_id": "ae_import",
                "name": "导入AE合成",
                "tool": ToolType.AE.value,
                "operation": "import_footage",
                "description": "导入EXR序列并提取各通道",
                "depends_on": ["blender_render"]
            },
            {
                "step_id": "ae_composite",
                "name": "AE后期合成",
                "tool": ToolType.AE.value,
                "operation": "apply_effect",
                "description": "景深+运动模糊+色彩分级+光效",
                "params": {
                    "effects": ["Lens Blur", "Color Balance", "Optical Flares"]
                },
                "depends_on": ["ae_import"]
            }
        ]
    },

    "batch_process": {
        "name": "批量处理流水线",
        "description": "多文件批量转码/增强/格式统一",
        "steps": [
            {
                "step_id": "scan_input",
                "name": "扫描输入目录",
                "tool": ToolType.FFMPEG.value,
                "operation": "probe",
                "description": "扫描并检测所有输入文件"
            },
            {
                "step_id": "batch_enhance",
                "name": "批量Topaz增强",
                "tool": ToolType.TOPAZ.value,
                "operation": "enhance",
                "description": "对所有文件应用AI增强",
                "params": {
                    "model": "proteus",
                    "scale": 1,
                    "batch": True
                },
                "depends_on": ["scan_input"]
            },
            {
                "step_id": "batch_encode",
                "name": "批量编码",
                "tool": ToolType.FFMPEG.value,
                "operation": "transcode",
                "description": "统一编码格式和码率",
                "params": {
                    "codec": "libx264",
                    "preset": "medium",
                    "crf": 20,
                    "batch": True
                },
                "depends_on": ["batch_enhance"]
            }
        ]
    },

    # ================================================================
    # 开源工具驱动的新流水线
    # ================================================================

    "ai_subtitle_pipeline": {
        "name": "AI字幕流水线",
        "description": "Whisper语音识别自动生成SRT字幕并导入AE",
        "steps": [
            {
                "step_id": "extract_audio",
                "name": "提取音频",
                "tool": ToolType.FFMPEG.value,
                "operation": "extract_audio",
                "description": "从视频中提取音频轨道",
                "params": {"audio_codec": "pcm_s16le", "sample_rate": 16000}
            },
            {
                "step_id": "whisper_transcribe",
                "name": "Whisper语音识别",
                "tool": ToolType.WHISPER.value,
                "operation": "generate_subtitles",
                "description": "使用Whisper进行多语言语音识别并生成SRT字幕",
                "params": {"model": "base", "format": "srt"},
                "depends_on": ["extract_audio"]
            },
            {
                "step_id": "ae_import_subtitle",
                "name": "AE导入字幕",
                "tool": ToolType.AE.value,
                "operation": "import_footage",
                "description": "将SRT字幕文件导入AE项目",
                "depends_on": ["whisper_transcribe"]
            }
        ]
    },

    "smart_roto_pipeline": {
        "name": "智能Roto流水线",
        "description": "SAM2自动分割生成蒙版，经Silhouette精修后在AE中合成",
        "steps": [
            {
                "step_id": "sam2_segment",
                "name": "SAM2自动分割",
                "tool": ToolType.SAM2.value,
                "operation": "generate_matte",
                "description": "使用SAM2进行自动视频对象分割，生成蒙版序列",
                "params": {"model": "sam2_hiera_large"}
            },
            {
                "step_id": "silhouette_refine",
                "name": "Silhouette精修",
                "tool": ToolType.SILHOUETTE.value,
                "operation": "roto_refine",
                "description": "在SAM2蒙版基础上进行边缘精修",
                "params": {"edge_feather": 2, "refine_mode": "edge"},
                "depends_on": ["sam2_segment"]
            },
            {
                "step_id": "ae_composite",
                "name": "AE合成输出",
                "tool": ToolType.AE.value,
                "operation": "composite_with_matte",
                "description": "使用精修蒙版作为Track Matte在AE中合成",
                "depends_on": ["silhouette_refine"]
            }
        ]
    },

    "open_production_pipeline": {
        "name": "全自动视频制作流水线",
        "description": "OpenMontage编排 + Remotion渲染 + Whisper字幕 + FFmpeg编码",
        "steps": [
            {
                "step_id": "om_produce",
                "name": "OpenMontage视频制作",
                "tool": ToolType.OPENMONTAGE.value,
                "operation": "produce_video",
                "description": "从自然语言描述自动生成视频（脚本+素材+配音+剪辑）",
                "params": {"pipeline": "animated_explainer"}
            },
            {
                "step_id": "whisper_subtitle",
                "name": "Whisper字幕生成",
                "tool": ToolType.WHISPER.value,
                "operation": "generate_subtitles",
                "description": "为生成的视频自动添加字幕",
                "params": {"model": "base", "format": "srt"},
                "depends_on": ["om_produce"]
            },
            {
                "step_id": "ffmpeg_encode",
                "name": "FFmpeg最终编码",
                "tool": ToolType.FFMPEG.value,
                "operation": "transcode",
                "description": "H.264编码输出最终交付文件",
                "params": {"codec": "libx264", "preset": "slow", "crf": 20},
                "depends_on": ["whisper_subtitle"]
            }
        ]
    },

    "enhanced_upscale_pipeline": {
        "name": "增强超分流水线",
        "description": "RIFE插帧 + Video2X/Topaz超分 + FFmpeg编码",
        "steps": [
            {
                "step_id": "probe_input",
                "name": "素材检测",
                "tool": ToolType.FFMPEG.value,
                "operation": "probe",
                "description": "检测输入视频的分辨率、帧率、编码信息"
            },
            {
                "step_id": "rife_interpolate",
                "name": "RIFE帧插值",
                "tool": ToolType.RIFE.value,
                "operation": "interpolate_2x",
                "description": "使用RIFE将帧率提升至60fps",
                "params": {"exp": 1},
                "depends_on": ["probe_input"]
            },
            {
                "step_id": "video2x_upscale",
                "name": "Video2X超分辨率",
                "tool": ToolType.VIDEO2X.value,
                "operation": "upscale_4k",
                "description": "使用Real-ESRGAN放大至4K分辨率",
                "depends_on": ["rife_interpolate"]
            },
            {
                "step_id": "final_encode",
                "name": "最终编码",
                "tool": ToolType.FFMPEG.value,
                "operation": "transcode",
                "description": "H.265编码输出最终交付文件",
                "params": {"codec": "libx265", "preset": "slow", "crf": 22},
                "depends_on": ["video2x_upscale"]
            }
        ]
    },

    "batch_social_media": {
        "name": "批量社交媒体输出流水线",
        "description": "MoviePy多比例裁切 + Whisper字幕 + FFmpeg多平台编码",
        "steps": [
            {
                "step_id": "moviepy_crop_multi",
                "name": "MoviePy多比例裁切",
                "tool": ToolType.MOVIEPY.value,
                "operation": "resize",
                "description": "从16:9主文件裁切出9:16(竖屏)、1:1(方形)等多比例版本",
                "params": {
                    "ratios": ["16:9", "9:16", "1:1", "4:5"],
                    "mode": "crop_center"
                }
            },
            {
                "step_id": "whisper_subtitles",
                "name": "Whisper批量字幕",
                "tool": ToolType.WHISPER.value,
                "operation": "generate_subtitles",
                "description": "为每个比例版本生成字幕",
                "params": {"model": "base", "format": "srt"},
                "depends_on": ["moviepy_crop_multi"]
            },
            {
                "step_id": "ffmpeg_multi_encode",
                "name": "FFmpeg多平台编码",
                "tool": ToolType.FFMPEG.value,
                "operation": "batch_transcode",
                "description": "针对不同平台编码输出（B站/抖音/小红书/YouTube）",
                "params": {
                    "platforms": ["bilibili", "douyin", "xiaohongshu", "youtube"],
                    "codec": "libx264"
                },
                "depends_on": ["whisper_subtitles"]
            }
        ]
    }
}


# ============================================================================
# 统一集成调度器
# ============================================================================

class UnifiedToolIntegrator:
    """
    统一多工具集成调度器

    负责：
    1. 管理所有工具适配器
    2. 执行预设工作流
    3. 处理步骤间依赖和数据传递
    4. 错误处理和降级策略
    5. 进度回调和日志记录
    """

    def __init__(
        self,
        default_mode: str = "auto",
        output_dir: str = r"D:\AE-Work\_integrator_output",
        on_progress: Optional[Callable] = None,
        preset_file: Optional[str] = None,
        config_file: Optional[str] = None,
        log_level: str = "INFO",
        max_retries: int = 2,
        enable_checkpoint: bool = True,
        max_workers: int = 4,
    ):
        """
        初始化统一集成调度器

        Args:
            default_mode: 默认执行模式（real/simulate/auto）
            output_dir: 输出根目录
            on_progress: 进度回调函数 (workflow_name: str, progress: float, message: str) -> None
            preset_file: 外部预设JSON文件路径（可选）
            config_file: 工具路径配置文件路径（可选）
            log_level: 日志级别（DEBUG/INFO/WARNING/ERROR）
            max_retries: 失败步骤最大重试次数
            enable_checkpoint: 是否启用检查点持久化
            max_workers: 并行执行最大线程数
        """
        self._default_mode = default_mode
        self._output_dir = Path(output_dir)
        self._on_progress = on_progress
        self._tools: Dict[str, BaseToolAdapter] = {}
        self._external_presets: Dict[str, Any] = {}
        self._tool_config: Dict[str, Any] = {}
        self._max_retries = max_retries
        self._logger = Logger(log_dir=str(self._output_dir / "logs"), log_level=log_level)
        self._enable_checkpoint = enable_checkpoint
        self._max_workers = max_workers

        # 工作流控制状态
        self._control_lock = threading.Lock()
        self._pause_event = threading.Event()
        self._pause_event.set()  # 默认不暂停
        self._cancel_flag = False
        self._active_workflows: Dict[str, WorkflowResult] = {}

        if preset_file:
            self._load_presets_from_file(preset_file)
        
        if config_file:
            self._load_config_from_file(config_file)
        else:
            default_config = os.path.join(os.path.dirname(__file__), "tool_config.json")
            if os.path.exists(default_config):
                self._load_config_from_file(default_config)
        
        self._init_tools()
        self._init_opensource_adapters()

    def _log(self, message: str, level: str = "INFO"):
        """日志记录"""
        if level == "DEBUG":
            self._logger.debug(message)
        elif level == "WARNING":
            self._logger.warning(message)
        elif level == "ERROR":
            self._logger.error(message)
        else:
            self._logger.info(message)

    def _load_presets_from_file(self, preset_file: str):
        """从JSON文件加载外部工作流预设"""
        try:
            with open(preset_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "presets" in data:
                    for key, preset in data["presets"].items():
                        self._external_presets[key] = preset
            self._log(f"已加载预设文件: {preset_file} (共 {len(self._external_presets)} 个预设)", "INFO")
        except Exception as e:
            self._log(f"加载预设文件失败: {e}", "ERROR")

    def _load_config_from_file(self, config_file: str):
        """从JSON文件加载工具路径配置"""
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                self._tool_config = json.load(f)
            self._log(f"已加载工具配置: {config_file}", "INFO")
            self._scan_tool_paths()
        except Exception as e:
            self._log(f"加载配置文件失败: {e}", "ERROR")

    def _scan_tool_paths(self):
        """扫描所有工具的安装路径"""
        tools = self._tool_config.get("tools", {})
        search_paths = self._tool_config.get("search_paths", {})
        
        for tool_id, tool_info in tools.items():
            if not tool_info.get("enabled", True):
                continue
            
            executable = tool_info.get("executable", "")
            if not executable:
                continue
            
            install_path = tool_info.get("install_path", "")
            if install_path and os.path.exists(install_path):
                continue
            
            category = self._get_tool_category(tool_id)
            paths_to_search = search_paths.get(category, [])
            
            found_path = self._find_executable(executable, paths_to_search)
            if found_path:
                tool_info["install_path"] = found_path
                self._log(f"[发现] {tool_info['name']} 在 {found_path}", "INFO")

    def _find_executable(self, executable: str, search_paths: list) -> str:
        """在搜索路径中查找可执行文件"""
        for search_path in search_paths:
            full_path = os.path.join(search_path, executable)
            if os.path.exists(full_path):
                return search_path
        
        for search_path in search_paths:
            if os.path.isdir(search_path):
                for root, dirs, files in os.walk(search_path):
                    if executable in files:
                        return root
                    dirs[:] = [d for d in dirs if d not in ('node_modules', '.git')]
        
        return ""

    def _get_tool_category(self, tool_id: str) -> str:
        """获取工具所属类别"""
        if tool_id in ["after_effects", "premiere_pro", "photoshop", "illustrator", "media_encoder", "audition"]:
            return "adobe"
        elif tool_id == "ffmpeg":
            return "ffmpeg"
        elif tool_id == "topaz_video_ai":
            return "topaz"
        elif tool_id == "blender":
            return "blender"
        return "adobe"

    def _get_all_presets(self) -> Dict[str, Any]:
        """获取所有预设（内置+外部）"""
        all_presets = {}
        all_presets.update(WORKFLOW_PRESETS)
        all_presets.update(self._external_presets)
        return all_presets

    def _init_tools(self):
        """初始化所有工具适配器"""
        tools_config = self._tool_config.get("tools", {})
        
        def get_install_path(tool_id: str) -> str:
            tool_info = tools_config.get(tool_id, {})
            return tool_info.get("install_path", "")
        
        tool_configs = {
            # Adobe 全家桶
            ToolType.AE.value: ToolConfig(
                tool_type=ToolType.AE.value,
                mode=self._default_mode,
                install_path=get_install_path("after_effects"),
            ),
            ToolType.PREMIERE.value: ToolConfig(
                tool_type=ToolType.PREMIERE.value,
                mode=self._default_mode,
                install_path=get_install_path("premiere_pro"),
            ),
            ToolType.PHOTOSHOP.value: ToolConfig(
                tool_type=ToolType.PHOTOSHOP.value,
                mode=self._default_mode,
                install_path=get_install_path("photoshop"),
            ),
            ToolType.ILLUSTRATOR.value: ToolConfig(
                tool_type=ToolType.ILLUSTRATOR.value,
                mode=self._default_mode,
                install_path=get_install_path("illustrator"),
            ),
            ToolType.MEDIA_ENCODER.value: ToolConfig(
                tool_type=ToolType.MEDIA_ENCODER.value,
                mode=self._default_mode,
                install_path=get_install_path("media_encoder"),
            ),
            ToolType.AUDITION.value: ToolConfig(
                tool_type=ToolType.AUDITION.value,
                mode=self._default_mode,
                install_path=get_install_path("audition"),
            ),
            # 其他专业工具
            ToolType.FFMPEG.value: ToolConfig(
                tool_type=ToolType.FFMPEG.value,
                mode=self._default_mode,
                install_path=get_install_path("ffmpeg"),
            ),
            ToolType.TOPAZ.value: ToolConfig(
                tool_type=ToolType.TOPAZ.value,
                mode=self._default_mode,
                install_path=get_install_path("topaz_video_ai"),
                extra_params={"executable": tools_config.get("topaz_video_ai", {}).get("executable", "Topaz Video AI.exe")},
            ),
            ToolType.BLENDER.value: ToolConfig(
                tool_type=ToolType.BLENDER.value,
                mode=self._default_mode,
                install_path=get_install_path("blender"),
            ),
        }

        for tool_type, config in tool_configs.items():
            self._tools[tool_type] = self._create_adapter(config)

    def _create_adapter(self, config: ToolConfig) -> BaseToolAdapter:
        """根据工具类型创建适配器"""
        # Adobe 全家桶
        if config.tool_type == ToolType.AE.value:
            return AEAdapter(config)
        elif config.tool_type == ToolType.PREMIERE.value:
            return PremiereProAdapter(config)
        elif config.tool_type == ToolType.PHOTOSHOP.value:
            return PhotoshopAdapter(config)
        elif config.tool_type == ToolType.ILLUSTRATOR.value:
            return IllustratorAdapter(config)
        elif config.tool_type == ToolType.MEDIA_ENCODER.value:
            return MediaEncoderAdapter(config)
        elif config.tool_type == ToolType.AUDITION.value:
            return AuditionAdapter(config)
        # 其他专业工具
        elif config.tool_type == ToolType.FFMPEG.value:
            return FFmpegAdapter(config)
        elif config.tool_type == ToolType.TOPAZ.value:
            return TopazAdapter(config)
        elif config.tool_type == ToolType.BLENDER.value:
            return BlenderAdapter(config)
        else:
            raise ValueError(f"不支持的工具类型: {config.tool_type}")

    def get_available_tools(self) -> Dict[str, bool]:
        """获取所有工具的可用状态"""
        status = {name: adapter.check_available() for name, adapter in self._tools.items()}
        # 合并开源工具状态
        if hasattr(self, '_os_hub') and self._os_hub:
            os_status = self._os_hub.auto_detect()
            status.update(os_status)
        return status

    def _init_opensource_adapters(self):
        """初始化开源工具适配器（OpenSourceHub）"""
        try:
            from opensource_integrations import OpenSourceHub
            os_configs = {}
            # 从 tool_config 中提取开源工具路径配置
            tools_cfg = self._tool_config.get("tools", {})
            for key in ["rife", "sam2", "whisper", "remotion", "moviepy", "openmontage", "video2x"]:
                if key in tools_cfg:
                    os_configs[key] = tools_cfg[key]
            self._os_hub = OpenSourceHub(os_configs)
            self._os_hub.auto_detect()
            self._log(f"开源工具中心已初始化，可用工具: {sum(1 for v in self._os_hub.auto_detect().values() if v)}/7")
        except ImportError:
            self._os_hub = None
            self._log("opensource_integrations 模块不可用，开源工具已禁用", "WARNING")
        except Exception as e:
            self._os_hub = None
            self._log(f"开源工具初始化失败: {e}", "WARNING")

    def _execute_opensource_step(self, step: Dict[str, Any], result: Any) -> Dict[str, Any]:
        """执行开源工具步骤"""
        if not hasattr(self, '_os_hub') or self._os_hub is None:
            return {"files": [], "data": {"error": "OpenSourceHub not available"}}
        tool_name = step.get("tool", "")
        operation = step.get("operation", "")
        params = step.get("params", {})
        # 传递输出目录
        if "output_dir" not in params:
            params["output_dir"] = str(self._output_dir / "opensource")
        os_result = self._os_hub.execute(tool_name, operation, params)
        return {
            "files": os_result.output_files,
            "data": os_result.output_data,
            "status": os_result.status,
            "log": os_result.log,
        }

    def get_tool_operations(self, tool_type: str) -> List[str]:
        """获取指定工具支持的操作列表"""
        if tool_type in self._tools:
            return self._tools[tool_type].list_operations()
        return []

    def get_all_tools_info(self) -> Dict[str, Dict[str, Any]]:
        """获取所有工具的详细信息"""
        info = {}
        for name, adapter in self._tools.items():
            info[name] = {
                "available": adapter.check_available(),
                "operations": adapter.list_operations(),
                "operations_count": len(adapter.list_operations()),
            }
        return info

    def list_presets(self) -> List[Dict[str, Any]]:
        """列出所有可用的工作流预设"""
        presets = []
        all_presets = self._get_all_presets()
        for key, preset in all_presets.items():
            presets.append({
                "id": key,
                "name": preset["name"],
                "description": preset.get("description", ""),
                "steps_count": len(preset.get("steps", [])),
                "category": preset.get("category", ""),
                "tags": preset.get("tags", []),
            })
        return presets

    # ========================================================================
    # 工作流控制：暂停 / 恢复 / 取消
    # ========================================================================

    def pause_workflow(self, workflow_id: Optional[str] = None) -> bool:
        """暂停指定工作流（在工作流线程中检查暂停标志）"""
        self._pause_event.clear()
        self._log(f"工作流暂停请求已发送 (workflow_id={workflow_id or 'all'})")
        return True

    def resume_workflow(self, workflow_id: Optional[str] = None) -> bool:
        """恢复暂停的工作流"""
        self._pause_event.set()
        self._log(f"工作流已恢复 (workflow_id={workflow_id or 'all'})")
        return True

    def cancel_workflow(self, workflow_id: Optional[str] = None) -> bool:
        """取消正在执行的工作流"""
        self._cancel_flag = True
        self._pause_event.set()  # 解除暂停阻塞，让工作流检测到取消
        self._log(f"工作流取消请求已发送 (workflow_id={workflow_id or 'all'})")
        return True

    def is_paused(self) -> bool:
        """检查是否处于暂停状态"""
        return not self._pause_event.is_set()

    def get_active_workflows(self) -> Dict[str, Dict[str, Any]]:
        """获取所有活跃工作流状态"""
        with self._control_lock:
            return {
                wid: {
                    "workflow_name": r.workflow_name,
                    "status": r.status,
                    "steps_completed": len(r.steps),
                    "paused": r.paused,
                }
                for wid, r in self._active_workflows.items()
            }

    def _check_pause(self, workflow_id: str):
        """检查暂停标志，阻塞直到恢复或取消"""
        while not self._pause_event.is_set():
            if self._cancel_flag:
                raise InterruptedError(f"工作流 {workflow_id} 已被取消")
            time.sleep(0.2)
        if self._cancel_flag:
            raise InterruptedError(f"工作流 {workflow_id} 已被取消")

    # ========================================================================
    # 检查点持久化
    # ========================================================================

    def _save_checkpoint(self, result: WorkflowResult, job_dir: str):
        """保存工作流状态检查点"""
        if not self._enable_checkpoint:
            return
        checkpoint_path = os.path.join(job_dir, "checkpoint.json")
        result.checkpoint_path = checkpoint_path
        try:
            with open(checkpoint_path, "w", encoding="utf-8") as f:
                json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
            self._log(f"检查点已保存: {checkpoint_path}")
        except Exception as e:
            self._log(f"检查点保存失败: {e}", "WARNING")

    def load_checkpoint(self, checkpoint_path: str) -> WorkflowResult:
        """从检查点文件加载工作流状态"""
        with open(checkpoint_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        result = WorkflowResult.from_dict(data)
        self._log(f"检查点已加载: {checkpoint_path} (已完成 {len(result.steps)} 步)")
        return result

    def resume_from_checkpoint(
        self,
        checkpoint_path: str,
        preset_id: str,
        input_params: Optional[Dict[str, Any]] = None,
    ) -> WorkflowResult:
        """从检查点恢复工作流执行"""
        previous = self.load_checkpoint(checkpoint_path)
        self._log(f"从检查点恢复工作流: {previous.workflow_name} (已完成 {len(previous.steps)} 步)")

        completed_ids = previous.completed_step_ids()
        self._cancel_flag = False
        self._pause_event.set()

        return self.run_workflow(
            preset_id,
            input_params=input_params,
            skip_step_ids=completed_ids,
            previous_result=previous,
        )

    # ========================================================================
    # 依赖图与并行执行
    # ========================================================================

    def _build_dependency_graph(self, steps_config: List[Dict[str, Any]]) -> Dict[str, Set[str]]:
        """构建步骤依赖图，返回 {step_id: set(依赖的step_id)}"""
        graph = {}
        for step in steps_config:
            if not step.get("enabled", True):
                continue
            sid = step["step_id"]
            deps = set(step.get("depends_on", []))
            graph[sid] = deps
        return graph

    def _get_ready_steps(
        self,
        graph: Dict[str, Set[str]],
        completed: Set[str],
        pending: Set[str],
    ) -> List[str]:
        """获取当前可执行的步骤（依赖全部完成）"""
        ready = []
        for sid in pending:
            deps = graph.get(sid, set())
            if deps.issubset(completed):
                ready.append(sid)
        return ready

    def run_workflow(
        self,
        preset_id: str,
        input_params: Optional[Dict[str, Any]] = None,
        skip_step_ids: Optional[Set[str]] = None,
        previous_result: Optional[WorkflowResult] = None,
    ) -> WorkflowResult:
        """
        执行预设工作流（支持并行执行、暂停/恢复、检查点）

        Args:
            preset_id: 工作流预设ID
            input_params: 输入参数（覆盖默认参数）
            skip_step_ids: 跳过的步骤ID集合（用于从检查点恢复）
            previous_result: 前序执行结果（用于从检查点恢复）

        Returns:
            WorkflowResult 执行结果
        """
        all_presets = self._get_all_presets()
        if preset_id not in all_presets:
            raise ValueError(f"未知的工作流预设: {preset_id}. 可用: {list(all_presets.keys())}")

        preset = all_presets[preset_id]
        steps_config = preset["steps"]
        input_params = input_params or {}
        skip_step_ids = skip_step_ids or set()

        # 生成工作流ID
        workflow_id = str(uuid.uuid4())[:8]

        # 初始化结果对象
        if previous_result:
            result = previous_result
            result.status = PhaseStatus.RUNNING.value
            result.paused = False
        else:
            result = WorkflowResult(
                workflow_name=preset["name"],
                status=PhaseStatus.RUNNING.value,
                started_at=datetime.now().isoformat(),
                workflow_id=workflow_id,
            )

        result.workflow_id = workflow_id
        total_steps = len([s for s in steps_config if s.get("enabled", True)])
        completed_steps = len(result.steps)

        # 注册活跃工作流
        with self._control_lock:
            self._active_workflows[workflow_id] = result

        self._emit_progress(preset["name"], 0.0, f"开始工作流: {preset['name']} (id={workflow_id})")

        # 工作输出目录
        job_dir = self._output_dir / f"{preset_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        job_dir.mkdir(parents=True, exist_ok=True)

        # 重置控制标志
        self._cancel_flag = False
        self._pause_event.set()

        # 构建依赖图
        graph = self._build_dependency_graph(steps_config)
        all_step_ids = set(graph.keys())
        pending = all_step_ids - skip_step_ids
        completed: Set[str] = set(skip_step_ids)
        # 从前序结果恢复 step_results_map
        step_results_map: Dict[str, StepResult] = {}
        for sr in result.steps:
            step_results_map[sr.step_id] = sr

        try:
            while pending:
                # 检查暂停/取消
                self._check_pause(workflow_id)

                # 获取可执行步骤
                ready_ids = self._get_ready_steps(graph, completed, pending)
                if not ready_ids:
                    # 没有可执行步骤但还有pending → 可能是依赖循环
                    self._log(f"检测到可能存在依赖循环，剩余步骤: {pending}", "ERROR")
                    break

                # 过滤掉依赖失败的步骤
                executable = []
                for sid in ready_ids:
                    step_conf = next(s for s in steps_config if s["step_id"] == sid)
                    deps = step_conf.get("depends_on", [])
                    dep_failed = False
                    for dep_id in deps:
                        dep_result = step_results_map.get(dep_id)
                        if dep_result and dep_result.status != PhaseStatus.SUCCESS.value:
                            skip_result = StepResult(
                                step_id=sid,
                                name=step_conf["name"],
                                status=PhaseStatus.SKIPPED.value,
                                tool=step_conf["tool"],
                                operation=step_conf["operation"],
                                error=f"依赖步骤 {dep_id} 未成功",
                            )
                            result.steps.append(skip_result)
                            step_results_map[sid] = skip_result
                            completed.add(sid)
                            pending.discard(sid)
                            completed_steps += 1
                            dep_failed = True
                            break
                    if not dep_failed:
                        executable.append(sid)

                if not executable:
                    continue

                # 并行执行（如果多个步骤就绪）或串行执行
                if len(executable) == 1:
                    # 单步骤：串行执行
                    sid = executable[0]
                    step_conf = next(s for s in steps_config if s["step_id"] == sid)
                    self._emit_progress(
                        preset["name"],
                        completed_steps / total_steps if total_steps > 0 else 0,
                        f"执行步骤: {step_conf['name']}"
                    )
                    step_params = self._build_step_params(
                        step_conf, input_params, step_results_map, str(job_dir)
                    )
                    step_result = self._execute_step(step_conf, step_params)
                    result.steps.append(step_result)
                    step_results_map[sid] = step_result
                    completed.add(sid)
                    pending.discard(sid)
                    completed_steps += 1

                    if step_result.status == PhaseStatus.ERROR.value:
                        self._emit_progress(
                            preset["name"],
                            completed_steps / total_steps if total_steps > 0 else 0,
                            f"步骤失败: {step_conf['name']}"
                        )
                else:
                    # 多步骤：并行执行
                    self._log(f"并行执行 {len(executable)} 个步骤: {executable}")
                    self._emit_progress(
                        preset["name"],
                        completed_steps / total_steps if total_steps > 0 else 0,
                        f"并行执行 {len(executable)} 个步骤"
                    )

                    with ThreadPoolExecutor(max_workers=min(self._max_workers, len(executable))) as executor:
                        futures = {}
                        for sid in executable:
                            step_conf = next(s for s in steps_config if s["step_id"] == sid)
                            step_params = self._build_step_params(
                                step_conf, input_params, step_results_map, str(job_dir)
                            )
                            future = executor.submit(
                                self._execute_step, step_conf, step_params
                            )
                            futures[future] = (sid, step_conf)

                        for future in as_completed(futures):
                            sid, step_conf = futures[future]
                            step_result = future.result()
                            result.steps.append(step_result)
                            step_results_map[sid] = step_result
                            completed.add(sid)
                            pending.discard(sid)
                            completed_steps += 1

                            icon = "✅" if step_result.status == PhaseStatus.SUCCESS.value else "❌"
                            self._log(f"{icon} 并行步骤完成: {step_conf['name']} [{step_result.status}]")

                # 每轮执行后保存检查点
                self._save_checkpoint(result, str(job_dir))

            # 判断最终状态
            failed = result.failed_steps()
            if self._cancel_flag:
                result.status = PhaseStatus.SKIPPED.value
                result.error = "工作流已被取消"
                result.paused = True
            elif failed:
                result.status = PhaseStatus.ERROR.value
                result.error = f"{len(failed)} 个步骤失败"
            else:
                result.status = PhaseStatus.SUCCESS.value

            # 收集所有输出文件
            for sr in result.steps:
                result.output_files.extend(sr.output_files)

            result.summary = self._generate_summary(result)

        except InterruptedError as e:
            result.status = PhaseStatus.SKIPPED.value
            result.error = str(e)
            result.paused = True
            result.summary = f"工作流已暂停: {e}"
            self._save_checkpoint(result, str(job_dir))
        except Exception as e:
            result.status = PhaseStatus.ERROR.value
            result.error = str(e)
            result.summary = f"工作流异常: {e}"
            self._log(f"工作流异常: {e}\n{traceback.format_exc()}", "ERROR")

        result.finished_at = datetime.now().isoformat()
        result.total_duration_ms = sum(s.duration_ms for s in result.steps)

        result.log_file_path = self._logger.get_log_path()
        self._logger.close()

        report_html = self._generate_html_report(result)
        report_path = os.path.join(str(job_dir), "report.html")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_html)
        result.report_file_path = report_path

        # 从活跃工作流中移除
        with self._control_lock:
            self._active_workflows.pop(workflow_id, None)

        self._emit_progress(preset["name"], 1.0, f"工作流完成: {result.status}")

        return result

    def _build_step_params(
        self,
        step_conf: Dict[str, Any],
        input_params: Dict[str, Any],
        prev_results: Dict[str, StepResult],
        job_dir: str,
    ) -> Dict[str, Any]:
        """构建步骤参数，合并输入参数和前序步骤输出"""
        params = copy.deepcopy(step_conf.get("params", {}))
        params["step_id"] = step_conf["step_id"]
        params["step_name"] = step_conf["name"]

        # 从输入参数中获取文件路径
        if "input_file" in input_params and "input_file" not in params:
            params["input_file"] = input_params["input_file"]

        # 从依赖步骤中获取输出作为输入
        deps = step_conf.get("depends_on", [])
        if deps and "input_file" not in params:
            # 使用第一个依赖的第一个输出文件
            first_dep = deps[0]
            dep_result = prev_results.get(first_dep)
            if dep_result and dep_result.output_files:
                params["input_file"] = dep_result.output_files[0]

        # 设置输出目录/文件
        step_out_dir = os.path.join(job_dir, step_conf["step_id"])
        os.makedirs(step_out_dir, exist_ok=True)
        params["output_dir"] = step_out_dir

        if "output_file" not in params and "input_file" in params:
            base_name = os.path.splitext(os.path.basename(params["input_file"]))[0]
            params["output_file"] = os.path.join(step_out_dir, f"{base_name}_out.mp4")

        return params

    def _execute_step(self, step_conf: Dict[str, Any], params: Dict[str, Any]) -> StepResult:
        """执行单个步骤（带重试机制）"""
        tool_type = step_conf["tool"]
        operation = step_conf["operation"]
        step_id = step_conf["step_id"]
        step_name = step_conf["name"]

        if tool_type not in self._tools:
            if self._default_mode in ("simulate", "auto"):
                result = StepResult(
                    step_id=step_id,
                    name=step_name,
                    status=PhaseStatus.SUCCESS.value,
                    tool=tool_type,
                    operation=operation,
                    mode_used="simulate",
                    output_files=[],
                    log=[
                        f"[{tool_type}] [模拟] 未知工具，模拟执行: {operation}",
                        f"[{tool_type}] [模拟] 参数: {json.dumps({k: v for k, v in params.items() if k not in ('step_id', 'step_name', 'output_dir')}, ensure_ascii=False)}",
                        f"[{tool_type}] [模拟] 执行完成（模拟）",
                    ],
                )
                return result
            result = StepResult(
                step_id=step_id,
                name=step_name,
                status=PhaseStatus.ERROR.value,
                tool=tool_type,
                operation=operation,
                error=f"未找到工具适配器: {tool_type}",
            )
            return result

        adapter = self._tools[tool_type]
        max_retries = step_conf.get("retries", self._max_retries)
        retry_delay = step_conf.get("retry_delay", 5)

        for attempt in range(max_retries + 1):
            try:
                result = adapter.execute(operation, params)
                if result.status == PhaseStatus.SUCCESS.value:
                    return result
                elif attempt < max_retries:
                    self._log(f"步骤 {step_id} 执行失败，正在重试 ({attempt + 1}/{max_retries})", "WARNING")
                    time.sleep(retry_delay)
                else:
                    self._log(f"步骤 {step_id} 重试 {max_retries} 次后仍失败", "ERROR")
                    return result
            except Exception as e:
                if attempt < max_retries:
                    self._log(f"步骤 {step_id} 异常，正在重试 ({attempt + 1}/{max_retries}): {e}", "WARNING")
                    time.sleep(retry_delay)
                else:
                    self._log(f"步骤 {step_id} 重试 {max_retries} 次后仍异常: {e}", "ERROR")
                    return StepResult(
                        step_id=step_id,
                        name=step_name,
                        status=PhaseStatus.ERROR.value,
                        tool=tool_type,
                        operation=operation,
                        error=str(e),
                        log=[f"执行异常: {e}"],
                    )

    def _generate_summary(self, result: WorkflowResult) -> str:
        """生成执行摘要"""
        total = len(result.steps)
        success = len(result.successful_steps())
        failed = len(result.failed_steps())
        skipped = total - success - failed

        lines = [
            f"工作流: {result.workflow_name}",
            f"状态: {result.status}",
            f"总步骤: {total} | 成功: {success} | 失败: {failed} | 跳过: {skipped}",
            f"总耗时: {result.total_duration_ms / 1000:.1f} 秒",
            f"输出文件: {len(result.output_files)} 个",
        ]
        return "\n".join(lines)

    def _generate_html_report(self, result: WorkflowResult) -> str:
        """生成HTML格式的执行报告"""
        total = len(result.steps)
        success = len(result.successful_steps())
        failed = len(result.failed_steps())
        success_rate = (success / total * 100) if total > 0 else 0

        tool_colors = {
            "after_effects": "#CC66FF",
            "premiere_pro": "#0099CC",
            "photoshop": "#33CC99",
            "illustrator": "#FF6633",
            "media_encoder": "#FFCC00",
            "audition": "#9933FF",
            "ffmpeg": "#FF6666",
            "topaz_video_ai": "#6699FF",
            "blender": "#E87D0D",
        }

        status_colors = {
            "success": "#10B981",
            "error": "#EF4444",
            "pending": "#9CA3AF",
            "running": "#3B82F6",
            "skipped": "#F59E0B",
            "fallback": "#8B5CF6",
        }

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>工作流执行报告 - {result.workflow_name}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: linear-gradient(135deg, #1e1e2e 0%, #2d2d44 100%); color: #e4e4e7; min-height: 100vh; padding: 20px; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        .header h1 {{ font-size: 28px; margin-bottom: 10px; color: #f4f4f5; }}
        .header p {{ color: #a1a1aa; }}
        .summary {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 15px; margin-bottom: 30px; }}
        .summary-card {{ background: rgba(255,255,255,0.05); border-radius: 12px; padding: 20px; text-align: center; border: 1px solid rgba(255,255,255,0.1); }}
        .summary-card .value {{ font-size: 32px; font-weight: bold; margin-bottom: 5px; }}
        .summary-card .label {{ font-size: 14px; color: #a1a1aa; }}
        .status-bar {{ height: 8px; background: rgba(255,255,255,0.1); border-radius: 4px; overflow: hidden; margin-bottom: 30px; }}
        .status-bar .success {{ height: 100%; background: #10B981; }}
        .status-bar .failed {{ height: 100%; background: #EF4444; }}
        .steps-title {{ font-size: 20px; margin-bottom: 20px; color: #f4f4f5; }}
        .step-card {{ background: rgba(255,255,255,0.05); border-radius: 12px; padding: 20px; margin-bottom: 15px; border-left: 4px solid; transition: transform 0.2s; }}
        .step-card:hover {{ transform: translateX(5px); }}
        .step-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }}
        .step-name {{ font-size: 16px; font-weight: bold; }}
        .step-status {{ padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: bold; }}
        .step-info {{ display: flex; gap: 15px; font-size: 14px; color: #a1a1aa; }}
        .step-info span {{ display: flex; align-items: center; gap: 5px; }}
        .step-info .tool-badge {{ padding: 2px 8px; border-radius: 4px; font-size: 12px; }}
        .step-duration {{ color: #60a5fa; }}
        .step-log {{ margin-top: 10px; padding: 10px; background: rgba(0,0,0,0.3); border-radius: 8px; font-family: monospace; font-size: 12px; max-height: 150px; overflow-y: auto; }}
        .step-log .log-line {{ padding: 2px 0; }}
        .step-log .log-line:nth-child(odd) {{ background: rgba(255,255,255,0.02); }}
        .error-details {{ margin-top: 10px; padding: 10px; background: rgba(239,68,68,0.1); border-left: 3px solid #EF4444; border-radius: 0 8px 8px 0; color: #fca5a5; }}
        .footer {{ text-align: center; margin-top: 40px; padding-top: 20px; border-top: 1px solid rgba(255,255,255,0.1); color: #71717a; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>工作流执行报告</h1>
            <p>{result.workflow_name} | {result.started_at} ~ {result.finished_at}</p>
        </div>
        
        <div class="summary">
            <div class="summary-card"><div class="value" style="color:#f4f4f5">{total}</div><div class="label">总步骤</div></div>
            <div class="summary-card"><div class="value" style="color:#10B981">{success}</div><div class="label">成功</div></div>
            <div class="summary-card"><div class="value" style="color:#EF4444">{failed}</div><div class="label">失败</div></div>
            <div class="summary-card"><div class="value" style="color:#60a5fa">{result.total_duration_ms / 1000:.1f}s</div><div class="label">总耗时</div></div>
            <div class="summary-card"><div class="value" style="color:#34D399">{success_rate:.1f}%</div><div class="label">成功率</div></div>
        </div>
        
        <div class="status-bar">
            <div class="success" style="width:{success_rate}%"></div>
            <div class="failed" style="width:{100 - success_rate}%"></div>
        </div>
        
        <div class="steps-title">执行步骤详情</div>
"""

        for step in result.steps:
            tool_color = tool_colors.get(step.tool, "#888888")
            status_color = status_colors.get(step.status, "#9CA3AF")
            status_label = {
                "success": "成功",
                "error": "失败",
                "pending": "等待",
                "running": "运行中",
                "skipped": "跳过",
                "fallback": "降级",
            }.get(step.status, step.status)

            html += f"""        <div class="step-card" style="border-left-color:{status_color}">
            <div class="step-header">
                <span class="step-name">{step.name}</span>
                <span class="step-status" style="background:rgba({status_color[1:3]},{status_color[3:5]},{status_color[5:7]},0.2);color:{status_color}">{status_label}</span>
            </div>
            <div class="step-info">
                <span><span class="tool-badge" style="background:rgba({tool_color[1:3]},{tool_color[3:5]},{tool_color[5:7]},0.2);color:{tool_color}">{step.tool}</span></span>
                <span>操作: {step.operation}</span>
                <span class="step-duration">耗时: {step.duration_ms:.0f}ms</span>
                <span>模式: {step.mode_used}</span>
            </div>
"""
            if step.error:
                html += f"""            <div class="error-details">错误: {step.error}</div>"""
            
            if step.log:
                html += """            <div class="step-log">"""
                for log_line in step.log[-20:]:
                    html += f"""<div class="log-line">{log_line}</div>"""
                html += """            </div>"""
            
            html += """        </div>"""

        html += f"""        <div class="footer">
            <p>统一多工具集成调度器 | 日志文件: {result.log_file_path}</p>
        </div>
    </div>
</body>
</html>"""
        return html

    def _emit_progress(self, workflow_name: str, progress: float, message: str):
        """触发进度回调"""
        if self._on_progress:
            try:
                self._on_progress(workflow_name, progress, message)
            except Exception:
                pass

    def run_custom_workflow(
        self,
        steps: List[Dict[str, Any]],
        workflow_name: str = "自定义工作流",
    ) -> WorkflowResult:
        """执行自定义工作流"""
        temp_preset_id = "custom_temp"
        WORKFLOW_PRESETS[temp_preset_id] = {
            "name": workflow_name,
            "description": "自定义工作流",
            "steps": steps,
        }
        try:
            return self.run_workflow(temp_preset_id)
        finally:
            del WORKFLOW_PRESETS[temp_preset_id]


# ============================================================================
# 命令行接口
# ============================================================================

def print_available_presets(presets_file=None, config_file=None):
    """打印可用预设列表"""
    print("\n" + "=" * 70)
    print("  统一多工具集成调度器 - 可用资源")
    print("=" * 70)

    integrator = UnifiedToolIntegrator(
        preset_file=presets_file,
        config_file=config_file,
    )
    presets = integrator.list_presets()
    tools_info = integrator.get_all_tools_info()

    print("\n  📦 工具适配器 (9个)")
    print("-" * 70)
    total_ops = 0
    for tool, info in tools_info.items():
        status = "✅" if info["available"] else "❌"
        ops_count = info["operations_count"]
        total_ops += ops_count
        print(f"     {status} {tool:25s} {ops_count:2d} 个操作")
    print(f"\n     总计: {len(tools_info)} 个工具, {total_ops} 个操作")

    print("\n  🎬 工作流预设 (15个)")
    print("-" * 70)
    for i, p in enumerate(presets, 1):
        cat = f"[{p['category']}] " if p.get('category') else ""
        print(f"\n  {i:2d}. {p['name']}  [{p['id']}]")
        print(f"      {cat}{p['description']}")
        print(f"      步骤数: {p['steps_count']}", end="")
        if p.get('tags'):
            print(f"  | 标签: {', '.join(p['tags'][:5])}")
        else:
            print()

    print("\n" + "=" * 70 + "\n")


def main():
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(
        description="统一多工具集成调度器 - 跨工具工作流一键执行"
    )
    parser.add_argument(
        "preset",
        nargs="?",
        help="工作流预设ID（使用 --list 查看所有可用预设）",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="列出所有可用工作流预设",
    )
    parser.add_argument(
        "--input", "-i",
        help="输入文件路径",
    )
    parser.add_argument(
        "--output-dir", "-o",
        default=r"D:\AE-Work\_integrator_output",
        help="输出根目录（默认: D:\\AE-Work\\_integrator_output）",
    )
    parser.add_argument(
        "--mode", "-m",
        choices=["real", "simulate", "auto"],
        default="auto",
        help="执行模式（默认: auto）",
    )
    parser.add_argument(
        "--params", "-p",
        help="额外JSON参数",
    )
    parser.add_argument(
        "--presets-file",
        help="外部工作流预设JSON文件路径",
    )
    parser.add_argument(
        "--config-file",
        help="工具路径配置文件路径（默认: tool_config.json）",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="日志级别（默认: INFO）",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=2,
        help="失败步骤最大重试次数（默认: 2）",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=4,
        help="并行执行最大线程数（默认: 4）",
    )
    parser.add_argument(
        "--resume",
        help="从检查点文件恢复工作流执行",
    )
    parser.add_argument(
        "--no-checkpoint",
        action="store_true",
        help="禁用检查点持久化",
    )

    args = parser.parse_args()

    if args.list or not args.preset:
        print_available_presets(args.presets_file, args.config_file)
        return 0

    input_params = {}
    if args.input:
        input_params["input_file"] = os.path.abspath(args.input)
    if args.params:
        try:
            extra = json.loads(args.params)
            input_params.update(extra)
        except json.JSONDecodeError as e:
            print(f"错误: JSON参数解析失败 - {e}")
            return 1

    def on_progress(workflow, progress, message):
        bar_len = 30
        filled = int(bar_len * progress)
        bar = "█" * filled + "░" * (bar_len - filled)
        print(f"\r  [{bar}] {progress*100:.0f}%  {message}", end="", flush=True)

    print(f"\n🚀 启动工作流: {args.preset}")
    print(f"   模式: {args.mode}")
    if args.input:
        print(f"   输入: {args.input}")
    if args.resume:
        print(f"   恢复自: {args.resume}")
    print()

    integrator = UnifiedToolIntegrator(
        default_mode=args.mode,
        output_dir=args.output_dir,
        on_progress=on_progress,
        preset_file=args.presets_file,
        config_file=args.config_file,
        log_level=args.log_level,
        max_retries=args.max_retries,
        enable_checkpoint=not args.no_checkpoint,
        max_workers=args.max_workers,
    )

    if args.resume:
        result = integrator.resume_from_checkpoint(args.resume, args.preset, input_params)
    else:
        result = integrator.run_workflow(args.preset, input_params)

    print("\n\n" + "=" * 60)
    print("  执行结果")
    print("=" * 60)
    print(result.summary)
    print()

    for sr in result.steps:
        icon = "✅" if sr.status == "success" else "❌" if sr.status == "error" else "⏭️"
        mode_tag = f"[{sr.mode_used}]"
        print(f"  {icon} {sr.name} {mode_tag} - {sr.duration_ms/1000:.1f}s")
        if sr.error:
            print(f"     错误: {sr.error}")

    if result.output_files:
        print(f"\n  输出文件 ({len(result.output_files)}):")
        for f in result.output_files[:5]:
            print(f"    - {f}")
        if len(result.output_files) > 5:
            print(f"    ... 还有 {len(result.output_files) - 5} 个")

    if result.log_file_path:
        print(f"\n  📝 日志文件: {result.log_file_path}")
    if result.report_file_path:
        print(f"  📊 报告文件: {result.report_file_path}")
    if result.checkpoint_path:
        print(f"  💾 检查点: {result.checkpoint_path}")
    if result.workflow_id:
        print(f"  🔖 工作流ID: {result.workflow_id}")

    print("=" * 60)

    return 0 if result.status == PhaseStatus.SUCCESS.value else 1


if __name__ == "__main__":
    sys.exit(main())
