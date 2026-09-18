"""
t37b_direct_download_extract.py - 直接用yt-dlp下载B站视频并提取帧
=====================================================================
绕过MaterialSearcher，直接用yt-dlp下载B站动漫视频，然后提取帧扩充训练数据。
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")
CORPUS_DIR = Path(r"D:\multi_ip_corpus")
DL_BASE = Path(r"D:\anime_downloads")
PYTHON = sys.executable

# 目标IP: B站搜索关键词 → IP目录名
TARGET_IPS = {
    "蓝色监狱 合集": "blue_lock",
    "咒术回战 合集": "jujutsu_kaisen",
    "辉夜大小姐 合集": "kaguya_sama",
    "独自升级 合集": "solo_leveling",
    "猫猫 动漫": "mao_mao",
    "Alya 动漫": "alya_sometimes_hides_her_feelings_in_russian",
    "初音未来 Miku": "hatsune_miku",
}


def log(msg, level="INFO"):
    ts = time.strftime("%H:%M:%S")
    print(f"  [{ts}][{level}] {msg}")


def ytdlp_download(search_keyword, output_dir, max_videos=3):
    """用yt-dlp搜索B站并下载视频"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    ytdlp = shutil.which("yt-dlp")
    if not ytdlp:
        # Try python -m yt_dlp
        ytdlp_cmd = [PYTHON, "-m", "yt_dlp"]
    else:
        ytdlp_cmd = [ytdlp]
    
    # B站搜索
    search_url = f"https://search.bilibili.com/all?keyword={search_keyword}&order=click"
    log(f"B站搜索: {search_keyword}")
    
    # 先获取视频列表
    cmd = ytdlp_cmd + [
        "--flat-playlist",
        "--print", "id,title",
        "--playlist-items", f"1-{max_videos * 2}",
        search_url
    ]
    
    downloaded = []
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=60,
                          creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        if r.returncode != 0:
            log(f"搜索失败: {r.stderr[:200]}", "ERROR")
            return downloaded
        
        lines = r.stdout.decode('utf-8', errors='replace').strip().split("\n")
        videos = []
        for line in lines:
            parts = line.strip().split("\t")
            if len(parts) >= 2:
                vid_id = parts[0].strip()
                title = parts[1].strip()[:60]
                if vid_id.startswith("BV"):
                    videos.append((vid_id, title))
        
        log(f"找到 {len(videos)} 个候选视频")
        
        # 下载前max_videos个
        for vid_id, title in videos[:max_videos]:
            url = f"https://www.bilibili.com/video/{vid_id}"
            log(f"下载: {title} ({vid_id})")
            
            out_template = str(output_dir / f"{vid_id}.%(ext)s")
            cmd = ytdlp_cmd + [
                "--no-playlist",
                "-f", "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
                "--merge-output-format", "mp4",
                "-o", out_template,
                "--no-overwrites",
                "--socket-timeout", "30",
                url
            ]
            
            try:
                r = subprocess.run(cmd, capture_output=True, timeout=300,
                                  creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                if r.returncode == 0:
                    # 找到下载的文件
                    for f in output_dir.glob(f"{vid_id}.*"):
                        sz = f.stat().st_size
                        if sz > 1024 * 1024:  # > 1MB
                            log(f"  OK: {f.name} ({sz/1024/1024:.1f}MB)")
                            downloaded.append(str(f))
                            break
                else:
                    err = r.stderr.decode('utf-8', errors='replace')[:200]
                    log(f"  失败: {err}", "ERROR")
            except subprocess.TimeoutExpired:
                log("  超时", "WARN")
            except Exception as e:
                log(f"  异常: {e}", "ERROR")
            
            time.sleep(2)
            
    except Exception as e:
        log(f"搜索异常: {e}", "ERROR")
    
    return downloaded


def extract_frames(video_path, output_dir, fps=1, max_frames=300):
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
        str(output_dir / "dl_%06d.jpg")
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=600,
                          creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        new_count = len(list(output_dir.glob("*.jpg")))
        new_frames = new_count - existing
        if r.returncode == 0 and new_frames > 0:
            log(f"  提取 {new_frames} 帧 (总计 {new_count})")
            return new_frames
        else:
            log(f"  提取失败: {r.stderr.decode('utf-8', errors='replace')[:200]}", "ERROR")
    except Exception as e:
        log(f"  提取异常: {e}", "ERROR")
    return 0


def main():
    print("=" * 60)
    print("  T37b: yt-dlp直接下载B站 + 提取帧")
    print("=" * 60)
    
    # 当前数据
    print("\n[当前IP数据]")
    for d in sorted(CORPUS_DIR.iterdir()):
        if d.is_dir():
            frames = list(d.rglob("*.jpg")) + list(d.rglob("*.png"))
            print(f"  {d.name}: {len(frames)}")
    
    total_new = 0
    results = {}
    
    for search_kw, ip_name in TARGET_IPS.items():
        print(f"\n{'='*40}")
        print(f"  {search_kw} → {ip_name}")
        print(f"{'='*40}")
        
        ip_dl = DL_BASE / ip_name
        ip_dl.mkdir(parents=True, exist_ok=True)
        
        # 下载
        videos = ytdlp_download(search_kw, ip_dl, max_videos=2)
        log(f"下载了 {len(videos)} 个视频")
        
        # 提取帧
        ip_frames = 0
        for v in videos:
            frames = extract_frames(v, CORPUS_DIR / ip_name / "frames", fps=1, max_frames=300)
            ip_frames += frames
        
        total_new += ip_frames
        results[ip_name] = {"videos": len(videos), "new_frames": ip_frames}
        log(f"{ip_name}: +{ip_frames} 帧")
    
    # 汇总
    print("\n" + "=" * 60)
    print("  汇总")
    print("=" * 60)
    print(f"  新增总帧数: {total_new}")
    
    for ip, info in results.items():
        print(f"  {ip}: +{info['new_frames']} 帧 ({info['videos']} 视频)")
    
    print("\n[更新后各IP总帧数]")
    for d in sorted(CORPUS_DIR.iterdir()):
        if d.is_dir():
            frames = list(d.rglob("*.jpg")) + list(d.rglob("*.png"))
            print(f"  {d.name}: {len(frames)}")
    
    # 保存报告
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_new_frames": total_new,
        "per_ip": results,
    }
    report_path = PROJECT_ROOT / "reports" / "t37b_download_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  报告: {report_path}")


if __name__ == "__main__":
    main()
