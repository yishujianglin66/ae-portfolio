"""
tests/test_aep_analyzer.py - AEP 分析器测试 (TDD)

使用 mock 数据测试分析逻辑，无需实际 AE 运行。
"""
from __future__ import annotations

import json
import os
import tempfile
import pytest
from typing import Any, Dict

from aep_analyzer.analyzer import AEPAnalyzer
from aep_analyzer.knowledge_extractor import KnowledgeExtractor
from aep_analyzer.report import ReportGenerator
from aep_analyzer.template_learner import TemplateLearner


# ============================================================================
# Mock Data
# ============================================================================

def _make_mock_report() -> Dict[str, Any]:
    """创建模拟分析报告。"""
    return {
        "project": {
            "name": "TestProject.aep",
            "path": "/projects/TestProject.aep",
            "bitsPerChannel": 8,
            "items": {"total": 5, "comps": 2, "footage": 2, "folders": 1},
        },
        "compositions": [
            {
                "name": "Main Comp",
                "id": 1,
                "width": 1920,
                "height": 1080,
                "duration": 10.0,
                "frameRate": 30.0,
                "numLayers": 4,
                "has3D": True,
                "hasCamera": True,
                "hasLight": False,
                "hasAdjustmentLayer": True,
                "hasPrecomp": True,
                "bgColor": [0, 0, 0],
                "layers": [
                    {
                        "name": "BG_Footage",
                        "index": 1,
                        "id": 101,
                        "type": "footage",
                        "inPoint": 0.0,
                        "outPoint": 10.0,
                        "duration": 10.0,
                        "blendMode": "normal",
                        "opacity": {"value": 100, "animated": False, "expression": None},
                        "transform": {
                            "position": {
                                "value": [960, 540, 0],
                                "animated": True,
                                "expression": None,
                                "keyframes": [
                                    {"index": 1, "time": 0.0, "value": [960, 540, 0],
                                     "interpolation": {"in": "bezier", "out": "linear"},
                                     "inEase": {"speed": 0, "influence": 16.7}},
                                    {"index": 2, "time": 2.0, "value": [1200, 540, 0],
                                     "interpolation": {"in": "linear", "out": "bezier"}},
                                ],
                            },
                            "scale": {"value": [100, 100], "animated": False, "expression": None, "keyframes": []},
                            "rotation": {"value": 0, "animated": False, "expression": None, "keyframes": []},
                            "opacity": {"value": 100, "animated": False, "expression": None, "keyframes": []},
                        },
                        "parent": None,
                        "trackMatte": None,
                        "effects": [
                            {
                                "name": "Gaussian Blur",
                                "matchName": "ADBE Gaussian Blur 2",
                                "index": 1,
                                "enabled": True,
                                "isPlugin": False,
                                "category": "模糊",
                                "params": [
                                    {"name": "Blurriness", "index": 1, "value": 15.0,
                                     "animated": True, "keyframes": [
                                         {"index": 1, "time": 0.0, "value": 0},
                                         {"index": 2, "time": 1.0, "value": 15.0},
                                     ]},
                                ],
                                "expressions": [],
                            },
                            {
                                "name": "Curves",
                                "matchName": "ADBE Curves",
                                "index": 2,
                                "enabled": True,
                                "isPlugin": False,
                                "category": "曲线",
                                "params": [],
                                "expressions": [],
                            },
                        ],
                        "masks": [],
                        "source": {"name": "bg.mp4", "width": 1920, "height": 1080,
                                   "duration": 10.0, "path": "/media/bg.mp4"},
                        "threeD": True,
                    },
                    {
                        "name": "Adjustment Layer 1",
                        "index": 2,
                        "id": 102,
                        "type": "adjustment",
                        "inPoint": 0.0,
                        "outPoint": 10.0,
                        "duration": 10.0,
                        "blendMode": "normal",
                        "opacity": {"value": 100, "animated": False, "expression": None},
                        "transform": {
                            "position": {"value": [960, 540], "animated": False, "expression": None, "keyframes": []},
                            "scale": {"value": [100, 100], "animated": False, "expression": None, "keyframes": []},
                            "rotation": {"value": 0, "animated": False, "expression": None, "keyframes": []},
                            "opacity": {"value": 100, "animated": False, "expression": None, "keyframes": []},
                        },
                        "parent": None,
                        "trackMatte": None,
                        "effects": [
                            {
                                "name": "Lumetri Color",
                                "matchName": "ADBE Lumetri",
                                "index": 1,
                                "enabled": True,
                                "isPlugin": False,
                                "category": "色彩",
                                "params": [],
                                "expressions": [
                                    {"property": "Intensity", "text": "time * 10"}
                                ],
                            },
                        ],
                        "masks": [],
                        "source": None,
                        "threeD": False,
                    },
                    {
                        "name": "Null_Controller",
                        "index": 3,
                        "id": 103,
                        "type": "null",
                        "inPoint": 0.0,
                        "outPoint": 10.0,
                        "duration": 10.0,
                        "blendMode": "normal",
                        "opacity": {"value": 100, "animated": False, "expression": None},
                        "transform": {
                            "position": {"value": [960, 540, 0], "animated": False, "expression": None, "keyframes": []},
                            "scale": {"value": [100, 100, 100], "animated": False, "expression": None, "keyframes": []},
                            "rotation": {"value": 0, "animated": False, "expression": None, "keyframes": []},
                            "opacity": {"value": 100, "animated": False, "expression": None, "keyframes": []},
                        },
                        "parent": None,
                        "trackMatte": None,
                        "effects": [
                            {
                                "name": "Slider Control",
                                "matchName": "ADBE Slider Control",
                                "index": 1,
                                "enabled": True,
                                "isPlugin": False,
                                "category": "控制器",
                                "params": [
                                    {"name": "Slider", "index": 1, "value": 50,
                                     "animated": False, "keyframes": []},
                                ],
                                "expressions": [],
                            },
                        ],
                        "masks": [],
                        "source": None,
                        "threeD": False,
                    },
                    {
                        "name": "Particle FX",
                        "index": 4,
                        "id": 104,
                        "type": "precomp",
                        "inPoint": 0.0,
                        "outPoint": 5.0,
                        "duration": 5.0,
                        "blendMode": "add",
                        "opacity": {"value": 80, "animated": False, "expression": None},
                        "transform": {
                            "position": {"value": [960, 540, 0], "animated": False, "expression": None, "keyframes": []},
                            "scale": {"value": [100, 100, 100], "animated": False, "expression": None, "keyframes": []},
                            "rotation": {"value": 0, "animated": False, "expression": None, "keyframes": []},
                            "opacity": {"value": 80, "animated": False, "expression": None, "keyframes": []},
                        },
                        "parent": {"index": 3, "name": "Null_Controller"},
                        "trackMatte": None,
                        "effects": [
                            {
                                "name": "Particular",
                                "matchName": "Trapcode Particular",
                                "index": 1,
                                "enabled": True,
                                "isPlugin": True,
                                "category": "粒子特效",
                                "params": [],
                                "expressions": [],
                            },
                            {
                                "name": "Glow",
                                "matchName": "APCR Glow",
                                "index": 2,
                                "enabled": True,
                                "isPlugin": False,
                                "category": "发光",
                                "params": [],
                                "expressions": [],
                            },
                        ],
                        "masks": [
                            {
                                "name": "Mask 1",
                                "index": 1,
                                "mode": "add",
                                "feather": 10,
                                "opacity": 100,
                                "expansion": 0,
                                "inverted": False,
                            }
                        ],
                        "source": {"name": "Particle Comp", "isPrecomp": True,
                                   "precompName": "Particle Comp"},
                        "threeD": False,
                    },
                ],
                "layerTypes": {
                    "adjustment": ["Adjustment Layer 1"],
                    "null": ["Null_Controller"],
                    "shape": [],
                    "text": [],
                    "footage": ["BG_Footage"],
                    "precomp": ["Particle FX"],
                    "camera": [],
                    "light": [],
                },
            },
        ],
        "precompGraph": {"Main Comp": ["Particle Comp"]},
        "effectsByType": {
            "Gaussian Blur": {"count": 1, "matchName": "ADBE Gaussian Blur 2",
                              "category": "模糊", "isPlugin": False},
            "Curves": {"count": 1, "matchName": "ADBE Curves",
                       "category": "曲线", "isPlugin": False},
            "Lumetri Color": {"count": 1, "matchName": "ADBE Lumetri",
                              "category": "色彩", "isPlugin": False},
            "Slider Control": {"count": 1, "matchName": "ADBE Slider Control",
                               "category": "控制器", "isPlugin": False},
            "Particular": {"count": 1, "matchName": "Trapcode Particular",
                           "category": "粒子特效", "isPlugin": True},
            "Glow": {"count": 1, "matchName": "APCR Glow",
                     "category": "发光", "isPlugin": False},
        },
        "techniques": [
            "粒子特效", "发光效果", "表达式驱动动画 (1个表达式)",
            "3D摄像机运动", "预合成组织 (1个预合成)"
        ],
        "stats": {
            "totalComps": 1,
            "totalLayers": 4,
            "totalEffects": 6,
            "totalKeyframes": 4,
            "totalExpressions": 1,
            "totalMasks": 1,
        },
    }


