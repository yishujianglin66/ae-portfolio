"""测试 DaVinci fusionscript DLL 加载 - 添加 DLL 搜索路径"""
import ctypes
import os
import subprocess
import sys

resolve_dir = r"D:\DaVinci Resolve"

# 关键: 添加 Resolve 目录到 DLL 搜索路径
os.add_dll_directory(resolve_dir)
os.environ["PATH"] = resolve_dir + os.pathsep + os.environ.get("PATH", "")
os.environ["RESOLVE_SCRIPT_LIB"] = os.path.join(resolve_dir, "fusionscript.dll")

script_mod = r"C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\Modules"
if script_mod not in sys.path:
    sys.path.insert(0, script_mod)

# 清除缓存
for mod in list(sys.modules.keys()):
    if "DaVinci" in mod or "fusionscript" in mod:
        del sys.modules[mod]

print("=== Test 1: Import with DLL path ===")
try:
    import DaVinciResolveScript
    print("  Import OK!")
    resolve = DaVinciResolveScript.scriptapp("Resolve")
    print(f"  Resolve: {resolve}")
except Exception as e:
    print(f"  Failed: {e}")

print("\n=== Test 2: Direct ctypes load ===")
try:
    dll_path = os.path.join(resolve_dir, "fusionscript.dll")
    dll = ctypes.LoadLibrary(dll_path)
    print(f"  Direct load OK: {dll}")
except Exception as e:
    print(f"  Direct load failed: {e}")

print("\n=== Test 3: Check DLL dependencies ===")
dll_path = os.path.join(resolve_dir, "fusionscript.dll")
# Use objdump or manual PE parsing
with open(dll_path, "rb") as f:
    data = f.read()

# Find imported DLL names in PE import table
import re

# Look for common DLL names
dll_names = set(re.findall(b'([\\w]+\\.dll)', data, re.IGNORECASE))
print(f"  DLLs referenced in fusionscript.dll ({len(dll_names)}):")
for name in sorted(dll_names):
    n = name.decode("ascii", errors="ignore")
    if any(k in n.lower() for k in ["fusion", "resolve", "python", "qt", "api"]):
        print(f"    ** {n}")

# Check if Resolve has the needed support DLLs
print("\n=== Test 4: Check Resolve support files ===")
for subdir in ["", "libs", "bin", "Fusion"]:
    check_dir = os.path.join(resolve_dir, subdir) if subdir else resolve_dir
    if os.path.isdir(check_dir):
        for f in os.listdir(check_dir):
            fl = f.lower()
            if any(k in fl for k in ["fusion", "script", "resolve_api"]):
                fp = os.path.join(check_dir, f)
                sz = os.path.getsize(fp) // 1024 if os.path.isfile(fp) else 0
                print(f"  {subdir}/{f} ({sz}KB)" if subdir else f"{f} ({sz}KB)")

# Check if Resolve is running
print("\n=== Test 5: Resolve process ===")
r = subprocess.run("tasklist /FI \"IMAGENAME eq Resolve.exe\"", capture_output=True, text=True, shell=True)
print(f"  Resolve running: {'Resolve.exe' in r.stdout}")
