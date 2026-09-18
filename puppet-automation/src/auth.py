"""
共享认证模块
=============

统一管理 MCP Token（静态配置）和用户 JWT Session Token（动态登录）的认证逻辑。

两种 token 均被接受：
1. MCP Token: 静态配置，用于 MCP 工具/脚本调用
2. User JWT: 登录后颁发的 session token，存储在内存中，用于前端 Dashboard

所有认证相关的模块（main.py 中间件、dashboard_routes.py 端点）均从此处导入。
"""
from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

# ============================================================
# 工具函数
# ============================================================

def hash_password(pwd: str, salt: str | None = None) -> str:
    """带随机盐的 SHA-256 密码哈希，格式：``<salt>$<digest>``。

    与纯 SHA-256 相比，相同密码在不同盐下产生不同哈希，
    防止彩虹表攻击。开发环境默认账号也在启动时用随机盐重新哈希。
    """
    salt = salt or secrets.token_hex(16)
    digest = hashlib.sha256(f"{salt}:{pwd}".encode("utf-8")).hexdigest()
    return f"{salt}${digest}"


def verify_password(pwd: str, stored: str) -> bool:
    """验证密码与存储哈希。

    支持两种格式：
    1. 带盐格式 ``<salt>$<digest>``（当前实现）
    2. 旧版纯 SHA-256 hexdigest（兼容历史数据）
    """
    if not isinstance(stored, str) or not stored:
        return False
    if "$" in stored:
        salt, _, digest = stored.partition("$")
        expected = hashlib.sha256(f"{salt}:{pwd}".encode("utf-8")).hexdigest()
        return secrets.compare_digest(expected, digest)
    # 旧版纯 SHA-256
    return secrets.compare_digest(hashlib.sha256(pwd.encode("utf-8")).hexdigest(), stored)


# ============================================================
# 用户数据（内存存储，开发环境默认账号）
# ============================================================

_USERS: dict[str, dict[str, Any]] = {}

if os.environ.get("AE_DEV_ACCOUNTS", "").strip() == "1":
    import warnings
    warnings.warn(
        "AE_DEV_ACCOUNTS=1: 已加载硬编码开发账号（admin/admin123 等），"
        "仅限本地开发，禁止在生产环境启用",
        stacklevel=2,
    )
    _USERS.update({
        "admin": {
            "user_id": "u-admin",
            "username": "admin",
            "email": "admin@ae.local",
            "password_hash": hash_password("admin123"),
            "role": "admin",
            "permissions": ["*"],
            "is_active": True,
            "created_at": "2026-01-01T00:00:00",
        },
        "operator": {
            "user_id": "u-operator",
            "username": "operator",
            "email": "operator@ae.local",
            "password_hash": hash_password("operator123"),
            "role": "operator",
            "permissions": [
                "projects:read",
                "projects:write",
                "execute",
                "effects:read",
                "styles:read",
            ],
            "is_active": True,
            "created_at": "2026-01-01T00:00:00",
        },
        "viewer": {
            "user_id": "u-viewer",
            "username": "viewer",
            "email": "viewer@ae.local",
            "password_hash": hash_password("viewer123"),
            "role": "viewer",
            "permissions": ["projects:read", "effects:read", "styles:read"],
            "is_active": True,
            "created_at": "2026-01-01T00:00:00",
        },
    })

# Session Token 存储（access_token 和 refresh_token）
_TOKEN_STORE: dict[str, dict[str, Any]] = {}


def verify_user(username: str, password: str) -> dict[str, Any] | None:
    """验证用户名密码，返回用户 dict 或 None。"""
    user = _USERS.get(username)
    if not user:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    if not user["is_active"]:
        return None
    return user


def make_user_response(user: dict[str, Any]) -> dict[str, Any]:
    """生成安全的用户响应（不含 password_hash）。"""
    return {
        "user_id": user["user_id"],
        "username": user["username"],
        "email": user["email"],
        "role": user["role"],
        "permissions": user["permissions"],
        "is_active": user["is_active"],
        "created_at": user["created_at"],
    }


def create_session_tokens(user: dict[str, Any]) -> dict[str, str]:
    """为用户创建 access_token 和 refresh_token，存入 _TOKEN_STORE。"""
    access_token = secrets.token_hex(32)
    refresh_token = secrets.token_hex(32)
    now = datetime.now(timezone.utc)

    _TOKEN_STORE[access_token] = {
        "user_id": user["user_id"],
        "username": user["username"],
        "expires_at": (now + timedelta(hours=24)).isoformat(),
        "role": user["role"],
        "is_refresh": False,
    }
    _TOKEN_STORE[refresh_token] = {
        "user_id": user["user_id"],
        "username": user["username"],
        "expires_at": (now + timedelta(days=7)).isoformat(),
        "role": user["role"],
        "is_refresh": True,
    }
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
    }


def verify_user_token(token: str, refresh: bool = False) -> dict[str, Any] | None:
    """验证用户 session token，返回 session dict 或 None。

    Args:
        token: Bearer token 值
        refresh: 如果为 True，只接受 refresh token；否则只接受 access token
    """
    session = _TOKEN_STORE.get(token)
    if not session:
        return None
    # 检查类型
    is_ref = session.get("is_refresh", False)
    if refresh and not is_ref:
        return None
    if not refresh and is_ref:
        return None
    # 检查过期
    try:
        exp = datetime.fromisoformat(session["expires_at"])
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > exp:
            _TOKEN_STORE.pop(token, None)
            return None
    except (ValueError, TypeError):
        return None
    return session


def revoke_token(token: str) -> None:
    """撤销 token（登出时调用）。"""
    _TOKEN_STORE.pop(token, None)


def get_user(username: str) -> dict[str, Any] | None:
    """按用户名获取用户。"""
    return _USERS.get(username)


def list_users() -> list[dict[str, Any]]:
    """列出所有用户（不包含 password_hash）。"""
    return [make_user_response(u) for u in _USERS.values()]


def create_user(
    username: str,
    password: str,
    email: str = "",
    role: str = "viewer",
    permissions: list[str] | None = None,
) -> dict[str, Any]:
    """创建新用户。"""
    if username in _USERS:
        raise ValueError(f"用户名 '{username}' 已存在")
    user = {
        "user_id": f"u-{username}",
        "username": username,
        "email": email or f"{username}@ae.local",
        "password_hash": hash_password(password),
        "role": role,
        "permissions": permissions or [],
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _USERS[username] = user
    return make_user_response(user)


def update_user(username: str, **kwargs) -> dict[str, Any] | None:
    """更新用户信息。"""
    user = _USERS.get(username)
    if not user:
        return None
    if "password" in kwargs:
        user["password_hash"] = hash_password(kwargs.pop("password"))
    for k, v in kwargs.items():
        if k in ("email", "role", "is_active", "permissions"):
            user[k] = v
    return make_user_response(user)


def delete_user(username: str) -> bool:
    """删除用户。返回是否删除成功。"""
    if username not in _USERS:
        return False
    # 撤销该用户的所有 token
    to_revoke = [t for t, s in _TOKEN_STORE.items() if s["username"] == username]
    for t in to_revoke:
        del _TOKEN_STORE[t]
    del _USERS[username]
    return True
