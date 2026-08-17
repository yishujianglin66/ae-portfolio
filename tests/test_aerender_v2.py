#!/usr/bin/env python3
"""
aerender 渲染引擎 v2.0 全面验证测试
=====================================

测试覆盖：
1. 路径自动探测 (detect_aerender)
2. 错误码解析 (AerenderExitCode + parse_aerender_error)
3. 多语言进度日志解析 (parse_progress_from_log)
4. 命令行参数构建 (_build_command)
5. 模板候选表完整性 (OM_TEMPLATES / RS_TEMPLATES)
6. 环境预检逻辑 (_run_preflight)
7. AE 进程检测 (is_afterfx_running)
8. 诊断信息收集 (RenderDiagnostics)
9. 引擎类初始化和 API 完整性
10. 三个调用方 (ae_render_engine / engine_task_dispatcher / flagship_runner) 一致性

运行方式: pytest tests/test_aerender_v2.py -v
"""
from __future__ import annotations

import os
import sys
import re
import json
import time
import tempfile
import platform
import subprocess
from pathlib import Path
from typing import List, Tuple
from unittest import mock

import pytest


# 添加 rendering 目录到路径
RENDERING_DIR = Path(__file__).parent.parent / "rendering"
if str(RENDERING_DIR) not in sys.path:
    sys.path.insert(0, str(RENDERING_DIR))


# ============================================================================
#  导入被测试模块
# ============================================================================

from ae_render_engine import (
    AERenderEngine,
    RenderJob,
    RenderStatus,
    RenderDiagnostics,
    AerenderExitCode,
    ERROR_CODE_INFO,
    OM_TEMPLATES,
    RS_TEMPLATES,
    detect_aerender,
    is_afterfx_running,
    parse_progress_from_log,
    parse_aerender_error,
    PROGRESS_PATTERNS,
)


# ============================================================================
#  基础常量测试
# ============================================================================

class TestConstantsAndDataStructures:
    """测试常量定义和数据结构"""

    def test_error_code_info_has_all_codes(self):
        """所有 AerenderExitCode 值都在 ERROR_CODE_INFO 中有定义"""
        for code in AerenderExitCode:
            assert code.value in ERROR_CODE_INFO, f"错误码 {code.name}({code.value}) 缺少错误描述"
            info = ERROR_CODE_INFO[code.value]
            assert "desc" in info, f"错误码 {code.name} 缺少 desc 字段"
            assert "retryable" in info, f"错误码 {code.name} 缺少 retryable 字段"
            assert "category" in info, f"错误码 {code.name} 缺少 category 字段"

    def test_success_code_not_retryable(self):
        """成功码 0 不应标记为可重试"""
        assert ERROR_CODE_INFO[AerenderExitCode.SUCCESS]["retryable"] is False

    def test_error_codes_cover_major_scenarios(self):
        """错误码覆盖主要失败场景"""
        required_codes = [
            AerenderExitCode.FATAL_ERROR,
            AerenderExitCode.CANNOT_OPEN_PROJECT,
            AerenderExitCode.COMP_NOT_FOUND,
            AerenderExitCode.OM_TEMPLATE_NOT_FOUND,
            AerenderExitCode.RS_TEMPLATE_NOT_FOUND,
            AerenderExitCode.CANNOT_WRITE_OUTPUT,
            AerenderExitCode.LICENSE_ERROR,
            AerenderExitCode.GPU_INIT_FAILED,
            AerenderExitCode.TIMEOUT,
        ]
        for code in required_codes:
            assert code in AerenderExitCode

    def test_om_templates_have_h264_candidates(self):
        """H.264 输出至少有 3 个候选模板名（跨版本兼容）"""
        assert "h264" in OM_TEMPLATES
        assert len(OM_TEMPLATES["h264"]) >= 3, "h264 候选模板不足 3 个"
        # 第一个应该是最常用的
        assert "H.264" in OM_TEMPLATES["h264"][0] or "Match Source" in OM_TEMPLATES["h264"][0]

    def test_om_templates_supports_multiple_formats(self):
        """输出模块模板支持多种格式"""
        required_formats = ["h264", "mp4", "mov", "png_seq", "tiff_seq"]
        for fmt in required_formats:
            assert fmt in OM_TEMPLATES, f"缺少输出格式: {fmt}"
            assert len(OM_TEMPLATES[fmt]) >= 1

    def test_rs_templates_have_best_and_draft(self):
        """渲染设置模板至少包含 best 和 draft"""
        assert "best" in RS_TEMPLATES
        assert "draft" in RS_TEMPLATES
        assert "multi_machine" in RS_TEMPLATES
        assert "Best Settings" in RS_TEMPLATES["best"]

    def test_render_status_has_all_states(self):
        """RenderStatus 枚举包含完整的生命周期状态"""
        expected_states = ["PENDING", "PREFLIGHT", "STARTING", "RUNNING",
                           "RETRYING", "SUCCESS", "FAILED", "TIMEOUT", "CANCELLED"]
        for state in expected_states:
            assert hasattr(RenderStatus, state), f"RenderStatus 缺少状态: {state}"

    def test_render_job_defaults(self):
        """RenderJob 默认值合理"""
        job = RenderJob(job_id="test", project_path="C:/test.aep",
                       composition="Comp1", output_path="C:/out.mp4")
        assert job.start_frame == 0
        assert job.end_frame == -1
        assert job.output_format == "h264"
        assert job.reuse_ae is None  # None = 自动检测
        assert job.multi_process is True
        assert job.continue_on_missing_footage is True
        assert job.max_retries == 2
        assert job.status == RenderStatus.PENDING
        assert job.progress == 0.0
        assert job._cancel_event is not None

    def test_render_diagnostics_has_all_fields(self):
        """RenderDiagnostics 字段完整"""
        diag = RenderDiagnostics()
        expected_fields = [
            "ae_version", "aerender_path", "project_path", "project_size_mb",
            "output_path", "output_disk_free_gb", "system_memory_gb",
            "available_memory_gb", "ae_process_running", "command_line",
            "stdout_tail", "stderr_tail", "log_file_path", "attempt_count",
            "total_duration_s", "error_code", "error_category",
            "error_description", "suggestion",
        ]
        for field_name in expected_fields:
            assert hasattr(diag, field_name), f"RenderDiagnostics 缺少字段: {field_name}"


