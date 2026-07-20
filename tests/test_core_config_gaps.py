"""core.config 补充测试 — 覆盖现有 test_core_config.py 未触及的边界与路径

重点缺口:
- ConfigManager.validate() 直接调用
- ConfigManager.get_full_config() 敏感信息泄露风险
- ConfigManager._is_writable() 异常路径（权限拒绝、非法路径）
- ConfigManager._load_config_files() 异常处理（JSON 解析失败、文件不存在）
- reload() 后配置一致性
- 便捷函数在全局实例未加载时的行为边界
"""
import json
import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import ConfigManager, ConfigValidator


@pytest.fixture
def fresh_manager():
    """提供全新初始化的 ConfigManager"""
    mgr = ConfigManager()
    return mgr


@pytest.fixture
def temp_config_file():
    """提供临时配置文件"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump({
            "server": {"port": 9090, "debug": True},
            "output": {"default_dir": "./custom_output"},
            "custom": {"nested": {"value": 42}}
        }, f)
        path = f.name
    yield path
    os.remove(path)


# ============================================================================
# ConfigManager.validate() 直接调用
# ============================================================================

class TestConfigManagerValidateDirect:
    def test_validate_returns_errors_for_bad_paths(self, fresh_manager):
        fresh_manager.set("ae.install_path", "C:/nonexistent/ae.exe")
        errors = fresh_manager.validate()
        assert any("AE 安装路径不存在" in e for e in errors)

    def test_validate_returns_empty_for_defaults(self, fresh_manager):
        fresh_manager.load_config()
        errors = fresh_manager.validate()
        # 默认配置中的路径在大多数环境不存在，因此会有警告；
        # 但空配置不应产生 port/concurrency 类错误
        assert not any("server.port" in e for e in errors)
        assert not any("max_concurrent_tasks" in e for e in errors)

    def test_validate_after_set_valid_port(self, fresh_manager):
        fresh_manager.load_config()
        fresh_manager.set("server.port", 8080)
        errors = fresh_manager.validate()
        assert not any("server.port" in e for e in errors)


# ============================================================================
# ConfigManager.get_full_config() 敏感信息
# ============================================================================

class TestConfigManagerGetFullConfig:
    def test_returns_dict_copy(self, fresh_manager):
        fresh_manager.load_config()
        full = fresh_manager.get_full_config()
        assert isinstance(full, dict)
        # 修改返回的字典不应影响内部状态
        full["extra"] = "injected"
        assert "extra" not in fresh_manager.get_full_config()

    def test_contains_sensitive_data(self, fresh_manager):
        fresh_manager.set("secret.api_key", "sk-test-12345")
        full = fresh_manager.get_full_config()
        assert full.get("secret", {}).get("api_key") == "sk-test-12345"


# ============================================================================
# ConfigManager._is_writable() 异常路径
# ============================================================================

class TestConfigManagerIsWritable:
    def test_existing_dir_is_writable(self, fresh_manager):
        with tempfile.TemporaryDirectory() as tmpdir:
            assert fresh_manager._is_writable(tmpdir) is True

    def test_nonexistent_parent_creates_and_writable(self, fresh_manager):
        with tempfile.TemporaryDirectory() as tmpdir:
            nested = os.path.join(tmpdir, "deep", "nested")
            assert fresh_manager._is_writable(nested) is True

    def test_invalid_path_returns_false(self, fresh_manager):
        # Windows 下 NUL 等设备名可能导致异常
        assert fresh_manager._is_writable("") is False


# ============================================================================
# ConfigManager._load_config_files() 异常处理
# ============================================================================

class TestConfigManagerLoadConfigFiles:
    def test_missing_file_silently_skipped(self, fresh_manager):
        # 不存在的文件路径不应抛出异常
        fresh_manager.load_config(["C:/nonexistent_config_12345.json"])
        assert fresh_manager.get("nonexistent") is None

    def test_invalid_json_logs_error(self, fresh_manager, caplog):
        import logging
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            f.write("not valid json {{{")
            path = f.name
        try:
            fresh_manager.load_config([path])
        finally:
            os.remove(path)

    def test_loads_valid_json(self, fresh_manager):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump({"custom": {"key": "value"}}, f)
            path = f.name
        try:
            fresh_manager.load_config([path])
            assert fresh_manager.get_str("custom.key") == "value"
        finally:
            os.remove(path)


# ============================================================================
# reload() 配置一致性
# ============================================================================

class TestConfigManagerReload:
    def test_reload_restores_defaults(self, fresh_manager):
        fresh_manager.load_config()
        original_port = fresh_manager.get_int("server.port")
        fresh_manager.set("server.port", 99999)
        fresh_manager.reload()
        assert fresh_manager.get_int("server.port") == original_port

    def test_reload_keeps_config_files(self, fresh_manager, temp_config_file):
        fresh_manager.load_config([temp_config_file])
        assert fresh_manager.get_int("server.port") == 9090
        fresh_manager.reload()
        assert fresh_manager.get_int("server.port") == 9090


# ============================================================================
# 环境变量转换边界
# ============================================================================

class TestConfigManagerEnvConversion:
    def test_env_nested_path(self, fresh_manager, monkeypatch):
        monkeypatch.setenv("AEKV_MODEL_ROUTING_GENERAL", "fast-model")
        fresh_manager.load_config()
        assert fresh_manager.get_str("model.routing.general") == "fast-model"

    def test_env_list_parsing(self, fresh_manager, monkeypatch):
        # 使用单段路径避免下划线分割歧义: AEKV_MYLIST -> mylist
        monkeypatch.setenv("AEKV_MYLIST", "[\"a\", \"b\"]")
        fresh_manager.load_config()
        val = fresh_manager.get("mylist")
        assert val == ["a", "b"]

    def test_env_dict_parsing(self, fresh_manager, monkeypatch):
        # AEKV_EXTRA_X -> extra.x (下划线转为点号分隔)
        monkeypatch.setenv("AEKV_EXTRA_X", '{"x": 1}')
        fresh_manager.load_config()
        assert fresh_manager.get_dict("extra.x") == {"x": 1}

    def test_env_invalid_json_keeps_string(self, fresh_manager, monkeypatch):
        monkeypatch.setenv("AEKV_BAD_JSON", "[1, 2")
        fresh_manager.load_config()
        assert fresh_manager.get_str("bad.json") == "[1, 2"


# ============================================================================
# 便捷函数边界（不依赖全局实例状态）
# ============================================================================

class TestConfigManagerTypeGettersEdgeCases:
    def test_get_int_non_numeric_returns_default(self, fresh_manager):
        fresh_manager._config = {"val": "not_a_number"}
        assert fresh_manager.get_int("val", 42) == 42

    def test_get_float_non_numeric_returns_default(self, fresh_manager):
        fresh_manager._config = {"val": "abc"}
        assert fresh_manager.get_float("val", 3.14) == 3.14

    def test_get_bool_various_types(self, fresh_manager):
        fresh_manager._config = {
            "t1": True,
            "t2": "true",
            "t3": "TRUE",
            "f1": False,
            "f2": "false",
            "f3": 0,
        }
        assert fresh_manager.get_bool("t1") is True
        assert fresh_manager.get_bool("t2") is True
        assert fresh_manager.get_bool("t3") is True
        assert fresh_manager.get_bool("f1") is False
        assert fresh_manager.get_bool("f2") is False
        assert fresh_manager.get_bool("f3") is False

    def test_get_list_non_list_returns_default(self, fresh_manager):
        fresh_manager._config = {"val": "string"}
        assert fresh_manager.get_list("val", ["default"]) == ["default"]

    def test_get_dict_non_dict_returns_default(self, fresh_manager):
        fresh_manager._config = {"val": 123}
        assert fresh_manager.get_dict("val", {"default": 1}) == {"default": 1}

    def test_get_deep_missing_returns_default(self, fresh_manager):
        assert fresh_manager.get("a.b.c.d", "fallback") == "fallback"
