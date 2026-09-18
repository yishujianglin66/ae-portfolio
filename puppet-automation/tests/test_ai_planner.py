"""Unit tests for AI Planner module."""
from __future__ import annotations

import pytest
from src.ai_planner import (
    AIPlanner,
    IntentParser,
    ParamOptimizer,
    PlanningResult,
    StyleRecommendation,
    StyleRecommender,
)
from src.ai_planner.planner import OptimizedParams, _extract_json
from src.models.pipeline import PipelinePhase, PuppetStyle, VideoMetadata

# ============================================================
# Helper: JSON extraction
# ============================================================

class TestJsonExtraction:
    def test_extract_direct_json(self):
        text = '{"key": "value", "num": 42}'
        result = _extract_json(text)
        assert result["key"] == "value"
        assert result["num"] == 42

    def test_extract_from_markdown_code_block(self):
        text = """```json
{
    "style": "wooden",
    "quality": "high"
}
```
Some other text"""
        result = _extract_json(text)
        assert result["style"] == "wooden"
        assert result["quality"] == "high"

    def test_extract_from_code_block_no_lang(self):
        text = """```
{"key": "value"}
```"""
        result = _extract_json(text)
        assert result["key"] == "value"

    def test_extract_from_text_with_braces(self):
        text = "Here is some text {\"data\": 123} and more"
        result = _extract_json(text)
        assert result["data"] == 123

    def test_extract_invalid_json_returns_empty(self):
        text = "not json at all"
        result = _extract_json(text)
        assert result == {}


# ============================================================
# Intent Parser Tests
# ============================================================

class TestIntentParser:
    @pytest.fixture
    def parser(self):
        return IntentParser()

    def test_parser_init(self, parser):
        assert parser is not None
        assert hasattr(parser, '_style_keywords')
        assert isinstance(parser._style_keywords, dict)
        assert len(parser._style_keywords) == len(PuppetStyle)

    @pytest.mark.asyncio
    async def test_parse_rule_based_wooden(self, parser):
        """Test rule-based parsing detects wooden style keywords."""
        parser.llm = None  # Force rule-based
        result = await parser.parse("把这个视频做成木质木偶风格", "test.mp4")
        assert result["style"] == "wooden"
        assert isinstance(result["target_resolution"], list)
        assert len(result["target_resolution"]) == 2

    @pytest.mark.asyncio
    async def test_parse_rule_based_shadow(self, parser):
        """Test rule-based parsing detects shadow style keywords."""
        parser.llm = None
        result = await parser.parse("我想要皮影效果的视频", "test.mp4")
        assert result["style"] == "shadow"

    @pytest.mark.asyncio
    async def test_parse_rule_based_voxel(self, parser):
        """Test rule-based parsing detects voxel style keywords."""
        parser.llm = None
        result = await parser.parse("做成minecraft体素方块风格", "test.mp4")
        assert result["style"] == "voxel"

    @pytest.mark.asyncio
    async def test_parse_rule_based_clay(self, parser):
        """Test rule-based parsing detects clay style keywords."""
        parser.llm = None
        result = await parser.parse("黏土动画风格", "test.mp4")
        assert result["style"] == "clay"

    @pytest.mark.asyncio
    async def test_parse_rule_based_quality_high(self, parser):
        """Test high quality detection."""
        parser.llm = None
        result = await parser.parse("高清4K木质木偶效果", "test.mp4")
        assert result["quality_preset"] == "high"

    @pytest.mark.asyncio
    async def test_parse_rule_based_quality_low(self, parser):
        """Test low quality / preview detection."""
        parser.llm = None
        result = await parser.parse("快速预览一下木质木偶效果", "test.mp4")
        assert result["quality_preset"] == "low"

    @pytest.mark.asyncio
    async def test_parse_rule_based_3d_stage(self, parser):
        """Test 3D stage detection."""
        parser.llm = None
        result = await parser.parse("用3D舞台展示木质木偶", "test.mp4")
        assert result["enable_3d_stage"] is True

    @pytest.mark.asyncio
    async def test_parse_rule_based_default_style(self, parser):
        """Test default style when no keywords match."""
        parser.llm = None
        result = await parser.parse("处理这个视频", "test.mp4")
        assert result["style"] == "wooden"  # Default

    @pytest.mark.asyncio
    async def test_parse_has_all_required_fields(self, parser):
        """Test that all required fields are present in result."""
        parser.llm = None
        result = await parser.parse("木质木偶风格", "test.mp4")
        required_fields = [
            "style", "target_resolution", "target_fps",
            "enable_face_puppet", "enable_body_puppet",
            "enable_3d_stage", "enable_audio",
            "quality_preset", "phases",
            "style_reasoning", "estimated_duration_minutes",
        ]
        for field in required_fields:
            assert field in result, f"Missing field: {field}"

    @pytest.mark.asyncio
    async def test_parse_phases_is_list(self, parser):
        """Test that phases is a list with valid phase values."""
        parser.llm = None
        result = await parser.parse("木质木偶风格", "test.mp4")
        assert isinstance(result["phases"], list)
        assert len(result["phases"]) > 0
        # All phases should be valid enum values
        valid_phases = [p.value for p in PipelinePhase]
        for phase in result["phases"]:
            assert phase in valid_phases


