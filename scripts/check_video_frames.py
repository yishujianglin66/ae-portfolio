"""检查有显著性候选点视频的帧数。"""
import json, subprocess
from pathlib import Path

prompts = json.loads(Path(r'D:\AE-Work\saliency_vis\saliency_prompts.json').read_text(encoding='utf-8'))
with_prompts = [p for p in prompts if p['prompts']]
print(f'有候选点视频: {len(with_prompts)} 个')
for p in with_prompts:
    stem = p['stem']
    src = Path(r'C:\Users\Administrator\Desktop\AE-Knowledge-Vault\data\real_amv_test') / f'{stem}.mp4'
    r = subprocess.run(
        [r'C:\ffmpeg\bin\ffprobe.exe', '-v', 'error', '-select_streams', 'v:0',
         '-show_entries', 'stream=nb_frames', '-of', 'default=noprint_wrappers=1:nokey=1', str(src)],
        capture_output=True, text=True,
    )
    frames = int(r.stdout.strip()) if r.stdout.strip().isdigit() else 0
    est_min = frames / 2  # 2帧/分钟
    n = len(p['prompts'])
    print(f'  {stem[:50]:<50} {frames:>6} frames  est={est_min:.0f}min  prompts={n}')
