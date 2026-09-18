"""E2E 诊断测试 - 需要 DaVinci Resolve 运行环境"""
import pytest

pytestmark = pytest.mark.integration

import os
import shutil
import sys
import tempfile
import time

sys.path.insert(0, r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")

from integrations.davinci_fuscript import ColorGradeConfig, ResolveColorEngine, find_lut_for_preset

engine = ResolveColorEngine()

# 启动 Resolve
if not engine.check_resolve_running():
    print("Launching Resolve...")
    engine.launch_resolve()
else:
    print("Resolve already running")

time.sleep(3)

test_frame = r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\frames\frame_001.png"
print(f"Test media: {test_frame}")
print(f"Media exists: {os.path.exists(test_frame)}")

config = ColorGradeConfig(
    preset="cinematic",
    brightness=1.05,
    contrast=1.1,
    saturation=0.95,
)

lut_path = config.lut_path or find_lut_for_preset(config.preset)
safe_lut = engine._safe_lut_path(lut_path)
print(f"LUT: {lut_path}")
print(f"Safe LUT: {safe_lut}")
print(f"Safe LUT exists: {os.path.exists(safe_lut) if safe_lut else 'N/A'}")

# 生成 Lua 脚本
lua_script = engine._build_pipeline_lua(
    project_name="DiagTest",
    media_files=[test_frame],
    timeline_name="MainTimeline",
    lut_path=safe_lut,
    config=config,
    render=False,
    output_dir=None,
)

# 保存并显示 Step 5
lua_debug = os.path.join(tempfile.gettempdir(), "diag_pipeline.lua")
with open(lua_debug, 'w', encoding='utf-8') as f:
    f.write(lua_script)
print(f"\nLua saved to: {lua_debug}")

print("\n=== Step 5 (Color Grade) Lua Code ===")
in_step5 = False
for line in lua_script.split('\n'):
    if 'Step 5' in line:
        in_step5 = True
    if in_step5:
        print(line)
    if in_step5 and 'Pipeline Complete' in line:
        break

# 运行实际测试
print("\n=== Running actual fuscript ===")
script_dir = tempfile.mkdtemp(prefix="resolve_diag_")
script_path = os.path.join(script_dir, "script.lua")
with open(script_path, "w", encoding="utf-8") as f:
    f.write(lua_script)

import subprocess

proc = subprocess.run(
    [str(engine.fuscript_path), "-lua", script_path],
    capture_output=True, text=True, timeout=60,
    encoding="utf-8", errors="replace"
)

print("STDOUT:")
print(proc.stdout)
print("\nSTDERR:")
print(proc.stderr)
print(f"\nReturn code: {proc.returncode}")

shutil.rmtree(script_dir, ignore_errors=True)
"""E2E 诊断测试 - 显示调色每一步的详细输出"""
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, r'c:\Users\Administrator\Desktop\AE-Knowledge-Vault')
from integrations.davinci_fuscript import ColorGradeConfig, ResolveColorEngine

# 创建测试视频
test_dir = Path(tempfile.gettempdir()) / "resolve_diag"
test_dir.mkdir(exist_ok=True)
video_path = test_dir / "test_video.mp4"

if not video_path.exists():
    print("Creating test video...")
    try:
        from moviepy.editor import ColorClip
        clip = ColorClip(size=(1920, 1080), color=(100, 50, 200), duration=3)
        clip.write_videofile(str(video_path), fps=24, codec='libx264', logger=None)
    except Exception as e:
        print(f"moviepy failed: {e}")
        print("Trying ffmpeg...")
        import subprocess
        subprocess.run([
            r'C:\Users\Administrator\Desktop\AE-Knowledge-Vault\OpenSpace\.cache\ffmpeg.exe',
            '-f', 'lavfi', '-i', 'color=c=blue:s=1920x1080:d=3',
            '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(video_path), '-y'
        ], capture_output=True)

if not video_path.exists():
    print("ERROR: Cannot create test video")
    sys.exit(1)

print(f"Test video: {video_path}")

# 准备 LUT
lut_src = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\data\luts\cinematic_warm.cube")
lut_path = None
if lut_src.exists():
    lut_dir = test_dir / "luts"
    lut_dir.mkdir(exist_ok=True)
    lut_path = lut_dir / "test.cube"
    shutil.copy2(str(lut_src), str(lut_path))
    print(f"LUT: {lut_path}")
else:
    print("WARNING: No LUT file found")

# 运行引擎
engine = ResolveColorEngine()
print(f"Resolve running: {engine.check_resolve_running()}")

# 先打印生成的 Lua 脚本
config = ColorGradeConfig(lut_path=str(lut_path) if lut_path else None)
lua_content = engine._build_pipeline_lua(
    project_name="DiagTest",
    timeline_name="MainTimeline",
    media_files=[str(video_path)],
    config=config,
    segment_presets=None,
)

# 保存到文件供检查
lua_debug = test_dir / "debug_pipeline.lua"
with open(lua_debug, 'w', encoding='utf-8') as f:
    f.write(lua_content)
print(f"Lua script saved to: {lua_debug}")

# 显示 Step 5 相关部分
print("\n=== Step 5 (Color Grade) Lua Code ===")
in_step5 = False
for line in lua_content.split('\n'):
    if 'Step 5' in line:
        in_step5 = True
    if in_step5:
        print(line)
    if in_step5 and 'Pipeline Complete' in line:
        break

print("\n=== Running actual test ===")
result = engine.create_project(
    project_name="DiagTest",
    timeline_name="MainTimeline",
    media_files=[str(video_path)],
    config=config,
)

print(f"\nResult: {result}")
