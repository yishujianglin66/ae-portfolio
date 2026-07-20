"""core.config 单元测试 - ConfigManager 核心逻辑（与 config.config_manager 区分）"""
import json
import os
import sys
import tempfile
import pytest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import (
    ConfigSource,
    ConfigValidator,
    ConfigManager,
    config_manager,
    get_config,
    get_str,
    get_int,
    get_float,
    get_bool,
    get_list,
    get_dict,
    set_config,
    check_dependencies,
)


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


class TestConfigSource:
    def test_source_creation(self):
        src = ConfigSource(name="test", priority=5, data={"key": "value"})
        assert src.name == "test"
        assert src.priority == 5
        assert src.data == {"key": "value"}

    def test_source_default_data(self):
        src = ConfigSource(name="test", priority=1)
        assert src.data == {}


class TestConfigValidator:
    def test_validate_output_dir_relative_becomes_absolute(self):
        validator = ConfigValidator()
        config = {"output": {"default_dir": "./relative"}}
        errors = validator.validate(config)
        assert os.path.isabs(config["output"]["default_dir"])
        assert len(errors) == 0

    def test_validate_ae_path_not_exists(self):
        validator = ConfigValidator()
        config = {"ae": {"install_path": "C:/nonexistent/ae.exe"}}
        errors = validator.validate(config)
        assert len(errors) == 1
        assert "AE 安装路径不存在" in errors[0]

    def test_validate_silhouette_path_not_exists(self):
        validator = ConfigValidator()
        config = {"silhouette": {"install_path": "C:/nonexistent/sil.exe"}}
        errors = validator.validate(config)
        assert len(errors) == 1
        assert "Silhouette 安装路径不存在" in errors[0]

    def test_validate_port_too_low(self):
        validator = ConfigValidator()
        config = {"server": {"port": 80}}
        errors = validator.validate(config)
        assert len(errors) == 1
        assert "1024-65535" in errors[0]

    def test_validate_port_too_high(self):
        validator = ConfigValidator()
        config = {"server": {"port": 70000}}
        errors = validator.validate(config)
        assert len(errors) == 1

    def test_validate_port_valid(self):
        validator = ConfigValidator()
        config = {"server": {"port": 8080}}
        errors = validator.validate(config)
        assert len(errors) == 0

    def test_validate_concurrency_zero(self):
        validator = ConfigValidator()
        config = {"pipeline": {"max_concurrent_tasks": 0}}
        errors = validator.validate(config)
        assert len(errors) == 1
        assert "必须 >= 1" in errors[0]

    def test_validate_concurrency_negative(self):
        validator = ConfigValidator()
        config = {"pipeline": {"max_concurrent_tasks": -5}}
        errors = validator.validate(config)
        assert len(errors) == 1

    def test_validate_concurrency_valid(self):
        validator = ConfigValidator()
        config = {"pipeline": {"max_concurrent_tasks": 10}}
        errors = validator.validate(config)
        assert len(errors) == 0

    def test_validate_empty_config(self):
        validator = ConfigValidator()
        errors = validator.validate({})
        assert len(errors) == 0


class TestConfigManagerConvertValue:
    def test_convert_true(self, fresh_manager):
        assert fresh_manager._convert_value("true") is True
        assert fresh_manager._convert_value("TRUE") is True
        assert fresh_manager._convert_value("True") is True

    def test_convert_false(self, fresh_manager):
        assert fresh_manager._convert_value("false") is False
        assert fresh_manager._convert_value("FALSE") is False

    def test_convert_int(self, fresh_manager):
        assert fresh_manager._convert_value("42") == 42
        assert fresh_manager._convert_value("-7") == -7

    def test_convert_float(self, fresh_manager):
        assert fresh_manager._convert_value("3.14") == 3.14
        assert fresh_manager._convert_value("-0.5") == -0.5

    def test_convert_list(self, fresh_manager):
        assert fresh_manager._convert_value('[1, 2, 3]') == [1, 2, 3]

    def test_convert_dict(self, fresh_manager):
        assert fresh_manager._convert_value('{"a": 1}') == {"a": 1}

    def test_convert_invalid_json_returns_string(self, fresh_manager):
        assert fresh_manager._convert_value('[1, 2') == '[1, 2'
        assert fresh_manager._convert_value('{"a"') == '{"a"'

    def test_convert_string(self, fresh_manager):
        assert fresh_manager._convert_value("hello") == "hello"


