from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Tuple, Callable
from pathlib import Path
import re
import json
import os
import random
import time
from collections import defaultdict

# 关键词->matchName 映射从 effect_registry 统一导入（单一数据源）
from effects.effect_registry import KEYWORD_TO_EFFECT_MAP


@dataclass
class ParameterContext:
    effect_name: Optional[str] = None
    layer_type: Optional[str] = None
    style_name: Optional[str] = None
    color_temperature: Optional[str] = None
    intensity: float = 0.5
    adjust_direction: Optional[str] = None
    adjust_amount: Optional[str] = None


@dataclass
class OptimizedParameters:
    effect_name: str
    settings: Dict[str, Any]
    confidence: float
    adjustments: List[Dict[str, Any]] = field(default_factory=list)


EFFECT_PARAMETER_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "ADBE Gaussian Blur 2": {
        "defaults": {"Blurriness": 20.0},
        "intensity_scale": {"Blurriness": 50.0},
        "warm_temperature": {},
        "cool_temperature": {},
    },
    "ADBE Fast Blur": {
        "defaults": {"Blurriness": 10.0},
        "intensity_scale": {"Blurriness": 30.0},
        "warm_temperature": {},
        "cool_temperature": {},
    },
    "ADBE Glo2": {
        "defaults": {"Glow Radius": 20.0, "Glow Intensity": 0.8},
        "intensity_scale": {"Glow Radius": 50.0, "Glow Intensity": 2.0},
        "warm_temperature": {"Glow Color": [1.0, 0.5, 0.0]},
        "cool_temperature": {"Glow Color": [0.0, 0.5, 1.0]},
    },
    "ADBE Inner Glow": {
        "defaults": {"Glow Radius": 10.0, "Glow Intensity": 0.6},
        "intensity_scale": {"Glow Radius": 30.0, "Glow Intensity": 1.5},
        "warm_temperature": {"Glow Color": [1.0, 0.8, 0.0]},
        "cool_temperature": {"Glow Color": [0.0, 0.8, 1.0]},
    },
    "ADBE Starglow": {
        "defaults": {"Streak Length": 20.0, "Boost Light": 1.0},
        "intensity_scale": {"Streak Length": 50.0, "Boost Light": 3.0},
        "warm_temperature": {"Input Phase": 0.0},
        "cool_temperature": {"Input Phase": 0.5},
    },
    "ADBE Fractal Noise": {
        "defaults": {"Evolution": 0.0, "Scale": 100.0},
        "intensity_scale": {"Scale": 200.0},
        "warm_temperature": {},
        "cool_temperature": {},
    },
    "ADBE Ramp": {
        "defaults": {"Start Color": [1.0, 0.5, 0.0], "End Color": [0.0, 0.5, 1.0]},
        "intensity_scale": {},
        "warm_temperature": {"Start Color": [1.0, 0.7, 0.3], "End Color": [0.5, 0.3, 0.0]},
        "cool_temperature": {"Start Color": [0.3, 0.7, 1.0], "End Color": [0.0, 0.3, 0.5]},
    },
    "ADBE Keylight": {
        "defaults": {"Screen Color": [0.0, 0.8, 0.0], "Screen Gain": 50.0},
        "intensity_scale": {"Screen Gain": 100.0},
        "warm_temperature": {},
        "cool_temperature": {},
    },
    "ADBE Color Key": {
        "defaults": {"Color To Key": [0.0, 0.8, 0.0], "Tolerance": 20.0},
        "intensity_scale": {"Tolerance": 50.0},
        "warm_temperature": {"Color To Key": [0.5, 0.8, 0.0]},
        "cool_temperature": {"Color To Key": [0.0, 0.8, 0.5]},
    },
    "ADBE Turbulent Displace": {
        "defaults": {"Amount": 20.0, "Size": 50.0},
        "intensity_scale": {"Amount": 100.0, "Size": 100.0},
        "warm_temperature": {},
        "cool_temperature": {},
    },
    "ADBE Wave Warp": {
        "defaults": {"Wave Height": 20.0, "Wave Width": 100.0},
        "intensity_scale": {"Wave Height": 100.0},
        "warm_temperature": {},
        "cool_temperature": {},
    },
    "ADBE Curves": {
        "defaults": {},
        "intensity_scale": {},
        "warm_temperature": {},
        "cool_temperature": {},
    },
    "ADBE Colorista": {
        "defaults": {"Saturation": 0.0, "Contrast": 0.0},
        "intensity_scale": {"Saturation": 50.0, "Contrast": 30.0},
        "warm_temperature": {"Temperature": 20.0},
        "cool_temperature": {"Temperature": -20.0},
    },
    "ADBE Particle Playground": {
        "defaults": {"Birth Rate": 20.0, "Speed": 10.0},
        "intensity_scale": {"Birth Rate": 100.0, "Speed": 50.0},
        "warm_temperature": {"Color Map": ["fromBlack", "toRed"]},
        "cool_temperature": {"Color Map": ["fromBlack", "toBlue"]},
    },
    "ADBE Camera Lens Blur": {
        "defaults": {"Blur Radius": 15.0, "Iris Radius": 50.0},
        "intensity_scale": {"Blur Radius": 50.0},
        "warm_temperature": {},
        "cool_temperature": {},
    },
}