# ============================================================
# Style Recommender Tests
# ============================================================

class TestStyleRecommender:
    @pytest.fixture
    def recommender(self):
        return StyleRecommender()

    def test_recommender_init(self, recommender):
        assert recommender is not None

    @pytest.mark.asyncio
    async def test_recommend_rule_based_children_content(self, recommender):
        """Test rule-based recommendation for children content."""
        recommender.llm = None
        rec = await recommender.recommend(
            content_type="儿童故事",
            user_preferences="童话风格",
        )
        assert isinstance(rec, StyleRecommendation)
        assert rec.primary_style in PuppetStyle
        assert isinstance(rec.alternatives, list)
        assert len(rec.alternatives) == 2
        assert 0.0 < rec.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_recommend_rule_based_traditional_content(self, recommender):
        """Test rule-based recommendation for traditional content."""
        recommender.llm = None
        rec = await recommender.recommend(
            content_type="传统神话",
            user_preferences="皮影",
        )
        assert rec.primary_style == PuppetStyle.SHADOW

    @pytest.mark.asyncio
    async def test_recommend_rule_based_gaming_content(self, recommender):
        """Test rule-based recommendation for gaming content."""
        recommender.llm = None
        rec = await recommender.recommend(
            content_type="游戏解说",
            user_preferences="像素风",
        )
        assert rec.primary_style == PuppetStyle.VOXEL

    @pytest.mark.asyncio
    async def test_recommend_rule_based_travel_content(self, recommender):
        """Test rule-based recommendation for travel content."""
        recommender.llm = None
        rec = await recommender.recommend(
            content_type="旅行vlog",
            user_preferences="",
        )
        assert isinstance(rec, StyleRecommendation)

    @pytest.mark.asyncio
    async def test_recommend_with_video_metadata(self, recommender):
        """Test recommendation with video metadata."""
        recommender.llm = None
        metadata = VideoMetadata(
            duration=120.0,
            width=1920,
            height=1080,
            fps=30.0,
            bitrate=5000000,
            codec="h264",
            has_audio=True,
            file_size=100000000,
            path="test.mp4",
        )
        rec = await recommender.recommend(
            video_metadata=metadata,
            scene_count=5,
            face_count=1,
            content_type="一般内容",
            motion_level="medium",
        )
        assert isinstance(rec, StyleRecommendation)
        assert rec.reasoning != ""
        assert isinstance(rec.style_tips, dict)

    @pytest.mark.asyncio
    async def test_recommend_with_face_count(self, recommender):
        """Test that face_count affects recommendation."""
        recommender.llm = None
        rec = await recommender.recommend(
            face_count=3,
            content_type="采访",
        )
        assert isinstance(rec, StyleRecommendation)
        # With faces, handle and wooden should score higher
        # But we can't guarantee exact order without more context
        assert rec.primary_style in PuppetStyle


