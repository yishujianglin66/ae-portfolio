"""
puppet-automation/src/auth.py 模块高风险缺口测试
===============================================
覆盖用户验证、令牌生成、安全过滤、级联撤销等关键安全场景。
"""
from __future__ import annotations

import sys
import copy
import hashlib
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\puppet-automation\src")
import auth as puppet_auth


# ============================================================
# 测试隔离 fixture：保存并恢复全局 _USERS / _TOKEN_STORE
# ============================================================
@pytest.fixture(autouse=True)
def _isolate_global_state(monkeypatch):
    """每个测试前后隔离全局状态，防止测试间相互污染。"""
    original_users = copy.deepcopy(puppet_auth._USERS)
    original_tokens = copy.deepcopy(puppet_auth._TOKEN_STORE)

    monkeypatch.setattr(puppet_auth, "_USERS", copy.deepcopy(original_users))
    monkeypatch.setattr(puppet_auth, "_TOKEN_STORE", copy.deepcopy(original_tokens))

    yield

    monkeypatch.setattr(puppet_auth, "_USERS", original_users)
    monkeypatch.setattr(puppet_auth, "_TOKEN_STORE", original_tokens)


# ============================================================
# 缺口1: verify_user 验证函数
# ============================================================
class TestVerifyUser:
    """verify_user 用户名密码验证逻辑测试。"""

    def test_correct_credentials_returns_user(self):
        """正确用户名 + 正确密码 → 返回用户 dict。"""
        user = puppet_auth.verify_user("admin", "admin123")
        assert user is not None
        assert user["username"] == "admin"
        assert user["role"] == "admin"
        assert "password_hash" in user

    def test_correct_user_wrong_password_returns_none(self):
        """正确用户名 + 错误密码 → 返回 None。"""
        user = puppet_auth.verify_user("admin", "wrongpassword")
        assert user is None

    def test_nonexistent_username_returns_none(self):
        """不存在用户名 → 返回 None。"""
        user = puppet_auth.verify_user("nonexistent_user_xyz", "admin123")
        assert user is None

    def test_inactive_user_returns_none(self):
        """正确用户但 is_active=False → 返回 None。"""
        puppet_auth.update_user("operator", is_active=False)
        user = puppet_auth.verify_user("operator", "operator123")
        assert user is None


# ============================================================
# 缺口2: make_user_response 安全过滤
# ============================================================
class TestMakeUserResponse:
    """make_user_response 安全过滤（password_hash 不得泄露）。"""

    def test_response_no_password_hash(self):
        """确保返回 dict 中不含 password_hash 字段（安全关键）。"""
        raw_user = puppet_auth._USERS["admin"]
        assert "password_hash" in raw_user

        resp = puppet_auth.make_user_response(raw_user)
        assert "password_hash" not in resp

    def test_response_contains_required_fields(self):
        """确保包含 user_id/username/email/role/permissions/is_active/created_at 字段。"""
        raw_user = puppet_auth._USERS["viewer"]
        resp = puppet_auth.make_user_response(raw_user)

        required_fields = [
            "user_id", "username", "email", "role",
            "permissions", "is_active", "created_at",
        ]
        for field in required_fields:
            assert field in resp, f"响应缺少必填字段: {field}"

        assert resp["username"] == "viewer"
        assert resp["role"] == "viewer"
        assert isinstance(resp["permissions"], list)
        assert resp["is_active"] is True