STYLE_PARAMETER_OVERRIDES: Dict[str, List[Tuple[str, Dict[str, Any]]]] = {
    "赛博朋克": [
        ("ADBE Curves", {"preset": "cyberpunk_cyan_magenta"}),
        ("ADBE Glo2", {"Glow Radius": 30.0, "Glow Intensity": 1.2}),
        ("ADBE Turbulent Displace", {"Amount": 15.0}),
    ],
    "cyberpunk": [
        ("ADBE Curves", {"preset": "cyberpunk_cyan_magenta"}),
        ("ADBE Glo2", {"Glow Radius": 30.0, "Glow Intensity": 1.2}),
        ("ADBE Turbulent Displace", {"Amount": 15.0}),
    ],
    "电影感": [
        ("ADBE Curves", {"preset": "cinematic_teal_orange"}),
        ("ADBE Glo2", {"Glow Radius": 25.0, "Glow Intensity": 0.9}),
        ("ADBE Camera Lens Blur", {"Blur Radius": 20.0}),
    ],
    "cinematic": [
        ("ADBE Curves", {"preset": "cinematic_teal_orange"}),
        ("ADBE Glo2", {"Glow Radius": 25.0, "Glow Intensity": 0.9}),
        ("ADBE Camera Lens Blur", {"Blur Radius": 20.0}),
    ],
    "梦幻": [
        ("ADBE Gaussian Blur 2", {"Blurriness": 15.0}),
        ("ADBE Glo2", {"Glow Radius": 40.0, "Glow Intensity": 0.7}),
        ("ADBE Starglow", {"Streak Length": 30.0}),
    ],
    "dreamy": [
        ("ADBE Gaussian Blur 2", {"Blurriness": 15.0}),
        ("ADBE Glo2", {"Glow Radius": 40.0, "Glow Intensity": 0.7}),
        ("ADBE Starglow", {"Streak Length": 30.0}),
    ],
    "复古": [
        ("ADBE Colorista", {"Saturation": -20.0, "Temperature": 15.0}),
        ("ADBE Gaussian Blur 2", {"Blurriness": 5.0}),
    ],
    "vintage": [
        ("ADBE Colorista", {"Saturation": -20.0, "Temperature": 15.0}),
        ("ADBE Gaussian Blur 2", {"Blurriness": 5.0}),
    ],
    "霓虹": [
        ("ADBE Glo2", {"Glow Radius": 35.0, "Glow Intensity": 1.5}),
        ("ADBE Curves", {"preset": "neon_cyan_magenta"}),
    ],
    "neon": [
        ("ADBE Glo2", {"Glow Radius": 35.0, "Glow Intensity": 1.5}),
        ("ADBE Curves", {"preset": "neon_cyan_magenta"}),
    ],
}


