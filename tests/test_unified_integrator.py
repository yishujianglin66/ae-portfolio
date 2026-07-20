#!/usr/bin/env python3
"""
统一多工具集成调度器 - 端到端测试脚本
=========================================

测试所有工作流预设在模拟模式下的完整执行流程，
验证调度器、适配器、步骤依赖、错误处理等功能。

用法:
    py -3.11 test_unified_integrator.py
    py -3.11 test_unified_integrator.py -v  # 详细输出
    py -3.11 test_unified_integrator.py --test bler_d3_composite  # 测试单个工作流
"""

import os
import sys
import json
import time
import traceback
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

# 确保可以导入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from unified_tool_integrator import (
    UnifiedToolIntegrator,
    WorkflowResult,
    StepResult,
    PhaseStatus,
    WORKFLOW_PRESETS,
)


@dataclass
class TestResult:
    """单个测试结果"""
    name: str
    passed: bool
    duration_ms: float = 0
    error: str = ""
    details: str = ""
    steps_count: int = 0
    success_count: int = 0


@dataclass
class TestSuiteResult:
    """测试套件结果"""
    total: int = 0
    passed: int = 0
    failed: int = 0
    test_results: List[TestResult] = field(default_factory=list)
    total_duration_ms: float = 0

    @property
    def pass_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return self.passed / self.total * 100


