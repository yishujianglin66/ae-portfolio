"""
t37_download_extract_train.py - 自动下载动漫资源 → 提取帧 → 扩充训练数据
========================================================================
流程:
1. 通过蜜柑计划/B站搜索动漫资源
2. 用 aria2/yt-dlp 下载视频
3. ffmpeg 提取关键帧
4. 合并到训练数据集
"""
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PROJECT_ROOT = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "media"))

DOWNLOAD_DIR = Path(r"D:\anime_downloads")
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
CORPUS_DIR = Path(r"D:\multi_ip_corpus")

# 需要补充数据的IP (当前帧数少的)
TARGET_IPS = {
    # 搜索关键词 → (IP目录名, 中文名)
    "蓝色监狱": ("blue_lock", "Blue Lock"),
    "Blue Lock": ("blue_lock", "Blue Lock"),
    "咒术回战": ("jujutsu_kaisen", "Jujutsu Kaisen"),
    "Jujutsu Kaisen": ("jujutsu_kaisen", "Jujutsu Kaisen"),
    "辉夜大小姐": ("kaguya_sama", "Kaguya-sama"),
    "独自升级": ("solo_leveling", "Solo Leveling"),
    "Solo Leveling": ("solo_leveling", "Solo Leveling"),
    "猫猫": ("mao_mao", "MaoMao"),
    "Alya": ("alya_sometimes_hides_her_feelings_in_russian", "Alya"),
    "初音未来": ("hatsune_miku", "Hatsune Miku"),
}


def log(msg, level="INFO"):
    ts = time.strftime("%H:%M:%S")
    print(f"  [{ts}][{level}] {msg}")


# ── Step 1: 搜索动漫资源 ──
def search_anime(keyword, max_results=5):
    """通过 MaterialSearcher 搜索动漫资源"""
    from material_searcher import MaterialSearcher
    ms = MaterialSearcher()
    log(f"搜索: {keyword}")
    try:
        results = ms.search(keyword, min_results=1, max_per_source=max_results)
        log(f"  找到 {len(results)} 个结果")
        for r in results[:5]:
            title = r.get("title", "?")[:60]
            url = r.get("url", r.get("magnet", "?"))[:80]
            size = r.get("size", "?")
            log(f"  - {title} [{size}]")
            log(f"    {url}")
        return results
    except Exception as e:
        log(f"  搜索失败: {e}", "ERROR")
        return []


# ── Step 2: 下载视频 ──
def download_via_aria2(magnet_url, output_dir, filename=None):
    """通过 aria2 JSON-RPC 下载"""
    from auto_downloader import AutoDownloader
    ad = AutoDownloader()
    try:
        ad.aria2.start_daemon()
    except:
        pass
    
    log(f"aria2 下载: {magnet_url[:60]}...")
    try:
        gid = ad.aria2.add_uri(magnet_url, out=filename, dir=str(output_dir))
        if gid:
            log(f"  下载已提交: GID={gid}")
            return gid
    except Exception as e:
        log(f"  aria2 提交失败: {e}", "ERROR")
    return None


def download_via_ytdlp(url, output_dir):
    """通过 yt-dlp 下载"""
    ytdlp = shutil.which("yt-dlp")
    if not ytdlp:
        log("yt-dlp 未找到", "WARN")
        return False
    
    cmd = [
        ytdlp,
        "--no-playlist",
        "-f", "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
        "--merge-output-format", "mp4",
        "-o", str(output_dir / "%(title)s.%(ext)s"),
        url
    ]
    log(f"yt-dlp 下载: {url[:60]}...")
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600,
                          creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        if r.returncode == 0:
            log("  下载完成")
            return True
        else:
            log(f"  yt-dlp 失败: {r.stderr[:200]}", "ERROR")
    except Exception as e:
        log(f"  yt-dlp 异常: {e}", "ERROR")
    return False


