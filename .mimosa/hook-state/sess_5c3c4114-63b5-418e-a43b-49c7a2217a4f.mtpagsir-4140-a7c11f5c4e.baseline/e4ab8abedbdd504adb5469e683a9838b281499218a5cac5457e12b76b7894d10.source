"""
core/evolution/optimizer_agent.py — Optimizer Agent 优化器 (P1)
=================================================================

借鉴 PenguinHarness 的 Optimizer-Evaluator 分离原则:
1. Optimizer 只看训练集结果 — 分析失分原因，提出配置改进
2. Evaluator 独立打分 — Optimizer 不能干预评分
3. 安全边界 — 参数微调(±10%)自动执行；大范围改动标记人工确认
4. 文件即真相 — 优化提案持久化到 data/evolution/proposals/
5. 成本观测 — 单次优化受 COST_LIMITS["single_optimization"] 约束

用法:
    from core.evolution.optimizer_agent import get_optimizer_agent

    optimizer = get_optimizer_agent()
    proposal = optimizer.propose_improvement(eval_records, current_config)
    # proposal: OptimizationProposal(adjustments={...}, auto_approved=True)

降级策略:
    LLM 不可用 → 基于规则的启发式提案（保守参数微调）
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.evolution.protocol import append_jsonl, within_cost_limit

logger = logging.getLogger(__name__)

# 项目根目录（core/evolution/optimizer_agent.py → 上三级）
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


# ============================================================================
#  数据结构
# ============================================================================

@dataclass
class OptimizationProposal:
    """一次优化提案"""
    proposal_id: str
    scope: str
    adjustments: Dict[str, Any] = field(default_factory=dict)   # 配置调整键值对
    rationale: str = ""                                          # 失分原因分析
    actions: List[str] = field(default_factory=list)             # 建议动作清单
    auto_approved: bool = False                                  # 是否在安全边界内
    needs_human_review: bool = False                             # 需人工确认
    source: str = "heuristic"                                    # llm / heuristic
    tokens_used: int = 0
    cost_usd: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# 允许 Optimizer 自动调整的安全参数（键 → (最小值, 最大值)）
SAFE_ADJUSTABLE_PARAMS: Dict[str, tuple] = {
    "min_quality_score": (40.0, 90.0),
    "max_quality_iterations": (1, 5),
    "style_match": (None, None),        # bool 开关
    "enable_feedback_loop": (None, None),
    "use_compiler": (None, None),
}

# 分数低于该阈值时触发启发式改进
LOW_SCORE_THRESHOLD = 60.0
# 改进目标: 均分低于该值时逐步开启可用的改进手段
IMPROVEMENT_TARGET = 70.0


# ============================================================================
#  Optimizer Agent
# ============================================================================

class OptimizerAgent:
    """优化器 Agent — 分析评测结果 → 提出配置改进提案

    与 Evaluator 完全分离：
    - 输入: 训练集的评测记录（分数 + 分项明细 + 备注）
    - 输出: OptimizationProposal（不直接修改任何配置）
    - 应用由进化主循环（run_evolution）在版本管理框架下执行
    """

    DEFAULT_PROPOSALS_DIR = str(PROJECT_ROOT / "data" / "evolution" / "proposals")

    def __init__(self, proposals_dir: str = DEFAULT_PROPOSALS_DIR):
        self._proposals_dir = Path(proposals_dir)
        self._proposals_dir.mkdir(parents=True, exist_ok=True)

    # ----------------------------------------------------------------
    #  主入口
    # ----------------------------------------------------------------

    def propose_improvements(
        self,
        eval_records: List[Dict[str, Any]],
        current_config: Optional[Dict[str, Any]] = None,
        scope: str = "",
        experience_context: str = "",
    ) -> OptimizationProposal:
        """分析评测记录，提出改进提案

        Args:
            eval_records: 评测结果列表（EvaluationResult.to_dict() 格式）
            current_config: 当前管线配置快照
            scope: 作用域（任务类型）
            experience_context: P2 知识库经验文本（历史进化教训，防重复踩坑）

        Returns:
            OptimizationProposal（永不抛异常，失败时返回空提案）
        """
        current_config = current_config or {}
        proposal: Optional[OptimizationProposal] = None

        # 优先 LLM 分析，失败降级启发式
        try:
            proposal = self._propose_with_llm(
                eval_records, current_config, scope, experience_context
            )
        except Exception as e:
            logger.warning("[Optimizer] LLM proposal failed (degrade to heuristic): %s", e)

        if proposal is None or not proposal.adjustments:
            proposal = self._propose_heuristic(eval_records, current_config, scope)

        # 安全边界裁剪
        proposal.adjustments = self._clip_to_safe_bounds(proposal.adjustments)
        proposal.auto_approved = self._is_within_safe_bounds(proposal.adjustments)
        proposal.needs_human_review = not proposal.auto_approved
        proposal.scope = scope

        self._persist(proposal)
        logger.info(
            "[Optimizer] proposal=%s source=%s adjustments=%d auto_approved=%s",
            proposal.proposal_id, proposal.source,
            len(proposal.adjustments), proposal.auto_approved,
        )
        return proposal

    # ----------------------------------------------------------------
    #  LLM 分析失分原因
    # ----------------------------------------------------------------

    def _propose_with_llm(
        self,
        eval_records: List[Dict[str, Any]],
        current_config: Dict[str, Any],
        scope: str,
        experience_context: str = "",
    ) -> Optional[OptimizationProposal]:
        """用 LLM 分析失分原因并生成配置调整"""
        import asyncio
        from core.llm_gateway import LLMGateway, TaskType

        summary = self._build_analysis_summary(eval_records)
        allowed_keys = list(SAFE_ADJUSTABLE_PARAMS.keys())
        experience_section = f"\n{experience_context}\n" if experience_context else ""
        prompt = (
            "你是视频制作管线的优化专家(Optimizer)。请分析以下评测结果中的失分原因，"
            "并给出配置改进建议。\n\n"
            f"【评测结果摘要（仅训练集）】\n{summary}\n\n"
            f"{experience_section}"
            f"【当前配置】\n{json.dumps(current_config, ensure_ascii=False, default=str)[:1500]}\n\n"
            f"可调整的配置键（只能从中选择）: {allowed_keys}\n\n"
            "只输出严格 JSON 对象，格式:\n"
            '{"adjustments": {"键": 新值, ...}, "rationale": "<100字以内失分原因分析>", '
            '"actions": ["<动作1>", "<动作2>"]}'
        )

        gateway = LLMGateway()

        async def _call():
            return await gateway.chat_with_routing(
                message=prompt,
                task_type=TaskType.PARAMETER_OPTIMIZATION,
                system_prompt="你是严格的 JSON 输出器，只输出 JSON 对象。",
                temperature=0.4,
                max_tokens=1024,
            )

        try:
            resp = asyncio.run(_call())
        except RuntimeError:
            import concurrent.futures

            def _worker():
                return asyncio.run(_call())

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                resp = pool.submit(_worker).result(timeout=180)

        if resp is None or not getattr(resp, "success", False):
            return None
        tokens = getattr(resp, "tokens_input", 0) + getattr(resp, "tokens_output", 0)
        if not within_cost_limit("single_optimization", tokens):
            logger.warning("[Optimizer] proposal tokens exceeded limit")

        parsed = self._parse_proposal(getattr(resp, "content", "") or "")
        if parsed is None:
            return None

        return OptimizationProposal(
            proposal_id=self._next_proposal_id(),
            scope=scope,
            adjustments=parsed.get("adjustments", {}) or {},
            rationale=str(parsed.get("rationale", ""))[:500],
            actions=[str(a) for a in (parsed.get("actions") or [])][:10],
            source="llm",
            tokens_used=tokens,
            cost_usd=round(getattr(resp, "cost_usd", 0.0) or 0.0, 6),
        )

    def _build_analysis_summary(self, eval_records: List[Dict[str, Any]]) -> str:
        """构建失分分析摘要（只含训练集可见信息，P3-D: 含 style_match 失分归因）"""
        if not eval_records:
            return "（无评测记录）"
        lines = []
        for rec in eval_records[-5:]:  # 最近 5 条
            checks = rec.get("checks", {}) or {}
            smd = checks.get("style_match_detail", {}) or {}
            failures = smd.get("failures", []) or []
            lines.append(
                f"- run={rec.get('run_id', '?')} score={rec.get('score', 0)} "
                f"det={rec.get('deterministic_score', 0)} rubric={rec.get('rubric_score')} "
                f"style_match={checks.get('style_match')} style_failures={failures} "
                f"notes={rec.get('notes', [])}"
            )
        return "\n".join(lines)

    def _parse_proposal(self, content: str) -> Optional[Dict[str, Any]]:
        """解析 LLM 提案输出"""
        if not content:
            return None
        content = content.strip()
        fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
        if fence:
            content = fence.group(1)
        try:
            obj = json.loads(content)
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            try:
                obj = json.loads(match.group(0))
                return obj if isinstance(obj, dict) else None
            except Exception:
                pass
        return None

    # ----------------------------------------------------------------
    #  启发式降级（无 LLM 时）
    # ----------------------------------------------------------------

    def _propose_heuristic(
        self,
        eval_records: List[Dict[str, Any]],
        current_config: Dict[str, Any],
        scope: str,
    ) -> OptimizationProposal:
        """基于规则的保守改进（LLM 不可用时的兜底）

        策略按失分严重程度递进:
        - 均分 < 70: 逐步开启 反馈闭环 → 增加迭代 → compiler
        - 均分 < 60: 一次性开启全部可用改进
        """
        adjustments: Dict[str, Any] = {}
        actions: List[str] = []
        rationale_parts: List[str] = []

        if eval_records:
            avg_score = sum(float(r.get("score", 0) or 0) for r in eval_records) / len(eval_records)
            checks = eval_records[-1].get("checks", {}) or {}

            # 输出文件缺失 → 开启 feedback loop 确保重试
            if checks.get("output_exists", 100) < 50 and not current_config.get("enable_feedback_loop", True):
                adjustments["enable_feedback_loop"] = True
                actions.append("开启反馈闭环以重试失败阶段")
                rationale_parts.append("输出文件缺失")

            # 均分低于改进目标 → 递进式改进
            if avg_score < IMPROVEMENT_TARGET:
                if avg_score < LOW_SCORE_THRESHOLD:
                    # 严重失分: 全部开启
                    if not current_config.get("enable_feedback_loop", True):
                        adjustments["enable_feedback_loop"] = True
                        actions.append("开启反馈闭环")
                    cur_iter = int(current_config.get("max_quality_iterations", 1) or 1)
                    if cur_iter < 4:
                        adjustments["max_quality_iterations"] = min(5, cur_iter + 2)
                        actions.append("质量迭代次数提升至 %d" % adjustments["max_quality_iterations"])
                    if not current_config.get("use_compiler", False):
                        adjustments["use_compiler"] = True
                        actions.append("启用 compiler 确定性管线")
                else:
                    # 轻度失分: 每轮只动一个旋钮（保守策略）
                    cur_iter = int(current_config.get("max_quality_iterations", 1) or 1)
                    if cur_iter < 5:
                        adjustments["max_quality_iterations"] = cur_iter + 1
                        actions.append("增加质量迭代次数，让反馈闭环有更多修正机会")
                    elif not current_config.get("use_compiler", False):
                        adjustments["use_compiler"] = True
                        actions.append("启用 compiler 确定性管线提升输出稳定性")
                rationale_parts.append(
                    f"均分 {avg_score:.1f} 低于改进目标 {IMPROVEMENT_TARGET}"
                )

            # 管线成功但质检分低 → 优先 compiler
            if checks.get("pipeline_success", 0) >= 100 and checks.get("quality_score", 100) < 50:
                if not current_config.get("use_compiler", False) and "use_compiler" not in adjustments:
                    adjustments["use_compiler"] = True
                    actions.append("启用 compiler 确定性管线提升输出稳定性")
                rationale_parts.append("执行成功但质检分偏低")

            # 【P3-D】消费 style_match 失分归因 → 针对性提案
            # 归因来自评测器 checks.style_match_detail.failures（黑屏/断言未达标）
            failure_counts: Dict[str, int] = {}
            for rec in eval_records:
                smd = (rec.get("checks", {}) or {}).get("style_match_detail", {}) or {}
                for f in smd.get("failures", []) or []:
                    key = str(f).split(":")[0]
                    failure_counts[key] = failure_counts.get(key, 0) + 1
            for cause, cnt in sorted(failure_counts.items(), key=lambda x: -x[1]):
                if "黑屏" in cause:
                    actions.append(
                        f"修复 AE 执行链内容真实性({cnt}例黑屏): 检查合成按名定位与素材顺序上图层"
                    )
                    rationale_parts.append(f"黑屏产物 x{cnt}")
                elif "无产物" in cause or "未测到" in cause:
                    if not current_config.get("enable_feedback_loop", True):
                        adjustments["enable_feedback_loop"] = True
                        actions.append("开启反馈闭环以重试失败阶段")
                    rationale_parts.append(f"无有效产物 x{cnt}")
                elif "饱和度" in cause:
                    actions.append(f"增强风格效果映射的饱和度调整力度({cnt}例未达标)")
                    rationale_parts.append(f"饱和度断言失分 x{cnt}")
                elif "色温" in cause:
                    actions.append(f"增强风格效果映射的色彩平衡参数({cnt}例色温未达标)")
                    rationale_parts.append(f"色温断言失分 x{cnt}")
                elif "对比度" in cause:
                    actions.append(f"风格效果映射加入亮度/对比度调整({cnt}例对比度未达标)")
                    rationale_parts.append(f"对比度断言失分 x{cnt}")
                elif "效果" in cause or "effect" in cause.lower():
                    if not current_config.get("use_compiler", False) and "use_compiler" not in adjustments:
                        adjustments["use_compiler"] = True
                        actions.append("启用 compiler 确定性管线确保效果应用路径")
                    actions.append(f"确认效果应用记录写入执行结果({cnt}例未命中)")
                    rationale_parts.append(f"效果应用断言失分 x{cnt}")
                else:
                    actions.append(f"排查失分归因: {cause} (x{cnt})")

        return OptimizationProposal(
            proposal_id=self._next_proposal_id(),
            scope=scope,
            adjustments=adjustments,
            rationale="；".join(rationale_parts) if rationale_parts else "无明显失分，维持现状",
            actions=actions,
            source="heuristic",
        )

    # ----------------------------------------------------------------
    #  安全边界
    # ----------------------------------------------------------------

    def _clip_to_safe_bounds(self, adjustments: Dict[str, Any]) -> Dict[str, Any]:
        """裁剪到安全范围；未知键移除（防止 Optimizer 越权）"""
        clipped: Dict[str, Any] = {}
        for key, value in adjustments.items():
            if key not in SAFE_ADJUSTABLE_PARAMS:
                logger.warning("[Optimizer] reject unknown adjustment key: %s", key)
                continue
            lo, hi = SAFE_ADJUSTABLE_PARAMS[key]
            if lo is None and hi is None:
                # bool 开关类
                clipped[key] = bool(value)
                continue
            try:
                num = float(value)
            except (TypeError, ValueError):
                continue
            clipped[key] = max(lo, min(hi, int(num) if isinstance(value, int) else num))
        return clipped

    def _is_within_safe_bounds(self, adjustments: Dict[str, Any]) -> bool:
        """判断提案是否在自动执行的安全边界内

        规则: 全部键在 SAFE_ADJUSTABLE_PARAMS 白名单内 → 自动批准
        （大范围 Prompt/Skill 改动走人工确认，当前 Optimizer 只产出配置键）
        """
        return all(key in SAFE_ADJUSTABLE_PARAMS for key in adjustments)

    # ----------------------------------------------------------------
    #  持久化
    # ----------------------------------------------------------------

    def _next_proposal_id(self) -> str:
        existing = [
            p.name for p in self._proposals_dir.iterdir()
            if p.name.startswith("proposal_") and p.name.endswith(".json")
        ]
        return f"p{len(existing) + 1:04d}"

    def _persist(self, proposal: OptimizationProposal) -> None:
        path = self._proposals_dir / f"proposal_{proposal.proposal_id}.json"
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(proposal.to_dict(), f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.warning("[Optimizer] persist failed: %s", e)
        append_jsonl(self._proposals_dir.parent / "optimization_log.jsonl", proposal.to_dict())

    def load_proposal(self, proposal_id: str) -> Optional[Dict[str, Any]]:
        """读取历史提案"""
        path = self._proposals_dir / f"proposal_{proposal_id}.json"
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None


# ============================================================================
#  全局单例
# ============================================================================

_global_optimizer: Optional[OptimizerAgent] = None


def get_optimizer_agent(
    proposals_dir: str = OptimizerAgent.DEFAULT_PROPOSALS_DIR,
) -> OptimizerAgent:
    """获取全局 OptimizerAgent 单例"""
    global _global_optimizer
    if _global_optimizer is None:
        _global_optimizer = OptimizerAgent(proposals_dir=proposals_dir)
    return _global_optimizer
