import subprocess
import os
import json

FFMPEG = json.load(open("c:/Users/Administrator/Desktop/AE-Knowledge-Vault/config/media-config.json", encoding="utf-8"))["tools"]["ffmpeg"]

video = "D:/AE-Work/视频素材库/圣斗士沙加.mp4"
out_dir = "D:/AE-Work/style_copy/puppet_style/refs"
os.makedirs(out_dir, exist_ok=True)

cmd = [FFMPEG, "-i", video, "-vf", "fps=1", "-q:v", "2", "-frames:v", "8",
       os.path.join(out_dir, "saint_%03d.png"), "-y", "-hide_banner", "-loglevel", "error"]

subprocess.run(cmd, check=True)

frames = sorted([f for f in os.listdir(out_dir) if f.endswith(".png")])
print(f"提取了 {len(frames)} 帧关键帧:")
for f in frames:
    path = os.path.join(out_dir, f)
    print(f"  {f} ({os.path.getsize(path)/1024:.0f} KB)")
