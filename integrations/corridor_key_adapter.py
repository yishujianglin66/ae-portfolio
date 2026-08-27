"""
CorridorKey AI 抠像适配器 v1.0
================================
基于神经网络的绿幕抠像引擎适配器。

CorridorKey (nikopueringer/CorridorKey, 13.4k★) 使用 Hiera 骨干网络 + CNN 精炼器
实现物理级颜色分离，输出 VFX 标准 EXR (直前景色 + 线性 Alpha)。

核心能力:
  - 物理精确颜色分离 (非二进制蒙版)
  - 分辨率无关 (支持 4K, 动态缩放至 2048x2048)
  - 绿幕/蓝幕自动检测
  - 16/32-bit 线性 EXR 输出
  - 可选 AlphaHint 生成器 (GVM/VideoMaMa/BiRefNet)

系统要求:
  - Python 3.10~3.13
  - torch >= 2.8.0 (项目要求)
  - NVIDIA CUDA 6-8GB VRAM 或 Apple Silicon
  - 模型文件 ~300MB (CorridorKey.pth)

集成来源: nikopueringer/CorridorKey (13.4k★)
"""

import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXTERNAL_DIR = PROJECT_ROOT / "external"
CK_DIR = EXTERNAL_DIR / "CorridorKey"
CK_MODULE = CK_DIR / "CorridorKeyModule"
CK_CKPT_DIR = CK_MODULE / "checkpoints"


def _find_checkpoint() -> Optional[Path]:
    """查找 checkpoint — 同时支持 .pth 和 .safetensors

    实际下载产物为 CorridorKey_v1.0.safetensors (~380MB),
    旧版只认 CorridorKey.pth 会导致误报 checkpoint 缺失。
    """
    if not CK_CKPT_DIR.is_dir():
        return None
    candidates = sorted(CK_CKPT_DIR.iterdir())
    for suffix in (".safetensors", ".pth"):
        for f in candidates:
            if f.is_file() and f.suffix == suffix and "corridorkey" in f.name.lower():
                return f
    return None


CK_CHECKPOINT = _find_checkpoint()