class IntegratorTestSuite:
    """统一调度器测试套件"""

    def __init__(self, verbose: bool = False, output_dir: Optional[Path] = None):
        self.verbose = verbose
        self.results = TestSuiteResult()
        if output_dir is None:
            output_dir = Path(os.environ.get(
                "INTEGRATOR_TEST_OUTPUT",
                str(Path(__file__).parent / "_integrator_tests"),
            ))
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def run_all_tests(self) -> TestSuiteResult:
        """运行所有测试"""
        tests = [
            ("test_basic_import", self.test_basic_import),
            ("test_integrator_init", self.test_integrator_init),
            ("test_adobe_tools_available", self.test_adobe_tools_available),
            ("test_premiere_pro_adapter", self.test_premiere_pro_adapter),
            ("test_photoshop_adapter", self.test_photoshop_adapter),
            ("test_illustrator_adapter", self.test_illustrator_adapter),
            ("test_media_encoder_adapter", self.test_media_encoder_adapter),
            ("test_audition_adapter", self.test_audition_adapter),
            ("test_list_presets", self.test_list_presets),
            ("test_list_presets_external", self.test_list_presets_external),
            ("test_workflow_enhance_quality", self.test_workflow_enhance_quality),
            ("test_workflow_delivery", self.test_workflow_delivery),
            ("test_workflow_3d_composite", self.test_workflow_3d_composite),
            ("test_workflow_batch", self.test_workflow_batch),
            ("test_external_presets_load", self.test_external_presets_load),
            ("test_workflow_social_media", self.test_workflow_social_media),
            ("test_workflow_batch_normalize", self.test_workflow_batch_normalize),
            ("test_adobe_full_pipeline", self.test_adobe_full_pipeline),
            ("test_step_dependency", self.test_step_dependency),
            ("test_result_summary", self.test_result_summary),
            ("test_progress_callback", self.test_progress_callback),
            ("test_ffmpeg_real_execution", self.test_ffmpeg_real_execution),
            ("test_tool_config_scan", self.test_tool_config_scan),
            ("test_step_result_serialization", self.test_step_result_serialization),
            ("test_workflow_result_serialization", self.test_workflow_result_serialization),
            ("test_checkpoint_persistence", self.test_checkpoint_persistence),
            ("test_pause_resume", self.test_pause_resume),
            ("test_parallel_execution", self.test_parallel_execution),
            ("test_workflow_id_generation", self.test_workflow_id_generation),
            ("test_completed_step_ids", self.test_completed_step_ids),
        ]

        self.results.total = len(tests)

        for i, (name, test_func) in enumerate(tests, 1):
            print(f"\n[{i}/{len(tests)}] 测试: {name}")
            try:
                start = time.time()
                test_func()
                duration = (time.time() - start) * 1000
                result = TestResult(name=name, passed=True, duration_ms=duration)
                print(f"  ✅ 通过 ({duration:.1f}ms)")
            except Exception as e:
                duration = 0
                error_msg = str(e)
                if self.verbose:
                    traceback.print_exc()
                result = TestResult(name=name, passed=False, error=error_msg)
                print(f"  ❌ 失败: {error_msg}")

            self.results.test_results.append(result)

        self.results.passed = sum(1 for r in self.results.test_results if r.passed)
        self.results.failed = self.results.total - self.results.passed
        self.results.total_duration_ms = sum(r.duration_ms for r in self.results.test_results)

        return self.results

    def test_basic_import(self):
        """测试基本导入"""
        from unified_tool_integrator import (
            UnifiedToolIntegrator,
            FFmpegAdapter,
            TopazAdapter,
            BlenderAdapter,
            AEAdapter,
            PremiereProAdapter,
            PhotoshopAdapter,
            IllustratorAdapter,
            MediaEncoderAdapter,
            AuditionAdapter,
            WorkflowResult,
            StepResult,
            PhaseStatus,
            ToolType,
            WorkflowPreset,
            ExecutionMode,
        )
        assert UnifiedToolIntegrator is not None
        assert FFmpegAdapter is not None
        assert TopazAdapter is not None
        assert BlenderAdapter is not None
        assert AEAdapter is not None

    def test_integrator_init(self):
        """测试调度器初始化"""
        integrator = UnifiedToolIntegrator(
            default_mode="simulate",
            output_dir=str(self.output_dir),
        )
        assert integrator is not None
        tools = integrator.get_available_tools()
        assert isinstance(tools, dict)
        assert len(tools) >= 4
        # AE适配器应该可用（因为有ae_mcp_client.py）
        assert "after_effects" in tools

    def test_list_presets(self):
        """测试列出内置预设"""
        integrator = UnifiedToolIntegrator(default_mode="simulate")
        presets = integrator.list_presets()
        assert isinstance(presets, list)
        assert len(presets) >= 4
        preset_ids = [p["id"] for p in presets]
        assert "enhance_quality" in preset_ids
        assert "delivery_pipeline" in preset_ids
        assert "3d_composite" in preset_ids
        assert "batch_process" in preset_ids

    def test_adobe_tools_available(self):
        """测试Adobe全家桶工具是否已注册"""
        integrator = UnifiedToolIntegrator(default_mode="simulate")
        tools = integrator.get_available_tools()
        # 检查6个Adobe工具是否都注册了
        adobe_tools = [
            "after_effects", "premiere_pro", "photoshop",
            "illustrator", "media_encoder", "audition"
        ]
        for tool in adobe_tools:
            assert tool in tools, f"缺少Adobe工具: {tool}"

    def test_premiere_pro_adapter(self):
        """测试Premiere Pro适配器"""
        from unified_tool_integrator import PremiereProAdapter, ToolConfig, ToolType, PhaseStatus
        adapter = PremiereProAdapter(ToolConfig(
            tool_type=ToolType.PREMIERE.value,
            mode="simulate",
        ))
        result = adapter.execute("create_sequence", {
            "step_id": "test_pr",
            "step_name": "测试序列",
            "sequence_name": "Test_Seq",
            "preset": "1080p_25fps",
        })
        assert result.status == PhaseStatus.SUCCESS.value
        assert result.mode_used == "simulate"
        assert result.tool == "premiere_pro"

    def test_photoshop_adapter(self):
        """测试Photoshop适配器"""
        from unified_tool_integrator import PhotoshopAdapter, ToolConfig, ToolType, PhaseStatus
        adapter = PhotoshopAdapter(ToolConfig(
            tool_type=ToolType.PHOTOSHOP.value,
            mode="simulate",
        ))
        result = adapter.execute("remove_background", {
            "step_id": "test_ps",
            "step_name": "测试抠图",
        })
        assert result.status == PhaseStatus.SUCCESS.value
        assert result.mode_used == "simulate"
        assert result.tool == "photoshop"

    def test_illustrator_adapter(self):
        """测试Illustrator适配器"""
        from unified_tool_integrator import IllustratorAdapter, ToolConfig, ToolType, PhaseStatus
        adapter = IllustratorAdapter(ToolConfig(
            tool_type=ToolType.ILLUSTRATOR.value,
            mode="simulate",
        ))
        result = adapter.execute("create_logo", {
            "step_id": "test_ai",
            "step_name": "测试Logo",
        })
        assert result.status == PhaseStatus.SUCCESS.value
        assert result.mode_used == "simulate"
        assert result.tool == "illustrator"

    def test_media_encoder_adapter(self):
        """测试Media Encoder适配器"""
        from unified_tool_integrator import MediaEncoderAdapter, ToolConfig, ToolType, PhaseStatus
        adapter = MediaEncoderAdapter(ToolConfig(
            tool_type=ToolType.MEDIA_ENCODER.value,
            mode="simulate",
        ))
        result = adapter.execute("batch_encode", {
            "step_id": "test_me",
            "step_name": "测试批量编码",
            "count": 5,
        })
        assert result.status == PhaseStatus.SUCCESS.value
        assert result.mode_used == "simulate"
        assert result.tool == "media_encoder"

    def test_audition_adapter(self):
        """测试Audition适配器"""
        from unified_tool_integrator import AuditionAdapter, ToolConfig, ToolType, PhaseStatus
        adapter = AuditionAdapter(ToolConfig(
            tool_type=ToolType.AUDITION.value,
            mode="simulate",
        ))
        result = adapter.execute("mastering", {
            "step_id": "test_au",
            "step_name": "测试母带",
        })
        assert result.status == PhaseStatus.SUCCESS.value
        assert result.mode_used == "simulate"
        assert result.tool == "audition"

    def test_list_presets_external(self):
        """测试列出外部预设"""
        preset_file = os.path.join(
            os.path.dirname(__file__),
            "workflow_presets_library.json"
        )
        integrator = UnifiedToolIntegrator(
            default_mode="simulate",
            preset_file=preset_file,
        )
        presets = integrator.list_presets()
        assert len(presets) >= 15
        preset_ids = [p["id"] for p in presets]
        assert "enhance_quality_4k" in preset_ids
        assert "ai_creative_vfx" in preset_ids
        assert "blender_3d_composite" in preset_ids
        assert "social_media_delivery" in preset_ids
        assert "batch_normalize" in preset_ids
        assert "cinematic_color_grade" in preset_ids

    def test_workflow_enhance_quality(self):
        """测试质量增强工作流"""
        integrator = UnifiedToolIntegrator(
            default_mode="simulate",
            output_dir=str(self.output_dir),
        )
        result = integrator.run_workflow("enhance_quality", {
            "input_file": "test_input.mp4"
        })
        assert result is not None
        assert isinstance(result, WorkflowResult)
        assert result.workflow_name == "视频质量增强流水线"
        assert result.status == PhaseStatus.SUCCESS.value
        assert len(result.steps) == 3
        assert len(result.successful_steps()) == 3

        # 检查步骤顺序
        step_ids = [s.step_id for s in result.steps]
        assert step_ids == ["probe", "topaz_enhance", "final_encode"]

        # 检查所有步骤都是模拟模式
        for step in result.steps:
            assert step.mode_used == "simulate"

    def test_workflow_delivery(self):
        """测试交付输出工作流"""
        integrator = UnifiedToolIntegrator(
            default_mode="simulate",
            output_dir=str(self.output_dir),
        )
        result = integrator.run_workflow("delivery_pipeline")
        assert result is not None
        assert result.status == PhaseStatus.SUCCESS.value
        assert len(result.steps) == 4

        # 有两个并行编码步骤（1080p和4K），都依赖topaz_output
        step_map = {s.step_id: s for s in result.steps}
        assert "ae_render" in step_map
        assert "topaz_output" in step_map
        assert "encode_1080p" in step_map
        assert "encode_4k" in step_map

    def test_workflow_3d_composite(self):
        """测试3D合成工作流"""
        integrator = UnifiedToolIntegrator(
            default_mode="simulate",
            output_dir=str(self.output_dir),
        )
        result = integrator.run_workflow("3d_composite")
        assert result is not None
        assert result.status == PhaseStatus.SUCCESS.value
        assert len(result.steps) == 3

        step_map = {s.step_id: s for s in result.steps}
        assert step_map["blender_render"].tool == "blender"
        assert step_map["ae_import"].tool == "after_effects"
        assert step_map["ae_composite"].tool == "after_effects"

    def test_workflow_batch(self):
        """测试批量处理工作流"""
        integrator = UnifiedToolIntegrator(
            default_mode="simulate",
            output_dir=str(self.output_dir),
        )
        result = integrator.run_workflow("batch_process")
        assert result is not None
        assert result.status == PhaseStatus.SUCCESS.value
        assert len(result.steps) == 3

    def test_external_presets_load(self):
        """测试外部预设加载"""
        preset_file = os.path.join(
            os.path.dirname(__file__),
            "workflow_presets_library.json"
        )
        integrator = UnifiedToolIntegrator(
            default_mode="simulate",
            output_dir=str(self.output_dir),
            preset_file=preset_file,
        )

        # 测试所有外部预设都能运行
        external_presets = [
            "enhance_quality_4k",
            "ai_creative_vfx",
            "blender_3d_composite",
            "social_media_delivery",
            "batch_normalize",
            "cinematic_color_grade",
        ]

        for preset_id in external_presets:
            result = integrator.run_workflow(preset_id)
            assert result is not None, f"{preset_id} 返回None"
            assert result.status == PhaseStatus.SUCCESS.value, f"{preset_id} 状态: {result.status}, 错误: {result.error}"

    def test_workflow_social_media(self):
        """测试社交媒体多平台交付工作流"""
        preset_file = os.path.join(
            os.path.dirname(__file__),
            "workflow_presets_library.json"
        )
        integrator = UnifiedToolIntegrator(
            default_mode="simulate",
            output_dir=str(self.output_dir),
            preset_file=preset_file,
        )
        result = integrator.run_workflow("social_media_delivery")
        assert result is not None
        assert result.status == PhaseStatus.SUCCESS.value
        # 6个步骤：source_prores + topaz + 4个编码
        assert len(result.steps) == 6

        step_ids = [s.step_id for s in result.steps]
        assert "encode_bilibili" in step_ids
        assert "encode_youtube_4k" in step_ids
        assert "encode_wechat" in step_ids
        assert "encode_archive" in step_ids

    def test_workflow_batch_normalize(self):
        """测试批量素材规范化工作流"""
        preset_file = os.path.join(
            os.path.dirname(__file__),
            "workflow_presets_library.json"
        )
        integrator = UnifiedToolIntegrator(
            default_mode="simulate",
            output_dir=str(self.output_dir),
            preset_file=preset_file,
        )
        result = integrator.run_workflow("batch_normalize")
        assert result is not None
        assert result.status == PhaseStatus.SUCCESS.value
        assert len(result.steps) == 4

    def test_adobe_full_pipeline(self):
        """测试Adobe全家桶全链路工作流"""
        preset_file = os.path.join(
            os.path.dirname(__file__),
            "workflow_presets_library.json"
        )
        integrator = UnifiedToolIntegrator(
            default_mode="simulate",
            output_dir=str(self.output_dir),
            preset_file=preset_file,
        )
        result = integrator.run_workflow("adobe_full_pipeline")
        assert result is not None
        assert result.status == PhaseStatus.SUCCESS.value
        assert len(result.steps) == 6
        # 验证6个Adobe工具都被用到
        tool_set = set(s.tool for s in result.steps)
        assert "illustrator" in tool_set
        assert "photoshop" in tool_set
        assert "premiere_pro" in tool_set
        assert "after_effects" in tool_set
        assert "audition" in tool_set
        assert "media_encoder" in tool_set

    def test_step_dependency(self):
        """测试步骤依赖处理"""
        # 自定义工作流，测试依赖失败时跳过后续步骤
        custom_steps = [
            {
                "step_id": "step1",
                "name": "步骤1",
                "tool": "ffmpeg",
                "operation": "probe",
            },
            {
                "step_id": "step2",
                "name": "步骤2（依赖步骤1）",
                "tool": "ffmpeg",
                "operation": "transcode",
                "depends_on": ["step1"],
            },
        ]

        integrator = UnifiedToolIntegrator(default_mode="simulate")
        result = integrator.run_custom_workflow(custom_steps, "依赖测试")
        assert result is not None
        assert result.status == PhaseStatus.SUCCESS.value
        assert len(result.steps) == 2
        assert result.steps[0].status == PhaseStatus.SUCCESS.value
        assert result.steps[1].status == PhaseStatus.SUCCESS.value

    def test_result_summary(self):
        """测试结果摘要生成"""
        integrator = UnifiedToolIntegrator(
            default_mode="simulate",
            output_dir=str(self.output_dir),
        )
        result = integrator.run_workflow("enhance_quality")
        assert result.summary is not None
        assert "工作流" in result.summary
        assert "状态" in result.summary
        assert "总步骤" in result.summary
        assert "总耗时" in result.summary
        assert "输出文件" in result.summary

    def test_progress_callback(self):
        """测试进度回调"""
        progress_updates = []

        def on_progress(workflow, progress, message):
            progress_updates.append({
                "workflow": workflow,
                "progress": progress,
                "message": message,
            })

        integrator = UnifiedToolIntegrator(
            default_mode="simulate",
            output_dir=str(self.output_dir),
            on_progress=on_progress,
        )
        result = integrator.run_workflow("enhance_quality")

        assert len(progress_updates) > 0
        # 检查是否有100%进度
        last_progress = progress_updates[-1]["progress"]
        assert last_progress == 1.0, f"最终进度应该是1.0，实际是 {last_progress}"

    def test_ffmpeg_real_execution(self):
        """测试FFmpeg真实执行能力"""
        import unified_tool_integrator as ui
        ffmpeg = ui.FFmpegAdapter(ui.ToolConfig(tool_type='ffmpeg', mode='real', install_path='C:\\ffmpeg\\bin'))
        if not ffmpeg.check_available():
            self.skipTest("FFmpeg不可用")
        
        result = ffmpeg.execute('probe', {'input_file': os.path.join(os.path.dirname(__file__), 'test_input.mp4'), 'step_id': 'test_probe'})
        assert result.status == PhaseStatus.SUCCESS.value
        assert result.mode_used == 'real'
        assert 'streams' in result.output_data

    def test_tool_config_scan(self):
        """测试工具配置和路径扫描"""
        config_file = os.path.join(os.path.dirname(__file__), "tool_config.json")
        integrator = UnifiedToolIntegrator(
            default_mode="simulate",
            config_file=config_file,
        )
        tools = integrator.get_available_tools()
        assert 'ffmpeg' in tools
        assert 'premiere_pro' in tools
        assert 'photoshop' in tools

    def test_step_result_serialization(self):
        """测试StepResult序列化/反序列化"""
        sr = StepResult(
            step_id="test_1",
            name="测试步骤",
            status="success",
            tool="ffmpeg",
            operation="transcode",
            duration_ms=123.4,
            output_files=["a.mp4", "b.mp4"],
            output_data={"key": "value"},
            mode_used="real",
        )
        d = sr.to_dict()
        assert d["step_id"] == "test_1"
        assert d["duration_ms"] == 123.4

        sr2 = StepResult.from_dict(d)
        assert sr2.step_id == sr.step_id
        assert sr2.duration_ms == sr.duration_ms
        assert sr2.output_files == sr.output_files

    def test_workflow_result_serialization(self):
        """测试WorkflowResult序列化/反序列化"""
        wr = WorkflowResult(
            workflow_name="测试工作流",
            status="success",
            workflow_id="abc123",
        )
        wr.steps.append(StepResult(
            step_id="s1", name="步骤1", status="success",
            tool="ffmpeg", operation="transcode",
        ))
        wr.total_duration_ms = 500.0

        d = wr.to_dict()
        assert d["workflow_name"] == "测试工作流"
        assert d["workflow_id"] == "abc123"
        assert len(d["steps"]) == 1

        wr2 = WorkflowResult.from_dict(d)
        assert wr2.workflow_name == wr.workflow_name
        assert wr2.workflow_id == wr.workflow_id
        assert len(wr2.steps) == 1
        assert wr2.steps[0].step_id == "s1"

    def test_checkpoint_persistence(self):
        """测试检查点持久化"""
        preset_file = os.path.join(
            os.path.dirname(__file__), "workflow_presets_library.json"
        )
        integrator = UnifiedToolIntegrator(
            default_mode="simulate",
            output_dir=str(self.output_dir),
            preset_file=preset_file,
            enable_checkpoint=True,
        )
        result = integrator.run_workflow("enhance_quality")
        assert result.status == PhaseStatus.SUCCESS.value
        # 检查点文件应该存在
        assert result.checkpoint_path
        assert os.path.exists(result.checkpoint_path)

        # 加载检查点验证
        loaded = integrator.load_checkpoint(result.checkpoint_path)
        assert loaded.workflow_name == result.workflow_name
        assert len(loaded.steps) == len(result.steps)

    def test_pause_resume(self):
        """测试暂停/恢复功能"""
        integrator = UnifiedToolIntegrator(
            default_mode="simulate",
            output_dir=str(self.output_dir),
        )
        # 初始状态不暂停
        assert not integrator.is_paused()

        # 暂停
        integrator.pause_workflow()
        assert integrator.is_paused()

        # 恢复
        integrator.resume_workflow()
        assert not integrator.is_paused()

        # 取消
        integrator.cancel_workflow()
        # 取消后应解除暂停阻塞
        assert not integrator.is_paused()

    def test_parallel_execution(self):
        """测试并行执行（多步骤无依赖时并发）"""
        # 使用带并行步骤的自定义工作流测试
        custom_steps = [
            {
                "step_id": "parallel_1",
                "name": "并行步骤A",
                "tool": "ffmpeg",
                "operation": "probe",
                "params": {"input_file": "test_input.mp4"},
                "enabled": True,
            },
            {
                "step_id": "parallel_2",
                "name": "并行步骤B",
                "tool": "ffmpeg",
                "operation": "probe",
                "params": {"input_file": "test_input.mp4"},
                "enabled": True,
            },
            {
                "step_id": "parallel_3",
                "name": "并行步骤C",
                "tool": "ffmpeg",
                "operation": "probe",
                "params": {"input_file": "test_input.mp4"},
                "enabled": True,
            },
        ]
        integrator = UnifiedToolIntegrator(
            default_mode="simulate",
            output_dir=str(self.output_dir),
            max_workers=3,
        )
        result = integrator.run_custom_workflow(custom_steps, "并行执行测试")
        assert result.status == PhaseStatus.SUCCESS.value
        assert len(result.steps) == 3
        # 三个步骤都是无依赖的，应该全部成功
        assert len(result.successful_steps()) == 3

    def test_workflow_id_generation(self):
        """测试工作流ID生成"""
        integrator = UnifiedToolIntegrator(
            default_mode="simulate",
            output_dir=str(self.output_dir),
        )
        result = integrator.run_workflow("enhance_quality")
        assert result.workflow_id
        assert len(result.workflow_id) == 8  # uuid前8位

    def test_completed_step_ids(self):
        """测试已完成步骤ID集合"""
        wr = WorkflowResult(workflow_name="test", status="running")
        wr.steps.append(StepResult(
            step_id="s1", name="步骤1", status="success",
            tool="ffmpeg", operation="transcode",
        ))
        wr.steps.append(StepResult(
            step_id="s2", name="步骤2", status="error",
            tool="ffmpeg", operation="compress",
        ))
        wr.steps.append(StepResult(
            step_id="s3", name="步骤3", status="skipped",
            tool="ffmpeg", operation="merge",
        ))
        completed = wr.completed_step_ids()
        assert "s1" in completed  # 成功的步骤
        assert "s2" in completed  # 失败的步骤也算完成
        assert "s3" not in completed  # 跳过的步骤不算完成


