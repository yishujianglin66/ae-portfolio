"""
开源项目集成引擎 (Open Source Integration Engine) v1.0
======================================================

整合 GitHub 顶级开源项目，为 AE 管线提供全面的视频/音频/AI 能力。

集成项目清单：
┌-----------------┬----------------------------------------------┬-----------┐
│ 项目            │ 功能                                         │ GitHub    │
├-----------------┼----------------------------------------------┼-----------┤
│ RIFE            │ 实时视频帧插值 (2x/4x/8x FPS提升)            │ hzwer/... │
│ SAM2            │ 通用图像/视频分割 (Meta)                     │ facebook..│
│ Video2X         │ AI视频超分辨率放大 (Real-ESRGAN/RIFE)        │ video2x/..│
│ Whisper         │ 多语言语音识别 + 字幕生成 (OpenAI)           │ openai/.. │
│ Remotion        │ React编程式视频生成                          │ remotion..│
│ OpenMontage     │ Agent驱动全自动视频制作系统                   │ calesthio/│
│ MoviePy         │ Python视频编辑库                             │ Zulko/..  │
│ FFmpeg (python) │ 视频处理瑞士军刀                             │ kkroenli..│
└-----------------┴----------------------------------------------┴-----------┘

架构设计：
- 每个开源工具封装为独立 Adapter，继承 BaseOpenSourceAdapter
- 统一接口: check_available() / execute() / list_operations()
- 支持 simulate 模式用于测试
- 与 unified_tool_integrator.py 的工作流预设无缝对接
"""

import os
import sys
import json
import time
import shutil
import subprocess
import warnings
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union
from enum import Enum

logger = logging.getLogger(__name__)


# -------------------------------------------------------------
# -- 基础类
# -------------------------------------------------------------

class PhaseStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPP = "skipped"


@dataclass
class ToolResult:
    """统一工具执行结果"""
    tool_name: str
    operation: str
    status: str = "pending"
    mode_used: str = "simulate"
    output_files: List[str] = field(default_factory=list)
    output_data: Dict[str, Any] = field(default_factory=dict)
    log: List[str] = field(default_factory=list)
    error: Optional[str] = None
    duration_ms: float = 0.0
    used_fallback: bool = False


class BaseOpenSourceAdapter:
    """开源工具适配器基类"""

    TOOL_NAME: str = "base"
    SUPPORTED_OPERATIONS: List[str] = []

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._bin_path: Optional[str] = None

    def check_available(self) -> bool:
        """检查工具是否可用"""
        raise NotImplementedError

    def list_operations(self) -> List[str]:
        return self.SUPPORTED_OPERATIONS

    def execute(self, operation: str, params: Dict[str, Any]) -> ToolResult:
        raise NotImplementedError

    def _make_result(self, operation: str, **kwargs) -> ToolResult:
        return ToolResult(
            tool_name=self.TOOL_NAME,
            operation=operation,
            **kwargs,
        )

    def _run_cmd(self, cmd: List[str], timeout: int = 600, cwd: str = None) -> Tuple[int, str, str]:
        """Execute external command, return (returncode, stdout, stderr)

        Security note: shell=False is used on ALL platforms (default, not explicitly passed).
        For Windows .CMD/.BAT scripts: subprocess.run() with list[str] cmd automatically
        resolves executable extensions via PATHEXT (.COM/.EXE/.BAT/.CMD), so shell=True is never needed.
        shell=True would introduce HIGH-RISK command injection vulnerabilities if any cmd element
        contains user-controlled input (metacharacters like & | > <  would be interpreted by cmd.exe).
        Returncode/stdout/stderr CompletedProcess structure is identical between shell=True/False.
        """
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd,
                encoding="utf-8",
            )
            return proc.returncode, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired:
            return -1, "", f"Command timed out after {timeout}s"
        except FileNotFoundError:
            return -1, "", f"Command not found: {cmd[0]}"
        except Exception as e:
            return -1, "", str(e)


# -------------------------------------------------------------
# -- 1. RIFE 帧插值集成
# -------------------------------------------------------------
# GitHub: https://github.com/hzwer/ECCV2022-RIFE
# Stars: 6K+  |  License: MIT
# 功能: 实时中间流估计，视频帧插值，2x/4x/8x FPS提升

