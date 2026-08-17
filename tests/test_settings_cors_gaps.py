"""
config/settings.py cors_origin_list 和 jwt_secret 未覆盖边缘情况测试
====================================================================
覆盖缺口：
  缺口A: 生产环境 CORS_ORIGINS=* → RuntimeError（错误消息含"生产环境禁止"）
  缺口B: 开发环境 CORS_ORIGINS=* → RuntimeWarning 且返回 ["*"]
  缺口C: 逗号分隔解析（含空格、空项、尾逗号）
  缺口D: 显式设置 AE_VAULT_SECRET_KEY → jwt_secret 完全等于该值（不触发随机生成）
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# ============================================================
# 路径设置
# ============================================================
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# --------------------------------------------------------------------
# sys.path 优先级强制（解决 puppet-automation/src "config" 与项目级 config 命名空间冲突）
#   规则 1：PROJECT_ROOT / web / tools 必须在最前面（保证 "import config" 取到项目级 config/ 包）
#   规则 2：puppet-automation/src 放到最后（保证内部 auth 等 import 可用但不抢 config 包）
#   规则 3：清除 sys.modules 缓存中所有已加载的 config / config.* 模块，让新路径生效
# --------------------------------------------------------------------
def _aekv_enforce_sys_path_priority():
    import sys as _sys
    from pathlib import Path as _Path

    _PROJECT_ROOT = str(_Path(__file__).resolve().parent.parent)
    _PUPPET_SRC = r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\puppet-automation\src"

    def _path_eq(p: str, target: str) -> bool:
        try:
            return _Path(p).resolve() == _Path(target).resolve()
        except Exception:
            return False

    # 清除所有 puppet/src 和 PROJECT_ROOT 的已存在重复项
    _remaining = [
        p for p in _sys.path
        if not _path_eq(p, _PUPPET_SRC) and not _path_eq(p, _PROJECT_ROOT)
    ]

    # 按优先级放置：1) PROJECT_ROOT  2) web  3) tools  4) 原剩余  5) puppet/src
    _head = [_PROJECT_ROOT]
    for _extra in (r"\web", r"\tools"):
        _candidate = _PROJECT_ROOT + _extra
        _exists = any(_path_eq(p, _candidate) for p in _remaining)
        if not _exists:
            _head.append(_candidate)

    _sys.path[:] = _head + _remaining + [_PUPPET_SRC]

    # 最后：清 config 缓存
    for _m in list(_sys.modules.keys()):
        if _m == "config" or _m.startswith("config."):
            del _sys.modules[_m]

_aekv_enforce_sys_path_priority()

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# --------------------------------------------------------------------
# 防跨测试 sys.modules 缓存污染（puppet-automation/src/config 命名空间冲突）
# 先清缓存，再让上方的 sys.path 规则生效，保证加载到本项目级的 config/ 包。
# --------------------------------------------------------------------
for _m in list(sys.modules.keys()):
    if _m == "config" or _m.startswith("config."):
        del sys.modules[_m]


# ====================================================================
# 辅助：构造 Settings 实例（使用 monkeypatch 设置环境变量）
# ====================================================================

def _fresh_settings_module():
    """
    重新载入 config.settings 模块以获得干净的 Settings 类。
    因为 settings.py 的 `__init__` 会读取 os.environ，我们只需
    用 monkeypatch 修改 environ 后直接 Settings() 即可，不需要
    reload 整个模块（除非实例化了 settings 单例）。
    """
    import importlib

    import config.settings  # noqa: F401

    mod_name = "config.settings"
    settings_module = sys.modules.get(mod_name)
    if settings_module is None:
        importlib.import_module(mod_name)
        settings_module = sys.modules[mod_name]
    # 保证最新
    importlib.reload(settings_module)
    return settings_module


# ====================================================================
# 缺口A: 生产环境 CORS_ORIGINS=* → RuntimeError
# ====================================================================

class TestGapA_ProductionCorsWildcardRejected:
    """
    缺口A: 设置 AEK_ENVIRONMENT=production，CORS_ORIGINS=*，
    settings.cors_origin_list 必须抛 RuntimeError（L84-L87），
    错误消息包含"生产环境禁止"。
    """

    def test_production_cors_wildcard_raises_runtime_error(self, monkeypatch):
        """生产环境 + CORS_ORIGINS=* 必须抛 RuntimeError。"""
        # 先设置 JWT Secret，避免 __init__ 阶段就炸
        monkeypatch.setenv("AEK_ENVIRONMENT", "production")
        monkeypatch.setenv("AE_VAULT_SECRET_KEY", "prod-safe-secret-1234567890-abcdef")
        monkeypatch.setenv("CORS_ORIGINS", "*")

        from config.settings import Settings

        s = Settings()
        # 确认 Settings 本身构造成功（因为 JWT key 已提供）
        assert s.is_production is True
        assert s.cors_origins == "*"

        # cors_origin_list property 必须抛出 RuntimeError
        with pytest.raises(RuntimeError) as exc_info:
            _ = s.cors_origin_list

        # 错误消息必须包含"生产环境禁止"
        assert "生产环境禁止" in str(exc_info.value), (
            f"错误消息中未找到'生产环境禁止': {exc_info.value}"
        )

    def test_production_cors_with_explicit_domains_ok(self, monkeypatch):
        """生产环境 + 显式域名白名单（非*）不应抛错。"""
        monkeypatch.setenv("AEK_ENVIRONMENT", "production")
        monkeypatch.setenv("AE_VAULT_SECRET_KEY", "prod-safe-secret-1234567890-abcdef")
        monkeypatch.setenv("CORS_ORIGINS", "https://app.example.com")

        from config.settings import Settings

        s = Settings()
        # 不应抛错，应返回显式配置列表
        result = s.cors_origin_list
        assert "https://app.example.com" in result


# ====================================================================
# 缺口B: 开发环境 CORS_ORIGINS=* → warning 且返回 ["*"]
# ====================================================================

class TestGapB_DevelopmentCorsWildcardWarning:
    """
    缺口B: 设置 AEK_ENVIRONMENT=development，CORS_ORIGINS=*，
    用 pytest.warns(RuntimeWarning) 捕获警告，返回值必须包含 ["*"]。
    """

    def test_development_cors_wildcard_emits_runtime_warning(self, monkeypatch):
        """开发环境 CORS_ORIGINS=* 必须发出 RuntimeWarning。"""
        monkeypatch.setenv("AEK_ENVIRONMENT", "development")
        # 清空 Secret，让 Settings 自己生成随机值（不影响此测试）
        monkeypatch.delenv("AE_VAULT_SECRET_KEY", raising=False)
        monkeypatch.setenv("CORS_ORIGINS", "*")

        from config.settings import Settings

        s = Settings()
        assert s.is_development is True
        assert s.cors_origins == "*"

        # cors_origin_list 必须发出 RuntimeWarning
        with pytest.warns(RuntimeWarning) as record:
            result = s.cors_origin_list

        # 确认至少有一条 Warning
        assert len(record) >= 1, "未捕获到 RuntimeWarning"
        # 警告消息中应当提到"开发环境"或"CORS_ORIGINS=*"
        warning_texts = [str(w.message) for w in record]
        joined = " | ".join(warning_texts)
        assert "CORS_ORIGINS" in joined or "本地调试" in joined or "开发环境" in joined, (
            f"警告中未找到预期提示: {joined}"
        )

    def test_development_cors_wildcard_returns_wildcard_list(self, monkeypatch):
        """开发环境 CORS_ORIGINS=* 返回值必须为 ["*"]。"""
        monkeypatch.setenv("AEK_ENVIRONMENT", "development")
        monkeypatch.setenv("AE_VAULT_SECRET_KEY", "dev-key-1234567890")
        monkeypatch.setenv("CORS_ORIGINS", "*")

        from config.settings import Settings

        s = Settings()

        with pytest.warns(RuntimeWarning):
            result = s.cors_origin_list

        # 返回列表必须包含 "*"
        assert isinstance(result, list)
        assert "*" in result
        # 通常长度为 1
        assert len(result) == 1


# ====================================================================
# 缺口C: 逗号分隔解析
# ====================================================================

class TestGapC_CommaSeparatedCorsParsing:
    """
    缺口C: CORS_ORIGINS="https://a.com, https://b.com,, https://c.com,"
    解析结果应为 ["https://a.com", "https://b.com", "https://c.com"]
    （去空、去前后空格、去尾逗号）。
    """

    def test_complex_comma_list_parsed_cleanly(self, monkeypatch):
        """复杂逗号列表：含前后空格、空项、尾逗号。"""
        monkeypatch.setenv("AEK_ENVIRONMENT", "development")
        monkeypatch.setenv("AE_VAULT_SECRET_KEY", "dev-key-1234567890")
        monkeypatch.setenv(
            "CORS_ORIGINS",
            "https://a.com, https://b.com,, https://c.com,",
        )

        from config.settings import Settings

        s = Settings()
        # 非 "*" 路径不会发 warning
        result = s.cors_origin_list

        expected = ["https://a.com", "https://b.com", "https://c.com"]
        assert result == expected, f"期望 {expected}，实际 {result}"

    def test_single_origin_no_comma(self, monkeypatch):
        """单个域名（无逗号）。"""
        monkeypatch.setenv("AEK_ENVIRONMENT", "development")
        monkeypatch.setenv("AE_VAULT_SECRET_KEY", "dev-key-1234567890")
        monkeypatch.setenv("CORS_ORIGINS", "https://only.example.com")

        from config.settings import Settings

        s = Settings()
        result = s.cors_origin_list
        assert result == ["https://only.example.com"]

    def test_only_commas_and_spaces_returns_empty(self, monkeypatch):
        """CORS_ORIGINS 全是逗号 + 空格 → 空列表。"""
        monkeypatch.setenv("AEK_ENVIRONMENT", "development")
        monkeypatch.setenv("AE_VAULT_SECRET_KEY", "dev-key-1234567890")
        monkeypatch.setenv("CORS_ORIGINS", ",,  , ,   ,")

        from config.settings import Settings

        s = Settings()
        result = s.cors_origin_list
        assert result == [], f"期望空列表，实际 {result}"

    def test_whitespace_stripped_from_each_origin(self, monkeypatch):
        """每个域名前后的空格都被 strip 掉。"""
        monkeypatch.setenv("AEK_ENVIRONMENT", "development")
        monkeypatch.setenv("AE_VAULT_SECRET_KEY", "dev-key-1234567890")
        monkeypatch.setenv(
            "CORS_ORIGINS",
            "   http://localhost:3000   ,   http://localhost:8080\t",
        )

        from config.settings import Settings

        s = Settings()
        result = s.cors_origin_list
        assert "http://localhost:3000" in result
        assert "http://localhost:8080" in result
        # 没有空格残留
        for item in result:
            assert item == item.strip(), f"条目未去空格: {item!r}"


# ====================================================================
# 缺口D: 显式设置 AE_VAULT_SECRET_KEY → 不生成随机值
# ====================================================================

class TestGapD_ExplicitJWTSecretNotRandomized:
    """
    缺口D: 显式设置 AE_VAULT_SECRET_KEY="my-explicit-secret-1234567890"，
    验证 settings.jwt_secret 完全等于该值（不触发随机生成）。
    """

    EXPLICIT_KEY = "my-explicit-secret-1234567890"

    def test_explicit_secret_used_as_is_development(self, monkeypatch):
        """开发环境：显式 key → jwt_secret 与 key 完全相等。"""
        monkeypatch.setenv("AEK_ENVIRONMENT", "development")
        monkeypatch.setenv("AE_VAULT_SECRET_KEY", self.EXPLICIT_KEY)

        from config.settings import Settings

        s = Settings()
        assert s.jwt_secret == self.EXPLICIT_KEY, (
            f"jwt_secret 不等于显式设置值。期望 {self.EXPLICIT_KEY!r}，实际 {s.jwt_secret!r}"
        )

    def test_explicit_secret_used_as_is_production(self, monkeypatch):
        """生产环境：显式 key → jwt_secret 与 key 完全相等（且不抛异常）。"""
        monkeypatch.setenv("AEK_ENVIRONMENT", "production")
        monkeypatch.setenv("AE_VAULT_SECRET_KEY", self.EXPLICIT_KEY)

        from config.settings import Settings

        s = Settings()
        assert s.jwt_secret == self.EXPLICIT_KEY

    def test_explicit_secret_does_not_emit_random_warning(self, monkeypatch):
        """显式设置 key 时，不应发出"建议设置 AE_VAULT_SECRET_KEY"的 RuntimeWarning。"""
        monkeypatch.setenv("AEK_ENVIRONMENT", "development")
        monkeypatch.setenv("AE_VAULT_SECRET_KEY", self.EXPLICIT_KEY)

        from config.settings import Settings

        import warnings

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            s = Settings()

        # 过滤出 RuntimeWarning，消息里提到 AE_VAULT_SECRET_KEY / 随机 / 临时
        relevant = [
            w for w in caught
            if issubclass(w.category, RuntimeWarning)
            and ("AE_VAULT_SECRET_KEY" in str(w.message)
                 or "随机" in str(w.message)
                 or "临时" in str(w.message))
        ]
        assert len(relevant) == 0, (
            f"显式设置 Secret 时不应再发出缺少 key 的警告，实际警告: "
            f"{[str(w.message) for w in relevant]}"
        )

    def test_two_instances_same_explicit_key_are_equal(self, monkeypatch):
        """
        显式 key 下，两次实例化必须得到相同的 jwt_secret。

        这与缺口A的"随机生成"形成对比：随机生成的两次应该不同，
        而显式 key 的两次必须完全相同。
        """
        monkeypatch.setenv("AEK_ENVIRONMENT", "development")
        monkeypatch.setenv("AE_VAULT_SECRET_KEY", self.EXPLICIT_KEY)

        from config.settings import Settings

        s1 = Settings()
        s2 = Settings()

        assert s1.jwt_secret == s2.jwt_secret == self.EXPLICIT_KEY


# ====================================================================
# 直接运行入口
# ====================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
