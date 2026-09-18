import asyncio
import os

from playwright.async_api import async_playwright


async def main():
    print("=== 抖音登录助手 ===")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        await page.goto("https://www.douyin.com")
        
        print("等待登录...")
        for i in range(60):
            cookies = await context.cookies()
            has_ttwid = any(c.get("name") == "ttwid" for c in cookies)
            has_sessionid = any(c.get("name") == "sessionid" for c in cookies)
            if has_ttwid or has_sessionid:
                print(f"检测到登录cookies! (ttwid={has_ttwid}, sessionid={has_sessionid})")
                break
            await asyncio.sleep(1)
        else:
            print("超时：未检测到登录状态")
        
        cookies = await context.cookies()
        douyin_cookies = [c for c in cookies if "douyin" in c.get("domain", "").lower()]
        print(f"获取到 {len(douyin_cookies)} 条抖音cookies")
        
        cookie_file = "D:/AE-Work/cookies/douyin_cookies.txt"
        os.makedirs(os.path.dirname(cookie_file), exist_ok=True)
        
        lines = ["# Netscape HTTP Cookie File"]
        for cookie in douyin_cookies:
            domain = cookie.get("domain", "")
            if not domain.startswith("."):
                domain = "." + domain
            flag = "TRUE" if cookie.get("httpOnly") else "FALSE"
            path = cookie.get("path", "/")
            secure = "TRUE" if cookie.get("secure") else "FALSE"
            expires = str(int(cookie.get("expires", 0)))
            name = cookie.get("name", "")
            value = cookie.get("value", "")
            
            if not name or not value or expires == "-1":
                continue
            
            lines.append(f"{domain}\t{flag}\t{path}\t{secure}\t{expires}\t{name}\t{value}")
        
        with open(cookie_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        
        print(f"\ncookies已保存到: {cookie_file}")
        for line in lines:
            print(line)
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())