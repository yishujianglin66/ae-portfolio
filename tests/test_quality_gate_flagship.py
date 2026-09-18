"""
tests/test_quality_gate_flagship.py — 旗舰管线质量门 + 八类错误 测试
===================================================================

覆盖：
- QG-1 帧亮度规则
- QG-4 节拍对齐规则
- QG-5 调色节点规则
- 八类错误枚举 + 分类 + 修复建议
"""
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from core.failure_postmortem import (
    FLAGSHIP_FIX_TEMPLATES,
    FlagshipErrorCode,
    classify_error,
    get_fix_recommendation,
)
from core.quality_gate import (
    BeatAlignmentRule,
    FrameLuminanceRule,
    GradeNodeRule,
    QualityContext,
    QualityGate,
)

# ============================================================================
#  QG-1 帧亮度规则
# ============================================================================

class TestFrameLuminanceRule:
    """QG-1 帧亮度采样规则测试"""

    def test_rule_id(self):
        rule = FrameLuminanceRule()
        assert rule.rule_id == "frame_luminance"
        assert rule.weight == 2.0

    def test_missing_video_skips(self):
        """视频不存在 → 跳过（passed=True, warning）"""
        rule = FrameLuminanceRule()
        ctx = QualityContext(output_path="/nonexistent/video.mp4")
        result = rule.evaluate(ctx)
        assert result.passed is True
        assert result.severity == "warning"

    def test_empty_path_skips(self):
        """空路径 → 跳过"""
        rule = FrameLuminanceRule()
        ctx = QualityContext(output_path="")
        result = rule.evaluate(ctx)
        assert result.passed is True

    def test_no_opencv_skips(self, tmp_path):
        """OpenCV 不可用 → 跳过"""
        rule = FrameLuminanceRule()
        vid = tmp_path / "test.mp4"
        vid.write_bytes(b"\x00" * 100)

        ctx = QualityContext(output_path=str(vid))
        # 模拟 ImportError
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name in ("cv2", "numpy"):
                raise ImportError(f"no {name}")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            result = rule.evaluate(ctx)
        # 应该跳过但不崩溃
        assert result is not None
        assert result.passed is True


# ============================================================================
#  QG-4 节拍对齐规则
# ============================================================================

class TestBeatAlignmentRule:
    """QG-4 节拍对齐规则测试"""

    def test_rule_id(self):
        rule = BeatAlignmentRule()
        assert rule.rule_id == "beat_alignment"
        assert rule.max_offset_ms == 80.0

    def test_missing_paths_skips(self):
        """缺少路径 → 跳过"""
        rule = BeatAlignmentRule()
        ctx = QualityContext(extra={})
        result = rule.evaluate(ctx)
        assert result.passed is True
        assert result.severity == "warning"

    def test_perfect_alignment(self, tmp_path):
        """完美对齐 → 通过"""
        rule = BeatAlignmentRule(max_offset_ms=80.0)

        # 创建 beats.json
        beats = tmp_path / "beats.json"
        beats.write_text(json.dumps({"bpm": 128, "drops": [1.0, 2.0, 3.0, 4.0]}))

        # 创建 timeline.xml（标记点在相同时间）
        xml = tmp_path / "timeline.xml"
        xml.write_text("""<?xml version="1.0"?>
<fcpxml>
  <library>
    <event>
      <project>
        <sequence>
          <markeritem><start>1.0</start></markeritem>
          <markeritem><start>2.0</start></markeritem>
          <markeritem><start>3.0</start></markeritem>
          <markeritem><start>4.0</start></markeritem>
        </sequence>
      </project>
    </event>
  </library>
</fcpxml>""")

        ctx = QualityContext(extra={
            "beats_json_path": str(beats),
            "timeline_xml_path": str(xml),
        })
        result = rule.evaluate(ctx)
        assert result.passed is True
        assert result.score == 1.0

    def test_misalignment_fails(self, tmp_path):
        """偏移过大 → 失败"""
        rule = BeatAlignmentRule(max_offset_ms=80.0)

        beats = tmp_path / "beats.json"
        beats.write_text(json.dumps({"bpm": 128, "drops": [1.0, 2.0, 3.0]}))

        # 标记点偏移 200ms
        xml = tmp_path / "timeline.xml"
        xml.write_text("""<?xml version="1.0"?>
<fcpxml>
  <library>
    <event>
      <project>
        <sequence>
          <markeritem><start>1.2</start></markeritem>
          <markeritem><start>2.2</start></markeritem>
          <markeritem><start>3.2</start></markeritem>
        </sequence>
      </project>
    </event>
  </library>
</fcpxml>""")

        ctx = QualityContext(extra={
            "beats_json_path": str(beats),
            "timeline_xml_path": str(xml),
        })
        result = rule.evaluate(ctx)
        assert result.passed is False
        assert result.severity == "error"
        assert "偏移" in result.reason