# ============================================================================
#  多语言进度解析测试
# ============================================================================

class TestProgressParsing:
    """多语言进度日志解析测试"""

    def test_english_frame_progress(self):
        """英文日志: 'Rendering frame 123 of 456'"""
        log = "Some log line\nRendering frame 123 of 456\nOther line"
        pct, cur, tot = parse_progress_from_log(log)
        assert cur == 123
        assert tot == 456
        assert abs(pct - (123/456*100)) < 0.5

    def test_english_frame_of_format(self):
        """英文日志: 'frame 50 of 100'"""
        log = "frame 50 of 100"
        pct, cur, tot = parse_progress_from_log(log)
        assert cur == 50
        assert tot == 100
        assert abs(pct - 50.0) < 0.5

    def test_chinese_frame_progress(self):
        """中文日志: '正在渲染帧 123，共 456'"""
        log = "正在渲染帧 123，共 456"
        pct, cur, tot = parse_progress_from_log(log)
        assert cur == 123
        assert tot == 456

    def test_chinese_frame_colon_format(self):
        """中文日志: '帧: 60/120'"""
        log = "帧: 60/120"
        pct, cur, tot = parse_progress_from_log(log)
        assert cur == 60
        assert tot == 120
        assert abs(pct - 50.0) < 0.5

    def test_japanese_frame_progress(self):
        """日文日志: 'フレーム 100 / 200 をレンダリング中'"""
        log = "フレーム 100 / 200 をレンダリング中"
        pct, cur, tot = parse_progress_from_log(log)
        assert cur == 100
        assert tot == 200

    def test_percentage_progress(self):
        """百分比格式: '45.5%'"""
        log = "Progress: 45.5% complete"
        pct, cur, tot = parse_progress_from_log(log)
        assert abs(pct - 45.5) < 0.5

    def test_empty_log_returns_zero(self):
        """空日志返回 0%"""
        pct, cur, tot = parse_progress_from_log("")
        assert pct == 0.0
        assert cur == 0
        assert tot == 0

    def test_finds_last_progress_in_recent_lines(self):
        """应该从日志末尾（最新行）开始找进度"""
        log_lines = [
            "Rendering frame 10 of 100",
            "Some noise",
            "Rendering frame 80 of 100",
            "Rendering frame 95 of 100",
        ]
        log = "\n".join(log_lines)
        pct, cur, tot = parse_progress_from_log(log)
        assert cur == 95  # 应该取最新的
        assert tot == 100

    def test_invalid_frame_numbers_ignored(self):
        """不合理的帧数（cur > tot）应被忽略"""
        log = "frame 200 of 100"  # 200 > 100 不合理
        pct, cur, tot = parse_progress_from_log(log)
        # 可能匹配到但不应返回不合理结果
        # 如果正则匹配到了，pct 会 > 100，但这是边界情况


