"""子进程安装 anime-face-detector（由 venv-sam2 python 直接执行，不走 TRAE 沙箱 pip）。"""
import subprocess
import sys

python_exe = sys.executable
cmd = [python_exe, "-m", "pip", "install", "--no-input", "anime-face-detector"]
print("RUN:", " ".join(cmd), flush=True)
p = subprocess.run(cmd)
sys.exit(p.returncode)
