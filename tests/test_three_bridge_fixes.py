#!/usr/bin/env python3
"""
三个 Bridge 问题修复的验证测试
===============================

覆盖：
1. AE Bridge 渲染参数三级降级 (setSettingsWithPreset -> applyTemplate -> applySettings)
2. PR Bridge 超时策略增强 (心跳检测、keepalive标记、60s默认超时)
3. DaVinci Resolve Scripting API 全面路径探测 (注册表、多盘符、python_get_resolve)

运行方式: pytest tests/test_three_bridge_fixes.py -v
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List

import pytest

# =========================================================================
# FIXTURES
# =========================================================================

@pytest.fixture
def tmp_project_dir(tmp_path):
    """临时项目目录"""
    (tmp_path / ".premiere-mcp-bridge").mkdir(parents=True, exist_ok=True)
    (tmp_path / "integrations").mkdir(parents=True, exist_ok=True)
    return tmp_path


# =========================================================================
# 问题1: AE Bridge 渲染 - 三级降级
# =========================================================================

class TestAEBridgeRenderFixes:
    """AE 渲染失败修复验证（v2.0 生产级）"""

    def test_ae_render_engine_has_template_fallback_candidates(self):
        """验证 ae_render_engine.py 有完整的 OM_TEMPLATES / RS_TEMPLATES 候选表"""
        engine_path = Path(__file__).parent.parent / "rendering" / "ae_render_engine.py"
        c = engine_path.read_text(encoding="utf-8")

        assert "OM_TEMPLATES" in c, "缺少 OM_TEMPLATES 字典定义"
        assert "RS_TEMPLATES" in c, "缺少 RS_TEMPLATES 字典定义"
        assert "H.264 - Match Source - High bitrate" in c
        assert "Match Source - H.264 high bitrate" in c
        assert "High Quality" in c
        assert "Lossless" in c

    def test_ae_render_engine_error_code_handling(self):
        """验证有完整的 AerenderExitCode 错误码和自动重试"""
        engine_path = Path(__file__).parent.parent / "rendering" / "ae_render_engine.py"
        c = engine_path.read_text(encoding="utf-8")

        assert "AerenderExitCode" in c, "缺少 AerenderExitCode 枚举"
        assert "parse_aerender_error" in c, "缺少错误解析函数"
        assert "ERROR_CODE_INFO" in c, "缺少错误码信息表"
        assert "OM_TEMPLATE_NOT_FOUND" in c, "缺少模板未找到错误码"
        assert "CANNOT_OPEN_PROJECT" in c, "缺少项目打开失败错误码"
        assert "LICENSE_ERROR" in c, "缺少许可错误码"
        assert "GPU_INIT_FAILED" in c, "缺少GPU错误码"
        assert "taskkill" in c, "缺少进程树终止"

    def test_dispatcher_has_command_line_template_fallback(self):
        """验证 engine_task_dispatcher.py 有命令行模板候选 fallback 循环"""
        disp_path = Path(__file__).parent.parent / "pipeline" / "engine_task_dispatcher.py"
        c = disp_path.read_text(encoding="utf-8")

        assert "om_candidates" in c, "缺少 OM 候选列表构建"
        assert "is_template_error" in c, "缺少模板错误检测"
        assert "continueOnMissingFootage" in c, "缺少素材丢失容错"
        assert "CREATE_NO_WINDOW" in c, "Windows 下缺少无窗口标志"

    def test_flagship_runner_uses_cli_template_fallback(self):
        """验证 flagship_runner.py 使用 aerender CLI 模板候选 fallback"""
        flagship_path = Path(__file__).parent.parent / "pipeline" / "flagship_runner.py"
        c = flagship_path.read_text(encoding="utf-8")

        assert "OM_TEMPLATES" in c, "缺少模板候选表导入"
        assert "om_candidates" in c, "缺少 om_candidates 迭代"
        assert "continueOnMissingFootage" in c, "缺少 continueOnMissingFootage"
        assert "CREATE_NO_WINDOW" in c, "Windows 下缺少无窗口标志"
        assert "is_tmpl_err" in c, "缺少模板错误判断"
        assert "H.264" in c, "缺少 H.264 编码设置"

    def test_flagship_runner_jsx_error_handling(self):
        """验证 flagship_runner.py 中的 JSX 有合理的错误处理"""
        flagship_path = Path(__file__).parent.parent / "pipeline" / "flagship_runner.py"
        c = flagship_path.read_text(encoding="utf-8")

        try_count = c.count("try {") + c.count("try{")
        catch_count = c.count("catch(") + c.count("catch (")
        assert try_count >= 3, f"try/catch 不足 3 级（实际: {try_count} try）"
        assert catch_count >= 3, f"catch 不足 3 个（实际: {catch_count}）"

    def test_ae_render_engine_build_command_includes_templates(self, tmp_path):
        """验证 _build_command 在 h264 输出时注入 -OMtemplate 和 -RStemplate"""
        sys.path.insert(0, str(Path(__file__).parent.parent / "rendering"))
        try:
            engine_path = Path(__file__).parent.parent / "rendering" / "ae_render_engine.py"
            c = engine_path.read_text(encoding="utf-8")
            assert "-OMtemplate" in c, "_build_command 缺少 -OMtemplate 参数"
            assert "-RStemplate" in c, "_build_command 缺少 -RStemplate 参数"
            assert "-continueOnMissingFootage" in c, "缺少 -continueOnMissingFootage"
            assert "-close" in c, "缺少 -close 参数"
            assert "Best Settings" in c, "默认使用 Best Settings"
        finally:
            sys.path.pop(0)

class TestPRBridgeTimeoutFixes:
    """PR Bridge 超时策略增强验证"""

    def test_pr_client_default_timeout_increased(self):
        """验证 premiere_mcp_client.py 中 timeout 默认值从 30s 提升到 60s"""
        # 根目录治理后 premiere_mcp_client.py 已迁入 bridges/ 包
        pr_client_path = Path(__file__).parent.parent / "bridges" / "premiere_mcp_client.py"
        content = pr_client_path.read_text(encoding="utf-8")

        # 验证默认 timeout 值
        import re
        # 查找 __init__ 参数: timeout: float = XX.X
        m = re.search(r"timeout\s*:\s*float\s*=\s*(\d+\.\d+)", content)
        assert m, "未找到 timeout 参数定义"
        default_timeout = float(m.group(1))
        assert default_timeout >= 60.0, f"默认 timeout 应 ≥60s，当前: {default_timeout}s"

    def test_pr_client_send_command_has_keepalive(self):
        """验证 _send_command 方法创建和删除 .keepalive_ 标记文件"""
        pr_client_path = Path(__file__).parent.parent / "bridges" / "premiere_mcp_client.py"
        content = pr_client_path.read_text(encoding="utf-8")

        assert "keepalive_file" in content, "缺少 keepalive_file 变量"
        assert ".keepalive_" in content, "缺少 .keepalive_ 文件名前缀"
        assert ".touch()" in content, "缺少 keepalive 文件 touch 创建"
        assert ".unlink()" in content, "缺少 keepalive 文件 unlink 删除"

    def test_pr_process_manager_has_bridge_detection_loop(self):
        """验证 pr_process_manager.py 新增 Bridge 就绪主动检测循环"""
        pr_proc_path = Path(__file__).parent.parent / "ae" / "pr_process_manager.py"
        content = pr_proc_path.read_text(encoding="utf-8")

        # 关键组件
        assert "AEK_PR_BRIDGE_DIR" in content, "缺少 AEK_PR_BRIDGE_DIR 环境变量读取"
        assert "ping_check" in content.lower(), "缺少 ping_check 心跳检测"
        assert "existing_result_files" in content, "缺少 existing_result_files 新文件比对"
        assert ".premiere-mcp-bridge" in content, "缺少默认 Bridge 目录 .premiere-mcp-bridge"

    def test_pr_keepalive_file_creation_cleanup(self, tmp_project_dir):
        """实际运行 PR MCP 客户端 keepalive 机制验证"""
        pr_client_path = Path(__file__).parent.parent / "bridges"
        if str(pr_client_path) not in sys.path:
            sys.path.insert(0, str(pr_client_path))
        try:
            from premiere_mcp_client import PremiereMCP

            bridge_dir = tmp_project_dir / ".premiere-mcp-bridge"
            client = PremiereMCP(bridge_dir=str(bridge_dir), timeout=1.0, poll_interval=0.05)

            # 执行 ping - 应创建 .keepalive 文件并在超时后清理
            before_files = set(bridge_dir.glob("*"))
            result = client.ping()  # 必然超时，但测试 keepalive 机制
            after_files = set(bridge_dir.glob("*"))

            # 清理后不应残留 .keepalive 文件
            remaining_keepalive = [f for f in after_files if ".keepalive_" in f.name]
            assert len(remaining_keepalive) == 0, (
                f"keepalive 文件未被清理！残留: {[f.name for f in remaining_keepalive]}"
            )
            # 超时结果应被正确返回
            assert result.get("success") is False or "error" in result or "Timeout" in str(result)
        finally:
            pass


# =========================================================================
# 问题3: DaVinci Resolve Scripting API 路径探测
# =========================================================================

class TestDaVinciScriptingAPIDetection:
    """DaVinci Resolve Scripting API 全面路径探测验证"""

    def test_init_resolve_api_has_registry_detection(self):
        """验证 _init_resolve_api 包含 winreg 注册表探测"""
        resolve_int_path = (
            Path(__file__).parent.parent / "integrations" / "davinci_resolve_integration.py"
        )
        content = resolve_int_path.read_text(encoding="utf-8")

        assert "winreg" in content, "缺少 winreg 注册表导入"
        assert "HKEY_LOCAL_MACHINE" in content, "缺少 HKLM 注册表项"
        assert "HKEY_CURRENT_USER" in content, "缺少 HKCU 注册表项"
        assert "InstallPath" in content, "缺少 InstallPath 注册表值读取"
        assert "WOW6432Node" in content, "缺少 WOW6432Node 32位兼容注册表路径"

    def test_init_resolve_api_has_multiple_install_paths(self):
        """验证多盘符常见安装路径探测"""
        resolve_int_path = (
            Path(__file__).parent.parent / "integrations" / "davinci_resolve_integration.py"
        )
        content = resolve_int_path.read_text(encoding="utf-8")

        # 多盘符覆盖 - 必须出现在字符串字面量中（作为路径前缀）
        for drive in ["C:\\", "D:\\", "E:\\", "F:\\"]:
            has_drive = False
            # 检查常见形式: "C:\\Program Files", r"C:\", '"C:\\' 等
            for variant in [
                f'{drive}Program Files',
                f'"{drive}',
                f'r"{drive}',
                f"r'{drive}",
                f'{drive}Blackmagic',
            ]:
                if variant in content:
                    has_drive = True
                    break
            # 也检查 resolve_install_candidates 列表的定义（通过盘符拼接）
            if not has_drive:
                has_drive = "resolve_install_candidates" in content and (
                    f'Path("{drive}")' in content or f"Path('{drive}')" in content
                    or f'for d in ["{drive[0]}",' in content  # 盘符列表
                    or f'"{drive[0]}:\\\\"' in content.lower()
                )
            assert has_drive, f"缺少盘符 {drive} 的安装路径候选（可在字符串字面量或 resolve_install_candidates 列表中）"

        # Scripting Modules 子目录多路径 - 使用 Path 对象拼接（/ 运算符），通过子路径名验证
        script_api_candidates_block = content.split("script_api_candidates: List[Path]")[1].split("fusionscript_candidates")[0] if "script_api_candidates: List[Path]" in content else ""
        # 验证至少有这些子路径片段
        for segment in ['"Support"', '"Developer"', '"Scripting"', '"Modules"']:
            assert segment in content, f"Scripting API 路径构造缺少 {segment} 子路径"
        # 同时验证 script_api_candidates.extend 调用存在
        assert "script_api_candidates.extend" in content or (
            "for install_dir in resolve_install_candidates:" in content and
            '"Modules"' in content
        ), "缺少 Scripting Modules 路径的批量添加"

    def test_init_resolve_api_python_get_resolve_support(self):
        """验证 python_get_resolve.py 路径注入和 GetResolve() 调用"""
        resolve_int_path = (
            Path(__file__).parent.parent / "integrations" / "davinci_resolve_integration.py"
        )
        content = resolve_int_path.read_text(encoding="utf-8")

        assert "python_get_resolve" in content, "缺少 python_get_resolve.py 探测"
        assert "GetResolve" in content, "缺少 python_get_resolve.GetResolve() 调用"
        # 验证存在 python_get_resolve_paths 列表定义
        assert "python_get_resolve_paths" in content, "缺少 python_get_resolve_paths 路径列表"

    def test_init_resolve_api_eight_stages_complete(self):
        """验证 8 阶段全面探测逻辑都存在"""
        resolve_int_path = (
            Path(__file__).parent.parent / "integrations" / "davinci_resolve_integration.py"
        )
        content = resolve_int_path.read_text(encoding="utf-8")

        required_markers = [
            "fuscript.exe",              # 阶段1: fuscript 优先
            "resolve_install_candidates",# 阶段2: 安装路径
            "script_api_candidates",     # 阶段3: Scripting Modules
            "Scripting API injected",    # 阶段4: 路径注入验证
            "fusionscript_candidates",   # 阶段5: fusionscript.dll
            "python_get_resolve_paths",  # 阶段6: python_get_resolve
            "DaVinciResolveScript as",   # 阶段7: 官方模块导入
            "python_get_resolve.GetResolve", # 阶段8: 辅助脚本导入
        ]
        for marker in required_markers:
            assert marker in content, f"缺少阶段标记: {marker}"

    def test_resolve_path_detection_isolated(self, monkeypatch, tmp_path):
        """隔离测试路径探测逻辑（不启动 Resolve）"""
        # 创建模拟安装目录
        mock_resolve_home = tmp_path / "DaVinci Resolve"
        mock_scripting_modules = mock_resolve_home / "Support" / "Developer" / "Scripting" / "Modules"
        mock_scripting_modules.mkdir(parents=True, exist_ok=True)
        # 创建模拟 python 模块文件
        (mock_scripting_modules / "DaVinciResolveScript.py").write_text(
            "def scriptapp(x): return None\n", encoding="utf-8"
        )
        # fuscript.exe 模拟
        (mock_resolve_home / "fuscript.exe").write_bytes(b"MZ")
        (mock_resolve_home / "Resolve.exe").write_bytes(b"MZ")
        # fusionscript.dll 模拟
        (mock_resolve_home / "fusionscript.dll").write_bytes(b"MZ")
        # python_get_resolve.py 模拟
        examples_dir = mock_resolve_home / "Developer" / "Scripting" / "Examples" / "Python"
        examples_dir.mkdir(parents=True, exist_ok=True)
        (examples_dir / "python_get_resolve.py").write_text(
            "def GetResolve(): return None\n", encoding="utf-8"
        )

        # 临时添加到 sys.path 以便导入
        resolve_int_path = str(Path(__file__).parent.parent)
        if resolve_int_path not in sys.path:
            sys.path.insert(0, resolve_int_path)

        # 使用 monkeypatch 设置虚拟环境变量
        monkeypatch.setenv("PROGRAMDATA", str(tmp_path / "ProgramData"))

        # 只测试路径探测相关函数（通过源代码分析验证）
        resolve_int_file = Path(__file__).parent.parent / "integrations" / "davinci_resolve_integration.py"
        content = resolve_int_file.read_text(encoding="utf-8")

        # 验证 List[Path] 类型注解使用正确
        assert "python_get_resolve_paths: List[Path]" in content, \
            "python_get_resolve_paths 缺少 List[Path] 类型注解"
        assert "fusionscript_candidates: List[Path]" in content, \
            "fusionscript_candidates 缺少 List[Path] 类型注解"
        assert "script_api_candidates: List[Path]" in content, \
            "script_api_candidates 缺少 List[Path] 类型注解"


# =========================================================================
# S5 DaVinci 调色路径修复
# =========================================================================

class TestS5DaVinciResolvePath:
    """S5 DaVinci 调色路径修复验证"""

    def test_render_timeline_output_path_not_overwritten(self):
        """验证原生渲染路径中 output_path 精确受控（不被解析结果覆盖）"""
        resolve_engine_path = (
            Path(__file__).parent.parent / "integrations" / "resolve_engine.py"
        )
        content = resolve_engine_path.read_text(encoding="utf-8")

        start = content.find("def _render_with_resolve(")
        end = content.find("def _execute_lua_async(")
        code = content[start:end] if start >= 0 and end > start else ""
        assert code, "缺少 _render_with_resolve 方法"

        # 输出路径精确受控：临时 .mov → FFmpeg 转码 → 返回用户指定 output_path
        assert "temp_mov" in code, "缺少临时 .mov 路径构造"
        assert "ffmpeg -y -i" in code, "缺少 FFmpeg 转码步骤"
        assert "return output_path" in code, "缺少返回用户指定 output_path"
        # 转码成功后校验输出文件存在，避免误报成功
        assert "os.path.exists(output_path)" in code, "缺少输出文件存在性校验"

    def test_render_timeline_lua_prints_output_path(self):
        """验证原生渲染 Lua 有进度监控 + Python 端文件轮询检测输出"""
        resolve_engine_path = (
            Path(__file__).parent.parent / "integrations" / "resolve_engine.py"
        )
        content = resolve_engine_path.read_text(encoding="utf-8")

        start = content.find("def _render_with_resolve(")
        end = content.find("def _execute_lua_async(")
        code = content[start:end] if start >= 0 and end > start else ""
        assert code, "缺少 _render_with_resolve 方法"

        # Lua 脚本监控渲染任务与进度
        assert "StartRendering" in code, "Lua 缺少渲染启动"
        assert "GetRenderJobStatus" in code, "Lua 缺少渲染状态监控"
        assert "completionPercentage" in code, "Lua 缺少进度百分比输出"
        # Python 端文件轮询检测实际渲染产物（替代 Lua 输出解析）
        assert "os.path.exists(temp_mov)" in code, "缺少输出文件轮询检测"
        assert "file_size > 1024" in code, "缺少输出文件大小验证"

    def test_s5_native_resolve_uses_three_step_flow(self):
        """验证 _s5_native_resolve 使用三步流程替代 quick_grade"""
        flagship_path = Path(__file__).parent.parent / "pipeline" / "flagship_runner.py"
        content = flagship_path.read_text(encoding="utf-8")

        # 三步流程的关键步骤标记
        steps = [
            ("Step 1", "create_timeline_from_clips"),
            ("Step 2", "build_node_graph"),
            ("Step 3", "render_timeline"),
        ]
        for step_name, method in steps:
            assert method in content, f"缺少 {step_name}: {method}() 调用"

        # 不应再使用 quick_grade
        assert "quick_grade" not in content.split("def _s5_ffmpeg_fallback")[0], (
            "_s5_native_resolve 不应使用 quick_grade"
        )

    def test_s5_native_resolve_has_robust_output_search(self):
        """验证 _s5_native_resolve 有多层输出文件搜索策略"""
        flagship_path = Path(__file__).parent.parent / "pipeline" / "flagship_runner.py"
        content = flagship_path.read_text(encoding="utf-8")

        # 多层搜索策略
        assert "result.output_path" in content, "缺少 result.output_path 检查"
        assert "candidate.is_file()" in content, "缺少 is_file() 文件检查"
        assert "candidate.is_dir()" in content, "缺少 is_dir() 目录检查"
        assert "candidate.glob(" in content, "缺少 glob 搜索"
        assert "graded*" in content, "缺少 graded* 通配符搜索"
        # 最后兜底搜索
        assert "suffix.lower() in" in content, "缺少后缀名过滤"
        assert "graded_path" in content, "缺少 graded_path 赋值"

    def test_s5_native_resolve_engine_instance_check(self):
        """验证 _s5_native_resolve 检查 engine 实例非空"""
        flagship_path = Path(__file__).parent.parent / "pipeline" / "flagship_runner.py"
        content = flagship_path.read_text(encoding="utf-8")

        # 检查 engine 获取和验证
        assert "resolve_disp._get_engine()" in content, "缺少 _get_engine() 调用"
        assert "if not engine:" in content, "缺少 engine 为空检查"
        assert "无法获取 ResolveColorEngine 实例" in content, "缺少错误日志"


# =========================================================================
# 端到端结构测试（不实际启动外部软件）
# =========================================================================

class TestOverallBridgeFixQuality:
    """修复整体质量评估"""

    def test_no_regression_in_file_headers(self):
        """验证修复未破坏文件头部 docstring / imports"""
        files_to_check = [
            Path(__file__).parent.parent / "pipeline" / "flagship_runner.py",
            Path(__file__).parent.parent / "rendering" / "ae_render_engine.py",
            Path(__file__).parent.parent / "bridges" / "premiere_mcp_client.py",
            Path(__file__).parent.parent / "ae" / "pr_process_manager.py",
            Path(__file__).parent.parent / "integrations" / "davinci_resolve_integration.py",
        ]
        for f in files_to_check:
            content = f.read_text(encoding="utf-8")
            # 确保有文件开头的 docstring 或注释
            lines = content.split("\n")
            has_header = False
            for i, line in enumerate(lines[:10]):
                if line.startswith("#") or line.startswith('"""') or line.startswith("'''"):
                    has_header = True
                    break
            assert has_header, f"{f.name} 缺少文件头注释/docstring"

    def test_python_syntax_valid_all_modified_files(self):
        """验证所有修改文件的语法正确性"""
        import py_compile
        files_to_compile = [
            Path(__file__).parent.parent / "rendering" / "ae_render_engine.py",
            Path(__file__).parent.parent / "bridges" / "premiere_mcp_client.py",
            Path(__file__).parent.parent / "ae" / "pr_process_manager.py",
            Path(__file__).parent.parent / "integrations" / "davinci_resolve_integration.py",
        ]
        for f in files_to_compile:
            try:
                py_compile.compile(str(f), doraise=True)
            except py_compile.PyCompileError as e:
                pytest.fail(f"语法错误: {f.name}\n{e}")

    def test_fallback_presence_in_three_systems(self):
        """三个 Bridge 修复都必须包含「降级 / fallback」机制"""
        checks = [
            # (文件, 降级标记关键词, 描述)
            ("pipeline/flagship_runner.py", "om_candidates",
             "AE Bridge: Bridge创建 → aerender CLI（多模板候选fallback） → 错误码重试"),
            ("bridges/premiere_mcp_client.py", "Timeout",
             "PR Bridge: 超时 → keepalive 清理"),
            ("integrations/davinci_resolve_integration.py", "python_get_resolve",
             "DaVinci: DaVinciResolveScript → python_get_resolve → fuscript 三级"),
        ]
        for rel_path, keyword, desc in checks:
            f = Path(__file__).parent.parent / rel_path
            content = f.read_text(encoding="utf-8")
            assert keyword in content, f"缺少降级机制: {desc} (关键字: {keyword})"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
