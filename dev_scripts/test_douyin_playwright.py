import asyncio
import os
import re
from pathlib import Path

import pytest

pytest.importorskip("playwright")
import requests
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

OUTPUT_DIR = Path("D:/AE-Work/test_douyin")


async def get_douyin_video_url(page, video_url):
    try:
        await page.goto(video_url, wait_until="domcontentloaded", timeout=30000)
    except PlaywrightTimeoutError:
        pass

    await asyncio.sleep(5)

    try:
        await page.wait_for_selector("video", timeout=10000)
    except PlaywrightTimeoutError:
        pass

    video_src = await page.evaluate("""
        () => {
            const videos = document.querySelectorAll('video');
            for (const v of videos) {
                if (v.src) return v.src;
            }
            return null;
        }
    """)

    if video_src:
        return video_src

    page_content = await page.content()
    matches = re.findall(r'playAddr[":\s\w]*?"urlList"\s*:\s*\["([^"]+)"', page_content)
    if matches:
        return matches[0].encode().decode('unicode_escape')

    matches = re.findall(r'"play_addr"[^}]*?"url_list"\s*:\s*\["([^"]+)"', page_content)
    if matches:
        return matches[0].encode().decode('unicode_escape')

    return None


async def main():
    print("=" * 60)
    print("  抖音视频下载测试 (Playwright方式)")
    print("=" * 60)
    print()

    video_url = "https://www.douyin.com/video/7562348910123"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            storage_state="D:/AE-Work/cookies/douyin_state.json" if os.path.exists("D:/AE-Work/cookies/douyin_state.json") else None,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
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

        print(f"  访问视频页面: {video_url}")
        video_src = await get_douyin_video_url(page, video_url)

        if not video_src:
            print("  未找到视频src，尝试滚动页面...")
            await page.mouse.wheel(0, 500)
            await asyncio.sleep(3)
            video_src = await get_douyin_video_url(page, video_url)

        print()
        if video_src:
            print("  ✓ 找到视频地址:")
            print(f"    {video_src[:100]}..." if len(video_src) > 100 else f"    {video_src}")
            print()

            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            output_path = OUTPUT_DIR / "test_douyin_video.mp4"

            print("  开始下载...")
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://www.douyin.com/",
            }
            resp = requests.get(video_src, headers=headers, stream=True, timeout=120)

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
            print("  ✗ 未找到视频地址")
            print()
            print("  页面标题:", await page.title())
            print("  页面URL:", page.url)

        await browser.close()

    print()
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
