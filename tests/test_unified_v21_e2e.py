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
import subprocess
import sys
from pathlib import Path

import pytest

# 2026-09-23 修正过度门控：原模块级 `pytestmark = pytest.mark.real_davinci`
# 把本文件全部用例锁死，但**逐个读过实现后确认：5 个用例没有一个需要 Resolve**
#   · test_style_presets       —— 纯字典断言（零依赖）
#   · test_smart_grade         —— 只做参数推荐（分析视频，不经 Resolve）
#   · test_frame_interpolate   —— FFmpeg 补帧
#   · test_full_pipeline_smart —— 实现注释明写"跳过 Resolve，避免启动重型应用"
#   · test_full_pipeline_style —— 只验证参数映射
# 门控用错标记的代价：在没装 Resolve 的机器上（含本机与 CI）**一个都不跑**，
# 于是这些用例既发现不了回归、也给不出集成信号。现改为按真实依赖门控
# （素材/FFmpeg），Resolve 相关能力若日后接入再单独加标记。
#
# 影响面已评估：全部 5 个用例仅依赖 FFmpeg 与真实素材，二者在本机与 CI 均具备。

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from integrations.unified_video_pipeline import (  # noqa: E402
    OPENMONTAGE_STYLE_MAP,
    UnifiedVideoPipeline,
)

# 候选素材目录，按优先级排列
# 2026-09-23: 增列 data/reference_top —— 仓库内本就常驻 145 条真实 AMV 参照
# (平均 35MB), 但此前不在候选里, 导致"明明有素材却 skip"。
_CANDIDATE_DIRS = (
    PROJECT_ROOT / "data" / "real_amv_test",
    PROJECT_ROOT / "data" / "reference_top",
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
def test_video(tmp_path_factory) -> str:
    """真实素材的**有界切片**：真实链路 + 时长可控。

    2026-09-23：原来直接把 35MB 的完整 AMV 交给用例，实测
    `test_frame_interpolate`（60fps 补帧）跑 240s 仍未完 —— 这正是本文件当初被
    整体门控的真实原因。e2e 需要的是"真实素材走真实链路"，不是"处理完整长片"，
    故取前 6 秒（ffmpeg 无损重封装式裁剪，仅重编码必要部分）作为测试素材。
    切片仍来自真实 AMV，链路与判据不变；耗时从分钟级降到可接受范围。
    """
    if TEST_VIDEO_PATH is None:
        pytest.skip("无可用测试素材")
    cut = tmp_path_factory.mktemp("v21_src") / "clip_6s.mp4"
    # 参数全部为字面量，不做字符串插值（无注入面）
    proc = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(TEST_VIDEO_PATH),
         "-t", "6", "-c:v", "libx264", "-preset", "veryfast",
         "-pix_fmt", "yuv420p", "-an", str(cut)],
        capture_output=True, text=True, timeout=180)
    if proc.returncode != 0 or not cut.exists() or cut.stat().st_size == 0:
        pytest.skip(f"素材切片失败: {(proc.stderr or '')[:200]}")
    return str(cut)


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
