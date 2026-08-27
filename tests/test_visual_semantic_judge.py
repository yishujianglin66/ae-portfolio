"""tests/test_visual_semantic_judge.py — 语义级视觉评判器测试

覆盖:
  - 规则后端: 黑帧/纯白/正常视频判分、硬性否决、文件过小、文件缺失
  - VLM 后端: prompt 构造、JSON 解析、正则降级、解析失败
  - 统一入口: backend=rule/auto/vlm 不可用降级、VLM mock 融合逻辑
  - PipelineConfig: 语义评判配置钳制
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from pipeline.visual_semantic_judge import (
    JudgeReport,
    RuleJudge,
    VisualSemanticJudge,
    VLMJudge,
)

FFMPEG = shutil.which("ffmpeg")


# ============================================================================
#  视频合成 fixtures (ffmpeg lavfi)
# ============================================================================

def _make_video(tmp_path: Path, name: str, src: str, duration: int = 5) -> Path:
    out = tmp_path / name
    subprocess.run(
        ["ffmpeg", "-y", "-v", "quiet", "-f", "lavfi", "-i", src,
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out)],
        check=True, timeout=60,
    )
    return out


@pytest.fixture(scope="module")
def videos(tmp_path_factory) -> dict:
    if not FFMPEG:
        pytest.skip("ffmpeg not available")
    tmp = tmp_path_factory.mktemp("judge_videos")
    return {
        "black": _make_video(tmp, "black.mp4",
                             "color=c=black:size=320x240:rate=24:duration=5"),
        "white": _make_video(tmp, "white.mp4",
                             "color=c=white:size=320x240:rate=24:duration=5"),
        "normal": _make_video(tmp, "normal.mp4",
                              "testsrc2=size=640x480:rate=24:duration=5"),
    }


@pytest.fixture
def rule_judge() -> RuleJudge:
    return RuleJudge()


# ============================================================================
#  规则后端
# ============================================================================

class TestRuleJudge:
    def test_black_video_hard_veto(self, rule_judge, videos):
        report = rule_judge.judge(str(videos["black"]))
        assert report.hard_veto is True
        assert report.passed is False
        assert report.score <= 40.0
        assert report.metrics["black_ratio"] > 0.3
        assert any("黑帧" in i for i in report.issues)
        assert report.recommendations  # 供重试调参消费

    def test_white_video_solid_veto(self, rule_judge, videos):
        report = rule_judge.judge(str(videos["white"]))
        assert report.hard_veto is True
        assert report.metrics["solid_ratio"] > 0.85

    def test_normal_video_passes(self, rule_judge, videos):
        report = rule_judge.judge(str(videos["normal"]))
        assert report.hard_veto is False
        assert report.passed is True
        assert report.score >= 60.0
        assert report.metrics["black_ratio"] < 0.1

    def test_tiny_file_veto(self, rule_judge, tmp_path):
        tiny = tmp_path / "tiny.mp4"
        tiny.write_bytes(b"\x00" * 1024)  # 1KB < 100KB 渲染验证标准
        report = rule_judge.judge(str(tiny))
        assert report.hard_veto is True
        assert report.passed is False
        assert any("文件过小" in i for i in report.issues)

    def test_missing_file_veto(self, rule_judge, tmp_path):
        report = rule_judge.judge(str(tmp_path / "no_such.mp4"))
        assert report.hard_veto is True
        assert report.score == 0.0

    def test_report_serializable(self, rule_judge, videos):
        d = rule_judge.judge(str(videos["normal"])).to_dict()
        assert set(d) >= {"score", "passed", "issues", "recommendations",
                          "backend", "hard_veto", "metrics"}
        json.dumps(d)  # 必须可序列化 (供 _results 落盘)


# ============================================================================
#  VLM 后端 (不加载模型, 测解析与 prompt)
# ============================================================================

class TestVLMJudgeParsing:
    def test_parse_valid_json(self):
        text = '分析如下 {"black_frame": 9, "color_anomaly": 8, ' \
               '"effect_presence": 7, "transition_quality": 8, ' \
               '"style_coherence": 9, "issues": ["转场略快"]} 完毕'
        dims, issues = VLMJudge._parse_output(text)
        assert dims is not None
        assert dims["black_frame"] == 9
        assert dims["effect_presence"] == 7
        assert issues == ["转场略快"]

    def test_parse_clamps_range(self):
        text = '{"black_frame": 15, "color_anomaly": -3}'
        dims, _ = VLMJudge._parse_output(text)
        assert dims["black_frame"] == 10.0
        assert dims["color_anomaly"] == 0.0

    def test_parse_regex_fallback(self):
        # 非法 JSON (缺引号) 但逐项模式存在 → 正则降级
        text = "结果: {black_frame: 6, color_anomaly: 7}"
        dims, issues = VLMJudge._parse_output(text)
        assert dims is None  # 无引号键, JSON与带引号正则均不匹配
        text2 = 'oops {"black_frame": 6, "color_anomaly": 7 后面坏了'
        dims2, _ = VLMJudge._parse_output(text2)
        assert dims2 == {"black_frame": 6.0, "color_anomaly": 7.0}

    def test_parse_failure_returns_none(self):
        dims, issues = VLMJudge._parse_output("这是一段没有分数的描述文字")
        assert dims is None
        assert issues == []

    def test_build_prompt_with_context(self):
        prompt = VLMJudge.build_prompt({
            "effect_stack": [{"name": "particle_burst"}, {"name": "glitch"}],
            "style_params": {"style": "赛博暗黑"},
        })
        assert "particle_burst" in prompt
        assert "赛博暗黑" in prompt
        assert "JSON" in prompt

    def test_build_prompt_without_context(self):
        prompt = VLMJudge.build_prompt(None)
        assert "无附加创作意图信息" in prompt

    def test_is_available_requires_weights_and_transformers(self, tmp_path):
        # 权重目录不存在 → 不可用
        assert VLMJudge.is_available(str(tmp_path / "no_model")) is False
        assert VLMJudge.is_available("") is False


# ============================================================================
#  统一入口与降级链
# ============================================================================

class TestVisualSemanticJudge:
    def test_rule_backend_without_model(self, videos):
        judge = VisualSemanticJudge(backend="auto", model_path="")
        report = judge.judge(str(videos["normal"]))
        assert report.backend == "rule"  # 无权重自动降级规则后端
        assert report.passed is True

    def test_auto_backend_black_veto(self, videos):
        judge = VisualSemanticJudge(backend="auto", model_path="")
        report = judge.judge(str(videos["black"]))
        assert report.hard_veto is True
        assert report.passed is False
        assert report.score <= 40.0

    def test_invalid_backend_falls_back_to_auto(self, videos):
        judge = VisualSemanticJudge(backend="nonsense", model_path="")
        assert judge.backend_pref == "auto"

    def test_vlm_requested_but_unavailable_degrades(self, videos, tmp_path):
        judge = VisualSemanticJudge(
            backend="vlm", model_path=str(tmp_path / "no_model")
        )
        report = judge.judge(str(videos["normal"]))
        # 显式要求 vlm 但不可用: 仍返回规则结果并记录错误 (不阻塞管线)
        assert report.backend == "rule"
        assert "vlm" in report.error

    def test_vlm_merge_logic_with_mock(self, videos, monkeypatch):
        """mock VLM 返回, 验证融合: 语义分为主 + 规则硬否决取并集"""
        monkeypatch.setattr(VLMJudge, "is_available",
                            staticmethod(lambda p: True))
        monkeypatch.setattr(
            VLMJudge, "judge",
            lambda self, path, ctx=None: JudgeReport(
                score=90.0, passed=True, backend="vlm",
                metrics={"dimensions": {"black_frame": 10}},
            ),
        )
        judge = VisualSemanticJudge(backend="vlm", model_path="dummy")
        # 正常视频: VLM 分为主 (硬否决需规则佐证, 正常视频规则黑帧占比=0 → 不否决)
        report = judge.judge(str(videos["normal"]))
        assert report.backend == "vlm"
        assert report.score == 90.0
        assert report.passed is True
        # 黑帧视频: 规则硬否决直接生效 (不依赖VLM)
        report_black = judge.judge(str(videos["black"]))
        assert report_black.hard_veto is True
        assert report_black.passed is False
        assert report_black.score <= 40.0

    def test_vlm_veto_requires_rule_evidence(self, videos, monkeypatch):
        """VLM 误报黑帧时, 规则证据(黑帧占比低)应阻止错误否决"""
        monkeypatch.setattr(VLMJudge, "is_available",
                            staticmethod(lambda p: True))
        monkeypatch.setattr(
            VLMJudge, "judge",
            lambda self, path, ctx=None: JudgeReport(
                score=20.0, passed=False, backend="vlm", hard_veto=True,
                issues=["VLM误报黑帧"],
                metrics={"dimensions": {"black_frame": 0}},
            ),
        )
        judge = VisualSemanticJudge(backend="vlm", model_path="dummy")
        # 正常视频规则黑帧占比=0 → VLM 单独否决不成立, 只压低语义分不硬否决
        report = judge.judge(str(videos["normal"]))
        assert report.hard_veto is False
        assert report.score == 20.0  # 语义分仍以VLM为准 (低分会走普通重试, 非灾难路径)

    def test_min_score_threshold(self, videos):
        judge = VisualSemanticJudge(backend="rule", model_path="", min_score=99.0)
        report = judge.judge(str(videos["normal"]))
        # 正常视频规则分通常 <99 (可能有轻微扣分), 阈值拉满 → passed=False
        assert report.passed is (report.score >= 99.0)


# ============================================================================
#  PipelineConfig 配置钳制
# ============================================================================

class TestPipelineConfigClamp:
    def test_semantic_weight_clamped(self):
        from pipeline.unified_pipeline import PipelineConfig
        cfg = PipelineConfig(semantic_score_weight=5.0)
        assert cfg.semantic_score_weight == 1.0
        cfg2 = PipelineConfig(semantic_score_weight=-2.0)
        assert cfg2.semantic_score_weight == 0.0
        cfg3 = PipelineConfig(semantic_score_weight="bad")
        assert cfg3.semantic_score_weight == 0.6
        cfg4 = PipelineConfig(semantic_score_weight=True)  # bool 视为非法
        assert cfg4.semantic_score_weight == 0.6

    def test_visual_judge_min_score_clamped(self):
        from pipeline.unified_pipeline import PipelineConfig
        assert PipelineConfig(visual_judge_min_score=150).visual_judge_min_score == 100.0
        assert PipelineConfig(visual_judge_min_score=-1).visual_judge_min_score == 0.0
        assert PipelineConfig(visual_judge_min_score="x").visual_judge_min_score == 60.0

    def test_backend_whitelist(self):
        from pipeline.unified_pipeline import PipelineConfig
        assert PipelineConfig(visual_judge_backend="rule").visual_judge_backend == "rule"
        assert PipelineConfig(visual_judge_backend="VLm").visual_judge_backend == "VLm"
        assert PipelineConfig(visual_judge_backend="hacker").visual_judge_backend == "auto"

    def test_defaults(self):
        from pipeline.unified_pipeline import PipelineConfig
        cfg = PipelineConfig()
        assert cfg.enable_visual_judge is True
        assert cfg.visual_judge_backend == "auto"
        assert cfg.visual_judge_min_score == 60.0
        assert cfg.semantic_score_weight == 0.6
        assert "Qwen3-VL" in cfg.visual_judge_model_path
