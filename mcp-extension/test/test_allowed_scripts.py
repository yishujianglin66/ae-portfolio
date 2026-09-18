# -*- coding: utf-8 -*-
"""
test_allowed_scripts.py
allowed_scripts 白名单验证 - 检查 25 个 JSX 脚本名都注册到白名单

测试目的：
    验证 mcp-extension/index-additions.ts 中的 NEW_ALLOWED_SCRIPTS 数组
    包含全部 25 个 MCP 工具对应的 JSX 脚本名（驼峰命名，不带 .jsx 后缀）。
    这些名称将被合并到 after-effects-mcp-main/src/index.ts 的 allowedScripts
    数组中，作为 MCP Bridge 调用 JSX 脚本时的安全白名单。

检查策略：
    1. 解析 NEW_ALLOWED_SCRIPTS 数组的内容
    2. 验证数组长度为 25
    3. 验证每个名称都是 camelCase 格式
    4. 验证每个名称都有对应的 .jsx 文件
    5. 验证数组中无重复项
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parents[2]
INDEX_ADDITIONS_FILE = PROJECT_ROOT / "mcp-extension" / "index-additions.ts"
SCRIPTS_DIR = PROJECT_ROOT / "mcp-extension" / "scripts"

# 25 个预期脚本名（camelCase，与 NEW_ALLOWED_SCRIPTS 数组一致）
EXPECTED_SCRIPT_NAMES = [
    "addEffectWithKeyframes",
    "setKeyframeEasing",
    "batchAddEffects",
    "setBlendMode",
    "setTrackMatte",
    "setParentLayer",
    "addAdjustmentLayer",
    "addPrecomp",
    "importFootage",
    "setMotionBlur",
    "addMaskWithShape",
    "executeAtomScript",
    "getEffectProperties",
    "setEffectKeyframes",
    "applyNewtonDynamics",
    "createE2EMusicVideo",
    "addTextLayer",
    "addShapeLayer",
    "addCamera",
    "addLight",
    "applyLUT",
    "enableTimeRemap",
    "applySaber",
    "applyParticular",
    "applyOpticalFlares",
]


def _read_index_additions() -> str:
    """读取 index-additions.ts 文件内容"""
    assert INDEX_ADDITIONS_FILE.exists(), f"index-additions.ts 不存在: {INDEX_ADDITIONS_FILE}"
    return INDEX_ADDITIONS_FILE.read_text(encoding="utf-8")


def _extract_new_allowed_scripts(content: str) -> list[str]:
    """
    从 index-additions.ts 中提取 NEW_ALLOWED_SCRIPTS 数组的内容。
    数组定义为: export const NEW_ALLOWED_SCRIPTS = [ ... ];
    """
    # 匹配 NEW_ALLOWED_SCRIPTS = [ ... ];
    pattern = re.compile(
        r"NEW_ALLOWED_SCRIPTS\s*=\s*\[(.*?)\]\s*;",
        re.DOTALL,
    )
    match = pattern.search(content)
    assert match is not None, "未找到 NEW_ALLOWED_SCRIPTS 数组定义"

    array_body = match.group(1)
    # 提取所有字符串字面量
    names = re.findall(r'"([^"]+)"', array_body)
    return names


def test_new_allowed_scripts_array_exists():
    """测试1：NEW_ALLOWED_SCRIPTS 数组定义存在"""
    content = _read_index_additions()
    assert "NEW_ALLOWED_SCRIPTS" in content, "NEW_ALLOWED_SCRIPTS 未定义"
    assert "export const NEW_ALLOWED_SCRIPTS" in content, (
        "NEW_ALLOWED_SCRIPTS 未导出 - install.ps1 无法引用此数组"
    )


def test_allowed_scripts_count_is_25():
    """测试2：NEW_ALLOWED_SCRIPTS 数组长度为 25"""
    content = _read_index_additions()
    names = _extract_new_allowed_scripts(content)
    assert len(names) == 25, (
        f"NEW_ALLOWED_SCRIPTS 长度不为 25，实际 {len(names)}: {names}"
    )


def test_all_expected_scripts_in_whitelist():
    """测试3：所有 25 个预期脚本名都在白名单中"""
    content = _read_index_additions()
    actual = set(_extract_new_allowed_scripts(content))
    expected = set(EXPECTED_SCRIPT_NAMES)
    missing = expected - actual
    assert not missing, f"白名单缺失脚本: {sorted(missing)}"


def test_no_unexpected_scripts_in_whitelist():
    """测试4：白名单中无非预期脚本（数量与名称完全匹配）"""
    content = _read_index_additions()
    actual = set(_extract_new_allowed_scripts(content))
    expected = set(EXPECTED_SCRIPT_NAMES)
    extra = actual - expected
    assert not extra, f"白名单中存在非预期脚本: {sorted(extra)}"


def test_no_duplicates_in_whitelist():
    """测试5：白名单中无重复项"""
    content = _read_index_additions()
    names = _extract_new_allowed_scripts(content)
    seen: dict[str, int] = {}
    duplicates: list[str] = []
    for n in names:
        seen[n] = seen.get(n, 0) + 1
        if seen[n] == 2:
            duplicates.append(n)
    assert not duplicates, f"白名单中存在重复项: {duplicates}"


def test_script_names_are_camel_case():
    """测试6：所有脚本名为 camelCase 格式（JSX 函数命名约定）"""
    content = _read_index_additions()
    names = _extract_new_allowed_scripts(content)
    # camelCase: 首字母小写，后续单词首字母大写，无下划线/连字符
    camel_pattern = re.compile(r"^[a-z][a-zA-Z0-9]*$")
    invalid = [n for n in names if not camel_pattern.match(n)]
    assert not invalid, f"脚本名不符合 camelCase: {invalid}"


def test_each_whitelist_script_has_jsx_file():
    """测试7：每个白名单脚本名都有对应的 .jsx 文件存在"""
    content = _read_index_additions()
    names = _extract_new_allowed_scripts(content)
    missing_files: list[str] = []
    for name in names:
        jsx_file = SCRIPTS_DIR / f"{name}.jsx"
        if not jsx_file.exists():
            missing_files.append(f"{name}.jsx")
    assert not missing_files, f"缺失 JSX 文件: {missing_files}"


def test_install_ps1_references_allowed_scripts():
    """测试8：install.ps1 引用了 NEW_ALLOWED_SCRIPTS（合并到主项目的入口）"""
    install_ps1 = PROJECT_ROOT / "mcp-extension" / "install.ps1"
    if not install_ps1.exists():
        pytest.skip("install.ps1 不存在，跳过此检查")
    content = install_ps1.read_text(encoding="utf-8")
    # install.ps1 应引用 allowedScripts 或 NEW_ALLOWED_SCRIPTS
    assert "allowedScripts" in content or "NEW_ALLOWED_SCRIPTS" in content, (
        "install.ps1 未引用 allowedScripts - 无法将白名单合并到主项目"
    )


# ============================================================================
# 异步测试示例：使用 asyncio 异步读取并验证白名单
# pytest.ini 中 asyncio_mode = auto 已启用，async 测试函数自动应用 pytest.mark.asyncio
# ============================================================================
import asyncio


async def _read_file_async(file_path: Path) -> str:
    """异步读取文件内容"""
    return await asyncio.to_thread(file_path.read_text, encoding="utf-8")


async def test_async_whitelist_has_25_entries():
    """测试9（异步）：异步读取并验证白名单长度为 25"""
    content = await _read_file_async(INDEX_ADDITIONS_FILE)
    names = _extract_new_allowed_scripts(content)
    assert len(names) == 25, f"异步读取后白名单长度不为 25: {len(names)}"


async def test_async_whitelist_no_duplicates():
    """测试10（异步）：异步读取并验证白名单无重复"""
    content = await _read_file_async(INDEX_ADDITIONS_FILE)
    names = _extract_new_allowed_scripts(content)
    assert len(names) == len(set(names)), "异步验证: 白名单存在重复项"