# ============================================================================
# AEPAnalyzer Tests
# ============================================================================

class TestAEPAnalyzer:
    """AEPAnalyzer 测试"""

    def test_analyze_from_json(self, tmp_path: Any) -> None:
        report = _make_mock_report()
        json_file = str(tmp_path / "test_report.json")
        with open(json_file, "w") as f:
            json.dump(report, f)

        analyzer = AEPAnalyzer()
        result = analyzer.analyze_from_json(json_file)
        assert result["project"]["name"] == "TestProject.aep"
        assert result["stats"]["totalComps"] == 1

    def test_get_summary(self) -> None:
        analyzer = AEPAnalyzer()
        report = _make_mock_report()
        summary = analyzer.get_summary(report)
        assert summary["project_name"] == "TestProject.aep"
        assert summary["total_comps"] == 1
        assert summary["total_layers"] == 4
        assert summary["total_effects"] == 6
        assert summary["total_keyframes"] == 4
        assert summary["total_expressions"] == 1

    def test_get_summary_no_report(self) -> None:
        analyzer = AEPAnalyzer()
        summary = analyzer.get_summary()
        assert "error" in summary

    def test_get_effect_chains(self) -> None:
        analyzer = AEPAnalyzer()
        report = _make_mock_report()
        chains = analyzer.get_effect_chains(report)
        # BG_Footage has 2 effects, Particle FX has 2 effects
        assert len(chains) == 2
        # Check first chain
        first = chains[0]
        assert "comp" in first
        assert "effects" in first
        assert len(first["effects"]) >= 2

    def test_get_last_report(self) -> None:
        analyzer = AEPAnalyzer()
        assert analyzer.get_last_report() is None
        report = _make_mock_report()
        analyzer._last_report = report
        assert analyzer.get_last_report() is not None