# ============================================================================
#  QG-5 调色节点规则
# ============================================================================

class TestGradeNodeRule:
    """QG-5 调色节点规则测试"""

    def test_rule_id(self):
        rule = GradeNodeRule()
        assert rule.rule_id == "grade_nodes"
        assert rule.min_nodes == 3

    def test_no_metadata_skips(self):
        """无调色元数据 → 跳过"""
        rule = GradeNodeRule()
        ctx = QualityContext(extra={})
        result = rule.evaluate(ctx)
        assert result.passed is True
        assert result.severity == "warning"

    def test_sufficient_nodes_with_lut(self):
        """节点充足 + 有 LUT → 通过"""
        rule = GradeNodeRule(min_nodes=3, require_lut=True)
        ctx = QualityContext(extra={
            "grade_metadata": {
                "node_count": 4,
                "include_lut": True,
                "nodes_applied": [
                    {"index": 0, "type": "corrector"},
                    {"index": 1, "type": "lut"},
                    {"index": 2, "type": "style"},
                    {"index": 3, "type": "style"},
                ],
            }
        })
        result = rule.evaluate(ctx)
        assert result.passed is True
        assert result.score == 1.0

    def test_insufficient_nodes(self):
        """节点不足 → 失败"""
        rule = GradeNodeRule(min_nodes=3, require_lut=True)
        ctx = QualityContext(extra={
            "grade_metadata": {
                "node_count": 2,
                "include_lut": True,
            }
        })
        result = rule.evaluate(ctx)
        assert result.passed is False
        assert "节点数" in result.reason

    def test_missing_lut(self):
        """缺少 LUT → 失败"""
        rule = GradeNodeRule(min_nodes=3, require_lut=True)
        ctx = QualityContext(extra={
            "grade_metadata": {
                "node_count": 4,
                "include_lut": False,
            }
        })
        result = rule.evaluate(ctx)
        assert result.passed is False
        assert "LUT" in result.reason


# ============================================================================
#  八类错误枚举 + 分类 + 修复建议
# ============================================================================

