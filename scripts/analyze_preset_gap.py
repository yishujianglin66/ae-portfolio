#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分析知识库预设与JSON预设的缺口"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path

from ae.preset_system import PresetSystem


def to_snake(name: str) -> str:
    name = re.sub(r"[（(].*?[）)]", "", name).strip()
    result = re.sub(r"[^\w\u4e00-\u9fff]+", "_", name).strip("_").lower()
    return result


def main():
    # 1. 现有JSON预设名称
    ps = PresetSystem()
    existing_names = set(ps.list_presets())
    print(f"现有JSON预设: {len(existing_names)}个")

    # 2. 从知识库提取真正的预设名称
    kb = Path("10-风格化剪辑知识库/风格化预设宝典.md").read_text(encoding="utf-8")
    all_titles = re.findall(r"^####\s+\d+\.\d+\.\d+\s+(.+)$", kb, re.MULTILINE)

    exclude_keywords = [
        "预设（", "效果预设", "文字预设", "形状预设", "颜色预设", "表达式预设", "动画预设",
        "脚本", "工作", "制作", "添加", "调整", "保存", "测试", "优化",
        "常用", "表达式控制", "减小", "提高", "增强", "提升", "打包", "分发",
        "文档", "一级分类", "二级分类", "命名", "版本", "团队", "协作", "准备工作",
        "Kinetic Typography", "Cyberpunk", "Cinematic", "Social Media", "Teal & Orange"
    ]

    kb_presets = []
    for title in all_titles:
        if any(kw in title for kw in exclude_keywords):
            continue
        if len(title) < 4:
            continue
        kb_presets.append(title)

    print(f"知识库真实预设: {len(kb_presets)}个")

    # 3. 对比
    kb_snake = {to_snake(p): p for p in kb_presets}
    missing = []
    matched_count = 0

    for snake, readable in kb_snake.items():
        if snake in existing_names:
            matched_count += 1
            continue

        # 模糊匹配
        matched = False
        for en in existing_names:
            if snake in en or en in snake:
                matched = True
                break
            # 中文匹配
            cn_chars = [c for c in readable if "\u4e00" <= c <= "\u9fff"]
            if cn_chars and all(c in en.replace("_", "") for c in cn_chars[:3]):
                matched = True
                break

        if matched:
            matched_count += 1
        else:
            missing.append(readable)

    print(f"已匹配: {matched_count}个")
    print(f"缺口: {len(missing)}个")
    print()
    print("=== 知识库有但JSON缺失的预设 ===")
    for m in missing:
        print(m)

    # 保存到文件
    out = Path("output/preset_gap_analysis.txt")
    out.write_text("\n".join(missing), encoding="utf-8")
    print(f"\n缺口清单已保存到: {out}")


if __name__ == "__main__":
    main()
