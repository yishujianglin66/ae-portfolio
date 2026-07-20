import json, os, sys, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Use the DuckMiss API (OpenAI-compatible) to generate V17 creative plan
API_KEY = None
env_path = 'C:/Users/Administrator/Desktop/AE-Knowledge-Vault/.env.doubao'
with open(env_path, 'r', encoding='utf-8') as f:
    for line in f:
        if line.startswith('DUCK_MISS_API_KEY='):
            API_KEY = line.strip().split('=', 1)[1]
            break

if not API_KEY:
    print("No API key found!")
    sys.exit(1)

print(f"API Key found: {API_KEY[:10]}...")

# Prompt for AI to generate improved cinematic plan
prompt = """你是一个专业的短视频剪辑导演，擅长电影感混剪。

项目：《冰海战记》(Vinland Saga) 竖屏电影感混剪
参数：1080x1920竖屏 / 30fps / 23.15秒 / BPM=112.35
素材：9个源视频（NCOP/ED/战斗/MAD），已分析运动量

当前5段结构：
1. Intro (0-4s): 冷蓝北欧海洋，慢推
2. Build (4-9s): 暖橙火光预热，旋转拉镜
3. Drop (9-15s): 血红战斗高潮，鱼眼快推
4. Break (15-19s): 冷蓝情感沉淀，慢拉
5. Outro (19-23.15s): 暖→冷史诗收尾

请输出JSON格式的改进方案，包含：

1. "text_overlays": 文字叠加方案（8-12个），每个包含：
   - text: 文字内容（中英混合，电影感）
   - start: 开始时间(秒)
   - end: 结束时间(秒)
   - y_position: Y位置(0-1920)
   - font_style: 字体风格("bold_cn"/"bold_en"/"serif"/"brush")
   - font_size: 字号
   - animation: 动画类型("tracking_fade"/"elastic_scale"/"slide_up"/"glitch_in")
   - color: 颜色[r,g,b] 0-1范围

2. "camera_moves": 拉镜技法方案（5段），每段包含：
   - segment: 段落名
   - technique: 技法名称
   - scale_keyframes: [{time, value_x, value_y}]
   - position_keyframes: [{time, value_x, value_y}]
   - rotation_keyframes: [{time, value}]
   - description: 技法描述

3. "effects_timeline": 特效时间线（15-20个效果），每个包含：
   - name: 效果名
   - type: 类型("flash"/"glitch"/"blur"/"color_shift"/"shake"/"zoom_burst")
   - start: 开始时间
   - end: 结束时间
   - intensity: 强度0-100
   - beat_aligned: 是否对齐节拍

要求：
- 文字要有叙事感（不是简单标题，而是电影字幕风格）
- 拉镜要有电影感（参考Molob/Floby/Xenoz/DxshNova技法）
- 特效要精准对齐BPM节拍（每拍0.534秒）
- Drop段要密集高能，Break段要留白呼吸
"""

import urllib.request
import urllib.error

url = "https://api.duckmiss.com/v1/chat/completions"
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}"
}

data = json.dumps({
    "model": "gpt-4o-mini",
    "messages": [
        {"role": "system", "content": "你是专业的短视频剪辑导演，精通电影感混剪。只输出JSON，不要其他内容。"},
        {"role": "user", "content": prompt}
    ],
    "temperature": 0.7,
    "max_tokens": 4000
}).encode('utf-8')

req = urllib.request.Request(url, data=data, headers=headers, method='POST')

print("Calling AI API for V17 creative plan...")
try:
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read().decode('utf-8'))
    
    content = result['choices'][0]['message']['content']
    print(f"AI response received ({len(content)} chars)")
    
    # Extract JSON from response
    if '```json' in content:
        content = content.split('```json')[1].split('```')[0].strip()
    elif '```' in content:
        content = content.split('```')[1].split('```')[0].strip()
    
    plan = json.loads(content)
    
    # Save plan
    plan_path = 'C:/Users/Administrator/Desktop/AE-Knowledge-Vault/v17_ai_plan.json'
    with open(plan_path, 'w', encoding='utf-8') as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)
    
    print(f"\nV17 AI Plan saved to {plan_path}")
    print(f"  Text overlays: {len(plan.get('text_overlays', []))}")
    print(f"  Camera moves: {len(plan.get('camera_moves', []))}")
    print(f"  Effects: {len(plan.get('effects_timeline', []))}")
    
    # Show summary
    print("\n=== Text Overlays ===")
    for t in plan.get('text_overlays', [])[:5]:
        print(f"  [{t['start']:.1f}-{t['end']:.1f}s] {t['text']} ({t.get('animation','')})")
    
    print("\n=== Camera Moves ===")
    for c in plan.get('camera_moves', []):
        print(f"  {c.get('segment','')}: {c.get('technique','')} - {c.get('description','')[:40]}")
    
    print("\n=== Effects Timeline ===")
    for e in plan.get('effects_timeline', [])[:8]:
        print(f"  [{e['start']:.2f}-{e['end']:.2f}s] {e['type']} intensity={e.get('intensity','')}")
    
except Exception as e:
    print(f"API Error: {e}")
    # Fallback: use enhanced manual plan
    print("Using enhanced manual plan instead...")
    plan = None

if plan is None:
    print("Failed to get AI plan")
