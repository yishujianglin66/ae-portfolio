"""cutpoint_selfeval.py — 切点级自检与修复循环 (P2)

来源: 2026-09-09 四竞品调研报告 §3.3 —— 吸收 video-use "渲染后在每切点边界
self-eval, 不过则修复重渲 max 3" 的设计, 与 CNN 评分器互补:
CNN 管"整体好不好看", 本模块管"每一刀有没有技术事故"。

检测项 (对 hard cut):
  C1 frozen_cut  切点两侧画面几乎没变 (切了个寂寞, 如同源同 offset 重复段)
  C2 audio_pop   切点 ±5ms 内出现孤立样本级跳变 (拼接爆音, 区别于音乐性 onset)
  C3 min_gap     相邻切点间距过近 (< min_gap, 病态高频闪切)
  C4 flash       切点邻域出现近黑/近白帧 (编码事故/素材损坏)

修复策略 (repair_cutpoints):
  C1 → 丢弃该切点 (视觉上本来就没切)
  C3 → 丢弃过近对中的后一个
  C2 → 切点微调 ±1 帧 (改变拼接点, 消除波形不连续)
  C4 → 不自动修, 标记人工 (素材级问题)

repair_loop(render_fn, cut_times, max_rounds=3):
  analyze → 全过 → 返回; 有问题 → repair_cutpoints → render_fn 重渲 → 再检;
  3 轮不过 → 标记人工介入。render_fn(cut_times) -> video_path 由调用方注入
  (unified_edit 集成时由 ProductionDirector 提供)。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from scripts.render_regression import (  # noqa: E402
    _ahash_dhash,
    _extract_gray_frames,
    _hamming,
)

MIN_GAP_DEFAULT = 0.12          # 相邻切点最小间距 (秒, ≈3帧@24fps)
FREEZE_HAMMING_DEFAULT = 10     # 切点两侧 Hamming 距离低于此 → frozen_cut
POP_ABS_DEFAULT = 0.35          # 单样本跳变绝对阈值 (归一化幅值, 带限音频物理上不可能)
POP_RATIO_DEFAULT = 60.0        # 兜底: 切点邻域跳变 / 全局 P99.9 的倍数 (极端数字咔哒)
FLASH_LUMA_DEFAULT = 6.0        # 帧均亮度(0-255) <6 或 >249 → flash 帧
POP_SR_DEFAULT = 32000          # 音频检测采样率: 须够高使"带限不可能"论断成立
                                # (8kHz 下 4kHz 能量 SFX 瞬态会合法产生大跳变 → 误报)


def probe_fps(video: str | Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=r_frame_rate", "-of", "csv=p=0", str(video)],
        capture_output=True, text=True, timeout=60)
    frac = (out.stdout or "").strip().splitlines()[0]
    num, den = frac.split("/")
    return float(num) / float(den)


def _extract_audio_mono(video: str | Path, sr: int = 8000) -> np.ndarray:
    out = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(video), "-f", "f32le",
         "-ac", "1", "-ar", str(sr), "-"],
        capture_output=True, timeout=600)
    if out.returncode != 0 or not out.stdout:
        return np.zeros(0, dtype=np.float32)
    return np.frombuffer(out.stdout, dtype=np.float32)


def _frame_means(frames: list) -> list:
    return [sum(f) / len(f) for f in frames]


def analyze_cutpoints(
    video_path: str | Path,
    cut_times: list,
    *,
    min_gap: float = MIN_GAP_DEFAULT,
    freeze_hamming: int = FREEZE_HAMMING_DEFAULT,
    pop_abs: float = POP_ABS_DEFAULT,
    pop_ratio: float = POP_RATIO_DEFAULT,
    sr: int = POP_SR_DEFAULT,
) -> dict:
    """对渲染成品在切点边界做技术事故检测。返回报告 dict (含 issues)。"""
    v = str(video_path)
    fps = probe_fps(v)
    frames = _extract_gray_frames(v)
    hashes = [_ahash_dhash(f)[0] for f in frames]
    means = _frame_means(frames)
    audio = _extract_audio_mono(v, sr=sr)

    issues = []
    times = sorted(float(t) for t in cut_times if float(t) > 1e-6)

    # C3: min_gap (与画面无关, 先查)
    for i in range(1, len(times)):
        gap = times[i] - times[i - 1]
        if gap < min_gap:
            issues.append({
                "type": "min_gap", "cut_index": i, "time": times[i],
                "detail": {"gap": round(gap, 4), "min_gap": min_gap},
            })

    # C1 + C4: 逐切点查帧
    for i, t in enumerate(times):
        fi = int(round(t * fps))
        if 0 < fi < len(frames):
            d = _hamming(hashes[fi - 1], hashes[fi])
            if d <= freeze_hamming:
                issues.append({
                    "type": "frozen_cut", "cut_index": i, "time": t,
                    "detail": {"hamming": d, "threshold": freeze_hamming},
                })
        # C4: flash — 切点±2帧内出现极端亮度帧
        for j in range(max(0, fi - 2), min(len(means), fi + 3)):
            if means[j] < FLASH_LUMA_DEFAULT or means[j] > 255 - FLASH_LUMA_DEFAULT:
                issues.append({
                    "type": "flash", "cut_index": i, "time": t,
                    "detail": {"frame": j, "mean_luma": round(means[j], 1)},
                })
                break

    # C2: audio_pop — 切点 ±40ms 内样本级跳变
    # 判据: 单样本 |dx| > pop_abs (带限音频物理上不可能, 拼接咔哒特征),
    # 或局部跳变 > pop_ratio × 全局 P99.9 (数字咔哒兜底)。音乐性 onset 不触发。
    # 窗口 ±40ms: AAC 编码器 priming 会使拼接点偏离标称切点 ~1-2 帧。
    if len(audio) > 0:
        dx = np.abs(np.diff(audio))
        global_p999 = float(np.percentile(dx, 99.9)) if len(dx) else 0.0
        for i, t in enumerate(times):
            c = int(t * sr)
            lo, hi = max(0, c - int(0.040 * sr)), min(len(dx), c + int(0.040 * sr))
            if hi <= lo:
                continue
            local_max = float(dx[lo:hi].max())
            is_pop = local_max > pop_abs or (
                global_p999 > 0 and local_max > pop_ratio * global_p999)
            if is_pop:
                issues.append({
                    "type": "audio_pop", "cut_index": i, "time": t,
                    "detail": {"local_max": round(local_max, 5),
                               "global_p999": round(global_p999, 6),
                               "ratio": round(local_max / max(global_p999, 1e-9), 1)},
                })

    ok = not issues
    return {
        "verdict": "PASS" if ok else "FAIL",
        "video": v,
        "fps": fps,
        "frame_count": len(frames),
        "cut_count": len(times),
        "issues": issues,
        "params": {"min_gap": min_gap, "freeze_hamming": freeze_hamming,
                   "pop_abs": pop_abs, "pop_ratio": pop_ratio},
    }


def repair_cutpoints(cut_times: list, issues: list, *, fps: float = 24.0) -> list:
    """根据 issues 修复切点表 (不动渲染), 返回新切点表。"""
    times = sorted(float(t) for t in cut_times if float(t) > 1e-6)
    drop = set()
    nudge = {}
    for it in issues:
        idx = it["cut_index"]
        t = it["time"]
        if it["type"] in ("frozen_cut", "min_gap"):
            drop.add(t)
        elif it["type"] == "audio_pop":
            # ±1 帧微调, 交替方向
            step = 1.0 / fps
            nudge[t] = nudge.get(t, t) + (step if idx % 2 == 0 else -step)
        # flash: 人工项, 不自动修
    repaired = [nudge.get(t, t) for t in times if t not in drop]
    return [round(t, 4) for t in sorted(repaired)]


def repair_loop(
    render_fn,
    cut_times: list,
    video_path: str,
    *,
    max_rounds: int = 3,
    report_dir: str | Path | None = None,
    **analyze_kwargs,
) -> dict:
    """修复循环 (max_rounds): analyze → repair → render → 再检。

    render_fn(cut_times) -> 新 video_path;首轮 video_path 为已有渲染产物。
    """
    current_cuts = sorted(float(t) for t in cut_times)
    current_video = video_path
    history = []
    final = None

    for rnd in range(1, max_rounds + 1):
        rep = analyze_cutpoints(current_video, current_cuts, **analyze_kwargs)
        history.append({"round": rnd, "video": current_video,
                        "cut_count": len(current_cuts),
                        "verdict": rep["verdict"],
                        "issues": rep["issues"]})
        final = rep
        if rep["verdict"] == "PASS":
            break
        if rnd == max_rounds:
            rep["manual_review"] = True
            break
        current_cuts = repair_cutpoints(current_cuts, rep["issues"])
        current_video = render_fn(current_cuts)

    out = {
        "verdict": final["verdict"],
        "manual_review": final.get("manual_review", False),
        "rounds_used": len(history),
        "final_video": current_video,
        "final_cut_times": current_cuts,
        "history": history,
    }
    if report_dir:
        p = Path(report_dir)
        p.mkdir(parents=True, exist_ok=True)
        (p / "cutpoint_report.json").write_text(
            json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="切点级自检")
    ap.add_argument("video")
    ap.add_argument("cuts", help="逗号分隔切点时间(秒), 或 edl.json 路径")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    p = Path(a.cuts)
    if p.exists() and p.suffix == ".json":
        edl = json.loads(p.read_text(encoding="utf-8"))
        cut_times = edl.get("cut_points", [])
    else:
        cut_times = [float(x) for x in a.cuts.split(",") if x.strip()]

    rep = analyze_cutpoints(a.video, cut_times)
    out = Path(a.out) if a.out else Path(a.video).with_name(
        Path(a.video).stem + "_cutpoints.json")
    out.write_text(json.dumps(rep, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print(f"{'✅ PASS' if rep['verdict'] == 'PASS' else '❌ FAIL'} "
          f"cuts={rep['cut_count']} issues={len(rep['issues'])} fps={rep['fps']}")
    for it in rep["issues"][:20]:
        print(f"  - [{it['type']}] t={it['time']}s #{it['cut_index']} "
              f"{it['detail']}")
    print(f"report: {out}")
    return 0 if rep["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
