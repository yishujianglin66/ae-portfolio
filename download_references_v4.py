#!/usr/bin/env python3
"""
抖音视频下载器 - 获取cookies后下载
"""

import os
import sys
import json
import subprocess
import time
import httpx

OUTPUT_DIR = r"D:\AE-Work\视频素材库\参考分析"
os.makedirs(OUTPUT_DIR, exist_ok=True)

VIDEOS = [
    {"id": 1, "url": "https://v.douyin.com/-kugBZe9Zmk/", "author": "Alaul1n", "desc": "你没有敌人"},
    {"id": 2, "url": "https://v.douyin.com/Spy1iiuy8wk/", "author": "水羊", "desc": "任何人都没有敌人"},
    {"id": 3, "url": "https://v.douyin.com/jKR6N1_07tw/", "author": "水羊", "desc": "愿我的仁慈胜过我的怒火"},
    {"id": 4, "url": "https://v.douyin.com/uCGNd30sE54/", "author": "混的羊", "desc": "真正的战士不需要剑"},
    {"id": 5, "url": "https://v.douyin.com/VTP3mhlrCsw/", "author": "BlackStar", "desc": "救赎不是抹去血痕"},
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.douyin.com/",
}


def get_douyin_cookies():
    """访问抖音主页获取cookies"""
    print("获取抖音cookies...")
    try:
        with httpx.Client(follow_redirects=True, timeout=15) as client:
            # 先访问主页
            resp = client.get("https://www.douyin.com/", headers=HEADERS)
            cookies = dict(resp.cookies)
            print(f"  获取到 {len(cookies)} 个cookies")
            for k in cookies:
                print(f"    {k}")

            # 尝试获取ttwid
            if "ttwid" not in cookies:
                try:
                    resp2 = client.post(
                        "https://ttwid.bytedance.com/ttwid/union/register/",
                        json={
                            "region": "cn",
                            "aid": 1768,
                            "needFid": False,
                            "service": "www.douyin.com",
                            "migrate_info": {"ticket": "", "source": "node"},
                            "cbUrlProtocol": "https",
                            "union": True,
                        },
                        headers={**HEADERS, "Content-Type": "application/json"},
                    )
                    if resp2.status_code == 200:
                        data = resp2.json()
                        if "ttwid" in data:
                            cookies["ttwid"] = data["ttwid"]
                            print(f"  获取ttwid成功")
                except:
                    pass

            return cookies
    except Exception as e:
        print(f"  获取cookies失败: {e}")
        return {}


def save_cookies_netscape(cookies, filepath):
    """保存为Netscape cookies格式"""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("# Netscape HTTP Cookie File\n")
        for name, value in cookies.items():
            f.write(f".douyin.com\tTRUE\t/\tFALSE\t0\t{name}\t{value}\n")


def download_with_ytdlp(url, output_path, cookies_file):
    """使用yt-dlp下载"""
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--no-warnings",
        "--no-check-certificates",
        "--cookies", cookies_file,
        "-o", output_path,
        "-f", "best",
        url
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, encoding="utf-8")
        return result.returncode == 0, result.stdout + result.stderr
    except Exception as e:
        return False, str(e)


def main():
    print("=" * 60)
    print("下载5个抖音参考视频（Cookies模式）")
    print("=" * 60)

    # 获取cookies
    cookies = get_douyin_cookies()
    cookies_file = os.path.join(OUTPUT_DIR, "douyin_cookies.txt")
    if cookies:
        save_cookies_netscape(cookies, cookies_file)
        print(f"  Cookies保存到: {cookies_file}")
    else:
        print("  未获取到cookies，退出")
        return

    results = []

    for v in VIDEOS:
        output_path = os.path.join(OUTPUT_DIR, f"ref_{v['id']}_{v['author']}.mp4")
        print(f"\n[{v['id']}/5] {v['desc']} (作者: {v['author']})")

        success, msg = download_with_ytdlp(v["url"], output_path, cookies_file)

        if success and os.path.exists(output_path):
            size = os.path.getsize(output_path)
            print(f"  成功! 文件大小: {size / 1024 / 1024:.2f} MB")
            results.append({"id": v["id"], "path": output_path, "author": v["author"], "desc": v["desc"], "size": size, "success": True})
        else:
            print(f"  失败: {msg[:500]}")
            results.append({"id": v["id"], "path": None, "author": v["author"], "desc": v["desc"], "success": False, "error": msg[:500]})

        time.sleep(2)

    print("\n" + "=" * 60)
    print("下载结果汇总:")
    for r in results:
        status = "成功" if r.get("success") else "失败"
        print(f"  [{r['id']}] {r['author']}: {r['desc']} - {status}")

    with open(os.path.join(OUTPUT_DIR, "download_results.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    return results


if __name__ == "__main__":
    main()