"""
P1 关键缺陷回归测试: _run_execute_real_mix 成功路径临时目录清理

缺陷背景 (bf99595 提交遗漏):
  - _run_execute_real_mix() 在段渲染前创建 tmp_dir = output/p1_execute_mix/_tmp_{run_id}/
  - 失败路径 (ALL_SEGMENTS_FAILED, OUTPUT_INVALID) 调用了 shutil.rmtree(tmp_dir) 清理
  - 成功路径 (return 前) 遗漏清理，每次遗留 segment MP4 + concat_list.txt
  - 累积影响: 每次运行遗留 50-500MB 临时文件，磁盘空间缓慢耗尽

触发条件 (具体可信场景):
  1. execute 阶段不产出真实视频 (execution_mode != real_mix / 空 aep)
  2. _ensure_real_mix_output() 检测到并调用 _run_execute_real_mix()
  3. _run_execute_real_mix() 成功生成 final_output MP4
  4. 返回结果，tmp_dir/{seg_00.mp4,seg_01.mp4,...,concat_list.txt} 永久残留

修复方式: 成功 return 前添加 shutil.rmtree(tmp_dir, ignore_errors=True)
本测试验证修复后，成功路径和失败路径均会清理临时目录。
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.real_e2e


# 项目根
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class TestRealMixTempdirCleanup:
    """验证 _run_execute_real_mix 所有路径都会清理 tmp_dir。"""

    @pytest.fixture
    def setup_pipeline(self, tmp_path):
        """构造最小化 UnifiedPipeline 实例 (不调用外部依赖)。"""
        from pipeline.unified_pipeline import PipelineConfig, UnifiedPipeline

        output_dir = tmp_path / "output"
        materials_dir = tmp_path / "materials"
        materials_dir.mkdir(parents=True, exist_ok=True)

        config = PipelineConfig(
            input_topic="cleanup_test",
            materials_dir=str(materials_dir),
            output_dir=str(output_dir),
            project_name="cleanup_regression",
            ffmpeg_bin=r"C:\ffmpeg\bin\ffmpeg.exe",
            enable_vrs=False,
            use_knowledge=False,
            enable_multi_agent=False,
            enable_feedback_loop=False,
        )
        pipe = UnifiedPipeline(config)
        pipe.run_id = "cleanup_test_001"
        return pipe, output_dir

    def test_no_sources_path_creates_no_tmpdir(self, setup_pipeline):
        """路径: NO_SOURCE → 无素材直接返回，不应创建 tmp_dir。"""
        pipe, output_dir = setup_pipeline
        result = pipe._run_execute_real_mix()

        assert result.get("error_code") == "NO_SOURCE"
        p1_dir = output_dir / "p1_execute_mix"
        # 无素材时不创建任何目录
        assert not (p1_dir / f"_tmp_{pipe.run_id}").exists()

    def test_all_segments_failed_cleans_tmpdir(self, setup_pipeline, tmp_path):
        """路径: ALL_SEGMENTS_FAILED → 明确清理 tmp_dir。

        通过 mock subprocess.run 让所有段渲染失败，验证 tmp_dir 被清理。
        """
        pipe, output_dir = setup_pipeline

        mat_dir = Path(pipe.config.materials_dir)
        fake_video = mat_dir / "fake.mp4"
        # 写内容确保 filesize 检查通过 (is_file 为 True)
        fake_video.write_bytes(b"x" * 2048)

        def _fake_duration(self, p):
            """段渲染的输入 fake_video 返回 10s (通过 SOURCE_TOO_SHORT 检查),
            段渲染后的输出文件返回默认值 (不影响此测试分支)。"""
            p_str = str(p)
            if p_str == str(fake_video):
                return 10.0
            return 0.0

        with patch.object(
            pipe.__class__, '_get_previous_data',
            return_value={"plan": {}, "perceive": {}}
        ):
            with patch(
                "pipeline.ffmpeg_edit_engine.FFmpegEditEngine._get_duration",
                autospec=True, side_effect=_fake_duration,
            ):
                with patch(
                    "pipeline.ffmpeg_edit_engine.FFmpegEditEngine._has_audio_stream",
                    return_value=False,
                ):
                    with patch("subprocess.run") as mock_run:
                        # 所有段渲染 returncode != 0 → 走到 ALL_SEGMENTS_FAILED
                        mock_run.return_value = MagicMock(returncode=1, stderr="mock fail")

                        result = pipe._run_execute_real_mix()

        assert result.get("error_code") == "ALL_SEGMENTS_FAILED", (
            f"期望 ALL_SEGMENTS_FAILED, 实际: {result.get('error_code')} / {result}"
        )
        # 关键断言: tmp_dir 不应存在
        tmp_dir = output_dir / "p1_execute_mix" / f"_tmp_{pipe.run_id}"
        assert not tmp_dir.exists(), (
            f"ALL_SEGMENTS_FAILED 路径未清理 tmp_dir: {tmp_dir}"
        )

    def test_success_path_cleans_tmpdir(self, setup_pipeline, tmp_path):
        """关键回归测试: 成功路径必须清理 tmp_dir。

        这是 bf99595 提交中实际遗漏的清理路径。
        通过 mock 让段渲染 + 拼接全部成功，验证返回后 tmp_dir 被删除。
        """
        pipe, output_dir = setup_pipeline

        mat_dir = Path(pipe.config.materials_dir)
        fake_video = mat_dir / "fake.mp4"
        # 写点内容让 >1024 检查通过
        fake_video.write_bytes(b"x" * 2048)

        # 构建 final_output，让验证通过
        p1_dir = output_dir / "p1_execute_mix"
        p1_dir.mkdir(parents=True, exist_ok=True)

        def _fake_subprocess_run(cmd, **kwargs):
            """区分: 段渲染/拼接 → 写一个假输出文件让检查通过。"""
            # 找输出文件名 (命令最后一个参数)
            out_file = None
            if len(cmd) >= 2 and isinstance(cmd, list):
                out_file = cmd[-1]
            if out_file and not Path(out_file).exists():
                Path(out_file).parent.mkdir(parents=True, exist_ok=True)
                # 写 2KB 假数据 (通过 >1024 检查)
                Path(out_file).write_bytes(b"y" * 2048)
            return MagicMock(returncode=0, stderr="", stdout="")

        with patch.object(
            pipe.__class__, '_get_previous_data',
            return_value={"plan": {}, "perceive": {}}
        ):
            with patch(
                "pipeline.ffmpeg_edit_engine.FFmpegEditEngine._get_duration",
                return_value=10.0,
            ):
                with patch(
                    "pipeline.ffmpeg_edit_engine.FFmpegEditEngine._has_audio_stream",
                    return_value=False,
                ):
                    with patch("subprocess.run", side_effect=_fake_subprocess_run):
                        result = pipe._run_execute_real_mix()

        # 必须返回 success (非失败)
        assert result.get("execution_mode") == "real_mix", (
            f"期望 real_mix 成功，实际: {result}"
        )
        assert result.get("output_path") or result.get("project_path"), (
            f"成功路径应产出 output_path / project_path: {result}"
        )

        # ========== 核心断言: 成功返回后 tmp_dir 必须被清理 ==========
        tmp_dir = output_dir / "p1_execute_mix" / f"_tmp_{pipe.run_id}"
        assert not tmp_dir.exists(), (
            f"REGRESSION: _run_execute_real_mix 成功路径未清理 tmp_dir!\n"
            f"  残留路径: {tmp_dir}\n"
            f"  修复: 在 return 前加 shutil.rmtree(tmp_dir, ignore_errors=True)"
        )
        # 列出残留内容 (若断言失败时可辅助调试)
        if tmp_dir.exists():
            leftover = list(tmp_dir.iterdir())
            print(f"LEFTOVER files in tmp_dir: {[f.name for f in leftover]}")

    def test_output_invalid_cleans_tmpdir(self, setup_pipeline, tmp_path):
        """路径: OUTPUT_INVALID → 明确清理 tmp_dir。

        段渲染全部成功，但最终拼接写出的文件无效 (<1KB)。
        """
        pipe, output_dir = setup_pipeline

        mat_dir = Path(pipe.config.materials_dir)
        fake_video = mat_dir / "fake.mp4"
        fake_video.write_bytes(b"x" * 2048)

        def _fake_subprocess_run(cmd, **kwargs):
            out_file = cmd[-1] if len(cmd) >= 2 and isinstance(cmd, list) else None
            if out_file and not Path(out_file).exists():
                Path(out_file).parent.mkdir(parents=True, exist_ok=True)
                # 段文件写 2KB (通过段检查)，但 final_output 写 100B → 触发 OUTPUT_INVALID
                if Path(out_file).name.startswith("seg_"):
                    Path(out_file).write_bytes(b"y" * 2048)
                else:
                    # concat_list.txt 正常写，final_output 只写 100B
                    if Path(out_file).suffix == ".txt":
                        Path(out_file).write_text("file 'x'\n", encoding="utf-8")
                    else:
                        Path(out_file).write_bytes(b"z" * 100)
            return MagicMock(returncode=0, stderr="", stdout="")

        with patch.object(
            pipe.__class__, '_get_previous_data',
            return_value={"plan": {}, "perceive": {}}
        ):
            with patch(
                "pipeline.ffmpeg_edit_engine.FFmpegEditEngine._get_duration",
                return_value=10.0,
            ):
                with patch(
                    "pipeline.ffmpeg_edit_engine.FFmpegEditEngine._has_audio_stream",
                    return_value=False,
                ):
                    with patch("subprocess.run", side_effect=_fake_subprocess_run):
                        result = pipe._run_execute_real_mix()

        assert result.get("error_code") == "OUTPUT_INVALID"
        tmp_dir = output_dir / "p1_execute_mix" / f"_tmp_{pipe.run_id}"
        assert not tmp_dir.exists(), (
            f"OUTPUT_INVALID 路径未清理 tmp_dir: {tmp_dir}"
        )
