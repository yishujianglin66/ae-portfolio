#!/usr/bin/env python3
"""诊断2: 检查textLayerName参数默认值 + 模拟eval执行路径"""
import json
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "text_animation_presets.json"
cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
cats = cfg["categories"]

print("=" * 70)
print("  DIAG 2: Parameter defaults & eval path simulation")
print("=" * 70)

# 检查textLayerName和duration参数
for cat_key, cat_data in list(cats.items())[:4]:
    p = cat_data["presets"][0]
    params = p.get("parameters", [])
    print(f"\n[{cat_key}] {p['id']}")
    for param in params:
        print(f"  {param['name']} = {param.get('default', 'NO DEFAULT')} ({param.get('type','?')})")

# 模拟render_all_presets_3s.py的fill_template
print("\n" + "=" * 70)
print("  SIMULATE: fill_template for kt_char_waterfall")
print("=" * 70)
p = cats["kinetic_typography"]["presets"][0]
template = p["jsx_template"]
params = p.get("parameters", [])

jsx = template
for param in params:
    key = "{{" + param["name"] + "}}"
    val = param.get("default", "")
    if isinstance(val, bool):
        jsx = jsx.replace(key, "true" if val else "false")
    elif isinstance(val, str):
        jsx = jsx.replace(key, val)
    else:
        jsx = jsx.replace(key, str(val))
jsx = re.sub(r'\{\{(\w+)\}\}', '0', jsx)

# 检查填充后的关键内容
print("  After fill_template:")
print(f"  Contains 'app.project.activeItem': {'app.project.activeItem' in jsx}")
# 找textLayerName被替换成什么
m = re.search(r"var n='([^']*)'", jsx)
if m:
    print(f"  Layer name searched: '{m.group(1)}'")
else:
    print("  Could not find layer name pattern")

# 模拟wrapper中创建的图层名
wrapper_layer_name = "\u6807\u9898\u6587\u5b57"  # 标题文字
print(f"  Wrapper creates layer named: '{wrapper_layer_name}'")
print(f"  MATCH: {m.group(1) == wrapper_layer_name if m else 'UNKNOWN'}")

# 检查eval转义后是否有语法问题
print("\n" + "=" * 70)
print("  EVAL ESCAPING ANALYSIS")
print("=" * 70)
jsx_escaped = jsx.replace("'", "\\'").replace("\n", " ").replace("\r", "")
print(f"  Escaped length: {len(jsx_escaped)} chars")

# 关键: 检查转义后的字符串中是否有问题
# 在JS单引号字符串中, 不能有未转义的单引号
# 检查replace("'", "\\'") 是否正确
# 问题: 如果原文有 \\' (转义的反斜杠+引号), replace会破坏它
if "\\\\" in jsx:
    print("  WARNING: Template contains literal backslashes!")
    
# 检查模板中的单引号数量
sq_count = jsx.count("'")
print(f"  Single quotes in template: {sq_count}")
print(f"  After escaping: {jsx_escaped.count(chr(92)+chr(39))} escaped quotes")

# 最关键的问题: eval('...') 中如果内容太长或有特殊字符
# AE的ExtendScript eval有长度限制吗?
print("\n  CRITICAL ISSUE ANALYSIS:")
print(f"  1. Template uses app.project.activeItem: {'app.project.activeItem' in jsx}")
print("     -> After addComp(), activeItem is NOT set to new comp!")
print("     -> Template immediately returns 'No active comp' error!")
print("  2. Wrapper catch(pe){} silently swallows this error")
print("  3. Result: text layer created but NO animation applied")

# 验证: 3d_title preset使用不同模式
print("\n" + "=" * 70)
print("  3D TITLE PATTERN (uses _comp parameter)")
print("=" * 70)
p3d = cats["3d_title"]["presets"][0]
tpl3d = p3d["jsx_template"]
print(f"  Starts with: {tpl3d[:80]}")
print(f"  Uses activeItem: {'app.project.activeItem' in tpl3d}")
print(f"  Uses _comp param: {'(function(_comp)' in tpl3d}")
