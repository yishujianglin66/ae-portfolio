# -*- coding: utf-8 -*-
"""
test_tool_registration.py
MCP 工具注册验证 - 检查 25 个 MCP 工具是否都注册到了 server.tool() 调用

测试目的：
    验证 mcp-extension/index-additions.ts 中通过 registerNewTools() 函数
    注册的 MCP 工具数量与命名是否符合预期。该文件使用 zod schema 定义
    每个工具的参数，并通过 server.tool(name, description, schema, handler)
    形式注册到 MCP server。

检查策略：
    1. 解析 index-additions.ts，提取所有 server.tool() 调用的工具名
    2. 验证工具数量为 25
    3. 验证每个工具名都是 kebab-case 格式（MCP 协议约定）
    4. 验证每个工具都有描述字符串和 zod schema
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

# 项目根目录：本文件位于 mcp-extension/test/，向上两级即为根目录
PROJECT_ROOT = Path(__file__).resolve().parents[2]
INDEX_ADDITIONS_FILE = PROJECT_ROOT / "mcp-extension" / "index-additions.ts"

# 25 个 MCP 工具的预期名称（kebab-case 格式，与 server.tool() 调用一致）
EXPECTED_TOOL_NAMES = [
    "add-effect-with-keyframes",
    "set-keyframe-easing",
    "batch-add-effects",
    "set-blend-mode",
    "set-track-matte",
    "set-parent-layer",
    "add-adjustment-layer",
    "add-precomp",
    "import-footage",
    "set-motion-blur",
    "add-mask-with-shape",
    "execute-atom-script",
    "get-effect-properties",
    "set-effect-keyframes",
    "create-e2e-music-video",
    "apply-newton-dynamics",
    "add-text-layer",
    "add-shape-layer",
    "add-camera",
    "add-light",
    "apply-lut",
    "enable-time-remap",
    "apply-saber",
    "apply-particular",
    "apply-optical-flares",
]


def _read_index_additions() -> str:
    """读取 index-additions.ts 文件内容"""
    assert INDEX_ADDITIONS_FILE.exists(), f"index-additions.ts 不存在: {INDEX_ADDITIONS_FILE}"
    return INDEX_ADDITIONS_FILE.read_text(encoding="utf-8")


def _extract_tool_names(content: str) -> list[str]:
    """
    从 index-additions.ts 内容中提取所有 server.tool() 调用的工具名。
    工具名是 server.tool( 后的第一个字符串字面量。
    """
    # 匹配 server.tool( 后紧跟字符串字面量（双引号或单引号）
    # 允许多行空白
    pattern = re.compile(
        r"server\.tool\s*\(\s*"
        r'(?:"([^"]+)"|\'([^\']+)\'|`([^`]+)`)'
        r"\s*,",
        re.MULTILINE,
    )
    names: list[str] = []
    for match in pattern.finditer(content):
        # 三种引号情况，取非 None 的那个
        name = match.group(1) or match.group(2) or match.group(3)
        if name:
            names.append(name)
    return names


def test_index_additions_file_exists():
    """测试1：index-additions.ts 文件存在"""
    assert INDEX_ADDITIONS_FILE.exists(), (
        f"index-additions.ts 文件不存在: {INDEX_ADDITIONS_FILE}"
    )
    assert INDEX_ADDITIONS_FILE.stat().st_size > 0, "index-additions.ts 文件为空"


def test_register_new_tools_function_exists():
    """测试2：registerNewTools 函数定义存在"""
    content = _read_index_additions()
    assert "function registerNewTools" in content, (
        "registerNewTools 函数未定义 - 25 个工具注册的入口缺失"
    )
    # 验证函数是导出的
    assert "export function registerNewTools" in content, (
        "registerNewTools 未导出 - 外部无法调用此函数完成注册"
    )


def test_tool_count_is_25():
    """测试3：注册的工具数量恰好为 25"""
    content = _read_index_additions()
    names = _extract_tool_names(content)
    assert len(names) == 25, (
        f"工具数量不为 25，实际为 {len(names)}，工具列表: {names}"
    )


def test_all_expected_tools_registered():
    """测试4：所有 25 个预期工具名都被注册"""
    content = _read_index_additions()
    actual_names = set(_extract_tool_names(content))
    expected_names = set(EXPECTED_TOOL_NAMES)
    missing = expected_names - actual_names
    assert not missing, (
        f"缺失工具注册: {sorted(missing)}"
    )


def test_no_unexpected_tools_registered():
    """测试5：没有意外的工具被注册（数量与名称完全匹配）"""
    content = _read_index_additions()
    actual_names = set(_extract_tool_names(content))
    expected_names = set(EXPECTED_TOOL_NAMES)
    extra = actual_names - expected_names
    assert not extra, (
        f"发现非预期工具: {sorted(extra)}"
    )


def test_tool_names_are_kebab_case():
    """测试6：所有工具名均为 kebab-case 格式（MCP 协议约定）"""
    content = _read_index_additions()
    names = _extract_tool_names(content)
    # kebab-case: 仅小写字母、数字、连字符；不能以连字符开头或结尾
    kebab_pattern = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
    invalid = [n for n in names if not kebab_pattern.match(n)]
    assert not invalid, (
        f"工具名不符合 kebab-case 格式: {invalid}"
    )


def test_each_tool_has_description_and_schema():
    """测试7：每个工具调用都包含描述字符串和 zod schema 参数"""
    content = _read_index_additions()
    # server.tool(name, description, schema, handler) 标准模式
    # 解析每个 server.tool 块
    # 简单策略：统计 server.tool( 后紧跟字符串字面量的数量
    # 与 z.string() / z.number() / z.object() 等 schema 调用的存在性
    tool_blocks = re.split(r"server\.tool\s*\(", content)[1:]  # 跳过第一段（函数声明前）
    assert len(tool_blocks) == 25, f"server.tool 块数量不为 25: {len(tool_blocks)}"

    missing_desc: list[int] = []
    missing_schema: list[int] = []
    for idx, block in enumerate(tool_blocks, start=1):
        # 每个块应包含描述字符串（第二个参数）和 z.xxx() schema 调用
        if "z.string()" not in block and "z.number()" not in block and "z.record" not in block:
            missing_schema.append(idx)
        # 描述字符串：第二个字符串字面量（在 schema 之前）
        # 简单检查：包含至少两个字符串字面量
        string_literals = re.findall(r'"[^"]{5,}"', block[:2000])
        if len(string_literals) < 2:
            missing_desc.append(idx)

    assert not missing_desc, f"工具块缺失描述字符串: {missing_desc}"
    assert not missing_schema, f"工具块缺失 zod schema: {missing_schema}"


def test_each_tool_has_async_handler():
    """测试8：每个工具都注册了 async handler（返回 Promise）"""
    content = _read_index_additions()
    # 每个 server.tool 调用应包含 async ({...}) => { 或 async function
    # 由于代码风格统一使用箭头函数（但 .ts 文件允许 ES6），统计 async 数量
    async_count = len(re.findall(r"async\s*\(\s*\{", content))
    assert async_count >= 25, (
        f"async handler 数量不足 25，实际 {async_count}"
    )


def test_call_aescript_invoked_for_each_tool():
    """测试9：每个工具的 handler 都调用 callAEScript 执行 JSX 脚本"""
    content = _read_index_additions()
    call_count = len(re.findall(r"callAEScript\s*\(", content))
    assert call_count >= 25, (
        f"callAEScript 调用次数不足 25，实际 {call_count}"
    )


def test_parse_aeresult_used_for_each_tool():
    """测试10：每个工具的 handler 都使用 parseAEResult 解析返回值"""
    content = _read_index_additions()
    parse_count = len(re.findall(r"parseAEResult\s*\(", content))
    assert parse_count >= 25, (
        f"parseAEResult 调用次数不足 25，实际 {parse_count}"
    )


# ============================================================================
# 异步测试示例：使用 asyncio 异步读取文件并验证工具注册
# 说明：本项目所有 I/O 操作优先使用 async/await（见 project-conventions.md）
# pytest.ini 中 asyncio_mode = auto 已启用，async 测试函数自动应用 pytest.mark.asyncio
# ============================================================================
import asyncio


async def _read_file_async(file_path: Path) -> str:
    """异步读取文件内容（使用 asyncio.to_thread 包装同步 I/O）"""
    return await asyncio.to_thread(file_path.read_text, encoding="utf-8")


async def test_async_index_additions_has_25_tools():
    """测试11（异步）：异步读取 index-additions.ts 并验证工具数量为 25"""
    content = await _read_file_async(INDEX_ADDITIONS_FILE)
    names = _extract_tool_names(content)
    assert len(names) == 25, f"异步读取后工具数量不为 25: {len(names)}"


async def test_async_all_tool_names_valid():
    """测试12（异步）：异步读取并验证所有工具名为 kebab-case 格式"""
    content = await _read_file_async(INDEX_ADDITIONS_FILE)
    names = _extract_tool_names(content)
    kebab_pattern = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
    invalid = [n for n in names if not kebab_pattern.match(n)]
    assert not invalid, f"异步验证: 工具名不符合 kebab-case: {invalid}"
