#!/usr/bin/env python3
"""
Step 4 A2: TransNetV2 切镜头 → 候选镜头片段 (0.3-8s 筛选)

输入: D:\\AE-Data\\AnimeCamera\\manifest.jsonl (A1 采集清单) + videos/
输出:
  D:\\AE-Data\\AnimeCamera\\shots\\{bvid}_{idx:03d}.mp4     (镜头切片, 无音频)
  D:\\AE-Data\\AnimeCamera\\shots_manifest.jsonl            (镜头清单, 供 A3 VLM 预标注)

技术要点:
  - TransNetV2 阈值 0.3 (A4 调研: 短视频硬切召回修复)
  - 切点上升沿检测 + 3 帧合并
  - 镜头时长筛选 0.3-8s (Step 4 方案 §3), 去 <0.3s 闪帧噪声
  - ffmpeg 精确帧裁剪 + 重编码 (切点非关键帧, -c copy 会错位)
  - 断点续传: shots_manifest 已存在的 shot 跳过

用法:
  py -3.12 scripts/cut_anime_shots.py --limit 5          # 冒烟: 前 5 个视频
  py -3.12 scripts/cut_anime_shots.py                    # 全量 (A1 完成后)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DATA_ROOT = Path(r"D:\AE-Data\AnimeCamera")
MANIFEST = DATA_ROOT / "manifest.jsonl"
SHOTS_DIR = DATA_ROOT / "shots"
SHOTS_MANIFEST = DATA_ROOT / "shots_manifest.jsonl"

TRANSNET_THRESHOLD = 0.3        # A4 结论: 0.5→0.3 回收硬切
MERGE_FRAMES = 3                # 相邻切点合并窗口
MIN_SHOT_SEC = 0.3              # 最小镜头时长
MAX_SHOT_SEC = 8.0              # 最大镜头时长
FFMPEG = "ffmpeg"


def detect_cuts(video_path: str, model) -> tuple[np.ndarray, float]:
    """TransNetV2 切点帧索引 + fps。"""
    from transnetv2_pytorch import TransNetV2 as _T
    video_frames, single_pred, _ = model.predict_video(video_path, quiet=True)
    pred = single_pred.cpu().numpy() if hasattr(single_pred, "cpu") else np.asarray(single_pred)
    bin_pred = (pred > TRANSNET_THRESHOLD).astype(np.int8)
    cuts = [i for i in range(1, len(bin_pred)) if bin_pred[i] == 1 and bin_pred[i - 1] == 0]

    # 合并相邻切点 (MERGE_FRAMES 内)
    merged = []
    for c in cuts:
        if merged and c - merged[-1] <= MERGE_FRAMES:
            continue
        merged.append(c)

    # fps 从视频探测
    fps = 30.0
    try:
        r = subprocess.run([FFMPEG, "-i", video_path], capture_output=True,
                           text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        for line in r.stderr.splitlines():
            if "fps" in line and "Video" in line:
                import re
                m = re.search(r"(\d+(?:\.\d+)?)\s*fps", line)
                if m:
                    fps = float(m.group(1))
                    break
    except Exception:  # noqa: BLE001
        pass
    return np.array(merged, dtype=np.int64), fps


def segment_shots(total_frames: int, fps: float, cuts: np.ndarray) -> list[dict[str, Any]]:
    """切点 → 镜头段 [(start_frame, end_frame, duration_sec)]。"""
    boundaries = [0] + list(cuts) + [total_frames]
    shots = []
    for i in range(len(boundaries) - 1):
        s, e = boundaries[i], boundaries[i + 1]
        dur = (e - s) / fps if fps > 0 else 0
        if MIN_SHOT_SEC <= dur <= MAX_SHOT_SEC:
            shots.append({"start_frame": s, "end_frame": e,
                          "start_sec": round(s / fps, 3), "end_sec": round(e / fps, 3),
                          "duration_sec": round(dur, 3)})
    return shots


def crop_shot(video_path: str, start_sec: float, duration_sec: float,
              out_path: Path) -> bool:
    """ffmpeg 精确裁剪 (重编码, 无音频)。"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists() and out_path.stat().st_size > 10_000:
        return True  # 已存在
    cmd = [FFMPEG, "-y", "-ss", f"{start_sec:.3f}", "-i", video_path,
           "-t", f"{duration_sec:.3f}", "-an",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
           "-vf", "scale=640:-2",
           str(out_path)]
    r = subprocess.run(cmd, capture_output=True,
                       creationflags=subprocess.CREATE_NO_WINDOW)
    return r.returncode == 0 and out_path.exists() and out_path.stat().st_size > 10_000


