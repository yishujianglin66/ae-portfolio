import asyncio
import os
from pathlib import Path
import pytest
pytest.importorskip("playwright")
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import requests

OUTPUT_DIR = Path("D:/AE-Work/test_douyin")


async def main():
    print("=" * 60)
    print("  抖音视频下载测试 (网络请求捕获)")
    print("=" * 60)
    print()

    video_url = "https://www.douyin.com/video/7562348910123"
    found_urls = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
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

        async def handle_request(request):
            url = request.url
            if any(x in url for x in [".mp4", "m3u8", "video", "play", "aweme/v1"]):
                if url not in found_urls:
                    found_urls.append(url)
                    if len(found_urls) <= 10:
                        print(f"  [捕获] {url[:80]}...")

        page.on("request", handle_request)

        print(f"  访问视频页面: {video_url}")
        try:
            await page.goto(video_url, wait_until="domcontentloaded", timeout=30000)
        except PlaywrightTimeoutError:
            pass

        await asyncio.sleep(8)

        print()
        print(f"  共捕获 {len(found_urls)} 个相关请求")
        print()

        video_download_url = None
        for url in found_urls:
            if ".mp4" in url and ("aweme.snssdk.com" in url or "douyinvod" in url or "v.douyin" in url):
                video_download_url = url
                break

        if not video_download_url:
            for url in found_urls:
                if "play" in url and "aweme" in url:
                    video_download_url = url
                    break

        if video_download_url:
            print(f"  ✓ 找到视频下载地址:")
            print(f"    {video_download_url}")
            print()

            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            output_path = OUTPUT_DIR / "test_douyin_video.mp4"

            print("  开始下载...")
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
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
                print(f"    响应: {resp.text[:200]}")
        else:
            print("  ✗ 未找到视频下载地址")
            print()
            for i, url in enumerate(found_urls[:20]):
                print(f"    {i+1}. {url[:100]}")

        await browser.close()

    print()
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
