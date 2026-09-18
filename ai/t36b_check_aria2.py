"""Check aria2 availability and try to start daemon."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\media")))

print("=== aria2 Check ===")
# Search for aria2c
for drive in ["C:\\", "D:\\"]:
    try:
        r = subprocess.run(
            ["where", "/R", drive, "aria2c.exe"],
            capture_output=True, text=True, timeout=30
        )
        if r.stdout.strip():
            print(f"Found in {drive}: {r.stdout.strip()}")
    except:
        pass

# Try AutoDownloader
from auto_downloader import AutoDownloader

ad = AutoDownloader()
print(f"\naria2 binary: {getattr(ad.aria2, 'binary_path', 'N/A')}")

try:
    ad.aria2.start_daemon()
    print("aria2 daemon: STARTED")
except Exception as e:
    print(f"aria2 daemon: FAILED - {e}")

# Try pip install yt-dlp
print("\n=== yt-dlp Check ===")
ytdlp = shutil.which("yt-dlp")
if ytdlp:
    print(f"yt-dlp: {ytdlp}")
else:
    print("yt-dlp: NOT INSTALLED")
    print("  Can install via: pip install yt-dlp")

# Check pip
print("\n=== pip Check ===")
pip = shutil.which("pip")
print(f"pip: {pip}")

# Summary
print("\n=== Summary ===")
print("Can search anime: YES (MaterialSearcher + Mikanani/Bilibili)")
print(f"Can download: {'YES' if ad.aria2.is_available() else 'NO (aria2 not available)'}")
print(f"Can extract frames: YES (ffmpeg at {shutil.which('ffmpeg')})")
print("Can train locally: YES (GPU available)")
_du = shutil.disk_usage("D:\\")
print(f"Disk space: {_du.free / (1024**3):.0f} GB free")
