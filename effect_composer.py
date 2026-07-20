from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from style_template_library import STYLE_TEMPLATES


@dataclass
class EffectSettings:
    effectName: str
    settings: Dict[str, Any]
    intensity_param: str
    intensity_factor: float


@dataclass
class StyleTemplate:
    name: str
    display_name: str
    category: str
    description: str
    keywords: List[str]
    intensity_range: List[float]
    effects: List[EffectSettings]


class EffectComposer:
    def __init__(self):
        self.templates: Dict[str, StyleTemplate] = {}
        self._load_templates()

    def _load_templates(self):
        for name, data in STYLE_TEMPLATES.items():
            effects = []
            for effect_data in data["effects"]:
                effects.append(EffectSettings(
                    effectName=effect_data["effectName"],
                    settings=effect_data["settings"].copy(),
                    intensity_param=effect_data["intensity_param"],
                    intensity_factor=effect_data["intensity_factor"]
                ))
            self.templates[name] = StyleTemplate(
                name=data["name"],
                display_name=data["display_name"],
                category=data["category"],
                description=data["description"],
                keywords=data["keywords"],
                intensity_range=data["intensity_range"],
                effects=effects
            )

    def list_templates(self) -> List[str]:
        return list(self.templates.keys())

    def list_categories(self) -> List[str]:
        categories = set()
        for template in self.templates.values():
            categories.add(template.category)
        return sorted(list(categories))

    def get_template(self, name: str) -> Optional[StyleTemplate]:
        return self.templates.get(name)

    def _clamp_intensity(self, template: StyleTemplate, intensity: float) -> float:
        min_int, max_int = template.intensity_range
        return max(min_int, min(max_int, intensity))

    def _adjust_effect_intensity(self, effect: EffectSettings, intensity: float) -> Dict[str, Any]:
        adjusted_settings = effect.settings.copy()
        base_value = adjusted_settings[effect.intensity_param]
        adjusted_value = base_value + (effect.intensity_factor - base_value) * (intensity - 0.5) * 2
        adjusted_settings[effect.intensity_param] = adjusted_value
        return adjusted_settings

    def compose(self, style_name: str, intensity: float = 1.0, layer_name: str = "layer_001") -> Dict[str, Any]:
        template = self.get_template(style_name)
        if not template:
            raise ValueError(f"Style template '{style_name}' not found")

        clamped_intensity = self._clamp_intensity(template, intensity)

        effects = []
        for effect in template.effects:
            adjusted_settings = self._adjust_effect_intensity(effect, clamped_intensity)
            effects.append({
                "effectName": effect.effectName,
                "settings": adjusted_settings
            })

        return {
            "layer_name": layer_name,
            "style_name": style_name,
            "intensity": clamped_intensity,
            "effects": effects
        }

    def recommend_by_keywords(self, keywords: List[str], limit: int = 5) -> List[Dict[str, Any]]:
        if not keywords:
            return []

        scores = []
        keyword_set_lower = {kw.lower() for kw in keywords}

        for name, template in self.templates.items():
            template_keywords_lower = {kw.lower() for kw in template.keywords}
            match_count = len(keyword_set_lower & template_keywords_lower)

            for kw in keyword_set_lower:
                for tkw in template_keywords_lower:
                    if kw in tkw or tkw in kw:
                        match_count += 0.5

            if match_count > 0:
                scores.append({
                    "name": name,
                    "display_name": template.display_name,
                    "category": template.category,
                    "description": template.description,
                    "match_score": match_count
                })

        scores.sort(key=lambda x: x["match_score"], reverse=True)
        return scores[:limit]

    def mix_styles(self, style_names: List[str], ratios: Optional[List[float]] = None, layer_name: str = "layer_001") -> Dict[str, Any]:
        if not style_names:
            raise ValueError("At least one style name is required")

        if ratios is None:
            ratios = [1.0 / len(style_names)] * len(style_names)

        if len(ratios) != len(style_names):
            raise ValueError("Number of ratios must match number of style names")

        total_ratio = sum(ratios)
        if total_ratio == 0:
            raise ValueError("Sum of ratios cannot be zero")
        normalized_ratios = [r / total_ratio for r in ratios]

        all_effects: Dict[str, Dict[str, Any]] = {}
        intensity_param_map: Dict[str, str] = {}

        for style_name, ratio in zip(style_names, normalized_ratios):
            template = self.get_template(style_name)
            if not template:
                raise ValueError(f"Style template '{style_name}' not found")

            for effect in template.effects:
                effect_name = effect.effectName
                if effect_name not in all_effects:
                    all_effects[effect_name] = {}
                    intensity_param_map[effect_name] = effect.intensity_param

                for param, value in effect.settings.items():
                    if param in all_effects[effect_name]:
                        if isinstance(value, (int, float)):
                            all_effects[effect_name][param] += value * ratio
                        elif isinstance(value, list) and all(isinstance(v, (int, float)) for v in value):
                            if param not in all_effects[effect_name]:
                                all_effects[effect_name][param] = [v * ratio for v in value]
                            else:
                                existing = all_effects[effect_name][param]
                                all_effects[effect_name][param] = [
                                    existing[i] + value[i] * ratio for i in range(min(len(existing), len(value)))
                                ]
                        else:
                            if ratio >= 0.5:
                                all_effects[effect_name][param] = value
                    else:
                        if isinstance(value, (int, float)):
                            all_effects[effect_name][param] = value * ratio
                        elif isinstance(value, list) and all(isinstance(v, (int, float)) for v in value):
                            all_effects[effect_name][param] = [v * ratio for v in value]
                        else:
                            all_effects[effect_name][param] = value

        effects_list = []
        for effect_name, settings in all_effects.items():
            effects_list.append({
                "effectName": effect_name,
                "settings": settings
            })

        return {
            "layer_name": layer_name,
            "style_names": style_names,
            "ratios": normalized_ratios,
            "effects": effects_list
        }