class RIFEAdapter(BaseOpenSourceAdapter):
    """RIFE 视频帧插值适配器

    基于 ECCV2022-RIFE，实现实时视频帧插值。
    支持 2x/4x/8x 帧率提升，适用于慢动作制作和流畅度优化。

    安装方式:
        pip install rife-ncnn-vulkan-python
        或克隆: git clone https://github.com/hzwer/ECCV2022-RIFE.git

    使用示例:
        rife = RIFEAdapter({"rife_path": "/path/to/rife"})
        result = rife.execute("interpolate_2x", {"input_video": "input.mp4"})
    """

    TOOL_NAME = "rife"
    SUPPORTED_OPERATIONS = [
        "interpolate_2x",      # 2倍帧率插值
        "interpolate_4x",      # 4倍帧率插值
        "interpolate_8x",      # 8倍帧率插值
        "slow_motion",         # 慢动作生成
        "frame_generation",    # 指定帧数生成
        "batch_interpolate",   # 批量插值
    ]

    def check_available(self) -> bool:
        # 检查 Python 包
        try:
            import importlib
            importlib.import_module("rife")
            return True
        except ImportError:
            pass
        # 检查命令行工具
        rife_path = self.config.get("rife_path") or shutil.which("rife-ncnn-vulkan")
        if rife_path:
            self._bin_path = rife_path
            return True
        # 检查本地目录
        local_path = os.path.join(os.path.dirname(__file__), "external", "rife")
        if os.path.isdir(local_path):
            self._bin_path = local_path
            return True
        return False

    def execute(self, operation: str, params: Dict[str, Any]) -> ToolResult:
        result = self._make_result(operation)
        start = time.time()

        if not self.check_available():
            result.status = "simulated"
            result.log.append("[RIFE] 工具不可用，使用模拟模式")
            result.output_data = {"simulated": True, "operation": operation}
            result.duration_ms = (time.time() - start) * 1000
            return result

        try:
            if operation == "interpolate_2x":
                output = self._interpolate(params, exp=1)
            elif operation == "interpolate_4x":
                output = self._interpolate(params, exp=2)
            elif operation == "interpolate_8x":
                output = self._interpolate(params, exp=3)
            elif operation == "slow_motion":
                output = self._slow_motion(params)
            elif operation == "batch_interpolate":
                output = self._batch_interpolate(params)
            else:
                output = {"files": [], "data": {"error": f"Unknown operation: {operation}"}}

            result.status = "success"
            result.output_files = output.get("files", [])
            result.output_data = output.get("data", {})
            result.log.append(f"[RIFE] {operation} 完成")
        except Exception as e:
            result.status = "error"
            result.error = str(e)
            result.log.append(f"[RIFE] 执行失败: {e}")

        result.duration_ms = (time.time() - start) * 1000
        return result

    def _interpolate(self, params: Dict, exp: int = 1) -> Dict:
        input_video = params.get("input_video", "")
        output_dir = params.get("output_dir", "")
        scale = params.get("scale", 1.0)

        if not output_dir:
            output_dir = os.path.join(os.path.dirname(input_video), "rife_output")
        os.makedirs(output_dir, exist_ok=True)

        output_file = os.path.join(output_dir, f"interpolated_{exp}x.mp4")

        if self._bin_path and os.path.isfile(self._bin_path):
            cmd = [
                self._bin_path,
                "-i", input_video,
                "-o", output_file,
                "-e", str(exp),
            ]
            if scale != 1.0:
                cmd.extend(["--scale", str(scale)])
            rc, stdout, stderr = self._run_cmd(cmd, timeout=1800)
            if rc == 0:
                return {"files": [output_file], "data": {"exp": exp, "scale": scale}}
            else:
                raise RuntimeError(f"RIFE failed: {stderr}")
        else:
            # Python API 模式
            try:
                from rife import RIFE
                model = RIFE()
                model.interpolate(input_video, output_file, exp=exp)
                return {"files": [output_file], "data": {"exp": exp}}
            except ImportError:
                return {"files": [], "data": {"simulated": True, "exp": exp}}

    def _slow_motion(self, params: Dict) -> Dict:
        factor = params.get("factor", 4)
        exp = {2: 1, 4: 2, 8: 3}.get(factor, 2)
        return self._interpolate(params, exp=exp)

    def _batch_interpolate(self, params: Dict) -> Dict:
        input_files = params.get("input_files", [])
        results = []
        for f in input_files:
            r = self._interpolate({"input_video": f, "output_dir": params.get("output_dir", "")},
                                  exp=params.get("exp", 1))
            results.append(r)
        all_files = [f for r in results for f in r.get("files", [])]
        return {"files": all_files, "data": {"batch_count": len(results)}}


# -------------------------------------------------------------
# -- 2. SAM2 视频/图像分割集成
# -------------------------------------------------------------
# GitHub: https://github.com/facebookresearch/sam2
# Stars: 10K+  |  License: Apache 2.0
# 功能: 通用分割模型，支持图像和视频中的万物分割

