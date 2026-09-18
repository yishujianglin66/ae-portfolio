import importlib
import json
import os
import sys

# 读取FFmpeg路径
config = json.load(open("c:/Users/Administrator/Desktop/AE-Knowledge-Vault/config/media-config.json", encoding="utf-8"))
FFMPEG = config["tools"]["ffmpeg"]

video = "D:/AE-Work/视频素材库/圣斗士沙加.mp4"
output_dir = "D:/AE-Work/style_copy/puppet_style"
os.makedirs(output_dir, exist_ok=True)

# 木偶风格FFmpeg处理链
# 1. 抽帧(卡顿感) → 2. 冷色调+高对比度 → 3. 暗角 → 4. 胶片颗粒

output_step1 = os.path.join(output_dir, "step1_jerky.mp4")
output_step2 = os.path.join(output_dir, "step2_color.mp4")
output_final = os.path.join(output_dir, "thorfinn_puppet_style.mp4")

import subprocess

print("=" * 60)
print("  木偶风格视频处理")
print("=" * 60)
print()

# Step 1: 抽帧 + 冷色调 + 高对比度 + 暗角 + 胶片颗粒 (一步到位)
print("  Step 1: 应用木偶风格滤镜链...")

filter_chain = (
    # 抽帧到8fps再恢复(产生卡顿感)
    "fps=8,fps=30,"
    # 冷色调(色温偏蓝)
    "colortemperature=temperature=3500,"
    # 高对比度
    "eq=contrast=1.6:brightness=-0.05:saturation=0.8,"
    # 暗角
    "vignette=angle=0.4:mode=forward,"
    # 胶片颗粒
    "noise=alls=15:allf=t+u,"
    # 轻微色差(色散效果)
    "chromashift=cbh=2:cbv=1:crh=-2:crv=-1"
)

cmd = [
    FFMPEG, "-i", video,
    "-vf", filter_chain,
    "-c:v", "libx264", "-preset", "medium", "-crf", "20",
    "-c:a", "aac", "-b:a", "128k",
    "-atempo", "0.85",  # 降速(缓慢感)
    output_final,
    "-y", "-hide_banner", "-loglevel", "info"
]

print(f"  滤镜链: {filter_chain[:80]}...")
print()

result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

if result.returncode == 0 and os.path.exists(output_final):
    size = os.path.getsize(output_final)
    print("  ✓ 处理完成!")
    print(f"  输出: {output_final}")
    print(f"  大小: {size/1024/1024:.2f} MB")
else:
    print("  ✗ 处理失败")
    print(f"  错误: {result.stderr[:500]}")
    
    # 简化滤镜重试
    print()
    print("  尝试简化滤镜...")
    
    simple_filter = (
        "fps=8,fps=30,"
        "eq=contrast=1.5:brightness=-0.05:saturation=0.8,"
        "vignette=angle=0.4"
    )
    
    cmd_simple = [
        FFMPEG, "-i", video,
        "-vf", simple_filter,
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "128k",
        output_final,
        "-y", "-hide_banner", "-loglevel", "error"
    ]
    
    result2 = subprocess.run(cmd_simple, capture_output=True, text=True, timeout=300)
    
    if result2.returncode == 0 and os.path.exists(output_final):
        size = os.path.getsize(output_final)
        print("  ✓ 简化处理完成!")
        print(f"  输出: {output_final}")
        print(f"  大小: {size/1024/1024:.2f} MB")
    else:
        print(f"  ✗ 简化处理也失败: {result2.stderr[:300]}")

print()
print("=" * 60)
