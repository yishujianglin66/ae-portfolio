#!/usr/bin/env python3
"""dev_scripts/extract_downloads.py — 解压并验证 SCAIL-2 / AnimatedDrawings 源码 ZIP

背景: GitHub git-clone 线路长期断连, 改走 codeload.github.com ZIP 直下。
本脚本负责: 校验完整性 → 解压到适配器期望路径 → 环境检查验证。

目标路径 (与适配器常量一致):
  - temp/scail2.zip            → external/scail2/           (保留已有 weights/)
  - temp/animated_drawings.zip → external/AnimatedDrawings/ (剥离顶层目录)
"""
import os
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMP = ROOT / "temp"
EXTERNAL = ROOT / "external"


def check_zip(path: Path) -> bool:
    if not path.exists() or path.stat().st_size < 1024:
        print(f"[{path.name}] ❌ 不存在或过小")
        return False
    try:
        with zipfile.ZipFile(path) as zf:
            bad = zf.testzip()
            if bad:
                print(f"[{path.name}] ❌ 损坏于: {bad}")
                return False
            print(f"[{path.name}] ✅ 完整 ({len(zf.namelist())} 条目, "
                  f"{path.stat().st_size / 1048576:.1f} MB)")
            return True
    except zipfile.BadZipFile:
        print(f"[{path.name}] ❌ 非法 ZIP (可能仍在下载)")
        return False


def extract_scail2() -> bool:
    """解压 SCAIL-2 源码到 external/scail2 (与已有 weights/ 共存)"""
    src = TEMP / "scail2.zip"
    dst = EXTERNAL / "scail2"
    if not check_zip(src):
        return False
    stage = TEMP / "scail2_src_stage"
    if stage.exists():
        shutil.rmtree(stage)
    with zipfile.ZipFile(src) as zf:
        zf.extractall(stage)
    # codeload ZIP 顶层为 SCAIL-2-<branch>/
    tops = list(stage.iterdir())
    top = tops[0] if len(tops) == 1 and tops[0].is_dir() else stage
    moved = 0
    for item in top.iterdir():
        target = dst / item.name
        if item.name == "weights":  # 保护已下载的 15.5GB 权重
            continue
        if target.exists():
            shutil.rmtree(target) if target.is_dir() else target.unlink()
        shutil.move(str(item), str(target))
        moved += 1
    shutil.rmtree(stage, ignore_errors=True)
    print(f"[scail2] ✅ 解压完成 → {dst} ({moved} 项)")
    return True


def extract_animated_drawings() -> bool:
    """解压 AnimatedDrawings 到 external/AnimatedDrawings"""
    src = TEMP / "animated_drawings.zip"
    dst = EXTERNAL / "AnimatedDrawings"
    if not check_zip(src):
        return False
    stage = TEMP / "animated_src_stage"
    if stage.exists():
        shutil.rmtree(stage)
    with zipfile.ZipFile(src) as zf:
        zf.extractall(stage)
    tops = list(stage.iterdir())
    top = tops[0] if len(tops) == 1 and tops[0].is_dir() else stage
    if dst.exists():
        shutil.rmtree(dst)
    shutil.move(str(top), str(dst))
    shutil.rmtree(stage, ignore_errors=True)
    print(f"[AnimatedDrawings] ✅ 解压完成 → {dst}")
    return True


def verify_adapters():
    """适配器环境检查验证"""
    sys.path.insert(0, str(ROOT))
    ok = True
    try:
        from integrations.scail2_adapter import SCAIL2Adapter
        r = SCAIL2Adapter().execute("check_environment", {})
        print(f"[验证] SCAIL-2: source={r.get('source_available')}, "
              f"weights={r.get('weights_available')}")
    except Exception as e:
        print(f"[验证] SCAIL-2 ❌ {e}")
        ok = False
    try:
        from integrations.animated_drawings_adapter import AnimatedDrawingsAdapter
        r = AnimatedDrawingsAdapter().execute("check_environment", {})
        print(f"[验证] AnimatedDrawings: {r}")
    except Exception as e:
        print(f"[验证] AnimatedDrawings ❌ {e}")
        ok = False
    return ok


if __name__ == "__main__":
    results = {
        "scail2": extract_scail2(),
        "animated_drawings": extract_animated_drawings(),
    }
    print("=" * 50)
    if all(results.values()):
        verify_adapters()
    print("解压结果:", results)
