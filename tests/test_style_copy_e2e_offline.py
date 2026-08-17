#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
style_copy 端到端离线串联测试（片 B）

目标：在**不依赖**真实 V4/yt-dlp/AE/FFmpeg 的前提下，跑通整条风格复制链路：
    InputParser(提示词) → LocalStyleAnalyzer → ToolOrchestrator(规则 DAG)
    → FFmpegCommandGenerator → 合法 FFmpeg 命令
证明 DAG 编排产出结构合法、依赖闭环、最终命令可执行（结构层面）。

手法：
  - 强制 get_analyzer 返回 LocalStyleAnalyzer（离线启发式，避免选中 V4 触发真实 LLM）
  - ToolOrchestrator 不传 api_key → 走规则路径（无 V4）
  - 提示词输入 → workflow 不进入 FFmpeg 真实执行分支（DAG 计划即产物）
全部离线、确定性、可复现，不触网不触外部二进制。
"""
import bootstrap  # noqa: F401  确保项目子目录在 sys.path

import pytest

from style_copy import style_analyzer
from style_copy.style_analyzer import LocalStyleAnalyzer
from style_copy.workflow import StyleCopyWorkflow
from style_copy.ffmpeg_generator import FFmpegCommandGenerator


@pytest.fixture
def offline_workflow(monkeypatch):
    """强制离线分析器，使 StyleCopyWorkflow 全程离线可跑。

    注意：workflow.py 以 `from style_copy.style_analyzer import get_analyzer`
    在导入期绑定了函数引用，因此必须直接 patch workflow 模块自身的
    get_analyzer 属性，而非仅 patch style_analyzer.get_analyzer
    （后者不影响已绑定的局部名，会出现 V4Agent 真实探测）。
    """
    import style_copy.workflow as _wf

    monkeypatch.setattr(_wf, "get_analyzer", lambda *a, **k: LocalStyleAnalyzer())
    return StyleCopyWorkflow()


def test_e2e_prompt_workflow_completes_offline(offline_workflow):
    """提示词输入：分析+编排两阶段完成，流程标记为成功。"""
    res = offline_workflow.run("电影感暖色调快节奏胶片颗粒")
    assert res["success"] is True
    assert res["step"] == "completed"
    assert "style" in res["data"]
    assert "tool_sequence" in res["data"]


def test_e2e_dag_dependency_integrity(offline_workflow):
    """工具 DAG 的依赖必须指向已存在的步骤（无悬空依赖）。"""
    res = offline_workflow.run("电影感暖色调快节奏")
    steps = res["data"]["tool_sequence"]
    ids = {s["step_id"] for s in steps}
    assert ids, "编排未产出任何步骤"
    for s in steps:
        for dep in s.get("depends_on", []):
            assert dep in ids, f"步骤 {s['step_id']} 指向悬空依赖 {dep}"


def test_e2e_dag_to_ffmpeg_command_valid(offline_workflow):
    """DAG 产出的风格 → FFmpegCommandGenerator 生成结构合法的命令。"""
    res = offline_workflow.run("电影感暖色调快节奏胶片颗粒")
    style = res["data"]["style"]
    cmd = FFmpegCommandGenerator().generate_command("in.mp4", "out.mp4", style)
    assert cmd[0] == "ffmpeg"
    assert "-i" in cmd and "in.mp4" in cmd
    assert cmd[-1] == "out.mp4"
    assert "-c:v" in cmd and "libx264" in cmd
    assert "-c:a" in cmd and "aac" in cmd
    # 暖色调应映射出 colorbalance 滤镜（验证风格→滤镜链闭环）
    if "-filter_complex" in cmd:
        fc = cmd[cmd.index("-filter_complex") + 1]
        assert "colorbalance" in fc


def test_e2e_prompt_style_differs_by_keywords(offline_workflow):
    """不同色温关键词应产出不同结构化风格（验证分析器区分度）。"""
    warm = offline_workflow.run("暖色调夕阳")["data"]["style"]
    cool = offline_workflow.run("冷色调科技蓝调")["data"]["style"]
    assert warm["color_temperature"] == "warm"
    assert cool["color_temperature"] == "cool"
    # 不同色温关键词 -> 结构化风格在色温维度确有区分
    assert warm["color_temperature"] != cool["color_temperature"]


def test_e2e_prompt_pace_differs_by_keywords(offline_workflow):
    """快/慢节奏关键词应产出不同 pace（验证分析器 tempo 区分度）。"""
    fast = offline_workflow.run("快节奏动感卡点")["data"]["style"]
    slow = offline_workflow.run("慢节奏舒缓")["data"]["style"]
    assert fast["pace"] in ("fast", "very_fast")
    assert slow["pace"] == "slow"
    assert fast["pace"] != slow["pace"]


def test_e2e_unknown_prompt_graceful_fallback(offline_workflow):
    """无风格描述的普通提示词：优雅降级为合法默认风格，不崩溃。"""
    res = offline_workflow.run("一段普通视频没有风格描述")
    assert res["success"] is True
    style = res["data"]["style"]
    assert style["pace"] == "medium"  # 默认兜底
    assert isinstance(style["transitions"], list)
    assert isinstance(style["effects"], list)


def test_e2e_full_chain_explicit_composition():
    """显式组合各阶段（不经 StyleCopyWorkflow），验证链路可独立拼装。"""
    analyzer = LocalStyleAnalyzer()
    from style_copy.tool_orchestrator import ToolOrchestrator

    orch = ToolOrchestrator(api_key=None)  # 规则路径，离线
    style = analyzer.analyze_from_prompt("电影感快节奏")["style"]
    seq = orch.generate_tool_sequence(style, "")
    assert seq["success"]
    steps = seq["steps"]
    assert steps
    # 最终滤镜命令仍合法
    cmd = FFmpegCommandGenerator().generate_command("in.mp4", "out.mp4", style)
    assert cmd[0] == "ffmpeg" and cmd[-1] == "out.mp4"
