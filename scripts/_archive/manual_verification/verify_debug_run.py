"""Debug: 启动 Resolve 并运行 Lua 脚本，捕获完整输出"""
import os
import sys

sys.path.insert(0, r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")

import shutil
import subprocess
import tempfile
import time

from integrations.davinci_fuscript import ColorGradeConfig, ResolveColorEngine, find_lut_for_preset

engine = ResolveColorEngine()

# 启动 Resolve
if not engine.check_resolve_running():
    print("Launching Resolve...")
    engine.launch_resolve()
else:
    print("Resolve already running")

time.sleep(3)  # 额外等待

test_frame = r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\frames\frame_001.png"

config = ColorGradeConfig(
    preset="cinematic",
    brightness=1.05,
    contrast=1.1,
    saturation=0.95,
)

lut_path = config.lut_path or find_lut_for_preset(config.preset)
safe_lut = engine._safe_lut_path(lut_path)
print(f"Safe LUT: {safe_lut}")

lua_script = engine._build_pipeline_lua(
    project_name="Debug_E2E",
    media_files=[test_frame],
    timeline_name="MainTimeline",
    lut_path=safe_lut,
    config=config,
    render=False,
    output_dir=None,
)

# 写入临时文件并运行
script_dir = tempfile.mkdtemp(prefix="resolve_debug_")
script_path = os.path.join(script_dir, "script.lua")
with open(script_path, "w", encoding="utf-8") as f:
    f.write(lua_script)

print("\nRunning fuscript...")
print("=" * 60)

proc = subprocess.run(
    [str(engine.fuscript_path), "-lua", script_path],
    capture_output=True, text=True, timeout=60,
    encoding="utf-8", errors="replace"
)

print("STDOUT:")
print(proc.stdout)
print()
print("STDERR:")
print(proc.stderr)
print()
print(f"Return code: {proc.returncode}")

shutil.rmtree(script_dir, ignore_errors=True)
