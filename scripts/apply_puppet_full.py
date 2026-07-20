import subprocess
import os
import json

config = json.load(open("c:/Users/Administrator/Desktop/AE-Knowledge-Vault/config/media-config.json", encoding="utf-8"))
FFMPEG = config["tools"]["ffmpeg"]

video = "D:/AE-Work/视频素材库/圣斗士沙加.mp4"
output_dir = "D:/AE-Work/style_copy/puppet_style"
os.makedirs(output_dir, exist_ok=True)

# 完整木偶风格: 分步处理
print("=" * 60)
print("  木偶风格视频 - 完整处理链")
print("=" * 60)
print()

# Step 1: 抽帧(卡顿感) + 冷色调 + 高对比度 + 暗角
step1 = os.path.join(output_dir, "step1_jerky_color.mp4")
print("  Step 1/3: 抽帧 + 调色 + 暗角...")
cmd1 = [
    FFMPEG, "-i", video,
    "-vf", "fps=8,fps=30,eq=contrast=1.5:brightness=-0.08:saturation=0.75,vignette=angle=0.4",
    "-c:v", "libx264", "-preset", "medium", "-crf", "20",
    "-c:a", "aac", "-b:a", "128k",
    step1, "-y", "-hide_banner", "-loglevel", "error"
]
r1 = subprocess.run(cmd1, capture_output=True, text=True, timeout=300)
if r1.returncode == 0:
    print(f"    ✓ 大小: {os.path.getsize(step1)/1024/1024:.2f} MB")
else:
    print(f"    ✗ 失败: {r1.stderr[:200]}")

# Step 2: 添加噪声(胶片颗粒) + 色差
step2 = os.path.join(output_dir, "step2_grain_aberr.mp4")
print("  Step 2/3: 胶片颗粒 + 色差...")
cmd2 = [
    FFMPEG, "-i", step1,
    "-vf", "noise=alls=12:allf=t+u,chromashift=cbh=1:cbv=1:crh=-1:crv=-1",
    "-c:v", "libx264", "-preset", "medium", "-crf", "20",
    "-c:a", "copy",
    step2, "-y", "-hide_banner", "-loglevel", "error"
]
r2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=300)
if r2.returncode == 0:
    print(f"    ✓ 大小: {os.path.getsize(step2)/1024/1024:.2f} MB")
else:
    print(f"    ✗ 失败: {r2.stderr[:200]}")
    step2 = step1  # fallback

# Step 3: 音频处理(降速+回声)
final = os.path.join(output_dir, "thorfinn_puppet_final.mp4")
print("  Step 3/3: 音频氛围处理...")
cmd3 = [
    FFMPEG, "-i", step2,
    "-af", "atempo=0.85,aecho=0.8:0.7:60:0.3,volume=1.1",
    "-c:v", "copy",
    "-c:a", "aac", "-b:a", "128k",
    final, "-y", "-hide_banner", "-loglevel", "error"
]
r3 = subprocess.run(cmd3, capture_output=True, text=True, timeout=300)
if r3.returncode == 0:
    print(f"    ✓ 大小: {os.path.getsize(final)/1024/1024:.2f} MB")
else:
    print(f"    ✗ 失败: {r3.stderr[:200]}")
    # fallback: just copy
    import shutil
    shutil.copy2(step2, final)

# 复制到成品库
final_prod = "D:/AE-Work/成品库/木偶风格_圣斗士.mp4"
os.makedirs(os.path.dirname(final_prod), exist_ok=True)
import shutil
shutil.copy2(final, final_prod)

print()
print("=" * 60)
print("  ✓ 完成!")
print(f"  处理后: {final}")
print(f"  成品库: {final_prod}")
print(f"  大小: {os.path.getsize(final)/1024/1024:.2f} MB")
print()
print("  应用的效果:")
print("    1. 抽帧8fps→30fps (木偶卡顿感)")
print("    2. 高对比度1.5 + 降饱和度0.75 (戏剧化)")
print("    3. 降亮度-0.08 (暗调)")
print("    4. 暗角0.4 (聚焦中心)")
print("    5. 胶片颗粒noise=12 (复古质感)")
print("    6. 色差偏移 (光学缺陷美学)")
print("    7. 音频降速0.85 + 回声 (空灵感)")
print("=" * 60)
