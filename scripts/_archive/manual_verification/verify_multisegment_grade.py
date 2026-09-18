r"""
实战演练：多段分段调色 + 渲染 + 输出闭环
==========================================
选取 D:\AE-Work\output 中多个视频，导入 Resolve，
对每个片段应用不同的 DCTL 调色预设 + Fusion 微调，
最终渲染输出到同目录。
"""
import ctypes
import os
import shutil
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")

from integrations.davinci_fuscript import (
    ColorGradeConfig,
    RenderConfig,
    ResolveColorEngine,
    find_dctl_for_preset,
    find_lut_for_preset,
)


def get_long_path(short_path):
    buf = ctypes.create_unicode_buffer(1024)
    if ctypes.windll.kernel32.GetLongPathNameW(short_path, buf, 1024) > 0:
        return buf.value
    return short_path

# ============================================================
# 配置
# ============================================================
OUTPUT_DIR = r"D:\AE-Work\output"

# 选取多个视频文件进行分段调色
SELECTED_VIDEOS = [
    os.path.join(OUTPUT_DIR, "VinlandSaga_Battle_V2.mp4"),        # 7 MB - 段1: cinematic
    os.path.join(OUTPUT_DIR, "E2E_VinlandSaga_Phase2.mp4"),       # 7.6 MB - 段2: filmic DCTL
    os.path.join(OUTPUT_DIR, "VinlandSaga_Battle_Final.mp4"),     # 14.5 MB - 段3: opendrt DCTL
    os.path.join(OUTPUT_DIR, "VinlandSaga_Battle_V15.mp4"),       # 19.8 MB - 段4: primal DCTL
]

# 分段调色预设映射（片段名关键词 -> preset）
SEGMENT_PRESETS = {
    "V2": "cinematic",       # V2 片段 -> cinematic (Demystify DCTL)
    "Phase2": "filmic",      # Phase2 片段 -> filmic (MoazElgabry DCTL)
    "Final": "opendrt",      # Final 片段 -> opendrt (OpenDisplayTransform DCTL)
    "V15": "primal",         # V15 片段 -> primal (Demystify DCTL)
}

# ============================================================
# 主流程
# ============================================================
engine = ResolveColorEngine()

# Step 1: 确保 Resolve 运行
print("=" * 60)
print("  多段分段调色实战演练")
print("=" * 60)

if not engine.check_resolve_running():
    print("\n[1/6] Launching DaVinci Resolve...")
    engine.launch_resolve()
    print("  Waiting for Resolve to initialize...")
    time.sleep(15)
    # 验证启动
    for i in range(6):
        if engine.check_resolve_running():
            break
        print(f"  Still waiting... ({(i+1)*5}s)")
        time.sleep(5)
else:
    print("\n[1/6] Resolve already running ✓")

# Step 2: 验证素材存在
print("\n[2/6] Verifying media files...")
valid_videos = []
for v in SELECTED_VIDEOS:
    if os.path.isfile(v):
        size_mb = os.path.getsize(v) / (1024 * 1024)
        print(f"  ✓ {os.path.basename(v)} ({size_mb:.1f} MB)")
        valid_videos.append(v)
    else:
        print(f"  ✗ NOT FOUND: {os.path.basename(v)}")

if not valid_videos:
    print("ERROR: No valid video files found!")
    sys.exit(1)

print(f"  Total: {len(valid_videos)} videos")

# Step 3: 显示分段调色方案
print("\n[3/6] Segment grading plan:")
print(f"  {'Segment':<30} {'Preset':<15} {'LUT/DCTL'}")
print(f"  {'-'*30} {'-'*15} {'-'*40}")
for key, preset in SEGMENT_PRESETS.items():
    lut = find_lut_for_preset(preset)
    lut_name = os.path.basename(lut) if lut else "NOT FOUND"
    ext = os.path.splitext(lut)[1] if lut else "?"
    print(f"  {key:<30} {preset:<15} [{ext}] {lut_name}")

# Step 4: 构建配置
print("\n[4/6] Building pipeline configuration...")
default_preset = "cinematic"
default_lut = find_lut_for_preset(default_preset)
safe_lut = engine._safe_lut_path(default_lut) if default_lut else None

config = ColorGradeConfig(
    preset=default_preset,
    brightness=1.05,       # 微增亮度
    contrast=1.1,          # 增强对比度
    saturation=1.05,       # 微增饱和度
    segment_presets=SEGMENT_PRESETS,
)

