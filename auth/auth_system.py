#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用户权限系统
============

提供基于 JWT (JSON Web Token) 的认证与授权能力。

功能:
- 用户注册 / 登录 / 登出
- JWT 访问令牌 (access_token) + 刷新令牌 (refresh_token)
- 基于角色的访问控制 (RBAC): admin / operator / viewer
- 权限粒度控制 (permissions)
- 密码哈希存储 (PBKDF2-HMAC-SHA256)
- 令牌黑名单 (撤销已签发但未过期的令牌)
- 用户管理 API (admin 可增删改查用户)
- 操作审计日志
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

try:
    from logger import get_logger
    _logger = get_logger("auth")
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    _logger = logging.getLogger("auth")


# ============================================================================
# 常量与枚举
# ============================================================================

class Role(str, Enum):
    """用户角色"""
    ADMIN = "admin"        # 管理员：所有权限
    OPERATOR = "operator"  # 操作员：可执行任务、修改项目
    VIEWER = "viewer"      # 访客：只读


class Permission(str, Enum):
    """权限粒度"""
    # 任务相关
    TASK_SUBMIT = "task:submit"
    TASK_CANCEL = "task:cancel"
    TASK_VIEW = "task:view"
    # 项目相关
    PROJECT_CREATE = "project:create"
    PROJECT_UPDATE = "project:update"
    PROJECT_DELETE = "project:delete"
    PROJECT_VIEW = "project:view"
    # 系统相关
    SYSTEM_CONFIG = "system:config"
    USER_MANAGE = "user:manage"
    PLUGIN_MANAGE = "plugin:manage"
    # 渲染相关
    RENDER_SUBMIT = "render:submit"
    RENDER_VIEW = "render:view"


# 角色 -> 默认权限映射
ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.ADMIN: set(Permission),  # 所有权限
    Role.OPERATOR: {
        Permission.TASK_SUBMIT, Permission.TASK_CANCEL, Permission.TASK_VIEW,
        Permission.PROJECT_CREATE, Permission.PROJECT_UPDATE, Permission.PROJECT_VIEW,
        Permission.RENDER_SUBMIT, Permission.RENDER_VIEW,
    },
    Role.VIEWER: {
        Permission.TASK_VIEW, Permission.PROJECT_VIEW, Permission.RENDER_VIEW,
    },
}


# JWT 算法
JWT_ALG = "HS256"

# 默认令牌有效期 (秒)
DEFAULT_ACCESS_TOKEN_TTL = 3600       # 1 小时
DEFAULT_REFRESH_TOKEN_TTL = 7 * 86400  # 7 天

_WEAK_SECRET_KEY = "ae-knowledge-vault-secret-key-please-change-in-production"

MIN_SECRET_KEY_LENGTH = 32

def _resolve_secret_key(explicit: str | None = None) -> str:
    key = explicit or os.environ.get("AE_VAULT_SECRET_KEY", "")
    if not key:
        key = _WEAK_SECRET_KEY
        env = os.environ.get("AEK_ENVIRONMENT", "development").lower()
        if env == "production":
            raise RuntimeError(
                "生产环境必须设置 AE_VAULT_SECRET_KEY 环境变量，不得使用默认密钥"
            )
        _logger.warning(
            "⚠️  使用默认 JWT 密钥！仅限开发环境。生产环境请设置 AE_VAULT_SECRET_KEY。"
        )
    elif len(key.encode("utf-8")) < MIN_SECRET_KEY_LENGTH:
        raise ValueError(
            f"AE_VAULT_SECRET_KEY 至少需要 {MIN_SECRET_KEY_LENGTH} 字节"
        )
    return key


# ============================================================================
# 工具函数: 密码哈希
# ============================================================================

def hash_password(password: str, salt: str | None = None) -> str:
    """哈希密码 (PBKDF2-HMAC-SHA256)

    Args:
        password: 明文密码
        salt: 盐值 (None 则随机生成)

    Returns:
        格式: "pbkdf2_sha256$<iterations>$<salt>$<hash_hex>"
    """
    if salt is None:
        salt = secrets.token_hex(16)
    iterations = 100000
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations)
    return f"pbkdf2_sha256${iterations}${salt}${dk.hex()}"


def verify_password(password: str, hashed: str) -> bool:
    """验证密码

    Args:
        password: 明文密码
        hashed: hash_password 返回的字符串

    Returns:
        是否匹配
    """
    try:
        parts = hashed.split("$")
        if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
            return False
        iterations = int(parts[1])
        salt = parts[2]
        expected = parts[3]
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations)
        return hmac.compare_digest(dk.hex(), expected)
    except Exception:
        return False


