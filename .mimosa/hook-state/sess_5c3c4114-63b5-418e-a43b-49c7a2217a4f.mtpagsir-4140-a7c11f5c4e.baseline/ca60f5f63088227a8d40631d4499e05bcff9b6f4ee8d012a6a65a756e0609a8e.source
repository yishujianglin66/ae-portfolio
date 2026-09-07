r"""
t33_multi_ip_extract.py — 多IP帧提取管线
==========================================
从 D:\AE-Work\resources\video 中的动漫视频资源提取帧，
构建多IP训练数据集，解决AoT单IP过拟合问题。

工作流:
1. 扫描视频资源（排除教程视频）
2. 用ffprobe获取视频信息（分辨率/时长）
3. 用ffmpeg按1fps提取关键帧
4. 按目录/IP组织帧到标准目录结构
5. 生成待VLM标注的文件清单

输出: D:\multi_ip_corpus\{ip_name}\frames\frame_XXXX.jpg
"""
import os, sys, json, subprocess, shutil, time
from pathlib import Path
from collections import defaultdict

# ── 配置 ──────────────────────────────────────────────
VIDEO_DIR = Path(r"D:\AE-Work\resources\video")
OUTPUT_DIR = Path(r"D:\multi_ip_corpus")
FPS = 1  # 每秒提取1帧
MAX_FRAMES_PER_VIDEO = 600  # 每个视频最多提取帧数
MIN_VIDEO_SIZE_MB = 50  # 最小视频文件大小（排除短片/教程）
TARGET_IPS = {
    # 英文名 → IP标准名映射
    "alya": "alya_sometimes_hides_her_feelings_in_russian",
    "blue_lock": "blue_lock",
    "nagi": "blue_lock",
    "byakuya": "byakuya_mimori",
    "mimori": "byakuya_mimori",
    "hatsune miku": "hatsune_miku",
    "miku": "hatsune_miku",
    # 中文名 → IP标准名映射
    "五条悟": "jujutsu_kaisen",
    "李诗雅": "alya_sometimes_hides_her_feelings_in_russian",
    "独自升级": "solo_leveling",
    "猫猫": "mao_mao",
    "美人鱼": "alya_sometimes_hides_her_feelings_in_russian",
    "蓝色监狱": "blue_lock",
    "辉夜": "kaguya_sama",
}
# 需要跳过的目录（教程/非动漫内容）
SKIP_DIRS = {"", "."}  # 根目录下的文件是教程

def run_cmd(cmd, timeout=120):
    """执行命令，返回 (returncode, stdout, stderr)"""
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout,
                          creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        return r.returncode, r.stdout.decode('utf-8', errors='replace'), r.stderr.decode('utf-8', errors='replace')
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"
    except Exception as e:
        return -1, "", str(e)

def get_video_info(video_path):
    """用ffprobe获取视频信息"""
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", str(video_path)
    ]
    rc, out, err = run_cmd(cmd)
    if rc != 0 or not out:
        return None
    try:
        info = json.loads(out)
        duration = float(info.get("format", {}).get("duration", 0))
        width = height = 0
        for s in info.get("streams", []):
            if s.get("codec_type") == "video":
                width = int(s.get("width", 0))
                height = int(s.get("height", 0))
                break
        return {"duration": duration, "width": width, "height": height}
    except:
        return None

