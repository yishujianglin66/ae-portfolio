#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置Schema验证
=============

提供运行时配置校验、类型安全保障和配置Schema定义。

功能:
- 定义配置项的Schema（类型、范围、默认值、验证规则）
- 运行时验证配置值
- 类型转换与规范化
- 生成配置文档
- 与 config_manager 集成

Schema 类型:
- string: 字符串
- int: 整数
- float: 浮点数
- bool: 布尔值
- list: 列表
- dict: 字典/嵌套对象
- path: 文件/目录路径
- enum: 枚举值
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, Union

# ============================================================================
# 验证结果
# ============================================================================

@dataclass
class ValidationResult:
    """配置验证结果"""
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    fixed_value: Any = None  # 自动修复后的值

    def __bool__(self) -> bool:
        return self.valid

    def __str__(self) -> str:
        if self.valid:
            if self.warnings:
                return f"Valid with {len(self.warnings)} warnings"
            return "Valid"
        return f"Invalid: {len(self.errors)} errors"


@dataclass
class ConfigSchemaNode:
    """配置Schema节点"""
    type: str = "string"
    required: bool = False
    default: Any = None
    description: str = ""
    # 类型特定约束
    min_value: Union[int, float] | None = None
    max_value: Union[int, float] | None = None
    min_length: int | None = None
    max_length: int | None = None
    pattern: str | None = None
    enum: list[Any] | None = None
    item_schema: "ConfigSchemaNode" | None = None  # list 元素 schema
    properties: dict[str, "ConfigSchemaNode"] | None = None  # dict 属性 schema
    # 自定义验证器
    validator: Callable[[Any], tuple[bool, str | None]] | None = None
    # 转换器
    converter: Callable[[Any], Any] | None = None
    # 元数据
    category: str = "general"
    examples: list[Any] = field(default_factory=list)


# ============================================================================
# 配置Schema验证器
# ============================================================================

