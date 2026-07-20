import subprocess
import os
import json

config = json.load(open("c:/Users/Administrator/Desktop/AE-Knowledge-Vault/config/media-config.json", encoding="utf-8"))
FFMPEG = config["tools"]["ffmpeg"]

source_video = "D:/AE-Work/视频素材库/托尔芬.mp4"
output_dir = "D:/AE-Work/style_copy/puppet_style"
os.makedirs(output_dir, exist_ok=True)

final_output = os.path.join(output_dir, "puppet_thorfinn_final.mp4")
prod_output = "D:/AE-Work/output/puppet_thorfinn_final.mp4"
os.makedirs("D:/AE-Work/output", exist_ok=True)

print("=" * 60)
print("  生成壮壮木偶风格视频 - 托尔芬")
print("=" * 60)
print()

# 完整滤镜链：抽帧 + 冷色调 + 高对比 + 暗角 + 颗粒 + 色差 + 音频处理
filter_chain = (
    # 抽帧到8fps再恢复(卡顿感)
    "fps=8,fps=30,"
    # 高对比度
    "eq=contrast=1.6:brightness=-0.08:saturation=0.75,"
    # 冷色调(色温偏蓝)
    "colortemperature=temperature=3500,"
    # 色彩平衡(阴影加蓝)
    "colorbalance=rs=0:gs=0:bs=0.15:rh=0:gh=0.05:bh=0.1,"
    # 暗角
    "vignette=angle=0.4:mode=forward,"
    # 胶片颗粒
    "noise=alls=12:allf=t+u,"
    # 轻微色差
    "chromashift=cbh=1:cbv=1:crh=-1:crv=-1"
)

audio_filter = "atempo=0.85,aecho=0.8:0.7:60:0.3,volume=1.1"

print("  应用滤镜链:")
print("    1. 抽帧 8fps → 30fps (卡顿感)")
print("    2. 对比度 +1.6, 亮度 -0.08, 饱和度 -25%")
print("    3. 色温 3500K (冷色调)")
print("    4. 阴影+15%蓝, 高光+5%青")
print("    5. 暗角 angle=0.4")
print("    6. 胶片颗粒 noise=12")
print("    7. 色差偏移")
print("    8. 音频: 降速0.85 + 回声 + 音量提升")
print()

cmd = [
    FFMPEG, "-i", source_video,
    "-vf", filter_chain,
    "-af", audio_filter,
    "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
    "-c:a", "aac", "-b:a", "192k",
    final_output,
    "-y", "-hide_banner", "-loglevel", "info"
]

print("  正在处理...")
result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

if result.returncode == 0 and os.path.exists(final_output):
    size = os.path.getsize(final_output)
    print(f"\n  ✓ 处理完成!")
    print(f"  输出: {final_output}")
    print(f"  大小: {size/1024/1024:.2f} MB")
    
    import shutil
    shutil.copy2(final_output, prod_output)
    print(f"  已复制到成品库: {prod_output}")
else:
    print(f"\n  ✗ 处理失败")
    print(f"  stderr: {result.stderr[:500]}")

print()
print("=" * 60)
