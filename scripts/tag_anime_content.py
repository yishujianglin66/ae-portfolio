#!/usr/bin/env python3
"""
动漫内容标签 (A6): deepghs/anime_classification (MIT) — 给素材打 5 类内容标签

标签: 3d(3D渲染) / bangumi(番剧截图) / comic(漫画) / illustration(插画) /
      not_painting(非绘画: 宣传图/游戏截图/教程录屏等)

模型 (默认 mobilenetv3_v1.2_dist, 96.53% acc / 0.63G FLOPS, CPU 友好):
  D:\\AE-Data\\Models\\anime_classification\\mobilenetv3_v1.2_dist\\model.onnx
  备选 caformer_s36_v1.4_focal_fixed (96.21%, 22.1G FLOPS, 较慢)

关键经验 (2026-08-14 实测):
  - 该系列为 focal loss 训练, softmax 置信度校准偏低 (概率平坦, max 0.25-0.40
    属正常), **argmax 才是可靠信号**, 不要用置信度阈值做决策。
  - 视频级聚合用多数投票 (vote), 比概率平均更抗校准偏差。
  - 预处理: resize 384 + ImageNet 归一化 (timm 风格), RGB。

用法:
  py -3.12 scripts/tag_anime_content.py \
      --video-dir data\\real_amv_test --out models/output/anime_content_tags.json
  py -3.12 scripts/tag_anime_content.py --image xxx.png   # 单图
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

MODEL_ROOT = r"D:\AE-Data\Models\anime_classification"
DEFAULT_VARIANT = "mobilenetv3_v1.2_dist"
LABELS = ["3d", "bangumi", "comic", "illustration", "not_painting"]
# timm 风格: resize 384 + ImageNet 归一化 (两变体均为 sail_in22k/in1k 预训练)
INPUT_SIZE = 384
MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


class AnimeContentTagger:
    """deepghs/anime_classification ONNX 推理封装 (argmax 为可靠信号)。"""

    def __init__(self, variant: str = DEFAULT_VARIANT):
        import onnxruntime as ort
        model_path = Path(MODEL_ROOT) / variant / "model.onnx"
        if not model_path.exists():
            raise FileNotFoundError(f"模型不存在: {model_path}")
        self.sess = ort.InferenceSession(str(model_path),
                                         providers=["CPUExecutionProvider"])
        self.input_name = self.sess.get_inputs()[0].name
        self.variant = variant

    def tag_image(self, img_rgb: np.ndarray) -> Dict[str, float]:
        """单帧 (H,W,3 uint8 RGB) → 5 类概率 (argmax 为标签)。"""
        from PIL import Image
        pil = Image.fromarray(img_rgb).resize((INPUT_SIZE, INPUT_SIZE), Image.BICUBIC)
        x = np.asarray(pil, dtype=np.float32) / 255.0
        x = (x - MEAN) / STD
        x = x.transpose(2, 0, 1)[None, ...]  # (1,3,384,384)
        logits = self.sess.run(None, {self.input_name: x})[0][0]
        e = np.exp(logits - logits.max())
        probs = e / e.sum()
        return {LABELS[i]: float(probs[i]) for i in range(len(LABELS))}

    def tag_video(self, video_path: str, n_frames: int = 16) -> Dict[str, Any]:
        """视频 → 均匀采样 n_frames 帧 → 帧级 argmax 标签 + 视频级多数投票。"""
        from decord import VideoReader, cpu
        vr = VideoReader(str(video_path), ctx=cpu(0))
        n = len(vr)
        if n == 0:
            return {"video": str(video_path), "error": "no frames"}
        if n <= n_frames:
            idxs = list(range(n))
        else:
            step = (n - 1) / (n_frames - 1)
            idxs = [round(i * step) for i in range(n_frames)]
        frames = vr.get_batch(idxs).asnumpy()  # (T,H,W,3) RGB uint8

        votes: Dict[str, int] = {l: 0 for l in LABELS}
        mean_probs: Dict[str, float] = {l: 0.0 for l in LABELS}
        for f in frames:
            probs = self.tag_image(f)
            votes[max(probs, key=probs.get)] += 1
            for l in LABELS:
                mean_probs[l] += probs[l] / len(frames)

        return {
            "video": str(video_path),
            "n_frames": int(n),
            "sampled": len(frames),
            "dominant": max(votes, key=votes.get),
            "votes": votes,
            "mean_probs": {l: round(mean_probs[l], 4) for l in LABELS},
        }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="deepghs 动漫内容标签 (A6)")
    parser.add_argument("--video-dir", default=str(PROJECT_ROOT / "data" / "real_amv_test"))
    parser.add_argument("--image", help="单图文件 (优先)")
    parser.add_argument("--model", default=DEFAULT_VARIANT,
                        help=f"模型变体 ({DEFAULT_VARIANT} 或 caformer_s36_v1.4_focal_fixed)")
    parser.add_argument("--out", default=str(PROJECT_ROOT / "models" / "output" / "anime_content_tags.json"))
    parser.add_argument("--limit", type=int, default=0, help="只测前 N 个视频 (0=全部)")
    parser.add_argument("--n-frames", type=int, default=16)
    args = parser.parse_args()

    tagger = AnimeContentTagger(variant=args.model)
    print(f"[AnimeContentTagger] variant={tagger.variant} backend=CPU")

    if args.image:
        from PIL import Image
        img = np.asarray(Image.open(args.image).convert("RGB"))
        probs = tagger.tag_image(img)
        print("单图标签(argmax):", max(probs, key=probs.get), probs)
        return 0

    exts = (".mp4", ".mov", ".mkv", ".avi", ".webm", ".flv")
    videos = sorted(p for p in Path(args.video_dir).rglob("*") if p.suffix.lower() in exts)
    if args.limit > 0:
        videos = videos[:args.limit]
    print(f"[tag] {len(videos)} videos x {args.n_frames} frames")

    results: List[Dict[str, Any]] = []
    t0 = time.time()
    for i, vp in enumerate(videos):
        try:
            r = tagger.tag_video(str(vp), n_frames=args.n_frames)
        except Exception as exc:  # noqa: BLE001
            r = {"video": str(vp), "error": str(exc)}
        results.append(r)
        if "error" in r:
            print(f"[{i + 1}/{len(videos)}] skip {vp.name[:40]}: {r['error']}")
        else:
            print(f"[{i + 1}/{len(videos)}] {vp.name[:34]:34s} -> {r['dominant']:14s} "
                  f"(votes {r['votes']})")

    ok = [r for r in results if "error" not in r]
    from collections import Counter
    summary = {
        "model": args.model,
        "n_videos": len(results),
        "n_ok": len(ok),
        "dominant_distribution": dict(Counter(r["dominant"] for r in ok)),
        "elapsed_sec": round(time.time() - t0, 1),
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "results": results}, f, ensure_ascii=False, indent=2)
    print("\n=== 汇总 ===")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    print(f"结果 -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
