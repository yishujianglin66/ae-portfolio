"""build_lut_index.py — LUT 资源索引（去重 + 按风格主题）

扫描 resources/luts/调色-COLOR_LUTs/ 下 43 个风格主题目录的 .cube 文件:
  - 过滤 macOS 假文件 (._*) 与非 cube
  - 按内容 md5 去重 (同哈希只留第一个, 双份拷贝/同内容不同名消除)
  - 每主题保留采样上限 (默认 12 个, 供调参器 GRID 抽样; 全量清单另存)

输出:
  data/luts/index.json     [{theme, file, size_mb, md5}]  全量去重清单
  data/luts/sampling.json  {theme: [file...]}             每主题采样池 (GRID 用)

用法:
  python scripts/build_lut_index.py [--per-theme 12]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
LUT_ROOT = PROJECT / "resources" / "luts" / "调色-COLOR_LUTs"
OUT_DIR = PROJECT / "data" / "luts"


def md5_of(p: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.md5()
    with open(p, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-theme", type=int, default=12, help="每主题采样池上限")
    args = ap.parse_args()

    if not LUT_ROOT.exists():
        print(f"LUT 目录不存在: {LUT_ROOT}")
        return 1

    entries = []
    seen_hash = set()
    themes = sorted(d for d in LUT_ROOT.iterdir() if d.is_dir())
    print(f"主题目录 {len(themes)} 个")

    for theme_dir in themes:
        theme = theme_dir.name
        cubes = sorted(theme_dir.glob("*.cube"))
        n_kept = 0
        for c in cubes:
            if c.name.startswith("._"):  # macOS 元数据假文件
                continue
            h = md5_of(c)
            if h in seen_hash:  # 内容级去重 (同哈希不同名/双份拷贝)
                continue
            seen_hash.add(h)
            entries.append({
                "theme": theme,
                "file": str(c),
                "size_mb": round(c.stat().st_size / 1048576, 2),
                "md5": h,
            })
            n_kept += 1
        if cubes:
            print(f"  {theme}: {len(cubes)} → 保留 {n_kept}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "index.json").write_text(
        json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8")

    # 每主题采样池 (确定性: 按文件名排序取前 N, 大小均衡优先小文件)
    pool: dict = {}
    for e in entries:
        pool.setdefault(e["theme"], []).append(e["file"])
    sampling = {}
    for theme, files in pool.items():
        # 优先选小文件 (112KB 标准容量 cube 是主力, 超大 6MB 多为高精度重复风格)
        files_sorted = sorted(files, key=lambda f: Path(f).stat().st_size)
        sampling[theme] = files_sorted[:args.per_theme]
    (OUT_DIR / "sampling.json").write_text(
        json.dumps(sampling, ensure_ascii=False, indent=1), encoding="utf-8")

    total = sum(len(v) for v in sampling.values())
    print(f"\n全量去重: {len(entries)} 个 cube | 采样池: {len(sampling)} 主题 × ≤{args.per_theme} = {total}")
    print(f"索引: {OUT_DIR / 'index.json'}")
    print(f"采样: {OUT_DIR / 'sampling.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