# ============================================================================
# KnowledgeExtractor Tests
# ============================================================================

class TestKnowledgeExtractor:
    """KnowledgeExtractor 测试"""

    def setup_method(self) -> None:
        self.extractor = KnowledgeExtractor()
        self.report = _make_mock_report()

    def test_extract_all(self) -> None:
        knowledge = self.extractor.extract_all(self.report)
        assert "effect_chains" in knowledge
        assert "keyframe_patterns" in knowledge
        assert "layer_organization" in knowledge
        assert "technique_tags" in knowledge
        assert "color_grading_patterns" in knowledge
        assert "common_effects" in knowledge
        assert "plugin_usage" in knowledge

    def test_extract_effect_chains(self) -> None:
        chains = self.extractor.extract_effect_chains(self.report)
        assert len(chains) > 0
        # Find the Gaussian Blur + Curves chain
        found = False
        for chain in chains:
            effects = chain.get("effects", [])
            if "Gaussian Blur" in effects and "Curves" in effects:
                found = True
                break
        assert found, "Should find Gaussian Blur + Curves chain"

    def test_extract_keyframe_patterns(self) -> None:
        patterns = self.extractor.extract_keyframe_patterns(self.report)
        assert patterns["total_keyframes"] > 0
        assert "interpolation_distribution" in patterns
        # Should find bezier and linear interpolations
        interp = patterns["interpolation_distribution"]
        assert "linear" in interp or "bezier" in interp

    def test_extract_layer_organization(self) -> None:
        org = self.extractor.extract_layer_organization(self.report)
        assert org["total_layers"] == 4
        assert org["has_null_controllers"] is True
        assert org["has_adjustment_layers"] is True
        assert org["has_precomps"] is True
        # Check parent relationships
        assert len(org["parent_relationships"]) == 1
        assert org["parent_relationships"][0]["parent_name"] == "Null_Controller"

    def test_extract_technique_tags(self) -> None:
        tags = self.extractor.extract_technique_tags(self.report)
        assert "粒子特效" in tags
        assert "3D摄像机运动" in tags

    def test_extract_color_patterns(self) -> None:
        color = self.extractor.extract_color_patterns(self.report)
        assert color["color_effect_count"] > 0
        assert color["has_curves"] is True
        assert color["has_lumetri"] is True

    def test_extract_common_effects(self) -> None:
        effects = self.extractor.extract_common_effects(self.report)
        assert len(effects) > 0
        # All effects have count=1, so just check structure
        first = effects[0]
        assert "name" in first
        assert "count" in first
        assert "isPlugin" in first

    def test_extract_plugin_usage(self) -> None:
        usage = self.extractor.extract_plugin_usage(self.report)
        assert usage["plugin_count"] == 1  # Particular
        assert "Particular" in usage["plugins"]
        assert usage["standard_effect_count"] == 5

    def test_empty_report(self) -> None:
        empty: Dict[str, Any] = {"compositions": [], "effectsByType": {},
                                  "techniques": [], "stats": {}}
        knowledge = self.extractor.extract_all(empty)
        assert knowledge["effect_chains"] == []
        assert knowledge["technique_tags"] == []


