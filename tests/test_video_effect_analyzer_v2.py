#!/usr/bin/env python3
"""
test_video_effect_analyzer_v2.py — VRS 视频效果分析器 v2 回归测试

测试重点（覆盖 2026-07-20 VRS Phase 2 修复）：
1. _aggregate_blend_modes() 兼容 string 和 dict 两种格式
   - 历史问题：LLM 偶尔返回 [{"mode": "SCREEN"}, ...] 或 ["SCREEN", ...]，
     旧版代码假设元素为 dict，导致 .get("mode") 在字符串上抛 AttributeError
   - 修复：m.get("mode") if isinstance(m, dict) else m
2. _aggregate_style_tags() 按频次降序
3. _aggregate_effects() 按 confidence 降序合并
4. _VISION_TIMEOUT 配置为 90 秒（用户硬约束 60-90s）
5. 缺失字段时的健壮性（blend_modes_detected/style_tags 缺失或为 None）

回归原因：
- VRS v2.0 在 _aggregate_blend_modes 处崩溃会直接让整个 VISION 分析失败，
  端到端流程降级到纯 CV，丢失 LLM 的语义判断能力。
- 该聚合逻辑是 VISION 多帧结果的必经收敛点，无测试覆盖即等于"裸奔"。
"""
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "vrs"))

# 检查被测模块是否可用
try:
    from vrs.video_effect_analyzer_v2 import VideoEffectAnalyzerV2
    HAS_ANALYZER = True
except ImportError:
    HAS_ANALYZER = False

pytestmark = pytest.mark.skipif(
    not HAS_ANALYZER,
    reason="vrs.video_effect_analyzer_v2 不可用（依赖缺失）",
)


@pytest.fixture
def analyzer():
    """构造一个禁用 VISION LLM 的纯逻辑测试实例"""
    # enable_vision=False 避免触发 LLM 网关初始化
    return VideoEffectAnalyzerV2(enable_vision=False)


# =============================================================================
# 1. _aggregate_blend_modes — string/dict 混合格式兼容（核心修复点）
# =============================================================================