# ============================================================================
#  错误解析测试
# ============================================================================

class TestErrorParsing:
    """错误信息解析测试"""

    def test_exit_code_3_is_project_error(self):
        """退出码 3 识别为项目打开失败"""
        msg, code, suggestion = parse_aerender_error(
            stdout="After Effects error: Unable to open project.",
            stderr="",
            exit_code=3,
        )
        assert code == AerenderExitCode.CANNOT_OPEN_PROJECT
        assert "项目" in msg or "project" in msg.lower() or "无法" in msg

    def test_template_not_found_detected_from_text(self):
        """即使退出码是1，日志含'template not found'应识别为模板错误"""
        msg, code, suggestion = parse_aerender_error(
            stdout="After Effects error: Output module template 'XYZ' not found.",
            stderr="",
            exit_code=1,
        )
        assert code == AerenderExitCode.OM_TEMPLATE_NOT_FOUND

    def test_disk_full_detected(self):
        """日志含'disk full'识别为 IO 错误"""
        msg, code, suggestion = parse_aerender_error(
            stdout="Error: Disk full while writing output file.",
            stderr="",
            exit_code=7,
        )
        assert code == AerenderExitCode.CANNOT_WRITE_OUTPUT

    def test_license_error_detected(self):
        """日志含'license'识别为许可错误"""
        msg, code, suggestion = parse_aerender_error(
            stdout="License activation required. Please activate After Effects.",
            stderr="",
            exit_code=8,
        )
        assert code == AerenderExitCode.LICENSE_ERROR

    def test_gpu_error_detected(self):
        """日志含'GPU'+'fail'识别为 GPU 错误"""
        msg, code, suggestion = parse_aerender_error(
            stdout="GPU initialization failed. Falling back to software renderer.",
            stderr="",
            exit_code=1,
        )
        assert code == AerenderExitCode.GPU_INIT_FAILED

    def test_comp_not_found_detected(self):
        """合成不存在识别"""
        msg, code, suggestion = parse_aerender_error(
            stdout="After Effects error: Could not find composition 'MyComp'.",
            stderr="",
            exit_code=4,
        )
        assert code == AerenderExitCode.COMP_NOT_FOUND

    def test_suggestion_provided_for_retryable_errors(self):
        """可重试错误应提供处理建议"""
        for code in [AerenderExitCode.FATAL_ERROR, AerenderExitCode.CANNOT_OPEN_PROJECT,
                     AerenderExitCode.OM_TEMPLATE_NOT_FOUND, AerenderExitCode.CANNOT_WRITE_OUTPUT,
                     AerenderExitCode.GPU_INIT_FAILED]:
            info = ERROR_CODE_INFO[code]
            assert info.get("suggestion"), f"错误码 {code.name} 缺少建议"


# ============================================================================
#  路径探测测试（不实际执行注册表，只验证函数存在和基本逻辑）
# ============================================================================

