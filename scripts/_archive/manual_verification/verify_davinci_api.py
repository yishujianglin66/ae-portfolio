"""单独测试 DaVinci Resolve API 连接（延长等待）"""
import os, sys, time, ctypes, subprocess

sys.path.insert(0, r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")

# 设置环境变量
resolve_dll = r"D:\DaVinci Resolve\fusionscript.dll"
if os.path.exists(resolve_dll):
    os.environ["RESOLVE_SCRIPT_LIB"] = resolve_dll
    print(f"RESOLVE_SCRIPT_LIB set to: {resolve_dll}")

RESOLVE_EXE = r"D:\DaVinci Resolve\Resolve.exe"

def is_running(name):
    try:
        r = subprocess.run(["tasklist"], capture_output=True, text=True, timeout=10)
        return name.lower() in r.stdout.lower()
    except:
        return False

# 启动 Resolve
if not is_running("Resolve.exe"):
    print(f"Starting Resolve...")
    subprocess.Popen([RESOLVE_EXE])
    print("Process launched, waiting...")
else:
    print("Resolve already running")

# 等待窗口
user32 = ctypes.windll.user32
print("\n=== Step 1: Wait for Resolve window ===")
for i in range(60):
    time.sleep(2)
    hwnd = user32.FindWindowW(None, "DaVinci Resolve")
    if hwnd:
        print(f"  Window found at {(i+1)*2}s!")
        break
    if (i+1) % 5 == 0:
        print(f"  Waiting... {(i+1)*2}s (hwnd={hwnd})")
else:
    print("  Window not found after 120s")

# 等待 API
print("\n=== Step 2: Wait for Fusion API ===")
for attempt in range(30):
    time.sleep(5)
    # Clear cached imports
    for mod_name in list(sys.modules.keys()):
        if 'DaVinciResolveScript' in mod_name or 'fusionscript' in mod_name:
            del sys.modules[mod_name]
    
    resolve_script_path = r"C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\Modules"
    if resolve_script_path not in sys.path:
        sys.path.insert(0, resolve_script_path)
    
    try:
        import DaVinciResolveScript
        resolve_app = DaVinciResolveScript.scriptapp("Resolve")
        if resolve_app is not None:
            pm = resolve_app.GetProjectManager()
            print(f"\n  SUCCESS! API connected at {(attempt+1)*5}s!")
            print(f"  ProjectManager: {pm}")
            # Try to get current project
            proj = pm.GetCurrentProject()
            print(f"  Current Project: {proj}")
            break
        else:
            if (attempt+1) % 3 == 0:
                print(f"  Attempt {attempt+1}/30: instance is None")
    except Exception as e:
        if (attempt+1) % 3 == 0:
            print(f"  Attempt {attempt+1}/30: {str(e)[:80]}")
else:
    print("\n  FAILED: API not connected after 150s")
