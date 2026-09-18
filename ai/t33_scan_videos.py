"""Scan video resources on D drive to identify anime content for multi-IP corpus."""
import json
import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

video_dir = Path(r"D:\AE-Work\resources\video")
results = []
for root, dirs, files in os.walk(video_dir):
    for f in files:
        fp = os.path.join(root, f)
        ext = os.path.splitext(f)[1].lower()
        if ext in ('.mp4', '.mkv', '.mov', '.avi'):
            size_mb = os.path.getsize(fp) / (1024 * 1024)
            rel = os.path.relpath(fp, video_dir)
            results.append({
                'path': fp, 'name': f, 'rel': rel,
                'size_mb': round(size_mb, 1),
                'dir': os.path.dirname(rel)
            })

by_dir = defaultdict(list)
for r in results:
    by_dir[r['dir']].append(r)

print(f"Total video files: {len(results)}")
total_gb = sum(r['size_mb'] for r in results) / 1024
print(f"Total size: {total_gb:.1f} GB")
print()

for d in sorted(by_dir.keys()):
    items = by_dir[d]
    total = sum(i['size_mb'] for i in items)
    print(f"[{d}] ({len(items)} files, {total:.0f} MB)")
    for i in sorted(items, key=lambda x: -x['size_mb'])[:5]:
        nm = i['name'][:60]
        print(f"  {nm:60s} {i['size_mb']:8.1f} MB")
    if len(items) > 5:
        print(f"  ... and {len(items) - 5} more")

# Also check D:\BaiduNetdiskDownload remaining
print("\n=== BaiduNetdiskDownload remaining ===")
baidu_dir = Path(r"D:\BaiduNetdiskDownload")
if baidu_dir.exists():
    for root, dirs, files in os.walk(baidu_dir):
        vids = [f for f in files if os.path.splitext(f)[1].lower() in ('.mp4','.mkv','.mov','.avi')]
        if vids:
            total = sum(os.path.getsize(os.path.join(root, f)) for f in vids) / (1024*1024)
            rel = os.path.relpath(root, baidu_dir)
            print(f"  [{rel}] {len(vids)} videos, {total:.0f} MB")