# ============================================================
# Parameter Optimizer Tests
# ============================================================

class TestParamOptimizer:
    @pytest.fixture
    def optimizer(self):
        return ParamOptimizer()

    def test_optimizer_init(self, optimizer):
        assert optimizer is not None

    @pytest.mark.asyncio
    async def test_optimize_rule_based_low_quality(self, optimizer):
        """Test rule-based optimization for low quality."""
        optimizer.llm = None
        result = await optimizer.optimize(
            video_metadata=None,
            style=PuppetStyle.WOODEN,
            quality_preset="low",
        )
        assert isinstance(result, OptimizedParams)
        assert result.recommended_resolution == (1280, 720)
        assert result.recommended_fps == 24
        assert result.enable_topaz is False

    @pytest.mark.asyncio
    async def test_optimize_rule_based_medium_quality(self, optimizer):
        """Test rule-based optimization for medium quality."""
        optimizer.llm = None
        result = await optimizer.optimize(
            video_metadata=None,
            style=PuppetStyle.WOODEN,
            quality_preset="medium",
        )
        assert result.recommended_resolution == (1920, 1080)
        assert result.recommended_fps == 30
        assert result.enable_topaz is False

    @pytest.mark.asyncio
    async def test_optimize_rule_based_high_quality(self, optimizer):
        """Test rule-based optimization for high quality."""
        optimizer.llm = None
        result = await optimizer.optimize(
            video_metadata=None,
            style=PuppetStyle.WOODEN,
            quality_preset="high",
        )
        assert result.recommended_resolution == (1920, 1080)
        assert result.enable_topaz is True

    @pytest.mark.asyncio
    async def test_optimize_rule_based_ultra_quality(self, optimizer):
        """Test rule-based optimization for ultra quality."""
        optimizer.llm = None
        result = await optimizer.optimize(
            video_metadata=None,
            style=PuppetStyle.WOODEN,
            quality_preset="ultra",
        )
        assert result.recommended_resolution == (3840, 2160)
        assert result.enable_topaz is True

    @pytest.mark.asyncio
    async def test_optimize_with_video_metadata(self, optimizer):
        """Test optimization with video metadata."""
        optimizer.llm = None
        metadata = VideoMetadata(
            duration=60.0,
            width=1920,
            height=1080,
            fps=30.0,
            bitrate=5000000,
            codec="h264",
            has_audio=True,
            file_size=50000000,
            path="test.mp4",
        )
        result = await optimizer.optimize(
            video_metadata=metadata,
            style=PuppetStyle.WOODEN,
            quality_preset="medium",
            face_count=1,
            has_people=True,
        )
        assert isinstance(result, OptimizedParams)
        assert result.estimated_processing_time_minutes > 0
        assert result.optimization_notes != ""

    @pytest.mark.asyncio
    async def test_optimize_silhouette_with_faces(self, optimizer):
        """Test silhouette roto enabled when there are faces."""
        optimizer.llm = None
        metadata = VideoMetadata(
            duration=30.0,
            width=1920,
            height=1080,
            fps=30.0,
            bitrate=5000000,
            codec="h264",
            has_audio=True,
            file_size=30000000,
            path="test.mp4",
        )
        result = await optimizer.optimize(
            video_metadata=metadata,
            style=PuppetStyle.WOODEN,
            quality_preset="high",
            face_count=2,
            has_people=True,
        )
        assert result.enable_silhouette_roto is True

    @pytest.mark.asyncio
    async def test_optimize_no_people_no_silhouette(self, optimizer):
        """Test silhouette roto disabled when no people."""
        optimizer.llm = None
        result = await optimizer.optimize(
            video_metadata=None,
            style=PuppetStyle.WOODEN,
            quality_preset="medium",
            face_count=0,
            has_people=False,
        )
        assert result.enable_silhouette_roto is False

    @pytest.mark.asyncio
    async def test_optimize_color_grade_enabled(self, optimizer):
        """Test that color grade is enabled by default."""
        optimizer.llm = None
        result = await optimizer.optimize(
            video_metadata=None,
            style=PuppetStyle.WOODEN,
            quality_preset="medium",
        )
        assert result.enable_color_grade is True


