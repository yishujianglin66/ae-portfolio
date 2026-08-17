#!/usr/bin/env python3
"""将20个扩充片段合并为一个带标题标注的预览视频"""
import subprocess, os, sys, json
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

BATCH_DIR = Path(r"D:\AE-Work\output\textfx_batch")
TEMP_DIR = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\temp\showreel")
OUTPUT = Path(r"D:\AE-Work\output\textfx_batch\TextFX_Expand_Showreel.mp4")
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# 20个片段顺序及标注信息
CLIPS = [
    {"file":"TextFX_jelly_bounce_v.mp4",    "title":"P0-1 弹性果冻字 竖屏9:16",   "style":"Aest"},
    {"file":"TextFX_cinematic_min.mp4",      "title":"P0-2 电影感极简字 横屏16:9",  "style":"Kyoukai"},
    {"file":"TextFX_lofi_warmth.mp4",        "title":"P0-3 Lo-fi暖调手写 竖屏9:16", "style":"Lo-fi"},
    {"file":"TextFX_soft_bokeh.mp4",         "title":"P0-4 柔焦氛围字 竖屏9:16",    "style":"Zenit"},
    {"file":"TextFX_seamless_trans.mp4",     "title":"P0-5 无缝转场文字 横屏16:9",  "style":"Flux"},
    {"file":"TextFX_jelly_bounce_h.mp4",     "title":"P0-6 弹性果冻字 横屏16:9",    "style":"Aest"},
    {"file":"TextFX_soft_bokeh_h.mp4",       "title":"P0-7 柔焦氛围字 横屏16:9",    "style":"Zenit"},
    {"file":"TextFX_lofi_warmth_h.mp4",      "title":"P0-8 Lo-fi暖调手写 横屏16:9", "style":"Lo-fi"},
    {"file":"TextFX_cinematic_min_v.mp4",    "title":"P0-9 电影感极简字 竖屏9:16",  "style":"Kyoukai"},
    {"file":"TextFX_seamless_trans_v.mp4",   "title":"P0-10 无缝转场文字 竖屏9:16", "style":"Flux"},
    {"file":"TextFX_holo_proj.mp4",          "title":"P1-1 全息投影字 横屏16:9",    "style":"Nxnja"},
    {"file":"TextFX_text_shatter.mp4",       "title":"P1-2 文字破碎重组 横屏16:9",  "style":"Nxnja"},
    {"file":"TextFX_depth_3d.mp4",           "title":"P1-3 3D景深伪效果 横屏16:9",  "style":"DizzyAMV"},
    {"file":"TextFX_ui_hud.mp4",             "title":"P1-4 UI/HUD界面字 竖屏9:16",  "style":"CyberCore"},
    {"file":"TextFX_retro_pixel.mp4",        "title":"P1-5 复古像素字 横屏16:9",    "style":"Retro AMV"},
    {"file":"TextFX_fg_occlude.mp4",         "title":"P1-6 前景遮挡字 横屏16:9",    "style":"Mephis"},
    {"file":"TextFX_holo_proj_v.mp4",        "title":"P1-7 全息投影字 竖屏9:16",    "style":"Nxnja"},
    {"file":"TextFX_text_shatter_v.mp4",     "title":"P1-8 文字破碎重组 竖屏9:16",  "style":"Nxnja"},
    {"file":"TextFX_retro_pixel_v.mp4",      "title":"P1-9 复古像素字 竖屏9:16",    "style":"Retro AMV"},
    {"file":"TextFX_ui_hud_h.mp4",           "title":"P1-10 UI/HUD界面字 横屏16:9", "style":"CyberCore"},
]

W, H, FPS = 1920, 1080, 30
GAP_SEC = 1.5  # 黑色间隔时长

def run_cmd(cmd, desc=""):
    """运行命令并返回结果"""
    print(f"  {desc}..." if desc else "  Running...")
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
    if result.returncode != 0:
        print(f"  ERROR: {result.stderr[:200]}")
        return False
    return True

def get_duration(filepath):
    """获取视频时长"""
    cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
           '-of', 'default=noprint_wrappers=1:nokey=1', str(filepath)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    try:
        return float(result.stdout.strip())
    except:
        return 4.0  # 默认4秒

# Step 1: 生成1.5秒黑色间隔片段
print("Step 1: 创建黑色间隔...")
black_file = TEMP_DIR / "black_gap.mp4"
if not black_file.exists():
    run_cmd([
        'ffmpeg', '-y', '-f', 'lavfi', '-i',
        f'color=c=black:s={W}x{H}:d={GAP_SEC}:r={FPS}',
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
        str(black_file)
    ], "创建黑色间隔")
print(f"  OK: {black_file.name}")