class ConfigSchemaValidator:
    """配置Schema验证器

    支持验证嵌套配置结构，类型检查，范围验证等。
    """

    def __init__(self, schema: dict[str, ConfigSchemaNode]):
        """
        Args:
            schema: 顶层配置Schema字典 {config_key: ConfigSchemaNode}
        """
        self._schema = schema
        self._type_validators = {
            "string": self._validate_string,
            "int": self._validate_int,
            "float": self._validate_float,
            "bool": self._validate_bool,
            "list": self._validate_list,
            "dict": self._validate_dict,
            "path": self._validate_path,
            "enum": self._validate_enum,
            "any": lambda v, n: ValidationResult(valid=True),
        }

    def validate(self, config: dict[str, Any]) -> ValidationResult:
        """验证完整配置

        Args:
            config: 配置字典

        Returns:
            ValidationResult 验证结果
        """
        all_errors: list[str] = []
        all_warnings: list[str] = []
        cleaned_config: dict[str, Any] = {}

        for key, node in self._schema.items():
            value = config.get(key)

            # 必填检查
            if node.required and value is None and node.default is None:
                all_errors.append(f"配置项 '{key}' 是必填项，但未提供")
                continue

            # 应用默认值
            if value is None and node.default is not None:
                value = node.default

            # 跳过非必填且无值的项
            if value is None and not node.required:
                continue

            # 验证该配置项
            result = self._validate_value(value, node, key)
            if not result.valid:
                all_errors.extend(result.errors)
            else:
                all_warnings.extend(result.warnings)

            # 使用转换/修复后的值
            cleaned_config[key] = result.fixed_value if result.fixed_value is not None else value

        return ValidationResult(
            valid=len(all_errors) == 0,
            errors=all_errors,
            warnings=all_warnings,
            fixed_value=cleaned_config,
        )

    def validate_value(
        self,
        value: Any,
        node: ConfigSchemaNode,
        path: str = "value",
    ) -> ValidationResult:
        """验证单个值

        Args:
            value: 待验证的值
            node: Schema节点
            path: 当前路径（用于错误信息）

        Returns:
            ValidationResult
        """
        return self._validate_value(value, node, path)

    def _validate_value(
        self,
        value: Any,
        node: ConfigSchemaNode,
        path: str,
    ) -> ValidationResult:
        """内部验证方法"""
        errors: list[str] = []
        warnings: list[str] = []
        current_value = value

        # 类型验证
        type_validator = self._type_validators.get(node.type)
        if type_validator:
            type_result = type_validator(current_value, node)
            if not type_result.valid:
                errors.extend(f"{path}: {e}" for e in type_result.errors)
            if type_result.warnings:
                warnings.extend(f"{path}: {w}" for w in type_result.warnings)
            if type_result.fixed_value is not None:
                current_value = type_result.fixed_value

        # 通用约束验证
        if isinstance(current_value, str):
            if node.min_length is not None and len(current_value) < node.min_length:
                errors.append(
                    f"{path}: 长度 {len(current_value)} 小于最小值 {node.min_length}"
                )
            if node.max_length is not None and len(current_value) > node.max_length:
                errors.append(
                    f"{path}: 长度 {len(current_value)} 大于最大值 {node.max_length}"
                )
            if node.pattern and not re.match(node.pattern, current_value):
                errors.append(
                    f"{path}: 值 '{current_value}' 不匹配模式 '{node.pattern}'"
                )

        if isinstance(current_value, (int, float)) and not isinstance(current_value, bool):
            if node.min_value is not None and current_value < node.min_value:
                errors.append(
                    f"{path}: 值 {current_value} 小于最小值 {node.min_value}"
                )
            if node.max_value is not None and current_value > node.max_value:
                errors.append(
                    f"{path}: 值 {current_value} 大于最大值 {node.max_value}"
                )

        # 自定义验证器
        if node.validator:
            try:
                valid, msg = node.validator(current_value)
                if not valid:
                    errors.append(f"{path}: {msg or '自定义验证失败'}")
            except Exception as e:
                errors.append(f"{path}: 验证器执行错误: {e}")

        # 转换器
        if node.converter:
            try:
                converted = node.converter(current_value)
                current_value = converted
            except Exception as e:
                errors.append(f"{path}: 转换失败: {e}")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            fixed_value=current_value,
        )

    # --------------------------------------------------------------------
    # 类型验证器
    # --------------------------------------------------------------------

    def _validate_string(self, value: Any, node: ConfigSchemaNode) -> ValidationResult:
        """验证字符串类型"""
        if isinstance(value, str):
            return ValidationResult(valid=True, fixed_value=value)
        # 尝试转换
        try:
            converted = str(value)
            return ValidationResult(
                valid=True,
                warnings=[f"自动将 {type(value).__name__} 转换为字符串"],
                fixed_value=converted,
            )
        except Exception:
            return ValidationResult(
                valid=False,
                errors=[f"期望字符串类型，实际为 {type(value).__name__}"],
            )

    def _validate_int(self, value: Any, node: ConfigSchemaNode) -> ValidationResult:
        """验证整数类型"""
        if isinstance(value, int) and not isinstance(value, bool):
            return ValidationResult(valid=True, fixed_value=value)
        # 尝试转换
        try:
            if isinstance(value, float):
                if value.is_integer():
                    return ValidationResult(
                        valid=True,
                        warnings=["浮点数自动转换为整数"],
                        fixed_value=int(value),
                    )
                return ValidationResult(
                    valid=False,
                    errors=[f"浮点数值 {value} 不是整数"],
                )
            converted = int(value)
            return ValidationResult(
                valid=True,
                warnings=[f"自动将 {type(value).__name__} 转换为整数"],
                fixed_value=converted,
            )
        except (ValueError, TypeError):
            return ValidationResult(
                valid=False,
                errors=[f"期望整数类型，实际为 {type(value).__name__}: {value!r}"],
            )

    def _validate_float(self, value: Any, node: ConfigSchemaNode) -> ValidationResult:
        """验证浮点数类型"""
        if isinstance(value, float):
            return ValidationResult(valid=True, fixed_value=value)
        if isinstance(value, int) and not isinstance(value, bool):
            return ValidationResult(
                valid=True,
                warnings=["整数自动转换为浮点数"],
                fixed_value=float(value),
            )
        try:
            converted = float(value)
            return ValidationResult(
                valid=True,
                warnings=[f"自动将 {type(value).__name__} 转换为浮点数"],
                fixed_value=converted,
            )
        except (ValueError, TypeError):
            return ValidationResult(
                valid=False,
                errors=[f"期望浮点类型，实际为 {type(value).__name__}: {value!r}"],
            )

    def _validate_bool(self, value: Any, node: ConfigSchemaNode) -> ValidationResult:
        """验证布尔类型"""
        if isinstance(value, bool):
            return ValidationResult(valid=True, fixed_value=value)
        # 字符串/数字转换
        if isinstance(value, str):
            lower = value.lower()
            if lower in ("true", "1", "yes", "on", "是", "开"):
                return ValidationResult(
                    valid=True,
                    warnings=[f"字符串 '{value}' 转换为 True"],
                    fixed_value=True,
                )
            if lower in ("false", "0", "no", "off", "否", "关"):
                return ValidationResult(
                    valid=True,
                    warnings=[f"字符串 '{value}' 转换为 False"],
                    fixed_value=False,
                )
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return ValidationResult(
                valid=True,
                warnings=[f"数字 {value} 转换为布尔值"],
                fixed_value=bool(value),
            )
        return ValidationResult(
            valid=False,
            errors=[f"期望布尔类型，实际为 {type(value).__name__}: {value!r}"],
        )

    def _validate_list(self, value: Any, node: ConfigSchemaNode) -> ValidationResult:
        """验证列表类型"""
        if isinstance(value, list):
            # 如果有元素schema，逐个验证
            if node.item_schema:
                all_errors: list[str] = []
                fixed_items: list[Any] = []
                for i, item in enumerate(value):
                    result = self._validate_value(item, node.item_schema, f"[{i}]")
                    if not result.valid:
                        all_errors.extend(result.errors)
                    fixed_items.append(
                        result.fixed_value if result.fixed_value is not None else item
                    )
                return ValidationResult(
                    valid=len(all_errors) == 0,
                    errors=all_errors,
                    fixed_value=fixed_items,
                )
            return ValidationResult(valid=True, fixed_value=value)
        # 单元素转列表
        if node.item_schema is not None:
            result = self._validate_value(value, node.item_schema, "[0]")
            if result.valid:
                return ValidationResult(
                    valid=True,
                    warnings=["单个值自动包装为列表"],
                    fixed_value=[result.fixed_value if result.fixed_value is not None else value],
                )
        try:
            converted = list(value)
            return ValidationResult(
                valid=True,
                warnings=[f"自动将 {type(value).__name__} 转换为列表"],
                fixed_value=converted,
            )
        except TypeError:
            return ValidationResult(
                valid=False,
                errors=[f"期望列表类型，实际为 {type(value).__name__}"],
            )

    def _validate_dict(self, value: Any, node: ConfigSchemaNode) -> ValidationResult:
        """验证字典/对象类型"""
        if isinstance(value, dict):
            # 如果有属性schema，逐个验证
            if node.properties:
                all_errors: list[str] = []
                all_warnings: list[str] = []
                fixed_dict: dict[str, Any] = {}
                for prop_key, prop_schema in node.properties.items():
                    prop_value = value.get(prop_key)
                    if prop_value is None and prop_schema.default is not None:
                        prop_value = prop_schema.default
                        all_warnings.append(f".{prop_key}: 使用默认值")
                    if prop_value is None and not prop_schema.required:
                        continue
                    if prop_value is None and prop_schema.required:
                        all_errors.append(f".{prop_key}: 必填属性缺失")
                        continue
                    result = self._validate_value(
                        prop_value, prop_schema, f".{prop_key}"
                    )
                    if not result.valid:
                        all_errors.extend(result.errors)
                    all_warnings.extend(result.warnings)
                    fixed_dict[prop_key] = (
                        result.fixed_value if result.fixed_value is not None else prop_value
                    )
                return ValidationResult(
                    valid=len(all_errors) == 0,
                    errors=all_errors,
                    warnings=all_warnings,
                    fixed_value=fixed_dict,
                )
            return ValidationResult(valid=True, fixed_value=value)
        return ValidationResult(
            valid=False,
            errors=[f"期望字典类型，实际为 {type(value).__name__}"],
        )

    def _validate_path(self, value: Any, node: ConfigSchemaNode) -> ValidationResult:
        """验证路径类型"""
        if isinstance(value, (str, Path)):
            path_str = str(value)
            # 展开用户目录
            expanded = os.path.expanduser(path_str) if isinstance(path_str, str) else path_str
            return ValidationResult(
                valid=True,
                fixed_value=str(expanded),
            )
        return ValidationResult(
            valid=False,
            errors=[f"期望路径类型，实际为 {type(value).__name__}"],
        )

    def _validate_enum(self, value: Any, node: ConfigSchemaNode) -> ValidationResult:
        """验证枚举类型"""
        if node.enum is None:
            return ValidationResult(valid=True, fixed_value=value)
        if value in node.enum:
            return ValidationResult(valid=True, fixed_value=value)
        # 尝试不区分大小写的字符串匹配
        if isinstance(value, str):
            lower_val = value.lower()
            for e in node.enum:
                if isinstance(e, str) and e.lower() == lower_val:
                    return ValidationResult(
                        valid=True,
                        warnings=[f"枚举值大小写不敏感匹配: {value} -> {e}"],
                        fixed_value=e,
                    )
        return ValidationResult(
            valid=False,
            errors=[
                f"值 {value!r} 不在允许的枚举值中: {node.enum}"
            ],
        )

    # --------------------------------------------------------------------
    # 文档生成
    # --------------------------------------------------------------------

    def generate_documentation(self) -> str:
        """生成配置文档（Markdown格式）"""
        lines = ["# 配置项文档\n"]

        # 按分类组织
        categories: dict[str, list[tuple[str, ConfigSchemaNode]]] = {}
        for key, node in self._schema.items():
            cat = node.category or "general"
            if cat not in categories:
                categories[cat] = []
            categories[cat].append((key, node))

        for cat, items in categories.items():
            lines.append(f"\n## {cat}\n")
            lines.append("| 配置项 | 类型 | 必填 | 默认值 | 说明 |")
            lines.append("|--------|------|------|--------|------|")
            for key, node in items:
                required = "是" if node.required else "否"
                default = f"`{node.default}`" if node.default is not None else "-"
                desc = node.description or ""
                lines.append(f"| `{key}` | {node.type} | {required} | {default} | {desc} |")

        return "\n".join(lines)

    def get_defaults(self) -> dict[str, Any]:
        """获取所有默认值"""
        defaults = {}
        for key, node in self._schema.items():
            if node.default is not None:
                defaults[key] = node.default
        return defaults


