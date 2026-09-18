"""
t37d_reextract_more_frames.py - 从现有视频资源提取更多帧
============================================================
之前只用了 fps=1，现在用 fps=2 + 多分辨率裁剪来扩充训练数据。
同时利用MaterialSearcher已下载的视频。
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

CORPUS_DIR = Path(r"D:\multi_ip_corpus")
VIDEO_DIR = Path(r"D:\AE-Work\resources\video")
MAT_DIR = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\output_director\materials")
PROJECT_ROOT = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")

# 视频目录 → IP映射 (从之前的分析得出)
# 目录结构: 视频根目录下的子目录名包含IP关键词
IP_KEYWORDS = {
    "blue_lock": ["蓝色监狱", "Blue Lock", "blue_lock", "nagi", "Nagi"],
    "jujutsu_kaisen": ["咒术回战", "jujutsu", "五条悟"],
    "kaguya_sama": ["辉夜", "kaguya", "Kaguya"],
    "solo_leveling": ["独自升级", "Solo Leveling", "solo_leveling"],
    "mao_mao": ["猫猫", "mao_mao", "è1", "è2", "MAC"],
    "alya_sometimes_hides_her_feelings_in_russian": ["Alya", "alya", "李诗雅"],
    "hatsune_miku": ["初音", "Miku", "miku", "Hatsune"],
    "byakuya_mimori": ["Byakuya", "byakuya"],
    "mao_god_manga": ["毛神"],
}


def log(msg, level="INFO"):
    ts = time.strftime("%H:%M:%S")
    print(f"  [{ts}][{level}] {msg}")


def identify_ip(filepath, dirname):
    """根据文件路径和目录名判断IP"""
    combined = f"{filepath} {dirname}".lower()
    for ip_name, keywords in IP_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in combined:
                return ip_name
    return None


def extract_frames(video_path, output_dir, fps=2, max_frames=500, prefix="frm"):
    """从视频提取帧"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    existing = len(list(output_dir.glob("*.jpg")))
    
    cmd = [
        "ffmpeg", "-i", str(video_path),
        "-vf", f"fps={fps},scale=448:-1",
        "-q:v", "2",
        "-frames:v", str(max_frames),
        "-y",
        str(output_dir / f"{prefix}_%06d.jpg")
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=600,
                          creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        new_count = len(list(output_dir.glob("*.jpg")))
        added = new_count - existing
        if r.returncode == 0 and added > 0:
            return added
        else:
            err = r.stderr.decode('utf-8', errors='replace')[:100]
            log(f"  ffmpeg err: {err}", "WARN")
    except Exception as e:
        log(f"  异常: {e}", "WARN")
    return 0


def get_video_info(video_path):
    """获取视频信息"""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format", "-show_streams",
        str(video_path)
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=30,
                          creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        data = json.loads(r.stdout.decode('utf-8', errors='replace'))
        duration = float(data.get("format", {}).get("duration", 0))
        for s in data.get("streams", []):
            if s.get("codec_type") == "video":
                w = s.get("width", 0)
                h = s.get("height", 0)
                return {"duration": duration, "width": w, "height": h}
        return {"duration": duration, "width": 0, "height": 0}
    except:
        return {"duration": 0, "width": 0, "height": 0}


def main():
    print("=" * 60)
    print("  T37d: 从现有视频提取更多帧 (fps=2)")
    print("=" * 60)
    
    # 当前帧数
    print("\n[当前各IP帧数]")
    before = {}
    for d in sorted(CORPUS_DIR.iterdir()):
        if d.is_dir():
            frames = list(d.rglob("*.jpg")) + list(d.rglob("*.png"))
            before[d.name] = len(frames)
            print(f"  {d.name}: {len(frames)}")
    
    total_new = 0
    ip_new = {}
    
    # ── Part 1: 从 D:\AE-Work\resources\video 提取 ──
    print("\n[Part 1] 扫描 D:\\AE-Work\\resources\\video")
    
    all_videos = []
    for root, dirs, files in os.walk(VIDEO_DIR):
        for f in files:
            if f.lower().endswith(('.mp4', '.mkv', '.avi', '.mov', '.webm')):
                fp = os.path.join(root, f)
                sz = os.path.getsize(fp)
                if sz > 5 * 1024 * 1024:  # > 5MB
                    all_videos.append((fp, sz))
    
    all_videos.sort(key=lambda x: -x[1])
    print(f"  找到 {len(all_videos)} 个视频 (>5MB)")
    
    for vpath, sz in all_videos:
        rel = os.path.relpath(vpath, VIDEO_DIR)
        dirname = os.path.basename(os.path.dirname(vpath))
        
        ip_name = identify_ip(vpath, dirname)
        if not ip_name:
            # Try parent dir
            parent = os.path.basename(os.path.dirname(os.path.dirname(vpath)))
            ip_name = identify_ip(vpath, parent)
        
        if not ip_name:
            continue
        
        # 根据视频大小决定提取帧数
        if sz > 500 * 1024 * 1024:
            fps, max_f = 2, 500
        elif sz > 100 * 1024 * 1024:
            fps, max_f = 2, 300
        elif sz > 30 * 1024 * 1024:
            fps, max_f = 2, 200
        else:
            fps, max_f = 1, 100
        
        fname = Path(vpath).stem[:30]
        frames_dir = CORPUS_DIR / ip_name / "frames"
        
        log(f"{Path(vpath).name[:40]} ({sz/1024/1024:.0f}MB) → {ip_name}")
        added = extract_frames(vpath, frames_dir, fps=fps, max_frames=max_f, prefix="re")
        
        if added > 0:
            total_new += added
            ip_new[ip_name] = ip_new.get(ip_name, 0) + added
            log(f"  +{added} 帧 (fps={fps}, max={max_f})")
    
    # ── Part 2: 从 MaterialSearcher 已下载的视频提取 ──
    print("\n[Part 2] 扫描 MaterialSearcher 下载目录")
    
    if MAT_DIR.exists():
        mat_videos = []
        for f in MAT_DIR.iterdir():
            if f.is_file() and f.suffix.lower() in ('.mp4', '.mkv', '.avi', '.mov', '.webm'):
                sz = f.stat().st_size
                if sz > 5 * 1024 * 1024:
                    mat_videos.append((str(f), sz))
        
        print(f"  找到 {len(mat_videos)} 个视频 (>5MB)")
        
        for vpath, sz in mat_videos:
            fname = Path(vpath).name
            ip_name = identify_ip(vpath, fname)
            
            if not ip_name:
                # MaterialSearcher downloads may have different naming
                # Try to identify from filename
                fn_lower = fname.lower()
                if "blue" in fn_lower or "蓝" in fn_lower:
                    ip_name = "blue_lock"
                elif "jujutsu" in fn_lower or "咒术" in fn_lower:
                    ip_name = "jujutsu_kaisen"
                elif "kaguya" in fn_lower or "辉夜" in fn_lower:
                    ip_name = "kaguya_sama"
                elif "solo" in fn_lower or "独自" in fn_lower or "leveling" in fn_lower:
                    ip_name = "solo_leveling"
                elif "miku" in fn_lower or "初音" in fn_lower:
                    ip_name = "hatsune_miku"
                elif "alya" in fn_lower:
                    ip_name = "alya_sometimes_hides_her_feelings_in_russian"
                elif "mao" in fn_lower or "猫" in fn_lower:
                    ip_name = "mao_mao"
                elif "byakuya" in fn_lower:
                    ip_name = "byakuya_mimori"
                elif "aot" in fn_lower or "attack" in fn_lower or "进击" in fn_lower or "shingeki" in fn_lower:
                    # AoT data is already sufficient, skip
                    continue
            
            if not ip_name:
                log(f"  跳过 (无法识别IP): {fname[:50]}")
                continue
            
            log(f"{fname[:40]} ({sz/1024/1024:.0f}MB) → {ip_name}")
            frames_dir = CORPUS_DIR / ip_name / "frames"
            added = extract_frames(vpath, frames_dir, fps=2, max_frames=300, prefix="mat")
            
            if added > 0:
                total_new += added
                ip_new[ip_name] = ip_new.get(ip_name, 0) + added
                log(f"  +{added} 帧")
    
    # ── 汇总 ──
    print("\n" + "=" * 60)
    print("  汇总")
    print("=" * 60)
    print(f"  新增总帧数: {total_new}")
    
    for ip, cnt in sorted(ip_new.items()):
        print(f"  {ip}: +{cnt}")
    
    print("\n[更新后各IP总帧数]")
    after_total = 0
    for d in sorted(CORPUS_DIR.iterdir()):
        if d.is_dir():
            frames = list(d.rglob("*.jpg")) + list(d.rglob("*.png"))
            cnt = len(frames)
            after_total += cnt
            old = before.get(d.name, 0)
            diff = cnt - old
            marker = f" (+{diff})" if diff > 0 else ""
            print(f"  {d.name}: {cnt}{marker}")
    
    print(f"\n  总帧数: {after_total}")
    
    # 保存报告
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_new_frames": total_new,
        "per_ip_new": ip_new,
        "total_frames_after": after_total,
    }
    report_path = PROJECT_ROOT / "reports" / "t37d_reextract_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  报告: {report_path}")


if __name__ == "__main__":
    main()
