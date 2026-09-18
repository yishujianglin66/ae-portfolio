"""Tests for AI Planner LLM integration (mocked gateway path).

These tests exercise the LLM code paths by mocking
``core.llm_gateway.llm_gateway.chat_with_routing`` so no real API keys or
network calls are needed.  The old ``providers/`` package has been removed
(迁移到 core/llm_gateway.py 统一网关), so we mock the gateway directly.
"""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from src.models.pipeline import (
    PipelinePhase,
    PuppetStyle,
    VideoMetadata,
)

# ============================================================
# Helpers — 构造 mock gateway 响应
# ============================================================

def _make_gateway_mock(response_map: dict[str, str] | None = None):
    """构造一个 mock gateway，根据 user message 返回 canned JSON 响应。

    返回的对象有一个 ``chat_with_routing`` AsyncMock 方法，签名与
    ``core.llm_gateway.LLMGateway.chat_with_routing`` 一致。
    """
    response_map = response_map or {}

    async def _chat_with_routing(message, task_type=None, system_prompt="",
                                 temperature=None, max_tokens=None):
        # 用 message 内容作为 lookup key；找不到则用 __default__
        content = response_map.get(message, response_map.get("__default__", "{}"))
        # 构造与 core.llm_gateway.LLMResponse 兼容的对象
        class _Resp:
            def __init__(self, content_str: str):
                self.content = content_str
                self.success = True
                self.error = ""
                self.model = "mock-model"
                self.provider = "mock"
                self.tokens_input = 0
                self.tokens_output = 0
                self.latency_ms = 0.0
                self.raw = {}

        return _Resp(content)

    mock = AsyncMock()
    mock.chat_with_routing = _chat_with_routing
    return mock


# ============================================================
# IntentParser — LLM path (via gateway)
# ============================================================

class TestIntentParserLLM:
    """IntentParser when LLM gateway is mocked."""

    @pytest.mark.asyncio
    async def test_parse_with_llm_wooden(self):
        from src.ai_planner.planner import IntentParser

        gateway = _make_gateway_mock(response_map={
            "__default__": json.dumps({
                "style": "wooden",
                "target_resolution": [1920, 1080],
                "target_fps": 30,
                "enable_face_puppet": True,
                "enable_body_puppet": True,
                "enable_3d_stage": False,
                "enable_audio": True,
                "quality_preset": "medium",
                "phases": ["phase1_preprocess", "phase2_keying", "phase3_stylize", "phase4_render"],
                "style_reasoning": "LLM chose wooden",
            })
        })
        parser = IntentParser()
        parser.llm = gateway

        result = await parser.parse("木质木偶风格", "/tmp/v.mp4")
        assert result["style"] == "wooden"
        assert result["quality_preset"] == "medium"
        assert result["style_reasoning"] == "LLM chose wooden"

    @pytest.mark.asyncio
    async def test_parse_with_llm_invalid_json_falls_back(self):
        from src.ai_planner.planner import IntentParser

        gateway = _make_gateway_mock(response_map={
            "__default__": "not valid json at all"
        })
        parser = IntentParser()
        parser.llm = gateway

        result = await parser.parse("随便什么", "/tmp/v.mp4")
        # Should still return a dict with defaults populated by sanitize
        assert "style" in result
        assert "phases" in result

    @pytest.mark.asyncio
    async def test_parse_with_llm_malformed_fields_sanitized(self):
        from src.ai_planner.planner import IntentParser

        gateway = _make_gateway_mock(response_map={
            "__default__": json.dumps({
                "style": "bogus_style",
                "target_resolution": "not_a_list",
                "target_fps": "thirty",
                "enable_face_puppet": "yes",
                "quality_preset": "invalid",
            })
        })
        parser = IntentParser()
        parser.llm = gateway

        result = await parser.parse("测试", "/tmp/v.mp4")
        # Bogus style → fallback to wooden
        assert result["style"] == "wooden"
        # Invalid resolution → default
        assert isinstance(result["target_resolution"], list)
        assert len(result["target_resolution"]) == 2
        # Invalid fps → default
        assert isinstance(result["target_fps"], (int, float))
        # Non-bool → default True
        assert result["enable_face_puppet"] is True
        # Invalid quality → default medium
        assert result["quality_preset"] == "medium"

    @pytest.mark.asyncio
    async def test_parse_with_llm_failure_falls_back_to_rules(self):
        """LLM 网关返回 success=False 时应回退规则匹配。"""
        from src.ai_planner.planner import IntentParser

        class _FailedResp:
            success = False
            error = "gateway down"
            content = ""

        async def _failing_chat(*args, **kwargs):
            return _FailedResp()

        gateway = AsyncMock()
        gateway.chat_with_routing = _failing_chat

        parser = IntentParser()
        parser.llm = gateway

        result = await parser.parse("木质木偶风格", "/tmp/v.mp4")
        # 规则匹配回退应识别出 wooden 风格
        assert result["style"] == "wooden"


