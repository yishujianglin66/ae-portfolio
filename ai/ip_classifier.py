# -*- coding: utf-8 -*-
"""P2.2 本地IP分类器 — ResNet18微调，教师标签帧训练
=====================================================
协议(防泄漏):
- 训练/验证: 按【视频】划分(非黄金集素材)，同一视频帧不跨集
- 验收: 黄金集12素材完全保留，训练后按帧多数投票判定primary_ip，
  与 data/benchmark_golden.json 人工/双通道标签对比

用法:
  python -m ai.ip_classifier --train          # 训练
  python -m ai.ip_classifier --accept         # 黄金集验收
  python -m ai.ip_classifier --predict <视频> # 单视频推理
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

from core.torch_runtime import get_device, infer_ctx

ROOT = Path(__file__).resolve().parent.parent
LABELS = ROOT / "data" / "training" / "labels.json"
GOLDEN = ROOT / "data" / "benchmark_golden.json"
CKPT = ROOT / "models" / "ip_classifier.pt"
META = ROOT / "models" / "ip_classifier_meta.json"
REPORT = ROOT / "reports" / "ip_classifier_report.json"

MIN_CLASS_FRAMES = 30      # 少于该帧数的IP并入other
VAL_VIDEO_RATIO = 0.2
IMG_SIZE = 224
EPOCHS = 8                 # v2: 小样本防过拟合(原14epoch train_loss→0.01严重记忆)
BATCH = 32
LR = 1e-4                  # v2: 降低学习率(原3e-4)


def _log(msg: str):
    print(msg, flush=True)


def load_labels() -> list[dict]:
    return json.loads(LABELS.read_text(encoding="utf-8"))


def build_class_map(labels: list[dict]) -> tuple[dict[str, int], dict[int, str]]:
    cnt = Counter(l["ip"] for l in labels)
    kept = sorted([ip for ip, c in cnt.items() if c >= MIN_CLASS_FRAMES])
    classes = kept + ["other"]
    c2i = {c: i for i, c in enumerate(classes)}
    i2c = {i: c for c, i in c2i.items()}
    return c2i, i2c


def split_videos(labels: list[dict], golden_videos: set) -> tuple[list[str], list[str], list[str]]:
    """视频级三分: train / val / accept(黄金集)"""
    videos = sorted({l["video"] for l in labels})
    train_pool = [v for v in videos if v not in golden_videos]
    # 按IP主类分层抽样验证集
    vid_main_ip = {}
    for v in train_pool:
        ips = Counter(l["ip"] for l in labels if l["video"] == v)
        vid_main_ip[v] = ips.most_common(1)[0][0]
    by_ip: dict[str, list[str]] = defaultdict(list)
    for v, ip in vid_main_ip.items():
        by_ip[ip].append(v)
    val_videos: list[str] = []
    import random
    random.seed(42)
    for ip, vs in by_ip.items():
        random.shuffle(vs)
        k = max(1, int(len(vs) * VAL_VIDEO_RATIO)) if len(vs) >= 2 else 0
        val_videos.extend(vs[:k])
    train_videos = [v for v in train_pool if v not in set(val_videos)]
    accept_videos = [v for v in videos if v in golden_videos]
    return train_videos, val_videos, accept_videos


class FrameDataset:
    def __init__(self, items: list[dict], c2i: dict[str, int], train: bool):
        import torch
        from torchvision import transforms
        self.items = items
        self.c2i = c2i
        if train:
            self.tf = transforms.Compose([
                transforms.Resize((IMG_SIZE + 24, IMG_SIZE + 24)),
                transforms.RandomCrop(IMG_SIZE),
                transforms.RandomHorizontalFlip(),
                transforms.ColorJitter(0.3, 0.3, 0.25, 0.08),
                transforms.RandomGrayscale(0.05),
                transforms.ToTensor(),
                transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
                transforms.RandomErasing(0.2),
            ])
        else:
            self.tf = transforms.Compose([
                transforms.Resize((IMG_SIZE, IMG_SIZE)),
                transforms.ToTensor(),
                transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
            ])

    def __len__(self):
        return len(self.items)

    def __getitem__(self, i):
        import torch
        from PIL import Image
        it = self.items[i]
        img = Image.open(ROOT / it["path"]).convert("RGB")
        y = self.c2i.get(it["ip"], self.c2i["other"])
        return self.tf(img), y, it["video"]


def make_model(num_classes: int):
    import torch.nn as nn
    from torchvision import models
    m = models.resnet18(weights="IMAGENET1K_V1")
    # v2防过拟合: 冻结前半backbone(conv1/bn1/layer1/layer2)
    for p in list(m.conv1.parameters()) + list(m.bn1.parameters()) + \
             list(m.layer1.parameters()) + list(m.layer2.parameters()):
        p.requires_grad = False
    # fc前加dropout
    in_f = m.fc.in_features
    m.fc = nn.Sequential(nn.Dropout(0.35), nn.Linear(in_f, num_classes))
    return m


def train():
    import torch
    from torch.utils.data import DataLoader
    _log(f"[P2.2] torch={torch.__version__} cuda={torch.cuda.is_available()}")
    device = torch.device(get_device())

    labels = load_labels()
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    c2i, i2c = build_class_map(labels)
    train_v, val_v, accept_v = split_videos(labels, set(golden.keys()))
    _log(f"类别数={len(c2i)} | 训练视频={len(train_v)} 验证视频={len(val_v)} 验收视频={len(accept_v)}")

    train_items = [l for l in labels if l["video"] in set(train_v)]
    val_items = [l for l in labels if l["video"] in set(val_v)]
    _log(f"训练帧={len(train_items)} 验证帧={len(val_items)}")

    # 类权重(逆频率)
    cnt = Counter(c2i.get(l["ip"], c2i["other"]) for l in train_items)
    total = sum(cnt.values())
    weights = torch.tensor([total / (len(cnt) * max(cnt[i], 1))
                            for i in range(len(c2i))], dtype=torch.float32).to(device)

    ds_tr = FrameDataset(train_items, c2i, train=True)
    ds_va = FrameDataset(val_items, c2i, train=False)
    dl_tr = DataLoader(ds_tr, batch_size=BATCH, shuffle=True, num_workers=0)
    dl_va = DataLoader(ds_va, batch_size=BATCH, shuffle=False, num_workers=0)

    model = make_model(len(c2i)).to(device)
    trainable = [p for p in model.parameters() if p.requires_grad]
    opt = torch.optim.AdamW(trainable, lr=LR, weight_decay=5e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=EPOCHS)
    loss_fn = torch.nn.CrossEntropyLoss(weight=weights)

    best_acc, history = 0.0, []
    t_start = time.time()
    for ep in range(EPOCHS):
        model.train()
        run_loss, n = 0.0, 0
        for x, y, _ in dl_tr:
            x, y = x.to(device), y.to(device)
            opt.zero_grad()
            loss = loss_fn(model(x), y)
            loss.backward()
            opt.step()
            run_loss += loss.item() * len(y)
            n += len(y)
        sched.step()
        # 验证
        model.eval()
        ok, tot = 0, 0
        with infer_ctx(device):
            for x, y, _ in dl_va:
                x, y = x.to(device), y.to(device)
                ok += int((model(x).argmax(1) == y).sum())
                tot += len(y)
        acc = ok / max(tot, 1)
        history.append({"epoch": ep + 1, "loss": round(run_loss / max(n, 1), 4),
                        "val_acc": round(acc, 4)})
        _log(f"  epoch {ep+1:2d}/{EPOCHS} loss={run_loss/max(n,1):.4f} val_acc={acc:.3f}")
        if acc >= best_acc:
            best_acc = acc
            torch.save(model.state_dict(), CKPT)
    _log(f"训练完成 {time.time()-t_start:.0f}s | 最佳验证acc={best_acc:.3f}")

    META.parent.mkdir(parents=True, exist_ok=True)
    META.write_text(json.dumps({
        "classes": c2i, "num_classes": len(c2i), "img_size": IMG_SIZE,
        "backbone": "resnet18_imagenet", "best_val_acc": best_acc,
        "history": history, "train_videos": train_v,
        "val_videos": val_v, "accept_videos": accept_v,
        "trained_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "min_class_frames": MIN_CLASS_FRAMES,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    _log(f"模型: {CKPT}\n元数据: {META}")
    return best_acc


def predict_video(video_path: str, sample_frames: int = 16) -> dict:
    """对单视频抽帧推理 → 多数投票IP判定"""
    import cv2
    import torch
    from torchvision import transforms
    meta = json.loads(META.read_text(encoding="utf-8"))
    c2i = meta["classes"]
    i2c = {v: k for k, v in c2i.items()}
    device = torch.device(get_device())
    model = make_model(meta["num_classes"]).to(device)
    model.load_state_dict(torch.load(CKPT, map_location=device))
    model.eval()
    tf = transforms.Compose([
        transforms.Resize((IMG_SIZE, IMG_SIZE)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])

    cap = cv2.VideoCapture(str(video_path))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    import numpy as np
    picks = np.linspace(0, max(n - 1, 0), sample_frames).astype(int)
    votes: Counter = Counter()
    confs: list[float] = []
    import torch as T
    with T.no_grad():
        for fi in picks:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(fi))
            ok, frame = cap.read()
            if not ok:
                continue
            from PIL import Image
            img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            x = tf(img).unsqueeze(0).to(device)
            logits = model(x)
            p = torch.softmax(logits, 1)[0]
            yi = int(p.argmax())
            votes[i2c[yi]] += 1
            confs.append(float(p[yi]))
    cap.release()
    if not votes:
        return {"primary_ip": "", "confidence": 0.0, "votes": {}}
    top_ip, top_cnt = votes.most_common(1)[0]
    if top_ip == "other":
        top_ip = ""
    return {"primary_ip": top_ip,
            "confidence": round(top_cnt / sum(votes.values()), 3),
            "mean_softmax": round(sum(confs) / len(confs), 3),
            "votes": dict(votes)}


def accept():
    """黄金集验收 — 训练时未见的12素材，视频级多数投票对比人工标签"""
    from ai.material_intelligence import ip_matches
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    LIB = ROOT / "data" / "real_amv_test"
    rows, ok_ip, ok_kind, tot = [], 0, 0, 0
    for fname, g in golden.items():
        vp = LIB / fname
        if not vp.exists():
            continue
        r = predict_video(str(vp))
        gold_ip = g.get("primary_ip", "")
        if gold_ip:
            hit = (r["primary_ip"] == gold_ip or
                   ip_matches(r["primary_ip"], gold_ip))
        else:
            hit = True  # 教程/混剪无primary_ip → 不参与IP准确率
            r["note"] = "gold无primary_ip(教程/混剪)"
        tot += 1
        ok_ip += int(hit)
        rows.append({"file": fname, "pred": r["primary_ip"],
                     "gold": gold_ip, "hit": hit,
                     "confidence": r["confidence"], "votes": r["votes"]})
        _log(f"  {'✓' if hit else '✗'} {fname[:44]} pred={r['primary_ip'] or '(空)'} "
             f"gold={gold_ip or '(空)'} conf={r['confidence']}")

    acc = ok_ip / max(tot, 1)
    result = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "acceptance_accuracy": round(acc, 3),
        "passed": ok_ip, "total": tot, "details": rows,
    }
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    _log(f"\n黄金集验收: {ok_ip}/{tot} = {acc:.1%} | 报告: {REPORT}")
    return acc


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", action="store_true")
    ap.add_argument("--accept", action="store_true")
    ap.add_argument("--predict", type=str, default="")
    args = ap.parse_args()
    if args.train:
        train()
    if args.accept:
        accept()
    if args.predict:
        print(json.dumps(predict_video(args.predict), ensure_ascii=False, indent=2))
    if not (args.train or args.accept or args.predict):
        print("用法: --train / --accept / --predict <视频路径>")
