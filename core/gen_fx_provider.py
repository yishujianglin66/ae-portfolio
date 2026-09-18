"""GenFxProvider — 生成式特效素材层（M6）

合成树 gen_fx 图层的素材来源。执行时生成带 alpha 的特效素材，
生成后按 footage 逻辑进 AE（复用 orchestrator 的素材导入）。

双通道:
  1. ComfyUI 本地生成（ai.aigc_generator.ComfyUIAdapter, 127.0.0.1:8188）
     — 需要 ComfyUI 服务 + checkpoint 在跑；产出 diffusion 质感贴图
  2. 程序化降级（cv2 合成透明特效贴图: glow/smoke/spark/light_ray/flow）
     — 零依赖恒可用；产出真实 PNG（AE 可导入渲染），质感为程序化级别

诚实边界: 降级通道不是生成模型 — 它保证链路真实可跑，ComfyUI 一开自动升级质感。
缓存: 按 (kind, prompt, size) 哈希命名，重复请求直接命中已有文件。

用法:
  from core.gen_fx_provider import generate_fx_material
  path = generate_fx_material("爆炸橙色火光", kind="glow", out_dir="output/gen_fx")
"""
from __future__ import annotations

import hashlib
import logging
import sys
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = PROJECT_ROOT / "output" / "gen_fx"

FX_KINDS = ("glow", "smoke", "spark", "light_ray", "flow")


def _cache_key(kind: str, prompt: str, size: int) -> str:
    raw = f"{kind}|{prompt}|{size}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:16]


def _try_comfyui(prompt: str, out_path: Path, size: int) -> bool:
    """ComfyUI 通道：服务在跑才用；失败静默返回 False 走降级"""
    try:
        sys.path.insert(0, str(PROJECT_ROOT))
        from ai.aigc_generator import ComfyUIAdapter
        adapter = ComfyUIAdapter()
        if not adapter.is_available():
            return False
        res = adapter.generate_image(
            f"{prompt}, isolated on transparent background, vfx overlay element, "
            f"high quality, centered composition",
            str(out_path.with_suffix(".png")), size=f"{size}x{size}")
        ok = bool(res.get("success")) and out_path.with_suffix(".png").exists()
        if ok:
            logger.info("[GenFx] ComfyUI 生成: %s", out_path.name)
        return ok
    except Exception as e:  # noqa: BLE001 — ComfyUI 不可用属预期, 降级
        logger.debug("[GenFx] ComfyUI 通道跳过: %s", e)
        return False


# ── 程序化降级：真实透明 PNG 特效贴图（cv2 合成） ────────────────────

def _radial_glow(size: int, color: tuple, hardness: float = 0.35) -> np.ndarray:
    """径向辉光贴图（BGR float 0-1, 自带 alpha）"""
    yy, xx = np.mgrid[0:size, 0:size]
    cx = cy = size / 2
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / (size / 2)
    alpha = np.clip(1 - dist, 0, 1) ** (1 / hardness)
    alpha = alpha / alpha.max() if alpha.max() > 0 else alpha
    img = np.zeros((size, size, 4), np.float32)
    img[..., 0], img[..., 1], img[..., 2] = (c / 255 for c in color)
    img[..., 3] = alpha
    return img