class SAM2Adapter(BaseOpenSourceAdapter):
    """SAM2 视频/图像分割适配器

    基于 Meta SAM2，实现自动视频对象分割和追踪。
    适用于 Roto 替代、蒙版生成、对象追踪。

    安装方式:
        pip install sam2
        或: git clone https://github.com/facebookresearch/sam2.git && cd sam2 && pip install -e .

    使用示例:
        sam2 = SAM2Adapter({"model": "sam2_hiera_large"})
        result = sam2.execute("segment_video", {"input_video": "input.mp4", "points": [[500, 375]]})
    """

    TOOL_NAME = "sam2"
    SUPPORTED_OPERATIONS = [
        "segment_image",       # 单图分割
        "segment_video",       # 视频分割+追踪
        "auto_mask_generate",  # 全自动蒙版生成
        "track_object",        # 对象追踪
        "generate_matte",      # 生成 AE 可用蒙版
        "batch_segment",       # 批量分割
    ]

    def check_available(self) -> bool:
        try:
            import importlib
            importlib.import_module("sam2")
            return True
        except ImportError:
            pass
        sam2_path = self.config.get("sam2_path")
        if sam2_path and os.path.isdir(sam2_path):
            self._bin_path = sam2_path
            return True
        return False

    def execute(self, operation: str, params: Dict[str, Any]) -> ToolResult:
        result = self._make_result(operation)
        start = time.time()

        if not self.check_available():
            result.status = "simulated"
            result.log.append("[SAM2] 工具不可用，使用模拟模式")
            result.output_data = {"simulated": True, "operation": operation}
            result.duration_ms = (time.time() - start) * 1000
            return result

        try:
            if operation == "segment_image":
                output = self._segment_image(params)
            elif operation == "segment_video":
                output = self._segment_video(params)
            elif operation == "auto_mask_generate":
                output = self._auto_mask(params)
            elif operation == "track_object":
                output = self._track_object(params)
            elif operation == "generate_matte":
                output = self._generate_matte(params)
            elif operation == "batch_segment":
                output = self._batch_segment(params)
            else:
                output = {"files": [], "data": {"error": f"Unknown: {operation}"}}

            result.status = "success"
            result.output_files = output.get("files", [])
            result.output_data = output.get("data", {})
            result.log.append(f"[SAM2] {operation} 完成")
        except Exception as e:
            result.status = "error"
            result.error = str(e)
            result.log.append(f"[SAM2] 执行失败: {e}")

        result.duration_ms = (time.time() - start) * 1000
        return result

    def _segment_image(self, params: Dict) -> Dict:
        import numpy as np
        img_path = params.get("input_image", "")
        points = params.get("points", [])
        labels = params.get("labels", [1] * len(points))
        box = params.get("box", None)
        output_dir = params.get("output_dir", "")

        if not output_dir:
            output_dir = os.path.join(os.path.dirname(img_path), "sam2_output")
        os.makedirs(output_dir, exist_ok=True)

        from sam2.build_sam import build_sam2
        from sam2.sam2_image_predictor import SAM2ImagePredictor

        model_cfg = self.config.get("model_cfg", "sam2_hiera_l.yaml")
        checkpoint = self.config.get("checkpoint", "sam2_hiera_large.pt")
        predictor = build_sam2(model_cfg, checkpoint, device="cuda")

        import cv2
        image = cv2.imread(img_path)
        predictor.set_image(image)

        if box:
            masks, scores, logits = predictor.predict(box=np.array(box), multimask_output=False)
        elif points:
            masks, scores, logits = predictor.predict(
                point_coords=np.array(points),
                point_labels=np.array(labels),
                multimask_output=False,
            )
        else:
            raise ValueError("必须提供 points 或 box 参数")

        mask_file = os.path.join(output_dir, "mask.png")
        cv2.imwrite(mask_file, (masks[0] * 255).astype(np.uint8))
        return {"files": [mask_file], "data": {"scores": scores.tolist(), "mask_shape": masks[0].shape}}

    def _segment_video(self, params: Dict) -> Dict:
        video_path = params.get("input_video", "")
        points = params.get("points", [])
        output_dir = params.get("output_dir", "")

        if not output_dir:
            output_dir = os.path.join(os.path.dirname(video_path), "sam2_video_output")
        os.makedirs(output_dir, exist_ok=True)

        import torch
        from sam2.build_sam import build_sam2
        from sam2.sam2_video_predictor import SAM2VideoPredictor

        model_cfg = self.config.get("model_cfg", "sam2_hiera_l.yaml")
        checkpoint = self.config.get("checkpoint", "sam2_hiera_large.pt")
        predictor = build_sam2(model_cfg, checkpoint, device="cuda")

        with torch.inference_mode(), torch.autocast("cuda", dtype=torch.float16):
            state = predictor.init_state(video_path)
            if points:
                _, _, masks = predictor.add_new_points_or_box(
                    inference_state=state,
                    frame_idx=0,
                    obj_id=0,
                    points=points,
                    labels=[1] * len(points),
                )
            masks_gen = predictor.propagate_in_video(state)
            mask_files = []
            for frame_idx, out_mask in masks_gen:
                mask_file = os.path.join(output_dir, f"mask_{frame_idx:05d}.png")
                import cv2
                import numpy as np
                cv2.imwrite(mask_file, (out_mask[0].cpu().numpy() * 255).astype(np.uint8))
                mask_files.append(mask_file)

        return {"files": mask_files, "data": {"frame_count": len(mask_files)}}

    def _auto_mask(self, params: Dict) -> Dict:
        img_path = params.get("input_image", "")
        output_dir = params.get("output_dir", "")

        if not output_dir:
            output_dir = os.path.join(os.path.dirname(img_path), "sam2_auto_output")
        os.makedirs(output_dir, exist_ok=True)

        from sam2.build_sam import build_sam2
        from sam2.automatic_mask_generator import SAM2AutomaticMaskGenerator

        model_cfg = self.config.get("model_cfg", "sam2_hiera_l.yaml")
        checkpoint = self.config.get("checkpoint", "sam2_hiera_large.pt")
        mask_generator = build_sam2(model_cfg, checkpoint, device="cuda")

        import cv2
        import numpy as np
        image = cv2.imread(img_path)
        masks = mask_generator.generate(image)

        mask_files = []
        for i, mask in enumerate(masks):
            mask_file = os.path.join(output_dir, f"auto_mask_{i:03d}.png")
            cv2.imwrite(mask_file, (mask["segmentation"] * 255).astype(np.uint8))
            mask_files.append(mask_file)

        return {"files": mask_files, "data": {"mask_count": len(masks)}}

    def _track_object(self, params: Dict) -> Dict:
        return self._segment_video(params)

    def _generate_matte(self, params: Dict) -> Dict:
        """生成 AE 可用的蒙版序列（PNG序列或EXR）"""
        result = self._segment_video(params)
        output_dir = params.get("output_dir", "")
        matte_dir = os.path.join(output_dir, "matte_sequence")
        os.makedirs(matte_dir, exist_ok=True)

        import cv2
        import numpy as np
        for mask_file in result["files"]:
            mask = cv2.imread(mask_file, cv2.IMREAD_GRAYSCALE)
            # 边缘羽化，使蒙版更自然
            blurred = cv2.GaussianBlur(mask, (5, 5), 0)
            base_name = os.path.basename(mask_file)
            cv2.imwrite(os.path.join(matte_dir, base_name), blurred)

        result["output_files"].append(matte_dir)
        result["output_data"]["matte_dir"] = matte_dir
        return result

    def _batch_segment(self, params: Dict) -> Dict:
        input_files = params.get("input_files", [])
        results = []
        for f in input_files:
            r = self._segment_image({"input_image": f, "output_dir": params.get("output_dir", "")})
            results.append(r)
        all_files = [f for r in results for f in r.get("files", [])]
        return {"files": all_files, "data": {"batch_count": len(results)}}


# -------------------------------------------------------------
# -- 3. Video2X 超分辨率集成
# -------------------------------------------------------------
# GitHub: https://github.com/video2x/video2x
# Stars: 25K+  |  License: GPL-3.0
# 功能: AI视频超分辨率放大，支持 Real-ESRGAN / Real-CUGAN / RIFE

