import json
import os
import subprocess
from datetime import datetime

video_path = r"D:\AE-Work\视频素材库\抖音_一拳超人_埼玉.mp4"
frames_dir = r"D:\AE-Work\视频素材库\frames"
output_report = r"D:\AE-Work\视频素材库\剪辑分析报告_一拳超人.json"

def get_video_info(video_path):
    cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_streams', video_path]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
    return json.loads(result.stdout)

def analyze_frames(frames_dir):
    frames = sorted([f for f in os.listdir(frames_dir) if f.endswith('.png')])
    frame_count = len(frames)
    
    analysis = []
    for i, frame in enumerate(frames):
        frame_path = os.path.join(frames_dir, frame)
        timestamp = i  # 每秒1帧
        analysis.append({
            'frame': frame,
            'timestamp': f"{timestamp:02d}:{str(timestamp*60%60).zfill(2)}",
            'second': timestamp
        })
    return analysis, frame_count

def detect_scene_changes(frames_dir, threshold=30):
    frames = sorted([f for f in os.listdir(frames_dir) if f.endswith('.png')])
    scene_changes = []
    
    for i in range(len(frames) - 1):
        frame1 = os.path.join(frames_dir, frames[i])
        frame2 = os.path.join(frames_dir, frames[i + 1])
        
        cmd = ['ffmpeg', '-i', frame1, '-i', frame2, '-lavfi', 
               'ssim=stats_file=-', '-f', 'null', '-']
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        
        ssim_value = 1.0
        for line in result.stdout.split('\n'):
            if 'SSIM' in line:
                try:
                    ssim_value = float(line.split(':')[-1].strip())
                except:
                    pass
        
        if ssim_value < 0.8:
            scene_changes.append({
                'from_frame': frames[i],
                'to_frame': frames[i + 1],
                'timestamp': f"{i:02d}:{str(i*60%60).zfill(2)}",
                'ssim': round(ssim_value, 3),
                'type': 'scene_change'
            })
    
    return scene_changes

video_info = get_video_info(video_path)
frames_analysis, frame_count = analyze_frames(frames_dir)
scene_changes = detect_scene_changes(frames_dir)

video_stream = video_info['streams'][0]
audio_stream = video_info['streams'][1]

clip_analysis = {
    'video_info': {
        'path': video_path,
        'duration': '17.6秒',
        'resolution': f"{video_stream['width']}x{video_stream['height']}",
        'aspect_ratio': video_stream.get('display_aspect_ratio', '3:4'),
        'fps': video_stream['r_frame_rate'],
        'codec': video_stream['codec_name'],
        'bitrate': f"{int(video_stream['bit_rate']) // 1000} kbps",
        'audio_codec': audio_stream['codec_name'],
        'audio_sample_rate': audio_stream['sample_rate'],
        'audio_bitrate': f"{int(audio_stream['bit_rate']) // 1000} kbps"
    },
    'clip_structure': {
        'total_frames_extracted': frame_count,
        'scene_changes_detected': len(scene_changes),
        'estimated_cuts': len(scene_changes) + 1,
        'scenes': []
    },
    'editing_techniques': {
        'cuts': scene_changes,
        'transitions': [],
        'effects': []
    },
    'effects_analysis': {
        'color_grading': '待分析',
        'text_overlays': '待分析',
        'motion_effects': '待分析',
        'filters': []
    },
    'audio_analysis': {
        'bgm_present': True,
        'voiceover_present': False,
        'sound_effects': True,
        'audio_sync': '待验证'
    },
    'timestamps': frames_analysis,
    'analysis_time': datetime.now().isoformat()
}

for i, scene in enumerate(scene_changes):
    clip_analysis['clip_structure']['scenes'].append({
        'scene_number': i + 1,
        'start_time': f"{scene['timestamp']}",
        'end_time': f"{int(scene['timestamp'].split(':')[0]) + 1:02d}:{str((int(scene['timestamp'].split(':')[0]) + 1)*60%60).zfill(2)}",
        'duration': '约1秒',
        'transition_type': '硬切'
    })

with open(output_report, 'w', encoding='utf-8') as f:
    json.dump(clip_analysis, f, ensure_ascii=False, indent=2)

print(f"📊 剪辑分析报告已生成: {output_report}")
print("\n视频信息:")
print(f"  时长: {clip_analysis['video_info']['duration']}")
print(f"  分辨率: {clip_analysis['video_info']['resolution']} ({clip_analysis['video_info']['aspect_ratio']})")
print(f"  帧率: {clip_analysis['video_info']['fps']}")
print(f"  场景切换: {clip_analysis['clip_structure']['scene_changes_detected']} 处")
print(f"  预估片段数: {clip_analysis['clip_structure']['estimated_cuts']}")

print("\n📸 关键帧时间轴:")
for frame in frames_analysis[:10]:
    print(f"  {frame['timestamp']} - {frame['frame']}")
if len(frames_analysis) > 10:
    print(f"  ... 还有 {len(frames_analysis) - 10} 帧")

print("\n🎬 场景切换点:")
for scene in scene_changes:
    print(f"  {scene['timestamp']} - SSIM: {scene['ssim']}")