#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修复JSON预设中字符串形式的数组值，转换为真正的Python列表"""
from __future__ import annotations

import json
import re
from pathlib import Path


def looks_like_array_string(val) -> bool:
    """检查值是否看起来像JSON数组字符串"""
    return isinstance(val, str) and val.startswith("[") and val.endswith("]")


def parse_array_string(s: str):
    """将JSON数组字符串解析为Python列表"""
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return s


def fix_preset_file(json_path: Path) -> int:
    """修复单个JSON预设文件中的字符串数组"""
    data = json.loads(json_path.read_text(encoding="utf-8"))
    fixed = 0

    for preset in data:
        if "default_values" not in preset:
            continue
        for key, val in preset["default_values"].items():
            if looks_like_array_string(val):
                parsed = parse_array_string(val)
                if isinstance(parsed, list):
                    preset["default_values"][key] = parsed
                    fixed += 1
                    print(f"  修复 {preset['name']}.{key}: str->list")

    if fixed > 0:
        json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    return fixed


def main():
    presets_dir = Path("ae/presets")
    total_fixed = 0

    for json_file in presets_dir.glob("*.json"):
        if json_file.name == "combinations":
            continue
        fixed = fix_preset_file(json_file)
        if fixed > 0:
            total_fixed += fixed
            print(f"  -> {json_file.name}: 修复 {fixed} 个")

    print(f"\n总计修复: {total_fixed} 个字符串数组")


if __name__ == "__main__":
    main()
