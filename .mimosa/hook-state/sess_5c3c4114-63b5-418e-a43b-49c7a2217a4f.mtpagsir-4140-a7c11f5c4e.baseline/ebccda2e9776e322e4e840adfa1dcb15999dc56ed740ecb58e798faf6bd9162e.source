"""build_fx_asset_index.py — 特效贴图资产索引（14 类 → 语义池）

扫描 resources/effects 的 14 大类透明 PNG (刀光/魔法阵/序列帧...),
内容 md5 去重(双份拷贝消除), 生成 data/fx_assets/index.json:
  {category: [file...]}

类目语义映射 (目录名 → 英文语义键):
  刀光类→slash  魔法阵类→magic_circle  序列帧贴图→frame_seq
  扩散旋转类→burst  扭曲烟雾类→smoke  光点类→sparkle  溅射光点类→splash
  图案类→pattern  线性条状类→streak  UV动画类→uv_anim  物体类→object
  物件特效贴图→prop_fx  无缝贴图类→tile  文字类→glyph

用法:
  python scripts/build_fx_asset_index.py [--per-cat 30]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
FX_ROOT = PROJECT / "resources" / "effects"
OUT = PROJECT / "data" / "fx_assets" / "index.json"

CAT_MAP = {
    "刀光类": "slash",
    "魔法阵类": "magic_circle",
    "序列帧贴图": "frame_seq",
    "扩散旋转类": "burst",
    "扭曲烟雾类": "smoke",
    "光点类": "sparkle",
    "溅射光点类": "splash",
    "图案类": "pattern",
    "线性条状类": "streak",
    "UV动画类": "uv_anim",
    "物体类": "object",
    "物件特效贴图": "prop_fx",
    "无缝贴图类": "tile",
    "文字类": "glyph",
}
IMG_EXT = {".png", ".tga", ".png"}


def md5_of(p: Path) -> str:
    h = hashlib.md5()
    with open(p, "rb") as f:
        while True:
            b = f.read(1 << 20)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-cat", type=int, default=30)
    args = ap.parse_args()

    if not FX_ROOT.exists():
        print(f"贴图目录不存在: {FX_ROOT}")
        return 1

    pools: dict = {}
    seen = set()
    for d in FX_ROOT.iterdir():
        if not d.is_dir() or d.name in ("特效贴图PNG",):
            continue  # 跳过双份拷贝目录
        key = CAT_MAP.get(d.name)
        if not key:
            continue
        files = sorted([f for f in d.rglob("*")
                        if f.is_file() and f.suffix.lower() in IMG_EXT
                        and not f.name.startswith("._")])
        kept = 0
        for f in files:
            h = md5_of(f)
            if h in seen:
                continue
            seen.add(h)
            pools.setdefault(key, []).append(str(f))
            kept += 1
        print(f"  {d.name} → {key}: {len(files)} 文件, 去重保留 {kept}")

    for k in pools:
        pools[k] = sorted(pools[k])[: args.per_cat]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(pools, ensure_ascii=False, indent=1), encoding="utf-8")
    total = sum(len(v) for v in pools.values())
    print(f"\n池: {len(pools)} 类共 {total} 张 → {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
