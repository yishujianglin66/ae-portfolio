"""全量扫描58个透明视频的检出率，每200帧采样一次。

判定标准：
  - 优秀: 有前景帧 > 80%，平均前景 > 10%
  - 正常: 有前景帧 50-80%
  - 偏低: 有前景帧 20-50%
  - 极低: 有前景帧 < 20%（需重跑）
"""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

import cv2
import numpy as np

FFMPEG = r"C:\ffmpeg\bin\ffmpeg.exe"
FFPROBE = r"C:\ffmpeg\bin\ffprobe.exe"
TMP = Path(r"D:\AE-Work\scan_tmp.png")

BASES = [
    Path(r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault\data\output\batch_auto_frame"),
    Path(r"D:\AE-Work\batch_auto_frame"),
]

STEP = 200  # 每200帧采样


def get_frame_count(mov: Path) -> int:
    r = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=nb_frames", "-of", "default=noprint_wrappers=1:nokey=1", str(mov)],
        capture_output=True, text=True,
    )
    try:
        return int(r.stdout.strip())
    except ValueError:
        return 0


def scan_video(mov: Path) -> dict:
    total = get_frame_count(mov)
    if total == 0:
        return {"total": 0, "sampled": 0, "has_fg": 0, "no_fg": 0, "avg_fg": 0, "max_fg": 0}

    has_fg = 0
    no_fg = 0
    fg_list = []
    for idx in range(0, total, STEP):
        cmd = [FFMPEG, "-y", "-i", str(mov), "-vf", f"select=eq(n\\,{idx})",
               "-vframes", "1", "-pix_fmt", "rgba", "-f", "image2", str(TMP)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0 or not TMP.exists():
            continue
        d = np.fromfile(str(TMP), dtype=np.uint8)
        try:
            TMP.unlink(missing_ok=True)
        except PermissionError:
            pass
        f = cv2.imdecode(d, cv2.IMREAD_UNCHANGED)
        if f is None or f.ndim != 3 or f.shape[2] != 4:
            continue
        a = f[:, :, 3]
        fg = (a > 127).mean() * 100
        fg_list.append(fg)
        if fg > 0.1:
            has_fg += 1
        else:
            no_fg += 1

    sampled = has_fg + no_fg
    return {
        "total": total,
        "sampled": sampled,
        "has_fg": has_fg,
        "no_fg": no_fg,
        "avg_fg": np.mean(fg_list) if fg_list else 0,
        "max_fg": max(fg_list) if fg_list else 0,
    }


# 收集所有成品
all_movs = []
for base in BASES:
    if base.exists():
        all_movs.extend(sorted(base.rglob("*_transparent.mov")))

print(f"全量扫描 {len(all_movs)} 个透明视频（每{STEP}帧采样）\n")
t0 = time.time()

results = []
for i, mov in enumerate(all_movs):
    s = scan_video(mov)
    sampled = s["sampled"]
    if sampled == 0:
        grade = "FAIL"
        fg_pct = 0
    else:
        fg_pct = s["has_fg"] / sampled * 100
        if fg_pct > 80 and s["avg_fg"] > 10:
            grade = "优秀"
        elif fg_pct > 50:
            grade = "正常"
        elif fg_pct > 20:
            grade = "偏低"
        else:
            grade = "极低"

    s["name"] = mov.parent.name[:45]
    s["grade"] = grade
    s["fg_pct"] = fg_pct
    s["mov"] = str(mov)
    results.append(s)

    elapsed = time.time() - t0
    eta = elapsed / (i + 1) * (len(all_movs) - i - 1)
    print(f"  [{i+1:2d}/{len(all_movs)}] {s['name']:47s} {grade}  "
          f"有前景={s['has_fg']:2d}/{sampled:2d}({fg_pct:4.0f}%)  "
          f"平均={s['avg_fg']:4.1f}%  ETA={eta:.0f}s")

# 汇总
print(f"\n{'='*80}")
print(f"扫描完成，耗时 {time.time()-t0:.0f}s\n")

grades = {"优秀": [], "正常": [], "偏低": [], "极低": [], "FAIL": []}
for r in results:
    grades[r["grade"]].append(r)

for grade in ["优秀", "正常", "偏低", "极低", "FAIL"]:
    items = grades[grade]
    print(f"{grade}: {len(items)} 个")
    if grade in ("偏低", "极低", "FAIL"):
        for r in items:
            print(f"  {r['name']}  有前景={r['has_fg']}/{r['sampled']}({r['fg_pct']:.0f}%)  平均={r['avg_fg']:.1f}%  路径={r['mov']}")

# 保存需要重跑的列表
rerun_list = [r for r in results if r["grade"] in ("极低", "偏低")]
if rerun_list:
    import json
    out = Path(r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault\data\temp\rerun_candidates.json")
    out.write_text(json.dumps(rerun_list, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n需重跑列表: {out} ({len(rerun_list)} 个)")
