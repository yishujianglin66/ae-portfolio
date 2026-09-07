"""BiRefNet 动漫域微调（1111 对动漫图像+mask，8GB 显存）
策略: 冻结 backbone 微调 decoder/refiner + AMP FP16 + BCE+Dice 损失
用法: py -3.12 scripts/finetune_birefnet.py [--epochs 8] [--batch 4]
"""
from __future__ import annotations

import argparse
import random
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from core.torch_runtime import infer_ctx, get_device
from torchvision import transforms
from transformers import AutoModelForImageSegmentation

PROJECT = Path(__file__).resolve().parents[1]
DATA = PROJECT / "external" / "animeseg" / "dataset"
IMGS = DATA / "imgs"
MASKS = DATA / "masks"
CKPT_DIR = PROJECT / "external" / "birefnet"


def dice_loss(pred_logits: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    pred = torch.sigmoid(pred_logits)
    smooth = 1.0
    inter = (pred * target).sum(dim=(2, 3))
    union = pred.sum(dim=(2, 3)) + target.sum(dim=(2, 3))
    return 1 - ((2 * inter + smooth) / (union + smooth)).mean()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=8)
    ap.add_argument("--batch", type=int, default=4)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--resume", default="", help="从存档权重续训（如 external/birefnet/finetuned_anime_ep0.pth）")
    ap.add_argument("--data", default="", help="统一 imgs/masks 训练集目录 (默认 external/animeseg/dataset)")
    ap.add_argument("--ckpt-dir", default="", help="权重输出目录 (默认 external/birefnet)")
    ap.add_argument("--model-dir", default="", help="BiRefNet 模型代码目录 (默认 = ckpt-dir)")
    args = ap.parse_args()

    data_root = Path(args.data) if args.data else DATA
    img_dir = data_root / "imgs"
    mask_dir = data_root / "masks"
    ckpt_dir = Path(args.ckpt_dir) if args.ckpt_dir else CKPT_DIR
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    model_dir = Path(args.model_dir) if args.model_dir else ckpt_dir

    # ---- 数据配对 ----
    img_files = sorted(img_dir.glob("*.jpg")) + sorted(img_dir.glob("*.png"))
    pairs = []
    for f in img_files:
        m = mask_dir / f"{f.stem}.png"
        if not m.exists():
            m = mask_dir / f"{f.stem}.jpg"
        if m.exists():
            pairs.append((f, m))
    print(f"配对数据: {len(pairs)}", file=sys.stderr)
    if len(pairs) < 50:
        print("数据不足", file=sys.stderr)
        return 1
    random.seed(42)
    random.shuffle(pairs)
    split = int(len(pairs) * 0.9)
    train_pairs, val_pairs = pairs[:split], pairs[split:]

    tf = transforms.Compose([
        transforms.ToTensor(),
        transforms.Resize((1024, 1024)),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])

    def load_batch(pairs_slice):
        imgs, masks = [], []
        for f, m in pairs_slice:
            img = cv2.imdecode(np.fromfile(str(f), dtype=np.uint8), cv2.IMREAD_COLOR)
            msk = cv2.imdecode(np.fromfile(str(m), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
            if img is None or msk is None:
                continue
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            imgs.append(tf(img_rgb))
            m = cv2.resize(msk, (1024, 1024), interpolation=cv2.INTER_NEAREST)
            masks.append(torch.from_numpy((m > 127).astype(np.float32)))
        if not imgs:
            return None, None
        return torch.stack(imgs), torch.stack(masks).unsqueeze(1)

    # ---- 模型 ----
    print("loading BiRefNet...", file=sys.stderr)
    model = AutoModelForImageSegmentation.from_pretrained(
        str(model_dir), trust_remote_code=True, local_files_only=True).cuda().float()  # FP32 参数 + autocast AMP
    if args.resume:
        model.load_state_dict(torch.load(args.resume, map_location="cpu"))
        print(f"续训自 {args.resume}", file=sys.stderr)
    # 冻结 backbone：冻结所有参数，只解冻 decoder/refiner 层（名字含 decoder/refiner/seg/head）
    frozen = 0
    trainable = 0
    for name, p in model.named_parameters():
        if any(k in name for k in ("decoder", "refiner", "seg_head", "head", "aspp", "out")):
            p.requires_grad = True
            trainable += 1
        else:
            p.requires_grad = False
            frozen += 1
    print(f"冻结 {frozen} 层 / 可训练 {trainable} 层", file=sys.stderr)

    opt = torch.optim.AdamW(filter(lambda p: p.requires_grad, model.parameters()), lr=args.lr)
    scaler = torch.amp.GradScaler("cuda")

    best_val = 1e9
    t0 = time.time()
    for epoch in range(args.epochs):
        model.train()
        random.shuffle(train_pairs)
        epoch_loss = 0.0
        n_batches = 0
        for i in range(0, len(train_pairs), args.batch):
            imgs, masks = load_batch(train_pairs[i:i + args.batch])
            if imgs is None or imgs.shape[0] < 2:  # 读取失败致单样本 batch → 跳过（BN 需 batch≥2）
                continue
            imgs, masks = imgs.cuda(), masks.cuda()
            opt.zero_grad()
            with torch.autocast("cuda", dtype=torch.float16):
                out = model(imgs)
                # training 返回 [([aux], [multi_scale_logits]), [None]]；最终 logits = out[0][1][-1]
                preds = out[0][1][-1] if isinstance(out, (list, tuple)) and isinstance(out[0], (list, tuple)) else out
                loss = F.binary_cross_entropy_with_logits(preds, masks) + dice_loss(preds, masks)
            scaler.scale(loss).backward()
            scaler.step(opt)
            scaler.update()
            epoch_loss += float(loss)
            n_batches += 1
            if n_batches % 25 == 0:
                print(f"  ep{epoch} batch{n_batches} loss={float(loss):.4f}", file=sys.stderr)
        # 验证
        model.eval()
        val_loss = 0.0
        nv = 0
        with infer_ctx(get_device()):
            for i in range(0, len(val_pairs), args.batch):
                imgs, masks = load_batch(val_pairs[i:i + args.batch])
                if imgs is None or imgs.shape[0] < 2:  # 跳过单样本 batch（BN 需 batch≥2）
                    continue
                imgs, masks = imgs.cuda(), masks.cuda()
                with torch.autocast("cuda", dtype=torch.float16):
                    out = model(imgs)
                    # eval 模式返回结构与训练不同：取 [-1]（单 logits tensor）
                    preds = out[-1] if isinstance(out, (list, tuple)) else out
                    loss = F.binary_cross_entropy_with_logits(preds, masks) + dice_loss(preds, masks)
                val_loss += float(loss)
                nv += 1
        v = val_loss / max(nv, 1)
        print(f"epoch {epoch}: train={epoch_loss / max(n_batches, 1):.4f} val={v:.4f} "
              f"({time.time() - t0:.0f}s)", file=sys.stderr)
        torch.save(model.state_dict(), ckpt_dir / f"finetuned_anime_ep{epoch}.pth")  # 每 epoch 保险存档
        if v < best_val:
            best_val = v
            torch.save(model.state_dict(), ckpt_dir / "finetuned_anime.pth")
            print(f"  saved best (val {v:.4f})", file=sys.stderr)
    print(f"训练完成 {args.epochs} epochs in {(time.time() - t0) / 60:.1f} min, best_val={best_val:.4f}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