class CorridorKeyAdapter:
    """CorridorKey AI 抠像适配器

    降级策略:
      - 源码存在 + 依赖满足 → 完整推理
      - 源码存在 + 依赖不满足 → 环境检测 + 架构分析
      - 源码不存在 → 不可用
    """

    SUPPORTED_OPERATIONS = [
        "key_green_screen", "batch_key", "generate_alpha_hint",
        "cleanup_matte", "check_environment", "get_model_info",
        "list_alpha_hint_generators", "get_architecture",
    ]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._source_available = CK_DIR.is_dir()
        self._module_available = CK_MODULE.is_dir()
        self._env_check = self._check_environment()

    def _check_environment(self) -> Dict[str, Any]:
        """检测运行环境"""
        checks = {
            "source_cloned": self._source_available,
            "module_exists": self._module_available,
            "checkpoint_exists": CK_CHECKPOINT is not None and CK_CHECKPOINT.is_file(),
            "checkpoint_path": str(CK_CHECKPOINT) if CK_CHECKPOINT else None,
        }

        # Python 版本
        py_version = sys.version_info
        checks["python_version"] = f"{py_version.major}.{py_version.minor}.{py_version.micro}"
        checks["python_ok"] = (3, 10) <= py_version[:2] <= (3, 13)

        # torch 版本
        try:
            import torch
            checks["torch_version"] = torch.__version__
            # 项目推荐 >= 2.8.0, 但实战验证 2.6.0+cu124 可正常推理
            # → torch_ok 以实测最低 2.6 为准, recommended 字段保留官方要求
            ver = torch.__version__.split("+")[0]
            parts = tuple(int(p) for p in ver.split(".")[:2] if p.isdigit())
            major, minor = (parts + (0, 0))[:2]
            checks["torch_ok"] = (major, minor) >= (2, 6)
            checks["torch_recommended"] = (major, minor) >= (2, 8)
            checks["cuda_available"] = torch.cuda.is_available()
            if torch.cuda.is_available():
                checks["gpu_name"] = torch.cuda.get_device_name(0)
                checks["gpu_memory_gb"] = round(torch.cuda.get_device_properties(0).total_memory / 1024**3, 1)
                checks["vram_ok"] = checks["gpu_memory_gb"] >= 6.0
            else:
                checks["gpu_name"] = None
                checks["vram_ok"] = False
        except ImportError:
            checks["torch_version"] = None
            checks["torch_ok"] = False
            checks["torch_recommended"] = False
            checks["cuda_available"] = False
            checks["vram_ok"] = False

        # uv 包管理器
        try:
            result = subprocess.run(["uv", "--version"], capture_output=True, text=True, timeout=5)
            checks["uv_available"] = result.returncode == 0
            checks["uv_version"] = result.stdout.strip() if result.returncode == 0 else None
        except (FileNotFoundError, subprocess.TimeoutExpired):
            checks["uv_available"] = False
            checks["uv_version"] = None

        # 综合判断
        checks["can_run_inference"] = all([
            checks["source_cloned"],
            checks["module_exists"],
            checks["checkpoint_exists"],
            checks["python_ok"],
            checks["torch_ok"],
            checks["vram_ok"],
        ])

        return checks

    def check_available(self) -> bool:
        return self._source_available

    def list_operations(self) -> List[str]:
        return self.SUPPORTED_OPERATIONS

    def execute(self, operation: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = params or {}
        start = time.time()
        try:
            if operation == "check_environment":
                result = self._check_environment()
                result["status"] = "success"
            elif operation == "get_model_info":
                result = self._get_model_info()
            elif operation == "get_architecture":
                result = self._get_architecture()
            elif operation == "list_alpha_hint_generators":
                result = self._list_alpha_hint_generators()
            elif operation == "key_green_screen":
                result = self._key_green_screen(params)
            elif operation == "batch_key":
                result = self._batch_key(params)
            elif operation == "generate_alpha_hint":
                result = self._generate_alpha_hint(params)
            elif operation == "cleanup_matte":
                result = self._cleanup_matte(params)
            else:
                return {"status": "error", "error": f"Unknown operation: {operation}"}

            result["status"] = result.get("status", "success")
            result["duration_ms"] = (time.time() - start) * 1000
            return result
        except Exception as e:
            logger.error(f"[CorridorKey] {operation} failed: {e}")
            return {
                "status": "error",
                "operation": operation,
                "error": str(e),
                "duration_ms": (time.time() - start) * 1000,
            }

    def _get_model_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        info = {
            "model_name": "CorridorKey v1.0",
            "model_size_mb": "~380",
            "checkpoint_path": str(CK_CHECKPOINT) if CK_CHECKPOINT else None,
            "checkpoint_exists": CK_CHECKPOINT is not None and CK_CHECKPOINT.is_file(),
            "architecture": "Hiera backbone + CNN refiner",
            "input": "RGB frame + optional AlphaHint",
            "output": "Straight foreground (RGB) + Linear alpha (A)",
            "output_formats": ["16-bit EXR", "32-bit EXR", "PNG sequence"],
            "max_resolution": "2048x2048 (dynamic scaling)",
            "screen_colors": ["green", "blue", "auto-detect"],
        }

        # 检查 checkpoint 目录
        ckpt_dir = CK_MODULE / "checkpoints"
        if ckpt_dir.is_dir():
            files = list(ckpt_dir.iterdir())
            info["checkpoint_files"] = [f.name for f in files]
        else:
            info["checkpoint_files"] = []
            info["note"] = "Checkpoint directory not found. Download CorridorKey_v1.0.safetensors (~380MB)"

        return info

    def _get_architecture(self) -> Dict[str, Any]:
        """获取架构详情"""
        arch = {
            "project": "CorridorKey",
            "repo": "nikopueringer/CorridorKey",
            "stars": 13400,
            "license": "CC-BY-NC-SA-4.0",
            "modules": {
                "CorridorKeyModule": {
                    "description": "核心推理引擎",
                    "files": [],
                    "key_files": [
                        "inference_engine.py (519行, 主推理类)",
                        "core/model_transformer.py (Hiera + CNN refiner)",
                        "core/color_utils.py (数字合成数学工具)",
                    ],
                },
                "gvm_core": {
                    "description": "Generative Video Matting (自动 AlphaHint)",
                    "status": "optional",
                },
                "VideoMaMaInferenceModule": {
                    "description": "VideoMaMa (半自动 AlphaHint, 需 mask)",
                    "status": "optional",
                },
                "BiRefNetModule": {
                    "description": "BiRefNet (轻量 AlphaHint)",
                    "status": "optional",
                },
                "backend": {
                    "description": "后端服务 (Gradio UI)",
                },
            },
            "pipeline": {
                "step_1": "输入原始绿幕帧 + 可选 AlphaHint",
                "step_2": "模型预测: 直前景色 (straight FG) + 线性 Alpha",
                "step_3": "自动去溢色 (despill)",
                "step_4": "输出: 16/32-bit EXR (VFX 标准)",
            },
            "source_available": self._source_available,
        }

        # 扫描实际文件
        if self._source_available:
            for mod_name in ["CorridorKeyModule", "gvm_core", "VideoMaMaInferenceModule", "BiRefNetModule"]:
                mod_dir = CK_DIR / mod_name
                if mod_dir.is_dir():
                    py_files = list(mod_dir.rglob("*.py"))
                    if mod_name in arch["modules"]:
                        arch["modules"][mod_name]["files"] = [f.name for f in py_files[:10]]
                        arch["modules"][mod_name]["file_count"] = len(py_files)

        return arch

    def _list_alpha_hint_generators(self) -> Dict[str, Any]:
        """列出可用的 AlphaHint 生成器"""
        generators = [
            {
                "name": "GVM (Generative Video Matting)",
                "module": "gvm_core",
                "auto": True,
                "description": "全自动, 擅长人物, 需额外权重",
                "source": "HuggingFace: geyongtao/gvm",
                "available": (CK_DIR / "gvm_core").is_dir(),
            },
            {
                "name": "VideoMaMa",
                "module": "VideoMaMaInferenceModule",
                "auto": False,
                "description": "需粗略 mask hint, 更强控制力",
                "source": "HuggingFace: SammyLim/VideoMaMa",
                "available": (CK_DIR / "VideoMaMaInferenceModule").is_dir(),
            },
            {
                "name": "BiRefNet",
                "module": "BiRefNetModule",
                "auto": True,
                "description": "轻量级, 快速生成",
                "source": "内置",
                "available": (CK_DIR / "BiRefNetModule").is_dir(),
            },
        ]
        return {
            "generators": generators,
            "count": len(generators),
            "available_count": sum(1 for g in generators if g["available"]),
        }

    def _key_green_screen(self, params: Dict) -> Dict:
        """执行绿幕抠像 (真实推理, 基于实战验证的 backend API)

        已知坑位 (已在实战中验证并规避):
          1. create_engine 默认 device="cpu" 极慢 → 默认 cuda (不可用时回退 cpu)
          2. backend 用相对路径加载 → 必须 os.chdir 到 CorridorKey 目录
          3. process_frame 需要 mask_linear 参数 → 色度键生成初始蒙版
        """
        env = self._env_check
        if not env.get("can_run_inference"):
            blockers = []
            if not env.get("checkpoint_exists"):
                blockers.append("Model checkpoint missing (CorridorKey*.safetensors/.pth ~380MB)")
            if not env.get("torch_ok"):
                blockers.append(f"torch {env.get('torch_version')} 不可用 (实测最低 2.6)")
            if not env.get("vram_ok"):
                blockers.append("GPU VRAM < 6GB")
            return {
                "status": "blocked",
                "blockers": blockers,
                "env_check": env,
                "note": "Run 'check_environment' for details",
            }

        input_path = params.get("input_path", "")
        if not input_path or not Path(input_path).is_file():
            return {"status": "error", "error": f"input_path 不存在: {input_path}"}

        output_path = params.get("output_path") or str(
            Path(input_path).parent / (Path(input_path).stem + "_keyed.png"))
        screen_color = params.get("screen_color", "green")
        device = params.get("device", "cuda" if env.get("cuda_available") else "cpu")

        import numpy as np
        from PIL import Image

        # backend 用相对路径 → 必须切到 CorridorKey 目录, 完成后还原
        prev_cwd = os.getcwd()
        t0 = time.time()
        try:
            os.chdir(CK_DIR)
            if str(CK_DIR) not in sys.path:
                sys.path.insert(0, str(CK_DIR))
            from CorridorKeyModule.backend import create_engine
            engine = create_engine(screen_color=screen_color, device=device)
            t_load = time.time() - t0

            img = Image.open(input_path).convert("RGB")
            frame = np.array(img).astype(np.float32) / 255.0
            r, g, b = frame[:, :, 0], frame[:, :, 1], frame[:, :, 2]
            if screen_color == "blue":
                chroma_diff = b - np.maximum(r, g)
            else:
                chroma_diff = g - np.maximum(r, b)
            mask_linear = np.clip(1.0 - chroma_diff * 3.0, 0, 1).astype(np.float32)

            t1 = time.time()
            result = engine.process_frame(
                (frame * 255).astype(np.uint8),
                mask_linear=mask_linear,
                refiner_scale=1.0,
                input_is_linear=False,
                fg_is_straight=True,
                despill_strength=1.0,
                auto_despeckle=True,
                generate_comp=True,
                post_process_on_gpu=True,
            )
            t_infer = time.time() - t1

            alpha_stats = None
            if isinstance(result, dict):
                alpha = result.get("alpha")
                if alpha is not None:
                    a = np.asarray(alpha).squeeze()
                    alpha_stats = {
                        "min": float(a.min()), "max": float(a.max()),
                        "mean": float(a.mean()),
                        "fg_ratio": float((a > 0.5).sum() / a.size),
                    }
                    alpha_img = Image.fromarray((a * 255).clip(0, 255).astype(np.uint8), mode="L")
                    alpha_img.save(str(Path(output_path).with_suffix(".alpha.png")))
                comp = result.get("comp")
                if comp is not None:
                    comp_arr = np.asarray(comp)
                    mode = "RGBA" if comp_arr.ndim == 3 and comp_arr.shape[2] == 4 else "RGB"
                    Image.fromarray(comp_arr.astype(np.uint8), mode).save(str(output_path))

            return {
                "status": "success",
                "input": input_path,
                "output": output_path,
                "device": device,
                "checkpoint": str(CK_CHECKPOINT),
                "engine_load_sec": round(t_load, 2),
                "inference_sec": round(t_infer, 2),
                "alpha_stats": alpha_stats,
            }
        finally:
            os.chdir(prev_cwd)

    def _batch_key(self, params: Dict) -> Dict:
        """批量抠像"""
        return self._key_green_screen(params)

    def _generate_alpha_hint(self, params: Dict) -> Dict:
        """生成 AlphaHint"""
        generator = params.get("generator", "BiRefNet")
        return {
            "status": "info",
            "generator": generator,
            "note": f"Use {generator} module to generate alpha hint",
        }

    def _cleanup_matte(self, params: Dict) -> Dict:
        """清理 Matte"""
        return {
            "status": "info",
            "note": "Matte cleanup is part of the CorridorKey inference pipeline",
        }

    def summary(self) -> Dict[str, Any]:
        return {
            "source_available": self._source_available,
            "can_run_inference": self._env_check.get("can_run_inference", False),
            "operations": len(self.SUPPORTED_OPERATIONS),
            "torch_version": self._env_check.get("torch_version"),
            "torch_ok": self._env_check.get("torch_ok", False),
            "checkpoint_exists": self._env_check.get("checkpoint_exists", False),
        }
