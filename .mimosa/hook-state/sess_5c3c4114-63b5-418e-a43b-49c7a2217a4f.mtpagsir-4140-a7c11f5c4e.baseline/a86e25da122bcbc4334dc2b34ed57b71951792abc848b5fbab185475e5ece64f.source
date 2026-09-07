#!/usr/bin/env python3
"""
VideoMAE-MovieShots 运镜分类验证脚本 (Step 3 集成 V1)

加载现成 VideoMAE 微调模型 (gullalc/videomae-base-finetuned-kinetics-
movieshots-movement, MIT), 在项目素材上做镜头级运镜分类。

用途:
  1. 验证模型在动漫素材上的可用性 (P0 A1)
  2. 与现有光流规则 (core/camera_movement_classifier.py) 对照
  3. 输出可被 ai/camera_decision.py SourceCameraInventory.inject() 消费的标签

用法:
  py -3.12 models/verify_movieshots_videomae.py \
      --video-dir data\\real_amv_test --out models/output/videomae_verify.json
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import torch
from core.torch_runtime import infer_ctx

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("videomae_verify")

MODEL_ID = "gullalc/videomae-base-finetuned-kinetics-movieshots-movement"
LOCAL_DIR = r"D:\AE-Data\Models\VideoMAE-MovieShots\movement"

# MovieShots 运镜类别 (模型输出顺序, 以 config.id2label 为准, 这里兜底)
FALLBACK_LABELS = ["Static", "Motion", "Pull", "Push", "Multi_movement"]


def load_model():
    from transformers import VideoMAEImageProcessor, VideoMAEForVideoClassification
    proc = VideoMAEImageProcessor.from_pretrained(LOCAL_DIR)
    model = VideoMAEForVideoClassification.from_pretrained(LOCAL_DIR)
    model.eval()
    if torch.cuda.is_available():
        model.to("cuda")
    labels = list(model.config.id2label.values()) if hasattr(model.config, "id2label") else FALLBACK_LABELS
    return proc, model, labels


def load_video_frames(video_path: str, n_frames: int = 16, target_size: int = 224):
    """用 decord 读取视频, 均匀采样 n_frames 帧 -> (T,C,H,W) 归一化张量。"""
    from decord import VideoReader, cpu
    vr = VideoReader(str(video_path), ctx=cpu(0))
    n = len(vr)
    if n < 2:
        return None
    if n <= n_frames:
        idxs = list(range(n))
    else:
        step = (n - 1) / (n_frames - 1)
        idxs = [round(i * step) for i in range(n_frames)]
    frames = vr.get_batch(idxs).asnumpy()  # (T,H,W,C) 0-255
    import numpy as np
    frames = frames.astype(np.float32)
    # (T,H,W,C) -> (T,C,H,W)
    frames = frames.transpose(0, 3, 1, 2)
    # 缩放到 224
    from torchvision.transforms import v2
    resize = v2.Resize((target_size, target_size))
    frames = resize(torch.from_numpy(frames))
    return frames  # (T,3,224,224) 0-255


def classify_video(proc, model, labels, video_path: str) -> Dict[str, Any]:
    frames = load_video_frames(video_path)
    if frames is None:
        return {"video": str(video_path), "error": "too short / unreadable"}

    # 归一化 (使用模型 preprocessor)
    inputs = proc(frames, return_tensors="pt")
    device = next(model.parameters()).device
    inputs = {k: v.to(device) for k, v in inputs.items()}

    t0 = time.time()
    with infer_ctx(device):
        logits = model(**inputs).logits
    probs = torch.softmax(logits, dim=-1)[0]
    top_idx = int(probs.argmax().item())
    elapsed = time.time() - t0

    return {
        "video": str(video_path),
        "label": labels[top_idx] if top_idx < len(labels) else "Unknown",
        "label_idx": top_idx,
        "confidence": round(float(probs[top_idx].item()), 4),
        "probs": {labels[i]: round(float(probs[i].item()), 4) for i in range(len(labels))},
        "infer_seconds": round(elapsed, 3),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="VideoMAE MovieShots 运镜分类验证")
    parser.add_argument("--video-dir", required=True, help="素材目录 (递归扫描视频)")
    parser.add_argument("--video", help="单个视频文件 (优先)")
    parser.add_argument("--out", default="models/output/videomae_verify.json")
    parser.add_argument("--ext", default=".mp4,.mov,.mkv,.avi,.webm,.flv")
    args = parser.parse_args()

    proc, model, labels = load_model()
    logger.info("model loaded: %s, labels=%s, device=%s",
                MODEL_ID, labels, next(model.parameters()).device)

    video_paths: List[Path] = []
    if args.video:
        video_paths = [Path(args.video)]
    else:
        exts = tuple(e.strip() for e in args.ext.split(","))
        video_dir = Path(args.video_dir)
        video_paths = [p for p in sorted(video_dir.rglob("*")) if p.suffix.lower() in exts]

    results = []
    for i, vp in enumerate(video_paths):
        try:
            r = classify_video(proc, model, labels, str(vp))
        except Exception as exc:  # noqa: BLE001
            logger.warning("failed %s: %s", vp.name, exc)
            r = {"video": str(vp), "error": str(exc)}
        results.append(r)
        if "error" in r:
            logger.warning("[%d/%d] skip %s: %s", i + 1, len(video_paths), vp.name, r["error"])
        else:
            logger.info("[%d/%d] %s -> %s (%.3f)", i + 1, len(video_paths),
                        vp.name, r["label"], r["confidence"])

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    logger.info("results -> %s (%d videos)", out, len(results))

    # 与光流规则对照 (可选)
    if not args.video and results:
        try:
            from core.camera_movement_classifier import classify_video as rule_classify
            logger.info("=== 光流规则对照 ===")
            for r in results:
                if "error" in r:
                    continue
                rule = rule_classify(r["video"])
                logger.info("%s | VideoMAE=%s | 规则=%s (conf %.2f)",
                            Path(r["video"]).name, r["label"], rule["dominant"], rule["confidence"])
        except Exception as exc:  # noqa: BLE001
            logger.warning("rule comparison skipped: %s", exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