# ============================================================
# AI Planner (Main Class) Tests
# ============================================================

class TestAIPlanner:
    @pytest.fixture
    def planner(self):
        return AIPlanner()

    def test_planner_init(self, planner):
        assert planner is not None
        assert isinstance(planner.intent_parser, IntentParser)
        assert isinstance(planner.style_recommender, StyleRecommender)
        assert isinstance(planner.param_optimizer, ParamOptimizer)

    @pytest.mark.asyncio
    async def test_plan_from_query_basic(self, planner):
        """Test basic plan generation (rule-based, no LLM)."""
        # Force rule-based by setting llm to None on all components
        planner.intent_parser.llm = None
        planner.style_recommender.llm = None
        planner.param_optimizer.llm = None

        result = await planner.plan_from_query(
            user_query="把这个视频做成木质木偶风格，高清输出",
            video_path="test.mp4",
        )
        assert isinstance(result, PlanningResult)
        assert result.job is not None
        assert result.job.style == PuppetStyle.WOODEN
        assert result.job.quality_preset == "high"
        assert isinstance(result.job.phases, list)
        assert len(result.job.phases) == 4

    @pytest.mark.asyncio
    async def test_plan_from_query_shadow_style(self, planner):
        """Test plan with shadow style."""
        planner.intent_parser.llm = None
        planner.style_recommender.llm = None
        planner.param_optimizer.llm = None

        result = await planner.plan_from_query(
            user_query="皮影风格效果",
            video_path="test.mp4",
        )
        assert result.job.style == PuppetStyle.SHADOW

    @pytest.mark.asyncio
    async def test_plan_from_query_clay_style(self, planner):
        """Test plan with clay style."""
        planner.intent_parser.llm = None
        planner.style_recommender.llm = None
        planner.param_optimizer.llm = None

        result = await planner.plan_from_query(
            user_query="黏土动画风格",
            video_path="test.mp4",
        )
        assert result.job.style == PuppetStyle.CLAY

    @pytest.mark.asyncio
    async def test_plan_from_query_job_id_generated(self, planner):
        """Test that job_id is generated automatically."""
        planner.intent_parser.llm = None
        planner.style_recommender.llm = None
        planner.param_optimizer.llm = None

        result = await planner.plan_from_query(
            user_query="木质木偶",
            video_path="test.mp4",
        )
        assert result.job.job_id.startswith("job_")
        assert len(result.job.job_id) > 5  # job_ + 8 hex chars

    @pytest.mark.asyncio
    async def test_plan_from_query_explanation(self, planner):
        """Test that explanation is generated."""
        planner.intent_parser.llm = None
        planner.style_recommender.llm = None
        planner.param_optimizer.llm = None

        result = await planner.plan_from_query(
            user_query="木质木偶风格",
            video_path="test.mp4",
        )
        assert result.explanation != ""
        assert "木质木偶" in result.explanation or "wooden" in result.explanation.lower()

    @pytest.mark.asyncio
    async def test_plan_from_query_optimized_params(self, planner):
        """Test that optimized params are present."""
        planner.intent_parser.llm = None
        planner.style_recommender.llm = None
        planner.param_optimizer.llm = None

        result = await planner.plan_from_query(
            user_query="木质木偶风格",
            video_path="test.mp4",
        )
        assert result.optimized_params is not None
        assert isinstance(result.optimized_params, OptimizedParams)
        assert result.optimized_params.estimated_processing_time_minutes > 0

    @pytest.mark.asyncio
    async def test_recommend_style_method(self, planner):
        """Test the recommend_style convenience method."""
        planner.style_recommender.llm = None

        rec = await planner.recommend_style(
            video_path="test.mp4",
            user_preferences="童话风格",
        )
        assert isinstance(rec, StyleRecommendation)
        assert rec.primary_style in PuppetStyle

    @pytest.mark.asyncio
    async def test_plan_from_query_with_metadata(self, planner):
        """Test plan generation with video metadata."""
        planner.intent_parser.llm = None
        planner.style_recommender.llm = None
        planner.param_optimizer.llm = None

        metadata = VideoMetadata(
            duration=60.0,
            width=1920,
            height=1080,
            fps=30.0,
            bitrate=5000000,
            codec="h264",
            has_audio=True,
            file_size=50000000,
            path="test.mp4",
        )
        result = await planner.plan_from_query(
            user_query="木质木偶风格",
            video_path="test.mp4",
            video_metadata=metadata,
        )
        assert result.style_recommendation is not None
        assert isinstance(result.style_recommendation, StyleRecommendation)

    @pytest.mark.asyncio
    async def test_plan_from_query_target_resolution(self, planner):
        """Test that target resolution is set correctly."""
        planner.intent_parser.llm = None
        planner.style_recommender.llm = None
        planner.param_optimizer.llm = None

        result = await planner.plan_from_query(
            user_query="木质木偶 高清",
            video_path="test.mp4",
        )
        assert isinstance(result.job.target_resolution, tuple)
        assert len(result.job.target_resolution) == 2
        assert all(isinstance(x, int) for x in result.job.target_resolution)

    @pytest.mark.asyncio
    async def test_plan_from_query_enable_audio(self, planner):
        """Test that enable_audio is True by default."""
        planner.intent_parser.llm = None
        planner.style_recommender.llm = None
        planner.param_optimizer.llm = None

        result = await planner.plan_from_query(
            user_query="木质木偶",
            video_path="test.mp4",
        )
        assert result.job.enable_audio is True


