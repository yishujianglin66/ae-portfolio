# -*- coding: utf-8 -*-
"""
清理空壳目录脚本（2026-08-12 素材治理）
========================================
TRAE 沙箱限制了对 D:\\AE-Work 的写操作，本脚本需由用户手动运行：
    python scripts\\clean_empty_dirs.py

清理范围（均为 0 文件目录，安全无数据损失）：
1. D:\\AE-Work\\batch_auto_frame\\ 下所有 0 文件子目录（SAM2 失败任务残留，17 个）
2. D:\\AE-Work\\图片素材库、D:\\AE-Work\\音效素材库、D:\\AE-Work\\素材库\\enhanced

注意：media-config.json 仍引用 图片素材库/音效素材库 路径，
删除后调用 ensure_directories() 的流程会自动按需重建，无副作用。

batch_auto_frame 保留策略（不动）：
- 40 个透明 .mov 共 70.7GB —— 保留（抠像成果未交付）
- PNG 遮罩中间帧约 0.3GB —— 保留（SAM2 推理产物，重新生成需 GPU 时间，且 0.3GB 不占空间）
"""
from __future__ import annotations

import sys
from pathlib import Path

BATCH_DIR = Path(r"D:\AE-Work\batch_auto_frame")
FIXED_TARGETS = [
    Path(r"D:\AE-Work\图片素材库"),
    Path(r"D:\AE-Work\音效素材库"),
    Path(r"D:\AE-Work\素材库\enhanced"),
]


def count_files(d: Path) -> int:
    """统计目录内文件数（含子目录，忽略权限错误）。"""
    return len([f for f in d.rglob("*") if f.is_file()])


def main() -> int:
    deleted: list[Path] = []
    skipped: list[tuple[Path, int]] = []

    # 1. batch_auto_frame 下的空壳子目录
    if BATCH_DIR.exists():
        for sub in sorted(BATCH_DIR.iterdir()):
            if not sub.is_dir():
                continue
            n = count_files(sub)
            if n == 0:
                sub.rmdir()
                deleted.append(sub)
            else:
                skipped.append((sub, n))
    else:
        print(f"[跳过] 目录不存在: {BATCH_DIR}")

    # 2. 固定空库目录（安全断言：仅删 0 文件目录）
    for t in FIXED_TARGETS:
        if not t.exists():
            continue
        n = count_files(t)
        if n == 0:
            t.rmdir()
            deleted.append(t)
        else:
            skipped.append((t, n))

    # 报告
    print(f"已删除空壳目录 {len(deleted)} 个:")
    for d in deleted:
        print(f"  - {d}")
    if skipped:
        print(f"跳过非空目录 {len(skipped)} 个（含文件未删）:")
        for d, n in skipped:
            print(f"  - {d} ({n} 文件)")

    print("\n完成。batch_auto_frame 的 .mov 与 PNG 中间帧均未触碰。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
