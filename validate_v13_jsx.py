#!/usr/bin/env python3
import re
import sys

if len(sys.argv) > 1:
    jsx_path = sys.argv[1]
else:
    jsx_path = r'c:\Users\Administrator\Desktop\AE-Knowledge-Vault\scripts\vinland_saga_v13_5.jsx'

print(f'验证文件: {jsx_path}')

with open(jsx_path, 'r', encoding='utf-8') as f:
    content = f.read()

issues = []
brace_count = 0
paren_count = 0
for i, c in enumerate(content):
    if c == '{':
        brace_count += 1
    elif c == '}':
        brace_count -= 1
    elif c == '(':
        paren_count += 1
    elif c == ')':
        paren_count -= 1
    if brace_count < 0 or paren_count < 0:
        issues.append(f'Line {content[:i].count(chr(10))+1}: 括号不匹配')

if brace_count != 0:
    issues.append(f'整体大括号不平衡: {brace_count}')
if paren_count != 0:
    issues.append(f'整体圆括号不平衡: {paren_count}')

sources_match = re.search(r'var SOURCES = \{([^}]+)\};', content, re.DOTALL)
if sources_match:
    sources_content = sources_match.group(1)
    keys = re.findall(r'"([^"]+)":', sources_content)
    print(f'SOURCES 对象键: {keys}')
    print(f'SOURCES 对象数量: {len(keys)}')
    if len(keys) != 9:
        issues.append(f'SOURCES 对象应该有9个键, 实际 {len(keys)}')
else:
    issues.append('未找到 SOURCES 对象')

# 简化检查: 直接搜索段落名
seg_names = re.findall(r'name: "([^"]+)"', content)
if seg_names:
    print(f'SEGMENTS 段落: {seg_names}')
else:
    issues.append('未找到 SEGMENTS 段落名')

vars_check = ['COMP_NAME', 'LUT_CREATIVE', 'LUT_TECHNICAL', 'CLIP_PATH', 'AUDIO_PATH', 'DURATION', 'BPM', 'BEAT_INTERVAL']
for var in vars_check:
    if f'var {var} =' not in content:
        issues.append(f'缺失变量: {var}')

print()
if issues:
    print('发现问题:')
    for i, issue in enumerate(issues, 1):
        print(f'  {i}. {issue}')
else:
    print('语法检查通过, 未发现明显问题')

print(f'文件行数: {content.count(chr(10)) + 1}')