class TestIntentParserEdgeCases:
    """Test intent parser edge cases."""

    @pytest.fixture
    def parser(self):
        return IntentParser()

    @pytest.mark.asyncio
    async def test_parse_empty_query(self, parser):
        """Test parsing empty query returns defaults."""
        parser.llm = None
        result = await parser.parse("", "test.mp4")
        assert result["style"] == "wooden"  # Default
        assert isinstance(result["phases"], list)
        assert len(result["phases"]) > 0

    @pytest.mark.asyncio
    async def test_parse_very_long_query(self, parser):
        """Test parsing very long query."""
        parser.llm = None
        long_query = "木质木偶" * 1000
        result = await parser.parse(long_query, "test.mp4")
        assert result["style"] == "wooden"

    @pytest.mark.asyncio
    async def test_parse_special_characters(self, parser):
        """Test parsing query with special characters."""
        parser.llm = None
        result = await parser.parse("木质@#$%木偶^&*风格!", "test.mp4")
        assert result["style"] == "wooden"

    @pytest.mark.asyncio
    async def test_parse_mixed_language(self, parser):
        """Test parsing mixed Chinese/English query."""
        parser.llm = None
        result = await parser.parse("我想要wooden puppet风格的视频", "test.mp4")
        assert result["style"] == "wooden"

    @pytest.mark.asyncio
    async def test_parse_all_styles(self, parser):
        """Test that all 8 styles can be detected."""
        parser.llm = None
        style_queries = {
            "wooden": "木质木偶风格",
            "stop_motion": "定格动画效果",
            "miniature": "微缩模型移轴效果",
            "clay": "黏土橡皮泥风格",
            "shadow": "皮影戏剪影效果",
            "paper": "纸艺剪纸风格",
            "voxel": "体素方块像素minecraft风格",
            "handle": "提线木偶操纵杆效果",
        }
        for expected_style, query in style_queries.items():
            result = await parser.parse(query, "test.mp4")
            assert result["style"] == expected_style, f"Failed for {expected_style}: got {result['style']}"

    @pytest.mark.asyncio
    async def test_parse_stop_motion_keyword(self, parser):
        """Test stop motion keyword detection."""
        parser.llm = None
        result = await parser.parse("stop motion定格效果", "test.mp4")
        assert result["style"] == "stop_motion"

    @pytest.mark.asyncio
    async def test_parse_paper_keyword(self, parser):
        """Test paper style keyword detection."""
        parser.llm = None
        result = await parser.parse("清新paper cut纸艺风格", "test.mp4")
        assert result["style"] == "paper"