def _load_done_shots() -> set:
    done = set()
    if SHOTS_MANIFEST.exists():
        for line in SHOTS_MANIFEST.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                done.add(json.loads(line)["shot_id"])
            except (json.JSONDecodeError, KeyError):
                pass
    return done


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Step 4 A2: TransNetV2 切镜头")
    parser.add_argument("--limit", type=int, default=0, help="只处理前 N 个视频 (0=全部)")
    parser.add_argument("--no-crop", action="store_true", help="只检测不裁剪 (验证模式)")
    args = parser.parse_args()

    if not MANIFEST.exists():
        print(f"[A2] manifest 不存在: {MANIFEST} (先跑 A1 采集)")
        return 1

    rows = [json.loads(l) for l in MANIFEST.read_text(encoding="utf-8").splitlines() if l.strip()]
    if args.limit > 0:
        rows = rows[:args.limit]
    done_shots = _load_done_shots()

    from transnetv2_pytorch import TransNetV2
    model = TransNetV2(device="auto")
    print(f"[A2] {len(rows)} 视频, device={next(model.parameters()).device}, 已切 {len(done_shots)} 镜头")

    stats = {"videos_ok": 0, "videos_fail": 0, "shots_total": 0, "shots_cropped": 0}
    t0 = time.time()

    for i, row in enumerate(rows):
        bvid = row["bvid"]
        video_path = row["path"]
        if not Path(video_path).exists():
            print(f"  [{i + 1}/{len(rows)}] {bvid} 文件缺失, 跳过")
            stats["videos_fail"] += 1
            continue
        try:
            cuts, fps = detect_cuts(video_path, model)
            total_frames = int(round(row.get("duration", 0) * fps))
            shots = segment_shots(total_frames, fps, cuts)
        except Exception as exc:  # noqa: BLE001
            print(f"  [{i + 1}/{len(rows)}] {bvid} 切点检测失败: {str(exc)[:50]}")
            stats["videos_fail"] += 1
            continue
        stats["videos_ok"] += 1
        stats["shots_total"] += len(shots)

        crop_n = 0
        for si, shot in enumerate(shots):
            shot_id = f"{bvid}_{si:03d}"
            if shot_id in done_shots:
                continue
            clip_path = SHOTS_DIR / f"{shot_id}.mp4"
            if args.no_crop:
                crop_n += 1
                continue
            if crop_shot(video_path, shot["start_sec"], shot["duration_sec"], clip_path):
                with SHOTS_MANIFEST.open("a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "schema": "anime_camera_shot_v1",
                        "shot_id": shot_id,
                        "video_id": bvid,
                        "shot_idx": si,
                        "start_sec": shot["start_sec"],
                        "end_sec": shot["end_sec"],
                        "duration_sec": shot["duration_sec"],
                        "source_type": row.get("type", ""),
                        "anime": row.get("anime", ""),
                        "source_title": row.get("title", ""),
                        "clip_path": str(clip_path),
                        "movement_label": None,   # 待 A3 VLM 预标注
                        "cut_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    }, ensure_ascii=False) + "\n")
                crop_n += 1
        stats["shots_cropped"] += crop_n
        print(f"  [{i + 1}/{len(rows)}] {bvid} {row.get('anime','')[:8]:8s} "
              f"cuts={len(cuts)} shots={len(shots)} cropped={crop_n}")

    print(f"\n=== A2 汇总 ===\n  {json.dumps(stats, ensure_ascii=False)}")
    print(f"  elapsed {time.time() - t0:.0f}s | 镜头清单 -> {SHOTS_MANIFEST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