def extract_frames(video_path, output_dir, fps=1, max_frames=600):
    """用ffmpeg提取帧"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-vf", f"fps={fps}",
        "-q:v", "2",  # 高质量JPEG
        "-frames:v", str(max_frames),
        "-start_number", "0",
        str(output_dir / "frame_%04d.jpg")
    ]
    rc, out, err = run_cmd(cmd, timeout=300)
    
    # 统计提取的帧数
    frames = list(output_dir.glob("frame_*.jpg"))
    return len(frames)

def identify_ip_from_path(path_str):
    """从路径/文件名推断IP"""
    path_lower = path_str.lower()
    for key, ip_name in TARGET_IPS.items():
        if key in path_lower:
            return ip_name
    return None

def scan_video_resources():
    """扫描视频资源，识别动漫内容"""
    print("=" * 60)
    print("  多IP帧提取管线 — 资源扫描")
    print("=" * 60)
    
    candidates = []
    for root, dirs, files in os.walk(VIDEO_DIR):
        for f in files:
            fp = os.path.join(root, f)
            ext = os.path.splitext(f)[1].lower()
            if ext not in ('.mp4', '.mkv', '.mov', '.avi'):
                continue
            
            size_mb = os.path.getsize(fp) / (1024 * 1024)
            if size_mb < MIN_VIDEO_SIZE_MB:
                continue
            
            # 跳过根目录的教程视频
            rel_dir = os.path.relpath(root, VIDEO_DIR)
            if rel_dir in SKIP_DIRS or rel_dir == '.':
                continue
            
            # 尝试识别IP
            ip_name = identify_ip_from_path(fp)
            
            candidates.append({
                'path': fp,
                'name': f,
                'dir': rel_dir,
                'size_mb': round(size_mb, 1),
                'ip_hint': ip_name,
            })
    
    print(f"\n找到 {len(candidates)} 个候选视频 (>{MIN_VIDEO_SIZE_MB}MB, 排除教程)")
    total_size = sum(c['size_mb'] for c in candidates)
    print(f"总大小: {total_size/1024:.1f} GB")
    
    # 按目录分组显示
    by_dir = defaultdict(list)
    for c in candidates:
        by_dir[c['dir']].append(c)
    
    for d in sorted(by_dir.keys()):
        items = by_dir[d]
        ip_hints = set(i['ip_hint'] for i in items if i['ip_hint'])
        ip_str = f" → IP: {', '.join(ip_hints)}" if ip_hints else ""
        print(f"\n  [{d}]{ip_str}")
        for i in items:
            ip_tag = f" [{i['ip_hint']}]" if i['ip_hint'] else ""
            print(f"    {i['name'][:50]:50s} {i['size_mb']:8.1f} MB{ip_tag}")
    
    return candidates

def extract_all_frames(candidates):
    """从所有候选视频中提取帧"""
    print("\n" + "=" * 60)
    print("  开始提取帧")
    print("=" * 60)
    
    results = []
    total_extracted = 0
    
    for idx, cand in enumerate(candidates):
        video_path = cand['path']
        ip_hint = cand['ip_hint']
        
        # 确定输出目录
        if ip_hint:
            ip_dir = OUTPUT_DIR / ip_hint / "frames"
        else:
            # 用目录名作为临时IP名
            safe_dir_name = cand['dir'].replace('\\', '_').replace('/', '_').replace(' ', '_')
            if not safe_dir_name or safe_dir_name in ('.', ''):
                safe_dir_name = f"unknown_{idx}"
            ip_dir = OUTPUT_DIR / f"pending_{safe_dir_name}" / "frames"
        
        print(f"\n  [{idx+1}/{len(candidates)}] {cand['name'][:50]}")
        print(f"    → {ip_dir.parent.name}")
        
        # 获取视频信息
        info = get_video_info(video_path)
        if not info:
            print(f"    ✗ 无法获取视频信息")
            continue
        
        duration = info['duration']
        resolution = f"{info['width']}x{info['height']}"
        est_frames = min(int(duration * FPS), MAX_FRAMES_PER_VIDEO)
        print(f"    时长: {duration:.0f}s, 分辨率: {resolution}, 预计帧: {est_frames}")
        
        # 检查是否已提取
        if ip_dir.exists() and list(ip_dir.glob("frame_*.jpg")):
            existing = len(list(ip_dir.glob("frame_*.jpg")))
            print(f"    ⊙ 已存在 {existing} 帧，跳过")
            total_extracted += existing
            results.append({
                'ip': ip_dir.parent.name,
                'video': cand['name'],
                'frames': existing,
                'dir': str(ip_dir.parent),
                'status': 'existing'
            })
            continue
        
        # 提取帧
        t0 = time.time()
        n_frames = extract_frames(video_path, ip_dir, fps=FPS, max_frames=MAX_FRAMES_PER_VIDEO)
        elapsed = time.time() - t0
        
        print(f"    ✓ 提取 {n_frames} 帧 ({elapsed:.1f}s)")
        total_extracted += n_frames
        
        results.append({
            'ip': ip_dir.parent.name,
            'video': cand['name'],
            'frames': n_frames,
            'dir': str(ip_dir.parent),
            'status': 'extracted',
            'duration': duration,
            'resolution': resolution,
        })
    
    return results

def generate_summary(results):
    """生成提取结果汇总"""
    print("\n" + "=" * 60)
    print("  提取结果汇总")
    print("=" * 60)
    
    # 按IP分组
    by_ip = defaultdict(lambda: {'frames': 0, 'videos': 0, 'dirs': set()})
    for r in results:
        ip = r['ip']
        by_ip[ip]['frames'] += r['frames']
        by_ip[ip]['videos'] += 1
        by_ip[ip]['dirs'].add(r['dir'])
    
    print(f"\n{'IP':45s} {'帧数':>8s} {'视频数':>6s}")
    print("-" * 65)
    total_frames = 0
    for ip in sorted(by_ip.keys(), key=lambda x: -by_ip[x]['frames']):
        info = by_ip[ip]
        total_frames += info['frames']
        print(f"  {ip:43s} {info['frames']:8d} {info['videos']:6d}")
    
    print("-" * 65)
    print(f"  {'总计':43s} {total_frames:8d}")
    
    # 保存汇总报告
    report = {
        'total_videos': len(results),
        'total_frames': total_frames,
        'ip_count': len(by_ip),
        'by_ip': {ip: {'frames': info['frames'], 'videos': info['videos'], 'dirs': list(info['dirs'])}
                  for ip, info in by_ip.items()},
        'details': results,
    }
    
    report_path = OUTPUT_DIR / "extraction_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n报告已保存: {report_path}")
    
    return report

def main():
    print("\n" + "█" * 60)
    print("  T33: 多IP帧提取管线")
    print("  从视频资源提取多IP训练数据")
    print("█" * 60)
    
    # Step 1: 扫描资源
    candidates = scan_video_resources()
    
    if not candidates:
        print("\n✗ 未找到候选视频")
        return
    
    # Step 2: 提取帧
    results = extract_all_frames(candidates)
    
    # Step 3: 汇总
    report = generate_summary(results)
    
    print(f"\n{'='*60}")
    print(f"  完成! 共提取 {report['total_frames']} 帧, 覆盖 {report['ip_count']} 个IP分组")
    print(f"  输出目录: {OUTPUT_DIR}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
