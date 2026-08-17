#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修复知识库预设模板中的双重数组问题"""
from __future__ import annotations

import json
import re
from pathlib import Path


def main():
    fixes = {
        "ae/presets/effect.json": ["cp_neon_pulse", "cp_hologram_scan", "cp_matrix_rain"],
        "ae/presets/text_animation.json": ["ci_metallic_text", "ci_light_rays_text", "ci_lens_flare_text"],
    }

    for json_file, preset_names in fixes.items():
        data = json.loads(Path(json_file).read_text(encoding="utf-8"))
        for p in data:
            if p["name"] in preset_names:
                old = p["script_template"]
                # 将 var x=[${param}]; 改为 var x=${param};
                new = re.sub(r"\[\$\{(\w+)\}\]", r"${\1}", old)
                if new != old:
                    p["script_template"] = new
                    print(f"  修复 {p['name']}: 去掉双重数组方括号")

        Path(json_file).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print("模板修复完成")


if __name__ == "__main__":
    main()
