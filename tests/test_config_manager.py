"""配置管理器单元测试"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.config_manager import (
    _deep_merge,
    _set_nested_value,
    get_config,
    get_secret,
    reload_config,
)


class TestDeepMerge(unittest.TestCase):
    def test_simple_merge(self):
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = _deep_merge(base, override)
        self.assertEqual(result["a"], 1)
        self.assertEqual(result["b"], 3)
        self.assertEqual(result["c"], 4)

    def test_nested_merge(self):
        base = {"a": {"x": 1, "y": 2}, "b": 3}
        override = {"a": {"y": 20, "z": 30}}
        result = _deep_merge(base, override)
        self.assertEqual(result["a"]["x"], 1)
        self.assertEqual(result["a"]["y"], 20)
        self.assertEqual(result["a"]["z"], 30)
        self.assertEqual(result["b"], 3)

    def test_override_with_non_dict(self):
        base = {"a": {"x": 1}}
        override = {"a": "string"}
        result = _deep_merge(base, override)
        self.assertEqual(result["a"], "string")


class TestSetNested(unittest.TestCase):
    def test_set_simple(self):
        d = {}
        _set_nested_value(d, ["key"], "value")
        self.assertEqual(d["key"], "value")

    def test_set_nested(self):
        d = {}
        _set_nested_value(d, ["a", "b", "c"], 123)
        self.assertEqual(d["a"]["b"]["c"], 123)

    def test_set_int(self):
        d = {"x": 0}
        _set_nested_value(d, ["x"], "42")
        self.assertEqual(d["x"], 42)

    def test_set_bool(self):
        d = {"flag": False}
        _set_nested_value(d, ["flag"], "true")
        self.assertTrue(d["flag"])
        _set_nested_value(d, ["flag"], "false")
        self.assertFalse(d["flag"])

    def test_set_list(self):
        d = {"items": []}
        _set_nested_value(d, ["items"], "a,b,c")
        self.assertEqual(d["items"], ["a", "b", "c"])


class TestGetConfig(unittest.TestCase):
    def test_default_config_has_keys(self):
        reload_config()
        config = get_config()
        self.assertIn("version", config)
        self.assertIn("environment", config)
        self.assertIn("directories", config)
        self.assertIn("mcp_bridge", config)

    def test_development_environment(self):
        reload_config()
        config = get_config("development")
        self.assertEqual(config["environment"], "development")

    def test_test_environment(self):
        reload_config()
        config = get_config("test")
        self.assertEqual(config["environment"], "test")

    def test_production_environment(self):
        reload_config()
        config = get_config("production")
        self.assertEqual(config["environment"], "production")

    def test_env_override(self):
        reload_config()
        os.environ["AEK_VIDEO_LIBRARY"] = "/custom/path"
        try:
            config = get_config()
            self.assertEqual(config["directories"]["video_library"], "/custom/path")
        finally:
            del os.environ["AEK_VIDEO_LIBRARY"]
            reload_config()

    def test_config_deep_copy_isolation(self):
        """修改返回的配置不应污染 _DEFAULT_CONFIG 的嵌套字典"""
        from config import config_manager
        reload_config()
        config = get_config("development")
        # 修改返回的配置嵌套值
        config["directories"]["video_library"] = "/polluted/path"
        config["mcp_bridge"]["command_file"] = "polluted.json"
        # 重新获取配置，应仍为默认值
        fresh = get_config("development")
        self.assertNotEqual(fresh["directories"]["video_library"], "/polluted/path")
        self.assertNotEqual(fresh["mcp_bridge"]["command_file"], "polluted.json")

    def test_cached_config_deep_copy_isolation(self):
        """缓存返回的配置应为深拷贝，修改不影响缓存"""
        reload_config()
        config1 = get_config()  # 触发缓存
        config1["directories"]["video_library"] = "/tampered/path"
        config2 = get_config()  # 从缓存取
        self.assertNotEqual(config2["directories"]["video_library"], "/tampered/path")


class TestGetSecret(unittest.TestCase):
    def test_get_secret_from_env(self):
        os.environ["TEST_SECRET"] = "test_value_123"
        try:
            result = get_secret("TEST_SECRET")
            self.assertEqual(result, "test_value_123")
        finally:
            del os.environ["TEST_SECRET"]

    def test_get_secret_default(self):
        result = get_secret("NONEXISTENT_SECRET", "default_val")
        self.assertEqual(result, "default_val")

    def test_get_secret_none_default(self):
        result = get_secret("NONEXISTENT_SECRET")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