# ============================================================
# 缺口3: create_session_tokens 令牌生成
# ============================================================
class TestCreateSessionTokens:
    """create_session_tokens 令牌结构与过期时间测试。"""

    def test_returns_access_and_refresh_tokens(self):
        """返回结构必须包含 access_token 和 refresh_token。"""
        user = puppet_auth._USERS["admin"]
        tokens = puppet_auth.create_session_tokens(user)

        assert "access_token" in tokens
        assert "refresh_token" in tokens

    def test_tokens_are_64_char_hex(self):
        """两个 token 都是 64 字符 hex（32 字节 = 64 hex 字符）。"""
        user = puppet_auth._USERS["admin"]
        tokens = puppet_auth.create_session_tokens(user)

        assert len(tokens["access_token"]) == 64
        assert len(tokens["refresh_token"]) == 64
        int(tokens["access_token"], 16)
        int(tokens["refresh_token"], 16)

    def test_tokens_recorded_in_store(self):
        """两个 token 必须被记录到 _TOKEN_STORE 中。"""
        user = puppet_auth._USERS["admin"]
        tokens = puppet_auth.create_session_tokens(user)

        assert tokens["access_token"] in puppet_auth._TOKEN_STORE
        assert tokens["refresh_token"] in puppet_auth._TOKEN_STORE

    def test_token_is_refresh_flags(self):
        """access_token 的 is_refresh=False，refresh_token 的 is_refresh=True。"""
        user = puppet_auth._USERS["admin"]
        tokens = puppet_auth.create_session_tokens(user)

        access_session = puppet_auth._TOKEN_STORE[tokens["access_token"]]
        refresh_session = puppet_auth._TOKEN_STORE[tokens["refresh_token"]]

        assert access_session["is_refresh"] is False
        assert refresh_session["is_refresh"] is True

    def test_token_expiration_approximate(self):
        """access_token 过期时间 ≈ 24h，refresh_token ≈ 7d（± 1 分钟）。"""
        user = puppet_auth._USERS["admin"]
        now = datetime.now(timezone.utc)
        tokens = puppet_auth.create_session_tokens(user)

        access_session = puppet_auth._TOKEN_STORE[tokens["access_token"]]
        refresh_session = puppet_auth._TOKEN_STORE[tokens["refresh_token"]]

        access_exp = datetime.fromisoformat(access_session["expires_at"])
        refresh_exp = datetime.fromisoformat(refresh_session["expires_at"])

        expected_access = now + timedelta(hours=24)
        expected_refresh = now + timedelta(days=7)

        access_diff = abs((access_exp - expected_access).total_seconds())
        refresh_diff = abs((refresh_exp - expected_refresh).total_seconds())

        assert access_diff <= 60, f"access_token 过期时间偏差过大: {access_diff}s"
        assert refresh_diff <= 60, f"refresh_token 过期时间偏差过大: {refresh_diff}s"

    def test_token_stores_user_info(self):
        """token 对应的 session 需保存正确的 user_id/username/role。"""
        user = puppet_auth._USERS["operator"]
        tokens = puppet_auth.create_session_tokens(user)

        session = puppet_auth._TOKEN_STORE[tokens["access_token"]]
        assert session["user_id"] == "u-operator"
        assert session["username"] == "operator"
        assert session["role"] == "operator"


