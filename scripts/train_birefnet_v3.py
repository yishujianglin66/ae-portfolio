"""BiRefNet 动漫域续训 v3 — SOTA 改进链路 (V100-32GB / fp16)。

相对 finetune_birefnet.py 的改进:
  1. Loss 对齐官方 BiRefNet: 30*BCE + 100*MAE + 10*SSIM (+0*IoU) (自实现 box-filter SSIM)
  2. EMA shadow 权重: decay=0.9995, 每 step 更新, 评估/保存用 shadow (arXiv:2510.18213)
  3. CosineAnnealingLR + 5% warmup (step 级), eta_min=1e-6
  4. 梯度裁剪 clip_grad_norm_=1.0 (scaler.unscale_ 之后, scaler.step 之前)
  5. 多阶段监督: ms_supervision=True 时对 [m4,m3,m2,p1_out] 各尺度分别计 loss 后取平均
  6. AMP fp16 + GradScaler (V100 不支持 bf16)
  7. 数据增强: HorizontalFlip + RandomRotation(10) + ColorJitter (mask 同步, matting 友好)
  8. 基于 val_loss 保存最佳 shadow 权重 + meta.json 元数据

鲁棒 logits 提取兼容 train/eval 两种返回结构 (参考 tmp/cloud_p2_fix_v2.py)。

用法 (云端 autodl):
  python scripts/train_birefnet_v3.py --data-root /root/autodl-tmp/animeseg/dataset \
      --resume /root/autodl-tmp/birefnet_mixed/finetuned_anime_best.pth \
      --model-dir /root/autodl-tmp/birefnet --out /root/autodl-tmp/birefnet_v3
冒烟:
  python scripts/train_birefnet_v3.py --limit 32 --epochs 1
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import random
import sys
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from torchvision import transforms
from transformers import AutoModelForImageSegmentation

# ---------------- loss 权重 (对齐官方 BiRefNet loss.py) ----------------
W_BCE: float = 30.0
W_MAE: float = 100.0
W_SSIM: float = 10.0
W_IOU: float = 0.0  # 官方默认 iou 权重为 0

IMG_SIZE: int = 1024
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from core.torch_runtime import infer_ctx  # noqa: E402


# ============================== 损失函数 ==============================

def _ssim_loss(pred_sig: torch.Tensor, target: torch.Tensor, window_size: int = 11) -> torch.Tensor:
    """box-filter SSIM, 返回 1 - ssim (越小越好).

    pred_sig / target: [B,1,H,W], 值域 [0,1]. 在 fp32 下计算避免 fp16 精度损失.
    (pytorch_msssim 未安装时的自实现替代, 与官方 gaussian 版近似)
    """
    assert pred_sig.dim() == 4 and target.dim() == 4
    p = pred_sig.float()
    t = target.float()
    pad = window_size // 2
    c1, c2 = 0.01 ** 2, 0.03 ** 2

    def _avg(x: torch.Tensor) -> torch.Tensor:
        return F.avg_pool2d(x, window_size, stride=1, padding=pad)

    mu1, mu2 = _avg(p), _avg(t)
    mu1_sq, mu2_sq, mu1_mu2 = mu1 ** 2, mu2 ** 2, mu1 * mu2
    sigma1_sq = _avg(p * p) - mu1_sq
    sigma2_sq = _avg(t * t) - mu2_sq
    sigma12 = _avg(p * t) - mu1_mu2
    ssim_map = ((2 * mu1_mu2 + c1) * (2 * sigma12 + c2)) / (
        (mu1_sq + mu2_sq + c1) * (sigma1_sq + sigma2_sq + c2)
    )
    return 1.0 - ssim_map.mean()


def combined_loss(preds: torch.Tensor, masks: torch.Tensor) -> torch.Tensor:
    """单尺度组合损失: 30*BCE + 100*MAE + 10*SSIM + 0*IoU.

    preds: logits [B,1,h,w]; masks: [B,1,H,W] (自动插值对齐).
    """
    if preds.dim() == 3:
        preds = preds.unsqueeze(1)
    if preds.shape[-2:] != masks.shape[-2:]:
        preds = F.interpolate(preds, size=masks.shape[-2:], mode="bilinear", align_corners=False)

    bce = F.binary_cross_entropy_with_logits(preds, masks)
    pred_sig = torch.sigmoid(preds)
    mae = F.l1_loss(pred_sig, masks)
    ssim = _ssim_loss(pred_sig, masks)
    loss = W_BCE * bce + W_MAE * mae + W_SSIM * ssim
    if W_IOU > 0:
        inter = (pred_sig * masks).sum(dim=(2, 3))
        union = pred_sig.sum(dim=(2, 3)) + masks.sum(dim=(2, 3))
        iou = 1.0 - ((2 * inter + 1.0) / (union + 1.0)).mean()
        loss = loss + W_IOU * iou
    return loss


# ====================== 鲁棒 logits 提取 (train/eval 兼容) ======================

_struct_logged: dict[str, bool] = {"train": False, "eval": False}


def _log_struct(obj: Any, depth: int = 0) -> str:
    if depth > 4:
        return "..."
    if isinstance(obj, torch.Tensor):
        return f"Tensor{tuple(obj.shape)}"
    if isinstance(obj, (list, tuple)):
        inner = ", ".join(_log_struct(x, depth + 1) for x in obj[:3])
        return f"{type(obj).__name__}[{len(obj)}]({inner})"
    return type(obj).__name__


def extract_all_preds(out: Any, mode: str = "train") -> list[torch.Tensor]:
    """提取所有多阶段监督 logits (训练含 [m4,m3,m2,p1_out]; eval 含 [p1_out]).

    兼容 BiRefNet 经 AutoModelForImageSegmentation 包装后的返回结构:
      train: [scaled_preds, class_preds_lst], scaled_preds=([gdt_pred,gdt_label], outs)
              -> outs = [m4,m3,m2,p1_out]  => out[0][1]
      eval:  scaled_preds = outs = [p1_out]  (扁平 list)
    返回 list[Tensor], 至少 1 个, 最终高分辨率 logits 在末尾.
    """
    if not _struct_logged[mode]:
        logging.getLogger("birefnet_v3").info("[%s] 输出结构: %s", mode, _log_struct(out))
        _struct_logged[mode] = True

    if isinstance(out, torch.Tensor):
        return [out]
    if isinstance(out, (list, tuple)):
        # train: out[0] 是 (list, list) 形式的 scaled_preds
        if len(out) > 0 and isinstance(out[0], (list, tuple)):
            inner = out[0]
            # inner = ([gdt_pred, gdt_label], outs) -> outs = inner[1]
            if len(inner) == 2 and isinstance(inner[1], (list, tuple)) and inner[1]:
                ts = [t for t in inner[1] if isinstance(t, torch.Tensor)]
                if ts:
                    return ts
            # inner 本身含 tensor
            ts = [t for t in inner if isinstance(t, torch.Tensor)]
            if ts:
                return ts
        # eval 扁平结构: 直接收集 tensor
        ts = [t for t in out if isinstance(t, torch.Tensor)]
        if ts:
            return ts
        # 兜底递归
        for item in reversed(out):
            if isinstance(item, (list, tuple)):
                sub = [t for t in item if isinstance(t, torch.Tensor)]
                if sub:
                    return sub
    raise TypeError(f"无法从结构提取 logits: {type(out)} / {repr(out)[:200]}")


# ============================== EMA shadow ==============================

class EMA:
    """Exponential Moving Average shadow 权重 (arXiv:2510.18213).

    每 step update; 评估/保存时 apply_shadow 临时换入 shadow, 完成后 restore.
    仅 shadow 可训练参数 (BN running stats 等 buffer 保留模型当前值).
    """

    def __init__(self, model: torch.nn.Module, decay: float = 0.9995) -> None:
        self.decay = decay
        self.shadow: dict[str, torch.Tensor] = {}
        self.backup: dict[str, torch.Tensor] = {}
        for n, p in model.named_parameters():
            if p.requires_grad:
                self.shadow[n] = p.detach().clone()

    @torch.no_grad()
    def update(self, model: torch.nn.Module) -> None:
        d = self.decay
        for n, p in model.named_parameters():
            if n in self.shadow:
                self.shadow[n].mul_(d).add_(p.detach(), alpha=1.0 - d)

    def apply_shadow(self, model: torch.nn.Module) -> None:
        """临时把可训练参数替换为 shadow (BN buffer 不动)."""
        self.backup = {}
        for n, p in model.named_parameters():
            if n in self.shadow:
                self.backup[n] = p.detach().clone()
                p.copy_(self.shadow[n])

    def restore(self, model: torch.nn.Module) -> None:
        for n, p in model.named_parameters():
            if n in self.backup:
                p.copy_(self.backup[n])
        self.backup = {}

    def shadow_state_dict(self, model: torch.nn.Module) -> dict[str, torch.Tensor]:
        """返回含 shadow 参数 + 模型 buffer 的 state_dict (不修改模型)."""
        sd = {k: v.detach().clone() for k, v in model.state_dict().items()}
        for n, sh in self.shadow.items():
            if n in sd:
                sd[n] = sh.detach().clone()
        return sd


# ============================== 数据增强 ==============================

def _color_jitter(img_bgr: np.ndarray) -> np.ndarray:
    """亮度/对比度/饱和度抖动 (仅作用于图像, 不动 mask)."""
    out = img_bgr.astype(np.float32)
    if random.random() < 0.8:  # brightness
        out = out * random.uniform(0.8, 1.2)
    if random.random() < 0.8:  # contrast
        f = random.uniform(0.8, 1.2)
        mean = out.mean()
        out = (out - mean) * f + mean
    out = np.clip(out, 0, 255).astype(np.uint8)
    if random.random() < 0.8:  # saturation
        hsv = cv2.cvtColor(out, cv2.COLOR_BGR2HSV)
        s = hsv[:, :, 1].astype(np.float32) * random.uniform(0.8, 1.2)
        hsv[:, :, 1] = np.clip(s, 0, 255).astype(np.uint8)
        out = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    return out


def augment_pair(img_bgr: np.ndarray, msk_gray: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """matting 友好增强: HorizontalFlip + RandomRotation(10) + ColorJitter, mask 同步变换."""
    # HorizontalFlip
    if random.random() < 0.5:
        img_bgr = img_bgr[:, ::-1, :].copy()
        msk_gray = msk_gray[:, ::-1].copy()
    # RandomRotation ±10°
    angle = random.uniform(-10, 10)
    h, w = msk_gray.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), angle, 1.0)
    img_bgr = cv2.warpAffine(
        img_bgr, m, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101
    )
    msk_gray = cv2.warpAffine(
        msk_gray, m, (w, h), flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT, borderValue=0
    )
    # ColorJitter 仅图像
    img_bgr = _color_jitter(img_bgr)
    return img_bgr, msk_gray


# ============================== 主流程 ==============================

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="BiRefNet v3 续训 (SOTA 改进链路)")
    ap.add_argument("--resume", default="external/birefnet/finetuned_anime_best.pth",
                    help="续训权重 (云端 P2 产物 finetuned_anime_best.pth)")
    ap.add_argument("--epochs", type=int, default=15)
    ap.add_argument("--batch", type=int, default=4)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--ema-decay", type=float, default=0.9995)
    ap.add_argument("--warmup-ratio", type=float, default=0.05, help="warmup 步数占总步数比例")
    ap.add_argument("--eta-min", type=float, default=1e-6, help="cosine 退火最小学习率")
    ap.add_argument("--grad-clip", type=float, default=1.0, help="梯度裁剪 max_norm")
    ap.add_argument("--out", default="external/birefnet_v3", help="权重/元数据输出目录")
    ap.add_argument("--data-root", default="D:/AE-Data/AnimeCamera/external/animeseg/dataset",
                    help="imgs/masks 训练集根目录 (跨机可配置)")
    ap.add_argument("--model-dir", default="external/birefnet", help="BiRefNet 模型代码目录")
    ap.add_argument("--limit", type=int, default=0, help="冒烟测试: 仅取前 N 对样本 (0=全部)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--no-ema", action="store_true", help="禁用 EMA (调试用)")
    ap.add_argument("--log-file", default="", help="日志文件路径 (默认 out/train.log)")
    return ap.parse_args()


def setup_logger(log_file: Path | None) -> logging.Logger:
    logger = logging.getLogger("birefnet_v3")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(str(log_file), encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    return logger


def build_pairs(img_dir: Path, mask_dir: Path, limit: int, seed: int,
                logger: logging.Logger) -> tuple[list[tuple[Path, Path]], list[tuple[Path, Path]]]:
    img_files = sorted(img_dir.glob("*.jpg")) + sorted(img_dir.glob("*.png"))
    pairs: list[tuple[Path, Path]] = []
    for f in img_files:
        m = mask_dir / f"{f.stem}.png"
        if not m.exists():
            m = mask_dir / f"{f.stem}.jpg"
        if m.exists():
            pairs.append((f, m))
    logger.info("配对数据: %d", len(pairs))
    if len(pairs) < 50:
        logger.error("数据不足 (<50), 终止")
        sys.exit(1)
    random.seed(seed)
    random.shuffle(pairs)
    if limit and limit > 0:
        pairs = pairs[:limit]
        logger.info("冒烟模式: 截取前 %d 对", limit)
    split = int(len(pairs) * 0.9)
    return pairs[:split], pairs[split:]


def make_loader(tf_img: transforms.Compose):
    def load_batch(pairs_slice: list[tuple[Path, Path]], training: bool) \
            -> tuple[torch.Tensor | None, torch.Tensor | None]:
        imgs: list[torch.Tensor] = []
        masks: list[torch.Tensor] = []
        for f, m in pairs_slice:
            img = cv2.imdecode(np.fromfile(str(f), dtype=np.uint8), cv2.IMREAD_COLOR)
            msk = cv2.imdecode(np.fromfile(str(m), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
            if img is None or msk is None:
                continue
            if training:
                img, msk = augment_pair(img, msk)
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            imgs.append(tf_img(img_rgb))
            mm = cv2.resize(msk, (IMG_SIZE, IMG_SIZE), interpolation=cv2.INTER_NEAREST)
            masks.append(torch.from_numpy((mm > 127).astype(np.float32)))
        if not imgs:
            return None, None
        return torch.stack(imgs), torch.stack(masks).unsqueeze(1)

    return load_batch


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    logger = setup_logger(Path(args.log_file) if args.log_file else (out_dir / "train.log"))

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)

    data_root = Path(args.data_root)
    img_dir = data_root / "imgs"
    mask_dir = data_root / "masks"
    train_pairs, val_pairs = build_pairs(img_dir, mask_dir, args.limit, args.seed, logger)
    logger.info("train=%d val=%d", len(train_pairs), len(val_pairs))

    tf_img = transforms.Compose([
        transforms.ToTensor(),
        transforms.Resize((IMG_SIZE, IMG_SIZE)),
        transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
    ])
    load_batch = make_loader(tf_img)

    # ---- 模型 ----
    logger.info("loading BiRefNet from %s ...", args.model_dir)
    model = AutoModelForImageSegmentation.from_pretrained(
        args.model_dir, trust_remote_code=True, local_files_only=True
    ).cuda().float()  # FP32 参数 + autocast AMP fp16
    if args.resume:
        resume_path = Path(args.resume)
        if resume_path.exists():
            model.load_state_dict(torch.load(str(resume_path), map_location="cpu"))
            logger.info("续训自 %s", resume_path)
        else:
            logger.warning("resume 不存在: %s, 从预训练从头开始", resume_path)

    # 冻结 backbone, 解冻 decoder/refiner/seg/head (与 v1 一致)
    frozen, trainable = 0, 0
    for name, p in model.named_parameters():
        if any(k in name for k in ("decoder", "refiner", "seg_head", "head", "aspp", "out")):
            p.requires_grad = True
            trainable += 1
        else:
            p.requires_grad = False
            frozen += 1
    logger.info("冻结 %d 层 / 可训练 %d 层", frozen, trainable)

    params = list(filter(lambda p: p.requires_grad, model.parameters()))
    opt = torch.optim.AdamW(params, lr=args.lr)
    scaler = torch.amp.GradScaler("cuda")

    # ---- EMA ----
    use_ema = (not args.no_ema) and trainable > 0
    ema = EMA(model, decay=args.ema_decay) if use_ema else None
    if use_ema:
        logger.info("EMA 启用 decay=%.5f (shadow=%d)", args.ema_decay, len(ema.shadow))  # type: ignore[union-attr]

    # ---- LR: warmup + cosine (step 级) ----
    steps_per_epoch = max(1, math.ceil(len(train_pairs) / args.batch))
    total_steps = args.epochs * steps_per_epoch
    warmup_steps = max(1, int(total_steps * args.warmup_ratio))
    eta_min_ratio = args.eta_min / max(1e-12, args.lr)

    def lr_lambda(step: int) -> float:
        if step < warmup_steps:
            return (step + 1) / warmup_steps  # 线性 warmup, 末尾达 1.0
        progress = (step - warmup_steps) / max(1, total_steps - warmup_steps)
        progress = min(1.0, max(0.0, progress))
        return eta_min_ratio + (1.0 - eta_min_ratio) * 0.5 * (1.0 + math.cos(math.pi * progress))

    scheduler = torch.optim.lr_scheduler.LambdaLR(opt, lr_lambda)
    logger.info("LR 调度: base=%g eta_min=%g total_steps=%d warmup=%d",
               args.lr, args.eta_min, total_steps, warmup_steps)

    def forward_loss(imgs: torch.Tensor, masks: torch.Tensor, mode: str) -> torch.Tensor:
        with torch.autocast("cuda", dtype=torch.float16):
            out = model(imgs)
            preds_list = extract_all_preds(out, mode)
            # 多阶段监督: 各尺度分别计组合损失后取平均; eval 单尺度等价单次
            total = combined_loss(preds_list[0], masks)
            for p in preds_list[1:]:
                total = total + combined_loss(p, masks)
            return total / max(1, len(preds_list))

    best_val = float("inf")
    best_epoch = -1
    global_step = 0
    t0 = time.time()
    history: list[dict[str, Any]] = []

    for epoch in range(args.epochs):
        model.train()
        random.shuffle(train_pairs)
        epoch_loss, n_batches = 0.0, 0
        for i in range(0, len(train_pairs), args.batch):
            imgs, masks = load_batch(train_pairs[i:i + args.batch], training=True)
            if imgs is None or imgs.shape[0] < 2:  # BN 需 batch>=2
                continue
            imgs, masks = imgs.cuda(non_blocking=True), masks.cuda(non_blocking=True)
            opt.zero_grad(set_to_none=True)
            loss = forward_loss(imgs, masks, "train")
            scaler.scale(loss).backward()
            scaler.unscale_(opt)  # 先 unscale 再裁剪 (V100 fp16 必需顺序)
            torch.nn.utils.clip_grad_norm_(params, max_norm=args.grad_clip)
            scaler.step(opt)
            scaler.update()
            scheduler.step()
            if use_ema:
                ema.update(model)  # type: ignore[union-attr]
            global_step += 1
            epoch_loss += float(loss)
            n_batches += 1
            if n_batches % 25 == 0:
                cur_lr = scheduler.get_last_lr()[0]
                logger.info("  ep%d batch%d step%d loss=%.4f lr=%.2e",
                            epoch, n_batches, global_step, float(loss), cur_lr)
        train_loss = epoch_loss / max(1, n_batches)

        # ---- 验证 (用 shadow 权重) ----
        model.eval()
        if use_ema:
            ema.apply_shadow(model)  # type: ignore[union-attr]
        val_loss, n_val = 0.0, 0
        try:
            with infer_ctx():
                for i in range(0, len(val_pairs), args.batch):
                    imgs, masks = load_batch(val_pairs[i:i + args.batch], training=False)
                    if imgs is None or imgs.shape[0] < 2:
                        continue
                    imgs, masks = imgs.cuda(non_blocking=True), masks.cuda(non_blocking=True)
                    loss = forward_loss(imgs, masks, "eval")
                    val_loss += float(loss)
                    n_val += 1
        finally:
            if use_ema:
                ema.restore(model)  # type: ignore[union-attr]
        val_loss = val_loss / max(1, n_val)

        elapsed = time.time() - t0
        logger.info("epoch %d: train=%.4f val=%.4f (%.0fs)", epoch, train_loss, val_loss, elapsed)
        history.append({"epoch": epoch, "train_loss": round(train_loss, 6),
                        "val_loss": round(val_loss, 6), "elapsed_s": int(elapsed)})

        # ---- 保存 (shadow 权重) ----
        save_sd = ema.shadow_state_dict(model) if use_ema else model.state_dict()
        torch.save(save_sd, str(out_dir / f"birefnet_v3_ep{epoch}.pth"))  # 每 epoch 保险存档
        if val_loss < best_val:
            best_val = val_loss
            best_epoch = epoch
            torch.save(save_sd, str(out_dir / "birefnet_v3_best.pth"))
            logger.info("  saved best (shadow) val=%.4f -> birefnet_v3_best.pth", best_val)

    # 末轮权重
    final_sd = ema.shadow_state_dict(model) if use_ema else model.state_dict()
    torch.save(final_sd, str(out_dir / "birefnet_v3_last.pth"))

    # ---- meta.json ----
    meta = {
        "script": "train_birefnet_v3.py",
        "status": "completed",
        "best_val_loss": round(best_val, 6),
        "best_epoch": best_epoch,
        "epochs": args.epochs,
        "batch": args.batch,
        "lr": args.lr,
        "eta_min": args.eta_min,
        "warmup_ratio": args.warmup_ratio,
        "warmup_steps": warmup_steps,
        "total_steps": total_steps,
        "ema": {"enabled": use_ema, "decay": args.ema_decay},
        "grad_clip": args.grad_clip,
        "loss_config": {"bce": W_BCE, "mae": W_MAE, "ssim": W_SSIM, "iou": W_IOU,
                        "ssim_impl": "box_filter_avgpool"},
        "multi_stage_supervision": True,
        "amp": "fp16_gradscaler",
        "resume": args.resume,
        "data_root": args.data_root,
        "model_dir": args.model_dir,
        "out_dir": str(out_dir),
        "train_samples": len(train_pairs),
        "val_samples": len(val_pairs),
        "frozen": frozen,
        "trainable": trainable,
        "history": history,
        "elapsed_min": round((time.time() - t0) / 60.0, 1),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("训练完成 %d epochs in %.1f min, best_val=%.4f (ep%d)",
                args.epochs, (time.time() - t0) / 60.0, best_val, best_epoch)
    return 0


if __name__ == "__main__":
    sys.exit(main())
