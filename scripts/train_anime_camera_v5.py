#!/usr/bin/env python3
"""
v5.1 运镜分类重训 — VideoMAE v2 全参微调 + SOTA P0 修复 (2026-08-19)

v5.1 P0 修复 (基于 arXiv + VideoMAEv2 官方 SOTA):
  1. 🔴 禁止水平翻转: pan_left/pan_right 被翻转会破坏标签 (arXiv:2510.14713 CMC)
  2. 🟡 drop_path 0.1→0.2: 运镜分类任务易过拟合
  3. 🟡 Repeated Augmentation (num_sample=2): 官方复现 K400 87.4% 关键技巧
  4. 🟡 EMA 动态衰减: min(decay, (1+step)/(10+step)) (arXiv:2307.13813)
  5. 🟡 换 VideoMAEv2 ViT-B 底模 (K710 预训练, K400 86.6% 比 v1 高 1.6%)

验收: meta.json val_acc >= 0.70 (保底) / >= 0.75 (达标) / >= 0.80 (理想)
"""
from __future__ import annotations

import argparse
import json
import logging
import random
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.torch_runtime import get_device, infer_ctx  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("v5_train")

# ─── 模型与数据路径 ───
MODEL_DIR = r"D:\AE-Data\Models\VideoMAE-MovieShots\movement"
SHOTS_DIR = r"D:\AE-Data\AnimeCamera\shots"
NUM_FRAMES = 16
IMG_SIZE = 224

# ─── 六类标签 (与 v3c/v4 一致, 不变) ───
SIX_MAP = {
    "static": "static",
    "pan_left": "pan_left", "pan_right": "pan_right",
    "tilt_up": "tilt_orbit", "tilt_down": "tilt_orbit", "orbit": "tilt_orbit",
    "zoom_in": "push_in", "push": "push_in",
    "zoom_out": "pull_out", "zoom_back": "pull_out",
    "complex": None,
}
SIX_LABELS = ["static", "pan_left", "pan_right", "tilt_orbit", "push_in", "pull_out"]
REVERSE_PAIR = {
    "pan_left": "pan_right", "pan_right": "pan_left",
    "tilt_up": "tilt_down", "tilt_down": "tilt_up",
    "zoom_in": "zoom_out", "zoom_out": "zoom_in",
    "push": "zoom_back", "zoom_back": "push",
}


def load_trainable(labels_path: str, min_conf: float = 0.7,
                   time_reverse: bool = True,
                   data_root: str = "") -> list[dict[str, Any]]:
    """加载 VLM 标注, 六类映射, 过滤 complex/低置信/缺失文件。

    支持合并多个 jsonl (v3 合并格式: 用换行分隔的多文件路径)。
    """
    # 支持多文件合并 (vlm_labels_v3 = v1+v2+本地新标的合并)
    label_files = [p.strip() for p in labels_path.split("|") if p.strip()]
    rows: list[dict[str, Any]] = []
    for lf in label_files:
        p = Path(lf)
        if not p.exists():
            logger.warning("标签文件不存在, 跳过: %s", p)
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    logger.info("标签文件加载: %d 行 (来自 %d 文件)", len(rows), len(label_files))

    # 去重 (同一 shot_id 可能出现在多个文件, 保留最新的)
    seen: dict[str, dict[str, Any]] = {}
    for r in rows:
        sid = r.get("shot_id", "")
        if sid:
            seen[sid] = r
    rows = list(seen.values())
    logger.info("去重后: %d 行", len(rows))

    # 跨机 clip_path 重映射 (统一处理 Windows 反斜杠)
    def _basename_from_cross_platform(cp: str) -> str:
        # 兼容 Windows 路径在 Linux 上解析: D:\\foo\\bar.mp4 -> bar.mp4
        return Path(cp.replace("\\", "/")).name

    if data_root:
        for r in rows:
            cp = r.get("clip_path", "")
            if cp:
                r["clip_path"] = str(Path(data_root) / _basename_from_cross_platform(cp))

    out: list[dict[str, Any]] = []
    skipped = {"complex": 0, "low_conf": 0, "missing_clip": 0, "bad_dir": 0}
    n_reversed = 0
    for r in rows:
        d = r.get("movement_label", "")
        if d not in SIX_MAP:
            skipped["bad_dir"] += 1
            continue
        label = SIX_MAP[d]
        if label is None:
            skipped["complex"] += 1
            continue
        if float(r.get("confidence", 0)) < min_conf:
            skipped["low_conf"] += 1
            continue
        clip = r.get("clip_path", "")
        if not clip or not Path(clip).exists():
            basename = _basename_from_cross_platform(clip) if clip else ""
            alt = Path(SHOTS_DIR if not data_root else data_root) / basename
            if alt.exists():
                clip = str(alt)
            else:
                skipped["missing_clip"] += 1
                continue
        out.append({"clip": clip, "label": label, "direction": d,
                    "anime": r.get("anime", ""), "reverse": False})
        if time_reverse and d in REVERSE_PAIR:
            mirrored_fine = REVERSE_PAIR[d]
            mirrored = SIX_MAP[mirrored_fine]
            if mirrored is not None:
                out.append({"clip": clip, "label": mirrored, "direction": mirrored_fine,
                            "anime": r.get("anime", ""), "reverse": True})
                n_reversed += 1

    logger.info("可训练样本: %d (含反转增强 %d; 过滤 %s)",
                len(out), n_reversed, skipped)
    return out


