#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""导出现有预设目录，按分类整理"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ae.preset_system import PresetSystem, PRESET_CATEGORIES


def main():
    ps = PresetSystem()
    lines = []
    total = 0

    for cat in PRESET_CATEGORIES.keys():
        names = ps.list_presets(cat)
        total += len(names)
        cat_info = PRESET_CATEGORIES[cat]
        lines.append(f"=== {cat} | {cat_info['name']} ({len(names)}个) ===")
        for n in names:
            p = ps.get_preset(n)
            desc = p.description if p else ""
            lines.append(f"  {n} | {desc}")
        lines.append("")

    lines.append(f"总计: {total}个预设")
    output = "\n".join(lines)

    with open("output/existing_presets_by_category.txt", "w", encoding="utf-8") as f:
        f.write(output)

    print("已保存到 output/existing_presets_by_category.txt")


if __name__ == "__main__":
    main()
