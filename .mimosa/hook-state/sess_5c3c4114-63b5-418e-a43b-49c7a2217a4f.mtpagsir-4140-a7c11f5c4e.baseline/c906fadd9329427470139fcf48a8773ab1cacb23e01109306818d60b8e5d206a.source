"""
统一 QC 指标计算脚本 (benchmark_qc_matting.py)
===============================================
方案文档 §6 Benchmark & 量化指标。每个里程碑(M0→M4)跑一次，产出 qc_report_*.json。

指标（与方案 §6 对齐）:
  FR       fallback_rate       回退 auto_frame 帧 / 总帧（读 run result 的 fallback_rate）
  J500     帧间跳变次数        连续段内 |Δalpha非空率| > 0.5 的帧数（像素级 mask 判定，PIT-2）
  GPU_T    总GPU时长(秒)       读 run result 的 total_elapsed_s；--baseline 时给 ratio
  EDGE_IoU 边缘IoU均值         需 GT（人工标注），无 GT 时置 null
  BLUR_R   模糊区召回          需 GT，无 GT 时置 null
  补充:     nonempty_rate, nz_mean/min/max/median_pct

CLI:
  py -3.12 scripts/benchmark_qc_matting.py --masks <dirA> [--masks2 <dirB>] \
      --result <run_result.json> [--result2 <run_result2.json>] --out qc_report.json
  # 例: --masks output/step2_locator/m1_routed --result output/step2_locator/m1_routed.json.ok
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

JUMP_DELTA_THR = 0.5  # |Δ非空率| > 0.5 视为帧间跳变（方案 §6 J500）


def imread_unicode(p: str) -> np.ndarray | None:
    if not Path(p).exists():
        return None
    buf = np.fromfile(p, dtype=np.uint8)
    if buf.size == 0:
        return None
    return cv2.imdecode(buf, cv2.IMREAD_GRAYSCALE)


def load_masks(mask_dir: str, start: int = 0, frames: int = 0) -> dict[int, np.ndarray]:
    """按全局帧号读取 mask_%05d.png；返回 {global_idx: mask}。"""
    d = Path(mask_dir)
    masks: dict[int, np.ndarray] = {}
    if not d.is_dir():
        return masks
    for p in sorted(d.glob("mask_*.png")):
        name = p.stem
        try:
            gi = int(name.split("_")[-1])
        except Exception:
            continue
        if start and gi < start:
            continue
        if frames and gi >= start + frames:
            continue
        m = imread_unicode(str(p))
        if m is not None:
            masks[gi] = m
    return masks


def frame_metrics(masks: dict[int, np.ndarray]) -> dict:
    """逐帧非空率 + J500 跳变统计（像素级，PIT-2）。"""
    if not masks:
        return {"error": "no masks"}
    gis = sorted(masks)
    h, w = masks[gis[0]].shape[:2]
    nz_ratio = {}
    for gi in gis:
        m = masks[gi]
        nz_ratio[gi] = float(np.count_nonzero(m)) / (h * w)
    # 帧间跳变：连续帧 |Δ非空率| > 0.5
    jumps: list[int] = []
    prev = None
    for gi in gis:
        if prev is not None:
            d = abs(nz_ratio[gi] - nz_ratio[prev])
            if d > JUMP_DELTA_THR:
                jumps.append(gi)
        prev = gi
    nz_vals = list(nz_ratio.values())
    return {
        "frames": len(gis),
        "first_frame": gis[0],
        "last_frame": gis[-1],
        "resolution": f"{w}x{h}",
        "nonempty_rate": float(np.mean([1.0 if v > 0.001 else 0.0 for v in nz_vals])),
        "nz_mean_pct": round(100.0 * float(np.mean(nz_vals)), 2),
        "nz_min_pct": round(100.0 * float(np.min(nz_vals)), 2),
        "nz_max_pct": round(100.0 * float(np.max(nz_vals)), 2),
        "nz_median_pct": round(100.0 * float(np.median(nz_vals)), 2),
        "J500_jump_count": len(jumps),
        "J500_jump_frames": jumps,
    }


def load_result(path: str) -> dict | None:
    p = Path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def pairwise_iou_series(masks: dict[int, np.ndarray]) -> dict:
    """连续帧 mask 的 IoU 序列（人物区域帧间一致性，越大越稳）。
    iou[f] = |M_f ∩ M_{f-1}| / |M_f ∪ M_{f-1}|（两帧都非空才计入）。
    """
    gis = sorted(masks)
    frames = []
    ious = []
    for i in range(1, len(gis)):
        a = masks[gis[i - 1]]
        b = masks[gis[i]]
        na = np.count_nonzero(a)
        nb = np.count_nonzero(b)
        if na < 100 or nb < 100:
            continue
        inter = float(np.count_nonzero(np.logical_and(a > 0, b > 0)))
        union = float(np.count_nonzero(np.logical_or(a > 0, b > 0)))
        if union <= 0:
            continue
        frames.append(gis[i])
        ious.append(inter / union)
    return {"frames": frames, "iou": ious,
            "mean": round(float(np.mean(ious)), 4) if ious else None,
            "std": round(float(np.std(ious)), 4) if ious else None}


def welch_ttest(a: list[float], b: list[float]) -> dict:
    """Welch t 检验（不等方差），返回 t、p、均值差、效应(均值差/合并σ)。"""
    import math
    if len(a) < 2 or len(b) < 2:
        return {"error": "insufficient samples"}
    na, nb = len(a), len(b)
    ma, mb = float(np.mean(a)), float(np.mean(b))
    va, vb = float(np.var(a, ddof=1)), float(np.var(b, ddof=1))
    se = math.sqrt(va / na + vb / nb)
    if se <= 0:
        return {"error": "zero variance"}
    t = (ma - mb) / se
    df = (va / na + vb / nb) ** 2 / ((va / na) ** 2 / (na - 1) + (vb / nb) ** 2 / (nb - 1))
    p = None
    try:
        from scipy import stats
        p = float(stats.t.sf(abs(t), df) * 2)
    except Exception:
        p = None
    pooled_std = math.sqrt((va + vb) / 2)
    return {
        "n_A": na, "n_B": nb,
        "mean_A": round(ma, 4), "mean_B": round(mb, 4),
        "mean_diff_B_minus_A": round(mb - ma, 4),
        "t": round(t, 4), "df": round(df, 2), "p_value": p,
        "effect_size_sigma": round((mb - ma) / pooled_std, 4) if pooled_std > 0 else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="统一 QC 指标计算（方案 §6）")
    ap.add_argument("--masks", required=True, help="mask PNG 目录（全局帧号命名 mask_%05d.png）")
    ap.add_argument("--masks2", default="", help="第二组 mask 目录（可选，A/B 对比）")
    ap.add_argument("--result", default="", help="run result json（params.json.ok，读 FR/GPU_T）")
    ap.add_argument("--result2", default="", help="第二组 run result json（可选）")
    ap.add_argument("--out", default="qc_report.json", help="输出报告路径")
    ap.add_argument("--start", type=int, default=0, help="起始全局帧号过滤（默认不过滤）")
    ap.add_argument("--frames", type=int, default=0, help="帧数过滤（默认全部）")
    args = ap.parse_args()

    t0 = time.time()
    rep: dict = {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S")}

    fm = frame_metrics(load_masks(args.masks, args.start, args.frames))
    rep["masks_A"] = args.masks
    rep["A"] = fm
    rA = load_result(args.result) if args.result else None
    if rA:
        rep["A_run"] = {
            "fallback_count": rA.get("fallback_count"),
            "fallback_rate": rA.get("fallback_rate"),
            "fallback_rate_excl_routed": rA.get("fallback_rate_excl_routed"),
            "total_elapsed_s": rA.get("total_elapsed_s"),
            "propagation_elapsed_s": rA.get("propagation_elapsed_s"),
            "motion_route": rA.get("motion_route"),
        }

    if args.masks2:
        masks_b = load_masks(args.masks2, args.start, args.frames)
        fm2 = frame_metrics(masks_b)
        rep["masks_B"] = args.masks2
        rep["B"] = fm2
        r2 = load_result(args.result2) if args.result2 else None
        if r2:
            rep["B_run"] = {
                "fallback_rate": r2.get("fallback_rate"),
                "fallback_rate_excl_routed": r2.get("fallback_rate_excl_routed"),
                "total_elapsed_s": r2.get("total_elapsed_s"),
                "motion_route": r2.get("motion_route"),
            }
        if rA and r2 and rA.get("total_elapsed_s") and r2.get("total_elapsed_s"):
            rep["GPU_T_ratio_B_over_A"] = round(
                float(r2["total_elapsed_s"]) / float(rA["total_elapsed_s"]), 3)
        rep["J500_A"] = fm.get("J500_jump_count")
        rep["J500_B"] = fm2.get("J500_jump_count")
        # —— M2-A4: 连续帧 IoU 序列 + Welch t 检验（Baseline vs Warp 统计显著性）
        iouA = pairwise_iou_series(load_masks(args.masks, args.start, args.frames))
        iouB = pairwise_iou_series(masks_b)
        rep["pairwise_iou_A"] = iouA
        rep["pairwise_iou_B"] = iouB
        if iouA.get("iou") and iouB.get("iou"):
            rep["pairwise_iou_ttest"] = welch_ttest(iouA["iou"], iouB["iou"])

    # 帧级 Δ非空率序列（用于 t 检验等细粒度分析）
    gis = sorted(load_masks(args.masks, args.start, args.frames))
    if gis:
        rep["A_delta_series"] = _delta_series(load_masks(args.masks, args.start, args.frames), gis)
    if args.masks2:
        gis2 = sorted(load_masks(args.masks2, args.start, args.frames))
        if gis2:
            rep["B_delta_series"] = _delta_series(load_masks(args.masks2, args.start, args.frames), gis2)

    rep["elapsed_s"] = round(time.time() - t0, 2)
    out_p = Path(args.out)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    out_p.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "A_J500": fm.get("J500_jump_count"),
        "A_fallback_rate": (rA or {}).get("fallback_rate"),
        "B_J500": fm2.get("J500_jump_count") if args.masks2 else None,
        "GPU_T_ratio": rep.get("GPU_T_ratio_B_over_A"),
        "pairwise_iou_ttest": rep.get("pairwise_iou_ttest"),
        "report": str(out_p),
    }, ensure_ascii=False, indent=2))
    return 0


def _delta_series(masks: dict[int, np.ndarray], gis: list[int]) -> list[float]:
    h, w = masks[gis[0]].shape[:2]
    out = []
    prev = None
    for gi in gis:
        r = float(np.count_nonzero(masks[gi])) / (h * w)
        if prev is not None:
            out.append(round(abs(r - prev), 4))
        prev = r
    return out


if __name__ == "__main__":
    sys.exit(main())
