"""查找 AE 和 DaVinci 安装路径"""
import glob
import os
import subprocess

# Find After Effects
for p in glob.glob(r"C:\Program Files\Adobe\Adobe After Effects*\Support Files\AfterFX.exe"):
    print(f"AE: {p}")
for p in glob.glob(r"C:\Program Files\Adobe\After Effects*\Support Files\AfterFX.exe"):
    print(f"AE: {p}")
for p in glob.glob(r"D:\Adobe\After Effects*\Support Files\AfterFX.exe"):
    print(f"AE: {p}")

# Find DaVinci Resolve
for p in [r"D:\DaVinci Resolve\Resolve.exe",
          r"C:\Program Files\Blackmagic Design\DaVinci Resolve\Resolve.exe"]:
    if os.path.exists(p):
        print(f"DaVinci: {p}")

# Check running
r = subprocess.run("tasklist", capture_output=True, text=True, shell=True)
print(f"AE running: {'AfterFX.exe' in r.stdout}")
print(f"Resolve running: {'Resolve.exe' in r.stdout}")
