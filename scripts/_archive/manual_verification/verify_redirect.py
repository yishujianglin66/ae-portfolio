import requests

url = "https://v.douyin.com/gA1N4UaxjPk/"

headers = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 12; SM-S908B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
}

print("请求短链接...")
resp = requests.head(url, headers=headers, allow_redirects=True, timeout=15)
print(f"最终URL: {resp.url}")
print(f"状态码: {resp.status_code}")
print()

import re

match = re.search(r'video/(\d+)', resp.url)
if match:
    print(f"视频ID: {match.group(1)}")
