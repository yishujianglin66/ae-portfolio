import asyncio
from playwright.async_api import async_playwright

async def main():
    print("=== 尝试连接Edge用户数据目录 ===")
    
    edge_user_data = r"C:\Users\Administrator\AppData\Local\Microsoft\Edge\User Data"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=edge_user_data,
            headless=False,
            channel="msedge",
            args=["--disable-features=msEdgeAutoLaunch"]
        )
        
        page = await browser.new_page()
        await page.goto("https://www.douyin.com")
        
        cookies = await page.context.cookies()
        print(f"\n成功获取到 {len(cookies)} 条cookies")
        
        for cookie in cookies:
            if cookie.get("domain") and ("douyin" in cookie["domain"] or "tiktok" in cookie["domain"]):
                print(f"  {cookie['name']}: {cookie['value'][:50]}...")
        
        await asyncio.sleep(5)
        await browser.close()

asyncio.run(main())
