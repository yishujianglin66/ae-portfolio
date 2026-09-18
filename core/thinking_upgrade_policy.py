"""core/thinking_upgrade_policy.py — 思考升级策略 (从 llm_gateway 拆出)

2026-08-14 从 core/llm_gateway.py (4607 行上帝文件) 拆出的尾部策略类
(580 行)。llm_gateway 保留 re-export 向后兼容
(from core.llm_gateway import ThinkingUpgradePolicy 不受影响)。

TaskType 运行时引用经 _TASK_TYPE_QUALITY_REVIEW() 惰性解析, 规避
llm_gateway ↔ thinking_upgrade_policy 循环导入。
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from core.llm_gateway import LLMGateway, TaskType


def _TASK_TYPE_QUALITY_REVIEW():
    """惰性取 TaskType.QUALITY_REVIEW (运行时才导入 llm_gateway)。"""
    from core.llm_gateway import TaskType
    return TaskType.QUALITY_REVIEW




class ThinkingUpgradePolicy:
    """根据复杂度触发 TIER_3 多轮推理和自我校准。"""

    UPGRADE_TRIGGERS = [
        "三维", "3d", "坐标", "calibration", "校准", "空间", "spatial",
        "形式化", "formal", "verify", "验证", "证明", "prove", "lean",
        "多步", "multi-step", "step-by-step", "reasoning chain", "推理链",
        "约束", "constraint", "boundary", "边界", "求解", "solve",
        "对比分析", "多镜头", "多场景", "综合评估",
    ]
    # H4: "同时考虑" 已从 UPGRADE_TRIGGERS 移除（仅保留在 COMPLEXITY_MARKERS，避免重复计数）
    COMPLEXITY_MARKERS = [
        "分析并对比", "同时考虑", "推导出", "证明并生成",
        "在多个约束下", "边界条件", "回归验证", "交叉验证",
    ]

    def __init__(
        self,
        llm_gateway: "LLMGateway" | None = None,
        thinking_config: dict[str, Any] | None = None,
    ):
        """初始化策略。

        Args:
            llm_gateway: 注入的 LLM 网关；None 时使用模块级已配置单例（H3）。
            thinking_config: thinking_upgrade 配置字典（H1：配置注入途径）；
                None 时读取 core.config 的 model.thinking_upgrade 默认配置
                （函数内 import，避免循环依赖）。
        """
        self._gw = llm_gateway
        self._logger = logging.getLogger(f"{__name__}.ThinkingUpgradePolicy")
        self._config: dict[str, Any] = (
            thinking_config if thinking_config is not None else self._load_default_config()
        )

    # ------------------------------------------------------------------
    # 配置
    # ------------------------------------------------------------------

    @staticmethod
    def _load_default_config() -> dict[str, Any]:
        """读取 core.config 中 model.thinking_upgrade 默认配置。

        函数内 import core.config 以避免循环依赖；配置缺失/异常时回退空配置。
        """
        try:
            from core import config as _core_config
            cfg = _core_config.get_config("model.thinking_upgrade", None)
            if isinstance(cfg, dict):
                return cfg
        except Exception as exc:
            logging.getLogger(f"{__name__}.ThinkingUpgradePolicy").warning(
                "读取 thinking_upgrade 配置失败，使用默认配置: %s", exc
            )
        return {}

    @property
    def _downgrade_on_failure(self) -> bool:
        """升级链路异常时是否回退普通路径（H1）。"""
        return bool(self._config.get("downgrade_on_failure", True))

    # ------------------------------------------------------------------
    # 触发词匹配
    # ------------------------------------------------------------------

    @staticmethod
    def _trigger_in_prompt(trigger: str, prompt_lower: str) -> bool:
        """判断触发词是否命中（H4：修复子串误匹配）。

        - 英文/数字触发词（如 'prove' / '3d'）：使用 ASCII 词边界
          ``(?<![a-z0-9])...(?![a-z0-9])``，避免 'prove' 误匹配 'improve'、
          'formal' 误匹配 'informal'、'lean' 误匹配 'clean'；同时允许中文紧邻
          （如 '3d模型'，Unicode 词边界 \\b 在 CJK 前后不生效，故用 ASCII 边界）。
        - 中文触发词无词边界概念，保留子串判断。
        """
        if not trigger:
            return False
        if re.search(r"^[a-z0-9][a-z0-9\- ]*$", trigger):
            pattern = rf"(?<![a-z0-9]){re.escape(trigger)}(?![a-z0-9])"
            return re.search(pattern, prompt_lower) is not None
        return trigger in prompt_lower

    # ------------------------------------------------------------------
    # 升级决策
    # ------------------------------------------------------------------

    def should_upgrade(
        self,
        task_type: TaskType,
        prompt: str,
        context: dict[str, Any] | None = None,
    ) -> ThinkingUpgradeDecision:
        """判断是否值得升级到 TIER_3 多轮深度推理（H1：预算来自配置）。"""
        current_tier = TASK_TIER_MAP.get(task_type, ModelTier.TIER_2_MIDTIER_GENERAL)
        budget = ThinkingBudget.from_config(self._config)
        if current_tier == ModelTier.TIER_3_FLAGSHIP_REASONING:
            return ThinkingUpgradeDecision(False, "already_tier3", task_type.name, 0.0, budget)

        # M7: context 文本拼入触发词匹配输入
        match_text = prompt or ""
        if context:
            try:
                match_text = f"{match_text}\n{json.dumps(context, ensure_ascii=False)}"
            except (TypeError, ValueError):
                match_text = f"{match_text}\n{str(context)}"

        prompt_lower = match_text.lower()
        hit_triggers = [
            trigger for trigger in self.UPGRADE_TRIGGERS
            if self._trigger_in_prompt(trigger, prompt_lower)
        ]
        complexity_score = sum(
            1 for marker in self.COMPLEXITY_MARKERS if marker in match_text
        )
        if not hit_triggers and complexity_score < 2:
            return ThinkingUpgradeDecision(False, "no_trigger", task_type.name, 0.0, budget)

        estimated_cost = self._estimate_thinking_cost(match_text, budget)
        if estimated_cost > budget.max_cost_usd:
            return ThinkingUpgradeDecision(
                False,
                f"cost_exceeded: ${estimated_cost:.4f} > ${budget.max_cost_usd:.4f}",
                task_type.name,
                estimated_cost,
                budget,
            )
        return ThinkingUpgradeDecision(
            True,
            f"triggers={hit_triggers}, complexity={complexity_score}, est_cost=${estimated_cost:.4f}",
            _TASK_TYPE_QUALITY_REVIEW().name,  # M1: 与实际执行轮一致（原 "deep_reasoning" 不存在）
            estimated_cost,
            budget,
        )

    # ------------------------------------------------------------------
    # 成本估算
    # ------------------------------------------------------------------

    @staticmethod
    def _estimate_input_tokens(text: str) -> int:
        """估算输入 token 数：中文约 1 token/字，英文按 len/4（H2c）。"""
        if not text:
            return 0
        cjk_count = len(re.findall(r"[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]", text))
        other_count = len(text) - cjk_count
        return cjk_count + int(other_count / 4) + 1

    def _estimate_thinking_cost(self, prompt: str, budget: ThinkingBudget) -> float:
        """估算升级路径总成本（H2c/M6：修正原低估口径）。

        估算口径：
        - 输入 token：中文约 1 token/字，英文约 len/4；
        - 每轮回答输出：打满 max_tokens_per_round 的 50%；
        - self-check 轮：输入 = 回答 + 提示词，输出 2000；
        - 价格：输入 $0.015/1K，输出 $0.075/1K。

        Args:
            prompt: 原始任务文本（可含 context 拼接文本）
            budget: 深度推理预算

        Returns:
            float: 估算成本（美元），保留 6 位小数
        """
        if budget.max_rounds <= 0:
            return 0.0
        input_price_per_1k = 0.015
        output_price_per_1k = 0.075
        base_input_tokens = self._estimate_input_tokens(prompt)
        answer_output_tokens = budget.max_tokens_per_round * 0.5
        total_input_tokens = 0.0
        total_output_tokens = 0.0
        for round_index in range(budget.max_rounds):
            # 回答轮：输入随轮次增长（上下文拼接上一轮回答与审查反馈）
            round_input = base_input_tokens + round_index * answer_output_tokens * 0.8
            total_input_tokens += round_input
            total_output_tokens += answer_output_tokens
            # self-check 轮：输入 ≈ 回答 + 提示词，输出 2000
            total_input_tokens += answer_output_tokens + base_input_tokens
            total_output_tokens += 2000
        return round(
            total_input_tokens / 1000 * input_price_per_1k
            + total_output_tokens / 1000 * output_price_per_1k,
            6,
        )

    # ------------------------------------------------------------------
    # self-check 判定
    # ------------------------------------------------------------------

    @staticmethod
    def _self_check_passed(content: str) -> bool:
        """判定 self-check 是否通过（H5：修复 "pass" 子串误判）。

        判定规则：
        - content 为 None 或空白 → False；
        - 中文："通过" 在文本中 且 不含 "不通过"/"未通过" → True；
        - 英文：正则 \\bpass\\b 匹配独立词 PASS，且排除否定上下文
          （not pass / no pass / did not pass / fail）与普通词假阳性
          （bypass / compass / passage / passed the）。
        """
        if not content or not content.strip():
            return False
        text = content.strip()
        lower = text.lower()
        # 先行否定词/失败词 → 直接判定未通过
        if re.search(r"\bnot\s+pass\b|\bno\s+pass\b|\bdid\s+not\s+pass\b|\bfail", lower):
            return False
        # 普通词假阳性防护（\\bpass\\b 本身已不会命中这些词，此处双保险）
        if re.search(r"\bbypass\b|\bcompass\b|\bpassage\b|\bpassed\s+the\b", lower):
            return False
        # 中文判定
        if "通过" in text:
            return "不通过" not in text and "未通过" not in text
        # 英文判定：独立词 PASS
        return re.search(r"\bpass\b", lower) is not None

    # ------------------------------------------------------------------
    # 升级执行
    # ------------------------------------------------------------------

    async def execute_with_thinking(
        self,
        prompt: str,
        original_task_type: TaskType,
        context: dict[str, Any] | None = None,
    ) -> tuple[str, ThinkingTrace]:
        """执行深度推理升级（H1/H2/H4/M1-M10 修复）。

        决策应升级时执行多轮 TIER_3 推理 + self-check；异常/超时/超预算时
        按配置降级或返回部分轨迹，绝不裸抛（M4）。
        """
        decision = self.should_upgrade(original_task_type, prompt, context)
        gateway = self._gateway_or_create()
        context_keys: list[str] = list(context.keys()) if context else []

        if not decision.should_upgrade:
            # 非升级路径（M5：检查 success）
            response = await gateway.chat_with_routing(prompt, original_task_type)
            trace = ThinkingTrace(
                prompt, original_task_type.name, decision, [],
                response.content or "", response.cost_usd, response.latency_ms,
                context_keys=context_keys,
            )
            if not response.success:
                trace.error = "llm_call_failed"
                self._logger.warning(
                    "深度推理非升级路径 LLM 调用失败 (task_type=%s)", original_task_type.name
                )
            return trace.final_answer or "", trace

        # M9: max_rounds <= 0 → 等价非升级，直接走普通路径（不进入循环，避免 IndexError）
        if decision.budget.max_rounds <= 0:
            decision.reason = f"{decision.reason}; max_rounds_zero_downgraded"
            response = await gateway.chat_with_routing(prompt, original_task_type)
            trace = ThinkingTrace(
                prompt, original_task_type.name, decision, [],
                response.content or "", response.cost_usd, response.latency_ms,
                context_keys=context_keys,
            )
            if not response.success:
                trace.error = "llm_call_failed"
            return trace.final_answer or "", trace

        # M7: context 注入首轮 prompt 前缀
        current_prompt = prompt
        if context:
            try:
                context_text = json.dumps(context, ensure_ascii=False, default=str)
            except (TypeError, ValueError):
                context_text = str(context)
            current_prompt = f"[上下文]\n{context_text}\n[任务]\n{prompt}"

        rounds: list[ThinkingRound] = []
        total_cost = 0.0
        total_latency = 0.0
        stop_reason: str | None = None
        start_time = time.time()
        timeout_seconds = float(decision.budget.timeout_seconds)

        try:
            for round_index in range(decision.budget.max_rounds):
                # H2a: 总执行时间超预算 → 直接中止
                elapsed = time.time() - start_time
                if elapsed >= timeout_seconds:
                    stop_reason = "timeout"
                    break
                remaining = max(0.0, timeout_seconds - elapsed)
                call_timeout = min(timeout_seconds, remaining)
                started = time.time()

                # 回答轮（M2: force_temperature=0.7 保留发散探索）
                try:
                    response = await asyncio.wait_for(
                        gateway.chat_with_routing(
                            current_prompt,
                            _TASK_TYPE_QUALITY_REVIEW(),
                            force_temperature=0.7,
                            max_tokens=decision.budget.max_tokens_per_round,
                        ),
                        timeout=call_timeout,
                    )
                except asyncio.TimeoutError:
                    self._logger.warning("深度推理回答轮超时 (round=%d)", round_index)
                    stop_reason = "timeout"
                    break

                if not response.success:
                    # 网关调用失败 → 交 M4 统一处理（降级或返回部分轨迹）
                    raise LLMUnavailableError(
                        f"深度推理回答轮 LLM 调用失败 (round={round_index}): "
                        f"{response.error or 'unknown'}"
                    )

                check_prompt = (
                    f"请检查以下回答是否满足原任务约束。原任务：{prompt}\n"
                    f"回答：{response.content or ''}\n全部通过请回复 PASS，否则给出修正建议。"
                )
                # 审查轮（M3: 与回答轮同档 TIER_3，force_temperature=0.2 严格评判）
                try:
                    check_response = await asyncio.wait_for(
                        gateway.chat_with_routing(
                            check_prompt,
                            _TASK_TYPE_QUALITY_REVIEW(),
                            force_temperature=0.2,
                            max_tokens=2000,
                        ),
                        timeout=call_timeout,
                    )
                except asyncio.TimeoutError:
                    self._logger.warning("深度推理审查轮超时 (round=%d)", round_index)
                    stop_reason = "timeout"
                    # 审查超时：本轮回答保留，标记未通过
                    latency_ms = (time.time() - started) * 1000
                    rounds.append(ThinkingRound(
                        round_index, current_prompt, response.content or "",
                        "", False, latency_ms, response.cost_usd,
                    ))
                    total_cost += response.cost_usd
                    total_latency += latency_ms
                    break

                # M10: latency_ms = 回答轮 + 审查轮耗时之和
                latency_ms = (time.time() - started) * 1000
                passed = self._self_check_passed(check_response.content)
                rounds.append(ThinkingRound(
                    round_index, current_prompt, response.content or "",
                    check_response.content or "", passed, latency_ms,
                    response.cost_usd + check_response.cost_usd,
                ))
                total_cost += response.cost_usd + check_response.cost_usd
                total_latency += latency_ms

                # H2b: 累计成本达到上限 → 提前中止并记录 reason
                if total_cost >= decision.budget.max_cost_usd:
                    stop_reason = "cost_capped"
                    self._logger.warning(
                        "深度推理成本达到上限 $%.4f，提前中止", decision.budget.max_cost_usd
                    )
                    break

                if passed or round_index == decision.budget.max_rounds - 1:
                    break

                current_prompt = (
                    f"原任务：{prompt}\n上一轮回答：{response.content or ''}\n"
                    f"发现问题：{check_response.content or ''}\n请修正并重新回答："
                )
        except Exception as exc:
            # M4: 循环内异常不裸抛 —— 记录日志并按配置降级或返回部分轨迹
            self._logger.error("深度推理升级执行异常: %s", exc)
            return await self._handle_upgrade_exception(
                gateway, prompt, original_task_type, decision,
                rounds, context_keys, exc,
            )

        # L2: 基于最后轮通过情况更新置信度阈值（decision 非 frozen，可直接赋值）
        if rounds:
            decision.confidence_threshold = 1.0 if rounds[-1].passed else 0.0
        if stop_reason:
            decision.reason = f"{decision.reason}; {stop_reason}"

        final_answer = rounds[-1].response or "" if rounds else ""
        trace = ThinkingTrace(
            prompt, original_task_type.name, decision, rounds, final_answer,
            total_cost, total_latency, error=stop_reason, context_keys=context_keys,
        )
        return final_answer, trace

    async def _handle_upgrade_exception(
        self,
        gateway: "LLMGateway",
        prompt: str,
        original_task_type: TaskType,
        decision: ThinkingUpgradeDecision,
        rounds: list[ThinkingRound],
        context_keys: list[str],
        exc: Exception,
    ) -> tuple[str, ThinkingTrace]:
        """处理升级循环异常（M4：不裸抛，降级或返回部分轨迹）。

        - downgrade_on_failure=True 且 rounds 为空 → 降级到普通 chat_with_routing；
        - 否则返回已完成轮次 + error 标记。
        """
        if self._downgrade_on_failure and not rounds:
            try:
                response = await gateway.chat_with_routing(prompt, original_task_type)
            except Exception as fallback_exc:
                self._logger.error("深度推理降级调用也失败: %s", fallback_exc)
                decision.reason = f"{decision.reason}; downgraded_failed"
                trace = ThinkingTrace(
                    prompt, original_task_type.name, decision, [], "",
                    0.0, 0.0, error=f"downgrade_failed: {fallback_exc}",
                    context_keys=context_keys,
                )
                return "", trace
            # H1: decision 保留，rounds 为已完成部分，reason 标注 downgraded
            decision.reason = f"{decision.reason}; downgraded"
            trace = ThinkingTrace(
                prompt, original_task_type.name, decision, [],
                response.content or "", response.cost_usd, response.latency_ms,
                error=f"upgrade_failed: {exc}", context_keys=context_keys,
            )
            if not response.success:
                trace.error = "llm_call_failed"
            return trace.final_answer or "", trace

        # 部分完成：返回已完成轮次 + error 标记（不裸抛）
        final_answer = rounds[-1].response or "" if rounds else ""
        decision.reason = f"{decision.reason}; partial_error"
        trace = ThinkingTrace(
            prompt, original_task_type.name, decision, rounds, final_answer,
            sum(r.cost_usd for r in rounds),
            sum(r.latency_ms for r in rounds),
            error=f"upgrade_failed: {exc}", context_keys=context_keys,
        )
        return final_answer, trace

    def _gateway_or_create(self) -> "LLMGateway":
        """获取网关实例（H3：共享模块级已配置单例，不负责关闭）。

        未注入独立网关时返回模块级 ``llm_gateway`` 单例（经 configure_from_env
        配置）；该单例由应用生命周期管理，本策略不负责创建或关闭它。
        """
        if self._gw is None:
            self._gw = llm_gateway
        return self._gw


async def chat_with_thinking_upgrade(
    prompt: str,
    task_type: TaskType,
    context: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
) -> tuple[str, ThinkingTrace]:
    """深度推理升级生产入口（M8：集成生产路径）。

    Args:
        prompt: 用户任务
        task_type: 任务类型
        context: 上下文（可含触发词，参与升级决策与首轮注入）
        config: thinking_upgrade 配置字典；enabled=False 时直接走普通路径

    Returns:
        Tuple[str, ThinkingTrace]: (最终答案, 深度推理轨迹)
    """
    cfg: dict[str, Any] = config if config is not None else {}
    if not cfg.get("enabled", False):
        # 未启用 → 直接走普通 chat_with_routing，返回最小轨迹
        from core.llm_gateway import chat_with_routing  # 惰性导入 (拆分后宿主函数)
        response = await chat_with_routing(prompt, task_type)
        decision = ThinkingUpgradeDecision(
            False, "disabled", task_type.name, 0.0,
            ThinkingBudget.from_config(cfg),
        )
        trace = ThinkingTrace(
            prompt, task_type.name, decision, [], response.content or "",
            response.cost_usd, response.latency_ms,
            error="llm_call_failed" if not response.success else None,
        )
        return trace.final_answer or "", trace
    policy = ThinkingUpgradePolicy(thinking_config=cfg)
    return await policy.execute_with_thinking(prompt, task_type, context)


if __name__ == "__main__":
    import asyncio
    import base64
    import io

    def _make_test_jpeg_b64() -> str | None:
        """生成 8x8 白色 JPEG 的 base64，用于 VISION 自测。

        依赖 Pillow；缺失时返回 None，VISION 测试将被跳过。
        """
        try:
            from PIL import Image  # type: ignore
        except ImportError:
            return None
        img = Image.new("RGB", (8, 8), (255, 255, 255))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode("ascii")

    async def _main() -> None:
        # 加载 .env（override=True 强制覆盖陈旧的系统环境变量，.env 为唯一权威源）
        try:
            from dotenv import load_dotenv  # type: ignore
            load_dotenv(override=True)
        except ImportError:
            _load_dotenv_manual()

        # 配置主 Provider + 多 Provider
        llm_gateway.configure_from_env()
        llm_gateway.configure_providers_from_env()

        print("=" * 60)
        print("已配置 Provider 清单")
        print("=" * 60)
        for name, cfg in llm_gateway._config.providers.items():
            models = list(cfg.get("models", {}).keys())
            print(f"  [{name:10s}] base_url={cfg.get('base_url')}")
            print(f"              models={models}")

        print("\nProvider 健康状态:")
        for name, h in llm_gateway.get_health().items():
            print(f"  [{name:10s}] status={h['status']}")

        # 测试 THINKING 调用
        print("\n" + "=" * 60)
        print("测试 chat_thinking() — 深度推理")
        print("=" * 60)
        resp = await chat_thinking(
            "1+1=?  请只输出最终数字。",
            system_prompt="你是数学助手，必须简短回答。",
        )
        print(f"  success : {resp.success}")
        print(f"  provider: {resp.provider}")
        print(f"  model   : {resp.model}")
        print(f"  latency : {resp.latency_ms:.0f} ms")
        print(f"  tokens  : in={resp.tokens_input} out={resp.tokens_output}")
        if resp.success:
            print(f"  content : {resp.content[:200]}")
        else:
            print(f"  error   : {_sanitize_log_text(resp.error)}")

        # 测试 VISION 调用
        print("\n" + "=" * 60)
        print("测试 chat_vision() — 多模态（8x8 白色 JPEG）")
        print("=" * 60)
        test_jpeg = _make_test_jpeg_b64()
        if test_jpeg is None:
            print("  跳过：未安装 Pillow，无法生成测试图片")
        else:
            resp = await chat_vision(
                "请用一句话描述这张图片的颜色和内容。",
                images=[test_jpeg],
                system_prompt="你是图像分析专家，请简短回答。",
            )
            print(f"  success : {resp.success}")
            print(f"  provider: {resp.provider}")
            print(f"  model   : {resp.model}")
            print(f"  latency : {resp.latency_ms:.0f} ms")
            print(f"  tokens  : in={resp.tokens_input} out={resp.tokens_output}")
            if resp.success:
                print(f"  content : {resp.content[:200]}")
            else:
                print(f"  error   : {_sanitize_log_text(resp.error)}")

        # 统计
        print("\n" + "=" * 60)
        print("网关统计:")
        print("=" * 60)
        stats = llm_gateway.get_stats()
        print(f"  total_requests: {stats['total_requests']}")
        print(f"  success_rate  : {stats['success_rate']}")
        print(f"  avg_latency_ms: {stats['avg_latency_ms']}")

        await llm_gateway.close()

    asyncio.run(_main())


# ── 宿主符号接入 (2026-08-14): 拆分后本模块运行时需要 llm_gateway 主模块
# 定义的 ModelTier/TASK_TIER_MAP。此导入位于模块底部, 两种加载路径均安全:
#   1) llm_gateway 尾部 import 本模块时: 宿主名字已定义, 直接成功
#   2) 直接 import 本模块时: 触发 llm_gateway 加载, 其尾部 import 本模块
#      (类已定义完毕) 后返回, 随后本导入成功 — 无循环死锁
try:
    from core import llm_gateway  # noqa: E402  # 模块级单例 (宿主符号接入)
    from core.llm_gateway import (  # noqa: E402
        TASK_TIER_MAP,
        LLMUnavailableError,
        ModelTier,
        ThinkingBudget,
        ThinkingRound,
        ThinkingTrace,
        ThinkingUpgradeDecision,
        _load_dotenv_manual,
        _sanitize_log_text,
        chat_thinking,
        chat_vision,
    )
except ImportError:  # 极端情况: 兜底空值
    llm_gateway = None  # type: ignore
    LLMUnavailableError = RuntimeError  # type: ignore
    ModelTier = None  # type: ignore
    TASK_TIER_MAP = {}  # type: ignore
    ThinkingBudget = ThinkingRound = ThinkingTrace = None  # type: ignore
    ThinkingUpgradeDecision = None  # type: ignore
    chat_thinking = chat_vision = _sanitize_log_text = _load_dotenv_manual = None  # type: ignore
