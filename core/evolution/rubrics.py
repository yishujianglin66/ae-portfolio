"""
core/evolution/rubrics.py — Rubrics 隐藏评分引擎 (P1)
=======================================================

借鉴 PenguinHarness 的 Rubrics 机制:
1. 隐藏评分 — Rubrics 标准只有 Evaluator/Optimizer 可见，被测 Agent 不可见
2. 多次采样取中位数 — 抑制 LLM 评分不稳定性
3. 成本观测 — 累计 token 用量并在超限时熔断
4. 分级 Rubrics — 任务级(题目自带 rubrics 字段) > 作用域级(rubrics/{scope}.md) > 默认

用法:
    from core.evolution.rubrics import get_rubrics_scorer

    scorer = get_rubrics_scorer()
    result = scorer.score(execution_summary, rubrics_text="...")
    # result: RubricScoreResult(score=78.0, runs_ok=3, tokens_used=..., ...)
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import statistics
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.evolution.protocol import within_cost_limit

logger = logging.getLogger(__name__)


# ============================================================================
#  数据结构
# ============================================================================

@dataclass
class RubricScoreResult:
    """一次 Rubrics 评分的完整结果"""
    score: float                                # 中位数得分 0-100
    runs_ok: int = 0                            # 成功采样次数
    samples: list[float] = field(default_factory=list)  # 各次采样分数
    tokens_used: int = 0
    cost_usd: float = 0.0
    reason: str = ""                            # 中位数那次采样的理由
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


DEFAULT_RUBRICS = (
    "评分维度: 1)任务意图达成度(40%) 2)输出完整性与正确性(30%) "
    "3)错误处理与降级质量(15%) 4)执行效率(15%)。\n"
    "每个维度 0-100 分，加权得到综合分。"
)


# ============================================================================
#  Rubrics 评分器
# ============================================================================

class RubricsScorer:
    """LLM 语义评分器 — 对被测管线隐藏评分标准

    与 EvolutionEvaluator 解耦：只负责「给定摘要 + Rubrics → 分数」。
    Optimizer/BenchmarkBuilder 等 P1 模块也可复用。
    """

    DEFAULT_BENCHMARK_DIR = "data/benchmark"
    DEFAULT_RUNS = 3          # 每题跑 3 次取中位数（风险控制）

    def __init__(
        self,
        benchmark_dir: str = DEFAULT_BENCHMARK_DIR,
        runs: int = DEFAULT_RUNS,
        cost_limit_key: str = "single_evaluation",
    ):
        self._benchmark_dir = Path(benchmark_dir)
        self._runs = max(1, int(runs))
        self._cost_limit_key = cost_limit_key

    # ----------------------------------------------------------------
    #  Rubrics 加载（隐藏标准）
    # ----------------------------------------------------------------

    def load_rubrics(self, scope: str = "", task_rubrics: str = "") -> str:
        """加载 Rubrics（优先级: 任务级 > 作用域级文件 > 默认）

        Args:
            scope: 作用域（任务类型或管线模式）
            task_rubrics: 题目自带的 rubrics 字段（优先级最高）
        """
        if task_rubrics and task_rubrics.strip():
            return task_rubrics.strip()
        candidates = []
        if scope:
            candidates.append(self._benchmark_dir / "rubrics" / f"{scope}.md")
        candidates.append(self._benchmark_dir / "rubrics" / "default.md")
        for rubric_path in candidates:
            if rubric_path.exists():
                try:
                    text = rubric_path.read_text(encoding="utf-8").strip()
                    if text:
                        return text
                except Exception:
                    continue
        return DEFAULT_RUBRICS

    # ----------------------------------------------------------------
    #  评分主入口
    # ----------------------------------------------------------------

    def score(
        self,
        execution_summary: str,
        rubrics_text: str = "",
        scope: str = "",
        extra_context: str = "",
    ) -> RubricScoreResult:
        """对一次执行进行 Rubrics 评分（多次采样取中位数）

        Args:
            execution_summary: 被评对象的执行摘要（文本）
            rubrics_text: 显式 Rubrics；为空时按 scope 从文件加载
            scope: 作用域（用于加载 rubrics 文件）
            extra_context: 附加上下文（如任务描述）

        Returns:
            RubricScoreResult；全部采样失败时 score=0 且 notes 含失败原因

        Raises:
            RuntimeError: 全部采样失败
        """
        from core.llm_gateway import TaskType, llm_gateway

        rubrics = rubrics_text.strip() if rubrics_text else self.load_rubrics(scope)

        sections = [
            "你是视频制作管线的独立质量评审专家。请根据以下评分标准(Rubrics)为本次执行打分。",
            f"【评分标准 Rubrics — 对被测系统隐藏】\n{rubrics}",
        ]
        if extra_context:
            sections.append(f"【任务上下文】\n{extra_context}")
        sections.append(f"【执行摘要】\n{execution_summary}")
        sections.append(
            '请只输出一个 JSON 对象，格式: {"score": <0-100的数值>, "reason": "<50字以内理由>"}'
        )
        prompt = "\n\n".join(sections)

        # 使用模块级已配置单例（此前新建 LLMGateway() 未配置任何 Provider，
        # is_available() 恒为 False，导致 Rubrics LLM 评分永远降级）。
        # ensure_configured() 幂等加载 .env/.env.doubao 并装配多 Provider。
        gateway = llm_gateway
        gateway.ensure_configured()
        samples: list[float] = []
        reasons: list[str] = []
        total_tokens = 0
        total_cost = 0.0
        notes: list[str] = []

        for _ in range(self._runs):
            # 成本熔断
            if not within_cost_limit(self._cost_limit_key, total_tokens):
                notes.append("cost_limit_reached_stopped_early")
                break
            try:
                resp = self._call_llm(gateway, prompt, TaskType.QUALITY_REVIEW)
            except Exception as e:
                notes.append(f"llm_call_failed: {type(e).__name__}")
                continue
            if resp is None or not getattr(resp, "success", False):
                continue
            total_tokens += getattr(resp, "tokens_input", 0) + getattr(resp, "tokens_output", 0)
            total_cost += getattr(resp, "cost_usd", 0.0) or 0.0
            parsed = self._parse_response(getattr(resp, "content", "") or "")
            if parsed is not None:
                samples.append(parsed[0])
                reasons.append(parsed[1])

        if not samples:
            raise RuntimeError("all_rubric_eval_runs_failed")

        median = float(statistics.median(samples))
        # 取最接近中位数那次的理由
        idx = min(range(len(samples)), key=lambda i: abs(samples[i] - median))
        notes.append(f"rubric_runs={len(samples)}, median={median:.1f}")

        return RubricScoreResult(
            score=round(median, 2),
            runs_ok=len(samples),
            samples=[round(s, 2) for s in samples],
            tokens_used=total_tokens,
            cost_usd=round(total_cost, 6),
            reason=reasons[idx] if reasons else "",
            notes=notes,
        )

    # ----------------------------------------------------------------
    #  LLM 调用（兼容 async 上下文）
    # ----------------------------------------------------------------

    def _call_llm(self, gateway: Any, prompt: str, task_type: Any) -> Any:
        """同步调用 async 的 chat_with_routing；已有事件循环时走线程兜底"""
        try:
            return asyncio.run(gateway.chat_with_routing(
                message=prompt,
                task_type=task_type,
                system_prompt="你是严格的 JSON 输出器，只输出 JSON 对象。",
                temperature=0.3,
                max_tokens=512,
            ))
        except RuntimeError:
            import concurrent.futures

            def _worker():
                return asyncio.run(gateway.chat_with_routing(
                    message=prompt,
                    task_type=task_type,
                    system_prompt="你是严格的 JSON 输出器，只输出 JSON 对象。",
                    temperature=0.3,
                    max_tokens=512,
                ))

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(_worker).result(timeout=120)

    # ----------------------------------------------------------------
    #  解析
    # ----------------------------------------------------------------

    def _parse_response(self, content: str) -> tuple | None:
        """从 LLM 输出解析 (score, reason)"""
        if not content:
            return None
        try:
            obj = json.loads(content.strip())
            if isinstance(obj, dict) and "score" in obj:
                return max(0.0, min(100.0, float(obj["score"]))), str(obj.get("reason", ""))[:200]
        except Exception:
            pass
        match = re.search(r'\{[^{}]*"score"\s*:\s*([\d.]+)[^{}]*\}', content)
        if match:
            try:
                score = max(0.0, min(100.0, float(match.group(1))))
                reason_match = re.search(r'"reason"\s*:\s*"([^"]*)"', content)
                return score, (reason_match.group(1)[:200] if reason_match else "")
            except ValueError:
                pass
        match = re.search(r'\b(\d{1,3}(?:\.\d+)?)\b', content)
        if match:
            try:
                val = float(match.group(1))
                if 0 <= val <= 100:
                    return val, ""
            except ValueError:
                pass
        return None


# ============================================================================
#  全局单例
# ============================================================================

_global_scorer: RubricsScorer | None = None


def get_rubrics_scorer(
    benchmark_dir: str = RubricsScorer.DEFAULT_BENCHMARK_DIR,
    runs: int = RubricsScorer.DEFAULT_RUNS,
) -> RubricsScorer:
    """获取全局 Rubrics 评分器单例"""
    global _global_scorer
    if _global_scorer is None:
        _global_scorer = RubricsScorer(benchmark_dir=benchmark_dir, runs=runs)
    return _global_scorer