class TestAggregateBlendModesMixedFormats:
    """覆盖 video_effect_analyzer_v2.py 第 1387-1408 行"""

    def test_pure_string_format(self, analyzer):
        """旧格式：blend_modes_detected 为字符串列表 ["SCREEN", "ADD"]"""
        batch_analyses = [
            {"per_frame": [
                {"blend_modes_detected": ["SCREEN", "ADD"]},
                {"blend_modes_detected": ["SCREEN", "MULTIPLY"]},
            ]}
        ]
        frame_analyses = []

        result = analyzer._aggregate_blend_modes(batch_analyses, frame_analyses)

        # 应该去重并保留出现顺序
        assert "SCREEN" in result
        assert "ADD" in result
        assert "MULTIPLY" in result
        # SCREEN 出现两次，但只保留一次
        assert result.count("SCREEN") == 1
        assert len(result) == 3

    def test_pure_dict_format(self, analyzer):
        """新格式：blend_modes_detected 为字典列表 [{"mode": "SCREEN"}]"""
        batch_analyses = [
            {"per_frame": [
                {"blend_modes_detected": [{"mode": "SCREEN"}, {"mode": "ADD"}]},
                {"blend_modes_detected": [{"mode": "OVERLAY"}]},
            ]}
        ]
        frame_analyses = []

        result = analyzer._aggregate_blend_modes(batch_analyses, frame_analyses)

        assert "SCREEN" in result
        assert "ADD" in result
        assert "OVERLAY" in result
        assert len(result) == 3

    def test_mixed_string_and_dict_format(self, analyzer):
        """混合格式：同一批次内既有字符串又有字典（核心回归场景）"""
        batch_analyses = [
            {"per_frame": [
                {"blend_modes_detected": ["SCREEN", {"mode": "ADD"}]},
                {"blend_modes_detected": [{"mode": "MULTIPLY"}, "SCREEN"]},
            ]}
        ]
        frame_analyses = []

        result = analyzer._aggregate_blend_modes(batch_analyses, frame_analyses)

        # 关键断言：不抛 AttributeError，所有模式都被正确提取
        assert "SCREEN" in result
        assert "ADD" in result
        assert "MULTIPLY" in result
        assert result.count("SCREEN") == 1  # 去重

    def test_frame_analyses_also_collected(self, analyzer):
        """frame_analyses（非批次）也应参与聚合"""
        batch_analyses = []
        frame_analyses = [
            {"blend_modes_detected": ["SCREEN"]},
            {"blend_modes_detected": [{"mode": "ADD"}]},
        ]

        result = analyzer._aggregate_blend_modes(batch_analyses, frame_analyses)

        assert "SCREEN" in result
        assert "ADD" in result

    def test_empty_inputs_returns_empty_list(self, analyzer):
        """空输入返回空列表"""
        result = analyzer._aggregate_blend_modes([], [])
        assert result == []

    def test_missing_blend_modes_field(self, analyzer):
        """帧缺少 blend_modes_detected 字段时不崩溃"""
        batch_analyses = [
            {"per_frame": [
                {"effects": []},  # 无 blend_modes_detected
                {"blend_modes_detected": ["SCREEN"]},
            ]}
        ]
        frame_analyses = [
            {},  # 完全空帧
        ]

        result = analyzer._aggregate_blend_modes(batch_analyses, frame_analyses)

        assert result == ["SCREEN"]

    def test_none_blend_modes_value(self, analyzer):
        """blend_modes_detected 显式为 None 时不崩溃"""
        batch_analyses = [
            {"per_frame": [
                {"blend_modes_detected": None},
                {"blend_modes_detected": ["SCREEN"]},
            ]}
        ]
        frame_analyses = []

        result = analyzer._aggregate_blend_modes(batch_analyses, frame_analyses)

        assert result == ["SCREEN"]

    def test_dict_without_mode_key(self, analyzer):
        """字典元素缺 mode 键时跳过该元素"""
        batch_analyses = [
            {"per_frame": [
                {"blend_modes_detected": [
                    {"mode": "SCREEN"},
                    {"not_mode": "weird"},  # 无 mode 键
                    {"mode": "ADD"},
                ]},
            ]}
        ]
        frame_analyses = []

        result = analyzer._aggregate_blend_modes(batch_analyses, frame_analyses)

        assert "SCREEN" in result
        assert "ADD" in result
        assert len(result) == 2  # weird 字典被跳过

    def test_empty_mode_name_skipped(self, analyzer):
        """空字符串 mode 名应被跳过（避免污染结果列表）"""
        batch_analyses = [
            {"per_frame": [
                {"blend_modes_detected": [
                    {"mode": ""},
                    "SCREEN",
                    {"mode": None},
                ]},
            ]}
        ]
        frame_analyses = []

        result = analyzer._aggregate_blend_modes(batch_analyses, frame_analyses)

        # SCREEN 应被保留；空字符串/None 被跳过
        assert "SCREEN" in result
        assert "" not in result
        assert None not in result

    def test_preserves_first_occurrence_order(self, analyzer):
        """去重时保留首次出现的顺序（不重排）"""
        batch_analyses = [
            {"per_frame": [
                {"blend_modes_detected": ["ADD", "SCREEN", "MULTIPLY"]},
                {"blend_modes_detected": ["SCREEN", "OVERLAY"]},
            ]}
        ]
        frame_analyses = []

        result = analyzer._aggregate_blend_modes(batch_analyses, frame_analyses)

        # 期望按首次出现顺序：ADD, SCREEN, MULTIPLY, OVERLAY
        assert result == ["ADD", "SCREEN", "MULTIPLY", "OVERLAY"]


# =============================================================================
# 2. _aggregate_style_tags — 按频次降序
# =============================================================================

class TestAggregateStyleTags:
    """覆盖 video_effect_analyzer_v2.py 第 1410-1428 行"""

    def test_sorted_by_frequency_descending(self, analyzer):
        """风格标签按出现频次降序排列"""
        batch_analyses = [
            {"per_frame": [
                {"style_tags": ["cinematic", "warm"]},
                {"style_tags": ["cinematic"]},
                {"style_tags": ["cinematic", "dark"]},
            ]}
        ]
        frame_analyses = []

        result = analyzer._aggregate_style_tags(batch_analyses, frame_analyses)

        # cinematic 出现 3 次，应排第一
        assert result[0] == "cinematic"
        # warm 和 dark 各 1 次，顺序由 dict 插入序决定（这里只验证都存在）
        assert "warm" in result
        assert "dark" in result

    def test_missing_style_tags_field(self, analyzer):
        """缺字段不崩溃"""
        batch_analyses = [
            {"per_frame": [
                {"effects": []},
                {"style_tags": ["cinematic"]},
            ]}
        ]
        frame_analyses = [{}]

        result = analyzer._aggregate_style_tags(batch_analyses, frame_analyses)

        assert result == ["cinematic"]

    def test_none_style_tags_value(self, analyzer):
        """style_tags 为 None 不崩溃"""
        batch_analyses = [
            {"per_frame": [
                {"style_tags": None},
                {"style_tags": ["cinematic"]},
            ]}
        ]
        frame_analyses = []

        result = analyzer._aggregate_style_tags(batch_analyses, frame_analyses)

        assert result == ["cinematic"]


