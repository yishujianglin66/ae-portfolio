"""能力注册表反馈闭环 — 记录管线运行结果，驱动预设/字体/调色自适应优化。

核心机制：
1. 每次管线运行后，将使用的预设、字体、调色风格及评测分数写入注册表
2. 使用指数移动平均（EMA）更新每种能力的历史得分
3. 提供基于历史数据的预设推荐权重，让高效预设被更频繁选择
4. 支持预设覆盖率统计，确保 14 种预设被充分多样化使用
"""

import json
import os
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# 项目根目录
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_REGISTRY_PATH = os.path.join(_PROJECT_ROOT, "data", "capability_registry.json")

# EMA 平滑系数（0~1，越大越重视近期数据）
EMA_ALPHA = 0.3

# 成功阈值：评测分数 >= 此值视为成功
SUCCESS_THRESHOLD = 0.6


class CapabilityFeedbackLoop:
    """管线能力反馈闭环。

    用法：
        fb = CapabilityFeedbackLoop()
        # 管线运行前：获取预设推荐权重
        weights = fb.get_preset_weights()
        # 管线运行后：记录结果
        fb.record_run(
            presets_used=["glow_pulse", "glitch_shake", ...],
            fonts_used=["MicrosoftYaHei", "Consolas", ...],
            grading_styles=["cinematic_warm", ...],
            techniques_used=["match_cut", ...],
            eval_score=0.78,
        )
    """

    def __init__(self, registry_path: Optional[str] = None):
        self._path = registry_path or _REGISTRY_PATH
        self._registry = self._load()

    # ------------------------------------------------------------------
    #  加载 / 保存
    # ------------------------------------------------------------------

    def _load(self) -> Dict[str, Any]:
        """从 JSON 文件加载能力注册表。"""
        if os.path.exists(self._path):
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                logger.debug(f"能力注册表已加载: {self._path}")
                return data
            except Exception as e:
                logger.warning(f"能力注册表加载失败: {e}，使用默认空注册表")
        return self._default_registry()

    @staticmethod
    def _default_registry() -> Dict[str, Any]:
        """生成默认空注册表。"""
        presets = [
            "scale_bounce", "slide_left", "slide_right", "rotate_3d",
            "drop_top", "fade_scale", "glow_pulse", "glitch_shake",
            "elastic_overshoot", "rgb_split", "speed_impact", "flip_card",
            "neon_stroke", "shockwave", "ink_spread", "glitch_flash",
            "particle_dissolve", "neon_breathe",
        ]
        return {
            "version": "1.0.0",
            "description": "管线能力注册表",
            "presets": {
                k: {"usages": 0, "successes": 0, "avg_score": 0.0,
                    "last_used": None, "font_variants_used": {}}
                for k in presets
            },
            "fonts": {
                "MicrosoftYaHei": {"usages": 0, "avg_score": 0.0},
                "Consolas": {"usages": 0, "avg_score": 0.0},
            },
            "color_grading_styles": {
                k: {"usages": 0, "successes": 0, "avg_score": 0.0}
                for k in ["cinematic_warm", "cinematic_cool", "desaturated",
                          "high_contrast", "vintage_fade", "neon_glow", "natural"]
            },
            "edit_techniques": {
                k: {"usages": 0, "successes": 0, "avg_score": 0.0}
                for k in ["match_cut", "j_cut", "l_cut", "jump_cut", "montage_sequence"]
            },
            "run_history": [],
        }

    def save(self) -> None:
        """持久化注册表到 JSON 文件。"""
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._registry, f, ensure_ascii=False, indent=2)
            logger.info(f"能力注册表已保存: {self._path}")
        except Exception as e:
            logger.error(f"能力注册表保存失败: {e}")

    # ------------------------------------------------------------------
    #  记录运行结果
    # ------------------------------------------------------------------

    def record_run(
        self,
        presets_used: List[str],
        fonts_used: List[str],
        eval_score: float,
        grading_styles: Optional[List[str]] = None,
        techniques_used: Optional[List[str]] = None,
    ) -> None:
        """记录一次管线运行的结果，更新注册表中的统计数据。

        Args:
            presets_used: 本次使用的预设名列表
            fonts_used: 本次使用的字体名列表
            eval_score: 评测系统给出的综合评分 (0~1)
            grading_styles: 本次使用的调色风格列表
            techniques_used: 本次使用的高级剪辑技法列表
        """
        is_success = eval_score >= SUCCESS_THRESHOLD
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

        # 更新预设统计
        for preset_key in presets_used:
            entry = self._registry["presets"].get(preset_key)
            if entry is None:
                # 动态注册新预设
                entry = {"usages": 0, "successes": 0, "avg_score": 0.0,
                         "last_used": None, "font_variants_used": {}}
                self._registry["presets"][preset_key] = entry
            entry["usages"] += 1
            if is_success:
                entry["successes"] += 1
            # EMA 更新平均分
            entry["avg_score"] = self._ema(entry["avg_score"], eval_score, entry["usages"])
            entry["last_used"] = now_str

        # 更新字体统计
        for font_name in fonts_used:
            entry = self._registry["fonts"].get(font_name)
            if entry is None:
                entry = {"usages": 0, "avg_score": 0.0}
                self._registry["fonts"][font_name] = entry
            entry["usages"] += 1
            entry["avg_score"] = self._ema(entry["avg_score"], eval_score, entry["usages"])

        # 更新调色风格统计
        for style in (grading_styles or []):
            entry = self._registry["color_grading_styles"].get(style)
            if entry is None:
                entry = {"usages": 0, "successes": 0, "avg_score": 0.0}
                self._registry["color_grading_styles"][style] = entry
            entry["usages"] += 1
            if is_success:
                entry["successes"] += 1
            entry["avg_score"] = self._ema(entry["avg_score"], eval_score, entry["usages"])

        # 更新剪辑技法统计
        for tech in (techniques_used or []):
            entry = self._registry["edit_techniques"].get(tech)
            if entry is None:
                entry = {"usages": 0, "successes": 0, "avg_score": 0.0}
                self._registry["edit_techniques"][tech] = entry
            entry["usages"] += 1
            if is_success:
                entry["successes"] += 1
            entry["avg_score"] = self._ema(entry["avg_score"], eval_score, entry["usages"])

        # 记录运行历史（保留最近 100 条）
        self._registry["run_history"].append({
            "timestamp": now_str,
            "presets": presets_used,
            "fonts": fonts_used,
            "score": eval_score,
            "success": is_success,
        })
        if len(self._registry["run_history"]) > 100:
            self._registry["run_history"] = self._registry["run_history"][-100:]

        logger.info(
            f"反馈闭环: score={eval_score:.3f} success={is_success} "
            f"presets={len(presets_used)} fonts={len(fonts_used)}"
        )

    # ------------------------------------------------------------------
    #  查询与推荐
    # ------------------------------------------------------------------

    def get_preset_weights(self) -> Dict[str, float]:
        """获取预设推荐权重（基于历史表现）。

        从未使用过的预设获得默认权重 1.0（鼓励探索），
        已使用的预设根据成功率加权。

        Returns:
            {preset_key: weight} 权重越高越推荐
        """
        weights: Dict[str, float] = {}
        for key, entry in self._registry["presets"].items():
            if entry["usages"] == 0:
                # 未使用 → 探索权重
                weights[key] = 1.0
            else:
                # 基于 EMA 平均分 + 成功率加权
                success_rate = entry["successes"] / entry["usages"]
                weights[key] = 0.4 * entry["avg_score"] + 0.6 * success_rate
        return weights

    def get_coverage_stats(self) -> Dict[str, Any]:
        """获取预设覆盖率统计。

        Returns:
            {
                "total": int,         # 总预设数
                "used": int,          # 至少使用过一次的预设数
                "coverage_rate": float,  # 覆盖率 (0~1)
                "unused": List[str],  # 未使用的预设列表
                "details": Dict       # 每个预设的详细统计
            }
        """
        presets = self._registry["presets"]
        total = len(presets)
        used = sum(1 for e in presets.values() if e["usages"] > 0)
        unused = [k for k, v in presets.items() if v["usages"] == 0]
        return {
            "total": total,
            "used": used,
            "coverage_rate": used / total if total > 0 else 0.0,
            "unused": unused,
            "details": {k: {"usages": v["usages"], "avg_score": v["avg_score"],
                            "success_rate": v["successes"] / v["usages"] if v["usages"] > 0 else 0.0}
                        for k, v in presets.items()},
        }

    def get_font_recommendations(self) -> Dict[str, float]:
        """获取字体推荐权重。"""
        weights: Dict[str, float] = {}
        for font, entry in self._registry["fonts"].items():
            if entry["usages"] == 0:
                weights[font] = 1.0
            else:
                weights[font] = entry["avg_score"]
        return weights

    def get_grading_style_recommendations(self) -> Dict[str, float]:
        """获取调色风格推荐权重。"""
        weights: Dict[str, float] = {}
        for style, entry in self._registry.get("color_grading_styles", {}).items():
            if entry["usages"] == 0:
                weights[style] = 1.0
            else:
                success_rate = entry["successes"] / entry["usages"]
                weights[style] = 0.5 * entry["avg_score"] + 0.5 * success_rate
        return weights

    # ------------------------------------------------------------------
    #  内部工具
    # ------------------------------------------------------------------

    @staticmethod
    def _ema(old_value: float, new_value: float, count: int) -> float:
        """指数移动平均（EMA）。

        首次记录直接返回新值，后续使用 EMA_ALPHA 加权。
        """
        if count <= 1:
            return new_value
        return EMA_ALPHA * new_value + (1 - EMA_ALPHA) * old_value

    @property
    def registry(self) -> Dict[str, Any]:
        """暴露原始注册表（只读访问）。"""
        return self._registry


# ============================================================================
#  全局单例入口
# ============================================================================

_global_capability_feedback: Optional[CapabilityFeedbackLoop] = None


def get_capability_feedback(
    registry_path: Optional[str] = None,
) -> CapabilityFeedbackLoop:
    """获取全局能力反馈闭环单例。

    Args:
        registry_path: 可选，覆盖默认注册表路径（测试隔离用）。

    Returns:
        全局共享的 CapabilityFeedbackLoop 实例。
    """
    global _global_capability_feedback
    if _global_capability_feedback is None:
        _global_capability_feedback = CapabilityFeedbackLoop(registry_path=registry_path)
    return _global_capability_feedback
