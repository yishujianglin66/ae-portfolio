"""Try to search and download anime via MaterialSearcher."""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\scripts")))
sys.path.insert(0, str(Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\media")))

from material_searcher import MaterialSearcher

print("=== Anime Search & Download Test ===\n")

ms = MaterialSearcher()

# Target IPs we need more data for
target_anime = [
    "blue lock",        # 蓝色监狱
    "solo leveling",    # 独自升级
    "jujutsu kaisen",   # 咒术回战
    "kaguya sama",      # 辉夜大小姐
]

DOWNLOAD_DIR = Path(r"D:\anime_downloads")
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

for anime in target_anime:
    print(f"\n--- Searching: {anime} ---")
    try:
        results = ms.search(anime, min_results=1, max_per_source=2)
        print(f"  Found {len(results)} results")
        for r in results[:3]:
            title = r.get("title", "?")[:60]
            source = r.get("source", "?")
            size = r.get("size", "?")
            url = r.get("url", r.get("magnet", ""))[:80]
            print(f"  [{source}] {title}")
            print(f"    size={size} url={url[:60]}...")
    except Exception as e:
        print(f"  Search failed: {e}")

print("\n=== Done ===")
