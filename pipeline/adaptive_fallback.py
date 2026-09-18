"""pipeline/adaptive_fallback.py — 自适应降级路径选择器

2026-08-14 从 pipeline/unified_pipeline.py (5824 行上帝文件) 拆出
(431 行类 + 单例/getter)。unified_pipeline 保留 re-export 向后兼容
(from pipeline.unified_pipeline import AdaptiveFallbackSelector 不受影响)。

能力: 基于历史成功率动态选择最优降级路径 (10% 探索性, 过滤同错路径)。
"""
from __future__ import annotations

import json
import logging
import os
import random
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)



class AdaptiveFallbackSelector:
    """自适应降级路径选择器
    
    基于历史成功率动态选择最优降级路径，而非固定降级链。
    
    核心能力:
    1. 记录每个降级路径的成功/失败历史
    2. 基于成功率排序选择最优路径
    3. 带探索性：10%概率尝试次优路径（避免局部最优）
    4. 过滤已知会导致相同错误的路径
    
    用法:
        selector = AdaptiveFallbackSelector()
        
        # 选择降级路径
        path = selector.select_fallback(
            failed_stage="execute",
            error=ValueError("AE Bridge timeout"),
            available_paths=["ae_retry", "ffmpeg_fallback", "skip_stage"]
        )
        
        # 更新成功率
        selector.update_success_rate("ffmpeg_fallback", success=True)
    """
    
    # 默认降级路径配置
    DEFAULT_FALLBACK_CHAINS = {
        "execute": ["ae_retry", "h3_video_edit", "h3_style_transfer", "ffmpeg_fallback", "mock_result"],
        "render": ["ae_render_retry", "h3_inpainting_enhance", "ffmpeg_transcode", "skip_render"],
        "perceive": ["retry", "basic_analysis", "skip"],
        "analyze": ["retry", "vrs_only", "skip"],
        "plan": ["llm_retry", "rule_based", "template"],
        "postproduction": ["h3_video_edit", "h3_style_transfer", "h3_subtitle_modify", "ffmpeg_fallback"],
        "generative": ["h3_video_generation", "h3_motion_transfer", "h3_scene_alteration", "skip"],
    }
    
    def __init__(self, history_file: str = "data/fallback_history.json"):
        # AEK_ENVIRONMENT=test 时使用临时文件，避免测试副作用污染生产 fallback_history.json
        # （典型场景：test_config_workflow_regression_gaps.test_fallback_failure_ends_in_failed_not_running
        #  使用 task_id="double_failure" 触发必然失败的 fallback_func，每次运行都累计失败计数）
        env_test = os.environ.get("AEK_ENVIRONMENT", "").lower() == "test"
        if env_test and history_file == "data/fallback_history.json":
            import tempfile
            history_file = str(Path(tempfile.gettempdir()) / "aekv_test_fallback_history.json")
        self._is_test_env = env_test
        self.history_file = Path(history_file)
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        self._success_rates: dict[str, dict] = {}  # path -> {success, total, last_error}
        # P2.4: 可解释性日志 (path_id -> choice_detail)
        self._explain_log: dict[str, dict[str, Any]] = {}
        self._load_history()
    
    def _load_history(self):
        """加载历史降级记录"""
        if self.history_file.exists():
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    self._success_rates = json.load(f)
            except Exception as e:
                logger.warning(f"[FallbackSelector] Load history failed: {e}")
                self._success_rates = {}
    
    def _save_history(self):
        """保存降级记录"""
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(self._success_rates, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"[FallbackSelector] Save history failed: {e}")
    
    def select_fallback(
        self,
        failed_stage: str,
        error: Exception,
        available_paths: list[str] | None = None,
        exploration_rate: float = 0.1,
    ) -> str:
        """选择最优降级路径
        
        Args:
            failed_stage: 失败的阶段名
            error: 异常对象
            available_paths: 可用降级路径列表（None则使用默认链）
            exploration_rate: 探索率（尝试次优路径的概率）
        
        Returns:
            选中的降级路径名称
        """
        # 获取可用路径
        if available_paths is None:
            available_paths = self.DEFAULT_FALLBACK_CHAINS.get(failed_stage, ["retry", "skip"])
        
        if not available_paths:
            return "skip"
        
        # 1. 过滤掉已知会导致相同错误的路径
        viable_paths = [
            p for p in available_paths
            if not self._is_known_failure(p, error)
        ]
        
        if not viable_paths:
            viable_paths = available_paths  # 所有路径都失败过，仍尝试默认顺序
        
        # 2. 按历史成功率排序
        ranked = sorted(
            viable_paths,
            key=lambda p: self._get_success_rate(p),
            reverse=True
        )
        
        # 3. 返回最优路径（带探索性）
        if ranked and random.random() < exploration_rate and len(ranked) > 1:
            selected = ranked[1]  # 10%概率尝试次优
            logger.info(f"[FallbackSelector] Exploration: selected {selected} (ranked #{2})")
        else:
            selected = ranked[0] if ranked else available_paths[0]
        
        logger.info(f"[FallbackSelector] Selected '{selected}' for stage '{failed_stage}'")
        return selected
    
    def _get_success_rate(self, path: str) -> float:
        """获取路径成功率"""
        stats = self._success_rates.get(path, {})
        total = stats.get("total", 0)
        success = stats.get("success", 0)
        if total == 0:
            return 0.5  # 未知路径默认50%成功率
        return success / total
    
    def _is_known_failure(self, path: str, error: Exception) -> bool:
        """检查路径是否已知会导致相同错误"""
        stats = self._success_rates.get(path, {})
        last_error = stats.get("last_error", "")
        error_msg = str(error).lower()
        
        # 如果上次错误与当前错误相似，认为该路径可能再次失败
        if last_error:
            # 简单的关键词匹配
            error_keywords = set(error_msg.split()[:5])
            last_keywords = set(last_error.lower().split()[:5])
            if len(error_keywords & last_keywords) >= 3:
                return True
        
        return False
    
    def update_success_rate(self, path: str, success: bool, error: Exception | None = None):
        """更新路径成功率（增量学习）

        Args:
            path: 降级路径名称
            success: 是否成功
            error: 如果失败，记录错误信息
        """
        if path not in self._success_rates:
            self._success_rates[path] = {"success": 0, "total": 0, "last_error": ""}

        self._success_rates[path]["total"] += 1
        if success:
            self._success_rates[path]["success"] += 1
            self._success_rates[path]["last_error"] = ""
        else:
            if error is not None:
                # 记录更详细的错误原因：错误类型 + 消息（避免笼统的 "fallback also fails"
                # 这种纯测试字符串进入生产数据，干扰后续诊断）
                error_type = type(error).__name__
                error_msg = str(error)[:200]
                self._success_rates[path]["last_error"] = f"[{error_type}] {error_msg}"

            # 持续 100% 失败检测：累计 ≥10 次且 success=0 时发出警告
            # 根因可能是：(a) 测试副作用污染生产数据；(b) fallback 配置缺失/端点不可用
            stats = self._success_rates[path]
            if stats["total"] >= 10 and stats["success"] == 0:
                logger.warning(
                    f"[FallbackSelector] 路径 '{path}' 持续 {stats['total']} 次全部失败，"
                    f"last_error={stats['last_error'][:120]!r}。"
                    f"建议：(a) 检查是否为测试污染（task_id=double_failure 类场景应使用临时 history_file）；"
                    f"(b) 校验 fallback_providers 配置是否为空或指向不可用端点。"
                )

        self._save_history()

        rate = self._get_success_rate(path)
        logger.debug(f"[FallbackSelector] Updated '{path}': success_rate={rate:.0%}")
    
    def get_statistics(self) -> dict:
        """获取降级路径统计"""
        stats = {}
        for path, data in self._success_rates.items():
            total = data.get("total", 0)
            success = data.get("success", 0)
            stats[path] = {
                "total": total,
                "success": success,
                "success_rate": success / total if total > 0 else 0.5,
                "last_error": data.get("last_error", ""),
            }
        return stats

    # =====================================================================
    #  P2.4: 深度集成 - 元数据增强选择 + 可解释性 + EngineRegistry/MetaStrategyEngine 联动
    # =====================================================================

    def select_with_meta(
        self,
        stage: str,
        error: Exception,
        candidates: list["EngineCandidate"],
        context: dict[str, Any] | None = None,
    ) -> str:
        """基于引擎元数据与历史成功率选择降级路径
        
        评分函数 (深度集成版):
            score = 0.5 * fallback_success_rate
                  + 0.3 * engine_quality_tier
                  + 0.2 * strategy_preference
        
        其中:
        - fallback_success_rate: 来自本选择器历史 (Beta(α=2,β=2) 平滑)
        - engine_quality_tier: 来自 EngineCandidate.metadata.quality_tier
        - strategy_preference: 来自 core.meta_strategy_engine 的策略偏好
        
        与 EngineRegistry 联动:
        - 若 EngineRegistry 可用且 candidate 带 engine_name，会查询其历史成功率
          并作为额外信号融入评分
        
        与 MetaStrategyEngine 联动:
        - 若 MetaStrategyEngine 可用，读取其当前策略偏好 (simplify/fallback/skip)
          作为先验影响选择
        
        Args:
            stage: 失败的阶段名
            error: 异常对象
            candidates: 候选引擎列表 (EngineCandidate 类型，含 path_id/engine_name/metadata)
            context: 可选的执行上下文 (用于 MetaStrategyEngine 查询)
        
        Returns:
            选中的降级路径的 path_id
        
        Raises:
            ValueError: candidates 为空时
        """
        if not candidates:
            # 退回到普通 select_fallback 逻辑
            return self.select_fallback(stage, error)

        # 1. 读取策略偏好 (MetaStrategyEngine 联动，graceful degrade)
        strategy_pref = self._read_strategy_preference(stage, context)

        # 2. 读取 EngineRegistry 历史 (联动，graceful degrade)
        registry = self._get_engine_registry()

        # 3. 评分每个候选
        scored: list[tuple] = []
        for cand in candidates:
            path_id = getattr(cand, "path_id", str(cand))
            engine_name = getattr(cand, "engine_name", "")
            metadata = getattr(cand, "metadata", None)

            # 2a. fallback 历史成功率 (本选择器)
            fb_rate = self._get_success_rate(path_id)

            # 2b. EngineRegistry 历史成功率 (若可用)
            engine_rate = 0.5
            if registry is not None and engine_name:
                try:
                    stats = registry.get_statistics(engine_name)
                    if stats.get("total", 0) > 0:
                        engine_rate = stats.get("success_rate", 0.5)
                except Exception:
                    pass

            # 2c. 质量分级
            tier_map = {"ultra": 1.0, "high": 0.8, "medium": 0.5, "low": 0.2}
            tier_score = 0.5
            if metadata is not None:
                tier_score = tier_map.get(
                    getattr(metadata, "quality_tier", "medium"), 0.5
                )

            # 2d. 策略偏好对齐 (simplify→低质量路径, fallback→中质量, run→高质量)
            strategy_align = 0.5
            if strategy_pref:
                pref_action = strategy_pref.get("action_type", "")
                if pref_action == "simplify" and tier_score < 0.5:
                    strategy_align = 0.9
                elif pref_action == "fallback" and 0.3 <= tier_score <= 0.7:
                    strategy_align = 0.9
                elif pref_action == "skip":
                    strategy_align = 0.3  # 不倾向选具体路径

            # 过滤已知失败的候选 (复用 _is_known_failure)
            if self._is_known_failure(path_id, error):
                # 显著降低分数但不完全排除
                penalty = 0.3
            else:
                penalty = 1.0

            # 综合评分
            score = (
                0.5 * fb_rate
                + 0.2 * engine_rate
                + 0.2 * tier_score
                + 0.1 * strategy_align
            ) * penalty

            scored.append((score, path_id, cand))
            logger.debug(
                "[FallbackSelector/select_with_meta] %s: score=%.3f "
                "(fb=%.2f, eng=%.2f, tier=%.2f, strat=%.2f, pen=%.2f)",
                path_id, score, fb_rate, engine_rate, tier_score,
                strategy_align, penalty,
            )

        # 4. 选最高分 (保留少量探索性)
        scored.sort(key=lambda x: x[0], reverse=True)
        if scored and random.random() < 0.1 and len(scored) > 1:
            selected_path = scored[1][1]
            logger.info(
                "[FallbackSelector/select_with_meta] Exploration: %s (rank #2)",
                selected_path,
            )
        else:
            selected_path = scored[0][1] if scored else "skip"

        # 5. 记录解释信息
        choice_detail = {
            "stage": stage,
            "error": str(error)[:200],
            "selected": selected_path,
            "candidates_evaluated": len(candidates),
            "top_score": scored[0][0] if scored else 0.0,
            "strategy_pref": strategy_pref,
            "registry_used": registry is not None,
            "timestamp": time.time(),
            "all_scores": [
                {"path_id": p, "score": s}
                for s, p, _ in scored[:5]
            ],
        }
        self._explain_log[selected_path] = choice_detail

        logger.info(
            "[FallbackSelector/select_with_meta] Selected '%s' for stage '%s' "
            "(score=%.3f, candidates=%d, registry=%s)",
            selected_path, stage, choice_detail["top_score"],
            len(candidates), registry is not None,
        )
        return selected_path

    def explain_choice(self, path_id: str) -> dict[str, Any]:
        """解释某次选择决策 (可解释性)
        
        Args:
            path_id: 降级路径 ID (由 select_with_meta 返回)
        
        Returns:
            决策详情字典，找不到返回空字典。包含:
            - stage: 失败阶段
            - error: 错误信息
            - selected: 选中的路径
            - candidates_evaluated: 评估的候选数
            - top_score: 最高分
            - strategy_pref: 策略偏好
            - registry_used: 是否使用了 EngineRegistry
            - all_scores: 所有候选的得分 (Top 5)
        """
        return dict(self._explain_log.get(path_id, {}))

    def list_recent_choices(self, limit: int = 10) -> list[dict[str, Any]]:
        """列出最近的选择记录 (按时间倒序)"""
        sorted_choices = sorted(
            self._explain_log.values(),
            key=lambda x: x.get("timestamp", 0),
            reverse=True,
        )
        return sorted_choices[:limit]

    def _get_engine_registry(self) -> Any:
        """获取 EngineRegistry (graceful degrade)"""
        try:
            from core.engine_registry import get_engine_registry
            return get_engine_registry()
        except Exception as e:
            logger.debug("[FallbackSelector] EngineRegistry not available: %s", e)
            return None

    def _read_strategy_preference(
        self, stage: str, context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """读取 MetaStrategyEngine 的策略偏好 (graceful degrade)
        
        Args:
            stage: 目标阶段
            context: 执行上下文
        
        Returns:
            策略偏好字典，包含 action_type (simplify/fallback/skip/run)；
            不可用时返回空字典。
        """
        try:
            from core.meta_strategy_engine import get_strategy_engine
            engine = get_strategy_engine()
            # 读取最近使用的活跃策略 (同步访问，避免事件循环问题)
            library = engine.get_library()
            active_strategies = library.get_active() if library else []
            if not active_strategies:
                return {}
            # 取最近使用的策略
            recent = max(
                active_strategies,
                key=lambda s: getattr(s, "last_used", 0) or 0,
            )
            # 查找该 stage 的 ActionStep
            for step in getattr(recent, "action_sequence", []):
                if step.stage == stage:
                    return {
                        "action_type": step.action_type,
                        "strategy_id": recent.strategy_id,
                        "strategy_name": recent.name,
                    }
            return {"strategy_id": recent.strategy_id, "action_type": ""}
        except Exception as e:
            logger.debug("[FallbackSelector] MetaStrategyEngine not available: %s", e)
            return {}


# 全局降级选择器实例
_fallback_selector: AdaptiveFallbackSelector | None = None


def get_fallback_selector() -> AdaptiveFallbackSelector:
    """获取全局降级选择器实例"""
    global _fallback_selector
    if _fallback_selector is None:
        _fallback_selector = AdaptiveFallbackSelector()
    return _fallback_selector