# Step 2: 预处理每个片段（缩放+加标题）
print(f"\nStep 2: 预处理 {len(CLIPS)} 个片段...")
processed = []
for i, clip in enumerate(CLIPS):
    src = BATCH_DIR / clip["file"]
    dst = TEMP_DIR / f"proc_{i:02d}.mp4"
    
    if not src.exists():
        print(f"  [{i+1}/{len(CLIPS)}] SKIP: {src.name} not found")
        continue
    
    # 标题文字（需要转义特殊字符）
    title = clip["title"].replace("'", "\\'").replace(":", "\\:")
    
    # 判断源视频是竖屏还是横屏
    probe_cmd = ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                 '-show_entries', 'stream=width,height',
                 '-of', 'csv=p=0', str(src)]
    result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=10)
    try:
        parts = result.stdout.strip().split(',')
        sw, sh = int(parts[0]), int(parts[1])
    except:
        sw, sh = 1920, 1080
    
    is_vertical = sh > sw
    
    if is_vertical:
        # 竖屏：缩放到高度1080，宽度按比例，居中放置（左右黑边）
        scale_filter = f"scale=-2:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black"
    else:
        # 横屏：缩放到1920x1080
        scale_filter = f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black"
    
    # drawtext: 左上角显示标题
    # fontfile使用系统Arial字体
    drawtext_filter = (
        f"drawtext=text='{title}'"
        f":fontcolor=white:fontsize=28:font=Arial"
        f":x=30:y=30"
        f":box=1:boxcolor=black@0.6:boxborderw=10"
    )
    
    full_filter = f"{scale_filter},{drawtext_filter}"
    
    cmd = [
        'ffmpeg', '-y', '-i', str(src),
        '-vf', full_filter,
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '20',
        '-pix_fmt', 'yuv420p', '-an',  # 无音频
        str(dst)
    ]
    
    ok = run_cmd(cmd, f"[{i+1}/{len(CLIPS)}] {clip['file']}")
    if ok and dst.exists():
        processed.append(dst)
        dur = get_duration(dst)
        print(f"    -> {dur:.1f}s ({'竖屏' if is_vertical else '横屏'})")
    else:
        print(f"    -> FAILED")

print(f"\n  成功预处理: {len(processed)}/{len(CLIPS)} 个片段")

# Step 3: 生成concat列表
print(f"\nStep 3: 生成拼接列表...")
concat_file = TEMP_DIR / "concat_list.txt"
with open(concat_file, 'w', encoding='utf-8') as f:
    for i, proc_file in enumerate(processed):
        f.write(f"file '{str(proc_file).replace(chr(39), chr(39)+chr(39))}'\n")
        if i < len(processed) - 1:
            f.write(f"file '{str(black_file).replace(chr(39), chr(39)+chr(39))}'\n")

print(f"  拼接列表: {concat_file}")

# Step 4: 拼接
print(f"\nStep 4: 拼接最终预览视频...")
cmd = [
    'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
    '-i', str(concat_file),
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '18',
    '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
    str(OUTPUT)
]
ok = run_cmd(cmd, "拼接所有片段")

if ok and OUTPUT.exists():
    mb = OUTPUT.stat().st_size / (1024*1024)
    dur = get_duration(OUTPUT)
    print(f"\n{'='*60}")
    print(f"SUCCESS!")
    print(f"  Output: {OUTPUT}")
    print(f"  Size: {mb:.1f} MB")
    print(f"  Duration: {dur:.1f}s ({dur/60:.1f} min)")
    print(f"  Resolution: {W}x{H} @ {FPS}fps")
    print(f"{'='*60}")
else:
    print(f"\nFAILED: 输出文件未生成")

# Step 5: 生成时间戳清单
print(f"\nStep 5: 生成时间戳清单...")
timeline = []
current_time = 0.0
for i, proc_file in enumerate(processed):
    clip_info = CLIPS[i]
    dur = get_duration(proc_file)
    timeline.append({
        "index": i+1,
        "start": round(current_time, 1),
        "end": round(current_time + dur, 1),
        "duration": round(dur, 1),
        "title": clip_info["title"],
        "style": clip_info["style"],
        "file": clip_info["file"]
    })
    current_time += dur
    if i < len(processed) - 1:
        current_time += GAP_SEC  # 黑色间隔

# 输出清单
print(f"\n{'='*60}")
print("时间戳 → 特效名称 → 风格分类")
print(f"{'='*60}")
for t in timeline:
    print(f"  {t['start']:6.1f}s - {t['end']:6.1f}s | {t['title']:<30} | {t['style']}")

# 保存JSON清单
manifest_file = TEMP_DIR / "showreel_manifest.json"
with open(manifest_file, 'w', encoding='utf-8') as f:
    json.dump({
        "output": str(OUTPUT),
        "total_duration": round(current_time, 1),
        "total_clips": len(timeline),
        "resolution": f"{W}x{H}",
        "fps": FPS,
        "timeline": timeline
    }, f, ensure_ascii=False, indent=2)
print(f"\n清单已保存: {manifest_file}")
