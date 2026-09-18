"""Check download capabilities and try to download anime."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

print("=== Download Tools Check ===\n")

# 1. yt-dlp
ytdlp = shutil.which("yt-dlp")
print(f"yt-dlp: {ytdlp or 'NOT FOUND'}")
if ytdlp:
    r = subprocess.run(["yt-dlp", "--version"], capture_output=True, text=True, timeout=5)
    print(f"  version: {r.stdout.strip()}")

# 2. aria2
aria2 = shutil.which("aria2c")
print(f"aria2c: {aria2 or 'NOT FOUND'}")

# 3. Check aria2 daemon
r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq aria2c.exe"], capture_output=True, text=True, timeout=5)
has_aria2 = "aria2c.exe" in r.stdout
print(f"aria2 daemon running: {has_aria2}")

# 4. Disk space
free_gb = shutil.disk_usage("D:\\").free / (1024**3)
print(f"\nD: free: {free_gb:.0f} GB")

# 5. Try MaterialSearcher
print("\n=== MaterialSearcher ===")
sys.path.insert(0, str(Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\scripts")))
try:
    from material_searcher import MaterialSearcher
    ms = MaterialSearcher()
    print(f"OK - {len(ms.adapters)} adapters")
    for a in ms.adapters:
        name = a.__class__.__name__
        pri = getattr(a, "priority", "?")
        print(f"  [{pri}] {name}")
except Exception as e:
    print(f"FAILED: {e}")

# 6. Try AutoDownloader
print("\n=== AutoDownloader ===")
sys.path.insert(0, str(Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\media")))
try:
    from auto_downloader import AutoDownloader
    ad = AutoDownloader()
    print("OK")
    print(f"  aria2 binary: {getattr(ad.aria2, 'binary_path', 'N/A')}")
    # Start daemon
    try:
        ad.aria2.start_daemon()
        print("  aria2 daemon: STARTED")
    except Exception as e:
        print(f"  aria2 daemon: {e}")
except Exception as e:
    print(f"FAILED: {e}")

# 7. What IPs need more data
print("\n=== Current IP Data ===")
multi_ip = Path(r"D:\multi_ip_corpus")
if multi_ip.exists():
    for d in sorted(multi_ip.iterdir()):
        if d.is_dir():
            frames = list(d.rglob("*.jpg")) + list(d.rglob("*.png"))
            print(f"  {d.name}: {len(frames)} frames")

# 8. What existing videos we have
print("\n=== Existing Videos (D:\\AE-Work\\resources\\video) ===")
video_dir = Path(r"D:\AE-Work\resources\video")
if video_dir.exists():
    vid_count = 0
    total_size = 0
    for root, dirs, files in os.walk(video_dir):
        for f in files:
            if f.lower().endswith(('.mp4','.mkv','.avi','.mov','.webm')):
                sz = os.path.getsize(os.path.join(root, f))
                total_size += sz
                vid_count += 1
    print(f"  {vid_count} videos, {total_size/1024/1024/1024:.2f} GB")
