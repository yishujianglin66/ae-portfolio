import os
from pathlib import Path

# Check mao_mao video directory
video_dir = Path(r"D:\AE-Work\resources\video")
for root, dirs, files in os.walk(video_dir):
    if "\u732b" in root:
        print(f"Dir: {root}")
        for f in files:
            fp = os.path.join(root, f)
            ext = os.path.splitext(f)[1].lower()
            size_mb = os.path.getsize(fp) / (1024*1024)
            print(f"  {f}: {size_mb:.1f} MB ({ext})")

# Check .env for API key
print()
env_path = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\.env")
if env_path.exists():
    content = env_path.read_text(encoding="utf-8")
    for line in content.splitlines():
        if "SILICON" in line.upper() or "API_KEY" in line.upper():
            parts = line.split("=", 1)
            if len(parts) == 2:
                val = parts[1].strip().strip('"').strip("'")
                masked = val[:8] + "..." if len(val) > 8 else val
                print(f"  {parts[0]}={masked}")

# Also check .env.doubao
env2 = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\.env.doubao")
if env2.exists():
    content = env2.read_text(encoding="utf-8")
    for line in content.splitlines():
        if "SILICON" in line.upper() or "API_KEY" in line.upper():
            parts = line.split("=", 1)
            if len(parts) == 2:
                val = parts[1].strip().strip('"').strip("'")
                masked = val[:8] + "..." if len(val) > 8 else val
                print(f"  [doubao] {parts[0]}={masked}")
