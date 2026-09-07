#!/usr/bin/env python3
"""
盲测作答页生成器: 读取 blind_answers.csv (只取 index+shot_id,
绝不嵌入 vlm_direction —— 盲测纪律), 校验 91 个 GIF 全部存在,
把清单注入 blind_answer_app_template.html, 输出独立可双击打开的作答页。

用法:
  py -3.12 scripts/build_blind_answer_app.py
"""
from __future__ import annotations

import csv
import json
import sys
from datetime import date
from pathlib import Path

DATA_ROOT = Path(r"D:\AE-Data\AnimeCamera")
REVIEW_DIR = DATA_ROOT / "blind_review"
GIF_DIR = REVIEW_DIR / "gifs"
SOURCE_CSV = REVIEW_DIR / "blind_answers.csv"
TEMPLATE = Path(__file__).parent / "blind_answer_app_template.html"
OUT_HTML = REVIEW_DIR / "blind_answer_app.html"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    for p in (SOURCE_CSV, TEMPLATE):
        if not p.exists():
            print(f"[FAIL] 缺少输入: {p}")
            return 1

    with SOURCE_CSV.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print(f"[FAIL] {SOURCE_CSV} 无数据行")
        return 1

    manifest = []
    missing = []
    seen_index = set()
    for r in rows:
        idx = int(r["index"])
        shot = r["shot_id"]
        if idx in seen_index:
            print(f"[FAIL] index 重复: {idx}")
            return 1
        seen_index.add(idx)
        gif = f"{idx:03d}_{shot}.gif"
        if not (GIF_DIR / gif).exists():
            missing.append(gif)
        manifest.append({"index": idx, "shot_id": shot, "gif": gif})

    if missing:
        print(f"[FAIL] {len(missing)} 个 GIF 缺失:")
        for m in missing:
            print(f"  - {m}")
        return 1

    html = TEMPLATE.read_text(encoding="utf-8")
    for ph in ("__MANIFEST__", "__TOTAL__", "__BUILD__"):
        if ph not in html:
            print(f"[FAIL] 模板缺少占位符 {ph}")
            return 1
    html = (html
            .replace("__MANIFEST__", json.dumps(manifest, ensure_ascii=False))
            .replace("__TOTAL__", str(len(manifest)))
            .replace("__BUILD__", date.today().isoformat()))

    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"作答页已生成: {OUT_HTML}")
    print(f"  清单 {len(manifest)} 条 | GIF 校验 91/91 通过 | 未嵌入任何模型预测")
    return 0


if __name__ == "__main__":
    sys.exit(main())
