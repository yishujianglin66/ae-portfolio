import asyncio
import os
import re
from pathlib import Path
from playwright.async_api import async_playwright
import requests

video_url = "https://www.douyin.com/video/7651343231908753649"
output_dir = Path("D:/AE-Work/style_copy/zhuangzhuang")

async def main():
    print("=" * 60)
    print("  抖音视频下载 (有头浏览器模式)")
    print("=" * 60)
    print()
    print("  正在启动浏览器...")
    print("  请在浏览器中登录抖音，视频会自动播放")
    print()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=["--start-maximized"])
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 768},
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
                        try:
                            exp_int = int(parts[4])
                        except:
                            exp_int = -1
                        cookies.append({
                            "domain": parts[0],
                            "path": parts[2],
                            "secure": parts[3] == "TRUE",
                            "expires": exp_int,
                            "name": parts[5],
                            "value": parts[6],
                        })
            if cookies:
                await context.add_cookies(cookies)
                print(f"  已加载 {len(cookies)} 条cookies")

        page = await context.new_page()

        video_urls = []

        async def handle_response(response):
            url = response.url
            if ".mp4" in url and ("douyinvod" in url or "aweme" in url or "bytecdn" in url):
                if url not in video_urls:
                    video_urls.append(url)
                    print(f"  [捕获视频] {url[:80]}...")

        page.on("response", handle_response)

        print(f"  访问视频页面...")
        try:
            await page.goto(video_url, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            print(f"  页面加载: {e}")

        print(f"  页面标题: {await page.title()}")
        print()

        for i in range(30):
            await asyncio.sleep(1)
            if video_urls:
                print(f"\r  等待视频加载... {i}s ✓", end="", flush=True)
                break
            print(f"\r  等待视频加载... {i}s", end="", flush=True)

        print()
        print()

        if not video_urls:
            print("  未自动捕获到视频，尝试点击播放...")
            try:
                play_btn = page.locator("button[aria-label='播放']").first
                if await play_btn.is_visible():
                    await play_btn.click()
                    await asyncio.sleep(5)
            except:
                pass

            try:
                video_el = page.locator("video").first
                if await page.locator("video").count() > 0:
                    await page.locator("video").first.click()
                    await asyncio.sleep(5)
            except:
                pass

        print()
        print(f"  共捕获 {len(video_urls)} 个视频地址")

        if video_urls:
            best_url = video_urls[0]
            print(f"  使用: {best_url[:100]}...")
            print()

            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / "zhuangzhuang_puppet.mp4"

            print("  开始下载...")
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://www.douyin.com/",
            }
            resp = requests.get(best_url, headers=headers, stream=True, timeout=180)

            if resp.status_code == 200:
                total_size = 0
                with open(output_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=64*1024):
                        f.write(chunk)
                        total_size += len(chunk)
                        if total_size % (1024*1024) < 64*1024:
                            print(f"\r  已下载: {total_size/1024/1024:.1f} MB", end="", flush=True)

                print(f"\r  已下载: {total_size/1024/1024:.2f} MB")
                print(f"  ✓ 下载完成: {output_path}")
            else:
                print(f"  ✗ 下载失败: HTTP {resp.status_code}")
        else:
            print("  ✗ 未找到视频地址")
            print()
            print("  请手动在浏览器中播放视频，")
            print("  然后按回车继续...")
            input()

            print(f"  再次检查，共找到 {len(video_urls)} 个视频地址")
            if video_urls:
                print(f"  第一个: {video_urls[0][:100]}")

        print()
        print("  浏览器将在10秒后关闭...")
        await asyncio.sleep(10)
        await browser.close()

    print("=" * 60)

asyncio.run(main())
