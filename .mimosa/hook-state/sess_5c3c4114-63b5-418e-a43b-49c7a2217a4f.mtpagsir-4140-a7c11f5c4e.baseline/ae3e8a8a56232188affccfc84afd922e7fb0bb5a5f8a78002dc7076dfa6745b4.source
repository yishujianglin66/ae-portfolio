"""torch_runtime.py — PyTorch 2.8+ CUDA 优化运行时工具

集中管理项目内所有模型推理的公共配置:
  - 设备检测与缓存 (RTX 4060 Laptop 8GB / CUDA 12.1)
  - 混合精度推理上下文 (autocast + no_grad 组合)
  - torch.compile 包装 (inductor 后端, 安全回退)
  - VRAM 监控与缓存清理

覆盖模型: CLIP-laion/cclip/siglip, DINOv2, OWLv2,
          VideoMAE-LoRA, Qwen2-VL, BiRefNet, SAM2, RIFE

用法:
  from core.torch_runtime import get_device, infer_ctx, optimize_model

  device = get_device()
  model = SomeModel().eval().to(device)
  model = optimize_model(model)

  with infer_ctx(device):
      out = model(inputs.to(device))
"""
from __future__ import annotations

import gc
import logging
from contextlib import contextmanager
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

_device_cache: Optional[str] = None
_vram_total: Optional[float] = None


def get_device() -> str:
    """返回最优计算设备, 结果缓存。cuda 不可用时回退 cpu。"""
    global _device_cache
    if _device_cache is not None:
        return _device_cache
    try:
        import torch
        _device_cache = "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        _device_cache = "cpu"
    if _device_cache == "cuda":
        logger.info("torch device: cuda (%s)", _gpu_name())
    else:
        logger.warning("torch device: cpu (CUDA not available)")
    return _device_cache


def _gpu_name() -> str:
    try:
        import torch
        if torch.cuda.is_available():
            return torch.cuda.get_device_name(0)
    except Exception:
        pass
    return "unknown"


def vram_info() -> Tuple[float, float]:
    """返回 (已用GB, 总GB); 无 CUDA 时返回 (0.0, 0.0)。"""
    global _vram_total
    try:
        import torch
        if not torch.cuda.is_available():
            return (0.0, 0.0)
        used = torch.cuda.memory_allocated(0) / 1e9
        if _vram_total is None:
            _vram_total = torch.cuda.get_device_properties(0).total_mem / 1e9
        return (round(used, 2), round(_vram_total, 2))
    except Exception:
        return (0.0, 0.0)


def clear_cache() -> None:
    """清理 CUDA 缓存 + Python GC, 在模型切换或大批量推理后调用。"""
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass


@contextmanager
def infer_ctx(device: Optional[str] = None, dtype: str = "float16"):
    """推理上下文: no_grad + autocast 组合。

    Args:
        device: 计算设备, 默认自动检测
        dtype: 精度模式 — "float16" (CLIP/BiRefNet/默认) 或 "bfloat16" (VLM/大模型)
    """
    import torch

    dev = str(device or get_device())
    dt = torch.bfloat16 if dtype == "bfloat16" else torch.float16

    if dev.startswith("cuda"):
        with torch.no_grad(), torch.autocast(dev, dtype=dt):
            yield
    else:
        with torch.no_grad():
            yield


def optimize_model(model, *, fullgraph: bool = False, mode: str = "reduce-overhead"):
    """torch.compile 包装, 不可用时原样返回。

    PyTorch 2.8+ inductor 后端对 RTX 40 系列有 Triton kernel 优化。
    8GB VRAM 下 mode="reduce-overhead" 比 "max-autotune" 更安全。

    Args:
        model: nn.Module
        fullgraph: 是否要求全图编译 (默认 False, 允许 graph break)
        mode: 编译模式 — "reduce-overhead" / "default" / "max-autotune"
    """
    try:
        import torch
        if not hasattr(torch, "compile"):
            logger.debug("torch.compile not available (<2.0), skipping")
            return model
        compiled = torch.compile(model, fullgraph=fullgraph, mode=mode)
        logger.info("torch.compile applied (%s, fullgraph=%s)", mode, fullgraph)
        return compiled
    except Exception as e:
        logger.warning("torch.compile failed, using eager mode: %s", e)
        return model


def model_summary_mb(model) -> float:
    """估算模型参数量 (MB), 用于 VRAM 预算。"""
    try:
        total_params = sum(p.numel() for p in model.parameters())
        bytes_per_param = 2
        return round(total_params * bytes_per_param / 1e6, 1)
    except Exception:
        return 0.0