class ParameterOptimizer:
    def optimize(self, context: ParameterContext) -> OptimizedParameters:
        effect_name = self._resolve_effect_name(context)
        if not effect_name:
            return OptimizedParameters(
                effect_name="",
                settings={},
                confidence=0.0,
                adjustments=[],
            )

        template = EFFECT_PARAMETER_TEMPLATES.get(effect_name, {})
        settings = dict(template.get("defaults", {}))

        adjustments = []

        if context.intensity != 0.5:
            intensity_adjustments = self._apply_intensity(settings, template, context.intensity)
            adjustments.extend(intensity_adjustments)

        if context.color_temperature:
            temp_adjustments = self._apply_color_temperature(settings, template, context.color_temperature)
            adjustments.extend(temp_adjustments)

        if context.style_name:
            style_adjustments = self._apply_style_overrides(settings, effect_name, context.style_name)
            adjustments.extend(style_adjustments)

        if context.adjust_direction and context.adjust_amount:
            adjust_adjustments = self._apply_adjustment(settings, context.adjust_direction, context.adjust_amount)
            adjustments.extend(adjust_adjustments)

        confidence = self._calculate_confidence(context, effect_name)

        return OptimizedParameters(
            effect_name=effect_name,
            settings=settings,
            confidence=confidence,
            adjustments=adjustments,
        )

    def optimize_enhanced(self, context: ParameterContext) -> OptimizedParameters:
        """
        LLM 增强版参数优化 — 先用本地规则，LLM 可用时补充建议
        失败时自动降级为纯本地优化

        策略：
          1. 查记忆系统是否有相似效果的经验
          2. 本地规则优化（optimize）
          3. LLM 不可用时直接返回本地结果
          4. LLM 增强参数建议（仅补充，不覆盖本地约束）
          5. 记录到记忆系统
        """
        import asyncio
        import json as _json

        # 1. 本地规则优化
        local_result = self.optimize(context)

        # 2. 尝试导入 LLM 网关和记忆系统
        try:
            from core.llm_gateway import llm_gateway, TaskType
            from core.memory_store import memory_store
        except ImportError:
            return local_result

        # 3. 查记忆系统
        mem_key = f"{context.effect_name}:{context.style_name}:{context.intensity}"
        experiences = memory_store.get_experience(
            category="param_optimize",
            task_keyword=mem_key[:50],
            limit=2,
        )
        if experiences and experiences[0].confidence > 0.85:
            exp = experiences[0]
            cached = exp.content.get("optimized", {})
            if cached.get("settings"):
                return OptimizedParameters(
                    effect_name=local_result.effect_name,
                    settings=cached["settings"],
                    confidence=min(exp.confidence, 0.95),
                    adjustments=cached.get("adjustments", local_result.adjustments),
                )

        # 4. LLM 不可用时降级
        if not llm_gateway.is_available():
            return local_result

        # 5. LLM 增强参数建议
        try:
            prompt = (
                f"效果: {local_result.effect_name}\n"
                f"当前参数: {_json.dumps(local_result.settings, ensure_ascii=False)}\n"
                f"风格: {context.style_name or '默认'}\n"
                f"强度: {context.intensity}\n"
                f"请返回JSON: {{\"suggestions\":{{\"参数名\":值}},"
                f"\"reason\":\"优化原因\"}}"
            )
            result = asyncio.run(llm_gateway.chat_with_routing(
                message=prompt,
                task_type=TaskType.PARAMETER_OPTIMIZATION,
                system_prompt=(
                    "你是AE效果参数优化专家。"
                    "基于当前参数和风格，提供额外优化建议。"
                    "返回JSON格式: "
                    '{"suggestions":{"参数名":值},"reason":"原因"}'
                ),
            ))

            if result.success and result.content:
                import re as _re
                match = _re.search(r'\{[^{}]*"suggestions"[^{}]*\}', result.content, _re.DOTALL)
                if match:
                    parsed = _json.loads(match.group(0))
                    suggestions = parsed.get("suggestions", {})

                    # 合并建议（仅补充，不覆盖本地约束已设置的值）
                    merged_settings = dict(local_result.settings)
                    extra_adjustments = []
                    for param, value in suggestions.items():
                        if param not in merged_settings:
                            merged_settings[param] = value
                            extra_adjustments.append({
                                "parameter": param,
                                "old_value": None,
                                "new_value": value,
                                "reason": f"LLM 建议: {parsed.get('reason', '')}",
                            })

                    enhanced = OptimizedParameters(
                        effect_name=local_result.effect_name,
                        settings=merged_settings,
                        confidence=min(local_result.confidence + 0.1, 0.98),
                        adjustments=local_result.adjustments + extra_adjustments,
                    )

                    # 6. 记录到记忆系统
                    memory_store.remember(
                        category="param_optimize",
                        key=mem_key[:50],
                        content={
                            "optimized": {
                                "settings": enhanced.settings,
                                "adjustments": enhanced.adjustments,
                            }
                        },
                        tags=[local_result.effect_name, context.style_name or ""],
                        confidence=enhanced.confidence,
                    )
                    return enhanced
        except Exception:
            # LLM 增强失败，返回本地结果
            pass

        return local_result

    def _resolve_effect_name(self, context: ParameterContext) -> Optional[str]:
        if context.effect_name:
            normalized = context.effect_name.lower()
            if normalized in KEYWORD_TO_EFFECT_MAP:
                return KEYWORD_TO_EFFECT_MAP[normalized]
            for keyword, effect in KEYWORD_TO_EFFECT_MAP.items():
                if keyword.lower() in normalized:
                    return effect
            return context.effect_name

        if context.style_name:
            recipe_overrides = STYLE_PARAMETER_OVERRIDES.get(context.style_name.lower())
            if recipe_overrides:
                return recipe_overrides[0][0]

        return None

    def _apply_intensity(self, settings: Dict[str, Any], template: Dict[str, Any], intensity: float) -> List[Dict[str, Any]]:
        adjustments = []
        scale = template.get("intensity_scale", {})
        for param, max_value in scale.items():
            if param in settings:
                base_value = settings[param]
                scaled_value = base_value * (0.5 + intensity * 1.0)
                settings[param] = min(scaled_value, max_value)
                adjustments.append({
                    "parameter": param,
                    "from": base_value,
                    "to": settings[param],
                    "reason": f"intensity={intensity}",
                })
        return adjustments

    def _apply_color_temperature(self, settings: Dict[str, Any], template: Dict[str, Any], temperature: str) -> List[Dict[str, Any]]:
        adjustments = []
        temp_settings = {}
        if temperature.lower() == "warm" or temperature == "暖色":
            temp_settings = template.get("warm_temperature", {})
        elif temperature.lower() == "cool" or temperature == "冷色":
            temp_settings = template.get("cool_temperature", {})

        for param, value in temp_settings.items():
            if param in settings:
                adjustments.append({
                    "parameter": param,
                    "from": settings[param],
                    "to": value,
                    "reason": f"temperature={temperature}",
                })
            settings[param] = value

        return adjustments

    def _apply_style_overrides(self, settings: Dict[str, Any], effect_name: str, style_name: str) -> List[Dict[str, Any]]:
        adjustments = []
        overrides = STYLE_PARAMETER_OVERRIDES.get(style_name.lower())
        if overrides:
            for eff_name, params in overrides:
                if eff_name == effect_name:
                    for param, value in params.items():
                        if param in settings:
                            adjustments.append({
                                "parameter": param,
                                "from": settings[param],
                                "to": value,
                                "reason": f"style={style_name}",
                            })
                        settings[param] = value
        return adjustments

    def _apply_adjustment(self, settings: Dict[str, Any], direction: str, amount: str) -> List[Dict[str, Any]]:
        adjustments = []
        amount_value = self._parse_amount(amount)

        for param in settings.keys():
            base_value = settings[param]
            if isinstance(base_value, (int, float)):
                if direction == "increase" or direction == "调大" or direction == "调高":
                    settings[param] = base_value * (1 + amount_value)
                elif direction == "decrease" or direction == "调小" or direction == "调低":
                    settings[param] = base_value * (1 - amount_value)
                elif direction == "set":
                    try:
                        settings[param] = float(amount)
                    except ValueError:
                        pass

                adjustments.append({
                    "parameter": param,
                    "from": base_value,
                    "to": settings[param],
                    "reason": f"{direction} {amount}",
                })

        return adjustments

    def _parse_amount(self, amount: str) -> float:
        m = re.match(r"(\d+(?:\.\d+)?)(%?)", amount)
        if m:
            val = float(m.group(1))
            if m.group(2) == "%":
                return val / 100
            return val / 100 if val > 1 else val

        if amount in ["一点", "稍微", "略微"]:
            return 0.1
        if amount in ["一些", "适中", "中等"]:
            return 0.3
        if amount in ["很多", "强烈"]:
            return 0.5

        return 0.3

    def _calculate_confidence(self, context: ParameterContext, effect_name: str) -> float:
        score = 0.5

        if context.effect_name:
            score += 0.2
        if effect_name in EFFECT_PARAMETER_TEMPLATES:
            score += 0.15
        if context.style_name:
            score += 0.1
        if context.color_temperature:
            score += 0.05

        return min(score, 1.0)

    def suggest_effects_for_style(self, style_name: str) -> List[Tuple[str, Dict[str, Any]]]:
        return STYLE_PARAMETER_OVERRIDES.get(style_name.lower(), [])


