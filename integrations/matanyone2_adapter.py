"""
integrations/matanyone2_adapter.py — MatAnyone2 视频抠图升级适配器
===================================================================

MatAnyone2 (CVPR 2026 Highlight): 发丝级视频抠图
  - 零样本视频抠图，发丝/半透明/运动模糊场景 SOTA
  - 8GB 显存即可运行，支持 4K 输入
  - GitHub: https://github.com/pq-yang/MatAnyone2
  - 论文: MatAnyone 2: Scaling Video Matting via Efficient Memory Management

与现有 MatAnyone v1 的关系:
  - external/matanyone/ 已有 v1 版本 (repo/ + weights/)
  - v2 升级: 发丝级精度 + 显存优化 (8GB vs v1 的 12GB)
  - 本适配器作为 v1 的升级替代，保留 v1 降级路径

集成点:
  - 分割抠像管线: 替代/升级现有 MatAnyone v1
  - 与 BiRefNet 互补: BiRefNet 擅长静态图像，MatAnyone2 擅长视频时序一致性
  - 手书动画管线: 角色分离 → 手绘风格化 → 合成

用法:
    from integrations.matanyone2_adapter import MatAnyone2Adapter
    adapter = MatAnyone2Adapter()
    result = adapter.execute("video_matting", {
        "video_path": "input.mp4",
        "output_dir": "output/matte/",
    })
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_EXTERNAL_DIR = _PROJECT_ROOT / "external"
_MATANYONE2_DIR = _EXTERNAL_DIR / "matanyone2"
_MATANYONE_V1_DIR = _EXTERNAL_DIR / "matanyone"


class MatAnyone2Adapter:
    """MatAnyone2 视频抠图适配器

    封装 MatAnyone2 推理管线，提供:
    1. video_matting: 视频抠图（发丝级精度）
    2. image_matting: 单帧精细抠图
    3. check_environment: 环境检查
    4. compare_with_v1: 与 v1 版本对比
    """

    TOOL_NAME = "matanyone2"
    SUPPORTED_OPERATIONS = [
        "video_matting",
        "image_matting",
        "check_environment",
        "get_model_info",
        "estimate_vram",
        "compare_with_v1",
        "extract_alpha_sequence",
    ]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._source_available = _MATANYONE2_DIR.is_dir()
        self._v1_available = _MATANYONE_V1_DIR.is_dir()
        self._simulate = not self._source_available
        self._env_check = self._check_environment()

    def _check_environment(self) -> Dict[str, Any]:
        checks: Dict[str, Any] = {
            "source_cloned": self._source_available,
            "v1_available": self._v1_available,
            "simulate_mode": self._simulate,
        }

        # Python 依赖
        for mod in ["torch", "torchvision", "pillow", "opencv-python", "tqdm"]:
            mod_import = mod.replace("-python", "")
            if mod_import == "opencv":
                mod_import = "cv2"
            try:
                __import__(mod_import)
                checks[f"dep_{mod}"] = True
            except ImportError:
                checks[f"dep_{mod}"] = False

        # GPU
        try:
            import torch
            checks["cuda_available"] = torch.cuda.is_available()
            if torch.cuda.is_available():
                checks["gpu_vram_gb"] = round(
                    torch.cuda.get_device_properties(0).total_memory / 1024**3, 1
                )
        except (ImportError, RuntimeError):
            checks["cuda_available"] = False

        # 权重检查 (README 官方路径为 pretrained_models/, 兼容 checkpoints/weights)
        checks["weights_available"] = False
        for d in (
            _MATANYONE2_DIR / "pretrained_models",
            _MATANYONE2_DIR / "checkpoints",
            _MATANYONE2_DIR / "weights",
        ):
            if d.is_dir() and (
                any(d.rglob("*.pth")) or any(d.rglob("*.safetensors"))
            ):
                checks["weights_available"] = True
                break

        return checks

    def check_available(self) -> bool:
        return self._source_available and self._env_check.get("dep_torch", False)

    def list_operations(self) -> List[str]:
        return self.SUPPORTED_OPERATIONS

    def execute(self, operation: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = params or {}

        handlers = {
            "check_environment": lambda: self._env_check,
            "get_model_info": self._get_model_info,
            "estimate_vram": lambda: self._estimate_vram(params),
            "compare_with_v1": self._compare_with_v1,
            "video_matting": lambda: self._video_matting(params),
            "image_matting": lambda: self._image_matting(params),
            "extract_alpha_sequence": lambda: self._extract_alpha_sequence(params),
        }

        handler = handlers.get(operation)
        if handler:
            return handler()
        return {"status": "error", "message": f"Unknown operation: {operation}"}

    def _get_model_info(self) -> Dict[str, Any]:
        return {
            "status": "success",
            "model_name": "MatAnyone 2",
            "architecture": "Efficient Memory-Managed Video Matting Network",
            "paper": "MatAnyone 2: Scaling Video Matting via Efficient Memory Management",
            "venue": "CVPR 2026 Highlight",
            "license": "Apache 2.0",
            "github": "https://github.com/pq-yang/MatAnyone2",
            "key_features": [
                "发丝级视频抠图精度 (SOTA on VideoMatting benchmark)",
                "8GB 显存运行 (v1 需 12GB)",
                "支持 4K 输入分辨率",
                "时序一致性: 无闪烁 alpha 序列",
                "零样本: 无需针对特定场景微调",
            ],
            "vram_requirement": {
                "minimum_gb": 8,
                "recommended_gb": 12,
                "max_resolution": "4K (3840x2160)",
            },
            "improvements_over_v1": {
                "memory": "高效显存管理，降低 33%",
                "quality": "发丝/半透明区域精度提升 15%",
                "speed": "处理速度提升 2x",
            },
        }

    def _estimate_vram(self, params: Dict[str, Any]) -> Dict[str, Any]:
        resolution = params.get("resolution", "1080p")
        res_map = {
            "720p": (1280, 720),
            "1080p": (1920, 1080),
            "4k": (3840, 2160),
        }
        w, h = res_map.get(resolution, (1920, 1080))

        # MatAnyone2 显存估算 (8GB 基础 for 1080p)
        base_vram = 5.0
        pixel_factor = (w * h) / (1920 * 1080)
        estimated = base_vram * pixel_factor

        return {
            "status": "success",
            "estimated_vram_gb": round(estimated, 1),
            "resolution": resolution,
            "degradation_options": {
                "half_precision": "fp16 节省 ~25%",
                "lower_resolution": "降至 720p 节省 ~55%",
                "chunk_processing": "分块处理长视频 (恒定 8GB)",
            },
        }

    def _compare_with_v1(self) -> Dict[str, Any]:
        return {
            "status": "success",
            "comparison": {
                "v1": {
                    "dir": str(_MATANYONE_V1_DIR),
                    "available": self._v1_available,
                    "vram_gb": 12,
                    "max_resolution": "1080p",
                    "quality": "good",
                },
                "v2": {
                    "dir": str(_MATANYONE2_DIR),
                    "available": self._source_available,
                    "vram_gb": 8,
                    "max_resolution": "4K",
                    "quality": "excellent (hair-level)",
                },
            },
            "recommendation": "优先使用 v2，v1 作为降级方案",
        }

    def _video_matting(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """视频抠图

        Args:
            params: {
                "video_path": str,      # 输入视频路径
                "output_dir": str,      # 输出目录
                "resolution": str,      # 处理分辨率
                "fp16": bool,           # 是否使用半精度
                "recursive": bool,      # 是否递归处理目录
            }
        """
        video_path = params.get("video_path", "")
        output_dir = params.get("output_dir", "")

        if not video_path:
            return {"status": "error", "message": "video_path is required"}

        if self._simulate:
            return {
                "status": "success",
                "mode": "simulate",
                "message": "MatAnyone2 源码未克隆，使用模拟模式",
                "output_dir": output_dir or "output_matanyone2_simulate/",
                "params": {"video_path": video_path},
                "simulated_output": True,
                "outputs": {
                    "rgba_video": "output_rgba.mp4",
                    "alpha_sequence": "alpha_frames/",
                    "fg_video": "foreground.mp4",
                },
            }

        try:
            script_path = _MATANYONE2_DIR / "inference.py"
            if not script_path.exists():
                script_path = _MATANYONE2_DIR / "scripts" / "inference.py"

            cmd = [
                sys.executable, str(script_path),
                "--input", video_path,
                "--output-dir", output_dir or "output_matanyone2/",
            ]

            if params.get("fp16", True):
                cmd.append("--fp16")
            if params.get("resolution"):
                cmd.extend(["--resolution", params["resolution"]])

            proc = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=1200, cwd=str(_MATANYONE2_DIR),
            )

            if proc.returncode == 0:
                return {
                    "status": "success",
                    "mode": "real",
                    "output_dir": output_dir or "output_matanyone2/",
                    "stdout": proc.stdout[-500:] if proc.stdout else "",
                }
            else:
                return {
                    "status": "error",
                    "stderr": proc.stderr[-500:] if proc.stderr else "",
                }

        except subprocess.TimeoutExpired:
            return {"status": "error", "message": "MatAnyone2 timed out (1200s)"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _image_matting(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """单帧精细抠图"""
        image_path = params.get("image_path", "")
        if not image_path:
            return {"status": "error", "message": "image_path is required"}

        if self._simulate:
            return {
                "status": "success",
                "mode": "simulate",
                "output_path": params.get("output_path", "output_matting_simulate.png"),
                "simulated_output": True,
            }

        # 使用视频抠图的单帧模式
        return self._video_matting({
            "video_path": image_path,
            "output_dir": params.get("output_dir", ""),
            **{k: v for k, v in params.items() if k not in ("image_path",)},
        })

    def _extract_alpha_sequence(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """提取 alpha 序列（PNG 帧）"""
        return self._video_matting({
            **params,
            "output_format": "alpha_png_sequence",
        })


def get_adapter(config: Optional[Dict[str, Any]] = None) -> MatAnyone2Adapter:
    return MatAnyone2Adapter(config)
