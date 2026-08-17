"""extend_font_pool.py — 资源字库扩池（分类抽样 → PS名解析 → 临时安装）

从 D:\\AE-Work\\resources\\fonts 的 10 个分类目录各抽候选, fontTools 读
PostScript 名, 复制到系统字体目录 + AddFontResourceW 会话级加载
（不写注册表, 重启失效 — 适合生产会话/验收演示）。

输出: data/fonts/pool_extension.json
  [{category, file, ps_name, family}]   — 供 AE 探测与风格链扩充

用法:
  python scripts/extend_font_pool.py [--per-cat 8] [--install]
  --install: 复制+AddFontResourceW 加载 (默认只索引)
"""
from __future__ import annotations

import argparse
import ctypes
import json
import random
import shutil
import sys
from pathlib import Path

from fontTools.ttLib import TTFont

PROJECT = Path(__file__).resolve().parent.parent
FONT_ROOT = Path(r"D:\AE-Work\resources\fonts")
OUT = PROJECT / "data" / "fonts" / "pool_extension.json"
WIN_FONTS = Path(r"C:\Windows\Fonts")
FONT_EXT = {".ttf", ".otf"}

# 分类 → 风格卡挂点 (资源分类目录名)
CAT_STYLE_HINT = {
    "01-中文字体": "通用中文",
    "02-英文字体": "英文展示",
    "03-书法字体": "hardcore/vintage 汉字大字",
    "04-卡通可爱字体": "ambient/emotional",
    "05-日文字体": "amv 日式",
    "06-艺术设计字体": "cyberpunk/edit",
    "07-毛笔书法字体": "hardcore_battle 撞拍大字",
    "08-方正字体": "通用中文",
    "09-造字工房字体": "edit 标题",
    "10-其他字体": "杂项",
}


def ps_name_of(f: Path) -> tuple:
    try:
        tf = TTFont(str(f), fontNumber=0, lazy=True)
        name = tf["name"]
        ps = name.getDebugName(6)   # PostScript
        fam = name.getDebugName(1)  # Family
        tf.close()
        return ps, fam
    except Exception:
        return None, None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-cat", type=int, default=8)
    ap.add_argument("--install", action="store_true")
    args = ap.parse_args()

    if not FONT_ROOT.exists():
        print(f"字库不存在: {FONT_ROOT}")
        return 1

    rng = random.Random(2026)
    entries = []
    for d in sorted(FONT_ROOT.iterdir()):
        if not d.is_dir() or d.name not in CAT_STYLE_HINT:
            continue
        fonts = [f for f in d.rglob("*") if f.is_file() and f.suffix.lower() in FONT_EXT]
        if not fonts:
            continue
        # 小文件优先 (大字体=全家桶冗余), 抽样
        fonts.sort(key=lambda f: f.stat().st_size)
        picks = fonts[: args.per_cat * 2]
        rng.shuffle(picks)
        picked = picks[: args.per_cat]
        n_ok = 0
        for f in picked:
            ps, fam = ps_name_of(f)
            if not ps:
                continue
            entries.append({
                "category": d.name,
                "style_hint": CAT_STYLE_HINT[d.name],
                "file": str(f),
                "ps_name": ps,
                "family": fam or "",
            })
            n_ok += 1
        print(f"  {d.name}: {len(fonts)} 字体 → 抽 {len(picked)}, PS名解析 {n_ok}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8")

    if args.install:
        gdi = ctypes.windll.gdi32
        n_inst = 0
        for e in entries:
            dst = WIN_FONTS / Path(e["file"]).name
            try:
                if not dst.exists():
                    shutil.copy(e["file"], dst)
                if gdi.AddFontResourceW(str(dst)):
                    n_inst += 1
            except OSError:
                continue
        # 广播字体变更 (不广播也常即时生效)
        HWND_BROADCAST = 0xFFFF
        WM_FONTCHANGE = 0x001D
        ctypes.windll.user32.SendMessageTimeoutW(HWND_BROADCAST, WM_FONTCHANGE, 0, 0, 2, 1000, None)
        print(f"已会话级安装 {n_inst}/{len(entries)} 字体 (重启后失效, 注册表未动)")

    print(f"扩池索引: {OUT} | {len(entries)} 个候选")
    return 0


if __name__ == "__main__":
    sys.exit(main())