# ============================================================================
# 反馈驱动的参数优化系统
# ============================================================================

@dataclass
class FeedbackRecord:
    """参数反馈记录"""
    record_id: str
    effect_name: str
    style_name: Optional[str]
    parameters: Dict[str, Any]
    rating: float  # 0.0 - 1.0 用户评分
    adjustment: Optional[Dict[str, Any]] = None  # 用户手动调整后的参数
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


class FeedbackStore:
    """反馈存储器 - 持久化到磁盘，支持按效果/风格查询"""

    def __init__(self, storage_path: Optional[str] = None):
        if storage_path is None:
            storage_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                ".cache",
                "param_feedback.json"
            )
        self._storage_path = storage_path
        self._records: List[FeedbackRecord] = []
        self._load()

    def _load(self):
        """从磁盘加载反馈记录"""
        try:
            if os.path.isfile(self._storage_path):
                with open(self._storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._records = [
                    FeedbackRecord(**rec) for rec in data.get("records", [])
                ]
        except (OSError, json.JSONDecodeError, TypeError):
            self._records = []

    def _save(self):
        """保存反馈记录到磁盘"""
        try:
            os.makedirs(os.path.dirname(self._storage_path), exist_ok=True)
            data = {
                "version": "1.0",
                "updated_at": time.time(),
                "records": [
                    {
                        "record_id": r.record_id,
                        "effect_name": r.effect_name,
                        "style_name": r.style_name,
                        "parameters": r.parameters,
                        "rating": r.rating,
                        "adjustment": r.adjustment,
                        "timestamp": r.timestamp,
                        "metadata": r.metadata,
                    }
                    for r in self._records
                ]
            }
            with open(self._storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def add(self, record: FeedbackRecord):
        """添加一条反馈记录"""
        self._records.append(record)
        self._save()

    def query(
        self,
        effect_name: Optional[str] = None,
        style_name: Optional[str] = None,
        min_rating: float = 0.0,
        limit: int = 100,
    ) -> List[FeedbackRecord]:
        """查询反馈记录"""
        results = self._records
        if effect_name:
            results = [r for r in results if r.effect_name == effect_name]
        if style_name:
            results = [r for r in results if r.style_name == style_name]
        if min_rating > 0:
            results = [r for r in results if r.rating >= min_rating]
        # 按时间倒序
        results = sorted(results, key=lambda r: r.timestamp, reverse=True)
        return results[:limit]

    def get_best_params(
        self,
        effect_name: str,
        style_name: Optional[str] = None,
        min_rating: float = 0.7,
    ) -> Optional[Dict[str, Any]]:
        """获取评分最高的参数组合"""
        records = self.query(
            effect_name=effect_name,
            style_name=style_name,
            min_rating=min_rating,
            limit=10,
        )
        if not records:
            return None
        # 按评分加权平均
        total_weight = sum(r.rating for r in records)
        if total_weight <= 0:
            return None

        # 收集所有数值参数
        param_values: Dict[str, List[Tuple[float, float]]] = defaultdict(list)
        for rec in records:
            params = rec.adjustment if rec.adjustment else rec.parameters
            for param, value in params.items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    param_values[param].append((float(value), rec.rating))

        best_params = {}
        for param, values_weights in param_values.items():
            weighted_sum = sum(v * w for v, w in values_weights)
            total_w = sum(w for _, w in values_weights)
            if total_w > 0:
                best_params[param] = weighted_sum / total_w

        return best_params if best_params else None

    @property
    def count(self) -> int:
        return len(self._records)


class ParameterTuner:
    """参数调优器 - 支持多种探索策略

    策略:
    - random: 随机搜索（适合初始探索）
    - grid: 网格搜索（适合精细调优）
    - bayesian: 贝叶斯优化（基于历史反馈的智能探索）
    - feedback_weighted: 基于历史反馈的加权平均
    """

    def __init__(
        self,
        feedback_store: Optional[FeedbackStore] = None,
        exploration_rate: float = 0.3,
    ):
        self._feedback = feedback_store or FeedbackStore()
        self._exploration_rate = exploration_rate

    def suggest(
        self,
        effect_name: str,
        base_params: Dict[str, Any],
        style_name: Optional[str] = None,
        strategy: str = "bayesian",
        param_ranges: Optional[Dict[str, Tuple[float, float]]] = None,
    ) -> Dict[str, Any]:
        """生成下一组探索参数

        Args:
            effect_name: 效果名称
            base_params: 基础参数（当前值）
            style_name: 风格名称
            strategy: 探索策略 (random/grid/bayesian/feedback_weighted)
            param_ranges: 参数范围 {param_name: (min, max)}

        Returns:
            建议的新参数字典
        """
        if param_ranges is None:
            param_ranges = self._infer_ranges(base_params)

        # 按探索率决定是探索还是利用
        if random.random() < self._exploration_rate:
            return self._explore(base_params, param_ranges, strategy)
        else:
            return self._exploit(effect_name, base_params, style_name, param_ranges)

    def _explore(
        self,
        base_params: Dict[str, Any],
        param_ranges: Dict[str, Tuple[float, float]],
        strategy: str,
    ) -> Dict[str, Any]:
        """探索阶段 - 生成新参数组合"""
        new_params = dict(base_params)

        if strategy == "random":
            # 随机调整数值参数
            for param, (min_val, max_val) in param_ranges.items():
                if param in new_params and isinstance(new_params[param], (int, float)):
                    new_params[param] = random.uniform(min_val, max_val)
        elif strategy == "grid":
            # 网格搜索：按固定步长调整
            step = 0.2
            for param, (min_val, max_val) in param_ranges.items():
                if param in new_params and isinstance(new_params[param], (int, float)):
                    current = new_params[param]
                    range_size = max_val - min_val
                    delta = range_size * step * random.choice([-1, 1])
                    new_val = current + delta
                    new_params[param] = max(min_val, min(max_val, new_val))
        elif strategy == "bayesian":
            # 简化版贝叶斯：基于高斯扰动，越不确定探索越大
            for param, (min_val, max_val) in param_ranges.items():
                if param in new_params and isinstance(new_params[param], (int, float)):
                    current = new_params[param]
                    range_size = max_val - min_val
                    noise = random.gauss(0, range_size * 0.15)
                    new_val = current + noise
                    new_params[param] = max(min_val, min(max_val, new_val))
        else:  # feedback_weighted fallback
            pass

        return new_params

    def _exploit(
        self,
        effect_name: str,
        base_params: Dict[str, Any],
        style_name: Optional[str],
        param_ranges: Dict[str, Tuple[float, float]],
    ) -> Dict[str, Any]:
        """利用阶段 - 使用历史最优参数"""
        best = self._feedback.get_best_params(effect_name, style_name)
        if best:
            # 混合：基础参数 30% + 历史最优 70%
            merged = dict(base_params)
            for param, value in best.items():
                if param in merged and isinstance(merged[param], (int, float)):
                    min_val, max_val = param_ranges.get(
                        param, (value * 0.5, value * 1.5)
                    )
                    merged[param] = merged[param] * 0.3 + value * 0.7
                    merged[param] = max(min_val, min(max_val, merged[param]))
                elif param not in merged:
                    merged[param] = value
            return merged
        return base_params

    def _infer_ranges(
        self, params: Dict[str, Any]
    ) -> Dict[str, Tuple[float, float]]:
        """从当前参数推断合理范围"""
        ranges = {}
        for param, value in params.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                if value == 0:
                    ranges[param] = (0.0, 100.0)
                elif value > 0:
                    ranges[param] = (value * 0.1, value * 2.0)
                else:
                    ranges[param] = (value * 2.0, value * 0.1)
        return ranges

    def record_feedback(
        self,
        effect_name: str,
        parameters: Dict[str, Any],
        rating: float,
        style_name: Optional[str] = None,
        adjustment: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """记录参数反馈"""
        record = FeedbackRecord(
            record_id=f"fb_{int(time.time() * 1000)}_{random.randint(1000, 9999)}",
            effect_name=effect_name,
            style_name=style_name,
            parameters=parameters,
            rating=max(0.0, min(1.0, rating)),
            adjustment=adjustment,
            metadata=metadata or {},
        )
        self._feedback.add(record)


class StylePresetEvolver:
    """风格预设进化器 - 根据用户反馈迭代优化风格预设

    功能:
    - 收集特定风格的所有参数反馈
    - 定期生成进化后的风格预设
    - 保留多个版本，支持回滚
    """

    def __init__(
        self,
        feedback_store: Optional[FeedbackStore] = None,
        preset_dir: Optional[str] = None,
    ):
        self._feedback = feedback_store or FeedbackStore()
        if preset_dir is None:
            preset_dir = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "config",
                "evolved_presets"
            )
        self._preset_dir = preset_dir
        self._generations: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._load_generations()

    def _load_generations(self):
        """加载历史进化版本"""
        try:
            if os.path.isdir(self._preset_dir):
                for fname in os.listdir(self._preset_dir):
                    if fname.endswith(".json"):
                        style_name = fname.replace(".json", "")
                        fpath = os.path.join(self._preset_dir, fname)
                        with open(fpath, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        if isinstance(data, list):
                            self._generations[style_name] = data
        except (OSError, json.JSONDecodeError):
            pass

    def _save_generation(self, style_name: str):
        """保存风格的进化历史"""
        try:
            os.makedirs(self._preset_dir, exist_ok=True)
            fpath = os.path.join(self._preset_dir, f"{style_name}.json")
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(self._generations[style_name], f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def evolve_style(
        self,
        style_name: str,
        base_preset: List[Tuple[str, Dict[str, Any]]],
        min_feedback: int = 5,
    ) -> Optional[List[Tuple[str, Dict[str, Any]]]]:
        """基于反馈进化风格预设

        Args:
            style_name: 风格名称
            base_preset: 基础预设 [(effect_match_name, params_dict), ...]
            min_feedback: 最少反馈数量才触发进化

        Returns:
            进化后的预设列表，或 None 表示反馈不足
        """
        evolved: List[Tuple[str, Dict[str, Any]]] = []
        total_feedback = 0

        for effect_name, base_params in base_preset:
            best = self._feedback.get_best_params(effect_name, style_name, min_rating=0.6)
            feedback_count = len(
                self._feedback.query(effect_name=effect_name, style_name=style_name)
            )
            total_feedback += feedback_count

            if best and feedback_count >= min_feedback:
                # 混合基础参数和最优参数（70% 最优 + 30% 基础）
                new_params = dict(base_params)
                for param, opt_value in best.items():
                    if param in new_params and isinstance(new_params[param], (int, float)):
                        new_params[param] = (
                            new_params[param] * 0.3 + opt_value * 0.7
                        )
                    elif param not in new_params:
                        new_params[param] = opt_value
                evolved.append((effect_name, new_params))
            else:
                evolved.append((effect_name, dict(base_params)))

        if total_feedback < min_feedback:
            return None

        # 记录进化版本
        generation_data = {
            "generation": len(self._generations[style_name]) + 1,
            "timestamp": time.time(),
            "feedback_count": total_feedback,
            "preset": [
                {"effect": e, "params": p} for e, p in evolved
            ],
        }
        self._generations[style_name].append(generation_data)
        self._save_generation(style_name)

        return evolved

    def get_latest_generation(self, style_name: str) -> Optional[Dict[str, Any]]:
        """获取最新一代预设"""
        gens = self._generations.get(style_name, [])
        if gens:
            return gens[-1]
        return None

    def get_generation_count(self, style_name: str) -> int:
        return len(self._generations.get(style_name, []))


# 增强版参数优化器
class EnhancedParameterOptimizer(ParameterOptimizer):
    """增强版参数优化器 - 集成反馈系统和自动调优

    在原有基础上增加:
    - 基于用户反馈的参数优化
    - 多策略参数探索
    - 风格预设自动进化
    - 推荐置信度动态调整
    """

    def __init__(self):
        super().__init__()
        self._tuner = ParameterTuner()
        self._evolver = StylePresetEvolver()

    @property
    def tuner(self) -> ParameterTuner:
        return self._tuner

    @property
    def evolver(self) -> StylePresetEvolver:
        return self._evolver

    def optimize_with_feedback(
        self,
        context: ParameterContext,
        use_feedback: bool = True,
    ) -> OptimizedParameters:
        """优化参数时考虑历史反馈

        先执行基础优化，再用历史高评分参数微调。
        """
        base_result = self.optimize(context)

        if not use_feedback or not context.effect_name:
            return base_result

        best_params = self._tuner._feedback.get_best_params(
            effect_name=context.effect_name,
            style_name=context.style_name,
            min_rating=0.7,
        )

        if not best_params:
            return base_result

        # 混合：基础 60% + 反馈最优 40%
        merged_settings = dict(base_result.settings)
        extra_adjustments = []
        for param, opt_value in best_params.items():
            if param in merged_settings and isinstance(merged_settings[param], (int, float)):
                old_value = merged_settings[param]
                merged_settings[param] = old_value * 0.6 + opt_value * 0.4
                extra_adjustments.append({
                    "parameter": param,
                    "from": old_value,
                    "to": merged_settings[param],
                    "reason": "feedback_weighted",
                })

        if extra_adjustments:
            return OptimizedParameters(
                effect_name=base_result.effect_name,
                settings=merged_settings,
                confidence=min(base_result.confidence + 0.05, 0.99),
                adjustments=base_result.adjustments + extra_adjustments,
            )

        return base_result

    def suggest_next_trial(
        self,
        context: ParameterContext,
        current_params: Dict[str, Any],
        strategy: str = "bayesian",
    ) -> Dict[str, Any]:
        """建议下一组试验参数（用于 A/B 测试）"""
        effect_name = self._resolve_effect_name(context)
        if not effect_name:
            return current_params
        return self._tuner.suggest(
            effect_name=effect_name,
            base_params=current_params,
            style_name=context.style_name,
            strategy=strategy,
        )

    def record_feedback(
        self,
        effect_name: str,
        parameters: Dict[str, Any],
        rating: float,
        style_name: Optional[str] = None,
        adjustment: Optional[Dict[str, Any]] = None,
    ):
        """记录用户对参数的反馈"""
        self._tuner.record_feedback(
            effect_name=effect_name,
            parameters=parameters,
            rating=rating,
            style_name=style_name,
            adjustment=adjustment,
        )

    def evolve_style_preset(
        self,
        style_name: str,
        min_feedback: int = 5,
    ) -> Optional[List[Tuple[str, Dict[str, Any]]]]:
        """进化指定风格的预设"""
        base_preset = self.suggest_effects_for_style(style_name)
        if not base_preset:
            return None
        return self._evolver.evolve_style(
            style_name=style_name,
            base_preset=base_preset,
            min_feedback=min_feedback,
        )


parameter_optimizer = ParameterOptimizer()
enhanced_optimizer = EnhancedParameterOptimizer()
