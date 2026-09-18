import asyncio
import json
import os
import re
from pathlib import Path

import pytest

pytest.importorskip("playwright")
import requests
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

OUTPUT_DIR = Path("D:/AE-Work/test_douyin")


async def extract_video_from_page(page):
    await asyncio.sleep(3)

    result = await page.evaluate("""
        () => {
            const scripts = document.querySelectorAll('script');
            for (const s of scripts) {
                const txt = s.textContent || '';
                if (txt.includes('play_addr') || txt.includes('video')) {
                    return txt.substring(0, 5000);
                }
            }
            return null;
        }
    """)

    if result:
        print("  [脚本内容] 找到包含video的脚本")
        return result

    result = await page.evaluate("""
        () => {
            if (window.__INITIAL_STATE__) {
                return JSON.stringify(window.__INITIAL_STATE__).substring(0, 10000);
            }
            if (window._SSR_HYDRATED_DATA) {
                return JSON.stringify(window._SSR_HYDRATED_DATA).substring(0, 10000);
            }
            return null;
        }
    """)

    if result:
        print("  [页面数据] 找到初始状态数据")
        return result

    return None


def find_video_urls(html_content):
    urls = []

    patterns = [
        r'"play_addr"[^}]*?"url_list"\s*:\s*\["([^"]+)"',
        r'"src"[^,}]*?"http[^"]+mp4[^"]*"',
        r'https?://[^"\s]+\.mp4[^"\s]*',
        r'"download_addr"[^}]*?"url_list"\s*:\s*\["([^"]+)"',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, html_content)
        for m in matches:
            url = m if m.startswith("http") else None
            if url and url not in urls:
                urls.append(url)

    return urls


async def main():
    print("=" * 60)
    print("  抖音视频下载测试 (页面数据提取)")
    print("=" * 60)
    print()

    video_url = "https://www.douyin.com/video/7562348910123"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Linux; Android 10; SM-G981B) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Mobile Safari/537.36"
            ),
            viewport={"width": 390, "height": 844},
            is_mobile=True,
        )

        cookie_file = "D:/AE-Work/cookies/douyin_cookies.txt"
        if os.path.exists(cookie_file):
            cookies = []
            with open(cookie_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("#") or not line:
                        continue
                    parts = line.split("\t")
                    if len(parts) >= 7:
                        cookies.append({
                            "domain": parts[0],
                            "path": parts[2],
                            "secure": parts[3] == "TRUE",
                            "expires": int(parts[4]) if parts[4].isdigit() else -1,
                            "name": parts[5],
                            "value": parts[6],
                        })
            await context.add_cookies(cookies)
            print(f"  已加载 {len(cookies)} 条cookies")

        page = await context.new_page()

        print(f"  访问视频页面 (移动端UA): {video_url}")
        try:
            await page.goto(video_url, wait_until="domcontentloaded", timeout=30000)
        except PlaywrightTimeoutError:
            pass

        await asyncio.sleep(5)

        print(f"  页面标题: {await page.title()}")
        print(f"  当前URL: {page.url}")

        page_data = await extract_video_from_page(page)
        html = await page.content()

        all_urls = []
        if page_data:
            urls = find_video_urls(page_data)
            all_urls.extend(urls)

        urls = find_video_urls(html)
        all_urls.extend(urls)

        all_urls = list(dict.fromkeys(all_urls))

        print()
        print(f"  找到 {len(all_urls)} 个视频URL候选:")
        for i, url in enumerate(all_urls[:10]):
            print(f"    {i+1}. {url[:100]}...")

        video_download_url = None
        for url in all_urls:
            if ".mp4" in url:
                video_download_url = url
                break

        if video_download_url:
            print()
            print("  ✓ 找到视频下载地址:")
            print(f"    {video_download_url[:120]}...")
            print()

            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            output_path = OUTPUT_DIR / "test_douyin_video.mp4"

            print("  开始下载...")
            headers = {
                "User-Agent": "Mozilla/5.0 (Linux; Android 10; SM-G981B) AppleWebKit/537.36",
                "Referer": "https://www.douyin.com/",
            }
            resp = requests.get(video_download_url, headers=headers, stream=True, timeout=120)

            if resp.status_code == 200:
                with open(output_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=64*1024):
                        f.write(chunk)
                size = os.path.getsize(output_path)
                print(f"  ✓ 下载完成: {output_path}")
                print(f"    文件大小: {size/1024/1024:.2f} MB")
            else:
                print(f"  ✗ 下载失败: HTTP {resp.status_code}")
        else:
            print()
            print("  ✗ 未找到视频下载地址")
            print()
            print("  尝试使用分享链接方式...")

            share_url = video_url.replace("www.douyin.com/video/", "v.douyin.com/")
            print(f"  分享链接: {share_url}")

        await browser.close()

    print()
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
