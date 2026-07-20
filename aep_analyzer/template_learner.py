"""
aep_analyzer/template_learner.py - 模板学习与知识入库

批量分析多个 .aep 模板文件，提取通用模式并写入知识库。
"""
from __future__ import annotations

import json
import logging
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from aep_analyzer.analyzer import AEPAnalyzer
from aep_analyzer.knowledge_extractor import KnowledgeExtractor

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_KB_DIR = str(_PROJECT_ROOT / "10-风格化剪辑知识库")


class TemplateLearner:
    """模板学习器 - 批量分析 AEP 模板并提取通用知识。

    用法：
        learner = TemplateLearner()
        learner.add_report(report1)
        learner.add_report(report2)
        knowledge = learner.synthesize()
        learner.write_to_kb("learned_patterns.md")
    """

    def __init__(self, kb_dir: str = "") -> None:
        self._kb_dir = kb_dir or _DEFAULT_KB_DIR
        self._reports: List[Dict[str, Any]] = []
        self._knowledge_list: List[Dict[str, Any]] = []
        self._extractor = KnowledgeExtractor()

    def add_report(self, report: Dict[str, Any]) -> None:
        """添加一份分析报告。

        Args:
            report: AEP 分析报告
        """
        self._reports.append(report)
        knowledge = self._extractor.extract_all(report)
        self._knowledge_list.append(knowledge)

    def add_report_from_json(self, json_path: str) -> None:
        """从 JSON 文件加载并添加报告。

        Args:
            json_path: JSON 文件路径
        """
        analyzer = AEPAnalyzer()
        report = analyzer.analyze_from_json(json_path)
        self.add_report(report)

    def synthesize(self) -> Dict[str, Any]:
        """综合所有报告提取通用模式。

        Returns:
            综合知识字典
        """
        if not self._knowledge_list:
            return {"error": "No reports added"}

        return {
            "common_effect_chains": self._merge_effect_chains(),
            "common_color_patterns": self._merge_color_patterns(),
            "common_naming_patterns": self._merge_naming_patterns(),
            "plugin_frequency": self._merge_plugin_usage(),
            "technique_frequency": self._merge_techniques(),
            "template_count": len(self._reports),
            "summary": self._generate_summary(),
        }

    def write_to_kb(self, filename: str = "learned_aep_patterns.md") -> str:
        """将学习到的模式写入知识库。

        Args:
            filename: 输出文件名

        Returns:
            输出文件路径
        """
        knowledge = self.synthesize()
        if "error" in knowledge:
            return ""

        md_lines: List[str] = []
        md_lines.append("# AEP 模板学习到的通用模式")
        md_lines.append("")
        md_lines.append(f"基于 {knowledge['template_count']} 个模板文件分析。")
        md_lines.append("")

        # Effect chains
        chains = knowledge.get("common_effect_chains", [])
        if chains:
            md_lines.append("## 常用效果链")
            md_lines.append("")
            md_lines.append("| 效果组合 | 出现次数 | 图层类型 |")
            md_lines.append("|---------|---------|---------|")
            for chain in chains[:20]:
                effects = " -> ".join(chain.get("effects", [])[:4])
                count = chain.get("total_frequency", 0)
                layer_type = chain.get("layer_type", "")
                md_lines.append(f"| {effects} | {count} | {layer_type} |")
            md_lines.append("")

        # Techniques
        techniques = knowledge.get("technique_frequency", [])
        if techniques:
            md_lines.append("## 常见技法")
            md_lines.append("")
            for tech, count in techniques:
                md_lines.append(f"- {tech} ({count}次)")
            md_lines.append("")

        # Plugins
        plugins = knowledge.get("plugin_frequency", {})
        if plugins:
            md_lines.append("## 插件使用频率")
            md_lines.append("")
            md_lines.append("| 插件 | 使用次数 |")
            md_lines.append("|------|---------|")
            for name, count in sorted(
                plugins.items(), key=lambda x: x[1], reverse=True
            )[:15]:
                md_lines.append(f"| {name} | {count} |")
            md_lines.append("")

        content = "\n".join(md_lines)
        output_path = os.path.join(self._kb_dir, filename)

        os.makedirs(self._kb_dir, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info(f"Knowledge written to: {output_path}")
        return output_path

    # =========================================================================
    # Merge Methods
    # =========================================================================

    def _merge_effect_chains(self) -> List[Dict[str, Any]]:
        """合并所有报告的效果链。"""
        chain_freq: Counter = Counter()
        chain_info: Dict[str, Dict[str, Any]] = {}

        for knowledge in self._knowledge_list:
            for chain in knowledge.get("effect_chains", []):
                key = " -> ".join(chain.get("effects", []))
                chain_freq[key] += chain.get("frequency", 1)
                if key not in chain_info:
                    chain_info[key] = {
                        "effects": chain.get("effects", []),
                        "layer_type": chain.get("layer_type", ""),
                        "total_frequency": 0,
                    }
                chain_info[key]["total_frequency"] += chain.get("frequency", 1)

        result: List[Dict[str, Any]] = []
        for key, freq in chain_freq.most_common(30):
            info = chain_info[key]
            info["total_frequency"] = freq
            result.append(info)
        return result

    def _merge_color_patterns(self) -> Dict[str, int]:
        """合并调色模式。"""
        merged: Counter = Counter()
        for knowledge in self._knowledge_list:
            color = knowledge.get("color_grading_patterns", {})
            for name, count in color.get("color_effects_used", {}).items():
                merged[name] += count
        return dict(merged)

    def _merge_naming_patterns(self) -> List[tuple]:
        """合并命名模式。"""
        merged: Counter = Counter()
        for knowledge in self._knowledge_list:
            org = knowledge.get("layer_organization", {})
            for pattern, count in org.get("common_naming_patterns", []):
                merged[pattern] += count
        return merged.most_common(20)

    def _merge_plugin_usage(self) -> Dict[str, int]:
        """合并插件使用频率。"""
        merged: Counter = Counter()
        for knowledge in self._knowledge_list:
            plugins = knowledge.get("plugin_usage", {})
            for name, count in plugins.get("plugins", {}).items():
                merged[name] += count
        return dict(merged)

    def _merge_techniques(self) -> List[tuple]:
        """合并技法标签。"""
        merged: Counter = Counter()
        for knowledge in self._knowledge_list:
            for tech in knowledge.get("technique_tags", []):
                merged[tech] += 1
        return merged.most_common()

    def _generate_summary(self) -> Dict[str, Any]:
        """生成综合摘要。"""
        total_layers = 0
        total_effects = 0
        total_keyframes = 0

        for report in self._reports:
            stats = report.get("stats", {})
            total_layers += stats.get("totalLayers", 0)
            total_effects += stats.get("totalEffects", 0)
            total_keyframes += stats.get("totalKeyframes", 0)

        return {
            "template_count": len(self._reports),
            "avg_layers_per_template": (
                total_layers / len(self._reports) if self._reports else 0
            ),
            "avg_effects_per_template": (
                total_effects / len(self._reports) if self._reports else 0
            ),
            "avg_keyframes_per_template": (
                total_keyframes / len(self._reports) if self._reports else 0
            ),
        }
