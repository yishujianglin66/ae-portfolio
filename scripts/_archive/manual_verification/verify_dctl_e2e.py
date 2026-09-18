"""E2E 验证：使用 DCTL 预设进行调色"""
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
    ResolveColorEngine,
    find_dctl_for_preset,
    find_lut_for_preset,
)


def get_long_path(short_path):
    buf = ctypes.create_unicode_buffer(1024)
    if ctypes.windll.kernel32.GetLongPathNameW(short_path, buf, 1024) > 0:
        return buf.value
    return short_path

engine = ResolveColorEngine()

# 1. 确保 Resolve 运行
if not engine.check_resolve_running():
    print("[1/5] Launching Resolve...")
    engine.launch_resolve()
    time.sleep(5)
else:
    print("[1/5] Resolve already running")

# 2. 测试素材
test_frame = r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\frames\frame_001.png"
print(f"[2/5] Test media: {test_frame}")

# 3. 测试多个 DCTL 预设
dctl_presets = ["filmic", "opendrt", "tesseract", "primal", "saturation"]
print(f"[3/5] DCTL presets to test: {dctl_presets}")

for preset in dctl_presets:
    dctl_path = find_dctl_for_preset(preset)
    lut_path = find_lut_for_preset(preset)
    ext = os.path.splitext(lut_path)[1] if lut_path else "N/A"
    print(f"  {preset}: {ext} -> {os.path.basename(lut_path) if lut_path else 'NOT FOUND'}")

# 4. 使用 filmic DCTL 进行调色测试
print("\n[4/5] Running E2E with 'filmic' DCTL preset...")
dctl_path = find_lut_for_preset("filmic")
safe_dctl = engine._safe_lut_path(dctl_path)
print(f"  DCTL: {dctl_path}")
print(f"  Safe: {safe_dctl}")

config = ColorGradeConfig(
    preset="filmic",
    brightness=1.05,
    contrast=1.1,
    saturation=0.95,
)

output_dir = get_long_path(os.path.join(tempfile.gettempdir(), "resolve_dctl_e2e"))
os.makedirs(output_dir, exist_ok=True)

lua_script = engine._build_pipeline_lua(
    project_name="DCTL_E2E_Test",
    media_files=[test_frame],
    timeline_name="MainTimeline",
    lut_path=safe_dctl,
    config=config,
    render=True,
    output_dir=output_dir,
)

script_dir = tempfile.mkdtemp(prefix="resolve_dctl_")
script_path = os.path.join(script_dir, "dctl_test.lua")
with open(script_path, "w", encoding="utf-8") as f:
    f.write(lua_script)

proc = subprocess.run(
    [str(engine.fuscript_path), "-lua", script_path],
    capture_output=True, text=True, timeout=120,
    encoding="utf-8", errors="replace"
)

print("\nSTDOUT:")
print(proc.stdout)
if proc.stderr.strip():
    print("STDERR:")
    print(proc.stderr)
print(f"Return code: {proc.returncode}")

# 5. 检查输出
print("\n[5/5] Checking output...")
for f in os.listdir(output_dir):
    fp = os.path.join(output_dir, f)
    size = os.path.getsize(fp)
    print(f"  {f} ({size / 1024:.1f} KB)")

if any(os.path.getsize(os.path.join(output_dir, f)) > 0 for f in os.listdir(output_dir)):
    print("\n✅ DCTL 调色 E2E 验证通过！")
else:
    print("\n⚠️ 输出为空")

shutil.rmtree(script_dir, ignore_errors=True)
