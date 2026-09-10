# -*- coding: utf-8 -*-
"""复现：手工渲染 seg 4 + seg 5 然后 concat_hard，看边界帧是否真切了。"""
import json, sys, subprocess, shutil, hashlib
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ))

import ai.production_director as pd_mod

_orig_init = pd_mod.ProductionDirector.__init__
def _stub_init(self, *a, **kw):
    self.ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    self.ffprobe = shutil.which("ffprobe") or "ffprobe"
    self.work_dir = PROJ / "tmp" / "r1_probe" / "work"
    self.work_dir.mkdir(parents=True, exist_ok=True)
    self._source_durations = {}
    self._lut_path = None
    self._color_presets = {"climax": {"saturation": 1.2, "contrast": 1.05, "brightness": 0.0}}
pd_mod.ProductionDirector.__init__ = _stub_init

d = json.loads((PROJ / "output/unified_run61/edl.json").read_text(encoding="utf-8"))
segs = d["cuts"]
dir_ = pd_mod.ProductionDirector()

for s in [segs[4], segs[5]]:
    src = s["source_file"]
    r = subprocess.run([dir_.ffprobe, "-v", "error", "-show_entries",
                        "format=duration", "-of", "csv=p=0", src],
                       capture_output=True, text=True)
    dir_._source_durations[src] = float(r.stdout.strip() or "60.0")

# 渲染
clips = []
for i in [4, 5]:
    seg = segs[i]
    out = PROJ / "tmp" / "r1_probe" / "concat_test" / f"clip_{i}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    duration = float(seg["end_time"]) - float(seg["start_time"])
    ok = dir_._extract_clip(
        source=seg["source_file"], output=str(out),
        start_time=float(seg["source_start"]), duration=duration,
        resolution=(1920, 1080), fps=24.0,
        color=dir_._color_presets["climax"], speed=float(seg["speed"]),
        out_frames=max(2, round(duration * 24)),
    )
    print(f"seg {i} render ok={ok}")
    clips.append((str(out), seg))

# concat
concat_out = PROJ / "tmp" / "r1_probe" / "concat_test" / "joined.mp4"
ok = dir_._concat_hard([c[0] for c in clips], str(concat_out))
print(f"concat ok={ok}, size={concat_out.stat().st_size if concat_out.exists() else 0}")

# 看产物的两段拼接处（约 t=seg4 dur 处）
n_seg4 = round((float(segs[4]["end_time"]) - float(segs[4]["start_time"])) * 24)
print(f"seg 4 should have {n_seg4} frames (cut boundary at frame {n_seg4-1} -> {n_seg4})")

# 在边界前后抽帧
for fn_off in [n_seg4 - 2, n_seg4 - 1, n_seg4, n_seg4 + 1]:
    cmd = ["ffmpeg", "-y", "-i", str(concat_out),
           "-vf", f"select=eq(n\\,{fn_off})", "-frames:v", "1",
           "-s", "240x135",
           str(concat_out.parent / f"join_fn{fn_off}.png")]
    subprocess.run(cmd, capture_output=True)
    p = concat_out.parent / f"join_fn{fn_off}.png"
    if p.exists():
        print(f"  fn{fn_off}: hash={hashlib.md5(p.read_bytes()).hexdigest()[:10]}")