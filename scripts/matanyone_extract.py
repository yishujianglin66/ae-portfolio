"""MatAnyone 集成：本地权重 + 目标 mask 生成 + 视频 alpha 提取

流程: 找首个可检测人物帧 → 截视频段(ffmpeg) → SAM2 生成该帧目标 mask
     → MatAnyone 记忆传播逐帧抠像 → alpha PNG 序列 → 面积统计

用法:
  py -3.12 scripts/matanyone_extract.py --video <mp4> --start <首个有人物帧> --frames 200 --outdir <dir>
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "external" / "matanyone" / "repo"))
sys.path.insert(0, str(PROJECT / "scripts"))

from infer_segment_video_enhanced import (  # noqa: E402
    build_image_predictor, sam_single_frame_predict, YOLOFallbackDetector,
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default=str(PROJECT / "data/real_amv_test/DL_FATE_r978_BV1qb411C79B_p1.mp4"))
    ap.add_argument("--start", type=int, default=0, help="目标锚定帧（首个有人物帧）")
    ap.add_argument("--frames", type=int, default=200)
    ap.add_argument("--outdir", default="output/step2_locator/matanyone_out")
    ap.add_argument("--ckpt", default=str(PROJECT / "external/matanyone/weights/model.safetensors"))
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--max_size", type=int, default=512, help="长边上限（8GB 显存需 ≤512）")
    args = ap.parse_args()

    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)

    # ---- 1. 截视频段（从锚定帧开始） ----
    seg_video = out / "segment.mp4"
    import subprocess
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-y",
                        "-ss", str(args.start / 24.0), "-i", args.video,
                        "-frames:v", str(args.frames), "-c:v", "libx264", "-preset", "fast",
                        "-crf", "18", "-pix_fmt", "yuv420p", str(seg_video)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f"ffmpeg failed: {r.stderr[-500:]}", file=sys.stderr)
        return 1

    # ---- 2. 目标 mask：锚定帧 YOLO+SAM2 ----
    cap = cv2.VideoCapture(args.video)
    cap.set(cv2.CAP_PROP_POS_FRAMES, args.start)
    ret, frame = cap.read()
    cap.release()
    params = {
        "sam2_checkpoint": r"D:\AE-Work\models\sam2\sam2.1_hiera_large.pt",
        "sam_variant": "large",
        "model_cfg": "sam2.1_hiera_l.yaml",
        "yolov8x_path": r"D:\AE-Work\models\yolov8\yolov8x.pt",
    }
    yolo = YOLOFallbackDetector(model_path=params["yolov8x_path"], conf=0.3)
    boxes = yolo.detect(frame)
    boxes = sorted(boxes, key=lambda b: (b[2]-b[0])*(b[3]-b[1]), reverse=True)[:1]
    if not boxes:
        print("锚定帧无检测目标", file=sys.stderr)
        return 2
    print(f"目标框: {boxes[0]}", file=sys.stderr)
    pred = build_image_predictor(params)
    tgt = sam_single_frame_predict(pred, frame, boxes, top_k=1, max_area_ratio=0)
    h, w = tgt.shape[:2]
    print(f"目标 mask 面积: {np.count_nonzero(tgt)/(h*w):.3f}", file=sys.stderr)
    mask_png = out / "target_mask.png"
    cv2.imencode(".png", tgt)[1].tofile(str(mask_png))
    del pred, yolo
    torch.cuda.empty_cache()

    # ---- 3. MatAnyone 逐帧 ----
    from hydra.core.global_hydra import GlobalHydra
    GlobalHydra.instance().clear()  # 清理可能的残留初始化
    _old_cwd = Path.cwd()
    _repo = PROJECT / "external" / "matanyone" / "repo"
    import os
    os.chdir(str(_repo / "matanyone" / "utils"))  # hydra config_path 相对 cwd 解析
    try:
        from matanyone.utils.get_default_model import get_matanyone_model
        from matanyone.inference.inference_core import InferenceCore
        from matanyone.utils.inference_utils import read_frame_from_videos
    finally:
        os.chdir(str(_old_cwd))

    print("[MATANYONE] loading model...", file=sys.stderr)
    from omegaconf import OmegaConf
    # 手动构造 config（绕开 hydra 相对路径问题）
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
    from matanyone.model.matanyone import MatAnyone
    matanyone = MatAnyone(cfg, single_object=True).to(args.device).eval()
    model_weights = torch.load(args.ckpt, map_location="cpu")  # CPU 加载省显存
    matanyone.load_weights(model_weights)
    del model_weights
    torch.cuda.empty_cache()
    processor = InferenceCore(matanyone, cfg=matanyone.cfg)
    print("[MATANYONE] model ready", file=sys.stderr)

    vframes, fps, length, _ = read_frame_from_videos(str(seg_video))
    n_warmup = 5
    rep = vframes[0].unsqueeze(0).repeat(n_warmup, 1, 1, 1)
    vframes = torch.cat([rep, vframes], dim=0).float()
    length += n_warmup

    mask = cv2.imdecode(np.fromfile(str(mask_png), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    mask = torch.from_numpy(mask).float().to(args.device)

    # 8GB 显存：按 max_size 缩放帧与 mask
    import torch.nn.functional as F
    h0, w0 = vframes.shape[-2:]
    min_side = min(h0, w0)
    new_h, new_w = h0, w0
    if args.max_size > 0 and min_side > args.max_size:
        new_h = int(h0 / min_side * args.max_size)
        new_w = int(w0 / min_side * args.max_size)
        vframes = F.interpolate(vframes, size=(new_h, new_w), mode="area")
        mask = F.interpolate(mask.unsqueeze(0).unsqueeze(0), size=(new_h, new_w), mode="nearest")[0, 0]
    print(f"[MATANYONE] input {w0}x{h0} -> {new_w}x{new_h}", file=sys.stderr)

    alpha_dir = out / "alpha"
    alpha_dir.mkdir(exist_ok=True)
    t0 = time.time()
    areas = []
    for ti in range(length):
        image = vframes[ti]
        image = (image / 255.0).float().to(args.device)
        with torch.inference_mode():  # 无梯度推理（不用 autocast：与 MatAnyone 内部 stream 冲突）
            if ti == 0:
                output_prob = processor.step(image, mask, objects=[1])
                output_prob = processor.step(image, first_frame_pred=True)
            elif ti <= n_warmup:
                output_prob = processor.step(image, first_frame_pred=True)
            else:
                output_prob = processor.step(image)
        m = processor.output_prob_to_mask(output_prob)
        pha = (m.detach().unsqueeze(2).cpu().numpy() * 255).astype(np.uint8)
        if ti > n_warmup - 1:
            gi = args.start + (ti - n_warmup)
            pha_out = pha
            if (new_h, new_w) != (h0, w0):
                pha_out = cv2.resize(pha, (w0, h0), interpolation=cv2.INTER_LINEAR)
            cv2.imencode(".png", pha_out)[1].tofile(str(alpha_dir / f"alpha_{gi:05d}.png"))
            areas.append(float(np.count_nonzero(pha_out)) / (h0 * w0))
    dt = time.time() - t0
    v = np.array(areas)
    print(f"[MATANYONE] done {len(areas)} frames in {dt:.1f}s ({dt/max(len(areas),1):.3f} s/f)", file=sys.stderr)
    import json
    print(json.dumps({
        "frames": len(areas),
        "area_median": round(float(np.median(v)), 3),
        "gt50pct": int((v > 0.5).sum()), "gt80pct": int((v > 0.8).sum()),
        "nonempty": int((v > 0.001).sum()),
        "elapsed_s": round(dt, 1),
        "outdir": str(out),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