class TestStyleRecommenderEdgeCases:
    """Test style recommender edge cases."""

    @pytest.fixture
    def recommender(self):
        return StyleRecommender()

    @pytest.mark.asyncio
    async def test_recommend_empty_preferences(self, recommender):
        """Test recommendation with empty preferences."""
        recommender.llm = None
        rec = await recommender.recommend(user_preferences="")
        assert isinstance(rec, StyleRecommendation)
        assert rec.primary_style in PuppetStyle

    @pytest.mark.asyncio
    async def test_recommend_zero_scenes(self, recommender):
        """Test recommendation with zero scenes."""
        recommender.llm = None
        rec = await recommender.recommend(scene_count=0, face_count=0)
        assert isinstance(rec, StyleRecommendation)
        assert rec.confidence > 0

    @pytest.mark.asyncio
    async def test_recommend_high_motion(self, recommender):
        """Test recommendation with high motion level."""
        recommender.llm = None
        rec = await recommender.recommend(motion_level="high")
        assert isinstance(rec, StyleRecommendation)

    @pytest.mark.asyncio
    async def test_recommend_many_faces(self, recommender):
        """Test recommendation with many faces."""
        recommender.llm = None
        rec = await recommender.recommend(face_count=10)
        assert isinstance(rec, StyleRecommendation)

    @pytest.mark.asyncio
    async def test_recommend_confidence_range(self, recommender):
        """Test that confidence is within valid range."""
        recommender.llm = None
        rec = await recommender.recommend()
        assert 0.0 < rec.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_recommend_alternatives_are_different(self, recommender):
        """Test that alternatives are different from primary."""
        recommender.llm = None
        rec = await recommender.recommend()
        for alt in rec.alternatives:
            assert alt != rec.primary_style


class TestParamOptimizerEdgeCases:
    """Test parameter optimizer edge cases."""

    @pytest.fixture
    def optimizer(self):
        return ParamOptimizer()

    @pytest.mark.asyncio
    async def test_optimize_very_short_video(self, optimizer):
        """Test optimization for very short video."""
        optimizer.llm = None
        from src.models.pipeline import VideoMetadata
        metadata = VideoMetadata(
            duration=1.0,
            width=1920,
            height=1080,
            fps=30.0,
            bitrate=5000000,
            codec="h264",
            has_audio=True,
            file_size=1000000,
            path="short.mp4",
        )
        result = await optimizer.optimize(
            video_metadata=metadata,
            style=PuppetStyle.WOODEN,
            quality_preset="medium",
        )
        assert isinstance(result, OptimizedParams)
        assert result.estimated_processing_time_minutes >= 0

    @pytest.mark.asyncio
    async def test_optimize_very_long_video(self, optimizer):
        """Test optimization for very long video."""
        optimizer.llm = None
        from src.models.pipeline import VideoMetadata
        metadata = VideoMetadata(
            duration=3600.0,
            width=1920,
            height=1080,
            fps=30.0,
            bitrate=5000000,
            codec="h264",
            has_audio=True,
            file_size=10000000000,
            path="long.mp4",
        )
        result = await optimizer.optimize(
            video_metadata=metadata,
            style=PuppetStyle.WOODEN,
            quality_preset="high",
        )
        assert isinstance(result, OptimizedParams)
        assert result.estimated_processing_time_minutes > 0

    @pytest.mark.asyncio
    async def test_optimize_low_resolution(self, optimizer):
        """Test optimization for low resolution video."""
        optimizer.llm = None
        from src.models.pipeline import VideoMetadata
        metadata = VideoMetadata(
            duration=60.0,
            width=640,
            height=480,
            fps=24.0,
            bitrate=1000000,
            codec="h264",
            has_audio=True,
            file_size=10000000,
            path="low_res.mp4",
        )
        result = await optimizer.optimize(
            video_metadata=metadata,
            style=PuppetStyle.VOXEL,
            quality_preset="medium",
        )
        assert isinstance(result, OptimizedParams)

    @pytest.mark.asyncio
    async def test_optimize_all_styles(self, optimizer):
        """Test optimization works for all puppet styles."""
        optimizer.llm = None
        for style in PuppetStyle:
            result = await optimizer.optimize(
                video_metadata=None,
                style=style,
                quality_preset="medium",
            )
            assert isinstance(result, OptimizedParams)
            assert result.recommended_quality == "medium"

    @pytest.mark.asyncio
    async def test_optimize_3d_stage_default_false(self, optimizer):
        """Test that 3D stage is disabled by default."""
        optimizer.llm = None
        result = await optimizer.optimize(
            video_metadata=None,
            style=PuppetStyle.WOODEN,
            quality_preset="medium",
        )
        assert result.enable_3d_stage is False


