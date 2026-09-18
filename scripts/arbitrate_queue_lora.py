#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""arbitrate_queue_lora.py — LoRA 分类器对复核队列 74 条做第三方仲裁

对 reviewed_results.jsonl 的每条样本跑 LoRA (VideoMAE anime_camera_lora v1,
val_acc 0.6365), 输出三方对照: VLM原始 / LK光流重标 / LoRA粗类。

输出: models/output/queue_lora_arbitration.json
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from models.anime_camera_classifier import AnimeCameraClassifier  # noqa: E402

DATA_ROOT = Path(r"D:\AE-Data\AnimeCamera")
REVIEWED = DATA_ROOT / "reviewed_results.jsonl"
OUT = PROJECT_ROOT / "models" / "output" / "queue_lora_arbitration.json"

# 粗类 → 细类近似 (Pull→zoom_out, Push→zoom_in, Static→static, Motion→方向不确定)
COARSE_TO_FINE = {"Static": "static", "Pull": "zoom_out", "Push": "zoom_in",
                  "Motion": "motion"}


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    rows = [json.loads(l) for l in REVIEWED.read_text(encoding="utf-8").splitlines()
            if l.strip()]
    clf = AnimeCameraClassifier()
    out: list[dict[str, Any]] = []
    t0 = time.time()
    for i, r in enumerate(rows):
        clip = r["clip_path"]
        try:
            pred = clf.classify_video(clip)
        except Exception as exc:  # noqa: BLE001
            pred = {"label": "unknown", "confidence": 0.0, "source": str(exc)}
        rec = {
            "shot_id": r["shot_id"],
            "vlm_label": r["original_label"],
            "vlm_confidence": r["original_confidence"],
            "flow_label": r["reviewed_label"],
            "flow_confidence": r["reviewed_confidence"],
            "lora_label": pred.get("label"),
            "lora_coarse": pred.get("coarse"),
            "lora_confidence": pred.get("confidence"),
            "lora_source": pred.get("source"),
        }
        out.append(rec)
        if (i + 1) % 10 == 0:
            print(f"  [{i + 1}/{len(rows)}] {r['shot_id']} -> "
                  f"{pred.get('label')} ({pred.get('coarse')})")
    print(f"完成, 用时 {time.time() - t0:.0f}s")

    # ── 三方对照统计 ──────────────────────────────────────────
    n = len(out)
    def agree(a: str, b: str) -> bool:
        return a == b

    flow_vs_vlm = sum(1 for r in out if agree(r["flow_label"], r["vlm_label"]))
    lora_flow = sum(1 for r in out
                    if COARSE_TO_FINE.get(r["lora_coarse"], r["lora_label"]) == r["flow_label"])
    lora_vlm = sum(1 for r in out
                   if COARSE_TO_FINE.get(r["lora_coarse"], r["lora_label"]) == r["vlm_label"])
    print(f"\n=== 三方对照 (n={n}) ===")
    print(f"flow vs VLM 一致: {flow_vs_vlm} ({100.0 * flow_vs_vlm / n:.1f}%)")
    print(f"LoRA粗类 vs flow 一致: {lora_flow} ({100.0 * lora_flow / n:.1f}%)")
    print(f"LoRA粗类 vs VLM 一致: {lora_vlm} ({100.0 * lora_vlm / n:.1f}%)")
    print("LoRA 粗类分布:", dict(Counter(r["lora_coarse"] for r in out)))

    # 争议样本: 三方互不相同 或 flow/lora 冲突
    print("\nLoRA=Static 但 flow≠static 的样本 (光流疑漏静态):")
    for r in out:
        if r["lora_coarse"] == "Static" and r["flow_label"] != "static":
            print(f"  {r['shot_id']:<22} VLM={r['vlm_label']:<8} "
                  f"flow={r['flow_label']:<10} LoRA=Static({r['lora_confidence']:.2f})")
    print("\nLoRA=Push 但 flow≠zoom_in 的样本 (光流疑漏推镜):")
    for r in out:
        if r["lora_coarse"] == "Push" and r["flow_label"] != "zoom_in":
            print(f"  {r['shot_id']:<22} VLM={r['vlm_label']:<8} "
                  f"flow={r['flow_label']:<10} LoRA=Push({r['lora_confidence']:.2f})")
    print("\nLoRA=Motion 样本的 flow 分布:")
    m_rows = [r for r in out if r["lora_coarse"] == "Motion"]
    print("  ", dict(Counter(r["flow_label"] for r in m_rows)))

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果 -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