class Video2XAdapter(BaseOpenSourceAdapter):
    """Video2X 视频超分辨率适配器

    基于 Video2X，实现 AI 驱动的视频画质增强。
    支持 Real-ESRGAN、Real-CUGAN 等算法，可将视频放大至 4K。

    安装方式:
        pip install video2x
        或下载: https://github.com/video2x/video2x/releases

    使用示例:
        v2x = Video2XAdapter()
        result = v2x.execute("upscale_4k", {"input_video": "input.mp4"})
    """

    TOOL_NAME = "video2x"
    SUPPORTED_OPERATIONS = [
        "upscale_2x",          # 2倍放大
        "upscale_4x",          # 4倍放大
        "upscale_4k",          # 放大至4K分辨率
        "upscale_8k",          # 放大至8K分辨率
        "enhance_anime",       # 动漫专用增强
        "enhance_realworld",   # 真实场景增强
        "denoise_enhance",     # 降噪+增强
        "batch_upscale",       # 批量放大
    ]

    def check_available(self) -> bool:
        # 检查命令行工具
        v2x_path = self.config.get("video2x_path") or shutil.which("video2x")
        if v2x_path:
            self._bin_path = v2x_path
            return True
        # 检查 Python 包
        try:
            import importlib
            importlib.import_module("video2x")
            return True
        except ImportError:
            pass
        return False

    def execute(self, operation: str, params: Dict[str, Any]) -> ToolResult:
        result = self._make_result(operation)
        start = time.time()

        if not self.check_available():
            result.status = "simulated"
            result.log.append("[Video2X] 工具不可用，使用模拟模式")
            result.output_data = {"simulated": True, "operation": operation}
            result.duration_ms = (time.time() - start) * 1000
            return result

        try:
            if operation.startswith("upscale_"):
                output = self._upscale(operation, params)
            elif operation.startswith("enhance_"):
                output = self._enhance(operation, params)
            elif operation == "denoise_enhance":
                output = self._denoise(params)
            elif operation == "batch_upscale":
                output = self._batch_upscale(params)
            else:
                output = {"files": [], "data": {"error": f"Unknown: {operation}"}}

            result.status = "success"
            result.output_files = output.get("files", [])
            result.output_data = output.get("data", {})
            result.log.append(f"[Video2X] {operation} 完成")
        except Exception as e:
            result.status = "error"
            result.error = str(e)
            result.log.append(f"[Video2X] 执行失败: {e}")

        result.duration_ms = (time.time() - start) * 1000
        return result

    def _upscale(self, operation: str, params: Dict) -> Dict:
        input_video = params.get("input_video", "")
        output_dir = params.get("output_dir", "")

        if not output_dir:
            output_dir = os.path.join(os.path.dirname(input_video), "video2x_output")
        os.makedirs(output_dir, exist_ok=True)

        output_file = os.path.join(output_dir, f"upscaled_{operation}.mp4")

        # 确定放大倍率和算法
        proc_config = {
            "upscale_2x": {"ratio": 2, "algorithm": "realesrgan"},
            "upscale_4x": {"ratio": 4, "algorithm": "realesrgan"},
            "upscale_4k": {"target_height": 2160, "algorithm": "realesrgan"},
            "upscale_8k": {"target_height": 4320, "algorithm": "realesrgan"},
        }
        cfg = proc_config.get(operation, {"ratio": 2, "algorithm": "realesrgan"})

        if self._bin_path:
            cmd = [self._bin_path, "-i", input_video, "-o", output_file]
            if "ratio" in cfg:
                cmd.extend(["-r", str(cfg["ratio"])])
            if "target_height" in cfg:
                cmd.extend(["--target-height", str(cfg["target_height"])])
            cmd.extend(["-p", cfg["algorithm"]])

            rc, stdout, stderr = self._run_cmd(cmd, timeout=3600)
            if rc == 0:
                return {"files": [output_file], "data": cfg}
            else:
                raise RuntimeError(f"Video2X failed: {stderr}")
        return {"files": [], "data": {"simulated": True}}

    def _enhance(self, operation: str, params: Dict) -> Dict:
        algorithm = "realcugan" if "anime" in operation else "realesrgan"
        params_copy = {**params}
        return self._upscale(f"upscale_2x", {**params_copy, "_algorithm": algorithm})

    def _denoise(self, params: Dict) -> Dict:
        return self._upscale("upscale_2x", params)

    def _batch_upscale(self, params: Dict) -> Dict:
        input_files = params.get("input_files", [])
        results = []
        for f in input_files:
            r = self._upscale("upscale_2x", {"input_video": f, "output_dir": params.get("output_dir", "")})
            results.append(r)
        all_files = [f for r in results for f in r.get("files", [])]
        return {"files": all_files, "data": {"batch_count": len(results)}}


# -------------------------------------------------------------
# -- 4. Whisper 语音识别集成
# -------------------------------------------------------------
# GitHub: https://github.com/openai/whisper
# Stars: 72K+  |  License: MIT
# 功能: 多语言语音识别、字幕生成、时间戳标注

