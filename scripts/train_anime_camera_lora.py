#!/usr/bin/env python3
"""
Step 4 A4: VideoMAE-MovieShots 动漫域 LoRA 微调

用 A3 的 VLM 预标注结果 (vlm_labels.jsonl) 对现成 VideoMAE 运镜模型
(gullalc/videomae-base-finetuned-kinetics-movieshots-movement, MIT) 做
LoRA 微调, 迁移到动漫域。

标签映射 (A3 三维 schema 的方向维 11 类 → 模型粗 4 类):
  static -> Static
  pan_left/pan_right/tilt_up/tilt_down/orbit -> Motion
  zoom_in/push -> Push
  zoom_out/zoom_back -> Pull
  complex -> 排除 (多轴无单一方向, 留人工复核后细分)
  confidence < 0.7 -> 排除 (主动学习: 低置信进人工队列, 不进训练)

用法 (A3 完成后):
  py -3.12 scripts/train_anime_camera_lora.py \
      --labels D:\\AE-Data\\AnimeCamera\\vlm_labels.jsonl \
      --out models/output/anime_camera_lora \
      --epochs 4 --limit 0
"""
from __future__ import annotations

import argparse
import json
import logging
import random
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("anime_camera_lora")

MODEL_DIR = r"D:\AE-Data\Models\VideoMAE-MovieShots\movement"
NUM_FRAMES = 16
IMG_SIZE = 224

# A3 方向标签 -> 模型粗 4 类 (None = 排除)
COARSE_MAP = {
    "static": "Static",
    "pan_left": "Motion", "pan_right": "Motion",
    "tilt_up": "Motion", "tilt_down": "Motion",
    "orbit": "Motion",
    "zoom_in": "Push", "push": "Push",
    "zoom_out": "Pull", "zoom_back": "Pull",
    "complex": None,
}
COARSE_LABELS = ["Static", "Motion", "Pull", "Push"]

# 细方向 10 类 (v3 直接训细头, 摆脱光流规则细分; complex 排除)
FINE_LABELS = ["static", "pan_left", "pan_right", "tilt_up", "tilt_down",
               "zoom_in", "zoom_out", "push", "zoom_back", "orbit"]

# v3c 六类合并 schema (2026-08-18 P0#2 B6 决策, 基于真实分布根因修复):
#   根因1 语义重叠(~50%): push↔zoom_in 前推语义不可分 (push 仅15条 vs zoom_in 2125条)
#   根因2 极稀缺类无法学习: orbit 7条 / zoom_back 0条 / push 15条
#   合并: push_in=zoom_in+push | pull_out=zoom_out+zoom_back
#         tilt_orbit=tilt_up+tilt_down+orbit (垂直/环绕运动语义近邻)
SIX_MAP = {
    "static": "static",
    "pan_left": "pan_left", "pan_right": "pan_right",
    "tilt_up": "tilt_orbit", "tilt_down": "tilt_orbit", "orbit": "tilt_orbit",
    "zoom_in": "push_in", "push": "push_in",
    "zoom_out": "pull_out", "zoom_back": "pull_out",
    "complex": None,
}
SIX_LABELS = ["static", "pan_left", "pan_right", "tilt_orbit", "push_in", "pull_out"]

# 时间反转增强: 运镜可逆性 (倒放 pan_left = pan_right 等), 补齐方向对不均衡
REVERSE_PAIR = {
    "pan_left": "pan_right", "pan_right": "pan_left",
    "tilt_up": "tilt_down", "tilt_down": "tilt_up",
    "zoom_in": "zoom_out", "zoom_out": "zoom_in",
    "push": "zoom_back", "zoom_back": "push",
}


