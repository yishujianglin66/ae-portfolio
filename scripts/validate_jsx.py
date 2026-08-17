#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""JSX脚本批量验证工具 - 扫描358个JSX文件的ExtendScript兼容性问题"""
from __future__ import annotations

import re
import sys
from pathlib import Path


def validate_all_jsx(jsx_dir: Path) -> dict:
    issues = {
        "python_bool_True": [],
        "python_bool_False": [],
        "no_IIFE_wrap": [],
        "no_error_handling": [],
        "no_JSON_return": [],
        "empty_content": [],
        "no_active_comp_check": [],
        "placeholder_not_replaced": [],
        "python_None": [],
    }

    for jsx_file in jsx_dir.rglob("*.jsx"):
        content = jsx_file.read_text(encoding="utf-8")
        rel = str(jsx_file.relative_to(jsx_dir))

        if len(content) < 100:
            issues["empty_content"].append(rel)
            continue

        if re.search(r"\bTrue\b", content):
            issues["python_bool_True"].append(rel)
        if re.search(r"\bFalse\b", content):
            issues["python_bool_False"].append(rel)
        if re.search(r"\bNone\b", content):
            issues["python_None"].append(rel)
        if not re.search(r"\(function\s*\(\)", content):
            issues["no_IIFE_wrap"].append(rel)
        if "try" not in content:
            issues["no_error_handling"].append(rel)
        if "JSON.stringify" not in content:
            issues["no_JSON_return"].append(rel)
        if "activeItem" not in content and "app.project" not in content:
            issues["no_active_comp_check"].append(rel)
        if re.search(r"\$\{[a-zA-Z_]\w*\}", content):
            issues["placeholder_not_replaced"].append(rel)

    return issues


def main():
    jsx_dir = Path("output/jsx")
    if not jsx_dir.exists():
        print("ERROR: output/jsx directory not found")
        sys.exit(1)

    total = len(list(jsx_dir.rglob("*.jsx")))
    issues = validate_all_jsx(jsx_dir)

    print("=== JSX 脚本批量验证报告 ===")
    print(f"扫描文件总数: {total}")
    print()

    has_issues = False
    for key, files in issues.items():
        if files:
            has_issues = True
            print(f"[{key}] ({len(files)} 个文件)")
            for f in files[:8]:
                print(f"  - {f}")
            if len(files) > 8:
                print(f"  ... 还有 {len(files) - 8} 个")
            print()

    if not has_issues:
        print("所有脚本通过验证，无ExtendScript兼容性问题！")

    # 返回退出码
    critical = len(issues["python_bool_True"]) + len(issues["python_bool_False"]) + len(issues["python_None"]) + len(issues["placeholder_not_replaced"])
    sys.exit(0 if critical == 0 else 1)


if __name__ == "__main__":
    main()
