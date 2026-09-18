"""
integrations/musetalk_adapter.py — MuseTalk 音频驱动唇同步适配器
=================================================================

MuseTalk (TMElyralab/腾讯): 实时音频驱动唇部同步
  - 30fps+ 实时唇同步，支持多语言
  - 基于 LatentSync 架构，低延迟
  - GitHub: https://github.com/TMElyralab/MuseTalk

集成点:
  - 音频驱动口型: 音频 + 人像 → 唇同步视频
  - 与 SCAIL-2 互补: SCAIL-2 驱动全身动作，MuseTalk 驱动面部唇同步
  - Hallo3 降级方案: 当 Hallo3 不可用时使用 MuseTalk

用法:
    from integrations.musetalk_adapter import MuseTalkAdapter
    adapter = MuseTalkAdapter()
    result = adapter.execute("lip_sync", {
        "audio_path": "speech.wav",
        "video_path": "portrait.mp4",
        "output_path": "output_lipsync.mp4",
    })
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_EXTERNAL_DIR = _PROJECT_ROOT / "external"
_MUSETALK_DIR = _EXTERNAL_DIR / "musetalk"


class MuseTalkAdapter:
    """MuseTalk 音频驱动唇同步适配器

    封装 MuseTalk 推理管线，提供:
    1. lip_sync: 音频 + 人像视频 → 唇同步视频
    2. batch_lip_sync: 批量唇同步
    3. check_environment: 环境检查
    4. list_models: 可用模型列表
    """

    TOOL_NAME = "musetalk"
    SUPPORTED_OPERATIONS = [
        "lip_sync",
        "batch_lip_sync",
        "check_environment",
        "list_models",
        "estimate_vram",
        "get_model_info",
    ]

    # 支持的音频格式
    AUDIO_FORMATS = [".wav", ".mp3", ".flac", ".ogg", ".m4a"]
    # 支持的视频格式
    VIDEO_FORMATS = [".mp4", ".avi", ".mov", ".mkv"]

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self._source_available = _MUSETALK_DIR.is_dir()
        self._simulate = not self._source_available
        self._env_check = self._check_environment()

    def _check_environment(self) -> dict[str, Any]:
        """检查运行环境"""
        checks: dict[str, Any] = {
            "source_cloned": self._source_available,
            "simulate_mode": self._simulate,
        }

        # Python 依赖
        for mod in ["torch", "torchvision", "diffusers", "transformers",
                     "decord", "ffmpeg"]:
            try:
                __import__(mod)
                checks[f"dep_{mod}"] = True
            except ImportError:
                checks[f"dep_{mod}"] = False

        # ffmpeg 检查
        try:
            r = subprocess.run(
                ["ffmpeg", "-version"], capture_output=True, text=True, timeout=5
            )
            checks["ffmpeg_ok"] = r.returncode == 0
            if r.returncode == 0:
                checks["ffmpeg_version"] = r.stdout.split("\n")[0]
        except (FileNotFoundError, subprocess.TimeoutExpired):
            checks["ffmpeg_ok"] = False

        # GPU 检查
        try:
            import torch
            checks["cuda_available"] = torch.cuda.is_available()
            if torch.cuda.is_available():
                checks["gpu_vram_gb"] = round(
                    torch.cuda.get_device_properties(0).total_memory / 1024**3, 1
                )
        except (ImportError, RuntimeError):
            checks["cuda_available"] = False

        # 模型权重 (MuseTalk 权重为 .pth/.bin: musetalk.json + pytorch_model.bin / unet.pth)
        weights_dir = _MUSETALK_DIR / "models"
        checks["weights_available"] = weights_dir.is_dir() and any(
            weights_dir.rglob(ext)
            for ext in ("*.pth", "*.bin", "*.safetensors")
        ) if weights_dir.is_dir() else False

        return checks

    def check_available(self) -> bool:
        return (
            self._source_available
            and self._env_check.get("dep_torch", False)
            and self._env_check.get("ffmpeg_ok", False)
        )

    def list_operations(self) -> list[str]:
        return self.SUPPORTED_OPERATIONS

    def execute(self, operation: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        params = params or {}

        handlers = {
            "check_environment": lambda: self._env_check,
            "list_models": self._list_models,
            "get_model_info": self._get_model_info,
            "estimate_vram": lambda: self._estimate_vram(params),
            "lip_sync": lambda: self._lip_sync(params),
            "batch_lip_sync": lambda: self._batch_lip_sync(params),
        }

        handler = handlers.get(operation)
        if handler:
            return handler()
        return {"status": "error", "message": f"Unknown operation: {operation}"}

    def _list_models(self) -> dict[str, Any]:
        return {
            "status": "success",
            "models": [
                {
                    "name": "musetalk_v1",
                    "description": "基础唇同步模型",
                    "vram_gb": 4,
                    "fps": 30,
                },
                {
                    "name": "musetalk_v2",
                    "description": "增强版，支持侧脸/遮挡",
                    "vram_gb": 6,
                    "fps": 25,
                },
            ],
        }

    def _get_model_info(self) -> dict[str, Any]:
        return {
            "status": "success",
            "model_name": "MuseTalk",
            "architecture": "LatentSync + Whisper Audio Encoder",
            "paper": "MuseTalk: Real-Time High Quality Lip Synchronization",
            "license": "Apache 2.0",
            "org": "Tencent Music (TMElyralab)",
            "github": "https://github.com/TMElyralab/MuseTalk",
            "key_features": [
                "实时 30fps+ 唇同步",
                "Whisper 音频编码器，多语言支持",
                "低 VRAM 需求 (4GB 起)",
                "支持侧脸和部分遮挡场景",
            ],
            "vram_requirement": {
                "minimum_gb": 4,
                "recommended_gb": 8,
            },
        }

    def _estimate_vram(self, params: dict[str, Any]) -> dict[str, Any]:
        resolution = params.get("resolution", "512x512")
        w, h = map(int, resolution.split("x")) if "x" in resolution else (512, 512)

        # MuseTalk VRAM 相对较低
        base_vram = 2.5
        pixel_factor = (w * h) / (512 * 512) * 1.5
        estimated = base_vram * pixel_factor

        return {
            "status": "success",
            "estimated_vram_gb": round(estimated, 1),
            "resolution": resolution,
            "note": "MuseTalk VRAM 需求低，4GB GPU 即可运行",
        }

    def _lip_sync(self, params: dict[str, Any]) -> dict[str, Any]:
        """音频驱动唇同步

        Args:
            params: {
                "audio_path": str,      # 音频文件路径
                "video_path": str,      # 人像视频/图片路径
                "output_path": str,     # 输出路径
                "resolution": str,      # 输出分辨率
                "batch_size": int,      # 批处理大小
            }
        """
        audio_path = params.get("audio_path", "")
        video_path = params.get("video_path", "")
        output_path = params.get("output_path", "")

        if not audio_path or not video_path:
            return {"status": "error", "message": "audio_path and video_path are required"}

        if self._simulate:
            return {
                "status": "success",
                "mode": "simulate",
                "message": "MuseTalk 源码未克隆，使用模拟模式",
                "output_path": output_path or "output_musetalk_simulate.mp4",
                "params": {
                    "audio_path": audio_path,
                    "video_path": video_path,
                },
                "simulated_output": True,
            }

        # 实际执行
        try:
            script_path = _MUSETALK_DIR / "scripts" / "inference.py"
            if not script_path.exists():
                script_path = _MUSETALK_DIR / "inference.py"

            cmd = [
                sys.executable, str(script_path),
                "--audio_path", audio_path,
                "--video_path", video_path,
                "--output_path", output_path or "output_musetalk.mp4",
            ]

            if params.get("batch_size"):
                cmd.extend(["--batch_size", str(params["batch_size"])])
            if params.get("resolution"):
                cmd.extend(["--resolution", params["resolution"]])

            proc = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=300, cwd=str(_MUSETALK_DIR),
            )

            if proc.returncode == 0:
                return {
                    "status": "success",
                    "mode": "real",
                    "output_path": output_path or "output_musetalk.mp4",
                    "stdout": proc.stdout[-500:] if proc.stdout else "",
                }
            else:
                return {
                    "status": "error",
                    "mode": "real",
                    "stderr": proc.stderr[-500:] if proc.stderr else "",
                }

        except subprocess.TimeoutExpired:
            return {"status": "error", "message": "MuseTalk inference timed out (300s)"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _batch_lip_sync(self, params: dict[str, Any]) -> dict[str, Any]:
        """批量唇同步"""
        items = params.get("items", [])
        results = []
        for item in items:
            result = self._lip_sync(item)
            results.append(result)

        success_count = sum(1 for r in results if r.get("status") == "success")
        return {
            "status": "success" if success_count == len(results) else "partial",
            "total": len(results),
            "success": success_count,
            "failed": len(results) - success_count,
            "results": results,
        }


def get_adapter(config: dict[str, Any] | None = None) -> MuseTalkAdapter:
    return MuseTalkAdapter(config)
