"""MatAnyone 分段独立抠像：每 SEG_LEN 帧独立跑（全新 InferenceCore，无跨段记忆污染）
对治：长序列记忆衰减 + AMV 切镜丢目标。段内锚定+传播，段间拼接 + 可选 MED 平滑。

用法:
  py -3.12 scripts/matanyone_segments.py --video <mp4> --start 100 --frames 292 \
      --outdir output/step2_locator/matanyone_seg --seg-len 48
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn.functional as F

# torchvision>=0.17 兼容: read_video 移入子模块且 0.28 需 pytorch.fb 布局(缺失)
# → 用 cv2 自实现等价函数注入 (全帧 RGB TCHW + fps 元数据)
import torchvision  # noqa: E402

from core.torch_runtime import get_device, infer_ctx

if not hasattr(torchvision.io, "read_video"):
    def _read_video_cv2(filename: str, pts_unit: str = "sec", output_format: str = "TCHW"):
        cap = cv2.VideoCapture(filename)
        fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
        frames = []
        while True:
            ret, f = cap.read()
            if not ret:
                break
            frames.append(f[..., ::-1])  # BGR→RGB
        cap.release()
        arr = np.stack(frames)  # THWC RGB
        t = torch.from_numpy(arr).permute(0, 3, 1, 2).contiguous()
        return t, None, {"video_fps": float(fps)}
    torchvision.io.read_video = _read_video_cv2

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "external" / "matanyone" / "repo"))
sys.path.insert(0, str(PROJECT / "scripts"))

from infer_segment_video_enhanced import (  # noqa: E402
    YOLOFallbackDetector,
    build_image_predictor,
    sam_single_frame_predict,
)


def build_processor(ckpt: str, device: str):
    from omegaconf import OmegaConf
    _repo = PROJECT / "external" / "matanyone" / "repo"
    _cfg_dir = _repo / "matanyone" / "config"
    model_cfg = OmegaConf.load(str(_cfg_dir / "model" / "base.yaml"))
    cfg = OmegaConf.create({
        "weights": ckpt, "amp": False, "max_internal_size": -1,
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
    matanyone = MatAnyone(cfg, single_object=True).to(device).eval()
    mw = torch.load(ckpt, map_location="cpu")
    matanyone.load_weights(mw)
    del mw
    torch.cuda.empty_cache()
    return matanyone, InferenceCore(matanyone, cfg=matanyone.cfg)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default=str(PROJECT / "data/real_amv_test/DL_FATE_r978_BV1qb411C79B_p1.mp4"))
    ap.add_argument("--start", type=int, default=100)
    ap.add_argument("--frames", type=int, default=292)
    ap.add_argument("--outdir", default="output/step2_locator/matanyone_seg")
    ap.add_argument("--ckpt", default=str(PROJECT / "external/matanyone/weights/matanyone.pth"))
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--max_size", type=int, default=512, help="长边上限（分段跑显存宽裕，512 提升边缘精度）")
    ap.add_argument("--seg-len", type=int, default=48, help="每段帧数（2 秒 @24fps）")
    ap.add_argument("--conf", type=float, default=0.3)
    ap.add_argument("--anchor-max", type=float, default=0.40, help="锚定 mask 面积上限")
    ap.add_argument("--manual-anchors", default="", help="人工锚定框（优先于自动检测）：'帧号:x1,y1,x2,y2;帧号2:x1,y1,x2,y2'")
    args = ap.parse_args()
    manual_anchors = {}
    if args.manual_anchors:
        for part in args.manual_anchors.split(";"):
            part = part.strip()
            if not part:
                continue
            try:
                gi_s, box_s = part.split(":")
                x1, y1, x2, y2 = [int(v) for v in box_s.split(",")]
                manual_anchors[int(gi_s)] = [x1, y1, x2, y2]
            except Exception as e:
                print(f"manual anchor parse err: {part} ({e})", file=sys.stderr)
    if manual_anchors:
        print(f"[MANUAL] 人工锚定点: {manual_anchors}", file=sys.stderr)

    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)

    params = {
        "sam2_checkpoint": r"D:\AE-Work\models\sam2\sam2.1_hiera_large.pt",
        "sam_variant": "large",
        "model_cfg": "sam2.1_hiera_l.yaml",
        "yolov8x_path": r"D:\AE-Work\models\yolov8\yolov8x.pt",
    }
    yolo = YOLOFallbackDetector(model_path=params["yolov8x_path"], conf=args.conf)
    print("[SAM2-IMG] loading image predictor...", file=sys.stderr)
    pred = build_image_predictor(params)
    # Owlv2 开放词汇检测（YOLO 失败时兜底：转身/亮场段人物检测）
    _owl_holder = {"m": None, "p": None}

    def get_owl():
        if _owl_holder["m"] is None:
            from transformers import Owlv2ForObjectDetection, Owlv2Processor
            _owl_holder["m"] = Owlv2ForObjectDetection.from_pretrained(
                "external/owlv2", local_files_only=True).eval().cuda()
            _owl_holder["p"] = Owlv2Processor.from_pretrained("external/owlv2", local_files_only=True)
            print("[OWLV2] ready", file=sys.stderr)
        return _owl_holder["m"], _owl_holder["p"]

    OWL_TEXTS = [["anime character"], ["person"]]

    def owl_detect(frame_bgr: np.ndarray) -> list[list[int]]:
        """Owlv2 检测人物框（BGR 输入）"""
        try:
            m, p = get_owl()
            rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            with infer_ctx(get_device()):
                inputs = p(text=OWL_TEXTS, images=rgb, return_tensors="pt").to("cuda")
                outputs = m(**inputs)
                results = p.post_process_grounded_object_detection(
                    outputs=outputs, target_sizes=torch.tensor([rgb.shape[:2]]), threshold=0.15)
            boxes = results[0]["boxes"].cpu().numpy()
            scores = results[0]["scores"].cpu().numpy()
            return [[int(b[0]), int(b[1]), int(b[2]), int(b[3])]
                    for b, s in zip(boxes, scores) if s >= 0.15]
        except Exception as e:
            print(f"[OWLV2] err: {e}", file=sys.stderr)
            return []
    # 全图自动分割器（YOLO 检测失败时的锚定兜底：转身/模糊段人物无检测框但自动分割可找到）
    _auto_gen_holder = {"g": None}

    def get_auto_gen():
        if _auto_gen_holder["g"] is None:
            from sam2.automatic_mask_generator import SAM2AutomaticMaskGenerator
            from sam2.build_sam import build_sam2
            _sam2 = build_sam2(config_file="configs/sam2.1/sam2.1_hiera_l.yaml",
                               ckpt_path=params["sam2_checkpoint"], device="cuda",
                               mode="eval", apply_postprocessing=True)
            _auto_gen_holder["g"] = SAM2AutomaticMaskGenerator(
                _sam2, points_per_side=16, pred_iou_thresh=0.7, min_mask_region_area=2000)
            print("[AUTO-SEG] automatic mask generator ready", file=sys.stderr)
        return _auto_gen_holder["g"]

    def auto_find_mask(frame_bgr: np.ndarray) -> np.ndarray | None:
        """全图自动分割找面积 [1%,40%] 且 IoU 最高的 mask"""
        try:
            gen = get_auto_gen()
            rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            masks = gen.generate(rgb)
        except Exception as e:
            print(f"[AUTO-SEG] err: {e}", file=sys.stderr)
            return None
        h, w = frame_bgr.shape[:2]
        best = None
        best_score = -1
        for m in masks:
            area = float(m["area"]) / (h * w)
            if 0.01 <= area <= args.anchor_max:
                score = float(m.get("predicted_iou", 0))
                if score > best_score:
                    best_score = score
                    best = (m["segmentation"].astype(np.uint8) * 255)
        return best

    cap = cv2.VideoCapture(args.video)
    cap.set(cv2.CAP_PROP_POS_FRAMES, args.start)
    src_frames = {}
    for i in range(args.frames):
        ret, frame = cap.read()
        if not ret:
            break
        src_frames[args.start + i] = frame
    cap.release()

    matanyone, processor = build_processor(args.ckpt, args.device)
    print("[MATANYONE] ready", file=sys.stderr)

    alpha_dir = out / "alpha"
    alpha_dir.mkdir(exist_ok=True)
    t0 = time.time()
    all_areas = []
    n_seg = 0
    n_anchor_fail = 0

    for seg_start in range(args.start, args.start + args.frames, args.seg_len):
        seg_end = min(seg_start + args.seg_len, args.start + args.frames)
        seg_len = seg_end - seg_start
        # 抽段视频
        seg_video = out / f"seg_{seg_start}_{seg_end}.mp4"
        r = subprocess.run(["ffmpeg", "-loglevel", "error", "-y",
                            "-ss", str(seg_start / 24.0), "-i", args.video,
                            "-frames:v", str(seg_len), "-c:v", "libx264", "-preset", "fast",
                            "-crf", "18", "-pix_fmt", "yuv420p", str(seg_video)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            print(f"ffmpeg failed: {r.stderr[-300:]}", file=sys.stderr)
            return 1

        from matanyone.utils.inference_utils import read_frame_from_videos
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

        # 锚定 mask（人工锚定优先；否则 YOLO+SAM2，面积须在 [1%,anchor_max]，否则向后滑帧找好锚点）
        frame0 = None
        boxes = []
        m0 = None
        anchor_gi = seg_start
        # 人工锚定：找段内第一个有人工框的帧
        for slide in range(0, seg_len):
            g = seg_start + slide
            if g in manual_anchors:
                f = src_frames.get(g)
                if f is not None:
                    frame0, boxes, m0, anchor_gi = f, [manual_anchors[g]], \
                        sam_single_frame_predict(pred, f, [manual_anchors[g]], top_k=1, max_area_ratio=0), g
                    print(f"  [SEG {seg_start}] 人工锚定帧 {g} box={manual_anchors[g]}", file=sys.stderr)
                    break
        if frame0 is None:
            slide_max = min(25, seg_len - 1)
            for slide in range(0, slide_max + 1):
                g = seg_start + slide
                if g >= seg_start + seg_len:
                    break
                f = src_frames.get(g)
                if f is None:
                    continue
                bs = yolo.detect(f)
                bs = sorted(bs, key=lambda b: (b[2]-b[0])*(b[3]-b[1]), reverse=True)[:1]
                if not bs:
                    # YOLO 失败 → Owlv2 开放词汇检测兜底
                    bs = owl_detect(f)
                    bs = sorted(bs, key=lambda b: (b[2]-b[0])*(b[3]-b[1]), reverse=True)[:1]
                if not bs:
                    # Owlv2 也失败 → 全图自动分割兜底（转身/模糊段）
                    m_auto = auto_find_mask(f)
                    if m_auto is not None and np.count_nonzero(m_auto) >= 100:
                        frame0, boxes, m0, anchor_gi = f, [], m_auto, g
                        print(f"  [SEG {seg_start}] 自动分割锚定帧 {g}", file=sys.stderr)
                        break
                    continue
                m_cand = sam_single_frame_predict(pred, f, bs, top_k=1, max_area_ratio=0)
                area_cand = float(np.count_nonzero(m_cand)) / (f.shape[0] * f.shape[1])
                if 0.01 <= area_cand <= args.anchor_max:  # 好锚点
                    frame0, boxes, m0, anchor_gi = f, bs, m_cand, g
                    break
        if frame0 is None or not boxes:
            print(f"  [SEG {seg_start}] 锚定失败（无合格锚点），跳过", file=sys.stderr)
            n_anchor_fail += 1
            seg_video.unlink(missing_ok=True)
            continue
        if anchor_gi != seg_start:
            print(f"  [SEG {seg_start}] 锚点滑帧到 {anchor_gi}", file=sys.stderr)
        mask = torch.from_numpy(m0).float().to(args.device)
        if (new_h, new_w) != (h0, w0):
            mask = F.interpolate(mask.unsqueeze(0).unsqueeze(0), size=(new_h, new_w), mode="nearest")[0, 0]

        # 段内推理
        for ti in range(length):
            image = (vframes[ti] / 255.0).float().to(args.device)
            with torch.inference_mode():
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
                gi = seg_start + (ti - n_warmup)
                pha_out = pha if (new_h, new_w) == (h0, w0) else cv2.resize(pha, (w0, h0), interpolation=cv2.INTER_LINEAR)
                cv2.imencode(".png", pha_out)[1].tofile(str(alpha_dir / f"alpha_{gi:05d}.png"))
                all_areas.append(float(np.count_nonzero(pha_out)) / (h0 * w0))
        processor.clear_memory()  # 段间清记忆
        seg_video.unlink(missing_ok=True)
        n_seg += 1
        print(f"  [SEG {seg_start}-{seg_end}] done", file=sys.stderr)

    dt = time.time() - t0
    v = np.array(all_areas)
    print(json.dumps({
        "frames": len(all_areas), "segments": n_seg, "anchor_fail": n_anchor_fail,
        "area_median": round(float(np.median(v)), 3),
        "gt50pct": int((v > 0.5).sum()), "missing_lt1pct": int((v < 0.01).sum()),
        "nonempty": int((v > 0.001).sum()),
        "elapsed_s": round(dt, 1), "outdir": str(out),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
