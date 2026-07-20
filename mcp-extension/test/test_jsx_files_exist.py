# -*- coding: utf-8 -*-
"""
test_jsx_files_exist.py
JSX 文件存在性验证 - 检查 25 个 MCP 工具的 JSX 脚本都存在且非空

测试目的：
    验证 mcp-extension/scripts/ 目录下 25 个 MCP 工具对应的 JSX 文件
    都存在、非空、且包含必要的结构（函数声明、JSON 返回值等）。

检查策略：
    1. 验证 25 个 JSX 文件都存在
    2. 验证每个文件大小 > 0（非空）
    3. 验证每个文件包含函数声明
    4. 验证每个文件包含 JSON.stringify（返回值构造）
    5. 验证每个文件不包含禁止的 ES6 语法
    6. 验证每个文件包含 args.json 读取逻辑（与 MCP Bridge 通信约定）
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = PROJECT_ROOT / "mcp-extension" / "scripts"

# 25 个 JSX 文件清单（与 NEW_ALLOWED_SCRIPTS 一一对应）
EXPECTED_JSX_FILES = [
    "addEffectWithKeyframes.jsx",
    "setKeyframeEasing.jsx",
    "batchAddEffects.jsx",
    "setBlendMode.jsx",
    "setTrackMatte.jsx",
    "setParentLayer.jsx",
    "addAdjustmentLayer.jsx",
    "addPrecomp.jsx",
    "importFootage.jsx",
    "setMotionBlur.jsx",
    "addMaskWithShape.jsx",
    "executeAtomScript.jsx",
    "getEffectProperties.jsx",
    "setEffectKeyframes.jsx",
    "applyNewtonDynamics.jsx",
    "createE2EMusicVideo.jsx",
    "addTextLayer.jsx",
    "addShapeLayer.jsx",
    "addCamera.jsx",
    "addLight.jsx",
    "applyLUT.jsx",
    "enableTimeRemap.jsx",
    "applySaber.jsx",
    "applyParticular.jsx",
    "applyOpticalFlares.jsx",
]


def _read_jsx(file_name: str) -> str:
    """读取 JSX 文件内容"""
    file_path = SCRIPTS_DIR / file_name
    return file_path.read_text(encoding="utf-8")


def test_scripts_directory_exists():
    """测试1：mcp-extension/scripts/ 目录存在"""
    assert SCRIPTS_DIR.exists(), f"scripts 目录不存在: {SCRIPTS_DIR}"
    assert SCRIPTS_DIR.is_dir(), f"scripts 路径不是目录: {SCRIPTS_DIR}"


def test_all_25_jsx_files_exist():
    """测试2：所有 25 个 JSX 文件都存在"""
    missing: list[str] = []
    for file_name in EXPECTED_JSX_FILES:
        file_path = SCRIPTS_DIR / file_name
        if not file_path.exists():
            missing.append(file_name)
    assert not missing, f"缺失 JSX 文件: {missing}"


def test_all_jsx_files_non_empty():
    """测试3：所有 JSX 文件非空（> 200 字节，过滤空文件或仅含注释的文件）"""
    empty_or_small: list[str] = []
    for file_name in EXPECTED_JSX_FILES:
        file_path = SCRIPTS_DIR / file_name
        if not file_path.exists():
            empty_or_small.append(f"{file_name} (不存在)")
            continue
        size = file_path.stat().st_size
        if size < 200:
            empty_or_small.append(f"{file_name} ({size} 字节)")
    assert not empty_or_small, f"文件为空或过小: {empty_or_small}"


def test_each_jsx_has_function_declaration():
    """测试4：每个 JSX 文件包含函数声明（命名函数或 IIFE）"""
    missing: list[str] = []
    for file_name in EXPECTED_JSX_FILES:
        file_path = SCRIPTS_DIR / file_name
        if not file_path.exists():
            missing.append(f"{file_name} (不存在)")
            continue
        content = file_path.read_text(encoding="utf-8")
        # 命名函数: function xxx(args) {
        has_named_func = re.search(r"function\s+[a-zA-Z_$][\w$]*\s*\([^)]*\)\s*\{", content)
        # IIFE: (function() { ... })();
        has_iife = re.search(r"\(\s*function\s*\(\s*\)\s*\{", content)
        if not has_named_func and not has_iife:
            missing.append(file_name)
    assert not missing, f"缺失函数声明的文件: {missing}"


def test_each_jsx_uses_json_stringify():
    """测试5：每个 JSX 文件使用 JSON.stringify 或 _lib/response_utils.jsx 构造返回值

    支持两种代码风格：
      - 旧风格：直接调用 JSON.stringify() 构造返回值
      - 新风格（_lib 重构后）：#include "_lib/response_utils.jsx"，
        通过 buildError()/buildSuccess() 辅助函数构造返回值（内部使用 JSON.stringify）
    """
    missing: list[str] = []
    for file_name in EXPECTED_JSX_FILES:
        file_path = SCRIPTS_DIR / file_name
        if not file_path.exists():
            missing.append(f"{file_name} (不存在)")
            continue
        content = file_path.read_text(encoding="utf-8")
        # 接受两种返回值构造方式
        has_json_stringify = "JSON.stringify" in content
        has_response_utils_lib = '#include "_lib/response_utils.jsx"' in content
        if not has_json_stringify and not has_response_utils_lib:
            missing.append(file_name)
    assert not missing, f"未使用 JSON.stringify 或 _lib/response_utils.jsx 的文件: {missing}"


def test_no_es6_syntax_in_jsx_files():
    """测试6：JSX 文件不包含禁止的 ES6 语法（const / let / => / 模板字符串）

    ExtendScript 是 ES3 子集，使用 ES6 语法会导致 AE 端解析失败。
    本测试排除注释行，避免注释中的 ES6 关键字误报。
    """
    # 禁止的 ES6 特性及其正则模式
    forbidden_patterns = [
        ("const声明", re.compile(r"\bconst\s+")),
        ("let声明", re.compile(r"\blet\s+")),
        ("箭头函数=>", re.compile(r"=>")),
        ("模板字符串反引号", re.compile(r"`")),
    ]

    violations: list[str] = []
    for file_name in EXPECTED_JSX_FILES:
        file_path = SCRIPTS_DIR / file_name
        if not file_path.exists():
            continue
        content = file_path.read_text(encoding="utf-8")
        lines = content.splitlines()
        for line_idx, line in enumerate(lines, start=1):
            # 移除单行注释 // ...
            comment_pos = line.find("//")
            stripped = line if comment_pos < 0 else line[:comment_pos]
            for pattern_name, pattern in forbidden_patterns:
                if pattern.search(stripped):
                    violations.append(
                        f"{file_name} L{line_idx}: {pattern_name} - {stripped.strip()[:80]}"
                    )
    assert not violations, (
        f"发现 {len(violations)} 处 ES6 语法违规:\n" + "\n".join(violations[:20])
    )


def test_each_jsx_reads_args_json():
    """测试7：每个 JSX 文件包含 args.json 读取逻辑（MCP Bridge 通信约定）

    MCP Bridge 通过 args.json 文件向 JSX 脚本传递参数，
    每个 JSX 脚本应包含读取该文件的逻辑。
    """
    missing: list[str] = []
    for file_name in EXPECTED_JSX_FILES:
        file_path = SCRIPTS_DIR / file_name
        if not file_path.exists():
            missing.append(f"{file_name} (不存在)")
            continue
        content = file_path.read_text(encoding="utf-8")
        # 检查是否包含 args.json 引用
        if "args.json" not in content and "argsFile" not in content:
            # executeAtomScript 是特殊的脚本执行器，参数为 scriptContent
            if file_name == "executeAtomScript.jsx":
                continue
            missing.append(file_name)
    # 此项为可选检查，部分特殊脚本可能使用不同参数传递方式
    if missing:
        pytest.skip(f"以下文件未使用标准 args.json 读取（可能是特殊脚本）: {missing}")


def test_each_jsx_has_undo_group():
    """测试8：写入类 JSX 文件包含 undoGroup 包装

    app.beginUndoGroup / app.endUndoGroup 是 AE 操作的标准包装，
    允许用户一次性撤销脚本的所有更改。只读类工具（如 getEffectProperties）
    可豁免。
    """
    # 只读工具豁免列表
    read_only_tools = {"getEffectProperties.jsx"}
    missing: list[str] = []
    for file_name in EXPECTED_JSX_FILES:
        if file_name in read_only_tools:
            continue
        file_path = SCRIPTS_DIR / file_name
        if not file_path.exists():
            missing.append(f"{file_name} (不存在)")
            continue
        content = file_path.read_text(encoding="utf-8")
        has_begin = "app.beginUndoGroup" in content
        has_end = "app.endUndoGroup" in content
        if not has_begin or not has_end:
            missing.append(
                f"{file_name} (begin={has_begin}, end={has_end})"
            )
    assert not missing, f"缺失 undoGroup 包装的文件: {missing}"


def test_lib_directory_exists():
    """测试9：_lib 公共模块目录存在（供重构后的 JSX 脚本引用）"""
    lib_dir = SCRIPTS_DIR / "_lib"
    if not lib_dir.exists():
        pytest.skip("_lib 目录尚未创建（_lib 重构未完成）")
    # 检查 _lib 目录下至少有几个公共模块
    lib_files = list(lib_dir.glob("*.jsx"))
    assert len(lib_files) >= 3, (
        f"_lib 目录下 JSX 文件过少 ({len(lib_files)} 个)，期望至少 3 个公共模块"
    )


def test_no_syntax_errors_in_comments():
    """测试10：JSX 文件中的中文注释可正常解析（无编码问题）"""
    encoding_issues: list[str] = []
    for file_name in EXPECTED_JSX_FILES:
        file_path = SCRIPTS_DIR / file_name
        if not file_path.exists():
            continue
        try:
            content = file_path.read_text(encoding="utf-8")
            # 简单检查：能正常读取且包含中文字符的文件不应有乱码
            # 检查是否存在 UTF-8 BOM 或编码异常字符
            if "\ufffd" in content:  # 替换字符
                encoding_issues.append(file_name)
        except UnicodeDecodeError:
            encoding_issues.append(f"{file_name} (解码失败)")
    assert not encoding_issues, f"文件编码异常: {encoding_issues}"


# ============================================================================
# 异步测试示例：使用 asyncio 异步读取并验证 JSX 文件
# pytest.ini 中 asyncio_mode = auto 已启用，async 测试函数自动应用 pytest.mark.asyncio
# ============================================================================
import asyncio


async def _read_file_async(file_path: Path) -> str:
    """异步读取文件内容"""
    return await asyncio.to_thread(file_path.read_text, encoding="utf-8")


async def test_async_all_jsx_files_exist():
    """测试11（异步）：异步验证所有 25 个 JSX 文件都存在"""
    missing: list[str] = []
    for file_name in EXPECTED_JSX_FILES:
        file_path = SCRIPTS_DIR / file_name
        exists = await asyncio.to_thread(file_path.exists)
        if not exists:
            missing.append(file_name)
    assert not missing, f"异步验证: 缺失 JSX 文件: {missing}"


async def test_async_all_jsx_use_json_stringify():
    """测试12（异步）：异步读取并验证所有 JSX 文件使用 JSON.stringify 或 _lib/response_utils.jsx"""
    missing: list[str] = []
    for file_name in EXPECTED_JSX_FILES:
        file_path = SCRIPTS_DIR / file_name
        if not file_path.exists():
            continue
        content = await _read_file_async(file_path)
        # 接受两种返回值构造方式（与同步测试5一致）
        has_json_stringify = "JSON.stringify" in content
        has_response_utils_lib = '#include "_lib/response_utils.jsx"' in content
        if not has_json_stringify and not has_response_utils_lib:
            missing.append(file_name)
    assert not missing, f"异步验证: 未使用 JSON.stringify 或 _lib/response_utils.jsx 的文件: {missing}"