class TestFlagshipErrorCodes:
    """八类错误枚举测试"""

    def test_all_codes_exist(self):
        """8 个错误码全部存在"""
        assert len(FlagshipErrorCode) == 8
        expected = [
            "BRIDGE_DOWN", "LICENSE_MISSING", "OUTPUT_CORRUPT",
            "SCRIPT_SYNTAX", "TIMEOUT", "USER_CANCELLED",
            "DISK_FULL", "LICENCE_POPUP_BLOCKING",
        ]
        for code in expected:
            assert FlagshipErrorCode(code) is not None

    def test_all_codes_have_templates(self):
        """每个错误码都有修复模板"""
        for code in FlagshipErrorCode:
            assert code in FLAGSHIP_FIX_TEMPLATES
            tmpl = FLAGSHIP_FIX_TEMPLATES[code]
            assert "title" in tmpl
            assert "action" in tmpl
            assert tmpl["confidence"] > 0

    def test_classify_direct_match(self):
        """直接匹配错误码"""
        assert classify_error("BRIDGE_DOWN") == FlagshipErrorCode.BRIDGE_DOWN
        assert classify_error("TIMEOUT") == FlagshipErrorCode.TIMEOUT
        assert classify_error("DISK_FULL") == FlagshipErrorCode.DISK_FULL

    def test_classify_by_message(self):
        """通过错误信息关键词分类"""
        assert classify_error("", "Bridge connection lost") == FlagshipErrorCode.BRIDGE_DOWN
        assert classify_error("", "license expired") == FlagshipErrorCode.LICENSE_MISSING
        assert classify_error("", "licence popup blocking") == FlagshipErrorCode.LICENCE_POPUP_BLOCKING
        assert classify_error("", "output file corrupt") == FlagshipErrorCode.OUTPUT_CORRUPT
        assert classify_error("", "JSX syntax error") == FlagshipErrorCode.SCRIPT_SYNTAX
        assert classify_error("", "operation timed out") == FlagshipErrorCode.TIMEOUT
        assert classify_error("", "user cancelled") == FlagshipErrorCode.USER_CANCELLED
        assert classify_error("", "disk full") == FlagshipErrorCode.DISK_FULL

    def test_classify_unknown_defaults_timeout(self):
        """未知错误默认归类为 TIMEOUT"""
        assert classify_error("", "something weird happened") == FlagshipErrorCode.TIMEOUT

    def test_get_fix_recommendation(self):
        """获取修复建议"""
        rec = get_fix_recommendation(FlagshipErrorCode.BRIDGE_DOWN)
        assert rec.title == "Bridge 连接中断"
        assert rec.confidence == 0.9
        assert rec.source == "expert"
        assert "Bridge" in rec.action

    def test_fix_recommendation_all_codes(self):
        """所有错误码都能获取修复建议"""
        for code in FlagshipErrorCode:
            rec = get_fix_recommendation(code)
            assert rec.title != ""
            assert rec.action != ""


# ============================================================================
#  集成测试：QualityGate + 旗舰规则
# ============================================================================

class TestQualityGateFlagship:
    """旗舰质量门集成测试"""

    def test_gate_with_flagship_rules_pass(self, tmp_path):
        """全部旗舰规则通过 → PASS"""
        gate = QualityGate()
        gate.add_rule(BeatAlignmentRule())
        gate.add_rule(GradeNodeRule())

        # 创建对齐的 beats + xml
        beats = tmp_path / "beats.json"
        beats.write_text(json.dumps({"bpm": 128, "drops": [1.0, 2.0]}))
        xml = tmp_path / "timeline.xml"
        xml.write_text("""<fcpxml><markeritem><start>1.0</start></markeritem>
<markeritem><start>2.0</start></markeritem></fcpxml>""")

        ctx = QualityContext(
            output_path="",
            duration_sec=15.0,
            resolution=(1920, 1080),
            stages_success=True,
            extra={
                "beats_json_path": str(beats),
                "timeline_xml_path": str(xml),
                "grade_metadata": {"node_count": 4, "include_lut": True},
            },
        )
        result = gate.evaluate(ctx)
        # 不应该有 error 级别的失败
        blocking = gate.get_blocking_issues(result)
        assert len(blocking) == 0

    def test_gate_with_grade_failure(self):
        """调色节点不足 → FAIL"""
        gate = QualityGate()
        gate.add_rule(GradeNodeRule(min_nodes=3, require_lut=True))

        ctx = QualityContext(
            output_path="",
            duration_sec=15.0,
            stages_success=True,
            extra={
                "grade_metadata": {"node_count": 1, "include_lut": False},
            },
        )
        result = gate.evaluate(ctx)
        assert result.status == "FAIL"
        blocking = gate.get_blocking_issues(result)
        assert any(i.rule_id == "grade_nodes" for i in blocking)
