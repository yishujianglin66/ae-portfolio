"""
learning/learning_bridge.py — 学习回读桥接层
============================================

闭合学习闭环的"读侧断点"：将 PersistentLearningLoop / BayesianParameterOptimizer /
MemoryStore 三个学习系统的查询接口集中封装，供 UnifiedPipeline._run_plan 调用，
让历史学习数据真正影响后续参数生成决策。

背景：
    修复前，三个学习系统在 unified_pipeline 主路径中"只写不读"——
    - case-store.json 12 条模板的 usageCount 全为 1（从未被复用）
    - default-value-store.json 仅 1 条记录（偏差学习几乎不触发）
    - BayesianParameterOptimizer 生产目录无观测数据（recommend 永远走冷启动）
    - MemoryStore 仅服务于 nlu_parser 子树，不影响参数生成

    本模块通过 enhance_effect_stack() 把学习数据注入 effect_stack，
    让"上次用户调成 45 满意了"这类经验真正回流到下次规划。

设计原则：
1. 失败安全：任何学习系统异常都不影响主管线，降级为日志告警
2. 增量增强：只填充缺失参数，不覆盖 plan 阶段已显式指定的值
3. 可观测：返回 EnhancementReport 描述每个效果的增强来源
4. 集中查询：一次调用同时查三个系统，按优先级合并
5. 风格感知：从 VRS/KB 分析结果构造 StyleVector，让贝叶斯推荐考虑风格上下文
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ============================================================================
#  增强报告数据结构
# ============================================================================


@dataclass
class EffectEnhancement:
    """单个效果的增强记录"""

    effect_index: int
    effect_name: str
    match_name: str
    enhanced: bool = False
    sources: list[str] = field(default_factory=list)  # ["template", "default_value", "bayesian", "memory"]
    applied_params: dict[str, Any] = field(default_factory=dict)
    template_id: str | None = None
    bayesian_confidence: float | None = None
    memory_key: str | None = None


@dataclass
class EnhancementReport:
    """effect_stack 整体增强报告"""

    total_effects: int = 0
    enhanced_count: int = 0
    per_effect: list[EffectEnhancement] = field(default_factory=list)
    learning_stats: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_effects": self.total_effects,
            "enhanced_count": self.enhanced_count,
            "per_effect": [
                {
                    "effect_index": e.effect_index,
                    "effect_name": e.effect_name,
                    "match_name": e.match_name,
                    "enhanced": e.enhanced,
                    "sources": e.sources,
                    "applied_params": e.applied_params,
                    "template_id": e.template_id,
                    "bayesian_confidence": e.bayesian_confidence,
                    "memory_key": e.memory_key,
                }
                for e in self.per_effect
            ],
            "learning_stats": self.learning_stats,
            "errors": self.errors,
        }


# ============================================================================
#  学习回读桥接器
# ============================================================================


class LearningBridge:
    """学习回读桥接器

    集中查询 PersistentLearningLoop / BayesianParameterOptimizer / MemoryStore，
    将历史学习数据注入 effect_stack，闭合"学了不用"的断点。

    用法：
        bridge = LearningBridge()
        report = bridge.enhance_effect_stack(effect_stack, style_context)
        # effect_stack 已被原地增强（只填充缺失参数）
    """

    # 学习系统优先级：模板 > 默认值 > 贝叶斯 > 记忆库
    # 模板是用户历史上"满意"的参数组合，置信度最高
    SOURCE_PRIORITY = ["template", "default_value", "bayesian", "memory"]

    def __init__(self, lazy_load: bool = True):
        self._learner: Any | None = None
        self._optimizer: Any | None = None
        self._memory_store: Any | None = None
        self._loaded = False
        self._lazy_load = lazy_load

    # ------------------------------------------------------------------
    #  延迟加载学习系统（避免在 import 时失败影响主进程）
    # ------------------------------------------------------------------

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True  # 标记已尝试，避免重复尝试

        # 1. PersistentLearningLoop
        try:
            from learning.persistent_learning_loop import PersistentLearningLoop

            self._learner = PersistentLearningLoop()
            logger.debug(
                "[LearningBridge] PersistentLearningLoop loaded: "
                f"{len(self._learner._execution_records)} records, "
                f"{len(self._learner._case_store.get_all_templates())} templates"
            )
        except Exception as e:
            logger.warning(f"[LearningBridge] PersistentLearningLoop load failed: {e}")

        # 2. BayesianParameterOptimizer
        try:
            from core.bayesian_optimizer import get_optimizer

            self._optimizer = get_optimizer()
            n_obs = sum(len(v) for v in self._optimizer._observations.values())
            logger.debug(f"[LearningBridge] BayesianOptimizer loaded: {n_obs} observations")
        except Exception as e:
            logger.warning(f"[LearningBridge] BayesianOptimizer load failed: {e}")

        # 3. MemoryStore
        try:
            from core.memory_store import MemoryStore

            self._memory_store = MemoryStore()
            logger.debug("[LearningBridge] MemoryStore loaded")
        except Exception as e:
            logger.warning(f"[LearningBridge] MemoryStore load failed: {e}")

    # ------------------------------------------------------------------
    #  主入口：增强 effect_stack
    # ------------------------------------------------------------------

    def enhance_effect_stack(
        self,
        effect_stack: list[dict[str, Any]],
        style_context: Any | None = None,
        user_input: str | None = None,
        vrs_result: dict[str, Any] | None = None,
        kb_style: dict[str, Any] | None = None,
    ) -> EnhancementReport:
        """增强 effect_stack 中的每个效果参数

        Args:
            effect_stack: plan 阶段生成的效果列表，每个元素包含
                          {name, matchName, params, ...}
            style_context: 风格向量（可选，供贝叶斯优化器使用）。
                           若未提供但 vrs_result/kb_style 可用，会自动构造。
            user_input: 用户输入主题（可选，供 MemoryStore 查询）
            vrs_result: VRS 逆向分析结果（可选，用于构造 StyleVector）
            kb_style: KB 风格上下文（可选，用于构造 StyleVector）

        Returns:
            EnhancementReport 描述增强详情
            注意：effect_stack 会被原地修改（只填充缺失参数）
        """
        report = EnhancementReport(total_effects=len(effect_stack))

        if not effect_stack:
            return report

        try:
            self._ensure_loaded()
        except Exception as e:
            report.errors.append(f"learning system load failed: {e}")
            return report

        # 若 style_context 未提供，尝试从 vrs_result/kb_style 自动构造
        if style_context is None and (vrs_result or kb_style or user_input):
            style_context = self.build_style_vector(
                user_input=user_input,
                vrs_result=vrs_result,
                kb_style=kb_style,
            )

        for idx, effect in enumerate(effect_stack):
            try:
                enhancement = self._enhance_single_effect(
                    idx, effect, style_context, user_input
                )
                report.per_effect.append(enhancement)
                if enhancement.enhanced:
                    report.enhanced_count += 1
            except Exception as e:
                err_msg = f"effect[{idx}] enhancement failed: {e}"
                report.errors.append(err_msg)
                logger.warning(f"[LearningBridge] {err_msg}")

        # 附带学习系统统计快照
        report.learning_stats = self._collect_learning_stats()
        return report

    # ------------------------------------------------------------------
    #  StyleVector 构造：从 VRS/KB 分析结果提取风格上下文
    # ------------------------------------------------------------------

    def build_style_vector(
        self,
        user_input: str | None = None,
        vrs_result: dict[str, Any] | None = None,
        kb_style: dict[str, Any] | None = None,
    ) -> Any:
        """从 VRS/KB 分析结果构造 StyleVector

        StyleVector 让贝叶斯优化器的 recommend() 能感知风格上下文，
        例如"高燃"风格倾向高 intensity，"电影感"倾向低 intensity。

        Args:
            user_input: 用户输入主题（如"利威尔高燃混剪"）
            vrs_result: VRS 逆向分析结果，包含 style/intensity/palette 等
            kb_style: KB 风格上下文，包含 mood/intensity 等字段

        Returns:
            StyleVector 实例（若导入失败则返回 None）
        """
        try:
            from core.bayesian_optimizer import StyleVector
        except Exception as e:
            logger.debug(f"[LearningBridge] StyleVector import failed: {e}")
            return None

        # 默认值
        style_name = ""
        mood = ""
        color_palette: list[str] = []
        intensity = 0.5
        target_platform = ""
        reference_params: dict[str, float] = {}

        # 从 user_input 提取风格名
        if user_input:
            ui_lower = user_input.lower()
            # 简单的关键词匹配（与 STYLE_PRESET_MAP 风格名对齐）
            style_keywords = {
                "cinematic": ["电影感", "cinematic", "电影"],
                "amv_fast_cut": ["高燃", "燃", "fast", "fast_cut", "AMV"],
                "amv_pull_zoom": ["pull", "zoom", "拉镜"],
                "dark_tone": ["暗调", "黑暗", "dark", "暗黑"],
                "ghibli": ["吉卜力", "宫崎骏", "ghibli"],
                "cyberpunk": ["赛博", "cyberpunk", "neon"],
                "documentary": ["纪录片", "documentary"],
            }
            for sname, keywords in style_keywords.items():
                if any(kw.lower() in ui_lower for kw in keywords):
                    style_name = sname
                    break
            if not style_name:
                style_name = user_input[:30]

        # 从 VRS 结果提取
        if vrs_result:
            vrs_style = vrs_result.get("style", {})
            if isinstance(vrs_style, dict):
                style_name = vrs_style.get("name", style_name) or style_name
                mood = vrs_style.get("mood", mood) or mood
                vrs_intensity = vrs_style.get("intensity")
                if isinstance(vrs_intensity, (int, float)):
                    intensity = float(vrs_intensity)
                palette = vrs_style.get("palette", [])
                if isinstance(palette, list):
                    color_palette = [str(c) for c in palette][:8]
            # VRS 可能直接提供 reference_params
            ref_params = vrs_result.get("reference_params", {})
            if isinstance(ref_params, dict):
                reference_params = {
                    k: float(v) for k, v in ref_params.items()
                    if isinstance(v, (int, float))
                }

        # 从 KB 风格上下文提取（覆盖 VRS，因为 KB 更具体）
        if kb_style:
            kb_mood = kb_style.get("mood")
            if kb_mood:
                mood = kb_mood
            kb_intensity = kb_style.get("intensity")
            if isinstance(kb_intensity, (int, float)):
                intensity = float(kb_intensity)
            kb_palette = kb_style.get("color_palette", [])
            if isinstance(kb_palette, list) and kb_palette:
                color_palette = [str(c) for c in kb_palette][:8]
            kb_platform = kb_style.get("target_platform")
            if kb_platform:
                target_platform = kb_platform

        # 基于风格名调整 intensity 默认值（若用户/VRS/KB 都未指定）
        if intensity == 0.5 and style_name:
            high_intensity_styles = {"amv_fast_cut", "cyberpunk", "amv_pull_zoom"}
            low_intensity_styles = {"ghibli", "documentary", "dark_tone"}
            if style_name in high_intensity_styles:
                intensity = 0.8
            elif style_name in low_intensity_styles:
                intensity = 0.3

        return StyleVector(
            style_name=style_name,
            mood=mood,
            color_palette=color_palette,
            intensity=intensity,
            target_platform=target_platform,
            reference_params=reference_params,
        )

    # ------------------------------------------------------------------
    #  单个效果增强
    # ------------------------------------------------------------------

    def _enhance_single_effect(
        self,
        idx: int,
        effect: dict[str, Any],
        style_context: Any | None,
        user_input: str | None,
    ) -> EffectEnhancement:
        """对单个效果应用四种学习来源的增强"""
        effect_name = effect.get("name", "") or effect.get("effectName", "")
        match_name = effect.get("matchName", "") or effect.get("id", "")
        key = match_name or effect_name

        enhancement = EffectEnhancement(
            effect_index=idx,
            effect_name=effect_name,
            match_name=match_name,
        )

        if not key:
            return enhancement

        # 确保 params 字段存在
        if "params" not in effect or effect["params"] is None:
            effect["params"] = {}
        current_params: dict[str, Any] = effect["params"]

        # 来源 1: PersistentLearningLoop 参数模板
        self._apply_template(key, current_params, enhancement)

        # 来源 2: PersistentLearningLoop 默认值表
        self._apply_default_values(key, current_params, enhancement)

        # 来源 3: BayesianParameterOptimizer 推荐
        self._apply_bayesian_recommendation(
            effect_name, key, style_context, current_params, enhancement
        )

        # 来源 4: MemoryStore 历史经验
        self._apply_memory_experience(
            effect_name, match_name, user_input, current_params, enhancement
        )

        if enhancement.applied_params:
            enhancement.enhanced = True
            # 把增强参数回写到 effect（只填充尚未设置的）
            for pk, pv in enhancement.applied_params.items():
                if pk not in current_params or current_params[pk] is None:
                    current_params[pk] = pv

        return enhancement

    # ------------------------------------------------------------------
    #  来源 1: 参数模板（用户历史上满意的参数组合）
    # ------------------------------------------------------------------

    def _apply_template(
        self,
        key: str,
        current_params: dict[str, Any],
        enhancement: EffectEnhancement,
    ) -> None:
        if not self._learner:
            return
        try:
            case_store = self._learner._case_store
            templates = case_store.find_templates(key)
            if not templates:
                return

            # 选使用频率最高的模板（find_templates 已按 usage_count 倒序）
            best = templates[0]
            if not best.parameters:
                return

            # 只填充缺失参数
            applied = {}
            for pk, pv in best.parameters.items():
                if pk not in current_params or current_params[pk] is None:
                    applied[pk] = pv

            if applied:
                enhancement.applied_params.update(applied)
                enhancement.sources.append("template")
                enhancement.template_id = best.id
                # 增加模板使用计数，闭合"复用腿"
                try:
                    case_store.increment_usage(best.id)
                except Exception as e:
                    logger.debug(f"[LearningBridge] increment_usage failed: {e}")
        except Exception as e:
            logger.debug(f"[LearningBridge] template query failed for '{key}': {e}")

    # ------------------------------------------------------------------
    #  来源 2: 默认值表（偏差学习的产物）
    # ------------------------------------------------------------------

    def _apply_default_values(
        self,
        key: str,
        current_params: dict[str, Any],
        enhancement: EffectEnhancement,
    ) -> None:
        if not self._learner:
            return
        try:
            default_store = self._learner._default_value_store
            # 取该效果下所有已学到的默认值
            all_defaults = default_store.get_all(key)
            if not all_defaults:
                return

            applied = {}
            for pk, pv in all_defaults.items():
                if pk not in current_params or current_params[pk] is None:
                    applied[pk] = pv

            if applied:
                enhancement.applied_params.update(applied)
                enhancement.sources.append("default_value")
        except Exception as e:
            logger.debug(f"[LearningBridge] default_value query failed for '{key}': {e}")

    # ------------------------------------------------------------------
    #  来源 3: BayesianParameterOptimizer 推荐
    # ------------------------------------------------------------------

    def _apply_bayesian_recommendation(
        self,
        effect_name: str,
        match_name: str,
        style_context: Any | None,
        current_params: dict[str, Any],
        enhancement: EffectEnhancement,
    ) -> None:
        if not self._optimizer:
            return
        try:
            # 尝试两种效果名映射：先按显示名，再按 matchName
            # PARAMETER_SPACES 的 key 是 "Glow" / "ColorBalance" 等
            candidates = [effect_name, match_name]
            # 从 matchName 提取短名（如 "ADBE Glo2" → "Glow"）
            short_name = self._extract_short_effect_name(match_name, effect_name)
            if short_name:
                candidates.append(short_name)

            effect_key = None
            from core.bayesian_optimizer import PARAMETER_SPACES

            for c in candidates:
                if c and c in PARAMETER_SPACES:
                    effect_key = c
                    break

            if not effect_key:
                return  # 不在参数空间中，跳过贝叶斯推荐

            suggestions = self._optimizer.recommend(
                effect_name=effect_key,
                style_context=style_context,
                n_suggestions=1,
            )

            if not suggestions:
                return

            best_suggestion = suggestions[0]
            if not best_suggestion.params:
                return

            applied = {}
            for pk, pv in best_suggestion.params.items():
                if pk not in current_params or current_params[pk] is None:
                    applied[pk] = pv

            if applied:
                enhancement.applied_params.update(applied)
                enhancement.sources.append("bayesian")
                enhancement.bayesian_confidence = best_suggestion.confidence
        except Exception as e:
            logger.debug(f"[LearningBridge] bayesian query failed for '{effect_name}': {e}")

    # ------------------------------------------------------------------
    #  来源 4: MemoryStore 历史经验
    # ------------------------------------------------------------------

    def _apply_memory_experience(
        self,
        effect_name: str,
        match_name: str,
        user_input: str | None,
        current_params: dict[str, Any],
        enhancement: EffectEnhancement,
    ) -> None:
        if not self._memory_store:
            return
        try:
            # 用效果名作为 category 查询历史经验
            # 优先精确匹配，再全文搜索
            memory_key = f"{effect_name}_{match_name}" if match_name else effect_name
            entry = self._memory_store.recall(
                category="effect_params", key=memory_key
            )

            if entry is None and user_input:
                # 退化到全文搜索：用户输入 + 效果名
                query = f"{user_input} {effect_name}"
                results = self._memory_store.search(
                    query=query,
                    category="effect_params",
                    limit=1,
                )
                if results:
                    entry = results[0]

            if entry is None:
                return

            content = entry.content if hasattr(entry, "content") else {}
            if not isinstance(content, dict):
                return

            # 经验内容格式：{"params": {...}, "notes": "...", "success_rate": ...}
            recommended_params = content.get("params", {})
            if not recommended_params:
                return

            applied = {}
            for pk, pv in recommended_params.items():
                if pk not in current_params or current_params[pk] is None:
                    applied[pk] = pv

            if applied:
                enhancement.applied_params.update(applied)
                enhancement.sources.append("memory")
                enhancement.memory_key = memory_key
        except Exception as e:
            logger.debug(f"[LearningBridge] memory query failed for '{effect_name}': {e}")

    # ------------------------------------------------------------------
    #  工具方法
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_short_effect_name(match_name: str, effect_name: str) -> str | None:
        """从 matchName 提取贝叶斯优化器能识别的短名

        例如：
            "ADBE Glo2" → "Glow"
            "ADBE Gaussian Blur 2" → "FastBlur"（近似映射）
            "ADBE CC Vignette" → "Vignette"（如有定义）
            "ADBE Sharpen" → "Sharpen"
            "ADBE Unsharp Mask" → "UnsharpMask"
        """
        if not match_name:
            return None

        mn = match_name.lower()
        en = (effect_name or "").lower()
        # 简单的关键词映射（与 PARAMETER_SPACES 的 key 对齐）
        if "glo2" in mn or "glow" in mn or "glow" in en:
            return "Glow"
        if "gaussian blur" in mn or "fast blur" in mn or "fastblur" in mn:
            return "FastBlur"
        if "starglow" in mn or "star glow" in mn:
            return "CC_StarGlow"
        if "turbulent" in mn or "disperse" in mn:
            return "TurbulentDisperse"
        if "color balance" in mn or "colorbalance" in mn:
            return "ColorBalance"
        if "curves" in mn or "curves" in en:
            # CurvesAdvanced 包含 saturation 字段，优先匹配
            return "Curves"
        if "motion blur" in mn or "motionblur" in mn:
            return "MotionBlur"
        if "vignette" in mn or "vignette" in en:
            return "Vignette"
        if "unsharp" in mn or "unsharp" in en:
            return "UnsharpMask"
        if "sharpen" in mn or "sharpen" in en:
            return "Sharpen"
        return None

    def _collect_learning_stats(self) -> dict[str, Any]:
        """收集三个学习系统的统计快照"""
        stats: dict[str, Any] = {}

        if self._learner:
            try:
                stats["persistent_learning_loop"] = self._learner.get_stats()
            except Exception:
                pass

        if self._optimizer:
            try:
                obs_count = sum(len(v) for v in self._optimizer._observations.values())
                pareto_count = sum(len(v) for v in self._optimizer._pareto_fronts.values())
                stats["bayesian_optimizer"] = {
                    "observations": obs_count,
                    "pareto_points": pareto_count,
                    "effects_tracked": list(self._optimizer._observations.keys()),
                }
            except Exception:
                pass

        if self._memory_store:
            try:
                # MemoryStore 没有统一的 stats 方法，简单查一下条目数
                cursor = self._memory_store._conn.execute("SELECT COUNT(*) FROM memories")
                row = cursor.fetchone()
                stats["memory_store"] = {"total_entries": row[0] if row else 0}
            except Exception:
                pass

        return stats


# ============================================================================
#  全局单例
# ============================================================================


_global_bridge: LearningBridge | None = None


def get_learning_bridge() -> LearningBridge:
    """获取全局 LearningBridge 单例"""
    global _global_bridge
    if _global_bridge is None:
        _global_bridge = LearningBridge()
    return _global_bridge


# ============================================================================
#  学习系统健康度自检
# ============================================================================


def diagnose_learning_systems() -> dict[str, Any]:
    """学习系统健康度自检

    返回每个学习系统的真实状态：
    - 是否加载成功
    - 实际记录条数
    - 是否有数据被消费
    - 推荐的修复动作
    """
    diagnosis: dict[str, Any] = {
        "overall_health": "unknown",
        "systems": {},
        "recommendations": [],
    }

    # 1. PersistentLearningLoop
    pll_status: dict[str, Any] = {"loaded": False}
    try:
        from learning.persistent_learning_loop import PersistentLearningLoop

        learner = PersistentLearningLoop()
        pll_status["loaded"] = True
        pll_status["stats"] = learner.get_stats()

        # 检查模板是否被复用（usageCount > 1 表示有读侧消费）
        templates = learner._case_store.get_all_templates()
        max_usage = max((t.usage_count for t in templates), default=0)
        pll_status["max_template_usage"] = max_usage
        pll_status["templates_being_reused"] = max_usage > 1

        if not templates:
            pll_status["health"] = "empty"
            diagnosis["recommendations"].append(
                "PersistentLearningLoop: 无参数模板，需要先运行几轮管线积累学习数据"
            )
        elif not pll_status["templates_being_reused"]:
            pll_status["health"] = "write_only"
            diagnosis["recommendations"].append(
                "PersistentLearningLoop: 模板只写不读，确认 LearningBridge.enhance_effect_stack "
                "已被 _run_plan 调用"
            )
        else:
            pll_status["health"] = "healthy"
    except Exception as e:
        pll_status["health"] = "broken"
        pll_status["error"] = str(e)
        diagnosis["recommendations"].append(
            f"PersistentLearningLoop: 加载失败 - {e}"
        )
    diagnosis["systems"]["persistent_learning_loop"] = pll_status

    # 2. BayesianParameterOptimizer
    bo_status: dict[str, Any] = {"loaded": False}
    try:
        from core.bayesian_optimizer import get_optimizer

        opt = get_optimizer()
        bo_status["loaded"] = True
        n_obs = sum(len(v) for v in opt._observations.values())
        bo_status["observations"] = n_obs
        bo_status["effects_tracked"] = list(opt._observations.keys())
        bo_status["data_dir"] = str(opt._data_dir)

        if n_obs == 0:
            bo_status["health"] = "empty"
            diagnosis["recommendations"].append(
                "BayesianParameterOptimizer: 无观测数据，确认 _run_learn 已调用 "
                "optimizer.observe() 写入渲染结果"
            )
        elif n_obs < 5:
            bo_status["health"] = "cold_start"
            diagnosis["recommendations"].append(
                f"BayesianParameterOptimizer: 仅 {n_obs} 条观测，需 ≥2 条才能拟合 GP 模型"
            )
        else:
            bo_status["health"] = "healthy"
    except Exception as e:
        bo_status["health"] = "broken"
        bo_status["error"] = str(e)
        diagnosis["recommendations"].append(
            f"BayesianParameterOptimizer: 加载失败 - {e}"
        )
    diagnosis["systems"]["bayesian_optimizer"] = bo_status

    # 3. MemoryStore
    ms_status: dict[str, Any] = {"loaded": False}
    try:
        from core.memory_store import MemoryStore

        ms = MemoryStore()
        ms_status["loaded"] = True
        cursor = ms._conn.execute("SELECT COUNT(*) FROM memories")
        row = cursor.fetchone()
        ms_status["total_entries"] = row[0] if row else 0

        # 检查 effect_params 类别的条目数
        cursor = ms._conn.execute(
            "SELECT COUNT(*) FROM memories WHERE category = ?", ("effect_params",)
        )
        row = cursor.fetchone()
        ms_status["effect_params_entries"] = row[0] if row else 0

        if ms_status["effect_params_entries"] == 0:
            ms_status["health"] = "empty_for_effects"
            diagnosis["recommendations"].append(
                "MemoryStore: 无 effect_params 类别条目，需要将渲染经验写入该类别"
            )
        else:
            ms_status["health"] = "healthy"
    except Exception as e:
        ms_status["health"] = "broken"
        ms_status["error"] = str(e)
        diagnosis["recommendations"].append(
            f"MemoryStore: 加载失败 - {e}"
        )
    diagnosis["systems"]["memory_store"] = ms_status

    # 总体健康度判定
    healths = [
        diagnosis["systems"]["persistent_learning_loop"].get("health"),
        diagnosis["systems"]["bayesian_optimizer"].get("health"),
        diagnosis["systems"]["memory_store"].get("health"),
    ]
    if all(h == "healthy" for h in healths):
        diagnosis["overall_health"] = "healthy"
    elif any(h == "broken" for h in healths):
        diagnosis["overall_health"] = "broken"
    elif any(h in ("empty", "write_only", "cold_start", "empty_for_effects") for h in healths):
        diagnosis["overall_health"] = "warming_up"
    else:
        diagnosis["overall_health"] = "degraded"

    return diagnosis
