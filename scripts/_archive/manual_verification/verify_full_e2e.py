"""全流程 E2E：导入多帧 → 调色 → 渲染输出（修复路径）"""
import sys, os, time, tempfile, shutil, subprocess, ctypes
sys.path.insert(0, r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")

from integrations.davinci_fuscript import ResolveColorEngine, ColorGradeConfig, find_lut_for_preset

def get_long_path(short_path):
    """将 8.3 短路径转为长路径"""
    buf = ctypes.create_unicode_buffer(1024)
    if ctypes.windll.kernel32.GetLongPathNameW(short_path, buf, 1024) > 0:
        return buf.value
    return short_path

engine = ResolveColorEngine()

# === 1. 确保 Resolve 运行 ===
if not engine.check_resolve_running():
    print("[1/6] Launching Resolve...")
    engine.launch_resolve()
    time.sleep(5)
else:
    print("[1/6] Resolve already running")

# === 2. 准备素材（多帧图片） ===
frames_dir = r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\frames"
media_files = []
for i in range(1, 13):
    fp = os.path.join(frames_dir, f"frame_{i:03d}.png")
    if os.path.exists(fp):
        media_files.append(fp)
print(f"[2/6] Media files: {len(media_files)} frames")

# === 3. 准备 LUT ===
config = ColorGradeConfig(
    preset="cinematic",
    brightness=1.05,
    contrast=1.1,
    saturation=0.95,
)
lut_path = config.lut_path or find_lut_for_preset(config.preset)
safe_lut = engine._safe_lut_path(lut_path)
print(f"[3/6] LUT: {safe_lut}")

# === 4. 输出目录（使用长路径） ===
output_dir = get_long_path(os.path.join(tempfile.gettempdir(), "resolve_full_e2e_output"))
os.makedirs(output_dir, exist_ok=True)
print(f"[4/6] Output dir: {output_dir}")

# === 5. 构建并运行全流程 Pipeline ===
project_name = "FullE2E_Demo"
timeline_name = "MainTimeline"

print(f"[5/6] Building pipeline: project={project_name}, render=True")

lua_script = engine._build_pipeline_lua(
    project_name=project_name,
    media_files=media_files,
    timeline_name=timeline_name,
    lut_path=safe_lut,
    config=config,
    render=True,
    output_dir=output_dir,
)

# 保存 Lua 脚本
script_dir = tempfile.mkdtemp(prefix="resolve_e2e_")
script_path = os.path.join(script_dir, "pipeline.lua")
with open(script_path, "w", encoding="utf-8") as f:
    f.write(lua_script)

# 显示渲染部分的 Lua
print("\n=== Render Lua Section ===")
in_render = False
for line in lua_script.split('\n'):
    if 'Step 6' in line:
        in_render = True
    if in_render:
        print(line)
    if in_render and 'Pipeline Complete' in line:
        break

print(f"\n  Running fuscript...")
print("=" * 60)

proc = subprocess.run(
    [str(engine.fuscript_path), "-lua", script_path],
    capture_output=True, text=True, timeout=300,
    encoding="utf-8", errors="replace"
)

print("STDOUT:")
print(proc.stdout)
if proc.stderr.strip():
    print("STDERR:")
    print(proc.stderr)
print(f"Return code: {proc.returncode}")
print("=" * 60)

# === 6. 检查输出 ===
print(f"\n[6/6] Checking output at: {output_dir}")
output_files = []
for root, dirs, files in os.walk(output_dir):
    for f in files:
        fp = os.path.join(root, f)
        size = os.path.getsize(fp)
        output_files.append((fp, size))
        print(f"  {fp} ({size / 1024:.1f} KB)")

if output_files:
    print(f"\n✅ 全流程完成！输出 {len(output_files)} 个文件")
    for fp, size in output_files:
        print(f"  📹 {fp} ({size / 1024:.1f} KB)")
else:
    print(f"\n⚠️ 输出目录为空，检查 Resolve 默认渲染位置...")
    # 检查 Resolve 默认输出
    default_dirs = [
        os.path.expanduser("~/Documents"),
        os.path.expanduser("~/Videos"),
        "C:\\Users\\Administrator\\Documents",
    ]
    for d in default_dirs:
        for f in os.listdir(d) if os.path.exists(d) else []:
            if "FullE2E" in f or "output" in f.lower():
                print(f"  Found in {d}: {f}")

shutil.rmtree(script_dir, ignore_errors=True)
