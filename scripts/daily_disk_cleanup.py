# -*- coding: utf-8 -*-
r"""每日磁盘自动清理 — Windows 计划任务入口 (2026-08-15)

背景: C 盘曾爆满至 2GB 剩余 (渲染中间产物 + 包缓存只增不清)。
本脚本由计划任务 \AEKV-Daily-Disk-Cleanup 每天 03:00 调用,
做三层清理并写日志到 D:/AE-Work/渲染档案/.cleanup_log.txt。

清理内容:
  1. 渲染产物生命周期管理 (scripts/render_cleanup.py):
     文档留档 / 最后版本保活 / 高完成度成品保留 / 活跃跳过
  2. pip 缓存 (可随时重下, 零风险)
  3. uv 缓存 (可随时重下, 零风险)
  4. 用户 Temp 目录 (系统临时文件)

任何单步失败不影响其余步骤; 永不删除: 素材库/resources/.git/源码。
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

# 直接执行时 sys.path[0] 是 scripts/, 项目根需显式加入
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

LOG_FILE = Path("D:/AE-Work/渲染档案/.cleanup_log.txt")


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def _size_gb(path: Path) -> float:
    if not path.exists():
        return 0.0
    total = 0.0
    for f in path.rglob("*"):
        if f.is_file():
            try:
                total += f.stat().st_size
            except OSError:
                pass
    return total / 1e9


def step_render_cleanup() -> str:
    from core.render_cleanup import auto_cleanup_quiet
    r = auto_cleanup_quiet(min_interval_hours=0)  # 计划任务场景不节流
    if r.get("skipped"):
        return "无待清理项"
    return (f"释放 {r['freed_gb']:.2f}GB, "
            f"归档文档 {r['archived_docs']} 个, 保留成品 {r['kept_finals']} 个")


def step_pip_cache() -> str:
    try:
        r = subprocess.run([sys.executable, "-m", "pip", "cache", "purge"],
                           capture_output=True, text=True, timeout=300)
        tail = (r.stdout or "").strip().splitlines()[-1] if r.stdout else ""
        return f"pip: {tail}" if r.returncode == 0 else f"pip 失败: {tail[:80]}"
    except Exception as e:
        return f"pip 异常: {e}"


def step_uv_cache() -> str:
    cache = Path.home() / "AppData" / "Local" / "uv" / "cache"
    before = _size_gb(cache)
    if not cache.exists():
        return "uv 无缓存"
    try:
        import shutil
        shutil.rmtree(cache, ignore_errors=True)
        return f"uv: 释放 {before:.2f}GB"
    except Exception as e:
        return f"uv 异常: {e}"


def step_temp() -> str:
    tmp = Path.home() / "AppData" / "Local" / "Temp"
    before = _size_gb(tmp)
    if not tmp.exists():
        return "Temp 无"
    try:
        for child in tmp.iterdir():
            try:
                if child.is_dir():
                    import shutil
                    shutil.rmtree(child, ignore_errors=True)
                else:
                    child.unlink(missing_ok=True)
            except OSError:
                pass
        return f"Temp: 释放 {before:.2f}GB"
    except Exception as e:
        return f"Temp 异常: {e}"


def main() -> None:
    log("=" * 56)
    log("每日磁盘清理开始")
    try:
        import shutil
        c_free = shutil.disk_usage("C:/").free / 1e9
        log(f"清理前 C 盘剩余: {c_free:.2f}GB")
    except OSError:
        pass

    for name, fn in (
        ("渲染产物", step_render_cleanup),
        ("pip 缓存", step_pip_cache),
        ("uv 缓存", step_uv_cache),
        ("Temp 目录", step_temp),
    ):
        try:
            log(f"  [{name}] {fn()}")
        except Exception as e:
            log(f"  [{name}] 异常(继续下一项): {e}")

    try:
        import shutil
        c_free = shutil.disk_usage("C:/").free / 1e9
        log(f"清理后 C 盘剩余: {c_free:.2f}GB")
    except OSError:
        pass
    log("每日磁盘清理完成")


if __name__ == "__main__":
    main()
