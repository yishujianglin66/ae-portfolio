"""build_sfx_index.py — SFX 音效池索引（语义分类 + 去重）

扫描项目内 resources/audio + 外部 D:\\AE-Work\\resources\\audio 的语义目录,
按内容 md5 去重, 生成 data/sfx/index.json: {pool_name: [file...]}。

池映射 (语义目录名 → 池):
  impact ← 击打-Hits / TVC(Trailer Hit/Code Black 模式匹配)
  whoosh ← whoosh/ / 转场音效-whooosh / 转场音效
  riser  ← 上升 Risers
  glitch ← 信号干扰故障音效

用法:
  python scripts/build_sfx_index.py [--per-pool 40]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
AUDIO_DIRS = [
    PROJECT / "resources" / "audio",
    Path(r"D:\AE-Work\resources\audio"),
]
OUT = PROJECT / "data" / "sfx" / "index.json"
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aiff"}

# 文件名模式 → 池 (TVC 混合库内的语义识别)
NAME_PATTERNS = [
    (re.compile(r"hit|trailer|impact|boom|击打|重音", re.I), "impact"),
    (re.compile(r"whoosh|swish|转场|环绕|swoosh", re.I), "whoosh"),
    (re.compile(r"riser|rise|上升", re.I), "riser"),
    (re.compile(r"glitch|signal|code black|干扰|故障|digital", re.I), "glitch"),
]


def pool_of(path: Path) -> str:
    """目录名/文件名 → 语义池。"""
    parts = [p.lower() for p in path.parts]
    joined = "/".join(parts)
    if "riser" in joined or "上升" in joined:
        return "riser"
    if "glitch" in joined or "故障" in joined or "干扰" in joined:
        return "glitch"
    if "击打" in joined or "hit" in joined:
        return "impact"
    if "whoosh" in joined or "转场" in joined:
        return "whoosh"
    # TVC 混合库: 按文件名模式
    name = path.name
    for pat, pool in NAME_PATTERNS:
        if pat.search(name):
            return pool
    return ""


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
    ap.add_argument("--per-pool", type=int, default=40)
    args = ap.parse_args()

    pools: dict = {}
    seen = set()
    n_scan = 0
    for root in AUDIO_DIRS:
        if not root.exists():
            continue
        for f in root.rglob("*"):
            if not f.is_file() or f.suffix.lower() not in AUDIO_EXT:
                continue
            if f.name.startswith("._"):
                continue
            n_scan += 1
            pool = pool_of(f)
            if not pool:
                continue
            h = md5_of(f)
            if h in seen:
                continue
            seen.add(h)
            pools.setdefault(pool, []).append(str(f))

    # 每池截断 (确定性排序)
    for k in pools:
        pools[k] = sorted(pools[k])[: args.per_pool]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(pools, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"扫描 {n_scan} 音频 → 池: " + ", ".join(f"{k}={len(v)}" for k, v in sorted(pools.items())))
    print(f"索引: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
