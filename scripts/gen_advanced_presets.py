#!/usr/bin/env python3
"""高级特效预设生成器 - 6方向18预设增量注入
用法: py -3.12 scripts/gen_advanced_presets.py [direction]
  direction: 1-6 或 all
"""
import json, sys, os
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "text_animation_presets.json"
PRESET_DIR = ROOT / "config" / "advanced_presets"
PRESET_DIR.mkdir(parents=True, exist_ok=True)

def load_config():
    return json.loads(CONFIG.read_text(encoding="utf-8"))

def save_config(cfg):
    CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

def inject_category(cfg, cat_key, display_name, presets):
    """注入一个分类到config"""
    if cat_key not in cfg["categories"]:
        cfg["categories"][cat_key] = {
            "display_name": display_name,
            "count": 0,
            "presets": []
        }
    cat = cfg["categories"][cat_key]
    existing_ids = {p["id"] for p in cat["presets"]}
    added = 0
    for p in presets:
        if p["id"] not in existing_ids:
            cat["presets"].append(p)
            added += 1
    cat["count"] = len(cat["presets"])
    return added

def make_preset(pid, name, name_en, desc, tags, difficulty, duration, params, jsx, typography=None, easing=None, variants=None):
    """标准化预设结构"""
    p = {
        "id": pid,
        "name": name,
        "name_en": name_en,
        "description": desc,
        "tags": tags,
        "difficulty": difficulty,
        "duration_default": duration,
        "parameters": params,
        "applies": ["TextLayer"],
        "jsx_template": jsx,
    }
    if typography:
        p["typography"] = typography
    if easing:
        p["easing"] = easing
    if variants:
        p["variants"] = variants
    return p

def std_params(text_default="标题文字", extra=None):
    """标准参数集"""
    params = [
        {"name":"textLayerName","type":"string","default":text_default,"description":"目标文字图层名"},
        {"name":"duration","type":"number","default":2.0,"min":0.5,"max":5.0,"description":"总时长(秒)"},
        {"name":"fontFamily","type":"string","default":"AlibabaPuHuiTi-3-85-Heavy","description":"字体"},
        {"name":"fontSize","type":"number","default":160,"min":40,"max":400,"description":"字号"},
    ]
    if extra:
        params.extend(extra)
    return params

# === 方向定义文件加载 ===
def load_direction(n):
    """加载方向n的预设定义"""
    f = PRESET_DIR / f"direction_{n}.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    return None

def save_direction(n, data):
    """保存方向n的预设定义"""
    f = PRESET_DIR / f"direction_{n}.json"
    f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def main():
    direction = sys.argv[1] if len(sys.argv) > 1 else "all"
    cfg = load_config()
    total_added = 0

    directions = range(1, 7) if direction == "all" else [int(direction)]
    
    for n in directions:
        data = load_direction(n)
        if data is None:
            print(f"  Direction {n}: no definition file yet, skip")
            continue
        cat_key = data["category"]
        display = data["display_name"]
        presets = data["presets"]
        added = inject_category(cfg, cat_key, display, presets)
        total_added += added
        print(f"  Direction {n} ({display}): +{added} presets -> {cat_key}")

    if total_added > 0:
        # 更新版本号和描述
        total = sum(v.get("count", len(v.get("presets",[]))) for v in cfg["categories"].values())
        cfg["version"] = "4.0-advanced"
        cfg["description"] = f"Text Animation Preset Library - Advanced FX ({total} presets)"
        save_config(cfg)
        print(f"\n  TOTAL: +{total_added} presets injected. Config now has {total} presets.")
    else:
        print("\n  No new presets to inject.")

if __name__ == "__main__":
    main()
