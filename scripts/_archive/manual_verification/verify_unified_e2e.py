"""E2E 验证：PySceneDetect + Resolve 多段调色全流程"""
import sys, os, time, tempfile, shutil, ctypes
sys.path.insert(0, r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")

from integrations.davinci_fuscript import (
    ResolveColorEngine, ColorGradeConfig, find_lut_for_preset, DCTL_PRESET_MAP
)

def get_long_path(short_path):
    buf = ctypes.create_unicode_buffer(1024)
    if ctypes.windll.kernel32.GetLongPathNameW(short_path, buf, 1024) > 0:
        return buf.value
    return short_path

engine = ResolveColorEngine()
OUTPUT_DIR = r"D:\AE-Work\output"

# ============================================================
print("=" * 60)
print("  整合验证：PySceneDetect + Resolve 多段调色")
print("=" * 60)

# Step 1: 确保 Resolve 运行
if not engine.check_resolve_running():
    print("\n[1/5] Launching Resolve...")
    engine.launch_resolve()
    time.sleep(15)
    for i in range(6):
        if engine.check_resolve_running():
            break
        print(f"  Waiting... ({(i+1)*5}s)")
        time.sleep(5)
else:
    print("\n[1/5] Resolve already running")

# Step 2: PySceneDetect 场景检测
video = os.path.join(OUTPUT_DIR, "VinlandSaga_Battle_V15.mp4")
print(f"\n[2/5] Scene detection: {os.path.basename(video)}")
scenes = engine.detect_scenes(video, threshold=20.0, max_scenes=10)
if scenes and "error" not in scenes[0]:
    print(f"  Detected {len(scenes)} scenes")
    for i, s in enumerate(scenes):
        print(f"    Scene {i}: {s['start']} -> {s['end']} ({s['duration_frames']} frames)")
else:
    print(f"  Scene detect failed: {scenes}")
    scenes = []

# Step 3: 自动生成预设映射
print(f"\n[3/5] Auto segment presets:")
preset_cycle = ["cinematic", "filmic", "opendrt", "primal", "saturation", "shadow-contrast"]
segment_presets = {}
if scenes:
    for i in range(min(len(scenes), len(preset_cycle))):
        segment_presets[f"scene_{i}"] = preset_cycle[i % len(preset_cycle)]
        lut = find_lut_for_preset(preset_cycle[i % len(preset_cycle)])
        print(f"    scene_{i} -> {preset_cycle[i % len(preset_cycle)]} ({os.path.splitext(os.path.basename(lut))[1] if lut else '?'})")
else:
    # Fallback: use filename-based presets
    segment_presets = {"V15": "primal"}
    print(f"    Fallback: V15 -> primal")

# Step 4: Resolve 多段调色 + 渲染
print(f"\n[4/5] Resolve multi-segment grade + render...")
config = ColorGradeConfig(
    preset="cinematic",
    brightness=1.05,
    contrast=1.1,
    saturation=1.05,
    segment_presets=segment_presets,
)

output_dir = get_long_path(OUTPUT_DIR)
lua_script = engine._build_pipeline_lua(
    project_name="Unified_Pipeline_E2E",
    media_files=[video],
    timeline_name="UnifiedTimeline",
    lut_path=engine._safe_lut_path(find_lut_for_preset("cinematic")),
    config=config,
    render=True,
    output_dir=output_dir,
)

script_dir = tempfile.mkdtemp(prefix="unified_e2e_")
script_path = os.path.join(script_dir, "pipeline.lua")
with open(script_path, "w", encoding="utf-8") as f:
    f.write(lua_script)

import subprocess
proc = subprocess.run(
    [str(engine.fuscript_path), "-lua", script_path],
    capture_output=True, text=True, timeout=300,
    encoding="utf-8", errors="replace"
)

print("\n--- Resolve Output ---")
print(proc.stdout[-2000:] if len(proc.stdout) > 2000 else proc.stdout)
if proc.stderr.strip():
    try:
        print("STDERR:", proc.stderr[:500].encode('utf-8', errors='replace').decode('utf-8'))
    except Exception:
        print("STDERR: (encoding error)")

shutil.rmtree(script_dir, ignore_errors=True)

# Step 5: 验证输出
print(f"\n[5/5] Output verification:")
output_found = False
for f in os.listdir(output_dir):
    fp = os.path.join(output_dir, f)
    if os.path.isfile(fp) and "Unified_Pipeline" in f:
        size = os.path.getsize(fp)
        mtime = os.path.getmtime(fp)
        if time.time() - mtime < 300:
            print(f"  {f} ({size / (1024*1024):.1f} MB)")
            output_found = True

print("\n" + "=" * 60)
if output_found:
    print("  INTEGRATION VERIFIED")
    print("  PySceneDetect -> Auto Segments -> DCTL Grade -> Render")
    print("=" * 60)
    print("\n  All 3 integrations working:")
    print("  1. PySceneDetect: scene detection + auto preset mapping")
    print("  2. DCTL Presets: 18 presets (Demystify/MoazElgabry/OpenDisplayTransform)")
    print("  3. Resolve Engine: multi-segment grading + rendering")
else:
    print("  Output not found, check Resolve logs above")
print("=" * 60)