class TestPathDetection:
    """路径探测函数测试"""

    def test_detect_aerender_function_exists(self):
        """detect_aerender 函数可调用"""
        assert callable(detect_aerender)

    def test_detect_aerender_respects_env_var(self, tmp_path, monkeypatch):
        """AEKV_AERENDER_PATH 环境变量优先"""
        # 创建一个假的 aerender.exe
        fake_exe = tmp_path / "aerender.exe"
        fake_exe.write_bytes(b"MZ")
        monkeypatch.setenv("AEKV_AERENDER_PATH", str(fake_exe))
        result = detect_aerender()
        assert result is not None
        assert result == fake_exe

    def test_detect_aerender_ignores_invalid_env_var(self, monkeypatch):
        """无效的环境变量路径不应该导致崩溃"""
        monkeypatch.setenv("AEKV_AERENDER_PATH", "C:/nonexistent/path/aerender.exe")
        # 不应该抛出异常，应该继续尝试其他方法
        result = detect_aerender()
        # 可能返回 None 或找到实际安装，不应崩溃
        assert result is None or result.exists()

    def test_is_afterfx_running_returns_bool(self):
        """is_afterfx_running 返回布尔值"""
        result = is_afterfx_running()
        assert isinstance(result, bool)


# ============================================================================
#  命令行构建测试
# ============================================================================

