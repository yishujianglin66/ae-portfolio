"""models/tagging/material_tag_fusion.py — 素材多源标签融合

把三个感知源的标注产物融合成统一素材画像 (按视频文件名键控):

  1. 内容标签 (deepghs/anime_classification, A6):
       models/output/anime_content_tags.json → {video: {dominant, votes}}
  2. 氛围标签 (ToriiGate-2B, W6):
       data/atmosphere_annotations/*.json → {video: {atmosphere, energy, ...}}
  3. 运镜标签 (VideoMAE 级联 / 光流规则, T3):
       可选, 调用方传入 {video: label}

输出 (data/material_tags/unified_tags.json):
  {video_name: {content, content_votes, atmosphere, energy, camera, sources}}

用法:
    from models.tagging.material_tag_fusion import fuse_material_tags
    fused = fuse_material_tags(video_names=..., camera_tags={...})
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_CONTENT_TAGS = _PROJECT_ROOT / "models" / "output" / "anime_content_tags.json"
_ATMO_DIR = _PROJECT_ROOT / "data" / "atmosphere_annotations"
_OUT_DIR = _PROJECT_ROOT / "data" / "material_tags"


def _video_name(path: str) -> str:
    return Path(path).name


def load_content_tags(path: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    """内容标签 (A6 产物, list 格式) → {文件名: {dominant, votes, mean_probs}}。"""
    p = Path(path) if path else _CONTENT_TAGS
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("content tags read failed: %s", e)
        return {}
    results = data.get("results") or []
    if isinstance(results, dict):
        results = [results]
    out: Dict[str, Dict[str, Any]] = {}
    for r in results:
        if not isinstance(r, dict) or "video" not in r:
            continue
        name = _video_name(str(r["video"]))
        out[name] = {
            "dominant": r.get("dominant"),
            "votes": r.get("votes", {}),
            "mean_probs": r.get("mean_probs", {}),
        }
    return out


def load_atmosphere_tags(anno_dir: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    """氛围标签 (W6 产物) → {文件名: {atmosphere, energy, ...}}。"""
    d = Path(anno_dir) if anno_dir else _ATMO_DIR
    if not d.is_dir():
        return {}
    merged: Dict[str, Dict[str, Any]] = {}
    for f in sorted(d.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for name, val in (data.get("results") or {}).items():
            if isinstance(val, dict):
                merged[name] = val
    return merged


def fuse_material_tags(
    video_names: Optional[Iterable[str]] = None,
    camera_tags: Optional[Dict[str, str]] = None,
    out_path: Optional[Path] = None,
    content_path: Optional[Path] = None,
    anno_dir: Optional[Path] = None,
) -> Dict[str, Dict[str, Any]]:
    """三源融合 → 统一素材画像。

    Args:
        video_names: 可选视频文件名集合 (None=取三源并集)
        camera_tags: 可选 {文件名: 运镜标签} (T3 产物, 调用方提供)
        out_path: 输出 JSON (默认 data/material_tags/unified_tags.json)
        content_path: 内容标签 JSON (默认 models/output/anime_content_tags.json)
        anno_dir: 氛围标注目录 (默认 data/atmosphere_annotations)

    Returns:
        {文件名: 融合画像}
    """
    content = load_content_tags(content_path)
    atmo = load_atmosphere_tags(anno_dir)
    camera = camera_tags or {}

    names = set(video_names) if video_names is not None else (
        set(content) | set(atmo) | set(camera))
    fused: Dict[str, Dict[str, Any]] = {}
    for name in sorted(names):
        c = content.get(name) or {}
        a = atmo.get(name) or {}
        entry: Dict[str, Any] = {
            "content": c.get("dominant"),
            "content_votes": c.get("votes", {}),
            "atmosphere": a.get("atmosphere"),
            "energy": a.get("energy"),
            "emotion": a.get("emotion"),
            "scene_type": a.get("scene_type"),
            "camera": camera.get(name),
            "sources": {
                "content": bool(c), "atmosphere": bool(a),
                "camera": name in camera,
            },
        }
        fused[name] = entry

    payload = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "n_materials": len(fused),
        "coverage": {
            "content": sum(1 for v in fused.values() if v["sources"]["content"]),
            "atmosphere": sum(1 for v in fused.values() if v["sources"]["atmosphere"]),
            "camera": sum(1 for v in fused.values() if v["sources"]["camera"]),
        },
        "tags": fused,
    }
    out = Path(out_path) if out_path else _OUT_DIR / "unified_tags.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    logger.info("fused %d materials -> %s", len(fused), out)
    return fused