# ============================================================================
# ReportGenerator Tests
# ============================================================================

class TestReportGenerator:
    """ReportGenerator 测试"""

    def setup_method(self) -> None:
        self.generator = ReportGenerator()
        self.report = _make_mock_report()

    def test_generate_json(self) -> None:
        json_str = self.generator.generate_json(self.report)
        data = json.loads(json_str)
        assert "meta" in data
        assert "analysis" in data
        assert data["analysis"]["project"]["name"] == "TestProject.aep"

    def test_generate_json_with_knowledge(self) -> None:
        knowledge = {"effect_chains": [{"effects": ["Blur", "Glow"], "frequency": 3}]}
        json_str = self.generator.generate_json(self.report, knowledge)
        data = json.loads(json_str)
        assert "knowledge" in data

    def test_generate_json_to_file(self, tmp_path: Any) -> None:
        output = str(tmp_path / "report.json")
        self.generator.generate_json(self.report, output_path=output)
        assert os.path.isfile(output)
        with open(output, encoding="utf-8") as f:
            data = json.load(f)
        assert data["analysis"]["project"]["name"] == "TestProject.aep"

    def test_generate_summary(self) -> None:
        summary = self.generator.generate_summary(self.report)
        assert "AEP Analysis Report" in summary
        assert "TestProject.aep" in summary
        assert "Compositions: 1" in summary

    def test_generate_markdown(self) -> None:
        md = self.generator.generate_markdown(self.report)
        assert "# AEP Analysis" in md
        assert "TestProject.aep" in md
        assert "## Statistics" in md
        assert "## Techniques" in md


# ============================================================================
# TemplateLearner Tests
# ============================================================================

class TestTemplateLearner:
    """TemplateLearner 测试"""

    def test_add_and_synthesize(self) -> None:
        learner = TemplateLearner(kb_dir="/tmp/test_kb")
        report = _make_mock_report()
        learner.add_report(report)

        knowledge = learner.synthesize()
        assert knowledge["template_count"] == 1
        assert "common_effect_chains" in knowledge
        assert "technique_frequency" in knowledge

    def test_multiple_reports(self) -> None:
        learner = TemplateLearner(kb_dir="/tmp/test_kb")
        report1 = _make_mock_report()
        report2 = _make_mock_report()
        learner.add_report(report1)
        learner.add_report(report2)

        knowledge = learner.synthesize()
        assert knowledge["template_count"] == 2
        # Techniques should have doubled counts
        techniques = dict(knowledge["technique_frequency"])
        assert techniques.get("粒子特效", 0) == 2

    def test_empty_learner(self) -> None:
        learner = TemplateLearner(kb_dir="/tmp/test_kb")
        knowledge = learner.synthesize()
        assert "error" in knowledge

    def test_write_to_kb(self, tmp_path: Any) -> None:
        kb_dir = str(tmp_path / "kb")
        learner = TemplateLearner(kb_dir=kb_dir)
        learner.add_report(_make_mock_report())

        output = learner.write_to_kb("test_patterns.md")
        assert output != ""
        assert os.path.isfile(output)
        with open(output, encoding="utf-8") as f:
            content = f.read()
        assert "AEP 模板学习到的通用模式" in content

    def test_add_from_json(self, tmp_path: Any) -> None:
        report = _make_mock_report()
        json_file = str(tmp_path / "report.json")
        with open(json_file, "w") as f:
            json.dump(report, f)

        learner = TemplateLearner(kb_dir="/tmp/test_kb")
        learner.add_report_from_json(json_file)
        knowledge = learner.synthesize()
        assert knowledge["template_count"] == 1
