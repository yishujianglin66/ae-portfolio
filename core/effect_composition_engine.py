"""
effect_composition_engine.py - 效果组合推理引擎
基于知识图谱的效果组合推理、智能推荐、冲突检测
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from effect_knowledge_graph import (
    CATEGORIES,
    EFFECT_KNOWLEDGE_GRAPH,
    EFFECT_RELATIONS,
    EffectNode,
    EffectRelation,
    get_effect_by_match_name,
    get_synergy_effects,
    search_effects,
)


@dataclass
class CompositionResult:
    effects: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    reasoning: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    synergies: list[dict[str, Any]] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class EffectRecommendation:
    match_name: str
    display_name: str
    category: str
    confidence: float
    reason: str
    synergy_score: float = 0.0
    tags: list[str] = field(default_factory=list)


class EffectCompositionEngine:
    """效果组合推理引擎"""

    def __init__(self):
        self.graph = EFFECT_KNOWLEDGE_GRAPH
        self.relations = EFFECT_RELATIONS
        self._build_relation_index()

    def _build_relation_index(self):
        """构建关系索引"""
        self.synergy_index: dict[str, list[EffectRelation]] = {}
        self.mutex_index: dict[str, list[EffectRelation]] = {}
        self.prereq_index: dict[str, list[EffectRelation]] = {}
        self.post_index: dict[str, list[EffectRelation]] = {}

        for rel in self.relations:
            idx_map = {
                "synergy": self.synergy_index,
                "mutex": self.mutex_index,
                "prerequisite": self.prereq_index,
                "post": self.post_index,
            }
            idx = idx_map.get(rel.relation_type)
            if idx is None:
                continue
            idx.setdefault(rel.effect_a, []).append(rel)
            idx.setdefault(rel.effect_b, []).append(rel)

    def compose_from_keywords(
        self,
        keywords: list[str],
        intensity: float = 1.0,
        max_effects: int = 5,
        layer_name: str = "layer_001",
    ) -> CompositionResult:
        """
        基于关键词组合效果
        
        Args:
            keywords: 关键词列表
            intensity: 强度系数 (0.2 ~ 2.0)
            max_effects: 最大效果数量
            layer_name: 图层名
        
        Returns:
            组合结果
        """
        result = CompositionResult()

        if not keywords:
            result.warnings.append("未提供关键词")
            return result

        recommendations = self.recommend_effects(keywords, limit=max_effects * 2)

        if not recommendations:
            result.warnings.append("未找到匹配的效果")
            return result

        selected = self._select_effects(recommendations, max_effects)
        selected_names = [r.match_name for r in selected]

        conflicts = self._detect_conflicts(selected_names)
        if conflicts:
            for conflict in conflicts:
                result.conflicts.append(conflict)
                result.warnings.append(
                    f"效果冲突: {conflict['effect_a']} vs {conflict['effect_b']} - {conflict['description']}"
                )
            selected_names = self._resolve_conflicts(selected_names, conflicts)

        synergies = self._find_synergies(selected_names)
        result.synergies = synergies

        effects_with_settings = []
        total_confidence = 0.0

        for match_name in selected_names:
            effect_node = self.graph.get(match_name)
            if not effect_node:
                continue

            settings = self._generate_default_settings(effect_node, intensity)
            effects_with_settings.append({
                "matchName": match_name,
                "displayName": effect_node.display_name,
                "settings": settings,
                "confidence": effect_node.confidence,
                "category": effect_node.category,
            })
            total_confidence += effect_node.confidence

        ordered_effects = self._order_effects(effects_with_settings)
        result.effects = ordered_effects

        if ordered_effects:
            result.confidence = total_confidence / len(ordered_effects)

        result.reasoning = self._generate_reasoning(selected, synergies, keywords)

        return result

    def recommend_effects(
        self,
        keywords: list[str],
        limit: int = 10,
    ) -> list[EffectRecommendation]:
        """
        推荐效果
        
        Args:
            keywords: 关键词列表
            limit: 返回数量限制
        
        Returns:
            推荐列表
        """
        scores: dict[str, dict[str, Any]] = {}

        for keyword in keywords:
            keyword_lower = keyword.lower()
            matched_effects = search_effects(keyword)
            
            if len(matched_effects) < 3:
                matched_effects = list(self.graph.values())
            
            for effect in matched_effects:
                score = self._calculate_match_score(effect, keyword_lower)
                if score <= 0:
                    continue
                if effect.match_name not in scores:
                    scores[effect.match_name] = {
                        "effect": effect,
                        "total_score": 0.0,
                        "reasons": [],
                    }
                scores[effect.match_name]["total_score"] += score
                scores[effect.match_name]["reasons"].append(
                    f"关键词'{keyword}'匹配度: {score:.2f}"
                )

        for match_name, data in scores.items():
            effect = data["effect"]
            synergy_bonus = self._calculate_synergy_bonus(
                match_name, [n for n in scores.keys() if n != match_name]
            )
            data["total_score"] += synergy_bonus
            if synergy_bonus > 0:
                data["reasons"].append(f"协同加成: +{synergy_bonus:.2f}")

        sorted_results = sorted(
            scores.items(),
            key=lambda x: x[1]["total_score"],
            reverse=True,
        )

        recommendations = []
        for match_name, data in sorted_results[:limit]:
            effect = data["effect"]
            recommendations.append(EffectRecommendation(
                match_name=match_name,
                display_name=effect.display_name,
                category=effect.category,
                confidence=effect.confidence,
                reason="; ".join(data["reasons"][:3]),
                synergy_score=data["total_score"] - effect.confidence,
                tags=effect.tags,
            ))

        return recommendations

    def _calculate_match_score(self, effect: EffectNode, keyword: str) -> float:
        """计算匹配分数"""
        score = 0.0

        keyword_lower = keyword.lower()

        if keyword_lower == effect.display_name.lower():
            score += 2.0
        elif keyword_lower in effect.display_name.lower():
            score += 1.5

        if keyword_lower == effect.match_name.lower():
            score += 1.8
        elif keyword_lower in effect.match_name.lower():
            score += 1.2

        for tag in effect.tags:
            tag_lower = tag.lower()
            if keyword_lower == tag_lower:
                score += 1.5
            elif keyword_lower in tag_lower:
                score += 1.0
            elif tag_lower in keyword_lower:
                score += 0.6

        if keyword_lower in effect.description.lower():
            score += 0.5

        style_keyword_map = {
            "电影": ["胶片", "cinematic", "film", "暗角", "高对比", "暖调"],
            "film": ["胶片", "cinematic", "电影", "vignette", "contrast"],
            "cinematic": ["电影", "胶片", "暗角", "高对比", "film"],
            "胶片": ["电影", "颗粒", "暖调", "film", "cinematic"],
            "高对比": ["contrast", "对比", "亮度", "电影", "胶片"],
            "暗角": ["vignette", "电影", "cinematic", "film"],
            "暖调": ["warm", "暖色", "电影", "胶片", "复古"],
            "复古": ["vintage", "怀旧", "颗粒", "暖调", "褪色"],
            "vintage": ["复古", "怀旧", "颗粒", "老照片"],
            "赛博朋克": ["cyberpunk", "霓虹", "发光", "青品", "高对比"],
            "cyberpunk": ["赛博朋克", "霓虹", "neon", "glow"],
            "霓虹": ["neon", "发光", "赛博朋克", "高饱和"],
            "梦幻": ["dreamy", "柔焦", "发光", "柔和", "朦胧"],
            "dreamy": ["梦幻", "柔焦", "glow", "blur"],
            "垃圾": ["grunge", "粗糙", "颗粒", "脏", "噪波"],
            "grunge": ["垃圾", "粗糙", "noise", "颗粒"],
            "极简": ["minimal", "干净", "柔和", "淡雅", "简约"],
            "minimal": ["极简", "干净", "clean", "简约"],
            "故障": ["glitch", "错位", "像素", "扭曲", "数字"],
            "glitch": ["故障", "错位", "数字", "扭曲"],
        }

        related_keywords = style_keyword_map.get(keyword_lower, [])
        if related_keywords:
            for rk in related_keywords:
                rk_lower = rk.lower()
                for tag in effect.tags:
                    tag_lower = tag.lower()
                    if rk_lower == tag_lower:
                        score += 0.4
                    elif rk_lower in tag_lower:
                        score += 0.25
                    elif tag_lower in rk_lower:
                        score += 0.2
                if rk_lower in effect.display_name.lower():
                    score += 0.3
                if rk_lower in effect.description.lower():
                    score += 0.15

        return score * effect.confidence

    def _calculate_synergy_bonus(
        self, match_name: str, other_names: list[str]
    ) -> float:
        """计算协同加成"""
        bonus = 0.0
        synergies = get_synergy_effects(match_name)
        for synergy in synergies:
            if synergy["match_name"] in other_names:
                bonus += synergy["strength"] * 0.3
        return bonus

    def _select_effects(
        self,
        recommendations: list[EffectRecommendation],
        max_effects: int,
    ) -> list[EffectRecommendation]:
        """选择效果，保证类别多样性"""
        selected = []
        used_categories = set()

        for rec in recommendations:
            if len(selected) >= max_effects:
                break

            if rec.category not in used_categories:
                selected.append(rec)
                used_categories.add(rec.category)
            elif len(selected) < max_effects:
                selected.append(rec)

        return selected

    def _detect_conflicts(self, effect_names: list[str]) -> list[dict[str, Any]]:
        """检测效果冲突"""
        conflicts = []
        for i, name_a in enumerate(effect_names):
            for name_b in effect_names[i + 1:]:
                mutex_rels = self.mutex_index.get(name_a, [])
                for rel in mutex_rels:
                    if (rel.effect_a == name_a and rel.effect_b == name_b) or \
                       (rel.effect_b == name_a and rel.effect_a == name_b):
                        conflicts.append({
                            "effect_a": name_a,
                            "effect_b": name_b,
                            "strength": rel.strength,
                            "description": rel.description,
                        })
                        break
        return conflicts

    def _resolve_conflicts(
        self, effect_names: list[str], conflicts: list[dict[str, Any]]
    ) -> list[str]:
        """解决冲突，保留置信度更高的效果"""
        to_remove = set()
        for conflict in conflicts:
            effect_a = self.graph.get(conflict["effect_a"])
            effect_b = self.graph.get(conflict["effect_b"])
            if not effect_a or not effect_b:
                continue
            if conflict["strength"] >= 0.8:
                if effect_a.confidence >= effect_b.confidence:
                    to_remove.add(conflict["effect_b"])
                else:
                    to_remove.add(conflict["effect_a"])

        return [n for n in effect_names if n not in to_remove]

    def _find_synergies(self, effect_names: list[str]) -> list[dict[str, Any]]:
        """发现协同效果组合"""
        synergies = []
        for i, name_a in enumerate(effect_names):
            for name_b in effect_names[i + 1:]:
                synergy_rels = self.synergy_index.get(name_a, [])
                for rel in synergy_rels:
                    if (rel.effect_a == name_a and rel.effect_b == name_b) or \
                       (rel.effect_b == name_a and rel.effect_a == name_b):
                        synergies.append({
                            "effect_a": name_a,
                            "effect_b": name_b,
                            "strength": rel.strength,
                            "description": rel.description,
                        })
                        break
        return synergies

    def _generate_default_settings(
        self, effect: EffectNode, intensity: float
    ) -> dict[str, Any]:
        """生成默认参数设置"""
        settings = {}

        for param in effect.parameters:
            if param.param_type == "number":
                base_value = param.default if param.default is not None else 0
                if param.intensity_scale and param.intensity_scale > 0:
                    scaled_value = base_value * (
                        1 + (intensity - 1.0) * param.intensity_scale
                    )
                    if param.min_val is not None:
                        scaled_value = max(param.min_val, scaled_value)
                    if param.max_val is not None:
                        scaled_value = min(param.max_val, scaled_value)
                    settings[param.name] = round(scaled_value, 4)
                else:
                    settings[param.name] = base_value
            elif param.param_type == "color":
                settings[param.name] = param.default if param.default else [1, 1, 1]
            elif param.param_type == "enum":
                settings[param.name] = param.default if param.default else (
                    param.enum_values[0] if param.enum_values else ""
                )
            elif param.param_type == "boolean":
                settings[param.name] = 1 if param.default else 0
            elif param.param_type == "point":
                settings[param.name] = param.default if param.default else [0.5, 0.5]
            else:
                settings[param.name] = param.default

        return settings

    def _order_effects(self, effects: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        效果排序 - 按照标准AE效果应用顺序
        
        一般顺序：生成类 → 颜色校正 → 键控/通道 → 风格化 → 扭曲 → 模糊/锐化 → 发光/灯光 → 透视/3D
        """
        category_order = {
            "generate_draw": 0,
            "noise_grain": 1,
            "color_correction": 2,
            "channel_keying": 3,
            "stylize": 4,
            "distort": 5,
            "blur_sharpen": 6,
            "glow_light": 7,
            "perspective_3d": 8,
        }

        def sort_key(effect):
            category = effect.get("category", "")
            return category_order.get(category, 5)

        return sorted(effects, key=sort_key)

    def _generate_reasoning(
        self,
        selected: list[EffectRecommendation],
        synergies: list[dict[str, Any]],
        keywords: list[str],
    ) -> list[str]:
        """生成推理解释"""
        reasoning = []

        reasoning.append(
            f"输入关键词: {', '.join(keywords)}"
        )
        reasoning.append(
            f"选择了 {len(selected)} 个效果，覆盖 {len(set(r.category for r in selected))} 个类别"
        )

        for rec in selected:
            category_name = CATEGORIES.get(rec.category, rec.category)
            reasoning.append(
                f"- {rec.display_name} ({category_name}): {rec.reason}"
            )

        if synergies:
            reasoning.append(f"发现 {len(synergies)} 个协同组合:")
            for synergy in synergies:
                reasoning.append(f"  - {synergy['description']} (强度: {synergy['strength']:.2f})")

        return reasoning

    def get_categories(self) -> dict[str, str]:
        """获取类别列表"""
        return CATEGORIES.copy()

    def get_effects_by_category(self, category: str) -> list[EffectNode]:
        """按类别获取效果"""
        return [e for e in self.graph.values() if e.category == category]

    def analyze_combination(self, effect_names: list[str]) -> dict[str, Any]:
        """分析现有效果组合"""
        synergies = self._find_synergies(effect_names)
        conflicts = self._detect_conflicts(effect_names)

        categories = set()
        total_confidence = 0.0
        for name in effect_names:
            effect = self.graph.get(name)
            if effect:
                categories.add(effect.category)
                total_confidence += effect.confidence

        avg_confidence = total_confidence / len(effect_names) if effect_names else 0

        return {
            "total_effects": len(effect_names),
            "categories_covered": len(categories),
            "categories": list(categories),
            "average_confidence": round(avg_confidence, 4),
            "synergies": synergies,
            "synergy_count": len(synergies),
            "conflicts": conflicts,
            "conflict_count": len(conflicts),
            "recommended_order": self._order_effects([
                {"matchName": n, "category": self.graph[n].category}
                for n in effect_names if n in self.graph
            ]),
        }

    def enhance_combination(
        self,
        effect_names: list[str],
        max_additions: int = 3,
    ) -> dict[str, Any]:
        """增强现有效果组合，推荐添加的效果"""
        suggestions = []
        existing_set = set(effect_names)

        for name in effect_names:
            synergies = get_synergy_effects(name)
            for synergy in synergies:
                if synergy["match_name"] not in existing_set:
                    suggestions.append({
                        "match_name": synergy["match_name"],
                        "display_name": self.graph[synergy["match_name"]].display_name
                        if synergy["match_name"] in self.graph else synergy["match_name"],
                        "reason": synergy["description"],
                        "synergy_strength": synergy["strength"],
                        "paired_with": name,
                    })

        suggestions.sort(key=lambda x: x["synergy_strength"], reverse=True)

        seen = set()
        unique_suggestions = []
        for s in suggestions:
            if s["match_name"] not in seen:
                seen.add(s["match_name"])
                unique_suggestions.append(s)
            if len(unique_suggestions) >= max_additions:
                break

        analysis = self.analyze_combination(effect_names)

        return {
            "current_analysis": analysis,
            "suggestions": unique_suggestions,
            "suggestion_count": len(unique_suggestions),
        }

    def generate_style_combination(
        self,
        style: str,
        intensity: float = 1.0,
        layer_name: str = "layer_001",
    ) -> CompositionResult:
        """
        根据风格名称生成效果组合
        
        支持的风格：cinematic, cyberpunk, vintage, dreamy, neon, grunge, minimal, glitch
        """
        style_recipes = {
            "cinematic": {
                "keywords": ["电影", "胶片", "高对比", "暗角", "暖调"],
                "effects": [
                    "ADBE Brightness & Contrast 2",
                    "ADBE Color Balance",
                    "CC Vignette",
                ],
                "description": "电影感：高对比、暖调、暗角",
            },
            "cyberpunk": {
                "keywords": ["赛博朋克", "霓虹", "青品", "高对比", "发光"],
                "effects": [
                    "ADBE HUE SATURATION",
                    "ADBE Color Balance",
                    "ADBE Glo2",
                    "ADBE Brightness & Contrast 2",
                    "CC Light Rays",
                ],
                "description": "赛博朋克：霓虹色、发光、高饱和",
            },
            "vintage": {
                "keywords": ["复古", "胶片", "暖调", "颗粒", "褪色"],
                "effects": [
                    "ADBE Photo Filter",
                    "ADBE Color Balance",
                    "ADBE Noise",
                    "ADBE Brightness & Contrast 2",
                    "ADBE HUE SATURATION",
                ],
                "description": "复古：暖调、颗粒、褪色感",
            },
            "dreamy": {
                "keywords": ["梦幻", "柔焦", "发光", "柔和", "朦胧"],
                "effects": [
                    "ADBE Gaussian Blur 2",
                    "ADBE Glo2",
                    "ADBE HUE SATURATION",
                    "ADBE Directional Blur",
                ],
                "description": "梦幻：柔焦、发光、朦胧感",
            },
            "neon": {
                "keywords": ["霓虹", "发光", "鲜艳", "高饱和", "色彩"],
                "effects": [
                    "ADBE Glo2",
                    "ADBE HUE SATURATION",
                    "ADBE Color Balance",
                    "CC Light Rays",
                    "ADBE Brightness & Contrast 2",
                ],
                "description": "霓虹：发光、高饱和、鲜艳色彩",
            },
            "grunge": {
                "keywords": ["垃圾", "粗糙", "颗粒", "脏", "噪波"],
                "effects": [
                    "ADBE Noise",
                    "ADBE Roughen Edges",
                    "ADBE Find Edges",
                    "ADBE Brightness & Contrast 2",
                    "ADBE Turbulent Displace",
                ],
                "description": "垃圾风：粗糙、颗粒、噪波",
            },
            "minimal": {
                "keywords": ["极简", "干净", "柔和", "淡雅", "简约"],
                "effects": [
                    "ADBE Brightness & Contrast 2",
                    "ADBE HUE SATURATION",
                    "ADBE Photo Filter",
                    "ADBE Gaussian Blur 2",
                ],
                "description": "极简：干净、柔和、淡雅",
            },
            "glitch": {
                "keywords": ["故障", "错位", "数字", "扭曲", "像素"],
                "effects": [
                    "ADBE Channel Blur",
                    "ADBE Wave Warp",
                    "ADBE Mosaic",
                    "ADBE Turbulent Displace",
                    "ADBE Roughen Edges",
                ],
                "description": "故障风：错位、像素、扭曲",
            },
        }

        recipe = style_recipes.get(style.lower())
        if not recipe:
            result = CompositionResult()
            result.warnings.append(f"未知风格: {style}")
            return result

        effect_list = []
        valid_effect_names = []
        total_confidence = 0.0

        for effect_name in recipe["effects"]:
            effect = self.graph.get(effect_name)
            if effect:
                settings = self._generate_default_settings(effect, intensity)
                effect_list.append({
                    "matchName": effect.match_name,
                    "displayName": effect.display_name,
                    "category": effect.category,
                    "settings": settings,
                    "enabled": True,
                })
                valid_effect_names.append(effect_name)
                total_confidence += effect.confidence

        effect_list = self._order_effects(effect_list)

        synergies = self._find_synergies(valid_effect_names)
        conflicts = self._detect_conflicts(valid_effect_names)

        reasoning = []
        reasoning.append(f"风格: {style} - {recipe['description']}")
        reasoning.append(f"使用 {len(effect_list)} 个效果构建风格")
        for eff in effect_list:
            reasoning.append(f"- {eff['displayName']} ({CATEGORIES.get(eff['category'], eff['category'])})")

        if synergies:
            reasoning.append(f"发现 {len(synergies)} 个协同组合:")
            for synergy in synergies:
                reasoning.append(f"  - {synergy['description']}")

        warnings = []
        if conflicts:
            for conflict in conflicts:
                warnings.append(
                    f"冲突: {conflict['effect_a']} 与 {conflict['effect_b']}: {conflict['description']}"
                )

        avg_confidence = total_confidence / len(effect_list) if effect_list else 0.0

        result = CompositionResult(
            effects=effect_list,
            confidence=round(avg_confidence, 4),
            reasoning=reasoning,
            warnings=warnings,
            synergies=synergies,
            conflicts=conflicts,
        )
        return result