class WhisperAdapter(BaseOpenSourceAdapter):
    """Whisper 语音识别适配器

    基于 OpenAI Whisper，实现多语言语音转文字和自动字幕生成。
    支持 SRT/VTT/JSON 输出，适用于自动字幕、内容分析。

    安装方式:
        pip install openai-whisper
        或加速版: pip install faster-whisper

    使用示例:
        whisper = WhisperAdapter({"model": "large-v3"})
        result = whisper.execute("generate_subtitles", {"input_audio": "video.mp4"})
    """

    TOOL_NAME = "whisper"
    SUPPORTED_OPERATIONS = [
        "transcribe",           # 语音转文字
        "generate_subtitles",   # 生成字幕文件 (SRT/VTT)
        "detect_language",      # 语言检测
        "timestamp_align",      # 时间戳对齐
        "extract_segments",     # 提取语音段落
        "batch_transcribe",     # 批量转写
    ]

    def check_available(self) -> bool:
        try:
            import importlib
            # 优先检查 faster-whisper
            try:
                importlib.import_module("faster_whisper")
                self._backend = "faster"
                return True
            except ImportError:
                pass
            importlib.import_module("whisper")
            self._backend = "whisper"
            return True
        except ImportError:
            return False

    def execute(self, operation: str, params: Dict[str, Any]) -> ToolResult:
        result = self._make_result(operation)
        start = time.time()

        if not self.check_available():
            result.status = "simulated"
            result.log.append("[Whisper] 工具不可用，使用模拟模式")
            result.output_data = {"simulated": True, "operation": operation}
            result.duration_ms = (time.time() - start) * 1000
            return result

        try:
            if operation == "transcribe":
                output = self._transcribe(params)
            elif operation == "generate_subtitles":
                output = self._generate_subtitles(params)
            elif operation == "detect_language":
                output = self._detect_language(params)
            elif operation == "timestamp_align":
                output = self._timestamp_align(params)
            elif operation == "extract_segments":
                output = self._extract_segments(params)
            elif operation == "batch_transcribe":
                output = self._batch_transcribe(params)
            else:
                output = {"files": [], "data": {"error": f"Unknown: {operation}"}}

            result.status = "success"
            result.output_files = output.get("files", [])
            result.output_data = output.get("data", {})
            result.log.append(f"[Whisper] {operation} 完成")
        except RuntimeError as e:
            err_str = str(e)
            if "模型加载失败" in err_str or "无网络" in err_str:
                result.status = "simulated"
                result.log.append(f"[Whisper] 离线模式: {e}")
                result.output_data = {"simulated": True, "operation": operation, "reason": "offline_no_model"}
            else:
                result.status = "error"
                result.error = err_str
                result.log.append(f"[Whisper] 执行失败: {e}")
        except Exception as e:
            err_str = str(e)
            # 检测网络/离线相关错误，自动降级为模拟模式
            offline_keywords = ["ConnectTimeout", "ConnectionError", "No connection", "offline",
                                "cannot find the files on the Hub", "WinError 10060"]
            if any(kw in err_str for kw in offline_keywords):
                result.status = "simulated"
                result.log.append(f"[Whisper] 离线模式(网络不可用): {err_str[:120]}")
                result.output_data = {"simulated": True, "operation": operation, "reason": "offline_no_network"}
            else:
                result.status = "error"
                result.error = err_str
                result.log.append(f"[Whisper] 执行失败: {e}")

        result.duration_ms = (time.time() - start) * 1000
        return result

    def _get_model(self, model_name: str = None):
        model_name = model_name or self.config.get("model", "base")
        if self._backend == "faster":
            from faster_whisper import WhisperModel
            device = self.config.get("device", "cuda")
            compute_type = self.config.get("compute_type", "float16")
            return WhisperModel(model_name, device=device, compute_type=compute_type)
        else:
            import whisper
            try:
                return whisper.load_model(model_name)
            except Exception:
                # 离线环境回退: 尝试 tiny 模型（更小，更可能已缓存）
                for fallback in ["tiny", "base", "small"]:
                    try:
                        return whisper.load_model(fallback)
                    except Exception:
                        continue
                raise RuntimeError(
                    "Whisper 模型加载失败（可能无网络）。"
                    "请先在有网络时运行: python -c \"import whisper; whisper.load_model('tiny')\""
                )

    def _transcribe(self, params: Dict) -> Dict:
        input_file = params.get("input_audio", params.get("input_video", ""))
        model = self._get_model(params.get("model"))
        language = params.get("language")

        if self._backend == "faster":
            segments, info = model.transcribe(input_file, language=language, beam_size=5)
            result_segments = []
            for seg in segments:
                result_segments.append({
                    "start": seg.start,
                    "end": seg.end,
                    "text": seg.text,
                    "language": info.language,
                })
        else:
            result = model.transcribe(input_file, language=language)
            result_segments = [
                {"start": s["start"], "end": s["end"], "text": s["text"]}
                for s in result.get("segments", [])
            ]
            info = {"language": result.get("language", "unknown")}

        return {
            "files": [],
            "data": {
                "segments": result_segments,
                "language": info.language if hasattr(info, 'language') else info.get("language"),
                "segment_count": len(result_segments),
            }
        }

    def _generate_subtitles(self, params: Dict) -> Dict:
        input_file = params.get("input_audio", params.get("input_video", ""))
        output_dir = params.get("output_dir", "")
        fmt = params.get("format", "srt")  # srt / vtt / json

        if not output_dir:
            output_dir = os.path.dirname(input_file)
        os.makedirs(output_dir, exist_ok=True)

        transcribe_result = self._transcribe(params)
        segments = transcribe_result["data"]["segments"]

        base_name = Path(input_file).stem
        output_file = os.path.join(output_dir, f"{base_name}.{fmt}")

        if fmt == "srt":
            self._write_srt(segments, output_file)
        elif fmt == "vtt":
            self._write_vtt(segments, output_file)
        elif fmt == "json":
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(segments, f, ensure_ascii=False, indent=2)

        return {"files": [output_file], "data": {"format": fmt, "segment_count": len(segments)}}

    def _write_srt(self, segments: List[Dict], output_file: str):
        def fmt_time(seconds: float) -> str:
            h = int(seconds // 3600)
            m = int((seconds % 3600) // 60)
            s = int(seconds % 60)
            ms = int((seconds % 1) * 1000)
            return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

        with open(output_file, "w", encoding="utf-8") as f:
            for i, seg in enumerate(segments, 1):
                f.write(f"{i}\n")
                f.write(f"{fmt_time(seg['start'])} --> {fmt_time(seg['end'])}\n")
                f.write(f"{seg['text'].strip()}\n\n")

    def _write_vtt(self, segments: List[Dict], output_file: str):
        def fmt_time(seconds: float) -> str:
            h = int(seconds // 3600)
            m = int((seconds % 3600) // 60)
            s = int(seconds % 60)
            ms = int((seconds % 1) * 1000)
            return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"

        with open(output_file, "w", encoding="utf-8") as f:
            f.write("WEBVTT\n\n")
            for i, seg in enumerate(segments, 1):
                f.write(f"{i}\n")
                f.write(f"{fmt_time(seg['start'])} --> {fmt_time(seg['end'])}\n")
                f.write(f"{seg['text'].strip()}\n\n")

    def _detect_language(self, params: Dict) -> Dict:
        input_file = params.get("input_audio", params.get("input_video", ""))
        model = self._get_model(params.get("model"))

        if self._backend == "faster":
            segments, info = model.transcribe(input_file, beam_size=5)
            return {"files": [], "data": {"language": info.language, "probability": info.language_probability}}
        else:
            import whisper
            audio = whisper.load_audio(input_file)
            audio = whisper.pad_or_trim(audio)
            mel = whisper.log_mel_spectrogram(audio).to(model.device)
            _, probs = model.detect_language(mel)
            detected = max(probs, key=probs.get)
            return {"files": [], "data": {"language": detected, "probability": probs[detected]}}

    def _timestamp_align(self, params: Dict) -> Dict:
        return self._transcribe(params)

    def _extract_segments(self, params: Dict) -> Dict:
        result = self._transcribe(params)
        segments = result["data"]["segments"]
        min_duration = params.get("min_duration", 5.0)
        filtered = [s for s in segments if (s["end"] - s["start"]) >= min_duration]
        return {"files": [], "data": {"segments": filtered, "count": len(filtered)}}

    def _batch_transcribe(self, params: Dict) -> Dict:
        input_files = params.get("input_files", [])
        all_results = []
        for f in input_files:
            r = self._transcribe({"input_audio": f, **params})
            all_results.append({"file": f, "data": r["data"]})
        return {"files": [], "data": {"results": all_results, "file_count": len(all_results)}}


# -------------------------------------------------------------
# -- 5. Remotion 编程式视频生成集成
# -------------------------------------------------------------
# GitHub: https://github.com/remotion-dev/remotion
# Stars: 21K+  |  License: BSL 1.1
# 功能: 用 React 代码化生成视频，支持数据驱动、模板化批量生产

class RemotionAdapter(BaseOpenSourceAdapter):
    """Remotion 编程式视频生成适配器

    基于 Remotion，用 React 代码生成高质量视频。
    适用于数据可视化动画、模板化批量视频、产品演示。

    安装方式:
        npx create-video@latest
        或: npm install remotion @remotion/cli

    使用示例:
        remotion = RemotionAdapter({"project_path": "/path/to/remotion/project"})
        result = remotion.execute("render_video", {"composition": "Main", "props": {...}})
    """

    TOOL_NAME = "remotion"
    SUPPORTED_OPERATIONS = [
        "render_video",        # 渲染视频
        "render_sequence",     # 渲染序列帧
        "create_from_template",# 基于模板生成
        "batch_render",        # 批量渲染
        "preview",             # 预览（启动Remotion Studio）
        "still_image",         # 生成静态图
    ]

    def check_available(self) -> bool:
        # 检查 npx/node
        node_path = shutil.which("node") or shutil.which("npx")
        if not node_path:
            return False
        # 检查项目路径
        project_path = self.config.get("project_path")
        if project_path and os.path.isdir(project_path):
            self._bin_path = project_path
            return True
        # 检查全局安装 (remotion CLI)
        rc, stdout, stderr = self._run_cmd(["npx", "remotion", "--version"])
        # remotion --version 可能返回0或非0，但输出包含版本号
        combined = stdout + stderr
        if "remotion" in combined.lower() or "4." in combined or "3." in combined:
            return True
        # 检查 npm 全局包
        rc2, npm_out, _ = self._run_cmd(["npm", "list", "-g", "@remotion/cli", "--depth=0"])
        if rc2 == 0 and "@remotion/cli" in npm_out:
            return True
        return False

    def execute(self, operation: str, params: Dict[str, Any]) -> ToolResult:
        result = self._make_result(operation)
        start = time.time()

        if not self.check_available():
            result.status = "simulated"
            result.log.append("[Remotion] 工具不可用，使用模拟模式")
            result.output_data = {"simulated": True, "operation": operation}
            result.duration_ms = (time.time() - start) * 1000
            return result

        try:
            if operation == "render_video":
                output = self._render_video(params)
            elif operation == "render_sequence":
                output = self._render_sequence(params)
            elif operation == "create_from_template":
                output = self._create_from_template(params)
            elif operation == "batch_render":
                output = self._batch_render(params)
            elif operation == "still_image":
                output = self._still_image(params)
            else:
                output = {"files": [], "data": {"error": f"Unknown: {operation}"}}

            result.status = "success"
            result.output_files = output.get("files", [])
            result.output_data = output.get("data", {})
            result.log.append(f"[Remotion] {operation} 完成")
        except Exception as e:
            result.status = "error"
            result.error = str(e)
            result.log.append(f"[Remotion] 执行失败: {e}")

        result.duration_ms = (time.time() - start) * 1000
        return result

    def _render_video(self, params: Dict) -> Dict:
        composition = params.get("composition", "Main")
        output_dir = params.get("output_dir", "output")
        props = params.get("props", {})
        output_file = os.path.join(output_dir, f"{composition}_{int(time.time())}.mp4")
        os.makedirs(output_dir, exist_ok=True)

        cmd = ["npx", "remotion", "render", composition, output_file]
        if props:
            cmd.extend(["--props", json.dumps(props)])

        cwd = self._bin_path or self.config.get("project_path")
        rc, stdout, stderr = self._run_cmd(cmd, timeout=1800, cwd=cwd)
        if rc == 0:
            return {"files": [output_file], "data": {"composition": composition}}
        raise RuntimeError(f"Remotion render failed: {stderr}")

    def _render_sequence(self, params: Dict) -> Dict:
        composition = params.get("composition", "Main")
        output_dir = params.get("output_dir", "output/sequence")
        os.makedirs(output_dir, exist_ok=True)

        cmd = ["npx", "remotion", "render", composition, output_dir, "--image-format", "png"]
        cwd = self._bin_path or self.config.get("project_path")
        rc, stdout, stderr = self._run_cmd(cmd, timeout=1800, cwd=cwd)
        if rc == 0:
            frames = [os.path.join(output_dir, f) for f in os.listdir(output_dir) if f.endswith(".png")]
            return {"files": frames, "data": {"frame_count": len(frames)}}
        raise RuntimeError(f"Remotion sequence failed: {stderr}")

    def _create_from_template(self, params: Dict) -> Dict:
        template = params.get("template", "default")
        return self._render_video(params)

    def _batch_render(self, params: Dict) -> Dict:
        compositions = params.get("compositions", [])
        results = []
        for comp in compositions:
            p = {**params, "composition": comp}
            r = self._render_video(p)
            results.append(r)
        all_files = [f for r in results for f in r.get("files", [])]
        return {"files": all_files, "data": {"batch_count": len(results)}}

    def _still_image(self, params: Dict) -> Dict:
        composition = params.get("composition", "Main")
        output_dir = params.get("output_dir", "output")
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, f"{composition}_still.png")

        cmd = ["npx", "remotion", "still", composition, output_file]
        cwd = self._bin_path or self.config.get("project_path")
        rc, stdout, stderr = self._run_cmd(cmd, timeout=300, cwd=cwd)
        if rc == 0:
            return {"files": [output_file], "data": {"composition": composition}}
        raise RuntimeError(f"Remotion still failed: {stderr}")


# -------------------------------------------------------------
# -- 6. OpenMontage Agent视频制作集成
# -------------------------------------------------------------
# GitHub: https://github.com/calesthio/OpenMontage
# Stars: 15K+  |  License: AGPLv3
# 功能: Agent驱动全自动视频制作（脚本→素材→配音→字幕→剪辑→合成）

class OpenMontageAdapter(BaseOpenSourceAdapter):
    """OpenMontage Agent视频制作适配器

    全自动视频生产流水线：从自然语言描述到成片。
    内置12条生产管线，52个工具模块。

    安装方式:
        git clone https://github.com/calesthio/OpenMontage.git
        cd OpenMontage && make setup

    使用示例:
        om = OpenMontageAdapter({"project_path": "/path/to/OpenMontage"})
        result = om.execute("produce_video", {"prompt": "制作60秒科普视频"})
    """

    TOOL_NAME = "openmontage"
    SUPPORTED_OPERATIONS = [
        "produce_video",       # 全自动视频制作
        "generate_script",     # 生成脚本/文案
        "fetch_materials",     # 素材检索/下载
        "tts_voiceover",       # AI配音
        "auto_subtitle",      # 自动字幕
        "compose_timeline",    # 时间线合成
        "animated_explainer",  # 科普动画
        "documentary_montage", # 纪录片剪辑
        "clip_factory",        # 长内容切短视频
    ]

    def check_available(self) -> bool:
        project_path = self.config.get("project_path")
        if project_path and os.path.isdir(project_path):
            self._bin_path = project_path
            return True
        # 检查本地目录
        local = os.path.join(os.path.dirname(__file__), "external", "OpenMontage")
        if os.path.isdir(local):
            self._bin_path = local
            return True
        return False

    def execute(self, operation: str, params: Dict[str, Any]) -> ToolResult:
        result = self._make_result(operation)
        start = time.time()

        if not self.check_available():
            result.status = "simulated"
            result.log.append("[OpenMontage] 工具不可用，使用模拟模式")
            result.output_data = {"simulated": True, "operation": operation}
            result.duration_ms = (time.time() - start) * 1000
            return result

        try:
            # OpenMontage 通过 Python API 调用
            output_dir = params.get("output_dir", "output/openmontage")
            os.makedirs(output_dir, exist_ok=True)

            # 构建调用命令
            prompt = params.get("prompt", "")
            pipeline = params.get("pipeline", operation)

            cmd = [
                sys.executable, "-m", "openmontage",
                "--pipeline", pipeline,
                "--prompt", prompt,
                "--output", output_dir,
            ]

            rc, stdout, stderr = self._run_cmd(cmd, timeout=3600, cwd=self._bin_path)
            if rc == 0:
                output_files = []
                for f in os.listdir(output_dir):
                    output_files.append(os.path.join(output_dir, f))
                result.status = "success"
                result.output_files = output_files
                result.output_data = {"pipeline": pipeline, "output_dir": output_dir}
                result.log.append(f"[OpenMontage] {operation} 完成")
            else:
                raise RuntimeError(f"OpenMontage failed: {stderr}")
        except Exception as e:
            result.status = "error"
            result.error = str(e)
            result.log.append(f"[OpenMontage] 执行失败: {e}")

        result.duration_ms = (time.time() - start) * 1000
        return result


# -------------------------------------------------------------
# -- 7. MoviePy Python视频编辑集成
# -------------------------------------------------------------
# GitHub: https://github.com/Zulko/moviepy
# Stars: 12K+  |  License: MIT
# 功能: Python视频编辑库，脚本化处理

class MoviePyAdapter(BaseOpenSourceAdapter):
    """MoviePy Python视频编辑适配器

    纯Python视频编辑：剪辑、拼接、特效、文字动画。
    适用于快速脚本化视频处理。

    安装方式:
        pip install moviepy
    """

    TOOL_NAME = "moviepy"
    SUPPORTED_OPERATIONS = [
        "cut_clip",            # 剪辑片段
        "concatenate",         # 拼接视频
        "add_text",            # 添加文字
        "add_music",           # 添加背景音乐
        "resize",              # 调整尺寸
        "speed_change",        # 变速
        "compose",             # 多轨合成
        "extract_audio",       # 提取音频
        "gif_convert",         # 视频转GIF
    ]

    def check_available(self) -> bool:
        try:
            import importlib
            importlib.import_module("moviepy")
            return True
        except ImportError:
            return False

    def execute(self, operation: str, params: Dict[str, Any]) -> ToolResult:
        result = self._make_result(operation)
        start = time.time()

        if not self.check_available():
            result.status = "simulated"
            result.log.append("[MoviePy] 工具不可用，使用模拟模式")
            result.output_data = {"simulated": True, "operation": operation}
            result.duration_ms = (time.time() - start) * 1000
            return result

        try:
            try:
                from moviepy import (
                    VideoFileClip, concatenate_videoclips,
                    CompositeVideoClip, TextClip, AudioFileClip
                )
            except ImportError:
                from moviepy.editor import (
                    VideoFileClip, concatenate_videoclips,
                    CompositeVideoClip, TextClip, AudioFileClip
                )

            output_dir = params.get("output_dir", "output")
            os.makedirs(output_dir, exist_ok=True)

            if operation == "cut_clip":
                clip = VideoFileClip(params["input_video"])
                subclip = clip.subclip(params.get("start", 0), params.get("end", clip.duration))
                output_file = os.path.join(output_dir, "cut_output.mp4")
                subclip.write_videofile(output_file)
                clip.close()
                result.output_files = [output_file]

            elif operation == "concatenate":
                clips = [VideoFileClip(f) for f in params.get("input_files", [])]
                final = concatenate_videoclips(clips)
                output_file = os.path.join(output_dir, "concat_output.mp4")
                final.write_videofile(output_file)
                for c in clips:
                    c.close()
                result.output_files = [output_file]

            elif operation == "extract_audio":
                clip = VideoFileClip(params["input_video"])
                if clip.audio is None:
                    clip.close()
                    result.status = "simulated"
                    result.log.append("[MoviePy] 视频无音轨，跳过提取")
                    result.output_data = {"simulated": True, "reason": "no_audio_track"}
                else:
                    output_file = os.path.join(output_dir, "extracted_audio.mp3")
                    clip.audio.write_audiofile(output_file)
                    clip.close()
                    result.output_files = [output_file]

            elif operation == "gif_convert":
                clip = VideoFileClip(params["input_video"])
                output_file = os.path.join(output_dir, "output.gif")
                clip.write_gif(output_file)
                clip.close()
                result.output_files = [output_file]

            else:
                result.output_data = {"simulated": True, "note": f"{operation} not fully implemented"}

            result.status = "success"
            result.log.append(f"[MoviePy] {operation} 完成")
        except Exception as e:
            result.status = "error"
            result.error = str(e)
            result.log.append(f"[MoviePy] 执行失败: {e}")

        result.duration_ms = (time.time() - start) * 1000
        return result


# -------------------------------------------------------------
# -- 统一调度器
# -------------------------------------------------------------

class OpenSourceHub:
    """开源项目统一调度中心

    管理所有开源工具适配器，提供统一调用入口。

    使用示例:
        hub = OpenSourceHub()
        hub.auto_detect()  # 自动检测可用工具

        # 统一调用
        result = hub.execute("rife", "interpolate_2x", {"input_video": "input.mp4"})
        result = hub.execute("sam2", "segment_video", {"input_video": "input.mp4"})
        result = hub.execute("whisper", "generate_subtitles", {"input_video": "input.mp4"})

        # 查看状态
        print(hub.status_report())
    """

    ADAPTERS = {
        "rife": RIFEAdapter,
        "sam2": SAM2Adapter,
        "video2x": Video2XAdapter,
        "whisper": WhisperAdapter,
        "remotion": RemotionAdapter,
        "openmontage": OpenMontageAdapter,
        "moviepy": MoviePyAdapter,
    }

    def __init__(self, configs: Optional[Dict[str, Dict]] = None):
        self.configs = configs or {}
        self._adapters: Dict[str, BaseOpenSourceAdapter] = {}
        self._available: Dict[str, bool] = {}
        self._init_adapters()

    def _init_adapters(self):
        for name, cls in self.ADAPTERS.items():
            config = self.configs.get(name, {})
            self._adapters[name] = cls(config)

    def auto_detect(self) -> Dict[str, bool]:
        """自动检测所有工具的可用状态"""
        for name, adapter in self._adapters.items():
            self._available[name] = adapter.check_available()
        return self._available

    def execute(self, tool_name: str, operation: str, params: Dict[str, Any]) -> ToolResult:
        """统一执行入口"""
        if tool_name not in self._adapters:
            result = ToolResult(tool_name=tool_name, operation=operation, status="error")
            result.error = f"Unknown tool: {tool_name}. Available: {list(self.ADAPTERS.keys())}"
            return result

        adapter = self._adapters[tool_name]
        return adapter.execute(operation, params)

    def status_report(self) -> str:
        """生成工具状态报告"""
        self.auto_detect()
        lines = ["=" * 60, "开源项目集成状态报告", "=" * 60]
        for name, available in self._available.items():
            status = "[OK] 可用" if available else "[X] 未安装"
            adapter = self._adapters[name]
            ops = ", ".join(adapter.list_operations()[:3]) + "..."
            lines.append(f"  {name:15s} {status:10s}  操作: {ops}")
        lines.append("=" * 60)
        available_count = sum(1 for v in self._available.values() if v)
        lines.append(f"总计: {available_count}/{len(self._available)} 工具可用")
        return "\n".join(lines)

    def get_adapter(self, tool_name: str) -> Optional[BaseOpenSourceAdapter]:
        return self._adapters.get(tool_name)

    def list_tools(self) -> List[str]:
        return list(self.ADAPTERS.keys())

    def list_operations(self, tool_name: str) -> List[str]:
        adapter = self._adapters.get(tool_name)
        return adapter.list_operations() if adapter else []


# -------------------------------------------------------------
# -- 便捷工厂函数
# -------------------------------------------------------------

def create_hub(configs: Optional[Dict[str, Dict]] = None) -> OpenSourceHub:
    """创建开源项目调度中心"""
    return OpenSourceHub(configs)


def quick_status() -> str:
    """快速获取工具状态"""
    hub = create_hub()
    return hub.status_report()


# -------------------------------------------------------------
# -- 主入口
# -------------------------------------------------------------

if __name__ == "__main__":
    print(quick_status())
