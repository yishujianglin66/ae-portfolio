#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""风格复制管线（Phase 0-3 交付）回归测试。

标记约定（与 pyproject [tool.pytest.ini_options] 对齐）：
  - 未标记的测试 = 离线单元/集成测试，CI 默认执行（addopts 排除 real_ffmpeg/slow 等）。
  - @pytest.mark.real_ffmpeg = 需真实 ffmpeg 二进制，本地 `pytest -m real_ffmpeg` 跑，CI 自动跳过。
"""
import os
import shutil
import subprocess
import sys
import tempfile

import pytest

# tests/conftest.py 已把项目根注入 sys.path，可顶层包方式导入
import bootstrap  # noqa: E402  (统一路径引导)
from style_copy.ffmpeg_generator import (  # noqa: E402
    STYLE_TO_FILTER_MAP,
    FFmpegCommandGenerator,
)
from style_copy.style_analyzer import (  # noqa: E402
    V4_AVAILABLE,
    LocalStyleAnalyzer,
    get_analyzer,
)
from style_copy.style_copy_mvp import supported_ff_filters  # noqa: E402
from style_copy.tool_orchestrator import ToolOrchestrator  # noqa: E402

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------------------
# 离线单测（无外部依赖，CI 默认执行）
# ---------------------------------------------------------------------------

def test_bootstrap_path_injection():
    """bootstrap 注入后，style_copy 包应可被顶层解析（跨目录 import 可用）。"""
    import style_copy
    assert style_copy.__name__ == "style_copy"
    paths = [os.path.abspath(p) for p in getattr(style_copy, "__path__", [])]
    assert any(p.startswith(PROJECT_ROOT) for p in paths), "style_copy 解析路径不在项目根下"
    assert any(os.path.abspath(p) == PROJECT_ROOT for p in sys.path), "项目根未注入 sys.path"


def test_get_analyzer_returns_analyzable():
    """get_analyzer() 返回一个具备 analyze_from_prompt 的分析器。

    环境无关：V4 不可用时退化为本地离线分析器（CI 场景）并验证真实成功；
    V4 可用时（本机场景）仅校验对象形态，避免触发远程 V4 调用。
    """
    a = get_analyzer()
    assert a is not None and hasattr(a, "analyze_from_prompt")
    if not V4_AVAILABLE:
        res = a.analyze_from_prompt("电影感暖色调快节奏")
        assert res.get("success") is True
        assert res.get("source") == "local_heuristic"
        assert "color_temperature" in res["style"]


def test_local_analyzer_keyword_mapping():
    """离线关键词启发式应正确映射色彩/节奏/特效。"""
    a = LocalStyleAnalyzer()
    res = a.analyze_from_prompt("电影感暖色调快节奏胶片颗粒辉光光晕")
    assert res["success"]
    s = res["style"]
    assert s["color_temperature"] == "warm"
    assert s["pace"] in ("fast", "very_fast")
    assert "cinematic" in s["effects"]
    assert "glow" in s["effects"] or "film_grain" in s["effects"]


def test_ffmpeg_generator_glow_bloom_mapping():
    """Phase 3 修复：glow/bloom 原生滤镜本机缺失，须映射到可用近似滤镜。"""
    assert STYLE_TO_FILTER_MAP["effects"]["glow"] == "unsharp=9:9:0.6"
    assert STYLE_TO_FILTER_MAP["effects"]["bloom"] == "gblur=sigma=6"
    g = FFmpegCommandGenerator()
    style = {"color_temperature": "warm", "contrast": "high",
             "effects": ["glow", "bloom", "cinematic"], "pace": "fast"}
    g.generate_command("in.mp4", "out.mp4", style)
    chain = ",".join(g.filters)
    assert "glow=strength" not in chain and "bloom=" not in chain, "仍存在缺失原生滤镜"
    assert "unsharp=9:9:0.6" in chain and "gblur=sigma=6" in chain


def test_tool_orchestrator_has_toolchain():
    """适配器收口：Phase1 ToolchainManager 应可导入（统一执行出口）。"""
    assert ToolOrchestrator._has_toolchain() is True


def test_orchestrate_rules_dag_offline():
    """离线规则编排（不执行）应产出含 ffmpeg 真实出片引擎的 DAG。"""
    orch = ToolOrchestrator(mode="auto")
    style = {"color_temperature": "warm", "contrast": "high",
             "effects": ["cinematic", "glow"], "pace": "medium"}
    seq = orch.generate_tool_sequence(style, "dummy.mp4")
    assert seq["success"]
    steps = seq["steps"]
    assert len(steps) >= 3
    assert "ffmpeg" in {s["tool"] for s in steps}


def test_run_style_copy_via_toolchain_routing():
    """统一入口路由决策：无论步骤成功与否，都应收口到 toolchain_manager 引擎。"""
    orch = ToolOrchestrator(mode="auto")
    style = {"effects": ["cinematic"], "pace": "medium", "color_temperature": "neutral"}
    seq = orch.generate_tool_sequence(style, "nonexistent.mp4")
    res = orch.execute_via_toolchain(seq["steps"], "nonexistent.mp4", mode="auto")
    assert res["engine"] == "toolchain_manager"


# ---------------------------------------------------------------------------
# 真实 ffmpeg 测试（本地执行，CI 跳过）
# ---------------------------------------------------------------------------

@pytest.mark.real_ffmpeg
def test_supported_ff_filters_real():
    """supported_ff_filters 应读 stdout+stderr 正确解析（本机实测 526 个）。"""
    s = supported_ff_filters()
    assert len(s) > 100, "supported_ff_filters 未正确解析（应读 stdout+stderr）"
    for n in ("unsharp", "gblur", "colorbalance", "eq", "setpts", "noise", "vignette"):
        assert n in s
    assert "glow" not in s and "bloom" not in s, "glow/bloom 本机不存在，不应出现在支持集合"


@pytest.mark.real_ffmpeg
def test_run_style_copy_via_toolchain_real():
    """本地：统一入口经真实 ffmpeg 出片，端到端成功。"""
    ffmpeg = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if not ffmpeg:
        pytest.skip("ffmpeg 未安装")

    src = tempfile.mktemp(suffix=".mp4")
    r = subprocess.run([ffmpeg, "-y", "-f", "lavfi",
                       "-i", "testsrc=duration=1:size=320x180:rate=12",
                       "-pix_fmt", "yuv420p", src],
                      capture_output=True, text=True, timeout=60)
    assert r.returncode == 0 and os.path.exists(src), "测试源生成失败"

    orch = ToolOrchestrator(mode="auto")
    style = {"color_temperature": "warm", "contrast": "high",
             "effects": ["cinematic", "glow"], "pace": "medium"}
    res = orch.run_style_copy_via_toolchain(style, src, mode="auto")
    assert res["engine"] == "toolchain_manager"
    assert res["success"] is True
    mp4 = [f for f in res.get("output_files", []) if f.endswith(".mp4")]
    assert mp4 and os.path.exists(mp4[0]), "未产出真实 mp4"


@pytest.mark.real_ffmpeg
@pytest.mark.slow
def test_mvp_cli_end_to_end():
    """端到端跑 MVP 命令行入口（自带源生成），验证真实成片。"""
    ffmpeg = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if not ffmpeg:
        pytest.skip("ffmpeg 未安装")

    out = tempfile.mktemp(suffix=".mp4")
    r = subprocess.run(
        [sys.executable, "style_copy/style_copy_mvp.py",
         "--prompt", "电影感暖色调快节奏胶片颗粒辉光",
         "--output", out],
        capture_output=True, text=True, timeout=120, cwd=PROJECT_ROOT,
    )
    assert r.returncode == 0, r.stderr[-500:]
    assert os.path.exists(out) and os.path.getsize(out) > 0
