import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

clip_base = "D:/AE-Work/视频素材库/冰海战记新素材/"
audio_base = "D:/AE-Work/音频素材库/BGM/"

# Check audio
audio_file = audio_base + "ae实战音乐.mp3"
print(f"Audio: {'EXISTS' if os.path.exists(audio_file) else 'MISSING'}")

# List actual files
print("\n--- Actual mp4 files in clip directory ---")
if os.path.exists(clip_base):
    actual_files = [f for f in os.listdir(clip_base) if f.endswith('.mp4')]
    for f in sorted(actual_files):
        print(f"  {f}")
    print(f"\nTotal mp4 files: {len(actual_files)}")
else:
    print("  DIRECTORY NOT FOUND!")

# Check each source from JSX
sources_in_jsx = [
    ("MUKANJYO", "p01 S1OP1-MUKANJYO.f30077.mp4"),
    ("TORCHES", "p02 S1ED1-Torches.f30080.mp4"),
    ("DarkCrow", "p03 S2OP2-Dark Crow.f30077.mp4"),
    ("RIVER", "p05 S2OP1-River.f30077.mp4"),
    ("PARADOX", "p07 S2OP2-Paradox.f30080.mp4"),
    ("EPIC_S1", "冰海战记第一季"),
    ("FIGHT_S2", "打戏"),
    ("MAD_4K", "4K_MAD.f30077.mp4"),
    ("MAD_REV", "revolution coming"),
]

print("\n--- Matching check ---")
for name, pattern in sources_in_jsx:
    found = False
    if os.path.exists(clip_base):
        for f in os.listdir(clip_base):
            if pattern in f and f.endswith('.mp4'):
                found = True
                break
    print(f"  {name}: {'FOUND' if found else 'MISSING'} (pattern: {pattern})")
