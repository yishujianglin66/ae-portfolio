"""scripts/annotate_atmosphere.py — ToriiGate 批量氛围标注 CLI

对一批视频素材做 W6 氛围标注, 结果落盘 JSON 缓存 (供 material attribution
消费)。每个视频 4 帧 GPU 推理 ~35-45s; 失败/低置信自动跳过。

用法:
    python scripts/annotate_atmosphere.py --videos data/real_amv_test \
        --out data/atmosphere_annotations/real_amv_test.json --limit 10
    python scripts/annotate_atmosphere.py --video x.mp4 --video y.mp4 \
        --out data/atmosphere_annotations/custom.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from models.atmosphere.torii_annotator import get_torii_annotator  # noqa: E402

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".flv"}


def collect_videos(video_args, video_dir, limit):
    vids = []
    if video_args:
        vids = [Path(v) for v in video_args]
    elif video_dir:
        d = Path(video_dir)
        vids = sorted(p for p in d.rglob("*") if p.suffix.lower() in VIDEO_EXTS)
        if limit:
            vids = vids[:limit]
    return vids


def main() -> int:
    parser = argparse.ArgumentParser(description="ToriiGate 氛围批量标注")
    parser.add_argument("--video", action="append", default=[],
                        help="单个视频 (可多次)")
    parser.add_argument("--videos", dest="video_dir",
                        help="视频目录 (递归扫描)")
    parser.add_argument("--out", required=True, help="输出 JSON 路径")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--max-frames", type=int, default=4)
    args = parser.parse_args()

    vids = collect_videos(args.video, args.video_dir, args.limit)
    if not vids:
        print("无视频输入")
        return 1
    print(f"待标注: {len(vids)} 个视频")

    ann = get_torii_annotator(max_frames=args.max_frames)
    if not ann.available():
        print("ToriiGate 不可用 (模型缺失)")
        return 1

    results = {}
    t0 = time.time()
    for i, v in enumerate(vids):
        t1 = time.time()
        r = ann.annotate(str(v))
        dt = time.time() - t1
        results[v.name] = r.to_dict() if r else None
        status = f"{r.atmosphere}/{r.energy}" if r else "None"
        print(f"[{i+1}/{len(vids)}] {v.name[:40]:42s} -> {status} ({dt:.0f}s)")
    elapsed = time.time() - t0

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "annotator": "torii_gate_v0.4_2b",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "n_videos": len(vids),
        "n_annotated": sum(1 for v in results.values() if v),
        "elapsed_sec": round(elapsed, 1),
        "results": results,
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"完成: {payload['n_annotated']}/{len(vids)} ({elapsed:.0f}s) -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
