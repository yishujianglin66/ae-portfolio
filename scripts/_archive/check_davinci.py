"""检查 DaVinci Resolve 实际功能可用性"""
import os
import sys
import traceback

sys.path.insert(0, r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")

# 1. Check DaVinciResolveScript module
try:
    import DaVinciResolveScript
    print("DaVinciResolveScript: IMPORTED OK")
    # Try to get Resolve instance
    try:
        resolve = DaVinciResolveScript.scriptapp("Resolve")
        print(f"  Resolve instance: {resolve}")
        fm = resolve.GetProjectManager()
        print(f"  ProjectManager: {fm}")
    except Exception as e:
        print(f"  Resolve API error: {e}")
except ImportError:
    print("DaVinciResolveScript: NOT AVAILABLE (Resolve not running or API not installed)")

# 2. Check our integration
from davinci_resolve_integration import DavinciColorist

c = DavinciColorist()
print(f"\nDavinciColorist mode: {c.config.mode}")
print(f"is_available: {c.is_available()}")
print(f"presets: {c.get_available_presets()[:5]}")

# 3. Try actual color_grade
test_video = r"D:\AE-Work\output\VinlandSaga_Battle_V17.mp4"
out = r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\output_production\davinci_test.mp4"
os.makedirs(os.path.dirname(out), exist_ok=True)

print("\nTrying color_grade...")
try:
    result = c.color_grade(input_path=test_video, output_path=out)
    print(f"  result type: {type(result).__name__}")
    if hasattr(result, 'status'):
        print(f"  status: {result.status}")
        print(f"  mode: {getattr(result, 'mode', '?')}")
        print(f"  output_files: {result.output_files}")
        print(f"  log: {result.log[:5] if result.log else 'none'}")
    else:
        print(f"  result: {str(result)[:300]}")
except Exception as e:
    traceback.print_exc()

# 4. Check if Resolve process is running
import subprocess

r = subprocess.run(["tasklist"], capture_output=True, text=True)
print(f"\nResolve running: {'Resolve.exe' in r.stdout}")
print(f"AE running: {'AfterFX.exe' in r.stdout}")
