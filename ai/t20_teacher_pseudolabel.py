# -*- coding: utf-8 -*-
r"""T20: 教师伪标签生成 — 用集成模型(laion=0.3/cclip=0.7)对语料库全量帧推理。

产物:
  D:\aot_corpus\pseudolabels.json  — 每帧伪标签 {frame, shot, t_in, t_out, ip, confidence, scores_top3}
  D:\aot_corpus\pseudolabel_stats.json — 统计摘要

验收:
  1. 全部29566帧均有伪标签
  2. IP分布合理(进击的巨人占主体)
  3. 高置信度帧占比>60%
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Dict, List

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ai.clip_ensemble import EnsembleKB, BB_TAGS
from ai.clip_backbones import BackboneRegistry, ensemble_frame_scores

CORPUS_META = Path(r"D:\aot_corpus\corpus_meta.json")
CORPUS_FRAMES = Path(r"D:\aot_corpus\frames")
PSEUDO_OUT = Path(r"D:\aot_corpus\pseudolabels.json")
PSEUDO_STATS = Path(r"D:\aot_corpus\pseudolabel_stats.json")
PSEUDO_CKPT = Path(r"D:\aot_corpus\pseudolabel_ckpt.json")

# 最优集成权重(T6验收结果)
BEST_WEIGHTS = {"laion": 0.3, "cclip": 0.7}
BATCH_SIZE = 64
CKPT_INTERVAL = 500


def _log(msg: str):
    print(f"[T20] {msg}", flush=True)


def load_checkpoint() -> tuple:
    """加载断点: (已完成帧集合, 已保存的伪标签列表)"""
    if PSEUDO_CKPT.exists():
        try:
            ckpt = json.loads(PSEUDO_CKPT.read_text(encoding="utf-8"))
            done = set(ckpt.get("done_frames", []))
            labels = ckpt.get("labels", [])
            _log(f"断点续传: {len(done)}帧已完成, {len(labels)}条伪标签")
            return done, labels
        except Exception:
            pass
    return set(), []


def save_checkpoint(done_set: set, labels: list):
    """保存断点"""
    ckpt = {
        "done_frames": sorted(done_set),
        "labels": labels,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    PSEUDO_CKPT.write_text(json.dumps(ckpt, ensure_ascii=False), encoding="utf-8")


def generate_pseudolabels():
    """主流程: 批量推理语料帧生成伪标签"""
    _log("=" * 60)
    _log("T20 教师伪标签生成")
    _log(f"权重: {BEST_WEIGHTS}")
    _log("=" * 60)

    # 1. 加载语料元数据
    if not CORPUS_META.exists():
        _log(f"❌ 语料元数据不存在: {CORPUS_META}")
        return None
    meta = json.loads(CORPUS_META.read_text(encoding="utf-8"))
    videos = meta.get("videos", [])
    _log(f"语料: {len(videos)}个视频")

    # 2. 收集所有帧文件
    all_frame_entries = []
    for vid in videos:
        vid_name = vid.get("name", "")
        for fr in vid.get("frames", []):
            fp = Path(fr["frame"])
            if fp.exists():
                all_frame_entries.append({
                    "frame_path": str(fp),
                    "frame_name": fp.name,
                    "vid_name": vid_name,
                    "shot": fr.get("shot", 0),
                    "t_in": fr.get("t_in", 0),
                    "t_out": fr.get("t_out", 0),
                    "t": fr.get("t", 0),
                })

    _log(f"总帧文件: {len(all_frame_entries)}")

    # 3. 断点续传
    done_set, pseudolabels = load_checkpoint()
    remaining = [e for e in all_frame_entries if e["frame_name"] not in done_set]
    _log(f"待处理: {len(remaining)} (已完成 {len(done_set)})")

    if not remaining:
        _log("全部帧已处理，跳过推理")
    else:
        # 4. 初始化集成KB
        _log("初始化EnsembleKB(全量训练数据作支持集)...")
        t0 = time.time()
        registry = BackboneRegistry()
        kb = EnsembleKB(registry, golden_videos=set())  # 不排除任何视频
        _log(f"KB初始化: {len(kb.classes)}类, {len(kb.support_paths)}支持类, {time.time()-t0:.1f}s")

        # 5. 批量推理
        _log(f"开始批量推理 | batch={BATCH_SIZE} | 剩余={len(remaining)}")
        batch_paths = []
        batch_entries = []
        processed = 0
        t_start = time.time()

        for i, entry in enumerate(remaining):
            batch_paths.append(Path(entry["frame_path"]))
            batch_entries.append(entry)

            if len(batch_paths) >= BATCH_SIZE or i == len(remaining) - 1:
                # 编码当前batch
                per_bb_embs = {}
                for bb_name in BEST_WEIGHTS:
                    if BEST_WEIGHTS[bb_name] > 0:
                        bb = registry.get(bb_name)
                        per_bb_embs[bb_name] = bb.encode_images(batch_paths)

                # 逐帧打分
                for fi, entry in enumerate(batch_entries):
                    scores_by_bb = {}
                    for bb_name, embs in per_bb_embs.items():
                        scores_by_bb[bb_name] = kb.frame_scores(bb_name, embs[fi])

                    # 融合
                    fused = ensemble_frame_scores(scores_by_bb, BEST_WEIGHTS)
                    pred_ip = fused[0][0]
                    pred_score = fused[0][1]

                    # top-3
                    top3 = [(ip, round(sc, 4)) for ip, sc in fused[:3]]

                    pseudolabels.append({
                        "frame": entry["frame_name"],
                        "frame_path": entry["frame_path"],
                        "shot": entry["shot"],
                        "t_in": entry["t_in"],
                        "t_out": entry["t_out"],
                        "ip": pred_ip,
                        "confidence": round(pred_score, 4),
                        "scores_top3": top3,
                    })
                    done_set.add(entry["frame_name"])

                processed += len(batch_entries)
                elapsed = time.time() - t_start
                fps = processed / elapsed if elapsed > 0 else 0
                eta = (len(remaining) - processed) / fps if fps > 0 else 0
                _log(f"  [{processed}/{len(remaining)}] {fps:.1f}帧/s ETA={eta:.0f}s")

                # 定期保存断点
                if processed % CKPT_INTERVAL < BATCH_SIZE:
                    save_checkpoint(done_set, pseudolabels)

                batch_paths = []
                batch_entries = []

    # 6. 最终保存
    _log(f"保存伪标签: {PSEUDO_OUT}")
    PSEUDO_OUT.write_text(
        json.dumps(pseudolabels, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    # 7. 统计
    ip_counter = Counter(p["ip"] for p in pseudolabels)
    conf_values = [p["confidence"] for p in pseudolabels]
    high_conf = sum(1 for c in conf_values if c >= 0.6)
    stats = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_frames": len(pseudolabels),
        "unique_ips": len(ip_counter),
        "ip_distribution": dict(ip_counter.most_common()),
        "confidence_stats": {
            "mean": round(float(np.mean(conf_values)), 4),
            "median": round(float(np.median(conf_values)), 4),
            "min": round(float(np.min(conf_values)), 4),
            "max": round(float(np.max(conf_values)), 4),
            "high_conf_ratio": round(high_conf / len(conf_values), 4) if conf_values else 0,
        },
    }
    PSEUDO_STATS.write_text(
        json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    _log(f"\n{'='*60}")
    _log(f"✅ T20完成: {len(pseudolabels)}帧伪标签")
    _log(f"   IP类: {len(ip_counter)}")
    _log(f"   平均置信度: {stats['confidence_stats']['mean']}")
    _log(f"   高置信度(≥0.6): {stats['confidence_stats']['high_conf_ratio']*100:.1f}%")
    _log(f"   Top-5 IP: {ip_counter.most_common(5)}")
    _log(f"{'='*60}")

    # 清理断点文件
    PSEUDO_CKPT.unlink(missing_ok=True)

    return stats


if __name__ == "__main__":
    generate_pseudolabels()
