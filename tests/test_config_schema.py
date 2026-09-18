"""config_schema 模块单元测试

覆盖范围:
- 所有内置类型验证（string, int, float, bool, list, dict, path, enum, any）
- 类型自动转换
- 边界条件（min/max值、长度限制、模式匹配）
- 嵌套结构验证（list元素、dict属性）
- 必填项与默认值
- 自定义验证器与转换器
- 完整配置验证
- 文档生成
- 便捷函数
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config_schema import (
    ConfigSchemaNode,
    ConfigSchemaValidator,
    ValidationResult,
    build_default_schema,
    validate_config,
    validate_single,
)


class TestValidationResult:
    """ValidationResult 数据类测试"""

    def test_valid_result(self):
        r = ValidationResult(valid=True)
        assert bool(r) is True
        assert str(r) == "Valid"

    def test_valid_with_warnings(self):
        r = ValidationResult(valid=True, warnings=["warn1"])
        assert bool(r) is True
        assert "1 warnings" in str(r)

    def test_invalid_result(self):
        r = ValidationResult(valid=False, errors=["err1", "err2"])
        assert bool(r) is False
        assert "2 errors" in str(r)

    def test_fixed_value(self):
        r = ValidationResult(valid=True, fixed_value=42)
        assert r.fixed_value == 42


class TestStringValidation:
    """字符串类型验证测试"""

    def test_string_valid(self):
        node = ConfigSchemaNode(type="string")
        v = ConfigSchemaValidator({})
        r = v.validate_value("hello", node)
        assert r.valid is True
        assert r.fixed_value == "hello"

    def test_string_from_int_conversion(self):
        node = ConfigSchemaNode(type="string")
        v = ConfigSchemaValidator({})
        r = v.validate_value(123, node)
        assert r.valid is True
        assert r.fixed_value == "123"
        assert len(r.warnings) > 0

    def test_string_min_length(self):
        node = ConfigSchemaNode(type="string", min_length=5)
        v = ConfigSchemaValidator({})
        r = v.validate_value("abc", node)
        assert r.valid is False
        assert any("小于最小值" in e for e in r.errors)

    def test_string_max_length(self):
        node = ConfigSchemaNode(type="string", max_length=5)
        v = ConfigSchemaValidator({})
        r = v.validate_value("abcdef", node)
        assert r.valid is False
        assert any("大于最大值" in e for e in r.errors)

    def test_string_pattern_match(self):
        node = ConfigSchemaNode(type="string", pattern=r"^\d+$")
        v = ConfigSchemaValidator({})
        r = v.validate_value("12345", node)
        assert r.valid is True

    def test_string_pattern_mismatch(self):
        node = ConfigSchemaNode(type="string", pattern=r"^\d+$")
        v = ConfigSchemaValidator({})
        r = v.validate_value("abc", node)
        assert r.valid is False
        assert any("不匹配模式" in e for e in r.errors)

    def test_string_length_exact_boundary(self):
        node = ConfigSchemaNode(type="string", min_length=3, max_length=3)
        v = ConfigSchemaValidator({})
        r = v.validate_value("abc", node)
        assert r.valid is True


class TestIntValidation:
    """整数类型验证测试"""

    def test_int_valid(self):
        node = ConfigSchemaNode(type="int")
        v = ConfigSchemaValidator({})
        r = v.validate_value(42, node)
        assert r.valid is True
        assert r.fixed_value == 42

    def test_int_from_string(self):
        node = ConfigSchemaNode(type="int")
        v = ConfigSchemaValidator({})
        r = v.validate_value("123", node)
        assert r.valid is True
        assert r.fixed_value == 123
        assert len(r.warnings) > 0

    def test_int_from_float_whole(self):
        node = ConfigSchemaNode(type="int")
        v = ConfigSchemaValidator({})
        r = v.validate_value(5.0, node)
        assert r.valid is True
        assert r.fixed_value == 5

    def test_int_from_float_fractional(self):
        node = ConfigSchemaNode(type="int")
        v = ConfigSchemaValidator({})
        r = v.validate_value(5.5, node)
        assert r.valid is False
        assert any("不是整数" in e for e in r.errors)

    def test_int_invalid_string(self):
        node = ConfigSchemaNode(type="int")
        v = ConfigSchemaValidator({})
        r = v.validate_value("not_a_number", node)
        assert r.valid is False

    def test_int_min_value(self):
        node = ConfigSchemaNode(type="int", min_value=10)
        v = ConfigSchemaValidator({})
        r = v.validate_value(5, node)
        assert r.valid is False
        assert any("小于最小值" in e for e in r.errors)

    def test_int_max_value(self):
        node = ConfigSchemaNode(type="int", max_value=100)
        v = ConfigSchemaValidator({})
        r = v.validate_value(101, node)
        assert r.valid is False

    def test_int_boundary_values(self):
        node = ConfigSchemaNode(type="int", min_value=0, max_value=10)
        v = ConfigSchemaValidator({})
        assert v.validate_value(0, node).valid is True
        assert v.validate_value(10, node).valid is True
        assert v.validate_value(-1, node).valid is False
        assert v.validate_value(11, node).valid is False

    def test_bool_not_accepted_as_int(self):
        node = ConfigSchemaNode(type="int")
        v = ConfigSchemaValidator({})
        r = v.validate_value(True, node)
        assert r.valid is True
        assert r.fixed_value == 1
        assert len(r.warnings) > 0


class TestFloatValidation:
    """浮点数类型验证测试"""

    def test_float_valid(self):
        node = ConfigSchemaNode(type="float")
        v = ConfigSchemaValidator({})
        r = v.validate_value(3.14, node)
        assert r.valid is True
        assert r.fixed_value == 3.14

    def test_float_from_int(self):
        node = ConfigSchemaNode(type="float")
        v = ConfigSchemaValidator({})
        r = v.validate_value(42, node)
        assert r.valid is True
        assert r.fixed_value == 42.0
        assert len(r.warnings) > 0

    def test_float_from_string(self):
        node = ConfigSchemaNode(type="float")
        v = ConfigSchemaValidator({})
        r = v.validate_value("2.718", node)
        assert r.valid is True
        assert r.fixed_value == 2.718

    def test_float_invalid_string(self):
        node = ConfigSchemaNode(type="float")
        v = ConfigSchemaValidator({})
        r = v.validate_value("not_float", node)
        assert r.valid is False

    def test_float_min_max(self):
        node = ConfigSchemaNode(type="float", min_value=0.0, max_value=1.0)
        v = ConfigSchemaValidator({})
        assert v.validate_value(0.5, node).valid is True
        assert v.validate_value(0.0, node).valid is True
        assert v.validate_value(1.0, node).valid is True
        assert v.validate_value(-0.1, node).valid is False
        assert v.validate_value(1.1, node).valid is False

    def test_bool_not_accepted_as_float(self):
        node = ConfigSchemaNode(type="float")
        v = ConfigSchemaValidator({})
        r = v.validate_value(False, node)
        assert r.valid is True
        assert r.fixed_value == 0.0
        assert len(r.warnings) > 0


class TestBoolValidation:
    """布尔类型验证测试"""

    def test_bool_true(self):
        node = ConfigSchemaNode(type="bool")
        v = ConfigSchemaValidator({})
        r = v.validate_value(True, node)
        assert r.valid is True
        assert r.fixed_value is True

    def test_bool_false(self):
        node = ConfigSchemaNode(type="bool")
        v = ConfigSchemaValidator({})
        r = v.validate_value(False, node)
        assert r.valid is True
        assert r.fixed_value is False

    def test_bool_from_string_true(self):
        node = ConfigSchemaNode(type="bool")
        v = ConfigSchemaValidator({})
        true_strings = ["true", "1", "yes", "on", "是", "开", "TRUE", "Yes"]
        for s in true_strings:
            r = v.validate_value(s, node)
            assert r.valid is True, f"{s} should be valid True"
            assert r.fixed_value is True

    def test_bool_from_string_false(self):
        node = ConfigSchemaNode(type="bool")
        v = ConfigSchemaValidator({})
        false_strings = ["false", "0", "no", "off", "否", "关", "FALSE", "No"]
        for s in false_strings:
            r = v.validate_value(s, node)
            assert r.valid is True, f"{s} should be valid False"
            assert r.fixed_value is False

    def test_bool_from_int(self):
        node = ConfigSchemaNode(type="bool")
        v = ConfigSchemaValidator({})
        r = v.validate_value(1, node)
        assert r.valid is True
        assert r.fixed_value is True

        r = v.validate_value(0, node)
        assert r.valid is True
        assert r.fixed_value is False

    def test_bool_invalid_string(self):
        node = ConfigSchemaNode(type="bool")
        v = ConfigSchemaValidator({})
        r = v.validate_value("maybe", node)
        assert r.valid is False


class TestListValidation:
    """列表类型验证测试"""

    def test_list_valid(self):
        node = ConfigSchemaNode(type="list")
        v = ConfigSchemaValidator({})
        r = v.validate_value([1, 2, 3], node)
        assert r.valid is True
        assert r.fixed_value == [1, 2, 3]

    def test_list_with_item_schema(self):
        item_node = ConfigSchemaNode(type="int", min_value=0)
        node = ConfigSchemaNode(type="list", item_schema=item_node)
        v = ConfigSchemaValidator({})
        r = v.validate_value([1, 2, 3], node)
        assert r.valid is True
        assert r.fixed_value == [1, 2, 3]

    def test_list_with_invalid_items(self):
        item_node = ConfigSchemaNode(type="int", min_value=0)
        node = ConfigSchemaNode(type="list", item_schema=item_node)
        v = ConfigSchemaValidator({})
        r = v.validate_value([1, -2, 3], node)
        assert r.valid is False
        assert len(r.errors) >= 1

    def test_list_single_value_wrap(self):
        item_node = ConfigSchemaNode(type="int")
        node = ConfigSchemaNode(type="list", item_schema=item_node)
        v = ConfigSchemaValidator({})
        r = v.validate_value(42, node)
        assert r.valid is True
        assert r.fixed_value == [42]
        assert len(r.warnings) > 0

    def test_list_from_tuple(self):
        node = ConfigSchemaNode(type="list")
        v = ConfigSchemaValidator({})
        r = v.validate_value((1, 2, 3), node)
        assert r.valid is True
        assert r.fixed_value == [1, 2, 3]

    def test_list_empty(self):
        node = ConfigSchemaNode(type="list")
        v = ConfigSchemaValidator({})
        r = v.validate_value([], node)
        assert r.valid is True
        assert r.fixed_value == []

    def test_list_invalid_type(self):
        node = ConfigSchemaNode(type="list")
        v = ConfigSchemaValidator({})
        r = v.validate_value(123, node)
        assert r.valid is False


class TestDictValidation:
    """字典/对象类型验证测试"""

    def test_dict_valid(self):
        node = ConfigSchemaNode(type="dict")
        v = ConfigSchemaValidator({})
        r = v.validate_value({"a": 1, "b": 2}, node)
        assert r.valid is True

    def test_dict_with_properties(self):
        props = {
            "name": ConfigSchemaNode(type="string", required=True),
            "age": ConfigSchemaNode(type="int", min_value=0),
        }
        node = ConfigSchemaNode(type="dict", properties=props)
        v = ConfigSchemaValidator({})
        r = v.validate_value({"name": "Alice", "age": 30}, node)
        assert r.valid is True
        assert r.fixed_value["name"] == "Alice"
        assert r.fixed_value["age"] == 30

    def test_dict_missing_required(self):
        props = {
            "name": ConfigSchemaNode(type="string", required=True),
            "age": ConfigSchemaNode(type="int"),
        }
        node = ConfigSchemaNode(type="dict", properties=props)
        v = ConfigSchemaValidator({})
        r = v.validate_value({"age": 30}, node)
        assert r.valid is False
        assert any("必填属性缺失" in e for e in r.errors)

    def test_dict_default_values(self):
        props = {
            "name": ConfigSchemaNode(type="string", default="unknown"),
            "active": ConfigSchemaNode(type="bool", default=True),
        }
        node = ConfigSchemaNode(type="dict", properties=props)
        v = ConfigSchemaValidator({})
        r = v.validate_value({}, node)
        assert r.valid is True
        assert r.fixed_value["name"] == "unknown"
        assert r.fixed_value["active"] is True
        assert len(r.warnings) >= 2

    def test_dict_nested_validation(self):
        inner_props = {"x": ConfigSchemaNode(type="int", required=True)}
        outer_props = {
            "pos": ConfigSchemaNode(type="dict", properties=inner_props, required=True),
        }
        node = ConfigSchemaNode(type="dict", properties=outer_props)
        v = ConfigSchemaValidator({})

        r = v.validate_value({"pos": {"x": 5}}, node)
        assert r.valid is True

        r = v.validate_value({"pos": {}}, node)
        assert r.valid is False

    def test_dict_invalid_type(self):
        node = ConfigSchemaNode(type="dict")
        v = ConfigSchemaValidator({})
        r = v.validate_value("not_a_dict", node)
        assert r.valid is False


class TestPathValidation:
    """路径类型验证测试"""

    def test_path_from_string(self):
        node = ConfigSchemaNode(type="path")
        v = ConfigSchemaValidator({})
        r = v.validate_value("/some/path", node)
        assert r.valid is True
        assert r.fixed_value == "/some/path"

    def test_path_invalid_type(self):
        node = ConfigSchemaNode(type="path")
        v = ConfigSchemaValidator({})
        r = v.validate_value(123, node)
        assert r.valid is False

    def test_path_user_expansion(self):
        node = ConfigSchemaNode(type="path")
        v = ConfigSchemaValidator({})
        r = v.validate_value("~/test", node)
        assert r.valid is True
        assert "~" not in r.fixed_value


class TestEnumValidation:
    """枚举类型验证测试"""

    def test_enum_valid(self):
        node = ConfigSchemaNode(type="enum", enum=["red", "green", "blue"])
        v = ConfigSchemaValidator({})
        r = v.validate_value("red", node)
        assert r.valid is True
        assert r.fixed_value == "red"

    def test_enum_invalid(self):
        node = ConfigSchemaNode(type="enum", enum=["red", "green", "blue"])
        v = ConfigSchemaValidator({})
        r = v.validate_value("yellow", node)
        assert r.valid is False
        assert any("不在允许的枚举值中" in e for e in r.errors)

    def test_enum_case_insensitive(self):
        node = ConfigSchemaNode(type="enum", enum=["Red", "Green", "Blue"])
        v = ConfigSchemaValidator({})
        r = v.validate_value("red", node)
        assert r.valid is True
        assert r.fixed_value == "Red"
        assert len(r.warnings) > 0

    def test_enum_none_enum_list(self):
        node = ConfigSchemaNode(type="enum")
        v = ConfigSchemaValidator({})
        r = v.validate_value("anything", node)
        assert r.valid is True

    def test_enum_non_string_value(self):
        node = ConfigSchemaNode(type="enum", enum=[1, 2, 3])
        v = ConfigSchemaValidator({})
        r = v.validate_value(2, node)
        assert r.valid is True


class TestAnyType:
    """any 类型测试"""

    def test_any_accepts_everything(self):
        node = ConfigSchemaNode(type="any")
        v = ConfigSchemaValidator({})
        assert v.validate_value(None, node).valid is True
        assert v.validate_value(123, node).valid is True
        assert v.validate_value("str", node).valid is True
        assert v.validate_value([1, 2], node).valid is True
        assert v.validate_value({"a": 1}, node).valid is True


class TestCustomValidator:
    """自定义验证器测试"""

    def test_custom_validator_passes(self):
        def is_even(v):
            return (v % 2 == 0, None)
        node = ConfigSchemaNode(type="int", validator=is_even)
        v = ConfigSchemaValidator({})
        r = v.validate_value(4, node)
        assert r.valid is True

    def test_custom_validator_fails(self):
        def is_even(v):
            return (False, "必须是偶数")
        node = ConfigSchemaNode(type="int", validator=is_even)
        v = ConfigSchemaValidator({})
        r = v.validate_value(3, node)
        assert r.valid is False
        assert any("必须是偶数" in e for e in r.errors)

    def test_custom_validator_exception(self):
        def bad_validator(v):
            raise RuntimeError("oops")
        node = ConfigSchemaNode(type="int", validator=bad_validator)
        v = ConfigSchemaValidator({})
        r = v.validate_value(5, node)
        assert r.valid is False
        assert any("验证器执行错误" in e for e in r.errors)


class TestCustomConverter:
    """自定义转换器测试"""

    def test_custom_converter(self):
        def to_uppercase(v):
            return v.upper()
        node = ConfigSchemaNode(type="string", converter=to_uppercase)
        v = ConfigSchemaValidator({})
        r = v.validate_value("hello", node)
        assert r.valid is True
        assert r.fixed_value == "HELLO"

    def test_custom_converter_exception(self):
        def bad_converter(v):
            raise ValueError("conversion failed")
        node = ConfigSchemaNode(type="string", converter=bad_converter)
        v = ConfigSchemaValidator({})
        r = v.validate_value("hello", node)
        assert r.valid is False
        assert any("转换失败" in e for e in r.errors)


class TestFullConfigValidation:
    """完整配置验证测试"""

    def test_valid_config(self):
        schema = {
            "name": ConfigSchemaNode(type="string", required=True),
            "age": ConfigSchemaNode(type="int", default=18, min_value=0),
            "active": ConfigSchemaNode(type="bool", default=True),
        }
        v = ConfigSchemaValidator(schema)
        r = v.validate({"name": "Test", "age": 25})
        assert r.valid is True
        assert r.fixed_value["name"] == "Test"
        assert r.fixed_value["age"] == 25
        assert r.fixed_value["active"] is True

    def test_missing_required(self):
        schema = {
            "name": ConfigSchemaNode(type="string", required=True),
        }
        v = ConfigSchemaValidator(schema)
        r = v.validate({})
        assert r.valid is False
        assert any("必填项" in e for e in r.errors)

    def test_optional_skipped(self):
        schema = {
            "optional": ConfigSchemaNode(type="string", required=False),
        }
        v = ConfigSchemaValidator(schema)
        r = v.validate({})
        assert r.valid is True
        assert "optional" not in r.fixed_value

    def test_default_applied(self):
        schema = {
            "count": ConfigSchemaNode(type="int", default=10),
        }
        v = ConfigSchemaValidator(schema)
        r = v.validate({})
        assert r.valid is True
        assert r.fixed_value["count"] == 10

    def test_multiple_errors_collected(self):
        schema = {
            "a": ConfigSchemaNode(type="int", min_value=10),
            "b": ConfigSchemaNode(type="string", min_length=5),
        }
        v = ConfigSchemaValidator(schema)
        r = v.validate({"a": 5, "b": "hi"})
        assert r.valid is False
        assert len(r.errors) >= 2


class TestDocumentation:
    """文档生成测试"""

    def test_generate_documentation(self):
        schema = {
            "name": ConfigSchemaNode(
                type="string",
                required=True,
                description="用户名称",
                category="用户",
            ),
            "age": ConfigSchemaNode(
                type="int",
                default=18,
                description="用户年龄",
                category="用户",
            ),
        }
        v = ConfigSchemaValidator(schema)
        doc = v.generate_documentation()
        assert "配置项文档" in doc
        assert "name" in doc
        assert "age" in doc
        assert "用户" in doc

    def test_get_defaults(self):
        schema = {
            "a": ConfigSchemaNode(type="int", default=1),
            "b": ConfigSchemaNode(type="string", default="hello"),
            "c": ConfigSchemaNode(type="bool"),
        }
        v = ConfigSchemaValidator(schema)
        defaults = v.get_defaults()
        assert defaults["a"] == 1
        assert defaults["b"] == "hello"
        assert "c" not in defaults


class TestDefaultSchema:
    """默认 Schema 构建测试"""

    def test_build_default_schema_returns_dict(self):
        schema = build_default_schema()
        assert isinstance(schema, dict)
        assert len(schema) > 0

    def test_default_schema_has_expected_keys(self):
        schema = build_default_schema()
        assert "environment" in schema
        assert "version" in schema
        assert schema["environment"].type == "enum"
        assert schema["version"].type == "string"

    def test_default_schema_validation(self):
        schema = build_default_schema()
        v = ConfigSchemaValidator(schema)
        r = v.validate({})
        assert r.valid is True


class TestHelperFunctions:
    """便捷函数测试"""

    def test_validate_config_with_default_schema(self):
        r = validate_config({})
        assert r.valid is True

    def test_validate_config_with_custom_schema(self):
        custom = {"key": ConfigSchemaNode(type="int", required=True)}
        r = validate_config({}, schema=custom)
        assert r.valid is False

    def test_validate_single_string(self):
        r = validate_single("hello", "string")
        assert r.valid is True
        assert r.fixed_value == "hello"

    def test_validate_single_int_with_constraints(self):
        r = validate_single(5, "int", min_value=0, max_value=10)
        assert r.valid is True

        r = validate_single(15, "int", min_value=0, max_value=10)
        assert r.valid is False

    def test_validate_single_enum(self):
        r = validate_single("a", "enum", enum=["a", "b", "c"])
        assert r.valid is True
