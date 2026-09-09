# -*- coding: utf-8 -*-
"""repair_frozen_cuts.py — frozen_cut 源内微调修复（B1 方案 A，2026-09-09）

问题：run61 有 76 处 frozen_cut（切点两侧画面几乎相同），拉低 cut_visibility。
丢弃式不可行——会砍掉 21.13s（30s → 8.87s）。

本脚本采用**源内微调**：
  保持时间轴完全不变（不破坏卡点/beat_hit_rate），只把 frozen 段从源素材取的
  时刻平移到"与前一帧差异更大"的位置，让切点真正可见。

关键设计：
  1. 时间轴锁定 —— 段的 start_time/end_time/speed 一律不动，只改 source_start。
  2. 搜索窗口受限 —— 在 [src_start - 4s, src_start + 4s] 内搜索（默认），
     避免跨镜头跳到不相干的画面；可用 --window 调整。
  3. 评分目标 —— 用归一化帧差（与 cut_visibility 同口径）衡量"新首帧 vs 前一帧"，
     取差异最大者；差异需超过 --min-gain 才接受，否则保留原值。
  4. 只改 frozen 段 —— 非 frozen 段一律不动（避免无谓改动）。
  5. 只产出新 EDL —— 不渲染、不覆盖任何原文件。

用法:
  # 1) 先出修复后的 EDL（dry-run 看改动清单）
  python scripts/repair_frozen_cuts.py --edl output/unified_run61/edl.json \
      --cutpoints output/unified_run61/run61_cutpoints.json --dry-run

  # 2) 实际写出新 EDL
  python scripts/repair_frozen_cuts.py --edl ... --cutpoints ... \
      --out output/unified_run61/edl_repaired.json

  # 3) 用新 EDL 渲染（由既有渲染链路消费，本脚本不负责）
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

PROJ = Path(__file__).resolve().parent.parent
FF = shutil.which("ffmpeg") or "C:/ffmpeg/bin/ffmpeg.exe"
FFPROBE = shutil.which("ffprobe") or "C:/ffmpeg/bin/ffprobe.exe"
ALLOWED_SUFFIXES = (".mp4", ".mov", ".mkv", ".webm", ".m4v")


def safe_media(raw: str | Path) -> Path | None:
    try:
        p = Path(raw).expanduser().resolve()
    except (OSError, RuntimeError):
        return None
    if not p.is_file() or p.suffix.lower() not in ALLOWED_SUFFIXES:
        return None
    return p


def _run(cmd: list[str], timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, timeout=timeout,
                          shell=False, check=False)


def frame_gray(path: Path, t: float, w: int = 96, h: int = 54) -> np.ndarray | None:
    """取帧 → 灰度 → 缩放（未归一化，供帧差使用）。

    时间按 3 位小数格式化，与官方 `score_reference_gap._frame_gray` 一致——
    实测 ffmpeg `-ss` 在帧边界存在临界回退行为，更高精度会改变取到的帧。
    """
    cmd = [FF, "-ss", f"{max(t, 0):.3f}", "-i", str(path), "-frames:v", "1",
           "-vf", f"scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    r = _run(cmd, timeout=90)
    a = np.frombuffer(r.stdout, dtype=np.uint8).astype(np.float32)
    return a.reshape(h, w) if a.size == w * h else None


def media_duration(path: Path) -> float:
    r = _run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
              "-of", "csv=p=0", str(path)], timeout=60)
    try:
        return float((r.stdout or b"").decode().strip())
    except (TypeError, ValueError):
        return 0.0


def diff_score(a: np.ndarray | None, b: np.ndarray | None) -> float:
    """归一化帧差（与 cut_visibility 同口径：零均值单位方差后取绝对差均值）。"""
    if a is None or b is None or a.shape != b.shape:
        return 0.0
    an = (a - a.mean()) / (a.std() + 1e-6)
    bn = (b - b.mean()) / (b.std() + 1e-6)
    return float(np.abs(an - bn).mean())


def optimize_segment(src: Path, prev_frame: np.ndarray, cur_start: float,
                     speed: float, window: float, step: float, src_dur: float,
                     min_gain: float) -> tuple[float, float, float]:
    """在 [cur_start-window, cur_start+window] 内找与 prev_frame 差异最大的源时刻。

    口径严格对齐官方 cut_visibility：比较的是成片上 (t-1/24) 与 (t+3/24) 两帧。
    段内第 3 帧（成片 t+3/24）显示的源时刻 = src_start + (3/24)*speed，
    因此候选帧必须按此偏移取样，而不是直接取 src_start 处。

    返回 (new_start, old_diff, new_diff)。
    """
    probe_off = (3 / 24) * speed   # 成片 t+3/24 对应的段内源偏移

    def score_at(src_start: float) -> float:
        return diff_score(prev_frame, frame_gray(src, src_start + probe_off))

    old_diff = score_at(cur_start)
    lo = max(0.0, cur_start - window)
    hi = min(max(src_dur - 0.1, 0.0), cur_start + window) if src_dur > 0 else cur_start + window
    best_t, best_d = cur_start, old_diff
    t = lo
    while t <= hi:
        d = score_at(t)
        if d > best_d:
            best_d, best_t = d, t
        t += step
    if best_d - old_diff < min_gain:
        return cur_start, old_diff, old_diff
    return round(best_t, 3), old_diff, round(best_d, 3)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--edl", required=True, help="输入 EDL json")
    ap.add_argument("--cutpoints", required=True, help="cutpoint_report json（含 issues）")
    ap.add_argument("--out", default=None, help="输出 EDL 路径")
    ap.add_argument("--window", type=float, default=4.0, help="源内搜索半径（秒）")
    ap.add_argument("--step", type=float, default=0.25, help="搜索步长（秒）")
    ap.add_argument("--min-gain", type=float, default=0.15,
                    help="差异增益下限，低于此不修改")
    ap.add_argument("--tol", type=float, default=0.06, help="切点匹配容差（秒）")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", default=None, help="改动台账输出路径")
    args = ap.parse_args()

    edl_p = Path(args.edl)
    cp_p = Path(args.cutpoints)
    if not edl_p.exists() or not cp_p.exists():
        print("EDL 或 cutpoints 文件不存在")
        return 1
    edl = json.loads(edl_p.read_text(encoding="utf-8"))
    cp = json.loads(cp_p.read_text(encoding="utf-8"))
    cuts = edl.get("cuts", [])
    frozen = sorted({round(float(i["time"]), 3)
                     for i in cp.get("issues", []) if i.get("type") == "frozen_cut"})
    if not frozen:
        print("无 frozen_cut，无需修复")
        return 0

    # 视频文件（用于取"前一帧"）——从 EDL 同级找 master
    video = None
    for cand in (edl_p.parent / "polish" / "master_hr.mp4",
                 edl_p.parent / "polish" / "master.mp4",
                 edl_p.parent / "run61_final.mp4"):
        if cand.exists():
            video = cand
            break

    # 段起始 → 索引
    starts = [round(c["start_time"], 3) for c in cuts]
    dur_cache: dict[str, float] = {}
    ledger = []
    changed = 0

    for i, c in enumerate(cuts):
        t = round(c["start_time"], 3)
        if not any(abs(t - f) <= args.tol for f in frozen):
            continue
        src = safe_media(c["source_file"])
        if src is None:
            ledger.append({"index": i, "start": t, "action": "skip",
                           "reason": "源素材不可用"})
            continue
        if video is None:
            ledger.append({"index": i, "start": t, "action": "skip",
                           "reason": "找不到成片用于取前一帧"})
            continue
        prev_frame = frame_gray(video, max(0.0, c["start_time"] - 1 / 24))
        if prev_frame is None:
            ledger.append({"index": i, "start": t, "action": "skip",
                           "reason": "前一帧取样失败"})
            continue
        key = str(src)
        if key not in dur_cache:
            dur_cache[key] = media_duration(src)
        new_start, old_d, new_d = optimize_segment(
            src, prev_frame, float(c["source_start"]), float(c["speed"]),
            args.window, args.step, dur_cache[key], args.min_gain)
        if new_start == c["source_start"]:
            ledger.append({"index": i, "start": t, "action": "keep",
                           "old_src_start": c["source_start"],
                           "old_diff": round(old_d, 3), "new_diff": round(new_d, 3)})
            continue
        ledger.append({"index": i, "start": t, "action": "shift",
                       "old_src_start": c["source_start"],
                       "new_src_start": new_start,
                       "old_diff": round(old_d, 3), "new_diff": round(new_d, 3),
                       "gain": round(new_d - old_d, 3)})
        c["source_start"] = new_start
        c["frozen_repair"] = True
        changed += 1

    print(f"frozen_cut {len(frozen)} 处 | 扫描 {len(ledger)} 段 | 实际平移 {changed} 段")
    shifted = [x for x in ledger if x["action"] == "shift"]
    if shifted:
        gains = [x["gain"] for x in shifted]
        print(f"差异增益: 均值 {np.mean(gains):.2f} 中位 {np.median(gains):.2f} "
              f"最大 {max(gains):.2f}")
        print("\n前 10 处改动:")
        for x in sorted(shifted, key=lambda y: -y["gain"])[:10]:
            print(f"  idx={x['index']:>3} t={x['start']:>6.2f} "
                  f"src {x['old_src_start']:>7.2f}→{x['new_src_start']:>7.2f} "
                  f"差异 {x['old_diff']:.2f}→{x['new_diff']:.2f} (+{x['gain']:.2f})")

    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps({
            "source_edl": str(edl_p), "n_frozen": len(frozen),
            "n_shifted": changed, "window": args.window, "step": args.step,
            "ledger": ledger,
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n台账 → {args.json}")

    if args.dry_run:
        print("\n[dry-run] 未写出 EDL")
        return 0

    out = Path(args.out) if args.out else edl_p.with_name(edl_p.stem + "_repaired.json")
    edl["_frozen_repair"] = {
        "applied": True, "n_shifted": changed,
        "window": args.window, "step": args.step, "min_gain": args.min_gain,
        "note": "仅平移 source_start，时间轴与 speed 未动",
    }
    out.write_text(json.dumps(edl, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n新 EDL → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