# ============================================================================
# 项目默认配置Schema
# ============================================================================

def build_default_schema() -> dict[str, ConfigSchemaNode]:
    """构建项目默认配置Schema"""
    return {
        "environment": ConfigSchemaNode(
            type="enum",
            enum=["development", "test", "production"],
            default="development",
            description="运行环境",
            category="基础配置",
        ),
        "version": ConfigSchemaNode(
            type="string",
            default="1.0.0",
            description="项目版本号",
            category="基础配置",
        ),
        # 目录配置
        "directories.video_library": ConfigSchemaNode(
            type="path",
            default="D:/AE-Work/视频素材库",
            description="视频素材库目录",
            category="目录配置",
        ),
        "directories.audio_library": ConfigSchemaNode(
            type="path",
            default="D:/AE-Work/音频素材库",
            description="音频素材库目录",
            category="目录配置",
        ),
        "directories.output": ConfigSchemaNode(
            type="path",
            default="D:/AE-Work/成品库",
            description="输出目录",
            category="目录配置",
        ),
        "directories.logs": ConfigSchemaNode(
            type="path",
            default="D:/AE-Work/日志与报告",
            description="日志目录",
            category="目录配置",
        ),
        # 工具路径
        "tools.ffmpeg": ConfigSchemaNode(
            type="string",
            default="ffmpeg",
            description="FFmpeg 可执行文件路径",
            category="工具配置",
        ),
        "tools.ffprobe": ConfigSchemaNode(
            type="string",
            default="ffprobe",
            description="FFprobe 可执行文件路径",
            category="工具配置",
        ),
        "tools.yt_dlp": ConfigSchemaNode(
            type="string",
            default="yt-dlp",
            description="yt-dlp 可执行文件路径",
            category="工具配置",
        ),
        # 下载配置
        "download.max_concurrent": ConfigSchemaNode(
            type="int",
            default=3,
            min_value=1,
            max_value=10,
            description="最大并发下载数",
            category="下载配置",
        ),
        "download.timeout": ConfigSchemaNode(
            type="int",
            default=300,
            min_value=30,
            max_value=3600,
            description="下载超时时间（秒）",
            category="下载配置",
        ),
        "download.retries": ConfigSchemaNode(
            type="int",
            default=3,
            min_value=0,
            max_value=10,
            description="下载重试次数",
            category="下载配置",
        ),
        # MCP桥接配置
        "mcp_bridge.poll_interval_ms": ConfigSchemaNode(
            type="int",
            default=1000,
            min_value=100,
            max_value=10000,
            description="MCP桥接轮询间隔（毫秒）",
            category="MCP桥接",
        ),
        "mcp_bridge.command_timeout": ConfigSchemaNode(
            type="int",
            default=30,
            min_value=5,
            max_value=600,
            description="命令执行超时时间（秒）",
            category="MCP桥接",
        ),
        "mcp_bridge.signature_enabled": ConfigSchemaNode(
            type="bool",
            default=True,
            description="是否启用命令签名验证",
            category="MCP桥接",
        ),
        # 音频配置
        "audio.default_sample_rate": ConfigSchemaNode(
            type="int",
            default=44100,
            min_value=8000,
            max_value=192000,
            description="默认采样率",
            category="音频配置",
        ),
        # 质量阈值
        "quality.min_psnr": ConfigSchemaNode(
            type="float",
            default=30.0,
            min_value=0,
            max_value=60,
            description="PSNR 最低阈值 (dB)",
            category="质量验收",
        ),
        "quality.min_ssim": ConfigSchemaNode(
            type="float",
            default=0.90,
            min_value=0,
            max_value=1.0,
            description="SSIM 最低阈值",
            category="质量验收",
        ),
        "quality.min_vmaf": ConfigSchemaNode(
            type="float",
            default=80.0,
            min_value=0,
            max_value=100,
            description="VMAF 最低阈值",
            category="质量验收",
        ),
    }


# ============================================================================
# 便捷函数
# ============================================================================

def validate_config(
    config: dict[str, Any],
    schema: dict[str, ConfigSchemaNode] | None = None,
) -> ValidationResult:
    """便捷函数：验证配置

    Args:
        config: 配置字典
        schema: 自定义Schema，None则使用默认Schema

    Returns:
        ValidationResult
    """
    if schema is None:
        schema = build_default_schema()
    validator = ConfigSchemaValidator(schema)
    return validator.validate(config)


def validate_single(
    value: Any,
    type_name: str,
    **kwargs,
) -> ValidationResult:
    """便捷函数：验证单个值

    Args:
        value: 待验证的值
        type_name: 类型名称
        **kwargs: 传递给 ConfigSchemaNode 的其他参数

    Returns:
        ValidationResult
    """
    node = ConfigSchemaNode(type=type_name, **kwargs)
    validator = ConfigSchemaValidator({})
    return validator.validate_value(value, node)


# ============================================================================
# 需要在 _validate_path 中导入 os
# ============================================================================
import os  # noqa: E402
