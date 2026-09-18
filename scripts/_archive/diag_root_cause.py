#!/usr/bin/env python3
"""诊断: 检查jsx_template实际内容 + 对比batch_render_textfx成功模式"""
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "text_animation_presets.json"

cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
cats = cfg["categories"]

print("=" * 70)
print("  DIAGNOSIS: jsx_template content analysis")
print("=" * 70)

# 检查每个分类第一个预设的jsx_template
for cat_key, cat_data in cats.items():
    presets = cat_data.get("presets", [])
    if not presets:
        continue
    p = presets[0]
    tpl = p.get("jsx_template", "")
    print(f"\n[{cat_key}] preset={p['id']}")
    print(f"  jsx_template length: {len(tpl)}")
    if tpl:
        # 显示前300字符
        preview = tpl[:300].replace('\n', '\\n')
        print(f"  Preview: {preview}")
        # 检查是否包含关键动画元素
        has_keyframe = "setValueAtTime" in tpl or "setValuesAtTimes" in tpl
        has_expression = "expression" in tpl
        has_animator = "ADBE Text Animator" in tpl or "animators" in tpl.lower()
        has_wiggly = "Wiggly" in tpl or "wiggly" in tpl
        print(f"  Has keyframes: {has_keyframe}")
        print(f"  Has expressions: {has_expression}")
        print(f"  Has text animator: {has_animator}")
        print(f"  Has wiggly: {has_wiggly}")
    else:
        print("  [EMPTY TEMPLATE!]")

# 统计
print("\n" + "=" * 70)
print("  SUMMARY")
print("=" * 70)
total = 0
empty = 0
has_anim = 0
for cat_key, cat_data in cats.items():
    for p in cat_data.get("presets", []):
        total += 1
        tpl = p.get("jsx_template", "")
        if not tpl:
            empty += 1
        elif "setValueAtTime" in tpl or "expression" in tpl or "Animator" in tpl:
            has_anim += 1

print(f"  Total presets: {total}")
print(f"  Empty templates: {empty}")
print(f"  With animation code: {has_anim}")
print(f"  Without animation markers: {total - empty - has_anim}")

# 检查eval问题
print("\n" + "=" * 70)
print("  EVAL ESCAPING TEST (first preset)")
print("=" * 70)
first_cat = list(cats.keys())[0]
p = cats[first_cat]["presets"][0]
tpl = p.get("jsx_template", "")
if tpl:
    # 模拟render_all_presets_3s.py的处理
    jsx_escaped = tpl.replace("'", "\\'").replace("\n", " ").replace("\r", "")
    # 检查问题
    issues = []
    if len(jsx_escaped) > 5000:
        issues.append(f"VERY LONG ({len(jsx_escaped)} chars) - eval may fail")
    if '"' in jsx_escaped:
        # 双引号在单引号字符串内是OK的
        pass
    # 检查是否有未转义的反斜杠
    import re
    bad_escapes = re.findall(r'\\[^\\\'"nrtbfu]', jsx_escaped[:1000])
    if bad_escapes:
        issues.append(f"Bad escape sequences: {bad_escapes[:5]}")
    # 检查模板是否引用了外部变量(如comp, L)
    if "var comp" in tpl or "app.project.items.addComp" in tpl:
        issues.append("Template creates its OWN comp - conflicts with wrapper!")
    if "var L" in tpl or "addText" in tpl:
        issues.append("Template creates its OWN text layer - conflicts with wrapper!")
    
    print(f"  Template length: {len(tpl)}")
    print(f"  Escaped length: {len(jsx_escaped)}")
    if issues:
        print("  ISSUES FOUND:")
        for iss in issues:
            print(f"    - {iss}")
    else:
        print("  No obvious issues")
    
    # 显示模板的开头结构
    print("\n  Template starts with:")
    lines = tpl.split('\n')[:10]
    for l in lines:
        print(f"    | {l}")
