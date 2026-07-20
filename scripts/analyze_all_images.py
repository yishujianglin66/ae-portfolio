#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批量分析设备图片并生成学习笔记"""

import os
import base64
import time
import requests
from dotenv import load_dotenv
from pathlib import Path

load_dotenv('.env.doubao')

img_dir = Path(r'14-职场学习成长档案\图片')
images = sorted(img_dir.glob('*.jpg'))

api_key = os.environ.get('GPT_GATEWAY_API_KEY')
base_url = os.environ.get('GPT_GATEWAY_BASE_URL')
model = os.environ.get('GPT_GATEWAY_VISION_MODEL', 'gpt-5.6-sol')

print(f'📸 找到 {len(images)} 张图片，开始分析...')
print()

results = []

for i, img_path in enumerate(images, 1):
    print(f'[{i}/{len(images)}] 分析: {img_path.name}...', end=' ', flush=True)
    
    with open(img_path, 'rb') as f:
        img_b64 = base64.b64encode(f.read()).decode('utf-8')
    
    prompt = """请详细分析这张工厂车间的照片：

1. 这是什么设备或场景？
2. 可以看到哪些部件/物品？（尽量具体）
3. 这可能是什么工作岗位的工作内容？
4. 如果是设备，它可能是做什么用的？
5. 有什么值得注意的细节？

请用中文回答，条理清晰。"""
    
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        'model': model,
        'messages': [{
            'role': 'user',
            'content': [
                {'type': 'image_url', 'image_url': {'url': f'data:image/jpeg;base64,{img_b64}'}},
                {'type': 'text', 'text': prompt}
            ]
        }],
        'max_tokens': 1500
    }
    
    start = time.time()
    try:
        r = requests.post(f'{base_url}/chat/completions', headers=headers, json=payload, timeout=120)
        elapsed = time.time() - start
        
        if r.status_code == 200:
            content = r.json()['choices'][0]['message']['content']
            print(f'✅ {elapsed:.1f}s')
            results.append({
                'filename': img_path.name,
                'path': str(img_path),
                'analysis': content
            })
        else:
            print(f'❌ HTTP {r.status_code}')
            results.append({
                'filename': img_path.name,
                'path': str(img_path),
                'analysis': f'分析失败: HTTP {r.status_code}'
            })
    except Exception as e:
        elapsed = time.time() - start
        print(f'❌ {str(e)[:30]}')
        results.append({
            'filename': img_path.name,
            'path': str(img_path),
            'analysis': f'分析失败: {e}'
        })

print()
print('=' * 60)
print('📝 分析结果汇总')
print('=' * 60)

for r in results:
    print(f'\n--- {r["filename"]} ---\n')
    print(r['analysis'])

# 保存为Markdown供后续生成Word使用
output_md = Path(r'14-职场学习成长档案\07-设备学习记录')
output_md.mkdir(parents=True, exist_ok=True)

md_path = output_md / '设备学习笔记-20260717.md'
with open(md_path, 'w', encoding='utf-8') as f:
    f.write('# 设备学习与普工工作笔记\n\n')
    f.write(f'> 日期: 2026-07-17\n')
    f.write(f'> 图片数量: {len(results)} 张\n\n')
    f.write('---\n\n')
    
    for i, r in enumerate(results, 1):
        f.write(f'## 图{i}: {r["filename"]}\n\n')
        f.write(f'![{r["filename"]}]({r["path"]})\n\n')
        f.write(r['analysis'])
        f.write('\n\n---\n\n')

print(f'\n📄 Markdown已保存: {md_path}')