class TestAIPlannerEdgeCases:
    """Test AI planner edge cases."""

    @pytest.fixture
    def planner(self):
        return AIPlanner()

    @pytest.mark.asyncio
    async def test_plan_empty_query(self, planner):
        """Test plan with empty query."""
        planner.intent_parser.llm = None
        planner.style_recommender.llm = None
        planner.param_optimizer.llm = None

        result = await planner.plan_from_query("", "test.mp4")
        assert isinstance(result, PlanningResult)
        assert result.job.style == PuppetStyle.WOODEN

    @pytest.mark.asyncio
    async def test_plan_job_id_unique(self, planner):
        """Test that each plan generates unique job_id."""
        planner.intent_parser.llm = None
        planner.style_recommender.llm = None
        planner.param_optimizer.llm = None

        result1 = await planner.plan_from_query("木质木偶", "test1.mp4")
        result2 = await planner.plan_from_query("木质木偶", "test2.mp4")
        assert result1.job.job_id != result2.job.job_id

    @pytest.mark.asyncio
    async def test_plan_job_id_format(self, planner):
        """Test that job_id follows expected format."""
        planner.intent_parser.llm = None
        planner.style_recommender.llm = None
        planner.param_optimizer.llm = None

        result = await planner.plan_from_query("木质木偶", "test.mp4")
        assert result.job.job_id.startswith("job_")
        assert len(result.job.job_id) == 12  # job_ + 8 hex chars

    @pytest.mark.asyncio
    async def test_plan_explanation_not_empty(self, planner):
        """Test that explanation is never empty."""
        planner.intent_parser.llm = None
        planner.style_recommender.llm = None
        planner.param_optimizer.llm = None

        result = await planner.plan_from_query("木质木偶", "test.mp4")
        assert result.explanation != ""
        assert len(result.explanation) > 10

    @pytest.mark.asyncio
    async def test_plan_all_styles(self, planner):
        """Test plan generation for all 8 styles."""
        planner.intent_parser.llm = None
        planner.style_recommender.llm = None
        planner.param_optimizer.llm = None

        style_queries = [
            ("木质木偶", PuppetStyle.WOODEN),
            ("皮影效果", PuppetStyle.SHADOW),
            ("黏土动画", PuppetStyle.CLAY),
            ("体素方块", PuppetStyle.VOXEL),
            ("微缩模型", PuppetStyle.MINIATURE),
            ("定格动画", PuppetStyle.STOP_MOTION),
            ("纸艺剪纸", PuppetStyle.PAPER),
            ("提线木偶", PuppetStyle.HANDLE),
        ]
        for query, expected_style in style_queries:
            result = await planner.plan_from_query(query, "test.mp4")
            assert result.job.style == expected_style, f"Failed for {expected_style.value}"