def load_trainable(labels_path: str, min_conf: float = 0.7,
                   schema: str = "coarse",
                   time_reverse: bool = True) -> List[Dict[str, Any]]:
    """加载 VLM 标注, 按 schema 映射标签, 过滤 complex/低置信。

    time_reverse=True: 对可逆方向对 (zoom_in↔zoom_out 等) 增加倒放样本,
    零标注成本补齐方向对不均衡 (v3 关键增强)。
    """
    rows = [json.loads(l) for l in Path(labels_path).read_text(encoding="utf-8").splitlines() if l.strip()]
    out = []
    skipped = {"complex": 0, "low_conf": 0, "missing_clip": 0, "bad_dir": 0}
    n_reversed = 0
    for r in rows:
        d = r.get("movement_label", "")
        if schema == "fine":
            if d not in FINE_LABELS:
                skipped["bad_dir"] += 1
                continue
            label = d
        elif schema == "six":
            if d not in SIX_MAP:
                skipped["bad_dir"] += 1
                continue
            label = SIX_MAP[d]
            if label is None:
                skipped["complex"] += 1
                continue
        else:
            if d not in COARSE_MAP:
                skipped["bad_dir"] += 1
                continue
            label = COARSE_MAP[d]
            if label is None:
                skipped["complex"] += 1
                continue
        if float(r.get("confidence", 0)) < min_conf:
            skipped["low_conf"] += 1
            continue
        if not Path(r.get("clip_path", "")).exists():
            skipped["missing_clip"] += 1
            continue
        out.append({"clip": r["clip_path"], "coarse": label,
                    "direction": d, "anime": r.get("anime", ""),
                    "reverse": False})
        # 时间反转增强 (只对 fine 方向对生效; coarse 下反转映射到镜像粗类)
        if time_reverse and d in REVERSE_PAIR:
            mirrored_fine = REVERSE_PAIR[d]
            if schema == "fine":
                mirrored = mirrored_fine
            elif schema == "six":
                mirrored = SIX_MAP[mirrored_fine]
            else:
                mirrored = COARSE_MAP[mirrored_fine]
            out.append({"clip": r["clip_path"], "coarse": mirrored,
                        "direction": mirrored_fine, "anime": r.get("anime", ""),
                        "reverse": True})
            n_reversed += 1
    logger.info("可训练样本: %d (含反转增强 %d; 过滤 %s)",
                len(out), n_reversed, skipped)
    return out


class ClipDataset:
    """逐镜头视频数据集: 均匀采样 16 帧 → (T,3,224,224) uint8。"""

    def __init__(self, samples: List[Dict[str, Any]], processor,
                 label_to_idx: Dict[str, int]):
        self.samples = samples
        self.processor = processor
        self.label_to_idx = label_to_idx

    def __len__(self) -> int:
        return len(self.samples)

    def _load_frames(self, clip: str) -> Optional[np.ndarray]:
        from decord import VideoReader, cpu
        try:
            # 解码器原生缩放: 直接出 224x224, 比全尺寸解码+Resize 快数倍
            # (与后续 Resize((224,224)) 同为拉伸语义, 视觉等价)
            vr = VideoReader(clip, ctx=cpu(0), width=IMG_SIZE, height=IMG_SIZE)
        except Exception:  # noqa: BLE001
            return None
        n = len(vr)
        if n < 2:
            return None
        if n <= NUM_FRAMES:
            idxs = list(range(n))
        else:
            step = (n - 1) / (NUM_FRAMES - 1)
            idxs = [round(i * step) for i in range(NUM_FRAMES)]
        try:
            return vr.get_batch(idxs).asnumpy()  # (T,H,W,3) RGB 0-255
        except Exception:  # noqa: BLE001
            return None

    def __getitem__(self, idx: int) -> Dict[str, Any]:
        s = self.samples[idx]
        frames = self._load_frames(s["clip"])
        if frames is None:
            # 坏视频: 重试下一个
            alt = self.samples[(idx + 1) % len(self.samples)]
            frames = self._load_frames(alt["clip"])
            s = alt
        frames = frames.astype(np.float32).transpose(0, 3, 1, 2)  # (T,3,H,W)
        if s.get("reverse"):
            frames = frames[::-1].copy()  # 时间反转增强
        if frames.shape[0] < NUM_FRAMES:
            # 短镜头循环补齐到 16 帧 (批量堆叠需要等长)
            rep = (NUM_FRAMES + frames.shape[0] - 1) // frames.shape[0]
            frames = np.tile(frames, (rep, 1, 1, 1))[:NUM_FRAMES]
        from torchvision.transforms import v2
        frames = v2.Resize((IMG_SIZE, IMG_SIZE))(__import__("torch").from_numpy(frames))
        # processor 兼容: 0-255 用 uint8 (transformers 4.46 对 float>1 会 PIL 转换报错)
        frames = frames.clamp(0, 255).to(__import__("torch").uint8)
        return {"pixel_values": frames, "labels": self.label_to_idx[s["coarse"]]}


