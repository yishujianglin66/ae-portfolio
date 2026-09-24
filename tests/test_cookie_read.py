import browser_cookie3
import requests


# ==== 脚本守卫 (2026-09-24) ====
# 本文件是**手工运行的脚本**（无 test 函数），不是 pytest 用例。模块级代码会
# 外连抖音发请求（requests.get，且携带 cookie）
# 被 pytest 收集/导入时这些副作用会立刻发生（显式传文件路径会绕过 python_files 模式）。
# 故被 import 时立刻失败；`python tests/test_cookie_read.py` 直接运行不受影响。
if __name__ != "__main__":
    raise ImportError(
        "这是脚本而非 pytest 用例，请用 `python tests/test_cookie_read.py` 直接运行；"
        "不要用 pytest 指定该文件路径。"
    )
# ==== /脚本守卫 ====
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
