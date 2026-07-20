#!/usr/bin/env python3
"""
完整递归扫描 MediaCore
"""
from pathlib import Path

media_core = Path("C:/Program Files/Adobe/Common/Plug-ins/7.0/MediaCore")
print(f"MediaCore 路径: {media_core}")
print(f"是否存在: {media_core.exists()}")
print()

if media_core.exists():
    # 列出顶层目录
    print("=== 顶层目录结构 ===")
    for item in sorted(media_core.iterdir()):
        if item.is_dir():
            count = len(list(item.rglob("*.aex"))) + len(list(item.rglob("*.prm"))) + len(list(item.rglob("*.plugin")))
            print(f"  📁 {item.name}/  ({count} 个插件)")
        else:
            print(f"  📄 {item.name}")
    print()

    # 所有 .aex 文件（递归）
    all_aex = sorted(media_core.rglob("*.aex"))
    all_prm = sorted(media_core.rglob("*.prm"))
    print(f"=== 递归统计 ===")
    print(f"  .aex 文件: {len(all_aex)} 个")
    print(f"  .prm 文件: {len(all_prm)} 个")
    print()

    # 按顶层目录分类
    print("=== 按插件包分类（.aex） ===")
    from collections import defaultdict
    by_top = defaultdict(list)
    for f in all_aex:
        # 找到 MediaCore 下的第一级子目录
        rel_parts = f.relative_to(media_core).parts
        if len(rel_parts) > 1:
            top = rel_parts[0]
        else:
            top = "(根目录)"
        by_top[top].append(f)

    for top in sorted(by_top.keys(), key=lambda k: -len(by_top[k])):
        files = by_top[top]
        total_size = sum(f.stat().st_size for f in files) / 1024 / 1024
        print(f"  {top}: {len(files)} 个, {total_size:.1f} MB")
        # 如果是 Red Giant / Trapcode 相关，列出全部
        if any(kw in top.lower() for kw in ["trapcode", "red giant", "redgiant", "maxon", "magic bullet", "universe"]):
            for f in files:
                print(f"    - {f.name} ({f.stat().st_size / 1024:.1f} KB)")
    print()

    # 特别找 Trapcode
    print("=== 包含 Trapcode 关键词的所有文件 ===")
    tg_files = [f for f in all_aex if any(kw in f.name.lower() for kw in 
        ["trapcode", "particular", "form", "shine", "starglow", "lux", "mir", 
         "tao", "echospace", "sound", "grow bounds", "horizon", "geo",
         "3d stroke", "starglow"])]
    for f in tg_files:
        rel = f.relative_to(media_core)
        print(f"  {rel}")
    print(f"共 {len(tg_files)} 个")