# ============================================================
# StyleRecommender — LLM path (via gateway)
# ============================================================

class TestStyleRecommenderLLM:
    @pytest.mark.asyncio
    async def test_recommend_with_llm(self):
        from src.ai_planner.planner import StyleRecommender

        gateway = _make_gateway_mock(response_map={
            "__default__": json.dumps({
                "primary_style": "shadow",
                "alternatives": ["wooden", "clay"],
                "confidence": 0.92,
                "reasoning": "皮影风格适合传统内容",
                "style_tips": {"lighting": "背光打亮"},
            })
        })
        rec = StyleRecommender()
        rec.llm = gateway

        result = await rec.recommend(
            video_metadata=None,
            scene_count=3,
            face_count=2,
            content_type="tradition",
            motion_level="low",
            user_preferences="皮影",
        )
        assert result.primary_style == PuppetStyle.SHADOW
        assert len(result.alternatives) == 2
        assert result.confidence == 0.92
        assert "皮影" in result.reasoning

    @pytest.mark.asyncio
    async def test_recommend_with_llm_invalid_style_fallback(self):
        from src.ai_planner.planner import StyleRecommender

        gateway = _make_gateway_mock(response_map={
            "__default__": json.dumps({
                "primary_style": "not_a_real_style",
                "alternatives": ["also_invalid"],
            })
        })
        rec = StyleRecommender()
        rec.llm = gateway

        result = await rec.recommend()
        assert result.primary_style == PuppetStyle.WOODEN
        assert result.alternatives == []


# ============================================================
# ParamOptimizer — LLM path (via gateway)
# ============================================================

class TestParamOptimizerLLM:
    @pytest.mark.asyncio
    async def test_optimize_with_llm(self):
        from src.ai_planner.planner import ParamOptimizer

        gateway = _make_gateway_mock(response_map={
            "__default__": json.dumps({
                "recommended_resolution": [3840, 2160],
                "recommended_fps": 60,
                "recommended_quality": "ultra",
                "enable_topaz": True,
                "enable_silhouette_roto": True,
                "enable_3d_stage": True,
                "enable_color_grade": True,
                "estimated_processing_time_minutes": 45,
                "optimization_notes": "LLM optimized for 4K",
            })
        })
        opt = ParamOptimizer()
        opt.llm = gateway

        result = await opt.optimize(
            video_metadata=VideoMetadata(
                width=1920, height=1080, fps=30, duration=120,
                bitrate=5000000, codec="h264", has_audio=True,
                file_size=1000000, path="/tmp/v.mp4",
            ),
            style=PuppetStyle.WOODEN,
            quality_preset="high",
        )
        assert result.recommended_resolution == (3840, 2160)
        assert result.recommended_fps == 60
        assert result.recommended_quality == "ultra"
        assert result.enable_topaz is True
        assert result.estimated_processing_time_minutes == 45

    @pytest.mark.asyncio
    async def test_optimize_with_llm_malformed_resolution(self):
        from src.ai_planner.planner import ParamOptimizer

        gateway = _make_gateway_mock(response_map={
            "__default__": json.dumps({
                "recommended_resolution": "bad",
                "recommended_fps": "not_a_number",
            })
        })
        opt = ParamOptimizer()
        opt.llm = gateway

        meta = VideoMetadata(
            width=1920, height=1080, fps=30, duration=60,
            bitrate=5000000, codec="h264", has_audio=True,
            file_size=1000000, path="/tmp/v.mp4",
        )
        result = await opt.optimize(video_metadata=meta, style=PuppetStyle.WOODEN)
        # Falls back to metadata dimensions
        assert result.recommended_resolution == (1920, 1080)
        assert result.recommended_fps == 30


