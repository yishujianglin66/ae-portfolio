#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
style_copy 离线逻辑单测

覆盖纯逻辑（不依赖 V4 API / yt-dlp / AE / FFmpeg 真实二进制）：
  - FFmpegCommandGenerator：风格 -> 滤镜命令映射
  - ToolOrchestrator._generate_with_rules：风格 -> 工具 DAG
  - LocalStyleAnalyzer：提示词 -> 符合 STYLE_JSON_SCHEMA 的结构化风格
  - InputParser：提示词/URL 解析（不走下载/场景分割外部依赖）
全部离线、确定性、可复现。
"""
import bootstrap  # noqa: F401  确保项目子目录在 sys.path

from style_copy.ffmpeg_generator import FFmpegCommandGenerator
from style_copy.tool_orchestrator import ToolOrchestrator
from style_copy.style_analyzer import LocalStyleAnalyzer
from style_copy.input_parser import InputParser


# ---------------------------------------------------------------------------
# FFmpegCommandGenerator
# ---------------------------------------------------------------------------

def test_ffmpeg_command_basic_structure():
    g = FFmpegCommandGenerator()
    style = {
        "color_temperature": "warm",
        "contrast": "high",
        "effects": ["cinematic"],
        "pace": "fast",
    }
    cmd = g.generate_command("in.mp4", "out.mp4", style)
    assert cmd[0] == "ffmpeg"
    assert "-i" in cmd and "in.mp4" in cmd
    assert cmd[-1] == "out.mp4"
    assert "-filter_complex" in cmd
    fc = cmd[cmd.index("-filter_complex") + 1]
    # warm -> colorbalance, high -> eq contrast, fast -> setpts 变速
    assert "colorbalance=rs=0.2" in fc
    assert "eq=contrast=1.3" in fc
    assert "setpts=0.7*PTS" in fc
    # 编码参数齐全
    assert "-c:v" in cmd and "libx264" in cmd
    assert "-c:a" in cmd and "aac" in cmd


def test_ffmpeg_command_no_filters_for_neutral():
    g = FFmpegCommandGenerator()
    style = {"color_temperature": "neutral", "contrast": "medium", "pace": "medium"}
    cmd = g.generate_command("in.mp4", "out.mp4", style)
    # 中性风格不应产生 filter_complex
    assert "-filter_complex" not in cmd


def test_ffmpeg_command_effects_mapping():
    g = FFmpegCommandGenerator()
    style = {"effects": ["film_grain", "glow"]}
    cmd = g.generate_command("in.mp4", "out.mp4", style)
    fc = cmd[cmd.index("-filter_complex") + 1]
    # film_grain -> noise, glow -> unsharp 近似（见 ffmpeg_generator 注释）
    assert "noise=alls=8" in fc
    assert "unsharp=9:9:0.6" in fc


def test_ffmpeg_transition_two_inputs():
    g = FFmpegCommandGenerator()
    cmd = g.generate_transition_command(["a.mp4", "b.mp4"], "out.mp4", "dissolve")
    assert cmd[0] == "ffmpeg"
    assert cmd.count("-i") == 2
    assert "-filter_complex" in cmd
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert "xfade=transition=dissolve" in fc
    assert "[v]" in fc and "[a]" in fc


def test_ffmpeg_transition_single_input_fallback():
    g = FFmpegCommandGenerator()
    cmd = g.generate_transition_command(["only.mp4"], "out.mp4")
    assert cmd[0] == "ffmpeg"
    assert "-i" in cmd


# ---------------------------------------------------------------------------
# ToolOrchestrator（规则路径，离线）
# ---------------------------------------------------------------------------

def _orch() -> ToolOrchestrator:
    # 无 api_key -> 走规则编排（不调用 V4），完全离线
    return ToolOrchestrator(api_key=None, mode="real")


def test_orchestrator_no_api_key_uses_rules():
    o = _orch()
    assert o.v4_orchestrator is None
    style = {"effects": ["cinematic"]}
    res = o.generate_tool_sequence(style, "in.mp4")
    assert res["success"]  # 规则路径无需 V4 即可产出


def test_orchestrator_rules_returns_ffmpeg_step():
    o = _orch()
    style = {"effects": ["cinematic"], "color_temperature": "warm",
             "contrast": "high", "pace": "fast", "text_style": {"text": "标题"}}
    res = o.generate_tool_sequence(style, "in.mp4")
    steps = res["steps"]
    assert isinstance(steps, list) and len(steps) >= 2
    tools = [s["tool"] for s in steps]
    assert "ffmpeg" in tools


def test_orchestrator_rules_dependency_chain():
    o = _orch()
    style = {"effects": ["cinematic"], "text_style": {"text": "标题"}}
    res = o.generate_tool_sequence(style, "in.mp4")
    by_id = {s["step_id"]: s for s in res["steps"]}
    # 画质增强(step_1) 存在时，调色(step_2) 应依赖它
    if "step_1" in by_id and "step_2" in by_id:
        assert "step_1" in by_id["step_2"]["depends_on"]


def test_orchestrator_ffmpeg_filters_mapping():
    o = _orch()
    f = o._get_ffmpeg_filters(
        {"contrast": "high", "color_temperature": "warm", "pace": "fast"}
    )
    joined = ",".join(f)  # 滤镜以逗号拼接，逐元素做子串校验
    assert "eq=contrast=1.3" in joined
    assert "colorbalance=rs=0.1" in joined
    assert "setpts=0.7*PTS" in joined


def test_orchestrator_dry_run_offline():
    o = _orch()
    style = {"effects": ["cinematic"], "pace": "medium"}
    res = o.run_style_copy(style, "in.mp4", execute=False)
    assert res["success"]
    assert res["dry_run"] is True
    assert "steps" in res


# ---------------------------------------------------------------------------
# LocalStyleAnalyzer（离线启发式）
# ---------------------------------------------------------------------------

def test_local_analyzer_prompt_offline():
    a = LocalStyleAnalyzer()
    res = a.analyze_from_prompt("电影感暖色调快节奏胶片颗粒")
    assert res["success"]
    # source 位于结果顶层（非 style 内部）
    assert res["source"] == "local_heuristic"
    style = res["style"]
    # 字段合法值（与 STYLE_JSON_SCHEMA enum 对齐）
    assert style["color_temperature"] in ("warm", "cool", "neutral")
    assert style["pace"] in ("slow", "medium", "fast", "very_fast")
    assert isinstance(style["transitions"], list) and len(style["transitions"]) >= 2
    assert isinstance(style["effects"], list) and len(style["effects"]) >= 2


def test_local_analyzer_prompt_defaults():
    a = LocalStyleAnalyzer()
    res = a.analyze_from_prompt("一段普通视频")
    assert res["success"]
    style = res["style"]
    assert style["pace"] == "medium"
    # 无关键词时给出合法默认（≥2 元素）
    assert style["transitions"] == ["hard_cut", "dissolve"]
    assert style["effects"] == ["cinematic"]


# ---------------------------------------------------------------------------
# InputParser（提示词/URL 解析，离线）
# ---------------------------------------------------------------------------

def test_input_parser_prompt_path_offline():
    p = InputParser(work_dir=None)
    res = p.parse("电影感暖色调快节奏")
    assert res["success"]
    assert res["type"] == "prompt"
    assert res["prompt"] == "电影感暖色调快节奏"


def test_input_parser_detect_platform():
    p = InputParser(work_dir=None)
    assert p._detect_platform("https://www.youtube.com/watch?v=1") == "youtube"
    assert p._detect_platform("https://youtu.be/abc") == "youtube"
    assert p._detect_platform("https://www.bilibili.com/video/BV1") == "bilibili"
    assert p._detect_platform("https://www.douyin.com/abc") == "douyin"
    assert p._detect_platform("https://v.example.com/x.mp4") == "direct"


def test_input_parser_url_extraction():
    p = InputParser(work_dir=None)
    assert p._extract_url("看这个 https://example.com/x.mp4 很好") == "https://example.com/x.mp4"
    assert p._extract_url("纯文本没有链接") is None