# ============================================================
# 缺口4: verify_user_token 类型匹配 + 过期
# ============================================================
class TestVerifyUserToken:
    """verify_user_token 类型校验、过期处理、异常容错测试。"""

    def _create_tokens(self, username: str = "admin"):
        user = puppet_auth._USERS[username]
        return puppet_auth.create_session_tokens(user)

    def test_access_token_with_refresh_false_ok(self):
        """用 access_token 调 verify_user_token(refresh=False) → 返回 session。"""
        tokens = self._create_tokens()
        session = puppet_auth.verify_user_token(tokens["access_token"], refresh=False)
        assert session is not None
        assert session["username"] == "admin"
        assert session["is_refresh"] is False

    def test_access_token_with_refresh_true_rejected(self):
        """用 access_token 调 verify_user_token(refresh=True) → 返回 None（类型不匹配）。"""
        tokens = self._create_tokens()
        session = puppet_auth.verify_user_token(tokens["access_token"], refresh=True)
        assert session is None

    def test_refresh_token_with_refresh_false_rejected(self):
        """用 refresh_token 调 verify_user_token(refresh=False) → 返回 None（类型不匹配）。"""
        tokens = self._create_tokens()
        session = puppet_auth.verify_user_token(tokens["refresh_token"], refresh=False)
        assert session is None

    def test_refresh_token_with_refresh_true_ok(self):
        """用 refresh_token 调 verify_user_token(refresh=True) → 返回 session。"""
        tokens = self._create_tokens()
        session = puppet_auth.verify_user_token(tokens["refresh_token"], refresh=True)
        assert session is not None
        assert session["username"] == "admin"
        assert session["is_refresh"] is True

    def test_expired_token_returns_none_and_removed(self):
        """过期 token：设置 expires_at 为过去时间 → 返回 None 且 token 被从 _TOKEN_STORE 移除。"""
        tokens = self._create_tokens()
        token = tokens["access_token"]

        past_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        puppet_auth._TOKEN_STORE[token]["expires_at"] = past_time

        session = puppet_auth.verify_user_token(token, refresh=False)
        assert session is None
        assert token not in puppet_auth._TOKEN_STORE

    def test_invalid_expires_at_format_value_error(self):
        """非法 expires_at 格式（ValueError）：返回 None 不崩溃。"""
        tokens = self._create_tokens()
        token = tokens["access_token"]

        puppet_auth._TOKEN_STORE[token]["expires_at"] = "not-a-valid-datetime"

        session = puppet_auth.verify_user_token(token, refresh=False)
        assert session is None

    def test_invalid_expires_at_format_type_error(self):
        """非法 expires_at 格式（TypeError，None/数字等）：返回 None 不崩溃。"""
        tokens = self._create_tokens()
        token = tokens["access_token"]

        puppet_auth._TOKEN_STORE[token]["expires_at"] = 12345

        session = puppet_auth.verify_user_token(token, refresh=False)
        assert session is None

    def test_nonexistent_token_returns_none(self):
        """完全不存在的 token → 返回 None。"""
        fake = "a" * 64
        session = puppet_auth.verify_user_token(fake, refresh=False)
        assert session is None


# ============================================================
# 缺口5: revoke_token 撤销
# ============================================================
class TestRevokeToken:
    """revoke_token 撤销逻辑测试。"""

    def test_revoke_existing_token_removed(self):
        """撤销存在的 token：_TOKEN_STORE 中不再包含该 token。"""
        user = puppet_auth._USERS["admin"]
        tokens = puppet_auth.create_session_tokens(user)
        token = tokens["access_token"]

        assert token in puppet_auth._TOKEN_STORE

        puppet_auth.revoke_token(token)

        assert token not in puppet_auth._TOKEN_STORE

    def test_revoke_nonexistent_token_no_exception(self):
        """撤销不存在的 token：不抛异常。"""
        fake = "deadbeef" * 8
        try:
            puppet_auth.revoke_token(fake)
        except Exception as e:
            pytest.fail(f"撤销不存在的 token 时抛出异常: {type(e).__name__}: {e}")


# ============================================================
# 缺口6: create_user 用户创建
# ============================================================
class TestCreateUser:
    """create_user 创建逻辑与重复检查测试。"""

    def test_create_user_success_no_password_hash(self):
        """正常创建：返回 dict 无 password_hash，用户名存在。"""
        result = puppet_auth.create_user(
            username="newuser",
            password="newpass123",
            email="new@ae.local",
            role="operator",
            permissions=["projects:read"],
        )

        assert "password_hash" not in result
        assert result["username"] == "newuser"
        assert result["email"] == "new@ae.local"
        assert result["role"] == "operator"
        assert result["is_active"] is True
        assert result["permissions"] == ["projects:read"]

        assert "newuser" in puppet_auth._USERS
        raw = puppet_auth._USERS["newuser"]
        # 密码哈希为带盐格式 <salt>$<digest>，且可通过 verify_password 验证
        assert "$" in raw["password_hash"]
        assert puppet_auth.verify_password("newpass123", raw["password_hash"]) is True
        assert puppet_auth.verify_password("wrongpass", raw["password_hash"]) is False

    def test_create_duplicate_user_raises_value_error(self):
        """创建已存在用户名 → 抛 ValueError。"""
        with pytest.raises(ValueError):
            puppet_auth.create_user(
                username="admin",
                password="anotherpass",
            )


