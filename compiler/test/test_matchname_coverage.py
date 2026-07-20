# -*- coding: utf-8 -*-
"""
test_matchname_coverage.py
matchName 覆盖完整性验证 - 检查第三方插件 matchName 映射完整

测试目的：
    验证 compiler/src/phase3/effect-name-map.ts 中的 EFFECT_MAP
    完整覆盖了项目中使用的所有第三方插件 matchName（Saber / Particular /
    OpticalFlares / Element3D / Plexus / Shine 等）。

    matchName 是 AE 效果的程序唯一标识，错误的 matchName 会导致
    Effects.addProperty() 调用失败。本测试确保：
      1. 编译器 (compiler/) 的 EFFECT_MAP 包含所有第三方插件
      2. MCP 扩展 (mcp-extension/) 的 JSX 脚本中引用的 matchName
         都能在 EFFECT_MAP 中找到
      3. validator.ts 的有效 matchName 列表包含所有第三方插件

检查策略：
    1. 解析 effect-name-map.ts 中的 EFFECT_MAP，提取所有 matchName
    2. 验证关键第三方插件 matchName 都在 EFFECT_MAP 中
    3. 验证 mcp-extension JSX 脚本中引用的第三方 matchName 都在 EFFECT_MAP 中
    4. 验证 validator.ts 的 VALID_MATCHNAMES 列表包含所有第三方插件
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parents[2]
EFFECT_NAME_MAP_FILE = PROJECT_ROOT / "compiler" / "src" / "phase3" / "effect-name-map.ts"
VALIDATOR_FILE = PROJECT_ROOT / "compiler" / "src" / "validator.ts"
MCP_SCRIPTS_DIR = PROJECT_ROOT / "mcp-extension" / "scripts"

# 第三方插件及其预期 matchName（核心覆盖清单）
# 这些是项目中实际使用的第三方插件，必须完整覆盖
THIRD_PARTY_PLUGINS = {
    "Saber": {
        "matchName": "VC Saber",
        "source": "vc",
        "vendor": "Video Copilot",
    },
    "Optical Flares": {
        "matchName": "VC Optical Flares",
        "source": "vc",
        "vendor": "Video Copilot",
    },
    "Element 3D": {
        "matchName": "VC Element",
        "source": "vc",
        "vendor": "Video Copilot",
    },
    "Particular": {
        "matchName": "ACP Particular",
        "source": "trapcode",
        "vendor": "Trapcode (Red Giant)",
    },
    "Plexus": {
        "matchName": "ACP Plexus",
        "source": "trapcode",
        "vendor": "Trapcode (Red Giant)",
    },
    "Trapcode Shine": {
        "matchName": "TC Shine",
        "source": "trapcode",
        "vendor": "Trapcode (Red Giant)",
    },
}


def _read_effect_name_map() -> str:
    """读取 effect-name-map.ts 文件内容"""
    assert EFFECT_NAME_MAP_FILE.exists(), (
        f"effect-name-map.ts 不存在: {EFFECT_NAME_MAP_FILE}"
    )
    return EFFECT_NAME_MAP_FILE.read_text(encoding="utf-8")


def _extract_matchnames_from_effect_map(content: str) -> set[str]:
    """
    从 EFFECT_MAP 中提取所有 matchName 值。
    格式: matchName: "XXX",
    """
    pattern = re.compile(r'matchName:\s*"([^"]+)"')
    return set(pattern.findall(content))


def _extract_matchnames_from_validator(content: str) -> set[str]:
    """
    从 validator.ts 中提取 VALID_MATCHNAMES 数组的内容。
    数组中的字符串字面量都是有效的 matchName。

    matchName 格式多样：
      - 全大写前缀+大写单词：ADBE Gaussian Blur 2, ACP Particular
      - 含小写字母：VC Saber, TC Shine, VC Optical Flares
      - 含数字/特殊字符：ADBE Vibrance, ACP 3D Stroke
    因此采用宽松匹配：双引号包裹、长度>=4、以大写字母开头。
    """
    # 提取所有双引号字符串字面量，然后过滤出看起来像 matchName 的
    all_strings = set(re.findall(r'"([^"]{3,})"', content))
    # matchName 通常以大写字母开头（ADBE/CC/ACP/VC/TC/S_ 等前缀）
    # 且不包含中文、不全是小写、不是描述性句子
    matchnames: set[str] = set()
    for s in all_strings:
        # 跳过明显不是 matchName 的字符串（含空格但首字母小写，或含中文）
        if not s:
            continue
        if not s[0].isupper():
            continue
        # 跳过含中文字符的（描述文本）
        if any('\u4e00' <= ch <= '\u9fff' for ch in s):
            continue
        # 跳过含句号/问号的（描述性句子）
        if '.' in s and not s.startswith('ADBE') and not s.startswith('S_'):
            # ADBE 类 matchName 不含句号，但 S_xxx 也不含
            continue
        # matchName 不应包含等号、分号、大括号
        if any(ch in s for ch in ['=', ';', '{', '}', '(', ')']):
            continue
        matchnames.add(s)
    return matchnames


def _extract_matchnames_from_jsx_scripts() -> set[str]:
    """
    扫描 mcp-extension/scripts/ 下所有 JSX 文件，提取所有引用的 matchName。
    主要扫描 addProperty("...") 调用中的字符串参数。
    """
    matchnames: set[str] = set()
    if not MCP_SCRIPTS_DIR.exists():
        return matchnames

    # 模式1: Effects.addProperty("XXX") 或 .addProperty('XXX')
    add_property_pattern = re.compile(r'\.addProperty\s*\(\s*"([^"]+)"')
    # 模式2: matchNames = ["XXX", "YYY", ...]
    array_pattern = re.compile(r'matchNames\s*=\s*\[([^\]]+)\]')
    string_literal_pattern = re.compile(r'"([^"]+)"')

    for jsx_file in MCP_SCRIPTS_DIR.glob("*.jsx"):
        try:
            content = jsx_file.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        # 提取 addProperty 调用
        for match in add_property_pattern.finditer(content):
            matchnames.add(match.group(1))

        # 提取 matchNames 数组
        for arr_match in array_pattern.finditer(content):
            arr_body = arr_match.group(1)
            for str_match in string_literal_pattern.finditer(arr_body):
                matchnames.add(str_match.group(1))

    return matchnames


# ============================================================================
# 测试1：EFFECT_MAP 文件存在
# ============================================================================
def test_effect_name_map_file_exists():
    """测试1：effect-name-map.ts 文件存在且非空"""
    assert EFFECT_NAME_MAP_FILE.exists(), (
        f"effect-name-map.ts 不存在: {EFFECT_NAME_MAP_FILE}"
    )
    assert EFFECT_NAME_MAP_FILE.stat().st_size > 0, "effect-name-map.ts 文件为空"


def test_validator_file_exists():
    """测试2：validator.ts 文件存在（含 VALID_MATCHNAMES 列表）"""
    assert VALIDATOR_FILE.exists(), f"validator.ts 不存在: {VALIDATOR_FILE}"
    assert VALIDATOR_FILE.stat().st_size > 0, "validator.ts 文件为空"


# ============================================================================
# 测试3：EFFECT_MAP 覆盖所有第三方插件
# ============================================================================
# 修复记录：effect-name-map.ts 已补全 Saber 条目（VC Saber），xfail 标记已移除
def test_effect_map_covers_all_third_party_plugins():
    """测试3：EFFECT_MAP 覆盖所有第三方插件（Saber/Particular/OpticalFlares/Element3D/Plexus/Shine）"""
    content = _read_effect_name_map()
    actual_matchnames = _extract_matchnames_from_effect_map(content)

    missing: list[str] = []
    for plugin_name, info in THIRD_PARTY_PLUGINS.items():
        if info["matchName"] not in actual_matchnames:
            missing.append(f"{plugin_name} ({info['matchName']})")

    assert not missing, (
        f"EFFECT_MAP 缺失第三方插件 matchName: {missing}\n"
        f"当前 EFFECT_MAP 包含的 matchName: {sorted(actual_matchnames)}"
    )


# ============================================================================
# 测试4：validator.ts 的有效 matchName 列表包含所有第三方插件
# ============================================================================
def test_validator_includes_third_party_plugins():
    """测试4：validator.ts 的 VALID_MATCHNAMES 包含所有第三方插件"""
    content = VALIDATOR_FILE.read_text(encoding="utf-8")
    valid_matchnames = _extract_matchnames_from_validator(content)

    missing: list[str] = []
    for plugin_name, info in THIRD_PARTY_PLUGINS.items():
        if info["matchName"] not in valid_matchnames:
            missing.append(f"{plugin_name} ({info['matchName']})")

    assert not missing, (
        f"validator.ts 缺失第三方插件 matchName: {missing}"
    )


# ============================================================================
# 测试5：MCP JSX 脚本引用的第三方 matchName 都在 EFFECT_MAP 中
# ============================================================================
# 已知情况：JSX 脚本使用 matchName 数组作为 fallback 列表，例如：
#   applySaber.jsx:        ["VC Saber", "ADBE VC Saber", "ACP VC Saber"]
#   applyOpticalFlares.jsx: ["Optical Flares", "VC Optical Flares", "ACP Optical Flares"]
#   applyParticular.jsx:    ["Particular", "Trapcode Particular", "ACP Particular", "RG Particular"]
# 数组中第一个是 primary matchName（应在 EFFECT_MAP 中），其余是 fallback 变体
# （可能不在 EFFECT_MAP 中，这是预期的容错设计）
# 因此本测试仅检查 primary matchName 是否在 EFFECT_MAP 中
def test_jsx_matchnames_covered_by_effect_map():
    """测试5：MCP JSX 脚本引用的第三方 primary matchName 都在 EFFECT_MAP 中"""
    effect_map_content = _read_effect_name_map()
    effect_map_matchnames = _extract_matchnames_from_effect_map(effect_map_content)

    # 从 JSX 脚本中提取每个 matchNames 数组的第一个元素（primary matchName）
    primary_matchnames: set[str] = set()
    if MCP_SCRIPTS_DIR.exists():
        array_pattern = re.compile(r'matchNames\s*=\s*\[([^\]]+)\]')
        for jsx_file in MCP_SCRIPTS_DIR.glob("*.jsx"):
            try:
                content = jsx_file.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for arr_match in array_pattern.finditer(content):
                arr_body = arr_match.group(1)
                # 提取数组中的所有字符串字面量
                strings = re.findall(r'"([^"]+)"', arr_body)
                if strings:
                    # 第一个是 primary matchName
                    primary_matchnames.add(strings[0])

    # 仅检查第三方插件相关的 primary matchName
    third_party_prefixes = ("VC ", "ACP ", "TC ")
    jsx_third_party_primary = {
        m for m in primary_matchnames
        if any(m.startswith(prefix) for prefix in third_party_prefixes)
    }

    missing = jsx_third_party_primary - effect_map_matchnames
    # 修复记录：effect-name-map.ts 已补全 Saber 条目（VC Saber），无需再 xfail
    assert not missing, (
        f"JSX 脚本的 primary matchName 未在 EFFECT_MAP 中找到: {sorted(missing)}"
    )


# ============================================================================
# 测试6：第三方插件有完整的 paramMap（参数映射）
# ============================================================================
# 修复记录：effect-name-map.ts 已补全 Saber 条目（含 paramMap），xfail 标记已移除
def test_third_party_plugins_have_param_maps():
    """测试6：每个第三方插件在 EFFECT_MAP 中都有 paramMap 参数映射"""
    content = _read_effect_name_map()
    # 检查每个第三方插件的 matchName 周围是否有 paramMap 定义
    for plugin_name, info in THIRD_PARTY_PLUGINS.items():
        matchname = info["matchName"]
        # 找到 matchName 出现的位置
        idx = content.find(f'matchName: "{matchname}"')
        assert idx >= 0, f"未找到 {plugin_name} 的 matchName 定义"
        # 截取该条目后续 800 字符，检查是否包含 paramMap
        snippet = content[idx:idx + 800]
        assert "paramMap" in snippet, (
            f"{plugin_name} ({matchname}) 缺少 paramMap 参数映射定义"
        )


# ============================================================================
# 测试7：第三方插件 source 字段正确
# ============================================================================
# 修复记录：effect-name-map.ts 已补全 Saber 条目（source="vc"），xfail 标记已移除
def test_third_party_plugins_source_correct():
    """测试7：第三方插件的 source 字段标注正确（vc / trapcode）"""
    content = _read_effect_name_map()
    for plugin_name, info in THIRD_PARTY_PLUGINS.items():
        matchname = info["matchName"]
        expected_source = info["source"]
        # 找到 matchName 出现的位置
        idx = content.find(f'matchName: "{matchname}"')
        assert idx >= 0, f"未找到 {plugin_name} 的 matchName 定义"
        # 截取该条目后续 500 字符，检查 source 字段
        snippet = content[idx:idx + 500]
        assert f'source: "{expected_source}"' in snippet, (
            f"{plugin_name} ({matchname}) 的 source 字段不是 '{expected_source}'"
        )


# ============================================================================
# 测试8：EFFECT_MAP 中至少有 30 个效果映射条目
# ============================================================================
def test_effect_map_has_minimum_entries():
    """测试8：EFFECT_MAP 至少有 30 个效果映射条目（覆盖原生+第三方）"""
    content = _read_effect_name_map()
    matchnames = _extract_matchnames_from_effect_map(content)
    assert len(matchnames) >= 30, (
        f"EFFECT_MAP 条目数 {len(matchnames)} < 30，覆盖不足"
    )


# ============================================================================
# 测试9：第三方插件在 MCP JSX 脚本中有对应的应用工具
# ============================================================================
def test_third_party_plugins_have_mcp_tools():
    """测试9：核心第三方插件在 MCP JSX 脚本中有对应的应用工具

    Saber / Particular / OpticalFlares 都应该有独立的 applyXxx.jsx 脚本
    """
    expected_tool_files = {
        "Saber": "applySaber.jsx",
        "Particular": "applyParticular.jsx",
        "Optical Flares": "applyOpticalFlares.jsx",
    }
    missing: list[str] = []
    for plugin_name, file_name in expected_tool_files.items():
        file_path = MCP_SCRIPTS_DIR / file_name
        if not file_path.exists():
            missing.append(f"{plugin_name} -> {file_name}")
    assert not missing, f"缺失第三方插件应用工具: {missing}"


# ============================================================================
# 测试10：MCP 工具注册中包含第三方插件工具
# ============================================================================
def test_mcp_registers_third_party_tools():
    """测试10：MCP 工具注册中包含 Saber/Particular/OpticalFlares 工具"""
    index_additions = PROJECT_ROOT / "mcp-extension" / "index-additions.ts"
    if not index_additions.exists():
        pytest.skip("index-additions.ts 不存在")
    content = index_additions.read_text(encoding="utf-8")

    expected_tool_names = [
        "apply-saber",
        "apply-particular",
        "apply-optical-flares",
    ]
    missing: list[str] = []
    for tool_name in expected_tool_names:
        if f'"{tool_name}"' not in content:
            missing.append(tool_name)
    assert not missing, f"MCP 工具注册缺失第三方插件工具: {missing}"


# ============================================================================
# 异步测试示例：使用 asyncio 异步读取并验证 matchName 覆盖
# pytest.ini 中 asyncio_mode = auto 已启用，async 测试函数自动应用 pytest.mark.asyncio
# ============================================================================
import asyncio


async def _read_file_async(file_path: Path) -> str:
    """异步读取文件内容"""
    return await asyncio.to_thread(file_path.read_text, encoding="utf-8")


async def test_async_effect_map_has_entries():
    """测试11（异步）：异步读取 EFFECT_MAP 并验证有条目"""
    content = await _read_file_async(EFFECT_NAME_MAP_FILE)
    matchnames = _extract_matchnames_from_effect_map(content)
    assert len(matchnames) >= 30, (
        f"异步验证: EFFECT_MAP 条目数 {len(matchnames)} < 30"
    )


async def test_async_validator_includes_optical_flares():
    """测试12（异步）：异步读取 validator.ts 并验证包含 VC Optical Flares"""
    content = await _read_file_async(VALIDATOR_FILE)
    valid_matchnames = _extract_matchnames_from_validator(content)
    assert "VC Optical Flares" in valid_matchnames, (
        "异步验证: validator.ts 缺失 VC Optical Flares"
    )