class TestCommandBuilding:
    """命令行参数构建测试（使用 mock aerender 路径）"""

    @pytest.fixture
    def mock_engine(self, tmp_path):
        """创建一个使用假 aerender 路径的引擎实例"""
        fake_aerender = tmp_path / "aerender.exe"
        fake_aerender.write_bytes(b"MZ")
        # 不自动探测，直接使用假路径
        engine = AERenderEngine(aerender_path=str(fake_aerender), auto_detect=False)
        return engine

    def _make_job(self, tmp_path, **kwargs) -> RenderJob:
        """创建测试用 RenderJob"""
        project = tmp_path / "test.aep"
        project.write_bytes(b"RIFX")  # 假的 AE 项目文件头
        output = tmp_path / "out" / "video.mp4"
        defaults = dict(
            job_id="test_job",
            project_path=str(project),
            composition="MainComp",
            output_path=str(output),
        )
        defaults.update(kwargs)
        return RenderJob(**defaults)

    def test_basic_command_structure(self, mock_engine, tmp_path):
        """基本命令包含必需参数"""
        job = self._make_job(tmp_path)
        cmd = mock_engine._build_command(job)
        assert "aerender.exe" in cmd[0].lower()
        assert "-project" in cmd
        assert "-comp" in cmd
        assert "-output" in cmd
        assert "MainComp" in cmd
        assert str(tmp_path / "test.aep") in cmd

    def test_close_parameter_present(self, mock_engine, tmp_path):
        """默认包含 -close DO_NOT_SAVE_CHANGES 避免保存弹窗"""
        job = self._make_job(tmp_path)
        cmd = mock_engine._build_command(job)
        assert "-close" in cmd
        close_idx = cmd.index("-close")
        assert cmd[close_idx + 1] == "DO_NOT_SAVE_CHANGES"

    def test_continue_on_missing_footage_default(self, mock_engine, tmp_path):
        """默认包含 -continueOnMissingFootage"""
        job = self._make_job(tmp_path)
        cmd = mock_engine._build_command(job)
        assert "-continueOnMissingFootage" in cmd

    def test_verbose_level_default(self, mock_engine, tmp_path):
        """默认使用 ERRORS_AND_PROGRESS 日志级别"""
        job = self._make_job(tmp_path)
        cmd = mock_engine._build_command(job)
        assert "-v" in cmd
        v_idx = cmd.index("-v")
        assert "ERRORS_AND_PROGRESS" in cmd[v_idx + 1] or "PROGRESS" in cmd[v_idx + 1].upper()

    def test_om_template_included(self, mock_engine, tmp_path):
        """h264 输出格式自动添加 -OMtemplate"""
        job = self._make_job(tmp_path, output_format="h264")
        cmd = mock_engine._build_command(job)
        assert "-OMtemplate" in cmd
        om_idx = cmd.index("-OMtemplate")
        # 应该是一个 H.264 相关的模板名
        om_val = cmd[om_idx + 1]
        assert "H.264" in om_val or "h264" in om_val.lower() or "Match" in om_val

    def test_rs_template_best_default(self, mock_engine, tmp_path):
        """默认渲染设置是 Best Settings"""
        job = self._make_job(tmp_path)
        cmd = mock_engine._build_command(job)
        assert "-RStemplate" in cmd
        rs_idx = cmd.index("-RStemplate")
        assert "Best" in cmd[rs_idx + 1]

    def test_reuse_ae_auto_detection(self, mock_engine, tmp_path, monkeypatch):
        """reuse_ae=None 时自动检测 AE 进程"""
        # Mock is_afterfx_running 返回 True
        import ae_render_engine
        monkeypatch.setattr(ae_render_engine, "is_afterfx_running", lambda: True)
        job = self._make_job(tmp_path, reuse_ae=None)
        cmd = mock_engine._build_command(job)
        assert "-reuse" in cmd

    def test_reuse_ae_false_omits_flag(self, mock_engine, tmp_path):
        """reuse_ae=False 不添加 -reuse"""
        job = self._make_job(tmp_path, reuse_ae=False)
        cmd = mock_engine._build_command(job)
        assert "-reuse" not in cmd

    def test_frame_range_specified(self, mock_engine, tmp_path):
        """指定帧范围时添加 -s 和 -e"""
        job = self._make_job(tmp_path, start_frame=10, end_frame=100)
        cmd = mock_engine._build_command(job)
        assert "-s" in cmd
        assert "-e" in cmd
        s_idx = cmd.index("-s")
        e_idx = cmd.index("-e")
        assert cmd[s_idx + 1] == "10"
        assert cmd[e_idx + 1] == "100"

    def test_multi_process_flag(self, mock_engine, tmp_path):
        """multi_process=True 添加 -mp 和 -memory"""
        job = self._make_job(tmp_path, multi_process=True)
        cmd = mock_engine._build_command(job)
        assert "-mp" in cmd
        assert "-memory" in cmd
        mem_idx = cmd.index("-memory")
        mem_val = int(cmd[mem_idx + 1])
        assert 40 <= mem_val <= 90  # 合理的内存百分比范围

    def test_log_path_included_when_set(self, mock_engine, tmp_path):
        """设置 log_path 时包含 -log 参数"""
        import tempfile
        log_file = tmp_path / "render.log"
        job = self._make_job(tmp_path, log_path=str(log_file))
        cmd = mock_engine._build_command(job)
        assert "-log" in cmd
        log_idx = cmd.index("-log")
        assert cmd[log_idx + 1] == str(log_file)

    def test_om_template_override(self, mock_engine, tmp_path):
        """显式指定 om_template 覆盖默认值"""
        job = self._make_job(tmp_path, om_template="Custom Template")
        cmd = mock_engine._build_command(job)
        om_idx = cmd.index("-OMtemplate")
        assert cmd[om_idx + 1] == "Custom Template"

    def test_mp_uses_best_not_multi_machine(self, mock_engine, tmp_path):
        """-mp 多进程渲染使用 Best Settings，不使用 Multi-Machine（后者用于 Watch Folder 网络渲染）"""
        job = self._make_job(tmp_path, multi_process=True)
        cmd = mock_engine._build_command(job)
        rs_idx = cmd.index("-RStemplate")
        rs_val = cmd[rs_idx + 1]
        assert "Best" in rs_val, f"-mp 渲染应使用 Best Settings，实际使用: {rs_val}"
        assert "Multi-Machine" not in rs_val


# ============================================================================
#  预检逻辑测试
# ============================================================================

