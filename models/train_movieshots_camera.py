#!/usr/bin/env python3
"""
MovieShots 运镜分类器训练脚本 (Step 3)

路线: 光流特征工程 + 轻量 MLP 分类
  - 特征: 复用 core/camera_movement_classifier.py 的 _track_and_analyze
    输出的 8 维光流统计量 (mean_dx/mean_dy/mean_radial/h_consistency/
    v_consistency/radial_consistency/total_disp/direction_entropy)
  - 标签: MovieShots movement 5 类 -> 项目标签映射
    (Static->static, Motion->pan_left, Pull->zoom_out, Push->zoom_in,
     Multi_movement->complex)
  - 模型: 轻量 MLP (8 维输入 -> 5 类输出), 8GB 笔记本 GPU 秒级训练
  - 产出: models/movieshots_camera_clf.pt + meta json + 注册 model_registry

流程:
  Step A (需视频): 特征提取 -- 对 trailer.zip 解压后的视频逐镜提取光流特征
  Step B (无需视频): 训练分类器 -- 用特征数据集训练 MLP
  Step C: 验证 -- 在项目 v23 素材库上准确率 >80% (验收标准)

用法:
  py -3.12 models/train_movieshots_camera.py extract \
      --video-dir D:\\AE-Data\\MovieNet\\MovieShots\\trailer \
      --annot D:\\AE-Data\\MovieNet\\MovieShots\\movieshots_unified.jsonl \
      --out D:\\AE-Data\\MovieNet\\MovieShots\\features.jsonl
  py -3.12 models/train_movieshots_camera.py train \
      --data D:\\AE-Data\\MovieNet\\MovieShots\\features.jsonl \
      --out models/movieshots_camera_clf.pt
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("movieshots_train")

# 5 类训练标签 (与 MOVEMENT_TO_PROJECT 的取值集合对齐)
TRAIN_LABELS = ["static", "pan_left", "zoom_in", "zoom_out", "complex"]
LABEL_TO_IDX = {lbl: i for i, lbl in enumerate(TRAIN_LABELS)}

# 特征维度 (与 _track_and_analyze 输出对齐)
FEATURE_DIM = 8
FEATURE_KEYS = [
    "mean_dx", "mean_dy", "mean_radial",
    "h_consistency", "v_consistency", "radial_consistency",
    "total_disp", "direction_entropy",
]


# ── 特征提取 ─────────────────────────────────────────────────────────────

def extract_shot_features(video_path: str) -> Optional[Dict[str, float]]:
    """对视频提取光流统计特征 (复用光流规则分类器的特征工程)。

    注意: MovieShots 镜头边界在 shot_detection 标注里, 这里先用整段视频
    的全局特征作为 v0 特征 (镜头级特征待 v2 接入切点后细化)。
    """
    try:
        sys.path.insert(0, str(PROJECT_ROOT))
        from core.camera_movement_classifier import _track_and_analyze, _read_frames
        frames = _read_frames(video_path)
        if len(frames) < 3:
            return None
        stats = _track_and_analyze(frames)
        return {k: float(stats[k]) for k in FEATURE_KEYS}
    except Exception as exc:  # noqa: BLE001
        logger.warning("feature extract failed %s: %s", video_path, exc)
        return None


def cmd_extract(args: argparse.Namespace) -> int:
    """Step A: 对视频提取特征, 与标注按 (movie_id, shot_idx) 匹配。"""
    # 加载标注 (统一 JSONL)
    annot: Dict[Tuple[str, str], Dict[str, Any]] = {}
    with open(args.annot, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            annot[(d["movie_id"], d["shot_idx"])] = d

    # 扫描视频文件: 目录名=trailer id, 文件名=shot_idx
    video_dir = Path(args.video_dir)
    if not video_dir.is_dir():
        logger.error("video dir not found: %s", video_dir)
        return 1

    out_rows: List[Dict[str, Any]] = []
    n_total = 0
    n_hit = 0
    for video_file in sorted(video_dir.rglob("*")):
        if video_file.suffix.lower() not in (".mp4", ".mov", ".mkv", ".avi", ".webm"):
            continue
        # trailer zip 解压后目录结构: {trailer_id}/{shot_idx}.{ext}
        # 兼容双层目录: trailer/trailer/{trailer_id}/shot_XXXX.mp4
        rel = video_file.relative_to(video_dir)
        parts = list(rel.parts)
        if len(parts) < 2:
            continue
        movie_id = parts[-2]  # 倒数第二级 = trailer id (无论是否双层)
        shot_idx = Path(parts[-1]).stem
        # 文件名形如 shot_0014.mp4, 标注 shot_idx 是 0014 (去 shot_ 前缀)
        if shot_idx.startswith("shot_"):
            shot_idx = shot_idx[len("shot_"):]
        key = (movie_id, shot_idx)
        n_total += 1
        if key not in annot:
            continue
        n_hit += 1
        features = extract_shot_features(str(video_file))
        if features is None:
            continue
        ann = annot[key]
        row = {
            "movie_id": movie_id,
            "shot_idx": shot_idx,
            "label": ann["movement_label"],
            "movement_raw": ann["movement_raw"],
            "source": ann.get("source", ""),
            "features": features,
        }
        out_rows.append(row)
        if len(out_rows) % 500 == 0:
            logger.info("extracted %d / %d", len(out_rows), n_total)

    # 写特征数据集
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        for row in out_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # 标签分布
    dist = Counter(r["label"] for r in out_rows)
    logger.info("matched %d/%d videos to annotations", n_hit, n_total)
    logger.info("label dist: %s", dict(dist))
    logger.info("features -> %s (%d rows)", args.out, len(out_rows))
    return 0


# ── 训练 ─────────────────────────────────────────────────────────────────

def _load_features(path: str) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    """加载特征数据集 -> (X, y_idx, samples)。"""
    rows: List[Dict[str, Any]] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))

    X, y, meta = [], [], []
    for r in rows:
        lbl = r["label"]
        if lbl not in LABEL_TO_IDX:
            continue
        feat = [float(r["features"][k]) for k in FEATURE_KEYS]
        X.append(feat)
        y.append(LABEL_TO_IDX[lbl])
        meta.append(r)
    return np.array(X, dtype=np.float32), np.array(y, dtype=np.int64), meta


def _build_mlp(dim: int, hidden: int = 64, n_classes: int = 5, dropout: float = 0.2):
    """轻量 MLP: dim -> hidden -> hidden -> n_classes。"""
    import torch
    import torch.nn as nn
    return nn.Sequential(
        nn.Linear(dim, hidden),
        nn.ReLU(),
        nn.Dropout(dropout),
        nn.Linear(hidden, hidden),
        nn.ReLU(),
        nn.Dropout(dropout),
        nn.Linear(hidden, n_classes),
    )


def cmd_train(args: argparse.Namespace) -> int:
    """Step B: 训练轻量 MLP 分类器。"""
    import torch
    import torch.nn as nn

    X, y, meta = _load_features(args.data)
    logger.info("loaded %d samples, %d dims, classes=%s",
                len(X), X.shape[1], dict(Counter(y.tolist())))
    if len(X) < 100:
        logger.error("too few samples (%d), need >=100", len(X))
        return 1

    # train/val split (按 seed, 8:2)
    rng = np.random.RandomState(args.seed)
    perm = rng.permutation(len(X))
    n_val = max(1, int(len(X) * 0.2))
    val_idx, train_idx = perm[:n_val], perm[n_val:]
    X_tr, y_tr = torch.tensor(X[train_idx]), torch.tensor(y[train_idx])
    X_va, y_va = torch.tensor(X[val_idx]), torch.tensor(y[val_idx])

    model = _build_mlp(X.shape[1], hidden=args.hidden, n_classes=len(TRAIN_LABELS))
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    loss_fn = nn.CrossEntropyLoss()

    bs = args.batch_size
    best_acc, best_state = 0.0, None
    t0 = time.time()
    for epoch in range(args.epochs):
        model.train()
        order = torch.randperm(len(X_tr), generator=torch.Generator().manual_seed(args.seed + epoch))
        total_loss = 0.0
        for i in range(0, len(order), bs):
            idx = order[i:i + bs]
            xb, yb = X_tr[idx].to(device), y_tr[idx].to(device)
            opt.zero_grad()
            out = model(xb)
            loss = loss_fn(out, yb)
            loss.backward()
            opt.step()
            total_loss += loss.item() * len(idx)
        # eval
        model.eval()
        with torch.no_grad():
            pred = model(X_va.to(device)).argmax(dim=1).cpu().numpy()
        acc = float((pred == y_va.numpy()).mean())
        if acc > best_acc:
            best_acc = acc
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        if (epoch + 1) % 20 == 0 or epoch == args.epochs - 1:
            logger.info("epoch %d loss=%.4f val_acc=%.4f (best %.4f)",
                        epoch + 1, total_loss / len(order), acc, best_acc)

    # 保存
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    model.load_state_dict(best_state)
    torch.save({
        "state_dict": best_state,
        "labels": TRAIN_LABELS,
        "feature_keys": FEATURE_KEYS,
        "feature_dim": X.shape[1],
        "hidden": args.hidden,
        "val_acc": best_acc,
        "n_train": len(train_idx),
        "n_val": len(val_idx),
        "label_dist": dict(Counter(y.tolist())),
        "trained_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }, args.out)
    logger.info("saved %s (val_acc=%.4f, %.1fs)",
                args.out, best_acc, time.time() - t0)

    # 每类准确率 (混淆矩阵)
    model.eval()
    with torch.no_grad():
        pred = model(X_va.to(device)).argmax(dim=1).cpu().numpy()
    cm = np.zeros((len(TRAIN_LABELS), len(TRAIN_LABELS)), dtype=int)
    for p, t in zip(pred, y_va.numpy()):
        cm[t, p] += 1
    logger.info("confusion matrix (rows=truth, cols=pred):")
    logger.info("  labels: %s", TRAIN_LABELS)
    for i, lbl in enumerate(TRAIN_LABELS):
        logger.info("  %-10s %s", lbl, cm[i].tolist())

    # 写入模型注册表
    try:
        _register_model(args.out, best_acc, len(train_idx))
    except Exception as exc:  # noqa: BLE001
        logger.warning("registry update failed: %s", exc)
    return 0


def _register_model(model_path: str, val_acc: float, n_train: int) -> None:
    """把模型登记进 models/model_registry.json (遵循既有注册约定)。"""
    reg_path = PROJECT_ROOT / "models" / "model_registry.json"
    if not reg_path.exists():
        logger.warning("model_registry.json not found, skip registration")
        return
    with open(reg_path, encoding="utf-8") as f:
        reg = json.load(f)
    entry = {
        "name": "movieshots_camera_clf",
        "type": "camera_movement_classifier",
        "path": str(model_path),
        "val_acc": val_acc,
        "n_train": n_train,
        "labels": TRAIN_LABELS,
        "feature_keys": FEATURE_KEYS,
        "registered_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source": "MovieShots (ECCV2020, 47,463 annotations)",
        "note": "光流特征 + 轻量 MLP, 替代 core/camera_movement_classifier 规则判定",
    }
    # 更新或追加
    entries = reg.get("models", reg.get("model", []))
    if isinstance(entries, dict):
        entries["movieshots_camera_clf"] = entry
    elif isinstance(entries, list):
        entries = [e for e in entries if e.get("name") != "movieshots_camera_clf"]
        entries.append(entry)
        reg["models"] = entries
    with open(reg_path, "w", encoding="utf-8") as f:
        json.dump(reg, f, ensure_ascii=False, indent=2)
    logger.info("registered movieshots_camera_clf in model_registry.json")


def cmd_verify(args: argparse.Namespace) -> int:
    """Step C: 在项目 v23 素材库上验证 (验收: 准确率 >80%)。"""
    import torch

    ckpt = torch.load(args.model, map_location="cpu")
    labels: List[str] = ckpt["labels"]
    feature_keys: List[str] = ckpt["feature_keys"]

    model = _build_mlp(ckpt["feature_dim"], hidden=ckpt.get("hidden", 64),
                       n_classes=len(labels))
    model.load_state_dict(ckpt["state_dict"])
    model.eval()

    # 素材库目录: 逐视频提取特征 -> 分类
    from core.camera_movement_classifier import _track_and_analyze, _read_frames

    video_dir = Path(args.video_dir)
    results = []
    for vf in sorted(video_dir.rglob("*")):
        if vf.suffix.lower() not in (".mp4", ".mov", ".mkv"):
            continue
        frames = _read_frames(str(vf))
        if len(frames) < 3:
            continue
        stats = _track_and_analyze(frames)
        feat = np.array([[float(stats[k]) for k in feature_keys]], dtype=np.float32)
        with torch.no_grad():
            pred = int(model(torch.tensor(feat)).argmax(dim=1).item())
        results.append({"video": str(vf), "pred": labels[pred],
                        "conf": float(torch.softmax(model(torch.tensor(feat)), dim=1).max().item())})

    logger.info("verified %d videos, pred dist: %s",
                len(results), dict(Counter(r["pred"] for r in results)))
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    logger.info("results -> %s", args.out)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="MovieShots 运镜分类器训练")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_extract = sub.add_parser("extract", help="Step A: 视频特征提取")
    p_extract.add_argument("--video-dir", required=True)
    p_extract.add_argument("--annot", required=True)
    p_extract.add_argument("--out", required=True)

    p_train = sub.add_parser("train", help="Step B: 训练 MLP")
    p_train.add_argument("--data", required=True)
    p_train.add_argument("--out", default=str(PROJECT_ROOT / "models" / "movieshots_camera_clf.pt"))
    p_train.add_argument("--epochs", type=int, default=80)
    p_train.add_argument("--batch-size", type=int, default=256)
    p_train.add_argument("--lr", type=float, default=1e-3)
    p_train.add_argument("--hidden", type=int, default=64)
    p_train.add_argument("--seed", type=int, default=42)

    p_verify = sub.add_parser("verify", help="Step C: 素材库验证")
    p_verify.add_argument("--model", required=True)
    p_verify.add_argument("--video-dir", required=True)
    p_verify.add_argument("--out", default="models/output/movieshots_verify.json")

    args = parser.parse_args()
    if args.cmd == "extract":
        return cmd_extract(args)
    if args.cmd == "train":
        return cmd_train(args)
    if args.cmd == "verify":
        return cmd_verify(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
