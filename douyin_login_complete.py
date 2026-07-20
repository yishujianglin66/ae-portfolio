import asyncio
import os
from playwright.async_api import async_playwright

async def main():
    print("=== 抖音完整登录助手 ===")
    print("浏览器将启动，请完成扫码登录")
    print("登录后点击页面上的'我的'确认登录状态")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, channel="msedge")
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        await page.goto("https://www.douyin.com")
        
        logged_in = False
        for i in range(120):
            cookies = await context.cookies()
            has_sessionid = any(c.get("name") == "sessionid" for c in cookies)
            has_ttwid = any(c.get("name") == "ttwid" for c in cookies)
            
            if has_sessionid:
                print(f"检测到完整登录态! (sessionid={has_sessionid}, ttwid={has_ttwid})")
                logged_in = True
                break
            elif i % 10 == 0:
                print(f"等待登录... ({i}/120秒)")
            await asyncio.sleep(1)
        
        if not logged_in:
            print("超时：未检测到完整登录状态")
        
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
            flag = "TRUE"
            path = cookie.get("path", "/")
            secure = "TRUE" if cookie.get("secure") else "FALSE"
            expires = str(int(cookie.get("expires", 0)))
            name = cookie.get("name", "")
            value = cookie.get("value", "")
            
            if not name or not value or expires == "-1":
                continue
            
            lines.append(f"{domain}\t{flag}\t{path}\t{secure}\t{expires}\t{name}\t{value}")
            print(f"  {name}: {value[:30]}...")
        
        with open(cookie_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        
        print(f"\ncookies已保存到: {cookie_file}")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())