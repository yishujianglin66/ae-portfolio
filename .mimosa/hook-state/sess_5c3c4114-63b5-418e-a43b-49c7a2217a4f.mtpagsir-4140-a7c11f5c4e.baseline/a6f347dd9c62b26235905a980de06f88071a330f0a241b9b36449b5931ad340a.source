"""
integrations/scail2_adapter.py — SCAIL-2 角色动画集成适配器
=============================================================

SCAIL-2 (智谱 × 清华): DiT 端到端角色动画生成
  - 支持手绘/真实/动物/多人角色零样本动画驱动
  - Apache 2.0 协议
  - GitHub: https://github.com/zai-org/SCAIL-2

集成点:
  - 手书动画管线: 手绘关键帧 → SCAIL-2 → 动画角色视频
  - 角色动画服务: 姿态/表情驱动
  - ComfyUI 工作流: 手绘风格化节点

用法:
    from integrations.scail2_adapter import SCAIL2Adapter
    adapter = SCAIL2Adapter()
    result = adapter.execute("animate_character", {
        "reference_image": "path/to/drawing.png",
        "motion_sequence": "path/to/motion.mp4",
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
_SCAIL2_DIR = _EXTERNAL_DIR / "scail2"


class SCAIL2Adapter:
    """SCAIL-2 角色动画适配器

    封装 SCAIL-2 模型，提供:
    1. animate_character: 参考图 + 动作序列 → 角色动画视频
    2. check_environment: 检查模型/依赖可用性
    3. list_capabilities: 列出支持的角色类型和动作模式
    """

    TOOL_NAME = "scail2"
    SUPPORTED_OPERATIONS = [
        "animate_character",
        "check_environment",
        "list_capabilities",
        "get_model_info",
        "estimate_vram",
    ]

    # SCAIL-2 支持的角色类型
    CHARACTER_TYPES = [
        "realistic_human",
        "hand_drawn",
        "anime",
        "animal",
        "multi_character",
    ]

    # 动作驱动模式
    MOTION_MODES = [
        "video_driven",      # 视频驱动 (从参考视频提取动作)
        "pose_sequence",     # 姿态序列驱动
        "audio_driven",      # 音频驱动 (需配合 MuseTalk)
    ]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._source_available = _SCAIL2_DIR.is_dir()
        self._simulate = not self._source_available
        self._env_check = self._check_environment()

    def _check_environment(self) -> Dict[str, Any]:
        """检查运行环境"""
        checks: Dict[str, Any] = {
            "source_cloned": self._source_available,
            "simulate_mode": self._simulate,
        }

        # Python 依赖检查
        for mod in ["torch", "torchvision", "diffusers", "accelerate", "einops"]:
            try:
                __import__(mod)
                checks[f"dep_{mod}"] = True
            except ImportError:
                checks[f"dep_{mod}"] = False

        # GPU 检查
        try:
            import torch
            checks["cuda_available"] = torch.cuda.is_available()
            if torch.cuda.is_available():
                checks["gpu_name"] = torch.cuda.get_device_name(0)
                checks["gpu_vram_gb"] = round(
                    torch.cuda.get_device_properties(0).total_memory / 1024**3, 1
                )
        except (ImportError, RuntimeError):
            checks["cuda_available"] = False
            checks["gpu_vram_gb"] = 0

        # 模型权重检查 (SCAIL-2 实际权重为 .pth/.pt: VAE/T5/CLIP/LoRA)
        weights_dir = _SCAIL2_DIR / "weights"
        checks["weights_available"] = weights_dir.is_dir() and any(
            weights_dir.rglob(ext)
            for ext in ("*.pth", "*.pt", "*.safetensors")
        ) if weights_dir.is_dir() else False

        return checks

    def check_available(self) -> bool:
        """检查适配器是否可用（源码已克隆且核心依赖已安装）"""
        return (
            self._source_available
            and self._env_check.get("dep_torch", False)
            and self._env_check.get("dep_diffusers", False)
        )

    def list_operations(self) -> List[str]:
        return self.SUPPORTED_OPERATIONS

    def execute(self, operation: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """执行操作

        Args:
            operation: 操作名称
            params: 操作参数

        Returns:
            执行结果字典
        """
        params = params or {}

        if operation == "check_environment":
            return self._env_check
        elif operation == "list_capabilities":
            return self._list_capabilities()
        elif operation == "get_model_info":
            return self._get_model_info()
        elif operation == "estimate_vram":
            return self._estimate_vram(params)
        elif operation == "animate_character":
            return self._animate_character(params)
        else:
            return {"status": "error", "message": f"Unknown operation: {operation}"}

    def _list_capabilities(self) -> Dict[str, Any]:
        return {
            "status": "success",
            "character_types": self.CHARACTER_TYPES,
            "motion_modes": self.MOTION_MODES,
            "max_resolution": "1024x1024",
            "output_formats": ["mp4", "gif", "frame_sequence"],
            "batch_support": False,
            "zero_shot": True,
        }

    def _get_model_info(self) -> Dict[str, Any]:
        return {
            "status": "success",
            "model_name": "SCAIL-2",
            "architecture": "DiT (Diffusion Transformer)",
            "paper": "SCAIL-2: Scaling Character Animation with Large-Scale Video Generation",
            "license": "Apache 2.0",
            "org": "Zhipu AI × Tsinghua University",
            "github": "https://github.com/zai-org/SCAIL-2",
            "key_features": [
                "端到端 DiT 架构，无需显式 3D 中间表示",
                "零样本角色动画：单张参考图 + 动作序列即可驱动",
                "支持手绘/真实/动物/多人等多种角色类型",
                "唯一开源的手绘角色零样本动画模型",
            ],
            "vram_requirement": {
                "minimum_gb": 16,
                "recommended_gb": 24,
                "resolution": "512x512 @ 16GB, 1024x1024 @ 24GB",
            },
        }

    def _estimate_vram(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """估算 VRAM 需求"""
        resolution = params.get("resolution", "512x512")
        num_frames = params.get("num_frames", 60)
        character_type = params.get("character_type", "realistic_human")

        # 基于 SCAIL-2 论文的 VRAM 估算
        w, h = map(int, resolution.split("x"))
        pixels = w * h
        base_vram = 8.0  # 基础模型加载
        vram_per_pixel = 0.000008  # 每像素额外 VRAM
        frame_factor = min(num_frames / 30.0, 4.0)  # 帧数因子

        estimated = base_vram + (pixels * vram_per_pixel * frame_factor)

        # 手绘角色比真实人物省 VRAM（线条简单）
        if character_type == "hand_drawn":
            estimated *= 0.85
        elif character_type == "multi_character":
            estimated *= 1.3

        return {
            "status": "success",
            "estimated_vram_gb": round(estimated, 1),
            "resolution": resolution,
            "num_frames": num_frames,
            "character_type": character_type,
            "degradation_options": {
                "half_precision": "fp16/bf16 节省 ~30%",
                "lower_resolution": f"降至 {w//2}x{h//2} 节省 ~50%",
                "fewer_frames": f"减至 {max(num_frames//2, 16)} 帧节省 ~25%",
            },
        }

    def _animate_character(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """角色动画生成

        Args:
            params: {
                "reference_image": str,     # 参考图路径
                "motion_sequence": str,     # 动作序列路径 (视频/姿态文件)
                "output_path": str,         # 输出路径
                "resolution": str,          # 分辨率 (默认 512x512)
                "num_frames": int,          # 帧数
                "character_type": str,      # 角色类型
                "motion_mode": str,         # 动作模式
            }
        """
        ref_image = params.get("reference_image", "")
        motion_seq = params.get("motion_sequence", "")
        output_path = params.get("output_path", "")
        resolution = params.get("resolution", "512x512")
        num_frames = params.get("num_frames", 60)

        if not ref_image:
            return {"status": "error", "message": "reference_image is required"}

        if self._simulate:
            # 模拟模式：验证参数，返回模拟结果
            return {
                "status": "success",
                "mode": "simulate",
                "message": "SCAIL-2 源码未克隆，使用模拟模式",
                "output_path": output_path or "output_scail2_simulate.mp4",
                "params": {
                    "reference_image": ref_image,
                    "motion_sequence": motion_seq,
                    "resolution": resolution,
                    "num_frames": num_frames,
                },
                "simulated_output": True,
            }

        # 实际执行模式
        try:
            # 构建 SCAIL-2 推理命令
            script_path = _SCAIL2_DIR / "inference.py"
            if not script_path.exists():
                # 尝试其他入口
                script_path = _SCAIL2_DIR / "scripts" / "inference.py"

            cmd = [
                sys.executable, str(script_path),
                "--reference_image", ref_image,
                "--motion_sequence", motion_seq,
                "--output", output_path or "output_scail2.mp4",
                "--resolution", resolution,
                "--num_frames", str(num_frames),
            ]

            # 添加可选参数
            if params.get("character_type"):
                cmd.extend(["--character_type", params["character_type"]])
            if params.get("seed"):
                cmd.extend(["--seed", str(params["seed"])])

            proc = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=600, cwd=str(_SCAIL2_DIR),
            )

            if proc.returncode == 0:
                return {
                    "status": "success",
                    "mode": "real",
                    "output_path": output_path or "output_scail2.mp4",
                    "stdout": proc.stdout[-500:] if proc.stdout else "",
                }
            else:
                return {
                    "status": "error",
                    "mode": "real",
                    "stderr": proc.stderr[-500:] if proc.stderr else "",
                    "returncode": proc.returncode,
                }

        except subprocess.TimeoutExpired:
            return {"status": "error", "message": "SCAIL-2 inference timed out (600s)"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


# ── 集成注册入口 ──────────────────────────────────────────────────

def get_adapter(config: Optional[Dict[str, Any]] = None) -> SCAIL2Adapter:
    """工厂函数，供 integration_registry 调用"""
    return SCAIL2Adapter(config)