# ============================================================
# 缺口7: update_user 用户更新
# ============================================================
class TestUpdateUser:
    """update_user 字段更新逻辑测试。"""

    def test_update_password(self):
        """修改密码：verify_user 原密码失败，新密码成功。"""
        old_ok = puppet_auth.verify_user("viewer", "viewer123")
        assert old_ok is not None

        result = puppet_auth.update_user("viewer", password="new_viewer_pass")
        assert result is not None

        after_old = puppet_auth.verify_user("viewer", "viewer123")
        assert after_old is None

        after_new = puppet_auth.verify_user("viewer", "new_viewer_pass")
        assert after_new is not None
        assert after_new["username"] == "viewer"

    def test_update_email_role_is_active_permissions(self):
        """修改 email/role/is_active/permissions 各字段，正确更新。"""
        result = puppet_auth.update_user(
            "viewer",
            email="new_viewer_email@ae.local",
            role="operator",
            is_active=False,
            permissions=["a", "b", "c"],
        )

        assert result is not None
        assert result["email"] == "new_viewer_email@ae.local"
        assert result["role"] == "operator"
        assert result["is_active"] is False
        assert result["permissions"] == ["a", "b", "c"]

        raw = puppet_auth._USERS["viewer"]
        assert raw["email"] == "new_viewer_email@ae.local"
        assert raw["role"] == "operator"
        assert raw["is_active"] is False
        assert raw["permissions"] == ["a", "b", "c"]

    def test_update_nonexistent_user_returns_none(self):
        """更新不存在的用户名 → 返回 None。"""
        result = puppet_auth.update_user(
            "no_such_user_12345",
            email="should@not.work",
        )
        assert result is None


# ============================================================
# 缺口8: delete_user 用户删除 + token 级联撤销
# ============================================================
class TestDeleteUser:
    """delete_user 删除用户与级联 token 撤销测试。"""

    def test_delete_user_cascades_tokens(self):
        """
        创建用户并创建 session_tokens，然后 delete_user：
        1. _USERS 中用户已被删除
        2. 该用户的所有 session token 都被级联删除
        """
        puppet_auth.create_user("deleteme", password="del123", email="del@ae.local")
        assert "deleteme" in puppet_auth._USERS

        user = puppet_auth._USERS["deleteme"]
        tokens1 = puppet_auth.create_session_tokens(user)
        tokens2 = puppet_auth.create_session_tokens(user)

        all_user_tokens = [
            tokens1["access_token"], tokens1["refresh_token"],
            tokens2["access_token"], tokens2["refresh_token"],
        ]
        for t in all_user_tokens:
            assert t in puppet_auth._TOKEN_STORE

        ok = puppet_auth.delete_user("deleteme")
        assert ok is True

        assert "deleteme" not in puppet_auth._USERS

        for t in all_user_tokens:
            assert t not in puppet_auth._TOKEN_STORE, (
                f"删除用户后仍遗留有效 token: {t}"
            )

    def test_delete_nonexistent_user_returns_false(self):
        """删除不存在的用户 → 返回 False。"""
        result = puppet_auth.delete_user("no_such_user_delete_xyz")
        assert result is False


# ============================================================
# 缺口9: list_users / get_user
# ============================================================
class TestListAndGetUser:
    """list_users（对外，过滤哈希）与 get_user（内部，含哈希）测试。"""

    def test_list_users_no_password_hash(self):
        """list_users 返回的每个用户都无 password_hash。"""
        users = puppet_auth.list_users()
        assert len(users) >= 3

        for u in users:
            assert "password_hash" not in u, (
                f"list_users 中用户 {u.get('username')} 泄露了 password_hash"
            )

    def test_get_existing_user_contains_hash(self):
        """get_user(存在的) 返回完整用户 dict（含 password_hash，因为是内部函数）。"""
        user = puppet_auth.get_user("admin")
        assert user is not None
        assert "password_hash" in user
        assert user["username"] == "admin"
        assert user["role"] == "admin"

    def test_get_nonexistent_user_returns_none(self):
        """get_user(不存在的) → None。"""
        user = puppet_auth.get_user("this_user_does_not_exist_xyz")
        assert user is None
