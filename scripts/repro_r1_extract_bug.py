# -*- coding: utf-8 -*-
"""复现 R1 bug：手工调 production_director._extract_clip 跑 seg 4 和 seg 5

绕过完整 director 初始化，直接拿方法对比相邻段的渲染产物。
"""
import json
import sys
import subprocess
import shutil
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ))

# 极简 stub: 绕开重型 __init__
import ai.production_director as pd_mod

# 备份原 __init__ 后替为 minimal
_orig_init = pd_mod.ProductionDirector.__init__
def _stub_init(self, *args, **kwargs):
    self.ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    self.ffprobe = shutil.which("ffprobe") or "ffprobe"
    self.work_dir = PROJ / "tmp" / "r1_probe" / "work"
    self.work_dir.mkdir(parents=True, exist_ok=True)
    self._source_durations = {}
    self._lut_path = None
    self._color_presets = {
        "climax": {"saturation": 1.2, "contrast": 1.05, "brightness": 0.0},
        "intro": {"saturation": 1.0, "contrast": 1.0, "brightness": 0.0},
    }
pd_mod.ProductionDirector.__init__ = _stub_init

d = json.loads((PROJ / "output/unified_run61/edl.json").read_text(encoding="utf-8"))
segs = d["cuts"]
dir_ = pd_mod.ProductionDirector()

# 探测所有相关源的时长（真实 _source_durations 行为）
for s in [segs[4], segs[5]]:
    src = s["source_file"]
    r = subprocess.run([dir_.ffprobe, "-v", "error", "-show_entries",
                        "format=duration", "-of", "csv=p=0", src],
                       capture_output=True, text=True)
    dur = float(r.stdout.strip() or "60.0")
    dir_._source_durations[src] = dur
    print(f"src_dur {Path(src).name}: {dur:.2f}s")

for i in [4, 5]:
    seg = segs[i]
    out = PROJ / "tmp" / "r1_probe" / "ext" / f"prod_seg{i}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    duration = float(seg["end_time"]) - float(seg["start_time"])
    ok = dir_._extract_clip(
        source=seg["source_file"],
        output=str(out),
        start_time=float(seg["source_start"]),
        duration=duration,
        resolution=(1920, 1080),
        fps=24.0,
        color=dir_._color_presets["climax"],
        speed=float(seg["speed"]),
        out_frames=max(2, round(duration * 24)),
    )
    print(f"seg {i} extract ok={ok} -> {out}")

# 比 f35/f37 与源在对应 source_start 处的帧
print("\n--- 验证：产物的关键帧 vs 源 ---")
for i in [4, 5]:
    p = PROJ / "tmp" / "r1_probe" / "ext" / f"prod_seg{i}.mp4"
    r = subprocess.run([dir_.ffprobe, "-v", "error", "-show_entries",
                        "stream=nb_read_packets", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True)
    print(f"  prod_seg{i} frames: {r.stdout.strip()}")

# 抓产物中间帧对比
for i in [4, 5]:
    p = PROJ / "tmp" / "r1_probe" / "ext" / f"prod_seg{i}.mp4"
    cmd = ["ffmpeg", "-y", "-i", str(p), "-vf", "scale=320:180",
           "-frames:v", "1", str(PROJ / f"tmp/r1_probe/ext/prod_seg{i}_m.png")]
    subprocess.run(cmd, capture_output=True)

import hashlib
for i in [4, 5]:
    p = PROJ / f"tmp/r1_probe/ext/prod_seg{i}_m.png"
    h = hashlib.md5(p.read_bytes()).hexdigest()[:10]
    print(f"prod_seg{i}_m hash={h}")