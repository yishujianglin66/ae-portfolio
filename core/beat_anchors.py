"""beat_anchors.py — BGM stem 锚点缓存的唯一读取实现。

来源: scripts/separate_drums.py 产出 `cache/stems/<sha256(bgm)[:12]>/anchors.json`
(v23 编排引擎切点锚定原料, R-2026-0002 网格量化锚的真值事件表)。

消费方:
  - ai/production_director.py  切点锚定 (kick/snare → 网格量化锚)
  - scripts/cutpoint_selfeval.py  保节拍修复与节拍回归守卫 (2026-09-19)
  - scripts/beat_anchor_check.py  成品节拍锚点评测

此前 production_director 与 beat_anchor_check 各自内联实现键算法与字段解析;
本模块收敛为唯一实现, 避免"三处各写一份、改一处漏两处"。
缓存缺席时一律 fail-safe 返回空表 (调用方退回原启发式, 不抛异常)。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

STRONG_DEFAULT = 0.5          # 强锚阈值 (与 production_director 一致)
CACHE_ROOT_DEFAULT = "cache/stems"


def cache_key(bgm: str | Path) -> str:
    """BGM 文件 → 缓存键 (sha256 前 12 位)。文件不可读时返回空串。"""
    try:
        return hashlib.sha256(Path(bgm).read_bytes()).hexdigest()[:12]
    except OSError:
        return ""


def anchors_path(bgm: str | Path,
                 cache_root: str | Path = CACHE_ROOT_DEFAULT) -> Path | None:
    """BGM 文件 → anchors.json 路径 (不存在返回 None)。"""
    key = cache_key(bgm)
    if not key:
        return None
    p = Path(cache_root) / key / "anchors.json"
    return p if p.exists() else None


def load_file(path: str | Path) -> dict:
    """读 anchors.json → {'kick': [(t, s)], 'snare': [(t, s)], 'melody': [(t, s)]}。

    兼容扁平数组 [[t, s], ...] 与对象数组 [{'time': t, 'strength': s}, ...]。
    文件缺失/损坏 → 三个键均为空表。
    """
    out: dict[str, list[tuple[float, float]]] = {"kick": [], "snare": [], "melody": []}
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return out
    for kind in out:
        for item in raw.get(f"{kind}_onsets", []) or []:
            try:
                if isinstance(item, dict):
                    t, s = float(item["time"]), float(item.get("strength", 1.0))
                else:
                    t, s = float(item[0]), float(item[1])
            except (TypeError, ValueError, KeyError, IndexError):
                continue
            out[kind].append((t, s))
    return out


def load_for_bgm(bgm: str | Path,
                 cache_root: str | Path = CACHE_ROOT_DEFAULT) -> dict:
    """按 BGM 文件定位并读取锚点表 (缓存缺席 → 空表)。"""
    p = anchors_path(bgm, cache_root)
    return load_file(p) if p else {"kick": [], "snare": [], "melody": []}


def strong_times(anchors: dict, strong: float = STRONG_DEFAULT,
                 kinds: tuple[str, ...] = ("kick", "snare")) -> list[float]:
    """锚点表 → 强度 ≥ strong 的鼓点时间表 (升序, 去重到毫秒)。"""
    ts = {round(t, 3) for k in kinds for t, s in anchors.get(k, []) if s >= strong}
    return sorted(ts)


def hit_rate(times: list[float], anchors: list[float], tol: float = 0.080) -> float:
    """times 中落在 anchors ±tol 内的比例 (锚点表为空时返回 0.0)。"""
    if not times or not anchors:
        return 0.0
    import bisect
    a = sorted(anchors)
    hit = 0
    for t in times:
        i = bisect.bisect_left(a, t)
        best = 1e9
        for j in (i - 1, i):
            if 0 <= j < len(a):
                best = min(best, abs(a[j] - t))
        if best <= tol:
            hit += 1
    return hit / len(times)
