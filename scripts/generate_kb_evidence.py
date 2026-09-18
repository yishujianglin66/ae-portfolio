import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from knowledge_base.kb_scanner import KBScanner

OUTPUT_DIR = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\output\evidence")
OUTPUT_FILE = OUTPUT_DIR / "kb_effect_inventory_20260818.json"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

scanner = KBScanner()

effects = scanner.scan_knowledge_base()

if len(effects) < 1400:
    scanner.scan_plugins(generate_missing=True)
    effects = scanner.scan_knowledge_base()

kb_directory_breakdown = {}
total_md_files = 0

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_KB_DIRS = [
    _PROJECT_ROOT / "10-风格化剪辑知识库",
    _PROJECT_ROOT / "11-大师知识库",
    _PROJECT_ROOT / "12-漫剪拉镜大师",
    _PROJECT_ROOT / "14-Silhouette知识库",
    _PROJECT_ROOT / "15-3D模型与骨骼动画知识库",
    _PROJECT_ROOT / "13-素材获取与搜索",
]

for kb_dir in _DEFAULT_KB_DIRS:
    if kb_dir.exists():
        md_count = len(list(kb_dir.rglob("*.md")))
        kb_directory_breakdown[kb_dir.name] = md_count
        total_md_files += md_count

target_categories = [
    "color", "blur", "distort", "generate", "keying",
    "stylize", "transition", "particle", "light", "audio", "other"
]

per_category_counts = {cat: 0 for cat in target_categories}

effect_items = []
for name_lower, effect_info in effects.items():
    cat = effect_info.category
    if cat not in target_categories:
        cat = "other"
    per_category_counts[cat] += 1
    entry = {
        "name": effect_info.name,
        "category": cat,
        "source_file": getattr(effect_info, "source", "") or "",
        "confidence": getattr(effect_info, "confidence", 0.8) or 0.8,
    }
    effect_items.append(entry)

sorted_effect_items = sorted(effect_items, key=lambda x: x["name"].lower())
total_effects = len(sorted_effect_items)

effects_sample = sorted_effect_items[:100]

effects_keys_sorted = sorted([e["name"] for e in sorted_effect_items])

output = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "kb_directory_breakdown": kb_directory_breakdown,
    "stats": {
        "total_md_files": total_md_files,
        "total_effects": total_effects,
        "per_category_counts": per_category_counts,
    },
    "effects_sample": effects_sample,
    "effects_full_count": total_effects,
    "effects_keys_sorted": effects_keys_sorted,
}

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

file_size_kb = os.path.getsize(OUTPUT_FILE) / 1024

print(f"EVIDENCE SAVED: output/evidence/kb_effect_inventory_20260818.json  ({total_effects} effects catalogued)")
print(f"File size: {file_size_kb:.1f} KB")
print("First 5 effects:")
for i, e in enumerate(effects_sample[:5]):
    print(f"  {i+1}. {e['name']} [{e['category']}]")
