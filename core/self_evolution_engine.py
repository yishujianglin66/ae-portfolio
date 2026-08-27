"""
core/self_evolution_engine.py — 全链路闭环自进化引擎 v1.0
============================================================

从执行结果自动学习，无需人工标注。整合所有子系统形成闭环。

设计原则:
1. 自动评估: 渲染完成后自动评估质量
2. 经验蒸馏: 对比成功/失败案例提取知识
3. 知识库自动更新: 新知识写入各子系统
4. 策略自动迭代: 每 N 次运行触发策略进化
5. 新知识验证: 新知识标记"待验证"，N次确认后才升级

集成方式:
    from core.self_evolution_engine import get_evolution_engine

    engine = get_evolution_engine()
    await engine.post_execution_review(execution_record)
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ============================================================================
#  数据结构
# ============================================================================

@dataclass
class ExecutionRecord:
    """管线执行记录"""
    run_id: str
    timestamp: float = 0.0
    # 各阶段结果
    stages: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # 输入规格
    input_spec: Dict[str, Any] = field(default_factory=dict)
    # 配置
    config: Dict[str, Any] = field(default_factory=dict)
    # 输出
    output_path: str = ""
    output_quality: float = 0.0
    # 是否成功
    success: bool = False
    # 总耗时
    total_duration: float = 0.0
    # 使用的策略
    strategy_id: str = ""


@dataclass
class QualityAssessment:
    """自动质量评估结果"""
    overall_score: float = 0.0        # 0-100
    visual_quality: float = 0.0       # 视觉质量
    audio_quality: float = 0.0        # 音频质量
    style_consistency: float = 0.0    # 风格一致性
    technical_quality: float = 0.0    # 技术质量（分辨率/帧率/编码）
    issues: List[Dict[str, str]] = field(default_factory=list)
    strengths: List[str] = field(default_factory=list)


@dataclass
class ReviewResult:
    """执行后评审结果"""
    run_id: str
    quality: QualityAssessment
    prediction_deviation: float = 0.0  # 预测偏差
    experience_extracted: List[str] = field(default_factory=list)
    knowledge_updates: List[Dict[str, str]] = field(default_factory=list)
    strategy_feedback: Optional[Dict[str, Any]] = None


@dataclass
class DistilledKnowledge:
    """蒸馏出的知识"""
    rules: List[Dict[str, Any]] = field(default_factory=list)
    # 每条规则: {"condition": str, "action": str, "confidence": float, "evidence": int}
    error_patterns: List[Dict[str, str]] = field(default_factory=list)
    parameter_insights: List[Dict[str, float]] = field(default_factory=list)
    strategy_improvements: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class PendingKnowledge:
    """待验证的知识"""
    knowledge_id: str
    content: Dict[str, Any]
    confirm_count: int = 0
    reject_count: int = 0
    created_at: float = 0.0
    target_subsystem: str = ""  # "error_memory" | "causal_engine" | "strategy" | "digital_twin"


# ============================================================================
#  P3.3: 规则蒸馏深度增强 (Rule Distillation)
# ============================================================================

@dataclass
class ExecutionEpisode:
    """单次执行情节（用于规则蒸馏的输入）
    
    与 ExecutionRecord 互补:
    - ExecutionRecord: 完整执行日志（含 stages / config / output 等）
    - ExecutionEpisode: 提炼后的关键特征（condition / action / outcome）
    
    Attributes:
        episode_id: 情节 ID
        context_features: 上下文特征 (如 effects_count=10, duration=120)
        action_taken: 执行的动作 (如 "use_glow_with_high_intensity")
        outcome_success: 是否成功
        outcome_quality: 质量分 [0, 100]
        outcome_duration: 耗时(秒)
        strategy_used: 使用的策略 ID
        engine_used: 使用的引擎名
    """
    episode_id: str = ""
    context_features: Dict[str, Any] = field(default_factory=dict)
    action_taken: str = ""
    outcome_success: bool = False
    outcome_quality: float = 0.0
    outcome_duration: float = 0.0
    strategy_used: str = ""
    engine_used: str = ""
    timestamp: float = 0.0


@dataclass
class DistilledRule:
    """蒸馏出的规则
    
    格式: IF <condition> THEN <action> (confidence: float, support: int)
    
    Attributes:
        rule_id: 规则唯一 ID
        condition: 条件表达式（自然语言或简单 DSL）
        action: 推荐动作
        confidence: 置信度 [0, 1]（基于成功比例）
        support: 支撑样本数（满足条件的情节数）
        source: 规则来源 ("distillation" / "expert" / "transfer")
        created_at: 创建时间戳
        metadata: 额外元数据
    """
    rule_id: str = ""
    condition: str = ""
    action: str = ""
    confidence: float = 0.0
    support: int = 0
    source: str = "distillation"
    created_at: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "condition": self.condition,
            "action": self.action,
            "confidence": self.confidence,
            "support": self.support,
            "source": self.source,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


@dataclass
class RuleValidation:
    """规则验证结果
    
    在历史 episodes 上验证规则的有效性。
    
    Attributes:
        rule_id: 被验证的规则 ID
        valid: 是否通过验证（accuracy >= threshold）
        accuracy: 规则预测准确率 [0, 1]
        precision: 精确率 [0, 1]
        recall: 召回率 [0, 1]
        f1_score: F1 分数 [0, 1]
        support: 验证集中满足条件的样本数
        evaluated_at: 评估时间戳
    """
    rule_id: str = ""
    valid: bool = False
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    support: int = 0
    evaluated_at: float = 0.0


class RuleDistiller:
    """规则蒸馏器
    
    从多次执行情节中蒸馏通用规则，规则格式:
        IF <condition> THEN <action> (confidence: float, support: int)
    
    蒸馏流程:
    1. 特征提取: 从 episodes 中提取上下文特征 (effects_count, duration 等)
    2. 分组: 按 (context_features, action) 对 episodes 分组
    3. 规则生成: 对每组生成 IF-THEN 规则
       - confidence = |成功 episodes| / |总 episodes|
       - support = |总 episodes|
    4. 过滤: 丢弃 support < min_support 或 confidence < min_confidence 的规则
    5. 冲突解决: 调用 rule_conflict_resolution 解决冲突
    
    使用示例:
        distiller = RuleDistiller()
        rules = distiller.distill_from_episodes(episodes)
        validation = distiller.validate_rule(rules[0], test_episodes)
        resolved = distiller.rule_conflict_resolution(rules)
    """
    
    def __init__(
        self,
        min_support: int = 3,
        min_confidence: float = 0.6,
    ):
        """
        Args:
            min_support: 规则的最小支撑样本数（少于此数的规则被丢弃）
            min_confidence: 规则的最小置信度（低于此值的规则被丢弃）
        """
        self._min_support = max(1, min_support)
        self._min_confidence = float(np.clip(min_confidence, 0.0, 1.0))
    
    def distill_from_episodes(
        self,
        episodes: List[ExecutionEpisode],
    ) -> List[DistilledRule]:
        """从多次执行情节中蒸馏通用规则
        
        Args:
            episodes: 执行情节列表
            
        Returns:
            蒸馏出的规则列表（已过滤低质量规则，但未做冲突解决）
        """
        if not episodes:
            return []
        
        # Step 1: 按 (condition_signature, action) 分组
        # condition_signature 是上下文特征的简化签名（离散化后的 key-value 对）
        groups: Dict[Tuple[str, str], List[ExecutionEpisode]] = {}
        for ep in episodes:
            cond_sig = self._signature(ep.context_features)
            key = (cond_sig, ep.action_taken)
            groups.setdefault(key, []).append(ep)
        
        # Step 2: 对每组生成规则
        rules: List[DistilledRule] = []
        for (cond_sig, action), group_eps in groups.items():
            support = len(group_eps)
            if support < self._min_support:
                continue
            
            success_count = sum(1 for e in group_eps if e.outcome_success)
            confidence = success_count / support
            
            if confidence < self._min_confidence:
                continue
            
            # 生成人类可读的 condition
            condition_str = self._condition_to_str(
                group_eps[0].context_features, cond_sig
            )
            
            rule = DistilledRule(
                rule_id="rule_" + hashlib.sha256(f"{cond_sig}|{action}".encode()).hexdigest()[:10],
                condition=condition_str,
                action=action,
                confidence=float(confidence),
                support=support,
                source="distillation",
                created_at=time.time(),
                metadata={
                    "avg_quality": float(np.mean(
                        [e.outcome_quality for e in group_eps]
                    )),
                    "avg_duration": float(np.mean(
                        [e.outcome_duration for e in group_eps]
                    )),
                    "success_count": success_count,
                    "condition_signature": cond_sig,
                },
            )
            rules.append(rule)
        
        logger.info(
            f"[RuleDistiller] 蒸馏完成: {len(episodes)} episodes → {len(rules)} rules "
            f"(min_support={self._min_support}, min_confidence={self._min_confidence})"
        )
        return rules
    
    def validate_rule(
        self,
        rule: DistilledRule,
        test_episodes: List[ExecutionEpisode],
    ) -> RuleValidation:
        """在历史 episodes 上验证规则有效性
        
        计算指标:
        - accuracy: 规则预测正确的比例
        - precision: 当规则预测"会成功"时，实际成功的比例
        - recall: 实际成功的 episodes 中，规则预测"会成功"的比例
        - f1_score: 精确率与召回率的调和平均
        
        验证逻辑:
        - 对每个 test episode，判断是否满足 rule.condition
        - 若满足: 规则预测"应用此 action 会成功" (置信度 >= 0.5)
        - 若不满足: 规则预测"不应使用此 action"
        - 与实际 outcome_success 对比，计算指标
        
        Args:
            rule: 待验证的规则
            test_episodes: 测试集 episodes
            
        Returns:
            RuleValidation 验证结果
        """
        if not test_episodes:
            return RuleValidation(
                rule_id=rule.rule_id,
                valid=False,
                support=0,
                evaluated_at=time.time(),
            )
        
        # 二分类: 规则预测 (满足条件 → 应用 action 会成功)
        # TP: 满足条件且实际成功
        # FP: 满足条件但实际失败
        # FN: 不满足条件但实际成功 (规则认为不该用此 action)
        # TN: 不满足条件且实际失败
        tp = fp = fn = tn = 0
        support = 0
        
        for ep in test_episodes:
            matches = self._episode_matches_rule(ep, rule)
            if matches:
                support += 1
                if ep.outcome_success:
                    tp += 1
                else:
                    fp += 1
            else:
                if ep.outcome_success:
                    fn += 1
                else:
                    tn += 1
        
        total = len(test_episodes)
        accuracy = (tp + tn) / total if total > 0 else 0.0
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)
              if (precision + recall) > 0 else 0.0)
        
        # 验证通过条件: accuracy >= 0.6 且 support >= min_support
        valid = accuracy >= 0.6 and support >= self._min_support
        
        return RuleValidation(
            rule_id=rule.rule_id,
            valid=valid,
            accuracy=float(accuracy),
            precision=float(precision),
            recall=float(recall),
            f1_score=float(f1),
            support=support,
            evaluated_at=time.time(),
        )
    
    def rule_conflict_resolution(
        self,
        rules: List[DistilledRule],
    ) -> List[DistilledRule]:
        """检测并解决冲突规则
        
        冲突定义: 两条规则 condition 相似（签名相同）但 action 不同，
        且置信度差异 < 0.1（即两者势均力敌）。
        
        解决策略:
        1. 优先保留 support 更高的规则（数据更充分）
        2. 若 support 相同，保留 confidence 更高的
        3. 若两者都相同，保留 rule_id 字典序更小的（确定性）
        
        Args:
            rules: 待解决冲突的规则列表
            
        Returns:
            解决冲突后的规则列表（可能比输入少）
        """
        if len(rules) <= 1:
            return list(rules)
        
        # 按 condition_signature 分组
        groups: Dict[str, List[DistilledRule]] = {}
        for rule in rules:
            sig = rule.metadata.get("condition_signature", rule.condition)
            groups.setdefault(sig, []).append(rule)
        
        resolved: List[DistilledRule] = []
        for sig, group_rules in groups.items():
            if len(group_rules) == 1:
                resolved.append(group_rules[0])
                continue
            
            # 检测冲突: action 不同 + confidence 接近
            # 先按 action 二次分组
            by_action: Dict[str, List[DistilledRule]] = {}
            for r in group_rules:
                by_action.setdefault(r.action, []).append(r)
            
            if len(by_action) == 1:
                # 同 condition 同 action — 取置信度最高的
                best = max(group_rules, key=lambda r: (r.confidence, r.support))
                resolved.append(best)
                continue
            
            # 不同 action — 检测是否真的冲突
            # 排序: 按 (confidence, support) 降序
            sorted_rules = sorted(
                group_rules,
                key=lambda r: (r.confidence, r.support, r.rule_id),
                reverse=True,
            )
            
            kept: List[DistilledRule] = []
            for r in sorted_rules:
                conflict = False
                for k in kept:
                    # 同 condition 不同 action，且置信度接近 → 冲突
                    if (r.action != k.action
                            and abs(r.confidence - k.confidence) < 0.1):
                        # 保留 support 更高的（已经在 kept 中）
                        conflict = True
                        break
                if not conflict:
                    kept.append(r)
            
            resolved.extend(kept)
        
        logger.info(
            f"[RuleDistiller] 冲突解决: {len(rules)} → {len(resolved)} rules"
        )
        return resolved
    
    # ------------------------------------------------------------------
    #  内部工具方法
    # ------------------------------------------------------------------
    
    def _signature(self, context_features: Dict[str, Any]) -> str:
        """生成上下文特征的签名（用于分组）
        
        将连续特征离散化，便于规则匹配。
        """
        if not context_features:
            return "empty"
        
        parts = []
        for key in sorted(context_features.keys()):
            val = context_features[key]
            if isinstance(val, bool):
                parts.append(f"{key}={'T' if val else 'F'}")
            elif isinstance(val, (int, float)):
                # 离散化: 按数量级分桶
                if val < 0:
                    bucket = "neg"
                elif val == 0:
                    bucket = "zero"
                elif val < 5:
                    bucket = "low"
                elif val < 20:
                    bucket = "mid"
                elif val < 100:
                    bucket = "high"
                else:
                    bucket = "vhigh"
                parts.append(f"{key}={bucket}")
            elif isinstance(val, str):
                # 字符串直接用（截断到 20 字符）
                parts.append(f"{key}={val[:20]}")
            else:
                parts.append(f"{key}=other")
        return "|".join(parts)
    
    def _condition_to_str(
        self,
        context_features: Dict[str, Any],
        signature: str,
    ) -> str:
        """将条件签名转换为人类可读的条件表达式"""
        if not context_features or signature == "empty":
            return "IF (no specific context)"
        
        parts = []
        for key in sorted(context_features.keys()):
            val = context_features[key]
            if isinstance(val, bool):
                parts.append(f"{key}={val}")
            elif isinstance(val, (int, float)):
                if val < 0:
                    bucket = "negative"
                elif val == 0:
                    bucket = "zero"
                elif val < 5:
                    bucket = "low(<5)"
                elif val < 20:
                    bucket = "mid(5-20)"
                elif val < 100:
                    bucket = "high(20-100)"
                else:
                    bucket = "very_high(>=100)"
                parts.append(f"{key}_bucket={bucket}")
            elif isinstance(val, str):
                parts.append(f"{key}='{val}'")
        return f"IF ({' AND '.join(parts)})"
    
    def _episode_matches_rule(
        self,
        episode: ExecutionEpisode,
        rule: DistilledRule,
    ) -> bool:
        """判断 episode 是否匹配规则的条件
        
        匹配逻辑: 比较 episode 上下文特征的签名与规则的 condition_signature
        """
        ep_sig = self._signature(episode.context_features)
        rule_sig = rule.metadata.get("condition_signature", "")
        if rule_sig:
            return ep_sig == rule_sig
        # 回退: 字符串包含匹配
        return rule.condition in self._condition_to_str(
            episode.context_features, ep_sig
        )


# ============================================================================
#  L3.1: 自动质量评估器
# ============================================================================

class AutoQualityEvaluator:
    """自动质量评估器
    
    无需人工标注，基于:
    - 视频技术指标（分辨率/帧率/编码/码率）
    - 统计特征（亮度/对比度/色彩分布）
    - 风格一致性（与输入描述的匹配度）
    """
    
    # 各平台的技术标准
    PLATFORM_STANDARDS: Dict[str, Dict[str, Any]] = {
        "bilibili": {"min_resolution": (1280, 720), "min_fps": 24, "target_bitrate_mbps": 6},
        "douyin": {"min_resolution": (1080, 1920), "min_fps": 30, "target_bitrate_mbps": 8},
        "youtube": {"min_resolution": (1920, 1080), "min_fps": 30, "target_bitrate_mbps": 10},
        "default": {"min_resolution": (1280, 720), "min_fps": 24, "target_bitrate_mbps": 5},
    }
    
    async def evaluate(
        self,
        output_path: str,
        input_spec: Dict[str, Any],
        config: Dict[str, Any],
        stages_result: Dict[str, Dict]
    ) -> QualityAssessment:
        """自动评估输出质量"""
        assessment = QualityAssessment()
        
        # 1. 技术质量评估
        assessment.technical_quality = self._evaluate_technical(
            output_path, input_spec, config
        )
        
        # 2. 视觉质量评估（基于统计特征）
        assessment.visual_quality = self._evaluate_visual(output_path, stages_result)
        
        # 3. 音频质量评估
        assessment.audio_quality = self._evaluate_audio(output_path)
        
        # 4. 风格一致性评估
        assessment.style_consistency = self._evaluate_style_consistency(
            stages_result, config
        )
        
        # 综合评分
        weights = {"technical": 0.3, "visual": 0.3, "audio": 0.2, "style": 0.2}
        assessment.overall_score = (
            assessment.technical_quality * weights["technical"] +
            assessment.visual_quality * weights["visual"] +
            assessment.audio_quality * weights["audio"] +
            assessment.style_consistency * weights["style"]
        )
        
        # 识别问题和优势
        assessment.issues = self._identify_issues(assessment)
        assessment.strengths = self._identify_strengths(assessment)
        
        return assessment
    
    def _evaluate_technical(
        self, output_path: str, input_spec: Dict, config: Dict
    ) -> float:
        """技术质量评估 — 使用 ffprobe 真实数据"""
        # 检查输出文件
        if not output_path or not Path(output_path).exists():
            return 20.0  # 文件不存在
        
        file_size = Path(output_path).stat().st_size
        if file_size < 1024:
            return 15.0  # 文件过小，可能损坏
        
        # 使用 ffprobe 获取真实技术参数
        try:
            from core.frame_sampler import probe_video
            info = probe_video(output_path)
        except Exception:
            # ffprobe 失败时回退到文件级检查
            info = {}
        
        score = 50.0  # 基础分
        
        # 分辨率检查
        target_res = config.get("target_resolution", (1920, 1080))
        platform = config.get("publish_platforms", ["default"])[0] if config.get("publish_platforms") else "default"
        standards = self.PLATFORM_STANDARDS.get(platform, self.PLATFORM_STANDARDS["default"])
        
        width = info.get("width", target_res[0])
        height = info.get("height", target_res[1])
        min_res = standards["min_resolution"]
        if width >= min_res[0] and height >= min_res[1]:
            score += 15
        elif width >= 640 and height >= 480:
            score += 5  # 低分辨率但可接受
        else:
            score -= 15
        
        # 帧率检查
        fps = info.get("fps", config.get("target_fps", 30))
        if fps >= standards["min_fps"]:
            score += 10
        elif fps >= 20:
            score += 3
        else:
            score -= 10
        
        # 码率合理性
        duration = info.get("duration", input_spec.get("total_duration_sec", 60))
        bitrate = info.get("bitrate_kbps", 0)
        if bitrate > 0 and duration > 0:
            expected_kbps = standards["target_bitrate_mbps"] * 1000
            ratio = bitrate / expected_kbps
            if 0.5 < ratio < 2.0:
                score += 10
            elif ratio < 0.2:
                score -= 10
        
        # 文件大小兜底检查
        if duration > 0:
            expected_size = duration * standards["target_bitrate_mbps"] * 1024 * 1024 / 8
            if expected_size > 0:
                size_ratio = file_size / expected_size
                if 0.5 < size_ratio < 2.0:
                    score += 5
        
        return float(np.clip(score, 0, 100))
    
    def _evaluate_visual(self, output_path: str, stages_result: Dict) -> float:
        """视觉质量评估 — 使用真实帧采样解码像素
        
        修复 D1 根因: 旧实现仅数阶段成功数(恒返 60.0), 从未解码像素。
        新实现: 用 frame_sampler 真实解码帧, 计算亮度/对比度/时序变化。
        """
        if not output_path or not Path(output_path).exists():
            return 20.0
        
        # 尝试真实帧采样
        try:
            from core.frame_sampler import sample_frame_stats
            stats = sample_frame_stats(output_path, n_frames=8, scale=160)
        except Exception:
            stats = None
        
        if stats is None or stats.n_sampled == 0:
            # 帧采样失败, 回退到阶段检查
            score = 50.0
            execute_result = stages_result.get("execute", {})
            render_result = stages_result.get("render", {})
            if execute_result.get("success"):
                score += 10
            if render_result.get("success"):
                score += 10
            return float(np.clip(score, 0, 100))
        
        # 基于真实像素统计评分
        score = 40.0  # 基础分
        
        # 亮度适配度: 太暗或太亮都扣分, 中间值最佳
        luma = stats.mean_luma
        luma_fit = 1.0 - abs(luma - 0.45) * 2.0  # 0.45 是理想亮度
        score += max(luma_fit * 15, 0)
        
        # 对比度/纹理丰富度: 高对比度 = 画面有内容
        contrast = stats.luma_contrast
        score += min(contrast * 80, 20)  # contrast ~0.15-0.35 典型范围
        
        # 时序动态: 帧间变化大 = 有动作/节奏感
        temporal = stats.temporal_change
        score += min(temporal * 100, 25)  # temporal ~0.02-0.15 典型范围
        
        # 阶段成功兜底加分
        execute_result = stages_result.get("execute", {})
        render_result = stages_result.get("render", {})
        if execute_result.get("success"):
            score += 5
        if render_result.get("success"):
            score += 5
        
        # Task 9: VMAF 无参考降级分加权(已就绪, 不可用时自动跳过)
        try:
            from integrations.vmaf_quality_adapter import VMAFAdapter
            v = VMAFAdapter().assess_quality(output_path)
            if v.success and v.vmaf_score > 0:
                score = score * 0.6 + float(v.vmaf_score) * 0.4
        except Exception:
            pass  # VMAF 不可用时保持帧统计分
        
        return float(np.clip(score, 0, 100))
    
    def _evaluate_audio(self, output_path: str) -> float:
        """音频质量评估 — 使用 ffprobe 检测音频轨"""
        if not output_path or not Path(output_path).exists():
            return 20.0
        
        file_size = Path(output_path).stat().st_size
        if file_size < 1024:
            return 15.0
        
        # 使用 ffprobe 检测音频轨
        try:
            from core.frame_sampler import probe_video
            info = probe_video(output_path)
            if info.get("has_audio"):
                return 70.0  # 有音频轨 → 中等偏上
            else:
                return 40.0  # 无音频轨 → 偏低(对 AMV 来说音频重要)
        except Exception:
            # ffprobe 失败, 用文件大小兜底
            if file_size > 100 * 1024:  # >100KB 可能有音频
                return 60.0
            return 40.0
    
    def _evaluate_style_consistency(
        self, stages_result: Dict, config: Dict
    ) -> float:
        """风格一致性评估 — 内容级指标优先, 阶段计数兜底
        
        当导演提交了 content metrics(beat_times/cut_times/camera_moves/material_windows)
        时, 用 content_metrics 模块计算真实的卡点对齐+运镜多样性+素材复用率。
        否则回退到 plan 阶段 style_match_score。
        """
        # 尝试从 content 数据计算真实风格分
        content = (stages_result or {}).get("content", {})
        if content:
            try:
                from core import content_metrics as cm
                beat = cm.beat_alignment_score(
                    content.get("cut_times", []),
                    content.get("beat_times", []),
                )
                div = cm.camera_diversity_score(
                    content.get("camera_moves", [])
                )
                reuse = cm.material_reuse_penalty(
                    content.get("material_windows", [])
                )
                # 加权: 卡点 0.5 + 运镜多样性 0.3 + 素材不复用 0.2
                score = (beat * 0.5 + div * 0.3 + (1.0 - reuse) * 0.2) * 100.0
                return float(np.clip(score, 0, 100))
            except Exception:
                pass  # 降级到阶段计数
        
        # 兜底: 阶段计数
        score = 60.0
        plan_result = (stages_result or {}).get("plan", {})
        if plan_result.get("success"):
            style_match = plan_result.get("style_match_score", 0.5)
            score = 50 + style_match * 40
        analyze_result = (stages_result or {}).get("analyze", {})
        if analyze_result.get("success"):
            score += 5
        return float(np.clip(score, 0, 100))
    
    def _identify_issues(self, assessment: QualityAssessment) -> List[Dict[str, str]]:
        """识别质量问题"""
        issues = []
        
        if assessment.technical_quality < 60:
            issues.append({"category": "technical", "severity": "high",
                          "description": "技术质量低于标准"})
        if assessment.visual_quality < 50:
            issues.append({"category": "visual", "severity": "high",
                          "description": "视觉质量不足"})
        if assessment.audio_quality < 50:
            issues.append({"category": "audio", "severity": "medium",
                          "description": "音频质量需要改善"})
        if assessment.style_consistency < 50:
            issues.append({"category": "style", "severity": "medium",
                          "description": "风格一致性较低"})
        
        return issues
    
    def _identify_strengths(self, assessment: QualityAssessment) -> List[str]:
        """识别优势"""
        strengths = []
        if assessment.technical_quality > 80:
            strengths.append("技术质量优秀")
        if assessment.visual_quality > 80:
            strengths.append("视觉效果出色")
        if assessment.style_consistency > 80:
            strengths.append("风格一致性高")
        return strengths


# ============================================================================
#  L3.2: 预测偏差分析
# ============================================================================

class PredictionDeviationAnalyzer:
    """预测偏差分析器
    
    对比数字孪生预测 vs 实际结果，生成校正信号
    """
    
    async def analyze(
        self,
        prediction: Dict[str, Any],
        actual: ExecutionRecord
    ) -> float:
        """分析预测偏差
        
        Returns:
            deviation: 偏差量 [0, 1]，0=完美预测，1=完全偏差
        """
        deviations = []
        
        # 耗时偏差
        pred_duration = prediction.get("total_duration", 0)
        if pred_duration > 0 and actual.total_duration > 0:
            dur_dev = abs(actual.total_duration - pred_duration) / pred_duration
            deviations.append(min(1.0, dur_dev))
        
        # 成功率偏差
        pred_success = prediction.get("overall_success_rate", 0.5)
        actual_success = 1.0 if actual.success else 0.0
        deviations.append(abs(actual_success - pred_success))
        
        # 质量偏差
        pred_quality = prediction.get("quality", 50)
        if pred_quality > 0 and actual.output_quality > 0:
            qual_dev = abs(actual.output_quality - pred_quality) / 100
            deviations.append(min(1.0, qual_dev))
        
        return float(np.mean(deviations)) if deviations else 0.5


# ============================================================================
#  L3.3: 经验蒸馏
# ============================================================================

class ExperienceDistiller:
    """经验蒸馏器
    
    对比成功/失败案例，提取区分性特征，生成可复用规则
    """
    
    async def distill(
        self,
        successful_runs: List[ExecutionRecord],
        failed_runs: List[ExecutionRecord]
    ) -> DistilledKnowledge:
        """蒸馏经验"""
        knowledge = DistilledKnowledge()
        
        if not successful_runs and not failed_runs:
            return knowledge
        
        # 1. 提取错误模式
        knowledge.error_patterns = self._extract_error_patterns(failed_runs)
        
        # 2. 提取成功因素
        success_factors = self._extract_success_factors(successful_runs)
        
        # 3. 对比生成规则
        knowledge.rules = self._generate_rules(success_factors, knowledge.error_patterns)
        
        # 4. 参数洞察
        knowledge.parameter_insights = self._extract_parameter_insights(successful_runs)
        
        return knowledge
    
    def _extract_error_patterns(
        self, failed_runs: List[ExecutionRecord]
    ) -> List[Dict[str, str]]:
        """从失败案例提取错误模式"""
        patterns = []
        error_counts: Dict[str, int] = {}
        
        for run in failed_runs:
            for stage_name, stage_data in run.stages.items():
                if not stage_data.get("success", True):
                    error_msg = stage_data.get("error", "unknown")
                    error_key = f"{stage_name}:{error_msg[:50]}"
                    error_counts[error_key] = error_counts.get(error_key, 0) + 1
        
        for error_key, count in sorted(error_counts.items(), key=lambda x: -x[1]):
            if count >= 2:  # 至少出现2次
                parts = error_key.split(":", 1)
                patterns.append({
                    "stage": parts[0],
                    "error": parts[1] if len(parts) > 1 else "unknown",
                    "frequency": str(count),
                    "severity": "high" if count >= 3 else "medium"
                })
        
        return patterns
    
    def _extract_success_factors(
        self, successful_runs: List[ExecutionRecord]
    ) -> Dict[str, Any]:
        """提取成功因素"""
        factors: Dict[str, Any] = {
            "common_stages": {},
            "avg_effects_count": 0,
            "common_engines": [],
            "avg_quality": 0
        }
        
        if not successful_runs:
            return factors
        
        # 统计共同的成功阶段
        for run in successful_runs:
            for stage_name, stage_data in run.stages.items():
                if stage_data.get("success"):
                    factors["common_stages"][stage_name] = \
                        factors["common_stages"].get(stage_name, 0) + 1
        
        # 平均效果数
        effects_counts = [
            run.stages.get("execute", {}).get("effects_count", 0)
            for run in successful_runs
        ]
        factors["avg_effects_count"] = np.mean(effects_counts) if effects_counts else 0
        
        # 平均质量
        qualities = [run.output_quality for run in successful_runs if run.output_quality > 0]
        factors["avg_quality"] = np.mean(qualities) if qualities else 0
        
        return factors
    
    def _generate_rules(
        self,
        success_factors: Dict,
        error_patterns: List[Dict]
    ) -> List[Dict[str, Any]]:
        """生成 if-then 规则"""
        rules = []
        
        # 从成功因素生成正向规则
        common_stages = success_factors.get("common_stages", {})
        for stage, count in common_stages.items():
            if count >= 3:
                rules.append({
                    "condition": f"stage_{stage}_enabled",
                    "action": f"keep_{stage}_in_pipeline",
                    "confidence": min(0.9, count / 10.0),
                    "evidence": count,
                    "source": "success_pattern"
                })
        
        # 从错误模式生成规避规则
        for pattern in error_patterns:
            rules.append({
                "condition": f"stage_{pattern['stage']}_with_error_{pattern['error'][:20]}",
                "action": f"avoid_{pattern['stage']}_misconfiguration",
                "confidence": min(0.8, int(pattern['frequency']) / 10.0),
                "evidence": int(pattern['frequency']),
                "source": "error_pattern"
            })
        
        # 效果数量规则
        avg_effects = success_factors.get("avg_effects_count", 0)
        if avg_effects > 0:
            rules.append({
                "condition": "effects_count_in_range",
                "action": f"keep_effects_count_around_{int(avg_effects)}",
                "confidence": 0.6,
                "evidence": len(success_factors.get("common_stages", {})),
                "source": "success_pattern"
            })
        
        return rules
    
    def _extract_parameter_insights(
        self, successful_runs: List[ExecutionRecord]
    ) -> List[Dict[str, float]]:
        """提取参数洞察"""
        insights = []
        
        # 收集成功运行中的参数
        all_params: Dict[str, List[float]] = {}
        for run in successful_runs:
            execute_data = run.stages.get("execute", {})
            params = execute_data.get("params", {})
            for key, value in params.items():
                if isinstance(value, (int, float)):
                    all_params.setdefault(key, []).append(float(value))
        
        # 统计最优参数范围
        for param_name, values in all_params.items():
            if len(values) >= 3:
                insights.append({
                    "param": param_name,
                    "optimal_mean": float(np.mean(values)),
                    "optimal_std": float(np.std(values)),
                    "optimal_min": float(np.min(values)),
                    "optimal_max": float(np.max(values)),
                    "sample_count": len(values)
                })
        
        return insights


# ============================================================================
#  L3.4: 知识库自动更新
# ============================================================================

class KnowledgeBaseUpdater:
    """知识库自动更新器
    
    将蒸馏出的知识写入各子系统:
    - 新错误模式 → ErrorPatternMemory
    - 新因果关系 → CausalEngine
    - 新策略 → StrategyLibrary
    - 校正参数 → DigitalTwin
    """
    
    def __init__(self):
        self._pending: Dict[str, PendingKnowledge] = {}
        self._confirmed_threshold = 3  # 确认3次后升级
    
    def submit_knowledge(
        self,
        content: Dict[str, Any],
        target_subsystem: str,
        knowledge_id: str = ""
    ) -> str:
        """提交新知识（标记为待验证）"""
        kid = knowledge_id or f"k_{int(time.time())}_{len(self._pending)}"
        
        self._pending[kid] = PendingKnowledge(
            knowledge_id=kid,
            content=content,
            created_at=time.time(),
            target_subsystem=target_subsystem
        )
        
        logger.info(f"[KBUpdater] 新知识待验证: {kid} → {target_subsystem}")
        return kid
    
    def confirm_knowledge(self, knowledge_id: str) -> bool:
        """确认知识（+1票）"""
        if knowledge_id not in self._pending:
            return False
        
        pk = self._pending[knowledge_id]
        pk.confirm_count += 1
        
        if pk.confirm_count >= self._confirmed_threshold:
            # 升级为已验证，写入目标子系统
            self._apply_knowledge(pk)
            del self._pending[knowledge_id]
            return True
        
        return False
    
    def reject_knowledge(self, knowledge_id: str) -> None:
        """拒绝知识"""
        if knowledge_id in self._pending:
            pk = self._pending[knowledge_id]
            pk.reject_count += 1
            if pk.reject_count >= 3:
                del self._pending[knowledge_id]
    
    def _apply_knowledge(self, pk: PendingKnowledge) -> None:
        """将已验证知识写入目标子系统"""
        try:
            if pk.target_subsystem == "error_memory":
                self._apply_to_error_memory(pk.content)
            elif pk.target_subsystem == "causal_engine":
                self._apply_to_causal_engine(pk.content)
            elif pk.target_subsystem == "strategy":
                self._apply_to_strategy(pk.content)
            elif pk.target_subsystem == "digital_twin":
                self._apply_to_digital_twin(pk.content)
            
            logger.info(f"[KBUpdater] 知识已应用: {pk.knowledge_id} → {pk.target_subsystem}")
        except Exception as e:
            logger.warning(f"[KBUpdater] 应用知识失败: {e}")
    
    def _apply_to_error_memory(self, content: Dict) -> None:
        """写入错误模式记忆"""
        try:
            from pipeline.feedback_loop import ErrorPatternMemory
            memory = ErrorPatternMemory()
            for pattern in content.get("error_patterns", []):
                # 记录新错误模式
                memory.record_error(
                    error_msg=pattern.get("error", ""),
                    stage=pattern.get("stage", ""),
                    fix_applied=pattern.get("fix", "")
                )
        except ImportError:
            pass
    
    def _apply_to_causal_engine(self, content: Dict) -> None:
        """写入因果引擎"""
        try:
            from core.causal_engine import get_causal_engine
            engine = get_causal_engine()
            # 更新因果边权重
            for rule in content.get("rules", []):
                if "source" in rule and "target" in rule:
                    graph = engine.get_causal_graph()
                    edge = graph.get_edge(rule["source"], rule["target"])
                    if edge:
                        edge.confidence = min(1.0, edge.confidence + 0.1)
        except ImportError:
            logger.debug("[KBUpdater] causal_engine 未安装，跳过因果写入")
        except Exception as e:
            logger.warning(f"[KBUpdater] 因果引擎写入异常: {e}")
    
    def _apply_to_strategy(self, content: Dict) -> None:
        """写入策略引擎"""
        try:
            from core.meta_strategy_engine import get_strategy_engine
            engine = get_strategy_engine()
            # 更新策略反馈
            for improvement in content.get("strategy_improvements", []):
                strategy_id = improvement.get("strategy_id", "")
                if strategy_id:
                    engine.record_usage(
                        strategy_id,
                        success=improvement.get("success", True),
                        quality=improvement.get("quality", 0)
                    )
        except ImportError:
            logger.debug("[KBUpdater] meta_strategy_engine 未安装，跳过策略写入")
        except Exception as e:
            logger.warning(f"[KBUpdater] 策略引擎写入异常: {e}")
    
    def _apply_to_digital_twin(self, content: Dict) -> None:
        """P1-1 修复: 将参数洞察转化为数字孪生预测校正

        实现逻辑:
        - 从 parameter_insights 提取最优参数统计
        - 计算参数稳定性 (CV < 0.3 视为高稳定性)
        - 生成合成 ExecutionObservation 馈入孪生校正器
        - 高稳定性洞察 → execute/render 阶段成功率提升
        """
        try:
            from core.pipeline_digital_twin import get_digital_twin, ExecutionObservation
            twin = get_digital_twin()
            insights = content.get("parameter_insights", [])
            if not insights:
                return

            # 统计高稳定性参数比例 (CV = std/mean < 0.3)
            stable_count = 0
            for insight in insights:
                mean = insight.get("optimal_mean", 0)
                std = insight.get("optimal_std", 0)
                cv = abs(std / mean) if mean != 0 else 1.0
                if cv < 0.3:
                    stable_count += 1

            stability_ratio = stable_count / len(insights) if insights else 0
            # 高稳定性 → 执行阶段成功率提升
            success_boost = stability_ratio > 0.5

            # 生成合成观测: 代表"参数已优化"的执行阶段观测
            observation = ExecutionObservation(
                stage_name="execute",
                actual_duration=insights[0].get("optimal_mean", 10.0),
                actual_success=True,
                actual_quality=0.7 + 0.3 * stability_ratio,  # 稳定性越高质量越好
            )

            # 写入孪生预测器的观测历史（影响后续贝叶斯预测）
            predictor = twin._shared_predictor
            predictor._observations.setdefault("execute", []).append(observation)

            # 更新成功率贝叶斯参数
            if "execute" in predictor._success_params:
                alpha, beta = predictor._success_params["execute"]
                if success_boost:
                    alpha += 2  # 强正反馈
                else:
                    alpha += 1
                predictor._success_params["execute"] = (alpha, beta)

            logger.info(
                f"[KBUpdater] 数字孪生校正: {len(insights)} 洞察, "
                f"稳定性={stability_ratio:.2f}, 成功提升={success_boost}"
            )
        except ImportError:
            logger.debug("[KBUpdater] pipeline_digital_twin 未安装，跳过孪生校正")
        except Exception as e:
            logger.warning(f"[KBUpdater] 数字孪生校正异常: {e}")
    
    def get_pending_count(self) -> int:
        return len(self._pending)
    
    def get_statistics(self) -> Dict[str, Any]:
        return {
            "pending_knowledge": len(self._pending),
            "pending_details": {
                kid: {"target": pk.target_subsystem,
                      "confirms": pk.confirm_count,
                      "rejects": pk.reject_count}
                for kid, pk in self._pending.items()
            }
        }


# ============================================================================
#  主引擎: SelfEvolutionEngine
# ============================================================================

class SelfEvolutionEngine:
    """自进化引擎 — 从执行结果自动学习"""
    
    # 默认数据目录收口到 core/paths.self_evolution_dir()
    # （运行时产物移出代码仓库: <AE_WORK_DIR>/self_evolution, AEK_SELF_EVOLUTION_DIR 可覆盖）
    try:
        from core.paths import self_evolution_dir as _paths_evo_dir
        DEFAULT_DATA_DIR = _paths_evo_dir()
    except ImportError:
        DEFAULT_DATA_DIR = "data/self_evolution"
    # 历史位置（迁移前），启动时若存在数据且新位置为空则自动搬迁
    LEGACY_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "self_evolution"
    EVOLUTION_INTERVAL = 10  # 每10次运行触发策略进化
    
    def __init__(self, data_dir: str = DEFAULT_DATA_DIR):
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._migrate_legacy_data()
        
        # 子模块
        self._quality_evaluator = AutoQualityEvaluator()
        self._deviation_analyzer = PredictionDeviationAnalyzer()
        self._distiller = ExperienceDistiller()
        self._kb_updater = KnowledgeBaseUpdater()
        
        # 执行历史
        self._execution_history: List[ExecutionRecord] = []
        self._review_history: List[Dict] = []
        self._last_evolution_run: int = 0
        
        # 加载持久化
        self._load_state()
    
    def _migrate_legacy_data(self) -> None:
        """把历史位置 data/self_evolution 的数据搬迁到新位置（一次性，幂等）。

        只在新位置为空、旧位置存在数据时搬迁；搬迁后旧文件保留（git 已停止跟踪）。
        """
        if not self.LEGACY_DATA_DIR.is_dir():
            return
        try:
            legacy_files = [p for p in self.LEGACY_DATA_DIR.iterdir() if p.is_file()]
            new_files = set(p.name for p in self._data_dir.iterdir()) if self._data_dir.is_dir() else set()
            moved = 0
            for lp in legacy_files:
                if lp.name in new_files:
                    continue
                import shutil
                shutil.copy2(lp, self._data_dir / lp.name)
                moved += 1
            if moved:
                logger.info(f"[SelfEvolution] 已从 {self.LEGACY_DATA_DIR} 搬迁 {moved} 个文件到 {self._data_dir}")
        except Exception as e:
            logger.warning(f"[SelfEvolution] 历史数据搬迁失败（不阻断）: {e}")
    
    # ----------------------------------------------------------------
    #  L3.1: 执行后自动评审
    # ----------------------------------------------------------------
    
    async def post_execution_review(
        self, execution_record: ExecutionRecord
    ) -> ReviewResult:
        """执行后自动评审"""
        # 1. 自动质量评估
        quality = await self._quality_evaluator.evaluate(
            execution_record.output_path,
            execution_record.input_spec,
            execution_record.config,
            execution_record.stages
        )
        execution_record.output_quality = quality.overall_score
        
        # 2. 预测偏差分析
        prediction = execution_record.config.get("_prediction", {})
        deviation = await self._deviation_analyzer.analyze(prediction, execution_record)
        
        # 3. 记录执行
        self._execution_history.append(execution_record)
        
        # 4. 策略反馈
        strategy_feedback = None
        if execution_record.strategy_id:
            strategy_feedback = {
                "strategy_id": execution_record.strategy_id,
                "success": execution_record.success,
                "quality": quality.overall_score,
                "duration": execution_record.total_duration
            }
            # 更新策略引擎
            try:
                from core.meta_strategy_engine import get_strategy_engine
                engine = get_strategy_engine()
                engine.record_usage(
                    execution_record.strategy_id,
                    success=execution_record.success,
                    quality=quality.overall_score,
                    duration=execution_record.total_duration
                )
            except (ImportError, Exception):
                pass
        
        # 5. 构建评审结果
        review = ReviewResult(
            run_id=execution_record.run_id,
            quality=quality,
            prediction_deviation=deviation,
            strategy_feedback=strategy_feedback
        )
        
        self._review_history.append({
            "run_id": review.run_id,
            "quality": quality.overall_score,
            "deviation": deviation,
            "success": execution_record.success,
            "timestamp": time.time()
        })
        
        # 6. 检查是否触发进化
        if len(self._execution_history) - self._last_evolution_run >= self.EVOLUTION_INTERVAL:
            await self.trigger_evolution_cycle()
        
        self._save_state()
        return review
    
    # ----------------------------------------------------------------
    #  L3.3: 经验蒸馏
    # ----------------------------------------------------------------
    
    async def distill_experience(
        self,
        successful_runs: Optional[List[ExecutionRecord]] = None,
        failed_runs: Optional[List[ExecutionRecord]] = None
    ) -> DistilledKnowledge:
        """经验蒸馏"""
        if successful_runs is None:
            successful_runs = [r for r in self._execution_history if r.success]
        if failed_runs is None:
            failed_runs = [r for r in self._execution_history if not r.success]
        
        knowledge = await self._distiller.distill(successful_runs, failed_runs)
        
        # 将知识提交到待验证队列
        if knowledge.error_patterns:
            self._kb_updater.submit_knowledge(
                {"error_patterns": knowledge.error_patterns},
                target_subsystem="error_memory"
            )
        
        if knowledge.rules:
            self._kb_updater.submit_knowledge(
                {"rules": knowledge.rules},
                target_subsystem="causal_engine"
            )
        
        if knowledge.parameter_insights:
            self._kb_updater.submit_knowledge(
                {"parameter_insights": knowledge.parameter_insights},
                target_subsystem="digital_twin"
            )
        
        logger.info(f"[SelfEvolution] 蒸馏完成: {len(knowledge.rules)} 规则, "
                    f"{len(knowledge.error_patterns)} 错误模式, "
                    f"{len(knowledge.parameter_insights)} 参数洞察")
        
        return knowledge
    
    # ----------------------------------------------------------------
    #  L3.5: 周期性策略进化
    # ----------------------------------------------------------------
    
    async def trigger_evolution_cycle(self) -> List[Dict]:
        """触发策略进化周期"""
        self._last_evolution_run = len(self._execution_history)
        
        # 1. 经验蒸馏
        knowledge = await self.distill_experience()
        
        # 2. 策略进化
        new_strategies = []
        try:
            from core.meta_strategy_engine import get_strategy_engine
            engine = get_strategy_engine()
            history = [
                {
                    "strategy_id": r.strategy_id,
                    "success": r.success,
                    "quality": r.output_quality,
                    "duration": r.total_duration
                }
                for r in self._execution_history[-50:]
            ]
            evolved = await engine.evolve_strategies(
                performance_history=history,
                population_size=15,
                n_generations=5
            )
            new_strategies = [
                {"id": s.strategy_id, "name": s.name, "parent": s.parent_id}
                for s in evolved
            ]
        except (ImportError, Exception) as e:
            logger.warning(f"[SelfEvolution] 策略进化失败: {e}")
        
        # 3. 因果图增量更新
        try:
            from core.causal_engine import get_causal_engine, ExecutionRecord as CER
            causal = get_causal_engine()
            # 将执行记录转换为因果引擎格式
            causal_records = []
            for r in self._execution_history[-20:]:
                cr = CER(
                    run_id=r.run_id,
                    timestamp=r.timestamp,
                    stages=r.stages,
                    success=r.success,
                    output_quality=r.output_quality
                )
                causal_records.append(cr)
            if causal_records:
                await causal.discover_causal_structure(causal_records)
        except (ImportError, Exception) as e:
            logger.warning(f"[SelfEvolution] 因果图更新失败: {e}")
        
        # 4. 数字孪生校正
        try:
            from core.pipeline_digital_twin import get_digital_twin, ExecutionObservation
            twin = get_digital_twin()
            for record in self._execution_history[-10:]:
                for stage_name, stage_data in record.stages.items():
                    obs = ExecutionObservation(
                        stage_name=stage_name,
                        actual_duration=stage_data.get("duration", 0),
                        actual_success=stage_data.get("success", True),
                        actual_quality=record.output_quality
                    )
                    # 更新预测器
                    twin._shared_predictor._observations.setdefault(stage_name, []).append(obs)
        except (ImportError, Exception) as e:
            logger.warning(f"[SelfEvolution] 数字孪生校正失败: {e}")
        
        logger.info(f"[SelfEvolution] 进化周期完成: {len(new_strategies)} 新策略")
        self._save_state()
        
        return new_strategies
    
    # ----------------------------------------------------------------
    #  持久化
    # ----------------------------------------------------------------
    
    def _save_state(self) -> None:
        """持久化状态"""
        try:
            state_path = self._data_dir / "evolution_state.json"
            state = {
                "execution_history_size": len(self._execution_history),
                "review_history": self._review_history[-100:],
                "last_evolution_run": self._last_evolution_run,
                "recent_runs": [
                    {
                        "run_id": r.run_id,
                        "timestamp": r.timestamp,
                        "success": r.success,
                        "quality": r.output_quality,
                        "duration": r.total_duration,
                        "strategy_id": r.strategy_id
                    }
                    for r in self._execution_history[-50:]
                ]
            }
            with open(state_path, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"[SelfEvolution] Save state failed: {e}")
    
    def _load_state(self) -> None:
        """加载持久化状态"""
        try:
            state_path = self._data_dir / "evolution_state.json"
            if state_path.exists():
                with open(state_path, "r", encoding="utf-8") as f:
                    state = json.load(f)
                self._review_history = state.get("review_history", [])
                self._last_evolution_run = state.get("last_evolution_run", 0)
        except Exception as e:
            logger.warning(f"[SelfEvolution] Load state failed: {e}")
    
    # ----------------------------------------------------------------
    #  统计
    # ----------------------------------------------------------------
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = len(self._execution_history)
        success = sum(1 for r in self._execution_history if r.success)
        
        return {
            "total_executions": total,
            "success_count": success,
            "failure_count": total - success,
            "success_rate": success / max(total, 1),
            "avg_quality": np.mean([r.output_quality for r in self._execution_history
                                    if r.output_quality > 0]) if self._execution_history else 0.0,
            "reviews_count": len(self._review_history),
            "last_evolution_run": self._last_evolution_run,
            "pending_knowledge": self._kb_updater.get_pending_count(),
            "kb_updater_stats": self._kb_updater.get_statistics(),
        }

    # ----------------------------------------------------------------
    #  P3.3: 规则蒸馏深度增强
    # ----------------------------------------------------------------

    def distill_rules_from_history(
        self,
        min_support: int = 3,
        min_confidence: float = 0.6,
    ) -> List["DistilledRule"]:
        """从执行历史中蒸馏规则
        
        将 self._execution_history 中的 ExecutionRecord 转换为 ExecutionEpisode，
        然后调用 RuleDistiller.distill_from_episodes。
        
        Args:
            min_support: 最小支撑样本数
            min_confidence: 最小置信度
            
        Returns:
            蒸馏出的规则列表（已做冲突解决）
        """
        episodes = self._records_to_episodes(self._execution_history)
        distiller = RuleDistiller(min_support=min_support,
                                  min_confidence=min_confidence)
        rules = distiller.distill_from_episodes(episodes)
        # 自动做冲突解决
        resolved = distiller.rule_conflict_resolution(rules)
        return resolved
    
    def _records_to_episodes(
        self,
        records: List["ExecutionRecord"],
    ) -> List["ExecutionEpisode"]:
        """将 ExecutionRecord 列表转换为 ExecutionEpisode 列表
        
        转换规则:
        - context_features: 从 input_spec / config 提取关键特征
        - action_taken: 用 strategy_id 或 engine 名作为 action 标识
        - outcome_success / quality / duration: 直接映射
        """
        episodes: List[ExecutionEpisode] = []
        for r in records:
            ctx: Dict[str, Any] = {}
            # 从 input_spec 提取
            for k in ("material_count", "video_count", "image_count",
                      "audio_count", "total_duration_sec"):
                if k in r.input_spec:
                    ctx[k] = r.input_spec[k]
            # 从 config 提取
            for k in ("effects_count", "transitions_count", "target_fps",
                      "mode", "enable_vrs"):
                if k in r.config:
                    ctx[k] = r.config[k]
            
            action = r.strategy_id or "unknown_strategy"
            episodes.append(ExecutionEpisode(
                episode_id=r.run_id,
                context_features=ctx,
                action_taken=action,
                outcome_success=r.success,
                outcome_quality=r.output_quality,
                outcome_duration=r.total_duration,
                strategy_used=r.strategy_id,
                timestamp=r.timestamp,
            ))
        return episodes
    
    def get_rule_distiller(
        self,
        min_support: int = 3,
        min_confidence: float = 0.6,
    ) -> "RuleDistiller":
        """获取一个配置好的 RuleDistiller 实例
        
        Args:
            min_support: 最小支撑样本数
            min_confidence: 最小置信度
            
        Returns:
            RuleDistiller 实例
        """
        return RuleDistiller(
            min_support=min_support,
            min_confidence=min_confidence,
        )


# ============================================================================
#  全局单例
# ============================================================================

_global_engine: Optional[SelfEvolutionEngine] = None


def get_evolution_engine(data_dir: str = SelfEvolutionEngine.DEFAULT_DATA_DIR
                         ) -> SelfEvolutionEngine:
    """获取全局自进化引擎单例"""
    global _global_engine
    if _global_engine is None:
        _global_engine = SelfEvolutionEngine(data_dir)
    return _global_engine