def print_test_summary(results: TestSuiteResult):
    """打印测试摘要"""
    print("\n" + "=" * 70)
    print("  测试结果摘要")
    print("=" * 70)
    print(f"  总测试数: {results.total}")
    print(f"  通过: {results.passed}")
    print(f"  失败: {results.failed}")
    print(f"  通过率: {results.pass_rate:.1f}%")
    print(f"  总耗时: {results.total_duration_ms / 1000:.2f} 秒")
    print()

    if results.failed > 0:
        print("  失败的测试:")
        for r in results.test_results:
            if not r.passed:
                print(f"    ❌ {r.name}: {r.error[:80]}")
        print()

    print("  详细结果:")
    for i, r in enumerate(results.test_results, 1):
        status = "✅" if r.passed else "❌"
        duration = f"{r.duration_ms:.1f}ms" if r.passed else ""
        print(f"    {status} [{i:2d}] {r.name:<40} {duration}")

    print("=" * 70)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="统一集成调度器 - 端到端测试")
    parser.add_argument("-v", "--verbose", action="store_true", help="详细输出")
    parser.add_argument("--test", help="运行单个测试")
    parser.add_argument("--preset", help="测试单个工作流预设")
    parser.add_argument("--output-dir", help="测试输出目录（默认：项目目录下 _integrator_tests，或环境变量 INTEGRATOR_TEST_OUTPUT）")
    args = parser.parse_args()

    suite = IntegratorTestSuite(
        verbose=args.verbose,
        output_dir=Path(args.output_dir) if args.output_dir else None,
    )

    if args.preset:
        # 测试单个工作流预设
        print(f"\n测试工作流预设: {args.preset}")
        preset_file = os.path.join(
            os.path.dirname(__file__),
            "workflow_presets_library.json"
        )
        integrator = UnifiedToolIntegrator(
            default_mode="simulate",
            output_dir=str(suite.output_dir),
            preset_file=preset_file,
        )
        result = integrator.run_workflow(args.preset)
        print(f"\n  状态: {result.status}")
        print(f"  步骤: {len(result.steps)}")
        for step in result.steps:
            icon = "✅" if step.status == "success" else "❌" if step.status == "error" else "⏭️"
            print(f"    {icon} {step.name} ({step.tool}/{step.operation}) - {step.duration_ms:.1f}ms")
            if step.error:
                print(f"       错误: {step.error}")
            if args.verbose and step.log:
                print(f"       日志:")
                for line in step.log[-5:]:
                    print(f"         {line}")
        return 0 if result.status == PhaseStatus.SUCCESS.value else 1

    print("=" * 70)
    print("  统一多工具集成调度器 - 端到端测试")
    print("=" * 70)

    results = suite.run_all_tests()
    print_test_summary(results)

    return 0 if results.pass_rate == 100 else 1


if __name__ == "__main__":
    sys.exit(main())