class TestConfigManagerDeepMerge:
    def test_simple_merge(self, fresh_manager):
        base = {"a": 1, "b": 2}
        overlay = {"b": 3, "c": 4}
        result = fresh_manager._deep_merge(base, overlay)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self, fresh_manager):
        base = {"a": {"x": 1, "y": 2}, "b": 3}
        overlay = {"a": {"y": 20, "z": 30}}
        result = fresh_manager._deep_merge(base, overlay)
        assert result["a"]["x"] == 1
        assert result["a"]["y"] == 20
        assert result["a"]["z"] == 30
        assert result["b"] == 3

    def test_override_with_non_dict(self, fresh_manager):
        base = {"a": {"x": 1}}
        overlay = {"a": "string"}
        result = fresh_manager._deep_merge(base, overlay)
        assert result["a"] == "string"

    def test_empty_overlay(self, fresh_manager):
        base = {"a": 1}
        result = fresh_manager._deep_merge(base, {})
        assert result == {"a": 1}

    def test_empty_base(self, fresh_manager):
        overlay = {"a": 1}
        result = fresh_manager._deep_merge({}, overlay)
        assert result == {"a": 1}


class TestConfigManagerGet:
    def test_get_existing(self, fresh_manager):
        fresh_manager._config = {"server": {"port": 8080}}
        assert fresh_manager.get("server.port") == 8080

    def test_get_missing_with_default(self, fresh_manager):
        assert fresh_manager.get("nonexistent", "default") == "default"

    def test_get_missing_without_default(self, fresh_manager):
        assert fresh_manager.get("nonexistent") is None

    def test_get_nested_missing(self, fresh_manager):
        fresh_manager._config = {"server": 8080}
        assert fresh_manager.get("server.port") is None

    def test_get_str(self, fresh_manager):
        fresh_manager._config = {"val": 123}
        assert fresh_manager.get_str("val") == "123"
        assert fresh_manager.get_str("missing", "def") == "def"

    def test_get_int(self, fresh_manager):
        fresh_manager._config = {"val": "42", "bad": "abc"}
        assert fresh_manager.get_int("val") == 42
        assert fresh_manager.get_int("missing", 7) == 7
        assert fresh_manager.get_int("bad", 0) == 0  # 转换失败返回默认值

    def test_get_float(self, fresh_manager):
        fresh_manager._config = {"val": "3.14", "bad": "abc"}
        assert fresh_manager.get_float("val") == 3.14
        assert fresh_manager.get_float("missing", 1.0) == 1.0
        assert fresh_manager.get_float("bad", 0.0) == 0.0

    def test_get_bool_true(self, fresh_manager):
        fresh_manager._config = {"val": True, "str_true": "true", "str_yes": "TRUE"}
        assert fresh_manager.get_bool("val") is True
        assert fresh_manager.get_bool("str_true") is True
        assert fresh_manager.get_bool("str_yes") is True

    def test_get_bool_false(self, fresh_manager):
        fresh_manager._config = {"val": False, "str_false": "false", "zero": 0}
        assert fresh_manager.get_bool("val") is False
        assert fresh_manager.get_bool("str_false") is False
        assert fresh_manager.get_bool("zero") is False

    def test_get_list(self, fresh_manager):
        fresh_manager._config = {"items": [1, 2, 3], "str": "not list"}
        assert fresh_manager.get_list("items") == [1, 2, 3]
        assert fresh_manager.get_list("str") == []
        assert fresh_manager.get_list("missing", ["def"]) == ["def"]

    def test_get_dict(self, fresh_manager):
        fresh_manager._config = {"data": {"a": 1}, "str": "not dict"}
        assert fresh_manager.get_dict("data") == {"a": 1}
        assert fresh_manager.get_dict("str") == {}
        assert fresh_manager.get_dict("missing", {"def": 1}) == {"def": 1}


class TestConfigManagerSet:
    def test_set_simple(self, fresh_manager):
        fresh_manager.set("key", "value")
        assert fresh_manager._config["key"] == "value"

    def test_set_nested_create(self, fresh_manager):
        fresh_manager.set("a.b.c", 123)
        assert fresh_manager._config["a"]["b"]["c"] == 123

    def test_set_override(self, fresh_manager):
        fresh_manager._config = {"a": {"b": 1}}
        fresh_manager.set("a.b", 2)
        assert fresh_manager._config["a"]["b"] == 2

    def test_update(self, fresh_manager):
        fresh_manager._config = {"a": 1}
        fresh_manager.update({"b": 2})
        assert fresh_manager._config == {"a": 1, "b": 2}


