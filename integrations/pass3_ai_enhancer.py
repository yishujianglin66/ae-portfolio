"""Pass 3 AI 增强适配器
====================
将 core/ 下的智能引擎（MetaStrategyEngine, CausalEngine, SelfEvolutionEngine）
连接到 ModelScope 真实推理 API，实现：
1. LLM 驱动的策略推荐与解释
2. AI 辅助的因果分析与根因定位
3. 自动规则蒸馏与演化建议

依赖: integrations/modelscope_client.py
"""
from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# 确保项目根在 sys.path
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from integrations.modelscope_client import ModelScopeClient, get_client

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------

@dataclass
class AIStrategyRecommendation:
    """AI 策略推荐结果"""
    strategy_id: str
    confidence: float
    reasoning: str
    parameters: dict[str, Any] = field(default_factory=dict)
    alternatives: list[str] = field(default_factory=list)


@dataclass
class AICausalAnalysis:
    """AI 因果分析结果"""
    root_cause: str
    causal_chain: list[str]
    confidence: float
    recommendations: list[str] = field(default_factory=list)
    counterfactual: str = ""


@dataclass
class AIRuleSuggestion:
    """AI 规则蒸馏建议"""
    rule_name: str
    condition: str
    action: str
    confidence: float
    source_episodes: int = 0


# ---------------------------------------------------------------------------
# AI 增强适配器
# ---------------------------------------------------------------------------

class Pass3AIEnhancer:
    """Pass 3 智能引擎 AI 增强适配器"""

    SYSTEM_PROMPT_STRATEGY = """你是 AE 视频自动化管线的策略优化专家。
根据当前任务上下文和历史执行数据，推荐最优执行策略。
输出格式: JSON {"strategy_id": "...", "confidence": 0.0-1.0, "reasoning": "...", "parameters": {...}}"""

    SYSTEM_PROMPT_CAUSAL = """你是视频渲染管线故障诊断专家。
分析失败案例，识别根本原因，给出因果链和修复建议。
输出格式: JSON {"root_cause": "...", "causal_chain": [...], "confidence": 0.0-1.0, "recommendations": [...]}"""

    SYSTEM_PROMPT_EVOLUTION = """你是技能演化系统的规则蒸馏专家。
从执行历史中提炼可复用规则，格式化为条件-动作对。
输出格式: JSON {"rules": [{"name": "...", "condition": "...", "action": "...", "confidence": 0.0-1.0}]}"""

    def __init__(self, client: ModelScopeClient | None = None):
        self.client = client or get_client()
        self._cache: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # 策略推荐 (MetaStrategyEngine 增强)
    # ------------------------------------------------------------------

    def recommend_strategy(
        self,
        task_type: str,
        context: dict[str, Any],
        history: list[dict] | None = None,
    ) -> AIStrategyRecommendation:
        """LLM 驱动的策略推荐"""
        prompt = f"""任务类型: {task_type}
当前上下文:
{json.dumps(context, ensure_ascii=False, indent=2)[:2000]}

历史执行记录 (最近5条):
{json.dumps((history or [])[:5], ensure_ascii=False, indent=2)[:1500]}

请推荐最优执行策略。"""

        resp = self.client.chat(
            [{"role": "user", "content": prompt}],
            system_prompt=self.SYSTEM_PROMPT_STRATEGY,
            max_tokens=1024,
            temperature=0.3,
        )

        try:
            data = self._extract_json(resp.content)
            return AIStrategyRecommendation(
                strategy_id=data.get("strategy_id", "ai_recommended"),
                confidence=float(data.get("confidence", 0.7)),
                reasoning=data.get("reasoning", resp.content[:200]),
                parameters=data.get("parameters", {}),
                alternatives=data.get("alternatives", []),
            )
        except Exception as e:
            logger.warning(f"Strategy recommendation parse failed: {e}")
            return AIStrategyRecommendation(
                strategy_id="fallback_default",
                confidence=0.5,
                reasoning=resp.content[:200] if resp.content else str(e),
            )

    # ------------------------------------------------------------------
    # 因果分析 (CausalEngine 增强)
    # ------------------------------------------------------------------

    def analyze_failure(
        self,
        error_info: dict[str, Any],
        execution_log: str = "",
    ) -> AICausalAnalysis:
        """AI 辅助的失败根因分析"""
        prompt = f"""失败信息:
{json.dumps(error_info, ensure_ascii=False, indent=2)[:2000]}

执行日志 (尾部):
{execution_log[-2000:] if execution_log else "(无)"}

请分析根本原因，给出因果链和修复建议。"""

        resp = self.client.chat(
            [{"role": "user", "content": prompt}],
            system_prompt=self.SYSTEM_PROMPT_CAUSAL,
            max_tokens=1024,
            temperature=0.2,
        )

        try:
            data = self._extract_json(resp.content)
            return AICausalAnalysis(
                root_cause=data.get("root_cause", "unknown"),
                causal_chain=data.get("causal_chain", []),
                confidence=float(data.get("confidence", 0.6)),
                recommendations=data.get("recommendations", []),
                counterfactual=data.get("counterfactual", ""),
            )
        except Exception as e:
            logger.warning(f"Causal analysis parse failed: {e}")
            return AICausalAnalysis(
                root_cause=resp.content[:100] if resp.content else str(e),
                causal_chain=[],
                confidence=0.3,
            )

    # ------------------------------------------------------------------
    # 规则蒸馏 (SelfEvolutionEngine 增强)
    # ------------------------------------------------------------------

    def distill_rules(
        self,
        episodes: list[dict[str, Any]],
        min_confidence: float = 0.6,
    ) -> list[AIRuleSuggestion]:
        """从执行历史中蒸馏可复用规则"""
        prompt = f"""以下是 {len(episodes)} 条执行历史:
{json.dumps(episodes[:10], ensure_ascii=False, indent=2)[:3000]}

请提炼可复用的条件-动作规则，置信度低于 {min_confidence} 的不要输出。"""

        resp = self.client.chat(
            [{"role": "user", "content": prompt}],
            system_prompt=self.SYSTEM_PROMPT_EVOLUTION,
            max_tokens=2048,
            temperature=0.4,
        )

        rules = []
        try:
            data = self._extract_json(resp.content)
            for r in data.get("rules", []):
                conf = float(r.get("confidence", 0.5))
                if conf >= min_confidence:
                    rules.append(AIRuleSuggestion(
                        rule_name=r.get("name", "unnamed"),
                        condition=r.get("condition", ""),
                        action=r.get("action", ""),
                        confidence=conf,
                        source_episodes=len(episodes),
                    ))
        except Exception as e:
            logger.warning(f"Rule distillation parse failed: {e}")

        return rules

    # ------------------------------------------------------------------
    # 视频帧分析 (Vision)
    # ------------------------------------------------------------------

    def analyze_frame(
        self,
        frame_path: str,
        analysis_type: str = "quality",
    ) -> dict[str, Any]:
        """使用视觉模型分析视频帧"""
        prompts = {
            "quality": "评估这个视频帧的质量：清晰度、色彩、构图。输出JSON: {score: 0-10, issues: [...]}",
            "style": "识别这个视频帧的视觉风格：色调、特效类型、节奏感。输出JSON: {style: ..., confidence: 0-1}",
            "scene": "描述这个视频帧的场景内容：主体、背景、动作。输出JSON: {subject: ..., action: ...}",
        }
        prompt = prompts.get(analysis_type, prompts["quality"])
        result = self.client.analyze_video_frame(frame_path, prompt)

        try:
            return self._extract_json(result)
        except Exception:
            return {"raw": result, "analysis_type": analysis_type}

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------

    def _extract_json(self, text: str) -> dict[str, Any]:
        """从 LLM 输出中提取 JSON"""
        # 尝试直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 尝试提取 ```json ... ``` 块
        import re
        match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # 尝试提取第一个 {...}
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        raise ValueError(f"No JSON found in: {text[:100]}...")

    def health_check(self) -> dict[str, Any]:
        """检查 AI 增强器健康状态"""
        client_health = self.client.health_check()
        return {
            "client": client_health,
            "cache_size": len(self._cache),
        }


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_global_enhancer: Pass3AIEnhancer | None = None


