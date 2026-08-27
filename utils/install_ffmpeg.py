import zipfile, os, shutil

z = r'C:\Users\Administrator\Desktop\ffmpeg.zip'
d = r'C:\ffmpeg'

print("Extracting...")
with zipfile.ZipFile(z) as zf:
    zf.extractall(d)

# Find ffmpeg.exe bin dir
for dp, dn, fn in os.walk(d):
    if 'ffmpeg.exe' in fn:
        bin_dir = dp
        print(f"Found bin dir: {bin_dir}")
        break

# Add to user PATH permanently (HKCU)
import winreg
key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment", 0, winreg.KEY_ALL_ACCESS)
try:
    current_path = winreg.QueryValueEx(key, "Path")[0]
except FileNotFoundError:
    current_path = ""

if bin_dir not in current_path:
    new_path = current_path.rstrip(";") + ";" + bin_dir
    winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, new_path)
    print(f"Added to system PATH: {bin_dir}")
else:
    print("Already in PATH")
winreg.CloseKey(key)

# Also set for current process
os.environ["PATH"] = os.environ.get("PATH", "") + ";" + bin_dir

# Verify
import subprocess
result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
print(result.stdout.split('\n')[0])
print("FFmpeg installed successfully!")
