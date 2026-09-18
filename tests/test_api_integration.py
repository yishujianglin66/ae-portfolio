#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""API 集成测试脚本"""

import json
import urllib.error
import urllib.request

base = "http://127.0.0.1:8000"

def req(method, path, data=None, token=None):
    url = base + path
    body = json.dumps(data).encode() if data else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(r)
        resp_body = resp.read()
        return resp.status, json.loads(resp_body) if resp_body else {}
    except urllib.error.HTTPError as e:
        err_body = e.read()
        return e.code, json.loads(err_body) if err_body else {}


print("=" * 60)
print("  API 集成测试")
print("=" * 60)

# 1. 健康检查
print("\n--- 1. 健康检查 ---")
code, data = req("GET", "/health")
print(f"  Status: {code}")
print(f"  Services: {list(data.get('services', {}).keys())}")
assert code == 200

# 2. 登录 (admin)
print("\n--- 2. 登录 (admin) ---")
code, data = req("POST", "/api/v1/auth/login",
    {"username": "admin", "password": "admin123"})
print(f"  Status: {code}")
print(f"  User: {data.get('user', {}).get('username')}")
print(f"  Role: {data.get('user', {}).get('role')}")
print(f"  Token prefix: {data.get('access_token', '')[:30]}...")
assert code == 200
admin_token = data["access_token"]

# 3. 获取当前用户
print("\n--- 3. 获取当前用户 ---")
code, data = req("GET", "/api/v1/auth/me", token=admin_token)
print(f"  Status: {code}")
print(f"  Username: {data.get('username')}")
print(f"  Permissions: {len(data.get('permissions', []))}")
assert code == 200

# 4. 未认证访问受保护接口
print("\n--- 4. 未认证访问 ---")
code, data = req("GET", "/api/v1/auth/me")
print(f"  Status: {code}")
print(f"  Error: {data.get('detail', '')[:50]}")
assert code == 401

# 5. 权限不足测试 (viewer 访问用户管理)
print("\n--- 5. 权限测试 (viewer) ---")
code, vdata = req("POST", "/api/v1/auth/login",
    {"username": "viewer", "password": "viewer123"})
viewer_token = vdata["access_token"]
code, data = req("GET", "/api/v1/users", token=viewer_token)
print(f"  viewer 访问 /api/v1/users: Status={code}")
assert code == 403

# 6. admin 访问用户管理
print("\n--- 6. 用户列表 (admin) ---")
code, data = req("GET", "/api/v1/users", token=admin_token)
print(f"  Status: {code}")
print(f"  Users: {data.get('total')}")
for u in data.get("users", []):
    print(f"    - {u['username']} ({u['role']})")
assert code == 200

import time

_unique_user = f"testuser_{int(time.time())}"

# 7. 创建新用户
print("\n--- 7. 创建新用户 ---")
code, data = req("POST", "/api/v1/users", {
    "username": _unique_user,
    "email": f"{_unique_user}@ae-vault.local",
    "password": "test123456",
    "role": "operator"
}, token=admin_token)
print(f"  Status: {code}")
print(f"  Created: {data.get('created')}, user={data.get('user', {}).get('username')}")
assert code == 200

# 8. 修改密码
print("\n--- 8. 修改密码 ---")
code, tdata = req("POST", "/api/v1/auth/login",
    {"username": _unique_user, "password": "test123456"})
test_token = tdata["access_token"]
code, data = req("POST", "/api/v1/auth/change-password", {
    "old_password": "test123456",
    "new_password": "newpass123"
}, token=test_token)
print(f"  Status: {code}")
print(f"  Success: {data.get('success')}")
assert code == 200

# 9. 删除用户
print("\n--- 9. 删除用户 ---")
user_list = req("GET", "/api/v1/users", token=admin_token)[1]
test_uid = None
for u in user_list.get("users", []):
    if u["username"] == _unique_user:
        test_uid = u.get("user_id") or u.get("id")
        break
assert test_uid is not None
code, data = req("DELETE", f"/api/v1/users/{test_uid}", token=admin_token)
print(f"  Status: {code}")
print(f"  Deleted: {data.get('deleted')}")
assert code == 200

# 10. Prometheus 指标
print("\n--- 10. Prometheus /metrics ---")
url = base + "/metrics"
resp = urllib.request.urlopen(url)
text = resp.read().decode()
lines = text.strip().split("\n")
print(f"  行数: {len(lines)}")
metrics_found = []
for line in lines:
    if "http_requests_total" in line and "{" not in line:
        metrics_found.append(line.strip()[:80])
    if line.startswith("system_cpu_percent"):
        metrics_found.append(line.strip()[:80])
    if line.startswith("app_uptime"):
        metrics_found.append(line.strip()[:80])
for m in metrics_found[:5]:
    print(f"    {m}")
assert len(lines) > 10

# 11. 刷新令牌
print("\n--- 11. 刷新令牌 ---")
code, ldata = req("POST", "/api/v1/auth/login",
    {"username": "operator", "password": "operator123"})
refresh = ldata["refresh_token"]
code, data = req("POST", "/api/v1/auth/refresh", {"refresh_token": refresh})
print(f"  Status: {code}")
print(f"  New token prefix: {data.get('access_token', '')[:30]}...")
assert code == 200

# 12. 登出
print("\n--- 12. 登出 ---")
op_token = ldata["access_token"]
code, data = req("POST", "/api/v1/auth/logout", token=op_token)
print(f"  Status: {code}")
print(f"  Logged out: {data.get('logged_out')}")
assert code == 200

# 13. 告警列表
print("\n--- 13. 告警列表 ---")
code, data = req("GET", "/api/v1/alerts/active", token=admin_token)
print(f"  Status: {code}")
print(f"  活跃告警: {data.get('total')}")
assert code == 200

code, data = req("GET", "/api/v1/alerts/history", token=admin_token)
print(f"  告警历史: {data.get('total')}")
assert code == 200

# 14. 审计日志
print("\n--- 14. 审计日志 ---")
code, data = req("GET", "/api/v1/auth/audit-log?limit=5", token=admin_token)
print(f"  Status: {code}")
print(f"  条目数: {data.get('total')}")
for e in data.get("entries", [])[:3]:
    print(f"    - {e['action']} by {e['username']} ({e['success']})")
assert code == 200

# 15. 错误密码
print("\n--- 15. 错误密码登录 ---")
code, data = req("POST", "/api/v1/auth/login",
    {"username": "admin", "password": "wrongpassword"})
print(f"  Status: {code}")
print(f"  Error: {data.get('detail', '')}")
assert code == 401

print("\n" + "=" * 60)
print("  全部测试通过！")
print("=" * 60)
