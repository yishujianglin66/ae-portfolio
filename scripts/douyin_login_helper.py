import asyncio
import os
import sys
from pathlib import Path

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

COOKIE_FILE = Path("D:/AE-Work/cookies/douyin_cookies.txt")
LOGIN_KEY_COOKIES = ["sessionid", "sid_guard"]
REQUIRED_COOKIES = ["sessionid"]


def save_cookies_netscape(cookies, output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Netscape HTTP Cookie File"]
    for cookie in cookies:
        domain = cookie.get("domain", "")
        if not domain:
            continue
        if not domain.startswith("."):
            domain = "." + domain
        flag = "TRUE"
        path = cookie.get("path", "/")
        secure = "TRUE" if cookie.get("secure") else "FALSE"
        expires = str(int(cookie.get("expires", 0)))
        name = cookie.get("name", "")
        value = cookie.get("value", "")
        if not name or not value or expires == "-1" or expires == "0":
            continue
        lines.append(f"{domain}\t{flag}\t{path}\t{secure}\t{expires}\t{name}\t{value}")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return len(lines) - 1


def check_login_state(cookies):
    cookie_names = {c.get("name", "") for c in cookies}
    return all(k in cookie_names for k in REQUIRED_COOKIES)


async def main():
    print("=" * 60)
    print("  抖音登录助手")
    print("=" * 60)
    print()
    print("  即将打开浏览器，请使用抖音APP扫码登录")
    print("  登录成功后请点击'我的'确认登录状态")
    print("  系统会自动检测 sessionid 并保存")
    print("  超时时间：180秒")
    print()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--start-maximized"],
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 768},
        )
        page = await context.new_page()

        try:
            await page.goto("https://www.douyin.com", wait_until="domcontentloaded", timeout=30000)
        except PlaywrightTimeoutError:
            print("  页面加载超时，继续等待登录...")

        print("  等待登录...")
        print()

        logged_in = False
        cookie_count = 0
        cookie_names_list = ""

        for i in range(180):
            cookies = await context.cookies()
            douyin_cookies = [c for c in cookies if "douyin" in c.get("domain", "").lower()]
            cookie_count = len(douyin_cookies)
            names = sorted({c.get("name", "") for c in douyin_cookies})
            cookie_names_list = ", ".join(names)

            if check_login_state(douyin_cookies):
                logged_in = True
                print(f"\r  ✓ 检测到完整登录状态！ (第 {i+1} 秒)", end="", flush=True)
                print()
                break

            if i % 5 == 0:
                print(f"\r  等待中... {i:3d}s | cookies: {cookie_count:2d} 条", end="", flush=True)

            await asyncio.sleep(1)

        print()
        print(f"  已获取的cookies: {cookie_names_list}")
        print()

        if not logged_in:
            print("  ⚠ 未检测到 sessionid（完整登录态）")
            print(f"  当前获取到 {cookie_count} 条抖音cookies")
            print("  将保存当前cookies（游客模式，部分视频可能无法下载）")
            print()
            print("  提示：请确保使用抖音APP扫码完成登录")
            print("        登录成功后刷新页面或点击'我的'")
            print()

        cookies = await context.cookies()
        douyin_cookies = [c for c in cookies if "douyin" in c.get("domain", "").lower()]

        saved = save_cookies_netscape(douyin_cookies, COOKIE_FILE)
        print(f"  ✓ 已保存 {saved} 条cookies到:")
        print(f"    {COOKIE_FILE}")
        print()

        if logged_in:
            print("  ✓ 登录成功！现在可以下载抖音视频了")
        else:
            print("  提示：当前为游客模式")
            print("        如需下载高清/无水印视频，请完成登录后重试")

        print()
        print("  10秒后关闭浏览器...")
        await asyncio.sleep(10)
        await browser.close()

    print("=" * 60)
    print("  完成")
    print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n  用户中断")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n  错误: {e}")
        sys.exit(1)
