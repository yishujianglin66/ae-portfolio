"""
t37c_bilibili_download.py - B站API搜索 + yt-dlp下载 + 帧提取
==============================================================
"""
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")
CORPUS_DIR = Path(r"D:\multi_ip_corpus")
DL_BASE = Path(r"D:\anime_downloads")
PYTHON = sys.executable

# 目标IP: B站搜索词 → IP目录名
TARGET_IPS = {
    "蓝色监狱": "blue_lock",
    "咒术回战": "jujutsu_kaisen",
    "辉夜大小姐想让我告白": "kaguya_sama",
    "独自升级": "solo_leveling",
    "狸猫物语": "mao_mao",
    "不时轻声话俄语": "alya_sometimes_hides_her_feelings_in_russian",
    "初音未来": "hatsune_miku",
}


def log(msg, level="INFO"):
    ts = time.strftime("%H:%M:%S")
    print(f"  [{ts}][{level}] {msg}")


def bilibili_search(keyword, page_size=5):
    """通过B站API搜索视频，返回BV号列表"""
    search_url = f"https://api.bilibili.com/x/web-interface/search/type?search_type=video&keyword={urllib.parse.quote(keyword)}&page=1&page_size={page_size}&order=click"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.bilibili.com",
    }
    
    req = urllib.request.Request(search_url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        
        if data.get("code") == 0 and data.get("data", {}).get("result"):
            results = []
            for item in data["data"]["result"]:
                bvid = item.get("bvid", "")
                title = item.get("title", "").replace("<em class=\"keyword\">", "").replace("</em>", "")
                duration = item.get("duration", "")
                if bvid:
                    results.append({"bvid": bvid, "title": title, "duration": duration})
            return results
        else:
            log(f"API返回: code={data.get('code')}, message={data.get('message', '')}", "WARN")
    except Exception as e:
        log(f"B站API搜索失败: {e}", "ERROR")
    
    return []


def ytdlp_download_video(bvid, output_dir, timeout=300):
    """用yt-dlp下载指定BV号的视频"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    url = f"https://www.bilibili.com/video/{bvid}"
    
    # Check if yt-dlp is available as command or module
    ytdlp = shutil.which("yt-dlp")
    if ytdlp:
        cmd = [ytdlp]
    else:
        cmd = [PYTHON, "-m", "yt_dlp"]
    
    cmd += [
        "--no-playlist",
        "-f", "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
        "--merge-output-format", "mp4",
        "-o", str(output_dir / f"{bvid}.%(ext)s"),
        "--no-overwrites",
        url
    ]
    
    log(f"下载: {bvid} → {output_dir.name}")
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout,
                          creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        stdout = r.stdout.decode('utf-8', errors='replace')
        stderr = r.stderr.decode('utf-8', errors='replace')
        
        if r.returncode == 0:
            for f in output_dir.glob(f"{bvid}.*"):
                if f.suffix in ('.mp4', '.mkv', '.webm', '.flv'):
                    sz = f.stat().st_size
                    if sz > 1024 * 1024:
                        log(f"  OK: {f.name} ({sz/1024/1024:.1f}MB)")
                        return str(f)
            # Search more broadly
            for f in output_dir.iterdir():
                if f.stem.startswith(bvid) and f.stat().st_size > 1024 * 1024:
                    log(f"  OK: {f.name} ({f.stat().st_size/1024/1024:.1f}MB)")
                    return str(f)
        else:
            log(f"  失败: {stderr[:200]}", "ERROR")
    except subprocess.TimeoutExpired:
        log(f"  超时 ({timeout}s)", "WARN")
    except Exception as e:
        log(f"  异常: {e}", "ERROR")
    
    return None


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
            err = r.stderr.decode('utf-8', errors='replace')[:200]
            log(f"  提取失败: {err}", "ERROR")
    except Exception as e:
        log(f"  提取异常: {e}", "ERROR")
    return 0


def main():
    print("=" * 60)
    print("  T37c: B站API搜索 + yt-dlp下载 + 帧提取")
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
        print(f"\n{'='*50}")
        log(f"{search_kw} → {ip_name}")
        print(f"{'='*50}")
        
        ip_dl = DL_BASE / ip_name
        ip_dl.mkdir(parents=True, exist_ok=True)
        
        # Step 1: B站API搜索
        search_results = bilibili_search(search_kw, page_size=5)
        log(f"搜索到 {len(search_results)} 个视频")
        for sr in search_results[:3]:
            log(f"  {sr['bvid']} | {sr['title'][:40]} | {sr['duration']}")
        
        # Step 2: 下载前2个
        videos = []
        for sr in search_results[:2]:
            vpath = ytdlp_download_video(sr["bvid"], ip_dl)
            if vpath:
                videos.append(vpath)
            time.sleep(2)
        
        # Step 3: 提取帧
        ip_frames = 0
        for v in videos:
            frames = extract_frames(v, CORPUS_DIR / ip_name / "frames", fps=1, max_frames=300)
            ip_frames += frames
        
        total_new += ip_frames
        results[ip_name] = {"videos": len(videos), "new_frames": ip_frames}
        log(f"结果: +{ip_frames} 帧")
    
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
    report_path = PROJECT_ROOT / "reports" / "t37c_download_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  报告: {report_path}")


if __name__ == "__main__":
    main()