def _smoke(size: int, color: tuple, seed: int = 7) -> np.ndarray:
    """云雾贴图：多层模糊噪声 × 径向衰减"""
    rng = np.random.default_rng(seed)
    acc = np.zeros((size, size), np.float32)
    for scale, weight in ((size // 4, 1.0), (size // 8, 0.6), (size // 16, 0.35)):
        n = rng.random((max(scale, 4), max(scale, 4))).astype(np.float32)
        n = cv2.resize(n, (size, size), interpolation=cv2.INTER_CUBIC)
        acc += weight * n
    acc /= acc.max()
    acc = cv2.GaussianBlur(acc, (0, 0), size / 24)
    yy, xx = np.mgrid[0:size, 0:size]
    dist = np.sqrt((xx - size / 2) ** 2 + (yy - size / 2) ** 2) / (size / 2)
    alpha = np.clip(acc - 0.25, 0, 1) * np.clip(1.25 - dist, 0, 1)
    alpha = alpha / alpha.max() if alpha.max() > 0 else alpha
    img = np.zeros((size, size, 4), np.float32)
    img[..., 0], img[..., 1], img[..., 2] = (c / 255 for c in color)
    img[..., 3] = alpha * 0.85
    return img


def _sparks(size: int, color: tuple, seed: int = 3, n_pts: int = 140) -> np.ndarray:
    """火花贴图：点群 + 每点微辉光"""
    rng = np.random.default_rng(seed)
    alpha = np.zeros((size, size), np.float32)
    for _ in range(n_pts):
        r = rng.random() * size * 0.42
        theta = rng.random() * 2 * np.pi
        x = int(size / 2 + r * np.cos(theta))
        y = int(size / 2 + r * 0.6 * np.sin(theta))   # 稍扁的爆发分布
        rad = int(rng.integers(1, 4))
        bright = float(rng.uniform(0.5, 1.0))
        cv2.circle(alpha, (x, y), rad, bright, -1)
    alpha = cv2.GaussianBlur(alpha, (0, 0), 1.2)
    alpha = np.clip(alpha * 1.4, 0, 1)
    img = np.zeros((size, size, 4), np.float32)
    img[..., 0], img[..., 1], img[..., 2] = (c / 255 for c in color)
    img[..., 3] = alpha
    return img


def _light_ray(size: int, color: tuple) -> np.ndarray:
    """光束贴图：从上方的扇形光"""
    yy, xx = np.mgrid[0:size, 0:size]
    spread = np.abs(xx - size / 2) / (size / 2)
    vertical = np.clip(1 - yy / size, 0, 1)          # 上强下弱
    alpha = np.clip((0.55 - spread) * 2.2, 0, 1) * vertical
    alpha = cv2.GaussianBlur(alpha, (0, 0), size / 40)
    alpha = alpha / alpha.max() if alpha.max() > 0 else alpha
    img = np.zeros((size, size, 4), np.float32)
    img[..., 0], img[..., 1], img[..., 2] = (c / 255 for c in color)
    img[..., 3] = alpha * 0.9
    return img


def _flow(size: int, color: tuple, seed: int = 11) -> np.ndarray:
    """流体拖尾贴图：涡旋变形噪声"""
    rng = np.random.default_rng(seed)
    base = rng.random((size // 8, size // 8)).astype(np.float32)
    base = cv2.resize(base, (size, size), interpolation=cv2.INTER_CUBIC)
    # 涡旋位移
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    ang = np.arctan2(yy - size / 2, xx - size / 2) + base * 2.5
    rad = np.sqrt((xx - size / 2) ** 2 + (yy - size / 2) ** 2)
    mx = (size / 2 + np.cos(ang) * rad).astype(np.float32)
    my = (size / 2 + np.sin(ang) * rad).astype(np.float32)
    warp = cv2.remap(base, mx, my, cv2.INTER_LINEAR)
    warp = cv2.GaussianBlur(warp, (0, 0), size / 30)
    alpha = np.clip(warp - 0.3, 0, 1)
    alpha = alpha / alpha.max() if alpha.max() > 0 else alpha
    img = np.zeros((size, size, 4), np.float32)
    img[..., 0], img[..., 1], img[..., 2] = (c / 255 for c in color)
    img[..., 3] = alpha * 0.8
    return img


# prompt → 主色启发（降级通道的简单语义映射；ComfyUI 通道由模型理解 prompt）
_COLOR_HINTS = {
    "橙": (255, 140, 30), "红": (255, 60, 40), "金": (255, 200, 80),
    "蓝": (60, 150, 255), "青": (0, 220, 220), "紫": (170, 80, 255),
    "绿": (80, 230, 120), "白": (235, 235, 235), "冷": (150, 200, 255),
    "暖": (255, 170, 90), "火": (255, 120, 30), "霓虹": (255, 60, 200),
}


def _pick_color(prompt: str, default=(255, 170, 60)) -> tuple:
    for key, c in _COLOR_HINTS.items():
        if key in prompt:
            return c
    return default


_KIND_RENDERERS = {
    "glow": _radial_glow,
    "smoke": _smoke,
    "spark": _sparks,
    "light_ray": _light_ray,
    "flow": _flow,
}


def _render_procedural(kind: str, prompt: str, size: int, out_path: Path) -> None:
    color = _pick_color(prompt)
    img = _KIND_RENDERERS[kind](size, color)
    bgra = (np.clip(img, 0, 1) * 255).astype(np.uint8)
    cv2.imwrite(str(out_path), bgra)   # BGRA 透明 PNG


def generate_fx_material(prompt: str, kind: str = "glow",
                         out_dir: str | None = None,
                         size: int = 1024,
                         prefer: str = "auto") -> str:
    """生成特效素材，返回透明 PNG 绝对路径。

    prefer: "auto"(ComfyUI 可用则用) | "comfyui" | "procedural"
    """
    if kind not in FX_KINDS:
        raise ValueError(f"kind {kind} 不在 {FX_KINDS}")
    out = Path(out_dir) if out_dir else DEFAULT_OUT
    out.mkdir(parents=True, exist_ok=True)
    name = f"fx_{kind}_{_cache_key(kind, prompt, size)}.png"
    out_path = out / name
    if out_path.exists():                      # 缓存命中
        return str(out_path.resolve())
    if prefer in ("auto", "comfyui") and _try_comfyui(prompt, out_path, size):
        return str(out_path.with_suffix(".png").resolve())
    _render_procedural(kind, prompt, size, out_path)
    return str(out_path.resolve())


def resolve_gen_fx_layers(tree) -> int:
    """合成树预备：把所有 gen_fx 图层生成素材并把路径写回 content.path。

    在 orchestrator.execute 前调用；返回生成（含缓存命中）的层数。
    """
    n = 0
    for layer in tree.layers:
        if layer.type != "gen_fx":
            continue
        prompt = str(layer.content.get("prompt", "特效"))
        kind = str(layer.content.get("kind", "glow"))
        prefer = str(layer.content.get("engine", "auto"))
        path = generate_fx_material(prompt, kind, prefer=prefer)
        layer.content["path"] = path           # 供 footage 导入复用
        n += 1
    return n


__all__ = ["generate_fx_material", "resolve_gen_fx_layers", "FX_KINDS"]