def _set_drop_path(model, drop_path_rate: float) -> None:
    """为 ViT 的 Stochastic Depth 配置 drop_path rate (官方 ViT-B=0.1)。

    VideoMAE 的 transformers 实现中, drop_path 通常在 config 里设
    `drop_path_rate`。若已加载, 通过遍历 module 找 DropPath 实例并设置。

    v5.2: 支持 VideoMAEv2 自带的 DropPath 类 (非 timm.layers.DropPath,
    但也有 .drop_prob 属性)。
    """
    # 尝试通过 config 重设 (transformers VideoMAE 支持)
    if hasattr(model, "config") and hasattr(model.config, "drop_path_rate"):
        model.config.drop_path_rate = drop_path_rate
    # 兼容: 任何有 drop_prob 属性的模块都算 DropPath (v1 timm 版 & v2 自定义版)
    def _is_droppath(m):
        return hasattr(m, "drop_prob") and isinstance(getattr(m, "drop_prob", None), (int, float))
    modules = list(model.modules())
    n_total_depth = sum(1 for _ in modules if _is_droppath(_))
    n_set = 0
    for m in modules:
        if _is_droppath(m):
            # 按 DropPath 自身序号线性递增 (0 → drop_path_rate),
            # 不能使用模型模块全局索引 (i), 否则 rate 会超过 1 → bernoulli 崩溃
            rate = drop_path_rate * (n_set + 1) / max(1, n_total_depth)
            m.drop_prob = rate
            n_set += 1
    if n_set == 0 and n_total_depth == 0:
        logger.warning("DropPath 未在模型中找到 (transformers VideoMAE 可能不暴露 DropPath module, "
                      "改用 model.config.drop_path_rate=%.2f)", drop_path_rate)


def _build_layer_decay_param_groups(model, lr: float, weight_decay: float,
                                    layer_decay: float) -> list:
    """ViT 分层学习率 (官方 ViT-B=0.75; layer_decay=1 等价普通统一 lr)。

    浅层 (encoder 早 block) lr 小, 深层 (分类头) lr 大。
    VideoMAE v1 参数名: videomae.encoder.layer.{i}...
    VideoMAEv2 参数名: model.blocks.{i}...
    两者正则都支持。
    """
    if layer_decay <= 0 or layer_decay >= 1:
        return [{"params": [p for p in model.parameters() if p.requires_grad],
                 "lr": lr, "weight_decay": weight_decay}]

    # 分组: 按参数名中的 layer.{i} / blocks.{i} 提取深度
    layer_groups: dict[int, list] = {}
    no_decay_groups = {"layernorm": [], "bias": []}
    other_params = []

    for name, p in model.named_parameters():
        if not p.requires_grad:
            continue
        # LayerNorm / bias 不加 weight_decay
        if "layernorm" in name.lower() or "layer_norm" in name.lower() or "norm" in name.lower():
            no_decay_groups["layernorm"].append(p)
            continue
        if name.endswith("bias"):
            no_decay_groups["bias"].append(p)
            continue
        # 提取深度: v1 = layer.{i}, v2 = blocks.{i}
        import re
        m = re.search(r"(?:layer|blocks)\.(\d+)", name)
        if m:
            depth = int(m.group(1))
            layer_groups.setdefault(depth, []).append(p)
        elif "classifier" in name or "head" in name:
            # 分类头 lr 不衰减 (depth=最大+1)
            max_depth = max(layer_groups.keys()) if layer_groups else 12
            layer_groups.setdefault(max_depth + 1, []).append(p)
        else:
            other_params.append(p)

    # 构造 param groups
    max_depth = max(layer_groups.keys()) if layer_groups else 12
    param_groups = []
    for depth in sorted(layer_groups.keys()):
        scale = (layer_decay ** (max_depth - depth + 1))
        param_groups.append({
            "params": layer_groups[depth],
            "lr": lr * scale,
            "weight_decay": weight_decay,
        })
        logger.info("  layer %d: lr=%.6e (%.2fx) params=%d",
                    depth, lr * scale, scale, len(layer_groups[depth]))
    if other_params:
        param_groups.append({"params": other_params, "lr": lr, "weight_decay": weight_decay})
    # LayerNorm/bias 不加 weight_decay
    if no_decay_groups["layernorm"]:
        param_groups.append({"params": no_decay_groups["layernorm"],
                             "lr": lr, "weight_decay": 0.0})
    if no_decay_groups["bias"]:
        param_groups.append({"params": no_decay_groups["bias"],
                             "lr": lr, "weight_decay": 0.0})
    return param_groups


