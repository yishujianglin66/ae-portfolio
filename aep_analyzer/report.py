"""
aep_analyzer/report.py - 分析报告生成器

生成结构化分析报告（JSON + 可读摘要）。
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ReportGenerator:
    """AEP 分析报告生成器。

    支持：
    - JSON 结构化报告
    - 可读文本摘要
    - Markdown 格式报告
    """

    def generate_json(
        self,
        report: dict[str, Any],
        knowledge: dict[str, Any] | None = None,
        output_path: str = "",
    ) -> str:
        """生成 JSON 格式报告。

        Args:
            report: AEP 分析结果
            knowledge: 提取的知识（可选）
            output_path: 输出文件路径（可选）

        Returns:
            JSON 字符串
        """
        full_report: dict[str, Any] = {
            "meta": {
                "generated_at": datetime.now().isoformat(),
                "analyzer_version": "1.0.0",
            },
            "analysis": report,
        }
        if knowledge:
            full_report["knowledge"] = knowledge

        json_str = json.dumps(full_report, ensure_ascii=False, indent=2)

        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(json_str)
            logger.info(f"Report saved to: {output_path}")

        return json_str

    def generate_summary(
        self,
        report: dict[str, Any],
        knowledge: dict[str, Any] | None = None,
    ) -> str:
        """生成可读文本摘要。

        Args:
            report: AEP 分析结果
            knowledge: 提取的知识（可选）

        Returns:
            文本摘要
        """
        lines: list[str] = []
        lines.append("=" * 60)
        lines.append("AEP Analysis Report")
        lines.append("=" * 60)

        # Project info
        proj = report.get("project", {})
        lines.append(f"\nProject: {proj.get('name', 'Unknown')}")
        lines.append(f"Path: {proj.get('path', 'N/A')}")

        # Stats
        stats = report.get("stats", {})
        lines.append("\n--- Statistics ---")
        lines.append(f"Compositions: {stats.get('totalComps', 0)}")
        lines.append(f"Layers: {stats.get('totalLayers', 0)}")
        lines.append(f"Effects: {stats.get('totalEffects', 0)}")
        lines.append(f"Keyframes: {stats.get('totalKeyframes', 0)}")
        lines.append(f"Expressions: {stats.get('totalExpressions', 0)}")
        lines.append(f"Masks: {stats.get('totalMasks', 0)}")

        # Techniques
        techniques = report.get("techniques", [])
        if techniques:
            lines.append("\n--- Techniques Detected ---")
            for t in techniques:
                lines.append(f"  - {t}")

        # Top effects
        effects_by_type = report.get("effectsByType", {})
        if effects_by_type:
            sorted_effects = sorted(
                effects_by_type.items(),
                key=lambda x: x[1].get("count", 0),
                reverse=True,
            )
            lines.append("\n--- Top 10 Effects ---")
            for name, data in sorted_effects[:10]:
                count = data.get("count", 0)
                plugin = " [Plugin]" if data.get("isPlugin") else ""
                lines.append(f"  {name}{plugin}: {count}x")

        # Precomp structure
        precomp_graph = report.get("precompGraph", {})
        if precomp_graph:
            lines.append("\n--- Precomp Structure ---")
            for parent, children in precomp_graph.items():
                lines.append(f"  {parent} -> {', '.join(children)}")

        # Knowledge summary
        if knowledge:
            lines.append("\n--- Knowledge Extracted ---")

            # Effect chains
            chains = knowledge.get("effect_chains", [])
            if chains:
                lines.append(f"  Effect Chains: {len(chains)} patterns found")
                for chain in chains[:5]:
                    effects = chain.get("effects", [])
                    freq = chain.get("frequency", 0)
                    lines.append(f"    [{freq}x] {' -> '.join(effects[:5])}")

            # Plugin usage
            plugins = knowledge.get("plugin_usage", {})
            if plugins.get("plugin_count", 0) > 0:
                lines.append(
                    f"  Plugins: {plugins['plugin_count']} unique plugins"
                )

        lines.append("\n" + "=" * 60)
        return "\n".join(lines)

    def generate_markdown(
        self,
        report: dict[str, Any],
        knowledge: dict[str, Any] | None = None,
    ) -> str:
        """生成 Markdown 格式报告。

        Args:
            report: AEP 分析结果
            knowledge: 提取的知识（可选）

        Returns:
            Markdown 字符串
        """
        lines: list[str] = []
        proj = report.get("project", {})
        stats = report.get("stats", {})

        lines.append(f"# AEP Analysis: {proj.get('name', 'Unknown')}")
        lines.append("")
        lines.append(f"**Path**: `{proj.get('path', 'N/A')}`")
        lines.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append("")

        # Stats table
        lines.append("## Statistics")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Compositions | {stats.get('totalComps', 0)} |")
        lines.append(f"| Layers | {stats.get('totalLayers', 0)} |")
        lines.append(f"| Effects | {stats.get('totalEffects', 0)} |")
        lines.append(f"| Keyframes | {stats.get('totalKeyframes', 0)} |")
        lines.append(f"| Expressions | {stats.get('totalExpressions', 0)} |")
        lines.append(f"| Masks | {stats.get('totalMasks', 0)} |")
        lines.append("")

        # Techniques
        techniques = report.get("techniques", [])
        if techniques:
            lines.append("## Techniques Detected")
            lines.append("")
            for t in techniques:
                lines.append(f"- {t}")
            lines.append("")

        # Effects
        effects_by_type = report.get("effectsByType", {})
        if effects_by_type:
            sorted_effects = sorted(
                effects_by_type.items(),
                key=lambda x: x[1].get("count", 0),
                reverse=True,
            )
            lines.append("## Top Effects")
            lines.append("")
            lines.append("| Effect | Count | Category | Plugin |")
            lines.append("|--------|-------|----------|--------|")
            for name, data in sorted_effects[:15]:
                count = data.get("count", 0)
                cat = data.get("category", "")
                plugin = "Yes" if data.get("isPlugin") else "No"
                lines.append(f"| {name} | {count} | {cat} | {plugin} |")
            lines.append("")

        # Knowledge
        if knowledge:
            chains = knowledge.get("effect_chains", [])
            if chains:
                lines.append("## Effect Chain Patterns")
                lines.append("")
                for chain in chains[:10]:
                    effects = chain.get("effects", [])
                    freq = chain.get("frequency", 0)
                    lines.append(f"- **[{freq}x]** {' -> '.join(effects)}")
                lines.append("")

        return "\n".join(lines)
