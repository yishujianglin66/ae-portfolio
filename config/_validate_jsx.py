# -*- coding: utf-8 -*-
"""验证 text_animation_presets.json 中所有 jsx_template 符合 MCP 自动化规范"""
import json
import os
import sys

p = r'c:\Users\Administrator\Desktop\AE-Knowledge-Vault\config\text_animation_presets.json'
with open(p, encoding='utf-8') as f:
    d = json.load(f)

iife_start = '(function(){var _r={};try{'
iife_end = 'return JSON.stringify(_r);})();'
error_pattern = "catch(e){_r={status:'error',message:e.toString()};}"

total = 0
valid = 0
invalid = []
long_lines = []

for cat_name, cat in d['categories'].items():
    for preset in cat['presets']:
        total += 1
        jsx = preset.get('jsx_template', '')
        checks = {
            'iife_start': jsx.startswith(iife_start),
            'iife_end': jsx.endswith(iife_end),
            'explicit_return': 'return JSON.stringify(_r);' in jsx,
            'catch_block': error_pattern in jsx,
            'has_placeholder': '{{' in jsx and '}}' in jsx,
            'es3_no_const': 'const ' not in jsx,
            'es3_no_let': ' let ' not in jsx,
            'es3_no_arrow': '=>' not in jsx.replace('>=', '').replace('<=', '').replace('==', '').replace('!=', ''),
        }
        failed = [k for k, v in checks.items() if not v]
        if not failed:
            valid += 1
        else:
            invalid.append((preset['id'], failed))

print('=== JSON JSX 验证 ===')
print('Total presets:', total)
print('Valid:', valid)
print('Invalid:', len(invalid))
if invalid:
    print('--- Invalid presets (first 10) ---')
    for pid, fails in invalid[:10]:
        print(' ', pid, ':', fails)

print()
print('=== Markdown JSX 代码块统计 ===')
md_files = [
    r'c:\Users\Administrator\Desktop\AE-Knowledge-Vault\10-风格化剪辑知识库\文字动画预设库-MCP自动化版.md',
    r'c:\Users\Administrator\Desktop\AE-Knowledge-Vault\10-风格化剪辑知识库\文字动画效果库.md',
    r'c:\Users\Administrator\Desktop\AE-Knowledge-Vault\10-风格化剪辑知识库\风格化预设宝典.md',
    r'c:\Users\Administrator\Desktop\AE-Knowledge-Vault\10-风格化剪辑知识库\字体预设库.md',
    r'c:\Users\Administrator\Desktop\AE-Knowledge-Vault\07-MCP参考指南\AE内置预设全索引.md',
    r'c:\Users\Administrator\Desktop\AE-Knowledge-Vault\07-MCP参考指南\preset-catalog.md',
]

total_blocks = 0
total_returns = 0
for md in md_files:
    if not os.path.exists(md):
        print('[NOT FOUND]', md)
        continue
    with open(md, encoding='utf-8') as f:
        content = f.read()
    blocks = content.count('```jsx')
    returns = content.count('return JSON.stringify(_r)')
    iife_starts = content.count('(function(){var _r={};try{')
    iife_ends = content.count('})();')
    total_blocks += blocks
    total_returns += returns
    name = os.path.basename(md)
    print(f'{name}:')
    print(f'  jsx blocks: {blocks}')
    print(f'  return JSON.stringify(_r): {returns}')
    print(f'  IIFE starts: {iife_starts}')
    print('  IIFE ends (})();): ' + str(iife_ends))

print()
print('=== 总结 ===')
print(f'JSON 预设验证: {valid}/{total} 通过')
print(f'Markdown JSX 代码块总数: {total_blocks}')
print(f'显式 return 语句总数: {total_returns}')
