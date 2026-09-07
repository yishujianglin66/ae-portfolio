"""build_highlight_cache.py — 预扫描源池生成高光评分磁盘缓存

production_director._get_highlight_pool() 只读缓存 (load_disk_cache)，不会自己算。
缓存缺席时它静默返回 None，选段回退 mood-ratio 均匀取点。本脚本负责把缓存建起来。

分析参数必须与 ai/production_director.py:3639-3642 完全一致 —— 缓存键 hash 含
sample_fps/resize/segment_duration/stride/motion_threshold，任一不符即 miss。
脚本对每个源做 save→load 往返校验，参数漂移会当场失败而不是静默产出废缓存。

用法：
  python scripts/build_highlight_cache.py                # 全量（约 30 分钟 / 14 源）
  python scripts/build_highlight_cache.py --force        # 忽略已有缓存重算
  python scripts/build_highlight_cache.py --sources a.mp4 b.mp4
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core.highlight_scorer import HighlightScorer
from scripts.unified_edit import DEFAULT_SOURCES

# 与 ai/production_director.py:3639-3642 保持一致，改动必须同步
SAMPLE_FPS = 6
RESIZE = (256, 144)
SEGMENT_DURATION = 2.0
CACHE_DIR = os.path.join(PROJECT, "cache", "highlight_scores")


def build(sources: list, force: bool) -> int:
    scorer = HighlightScorer(
        sample_fps=SAMPLE_FPS, resize=RESIZE, cache_enabled=True,
        disk_cache_dir=CACHE_DIR)

    ok, skipped, failed = [], [], []
    t_all = time.time()

    for i, src in enumerate(sources, 1):
        name = Path(src).name
        if not os.path.exists(src):
            print(f"[{i}/{len(sources)}] MISS  {name} — 文件不存在")
            failed.append((name, "文件不存在"))
            continue

        if not force:
            cached = scorer.load_disk_cache(src, segment_duration=SEGMENT_DURATION)
            if cached:
                print(f"[{i}/{len(sources)}] SKIP  {name} — 缓存已有 {len(cached)} 段")
                skipped.append(src)
                continue

        t0 = time.time()
        try:
            scores = scorer.score_all_segments(src, segment_duration=SEGMENT_DURATION)
        except Exception as e:
            print(f"[{i}/{len(sources)}] FAIL  {name} — 评分异常 {type(e).__name__}: {e}")
            failed.append((name, f"{type(e).__name__}: {e}"))
            continue

        if not scores:
            print(f"[{i}/{len(sources)}] FAIL  {name} — 0 段（时长不足 {SEGMENT_DURATION}s?）")
            failed.append((name, "0 段"))
            continue

        scorer.save_disk_cache(src, scores, segment_duration=SEGMENT_DURATION)

        # 往返校验：读不回来等于没建
        back = scorer.load_disk_cache(src, segment_duration=SEGMENT_DURATION)
        if not back or len(back) != len(scores):
            print(f"[{i}/{len(sources)}] FAIL  {name} — 往返校验失败 "
                  f"(写 {len(scores)} 段 / 读 {len(back) if back else 0} 段)；"
                  f"分析参数可能与 production_director 不一致")
            failed.append((name, "往返校验失败"))
            continue

        top = max(back, key=lambda s: s.total)
        el = time.time() - t0
        print(f"[{i}/{len(sources)}] OK    {name} — {len(back)} 段 / {el:.0f}s "
              f"(最高分 {top.total:.4f} @ {top.start_sec:.1f}s)")
        ok.append(src)

    print(f"\n=== 完成: 新建 {len(ok)} / 跳过 {len(skipped)} / 失败 {len(failed)} "
          f"| 可用合计 {len(ok) + len(skipped)}/{len(sources)} "
          f"| 总耗时 {(time.time() - t_all) / 60:.1f}min ===")
    print(f"缓存目录: {CACHE_DIR}")
    for name, why in failed:
        print(f"  FAIL {name}: {why}")
    return 1 if failed else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="预扫描源池生成高光评分磁盘缓存")
    ap.add_argument("--sources", nargs="*", default=None,
                    help="覆盖源池（默认取 scripts/unified_edit.py 的 DEFAULT_SOURCES）")
    ap.add_argument("--force", action="store_true", help="忽略已有缓存重算")
    args = ap.parse_args()

    sources = args.sources or DEFAULT_SOURCES
    return build(sources, args.force)


if __name__ == "__main__":
    sys.exit(main())
