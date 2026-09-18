#!/usr/bin/env python3
"""统一管线 v2.1 E2E 验证。

验证新增能力：
1. ``smart_grade_params()``  — 智能调色推荐
2. ``frame_interpolate()``   — FFmpeg 补帧
3. ``OPENMONTAGE_STYLE_MAP`` — 风格预设
4. ``full_pipeline()`` v2.1  — 全流程联动

素材来源
--------
此前硬编码了外部绝对路径 ``D:\\AE-Work\\output\\quick_test_warm_cinematic.mp4``，
在任何未搭建该目录的机器上都会直接失败（``OSError: Video file not found``）。

现改为按以下优先级自动解析测试素材，使该 E2E 在仓库内即可真实运行：

1. 环境变量 ``AEK_TEST_VIDEO`` 指定的文件；
2. 仓库内 ``data/real_amv_test`` 等目录下的真实视频素材；
3. 均不存在时 ``skip``（而非 ``fail``），避免把"环境缺素材"误报成"功能缺陷"。

依赖 FFmpeg 的用例在 FFmpeg 缺失时同样 ``skip``。
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.real_davinci  # 依赖真实 DaVinci Resolve(fuscript) + FFmpeg + 真实素材

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from integrations.unified_video_pipeline import (  # noqa: E402
    OPENMONTAGE_STYLE_MAP,
    UnifiedVideoPipeline,
)

# 候选素材目录，按优先级排列
_CANDIDATE_DIRS = (
    PROJECT_ROOT / "data" / "real_amv_test",
    PROJECT_ROOT / "data" / "output" / "me_watch_folder",
    PROJECT_ROOT / "data" / "test_videos",
)

_MIN_VIDEO_BYTES = 100 * 1024  # 过滤占位/损坏文件


def _discover_test_video() -> Path | None:
    """解析一个真实可用的测试视频。"""
    env_path = os.environ.get("AEK_TEST_VIDEO")
    if env_path:
        p = Path(env_path)
        if p.is_file() and p.stat().st_size >= _MIN_VIDEO_BYTES:
            return p

    for directory in _CANDIDATE_DIRS:
        if not directory.is_dir():
            continue
        candidates = [
            f
            for ext in ("*.mp4", "*.mov")
            for f in sorted(directory.glob(ext))
            if f.stat().st_size >= _MIN_VIDEO_BYTES
        ]
        if candidates:
            # 选体积最大的，通常时长/画面信息更充分
            return max(candidates, key=lambda f: f.stat().st_size)
    return None


TEST_VIDEO_PATH = _discover_test_video()

requires_video = pytest.mark.skipif(
    TEST_VIDEO_PATH is None,
    reason="未找到测试视频素材（可通过 AEK_TEST_VIDEO 指定）",
)
requires_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="未安装 FFmpeg"
)


@pytest.fixture(scope="module")
def test_video() -> str:
    return str(TEST_VIDEO_PATH)


@pytest.fixture(scope="module")
def output_dir(tmp_path_factory) -> str:
    return str(tmp_path_factory.mktemp("unified_v21_e2e"))


@pytest.fixture(scope="module")
def pipeline() -> UnifiedVideoPipeline:
    return UnifiedVideoPipeline()


@requires_video
def test_smart_grade(pipeline, test_video):
    """验证智能调色推荐返回合法参数区间。"""
    result = pipeline.smart_grade_params(test_video)

    for key in ("brightness", "contrast", "saturation", "preset", "reasoning"):
        assert key in result, f"Missing {key}"

    for key in ("brightness", "contrast", "saturation"):
        assert 0.5 <= result[key] <= 1.5, f"{key} out of range: {result[key]}"

    known_presets = set(OPENMONTAGE_STYLE_MAP) | {
        "cinematic",
        "filmic",
        "opendrt",
        "saturation",
        "shadow-contrast",
    }
    assert result["preset"] in known_presets, f"Unknown preset: {result['preset']}"


@requires_video
@requires_ffmpeg
def test_frame_interpolate(pipeline, test_video, output_dir):
    """验证 FFmpeg 补帧真实产出文件。"""
    output = os.path.join(output_dir, "e2e_v21_interp_60fps.mp4")
    result = pipeline.frame_interpolate(
        test_video, output, target_fps=60, method="blend"
    )

    assert result, "Frame interpolation returned empty path"
    assert os.path.isfile(result), f"Output file not found: {result}"
    assert os.path.getsize(result) > 100_000, "Output file too small"


def test_style_presets():
    """验证 OpenMontage 风格预设表完整（不依赖素材）。"""
    expected_styles = ["ghibli", "premium", "clean", "flat", "dramatic", "vivid"]
    for style in expected_styles:
        assert style in OPENMONTAGE_STYLE_MAP, f"Missing style: {style}"
        cfg = OPENMONTAGE_STYLE_MAP[style]
        for key in ("preset", "brightness", "contrast", "saturation", "description"):
            assert key in cfg, f"{style}: missing {key}"


@requires_video
@requires_ffmpeg
def test_full_pipeline_smart(pipeline, test_video, output_dir):
    """验证 full_pipeline v2.1 smart 模式（跳过 Resolve，避免启动重型应用）。"""
    results = pipeline.full_pipeline(
        video_path=test_video,
        output_dir=output_dir,
        smart_mode=True,
        do_quick_grade=False,
        do_resolve_grade=False,
        interpolate_fps=60,
        interpolate_method="blend",
    )

    assert "steps" in results
    steps = results["steps"]
    for step in ("smart_analysis", "scene_detect", "frame_interpolate"):
        assert step in steps, f"Missing step: {step}"
    assert "reasoning" in steps["smart_analysis"]


@requires_video
def test_full_pipeline_style(pipeline, test_video, output_dir):
    """验证 full_pipeline v2.1 style 模式参数映射正确。"""
    results = pipeline.full_pipeline(
        video_path=test_video,
        output_dir=output_dir,
        style="dramatic",
        do_quick_grade=False,
        do_resolve_grade=False,
    )

    steps = results["steps"]
    assert "style_preset" in steps
    style_data = steps["style_preset"]
    assert style_data["style"] == "dramatic"
    assert style_data["preset"] == "shadow-contrast"
