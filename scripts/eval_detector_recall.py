"""检测器召回率评估：YOLO/Owlv2 在 COCO person 类 bbox 上的召回/精度
（量化"锚定检测"组件质量，B2 任务）
用法（云端）: python eval_detector_recall.py --detector yolo --out recall_yolo.json
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch

from core.torch_runtime import get_device, infer_ctx

COCO_ROOT = Path("/root/autodl-pub/COCO2017")
VAL_IMG = COCO_ROOT / "val2017"
VAL_ANN = COCO_ROOT / "annotations" / "instances_val2017.json"


def iou_box(a, b):
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua else 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--detector", choices=["yolo", "owlv2"], default="yolo")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--out", default="recall.json")
    args = ap.parse_args()

    ann = json.loads(VAL_ANN.read_text(encoding="utf-8"))
    img_anns = {}
    for a in ann["annotations"]:
        if a["category_id"] == 1 and a.get("iscrowd", 0) == 0:
            img_anns.setdefault(a["image_id"], []).append(a["bbox"])
    img_meta = {i["id"]: i for i in ann["images"]}
    cand = list(img_anns)
    random.seed(42)
    random.shuffle(cand)
    cand = cand[:args.n]

    if args.detector == "yolo":
        sys.path.insert(0, "scripts")
        from infer_segment_video_enhanced import YOLOFallbackDetector
        det = YOLOFallbackDetector(model_path="models/yolov8x.pt", conf=0.3)
        detect = det.detect
    else:
        from transformers import Owlv2ForObjectDetection, Owlv2Processor
        model = Owlv2ForObjectDetection.from_pretrained("external/owlv2", local_files_only=True).eval().cuda()
        proc = Owlv2Processor.from_pretrained("external/owlv2", local_files_only=True)

        def detect(img_bgr):
            rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
            with infer_ctx(get_device()):
                inputs = proc(text=[["person"]], images=rgb, return_tensors="pt").to("cuda")
                outputs = model(**inputs)
                results = proc.post_process_grounded_object_detection(
                    outputs=outputs, target_sizes=torch.tensor([rgb.shape[:2]]), threshold=0.15)
            boxes = results[0]["boxes"].cpu().numpy()
            scores = results[0]["scores"].cpu().numpy()
            return [[int(b[0]), int(b[1]), int(b[2]), int(b[3])] for b, s in zip(boxes, scores) if s >= 0.15]

    # COCO bbox 是 [x, y, w, h] → [x1, y1, x2, y2]
    tp = fp = fn = 0
    t0 = time.time()
    for iid in cand:
        meta = img_meta[iid]
        img = cv2.imread(str(VAL_IMG / meta["file_name"]))
        if img is None:
            continue
        gts = [[b[0], b[1], b[0] + b[2], b[1] + b[3]] for b in img_anns[iid]]
        dets = detect(img)
        matched = [False] * len(gts)
        for d in dets:
            best_i, best_v = -1, 0.0
            for gi, g in enumerate(gts):
                if matched[gi]:
                    continue
                v = iou_box(d, g)
                if v > best_v:
                    best_i, best_v = gi, v
            if best_i >= 0 and best_v >= 0.5:
                matched[best_i] = True
                tp += 1
            else:
                fp += 1
        fn += sum(1 for m in matched if not m)

    recall = tp / max(tp + fn, 1)
    precision = tp / max(tp + fp, 1)
    result = {
        "detector": args.detector,
        "n_images": len(cand),
        "TP": tp, "FP": fp, "FN": fn,
        "recall": round(recall, 4),
        "precision": round(precision, 4),
        "F1": round(2 * recall * precision / max(recall + precision, 1e-9), 4),
        "elapsed_s": round(time.time() - t0, 1),
    }
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
