# ============================================================
# 环境验证脚本 - 检查所有引擎可用性
# ============================================================

"""Environment verification script."""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Set sandbox-safe env vars BEFORE any imports
os.environ.setdefault(
    "YOLO_CONFIG_DIR",
    r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault\puppet-automation\data\cache\ultralytics",
)


def check_section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def check_import(modules: list[str]) -> dict[str, bool]:
    results = {}
    for mod in modules:
        try:
            __import__(mod)
            results[mod] = True
            print(f"  [OK] {mod}")
        except ImportError as e:
            results[mod] = False
            print(f"  [FAIL] {mod}: {e}")
    return results


def check_path(name: str, path: str) -> bool:
    exists = Path(path).exists()
    status = "[OK]" if exists else "[MISSING]"
    print(f"  {status} {name}: {path}")
    return exists


def main() -> int:
    failed = 0

    check_section("Python Environment")
    print(f"  Python: {sys.version.split()[0]}")
    print(f"  Executable: {sys.executable}")

    check_section("Web Framework")
    r1 = check_import(["fastapi", "uvicorn", "pydantic", "celery", "redis", "sqlalchemy"])
    failed += sum(1 for v in r1.values() if not v)

    check_section("CV & Video")
    r2 = check_import(["cv2", "PIL", "imageio", "imageio_ffmpeg", "av", "moviepy", "librosa"])
    failed += sum(1 for v in r2.values() if not v)

    check_section("AI/ML Core")
    r3 = check_import(["numpy", "scipy", "pandas", "sklearn", "torch", "torchvision"])
    failed += sum(1 for v in r3.values() if not v)

    check_section("Detection & Segmentation")
    r4 = check_import(["mediapipe", "ultralytics", "onnxruntime"])
    failed += sum(1 for v in r4.values() if not v)

    check_section("LLM Orchestration")
    r5 = check_import(["langchain", "openai"])
    failed += sum(1 for v in r5.values() if not v)

    check_section("GPU / CUDA")
    try:
        import torch
        print(f"  CUDA available: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"  GPU: {torch.cuda.get_device_name(0)}")
            print(f"  CUDA version: {torch.version.cuda}")
            print(f"  cuDNN version: {torch.backends.cudnn.version()}")
        else:
            print("  [WARN] CUDA not available")
            failed += 1
    except Exception as e:
        print(f"  [FAIL] {e}")
        failed += 1

    check_section("FFmpeg")
    try:
        import imageio_ffmpeg
        ff = imageio_ffmpeg.get_ffmpeg_exe()
        print(f"  imageio-ffmpeg: {ff}")
        print(f"  exists: {Path(ff).exists()}")
    except ImportError:
        print("  [FAIL] imageio_ffmpeg not installed")
        failed += 1

    check_section("Engine Executables")
    engines = {
        "AE 2025": "C:/Program Files/Adobe/Adobe After Effects 2025",
        "aerender": "C:/Program Files/Adobe/Adobe After Effects 2025/Support Files/aerender.exe",
        "Photoshop 2025": "C:/Program Files/Adobe/Adobe Photoshop 2025",
        "Silhouette 2026": "C:/Program Files/BorisFX/Silhouette 2026.0",
        "DaVinci Resolve": "C:/Program Files/Blackmagic Design/DaVinci Resolve",
        "Topaz Video AI": "D:/top/Topaz Video AI Pro/Topaz Video AI BETA.exe",
        "Blender (pending)": "C:/Program Files/Blender Foundation/Blender/blender.exe",
        "FFmpeg (full, pending)": "C:/tools/ffmpeg/bin/ffmpeg.exe",
    }
    for name, path in engines.items():
        if not check_path(name, path):
            if "(pending)" not in name:
                failed += 1

    check_section("Node.js / nexrender")
    import subprocess
    try:
        r = subprocess.run(["node", "--version"], capture_output=True, text=True)
        print(f"  Node: {r.stdout.strip()}")
    except Exception:
        print("  [FAIL] node not in PATH")
        failed += 1
    try:
        r = subprocess.run(
            ["npm", "list", "-g", "@nexrender/core"],
            capture_output=True, text=True,
        )
        if "@nexrender/core" in r.stdout:
            print("  [OK] @nexrender/core installed globally")
        else:
            print("  [FAIL] @nexrender/core not found")
            failed += 1
    except Exception:
        print("  [FAIL] npm check failed")
        failed += 1

    check_section("Summary")
    if failed == 0:
        print("  [SUCCESS] All checks passed!")
        return 0
    else:
        print(f"  [WARN] {failed} check(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
