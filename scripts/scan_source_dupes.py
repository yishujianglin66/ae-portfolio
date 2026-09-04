"""Scan a production_report.json for globally reused source segments.

Acceptance check for the "same footage appears twice" defect (handoff 2026-09-04 section 3).

Usage:
    python scripts/scan_source_dupes.py output/unified_run53/production_report.json [--thresh 0.5]
Exit code 0 = no reuse and no file over 25%; 1 = violation.
"""

import json
import sys
from collections import defaultdict


def clusters_by_time(points, thresh):
    """Group ascending-sorted values whose neighbour gap is <= thresh."""
    groups, cur = [], []
    for p in points:
        if cur and p[0] - cur[-1][0] > thresh:
            if len(cur) > 1:
                groups.append(cur)
            cur = []
        cur.append(p)
    if len(cur) > 1:
        groups.append(cur)
    return groups


def main():
    path = sys.argv[1]
    thresh = float(sys.argv[sys.argv.index("--thresh") + 1]) if "--thresh" in sys.argv else 0.5

    segs = json.loads(open(path, encoding="utf-8").read())["script"]["segments"]
    by_file = defaultdict(list)
    for s in segs:
        src = s["source_file"].replace("\\", "/").rsplit("/", 1)[-1]
        by_file[src].append((float(s["source_start"]), float(s["start_time"])))

    reused = []
    for src, pts in by_file.items():
        for g in clusters_by_time(sorted(pts), thresh):
            reused.append((src, g))

    print(f"[scan_source_dupes] {len(segs)} shots, {len(by_file)} source files, thresh={thresh}s")
    for src, g in sorted(reused, key=lambda x: -len(x[1])):
        starts = ", ".join(f"{p[0]:.2f}" for p in g)
        times = ", ".join(f"{p[1]:.2f}" for p in g)
        print(f"  REUSE x{len(g)}  {src} @ [{starts}]  -> out times [{times}]")

    file_counts = {src: len(pts) for src, pts in by_file.items()}
    for src, n in sorted(file_counts.items(), key=lambda x: -x[1]):
        print(f"  SHARE {n / len(segs) * 100:5.1f}%  {src} x{n}")

    worst = max(file_counts.values()) / len(segs)
    bad = bool(reused) or worst > 0.25
    print(f"[scan_source_dupes] clusters={len(reused)} affected_shots="
          f"{sum(len(g) for _, g in reused)} max_share={worst * 100:.1f}% -> "
          f"{'FAIL' if bad else 'OK'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