render_config = RenderConfig(
    format="MP4",
    codec="H.264",
    resolution="1920x1080",
    frame_rate="24",
    quality="18",
    timeout=600,
)

print(f"  Default preset: {default_preset}")
print(f"  Default LUT: {os.path.basename(safe_lut) if safe_lut else 'None'}")
print(f"  Brightness: {config.brightness}, Contrast: {config.contrast}, Saturation: {config.saturation}")
print(f"  Render: {render_config.format} / {render_config.codec} / {render_config.resolution}")
print(f"  Output: {OUTPUT_DIR}")

# Step 5: 构建并执行 Lua 管线
print("\n[5/6] Building Lua pipeline script...")
project_name = "MultiSegment_Grade_E2E"
timeline_name = "MultiSegmentTimeline"

lua_script = engine._build_pipeline_lua(
    project_name=project_name,
    media_files=valid_videos,
    timeline_name=timeline_name,
    lut_path=safe_lut,
    config=config,
    render=True,
    output_dir=OUTPUT_DIR,
    render_config=render_config,
)

# 写入临时 Lua 文件
script_dir = tempfile.mkdtemp(prefix="resolve_multiseg_")
script_path = os.path.join(script_dir, "multiseg_grade.lua")
with open(script_path, "w", encoding="utf-8") as f:
    f.write(lua_script)

print(f"  Lua script: {script_path}")
print(f"  Script size: {os.path.getsize(script_path)} bytes")

# 显示生成的 Lua 脚本（关键段落）
print("\n  --- Lua Script Preview (segment section) ---")
lines = lua_script.split("\n")
in_segment = False
for line in lines:
    if "segmentLUTs" in line or "Segment" in line:
        in_segment = True
    if in_segment:
        print(f"  | {line}")
        if line.strip() == "}" and "segmentLUTs" not in line:
            in_segment = False
print("  --- End Preview ---\n")

# 执行
print("[6/6] Executing pipeline via fuscript.exe...")
print("  This may take several minutes for rendering...")
start_time = time.time()

proc = subprocess.run(
    [str(engine.fuscript_path), "-lua", script_path],
    capture_output=True, text=True, timeout=600,
    encoding="utf-8", errors="replace"
)

elapsed = time.time() - start_time
print(f"\n  Execution time: {elapsed:.1f}s")
print(f"  Return code: {proc.returncode}")

# 输出完整日志
print("\n" + "=" * 60)
print("  FUSCRIPT OUTPUT")
print("=" * 60)
print(proc.stdout)
if proc.stderr.strip():
    print("\nSTDERR:")
    print(proc.stderr)

# Step 7: 验证输出
print("\n" + "=" * 60)
print("  OUTPUT VERIFICATION")
print("=" * 60)

output_files = []
for f in os.listdir(OUTPUT_DIR):
    fp = os.path.join(OUTPUT_DIR, f)
    if os.path.isfile(fp) and "MultiSegment" in f:
        size = os.path.getsize(fp)
        output_files.append((f, size))
        print(f"  {f} ({size / (1024*1024):.1f} MB)")

# 也检查 _output 后缀的文件
for f in os.listdir(OUTPUT_DIR):
    fp = os.path.join(OUTPUT_DIR, f)
    if os.path.isfile(fp) and "_output" in f and (f.endswith(".mp4") or f.endswith(".mov")):
        size = os.path.getsize(fp)
        mtime = os.path.getmtime(fp)
        # 只检查最近 10 分钟内创建的
        if time.time() - mtime < 600:
            already_listed = any(x[0] == f for x in output_files)
            if not already_listed:
                output_files.append((f, size))
                print(f"  {f} ({size / (1024*1024):.1f} MB) [recent]")

# 总结
print("\n" + "=" * 60)
print("  SUMMARY")
print("=" * 60)
print(f"  Videos imported: {len(valid_videos)}")
print(f"  Segment presets: {len(SEGMENT_PRESETS)}")
print(f"  Output files: {len(output_files)}")
print(f"  Execution time: {elapsed:.1f}s")

if output_files and any(s > 0 for _, s in output_files):
    total_size = sum(s for _, s in output_files) / (1024 * 1024)
    print(f"  Total output: {total_size:.1f} MB")
    print("\n  ✅ 多段分段调色实战完成！")
    print(f"  输出目录: {OUTPUT_DIR}")
else:
    print("\n  ⚠️ 未检测到有效输出文件")

# 清理
shutil.rmtree(script_dir, ignore_errors=True)
print("\nDone.")
