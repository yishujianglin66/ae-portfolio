#!/usr/bin/env python3
"""
从B站下载冰海战记素材视频
"""

import os
import sys
import subprocess
import time

OUTPUT_DIR = r"D:\AE-Work\视频素材库\冰海战记新素材"
os.makedirs(OUTPUT_DIR, exist_ok=True)

VIDEOS = [
    {"id": 1, "url": "https://www.bilibili.com/video/BV1zc411g7Mr", "desc": "冰海战记NCOP&ED 4K合集"},
    {"id": 2, "url": "https://www.bilibili.com/video/BV1SG411C7XJ", "desc": "冰海战记最后的封神场面"},
    {"id": 3, "url": "https://www.bilibili.com/video/BV1pu411t7pq", "desc": "托尔芬VS蛇 最精彩打戏"},
    {"id": 4, "url": "https://www.bilibili.com/video/BV1mh4y1U7vd", "desc": "4K 60fps 冰海战记MAD"},
    {"id": 5, "url": "https://www.bilibili.com/video/BV1S8411c7RR", "desc": "冰海战记MAD revolution"},
]

def download_video(url, output_template):
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--no-warnings",
        "--no-check-certificates",
        "-o", output_template,
        "-f", "bestvideo+bestaudio/best",
        "--merge-output-format", "mp4",
        url
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180, encoding="utf-8")
        return result.returncode == 0, result.stdout + result.stderr
    except Exception as e:
        return False, str(e)


def main():
    print("=" * 60)
    print("从B站下载冰海战记素材视频")
    print("=" * 60)

    results = []

    for v in VIDEOS:
        output_template = os.path.join(OUTPUT_DIR, f"vinland_{v['id']}_%(title)s.%(ext)s")
        # 清理文件名
        output_template = output_template.replace(" ", "_")
        print(f"\n[{v['id']}/{len(VIDEOS)}] {v['desc']}")
        print(f"  URL: {v['url']}")

        success, msg = download_video(v["url"], output_template)

        if success:
            # 查找实际下载的文件
            found_files = [f for f in os.listdir(OUTPUT_DIR) if f.startswith(f"vinland_{v['id']}")]
            if found_files:
                filepath = os.path.join(OUTPUT_DIR, found_files[0])
                size = os.path.getsize(filepath)
                print(f"  成功! {found_files[0]} ({size/1024/1024:.2f} MB)")
                results.append({"id": v["id"], "path": filepath, "desc": v["desc"], "size": size, "success": True})
            else:
                print(f"  下载成功但文件未找到")
                results.append({"id": v["id"], "path": None, "desc": v["desc"], "success": False, "error": "File not found"})
        else:
            print(f"  失败: {msg[:300]}")
            results.append({"id": v["id"], "path": None, "desc": v["desc"], "success": False, "error": msg[:500]})

        time.sleep(2)

    print("\n" + "=" * 60)
    print("下载结果汇总:")
    for r in results:
        status = f"成功 ({r.get('size', 0)/1024/1024:.1f}MB)" if r.get("success") else "失败"
        print(f"  [{r['id']}] {r['desc']} - {status}")

    successful = [r for r in results if r.get("success")]
    print(f"\n成功下载: {len(successful)}/{len(VIDEOS)}")

    return results


if __name__ == "__main__":
    main()