# ============================================================
# AIPlanner — full LLM path (via gateway)
# ============================================================

class TestAIPlannerFullLLM:
    @pytest.mark.asyncio
    async def test_plan_from_query_with_llm(self):
        from src.ai_planner.planner import AIPlanner

        gateway = _make_gateway_mock(response_map={
            "__default__": json.dumps({
                "style": "clay",
                "target_resolution": [1920, 1080],
                "target_fps": 30,
                "enable_face_puppet": True,
                "enable_body_puppet": True,
                "enable_3d_stage": False,
                "enable_audio": True,
                "quality_preset": "high",
                "phases": ["phase1_preprocess", "phase2_keying", "phase3_stylize", "phase4_render"],
                "style_reasoning": "LLM chose clay",
                "estimated_duration_minutes": 10,
            })
        })
        planner = AIPlanner()
        planner.intent_parser.llm = gateway
        planner.style_recommender.llm = gateway
        planner.param_optimizer.llm = gateway

        result = await planner.plan_from_query(
            user_query="黏土风格",
            video_path="/tmp/v.mp4",
        )
        assert result.job.style == PuppetStyle.CLAY
        assert result.job.quality_preset == "high"


# ============================================================
# _extract_json edge cases (still works after migration)
# ============================================================

class TestExtractJson:
    def test_direct_json(self):
        from src.ai_planner.planner import _extract_json
        assert _extract_json('{"a": 1}') == {"a": 1}

    def test_json_in_markdown_block(self):
        from src.ai_planner.planner import _extract_json
        text = '```json\n{"a": 1}\n```'
        assert _extract_json(text) == {"a": 1}

    def test_json_in_plain_markdown_block(self):
        from src.ai_planner.planner import _extract_json
        text = '```\n{"a": 1}\n```'
        assert _extract_json(text) == {"a": 1}

    def test_json_embedded_in_text(self):
        from src.ai_planner.planner import _extract_json
        text = 'Here is the result: {"a": 1} and some more text'
        assert _extract_json(text) == {"a": 1}

    def test_invalid_json_returns_empty_dict(self):
        from src.ai_planner.planner import _extract_json
        assert _extract_json("not json at all") == {}

    def test_empty_string_returns_empty_dict(self):
        from src.ai_planner.planner import _extract_json
        assert _extract_json("") == {}


# ============================================================
# _get_llm — 网关获取逻辑
# ============================================================

class TestGetLLM:
    """验证 _get_llm() 在不同环境下的行为。"""

    def test_get_llm_returns_none_when_gateway_unconfigured(self, monkeypatch):
        """无 API Key 配置时返回 None 以触发规则匹配回退。"""
        from src.ai_planner.planner import _get_llm
        # 清空环境变量确保网关不可用
        for key in ("AEKV_LLM_API_KEY", "OPENAI_API_KEY", "AEKV_LLM_BASE_URL"):
            monkeypatch.delenv(key, raising=False)

        # 重新配置网关为空
        from core.llm_gateway import LLMConfig, llm_gateway
        llm_gateway.configure(LLMConfig(base_url="", api_key=""))

        result = _get_llm()
        assert result is None

    def test_get_llm_returns_gateway_when_configured(self, monkeypatch):
        """有 API Key + base_url 时返回网关实例。"""
        from src.ai_planner.planner import _get_llm

        from core.llm_gateway import LLMConfig, llm_gateway

        # 重新配置网关为可用状态
        llm_gateway.configure(LLMConfig(
            base_url="http://localhost:5273/v1",
            api_key="sk-test-key-for-unit-test-only",
        ))

        try:
            result = _get_llm()
            assert result is not None
        finally:
            # 清理配置避免影响其他测试
            llm_gateway.configure(LLMConfig(base_url="", api_key=""))