# =============================================================================
# 3. _aggregate_effects — 按 confidence 合并
# =============================================================================

class TestAggregateEffects:
    """覆盖 video_effect_analyzer_v2.py 第 1331-1360 行"""

    def test_merge_same_effect_type_takes_higher_confidence(self, analyzer):
        """同类型效果合并时取更高置信度的 params"""
        batch_analyses = [
            {"per_frame": [
                {"effects": [
                    {"type": "glow", "confidence": 0.6, "params": {"v1": 1}},
                ]},
                {"effects": [
                    {"type": "glow", "confidence": 0.9, "params": {"v2": 2}},
                ]},
            ]}
        ]
        frame_analyses = []

        result = analyzer._aggregate_effects(batch_analyses, frame_analyses)

        # 应只保留一个 glow，且取 confidence=0.9 的 params
        glow_results = [e for e in result if e.get("type") == "glow"]
        assert len(glow_results) == 1
        assert glow_results[0]["confidence"] == 0.9
        assert glow_results[0]["params"] == {"v2": 2}
        # occurrence 应累加
        assert glow_results[0]["occurrence"] == 2

    def test_sorted_by_confidence_descending(self, analyzer):
        """结果按 confidence 降序排列"""
        batch_analyses = [
            {"per_frame": [
                {"effects": [
                    {"type": "low", "confidence": 0.3},
                    {"type": "high", "confidence": 0.95},
                    {"type": "mid", "confidence": 0.6},
                ]},
            ]}
        ]
        frame_analyses = []

        result = analyzer._aggregate_effects(batch_analyses, frame_analyses)

        confidences = [e["confidence"] for e in result]
        assert confidences == sorted(confidences, reverse=True)
        assert result[0]["type"] == "high"

    def test_skips_unsuccessful_pending_frames(self, analyzer):
        """success=False 且 pending=True 的帧被跳过"""
        batch_analyses = [
            {"per_frame": [
                {"success": False, "pending": True, "effects": [
                    {"type": "should_skip", "confidence": 0.9}
                ]},
                {"success": True, "effects": [
                    {"type": "should_keep", "confidence": 0.8}
                ]},
            ]}
        ]
        frame_analyses = []

        result = analyzer._aggregate_effects(batch_analyses, frame_analyses)

        types = [e["type"] for e in result]
        assert "should_skip" not in types
        assert "should_keep" in types

    def test_frame_analyses_skips_unsuccessful(self, analyzer):
        """frame_analyses 中 success=False 的帧被跳过"""
        batch_analyses = []
        frame_analyses = [
            {"success": False, "effects": [{"type": "skip"}]},
            {"success": True, "effects": [{"type": "keep"}]},
        ]

        result = analyzer._aggregate_effects(batch_analyses, frame_analyses)

        types = [e["type"] for e in result]
        assert "skip" not in types
        assert "keep" in types


# =============================================================================
# 4. _VISION_TIMEOUT 配置硬约束
# =============================================================================

class TestVisionTimeoutConfig:
    """覆盖 video_effect_analyzer_v2.py 第 300 行"""

    def test_vision_timeout_is_90_seconds(self):
        """_VISION_TIMEOUT 必须为 90 秒（用户硬约束 60-90s 上限）"""
        assert VideoEffectAnalyzerV2._VISION_TIMEOUT == 90

    def test_vision_timeout_within_user_constraints(self):
        """_VISION_TIMEOUT 必须落在用户要求的 60-90s 范围内"""
        timeout = VideoEffectAnalyzerV2._VISION_TIMEOUT
        assert 60 <= timeout <= 90, \
            f"_VISION_TIMEOUT={timeout} 不在用户硬约束 60-90s 范围内"

    def test_batch_max_frames_reasonable(self):
        """批量拼图最大帧数应在合理范围（避免单次 LLM 调用 token 爆炸）"""
        assert 1 <= VideoEffectAnalyzerV2._BATCH_MAX_FRAMES <= 16
