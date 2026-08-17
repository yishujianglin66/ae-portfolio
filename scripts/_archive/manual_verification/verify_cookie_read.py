import pytest
pytest.importorskip("browser_cookie3")
import browser_cookie3
import requests

print("=== 测试读取Edge cookies ===")

try:
    cookies = browser_cookie3.edge(domain_name="douyin.com")
    cookie_dict = {c.name: c.value for c in cookies}
    print(f"成功读取到 {len(cookie_dict)} 条抖音cookies")
    print(f"Cookie名称: {list(cookie_dict.keys())}")
    
    test_url = "https://www.douyin.com"
    resp = requests.get(test_url, cookies=cookies, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    }, timeout=10)
    print(f"\n访问抖音返回状态码: {resp.status_code}")
    
except Exception as e:
    print(f"读取失败: {e}")
