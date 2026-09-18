"""core.config 单元测试 - ConfigSource / ConfigValidator / ConfigManager / 全局便捷函数"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import (
    ConfigManager,
    ConfigSource,
    ConfigValidator,
    check_dependencies,
    config_manager,
    get_bool,
    get_config,
    get_dict,
    get_float,
    get_int,
    get_list,
    get_str,
    load_config,
    set_config,
)

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def fresh_manager():
    """提供全新初始化的 ConfigManager，避免全局状态污染"""
    mgr = ConfigManager()
    mgr.load_config([])
    return mgr


@pytest.fixture
def sample_config_file(tmp_path):
    """创建临时配置文件并返回路径"""
    config_data = {
        "server": {
            "port": 9090,
            "debug": True,
        },
        "output": {
            "default_dir": "./custom_output",
        },
        "custom": {
            "nested": {
                "value": 42,
            },
        },
        "pipeline": {
            "max_concurrent_tasks": 8,
        },
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config_data, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(config_file)


# ============================================================================
# ConfigSource 数据类
# ============================================================================

class TestConfigSource:
    def test_initialization_with_data(self):
        src = ConfigSource(name="test_source", priority=5, data={"key": "value", "num": 42})
        assert src.name == "test_source"
        assert src.priority == 5
        assert src.data == {"key": "value", "num": 42}

    def test_initialization_default_data(self):
        src = ConfigSource(name="empty_source", priority=1)
        assert src.name == "empty_source"
        assert src.priority == 1
        assert src.data == {}

    def test_mutation_independence(self):
        data = {"a": 1}
        src = ConfigSource(name="t", priority=1, data=data)
        data["b"] = 2
        assert src.data == {"a": 1, "b": 2}


# ============================================================================
# ConfigValidator 配置验证器
# ============================================================================

class TestConfigValidator:
    """ConfigValidator 测试——validate() 返回 (errors, warnings) 元组"""

    @staticmethod
    def _base(output_dir="C:/tmp/test_output"):
        return {"output": {"default_dir": output_dir}}

    def test_port_range_valid(self):
        validator = ConfigValidator()
        config = {**self._base(), "server": {"port": 8080}}
        errors, _ = validator.validate(config)
        assert len(errors) == 0

    def test_port_below_1024(self):
        validator = ConfigValidator()
        config = {**self._base(), "server": {"port": 80}}
        errors, _ = validator.validate(config)
        assert len(errors) == 1
        assert "1024-65535" in errors[0]

    def test_port_above_65535(self):
        validator = ConfigValidator()
        config = {**self._base(), "server": {"port": 70000}}
        errors, _ = validator.validate(config)
        assert len(errors) == 1
        assert "1024-65535" in errors[0]

    def test_concurrency_valid(self):
        validator = ConfigValidator()
        config = {**self._base(), "pipeline": {"max_concurrent_tasks": 5}}
        errors, _ = validator.validate(config)
        assert len(errors) == 0

    def test_concurrency_less_than_one(self):
        validator = ConfigValidator()
        config = {**self._base(), "pipeline": {"max_concurrent_tasks": 0}}
        errors, _ = validator.validate(config)
        assert len(errors) == 1
        assert "必须 >= 1" in errors[0]

    def test_concurrency_zero(self):
        validator = ConfigValidator()
        config = {**self._base(), "pipeline": {"max_concurrent_tasks": 0}}
        errors, _ = validator.validate(config)
        assert len(errors) == 1

    def test_concurrency_negative(self):
        validator = ConfigValidator()
        config = {**self._base(), "pipeline": {"max_concurrent_tasks": -3}}
        errors, _ = validator.validate(config)
        assert len(errors) == 1
        assert "必须 >= 1" in errors[0]

    def test_output_dir_relative_to_absolute(self):
        validator = ConfigValidator()
        config = {"output": {"default_dir": "./relative_path"}}
        errors, _ = validator.validate(config)
        assert os.path.isabs(config["output"]["default_dir"])
        assert "relative_path" in config["output"]["default_dir"]
        assert len(errors) == 0

    def test_output_dir_absolute_stays_absolute(self):
        validator = ConfigValidator()
        abs_path = os.path.abspath("/some/absolute/path")
        config = {"output": {"default_dir": abs_path}}
        errors, _ = validator.validate(config)
        assert config["output"]["default_dir"] == abs_path
        assert len(errors) == 0

    def test_ae_path_not_exists(self):
        validator = ConfigValidator()
        config = {**self._base(), "ae": {"install_path": "C:/nonexistent_path_xyz/ae.exe"}}
        errors, _ = validator.validate(config)
        assert len(errors) == 1
        assert "AE 安装路径不存在" in errors[0]

    def test_silhouette_path_not_exists(self):
        validator = ConfigValidator()
        config = {**self._base(), "silhouette": {"install_path": "C:/nonexistent_path_xyz/sil.exe"}}
        errors, _ = validator.validate(config)
        assert len(errors) == 1
        assert "Silhouette 安装路径不存在" in errors[0]

    def test_multiple_validation_errors(self):
        validator = ConfigValidator()
        config = {
            **self._base(),
            "server": {"port": 80},
            "pipeline": {"max_concurrent_tasks": 0},
            "ae": {"install_path": "C:/nonexistent/ae.exe"},
            "silhouette": {"install_path": "C:/nonexistent/sil.exe"},
        }
        errors, _ = validator.validate(config)
        assert len(errors) == 4
        error_texts = " ".join(errors)
        assert "1024-65535" in error_texts
        assert "必须 >= 1" in error_texts
        assert "AE 安装路径不存在" in error_texts
        assert "Silhouette 安装路径不存在" in error_texts

    def test_empty_config_no_errors(self):
        """empty config 缺少 output.default_dir，应返回 1 个错误"""
        validator = ConfigValidator()
        errors, _ = validator.validate({})
        assert len(errors) == 1
        assert "output.default_dir" in errors[0]


# ============================================================================
# ConfigManager 配置管理器
# ============================================================================

class TestConfigManagerDefaultConfig:
    def test_default_config_loaded_after_init(self, fresh_manager):
        assert fresh_manager.get("server.port") == 8000
        assert fresh_manager.get("server.host") == "localhost"
        assert fresh_manager.get("pipeline.max_concurrent_tasks") == 5
        assert fresh_manager.get("memory.enabled") is True

    def test_default_config_has_all_sections(self, fresh_manager):
        sections = [
            "output", "ae", "silhouette", "topaz", "runway", "pika",
            "blender", "ffmpeg", "server", "pipeline", "logging",
            "media_library", "mcp_bridge", "model", "doubao", "vision", "memory"
        ]
        for section in sections:
            assert fresh_manager.get(section) is not None, f"缺少默认配置节: {section}"


class TestConfigManagerGetters:
    def test_get_existing_path(self, fresh_manager):
        fresh_manager._config = {"server": {"port": 8080, "host": "localhost"}}
        assert fresh_manager.get("server.port") == 8080
        assert fresh_manager.get("server.host") == "localhost"

    def test_get_missing_path_returns_default(self, fresh_manager):
        assert fresh_manager.get("nonexistent.path", "fallback") == "fallback"
        assert fresh_manager.get("nonexistent.path") is None

    def test_get_deeply_nested_missing(self, fresh_manager):
        fresh_manager._config = {"a": {"b": 1}}
        assert fresh_manager.get("a.b.c.d", "default") == "default"

    def test_get_str(self, fresh_manager):
        fresh_manager._config = {"val": 123, "name": "test"}
        assert fresh_manager.get_str("val") == "123"
        assert fresh_manager.get_str("name") == "test"
        assert fresh_manager.get_str("missing", "def") == "def"

    def test_get_int(self, fresh_manager):
        fresh_manager._config = {"val": "42", "num": 100, "bad": "abc"}
        assert fresh_manager.get_int("val") == 42
        assert fresh_manager.get_int("num") == 100
        assert fresh_manager.get_int("missing", 7) == 7
        assert fresh_manager.get_int("bad", 0) == 0

    def test_get_float(self, fresh_manager):
        fresh_manager._config = {"val": "3.14", "num": 2.5, "bad": "abc"}
        assert fresh_manager.get_float("val") == 3.14
        assert fresh_manager.get_float("num") == 2.5
        assert fresh_manager.get_float("missing", 1.0) == 1.0
        assert fresh_manager.get_float("bad", 0.0) == 0.0

    def test_get_bool_true(self, fresh_manager):
        fresh_manager._config = {
            "b1": True,
            "b2": "true",
            "b3": "TRUE",
            "b4": "True",
            "b5": 1,
        }
        assert fresh_manager.get_bool("b1") is True
        assert fresh_manager.get_bool("b2") is True
        assert fresh_manager.get_bool("b3") is True
        assert fresh_manager.get_bool("b4") is True
        assert fresh_manager.get_bool("b5") is True

    def test_get_bool_false(self, fresh_manager):
        fresh_manager._config = {
            "b1": False,
            "b2": "false",
            "b3": "FALSE",
            "b4": 0,
            "b5": "",
        }
        assert fresh_manager.get_bool("b1") is False
        assert fresh_manager.get_bool("b2") is False
        assert fresh_manager.get_bool("b3") is False
        assert fresh_manager.get_bool("b4") is False
        assert fresh_manager.get_bool("b5") is False

    def test_get_bool_default(self, fresh_manager):
        assert fresh_manager.get_bool("missing", True) is True
        assert fresh_manager.get_bool("missing", False) is False
        assert fresh_manager.get_bool("missing") is False

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


class TestConfigManagerSetters:
    def test_set_simple_value(self, fresh_manager):
        fresh_manager.set("key", "value")
        assert fresh_manager.get("key") == "value"

    def test_set_nested_creates_intermediate(self, fresh_manager):
        fresh_manager.set("a.b.c", 123)
        assert fresh_manager.get("a.b.c") == 123
        assert isinstance(fresh_manager.get("a.b"), dict)
        assert isinstance(fresh_manager.get("a"), dict)

    def test_set_override_existing(self, fresh_manager):
        fresh_manager._config = {"a": {"b": 1}}
        fresh_manager.set("a.b", 2)
        assert fresh_manager.get("a.b") == 2

    def test_update_deep_merge_simple(self, fresh_manager):
        fresh_manager._config = {"a": 1, "b": 2}
        fresh_manager.update({"b": 3, "c": 4})
        assert fresh_manager.get("a") == 1
        assert fresh_manager.get("b") == 3
        assert fresh_manager.get("c") == 4

    def test_update_deep_merge_nested(self, fresh_manager):
        fresh_manager._config = {"server": {"port": 8080, "host": "localhost"}}
        fresh_manager.update({"server": {"port": 9090, "debug": True}})
        assert fresh_manager.get("server.port") == 9090
        assert fresh_manager.get("server.host") == "localhost"
        assert fresh_manager.get("server.debug") is True

    def test_update_override_non_dict(self, fresh_manager):
        fresh_manager._config = {"a": {"x": 1}}
        fresh_manager.update({"a": "string"})
        assert fresh_manager.get("a") == "string"


class TestConfigManagerConvertValue:
    def test_convert_bool_true(self, fresh_manager):
        fresh_manager._config = {"t": "placeholder"}
        fresh_manager.set("test", "true")
        assert isinstance(fresh_manager._config["test"], str)

    def test_convert_int(self, fresh_manager, monkeypatch):
        monkeypatch.setenv("AEKV_TEST_INT", "42")
        fresh_manager.load_config()
        assert fresh_manager.get("test.int") == 42
        assert isinstance(fresh_manager.get("test.int"), int)

    def test_convert_float(self, fresh_manager, monkeypatch):
        monkeypatch.setenv("AEKV_TEST_FLOAT", "3.14")
        fresh_manager.load_config()
        assert fresh_manager.get("test.float") == 3.14
        assert isinstance(fresh_manager.get("test.float"), float)

    def test_convert_bool_via_env(self, fresh_manager, monkeypatch):
        monkeypatch.setenv("AEKV_TEST_BOOL", "true")
        monkeypatch.setenv("AEKV_TEST_BOOL2", "false")
        fresh_manager.load_config()
        assert fresh_manager.get("test.bool") is True
        assert fresh_manager.get("test.bool2") is False

    def test_convert_list_via_env(self, fresh_manager, monkeypatch):
        monkeypatch.setenv("AEKV_TEST_LIST", "[1, 2, 3]")
        fresh_manager.load_config()
        assert fresh_manager.get("test.list") == [1, 2, 3]

    def test_convert_dict_via_env(self, fresh_manager, monkeypatch):
        monkeypatch.setenv("AEKV_TEST_DICT", '{"key": "value"}')
        fresh_manager.load_config()
        assert fresh_manager.get("test.dict") == {"key": "value"}

    def test_convert_invalid_json_keeps_string(self, fresh_manager, monkeypatch):
        monkeypatch.setenv("AEKV_TEST_BAD", "[1, 2")
        fresh_manager.load_config()
        assert fresh_manager.get_str("test.bad") == "[1, 2"

    def test_convert_plain_string(self, fresh_manager, monkeypatch):
        monkeypatch.setenv("AEKV_TEST_STR", "hello_world")
        fresh_manager.load_config()
        assert fresh_manager.get("test.str") == "hello_world"


class TestConfigManagerDeepMerge:
    def test_nested_dict_merge(self, fresh_manager):
        fresh_manager._config = {"a": {"x": 1, "y": 2}}
        fresh_manager.update({"a": {"y": 20, "z": 30}})
        assert fresh_manager.get("a.x") == 1
        assert fresh_manager.get("a.y") == 20
        assert fresh_manager.get("a.z") == 30

    def test_value_override(self, fresh_manager):
        fresh_manager._config = {"key": "old"}
        fresh_manager.update({"key": "new"})
        assert fresh_manager.get("key") == "new"

    def test_non_dict_replaces_dict(self, fresh_manager):
        fresh_manager._config = {"a": {"x": 1}}
        fresh_manager.update({"a": "not_dict"})
        assert fresh_manager.get("a") == "not_dict"

    def test_empty_overlay(self, fresh_manager):
        original = {"a": 1, "b": 2}
        fresh_manager._config = original.copy()
        fresh_manager.update({})
        assert fresh_manager._config == original


class TestConfigManagerLoadConfigFile:
    def test_load_from_config_file(self, fresh_manager, sample_config_file):
        fresh_manager.load_config([sample_config_file])
        assert fresh_manager.get_int("server.port") == 9090
        assert fresh_manager.get_bool("server.debug") is True
        assert fresh_manager.get_int("custom.nested.value") == 42
        assert fresh_manager.get_int("pipeline.max_concurrent_tasks") == 8

    def test_config_file_overrides_default(self, fresh_manager, sample_config_file):
        default_port = fresh_manager.get("server.port")
        fresh_manager.load_config([sample_config_file])
        assert fresh_manager.get("server.port") != default_port
        assert fresh_manager.get("server.port") == 9090

    def test_missing_config_file_silently_skipped(self, fresh_manager):
        fresh_manager.load_config(["C:/nonexistent_config_xyz123.json"])
        assert fresh_manager.get("nonexistent") is None

    def test_invalid_json_config_file(self, fresh_manager, tmp_path):
        bad_file = tmp_path / "bad_config.json"
        bad_file.write_text("not valid json {{{", encoding="utf-8")
        fresh_manager.load_config([str(bad_file)])
        assert fresh_manager.get("nonexistent") is None


class TestConfigManagerLoadEnvVars:
    def test_load_from_env_vars(self, fresh_manager, monkeypatch):
        monkeypatch.setenv("AEKV_SERVER_PORT", "7777")
        monkeypatch.setenv("AEKV_SERVER_DEBUG", "true")
        fresh_manager.load_config()
        assert fresh_manager.get_int("server.port") == 7777
        assert fresh_manager.get_bool("server.debug") is True

    def test_env_var_nested_path(self, fresh_manager, monkeypatch):
        monkeypatch.setenv("AEKV_CUSTOM_NESTED_VALUE", "99")
        fresh_manager.load_config()
        assert fresh_manager.get_int("custom.nested.value") == 99

    def test_env_priority_over_default(self, fresh_manager, monkeypatch):
        monkeypatch.setenv("AEKV_SERVER_PORT", "9999")
        fresh_manager.load_config()
        assert fresh_manager.get_int("server.port") == 9999

    def test_env_priority_over_config_file(self, fresh_manager, sample_config_file, monkeypatch):
        monkeypatch.setenv("AEKV_SERVER_PORT", "5555")
        fresh_manager.load_config([sample_config_file])
        assert fresh_manager.get_int("server.port") == 5555

    def test_no_aekv_prefix_ignored(self, fresh_manager, monkeypatch):
        monkeypatch.setenv("NOT_AEKV_SERVER_PORT", "1234")
        fresh_manager.load_config()
        assert fresh_manager.get("not.aekv.server.port") is None


class TestConfigManagerReload:
    def test_reload_hot_reload(self, fresh_manager, sample_config_file):
        fresh_manager.load_config([sample_config_file])
        assert fresh_manager.get_int("server.port") == 9090
        fresh_manager.set("server.port", 11111)
        assert fresh_manager.get_int("server.port") == 11111
        fresh_manager.reload()
        assert fresh_manager.get_int("server.port") == 9090

    def test_reload_keeps_config_files(self, fresh_manager, sample_config_file):
        fresh_manager.load_config([sample_config_file])
        fresh_manager.reload()
        assert fresh_manager.get_int("server.port") == 9090

    def test_reload_refreshes_env_vars(self, fresh_manager, monkeypatch):
        monkeypatch.setenv("AEKV_SERVER_PORT", "8888")
        fresh_manager.load_config()
        assert fresh_manager.get_int("server.port") == 8888
        monkeypatch.setenv("AEKV_SERVER_PORT", "7777")
        fresh_manager.reload()
        assert fresh_manager.get_int("server.port") == 7777


class TestConfigManagerSave:
    def test_save_to_file(self, fresh_manager, tmp_path):
        save_path = str(tmp_path / "saved_config.json")
        fresh_manager.set("test.name", "saved_value")
        fresh_manager.set("test.num", 42)
        fresh_manager.save(save_path)
        assert os.path.exists(save_path)
        with open(save_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["test"]["name"] == "saved_value"
        assert data["test"]["num"] == 42

    def test_save_creates_directory(self, fresh_manager, tmp_path):
        save_path = str(tmp_path / "subdir" / "config.json")
        fresh_manager.save(save_path)
        assert os.path.exists(save_path)

    def test_save_json_format_correct(self, fresh_manager, tmp_path):
        save_path = str(tmp_path / "config.json")
        fresh_manager._config = {"a": 1, "b": {"c": 2}}
        fresh_manager.save(save_path)
        with open(save_path, "r", encoding="utf-8") as f:
            content = f.read()
        data = json.loads(content)
        assert data == {"a": 1, "b": {"c": 2}}


class TestConfigManagerValidate:
    def test_validate_returns_errors(self, fresh_manager):
        fresh_manager.set("server.port", 80)
        fresh_manager.set("pipeline.max_concurrent_tasks", 0)
        errors = fresh_manager.validate()
        assert len(errors) >= 2

    def test_validate_default_config(self, fresh_manager):
        fresh_manager.load_config()
        errors = fresh_manager.validate()
        assert isinstance(errors, list)

    def test_validate_after_fixing_errors(self, fresh_manager):
        fresh_manager.set("server.port", 80)
        errors = fresh_manager.validate()
        assert any("1024-65535" in e for e in errors)
        fresh_manager.set("server.port", 8080)
        errors = fresh_manager.validate()
        assert not any("1024-65535" in e for e in errors)


class TestConfigManagerGetConfigSummary:
    def test_summary_structure(self, fresh_manager):
        fresh_manager.load_config()
        summary = fresh_manager.get_config_summary()
        assert "sources" in summary
        assert "last_reload_time" in summary
        assert "output" in summary
        assert "ae" in summary
        assert "silhouette" in summary
        assert "server" in summary
        assert "pipeline" in summary
        assert "model" in summary
        assert "memory" in summary

    def test_summary_excludes_sensitive_fields(self, fresh_manager):
        fresh_manager.set("model.api_key", "sk-secret-12345")
        fresh_manager.set("runway.api_key", "runway-secret")
        fresh_manager.set("pika.api_key", "pika-secret")
        summary = fresh_manager.get_config_summary()
        summary_str = json.dumps(summary, ensure_ascii=False)
        assert "sk-secret-12345" not in summary_str
        assert "runway-secret" not in summary_str
        assert "pika-secret" not in summary_str

    def test_summary_has_correct_values(self, fresh_manager):
        fresh_manager.load_config()
        summary = fresh_manager.get_config_summary()
        assert summary["server"]["port"] == 8000
        assert summary["server"]["host"] == "localhost"
        assert summary["pipeline"]["max_concurrent_tasks"] == 5


class TestConfigManagerGetFullConfig:
    def test_returns_complete_config(self, fresh_manager):
        full = fresh_manager.get_full_config()
        assert isinstance(full, dict)
        assert "server" in full
        assert "ae" in full
        assert "model" in full

    def test_returns_copy_not_reference(self, fresh_manager):
        full = fresh_manager.get_full_config()
        full["injected"] = "should_not_appear"
        full2 = fresh_manager.get_full_config()
        assert "injected" not in full2

    def test_contains_sensitive_data(self, fresh_manager):
        """get_full_config 返回未掩码原值（对外展示应使用 get_config_summary）"""
        fresh_manager.set("model.api_key", "sk-test-12345")
        full = fresh_manager.get_full_config()
        val = full.get("model", {}).get("api_key", "")
        assert val == "sk-test-12345"


class TestConfigManagerCheckDependencies:
    def test_returns_dependency_dict(self, fresh_manager):
        deps = fresh_manager.check_dependencies()
        assert isinstance(deps, dict)
        expected_keys = [
            "ae_installed", "silhouette_installed", "topaz_installed",
            "blender_installed", "ffmpeg_available", "runway_configured",
            "pika_configured", "output_dir_writable", "tmp_dir_writable",
            "bridge_dir_writable",
        ]
        for key in expected_keys:
            assert key in deps, f"缺少依赖检查项: {key}"
            assert isinstance(deps[key], bool)

    def test_output_dir_writable(self, fresh_manager, tmp_path):
        fresh_manager.set("output.default_dir", str(tmp_path))
        deps = fresh_manager.check_dependencies()
        assert deps["output_dir_writable"] is True

    def test_tmp_dir_writable(self, fresh_manager, tmp_path):
        fresh_manager.set("output.tmp_dir", str(tmp_path))
        deps = fresh_manager.check_dependencies()
        assert deps["tmp_dir_writable"] is True


class TestConfigManagerIsWritable:
    def test_existing_dir_is_writable(self, fresh_manager, tmp_path):
        result = fresh_manager._is_writable(str(tmp_path))
        assert result is True

    def test_nonexistent_dir_creates_and_writable(self, fresh_manager, tmp_path):
        nested_dir = str(tmp_path / "deep" / "nested" / "dir")
        result = fresh_manager._is_writable(nested_dir)
        assert result is True
        assert os.path.exists(nested_dir)

    def test_invalid_path_returns_false(self, fresh_manager):
        result = fresh_manager._is_writable("")
        assert result is False


# ============================================================================
# 全局便捷函数
# ============================================================================

class TestGlobalFunctions:
    def test_config_manager_global_instance(self):
        assert config_manager is not None
        assert isinstance(config_manager, ConfigManager)

    def test_load_config_function(self):
        load_config()
        assert config_manager.get("server.port") is not None

    def test_get_config_function(self):
        result = get_config("server.port")
        assert isinstance(result, (int, type(None)))

    def test_get_str_function(self):
        result = get_str("server.host")
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
        result = get_dict("server")
        assert isinstance(result, dict)

    def test_set_config_function(self):
        original = get_str("test_global_temp_key", "__not_set__")
        try:
            set_config("test_global_temp_key", "test_value_123")
            assert get_str("test_global_temp_key") == "test_value_123"
        finally:
            if original == "__not_set__":
                if "test_global_temp_key" in config_manager._config:
                    del config_manager._config["test_global_temp_key"]
            else:
                set_config("test_global_temp_key", original)

    def test_check_dependencies_function(self):
        result = check_dependencies()
        assert isinstance(result, dict)
        assert "ae_installed" in result