def _discover_lora_targets(model) -> List[str]:
    """动态发现 LoRA 目标模块 (VideoMAE 的 attention qkv/query/key/value)。"""
    targets = []
    for name, _ in model.named_modules():
        if name.endswith(".qkv") or name.endswith(".query") \
                or name.endswith(".key") or name.endswith(".value"):
            targets.append(name)
    if not targets:  # 兜底: 全部 Linear
        for name, mod in model.named_modules():
            if "Linear" in type(mod).__name__:
                targets.append(name)
    return targets


def _collate_batch(batch: List[Dict[str, Any]]) -> Dict[str, Any]:
    """模块级 collate (Windows spawn 多进程可 pickle)。

    手动归一化 (VideoMAE 预训练: ImageNet mean/std), 不依赖 processor 版本。
    """
    import torch
    videos = torch.stack([b["pixel_values"] for b in batch])  # (B,T,3,224,224) uint8
    videos = videos.float() / 255.0
    mean = torch.tensor([0.485, 0.456, 0.406], dtype=torch.float32).view(1, 1, 3, 1, 1)
    std = torch.tensor([0.229, 0.224, 0.225], dtype=torch.float32).view(1, 1, 3, 1, 1)
    videos = (videos - mean) / std
    lab = torch.tensor([b["labels"] for b in batch], dtype=torch.long)
    return {"pixel_values": videos, "labels": lab}


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Step 4 A4: VideoMAE 动漫 LoRA 微调")
    parser.add_argument("--labels", default=r"D:\AE-Data\AnimeCamera\vlm_labels.jsonl")
    parser.add_argument("--model-dir", default=MODEL_DIR, help="基座模型目录 (云训练时改路径)")
    parser.add_argument("--out", default=str(PROJECT_ROOT / "models" / "output" / "anime_camera_lora"))
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--num-workers", type=int, default=0, help="数据加载进程数 (云训练设 8)")
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--limit", type=int, default=0, help="最多用 N 样本 (0=全部)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--label-schema", default="coarse", choices=["coarse", "fine", "six"],
                        help="coarse=粗4类 / fine=细10类方向 (v3) / six=合并6类 (v3c 根因修复)")
    parser.add_argument("--weight-cap", type=float, default=5.0,
                        help="类权重上限 (v2 用 20x 崩了, 默认温和 5x)")
    parser.add_argument("--use-sampler", action="store_true",
                        help="启用 WeightedRandomSampler (v2 教训: 默认关)")
    parser.add_argument("--no-time-reverse", dest="time_reverse", action="store_false",
                        help="关闭时间反转增强 (默认开: 补齐方向对不均衡)")
    parser.add_argument("--grad-checkpoint", action="store_true",
                        help="启用梯度检查点 (小显存卡用; 默认关, 实测开反而拖慢2x)")
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)
    import torch
    torch.manual_seed(args.seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info("device=%s", device)

    # 1. 数据
    samples = load_trainable(args.labels, schema=args.label_schema,
                             time_reverse=args.time_reverse)
    LABELS = {"fine": FINE_LABELS, "six": SIX_LABELS}.get(args.label_schema, COARSE_LABELS)
    if args.limit > 0:
        samples = samples[:args.limit]
    if len(samples) < 50:
        logger.error("训练样本不足 (%d), 先跑完 A3", len(samples))
        return 1

    # 2. 模型 (不依赖 processor: 数据集已 resize, collate 手动归一化, 跨版本稳)
    from transformers import VideoMAEForVideoClassification
    model = VideoMAEForVideoClassification.from_pretrained(
        args.model_dir, local_files_only=True, num_labels=len(LABELS),
        ignore_mismatched_sizes=True)
    # gradient checkpointing 默认关: batch16 显存仅 ~4GB, 开启反而加倍计算
    # (实测主进程 98% CPU 瓶颈就是它; 24GB 卡无需省这点显存)
    if args.grad_checkpoint:
        model.gradient_checkpointing_enable()
    model.to(device)

    label_to_idx = {l: i for i, l in enumerate(LABELS)}
    n_total = len(samples)
    n_val = max(16, int(n_total * 0.15))
    idxs = list(range(n_total))
    random.shuffle(idxs)
    val_idx, train_idx = set(idxs[:n_val]), idxs[n_val:]
    train_ds = ClipDataset([samples[i] for i in train_idx], None, label_to_idx)
    val_ds = ClipDataset([samples[i] for i in val_idx], None, label_to_idx)
    logger.info("train=%d val=%d (schema=%s, %d 类)", len(train_ds), len(val_ds),
                args.label_schema, len(LABELS))

    # 类权重 (不均衡处理, 上限可配; v2 教训: 20x+重采样会崩)
    from collections import Counter
    dist = Counter(s["coarse"] for s in samples)
    raw_weights = torch.tensor(
        [n_total / max(1, dist.get(l, 0)) for l in LABELS],
        dtype=torch.float32)
    weights = torch.clamp(raw_weights, max=args.weight_cap).to(device)
    logger.info("类分布: %s | 权重(上限%.0fx): %s", dict(dist),
                args.weight_cap, weights.tolist())

    # 3. LoRA
    from peft import LoraConfig, get_peft_model
    targets = _discover_lora_targets(model)
    logger.info("LoRA 目标模块: %d 个 (示例 %s)", len(targets), targets[:3])
    # fine/six schema 时把 classifier 头纳入保存 (modules_to_save): 分类头是 num_labels
    # 重建的随机初始化层, 不在 ckpt 里, 若不保存 adapter 回传后本地无法恢复 (v3 坑)
    modules_to_save = ["classifier"] if args.label_schema in ("fine", "six") else None
    lora_config = LoraConfig(
        r=8, lora_alpha=16, lora_dropout=0.1,
        target_modules=targets,
        bias="none",
        modules_to_save=modules_to_save,
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # 4. 训练 (按类加权重采样: 稀缺类 Pull/Static 出现频率放大)
    from torch.utils.data import DataLoader, WeightedRandomSampler
    loss_fn = torch.nn.CrossEntropyLoss(weight=weights)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)

    # 注: collate 必须是模块级 _collate_batch — Windows spawn 模式无法 pickle 局部函数
    collate = _collate_batch

    # 加权重采样: v2 教训 (num_samples=2x + replacement 导致崩), v3 默认关
    if args.use_sampler:
        sample_weights = [weights[label_to_idx[samples[i]["coarse"]]].item()
                          for i in train_idx]
        sampler = WeightedRandomSampler(sample_weights, num_samples=len(train_idx),
                                        replacement=True)
        train_loader = DataLoader(train_ds, batch_size=args.batch_size, sampler=sampler,
                                  collate_fn=collate, num_workers=args.num_workers,
                                  persistent_workers=(args.num_workers > 0))
    else:
        train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True,
                                  collate_fn=collate, num_workers=args.num_workers,
                                  persistent_workers=(args.num_workers > 0))
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False,
                            collate_fn=collate, num_workers=args.num_workers,
                            persistent_workers=(args.num_workers > 0))

    best_acc = 0.0
    t0 = time.time()
    for epoch in range(args.epochs):
        model.train()
        total_loss = 0.0
        for bi, batch in enumerate(train_loader):
            batch = {k: v.to(device) for k, v in batch.items()}
            opt.zero_grad()
            out = model(**batch)
            loss = loss_fn(out.logits, batch["labels"])
            loss.backward()
            opt.step()
            total_loss += loss.item()
            if (bi + 1) % 20 == 0:
                logger.info("  epoch %d step %d/%d loss=%.4f",
                            epoch + 1, bi + 1, len(train_loader), loss.item())
        # 验证
        model.eval()
        correct = 0
        n_val_eval = 0
        with torch.no_grad():
            for batch in val_loader:
                batch = {k: v.to(device) for k, v in batch.items()}
                out = model(**batch)
                pred = out.logits.argmax(dim=1)
                correct += int((pred == batch["labels"]).sum())
                n_val_eval += len(batch["labels"])
        acc = correct / max(1, n_val_eval)
        logger.info("epoch %d loss=%.4f val_acc=%.4f (best %.4f)",
                    epoch + 1, total_loss / max(1, len(train_loader)), acc, best_acc)
        if acc > best_acc:
            best_acc = acc
            out_dir = Path(args.out)
            out_dir.mkdir(parents=True, exist_ok=True)
            model.save_pretrained(str(out_dir))
            (out_dir / "meta.json").write_text(json.dumps({
                "base_model": "gullalc/videomae-base-finetuned-kinetics-movieshots-movement",
                "label_schema": args.label_schema,
                "labels": LABELS,
                "n_train": len(train_ds),
                "n_val": len(val_ds),
                "val_acc": round(acc, 4),
                "weight_cap": args.weight_cap,
                "epochs": args.epochs,
                "trained_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }, ensure_ascii=False, indent=2), encoding="utf-8")
            logger.info("已保存最佳 -> %s", out_dir)

    logger.info("完成: best val_acc=%.4f, 耗时 %.0fs", best_acc, time.time() - t0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