# ============================================================================
# JWT 编解码 (纯 Python 实现, 不依赖 PyJWT)
# ============================================================================

def _b64url_encode(data: bytes) -> str:
    """Base64 URL-safe 编码"""
    import base64
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    """Base64 URL-safe 解码"""
    import base64
    padding = 4 - (len(data) % 4)
    if padding != 4:
        data = data + "=" * padding
    return base64.urlsafe_b64decode(data)


def _hmac_sha256(message: bytes, secret: bytes) -> bytes:
    """HMAC-SHA256"""
    return hmac.new(secret, message, hashlib.sha256).digest()


def jwt_encode(payload: dict[str, Any], secret: str = _WEAK_SECRET_KEY,
               algorithm: str = JWT_ALG) -> str:
    """编码 JWT

    Args:
        payload: JWT 载荷
        secret: 签名密钥
        algorithm: 算法 (目前仅支持 HS256)

    Returns:
        JWT 字符串: "header.payload.signature"
    """
    if algorithm != JWT_ALG:
        raise ValueError(f"不支持的算法: {algorithm}, 仅支持 {JWT_ALG}")

    header = {"alg": algorithm, "typ": "JWT"}
    header_json = json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")

    header_b64 = _b64url_encode(header_json)
    payload_b64 = _b64url_encode(payload_json)
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    signature = _hmac_sha256(signing_input, secret.encode("utf-8"))
    signature_b64 = _b64url_encode(signature)

    return f"{header_b64}.{payload_b64}.{signature_b64}"


def jwt_decode(token: str, secret: str = _WEAK_SECRET_KEY,
               verify_exp: bool = True) -> dict[str, Any]:
    """解码并验证 JWT

    Args:
        token: JWT 字符串
        secret: 签名密钥
        verify_exp: 是否验证过期时间

    Returns:
        payload 字典

    Raises:
        ValueError: 令牌无效、签名错误、已过期
    """
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("无效的 JWT 格式")

    header_b64, payload_b64, signature_b64 = parts

    # 验证签名
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    expected_signature = _hmac_sha256(signing_input, secret.encode("utf-8"))
    actual_signature = _b64url_decode(signature_b64)
    if not hmac.compare_digest(expected_signature, actual_signature):
        raise ValueError("JWT 签名验证失败")

    # 解析 header
    try:
        header = json.loads(_b64url_decode(header_b64))
    except Exception:
        raise ValueError("JWT header 解析失败")
    if header.get("alg") != JWT_ALG:
        raise ValueError(f"不支持的算法: {header.get('alg')}")

    # 解析 payload
    try:
        payload = json.loads(_b64url_decode(payload_b64))
    except Exception:
        raise ValueError("JWT payload 解析失败")

    # 验证过期时间
    if verify_exp and "exp" in payload:
        if time.time() > payload["exp"]:
            raise ValueError("JWT 已过期")

    return payload


# ============================================================================
# 数据模型
# ============================================================================

