"""Concurrent disk scan - fast directory size aggregation for cleanup audit.
Usage: python scripts/scan_disk.py <root> [--depth N] [--out result.json]
Read-only: never modifies anything.
"""
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed


def scan_dir(path):
    """Return (size, file_count) for a directory tree. Errors are skipped."""
    total = 0
    count = 0
    stack = [path]
    while stack:
        cur = stack.pop()
        try:
            with os.scandir(cur) as it:
                for e in it:
                    try:
                        if e.is_symlink():
                            continue
                        if e.is_dir(follow_symlinks=False):
                            stack.append(e.path)
                        elif e.is_file(follow_symlinks=False):
                            total += e.stat(follow_symlinks=False).st_size
                            count += 1
                    except (OSError, PermissionError):
                        continue
        except (OSError, PermissionError):
            continue
    return total, count


def scan_children(root, max_workers=16):
    entries = []
    try:
        with os.scandir(root) as it:
            entries = [e for e in it if e.is_dir(follow_symlinks=False)]
    except (OSError, PermissionError):
        return []

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(scan_dir, e.path): e for e in entries}
        for f in as_completed(futs):
            e = futs[f]
            try:
                size, nfiles = f.result()
            except Exception:
                size, nfiles = 0, 0
            results.append({
                "path": e.path,
                "name": e.name,
                "size_gb": round(size / 1024 ** 3, 2),
                "size_mb": round(size / 1024 ** 2, 1),
                "files": nfiles,
            })
    results.sort(key=lambda r: -r["size_gb"])
    return results


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "D:/"
    out = None
    if "--out" in sys.argv:
        out = sys.argv[sys.argv.index("--out") + 1]
    t0 = time.time()
    res = scan_children(root)
    total = sum(r["size_gb"] for r in res)
    print(f"root={root} entries={len(res)} total={total:.1f}GB elapsed={time.time()-t0:.0f}s")
    for r in res[:40]:
        print(f"  {r['size_gb']:>8.2f} GB  {r['files']:>7} files  {r['name']}")
    if out:
        json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"saved -> {out}")


if __name__ == "__main__":
    main()