class ClipDataset(torch.utils.data.Dataset):
    """运镜分类数据集 — v5.1 修复版

    🔴 P0 修复: 禁止任何水平翻转/旋转 (pan_left/pan_right 标签会被破坏)
    🟡 支持 Repeated Augmentation: 同视频采样 num_sample 个不同增强副本
    """

    def __init__(self, samples: list[dict[str, Any]],
                 label_to_idx: dict[str, int],
                 num_sample: int = 2,
                 is_train: bool = True):
        self.samples = samples
        self.label_to_idx = label_to_idx
        self.num_sample = num_sample
        self.is_train = is_train

    def __len__(self) -> int:
        return len(self.samples) * self.num_sample

    def _load_frames(self, clip: str, copy_id: int = 0) -> np.ndarray | None:
        from decord import VideoReader, cpu
        try:
            vr = VideoReader(clip, ctx=cpu(0), width=IMG_SIZE, height=IMG_SIZE)
        except Exception:  # noqa: BLE001
            return None
        n = len(vr)
        if n < 2:
            return None
        if n <= NUM_FRAMES:
            idxs = list(range(n))
        else:
            # Repeated Aug: 不同 copy_id 用不同起始偏移, 模拟时序抖动 (jitter sampling)
            total_avail = n - NUM_FRAMES
            offset = (copy_id * max(1, total_avail // max(1, self.num_sample))) % max(1, total_avail)
            step = (n - 1 - offset) / (NUM_FRAMES - 1)
            idxs = [min(n - 1, offset + round(i * step)) for i in range(NUM_FRAMES)]
        try:
            return vr.get_batch(idxs).asnumpy()
        except Exception:  # noqa: BLE001
            return None

    def __getitem__(self, idx: int) -> dict[str, Any]:
        sample_idx = idx // self.num_sample
        copy_id = idx % self.num_sample
        s = self.samples[sample_idx]
        frames = self._load_frames(s["clip"], copy_id=copy_id)
        if frames is None:
            alt = self.samples[(sample_idx + 1) % len(self.samples)]
            frames = self._load_frames(alt["clip"], copy_id=copy_id)
            s = alt
        frames = frames.astype(np.float32).transpose(0, 3, 1, 2)
        if s.get("reverse"):
            frames = frames[::-1].copy()
        if frames.shape[0] < NUM_FRAMES:
            rep = (NUM_FRAMES + frames.shape[0] - 1) // frames.shape[0]
            frames = np.tile(frames, (rep, 1, 1, 1))[:NUM_FRAMES]
        import torch
        from torchvision.transforms import v2

        # 🔴 P0 强制安全: 运镜分类严禁水平翻转/旋转
        # 只做: Resize + 亮度/对比度轻微抖动 + 裁剪抖动 (不改变运动方向语义)
        frames_tensor = torch.from_numpy(frames)
        frames_tensor = v2.Resize((IMG_SIZE + 16, IMG_SIZE + 16))(frames_tensor)

        if self.is_train:
            # 随机裁剪 + 亮度/对比度/饱和度抖动 (不影响运动方向)
            frames_tensor = v2.RandomCrop((IMG_SIZE, IMG_SIZE))(frames_tensor)
            frames_tensor = v2.ColorJitter(
                brightness=0.2,
                contrast=0.2,
                saturation=0.15,
                hue=0.0,  # hue 会改变颜色语义, 禁用
            )(frames_tensor)
        else:
            # 验证/测试: 中心裁剪
            frames_tensor = v2.CenterCrop((IMG_SIZE, IMG_SIZE))(frames_tensor)

        frames_tensor = frames_tensor.clamp(0, 255).to(torch.uint8)
        return {"pixel_values": frames_tensor, "labels": self.label_to_idx[s["label"]]}


def _collate_batch(batch: list[dict[str, Any]]) -> dict[str, Any]:
    """模块级 collate (Windows spawn 可 pickle)。

    v5 改进: label smoothing 由 loss_fn 处理, 这里只做归一化。
    """
    import torch
    videos = torch.stack([b["pixel_values"] for b in batch])
    videos = videos.float() / 255.0
    mean = torch.tensor([0.485, 0.456, 0.406], dtype=torch.float32).view(1, 1, 3, 1, 1)
    std = torch.tensor([0.229, 0.224, 0.225], dtype=torch.float32).view(1, 1, 3, 1, 1)
    videos = (videos - mean) / std
    lab = torch.tensor([b["labels"] for b in batch], dtype=torch.long)
    return {"pixel_values": videos, "labels": lab}


def _mixup_batch(batch: dict[str, Any], num_classes: int, alpha: float = 0.2):
    """Mixup 增强 (运镜类间语义重叠, mixup 提升泛化)。

    v4 在 60% 饱和, 部分原因是过拟合到训练分布; mixup 平滑决策边界。
    返回 soft target (与 timm SoftTargetCrossEntropy 对齐)。
    """
    import torch
    if alpha <= 0:
        return batch, None
    lam = float(np.random.beta(alpha, alpha))
    perm = torch.randperm(batch["pixel_values"].size(0), device=batch["pixel_values"].device)
    mixed_px = lam * batch["pixel_values"] + (1 - lam) * batch["pixel_values"][perm]
    batch["pixel_values"] = mixed_px
    labels = batch["labels"]
    soft = torch.zeros(labels.size(0), num_classes, device=labels.device)
    soft.scatter_(1, labels.unsqueeze(1), lam)
    soft.scatter_(1, labels[perm].unsqueeze(1), 1.0 - lam)
    return batch, soft


class EMA:
    """Exponential Moving Average shadow 权重 (arXiv:2307.13813 + arXiv:2510.18213).

    每 step update; 评估/保存时 apply_shadow 临时换入 shadow, 完成后 restore.
    仅 shadow 可训练参数 (BN running stats 等 buffer 保留模型当前值).

    v5.1 修复: 🔴 添加动态衰减 (Dynamic Decay)
      - 训练初期: 让 EMA 快速追随模型 (decay 较小)
      - 训练后期: 趋近于静态 decay
      - 公式: actual_decay = min(static_decay, (1 + num_updates) / (10 + num_updates))
    """

    def __init__(self, model, decay: float = 0.9999) -> None:
        import torch
        self.decay = decay
        self._num_updates = 0
        self.shadow: dict = {}
        self.backup: dict = {}
        for n, p in model.named_parameters():
            if p.requires_grad:
                self.shadow[n] = p.detach().clone()

    @torch.no_grad()
    def update(self, model) -> None:
        self._num_updates += 1
        # 动态衰减: 初期小, 后期趋近 static decay
        warmup_decay = (1.0 + self._num_updates) / (10.0 + self._num_updates)
        d = min(self.decay, warmup_decay)
        for n, p in model.named_parameters():
            if n in self.shadow:
                self.shadow[n].mul_(d).add_(p.detach(), alpha=1.0 - d)

    def apply_shadow(self, model) -> None:
        """临时把可训练参数替换为 shadow (BN buffer 不动)."""
        self.backup = {}
        for n, p in model.named_parameters():
            if n in self.shadow:
                self.backup[n] = p.detach().clone()
                p.data.copy_(self.shadow[n])

    def restore(self, model) -> None:
        for n, p in model.named_parameters():
            if n in self.backup:
                p.data.copy_(self.backup[n])
        self.backup = {}


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="v5 VideoMAE 全参微调 (扩数据集)")
    parser.add_argument("--labels", default=r"D:\AE-Data\AnimeCamera\vlm_labels_v3.jsonl",
                        help="标签 jsonl (支持 | 分隔多文件合并)")
    parser.add_argument("--data-root", default="",
                        help="clips 重映射目录 (跨机训练包)")
    parser.add_argument("--model-dir", default=MODEL_DIR,
                        help="底座模型目录 (从底模重训时用)")
    parser.add_argument("--resume-from", default="",
                        help="从已有模型续训 (warm start, lr 自动降低)")
    parser.add_argument("--out", default=str(PROJECT_ROOT / "models" / "output" / "anime_camera_lora_v5"))
    parser.add_argument("--epochs", type=int, default=25)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--num-workers", type=int, default=4,
                        help="数据加载进程数 (vGPU-32GB 推荐 8, 本地 0)")
    parser.add_argument("--lr", type=float, default=3e-5,
                        help="学习率 (resume-from 时自动降到 1e-5)")
    parser.add_argument("--limit", type=int, default=0,
                        help="最多用 N 样本 (0=全部, 冒烟用 200)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--weight-cap", type=float, default=5.0)
    parser.add_argument("--no-time-reverse", dest="time_reverse", action="store_false")
    # === SOTA recipe (VideoMAE 官方 FINETUNE.md) ===
    parser.add_argument("--layer-decay", type=float, default=0.75,
                        help="ViT 微调分层学习率 (官方 ViT-B=0.75; 0=关闭)")
    parser.add_argument("--drop-path", type=float, default=0.2,
                        help="Drop Path Rate (官方 ViT-B=0.1; 运镜分类易过拟合建议 0.2)")
    parser.add_argument("--warmup-epochs", type=int, default=5,
                        help="Warmup epochs (官方 5)")
    parser.add_argument("--weight-decay", type=float, default=0.05,
                        help="Weight decay (官方 0.05, 旧版 1e-4 异常偏低 500x)")
    parser.add_argument("--mixup", type=float, default=0.2,
                        help="Mixup alpha (v5.3: 0.8 过强会稀释少数类, 改 0.2 轻mixup; 0=关闭)")
    parser.add_argument("--cutmix", type=float, default=0.0,
                        help="CutMix alpha (v5.3: 默认禁用! 拼贴画面破坏运镜运动方向语义)")
    parser.add_argument("--label-smoothing", type=float, default=0.1,
                        help="标签平滑 (SoftTargetCE 配合 mixup)")
    parser.add_argument("--amp", action="store_true", help="混合精度")
    parser.add_argument("--early-stop", type=int, default=5,
                        help="早停耐心 (v5 放宽到 5)")
    parser.add_argument("--grad-checkpoint", action="store_true",
                        help="梯度检查点 (小显存卡用)")
    parser.add_argument("--tta-clips", type=int, default=5,
                        help="Test-Time Augmentation clip 数 (官方 5; 1=关闭)")
    parser.add_argument("--tta-crops", type=int, default=3,
                        help="Test-Time Augmentation crop 数 (官方 3; 1=关闭)")
    parser.add_argument("--ema-decay", type=float, default=0.9999,
                        help="EMA decay (0=关闭)")
    parser.add_argument("--no-ema", action="store_true",
                        help="关闭 EMA 平滑权重")
    parser.add_argument("--num-sample", type=int, default=2,
                        help="Repeated Augmentation: 同视频采样 N 个增强副本 (官方 2, 复现 K400 87.4% 关键)")
    parser.add_argument("--no-flip-safe", action="store_true",
                        help="启用前请不要传: 本脚本已强制禁用水平翻转 (运镜标签会被翻转破坏)")
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)
    import torch
    torch.manual_seed(args.seed)
    device = get_device()
    logger.info("device=%s", device)

    # 1. 数据
    samples = load_trainable(args.labels, time_reverse=args.time_reverse,
                            data_root=args.data_root)
    if args.limit > 0:
        samples = samples[:args.limit]
    if len(samples) < 50:
        logger.error("训练样本不足 (%d), 先跑完本地 VLM 标注", len(samples))
        return 1

    # 2. 模型加载 (三模式: transformers VideoMAE v1 / VideoMAEv2 自定义代码)
    # v5.2: VideoMAEv2 (OpenGVLab 自定义架构) 走独立分支 —— 通过加载 modeling_videomaev2.py 源码
    import json as _json
    import os as _os

    def _is_videomaev2(path_or_id: str) -> bool:
        """识别是否为 VideoMAEv2 目录/权重: config.json 的 model_type == 'VideoMAEv2_Base'"""
        if not _os.path.isdir(path_or_id):
            return False
        cfg_path = _os.path.join(path_or_id, "config.json")
        if not _os.path.isfile(cfg_path):
            return False
        try:
            cfg = _json.loads(open(cfg_path, "r", encoding="utf-8").read())
            return str(cfg.get("model_type", "")) == "VideoMAEv2_Base"
        except Exception:
            return False

    def _load_videomaev2_custom(model_dir: str,
                                 num_classes: int,
                                 drop_path_rate: float,
                                 grad_checkpoint: bool):
        """v5.2 新增: 从本地目录 (含 modeling_videomaev2.py + model.safetensors)
        加载 VideoMAEv2, 并替换 head 为 num_classes。

        为什么不用 AutoModel.from_pretrained(trust_remote_code=True):
          - 老版本 transformers 要求 PreTrainedModel 有 all_tied_weights_keys
          - VideoMAEv2 的包装类写的不够完整, 导致加载尾阶段炸
        所以这里直接把两个文件当作普通源码 exec 进来, 然后手动 safetensors.load_state_dict。
        """
        import pathlib as _pl
        import sys as _sys
        import types as _types

        from safetensors.torch import load_file as _load_sf

        mdl_path = _pl.Path(model_dir)
        assert mdl_path.is_dir(), f"model_dir 不存在: {model_dir}"

        # easydict fallback (云端经常没装 easydict, FakeEasyDict 行为兼容足够)
        class FakeEasyDict(dict):
            def __getattr__(self, k):
                try: return self[k]
                except KeyError: raise AttributeError(k)
            def __setattr__(self, k, v): self[k] = v
            def __deepcopy__(self, memo=None):
                cp = __import__('copy').deepcopy
                return FakeEasyDict({kk: cp(vv, memo) for kk, vv in self.items()})
        if 'easydict' not in _sys.modules:
            _sys.modules['easydict'] = _types.ModuleType('easydict')
        if not hasattr(_sys.modules['easydict'], 'EasyDict'):
            _sys.modules['easydict'].EasyDict = FakeEasyDict

        def _exec_mod(name: str, src: str, extra_g: dict | None = None):
            g = dict(globals())
            if extra_g: g.update(extra_g)
            g['__name__'] = name
            g['__file__'] = str(mdl_path / f"{name}.py")
            g['__package__'] = None
            code = compile(src, g['__file__'], 'exec')
            mod = _types.ModuleType(name)
            _sys.modules[name] = mod
            exec(code, g)
            for k, v in g.items():
                if k.startswith('_') and k not in ('__name__','__file__','__package__'):
                    continue
                setattr(mod, k, v)
            return mod

        # 1) modeling_config
        cfg_src = mdl_path.joinpath("modeling_config.py").read_text(encoding="utf-8")
        cfg_mod = _exec_mod("modeling_config", cfg_src)
        VideoMAEv2Config = cfg_mod.VideoMAEv2Config

        # 2) modeling_videomaev2 — 修复相对 import
        v2_src = mdl_path.joinpath("modeling_videomaev2.py").read_text(encoding="utf-8")
        v2_src_fixed = v2_src.replace(
            "from .modeling_config import VideoMAEv2Config",
            "from modeling_config import VideoMAEv2Config",
        )
        v2_mod = _exec_mod("modeling_videomaev2", v2_src_fixed,
                           extra_g={"VideoMAEv2Config": VideoMAEv2Config})
        VideoMAEv2 = v2_mod.VideoMAEv2

        # 3) 实例化 —— 关键: drop_path_rate 在实例化前写进 model_config (否则 dpr=[]，DropPath 不会被构造)
        cfg = VideoMAEv2Config.from_pretrained(str(model_dir))
        if isinstance(cfg.model_config, dict):
            cfg.model_config["drop_path_rate"] = float(drop_path_rate)
            cfg.model_config["with_cp"] = bool(grad_checkpoint)
        else:
            try:
                cfg.model_config.drop_path_rate = float(drop_path_rate)
                cfg.model_config.with_cp = bool(grad_checkpoint)
            except Exception:
                pass
        base = VideoMAEv2(cfg)

        # 5) 先替换分类头再加载权重 — 🔴 P0 修复 (2026-08-21)
        # 原顺序: load(丢弃 head) → reset(随机头) 导致 resume/推理时训练好的 head 丢失,
        # 全部推理结果等同随机头 (混淆矩阵均匀≈1/6), 诊断结论全部作废。
        backbone = base.model if hasattr(base, 'model') else base
        if hasattr(backbone, "reset_classifier"):
            backbone.reset_classifier(num_classes)
        else:
            backbone.head = torch.nn.Linear(backbone.embed_dim, num_classes)
            backbone.num_classes = num_classes
        logger.info("VideoMAEv2 分类头: 先 reset 为 %d 类再加载权重", num_classes)

        # 4) 加载 safetensors / pytorch_model.bin
        sf_path = mdl_path / "model.safetensors"
        bin_path = mdl_path / "pytorch_model.bin"
        if sf_path.exists():
            st = _load_sf(str(sf_path))
            info = base.load_state_dict(st, strict=False)
        elif bin_path.exists():
            import torch as _torch
            st = _torch.load(str(bin_path), map_location="cpu")
            info = base.load_state_dict(st, strict=False)
        else:
            raise FileNotFoundError(f"VideoMAEv2 模型权重未找到 (需要 model.safetensors 或 pytorch_model.bin): {model_dir}")
        logger.info("VideoMAEv2 权重加载: missing=%d, unexpected=%d",
                     len(info.missing_keys), len(info.unexpected_keys))
        if "head.weight" in " ".join(info.unexpected_keys):
            logger.warning("分类头权重仍未被加载 (unexpected 含 head), 检查 reset_classifier 键名")

        # 6) 包装一下, 让 forward(pixel_values=...) 返回带 .logits 的对象 (与 v1 的 ModelOutput 行为一致)
        class _V2Output:
            __slots__ = ("logits",)
            def __init__(self, logits):
                self.logits = logits

        class _V2ModelWrapper(torch.nn.Module):
            """VideoMAEv2 forward 输出是 raw Tensor。这里包装成 HF ModelOutput 风格。

            注意: VideoMAEv2(包装里的 self.inner) 本身就是 torch.nn.Module，
            并且我们把它当作子模块赋给了 self.inner，
            所以 parameters() / to() / state_dict() / train() / modules() / named_parameters()
            全部自动由 nn.Module 递归处理，无需手动转发。
            """
            def __init__(self, inner):
                super().__init__()
                self.inner = inner
                self.config = getattr(inner, "config", None)

            def forward(self, pixel_values=None, **kwargs):
                # VideoMAEv2(pixel_values) 直接返回 Tensor (B, num_classes)
                if pixel_values is None:
                    for k in ("pixel_values", "inputs", "videos"):
                        if k in kwargs:
                            pixel_values = kwargs[k]
                            break
                # VideoMAEv2 的 patch_embed 是 Conv3d, 期望输入 [B, C, T, H, W] (BCTHW)
                # 而 _collate_batch 输出的是 [B, T, C, H, W] (BTCHW) → 需要 permute
                if pixel_values.dim() == 5 and pixel_values.shape[2] == 3:
                    pixel_values = pixel_values.permute(0, 2, 1, 3, 4)  # BTCHW → BCTHW
                logits = self.inner(pixel_values)
                return _V2Output(logits=logits)

            def save_pretrained(self, out_dir, **kw):
                # 保存: 优先 safetensors + config.json (标准 HF 格式)
                import json as _json
                import pathlib as _pl
                out_p = _pl.Path(out_dir)
                out_p.mkdir(parents=True, exist_ok=True)
                # config
                try:
                    if hasattr(self.config, "to_dict"):
                        (out_p / "config.json").write_text(
                            _json.dumps(self.config.to_dict(), indent=2, ensure_ascii=False),
                            encoding="utf-8")
                except Exception:
                    pass
                # 权重 (safetensors 首选 + pt 备份兜底)
                try:
                    from safetensors.torch import save_file as _sf_save
                    state = {k: v.detach().cpu().contiguous()
                             for k, v in self.inner.state_dict().items()}
                    _sf_save(state, str(out_p / "model.safetensors"))
                except Exception:
                    import torch as _torch
                    _torch.save(self.inner.state_dict(), str(out_p / "pytorch_model.bin"))

            def gradient_checkpointing_enable(self, *a, **kw):
                """与 transformers 同名方法对齐。VideoMAEv2 的 with_cp 只在 block 构造时生效，
                所以这里仅做 fallback（建议启动参数里 --grad-checkpoint 直接传入，实例化前会设置 with_cp=True）。"""
                try:
                    backbone = getattr(self.inner, "model", self.inner)
                    setattr(backbone, "with_cp", True)
                    logger.info("VideoMAEv2: 已设置 backbone.with_cp=True")
                except Exception:
                    pass

        wrapped = _V2ModelWrapper(base)
        total_p = sum(p.numel() for p in wrapped.parameters())
        logger.info("VideoMAEv2 加载完成: 参数量=%.1fM, drop_path_rate=%.2f, with_cp=%s",
                     total_p / 1e6, drop_path_rate, grad_checkpoint)
        return wrapped

    # ---------------- 实际模型加载 ----------------
    from transformers import VideoMAEForVideoClassification

    def _from_pretrained(path_or_id: str, local_only: bool, drop_path_rate: float, num_labels: int):
        """统一入口：v2 走自定义加载，v1 走 transformers VideoMAEForVideoClassification。"""
        if _is_videomaev2(path_or_id):
            logger.info("检测到 VideoMAEv2 架构 (model_type=VideoMAEv2_Base), 走自定义加载分支")
            return _load_videomaev2_custom(
                model_dir=path_or_id,
                num_classes=num_labels,
                drop_path_rate=drop_path_rate,
                grad_checkpoint=args.grad_checkpoint,
            )
        import os
        from os import path as osp
        is_local = osp.exists(osp.expanduser(path_or_id))
        try:
            return VideoMAEForVideoClassification.from_pretrained(
                path_or_id,
                local_files_only=local_only and is_local,
                num_labels=num_labels,
                ignore_mismatched_sizes=True,
                attn_implementation="sdpa",
            )
        except Exception as e:
            if is_local:
                raise
            logger.warning("本地加载失败 (%s), 尝试在线从 HuggingFace 下载...", e)
            return VideoMAEForVideoClassification.from_pretrained(
                path_or_id,
                local_files_only=False,
                num_labels=num_labels,
                ignore_mismatched_sizes=True,
                attn_implementation="sdpa",
            )

    if args.resume_from:
        logger.info("续训模式: 从 %s 加载", args.resume_from)
        model = _from_pretrained(args.resume_from, local_only=True,
                                 drop_path_rate=args.drop_path, num_labels=len(SIX_LABELS))
        # 续训自动降学习率 (warm start 对 lr 敏感)
        if args.lr >= 2e-5:
            logger.info("续训 lr 自动下调 %.1e -> 1e-5", args.lr)
            args.lr = 1e-5
    else:
        logger.info("底模重训模式: 从 %s 加载 (v5.2 支持 VideoMAE v1 + v2 自动识别)", args.model_dir)
        model = _from_pretrained(args.model_dir, local_only=False,
                                 drop_path_rate=args.drop_path, num_labels=len(SIX_LABELS))

    # SOTA: Drop Path Rate (官方 ViT-B=0.1)
    # 注意: VideoMAEv2 已经在实例化时把 drop_path_rate 注入了, 这里再跑一次用于
    # transformers v1 / 手动覆盖 (通过 drop_prob 属性扫描, 对 v2 也能生效)
    if args.drop_path > 0:
        _set_drop_path(model, args.drop_path)
        logger.info("Drop Path Rate=%.2f 已配置", args.drop_path)

    if args.grad_checkpoint:
        model.gradient_checkpointing_enable()
    model.to(device)

    # EMA 初始化
    ema = None
    if not args.no_ema:
        ema = EMA(model, decay=args.ema_decay if hasattr(args, 'ema_decay') else 0.9999)
        logger.info("EMA 已启用, decay=%.4f", ema.decay)

    label_to_idx = {l: i for i, l in enumerate(SIX_LABELS)}
    n_total = len(samples)
    n_val = max(16, int(n_total * 0.15))
    idxs = list(range(n_total))
    random.shuffle(idxs)
    val_idx, train_idx = set(idxs[:n_val]), idxs[n_val:]
    # v5.1: Repeated Augmentation — train: num_sample copies, val: 1 copy
    train_ds = ClipDataset(
        [samples[i] for i in train_idx], label_to_idx,
        num_sample=args.num_sample, is_train=True,
    )
    val_ds = ClipDataset(
        [samples[i] for i in val_idx], label_to_idx,
        num_sample=1, is_train=False,
    )
    logger.info(
        "train=%d (raw=%d × num_sample=%d) | val=%d (raw=%d × 1) | schema=six, %d 类",
        len(train_ds), len(train_idx), args.num_sample,
        len(val_ds), len(val_idx), len(SIX_LABELS),
    )

    # 3. 类权重
    dist = Counter(s["label"] for s in samples)
    raw_weights = torch.tensor(
        [n_total / max(1, dist.get(l, 0)) for l in SIX_LABELS], dtype=torch.float32)
    weights = torch.clamp(raw_weights, max=args.weight_cap).to(device)
    logger.info("类分布: %s | 权重(上限%.0fx): %s", dict(dist), args.weight_cap, weights.tolist())

    # 4. 全参微调 (v5 继承 v4 的全参策略, memory 教训: LoRA 有效秩不足)
    for p in model.parameters():
        p.requires_grad = True
    n_train = sum(p.numel() for p in model.parameters() if p.requires_grad)
    n_all = sum(p.numel() for p in model.parameters())
    logger.info("全参微调: 可训练 %d / %d (%.2f%%)", n_train, n_all, 100 * n_train / max(1, n_all))

    # 5. 训练 (SOTA: Layer Decay + SoftTargetCE + Mixup/CutMix + Warmup+Cosine + Weight Decay 0.05)
    import torch
    from timm.data import Mixup
    from timm.loss import SoftTargetCrossEntropy
    from torch.utils.data import DataLoader

    # SOTA: SoftTargetCrossEntropy (配合 mixup, 替代 LabelSmoothingCE)
    # 类权重通过 sample weight 实现 (SoftTargetCE 不直接支持 weight 参数)
    loss_fn = SoftTargetCrossEntropy()  # 配合 timm.data.Mixup 输出的 soft target
    logger.info("Loss: SoftTargetCrossEntropy (timm), 配合 mixup/cutmix 软标签")

    # SOTA: timm.data.Mixup (官方 mixup=0.8 + cutmix=1.0)
    mixup_fn = None
    if args.mixup > 0 or args.cutmix > 0:
        mixup_fn = Mixup(
            mixup_alpha=args.mixup,
            cutmix_alpha=args.cutmix,
            cutmix_minmax=None,
            prob=1.0,
            switch_prob=0.5,
            mode="batch",
            num_classes=len(SIX_LABELS),
            label_smoothing=args.label_smoothing,
        )
        logger.info("Mixup: alpha=%.2f, cutmix=%.2f, label_smoothing=%.2f",
                    args.mixup, args.cutmix, args.label_smoothing)

    # SOTA: Layer Decay param groups (官方 ViT-B=0.75)
    param_groups = _build_layer_decay_param_groups(
        model, lr=args.lr, weight_decay=args.weight_decay, layer_decay=args.layer_decay)
    logger.info("Layer Decay=%.2f, param groups=%d", args.layer_decay, len(param_groups))

    opt = torch.optim.AdamW(param_groups, lr=args.lr, weight_decay=args.weight_decay)

    # SOTA: Warmup + Cosine (官方 warmup_epochs=5)
    total_steps_per_epoch = max(1, len(train_ds) // args.batch_size)
    total_steps = total_steps_per_epoch * args.epochs
    warmup_steps = total_steps_per_epoch * args.warmup_epochs
    logger.info("Scheduler: warmup_steps=%d (%d epochs), total_steps=%d",
                warmup_steps, args.warmup_epochs, total_steps)

    def _lr_lambda(step: int) -> float:
        if step < warmup_steps:
            return step / max(1, warmup_steps)  # 线性 warmup
        # cosine 退火
        import math
        progress = (step - warmup_steps) / max(1, total_steps - warmup_steps)
        return 0.5 * (1.0 + math.cos(math.pi * progress))

    sched = torch.optim.lr_scheduler.LambdaLR(opt, _lr_lambda)
    scaler = torch.cuda.amp.GradScaler(enabled=args.amp and device == "cuda")

    # v5.3 修复: 类别权重实际生效 (v4=0.60 的关键; 之前权重计算了但从未使用)
    # 用 WeightedRandomSampler 采样加权, 兼容 mixup soft-target 损失 (CE weight 无法与 soft target 共用)
    from torch.utils.data import WeightedRandomSampler
    train_ds_samples = [samples[i] for i in train_idx]
    sample_weights = torch.tensor(
        [weights[label_to_idx[s["label"]]]
         for s in train_ds_samples for _ in range(args.num_sample)],
        dtype=torch.float32)
    sampler = WeightedRandomSampler(sample_weights, num_samples=len(sample_weights),
                                    replacement=True)
    logger.info("WeightedRandomSampler: %d 样本, 类权重=%s", len(sample_weights),
                weights.tolist())

    train_loader = DataLoader(train_ds, batch_size=args.batch_size, sampler=sampler,
                              collate_fn=_collate_batch, num_workers=args.num_workers,
                              persistent_workers=(args.num_workers > 0))
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False,
                            collate_fn=_collate_batch, num_workers=args.num_workers,
                            persistent_workers=(args.num_workers > 0))

    best_acc = 0.0
    best_epoch = 0
    history: list[dict[str, Any]] = []
    t0 = time.time()
    for epoch in range(args.epochs):
        model.train()
        total_loss = 0.0
        for bi, batch in enumerate(train_loader):
            batch = {k: v.to(device) for k, v in batch.items()}
            opt.zero_grad()
            # Mixup
            mixup_target = None
            if args.mixup > 0:
                batch, mixup_target = _mixup_batch(batch, len(label_to_idx), args.mixup)

            if scaler.is_enabled():
                with torch.cuda.amp.autocast():
                    out = model(**batch)
                    if mixup_target is not None:
                        loss = loss_fn(out.logits, mixup_target)
                    else:
                        loss = loss_fn(out.logits, batch["labels"])
                scaler.scale(loss).backward()
                scaler.step(opt)
                scaler.update()
                sched.step()
                if ema is not None:
                    ema.update(model)
            else:
                out = model(**batch)
                if mixup_target is not None:
                    loss = loss_fn(out.logits, mixup_target)
                else:
                    loss = loss_fn(out.logits, batch["labels"])
                loss.backward()
                opt.step()
                sched.step()
                if ema is not None:
                    ema.update(model)
            total_loss += loss.item()
            if (bi + 1) % 20 == 0:
                logger.info("  epoch %d step %d/%d loss=%.4f",
                            epoch + 1, bi + 1, len(train_loader), loss.item())

        # 验证
        model.eval()
        if ema is not None:
            ema.apply_shadow(model)
        correct = 0
        n_val_eval = 0
        with infer_ctx(device):
            for batch in val_loader:
                batch = {k: v.to(device) for k, v in batch.items()}
                out = model(**batch)
                pred = out.logits.argmax(dim=1)
                correct += int((pred == batch["labels"]).sum())
                n_val_eval += len(batch["labels"])
        acc = correct / max(1, n_val_eval)
        logger.info("epoch %d loss=%.4f val_acc=%.4f (best %.4f) lr=%.1e",
                    epoch + 1, total_loss / max(1, len(train_loader)), acc, best_acc,
                    sched.get_last_lr()[0])
        history.append({"epoch": epoch + 1, "loss": round(total_loss / max(1, len(train_loader)), 4),
                        "val_acc": round(acc, 4), "lr": float(sched.get_last_lr()[0])})

        if ema is not None:
            ema.restore(model)

        if acc > best_acc:
            best_acc = acc
            best_epoch = epoch + 1
            out_dir = Path(args.out)
            out_dir.mkdir(parents=True, exist_ok=True)
            if ema is not None:
                ema.apply_shadow(model)
            model.save_pretrained(str(out_dir))
            if ema is not None:
                ema.restore(model)
            (out_dir / "meta.json").write_text(json.dumps({
                "base_model": "gullalc/videomae-base-finetuned-kinetics-movieshots-movement",
                "label_schema": "six",
                "labels": SIX_LABELS,
                "n_train": len(train_ds),
                "n_val": len(val_ds),
                "val_acc": round(acc, 4),
                "weight_cap": args.weight_cap,
                "epochs": args.epochs,
                "mode": "full_ft",
                "lora_rank": 0,
                "unfreeze": 0,
                "amp": args.amp,
                "label_smoothing": args.label_smoothing,
                "mixup": args.mixup,
                "best_epoch": best_epoch,
                "resume_from": args.resume_from or None,
                "version": "v5",
                "trained_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "ema_decay": args.ema_decay if not args.no_ema else 0,
            }, ensure_ascii=False, indent=2), encoding="utf-8")
            (out_dir / "train_history.json").write_text(
                json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
            logger.info("已保存最佳 -> %s (val_acc=%.4f)", out_dir, acc)

        if args.early_stop > 0 and (epoch + 1) - best_epoch >= args.early_stop:
            logger.info("早停触发: 连续 %d 轮无提升 (best=%.4f @epoch %d)",
                        args.early_stop, best_acc, best_epoch)
            break

    logger.info("v5 完成: best val_acc=%.4f (epoch %d), 耗时 %.0fs",
                best_acc, best_epoch, time.time() - t0)

    # 验收分级提示
    if best_acc >= 0.80:
        logger.info("验收: 理想 (>=0.80) ✅")
    elif best_acc >= 0.75:
        logger.info("验收: 达标 (>=0.75) ✅")
    elif best_acc >= 0.70:
        logger.info("验收: 保底 (>=0.70) ✅")
    else:
        logger.info("验收: 未达标 (<0.70) ⚠️ (v4=0.6047, v5 需对比 v4 是否提升)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