def get_enhancer() -> Pass3AIEnhancer:
    """获取全局 AI 增强器"""
    global _global_enhancer
    if _global_enhancer is None:
        _global_enhancer = Pass3AIEnhancer()
    return _global_enhancer


# ---------------------------------------------------------------------------
# CLI 验证
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    logging.basicConfig(level=logging.INFO)

    enhancer = Pass3AIEnhancer()

    print("=" * 60)
    print("Pass 3 AI 增强适配器验证")
    print("=" * 60)

    # 1. 健康检查
    print("\n[1] 健康检查...")
    health = enhancer.health_check()
    print(f"    Client: {health['client']['status']}")

    # 2. 策略推荐测试
    print("\n[2] 策略推荐测试...")
    rec = enhancer.recommend_strategy(
        task_type="video_render",
        context={"resolution": "1920x1080", "fps": 30, "effect_count": 5},
        history=[{"task": "render", "success": True, "duration": 45}],
    )
    print(f"    策略: {rec.strategy_id}")
    print(f"    置信度: {rec.confidence}")
    print(f"    理由: {rec.reasoning[:100]}...")

    # 3. 因果分析测试
    print("\n[3] 因果分析测试...")
    analysis = enhancer.analyze_failure(
        error_info={"error": "render_timeout", "comp": "Test_Comp", "duration": 300},
        execution_log="WARN: GPU memory low\nERROR: Render failed at frame 150",
    )
    print(f"    根因: {analysis.root_cause}")
    print(f"    置信度: {analysis.confidence}")
    print(f"    建议: {analysis.recommendations[:2]}")

    print("\n" + "=" * 60)
    print("验证完成")