# ── Step 3: 提取帧 ──
def extract_frames(video_path, output_dir, ip_name, fps=1, max_frames=200):
    """从视频提取关键帧"""
    output_dir = Path(output_dir) / ip_name / "frames"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    existing = len(list(output_dir.glob("*.jpg")))
    
    cmd = [
        "ffmpeg", "-i", str(video_path),
        "-vf", f"fps={fps},scale=448:-1",
        "-q:v", "2",
        "-frames:v", str(max_frames),
        "-y",
        str(output_dir / "frame_%06d.jpg")
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=300,
                          creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        new_frames = len(list(output_dir.glob("*.jpg"))) - existing
        if r.returncode == 0:
            log(f"  提取 {new_frames} 帧 → {output_dir}")
            return new_frames
        else:
            log(f"  ffmpeg 失败: {r.stderr[:200]}", "ERROR")
    except Exception as e:
        log(f"  提取异常: {e}", "ERROR")
    return 0


# ── Step 4: 从B站直接搜索下载 ──
def search_bilibili_anime(keyword):
    """搜索B站动漫视频并用yt-dlp下载"""
    ytdlp = shutil.which("yt-dlp")
    if not ytdlp:
        log("yt-dlp 不可用", "WARN")
        return []
    
    # B站搜索URL
    search_url = f"https://search.bilibili.com/all?keyword={keyword}&order=click"
    log(f"B站搜索: {keyword}")
    
    # 用yt-dlp提取搜索页面中的视频链接
    cmd = [
        ytdlp,
        "--flat-playlist",
        "--print", "id,title,url",
        "--playlist-items", "1-5",
        search_url
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                          creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        if r.returncode == 0 and r.stdout.strip():
            lines = r.stdout.strip().split("\n")
            results = []
            for line in lines:
                parts = line.split("\t")
                if len(parts) >= 2:
                    vid_id = parts[0]
                    title = parts[1] if len(parts) > 1 else "?"
                    url = f"https://www.bilibili.com/video/{vid_id}"
                    results.append({"id": vid_id, "title": title, "url": url})
                    log(f"  - {title[:50]}")
            return results
        else:
            log("  B站搜索无结果", "WARN")
    except Exception as e:
        log(f"  B站搜索失败: {e}", "ERROR")
    return []


def download_bilibili_video(url, output_dir):
    """用yt-dlp下载B站视频"""
    ytdlp = shutil.which("yt-dlp")
    if not ytdlp:
        return False
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    cmd = [
        ytdlp,
        "--no-playlist",
        "-f", "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
        "--merge-output-format", "mp4",
        "-o", str(output_dir / "%(title).50s.%(ext)s"),
        "--no-overwrites",
        url
    ]
    log(f"  下载: {url}")
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600,
                          creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        if r.returncode == 0:
            # 找到下载的文件
            for f in output_dir.glob("*.mp4"):
                sz = f.stat().st_size
                if sz > 1024 * 1024:  # > 1MB
                    log(f"  下载完成: {f.name} ({sz/1024/1024:.1f}MB)")
                    return str(f)
            log("  下载完成但未找到文件", "WARN")
        else:
            log(f"  下载失败: {r.stderr[:200]}", "ERROR")
    except Exception as e:
        log(f"  下载异常: {e}", "ERROR")
    return None


# ── 主流程 ──
def main():
    print("=" * 60)
    print("  T37: 自动下载 → 提取帧 → 扩充训练数据")
    print("=" * 60)
    
    # 统计当前数据
    print("\n[1/4] 当前IP数据统计:")
    ip_stats = {}
    if CORPUS_DIR.exists():
        for d in sorted(CORPUS_DIR.iterdir()):
            if d.is_dir() and d.name != "extraction_report.json":
                frames = list(d.rglob("*.jpg")) + list(d.rglob("*.png"))
                ip_stats[d.name] = len(frames)
                print(f"  {d.name}: {len(frames)} frames")
    
    # 需要补充的IP (帧数 < 100 的)
    need_more = [ip for ip, cnt in ip_stats.items() if cnt < 100]
    print(f"\n  需要补充 (< 100帧): {need_more}")
    
    # 搜索映射
    search_map = {}
    for keyword, (ip_name, cn_name) in TARGET_IPS.items():
        if ip_name in need_more or ip_name not in ip_stats:
            if ip_name not in search_map:
                search_map[ip_name] = (keyword, cn_name)
    
    if not search_map:
        print("\n  所有IP数据充足！尝试全部搜索更多数据。")
        for keyword, (ip_name, cn_name) in TARGET_IPS.items():
            if ip_name not in search_map:
                search_map[ip_name] = (keyword, cn_name)
    
    # 搜索 + 下载
    print("\n[2/4] 搜索动漫资源...")
    downloaded_videos = []
    
    for ip_name, (keyword, cn_name) in search_map.items():
        print(f"\n  === {cn_name} ({ip_name}) ===")
        ip_download_dir = DOWNLOAD_DIR / ip_name
        ip_download_dir.mkdir(parents=True, exist_ok=True)
        
        # 方法1: B站搜索 + yt-dlp下载
        bilibili_results = search_bilibili_anime(keyword)
        for result in bilibili_results[:2]:  # 每个IP最多下载2个视频
            video_path = download_bilibili_video(result["url"], ip_download_dir)
            if video_path:
                downloaded_videos.append((video_path, ip_name))
        
        # 方法2: 蜜柑计划搜索
        mikan_results = search_anime(keyword, max_results=3)
        for r in mikan_results[:2]:
            url = r.get("magnet", r.get("url", ""))
            if url and (url.startswith("magnet:") or url.startswith("http")):
                if url.startswith("magnet:"):
                    gid = download_via_aria2(url, ip_download_dir)
                    if gid:
                        # aria2下载需要等待完成
                        log(f"  aria2 下载中 (GID={gid})，稍后检查...")
                elif url.endswith((".mp4", ".mkv")):
                    # 直接HTTP下载
                    video_path = download_bilibili_video(url, ip_download_dir)
                    if video_path:
                        downloaded_videos.append((video_path, ip_name))
        
        time.sleep(1)  # 避免请求过快
    
    # 检查aria2下载完成的文件
    print("\n[3/4] 检查下载完成的文件...")
    time.sleep(5)  # 等待aria2写入
    for ip_name in search_map:
        ip_dir = DOWNLOAD_DIR / ip_name
        if ip_dir.exists():
            for f in ip_dir.glob("*.mp4"):
                sz = f.stat().st_size
                if sz > 5 * 1024 * 1024:  # > 5MB
                    vpath = str(f)
                    if vpath not in [v for v, _ in downloaded_videos]:
                        downloaded_videos.append((vpath, ip_name))
                        log(f"  发现: {f.name} ({sz/1024/1024:.1f}MB) → {ip_name}")
            for f in ip_dir.glob("*.mkv"):
                sz = f.stat().st_size
                if sz > 5 * 1024 * 1024:
                    vpath = str(f)
                    if vpath not in [v for v, _ in downloaded_videos]:
                        downloaded_videos.append((vpath, ip_name))
                        log(f"  发现: {f.name} ({sz/1024/1024:.1f}MB) → {ip_name}")
    
    print(f"\n  共获取 {len(downloaded_videos)} 个视频")
    
    # 提取帧
    print("\n[4/4] 提取帧...")
    total_new_frames = 0
    frame_stats = {}
    
    for video_path, ip_name in downloaded_videos:
        print(f"\n  {Path(video_path).name} → {ip_name}")
        new_frames = extract_frames(video_path, CORPUS_DIR, ip_name, fps=1, max_frames=200)
        total_new_frames += new_frames
        frame_stats[ip_name] = frame_stats.get(ip_name, 0) + new_frames
    
    # 汇总
    print("\n" + "=" * 60)
    print("  下载提取完成汇总")
    print("=" * 60)
    print(f"  下载视频: {len(downloaded_videos)} 个")
    print(f"  新增帧数: {total_new_frames}")
    
    if frame_stats:
        print("\n  各IP新增帧数:")
        for ip, cnt in sorted(frame_stats.items()):
            print(f"    {ip}: +{cnt}")
    
    # 更新后统计
    print("\n  更新后各IP总帧数:")
    if CORPUS_DIR.exists():
        for d in sorted(CORPUS_DIR.iterdir()):
            if d.is_dir():
                frames = list(d.rglob("*.jpg")) + list(d.rglob("*.png"))
                print(f"    {d.name}: {len(frames)} frames")
    
    # 保存报告
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "downloaded_videos": len(downloaded_videos),
        "new_frames": total_new_frames,
        "frame_stats": frame_stats,
        "video_details": [{"path": v, "ip": ip} for v, ip in downloaded_videos],
    }
    report_path = PROJECT_ROOT / "reports" / "t37_download_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  报告: {report_path}")


if __name__ == "__main__":
    main()
