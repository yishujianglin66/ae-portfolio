"""MatAnyone 分段重锚定版：每 REANCHOR_EVERY 帧用 YOLO+SAM2 重新生成目标 mask 锚定
对治：长序列记忆衰减 + AMV 切镜丢目标（用户反馈 2-4s/8s+ 坏段）

用法:
  py -3.12 scripts/matanyone_reanchor.py --video <mp4> --start 100 --frames 292 \
      --outdir output/step2_locator/matanyone_ra --reanchor-every 48
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn.functional as F

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "external" / "matanyone" / "repo"))
sys.path.insert(0, str(PROJECT / "scripts"))

from infer_segment_video_enhanced import (  # noqa: E402
    YOLOFallbackDetector,
    build_image_predictor,
    sam_single_frame_predict,
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default=str(PROJECT / "data/real_amv_test/DL_FATE_r978_BV1qb411C79B_p1.mp4"))
    ap.add_argument("--start", type=int, default=100)
    ap.add_argument("--frames", type=int, default=292)
    ap.add_argument("--outdir", default="output/step2_locator/matanyone_ra")
    ap.add_argument("--ckpt", default=str(PROJECT / "external/matanyone/weights/matanyone.pth"))
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--max_size", type=int, default=384)
    ap.add_argument("--reanchor-every", type=int, default=48, help="每 N 帧重新锚定（2 秒 @24fps）")
    ap.add_argument("--conf", type=float, default=0.3)
    args = ap.parse_args()

    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    seg_video = out / "segment.mp4"
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-y",
                        "-ss", str(args.start / 24.0), "-i", args.video,
                        "-frames:v", str(args.frames), "-c:v", "libx264", "-preset", "fast",
                        "-crf", "18", "-pix_fmt", "yuv420p", str(seg_video)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f"ffmpeg failed: {r.stderr[-400:]}", file=sys.stderr)
        return 1

    # ---- SAM2 单帧检测器（重锚定用，全程保留） ----
    params = {
        "sam2_checkpoint": r"D:\AE-Work\models\sam2\sam2.1_hiera_large.pt",
        "sam_variant": "large",
        "model_cfg": "sam2.1_hiera_l.yaml",
        "yolov8x_path": r"D:\AE-Work\models\yolov8\yolov8x.pt",
    }
    yolo = YOLOFallbackDetector(model_path=params["yolov8x_path"], conf=args.conf)
    print("[SAM2-IMG] loading image predictor...", file=sys.stderr)
    pred = build_image_predictor(params)

    # 读原视频帧（重锚定检测用）
    cap = cv2.VideoCapture(args.video)
    cap.set(cv2.CAP_PROP_POS_FRAMES, args.start)
    src_frames = {}
    for i in range(args.frames):
        ret, frame = cap.read()
        if not ret:
            break
        src_frames[args.start + i] = frame
    cap.release()

    # ---- MatAnyone 模型（CPU 加载权重 + 手动 config） ----
    from omegaconf import OmegaConf
    _repo = PROJECT / "external" / "matanyone" / "repo"
    _cfg_dir = _repo / "matanyone" / "config"
    model_cfg = OmegaConf.load(str(_cfg_dir / "model" / "base.yaml"))
    cfg = OmegaConf.create({
        "weights": args.ckpt, "amp": False, "max_internal_size": -1,
        "save_all": True, "use_all_masks": False, "use_long_term": False,
        "mem_every": 5, "max_mem_frames": 5, "top_k": 30, "stagger_updates": 5,
        "chunk_size": -1, "save_scores": False, "save_aux": False,
        "visualize": False, "flip_aug": False, "output_dir": None,
        "long_term": {"count_usage": True, "max_mem_frames": 10, "min_mem_frames": 5,
                      "num_prototypes": 128, "max_num_tokens": 10000, "buffer_tokens": 2000},
    })
    cfg.model = model_cfg
    from matanyone.inference.inference_core import InferenceCore
    from matanyone.model.matanyone import MatAnyone
    from matanyone.utils.inference_utils import read_frame_from_videos
    matanyone = MatAnyone(cfg, single_object=True).to(args.device).eval()
    mw = torch.load(args.ckpt, map_location="cpu")
    matanyone.load_weights(mw)
    del mw
    torch.cuda.empty_cache()
    processor = InferenceCore(matanyone, cfg=matanyone.cfg)
    print("[MATANYONE] ready", file=sys.stderr)

    vframes, fps, length, _ = read_frame_from_videos(str(seg_video))
    n_warmup = 5
    rep = vframes[0].unsqueeze(0).repeat(n_warmup, 1, 1, 1)
    vframes = torch.cat([rep, vframes], dim=0).float()
    length += n_warmup
    h0, w0 = vframes.shape[-2:]
    min_side = min(h0, w0)
    new_h, new_w = h0, w0
    if args.max_size > 0 and min_side > args.max_size:
        new_h = int(h0 / min_side * args.max_size)
        new_w = int(w0 / min_side * args.max_size)
        vframes = F.interpolate(vframes, size=(new_h, new_w), mode="area")

    alpha_dir = out / "alpha"
    alpha_dir.mkdir(exist_ok=True)
    t0 = time.time()
    areas = []
    n_anchor_ok = 0
    n_anchor_fail = 0

    def make_anchor_mask(gi: int) -> torch.Tensor | None:
        """YOLO+SAM2 生成 gi 帧的目标 mask（缩放后）"""
        frame = src_frames.get(gi)
        if frame is None:
            return None
        boxes = yolo.detect(frame)
        boxes = sorted(boxes, key=lambda b: (b[2]-b[0])*(b[3]-b[1]), reverse=True)[:1]
        if not boxes:
            return None
        m = sam_single_frame_predict(pred, frame, boxes, top_k=1, max_area_ratio=0)
        if np.count_nonzero(m) < 100:
            return None
        mt = torch.from_numpy(m).float().to(args.device)
        if (new_h, new_w) != (h0, w0):
            mt = F.interpolate(mt.unsqueeze(0).unsqueeze(0), size=(new_h, new_w), mode="nearest")[0, 0]
        return mt

    cur_mask: torch.Tensor | None = None
    for ti in range(length):
        image = (vframes[ti] / 255.0).float().to(args.device)
        # 重锚定时机（原片帧号）
        orig_gi = args.start + (ti - n_warmup)
        is_anchor_point = (ti == 0) or (ti > n_warmup and (ti - n_warmup) % args.reanchor_every == 0)
        with torch.inference_mode():
            if is_anchor_point and ti > 0:
                anchor = make_anchor_mask(orig_gi) if orig_gi in src_frames else None
                if anchor is not None:
                    cur_mask = anchor
                    processor.clear_memory()  # 关键：清旧记忆再重锚定（否则新旧目标混合→糊块）
                    output_prob = processor.step(image, cur_mask, objects=[1])
                    output_prob = processor.step(image, first_frame_pred=True)  # 锚定后需预测步才出 alpha
                    n_anchor_ok += 1
                else:
                    n_anchor_fail += 1
                    output_prob = processor.step(image)
            elif ti == 0:
                anchor = make_anchor_mask(args.start)
                if anchor is None:
                    print("首帧锚定失败", file=sys.stderr)
                    return 2
                cur_mask = anchor
                output_prob = processor.step(image, cur_mask, objects=[1])
                output_prob = processor.step(image, first_frame_pred=True)
                n_anchor_ok += 1
            elif ti <= n_warmup:
                output_prob = processor.step(image, first_frame_pred=True)
            else:
                output_prob = processor.step(image)
        m = processor.output_prob_to_mask(output_prob)
        pha = (m.detach().unsqueeze(2).cpu().numpy() * 255).astype(np.uint8)
        if ti > n_warmup - 1:
            gi = args.start + (ti - n_warmup)
            pha_out = pha if (new_h, new_w) == (h0, w0) else cv2.resize(pha, (w0, h0), interpolation=cv2.INTER_LINEAR)
            cv2.imencode(".png", pha_out)[1].tofile(str(alpha_dir / f"alpha_{gi:05d}.png"))
            areas.append(float(np.count_nonzero(pha_out)) / (h0 * w0))

    dt = time.time() - t0
    v = np.array(areas)
    print(json.dumps({
        "frames": len(areas), "anchors_ok": n_anchor_ok, "anchors_fail": n_anchor_fail,
        "area_median": round(float(np.median(v)), 3),
        "gt50pct": int((v > 0.5).sum()), "missing_lt1pct": int((v < 0.01).sum()),
        "nonempty": int((v > 0.001).sum()),
        "elapsed_s": round(dt, 1), "outdir": str(out),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