@dataclass
class User:
    """用户"""
    user_id: str
    username: str
    email: str
    password_hash: str
    role: Role = Role.VIEWER
    permissions: set[Permission] = field(default_factory=set)
    is_active: bool = True
    created_at: float = field(default_factory=time.time)
    last_login: float | None = None
    last_login_ip: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典 (不含密码)"""
        d = asdict(self)
        d["role"] = self.role.value
        d["permissions"] = [p.value for p in self.permissions]
        d.pop("password_hash", None)
        return d

    def has_permission(self, permission: Permission) -> bool:
        """检查是否拥有权限"""
        if not self.is_active:
            return False
        return permission in self.permissions or permission in ROLE_PERMISSIONS[self.role]

    def has_any_permission(self, *permissions: Permission) -> bool:
        """检查是否拥有任意一个权限"""
        return any(self.has_permission(p) for p in permissions)


@dataclass
class TokenPair:
    """令牌对"""
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = DEFAULT_ACCESS_TOKEN_TTL
    user_id: str = ""
    username: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_type": self.token_type,
            "expires_in": self.expires_in,
            "user_id": self.user_id,
            "username": self.username,
        }


@dataclass
class AuditLogEntry:
    """审计日志条目"""
    log_id: str
    user_id: str
    username: str
    action: str
    resource: str
    timestamp: float
    ip_address: str | None = None
    user_agent: str | None = None
    success: bool = True
    details: dict[str, Any] = field(default_factory=dict)


# ============================================================================
# 用户存储 (内存, 可扩展为数据库)
# ============================================================================

class UserStore:
    """用户存储"""

    def __init__(self):
        self._users: dict[str, User] = {}  # user_id -> User
        self._username_index: dict[str, str] = {}  # username (lower) -> user_id
        self._email_index: dict[str, str] = {}  # email (lower) -> user_id
        self._lock = __import__("threading").RLock()

    def add(self, user: User) -> None:
        with self._lock:
            if user.username.lower() in self._username_index:
                raise ValueError(f"用户名已存在: {user.username}")
            if user.email.lower() in self._email_index:
                raise ValueError(f"邮箱已存在: {user.email}")
            self._users[user.user_id] = user
            self._username_index[user.username.lower()] = user.user_id
            self._email_index[user.email.lower()] = user.user_id

    def get(self, user_id: str) -> User | None:
        with self._lock:
            return self._users.get(user_id)

    def get_by_username(self, username: str) -> User | None:
        with self._lock:
            uid = self._username_index.get(username.lower())
            return self._users.get(uid) if uid else None

    def get_by_email(self, email: str) -> User | None:
        with self._lock:
            uid = self._email_index.get(email.lower())
            return self._users.get(uid) if uid else None

    def update(self, user_id: str, updates: dict[str, Any]) -> User:
        with self._lock:
            user = self._users.get(user_id)
            if not user:
                raise KeyError(f"用户不存在: {user_id}")

            if "username" in updates and updates["username"] != user.username:
                new_username = updates["username"]
                if new_username.lower() in self._username_index:
                    raise ValueError(f"用户名已存在: {new_username}")
                del self._username_index[user.username.lower()]
                user.username = new_username
                self._username_index[new_username.lower()] = user_id

            if "email" in updates and updates["email"] != user.email:
                new_email = updates["email"]
                if new_email.lower() in self._email_index:
                    raise ValueError(f"邮箱已存在: {new_email}")
                del self._email_index[user.email.lower()]
                user.email = new_email
                self._email_index[new_email.lower()] = user_id

            if "password_hash" in updates:
                user.password_hash = updates["password_hash"]

            if "role" in updates:
                user.role = Role(updates["role"]) if isinstance(updates["role"], str) else updates["role"]

            if "is_active" in updates:
                user.is_active = bool(updates["is_active"])

            if "permissions" in updates:
                perms = updates["permissions"]
                if isinstance(perms, (list, set)):
                    user.permissions = {
                        Permission(p) if isinstance(p, str) else p for p in perms
                    }

            if "metadata" in updates:
                user.metadata.update(updates["metadata"])

            return user

    def delete(self, user_id: str) -> bool:
        with self._lock:
            user = self._users.pop(user_id, None)
            if not user:
                return False
            self._username_index.pop(user.username.lower(), None)
            self._email_index.pop(user.email.lower(), None)
            return True

    def list_users(self) -> list[User]:
        with self._lock:
            return list(self._users.values())

    def count(self) -> int:
        with self._lock:
            return len(self._users)


# ============================================================================
# 令牌黑名单
# ============================================================================

class TokenBlacklist:
    """令牌黑名单 (撤销已签发但未过期的令牌)"""

    def __init__(self, cleanup_interval: float = 300.0):
        self._blacklist: dict[str, float] = {}  # token_id -> exp
        self._lock = __import__("threading").RLock()
        self._cleanup_interval = cleanup_interval
        self._last_cleanup = time.time()

    def revoke(self, token_id: str, exp: float) -> None:
        """撤销令牌"""
        with self._lock:
            self._blacklist[token_id] = exp
            self._maybe_cleanup()

    def is_revoked(self, token_id: str) -> bool:
        """检查令牌是否已撤销"""
        with self._lock:
            return token_id in self._blacklist

    def _maybe_cleanup(self) -> None:
        """清理过期条目"""
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return
        expired = [tid for tid, exp in self._blacklist.items() if exp < now]
        for tid in expired:
            del self._blacklist[tid]
        self._last_cleanup = now

    def size(self) -> int:
        with self._lock:
            return len(self._blacklist)


# ============================================================================
# 审计日志
# ============================================================================

class AuditLogger:
    """审计日志记录器"""

    def __init__(self, max_entries: int = 10000):
        self._entries: list[AuditLogEntry] = []
        self._max_entries = max_entries
        self._lock = __import__("threading").RLock()

    def log(self, user_id: str, username: str, action: str, resource: str,
            success: bool = True, ip_address: str | None = None,
            user_agent: str | None = None, **details) -> str:
        """记录审计日志"""
        log_id = uuid.uuid4().hex[:12]
        entry = AuditLogEntry(
            log_id=log_id,
            user_id=user_id,
            username=username,
            action=action,
            resource=resource,
            timestamp=time.time(),
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            details=details,
        )
        with self._lock:
            self._entries.append(entry)
            if len(self._entries) > self._max_entries:
                self._entries = self._entries[-self._max_entries:]
        return log_id

    def list_entries(self, user_id: str | None = None, action: str | None = None,
                    limit: int = 100) -> list[AuditLogEntry]:
        with self._lock:
            entries = list(self._entries)
        if user_id:
            entries = [e for e in entries if e.user_id == user_id]
        if action:
            entries = [e for e in entries if e.action == action]
        return entries[-limit:]

    def count(self) -> int:
        with self._lock:
            return len(self._entries)


# ============================================================================
# 认证管理器
# ============================================================================

class AuthManager:
    """认证管理器

    整合用户存储、令牌签发/验证、黑名单、审计日志。
    """

    def __init__(self, secret_key: str = _WEAK_SECRET_KEY,
                 access_token_ttl: int = DEFAULT_ACCESS_TOKEN_TTL,
                 refresh_token_ttl: int = DEFAULT_REFRESH_TOKEN_TTL):
        self.secret_key = secret_key
        self.access_token_ttl = access_token_ttl
        self.refresh_token_ttl = refresh_token_ttl
        self.users = UserStore()
        self.blacklist = TokenBlacklist()
        self.audit = AuditLogger()
        self._init_default_users()

    def _init_default_users(self) -> None:
        """初始化默认管理员账户 (首次启动)

        安全策略：
        - admin 密码从 AEK_BOOTSTRAP_ADMIN_PASSWORD 环境变量读取，
          未设置时自动生成随机密码并打印到控制台（仅一次）。
        - operator / viewer 账户不再自动创建，需由管理员手动添加。
        - 密码绝不写入日志。
        """
        if self.users.count() == 0:
            bootstrap_pwd = os.environ.get("AEK_BOOTSTRAP_ADMIN_PASSWORD", "")
            generated = False
            if not bootstrap_pwd:
                bootstrap_pwd = secrets.token_urlsafe(24)
                generated = True

            admin = User(
                user_id=uuid.uuid4().hex[:12],
                username="admin",
                email="admin@ae-vault.local",
                password_hash=hash_password(bootstrap_pwd),
                role=Role.ADMIN,
                permissions=set(Permission),
            )
            self.users.add(admin)
            _logger.info("已创建默认管理员账户 (admin)")
            if generated:
                print("=" * 60)
                print("  首次启动：自动生成的管理员密码")
                print("  用户名: admin")
                print(f"  密码  : {bootstrap_pwd}")
                print("  请立即登录并修改密码！")
                print("  或设置 AEK_BOOTSTRAP_ADMIN_PASSWORD 环境变量。")
                print("=" * 60)

    # ==================== 用户管理 ====================

    def register_user(self, username: str, email: str, password: str,
                      role: Role = Role.VIEWER,
                      permissions: set[Permission] | None = None) -> User:
        """注册新用户

        Raises:
            ValueError: 用户名/邮箱已存在; 密码强度不足
        """
        if len(password) < 6:
            raise ValueError("密码长度至少 6 位")
        if len(username) < 3:
            raise ValueError("用户名长度至少 3 位")

        user = User(
            user_id=uuid.uuid4().hex[:12],
            username=username,
            email=email,
            password_hash=hash_password(password),
            role=role,
            permissions=permissions or ROLE_PERMISSIONS.get(role, set()),
        )
        self.users.add(user)
        self.audit.log(user.user_id, username, "register", "user",
                       details={"role": role.value})
        _logger.info(f"新用户注册: {username} (角色: {role.value})")
        return user

    def delete_user(self, user_id: str, operator: User | None = None) -> bool:
        """删除用户"""
        user = self.users.get(user_id)
        if not user:
            return False
        if user.username == "admin":
            raise ValueError("不能删除默认管理员账户")
        ok = self.users.delete(user_id)
        if ok:
            self.audit.log(
                operator.user_id if operator else "system",
                operator.username if operator else "system",
                "delete_user", f"user:{user.username}",
                details={"deleted_user_id": user_id},
            )
            _logger.info(f"用户已删除: {user.username}")
        return ok

    def update_user(self, user_id: str, updates: dict[str, Any],
                    operator: User | None = None) -> User:
        """更新用户信息"""
        user = self.users.update(user_id, updates)
        self.audit.log(
            operator.user_id if operator else "system",
            operator.username if operator else "system",
            "update_user", f"user:{user.username}",
            details={"fields": list(updates.keys())},
        )
        return user

    def change_password(self, user_id: str, old_password: str,
                        new_password: str) -> bool:
        """修改密码"""
        if len(new_password) < 6:
            raise ValueError("新密码长度至少 6 位")
        user = self.users.get(user_id)
        if not user:
            raise KeyError(f"用户不存在: {user_id}")
        if not verify_password(old_password, user.password_hash):
            raise ValueError("旧密码不正确")
        self.users.update(user_id, {"password_hash": hash_password(new_password)})
        self.audit.log(user_id, user.username, "change_password", "user")
        _logger.info(f"用户修改密码: {user.username}")
        return True

    # ==================== 认证 ====================

    def authenticate(self, username: str, password: str,
                     ip_address: str | None = None) -> tuple[User, TokenPair]:
        """用户认证 (登录)

        Returns:
            (user, token_pair)

        Raises:
            ValueError: 用户名或密码错误; 账户已禁用
        """
        user = self.users.get_by_username(username)
        if not user or not verify_password(password, user.password_hash):
            self.audit.log(
                user.user_id if user else "unknown",
                username,
                "login_failed", "auth",
                success=False,
                ip_address=ip_address,
            )
            raise ValueError("用户名或密码错误")

        if not user.is_active:
            self.audit.log(user.user_id, username, "login_disabled",
                           "auth", success=False, ip_address=ip_address)
            raise ValueError("账户已被禁用")

        # 更新登录信息
        self.users.update(user.user_id, {
            "last_login": time.time(),
            "last_login_ip": ip_address,
        })

        # 签发令牌
        token_pair = self._issue_token_pair(user)

        self.audit.log(user.user_id, username, "login", "auth",
                       ip_address=ip_address)
        _logger.info(f"用户登录: {username} (IP: {ip_address})")
        return user, token_pair

    def logout(self, token_id: str, exp: float, user_id: str,
               username: str) -> None:
        """登出 (撤销令牌)"""
        self.blacklist.revoke(token_id, exp)
        self.audit.log(user_id, username, "logout", "auth")
        _logger.info(f"用户登出: {username}")

    def refresh_token(self, refresh_token: str) -> TokenPair:
        """使用 refresh_token 换取新的 access_token

        Raises:
            ValueError: 令牌无效/已撤销/用户不存在
        """
        payload = jwt_decode(refresh_token, self.secret_key)
        if payload.get("type") != "refresh":
            raise ValueError("不是 refresh_token")

        token_id = payload.get("jti", "")
        if self.blacklist.is_revoked(token_id):
            raise ValueError("refresh_token 已被撤销")

        user_id = payload.get("sub", "")
        user = self.users.get(user_id)
        if not user or not user.is_active:
            raise ValueError("用户不存在或已禁用")

        return self._issue_token_pair(user)

    def _issue_token_pair(self, user: User) -> TokenPair:
        """签发访问令牌 + 刷新令牌"""
        now = time.time()
        access_token_id = uuid.uuid4().hex[:16]
        refresh_token_id = uuid.uuid4().hex[:16]

        access_payload = {
            "sub": user.user_id,
            "username": user.username,
            "role": user.role.value,
            "permissions": [p.value for p in user.permissions],
            "type": "access",
            "jti": access_token_id,
            "iat": int(now),
            "exp": int(now + self.access_token_ttl),
        }
        refresh_payload = {
            "sub": user.user_id,
            "username": user.username,
            "type": "refresh",
            "jti": refresh_token_id,
            "iat": int(now),
            "exp": int(now + self.refresh_token_ttl),
        }

        access_token = jwt_encode(access_payload, self.secret_key)
        refresh_token = jwt_encode(refresh_payload, self.secret_key)

        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=self.access_token_ttl,
            user_id=user.user_id,
            username=user.username,
        )

    # ==================== 令牌验证 ====================

    def verify_token(self, token: str) -> dict[str, Any]:
        """验证 access_token

        Returns:
            payload 字典

        Raises:
            ValueError: 令牌无效/已过期/已撤销
        """
        payload = jwt_decode(token, self.secret_key)
        if payload.get("type") != "access":
            raise ValueError("不是 access_token")

        token_id = payload.get("jti", "")
        if self.blacklist.is_revoked(token_id):
            raise ValueError("令牌已被撤销")

        user_id = payload.get("sub", "")
        user = self.users.get(user_id)
        if not user or not user.is_active:
            raise ValueError("用户不存在或已禁用")

        return payload

    def get_user_from_token(self, token: str) -> User | None:
        """从令牌中获取用户"""
        try:
            payload = self.verify_token(token)
            return self.users.get(payload.get("sub", ""))
        except Exception:
            return None

    # ==================== 权限检查 ====================

    def check_permission(self, token: str, permission: Permission) -> bool:
        """检查令牌对应的用户是否有指定权限"""
        user = self.get_user_from_token(token)
        if not user:
            return False
        return user.has_permission(permission)

    def require_permission(self, token: str, permission: Permission) -> dict[str, Any]:
        """要求令牌必须有指定权限, 否则抛出异常

        Returns:
            payload 字典

        Raises:
            PermissionError: 权限不足
            ValueError: 令牌无效
        """
        payload = self.verify_token(token)
        user = self.users.get(payload.get("sub", ""))
        if not user or not user.has_permission(permission):
            self.audit.log(
                payload.get("sub", "unknown"),
                payload.get("username", "unknown"),
                "permission_denied", permission.value,
                success=False,
            )
            raise PermissionError(f"权限不足: 需要 {permission.value}")
        return payload


# ============================================================================
# 单例
# ============================================================================

_auth_manager: AuthManager | None = None


def get_auth_manager(secret_key: str | None = None) -> AuthManager:
    """获取认证管理器单例"""
    global _auth_manager
    if _auth_manager is None:
        key = _resolve_secret_key(secret_key)
        _auth_manager = AuthManager(secret_key=key)
    return _auth_manager


# ============================================================================
# FastAPI 集成: 依赖注入
# ============================================================================

def create_fastapi_dependencies():
    """创建 FastAPI 依赖注入函数

    用法:
        deps = create_fastapi_dependencies()

        @app.post("/api/v1/tasks", dependencies=[Depends(deps.require(Permission.TASK_SUBMIT))])
        async def submit_task(...):
            ...
    """
    try:
        from fastapi import Depends, Header, HTTPException, status
        from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
    except ImportError:
        _logger.warning("FastAPI 未安装, 跳过依赖注入创建")
        return None

    security = HTTPBearer(auto_error=False)
    auth = get_auth_manager()

    def get_current_user(
        credentials: HTTPAuthorizationCredentials | None = Depends(security),
    ) -> User:
        """获取当前用户 (必须已认证)"""
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未提供认证令牌",
                headers={"WWW-Authenticate": "Bearer"},
            )
        try:
            user = auth.get_user_from_token(credentials.credentials)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="令牌无效或用户不存在",
                )
            return user
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e),
                headers={"WWW-Authenticate": "Bearer"},
            )

    def require(permission: Permission):
        """要求指定权限的依赖"""
        def _checker(user: User = Depends(get_current_user)) -> User:
            if not user.has_permission(permission):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"权限不足: 需要 {permission.value}",
                )
            return user
        return _checker

    def require_admin(user: User = Depends(get_current_user)) -> User:
        """要求管理员权限"""
        if user.role != Role.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="需要管理员权限",
            )
        return user

    def optional_user(
        credentials: HTTPAuthorizationCredentials | None = Depends(security),
    ) -> User | None:
        """可选的用户 (未认证返回 None)"""
        if not credentials:
            return None
        try:
            return auth.get_user_from_token(credentials.credentials)
        except Exception:
            return None

    return type("AuthDeps", (), {
        "get_current_user": get_current_user,
        "require": require,
        "require_admin": require_admin,
        "optional_user": optional_user,
        "auth": auth,
    })()


# ============================================================================
# 测试
# ============================================================================

def _run_tests():
    """运行测试"""
    print("=" * 70)
    print("  用户权限系统测试 (JWT 认证)")
    print("=" * 70)

    # 使用独立实例, 避免污染单例
    auth = AuthManager(secret_key="test-secret-key-for-testing-only")

    # ---------- 1. 密码哈希 ----------
    print("\n1. 密码哈希...")
    hashed = hash_password("mypassword")
    assert verify_password("mypassword", hashed), "密码验证失败"
    assert not verify_password("wrongpassword", hashed), "错误密码不应通过"
    print(f"  哈希格式: {hashed[:30]}...")
    print("  验证正确密码: OK")
    print("  拒绝错误密码: OK")

    # ---------- 2. JWT 编解码 ----------
    print("\n2. JWT 编解码...")
    payload = {"sub": "user123", "username": "test", "exp": int(time.time()) + 3600}
    token = jwt_encode(payload, "test-secret")
    decoded = jwt_decode(token, "test-secret")
    assert decoded["sub"] == "user123", "JWT 解码失败"
    assert decoded["username"] == "test"
    print(f"  令牌: {token[:40]}...")
    print(f"  解码: sub={decoded['sub']}, username={decoded['username']}")

    # 错误密钥应失败
    try:
        jwt_decode(token, "wrong-secret")
        assert False, "错误密钥应失败"
    except ValueError as e:
        assert "签名" in str(e)
        print("  错误密钥拒绝: OK")

    # 过期令牌应失败
    expired_payload = {"sub": "x", "exp": int(time.time()) - 100}
    expired_token = jwt_encode(expired_payload, "test-secret")
    try:
        jwt_decode(expired_token, "test-secret")
        assert False, "过期令牌应失败"
    except ValueError as e:
        assert "过期" in str(e)
        print("  过期令牌拒绝: OK")

    # ---------- 3. 默认用户 ----------
    print("\n3. 默认用户...")
    users = auth.users.list_users()
    assert len(users) == 3, f"应有 3 个默认用户, 实际 {len(users)}"
    admin = auth.users.get_by_username("admin")
    assert admin is not None
    assert admin.role == Role.ADMIN
    assert Permission.USER_MANAGE in admin.permissions
    print(f"  admin: role={admin.role.value}, perms={len(admin.permissions)}")
    print(f"  operator: role={auth.users.get_by_username('operator').role.value}")
    print(f"  viewer: role={auth.users.get_by_username('viewer').role.value}")

    # ---------- 4. 用户注册 ----------
    print("\n4. 用户注册...")
    new_user = auth.register_user("newuser", "new@ae-vault.local", "newpass123",
                                  role=Role.OPERATOR)
    assert new_user.username == "newuser"
    assert new_user.role == Role.OPERATOR
    print(f"  新用户: {new_user.username} ({new_user.role.value})")

    # 重复用户名应失败
    try:
        auth.register_user("newuser", "other@ae-vault.local", "pass123")
        assert False
    except ValueError:
        print("  重复用户名拒绝: OK")

    # 密码过短应失败
    try:
        auth.register_user("short", "short@ae-vault.local", "123")
        assert False
    except ValueError:
        print("  短密码拒绝: OK")

    # ---------- 5. 登录认证 ----------
    print("\n5. 登录认证...")
    user, tokens = auth.authenticate("admin", "admin123", ip_address="127.0.0.1")
    assert user.username == "admin"
    assert tokens.access_token
    assert tokens.refresh_token
    assert tokens.token_type == "Bearer"
    print(f"  登录成功: {user.username}")
    print(f"  access_token: {tokens.access_token[:40]}...")
    print(f"  refresh_token: {tokens.refresh_token[:40]}...")
    print(f"  expires_in: {tokens.expires_in}s")

    # 错误密码应失败
    try:
        auth.authenticate("admin", "wrongpassword")
        assert False
    except ValueError:
        print("  错误密码拒绝: OK")

    # 不存在的用户应失败
    try:
        auth.authenticate("nonexistent", "pass")
        assert False
    except ValueError:
        print("  不存在用户拒绝: OK")

    # ---------- 6. 令牌验证 ----------
    print("\n6. 令牌验证...")
    payload = auth.verify_token(tokens.access_token)
    assert payload["username"] == "admin"
    assert payload["role"] == "admin"
    assert payload["type"] == "access"
    print(f"  令牌验证: username={payload['username']}, role={payload['role']}")

    user_from_token = auth.get_user_from_token(tokens.access_token)
    assert user_from_token is not None
    assert user_from_token.username == "admin"
    print("  从令牌获取用户: OK")

    # ---------- 7. 刷新令牌 ----------
    print("\n7. 刷新令牌...")
    new_tokens = auth.refresh_token(tokens.refresh_token)
    assert new_tokens.access_token != tokens.access_token
    assert new_tokens.refresh_token != tokens.refresh_token
    print(f"  新 access_token: {new_tokens.access_token[:40]}...")
    print(f"  新 refresh_token: {new_tokens.refresh_token[:40]}...")

    # ---------- 8. 权限检查 ----------
    print("\n8. 权限检查...")
    assert admin.has_permission(Permission.USER_MANAGE), "admin 应有 USER_MANAGE"
    assert admin.has_permission(Permission.TASK_SUBMIT), "admin 应有 TASK_SUBMIT"
    print("  admin 有 USER_MANAGE: OK")
    print("  admin 有 TASK_SUBMIT: OK")

    viewer = auth.users.get_by_username("viewer")
    assert not viewer.has_permission(Permission.USER_MANAGE), "viewer 不应有 USER_MANAGE"
    assert viewer.has_permission(Permission.TASK_VIEW), "viewer 应有 TASK_VIEW"
    print("  viewer 无 USER_MANAGE: OK")
    print("  viewer 有 TASK_VIEW: OK")

    # require_permission
    payload = auth.require_permission(tokens.access_token, Permission.USER_MANAGE)
    assert payload["username"] == "admin"
    print("  require_permission (admin, USER_MANAGE): OK")

    viewer_tokens = auth.authenticate("viewer", "viewer123")[1]
    try:
        auth.require_permission(viewer_tokens.access_token, Permission.USER_MANAGE)
        assert False
    except PermissionError:
        print("  require_permission (viewer, USER_MANAGE) 拒绝: OK")

    # ---------- 9. 令牌黑名单 / 登出 ----------
    print("\n9. 令牌黑名单 / 登出...")
    payload = auth.verify_token(tokens.access_token)
    auth.logout(payload["jti"], payload["exp"], payload["sub"], payload["username"])
    print("  登出 (撤销令牌): OK")

    try:
        auth.verify_token(tokens.access_token)
        assert False, "已撤销令牌应失败"
    except ValueError as e:
        assert "撤销" in str(e)
        print("  已撤销令牌拒绝: OK")

    # ---------- 10. 修改密码 ----------
    print("\n10. 修改密码...")
    auth.change_password(new_user.user_id, "newpass123", "newpass456")
    # 旧密码应失败
    try:
        auth.authenticate("newuser", "newpass123")
        assert False
    except ValueError:
        print("  旧密码登录拒绝: OK")
    # 新密码应成功
    user, _ = auth.authenticate("newuser", "newpass456")
    assert user.username == "newuser"
    print("  新密码登录: OK")

    # ---------- 11. 用户管理 ----------
    print("\n11. 用户管理...")
    # 禁用用户
    auth.update_user(new_user.user_id, {"is_active": False})
    try:
        auth.authenticate("newuser", "newpass456")
        assert False, "禁用用户不应能登录"
    except ValueError as e:
        assert "禁用" in str(e)
        print("  禁用用户登录拒绝: OK")

    # 重新启用
    auth.update_user(new_user.user_id, {"is_active": True})
    user, _ = auth.authenticate("newuser", "newpass456")
    assert user.is_active
    print("  重新启用用户: OK")

    # 删除用户
    ok = auth.delete_user(new_user.user_id)
    assert ok
    assert auth.users.get(new_user.user_id) is None
    print("  删除用户: OK")

    # 不能删除 admin
    try:
        auth.delete_user(admin.user_id)
        assert False
    except ValueError:
        print("  删除 admin 拒绝: OK")

    # ---------- 12. 审计日志 ----------
    print("\n12. 审计日志...")
    entries = auth.audit.list_entries()
    assert len(entries) > 0, "应有审计日志"
    print(f"  审计日志条目: {auth.audit.count()}")
    login_entries = auth.audit.list_entries(action="login")
    print(f"  登录日志: {len(login_entries)}")
    failed_entries = auth.audit.list_entries(action="login_failed")
    print(f"  失败登录日志: {len(failed_entries)}")

    # ---------- 13. FastAPI 依赖注入 ----------
    print("\n13. FastAPI 依赖注入...")
    try:
        deps = create_fastapi_dependencies()
        if deps:
            print("  依赖注入创建: OK")
            print(f"  get_current_user: {deps.get_current_user}")
            print(f"  require_admin: {deps.require_admin}")
        else:
            print("  FastAPI 未安装, 跳过")
    except Exception as e:
        print(f"  依赖注入创建失败: {e}")

    # ---------- 14. 角色权限矩阵 ----------
    print("\n14. 角色权限矩阵...")
    for role in Role:
        perms = ROLE_PERMISSIONS[role]
        print(f"  {role.value}: {len(perms)} 项权限")
        for p in sorted(perms, key=lambda x: x.value):
            print(f"    - {p.value}")

    # ---------- 15. 统计 ----------
    print("\n15. 统计...")
    print(f"  用户总数: {auth.users.count()}")
    print(f"  审计日志: {auth.audit.count()}")
    print(f"  黑名单大小: {auth.blacklist.size()}")

    print("\n" + "=" * 70)
    print("  测试完成！")
    print("=" * 70)


if __name__ == "__main__":
    _run_tests()
