#!/usr/bin/env python3
"""
ComfyUI 启动脚本
=================
检测环境并启动 ComfyUI 服务。

用法:
  py scripts/start_comfyui.py              # 正常启动
  py scripts/start_comfyui.py --check      # 仅检查环境
  py scripts/start_comfyui.py --port 8188  # 指定端口
"""
import os
import sys
import json
import time
import signal
import subprocess
import argparse
from pathlib import Path

# ComfyUI 根目录
COMFYUI_DIR = Path(__file__).parent.parent / "external" / "ComfyUI"
OUTPUT_DIR = Path(__file__).parent.parent / "output" / "comfyui"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def check_environment():
    """检查运行环境"""
    report = {"ok": True, "checks": {}}

    # Python
    report["checks"]["python"] = sys.version.split()[0]

    # Torch + CUDA
    try:
        import torch
        report["checks"]["torch"] = torch.__version__
        report["checks"]["cuda"] = torch.cuda.is_available()
        if torch.cuda.is_available():
            report["checks"]["gpu"] = torch.cuda.get_device_name(0)
            vram_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
            report["checks"]["vram_gb"] = round(vram_gb, 1)
        else:
            report["checks"]["gpu"] = "CPU only"
    except ImportError:
        report["checks"]["torch"] = "MISSING"
        report["ok"] = False

    # ComfyUI 目录
    report["checks"]["comfyui_dir"] = str(COMFYUI_DIR)
    report["checks"]["comfyui_exists"] = COMFYUI_DIR.is_dir()
    report["checks"]["main_py_exists"] = (COMFYUI_DIR / "main.py").is_file()

    # 关键依赖
    deps = ["aiohttp", "transformers", "safetensors", "einops",
            "torchsde", "alembic", "sqlalchemy", "kornia", "spandrel"]
    missing = []
    for d in deps:
        try:
            __import__(d)
        except ImportError:
            missing.append(d)
    report["checks"]["missing_deps"] = missing
    if missing:
        report["ok"] = False

    # 模型文件
    models_dir = COMFYUI_DIR / "models" / "checkpoints"
    if models_dir.is_dir():
        ckpts = list(models_dir.glob("*.safetensors")) + list(models_dir.glob("*.ckpt"))
        report["checks"]["checkpoint_count"] = len(ckpts)
        report["checks"]["checkpoints"] = [f.name for f in ckpts]
    else:
        report["checks"]["checkpoint_count"] = 0

    return report


def start_comfyui(port=8188, listen="127.0.0.1", cpu_only=False, extra_args=None):
    """启动 ComfyUI 服务"""
    if not (COMFYUI_DIR / "main.py").is_file():
        print(f"[ERROR] ComfyUI main.py not found at {COMFYUI_DIR / 'main.py'}")
        return None

    cmd = [
        sys.executable, str(COMFYUI_DIR / "main.py"),
        "--listen", listen,
        "--port", str(port),
        "--output-dir", str(OUTPUT_DIR),
    ]
    if cpu_only:
        cmd.append("--cpu")
    if extra_args:
        cmd.extend(extra_args)

    print(f"[ComfyUI] Starting: {' '.join(cmd)}")
    print(f"[ComfyUI] Working dir: {COMFYUI_DIR}")

    proc = subprocess.Popen(
        cmd,
        cwd=str(COMFYUI_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc


def wait_for_ready(port=8188, timeout=120):
    """等待 ComfyUI 服务就绪"""
    import urllib.request
    url = f"http://127.0.0.1:{port}/system_stats"
    start = time.time()
    while time.time() - start < timeout:
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    return json.loads(resp.read().decode("utf-8"))
        except Exception:
            pass
        time.sleep(3)
    return None


def main():
    parser = argparse.ArgumentParser(description="ComfyUI Launcher")
    parser.add_argument("--check", action="store_true", help="Only check environment")
    parser.add_argument("--port", type=int, default=8189)
    parser.add_argument("--cpu", action="store_true", help="Force CPU mode")
    args = parser.parse_args()

    print("=" * 60)
    print("ComfyUI Startup Script")
    print("=" * 60)

    # Environment check
    env = check_environment()
    print("\n[Environment]")
    for k, v in env["checks"].items():
        print(f"  {k}: {v}")
    print(f"\n  Overall: {'OK' if env['ok'] else 'ISSUES FOUND'}")

    if args.check:
        print("\n[Check mode] Exiting.")
        return

    if not env["ok"]:
        print("\n[ERROR] Environment not ready. Fix issues above.")
        return

    # Start ComfyUI
    proc = start_comfyui(port=args.port, cpu_only=args.cpu)
    if not proc:
        return

    print(f"\n[ComfyUI] Waiting for service ready on port {args.port}...")
    stats = wait_for_ready(port=args.port, timeout=120)

    if stats:
        print(f"\n[ComfyUI] SERVICE READY!")
        print(json.dumps(stats, indent=2))

        # Test MCP Client
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from integrations.comfyui_mcp_server import ComfyUIClient
        client = ComfyUIClient(f"http://127.0.0.1:{args.port}")
        print(f"\n[MCP Client] is_available: {client.is_available()}")
        models = client.list_models()
        print(f"[MCP Client] models: {models}")
        gpu = client.get_gpu_info()
        print(f"[MCP Client] gpu: {json.dumps(gpu, indent=2)}")

        if not models:
            print("\n[WARNING] No checkpoint models found.")
            print("  To generate images, download a model to:")
            print(f"  {COMFYUI_DIR / 'models' / 'checkpoints'}")
            print("  Example: https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0")
    else:
        print(f"\n[ERROR] ComfyUI did not start within timeout.")
        # Print recent output
        if proc.stdout:
            proc.terminate()

    print("\n[ComfyUI] Service running. Press Ctrl+C to stop.")
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        print("\n[ComfyUI] Stopped.")


if __name__ == "__main__":
    main()