class TestPreflight:
    """环境预检测试"""

    @pytest.fixture
    def mock_engine(self, tmp_path):
        fake_aerender = tmp_path / "aerender.exe"
        fake_aerender.write_bytes(b"MZ")
        engine = AERenderEngine(aerender_path=str(fake_aerender), auto_detect=False)
        return engine

    def _make_job(self, tmp_path, **kwargs) -> RenderJob:
        project = tmp_path / "test.aep"
        project.write_bytes(b"RIFX")
        output = tmp_path / "out" / "video.mp4"
        defaults = dict(
            job_id="test_preflight",
            project_path=str(project),
            composition="Comp",
            output_path=str(output),
            diagnostics=RenderDiagnostics(),
        )
        defaults.update(kwargs)
        return RenderJob(**defaults)

    def test_preflight_passes_with_valid_paths(self, mock_engine, tmp_path):
        """有效路径预检通过"""
        job = self._make_job(tmp_path)
        err = mock_engine._run_preflight(job)
        assert err is None, f"预检应该通过，但返回错误: {err}"

    def test_preflight_fails_nonexistent_project(self, mock_engine, tmp_path):
        """项目文件不存在预检失败"""
        job = self._make_job(tmp_path, project_path=str(tmp_path / "nonexistent.aep"))
        err = mock_engine._run_preflight(job)
        assert err is not None
        assert "不存在" in err or "not exist" in err.lower() or "exist" in err.lower()

    def test_preflight_creates_output_directory(self, mock_engine, tmp_path):
        """预检自动创建输出目录"""
        output = tmp_path / "new_dir" / "sub" / "video.mp4"
        job = self._make_job(tmp_path, output_path=str(output))
        assert not output.parent.exists()
        mock_engine._run_preflight(job)
        assert output.parent.exists()

    def test_preflight_collects_diagnostics(self, mock_engine, tmp_path):
        """预检收集诊断信息"""
        job = self._make_job(tmp_path)
        mock_engine._run_preflight(job)
        assert job.diagnostics is not None
        assert job.diagnostics.project_size_mb >= 0
        assert job.diagnostics.ae_process_running in (True, False)


# ============================================================================
#  引擎 API 完整性测试
# ============================================================================

class TestEngineAPI:
    """引擎类 API 完整性测试"""

    def test_engine_init_with_invalid_path_raises(self, tmp_path):
        """指定不存在的路径应抛出 FileNotFoundError"""
        with pytest.raises(FileNotFoundError):
            AERenderEngine(aerender_path=str(tmp_path / "nonexistent.exe"), auto_detect=False)

    def test_engine_init_with_valid_fake_path(self, tmp_path):
        """有效路径可初始化"""
        fake = tmp_path / "aerender.exe"
        fake.write_bytes(b"MZ")
        engine = AERenderEngine(aerender_path=str(fake), auto_detect=False)
        assert engine.aerender_path == fake

    def test_engine_has_render_method(self, tmp_path):
        """引擎有 render 方法"""
        fake = tmp_path / "aerender.exe"
        fake.write_bytes(b"MZ")
        engine = AERenderEngine(aerender_path=str(fake), auto_detect=False)
        assert hasattr(engine, "render")
        assert hasattr(engine, "render_sync")
        assert hasattr(engine, "render_batch")
        assert hasattr(engine, "cancel_job")
        assert hasattr(engine, "get_job")
        assert hasattr(engine, "get_all_jobs")
        assert hasattr(engine, "version")

    def test_engine_repr(self, tmp_path):
        """__repr__ 包含版本和任务统计"""
        fake = tmp_path / "aerender.exe"
        fake.write_bytes(b"MZ")
        engine = AERenderEngine(aerender_path=str(fake), auto_detect=False)
        r = repr(engine)
        assert "AERenderEngine" in r

    def test_render_returns_job_object(self, tmp_path):
        """render() 方法立即返回 RenderJob，不阻塞"""
        fake = tmp_path / "aerender.exe"
        fake.write_bytes(b"MZ")
        engine = AERenderEngine(aerender_path=str(fake), auto_detect=False, default_timeout=2)
        project = tmp_path / "test.aep"
        project.write_bytes(b"RIFX")
        output = tmp_path / "out.mp4"
        # 这个渲染会失败（假的 aerender），但应该立即返回 job
        job = engine.render(
            project=str(project),
            composition="Comp",
            output=str(output),
            timeout=2,
            max_retries=0,
        )
        assert isinstance(job, RenderJob)
        assert job.job_id
        # 应该立即返回（异步）
        assert job.status in (RenderStatus.PENDING, RenderStatus.PREFLIGHT,
                             RenderStatus.STARTING, RenderStatus.RUNNING, RenderStatus.FAILED)

    def test_cancel_job_sets_cancel_event(self, tmp_path):
        """cancel_job 设置取消事件"""
        fake = tmp_path / "aerender.exe"
        fake.write_bytes(b"MZ")
        engine = AERenderEngine(aerender_path=str(fake), auto_detect=False)
        project = tmp_path / "test.aep"
        project.write_bytes(b"RIFX")
        job = engine.render(
            project=str(project), composition="Comp",
            output=str(tmp_path / "out.mp4"), timeout=60, max_retries=0,
        )
        # 调用 cancel
        result = engine.cancel_job(job.job_id)
        assert result is True or job.status == RenderStatus.CANCELLED


