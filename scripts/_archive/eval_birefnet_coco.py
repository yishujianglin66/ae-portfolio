"""BiRefNet 微调前后客观评估：COCO2017 验证集 person 类 IoU / 边界 F1
用法（云端，数据已挂载 /root/autodl-pub/COCO2017）:
  python eval_birefnet_coco.py --weights /path/finetuned_anime.pth --out eval_finetuned.json
  python eval_birefnet_coco.py --out eval_base.json   # 不传 --weights = 原版
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
from torchvision import transforms
from transformers import AutoModelForImageSegmentation

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root: _archive 迁移后 core.* 导入用

from core.torch_runtime import infer_ctx  # noqa: E402

COCO_ROOT = Path("/root/autodl-pub/COCO2017")
VAL_IMG = COCO_ROOT / "val2017"
VAL_ANN = COCO_ROOT / "annotations" / "instances_val2017.json"
MODEL_DIR = "external/birefnet"

tf = transforms.Compose([
    transforms.ToTensor(),
    transforms.Resize((1024, 1024)),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])


def polygon_to_mask(seg, h, w):
    """COCO polygon → mask"""
    mask = np.zeros((h, w), dtype=np.uint8)
    try:
        pts = np.array(seg, dtype=np.int32).reshape(-1, 1, 2)
        cv2.fillPoly(mask, [pts], 255)
    except Exception:
        return None
    return mask


def rle_to_mask(rle, h, w):
    import pycocotools.mask as mask_util
    return mask_util.decode(rle).astype(np.uint8) * 255


def compute_iou(pred, gt):
    inter = np.count_nonzero((pred > 127) & (gt > 127))
    union = np.count_nonzero((pred > 127) | (gt > 127))
    return inter / union if union else 0.0


def boundary_f1(pred, gt):
    """边界 F1：mask 边缘带（膨胀-腐蚀）内的像素一致率"""
    k = np.ones((5, 5), np.uint8)
    p_b = (pred > 127).astype(np.uint8)
    g_b = (gt > 127).astype(np.uint8)
    p_band = cv2.dilate(p_b, k) - cv2.erode(p_b, k)
    g_band = cv2.dilate(g_b, k) - cv2.erode(g_b, k)
    band = (p_band | g_band) > 0
    if not band.any():
        return 1.0
    tp = np.count_nonzero((p_b == g_b)[band])
    return tp / np.count_nonzero(band)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", default="")
    ap.add_argument("--out", default="eval_result.json")
    ap.add_argument("--n", type=int, default=200, help="评估样本数")
    ap.add_argument("--coco-root", default=str(COCO_ROOT), help="COCO2017 根目录")
    ap.add_argument("--model-dir", default=MODEL_DIR, help="BiRefNet 模型目录")
    args = ap.parse_args()

    coco_root = Path(args.coco_root)
    val_img = coco_root / "val2017"
    val_ann = coco_root / "annotations" / "instances_val2017.json"

    # 读标注（person 类 id=1 的实例）
    ann = json.loads(val_ann.read_text(encoding="utf-8"))
    cat_person = 1
    img_anns = {}
    for a in ann["annotations"]:
        if a["category_id"] == cat_person and a.get("iscrowd", 0) == 0 and a["area"] > 10000:
            img_anns.setdefault(a["image_id"], []).append(a)
    img_meta = {i["id"]: i for i in ann["images"]}
    cand = list(img_anns)
    random.seed(42)
    random.shuffle(cand)
    cand = cand[:args.n]

    model = AutoModelForImageSegmentation.from_pretrained(
        args.model_dir, trust_remote_code=True, local_files_only=True).cuda().half().eval()
    if args.weights:
        model.load_state_dict(torch.load(args.weights, map_location="cpu"))
        print(f"加载权重 {args.weights}", file=sys.stderr)

    ious = []
    f1s = []
    t0 = time.time()
    for iid in cand:
        meta = img_meta[iid]
        img_path = val_img / meta["file_name"]
        if not img_path.exists():
            continue
        img = cv2.imread(str(img_path))
        if img is None:
            continue
        h, w = img.shape[:2]
        # GT：该图所有 person 实例的并集
        gt = np.zeros((h, w), dtype=np.uint8)
        for a in img_anns[iid]:
            seg = a["segmentation"]
            m = None
            if isinstance(seg, list) and seg:
                m = polygon_to_mask(seg[0], h, w) if isinstance(seg[0], list) else polygon_to_mask(seg, h, w)
            elif isinstance(seg, dict):
                m = rle_to_mask(seg, h, w)
            if m is not None:
                gt = cv2.bitwise_or(gt, m)
        if not np.count_nonzero(gt):
            continue
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        inp = tf(rgb).unsqueeze(0).half().cuda()
        with infer_ctx():
            pred = model(inp)[-1].sigmoid().cpu()[0].squeeze().float().numpy()
        pred = cv2.resize(pred, (w, h), interpolation=cv2.INTER_LINEAR)
        pred_u8 = (pred * 255).astype(np.uint8)
        ious.append(compute_iou(pred_u8, gt))
        f1s.append(boundary_f1(pred_u8, gt))
        if len(ious) % 25 == 0:
            print(f"  {len(ious)}/{args.n} IoU均值 {np.mean(ious):.3f}", file=sys.stderr)

    result = {
        "weights": args.weights or "base",
        "n": len(ious),
        "IoU_mean": round(float(np.mean(ious)), 4),
        "IoU_median": round(float(np.median(ious)), 4),
        "boundaryF1_mean": round(float(np.mean(f1s)), 4),
        "elapsed_s": round(time.time() - t0, 1),
    }
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
