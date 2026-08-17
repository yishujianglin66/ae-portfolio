#!/usr/bin/env python3
"""
评估 TransNetV2 在 B 站动漫/AMV 素材上的镜头切点检测质量 (A4)。

背景 (docs/research/2026-08-14-integration-candidates-v2.md A4):
  AutoShot (CVPR NAS 2023) 的 SHOT 数据集 (853 快手短视频) 显示 AutoShot
  比 TransNetV2 高 4.2% F1。但 SHOT 视频需百度网盘下载 (GB 级), 本会话不可行。
  故改为在项目自有 B 站 AMV 素材 (data/real_amv_test, 58 视频) 上做交叉验证:
    TransNetV2 (神经网络) vs PySceneDetect ContentDetector (项目当前默认基线)。

  无 ground-truth 切点, 故报告"跨方法一致率"而非 precision/recall:
    - TransNetV2 检出切点数 / PySceneDetect 检出切点数
    - 一致率 = TransNetV2 切点被 PySceneDetect 佐证的比例 (±tolerance 帧)
    - TransNetV2 独有切点 (疑似闪帧/硬切, PySceneDetect 漏检)

用法:
  py -3.12 scripts/eval_transnetv2_bilibili.py --limit 2 --out models/output/transnetv2_bilibili_eval.json
  py -3.12 scripts/eval_transnetv2_bilibili.py   # 全量 58 视频
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

# TransNetV2 切点阈值
TRANSNET_THRESHOLD = 0.5
# 跨方法匹配容差 (帧)
TOLERANCE_FRAMES = 5


def transnetv2_cuts(video_path: str, model) -> Optional[np.ndarray]:
    """TransNetV2 逐帧预测 → 切点帧索引 (上升沿)。"""
    video_frames, single_pred, _ = model.predict_video(video_path, quiet=True)
    pred = single_pred.cpu().numpy() if hasattr(single_pred, "cpu") else np.asarray(single_pred)
    bin_pred = (pred > TRANSNET_THRESHOLD).astype(np.int8)
    cuts = []
    for i in range(1, len(bin_pred)):
        if bin_pred[i] == 1 and bin_pred[i - 1] == 0:
            cuts.append(i)
    return np.array(cuts, dtype=np.int64), int(video_frames.shape[0])


def pyscenedetect_cuts(video_path: str) -> Optional[np.ndarray]:
    """PySceneDetect ContentDetector 切点帧索引。"""
    from scenedetect import ContentDetector, detect
    scenes = detect(str(video_path), ContentDetector(threshold=27.0), show_progress=False)
    # scenes = [(start_ftc, end_ftc), ...]; 切点在每镜头起点 (首镜头除外)
    if not scenes:
        return np.array([], dtype=np.int64), 0
    cuts = [int(s[0].get_frames()) for s in scenes[1:]]
    return np.array(cuts, dtype=np.int64), int(scenes[-1][1].get_frames())


def _match(cuts_a: np.ndarray, cuts_b: np.ndarray, tol: int) -> int:
    """cuts_a 中有多少切点能在 cuts_b 的 ±tol 帧内找到佐证。"""
    if len(cuts_a) == 0 or len(cuts_b) == 0:
        return 0
    matched = 0
    for c in cuts_a:
        if np.any(np.abs(cuts_b - c) <= tol):
            matched += 1
    return matched


def main() -> int:
    # Windows GBK 控制台无法打印特殊 Unicode 文件名 → 强制 UTF-8 + 容错
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="TransNetV2 在 B 站素材的切点评估")
    parser.add_argument("--video-dir", default=str(PROJECT_ROOT / "data" / "real_amv_test"))
    parser.add_argument("--out", default=str(PROJECT_ROOT / "models" / "output" / "transnetv2_bilibili_eval.json"))
    parser.add_argument("--limit", type=int, default=0, help="只测前 N 个视频 (0=全部)")
    parser.add_argument("--ext", default=".mp4,.mov,.mkv,.avi,.webm,.flv")
    args = parser.parse_args()

    from transnetv2_pytorch import TransNetV2
    model = TransNetV2(device="auto")
    device = next(model.parameters()).device
    print(f"[TransNetV2] device={device}")

    exts = tuple(e.strip() for e in args.ext.split(","))
    videos = sorted(p for p in Path(args.video_dir).rglob("*") if p.suffix.lower() in exts)
    if args.limit > 0:
        videos = videos[:args.limit]
    print(f"[eval] {len(videos)} videos")

    results: List[Dict[str, Any]] = []
    t0 = time.time()
    for i, vp in enumerate(videos):
        row: Dict[str, Any] = {"video": str(vp)}
        try:
            tn_cuts, tn_frames = transnetv2_cuts(str(vp), model)
            row["transnet_frames"] = tn_frames
            row["transnet_cuts"] = int(len(tn_cuts))
        except Exception as exc:  # noqa: BLE001
            row["transnet_error"] = str(exc)
            tn_cuts = np.array([], dtype=np.int64)
        try:
            psd_cuts, psd_frames = pyscenedetect_cuts(str(vp))
            row["psd_frames"] = psd_frames
            row["psd_cuts"] = int(len(psd_cuts))
        except Exception as exc:  # noqa: BLE001
            row["psd_error"] = str(exc)
            psd_cuts = np.array([], dtype=np.int64)

        if len(tn_cuts) and len(psd_cuts):
            matched = _match(tn_cuts, psd_cuts, TOLERANCE_FRAMES)
            row["matched"] = matched
            row["agreement"] = round(matched / max(1, len(tn_cuts)), 4)
            row["transnet_only"] = int(len(tn_cuts) - matched)
            row["psd_only"] = int(len(psd_cuts) - _match(psd_cuts, tn_cuts, TOLERANCE_FRAMES))
        else:
            row["matched"] = 0
            row["agreement"] = 0.0
            row["transnet_only"] = int(len(tn_cuts))
            row["psd_only"] = int(len(psd_cuts))

        results.append(row)
        print(f"[{i + 1}/{len(videos)}] {vp.name[:40]:40s} "
              f"TN={row.get('transnet_cuts', '?')} PSD={row.get('psd_cuts', '?')} "
              f"agree={row.get('agreement', 0):.2f}")

    # 汇总
    ok = [r for r in results if "transnet_error" not in r and "psd_error" not in r]
    summary = {
        "n_videos": len(results),
        "n_ok": len(ok),
        "avg_transnet_cuts": round(float(np.mean([r["transnet_cuts"] for r in ok])), 2) if ok else 0,
        "avg_psd_cuts": round(float(np.mean([r["psd_cuts"] for r in ok])), 2) if ok else 0,
        "avg_agreement": round(float(np.mean([r.get("agreement", 0) for r in ok])), 4) if ok else 0,
        "total_transnet_cuts": int(sum(r["transnet_cuts"] for r in ok)),
        "total_psd_cuts": int(sum(r["psd_cuts"] for r in ok)),
        "total_transnet_only": int(sum(r.get("transnet_only", 0) for r in ok)),
        "total_psd_only": int(sum(r.get("psd_only", 0) for r in ok)),
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
