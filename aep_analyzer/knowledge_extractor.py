"""
aep_analyzer/knowledge_extractor.py - 知识提取器

从 AEP 分析结果中提取知识：
- 效果链模式（常用效果组合）
- 关键帧节奏模式（动画曲线偏好）
- 图层组织模式（命名规范、分组逻辑）
- 技法标签（自动检测并标记）
"""
from __future__ import annotations

import logging
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class KnowledgeExtractor:
    """从 AEP 分析报告中提取知识。

    提取维度：
    1. 效果链模式 - 哪些效果经常一起使用
    2. 关键帧模式 - 动画曲线偏好（linear/bezier/hold）
    3. 图层组织 - 命名规范、层级结构
    4. 技法标签 - 自动识别的制作技术
    5. 调色模式 - 常用调色效果组合
    """

    def extract_all(self, report: Dict[str, Any]) -> Dict[str, Any]:
        """提取所有知识维度。

        Args:
            report: AEP 分析报告

        Returns:
            知识字典
        """
        return {
            "effect_chains": self.extract_effect_chains(report),
            "keyframe_patterns": self.extract_keyframe_patterns(report),
            "layer_organization": self.extract_layer_organization(report),
            "technique_tags": self.extract_technique_tags(report),
            "color_grading_patterns": self.extract_color_patterns(report),
            "common_effects": self.extract_common_effects(report),
            "plugin_usage": self.extract_plugin_usage(report),
        }

    def extract_effect_chains(
        self, report: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """提取效果链模式。

        分析哪些效果经常在同一图层上组合使用。

        Returns:
            效果链列表，按出现频率排序
        """
        chain_counter: Counter = Counter()
        chain_details: Dict[str, Dict[str, Any]] = {}

        for comp in report.get("compositions", []):
            for layer in comp.get("layers", []):
                effects = layer.get("effects", [])
                if len(effects) < 2:
                    continue

                # 构建效果链签名
                names = sorted([e.get("name", "") for e in effects])
                chain_key = " -> ".join(names)
                chain_counter[chain_key] += 1

                if chain_key not in chain_details:
                    chain_details[chain_key] = {
                        "effects": names,
                        "match_names": [
                            e.get("matchName", "") for e in effects
                        ],
                        "layer_type": layer.get("type", ""),
                        "sample_comp": comp.get("name", ""),
                        "sample_layer": layer.get("name", ""),
                        "count": 0,
                    }
                chain_details[chain_key]["count"] += 1

        # 按频率排序
        result: List[Dict[str, Any]] = []
        for chain_key, count in chain_counter.most_common(20):
            detail = chain_details[chain_key]
            detail["frequency"] = count
            result.append(detail)

        return result

    def extract_keyframe_patterns(
        self, report: Dict[str, Any]
    ) -> Dict[str, Any]:
        """提取关键帧动画模式。

        分析关键帧的缓动类型分布、时间间隔模式等。

        Returns:
            关键帧模式字典
        """
        interpolation_types: Counter = Counter()
        ease_speeds: List[float] = []
        animated_properties: List[str] = []
        total_keyframes = 0
        bezier_curves: List[Dict[str, Any]] = []
        property_timelines: Dict[str, List[Dict[str, Any]]] = {}

        for comp in report.get("compositions", []):
            for layer in comp.get("layers", []):
                layer_name = layer.get("name", "unknown")
                # Transform keyframes
                transform = layer.get("transform", {})
                for prop_name, prop_data in transform.items():
                    if isinstance(prop_data, dict):
                        kfs = prop_data.get("keyframes", [])
                        total_keyframes += len(kfs)
                        if kfs:
                            animated_properties.append(prop_name)
                        timeline: List[Dict[str, Any]] = []
                        for kf in kfs:
                            interp = kf.get("interpolation", {})
                            for direction in ["in", "out"]:
                                itype = interp.get(direction, "")
                                if itype:
                                    interpolation_types[itype] += 1
                            # Ease speed
                            in_ease = kf.get("inEase", {})
                            if in_ease and "speed" in in_ease:
                                ease_speeds.append(abs(in_ease["speed"]))
                            # Bezier control points extraction
                            bezier_in = kf.get("inBezier", kf.get("bezierIn"))
                            bezier_out = kf.get("outBezier", kf.get("bezierOut"))
                            if bezier_in or bezier_out:
                                curve_info: Dict[str, Any] = {
                                    "layer": layer_name,
                                    "property": prop_name,
                                    "time": kf.get("time", 0),
                                    "value": kf.get("value"),
                                }
                                if bezier_in:
                                    curve_info["bezier_in"] = bezier_in
                                if bezier_out:
                                    curve_info["bezier_out"] = bezier_out
                                # Spatial tangents
                                spatial_in = kf.get("spatialInBezier", kf.get("inSpatial"))
                                spatial_out = kf.get("spatialOutBezier", kf.get("outSpatial"))
                                if spatial_in:
                                    curve_info["spatial_in"] = spatial_in
                                if spatial_out:
                                    curve_info["spatial_out"] = spatial_out
                                bezier_curves.append(curve_info)
                            # Build timeline
                            timeline.append({
                                "time": kf.get("time", 0),
                                "value": kf.get("value"),
                                "interpolation": interp,
                                "ease_in_speed": in_ease.get("speed", 0) if in_ease else 0,
                            })
                        if timeline:
                            prop_key = f"{layer_name}.{prop_name}"
                            property_timelines[prop_key] = timeline

                # Effect parameter keyframes
                for effect in layer.get("effects", []):
                    for param in effect.get("params", []):
                        kfs = param.get("keyframes", [])
                        total_keyframes += len(kfs)

        # Compute curve statistics
        curve_type_summary: Counter = Counter()
        for curve in bezier_curves:
            bi = curve.get("bezier_in", [])
            if bi and len(bi) >= 2:
                # Classify: ease-in (control point close to keyframe)
                magnitude = (bi[0] ** 2 + bi[1] ** 2) ** 0.5 if len(bi) >= 2 else 0
                if magnitude < 0.3:
                    curve_type_summary["ease_in_sharp"] += 1
                elif magnitude < 0.7:
                    curve_type_summary["ease_in_smooth"] += 1
                else:
                    curve_type_summary["ease_in_gentle"] += 1

        return {
            "total_keyframes": total_keyframes,
            "interpolation_distribution": dict(interpolation_types),
            "most_common_interpolation": (
                interpolation_types.most_common(1)[0][0]
                if interpolation_types else "unknown"
            ),
            "animated_transform_properties": Counter(
                animated_properties
            ).most_common(10),
            "average_ease_speed": (
                sum(ease_speeds) / len(ease_speeds)
                if ease_speeds else 0.0
            ),
            "bezier_curve_count": len(bezier_curves),
            "bezier_curves_sample": bezier_curves[:50],
            "curve_type_distribution": dict(curve_type_summary),
            "animated_property_timelines": property_timelines,
        }

    def extract_layer_organization(
        self, report: Dict[str, Any]
    ) -> Dict[str, Any]:
        """提取图层组织模式。

        分析命名规范、层级结构、父子关系等。

        Returns:
            图层组织模式字典
        """
        layer_names: List[str] = []
        parent_relationships: List[Dict[str, str]] = []
        type_distribution: Counter = Counter()
        naming_patterns: Counter = Counter()

        for comp in report.get("compositions", []):
            for layer in comp.get("layers", []):
                name = layer.get("name") or ""
                layer_names.append(name)
                layer_type = layer.get("type", "unknown")
                type_distribution[layer_type] += 1

                # Detect naming patterns
                if name and "_" in name:
                    prefix = name.split("_")[0]
                    naming_patterns[f"prefix:{prefix}"] += 1
                if name and " " in name:
                    first_word = name.split(" ")[0].lower()
                    naming_patterns[f"word:{first_word}"] += 1

                # Parent relationships
                parent = layer.get("parent")
                if parent and name:
                    parent_relationships.append({
                        "child": name,
                        "parent_name": parent.get("name", ""),
                        "comp": comp.get("name", ""),
                    })

        return {
            "total_layers": len(layer_names),
            "type_distribution": dict(type_distribution),
            "parent_relationships": parent_relationships,
            "common_naming_patterns": naming_patterns.most_common(10),
            "has_null_controllers": type_distribution.get("null", 0) > 0,
            "has_adjustment_layers": type_distribution.get("adjustment", 0) > 0,
            "has_precomps": type_distribution.get("precomp", 0) > 0,
        }

    def extract_technique_tags(
        self, report: Dict[str, Any]
    ) -> List[str]:
        """提取技法标签。

        Returns:
            技法标签列表
        """
        return list(report.get("techniques", []))

    def extract_color_patterns(
        self, report: Dict[str, Any]
    ) -> Dict[str, Any]:
        """提取调色模式。

        分析调色效果的组合和使用频率。

        Returns:
            调色模式字典
        """
        color_effects: Counter = Counter()
        color_keywords = {
            "Curves", "Levels", "Hue", "Color Balance", "Tint",
            "LUT", "Lumetri", "Color Finesse", "Gradient",
            "Brightness", "Contrast", "Exposure",
        }

        for comp in report.get("compositions", []):
            for layer in comp.get("layers", []):
                for effect in layer.get("effects", []):
                    name = effect.get("name", "")
                    for kw in color_keywords:
                        if kw.lower() in name.lower():
                            color_effects[name] += 1
                            break

        return {
            "color_effect_count": sum(color_effects.values()),
            "color_effects_used": dict(color_effects),
            "has_lut": any("LUT" in name for name in color_effects),
            "has_curves": any("Curves" in name for name in color_effects),
            "has_lumetri": any("Lumetri" in name for name in color_effects),
        }

    def extract_common_effects(
        self, report: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """提取最常用的效果排名。

        Returns:
            效果列表，按使用频率排序
        """
        effects_by_type = report.get("effectsByType", {})
        sorted_effects = sorted(
            effects_by_type.items(),
            key=lambda x: x[1].get("count", 0),
            reverse=True,
        )

        result: List[Dict[str, Any]] = []
        for name, data in sorted_effects[:30]:
            result.append({
                "name": name,
                "matchName": data.get("matchName", ""),
                "count": data.get("count", 0),
                "category": data.get("category", ""),
                "isPlugin": data.get("isPlugin", False),
            })
        return result

    def extract_plugin_usage(
        self, report: Dict[str, Any]
    ) -> Dict[str, Any]:
        """提取第三方插件使用情况。

        Returns:
            插件使用字典
        """
        effects_by_type = report.get("effectsByType", {})
        plugins: Dict[str, int] = {}
        standard: Dict[str, int] = {}

        for name, data in effects_by_type.items():
            count = data.get("count", 0)
            if data.get("isPlugin", False):
                plugins[name] = count
            else:
                standard[name] = count

        return {
            "plugins": dict(
                sorted(plugins.items(), key=lambda x: x[1], reverse=True)
            ),
            "standard_effects": dict(
                sorted(standard.items(), key=lambda x: x[1], reverse=True)
            ),
            "plugin_count": len(plugins),
            "standard_effect_count": len(standard),
        }