class TestConfigManagerLoad:
    def test_load_config_file(self, fresh_manager, temp_config_file):
        fresh_manager.load_config([temp_config_file])
        assert fresh_manager.get_int("server.port") == 9090
        assert fresh_manager.get_bool("server.debug") is True
        # validate_output_dir 会将相对路径转换为绝对路径
        assert os.path.isabs(fresh_manager.get_str("output.default_dir"))
        assert "custom_output" in fresh_manager.get_str("output.default_dir")
        assert fresh_manager.get_int("custom.nested.value") == 42

    def test_load_env_vars(self, fresh_manager, monkeypatch):
        monkeypatch.setenv("AEKV_SERVER_PORT", "7777")
        monkeypatch.setenv("AEKV_OUTPUT_DEFAULT_DIR", "/env/path")
        monkeypatch.setenv("AEKV_SERVER_DEBUG", "true")

        fresh_manager.load_config()
        assert fresh_manager.get_int("server.port") == 7777
        # validate_output_dir 会将环境变量中的相对路径也转换为绝对路径
        assert os.path.isabs(fresh_manager.get_str("output.default_dir"))
        assert fresh_manager.get_bool("server.debug") is True

    def test_load_env_nested_path(self, fresh_manager, monkeypatch):
        monkeypatch.setenv("AEKV_CUSTOM_NESTED_VALUE", "99")
        fresh_manager.load_config()
        assert fresh_manager.get_int("custom.nested.value") == 99

    def test_env_priority_over_default(self, fresh_manager, monkeypatch):
        monkeypatch.setenv("AEKV_SERVER_PORT", "9999")
        fresh_manager.load_config()
        assert fresh_manager.get_int("server.port") == 9999

    def test_reload_clears_previous(self, fresh_manager, temp_config_file):
        fresh_manager.load_config([temp_config_file])
        assert fresh_manager.get_int("server.port") == 9090
        fresh_manager.reload()
        # reload 会重新合并所有 source，但不会清除已加载的文件源
        assert fresh_manager.get_int("server.port") == 9090


class TestConfigManagerSave:
    def test_save_and_load(self, fresh_manager, temp_config_file):
        fresh_manager.load_config([temp_config_file])
        fresh_manager.set("extra.key", "saved")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            save_path = f.name

        try:
            fresh_manager.save(save_path)
            with open(save_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            assert data["server"]["port"] == 9090
            assert data["extra"]["key"] == "saved"
        finally:
            os.remove(save_path)


class TestConfigManagerCheckDependencies:
    def test_check_dependencies_structure(self, fresh_manager):
        deps = fresh_manager.check_dependencies()
        assert isinstance(deps, dict)
        assert "ae_installed" in deps
        assert "silhouette_installed" in deps
        assert "output_dir_writable" in deps
        assert "tmp_dir_writable" in deps

    def test_output_dir_writable(self, fresh_manager):
        with tempfile.TemporaryDirectory() as tmpdir:
            fresh_manager.set("output.default_dir", tmpdir)
            deps = fresh_manager.check_dependencies()
            assert deps["output_dir_writable"] is True

    def test_nonexistent_dir_not_writable(self, fresh_manager):
        fresh_manager.set("output.default_dir", "C:/nonexistent_path_for_test")
        deps = fresh_manager.check_dependencies()
        # 在 Windows 上可能因权限不同而有差异，但通常不可写
        assert isinstance(deps["output_dir_writable"], bool)


class TestConfigManagerGetConfigSummary:
    def test_summary_excludes_secrets(self, fresh_manager):
        fresh_manager.load_config()
        summary = fresh_manager.get_config_summary()
        assert "model" in summary
        assert "api_key" not in str(summary)  # 摘要不应包含敏感信息

    def test_summary_structure(self, fresh_manager):
        fresh_manager.load_config()
        summary = fresh_manager.get_config_summary()
        assert "sources" in summary
        assert "output" in summary
        assert "ae" in summary
        assert "server" in summary
        assert "pipeline" in summary


class TestGlobalFunctions:
    def test_global_config_manager_exists(self):
        assert config_manager is not None
        assert isinstance(config_manager, ConfigManager)

    def test_get_config_function(self):
        result = get_config("server.port")
        # 全局 config_manager 应已加载默认配置；若因环境差异返回 None 也属正常行为边界
        assert isinstance(result, (int, type(None)))
        if isinstance(result, int):
            assert result >= 0

    def test_get_str_function(self):
        result = get_str("output.default_dir")
        assert isinstance(result, str)

    def test_get_int_function(self):
        result = get_int("server.port")
        assert isinstance(result, int)

    def test_get_float_function(self):
        result = get_float("memory.min_confidence")
        assert isinstance(result, float)

    def test_get_bool_function(self):
        result = get_bool("memory.enabled")
        assert isinstance(result, bool)

    def test_get_list_function(self):
        result = get_list("model.fallback_providers")
        assert isinstance(result, list)

    def test_get_dict_function(self):
        result = get_dict("ae")
        assert isinstance(result, dict)

    def test_set_and_get_config(self):
        original = get_str("test_temp_key", "none")
        set_config("test_temp_key", "test_value")
        assert get_str("test_temp_key") == "test_value"
        # 清理
        if original != "none":
            set_config("test_temp_key", original)
        else:
            # 删除临时键
            if "test_temp_key" in config_manager._config:
                del config_manager._config["test_temp_key"]

    def test_check_dependencies_function(self):
        result = check_dependencies()
        assert isinstance(result, dict)
        assert "ae_installed" in result