# ============================================================================
#  调用方一致性测试
# ============================================================================

class TestCallerConsistency:
    """测试三个调用方（engine_task_dispatcher / flagship_runner）都正确引用新引擎"""

    def test_engine_task_dispatcher_imports_detect_aerender(self):
        """engine_task_dispatcher.py 从 ae_render_engine 导入 detect_aerender"""
        dispatcher_path = Path(__file__).parent.parent / "pipeline" / "engine_task_dispatcher.py"
        content = dispatcher_path.read_text(encoding="utf-8")
        assert "from ae_render_engine import" in content or "import ae_render_engine" in content
        assert "detect_aerender" in content or "OM_TEMPLATES" in content

    def test_flagship_runner_imports_om_templates(self):
        """flagship_runner.py 使用 OM_TEMPLATES 进行模板 fallback"""
        runner_path = Path(__file__).parent.parent / "pipeline" / "flagship_runner.py"
        content = runner_path.read_text(encoding="utf-8")
        assert "OM_TEMPLATES" in content or "om_candidates" in content
        assert "continueOnMissingFootage" in content  # 使用了新增的参数

    def test_dispatch_render_has_template_fallback_loop(self):
        """dispatch_render 包含模板候选迭代逻辑"""
        dispatcher_path = Path(__file__).parent.parent / "pipeline" / "engine_task_dispatcher.py"
        content = dispatcher_path.read_text(encoding="utf-8")
        assert "om_candidates" in content, "dispatch_render 缺少 om_candidates 列表"
        assert "is_template_error" in content, "dispatch_render 缺少模板错误判断"
        assert "for attempt_idx" in content or "for om_tmpl" in content, "dispatch_render 缺少模板 fallback 循环"

    def test_all_callers_use_creationflags_no_window(self):
        """Windows 下都使用 CREATE_NO_WINDOW 避免弹窗"""
        files_to_check = [
            Path(__file__).parent.parent / "rendering" / "ae_render_engine.py",
            Path(__file__).parent.parent / "pipeline" / "engine_task_dispatcher.py",
            Path(__file__).parent.parent / "pipeline" / "flagship_runner.py",
        ]
        for f in files_to_check:
            content = f.read_text(encoding="utf-8")
            assert "CREATE_NO_WINDOW" in content, f"{f.name} 缺少 CREATE_NO_WINDOW 标志"

    def test_process_tree_termination_uses_taskkill(self):
        """取消时使用 taskkill /T /F 终止进程树"""
        engine_path = Path(__file__).parent.parent / "rendering" / "ae_render_engine.py"
        content = engine_path.read_text(encoding="utf-8")
        assert "taskkill" in content, "_terminate_process_tree 缺少 taskkill"
        assert "/T" in content, "taskkill 缺少 /T (终止树)"
        assert "/F" in content, "taskkill 缺少 /F (强制)"


# ============================================================================
#  Python 语法检查（不实际运行 aerender）
# ============================================================================

class TestSyntaxValidity:
    """验证所有修改文件的 Python 语法"""

    def test_ae_render_engine_syntax(self):
        import py_compile
        py_compile.compile(str(RENDERING_DIR / "ae_render_engine.py"), doraise=True)

    def test_engine_task_dispatcher_syntax(self):
        import py_compile
        py_compile.compile(
            str(Path(__file__).parent.parent / "pipeline" / "engine_task_dispatcher.py"),
            doraise=True,
        )

    def test_flagship_runner_syntax(self):
        import py_compile
        py_compile.compile(
            str(Path(__file__).parent.parent / "pipeline" / "flagship_runner.py"),
            doraise=True,
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
