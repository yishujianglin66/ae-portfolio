"""
Phase 3.1: 下载真实B站AMV/MAD视频用于管线测试

使用 yt-dlp 从B站搜索并下载不同风格的漫剪视频片段。
每个视频只下载前15秒(足够管线分析)，低画质(节省空间)。

输出: data/real_amv_test/ 目录 + ground_truth.json
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# yt-dlp 路径
PYTHON = sys.executable
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "real_amv_test"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# 搜索关键词 → 预期风格标签 (扩展版: 8种风格, 多种搜索词覆盖)
SEARCH_QUERIES = [
    # amv_beat_sync - 踩点/节奏同步
    ("AMV踩点混剪", "amv_beat_sync"),
    ("MAD踩点燃向", "amv_beat_sync"),
    ("动漫节奏踩点", "amv_beat_sync"),
    # amv_pull_zoom - 拉镜/缩放
    ("AMV拉镜缩放", "amv_pull_zoom"),
    ("AMV推拉镜头", "amv_pull_zoom"),
    ("动漫拉镜混剪", "amv_pull_zoom"),
    # amv_fast_cut - 快切
    ("MAD快切", "amv_fast_cut"),
    ("AMV快速剪辑", "amv_fast_cut"),
    ("动漫快切燃", "amv_fast_cut"),
    # amv_cinematic - 电影感
    ("AMV电影感调色", "amv_cinematic"),
    ("动漫电影级调色", "amv_cinematic"),
    ("AMV cinematic", "amv_cinematic"),
    # amv_glitch - 故障风
    ("AMV故障风glitch", "amv_glitch"),
    ("动漫RGB分离特效", "amv_glitch"),
    ("AMV赛博故障", "amv_glitch"),
    # amv_korean_flash - 韩式快闪
    ("韩闪AMV", "amv_korean_flash"),
    ("韩式快闪剪辑", "amv_korean_flash"),
    ("korean flash AMV", "amv_korean_flash"),
    # amv_high_burn - 高燃
    ("AMV高燃", "amv_high_burn"),
    ("动漫高燃混剪", "amv_high_burn"),
    ("AMV超燃踩点", "amv_high_burn"),
    # amv_3d_spatial - 3D空间
    ("AMV 3D运镜", "amv_3d_spatial"),
    ("动漫3D空间特效", "amv_3d_spatial"),
    ("MAD三维镜头", "amv_3d_spatial"),
]

# 每个搜索词下载的最大数量
MAX_PER_QUERY = 2
# 每种风格的最大数量
MAX_PER_STYLE = 7
# 总最大下载数
MAX_TOTAL = 56


def search_videos(query: str, count: int = 5) -> list:
    """搜索B站视频，返回 [(bv_id, title, duration), ...]"""
    cmd = [
        PYTHON, "-m", "yt_dlp",
        "--user-agent", USER_AGENT,
        "--print", "%(id)s\t%(title)s\t%(duration)s",
        f"bilisearch{count}:{query}",
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30,
            encoding="utf-8", errors="replace"
        )
        videos = []
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) >= 3:
                bv_id, title, dur = parts[0], parts[1], parts[2]
                try:
                    duration = float(dur)
                except ValueError:
                    duration = 0
                # 只选择 30-300 秒的视频 (太短没内容,太长下载慢)
                if 30 <= duration <= 300:
                    videos.append((bv_id, title, duration))
        return videos
    except Exception as e:
        print(f"  搜索失败 [{query}]: {e}")
        return []


def download_clip(bv_id: str, title: str, output_path: Path) -> bool:
    """下载视频前15秒片段"""
    url = f"https://www.bilibili.com/video/{bv_id}"
    safe_title = "".join(c for c in title[:30] if c.isalnum() or c in "_ -").strip()
    filename = f"{bv_id}_{safe_title}.mp4"
    full_path = output_path / filename

    if full_path.exists() and full_path.stat().st_size > 100000:
        print(f"  已存在: {filename}")
        return True

    cmd = [
        PYTHON, "-m", "yt_dlp",
        "--user-agent", USER_AGENT,
        "-f", "bv[height<=480]+ba/b",  # DASH分离流: 480p视频+音频
        "--merge-output-format", "mp4",
        "--download-sections", "*0:00-0:15",  # 只下载前15秒
        "-o", str(full_path),
        "--no-playlist",
        "--socket-timeout", "15",
        "--retries", "2",
        url,
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120,
            encoding="utf-8", errors="replace"
        )
        if full_path.exists() and full_path.stat().st_size > 50000:
            print(f"  下载成功: {filename} ({full_path.stat().st_size // 1024}KB)")
            return True
        else:
            # 尝试不带 section 下载完整视频(某些视频不支持section)
            cmd2 = [
                PYTHON, "-m", "yt_dlp",
                "--user-agent", USER_AGENT,
                "-f", "bv[height<=480]+ba/b",
                "--merge-output-format", "mp4",
                "-o", str(full_path),
                "--no-playlist",
                "--socket-timeout", "15",
                "--retries", "2",
                url,
            ]
            result2 = subprocess.run(
                cmd2, capture_output=True, text=True, timeout=180,
                encoding="utf-8", errors="replace"
            )
            if full_path.exists() and full_path.stat().st_size > 50000:
                print(f"  下载成功(完整): {filename} ({full_path.stat().st_size // 1024}KB)")
                return True
            print(f"  下载失败: {bv_id} - {result2.stderr[-200:] if result2.stderr else 'unknown'}")
            return False
    except subprocess.TimeoutExpired:
        print(f"  下载超时: {bv_id}")
        return False
    except Exception as e:
        print(f"  下载异常: {bv_id} - {e}")
        return False


def main():
    print("=" * 60)
    print("Phase 3.1: 下载真实B站AMV/MAD视频 (扩展版 50+)")
    print(f"输出目录: {OUTPUT_DIR}")
    print(f"目标: {MAX_TOTAL} 个视频, 每风格最多 {MAX_PER_STYLE} 个")
    print("=" * 60)

    ground_truth = []
    total_downloaded = 0
    style_counts = {}  # 每种风格已下载数量
    downloaded_bv_ids = set()  # 避免重复下载

    for query, expected_style in SEARCH_QUERIES:
        if total_downloaded >= MAX_TOTAL:
            break
        if style_counts.get(expected_style, 0) >= MAX_PER_STYLE:
            continue

        print(f"\n搜索: [{query}] → 预期风格: {expected_style} "
              f"(已有{style_counts.get(expected_style, 0)}/{MAX_PER_STYLE})")
        videos = search_videos(query, count=8)
        print(f"  找到 {len(videos)} 个合适视频")

        downloaded_for_query = 0
        for bv_id, title, duration in videos:
            if downloaded_for_query >= MAX_PER_QUERY:
                break
            if total_downloaded >= MAX_TOTAL:
                break
            if style_counts.get(expected_style, 0) >= MAX_PER_STYLE:
                break
            if bv_id in downloaded_bv_ids:
                continue

            print(f"  尝试: {bv_id} - {title[:40]}... ({duration:.0f}s)")
            success = download_clip(bv_id, title, OUTPUT_DIR)
            if success:
                ground_truth.append({
                    "bv_id": bv_id,
                    "title": title,
                    "duration": duration,
                    "expected_style": expected_style,
                    "search_query": query,
                })
                downloaded_bv_ids.add(bv_id)
                downloaded_for_query += 1
                total_downloaded += 1
                style_counts[expected_style] = style_counts.get(expected_style, 0) + 1

            time.sleep(1)  # 避免请求过快

    # 保存 ground_truth.json
    gt_path = OUTPUT_DIR / "ground_truth.json"
    with open(gt_path, "w", encoding="utf-8") as f:
        json.dump({
            "description": "真实B站AMV/MAD视频 ground truth 标注 (扩展版)",
            "created": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_videos": len(ground_truth),
            "style_distribution": style_counts,
            "videos": ground_truth,
        }, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print(f"完成! 共下载 {total_downloaded} 个视频")
    print(f"风格分布: {style_counts}")
    print(f"Ground truth: {gt_path}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
