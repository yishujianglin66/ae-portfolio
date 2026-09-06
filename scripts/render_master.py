# -*- coding: utf-8 -*-
"""render_master.py — 显式渲染 MASTER 合成 (2026-09-06)

与 build_master_polish.py 解耦：build 只负责建 comp 存 master.aep，
本脚本负责确定性渲染 aerender master.aep → polish/<tag>_master.mp4。
用于 polish_watchdog 重试、或 build 后 aerender 静默死亡时的补渲染。

渲染范式复刻 ai/ae_render_channel.py::polish_pass（2026-09-04 三坑修复验证）：
  aerender -project <aep> -comp MASTER -output <out_mp4>
  GBK 输出用 errors='replace' 防 reader 线程崩（中文版 AE）。

用法: python scripts/render_master.py <run_dir> <tag>
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.paths import aerender_exe  # noqa: E402


def main() -> int:
    if len(sys.argv) < 3:
        print("用法: python scripts/render_master.py <run_dir> <tag>")
        return 1
    _raw = str(sys.argv[1]).replace("\\", "/").removeprefix("output/")
    if not re.fullmatch(r"unified_run\d+", _raw):
        print(f"[ERR] 非法 run 目录名(白名单 unified_run\\d+): {_raw}")
        return 1
    if not re.fullmatch(r"run\d+", str(sys.argv[2])):
        print(f"[ERR] 非法 tag(白名单 run\\d+): {sys.argv[2]}")
        return 1
    tag = sys.argv[2]
    polish_dir = ROOT / "output" / _raw / "polish"
    aep = polish_dir / "master.aep"
    out_mp4 = polish_dir / f"{tag}_master.mp4"
    if not aep.exists():
        print(f"[ERR] 未找到 {aep} — 先运行 build_master_polish.py")
        return 1
    aerender = aerender_exe()
    if not aerender or not Path(aerender).exists():
        print("[ERR] aerender 不存在 (检查 core.paths.aerender_exe / AEK_AERENDER)")
        return 1
    print(f"[render] aerender {aep.name} (comp MASTER) → {out_mp4.name}")
    r = subprocess.run([aerender, "-project", str(aep), "-comp", "MASTER",
                        "-output", str(out_mp4)],
                       capture_output=True, timeout=1800,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print(f"[ERR] aerender exit={r.returncode}")
        print((r.stdout or "")[-2000:])
        return 1
    if not out_mp4.exists() or out_mp4.stat().st_size < 10000:
        print("[ERR] 渲染产物缺失或过小 — 检查 aerender 输出")
        return 1
    print(f"[OK] {out_mp4} ({out_mp4.stat().st_size // 1000} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())