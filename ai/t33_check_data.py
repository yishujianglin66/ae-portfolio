"""Quick check of data structures."""
import json
import os
from pathlib import Path

# Check mao_mao issue
mao_dir = Path(r"D:\multi_ip_corpus\mao_mao\frames")
if mao_dir.exists():
    frames = list(mao_dir.glob("frame_*.jpg"))
    print(f"mao_mao frames: {len(frames)}")
    for f in sorted(frames)[:5]:
        print(f"  {f.name} ({f.stat().st_size} bytes)")

# Check pending dir
pending = Path(r"D:\multi_ip_corpus")
for d in pending.iterdir():
    if d.is_dir() and d.name.startswith("pending"):
        print(f"\nPending: {d.name}")
        frames_dir = d / "frames"
        if frames_dir.exists():
            n = len(list(frames_dir.glob("frame_*.jpg")))
            print(f"  frames: {n}")

# Check all corpus dirs
print("\n=== All multi_ip_corpus directories ===")
for d in sorted(pending.iterdir()):
    if d.is_dir():
        frames_dir = d / "frames"
        n = len(list(frames_dir.glob("frame_*.jpg"))) if frames_dir.exists() else 0
        print(f"  {d.name:55s} {n:6d} frames")

# Check existing VLM data structure
vlm_path = Path(r"D:\aot_corpus\vlm_full\results.jsonl")
if vlm_path.exists():
    with open(vlm_path, "r", encoding="utf-8") as f:
        line = f.readline()
        data = json.loads(line)
        print(f"\nVLM data fields: {list(data.keys())}")
        print(f"  vlm_ip: {data.get('vlm_ip', '')}")
        print(f"  scene_type: {data.get('scene_type', '')}")
        print(f"  mood: {data.get('mood', '')}")
        print(f"  frame_path: {data.get('frame_path', '')[:80]}")

# Check pseudolabels structure
pseudo_path = Path(r"D:\aot_corpus\pseudolabels.json")
if pseudo_path.exists():
    d = json.load(open(pseudo_path, "r", encoding="utf-8"))
    print(f"\nPseudolabels: {len(d)} entries")
    if d:
        print(f"  fields: {list(d[0].keys())}")
        print(f"  ip: {d[0].get('ip', '')}")
        print(f"  frame_path: {d[0].get('frame_path', '')[:80]}")

# Check teacher labels
teacher_path = Path(r"D:\aot_corpus\teacher_labels")
if teacher_path.exists():
    tfiles = list(teacher_path.glob("*.json"))
    print(f"\nTeacher labels: {len(tfiles)} files")
    if tfiles:
        td = json.load(open(tfiles[0], "r", encoding="utf-8"))
        if isinstance(td, list) and td:
            print(f"  fields: {list(td[0].keys())}")
        elif isinstance(td, dict):
            print(f"  keys: {list(td.keys())[:10]}")
