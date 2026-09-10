"""render_regression.py — 帧级哈希回归比对 (P0 确定性渲染框架)

来源: 2026-09-09 四竞品调研报告 §2.2 —— HyperFrames "同输入同帧输出+逐帧回归"
理念在 FFmpeg 链路的等价实现: 渲染产物逐帧提取 aHash+dHash (128bit/帧),
与基线比对, 超 Hamming 阈值的帧计为漂移帧, 比例超限即回归失败。

帧提取: ffmpeg -i <video> -vf scale=64:64,format=gray -f rawvideo - (stdout pipe)
  → 每帧 4096 字节灰度, 不落盘、不依赖解码库行为差异。

CLI:
  baseline <video> <out.json>                       建基线
  compare  <video> <baseline.json> [--out r.json]   比对, 退出码 0=PASS 1=FAIL

判定:
  结构变化(帧数不一致)        → FAIL (structural_change)
  漂移帧比例 > flag_ratio(2%)  → FAIL
  否则                        → PASS
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

FRAME_SIZE = 64                     # 64x64 灰度
FRAME_BYTES = FRAME_SIZE * FRAME_SIZE
HAMMING_DEFAULT = 18                # 单帧 128bit 中允许的漂移位数上限
FLAG_RATIO_DEFAULT = 0.02           # 漂移帧占比上限 (2%)
MEAN_DELTA_DEFAULT = 4.0            # 帧均亮度差上限 (64 级灰度中的 4 级)


def _extract_gray_frames(video_path: str | Path) -> list:
    """解码全部帧为 64x64 灰度字节串列表 (顺序即帧序)。"""
    cmd = ["ffmpeg", "-v", "error", "-i", str(video_path),
           "-vf", f"scale={FRAME_SIZE}:{FRAME_SIZE},format=gray",
           "-f", "rawvideo", "-"]
    proc = subprocess.run(cmd, capture_output=True, timeout=600)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg decode failed: {proc.stderr.decode(errors='replace')[:400]}")
    buf = proc.stdout
    if len(buf) < FRAME_BYTES:
        raise RuntimeError(f"no frames decoded from {video_path}")
    return [buf[i:i + FRAME_BYTES]
            for i in range(0, len(buf) - FRAME_BYTES + 1, FRAME_BYTES)]


def _ahash_dhash(gray: bytes) -> str:
    """一帧 → aHash(64bit)+dHash(64bit) 拼接的 32 位 hex。"""
    n = FRAME_SIZE
    px = gray
    # aHash: 64x64 网格降采样 8x8 (每 8 像素取一) → 与均值比较
    sample = [px[r * n + c]
              for r in range(0, n, n // 8)
              for c in range(0, n, n // 8)]
    mean = sum(sample) / len(sample)
    a = 0
    for i, v in enumerate(sample):
        if v > mean:
            a |= 1 << (63 - i)
    # dHash: 水平梯度 (8 行采样 × 每行前 8 对 = 64bit)
    d = 0
    bit = 0
    for row in range(0, n, n // 8):           # 8 行采样
        for col in range(8):                  # 每行前 8 对
            left = px[row * n + col]
            right = px[row * n + col + 1]
            if left > right:
                d |= 1 << (63 - bit)
            bit += 1
    return f"{a:016x}{d:016x}", mean


def _frame_mean(gray: bytes) -> float:
    return sum(gray) / len(gray)


def _popcount(x: int) -> int:
    return bin(x).count("1")


def _hamming(h1: str, h2: str) -> int:
    return _popcount(int(h1, 16) ^ int(h2, 16))


def make_baseline(video_path: str | Path) -> dict:
    frames = _extract_gray_frames(video_path)
    pairs = [_ahash_dhash(f) for f in frames]
    return {
        "video": str(video_path),
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "frame_count": len(frames),
        "hashes": [h for h, _ in pairs],
        "means": [round(m, 3) for _, m in pairs],
        "hash_spec": {"frame_size": FRAME_SIZE,
                      "algos": ["ahash", "dhash", "mean_luma"],
                      "bits": 128, "mean_threshold": MEAN_DELTA_DEFAULT},
    }


def save_baseline(baseline: dict, path: str | Path) -> Path:
    p = Path(path)
    p.write_text(json.dumps(baseline, ensure_ascii=False, indent=1),
                 encoding="utf-8")
    return p


def compare_to_baseline(
    video_path: str | Path,
    baseline: dict,
    *,
    hamming_threshold: int = HAMMING_DEFAULT,
    flag_ratio: float = FLAG_RATIO_DEFAULT,
    mean_delta_threshold: float = MEAN_DELTA_DEFAULT,
) -> dict:
    """逐帧比对, 产出回归报告 dict (verdict: PASS/FAIL)。

    漂移帧判定: Hamming 超阈值 **或** 帧均值亮度差超阈值
    (aHash/dHash 对全局亮度平移不敏感, 必须补绝对亮度分量才能
    抓住 LUT 误用类回归 — 见 2026-09-09 实测教训)。
    """
    frames = _extract_gray_frames(video_path)
    pairs = [_ahash_dhash(f) for f in frames]
    hashes = [h for h, _ in pairs]
    means = [m for _, m in pairs]
    base_hashes = baseline["hashes"]
    base_means = baseline.get("means")
    base_n = baseline["frame_count"]

    if len(hashes) != base_n:
        return {
            "verdict": "FAIL",
            "reason": "structural_change",
            "frame_count": len(hashes),
            "baseline_frame_count": base_n,
            "video": str(video_path),
            "baseline_video": baseline.get("video"),
            "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }

    dists = [_hamming(h, b) for h, b in zip(hashes, base_hashes)]
    mean_deltas = ([abs(m - bm) for m, bm in zip(means, base_means)]
                   if base_means else [0.0] * len(dists))
    flagged = [i for i in range(len(dists))
               if dists[i] > hamming_threshold
               or mean_deltas[i] > mean_delta_threshold]
    ratio = len(flagged) / max(1, len(dists))
    ok = ratio <= flag_ratio
    return {
        "verdict": "PASS" if ok else "FAIL",
        "reason": "ok" if ok else "frame_drift",
        "video": str(video_path),
        "baseline_video": baseline.get("video"),
        "frame_count": len(dists),
        "hamming_threshold": hamming_threshold,
        "mean_delta_threshold": mean_delta_threshold,
        "max_distance": max(dists) if dists else 0,
        "mean_distance": round(sum(dists) / max(1, len(dists)), 3),
        "max_mean_luma_delta": round(max(mean_deltas), 3) if mean_deltas else 0,
        "flagged_frames": len(flagged),
        "flag_ratio": round(ratio, 5),
        "flag_ratio_limit": flag_ratio,
        "flagged_sample": flagged[:50],
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="帧级哈希回归比对")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pb = sub.add_parser("baseline")
    pb.add_argument("video")
    pb.add_argument("out")
    pc = sub.add_parser("compare")
    pc.add_argument("video")
    pc.add_argument("baseline")
    pc.add_argument("--out", default=None)
    pc.add_argument("--hamming", type=int, default=HAMMING_DEFAULT)
    pc.add_argument("--flag-ratio", type=float, default=FLAG_RATIO_DEFAULT)
    pc.add_argument("--mean-delta", type=float, default=MEAN_DELTA_DEFAULT)
    a = ap.parse_args()

    if a.cmd == "baseline":
        b = make_baseline(a.video)
        p = save_baseline(b, a.out)
        print(f"baseline: {p}  frames={b['frame_count']}")
        return 0

    baseline = json.loads(Path(a.baseline).read_text(encoding="utf-8"))
    rep = compare_to_baseline(a.video, baseline,
                              hamming_threshold=a.hamming,
                              flag_ratio=a.flag_ratio,
                              mean_delta_threshold=a.mean_delta)
    out = Path(a.out) if a.out else Path(a.video).with_name(
        Path(a.video).stem + "_regression.json")
    out.write_text(json.dumps(rep, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print(f"{'✅ PASS' if rep['verdict'] == 'PASS' else '❌ FAIL'} "
          f"({rep.get('reason')})  frames={rep.get('frame_count')} "
          f"flagged={rep.get('flagged_frames')} "
          f"max_d={rep.get('max_distance')} mean_d={rep.get('mean_distance')}")
    print(f"report: {out}")
    return 0 if rep["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
