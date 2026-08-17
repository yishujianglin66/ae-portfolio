#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修复puppet_style预设中的双重数组问题"""
from __future__ import annotations

import json
import re
from pathlib import Path


def main():
    json_file = "ae/presets/puppet_style.json"
    data = json.loads(Path(json_file).read_text(encoding="utf-8"))
    fixed = 0

    for p in data:
        old = p["script_template"]
        new = re.sub(r"\[\$\{(\w+)\}\]", r"${\1}", old)
        if new != old:
            p["script_template"] = new
            fixed += 1
            print(f"  修复 {p['name']}")

    Path(json_file).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"修复完成: {fixed} 个预设")


if __name__ == "__main__":
    main()
